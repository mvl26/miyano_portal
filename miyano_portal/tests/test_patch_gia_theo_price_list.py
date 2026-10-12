from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import bang_gia_khach as bg
from miyano_portal import dat_hang
from miyano_portal.patches.v1_41 import gia_theo_price_list as patch_moi
from miyano_portal.tests import test_catalog_gop as goc


class TestTruongGiaTheoPriceList(FrappeTestCase):
	def test_truong_moi_co_mat(self):
		soi = frappe.get_meta("Sales Order Item")
		self.assertEqual(
			soi.get_field("custom_nguon_gia").options.split("\n"),
			["", "Bảng giá", "Báo giá"],
		)
		self.assertEqual(soi.get_field("custom_gia_khach_dong_y").fieldtype, "Currency")
		dx = frappe.get_meta("Portal De Xuat Mua")
		self.assertEqual(dx.get_field("ma_lan_dat").fieldtype, "Data")
		self.assertEqual(dx.get_field("phieu_cung_lan_dat").options, "Portal De Xuat Mua")

	def test_lua_chon_moi_giu_ca_gia_tri_cu(self):
		nguon = frappe.get_meta("Portal De Xuat Mua Item").get_field("nguon_gia")
		self.assertEqual(
			nguon.options.split("\n"), ["Hợp đồng", "Bảng giá", "Chờ báo giá"]
		)
		loai = frappe.get_meta("Sales Order").get_field("custom_loai_don")
		self.assertIn("Theo bảng giá", loai.options.split("\n"))
		self.assertIn("Theo HĐNT", loai.options.split("\n"))
		self.assertIn("Mua lẻ", loai.options.split("\n"))

	def _chay_them_truong(self):
		"""`them_truong()` với hai bước CẤU TRÚC (`reload_doc`,
		`create_custom_fields`) bị thay bằng mock: chúng có thể ALTER TABLE,
		tức commit ngầm giữa một bài test trên site đang dùng thật. Phần cần
		kiểm ở đây là phần ghi `options` của `custom_loai_don`."""
		with patch.object(patch_moi.frappe, "reload_doc"), \
				patch.object(patch_moi, "create_custom_fields"):
			patch_moi.them_truong()

	def test_them_truong_chay_hai_lan_chi_them_lua_chon_mot_lan(self):
		ten = frappe.db.get_value(
			"Custom Field", {"dt": "Sales Order", "fieldname": "custom_loai_don"}, "name"
		)
		self.assertTrue(ten, "tiền đề: site phải có Custom Field custom_loai_don")
		# Dựng lại hiện trường TRƯỚC patch (chưa có lựa chọn mới) để lần chạy
		# đầu thật sự phải thêm; `FrappeTestCase` rollback trả lại sau lớp.
		truoc = (frappe.db.get_value("Custom Field", ten, "options") or "").split("\n")
		frappe.db.set_value(
			"Custom Field", ten, "options",
			"\n".join(o for o in truoc if o != "Theo bảng giá"),
		)
		self._chay_them_truong()
		self._chay_them_truong()
		sau = (frappe.db.get_value("Custom Field", ten, "options") or "").split("\n")
		self.assertEqual(sau.count("Theo bảng giá"), 1)
		self.assertEqual(
			[o for o in sau if o != "Theo bảng giá"],
			[o for o in truoc if o != "Theo bảng giá"],
			"các lựa chọn cũ phải còn nguyên, đúng thứ tự",
		)

	def test_them_truong_thieu_custom_loai_don_thi_ghi_error_log(self):
		"""Site thiếu Custom Field `custom_loai_don` (patch v1_8 chưa chạy
		/ field bị xoá tay): không có chỗ nào để thêm "Theo bảng giá", và đơn
		"Theo bảng giá" đầu tiên sẽ hỏng ở phép kiểm Select. Bỏ qua trong im
		lặng là giấu đúng lỗi đó — phải để lại Error Log nói rõ."""
		that = frappe.db.get_value

		def _khong_co_truong(doctype, filters=None, *a, **kw):
			if doctype == "Custom Field" and isinstance(filters, dict) \
					and filters.get("fieldname") == "custom_loai_don":
				return None
			return that(doctype, filters, *a, **kw)

		with patch.object(patch_moi.frappe.db, "get_value", side_effect=_khong_co_truong), \
				patch.object(patch_moi.frappe, "log_error") as ghi_loi:
			self._chay_them_truong()
		self.assertEqual(ghi_loi.call_count, 1)
		noi_dung = " ".join(str(v) for v in ghi_loi.call_args.kwargs.values())
		self.assertIn("custom_loai_don", noi_dung)
		self.assertIn("Theo bảng giá", noi_dung)


class TestChuyenDuLieu(FrappeTestCase):
	"""Phần DỮ LIỆU của patch (spec 2026-10-09 §6). `chuyen_du_lieu()` quét MỌI
	khách của site; các bài dưới chỉ khẳng định về khách `_TEST DX%` của fixture."""

	def setUp(self):
		goc.TestPortalCatalogGop.setUp(self)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_khach_dung_chung_bang_duoc_tach(self):
		frappe.db.set_value("Customer", self.kh_b, "default_price_list", self.price_list)
		patch_moi.chuyen_du_lieu()
		a = frappe.db.get_value("Customer", self.kh_a, "default_price_list")
		b = frappe.db.get_value("Customer", self.kh_b, "default_price_list")
		self.assertTrue(a)
		self.assertTrue(b)
		self.assertNotEqual(a, b)

	def test_khach_chua_co_bang_duoc_tao_bang(self):
		frappe.db.set_value("Customer", self.kh_b, "default_price_list", None)
		patch_moi.chuyen_du_lieu()
		b = frappe.db.get_value("Customer", self.kh_b, "default_price_list")
		self.assertTrue(b)
		self.assertEqual(
			frappe.get_all("Customer", filters={"default_price_list": b}, pluck="name"),
			[self.kh_b],
		)

	def test_gia_hop_dong_duoc_chep_sang_bang_gia(self):
		"""Hợp đồng A khai 125.000 cho `item_hd`; xoá dòng giá để mô phỏng
		khách chỉ có giá nhờ hợp đồng (ca của Minh Đức)."""
		for ten in frappe.get_all(
			"Item Price", filters={"item_code": self.item_hd, "selling": 1}, pluck="name"
		):
			frappe.delete_doc("Item Price", ten, force=True)
		self.assertIsNone(bg.gia_bang_gia(self.kh_a, self.item_hd))
		patch_moi.chuyen_du_lieu()
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_hd), 125000.0)

	def _dong_gia_cua(self, *khach):
		bang = [frappe.db.get_value("Customer", kh, "default_price_list") for kh in khach]
		return sorted(
			(d.price_list, d.name, float(d.price_list_rate), str(d.valid_from), str(d.valid_upto))
			for d in frappe.get_all(
				"Item Price", filters={"price_list": ["in", bang], "selling": 1},
				fields=["price_list", "name", "price_list_rate", "valid_from", "valid_upto"],
			)
		)

	def test_chay_hai_lan_khong_doi_ket_qua(self):
		patch_moi.chuyen_du_lieu()
		truoc = frappe.db.count("Item Price", {"selling": 1})
		so_bang = frappe.db.count("Price List")
		bang = frappe.db.get_value("Customer", self.kh_a, "default_price_list")
		dong_truoc = self._dong_gia_cua(self.kh_a, self.kh_b)
		self.assertTrue(dong_truoc, "tiền đề: khách fixture có dòng giá sau lần chạy đầu")
		patch_moi.chuyen_du_lieu()
		self.assertEqual(frappe.db.count("Item Price", {"selling": 1}), truoc)
		self.assertEqual(frappe.db.count("Price List"), so_bang)
		self.assertEqual(
			frappe.db.get_value("Customer", self.kh_a, "default_price_list"), bang
		)
		# Không chỉ đếm: từng dòng giữ nguyên tên, giá và hiệu lực.
		self.assertEqual(self._dong_gia_cua(self.kh_a, self.kh_b), dong_truoc)

	def test_khach_vo_hieu_hoa_co_hop_dong_van_duoc_chep_gia(self):
		"""§6 bước 3: MỌI khách có hợp đồng Selling đã ký, kể cả khách đã vô
		hiệu hoá — và giá của nó vào bảng của RIÊNG nó, không vào bảng của
		khách đang hoạt động mà nó còn trỏ tới."""
		# Đọc lại bảng của A thay vì tin `self.price_list`: rollback mỗi CLASS một
		# lần, nên B còn trỏ chung từ method trước là hook `on_submit` trong
		# `setUp` đã tách A sang bảng khác.
		bang_a = frappe.db.get_value("Customer", self.kh_a, "default_price_list")
		frappe.db.set_value("Customer", self.kh_b, "default_price_list", bang_a)
		self.addCleanup(frappe.db.set_value, "Customer", self.kh_b, "disabled", 0)
		frappe.db.set_value("Customer", self.kh_b, "disabled", 1)
		# Cùng lý do: dọn giá mã của B mà method trước có thể đã để lại.
		frappe.db.delete("Item Price", {"item_code": self.item_chi_b})
		self.assertIsNone(bg.gia_bang_gia(self.kh_a, self.item_chi_b))
		patch_moi.chuyen_du_lieu()
		self.assertEqual(
			frappe.db.get_value("Customer", self.kh_a, "default_price_list"), bang_a
		)
		bang_b = frappe.db.get_value("Customer", self.kh_b, "default_price_list")
		self.assertNotEqual(bang_b, bang_a)
		self.assertEqual(bg.gia_bang_gia(self.kh_b, self.item_chi_b), 50000.0)
		self.assertIsNone(bg.gia_bang_gia(self.kh_a, self.item_chi_b))

	def test_don_bao_gia_dang_do_duoc_dong_dau(self):
		kq = dat_hang.tao_sales_order(
			self.kh_a, items=[{"item_code": self.item_boi_so, "qty": 10}],
			request_id=frappe.generate_hash(length=12),
		)
		dong = frappe.db.get_value("Sales Order Item", {"parent": kq["sales_order"]}, "name")
		frappe.db.set_value("Sales Order Item", dong, "custom_nguon_gia", None)
		patch_moi.chuyen_du_lieu()
		self.assertEqual(
			frappe.db.get_value("Sales Order Item", dong, "custom_nguon_gia"), "Báo giá"
		)

	def test_mot_khach_loi_khong_chan_khach_khac(self):
		"""Site thật có dữ liệu hỏng: khách B ném lỗi SAU KHI đã ghi dở (bảng đã
		tạo, đã gán) thì khách A vẫn phải được chép giá hợp đồng; lỗi nằm trong
		Error Log kèm tên khách B, và không mảnh nào của B còn lại."""
		frappe.db.set_value("Customer", self.kh_b, "default_price_list", None)
		for ten in frappe.get_all(
			"Item Price", filters={"item_code": self.item_hd, "selling": 1}, pluck="name"
		):
			frappe.delete_doc("Item Price", ten, force=True)
		bang_truoc = set(frappe.get_all("Price List", pluck="name"))
		that = bg.dam_bao_bang_gia_rieng
		da_ghi = []

		def _hong_voi_b(customer):
			ten = that(customer)
			if customer == self.kh_b:
				# Tiền đề của bài: lỗi tới SAU khi việc ghi đã xảy ra.
				da_ghi.append((
					frappe.db.exists("Price List", ten),
					frappe.db.get_value("Customer", customer, "default_price_list"),
				))
				raise RuntimeError("bang gia hong")
			return ten

		with patch.object(bg, "dam_bao_bang_gia_rieng", side_effect=_hong_voi_b):
			patch_moi.chuyen_du_lieu()   # không được ném lỗi

		self.assertTrue(da_ghi and all(ten and gan == ten for ten, gan in da_ghi), da_ghi)
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_hd), 125000.0)
		self.assertFalse(frappe.db.get_value("Customer", self.kh_b, "default_price_list"))
		for ten, _gan in da_ghi:
			self.assertFalse(frappe.db.exists("Price List", ten), "bảng ghi dở của B còn sót")
		self.assertEqual(
			[t for t in set(frappe.get_all("Price List", pluck="name")) - bang_truoc
			 if self.kh_b in t],
			[],
		)
		self.assertIsNone(bg.gia_bang_gia(self.kh_b, self.item_chi_b))
		log = frappe.get_all(
			"Error Log", filters={"method": ["like", f"%{self.kh_b}%"]}, pluck="name"
		)
		self.assertTrue(log, "lỗi của khách B phải nằm trong Error Log kèm tên khách")
		frappe.db.delete("Error Log", {"name": ["in", log]})


for _ten, _ham in vars(goc.TestPortalCatalogGop).items():
	if _ten.startswith("_") and not _ten.startswith("__") and callable(_ham):
		if _ten not in vars(TestChuyenDuLieu):
			setattr(TestChuyenDuLieu, _ten, _ham)
