"""E7b — submit Sales Invoice thì tự lập HĐĐT từ từng phiếu giao.

KHÔNG gọi mạng: `actions.preview_draft` nhận tham số `client`, nên test tiêm
một `FastClient` dùng `FakeTransport` của chính module HĐĐT
(`erpnext/einvoice/test_fast_client.py`) thay vì monkeypatch tầng HTTP.

Ranh giới quan trọng nhất mà bộ test này canh giữ: job DỪNG ở `02 - Đã xem
nháp`. Không bao giờ tự gửi email cho khách — kế toán phải được liếc bản nháp
trước khi nó vào hộp thư khách hàng (quyết định Q1 của spec). Khách vẫn xem
được ngay trên cổng nên không ai phải chờ email.
"""

import base64
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.einvoice.fast_client import FastClient
from erpnext.einvoice.test_fast_client import FakeTransport, checkkey_ok, configure, envelope
from erpnext.einvoice.test_fixtures import make_delivery_note, minimal_pdf_bytes

from miyano_portal import hddt_tu_dong

FEI = "Fast EInvoice Document"


def pdf_response():
    return envelope(1, base64.b64encode(minimal_pdf_bytes()).decode())


class _TuDongFixture(FrappeTestCase):
    def setUp(self):
        frappe.db.rollback()
        configure(token="TOKEN-E7B", token_time=frappe.utils.now_datetime())

    def tearDown(self):
        frappe.db.rollback()

    def _client(self, so_lan=1):
        """FastClient giả trả `so_lan` phản hồi PDF — một cho mỗi phiếu giao."""
        return FastClient(transport=FakeTransport(checkkey_ok(), *([pdf_response()] * so_lan)))

    def _si_tu_dn(self, dn_list):
        si = frappe.new_doc("Sales Invoice")
        si.company = dn_list[0].company
        si.customer = dn_list[0].customer
        si.posting_date = frappe.utils.today()
        si.set_posting_time = 1
        si.update_stock = 0
        for dn in dn_list:
            for d in dn.items:
                si.append("items", {
                    "item_code": d.item_code, "qty": d.qty, "rate": d.rate,
                    "delivery_note": dn.name, "dn_detail": d.name,
                })
        si.insert(ignore_permissions=True)
        si.submit()
        return si

    def _fei_cua(self, dn_name):
        return frappe.get_all(
            FEI, filters={"delivery_note": dn_name}, fields=["name", "status", "draft_pdf"]
        )


class TestLapTuDong(_TuDongFixture):
    def test_mot_phieu_giao_ra_mot_chung_tu_o_02(self):
        dn = make_delivery_note()
        si = self._si_tu_dn([dn])
        ket_qua = hddt_tu_dong.lap_hddt_cho_hoa_don(si.name, client=self._client())

        self.assertEqual(len(ket_qua["tao"]), 1)
        rows = self._fei_cua(dn.name)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status, "02 - Đã xem nháp")
        self.assertTrue(rows[0].draft_pdf, "phải có PDF do Fast dựng")

    def test_si_gop_nhieu_dot_giao_ra_nhieu_chung_tu(self):
        dn1, dn2 = make_delivery_note(), make_delivery_note()
        si = self._si_tu_dn([dn1, dn2])
        ket_qua = hddt_tu_dong.lap_hddt_cho_hoa_don(si.name, client=self._client(so_lan=2))

        self.assertEqual(len(ket_qua["tao"]), 2)
        self.assertEqual(len(self._fei_cua(dn1.name)), 1)
        self.assertEqual(len(self._fei_cua(dn2.name)), 1)

    def test_khong_bao_gio_tu_gui_email(self):
        """Ranh giới Q1. Trạng thái dừng ở 02 và `draft_sent_time` phải rỗng —
        03 chỉ đặt được bằng `send_draft_to_customer`, mà job không gọi."""
        dn = make_delivery_note()
        si = self._si_tu_dn([dn])
        hddt_tu_dong.lap_hddt_cho_hoa_don(si.name, client=self._client())

        fei = frappe.get_doc(FEI, self._fei_cua(dn.name)[0].name)
        self.assertEqual(fei.status, "02 - Đã xem nháp")
        self.assertFalse(fei.draft_sent_time)
        self.assertFalse(fei.draft_sent_to)

    def test_chay_lai_khong_lap_trung(self):
        dn = make_delivery_note()
        si = self._si_tu_dn([dn])
        hddt_tu_dong.lap_hddt_cho_hoa_don(si.name, client=self._client())
        lan_hai = hddt_tu_dong.lap_hddt_cho_hoa_don(si.name, client=self._client())

        self.assertEqual(len(self._fei_cua(dn.name)), 1)
        self.assertEqual(lan_hai["tao"], [])
        self.assertEqual(len(lan_hai["bo_qua"]), 1)

    def test_si_khong_qua_phieu_giao_thi_khong_tao_gi(self):
        dn = make_delivery_note()
        si = frappe.new_doc("Sales Invoice")
        si.company, si.customer = dn.company, dn.customer
        si.posting_date = frappe.utils.today()
        si.append("items", {"item_code": dn.items[0].item_code, "qty": 1, "rate": 1000})
        si.insert(ignore_permissions=True)
        si.submit()

        ket_qua = hddt_tu_dong.lap_hddt_cho_hoa_don(si.name, client=self._client())
        self.assertEqual(ket_qua["tao"], [])
        self.assertIn("phiếu giao", ket_qua["ly_do"])

    def test_ghi_comment_len_sales_invoice(self):
        """Comment là nơi DUY NHẤT kế toán biết job đã chạy hay chưa — chủ dự
        án đã chốt giữ Comment, không bắn Notification."""
        dn = make_delivery_note()
        si = self._si_tu_dn([dn])
        hddt_tu_dong.lap_hddt_cho_hoa_don(si.name, client=self._client())
        self.assertTrue(frappe.db.exists(
            "Comment", {"reference_doctype": "Sales Invoice", "reference_name": si.name}
        ))


class TestKhongLamVoSubmit(_TuDongFixture):
    def test_fast_tat_thi_submit_van_thanh_cong(self):
        frappe.db.set_single_value("Fast EInvoice Settings", "enabled", 0)
        dn = make_delivery_note()
        si = self._si_tu_dn([dn])          # submit KHÔNG được ném lỗi
        self.assertEqual(si.docstatus, 1)

        ket_qua = hddt_tu_dong.lap_hddt_cho_hoa_don(si.name, client=self._client())
        self.assertEqual(ket_qua["tao"], [])
        self.assertTrue(ket_qua["ly_do"])
        self.assertEqual(self._fei_cua(dn.name), [])

    def test_hook_nuot_loi_khong_chan_submit(self):
        dn = make_delivery_note()
        with patch.object(hddt_tu_dong.frappe, "enqueue", side_effect=Exception("hàng đợi chết")):
            si = self._si_tu_dn([dn])
        self.assertEqual(si.docstatus, 1)

    def test_si_tra_hang_khong_day_job(self):
        """Phiếu trả hàng bị `builder._load_delivery_note` từ chối thẳng
        ("dùng hóa đơn điều chỉnh giảm từ hóa đơn gốc"). Không lọc sớm thì
        mỗi giấy báo có là một Comment lỗi vô nghĩa.

        Kiểm THẲNG hàm hook với một doc giả thay vì dựng một giấy báo có
        thật: dựng credit note thật kéo theo `return_against`, số lượng âm và
        cả chuỗi validate của ERPNext — toàn thứ không liên quan đến điều ca
        này muốn khẳng định, và mỗi thứ là một cách để test đỏ vì lý do khác."""
        doc = frappe._dict(name="SI-TRA-TEST", is_return=1)
        with patch.object(hddt_tu_dong.frappe, "enqueue") as day_hang_doi:
            hddt_tu_dong.tu_sales_invoice(doc)
        day_hang_doi.assert_not_called()

    def test_hoa_don_khong_con_ton_tai_thi_job_im_lang(self):
        """Job chạy SAU `on_submit` vài giây tới vài phút; trong khoảng đó
        hoá đơn có thể đã bị xoá. Đo thật trên bench: thiếu chốt này thì mỗi
        lượt chạy test suite để lại 75 Error Log rác — worker nhặt job đã đẩy
        rồi không còn thấy Sales Invoice nào (test đã rollback giao dịch)."""
        ket_qua = hddt_tu_dong.lap_hddt_cho_hoa_don("SI-KHONG-TON-TAI-9999")
        self.assertEqual(ket_qua["tao"], [])
        self.assertIsNone(ket_qua["ly_do"])

    def test_si_thuong_thi_co_day_job(self):
        """Ca đối chứng của ca trên — nếu thiếu, một hàm `tu_sales_invoice`
        return sớm vô điều kiện cũng làm ca trên xanh."""
        doc = frappe._dict(name="SI-THUONG-TEST", is_return=0)
        with patch.object(hddt_tu_dong.frappe, "enqueue") as day_hang_doi:
            hddt_tu_dong.tu_sales_invoice(doc)
        day_hang_doi.assert_called_once()


class TestLoiTungPhieuKhongKeoTheoNhau(_TuDongFixture):
    def test_mot_phieu_hong_phieu_con_lai_van_chay(self):
        """Phiếu 1 đã có chứng từ HĐĐT sống → bỏ qua. Phiếu 2 vẫn phải ra
        chứng từ. Bọc lỗi phải nằm TRONG vòng lặp, không bọc cả vòng."""
        from erpnext.einvoice.builder import create_from_delivery_note

        dn1, dn2 = make_delivery_note(), make_delivery_note()
        create_from_delivery_note(dn1.name)          # dựng sẵn cho phiếu 1
        si = self._si_tu_dn([dn1, dn2])

        ket_qua = hddt_tu_dong.lap_hddt_cho_hoa_don(si.name, client=self._client())
        self.assertEqual(len(ket_qua["tao"]), 1)
        self.assertEqual(len(ket_qua["bo_qua"]), 1)
        self.assertEqual(ket_qua["bo_qua"][0]["delivery_note"], dn1.name)
        self.assertEqual(len(self._fei_cua(dn2.name)), 1)
