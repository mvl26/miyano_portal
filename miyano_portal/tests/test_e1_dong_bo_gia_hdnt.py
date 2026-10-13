"""Đồng bộ đơn giá HĐNT → `Item Price` (sửa lỗi "chưa có giá trong hợp đồng").

**Lỗi gốc, đã dựng lại được trên site thật:** cổng KHÔNG đọc `rate` của
`Blanket Order Item`. Ba đường đặt hàng (`portal_order_place` HĐNT, bán lẻ,
`portal_reorder`) chỉ tra `Item Price` trong `Customer.default_price_list`,
trong khi `portal_catalog` lại rơi về `row["rate"]` khi không có Item Price.
Hệ quả: danh mục HIỆN giá đẹp, khách bỏ vào giỏ, đến lúc gửi thì bị chặn
"… chưa có giá trong hợp đồng" — kế toán/sales nhìn vào HĐNT thấy rate rành
rành nên không hiểu chuyện gì. Trên `erptest.local` lúc phát hiện: cả site có
**0 bản ghi `Item Price`** dù ba bảng giá HĐNT đều tồn tại và ba HĐNT đều có
rate.

Cách sửa đã chốt: sales nhập giá MỘT lần trên HĐNT, submit HĐNT thì hệ thống
tự dựng `Item Price` trong bảng giá của khách. Giữ nguyên cơ chế bảng giá của
ERPNext (không bỏ qua Item Price ở đường đặt hàng) để đơn hàng nhân viên sửa
trên Desk vẫn nạp lại đúng giá.

Test dưới đây khoá CẢ HAI tầng: hàm đồng bộ, và bằng chứng cuối cùng — sau khi
submit HĐNT thì `portal_order_place` đặt được hàng thật, không còn `thieu_gia`.
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from miyano_portal import bang_gia_khach, dat_hang, gia_hdnt
from miyano_portal.api import portal
from miyano_portal.setup.seed_demo import COMPANY, seed_demo

KHACH = "PXN ABC"
KHACH_USER = "pxnabc@demo.miyano"
BANG_GIA = "HĐNT-TEST-DONGBO"
VT = "VT0005"
HC = "HC0009"


class _GiaFixture(FrappeTestCase):
    """HĐNT có rate nhưng bảng giá RỖNG — đúng hình dạng dữ liệu đã gây lỗi
    trên site thật (bảng giá được tạo, Item Price thì không)."""

    def setUp(self):
        seed_demo()
        self.addCleanup(frappe.set_user, "Administrator")
        frappe.set_user("Administrator")

        if not frappe.db.exists("Price List", BANG_GIA):
            frappe.get_doc({
                "doctype": "Price List", "price_list_name": BANG_GIA,
                "selling": 1, "enabled": 1, "currency": "VND",
            }).insert(ignore_permissions=True)
        frappe.db.set_value("Customer", KHACH, "default_price_list", BANG_GIA)
        # Sạch tuyệt đối: test phải bắt đầu từ "chưa có giá nào".
        frappe.db.delete("Item Price", {"price_list": BANG_GIA})

    def _hdnt(self, dong=None, submit=True, customer=KHACH, loai="Selling"):
        dong = dong if dong is not None else [
            {"item_code": VT, "qty": 500, "rate": 95000},
            {"item_code": HC, "qty": 300, "rate": 1250000},
        ]
        bo = frappe.new_doc("Blanket Order")
        bo.blanket_order_type = loai
        bo.company = COMPANY
        if loai == "Selling":
            bo.customer = customer
        else:
            bo.supplier = customer
        bo.from_date = today()
        bo.to_date = add_days(today(), 365)
        for d in dong:
            bo.append("items", d)
        bo.insert(ignore_permissions=True)
        if submit:
            bo.submit()
        return bo

    def _khach_rieng(self):
        """Khách + bảng giá DÙNG RIÊNG cho một test method.

        `FrappeTestCase` rollback MỘT LẦN MỖI CLASS, nên hợp đồng do test
        chạy trước tạo ra vẫn còn khi test sau chạy — mà `dong_bo_khach` cố ý
        quét MỌI hợp đồng của khách, nên mọi ca khẳng định "KHÔNG có giá" sẽ
        đỏ vì hợp đồng của test khác. Ca nào khẳng định sự VẮNG MẶT thì phải
        đứng trên khách của riêng nó."""
        hau_to = frappe.generate_hash(length=6)
        ten, bang_gia = f"KH Test Giá {hau_to}", f"BG-Test-{hau_to}"
        frappe.get_doc({
            "doctype": "Price List", "price_list_name": bang_gia,
            "selling": 1, "enabled": 1, "currency": "VND",
        }).insert(ignore_permissions=True)
        frappe.get_doc({
            "doctype": "Customer", "customer_name": ten, "customer_type": "Company",
            "customer_group": "All Customer Groups", "territory": "All Territories",
            "default_price_list": bang_gia,
        }).insert(ignore_permissions=True)
        return ten, bang_gia

    def _gia(self, item_code, bang_gia=BANG_GIA):
        return frappe.db.get_value(
            "Item Price",
            {"item_code": item_code, "price_list": bang_gia, "selling": 1},
            "price_list_rate",
        )


class TestDongBoGia(_GiaFixture):
    def test_submit_hdnt_tao_item_price_theo_rate(self):
        self._hdnt()
        self.assertEqual(self._gia(VT), 95000)
        self.assertEqual(self._gia(HC), 1250000)

    def test_ghi_hong_giua_chung_khong_de_lai_gia_nua_voi(self):
        """Final-fix S-4: dòng thứ hai ghi hỏng → giá dòng thứ nhất KHÔNG được
        nằm lại trong bảng (một bảng giá nửa vời trông như đã đồng bộ xong),
        và việc ký hợp đồng vẫn thành công — hook nuốt lỗi như cũ."""
        from unittest.mock import patch

        that = bang_gia_khach.ghi_gia_vao_bang
        da_ghi = []

        def hong_o_dong_hai(bang, customer, item_code, gia, tien_te=None):
            if da_ghi:
                raise RuntimeError("giả lập: ghi dòng thứ hai hỏng")
            da_ghi.append(item_code)
            return that(bang, customer, item_code, gia, tien_te)

        with patch.object(bang_gia_khach, "ghi_gia_vao_bang", side_effect=hong_o_dong_hai):
            bo = self._hdnt()

        self.assertEqual(da_ghi, [VT], "dòng thứ nhất phải đã được ghi thật trước khi hỏng")
        self.assertEqual(frappe.db.get_value("Blanket Order", bo.name, "docstatus"), 1)
        self.assertIsNone(self._gia(VT), "giá dòng thứ nhất phải được lùi lại")
        self.assertIsNone(self._gia(HC))
        self.assertEqual(frappe.db.count("Item Price", {"price_list": BANG_GIA}), 0)

    def test_item_price_dung_uom_va_currency_cua_bang_gia(self):
        self._hdnt()
        row = frappe.db.get_value(
            "Item Price", {"item_code": VT, "price_list": BANG_GIA, "selling": 1},
            ["uom", "currency", "selling", "buying"], as_dict=True,
        )
        self.assertEqual(row.uom, frappe.db.get_value("Item", VT, "stock_uom"))
        self.assertEqual(row.currency, "VND")
        self.assertEqual(row.selling, 1)
        self.assertEqual(row.buying, 0)

    def test_chay_lai_khong_tao_trung(self):
        bo = self._hdnt()
        gia_hdnt.dong_bo(bo.name)
        gia_hdnt.dong_bo(bo.name)
        self.assertEqual(
            frappe.db.count("Item Price", {"item_code": VT, "price_list": BANG_GIA}), 1
        )

    def test_rate_khong_tron_chay_lai_khong_ghi_lai(self):
        """Rate hợp đồng nhiều chữ số lẻ: lần chạy sau so theo giá đã làm tròn
        như bộ ghi, nên không báo "đã ghi" mãi."""
        bo = self._hdnt(dong=[{"item_code": VT, "qty": 5, "rate": 95000.123456789}])
        gia_hdnt.dong_bo(bo.name)
        ket_qua = gia_hdnt.dong_bo(bo.name)
        self.assertEqual((ket_qua["tao"], ket_qua["cap_nhat"]), (0, 0))

    def test_gia_hdnt_doi_thi_item_price_doi_theo(self):
        """HĐNT là nguồn sự thật về giá đã ký: rate mới (qua sửa đổi hợp đồng)
        phải ĐÈ giá cũ, không im lặng giữ giá cũ rồi xuất hoá đơn sai."""
        bo = self._hdnt()
        frappe.db.set_value("Blanket Order Item", {"parent": bo.name, "item_code": VT}, "rate", 99000)
        ket_qua = gia_hdnt.dong_bo(bo.name)
        self.assertEqual(self._gia(VT), 99000)
        self.assertEqual(ket_qua["cap_nhat"], 1)
        self.assertEqual(ket_qua["tao"], 0)

    def test_rate_0_khong_tao_gia_0(self):
        """rate 0 = CHƯA khai giá, không phải "bán 0 đồng". Tạo một Item Price
        giá 0 sẽ khiến đường đặt hàng (`if not rate`) vẫn báo thiếu giá nhưng
        sales lại thấy bảng giá "đã có dòng" — che mất việc cần làm."""
        khach, bang_gia = self._khach_rieng()
        bo = self._hdnt(customer=khach, dong=[{"item_code": VT, "qty": 500, "rate": 0}])
        self.assertIsNone(self._gia(VT, bang_gia))
        ket_qua = gia_hdnt.dong_bo(bo.name)
        self.assertEqual(ket_qua["tao"], 0)
        self.assertIn(VT, [b["item_code"] for b in ket_qua["bo_qua"]])

    def test_hdnt_mua_hang_khong_dung_toi(self):
        """`blanket_order_type = Purchasing` là hợp đồng MUA của Miyano —
        không liên quan bảng giá bán của khách."""
        # Tự dựng Supplier thay vì `skipTest` khi site không có: một test bị
        # skip không chứng minh được nhánh `Purchasing` có thật sự được chặn.
        ncc = "NCC Test Đồng Bộ Giá"
        if not frappe.db.exists("Supplier", ncc):
            frappe.get_doc({
                "doctype": "Supplier", "supplier_name": ncc,
                "supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"),
            }).insert(ignore_permissions=True)
        bo = self._hdnt(customer=ncc, loai="Purchasing")
        self.assertEqual(gia_hdnt.dong_bo(bo.name)["tao"], 0)
        self.assertIsNone(self._gia(VT))

    # Đảo theo spec 2026-10-09 (giá theo Price List).
    def test_khach_chua_co_bang_gia_thi_duoc_tao_bang_rieng_va_ghi_gia(self):
        """§5.3 — khách chưa có `default_price_list` KHÔNG còn bị bỏ qua kèm
        `ly_do`: ký hợp đồng là khách có bảng giá của riêng mình, và đơn giá
        hợp đồng nằm trong đó."""
        khach, _bang_gia = self._khach_rieng()
        frappe.db.set_value("Customer", khach, "default_price_list", None)
        bo = self._hdnt(customer=khach)   # submit phải thành công
        self.assertEqual(bo.docstatus, 1)
        bang = frappe.db.get_value("Customer", khach, "default_price_list")
        self.assertTrue(bang, "ký hợp đồng phải dựng bảng giá riêng cho khách")
        self.assertEqual(
            frappe.get_all("Customer", filters={"default_price_list": bang}, pluck="name"),
            [khach],
        )
        self.assertEqual(bang_gia_khach.gia_bang_gia(khach, VT), 95000.0)
        self.assertEqual(bang_gia_khach.gia_bang_gia(khach, HC), 1250000.0)
        ket_qua = gia_hdnt.dong_bo(bo.name)
        self.assertIsNone(ket_qua["ly_do"])
        self.assertEqual((ket_qua["tao"], ket_qua["cap_nhat"]), (0, 0), "chạy lại không ghi gì")

    # -- BỘ GHI PHẢI KHỚP BỘ ĐỌC (spec 2026-10-09 §3.1) -----------------------
    # Ba ca dưới chỉ khẳng định KẾT CỤC: sau `dong_bo`, bộ đọc của cổng trả
    # đúng giá hợp đồng. Dòng nào được sửa/chèn là việc của bộ ghi chung
    # (`bang_gia_khach.ghi_gia_vao_bang`).

    def _dong_gia(self, bang_gia, rate, **them):
        return frappe.get_doc({
            "doctype": "Item Price", "item_code": VT, "price_list": bang_gia,
            "selling": 1, "price_list_rate": rate, **them,
        }).insert(ignore_permissions=True)

    def test_bang_dang_co_dong_het_han_thi_bo_doc_van_ra_gia_hop_dong(self):
        """Dòng cũ ĐÚNG giá hợp đồng nhưng đã hết hạn: phép upsert cũ thấy
        "đã khớp" và bỏ qua, cổng thì không thấy giá nào."""
        khach, bang_gia = self._khach_rieng()
        self._dong_gia(bang_gia, 95000, valid_from=add_days(today(), -30),
                       valid_upto=add_days(today(), -1))
        self.assertIsNone(bang_gia_khach.gia_bang_gia(khach, VT))
        bo = self._hdnt(customer=khach, dong=[{"item_code": VT, "qty": 500, "rate": 95000}])
        gia_hdnt.dong_bo(bo.name)
        self.assertEqual(bang_gia_khach.gia_bang_gia(khach, VT), 95000.0)

    def test_bang_dang_co_dong_rieng_cua_khach_thi_bo_doc_van_ra_gia_hop_dong(self):
        """Dòng gắn riêng khách che dòng chung ở bộ đọc: sửa dòng chung thì
        giá hợp đồng không bao giờ hiện ra."""
        khach, bang_gia = self._khach_rieng()
        self._dong_gia(bang_gia, 50000)
        self._dong_gia(bang_gia, 40000, customer=khach)
        self.assertEqual(bang_gia_khach.gia_bang_gia(khach, VT), 40000.0)
        bo = self._hdnt(customer=khach, dong=[{"item_code": VT, "qty": 500, "rate": 95000}])
        gia_hdnt.dong_bo(bo.name)
        self.assertEqual(bang_gia_khach.gia_bang_gia(khach, VT), 95000.0)

    def test_bang_dang_co_dong_khac_don_vi_thi_bo_doc_van_ra_gia_hop_dong(self):
        """Dòng duy nhất của mã là giá theo một đơn vị KHÁC đơn vị gốc: bộ
        đọc bỏ qua nó, nên ghi giá hợp đồng vào đó là ghi vào chỗ không ai đọc."""
        khach, bang_gia = self._khach_rieng()
        goc = frappe.db.get_value("Item", VT, "stock_uom")
        khac = "Box" if goc != "Box" else "Nos"
        self._dong_gia(bang_gia, 95000, uom=khac)
        self.assertIsNone(bang_gia_khach.gia_bang_gia(khach, VT))
        bo = self._hdnt(customer=khach, dong=[{"item_code": VT, "qty": 500, "rate": 95000}])
        gia_hdnt.dong_bo(bo.name)
        self.assertEqual(bang_gia_khach.gia_bang_gia(khach, VT), 95000.0)
        self.assertEqual(
            float(frappe.db.get_value(
                "Item Price", {"item_code": VT, "price_list": bang_gia, "uom": khac},
                "price_list_rate",
            )),
            95000.0, "dòng theo đơn vị khác không bị đụng tới",
        )

    def test_cung_ma_hai_dong_gia_khong_tron_chi_ghi_mot_lan(self):
        """Hợp đồng liệt kê cùng một mã hai dòng, cùng một giá KHÔNG TRÒN:
        dòng sau phải thấy giá (đã làm tròn) dòng trước vừa ghi, không ghi lần
        hai. Dựng chứng từ trong bộ nhớ: ERPNext không cho lưu hợp đồng trùng
        mã, nhưng dữ liệu nhập ngoài luồng thì có."""
        khach, _bang_gia = self._khach_rieng()
        le = 95000.123456789
        bo = frappe.get_doc({
            "doctype": "Blanket Order", "blanket_order_type": "Selling",
            "customer": khach, "company": COMPANY, "name": "_TEST BO TRUNG MA",
            "from_date": today(), "to_date": add_days(today(), 365),
            "items": [
                {"item_code": VT, "qty": 500, "rate": le},
                {"item_code": VT, "qty": 500, "rate": le},
            ],
        })
        self.assertNotEqual(bang_gia_khach.lam_tron_gia(le, "VND"), le, "tiền đề: giá không tròn")
        ket_qua = gia_hdnt.dong_bo(bo)
        self.assertEqual((ket_qua["tao"], ket_qua["cap_nhat"]), (1, 0))
        self.assertEqual(
            bang_gia_khach.gia_bang_gia(khach, VT), bang_gia_khach.lam_tron_gia(le, "VND")
        )

    def test_hdnt_het_han_khong_dat_gia_cho_hom_nay(self):
        """Lỗi thật đã bị `test_e6_mua_le` bắt: `dong_bo` suy bảng giá từ
        KHÁCH chứ không từ hợp đồng, nên một HĐNT cũ đã hết hiệu lực (khách
        có thể có nhiều hợp đồng qua các năm) sẽ ghi đè giá của hợp đồng
        ĐANG chạy. Hết hạn = không có quyền đặt giá cho hôm nay."""
        khach, bang_gia = self._khach_rieng()
        bo = self._hdnt(customer=khach, submit=False)
        bo.from_date = add_days(today(), -400)
        bo.to_date = add_days(today(), -30)
        bo.save(ignore_permissions=True)
        bo.submit()
        self.assertIsNone(self._gia(VT, bang_gia))
        self.assertIn("hết hiệu lực", gia_hdnt.dong_bo(bo.name)["ly_do"])

    def test_hdnt_chua_toi_ngay_hieu_luc_van_dung_gia_san(self):
        """Ngược lại với ca trên: ký trước ngày hiệu lực thì vẫn dựng giá —
        giá "có sớm" được coi là vô hại (xem chú thích ở `gia_hdnt.dong_bo`),
        còn bắt sales quay lại nhập tay đúng ngày mới là hại."""
        bo = self._hdnt(submit=False)
        bo.from_date = add_days(today(), 10)
        bo.to_date = add_days(today(), 400)
        bo.save(ignore_permissions=True)
        bo.submit()
        self.assertEqual(self._gia(VT), 95000)

    def test_khong_dong_cham_bang_gia_cua_khach_khac(self):
        from miyano_portal.setup.seed_demo import PRICE_LIST

        truoc = frappe.db.count("Item Price", {"price_list": PRICE_LIST})
        self._hdnt()
        self.assertEqual(frappe.db.count("Item Price", {"price_list": PRICE_LIST}), truoc)


class TestNhieuHopDongMotKhach(_GiaFixture):
    """`Customer.default_price_list` là MỘT field, nhưng một khách có thể có
    NHIỀU hợp đồng còn hiệu lực cùng lúc (không gì ép mỗi khách một hợp
    đồng). Trình
    import lại đặt mỗi hợp đồng một bảng giá riêng rồi trỏ `default_price_list`
    sang bảng giá MỚI NHẤT — hợp đồng cũ hơn bị bỏ lại ở bảng giá không còn
    ai đọc, và lỗi "chưa có giá" quay lại đúng cho hợp đồng đó."""

    def test_ky_hop_dong_moi_khong_lam_hop_dong_cu_mat_gia(self):
        bang_gia_2 = BANG_GIA + "-2"
        self._hdnt(dong=[{"item_code": VT, "qty": 500, "rate": 95000}])

        # Ký hợp đồng thứ hai — trình import trỏ bảng giá mặc định sang bảng
        # MỚI trước khi hợp đồng mới được submit.
        if not frappe.db.exists("Price List", bang_gia_2):
            frappe.get_doc({
                "doctype": "Price List", "price_list_name": bang_gia_2,
                "selling": 1, "enabled": 1, "currency": "VND",
            }).insert(ignore_permissions=True)
        frappe.db.set_value("Customer", KHACH, "default_price_list", bang_gia_2)
        self._hdnt(dong=[{"item_code": HC, "qty": 300, "rate": 1250000}])

        self.assertEqual(self._gia(HC, bang_gia_2), 1250000, "hợp đồng mới phải có giá")
        self.assertEqual(
            self._gia(VT, bang_gia_2), 95000,
            "hợp đồng CŨ còn hiệu lực cũng phải có giá trong bảng giá đang dùng",
        )

    def test_dat_hang_theo_hop_dong_cu_van_chay(self):
        bang_gia_2 = BANG_GIA + "-2"
        bo_cu = self._hdnt(dong=[{"item_code": VT, "qty": 500, "rate": 95000}])
        if not frappe.db.exists("Price List", bang_gia_2):
            frappe.get_doc({
                "doctype": "Price List", "price_list_name": bang_gia_2,
                "selling": 1, "enabled": 1, "currency": "VND",
            }).insert(ignore_permissions=True)
        frappe.db.set_value("Customer", KHACH, "default_price_list", bang_gia_2)
        self._hdnt(dong=[{"item_code": HC, "qty": 300, "rate": 1250000}])

        frappe.set_user(KHACH_USER)
        res = portal.portal_order_place(
            bo_cu.name,
            json.dumps([{"item_code": VT, "qty": 1}]),
            request_id=frappe.generate_hash(length=12),
        )
        self.assertTrue(res.get("sales_order"))


class TestDonHangLayGiaBangGia(_GiaFixture):
    """Đơn lấy giá từ Price List của khách, không từ hợp đồng (spec
    2026-10-09 §4.2).

    LỊCH SỬ, đọc trước khi sửa: lớp này từng tên `TestDanhMucVaDatHangCoThe
    LECH` (ghim điểm lệch "danh mục hiện giá, đơn bị chặn chưa có giá"), rồi
    `TestDanhMucVaDatHangKHONGCONLECH` khi Task 12 (QĐ-G12) cho cả danh mục
    cũ lẫn đơn hỏi chung `gia_hdnt.gia_dong_hop_dong` (hàm đã xoá) — hợp đồng THẮNG bảng
    giá ở cả hai phía. Spec 2026-10-09 đảo vế ĐƠN: nguồn giá duy nhất của
    đơn là Price List. Bài dưới cố ý cài một `Item Price` KHÁC giá hợp đồng
    để phân biệt được hai nguồn."""

    # Đảo theo spec 2026-10-09 (giá theo Price List).
    def test_don_hang_lay_gia_bang_gia_khi_lech_voi_hop_dong(self):
        """Hợp đồng khai 95.000, Price List của khách bị sửa tay thành 55.000
        → đơn mang giá PRICE LIST (§4.2).

        Trước spec 2026-10-09 bài này tên `test_danh_muc_va_don_hang_noi_
        cung_mot_gia` và đòi đơn mang đúng 95.000 mà danh mục cũ
        `portal_catalog` hiện. Endpoint danh mục cũ đó đã gỡ (§7), nên vế
        danh mục nay hỏi `portal_catalog_gop`: danh mục và đơn nói CÙNG một
        giá, giá Price List."""
        bo = self._hdnt(dong=[{"item_code": VT, "qty": 500, "rate": 95000}])
        frappe.db.delete("Item Price", {"price_list": BANG_GIA})
        frappe.get_doc({
            "doctype": "Item Price", "item_code": VT, "price_list": BANG_GIA,
            "selling": 1, "price_list_rate": 55000,
        }).insert(ignore_permissions=True)

        frappe.set_user(KHACH_USER)
        dong = {
            r["item_code"]: r for r in portal.portal_catalog_gop(tu_khoa=VT)["rows"]
        }[VT]
        self.assertEqual(dong["tang"], "bang_gia")
        self.assertEqual(dong["don_gia"], 55000, "danh mục hiện giá Price List")

        res = portal.portal_order_place(
            bo.name,
            json.dumps([{"item_code": VT, "qty": 1}]),
            request_id=frappe.generate_hash(length=12),
        )
        so = frappe.get_doc("Sales Order", res["sales_order"])
        self.assertEqual(float(so.items[0].rate), 55000.0)
        self.assertEqual(so.items[0].custom_nguon_gia, "Bảng giá")


class TestDatHangDuocSauKhiDongBo(_GiaFixture):
    """Bằng chứng cuối cùng: đúng thao tác đã báo lỗi cho khách."""

    def test_dat_hang_khong_con_bao_thieu_gia(self):
        bo = self._hdnt()
        frappe.set_user(KHACH_USER)
        res = portal.portal_order_place(
            bo.name,
            json.dumps([{"item_code": VT, "qty": 2}]),
            request_id=frappe.generate_hash(length=12),
        )
        self.assertTrue(res.get("sales_order"))
        so = frappe.get_doc("Sales Order", res["sales_order"])
        self.assertEqual(so.items[0].rate, 95000)

    # Đảo theo spec 2026-10-09 (giá theo Price List).
    def test_chua_khai_gia_o_dau_ca_thi_la_dong_cho_bao_gia(self):
        """Ca ĐỐI CHỨNG — không có ca này thì test trên có thể xanh vì một lý
        do khác (vd. site tình cờ đã có Item Price) mà ta không biết.

        "Chưa có giá" = `rate = 0` trên hợp đồng VÀ không có dòng bảng giá.
        Trước spec 2026-10-09 cổng CHẶN đơn bằng "chưa có giá trong hợp
        đồng"; giờ đơn TẠO ĐƯỢC, dòng đó mang `rate = 0` và chờ Miyano báo
        giá (§4.2).

        Đứng trên KHÁCH RIÊNG (`_khach_rieng()`): đây là một khẳng định về sự
        VẮNG MẶT, mà `FrappeTestCase` rollback MỘT LẦN mỗi CLASS nên hợp đồng
        của method chạy trước vẫn còn hiệu lực ở đây và sẽ khai giá hộ."""
        khach, _bang_gia = self._khach_rieng()
        bo = self._hdnt(customer=khach, dong=[{"item_code": VT, "qty": 500, "rate": 0}])
        kq = dat_hang.tao_sales_order(
            khach, contract=bo.name, items=[{"item_code": VT, "qty": 2}],
            request_id=frappe.generate_hash(length=12),
        )
        so = frappe.get_doc("Sales Order", kq["sales_order"])
        self.assertEqual(float(so.items[0].rate), 0.0)
        self.assertEqual(so.items[0].custom_nguon_gia, "Báo giá")
        self.assertEqual(so.custom_loai_don, "Mua lẻ")


class TestBackfill(_GiaFixture):
    """Patch vá dữ liệu cũ — ba HĐNT trên site thật đã submit từ trước khi có
    hook, nên hook không bao giờ chạy cho chúng."""

    def test_backfill_dung_cho_hdnt_da_submit_tu_truoc(self):
        bo = self._hdnt()
        frappe.db.delete("Item Price", {"price_list": BANG_GIA})   # mô phỏng dữ liệu cũ
        from miyano_portal.patches.v1_13.dong_bo_gia_hdnt import execute

        execute()
        self.assertEqual(self._gia(VT), 95000)

    def test_backfill_chay_lai_duoc_nhieu_lan(self):
        self._hdnt()
        from miyano_portal.patches.v1_13.dong_bo_gia_hdnt import execute

        execute()
        execute()
        self.assertEqual(
            frappe.db.count("Item Price", {"item_code": VT, "price_list": BANG_GIA}), 1
        )

    def test_backfill_bo_qua_hdnt_nhap_va_da_huy(self):
        bo_nhap = self._hdnt(submit=False)
        from miyano_portal.patches.v1_13.dong_bo_gia_hdnt import execute

        frappe.db.delete("Item Price", {"price_list": BANG_GIA})
        execute()
        self.assertIsNone(self._gia(VT), f"HĐNT nháp {bo_nhap.name} chưa ký thì chưa có giá")
