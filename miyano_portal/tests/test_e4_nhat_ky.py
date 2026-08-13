"""E4 phần B — nhật ký vật tư, NXT theo đợt (FIFO), nhóm "Không có hạn dùng".

Bám 40_TestCases.md TC-E4-07 (nhật ký, đối chiếu kho_ton, dòng đã đảo không bị
giấu), TC-E4-08 (bộ số chuẩn FIFO của PRD E4 §US-E4.7) và TC-E4-09 (cảnh báo
hạn: lô không hạn dùng vào nhóm riêng, VĐ-2).

Ngày dùng trong các test KHÔNG cancel phiếu (TestBaoCaoDotFifo) là ngày TUYỆT
ĐỐI, đúng như bộ số PRD yêu cầu (01/08, 10/08, báo cáo 30/09 -> tuổi tồn 51
ngày là một quan hệ SỐ HỌC cố định, không phải quan hệ với "hôm nay" lúc chạy
test). Các test có cancel phiếu (phiếu đảo luôn mang ngay=frappe.utils.today(),
xem customer_stock_receipt.py/_tao_phieu_dao) thì dùng ngày TƯƠNG ĐỐI so với
frappe.utils.today() — cùng lý do "date rot" đã ghi trong test_kho_reports.py.
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
		result = reports.nhat_ky_rows(self.K, self.VT, d(-60), today, trang=1)
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
		tong_hien_tai = hien_tai.get(self.VT, 0.0)
		self.assertEqual(result["dong"][-1]["ton_sau"], tong_hien_tai)

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

		rows = reports.bao_cao_dot_rows(self.K, "2026-01-01", "2026-09-30", vat_tu=self.VT)
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
		"""Brief: ngưỡng <= 0 = "không áp ngưỡng" — kể cả khi tuổi tồn rất lớn."""
		frappe.db.set_single_value("Miyano Portal Settings", "nguong_cham_luan_chuyen_ngay", 0)
		_nhap(self.K, self.VT, 10, 1000, "2026-01-01", so_lo="L-CU")
		rows = reports.bao_cao_dot_rows(self.K, "2026-01-01", "2026-12-31", vat_tu=self.VT)
		self.assertTrue(rows)
		self.assertFalse(any(r["cham_luan_chuyen"] for r in rows))

	def test_endpoint_reaches_own_data(self):
		_nhap(self.K, self.VT, 10, 1000, "2026-08-01", so_lo="L1")
		frappe.set_user(BM_USER)
		try:
			rows = kho_api.kho_bao_cao_dot("2026-01-01", "2026-09-30")
		finally:
			frappe.set_user("Administrator")
		self.assertTrue(any(r["vat_tu"] == self.VT for r in rows))


class TestBaoCaoDotPhieuDao(_KhoBmTestCase):
	"""NL-8.2: đợt có phiếu bị đảo -> SL nhập của đợt trừ phần đã đảo. Vì huỷ
	luôn đảo TOÀN BỘ một phiếu nhập (không có huỷ một phần), "trừ phần đã đảo"
	tương đương với việc đợt đó biến mất khỏi báo cáo — không phải hiện ra với
	SL nhập = 0."""

	def test_cancelled_receipt_is_excluded_and_its_reversal_is_not_a_batch(self):
		r1 = _nhap(self.K, self.VT, 40, 1000, "2026-03-01", so_lo="LO-X")
		r2 = _nhap(self.K, self.VT, 25, 1000, "2026-03-05", so_lo="LO-X")
		r2.cancel()

		rows = reports.bao_cao_dot_rows(self.K, "2026-01-01", "2026-04-01", vat_tu=self.VT)
		dots = {r["dot"] for r in rows}
		self.assertIn(r1.name, dots)
		self.assertNotIn(
			r2.name, dots,
			"đợt đã bị huỷ hoàn toàn không được đếm là hàng còn trong báo cáo (NL-8.2)",
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
