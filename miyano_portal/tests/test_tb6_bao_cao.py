"""Task 9 — báo cáo "Vật tư · Máy · Khoa phòng" (`reports.bao_cao_thiet_bi_rows`).

Trái tim của bài toán vật tư/máy/khoa: một vật tư đã nhập bao nhiêu, cấp
phát cho máy nào, khoa nào — và phải TÁCH hai cột xuất (cap_phat/xuat_khac,
xem docstring `bao_cao_thiet_bi_rows` trong `kho/reports.py`), không phải
một cột "Đã xuất" kiểu NXT gộp chung với phần tách theo máy.

Nền dữ liệu (một kho `ZZTB9`):
  * `self.vat_tu` — gắn 3 máy (`may_a/b/c`), xuất cho 2 máy (a, b), máy c
    chưa từng dùng.
  * `self.vat_tu_dao` — 1 phiếu xuất sử dụng bị HUỶ (tạo phiếu đảo) — phải
    lọt qua HAI lớp lọc, không lọt lớp nào.
  * `self.vat_tu_cu` — 1 phiếu xuất sử dụng gắn máy thật + 1 phiếu "cũ"
    không gắn máy (nhóm "Chưa gắn máy") + 1 phiếu "Xuất huỷ - hết hạn"
    (không mang máy theo thiết kế, chỉ vào `xuat_khac`).
  * `self.vt_nuoc_chai`/`self.vt_nuoc_lit` — hai vật tư CÙNG TÊN "Nước cất"
    khác ĐVT, chỉ có nhập — gộp theo tên (thay vì docname) sẽ cộng nhầm.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.kho import desk_reports, reports

KHACH = "ZZTB9 Benh Vien"


class TestBaoCaoThietBi(FrappeTestCase):
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
			"ten_kho": "ZZTB9 Kho", "ma_kho": "ZZTB9",
			"ngay_bat_dau": frappe.utils.add_days(frappe.utils.today(), -60),
		}).insert(ignore_permissions=True).name

		self.tu = "2026-08-01"
		self.den = "2026-08-31"

		self.kp_a = self._khoa("ZZTB9 Khoa A", "ZZTB9A")
		self.kp_b = self._khoa("ZZTB9 Khoa B", "ZZTB9B")
		self.kp_d = self._khoa("ZZTB9 Khoa D", "ZZTB9D")

		self.may_a = self._may("ZZTB9-M1", "Máy A", self.kp_a.name)
		self.may_b = self._may("ZZTB9-M2", "Máy B", self.kp_b.name)
		self.may_c = self._may("ZZTB9-M3", "Máy C (chưa dùng)", None)
		self.may_d = self._may("ZZTB9-M4", "Máy D", self.kp_d.name)

		# --- Vật tư 1: gắn 3 máy tương thích, chỉ xuất cho 2 máy. ------------
		self.vat_tu = frappe.get_doc({
			"doctype": "Customer Warehouse Item", "kho": self.kho,
			"ma_vat_tu": "ZZTB9-VT1", "ten_vat_tu": "Test hoá chất ba máy", "dvt": "Hộp",
			"may_su_dung": [
				{"thiet_bi": self.may_a.name},
				{"thiet_bi": self.may_b.name},
				{"thiet_bi": self.may_c.name},
			],
		}).insert(ignore_permissions=True)
		self._nhap(self.vat_tu.name, "LO-VT1", 100, 10000)
		self._xuat_su_dung(self.vat_tu.name, "LO-VT1", 20, self.kp_a.name, self.may_a.name)
		self._xuat_su_dung(self.vat_tu.name, "LO-VT1", 15, self.kp_b.name, self.may_b.name)

		# --- Vật tư 2: 1 phiếu xuất sử dụng bị huỷ (phiếu đảo). --------------
		self.vat_tu_dao = frappe.get_doc({
			"doctype": "Customer Warehouse Item", "kho": self.kho,
			"ma_vat_tu": "ZZTB9-VT2", "ten_vat_tu": "Test hoá chất bị đảo", "dvt": "Chai",
		}).insert(ignore_permissions=True)
		self._nhap(self.vat_tu_dao.name, "LO-VT2", 50, 20000)
		doc_se_huy = self._xuat_su_dung(
			self.vat_tu_dao.name, "LO-VT2", 10, self.kp_a.name, self.may_a.name,
		)
		doc_se_huy.cancel()
		dao_name = frappe.db.get_value(
			"Customer Stock Issue", {"phieu_goc": doc_se_huy.name}, "name"
		)
		# Bài học F-2 (review E8, xem test_e8_cap_phat.py): _tao_phieu_dao()
		# luôn đặt `ngay = today()` (ngày HUỶ THẬT), có thể rơi ra ngoài kỳ
		# báo cáo cố định 08/2026 tuỳ ngày chạy CI thật — ép cả phiếu đảo lẫn
		# dòng sổ của nó vào TRONG kỳ để chốt `loai_xuat != "Xuất sử dụng"`
		# (lớp lọc thứ hai) thực sự được test này chạm tới, không phải bị bộ
		# lọc NGÀY loại hộ trước khi kịp chạm chốt đó.
		frappe.db.set_value("Customer Stock Issue", dao_name, "ngay", "2026-08-08")
		frappe.db.set_value(
			"Customer Stock Ledger Entry", {"chung_tu": dao_name}, "ngay", "2026-08-08"
		)

		# --- Vật tư 3: 1 phiếu gắn máy thật + 1 phiếu "cũ" không máy + 1 -----
		# phiếu "Xuất huỷ - hết hạn" (không mang máy theo thiết kế BR-TB-3,
		# chỉ vào xuat_khac).
		self.vat_tu_cu = frappe.get_doc({
			"doctype": "Customer Warehouse Item", "kho": self.kho,
			"ma_vat_tu": "ZZTB9-VT3", "ten_vat_tu": "Test hoá chất cũ", "dvt": "Chai",
		}).insert(ignore_permissions=True)
		self._nhap(self.vat_tu_cu.name, "LO-VT3", 30, 15000)
		self._xuat_su_dung(self.vat_tu_cu.name, "LO-VT3", 5, self.kp_d.name, self.may_d.name)
		self._xuat_su_dung(self.vat_tu_cu.name, "LO-VT3", 3, None, None)
		self._xuat(
			self.vat_tu_cu.name, "LO-VT3", 2, khoa_phong=None, thiet_bi=None,
			loai_xuat="Xuất huỷ - hết hạn",
		)

		# --- Hai vật tư CÙNG TÊN, khác ĐVT — chỉ có nhập. --------------------
		self.vt_nuoc_chai = frappe.get_doc({
			"doctype": "Customer Warehouse Item", "kho": self.kho,
			"ma_vat_tu": "ZZTB9-NC1", "ten_vat_tu": "Nước cất", "dvt": "Chai",
		}).insert(ignore_permissions=True)
		self.vt_nuoc_lit = frappe.get_doc({
			"doctype": "Customer Warehouse Item", "kho": self.kho,
			"ma_vat_tu": "ZZTB9-NC2", "ten_vat_tu": "Nước cất", "dvt": "Lít",
		}).insert(ignore_permissions=True)
		self._nhap(self.vt_nuoc_chai.name, "LO-NC1", 40, 5000)
		self._nhap(self.vt_nuoc_lit.name, "LO-NC2", 40, 5000)

	def tearDown(self):
		frappe.set_user("Administrator")

	# ------------------------------------------------------------------ #
	# Fixture helpers
	# ------------------------------------------------------------------ #

	def _khoa(self, ten, ma):
		return frappe.get_doc({
			"doctype": "Customer Department", "customer": KHACH, "kho": self.kho,
			"ten_khoa_phong": ten, "ma_khoa": ma,
		}).insert(ignore_permissions=True)

	def _may(self, ma, ten, khoa_phong):
		return frappe.get_doc({
			"doctype": "Customer Equipment", "customer": KHACH,
			"ma_thiet_bi": ma, "ten_thiet_bi": ten, "khoa_phong": khoa_phong,
		}).insert(ignore_permissions=True)

	def _nhap(self, vat_tu, so_lo, so_luong, don_gia, ngay="2026-08-01"):
		doc = frappe.get_doc({
			"doctype": "Customer Stock Receipt", "kho": self.kho,
			"ngay": ngay, "loai_nhap": "Nhập khác",
			"items": [{
				"vat_tu": vat_tu, "so_lo": so_lo, "so_luong": so_luong, "don_gia": don_gia,
			}],
		}).insert(ignore_permissions=True)
		doc.submit()
		return doc

	def _xuat(self, vat_tu, so_lo, so_luong, khoa_phong=None, thiet_bi=None,
	          loai_xuat="Xuất sử dụng", ngay="2026-08-05", nguoi_nhan="Test"):
		doc = frappe.get_doc({
			"doctype": "Customer Stock Issue", "kho": self.kho,
			"ngay": ngay, "loai_xuat": loai_xuat,
			"khoa_phong": khoa_phong, "nguoi_nhan": nguoi_nhan,
			"items": [{
				"vat_tu": vat_tu, "so_lo": so_lo, "so_luong": so_luong, "thiet_bi": thiet_bi,
			}],
		}).insert(ignore_permissions=True)
		doc.submit()
		return doc

	def _xuat_su_dung(self, vat_tu, so_lo, so_luong, khoa_phong, thiet_bi, ngay="2026-08-05"):
		return self._xuat(
			vat_tu, so_lo, so_luong, khoa_phong=khoa_phong, thiet_bi=thiet_bi,
			loai_xuat="Xuất sử dụng", ngay=ngay,
		)

	def _dong(self, bc, vat_tu_id):
		for d in bc["dong"]:
			if d["vat_tu_id"] == vat_tu_id:
				return d
		self.fail(f"Không thấy dòng báo cáo cho vật tư {vat_tu_id}")

	def _don(self):
		"""Dọn CHỈ dữ liệu của khách hàng ZZTB9 của bộ test này — erptest.local
		là site làm việc thật, mang dữ liệu demo của nhiều bệnh viện và nhiều
		bộ test khác, TUYỆT ĐỐI không xoá không lọc."""
		khos = frappe.get_all(
			"Customer Warehouse", filters={"customer": KHACH}, pluck="name"
		) or [""]
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
			frappe.db.delete(dt, {"customer": KHACH})
		frappe.db.delete("Customer", {"name": KHACH})

	# ------------------------------------------------------------------ #
	# Test cases — nguyên văn task-9-brief.md Step 1
	# ------------------------------------------------------------------ #

	def test_tong_theo_may_bang_cot_cap_phat(self):
		bc = reports.bao_cao_thiet_bi_rows(self.kho, self.tu, self.den)
		dong = self._dong(bc, self.vat_tu.name)
		self.assertAlmostEqual(sum(r["sl"] for r in dong["theo_may"]), dong["cap_phat"])

	def test_khong_cong_trung_khi_vat_tu_dung_nhieu_may(self):
		"""Máy thứ ba khai trong danh mục nhưng chưa xuất lần nào — KHÔNG được
		xuất hiện trong theo_may với số 0 giả."""
		bc = reports.bao_cao_thiet_bi_rows(self.kho, self.tu, self.den)
		dong = self._dong(bc, self.vat_tu.name)
		self.assertEqual(len(dong["theo_may"]), 2)
		self.assertEqual(len(dong["may_tuong_thich"]), 3)

	def test_phieu_dao_khong_lot_ca_hai_lop(self):
		bc = reports.bao_cao_thiet_bi_rows(self.kho, self.tu, self.den)
		dong = self._dong(bc, self.vat_tu_dao.name)
		self.assertEqual(dong["cap_phat"], 0)

	def test_phieu_cu_khong_may_vao_nhom_chua_gan(self):
		bc = reports.bao_cao_thiet_bi_rows(self.kho, self.tu, self.den)
		dong = self._dong(bc, self.vat_tu_cu.name)
		chua = [r for r in dong["theo_may"] if r["thiet_bi"] is None]
		self.assertEqual(len(chua), 1)
		self.assertEqual(chua[0]["ten_may"], "Chưa gắn máy")
		self.assertIs(dong["theo_may"][-1], chua[0])   # LUÔN ở cuối

	def test_hai_vat_tu_cung_ten_khac_dvt_tach_hai_dong(self):
		bc = reports.bao_cao_thiet_bi_rows(self.kho, self.tu, self.den)
		trung = [d for d in bc["dong"] if d["vat_tu"] == "Nước cất"]
		self.assertEqual(len(trung), 2)
		self.assertEqual({d["dvt"] for d in trung}, {"Chai", "Lít"})

	def test_hang_van_can_khi_ky_co_ca_xuat_huy_va_phieu_dao(self):
		"""CA 13 của spec — ca đã suýt bị bỏ sót và là lý do tách hai cột xuất.

		Task 10 (mang từ Task 9 sang): vòng lặp PHẢI dùng `subTest`, không
		thì `assertAlmostEqual` dừng ở dòng vi phạm ĐẦU TIÊN và che khuất mọi
		dòng vi phạm sau — dưới cùng một đột biến có thể có HAI vật tư cùng
		vi phạm mà chỉ một được báo."""
		bc = reports.bao_cao_thiet_bi_rows(self.kho, self.tu, self.den)
		for d in bc["dong"]:
			with self.subTest(vat_tu=d["ma_vat_tu"]):
				self.assertAlmostEqual(
					d["ton_dau"] + d["nhap"] - d["cap_phat"] - d["xuat_khac"], d["ton_cuoi"],
					places=4,
					msg=f"Hàng không cân ở vật tư {d['ma_vat_tu']}",
				)

	def test_may_chuyen_khoa_giua_ky_khong_doi_so_lieu_ky_truoc(self):
		"""Ca 4, spec §11 (đợt sửa cuối, I-1) — QĐ-TB-13: khoa lấy từ PHIẾU,
		không suy theo `Customer Equipment.khoa_phong` tại thời điểm chạy
		báo cáo. Nếu suy theo máy, ngày máy A chuyển từ Khoa A sang Khoa D
		sẽ làm số liệu kỳ báo cáo TRƯỚC ĐÓ (đã đóng, đã in) tự viết lại —
		bản in tháng trước và bản in lại hôm nay ra hai con số khác nhau,
		không ai đối chiếu được. `self.tu`/`self.den` là kỳ CỐ ĐỊNH trong
		quá khứ (08/2026); việc chuyển khoa xảy ra SAU kỳ đó, ở "hiện tại"
		của test."""
		bc_truoc = reports.bao_cao_thiet_bi_rows(self.kho, self.tu, self.den)
		dong_truoc = self._dong(bc_truoc, self.vat_tu.name)
		r_truoc = next(r for r in dong_truoc["theo_may"] if r["thiet_bi"] == self.may_a.name)
		self.assertEqual(r_truoc["khoa_phong"], self.kp_a.name)

		# Máy A chuyển khoa — KHÔNG chạm gì tới phiếu/sổ của kỳ đã đóng.
		self.may_a.khoa_phong = self.kp_d.name
		self.may_a.save(ignore_permissions=True)

		bc_sau = reports.bao_cao_thiet_bi_rows(self.kho, self.tu, self.den)
		dong_sau = self._dong(bc_sau, self.vat_tu.name)
		r_sau = next(r for r in dong_sau["theo_may"] if r["thiet_bi"] == self.may_a.name)

		self.assertEqual(r_sau["khoa_phong"], self.kp_a.name)  # vẫn khoa TRÊN PHIẾU
		self.assertNotEqual(r_sau["khoa_phong"], self.kp_d.name)  # không phải khoa MỚI của máy
		self.assertEqual(r_truoc, r_sau)  # số liệu kỳ trước không đổi

	def test_loc_khoa_phong_theo_khoa_tren_phieu_khong_phai_khoa_cua_may(self):
		"""Hệ quả thứ hai của cùng lỗi: bộ lọc `khoa_phong` phải lọc theo
		khoa GHI TRÊN PHIẾU (nơi hàng được cấp phát tới), không phải khoa
		máy ĐANG đặt. Chuyển máy A sang Khoa D rồi lọc theo Khoa A: dòng
		cấp phát cho máy A (phiếu ghi khoa A) vẫn phải hiện ra, dù máy A
		hiện đã ở khoa D — nhãn màn hình "Khoa phòng" nói cấp phát, không
		phải vị trí máy hiện tại."""
		self.may_a.khoa_phong = self.kp_d.name
		self.may_a.save(ignore_permissions=True)
		bc = reports.bao_cao_thiet_bi_rows(
			self.kho, self.tu, self.den, khoa_phong=self.kp_a.name
		)
		dong = self._dong(bc, self.vat_tu.name)
		self.assertTrue(any(r["thiet_bi"] == self.may_a.name for r in dong["theo_may"]))


# --------------------------------------------------------------- Task 10 ---
# Báo cáo xoay chiều theo máy (`reports.tieu_thu_theo_may_rows`), mở rộng
# `bao_cao_cap_phat_rows` thành ba cấp (khoa -> dòng -> theo_may), và bản
# Desk cho nhân viên Miyano (`desk_reports.tieu_thu_theo_thiet_bi_rows`).
#
# LỆCH so với task-10-brief.md, ghi rõ trong task-10-report.md:
#   * `desk_reports.tieu_thu_theo_thiet_bi_rows` gắn khoá `customer_name`
#     (không phải `ten_khach` như brief gõ) — MỌI hàm khác trong
#     desk_reports.py đều dùng `customer_name` (ton_kho_khach_hang_rows,
#     nxt_khach_hang_rows, canh_bao_han_khach_hang_rows, ...), đặt tên khác
#     đúng một hàm sẽ phá tính nhất quán không lý do.
#   * Hai test "desk" của brief gọi hàm KHÔNG truyền tu_ngay/den_ngay — lệch
#     với MỌI lời gọi desk_reports.*_khach_hang_rows() khác trong cả bộ test
#     (luôn truyền tu_ngay/den_ngay tường minh, xem
#     test_kho_desk_reports.py::test_blank_customer_filter_returns_all_customers)
#     — giữ nguyên quy ước đó ở đây, tránh phát minh ngữ nghĩa "ngày mặc
#     định" mới không nơi nào khác trong module dùng.
#   * `test_desk_khong_loc_thi_gom_nhieu_benh_vien` bản gốc của brief chỉ
#     kiểm `len({...}) >= 1` — luôn đúng miễn có ít nhất một dòng, không bắt
#     được đột biến "âm thầm lọc theo MỘT khách dù customer=None". Thay bằng
#     khẳng định CẢ HAI khách hàng dựng riêng trong fixture đều có mặt, đúng
#     khuôn test_blank_customer_filter_returns_all_customers ở trên.

KHACH_MAY_A = "ZZTB10 Benh Vien A"
KHACH_MAY_B = "ZZTB10 Benh Vien B"


class TestBaoCaoTheoMay(FrappeTestCase):
	# Danh sách CỨNG, cố ý: ba màn SPA và một nút Excel đang đọc đúng các
	# khoá này. Thêm khoá thì sửa danh sách; ĐỔI hoặc XOÁ khoá là hồi quy.
	KHOA_NHOM_CU = {"khoa_phong", "ten_hien_thi", "gia_tri", "pct", "dong"}

	def setUp(self):
		frappe.set_user("Administrator")
		self._don()
		self.addCleanup(self._don)

		for ten in (KHACH_MAY_A, KHACH_MAY_B):
			frappe.get_doc({
				"doctype": "Customer", "customer_name": ten,
				"customer_type": "Company", "customer_group": "All Customer Groups",
				"territory": "All Territories",
			}).insert(ignore_permissions=True)
		self.khach = KHACH_MAY_A
		self.khach2 = KHACH_MAY_B

		self.kho = frappe.get_doc({
			"doctype": "Customer Warehouse", "customer": KHACH_MAY_A,
			"ten_kho": "ZZTB10 Kho A", "ma_kho": "ZZTB10A",
			"ngay_bat_dau": frappe.utils.add_days(frappe.utils.today(), -365),
		}).insert(ignore_permissions=True).name
		self.kho_b = frappe.get_doc({
			"doctype": "Customer Warehouse", "customer": KHACH_MAY_B,
			"ten_kho": "ZZTB10 Kho B", "ma_kho": "ZZTB10B",
			"ngay_bat_dau": frappe.utils.add_days(frappe.utils.today(), -365),
		}).insert(ignore_permissions=True).name

		# Kỳ báo cáo cố định trong quá khứ xa (không phụ thuộc ngày chạy CI)
		# — tránh bẫy `_tao_phieu_dao()` luôn gán `ngay=today()` bằng cách tự
		# ép lại ngày của phiếu đảo/dòng sổ của nó vào TRONG kỳ, giống khuôn
		# test_tb6_bao_cao (Task 9) đã làm.
		self.tu = "2026-01-01"
		self.den = "2026-01-31"

		self.kp_a = frappe.get_doc({
			"doctype": "Customer Department", "customer": KHACH_MAY_A, "kho": self.kho,
			"ten_khoa_phong": "ZZTB10 Khoa A", "ma_khoa": "ZZTB10KA",
		}).insert(ignore_permissions=True)

		# Hai máy CÙNG TÊN, khác docname — ca test bắt buộc của
		# task-10-brief.md để ghim việc gộp theo DOCNAME, không theo tên.
		#
		# QUYẾT ĐỊNH đã chốt (chủ đầu tư, vòng sửa 1 của Task 10, xem
		# task-10-report.md): GIỮ NGUYÊN luật tên máy duy nhất — spec §4.1
		# là thẩm quyền, "hai máy trùng tên là chuyện thường" trong
		# task-10-brief.md là brief SAI, không phải spec sai.
		# `CustomerEquipment._chan_trung_ten()` (Task 1) CHẶN CỨNG hai máy
		# trùng `ten_thiet_bi` trong CÙNG một khách hàng — nghĩa là qua
		# đường tạo mới bình thường, trạng thái dựng ở đây KHÔNG THỂ phát
		# sinh. Đây KHÔNG phải mô phỏng một tình huống thật (không có "di
		# trú"/"import cũ" nào tạo ra được nó — chưa từng có đường nào khác
		# ngoài `ignore_validate`); đây là dựng THẲNG một trạng thái BẤT KHẢ
		# qua đường bình thường, chỉ để ghim logic gộp theo docname vẫn đúng
		# NẾU luật đổi trong tương lai — phòng thủ, không phải hiện trạng.
		self.may_x1 = frappe.get_doc({
			"doctype": "Customer Equipment", "customer": KHACH_MAY_A,
			"ma_thiet_bi": "ZZTB10-MX1", "ten_thiet_bi": "Máy XN-500",
			"khoa_phong": self.kp_a.name,
		}).insert(ignore_permissions=True)
		may_x2_doc = frappe.get_doc({
			"doctype": "Customer Equipment", "customer": KHACH_MAY_A,
			"ma_thiet_bi": "ZZTB10-MX2", "ten_thiet_bi": "Máy XN-500",
			"khoa_phong": self.kp_a.name,
		})
		may_x2_doc.flags.ignore_validate = True
		self.may_x2 = may_x2_doc.insert(ignore_permissions=True)
		self.may_dao = frappe.get_doc({
			"doctype": "Customer Equipment", "customer": KHACH_MAY_A,
			"ma_thiet_bi": "ZZTB10-MD", "ten_thiet_bi": "Máy Đảo Test",
		}).insert(ignore_permissions=True)

		self.vat_tu = frappe.get_doc({
			"doctype": "Customer Warehouse Item", "kho": self.kho,
			"ma_vat_tu": "ZZTB10-VT1", "ten_vat_tu": "Test hoá chất theo máy", "dvt": "Hộp",
		}).insert(ignore_permissions=True)
		self._nhap(self.kho, self.vat_tu.name, "LO-VT1", 100, 10000)
		# Nhập 100 @ đơn giá 10.000 -> đơn giá xuất suy ra cũng 10.000/đv:
		# 10 đv -> gia_tri 100.000; 8 đv -> gia_tri 80.000.
		self._xuat_su_dung(self.kho, self.vat_tu.name, "LO-VT1", 10, self.kp_a.name, self.may_x1.name)
		self._xuat_su_dung(self.kho, self.vat_tu.name, "LO-VT1", 8, self.kp_a.name, self.may_x2.name)

		# --- Vật tư riêng để thử HAI LỚP LỌC khi có phiếu đảo (Điều 2). -----
		# Một phiếu 5 đơn vị GIỮ NGUYÊN, một phiếu 10 đơn vị bị HUỶ. Nếu chỉ
		# lọc da_dao=0 (bỏ dòng GỐC của phiếu 10 đã huỷ) mà KHÔNG lọc thêm
		# loai_xuat=="Xuất sử dụng" (bỏ chính dòng BÙ TRỪ), dòng bù trừ
		# (so_luong dương, mang thiet_bi=may_dao vì Task 3 chép sang) sẽ bị
		# cộng NGƯỢC DẤU vào tổng của may_dao, biến 5 thành -5 — sai rõ ràng,
		# không phải lệch làm tròn.
		self.vat_tu_dao = frappe.get_doc({
			"doctype": "Customer Warehouse Item", "kho": self.kho,
			"ma_vat_tu": "ZZTB10-VT2", "ten_vat_tu": "Test hoá chất bị đảo", "dvt": "Chai",
		}).insert(ignore_permissions=True)
		self._nhap(self.kho, self.vat_tu_dao.name, "LO-VT2", 50, 20000)
		self._xuat_su_dung(self.kho, self.vat_tu_dao.name, "LO-VT2", 5, None, self.may_dao.name)
		se_huy = self._xuat_su_dung(
			self.kho, self.vat_tu_dao.name, "LO-VT2", 10, None, self.may_dao.name,
		)
		se_huy.cancel()
		dao_name = frappe.db.get_value(
			"Customer Stock Issue", {"phieu_goc": se_huy.name}, "name"
		)
		frappe.db.set_value("Customer Stock Issue", dao_name, "ngay", "2026-01-15")
		frappe.db.set_value(
			"Customer Stock Ledger Entry", {"chung_tu": dao_name}, "ngay", "2026-01-15"
		)

		# --- Khách hàng B (bệnh viện khác) — để test lọc theo customer ở ----
		# desk_reports.tieu_thu_theo_thiet_bi_rows().
		self.kp_b = frappe.get_doc({
			"doctype": "Customer Department", "customer": KHACH_MAY_B, "kho": self.kho_b,
			"ten_khoa_phong": "ZZTB10 Khoa B", "ma_khoa": "ZZTB10KB",
		}).insert(ignore_permissions=True)
		self.may_b = frappe.get_doc({
			"doctype": "Customer Equipment", "customer": KHACH_MAY_B,
			"ma_thiet_bi": "ZZTB10-MB1", "ten_thiet_bi": "Máy Siêu âm B",
			"khoa_phong": self.kp_b.name,
		}).insert(ignore_permissions=True)
		self.vat_tu_b = frappe.get_doc({
			"doctype": "Customer Warehouse Item", "kho": self.kho_b,
			"ma_vat_tu": "ZZTB10B-VT1", "ten_vat_tu": "Test hoá chất B", "dvt": "Hộp",
		}).insert(ignore_permissions=True)
		self._nhap(self.kho_b, self.vat_tu_b.name, "LO-B1", 40, 5000)
		self._xuat_su_dung(self.kho_b, self.vat_tu_b.name, "LO-B1", 4, self.kp_b.name, self.may_b.name)

	def tearDown(self):
		frappe.set_user("Administrator")

	# ------------------------------------------------------------------ #
	# Fixture helpers
	# ------------------------------------------------------------------ #

	def _nhap(self, kho, vat_tu, so_lo, so_luong, don_gia, ngay="2026-01-05"):
		doc = frappe.get_doc({
			"doctype": "Customer Stock Receipt", "kho": kho,
			"ngay": ngay, "loai_nhap": "Nhập khác",
			"items": [{
				"vat_tu": vat_tu, "so_lo": so_lo, "so_luong": so_luong, "don_gia": don_gia,
			}],
		}).insert(ignore_permissions=True)
		doc.submit()
		return doc

	def _xuat_su_dung(self, kho, vat_tu, so_lo, so_luong, khoa_phong, thiet_bi, ngay="2026-01-10"):
		doc = frappe.get_doc({
			"doctype": "Customer Stock Issue", "kho": kho,
			"ngay": ngay, "loai_xuat": "Xuất sử dụng",
			"khoa_phong": khoa_phong, "nguoi_nhan": "Test",
			"items": [{
				"vat_tu": vat_tu, "so_lo": so_lo, "so_luong": so_luong, "thiet_bi": thiet_bi,
			}],
		}).insert(ignore_permissions=True)
		doc.submit()
		return doc

	def _don(self):
		"""Dọn CHỈ dữ liệu của hai khách ZZTB10 A/B của bộ test này —
		erptest.local là site làm việc thật, mang dữ liệu demo của nhiều
		bệnh viện và nhiều bộ test khác, TUYỆT ĐỐI không xoá không lọc."""
		for khach in (KHACH_MAY_A, KHACH_MAY_B):
			khos = frappe.get_all(
				"Customer Warehouse", filters={"customer": khach}, pluck="name"
			) or [""]
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
				frappe.db.delete(dt, {"customer": khach})
			frappe.db.delete("Customer", {"name": khach})

	# ------------------------------------------------------------------ #
	# Test cases
	# ------------------------------------------------------------------ #

	def test_cap_phat_giu_nguyen_khoa_cu(self):
		bc = reports.bao_cao_cap_phat_rows(self.kho, self.tu, self.den)
		self.assertTrue(bc["nhom"])
		for nhom in bc["nhom"]:
			self.assertTrue(self.KHOA_NHOM_CU <= set(nhom))

	def test_cap_phat_them_khoa_theo_may(self):
		bc = reports.bao_cao_cap_phat_rows(self.kho, self.tu, self.den)
		self.assertIn("theo_may", bc["nhom"][0])

	def test_theo_may_cong_bang_gia_tri_cua_khoa(self):
		bc = reports.bao_cao_cap_phat_rows(self.kho, self.tu, self.den)
		self.assertTrue(bc["nhom"])
		for nhom in bc["nhom"]:
			with self.subTest(khoa=nhom["ten_hien_thi"]):
				self.assertAlmostEqual(
					sum(m["gia_tri"] for m in nhom["theo_may"]), nhom["gia_tri"], places=2
				)

	def test_theo_may_loc_hai_lop_khi_co_phieu_dao(self):
		"""I-2 (review vòng sửa 1) — `theo_may` của `bao_cao_cap_phat_rows`
		trước bản này CHỈ có `test_theo_may_cong_bang_gia_tri_cua_khoa` bảo
		vệ, và ca đó là một bất biến HÌNH THỨC: `sum(theo_may.gia_tri)` và
		`nhom.gia_tri` cộng từ CÙNG một vòng lặp, CÙNG một `continue` lọc
		`loai_xuat` — xoá bộ lọc đó làm CẢ HAI vế lệch NHƯ NHAU nên ca đó
		không đỏ (cùng loại bẫy "bất biến hàng cân tautological" Task 9 đã
		bị chỉ ra). Ca này kiểm một GIÁ TRỊ TUYỆT ĐỐI, không phải một tổng
		nội bộ, nên không tự triệt tiêu theo cách đó.

		`vat_tu_dao`/`may_dao` (khoa_phong=None -> nhóm "Chưa gắn khoa"): một
		phiếu 5 đơn vị GIỮ NGUYÊN (đơn giá 20.000 -> gia_tri 100.000) và một
		phiếu 10 đơn vị bị HUỶ. Lọc đúng hai lớp phải ra sl=5.0/gia_tri=
		100.000 cho `may_dao`; thiếu lớp `loai_xuat` sẽ cộng NGƯỢC DẤU dòng
		bù trừ của phiếu đảo (nó VẪN mang `thiet_bi=may_dao` vì Task 3 chép
		sang) vào tổng, ra sl=-5.0/gia_tri=-100.000 — sai rõ ràng.

		Thực nghiệm xác nhận (ghi lại trong task-10-report.md): xoá tạm điều
		kiện `iss["loai_xuat"] != "Xuất sử dụng"` khỏi vòng lặp xây
		`theo_may_map` trong `bao_cao_cap_phat_rows` -> ca này ĐỎ (gia_tri
		ra -100000.0 thay vì 100000.0) -> revert -> xanh lại.
		"""
		bc = reports.bao_cao_cap_phat_rows(self.kho, self.tu, self.den)
		nhom_chua_gan = next(n for n in bc["nhom"] if n["khoa_phong"] is None)
		dong = next(m for m in nhom_chua_gan["theo_may"] if m["thiet_bi"] == self.may_dao.name)
		self.assertAlmostEqual(dong["sl"], 5.0, places=4)
		self.assertAlmostEqual(dong["gia_tri"], 100000.0, places=2)

	def test_theo_may_tach_hai_may_cung_ten_theo_docname(self):
		"""Khoa A có HAI máy cùng tên 'Máy XN-500' (khác docname) — phải ra
		HAI dòng theo_may, không bị gộp thành một."""
		bc = reports.bao_cao_cap_phat_rows(self.kho, self.tu, self.den)
		nhom_a = next(n for n in bc["nhom"] if n["khoa_phong"] == self.kp_a.name)
		cung_ten = [m for m in nhom_a["theo_may"] if m["ten_may"] == "Máy XN-500"]
		self.assertEqual(len(cung_ten), 2)
		self.assertEqual(
			{m["thiet_bi"] for m in cung_ten}, {self.may_x1.name, self.may_x2.name}
		)
		gia_tri_by_thiet_bi = {m["thiet_bi"]: m["gia_tri"] for m in cung_ten}
		self.assertAlmostEqual(gia_tri_by_thiet_bi[self.may_x1.name], 100000.0, places=2)
		self.assertAlmostEqual(gia_tri_by_thiet_bi[self.may_x2.name], 80000.0, places=2)

	def test_tieu_thu_theo_may_gop_theo_docname(self):
		"""Hai máy khác nhau CÙNG TÊN phải ra HAI dòng — PHÒNG THỦ, không
		mô tả hiện trạng: luật hiện hành (`_chan_trung_ten()`, spec §4.1)
		chặn cứng trùng tên trong một bệnh viện qua đường tạo mới bình
		thường; trạng thái này chỉ dựng được ở đây bằng
		`flags.ignore_validate` (xem setUp), để ghim gộp theo docname vẫn
		đúng NẾU luật đổi sau này."""
		rows = reports.tieu_thu_theo_may_rows(self.kho, self.tu, self.den)
		cung_ten = [r for r in rows if r["ten_may"] == "Máy XN-500"]
		self.assertEqual(len(cung_ten), 2)

	def test_tieu_thu_theo_may_loc_hai_lop_khi_co_phieu_dao(self):
		"""Máy Đảo Test có một phiếu 5 GIỮ NGUYÊN và một phiếu 10 bị HUỶ.
		Lọc đúng hai lớp phải ra sl=5; thiếu lớp `loai_xuat` sẽ ra -5 (dòng
		bù trừ bị cộng ngược dấu vào tổng)."""
		rows = reports.tieu_thu_theo_may_rows(self.kho, self.tu, self.den)
		dong = next(r for r in rows if r["thiet_bi"] == self.may_dao.name)
		self.assertAlmostEqual(dong["sl"], 5.0, places=4)

	def test_tieu_thu_theo_may_gom_vat_tu_chi_tiet(self):
		rows = reports.tieu_thu_theo_may_rows(self.kho, self.tu, self.den)
		dong = next(r for r in rows if r["thiet_bi"] == self.may_x1.name)
		self.assertEqual(dong["so_vat_tu"], 1)
		self.assertAlmostEqual(dong["sl"], 10.0, places=4)
		self.assertEqual(len(dong["vat_tu"]), 1)
		self.assertEqual(dong["vat_tu"][0]["vat_tu_id"], self.vat_tu.name)

	def test_desk_loc_theo_customer(self):
		rows = desk_reports.tieu_thu_theo_thiet_bi_rows(
			customer=self.khach, tu_ngay=self.tu, den_ngay=self.den,
		)
		self.assertTrue(rows)
		self.assertTrue(all(r["customer"] == self.khach for r in rows))

	def test_desk_be_phang_khong_long_danh_sach_vat_tu(self):
		"""`reports.tieu_thu_theo_may_rows()` trả `vat_tu` là DANH SÁCH LỒNG
		(đúng hợp đồng brief). Bản Desk PHẢI bẻ phẳng — một dòng bảng Script
		Report không render được cột chứa một list, và MỌI hàm khác của
		desk_reports.py trả `vat_tu`/`vat_tu_id` là giá trị VÔ HƯỚNG."""
		rows = desk_reports.tieu_thu_theo_thiet_bi_rows(
			customer=self.khach, tu_ngay=self.tu, den_ngay=self.den,
		)
		self.assertTrue(rows)
		dong = next(r for r in rows if r["thiet_bi"] == self.may_x1.name)
		self.assertEqual(dong["vat_tu_id"], self.vat_tu.name)
		self.assertNotIsInstance(dong["vat_tu_id"], list)
		self.assertAlmostEqual(dong["sl"], 10.0, places=4)
		# Vật tư đó CHỈ dùng đúng một máy trong fixture -> đúng MỘT dòng, không
		# nhân bản qua mọi máy.
		self.assertEqual(
			len([r for r in rows if r["thiet_bi"] == self.may_x1.name]), 1
		)

	def test_desk_khong_loc_thi_gom_nhieu_benh_vien(self):
		rows = desk_reports.tieu_thu_theo_thiet_bi_rows(tu_ngay=self.tu, den_ngay=self.den)
		customers = {r["customer"] for r in rows}
		self.assertIn(self.khach, customers)
		self.assertIn(self.khach2, customers)

	def test_desk_report_dang_ky_va_execute_chay_duoc(self):
		"""Nhân viên Miyano phải MỞ ĐƯỢC report này qua Desk thật, không chỉ
		hàm Python chạy được — chốt bị advisor phát hiện: task-10-brief.md
		không giao 'setup/install_kho_desk_reports.py' trong "Files", nhưng
		thiếu đăng ký thì báo cáo này là một hàm không ai với tới được, đúng
		lỗ hổng kế hoạch phải tự sửa. Test này chạy qua ĐÚNG `execute()` —
		đường Desk thật đọc filter dạng dict — không gọi thẳng desk_reports
		như các test khác ở trên."""
		from miyano_portal.miyano_portal.report.tiêu_thụ_theo_máy import (
			tiêu_thụ_theo_máy as rp,
		)
		from miyano_portal.setup.install_kho_desk_reports import install_kho_desk_reports

		install_kho_desk_reports()  # idempotent — đảm bảo Report đã tồn tại
		self.assertEqual(
			frappe.db.get_value("Report", "Tiêu thụ theo máy", "ref_doctype"),
			"Customer Stock Ledger Entry",
		)
		columns, data = rp.execute({
			"customer": self.khach, "tu_ngay": self.tu, "den_ngay": self.den,
		})
		self.assertTrue(columns)
		self.assertTrue(data)
		self.assertTrue(all(r["customer"] == self.khach for r in data))
