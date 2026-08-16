// Nút xử lý biên bản kiểm hàng trên Desk.
//
// HAI nhóm nút cho HAI việc khác nhau, đúng như hai field khác nhau ở server:
//   * "Hàng hỏng"  → luồng trả hàng, đổi `trang_thai`.
//   * "Hàng thiếu" → giao bù / đổi ngày giao / đóng, đổi `xu_ly_thieu`.
// Một biên bản có thể có CẢ HAI. Bản trước gộp chung vào `trang_thai` nên
// duyệt trả hàng xong là nửa "thiếu" biến mất khỏi màn hình, không ai trả lời
// khách được nữa.
//
// Nút chỉ hiện đúng trạng thái dùng được — không hiện một nút rồi để nó báo
// lỗi khi bấm. Ba hàm server đều tự kiểm role và tự kiểm trạng thái lần nữa;
// phần dưới đây là giao diện, không phải chốt chặn.

frappe.ui.form.on("Portal Delivery Inspection", {
	refresh(frm) {
		them_link_chung_tu(frm);
		if (frm.doc.docstatus !== 1) return;

		if (frm.doc.trang_thai === "Chờ xử lý") {
			if (frm.doc.co_hang_hong) {
				frm.add_custom_button(__("Duyệt trả hàng"), () => duyet_tra(frm), __("Hàng hỏng"))
					.addClass("btn-primary");
			}
			frm.add_custom_button(__("Từ chối biên bản"), () => tu_choi(frm), __("Hàng hỏng"));
		}

		if (co_thieu_hang(frm.doc) && !frm.doc.xu_ly_thieu) {
			frm.add_custom_button(__("Hẹn lịch giao"), () => hen_giao(frm), __("Hàng thiếu"));
			frm.add_custom_button(__("Đóng, không giao bù"), () => da_xu_ly(frm), __("Hàng thiếu"));
		}
	},
});

// `co_thieu_hang` là method phía server, không phải field — tính lại từ chính
// các dòng đang hiển thị để nút bám đúng thứ người dùng đang nhìn thấy.
function co_thieu_hang(doc) {
	return (doc.items || []).some(
		(r) => flt(r.sl_giao) - flt(r.sl_nhan) - flt(r.sl_tra) > 0.000001
	);
}

function duyet_tra(frm) {
	frappe.confirm(
		__(
			"Duyệt trả hàng sẽ lập một phiếu giao ngược ở dạng NHÁP, ghi vào kho «Hàng trả về» " +
			"(không phải kho bán được). Tồn kho chỉ đổi khi kho ghi sổ phiếu đó."
		),
		() => {
			frappe.call({
				method: "miyano_portal.portal_kiem_hang.kiem_hang_duyet_tra",
				args: { name: frm.doc.name },
				freeze: true,
				freeze_message: __("Đang lập phiếu trả hàng…"),
			}).then((r) => {
				if (!r.message) return;
				frappe.show_alert({
					message: __("Đã lập phiếu trả hàng {0}", [r.message.phieu_tra_hang]),
					indicator: "green",
				});
				frm.reload_doc();
			});
		}
	);
}

function tu_choi(frm) {
	frappe.prompt(
		[{
			fieldname: "ly_do", fieldtype: "Small Text", reqd: 1,
			label: __("Lý do từ chối — khách sẽ đọc đúng dòng này"),
			description: __("Khách được phép kiểm lại và gửi biên bản mới sau khi bị từ chối."),
		}],
		(v) => {
			frappe.call({
				method: "miyano_portal.portal_kiem_hang.kiem_hang_tu_choi",
				args: { name: frm.doc.name, ly_do: v.ly_do },
				freeze: true,
			}).then(() => frm.reload_doc());
		},
		__("Từ chối biên bản")
	);
}

function hen_giao(frm) {
	frappe.prompt(
		[
			{
				fieldname: "loai", fieldtype: "Select", reqd: 1,
				label: __("Hình thức"),
				options: ["Sẽ giao bù", "Đã đổi ngày giao"].join("\n"),
				default: "Sẽ giao bù",
				description: __(
					"«Sẽ giao bù»: giữ nguyên ngày cam kết gốc, chỉ hẹn ngày giao phần thiếu. " +
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
				method: "miyano_portal.portal_kiem_hang.kiem_hang_hen_giao",
				args: {
					name: frm.doc.name, ngay_moi: v.ngay_moi,
					loai: v.loai, ly_do: v.ly_do,
				},
				freeze: true,
				freeze_message: __("Đang ghi lời hẹn lên đơn hàng và báo khách…"),
			}).then((r) => {
				if (!r.message) return;
				frappe.show_alert({
					message: __("Đã báo khách: {0} ngày {1}", [r.message.loai, r.message.ngay_hen_giao]),
					indicator: "green",
				});
				frm.reload_doc();
			});
		},
		__("Hẹn lịch giao cho phần hàng thiếu")
	);
}

function da_xu_ly(frm) {
	frappe.prompt(
		[{
			fieldname: "ghi_chu", fieldtype: "Small Text",
			label: __("Ghi chú gửi khách (không bắt buộc)"),
		}],
		(v) => {
			frappe.call({
				method: "miyano_portal.portal_kiem_hang.kiem_hang_da_xu_ly",
				args: { name: frm.doc.name, ghi_chu: v.ghi_chu },
				freeze: true,
			}).then(() => frm.reload_doc());
		},
		__("Đóng phần hàng thiếu")
	);
}

function them_link_chung_tu(frm) {
	// `delivery_note`/`sales_order`/`phieu_tra_hang` là field Data (không
	// Link — xem docstring `_chan_trung_phieu_giao`), nên Frappe không cho
	// bấm sang. Ba nút dưới đây là đường đi duy nhất.
	const mo = (dt, ten) => () => frappe.set_route("Form", dt, ten);
	if (frm.doc.delivery_note) {
		frm.add_custom_button(__("Phiếu giao"), mo("Delivery Note", frm.doc.delivery_note), __("Chứng từ"));
	}
	if (frm.doc.sales_order) {
		frm.add_custom_button(__("Đơn hàng"), mo("Sales Order", frm.doc.sales_order), __("Chứng từ"));
	}
	if (frm.doc.phieu_tra_hang) {
		frm.add_custom_button(__("Phiếu trả hàng"), mo("Delivery Note", frm.doc.phieu_tra_hang), __("Chứng từ"));
	}
}
