"""Quy tắc duyệt đơn của QT2 — ngưỡng hai tầng và lý do từ chối.

Tách khỏi `api/portal.py` vì đây là quy tắc áp cho MỌI Sales Order (kể cả đơn
nội bộ Miyano tự lập), không riêng đơn từ cổng — nó thuộc về `doc_events`,
không thuộc về một endpoint nào.
"""

import frappe
from frappe import _

LY_DO_TOI_THIEU = 10


def kiem_ly_do_tu_choi(doc, method=None):
    """BR-O14 / NL-2.1. Không có lý do thì không chuyển sang "Từ chối" được.

    Đặt ở `validate` chứ không ở `before_submit`: state "Từ chối" mang
    `doc_status = 0`, nên `apply_workflow` đi nhánh `doc.save()` — `before_submit`
    không bao giờ chạy cho chuyển tiếp này.
    """
    if (doc.get("workflow_state") or "") != "Từ chối":
        return
    ly_do = (doc.get("custom_ly_do_tu_choi") or "").strip()
    if len(ly_do) < LY_DO_TOI_THIEU:
        frappe.throw(
            _("Phải nhập lý do từ chối (tối thiểu {0} ký tự) trước khi chuyển trạng thái.").format(
                LY_DO_TOI_THIEU
            ),
            frappe.ValidationError,
        )
