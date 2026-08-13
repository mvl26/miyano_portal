"""E3 phần B — giao diện đợt giao (US-E3.4, TC-E3-06) và hai Desk report
(US-E3.5 "Đối soát giao nhận", US-E3.6 "Chất lượng dữ liệu kho khách").

Xem `.superpowers/sdd/e3/brief-B-giao-dien-va-bao-cao.md`,
`docs/Miyano-Portal(Client)_V2/DevHandoff/12_PRD_E3_GiaoNhieuDot_DoiSoat.md`,
`30_API_Spec.md` §1.2, `40_TestCases.md` TC-E3-06.

KHÔNG có bài test nào ở đây cho ô "Lý do chênh lệch" trên
`PhieuNhapDetail.vue` (hạng mục "VIỆC ƯU TIÊN SỐ MỘT" của brief) — repo
không có bộ test frontend (`frontend/package.json` chỉ có script `build`,
không có vitest/jest). Backend nhận `ly_do_chenh_lech` qua
`kho_phieu_nhap_save` đã có test ở `test_e3_doi_soat.py`
(`test_TC_E3_03_qua_api_khong_lam_mat_sl_giao_khi_sua`) TRƯỚC KHI phần B này
động vào Vue — phần B chỉ nối lại đường UI đã thiếu tới field đó. Đối chiếu
bằng mắt: `payload()` giờ gửi field này, template có ô nhập chỉ hiện khi
lệch, `yarn build` xanh (xem báo cáo bàn giao).

(I4/M5, vòng review sau) Tên hai report ĐÃ ĐỔI — bỏ hẳn en-dash "–" khỏi tên
thứ nhất (rủi ro `frappe.modules.scrub()` chỉ map đúng en-dash, ai gõ nhầm
gạch nối thường sẽ ra ba gạch dưới liền nhau → ModuleNotFoundError + report
mở lên không có ô lọc, không lần ngược được) và tên thứ hai không còn chung
chung "Chất lượng dữ liệu" (Report docname duy nhất TOÀN SITE). Vẫn giữ
nguyên tắc "không bao giờ `import` tĩnh module report" bên dưới cho chắc,
dù tên mới không còn ký tự đặc biệt — Frappe luôn gọi các report .py bằng
`frappe.get_attr()`/`importlib` (import ĐỘNG bằng chuỗi) qua đúng module
path suy ra từ `scrub(report_name)`, không phải cú pháp `import` tĩnh.
"""

import frappe
import frappe.desk.query_report
from frappe.tests.utils import FrappeTestCase

from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

from miyano_portal.api import portal as portal_api
from miyano_portal.kho import desk_reports
from miyano_portal.setup.install_kho_desk_reports import install_kho_desk_reports
from miyano_portal.setup.seed_kho_demo import seed_kho_demo

COMPANY = "Miyano Việt Nam"
KHO_MYN = "Kho Miyano - MYN"
COST_CENTER = "Main - MYN"
KHACH_BM = "Bệnh viện Bạch Mai"
KHACH_PXN = "PXN ABC"
ITEM = "MYN-GLOVE-M"  # không batch/hạn — sinh thieu_lo_han=1 (US-E3.6)

BM_USER = "bvbm@demo.miyano"
PXN_USER = "pxnabc@demo.miyano"
SALES_USER = "sales_user@demo.miyano"

REPORT_DOI_SOAT = "Đối soát giao nhận"
REPORT_CHAT_LUONG = "Chất lượng dữ liệu kho khách"


def _ensure_sales_user() -> str:
	"""M2 (E3 phần B review): PHẢI ensure role kể cả khi user đã tồn tại —
	`test_e3_doi_soat.py` (cùng module `test_e3_*`, chạy trong CÙNG site
	trước bản sửa này) tạo đúng email `SALES_USER` này nhưng KHÔNG gán role
	nào (chỉ cần user tồn tại để làm `account_manager` nhận notification).
	Nếu hàm này chỉ gán role trong nhánh "vừa tạo mới", một site/thứ tự chạy
	mà user đã tồn tại từ trước (kể cả do rollback per-CLASS không dọn hết,
	hay một phiên bản test runner khác) sẽ khiến `TestE3DeskReportPermissions`
	đỏ theo cách rất khó lần ra: PermissionError trên user tưởng đã có
	quyền."""
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
	`frappe.get_attr`, khớp `Report.execute_module`) — không phải
	`desk_reports.*_rows()` trực tiếp. `execute()` là nơi filter thô từ URL
	(chuỗi "0"/"1", có thể vắng mặt) được ép kiểu TRƯỚC khi tới hàm dữ liệu;
	gọi thẳng hàm dữ liệu (như các test khác trong file này) bỏ qua đúng
	bước đó."""
	slug = frappe.scrub(report_name)
	fn = frappe.get_attr(f"miyano_portal.miyano_portal.report.{slug}.{slug}.execute")
	return fn(frappe._dict(filters or {}))


class _KhoDnTestCase(FrappeTestCase):
	"""Hạ tầng dùng chung: seed hai kho demo, dọn sạch phiếu/sổ của CẢ HAI
	trước mỗi test (FrappeTestCase rollback một lần mỗi CLASS — phiếu rác từ
	test trước sẽ âm thầm lọt vào báo cáo "quét toàn site" của test sau nếu
	không dọn, đúng bài học `_KhoDeskTestCase` của test_kho_desk_reports.py)."""

	def setUp(self):
		self.kho = seed_kho_demo()
		self.kho_bm = self.kho["kho_bm"]
		self.kho_pxn = self.kho["kho_pxn"]
		for kho in (self.kho_bm, self.kho_pxn):
			frappe.db.set_value(
				"Customer Warehouse", kho, {"active": 1, "ngay_bat_dau": "2026-01-01"},
			)
			for parent in frappe.get_all("Customer Stock Receipt", filters={"kho": kho}, pluck="name"):
				frappe.db.delete("Customer Stock Receipt Item", {"parent": parent})
			frappe.db.delete("Customer Stock Receipt", {"kho": kho})
			frappe.db.delete("Customer Stock Ledger Entry", {"kho": kho})
			frappe.db.delete("Customer Stock Lot Balance", {"kho": kho})
		self._nap_ton(ITEM, 1000)

	def tearDown(self):
		frappe.set_user("Administrator")

	# ------------------------------------------------------------------ setup
	def _nap_ton(self, item_code, qty):
		make_stock_entry(
			item_code=item_code, qty=qty, to_warehouse=KHO_MYN, rate=1000,
			company=COMPANY, purpose="Material Receipt",
		)

	def _sales_order(self, customer=KHACH_BM, qty=10, rate=95000):
		so = frappe.new_doc("Sales Order")
		so.customer = customer
		so.company = COMPANY
		so.transaction_date = frappe.utils.today()
		so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 2)
		so.append("items", {
			"item_code": ITEM, "qty": qty, "rate": rate,
			"warehouse": KHO_MYN, "delivery_date": frappe.utils.add_days(frappe.utils.today(), 2),
		})
		so.insert(ignore_permissions=True)
		so.submit()
		return so

	def _dn_tu_so(self, so, qty):
		dn = make_delivery_note(so.name)
		dn.posting_date = frappe.utils.today()
		dn.set_posting_time = 1
		for r in dn.items:
			r.qty = qty
			r.warehouse = KHO_MYN
			r.cost_center = COST_CENTER
		dn.insert(ignore_permissions=True)
		dn.submit()
		return dn

	def _phieu_duy_nhat(self, dn):
		names = frappe.get_all(
			"Customer Stock Receipt",
			filters={"delivery_note": dn.name, "docstatus": ["<", 2]},
			pluck="name",
		)
		self.assertEqual(len(names), 1, f"Kỳ vọng đúng 1 phiếu cho {dn.name}, có {names}")
		return frappe.get_doc("Customer Stock Receipt", names[0])


# ============================================================= US-E3.4 / TC-E3-06
class TestPortalOrderTrackDotGiao(_KhoDnTestCase):
	def test_TC_E3_06_hai_dot_du_thong_tin_dung_ty_le_dung_trang_thai_phieu(self):
		"""AC US-E3.4: 2 DN trên cùng SO → deliveries[] đủ 2 phần tử, đúng %
		từng đợt, `so_dot` khớp thứ tự, `phieu_nhap.trang_thai` phân biệt
		"Nháp" (chưa đối chiếu) và "Đã ghi sổ" (đã ghi sổ, không lệch)."""
		so = self._sales_order(qty=20)
		dn1 = self._dn_tu_so(so, 12)  # 60%
		dn2 = self._dn_tu_so(so, 8)   # 40%

		phieu1 = self._phieu_duy_nhat(dn1)  # để nguyên nháp — chưa đối chiếu
		phieu2 = self._phieu_duy_nhat(dn2)
		phieu2.submit()  # so_luong mặc định = sl_giao → không chênh lệch

		frappe.set_user(BM_USER)
		data = portal_api.portal_order_track(so.name)

		self.assertEqual(len(data["deliveries"]), 2, "phải có đủ 2 đợt giao")
		d1, d2 = data["deliveries"]

		self.assertEqual(d1["name"], dn1.name)
		self.assertEqual(d1["percent"], 60)
		self.assertEqual(d1["so_dot"], 1)
		self.assertIn("phieu_nhap", d1, "khách có kho phải thấy khối phiếu nhập")
		self.assertEqual(d1["phieu_nhap"], {
			"name": phieu1.name, "trang_thai": "Nháp", "co_chenh_lech": False,
		})

		self.assertEqual(d2["name"], dn2.name)
		self.assertEqual(d2["percent"], 40)
		self.assertEqual(d2["so_dot"], 2)
		self.assertEqual(d2["phieu_nhap"], {
			"name": phieu2.name, "trang_thai": "Đã ghi sổ", "co_chenh_lech": False,
		})

		# `30_API_Spec` §1.2 đặt tên field là `dot_giao[]`, không phải
		# `deliveries` — response phải có CẢ HAI (xem ghi chú trong
		# portal_order_track: hai key riêng dựng từ cùng một vòng lặp).
		self.assertEqual(len(data["dot_giao"]), 2)
		g1, g2 = data["dot_giao"]
		self.assertEqual(g1, {
			"so_dot": 1, "delivery_note": dn1.name, "ngay": dn1.posting_date,
			"phan_tram": 60, "van_chuyen": "", "awb": "",
			"phieu_nhap": {"name": phieu1.name, "trang_thai": "Nháp", "co_chenh_lech": False},
		})
		self.assertEqual(g2, {
			"so_dot": 2, "delivery_note": dn2.name, "ngay": dn2.posting_date,
			"phan_tram": 40, "van_chuyen": "", "awb": "",
			"phieu_nhap": {"name": phieu2.name, "trang_thai": "Đã ghi sổ", "co_chenh_lech": False},
		})

	def test_TC_E3_06_chenh_lech_hien_canh_bao_thay_the_da_ghi_so(self):
		"""`co_chenh_lech=1` phải ĐÈ nhãn "Đã ghi sổ" thành "Có chênh lệch ⚠"
		— đây là tín hiệu khách cần thấy ngay, không phải một chi tiết phụ."""
		so = self._sales_order(qty=50)
		dn = self._dn_tu_so(so, 50)
		phieu = self._phieu_duy_nhat(dn)
		phieu.items[0].so_luong = 48
		phieu.items[0].ly_do_chenh_lech = "vỡ 2 hộp"
		phieu.save(ignore_permissions=True)
		phieu.submit()

		frappe.set_user(BM_USER)
		data = portal_api.portal_order_track(so.name)

		d = data["deliveries"][0]
		self.assertEqual(d["phieu_nhap"]["trang_thai"], "Có chênh lệch ⚠")
		self.assertTrue(d["phieu_nhap"]["co_chenh_lech"])

	def test_khach_khong_co_kho_thay_dot_giao_nhung_khong_co_khoi_phieu_nhap(self):
		"""Khách chưa mở kho (hoặc kho đang tắt) vẫn phải thấy đủ đợt giao
		(DN + % + hãng/AWB) — chỉ THIẾU khối phiếu nhập, không phải thiếu cả
		đợt giao. Tắt kho PXN TRƯỚC khi tạo DN nên hook `delivery_hook`
		(`_kho_cua_khach`, active=1) cũng bỏ qua im lặng — không phiếu nào
		được sinh ra, đúng thực tế "khách chưa từng mở kho"."""
		frappe.db.set_value("Customer Warehouse", self.kho_pxn, "active", 0)
		so = self._sales_order(customer=KHACH_PXN, qty=10)
		dn = self._dn_tu_so(so, 10)
		self.assertEqual(
			frappe.get_all("Customer Stock Receipt", filters={"delivery_note": dn.name}), [],
			"kho tắt → hook không được tự sinh phiếu",
		)

		frappe.set_user(PXN_USER)
		data = portal_api.portal_order_track(so.name)

		self.assertEqual(len(data["deliveries"]), 1)
		d = data["deliveries"][0]
		self.assertEqual(d["name"], dn.name)
		self.assertNotIn("phieu_nhap", d)
		self.assertNotIn("so_dot", d)

		self.assertEqual(len(data["dot_giao"]), 1)
		g = data["dot_giao"][0]
		self.assertEqual(g["delivery_note"], dn.name)
		self.assertIsNone(g["so_dot"])
		self.assertNotIn("phieu_nhap", g)

	def test_kho_bi_tat_sau_khi_da_co_phieu_cung_an_khoi_phieu_nhap(self):
		"""Quyết định tự đưa ra (Phần B): "khách có kho" dùng ĐÚNG định nghĩa
		`active=1` mà `get_portal_kho()`/`delivery_hook._kho_cua_khach()` đã
		dùng khắp nơi trong app — một kho bị tắt SAU KHI phiếu đã tồn tại vẫn
		bị coi là "không có kho" ở khối này, nhất quán với việc hook cũng
		ngừng tự sinh phiếu mới cho kho đó."""
		so = self._sales_order(qty=10)
		dn = self._dn_tu_so(so, 10)
		self._phieu_duy_nhat(dn)  # tồn tại, cố tình không đụng tới
		frappe.db.set_value("Customer Warehouse", self.kho_bm, "active", 0)

		frappe.set_user(BM_USER)
		data = portal_api.portal_order_track(so.name)

		d = data["deliveries"][0]
		self.assertNotIn("phieu_nhap", d)

	def test_isolation_kho_khach_khac_khong_lo_vao_deliveries(self):
		"""BM và PXN đều có kho — phiếu của PXN cho DN của BM (không thể xảy
		ra qua đường thật, nhưng đây là test cách ly) không được lẫn vào."""
		so = self._sales_order(customer=KHACH_BM, qty=10)
		dn = self._dn_tu_so(so, 10)
		phieu = self._phieu_duy_nhat(dn)

		frappe.set_user(BM_USER)
		data = portal_api.portal_order_track(so.name)
		self.assertEqual(data["deliveries"][0]["phieu_nhap"]["name"], phieu.name)

		# PXN không sở hữu SO này — check_permission phải chặn TRƯỚC khi tới
		# đoạn ghép deliveries.
		frappe.set_user(PXN_USER)
		with self.assertRaises(frappe.PermissionError):
			portal_api.portal_order_track(so.name)


# ============================================================ US-E3.5 (UC-48)
class TestDoiSoatGiaoNhanReport(_KhoDnTestCase):
	def test_khong_chenh_lech_van_liet_ke_dung_moc_doi_soat(self):
		so = self._sales_order(customer=KHACH_BM, qty=10)
		dn = self._dn_tu_so(so, 10)
		phieu = self._phieu_duy_nhat(dn)

		rows = desk_reports.doi_soat_giao_nhan_rows()
		row = next(r for r in rows if r["phieu_nhap"] == phieu.name)

		self.assertEqual(row["delivery_note"], dn.name)
		self.assertEqual(row["sales_order"], so.name)
		self.assertEqual(row["customer"], KHACH_BM)
		self.assertEqual(row["so_dot"], 1)
		self.assertEqual(row["sl_giao"], 10)
		self.assertEqual(row["so_luong"], 10)
		self.assertEqual(row["chenh"], 0)
		self.assertEqual(row["ly_do_chenh_lech"], "")
		self.assertEqual(row["trang_thai_phieu"], "Nháp")

	def test_chi_chenh_lech_loc_dung_dong_va_tinh_dung_chenh(self):
		so = self._sales_order(customer=KHACH_BM, qty=50)
		dn = self._dn_tu_so(so, 50)
		phieu = self._phieu_duy_nhat(dn)
		phieu.items[0].so_luong = 48
		phieu.items[0].ly_do_chenh_lech = "vỡ 2 hộp"
		phieu.save(ignore_permissions=True)
		phieu.submit()

		so2 = self._sales_order(customer=KHACH_PXN, qty=5)
		dn2 = self._dn_tu_so(so2, 5)
		phieu2 = self._phieu_duy_nhat(dn2)
		phieu2.submit()  # không lệch

		tat_ca = desk_reports.doi_soat_giao_nhan_rows()
		self.assertGreaterEqual(len(tat_ca), 2)

		chi_lech = desk_reports.doi_soat_giao_nhan_rows(chi_chenh_lech=True)
		ten_phieu_lech = {r["phieu_nhap"] for r in chi_lech}
		self.assertIn(phieu.name, ten_phieu_lech)
		self.assertNotIn(phieu2.name, ten_phieu_lech)

		row = next(r for r in chi_lech if r["phieu_nhap"] == phieu.name)
		self.assertEqual(row["chenh"], -2)
		self.assertEqual(row["ly_do_chenh_lech"], "vỡ 2 hộp")
		self.assertEqual(row["trang_thai_phieu"], "Đã ghi sổ")

	def test_execute_qua_url_deep_link_chuoi_0_khong_bi_hieu_nham_thanh_bat(self):
		"""`execute()` (không phải `doi_soat_giao_nhan_rows()` gọi thẳng) là
		nơi filter thô từ URL deep-link tới — Frappe gửi Check dạng chuỗi
		("0"/"1"), và "0" là TRUTHY trong Python nếu không `cint()` trước khi
		dùng, tức sẽ bật nhầm bộ lọc dù người dùng để ô Check TẮT."""
		so = self._sales_order(customer=KHACH_BM, qty=10)
		dn = self._dn_tu_so(so, 10)
		phieu = self._phieu_duy_nhat(dn)  # không chênh lệch

		_cols, data = _execute(REPORT_DOI_SOAT, {"chi_chenh_lech": "0"})
		self.assertTrue(
			any(r["phieu_nhap"] == phieu.name for r in data),
			'"0" (chuỗi) từ URL phải nghĩa là TẮT bộ lọc, không phải bật',
		)

	def test_qua_han_ngay_chi_loc_phieu_con_nhap_qua_cu(self):
		"""M1 (E3 phần B review): KHÔNG khẳng định `len(rows_30_ngay) == 1` —
		`doi_soat_giao_nhan_rows()` quét `_active_khos()` là MỌI Customer
		Warehouse TOÀN SITE, không chỉ hai kho `setUp` dọn (kho_bm, kho_pxn).
		Bench này có `demo_kho_flow.py`/dữ liệu demo khác có thể để lại phiếu
		nháp cũ ở MỘT KHO KHÁC không liên quan gì tới test này — đếm tổng số
		dòng là giả định về trạng thái toàn site mà test không kiểm soát
		được. Khẳng định đúng những gì test NÀY tạo ra: phiếu cũ có mặt,
		phiếu mới (không "treo") không có mặt."""
		so = self._sales_order(customer=KHACH_BM, qty=10)
		dn_cu = self._dn_tu_so(so, 4)
		phieu_cu = self._phieu_duy_nhat(dn_cu)
		# Giả một phiếu nháp "treo" 40 ngày — sửa thẳng creation trên DB (phiếu
		# vẫn còn docstatus=0, không đụng tới bất kỳ trạng thái nghiệp vụ nào).
		frappe.db.set_value(
			"Customer Stock Receipt", phieu_cu.name, "creation",
			frappe.utils.add_days(frappe.utils.now_datetime(), -40),
		)

		dn_moi = self._dn_tu_so(so, 3)
		phieu_moi = self._phieu_duy_nhat(dn_moi)  # nháp, mới tạo — không "treo"

		rows_30_ngay = desk_reports.doi_soat_giao_nhan_rows(qua_han_ngay=30)
		phieu_names = {r["phieu_nhap"] for r in rows_30_ngay}
		self.assertIn(phieu_cu.name, phieu_names, "phiếu nháp quá hạn phải lọt qua bộ lọc")
		self.assertNotIn(
			phieu_moi.name, phieu_names,
			"phiếu nháp mới tạo (không treo) không được lọt qua bộ lọc theo N ngày",
		)

	def test_isolation_hai_khach_khong_gop_nham(self):
		so_bm = self._sales_order(customer=KHACH_BM, qty=6)
		dn_bm = self._dn_tu_so(so_bm, 6)
		self._phieu_duy_nhat(dn_bm)

		so_pxn = self._sales_order(customer=KHACH_PXN, qty=7)
		dn_pxn = self._dn_tu_so(so_pxn, 7)
		self._phieu_duy_nhat(dn_pxn)

		rows_bm = desk_reports.doi_soat_giao_nhan_rows(customer=KHACH_BM)
		self.assertTrue(all(r["customer"] == KHACH_BM for r in rows_bm))
		self.assertTrue(any(r["delivery_note"] == dn_bm.name for r in rows_bm))
		self.assertFalse(any(r["delivery_note"] == dn_pxn.name for r in rows_bm))


# ============================================================= US-E3.6 (NL-3.7)
class TestChatLuongDuLieuReport(_KhoDnTestCase):
	def test_item_thieu_batch_len_report_kem_co_hien_tai(self):
		"""ITEM = MYN-GLOVE-M không bật Has Batch No — hook rơi lô về
		KHONG-LO, đánh dấu thieu_lo_han=1 (TC-E3-07, phần A). Report phải gộp
		đúng Item đó, kèm cờ has_batch_no HIỆN TẠI (0, vì chưa ai sửa)."""
		so = self._sales_order(customer=KHACH_BM, qty=10)
		dn = self._dn_tu_so(so, 10)
		phieu = self._phieu_duy_nhat(dn)
		self.assertEqual(phieu.items[0].thieu_lo_han, 1)

		rows = desk_reports.chat_luong_du_lieu_rows()
		row = next(r for r in rows if r["item_code"] == ITEM)
		self.assertEqual(row["so_dong_thieu"], 1)
		self.assertEqual(row["so_khach_anh_huong"], 1)
		self.assertEqual(row["has_batch_no"], 0)
		self.assertEqual(row["has_expiry_date"], 0)

	def test_gop_nhieu_dong_nhieu_khach_dung_so_khach_anh_huong(self):
		so_bm = self._sales_order(customer=KHACH_BM, qty=10)
		self._dn_tu_so(so_bm, 10)
		so_bm2 = self._sales_order(customer=KHACH_BM, qty=5)
		self._dn_tu_so(so_bm2, 5)
		so_pxn = self._sales_order(customer=KHACH_PXN, qty=3)
		self._dn_tu_so(so_pxn, 3)

		rows = desk_reports.chat_luong_du_lieu_rows()
		row = next(r for r in rows if r["item_code"] == ITEM)
		self.assertEqual(row["so_dong_thieu"], 3, "ba dòng phiếu (2 BM + 1 PXN) đều thiếu lô")
		self.assertEqual(row["so_khach_anh_huong"], 2, "gộp theo Item, không đếm trùng khách")

	def test_chi_chua_bat_co_an_item_da_bat_du_hai_co(self):
		"""Đọc đúng nghĩa đen US-E3.6 ("liệt kê item CẦN bật...") — item đã
		được Miyano bật CẢ HAI cờ sau khi phát hiện thì không còn "cần" gì
		nữa, dù dòng `thieu_lo_han` lịch sử vẫn còn thật (không xoá). Mặc
		định (`chi_chua_bat_co=True`, đúng giá trị mặc định của hàm) phải ẩn
		nó; tắt bộ lọc thì vẫn thấy được, kèm đúng cờ hiện tại."""
		so = self._sales_order(customer=KHACH_BM, qty=10)
		dn = self._dn_tu_so(so, 10)
		self._phieu_duy_nhat(dn)

		truoc = frappe.db.get_value(
			"Item", ITEM, ["has_batch_no", "has_expiry_date"], as_dict=True
		)
		frappe.db.set_value("Item", ITEM, {"has_batch_no": 1, "has_expiry_date": 1})
		self.addCleanup(frappe.db.set_value, "Item", ITEM, dict(truoc))

		an_di = desk_reports.chat_luong_du_lieu_rows()
		self.assertFalse(any(r["item_code"] == ITEM for r in an_di))

		van_thay = desk_reports.chat_luong_du_lieu_rows(chi_chua_bat_co=False)
		row = next(r for r in van_thay if r["item_code"] == ITEM)
		self.assertEqual(row["has_batch_no"], 1)
		self.assertEqual(row["has_expiry_date"], 1)

	def test_chi_chua_bat_co_van_hien_khi_moi_bat_mot_trong_hai_co(self):
		"""Thiếu MỘT trong hai cờ vẫn coi là "cần" — `thieu_lo_han` có thể
		tái diễn tới khi cả hai đều bật, không phải chỉ một."""
		so = self._sales_order(customer=KHACH_BM, qty=10)
		dn = self._dn_tu_so(so, 10)
		self._phieu_duy_nhat(dn)

		truoc = frappe.db.get_value(
			"Item", ITEM, ["has_batch_no", "has_expiry_date"], as_dict=True
		)
		frappe.db.set_value("Item", ITEM, {"has_batch_no": 1, "has_expiry_date": 0})
		self.addCleanup(frappe.db.set_value, "Item", ITEM, dict(truoc))

		rows = desk_reports.chat_luong_du_lieu_rows()
		self.assertTrue(any(r["item_code"] == ITEM for r in rows))

	def test_execute_qua_url_deep_link_chuoi_0_tat_dung_bo_loc_mac_dinh(self):
		"""Cùng cái bẫy `"0"` truthy như report 1 — `execute()` phải `cint()`
		giá trị thô từ URL TRƯỚC khi coi nó là bật/tắt."""
		so = self._sales_order(customer=KHACH_BM, qty=10)
		dn = self._dn_tu_so(so, 10)
		self._phieu_duy_nhat(dn)
		truoc = frappe.db.get_value(
			"Item", ITEM, ["has_batch_no", "has_expiry_date"], as_dict=True
		)
		frappe.db.set_value("Item", ITEM, {"has_batch_no": 1, "has_expiry_date": 1})
		self.addCleanup(frappe.db.set_value, "Item", ITEM, dict(truoc))

		_cols, tat = _execute(REPORT_CHAT_LUONG, {"chi_chua_bat_co": "0"})
		self.assertTrue(
			any(r["item_code"] == ITEM for r in tat),
			'"0" (chuỗi) phải TẮT bộ lọc mặc định, không phải giữ nguyên bật',
		)

		_cols2, mac_dinh = _execute(REPORT_CHAT_LUONG, {})
		self.assertFalse(
			any(r["item_code"] == ITEM for r in mac_dinh),
			"không truyền gì → mặc định BẬT, item đã fix phải bị ẩn",
		)


# ==================================================== Script filter (.js) tải được
class TestE3ReportFilterScript(_KhoDnTestCase):
	"""`frappe.desk.query_report.run()` (dùng ở TestE3DeskReportPermissions)
	KHÔNG BAO GIỜ đọc file .js — đó là script filter phía CLIENT, nạp riêng
	qua `query_report.get_script()` khi trang desk mở report. Test phân
	quyền không chứng minh được gì về đường này: nếu `scrub()` ghép sai
	đường dẫn (module path suy từ report_name — nguyên uỷ của test này là
	tên report cũ dùng en-dash, đã đổi ở I4, nhưng chốt giữ nguyên vì đây là
	đường dễ vỡ ÂM THẦM cho bất kỳ report nào đặt tên có ký tự đặc biệt
	trong tương lai), report vẫn CHẠY được (data đúng) nhưng mở lên KHÔNG CÓ
	Ô LỌC NÀO — "lọc được chỉ dòng chênh lệch / phiếu chưa ghi sổ quá N
	ngày" (AC US-E3.5) sẽ có mặt trên giấy nhưng không bấm được trên thực
	tế."""

	def setUp(self):
		super().setUp()
		install_kho_desk_reports()

	def test_ca_hai_report_tai_duoc_script_loc_khong_rong(self):
		"""I2 (E3 phần B review): bản trước chỉ kiểm script "không rỗng" và
		"có chứa tên report" — CẢ HAI đều đúng trên đúng nhánh HỎNG mà test
		này sinh ra để bắt, vì `get_script()` khi không tìm thấy file .js
		trả về đúng một fallback KHÔNG RỖNG và CÓ chứa report_name:
		`"frappe.query_reports['{name}']={{}}"`. Assert đúng thứ CHỈ CÓ
		trong file .js thật (tên field filter) mới thật sự phân biệt được
		hai nhánh."""
		checks = {
			REPORT_DOI_SOAT: "chi_chenh_lech",
			REPORT_CHAT_LUONG: "chi_chua_bat_co",
		}
		for name, dau_hieu in checks.items():
			out = frappe.desk.query_report.get_script(name)
			script = out.get("script") or ""
			self.assertIn(
				dau_hieu, script,
				msg=(
					f"report: {name} — script không phải file .js thật (có thể "
					"đang rơi về fallback rỗng của get_script() khi không tìm "
					"thấy file, fallback đó VẪN chứa report_name nên không dùng "
					"assertIn(name, script) để kiểm được)"
				),
			)


# ================================================================= An ninh
class TestE3DeskReportPermissions(_KhoDnTestCase):
	"""Cổng thật: `frappe.desk.query_report.run()` — kiểm
	`report.is_permitted()` VÀ `frappe.has_permission(ref_doctype, "report")`
	TRƯỚC khi execute() được gọi. Role Customer liệt kê dữ liệu của MỌI
	khách hàng qua hai report này là rò rỉ chéo khách hàng — ràng buộc an
	ninh số một của brief phần B."""

	def setUp(self):
		super().setUp()
		_ensure_sales_user()
		install_kho_desk_reports()

	def test_customer_khong_chay_duoc_ca_hai_report_moi(self):
		frappe.set_user(BM_USER)
		for name in (REPORT_DOI_SOAT, REPORT_CHAT_LUONG):
			with self.assertRaises(frappe.PermissionError, msg=f"report: {name}"):
				frappe.desk.query_report.run(name, filters={})

	def test_sales_user_chay_duoc_ca_hai_report_moi(self):
		frappe.set_user(SALES_USER)
		for name in (REPORT_DOI_SOAT, REPORT_CHAT_LUONG):
			result = frappe.desk.query_report.run(name, filters={})
			self.assertIn("result", result, msg=f"report: {name}")
			self.assertIsInstance(result["result"], list, msg=f"report: {name}")
