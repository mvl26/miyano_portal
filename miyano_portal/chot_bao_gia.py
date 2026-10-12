"""Chốt của luồng báo giá (spec 2026-10-09 §5.1, §5.4).

Giá báo chỉ vào Price List khi KHÁCH đồng ý (quyết định Q4). Ba chốt dưới đây
giữ cho điều đó không có đường vòng: đơn báo giá không đi tắt qua khách,
không gửi khách khi còn thiếu giá, và giá không đổi sau khi khách đã đồng ý.

Chỉ áp cho đơn từ cổng (`custom_nguon_don == "Client Portal"`); đơn Desk tự
lập không bị ràng. Đơn cổng cũ (trước thay đổi này) có dòng `custom_nguon_gia`
trống: chốt 3 chỉ nhìn dòng đã đóng dấu "Báo giá" nên không chặn nhầm chúng.
"""

import frappe
from frappe.utils import flt

from miyano_portal.bang_gia_khach import NGUON_BAO_GIA
from miyano_portal.portal_mua_le import ITEM_GIU_CHO, TRANG_THAI_CHO_KHACH, di_vong_bao_gia

TT_CHO_XAC_NHAN = "Chờ xác nhận"
TT_CHO_MIYANO = "Chờ Miyano xác nhận"


def _trang_thai_truoc(doc) -> str | None:
	truoc = doc.get_doc_before_save()
	return truoc.get("workflow_state") if truoc else None


def kiem_chuyen_trang_thai(doc, method=None) -> None:
	"""§5.1 — hai chốt trên bước chuyển trạng thái, và dọn giá đã đồng ý.

	Chỉ so khi trạng thái THAY ĐỔI, nên các đường chạy bằng mã (khách đồng ý /
	không đồng ý, sửa số lượng, hết hạn báo giá, huỷ) không bị chặn oan.
	"""
	if doc.is_new() or doc.get("custom_nguon_don") != "Client Portal":
		return
	truoc, nay = _trang_thai_truoc(doc), doc.get("workflow_state")
	if truoc == nay:
		return

	# Chốt 1: "Gửi duyệt" thẳng từ "Chờ xác nhận" bỏ qua khách. Đơn có
	# hàng chờ báo giá phải qua "Gửi khách duyệt"; đơn "Khách đồng ý" vào
	# "Chờ Miyano xác nhận" từ "Chờ khách đồng ý" nên không dính.
	if nay == TT_CHO_MIYANO and truoc == TT_CHO_XAC_NHAN and di_vong_bao_gia(doc):
		frappe.throw(
			"Đơn có hàng chờ báo giá — dùng «Gửi khách duyệt» để khách đồng ý "
			"giá trước khi Miyano xác nhận.",
			frappe.ValidationError,
		)

	# Chốt 2: không gửi khách báo giá khi còn dòng chưa có giá (<= 0 là chưa
	# có giá, không phải giá 0).
	if nay == TRANG_THAI_CHO_KHACH:
		thieu = [
			d.item_code for d in doc.items
			if d.item_code != ITEM_GIU_CHO and flt(d.rate) <= 0
		]
		if thieu:
			frappe.throw(
				"Chưa gửi khách được — còn mặt hàng chưa có đơn giá: "
				+ ", ".join(thieu) + ".",
				frappe.ValidationError,
			)

	# Quay về "Chờ xác nhận" (khách không đồng ý, hoặc khách sửa số lượng) thì
	# giá đã đồng ý không còn giá trị; vòng đồng ý sau sẽ đóng dấu lại.
	if nay == TT_CHO_XAC_NHAN:
		for d in doc.items:
			d.custom_gia_khach_dong_y = 0


def kiem_gia_khop_gia_da_dong_y(doc, method=None) -> None:
	"""§5.4 — chốt 3: không xác nhận đơn khi giá lệch giá khách đã đồng ý."""
	if doc.get("custom_nguon_don") != "Client Portal" or not di_vong_bao_gia(doc):
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
			"gửi khách duyệt lại trước khi xác nhận.",
			frappe.ValidationError,
		)
