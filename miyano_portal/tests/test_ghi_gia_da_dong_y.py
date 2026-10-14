"""Ghi giá khách đã đồng ý vào Price List (spec 2026-10-09 §5.2).

Khách chỉ còn đồng ý giá trên Quotation (`bao_gia.dong_y`, patch v1_44): đơn
"Theo báo giá" sinh ra mang mọi dòng là "Báo giá", và `bang_gia_khach.
ghi_gia_da_dong_y` ghi các dòng đó vào bảng giá riêng của khách.
"""

from unittest.mock import patch

import frappe
from frappe.model.workflow import apply_workflow
from frappe.utils import add_days, today

from miyano_portal import bang_gia_khach as bg
from miyano_portal import bao_gia, dat_hang
from miyano_portal.tests.nen_bao_gia import NenBaoGia


class TestGhiGiaDaDongY(NenBaoGia):
	def setUp(self):
		super().setUp()
		self.quan_ly = self._quan_ly("ghigia.ql@demo.miyano", self.kh_a)

	def _bao_gia(self, dong, sua=None):
		"""Báo giá của cổng `dong` = [(mã, số lượng, đơn giá)], Miyano điền giá
		(và `sua(bg)` nếu có) rồi gửi khách."""
		phieu = frappe.get_doc({
			"doctype": "Portal De Xuat Mua", "customer": self.kh_a,
			"khoa_phong": self.khoa_huyethoc, "ly_do_yeu_cau": "Hết hàng trong kho khoa",
			"trang_thai": "Đã duyệt", "ngay_can": add_days(today(), 10),
			"items": [{"item_code": ma, "so_luong_de_xuat": sl, "so_luong_duyet": sl}
			          for ma, sl, _ in dong],
		}).insert(ignore_permissions=True)
		kq = bao_gia.tao_bao_gia(
			self.kh_a, items=[{"item_code": ma, "qty": sl} for ma, sl, _ in dong],
			request_id=frappe.generate_hash(length=12), khoa_phong=self.khoa_huyethoc,
		)
		q = frappe.get_doc("Quotation", kq["bao_gia"])
		q.custom_de_xuat = phieu.name
		for d, (_, _, gia) in zip(q.items, dong):
			d.rate = d.price_list_rate = gia
		if sua:
			sua(q)
		q.save()
		frappe.db.set_value("Portal De Xuat Mua", phieu.name, "bao_gia", q.name)
		return apply_workflow(q, bao_gia.HD_GUI_KHACH)

	def _dong_y(self, q):
		frappe.set_user(self.quan_ly)
		try:
			kq = bao_gia.dong_y(q.name)
		finally:
			frappe.set_user("Administrator")
		return frappe.get_doc("Sales Order", kq["sales_order"])

	def _dong_y_gia(self, ma, rate):
		return self._dong_y(self._bao_gia([(ma, 10, rate)]))

	def _dong_gia(self, ma, bang, rate, **them):
		"""Chèn thẳng một dòng Item Price (kể cả dòng gắn khách / có hạn)."""
		return frappe.get_doc({
			"doctype": "Item Price", "item_code": ma, "price_list": bang,
			"selling": 1, "price_list_rate": rate, **them,
		}).insert(ignore_permissions=True)

	def _quy_doi(self, uom, he_so):
		item = frappe.get_doc("Item", self.item_boi_so)
		dong = [u for u in item.uoms if u.uom == uom]
		if dong:
			dong[0].conversion_factor = he_so
		else:
			item.append("uoms", {"uom": uom, "conversion_factor": he_so})
		item.save(ignore_permissions=True)

	def _thung(self):
		return "Box" if frappe.db.get_value("Item", self.item_boi_so, "stock_uom") != "Box" else "Nos"

	def _dong(self, ten):
		return frappe.db.get_value(
			"Item Price", ten, ["price_list_rate", "valid_from", "valid_upto"], as_dict=True)

	def test_dong_y_tao_dong_gia_moi(self):
		self._dong_y_gia(self.item_boi_so, 7000)
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 7000.0)

	def test_dong_y_cap_nhat_dong_gia_cu_khong_tao_dong_thu_hai(self):
		q = self._bao_gia([(self.item_boi_so, 10, 7000)])
		# Giá xuất hiện SAU khi báo giá đã gửi khách.
		self._tao_gia(self.item_boi_so, self.price_list, 5000)
		self._dong_y(q)
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 7000.0)
		bang = frappe.db.get_value("Customer", self.kh_a, "default_price_list")
		self.assertEqual(frappe.db.count("Item Price", {
			"item_code": self.item_boi_so, "price_list": bang, "selling": 1,
		}), 1)

	def test_dong_y_co_ca_dong_rieng_khach_va_dong_chung(self):
		"""Bảng của khách có cả dòng gắn riêng khách lẫn dòng chung: bộ đọc ưu tiên
		dòng riêng, nên bộ ghi phải sửa đúng dòng đó — đọc lại ra giá vừa đồng ý."""
		q = self._bao_gia([(self.item_boi_so, 10, 7000)])
		bang = bg.dam_bao_bang_gia_rieng(self.kh_a)
		self._dong_gia(self.item_boi_so, bang, 4000, customer=self.kh_a)
		self._dong_gia(self.item_boi_so, bang, 5000)
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 4000.0)
		self._dong_y(q)
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 7000.0)
		self.assertEqual(frappe.db.count("Item Price", {
			"item_code": self.item_boi_so, "price_list": bang, "selling": 1,
		}), 2)

	def test_dong_y_khi_dong_gia_da_het_han(self):
		"""Chỉ có dòng hết hạn: để nguyên nó, chèn dòng chung mới; đọc ra giá mới."""
		q = self._bao_gia([(self.item_boi_so, 10, 7000)])
		bang = bg.dam_bao_bang_gia_rieng(self.kh_a)
		cu = self._dong_gia(self.item_boi_so, bang, 3000,
		                    valid_from=add_days(today(), -30), valid_upto=add_days(today(), -1))
		truoc = self._dong(cu.name)
		self.assertIsNone(bg.gia_bang_gia(self.kh_a, self.item_boi_so))
		self._dong_y(q)
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
		q = self._bao_gia([(self.item_boi_so, 10, 7000)])
		bang = bg.dam_bao_bang_gia_rieng(self.kh_a)
		cu = self._dong_gia(self.item_boi_so, bang, 3000, valid_from=add_days(today(), 10))
		truoc = self._dong(cu.name)
		self._dong_y(q)
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 7000.0)
		self.assertEqual(self._dong(cu.name), truoc)
		self.assertEqual(frappe.db.count("Item Price", {
			"item_code": self.item_boi_so, "price_list": bang}), 2)

	def test_dong_y_khi_dong_gia_co_valid_from_hom_nay(self):
		"""Dòng cùng khoá với dòng sẽ chèn (valid_from hôm nay, không hạn) còn hiệu
		lực nên được SỬA, không chèn trùng khoá."""
		q = self._bao_gia([(self.item_boi_so, 10, 7000)])
		bang = bg.dam_bao_bang_gia_rieng(self.kh_a)
		cu = self._dong_gia(self.item_boi_so, bang, 3000,
		                    uom=frappe.db.get_value("Item", self.item_boi_so, "stock_uom"),
		                    valid_from=today())
		self._dong_y(q)
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 7000.0)
		self.assertEqual(self._dong(cu.name).price_list_rate, 7000.0)
		self.assertEqual(frappe.db.count("Item Price", {
			"item_code": self.item_boi_so, "price_list": bang}), 1)

	def test_dong_y_giu_nguyen_ngay_hieu_luc_cua_dong_dang_dung(self):
		q = self._bao_gia([(self.item_boi_so, 10, 7000)])
		bang = bg.dam_bao_bang_gia_rieng(self.kh_a)
		cu = self._dong_gia(self.item_boi_so, bang, 3000, valid_from=add_days(today(), -5),
		                    valid_upto=add_days(today(), 20))
		self._dong_y(q)
		d = self._dong(cu.name)
		self.assertEqual(d.price_list_rate, 7000.0)
		self.assertEqual(str(d.valid_from), add_days(today(), -5))
		self.assertEqual(str(d.valid_upto), add_days(today(), 20))

	def _bao_gia_theo_thung(self, he_so, gia_thung):
		thung = self._thung()
		self._quy_doi(thung, he_so)

		def theo_thung(q):
			q.items[0].uom = thung
			q.items[0].conversion_factor = he_so
			q.items[0].rate = q.items[0].price_list_rate = gia_thung

		return self._bao_gia([(self.item_boi_so, 10, gia_thung)], sua=theo_thung)

	def test_he_so_quy_doi_khong_tron(self):
		"""100000 / 12 không tròn: ghi được, đọc ra giá làm tròn, không Error Log."""
		so = self._dong_y(self._bao_gia_theo_thung(12, 100000))
		self.assertEqual(float(so.items[0].conversion_factor), 12.0)
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), bg.lam_tron_gia(100000 / 12))
		self.assertFalse(frappe.db.exists("Error Log", {"reference_name": so.name}))

	def test_quy_doi_ve_don_vi_goc(self):
		so = self._dong_y(self._bao_gia_theo_thung(10, 70000))
		self.assertEqual(float(so.items[0].conversion_factor), 10.0)
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 7000.0)

	def test_cung_ma_hai_dong_khac_gia_dong_cuoi_thang(self):
		"""Báo giá của cổng gộp dòng cùng mã; nhân viên vẫn thêm được dòng thứ
		hai trên Desk. Bộ ghi lấy dòng sau cùng và để lại lời nhắc."""
		so = self._dong_y_gia(self.item_boi_so, 7000)
		so.append("items", {**{k: so.items[0].get(k) for k in (
			"item_code", "qty", "uom", "conversion_factor", "warehouse", "delivery_date",
			"custom_nguon_gia")}, "rate": 8000})
		bg.ghi_gia_da_dong_y(so, nguoi_dong_y=self.quan_ly)
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 8000.0)
		noi_dung = " ".join(frappe.get_all("Comment", filters={
			"reference_doctype": "Sales Order", "reference_name": so.name}, pluck="content"))
		self.assertIn("nhiều dòng khác giá", noi_dung)

	def test_hong_giua_chung_khong_de_lai_nua_vo_va_van_giu_dau(self):
		"""Hai mã; mã thứ hai ghi hỏng: không dòng giá nào còn lại, bảng giá mặc
		định như cũ, đơn vẫn sinh ở "Chờ Miyano xác nhận", dấu còn nguyên."""
		q = self._bao_gia([(self.item_boi_so, 10, 7000), (self.item_ngoai, 1, 9000)])
		bang_truoc = frappe.db.get_value("Customer", self.kh_a, "default_price_list")
		goc_ghi = bg.ghi_gia_vao_bang
		cac_ma = []

		def ghi_hong(bang, khach, ma, gia, tien_te=None):
			cac_ma.append(ma)
			if len(cac_ma) == 2:
				raise RuntimeError("hong o ma thu hai")
			return goc_ghi(bang, khach, ma, gia, tien_te)

		with patch.object(bg, "ghi_gia_vao_bang", side_effect=ghi_hong):
			so = self._dong_y(q)
		self.assertEqual(len(cac_ma), 2)
		self.assertEqual(so.workflow_state, "Chờ Miyano xác nhận")
		self.assertEqual(frappe.db.get_value("Customer", self.kh_a, "default_price_list"),
		                 bang_truoc)
		for ma in (self.item_boi_so, self.item_ngoai):
			self.assertFalse(frappe.get_all("Item Price", filters={
				"item_code": ma, "price_list": ["not in", [bang_truoc]], "selling": 1,
				"creation": [">=", so.creation]}))
		self.assertIsNone(bg.gia_bang_gia(self.kh_a, self.item_boi_so))
		self.assertEqual(sorted(float(d.custom_gia_khach_dong_y) for d in so.items),
		                 [7000.0, 9000.0])
		# dấu còn nên chốt 3 vẫn chặn khi nhân viên đổi giá
		so.items[0].rate = float(so.items[0].rate) + 1000
		with self.assertRaises(frappe.ValidationError):
			so.submit()
		frappe.db.delete("Error Log", {"reference_name": so.name})

	def test_doc_lai_khong_ra_gia_van_giu_dau(self):
		q = self._bao_gia([(self.item_boi_so, 10, 7000)])
		with patch.object(bg, "gia_bang_gia_nhieu", return_value={}):
			so = self._dong_y(q)
		self.assertEqual(float(so.items[0].custom_gia_khach_dong_y), 7000.0)
		self.assertEqual(frappe.db.count("Item Price", {
			"item_code": self.item_boi_so, "selling": 1}), 0)
		frappe.db.delete("Error Log", {"reference_name": so.name})

	def test_de_lai_dau_vet_tren_don(self):
		so = self._dong_y_gia(self.item_boi_so, 7000)
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
		so = self._dong_y_gia(self.item_boi_so, 7000)
		dong = self._nhat_ky_ghi_gia(so)
		self.assertEqual(len(dong), 1, "đúng MỘT dòng cho một lần ghi giá")
		self.assertEqual(dong[0].customer, self.kh_a)
		self.assertEqual(dong[0].khoa_phong, so.custom_khoa_phong)
		self.assertEqual(dong[0].vai, nhat_ky.VAI_HE_THONG)
		self.assertFalse(dong[0].nguoi_thao_tac, "hệ thống ghi, không gán cho người bấm")
		self.assertIn(self.item_boi_so, dong[0].ghi_chu)
		self.assertIn("7.000", dong[0].ghi_chu.replace(",", "."))

	def test_don_khong_co_dong_bao_gia_thi_khong_ghi_gi(self):
		"""Đơn không có dòng "Báo giá" nào có giá: gọi thẳng cũng không ghi."""
		kq = dat_hang.tao_sales_order(
			self.kh_a, items=[{"item_code": self.item_ngoai, "qty": 1}],
			request_id=frappe.generate_hash(length=12),
		)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(bg.ghi_gia_da_dong_y(so), [])
		self.assertEqual(self._nhat_ky_ghi_gia(so), [])

	def test_nhat_ky_hong_khong_lam_hong_viec_ghi_gia(self):
		from miyano_portal import nhat_ky
		q = self._bao_gia([(self.item_boi_so, 10, 7000)])
		ghi_that = nhat_ky.ghi

		# Chỉ làm hỏng ĐÚNG sự kiện này: `bao_gia.dong_y` còn ghi
		# `khach_dong_y` qua cùng hàm.
		def _hong(su_kien, **kw):
			if su_kien == nhat_ky.SK_GHI_GIA_BANG_GIA:
				raise RuntimeError("so nhat ky hong")
			return ghi_that(su_kien, **kw)

		with patch.object(nhat_ky, "ghi", side_effect=_hong):
			so = self._dong_y(q)
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 7000.0)
		self.assertEqual(self._nhat_ky_ghi_gia(so), [])
		self.assertFalse(
			frappe.db.exists("Error Log", {"reference_name": so.name}),
			"sổ nhật ký hỏng không được bị báo thành lỗi ghi giá",
		)

	def test_loi_ghi_gia_bao_nhan_vien_phu_trach(self):
		sales = "ghigia.sales@demo.miyano"
		if not frappe.db.exists("User", sales):
			frappe.get_doc({"doctype": "User", "email": sales, "first_name": "ghigiasales",
			                "send_welcome_email": 0}).insert(ignore_permissions=True)
		frappe.db.set_value("Customer", self.kh_a, "account_manager", sales)
		q = self._bao_gia([(self.item_boi_so, 10, 7000)])
		with patch.object(bg, "ghi_gia_da_dong_y", side_effect=RuntimeError("hong")):
			so = self._dong_y(q)
		thong_bao = frappe.get_all("Notification Log", filters={"for_user": sales},
		                           fields=["subject", "email_content"])
		self.assertTrue(any(so.name in (t.subject or "") for t in thong_bao), thong_bao)
		frappe.db.delete("Error Log", {"reference_name": so.name})
