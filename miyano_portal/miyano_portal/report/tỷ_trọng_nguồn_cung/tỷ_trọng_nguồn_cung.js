// Report desk "Tỷ trọng nguồn cung" — filter phía client. Xem
// tỷ_trọng_nguồn_cung.py cho phép tính; file này chỉ khai báo ô lọc.
frappe.query_reports["Tỷ trọng nguồn cung"] = {
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
