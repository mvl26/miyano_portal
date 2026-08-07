"""Phase 6 — ba Query/Script Report phía desk cho nhân viên Miyano:
"Tồn kho khách hàng", "Nhập-Xuất-Tồn khách hàng", "Cảnh báo hạn dùng khách
hàng". Xem docs/superpowers/specs/2026-08-06-kho-khach-hang-design.md §4.6,
§6 và .superpowers/sdd/2026-08-06-kho-khach-hang-phase-1/p6-desk-report.md.

Ba lớp test:
  * TestKhoDeskTonKhoReport / TestKhoDeskNXTReport / TestKhoDeskCanhBaoHan —
    đúng số liệu, tách đúng theo khách hàng (KHÔNG gộp), khớp chéo với hàm/
    API portal đã có (single source of truth).
  * TestKhoDeskReportExecuteDefaults — filter mặc định của từng report khi
    chạy qua đúng đường Frappe dùng (`frappe.get_attr(...).execute`).
  * TestKhoDeskReportPermissions — cổng ĐÚNG chỗ thật: `frappe.desk.
    query_report.run()`, không gọi thẳng execute() — đó là hàm kiểm quyền,
    không phải hàm tính số.

FrappeTestCase chỉ rollback cuối CLASS chứ không phải cuối từng test method
(bài học lặp lại nhiều lần trong module này) — sổ/tồn của kho BM và PXN bị dọn
ở setUp mỗi class, đúng khuôn `_KhoBmTestCase` trong test_kho_reports.py.
"""

import frappe
import frappe.desk.query_report
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import kho as kho_api
from miyano_portal.kho import desk_reports
from miyano_portal.setup.install_kho_desk_reports import install_kho_desk_reports
from miyano_portal.setup.seed_kho_demo import seed_kho_demo

BM_USER = "bvbm@demo.miyano"
PXN_USER = "pxnabc@demo.miyano"
SALES_USER = "sales_user@demo.miyano"

REPORT_TON = "Tồn kho khách hàng"
REPORT_NXT = "Nhập-Xuất-Tồn khách hàng"
REPORT_HAN = "Cảnh báo hạn dùng khách hàng"
ALL_REPORTS = (REPORT_TON, REPORT_NXT, REPORT_HAN)


def _today():
	return frappe.utils.getdate(frappe.utils.today())


def _iso(d):
	return frappe.utils.getdate(d).strftime("%Y-%m-%d")


def _nhap(kho, vat_tu, so_luong, don_gia, ngay, so_lo="LO-A", han="2030-01-01"):
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


def _ensure_vat_tu(kho: str, ma_vat_tu: str, ten_vat_tu: str, dvt: str = "Hộp") -> str:
	"""Tạo thêm một Customer Warehouse Item VỚI MÃ TỰ CHỌN trong một kho cụ
	thể — dùng để dựng kịch bản hai khách hàng TRÙNG mã vật tư của riêng họ
	(mỗi kho unique `ma_vat_tu` độc lập, xem thiết kế §3.2)."""
	existing = frappe.db.get_value(
		"Customer Warehouse Item", {"kho": kho, "ma_vat_tu": ma_vat_tu}, "name"
	)
	if existing:
		return existing
	doc = frappe.get_doc({
		"doctype": "Customer Warehouse Item",
		"kho": kho, "ma_vat_tu": ma_vat_tu, "ten_vat_tu": ten_vat_tu, "dvt": dvt,
	})
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_sales_user() -> str:
	"""Nhân viên Miyano CHỈ có role Sales User (không System Manager) — để
	test phân quyền chứng minh đúng role được cấp trong đặc tả, không phải
	'bất kỳ ai có quyền desk nào cũng chạy được' (System Manager gần như luôn
	đúng, không phải bằng chứng của việc giới hạn role)."""
	if not frappe.db.exists("User", SALES_USER):
		frappe.get_doc({
			"doctype": "User",
			"email": SALES_USER,
			"first_name": "Sales",
			"last_name": "User",
			"user_type": "System User",
			"send_welcome_email": 0,
			"roles": [{"role": "Sales User"}],
		}).insert(ignore_permissions=True)
	return SALES_USER


def _execute(report_name: str, filters: dict | None = None):
	"""Gọi report ĐÚNG đường Frappe tự gọi (`Report.execute_module` →
	`frappe.get_attr(<module dotted path>).execute`), không import thẳng bằng
	tay — nếu quy ước đặt tên thư mục/':scrub()' lệch, test này lộ ra ngay
	thay vì một bản import viết tay lỡ trỏ đúng chỗ khác."""
	slug = frappe.scrub(report_name)
	fn = frappe.get_attr(f"miyano_portal.miyano_portal.report.{slug}.{slug}.execute")
	return fn(frappe._dict(filters or {}))


class _KhoDeskTestCase(FrappeTestCase):
	"""Base: seed hai khách (BM, PXN) + dọn sạch sổ/tồn của CẢ HAI trước mỗi
	test — báo cáo desk cộng dồn trên toàn site, một dòng rác từ test trước
	sẽ âm thầm cộng vào tổng của test sau (đúng bài học của _KhoBmTestCase)."""

	def setUp(self):
		self.kho = seed_kho_demo()
		self.K = self.kho["kho_bm"]
		self.VT = self.kho["vt_bm"]
		self.K2 = self.kho["kho_pxn"]
		self.VT2 = self.kho["vt_pxn"]
		self.CUST = frappe.db.get_value("Customer Warehouse", self.K, "customer")
		self.CUST2 = frappe.db.get_value("Customer Warehouse", self.K2, "customer")
		for k in (self.K, self.K2):
			frappe.db.delete("Customer Stock Ledger Entry", {"kho": k})
			frappe.db.delete("Customer Stock Lot Balance", {"kho": k})


class TestKhoDeskTonKhoReport(_KhoDeskTestCase):
	def test_figures_match_ton_hien_tai_rows_for_the_customer(self):
		today = _today()
		_nhap(self.K, self.VT, 40, 15000, frappe.utils.add_days(today, -5), so_lo="LO-A")
		_nhap(self.K, self.VT, 10, 20000, frappe.utils.add_days(today, -3), so_lo="LO-B",
			  han=frappe.utils.add_days(today, 10))

		rows = desk_reports.ton_kho_khach_hang_rows(customer=self.CUST)
		row = next(r for r in rows if r["vat_tu"] == self.VT)

		self.assertEqual(row["customer"], self.CUST)
		self.assertEqual(row["kho"], self.K)
		self.assertEqual(row["so_luong"], 50)
		self.assertEqual(row["gia_tri"], 40 * 15000 + 10 * 20000)
		self.assertEqual(row["so_lo_count"], 2)
		self.assertEqual(row["han_gan_nhat"], frappe.utils.add_days(today, 10))

	def test_two_customers_with_colliding_item_code_are_not_merged(self):
		"""Cả hai khách tự đặt mã vật tư TRÙNG NHAU ('GANG-TRUNG-MA') — nếu
		báo cáo lỡ gộp theo `ma_vat_tu` thay vì docname `vat_tu`, tồn của hai
		khách sẽ cộng vào MỘT dòng và bài test này bắt được ngay."""
		vt_bm = _ensure_vat_tu(self.K, "GANG-TRUNG-MA", "Găng tay (mã trùng, BM)")
		vt_pxn = _ensure_vat_tu(self.K2, "GANG-TRUNG-MA", "Găng tay (mã trùng, PXN)")
		today = _today()
		_nhap(self.K, vt_bm, 30, 10000, frappe.utils.add_days(today, -1))
		_nhap(self.K2, vt_pxn, 999, 5000, frappe.utils.add_days(today, -1))

		rows = [r for r in desk_reports.ton_kho_khach_hang_rows() if r["ma_vat_tu"] == "GANG-TRUNG-MA"]
		self.assertEqual(len(rows), 2, "hai khách trùng mã vật tư phải ra HAI dòng riêng, không phải một")

		row_bm = next(r for r in rows if r["kho"] == self.K)
		row_pxn = next(r for r in rows if r["kho"] == self.K2)
		self.assertEqual(row_bm["so_luong"], 30)
		self.assertEqual(row_pxn["so_luong"], 999, "tồn của PXN không được lẫn vào dòng của BM")
		self.assertNotEqual(row_bm["customer"], row_pxn["customer"])

	def test_filter_by_customer_excludes_other_customer(self):
		today = _today()
		_nhap(self.K, self.VT, 5, 1000, frappe.utils.add_days(today, -1))
		_nhap(self.K2, self.VT2, 7, 2000, frappe.utils.add_days(today, -1))

		rows = desk_reports.ton_kho_khach_hang_rows(customer=self.CUST)
		self.assertTrue(all(r["kho"] == self.K for r in rows))
		self.assertFalse(any(r["vat_tu"] == self.VT2 for r in rows))

	def test_filter_by_item_text_matches_code_or_name(self):
		today = _today()
		_nhap(self.K, self.VT, 5, 1000, frappe.utils.add_days(today, -1))
		rows = desk_reports.ton_kho_khach_hang_rows(item="Găng")
		self.assertTrue(any(r["vat_tu"] == self.VT for r in rows))
		rows_none = desk_reports.ton_kho_khach_hang_rows(item="khong-co-gi-khop-ca")
		self.assertEqual(rows_none, [])

	def test_expiring_within_n_days_filter_excludes_far_future_lot(self):
		today = _today()
		_nhap(self.K, self.VT, 5, 1000, frappe.utils.add_days(today, -10),
			  so_lo="LO-GAN", han=frappe.utils.add_days(today, 5))
		vt2 = _ensure_vat_tu(self.K, "VT-XA-HAN", "Vật tư hạn xa")
		_nhap(self.K, vt2, 5, 1000, frappe.utils.add_days(today, -10),
			  so_lo="LO-XA", han=frappe.utils.add_days(today, 200))

		rows = desk_reports.ton_kho_khach_hang_rows(customer=self.CUST,
													 sap_het_han_trong_ngay=30)
		vat_tu_ids = {r["vat_tu"] for r in rows}
		self.assertIn(self.VT, vat_tu_ids)
		self.assertNotIn(vt2, vat_tu_ids, "vật tư hạn xa 200 ngày phải bị loại khi lọc trong 30 ngày")

	def test_zero_stock_item_excluded(self):
		today = _today()
		_nhap(self.K, self.VT, 5, 1000, frappe.utils.add_days(today, -5))
		_xuat(self.K, self.VT, 5, frappe.utils.add_days(today, -1))
		rows = desk_reports.ton_kho_khach_hang_rows(customer=self.CUST)
		self.assertFalse(any(r["vat_tu"] == self.VT for r in rows))

	def test_matches_portal_kho_ton_for_same_customer(self):
		"""Đối chiếu với chính API portal (`kho_ton`, gọi lại CÙNG
		`reports.ton_hien_tai_rows()`) — hai đường phải khớp tuyệt đối, đúng lý
		do tồn tại của phép refactor rút hàm dùng chung."""
		today = _today()
		_nhap(self.K, self.VT, 12, 30000, frappe.utils.add_days(today, -2))

		frappe.set_user(BM_USER)
		try:
			portal_rows = kho_api.kho_ton()
		finally:
			frappe.set_user("Administrator")

		desk_rows = desk_reports.ton_kho_khach_hang_rows(customer=self.CUST)
		portal_row = next(r for r in portal_rows if r["vat_tu"] == self.VT)
		desk_row = next(r for r in desk_rows if r["vat_tu"] == self.VT)
		for key in ("so_luong", "gia_tri", "so_lo_count", "han_gan_nhat", "ma_vat_tu", "ten_vat_tu", "dvt"):
			self.assertEqual(desk_row[key], portal_row[key], msg=f"lệch ở trường {key}")


class TestKhoDeskNXTReport(_KhoDeskTestCase):
	def test_matches_portal_kho_bao_cao_nxt_for_same_customer_and_period(self):
		"""Đối chiếu chéo BẮT BUỘC theo đặc tả: desk report và endpoint portal
		`kho_bao_cao_nxt` PHẢI khớp từng con số cho cùng khách/cùng kỳ, vì cả
		hai đều gọi lại `reports.nxt_item_rows()` — không được lệch."""
		today = _today()
		tu_ngay = frappe.utils.add_days(today, -20)
		den_ngay = frappe.utils.add_days(today, 5)
		_nhap(self.K, self.VT, 50, 40000, frappe.utils.add_days(today, -30))
		_nhap(self.K, self.VT, 100, 50000, frappe.utils.add_days(today, -15))
		_xuat(self.K, self.VT, 30, frappe.utils.add_days(today, -10))

		frappe.set_user(BM_USER)
		try:
			portal = kho_api.kho_bao_cao_nxt(tu_ngay=_iso(tu_ngay), den_ngay=_iso(den_ngay))
		finally:
			frappe.set_user("Administrator")
		portal_row = next(r for r in portal["rows"] if r["vat_tu"] == self.VT)

		desk_rows = desk_reports.nxt_khach_hang_rows(
			customer=self.CUST, tu_ngay=tu_ngay, den_ngay=den_ngay
		)
		desk_row = next(r for r in desk_rows if r["vat_tu"] == self.VT)

		for key in ("ton_dau_sl", "ton_dau_tt", "nhap_sl", "nhap_tt",
					"xuat_sl", "xuat_tt", "ton_cuoi_sl", "ton_cuoi_tt"):
			self.assertEqual(desk_row[key], portal_row[key], msg=f"lệch ở trường {key}")

	def test_two_customers_movements_in_same_period_not_merged(self):
		today = _today()
		tu_ngay = frappe.utils.add_days(today, -10)
		den_ngay = frappe.utils.add_days(today, 5)
		_nhap(self.K, self.VT, 20, 10000, frappe.utils.add_days(today, -3))
		_nhap(self.K2, self.VT2, 999, 7000, frappe.utils.add_days(today, -3))

		rows = desk_reports.nxt_khach_hang_rows(tu_ngay=tu_ngay, den_ngay=den_ngay)
		row_bm = next(r for r in rows if r["vat_tu"] == self.VT)
		row_pxn = next(r for r in rows if r["vat_tu"] == self.VT2)
		self.assertEqual(row_bm["nhap_sl"], 20)
		self.assertEqual(row_pxn["nhap_sl"], 999, "nhập của PXN không được cộng lẫn vào dòng của BM")
		self.assertNotEqual(row_bm["kho"], row_pxn["kho"])

	def test_blank_customer_filter_returns_all_customers(self):
		today = _today()
		tu_ngay = frappe.utils.add_days(today, -5)
		den_ngay = frappe.utils.add_days(today, 5)
		_nhap(self.K, self.VT, 5, 1000, frappe.utils.add_days(today, -1))
		_nhap(self.K2, self.VT2, 5, 1000, frappe.utils.add_days(today, -1))

		rows = desk_reports.nxt_khach_hang_rows(tu_ngay=tu_ngay, den_ngay=den_ngay)
		vat_tu_ids = {r["vat_tu"] for r in rows}
		self.assertIn(self.VT, vat_tu_ids)
		self.assertIn(self.VT2, vat_tu_ids)

	def test_from_date_after_to_date_is_rejected(self):
		today = _today()
		with self.assertRaises(frappe.ValidationError):
			desk_reports.nxt_khach_hang_rows(
				customer=self.CUST, tu_ngay=today,
				den_ngay=frappe.utils.add_days(today, -1),
			)


class TestKhoDeskCanhBaoHan(_KhoDeskTestCase):
	def test_separates_expired_from_expiring_and_orders_nearest_first_across_customers(self):
		today = _today()
		_nhap(self.K, self.VT, 5, 1000, frappe.utils.add_days(today, -30),
			  so_lo="LO-HET-HAN-BM", han=frappe.utils.add_days(today, -8))
		_nhap(self.K2, self.VT2, 7, 2000, frappe.utils.add_days(today, -30),
			  so_lo="LO-HET-HAN-PXN", han=frappe.utils.add_days(today, -3))
		_nhap(self.K, self.VT, 9, 3000, frappe.utils.add_days(today, -20),
			  so_lo="LO-SAP-HET-BM", han=frappe.utils.add_days(today, 10))

		rows = desk_reports.canh_bao_han_khach_hang_rows(so_ngay=90)
		lo_thay = [r["so_lo"] for r in rows]
		for lo in ("LO-HET-HAN-BM", "LO-HET-HAN-PXN", "LO-SAP-HET-BM"):
			self.assertIn(lo, lo_thay)

		# Cả hai lô ĐÃ hết hạn (của HAI khách khác nhau) phải đứng trước lô
		# sắp hết hạn, và trong nhóm đã hết hạn, hết hạn LÂU HƠN (BM, -8 ngày)
		# đứng trước hết hạn GẦN ĐÂY (PXN, -3 ngày) — nearest-first xuyên khách.
		idx_bm_het = lo_thay.index("LO-HET-HAN-BM")
		idx_pxn_het = lo_thay.index("LO-HET-HAN-PXN")
		idx_sap_het = lo_thay.index("LO-SAP-HET-BM")
		self.assertLess(idx_bm_het, idx_pxn_het)
		self.assertLess(idx_pxn_het, idx_sap_het)

		het_han_bm = next(r for r in rows if r["so_lo"] == "LO-HET-HAN-BM")
		sap_het = next(r for r in rows if r["so_lo"] == "LO-SAP-HET-BM")
		self.assertEqual(het_han_bm["trang_thai"], "Đã hết hạn")
		self.assertEqual(sap_het["trang_thai"], "Sắp hết hạn")

	def test_two_customers_not_merged_even_with_same_lot_code(self):
		today = _today()
		_nhap(self.K, self.VT, 11, 1000, frappe.utils.add_days(today, -5),
			  so_lo="LO-CHUNG-MA", han=frappe.utils.add_days(today, 20))
		_nhap(self.K2, self.VT2, 22, 2000, frappe.utils.add_days(today, -5),
			  so_lo="LO-CHUNG-MA", han=frappe.utils.add_days(today, 20))

		rows = [r for r in desk_reports.canh_bao_han_khach_hang_rows(so_ngay=90)
				if r["so_lo"] == "LO-CHUNG-MA"]
		self.assertEqual(len(rows), 2)
		row_bm = next(r for r in rows if r["kho"] == self.K)
		row_pxn = next(r for r in rows if r["kho"] == self.K2)
		self.assertEqual(row_bm["so_luong"], 11)
		self.assertEqual(row_pxn["so_luong"], 22)

	def test_filter_by_customer(self):
		today = _today()
		_nhap(self.K, self.VT, 5, 1000, frappe.utils.add_days(today, -5),
			  han=frappe.utils.add_days(today, 10))
		_nhap(self.K2, self.VT2, 5, 1000, frappe.utils.add_days(today, -5),
			  han=frappe.utils.add_days(today, 10))
		rows = desk_reports.canh_bao_han_khach_hang_rows(customer=self.CUST, so_ngay=90)
		self.assertTrue(all(r["kho"] == self.K for r in rows))


class TestKhoDeskReportExecuteDefaults(_KhoDeskTestCase):
	"""Ba report .py chạy qua ĐÚNG đường Frappe gọi (get_attr trên module
	trên đĩa), không phải qua desk_reports.py trực tiếp — khoá luôn quy ước
	đặt tên thư mục theo `frappe.scrub(report_name)`."""

	def test_ton_kho_report_executes_and_returns_columns_and_data(self):
		today = _today()
		_nhap(self.K, self.VT, 3, 1000, frappe.utils.add_days(today, -1))
		columns, data = _execute(REPORT_TON, {})
		fieldnames = {c["fieldname"] for c in columns}
		for expect in ("customer_name", "ten_kho", "ma_vat_tu", "ten_vat_tu",
					   "dvt", "so_luong", "gia_tri", "so_lo_count", "han_gan_nhat"):
			self.assertIn(expect, fieldnames)
		self.assertTrue(any(r["vat_tu"] == self.VT for r in data))

	def test_nxt_report_defaults_to_current_month_when_no_dates_given(self):
		"""Chốt ĐÚNG biên tháng, không chỉ 'có dữ liệu hôm nay là được': một
		phiếu nhập vào NGÀY ĐẦU THÁNG hiện tại phải rơi vào "nhập" (trong kỳ),
		còn một phiếu nhập vào NGÀY CUỐI THÁNG TRƯỚC (ngay trước đó một ngày)
		phải rơi vào "tồn đầu" (ngoài kỳ) — phân biệt được với một default sai
		kiểu 'chỉ hôm nay' hay 'toàn bộ lịch sử', cả hai đều vẫn cho thấy phát
		sinh hôm nay nếu chỉ kiểm tra sự có mặt của dữ liệu."""
		today = frappe.utils.getdate(frappe.utils.today())
		month_start = frappe.utils.get_first_day(today)
		before_month_start = frappe.utils.add_days(month_start, -1)

		_nhap(self.K, self.VT, 4, 2000, month_start, so_lo="LO-DAU-THANG")
		_nhap(self.K, self.VT, 9, 3000, before_month_start, so_lo="LO-TRUOC-THANG")

		columns, data = _execute(REPORT_NXT, {"customer": self.CUST})
		row = next(r for r in data if r["vat_tu"] == self.VT)
		self.assertEqual(row["nhap_sl"], 4, "phiếu ngày đầu tháng phải tính vào NHẬP của kỳ mặc định")
		self.assertEqual(row["ton_dau_sl"], 9, "phiếu ngày cuối tháng trước phải tính vào TỒN ĐẦU, không phải NHẬP")

	def test_canh_bao_report_defaults_so_ngay_90(self):
		today = _today()
		_nhap(self.K, self.VT, 5, 1000, frappe.utils.add_days(today, -1),
			  han=frappe.utils.add_days(today, 60))
		vt_xa = _ensure_vat_tu(self.K, "VT-XA-HAN-2", "Vật tư hạn xa 2")
		_nhap(self.K, vt_xa, 5, 1000, frappe.utils.add_days(today, -1),
			  han=frappe.utils.add_days(today, 200))

		columns, data = _execute(REPORT_HAN, {"customer": self.CUST})
		vat_tu_ids = {r["vat_tu"] for r in data}
		self.assertIn(self.VT, vat_tu_ids)
		self.assertNotIn(vt_xa, vat_tu_ids, "mặc định so_ngay=90 phải loại lô hạn 200 ngày")


class TestKhoDeskReportPermissions(_KhoDeskTestCase):
	"""Cổng thật: `frappe.desk.query_report.run()` — nơi thật sự kiểm
	`report.is_permitted()` VÀ `frappe.has_permission(ref_doctype, "report")`.
	Gọi thẳng execute()/desk_reports.* không chứng minh được gì về phân quyền."""

	def setUp(self):
		super().setUp()
		_ensure_sales_user()
		install_kho_desk_reports()

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_portal_user_cannot_run_any_of_the_three_reports(self):
		frappe.set_user(BM_USER)
		for name in ALL_REPORTS:
			with self.assertRaises(frappe.PermissionError, msg=f"report: {name}"):
				frappe.desk.query_report.run(name, filters={})

	def test_sales_user_can_run_all_three_reports(self):
		frappe.set_user(SALES_USER)
		for name in ALL_REPORTS:
			result = frappe.desk.query_report.run(name, filters={})
			self.assertIn("result", result, msg=f"report: {name}")
			self.assertIsInstance(result["result"], list, msg=f"report: {name}")
