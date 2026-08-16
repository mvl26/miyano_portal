// Nút vai NHÂN VIÊN trên đơn hàng (Desk).
//
// "Hẹn lịch giao mới" phục vụ đúng câu của chủ đầu tư 2026-08-16: "khi chưa
// có hàng tôi muốn thông báo lại cho khách hàng về hàng thiếu và sẽ vận
// chuyển sau hoặc đổi ngày giao hàng". Nút chỉ hiện trên đơn ĐÃ XÁC NHẬN —
// đơn còn nháp thì sửa thẳng ngày giao trên form, không cần báo ai.

frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Hẹn lịch giao mới"), () => hen_lich_giao(frm), __("Miyano"));
		}
		// `Portal Delivery Inspection.sales_order` là field Data (không Link)
		// nên Frappe không dựng mục "Connections" — không có nút này thì
		// nhân viên không có đường nào từ đơn sang biên bản kiểm hàng.
		frm.add_custom_button(__("Biên bản kiểm hàng"), () => {
			frappe.set_route("List", "Portal Delivery Inspection", {
				sales_order: frm.doc.name,
			});
		}, __("Miyano"));
	},
});

function hen_lich_giao(frm) {
	frappe.prompt(
		[
			{
				fieldname: "loai", fieldtype: "Select", reqd: 1,
				label: __("Hình thức"),
				options: ["Sẽ giao bù", "Đã đổi ngày giao"].join("\n"),
				default: "Sẽ giao bù",
				description: __(
					"«Sẽ giao bù»: giữ nguyên ngày cam kết gốc, chỉ hẹn ngày giao phần còn lại. " +
					"«Đã đổi ngày giao»: dời hẳn ngày giao của đơn và mọi dòng."
				),
			},
			{
				fieldname: "ngay_moi", fieldtype: "Date", reqd: 1,
				label: __("Ngày hẹn giao"),
				default: frappe.datetime.add_days(frappe.datetime.get_today(), 7),
			},
			{
				fieldname: "ly_do", fieldtype: "Small Text", reqd: 1,
				label: __("Lý do — khách sẽ đọc đúng dòng này"),
			},
		],
		(v) => {
			frappe.call({
				method: "miyano_portal.portal_hen_giao.hen_giao_lai",
				args: { order: frm.doc.name, ngay_moi: v.ngay_moi, loai: v.loai, ly_do: v.ly_do },
				freeze: true,
				freeze_message: __("Đang ghi lời hẹn và báo khách…"),
			}).then((r) => {
				if (!r.message) return;
				frappe.show_alert({
					message: __("Đã báo khách: {0} ngày {1}", [r.message.loai, r.message.ngay_hen_giao]),
					indicator: "green",
				});
				frm.reload_doc();
			});
		},
		__("Hẹn lịch giao mới")
	);
}
