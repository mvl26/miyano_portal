"""Tách giỏ trộn thành hai phiếu (spec 2026-10-09 §4.1)."""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import tach_phieu
from miyano_portal.api import de_xuat, portal
from miyano_portal.tests import test_catalog_gop as goc

DT = "Portal De Xuat Mua"


class TestTachPhieu(FrappeTestCase):
	def setUp(self):
		goc.TestPortalCatalogGop.setUp(self)
		for ma in (self.item_ngoai, self.item_boi_so):
			for ten in frappe.get_all(
				"Item Price", filters={"item_code": ma, "selling": 1}, pluck="name"
			):
				frappe.delete_doc("Item Price", ten, force=True)
		self._tao_gia(self.item_ngoai, self.price_list, 54000)   # có giá
		self.co_gia, self.chua_gia = self.item_ngoai, self.item_boi_so
		self.quan_ly = self._dam_bao_thanh_vien(
			"tach.ql@demo.miyano", self.kh_a, "Quản lý", None
		)
		# ERPNext tự tìm `Contact` theo người đang đăng nhập và gán vào
		# `so.contact_person`; Contact tự sinh của User chưa nối với khách thì
		# đơn bị từ chối ("Contact Person does not belong to…"). Cùng cách
		# dựng với `test_don_tron_bao_gia.py`.
		contact = frappe.db.get_value("Contact", {"user": self.quan_ly})
		if contact and not frappe.db.exists("Dynamic Link", {
			"parent": contact, "parenttype": "Contact",
			"link_doctype": "Customer", "link_name": self.kh_a,
		}):
			c = frappe.get_doc("Contact", contact)
			c.append("links", {"link_doctype": "Customer", "link_name": self.kh_a})
			c.save(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _phieu_nhap(self, ma_hang, dat_ngoai=None):
		frappe.set_user(self.user_a)
		ten = de_xuat.de_xuat_tao_nhap()["name"]
		de_xuat.de_xuat_luu_nhap(
			ten,
			items=[{"item_code": m, "so_luong_de_xuat": 10} for m in ma_hang],
			dat_ngoai=dat_ngoai or [], ly_do_yeu_cau="Hết hàng trong kho khoa",
			ghi_chu="giao buổi sáng",
		)
		return ten

	def _gio_tron(self, rid):
		return dict(
			items=json.dumps([{"item_code": self.co_gia, "qty": 2},
			                  {"item_code": self.chua_gia, "qty": 10}]),
			request_id=rid,
		)

	def test_chia_dong(self):
		a, b = tach_phieu.chia_dong(
			self.kh_a, [{"item_code": self.co_gia}, {"item_code": self.chua_gia}]
		)
		self.assertEqual([d["item_code"] for d in a], [self.co_gia])
		self.assertEqual([d["item_code"] for d in b], [self.chua_gia])

	def test_chia_dong_chuan_hoa_ma_hang_truoc_khi_hoi_gia(self):
		"""`tabItem` so không phân biệt hoa/thường và bỏ khoảng trắng cuối;
		`dat_hang.tao_sales_order` chuẩn hoá mã TRƯỚC khi hỏi giá. Phép chia
		phải hỏi cùng câu, nếu không một dòng CÓ giá gõ lệch hoa/thường bị
		xếp nhầm sang nhóm chờ báo giá và giỏ bị tách oan."""
		lech = self.co_gia.lower() + " "
		a, b = tach_phieu.chia_dong(self.kh_a, [{"item_code": lech}])
		self.assertEqual([d["item_code"] for d in a], [lech])   # giữ nguyên dict vào
		self.assertEqual(b, [])

	def test_phieu_chi_co_gia_khong_tach(self):
		kq = de_xuat.de_xuat_gui_duyet(self._phieu_nhap([self.co_gia]))
		self.assertIsNone(kq["phieu_cung_lan_dat"])
		self.assertFalse(frappe.db.get_value(DT, kq["name"], "ma_lan_dat"))

	def test_phieu_chi_cho_bao_gia_khong_tach(self):
		kq = de_xuat.de_xuat_gui_duyet(self._phieu_nhap([self.chua_gia]))
		self.assertIsNone(kq["phieu_cung_lan_dat"])

	def test_phieu_tron_tach_thanh_hai(self):
		ten = self._phieu_nhap([self.co_gia, self.chua_gia])
		kq = de_xuat.de_xuat_gui_duyet(ten)
		frappe.set_user("Administrator")
		a = frappe.get_doc(DT, kq["name"])
		b = frappe.get_doc(DT, kq["phieu_cung_lan_dat"])
		self.assertEqual(a.name, ten)
		self.assertEqual(kq["ma_de_xuat"], a.ma_de_xuat)
		self.assertEqual([r.item_code for r in a.items], [self.co_gia])
		self.assertEqual([r.item_code for r in b.items], [self.chua_gia])
		self.assertEqual(a.trang_thai, "Chờ duyệt")
		self.assertEqual(b.trang_thai, "Chờ duyệt")
		self.assertTrue(a.ma_lan_dat)
		self.assertEqual(a.ma_lan_dat, b.ma_lan_dat)
		self.assertEqual(a.phieu_cung_lan_dat, b.name)
		self.assertEqual(b.phieu_cung_lan_dat, a.name)
		self.assertTrue(b.ma_de_xuat)
		self.assertNotEqual(a.ma_de_xuat, b.ma_de_xuat)
		self.assertEqual(a.owner, self.user_a)
		for f in ("khoa_phong", "ly_do_yeu_cau", "ghi_chu", "owner"):
			self.assertEqual(a.get(f), b.get(f), f)
		self.assertEqual(float(b.items[0].so_luong_de_xuat), 10.0)
		self.assertEqual(a.items[0].nguon_gia, "Bảng giá")
		self.assertEqual(b.items[0].nguon_gia, "Chờ báo giá")

	def test_hang_go_tay_di_theo_phieu_cho_bao_gia(self):
		ten = self._phieu_nhap(
			[self.co_gia],
			dat_ngoai=[{"ten_hang": "Kim luồn X", "dvt": "Cái", "so_luong": 5,
			            "khong_co_anh": 1}],
		)
		kq = de_xuat.de_xuat_gui_duyet(ten)
		frappe.set_user("Administrator")
		a = frappe.get_doc(DT, kq["name"])
		b = frappe.get_doc(DT, kq["phieu_cung_lan_dat"])
		self.assertEqual(len(a.dat_ngoai), 0)
		self.assertEqual(len(b.dat_ngoai), 1)
		self.assertEqual(len(b.items), 0)

	def test_anh_cua_hang_go_tay_di_theo_sang_phieu_moi(self):
		"""Ảnh đính vào PHIẾU (không vào dòng con), và `portal_dat_ngoai_xem_
		anh` chỉ phục vụ ảnh đính đúng phiếu đang xem. Dòng gõ tay chuyển
		sang phiếu mới mà tệp ở lại phiếu gốc thì quản lý mở phiếu mới không
		xem được ảnh nào."""
		from frappe.utils.file_manager import save_file

		ten = self._phieu_nhap(
			[self.co_gia],
			dat_ngoai=[{"ten_hang": "Kim luồn X", "dvt": "Cái", "so_luong": 5}],
		)
		frappe.set_user("Administrator")
		f = save_file(
			f"cr03_tach_{frappe.generate_hash(length=6)}.png",
			b"\x89PNG\r\n\x1a\n_test_tach_" + ten.encode(),
			DT, ten, is_private=1,
		)
		dong = frappe.get_doc(DT, ten).dat_ngoai[0].name
		frappe.db.set_value(
			"Sales Order Dat Ngoai Item", dong, "anh", frappe.as_json([f.file_url])
		)
		frappe.set_user(self.user_a)
		kq = de_xuat.de_xuat_gui_duyet(ten)
		moi = kq["phieu_cung_lan_dat"]
		self.assertTrue(moi)
		portal.portal_dat_ngoai_xem_anh(moi, f.file_url)   # không ném
		self.assertTrue(frappe.local.response.get("filecontent"))
		frappe.set_user("Administrator")
		self.assertEqual(
			frappe.db.get_value("File", f.name, "attached_to_name"), moi
		)

	def test_loi_khi_gui_phieu_thu_hai_khong_de_lai_gi(self):
		ten = self._phieu_nhap(
			[self.co_gia],
			# Thiếu ảnh và không tích "không chụp được" → `gui_duyet` ném lỗi.
			dat_ngoai=[{"ten_hang": "Kim luồn X", "dvt": "Cái", "so_luong": 5}],
		)
		truoc = frappe.db.count(DT, {"customer": self.kh_a})
		# Savepoint, KHÔNG `frappe.db.rollback()` trần: rollback trần cuốn
		# luôn fixture của cả class (FrappeTestCase chạy trong một giao dịch).
		# Trong request thật, Frappe rollback toàn bộ khi endpoint ném lỗi.
		frappe.db.savepoint("truoc_gui")
		with self.assertRaises(frappe.ValidationError):
			de_xuat.de_xuat_gui_duyet(ten)
		frappe.db.rollback(save_point="truoc_gui")
		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.count(DT, {"customer": self.kh_a}), truoc)
		self.assertEqual(frappe.db.get_value(DT, ten, "trang_thai"), "Nháp")

	def test_loi_cua_phieu_thu_hai_bi_bat_truoc_khi_ghi_bat_cu_thu_gi(self):
		"""Cùng ca trên nhưng KHÔNG rollback: phép kiểm của nhóm chờ báo giá
		chạy TRƯỚC mọi lần ghi, nên ngay cả khi người gọi không rollback thì
		phiếu gốc vẫn nguyên dòng và chưa tiêu số nào trong dãy mã."""
		ten = self._phieu_nhap(
			[self.co_gia],
			dat_ngoai=[{"ten_hang": "Kim luồn X", "dvt": "Cái", "so_luong": 5}],
		)
		truoc = frappe.db.count(DT, {"customer": self.kh_a})
		with self.assertRaises(frappe.ValidationError):
			de_xuat.de_xuat_gui_duyet(ten)
		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.count(DT, {"customer": self.kh_a}), truoc)
		doc = frappe.get_doc(DT, ten)
		self.assertEqual(doc.trang_thai, "Nháp")
		self.assertFalse(doc.ma_de_xuat)
		self.assertEqual(len(doc.items), 1)
		self.assertEqual(len(doc.dat_ngoai), 1)

	def test_gui_lai_sau_thu_hoi_khong_tach_du_phieu_da_thanh_tron(self):
		"""Ruling R6 — chỉ tách ở lần gửi duyệt ĐẦU TIÊN. Phiếu đã có mã là
		phiếu quản lý và khoa đã gọi tên; gửi lại không được đẻ thêm phiếu."""
		ten = self._phieu_nhap([self.co_gia])
		lan1 = de_xuat.de_xuat_gui_duyet(ten)
		self.assertIsNone(lan1["phieu_cung_lan_dat"])
		de_xuat.de_xuat_thu_hoi(ten)
		de_xuat.de_xuat_luu_nhap(ten, items=[
			{"item_code": self.co_gia, "so_luong_de_xuat": 10},
			{"item_code": self.chua_gia, "so_luong_de_xuat": 10},
		])
		frappe.set_user("Administrator")
		truoc = frappe.db.count(DT, {"customer": self.kh_a})
		frappe.set_user(self.user_a)
		lan2 = de_xuat.de_xuat_gui_duyet(ten)
		frappe.set_user("Administrator")
		self.assertEqual(lan2["name"], ten)
		self.assertEqual(lan2["ma_de_xuat"], lan1["ma_de_xuat"])
		self.assertIsNone(lan2["phieu_cung_lan_dat"])
		self.assertEqual(frappe.db.count(DT, {"customer": self.kh_a}), truoc)
		doc = frappe.get_doc(DT, ten)
		self.assertEqual(doc.trang_thai, "Chờ duyệt")
		self.assertEqual(
			sorted(r.item_code for r in doc.items), sorted([self.co_gia, self.chua_gia])
		)
		self.assertFalse(doc.ma_lan_dat)
		self.assertFalse(doc.phieu_cung_lan_dat)

	def test_quan_ly_dat_gio_tron_ra_hai_don(self):
		frappe.set_user(self.quan_ly)
		rid = frappe.generate_hash(length=12)
		kq = portal.portal_order_place(**self._gio_tron(rid))
		self.assertEqual([d["loai_don"] for d in kq["don"]], ["Theo bảng giá", "Mua lẻ"])
		self.assertEqual(kq["sales_order"], kq["don"][0]["sales_order"])
		self.assertEqual(kq["de_xuat"], kq["don"][0]["de_xuat"])
		for khoa in ("da_ton_tai", "total"):
			self.assertIn(khoa, kq)
		frappe.set_user("Administrator")
		a, b = (frappe.get_doc(DT, d["de_xuat"]) for d in kq["don"])
		self.assertTrue(a.ma_lan_dat)
		self.assertEqual(a.ma_lan_dat, b.ma_lan_dat)
		self.assertEqual(a.phieu_cung_lan_dat, b.name)
		self.assertEqual(b.phieu_cung_lan_dat, a.name)
		self.assertEqual([r.item_code for r in a.items], [self.co_gia])
		self.assertEqual([r.item_code for r in b.items], [self.chua_gia])
		self.assertEqual(
			[frappe.db.get_value("Sales Order", d["sales_order"], "custom_request_id")
			 for d in kq["don"]],
			[f"{rid}:gia", f"{rid}:baogia"],
		)

	def test_quan_ly_gui_lai_cung_request_id_khong_sinh_don_thu_ba(self):
		frappe.set_user(self.quan_ly)
		rid = frappe.generate_hash(length=12)
		tham_so = self._gio_tron(rid)
		lan1 = portal.portal_order_place(**tham_so)
		so_don = frappe.db.count("Sales Order", {"customer": self.kh_a})
		so_phieu = frappe.db.count(DT, {"customer": self.kh_a})
		lan2 = portal.portal_order_place(**tham_so)
		self.assertEqual(
			[d["sales_order"] for d in lan1["don"]],
			[d["sales_order"] for d in lan2["don"]],
		)
		self.assertEqual(
			[d["de_xuat"] for d in lan1["don"]], [d["de_xuat"] for d in lan2["don"]],
		)
		self.assertTrue(all(d["de_xuat"] for d in lan2["don"]))
		self.assertTrue(lan2["da_ton_tai"])
		self.assertEqual(frappe.db.count("Sales Order", {"customer": self.kh_a}), so_don)
		self.assertEqual(frappe.db.count(DT, {"customer": self.kh_a}), so_phieu)

	def test_quan_ly_gui_lai_sau_khi_gia_doi_van_tra_dung_hai_don_cu(self):
		"""Lần bấm lại không được chia giỏ theo Price List HIỆN TẠI: mặt hàng
		chờ báo giá vừa có giá giữa hai lần bấm thì giỏ thành "một loại", và
		`request_id` trần sẽ đẻ ra đơn thứ ba."""
		frappe.set_user(self.quan_ly)
		rid = frappe.generate_hash(length=12)
		tham_so = self._gio_tron(rid)
		lan1 = portal.portal_order_place(**tham_so)
		frappe.set_user("Administrator")
		self._tao_gia(self.chua_gia, self.price_list, 9000)
		so_don = frappe.db.count("Sales Order", {"customer": self.kh_a})
		frappe.set_user(self.quan_ly)
		lan2 = portal.portal_order_place(**tham_so)
		self.assertEqual(
			[d["sales_order"] for d in lan1["don"]],
			[d["sales_order"] for d in lan2["don"]],
		)
		self.assertEqual(frappe.db.count("Sales Order", {"customer": self.kh_a}), so_don)

	def test_quan_ly_dat_gio_mot_loai_giu_nguyen_request_id(self):
		frappe.set_user(self.quan_ly)
		rid = frappe.generate_hash(length=12)
		kq = portal.portal_order_place(
			items=json.dumps([{"item_code": self.co_gia, "qty": 2}]), request_id=rid,
		)
		self.assertEqual(len(kq["don"]), 1)
		self.assertEqual(
			frappe.db.get_value("Sales Order", kq["sales_order"], "custom_request_id"), rid
		)
		self.assertFalse(frappe.db.get_value(DT, kq["de_xuat"], "ma_lan_dat"))
		self.assertFalse(frappe.db.get_value(DT, kq["de_xuat"], "phieu_cung_lan_dat"))

	def test_quan_ly_dat_gio_tron_thieu_request_id_bi_tu_choi_nhu_gio_mot_loai(self):
		"""Thiếu `request_id` thì `dat_hang.tao_sales_order` từ chối (BR-O12).
		Giỏ trộn không được biến `None` thành `"None:gia"` rồi đi lọt."""
		frappe.set_user(self.quan_ly)
		so_don = frappe.db.count("Sales Order", {"customer": self.kh_a})
		tham_so = self._gio_tron(None)
		with self.assertRaises(frappe.ValidationError):
			portal.portal_order_place(**tham_so)
		self.assertEqual(frappe.db.count("Sales Order", {"customer": self.kh_a}), so_don)
		self.assertFalse(frappe.db.exists(
			"Sales Order", {"custom_request_id": ["like", "None:%"]}
		))


for _ten, _ham in vars(goc.TestPortalCatalogGop).items():
	if _ten.startswith("_") and not _ten.startswith("__") and callable(_ham):
		if _ten not in vars(TestTachPhieu):
			setattr(TestTachPhieu, _ten, _ham)
