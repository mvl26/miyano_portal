"""Máy trên DÒNG phiếu xuất — BR-TB-1/2/4/5.

`thiet_bi_mac_dinh` ở đầu phiếu là TIỆN ÍCH NHẬP LIỆU, không ghi sổ và
không báo cáo nào được đọc nó — test cuối file khẳng định điều đó.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

KHACH = "ZZTB2 Benh Vien"


class TestMayTrenPhieuXuat(FrappeTestCase):
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
			"ten_kho": "ZZTB2 Kho", "ma_kho": "ZZTB2",
			"ngay_bat_dau": frappe.utils.add_days(frappe.utils.today(), -30),
		}).insert(ignore_permissions=True)
		self.kp_a = self._khoa("ZZTB2 Khoa A", "ZZTB2A")
		self.kp_b = self._khoa("ZZTB2 Khoa B", "ZZTB2B")
		self.may_a = self._may("XN500-01", "Máy XN-500", self.kp_a.name)
		self.may_b = self._may("XN500-02", "Máy XN-500 số 2", None)
		self.may_khoa_a = self.may_a
		self.may_la = self._may_benh_vien_khac()
		self.vat_tu = frappe.get_doc({
			"doctype": "Customer Warehouse Item", "kho": self.kho.name,
			"ma_vat_tu": "ZZTB2-HC1", "ten_vat_tu": "Hoá chất ZZTB2", "dvt": "Hộp",
		}).insert(ignore_permissions=True)
		self.lo = "LO-ZZTB2"
		nhap = frappe.get_doc({
			"doctype": "Customer Stock Receipt", "kho": self.kho.name,
			"ngay": frappe.utils.add_days(frappe.utils.today(), -7),
			"loai_nhap": "Nhập khác",
			"items": [{
				"vat_tu": self.vat_tu.name, "so_lo": self.lo, "so_luong": 100,
				"don_gia": 50000,
			}],
		}).insert(ignore_permissions=True)
		nhap.submit()

	def _khoa(self, ten, ma):
		# SỬA (đợt sửa cuối, C-2): KHÔNG điền `kho` — đúng đường onboarding
		# thật (`api/nhan_su.py::nhan_su_import_commit`, HDSD-phan-quyen-
		# khoa-phong.md:75 dạy "Kho — để trống"). Trước đây fixture này CỐ
		# TÌNH điền `kho` để né lỗ hổng "khoa không gắn kho bị chặn nhầm" ở
		# `_validate_khoa_phong_thuoc_kho()` — điền tay như vậy che mất lỗ,
		# vì mọi test dùng `_khoa()` không bao giờ chạm nhánh khoa-không-
		# gắn-kho mà onboarding thật tạo ra. Hàm đó nay đã sửa để so
		# `customer` (đúng khuôn `_khoa_cua_kho()`), khoa không gắn `kho`
		# vẫn ghi sổ được.
		return frappe.get_doc({
			"doctype": "Customer Department", "customer": KHACH,
			"ten_khoa_phong": ten, "ma_khoa": ma,
		}).insert(ignore_permissions=True)

	def _may(self, ma, ten, khoa_phong):
		return frappe.get_doc({
			"doctype": "Customer Equipment", "customer": KHACH,
			"ma_thiet_bi": ma, "ten_thiet_bi": ten, "khoa_phong": khoa_phong,
		}).insert(ignore_permissions=True)

	def _may_benh_vien_khac(self):
		"""Máy CÓ THẬT nhưng của bệnh viện khác — dùng cho ca BR-TB-1. Phải là
		máy thật chứ không phải docname bịa, nếu không ca test chỉ chứng minh
		được "docname không tồn tại thì lỗi", vốn là chuyện khác."""
		if not frappe.db.exists("Customer", "ZZTB2 Benh Vien Khac"):
			frappe.get_doc({
				"doctype": "Customer", "customer_name": "ZZTB2 Benh Vien Khac",
				"customer_type": "Company", "customer_group": "All Customer Groups",
				"territory": "All Territories",
			}).insert(ignore_permissions=True)
		return frappe.get_doc({
			"doctype": "Customer Equipment", "customer": "ZZTB2 Benh Vien Khac",
			"ma_thiet_bi": "LA-01", "ten_thiet_bi": "Máy lạ",
		}).insert(ignore_permissions=True)

	def _xuat(self, thiet_bi=None, khoa_phong=None, loai_xuat="Xuất sử dụng",
	          thiet_bi_mac_dinh=None, submit=True):
		"""Lập một phiếu xuất một dòng. `submit=False` để giữ phiếu ở nháp cho
		các ca cần tạo trước / bật cờ sau."""
		doc = frappe.get_doc({
			"doctype": "Customer Stock Issue", "kho": self.kho.name,
			"ngay": frappe.utils.today(), "loai_xuat": loai_xuat,
			"khoa_phong": khoa_phong or self.kp_a.name,
			"thiet_bi_mac_dinh": thiet_bi_mac_dinh,
			"items": [{
				"vat_tu": self.vat_tu.name, "so_lo": self.lo,
				"so_luong": 2, "thiet_bi": thiet_bi,
			}],
		}).insert(ignore_permissions=True)
		if submit:
			doc.submit()
		return doc

	def _don(self):
		"""Dọn CHỈ dữ liệu của hai khách hàng ZZTB2 của bộ test này.

		TUYỆT ĐỐI không `frappe.get_all(dt, pluck="name")` không lọc rồi xoá —
		erptest.local là site làm việc thật, có dữ liệu demo của nhiều bệnh
		viện và các bộ test khác. Một vòng xoá không lọc sẽ dọn sạch site và
		chỉ lộ ra ở lần chạy test tiếp theo của người khác.
		"""
		khach = [KHACH, "ZZTB2 Benh Vien Khac"]
		khos = frappe.get_all(
			"Customer Warehouse", filters={"customer": ["in", khach]}, pluck="name"
		) or [""]
		# Xoá thẳng bằng SQL (frappe.db.delete), KHÔNG qua frappe.delete_doc():
		# Customer Stock Issue/Receipt là submittable — delete_doc() chặn xoá
		# bản ghi docstatus=1 vô điều kiện (force chỉ bỏ qua kiểm tra LIÊN
		# KẾT, không bỏ qua kiểm tra docstatus), còn Customer Stock Ledger
		# Entry tự chặn on_trash() vô điều kiện (sổ chỉ được đảo bằng phiếu
		# đảo, không được xoá tay — đúng thiết kế, xem docstring của nó).
		# Cùng khuôn dọn của test_e4_ncc.py: frappe.db.delete không chạy hook
		# nào, phù hợp cho dọn dẹp test, và bảng con phải xoá riêng vì
		# frappe.db.delete không cascade như delete_doc().
		phieu_xuat = frappe.get_all("Customer Stock Issue", filters={"kho": ["in", khos]}, pluck="name")
		phieu_nhap = frappe.get_all("Customer Stock Receipt", filters={"kho": ["in", khos]}, pluck="name")
		vat_tu = frappe.get_all("Customer Warehouse Item", filters={"kho": ["in", khos]}, pluck="name")
		frappe.db.delete("Customer Stock Issue Item", {"parent": ["in", phieu_xuat or [""]]})
		frappe.db.delete("Customer Stock Receipt Item", {"parent": ["in", phieu_nhap or [""]]})
		frappe.db.delete("Customer Warehouse Item Equipment", {"parent": ["in", vat_tu or [""]]})
		frappe.db.delete("Customer Stock Issue", {"kho": ["in", khos]})
		frappe.db.delete("Customer Stock Receipt", {"kho": ["in", khos]})
		frappe.db.delete("Customer Stock Ledger Entry", {"kho": ["in", khos]})
		frappe.db.delete("Customer Stock Lot Balance", {"kho": ["in", khos]})
		frappe.db.delete("Customer Warehouse Item", {"kho": ["in", khos]})
		for dt in ("Customer Equipment", "Customer Department", "Customer Warehouse"):
			frappe.db.delete(dt, {"customer": ["in", khach]})
		frappe.db.delete("Customer", {"name": ["in", khach]})

	def test_may_cua_benh_vien_khac_bi_chan(self):
		"""BR-TB-1."""
		with self.assertRaises(frappe.ValidationError):
			self._xuat(thiet_bi=self.may_la.name)

	def test_may_ngoai_danh_muc_cua_vat_tu_chi_canh_bao(self):
		"""BR-TB-2 — KHÔNG chặn. Danh mục có thể khai thiếu; chặn cứng làm
		tắc việc xuất hàng. Cảnh báo đi kèm để SPA hiện nút "Gắn vào vật tư"."""
		self.vat_tu.set("may_su_dung", [{"thiet_bi": self.may_a.name}])
		self.vat_tu.save(ignore_permissions=True)
		doc = self._xuat(thiet_bi=self.may_b.name)
		self.assertEqual(doc.items[0].thiet_bi, self.may_b.name)
		self.assertTrue(doc.flags.canh_bao_thiet_bi)

	def test_may_trong_danh_muc_khong_canh_bao(self):
		self.vat_tu.set("may_su_dung", [{"thiet_bi": self.may_a.name}])
		self.vat_tu.save(ignore_permissions=True)
		doc = self._xuat(thiet_bi=self.may_a.name)
		self.assertFalse(doc.flags.get("canh_bao_thiet_bi"))

	def test_bang_may_trong_thi_chon_may_nao_cung_duoc(self):
		doc = self._xuat(thiet_bi=self.may_b.name)
		self.assertFalse(doc.flags.get("canh_bao_thiet_bi"))

	def test_khoa_cua_may_khac_khoa_tren_phieu_chi_canh_bao(self):
		"""BR-TB-4 — máy mới chuyển khoa, hoặc khoa mượn máy, đều là thật."""
		doc = self._xuat(thiet_bi=self.may_khoa_a.name, khoa_phong=self.kp_b.name)
		self.assertEqual(doc.docstatus, 1)
		self.assertTrue(doc.flags.canh_bao_thiet_bi)

	def test_may_da_tat_bi_chan_tren_phieu_moi(self):
		"""BR-TB-5."""
		self.may_a.active = 0
		self.may_a.save(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			self._xuat(thiet_bi=self.may_a.name)

	def test_may_da_tat_khong_lam_vo_phieu_cu(self):
		doc = self._xuat(thiet_bi=self.may_a.name)
		self.may_a.active = 0
		self.may_a.save(ignore_permissions=True)
		doc.reload()
		self.assertEqual(doc.items[0].thiet_bi, self.may_a.name)

	def test_khong_xoa_duoc_may_da_dung(self):
		"""BR-TB-9 — hoàn tất ca test bỏ dở ở Task 1."""
		self._xuat(thiet_bi=self.may_a.name)
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc(
				"Customer Equipment", self.may_a.name, force=True, ignore_permissions=True
			)

	def test_thiet_bi_mac_dinh_khong_ghi_xuong_dong(self):
		"""Đầu phiếu chỉ là tiện ích nhập liệu của SPA. Server KHÔNG tự điền
		xuống dòng — nếu server cũng điền thì một phiếu đổi máy mặc định sau
		khi các dòng đã chọn tay sẽ ra hai con số khác nhau tuỳ báo cáo nào chạy."""
		doc = self._xuat(thiet_bi=None, thiet_bi_mac_dinh=self.may_a.name)
		self.assertIsNone(doc.items[0].thiet_bi)

	def test_huy_phieu_van_dao_duoc_khi_may_da_tat(self):
		"""Máy tắt GIỮA lúc xuất và lúc huỷ không được làm sập thao tác huỷ —
		cùng ràng buộc "on_cancel không được phép ném lỗi" đã có sẵn cho
		khoa phòng (_chan_khoa_phong_da_tat chỉ chạy ở before_submit, không
		chạy khi tạo phiếu đảo). Dòng phiếu đảo vẫn phải mang đúng máy để
		báo cáo sau này cấn trừ được theo máy qua chung_tu_row."""
		doc = self._xuat(thiet_bi=self.may_a.name)
		self.may_a.active = 0
		self.may_a.save(ignore_permissions=True)
		doc.cancel()
		dao_name = frappe.db.get_value(
			"Customer Stock Issue", {"phieu_goc": doc.name}, "name"
		)
		self.assertEqual(
			frappe.get_doc("Customer Stock Issue", dao_name).items[0].thiet_bi,
			self.may_a.name,
		)

	def test_khoa_khong_gan_kho_van_ghi_so_duoc(self):
		"""C-2 (đợt sửa cuối). `self.kp_a` (từ `_khoa()`) KHÔNG gắn `kho` —
		đúng như đường onboarding thật (`api/nhan_su.py::
		nhan_su_import_commit` tạo khoa không có `kho`; HDSD-phan-quyen-
		khoa-phong.md:75 dạy để trống). Trước khi sửa,
		`_validate_khoa_phong_thuoc_kho()` so `Customer Department.kho ==
		self.kho` — khoa không gắn kho luôn khớp `None != self.kho`, chặn
		nhầm MỌI phiếu của một khoa hợp lệ, có thật, đúng bệnh viện. Phiếu
		phải ghi sổ được."""
		doc = self._xuat(thiet_bi=self.may_a.name, khoa_phong=self.kp_a.name)
		self.assertEqual(doc.docstatus, 1)
		self.assertIsNone(frappe.db.get_value("Customer Department", self.kp_a.name, "kho"))

	def test_khoa_cua_benh_vien_khac_van_bi_chan(self):
		"""C-2 — đối chứng: guard đổi sang so `customer` không nới quyền,
		khoa của MỘT BỆNH VIỆN KHÁC vẫn phải bị chặn."""
		if not frappe.db.exists("Customer", "ZZTB2 Benh Vien Khac"):
			frappe.get_doc({
				"doctype": "Customer", "customer_name": "ZZTB2 Benh Vien Khac",
				"customer_type": "Company", "customer_group": "All Customer Groups",
				"territory": "All Territories",
			}).insert(ignore_permissions=True)
		kp_khac = frappe.get_doc({
			"doctype": "Customer Department", "customer": "ZZTB2 Benh Vien Khac",
			"ten_khoa_phong": "ZZTB2K Khoa La", "ma_khoa": "ZZTB2KL",
		}).insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			self._xuat(khoa_phong=kp_khac.name)
