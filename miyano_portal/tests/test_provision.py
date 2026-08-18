import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.seed_demo import seed_demo
from miyano_portal.api import portal

BUYER2 = "buyer2@demo.miyano"
NEW_CUST = "ZZTEST Provision Khach Moi"
NEW_EMAIL = "zztest.provision.new@demo.miyano"


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
        # VÒNG SỬA 3 (F5, review độc lập): đặt Mã ngắn TRƯỚC khi gọi
        # portal_provision, không phải sau. `_chan_thieu_ma_ngan` (portal_
        # member.py) KHÔNG được nới theo `active` — nó đòi Mã ngắn cho MỌI
        # `Nhân viên khoa`, kể cả bản ghi `active=0` mà `portal_provision`
        # tạo cho tài khoản chờ gán khoa. Đây là guard đúng lúc phải giữ:
        # Mã ngắn là dữ liệu của Miyano, người cấp tài khoản đặt được ngay
        # lúc đó — dời việc này ra sau (lúc quản lý bệnh viện bấm kích hoạt)
        # sẽ đẩy một lỗi họ không tự sửa được cho chính họ.
        frappe.db.set_value("Customer", "PXN ABC", "custom_ma_ngan", "ZZP2M")

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
        # viên có tài khoản và được gán khoa bởi quản lý"). Mã ngắn đã được
        # đặt từ setUp (trước lời gọi portal_provision — xem chú thích ở
        # đó). Không dùng db_set()/frappe.db.set_value() cho các field bị
        # _chan_hai_quan_ly để mắt tới — đi qua doc.save() để validate()
        # chạy thật.
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

    def test_provision_first_account_is_active_manager(self):
        """VÒNG SỬA 3 (F5, review độc lập, Important — V6): nhánh "chưa có
        quản lý nào" (`da_co_quan_ly == False` trong `portal_provision`)
        mang đúng Ý ĐỊNH GỐC "cấp xong thì dùng được ngay" — nhưng trước
        vòng sửa này KHÔNG có test nào đi qua nó, toàn bộ
        `test_provision.py` chỉ đi nhánh "đã có quản lý" (PXN ABC luôn có
        sẵn quản lý từ backfill). Dựng một `Customer` HOÀN TOÀN MỚI để chắc
        chắn đi đúng nhánh này."""
        frappe.get_doc({
            "doctype": "Customer", "customer_name": NEW_CUST,
            "customer_type": "Company", "customer_group": "All Customer Groups",
            "territory": "All Territories",
        }).insert(ignore_permissions=True)
        self.addCleanup(frappe.db.delete, "User Permission", {"user": NEW_EMAIL})
        self.addCleanup(frappe.db.delete, "Contact", {"name": f"{NEW_CUST}-{NEW_EMAIL}"})
        self.addCleanup(frappe.db.delete, "Portal Member", {"user": NEW_EMAIL})
        self.addCleanup(frappe.db.delete, "User", {"name": NEW_EMAIL})
        self.addCleanup(frappe.db.delete, "Customer", {"name": NEW_CUST})

        res = portal.portal_provision(NEW_CUST, NEW_EMAIL)
        self.assertFalse(res["cho_gan_khoa"])
        tv = frappe.db.get_value(
            "Portal Member", {"user": NEW_EMAIL},
            ["vai_tro", "active", "khoa_phong"], as_dict=True,
        )
        self.assertEqual(tv.vai_tro, "Quản lý")
        self.assertEqual(tv.active, 1)
        self.assertFalse(tv.khoa_phong)

        # Ý định gốc: cấp xong thì dùng được ngay, không cần bước gán khoa
        # nào — đối lập với nhánh "đã có quản lý" (test phía trên).
        frappe.set_user(NEW_EMAIL)
        self.addCleanup(frappe.set_user, "Administrator")
        from miyano_portal.portal_context import get_portal_customer
        self.assertEqual(get_portal_customer(), NEW_CUST)

    def test_provision_rejects_email_belonging_to_another_customer(self):
        """VÒNG SỬA 3 (F5, review độc lập, Important — V5): `pxnabc@demo.
        miyano` đã có `Portal Member` thuộc "PXN ABC" (dữ liệu thật, đã
        backfill trên site này). Gọi `portal_provision` với một khách hàng
        KHÁC cho đúng email này phải bị chặn NGAY — không âm thầm tạo
        Contact/Dynamic Link/User Permission cho khách mới trong khi danh
        tính cổng (Portal Member) của user đó vẫn trỏ về khách cũ."""
        with self.assertRaises(frappe.ValidationError) as cm:
            portal.portal_provision("Bệnh viện Bạch Mai", "pxnabc@demo.miyano")
        self.assertIn("đã thuộc khách hàng", str(cm.exception))
        # Chặn TRƯỚC mọi side effect — không có User Permission mới nào trỏ
        # sang "Bệnh viện Bạch Mai" cho email này.
        self.assertFalse(frappe.db.exists(
            "User Permission",
            {
                "user": "pxnabc@demo.miyano", "allow": "Customer",
                "for_value": "Bệnh viện Bạch Mai",
            },
        ))

    def test_provision_requires_admin_role(self):
        # Use an existing seeded portal user (Customer role only) to attempt provisioning.
        frappe.set_user("pxnabc@demo.miyano")
        self.addCleanup(frappe.set_user, "Administrator")
        with self.assertRaises(frappe.PermissionError):
            portal.portal_provision("PXN ABC", "buyer3@demo.miyano")
