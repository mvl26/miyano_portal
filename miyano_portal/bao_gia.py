"""Yêu cầu báo giá bằng Quotation (spec 2026-10-12).

Một yêu cầu báo giá của khách là một Quotation đi workflow `WORKFLOW`. Sales
Order chỉ sinh ra khi khách đồng ý (`dong_y`). Tài khoản cổng KHÔNG có DocPerm
trên Quotation: mọi hàm ghi ở đây chạy bước chuyển trạng thái dưới
`nang_quyen.quyen_he_thong()`, và NGƯỜI GỌI (endpoint trong `api/portal.py`)
phải kiểm quyền của khách trên đúng báo giá đó trước khi gọi vào đây.
"""

import frappe

WORKFLOW = "Quotation - Client Portal"
NGUON_CONG = "Client Portal"
LOAI_DON_THEO_BAO_GIA = "Theo báo giá"
HAU_TO_DON = ":don"

TT_CHO_MIYANO = "Chờ Miyano báo giá"
TT_CHO_KHACH = "Chờ khách đồng ý"
TT_DA_DONG_Y = "Khách đã đồng ý"
TT_KHACH_TU_CHOI = "Khách từ chối"
TT_MIYANO_TU_CHOI = "Miyano từ chối"
TT_HET_HAN = "Báo giá hết hạn"

HD_GUI_KHACH = "Gửi khách duyệt"
HD_TU_CHOI = "Từ chối"
HD_THU_HOI = "Thu hồi để sửa"
HD_KHACH_DONG_Y = "Khách đồng ý"
HD_KHACH_TU_CHOI = "Khách từ chối"
HD_KHACH_SUA_SL = "Khách sửa số lượng"
HD_HET_HAN = "Báo giá hết hạn"
HD_GHI_NHAN = "Ghi nhận khách đồng ý"

LY_DO_TOI_THIEU = 10


def _trang_thai_truoc(doc) -> str | None:
	truoc = doc.get_doc_before_save()
	return truoc.get("workflow_state") if truoc else None


def chan_dong_y_ngoai_cong(doc, method=None) -> None:
	"""Hook `before_submit` của Quotation.

	Báo giá của cổng chỉ được Submit bởi `dong_y()`, nơi sinh luôn Sales Order.
	Bước "Khách đồng ý" khai `System Manager`, nên một nhân viên có vai đó bấm
	được nó trên Desk; đi đường đó thì báo giá "đã đồng ý" mà không có đơn.
	"""
	if doc.get("custom_nguon_don") != NGUON_CONG:
		return
	if frappe.flags.get("bao_gia_dong_y_qua_cong") == doc.name:
		return
	frappe.throw(
		"Báo giá của cổng khách hàng chỉ được đồng ý bởi chính khách trên cổng.",
		frappe.ValidationError,
	)


def kiem_ly_do_tu_choi(doc, method=None) -> None:
	"""Hook `validate` — Miyano từ chối thì phải có lý do (spec §4.1)."""
	if doc.get("workflow_state") != TT_MIYANO_TU_CHOI:
		return
	if _trang_thai_truoc(doc) == TT_MIYANO_TU_CHOI:
		return
	if len((doc.get("custom_ly_do_tu_choi") or "").strip()) < LY_DO_TOI_THIEU:
		frappe.throw(
			f"Phải nhập lý do từ chối (tối thiểu {LY_DO_TOI_THIEU} ký tự) trước khi "
			"chuyển trạng thái.",
			frappe.ValidationError,
		)
