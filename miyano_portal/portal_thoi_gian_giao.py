"""Thời gian giao hàng của một phiếu giao — MỘT nguồn cho cổng, màn kiểm hàng
và email.

`Delivery Note.posting_date` là ngày GHI SỔ. Phiếu lập chiều nay, xe tới bệnh
viện sáng mai là ca thường, nên Miyano nhập thời điểm giao thật vào
`custom_thoi_gian_giao` (chủ đầu tư 09/10/2026).

Mọi nơi hiện "giao lúc nào" đều hỏi `thoi_gian_giao_cua_dn()` — không nơi nào
tự đọc `posting_date`, để hai màn nói về cùng một đợt giao không ra hai ngày.
"""

import frappe

FIELD = "custom_thoi_gian_giao"

# Bộ cột tối thiểu để tính — dùng chung cho mọi truy vấn `Delivery Note` cần
# thời gian giao, thay vì mỗi nơi tự nhớ ba tên cột.
COT_CAN = (FIELD, "posting_date", "posting_time")


def thoi_gian_giao_cua_dn(dn):
	"""Thời điểm giao của phiếu, hoặc `None` khi phiếu không có cả ngày ghi sổ.

	Lùi về ngày giờ ghi sổ khi `custom_thoi_gian_giao` rỗng: phiếu lập TRƯỚC
	bản này không có giá trị, và một đợt giao không ngày trên cổng tệ hơn một
	đợt giao mang ngày ghi sổ.
	"""
	gia_tri = dn.get(FIELD)
	if gia_tri:
		return frappe.utils.get_datetime(gia_tri)
	if not dn.get("posting_date"):
		return None
	return frappe.utils.get_datetime(
		f"{dn.get('posting_date')} {dn.get('posting_time') or '00:00:00'}"
	)


def dien_thoi_gian_giao(doc, method=None) -> None:
	"""`validate` của Delivery Note — điền thời gian giao khi còn trống.

	Làm ở server chứ không bằng `default` của field: phiếu dựng qua
	`make_delivery_note` (nút "Tạo phiếu giao" trên đơn, mọi luồng tự động)
	không đi qua form nên không nhận giá trị mặc định nào của form.

	Không bao giờ ném lỗi — cùng ràng buộc với mọi hook khác trên Delivery
	Note của app này: một trục trặc ở đây không được chặn Miyano giao hàng.
	"""
	try:
		if doc.get(FIELD):
			return
		doc.set(FIELD, thoi_gian_giao_cua_dn(doc) or frappe.utils.now_datetime())
	except Exception:
		frappe.log_error(
			title="Phiếu giao: không điền được thời gian giao hàng",
			message=frappe.get_traceback(with_context=True),
		)
