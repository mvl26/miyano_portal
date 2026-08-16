// Nút xử lý biên bản kiểm hàng trên Desk.
//
// Nút chỉ hiện đúng trạng thái dùng được — không hiện một nút rồi để nó báo
// lỗi khi bấm. Ba hàm server đều tự kiểm role và tự kiểm trạng thái lần nữa;
// phần dưới đây là giao diện, không phải chốt chặn.

frappe.ui.form.on("Portal Delivery Inspection", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1 || frm.doc.trang_thai !== "Chờ xử lý") {
			// Phiếu giao gốc luôn đáng mở, kể cả khi không còn nút xử lý nào.
			them_link_phieu_giao(frm);
			return;
		}

		if (frm.doc.co_hang_hong) {
			frm.add_custom_button(__("Duyệt trả hàng"), () => {
				frappe.confirm(
					__("Duyệt trả hàng sẽ lập một phiếu giao ngược ở dạng NHÁP. Tồn kho chỉ được cộng lại khi kho ghi sổ phiếu đó."),
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
			}).addClass("btn-primary");
		} else {
			// Chỉ THIẾU hàng, không có gì để thu hồi — đóng biên bản tường minh
			// để khách thôi thấy "Chờ xử lý".
			frm.add_custom_button(__("Đánh dấu đã xử lý"), () => {
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
					__("Đánh dấu đã xử lý")
				);
			});
		}

		frm.add_custom_button(__("Từ chối"), () => {
			frappe.prompt(
				[{
					fieldname: "ly_do", fieldtype: "Small Text", reqd: 1,
					label: __("Lý do từ chối — khách sẽ đọc đúng dòng này"),
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
		});

		them_link_phieu_giao(frm);
	},
});

function them_link_phieu_giao(frm) {
	// `delivery_note`/`phieu_tra_hang` là field Data (không phải Link — xem
	// docstring `_chan_trung_phieu_giao`), nên Frappe không tự cho bấm sang.
	if (frm.doc.delivery_note) {
		frm.add_custom_button(__("Mở phiếu giao"), () => {
			frappe.set_route("Form", "Delivery Note", frm.doc.delivery_note);
		}, __("Chứng từ"));
	}
	if (frm.doc.phieu_tra_hang) {
		frm.add_custom_button(__("Mở phiếu trả hàng"), () => {
			frappe.set_route("Form", "Delivery Note", frm.doc.phieu_tra_hang);
		}, __("Chứng từ"));
	}
}
