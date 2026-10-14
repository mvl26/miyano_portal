"""Patch v1_44 `bo_vong_bao_gia_tren_don` — Sales Order không còn vòng báo
giá với khách; báo giá đi trên Quotation.

Site test đã chạy patch: các bài cấu hình đọc thẳng kết quả trên site, bài dữ
liệu dựng lại đơn ở trạng thái cũ bằng `db.set_value` rồi chạy lại patch.
Không bài nào tạo lại Custom Field đã xoá: `alter table` tự commit giao dịch
của lớp test.
"""

import frappe

from miyano_portal import bao_gia, dat_hang
from miyano_portal.patches.v1_44 import bo_vong_bao_gia_tren_don as patch
from miyano_portal.tests.nen_bao_gia import NenBaoGia

WF = "Sales Order - Client Portal"


class TestBoVongBaoGiaTrenDon(NenBaoGia):
	@classmethod
	def setUpClass(cls):
		# Bản Workflow trong cache tài liệu không theo giao dịch: xoá SAU rollback.
		cls.addClassCleanup(frappe.clear_document_cache, "Workflow", WF)
		super().setUpClass()

	# ---- cấu hình sau patch ----------------------------------------------

	def test_workflow_don_chi_con_bon_trang_thai_bon_buoc(self):
		wf = frappe.get_doc("Workflow", WF)
		self.assertEqual(
			sorted((s.state, str(s.doc_status)) for s in wf.states),
			sorted([
				("Chờ xác nhận", "0"), ("Chờ Miyano xác nhận", "0"),
				("Đã xác nhận", "1"), ("Từ chối", "0"),
			]),
		)
		self.assertEqual(
			sorted((t.state, t.action, t.next_state, t.allowed) for t in wf.transitions),
			sorted([
				("Chờ xác nhận", "Gửi duyệt", "Chờ Miyano xác nhận", "Sales User"),
				("Chờ Miyano xác nhận", "Xác nhận", "Đã xác nhận", "Sales User"),
				("Chờ Miyano xác nhận", "Xác nhận", "Đã xác nhận", "Sales Manager"),
				("Chờ Miyano xác nhận", "Từ chối", "Từ chối", "Sales User"),
			]),
		)
		self.assertFalse({s.state for s in wf.states} & patch.TT_BO)
		self.assertFalse({t.action for t in wf.transitions} & patch.HD_BO)

	def test_workflow_bao_gia_khong_bi_dong(self):
		"""Workflow của Quotation dùng chung tên trạng thái / hành động: patch
		không xoá Workflow State / Action Master và không đụng workflow đó."""
		wf = frappe.get_doc("Workflow", bao_gia.WORKFLOW)
		states = {s.state for s in wf.states}
		self.assertIn("Chờ khách đồng ý", states)
		self.assertIn("Báo giá hết hạn", states)
		canh = {(t.state, t.action, t.next_state) for t in wf.transitions}
		self.assertIn(("Chờ khách đồng ý", "Khách đồng ý", "Khách đã đồng ý"), canh)
		self.assertIn(("Báo giá hết hạn", "Mở lại", "Chờ Miyano báo giá"), canh)
		for ten in ("Chờ khách đồng ý", "Báo giá hết hạn"):
			self.assertTrue(frappe.db.exists("Workflow State", ten), ten)
		for ten in ("Gửi khách duyệt", "Khách đồng ý", "Báo giá hết hạn", "Mở lại"):
			self.assertTrue(frappe.db.exists("Workflow Action Master", ten), ten)

	def test_custom_field_bo_khoi_don_con_tren_bao_gia(self):
		meta_don = frappe.get_meta("Sales Order")
		meta_bg = frappe.get_meta("Quotation")
		for fieldname in patch.FIELD_BO:
			with self.subTest(fieldname=fieldname):
				self.assertFalse(frappe.db.exists(
					"Custom Field", {"dt": "Sales Order", "fieldname": fieldname}))
				self.assertFalse(frappe.db.has_column("Sales Order", fieldname))
				self.assertIsNone(meta_don.get_field(fieldname))
				self.assertTrue(frappe.db.exists(
					"Custom Field", {"dt": "Quotation", "fieldname": fieldname}))
				self.assertIsNotNone(meta_bg.get_field(fieldname))
		self.assertFalse(frappe.get_all(
			"Custom Field",
			filters={"dt": "Sales Order", "insert_after": ["in", patch.FIELD_BO]},
		))
		self.assertTrue(frappe.db.exists("DocType", "Sales Order Dat Ngoai Item"))

	def test_thong_bao_va_mau_in_cua_don_da_xoa(self):
		self.assertFalse(frappe.db.exists("Notification", patch.THONG_BAO_BO))
		self.assertFalse(frappe.db.exists("Print Format", patch.MAU_IN_BO))
		self.assertTrue(frappe.db.exists("Print Format", "Miyano - Yêu cầu báo giá"))

	# ---- dữ liệu cũ: chạy lại patch --------------------------------------

	def _don(self, trang_thai, ly_do=None):
		kq = dat_hang.tao_sales_order(
			self.kh_a, items=[{"item_code": self.item_ngoai, "qty": 1}],
			request_id=frappe.generate_hash(length=12),
		)
		gia_tri = {"workflow_state": trang_thai}
		if ly_do:
			gia_tri["custom_ly_do_tu_choi"] = ly_do
		frappe.db.set_value("Sales Order", kq["sales_order"], gia_tri, update_modified=False)
		return kq["sales_order"]

	def _dong_dat_ngoai(self, parenttype, parent, idx, **gia_tri):
		frappe.get_doc({
			"doctype": "Sales Order Dat Ngoai Item", "parenttype": parenttype,
			"parent": parent, "parentfield": "custom_dat_ngoai", "idx": idx,
			**gia_tri,
		}).db_insert()

	def _comment(self, ten):
		return frappe.get_all(
			"Comment",
			filters={"reference_doctype": "Sales Order", "reference_name": ten,
			         "content": ["like", "%Dòng đặt ngoài%"]},
			pluck="content",
		)

	def test_chay_lai_chuyen_trang_thai_va_chep_dong_dat_ngoai(self):
		cho_khach = self._don("Chờ khách đồng ý")
		het_han = self._don("Báo giá hết hạn")
		huy = self._don("Khách huỷ")
		huy_co_ly_do = self._don("Khách huỷ", ly_do="Khoa đã mua nơi khác")
		self.assertEqual(
			frappe.db.get_value("Sales Order", cho_khach, "workflow_state"),
			"Chờ khách đồng ý", "cột workflow_state phải giữ được trạng thái cũ",
		)
		sua_luc = frappe.db.get_value("Sales Order", cho_khach, "modified")

		self._dong_dat_ngoai(
			"Sales Order", cho_khach, 1, ten_hang="Kim luồn 24G", dvt="Cái",
			so_luong=5, model_ma="KL-24", item_khop=self.item_ngoai, da_chuyen=1,
		)
		self._dong_dat_ngoai(
			"Sales Order", cho_khach, 2, ten_hang="Găng tay <M>", dvt="Hộp",
			so_luong=2, ghi_chu="loại không bột",
		)
		ten_bg = "_TEST-BG-GIU-NGUYEN"
		self._dong_dat_ngoai("Quotation", ten_bg, 1, ten_hang="Bông y tế", dvt="Gói", so_luong=1)

		patch.execute()
		patch.execute()

		trang_thai = dict(frappe.get_all(
			"Sales Order", filters={"name": ["in", [cho_khach, het_han, huy, huy_co_ly_do]]},
			fields=["name", "workflow_state"], as_list=True,
		))
		self.assertEqual(trang_thai, {
			cho_khach: "Chờ xác nhận", het_han: "Chờ xác nhận",
			huy: "Từ chối", huy_co_ly_do: "Từ chối",
		})
		self.assertEqual(
			frappe.db.get_value("Sales Order", huy, "custom_ly_do_tu_choi"),
			patch.LY_DO_KHACH_HUY,
		)
		self.assertEqual(
			frappe.db.get_value("Sales Order", huy_co_ly_do, "custom_ly_do_tu_choi"),
			"Khoa đã mua nơi khác",
		)
		self.assertEqual(frappe.db.get_value("Sales Order", cho_khach, "modified"), sua_luc)

		comment = self._comment(cho_khach)
		self.assertEqual(len(comment), 1, "chạy lại không được chép lần hai")
		self.assertIn("Kim luồn 24G — 5 Cái (KL-24)", comment[0])
		self.assertIn(f"đã chuyển thành dòng hàng {self.item_ngoai}", comment[0])
		self.assertIn("Găng tay &lt;M&gt; — 2 Hộp (loại không bột): CHƯA khớp mã", comment[0])
		self.assertEqual(self._comment(het_han), [])

		self.assertFalse(frappe.get_all(
			"Sales Order Dat Ngoai Item", filters={"parenttype": "Sales Order"}))
		self.assertTrue(frappe.db.exists(
			"Sales Order Dat Ngoai Item", {"parenttype": "Quotation", "parent": ten_bg}))
