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

from miyano_portal import dat_hang, gia_hdnt
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

    def test_khach_chua_co_bang_gia_thi_bo_qua_khong_vo_submit(self):
        """Không được chặn việc ký hợp đồng chỉ vì chưa cấu hình bảng giá —
        nhưng cũng không được im lặng: trả lý do để người submit nhìn thấy."""
        frappe.db.set_value("Customer", KHACH, "default_price_list", None)
        bo = self._hdnt()   # submit phải thành công
        self.assertEqual(bo.docstatus, 1)
        ket_qua = gia_hdnt.dong_bo(bo.name)
        self.assertEqual(ket_qua["tao"], 0)
        self.assertTrue(ket_qua["ly_do"], "phải nêu rõ vì sao không đồng bộ được")

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
        `portal_contracts` đã tự chặn đặt hàng cho tới `from_date`, nên giá
        "có sớm" vô hại, còn bắt sales quay lại nhập tay đúng ngày mới là hại."""
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
    NHIỀU hợp đồng còn hiệu lực cùng lúc (`portal_contracts` chỉ lọc theo
    khoảng ngày, và `portal_order_place` nhận `contract` làm tham số). Trình
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


class TestDanhMucVaDatHangKHONGCONLECH(_GiaFixture):
    """Task 12 (QĐ-G12) — điểm LỆCH mà lớp này từng GHIM đã bị xoá hẳn.

    LỊCH SỬ, đọc trước khi sửa: lớp này tên cũ là `TestDanhMucVaDatHangCoThe
    LECH` và khẳng định ĐÚNG cái sai — `portal_catalog` tra `Item Price` rồi
    rơi về `Blanket Order Item.rate`, trong khi đường đặt hàng chỉ chấp nhận
    `Item Price`, nên danh mục hiện giá đẹp còn gửi đơn thì bị chặn "chưa có
    giá trong hợp đồng". Docstring cũ tự nói rõ: ai sửa hành vi đó phải cập
    nhật lại chính test này, có ý thức. Task 12 là lần sửa đó — chủ đầu tư
    gặp đúng điểm lệch ấy trên trình duyệt ngày 21/08.

    Giờ CẢ HAI phía hỏi cùng một hàm (`gia_hdnt.gia_dong_hop_dong`), nên
    khẳng định đúng của lớp này là hai bên KHỚP NHAU. Bài dưới còn cố ý cài
    một `Item Price` KHÁC giá hợp đồng: nếu ai đó lật ngược thứ tự tra (bảng
    giá trước, hợp đồng sau) thì danh mục và đơn lại nói hai con số, và bài
    này đỏ."""

    def test_danh_muc_va_don_hang_noi_cung_mot_gia(self):
        bo = self._hdnt(dong=[{"item_code": VT, "qty": 500, "rate": 95000}])
        # Bảng giá khai một con số KHÁC — hợp đồng đã ký phải THẮNG, ở CẢ HAI
        # phía. Không có dòng này, bài xanh cả khi bảng giá được ưu tiên.
        frappe.db.delete("Item Price", {"price_list": BANG_GIA})
        frappe.get_doc({
            "doctype": "Item Price", "item_code": VT, "price_list": BANG_GIA,
            "selling": 1, "price_list_rate": 55000,
        }).insert(ignore_permissions=True)

        frappe.set_user(KHACH_USER)
        dong = {r["item_code"]: r for r in portal.portal_catalog(bo.name)}[VT]
        self.assertEqual(dong["rate"], 95000, "danh mục phải hiện GIÁ HỢP ĐỒNG")

        res = portal.portal_order_place(
            bo.name,
            json.dumps([{"item_code": VT, "qty": 1}]),
            request_id=frappe.generate_hash(length=12),
        )
        so = frappe.get_doc("Sales Order", res["sales_order"])
        self.assertEqual(
            float(so.items[0].rate), dong["rate"],
            "giá khách NHÌN THẤY và giá đơn MANG phải là một",
        )


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

    def test_chua_khai_gia_o_dau_ca_thi_van_bao_thieu_gia(self):
        """Ca ĐỐI CHỨNG — không có ca này thì test trên có thể xanh vì một lý
        do khác (vd. site tình cờ đã có Item Price) mà ta không biết.

        Task 12 (QĐ-G12) — ĐỔI ĐỐI CHỨNG, không nới lỏng nó. Bản cũ xoá
        `Item Price` rồi đòi cổng phải CHẶN; từ QĐ-G12 cổng đọc thẳng `rate`
        của hợp đồng nên nó KHÔNG chặn nữa, và đó chính là bản vá, không phải
        hồi quy (vế dương ở `TestDanhMucVaDatHangKHONGCONLECH` và ở
        `test_gia_tu_hop_dong.py`). "Thiếu giá" giờ có nghĩa CHƯA KHAI Ở ĐÂU
        CẢ: `rate = 0` trên hợp đồng VÀ không có dòng bảng giá — và cổng vẫn
        phải chặn, nguyên văn.

        Đứng trên KHÁCH RIÊNG (`_khach_rieng()`): đây là một khẳng định về sự
        VẮNG MẶT, mà `FrappeTestCase` rollback MỘT LẦN mỗi CLASS nên hợp đồng
        của method chạy trước vẫn còn hiệu lực ở đây và sẽ khai giá hộ."""
        khach, _bang_gia = self._khach_rieng()
        bo = self._hdnt(customer=khach, dong=[{"item_code": VT, "qty": 500, "rate": 0}])
        with self.assertRaises(frappe.ValidationError) as ctx:
            dat_hang.tao_sales_order(
                khach, contract=bo.name, items=[{"item_code": VT, "qty": 2}],
                request_id=frappe.generate_hash(length=12),
            )
        self.assertIn("chưa có giá trong hợp đồng", str(ctx.exception))


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
