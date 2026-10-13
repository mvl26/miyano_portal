// Khối "Hàng chưa có mã — thông tin khách khai" trên form Sales Order VÀ
// Quotation (spec 2026-10-12 §7). Cả hai doctype mang bảng `custom_dat_ngoai`
// cùng bảng con, nên một hàm phục vụ cả hai; file này nạp TRƯỚC file form
// trong `hooks.py::doctype_js`.
frappe.provide("miyano_portal");

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
//
// Khối nằm NGAY DƯỚI bảng `custom_dat_ngoai`, không qua `frm.dashboard`:
// Frappe 15 đặt mọi khối dashboard vào tab "Liên kết", còn người khớp mã làm
// việc ở tab "Chi tiết" — mở chứng từ ra là không thấy ảnh và mô tả của
// khách (lộ khi chạy trình duyệt thật 13/10/2026; cùng lỗi và cùng cách chữa
// với bảng "Đối sánh tồn kho" trong `sales_order.js`).
//
// KHÔNG khai `const`/`let` ở cấp ngoài cùng của file này: Frappe chạy JS của
// form như một thẻ <script> toàn cục, và file này nạp cho HAI doctype — lần
// nạp thứ hai sẽ ném "Identifier has already been declared" và làm chết toàn
// bộ JS của form đó.
miyano_portal.hien_thong_tin_hang_moi = function (frm) {
	const LOP_KHOI_KHACH_KHAI = "mvl-hang-moi-khach-khai";
	// Khối không do dashboard quản nên Frappe không tự dọn, và một form dùng
	// lại cho mọi chứng từ: gỡ khối cũ TRƯỚC mọi lối thoát sớm.
	$(frm.wrapper).find("." + LOP_KHOI_KHACH_KHAI).remove();
	const bang = frm.fields_dict.custom_dat_ngoai && frm.fields_dict.custom_dat_ngoai.$wrapper;
	if (!bang || !bang.length) return;

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

	$(`<div class="${LOP_KHOI_KHACH_KHAI}" style="margin:.25rem 0 1rem">
		<div class="text-muted" style="font-size:.75rem;text-transform:uppercase;letter-spacing:.04em;margin-bottom:.5rem">
			${__("Hàng chưa có mã — thông tin khách khai")}
		</div>
		${the}
	</div>`).insertAfter(bang);
};
