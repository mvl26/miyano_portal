"""Thông báo Miyano/hệ thống -> khách hàng (`portal_thong_bao_khach.py`) —
brief 2026-08-15, trang thông báo, Phần 2 (điểm giòn định tuyến) + Phần 3
(resolve tài khoản cổng cho `delivery_hook`)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.portal_thong_bao_khach import (
    _portal_users_cua_khach,
    bao_da_nhap_hang,
    kiem_tra_dinh_tuyen_thong_bao_khach,
)
from miyano_portal.setup.seed_demo import seed_demo

BVBM = "Bệnh viện Bạch Mai"
USER_BVBM = "bvbm@demo.miyano"


class TestPortalUsersCuaKhach(FrappeTestCase):
    def setUp(self):
        seed_demo()

    def test_resolve_dung_tai_khoan_cong(self):
        self.assertEqual(_portal_users_cua_khach(BVBM), [USER_BVBM])

    def test_khach_khong_ton_tai_tra_rong(self):
        self.assertEqual(_portal_users_cua_khach("Khách không tồn tại XYZ"), [])

    def test_user_bi_khoa_khong_duoc_tinh(self):
        frappe.db.set_value("User", USER_BVBM, "enabled", 0)
        self.addCleanup(frappe.db.set_value, "User", USER_BVBM, "enabled", 1)
        self.assertEqual(_portal_users_cua_khach(BVBM), [])


class TestBaoDaNhapHang(FrappeTestCase):
    def setUp(self):
        seed_demo()
        frappe.db.delete("Notification Log", {"for_user": USER_BVBM})
        self.addCleanup(
            frappe.db.delete, "Error Log", {"method": ["like", "Portal - Không tra được tài khoản cổng:%"]}
        )

    def test_gui_dung_tai_khoan_cong_va_dung_link(self):
        dem = bao_da_nhap_hang(BVBM, "PHIEU-TEST-001", "DN-TEST-001")
        self.assertEqual(dem, 1)
        log = frappe.get_all(
            "Notification Log",
            filters={"for_user": USER_BVBM, "document_type": "Customer Stock Receipt", "document_name": "PHIEU-TEST-001"},
            fields=["subject", "type", "read"],
        )
        self.assertEqual(len(log), 1)
        self.assertIn("PHIEU-TEST-001", log[0].subject)
        self.assertEqual(log[0].type, "Alert")
        self.assertEqual(log[0].read, 0)

    def test_chong_trung_theo_phieu(self):
        bao_da_nhap_hang(BVBM, "PHIEU-TEST-002", "DN-TEST-002")
        dem_lan_hai = bao_da_nhap_hang(BVBM, "PHIEU-TEST-002", "DN-TEST-002")
        self.assertEqual(dem_lan_hai, 0)
        self.assertEqual(
            frappe.db.count(
                "Notification Log",
                {"for_user": USER_BVBM, "document_type": "Customer Stock Receipt", "document_name": "PHIEU-TEST-002"},
            ),
            1,
        )

    def test_khach_khong_co_tai_khoan_cong_khong_nem_loi_va_co_ghi_log(self):
        khach = "Khách không có tài khoản cổng ABC"
        if not frappe.db.exists("Customer", khach):
            frappe.get_doc({
                "doctype": "Customer", "customer_name": khach,
                "customer_type": "Company", "customer_group": "All Customer Groups",
                "territory": "All Territories",
            }).insert(ignore_permissions=True)

        dem = bao_da_nhap_hang(khach, "PHIEU-TEST-003", "DN-TEST-003")
        self.assertEqual(dem, 0, "Không có ai để gửi -> 0, KHÔNG được ném lỗi")

        log = frappe.get_all(
            "Error Log",
            filters={"reference_doctype": "Customer Stock Receipt", "reference_name": "PHIEU-TEST-003"},
            fields=["method"],
        )
        self.assertEqual(len(log), 1, "Điểm giòn phải để lại đúng một dòng Error Log, không im lặng")
        self.assertIn("Portal - Không tra được tài khoản cổng", log[0].method)

        # Gọi lại lần nữa -- KHÔNG được nhân đôi dòng log.
        bao_da_nhap_hang(khach, "PHIEU-TEST-003", "DN-TEST-003")
        log2 = frappe.get_all(
            "Error Log",
            filters={"reference_doctype": "Customer Stock Receipt", "reference_name": "PHIEU-TEST-003"},
        )
        self.assertEqual(len(log2), 1, "Log điểm giòn phải chống trùng, không lặp mỗi lần gọi lại")


class TestKiemTraDinhTuyenThongBaoKhach(FrappeTestCase):
    """Phần 2/điểm giòn — chứng từ có `contact_email` KHÔNG khớp tài khoản
    cổng của khách phải để lại một dòng Error Log DUY NHẤT (không sửa được
    đường định tuyến của Frappe, chỉ phát hiện)."""

    def setUp(self):
        seed_demo()
        self.addCleanup(
            frappe.db.delete, "Error Log", {"method": ["like", "Portal - Điểm giòn định tuyến thông báo:%"]}
        )

    def _so_gia(self, contact_email):
        return frappe._dict(
            doctype="Sales Order", name="SAL-ORD-GIA-DINH",
            customer=BVBM, contact_email=contact_email,
        )

    def test_contact_email_khop_khong_ghi_log(self):
        kiem_tra_dinh_tuyen_thong_bao_khach(self._so_gia(USER_BVBM))
        self.assertFalse(frappe.db.exists(
            "Error Log", {"reference_doctype": "Sales Order", "reference_name": "SAL-ORD-GIA-DINH"}
        ))

    def test_contact_email_lech_ghi_dung_mot_dong_log(self):
        doc = self._so_gia("mot-email-khac@vidu.com")
        kiem_tra_dinh_tuyen_thong_bao_khach(doc)
        log = frappe.get_all(
            "Error Log",
            filters={"reference_doctype": "Sales Order", "reference_name": "SAL-ORD-GIA-DINH"},
            fields=["method"],
        )
        self.assertEqual(len(log), 1)
        self.assertIn("Điểm giòn định tuyến thông báo", log[0].method)

        # Gọi lại (on_update chạy trên MỌI lần lưu) -- không được nhân đôi.
        kiem_tra_dinh_tuyen_thong_bao_khach(doc)
        log2 = frappe.get_all(
            "Error Log",
            filters={"reference_doctype": "Sales Order", "reference_name": "SAL-ORD-GIA-DINH"},
        )
        self.assertEqual(len(log2), 1, "on_update chạy lại nhiều lần không được nhân đôi log")

    def test_khach_khong_co_tai_khoan_cong_khong_ghi_log(self):
        """Không phải điểm giòn của TÍNH NĂNG CỔNG — khách này chưa từng lên
        cổng, contact_email lệch không phải một lỗ hổng cần báo."""
        khach = "Khách chưa lên cổng DEF"
        if not frappe.db.exists("Customer", khach):
            frappe.get_doc({
                "doctype": "Customer", "customer_name": khach,
                "customer_type": "Company", "customer_group": "All Customer Groups",
                "territory": "All Territories",
            }).insert(ignore_permissions=True)
        doc = frappe._dict(
            doctype="Sales Order", name="SAL-ORD-GIA-DINH-2",
            customer=khach, contact_email="ai-do@vidu.com",
        )
        kiem_tra_dinh_tuyen_thong_bao_khach(doc)
        self.assertFalse(frappe.db.exists(
            "Error Log", {"reference_doctype": "Sales Order", "reference_name": "SAL-ORD-GIA-DINH-2"}
        ))

    def test_khong_nem_loi_khi_doc_thieu_field(self):
        """Hook `on_update` không bao giờ được ném lỗi — kể cả với input kỳ dị."""
        kiem_tra_dinh_tuyen_thong_bao_khach(frappe._dict(doctype="Sales Order", name="X"))
        kiem_tra_dinh_tuyen_thong_bao_khach(frappe._dict())
