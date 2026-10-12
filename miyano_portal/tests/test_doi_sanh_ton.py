"""Đối sánh tồn kho trên Sales Order và Material Request cho phần thiếu.

Spec: docs/superpowers/specs/2026-10-12-doi-sanh-ton-kho-khi-tao-so-design.md

BA ĐIỀU ĐỊNH HÌNH BỘ TEST NÀY:

1. **Đây là tồn của MIYANO (`Bin`), không phải tồn của bệnh viện** (CR-04,
   `kho/can_cu_duyet.py`). Hai nguồn, hai người đọc.

2. **Không tra được thì trả `None`, KHÔNG trả 0.** "Tồn 0" nghĩa là hết hàng.

3. **Tài khoản cổng khách hàng ĐỌC ĐƯỢC đơn của chính họ**, nên chốt quyền
   phải là danh sách vai nội bộ — kiểm "đọc được Sales Order" là để lọt đúng
   người cần chặn.
"""

import unittest.mock
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import doi_sanh_ton as dst
from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry
from erpnext.stock.stock_balance import get_reserved_qty

from miyano_portal.setup.seed_kho_demo import seed_kho_demo

COMPANY = "Miyano Việt Nam"
KHO_MYN = "Kho Miyano - MYN"
COST_CENTER = "Main - MYN"
KHACH = "Bệnh viện Bạch Mai"

# `seed_demo()` tạo tài khoản cổng này cho đúng Customer KHACH (vai "Customer").
BM_USER = "bvbm@demo.miyano"
SALES_USER = "sales_user@demo.miyano"


class _CoSo(FrappeTestCase):
	"""Dựng dữ liệu chung. Mỗi test tự tạo MẶT HÀNG MỚI (`_TEST DST-…`):
	`erptest.local` có sẵn tồn và đơn cũ, dùng lại mặt hàng demo thì số tồn
	và số "đã giữ cho đơn khác" không còn là số test tự đặt ra."""

	def setUp(self):
		frappe.set_user("Administrator")
		seed_kho_demo()

	def tearDown(self):
		frappe.set_user("Administrator")

	def _item(self, theo_lo=False, quan_ly_ton=True, uoms=None):
		ma = "_TEST DST-" + frappe.generate_hash(length=8)
		frappe.get_doc({
			"doctype": "Item", "item_code": ma,
			"item_name": "Vật tư test đối sánh tồn",
			"item_group": frappe.get_all(
				"Item Group", filters={"is_group": 0}, pluck="name"
			)[0],
			"stock_uom": "Hộp", "is_stock_item": int(quan_ly_ton),
			"has_batch_no": int(theo_lo), "create_new_batch": 0,
			"uoms": uoms or [],
		}).insert(ignore_permissions=True)
		return ma

	def _nap(self, item, qty, lo=None):
		make_stock_entry(
			item_code=item, qty=qty, to_warehouse=KHO_MYN, rate=1000,
			batch_no=lo, company=COMPANY, purpose="Material Receipt",
		)

	def _lo(self, item, han):
		ten = "_TEST DST-LO-" + frappe.generate_hash(length=8)
		frappe.get_doc({
			"doctype": "Batch", "batch_id": ten, "item": item, "expiry_date": han,
		}).insert(ignore_permissions=True)
		return ten

	def _don(self, dong, submit=True):
		"""`dong`: `[(item_code, qty), ...]` hoặc dict dòng đầy đủ."""
		ngay = frappe.utils.add_days(frappe.utils.today(), 2)
		so = frappe.new_doc("Sales Order")
		so.customer = KHACH
		so.company = COMPANY
		so.transaction_date = frappe.utils.today()
		so.delivery_date = ngay
		for d in dong:
			if not isinstance(d, dict):
				d = {"item_code": d[0], "qty": d[1]}
			so.append("items", {
				"rate": 1000, "warehouse": KHO_MYN, "delivery_date": ngay, **d,
			})
		so.insert(ignore_permissions=True)
		if submit:
			so.submit()
		return so

	def _bang(self, so):
		return dst.bang_cho_don(frappe.get_doc("Sales Order", so.name))

	def _dong_dau(self, so):
		return self._bang(so)["dong"][0]


class TestSlConGiao(FrappeTestCase):
	def test_chua_giao_gi_thi_bang_stock_qty(self):
		self.assertEqual(dst.sl_con_giao(stock_qty=20, qty=2, delivered_qty=0), 20)

	def test_giao_mot_phan_chi_con_phan_chua_giao(self):
		"""2 Thùng = 20 Hộp, đã giao 0,5 Thùng -> còn 15 Hộp."""
		self.assertEqual(dst.sl_con_giao(stock_qty=20, qty=2, delivered_qty=0.5), 15)

	def test_giao_thua_khong_ra_so_am(self):
		self.assertEqual(dst.sl_con_giao(stock_qty=10, qty=10, delivered_qty=12), 0)

	def test_qty_bang_0_khong_chia(self):
		self.assertEqual(dst.sl_con_giao(stock_qty=0, qty=0, delivered_qty=0), 0)


class TestTonKhaDung(FrappeTestCase):
	def test_khong_co_lo_het_han_thi_chi_tru_phan_da_giu(self):
		self.assertEqual(dst.ton_kha_dung(100, 0, 30), 70)

	def test_tru_lo_het_han_roi_tru_phan_da_giu(self):
		"""Tồn 100, trong đó 40 đã hết hạn; đơn khác giữ 10."""
		self.assertEqual(dst.ton_kha_dung(100, 40, 10), 50)

	def test_moi_lo_deu_het_han_thi_ve_0(self):
		self.assertEqual(dst.ton_kha_dung(100, 100, 0), 0)

	def test_don_khac_giu_nhieu_hon_ton_thi_ve_0_khong_am(self):
		self.assertEqual(dst.ton_kha_dung(4, 0, 10), 0)


class TestChiaTon(FrappeTestCase):
	def test_hai_dong_cung_mat_hang_chia_nhau_mot_luong_ton(self):
		"""Tồn 10, hai dòng mỗi dòng 6: dòng sau chỉ thấy 4 còn lại.

		Không có bài này thì hai dòng cùng báo "đủ" trên cùng 10 cái.
		"""
		k = ("A", "Kho 1")
		kq = dst.chia_ton([(k, 6), (k, 6)], {k: 10})
		self.assertEqual(kq, [(10, 0), (4, 2)])

	def test_khac_kho_thi_khong_chia_nhau(self):
		k1, k2 = ("A", "Kho 1"), ("A", "Kho 2")
		kq = dst.chia_ton([(k1, 6), (k2, 6)], {k1: 10, k2: 1})
		self.assertEqual(kq, [(10, 0), (1, 5)])

	def test_khong_sua_dict_dau_vao(self):
		k = ("A", "Kho 1")
		nguon = {k: 10}
		dst.chia_ton([(k, 6)], nguon)
		self.assertEqual(nguon, {k: 10})


class TestDeXuat(FrappeTestCase):
	def test_du_hang(self):
		self.assertEqual(
			dst.de_xuat(0, 0), {"ma": dst.DX_DU, "mr_da_phu": 0, "can_mua": 0}
		)

	def test_thieu_chua_co_mr(self):
		self.assertEqual(
			dst.de_xuat(6, 0), {"ma": dst.DX_CAN_MUA, "mr_da_phu": 0, "can_mua": 6}
		)

	def test_mr_phu_mot_phan(self):
		self.assertEqual(
			dst.de_xuat(6, 4), {"ma": dst.DX_MOT_PHAN, "mr_da_phu": 4, "can_mua": 2}
		)

	def test_mr_phu_het(self):
		self.assertEqual(
			dst.de_xuat(6, 6), {"ma": dst.DX_DA_CO_MR, "mr_da_phu": 6, "can_mua": 0}
		)

	def test_mr_nhieu_hon_thieu_thi_chi_tinh_bang_phan_thieu(self):
		"""MR 10 nhưng nay chỉ còn thiếu 6: không hiện "đã có MR 10" cho 6 cái."""
		self.assertEqual(
			dst.de_xuat(6, 10), {"ma": dst.DX_DA_CO_MR, "mr_da_phu": 6, "can_mua": 0}
		)

	def test_du_hang_ma_van_con_mr_thi_van_la_du(self):
		self.assertEqual(dst.de_xuat(0, 5)["ma"], dst.DX_DU)


class TestLyDoKhongTra(FrappeTestCase):
	"""Bốn ca của spec §5.5 (ca đặt ngoài nằm ở `bang_cho_don`)."""

	TON = frappe._dict(is_stock_item=1, has_batch_no=0)

	def _dong(self, **kw):
		d = frappe._dict(item_code="A", warehouse="Kho 1", delivered_by_supplier=0)
		d.update(kw)
		return d

	def test_dong_binh_thuong_tra_duoc(self):
		self.assertIsNone(dst.ly_do_khong_tra(self._dong(), self.TON, False))

	def test_hang_khong_quan_ly_ton(self):
		khong_ton = frappe._dict(is_stock_item=0, has_batch_no=0)
		self.assertEqual(
			dst.ly_do_khong_tra(self._dong(), khong_ton, False), dst.LY_DO_KHONG_TON
		)

	def test_item_khong_con_ton_tai(self):
		self.assertEqual(
			dst.ly_do_khong_tra(self._dong(), None, False), dst.LY_DO_KHONG_TON
		)

	def test_bo_san_pham(self):
		"""Mã gộp của Product Bundle luôn là hàng KHÔNG quản lý tồn — lý do
		phải là "bộ sản phẩm", không bị ca "không quản lý tồn" che mất."""
		khong_ton = frappe._dict(is_stock_item=0, has_batch_no=0)
		self.assertEqual(
			dst.ly_do_khong_tra(self._dong(), khong_ton, True), dst.LY_DO_BO
		)

	def test_giao_thang(self):
		self.assertEqual(
			dst.ly_do_khong_tra(self._dong(delivered_by_supplier=1), self.TON, False),
			dst.LY_DO_GIAO_THANG,
		)

	def test_khong_co_kho(self):
		self.assertEqual(
			dst.ly_do_khong_tra(self._dong(warehouse=None), self.TON, False),
			dst.LY_DO_KHONG_KHO,
		)


class TestBangChoDon(_CoSo):
	def test_du_hang(self):
		item = self._item()
		self._nap(item, 10)
		d = self._dong_dau(self._don([(item, 4)], submit=False))
		self.assertEqual(d["sl_yeu_cau"], 4)
		self.assertEqual(d["ton_hien_tai"], 10)
		self.assertEqual(d["ton_kha_dung"], 10)
		self.assertEqual(d["sl_thieu"], 0)
		self.assertEqual(d["de_xuat"], dst.DX_DU)
		self.assertEqual(d["dvt"], "Hộp")
		self.assertIsNone(d["ly_do"])

	def test_thieu_mot_phan(self):
		item = self._item()
		self._nap(item, 4)
		d = self._dong_dau(self._don([(item, 10)], submit=False))
		self.assertEqual(d["sl_thieu"], 6)
		self.assertEqual(d["can_mua"], 6)
		self.assertEqual(d["de_xuat"], dst.DX_CAN_MUA)

	def test_mat_hang_chua_tung_nhap_kho_la_TON_0_khong_phai_gach_ngang(self):
		"""Không có dòng `Bin` nào = thật sự không có hàng, tra được hẳn hoi."""
		item = self._item()
		d = self._dong_dau(self._don([(item, 3)], submit=False))
		self.assertIsNone(d["ly_do"])
		self.assertEqual(d["ton_hien_tai"], 0)
		self.assertEqual(d["sl_thieu"], 3)

	def test_don_dang_xem_da_submit_KHONG_tu_tru_chinh_minh(self):
		"""`Bin.reserved_qty` gồm cả đơn đang xem. Trừ nhầm thì đơn tự tranh
		hàng với chính nó và luôn báo thiếu."""
		item = self._item()
		self._nap(item, 10)
		d = self._dong_dau(self._don([(item, 10)]))
		self.assertEqual(d["ton_kha_dung"], 10)
		self.assertEqual(d["sl_thieu"], 0)

	def test_don_khac_da_submit_lam_giam_ton_kha_dung(self):
		item = self._item()
		self._nap(item, 10)
		self._don([(item, 7)])
		d = self._dong_dau(self._don([(item, 5)], submit=False))
		self.assertEqual(d["ton_hien_tai"], 10)
		self.assertEqual(d["ton_kha_dung"], 3)
		self.assertEqual(d["sl_thieu"], 2)

	def test_don_nhap_khac_KHONG_tru_nhung_co_ghi_chu(self):
		item = self._item()
		self._nap(item, 10)
		self._don([(item, 7)], submit=False)
		self._don([(item, 1)], submit=False)
		d = self._dong_dau(self._don([(item, 5)], submit=False))
		self.assertEqual(d["ton_kha_dung"], 10)
		self.assertEqual(d["don_nhap_khac"], {"sl": 8, "so_don": 2})

	def test_khong_co_don_nhap_khac_thi_ghi_chu_la_None(self):
		item = self._item()
		self._nap(item, 10)
		d = self._dong_dau(self._don([(item, 5)], submit=False))
		self.assertIsNone(d["don_nhap_khac"])

	def test_giu_cho_don_khac_khop_dung_ham_goc_cua_ERPNext(self):
		"""Ghim bản sao truy vấn vào `stock_balance.get_reserved_qty`: không
		loại đơn nào thì hai hàm phải ra cùng một số."""
		item = self._item()
		self._nap(item, 20)
		self._don([(item, 7)])
		self._don([(item, 2)])
		self.assertEqual(
			dst._giu_cho_don_khac(item, KHO_MYN, tru_don=""),
			get_reserved_qty(item, KHO_MYN),
		)
		self.assertEqual(dst._giu_cho_don_khac(item, KHO_MYN, tru_don=""), 9)

	def test_hai_dong_cung_mat_hang_chia_nhau_ton(self):
		item = self._item()
		self._nap(item, 10)
		dong = self._bang(self._don([(item, 6), (item, 6)], submit=False))["dong"]
		self.assertEqual([d["ton_kha_dung"] for d in dong], [10, 4])
		self.assertEqual([d["sl_thieu"] for d in dong], [0, 2])

	def test_don_vi_ban_khac_don_vi_ton_kho(self):
		"""2 Thùng × 10 = 20 Hộp; tồn 15 Hộp -> thiếu 5 Hộp."""
		item = self._item(uoms=[{"uom": "Thùng", "conversion_factor": 10}])
		self._nap(item, 15)
		so = self._don(
			[{"item_code": item, "qty": 2, "uom": "Thùng", "conversion_factor": 10}],
			submit=False,
		)
		d = self._dong_dau(so)
		self.assertEqual(d["sl_yeu_cau"], 20)
		self.assertEqual(d["sl_thieu"], 5)
		self.assertEqual(d["dvt"], "Hộp")

	def test_don_da_giao_mot_phan_chi_tinh_phan_con_lai(self):
		item = self._item()
		self._nap(item, 10)
		so = self._don([(item, 10)])
		dn = make_delivery_note(so.name)
		dn.posting_date = frappe.utils.today()
		dn.set_posting_time = 1
		for r in dn.items:
			r.qty = 4
			r.warehouse = KHO_MYN
			r.cost_center = COST_CENTER
		dn.insert(ignore_permissions=True)
		dn.submit()
		d = self._dong_dau(so)
		self.assertEqual(d["sl_yeu_cau"], 6)
		self.assertEqual(d["ton_hien_tai"], 6)
		self.assertEqual(d["sl_thieu"], 0)

	def test_hang_khong_quan_ly_ton_hien_gach_ngang(self):
		item = self._item(quan_ly_ton=False)
		d = self._dong_dau(self._don([(item, 3)], submit=False))
		self.assertEqual(d["ly_do"], dst.LY_DO_KHONG_TON)
		for cot in ("ton_hien_tai", "ton_kha_dung", "sl_thieu", "can_mua", "de_xuat"):
			self.assertIsNone(d[cot], cot)

	def test_dong_dat_ngoai_chua_khop_ma_hien_gach_ngang(self):
		item = self._item()
		self._nap(item, 10)
		so = self._don([(item, 1)], submit=False)
		so.append("custom_dat_ngoai", {
			"ten_hang": "Kim sinh thiết ngoài danh mục", "so_luong": 3, "dvt": "Cái",
		})
		bang = dst.bang_cho_don(so)
		dn = bang["dong"][-1]
		self.assertEqual(dn["ly_do"], dst.LY_DO_DAT_NGOAI)
		self.assertEqual(dn["item_name"], "Kim sinh thiết ngoài danh mục")
		self.assertEqual(dn["sl_yeu_cau"], 3)
		self.assertIsNone(dn["ton_hien_tai"])
		self.assertIsNone(dn["so_detail"])
		# Dòng không tra được không vào số tổng kết.
		self.assertEqual(bang["tong"], {"so_dong": 1, "so_thieu": 0})

	def test_tong_ket_dem_dung_dong_thieu(self):
		a, b = self._item(), self._item()
		self._nap(a, 10)
		bang = self._bang(self._don([(a, 4), (b, 2)], submit=False))
		self.assertEqual(bang["tong"], {"so_dong": 2, "so_thieu": 1})

	def test_don_nhap_co_thieu_van_KHONG_tao_duoc_mr(self):
		item = self._item()
		bang = self._bang(self._don([(item, 2)], submit=False))
		self.assertFalse(bang["co_the_tao_mr"])

	def test_don_da_submit_co_thieu_thi_tao_duoc_mr(self):
		item = self._item()
		bang = self._bang(self._don([(item, 2)]))
		self.assertTrue(bang["co_the_tao_mr"])


class TestLoHetHan(_CoSo):
	def _hom_qua(self):
		return frappe.utils.add_days(frappe.utils.today(), -1)

	def test_lo_het_han_bi_loai_khoi_ton_kha_dung(self):
		item = self._item(theo_lo=True)
		con_han = self._lo(item, frappe.utils.add_days(frappe.utils.today(), 90))
		sap_het = self._lo(item, frappe.utils.add_days(frappe.utils.today(), 90))
		self._nap(item, 6, lo=con_han)
		self._nap(item, 4, lo=sap_het)
		# Nhập khi lô còn hạn rồi mới đẩy hạn về quá khứ: ERPNext không cho
		# nhập kho vào một lô đã hết hạn sẵn.
		frappe.db.set_value("Batch", sap_het, "expiry_date", self._hom_qua())

		d = self._dong_dau(self._don([(item, 8)], submit=False))
		self.assertEqual(d["ton_hien_tai"], 10)
		self.assertEqual(d["ton_kha_dung"], 6)
		self.assertEqual(d["sl_thieu"], 2)

	def test_lo_khong_khai_han_van_dung_duoc(self):
		item = self._item(theo_lo=True)
		khong_han = self._lo(item, None)
		self._nap(item, 5, lo=khong_han)
		d = self._dong_dau(self._don([(item, 5)], submit=False))
		self.assertEqual(d["ton_kha_dung"], 5)
		self.assertEqual(d["sl_thieu"], 0)

	def test_moi_lo_deu_het_han_thi_ton_kha_dung_0(self):
		item = self._item(theo_lo=True)
		lo = self._lo(item, frappe.utils.add_days(frappe.utils.today(), 90))
		self._nap(item, 5, lo=lo)
		frappe.db.set_value("Batch", lo, "expiry_date", self._hom_qua())
		d = self._dong_dau(self._don([(item, 2)], submit=False))
		self.assertEqual(d["ton_hien_tai"], 5)
		self.assertEqual(d["ton_kha_dung"], 0)
		self.assertEqual(d["sl_thieu"], 2)

	def test_ton_khong_co_so_lo_di_kem_VAN_tinh_la_dung_duoc(self):
		"""Mặt hàng theo lô mà tồn `Bin` không có sổ lô (dữ liệu nhập thiếu
		lô — có thật trên site thử). Không biết lô nào hết hạn thì không trừ
		gì: báo "tồn 0" ở đây là bịa ra một ca hết hàng."""
		item = self._item(theo_lo=True)
		lo = self._lo(item, frappe.utils.add_days(frappe.utils.today(), 90))
		self._nap(item, 5, lo=lo)
		with unittest.mock.patch(
			"erpnext.stock.doctype.batch.batch.get_batch_qty", return_value=[]
		):
			d = self._dong_dau(self._don([(item, 5)], submit=False))
		self.assertEqual(d["ton_kha_dung"], 5)
		self.assertEqual(d["sl_thieu"], 0)


class TestEndpointDoc(_CoSo):
	def setUp(self):
		super().setUp()
		if not frappe.db.exists("User", SALES_USER):
			frappe.get_doc({
				"doctype": "User", "email": SALES_USER, "first_name": "Sales DST",
				"send_welcome_email": 0,
			}).insert(ignore_permissions=True)
		frappe.get_doc("User", SALES_USER).add_roles("Sales User")
		self.item = self._item()
		self._nap(self.item, 4)
		self.so = self._don([(self.item, 10)])
		self.addCleanup(
			frappe.db.delete, "Error Log", {"method": ["like", "Đối sánh tồn kho:%"]}
		)

	def test_nhan_vien_ban_hang_doc_duoc(self):
		frappe.set_user(SALES_USER)
		bang = dst.doi_sanh_ton(self.so.name)
		self.assertEqual(bang["dong"][0]["sl_thieu"], 6)

	def test_tai_khoan_cong_khach_hang_bi_tu_choi_voi_DON_CUA_CHINH_HO(self):
		"""Khách đọc được Sales Order này (đơn của bệnh viện họ) — và đúng vì
		thế mà chốt phải là vai, không phải quyền đọc đơn."""
		frappe.set_user(BM_USER)
		self.assertTrue(
			frappe.has_permission("Sales Order", "read", doc=self.so.name)
		)
		with self.assertRaises(frappe.PermissionError):
			dst.doi_sanh_ton(self.so.name)

	def test_tai_khoan_cong_LO_DUOC_GAN_vai_noi_bo_van_bi_tu_choi(self):
		"""Chốt "không phải tài khoản cổng" đứng TRƯỚC chốt vai. Giả lập bằng
		cách vá `get_roles`: gán vai Desk thật cho user sẽ khiến Frappe đổi
		`user_type` của họ, không còn là ca cần canh."""
		frappe.set_user(BM_USER)
		with unittest.mock.patch.object(
			frappe, "get_roles", return_value=["Customer", "Sales User", "All"]
		):
			with self.assertRaises(frappe.PermissionError):
				dst.doi_sanh_ton(self.so.name)

	def test_nhan_vien_khong_co_quyen_tao_mr_thi_khong_thay_nut(self):
		frappe.set_user(SALES_USER)
		self.assertFalse(frappe.has_permission("Material Request", "create"))
		self.assertFalse(dst.doi_sanh_ton(self.so.name)["co_the_tao_mr"])

	def test_quan_tri_thay_nut(self):
		self.assertTrue(dst.doi_sanh_ton(self.so.name)["co_the_tao_mr"])

	def test_phep_tinh_hong_KHONG_lam_chet_form(self):
		with unittest.mock.patch.object(
			dst, "bang_cho_don", side_effect=RuntimeError("truy vấn hỏng")
		):
			kq = dst.doi_sanh_ton(self.so.name)
		self.assertEqual(list(kq), ["loi"])
		self.assertTrue(
			frappe.db.exists(
				"Error Log", {"method": "Đối sánh tồn kho: không tính được bảng"}
			)
		)

	def test_loi_QUYEN_thi_van_phai_nem_ra(self):
		"""Nuốt lỗi là để form không chết, KHÔNG phải để che lỗi quyền."""
		frappe.set_user(BM_USER)
		with unittest.mock.patch.object(
			dst, "bang_cho_don", side_effect=RuntimeError("không được tới đây")
		):
			with self.assertRaises(frappe.PermissionError):
				dst.doi_sanh_ton(self.so.name)


class TestTaoMr(_CoSo):
	def _mr_cua(self, so):
		return frappe.get_all(
			"Material Request Item",
			filters={"sales_order": so.name},
			fields=["parent", "item_code", "qty", "stock_qty", "uom", "stock_uom",
				"warehouse", "sales_order_item", "schedule_date", "docstatus"],
			order_by="idx",
		)

	def test_chi_gom_dong_thieu_dung_so_thieu_va_la_NHAP(self):
		du, thieu = self._item(), self._item()
		self._nap(du, 10)
		self._nap(thieu, 4)
		so = self._don([(du, 5), (thieu, 10)])

		kq = dst.tao_mr_phan_thieu(so.name)

		self.assertEqual(kq["so_dong"], 1)
		mr = frappe.get_doc("Material Request", kq["name"])
		self.assertEqual(mr.docstatus, 0)
		self.assertEqual(mr.material_request_type, "Purchase")
		self.assertEqual(mr.company, COMPANY)
		self.assertEqual(len(mr.items), 1)
		r = mr.items[0]
		self.assertEqual(r.item_code, thieu)
		self.assertEqual(r.qty, 6)
		self.assertEqual(r.stock_qty, 6)
		self.assertEqual(r.uom, "Hộp")
		self.assertEqual(r.warehouse, KHO_MYN)
		self.assertEqual(r.sales_order, so.name)
		self.assertEqual(r.sales_order_item, so.items[1].name)
		self.assertEqual(
			frappe.utils.getdate(r.schedule_date),
			frappe.utils.getdate(so.items[1].delivery_date),
		)

	def test_ngay_giao_da_qua_thi_ngay_can_hang_la_hom_nay(self):
		item = self._item()
		so = self._don([(item, 3)])
		frappe.db.set_value(
			"Sales Order Item", so.items[0].name, "delivery_date",
			frappe.utils.add_days(frappe.utils.today(), -5),
		)
		kq = dst.tao_mr_phan_thieu(so.name)
		mr = frappe.get_doc("Material Request", kq["name"])
		self.assertEqual(
			frappe.utils.getdate(mr.items[0].schedule_date),
			frappe.utils.getdate(frappe.utils.today()),
		)

	def test_bam_lan_hai_khong_sinh_mr_trung(self):
		item = self._item()
		so = self._don([(item, 3)])
		dst.tao_mr_phan_thieu(so.name)
		with self.assertRaises(frappe.ValidationError):
			dst.tao_mr_phan_thieu(so.name)
		self.assertEqual(len(self._mr_cua(so)), 1)
		d = self._dong_dau(so)
		self.assertEqual(d["de_xuat"], dst.DX_DA_CO_MR)
		self.assertEqual(d["mr_da_phu"], 3)
		self.assertEqual(len(d["mr"]), 1)

	def test_mr_da_huy_thi_khong_con_tinh_la_phu(self):
		item = self._item()
		so = self._don([(item, 3)])
		mr = frappe.get_doc("Material Request", dst.tao_mr_phan_thieu(so.name)["name"])
		mr.submit()
		mr.cancel()
		self.assertEqual(self._dong_dau(so)["de_xuat"], dst.DX_CAN_MUA)
		self.assertEqual(dst.tao_mr_phan_thieu(so.name)["so_dong"], 1)

	def test_mr_da_nhan_ve_kho_thi_phan_da_nhan_khong_con_la_phu(self):
		"""Cần 10, tồn 0, MR 10. Hàng về đủ rồi 6 cái bị xuất cho đơn khác:
		thiếu 6 và MR không còn phủ gì. Đếm `stock_qty` thay vì
		`stock_qty − received_qty` thì bảng nói "đã có MR" và nút biến mất."""
		item = self._item()
		so = self._don([(item, 10)])
		ten_mr = dst.tao_mr_phan_thieu(so.name)["name"]
		dong_mr = frappe.get_doc("Material Request", ten_mr).items[0].name
		frappe.db.set_value("Material Request Item", dong_mr, "received_qty", 10)
		self._nap(item, 4)  # 10 về, 6 đã đi nơi khác -> còn 4 trên kệ

		d = self._dong_dau(so)
		self.assertEqual(d["sl_thieu"], 6)
		self.assertEqual(d["mr_da_phu"], 0)
		self.assertEqual(d["de_xuat"], dst.DX_CAN_MUA)

	def test_mr_theo_so_thieu_LUC_BAM_khong_theo_luc_bang_hien(self):
		item = self._item()
		so = self._don([(item, 10)])
		self.assertEqual(self._dong_dau(so)["can_mua"], 10)
		self._nap(item, 7)  # hàng về giữa lúc xem và lúc bấm
		kq = dst.tao_mr_phan_thieu(so.name)
		self.assertEqual(
			frappe.get_doc("Material Request", kq["name"]).items[0].qty, 3
		)

	def test_mr_phu_mot_phan_thi_lan_sau_chi_tao_phan_con_lai(self):
		item = self._item()
		self._nap(item, 4)
		so = self._don([(item, 10)])
		dst.tao_mr_phan_thieu(so.name)  # MR 6
		# Đơn khác vừa Submit lấy mất 3 trong 4 cái trên kệ.
		self._don([(item, 3)])
		d = self._dong_dau(so)
		self.assertEqual(d["sl_thieu"], 9)
		self.assertEqual(d["de_xuat"], dst.DX_MOT_PHAN)
		self.assertEqual(d["can_mua"], 3)
		kq = dst.tao_mr_phan_thieu(so.name)
		self.assertEqual(
			frappe.get_doc("Material Request", kq["name"]).items[0].qty, 3
		)

	def test_don_nhap_khong_tao_duoc_mr(self):
		item = self._item()
		so = self._don([(item, 3)], submit=False)
		with self.assertRaises(frappe.ValidationError):
			dst.tao_mr_phan_thieu(so.name)
		self.assertEqual(self._mr_cua(so), [])

	def test_don_da_huy_khong_tao_duoc_mr(self):
		item = self._item()
		so = self._don([(item, 3)])
		so.cancel()
		with self.assertRaises(frappe.ValidationError):
			dst.tao_mr_phan_thieu(so.name)

	def test_don_du_hang_khong_tao_duoc_mr(self):
		item = self._item()
		self._nap(item, 10)
		so = self._don([(item, 3)])
		with self.assertRaises(frappe.ValidationError):
			dst.tao_mr_phan_thieu(so.name)

	def test_tai_khoan_cong_khach_hang_bi_tu_choi(self):
		item = self._item()
		so = self._don([(item, 3)])
		frappe.set_user(BM_USER)
		with self.assertRaises(frappe.PermissionError):
			dst.tao_mr_phan_thieu(so.name)
		frappe.set_user("Administrator")
		self.assertEqual(self._mr_cua(so), [])

	def test_nhan_vien_khong_co_quyen_tao_mr_bi_tu_choi(self):
		item = self._item()
		so = self._don([(item, 3)])
		if not frappe.db.exists("User", SALES_USER):
			frappe.get_doc({
				"doctype": "User", "email": SALES_USER, "first_name": "Sales DST",
				"send_welcome_email": 0,
			}).insert(ignore_permissions=True)
		frappe.get_doc("User", SALES_USER).add_roles("Sales User")
		frappe.set_user(SALES_USER)
		with self.assertRaises(frappe.PermissionError):
			dst.tao_mr_phan_thieu(so.name)
		frappe.set_user("Administrator")
		self.assertEqual(self._mr_cua(so), [])


class TestGiaoDienDesk(FrappeTestCase):
	"""Desk JS không có bộ chạy test trong repo này — canh bằng nội dung
	file, cùng cách `test_cr06_desk_hang_moi.py` đang làm."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Đi từ file THẬT của module, không từ `frappe.get_app_path`: khi
		# module được nối vào app bằng symlink (đang phát triển ở worktree),
		# `resolve()` dẫn về đúng cây mã chứa bản `sales_order.js` đi cùng nó.
		goc = Path(dst.__file__).resolve().parent
		cls.js = (goc / "public" / "js" / "sales_order.js").read_text(encoding="utf-8")
		cls.goc_repo = goc.parent

	def test_form_goi_dung_hai_endpoint(self):
		self.assertIn("miyano_portal.doi_sanh_ton.doi_sanh_ton", self.js)
		self.assertIn("miyano_portal.doi_sanh_ton.tao_mr_phan_thieu", self.js)

	def test_danh_sach_vai_o_js_khop_voi_python(self):
		"""Hai danh sách lệch nhau thì hoặc nhân viên không thấy bảng, hoặc
		người không có vai mở đơn là dính hộp báo lỗi quyền."""
		for vai in dst.ROLE_NOI_BO:
			self.assertIn(f'"{vai}"', self.js, vai)

	def test_js_xu_du_bon_ma_de_xuat(self):
		for ma in (dst.DX_DU, dst.DX_CAN_MUA, dst.DX_MOT_PHAN, dst.DX_DA_CO_MR):
			self.assertIn(f"{ma}:", self.js, ma)

	def test_cong_khach_hang_KHONG_goi_doi_sanh_ton(self):
		"""Spec Q4: tồn của Miyano không được lộ sang cổng khách hàng."""
		src = self.goc_repo / "frontend" / "src"
		for f in list(src.rglob("*.vue")) + list(src.rglob("*.js")):
			self.assertNotIn(
				"doi_sanh_ton", f.read_text(encoding="utf-8"), str(f)
			)
