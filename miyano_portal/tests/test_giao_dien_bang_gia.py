"""Giao diện theo Price List (spec 2026-10-09 §7). Kiểm bằng nguồn Vue vì
`frontend/` không có hạ tầng test component. Phần LOGIC (đếm hai nhóm khi tách,
tạm tính) nằm ở `frontend/src/gio-hang.js` và được `gio-hang.test.mjs` chạy
thật bằng `yarn test`; các bài dưới đây chỉ canh màn hình có NỐI vào đó."""

import re
from pathlib import Path

from frappe.tests.utils import FrappeTestCase

SRC = Path(__file__).resolve().parents[2] / "frontend" / "src"


def _doc(rel):
	return (SRC / rel).read_text(encoding="utf-8")


class TestGiaoDienBangGia(FrappeTestCase):
	def test_man_dat_hang_khong_con_hop_dong_va_han_muc(self):
		s = _doc("views/LapPhieu.vue")
		for cu in ("nhanHanMuc", "canhBaoHanMuc", "Giá HĐ", "blanket_order",
		           "khong_gioi_han", "nguon_don_gia", "'hop_dong'", "Hạn mức",
		           "HĐ KHUNG", "remaining"):
			self.assertNotIn(cu, s, cu)
		self.assertIn("Chờ báo giá", s)

	def test_man_dat_hang_doc_tang_va_gia_tu_gio_hang_js(self):
		"""Nhãn tầng, thành tiền và thông báo tách đều đi qua `gio-hang.js` —
		nơi có test chạy thật — không tự tính lại trong component."""
		s = _doc("views/LapPhieu.vue")
		self.assertRegex(s, r"from '\.\./gio-hang'")
		for ten in ("tomTatGio", "thanhTienDong", "tangTuNguonGia", "coGia", "laTangBangGia"):
			self.assertIn(ten, s, ten)
		self.assertIn("'bang_gia'", _doc("gio-hang.js"))

	def test_man_dat_hang_bao_truoc_khi_tach(self):
		s = _doc("views/LapPhieu.vue")
		self.assertIn("sẽ tách thành 2 phiếu", s)
		self.assertIn("tomTat.seTach", s)
		self.assertIn("Tạm tính", s)
		self.assertIn("THÀNH TIỀN", s)

	def test_man_dat_hang_ve_danh_sach_khi_ra_hai_phieu(self):
		s = _doc("views/LapPhieu.vue")
		self.assertIn("res.phieu_cung_lan_dat", s)
		# Nhánh quản lý: việc đọc `res.don` (một đơn hay hai chứng từ) nay nằm
		# ở `dichSauDatHang` của `bao-gia.js` (spec 2026-10-12 §5) — canh cả
		# chỗ màn GỌI hàm lẫn chỗ hàm ĐỌC `don`, và đích "về danh sách".
		self.assertIn("dichSauDatHang(res)", s)
		ham = _doc("bao-gia.js").split("export function dichSauDatHang", 1)[1]
		self.assertRegex(ham, r"res\?\.don\b")
		self.assertRegex(ham, r"don\.length === 2\) return \{ loai: 'tron', to: \{ name: 'yeu-cau' \} \}")
		self.assertNotRegex(s, r"portal_order_place'[^)]*\bcontract\b")

	def test_trang_chu_va_ho_so_khong_con_hop_dong(self):
		for f in ("views/Dashboard.vue", "views/Profile.vue"):
			s = _doc(f)
			self.assertNotIn("portal_contracts", s, f)
			self.assertNotIn("Hạn mức", s, f)
			self.assertNotIn("Hợp đồng khung", s, f)
			self.assertNotIn("hợp đồng khung", s, f)

	def test_khong_man_nao_con_goi_ba_endpoint_da_go(self):
		for f in sorted(SRC.rglob("*")):
			if f.suffix not in (".vue", ".js", ".mjs"):
				continue
			s = f.read_text(encoding="utf-8")
			for ten in ("portal_contracts", "portal_catalog_ban_le"):
				self.assertNotIn(ten, s, f"{f.name}: {ten}")
			self.assertIsNone(re.search(r"portal_catalog['\"]", s), f.name)

	def test_chi_tiet_co_duong_sang_phieu_cung_lan_dat_va_canh_bao_gia(self):
		s = _doc("views/ChiTietYeuCau.vue")
		self.assertIn("phieu_cung_lan_dat", s)
		self.assertIn("canh_bao_gia", s)
		self.assertIn("Duyệt cả hai", s)
		self.assertIn("Duyệt cả hai", _doc("de-xuat-actions.js"))
		self.assertNotIn("don.hdnt", s)
		self.assertNotIn("don?.hdnt", s)

	def test_chi_tiet_nap_lai_khi_doi_phieu_tren_cung_man(self):
		"""Đường dẫn sang phiếu cùng lần đặt chỉ đổi tham số route; Vue Router
		tái dùng component nên thiếu `watch` thì màn vẫn hiện phiếu cũ."""
		s = _doc("views/ChiTietYeuCau.vue")
		self.assertRegex(s, r"watch\(\s*\(\)\s*=>\s*\[route\.params\.ten,\s*route\.params\.name\]")

	def test_duyet_ca_hai_gui_co_len_server(self):
		reg = _doc("de-xuat-actions.js")
		self.assertRegex(reg, r"key:\s*'duyet_ca_hai',\s*const:\s*1")
		self.assertRegex(reg, r"phieu_cung_lan_dat\?\.trang_thai === 'Chờ duyệt'")
		# `nhanDuyet` phải gộp hằng số của hành động vào lời gọi, nếu không
		# "Duyệt cả hai" chỉ duyệt một phiếu.
		s = _doc("views/ChiTietYeuCau.vue")
		self.assertIn("hangSoCuaHanhDong(action)", s)

	def test_dat_lai_khong_con_ly_do_theo_hop_dong(self):
		s = _doc("views/ChiTietYeuCau.vue")
		for cu in ("ngoai_hdnt", "het_han_muc", "ngoài hợp đồng", "hết hạn mức", "thieu_gia"):
			self.assertNotIn(cu, s, cu)
		self.assertIn("mat_hang_ngung_kinh_doanh", s)

	def test_bang_mat_hang_hien_don_gia_da_dong_dau_cua_phieu_chua_co_don(self):
		s = _doc("components/chi-tiet/BangMatHang.vue")
		self.assertIn("coCotGiaPhieu", s)
		self.assertRegex(s, r"if \(coCotGiaPhieu\.value\) n \+= 1")
		# Giá chỉ hiện cho dòng thuộc nguồn CÓ giá: dòng "Chờ báo giá" còn sót
		# đơn giá của lần gửi trước không được in con số đó ra.
		self.assertRegex(
			s, r"NGUON_CO_GIA\.includes\(row\.nguon_gia\) && Number\(row\.don_gia\) > 0"
		)
		self.assertIn("dong.value.some(coGiaPhieu)", s)
		self.assertNotIn("some((r) => Number(r.don_gia) > 0)", s)
		self.assertRegex(s, r"coCotGiaPhieu = computed\([\s\S]{0,120}trang_thai !== 'Nháp'")

	def test_danh_sach_hien_ma_lan_dat_ca_hai_bo_cuc(self):
		s = _doc("views/YeuCauList.vue")
		self.assertEqual(s.count("Lần đặt {{ r.ma_lan_dat }}"), 2, "desktop và mobile")

	def test_sua_so_luong_khong_con_noi_moi_dong_ve_gia_0(self):
		"""Dòng có giá trong bảng giá GIỮ giá khi khách sửa số lượng; chỉ dòng
		đã báo giá mới chờ báo giá lại (spec §4.4)."""
		for f in ("views/ChiTietYeuCau.vue", "components/chi-tiet/KhoiBaoGia.vue", "don-actions.js"):
			s = _doc(f)
			for cu in ("về giá 0", "rate = 0 cho dòng đã đổi", "`rate` các dòng"):
				self.assertNotIn(cu, s, f"{f}: {cu}")
