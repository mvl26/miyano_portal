"""Bỏ vòng báo giá trên Sales Order (chủ dự án chốt 14/10/2026).

Từ spec 2026-10-12, mọi dòng khách gõ tay và mọi mặt hàng chưa có giá đi qua
Quotation; Sales Order từ cổng chỉ còn dòng đã có giá, nên đơn chỉ cần Miyano
xác nhận. Patch này dọn phần còn lại của vòng báo giá cũ trên đơn:

1. Đơn đang ở "Chờ khách đồng ý" / "Báo giá hết hạn" về "Chờ xác nhận" để
   Miyano xử lý tiếp. Đơn "Khách huỷ" sang "Từ chối" (ghi lý do nếu trống).
   Ghi bằng `db.set_value`, không qua `apply_workflow`: bước chuyển cũ sắp
   bị xoá, và không được bắn email "Đơn bị từ chối" cho đơn khách đã tự huỷ.
2. Dòng đặt ngoài của Sales Order được chép vào một Comment trên chính đơn,
   rồi xoá. Bảng con `Sales Order Dat Ngoai Item` ở lại: Quotation và phiếu
   đề xuất vẫn dùng nó.
3. Xoá Custom Field `custom_dat_ngoai`, `custom_ngay_gui_khach_duyet` của
   Sales Order.
4. Xoá trạng thái và bước chuyển của vòng báo giá khỏi workflow
   `Sales Order - Client Portal`. Không xoá Workflow State / Action Master:
   workflow của Quotation dùng chung tên.
5. Xoá mẫu in "Miyano - Báo giá" và thông báo "Portal - Báo giá sẵn sàng"
   của Sales Order (bản cho Quotation giữ nguyên).

Chạy lại được: mọi bước đều kiểm trước khi làm. Đứng SAU các patch v1_4,
v1_8, v1_18, v1_41 (chúng thêm đúng những thứ này), nên `install.after_install`
chạy lại cả chuỗi trên site mới vẫn ra workflow đã dọn.
"""

import frappe
from frappe.utils import escape_html

WF = "Sales Order - Client Portal"
TT_CHO_XAC_NHAN = "Chờ xác nhận"
TT_TU_CHOI = "Từ chối"
VE_CHO_XAC_NHAN = ("Chờ khách đồng ý", "Báo giá hết hạn")
VE_TU_CHOI = ("Khách huỷ",)
TT_BO = set(VE_CHO_XAC_NHAN) | set(VE_TU_CHOI)
HD_BO = {"Gửi khách duyệt", "Khách đồng ý", "Khách không đồng ý", "Báo giá hết hạn",
         "Khách huỷ", "Mở lại"}
FIELD_BO = ("custom_dat_ngoai", "custom_ngay_gui_khach_duyet")
MAU_IN_BO = "Miyano - Báo giá"
THONG_BAO_BO = "Portal - Báo giá sẵn sàng"
LY_DO_KHACH_HUY = "Khách huỷ đơn khi còn ở vòng báo giá cũ (chuyển trạng thái tự động 14/10/2026)."


def execute():
	_chuyen_trang_thai_don()
	_chep_dat_ngoai_vao_comment()
	_xoa_field()
	_don_workflow()
	_xoa_mau_in_va_thong_bao()


def _chuyen_trang_thai_don():
	for ten in frappe.get_all(
		"Sales Order", filters={"workflow_state": ["in", VE_CHO_XAC_NHAN]}, pluck="name"
	):
		frappe.db.set_value(
			"Sales Order", ten, "workflow_state", TT_CHO_XAC_NHAN, update_modified=False
		)
	for d in frappe.get_all(
		"Sales Order", filters={"workflow_state": ["in", VE_TU_CHOI]},
		fields=["name", "custom_ly_do_tu_choi"],
	):
		gia_tri = {"workflow_state": TT_TU_CHOI}
		if not (d.custom_ly_do_tu_choi or "").strip():
			gia_tri["custom_ly_do_tu_choi"] = LY_DO_KHACH_HUY
		frappe.db.set_value("Sales Order", d.name, gia_tri, update_modified=False)


def _chep_dat_ngoai_vao_comment():
	dong = frappe.get_all(
		"Sales Order Dat Ngoai Item",
		filters={"parenttype": "Sales Order"},
		fields=["parent", "ten_hang", "dvt", "so_luong", "model_ma", "hang_san_xuat",
		        "item_khop", "da_xu_ly", "da_chuyen", "ghi_chu"],
		order_by="parent, idx",
	)
	theo_don: dict[str, list] = {}
	for d in dong:
		theo_don.setdefault(d.parent, []).append(d)
	for ten, ds in theo_don.items():
		if not frappe.db.exists("Sales Order", ten):
			continue
		hang = []
		for d in ds:
			if d.da_chuyen:
				tinh_trang = f"đã chuyển thành dòng hàng {d.item_khop}"
			elif d.item_khop:
				tinh_trang = f"đã khớp mã {d.item_khop}, CHƯA có dòng hàng trên đơn"
			else:
				tinh_trang = "CHƯA khớp mã"
			mo_ta = ", ".join(x for x in (d.model_ma, d.hang_san_xuat, d.ghi_chu) if x)
			hang.append(
				f"<li>{escape_html(d.ten_hang or '?')} — {d.so_luong:g} {escape_html(d.dvt or '')}"
				+ (f" ({escape_html(mo_ta)})" if mo_ta else "")
				+ f": {escape_html(tinh_trang)}</li>"
			)
		frappe.get_doc({
			"doctype": "Comment", "comment_type": "Comment",
			"reference_doctype": "Sales Order", "reference_name": ten,
			"content": (
				"Đơn hàng không còn bảng «Dòng đặt ngoài» (hàng khách gõ tay đi qua "
				"yêu cầu báo giá). Các dòng khách đã gõ trên đơn này:<ul>"
				+ "".join(hang) + "</ul>"
			),
		}).insert(ignore_permissions=True)
	frappe.db.delete("Sales Order Dat Ngoai Item", {"parenttype": "Sales Order"})


def _xoa_field():
	# Section Break hẹn giao đang neo sau bảng sắp xoá.
	for cf in frappe.get_all(
		"Custom Field",
		filters={"dt": "Sales Order", "insert_after": ["in", FIELD_BO]},
		pluck="name",
	):
		frappe.db.set_value("Custom Field", cf, "insert_after", "custom_request_id")
	for fieldname in FIELD_BO:
		ten = frappe.db.get_value("Custom Field", {"dt": "Sales Order", "fieldname": fieldname})
		if ten:
			frappe.delete_doc("Custom Field", ten, ignore_permissions=True, force=True)
		if frappe.db.has_column("Sales Order", fieldname):
			frappe.db.sql_ddl(f"alter table `tabSales Order` drop column `{fieldname}`")
	frappe.clear_cache(doctype="Sales Order")


def _don_workflow():
	if not frappe.db.exists("Workflow", WF):
		return
	wf = frappe.get_doc("Workflow", WF)
	truoc = (len(wf.states), len(wf.transitions))
	wf.transitions = [
		t for t in wf.transitions
		if t.state not in TT_BO and t.next_state not in TT_BO and t.action not in HD_BO
	]
	wf.states = [s for s in wf.states if s.state not in TT_BO]
	if (len(wf.states), len(wf.transitions)) != truoc:
		wf.flags.ignore_permissions = True
		wf.save()


def _xoa_mau_in_va_thong_bao():
	if frappe.db.exists("Notification", THONG_BAO_BO):
		frappe.delete_doc("Notification", THONG_BAO_BO, ignore_permissions=True, force=True)
	if frappe.db.exists("Print Format", MAU_IN_BO):
		frappe.delete_doc("Print Format", MAU_IN_BO, ignore_permissions=True, force=True)
