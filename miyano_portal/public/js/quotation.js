// Form Quotation — yêu cầu báo giá từ cổng khách hàng (spec 2026-10-12 §7).
frappe.ui.form.on("Quotation", {
	setup(frm) {
		// `refresh` dưới đây chạy TRƯỚC `refresh` của lớp `erpnext.selling.
		// QuotationController` — nơi THÊM nút «Tạo → Đơn bán hàng» và «Đặt là
		// đã mất» — nên gỡ nút ở đó là gỡ thứ chưa có. `setTimeout(…, 0)` và
		// `frappe.after_ajax` cũng chạy quá sớm: script_manager chờ giữa hai
		// handler (đo trên trình duyệt thật 13/10/2026). `cscript.custom_refresh`
		// là handler kiểu cũ mà script_manager xếp NGAY SAU `cscript.refresh`.
		const truoc = frm.cscript.custom_refresh;
		frm.cscript.custom_refresh = function (...tham_so) {
			const kq = truoc && truoc.apply(this, tham_so);
			go_nut_bao_gia_cong_da_dong_y(frm);
			return kq;
		};
	},
	refresh(frm) {
		miyano_portal.hien_thong_tin_hang_moi(frm);
		dan_toi_don_da_sinh(frm);
	},
});

// Báo giá của cổng đã được khách đồng ý: đơn hàng ĐÃ được hệ thống sinh sẵn
// (`bao_gia.dong_y`). Hai nút chuẩn của ERPNext ở đây chỉ gây hại: «Tạo → Đơn
// bán hàng» cho ra đơn thứ hai (ERPNext chỉ trừ số "đã đặt" theo đơn ĐÃ
// Submit), «Đặt là đã mất» đánh dấu mất một báo giá đang có đơn. Chốt thật nằm
// ở server (`bao_gia.chan_don_thu_hai_tu_bao_gia_cong`, `chan_huy_khi_con_don`);
// ở đây chỉ dẹp lối bấm nhầm. Báo giá nội bộ không bị đụng tới.
function la_bao_gia_cong_da_dong_y(frm) {
	return frm.doc.custom_nguon_don === "Client Portal" && frm.doc.docstatus === 1;
}

function go_nut_bao_gia_cong_da_dong_y(frm) {
	if (!la_bao_gia_cong_da_dong_y(frm)) return;
	frm.remove_custom_button(__("Sales Order"), __("Create"));
	frm.remove_custom_button(__("Set as Lost"));
}

function dan_toi_don_da_sinh(frm) {
	if (!la_bao_gia_cong_da_dong_y(frm) || !frm.doc.custom_request_id) return;
	const ten = frm.doc.name;
	frappe.db.get_value(
		"Sales Order", { custom_request_id: frm.doc.custom_request_id + ":don" }, "name"
	).then((r) => {
		const don = r && r.message && r.message.name;
		// Người dùng đã chuyển sang báo giá khác trong lúc chờ: bỏ kết quả cũ.
		if (!don || frm.doc.name !== ten) return;
		frm.set_intro(
			__("Khách đã đồng ý trên cổng — hệ thống đã sinh đơn hàng {0}. Không tạo đơn thứ hai từ báo giá này.", [
				`<a href="/app/sales-order/${encodeURIComponent(don)}">${frappe.utils.escape_html(don)}</a>`,
			]),
			"blue"
		);
	});
}
