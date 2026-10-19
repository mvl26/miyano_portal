"""Task 6 (HSD tối thiểu theo yêu cầu khách) — cổng mang số tháng vào đơn."""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import de_xuat_duyet
from miyano_portal.api import de_xuat, portal
from miyano_portal.setup.seed_demo import seed_demo
from miyano_portal.tests.fixtures_de_xuat import dung_fixture, khai_gia
from miyano_portal.tests.test_de_xuat_duyet import (
	_dam_bao_thanh_vien,
	_don_phieu_cu,
	_item2,
)

ITEM_A = "VT0005"
ITEM_B = "HC0009"
ITEM_CHUA_GIA = "_TEST HSD CONG CHUA GIA"


def _rid():
	return frappe.generate_hash(length=12)


def _item_chua_gia():
	if not frappe.db.exists("Item", ITEM_CHUA_GIA):
		frappe.get_doc({
			"doctype": "Item", "item_code": ITEM_CHUA_GIA, "item_name": ITEM_CHUA_GIA,
			"item_group": "All Item Groups", "stock_uom": "Cái", "is_stock_item": 1,
		}).insert(ignore_permissions=True)
	return ITEM_CHUA_GIA


def _so_theo_ma(so):
	return {d.item_code: d.custom_hsd_toi_thieu_thang for d in so.items}


class TestHsdCongOrderPlace(FrappeTestCase):
	def setUp(self):
		seed_demo()
		frappe.set_user("bvbm@demo.miyano")
		self.addCleanup(frappe.set_user, "Administrator")

	def _dat(self, items, **kw):
		return portal.portal_order_place(
			None, json.dumps(items), request_id=_rid(), **kw
		)

	def test_order_place_mang_so_thang(self):
		res = self._dat(
			[{"item_code": ITEM_A, "qty": 10, "hsd_toi_thieu_thang": 6},
			 {"item_code": ITEM_B, "qty": 10}],
			hsd_toi_thieu_thang=3,
		)
		so = frappe.get_doc("Sales Order", res["sales_order"])
		self.assertEqual(so.custom_hsd_toi_thieu_thang, 3)
		self.assertEqual(_so_theo_ma(so), {ITEM_A: 6, ITEM_B: 3})

	def test_gop_cung_ma_lay_max(self):
		res = self._dat([
			{"item_code": ITEM_A, "qty": 10, "hsd_toi_thieu_thang": 2},
			{"item_code": ITEM_A, "qty": 10, "hsd_toi_thieu_thang": 5},
		])
		so = frappe.get_doc("Sales Order", res["sales_order"])
		self.assertEqual(len(so.items), 1)
		self.assertEqual(so.items[0].qty, 20)
		self.assertEqual(so.items[0].custom_hsd_toi_thieu_thang, 5)

	def test_gop_cung_ma_dong_trong_theo_dau_phieu(self):
		# Dòng trống của cùng mã kế thừa đầu phiếu → dòng gộp lấy max(khai, đầu phiếu).
		res = self._dat([
			{"item_code": ITEM_A, "qty": 10, "hsd_toi_thieu_thang": 2},
			{"item_code": ITEM_A, "qty": 10},
		], hsd_toi_thieu_thang=5)
		so = frappe.get_doc("Sales Order", res["sales_order"])
		self.assertEqual(len(so.items), 1)
		self.assertEqual(so.items[0].custom_hsd_toi_thieu_thang, 5)
		# Dòng khai chặt hơn đầu phiếu thì giữ dòng khai.
		res = self._dat([
			{"item_code": ITEM_A, "qty": 10, "hsd_toi_thieu_thang": 7},
			{"item_code": ITEM_A, "qty": 10},
		], hsd_toi_thieu_thang=5)
		so = frappe.get_doc("Sales Order", res["sales_order"])
		self.assertEqual(so.items[0].custom_hsd_toi_thieu_thang, 7)

	def test_dat_hang_khong_lo_canh_bao_hsd_cho_khach(self):
		"""Đơn đặt trên cổng có dòng không đạt HSD: kết quả vẫn được tính nhưng câu
		cảnh báo nội bộ (tồn kho, HSD lô) không lọt vào message_log trả về cổng."""
		from unittest.mock import patch

		from miyano_portal import han_dung_khach

		khong_dat = {"dat": False, "hsd_tot_nhat": None, "ton_dat": 0}
		frappe.clear_messages()
		with patch.object(han_dung_khach, "ap_dung", return_value=True), patch.object(
			han_dung_khach, "kiem_ton_cho_dong", return_value=khong_dat
		):
			res = self._dat([{"item_code": ITEM_A, "qty": 10}], hsd_toi_thieu_thang=6)
		self.assertNotIn("HSD", json.dumps(frappe.local.message_log, ensure_ascii=False))
		self.assertEqual(
			frappe.db.get_value("Sales Order Item", {"parent": res["sales_order"]}, "custom_ket_qua_hsd"),
			"Không đạt",
		)

	def test_client_get_khong_lo_truong_noi_bo(self):
		"""Khách cổng đọc đơn của mình qua frappe.client.get (bản bọc search_guard):
		các trường nội bộ HSD không mang giá trị thật."""
		from miyano_portal import search_guard

		res = self._dat([{"item_code": ITEM_A, "qty": 10}], hsd_toi_thieu_thang=3)
		ten = res["sales_order"]
		dong = frappe.db.get_value("Sales Order Item", {"parent": ten}, "name")
		frappe.db.set_value("Sales Order Item", dong, {
			"custom_ngoai_le_hsd": 1, "custom_ngoai_le_hsd_den": "2026-12-20",
			"custom_ngoai_le_ly_do": "Lý do nội bộ", "custom_ngoai_le_boi": "Administrator",
		})
		d = search_guard.client_get("Sales Order", ten)
		self.assertEqual(d["custom_hsd_toi_thieu_thang"], 3)
		self.assertEqual(d["items"][0]["custom_hsd_toi_thieu_thang"], 3)
		for f in ("custom_ket_qua_hsd", "custom_hsd_ton_tot_nhat", "custom_hsd_yeu_cau_den",
		          "custom_ngoai_le_hsd", "custom_ngoai_le_hsd_den", "custom_ngoai_le_ly_do",
		          "custom_ngoai_le_boi", "custom_ngoai_le_luc"):
			self.assertIn(d["items"][0].get(f), (None, 0), f)
		flat = frappe.as_json(d)
		for gia_tri in ("Không áp dụng", "Lý do nội bộ", "2026-12-20"):
			self.assertNotIn(gia_tri, flat)

	def test_so_thang_sai_bi_tu_choi(self):
		truoc = frappe.db.count("Sales Order")
		for dau, dong in ((61, None), (None, 61), (None, "abc"), (-1, None), (2.5, None)):
			frappe.local.response.pop("loi", None)
			item = {"item_code": ITEM_A, "qty": 10}
			if dong is not None:
				item["hsd_toi_thieu_thang"] = dong
			with self.assertRaises(frappe.ValidationError):
				self._dat([item], hsd_toi_thieu_thang=dau)
			loi = frappe.local.response.get("loi")
			self.assertEqual(loi[0]["ly_do"], "hsd_toi_thieu_khong_hop_le")
		self.assertEqual(frappe.db.count("Sales Order"), truoc)

	def test_gio_tron_loi_hsd_khong_tao_gi(self):
		"""Dòng lô sau sai thì lô trước (đơn có giá) cũng không được tạo."""
		item = _item_chua_gia()
		truoc_so = frappe.db.count("Sales Order")
		truoc_bg = frappe.db.count("Quotation")
		with self.assertRaises(frappe.ValidationError):
			self._dat([
				{"item_code": ITEM_A, "qty": 10},
				{"item_code": item, "qty": 1, "hsd_toi_thieu_thang": 99},
			])
		self.assertEqual(frappe.db.count("Sales Order"), truoc_so)
		self.assertEqual(frappe.db.count("Quotation"), truoc_bg)

	def test_quotation_co_comment_hsd(self):
		item = _item_chua_gia()
		res = self._dat(
			[{"item_code": item, "qty": 1, "hsd_toi_thieu_thang": 6}],
			hsd_toi_thieu_thang=3,
		)
		self.assertTrue(res["bao_gia"])
		cmts = frappe.get_all(
			"Comment",
			filters={"reference_doctype": "Quotation", "reference_name": res["bao_gia"],
			         "comment_type": "Comment"},
			pluck="content",
		)
		self.assertEqual(len(cmts), 1)
		self.assertIn(f"Khách yêu cầu HSD tối thiểu: 3 tháng (cả đơn); {item}: 6 tháng", cmts[0])

	def test_quotation_khong_hsd_khong_comment(self):
		item = _item_chua_gia()
		res = self._dat([{"item_code": item, "qty": 1}])
		self.assertFalse(frappe.db.exists(
			"Comment", {"reference_doctype": "Quotation", "reference_name": res["bao_gia"],
			            "comment_type": "Comment"}))

	def test_order_track_khong_lo_truong_noi_bo(self):
		res = self._dat([{"item_code": ITEM_A, "qty": 10}], hsd_toi_thieu_thang=3)
		d = portal.portal_order_track(res["sales_order"])
		self.assertEqual(d["hsd_toi_thieu_thang"], 3)
		self.assertEqual(d["items"][0]["hsd_toi_thieu_thang"], 3)
		flat = frappe.as_json(d)
		for f in ("custom_ket_qua_hsd", "custom_hsd_ton_tot_nhat", "custom_ngoai_le",
		          "ket_qua_hsd", "ngoai_le", "custom_hsd_yeu_cau_den", "hsd_yeu_cau_den"):
			self.assertNotIn(f, flat)


class TestHsdCongDeXuat(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		_don_phieu_cu()
		f = dung_fixture(self)
		self.kh = f.kh_a
		self.item = f.item
		self.item2 = _item2()
		khai_gia(self.kh, self.item, self.item2)
		self.user = _dam_bao_thanh_vien(
			"hsdcong.huyethoc@demo.miyano", self.kh, "Nhân viên khoa", f.khoa_huyethoc
		)
		self.ql = _dam_bao_thanh_vien(
			"hsdcong.ql@demo.miyano", self.kh, "Quản lý", None
		)
		self.addCleanup(frappe.set_user, "Administrator")

	def test_de_xuat_duyet_mang_so_thang(self):
		frappe.set_user(self.user)
		ten = de_xuat.de_xuat_tao_nhap()["name"]
		de_xuat.de_xuat_luu_nhap(
			ten,
			items=json.dumps([
				{"item_code": self.item, "so_luong_de_xuat": 5, "hsd_toi_thieu_thang": 6},
				{"item_code": self.item2, "so_luong_de_xuat": 5},
			]),
			hsd_toi_thieu_thang=4, ly_do_yeu_cau="cần gấp",
		)
		ct = de_xuat.de_xuat_chi_tiet(ten)
		self.assertEqual(ct["hsd_toi_thieu_thang"], 4)
		self.assertEqual([r["hsd_toi_thieu_thang"] for r in ct["items"]], [6, 0])
		de_xuat.de_xuat_gui_duyet(ten)
		frappe.set_user("Administrator")
		kq = de_xuat_duyet.duyet_va_tao_don(ten, self.ql)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(so.custom_hsd_toi_thieu_thang, 4)
		self.assertEqual(_so_theo_ma(so), {self.item: 6, self.item2: 4})

	def test_luu_nhap_so_thang_sai(self):
		frappe.set_user(self.user)
		ten = de_xuat.de_xuat_tao_nhap()["name"]
		with self.assertRaises(frappe.ValidationError):
			de_xuat.de_xuat_luu_nhap(ten, hsd_toi_thieu_thang=61)
		with self.assertRaises(frappe.ValidationError):
			de_xuat.de_xuat_luu_nhap(ten, items=json.dumps([
				{"item_code": self.item, "so_luong_de_xuat": 1, "hsd_toi_thieu_thang": 100}]))
