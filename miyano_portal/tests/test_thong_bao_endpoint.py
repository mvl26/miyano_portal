"""Endpoint trang Thông báo — brief 2026-08-15, Phần 4.

Test bắt buộc (brief):
- Khách A không thấy thông báo của khách B.
- Bấm thông báo trỏ tới chứng từ của khách khác -> chặn (link/None).
- Badge chưa đọc giảm đúng sau khi đọc.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api.portal import portal_thong_bao_doc, portal_thong_bao_list
from miyano_portal.setup.seed_demo import seed_demo

USER_BVBM = "bvbm@demo.miyano"
USER_PXN = "pxnabc@demo.miyano"


def _tao_log(for_user, subject, document_type=None, document_name=None, read=0):
    doc = frappe.get_doc({
        "doctype": "Notification Log",
        "subject": subject,
        "for_user": for_user,
        "type": "Alert",
        "document_type": document_type,
        "document_name": document_name,
        "read": read,
    })
    doc.insert(ignore_permissions=True)
    return doc.name


class TestPortalThongBaoList(FrappeTestCase):
    def setUp(self):
        seed_demo()
        frappe.db.delete("Notification Log", {"for_user": ["in", [USER_BVBM, USER_PXN]]})
        self.addCleanup(frappe.set_user, "Administrator")

    def test_chi_thay_thong_bao_cua_chinh_minh(self):
        _tao_log(USER_BVBM, "Thông báo của Bạch Mai")
        _tao_log(USER_PXN, "Thông báo của PXN")

        frappe.set_user(USER_BVBM)
        res = portal_thong_bao_list()
        subjects = [i["subject"] for i in res["items"]]
        self.assertIn("Thông báo của Bạch Mai", subjects)
        self.assertNotIn("Thông báo của PXN", subjects, "Không được thấy thông báo của khách khác")

    def test_chua_doc_dem_dung(self):
        _tao_log(USER_BVBM, "Chưa đọc 1", read=0)
        _tao_log(USER_BVBM, "Chưa đọc 2", read=0)
        _tao_log(USER_BVBM, "Đã đọc rồi", read=1)

        frappe.set_user(USER_BVBM)
        res = portal_thong_bao_list()
        self.assertEqual(res["chua_doc"], 2)

    def test_link_sales_order_cua_chinh_minh(self):
        so = frappe.new_doc("Sales Order")
        so.customer = "Bệnh viện Bạch Mai"
        so.company = "Miyano Việt Nam"
        so.transaction_date = frappe.utils.today()
        so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 2)
        so.append("items", {
            "item_code": "VT0005", "qty": 1, "rate": 1200,
            "delivery_date": frappe.utils.add_days(frappe.utils.today(), 2),
        })
        so.insert(ignore_permissions=True)

        _tao_log(USER_BVBM, "Đơn của bạn", "Sales Order", so.name)
        frappe.set_user(USER_BVBM)
        res = portal_thong_bao_list()
        row = next(i for i in res["items"] if i["subject"] == "Đơn của bạn")
        # Task 11 (QĐ-G11) — đường chính tắc của màn chi tiết đơn chuyển
        # sang dưới `/yeu-cau`. `/orders/<name>` vẫn CHUYỂN HƯỚNG đúng cho
        # thông báo cũ đã gửi đi (router.js), nhưng thông báo MỚI phải mang
        # đường mới.
        self.assertEqual(row["link"], f"/yeu-cau/don/{so.name}")

    def test_link_chung_tu_cua_khach_khac_bi_chan(self):
        """Notification Log CỦA MÌNH (for_user đúng) nhưng document_name trỏ
        tới chứng từ của khách khác -- link phải None, không được lộ."""
        so_khach_khac = frappe.new_doc("Sales Order")
        so_khach_khac.customer = "PXN ABC"
        so_khach_khac.company = "Miyano Việt Nam"
        so_khach_khac.transaction_date = frappe.utils.today()
        so_khach_khac.delivery_date = frappe.utils.add_days(frappe.utils.today(), 2)
        so_khach_khac.append("items", {
            "item_code": "VT0005", "qty": 1, "rate": 1200,
            "delivery_date": frappe.utils.add_days(frappe.utils.today(), 2),
        })
        so_khach_khac.insert(ignore_permissions=True)

        _tao_log(USER_BVBM, "Định tuyến sai", "Sales Order", so_khach_khac.name)
        frappe.set_user(USER_BVBM)
        res = portal_thong_bao_list()
        row = next(i for i in res["items"] if i["subject"] == "Định tuyến sai")
        self.assertIsNone(row["link"], "Chứng từ của khách khác phải bị chặn, không trả link")

    def test_link_thong_bao_phieu_de_xuat_tro_toi_man_chi_tiet(self):
        """Lỗ có TỪ Task 8 (§5.8): `bao_de_xuat_gui_duyet` gửi cho quản lý
        "Khoa vừa gửi đề xuất mua X chờ bạn duyệt" — và trang Thông báo ẩn
        nút đi tới chứng từ, vì `_lien_ket_thong_bao` không biết doctype này.
        Quản lý phải tự mở danh sách và tìm lại đúng phiếu bằng mắt.

        Vá được từ 03/09/2026 vì chi tiết một yêu cầu nay có MỘT màn chính
        tắc, không còn phải chọn giữa hai đường."""
        phieu = frappe.get_doc({
            "doctype": "Portal De Xuat Mua",
            "customer": "Bệnh viện Bạch Mai", "khoa_phong": None,
            "items": [{"item_code": "VT0005", "so_luong_de_xuat": 1}],
        }).insert(ignore_permissions=True)
        _tao_log(USER_BVBM, "Phiếu chờ duyệt", "Portal De Xuat Mua", phieu.name)
        frappe.set_user(USER_BVBM)
        res = portal_thong_bao_list()
        row = next(i for i in res["items"] if i["subject"] == "Phiếu chờ duyệt")
        self.assertEqual(row["link"], f"/yeu-cau/phieu/{phieu.name}")

    def test_link_phieu_cua_khach_khac_bi_chan(self):
        """VẾ ÂM — cùng lớp kiểm thứ hai mà mọi nhánh khác của
        `_lien_ket_thong_bao` đều có: `for_user` đúng KHÔNG phải bằng chứng
        người đó đọc được chứng từ đang trỏ tới."""
        phieu = frappe.get_doc({
            "doctype": "Portal De Xuat Mua",
            "customer": "PXN ABC",
            "items": [{"item_code": "VT0005", "so_luong_de_xuat": 1}],
        }).insert(ignore_permissions=True)
        _tao_log(USER_BVBM, "Phiếu khách khác", "Portal De Xuat Mua", phieu.name)
        frappe.set_user(USER_BVBM)
        res = portal_thong_bao_list()
        row = next(i for i in res["items"] if i["subject"] == "Phiếu khách khác")
        self.assertIsNone(row["link"])


class TestPortalThongBaoDoc(FrappeTestCase):
    def setUp(self):
        seed_demo()
        frappe.db.delete("Notification Log", {"for_user": ["in", [USER_BVBM, USER_PXN]]})
        self.addCleanup(frappe.set_user, "Administrator")

    def test_danh_dau_da_doc_va_giam_badge(self):
        name1 = _tao_log(USER_BVBM, "Chưa đọc A", read=0)
        _tao_log(USER_BVBM, "Chưa đọc B", read=0)

        frappe.set_user(USER_BVBM)
        truoc = portal_thong_bao_list()
        self.assertEqual(truoc["chua_doc"], 2)

        portal_thong_bao_doc(name1)
        self.assertEqual(frappe.db.get_value("Notification Log", name1, "read"), 1)

        sau = portal_thong_bao_list()
        self.assertEqual(sau["chua_doc"], 1, "Badge chưa đọc phải giảm đúng sau khi đọc")

    def test_khong_doc_duoc_thong_bao_cua_nguoi_khac(self):
        name_pxn = _tao_log(USER_PXN, "Của PXN", read=0)
        frappe.set_user(USER_BVBM)
        with self.assertRaises(frappe.PermissionError):
            portal_thong_bao_doc(name_pxn)
        # Và KHÔNG được vô tình đánh dấu đã đọc thông báo của người khác.
        self.assertEqual(frappe.db.get_value("Notification Log", name_pxn, "read"), 0)

    def test_link_bi_chan_khi_tro_toi_chung_tu_khach_khac(self):
        so_khach_khac = frappe.new_doc("Sales Order")
        so_khach_khac.customer = "PXN ABC"
        so_khach_khac.company = "Miyano Việt Nam"
        so_khach_khac.transaction_date = frappe.utils.today()
        so_khach_khac.delivery_date = frappe.utils.add_days(frappe.utils.today(), 2)
        so_khach_khac.append("items", {
            "item_code": "VT0005", "qty": 1, "rate": 1200,
            "delivery_date": frappe.utils.add_days(frappe.utils.today(), 2),
        })
        so_khach_khac.insert(ignore_permissions=True)
        name = _tao_log(USER_BVBM, "Định tuyến sai 2", "Sales Order", so_khach_khac.name)

        frappe.set_user(USER_BVBM)
        res = portal_thong_bao_doc(name)
        self.assertIsNone(res["link"], "Bấm thông báo trỏ tới chứng từ của khách khác phải bị chặn")
        # Vẫn được đánh dấu đã đọc (đây là thông báo CỦA MÌNH) -- chỉ link bị chặn.
        self.assertEqual(frappe.db.get_value("Notification Log", name, "read"), 1)
