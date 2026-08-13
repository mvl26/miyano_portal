"""BR-O14 — ô lý do từ chối trên Sales Order.

`create_custom_fields` tự nó đã idempotent: gọi lại chỉ cập nhật thuộc tính,
không sinh bản ghi thứ hai.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields(
        {
            "Sales Order": [
                {
                    "fieldname": "custom_ly_do_tu_choi",
                    "label": "Lý do từ chối",
                    "fieldtype": "Small Text",
                    "insert_after": "custom_hdnt",
                    "no_copy": 1,
                    # CỐ Ý không đặt `depends_on` theo workflow_state: ô phải
                    # nhập được TRƯỚC khi bấm Từ chối. Giấu ô cho tới lúc đã ở
                    # trạng thái "Từ chối" thì người duyệt không bao giờ điền
                    # được, và quy tắc bắt buộc lý do thành cái bẫy không lối ra.
                    "translatable": 0,
                }
            ]
        },
        ignore_validate=True,
    )
