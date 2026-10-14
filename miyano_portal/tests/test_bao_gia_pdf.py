"""Spec 2026-08-15 §3.6 — PDF báo giá, nay là PDF của Quotation.

Ba thứ được bảo vệ ở đây, theo thứ tự quan trọng: KHÔNG lộ báo giá của khách
khác; KHÔNG lộ giá Miyano chưa gửi; và bản báo giá phải ĐỦ — thiếu dòng gõ
tay đã khớp mã là khách nhận báo giá thiếu đúng món họ lo nhất.

Patch v1_44 bỏ vòng báo giá trên Sales Order cùng mẫu in "Miyano - Báo giá"
của đơn: tải PDF theo đơn nhận một lời từ chối rõ ràng.
"""

from unittest.mock import patch

import frappe
from frappe.model.workflow import apply_workflow

from miyano_portal import bao_gia, dat_hang
from miyano_portal.api import portal
from miyano_portal.portal_mua_le import ITEM_GIU_CHO
from miyano_portal.setup.install_print_formats import NAME_YCBG
from miyano_portal.tests.nen_bao_gia import NenBaoGia

MAU_IN_DON_CU = "Miyano - Báo giá"
THONG_BAO_DON_CU = "Portal - Báo giá sẵn sàng"
DONG_GO_TAY = {"ten_hang": "Găng tay nitrile size M", "dvt": "Hộp", "so_luong": 2}


class TestBaoGiaPdf(NenBaoGia):
	def setUp(self):
		super().setUp()
		self.ql_a = self._quan_ly("bgpdf.ql.a@demo.miyano", self.kh_a)
		self.ql_b = self._quan_ly("bgpdf.ql.b@demo.miyano", self.kh_b)

	def tearDown(self):
		super().tearDown()
		frappe.local.response.pop("filecontent", None)

	def _goi(self, user, ham, *a, **kw):
		frappe.set_user(user)
		try:
			return ham(*a, **kw)
		finally:
			frappe.set_user("Administrator")

	def _bao_gia(self, items, dat_ngoai=None):
		kq = bao_gia.tao_bao_gia(
			self.kh_a, items=items, dat_ngoai=dat_ngoai or [],
			request_id=frappe.generate_hash(length=12), khoa_phong=self.khoa_huyethoc,
		)
		return frappe.get_doc("Quotation", kq["bao_gia"])

	def _bao_gia_da_gui(self):
		"""3 `item_ngoai` (bảng giá 54.000) cộng một dòng gõ tay 2 đơn vị mà
		Miyano khớp về CHÍNH mã đó, rồi gửi khách."""
		bg = self._bao_gia([{"item_code": self.item_ngoai, "qty": 3}], [DONG_GO_TAY])
		bg.custom_dat_ngoai[0].item_khop = self.item_ngoai
		bg.save()
		return apply_workflow(bg, bao_gia.HD_GUI_KHACH)

	def _html(self, bg):
		return frappe.get_print("Quotation", bg.name, print_format=NAME_YCBG, no_letterhead=1)

	def test_mau_in_bao_gia_cua_don_da_bo(self):
		self.assertFalse(frappe.db.exists("Print Format", MAU_IN_DON_CU))
		self.assertFalse(frappe.db.exists("Notification", THONG_BAO_DON_CU))
		self.assertEqual(frappe.db.get_value("Print Format", NAME_YCBG, "doc_type"), "Quotation")

	def test_tai_theo_don_hang_bi_tu_choi_ro_rang(self):
		"""Đơn của CHÍNH khách, kể cả đơn "Mua lẻ" cũ: không còn PDF báo giá
		theo đơn. Lời từ chối là ValidationError, không phải lời "không thấy"
		của chốt quyền — đơn vẫn là của khách."""
		kq = dat_hang.tao_sales_order(
			self.kh_a, items=[{"item_code": self.item_boi_so, "qty": 20}],
			request_id=frappe.generate_hash(length=12),
		)
		with self.assertRaises(frappe.ValidationError) as cm:
			self._goi(self.ql_a, portal.portal_bao_gia_pdf, order=kq["sales_order"])
		self.assertNotIsInstance(cm.exception, frappe.PermissionError)
		self.assertFalse(frappe.local.response.get("filecontent"))

	def test_pdf_chua_dong_go_tay_da_khop_ma(self):
		bg = self._bao_gia_da_gui()
		html = self._html(bg)
		self.assertIn("Găng tay nitrile size M", html)
		self.assertIn(self.item_ngoai, html)

	def test_pdf_gop_dong_khop_ma_va_dung_dau_cham_phan_nhom(self):
		"""Dòng gõ tay khớp về mã đã có trên báo giá được GỘP vào dòng sẵn có:
		(3 + 2) × 54.000 = 270.000 ₫, phân nhóm bằng dấu CHẤM."""
		bg = self._bao_gia_da_gui()
		self.assertEqual([(d.item_code, d.qty) for d in bg.items], [(self.item_ngoai, 5)])
		html = self._html(bg)
		self.assertIn("270.000 ₫", html)
		self.assertNotIn("270,000", html)

	def test_pdf_khong_chua_dong_giu_cho(self):
		bg = self._bao_gia([], [DONG_GO_TAY])
		self.assertIn(ITEM_GIU_CHO, [d.item_code for d in bg.items])
		self.assertNotIn(ITEM_GIU_CHO, self._html(bg))

	def test_khach_khac_khong_tai_duoc(self):
		bg = self._bao_gia_da_gui()
		with self.assertRaises(frappe.PermissionError):
			self._goi(self.ql_b, portal.portal_bao_gia_pdf, quotation=bg.name)

	def test_bao_gia_chua_gui_khach_thi_khong_tai_duoc(self):
		"""Báo giá còn ở "Chờ Miyano báo giá" = Miyano chưa chốt giá. Cho tải
		là lộ giá nháp và biến một con số đang sửa thành cam kết với khách."""
		bg = self._bao_gia([{"item_code": self.item_ngoai, "qty": 3}])
		with self.assertRaises(frappe.ValidationError):
			self._goi(self.ql_a, portal.portal_bao_gia_pdf, quotation=bg.name)

	def test_chinh_khach_tai_duoc_bao_gia_da_gui(self):
		bg = self._bao_gia_da_gui()
		with patch("frappe.utils.pdf.get_pdf", return_value=b"%PDF-fake"):
			self._goi(self.ql_a, portal.portal_bao_gia_pdf, quotation=bg.name)
		self.assertEqual(frappe.local.response.filecontent, b"%PDF-fake")
		self.assertEqual(frappe.local.response.filename, f"BaoGia-{bg.name}.pdf")
