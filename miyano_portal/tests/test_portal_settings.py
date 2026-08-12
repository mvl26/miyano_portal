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


class TestOverDeliveryAllowance(FrappeTestCase):
    """QĐ-2 / BR-O10: không cho giao vượt số đặt.

    Kiểm CẤU HÌNH chứ không kiểm hành vi submit Delivery Note — hành vi đó
    thuộc E3 (TC-E3-01) và cần dựng cả Sales Order lẫn Delivery Note. Ở đây
    chỉ chốt rằng tham số ERPNext dùng để chặn đang ở đúng giá trị, và không
    mặt hàng nào mở ngoại lệ.

    Hai test này PASS ngay từ đầu: giá trị mặc định của site vốn đã đúng.
    Chúng là chốt HỒI QUY — biến "tình cờ đúng" thành thứ không ai lỡ tay đổi
    mà không bị phát hiện — chứ không phải bằng chứng có bug. Đừng đi tìm một
    bước RED không tồn tại.

    Trường nằm ở `Stock Settings`, KHÔNG phải `Selling Settings` như PRD E3
    ghi. `Item` cũng có trường cùng tên, ghi đè theo từng mặt hàng.
    """

    def test_stock_settings_allowance_bang_0(self):
        self.assertEqual(
            frappe.db.get_single_value(
                "Stock Settings", "over_delivery_receipt_allowance"
            )
            or 0,
            0,
        )

    def test_khong_item_nao_ghi_de_allowance(self):
        ngoai_le = frappe.get_all(
            "Item",
            filters={"over_delivery_receipt_allowance": [">", 0]},
            pluck="name",
            limit=5,
        )
        self.assertEqual(
            ngoai_le, [], f"Các mặt hàng sau mở ngoại lệ giao vượt: {ngoai_le}"
        )
