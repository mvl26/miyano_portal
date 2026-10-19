"""Báo giá theo đợt (spec 2026-10-15 §3).

Chạy lại được: `install.py::after_install` gọi lại mọi patch.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def them_truong():
	frappe.reload_doc("miyano_portal", "doctype", "portal_de_xuat_mua_don_hang", force=True)
	frappe.reload_doc("miyano_portal", "doctype", "portal_de_xuat_mua", force=True)
	# Mọi trường `no_copy`: bản «Duplicate»/«Amend» trên Desk là báo giá nội bộ
	# bình thường (cùng lý do với bốn trường của patch v1_42).
	create_custom_fields({
		"Quotation": [
			{
				"fieldname": "custom_phieu_goc", "label": "Phiếu gốc (báo giá theo đợt)",
				"fieldtype": "Link", "options": "Quotation",
				"insert_after": "custom_ly_do_tu_choi", "read_only": 1, "no_copy": 1,
				"search_index": 1,
			},
			{
				# Trên phiếu gốc đây là bộ đếm nội bộ (số đợt đã phát hành): ẩn.
				"fieldname": "custom_so_dot", "label": "Đợt", "fieldtype": "Int",
				"insert_after": "custom_phieu_goc", "read_only": 1, "no_copy": 1,
				"depends_on": "eval:doc.custom_phieu_goc",
			},
			{
				"fieldname": "custom_da_tra_ve", "label": "Đã trả mặt hàng về phiếu gốc",
				"fieldtype": "Check", "insert_after": "custom_so_dot", "read_only": 1,
				"no_copy": 1,
			},
			{
				# KHÔNG read-only: nhân viên gõ lý do rồi bấm «Huỷ phần còn lại»,
				# như ô «Lý do từ chối». Chỉ hiện trên phiếu gốc của cổng.
				"fieldname": "custom_ly_do_huy_con_lai", "label": "Lý do huỷ phần còn lại",
				"fieldtype": "Small Text", "insert_after": "custom_da_tra_ve", "no_copy": 1,
				"depends_on": "eval:doc.custom_nguon_don=='Client Portal' && !doc.custom_phieu_goc",
			},
			{
				"fieldname": "custom_nguoi_huy_con_lai", "label": "Người huỷ phần còn lại",
				"fieldtype": "Data", "insert_after": "custom_ly_do_huy_con_lai",
				"read_only": 1, "no_copy": 1,
			},
		],
	}, ignore_validate=True)


def cai_workflow():
	from miyano_portal.setup.install_workflow import (
		install_quotation_workflow,
		mo_rong_workflow_theo_dot,
	)

	# Đảm bảo Workflow State / Action Master mới (thoát sớm phần Workflow).
	install_quotation_workflow()
	mo_rong_workflow_theo_dot()
	frappe.clear_cache(doctype="Quotation")


def cap_nhat_thong_bao():
	"""`install_portal_notifications` bỏ qua thông báo đã có: ghi đè tiêu đề."""
	from miyano_portal.setup.install_notifications import DEFS, TEN_TB_BAO_GIA

	if frappe.db.exists("Notification", TEN_TB_BAO_GIA):
		tieu_de = next(d["subject"] for d in DEFS if d["name"] == TEN_TB_BAO_GIA)
		frappe.db.set_value("Notification", TEN_TB_BAO_GIA, "subject", tieu_de)


def chep_don_hang():
	"""Liên kết `sales_order`/`bao_gia` đang có của phiếu → một dòng `don_hang`."""
	from miyano_portal.bao_gia_theo_dot import them_don_hang

	for p in frappe.db.sql(
		"""select name, sales_order, bao_gia from `tabPortal De Xuat Mua`
		where coalesce(sales_order, '') != ''""",
		as_dict=True,
	):
		them_don_hang(p.name, p.sales_order, p.bao_gia or None, 0)


def execute():
	them_truong()
	cai_workflow()
	cap_nhat_thong_bao()
	chep_don_hang()
