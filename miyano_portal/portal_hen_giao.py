"""Miyano hẹn lại lịch giao cho khách.

Nhu cầu chủ đầu tư 2026-08-16 (vai nhân viên): "khi chưa có hàng tôi muốn
thông báo lại cho khách hàng về hàng thiếu và sẽ vận chuyển sau hoặc đổi ngày
giao hàng".

HAI bối cảnh, MỘT cơ chế:

1. **Trước khi giao** — Miyano biết chưa gom đủ hàng. Nhân viên mở đơn trên
   Desk và hẹn lại.
2. **Sau khi giao thiếu** — khách lập biên bản kiểm hàng báo thiếu. Nhân viên
   trả lời ngay trên biên bản (`portal_kiem_hang.kiem_hang_hen_giao`), và lời
   hẹn đó ghi vào CHÍNH đơn hàng qua hàm ở đây.

Gộp một cơ chế vì với khách chỉ có một câu hỏi: "bao giờ tôi nhận được hàng?".
Hai đường ghi vào hai chỗ khác nhau sẽ cho ra hai câu trả lời trên cùng một
đơn, và không có gì buộc chúng khớp nhau.
"""

import frappe

LOAI_GIAO_BU = "Sẽ giao bù"
LOAI_DOI_NGAY = "Đã đổi ngày giao"
LOAI_HOP_LE = (LOAI_GIAO_BU, LOAI_DOI_NGAY)

# Cùng ngưỡng với `LY_DO_TOI_THIEU` của kiểm hàng — khách đọc đúng dòng này.
LY_DO_TOI_THIEU = 5

ROLE_HEN_GIAO = ("System Manager", "Sales Manager", "Sales User")


def _kiem_role() -> None:
	if not set(ROLE_HEN_GIAO) & set(frappe.get_roles()):
		raise frappe.PermissionError("Bạn không có quyền hẹn lại lịch giao.")


@frappe.whitelist()
def hen_giao_lai(order: str, ngay_moi, loai: str, ly_do: str) -> dict:
	"""Ghi lời hẹn lên đơn hàng và báo khách.

	`LOAI_DOI_NGAY` ĐỔI THẬT `delivery_date` của đơn và của mọi dòng — cả hai
	field đều `allow_on_submit=1` nên sửa được trên đơn đã xác nhận (đã đo
	thực nghiệm trên đơn đã giao 100%). Đổi CẢ dòng chứ không chỉ header: mọi
	báo cáo giao hàng trễ của ERPNext đọc `Sales Order Item.delivery_date`, để
	lệch là để lại một đơn "trễ hạn" vĩnh viễn trên báo cáo dù đã thoả thuận
	lại với khách.

	`LOAI_GIAO_BU` KHÔNG đụng `delivery_date`: ngày cam kết gốc vẫn là ngày
	Miyano đã lỡ, và giữ nó là giữ đúng lịch sử. Lời hẹn giao phần còn lại
	nằm ở `custom_ngay_hen_giao`.
	"""
	_kiem_role()

	loai = (loai or "").strip()
	if loai not in LOAI_HOP_LE:
		frappe.throw(
			f"Loại hẹn giao không hợp lệ. Chọn «{LOAI_GIAO_BU}» hoặc «{LOAI_DOI_NGAY}».",
			frappe.ValidationError,
		)

	ly_do = (ly_do or "").strip()
	if len(ly_do) < LY_DO_TOI_THIEU:
		frappe.throw(
			f"Nêu lý do (tối thiểu {LY_DO_TOI_THIEU} ký tự) — khách sẽ đọc đúng dòng này.",
			frappe.ValidationError,
		)

	ngay_moi = frappe.utils.getdate(ngay_moi)
	if ngay_moi < frappe.utils.getdate(frappe.utils.nowdate()):
		frappe.throw(
			"Ngày hẹn giao không được ở quá khứ.", frappe.ValidationError
		)

	so = frappe.get_doc("Sales Order", order)
	if so.docstatus != 1:
		frappe.throw(
			"Chỉ hẹn lại lịch giao cho đơn đã xác nhận.", frappe.ValidationError
		)

	so.custom_loai_hen_giao = loai
	so.custom_ngay_hen_giao = ngay_moi
	so.custom_ly_do_hen_giao = ly_do
	if loai == LOAI_DOI_NGAY:
		so.delivery_date = ngay_moi
		for row in so.items:
			row.delivery_date = ngay_moi
	so.flags.ignore_permissions = True
	so.save()
	so.add_comment(
		"Comment",
		f"[Portal] {loai} — hẹn ngày {frappe.utils.formatdate(ngay_moi)}. Lý do: {ly_do}",
	)

	_bao_khach(so, loai, ngay_moi, ly_do)
	return {
		"order": so.name,
		"loai": loai,
		"ngay_hen_giao": str(ngay_moi),
		"delivery_date": str(so.delivery_date),
	}


def _bao_khach(so, loai: str, ngay_moi, ly_do: str) -> None:
	"""Không bao giờ ném lỗi: lời hẹn ĐÃ ghi lên đơn thật, một trục trặc ở
	khâu thông báo không được phép biến thao tác đó thành lỗi — cùng nguyên
	tắc toàn cụm thông báo của app."""
	try:
		from miyano_portal.portal_thong_bao_khach import bao_hen_giao_lai

		bao_hen_giao_lai(so, loai, ngay_moi, ly_do)
	except Exception:
		frappe.log_error(
			title="Hẹn giao: lỗi khi báo khách",
			message=frappe.get_traceback(with_context=True),
			reference_doctype="Sales Order",
			reference_name=so.name,
		)


def hen_giao_cua_don(so) -> dict | None:
	"""Khối "Miyano đã hẹn lại" cho cổng khách hàng, hoặc None."""
	ngay = so.get("custom_ngay_hen_giao")
	if not ngay:
		return None
	return {
		"loai": so.get("custom_loai_hen_giao") or "",
		"ngay": str(ngay),
		"ly_do": so.get("custom_ly_do_hen_giao") or "",
	}
