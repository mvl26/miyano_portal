// Report desk "Tiêu thụ theo máy" — filter phía client. Xem
// tiêu_thụ_theo_máy.py cho phép tính; file này chỉ khai báo ô lọc.
frappe.query_reports["Tiêu thụ theo máy"] = {
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
		},
		{
			fieldname: "den_ngay",
			label: __("Đến ngày"),
			fieldtype: "Date",
		},
	],
};
