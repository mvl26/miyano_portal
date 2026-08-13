// Report desk "Tiêu thụ và đề xuất dự trù" — filter phía client. Xem
// tiêu_thụ_và_đề_xuất_dự_trù.py cho phép tính; file này chỉ khai báo ô lọc.
frappe.query_reports["Tiêu thụ và đề xuất dự trù"] = {
	filters: [
		{
			fieldname: "customer",
			label: __("Khách hàng"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "nhom",
			label: __("Nhóm vật tư"),
			fieldtype: "Data",
		},
	],
};
