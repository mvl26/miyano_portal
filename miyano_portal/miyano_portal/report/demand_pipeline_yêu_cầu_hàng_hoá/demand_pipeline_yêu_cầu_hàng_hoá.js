// Report desk "Demand pipeline yêu cầu hàng hoá" — filter phía client. Xem
// demand_pipeline_yêu_cầu_hàng_hoá.py cho phép tính; file này chỉ khai ô lọc.
frappe.query_reports["Demand pipeline yêu cầu hàng hoá"] = {
	filters: [
		{
			fieldname: "customer",
			label: __("Khách hàng"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "loai",
			label: __("Loại yêu cầu"),
			fieldtype: "Select",
			options: "\nBổ sung HĐNT\nBáo giá mua lẻ\nTìm nguồn hàng mới",
		},
		{
			fieldname: "tan_suat",
			label: __("Tần suất"),
			fieldtype: "Select",
			options: "\nMột lần\nĐịnh kỳ",
		},
		{
			fieldname: "trang_thai",
			label: __("Trạng thái"),
			fieldtype: "Select",
			options: (
				"\nMới\nĐang tìm nguồn\nCần thêm thông tin\nĐã báo giá\n" +
				"Đã có hàng\nĐã chuyển thành đơn\nKhông đáp ứng được\n" +
				"Khách huỷ\nHết hạn"
			),
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
