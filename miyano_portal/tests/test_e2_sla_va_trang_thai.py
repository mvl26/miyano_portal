"""US-E2.2 (email lý do), US-E2.3 (SLA), US-E2.4 (đóng sớm)."""
import email

import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.api import portal
from miyano_portal.api.portal import _so_status_vi
from miyano_portal.portal_sla import gio_lam_viec_troi_qua, quet_don_treo
from miyano_portal.setup.seed_demo import seed_demo

MAIL_TU_CHOI = "Portal - Đơn bị từ chối"


def _van_ban_thuan_tuy_email(raw: str) -> str:
    """`Email Queue.message` là MIME thô (multipart, quoted-printable) — có
    những dấu `=\\r\\n` xuống dòng MỀM chen giữa chuỗi, kể cả giữa các ký tự
    ASCII thuần, nên `assertIn` trên chuỗi thô có thể trật dù nội dung thật
    sự có mặt. Giải mã đúng phần `text/plain` bằng module `email` chuẩn của
    Python trước khi so khớp."""
    msg = email.message_from_string(raw)
    phan = []
    parts = msg.walk() if msg.is_multipart() else [msg]
    for part in parts:
        if part.get_content_type() == "text/plain":
            payload = part.get_payload(decode=True) or b""
            phan.append(payload.decode(part.get_content_charset() or "utf-8", "replace"))
    return "\n".join(phan)


def _tao_so_bi_tu_choi(ly_do: str):
    """Sales Order đã ở trạng thái "Từ chối", mang `ly_do` trong
    `custom_ly_do_tu_choi`.

    Đi thẳng qua `frappe.db.set_value` để bỏ qua `kiem_ly_do_tu_choi`
    (validate hook) — test này không kiểm tra hook đó, nó kiểm tra
    `portal_order_track` đọc lại đúng lý do đã có sẵn trên đơn.
    """
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
        "Sales Order", so.name, "custom_ly_do_tu_choi", ly_do, update_modified=False
    )
    frappe.db.set_value(
        "Sales Order", so.name, "workflow_state", "Từ chối", update_modified=False
    )
    so.reload()
    return so


class TestMailTuChoi(FrappeTestCase):
    def setUp(self):
        # seed_demo() idempotent — cần cho test thứ ba (customer, item, price
        # list); hai test đầu không đụng dữ liệu demo nhưng gọi chung cho gọn.
        seed_demo()

    def test_mail_co_chen_lay_do_tu_choi(self):
        msg = frappe.db.get_value("Notification", MAIL_TU_CHOI, "message")
        self.assertIn(
            "custom_ly_do_tu_choi", msg,
            "email từ chối phải mang đúng lý do (US-E2.2), không phải câu "
            "'liên hệ để biết thêm chi tiết'",
        )

    def test_mail_van_bat_va_dung_dieu_kien_cu(self):
        n = frappe.get_doc("Notification", MAIL_TU_CHOI)
        self.assertTrue(n.enabled)
        self.assertEqual(n.value_changed, "workflow_state")
        self.assertIn("Từ chối", n.condition)

    def test_order_track_tra_ly_do_tu_choi(self):
        so = _tao_so_bi_tu_choi("Hết hàng trong kho, dự kiến về ngày 20/08.")
        frappe.set_user("bvbm@demo.miyano")
        self.addCleanup(frappe.set_user, "Administrator")
        kq = portal.portal_order_track(so.name)
        self.assertIn("ngày 20/08", kq["ly_do_tu_choi"])

    def test_mail_render_that_mang_dung_ly_do_khach_nhap(self):
        """P2 #4 (kiểm thử hệ thống): `test_mail_co_chen_lay_do_tu_choi` ở
        trên chỉ kiểm MÃ NGUỒN template (`"custom_ly_do_tu_choi" in
        message`) — không render Jinja, không đọc Email Queue, không khẳng
        định CHỮ LÝ DO THẬT có mặt trong thư. Khuôn theo
        test_e6_mua_le.py::TestJobBaoGiaHetHan.test_gui_email_hai_phia.

        Chuyển đơn sang "Từ chối" bằng `.save()` THẬT (không né qua
        frappe.db.set_value như `_tao_so_bi_tu_choi`) để kích hoạt đúng
        đường Frappe tự chạy: `run_notifications()` -> `evaluate_alert()`
        cho Notification "Value Change" — render template rồi queue email
        thật, đúng những gì khách thật sự nhận được.
        """
        frappe.flags.mute_emails = True
        self.addCleanup(frappe.flags.pop, "mute_emails", None)

        from miyano_portal.setup.seed_demo import PRICE_LIST
        so = frappe.new_doc("Sales Order")
        so.customer = "Bệnh viện Bạch Mai"
        so.transaction_date = frappe.utils.today()
        so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 7)
        so.selling_price_list = PRICE_LIST
        so.custom_nguon_don = "Client Portal"  # điều kiện Notification đòi
        so.contact_email = "bvbm@demo.miyano"
        so.append("items", {
            "item_code": "VT0005", "qty": 1, "rate": 1200,
            "delivery_date": so.delivery_date,
        })
        so.taxes = []
        so.taxes_and_charges = None
        so.insert(ignore_permissions=True)
        # BẪY 4 — không gán workflow_state trước insert(). Xem docstring
        # _tao_so_nhap() ở test_e2_nguong_duyet.py cho lý do đầy đủ.
        frappe.db.set_value(
            "Sales Order", so.name, "workflow_state", "Chờ Miyano xác nhận",
            update_modified=False,
        )
        so.reload()
        frappe.db.delete("Email Queue", {"reference_name": so.name})

        ly_do = "Hết hàng trong kho, dự kiến về ngày 20/08 (mã đối chiếu ĐC-E204)."
        so.workflow_state = "Từ chối"
        so.custom_ly_do_tu_choi = ly_do
        so.save()  # transition THẬT qua validate() + on_change() -> Notification chạy

        hang_doi = frappe.get_all(
            "Email Queue", filters={"reference_name": so.name}, pluck="name",
        )
        self.assertTrue(
            hang_doi,
            "Notification 'Portal - Đơn bị từ chối' phải queue được ít nhất "
            "một email khi đơn chuyển sang Từ chối",
        )
        noi_dung = "\n".join(
            _van_ban_thuan_tuy_email(frappe.db.get_value("Email Queue", r, "message") or "")
            for r in hang_doi
        )
        self.assertIn(
            ly_do, noi_dung,
            "thư PHẢI mang đúng CHỮ lý do khách/sales đã nhập, không phải "
            "chỉ tên field hay câu chung chung 'liên hệ để biết thêm chi tiết'",
        )

        nguoi_nhan = set(frappe.get_all(
            "Email Queue Recipient", filters={"parent": ["in", hang_doi]}, pluck="recipient",
        ))
        self.assertIn("bvbm@demo.miyano", nguoi_nhan, "khách phải nhận được thư từ chối")


def _tao_so_treo(cho_tu_luc: str):
    """Sales Order ở "Chờ Miyano xác nhận", `modified` đặt về `cho_tu_luc`.

    Lùi `modified` bằng SQL thẳng: `doc.save()` luôn đặt lại `modified` = bây
    giờ, nên không có cách nào dựng được đơn treo qua đường document bình thường.
    Nhận mốc TUYỆT ĐỐI chứ không nhận "số giờ trước" — số giờ trước phụ thuộc
    vào lúc chạy test, mốc tuyệt đối thì không.
    """
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
    # `update_modified=False` là BẮT BUỘC ở đây: job SLA tính giờ treo từ
    # `modified`, để set_value chạm vào nó là phá chính thứ đang thử.
    frappe.db.set_value(
        "Sales Order", so.name, "workflow_state", "Chờ Miyano xác nhận",
        update_modified=False,
    )
    frappe.db.sql(
        "update `tabSales Order` set modified=%s where name=%s", (cho_tu_luc, so.name)
    )
    return so


class TestSLADonTreo(FrappeTestCase):
    def setUp(self):
        seed_demo()
        frappe.db.set_single_value("Miyano Portal Settings", "sla_xu_ly_don_gio", 8)
        frappe.db.delete("Notification Log", {"subject": ("like", "Portal - Đơn treo%")})
        # FrappeTestCase chỉ rollback một lần mỗi CLASS (Global Constraints):
        # đơn "treo" dựng ở một test trước vẫn còn nguyên khi test sau chạy,
        # nên quet_don_treo() sẽ đếm luôn cả nó nếu không dọn ở đây. seed_demo()
        # không tự tạo Sales Order nào ở trạng thái này, nên xoá sạch là an toàn.
        frappe.db.delete(
            "Sales Order", {"workflow_state": "Chờ Miyano xác nhận", "docstatus": 0}
        )

    # ---------- đếm giờ làm việc ----------
    def test_bo_qua_cuoi_tuan(self):
        """T6 17:00 -> T2 09:00 chỉ tính 16 giờ làm việc, không phải 64 giờ."""
        self.assertAlmostEqual(
            gio_lam_viec_troi_qua("2026-08-07 17:00:00", moc="2026-08-10 09:00:00"),
            16.0, delta=0.1,
        )

    def test_trong_tuan_tinh_binh_thuong(self):
        self.assertAlmostEqual(
            gio_lam_viec_troi_qua("2026-08-11 09:00:00", moc="2026-08-11 17:00:00"),
            8.0, delta=0.1,
        )

    # ---------- TC-E2-05 ----------
    # MOC cố định (Thứ Tư 16:00) để ca test không phụ thuộc lúc chạy. Dùng giờ
    # thực: chạy vào sáng Thứ Hai thì "9 giờ trước" rơi vào Chủ Nhật, số giờ
    # làm việc ra gần 0, và ca sẽ đỏ vì lịch chứ không vì code.
    MOC = "2026-08-12 16:00:00"

    def test_don_treo_qua_sla_thi_nhac_manager(self):
        so = _tao_so_treo("2026-08-12 07:00:00")   # 9 giờ làm việc trước MOC
        self.assertEqual(quet_don_treo(moc=self.MOC), 1)
        self.assertTrue(
            frappe.db.exists(
                "Notification Log", {"subject": ("like", f"%{so.name}%")}
            )
        )

    def test_don_chua_qua_sla_thi_im(self):
        _tao_so_treo("2026-08-12 13:00:00")        # 3 giờ trước MOC
        self.assertEqual(quet_don_treo(moc=self.MOC), 0)

    def test_moi_don_chi_nhac_mot_lan_moi_ngay(self):
        _tao_so_treo("2026-08-12 07:00:00")
        self.assertEqual(quet_don_treo(moc=self.MOC), 1)
        self.assertEqual(
            quet_don_treo(moc=self.MOC), 0, "chạy hourly mà nhắc mỗi giờ là spam"
        )

    def test_don_da_xac_nhan_khong_bi_nhac(self):
        so = _tao_so_treo("2026-08-12 07:00:00")
        frappe.db.set_value("Sales Order", so.name, "workflow_state", "Đã xác nhận")
        self.assertEqual(quet_don_treo(moc=self.MOC), 0)


class TestBaoCaoDonCham(FrappeTestCase):
    def test_bao_cao_ton_tai_va_chay_duoc(self):
        from frappe.desk.query_report import run
        self.assertTrue(frappe.db.exists("Report", "Đơn chậm xử lý"))
        kq = run("Đơn chậm xử lý", ignore_prepared_report=True)
        self.assertIn("columns", kq)

    def test_bao_cao_chi_danh_cho_nhan_vien(self):
        """Role `Customer` mà đọc được báo cáo này là thấy đơn của khách khác."""
        roles = frappe.get_all(
            "Has Role", filters={"parent": "Đơn chậm xử lý", "parenttype": "Report"},
            pluck="role",
        )
        self.assertNotIn("Customer", roles)
        self.assertTrue(roles, "báo cáo không khai role nào là mặc định mở quá rộng")


class TestTrangThaiDongSom(FrappeTestCase):
    def test_closed_khong_con_la_da_huy(self):
        """Đơn giao dở rồi đóng sớm KHÔNG phải đơn bị huỷ — khách đọc "Đã huỷ"
        sẽ tưởng chưa nhận được gì, trong khi đã nhận 60%."""
        self.assertEqual(_so_status_vi("Closed", per_delivered=60), "Hoàn thành (đóng sớm)")

    def test_closed_khi_chua_giao_gi_van_la_dong_som(self):
        self.assertEqual(_so_status_vi("Closed", per_delivered=0), "Hoàn thành (đóng sớm)")

    def test_cancelled_van_la_da_huy(self):
        self.assertEqual(_so_status_vi("Cancelled", per_delivered=0), "Đã huỷ")

    def test_cac_trang_thai_khac_khong_doi(self):
        self.assertEqual(_so_status_vi("Completed", per_delivered=100), "Hoàn thành")
        self.assertEqual(_so_status_vi("Draft", per_delivered=0), "Chờ xác nhận")
        self.assertEqual(_so_status_vi("To Deliver and Bill", per_delivered=30), "Đang giao")
