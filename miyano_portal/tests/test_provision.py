import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.seed_demo import seed_demo
from miyano_portal.api import portal

BUYER2 = "buyer2@demo.miyano"


class TestProvision(FrappeTestCase):
    def setUp(self):
        seed_demo()
        # VÒNG SỬA 2 (F5): PXN ABC đã có quản lý đang hoạt động
        # (pxnabc@demo.miyano, dữ liệu thật đã backfill trên site này) nên
        # buyer2@demo.miyano sẽ là tài khoản THỨ HAI -> Nhân viên khoa chờ
        # gán khoa (xem test bên dưới). Dọn trước lẫn sau để `run-tests`
        # chạy hai lần liên tiếp không tích rác — cùng lý do như
        # `_don_sach` trong test_portal_member.py.
        self._don_sach()
        self.addCleanup(self._don_sach)
        self._ma_ngan_cu = frappe.db.get_value("Customer", "PXN ABC", "custom_ma_ngan")
        self.addCleanup(
            frappe.db.set_value, "Customer", "PXN ABC", "custom_ma_ngan", self._ma_ngan_cu
        )

    def _don_sach(self):
        frappe.db.delete("Portal Member", {"user": BUYER2})
        frappe.db.delete("Customer Department", {"customer": "PXN ABC", "ma_khoa": "ZZP2"})

    def test_provision_creates_website_user_and_link(self):
        res = portal.portal_provision("PXN ABC", BUYER2)
        self.assertEqual(res["user"], BUYER2)
        self.assertEqual(
            frappe.get_cached_value("User", BUYER2, "user_type"),
            "Website User",
        )

        # PXN ABC đã có quản lý đang hoạt động (pxnabc@demo.miyano) ->
        # portal_provision KHÔNG được cấp thêm quản lý thứ hai (luật
        # _chan_hai_quan_ly). Tài khoản mới phải là Nhân viên khoa CHƯA gán
        # khoa, TẮT, và hàm phải báo rõ còn một bước nữa qua cờ
        # "cho_gan_khoa" — không được để tài khoản chết lặng lẽ (vòng sửa 1
        # đúng là chỗ hỏng này: bản cũ tạo Quản lý+active=0 và không báo gì).
        self.assertTrue(res["cho_gan_khoa"])
        tv = frappe.db.get_value(
            "Portal Member", {"user": BUYER2},
            ["vai_tro", "active", "khoa_phong"], as_dict=True,
        )
        self.assertEqual(tv.vai_tro, "Nhân viên khoa")
        self.assertEqual(tv.active, 0)
        self.assertFalse(tv.khoa_phong)

        # Tài khoản vừa cấp CHƯA dùng được — đúng ý định mới, không phải lỗi.
        frappe.set_user(BUYER2)
        self.addCleanup(frappe.set_user, "Administrator")
        from miyano_portal.portal_context import get_portal_customer
        with self.assertRaises(frappe.PermissionError) as cm:
            get_portal_customer()
        self.assertIn("chưa gắn với khách hàng nào", str(cm.exception))
        frappe.set_user("Administrator")

        # Quản lý gán khoa + bật lại — đúng luồng chủ đầu tư mô tả ("nhân
        # viên có tài khoản và được gán khoa bởi quản lý"). Không dùng
        # db_set()/frappe.db.set_value() cho các field bị _chan_hai_quan_ly
        # để mắt tới — đi qua doc.save() để validate() chạy thật.
        frappe.db.set_value("Customer", "PXN ABC", "custom_ma_ngan", "ZZP2M")
        kp = frappe.get_doc({
            "doctype": "Customer Department", "customer": "PXN ABC",
            "ten_khoa_phong": "ZZTEST Khoa tạm", "ma_khoa": "ZZP2",
        }).insert(ignore_permissions=True)
        self.addCleanup(lambda: frappe.db.delete("Customer Department", {"name": kp.name}))
        pm = frappe.get_doc("Portal Member", {"user": BUYER2})
        pm.khoa_phong = kp.name
        pm.active = 1
        pm.save(ignore_permissions=True)

        frappe.set_user(BUYER2)
        self.assertEqual(get_portal_customer(), "PXN ABC")

    def test_provision_requires_admin_role(self):
        # Use an existing seeded portal user (Customer role only) to attempt provisioning.
        frappe.set_user("pxnabc@demo.miyano")
        self.addCleanup(frappe.set_user, "Administrator")
        with self.assertRaises(frappe.PermissionError):
            portal.portal_provision("PXN ABC", "buyer3@demo.miyano")
