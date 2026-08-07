// Report desk "Cảnh báo hạn dùng khách hàng" — mặc định 90 ngày, khớp
// cảnh_báo_hạn_dùng_khách_hàng.py::DEFAULT_SO_NGAY.
frappe.query_reports["Cảnh báo hạn dùng khách hàng"] = {
	filters: [
		{
			fieldname: "customer",
			label: __("Khách hàng"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "so_ngay",
			label: __("Sắp hết hạn trong (ngày)"),
			fieldtype: "Int",
			default: 90,
			reqd: 1,
		},
	],
};
