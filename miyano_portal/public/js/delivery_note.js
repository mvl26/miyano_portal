// `Portal Delivery Inspection.delivery_note` là field Data (không Link — xem
// docstring `_chan_trung_phieu_giao`), nên Frappe không dựng mục
// "Connections". Không có nút này thì nhân viên đứng ở phiếu giao không có
// đường nào sang biên bản kiểm hàng của khách.

frappe.ui.form.on("Delivery Note", {
	refresh(frm) {
		frm.add_custom_button(__("Biên bản kiểm hàng"), () => {
			frappe.set_route("List", "Portal Delivery Inspection", {
				delivery_note: frm.doc.name,
			});
		}, __("Miyano"));
	},
});
