"""Report desk "Demand pipeline yêu cầu hàng hoá" (US-E6.6/UC-53) — Script
Report, is_standard=Yes. Theo đúng khuôn `install_kho_desk_reports.py`:
idempotent, cài bằng code trong một patch, KHÔNG trông cậy vào cơ chế đồng
bộ file-trên-đĩa của `bench migrate`.

CHỐT AN NINH THẬT SỰ nằm ở `ref_doctype` + `roles`, không phải "ai mở được
menu Report" — xem docstring dài ở install_kho_desk_reports.py, áp dụng y
nguyên ở đây: `Portal Item Request` không có DocPerm nào cho role `Customer`
(xem JSON doctype), nên `frappe.has_permission(ref_doctype, "report")` tự
chặn portal TRƯỚC KHI execute() được gọi. `roles` trên Report doc giới hạn
thêm cho đúng ba role nhân viên xử lý yêu cầu — KHÔNG được để trống.
"""

import frappe

STAFF_ROLES = ("Sales Manager", "Sales User", "Purchase User")

REPORT_NAME = "Demand pipeline yêu cầu hàng hoá"


def install_e6_desk_reports():
	if frappe.db.exists("Report", REPORT_NAME):
		return
	frappe.get_doc({
		"doctype": "Report",
		"report_name": REPORT_NAME,
		"ref_doctype": "Portal Item Request",
		"module": "Miyano Portal",
		"report_type": "Script Report",
		"is_standard": "Yes",
		# Cùng lý do với install_kho_desk_reports.py: báo cáo quét toàn site
		# nhưng nhẹ (một bảng, không N-X-T), không cần chuyển "prepared report".
		"disable_prepared_report_automation": 1,
		"roles": [{"role": role} for role in STAFF_ROLES],
	}).insert(ignore_permissions=True)
