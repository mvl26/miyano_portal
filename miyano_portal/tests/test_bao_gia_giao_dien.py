"""Nối dây giao diện của tab "Yêu cầu báo giá" (spec 2026-10-12 §6)."""

import inspect
import re
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import portal

SRC = Path(frappe.get_app_path("miyano_portal")).parent / "frontend" / "src"


def _doc(ten):
	return (SRC / ten).read_text()


def _endpoint_that_portal():
	# Cùng cách đo với `test_de_xuat_action_registry.py`: Frappe ghi hàm gốc
	# vào `frappe.whitelisted`, không gắn thuộc tính lên hàm.
	return {
		ten for ten, fn in inspect.getmembers(portal, inspect.isfunction)
		if fn in frappe.whitelisted and fn.__module__ == portal.__name__
	}


class TestBaoGiaGiaoDien(FrappeTestCase):
	def test_hai_route(self):
		router = _doc("router.js")
		self.assertIn("path: '/yeu-cau-bao-gia', name: 'bao-gia'", router)
		self.assertIn("path: '/yeu-cau-bao-gia/:ten', name: 'bao-gia-detail'", router)

	def test_muc_nav_sang_o_ca_hai_tab(self):
		app = _doc("App.vue")
		self.assertIn("name === 'bao-gia'", app)
		self.assertIn("name === 'bao-gia-detail'", app)

	def test_ca_hai_man_danh_sach_co_dai_tab(self):
		for ten in ("views/YeuCauList.vue", "views/BaoGiaList.vue"):
			self.assertIn("<TabDonBaoGia", _doc(ten), ten)

	def test_nhom_cua_frontend_khop_backend(self):
		nguon = _doc("bao-gia.js")
		khoa = re.search(r"NHOM_BAO_GIA = \[([^\]]+)\]", nguon).group(1)
		self.assertEqual(tuple(re.findall(r"'(\w+)'", khoa)), portal.NHOM_BAO_GIA)

	def test_khoa_nhom_khong_lot_vao_giai_doan(self):
		khoi = re.search(r"export const GIAI_DOAN = \[([^\]]+)\]", _doc("format.js")).group(1)
		for khoa in ("dang_bao_gia", "cho_dong_y", "da_dong"):
			self.assertNotIn(khoa, khoi)

	def test_endpoint_frontend_goi_deu_ton_tai(self):
		for ten in ("views/BaoGiaList.vue", "views/ChiTietBaoGia.vue",
		            "components/KhoiBaoGia.vue", "components/TabDonBaoGia.vue"):
			ds = re.findall(r"api\.call\(\s*['\"](\w+)['\"]", _doc(ten))
			self.assertTrue(ds, f"{ten}: không quét được lời gọi api.call nào")
			for ham in ds:
				self.assertIn(ham, _endpoint_that_portal(), f"{ten}: {ham}")

	def test_chi_tiet_khong_ve_gia_khi_server_giau(self):
		nguon = _doc("components/KhoiBaoGia.vue")
		self.assertIn("quotation=", nguon)
		mau = nguon.split("<template>", 1)[1]
		# Mỗi con số tiền phải nằm trên phần tử mang `v-if="bg.hien_gia"` của
		# CHÍNH nó: giữa thẻ mở đó và `{{ … }}` chỉ được có chữ (và một <b>),
		# không có thẻ nào khác. Vẽ giá không điều kiện là hỏng test này.
		for bieu_thuc in ("fmtVND(it.rate)", "fmtVND(it.amount)", "fmtVND(bg.tong_tien)"):
			tat_ca = mau.count(bieu_thuc)
			self.assertGreaterEqual(tat_ca, 1, bieu_thuc)
			co_cong = re.findall(
				r'<\w+\b[^>]*\bv-if="bg\.hien_gia"[^>]*>(?:\s*<b>)?[^<>]*' + re.escape(bieu_thuc),
				mau,
			)
			self.assertEqual(len(co_cong), tat_ca, f"{bieu_thuc} bị vẽ ngoài v-if bg.hien_gia")

	def test_thong_bao_gia_chua_co_theo_co_cua_server(self):
		self.assertIn(
			"v-if=\"!bg.hien_gia && bg.nhom === 'dang_bao_gia'\"",
			_doc("components/KhoiBaoGia.vue"),
		)

	def test_sua_so_luong_chan_so_khong_hop_le(self):
		nguon = _doc("components/KhoiBaoGia.vue")
		ham = nguon.split("function guiSuaSoLuong", 1)[1].split("\n}\n", 1)[0]
		self.assertIn("loiSoLuong(bg.value.items, soLuongMoi.value)", ham)
		# Kiểm lỗi TRƯỚC khi dựng danh sách dòng gửi đi.
		self.assertLess(ham.index("loiSoLuong("), ham.index("dongDaSua("))

	def test_chi_tiet_ve_moi_dot_mot_khoi(self):
		nguon = _doc("views/ChiTietBaoGia.vue")
		self.assertIn('<KhoiBaoGia v-for="d in bg.dot"', nguon)
		self.assertIn("portal_bao_gia_huy_con_lai", nguon)
		self.assertIn('v-if="bg.duoc_huy_con_lai"', nguon)
		# Khối "Chờ Miyano báo giá" chỉ theo cờ của server, không theo dòng gõ tay
		# (server đã trả `dat_ngoai` rỗng khi phiếu gốc thôi báo).
		self.assertIn('v-if="bg.con_lai.length || bg.duoc_huy_con_lai"', nguon)
		self.assertIn('v-if="bg.da_huy_con_lai"', nguon)
		self.assertIn("Đã huỷ các mặt hàng chưa báo giá", nguon)
		self.assertIn("Lý do: {{ bg.ly_do_huy_con_lai }}", nguon)
		# Dòng chưa báo không bao giờ mang giá.
		khoi = nguon.split('v-for="it in bg.con_lai"', 1)[1].split("</tr>", 1)[0]
		self.assertNotIn("fmtVND", khoi)

	def test_duyet_phieu_bao_dung_chung_tu_sinh_ra(self):
		nguon = _doc("views/ChiTietYeuCau.vue")
		self.assertIn("thongBaoSauDuyet(kq)", nguon)
		# Câu khẳng định "đã tạo đơn" không còn nằm cứng trong bảng toast.
		self.assertNotRegex(nguon, r"de_xuat_duyet_phieu[^\n]*đơn hàng đã được tạo")

	def test_phieu_mo_tu_tab_bao_gia_quay_lai_dung_tab(self):
		nguon = _doc("views/ChiTietYeuCau.vue")
		khoi = nguon.split("const quayLaiTo = computed(", 1)[1].split("\n})", 1)[0]
		self.assertIn("route.query.tu === 'bao-gia'", khoi)
		self.assertIn("name: 'bao-gia'", khoi)
		self.assertIn("name: 'yeu-cau'", khoi)

	def test_chi_tiet_dung_ba_cot_ten_hang_chung(self):
		# Quy tắc Mã / Tên mặt hàng / Tên thường gọi của mọi bảng mặt hàng
		# trên cổng (`ten-hang.js`): bảng của màn báo giá không tự vẽ ô riêng.
		nguon = _doc("components/KhoiBaoGia.vue")
		self.assertIn("<CotTenHang head />", nguon)
		self.assertIn('<CotTenHang :ma="it.item_code"', nguon)

	def test_su_kien_nhat_ky_moi_co_nhan(self):
		fmt = _doc("format.js")
		for khoa in ("bao_gia_tao", "bao_gia_het_han"):
			self.assertIn(f"{khoa}:", fmt)

	def test_dashboard_co_the_bao_gia(self):
		nguon = _doc("views/Dashboard.vue")
		mau = nguon.split("<template>", 1)[1]
		the = re.search(
			r"<router-link :to=\"\{ name: 'bao-gia', query: \{ nhom: 'cho_dong_y' \} \}\""
			r".*?</router-link>", mau, re.S,
		).group(0)
		self.assertIn("{{ kpi.bao_gia_cho_dong_y }}", the)
		# Thẻ trỏ sang tab báo giá chỉ mang con số của tab báo giá.
		self.assertNotIn("don_cu_cho_dong_y", the)

	def test_dashboard_khong_con_duong_dan_don_cu_cho_dong_y(self):
		# Patch v1_44 bỏ vòng báo giá trên đơn: không còn đơn nào chờ khách
		# đồng ý, và máy chủ không còn trả con số đó.
		self.assertNotIn("don_cu_cho_dong_y", _doc("views/Dashboard.vue"))

	def test_dong_nhom_nhap_hien_trang_thai_phieu_ca_tren_di_dong(self):
		"""I1 — nhóm "Nháp / chờ duyệt nội bộ" gom Nháp, Chờ duyệt, Từ chối, Đã
		huỷ. Huy hiệu của dòng nhóm đó phải nói đúng trạng thái phiếu, ở cả
		bảng lẫn thẻ di động."""
		mau = _doc("views/BaoGiaList.vue").split("<template>", 1)[1]
		ban, di_dong = mau.split("<template v-else>", 1)
		huy_hieu = (
			'<span class="badge" :class="badgeDongBaoGia(r)">{{ nhanDongBaoGia(r) }}</span>'
		)
		self.assertEqual(ban.count(huy_hieu), 1)
		self.assertEqual(di_dong.count(huy_hieu), 1)
		# Không còn huy hiệu nào chỉ vẽ theo nhóm.
		self.assertNotIn("nhomBaoGiaBadge", mau)
		nguon = _doc("bao-gia.js")
		ham = nguon.split("export function nhanDongBaoGia", 1)[1].split("\n}\n", 1)[0]
		self.assertIn("dong.nhom === 'nhap'", ham)
		self.assertIn("dong.trang_thai_phieu", ham)

	def test_dat_hang_khong_hien_ma_don_rong(self):
		# Giỏ chỉ có hàng chờ báo giá không sinh đơn: màn Đặt hàng hỏi
		# `dichSauDatHang` (bao-gia.js) chứ không tự coi kết quả là một đơn.
		nguon = _doc("views/LapPhieu.vue")
		self.assertIn("dichSauDatHang(res)", nguon)
		self.assertIn("1 đơn đặt ngay và 1 yêu cầu báo giá", nguon)
		self.assertNotIn("1 đơn chờ báo giá", nguon)

	def test_desk_quotation_co_nut_bao_gia_dot(self):
		js = (Path(frappe.get_app_path("miyano_portal")) / "public" / "js" / "quotation.js").read_text()
		self.assertIn('method: "miyano_portal.bao_gia_theo_dot.tach_dot"', js)
		self.assertIn('__("Báo giá đợt này")', js)
		# Nhãn ô chọn được gán bằng innerHTML: tên hàng phải được thoát.
		self.assertIn("frappe.utils.escape_html(d.item_name", js)
		from miyano_portal import bao_gia_theo_dot

		self.assertIn(bao_gia_theo_dot.tach_dot, frappe.whitelisted)
