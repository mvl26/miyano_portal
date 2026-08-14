"""E5 — US-E5.5: ba Script Report Desk.

- Mở rộng "Chất lượng dữ liệu kho khách" (đã có từ E3 phần B) với hai khía
  cạnh mới (`kho_khong_hoat_dong`/`thieu_chung_tu`, NL-9.3) — item thiếu
  lô/hạn (US-E3.6, hành vi CŨ) đã có test riêng ở test_e3_giao_dien.py,
  KHÔNG lặp lại ở đây.
- "Tiêu thụ và đề xuất dự trù" (mới).
- "Tỷ trọng nguồn cung" (mới, TC-E5-06).

Cả ba: role Sales Manager/Sales User, TUYỆT ĐỐI không Customer — kiểm bằng
`frappe.desk.query_report.run()` (cổng thật), không gọi thẳng hàm dữ liệu,
đúng khuôn TestE3DeskReportPermissions.
"""

import frappe
import frappe.desk.query_report
from frappe.tests.utils import FrappeTestCase

from miyano_portal.kho import desk_reports
from miyano_portal.setup.install_kho_desk_reports import install_kho_desk_reports
from miyano_portal.setup.seed_kho_demo import seed_kho_demo

BM_USER = "bvbm@demo.miyano"
PXN_USER = "pxnabc@demo.miyano"
SALES_USER = "sales_user@demo.miyano"

REPORT_CHAT_LUONG = "Chất lượng dữ liệu kho khách"
REPORT_TIEU_THU = "Tiêu thụ và đề xuất dự trù"
REPORT_TY_TRONG = "Tỷ trọng nguồn cung"


def _today():
	return frappe.utils.getdate(frappe.utils.today())


def _iso(d):
	return frappe.utils.getdate(d).strftime("%Y-%m-%d")


def _nhap(kho, vat_tu, so_luong, ngay, don_gia=1000, so_lo="LO-A", han=None, loai_nhap="Nhập khác", **extra):
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


def _ensure_sales_user() -> str:
	"""Cùng khuôn `test_e3_giao_dien._ensure_sales_user()` — PHẢI ensure role
	kể cả khi user đã tồn tại (một module test khác trong CÙNG site có thể
	đã tạo user này mà chưa gán role)."""
	if not frappe.db.exists("User", SALES_USER):
		frappe.get_doc({
			"doctype": "User", "email": SALES_USER, "first_name": "Sales", "last_name": "User",
			"user_type": "System User", "send_welcome_email": 0,
		}).insert(ignore_permissions=True)
	user = frappe.get_doc("User", SALES_USER)
	if not any(r.role == "Sales User" for r in user.roles):
		user.append("roles", {"role": "Sales User"})
		user.save(ignore_permissions=True)
	return SALES_USER


def _execute(report_name: str, filters: dict | None = None):
	"""Gọi `execute()` ĐÚNG đường Frappe tự gọi (import ĐỘNG bằng chuỗi qua
	`frappe.get_attr`) — cùng khuôn `test_e3_giao_dien._execute()`."""
	slug = frappe.scrub(report_name)
	fn = frappe.get_attr(f"miyano_portal.miyano_portal.report.{slug}.{slug}.execute")
	return fn(frappe._dict(filters or {}))


def _ncc(kho, ten_ncc="NCC-X"):
	existing = frappe.db.get_value("Customer Supplier", {"kho": kho, "ten_ncc": ten_ncc}, "name")
	if existing:
		return existing
	doc = frappe.get_doc({
		"doctype": "Customer Supplier", "kho": kho, "ten_ncc": ten_ncc,
	})
	doc.insert(ignore_permissions=True)
	return doc.name


class _KhoBmTestCase(FrappeTestCase):
	def setUp(self):
		self.kho = seed_kho_demo()
		self.K = self.kho["kho_bm"]
		self.VT = self.kho["vt_bm"]
		frappe.db.delete("Customer Stock Ledger Entry", {"kho": self.K})
		frappe.db.delete("Customer Stock Lot Balance", {"kho": self.K})
		for parent in frappe.get_all("Customer Stock Receipt", filters={"kho": self.K}, pluck="name"):
			frappe.db.delete("Customer Stock Receipt Item", {"parent": parent})
		frappe.db.delete("Customer Stock Receipt", {"kho": self.K})
		for parent in frappe.get_all("Customer Stock Issue", filters={"kho": self.K}, pluck="name"):
			frappe.db.delete("Customer Stock Issue Item", {"parent": parent})
		frappe.db.delete("Customer Stock Issue", {"kho": self.K})
		frappe.db.set_value("Customer Warehouse Item", self.VT, {
			"ton_toi_thieu": 0, "diem_dat_lai": 0, "ton_toi_da": 0,
			"lead_time_ngay": 3, "boi_so_dat": 0,
		})

	def tearDown(self):
		frappe.set_user("Administrator")


# ==================================================== "Kho không hoạt động"

class TestKhoKhongHoatDong(_KhoBmTestCase):
	def test_kho_khong_co_phieu_xuat_nao_xuat_hien(self):
		rows = desk_reports.chat_luong_du_lieu_rows(loai_van_de="kho_khong_hoat_dong")
		row = next((r for r in rows if r["kho"] == self.K), None)
		self.assertIsNotNone(row, "kho chưa từng xuất phải xuất hiện trong danh sách")
		self.assertIsNone(row["ngay_xuat_gan_nhat"])
		self.assertIsNone(row["so_ngay_khong_xuat"])

	def test_kho_moi_xuat_gan_day_khong_xuat_hien(self):
		_nhap(self.K, self.VT, 100, frappe.utils.add_days(_today(), -10))
		_xuat(self.K, self.VT, 5, frappe.utils.add_days(_today(), -1))
		rows = desk_reports.chat_luong_du_lieu_rows(loai_van_de="kho_khong_hoat_dong")
		self.assertFalse(any(r["kho"] == self.K for r in rows), "vừa xuất hôm qua thì không phải kho chết")

	def test_kho_xuat_lau_roi_xuat_hien_dung_so_ngay(self):
		nguong = 200  # đủ lớn để chắc chắn > _nguong_cham_luan_chuyen() mặc định (90)
		_nhap(self.K, self.VT, 100, frappe.utils.add_days(_today(), -(nguong + 20)))
		_xuat(self.K, self.VT, 5, frappe.utils.add_days(_today(), -(nguong + 10)))
		rows = desk_reports.chat_luong_du_lieu_rows(loai_van_de="kho_khong_hoat_dong")
		row = next(r for r in rows if r["kho"] == self.K)
		self.assertEqual(row["so_ngay_khong_xuat"], nguong + 10)

	def test_dispatcher_mac_dinh_khong_doi_hanh_vi_cu(self):
		"""Không truyền `loai_van_de` phải KHÔNG bao giờ trả dòng có khoá
		"kho"/"so_ngay_khong_xuat" — vẫn là nhánh item thiếu lô/hạn cũ."""
		rows = desk_reports.chat_luong_du_lieu_rows()
		self.assertTrue(all("so_ngay_khong_xuat" not in r for r in rows))

	def test_so_ngay_override_qua_dispatcher_va_qua_execute(self):
		"""Review E5 round 2 — `so_ngay` giờ phơi được ra ô lọc thật (`.js`)
		và `execute()` chuyển tiếp đúng; test qua CẢ hai đường: gọi thẳng
		dispatcher VÀ qua `execute()` (đường Frappe thật sự gọi khi mở report)."""
		_nhap(self.K, self.VT, 100, frappe.utils.add_days(_today(), -50))
		_xuat(self.K, self.VT, 5, frappe.utils.add_days(_today(), -40))  # 40 ngày không xuất

		# Ngưỡng mặc định (90) -> chưa đủ 40 ngày để coi là "chết".
		rows_mac_dinh = desk_reports.chat_luong_du_lieu_rows(loai_van_de="kho_khong_hoat_dong")
		self.assertFalse(any(r["kho"] == self.K for r in rows_mac_dinh))

		# Override so_ngay=30 -> 40 ngày không xuất đã vượt ngưỡng.
		rows_override = desk_reports.chat_luong_du_lieu_rows(loai_van_de="kho_khong_hoat_dong", so_ngay=30)
		self.assertTrue(any(r["kho"] == self.K for r in rows_override))

		_cols, data = _execute(REPORT_CHAT_LUONG, {"loai_van_de": "Kho không hoạt động", "so_ngay": 30})
		self.assertTrue(any(r["kho"] == self.K for r in data), "execute() phải chuyển tiếp so_ngay xuống dispatcher")


# ========================================================== "Thiếu chứng từ"

class TestThieuChungTu(_KhoBmTestCase):
	def test_phieu_mua_ngoai_thieu_chung_tu_xuat_hien(self):
		ncc = _ncc(self.K)
		doc = _nhap(self.K, self.VT, 50, _today(), loai_nhap="Mua ngoài (NCC khác)", ncc=ncc)
		self.assertEqual(doc.thieu_chung_tu, 1)

		rows = desk_reports.chat_luong_du_lieu_rows(loai_van_de="thieu_chung_tu")
		row = next((r for r in rows if r["phieu_nhap"] == doc.name), None)
		self.assertIsNotNone(row)
		self.assertEqual(row["ncc"], "NCC-X")

	def test_phieu_co_du_chung_tu_khong_xuat_hien(self):
		ncc = _ncc(self.K)
		doc = _nhap(
			self.K, self.VT, 50, _today(), loai_nhap="Mua ngoài (NCC khác)", ncc=ncc,
			so_chung_tu_ncc="HD-001",
		)
		self.assertEqual(doc.thieu_chung_tu, 0)
		rows = desk_reports.chat_luong_du_lieu_rows(loai_van_de="thieu_chung_tu")
		self.assertFalse(any(r["phieu_nhap"] == doc.name for r in rows))

	def test_phieu_nhap_khac_khong_bao_gio_thieu_chung_tu(self):
		"""loai_nhap != "Mua ngoài" -> thieu_chung_tu luôn 0, không liên quan
		tới khái niệm "chứng từ NCC" chút nào."""
		doc = _nhap(self.K, self.VT, 50, _today())  # loai_nhap mặc định "Nhập khác"
		self.assertEqual(doc.thieu_chung_tu, 0)
		rows = desk_reports.chat_luong_du_lieu_rows(loai_van_de="thieu_chung_tu")
		self.assertFalse(any(r["phieu_nhap"] == doc.name for r in rows))

	def test_phieu_da_huy_khong_con_xuat_hien(self):
		ncc = _ncc(self.K)
		doc = _nhap(self.K, self.VT, 50, _today(), loai_nhap="Mua ngoài (NCC khác)", ncc=ncc)
		doc.reload()
		doc.cancel()
		rows = desk_reports.chat_luong_du_lieu_rows(loai_van_de="thieu_chung_tu")
		self.assertFalse(any(r["phieu_nhap"] == doc.name for r in rows), "phiếu đã huỷ không còn 'thiếu' gì nữa")


# ================================================== "Tiêu thụ & đề xuất dự trù"

class TestTieuThuDeXuat(_KhoBmTestCase):
	def test_smoke_tra_dung_so_lieu_co_ban(self):
		today = _today()
		_nhap(self.K, self.VT, 1000, frappe.utils.add_days(today, -100))
		_xuat(self.K, self.VT, 450, frappe.utils.add_days(today, -50))
		frappe.db.set_value("Customer Warehouse Item", self.VT, {
			"ton_toi_thieu": 10, "diem_dat_lai": 25, "ton_toi_da": 60, "boi_so_dat": 10,
		})

		rows = desk_reports.tieu_thu_de_xuat_rows(customer="Bệnh viện Bạch Mai")
		row = next(r for r in rows if r["vat_tu"] == self.VT)
		self.assertEqual(row["ton"], 550)
		self.assertEqual(row["rop"], 25)
		self.assertEqual(row["max"], 60)
		self.assertEqual(row["customer"], "Bệnh viện Bạch Mai")

	def test_khong_bo_qua_vat_tu_it_du_lieu_khac_voi_man_canh_bao_khach_hang(self):
		"""KHÁC với kho_canh_bao_ton() (BR-P3 ẩn vật tư ít dữ liệu khỏi màn
		khách hàng), report NỘI BỘ này phải liệt kê MỌI vật tư đang dùng —
		sales cần thấy cả vật tư mới để lên kế hoạch."""
		today = _today()
		_nhap(self.K, self.VT, 100, frappe.utils.add_days(today, -5))
		_xuat(self.K, self.VT, 10, frappe.utils.add_days(today, -2))  # < 30 ngày dữ liệu, min/rop chưa khai

		rows = desk_reports.tieu_thu_de_xuat_rows(customer="Bệnh viện Bạch Mai")
		self.assertTrue(any(r["vat_tu"] == self.VT for r in rows))

	def test_cach_ly_khach_khac_khong_lo_sang(self):
		today = _today()
		kho_pxn = self.kho["kho_pxn"]
		vt_pxn = self.kho["vt_pxn"]
		frappe.db.delete("Customer Stock Ledger Entry", {"kho": kho_pxn})
		frappe.db.delete("Customer Stock Lot Balance", {"kho": kho_pxn})
		_nhap(kho_pxn, vt_pxn, 100, frappe.utils.add_days(today, -40))
		_xuat(kho_pxn, vt_pxn, 10, frappe.utils.add_days(today, -35))

		rows = desk_reports.tieu_thu_de_xuat_rows(customer="Bệnh viện Bạch Mai")
		self.assertFalse(any(r["vat_tu"] == vt_pxn for r in rows))


# ======================================================= "Tỷ trọng nguồn cung"

class TestTyTrongNguonCung(_KhoBmTestCase):
	def test_tc_e5_06_ty_trong_70_30_loai_tru_dao(self):
		today = _today()
		ncc_x = _ncc(self.K, "NCC-X")

		# Miyano: 700 đơn vị x 100.000 = 70.000.000.
		_nhap(self.K, self.VT, 700, today, don_gia=100000, so_lo="LO-MYN")
		# NCC-X: 300 đơn vị x 100.000 = 30.000.000.
		_nhap(self.K, self.VT, 300, today, don_gia=100000, so_lo="LO-NCC", loai_nhap="Mua ngoài (NCC khác)", ncc=ncc_x)

		# Một phiếu THỨ BA (Mua ngoài NCC-X, 500 đơn vị) bị HUỶ ngay — phải
		# loại trừ HOÀN TOÀN khỏi tỷ trọng (DoD: "loại trừ phiếu đảo").
		dao = _nhap(self.K, self.VT, 500, today, don_gia=100000, so_lo="LO-DAO", loai_nhap="Mua ngoài (NCC khác)", ncc=ncc_x)
		dao.reload()
		dao.cancel()

		rows = desk_reports.ty_trong_nguon_cung_rows(customer="Bệnh viện Bạch Mai")
		theo_nguon = {r["nguon"]: r for r in rows}
		self.assertEqual(theo_nguon["Miyano"]["gia_tri_nhap"], 70_000_000)
		self.assertEqual(theo_nguon["NCC-X"]["gia_tri_nhap"], 30_000_000)
		self.assertEqual(theo_nguon["Miyano"]["ty_trong_pct"], 70.0)
		self.assertEqual(theo_nguon["NCC-X"]["ty_trong_pct"], 30.0)
		self.assertEqual(theo_nguon["Miyano"]["sl_nhap"], 700)
		self.assertEqual(theo_nguon["NCC-X"]["sl_nhap"], 300)

		# TC-E5-06 (P1 #6, báo cáo kiểm thử hệ thống): CÙNG bộ số qua ĐÚNG
		# cổng report thật — frappe.desk.query_report.run() -> execute() ->
		# dispatcher, dưới phiên Sales User (không Administrator), filter
		# `customer` đi qua `filters.get("customer")` của execute() thay vì
		# tham số Python tiêm tay ở trên. test_sales_user_chay_duoc_ba_report
		# chỉ assertIn("result", result) — luôn đúng kể cả report rỗng; đây
		# là assertion SỐ đầu tiên đi qua đúng đường đó, nên một lỗi suy diễn
		# tenant ở execute()/dispatcher sẽ làm nó đỏ.
		install_kho_desk_reports()
		frappe.set_user(_ensure_sales_user())
		try:
			ket_qua = frappe.desk.query_report.run(
				REPORT_TY_TRONG, filters={"customer": "Bệnh viện Bạch Mai"},
			)
		finally:
			frappe.set_user("Administrator")
		theo_nguon_qua_report = {r["nguon"]: r for r in ket_qua["result"]}
		self.assertEqual(theo_nguon_qua_report["Miyano"]["gia_tri_nhap"], 70_000_000)
		self.assertEqual(theo_nguon_qua_report["NCC-X"]["gia_tri_nhap"], 30_000_000)
		self.assertEqual(theo_nguon_qua_report["Miyano"]["ty_trong_pct"], 70.0)
		self.assertEqual(theo_nguon_qua_report["NCC-X"]["ty_trong_pct"], 30.0)

	def test_loc_theo_ky_tu_ngay_den_ngay(self):
		today = _today()
		_nhap(self.K, self.VT, 100, frappe.utils.add_days(today, -100), don_gia=1000)
		_nhap(self.K, self.VT, 50, frappe.utils.add_days(today, -5), don_gia=1000)

		rows = desk_reports.ty_trong_nguon_cung_rows(
			customer="Bệnh viện Bạch Mai",
			tu_ngay=frappe.utils.add_days(today, -10), den_ngay=today,
		)
		theo_nguon = {r["nguon"]: r for r in rows}
		self.assertEqual(theo_nguon["Miyano"]["sl_nhap"], 50, "chỉ tính phiếu trong kỳ")

	def test_i4_chi_dien_tu_ngay_van_loc_khong_tra_ve_toan_bo_lich_su(self):
		"""I-4 (review E5 round 2) — sales gõ "Từ ngày = 10 ngày trước", để
		trống "Đến ngày" (rất tự nhiên: "từ đó tới nay"). Trước bản sửa,
		điều kiện `if tu_ngay and den_ngay` bỏ lọc HOÀN TOÀN khi chỉ một đầu
		được điền — report trả về TOÀN BỘ lịch sử (kể cả phiếu 100 ngày
		trước), không một dấu hiệu nào cho biết bộ lọc đã bị bỏ qua."""
		today = _today()
		_nhap(self.K, self.VT, 100, frappe.utils.add_days(today, -100), don_gia=1000)
		_nhap(self.K, self.VT, 50, frappe.utils.add_days(today, -5), don_gia=1000)

		rows = desk_reports.ty_trong_nguon_cung_rows(
			customer="Bệnh viện Bạch Mai", tu_ngay=frappe.utils.add_days(today, -10),
		)
		theo_nguon = {r["nguon"]: r for r in rows}
		self.assertEqual(
			theo_nguon["Miyano"]["sl_nhap"], 50,
			"chỉ 'từ ngày' vẫn phải lọc bỏ phiếu 100 ngày trước, không trả toàn bộ lịch sử",
		)

	def test_i4_chi_dien_den_ngay_van_loc(self):
		today = _today()
		_nhap(self.K, self.VT, 100, frappe.utils.add_days(today, -100), don_gia=1000)
		_nhap(self.K, self.VT, 50, frappe.utils.add_days(today, -5), don_gia=1000)

		rows = desk_reports.ty_trong_nguon_cung_rows(
			customer="Bệnh viện Bạch Mai", den_ngay=frappe.utils.add_days(today, -50),
		)
		theo_nguon = {r["nguon"]: r for r in rows}
		self.assertEqual(
			theo_nguon["Miyano"]["sl_nhap"], 100,
			"chỉ 'đến ngày' phải loại phiếu 5 ngày trước (sau mốc đến ngày)",
		)

	def test_cach_ly_khach_khac(self):
		today = _today()
		kho_pxn = self.kho["kho_pxn"]
		vt_pxn = self.kho["vt_pxn"]
		frappe.db.delete("Customer Stock Ledger Entry", {"kho": kho_pxn})
		frappe.db.delete("Customer Stock Lot Balance", {"kho": kho_pxn})
		_nhap(kho_pxn, vt_pxn, 20, today, don_gia=5000)

		rows = desk_reports.ty_trong_nguon_cung_rows(customer="Bệnh viện Bạch Mai")
		self.assertFalse(any(r["customer"] == "PXN ABC" for r in rows))


# ================================================================= An ninh

class TestE5DeskReportPermissions(FrappeTestCase):
	"""Cùng khuôn TestE3DeskReportPermissions — cổng thật:
	`frappe.desk.query_report.run()`."""

	def setUp(self):
		seed_kho_demo()
		_ensure_sales_user()
		install_kho_desk_reports()

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_customer_khong_chay_duoc_ba_report(self):
		frappe.set_user(BM_USER)
		for name in (REPORT_CHAT_LUONG, REPORT_TIEU_THU, REPORT_TY_TRONG):
			with self.assertRaises(frappe.PermissionError, msg=f"report: {name}"):
				frappe.desk.query_report.run(name, filters={})

	def test_sales_user_chay_duoc_ba_report(self):
		frappe.set_user(SALES_USER)
		for name in (REPORT_CHAT_LUONG, REPORT_TIEU_THU, REPORT_TY_TRONG):
			result = frappe.desk.query_report.run(name, filters={})
			self.assertIn("result", result, msg=f"report: {name}")

	def test_execute_qua_url_report_chat_luong_kho_khong_hoat_dong(self):
		"""`execute()` phải dịch đúng nhãn tiếng Việt từ ô chọn (.js) sang mã
		nội bộ TRƯỚC khi gọi desk_reports — kiểm qua đường thật, không gọi
		thẳng desk_reports.chat_luong_du_lieu_rows()."""
		columns, _data = _execute(REPORT_CHAT_LUONG, {"loai_van_de": "Kho không hoạt động"})
		fieldnames = {c["fieldname"] for c in columns}
		self.assertIn("so_ngay_khong_xuat", fieldnames)

	def test_execute_qua_url_report_chat_luong_mac_dinh(self):
		columns, _data = _execute(REPORT_CHAT_LUONG, {})
		fieldnames = {c["fieldname"] for c in columns}
		self.assertIn("has_batch_no", fieldnames, "không chọn khía cạnh -> vẫn là item thiếu lô/hạn")
