"""Cách ly Quotation (spec 2026-10-12 §8). Thiếu một chốt là lộ báo giá của
bệnh viện này sang bệnh viện khác."""

import frappe

from miyano_portal import permissions, rest_guard, search_guard
from miyano_portal.portal_context import dam_bao_xem_duoc
from miyano_portal.tests import test_rest_guard as rg
from miyano_portal.tests.nen_bao_gia import NenBaoGia


class TestBaoGiaCachLy(NenBaoGia):
	def setUp(self):
		super().setUp()
		self.bg_a = self._bao_gia_tho(khoa=self.khoa_huyethoc)
		self.ql_a = self._quan_ly("bgcl.ql.a@demo.miyano", self.kh_a)

	def _them_portal_user(self, user, khach):
		"""Dòng `Portal User` là thứ khiến chốt trang web của ERPNext cho qua."""
		kh = frappe.get_doc("Customer", khach)
		kh.append("portal_users", {"user": user})
		kh.save(ignore_permissions=True)

	def test_vai_customer_khong_co_docperm(self):
		quyen = frappe.get_all(
			"DocPerm", filters={"parent": "Quotation", "role": "Customer"}
		) + frappe.get_all(
			"Custom DocPerm", filters={"parent": "Quotation", "role": "Customer"}
		)
		self.assertEqual(quyen, [])

	def test_doc_chung_bi_tu_choi_ke_ca_dung_khach(self):
		frappe.set_user(self.ql_a)
		self.assertFalse(frappe.has_permission("Quotation", "read", doc=self.bg_a))
		with self.assertRaises(frappe.PermissionError):
			frappe.get_list("Quotation", fields=["name"])
		with self.assertRaises(frappe.PermissionError):
			search_guard.client_get("Quotation", self.bg_a.name)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc("Quotation", self.bg_a.name).check_permission("read")

	def test_make_sales_order_bi_tu_choi(self):
		from erpnext.selling.doctype.quotation.quotation import make_sales_order

		frappe.set_user(self.ql_a)
		with self.assertRaises(frappe.PermissionError):
			make_sales_order(self.bg_a.name)

	def test_run_doc_method_bi_tu_choi(self):
		from frappe.handler import run_doc_method

		frappe.set_user(self.ql_a)
		with self.assertRaises(frappe.PermissionError):
			run_doc_method("declare_enquiry_lost", dt="Quotation", dn=self.bg_a.name)

	def test_trang_web_erpnext_bi_chan(self):
		"""Review Focus 5."""
		self._them_portal_user(self.ql_a, self.kh_a)
		frappe.set_user(self.ql_a)
		self.assertFalse(frappe.has_website_permission(self.bg_a))

	def test_nhan_vien_noi_bo_van_qua_chot_trang_web(self):
		self.assertTrue(permissions.bao_gia_khong_qua_trang_web(self.bg_a, user="Administrator"))

	def test_lop_hai_khach_khac_khong_thay(self):
		self.assertFalse(permissions.bao_gia_has_permission(self.bg_a, user=self.user_b))
		self.assertTrue(permissions.bao_gia_has_permission(self.bg_a, user=self.ql_a))

	def test_lop_hai_khoa_khac_khong_thay(self):
		nv_duoc_a = self._dam_bao_thanh_vien(
			"bgcl.duoc.a@demo.miyano", self.kh_a, "Nhân viên khoa", self._khoa_khac_cua_a()
		)
		self.assertFalse(permissions.bao_gia_has_permission(self.bg_a, user=nv_duoc_a))
		self.assertTrue(permissions.bao_gia_has_permission(self.bg_a, user=self.user_a))

	def test_lop_hai_bao_gia_noi_bo_khong_hien(self):
		noi_bo = self._bao_gia_tho(nguon="Nội bộ")
		self.assertFalse(permissions.bao_gia_has_permission(noi_bo, user=self.ql_a))

	def test_dieu_kien_truy_van(self):
		dk = permissions.bao_gia_query(self.user_a)
		self.assertIn("`tabQuotation`.`party_name` in", dk)
		self.assertIn("'Client Portal'", dk)
		self.assertIn("`tabQuotation`.`custom_khoa_phong` =", dk)
		self.assertEqual(permissions.bao_gia_query("Administrator"), "")
		self.assertNotIn("custom_khoa_phong", permissions.bao_gia_query(self.ql_a))

	def test_dam_bao_xem_duoc_theo_khoa(self):
		dam_bao_xem_duoc("Quotation", self.bg_a.name, user=self.user_a)
		nv_duoc_a = self._dam_bao_thanh_vien(
			"bgcl.duoc.a@demo.miyano", self.kh_a, "Nhân viên khoa", self._khoa_khac_cua_a()
		)
		with self.assertRaises(frappe.PermissionError):
			dam_bao_xem_duoc("Quotation", self.bg_a.name, user=nv_duoc_a)

	def _khoa_khac_cua_a(self):
		ten = frappe.db.get_value(
			"Customer Department", {"customer": self.kh_a, "ma_khoa": "BGCL"}, "name"
		)
		if ten:
			return ten
		return frappe.get_doc({
			"doctype": "Customer Department", "customer": self.kh_a,
			"ten_khoa_phong": "Khoa thử cách ly báo giá", "ma_khoa": "BGCL", "active": 1,
		}).insert(ignore_permissions=True).name


class TestChanTrangBaoGiaErpnext(NenBaoGia):
	"""Chạy trong tiến trình test, không cần tiến trình web nên không bao giờ skip.

	Bộ định tuyến Frappe (`PathResolver`) `strip("/ ")` hai đầu, bỏ đuôi `.html`
	rồi so khớp phân biệt hoa thường: guard phải chuẩn hoá y hệt.
	"""

	CHAN = (
		"/quotations", "/quotations/", "/quotations.html", "/quotations.html/",
		"//quotations", "/quotations ", "/quotations/SAL-QTN-1",
		"/quotations/SAL-QTN-1.html",
	)
	MO = ("/portal/yeu-cau", "/quotations-khac", "/api/method/ping")

	def _goi(self, duong_dan, user):
		frappe.set_user(user)
		old = getattr(frappe.local, "request", None)
		frappe.local.request = frappe._dict(path=duong_dan)
		try:
			rest_guard.chan_trang_bao_gia_erpnext()
		finally:
			frappe.local.request = old

	def test_khach_cong_bi_chan_moi_bien_the(self):
		ql = self._quan_ly("bgcl.ql.chan@demo.miyano", self.kh_a)
		for duong_dan in self.CHAN:
			with self.subTest(duong_dan=duong_dan):
				with self.assertRaises(frappe.PermissionError):
					self._goi(duong_dan, ql)

	def test_duong_khac_van_mo(self):
		ql = self._quan_ly("bgcl.ql.chan@demo.miyano", self.kh_a)
		for duong_dan in self.MO:
			with self.subTest(duong_dan=duong_dan):
				self._goi(duong_dan, ql)

	def test_nhan_vien_noi_bo_khong_bi_chan(self):
		self._goi("/quotations", "Administrator")


class TestBaoGiaHTTP(NenBaoGia):
	"""Đăng nhập thật: `before_request` chỉ chạy trên request thật."""

	def setUp(self):
		super().setUp()
		self.session = rg._login_bvbm()
		if self.session is None:
			self.skipTest("bench không phản hồi trên loopback")

	def _get(self, duong_dan):
		return self.session.get(f"{rg.BASE_URL}{duong_dan}", timeout=30, allow_redirects=False)

	def test_danh_sach_bao_gia_erpnext_bi_chan(self):
		self.assertEqual(self._get("/quotations").status_code, 403)

	def test_chi_tiet_bao_gia_erpnext_bi_chan(self):
		self.assertEqual(self._get("/quotations/SAL-QTN-KHONG-CO").status_code, 403)

	def test_trang_cong_van_mo(self):
		self.assertEqual(self._get("/portal/yeu-cau").status_code, 200)
