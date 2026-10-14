"""Dựng đơn theo Price List (spec 2026-10-09 §4.2)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import bang_gia_khach as bg
from miyano_portal import dat_hang
from miyano_portal.portal_mua_le import LOAI_DON_BAO_GIA
from miyano_portal.tests import test_catalog_gop as goc


class TestXayDonBangGia(FrappeTestCase):
	def setUp(self):
		goc.TestPortalCatalogGop.setUp(self)
		for ma in (self.item_ngoai, self.item_boi_so):
			for ten in frappe.get_all(
				"Item Price", filters={"item_code": ma, "selling": 1}, pluck="name"
			):
				frappe.delete_doc("Item Price", ten, force=True)
		self._tao_gia(self.item_ngoai, self.price_list, 54000)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _dat(self, items, **them):
		kq = dat_hang.tao_sales_order(
			self.kh_a, items=items,
			request_id=frappe.generate_hash(length=12), **them,
		)
		return frappe.get_doc("Sales Order", kq["sales_order"])

	def test_dong_co_gia_lay_gia_bang_gia_va_dong_dau(self):
		so = self._dat([{"item_code": self.item_ngoai, "qty": 3}])
		d = so.items[0]
		self.assertEqual(float(d.rate), 54000.0)
		self.assertEqual(float(d.price_list_rate), 54000.0)
		self.assertEqual(d.custom_nguon_gia, bg.NGUON_BANG_GIA)
		self.assertEqual(so.custom_loai_don, bg.LOAI_DON_BANG_GIA)

	def test_pricing_rule_cua_erpnext_khong_dinh_gia_lai_dong_cua_cong(self):
		"""Ruling R19 — cổng có ĐÚNG MỘT nguồn giá (Price List của khách). Một
		Pricing Rule bán hàng đang bật, khớp đúng mặt hàng và khách, không được
		chiết khấu dòng do cổng dựng: khách đã thấy 54.000 trên màn đặt hàng."""
		quy_tac = frappe.get_doc({
			"doctype": "Pricing Rule", "title": "_TEST DX R19 giam 10%",
			"apply_on": "Item Code", "items": [{"item_code": self.item_ngoai}],
			"selling": 1, "applicable_for": "Customer", "customer": self.kh_a,
			"price_or_product_discount": "Price",
			"rate_or_discount": "Discount Percentage", "discount_percentage": 10,
			"company": goc.COMPANY, "currency": "VND",
			"valid_from": frappe.utils.add_days(frappe.utils.today(), -1),
		}).insert(ignore_permissions=True)
		self.addCleanup(
			frappe.delete_doc, "Pricing Rule", quy_tac.name,
			force=True, ignore_permissions=True,
		)

		so = self._dat([{"item_code": self.item_ngoai, "qty": 3}])
		d = so.items[0]
		self.assertEqual(float(d.rate), 54000.0)
		self.assertEqual(float(d.price_list_rate), 54000.0)
		self.assertEqual(float(d.discount_percentage or 0), 0.0)
		self.assertEqual(float(d.amount), 3 * 54000.0)
		self.assertFalse(d.pricing_rules)
		self.assertEqual(so.ignore_pricing_rule, 1)
		# Lưu lại trên Desk (nhân viên mở đơn, bấm lưu) cũng không định giá lại.
		so.save()
		self.assertEqual(float(so.items[0].rate), 54000.0)

	def test_dong_luon_theo_don_vi_goc_du_item_co_sales_uom_khac(self):
		"""Ruling R15 — ERPNext mặc định `uom` của dòng mới theo `Item.sales_uom`,
		còn giá bảng tính theo `stock_uom` và cổng đặt theo đơn vị gốc. Dòng cổng
		dựng phải mang đơn vị gốc, hệ số 1, đúng giá bảng."""
		item = frappe.get_doc("Item", self.item_ngoai)
		thung = "Box" if item.stock_uom != "Box" else "Nos"
		item.append("uoms", {"uom": thung, "conversion_factor": 10})
		item.sales_uom = thung
		item.save(ignore_permissions=True)

		so = self._dat([{"item_code": self.item_ngoai, "qty": 3}])
		d = so.items[0]
		self.assertEqual(d.uom, item.stock_uom)
		self.assertEqual(float(d.conversion_factor), 1.0)
		self.assertEqual(float(d.stock_qty), 3.0)
		self.assertEqual(float(d.rate), 54000.0)
		self.assertEqual(float(d.amount), 3 * 54000.0)

	def test_dong_chua_co_gia_la_bao_gia_gia_0(self):
		so = self._dat([{"item_code": self.item_boi_so, "qty": 10}])
		d = so.items[0]
		self.assertEqual(float(d.rate), 0.0)
		self.assertEqual(d.custom_nguon_gia, bg.NGUON_BAO_GIA)
		self.assertEqual(so.custom_loai_don, LOAI_DON_BAO_GIA)

	def test_don_luon_mang_bang_gia_cua_khach(self):
		so = self._dat([{"item_code": self.item_boi_so, "qty": 10}])
		self.assertEqual(so.selling_price_list, self.price_list)

	def test_khach_chua_co_bang_gia_van_dat_duoc_va_duoc_gan_bang_rieng(self):
		frappe.db.set_value("Customer", self.kh_a, "default_price_list", None)
		so = self._dat([{"item_code": self.item_ngoai, "qty": 1}])
		# Tên có thể mang hậu tố "(mã ngắn)" khi "Bảng giá <khách>" đã tồn tại
		# (vd. patch v1_41 tạo trước) — chốt là bảng MỚI được gán cho khách.
		self.assertTrue(so.selling_price_list.startswith(f"Bảng giá {self.kh_a}"))
		self.assertEqual(
			so.selling_price_list,
			frappe.db.get_value("Customer", self.kh_a, "default_price_list"),
		)
		self.assertEqual(so.items[0].custom_nguon_gia, bg.NGUON_BAO_GIA)

	def test_dong_thuoc_hop_dong_khong_con_gan_lien_ket_hop_dong(self):
		so = self._dat([{"item_code": self.item_han_muc, "qty": 1}])
		self.assertFalse(so.items[0].get("blanket_order"))
		self.assertFalse(so.items[0].get("against_blanket_order"))
		self.assertFalse(so.get("custom_hdnt"))

	def test_dat_vuot_so_luong_hop_dong_khong_con_bi_chan(self):
		"""`item_het_hm` khai 50 trên hợp đồng A (fixture); đặt 999 vẫn đi."""
		so = self._dat([{"item_code": self.item_het_hm, "qty": 999}])
		self.assertEqual(float(so.items[0].qty), 999.0)

	def test_hop_dong_khai_gia_nhung_bang_gia_trong_thi_la_bao_gia(self):
		for ten in frappe.get_all(
			"Item Price", filters={"item_code": self.item_hd, "selling": 1}, pluck="name"
		):
			frappe.delete_doc("Item Price", ten, force=True)
		so = self._dat([{"item_code": self.item_hd, "qty": 1}])
		self.assertEqual(so.items[0].custom_nguon_gia, bg.NGUON_BAO_GIA)
		self.assertEqual(float(so.items[0].rate), 0.0)

	def test_hang_go_tay_lam_don_thanh_mua_le(self):
		"""Dòng gõ tay không lên Sales Order (patch v1_44): `_xay_don` giữ nó ở
		`flags` cho Quotation, nhưng vẫn đóng dấu đơn là còn dòng chờ báo giá."""
		so = dat_hang._xay_don(
			self.kh_a, {self.item_ngoai: 1},
			[{"ten_hang": "Kim luồn X", "dvt": "Cái", "so_luong": 5, "khong_co_anh": 1}],
			frappe.utils.add_days(frappe.utils.today(), 3), None, None, None,
			frappe.generate_hash(length=12),
		)
		self.assertEqual(so.custom_loai_don, LOAI_DON_BAO_GIA)
		self.assertEqual([d["ten_hang"] for d in so.flags.dong_dat_ngoai], ["Kim luồn X"])
		self.assertFalse(so.meta.has_field("custom_dat_ngoai"))

	def test_dong_gia_het_han_trong_bang_cua_khach_van_la_bao_gia_gia_0(self):
		"""Bảng của khách CÓ một dòng giá cho mã này, nhưng đã hết hiệu lực —
		`gia_bang_gia_nhieu` cố ý bỏ qua. ERPNext tính lại dòng lúc `insert()`
		từ chính `selling_price_list` của đơn; nó không được tự điền lại giá
		đó vào một dòng cổng đã coi là chờ báo giá."""
		hom_nay = frappe.utils.today()
		frappe.get_doc({
			"doctype": "Item Price", "item_code": self.item_boi_so,
			"price_list": self.price_list, "selling": 1, "price_list_rate": 31000,
			"valid_from": frappe.utils.add_days(hom_nay, -60),
			"valid_upto": frappe.utils.add_days(hom_nay, -1),
		}).insert(ignore_permissions=True)
		self.assertIsNone(bg.gia_bang_gia(self.kh_a, self.item_boi_so))

		so = self._dat([{"item_code": self.item_boi_so, "qty": 10}])
		d = so.items[0]
		self.assertEqual(float(d.rate), 0.0)
		self.assertEqual(float(d.price_list_rate), 0.0)
		self.assertEqual(float(d.amount), 0.0)
		self.assertEqual(d.custom_nguon_gia, bg.NGUON_BAO_GIA)
		self.assertEqual(so.custom_loai_don, LOAI_DON_BAO_GIA)

	def test_dong_gia_khac_don_vi_goc_trong_bang_cua_khach_van_la_bao_gia_gia_0(self):
		"""Cùng họ với ca hết hạn: dòng giá khai theo đơn vị KHÁC đơn vị gốc
		(cổng luôn đặt theo `stock_uom`) không phải giá của dòng đơn này."""
		# Đọc đơn vị gốc THẬT của mặt hàng thay vì tin nó là "Cái": fixture
		# đổi đơn vị thì dòng giá dưới đây thành dòng ĐÚNG đơn vị gốc, và bài
		# đỏ ở chỗ khác với một lý do không liên quan.
		dvt_goc = frappe.db.get_value("Item", self.item_boi_so, "stock_uom")
		self.assertTrue(dvt_goc, "tiền đề: mặt hàng phải có đơn vị gốc")
		dvt_khac = frappe.db.get_value("UOM", {"name": ["!=", dvt_goc]}, "name")
		self.assertTrue(dvt_khac, "Site test không có đơn vị tính thứ hai.")
		self.assertNotEqual(dvt_khac, dvt_goc)
		frappe.get_doc({
			"doctype": "Item Price", "item_code": self.item_boi_so,
			"price_list": self.price_list, "selling": 1, "price_list_rate": 880000,
			"uom": dvt_khac,
		}).insert(ignore_permissions=True)
		self.assertIsNone(bg.gia_bang_gia(self.kh_a, self.item_boi_so))

		so = self._dat([{"item_code": self.item_boi_so, "qty": 10}])
		d = so.items[0]
		self.assertEqual(float(d.rate), 0.0)
		self.assertEqual(float(d.price_list_rate), 0.0)
		self.assertEqual(d.custom_nguon_gia, bg.NGUON_BAO_GIA)

	def test_erpnext_khong_tu_dien_gia_cho_dong_cho_bao_gia(self):
		"""Ca mà phép tra giá của ERPNext và của cổng THẬT SỰ lệch nhau: mã là
		biến thể, bảng của khách chỉ khai giá cho mã MẪU. ERPNext rơi về giá
		của mã mẫu (`get_price_list_rate`); cổng thì không — với cổng đây là
		dòng chờ báo giá. Lúc `insert()` ERPNext không được âm thầm đổi `rate
		= 0` thành giá mã mẫu: `_xay_don` phải gửi `price_list_rate = 0`
		tường minh."""
		# Ghi thẳng cột: bài này kiểm đường tính lại giá của đơn, không kiểm
		# cách dựng biến thể. `item_ngoai` đã có giá 54.000 ở `setUp`.
		frappe.db.set_value("Item", self.item_boi_so, "variant_of", self.item_ngoai)
		self.addCleanup(frappe.db.set_value, "Item", self.item_boi_so, "variant_of", None)
		self.assertIsNone(bg.gia_bang_gia(self.kh_a, self.item_boi_so))

		so = self._dat([{"item_code": self.item_boi_so, "qty": 10}])
		d = so.items[0]
		self.assertEqual(float(d.rate), 0.0)
		self.assertEqual(float(d.price_list_rate), 0.0)
		self.assertEqual(d.custom_nguon_gia, bg.NGUON_BAO_GIA)


for _ten, _ham in vars(goc.TestPortalCatalogGop).items():
	if _ten.startswith("_") and not _ten.startswith("__") and callable(_ham):
		if _ten not in vars(TestXayDonBangGia):
			setattr(TestXayDonBangGia, _ten, _ham)
