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
		{
			// (review E5 round 2) — trước đây `so_ngay` có sẵn trên hàm dữ
			// liệu nhưng KHÔNG được phơi ra ô lọc nào; ngưỡng "kho không
			// hoạt động" mặc định tái dùng nguong_cham_luan_chuyen_ngay (90
			// ngày) của E4, một khái niệm KHÁC (chỉ áp cho "Kho không hoạt
			// động") — ô này cho sales override ngay mà không cần chờ tách
			// field Settings riêng.
			fieldname: "so_ngay",
			label: __("Số ngày (chỉ áp cho \"Kho không hoạt động\")"),
			fieldtype: "Int",
		},
	],
};
