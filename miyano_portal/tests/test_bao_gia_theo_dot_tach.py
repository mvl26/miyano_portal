"""Tách đợt trên yêu cầu báo giá (spec 2026-10-15 §4.1)."""

from unittest.mock import patch

import frappe
from frappe.model.workflow import apply_workflow, get_transitions
from frappe.utils import flt

from miyano_portal import bao_gia, bao_gia_theo_dot as dot
from miyano_portal.tests.nen_bao_gia import NenBaoGiaTheoDot


class TestTachDot(NenBaoGiaTheoDot):
	def _ten_dong(self, goc, *ma):
		return [d.name for d in goc.items if d.item_code in ma]

	def test_tach_hop_le(self):
		goc = self._goc_ba_dong()
		kq = dot.tach_dot(goc.name, self._ten_dong(goc, self.item_ngoai, self.item_boi_so))
		d1 = frappe.get_doc("Quotation", kq["dot"])
		self.assertEqual(kq["so_dot"], 1)
		self.assertEqual(d1.custom_phieu_goc, goc.name)
		self.assertEqual(d1.custom_so_dot, 1)
		self.assertEqual(d1.custom_request_id, goc.custom_request_id + ":dot1")
		self.assertEqual(d1.workflow_state, bao_gia.TT_CHO_KHACH)
		self.assertTrue(d1.valid_till)
		self.assertEqual(d1.custom_nguon_don, bao_gia.NGUON_CONG)
		self.assertEqual((d1.party_name, d1.custom_khoa_phong), (goc.party_name, goc.custom_khoa_phong))
		self.assertEqual(
			sorted((d.item_code, d.rate) for d in d1.items),
			sorted([(self.item_ngoai, 54000), (self.item_boi_so, 7000)]),
		)
		goc.reload()
		self.assertEqual([d.item_code for d in goc.items], [self.item_co_dau])
		self.assertEqual(goc.workflow_state, bao_gia.TT_CHO_MIYANO)
		self.assertEqual(kq["trang_thai_goc"], bao_gia.TT_CHO_MIYANO)

	def test_dot_thu_hai_tang_so(self):
		goc = self._goc_ba_dong()
		dot.tach_dot(goc.name, self._ten_dong(goc, self.item_ngoai))
		goc.reload()
		kq = dot.tach_dot(goc.name, self._ten_dong(goc, self.item_boi_so))
		self.assertEqual(kq["so_dot"], 2)
		self.assertTrue(kq["dot"])
		self.assertEqual(
			frappe.db.get_value("Quotation", kq["dot"], "custom_request_id"),
			goc.custom_request_id + ":dot2",
		)

	def test_tach_het_dong_thanh_da_bao_het(self):
		goc = self._goc_ba_dong()
		kq = dot.tach_dot(goc.name, [d.name for d in goc.items])
		goc.reload()
		self.assertEqual(goc.items, [])
		self.assertEqual(goc.workflow_state, bao_gia.TT_DA_BAO_HET)
		self.assertEqual(kq["trang_thai_goc"], bao_gia.TT_DA_BAO_HET)

	def test_con_dong_go_tay_chua_khop_thi_khong_bao_het(self):
		goc = self._goc_ba_dong(custom_dat_ngoai=[
			{"ten_hang": "Kim lạ chưa có mã", "dvt": "Cái", "so_luong": 2},
		])
		dot.tach_dot(goc.name, [d.name for d in goc.items])
		goc.reload()
		self.assertEqual(goc.workflow_state, bao_gia.TT_CHO_MIYANO)

	def test_dong_go_tay_da_khop_chuyen_sang_dot_khong_sinh_lai(self):
		"""Dòng gõ tay đã khớp mã sinh ra một dòng hàng (`dong_hang`). Dòng hàng
		đó sang đợt thì lần lưu sau của phiếu gốc KHÔNG được sinh nó lần nữa
		(`da_chuyen` giữ nguyên), và dòng giữ chỗ hook tự chèn không chặn
		"Đã báo hết"."""
		goc = self._bao_gia_tho(
			items=[{"item_code": self.item_boi_so, "qty": 10, "rate": 7000, "price_list_rate": 7000}],
			custom_dat_ngoai=[{"ten_hang": "Kim gõ tay", "dvt": "Cái", "so_luong": 2}],
		)
		goc.custom_dat_ngoai[0].item_khop = self.item_ngoai
		goc.save()
		self.assertIn(self.item_ngoai, [d.item_code for d in goc.items])
		self.assertEqual(goc.custom_dat_ngoai[0].da_xu_ly, 1)
		dot.tach_dot(goc.name, [d.name for d in goc.items if flt(d.rate) > 0])
		goc.reload()
		goc.save()
		goc.reload()
		from miyano_portal.portal_mua_le import la_dong_giu_cho

		self.assertEqual([d.item_code for d in goc.items if not la_dong_giu_cho(d.item_code)], [])
		self.assertEqual(goc.workflow_state, bao_gia.TT_DA_BAO_HET)

	def test_dong_thieu_gia_bi_chan(self):
		goc = self._goc_ba_dong()
		goc.items[0].rate = goc.items[0].price_list_rate = 0
		goc.save()
		with self.assertRaisesRegex(frappe.ValidationError, "Chưa có đơn giá"):
			dot.tach_dot(goc.name, [goc.items[0].name])
		self.assertFalse(frappe.db.exists("Quotation", {"custom_phieu_goc": goc.name}))

	def test_tach_dong_khong_con_tren_phieu_bi_chan(self):
		goc = self._goc_ba_dong()
		with self.assertRaisesRegex(frappe.ValidationError, "đã được báo ở đợt khác"):
			dot.tach_dot(goc.name, ["khong-ton-tai-123"])

	def test_tach_hai_lan_cung_dong_bi_chan(self):
		goc = self._goc_ba_dong()
		chon = self._ten_dong(goc, self.item_ngoai)
		dot.tach_dot(goc.name, chon)
		with self.assertRaisesRegex(frappe.ValidationError, "đã được báo ở đợt khác"):
			dot.tach_dot(goc.name, chon)
		self.assertEqual(
			frappe.db.count("Quotation", {"custom_phieu_goc": goc.name}), 1
		)

	def test_loi_giua_chung_lui_ca_ba_buoc(self):
		goc = self._goc_ba_dong()
		chon = self._ten_dong(goc, self.item_ngoai)

		# Hỏng đúng ở bước CUỐI (gửi khách đợt): đợt đã chèn, dòng đã xoá khỏi
		# phiếu gốc — cả hai phải lùi. Frappe tra hook theo chuỗi mỗi lần gọi
		# nên `patch` thay được.
		def hong_khi_gui_khach(doc, method=None):
			if doc.get("workflow_state") == bao_gia.TT_CHO_KHACH:
				raise frappe.ValidationError("hỏng")

		with patch("miyano_portal.bao_gia.chot_gui_khach", side_effect=hong_khi_gui_khach):
			with self.assertRaises(frappe.ValidationError):
				dot.tach_dot(goc.name, chon)
		goc.reload()
		self.assertEqual(len(goc.items), 3)
		self.assertFalse(frappe.db.exists("Quotation", {"custom_phieu_goc": goc.name}))

	def test_chi_tach_tren_phieu_goc_cua_cong_dang_cho_miyano(self):
		noi_bo = self._goc_ba_dong(nguon="Nội bộ")
		with self.assertRaises(frappe.ValidationError):
			dot.tach_dot(noi_bo.name, [noi_bo.items[0].name])
		goc = self._goc_ba_dong()
		kq = dot.tach_dot(goc.name, [goc.items[0].name])
		d1 = frappe.get_doc("Quotation", kq["dot"])
		with self.assertRaises(frappe.ValidationError):
			dot.tach_dot(d1.name, [d1.items[0].name])

	def test_dong_rong_bi_chan(self):
		goc = self._goc_ba_dong()
		for xau in ([], "[]", "khong-phai-json", [1, 2], None):
			with self.assertRaises(frappe.ValidationError):
				dot.tach_dot(goc.name, xau)

	def test_chan_gui_khach_va_tu_choi_tren_phieu_goc_da_co_dot(self):
		goc = self._goc_ba_dong()
		dot.tach_dot(goc.name, [goc.items[0].name])
		goc.reload()
		with self.assertRaisesRegex(frappe.ValidationError, "Báo giá đợt này"):
			apply_workflow(goc, bao_gia.HD_GUI_KHACH)
		goc.reload()
		goc.custom_ly_do_tu_choi = "Không còn nhà cung cấp nào"
		goc.save()
		with self.assertRaisesRegex(frappe.ValidationError, "Huỷ phần còn lại"):
			apply_workflow(goc, bao_gia.HD_TU_CHOI)

	def test_phieu_chua_tach_khong_thay_huy_con_lai_va_bao_het(self):
		goc = self._goc_ba_dong()
		hd = {t["action"] for t in get_transitions(goc)}
		self.assertNotIn(bao_gia.HD_HUY_CON_LAI, hd)
		self.assertNotIn(bao_gia.HD_BAO_HET, hd)

	def test_nhan_vien_sales_user_tach_het_duoc(self):
		goc = self._goc_ba_dong()
		frappe.set_user(self._nhan_vien())
		try:
			kq = dot.tach_dot(goc.name, [d.name for d in goc.items])
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(kq["trang_thai_goc"], bao_gia.TT_DA_BAO_HET)

	def test_khong_xoa_duoc_phieu_goc_con_dot(self):
		goc = self._goc_ba_dong()
		dot.tach_dot(goc.name, [goc.items[0].name])
		with self.assertRaises(frappe.LinkExistsError):
			frappe.delete_doc("Quotation", goc.name)

	def test_hook_bo_qua_khi_chua_co_cot(self):
		goc = self._goc_ba_dong()
		with patch.object(dot, "san_sang", return_value=False):
			goc.custom_ten_don_hang = "Lưu khi chưa migrate"
			goc.save()
			self.assertFalse(dot.co_dot(goc.name))
