// Report desk "Tồn kho khách hàng" — filter phía client. Xem
// tồn_kho_khách_hàng.py cho phép tính; file này chỉ khai báo ô lọc.
frappe.query_reports["Tồn kho khách hàng"] = {
	filters: [
		{
			fieldname: "customer",
			label: __("Khách hàng"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "item",
			label: __("Vật tư (mã hoặc tên)"),
			fieldtype: "Data",
		},
		{
			fieldname: "sap_het_han_trong_ngay",
			label: __("Chỉ hiện sắp hết hạn trong (ngày)"),
			fieldtype: "Int",
		},
	],
};
