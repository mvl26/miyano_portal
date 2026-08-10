"""Danh mục vật tư trên cổng — tạo, sửa có rào."""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.kho import vat_tu as vat_tu_mod
from miyano_portal.setup.seed_kho_demo import seed_kho_demo


class TestVatTuTao(FrappeTestCase):
	def setUp(self):
		self.kho = seed_kho_demo()
		self.kho_bm = self.kho["kho_bm"]
		self._da_tao = []

	def tearDown(self):
		for name in self._da_tao:
			if frappe.db.exists("Customer Warehouse Item", name):
				frappe.delete_doc("Customer Warehouse Item", name, force=True, ignore_permissions=True)

	def _tao(self, **kwargs):
		row = vat_tu_mod.tao(self.kho_bm, kwargs)
		self._da_tao.append(row["name"])
		return row

	def test_ma_khop_item_miyano_thi_tu_gan_item_code(self):
		# VT0005 chứ không phải MYN-*: seed_demo() (do seed_kho_demo() gọi) tạo
		# VT0005 và HC0009 trên MỌI site, còn các Item MYN-* chỉ có nếu
		# uat_scenario đã chạy — một test phụ thuộc dữ liệu ngoài phạm vi seed
		# của chính nó là test đỏ ngẫu nhiên.
		row = self._tao(ma_vat_tu="vt0005", ten_vat_tu="Găng tay khám", dvt="Cái")
		self.assertEqual(row["item_code"], "VT0005")
		# Chính tả chuẩn của Miyano, không phải cách người dùng gõ.
		self.assertEqual(row["ma_vat_tu"], "VT0005")

	def test_ma_rieng_thi_item_code_trong(self):
		row = self._tao(ma_vat_tu="BM-TU-MUA-01", ten_vat_tu="Băng ép", dvt="Cuộn")
		self.assertEqual(row["item_code"], "")

	def test_item_code_client_gui_bi_bo_qua(self):
		# HC0009 là một Item CÓ THẬT, nên nếu server nhận item_code từ client
		# thì trường này sẽ có giá trị — test bắt đúng nhánh đó, không phải bắt
		# một mã bịa mà đằng nào cũng rỗng.
		row = self._tao(
			ma_vat_tu="BM-TU-MUA-02", ten_vat_tu="Gạc", dvt="Gói", item_code="HC0009"
		)
		self.assertEqual(row["item_code"], "")

	def test_tao_trung_ma_tra_ve_vat_tu_dang_co(self):
		row = vat_tu_mod.tao(
			self.kho_bm, {"ma_vat_tu": "MYN-GLOVE-M", "ten_vat_tu": "X", "dvt": "Hộp"}
		)
		self.assertTrue(row["da_co"])
		self.assertEqual(row["name"], self.kho["vt_bm"])

	def test_thieu_ten_bi_chan(self):
		with self.assertRaises(frappe.ValidationError) as ctx:
			vat_tu_mod.tao(self.kho_bm, {"ma_vat_tu": "BM-X", "dvt": "Cái"})
		self.assertIn("Tên vật tư", str(ctx.exception))


class TestVatTuSua(FrappeTestCase):
	def setUp(self):
		self.kho = seed_kho_demo()
		self.kho_bm = self.kho["kho_bm"]
		self.vt_moi = vat_tu_mod.tao(
			self.kho_bm, {"ma_vat_tu": "BM-SUA-01", "ten_vat_tu": "Chưa phát sinh", "dvt": "Cái"}
		)["name"]

	def tearDown(self):
		if frappe.db.exists("Customer Warehouse Item", self.vt_moi):
			frappe.delete_doc("Customer Warehouse Item", self.vt_moi, force=True, ignore_permissions=True)

	def test_sua_ten_luon_duoc(self):
		row = vat_tu_mod.sua(self.kho_bm, self.kho["vt_bm"], {"ten_vat_tu": "Tên mới"})
		self.assertEqual(row["ten_vat_tu"], "Tên mới")

	def test_sua_dvt_khi_chua_phat_sinh_thi_duoc(self):
		row = vat_tu_mod.sua(self.kho_bm, self.vt_moi, {"dvt": "Hộp"})
		self.assertEqual(row["dvt"], "Hộp")

	def test_sua_dvt_khi_da_phat_sinh_bi_chan(self):
		# vt_bm đã có phát sinh? Nếu chưa, tạo một phiếu nhập đã ghi sổ trước.
		self._bao_dam_co_phat_sinh(self.kho["vt_bm"])
		with self.assertRaises(frappe.ValidationError) as ctx:
			vat_tu_mod.sua(self.kho_bm, self.kho["vt_bm"], {"dvt": "Cái"})
		self.assertIn("đã có phát sinh", str(ctx.exception))

	def test_sua_ma_khi_da_phat_sinh_bi_chan(self):
		self._bao_dam_co_phat_sinh(self.kho["vt_bm"])
		with self.assertRaises(frappe.ValidationError) as ctx:
			vat_tu_mod.sua(self.kho_bm, self.kho["vt_bm"], {"ma_vat_tu": "MA-KHAC"})
		self.assertIn("đã có phát sinh", str(ctx.exception))

	def test_tat_vat_tu_con_ton_bi_chan(self):
		self._bao_dam_co_phat_sinh(self.kho["vt_bm"])
		with self.assertRaises(frappe.ValidationError) as ctx:
			vat_tu_mod.sua(self.kho_bm, self.kho["vt_bm"], {"active": 0})
		self.assertIn("còn tồn", str(ctx.exception))

	def test_tat_vat_tu_khong_ton_thi_duoc(self):
		row = vat_tu_mod.sua(self.kho_bm, self.vt_moi, {"active": 0})
		self.assertEqual(row["active"], 0)

	def _bao_dam_co_phat_sinh(self, vat_tu):
		if vat_tu_mod.co_phat_sinh(vat_tu):
			return
		doc = frappe.get_doc({
			"doctype": "Customer Stock Receipt",
			"kho": self.kho_bm,
			"ngay": frappe.utils.today(),
			"loai_nhap": "Nhập khác",
			"items": [{
				"vat_tu": vat_tu, "so_lo": "LO-TEST-PS",
				"so_luong": 5, "don_gia": 1000,
			}],
		})
		doc.insert(ignore_permissions=True)
		doc.submit()


from miyano_portal.api import kho as kho_api

BM_USER = "bvbm@demo.miyano"
PXN_USER = "pxnabc@demo.miyano"


class TestVatTuEndpoint(FrappeTestCase):
	def setUp(self):
		self.kho = seed_kho_demo()
		frappe.set_user(BM_USER)
		self._da_tao = []

	def tearDown(self):
		frappe.set_user("Administrator")
		for name in self._da_tao:
			if frappe.db.exists("Customer Warehouse Item", name):
				frappe.delete_doc("Customer Warehouse Item", name, force=True, ignore_permissions=True)

	def test_tao_qua_endpoint_gan_vao_kho_cua_phien(self):
		row = kho_api.kho_vat_tu_tao({
			"ma_vat_tu": "BM-API-01", "ten_vat_tu": "Vật tư API", "dvt": "Cái",
		})
		self._da_tao.append(row["name"])
		self.assertEqual(
			frappe.db.get_value("Customer Warehouse Item", row["name"], "kho"),
			self.kho["kho_bm"],
		)

	def test_khong_sua_duoc_vat_tu_cua_kho_khac(self):
		with self.assertRaises(frappe.PermissionError):
			kho_api.kho_vat_tu_sua(self.kho["vt_pxn"], {"ten_vat_tu": "Đổi trộm"})

	def test_list_tra_them_co_phat_sinh_va_active(self):
		rows = kho_api.kho_vat_tu_list()
		self.assertTrue(rows)
		for r in rows:
			self.assertIn("co_phat_sinh", r)
			self.assertIn("active", r)
			self.assertIn("quy_cach", r)

	def test_list_mac_dinh_chi_tra_vat_tu_dang_dung(self):
		row = kho_api.kho_vat_tu_tao({
			"ma_vat_tu": "BM-TAT-01", "ten_vat_tu": "Sẽ tắt", "dvt": "Cái",
		})
		self._da_tao.append(row["name"])
		kho_api.kho_vat_tu_sua(row["name"], {"active": 0})
		self.assertNotIn(row["name"], [r["name"] for r in kho_api.kho_vat_tu_list()])
		self.assertIn(row["name"], [r["name"] for r in kho_api.kho_vat_tu_list(ca_tat=1)])

	def test_tim_loc_theo_ma_va_ten(self):
		rows = kho_api.kho_vat_tu_list(tim="glove")
		self.assertTrue(rows)
		self.assertTrue(all("glove" in f"{r['ma_vat_tu']} {r['ten_vat_tu']}".lower() for r in rows))
