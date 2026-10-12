"""Thời gian giao hàng của một phiếu giao — MỘT nguồn cho cổng, màn kiểm hàng
và email.

`Delivery Note.posting_date` là ngày GHI SỔ. Phiếu lập chiều nay, xe tới bệnh
viện sáng mai là ca thường, nên Miyano nhập thời điểm giao thật vào
`custom_thoi_gian_giao` (chủ đầu tư 09/10/2026).

Mọi nơi hiện "giao lúc nào" đều hỏi `thoi_gian_giao_cua_dn()` — không nơi nào
tự đọc `posting_date`, để hai màn nói về cùng một đợt giao không ra hai ngày.

Nhân viên để trống thì giá trị mặc định được điền LÚC GHI SỔ (`before_submit`),
bằng ngày giờ ghi sổ của lúc đó — xem `dien_thoi_gian_giao`. Phiếu nháp và
phiếu cũ để trống thì lúc đọc lùi về ngày giờ ghi sổ đang có trên phiếu.
"""

import frappe

FIELD = "custom_thoi_gian_giao"

# Mô tả của field trên Desk — một chỗ cho patch tạo field (v1_40) và patch cập
# nhật site đang chạy (v1_41 `don_thoi_gian_giao_tu_dien_tren_phieu_nhap`).
MO_TA_TRUONG = (
	"Thời điểm hàng tới khách. Hiện trên cổng khách hàng và trong email báo "
	"xuất giao. Để trống thì khi ghi sổ (Submit) hệ thống tự điền ngày giờ ghi "
	"sổ của phiếu."
)

# Bộ cột tối thiểu để tính — dùng chung cho mọi truy vấn `Delivery Note` cần
# thời gian giao, thay vì mỗi nơi tự nhớ ba tên cột.
COT_CAN = (FIELD, "posting_date", "posting_time")


def thoi_gian_giao_cua_dn(dn):
	"""Thời điểm giao của phiếu, hoặc `None` khi phiếu không có cả ngày ghi sổ.

	Lùi về ngày giờ ghi sổ khi `custom_thoi_gian_giao` rỗng: phiếu NHÁP (giá
	trị mặc định chỉ được điền lúc ghi sổ) và phiếu lập TRƯỚC bản này không có
	giá trị, và một đợt giao không ngày trên cổng tệ hơn một đợt giao mang
	ngày ghi sổ.
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
	"""`before_submit` của Delivery Note — điền thời gian giao khi còn trống.

	Lúc GHI SỔ chứ không lúc lưu nháp: ERPNext đặt lại `posting_date` /
	`posting_time` về "bây giờ" ở MỖI lần validate, kể cả lần ghi sổ (trừ khi
	tick "Edit Posting Date and Time"). Điền ở lần lưu nháp đầu là đóng băng
	giờ SOẠN phiếu: phiếu soạn 15:00 thứ Hai, ghi sổ 09:00 thứ Ba sẽ báo khách
	— trên cổng và trong thư "Portal - Xuất giao" — rằng hàng giao chiều thứ
	Hai. `before_submit` chạy sau `validate` của lần ghi sổ, nên con số lấy ở
	đây là ngày giờ ghi sổ CUỐI CÙNG; và nó chạy trước khi dòng được ghi xuống
	và trước Notification event "Submit" (Frappe gửi ở `on_submit`), nên thư
	thấy đúng giá trị vừa điền.

	Chỉ điền khi còn TRỐNG — giá trị nhân viên tự gõ được giữ nguyên.

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
