// Report desk "Cấp phát theo tháng và khoa phòng" — filter phía client. Xem
// cấp_phát_theo_tháng_và_khoa_phòng.py cho phép tính; file này chỉ khai ô lọc.
//
// Hai ô ngày để TRỐNG có chủ ý: execute() tự lấy 12 tháng gần nhất khi trống
// (tính lại mỗi lần chạy). Điền sẵn giá trị ở đây sẽ đóng băng một mốc vào
// định nghĩa report và làm hai bên lệch nhau.
frappe.query_reports["Cấp phát theo tháng và khoa phòng"] = {
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
