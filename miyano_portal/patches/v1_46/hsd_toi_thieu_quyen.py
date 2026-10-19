"""HSD tối thiểu: ẩn trường nội bộ khỏi khách cổng (permlevel 2) và cấp quyền level 2.

Patch riêng (không chỉ sửa `hsd_toi_thieu`) vì site đã chạy `hsd_toi_thieu`
trước khi trường lên permlevel 2 sẽ không chạy lại nó; patch này chạy lại
`them_truong()` (cập nhật thuộc tính trường đã có) rồi cấp quyền. Site mới /
production chạy cả hai theo thứ tự, kết quả như nhau.

Chạy lại được: `install.py::after_install` gọi lại mọi patch.
"""

import frappe
from frappe.permissions import add_permission, setup_custom_perms, update_permission_property

from miyano_portal.patches.v1_46.hsd_toi_thieu import them_truong

DOCTYPE = "Sales Order"
MUC = 2

# Vai trò → có quyền ghi level 2 không. Kinh doanh tính/ghi; kho và kế toán chỉ xem kết quả.
VAI_TRO = {
	"Sales User": 1,
	"Sales Manager": 1,
	"System Manager": 1,
	"Stock User": 0,
	"Stock Manager": 0,
	"Accounts User": 0,
}


def _co_level_0(role):
	return frappe.db.exists("Custom DocPerm", {"parent": DOCTYPE, "role": role, "permlevel": 0})


def cap_quyen():
	"""Thêm dòng Custom DocPerm level 2 (đọc, ghi theo `VAI_TRO`) cho Sales Order.

	Bỏ qua vai trò chưa có quyền level 0 trên Sales Order: Frappe không cho dòng
	level > 0 khi thiếu level 0 (`check_level_zero_is_set`), và vai trò đó vốn
	không mở được đơn nên level 2 cũng vô nghĩa. Không tự thêm level 0 — làm vậy
	là mở rộng người được đọc đơn.
	"""
	setup_custom_perms(DOCTYPE)
	bo_qua = []
	for role, ghi in VAI_TRO.items():
		if not _co_level_0(role):
			bo_qua.append(role)
			continue
		if not frappe.db.exists("Custom DocPerm", {"parent": DOCTYPE, "role": role, "permlevel": MUC, "if_owner": 0}):
			add_permission(DOCTYPE, role, MUC, "read")
		update_permission_property(DOCTYPE, role, MUC, "read", 1, validate=False)
		update_permission_property(DOCTYPE, role, MUC, "write", ghi, validate=False)
	frappe.clear_cache(doctype=DOCTYPE)
	return bo_qua


def execute():
	them_truong()
	cap_quyen()
