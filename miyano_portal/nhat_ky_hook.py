"""Hai móc nối vào chuỗi hook ĐÃ CÓ của `Sales Order` và `Sales Invoice`.

CỐ Ý không dựng hook mới: `hooks.py` đã móc sẵn `Sales Order.on_update` và
`Sales Invoice.on_submit` cho việc khác. Thêm một tên hàm vào danh sách có
sẵn rẻ hơn và ít bất ngờ hơn là thêm một điểm móc thứ hai lên cùng một
doctype.

Chỉ ghi khi `workflow_state` THẬT SỰ đổi. Không có phép so đó thì mỗi lần
nhân sự Miyano sửa một ghi chú vặt trên đơn cũng đẻ một dòng nhật ký, và
một cuốn sổ đầy dòng vô nghĩa là một cuốn sổ không ai đọc — tức là mất
đúng thứ nó sinh ra để cho.
"""

import frappe

from miyano_portal import nhat_ky, portal_context
from miyano_portal.portal_mua_le import han_hieu_luc_bao_gia

# `workflow_state` MỚI → khoá sự kiện. Trạng thái không nằm trong bảng này
# (vd "Chờ xác nhận"/"Chờ Miyano xác nhận" — trạng thái trung gian không
# đáng một dòng riêng, hoặc "Báo giá hết hạn"/"Khách huỷ" — do HỆ THỐNG/
# KHÁCH đứng tên, không phải Miyano) KHÔNG ghi gì cả.
_ANH_XA_TRANG_THAI = {
	"Đã xác nhận": nhat_ky.SK_MIYANO_XAC_NHAN,
	"Chờ khách đồng ý": nhat_ky.SK_MIYANO_BAO_GIA,
	"Từ chối": nhat_ky.SK_MIYANO_TU_CHOI,
}


def tu_sales_order_on_update(doc, method=None):
	"""`Sales Order.on_update` — ghi một dòng khi workflow_state CHUYỂN tới
	một trong ba trạng thái Miyano đứng tên (xác nhận / gửi khách duyệt báo
	giá / từ chối).

	`get_doc_before_save()` trả `None` cho LẦN LƯU ĐẦU TIÊN của một bản ghi
	(insert) — `_doc_before_save` chỉ được nạp khi có một bản ghi CŨ trong
	CSDL để so (`load_from_db()`). Coi `None` là "không có gì để so, bỏ
	qua" thay vì suy nó thành "đổi từ rỗng": lúc insert, workflow_state
	được CHÍNH Frappe gán về trạng thái đầu ("Chờ xác nhận", đã đo trên
	`erptest.local`, không nằm trong `_ANH_XA_TRANG_THAI`) chứ không phải
	một hành động CHUYỂN TIẾP của nhân sự Miyano — ghi nó vào sổ sẽ nói dối
	về việc "vừa có ai đó vừa làm gì" trong khi thực ra chỉ là giá trị khởi
	tạo. Đường thật đi tới `apply_workflow` (xem `test_yeu_cau_list.py::
	_miyano_tu_choi`) luôn `load_from_db()` trước khi đổi trạng thái, nên
	MỌI chuyển tiếp thật đều có `get_doc_before_save()` khác `None`.
	"""
	truoc = doc.get_doc_before_save()
	if truoc is None:
		return
	cu = truoc.get("workflow_state")
	moi = doc.get("workflow_state")
	if cu == moi:
		return
	su_kien = _ANH_XA_TRANG_THAI.get(moi)
	if not su_kien:
		return

	ghi_chu = None
	if su_kien == nhat_ky.SK_MIYANO_BAO_GIA:
		# `han_hieu_luc_bao_gia` đọc `custom_ngay_gui_khach_duyet`, mà hook
		# `portal_mua_le.ghi_ngay_gui_khach_duyet` (validate(), chạy TRƯỚC
		# on_update trong cùng lượt save) đã ghi field đó lên CHÍNH `doc`
		# đang cầm ở đây — không cần đọc lại từ CSDL.
		han = han_hieu_luc_bao_gia(doc)
		ghi_chu = f"Hạn hiệu lực báo giá: {frappe.utils.formatdate(han)}"
	elif su_kien == nhat_ky.SK_MIYANO_TU_CHOI:
		ghi_chu = doc.get("custom_ly_do_tu_choi")

	khoa_phong = None
	if portal_context._cot_khoa_phong_ton_tai():
		khoa_phong = doc.get("custom_khoa_phong")

	nhat_ky.ghi(
		su_kien, customer=doc.customer, khoa_phong=khoa_phong,
		sales_order=doc.name, vai=nhat_ky.VAI_MIYANO, ghi_chu=ghi_chu,
	)


def tu_sales_invoice_on_submit(doc, method=None):
	"""`Sales Invoice.on_submit` — ghi `SK_HOA_DON` khi Miyano ký hoá đơn.

	Bỏ qua hoá đơn TRẢ HÀNG (`is_return`) — cùng lý do
	`hddt_tu_dong.tu_sales_invoice` đã bỏ (xem docstring hàm đó): một giấy
	báo có không phải một lần "phát hành hoá đơn" mới cho khách; ghi nó vào
	sổ sẽ làm một khoản hoàn tiền trông giống một lần xuất hoá đơn.
	"""
	if doc.get("is_return"):
		return

	# SO đầu tiên mà dòng hoá đơn nào đó tham chiếu — `Sales Invoice Item.
	# sales_order` có với hoá đơn lập từ Sales Order lẫn từ Delivery Note
	# (chuỗi tham chiếu được chép lại qua `make_sales_invoice`). Hoá đơn
	# bán lẻ không qua Sales Order nào thì để trống, cùng cách các sự kiện
	# khác của sổ này chấp nhận `sales_order=None`.
	sales_order = None
	for row in doc.items:
		so = row.get("sales_order")
		if so:
			sales_order = so
			break

	khoa_phong = None
	if sales_order and portal_context._cot_khoa_phong_ton_tai():
		khoa_phong = frappe.db.get_value("Sales Order", sales_order, "custom_khoa_phong")

	nhat_ky.ghi(
		nhat_ky.SK_HOA_DON, customer=doc.customer, khoa_phong=khoa_phong,
		sales_order=sales_order, vai=nhat_ky.VAI_MIYANO,
	)
