"""Import/export danh mục vật tư qua cổng."""

import io

import frappe
from frappe.tests.utils import FrappeTestCase
from openpyxl import Workbook, load_workbook

from miyano_portal.kho import vat_tu as vat_tu_mod
from miyano_portal.setup.seed_kho_demo import seed_kho_demo

HEADERS = [label for label, _ in vat_tu_mod.DANH_MUC_COLUMNS]


def _xlsx(rows, headers=None):
	wb = Workbook()
	ws = wb.active
	ws.append(headers if headers is not None else HEADERS)
	for r in rows:
		ws.append(r)
	buf = io.BytesIO()
	wb.save(buf)
	return buf.getvalue()


class TestDanhMucFile(FrappeTestCase):
	def setUp(self):
		self.kho = seed_kho_demo()
		self.kho_bm = self.kho["kho_bm"]
		self._da_tao = []

	def tearDown(self):
		for name in self._da_tao:
			if frappe.db.exists("Customer Warehouse Item", name):
				frappe.delete_doc("Customer Warehouse Item", name, force=True, ignore_permissions=True)

	def test_preview_khong_ghi_gi(self):
		truoc = frappe.db.count("Customer Warehouse Item", {"kho": self.kho_bm})
		vat_tu_mod.parse_danh_muc(
			_xlsx([["BM-NEW-01", "Vật tư mới", "Cái", "", "", "", 1]]), self.kho_bm
		)
		self.assertEqual(frappe.db.count("Customer Warehouse Item", {"kho": self.kho_bm}), truoc)

	def test_ma_moi_thi_tao_ma_da_co_thi_cap_nhat(self):
		content = _xlsx([
			["BM-NEW-02", "Vật tư mới 2", "Cái", "", "Gói 10", "Tiêu hao", 1],
			["MYN-GLOVE-M", "Găng tay ĐỔI TÊN", "Hộp", "", "", "", 1],
		])
		parsed = vat_tu_mod.parse_danh_muc(content, self.kho_bm)
		self.assertEqual(parsed["error_count"], 0)
		self.assertEqual(parsed["summary"], {"tao_moi": 1, "cap_nhat": 1})

		kq = vat_tu_mod.commit_danh_muc(content, self.kho_bm)
		moi = frappe.db.get_value("Customer Warehouse Item", {"kho": self.kho_bm, "ma_vat_tu": "BM-NEW-02"})
		self._da_tao.append(moi)
		self.assertEqual(kq, {"tao_moi": 1, "cap_nhat": 1})
		self.assertEqual(
			frappe.db.get_value("Customer Warehouse Item", self.kho["vt_bm"], "ten_vat_tu"),
			"Găng tay ĐỔI TÊN",
		)

	def test_mot_dong_loi_thi_khong_ghi_gi(self):
		truoc = frappe.db.count("Customer Warehouse Item", {"kho": self.kho_bm})
		content = _xlsx([
			["BM-NEW-03", "Hợp lệ", "Cái", "", "", "", 1],
			["", "Thiếu mã", "Cái", "", "", "", 1],
		])
		with self.assertRaises(frappe.ValidationError):
			vat_tu_mod.commit_danh_muc(content, self.kho_bm)
		self.assertEqual(frappe.db.count("Customer Warehouse Item", {"kho": self.kho_bm}), truoc)

	def test_doi_dvt_vat_tu_da_phat_sinh_la_dong_loi(self):
		self._bao_dam_co_phat_sinh(self.kho["vt_bm"])
		parsed = vat_tu_mod.parse_danh_muc(
			_xlsx([["MYN-GLOVE-M", "Găng tay y tế size M", "Cái", "", "", "", 1]]), self.kho_bm
		)
		self.assertEqual(parsed["error_count"], 1)
		self.assertIn("ĐVT", " ".join(parsed["rows_error"][0]["errors"]))

	def test_tat_vat_tu_con_ton_la_dong_loi(self):
		self._bao_dam_co_phat_sinh(self.kho["vt_bm"])
		parsed = vat_tu_mod.parse_danh_muc(
			_xlsx([["MYN-GLOVE-M", "Găng tay y tế size M", "Hộp", "", "", "", 0]]), self.kho_bm
		)
		self.assertEqual(parsed["error_count"], 1)
		self.assertIn("còn tồn", " ".join(parsed["rows_error"][0]["errors"]))

	def test_round_trip_xuat_roi_nap_lai_khong_doi_du_lieu(self):
		content = vat_tu_mod.build_danh_muc_xlsx(self.kho_bm)
		ws = load_workbook(io.BytesIO(content), data_only=True).active
		self.assertEqual([c.value for c in ws[1]], HEADERS)
		parsed = vat_tu_mod.parse_danh_muc(content, self.kho_bm)
		self.assertEqual(parsed["error_count"], 0)
		self.assertEqual(parsed["summary"]["tao_moi"], 0)

	def _bao_dam_co_phat_sinh(self, vat_tu):
		if vat_tu_mod.co_phat_sinh(vat_tu):
			return
		doc = frappe.get_doc({
			"doctype": "Customer Stock Receipt",
			"kho": self.kho_bm,
			"ngay": frappe.utils.today(),
			"loai_nhap": "Nhập khác",
			"items": [{"vat_tu": vat_tu, "so_lo": "LO-DM-01", "so_luong": 5, "don_gia": 1000}],
		})
		doc.insert(ignore_permissions=True)
		doc.submit()
