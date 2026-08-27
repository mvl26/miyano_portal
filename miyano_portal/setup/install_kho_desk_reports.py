"""Ba Report doctype (Script Report, is_standard=Yes) cho nhân viên Miyano
xem kho khách hàng trên desk — Phase 6. Theo đúng khuôn
`install_kho_print_formats.py`: idempotent, cài bằng code trong một patch,
không trông cậy vào cơ chế đồng bộ file-trên-đĩa của `bench migrate`.

`is_standard="Yes"` + file .py trên đĩa (KHÔNG phải `report_script`/
`is_standard="No"`): report_script chạy qua RestrictedPython
(`frappe.utils.safe_exec`, cần bật `server_script_enabled` trong site config)
và không cho `import` thẳng module của app — sẽ buộc phải chép lại phép tính
N-X-T/tồn/cảnh báo hạn lần thứ hai bằng cú pháp hạn chế, đúng điều đặc tả cấm.
File .py chuẩn thì gọi thẳng `kho.desk_reports`, không giới hạn gì.

CHỐT AN NINH THẬT SỰ nằm ở `ref_doctype` + `roles`, không phải ở việc "ai mở
được menu Report":
  * `frappe.desk.query_report.run()` gọi `frappe.has_permission(ref_doctype,
    "report")` TRƯỚC KHI thực thi — role `Customer` không có DocPerm nào trên
    sáu doctype kho (xem hooks.py), nên điều kiện này tự chặn portal mà không
    cần thêm gì ở đây.
  * `roles` (Has Role) trên chính Report doc giới hạn thêm cho ĐÚNG BA role
    nhân viên Miyano — hẹp hơn "mọi role có report:1 trên ref_doctype", dù
    hiện tại ba role đó trùng nhau. Bỏ trống `roles` = ai cũng chạy được
    (`is_permitted()` trả True khi rỗng) — KHÔNG được để trống.
"""

import frappe

STAFF_ROLES = ("System Manager", "Sales Manager", "Sales User")

# ref_doctype chọn trong số các doctype kho ĐÃ có report:1 cho ba role trên và
# KHÔNG có DocPerm nào cho Customer (xem *.json của từng doctype) — không tạo
# thêm doctype hay quyền mới nào riêng cho các report này.
REPORTS = [
	{
		"report_name": "Tồn kho khách hàng",
		"ref_doctype": "Customer Stock Lot Balance",
	},
	{
		"report_name": "Nhập-Xuất-Tồn khách hàng",
		"ref_doctype": "Customer Stock Ledger Entry",
	},
	{
		"report_name": "Cảnh báo hạn dùng khách hàng",
		"ref_doctype": "Customer Stock Lot Balance",
	},
	# E3 phần B (US-E3.5/E3.6) — cùng khuôn an ninh: ref_doctype đã có report:1
	# cho ba role trên và KHÔNG DocPerm nào cho Customer (xem
	# customer_stock_receipt.json). Cả hai đọc dữ liệu của MỌI khách hàng.
	#
	# (I4/M5, review) Tên KHÔNG dùng en-dash "–" (rủi ro scrub()/gõ nhầm gạch
	# nối thường — xem docstring đối_soát_giao_nhận.py) và tên thứ hai KHÔNG
	# còn là "Chất lượng dữ liệu" chung chung (Report docname duy nhất TOÀN
	# SITE, dễ đụng report app khác).
	{
		"report_name": "Đối soát giao nhận",
		"ref_doctype": "Customer Stock Receipt",
	},
	{
		"report_name": "Chất lượng dữ liệu kho khách",
		"ref_doctype": "Customer Stock Receipt",
	},
	# E5 (US-E5.5) — cùng khuôn an ninh: ref_doctype đã có report:1 cho ba
	# role trên và KHÔNG DocPerm nào cho Customer. Cả hai đọc dữ liệu tiêu
	# thụ/nhập hàng của MỌI khách hàng (VĐ-10 — chỉ nhân viên Miyano, không
	# phải khách, xem hạn chế pháp lý ở PRD E5 §Dữ liệu & API).
	{
		"report_name": "Tiêu thụ và đề xuất dự trù",
		"ref_doctype": "Customer Warehouse Item",
	},
	{
		"report_name": "Tỷ trọng nguồn cung",
		"ref_doctype": "Customer Stock Receipt",
	},
	# E8 (US-E8.5) — cùng khuôn an ninh: ref_doctype đã có report:1 cho ba
	# role trên và KHÔNG DocPerm nào cho Customer. Đọc cấp phát theo khoa
	# phòng của MỌI khách hàng (VĐ-10, cùng hạn chế các report desk khác).
	{
		"report_name": "Cấp phát theo khoa phòng",
		"ref_doctype": "Customer Stock Ledger Entry",
	},
	# Yêu cầu chủ đầu tư 2026-08-17 — bản GỘP THEO THÁNG của report ngay trên.
	# Cùng khuôn an ninh, cùng ref_doctype. KHÔNG thay thế report kia: một cái
	# ở mức dòng chi tiết (có số lượng theo vật tư), một cái ở mức tháng × khoa
	# (chỉ tiền + phép đếm) — xem docstring desk_reports.cap_phat_thang_theo_
	# khoa_rows() cho lý do mức tháng không được có cột số lượng.
	{
		"report_name": "Cấp phát theo tháng và khoa phòng",
		"ref_doctype": "Customer Stock Ledger Entry",
	},
	# Task 10 — báo cáo xoay chiều theo máy (`reports.tieu_thu_theo_may_rows`)
	# gọi qua `desk_reports.tieu_thu_theo_thiet_bi_rows`. Cùng khuôn an ninh,
	# cùng ref_doctype "Cấp phát theo khoa phòng" (cùng nguồn dữ liệu — sổ
	# kho join phiếu xuất). Report tra cứu theo tình huống (như "Cấp phát
	# theo khoa phòng"/"Tiêu thụ và đề xuất dự trù"), KHÔNG thêm shortcut
	# workspace — xem install_kho_workspace.py cho lý do bốn report tra cứu
	# không có shortcut trong khi bốn report định kỳ có.
	{
		"report_name": "Tiêu thụ theo máy",
		"ref_doctype": "Customer Stock Ledger Entry",
	},
]


def install_kho_desk_reports():
	for spec in REPORTS:
		if frappe.db.exists("Report", spec["report_name"]):
			continue
		frappe.get_doc({
			"doctype": "Report",
			"report_name": spec["report_name"],
			"ref_doctype": spec["ref_doctype"],
			"module": "Miyano Portal",
			"report_type": "Script Report",
			"is_standard": "Yes",
			# Không cho tự động chuyển "prepared report" sau 15 giây thực thi
			# (execute_script_report) — báo cáo này quét toàn site, đủ nhanh,
			# và một job nền sẽ phá vỡ giả định "chạy xong trả kết quả ngay"
			# mà test/portal đối chiếu số liệu ở đây đang dùng.
			"disable_prepared_report_automation": 1,
			"roles": [{"role": role} for role in STAFF_ROLES],
		}).insert(ignore_permissions=True)
