"""E6 phần B — Yêu cầu hàng hoá (`Portal Item Request`), phần Desk-only còn
sống sau spec 2026-08-15 §3.2: cổng khách hàng đã gỡ 6 endpoint
(`portal_yeu_cau_list/detail/save/cancel/tra_loi/file` — xem
test_go_yeu_cau_khoi_cong.py, cùng thư mục), nhưng toàn bộ phía Miyano Desk
GIỮ NGUYÊN — doctype, state machine, job SLA leo thang, báo cáo demand
pipeline, ba Notification nội bộ.

Re-home từ `test_e6_yeu_cau.py` gốc (xoá ở task 1, cùng lúc với 6 endpoint):
file gốc trộn CHUNG test của lớp cổng (gọi thẳng `api/portal.py::
portal_yeu_cau_*`, đã chết vì endpoint không còn) với test của lớp Desk vẫn
sống. `git rm` cả file gốc xoá theo LUÔN 5 class Desk còn sống, để lại độ phủ
bằng không cho state machine/job SLA/báo cáo/email — trong khi brief chính
task này dặn GIỮ NGUYÊN các phần đó. File này chỉ mang theo 5 class thật sự
Desk-only, không dựng lại 5 class gọi endpoint đã xoá
(`TestPortalYeuCauSave/List/Cancel/TraLoi/DetailVaFile` — bỏ hẳn, đúng
nghĩa).

Một ca cần đổi đường ghi: `TestQuetYeuCauQuaHan.
test_sua_nhap_khong_reset_dong_ho_sla` trước đây gọi
`portal.portal_yeu_cau_save()` để mô phỏng khách sửa nháp; giờ dựng thẳng
qua `doc.save()` (cùng khuôn `_tao_yeu_cau`) — điều nó kiểm (sửa nháp không
reset đồng hồ SLA tính từ `creation`) không đổi, chỉ đổi đường ghi vì
endpoint không còn tồn tại để gọi.
"""

import email

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, get_datetime, nowdate

from miyano_portal import demand_pipeline
from miyano_portal.portal_sla import cong_gio_lam_viec, gio_lam_viec_troi_qua, quet_yeu_cau_qua_han
from miyano_portal.setup.seed_demo import seed_demo

CUSTOMER_BM = "Bệnh viện Bạch Mai"
CUSTOMER_PXN = "PXN ABC"
BM_USER = "bvbm@demo.miyano"
PXN_USER = "pxnabc@demo.miyano"


def _van_ban_thuan_tuy_email(raw: str) -> str:
    """`Email Queue.message` là MIME thô (multipart, quoted-printable) —
    giải mã đúng phần `text/plain` bằng module `email` chuẩn của Python
    trước khi so khớp chuỗi, tránh dấu `=\\r\\n` xuống dòng MỀM chen giữa
    chuỗi thô làm assertIn trật oan."""
    msg = email.message_from_string(raw)
    phan = []
    parts = msg.walk() if msg.is_multipart() else [msg]
    for part in parts:
        if part.get_content_type() == "text/plain":
            payload = part.get_payload(decode=True) or b""
            phan.append(payload.decode(part.get_content_charset() or "utf-8", "replace"))
    return "\n".join(phan)


_USER_CUA_KHACH = {CUSTOMER_BM: BM_USER, CUSTOMER_PXN: PXN_USER}


def _tao_yeu_cau(customer, **kw):
    """Dựng thẳng qua get_doc (bỏ qua endpoint) — nhanh hơn và không phụ
    thuộc hành vi của một endpoint cổng nào (đúng cho phần Desk-only:
    portal_yeu_cau_save() đã gỡ khỏi cổng, chỉ còn ý nghĩa như một cách tạo
    dữ liệu mẫu ở đây)."""
    data = {
        "doctype": "Portal Item Request",
        "customer": customer,
        "nguoi_yeu_cau": _USER_CUA_KHACH.get(customer, "test@demo.miyano"),
        "loai": "Tìm nguồn hàng mới",
        "ten_hang": "Yêu cầu mặc định test",
        "dvt": "Hộp",
        "so_luong_du_kien": 5,
    }
    data.update(kw)
    doc = frappe.get_doc(data)
    doc.insert(ignore_permissions=True)
    return doc


# ---------------------------------------------------------------------------
# Doctype — BR-Y1 (máy trạng thái), BR-Y2 (lý do bắt buộc), BR-Y4 (không xoá)
# ---------------------------------------------------------------------------

class TestPortalItemRequestDoctype(FrappeTestCase):
    def setUp(self):
        seed_demo()

    def test_yeu_cau_moi_mac_dinh_trang_thai_moi(self):
        doc = _tao_yeu_cau(CUSTOMER_BM)
        self.assertEqual(doc.trang_thai, "Mới")
        self.assertTrue(doc.name.startswith("YCH-"))

    def test_khong_dap_ung_thieu_ly_do_bi_chan(self):  # TC-E6-08
        doc = _tao_yeu_cau(CUSTOMER_BM)
        doc.trang_thai = "Đang tìm nguồn"
        doc.save(ignore_permissions=True)
        doc.trang_thai = "Không đáp ứng được"
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    def test_khong_dap_ung_co_ly_do_thi_luu_duoc(self):  # TC-E6-08
        doc = _tao_yeu_cau(CUSTOMER_BM)
        doc.trang_thai = "Đang tìm nguồn"
        doc.save(ignore_permissions=True)
        doc.trang_thai = "Không đáp ứng được"
        doc.ly_do_khong_dap_ung = "Không tìm được nguồn hàng phù hợp."
        doc.save(ignore_permissions=True)
        doc.reload()
        self.assertEqual(doc.trang_thai, "Không đáp ứng được")

    def test_chuyen_thang_tu_moi_sang_da_bao_gia_bi_chan(self):  # BR-Y1
        doc = _tao_yeu_cau(CUSTOMER_BM)
        doc.trang_thai = "Đã báo giá"
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    def test_can_them_thong_tin_ve_lai_dang_tim_nguon_hop_le(self):  # BR-Y1
        doc = _tao_yeu_cau(CUSTOMER_BM)
        doc.trang_thai = "Đang tìm nguồn"
        doc.save(ignore_permissions=True)
        doc.trang_thai = "Cần thêm thông tin"
        doc.save(ignore_permissions=True)
        doc.trang_thai = "Đang tìm nguồn"
        doc.save(ignore_permissions=True)  # không ném — cạnh hai chiều hợp lệ
        doc.reload()
        self.assertEqual(doc.trang_thai, "Đang tìm nguồn")

    def test_trang_thai_ket_thuc_khong_chuyen_tiep_duoc(self):  # BR-Y1/BR-Y4
        doc = _tao_yeu_cau(CUSTOMER_BM)
        doc.trang_thai = "Khách huỷ"
        doc.save(ignore_permissions=True)
        doc.trang_thai = "Đang tìm nguồn"
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    def test_khong_xoa_duoc_du_o_trang_thai_nao(self):  # BR-Y4
        doc = _tao_yeu_cau(CUSTOMER_BM)
        with self.assertRaises(frappe.ValidationError):
            frappe.delete_doc("Portal Item Request", doc.name, ignore_permissions=True)
        doc2 = _tao_yeu_cau(CUSTOMER_BM, ten_hang="Yêu cầu 2")
        doc2.trang_thai = "Khách huỷ"
        doc2.save(ignore_permissions=True)
        with self.assertRaises(frappe.ValidationError):
            frappe.delete_doc("Portal Item Request", doc2.name, ignore_permissions=True)

    def test_khong_docperm_cho_customer(self):
        for table in ("DocPerm", "Custom DocPerm"):
            rows = frappe.get_all(
                table, filters={"parent": "Portal Item Request", "role": "Customer"},
            )
            self.assertEqual(rows, [], table)

    def test_dinh_kien_ngay_can_qua_khu_bi_chan(self):
        with self.assertRaises(frappe.ValidationError):
            _tao_yeu_cau(CUSTOMER_BM, ngay_can=add_days(nowdate(), -1))

    def test_dinh_ky_thieu_chu_ky_bi_chan(self):
        with self.assertRaises(frappe.ValidationError):
            _tao_yeu_cau(CUSTOMER_BM, tan_suat="Định kỳ")


# ---------------------------------------------------------------------------
# Job SLA leo thang — TC-E6-07 / NL-11.2
# ---------------------------------------------------------------------------

class TestQuetYeuCauQuaHan(FrappeTestCase):
    MOC = "2026-08-12 16:00:00"  # Thứ Tư — cùng mốc cố định với TestSLADonTreo

    def setUp(self):
        seed_demo()
        frappe.db.set_single_value("Miyano Portal Settings", "sla_yeu_cau_gio", 48)
        frappe.db.delete(
            "Notification Log",
            {"subject": ("like", "Portal - Yêu cầu hàng hoá treo SLA%")},
        )
        # Cùng lý do với TestSLADonTreo: FrappeTestCase rollback theo CLASS,
        # dọn sạch mọi "Mới" sót lại từ test trước trong cùng class.
        frappe.db.delete("Portal Item Request", {"trang_thai": "Mới"})

    def _tao_qua_han(self, tao_luc, **kw):
        doc = _tao_yeu_cau(CUSTOMER_BM, **kw)
        frappe.db.sql(
            "update `tabPortal Item Request` set creation=%s where name=%s",
            (tao_luc, doc.name),
        )
        return doc

    def _so_lan_nhac(self, doc_name) -> int:
        """M-5 (review) — đếm Notification Log CHO ĐÚNG TÊN bản ghi của
        CHÍNH test này, không đọc giá trị trả về (int tuyệt đối) của
        quet_yeu_cau_qua_han(): giá trị đó phụ thuộc SỐ NGƯỜI có role Sales
        Manager trên site (job insert một dòng MỖI người nhận — xem
        _nguoi_nhan() trong portal_sla.py), một con số ngoài tầm kiểm soát
        của setUp (đúng bẫy #5 của brief). Vì vậy các test dưới đây KHÔNG so
        con số này với một hằng số tuyệt đối — chỉ so nó TRƯỚC/SAU trong
        cùng một test (test_moi_yeu_cau_chi_nhac_mot_lan_moi_ngay), hoặc so
        có/không (>0 hay ==0)."""
        return frappe.db.count(
            "Notification Log", {"subject": ("like", f"%{doc_name}%")}
        )

    def test_yeu_cau_qua_sla_o_moi_thi_nhac_manager(self):
        doc = self._tao_qua_han("2026-08-05 08:00:00", ten_hang="Treo lâu rồi")
        quet_yeu_cau_qua_han(moc=self.MOC)
        self.assertGreater(self._so_lan_nhac(doc.name), 0)

    def test_yeu_cau_chua_qua_sla_thi_im(self):
        doc = self._tao_qua_han("2026-08-12 13:00:00", ten_hang="Còn mới nguyên")
        quet_yeu_cau_qua_han(moc=self.MOC)
        self.assertEqual(self._so_lan_nhac(doc.name), 0)

    def test_moi_yeu_cau_chi_nhac_mot_lan_moi_ngay(self):
        doc = self._tao_qua_han("2026-08-05 08:00:00", ten_hang="Nhắc một lần")
        quet_yeu_cau_qua_han(moc=self.MOC)
        sau_lan_1 = self._so_lan_nhac(doc.name)
        self.assertGreater(sau_lan_1, 0)
        quet_yeu_cau_qua_han(moc=self.MOC)
        self.assertEqual(
            self._so_lan_nhac(doc.name), sau_lan_1,
            "chạy hourly mà nhắc mỗi giờ là spam",
        )

    def test_yeu_cau_da_xu_ly_khong_bi_nhac(self):
        doc = self._tao_qua_han("2026-08-05 08:00:00", ten_hang="Đã có người nhận")
        doc.reload()
        doc.trang_thai = "Đang tìm nguồn"
        doc.save(ignore_permissions=True)
        quet_yeu_cau_qua_han(moc=self.MOC)
        self.assertEqual(self._so_lan_nhac(doc.name), 0)

    def test_sua_nhap_khong_reset_dong_ho_sla(self):
        """LỆCH CÓ CHỦ Ý so với quet_don_treo (dùng `modified`): SLA của yêu
        cầu tính từ `creation`, vì khách được sửa nháp "Mới" của chính mình
        — nếu job dùng `modified`, một lần khách sửa ghi chú sẽ âm thầm reset
        đồng hồ SLA nội bộ.

        Đường ghi: `doc.save()` trực tiếp, cùng khuôn `_tao_yeu_cau` — endpoint
        `portal_yeu_cau_save` đã gỡ khỏi cổng (spec 2026-08-15 §3.2, task 1);
        điều test này kiểm (sửa nháp không reset `creation`) không đổi."""
        doc = self._tao_qua_han("2026-08-05 08:00:00", ten_hang="Sắp bị sửa")
        doc.reload()
        doc.ten_hang = "Sắp bị sửa — đã cập nhật"
        doc.save(ignore_permissions=True)
        quet_yeu_cau_qua_han(moc=self.MOC)
        self.assertGreater(
            self._so_lan_nhac(doc.name), 0,
            "sửa nháp không được reset đồng hồ SLA tính từ creation",
        )


# ---------------------------------------------------------------------------
# cong_gio_lam_viec — chiều ngược của gio_lam_viec_troi_qua, phải khớp nhau
# (delta nhỏ do cắt ngày ở 23:59:59, xem docstring portal_sla.py)
# ---------------------------------------------------------------------------

class TestCongGioLamViec(FrappeTestCase):
    def test_doi_xung_voi_gio_lam_viec_troi_qua(self):
        bat_dau = "2026-08-10 09:00:00"  # Thứ Hai
        han = cong_gio_lam_viec(bat_dau, 48)
        gio_do_lai = gio_lam_viec_troi_qua(bat_dau, moc=han)
        self.assertAlmostEqual(gio_do_lai, 48.0, delta=0.01)

    def test_cong_gio_bo_qua_cuoi_tuan(self):
        # Thứ Sáu 17:00 + 16 giờ làm việc = Thứ Hai 09:00 (bỏ T7/CN).
        han = cong_gio_lam_viec("2026-08-07 17:00:00", 16)
        self.assertEqual(get_datetime(han).strftime("%Y-%m-%d %H:%M"), "2026-08-10 09:00")


# ---------------------------------------------------------------------------
# Email khách — BR-Y2 (đúng lý do), NL-11.3, xác nhận tạo
# ---------------------------------------------------------------------------

class TestEmailYeuCau(FrappeTestCase):
    def test_email_khong_dap_ung_mang_dung_ly_do(self):  # BR-Y2
        n = frappe.get_doc("Notification", "Portal - Yêu cầu không đáp ứng được")
        self.assertIn("ly_do_khong_dap_ung", n.message)
        self.assertEqual(n.document_type, "Portal Item Request")
        self.assertEqual(n.value_changed, "trang_thai")
        self.assertEqual(n.recipients[0].receiver_by_document_field, "nguoi_yeu_cau")
        self.assertTrue(n.enabled)

    def test_email_khong_dap_ung_render_that_mang_dung_ly_do(self):  # TC-E6-08
        """P2 #4 (kiểm thử hệ thống): test trên chỉ kiểm MÃ NGUỒN template —
        `"ly_do_khong_dap_ung" in n.message` khớp bất kể mã đó có được render
        thành CHỮ LÝ DO THẬT trong thư hay không. Render thật (chuyển
        trang_thai bằng `.save()` thật, kích hoạt Notification Value Change),
        đọc Email Queue, khẳng định đúng câu lý do khách/sales đã nhập có
        mặt. Khuôn theo test_e6_mua_le.py::TestJobBaoGiaHetHan.test_gui_email_hai_phia."""
        seed_demo()
        frappe.flags.mute_emails = True
        self.addCleanup(frappe.flags.pop, "mute_emails", None)

        doc = _tao_yeu_cau(CUSTOMER_BM)
        doc.trang_thai = "Đang tìm nguồn"
        doc.save(ignore_permissions=True)

        frappe.db.delete("Email Queue", {"reference_name": doc.name})

        ly_do = "Không tìm được nguồn hàng phù hợp (mã đối chiếu ĐC-E608)."
        doc.trang_thai = "Không đáp ứng được"
        doc.ly_do_khong_dap_ung = ly_do
        doc.save(ignore_permissions=True)  # transition THẬT -> Notification chạy

        hang_doi = frappe.get_all(
            "Email Queue", filters={"reference_name": doc.name}, pluck="name",
        )
        self.assertTrue(
            hang_doi,
            "Notification 'Portal - Yêu cầu không đáp ứng được' phải queue "
            "được ít nhất một email khi trang_thai chuyển sang Không đáp ứng được",
        )
        noi_dung = "\n".join(
            _van_ban_thuan_tuy_email(frappe.db.get_value("Email Queue", r, "message") or "")
            for r in hang_doi
        )
        self.assertIn(
            ly_do, noi_dung,
            "thư PHẢI mang đúng CHỮ lý do đã nhập, không chỉ tên field",
        )

        nguoi_nhan = set(frappe.get_all(
            "Email Queue Recipient", filters={"parent": ["in", hang_doi]}, pluck="recipient",
        ))
        self.assertIn(BM_USER, nguoi_nhan, "khách (nguoi_yeu_cau) phải nhận được thư")

    def test_email_xac_nhan_tao_moi(self):
        n = frappe.get_doc("Notification", "Portal - Yêu cầu hàng hoá đã ghi nhận")
        self.assertEqual(n.event, "New")
        self.assertEqual(n.recipients[0].receiver_by_document_field, "nguoi_yeu_cau")

    def test_email_can_them_thong_tin(self):  # NL-11.3
        n = frappe.get_doc("Notification", "Portal - Yêu cầu cần thêm thông tin")
        self.assertEqual(n.value_changed, "trang_thai")
        self.assertIn("Cần thêm thông tin", n.condition)
        self.assertEqual(n.recipients[0].receiver_by_document_field, "nguoi_yeu_cau")


# ---------------------------------------------------------------------------
# Report Desk — US-E6.6/UC-53
# ---------------------------------------------------------------------------

class TestDemandPipelineReport(FrappeTestCase):
    REPORT = "Demand pipeline yêu cầu hàng hoá"

    def test_bao_cao_ton_tai_va_chay_duoc(self):
        from frappe.desk.query_report import run
        self.assertTrue(frappe.db.exists("Report", self.REPORT))
        kq = run(self.REPORT, ignore_prepared_report=True)
        self.assertIn("columns", kq)

    def test_bao_cao_khong_danh_cho_customer(self):
        roles = frappe.get_all(
            "Has Role", filters={"parent": self.REPORT, "parenttype": "Report"},
            pluck="role",
        )
        self.assertNotIn("Customer", roles)
        self.assertTrue(roles)
        for r in ("Sales Manager", "Sales User", "Purchase User"):
            self.assertIn(r, roles)

    def test_ty_le_chuyen_thanh_don_tinh_dung(self):
        rows = [
            {"trang_thai": "Đã chuyển thành đơn", "ket_thuc": 1, "da_chuyen_don": 1,
             "tan_suat": "Một lần", "thoi_gian_xu_ly_gio": 10.0},
            {"trang_thai": "Không đáp ứng được", "ket_thuc": 1, "da_chuyen_don": 0,
             "tan_suat": "Một lần", "thoi_gian_xu_ly_gio": 20.0},
            {"trang_thai": "Mới", "ket_thuc": 0, "da_chuyen_don": 0,
             "tan_suat": "Một lần", "thoi_gian_xu_ly_gio": None},
        ]
        tt = demand_pipeline.tom_tat(rows)
        self.assertEqual(tt["tong"], 3)
        self.assertEqual(tt["ket_thuc"], 2)
        self.assertEqual(tt["chuyen_don"], 1)
        # Mẫu số CHỈ gồm kết thúc (2), KHÔNG gồm "Mới" (3) — 1/2 = 50%.
        self.assertEqual(tt["ty_le_chuyen_don"], 50.0)
        self.assertEqual(tt["thoi_gian_xu_ly_binh_quan_gio"], 15.0)

    def test_nhom_dinh_ky_tach_rieng(self):  # NL-11.7
        rows = [
            {"trang_thai": "Đã chuyển thành đơn", "ket_thuc": 1, "da_chuyen_don": 1,
             "tan_suat": "Định kỳ", "thoi_gian_xu_ly_gio": 5.0},
            {"trang_thai": "Không đáp ứng được", "ket_thuc": 1, "da_chuyen_don": 0,
             "tan_suat": "Định kỳ", "thoi_gian_xu_ly_gio": 5.0},
            {"trang_thai": "Đã chuyển thành đơn", "ket_thuc": 1, "da_chuyen_don": 1,
             "tan_suat": "Một lần", "thoi_gian_xu_ly_gio": 5.0},
        ]
        tt = demand_pipeline.tom_tat(rows)
        self.assertEqual(tt["dinh_ky_tong"], 2)
        self.assertEqual(tt["dinh_ky_ket_thuc"], 2)
        self.assertEqual(tt["dinh_ky_chuyen_don"], 1)
        self.assertEqual(tt["dinh_ky_ty_le_chuyen_don"], 50.0)
        # Tổng thể (gộp cả định kỳ lẫn một lần) là 2/3 chuyển đơn — khác hẳn
        # con số riêng của nhóm Định kỳ, chứng minh hai nhóm KHÔNG bị trộn.
        self.assertAlmostEqual(tt["ty_le_chuyen_don"], 66.7, delta=0.1)

    def test_yeu_cau_rows_loc_theo_khach(self):
        seed_demo()
        frappe.db.delete("Portal Item Request", {"customer": ["in", [CUSTOMER_BM, CUSTOMER_PXN]]})
        _tao_yeu_cau(CUSTOMER_BM, ten_hang="Hàng của BM")
        _tao_yeu_cau(CUSTOMER_PXN, ten_hang="Hàng của PXN")
        rows = demand_pipeline.yeu_cau_rows(customer=CUSTOMER_BM)
        self.assertTrue(all(r["customer"] == CUSTOMER_BM for r in rows))

    def test_trang_thai_ket_thuc_dung_chung_mot_nguon(self):  # F-6
        """Không được có bản sao thứ hai của tuple này — xem docstring
        demand_pipeline.py. Một trạng thái kết thúc thứ năm thêm vào
        controller mà quên sửa nơi khác sẽ tự động lệch nếu có hai bản độc
        lập; import chung một object thì không có gì để lệch."""
        from miyano_portal.miyano_portal.doctype.portal_item_request.portal_item_request import (
            TRANG_THAI_KET_THUC as tu_controller,
        )
        self.assertIs(demand_pipeline.TRANG_THAI_KET_THUC, tu_controller)

    def test_yeu_cau_rows_gan_nhan_va_thoi_gian_xu_ly_dung(self):  # F-6
        """End-to-end trên bản ghi THẬT (không dựng dict tay như hai test
        trên) — phủ đúng phần `yeu_cau_rows()` gán nhãn `ket_thuc`/
        `da_chuyen_don`/`thoi_gian_xu_ly_gio` mà trước bản vá không có test
        nào chạm tới."""
        seed_demo()
        frappe.db.delete(
            "Portal Item Request",
            {"customer": CUSTOMER_BM, "ten_hang": ("like", "F6 demand%")},
        )

        con_mo = _tao_yeu_cau(CUSTOMER_BM, ten_hang="F6 demand - con mo")

        khong_dap_ung = _tao_yeu_cau(CUSTOMER_BM, ten_hang="F6 demand - khong dap ung")
        frappe.db.sql(
            "update `tabPortal Item Request` set creation=%s where name=%s",
            ("2026-08-01 08:00:00", khong_dap_ung.name),
        )
        khong_dap_ung.reload()
        khong_dap_ung.trang_thai = "Đang tìm nguồn"
        khong_dap_ung.save(ignore_permissions=True)
        khong_dap_ung.trang_thai = "Không đáp ứng được"
        khong_dap_ung.ly_do_khong_dap_ung = "Không tìm được nguồn."
        khong_dap_ung.save(ignore_permissions=True)

        chuyen_don = _tao_yeu_cau(CUSTOMER_BM, ten_hang="F6 demand - chuyen don")
        frappe.db.sql(
            "update `tabPortal Item Request` set creation=%s where name=%s",
            ("2026-08-01 08:00:00", chuyen_don.name),
        )
        chuyen_don.reload()
        chuyen_don.trang_thai = "Đang tìm nguồn"
        chuyen_don.save(ignore_permissions=True)
        chuyen_don.trang_thai = "Đã báo giá"
        chuyen_don.save(ignore_permissions=True)
        chuyen_don.trang_thai = "Đã chuyển thành đơn"
        chuyen_don.save(ignore_permissions=True)

        by_name = {
            r["name"]: r
            for r in demand_pipeline.yeu_cau_rows(customer=CUSTOMER_BM)
        }

        r_mo = by_name[con_mo.name]
        self.assertEqual(r_mo["ket_thuc"], 0)
        self.assertEqual(r_mo["da_chuyen_don"], 0)
        self.assertIsNone(r_mo["thoi_gian_xu_ly_gio"])

        r_kdu = by_name[khong_dap_ung.name]
        self.assertEqual(r_kdu["ket_thuc"], 1)
        self.assertEqual(r_kdu["da_chuyen_don"], 0)
        self.assertGreater(r_kdu["thoi_gian_xu_ly_gio"], 0)

        r_cd = by_name[chuyen_don.name]
        self.assertEqual(r_cd["ket_thuc"], 1)
        self.assertEqual(r_cd["da_chuyen_don"], 1)
        self.assertGreater(r_cd["thoi_gian_xu_ly_gio"], 0)
