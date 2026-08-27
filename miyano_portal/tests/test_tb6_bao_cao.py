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

from miyano_portal.kho import reports

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
		"""CA 13 của spec — ca đã suýt bị bỏ sót và là lý do tách hai cột xuất."""
		bc = reports.bao_cao_thiet_bi_rows(self.kho, self.tu, self.den)
		for d in bc["dong"]:
			self.assertAlmostEqual(
				d["ton_dau"] + d["nhap"] - d["cap_phat"] - d["xuat_khac"], d["ton_cuoi"],
				places=4,
				msg=f"Hàng không cân ở vật tư {d['ma_vat_tu']}",
			)
