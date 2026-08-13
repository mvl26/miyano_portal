// Report desk "Chất lượng dữ liệu kho khách" — filter phía client. Xem
// chất_lượng_dữ_liệu_kho_khách.py cho phép tính; file này chỉ khai báo ô lọc.
frappe.query_reports["Chất lượng dữ liệu kho khách"] = {
	filters: [
		{
			fieldname: "customer",
			label: __("Khách hàng"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "chi_chua_bat_co",
			label: __("Chỉ hiện item CHƯA bật đủ cả hai cờ"),
			fieldtype: "Check",
			default: 1,
		},
	],
};
