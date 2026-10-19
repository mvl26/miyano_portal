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

		hien_doi_sanh_ton(frm);
		hien_canh_bao_hsd(frm);
		to_do_ket_qua_hsd(frm);
		nut_ngoai_le_hsd(frm);
	},
});

// HSD tối thiểu theo yêu cầu khách (spec 2026-10-19 §4.3, §4.7).
// Quyền ghi/gỡ KHỚP `han_dung_khach.VAI_TRO_NGOAI_LE`; chốt thật ở máy chủ.
const VAI_NGOAI_LE_HSD = ["Sales User", "Sales Manager", "System Manager"];

function dong_hsd_khong_dat(frm) {
	return (frm.doc.items || []).filter((d) => d.custom_ket_qua_hsd === "Không đạt");
}

function hien_canh_bao_hsd(frm) {
	const esc = frappe.utils.escape_html;
	const dong = dong_hsd_khong_dat(frm);
	if (!dong.length) return;
	const ngay = (v) => (v ? frappe.datetime.str_to_user(v) : "—");
	const li = dong.map((d) => {
		const ngoai_le = d.custom_ngoai_le_hsd
			? `đã ghi ngoại lệ, khách chấp nhận đến ${ngay(d.custom_ngoai_le_hsd_den)}`
			: "chưa có ngoại lệ";
		return `<li>Dòng ${d.idx} – ${esc(d.item_code || "")}: HSD yêu cầu đến ${ngay(d.custom_hsd_yeu_cau_den)}, ` +
			`HSD tồn tốt nhất ${ngay(d.custom_hsd_ton_tot_nhat)}, ${ngoai_le}</li>`;
	}).join("");
	frm.set_intro(
		`<b>${__("Không đáp ứng HSD khách yêu cầu")}</b><ul style="margin:.25rem 0 0 1rem">${li}</ul>`,
		"orange"
	);
}

// Tô đỏ ô kết quả "Không đạt" trên lưới mặt hàng.
function to_do_ket_qua_hsd(frm) {
	const luoi = frm.fields_dict.items && frm.fields_dict.items.grid;
	const df = luoi && luoi.get_docfield("custom_ket_qua_hsd");
	if (!df || df._mvl_to_do) return;
	df._mvl_to_do = true;
	df.formatter = (value, field, options, doc) => {
		const text = frappe.utils.escape_html(__(value || ""));
		return value === "Không đạt"
			? `<span class="indicator-pill red">${text}</span>`
			: text;
	};
	luoi.refresh();
}

function nut_ngoai_le_hsd(frm) {
	if (frm.doc.docstatus !== 1 || ["Closed", "Completed"].includes(frm.doc.status)) return;
	if (!VAI_NGOAI_LE_HSD.some((v) => frappe.user_roles.includes(v))) return;
	const dong = (frm.doc.items || []).filter(
		(d) => d.custom_hsd_toi_thieu_thang > 0 && d.custom_ket_qua_hsd && d.custom_ket_qua_hsd !== "Không áp dụng"
	);
	if (!dong.length) return;
	frm.add_custom_button(__("Ghi ngoại lệ HSD"), () => hop_thoai_ngoai_le(frm, dong, true), __("Miyano"));
	if (dong.some((d) => d.custom_ngoai_le_hsd)) {
		frm.add_custom_button(__("Gỡ ngoại lệ HSD"), () => hop_thoai_ngoai_le(frm, dong, false), __("Miyano"));
	}
}

function hop_thoai_ngoai_le(frm, dong, ghi) {
	const nhan = (d) => `${d.idx} – ${d.item_code}`;
	const ds = ghi ? dong : dong.filter((d) => d.custom_ngoai_le_hsd);
	const tim = (v) => ds.find((d) => nhan(d) === v);
	const fields = [
		{
			fieldname: "dong", fieldtype: "Select", reqd: 1, label: __("Dòng hàng"),
			options: ds.map(nhan).join("\n"), default: nhan(ds[0]),
			change() {
				const d = tim(this.get_value());
				if (ghi && d) hop.set_value("chap_nhan_den", d.custom_hsd_ton_tot_nhat || "");
			},
		},
	];
	if (ghi) {
		fields.push({
			fieldname: "chap_nhan_den", fieldtype: "Date", reqd: 1,
			label: __("Khách chấp nhận hàng đến ngày"), default: ds[0].custom_hsd_ton_tot_nhat,
		});
	}
	fields.push({
		fieldname: "ly_do", fieldtype: "Small Text", reqd: 1,
		label: ghi ? __("Lý do / người khách xác nhận") : __("Lý do gỡ"),
	});
	const hop = new frappe.ui.Dialog({
		title: ghi ? __("Ghi ngoại lệ HSD") : __("Gỡ ngoại lệ HSD"),
		fields,
		primary_action_label: ghi ? __("Ghi ngoại lệ") : __("Gỡ ngoại lệ"),
		primary_action(v) {
			const d = tim(v.dong);
			if (!d) return;
			frappe.call({
				method: "miyano_portal.han_dung_khach." + (ghi ? "ghi_ngoai_le" : "go_ngoai_le"),
				args: ghi
					? { so: frm.doc.name, dong: d.name, chap_nhan_den: v.chap_nhan_den, ly_do: v.ly_do }
					: { so: frm.doc.name, dong: d.name, ly_do: v.ly_do },
				freeze: true,
			}).then((r) => {
				if (!r.message) return;
				hop.hide();
				frappe.show_alert({
					message: ghi ? __("Đã ghi ngoại lệ HSD") : __("Đã gỡ ngoại lệ HSD"),
					indicator: "green",
				});
				frm.reload_doc();
			});
		},
	});
	hop.show();
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

// Đối sánh tồn kho của MIYANO (spec 2026-10-12).
//
// Danh sách vai phải KHỚP `doi_sanh_ton.ROLE_NOI_BO` ở máy chủ (có bài test
// canh). Lọc ở đây không phải là chốt quyền — chốt thật nằm ở máy chủ — mà
// để người không có vai mở đơn không bị hộp báo "không có quyền" bật lên.
const VAI_XEM_TON = [
	"System Manager", "Sales Manager", "Sales User",
	"Stock Manager", "Stock User", "Purchase Manager", "Purchase User",
];

const NHAN_DE_XUAT = {
	du: (d, so) => `<span style="color:var(--green-600)">Đủ hàng</span>`,
	can_mua: (d, so) => `<b style="color:var(--red-600)">Cần mua ${so(d.can_mua)}</b>`,
	mr_mot_phan: (d, so) =>
		`Đã có MR ${so(d.mr_da_phu)} · <b style="color:var(--red-600)">cần mua thêm ${so(d.can_mua)}</b>`,
	da_co_mr: (d, so) => `Đã có MR ${so(d.mr_da_phu)}`,
};

// Bảng nằm NGAY DƯỚI lưới mặt hàng ở tab đầu, KHÔNG dùng
// `frm.dashboard.add_section`: form Sales Order chia tab, và mọi khối
// dashboard nằm trong tab "Connections" — đặt ở đó thì mở đơn ra không thấy
// bảng (bắt được khi mở trình duyệt thật 12/10/2026).
//
// Vì không còn do dashboard quản, Frappe KHÔNG tự dọn khối này. Một form dùng
// lại cho mọi đơn, nên phải gỡ bảng cũ trước mọi lối thoát sớm — không thì
// đơn mới (chưa lưu) hiện bảng tồn của đơn vừa xem trước đó.
function go_doi_sanh_ton(frm) {
	$(frm.wrapper).find(".mvl-doi-sanh-ton").remove();
}

function hien_doi_sanh_ton(frm) {
	go_doi_sanh_ton(frm);
	// Mỗi lần gọi một số thứ tự: phản hồi CHẬM của lần refresh trước không
	// được vẽ đè hay thêm lại nút mà lần sau đã cho là không còn.
	frm._dst_lan = (frm._dst_lan || 0) + 1;
	const lan = frm._dst_lan;
	if (frm.is_new()) return;
	// Đơn đã huỷ / đã đóng không còn giao: "Thiếu k/n dòng" màu đỏ ở đó là
	// một lời kêu gọi hành động sai.
	if (frm.doc.docstatus === 2 || frm.doc.status === "Closed") return;
	if (!VAI_XEM_TON.some((v) => frappe.user_roles.includes(v))) return;

	const ten = frm.doc.name;
	frappe.call({
		method: "miyano_portal.doi_sanh_ton.doi_sanh_ton",
		args: { order: ten },
	}).then((r) => {
		// Người dùng đã chuyển sang đơn khác trong lúc chờ: bỏ kết quả cũ.
		if (frm.doc.name !== ten || lan !== frm._dst_lan || !r.message) return;
		try {
			ve_doi_sanh_ton(frm, r.message);
		} catch (e) {
			// Vẽ hỏng không được để form mất cả bảng lẫn lời giải thích.
			console.error(e);
			go_doi_sanh_ton(frm);
			ve_doi_sanh_ton(frm, { loi: __("Không hiển thị được bảng đối sánh tồn kho.") });
			return;
		}
		if (r.message.co_the_tao_mr) {
			frm.add_custom_button(
				__("Tạo MR cho phần thiếu"), () => tao_mr_phan_thieu(frm), __("Miyano")
			);
		}
	});
}

function ve_doi_sanh_ton(frm, bang) {
	const esc = frappe.utils.escape_html;
	const so = (v) => (v === null || v === undefined
		? "—"
		: format_number(v, null, Number.isInteger(v) ? 0 : 3));

	const luoi = frm.fields_dict.items && frm.fields_dict.items.$wrapper;
	if (!luoi || !luoi.length) return;
	// `refresh` có thể chạy hai lần sát nhau; mỗi lần là một lời gọi riêng.
	// Gỡ khối cũ trước khi vẽ, không thì form có hai bảng.
	go_doi_sanh_ton(frm);

	let than;
	if (bang.loi) {
		than = `<p class="text-muted">${esc(bang.loi)}</p>`;
	} else {
		const tong = bang.tong.so_thieu
			? `<b style="color:var(--red-600)">Thiếu ${bang.tong.so_thieu}/${bang.tong.so_dong} dòng</b>`
			: (bang.tong.so_dong
				? `<b style="color:var(--green-600)">Đủ hàng cả đơn</b>`
				: `<span class="text-muted">Không có dòng nào tra được tồn</span>`);

		const hang = bang.dong.map((d) => {
			const mr = (d.mr || []).map(
				(m) => `<a href="/app/material-request/${encodeURIComponent(m)}">${esc(m)}</a>`
			).join(", ");
			const de_xuat = d.ly_do
				? `<span class="text-muted">${esc(d.ly_do)}</span>`
				: (NHAN_DE_XUAT[d.de_xuat] || (() => "—"))(d, so) + (mr ? `<br>${mr}` : "");
			// Hai đơn đã xác nhận tranh cùng một lượng tồn thì cả hai đều báo
			// thiếu — dòng này cho nhân viên thấy vì sao, trước khi lập hai
			// MR cho cùng một chỗ thiếu.
			const giu = d.giu_don_khac
				? `<div class="text-muted" style="font-size:.75rem">Đơn khác đã giữ: ${so(d.giu_don_khac)} ${esc(d.dvt || "")}</div>`
				: "";
			const bo = d.bo_trong_don
				? `<div class="text-muted" style="font-size:.75rem">Bộ sản phẩm trong đơn này dùng: ${so(d.bo_trong_don)} ${esc(d.dvt || "")}</div>`
				: "";
			const nhap = d.don_nhap_khac
				? `<div class="text-muted" style="font-size:.75rem">Đơn nháp khác đang chờ: ${so(d.don_nhap_khac.sl)} ${esc(d.dvt || "")} (${d.don_nhap_khac.so_don} đơn)</div>`
				: "";
			return `<tr>
				<td>${esc(d.item_name || "")}
					${d.item_code ? `<div class="text-muted" style="font-size:.75rem">${esc(d.item_code)}${d.kho ? " · " + esc(d.kho) : ""}</div>` : ""}
				</td>
				<td>${esc(d.dvt || "")}</td>
				<td class="text-right">${so(d.sl_yeu_cau)}</td>
				<td class="text-right">${so(d.ton_hien_tai)}</td>
				<td class="text-right">${so(d.ton_kha_dung)}${giu}${bo}${nhap}</td>
				<td class="text-right">${d.sl_thieu ? `<b style="color:var(--red-600)">${so(d.sl_thieu)}</b>` : so(d.sl_thieu)}</td>
				<td>${de_xuat}</td>
			</tr>`;
		}).join("");

		than = `<p style="margin:0 0 .5rem">${tong}
				<span class="text-muted"> · tính theo bản đơn đã lưu, đơn vị tồn kho</span></p>
			<div style="overflow-x:auto">
			<table class="table table-bordered" style="margin:0;font-size:.85rem">
				<thead><tr>
					<th>Mặt hàng</th><th>ĐVT</th>
					<th class="text-right">SL yêu cầu</th>
					<th class="text-right">Tồn hiện tại</th>
					<th class="text-right">Tồn có thể sử dụng</th>
					<th class="text-right">SL thiếu</th>
					<th>Đề xuất</th>
				</tr></thead>
				<tbody>${hang}</tbody>
			</table></div>`;
	}

	luoi.after(
		`<div class="mvl-doi-sanh-ton" style="margin:1rem 0 .5rem">
			<div style="font-weight:600;margin-bottom:.4rem">${__("Đối sánh tồn kho")}</div>
			${than}
		</div>`
	);
}

function tao_mr_phan_thieu(frm) {
	frappe.confirm(
		__("Tạo một yêu cầu mua hàng NHÁP cho các dòng đang thiếu? Số lượng được tính lại theo tồn kho lúc này."),
		() => {
			frappe.call({
				method: "miyano_portal.doi_sanh_ton.tao_mr_phan_thieu",
				args: { order: frm.doc.name },
				freeze: true,
				freeze_message: __("Đang tạo yêu cầu mua hàng…"),
			}).then((r) => {
				if (!r.message) return;
				frappe.show_alert({
					message: __("Đã tạo {0} (nháp) — {1} dòng", [r.message.name, r.message.so_dong]),
					indicator: "green",
				});
				frappe.set_route("Form", "Material Request", r.message.name);
			});
		}
	);
}
