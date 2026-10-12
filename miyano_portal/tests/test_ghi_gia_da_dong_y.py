"""Ghi giá khách đã đồng ý vào Price List (spec 2026-10-09 §5.2)."""

from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.model.workflow import apply_workflow
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, today

from miyano_portal import bang_gia_khach as bg
from miyano_portal import dat_hang
from miyano_portal.api import portal
from miyano_portal.tests import test_catalog_gop as goc


class TestGhiGiaDaDongY(FrappeTestCase):
	def setUp(self):
		goc.TestPortalCatalogGop.setUp(self)
		for ma in (self.item_ngoai, self.item_boi_so):
			for ten in frappe.get_all(
				"Item Price", filters={"item_code": ma, "selling": 1}, pluck="name"
			):
				frappe.delete_doc("Item Price", ten, force=True)
		self.quan_ly = self._dam_bao_thanh_vien(
			"ghigia.ql@demo.miyano", self.kh_a, "Quản lý", None
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _don_cho_khach(self, ma, rate):
		kq = dat_hang.tao_sales_order(
			self.kh_a, items=[{"item_code": ma, "qty": 10}],
			request_id=frappe.generate_hash(length=12),
		)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		so.items[0].rate = rate
		so.save()
		return apply_workflow(so, "Gửi khách duyệt")

	def _khach(self, so, action, **them):
		frappe.set_user(self.quan_ly)
		try:
			return portal.portal_order_accept(so.name, action, **them)
		finally:
			frappe.set_user("Administrator")

	def _dong_gia(self, ma, bang, rate, **them):
		"""Chèn thẳng một dòng Item Price (kể cả dòng gắn khách / có hạn)."""
		return frappe.get_doc({
			"doctype": "Item Price", "item_code": ma, "price_list": bang,
			"selling": 1, "price_list_rate": rate, **them,
		}).insert(ignore_permissions=True)

	def test_dong_y_tao_dong_gia_moi(self):
		so = self._don_cho_khach(self.item_boi_so, 7000)
		self._khach(so, "dong_y")
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 7000.0)

	def test_dong_y_cap_nhat_dong_gia_cu_khong_tao_dong_thu_hai(self):
		so = self._don_cho_khach(self.item_boi_so, 7000)
		# Giá xuất hiện SAU khi đơn đã tạo ở tầng chờ báo giá.
		self._tao_gia(self.item_boi_so, self.price_list, 5000)
		self._khach(so, "dong_y")
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 7000.0)
		bang = frappe.db.get_value("Customer", self.kh_a, "default_price_list")
		self.assertEqual(frappe.db.count("Item Price", {
			"item_code": self.item_boi_so, "price_list": bang, "selling": 1,
		}), 1)

	def test_dong_y_co_ca_dong_rieng_khach_va_dong_chung(self):
		"""Bảng của khách có cả dòng gắn riêng khách lẫn dòng chung: bộ đọc ưu tiên
		dòng riêng, nên bộ ghi phải sửa đúng dòng đó — đọc lại ra giá vừa đồng ý."""
		so = self._don_cho_khach(self.item_boi_so, 7000)
		bang = bg.dam_bao_bang_gia_rieng(self.kh_a)
		self._dong_gia(self.item_boi_so, bang, 4000, customer=self.kh_a)
		self._dong_gia(self.item_boi_so, bang, 5000)
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 4000.0)
		self._khach(so, "dong_y")
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 7000.0)
		self.assertEqual(frappe.db.count("Item Price", {
			"item_code": self.item_boi_so, "price_list": bang, "selling": 1,
		}), 2)

	def test_dong_y_khi_dong_gia_da_het_han(self):
		"""Dòng cũ đã hết hạn: không được ném lỗi trùng khoá, và đọc lại ra giá mới."""
		so = self._don_cho_khach(self.item_boi_so, 7000)
		bang = bg.dam_bao_bang_gia_rieng(self.kh_a)
		self._dong_gia(self.item_boi_so, bang, 3000,
		               valid_from=add_days(today(), -30), valid_upto=add_days(today(), -1))
		self.assertIsNone(bg.gia_bang_gia(self.kh_a, self.item_boi_so))
		self._khach(so, "dong_y")
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 7000.0)

	def test_dong_y_khi_dong_gia_chua_co_hieu_luc(self):
		so = self._don_cho_khach(self.item_boi_so, 7000)
		bang = bg.dam_bao_bang_gia_rieng(self.kh_a)
		self._dong_gia(self.item_boi_so, bang, 3000, valid_from=add_days(today(), 10))
		self._khach(so, "dong_y")
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 7000.0)

	def test_dong_y_dong_dau_gia_khach_dong_y_tren_dong_don(self):
		so = self._don_cho_khach(self.item_boi_so, 7000)
		self._khach(so, "dong_y")
		self.assertEqual(float(frappe.db.get_value(
			"Sales Order Item", so.items[0].name, "custom_gia_khach_dong_y")), 7000.0)

	def test_khong_dong_y_khong_ghi_gi(self):
		so = self._don_cho_khach(self.item_boi_so, 7000)
		self._khach(so, "khong_dong_y", ly_do="Giá cao hơn nhà cung cấp hiện tại")
		self.assertIsNone(bg.gia_bang_gia(self.kh_a, self.item_boi_so))

	def test_quy_doi_ve_don_vi_goc(self):
		so = self._don_cho_khach(self.item_boi_so, 7000)
		# Dòng đặt theo thùng (1 thùng = 10 đơn vị gốc): nếu chỉ ép
		# `conversion_factor` bằng SQL thì lần lưu của workflow đặt lại về 1,
		# nên phải khai báo quy đổi thật trên Item.
		thung = "Box" if frappe.db.get_value("Item", self.item_boi_so, "stock_uom") != "Box" else "Nos"
		item = frappe.get_doc("Item", self.item_boi_so)
		item.append("uoms", {"uom": thung, "conversion_factor": 10})
		item.save(ignore_permissions=True)
		frappe.db.set_value("Sales Order Item", so.items[0].name,
		                    {"uom": thung, "conversion_factor": 10, "rate": 70000})
		self._khach(so, "dong_y")
		self.assertEqual(float(frappe.db.get_value(
			"Sales Order Item", so.items[0].name, "conversion_factor")), 10.0)
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 7000.0)

	def test_khong_ghi_dong_bang_gia(self):
		self._tao_gia(self.item_ngoai, self.price_list, 54000)
		kq = dat_hang.tao_sales_order(
			self.kh_a,
			items=[{"item_code": self.item_ngoai, "qty": 1}],
			dat_ngoai=[{"ten_hang": "Kim X", "dvt": "Cái", "so_luong": 1,
			            "khong_co_anh": 1}],
			request_id=frappe.generate_hash(length=12),
		)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(
			[d for d in bg.ghi_gia_da_dong_y(so) if d["item_code"] == self.item_ngoai], []
		)

	def test_de_lai_dau_vet_tren_don(self):
		so = self._don_cho_khach(self.item_boi_so, 7000)
		self._khach(so, "dong_y")
		noi_dung = " ".join(frappe.get_all(
			"Comment", filters={"reference_doctype": "Sales Order",
			                    "reference_name": so.name}, pluck="content"))
		self.assertIn(self.item_boi_so, noi_dung)
		self.assertIn("7.000", noi_dung.replace(",", "."))
		self.assertIn(self.quan_ly, noi_dung)  # ai đồng ý

	def test_loi_ghi_gia_khong_lam_hong_viec_dong_y(self):
		so = self._don_cho_khach(self.item_boi_so, 7000)
		with patch.object(bg, "ghi_gia_da_dong_y", side_effect=RuntimeError("hong")):
			kq = self._khach(so, "dong_y")
		self.assertEqual(kq["trang_thai_moi"], "Chờ Miyano xác nhận")
		self.assertTrue(frappe.db.exists("Error Log", {
			"reference_doctype": "Sales Order", "reference_name": so.name,
		}))
		frappe.db.delete("Error Log", {"reference_name": so.name})

	def test_loi_ghi_gia_bao_nhan_vien_phu_trach(self):
		sales = "ghigia.sales@demo.miyano"
		if not frappe.db.exists("User", sales):
			frappe.get_doc({"doctype": "User", "email": sales, "first_name": "ghigiasales",
			                "send_welcome_email": 0}).insert(ignore_permissions=True)
		frappe.db.set_value("Customer", self.kh_a, "account_manager", sales)
		so = self._don_cho_khach(self.item_boi_so, 7000)
		with patch.object(bg, "ghi_gia_da_dong_y", side_effect=RuntimeError("hong")):
			self._khach(so, "dong_y")
		thong_bao = frappe.get_all("Notification Log", filters={"for_user": sales},
		                           fields=["subject", "email_content"])
		self.assertTrue(any(so.name in (t.subject or "") for t in thong_bao), thong_bao)
		frappe.db.delete("Error Log", {"reference_name": so.name})

	def test_chot_3_chan_khi_nhan_vien_sua_gia_sau_khi_khach_dong_y(self):
		so = self._don_cho_khach(self.item_boi_so, 7000)
		self._khach(so, "dong_y")
		so.reload()
		self.assertEqual(flt_(so.items[0].custom_gia_khach_dong_y), 7000.0)
		so.items[0].rate = 9000
		with self.assertRaises(frappe.ValidationError) as ctx:
			so.submit()
		self.assertIn("gửi khách duyệt lại", str(ctx.exception))

	def test_chot_3_cho_qua_khi_gia_giu_nguyen(self):
		so = self._don_cho_khach(self.item_boi_so, 7000)
		self._khach(so, "dong_y")
		so.reload()
		so = apply_workflow(so, "Xác nhận")
		self.assertEqual(so.docstatus, 1)


def flt_(v):
	return float(v or 0)


for _ten, _ham in vars(goc.TestPortalCatalogGop).items():
	if _ten.startswith("_") and not _ten.startswith("__") and callable(_ham):
		if _ten not in vars(TestGhiGiaDaDongY):
			setattr(TestGhiGiaDaDongY, _ten, _ham)
