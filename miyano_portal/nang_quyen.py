"""Chạy một khối dưới quyền hệ thống mà không làm hỏng phiên của khách.

Các bước chuyển trạng thái phía khách (đồng ý, từ chối, sửa số lượng) khai
`allowed = System Manager` trong workflow: khách không bao giờ có vai nào
trên Desk. Endpoint cổng tự kiểm quyền của khách trên đúng chứng từ rồi mới
vào khối này.

CỐ Ý KHÔNG dùng frappe.set_user() ở đây (code review sau lần merge đầu
phát hiện): frappe.local.session LÀ CÙNG MỘT OBJECT với
Session.data trong frappe/sessions.py — set_user() ghi đè
local.session.sid bằng chính chuỗi username (không phải sid thật) và
xoá sạch local.session.data (mất csrf_token...). Session.update()
(app.py, cuối MỌI request thật) vẫn dùng self.sid GỐC (biến riêng của
Session, không đổi) làm khoá `frappe.cache.hset("session", self.sid,
self.data)` — nên nó ghi ĐÈ cache session THẬT của chính khách đang gọi
bằng self.data đã hỏng. Gọi set_user() lần hai để "trả lại" chỉ khiến
nó tệ hơn: sid bị đặt lại thành username (không phải sid gốc), data
thành dict rỗng — không phải dữ liệu session gốc. Kết quả: khách mở
báo giá lâu (vượt threshold update session giữa chừng) rồi bấm Đồng ý
thì mọi POST sau đó trên tab đang mở lỗi CSRF tới khi tải lại trang.

apply_workflow() chỉ tra vai trò qua frappe.get_roles() ->
frappe.session.user (frappe/model/workflow.py, frappe/permissions.py
get_roles() cache theo user nên an toàn khi đổi qua đổi lại) — không
đọc sid hay session.data ở đâu cả. Nên chỉ cần đổi ĐÚNG MỘT thuộc tính
`session.user`, không đụng `sid`/`data`, là đủ để apply_workflow chạy
dưới quyền hệ thống mà không có gì trên session thật của khách để
khôi phục sai.
"""

from contextlib import contextmanager

import frappe


@contextmanager
def quyen_he_thong():
	session = frappe.local.session
	nguoi_goi = session.user
	frappe.local.user_perms = None  # tránh dùng nhầm cache quyền của người cũ
	session.user = "Administrator"
	try:
		yield nguoi_goi
	finally:
		# Trả phiên về NGAY, kể cả khi khối ném lỗi: thiếu `finally` thì phần
		# còn lại của request chạy dưới quyền Administrator.
		session.user = nguoi_goi
		frappe.local.user_perms = None
