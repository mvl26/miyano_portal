"""E4 phần B — nhật ký vật tư, NXT theo đợt (FIFO), nhóm "Không có hạn dùng".

Bám 40_TestCases.md TC-E4-07 (nhật ký, đối chiếu kho_ton, dòng đã đảo không bị
giấu), TC-E4-08 (bộ số chuẩn FIFO của PRD E4 §US-E4.7) và TC-E4-09 (cảnh báo
hạn: lô không hạn dùng vào nhóm riêng, VĐ-2).

Ngày dùng trong các test KHÔNG cancel phiếu (TestBaoCaoDotFifo) là ngày TUYỆT
ĐỐI, đúng như bộ số PRD yêu cầu (01/08, 10/08, báo cáo 30/09 -> tuổi tồn 51
ngày là một quan hệ SỐ HỌC cố định, không phải quan hệ với "hôm nay" lúc chạy
test). MỌI test có cancel phiếu (phiếu đảo luôn mang ngay=frappe.utils.today(),
xem customer_stock_receipt.py/_tao_phieu_dao) PHẢI dùng ngày TƯƠNG ĐỐI so với
frappe.utils.today() — cùng lý do "date rot" đã ghi trong test_kho_reports.py,
và cùng lý do review E4 phần B (M-3) bắt lỗi
`TestBaoCaoDotPhieuDao` bản trước dùng ngày tuyệt đối: sau khi I-2 sửa
`bao_cao_dot_rows()` thành kỳ-aware (một phiếu đảo lập SAU `den_ngay` không
còn được trừ vào SL nhập của đợt), một `den_ngay` tuyệt đối trong quá khứ
luôn đứng TRƯỚC ngày cancel thật (hôm nay) — đợt không còn bị loại nữa, và
assertion cũ đỏ. Bài học: bất kỳ test nào gọi `.cancel()` đều gắn với
`frappe.utils.today()` một cách không thể tránh, nên phải tính mọi mốc ngày
khác TƯƠNG ĐỐI với nó.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import kho as kho_api
from miyano_portal.kho import reports
from miyano_portal.setup.seed_kho_demo import seed_kho_demo

BM_USER = "bvbm@demo.miyano"
PXN_USER = "pxnabc@demo.miyano"


def _today():
	return frappe.utils.getdate(frappe.utils.today())


def _iso(d):
	return frappe.utils.getdate(d).strftime("%Y-%m-%d")


def _nhap(kho, vat_tu, so_luong, don_gia, ngay, so_lo="LO-A", han=None, loai_nhap="Nhập khác", **extra):
	doc = frappe.get_doc({
		"doctype": "Customer Stock Receipt",
		"kho": kho, "ngay": _iso(ngay), "loai_nhap": loai_nhap,
		"nguoi_giao": "Trần Văn Giao",
		"items": [{
			"vat_tu": vat_tu, "so_lo": so_lo, "han_su_dung": han,
			"so_luong": so_luong, "don_gia": don_gia,
		}],
		**extra,
	})
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc


def _xuat(kho, vat_tu, so_luong, ngay, so_lo="LO-A"):
	doc = frappe.get_doc({
		"doctype": "Customer Stock Issue",
		"kho": kho, "ngay": _iso(ngay), "loai_xuat": "Xuất sử dụng",
		"noi_nhan": "Khoa Nội", "nguoi_nhan": "Y tá Lan",
		"items": [{"vat_tu": vat_tu, "so_lo": so_lo, "so_luong": so_luong}],
	})
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc


class _KhoBmTestCase(FrappeTestCase):
	"""Base dùng lại đúng khuôn test_kho_reports.py::_KhoBmTestCase: dọn sổ/tồn
	của kho BM trước mỗi test vì các báo cáo ở đây cộng dồn trên TOÀN BỘ sổ."""

	def setUp(self):
		self.kho = seed_kho_demo()
		self.K = self.kho["kho_bm"]
		self.VT = self.kho["vt_bm"]
		frappe.db.delete("Customer Stock Ledger Entry", {"kho": self.K})
		frappe.db.delete("Customer Stock Lot Balance", {"kho": self.K})

	def tearDown(self):
		frappe.set_user("Administrator")


# ---------------------------------------------------------------------------
# TC-E4-09 (VĐ-2, US-E4.8): lô không có hạn dùng KHÔNG được lẫn vào "Sắp hết
# hạn"/"Đã hết hạn" — hồi quy của lỗi ifnull/coalesce trong canh_bao_han_rows.
# ---------------------------------------------------------------------------


class TestCanhBaoHanKhongCoHanDung(_KhoBmTestCase):
	def test_lot_without_expiry_forms_its_own_group_not_counted_as_expiring(self):
		today = _today()
		_nhap(self.K, self.VT, 10, 1000, frappe.utils.add_days(today, -5),
			  so_lo="LO-VO-HAN", han=None)
		_nhap(self.K, self.VT, 5, 1000, frappe.utils.add_days(today, -5),
			  so_lo="LO-CO-HAN", han=frappe.utils.add_days(today, 10))

		rows = reports.canh_bao_han_rows(self.K, so_ngay=90)
		by_lo = {r["so_lo"]: r for r in rows}

		self.assertIn("LO-VO-HAN", by_lo, "lô không hạn dùng phải VẪN xuất hiện trong báo cáo")
		vo_han = by_lo["LO-VO-HAN"]
		self.assertEqual(vo_han["trang_thai"], "Không có hạn dùng")
		self.assertIsNone(vo_han["han_su_dung"])
		self.assertIsNone(vo_han["so_ngay_con_lai"])

		# Hồi quy trực tiếp của lỗi ifnull/coalesce: TRƯỚC bản sửa, lô này bị
		# kéo vào SQL bằng coalesce(han_su_dung, '0001-01-01') <= han_toi, rồi
		# frappe.utils.getdate(None) trả về NGÀY HÔM NAY khiến nó hiện ra là
		# "Sắp hết hạn" với 0 ngày còn lại — hai dòng assert dưới đây sẽ ĐỎ
		# nếu lỗi đó quay lại.
		self.assertNotEqual(vo_han["trang_thai"], "Sắp hết hạn")
		self.assertNotEqual(vo_han["trang_thai"], "Đã hết hạn")

		self.assertEqual(by_lo["LO-CO-HAN"]["trang_thai"], "Sắp hết hạn")

	def test_api_endpoint_also_separates_no_expiry_group(self):
		"""Cùng kiểm tra qua đúng cổng portal (kho_canh_bao_han), không chỉ
		hàm reports.* trần — endpoint là nơi khách hàng thật sự chạm tới."""
		today = _today()
		_nhap(self.K, self.VT, 8, 1000, frappe.utils.add_days(today, -1), so_lo="LO-VO-HAN-2", han=None)
		frappe.set_user(BM_USER)
		try:
			rows = kho_api.kho_canh_bao_han(so_ngay=90)
		finally:
			frappe.set_user("Administrator")
		row = next(r for r in rows if r["so_lo"] == "LO-VO-HAN-2")
		self.assertEqual(row["trang_thai"], "Không có hạn dùng")


# ---------------------------------------------------------------------------
# TC-E4-07 (US-E4.6, BR-D2): nhật ký vật tư — đối chiếu chéo với kho_ton, dòng
# đã đảo không bị giấu, phân trang server.
# ---------------------------------------------------------------------------


class TestNhatKyVatTu(_KhoBmTestCase):
	def test_last_row_running_balance_matches_kho_ton_and_reversed_rows_are_shown(self):
		today = _today()
		d = lambda n: frappe.utils.add_days(today, n)

		_nhap(self.K, self.VT, 100, 1000, d(-30), so_lo="LO-A")
		_nhap(self.K, self.VT, 15, 1000, d(-28), so_lo="LO-A")
		_nhap(self.K, self.VT, 50, 1000, d(-20), so_lo="LO-A")
		_nhap(self.K, self.VT, 20, 2000, d(-15), so_lo="LO-B")
		r3 = _nhap(self.K, self.VT, 30, 2000, d(-14), so_lo="LO-B")
		# Huỷ NGAY trong khi lô LO-B còn đủ 30 đơn vị (chưa có lượt xuất nào
		# đụng tới LO-B) — huỷ trễ hơn sẽ bị _chan_neu_dao_lam_am_ton chặn.
		r3.cancel()

		_xuat(self.K, self.VT, 40, d(-10), so_lo="LO-A")
		_xuat(self.K, self.VT, 15, d(-9), so_lo="LO-B")
		_xuat(self.K, self.VT, 5, d(-8), so_lo="LO-B")
		_xuat(self.K, self.VT, 5, d(-7), so_lo="LO-A")
		x2 = _xuat(self.K, self.VT, 30, d(-6), so_lo="LO-A")
		x2.cancel()

		# 12 dòng sổ (TC-E4-07): 4 phiếu nhập KHÔNG bị đảo + 1 phiếu nhập bị
		# đảo (dòng gốc + dòng đảo) + 4 phiếu xuất KHÔNG bị đảo + 1 phiếu xuất
		# bị đảo (dòng gốc + dòng đảo) = 4+2+4+2 = 12; đúng 2 dòng da_dao=1.
		#
		# TC-E4-07 (P1 #6, báo cáo kiểm thử hệ thống): qua ĐÚNG cổng khách
		# (kho_api.kho_nhat_ky), kho suy từ phiên BM_USER — không tiêm tay
		# `self.K` nữa, để một lỗi suy diễn tenant ở get_portal_kho()/
		# _vat_tu_cua_kho() có cơ hội làm bộ số chuẩn này đỏ. Theo khuôn
		# test_e8_cap_phat.py::_chay().
		frappe.set_user(BM_USER)
		try:
			result = kho_api.kho_nhat_ky(self.VT, _iso(d(-60)), _iso(today), trang=1)
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(result["tong_dong"], 12)
		self.assertEqual(len(result["dong"]), 12)
		self.assertEqual(result["trang"], 1)
		self.assertEqual(result["so_dong_moi_trang"], 50)

		da_dao_rows = [r for r in result["dong"] if r["da_dao"]]
		self.assertEqual(
			len(da_dao_rows), 2,
			"dòng đã đảo phải VẪN xuất hiện trong nhật ký (BR-D2), không bị giấu đi",
		)
		# Cả hai dòng đảo phải đúng là dòng GỐC của r3 (nhập) và x2 (xuất) —
		# không phải dòng bù trừ (dòng bù trừ mang chung_tu là phiếu đảo mới
		# sinh, không phải r3.name/x2.name, và da_dao=0 trên chính nó).
		self.assertEqual({r["phieu"] for r in da_dao_rows}, {r3.name, x2.name})

		# Bất biến chính của TC-E4-07: tồn sau giao dịch của DÒNG CUỐI (đã
		# sắp theo thời gian) phải bằng đúng tồn hiện tại của vật tư theo
		# đường tính ĐỘC LẬP kho_ton()/ton_hien_tai_rows() (cache Customer
		# Stock Lot Balance dựng từ cùng sổ nhưng qua rebuild delta-theo-lô,
		# không phải luỹ kế theo thời gian như ở đây).
		hien_tai = {r["vat_tu"]: r["so_luong"] for r in reports.ton_hien_tai_rows(self.K)}
		# P1 #6: rỗng phải ĐỎ, không được âm thầm so ton_sau với 0.0 — trước
		# bản sửa, `.get(self.VT, 0.0)` biến "ton_hien_tai_rows() rỗng" (một
		# lỗi thật) thành một phép so sánh vô nghĩa nhưng vẫn có thể pass nếu
		# ton_sau của dòng cuối tình cờ cũng bằng 0.
		self.assertIn(
			self.VT, hien_tai,
			"ton_hien_tai_rows() không trả vật tư của test — rỗng ở đây từng "
			"bị .get(..., 0.0) nuốt câm lặng thay vì làm assertion dưới đỏ",
		)
		tong_hien_tai = hien_tai[self.VT]
		self.assertEqual(result["dong"][-1]["ton_sau"], tong_hien_tai)

		# la_dao: đúng HAI dòng LÀ bút toán bù trừ (dòng đảo mới sinh, khác
		# `phieu` với dòng gốc) — khác `da_dao` (đánh dấu dòng GỐC đã bị đảo).
		# Không dòng nào trong 12 dòng vừa đếm ở trên vừa da_dao=True vừa
		# la_dao=True: một cặp huỷ luôn tách thành đúng một dòng mỗi cờ.
		la_dao_rows = [r for r in result["dong"] if r["la_dao"]]
		self.assertEqual(len(la_dao_rows), 2)
		self.assertEqual({r["phieu"] for r in la_dao_rows} & {r3.name, x2.name}, set())
		self.assertFalse(any(r["da_dao"] and r["la_dao"] for r in result["dong"]))

	def test_reversal_row_of_a_cancelled_ncc_receipt_is_not_relabelled_as_miyano(self):
		"""I-1 (review E4 phần B): `_tao_phieu_dao()` không copy `ncc` sang
		phiếu đảo (`loai_nhap="Phiếu đảo"`, `ncc=None`) — dòng bù trừ của một
		đợt "Mua ngoài (NCC khác)" bị huỷ KHÔNG được quy về nguồn "Miyano".
		Nó cũng không phải một đợt hàng thật nên `dot` không mang tên phiếu
		đảo (không có ý nghĩa mã đợt) mà trỏ ngược về đợt gốc bị huỷ."""
		ncc = frappe.get_doc({
			"doctype": "Customer Supplier", "kho": self.K, "ten_ncc": "Cty TNHH ABC",
		}).insert(ignore_permissions=True)

		today = _today()
		goc = _nhap(
			self.K, self.VT, 50, 1000, frappe.utils.add_days(today, -10), so_lo="LO-NCC",
			loai_nhap="Mua ngoài (NCC khác)", ncc=ncc.name, so_chung_tu_ncc="HD-01",
		)
		goc.cancel()

		result = reports.nhat_ky_rows(self.K, self.VT, frappe.utils.add_days(today, -30), today)
		dong_goc = next(r for r in result["dong"] if r["phieu"] == goc.name)
		dong_dao = next(r for r in result["dong"] if r["phieu"] != goc.name and r["loai"] == "Nhập")

		# Dòng GỐC không đổi hành vi: vẫn mang đúng nguồn NCC, vẫn là đợt của
		# chính nó, vẫn mờ đi (da_dao) và KHÔNG phải bút toán bù trừ.
		self.assertEqual(dong_goc["nguon"], "Cty TNHH ABC")
		self.assertEqual(dong_goc["dot"], goc.name)
		self.assertTrue(dong_goc["da_dao"])
		self.assertFalse(dong_goc["la_dao"])

		# Dòng ĐẢO: không bị quy về "Miyano", trỏ ngược đúng đợt gốc, và tự
		# mang dấu hiệu la_dao — trước bản sửa nó không có dấu hiệu nào.
		self.assertNotEqual(dong_dao["nguon"], "Miyano")
		self.assertEqual(dong_dao["nguon"], "")
		self.assertEqual(dong_dao["dot"], goc.name)
		self.assertTrue(dong_dao["la_dao"])
		self.assertFalse(dong_dao["da_dao"])

	def test_pagination_size_is_fifty_and_page_two_is_the_remainder(self):
		today = _today()
		# 55 dòng nhập rời rạc (mỗi dòng 1 đơn vị, số lô khác nhau) -> hai
		# trang: 50 + 5.
		for i in range(55):
			_nhap(self.K, self.VT, 1, 1000, frappe.utils.add_days(today, -60 + i),
				  so_lo=f"LO-{i:02d}")

		trang_1 = reports.nhat_ky_rows(self.K, self.VT, frappe.utils.add_days(today, -60), today, trang=1)
		trang_2 = reports.nhat_ky_rows(self.K, self.VT, frappe.utils.add_days(today, -60), today, trang=2)
		self.assertEqual(trang_1["tong_dong"], 55)
		self.assertEqual(len(trang_1["dong"]), 50)
		self.assertEqual(trang_2["tong_dong"], 55)
		self.assertEqual(len(trang_2["dong"]), 5)
		# Hai trang không trùng dòng nào.
		ten_trang_1 = {r["phieu"] for r in trang_1["dong"]}
		ten_trang_2 = {r["phieu"] for r in trang_2["dong"]}
		self.assertEqual(ten_trang_1 & ten_trang_2, set())

	def test_endpoint_rejects_vat_tu_of_another_customer(self):
		frappe.set_user(BM_USER)
		today = _today()
		try:
			with self.assertRaises(frappe.PermissionError):
				kho_api.kho_nhat_ky(
					self.kho["vt_pxn"],
					_iso(frappe.utils.add_days(today, -30)),
					_iso(today),
				)
		finally:
			frappe.set_user("Administrator")

	def test_endpoint_reaches_own_item_positive_control(self):
		today = _today()
		_nhap(self.K, self.VT, 5, 1000, frappe.utils.add_days(today, -1))
		frappe.set_user(BM_USER)
		try:
			out = kho_api.kho_nhat_ky(
				self.VT, _iso(frappe.utils.add_days(today, -5)), _iso(today),
			)
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(out["tong_dong"], 1)
		self.assertEqual(out["dong"][0]["sl_nhap"], 5)


# ---------------------------------------------------------------------------
# TC-E4-08 (US-E4.7, BR-D1/D3): NXT theo đợt, phân bổ FIFO — bộ số chuẩn PRD.
# ---------------------------------------------------------------------------


class TestBaoCaoDotFifo(_KhoBmTestCase):
	def setUp(self):
		super().setUp()
		self.addCleanup(
			frappe.db.set_single_value, "Miyano Portal Settings",
			"nguong_cham_luan_chuyen_ngay", 90,
		)

	def test_prd_reference_numbers(self):
		"""Bộ số chuẩn của brief-B / PRD US-E4.7:
		Lô L1 nhận 2 đợt: PNK-001 (01/08, nhập 100), PNK-005 (10/08, nhập 50).
		Tổng đã xuất của L1 = 120. Báo cáo ngày 30/09, ngưỡng chậm 30 ngày.
		-> PNK-001: còn 0, 100% tiêu thụ, không cờ.
		-> PNK-005: còn 30, tuổi tồn 51 ngày, 40% tiêu thụ, cờ chậm luân chuyển.
		"""
		frappe.db.set_single_value("Miyano Portal Settings", "nguong_cham_luan_chuyen_ngay", 30)

		pnk001 = _nhap(self.K, self.VT, 100, 1000, "2026-08-01", so_lo="L1")
		pnk005 = _nhap(self.K, self.VT, 50, 1000, "2026-08-10", so_lo="L1")
		_xuat(self.K, self.VT, 120, "2026-08-20", so_lo="L1")

		# TC-E4-08 (P1 #6, báo cáo kiểm thử hệ thống): bộ số chuẩn PRD phải đi
		# qua ĐÚNG cổng khách (kho_api.kho_bao_cao_dot), kho suy từ phiên
		# BM_USER — trước bản sửa, test duy nhất qua session
		# (test_endpoint_reaches_own_data) chỉ assertTrue(any(...)), gần như
		# luôn đúng. Theo khuôn test_e8_cap_phat.py::_chay().
		frappe.set_user(BM_USER)
		try:
			rows = kho_api.kho_bao_cao_dot("2026-01-01", "2026-09-30", vat_tu=self.VT)
		finally:
			frappe.set_user("Administrator")
		by_dot = {r["dot"]: r for r in rows}
		self.assertEqual(set(by_dot), {pnk001.name, pnk005.name})

		r001 = by_dot[pnk001.name]
		self.assertEqual(r001["sl_nhap"], 100)
		self.assertEqual(r001["da_xuat"], 100)
		self.assertEqual(r001["con_lai"], 0)
		self.assertEqual(r001["pct_tieu_thu"], 100)
		self.assertFalse(r001["cham_luan_chuyen"])
		self.assertEqual(r001["nguon"], "Miyano")

		r005 = by_dot[pnk005.name]
		self.assertEqual(r005["sl_nhap"], 50)
		self.assertEqual(r005["da_xuat"], 20)
		self.assertEqual(r005["con_lai"], 30)
		self.assertEqual(r005["tuoi_ton_ngay"], 51)
		self.assertEqual(r005["pct_tieu_thu"], 40)
		self.assertTrue(r005["cham_luan_chuyen"])

	def test_zero_or_negative_threshold_means_no_flag(self):
		"""Brief: ngưỡng <= 0 = "không áp ngưỡng" — kể cả khi tuổi tồn rất lớn.

		M-1 (review E4 phần B): tên test cũ hứa "zero_or_negative" nhưng chỉ
		set 0 — thêm ca số ÂM thật (subTest) để tên test không hứa nhiều hơn
		nó kiểm."""
		for nguong_dat in (0, -5):
			with self.subTest(nguong_dat=nguong_dat):
				frappe.db.set_single_value(
					"Miyano Portal Settings", "nguong_cham_luan_chuyen_ngay", nguong_dat
				)
				so_lo = f"L-CU-{nguong_dat}"
				_nhap(self.K, self.VT, 10, 1000, "2026-01-01", so_lo=so_lo)
				rows = reports.bao_cao_dot_rows(self.K, "2026-01-01", "2026-12-31", vat_tu=self.VT)
				rows = [r for r in rows if r["lo"] == so_lo]
				self.assertTrue(rows)
				self.assertFalse(any(r["cham_luan_chuyen"] for r in rows))

	def test_default_threshold_applies_when_settings_never_configured(self):
		"""C-1 (Critical, review E4 phần B): trên một site/CSDL nơi CHƯA AI mở
		Miyano Portal Settings ra bấm Lưu, `tabSingles` không có dòng nào cho
		field này — `get_single_value` trả `None`. `_nguong_cham_luan_chuyen()`
		PHẢI rơi về mặc định 90 (khớp `20_DataDict.md`), KHÔNG PHẢI 0.

		Đo trực nghiệm TRƯỚC bản sửa này trên `erptest.local`: SINGLES ROW
		rỗng -> `get_single_value` trả 0 -> `nguong=0` -> cờ "chậm luân
		chuyển" tắt câm lặng cho MỌI đợt, bất kể tuổi tồn — nửa giá trị
		nghiệp vụ của US-E4.7 chết im lặng trên đúng tình huống "site khách
		mới, chưa ai đụng tới Settings".

		Dùng `set_single_value(..., None)` (KHÔNG phải xoá thẳng bằng
		`frappe.db.delete("Singles", ...)`) để vừa đưa field về đúng trạng
		thái "rỗng" vừa dọn sạch `frappe.db.value_cache` — `get_single_value`
		cache theo tiến trình, xoá thẳng bảng mà không qua API này sẽ để lại
		giá trị cache CŨ của một test khác chạy trước trong cùng phiên, làm
		test tự dối. Cùng khuôn `test_e2_nguong_duyet.py::
		test_nguong_de_trong_doc_ra_0` đã dùng cho `nguong_duyet_2_tang`."""
		frappe.db.set_single_value("Miyano Portal Settings", "nguong_cham_luan_chuyen_ngay", None)

		# -150 ngày, không -400: `Customer Warehouse.ngay_bat_dau` của kho demo
		# là 2026-01-01 (voucher.validate_ngay chặn phiếu trước mốc đó) —
		# 150 ngày đã đủ vượt xa ngưỡng mặc định 90 mà vẫn nằm trong khoảng
		# hợp lệ của kho tại thời điểm chạy test.
		today = _today()
		_nhap(self.K, self.VT, 10, 1000, frappe.utils.add_days(today, -150), so_lo="L-CHUA-CAU-HINH")
		rows = reports.bao_cao_dot_rows(
			self.K, frappe.utils.add_days(today, -200), today, vat_tu=self.VT
		)
		self.assertTrue(rows)
		self.assertTrue(
			rows[0]["cham_luan_chuyen"],
			"một đợt 150 ngày tuổi phải bị gắn cờ chậm luân chuyển kể cả khi "
			"Settings CHƯA TỪNG được cấu hình (mặc định 90 ngày, không phải 0)",
		)

	def test_endpoint_reaches_own_data(self):
		_nhap(self.K, self.VT, 10, 1000, "2026-08-01", so_lo="L1")
		frappe.set_user(BM_USER)
		try:
			rows = kho_api.kho_bao_cao_dot("2026-01-01", "2026-09-30")
		finally:
			frappe.set_user("Administrator")
		self.assertTrue(any(r["vat_tu"] == self.VT for r in rows))


class TestBaoCaoDotPhieuDao(_KhoBmTestCase):
	"""NL-8.2: đợt có phiếu bị đảo -> SL nhập của đợt trừ phần đã đảo, TÍNH
	TỚI `den_ngay` của báo cáo (I-2, review E4 phần B — không phải trạng thái
	`da_dao` hiện tại, xem docstring bao_cao_dot_rows()). Vì huỷ luôn đảo
	TOÀN BỘ một phiếu nhập (không có huỷ một phần), "trừ phần đã đảo" khi
	phiếu đảo NẰM TRONG kỳ báo cáo tương đương với việc đợt đó biến mất khỏi
	báo cáo — không phải hiện ra với SL nhập = 0.

	Mọi ngày ở đây TƯƠNG ĐỐI so với frappe.utils.today() — phiếu đảo do
	.cancel() sinh ra luôn mang ngay=hôm nay (xem docstring đầu file)."""

	def test_cancelled_receipt_is_excluded_and_its_reversal_is_not_a_batch(self):
		today = _today()
		d = lambda n: frappe.utils.add_days(today, n)

		r1 = _nhap(self.K, self.VT, 40, 1000, d(-60), so_lo="LO-X")
		r2 = _nhap(self.K, self.VT, 25, 1000, d(-55), so_lo="LO-X")
		r2.cancel()  # ngay của phiếu đảo = hôm nay

		# den_ngay = hôm nay -> phiếu đảo (ngay=hôm nay) NẰM TRONG kỳ, đợt r2
		# phải bị trừ ròng về 0 và loại khỏi báo cáo, đúng hành vi "báo cáo
		# hiện tại" trước khi I-2 từng đúng theo cách khác (xem test dưới cho
		# trường hợp NGƯỢC LẠI — báo cáo kỳ đã đóng, phiếu đảo đứng SAU).
		rows = reports.bao_cao_dot_rows(self.K, d(-90), today, vat_tu=self.VT)
		dots = {r["dot"] for r in rows}
		self.assertIn(r1.name, dots)
		self.assertNotIn(
			r2.name, dots,
			"đợt đã bị huỷ hoàn toàn TRONG kỳ báo cáo không được đếm là hàng còn (NL-8.2)",
		)

		dao_name = frappe.db.get_value(
			"Customer Stock Receipt", {"phieu_goc": r2.name, "loai_nhap": "Phiếu đảo"}, "name"
		)
		self.assertTrue(dao_name)
		self.assertNotIn(
			dao_name, dots,
			"phiếu đảo là bút toán bù trừ, không phải một đợt hàng thật",
		)

		row1 = next(r for r in rows if r["dot"] == r1.name)
		self.assertEqual(row1["sl_nhap"], 40)
		self.assertEqual(row1["con_lai"], 40)

	def test_old_period_report_is_immutable_after_a_later_cancellation(self):
		"""I-2: huỷ một đợt SAU `den_ngay` không được viết lại một báo cáo của
		một kỳ ĐÃ ĐÓNG trước đó — chạy lại đúng báo cáo cũ phải ra CÙNG một
		kết quả trước và sau khi huỷ, vì tại thời điểm `den_ngay`, đợt đó
		trong thực tế vẫn còn nguyên (chưa ai huỷ gì cả)."""
		today = _today()
		d = lambda n: frappe.utils.add_days(today, n)

		a = _nhap(self.K, self.VT, 100, 1000, d(-60), so_lo="L1")
		_nhap(self.K, self.VT, 50, 1000, d(-50), so_lo="L1")
		_xuat(self.K, self.VT, 30, d(-40), so_lo="L1")

		tu_cu, den_cu = d(-90), d(-30)
		truoc = reports.bao_cao_dot_rows(self.K, tu_cu, den_cu, vat_tu=self.VT)

		# Huỷ đợt A NGAY BÂY GIỜ (ngay=hôm nay), tức SAU den_cu (-30 ngày) —
		# tồn lô L1 lúc này = 100+50-30 = 120 >= 100, đủ để huỷ không đụng
		# _chan_neu_dao_lam_am_ton.
		a.cancel()

		sau = reports.bao_cao_dot_rows(self.K, tu_cu, den_cu, vat_tu=self.VT)
		self.assertEqual(
			truoc, sau,
			"báo cáo của một kỳ đã đóng phải bất biến trước một lần huỷ xảy ra SAU kỳ đó",
		)
		# Positive control: đúng là đợt A CÓ trong kết quả (không phải cả hai
		# lần đều rỗng một cách vô nghĩa).
		self.assertIn(a.name, {r["dot"] for r in truoc})
		row_a = next(r for r in truoc if r["dot"] == a.name)
		self.assertEqual(row_a["sl_nhap"], 100)
		self.assertEqual(row_a["da_xuat"], 30)
		self.assertEqual(row_a["con_lai"], 70)

		# Đối chứng: báo cáo CHẠY HÔM NAY (den=today, phủ luôn ngày huỷ) PHẢI
		# loại đợt A và dồn toàn bộ pool xuất còn lại cho đợt B — chứng minh
		# việc "bất biến với kỳ cũ" ở trên không phải vì code lỡ bỏ qua luôn
		# việc trừ phần đã đảo.
		hien_tai = reports.bao_cao_dot_rows(self.K, d(-90), today, vat_tu=self.VT)
		dots_hien_tai = {r["dot"] for r in hien_tai}
		self.assertNotIn(a.name, dots_hien_tai)
		self.assertEqual(len(hien_tai), 1)
		self.assertEqual(hien_tai[0]["da_xuat"], 30)
		self.assertEqual(hien_tai[0]["con_lai"], 20)

	def test_endpoint_rejects_vat_tu_of_another_customer(self):
		frappe.set_user(BM_USER)
		try:
			with self.assertRaises(frappe.PermissionError):
				kho_api.kho_bao_cao_dot("2026-01-01", "2026-12-31", vat_tu=self.kho["vt_pxn"])
		finally:
			frappe.set_user("Administrator")


# ---------------------------------------------------------------------------
# DoD epic: NCC / nhật ký / báo cáo đợt chỉ truy cập qua get_portal_kho() —
# cách ly hai khách cho hai endpoint mới của phần B.
# ---------------------------------------------------------------------------


class TestPhanBIsolation(_KhoBmTestCase):
	"""M-2 (review E4 phần B): `_KhoBmTestCase.setUp()` chỉ dọn sổ/tồn của kho
	BM — hai test dưới đây seed CẢ kho PXN rồi khẳng định `kho_bao_cao_dot()`
	của KH-B (PXN) chỉ chứa vật tư CỦA CHÍNH PXN
	(`all(r["vat_tu"] == self.kho["vt_pxn"] ...)`), một khẳng định TUYỆT ĐỐI
	sẽ đỏ oan nếu kho PXN còn rác từ lần chạy trước trong cùng site — dọn
	thêm PXN ở đây, đúng khuôn dọn kho BM của lớp cha."""

	def setUp(self):
		super().setUp()
		frappe.db.delete("Customer Stock Ledger Entry", {"kho": self.kho["kho_pxn"]})
		frappe.db.delete("Customer Stock Lot Balance", {"kho": self.kho["kho_pxn"]})

	def test_customer_b_never_sees_customer_a_batches_in_bao_cao_dot(self):
		"""Positive+negative kết hợp: seed CẢ HAI khách, khẳng định báo cáo
		của KH-B (không lọc vat_tu) không hề chứa đợt của KH-A."""
		r_a = _nhap(self.K, self.VT, 10, 1000, "2026-08-01", so_lo="L1")
		_nhap(self.kho["kho_pxn"], self.kho["vt_pxn"], 20, 1000, "2026-08-01", so_lo="L1")

		frappe.set_user(PXN_USER)
		try:
			rows = kho_api.kho_bao_cao_dot("2026-01-01", "2026-12-31")
		finally:
			frappe.set_user("Administrator")
		self.assertTrue(rows, "positive control: KH-B phải thấy đúng đợt của chính mình")
		self.assertNotIn(r_a.name, {r["dot"] for r in rows})
		self.assertTrue(all(r["vat_tu"] == self.kho["vt_pxn"] for r in rows))

	def test_customer_b_cannot_read_customer_a_item_journal(self):
		frappe.set_user(PXN_USER)
		try:
			with self.assertRaises(frappe.PermissionError):
				kho_api.kho_nhat_ky(self.VT, "2026-01-01", "2026-12-31")
		finally:
			frappe.set_user("Administrator")
