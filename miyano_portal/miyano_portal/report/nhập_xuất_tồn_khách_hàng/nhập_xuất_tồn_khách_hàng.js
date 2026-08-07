// Report desk "Nhập-Xuất-Tồn khách hàng" — mặc định khoảng ngày là THÁNG
// HIỆN TẠI, tính lại mỗi lần mở trang (frappe.datetime.month_start/end),
// không phải một hằng số ngày cố định.
frappe.query_reports["Nhập-Xuất-Tồn khách hàng"] = {
	filters: [
		{
			fieldname: "customer",
			label: __("Khách hàng"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "tu_ngay",
			label: __("Từ ngày"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "den_ngay",
			label: __("Đến ngày"),
			fieldtype: "Date",
			default: frappe.datetime.month_end(),
			reqd: 1,
		},
	],
};
