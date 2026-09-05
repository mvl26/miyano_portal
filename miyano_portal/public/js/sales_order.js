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

		hien_thong_tin_hang_moi(frm);
	},
});

// CR-03 trên Desk — hiện THỨ KHÁCH ĐÃ KHAI cho hàng chưa có mã.
//
// Chủ đầu tư báo 05/09/2026: *"sao không hiển thị các thông tin mà khách
// hàng đã nhập cho hàng mới trên phần back của Miyano"*. Đúng, và đây là
// lỗi của chính bản CR-03: chín trường được thêm vào doctype nhưng bảy
// trong số đó để `in_list_view: 0`, tức chỉ hiện khi bung TỪNG dòng lưới —
// và ô `anh` là Small Text chứa JSON THÔ, nên người khớp hàng nhìn thấy
// chuỗi `["/private/files/CR03_....jpg"]` chứ không thấy ảnh.
//
// Khách bỏ công chụp nhãn hộp và gõ model/hãng/quy cách CHÍNH LÀ để Miyano
// tìm được nguồn. Để nó nằm sau hai cú bấm và một chuỗi JSON là vứt bỏ đúng
// thứ CR-03 sinh ra để lấy.
//
// Dựng MỘT khối đọc-được ngay trên form, không sửa lưới: lưới đã kín ngân
// sách cột (xem `description` của `model_ma`), và nhồi thêm vào đó sẽ lại
// đẩy rơi cột khớp mã như lần trước.
function hien_thong_tin_hang_moi(frm) {
	const dong = (frm.doc.custom_dat_ngoai || []).filter(
		(d) => d.model_ma || d.hang_san_xuat || d.nuoc_san_xuat || d.quy_cach
			|| d.ncc_hien_tai || d.gia_hien_tai || d.anh || d.mo_ta_nhan_dang
	);
	if (!dong.length) return;

	const esc = frappe.utils.escape_html;
	const o = (v) => (v ? esc(String(v)) : "");

	const the = dong.map((d) => {
		let anh = [];
		try {
			const ds = JSON.parse(d.anh || "[]");
			if (Array.isArray(ds)) anh = ds.filter((x) => typeof x === "string" && x);
		} catch (e) {
			// Field hỏng không được làm chết cả khối — người khớp hàng vẫn
			// phải đọc được các trường chữ để mà làm việc.
			anh = [];
		}
		const hinh = anh.length
			? `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,7rem),1fr));gap:.5rem;margin:.5rem 0">
			     ${anh.map((u) => `<a href="${esc(u)}" target="_blank" rel="noopener">
			       <img src="${esc(u)}" style="width:100%;aspect-ratio:1;object-fit:cover;border:1px solid var(--border-color);border-radius:.375rem">
			     </a>`).join("")}
			   </div>`
			: (d.khong_co_anh
				? `<p style="margin:.4rem 0 0"><b>⚠ Khách không chụp được ảnh.</b> Mô tả nhận dạng:<br>${o(d.mo_ta_nhan_dang)}</p>`
				: "");

		const o_muc = (nhan, gt) => gt
			? `<div><div style="font-size:.7rem;text-transform:uppercase;letter-spacing:.04em;color:var(--text-muted)">${nhan}</div>
			     <div style="font-weight:500">${o(gt)}</div></div>`
			: "";

		return `<div style="border:1px solid var(--border-color);border-radius:.5rem;padding:.75rem;margin-bottom:.6rem">
			<b>${o(d.ten_hang)}</b> — ${o(d.so_luong)} ${o(d.dvt)}
			${d.item_khop ? `<span style="color:var(--green-600)">· đã khớp ${o(d.item_khop)}</span>` : ""}
			${hinh}
			<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,12rem),1fr));gap:.5rem 1.25rem;margin-top:.6rem">
				${o_muc("Model / mã catalogue", d.model_ma)}
				${o_muc("Hãng sản xuất", d.hang_san_xuat)}
				${o_muc("Nước sản xuất", d.nuoc_san_xuat)}
				${o_muc("Quy cách", d.quy_cach)}
				${o_muc("Khoa đang mua của", d.ncc_hien_tai)}
				${o_muc("Giá khoa đang mua", d.gia_hien_tai ? format_currency(d.gia_hien_tai) : "")}
			</div>
			${d.ghi_chu ? `<p style="margin:.5rem 0 0">${o(d.ghi_chu)}</p>` : ""}
		</div>`;
	}).join("");

	frm.dashboard.add_section(
		`<div style="padding:.5rem 0">${the}</div>`,
		__("Hàng chưa có mã — thông tin khách khai")
	);
}

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
