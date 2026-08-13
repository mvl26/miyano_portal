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


def nguong_duyet() -> float:
    """Ngưỡng duyệt hai tầng. `0` = một tầng (không chặn ai).

    BẮT BUỘC dùng `get_single_value` (trả float) chứ không `get_value`: field
    Currency để trống được lưu thành chuỗi `'0'`, mà `not '0'` là False — đọc
    kiểu đó thì ngưỡng-để-trống biến thành "mọi đơn đều cần Manager", khoá
    sạch quyền duyệt của Sales User. Đã kiểm thực nghiệm, xem BẪY 1 của kế hoạch.
    """
    return float(
        frappe.db.get_single_value("Miyano Portal Settings", "nguong_duyet_2_tang") or 0
    )


def _tien_vn(so: float) -> str:
    """50000000.0 -> "50.000.000". Không thập phân, dấu chấm ngăn nghìn."""
    return f"{int(so):,}".replace(",", ".")


def kiem_nguong_duyet(doc, method=None):
    """BR-O9 / NL-2.5. Đơn từ ngưỡng trở lên chỉ Sales Manager xác nhận được.

    Đặt ở `before_submit` chứ KHÔNG ở `condition` của workflow transition:
    `apply_workflow` ném `WorkflowTransitionError` ngay khi không transition nào
    khớp, TRƯỚC mọi save/submit (`frappe/model/workflow.py:113-115`), nên hook
    sẽ không bao giờ chạy và khách chỉ nhận được câu "Not a valid Workflow
    Action" thay vì câu NL-2.5. Exception ở đây làm rollback, nên đơn nằm
    nguyên ở "Chờ Miyano xác nhận" — đúng như NL-2.5 mô tả.
    """
    nguong = nguong_duyet()
    if nguong <= 0:
        return
    if float(doc.get("grand_total") or 0) < nguong:
        return
    if "Sales Manager" in frappe.get_roles():
        return
    frappe.throw(
        _("Đơn ≥ {0} ₫ — cần Sales Manager xác nhận.").format(_tien_vn(nguong)),
        frappe.ValidationError,
    )
