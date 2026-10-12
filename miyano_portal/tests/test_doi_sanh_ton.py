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

	def _bo(self, thanh_phan, sl=2):
		"""Product Bundle: một mã gộp (không quản lý tồn) gồm `sl` thành phần."""
		cha = self._item(quan_ly_ton=False)
		frappe.get_doc({
			"doctype": "Product Bundle", "new_item_code": cha,
			"items": [{"item_code": thanh_phan, "qty": sl}],
		}).insert(ignore_permissions=True)
		return cha

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

	def test_don_khac_da_giu_thi_co_ghi_chu_so_da_giu(self):
		"""Tồn 10, đơn A và đơn B cùng cần 7 và cùng đã Submit: mỗi đơn thấy
		thiếu 4. Không có ghi chú này thì nhân viên không biết vì sao "tồn có
		thể sử dụng" thấp hơn tồn hiện tại, và lập hai MR cho cùng một chỗ
		thiếu."""
		item = self._item()
		self._nap(item, 10)
		self._don([(item, 7)])
		d = self._dong_dau(self._don([(item, 7)]))
		self.assertEqual(d["sl_thieu"], 4)
		self.assertEqual(d["giu_don_khac"], 7)

	def test_khong_don_nao_giu_thi_ghi_chu_la_None(self):
		item = self._item()
		self._nap(item, 10)
		d = self._dong_dau(self._don([(item, 7)]))
		self.assertIsNone(d["giu_don_khac"])

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
		khoi = self.js[self.js.index("const VAI_XEM_TON = ["):]
		khoi = khoi[: khoi.index("];")]
		import re
		self.assertEqual(set(re.findall(r'"([^"]+)"', khoi)), set(dst.ROLE_NOI_BO))

	def test_js_xu_du_bon_ma_de_xuat(self):
		for ma in (dst.DX_DU, dst.DX_CAN_MUA, dst.DX_MOT_PHAN, dst.DX_DA_CO_MR):
			self.assertIn(f"{ma}:", self.js, ma)

	def test_bang_nam_duoi_luoi_mat_hang_KHONG_nam_trong_dashboard(self):
		"""Form Sales Order chia tab, và mọi khối `frm.dashboard.add_section`
		nằm trong tab "Connections": đặt bảng ở đó thì mở đơn ra KHÔNG THẤY
		bảng. Lỗi này chỉ lộ khi mở trình duyệt thật (12/10/2026) — mọi test
		khác vẫn xanh."""
		moi = self.js[self.js.index("// Đối sánh tồn kho của MIYANO"):]
		self.assertNotIn("dashboard.add_section(", moi)
		self.assertIn("frm.fields_dict.items", moi)

	def test_bang_cu_duoc_go_TRUOC_moi_loi_thoat_som(self):
		"""Bảng không còn do dashboard quản, nên Frappe không tự dọn. Một form
		dùng lại cho mọi đơn: không gỡ trước thì đơn MỚI (chưa lưu) hiện bảng
		tồn của đơn vừa xem trước đó."""
		than = self.js[self.js.index("function hien_doi_sanh_ton(frm) {"):]
		self.assertLess(than.index("go_doi_sanh_ton(frm)"), than.index("frm.is_new()"))

	def test_khong_ve_bang_tren_don_da_huy_hoac_da_dong(self):
		"""Đơn đã huỷ / đã đóng không còn giao: "Thiếu k/n dòng" màu đỏ ở đó
		là một lời kêu gọi hành động sai."""
		than = self.js[self.js.index("function hien_doi_sanh_ton(frm) {"):]
		than = than[: than.index("frappe.call(")]
		self.assertIn("frm.doc.docstatus === 2", than)
		self.assertIn('frm.doc.status === "Closed"', than)

	def test_phan_hoi_cu_bi_bo_theo_so_thu_tu_lan_goi(self):
		"""Hai lần refresh sát nhau: phản hồi CHẬM của lần trước không được
		thêm lại nút "Tạo MR" mà lần sau đã cho là không còn."""
		than = self.js[self.js.index("function hien_doi_sanh_ton(frm) {"):]
		self.assertIn("frm._dst_lan", than)
		self.assertIn("lan !== frm._dst_lan", than)

	def test_ve_bang_hong_thi_van_con_dong_bao_loi(self):
		than = self.js[self.js.index("function hien_doi_sanh_ton(frm) {"):]
		than = than[: than.index("function ve_doi_sanh_ton")]
		self.assertIn("try {", than)
		self.assertIn("catch (e)", than)

	def test_js_hien_ghi_chu_bo_trong_don(self):
		self.assertIn("d.bo_trong_don", self.js)

	def test_js_hien_ghi_chu_don_khac_da_giu(self):
		self.assertIn("d.giu_don_khac", self.js)
		self.assertIn("Đơn khác đã giữ", self.js)

	def test_cong_khach_hang_KHONG_goi_doi_sanh_ton(self):
		"""Spec Q4: tồn của Miyano không được lộ sang cổng khách hàng."""
		src = self.goc_repo / "frontend" / "src"
		self.assertTrue(src.is_dir(), src)  # không có thư mục thì bài này xanh giả
		for f in list(src.rglob("*.vue")) + list(src.rglob("*.js")):
			self.assertNotIn(
				"doi_sanh_ton", f.read_text(encoding="utf-8"), str(f)
			)


class TestTaoMrDongThoi(_CoSo):
	"""Hai người cùng mở một đơn thiếu và cùng bấm "Tạo MR".

	CSDL chạy REPEATABLE READ: yêu cầu thứ hai đã mở ảnh chụp dữ liệu TRƯỚC
	khi xếp hàng ở khoá dòng đơn, nên một SELECT thường sau khoá vẫn không
	thấy MR nháp yêu cầu thứ nhất vừa tạo. Chỉ ĐỌC CÓ KHOÁ mới thấy dữ liệu
	đã commit mới nhất. Không dựng được hai giao dịch thật trong một test,
	nên canh đúng hai điều làm nên cái khoá.
	"""

	def test_duong_tao_mr_doc_do_phu_bang_truy_van_CO_KHOA(self):
		item = self._item()
		so = self._don([(item, 3)])
		cau = []
		goc = frappe.db.sql

		def ghi(query, *a, **kw):
			cau.append(" ".join(str(query).lower().split()))
			return goc(query, *a, **kw)

		with unittest.mock.patch.object(frappe.db, "sql", side_effect=ghi):
			dst.tao_mr_phan_thieu(so.name)
		doc_mr = [c for c in cau if "from `tabmaterial request item` mri" in c]
		self.assertTrue(doc_mr)
		self.assertTrue(all(c.endswith("for update") for c in doc_mr), doc_mr)

	def test_duong_xem_bang_KHONG_khoa(self):
		"""Mở form chỉ để xem thì không được giữ khoá dòng nào."""
		item = self._item()
		so = self._don([(item, 3)])
		dst.tao_mr_phan_thieu(so.name)
		cau = []
		goc = frappe.db.sql

		def ghi(query, *a, **kw):
			cau.append(" ".join(str(query).lower().split()))
			return goc(query, *a, **kw)

		with unittest.mock.patch.object(frappe.db, "sql", side_effect=ghi):
			dst.doi_sanh_ton(so.name)
		self.assertFalse([c for c in cau if c.endswith("for update")])

	def test_trang_thai_don_duoc_doc_lai_SAU_khoa(self):
		"""Đơn bị đóng trong lúc chờ khoá thì không sinh MR: trạng thái phải
		đọc lại từ CSDL, không lấy từ bản đã nạp trước khi khoá."""
		item = self._item()
		so = self._don([(item, 3)])
		goc = frappe.get_doc

		def nap_ban_cu(*a, **kw):
			doc = goc(*a, **kw)
			if doc.doctype == "Sales Order":
				# Sau khi bản này được nạp, người khác đóng đơn.
				frappe.db.set_value(
					"Sales Order", doc.name, "status", "Closed",
					update_modified=False,
				)
			return doc

		with unittest.mock.patch.object(frappe, "get_doc", side_effect=nap_ban_cu):
			with self.assertRaises(frappe.ValidationError) as ca:
				dst.tao_mr_phan_thieu(so.name)
		# Phải là chốt CỦA MÌNH chặn, không phải may nhờ một kiểm tra nào đó
		# của ERPNext chạy muộn hơn trong `mr.insert()`.
		self.assertIn("đã đóng", str(ca.exception))
		self.assertFalse(
			frappe.db.exists("Material Request Item", {"sales_order": so.name})
		)


class TestTaoMrHaiDongCungMatHang(_CoSo):
	def setUp(self):
		super().setUp()
		cu = frappe.db.get_single_value("Buying Settings", "allow_multiple_items")
		self.addCleanup(
			frappe.db.set_single_value, "Buying Settings", "allow_multiple_items", cu
		)

	def test_cho_phep_trung_mat_hang_thi_moi_dong_don_mot_dong_mr(self):
		frappe.db.set_single_value("Buying Settings", "allow_multiple_items", 1)
		item = self._item()
		so = self._don([(item, 2), (item, 3)])
		kq = dst.tao_mr_phan_thieu(so.name)
		mr = frappe.get_doc("Material Request", kq["name"])
		self.assertEqual([r.qty for r in mr.items], [2, 3])
		self.assertEqual(
			[r.sales_order_item for r in mr.items], [r.name for r in so.items]
		)

	def test_khong_cho_phep_thi_bao_ro_bang_tieng_Viet_va_khong_tao_gi(self):
		"""Không báo trước thì người dùng nhận câu lỗi tiếng Anh của ERPNext
		("Same item cannot be entered multiple times") và không biết sửa ở
		đâu."""
		frappe.db.set_single_value("Buying Settings", "allow_multiple_items", 0)
		item = self._item()
		so = self._don([(item, 2), (item, 3)])
		with self.assertRaises(frappe.ValidationError) as ca:
			dst.tao_mr_phan_thieu(so.name)
		self.assertIn("Buying Settings", str(ca.exception))
		self.assertIn("cùng một mặt hàng", str(ca.exception))
		self.assertFalse(
			frappe.db.exists("Material Request Item", {"sales_order": so.name})
		)


class TestSlMua(FrappeTestCase):
	"""Đơn vị chỉ nhận số nguyên: ERPNext từ chối 2,3 Hộp trên Material
	Request. Thiếu 2,3 thì phải mua 3 — làm tròn LÊN, không bao giờ xuống."""

	def test_don_vi_nguyen_lam_tron_len(self):
		self.assertEqual(dst.sl_mua(2.3, True), 3)
		self.assertEqual(dst.sl_mua(2.0, True), 2)
		self.assertEqual(dst.sl_mua(0.001, True), 1)

	def test_don_vi_le_giu_nguyen(self):
		self.assertEqual(dst.sl_mua(2.3, False), 2.3)


class TestLoVoHieu(_CoSo):
	def test_lo_bi_vo_hieu_hoa_khong_tinh_la_dung_duoc(self):
		"""Lô bị `disabled` (cách ly, thu hồi): hàng vẫn nằm trong `Bin`
		nhưng ERPNext không cho chọn lô đó để xuất."""
		item = self._item(theo_lo=True)
		tot = self._lo(item, None)
		khoa = self._lo(item, None)
		self._nap(item, 6, lo=tot)
		self._nap(item, 4, lo=khoa)
		frappe.db.set_value("Batch", khoa, "disabled", 1)
		d = self._dong_dau(self._don([(item, 8)], submit=False))
		self.assertEqual(d["ton_hien_tai"], 10)
		self.assertEqual(d["ton_kha_dung"], 6)
		self.assertEqual(d["sl_thieu"], 2)

	def test_lo_vua_het_han_vua_vo_hieu_chi_bi_tru_MOT_lan(self):
		item = self._item(theo_lo=True)
		tot = self._lo(item, None)
		xau = self._lo(item, frappe.utils.add_days(frappe.utils.today(), 90))
		self._nap(item, 6, lo=tot)
		self._nap(item, 4, lo=xau)
		frappe.db.set_value("Batch", xau, {
			"disabled": 1,
			"expiry_date": frappe.utils.add_days(frappe.utils.today(), -1),
		})
		d = self._dong_dau(self._don([(item, 6)], submit=False))
		self.assertEqual(d["ton_kha_dung"], 6)
		self.assertEqual(d["sl_thieu"], 0)


class TestBoSanPham(_CoSo):
	def _kho_thanh_phan(self, bo):
		"""Kho ERPNext gán cho thành phần của bộ — hỏi chính ERPNext thay vì
		đoán, để bài test không gãy theo cách nó chọn kho."""
		so = self._don([(bo, 1)], submit=False)
		return so.packed_items[0].warehouse

	def test_thanh_phan_bo_cua_CHINH_DON_tru_vao_dong_le_cung_mat_hang(self):
		"""Đơn vừa có bộ (2 bộ × 2 = 4 thành phần) vừa có dòng lẻ 8 cái của
		chính thành phần đó; tồn 10. Dòng lẻ chỉ còn 6 để dùng, thiếu 2."""
		tp = self._item()
		bo = self._bo(tp, sl=2)
		kho = self._kho_thanh_phan(bo)
		make_stock_entry(
			item_code=tp, qty=10, to_warehouse=kho, rate=1000,
			company=COMPANY, purpose="Material Receipt",
		)
		so = self._don(
			[(bo, 2), {"item_code": tp, "qty": 8, "warehouse": kho}], submit=False
		)
		dong = {d["item_code"]: d for d in self._bang(so)["dong"]}
		self.assertEqual(dong[bo]["ly_do"], dst.LY_DO_BO)
		self.assertEqual(dong[tp]["bo_trong_don"], 4)
		self.assertEqual(dong[tp]["ton_kha_dung"], 6)
		self.assertEqual(dong[tp]["sl_thieu"], 2)

	def test_don_khong_co_bo_thi_ghi_chu_la_None(self):
		item = self._item()
		self._nap(item, 5)
		self.assertIsNone(self._dong_dau(self._don([(item, 1)], submit=False))["bo_trong_don"])

	def test_nhanh_Packed_Item_cua_ban_sao_khop_ham_goc(self):
		"""Ghim NHÁNH THỨ HAI của bản sao `get_reserved_qty` (Packed Item) —
		bài `…khop_dung_ham_goc…` ở trên chỉ ghim nhánh dòng đơn thường."""
		tp = self._item()
		bo = self._bo(tp, sl=2)
		kho = self._kho_thanh_phan(bo)
		make_stock_entry(
			item_code=tp, qty=20, to_warehouse=kho, rate=1000,
			company=COMPANY, purpose="Material Receipt",
		)
		so = self._don([(bo, 3)])
		self.assertEqual(get_reserved_qty(tp, kho), 6)
		self.assertEqual(dst._giu_cho_don_khac(tp, kho, tru_don=""), 6)
		self.assertEqual(dst._giu_cho_don_khac(tp, kho, tru_don=so.name), 0)


class TestKhopHamGocSauGiaoHang(_CoSo):
	def test_sau_khi_giao_mot_phan_van_khop(self):
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
		self.assertEqual(get_reserved_qty(item, KHO_MYN), 6)
		self.assertEqual(dst._giu_cho_don_khac(item, KHO_MYN, tru_don=""), 6)


class TestTaoMrBoSung(_CoSo):
	def test_chi_nhan_POST(self):
		"""Endpoint GHI dữ liệu. Frappe tình cờ rollback mọi GET, nhưng đó
		không phải thứ nên đứng ra bảo vệ một endpoint tạo chứng từ."""
		self.assertEqual(
			frappe.allowed_http_methods_for_whitelisted_func[dst.tao_mr_phan_thieu],
			["POST"],
		)

	def test_don_dang_tam_giu_khong_tao_duoc_mr(self):
		item = self._item()
		so = self._don([(item, 3)])
		so.update_status("On Hold")
		with self.assertRaises(frappe.ValidationError) as ca:
			dst.tao_mr_phan_thieu(so.name)
		self.assertIn("tạm giữ", str(ca.exception))

	def test_dong_khong_tra_duoc_KHONG_vao_mr(self):
		"""Spec §10.9, đi qua đúng đường tạo MR chứ không chỉ hàm thuần."""
		thieu = self._item()
		dich_vu = self._item(quan_ly_ton=False)
		so = self._don([(dich_vu, 1), (thieu, 3)])
		mr = frappe.get_doc("Material Request", dst.tao_mr_phan_thieu(so.name)["name"])
		self.assertEqual([r.item_code for r in mr.items], [thieu])

	def test_don_vi_nguyen_thi_mua_lam_tron_len(self):
		item = self._item()
		self._nap(item, 0.5)  # nhập khi đơn vị còn cho số lẻ
		frappe.db.set_value("UOM", "Hộp", "must_be_whole_number", 1)
		so = self._don([(item, 3)])
		self.assertEqual(self._dong_dau(so)["can_mua"], 2.5)
		mr = frappe.get_doc("Material Request", dst.tao_mr_phan_thieu(so.name)["name"])
		self.assertEqual(mr.items[0].qty, 3)
		# MR 3 phủ trọn 2,5 thiếu: không còn gì để mua thêm.
		d = self._dong_dau(so)
		self.assertEqual(d["de_xuat"], dst.DX_DA_CO_MR)
		self.assertEqual(d["can_mua"], 0)

	def test_duong_that_MR_sang_PO_sang_nhap_kho(self):
		"""Đi hết đường thật: MR -> Purchase Order -> Purchase Receipt.

		Ghim hai điều mới chỉ được kiểm bằng `db.set_value`: MR do mình dựng
		chuyển được thành PO bình thường, và `received_qty` ERPNext ghi lên
		dòng MR đúng là theo đơn vị tồn kho — hàng về thì MR thôi phủ và dòng
		chuyển sang "Đủ hàng".
		"""
		from erpnext.buying.doctype.purchase_order.purchase_order import (
			make_purchase_receipt,
		)
		from erpnext.stock.doctype.material_request.material_request import (
			make_purchase_order,
		)

		ncc = frappe.get_all("Supplier", filters={"disabled": 0}, pluck="name", limit=1)[0]
		item = self._item()
		so = self._don([(item, 5)])
		mr = frappe.get_doc("Material Request", dst.tao_mr_phan_thieu(so.name)["name"])
		mr.submit()

		po = make_purchase_order(mr.name)
		po.supplier = ncc
		po.schedule_date = frappe.utils.today()
		for r in po.items:
			r.rate = 1000
			r.schedule_date = frappe.utils.today()
		po.insert(ignore_permissions=True)
		self.assertEqual(po.items[0].material_request, mr.name)
		self.assertEqual(po.items[0].sales_order, so.name)
		po.submit()

		pr = make_purchase_receipt(po.name)
		pr.insert(ignore_permissions=True)
		pr.submit()

		self.assertEqual(
			frappe.db.get_value("Material Request Item", mr.items[0].name, "received_qty"), 5
		)
		d = self._dong_dau(so)
		self.assertEqual(d["ton_hien_tai"], 5)
		self.assertEqual(d["sl_thieu"], 0)
		self.assertEqual(d["de_xuat"], dst.DX_DU)
		self.assertEqual(d["mr"], [])
