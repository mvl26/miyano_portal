"""US-E2.5 — trạng thái "Chờ khách đồng ý" và endpoint portal_order_accept."""
import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.api import portal
from miyano_portal.setup.seed_demo import seed_demo

WF = "Sales Order - Client Portal"
STATE_KHACH = "Chờ khách đồng ý"


def _tao_so_cho_khach_duyet():
    from miyano_portal.setup.seed_demo import PRICE_LIST
    so = frappe.new_doc("Sales Order")
    so.customer = "Bệnh viện Bạch Mai"
    so.transaction_date = frappe.utils.today()
    so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 7)
    so.selling_price_list = PRICE_LIST
    so.append("items", {
        "item_code": "VT0005", "qty": 1, "rate": 1200,
        "delivery_date": so.delivery_date,
    })
    so.taxes = []
    so.taxes_and_charges = None
    so.insert(ignore_permissions=True)
    # BẪY 4 — không gán workflow_state trước insert(). Xem Global Constraints.
    frappe.db.set_value(
        "Sales Order", so.name, "workflow_state", "Chờ khách đồng ý",
        update_modified=False,
    )
    so.reload()
    return so


class TestWorkflowMoRong(FrappeTestCase):
    def test_co_state_cho_khach_dong_y(self):
        wf = frappe.get_doc("Workflow", WF)
        s = next((x for x in wf.states if x.state == STATE_KHACH), None)
        self.assertIsNotNone(s, "thiếu state 'Chờ khách đồng ý'")
        self.assertEqual(str(s.doc_status), "0")

    def test_du_bon_transition_moi(self):
        wf = frappe.get_doc("Workflow", WF)
        co = {(t.state, t.action, t.next_state) for t in wf.transitions}
        for mong_doi in [
            ("Chờ xác nhận", "Gửi khách duyệt", STATE_KHACH),
            (STATE_KHACH, "Khách đồng ý", "Chờ Miyano xác nhận"),
            (STATE_KHACH, "Khách không đồng ý", "Chờ xác nhận"),
            ("Chờ Miyano xác nhận", "Xác nhận", "Đã xác nhận"),
        ]:
            with self.subTest(t=mong_doi):
                self.assertIn(mong_doi, co)

    def test_khong_transition_nao_mo_cho_role_customer(self):
        """Rào an toàn: role `Customer` lọt vào `allowed` là khách tự duyệt
        được đơn của chính mình từ Desk."""
        wf = frappe.get_doc("Workflow", WF)
        for t in wf.transitions:
            with self.subTest(t=f"{t.state}->{t.next_state}"):
                self.assertNotIn("Customer", (t.allowed or ""))

    def test_transition_cu_van_con_nguyen(self):
        """Không được dựng lại workflow — đơn nội bộ vẫn đi đường cũ (DoD)."""
        wf = frappe.get_doc("Workflow", WF)
        co = {(t.state, t.action, t.next_state) for t in wf.transitions}
        self.assertIn(("Chờ xác nhận", "Gửi duyệt", "Chờ Miyano xác nhận"), co)
        self.assertIn(("Chờ Miyano xác nhận", "Từ chối", "Từ chối"), co)


class TestOrderAccept(FrappeTestCase):
    def setUp(self):
        seed_demo()
        self.so = _tao_so_cho_khach_duyet()   # helper dưới
        self.addCleanup(frappe.set_user, "Administrator")

    def test_dong_y_chuyen_sang_cho_miyano_xac_nhan(self):
        frappe.set_user("bvbm@demo.miyano")
        kq = portal.portal_order_accept(self.so.name, "dong_y")
        self.assertEqual(kq["trang_thai_moi"], "Chờ Miyano xác nhận")
        frappe.set_user("Administrator")
        self.assertEqual(
            frappe.db.get_value("Sales Order", self.so.name, "workflow_state"),
            "Chờ Miyano xác nhận",
        )

    def test_dong_y_ghi_log_nguoi_bam_vao_comment(self):
        frappe.set_user("bvbm@demo.miyano")
        portal.portal_order_accept(self.so.name, "dong_y")
        frappe.set_user("Administrator")
        cmt = frappe.get_all(
            "Comment",
            filters={"reference_doctype": "Sales Order", "reference_name": self.so.name},
            pluck="content",
        )
        self.assertTrue(
            any("bvbm@demo.miyano" in (c or "") for c in cmt),
            "phải ghi lại AI bấm đồng ý — không có log thì không truy được trách nhiệm",
        )

    def test_khong_dong_y_bat_buoc_ly_do(self):
        frappe.set_user("bvbm@demo.miyano")
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_accept(self.so.name, "khong_dong_y")

    # ---------- TC-E6-10 ----------
    def test_khong_dong_y_ly_do_5_ky_tu_bi_chan(self):
        """TC-E6-10 — lý do 5 ký tự phải CHẶN (dưới ngưỡng
        `LY_DO_TOI_THIEU_KHACH=10`). Bản trước chỉ có ca không gửi `ly_do`
        nào cả (`None` -> rỗng -> `len(0) < ngưỡng`), luôn đúng bất kể
        ngưỡng >= 1 nên không chạm được nhánh so sánh ĐỘ DÀI thật —
        hạ `LY_DO_TOI_THIEU_KHACH` 10 -> 1 vẫn để lọt (0 < 1 vẫn đúng). Ca
        này gửi đúng 5 ký tự (chạm nhánh `len(ly_do) < LY_DO_TOI_THIEU_KHACH`
        với một giá trị > 0), nên đỏ ngay nếu ngưỡng bị hạ xuống <= 5."""
        ly_do_5 = "Đắt á"
        self.assertEqual(len(ly_do_5), 5, "fixture sai — TC đòi đúng 5 ký tự")
        frappe.set_user("bvbm@demo.miyano")
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_accept(self.so.name, "khong_dong_y", ly_do=ly_do_5)
        frappe.set_user("Administrator")
        self.assertEqual(
            frappe.db.get_value("Sales Order", self.so.name, "workflow_state"),
            STATE_KHACH,
            "lý do dưới ngưỡng bị chặn thì đơn KHÔNG được đổi trạng thái",
        )

    def test_khong_dong_y_ly_do_15_ky_tu_ve_cho_xac_nhan_va_luu_lai(self):
        """TC-E6-10 — lý do 15 ký tự phải ĐẬU, đơn về "Chờ xác nhận", và lý
        do PHẢI truy vết được — đây là chứng từ đàm phán giá, mất là mất căn
        cứ. Bản trước dùng 28 ký tự (dư so với ngưỡng 10, không đứng sát
        biên 15 mà TC yêu cầu) và không có assertion nào đọc lại lý do đã
        lưu. Hạ ngưỡng 10 -> 1 không làm ca 15 ký tự đỏ (đó là hành vi ĐÚNG:
        15 vẫn >= 1) — ca đó chỉ để chứng minh đường "đậu" còn hoạt động
        đúng, ranh giới thật được `test_khong_dong_y_ly_do_5_ky_tu_bi_chan`
        (5 ký tự) bảo vệ."""
        ly_do_15 = "Giá quá cao rồi"
        self.assertEqual(len(ly_do_15), 15, "fixture sai — TC đòi đúng 15 ký tự")
        frappe.set_user("bvbm@demo.miyano")
        kq = portal.portal_order_accept(self.so.name, "khong_dong_y", ly_do=ly_do_15)
        self.assertEqual(kq["trang_thai_moi"], "Chờ xác nhận")

        frappe.set_user("Administrator")
        self.assertEqual(
            frappe.db.get_value("Sales Order", self.so.name, "workflow_state"),
            "Chờ xác nhận",
        )
        # Lý do PHẢI lưu lại — nơi lưu hiện tại là Comment gắn vào chính SO
        # (BA §4.10/review I-5 đòi "lý do lưu vào đơn"). Đọc lại qua
        # `frappe.get_all("Comment", ...)`, KHÔNG chỉ tin `add_comment` đã
        # được gọi — comment thật sự phải nằm trong CSDL, đọc lại được sau
        # khi request đã kết thúc (khác request, khác phiên).
        cmt = frappe.get_all(
            "Comment",
            filters={"reference_doctype": "Sales Order", "reference_name": self.so.name},
            pluck="content",
        )
        self.assertTrue(
            any(ly_do_15 in (c or "") for c in cmt),
            "lý do không đồng ý phải truy vết được trên chính đơn hàng — "
            "mất lý do là mất căn cứ đàm phán giá",
        )

    def test_khong_dong_y_kem_ly_do_ve_cho_xac_nhan(self):
        frappe.set_user("bvbm@demo.miyano")
        kq = portal.portal_order_accept(
            self.so.name, "khong_dong_y", ly_do="Giá cao hơn dự toán của đơn vị."
        )
        self.assertEqual(kq["trang_thai_moi"], "Chờ xác nhận")

    # ---------- TC-E2-06 ----------
    def test_don_cua_khach_khac_bi_tu_choi_403(self):
        frappe.set_user("pxnabc@demo.miyano")
        with self.assertRaises(frappe.PermissionError):
            portal.portal_order_accept(self.so.name, "dong_y")
        frappe.set_user("Administrator")
        self.assertEqual(
            frappe.db.get_value("Sales Order", self.so.name, "workflow_state"),
            "Chờ khách đồng ý",
            "đơn không được đổi trạng thái khi bị chặn",
        )

    def test_don_khong_o_trang_thai_cho_khach_thi_chan(self):
        frappe.db.set_value("Sales Order", self.so.name, "workflow_state", "Chờ xác nhận")
        frappe.set_user("bvbm@demo.miyano")
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_accept(self.so.name, "dong_y")

    # ---------- Code review: session của khách không được hỏng ----------
    def test_phien_khach_khong_bi_hong_sau_khi_goi(self):
        """`apply_workflow` chạy dưới quyền hệ thống KHÔNG được để lại dấu
        vết trên session thật của khách — cụ thể `sid` và `data` phải
        NGUYÊN VẸN từng byte, không chỉ `user` quay lại đúng tên.

        `frappe.set_user()` (cách làm cũ) ghi đè `local.session.sid` bằng
        chính chuỗi username và xoá sạch `local.session.data` (mất
        csrf_token...) — và `Session.update()` ở cuối MỌI request thật
        (frappe/sessions.py) dùng `sid` GỐC (không đổi) làm khoá ghi cache,
        nên nó ghi đè cache session THẬT của khách bằng dữ liệu đã hỏng.
        Gán thẳng `sid`/`data` giả lập ở đây rồi so khớp bit-for-bit sau khi
        gọi là phép thử phân biệt được hai cách làm — test này FAIL với
        cách cũ (`frappe.set_user`) và PASS với cách mới (chỉ đổi
        `session.user`).
        """
        frappe.set_user("bvbm@demo.miyano")
        session = frappe.local.session
        session.sid = "sid-that-cua-khach-gia-lap-de-kiem-tra"
        session.data = frappe._dict(
            {"csrf_token": "token-that-gia-lap", "data": frappe._dict({"hello": "world"})}
        )
        sid_truoc = session.sid
        data_truoc = dict(session.data)

        portal.portal_order_accept(self.so.name, "dong_y")

        self.assertEqual(
            frappe.session.user, "bvbm@demo.miyano",
            "phiên phải quay về đúng người bấm, không được dừng lại ở Administrator",
        )
        self.assertEqual(
            frappe.local.session.sid, sid_truoc,
            "sid của khách bị đổi — sẽ khiến Session.update() ghi cache session thật sai chỗ",
        )
        self.assertEqual(
            dict(frappe.local.session.data), data_truoc,
            "data của khách (kể cả csrf_token) bị mất — mọi POST sau đó trên "
            "tab đang mở sẽ lỗi CSRF tới khi tải lại trang",
        )
