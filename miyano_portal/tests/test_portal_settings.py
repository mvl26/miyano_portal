"""P0 — `Miyano Portal Settings` và cấu hình over-delivery.

`00_INDEX.md` xếp cả hai là việc chung P0, làm trước mọi epic: E2 đọc
`nguong_duyet_2_tang` + `sla_xu_ly_don_gio`, E4 đọc
`nguong_cham_luan_chuyen_ngay`, E5 đọc `so_ngay_adu` +
`so_ngay_du_lieu_toi_thieu`, E6 đọc `price_list_ban_le` +
`hieu_luc_bao_gia_ngay` + `sla_yeu_cau_gio`.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

TEN = "Miyano Portal Settings"


class TestMiyanoPortalSettings(FrappeTestCase):
    def test_doctype_ton_tai_va_la_single(self):
        self.assertTrue(frappe.db.exists("DocType", TEN))
        self.assertEqual(frappe.get_meta(TEN).issingle, 1)

    def test_du_tam_truong_dung_kieu(self):
        meta = frappe.get_meta(TEN)
        mong_doi = {
            "nguong_duyet_2_tang": "Currency",
            "sla_xu_ly_don_gio": "Int",
            "price_list_ban_le": "Link",
            "hieu_luc_bao_gia_ngay": "Int",
            "sla_yeu_cau_gio": "Int",
            "so_ngay_adu": "Int",
            "so_ngay_du_lieu_toi_thieu": "Int",
            "nguong_cham_luan_chuyen_ngay": "Int",
        }
        for fieldname, fieldtype in mong_doi.items():
            with self.subTest(fieldname=fieldname):
                f = meta.get_field(fieldname)
                self.assertIsNotNone(f, f"thiếu trường {fieldname}")
                self.assertEqual(f.fieldtype, fieldtype)

    def test_gia_tri_mac_dinh_dung_dataDict(self):
        """Mặc định lấy nguyên từ `20_DataDict.md` §1.3. `nguong_duyet_2_tang`
        CỐ Ý để trống = một tầng duyệt (VĐ-8 chưa chốt số)."""
        meta = frappe.get_meta(TEN)
        self.assertIn(meta.get_field("nguong_duyet_2_tang").default, (None, ""))
        for fieldname, mac_dinh in (
            ("sla_xu_ly_don_gio", "8"),
            ("hieu_luc_bao_gia_ngay", "7"),
            ("sla_yeu_cau_gio", "48"),
            ("so_ngay_adu", "90"),
            ("so_ngay_du_lieu_toi_thieu", "30"),
            ("nguong_cham_luan_chuyen_ngay", "90"),
        ):
            with self.subTest(fieldname=fieldname):
                self.assertEqual(meta.get_field(fieldname).default, mac_dinh)

    def test_chi_system_manager_duoc_sua(self):
        """BA §8: Settings chỉ `System Manager` sửa; role `Customer` không có
        DocPerm nào — cùng khuôn với tám doctype kho."""
        roles = {p.role for p in frappe.get_meta(TEN).permissions}
        self.assertEqual(roles, {"System Manager"})
