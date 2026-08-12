"""Thông báo từ cổng sang nhân viên Miyano.

Chống spam bằng `Notification Log` có sẵn của Frappe thay vì dựng bảng riêng:
bản thân lịch sử thông báo đã là nơi trả lời câu "hôm nay đã báo chưa", thêm
một bảng nữa chỉ tạo thêm một thứ phải giữ đồng bộ.
"""

import frappe
from frappe.utils import today

TIEN_TO = "Portal - Thiếu giá"


def _sales_phu_trach(customer: str) -> str | None:
    """Nhân viên kinh doanh của khách. Rỗng thì không gửi cho ai cả."""
    return frappe.db.get_value("Customer", customer, "account_manager")


def bao_thieu_gia(customer: str, item_code: str) -> bool:
    """NL-1.4 / US-E1.4. Trả `True` nếu vừa gửi, `False` nếu không gửi.

    Chống spam theo CẶP (khách, mặt hàng) mỗi ngày một lần — không phải theo
    khách: chặn cả mặt hàng thứ hai là giấu mất một nhu cầu thật của họ.

    Không bao giờ ném lỗi. Hàm này chạy trên đường mà khách đang bị chặn đặt
    hàng; một trục trặc ở khâu thông báo nội bộ không được phép thay thế
    thông điệp mà khách cần đọc.
    """
    nguoi_nhan = _sales_phu_trach(customer)
    if not nguoi_nhan:
        return False

    chu_de = f"{TIEN_TO}: {item_code} ({customer})"
    da_gui = frappe.db.exists(
        "Notification Log",
        {
            "subject": chu_de,
            "for_user": nguoi_nhan,
            "creation": [">=", f"{today()} 00:00:00"],
        },
    )
    if da_gui:
        return False

    frappe.get_doc({
        "doctype": "Notification Log",
        "subject": chu_de,
        "for_user": nguoi_nhan,
        "type": "Alert",
        "email_content": (
            f"Khách hàng <b>{customer}</b> không đặt được mặt hàng "
            f"<b>{item_code}</b> vì mặt hàng này chưa có giá trong bảng giá "
            f"của họ. Bổ sung Item Price để khách đặt được."
        ),
    }).insert(ignore_permissions=True)
    return True
