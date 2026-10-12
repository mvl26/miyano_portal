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
