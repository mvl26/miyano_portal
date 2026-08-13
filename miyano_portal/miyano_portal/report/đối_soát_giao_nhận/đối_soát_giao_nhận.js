// Report desk "Đối soát giao nhận" — filter phía client. Xem
// đối_soát_giao_nhận.py cho phép tính; file này chỉ khai báo ô lọc.
frappe.query_reports["Đối soát giao nhận"] = {
	filters: [
		{
			fieldname: "customer",
			label: __("Khách hàng"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "chi_chenh_lech",
			label: __("Chỉ hiện dòng chênh lệch"),
			fieldtype: "Check",
		},
		{
			fieldname: "qua_han_ngay",
			label: __("Chỉ hiện phiếu còn nháp quá (ngày)"),
			fieldtype: "Int",
		},
	],
};
