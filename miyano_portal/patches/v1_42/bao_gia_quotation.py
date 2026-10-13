"""Yêu cầu báo giá bằng Quotation (spec 2026-10-12 §3, §9).

Chạy lại được: `install.py::after_install` gọi lại mọi patch, nên từng bước
phải cho cùng kết quả ở lần chạy thứ hai.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

LOAI_DON_THEO_BAO_GIA = "Theo báo giá"


def them_truong():
	# Trường `bao_gia` nằm trong .json của phiếu: site cũ chỉ thấy sau khi nạp lại.
	frappe.reload_doc("miyano_portal", "doctype", "portal_de_xuat_mua")
	create_custom_fields({
		"Quotation": [
			{
				"fieldname": "custom_sec_cong_khach_hang", "label": "Cổng khách hàng",
				"fieldtype": "Section Break", "insert_after": "amended_from",
				# Mở sẵn: ô «Lý do từ chối» nằm trong mục này, và bước «Từ chối»
				# đòi nó. Ghi `0` TƯỜNG MINH — `create_custom_fields` chỉ cập
				# nhật khoá được nêu, bỏ khoá đi thì site đã cài vẫn thu gọn.
				"collapsible": 0,
			},
			# Bốn trường dưới đây `no_copy`: bản «Duplicate» / «Amend» trên Desk
			# không mang `custom_request_id` (cũng `no_copy`), nên nếu còn mang
			# nguồn "Client Portal" thì khách thấy nút Đồng ý mà `bao_gia.
			# _dam_bao_cua_cong` từ chối, và nhân viên cũng không ghi nhận thay
			# được. Bản sao là một báo giá "Nội bộ" bình thường. Hệ quả: mapper
			# Quotation → Sales Order không chép chúng nữa — `bao_gia._sinh_don`
			# gán tường minh cả bốn lên đơn.
			{
				"fieldname": "custom_nguon_don", "label": "Nguồn",
				"fieldtype": "Select", "options": "Nội bộ\nClient Portal",
				"default": "Nội bộ", "insert_after": "custom_sec_cong_khach_hang",
				"read_only": 1, "in_standard_filter": 1, "no_copy": 1,
			},
			{
				"fieldname": "custom_de_xuat", "label": "Phiếu gốc",
				"fieldtype": "Link", "options": "Portal De Xuat Mua",
				"insert_after": "custom_nguon_don", "read_only": 1, "search_index": 1,
				"no_copy": 1,
			},
			{
				"fieldname": "custom_khoa_phong", "label": "Khoa phòng",
				"fieldtype": "Link", "options": "Customer Department",
				"insert_after": "custom_de_xuat", "read_only": 1, "search_index": 1,
				"no_copy": 1,
			},
			{
				"fieldname": "custom_ten_don_hang", "label": "Tên đơn hàng",
				"fieldtype": "Data", "insert_after": "custom_khoa_phong", "no_copy": 1,
			},
			{
				"fieldname": "custom_request_id", "label": "Mã yêu cầu",
				"fieldtype": "Data", "insert_after": "custom_ten_don_hang",
				"read_only": 1, "unique": 1, "no_copy": 1,
			},
			{
				"fieldname": "custom_ngay_gui_khach_duyet", "label": "Gửi khách duyệt lúc",
				"fieldtype": "Datetime", "insert_after": "custom_request_id",
				"read_only": 1, "no_copy": 1,
			},
			{
				"fieldname": "custom_ly_do_tu_choi", "label": "Lý do từ chối",
				"fieldtype": "Small Text", "insert_after": "custom_ngay_gui_khach_duyet",
				"no_copy": 1,
			},
			{
				# `no_copy` là BẮT BUỘC: Sales Order có bảng cùng tên, cùng bảng
				# con, nên mapper Quotation → Sales Order sẽ tự chép dòng gõ tay
				# sang đơn, mang theo `dong_hang` trỏ vào dòng của BÁO GIÁ.
				"fieldname": "custom_dat_ngoai", "label": "Hàng khách gõ tay (chưa có mã)",
				"fieldtype": "Table", "options": "Sales Order Dat Ngoai Item",
				"insert_after": "items", "no_copy": 1,
			},
		],
		"Quotation Item": [
			{
				"fieldname": "custom_nguon_gia", "label": "Nguồn giá",
				"fieldtype": "Select", "options": "\nBảng giá\nBáo giá",
				"insert_after": "rate", "read_only": 1, "no_copy": 1,
				"in_list_view": 1, "columns": 1,
			},
		],
	}, ignore_validate=True)

	# `custom_loai_don` là Custom Field: lựa chọn nằm ở `options` của chính nó.
	ten = frappe.db.get_value(
		"Custom Field", {"dt": "Sales Order", "fieldname": "custom_loai_don"}, "name"
	)
	if not ten:
		frappe.log_error(
			title="Patch v1_42: thiếu Custom Field custom_loai_don",
			message=(
				"Không tìm thấy Custom Field `custom_loai_don` trên Sales Order nên "
				f'CHƯA thêm được lựa chọn "{LOAI_DON_THEO_BAO_GIA}". Tạo lại field '
				"(patch v1_8) rồi chạy lại "
				"`miyano_portal.patches.v1_42.bao_gia_quotation.them_truong`."
			),
		)
		return
	lua_chon = (frappe.db.get_value("Custom Field", ten, "options") or "").split("\n")
	if LOAI_DON_THEO_BAO_GIA not in lua_chon:
		lua_chon.append(LOAI_DON_THEO_BAO_GIA)
		frappe.db.set_value("Custom Field", ten, "options", "\n".join(lua_chon))
		frappe.clear_cache(doctype="Sales Order")


def cai_workflow():
	from miyano_portal.setup.install_workflow import (
		gan_trang_thai_bao_gia_cu,
		install_quotation_workflow,
		mo_rong_workflow_bao_gia,
	)

	install_quotation_workflow()
	# Workflow cài từ bản trước chưa có bước «Mở lại» của báo giá hết hạn.
	mo_rong_workflow_bao_gia()
	frappe.clear_cache(doctype="Quotation")
	gan_trang_thai_bao_gia_cu()


def cai_mau_in_thong_bao_hang_viec():
	from miyano_portal.setup.install_kho_workspace import install_kho_workspace
	from miyano_portal.setup.install_notifications import (
		TEN_TB_BAO_GIA,
		install_portal_notifications,
	)
	from miyano_portal.setup.install_print_formats import (
		NAME_YCBG,
		install_portal_print_formats,
	)

	install_portal_print_formats()
	install_portal_notifications()
	if frappe.db.exists("Notification", TEN_TB_BAO_GIA) and frappe.db.exists(
		"Print Format", NAME_YCBG
	):
		frappe.db.set_value(
			"Notification", TEN_TB_BAO_GIA, {"attach_print": 1, "print_format": NAME_YCBG}
		)
	install_kho_workspace()


def execute():
	them_truong()
	cai_workflow()
	cai_mau_in_thong_bao_hang_viec()
