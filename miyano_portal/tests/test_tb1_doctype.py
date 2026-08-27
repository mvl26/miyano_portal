"""Master thiết bị — chuẩn hoá mã, chống trùng, ràng buộc khoa cùng bệnh viện.

Dùng khách hàng ZZTB RIÊNG của bộ test này, không mượn khách thật trên site
(tiền lệ vỡ test: xem docs/CHANGELOG-khac-phuc-BA-v2.md dòng 302).
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.kho import vat_tu as vat_tu_mod

KHACH = "ZZTB Benh Vien"


class TestThietBiDoctype(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self._don()
		self.addCleanup(self._don)
		frappe.get_doc({
			"doctype": "Customer", "customer_name": KHACH,
			"customer_type": "Company", "customer_group": "All Customer Groups",
			"territory": "All Territories",
		}).insert(ignore_permissions=True)
		self.kp = frappe.get_doc({
			"doctype": "Customer Department", "customer": KHACH,
			"ten_khoa_phong": "ZZTB Khoa Xet nghiem", "ma_khoa": "ZZTBXN",
		}).insert(ignore_permissions=True)

	def _don(self):
		khach_khac = "ZZTB Benh Vien Khac"
		for khach in (KHACH, khach_khac):
			for dt in ("Customer Equipment", "Customer Department"):
				for r in frappe.get_all(dt, filters={"customer": khach}, pluck="name"):
					frappe.delete_doc(dt, r, force=True, ignore_permissions=True)
			if frappe.db.exists("Customer", khach):
				frappe.delete_doc("Customer", khach, force=True, ignore_permissions=True)

	def _may(self, **kw):
		du_lieu = {
			"doctype": "Customer Equipment", "customer": KHACH,
			"ma_thiet_bi": "xn500-01", "ten_thiet_bi": "Máy XN-500",
		}
		du_lieu.update(kw)
		return frappe.get_doc(du_lieu).insert(ignore_permissions=True)

	def test_ma_duoc_viet_hoa_va_cat_khoang_trang(self):
		may = self._may(ma_thiet_bi="  xn500-01  ")
		self.assertEqual(may.ma_thiet_bi, "XN500-01")

	def test_thieu_ten_bi_chan(self):
		with self.assertRaises(frappe.ValidationError):
			self._may(ten_thiet_bi="   ")

	def test_thieu_ma_bi_chan(self):
		with self.assertRaises(frappe.ValidationError):
			self._may(ma_thiet_bi="   ")

	def test_ma_trung_trong_cung_benh_vien_bi_chan(self):
		self._may()
		with self.assertRaises(frappe.ValidationError):
			self._may(ten_thiet_bi="Máy khác")

	def test_ten_trung_khac_dau_khac_hoa_thuong_bi_chan(self):
		self._may(ten_thiet_bi="Máy Xét nghiệm")
		with self.assertRaises(frappe.ValidationError):
			self._may(ma_thiet_bi="XN500-02", ten_thiet_bi="may xet nghiem")

	def test_khoa_phong_khac_benh_vien_bi_chan(self):
		khach_khac = frappe.get_doc({
			"doctype": "Customer", "customer_name": "ZZTB Benh Vien Khac",
			"customer_type": "Company", "customer_group": "All Customer Groups",
			"territory": "All Territories",
		}).insert(ignore_permissions=True)
		self.addCleanup(
			frappe.delete_doc, "Customer", khach_khac.name, force=True, ignore_permissions=True
		)
		kp_khac = frappe.get_doc({
			"doctype": "Customer Department", "customer": khach_khac.name,
			"ten_khoa_phong": "ZZTB Khoa La",
		}).insert(ignore_permissions=True)
		self.addCleanup(
			frappe.delete_doc, "Customer Department", kp_khac.name,
			force=True, ignore_permissions=True,
		)
		with self.assertRaises(frappe.ValidationError):
			self._may(khoa_phong=kp_khac.name)

	def test_khoa_phong_de_trong_la_may_dung_chung(self):
		may = self._may()
		self.assertIsNone(may.khoa_phong)

	def test_mac_dinh_dang_hoat_dong(self):
		self.assertEqual(self._may().active, 1)


class TestVatTuMaySuDung(FrappeTestCase):
	"""Bảng "Máy sử dụng" là DANH MỤC TƯƠNG THÍCH, không phải số liệu."""

	def setUp(self):
		frappe.set_user("Administrator")
		self._don()
		self.addCleanup(self._don)
		frappe.get_doc({
			"doctype": "Customer", "customer_name": KHACH,
			"customer_type": "Company", "customer_group": "All Customer Groups",
			"territory": "All Territories",
		}).insert(ignore_permissions=True)
		self.kho = frappe.get_doc({
			"doctype": "Customer Warehouse", "customer": KHACH,
			"ten_kho": "ZZTB Kho", "ma_kho": "ZZTB",
			"ngay_bat_dau": frappe.utils.today(),
		}).insert(ignore_permissions=True)
		self.may = frappe.get_doc({
			"doctype": "Customer Equipment", "customer": KHACH,
			"ma_thiet_bi": "XN500-01", "ten_thiet_bi": "Máy XN-500",
		}).insert(ignore_permissions=True)

	def _don(self):
		"""Mỗi doctype PHẢI có filter tường minh của riêng nó — không filter
		mặc định khớp-tất-cả. Review vòng 1 (task-2, Minor #4): bản trước
		đây khởi tạo `flt` mặc định `{"kho": ["like", "%"]}` rồi mới override
		theo từng nhánh if/elif — an toàn tình cờ vì cả ba doctype hiện có
		đều rơi vào một nhánh override, nhưng thêm doctype thứ tư mà quên
		viết nhánh cho nó sẽ ÂM THẦM kế thừa filter khớp-tất-cả và xoá sạch
		doctype đó trên toàn site (đúng bẫy mà nguyên tắc #3 của kế hoạch
		cấm). Không có `else` an toàn: doctype lạ phải NÉM LỖI ngay, không
		được lặng lẽ bỏ qua hay xoá tất."""
		khos = frappe.get_all("Customer Warehouse", filters={"customer": KHACH}, pluck="name")
		filters_theo_dt = {
			"Customer Warehouse Item": {"kho": ["in", khos or [""]]},
			"Customer Equipment": {"customer": KHACH},
			"Customer Warehouse": {"customer": KHACH},
		}
		for dt in ("Customer Warehouse Item", "Customer Equipment", "Customer Warehouse"):
			for r in frappe.get_all(dt, filters=filters_theo_dt[dt], pluck="name"):
				frappe.delete_doc(dt, r, force=True, ignore_permissions=True)
		if frappe.db.exists("Customer", KHACH):
			frappe.delete_doc("Customer", KHACH, force=True, ignore_permissions=True)

	def _vat_tu(self, **kw):
		du_lieu = {
			"doctype": "Customer Warehouse Item", "kho": self.kho.name,
			"ma_vat_tu": "ZZTB-HC1", "ten_vat_tu": "Hoá chất ZZTB", "dvt": "Hộp",
		}
		du_lieu.update(kw)
		return frappe.get_doc(du_lieu).insert(ignore_permissions=True)

	def test_gan_duoc_nhieu_may(self):
		may2 = frappe.get_doc({
			"doctype": "Customer Equipment", "customer": KHACH,
			"ma_thiet_bi": "XN500-02", "ten_thiet_bi": "Máy XN-500 số 2",
		}).insert(ignore_permissions=True)
		vt = self._vat_tu(may_su_dung=[
			{"thiet_bi": self.may.name}, {"thiet_bi": may2.name},
		])
		# Đọc lại TỪ CSDL, không assert trên doc trong bộ nhớ (review vòng 1,
		# Important #2): nếu db_update() của bảng con lỗi âm thầm, doc trong
		# bộ nhớ vẫn "đúng" (nó chưa từng bị ghi đè) trong khi CSDL sai — chỉ
		# đọc lại mới lộ ra khác biệt đó.
		lai = frappe.get_doc("Customer Warehouse Item", vt.name)
		self.assertEqual(
			{r.thiet_bi for r in lai.may_su_dung}, {self.may.name, may2.name}
		)

	def test_bang_trong_la_vat_tu_dung_chung(self):
		self.assertEqual(self._vat_tu().may_su_dung, [])

	def test_may_cua_benh_vien_khac_bi_chan(self):
		khach2 = frappe.get_doc({
			"doctype": "Customer", "customer_name": "ZZTB Benh Vien Khac",
			"customer_type": "Company", "customer_group": "All Customer Groups",
			"territory": "All Territories",
		}).insert(ignore_permissions=True)
		self.addCleanup(
			frappe.delete_doc, "Customer", khach2.name, force=True, ignore_permissions=True
		)
		may_la = frappe.get_doc({
			"doctype": "Customer Equipment", "customer": khach2.name,
			"ma_thiet_bi": "LA-01", "ten_thiet_bi": "Máy lạ",
		}).insert(ignore_permissions=True)
		self.addCleanup(
			frappe.delete_doc, "Customer Equipment", may_la.name,
			force=True, ignore_permissions=True,
		)
		with self.assertRaises(frappe.ValidationError):
			self._vat_tu(may_su_dung=[{"thiet_bi": may_la.name}])

	def test_gan_trung_mot_may_hai_lan_bi_gop(self):
		vt = self._vat_tu(may_su_dung=[
			{"thiet_bi": self.may.name}, {"thiet_bi": self.may.name},
		])
		# Đọc lại TỪ CSDL — cùng lý do với test_gan_duoc_nhieu_may ở trên.
		lai = frappe.get_doc("Customer Warehouse Item", vt.name)
		self.assertEqual(len(lai.may_su_dung), 1)

	# ------------------------------------------------------------------
	# Review vòng 1 (task-2), Important #1 — `api/kho.py::kho_vat_tu_tao`/
	# `kho_vat_tu_sua` chuyển `_parse_payload(payload)` NGUYÊN XI xuống
	# `vat_tu.tao()`/`vat_tu.sua()` làm `du_lieu`, không lọc khoá nào. Đường
	# `may_su_dung` từ client vì vậy là CODE SỐNG, không phải code chết —
	# ba ca dưới đây đi thẳng qua `vat_tu_mod.tao()`/`vat_tu_mod.sua()`
	# (không phải `frappe.get_doc().insert()` thẳng như `_vat_tu()` ở trên),
	# đúng con đường một request thật từ client sẽ đi qua.
	# ------------------------------------------------------------------

	def test_tao_qua_vat_tu_mod_voi_may_su_dung(self):
		ket = vat_tu_mod.tao(self.kho.name, {
			"ma_vat_tu": "ZZTB-HC2", "ten_vat_tu": "Hoá chất ZZTB 2", "dvt": "Hộp",
			"may_su_dung": [self.may.name],
		})
		lai = frappe.get_doc("Customer Warehouse Item", ket["name"])
		self.assertEqual({r.thiet_bi for r in lai.may_su_dung}, {self.may.name})

	def test_sua_khong_gui_khoa_may_su_dung_giu_nguyen_bang_may(self):
		"""Ca CHỐNG MẤT DỮ LIỆU — quan trọng nhất trong ba ca này: một request
		sửa vật tư không đụng gì tới máy (ví dụ chỉ đổi tên) không được lặng
		lẽ xoá sạch bảng máy đang có. Đây chính là điều `if "may_su_dung" in
		du_lieu` trong `vat_tu.sua()` phải bảo đảm — thiếu khoá phải khác
		hẳn với có khoá mà rỗng (ca kế tiếp)."""
		vt = self._vat_tu(may_su_dung=[{"thiet_bi": self.may.name}])
		vat_tu_mod.sua(self.kho.name, vt.name, {"ten_vat_tu": "Đổi tên, không đụng máy"})
		lai = frappe.get_doc("Customer Warehouse Item", vt.name)
		self.assertEqual({r.thiet_bi for r in lai.may_su_dung}, {self.may.name})

	def test_sua_gui_bang_rong_xoa_het_may(self):
		"""Đối chứng với ca trên: gửi `may_su_dung=[]` (CÓ khoá, danh sách
		rỗng) phải xoá hết, phân biệt rõ với KHÔNG gửi khoá."""
		vt = self._vat_tu(may_su_dung=[{"thiet_bi": self.may.name}])
		vat_tu_mod.sua(self.kho.name, vt.name, {"may_su_dung": []})
		lai = frappe.get_doc("Customer Warehouse Item", vt.name)
		self.assertEqual(lai.may_su_dung, [])

	def test_ra_dict_tra_ve_may_su_dung(self):
		"""Review vòng 1, Important #3 — `ra_dict()` từng không trả
		`may_su_dung`: client ghi được nhưng response không có gì để hiện
		lại ngay sau khi lưu."""
		vt = self._vat_tu(may_su_dung=[{"thiet_bi": self.may.name}])
		row = vat_tu_mod.ra_dict(vt.name)
		self.assertEqual(
			[(r["thiet_bi"], r["ten_thiet_bi"]) for r in row["may_su_dung"]],
			[(self.may.name, self.may.ten_thiet_bi)],
		)
