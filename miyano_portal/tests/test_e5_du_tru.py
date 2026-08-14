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
		# 525 = 22 (tồn cuối mong muốn) + 450 (xuất sử dụng) + 30 (huỷ) + 15
		# (trả lại) + 8 (điều chỉnh) + 0 (net cancel của phiếu đảo).
		_nhap(self.K, self.VT, 525, frappe.utils.add_days(today, -200))

		# Phiếu "Xuất sử dụng" 25 hộp bị HUỶ NGAY (trước khi rút thêm tồn) —
		# tồn thật (append-only, xét theo THỨ TỰ GHI SỔ, không phải theo
		# `ngay` trên chứng từ) phải đủ 25 tại thời điểm này. Huỷ sinh phiếu
		# đảo thật (ngay=today()), đánh dấu dòng gốc da_dao=1 — cả dòng gốc
		# lẫn dòng đảo đều PHẢI bị loại khỏi ADU (BR-P1/NL-9.4).
		bi_huy = _xuat(self.K, self.VT, 25, frappe.utils.add_days(today, -10))
		bi_huy.reload()
		bi_huy.cancel()

		# 450 "Xuất sử dụng" trải trong kỳ trượt 90 ngày (BR-P1). Chỉ dòng
		# -5 ngày rơi trong cửa sổ 30 ngày gần nhất -> adu_30 = 100/30
		# (NL-9.2, khẳng định ở test_adu_loai_tru_dung_phieu_huy_va_phieu_dao).
		_xuat(self.K, self.VT, 200, frappe.utils.add_days(today, -80))
		_xuat(self.K, self.VT, 150, frappe.utils.add_days(today, -40))
		_xuat(self.K, self.VT, 100, frappe.utils.add_days(today, -5))

		# NL-9.4: BA loại xuất không phải tiêu thụ, KHÔNG tính — M-10 (review
		# E5 round 2): fixture trước chỉ có MỘT loại ("Xuất huỷ - hết hạn"),
		# chưa thử "Xuất trả lại"/"Điều chỉnh kiểm kê" — một `loai_xuat` mới
		# lọt qua bộ lọc `_xuat_su_dung_issue_names()` (rủi ro cụ thể: E8 vừa
		# thêm khoa phòng vào phiếu xuất, một loại xuất mới trong tương lai
		# hoàn toàn có thể xảy ra) sẽ không bị bất kỳ test nào bắt nếu chỉ
		# thử một loại.
		_xuat(self.K, self.VT, 30, frappe.utils.add_days(today, -20), loai_xuat="Xuất huỷ - hết hạn")
		_xuat(self.K, self.VT, 15, frappe.utils.add_days(today, -25), loai_xuat="Xuất trả lại")
		_xuat(self.K, self.VT, 8, frappe.utils.add_days(today, -35), loai_xuat="Điều chỉnh kiểm kê")

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

	def test_adu_30_ngay_dung_cua_so_co_dinh_30(self):
		"""NL-9.2 — trước bản sửa round 2, `adu_30` không được khẳng định ở
		bất kỳ test nào; nếu cửa sổ 30 ngày lệch (ví dụ vô tình chia cho `n`
		thay vì hằng số 30) sẽ không có test nào đỏ. Chỉ dòng "-5 ngày" (100
		hộp) rơi trong 30 ngày gần nhất trong fixture của lớp này."""
		tt = dutru.tinh_tieu_thu(self.K, self.VT)
		self.assertEqual(tt["adu_30"], round(100 / 30, 6))

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

	def test_i3_du_du_lieu_nhung_chua_khai_gi_van_tinh_duoc_rop(self):
		"""I-3 (review E5 round 2) — ĐÚNG kịch bản khách cần gợi ý nhất: vật
		tư mới đủ dữ liệu, CHƯA khai min/ROP/max (chỉ có lead_time_ngay mặc
		định 3 từ setUp). Trước bản sửa, `tinh_rop()` đòi CẢ hai điều kiện
		(lead_time VÀ min) nên trả `rop=None` — nút "Gợi ý từ tiêu thụ" chỉ
		điền được đúng ô ADU, 0/3 ô còn lại, khách kết luận nút hỏng.
		`rop` giờ chỉ cần `lead_time_ngay` — `ton_toi_thieu` chưa khai được
		coi là 0 KHI CỘNG (không phải lý do chặn)."""
		today = _today()
		_nhap(self.K, self.VT, 100, frappe.utils.add_days(today, -35))
		_xuat(self.K, self.VT, 10, frappe.utils.add_days(today, -29))

		frappe.set_user(BM_USER)
		out = kho_api.kho_min_max_goi_y(vat_tu_list=[self.VT])
		row = out[self.VT]
		self.assertIsNone(row["min"], "min vẫn phải ECHO None — chưa khai, không suy diễn")
		self.assertIsNotNone(row["rop"], "ROP=ADU×lead+0 vẫn có nghĩa, không được trả None")
		self.assertEqual(row["rop"], round(row["adu_90"] * 3, 6))

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


# ======================================================= M-1 (review round 2)

class TestPhanTrangVaTheDem(_KhoBmTestCase):
	"""DoD đòi phân trang phía server, nhưng trước bản sửa round 2 KHÔNG test
	nào truyền `trang`/`trang_thai` — `tong_dong`/`trang`/`so_dong_moi_trang`
	chưa từng được khẳng định. Kèm bẫy: khoá thẻ đếm "cham_rop" không trùng
	giá trị `trang_thai` của dòng ("sap_thieu") — bấm thẻ rồi gửi đúng khoá
	của thẻ trả về 0 dòng, im lặng."""

	def test_bam_the_cham_rop_loc_dung_dong_sap_thieu(self):
		"""M-1 — trước bản sửa, `trang_thai="cham_rop"` (đúng khoá thẻ đếm
		client tự nhiên gửi lại) không khớp dòng nào (dòng mang "sap_thieu"),
		bảng lọc ra RỖNG dù `cham_rop > 0`."""
		today = _today()
		_nhap(self.K, self.VT, 100, frappe.utils.add_days(today, -100))
		_xuat(self.K, self.VT, 78, frappe.utils.add_days(today, -50))  # tồn 22, dưới ROP nhưng trên min
		doc = frappe.get_doc("Customer Warehouse Item", self.VT)
		doc.ton_toi_thieu = 10
		doc.diem_dat_lai = 25
		doc.ton_toi_da = 60
		doc.save(ignore_permissions=True)

		frappe.set_user(BM_USER)
		out = kho_api.kho_canh_bao_ton(trang_thai="cham_rop")
		self.assertGreater(out["cham_rop"], 0)
		self.assertTrue(any(r["vat_tu"] == self.VT for r in out["dong"]), "thẻ 'cham_rop' phải lọc ra được dòng sap_thieu")
		self.assertTrue(all(r["trang_thai"] == "sap_thieu" for r in out["dong"]))

	def test_gia_tri_dong_that_sap_thieu_van_loc_duoc_truc_tiep(self):
		"""Client gửi thẳng giá trị dòng thật ("sap_thieu", không qua bí
		danh thẻ đếm) vẫn phải hoạt động — hai đường cùng dẫn tới một kết quả."""
		today = _today()
		_nhap(self.K, self.VT, 100, frappe.utils.add_days(today, -100))
		_xuat(self.K, self.VT, 78, frappe.utils.add_days(today, -50))
		doc = frappe.get_doc("Customer Warehouse Item", self.VT)
		doc.ton_toi_thieu = 10
		doc.diem_dat_lai = 25
		doc.ton_toi_da = 60
		doc.save(ignore_permissions=True)

		frappe.set_user(BM_USER)
		out = kho_api.kho_canh_bao_ton(trang_thai="sap_thieu")
		self.assertTrue(any(r["vat_tu"] == self.VT for r in out["dong"]))

	def test_phan_trang_cat_dung_trang_khong_lam_lech_tong_dong(self):
		"""Phân trang server thật — dựng 3 dòng "on_dinh" (đủ dữ liệu, không
		báo động, để không lẫn với các trạng thái khác), vá TẠM `_TRANG_KHO_
		CANH_BAO_TON` xuống 2 để không phải dựng 51+ vật tư mới đủ vượt trang
		mặc định 50."""
		today = _today()
		ten_vt = []
		for i in range(3):
			vt = frappe.get_doc({
				"doctype": "Customer Warehouse Item", "kho": self.K,
				"ma_vat_tu": f"VT-TRANG-{i}", "ten_vat_tu": f"Vật tư trang {i}",
				"dvt": "Cái", "lead_time_ngay": 3,
				"ton_toi_thieu": 1, "diem_dat_lai": 2, "ton_toi_da": 1000,
			}).insert(ignore_permissions=True)
			_nhap(self.K, vt.name, 500, frappe.utils.add_days(today, -40))
			_xuat(self.K, vt.name, 5, frappe.utils.add_days(today, -35))
			ten_vt.append(vt.name)

		truoc = dutru._TRANG_KHO_CANH_BAO_TON
		dutru._TRANG_KHO_CANH_BAO_TON = 2
		self.addCleanup(setattr, dutru, "_TRANG_KHO_CANH_BAO_TON", truoc)

		frappe.set_user(BM_USER)
		trang_1 = kho_api.kho_canh_bao_ton(trang=1)
		trang_2 = kho_api.kho_canh_bao_ton(trang=2)

		dong_1 = [r["vat_tu"] for r in trang_1["dong"] if r["vat_tu"] in ten_vt]
		dong_2 = [r["vat_tu"] for r in trang_2["dong"] if r["vat_tu"] in ten_vt]
		self.assertEqual(len(dong_1), 2, "trang 1 phải đúng 2 dòng (so_dong_moi_trang đã vá = 2)")
		self.assertEqual(len(dong_2), 1, "trang 2 phải còn đúng 1 dòng (3 dòng - 2 đã ở trang 1)")
		self.assertEqual(set(dong_1) & set(dong_2), set(), "hai trang không được trùng dòng")
		self.assertEqual(trang_1["so_dong_moi_trang"], 2)
		self.assertEqual(trang_1["trang"], 1)
		self.assertEqual(trang_2["trang"], 2)
		self.assertEqual(trang_1["tong_dong"], trang_2["tong_dong"], "tong_dong không đổi theo trang")


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
	"""AN-2 (báo cáo kiểm thử hệ thống, P1 #7): bốn màn mới khác (NCC, nhật
	ký, yêu cầu, HĐĐT) đều có cặp đối chứng "khách B gọi endpoint ->
	assertNotIn dữ liệu khách A VÀ assertIn dữ liệu của chính mình" — thiếu
	vế `assertIn` (positive control), một endpoint trả RỖNG cho mọi khách
	(bug hoàn toàn khác, hoàn toàn nghiêm trọng) vẫn làm cả hai test dưới đây
	xanh. Bổ sung vế còn thiếu ở cả hai test."""

	def test_kho_min_max_goi_y_tu_choi_vat_tu_kho_khac(self):
		frappe.set_user(PXN_USER)
		with self.assertRaises(frappe.PermissionError):
			kho_api.kho_min_max_goi_y(vat_tu_list=[self.VT])

		# Positive control: CÙNG phiên PXN_USER, vật tư CỦA CHÍNH PXN vẫn
		# phải trả về được — không thì assertRaises ở trên có thể xanh chỉ
		# vì toàn bộ endpoint đang ném PermissionError vô điều kiện.
		vt_pxn = self.kho["vt_pxn"]
		out = kho_api.kho_min_max_goi_y(vat_tu_list=[vt_pxn])
		self.assertIn(vt_pxn, out)

	def test_kho_canh_bao_ton_khong_lo_sang_khach_khac(self):
		today = _today()
		kho_pxn = self.kho["kho_pxn"]
		vt_pxn = self.kho["vt_pxn"]
		frappe.db.delete("Customer Stock Ledger Entry", {"kho": kho_pxn})
		frappe.db.delete("Customer Stock Lot Balance", {"kho": kho_pxn})
		_nhap(kho_pxn, vt_pxn, 100, frappe.utils.add_days(today, -40))
		_xuat(kho_pxn, vt_pxn, 10, frappe.utils.add_days(today, -35))

		# Positive control: vật tư CỦA CHÍNH BM phải có mặt — set min/ROP
		# (co_nguong=True) để BR-P3 (dutru.canh_bao_ton_rows) không loại nó
		# vì "chưa khai VÀ chưa đủ dữ liệu", cùng khuôn
		# TestTrangThaiThieu.test_ton_duoi_min_la_thieu_khong_phai_sap_thieu.
		# Thiếu vế này, một `kho_canh_bao_ton()` lỗi trả RỘNG luôn ("dong": [])
		# cho MỌI khách vẫn làm assertFalse bên dưới xanh — không phải cách
		# ly đúng, mà là hỏng hoàn toàn.
		doc = frappe.get_doc("Customer Warehouse Item", self.VT)
		doc.ton_toi_thieu = 10
		doc.diem_dat_lai = 25
		doc.ton_toi_da = 60
		doc.save(ignore_permissions=True)

		frappe.set_user(BM_USER)
		out = kho_api.kho_canh_bao_ton()
		self.assertTrue(
			any(r["vat_tu"] == self.VT for r in out["dong"]),
			"positive control: vật tư của chính BM phải có mặt trong kết quả của BM",
		)
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

	def test_i1_min_lon_hon_max_de_trong_rop_bi_chan(self):
		"""I-1 (review E5 round 2) — kịch bản thật: thủ kho gõ nhầm đảo hai
		ô (min=100, max=5), ĐỂ TRỐNG ROP. Trước bản sửa, phép kiểm ba-ngôi
		chỉ chạy khi ĐỦ CẢ BA nên lưu SẠCH không một cảnh báo — vật tư báo
		"Thiếu" đỏ vĩnh viễn (tồn luôn < 100) và sl_goi_y luôn = 0 (max=5
		luôn nhỏ hơn tồn). `min ≤ max` phải kiểm được ĐỘC LẬP với ROP."""
		doc = frappe.get_doc({
			"doctype": "Customer Warehouse Item", "kho": self.kho["kho_bm"],
			"ma_vat_tu": "VT-MINROP-6", "ten_vat_tu": "Test min>max khong ROP", "dvt": "Cái",
			"ton_toi_thieu": 100, "ton_toi_da": 5,
		})
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_i1_rop_am_bi_chan(self):
		"""I-1 — biến thể hai: `diem_dat_lai` âm lưu được trước bản sửa (chỉ
		`ton_toi_thieu` được kiểm âm) → `co_nguong=True` mà giá trị vô nghĩa,
		vật tư thoát BR-P3 vĩnh viễn với một ROP âm không ai chốt."""
		doc = frappe.get_doc({
			"doctype": "Customer Warehouse Item", "kho": self.kho["kho_bm"],
			"ma_vat_tu": "VT-MINROP-7", "ten_vat_tu": "Test ROP am", "dvt": "Cái",
			"diem_dat_lai": -5,
		})
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_i1_max_am_bi_chan(self):
		doc = frappe.get_doc({
			"doctype": "Customer Warehouse Item", "kho": self.kho["kho_bm"],
			"ma_vat_tu": "VT-MINROP-8", "ten_vat_tu": "Test max am", "dvt": "Cái",
			"ton_toi_da": -1,
		})
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_i2_xoa_trang_lead_time_khong_nem_loi(self):
		"""I-2 (review E5 round 2) — `_so_hoac_khong("")` ánh xạ MỌI ô trống
		thành 0 cho cả năm trường ngưỡng (kho/vat_tu.py), nhưng trước bản sửa
		`_validate_nguong_ton` xử RIÊNG `lead_time_ngay` bằng `not in (None,
		"")` — 0 KHÔNG rơi vào đó nên bị `not (1 <= 0 <= 60)` chặn NGAY TẠI Ô
		ĐANG TRỐNG. Bốn ô kia xoá trắng lưu bình thường; hành vi phải nhất
		quán: `lead_time_ngay=0` cũng là "chưa khai", không phải lỗi."""
		doc = frappe.get_doc({
			"doctype": "Customer Warehouse Item", "kho": self.kho["kho_bm"],
			"ma_vat_tu": "VT-MINROP-9", "ten_vat_tu": "Test lead time = 0", "dvt": "Cái",
			"lead_time_ngay": 0,
		})
		doc.insert(ignore_permissions=True)  # KHÔNG được ném ValidationError
		self.assertEqual(doc.lead_time_ngay, 0)

	def test_i2_xoa_trang_lead_time_qua_endpoint_khong_nem_loi(self):
		"""Đường thật khách đi qua — kho_vat_tu_sua(), không phải
		frappe.get_doc() trực tiếp."""
		self.addCleanup(frappe.set_user, "Administrator")
		vt = frappe.get_doc({
			"doctype": "Customer Warehouse Item", "kho": self.kho["kho_bm"],
			"ma_vat_tu": "VT-MINROP-10", "ten_vat_tu": "Test lead time endpoint",
			"dvt": "Cái", "lead_time_ngay": 5,
		}).insert(ignore_permissions=True)
		frappe.set_user(BM_USER)
		out = kho_api.kho_vat_tu_sua(vt.name, payload={"lead_time_ngay": ""})
		self.assertEqual(out["lead_time_ngay"], 0)


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


# ============================================================== US-E5.4 (job)

class TestJobCanhBaoTonDaily(_KhoBmTestCase):
	"""US-E5.4 — job daily + email tổng hợp, mặc định TẮT, bật theo kho."""

	def setUp(self):
		super().setUp()
		# Đảm bảo trạng thái sạch bất kể test khác trong CÙNG class đã bật
		# email/ghi gui_lan_cuoi trước đó (FrappeTestCase rollback theo CLASS).
		frappe.db.set_value("Customer Warehouse", self.K, {
			"canh_bao_ton_email_bat": 0,
			"canh_bao_ton_email_tan_suat": "Hàng tuần",
			"canh_bao_ton_email_gui_lan_cuoi": None,
		})
		frappe.flags.mute_emails = True
		self.addCleanup(frappe.flags.pop, "mute_emails", None)

	def _tao_vat_tu_thieu_ton(self):
		"""Một vật tư "Thiếu" thật (tồn < min) để job có gì mà cảnh báo."""
		today = _today()
		_nhap(self.K, self.VT, 100, frappe.utils.add_days(today, -100))
		_xuat(self.K, self.VT, 92, frappe.utils.add_days(today, -50))  # tồn còn 8
		doc = frappe.get_doc("Customer Warehouse Item", self.VT)
		doc.ton_toi_thieu = 10
		doc.diem_dat_lai = 25
		doc.ton_toi_da = 60
		doc.save(ignore_permissions=True)

	def test_mac_dinh_tat_khong_gui(self):
		from miyano_portal.portal_du_tru_job import quet_canh_bao_ton_daily

		self._tao_vat_tu_thieu_ton()
		dem = quet_canh_bao_ton_daily()
		self.assertEqual(
			frappe.db.get_value("Customer Warehouse", self.K, "canh_bao_ton_email_gui_lan_cuoi"),
			None,
			"kho chưa bật cảnh báo email không được job đụng tới",
		)
		self.assertEqual(dem, 0)

	def test_bat_va_co_vat_tu_thieu_thi_gui_email(self):
		from miyano_portal.portal_du_tru_job import quet_canh_bao_ton_daily

		frappe.db.set_value("Customer Warehouse", self.K, "canh_bao_ton_email_bat", 1)
		self._tao_vat_tu_thieu_ton()

		frappe.db.delete("Email Queue", {"reference_name": self.K})
		quet_canh_bao_ton_daily()

		nguoi_nhan = set(frappe.get_all(
			"Email Queue Recipient",
			filters={"parent": ["in", frappe.get_all(
				"Email Queue", filters={"reference_name": self.K}, pluck="name",
			)]},
			pluck="recipient",
		))
		self.assertIn(BM_USER, nguoi_nhan)
		self.assertEqual(
			frappe.utils.getdate(frappe.db.get_value(
				"Customer Warehouse", self.K, "canh_bao_ton_email_gui_lan_cuoi",
			)),
			_today(),
		)

	def test_m7_khong_tim_duoc_email_thi_khong_danh_dau_da_gui(self):
		"""M-7 (review E5 round 2) — trước bản sửa, không tìm được email
		(Contact chưa có/hỏng) vẫn khiến `gui_lan_cuoi` được ghi và `dem`
		tăng — kho đó bị đánh dấu "đã gửi hàng tuần" MÃI MÃI mà không ai
		nhận được gì, và tần suất "Hàng tuần" (dựa trên `gui_lan_cuoi`) sẽ
		không bao giờ thử lại. Monkeypatch `_email_khach_hang` thay vì xoá
		Contact demo dùng chung — xoá dữ liệu chung sẽ làm hỏng các test
		khác trong CÙNG class (FrappeTestCase chỉ rollback theo CLASS)."""
		import miyano_portal.portal_du_tru_job as job_mod

		truoc = job_mod._email_khach_hang
		job_mod._email_khach_hang = lambda customer: None
		self.addCleanup(setattr, job_mod, "_email_khach_hang", truoc)

		frappe.db.set_value("Customer Warehouse", self.K, "canh_bao_ton_email_bat", 1)
		self._tao_vat_tu_thieu_ton()

		dem = job_mod.quet_canh_bao_ton_daily()
		self.assertEqual(dem, 0, "không gửi được thì không được tính là đã gửi")
		self.assertIsNone(
			frappe.db.get_value("Customer Warehouse", self.K, "canh_bao_ton_email_gui_lan_cuoi"),
			"không được đánh dấu 'đã gửi' khi chưa ai nhận được gì — phải còn cơ hội thử lại",
		)

	def test_m7_mot_kho_loi_khong_lam_chet_luot_quet_cho_kho_con_lai(self):
		"""M-7 — một kho ném lỗi bất ngờ trong `canh_bao_ton_rows()` không
		được chặn đứng lượt quét cho các kho ĐANG BẬT email khác."""
		import miyano_portal.portal_du_tru_job as job_mod

		kho_pxn = self.kho["kho_pxn"]
		frappe.db.set_value("Customer Warehouse", kho_pxn, {
			"canh_bao_ton_email_bat": 1, "canh_bao_ton_email_tan_suat": "Hàng ngày",
			"canh_bao_ton_email_gui_lan_cuoi": None,
		})
		frappe.db.set_value("Customer Warehouse", self.K, "canh_bao_ton_email_bat", 1)
		self._tao_vat_tu_thieu_ton()

		truoc = dutru.canh_bao_ton_rows

		def _vo_canh_bao_ton_rows(kho, customer):
			if kho == kho_pxn:
				raise RuntimeError("dữ liệu hỏng giả lập cho kho PXN")
			return truoc(kho, customer)

		dutru.canh_bao_ton_rows = _vo_canh_bao_ton_rows
		self.addCleanup(setattr, dutru, "canh_bao_ton_rows", truoc)

		dem = job_mod.quet_canh_bao_ton_daily()
		self.assertEqual(dem, 1, "kho BM vẫn phải gửi được dù kho PXN lỗi")

	def test_khong_co_vat_tu_thieu_thi_khong_gui(self):
		"""Kho bật email nhưng KHÔNG có vật tư nào dưới min/ROP — không gửi
		email rỗng (cùng nguyên tắc BR-P3: cảnh báo trên dữ liệu/tình trạng
		không đáng báo động là cách nhanh nhất khiến khách tắt hết cảnh báo)."""
		from miyano_portal.portal_du_tru_job import quet_canh_bao_ton_daily

		frappe.db.set_value("Customer Warehouse", self.K, "canh_bao_ton_email_bat", 1)
		dem = quet_canh_bao_ton_daily()
		self.assertEqual(dem, 0)
		self.assertIsNone(
			frappe.db.get_value("Customer Warehouse", self.K, "canh_bao_ton_email_gui_lan_cuoi")
		)

	def test_tan_suat_hang_tuan_khong_gui_lai_trong_vong_7_ngay(self):
		from miyano_portal.portal_du_tru_job import quet_canh_bao_ton_daily

		frappe.db.set_value("Customer Warehouse", self.K, {
			"canh_bao_ton_email_bat": 1,
			"canh_bao_ton_email_tan_suat": "Hàng tuần",
			"canh_bao_ton_email_gui_lan_cuoi": frappe.utils.add_days(_today(), -3),
		})
		self._tao_vat_tu_thieu_ton()

		dem = quet_canh_bao_ton_daily()
		self.assertEqual(dem, 0, "mới gửi cách đây 3 ngày, tần suất Hàng tuần chưa tới hạn")

	def test_tan_suat_hang_tuan_gui_lai_sau_du_7_ngay(self):
		from miyano_portal.portal_du_tru_job import quet_canh_bao_ton_daily

		frappe.db.set_value("Customer Warehouse", self.K, {
			"canh_bao_ton_email_bat": 1,
			"canh_bao_ton_email_tan_suat": "Hàng tuần",
			"canh_bao_ton_email_gui_lan_cuoi": frappe.utils.add_days(_today(), -8),
		})
		self._tao_vat_tu_thieu_ton()

		dem = quet_canh_bao_ton_daily()
		self.assertEqual(dem, 1)

	def test_tan_suat_hang_ngay_gui_lai_sau_1_ngay(self):
		from miyano_portal.portal_du_tru_job import quet_canh_bao_ton_daily

		frappe.db.set_value("Customer Warehouse", self.K, {
			"canh_bao_ton_email_bat": 1,
			"canh_bao_ton_email_tan_suat": "Hàng ngày",
			"canh_bao_ton_email_gui_lan_cuoi": frappe.utils.add_days(_today(), -1),
		})
		self._tao_vat_tu_thieu_ton()

		dem = quet_canh_bao_ton_daily()
		self.assertEqual(dem, 1, "tần suất Hàng ngày: đã gửi HÔM QUA thì hôm nay phải đến hạn")

	def test_da_gui_hom_nay_roi_thi_khong_gui_lai_trong_ngay(self):
		"""Job chạy `daily` — hai lần gọi trong CÙNG một ngày (ví dụ retry
		thủ công) không được gửi trùng email, kể cả tần suất "Hàng ngày"."""
		from miyano_portal.portal_du_tru_job import quet_canh_bao_ton_daily

		frappe.db.set_value("Customer Warehouse", self.K, {
			"canh_bao_ton_email_bat": 1,
			"canh_bao_ton_email_tan_suat": "Hàng ngày",
			"canh_bao_ton_email_gui_lan_cuoi": _today(),
		})
		self._tao_vat_tu_thieu_ton()

		dem = quet_canh_bao_ton_daily()
		self.assertEqual(dem, 0)


# ============================================================ US-E5.1 (lưu)

class TestLuuNguongTonQuaEndpoint(_KhoBmTestCase):
	"""US-E5.1 khép vòng: "bấm [Gợi ý từ tiêu thụ] rồi khách TỰ LƯU" — chỗ
	LƯU đó là `kho_vat_tu_sua`. Trước bản sửa này (advisor round 1),
	`vat_tu.TRUONG_MO_TA`/`TRUONG_KHOA` không hề nhắc tới năm trường ngưỡng
	tồn, nên payload gửi `ton_toi_thieu`/`diem_dat_lai`/`ton_toi_da`/
	`lead_time_ngay`/`boi_so_dat` bị ÂM THẦM BỎ QUA — validate min≤ROP≤max
	ở CustomerWarehouseItem có thật, nhưng KHÔNG CÓ ĐƯỜNG GHI nào từ cổng
	khách hàng chạm tới được nó. Toàn bộ US-E5.1 (bên cạnh "gợi ý", còn "tự
	lưu") chỉ đóng vòng khi test này đi qua ĐÚNG kho_api.kho_vat_tu_sua()."""

	def test_luu_thanh_cong_qua_endpoint(self):
		frappe.set_user(BM_USER)
		out = kho_api.kho_vat_tu_sua(self.VT, payload={
			"ton_toi_thieu": 10, "diem_dat_lai": 25, "ton_toi_da": 60,
			"lead_time_ngay": 3, "boi_so_dat": 10,
		})
		self.assertEqual(out["ton_toi_thieu"], 10)
		self.assertEqual(out["diem_dat_lai"], 25)
		self.assertEqual(out["ton_toi_da"], 60)
		self.assertEqual(out["lead_time_ngay"], 3)
		self.assertEqual(out["boi_so_dat"], 10)

		# Đọc lại từ DB (không phải chỉ tin giá trị trả về của chính lệnh lưu).
		luu_lai = frappe.db.get_value(
			"Customer Warehouse Item", self.VT,
			["ton_toi_thieu", "diem_dat_lai", "ton_toi_da"], as_dict=True,
		)
		self.assertEqual(float(luu_lai.ton_toi_thieu), 10)
		self.assertEqual(float(luu_lai.diem_dat_lai), 25)
		self.assertEqual(float(luu_lai.ton_toi_da), 60)

	def test_kho_vat_tu_list_tra_ve_nguong_da_luu(self):
		"""Màn danh mục/form vật tư phải đọc lại được giá trị vừa lưu — nếu
		không, khách "lưu xong" nhưng mở lại form vẫn thấy trống."""
		frappe.set_user(BM_USER)
		kho_api.kho_vat_tu_sua(self.VT, payload={"ton_toi_thieu": 10, "diem_dat_lai": 25, "ton_toi_da": 60})
		row = next(r for r in kho_api.kho_vat_tu_list() if r["name"] == self.VT)
		self.assertEqual(row["ton_toi_thieu"], 10)
		self.assertEqual(row["diem_dat_lai"], 25)
		self.assertEqual(row["ton_toi_da"], 60)

	def test_min_lon_hon_rop_bi_chan_qua_endpoint_thong_diep_tieng_viet(self):
		"""Chốt min≤ROP≤max của CustomerWarehouseItem PHẢI vươn được tới cổng
		— không phải chỉ đúng khi gọi thẳng frappe.get_doc() trong test."""
		frappe.set_user(BM_USER)
		with self.assertRaises(frappe.ValidationError) as ctx:
			kho_api.kho_vat_tu_sua(self.VT, payload={
				"ton_toi_thieu": 30, "diem_dat_lai": 25, "ton_toi_da": 60,
			})
		self.assertIn("Điểm đặt lại", str(ctx.exception))

	def test_vat_tu_kho_khac_bi_tu_choi(self):
		frappe.set_user(PXN_USER)
		with self.assertRaises(frappe.PermissionError):
			kho_api.kho_vat_tu_sua(self.VT, payload={"ton_toi_thieu": 10})

	def test_xoa_trang_o_tra_ve_chua_khai(self):
		"""Xoá trắng một ô đã lưu -> DB ghi 0 (NOT NULL DEFAULT 0), và
		`kho_min_max_goi_y`/`kho_canh_bao_ton` phải đọc lại đúng là "chưa
		khai" (dutru.chua_khai(0) == True), không phải "khách chốt min=0"."""
		frappe.set_user(BM_USER)
		kho_api.kho_vat_tu_sua(self.VT, payload={"ton_toi_thieu": 10, "diem_dat_lai": 25, "ton_toi_da": 60})
		kho_api.kho_vat_tu_sua(self.VT, payload={"ton_toi_thieu": ""})

		row = next(r for r in kho_api.kho_vat_tu_list() if r["name"] == self.VT)
		self.assertEqual(row["ton_toi_thieu"], 0)
		self.assertTrue(dutru.chua_khai(row["ton_toi_thieu"]))

	def test_khong_lam_hong_gia_tri_khi_khong_gui_truong_nguong(self):
		"""Sửa TÊN vật tư (không đụng tới ngưỡng) không được vô tình xoá mất
		ngưỡng đã lưu trước đó — vòng lặp `TRUONG_NGUONG_TON` chỉ set khi
		field CÓ MẶT trong payload (`if truong in du_lieu`), không phải ghi
		đè vô điều kiện."""
		frappe.set_user(BM_USER)
		kho_api.kho_vat_tu_sua(self.VT, payload={"ton_toi_thieu": 10, "diem_dat_lai": 25, "ton_toi_da": 60})
		kho_api.kho_vat_tu_sua(self.VT, payload={"ten_vat_tu": "Tên mới"})

		row = next(r for r in kho_api.kho_vat_tu_list() if r["name"] == self.VT)
		self.assertEqual(row["ten_vat_tu"], "Tên mới")
		self.assertEqual(row["ton_toi_thieu"], 10)
		self.assertEqual(row["diem_dat_lai"], 25)
