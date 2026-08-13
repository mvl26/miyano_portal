"""E5 — Dự trù & vòng lặp Just-in-Time. Bám 14_PRD_E5_DuTru_JIT.md và
40_TestCases.md nhóm TC-E5, dùng ĐÚNG bộ số chuẩn của PRD làm test.

Mọi ngày dùng ở đây TÍNH TƯƠNG ĐỐI so với `frappe.utils.today()`, không
hardcode ngày tuyệt đối — cùng lý do "date rot" đã ghi trong
test_kho_reports.py/test_e4_nhat_ky.py: cửa sổ ADU trượt theo `today()` một
cách không thể tránh, và phiếu đảo do `.cancel()` sinh ra LUÔN mang
`ngay = frappe.utils.today()`.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import kho as kho_api
from miyano_portal.kho import dutru
from miyano_portal.setup.seed_kho_demo import seed_kho_demo

BM_USER = "bvbm@demo.miyano"
PXN_USER = "pxnabc@demo.miyano"


def _today():
	return frappe.utils.getdate(frappe.utils.today())


def _iso(d):
	return frappe.utils.getdate(d).strftime("%Y-%m-%d")


def _nhap(kho, vat_tu, so_luong, ngay, don_gia=1000, so_lo="LO-A", han=None):
	doc = frappe.get_doc({
		"doctype": "Customer Stock Receipt",
		"kho": kho, "ngay": _iso(ngay), "loai_nhap": "Nhập khác",
		"nguoi_giao": "Trần Văn Giao",
		"items": [{
			"vat_tu": vat_tu, "so_lo": so_lo, "han_su_dung": han,
			"so_luong": so_luong, "don_gia": don_gia,
		}],
	})
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc


def _xuat(kho, vat_tu, so_luong, ngay, loai_xuat="Xuất sử dụng", so_lo="LO-A"):
	doc = frappe.get_doc({
		"doctype": "Customer Stock Issue",
		"kho": kho, "ngay": _iso(ngay), "loai_xuat": loai_xuat,
		"noi_nhan": "Khoa Nội", "nguoi_nhan": "Y tá Lan",
		"items": [{"vat_tu": vat_tu, "so_lo": so_lo, "so_luong": so_luong}],
	})
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc


class _KhoBmTestCase(FrappeTestCase):
	"""Cùng khuôn test_kho_reports.py::_KhoBmTestCase — dọn sổ/tồn của kho BM
	trước mỗi test vì các phép tính ở đây cộng dồn trên TOÀN BỘ sổ, và
	FrappeTestCase chỉ rollback một lần mỗi CLASS."""

	def setUp(self):
		self.kho = seed_kho_demo()
		self.K = self.kho["kho_bm"]
		self.VT = self.kho["vt_bm"]  # item_code=None trên site test (MYN-GLOVE-M không tồn tại) — "ngoài HĐNT"
		frappe.db.delete("Customer Stock Ledger Entry", {"kho": self.K})
		frappe.db.delete("Customer Stock Lot Balance", {"kho": self.K})
		# Cột min/ROP/max/bội số là NOT NULL DEFAULT 0 (xem docstring
		# dutru._chua_khai) — "chưa khai" là 0, KHÔNG PHẢI None. FrappeTestCase
		# chỉ rollback một lần mỗi CLASS nên self.VT (idempotent qua
		# seed_kho_demo) có thể còn mang giá trị một test TRƯỚC đã lưu trong
		# cùng class — reset về 0 ở đây để mỗi test bắt đầu từ "chưa thiết lập".
		frappe.db.set_value("Customer Warehouse Item", self.VT, {
			"ton_toi_thieu": 0, "diem_dat_lai": 0, "ton_toi_da": 0,
			"lead_time_ngay": 3, "boi_so_dat": 0,
		})

	def tearDown(self):
		frappe.set_user("Administrator")


# ===================================================== Bộ số chuẩn PRD (canonical)

class TestBoSoChuanPRD(_KhoBmTestCase):
	"""MỘT kịch bản dựng đúng ví dụ chuẩn của brief:

	90 ngày xuất sử dụng 450 hộp (+1 phiếu xuất huỷ 30 hộp — KHÔNG tính, +1
	phiếu đảo lẫn vào — KHÔNG tính) -> ADU = 5/ngày. lead_time=3,
	ton_toi_thieu=10 -> ROP = 5x3+10 = 25. ton_toi_da khách chốt = 60. Tồn
	hiện tại = 22 (< ROP) -> "Sắp thiếu". SL gợi ý = 60-22 = 38, bội số 10 ->
	40. Ngày phủ = 22/5 = 4,4 ngày.

	DoD: "test phải có một phiếu xuất huỷ và một phiếu đảo lẫn vào dữ liệu"
	— nếu ADU vẫn ra 5 thì phép loại trừ đúng cả hai loại; nếu ra 5,33 thì
	phiếu huỷ bị tính; nếu lệch kiểu khác thì phiếu đảo bị tính.
	"""

	def setUp(self):
		super().setUp()
		today = _today()

		# Đủ tồn cho toàn bộ chuỗi sự kiện bên dưới, thời điểm nhập nằm NGOÀI
		# kỳ ADU 90 ngày để không lẫn vào tổng "xuất sử dụng" (đây là NHẬP).
		_nhap(self.K, self.VT, 502, frappe.utils.add_days(today, -200))

		# Phiếu "Xuất sử dụng" 25 hộp bị HUỶ NGAY (trước khi rút thêm tồn) —
		# tồn thật (append-only, xét theo THỨ TỰ GHI SỔ, không phải theo
		# `ngay` trên chứng từ) phải đủ 25 tại thời điểm này. Huỷ sinh phiếu
		# đảo thật (ngay=today()), đánh dấu dòng gốc da_dao=1 — cả dòng gốc
		# lẫn dòng đảo đều PHẢI bị loại khỏi ADU (BR-P1/NL-9.4).
		bi_huy = _xuat(self.K, self.VT, 25, frappe.utils.add_days(today, -10))
		bi_huy.reload()
		bi_huy.cancel()

		# 450 "Xuất sử dụng" trải trong kỳ trượt 90 ngày (BR-P1).
		_xuat(self.K, self.VT, 200, frappe.utils.add_days(today, -80))
		_xuat(self.K, self.VT, 150, frappe.utils.add_days(today, -40))
		_xuat(self.K, self.VT, 100, frappe.utils.add_days(today, -5))

		# NL-9.4: "Xuất huỷ - hết hạn" 30 hộp — KHÔNG phải tiêu thụ, không tính.
		_xuat(self.K, self.VT, 30, frappe.utils.add_days(today, -20), loai_xuat="Xuất huỷ - hết hạn")

		# Khách đã chốt min/ROP/max (US-E5.1) — mô phỏng đã lưu qua nút gợi ý.
		doc = frappe.get_doc("Customer Warehouse Item", self.VT)
		doc.ton_toi_thieu = 10
		doc.diem_dat_lai = 25
		doc.ton_toi_da = 60
		doc.lead_time_ngay = 3
		doc.boi_so_dat = 10
		doc.save(ignore_permissions=True)

	def test_adu_loai_tru_dung_phieu_huy_va_phieu_dao(self):
		"""TC-E5-01 — nếu bất kỳ phép loại trừ nào (loai_xuat != 'Xuất sử
		dụng' HOẶC da_dao=1) bị bỏ sót, con số này KHÔNG còn là 5.0."""
		tt = dutru.tinh_tieu_thu(self.K, self.VT)
		self.assertEqual(tt["adu_90"], 5.0)
		self.assertEqual(tt["so_ngay_du_lieu"], 81)  # today - (today-80) + 1

	def test_ton_kha_dung_la_22(self):
		self.assertEqual(dutru.ton_kha_dung(self.K, self.VT), 22)

	def test_min_max_goi_y_endpoint_tra_dung_rop_25(self):
		"""TC-E5-02 — lead=3, min=10 (đang lưu) -> ROP = 5*3+10 = 25; max
		"để khách chốt" nghĩa là hệ thống chỉ ECHO lại giá trị đang lưu (60),
		không tự tính lại."""
		frappe.set_user(BM_USER)
		out = kho_api.kho_min_max_goi_y(vat_tu_list=[self.VT])
		row = out[self.VT]
		self.assertEqual(row["adu_90"], 5.0)
		self.assertEqual(row["min"], 10)
		self.assertEqual(row["rop"], 25)
		self.assertEqual(row["max"], 60)

	def test_canh_bao_ton_dung_bo_so_chuan(self):
		"""TC-E5-03 — tồn 22, ROP 25, max 60, bội số 10 -> "Sắp thiếu";
		ngày phủ 4,4; SL gợi ý 40."""
		frappe.set_user(BM_USER)
		out = kho_api.kho_canh_bao_ton()
		row = next(r for r in out["dong"] if r["vat_tu"] == self.VT)
		self.assertEqual(row["ton"], 22)
		self.assertEqual(row["min"], 10)
		self.assertEqual(row["rop"], 25)
		self.assertEqual(row["max"], 60)
		self.assertEqual(row["trang_thai"], "sap_thieu")
		self.assertEqual(row["ngay_phu"], 4.4)
		self.assertEqual(row["sl_goi_y"], 40)
		self.assertEqual(out["cham_rop"], 1)
		self.assertEqual(out["thieu"], 0)


# ============================================================ Ngưỡng dữ liệu

class TestNguongDuLieu(_KhoBmTestCase):
	def test_tc_e5_04_vat_tu_20_ngay_du_lieu_khong_dien_so(self):
		"""TC-E5-04 — vật tư mới có 20 ngày dữ liệu, chưa khai min ->
		kho_min_max_goi_y trả du_lieu=false, KHÔNG điền số (NL-9.1)."""
		today = _today()
		_nhap(self.K, self.VT, 100, frappe.utils.add_days(today, -25))
		_xuat(self.K, self.VT, 10, frappe.utils.add_days(today, -19))  # 20 ngày dữ liệu (19->0, +1)

		frappe.set_user(BM_USER)
		out = kho_api.kho_min_max_goi_y(vat_tu_list=[self.VT])
		self.assertEqual(out[self.VT], {"du_lieu": False})

	def test_du_30_ngay_du_lieu_thi_co_so(self):
		"""Đối xứng: đúng 30 ngày dữ liệu (ranh giới) phải QUA được cổng."""
		today = _today()
		_nhap(self.K, self.VT, 100, frappe.utils.add_days(today, -35))
		_xuat(self.K, self.VT, 10, frappe.utils.add_days(today, -29))  # 30 ngày dữ liệu tròn

		frappe.set_user(BM_USER)
		out = kho_api.kho_min_max_goi_y(vat_tu_list=[self.VT])
		self.assertIn("adu_90", out[self.VT])
		self.assertNotIn("du_lieu", out[self.VT])

	def test_br_p3_chua_thiet_lap_va_chua_du_du_lieu_khong_canh_bao(self):
		"""BR-P3 — vật tư chưa khai min/ROP VÀ < 30 ngày dữ liệu: KHÔNG xuất
		hiện trong danh sách cảnh báo (không phải hiện với trạng thái nào cả)."""
		today = _today()
		_nhap(self.K, self.VT, 100, frappe.utils.add_days(today, -15))
		_xuat(self.K, self.VT, 10, frappe.utils.add_days(today, -10))  # 11 ngày dữ liệu, chưa đủ 30

		frappe.set_user(BM_USER)
		out = kho_api.kho_canh_bao_ton()
		self.assertFalse(any(r["vat_tu"] == self.VT for r in out["dong"]))
		self.assertEqual(out["thieu"], 0)
		self.assertEqual(out["cham_rop"], 0)
		self.assertEqual(out["chua_thiet_lap"], 0)

	def test_br_p3_du_du_lieu_nhung_chua_thiet_lap_thi_hien_chua_thiet_lap(self):
		"""Đối xứng của test trên: ĐÃ đủ 30 ngày dữ liệu nhưng CHƯA khai
		min/ROP -> vẫn hiện, gắn trạng thái "chua_thiet_lap" (khác với ẩn
		hoàn toàn) — đây chính là điểm phân biệt hai nhánh của BR-P3."""
		today = _today()
		_nhap(self.K, self.VT, 100, frappe.utils.add_days(today, -35))
		_xuat(self.K, self.VT, 10, frappe.utils.add_days(today, -29))

		frappe.set_user(BM_USER)
		out = kho_api.kho_canh_bao_ton()
		row = next(r for r in out["dong"] if r["vat_tu"] == self.VT)
		self.assertEqual(row["trang_thai"], "chua_thiet_lap")
		self.assertEqual(out["chua_thiet_lap"], 1)


# ============================================================== "Thiếu" đỏ

class TestTrangThaiThieu(_KhoBmTestCase):
	def test_ton_duoi_min_la_thieu_khong_phai_sap_thieu(self):
		today = _today()
		_nhap(self.K, self.VT, 100, frappe.utils.add_days(today, -100))
		_xuat(self.K, self.VT, 92, frappe.utils.add_days(today, -50))  # tồn còn 8

		doc = frappe.get_doc("Customer Warehouse Item", self.VT)
		doc.ton_toi_thieu = 10
		doc.diem_dat_lai = 25
		doc.ton_toi_da = 60
		doc.save(ignore_permissions=True)

		frappe.set_user(BM_USER)
		out = kho_api.kho_canh_bao_ton()
		row = next(r for r in out["dong"] if r["vat_tu"] == self.VT)
		self.assertEqual(row["trang_thai"], "thieu")
		self.assertEqual(out["thieu"], 1)
		self.assertEqual(out["cham_rop"], 0)


# =================================================================== US-E5.3

class TestGioBoSung(_KhoBmTestCase):
	"""US-E5.3 — dữ liệu để màn giao diện quyết định hiện nút nào."""

	def test_vat_tu_thuoc_hdnt_hieu_luc_co_co_dat_duoc_hdnt(self):
		"""TC-E5-05 (nhánh thuộc HĐNT) — VT0005 nằm trong Blanket Order còn
		hiệu lực của Bệnh viện Bạch Mai (seed_demo.py)."""
		today = _today()
		vt2 = frappe.get_doc({
			"doctype": "Customer Warehouse Item", "kho": self.K,
			"ma_vat_tu": "VT-HDNT", "ten_vat_tu": "Vật tư thuộc HĐNT",
			"dvt": "Cái", "item_code": "VT0005", "lead_time_ngay": 3,
		}).insert(ignore_permissions=True)
		_nhap(self.K, vt2.name, 100, frappe.utils.add_days(today, -40))
		_xuat(self.K, vt2.name, 10, frappe.utils.add_days(today, -35))

		frappe.set_user(BM_USER)
		out = kho_api.kho_canh_bao_ton()
		row = next(r for r in out["dong"] if r["vat_tu"] == vt2.name)
		self.assertTrue(row["dat_duoc_hdnt"])
		self.assertEqual(row["item_code"], "VT0005")

	def test_vat_tu_ngoai_hdnt_item_code_rong_khong_dat_duoc_hdnt(self):
		"""TC-E5-05 (nhánh ngoài HĐNT) — vật tư RIÊNG của kho (không khớp
		Item nào của Miyano, item_code để trống có chủ đích) -> chỉ có thể
		"Nhờ Miyano tìm nguồn", không được gắn cờ dat_duoc_hdnt. Tạo vật tư
		MỚI trong chính test này (không dựa vào item_code của self.VT/vt_bm
		từ seed_kho_demo — rule "đừng đếm tuyệt đối trên dữ liệu ngoài tầm
		setUp": Item "MYN-GLOVE-M" có thể đã tồn tại thật trên site dev do
		một script demo khác từng chạy, khiến vt_bm bất ngờ CÓ item_code)."""
		today = _today()
		vt_rieng = frappe.get_doc({
			"doctype": "Customer Warehouse Item", "kho": self.K,
			"ma_vat_tu": "VT-RIENG-KHO", "ten_vat_tu": "Vật tư riêng của kho",
			"dvt": "Cái", "lead_time_ngay": 3,
		}).insert(ignore_permissions=True)
		_nhap(self.K, vt_rieng.name, 100, frappe.utils.add_days(today, -40))
		_xuat(self.K, vt_rieng.name, 10, frappe.utils.add_days(today, -35))

		frappe.set_user(BM_USER)
		out = kho_api.kho_canh_bao_ton()
		row = next(r for r in out["dong"] if r["vat_tu"] == vt_rieng.name)
		self.assertFalse(row["dat_duoc_hdnt"])
		self.assertEqual(row["item_code"], "")

	def test_vat_tu_co_item_code_nhung_hdnt_da_het_han_khong_dat_duoc_hdnt(self):
		"""item_code có thật (VT0005) nhưng khách KHÔNG có Blanket Order hiệu
		lực (PXN ABC — seed_demo.py chỉ tạo Blanket Order cho khách đầu tiên)
		-> vẫn phải là "ngoài HĐNT", không suy diễn theo item_code một mình."""
		today = _today()
		kho_pxn = self.kho["kho_pxn"]
		frappe.db.delete("Customer Stock Ledger Entry", {"kho": kho_pxn})
		frappe.db.delete("Customer Stock Lot Balance", {"kho": kho_pxn})
		vt_pxn = frappe.get_doc({
			"doctype": "Customer Warehouse Item", "kho": kho_pxn,
			"ma_vat_tu": "VT-PXN-VT0005", "ten_vat_tu": "Vật tư PXN dùng mã VT0005",
			"dvt": "Cái", "item_code": "VT0005", "lead_time_ngay": 3,
		}).insert(ignore_permissions=True)
		_nhap(kho_pxn, vt_pxn.name, 100, frappe.utils.add_days(today, -40))
		_xuat(kho_pxn, vt_pxn.name, 10, frappe.utils.add_days(today, -35))

		frappe.set_user(PXN_USER)
		out = kho_api.kho_canh_bao_ton()
		row = next(r for r in out["dong"] if r["vat_tu"] == vt_pxn.name)
		self.assertFalse(row["dat_duoc_hdnt"])


# ============================================================= Cách ly kho

class TestCoLap(_KhoBmTestCase):
	def test_kho_min_max_goi_y_tu_choi_vat_tu_kho_khac(self):
		frappe.set_user(PXN_USER)
		with self.assertRaises(frappe.PermissionError):
			kho_api.kho_min_max_goi_y(vat_tu_list=[self.VT])

	def test_kho_canh_bao_ton_khong_lo_sang_khach_khac(self):
		today = _today()
		kho_pxn = self.kho["kho_pxn"]
		vt_pxn = self.kho["vt_pxn"]
		frappe.db.delete("Customer Stock Ledger Entry", {"kho": kho_pxn})
		frappe.db.delete("Customer Stock Lot Balance", {"kho": kho_pxn})
		_nhap(kho_pxn, vt_pxn, 100, frappe.utils.add_days(today, -40))
		_xuat(kho_pxn, vt_pxn, 10, frappe.utils.add_days(today, -35))

		frappe.set_user(BM_USER)
		out = kho_api.kho_canh_bao_ton()
		self.assertFalse(any(r["vat_tu"] == vt_pxn for r in out["dong"]))


# ========================================================== Validate min/max

class TestValidateMinMaxRop(FrappeTestCase):
	def setUp(self):
		self.kho = seed_kho_demo()

	def test_min_lon_hon_rop_bi_chan(self):
		doc = frappe.get_doc({
			"doctype": "Customer Warehouse Item", "kho": self.kho["kho_bm"],
			"ma_vat_tu": "VT-MINROP-1", "ten_vat_tu": "Test min>rop", "dvt": "Cái",
			"ton_toi_thieu": 30, "diem_dat_lai": 25, "ton_toi_da": 60,
		})
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_rop_lon_hon_max_bi_chan(self):
		doc = frappe.get_doc({
			"doctype": "Customer Warehouse Item", "kho": self.kho["kho_bm"],
			"ma_vat_tu": "VT-MINROP-2", "ten_vat_tu": "Test rop>max", "dvt": "Cái",
			"ton_toi_thieu": 10, "diem_dat_lai": 70, "ton_toi_da": 60,
		})
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_chi_khai_mot_phan_khong_bi_chan(self):
		"""Chỉ nhập min, chưa nhập ROP/max -> KHÔNG có gì để so, phải lưu được."""
		doc = frappe.get_doc({
			"doctype": "Customer Warehouse Item", "kho": self.kho["kho_bm"],
			"ma_vat_tu": "VT-MINROP-3", "ten_vat_tu": "Test mot phan", "dvt": "Cái",
			"ton_toi_thieu": 10,
		})
		doc.insert(ignore_permissions=True)
		self.assertEqual(doc.ton_toi_thieu, 10)

	def test_bo_so_dat_am_bi_chan(self):
		doc = frappe.get_doc({
			"doctype": "Customer Warehouse Item", "kho": self.kho["kho_bm"],
			"ma_vat_tu": "VT-MINROP-4", "ten_vat_tu": "Test boi so am", "dvt": "Cái",
			"boi_so_dat": -5,
		})
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_lead_time_ngoai_khoang_bi_chan(self):
		doc = frappe.get_doc({
			"doctype": "Customer Warehouse Item", "kho": self.kho["kho_bm"],
			"ma_vat_tu": "VT-MINROP-5", "ten_vat_tu": "Test lead time", "dvt": "Cái",
			"lead_time_ngay": 90,
		})
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)


# ==================================================== Mặc định Settings (C-1)

class TestSettingsDefault(FrappeTestCase):
	"""so_ngay_adu/so_ngay_du_lieu_toi_thieu phải rơi về mặc định TƯỜNG MINH
	trong code (90/30) khi `tabSingles` CHƯA có dòng cho field đó — mô phỏng
	một site chưa từng chạy patch v1_6.seed_portal_settings_defaults."""

	def setUp(self):
		self._backup = frappe.db.get_singles_dict("Miyano Portal Settings")

	def tearDown(self):
		for k, v in self._backup.items():
			frappe.db.set_single_value("Miyano Portal Settings", k, v)
		frappe.db.delete("Singles", {
			"doctype": "Miyano Portal Settings",
			"field": ["not in", list(self._backup.keys())],
		})

	def test_chua_tung_luu_roi_ve_mac_dinh_90_va_30(self):
		frappe.db.delete("Singles", {
			"doctype": "Miyano Portal Settings",
			"field": ["in", ["so_ngay_adu", "so_ngay_du_lieu_toi_thieu"]],
		})
		self.assertEqual(dutru.so_ngay_adu(), 90)
		self.assertEqual(dutru.so_ngay_du_lieu_toi_thieu(), 30)

	def test_da_cau_hinh_gia_tri_khac_thi_doc_dung_gia_tri_do(self):
		frappe.db.set_single_value("Miyano Portal Settings", "so_ngay_adu", 60)
		self.assertEqual(dutru.so_ngay_adu(), 60)
