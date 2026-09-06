// Vẽ ẢNH vào ô "Ảnh mặt hàng" của dòng "hàng chưa có trong hệ thống".
//
// Chủ đầu tư báo 06/09/2026: ô ảnh hiện nguyên chuỗi
// `["/private/files/CR03_....png"]` thay vì cái ảnh.
//
// Đúng: `anh` là `Small Text` chứa JSON — Frappe in ra y nguyên thứ nó lưu.
// Khối tóm tắt ở đầu form (`sales_order.js`) có vẽ ảnh, nhưng người khớp hàng
// làm việc TRONG dòng lưới, và ở đó họ vẫn thấy chuỗi thô.
//
// Sửa: `anh` chuyển sang `hidden` (dữ liệu giữ nguyên, cổng và các khối khác
// vẫn đọc), và một ô `HTML` tên `anh_xem` đứng ngay trên nó nhận ảnh thật.
//
// ĐẶT Ở FILE RIÊNG, đăng ký theo BẢNG CON chứ không theo doctype cha: cùng
// một bảng con `Sales Order Dat Ngoai Item` sống trên CẢ `Sales Order` LẪN
// `Portal De Xuat Mua`. Một handler, hai nơi dùng — thay vì hai bản sao sớm
// muộn trôi lệch.
//
// `parentfield` đọc TỪ CHÍNH DÒNG, không gõ cứng: nó là `custom_dat_ngoai`
// trên đơn hàng và `dat_ngoai` trên phiếu. Gõ cứng một tên là ô ảnh chỉ chạy
// ở một trong hai màn, và không ai biết màn kia hỏng.

frappe.ui.form.on("Sales Order Dat Ngoai Item", {
	form_render(frm, cdt, cdn) {
		const row = locals[cdt] && locals[cdt][cdn];
		if (!row) return;

		const grid = frm.get_field(row.parentfield) && frm.get_field(row.parentfield).grid;
		const grid_row = grid && grid.grid_rows_by_docname && grid.grid_rows_by_docname[cdn];
		const o = grid_row && grid_row.grid_form && grid_row.grid_form.fields_dict
			&& grid_row.grid_form.fields_dict.anh_xem;
		if (!o) return;

		let ds = [];
		try {
			const parsed = JSON.parse(row.anh || "[]");
			if (Array.isArray(parsed)) ds = parsed.filter((x) => typeof x === "string" && x);
		} catch (e) {
			// Field hỏng (bản ghi cũ, ai đó gõ tay) KHÔNG được làm chết cả
			// dòng — người khớp hàng vẫn phải đọc được các trường còn lại.
			ds = [];
		}

		if (!ds.length) {
			o.$wrapper.html(
				row.khong_co_anh
					? `<p class="text-muted">${__("Khách không chụp được ảnh — xem 'Mô tả nhận dạng' bên dưới.")}</p>`
					: `<p class="text-muted">${__("Không có ảnh.")}</p>`
			);
			return;
		}

		const esc = frappe.utils.escape_html;
		// Kích thước bằng `rem`, lưới `auto-fill`: co giãn theo bề ngang ô
		// lẫn cỡ chữ người dùng đặt — cùng luật đã áp cho khối bên cổng.
		o.$wrapper.html(
			`<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,8rem),1fr));gap:.5rem">
			   ${ds.map((u) => `<a href="${esc(u)}" target="_blank" rel="noopener" title="${__("Mở ảnh gốc")}">
			     <img src="${esc(u)}" alt="${__("Ảnh mặt hàng")}"
			          style="width:100%;aspect-ratio:1;object-fit:cover;border:1px solid var(--border-color);border-radius:.375rem">
			   </a>`).join("")}
			 </div>`
		);
	},
});
