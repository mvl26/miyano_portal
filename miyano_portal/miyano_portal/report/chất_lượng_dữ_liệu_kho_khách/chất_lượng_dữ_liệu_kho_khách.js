// Report desk "Chất lượng dữ liệu kho khách" — filter phía client. Xem
// chất_lượng_dữ_liệu_kho_khách.py cho phép tính; file này chỉ khai báo ô lọc.
//
// E5/US-E5.5: "loai_van_de" chọn một trong ba khía cạnh chất lượng dữ liệu
// (report được MỞ RỘNG, không tạo report thứ hai — xem docstring .py).
// Rỗng/"Item thiếu lô hạn" (mặc định) giữ nguyên hành vi cũ (US-E3.6).
frappe.query_reports["Chất lượng dữ liệu kho khách"] = {
	filters: [
		{
			fieldname: "loai_van_de",
			label: __("Khía cạnh"),
			fieldtype: "Select",
			options: "\nItem thiếu lô/hạn\nKho không hoạt động\nPhiếu thiếu chứng từ NCC",
			default: "",
		},
		{
			fieldname: "customer",
			label: __("Khách hàng"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "chi_chua_bat_co",
			label: __("Chỉ hiện item CHƯA bật đủ cả hai cờ (chỉ áp cho \"Item thiếu lô/hạn\")"),
			fieldtype: "Check",
			default: 1,
		},
	],
};
