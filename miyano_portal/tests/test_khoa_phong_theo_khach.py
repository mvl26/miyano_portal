"""Khoa phòng thuộc về BỆNH VIỆN, không thuộc về kho (bước 2).

Lý do đổi: đặt hàng thì bệnh viện nào cũng làm, kho thì chỉ vài bệnh viện
có. Giữ khoá theo kho thì khách chưa mở kho (Hi-medic) không có khoa phòng
nào để mà phân quyền.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.kho import khoa_phong
from miyano_portal.setup.seed_kho_demo import seed_kho_demo

KHACH_BM = "Bệnh viện Bạch Mai"
KHACH_PXN = "PXN ABC"  # khách thứ hai, dùng để chốt chiều "CHO PHÉP" — duy
# nhất PHẢI là trong-một-bệnh-viện, không phải toàn cục (vòng sửa 1, phát
# hiện 2).


class TestKhoaPhongThuocKhachHang(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Customer Department", {"ten_khoa_phong": ["like", "ZZTEST%"]})

	def _tao(self, ten, ma=None, customer=KHACH_BM):
		return frappe.get_doc({
			"doctype": "Customer Department", "customer": customer,
			"ten_khoa_phong": ten, "ma_khoa": ma,
		}).insert(ignore_permissions=True)

	def test_khai_duoc_khoa_phong_cho_khach_chua_co_kho(self):
		kp = self._tao("ZZTEST Khoa Huyết học")
		self.assertEqual(kp.customer, KHACH_BM)
		self.assertFalse(kp.kho, "không cần kho mới khai được khoa phòng")

	def test_ma_khoa_tu_viet_hoa(self):
		self.assertEqual(self._tao("ZZTEST Hoá sinh", ma="hs").ma_khoa, "HS")

	def test_ma_khoa_chi_nhan_chu_va_so(self):
		with self.assertRaises(frappe.ValidationError):
			self._tao("ZZTEST Xét nghiệm", ma="XN-01")

	def test_ma_khoa_khong_duoc_trung_trong_mot_benh_vien(self):
		self._tao("ZZTEST Khoa A", ma="KA")
		with self.assertRaises(frappe.ValidationError):
			self._tao("ZZTEST Khoa B", ma="ka")

	def test_ma_khoa_CHUNG_la_ma_danh_rieng(self):
		"""`CHUNG` dành cho đơn quản lý đặt "Toàn viện" (spec §5.5)."""
		with self.assertRaises(frappe.ValidationError):
			self._tao("ZZTEST Khoa chung", ma="CHUNG")

	def test_ma_khoa_khong_duoc_co_dau(self):
		"""Vòng sửa 1, phát hiện 1: `"HÓA".isalnum()` trả `True` trong Python
		(chữ có dấu vẫn là chữ cái theo Unicode) — chỉ `.isalnum()` một mình
		thì mã có dấu tiếng Việt lọt qua được. `.isascii()` là điều kiện
		CHẶN riêng, không phải hệ quả của `.isalnum()`."""
		with self.assertRaises(frappe.ValidationError):
			self._tao("ZZTEST Khoa có dấu", ma="HÓA")

	def test_ma_khoa_trung_o_benh_vien_khac_van_luu_duoc(self):
		"""Vòng sửa 1, phát hiện 2 (chiều CHO PHÉP): "duy nhất trong MỘT bệnh
		viện" — không phải toàn cục. Nếu chốt trùng lỡ tay bỏ điều kiện lọc
		theo `customer`, test này phải đỏ (xem báo cáo mục "Vòng sửa 1" để
		biết cách đã tự kiểm bằng cách gỡ tạm)."""
		self._tao("ZZTEST Khoa mã chung A", ma="ZZ01", customer=KHACH_BM)
		kp2 = self._tao("ZZTEST Khoa mã chung B", ma="ZZ01", customer=KHACH_PXN)
		self.assertEqual(kp2.ma_khoa, "ZZ01")

	def test_ten_khoa_phong_trung_o_benh_vien_khac_van_luu_duoc(self):
		"""Vòng sửa 1, phát hiện 2 (chiều CHO PHÉP), cho `_chan_trung_tuyet_doi()`
		— cùng lý do như trên, áp cho tên khoa thay vì mã khoa."""
		self._tao("ZZTEST Khoa tên chung", customer=KHACH_BM)
		kp2 = self._tao("ZZTEST Khoa tên chung", customer=KHACH_PXN)
		self.assertEqual(kp2.customer, KHACH_PXN)


class TestGoiYGanGiongTheoKhachKhongTheoKho(FrappeTestCase):
	"""Vòng sửa 1, phát hiện 4: `_chan_trung_tuyet_doi()` (customer_department.py)
	đã lọc theo `customer` từ bước 2, nhưng `khoa_phong._existing_rows()` —
	nguồn của gợi ý "gần giống" cho `kho_khoa_phong_save` (xem trước trước
	khi lưu) — vẫn lọc theo `kho`. Một khách giờ có thể có VỪA khoa gắn kho
	VỪA khoa không gắn kho (bước 2 vừa mở khoá điều đó); nếu gợi ý chỉ nhìn
	theo `kho`, nó bỏ sót khoa không gắn kho cùng khách — client xem trước
	báo "không trùng", bấm lưu thì validate() lại chặn vì SO SÁNH đúng phạm
	vi `customer`. Test dựng đúng kịch bản: một khoa GẮN kho + một khoa
	KHÔNG gắn kho, cùng khách, tên gần giống."""

	def setUp(self):
		self.kho = seed_kho_demo()
		self.K = self.kho["kho_bm"]
		self.customer = frappe.db.get_value("Customer Warehouse", self.K, "customer")
		frappe.db.delete("Customer Department", {
			"customer": self.customer, "ten_khoa_phong": ["like", "ZZTEST GoiY%"],
		})

	def test_goi_y_thay_duoc_khoa_khong_gan_kho_gan_giong(self):
		# Khoa "gốc" KHÔNG gắn kho nào — chỉ có customer (đường mới, bước 2).
		frappe.get_doc({
			"doctype": "Customer Department", "customer": self.customer,
			"ten_khoa_phong": "ZZTEST GoiY Khoa Hồi sức tích cực",
		}).insert(ignore_permissions=True)

		out = khoa_phong.save(self.K, {
			"ten_khoa_phong": "ZZTEST GoiY Khoa Hồi sức tích cực1", "chi_kiem_tra": 1,
		})
		self.assertTrue(
			out["goi_y_trung"],
			"khoa không gắn kho, cùng khách, phải xuất hiện trong gợi ý gần "
			"giống — không chỉ khoa cùng `kho`",
		)


class TestPatchXacThucMaKhoaTheoLuatMoi(FrappeTestCase):
	"""Vòng sửa 1, phát hiện 3: TRƯỚC task này `ma_khoa` chỉ có luật "≤20 ký
	tự". Patch gốc chỉ viết hoa mà không xác thực theo luật MỚI (chỉ
	A-Z0-9, không trùng trong cùng bệnh viện sau khi chuẩn hoá, không phải
	mã dành riêng). `frappe.db.set_value` (patch dùng để ghi) bỏ qua
	validate() nên một mã vi phạm có thể nằm lì trong DB.

	Dựng lại đúng hình dạng dữ liệu "trước task này": tạo bản ghi hợp lệ rồi
	GHI THẲNG qua `frappe.db.set_value` để mô phỏng `ma_khoa` được tạo trước
	khi `_chuan_hoa_ma_khoa()` tồn tại — không đi qua validate()."""

	TEN_LOI_MA_SAI = "Mã khoa vi phạm luật mới sau khi chuẩn hoá"

	def setUp(self):
		frappe.db.delete("Customer Department", {"ten_khoa_phong": ["like", "ZZTEST Patch%"]})
		# `tabError Log` là MyISAM (phi giao dịch, cùng lưu ý đã có ở
		# test_kho_delivery_hook.py/test_e3_doi_soat.py) — rollback theo CLASS
		# của FrappeTestCase không dọn được bảng này, nên dọn tay cả trước lẫn
		# sau mỗi test để không để rác lại trên site dùng chung.
		frappe.db.delete("Error Log", {"method": self.TEN_LOI_MA_SAI})
		self.addCleanup(frappe.db.delete, "Error Log", {"method": self.TEN_LOI_MA_SAI})

	def _tao_gia_lap_cu(self, ten, ma, customer=KHACH_BM):
		doc = frappe.get_doc({
			"doctype": "Customer Department", "customer": customer,
			"ten_khoa_phong": ten, "ma_khoa": "TAM",
		}).insert(ignore_permissions=True)
		frappe.db.set_value("Customer Department", doc.name, "ma_khoa", ma, update_modified=False)
		return doc.name

	def test_ma_hop_le_van_duoc_viet_hoa(self):
		from miyano_portal.patches.v1_23 import khoa_phong_theo_khach_hang as patch

		name = self._tao_gia_lap_cu("ZZTEST Patch Khoa A", "ab")
		patch.execute()
		self.assertEqual(frappe.db.get_value("Customer Department", name, "ma_khoa"), "AB")

	def test_ma_sai_dinh_dang_khong_bi_doan_chi_bi_ghi_error_log(self):
		from miyano_portal.patches.v1_23 import khoa_phong_theo_khach_hang as patch

		name = self._tao_gia_lap_cu("ZZTEST Patch Khoa B", "XN-01")
		patch.execute()
		self.assertEqual(
			frappe.db.get_value("Customer Department", name, "ma_khoa"), "XN-01",
			"mã sai định dạng không được patch tự đoán/sửa",
		)
		log = frappe.get_all("Error Log", filters={"method": self.TEN_LOI_MA_SAI})
		self.assertEqual(len(log), 1, "phải ghi đúng một dòng Error Log cho lượt chạy này")

	def test_trung_sau_chuan_hoa_khong_bi_gop_am_tham(self):
		from miyano_portal.patches.v1_23 import khoa_phong_theo_khach_hang as patch

		n1 = self._tao_gia_lap_cu("ZZTEST Patch Khoa C1", "hs")
		n2 = self._tao_gia_lap_cu("ZZTEST Patch Khoa C2", "HS ")  # strip+upper trùng "hs"
		patch.execute()
		# KHÔNG bên nào bị patch tự chọn giữ — vận hành phải xử tay ai giữ mã.
		self.assertEqual(frappe.db.get_value("Customer Department", n1, "ma_khoa"), "hs")
		self.assertEqual(frappe.db.get_value("Customer Department", n2, "ma_khoa"), "HS ")
		log = frappe.get_all("Error Log", filters={"method": self.TEN_LOI_MA_SAI})
		self.assertEqual(len(log), 1)

	def test_patch_khong_nem_loi_giua_migrate(self):
		"""Ném lỗi giữa `bench migrate` biến vấn đề DỮ LIỆU thành sự cố TRIỂN
		KHAI — dù có bản ghi vi phạm, execute() vẫn phải chạy xong."""
		from miyano_portal.patches.v1_23 import khoa_phong_theo_khach_hang as patch

		self._tao_gia_lap_cu("ZZTEST Patch Khoa D", "CHUNG")
		patch.execute()  # không được ném lỗi
