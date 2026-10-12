"""Nguồn giá duy nhất của cổng: Price List của khách (spec 2026-10-09 §3, §5.3)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from miyano_portal import bang_gia_khach as bg
from miyano_portal.tests.fixtures_de_xuat import dung_fixture

BANG_A = "_TEST DX BGK A"


def _bang(ten):
	if not frappe.db.exists("Price List", ten):
		frappe.get_doc({
			"doctype": "Price List", "price_list_name": ten,
			"currency": "VND", "selling": 1, "enabled": 1,
		}).insert(ignore_permissions=True)
	return ten


def _gia(item, bang, rate, **them):
	return frappe.get_doc({
		"doctype": "Item Price", "item_code": item, "price_list": bang,
		"selling": 1, "price_list_rate": rate, **them,
	}).insert(ignore_permissions=True)


class TestBangGiaKhach(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		f = dung_fixture(self)
		self.kh_a, self.kh_b, self.item = f.kh_a, f.kh_b, f.item
		for ten in frappe.get_all(
			"Item Price", filters={"item_code": self.item, "selling": 1}, pluck="name"
		):
			frappe.delete_doc("Item Price", ten, force=True)
		for kh in (self.kh_a, self.kh_b):
			frappe.db.set_value("Customer", kh, "default_price_list", None)
		for ten in frappe.get_all(
			"Price List", filters={"name": ["like", "Bảng giá _TEST DX%"]}, pluck="name"
		):
			frappe.delete_doc("Price List", ten, force=True)
		frappe.db.set_value("Customer", self.kh_a, "default_price_list", _bang(BANG_A))

	def test_co_gia_thi_tra_gia(self):
		_gia(self.item, BANG_A, 54000)
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item), 54000.0)

	def test_khong_co_dong_gia_tra_None(self):
		self.assertIsNone(bg.gia_bang_gia(self.kh_a, self.item))

	def test_gia_0_la_chua_khai_gia(self):
		_gia(self.item, BANG_A, 0)
		self.assertIsNone(bg.gia_bang_gia(self.kh_a, self.item))

	def test_khach_chua_co_bang_gia_tra_None(self):
		self.assertIsNone(bg.gia_bang_gia(self.kh_b, self.item))

	def test_gia_cua_bang_khach_khac_khong_lo_sang(self):
		_gia(self.item, _bang("_TEST DX BGK KHAC"), 99000)
		self.assertIsNone(bg.gia_bang_gia(self.kh_a, self.item))

	def test_bo_qua_dong_gia_het_hieu_luc_va_chua_toi_ngay(self):
		_gia(self.item, BANG_A, 11000, valid_from=add_days(today(), -30),
		     valid_upto=add_days(today(), -1))
		_gia(self.item, BANG_A, 22000, valid_from=add_days(today(), 5))
		self.assertIsNone(bg.gia_bang_gia(self.kh_a, self.item))

	def test_hai_dong_hop_le_lay_valid_from_moi_nhat(self):
		_gia(self.item, BANG_A, 11000, valid_from=add_days(today(), -30))
		_gia(self.item, BANG_A, 22000, valid_from=add_days(today(), -2))
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item), 22000.0)

	def test_bo_qua_dong_gia_theo_don_vi_khac_don_vi_goc(self):
		if not frappe.db.exists("UOM", "_TEST DX THUNG"):
			frappe.get_doc({"doctype": "UOM", "uom_name": "_TEST DX THUNG"}).insert()
		_gia(self.item, BANG_A, 900000, uom="_TEST DX THUNG")
		self.assertIsNone(bg.gia_bang_gia(self.kh_a, self.item))

	def test_tra_theo_lo_chi_chua_ma_co_gia(self):
		_gia(self.item, BANG_A, 54000)
		kq = bg.gia_bang_gia_nhieu(self.kh_a, [self.item, "KHONG-TON-TAI"])
		self.assertEqual(kq, {self.item: 54000.0})

	def test_bang_rieng_san_co_thi_giu_nguyen(self):
		self.assertEqual(bg.dam_bao_bang_gia_rieng(self.kh_a), BANG_A)

	def test_khach_vo_hieu_hoa_con_tro_vao_khong_lam_chu_bang_bi_tach(self):
		"""Chủ bảng hỏi: khách khác đã vô hiệu hoá vẫn trỏ về bảng này không
		phải là "dùng chung" — giữ nguyên bảng, không tách thừa."""
		frappe.db.set_value("Customer", self.kh_b, "default_price_list", BANG_A)
		self.addCleanup(frappe.db.set_value, "Customer", self.kh_b, "disabled", 0)
		frappe.db.set_value("Customer", self.kh_b, "disabled", 1)
		self.assertEqual(bg.dam_bao_bang_gia_rieng(self.kh_a), BANG_A)

	def test_khach_vo_hieu_hoa_hoi_thi_khong_nhan_bang_cua_khach_khac(self):
		"""Khách đã vô hiệu hoá hỏi: bảng nó trỏ tới đang là của một khách
		ĐANG HOẠT ĐỘNG khác, nên nó phải được tách bảng riêng."""
		frappe.db.set_value("Customer", self.kh_b, "default_price_list", BANG_A)
		self.addCleanup(frappe.db.set_value, "Customer", self.kh_b, "disabled", 0)
		frappe.db.set_value("Customer", self.kh_b, "disabled", 1)
		ten = bg.dam_bao_bang_gia_rieng(self.kh_b)
		self.assertNotEqual(ten, BANG_A)
		self.assertEqual(frappe.db.get_value("Customer", self.kh_b, "default_price_list"), ten)
		self.assertEqual(frappe.db.get_value("Customer", self.kh_a, "default_price_list"), BANG_A)

	def _bang_khong_dung_duoc(self, **thuoc_tinh):
		"""Gán cho kh_b một bảng có giá nhưng KHÔNG dùng được làm bảng giá bán."""
		ten = "_TEST DX BGK HONG"
		if not frappe.db.exists("Price List", ten):
			frappe.get_doc({
				"doctype": "Price List", "price_list_name": ten,
				"currency": "VND", "selling": 1, "buying": 1, "enabled": 1,
			}).insert(ignore_permissions=True)
		# Bảng sống qua các test trong lớp: đưa về trạng thái dùng được trước
		# khi chèn giá (Item Price từ chối bảng đã tắt).
		frappe.db.set_value("Price List", ten, {"enabled": 1, "selling": 1})
		_gia(self.item, ten, 33000)
		frappe.db.set_value("Price List", ten, thuoc_tinh)
		frappe.db.set_value("Customer", self.kh_b, "default_price_list", ten)
		return ten

	def test_bang_mac_dinh_da_tat_thi_coi_nhu_chua_co_bang(self):
		"""Final-fix S-2: bảng đã bị tắt không phải là bảng giá của khách —
		tạo bảng riêng và gán, không trả về bảng tắt."""
		hong = self._bang_khong_dung_duoc(enabled=0)
		ten = bg.dam_bao_bang_gia_rieng(self.kh_b)
		self.assertEqual(ten, f"Bảng giá {self.kh_b}")
		self.assertNotEqual(ten, hong)
		self.assertEqual(
			frappe.db.get_value("Customer", self.kh_b, "default_price_list"), ten
		)
		self.assertEqual(
			frappe.db.get_value("Price List", ten, ["selling", "enabled"]), (1, 1)
		)
		# "Coi như chưa có bảng": không chép giá từ bảng không dùng được.
		self.assertEqual(frappe.db.count("Item Price", {"price_list": ten}), 0)

	def test_bang_mac_dinh_khong_phai_bang_gia_ban_thi_coi_nhu_chua_co_bang(self):
		hong = self._bang_khong_dung_duoc(selling=0)
		ten = bg.dam_bao_bang_gia_rieng(self.kh_b)
		self.assertEqual(ten, f"Bảng giá {self.kh_b}")
		self.assertNotEqual(ten, hong)
		self.assertEqual(
			frappe.db.get_value("Customer", self.kh_b, "default_price_list"), ten
		)
		self.assertEqual(frappe.db.count("Item Price", {"price_list": ten}), 0)

	def test_khach_chua_co_bang_thi_tao_va_gan(self):
		ten = bg.dam_bao_bang_gia_rieng(self.kh_b)
		self.assertEqual(ten, f"Bảng giá {self.kh_b}")
		self.assertEqual(
			frappe.db.get_value("Customer", self.kh_b, "default_price_list"), ten
		)
		self.assertEqual(
			frappe.db.get_value("Price List", ten, ["selling", "currency", "enabled"]),
			(1, "VND", 1),
		)

	def test_bang_dung_chung_thi_tach_va_chep_gia(self):
		_gia(self.item, BANG_A, 54000)
		frappe.db.set_value("Customer", self.kh_b, "default_price_list", BANG_A)
		ten = bg.dam_bao_bang_gia_rieng(self.kh_b)
		self.assertNotEqual(ten, BANG_A)
		self.assertEqual(bg.gia_bang_gia(self.kh_b, self.item), 54000.0)
		# Khách kia giữ nguyên bảng cũ — chỉ người được gọi mới bị tách.
		self.assertEqual(
			frappe.db.get_value("Customer", self.kh_a, "default_price_list"), BANG_A
		)

	def test_goi_hai_lan_khong_tao_bang_thu_hai(self):
		a = bg.dam_bao_bang_gia_rieng(self.kh_b)
		self.assertEqual(bg.dam_bao_bang_gia_rieng(self.kh_b), a)

	def test_dong_gia_gan_khach_khac_khong_lo_sang(self):
		_gia(self.item, BANG_A, 77000, customer=self.kh_b)
		self.assertIsNone(bg.gia_bang_gia(self.kh_a, self.item))

	def test_dong_gan_rieng_khach_thang_dong_chung(self):
		_gia(self.item, BANG_A, 50000, valid_from=add_days(today(), -1))
		_gia(self.item, BANG_A, 40000, customer=self.kh_a, valid_from=add_days(today(), -10))
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item), 40000.0)

	def test_tach_bang_khong_chep_dong_gan_khach_khac(self):
		_gia(self.item, BANG_A, 50000)
		frappe.db.set_value("Customer", self.kh_b, "default_price_list", BANG_A)
		# Dòng gắn riêng kh_a trong bảng chung: kh_b tách ra không được thấy.
		item2 = frappe.get_all("Item", filters={"name": ["!=", self.item]}, limit=1, pluck="name")[0]
		_gia(item2, BANG_A, 88000, customer=self.kh_a)
		ten = bg.dam_bao_bang_gia_rieng(self.kh_b)
		self.assertEqual(bg.gia_bang_gia(self.kh_b, self.item), 50000.0)
		self.assertEqual(
			frappe.db.count("Item Price", {"price_list": ten, "item_code": item2}), 0
		)
		frappe.db.delete("Item Price", {"item_code": item2, "price_list": BANG_A})

	def test_tach_bang_giu_valid_from(self):
		tu = add_days(today(), -7)
		_gia(self.item, BANG_A, 50000, valid_from=tu)
		frappe.db.set_value("Customer", self.kh_b, "default_price_list", BANG_A)
		ten = bg.dam_bao_bang_gia_rieng(self.kh_b)
		self.assertEqual(
			str(frappe.db.get_value("Item Price", {"price_list": ten, "item_code": self.item}, "valid_from")),
			str(tu),
		)

	def test_ten_bang_trung_thi_them_hau_to(self):
		_bang(f"Bảng giá {self.kh_b}")
		ten = bg.dam_bao_bang_gia_rieng(self.kh_b)
		self.assertNotEqual(ten, f"Bảng giá {self.kh_b}")
		self.assertTrue(ten.startswith(f"Bảng giá {self.kh_b} ("))
