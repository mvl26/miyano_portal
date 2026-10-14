"""Chốt giá trên Sales Order từ cổng (spec 2026-10-09 §5.1, §5.4).

Đơn không còn vòng báo giá với khách (patch v1_44): báo giá đi trên Quotation,
đơn chỉ cần Miyano xác nhận. Hai chốt còn lại:

  * đơn không vào "Chờ Miyano xác nhận" khi còn dòng chưa có đơn giá (đơn
    "Mua lẻ" cũ: Miyano điền giá trên đơn nháp rồi gửi duyệt);
  * đơn mang giá khách đã đồng ý (đơn "Theo báo giá", đơn "Mua lẻ" cũ khách
    đã đồng ý) không được xác nhận với một đơn giá khác.

Chỉ áp cho đơn từ cổng (`custom_nguon_don == "Client Portal"`); đơn Desk tự
lập không bị ràng. Đơn cổng cũ có dòng `custom_nguon_gia` trống: chốt giá đã
đồng ý chỉ nhìn dòng đã đóng dấu "Báo giá" nên không chặn nhầm chúng.
"""

import frappe
from frappe.utils import flt

from miyano_portal.bang_gia_khach import NGUON_BAO_GIA
from miyano_portal.portal_mua_le import ITEM_GIU_CHO, di_vong_bao_gia

TT_CHO_XAC_NHAN = "Chờ xác nhận"
TT_CHO_MIYANO = "Chờ Miyano xác nhận"


def _trang_thai_truoc(doc) -> str | None:
	truoc = doc.get_doc_before_save()
	return truoc.get("workflow_state") if truoc else None


def co_gia_khach_dong_y(doc) -> bool:
	"""Đơn mang giá khách ĐÃ ĐỒNG Ý trên từng dòng: đơn "Mua lẻ" của luồng cũ
	(khách đồng ý trên chính đơn) và đơn "Theo báo giá" (khách đồng ý trên
	Quotation, spec 2026-10-12 §4.5)."""
	from miyano_portal.bao_gia import LOAI_DON_THEO_BAO_GIA

	return di_vong_bao_gia(doc) or doc.get("custom_loai_don") == LOAI_DON_THEO_BAO_GIA


def kiem_chuyen_trang_thai(doc, method=None) -> None:
	"""§5.1 — đơn cổng vào "Chờ Miyano xác nhận" phải có đơn giá cho mọi dòng
	(<= 0 là chưa có giá, không phải giá 0). Chỉ so khi trạng thái THAY ĐỔI."""
	if doc.is_new() or doc.get("custom_nguon_don") != "Client Portal":
		return
	if doc.get("workflow_state") != TT_CHO_MIYANO or _trang_thai_truoc(doc) == TT_CHO_MIYANO:
		return
	thieu = [
		d.item_code for d in doc.items
		if d.item_code != ITEM_GIU_CHO and flt(d.rate) <= 0
	]
	if thieu:
		frappe.throw(
			"Chưa gửi duyệt được — còn mặt hàng chưa có đơn giá: "
			+ ", ".join(thieu) + ".",
			frappe.ValidationError,
		)


def kiem_gia_khop_gia_da_dong_y(doc, method=None) -> None:
	"""§5.4 — chốt 3: không xác nhận đơn khi giá lệch giá khách đã đồng ý."""
	if doc.get("custom_nguon_don") != "Client Portal" or not co_gia_khach_dong_y(doc):
		return
	lech = [
		d.item_code for d in doc.items
		if d.get("custom_nguon_gia") == NGUON_BAO_GIA
		and flt(d.get("custom_gia_khach_dong_y")) > 0
		and flt(d.rate) != flt(d.custom_gia_khach_dong_y)
	]
	if lech:
		frappe.throw(
			"Đơn giá của " + ", ".join(lech) + " khác giá khách đã đồng ý — "
			"sửa lại đúng giá đã đồng ý, hoặc từ chối đơn và gửi khách báo giá mới.",
			frappe.ValidationError,
		)
