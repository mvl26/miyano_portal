"""E6 phần B — Mua lẻ ngoài HĐNT, giỏ 2 ngăn, báo giá hết hiệu lực.

Xem docs/Miyano-Portal(Client)_V2/DevHandoff/15_PRD_E6_MuaLe_YeuCauHang.md
(US-E6.1/E6.2/E6.5), 30_API_Spec.md (§1.1, §2.2, §2.4), 40_TestCases.md
(TC-E6-01…04, 09…11), BA §4.10 (BR-R1…R7, NL-10.x).

Fixtures riêng của module này (KHÔNG sửa `setup/seed_demo.py`): một Price
List bán lẻ + hai item bán lẻ, gắn thêm vào dữ liệu `seed_demo()` sẵn có
(Bệnh viện Bạch Mai có HĐNT với VT0005/HC0009). `FrappeTestCase` rollback
một lần mỗi CLASS — mỗi `setUp` tự đặt lại field có thể bị ca trước bẻ
(`custom_cho_phep_mua_le`, `price_list_ban_le`...) để các test method trong
cùng class không ăn theo trạng thái của nhau.
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import portal
from miyano_portal.setup.seed_demo import COMPANY, PRICE_LIST, seed_demo

BVBM = "Bệnh viện Bạch Mai"
USER_BVBM = "bvbm@demo.miyano"
PXN = "PXN ABC"
USER_PXN = "pxnabc@demo.miyano"

PL_BAN_LE = "Bán lẻ E6 Test"
RETAIL_CO_GIA = "RTL-E6-001"
RETAIL_THIEU_GIA = "RTL-E6-002"
VT_HDNT = "VT0005"  # Item đã nằm trong HĐNT-BVBM-2026 (seed_demo)


def _rid() -> str:
    return frappe.generate_hash(length=12)


def _kho_mac_dinh():
    return frappe.db.get_value(
        "Warehouse", {"company": COMPANY, "is_group": 0, "warehouse_name": "Stores"}
    )


def _dam_bao_item_ban_le(item_code: str, ten: str, gia) -> None:
    """Item bật `custom_ban_le_portal`, có Item Default (company/kho) để
    `resolve_ban_le_company` suy được company, và (tuỳ `gia`) một dòng
    Item Price trong `PL_BAN_LE`."""
    kho = _kho_mac_dinh()
    if not frappe.db.exists("Item", item_code):
        doc = frappe.get_doc({
            "doctype": "Item",
            "item_code": item_code,
            "item_name": ten,
            "item_group": "Vật tư tiêu hao",
            "stock_uom": "Cái",
            "is_stock_item": 1,
            "description": "Hộp 10 cái",
            "custom_ban_le_portal": 1,
        })
        if kho:
            doc.append("item_defaults", {"company": COMPANY, "default_warehouse": kho})
        doc.insert(ignore_permissions=True)
    else:
        doc = frappe.get_doc("Item", item_code)
        doc.custom_ban_le_portal = 1
        if kho and not any(d.company == COMPANY and d.default_warehouse for d in doc.item_defaults):
            doc.append("item_defaults", {"company": COMPANY, "default_warehouse": kho})
        doc.save(ignore_permissions=True)

    existing = frappe.db.get_value(
        "Item Price", {"item_code": item_code, "price_list": PL_BAN_LE, "selling": 1}, "name"
    )
    if gia is None:
        if existing:
            frappe.delete_doc("Item Price", existing, ignore_permissions=True, force=True)
        return
    if existing:
        frappe.db.set_value("Item Price", existing, "price_list_rate", gia)
    else:
        frappe.get_doc({
            "doctype": "Item Price",
            "item_code": item_code,
            "price_list": PL_BAN_LE,
            "uom": "Cái",
            "selling": 1,
            "price_list_rate": gia,
            "currency": "VND",
        }).insert(ignore_permissions=True)


def _seed_mua_le():
    seed_demo()
    if not frappe.db.exists("Price List", PL_BAN_LE):
        frappe.get_doc({
            "doctype": "Price List", "price_list_name": PL_BAN_LE,
            "selling": 1, "currency": "VND",
        }).insert(ignore_permissions=True)

    frappe.db.set_single_value("Miyano Portal Settings", "price_list_ban_le", PL_BAN_LE)
    frappe.db.set_single_value("Miyano Portal Settings", "hieu_luc_bao_gia_ngay", 7)

    frappe.db.set_value("Customer", BVBM, "custom_cho_phep_mua_le", 1)
    frappe.db.set_value("Customer", PXN, "custom_cho_phep_mua_le", 0)

    _dam_bao_item_ban_le(RETAIL_CO_GIA, "Khẩu trang y tế lẻ", 25000)
    _dam_bao_item_ban_le(RETAIL_THIEU_GIA, "Kit test nhanh lẻ", None)

    # VT_HDNT đã thuộc HĐNT của BVBM (seed_demo) — gắn thêm cờ bán lẻ để
    # dựng đúng tình huống BR-R7: một mặt hàng CÓ MẶT ở cả hai danh mục.
    frappe.db.set_value("Item", VT_HDNT, "custom_ban_le_portal", 1)
    frappe.db.set_value("Item", "HC0009", "custom_ban_le_portal", 0)


class TestCatalogBanLe(FrappeTestCase):
    def setUp(self):
        _seed_mua_le()
        self.addCleanup(frappe.set_user, "Administrator")

    # ---------- TC-E6-01 ----------
    def test_khach_chua_bat_co_bi_403(self):
        frappe.set_user(USER_PXN)
        with self.assertRaises(frappe.PermissionError):
            portal.portal_catalog_ban_le()
        self.assertEqual(frappe.local.response.get("ly_do"), "khong_duoc_mua_le")

    def test_danh_muc_chi_gom_item_ban_le_co_gia_trong_settings(self):
        frappe.set_user(USER_BVBM)
        out = portal.portal_catalog_ban_le()["items"]
        ma = {r["item_code"] for r in out}
        self.assertIn(RETAIL_CO_GIA, ma)
        self.assertIn(RETAIL_THIEU_GIA, ma)
        # HC0009 không bật custom_ban_le_portal — không được lộ ra danh mục lẻ
        # (BR-R6: "không phơi toàn bộ kho hàng Miyano").
        self.assertNotIn("HC0009", ma)

    def test_item_thuoc_hdnt_hieu_luc_duoc_danh_dau_br_r7(self):
        frappe.set_user(USER_BVBM)
        out = portal.portal_catalog_ban_le()["items"]
        theo_ma = {r["item_code"]: r for r in out}
        self.assertIn(VT_HDNT, theo_ma, "VT_HDNT có custom_ban_le_portal=1, phải xuất hiện trong danh mục")
        self.assertTrue(theo_ma[VT_HDNT]["thuoc_hdnt"], "phải đánh dấu thuoc_hdnt=True (BR-R7/NL-10.7)")
        self.assertFalse(theo_ma[RETAIL_CO_GIA]["thuoc_hdnt"], "item lẻ thuần không được đánh dấu nhầm")

    def test_item_thieu_gia_tra_co_gia_false(self):
        frappe.set_user(USER_BVBM)
        out = portal.portal_catalog_ban_le()["items"]
        theo_ma = {r["item_code"]: r for r in out}
        self.assertFalse(theo_ma[RETAIL_THIEU_GIA]["co_gia"])
        self.assertIsNone(theo_ma[RETAIL_THIEU_GIA]["gia_ban_le"])
        self.assertTrue(theo_ma[RETAIL_CO_GIA]["co_gia"])
        self.assertEqual(theo_ma[RETAIL_CO_GIA]["gia_ban_le"], 25000.0)

    # ---------- VĐ-12 ----------
    def test_vd12_chua_cau_hinh_price_list_bao_loi_ro_khong_phai_rong_lang_le(self):
        """`get_single_value` không rơi về default của meta khi Singles chưa
        có dòng (bẫy đã trả giá ở E4) — `price_list_ban_le` không có
        `default` trong JSON nên xoá dòng khỏi Singles PHẢI làm hàm trả
        `None`, và `portal_catalog_ban_le` phải NÉM LỖI RÕ, không lặng lẽ
        trả `items: []` (im lặng trả rỗng sẽ bị đọc nhầm thành "khách không
        bật được mặt hàng nào" thay vì "chưa cấu hình")."""
        frappe.set_user(USER_BVBM)
        frappe.db.set_single_value("Miyano Portal Settings", "price_list_ban_le", "")
        with self.assertRaises(frappe.ValidationError):
            portal.portal_catalog_ban_le()


class TestDatHangBanLe(FrappeTestCase):
    def setUp(self):
        _seed_mua_le()
        frappe.set_user(USER_BVBM)
        self.addCleanup(frappe.set_user, "Administrator")

    # ---------- TC-E6-02 ----------
    def test_dat_le_item_co_gia_khong_tru_han_muc(self):
        bo = portal.portal_contracts()[0]["name"]
        con_lai_truoc, da_dat_truoc = frappe.db.get_value(
            "Blanket Order Item", {"parent": bo, "item_code": VT_HDNT},
            ["qty", "ordered_qty"],
        )

        res = portal.portal_order_place(
            items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 2}]),
            mode="ban_le", request_id=_rid(),
        )
        so = frappe.get_doc("Sales Order", res["sales_order"])
        self.assertEqual(so.docstatus, 0)
        self.assertEqual(so.custom_loai_don, "Mua lẻ")
        self.assertEqual(so.workflow_state, "Chờ xác nhận")
        self.assertEqual(so.items[0].item_code, RETAIL_CO_GIA)
        self.assertEqual(float(so.items[0].rate), 25000.0)
        # BR-R4 — không gắn Blanket Order lên dòng đơn mua lẻ.
        self.assertFalse(so.items[0].blanket_order)
        self.assertFalse(so.items[0].against_blanket_order)
        self.assertFalse(so.custom_hdnt)

        # Hạn mức HĐNT của khách không hề bị đụng tới bởi đơn mua lẻ.
        con_lai_sau, da_dat_sau = frappe.db.get_value(
            "Blanket Order Item", {"parent": bo, "item_code": VT_HDNT},
            ["qty", "ordered_qty"],
        )
        self.assertEqual(con_lai_sau, con_lai_truoc)
        self.assertEqual(da_dat_sau, da_dat_truoc)

    def test_dat_le_thieu_gia_bi_chan(self):
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_place(
                items=json.dumps([{"item_code": RETAIL_THIEU_GIA, "qty": 1}]),
                mode="ban_le", request_id=_rid(),
            )
        loi = frappe.local.response.get("loi")
        self.assertEqual(loi[0]["ly_do"], "thieu_gia")

    # ---------- TC-E6-03 / BR-R7 — chốt an ninh nghiệp vụ ----------
    def test_br_r7_item_thuoc_hdnt_hieu_luc_khong_dat_le_duoc(self):
        rid = _rid()
        with self.assertRaises(frappe.ValidationError) as ctx:
            portal.portal_order_place(
                items=json.dumps([{"item_code": VT_HDNT, "qty": 1}]),
                mode="ban_le", request_id=rid,
            )
        loi = frappe.local.response.get("loi")
        self.assertIsNotNone(loi, "phải có phong bì lỗi máy đọc được (BR-O3)")
        self.assertEqual(loi[0]["ly_do"], "thuoc_hdnt_hieu_luc")
        self.assertIn(VT_HDNT, str(ctx.exception))
        # Không có Sales Order "Mua lẻ" nào được tạo ra cho request_id này —
        # BR-R7 phải chặn TRƯỚC khi ghi, không phải ghi rồi mới xin lỗi.
        self.assertFalse(frappe.db.exists("Sales Order", {"custom_request_id": rid}))

    # ---------- TC-E6-04 — server từ chối "trộn" lẻ vào giỏ không thuộc danh mục lẻ ----------
    def test_item_khong_thuoc_danh_muc_le_bi_chan_du_gui_thang_ma_hang(self):
        """Khách (hoặc client bị sửa) gửi thẳng một mã hàng KHÔNG có
        `custom_ban_le_portal=1` vào giỏ mode=ban_le — catalog không hề hiện
        mã này, nhưng endpoint vẫn phải tự kiểm lại, không tin payload."""
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_place(
                items=json.dumps([{"item_code": "HC0009", "qty": 1}]),
                mode="ban_le", request_id=_rid(),
            )
        loi = frappe.local.response.get("loi")
        self.assertEqual(loi[0]["ly_do"], "khong_thuoc_danh_muc_le")

    def test_hdnt_mode_item_ngoai_hop_dong_van_bi_chan(self):
        """Chiều ngược lại của "trộn dòng": mode=hdnt nhưng gửi một mã hàng
        không nằm trong chính hợp đồng đó — vẫn phải bị chặn (không lọt qua
        vì "nó có trong danh mục lẻ")."""
        bo = portal.portal_contracts()[0]["name"]
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_place(
                bo, json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 1}]),
                mode="hdnt", request_id=_rid(),
            )

    def test_boi_so_ngay_giao_dia_chi_van_kiem_o_che_do_le(self):
        """BR-O11/O13 vẫn áp cho nhánh mua lẻ — dùng lại đúng
        `kiem_boi_so`/`kiem_ngay_giao` của nhánh HĐNT."""
        frappe.db.set_value("Item", RETAIL_CO_GIA, "custom_boi_so_dat", 5)
        try:
            with self.assertRaises(frappe.ValidationError):
                portal.portal_order_place(
                    items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 3}]),
                    mode="ban_le", request_id=_rid(),
                )
            loi = frappe.local.response.get("loi")
            self.assertEqual(loi[0]["ly_do"], "sai_boi_so")
        finally:
            frappe.db.set_value("Item", RETAIL_CO_GIA, "custom_boi_so_dat", 0)

    def test_idempotent_request_id_tra_don_cu(self):
        rid = _rid()
        res1 = portal.portal_order_place(
            items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 1}]),
            mode="ban_le", request_id=rid,
        )
        res2 = portal.portal_order_place(
            items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 1}]),
            mode="ban_le", request_id=rid,
        )
        self.assertEqual(res1["sales_order"], res2["sales_order"])
        self.assertTrue(res2["da_ton_tai"])


def _tao_so_bao_gia(customer, item_code, gia, ngay_lap=None, yeu_cau=None):
    so = frappe.new_doc("Sales Order")
    so.customer = customer
    so.company = COMPANY
    so.transaction_date = ngay_lap or frappe.utils.today()
    so.delivery_date = frappe.utils.add_days(so.transaction_date, 7)
    so.selling_price_list = PRICE_LIST
    so.custom_nguon_don = "Client Portal"
    so.custom_loai_don = "Mua lẻ"
    if yeu_cau:
        so.custom_yeu_cau_goc = yeu_cau
    so.append("items", {
        "item_code": item_code, "qty": 1, "rate": gia,
        "delivery_date": so.delivery_date,
    })
    so.taxes = []
    so.taxes_and_charges = None
    so.insert(ignore_permissions=True)
    # BẪY 4 — không gán workflow_state trước insert().
    frappe.db.set_value(
        "Sales Order", so.name, "workflow_state", "Chờ khách đồng ý",
        update_modified=False,
    )
    so.reload()
    return so


def _tao_yeu_cau_da_bao_gia(customer, nguoi_yeu_cau) -> str:
    """Mô phỏng US-E6.5: sales đã chốt giá cho một Portal Item Request, đưa
    nó về "Đã báo giá" (đi qua đúng cạnh hợp lệ Mới -> Đang tìm nguồn ->
    Đã báo giá của BR-Y1, không nhảy cóc)."""
    doc = frappe.new_doc("Portal Item Request")
    doc.customer = customer
    doc.nguoi_yeu_cau = nguoi_yeu_cau
    doc.trang_thai = "Mới"
    doc.loai = "Báo giá mua lẻ"
    doc.ten_hang = "Kit test nhanh lẻ (yêu cầu báo giá)"
    doc.dvt = "Hộp"
    doc.so_luong_du_kien = 5
    doc.insert(ignore_permissions=True)
    doc.trang_thai = "Đang tìm nguồn"
    doc.save(ignore_permissions=True)
    doc.trang_thai = "Đã báo giá"
    doc.gia_bao = 25000
    doc.save(ignore_permissions=True)
    return doc.name


class TestBaoGiaChoKhachDongY(FrappeTestCase):
    def setUp(self):
        _seed_mua_le()
        self.addCleanup(frappe.set_user, "Administrator")

    # ---------- TC-E6-09 ----------
    def test_dong_y_chuyen_yeu_cau_goc_thanh_da_chuyen_don(self):
        yc = _tao_yeu_cau_da_bao_gia(BVBM, USER_BVBM)
        so = _tao_so_bao_gia(BVBM, RETAIL_CO_GIA, 25000, yeu_cau=yc)

        frappe.set_user(USER_BVBM)
        kq = portal.portal_order_accept(so.name, "dong_y")
        self.assertEqual(kq["trang_thai_moi"], "Chờ Miyano xác nhận")

        frappe.set_user("Administrator")
        self.assertEqual(
            frappe.db.get_value("Portal Item Request", yc, "trang_thai"),
            "Đã chuyển thành đơn",
        )
        self.assertEqual(
            frappe.db.get_value("Portal Item Request", yc, "don_lien_ket"), so.name
        )

    # ---------- TC-E6-11 ----------
    def test_qua_han_hieu_luc_bi_chan_417(self):
        """Lập SO với ngày lập 8 ngày trước — hiệu lực mặc định 7 ngày nên
        đã hết hạn 1 ngày. `portal_order_accept` phải chặn TRƯỚC khi xử lý
        action (kể cả 'dong_y'), không cho khách chốt một báo giá đã nguội."""
        ngay_lap = frappe.utils.add_days(frappe.utils.today(), -8)
        so = _tao_so_bao_gia(BVBM, RETAIL_CO_GIA, 25000, ngay_lap=ngay_lap)

        frappe.set_user(USER_BVBM)
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_accept(so.name, "dong_y")
        self.assertEqual(frappe.local.response.get("ly_do"), "qua_han_hieu_luc")

        frappe.set_user("Administrator")
        self.assertEqual(
            frappe.db.get_value("Sales Order", so.name, "workflow_state"),
            "Chờ khách đồng ý",
            "chưa quá job daily quét thì trạng thái đơn KHÔNG được tự đổi bởi accept",
        )

    def test_dung_han_7_ngay_van_dong_y_duoc(self):
        """Biên: ngày lập = hôm nay, hiệu lực 7 ngày — accept phải ĐI QUA
        được, không lệch một ngày so với job daily."""
        so = _tao_so_bao_gia(BVBM, RETAIL_CO_GIA, 25000)
        frappe.set_user(USER_BVBM)
        kq = portal.portal_order_accept(so.name, "dong_y")
        self.assertEqual(kq["trang_thai_moi"], "Chờ Miyano xác nhận")

    def test_settings_chua_cau_hinh_hieu_luc_roi_ve_mac_dinh_7(self):
        """`hieu_luc_bao_gia_ngay` không có dòng trong Singles (xoá tường
        minh, mô phỏng site chưa từng lưu Settings) — `get_single_value`
        trả `None`, code PHẢI tự rơi về 7, không phải 0 hay lỗi."""
        frappe.db.sql(
            "delete from `tabSingles` where doctype='Miyano Portal Settings' and field='hieu_luc_bao_gia_ngay'"
        )
        # Ngày lập 6 ngày trước: còn hạn nếu mặc định ĐÚNG LÀ 7, đã quá hạn
        # nếu code lỡ rơi về 0 (mọi báo giá coi như hết hạn ngay khi lập).
        ngay_lap = frappe.utils.add_days(frappe.utils.today(), -6)
        so = _tao_so_bao_gia(BVBM, RETAIL_CO_GIA, 25000, ngay_lap=ngay_lap)
        frappe.set_user(USER_BVBM)
        kq = portal.portal_order_accept(so.name, "dong_y")
        self.assertEqual(kq["trang_thai_moi"], "Chờ Miyano xác nhận")

    def test_chap_nhan_trong_order_track_khi_dang_cho_khach(self):
        so = _tao_so_bao_gia(BVBM, RETAIL_CO_GIA, 25000)
        frappe.set_user(USER_BVBM)
        info = portal.portal_order_track(so.name)
        self.assertIsNotNone(info["chap_nhan"])
        self.assertTrue(info["chap_nhan"]["can_dong_y"])
        self.assertEqual(
            info["chap_nhan"]["han_hieu_luc"],
            str(frappe.utils.add_days(so.transaction_date, 7)),
        )


class TestJobBaoGiaHetHan(FrappeTestCase):
    def setUp(self):
        _seed_mua_le()
        self.addCleanup(frappe.set_user, "Administrator")

    def test_quet_dong_don_qua_han_va_cap_nhat_yeu_cau_goc(self):
        from miyano_portal.portal_bao_gia import quet_bao_gia_het_han

        yc = _tao_yeu_cau_da_bao_gia(BVBM, USER_BVBM)
        ngay_lap = frappe.utils.add_days(frappe.utils.today(), -8)
        so = _tao_so_bao_gia(BVBM, RETAIL_CO_GIA, 25000, ngay_lap=ngay_lap, yeu_cau=yc)

        # Một SO KHÁC còn trong hạn — không được job này đụng tới.
        so_con_han = _tao_so_bao_gia(BVBM, RETAIL_CO_GIA, 25000)

        dem = quet_bao_gia_het_han()
        self.assertEqual(dem, 1)

        self.assertEqual(
            frappe.db.get_value("Sales Order", so.name, "workflow_state"),
            "Báo giá hết hạn",
        )
        self.assertEqual(
            frappe.db.get_value("Sales Order", so_con_han.name, "workflow_state"),
            "Chờ khách đồng ý",
            "đơn còn hạn không được job đụng tới",
        )
        self.assertEqual(
            frappe.db.get_value("Portal Item Request", yc, "trang_thai"), "Hết hạn"
        )

    def test_quet_khong_dong_lai_don_da_dong(self):
        """Chạy job hai lần liên tiếp không được đóng lại đơn đã đóng (job
        chạy `daily`, không phải một lần trong đời)."""
        from miyano_portal.portal_bao_gia import quet_bao_gia_het_han

        ngay_lap = frappe.utils.add_days(frappe.utils.today(), -8)
        _tao_so_bao_gia(BVBM, RETAIL_CO_GIA, 25000, ngay_lap=ngay_lap)
        self.assertEqual(quet_bao_gia_het_han(), 1)
        self.assertEqual(quet_bao_gia_het_han(), 0)

    def test_gui_email_hai_phia(self):
        # Site test không cấu hình Email Account mặc định — `frappe.sendmail`
        # ném `OutgoingEmailError` ngay ở bước resolve tài khoản gửi (trước
        # cả khi kịp queue), bất kể `now=False`. `EmailAccount.find_outgoing`
        # tự rơi về một tài khoản "dummy" khi `frappe.flags.mute_emails`
        # được bật (are_emails_muted()) — đây là cơ chế test chuẩn của
        # Frappe, không phải patch riêng của app này. Đặt/thu hồi cờ đúng
        # phạm vi MỘT test: `frappe.flags` là dict toàn tiến trình, KHÔNG
        # theo giao dịch DB nên không tự rollback theo `FrappeTestCase` —
        # rò cờ này sang class test khác chạy sau trong CÙNG tiến trình
        # `run-tests` sẽ khiến các test khác vô tình mute email thật.
        frappe.flags.mute_emails = True
        self.addCleanup(frappe.flags.pop, "mute_emails", None)

        frappe.db.set_value("Customer", BVBM, "account_manager", "sales_user@demo.miyano")
        from miyano_portal.portal_bao_gia import quet_bao_gia_het_han

        ngay_lap = frappe.utils.add_days(frappe.utils.today(), -8)
        so = _tao_so_bao_gia(BVBM, RETAIL_CO_GIA, 25000, ngay_lap=ngay_lap)
        frappe.db.set_value("Sales Order", so.name, "contact_email", USER_BVBM, update_modified=False)

        frappe.db.delete("Email Queue", {"reference_name": so.name})
        quet_bao_gia_het_han()

        nguoi_nhan = set(frappe.get_all(
            "Email Queue Recipient",
            filters={"parent": ["in", frappe.get_all(
                "Email Queue", filters={"reference_name": so.name}, pluck="name",
            )]},
            pluck="recipient",
        ))
        self.assertIn(USER_BVBM, nguoi_nhan, "khách phải nhận email báo hết hạn")
        self.assertIn(
            "sales_user@demo.miyano", nguoi_nhan, "sales phụ trách (Miyano) phải nhận email — 'hai phía'",
        )
