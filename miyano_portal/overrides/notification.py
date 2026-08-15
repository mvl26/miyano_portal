"""Vá lỗi lõi Frappe: `Notification.send_notification_by_channel` bọc TOÀN
BỘ các nhánh kênh (Email/Slack/SMS/System Notification) trong CÙNG MỘT
`try/except`, và nhánh `send_system_notification` bổ sung (tạo System
Notification dù kênh chính không phải "System Notification") nằm SAU nhánh
kênh chính trong cùng khối try đó (`frappe/email/doctype/notification/
notification.py:220-237`).

Hệ quả: site không cấu hình Email Account gửi ra (đúng tình huống bệnh viện
cài on-prem, và đúng site test này) — `send_an_email()` ném lỗi ngay khi
resolve tài khoản gửi, exception nhảy thẳng xuống `except Exception:
self.log_error(...)`, và dòng tạo System Notification KHÔNG BAO GIỜ chạy tới.
`Notification Log` — nguồn duy nhất của trang Thông báo cổng — chết câm vĩnh
viễn, không một lỗi nào báo ra (log_error nuốt gọn, doc vẫn save/submit bình
thường).

Năm Notification "Portal - *" (patch `patches/v1_19/bat_thong_bao_he_thong_
huong_khach.py`) đã bật `send_system_notification = 1` với `channel =
"Email"` — đúng cấu hình rơi vào lỗ này.

Sửa tại NGUỒN thay vì đổi `channel` từng bản ghi hay dựng đường gửi email
riêng: override đúng MỘT phương thức, bọc RIÊNG từng nhánh trong try/except
của chính nó. Không đổi field nào trên các bản ghi Notification hiện có —
`channel = "Email"` + `send_system_notification = 1` vẫn hoạt động ĐÚNG NHƯ
Ý ĐỊNH ban đầu của patch v1_19, chỉ khác ở chỗ giờ nó THỰC SỰ tạo được
`Notification Log` khi email hỏng. Không cần patch cập nhật bản ghi đã cài
(brief 2026-08-15 phần "BLOCKING FIX" có nhắc yêu cầu này cho hướng sửa gốc —
không áp dụng ở đây vì cấu hình bản ghi không đổi, chỉ đổi hành vi dispatch).

Đăng ký qua `override_doctype_class` trong `hooks.py` — áp dụng cho MỌI
`Notification` trên site (không riêng 5 bản ghi "Portal - *"), đúng phạm vi
của một bugfix lõi: bất kỳ Notification nào khác trong tương lai bật cả
`channel = "Email"` và `send_system_notification = 1` cũng không rơi vào bẫy
này nữa.
"""

from frappe.email.doctype.notification.notification import Notification as _CoreNotification


class Notification(_CoreNotification):
	def send_notification_by_channel(self, doc, context):
		"""Bọc RIÊNG từng nhánh — một kênh hỏng không được phép chặn kênh
		khác chạy. KHÔNG gọi `super()`: đang thay thế nguyên thân hàm gốc
		(bug nằm trong chính thân hàm đó), gọi `super()` sẽ chạy lại đúng
		đoạn code lỗi rồi mới tới phần vá, vô nghĩa.
		"""
		if self.channel == "Email":
			try:
				self.send_an_email(doc, context)
			except Exception:
				self.log_error("Failed to send Notification (Email)")
		elif self.channel == "Slack":
			try:
				self.send_a_slack_msg(doc, context)
			except Exception:
				self.log_error("Failed to send Notification (Slack)")
		elif self.channel == "SMS":
			try:
				self.send_sms(doc, context)
			except Exception:
				self.log_error("Failed to send Notification (SMS)")
		elif self.channel == "System Notification":
			try:
				self.create_system_notification(doc, context)
			except Exception:
				self.log_error("Failed to send Notification (System Notification)")

		# Bổ sung — cùng ý định gốc của core: nếu bật cờ này VÀ kênh chính
		# không phải "System Notification" (tránh tạo hai lần), luôn thử tạo
		# System Notification, ĐỘC LẬP với kết quả nhánh kênh chính ở trên.
		if self.send_system_notification and self.channel != "System Notification":
			try:
				self.create_system_notification(doc, context)
			except Exception:
				self.log_error("Failed to send Notification (System Notification)")
