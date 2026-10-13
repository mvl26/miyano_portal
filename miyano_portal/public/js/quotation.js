// Form Quotation — yêu cầu báo giá từ cổng khách hàng (spec 2026-10-12 §7).
frappe.ui.form.on("Quotation", {
	refresh(frm) {
		miyano_portal.hien_thong_tin_hang_moi(frm);
	},
});
