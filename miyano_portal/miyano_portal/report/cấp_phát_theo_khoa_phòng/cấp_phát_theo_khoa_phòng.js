// Report desk "Cấp phát theo khoa phòng" — filter phía client. Xem
// cấp_phát_theo_khoa_phòng.py cho phép tính; file này chỉ khai báo ô lọc.
frappe.query_reports["Cấp phát theo khoa phòng"] = {
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
