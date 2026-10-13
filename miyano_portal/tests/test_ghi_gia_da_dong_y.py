"""Ghi giá khách đã đồng ý vào Price List (spec 2026-10-09 §5.2)."""

from unittest.mock import patch

import frappe
from frappe.model.workflow import apply_workflow
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

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

	def _don_cho_khach_chua_gui(self, ma, rate):
		kq = dat_hang.tao_sales_order(
			self.kh_a, items=[{"item_code": ma, "qty": 10}],
			request_id=frappe.generate_hash(length=12),
		)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		so.items[0].rate = rate
		so.save()
		return so

	def _don_cho_khach(self, ma, rate):
		return apply_workflow(self._don_cho_khach_chua_gui(ma, rate), "Gửi khách duyệt")

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

	def _quy_doi(self, uom, he_so):
		item = frappe.get_doc("Item", self.item_boi_so)
		dong = [u for u in item.uoms if u.uom == uom]
		if dong:
			dong[0].conversion_factor = he_so
		else:
			item.append("uoms", {"uom": uom, "conversion_factor": he_so})
		item.save(ignore_permissions=True)

	def _dong(self, ten):
		return frappe.db.get_value(
			"Item Price", ten, ["price_list_rate", "valid_from", "valid_upto"], as_dict=True)

	def test_dong_y_khi_dong_gia_da_het_han(self):
		"""Chỉ có dòng hết hạn: để nguyên nó, chèn dòng chung mới; đọc ra giá mới."""
		so = self._don_cho_khach(self.item_boi_so, 7000)
		bang = bg.dam_bao_bang_gia_rieng(self.kh_a)
		cu = self._dong_gia(self.item_boi_so, bang, 3000,
		                    valid_from=add_days(today(), -30), valid_upto=add_days(today(), -1))
		truoc = self._dong(cu.name)
		self.assertIsNone(bg.gia_bang_gia(self.kh_a, self.item_boi_so))
		self._khach(so, "dong_y")
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 7000.0)
		self.assertEqual(self._dong(cu.name), truoc)
		moi = frappe.get_all("Item Price", filters={
			"item_code": self.item_boi_so, "price_list": bang, "name": ["!=", cu.name]},
			fields=["customer", "valid_from", "valid_upto"])
		self.assertEqual(len(moi), 1)
		self.assertFalse(moi[0].customer)
		self.assertEqual(str(moi[0].valid_from), today())
		self.assertIsNone(moi[0].valid_upto)

	def test_dong_y_khi_dong_gia_chua_co_hieu_luc(self):
		"""Dòng hẹn ngày tương lai là kế hoạch của nhân viên: không bị ghi đè."""
		so = self._don_cho_khach(self.item_boi_so, 7000)
		bang = bg.dam_bao_bang_gia_rieng(self.kh_a)
		cu = self._dong_gia(self.item_boi_so, bang, 3000, valid_from=add_days(today(), 10))
		truoc = self._dong(cu.name)
		self._khach(so, "dong_y")
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 7000.0)
		self.assertEqual(self._dong(cu.name), truoc)
		self.assertEqual(frappe.db.count("Item Price", {
			"item_code": self.item_boi_so, "price_list": bang}), 2)

	def test_dong_y_khi_dong_gia_co_valid_from_hom_nay(self):
		"""Dòng cùng khoá với dòng sẽ chèn (valid_from hôm nay, không hạn) còn hiệu
		lực nên được SỬA, không chèn trùng khoá."""
		so = self._don_cho_khach(self.item_boi_so, 7000)
		bang = bg.dam_bao_bang_gia_rieng(self.kh_a)
		cu = self._dong_gia(self.item_boi_so, bang, 3000,
		                    uom=frappe.db.get_value("Item", self.item_boi_so, "stock_uom"),
		                    valid_from=today())
		self._khach(so, "dong_y")
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 7000.0)
		self.assertEqual(self._dong(cu.name).price_list_rate, 7000.0)
		self.assertEqual(frappe.db.count("Item Price", {
			"item_code": self.item_boi_so, "price_list": bang}), 1)

	def test_dong_y_giu_nguyen_ngay_hieu_luc_cua_dong_dang_dung(self):
		so = self._don_cho_khach(self.item_boi_so, 7000)
		bang = bg.dam_bao_bang_gia_rieng(self.kh_a)
		cu = self._dong_gia(self.item_boi_so, bang, 3000, valid_from=add_days(today(), -5),
		                    valid_upto=add_days(today(), 20))
		self._khach(so, "dong_y")
		d = self._dong(cu.name)
		self.assertEqual(d.price_list_rate, 7000.0)
		self.assertEqual(str(d.valid_from), add_days(today(), -5))
		self.assertEqual(str(d.valid_upto), add_days(today(), 20))

	def test_he_so_quy_doi_khong_tron(self):
		"""100000 / 12 không tròn: ghi được, đọc ra giá làm tròn, không Error Log."""
		so = self._don_cho_khach(self.item_boi_so, 7000)
		thung = "Box" if frappe.db.get_value("Item", self.item_boi_so, "stock_uom") != "Box" else "Nos"
		self._quy_doi(thung, 12)
		frappe.db.set_value("Sales Order Item", so.items[0].name,
		                    {"uom": thung, "conversion_factor": 12, "rate": 100000})
		self._khach(so, "dong_y")
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), bg.lam_tron_gia(100000 / 12))
		self.assertFalse(frappe.db.exists("Error Log", {"reference_name": so.name}))

	def test_cung_ma_hai_dong_khac_gia_dong_cuoi_thang(self):
		kq = dat_hang.tao_sales_order(
			self.kh_a, items=[{"item_code": self.item_boi_so, "qty": 10}],
			request_id=frappe.generate_hash(length=12))
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		so.append("items", {**{k: so.items[0].get(k) for k in (
			"item_code", "qty", "uom", "conversion_factor", "warehouse", "delivery_date",
			"custom_nguon_gia")}})
		so.items[0].rate, so.items[1].rate = 7000, 8000
		so.save()
		so = apply_workflow(so, "Gửi khách duyệt")
		self._khach(so, "dong_y")
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 8000.0)
		noi_dung = " ".join(frappe.get_all("Comment", filters={
			"reference_doctype": "Sales Order", "reference_name": so.name}, pluck="content"))
		self.assertIn("nhiều dòng khác giá", noi_dung)

	def test_hong_giua_chung_khong_de_lai_nua_vo_va_van_giu_dau(self):
		"""Hai mã "Báo giá"; mã thứ hai ghi hỏng: không dòng giá nào còn lại, bảng
		giá mặc định như cũ, đơn vẫn sang "Chờ Miyano xác nhận", dấu còn nguyên."""
		kq = dat_hang.tao_sales_order(
			self.kh_a, items=[{"item_code": self.item_boi_so, "qty": 10},
			                  {"item_code": self.item_ngoai, "qty": 1}],
			request_id=frappe.generate_hash(length=12))
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		for d in so.items:
			d.rate = 7000 if d.item_code == self.item_boi_so else 9000
			d.custom_nguon_gia = "Báo giá"
		so.save()
		so = apply_workflow(so, "Gửi khách duyệt")
		bang_truoc = frappe.db.get_value("Customer", self.kh_a, "default_price_list")
		goc_ghi = bg.ghi_gia_vao_bang
		cac_ma = []

		def ghi_hong(bang, khach, ma, gia, tien_te=None):
			cac_ma.append(ma)
			if len(cac_ma) == 2:
				raise RuntimeError("hong o ma thu hai")
			return goc_ghi(bang, khach, ma, gia, tien_te)

		with patch.object(bg, "ghi_gia_vao_bang", side_effect=ghi_hong):
			kq = self._khach(so, "dong_y")
		self.assertEqual(len(cac_ma), 2)
		self.assertEqual(kq["trang_thai_moi"], "Chờ Miyano xác nhận")
		self.assertEqual(frappe.db.get_value("Customer", self.kh_a, "default_price_list"),
		                 bang_truoc)
		for ma in (self.item_boi_so, self.item_ngoai):
			self.assertFalse(frappe.get_all("Item Price", filters={
				"item_code": ma, "price_list": ["not in", [bang_truoc]], "selling": 1,
				"creation": [">=", so.creation]}))
		self.assertIsNone(bg.gia_bang_gia(self.kh_a, self.item_boi_so))
		self.assertTrue(frappe.db.exists("Comment", {
			"reference_doctype": "Sales Order", "reference_name": so.name,
			"content": ["like", "Khách đồng ý%"]}))
		so.reload()
		self.assertEqual(sorted(float(d.custom_gia_khach_dong_y) for d in so.items),
		                 [7000.0, 9000.0])
		# dấu còn nên chốt 3 vẫn chặn khi nhân viên đổi giá
		so.items[0].rate = float(so.items[0].rate) + 1000
		with self.assertRaises(frappe.ValidationError):
			so.submit()
		frappe.db.delete("Error Log", {"reference_name": so.name})

	def test_doc_lai_khong_ra_gia_van_giu_dau(self):
		so = self._don_cho_khach(self.item_boi_so, 7000)
		with patch.object(bg, "gia_bang_gia_nhieu", return_value={}):
			self._khach(so, "dong_y")
		self.assertEqual(float(frappe.db.get_value(
			"Sales Order Item", so.items[0].name, "custom_gia_khach_dong_y")), 7000.0)
		self.assertEqual(frappe.db.count("Item Price", {
			"item_code": self.item_boi_so, "selling": 1}), 0)
		frappe.db.delete("Error Log", {"reference_name": so.name})

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
		self._quy_doi(thung, 10)
		frappe.db.set_value("Sales Order Item", so.items[0].name,
		                    {"uom": thung, "conversion_factor": 10, "rate": 70000})
		self._khach(so, "dong_y")
		self.assertEqual(float(frappe.db.get_value(
			"Sales Order Item", so.items[0].name, "conversion_factor")), 10.0)
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 7000.0)

	# ---- Final-fix I-3: dòng "Bảng giá" / dòng thêm tay trong ĐƠN BÁO GIÁ ----
	# Đơn "Mua lẻ" có một dòng "Bảng giá" là ca hợp lệ (giá xuất hiện giữa lúc
	# gửi và lúc duyệt §4.3, hoặc gửi lại). Luật R14/R16 chạy cho MỌI dòng lúc
	# đơn vào "Chờ khách đồng ý", không chỉ khi tình cờ có dòng gõ tay gộp vào.

	def _don_tron(self):
		"""Đơn báo giá: `item_ngoai` có giá bảng 54.000 (dòng "Bảng giá"),
		`item_boi_so` chưa có giá (dòng "Báo giá")."""
		self._tao_gia(self.item_ngoai, self.price_list, 54000)
		kq = dat_hang.tao_sales_order(
			self.kh_a,
			items=[{"item_code": self.item_ngoai, "qty": 2},
			       {"item_code": self.item_boi_so, "qty": 10}],
			request_id=frappe.generate_hash(length=12),
		)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(so.custom_loai_don, "Mua lẻ")
		self.assertEqual(self._dong_don(so, self.item_ngoai).custom_nguon_gia, "Bảng giá")
		self.assertEqual(self._dong_don(so, self.item_boi_so).custom_nguon_gia, "Báo giá")
		return so

	def _dong_don(self, so, ma):
		return [d for d in so.items if d.item_code == ma][0]

	def _gia_trong_bang(self, ma):
		return frappe.get_all(
			"Item Price", filters={"item_code": ma, "selling": 1},
			fields=["name", "price_list", "price_list_rate", "modified"],
			order_by="name asc",
		)

	def _dau_dong_y(self, so, ma):
		return float(frappe.db.get_value(
			"Sales Order Item", self._dong_don(so, ma).name, "custom_gia_khach_dong_y") or 0)

	def test_dong_bang_gia_khong_ai_sua_khong_ghi_khong_dong_dau(self):
		"""(a) Dòng "Bảng giá" còn nguyên giá bảng: giữ dấu, không ghi gì vào
		Price List, không có dấu giá đã đồng ý. Dòng "Báo giá" cạnh nó vẫn ghi."""
		so = self._don_tron()
		self._dong_don(so, self.item_boi_so).rate = 7000
		so.save()
		truoc = self._gia_trong_bang(self.item_ngoai)
		so = apply_workflow(so, "Gửi khách duyệt")
		dong = self._dong_don(so, self.item_ngoai)
		self.assertEqual(dong.custom_nguon_gia, "Bảng giá")
		self.assertEqual(float(dong.rate), 54000.0)
		self._khach(so, "dong_y")
		self.assertEqual(self._gia_trong_bang(self.item_ngoai), truoc)
		self.assertEqual(self._dau_dong_y(so, self.item_ngoai), 0.0)
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 7000.0)
		self.assertEqual(self._dau_dong_y(so, self.item_boi_so), 7000.0)

	def test_dong_bang_gia_bi_chiet_khau_tay_la_mot_bao_gia(self):
		"""(b) Nhân viên hạ giá dòng "Bảng giá" 54.000 → 50.000 rồi gửi khách:
		dòng thành "Báo giá" lúc gửi; khách đồng ý thì 50.000 vào Price List và
		được đóng dấu; đổi giá lần nữa thì chốt 3 chặn xác nhận."""
		so = self._don_tron()
		self._dong_don(so, self.item_boi_so).rate = 7000
		self._dong_don(so, self.item_ngoai).rate = 50000
		so.save()
		self.assertEqual(self._dong_don(so, self.item_ngoai).custom_nguon_gia, "Bảng giá",
		                 "dấu chỉ đổi lúc gửi khách, không đổi ở lần lưu thường")
		so = apply_workflow(so, "Gửi khách duyệt")
		dong = self._dong_don(so, self.item_ngoai)
		self.assertEqual(dong.custom_nguon_gia, "Báo giá")
		self.assertEqual(float(dong.rate), 50000.0)
		self.assertEqual(float(dong.amount), 2 * 50000.0)

		self._khach(so, "dong_y")
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_ngoai), 50000.0)
		self.assertEqual(self._dau_dong_y(so, self.item_ngoai), 50000.0)

		so.reload()
		self._dong_don(so, self.item_ngoai).rate = 45000
		with self.assertRaises(frappe.ValidationError) as ctx:
			so.submit()
		self.assertIn("gửi khách duyệt lại", str(ctx.exception))
		self.assertIn(self.item_ngoai, str(ctx.exception))

	def _them_dong_tay_tren_desk(self, so, ma, rate):
		"""Nhân viên thêm một dòng trên Desk: không qua cổng nên KHÔNG có dấu."""
		so.append("items", {
			"item_code": ma, "qty": 2, "rate": rate,
			"delivery_date": so.delivery_date,
			"warehouse": so.items[0].warehouse,
		})
		so.save()
		so.reload()
		dong = self._dong_don(so, ma)
		self.assertFalse(dong.custom_nguon_gia)
		self.assertEqual(float(dong.rate), float(rate))
		return so

	def test_dong_them_tay_tren_desk_mang_gia_go_tay_la_mot_bao_gia(self):
		"""(c) Dòng CHƯA có dấu, giá 50.000 khác giá bảng 54.000: như (b)."""
		so = self._don_cho_khach_chua_gui(self.item_boi_so, 7000)
		self._tao_gia(self.item_ngoai, self.price_list, 54000)
		so = self._them_dong_tay_tren_desk(so, self.item_ngoai, 50000)

		so = apply_workflow(so, "Gửi khách duyệt")
		dong = self._dong_don(so, self.item_ngoai)
		self.assertEqual(dong.custom_nguon_gia, "Báo giá")
		self.assertEqual(float(dong.rate), 50000.0)

		self._khach(so, "dong_y")
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_ngoai), 50000.0)
		self.assertEqual(self._dau_dong_y(so, self.item_ngoai), 50000.0)

		so.reload()
		self._dong_don(so, self.item_ngoai).rate = 45000
		with self.assertRaises(frappe.ValidationError) as ctx:
			so.submit()
		self.assertIn("gửi khách duyệt lại", str(ctx.exception))

	def test_dong_them_tay_tren_desk_dung_gia_bang_la_dong_bang_gia(self):
		"""(c') Dòng chưa có dấu mà giá ĐÚNG bằng giá bảng hôm nay: "Bảng giá",
		không có gì để ghi lúc khách đồng ý."""
		so = self._don_cho_khach_chua_gui(self.item_boi_so, 7000)
		self._tao_gia(self.item_ngoai, self.price_list, 54000)
		so = self._them_dong_tay_tren_desk(so, self.item_ngoai, 54000)
		truoc = self._gia_trong_bang(self.item_ngoai)

		so = apply_workflow(so, "Gửi khách duyệt")
		self.assertEqual(self._dong_don(so, self.item_ngoai).custom_nguon_gia, "Bảng giá")
		self._khach(so, "dong_y")
		self.assertEqual(self._gia_trong_bang(self.item_ngoai), truoc)
		self.assertEqual(self._dau_dong_y(so, self.item_ngoai), 0.0)

	def test_gia_bang_doi_thi_dong_bang_gia_duoc_lam_moi_luc_gui_khach(self):
		"""(d) Dòng "Bảng giá" chưa ai sửa, giá bảng đổi 54.000 → 56.000 từ lúc
		lập đơn: lúc gửi khách dòng nhận 56.000 (cả thành tiền và tổng đơn), vẫn
		là "Bảng giá"; khách đồng ý không ghi gì cho mã đó."""
		so = self._don_tron()
		self._dong_don(so, self.item_boi_so).rate = 7000
		so.save()
		ten_gia = self._gia_trong_bang(self.item_ngoai)[0].name
		frappe.db.set_value("Item Price", ten_gia, "price_list_rate", 56000)
		truoc = self._gia_trong_bang(self.item_ngoai)

		so = apply_workflow(so, "Gửi khách duyệt")
		dong = self._dong_don(so, self.item_ngoai)
		self.assertEqual(dong.custom_nguon_gia, "Bảng giá")
		self.assertEqual(float(dong.rate), 56000.0)
		self.assertEqual(float(dong.price_list_rate), 56000.0)
		self.assertEqual(float(dong.amount), 2 * 56000.0)
		self.assertEqual(float(so.total), 2 * 56000.0 + 10 * 7000.0)
		so.reload()
		self.assertEqual(float(self._dong_don(so, self.item_ngoai).amount), 2 * 56000.0)
		self.assertEqual(float(so.total), 2 * 56000.0 + 10 * 7000.0)

		self._khach(so, "dong_y")
		self.assertEqual(self._gia_trong_bang(self.item_ngoai), truoc)
		self.assertEqual(self._dau_dong_y(so, self.item_ngoai), 0.0)

	def test_ma_bi_rut_khoi_bang_thi_chua_gui_khach_duoc(self):
		"""(d') Dòng "Bảng giá" chưa ai sửa mà mã đã bị rút khỏi bảng: dòng về
		0, thành "Báo giá" — chốt 2 chặn gửi và nêu tên mặt hàng. Giá đã rút
		không đi tiếp tới khách, cũng không bị ghi ngược vào bảng."""
		so = self._don_tron()
		self._dong_don(so, self.item_boi_so).rate = 7000
		so.save()
		for r in self._gia_trong_bang(self.item_ngoai):
			frappe.delete_doc("Item Price", r.name, force=True)
		with self.assertRaises(frappe.ValidationError) as ctx:
			apply_workflow(so, "Gửi khách duyệt")
		self.assertIn(self.item_ngoai, str(ctx.exception))
		self.assertIn("chưa có đơn giá", str(ctx.exception))

	def test_don_theo_bang_gia_khong_bi_dong_lai_dau(self):
		"""Chỉ đơn ĐI VÒNG BÁO GIÁ: đơn "Theo bảng giá" bị sửa giá tay vẫn giữ
		dấu "Bảng giá" khi nhân viên dùng «Gửi khách duyệt»."""
		self._tao_gia(self.item_ngoai, self.price_list, 54000)
		kq = dat_hang.tao_sales_order(
			self.kh_a, items=[{"item_code": self.item_ngoai, "qty": 2}],
			request_id=frappe.generate_hash(length=12),
		)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(so.custom_loai_don, "Theo bảng giá")
		so.items[0].rate = 50000
		so.save()
		so = apply_workflow(so, "Gửi khách duyệt")
		self.assertEqual(so.items[0].custom_nguon_gia, "Bảng giá")
		self.assertEqual(float(so.items[0].rate), 50000.0)

	def test_dong_go_tay_khop_ma_co_gia_di_het_vong_ma_khong_ghi_bang_gia(self):
		"""Spec 2026-10-09 §4.4 gặp ba chốt §5: đơn chỉ có MỘT dòng gõ tay, nhân
		viên khớp nó về một mã ĐÃ CÓ GIÁ. Dòng sinh ra mang giá bảng và dấu "Bảng
		giá", nên (1) "Gửi khách duyệt" qua được chốt 2 mà không ai phải gõ giá,
		và (2) khách đồng ý KHÔNG ghi gì vào Price List — giá đó vốn là của bảng."""
		bang = bg.dam_bao_bang_gia_rieng(self.kh_a)
		self._tao_gia(self.item_ngoai, bang, 54000)
		kq = dat_hang.tao_sales_order(
			self.kh_a, items=[],
			dat_ngoai=[{"ten_hang": "Kim X", "dvt": "Cái", "so_luong": 3,
			            "khong_co_anh": 1}],
			request_id=frappe.generate_hash(length=12),
		)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		so.custom_dat_ngoai[0].item_khop = self.item_ngoai
		so.save()
		so.reload()
		dong = [d for d in so.items if d.item_code == self.item_ngoai][0]
		self.assertEqual(dong.custom_nguon_gia, "Bảng giá")
		self.assertEqual(float(dong.rate), 54000.0)
		self.assertEqual(so.custom_loai_don, "Mua lẻ", "đơn vẫn ở vòng báo giá (QĐ-G2b)")

		def gia_trong_bang():
			return frappe.get_all(
				"Item Price", filters={"item_code": self.item_ngoai, "selling": 1},
				fields=["name", "price_list", "price_list_rate", "modified"],
				order_by="name asc",
			)

		truoc = gia_trong_bang()
		so = apply_workflow(so, "Gửi khách duyệt")
		self.assertEqual(so.workflow_state, "Chờ khách đồng ý")
		self._khach(so, "dong_y")

		self.assertEqual(gia_trong_bang(), truoc, "Price List không được đổi")
		self.assertEqual(float(frappe.db.get_value(
			"Sales Order Item", dong.name, "custom_gia_khach_dong_y") or 0), 0.0)
		noi_dung = " ".join(frappe.get_all(
			"Comment", filters={"reference_doctype": "Sales Order",
			                    "reference_name": so.name}, pluck="content"))
		self.assertNotIn("Ghi giá khách đã đồng ý", noi_dung)

	def test_dong_chua_dau_mang_gia_nhan_vien_go_di_het_vong_nhu_mot_bao_gia(self):
		"""Ruling R14, đi hết đường: dòng CHƯA có dấu (nhân viên thêm tay trên
		Desk) mang 50.000, mã có giá bảng 54.000. Gộp một dòng gõ tay vào nó →
		dấu "Báo giá", giữ 50.000. Khách sửa số lượng → về 0 chờ báo lại, KHÔNG
		lặng lẽ thành 54.000."""
		bang = bg.dam_bao_bang_gia_rieng(self.kh_a)
		kq = dat_hang.tao_sales_order(
			self.kh_a, items=[{"item_code": self.item_ngoai, "qty": 2}],
			dat_ngoai=[{"ten_hang": "Kim X", "dvt": "Cái", "so_luong": 3,
			            "khong_co_anh": 1}],
			request_id=frappe.generate_hash(length=12),
		)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		so.items[0].rate = 50000
		so.save()
		frappe.db.set_value("Sales Order Item", so.items[0].name,
		                    "custom_nguon_gia", "", update_modified=False)
		self._tao_gia(self.item_ngoai, bang, 54000)
		so.reload()
		self.assertFalse(so.items[0].custom_nguon_gia)

		so.custom_dat_ngoai[0].item_khop = self.item_ngoai
		so.save()
		so.reload()
		dong = [d for d in so.items if d.item_code == self.item_ngoai][0]
		self.assertEqual(float(dong.qty), 5.0)
		self.assertEqual(float(dong.rate), 50000.0)
		self.assertEqual(dong.custom_nguon_gia, "Báo giá")

		so = apply_workflow(so, "Gửi khách duyệt")
		frappe.set_user(self.quan_ly)
		try:
			portal.portal_order_sua_so_luong(
				so.name, {"items": [{"item_code": self.item_ngoai, "qty": 8}]})
		finally:
			frappe.set_user("Administrator")
		dong.reload()
		self.assertEqual(float(dong.qty), 8.0)
		self.assertEqual(float(dong.rate), 0.0, "báo giá lại, không tự nhận 54.000")
		self.assertEqual(dong.custom_nguon_gia, "Báo giá")

	def test_de_lai_dau_vet_tren_don(self):
		so = self._don_cho_khach(self.item_boi_so, 7000)
		self._khach(so, "dong_y")
		noi_dung = " ".join(frappe.get_all(
			"Comment", filters={"reference_doctype": "Sales Order",
			                    "reference_name": so.name}, pluck="content"))
		self.assertIn(self.item_boi_so, noi_dung)
		self.assertIn("7.000", noi_dung.replace(",", "."))
		self.assertIn(self.quan_ly, noi_dung)  # ai đồng ý

	# --- Ruling R10: sự kiện nhật ký "ghi giá vào bảng giá" ------------------

	def _nhat_ky_ghi_gia(self, so):
		from miyano_portal import nhat_ky
		return frappe.get_all(
			nhat_ky.DOCTYPE,
			filters={"sales_order": so.name, "su_kien": nhat_ky.SK_GHI_GIA_BANG_GIA},
			fields=["customer", "khoa_phong", "de_xuat", "vai", "nguoi_thao_tac", "ghi_chu"],
		)

	def test_ghi_gia_de_lai_mot_dong_nhat_ky(self):
		from miyano_portal import nhat_ky
		so = self._don_cho_khach(self.item_boi_so, 7000)
		khoa = frappe.db.get_value("Sales Order", so.name, "custom_khoa_phong")
		self._khach(so, "dong_y")
		dong = self._nhat_ky_ghi_gia(so)
		self.assertEqual(len(dong), 1, "đúng MỘT dòng cho một lần ghi giá")
		self.assertEqual(dong[0].customer, self.kh_a)
		self.assertEqual(dong[0].khoa_phong, khoa)
		self.assertEqual(dong[0].vai, nhat_ky.VAI_HE_THONG)
		self.assertFalse(dong[0].nguoi_thao_tac, "hệ thống ghi, không gán cho người bấm")
		self.assertIn(self.item_boi_so, dong[0].ghi_chu)
		self.assertIn("7.000", dong[0].ghi_chu.replace(",", "."))

	def test_khong_ghi_gia_nao_thi_khong_co_dong_nhat_ky(self):
		so = self._don_cho_khach(self.item_boi_so, 7000)
		self._khach(so, "khong_dong_y", ly_do="Giá cao hơn dự kiến của khoa")
		self.assertEqual(self._nhat_ky_ghi_gia(so), [])
		# Đơn không có dòng "Báo giá" nào có giá: gọi thẳng cũng không ghi.
		self._tao_gia(self.item_ngoai, self.price_list, 54000)
		kq = dat_hang.tao_sales_order(
			self.kh_a, items=[{"item_code": self.item_ngoai, "qty": 1}],
			request_id=frappe.generate_hash(length=12),
		)
		so2 = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(bg.ghi_gia_da_dong_y(so2), [])
		self.assertEqual(self._nhat_ky_ghi_gia(so2), [])

	def test_nhat_ky_hong_khong_lam_hong_viec_ghi_gia(self):
		from miyano_portal import nhat_ky
		so = self._don_cho_khach(self.item_boi_so, 7000)
		truoc = frappe.db.count("Error Log", {"reference_name": so.name})
		ghi_that = nhat_ky.ghi

		# Chỉ làm hỏng ĐÚNG sự kiện này: `portal_order_accept` còn ghi
		# `khach_dong_y` qua cùng hàm.
		def _hong(su_kien, **kw):
			if su_kien == nhat_ky.SK_GHI_GIA_BANG_GIA:
				raise RuntimeError("so nhat ky hong")
			return ghi_that(su_kien, **kw)

		with patch.object(nhat_ky, "ghi", side_effect=_hong):
			self._khach(so, "dong_y")
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 7000.0)
		self.assertEqual(self._nhat_ky_ghi_gia(so), [])
		self.assertEqual(
			frappe.db.count("Error Log", {"reference_name": so.name}), truoc,
			"sổ nhật ký hỏng không được bị báo thành lỗi ghi giá",
		)

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
		self.assertEqual(float(so.items[0].custom_gia_khach_dong_y or 0), 7000.0)
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


for _ten, _ham in vars(goc.TestPortalCatalogGop).items():
	if _ten.startswith("_") and not _ten.startswith("__") and callable(_ham):
		if _ten not in vars(TestGhiGiaDaDongY):
			setattr(TestGhiGiaDaDongY, _ten, _ham)
