"""Brief 2026-08-15 — phân trang toàn cổng.

Hai nhóm test theo đúng hai rủi ro brief nêu là nặng nhất, không lỗi nào
tự báo ra nếu hỏng:

1. Ba endpoint KIÊM HAI VAI (`kho_vat_tu_list`/`kho_ncc_list`/
   `kho_khoa_phong_list`) — không truyền `limit` phải trả ĐỦ danh sách (nuôi
   dropdown NhatKy.vue/BaoCaoNXT.vue); truyền `limit` mới cắt trang.
2. Xuất Excel (`kho_bao_cao_excel`) phải LUÔN xuất toàn bộ, không theo
   trang JSON đang xem.

Cộng thêm: `tong`/hình dạng dict của các endpoint đổi hình dạng
(`portal_order_history`, `portal_invoices`, `kho_phieu_list`), và tiebreak
thứ tự tất định.
"""

import io

import frappe
from frappe.tests.utils import FrappeTestCase
from openpyxl import load_workbook

from miyano_portal.api import kho as kho_api
from miyano_portal.api import portal
from miyano_portal.setup.seed_kho_demo import seed_kho_demo

BM_USER = "bvbm@demo.miyano"

SO_LUONG_DU_NHIEU = 55  # > mọi kích thước trang (10/20/50) đang có trong UI


class TestKhoVatTuListKiemHaiVai(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()
        self.K = self.kho["kho_bm"]
        frappe.db.delete("Customer Warehouse Item", {"kho": self.K, "ma_vat_tu": ["like", "PT-VT-%"]})
        for i in range(SO_LUONG_DU_NHIEU):
            frappe.get_doc({
                "doctype": "Customer Warehouse Item",
                "kho": self.K,
                "ma_vat_tu": f"PT-VT-{i:03d}",
                "ten_vat_tu": f"Vật tư phân trang {i:03d}",
                "dvt": "Cái",
            }).insert(ignore_permissions=True)

    def test_khong_truyen_limit_tra_du_danh_sach_cho_dropdown(self):
        """NhatKy.vue/BaoCaoNXT.vue gọi kho_vat_tu_list KHÔNG truyền limit
        để đổ dropdown lọc — endpoint phải trả BARE LIST đủ mọi vật tư, dù
        có > 50 dòng. Đây chính là bộ lọc brief cảnh báo sẽ hỏng ÂM THẦM
        nếu ai đó phân trang vô điều kiện."""
        frappe.set_user(BM_USER)
        try:
            rows = kho_api.kho_vat_tu_list()
        finally:
            frappe.set_user("Administrator")
        self.assertIsInstance(rows, list, "không truyền limit phải trả list trần, không phải dict")
        ma_list = {r["ma_vat_tu"] for r in rows}
        self.assertGreaterEqual(
            len(rows), SO_LUONG_DU_NHIEU,
            "dropdown phải thấy ĐỦ vật tư, không bị cắt còn một trang",
        )
        for i in range(SO_LUONG_DU_NHIEU):
            self.assertIn(f"PT-VT-{i:03d}", ma_list)

    def test_truyen_limit_tra_dict_va_cat_dung_trang(self):
        frappe.set_user(BM_USER)
        try:
            trang_1 = kho_api.kho_vat_tu_list(limit=10, start=0)
            trang_2 = kho_api.kho_vat_tu_list(limit=10, start=10)
        finally:
            frappe.set_user("Administrator")
        self.assertIsInstance(trang_1, dict, "có limit phải trả dict {rows, tong}")
        self.assertEqual(len(trang_1["rows"]), 10)
        self.assertGreaterEqual(trang_1["tong"], SO_LUONG_DU_NHIEU)
        self.assertEqual(len(trang_2["rows"]), 10)
        # Hai trang không được trùng dòng nào — order_by có tiebreak `name`.
        ten_1 = {r["name"] for r in trang_1["rows"]}
        ten_2 = {r["name"] for r in trang_2["rows"]}
        self.assertFalse(ten_1 & ten_2, "hai trang liền kề không được lẫn dòng")


class TestKhoNccListKiemHaiVai(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()
        self.K = self.kho["kho_bm"]
        frappe.db.delete("Customer Supplier", {"kho": self.K, "ten_ncc": ["like", "NCC phân trang%"]})
        for i in range(SO_LUONG_DU_NHIEU):
            frappe.get_doc({
                "doctype": "Customer Supplier",
                "kho": self.K,
                "ten_ncc": f"NCC phân trang {i:03d}",
            }).insert(ignore_permissions=True)

    def test_khong_truyen_limit_tra_du_danh_sach_cho_dropdown(self):
        frappe.set_user(BM_USER)
        try:
            rows = kho_api.kho_ncc_list()
        finally:
            frappe.set_user("Administrator")
        self.assertIsInstance(rows, list)
        self.assertGreaterEqual(len(rows), SO_LUONG_DU_NHIEU)

    def test_truyen_limit_tra_dict_va_cat_dung_trang(self):
        frappe.set_user(BM_USER)
        try:
            ket_qua = kho_api.kho_ncc_list(limit=20, start=0)
        finally:
            frappe.set_user("Administrator")
        self.assertIsInstance(ket_qua, dict)
        self.assertEqual(len(ket_qua["rows"]), 20)
        self.assertGreaterEqual(ket_qua["tong"], SO_LUONG_DU_NHIEU)


class TestKhoKhoaPhongListKiemHaiVai(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()
        self.K = self.kho["kho_bm"]
        frappe.db.delete("Customer Department", {"kho": self.K, "ten_khoa_phong": ["like", "Khoa phân trang%"]})
        for i in range(SO_LUONG_DU_NHIEU):
            frappe.get_doc({
                "doctype": "Customer Department",
                "kho": self.K,
                "ten_khoa_phong": f"Khoa phân trang {i:03d}",
            }).insert(ignore_permissions=True)

    def test_khong_truyen_limit_tra_du_danh_sach_cho_dropdown(self):
        frappe.set_user(BM_USER)
        try:
            rows = kho_api.kho_khoa_phong_list()
        finally:
            frappe.set_user("Administrator")
        self.assertIsInstance(rows, list)
        self.assertGreaterEqual(len(rows), SO_LUONG_DU_NHIEU)

    def test_truyen_limit_tra_dict_va_cat_dung_trang(self):
        frappe.set_user(BM_USER)
        try:
            ket_qua = kho_api.kho_khoa_phong_list(limit=50, start=0)
        finally:
            frappe.set_user("Administrator")
        self.assertIsInstance(ket_qua, dict)
        self.assertEqual(len(ket_qua["rows"]), 50)
        self.assertGreaterEqual(ket_qua["tong"], SO_LUONG_DU_NHIEU)


class TestKhoTonPhanTrang(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()
        self.K = self.kho["kho_bm"]
        self.VT = self.kho["vt_bm"]
        frappe.db.delete("Customer Stock Ledger Entry", {"kho": self.K})
        frappe.db.delete("Customer Stock Lot Balance", {"kho": self.K})

    def test_khong_truyen_limit_van_tra_list_tran(self):
        frappe.set_user(BM_USER)
        try:
            rows = kho_api.kho_ton()
        finally:
            frappe.set_user("Administrator")
        self.assertIsInstance(rows, list)


class TestBaoCaoNxtPhanTrang(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()
        self.K = self.kho["kho_bm"]
        frappe.db.delete("Customer Stock Ledger Entry", {"kho": self.K})
        frappe.db.delete("Customer Stock Lot Balance", {"kho": self.K})
        frappe.db.delete("Customer Warehouse Item", {"kho": self.K, "ma_vat_tu": ["like", "PT-NXT-%"]})
        today = frappe.utils.getdate(frappe.utils.today())
        self.tu_ngay = frappe.utils.add_days(today, -10)
        self.den_ngay = today
        for i in range(15):
            vt = frappe.get_doc({
                "doctype": "Customer Warehouse Item",
                "kho": self.K, "ma_vat_tu": f"PT-NXT-{i:03d}",
                "ten_vat_tu": f"Vật tư NXT phân trang {i:03d}", "dvt": "Cái",
            }).insert(ignore_permissions=True)
            doc = frappe.get_doc({
                "doctype": "Customer Stock Receipt",
                "kho": self.K, "ngay": today, "loai_nhap": "Nhập khác",
                "nguoi_giao": "Test",
                "items": [{
                    "vat_tu": vt.name, "so_lo": f"LO-{i}", "so_luong": 10, "don_gia": 1000,
                }],
            })
            doc.insert(ignore_permissions=True)
            doc.submit()

    def test_muc_vat_tu_phan_trang_dung(self):
        frappe.set_user(BM_USER)
        try:
            ket_qua = kho_api.kho_bao_cao_nxt(
                tu_ngay=self.tu_ngay, den_ngay=self.den_ngay, limit=5, start=0,
            )
        finally:
            frappe.set_user("Administrator")
        self.assertEqual(ket_qua["muc"], "vat_tu")
        self.assertEqual(len(ket_qua["rows"]), 5)
        self.assertGreaterEqual(ket_qua["tong"], 15)

    def test_muc_lo_khong_bi_anh_huong_boi_limit(self):
        """Màn chi tiết (bung MỘT vật tư xuống lô) KHÔNG phân trang — theo
        giả định đã chốt với chủ dự án. `limit` bị bỏ qua khi có `vat_tu`."""
        vat_tu_name = frappe.db.get_value(
            "Customer Warehouse Item", {"kho": self.K, "ma_vat_tu": "PT-NXT-000"}, "name"
        )
        frappe.set_user(BM_USER)
        try:
            ket_qua = kho_api.kho_bao_cao_nxt(
                tu_ngay=self.tu_ngay, den_ngay=self.den_ngay, vat_tu=vat_tu_name, limit=1,
            )
        finally:
            frappe.set_user("Administrator")
        self.assertEqual(ket_qua["muc"], "lo")
        self.assertNotIn("tong", ket_qua, "mức lô là chi tiết, không có khái niệm tong/trang")


class TestBaoCaoExcelLuonXuatToanBo(FrappeTestCase):
    """DoD brief 2026-08-15: xuất Excel/PDF của BaoCaoNXT LUÔN xuất TOÀN
    BỘ, không theo trang JSON đang xem."""

    def setUp(self):
        self.kho = seed_kho_demo()
        self.K = self.kho["kho_bm"]
        frappe.db.delete("Customer Stock Ledger Entry", {"kho": self.K})
        frappe.db.delete("Customer Stock Lot Balance", {"kho": self.K})
        frappe.db.delete("Customer Warehouse Item", {"kho": self.K, "ma_vat_tu": ["like", "PT-XLS-%"]})
        today = frappe.utils.getdate(frappe.utils.today())
        self.tu_ngay = frappe.utils.add_days(today, -10)
        self.den_ngay = today
        # 12 vật tư có phát sinh — nhiều hơn kích thước trang nhỏ (10) test
        # sẽ dùng cho endpoint JSON, để phân biệt được "trang" với "toàn bộ".
        for i in range(12):
            vt = frappe.get_doc({
                "doctype": "Customer Warehouse Item",
                "kho": self.K, "ma_vat_tu": f"PT-XLS-{i:03d}",
                "ten_vat_tu": f"Vật tư xuất Excel {i:03d}", "dvt": "Cái",
            }).insert(ignore_permissions=True)
            doc = frappe.get_doc({
                "doctype": "Customer Stock Receipt",
                "kho": self.K, "ngay": today, "loai_nhap": "Nhập khác",
                "nguoi_giao": "Test",
                "items": [{
                    "vat_tu": vt.name, "so_lo": f"LO-{i}", "so_luong": 10, "don_gia": 1000,
                }],
            })
            doc.insert(ignore_permissions=True)
            doc.submit()

    def test_export_khong_bi_gioi_han_boi_page_size_cua_man_json(self):
        frappe.set_user(BM_USER)
        try:
            # Màn hình đang xem TRANG NHỎ (5 dòng/trang) — endpoint JSON
            # phải trả đúng 5, nhưng nút xuất Excel không được biết/không
            # được dùng con số này.
            trang_json = kho_api.kho_bao_cao_nxt(
                tu_ngay=self.tu_ngay, den_ngay=self.den_ngay, limit=5, start=0,
            )
            self.assertEqual(len(trang_json["rows"]), 5)
            self.assertGreaterEqual(trang_json["tong"], 12)

            kho_api.kho_bao_cao_excel(
                loai="nxt", tu_ngay=str(self.tu_ngay), den_ngay=str(self.den_ngay),
            )
            content = frappe.local.response.filecontent
        finally:
            frappe.local.response.clear()
            frappe.set_user("Administrator")

        wb = load_workbook(io.BytesIO(content))
        ws = wb.active
        so_dong_du_lieu = ws.max_row - 1  # trừ dòng tiêu đề
        self.assertGreaterEqual(
            so_dong_du_lieu, 12,
            "xuất Excel phải có ĐỦ toàn bộ 12 vật tư, không chỉ 5 dòng của trang JSON",
        )
        self.assertEqual(so_dong_du_lieu, trang_json["tong"], "xuất Excel phải khớp đúng tong, không phải page size")


class TestPortalOrderHistoryVaInvoicesHinhDangMoi(FrappeTestCase):
    def test_portal_order_history_tra_dict_co_tong(self):
        frappe.set_user(BM_USER)
        try:
            ket_qua = portal.portal_order_history()
        finally:
            frappe.set_user("Administrator")
        self.assertIn("rows", ket_qua)
        self.assertIn("tong", ket_qua)
        self.assertIsInstance(ket_qua["rows"], list)
        self.assertGreaterEqual(ket_qua["tong"], len(ket_qua["rows"]))

    def test_portal_invoices_tra_dict_co_tong_va_thong_ke_cong_no(self):
        frappe.set_user(BM_USER)
        try:
            ket_qua = portal.portal_invoices()
        finally:
            frappe.set_user("Administrator")
        for key in ("rows", "tong", "qua_han_thanh_toan", "sap_den_han_so_luong"):
            self.assertIn(key, ket_qua)


class TestKhoPhieuListHinhDangMoi(FrappeTestCase):
    def test_luon_tra_dict(self):
        seed_kho_demo()
        frappe.set_user(BM_USER)
        try:
            ket_qua = kho_api.kho_phieu_list("nhap")
        finally:
            frappe.set_user("Administrator")
        self.assertIn("rows", ket_qua)
        self.assertIn("tong", ket_qua)
