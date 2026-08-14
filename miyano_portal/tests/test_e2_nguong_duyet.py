"""US-E2.2 / BR-O14 — từ chối phải có lý do. TC-E2-04.
US-E2.1 / BR-O9 / NL-2.5 — ngưỡng duyệt hai tầng. TC-E2-01..03.
"""
import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.portal_duyet_don import nguong_duyet
from miyano_portal.setup.seed_demo import seed_demo

NGUONG = 50_000_000
SALES_MANAGER_USER = "sales_manager_e2@demo.miyano"


def _dam_bao_user_sales_manager() -> str:
    """P2 #2 (kiểm thử hệ thống): TC-E2-02 bản trước chạy as `Administrator`
    — `frappe/permissions.py:506-507` cấp Administrator MỌI role vô điều
    kiện, nên nhánh `"Sales Manager" in frappe.get_roles()` luôn qua được dù
    KHÔNG tài khoản thật nào trên site giữ role đó. Tự dựng (không phụ thuộc
    site có sẵn user nào) một System User CHỈ mang role `Sales Manager`,
    idempotent — cùng khuôn `_ensure_portal_user` của seed_demo.py."""
    email = SALES_MANAGER_USER
    if not frappe.db.exists("User", email):
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": "E2 Sales Manager (test)",
            "send_welcome_email": 0,
            "user_type": "System User",
        })
        user.append("roles", {"role": "Sales Manager"})
        user.insert(ignore_permissions=True)
    else:
        user = frappe.get_doc("User", email)
    vai = {r.role for r in user.roles}
    if "Sales Manager" not in vai:
        user.append("roles", {"role": "Sales Manager"})
        user.save(ignore_permissions=True)
    # Không được mang thêm role rộng hơn (System Manager, v.v.) làm nhánh
    # thử tình cờ qua được vì lý do khác, không phải vì "Sales Manager".
    thua = [r.role for r in user.roles if r.role not in ("Sales Manager", "All")]
    if thua:
        user.roles = [r for r in user.roles if r.role in ("Sales Manager", "All")]
        user.save(ignore_permissions=True)
    return email


class TestLyDoTuChoi(FrappeTestCase):
    def setUp(self):
        seed_demo()
        self.so = _tao_so_nhap("Chờ Miyano xác nhận")

    def test_khong_co_ly_do_thi_khong_chuyen_duoc(self):
        self.so.workflow_state = "Từ chối"
        with self.assertRaises(frappe.ValidationError) as ctx:
            self.so.save()
        self.assertIn("lý do từ chối", str(ctx.exception).lower())

    def test_ly_do_qua_ngan_bi_chan(self):
        self.so.workflow_state = "Từ chối"
        self.so.custom_ly_do_tu_choi = "hết hàng"   # 8 ký tự < 10
        with self.assertRaises(frappe.ValidationError):
            self.so.save()

    def test_ly_do_du_dai_thi_luu_duoc(self):
        self.so.workflow_state = "Từ chối"
        self.so.custom_ly_do_tu_choi = "Hết hàng trong kho, dự kiến về ngày 20/08."
        self.so.save()
        self.assertEqual(
            frappe.db.get_value("Sales Order", self.so.name, "workflow_state"), "Từ chối"
        )

    def test_trang_thai_khac_khong_bi_doi_hoi_ly_do(self):
        """Đơn nội bộ đi qua máy trạng thái như cũ — DoD E2."""
        self.so.workflow_state = "Chờ Miyano xác nhận"
        self.so.save()   # không được ném


class TestNguongDuyet(FrappeTestCase):
    def setUp(self):
        seed_demo()
        frappe.db.set_single_value("Miyano Portal Settings", "nguong_duyet_2_tang", NGUONG)
        # Toàn suite có test cũ gọi so.submit() — nếu ngưỡng còn sót giá trị
        # từ đây thì chúng sẽ đỏ vì lý do chẳng liên quan. Trả ngưỡng về rỗng
        # sau mỗi test của lớp này.
        self.addCleanup(
            frappe.db.set_single_value, "Miyano Portal Settings", "nguong_duyet_2_tang", None
        )
        self.addCleanup(frappe.set_user, "Administrator")

        # Đừng giả định seed đã gán đúng vai trò — kiểm và gán nếu thiếu.
        u = frappe.get_doc("User", "sales_user@demo.miyano")
        vai = {r.role for r in u.roles}
        if "Sales User" not in vai:
            u.append("roles", {"role": "Sales User"})
            u.save(ignore_permissions=True)
        if "Sales Manager" in vai:
            u.roles = [r for r in u.roles if r.role != "Sales Manager"]
            u.save(ignore_permissions=True)

    # ---------- đọc ngưỡng: BẪY 1 ----------
    def test_nguong_de_trong_doc_ra_0(self):
        frappe.db.set_single_value("Miyano Portal Settings", "nguong_duyet_2_tang", None)
        self.assertEqual(nguong_duyet(), 0.0)

    def test_nguong_bang_0_cung_la_mot_tang(self):
        """`0` và rỗng PHẢI cư xử giống nhau. Field Currency lưu rỗng thành 0,
        nên phân biệt hai thứ này là khoá sạch quyền duyệt của Sales User."""
        frappe.db.set_single_value("Miyano Portal Settings", "nguong_duyet_2_tang", 0)
        self.assertEqual(nguong_duyet(), 0.0)

    # ---------- TC-E2-01 ----------
    def test_sales_user_duyet_duoc_don_duoi_nguong(self):
        so = _tao_so_nhap("Chờ Miyano xác nhận", tong_muc_tieu=49_000_000)
        frappe.set_user("sales_user@demo.miyano")
        so.submit()
        self.assertEqual(so.docstatus, 1)

    def test_sales_user_bi_chan_o_dung_nguong(self):
        so = _tao_so_nhap("Chờ Miyano xác nhận", tong_muc_tieu=NGUONG)
        frappe.set_user("sales_user@demo.miyano")
        with self.assertRaises(frappe.ValidationError) as ctx:
            so.submit()
        self.assertEqual(
            str(ctx.exception), "Đơn ≥ 50.000.000 ₫ — cần Sales Manager xác nhận."
        )

    def test_don_bi_chan_van_o_nguyen_trang_thai_cu(self):
        """NL-2.5 — "đơn chờ ở Chờ Miyano xác nhận", không rơi sang trạng thái lửng."""
        so = _tao_so_nhap("Chờ Miyano xác nhận", tong_muc_tieu=NGUONG)
        frappe.set_user("sales_user@demo.miyano")
        with self.assertRaises(frappe.ValidationError):
            so.submit()
        frappe.set_user("Administrator")
        self.assertEqual(
            frappe.db.get_value("Sales Order", so.name, "docstatus"), 0
        )
        self.assertEqual(
            frappe.db.get_value("Sales Order", so.name, "workflow_state"),
            "Chờ Miyano xác nhận",
        )

    # ---------- TC-E2-02 ----------
    def test_sales_manager_duyet_duoc_don_tu_nguong(self):
        """P2 #2 (kiểm thử hệ thống): chạy như một tài khoản THẬT chỉ giữ
        role `Sales Manager` — không phải `Administrator` (được cấp mọi role
        vô điều kiện, nên xanh kể cả khi không ai thật sự giữ role đó)."""
        so = _tao_so_nhap("Chờ Miyano xác nhận", tong_muc_tieu=NGUONG)
        user = _dam_bao_user_sales_manager()
        frappe.set_user(user)
        self.assertNotEqual(frappe.session.user, "Administrator")
        self.assertIn("Sales Manager", frappe.get_roles())
        so.submit()
        self.assertEqual(so.docstatus, 1)

    # ---------- TC-E2-03 ----------
    def test_nguong_de_trong_thi_sales_user_duyet_duoc_don_100tr(self):
        frappe.db.set_single_value("Miyano Portal Settings", "nguong_duyet_2_tang", None)
        so = _tao_so_nhap("Chờ Miyano xác nhận", tong_muc_tieu=100_000_000)
        frappe.set_user("sales_user@demo.miyano")
        so.submit()
        self.assertEqual(so.docstatus, 1)


def _tao_so_nhap(trang_thai: str, tong_muc_tieu: float = 1200):
    """Sales Order nháp của khách demo, ở đúng workflow_state cần thử.

    `qty = 1` nên `rate` chính là `grand_total` — miễn là không có thuế. Ca
    ngưỡng phụ thuộc vào con số này nên phải KHẲNG ĐỊNH, không phỏng đoán:
    site có `Sales Taxes and Charges Template` mặc định là mọi ca ngưỡng lệch
    đi 8-10% và đỏ vì lý do chẳng liên quan gì tới quy tắc đang thử.
    """
    from miyano_portal.setup.seed_demo import PRICE_LIST
    so = frappe.new_doc("Sales Order")
    so.customer = "Bệnh viện Bạch Mai"
    so.transaction_date = frappe.utils.today()
    so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 7)
    so.selling_price_list = PRICE_LIST
    so.append("items", {
        "item_code": "VT0005",
        "qty": 1,
        "rate": tong_muc_tieu,
        "delivery_date": so.delivery_date,
    })
    so.taxes = []            # không để template thuế mặc định chen vào
    so.taxes_and_charges = None
    so.flags.ignore_permissions = True
    # KHÔNG gán workflow_state trước insert(): với doc mới, khung
    # `validate_workflow` (frappe/model/workflow.py) ném WorkflowPermissionError
    # bất kỳ khi nào state đích khác state đầu tiên của workflow, vì
    # `_doc_before_save` chưa tồn tại cho doc chưa lưu (nhánh "transitioning
    # directly to a state other than the first"). Cứ để insert() tự gán
    # state đầu (`Chờ xác nhận`), rồi ghi thẳng xuống DB (không qua ORM, nên
    # không đụng validate_workflow) để đưa đơn về đúng trạng thái cần thử,
    # sau đó reload() để đối tượng trong bộ nhớ khớp DB — nếu không, lần
    # `.save()` kế tiếp trong test sẽ dính TimestampMismatchError.
    so.insert(ignore_permissions=True)
    if so.workflow_state != trang_thai:
        frappe.db.set_value(
            "Sales Order", so.name, "workflow_state", trang_thai, update_modified=False
        )
        so.reload()
    assert float(so.grand_total) == float(tong_muc_tieu), (
        f"grand_total={so.grand_total} khác mức cần thử {tong_muc_tieu} — "
        "có thuế hoặc chiết khấu chen vào, ca ngưỡng sẽ vô nghĩa"
    )
    return so
