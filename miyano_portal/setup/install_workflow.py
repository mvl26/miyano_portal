import frappe

WORKFLOW = "Sales Order - Client Portal"

# "Chờ khách đồng ý" có mặt NGAY trong định nghĩa gốc (trước đây chỉ do
# `patches/v1_4/mo_rong_workflow_e2.py` thêm) vì cạnh "Chờ Miyano xác nhận" →
# «Gửi khách duyệt» nối vào nó, và Workflow từ chối một cạnh trỏ tới trạng
# thái không khai trong `states`. Các patch mở rộng (v1_4, v1_8, v1_18, v1_41)
# idempotent theo nội dung nên gặp trạng thái / cạnh đã có thì bỏ qua: site
# mới và site nâng cấp kết thúc với CÙNG một workflow.
STATE_KHACH = "Chờ khách đồng ý"


def _ensure_states():
    for s, style in [
        ("Chờ xác nhận", ""), ("Chờ Miyano xác nhận", ""), ("Đã xác nhận", ""),
        ("Từ chối", ""), (STATE_KHACH, "Warning"),
    ]:
        if not frappe.db.exists("Workflow State", s):
            frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": s, "style": style}).insert(ignore_permissions=True)
    for a in ["Gửi duyệt", "Xác nhận", "Từ chối", "Gửi khách duyệt"]:
        if not frappe.db.exists("Workflow Action Master", a):
            frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": a}).insert(ignore_permissions=True)


def install_portal_workflow():
    _ensure_states()
    if frappe.db.exists("Workflow", WORKFLOW):
        return frappe.get_doc("Workflow", WORKFLOW)
    wf = frappe.get_doc({
        "doctype": "Workflow",
        "workflow_name": WORKFLOW,
        "document_type": "Sales Order",
        "is_active": 1,
        "workflow_state_field": "workflow_state",
        "states": [
            {"state": "Chờ xác nhận", "doc_status": "0", "allow_edit": "Sales User"},
            {"state": "Chờ Miyano xác nhận", "doc_status": "0", "allow_edit": "Sales User"},
            {"state": "Đã xác nhận", "doc_status": "1", "allow_edit": "Sales Manager"},
            {"state": "Từ chối", "doc_status": "0", "allow_edit": "Sales Manager"},
            {"state": STATE_KHACH, "doc_status": "0", "allow_edit": "Sales User"},
        ],
        "transitions": [
            {"state": "Chờ xác nhận", "action": "Gửi duyệt", "next_state": "Chờ Miyano xác nhận", "allowed": "Sales User"},
            {"state": "Chờ Miyano xác nhận", "action": "Xác nhận", "next_state": "Đã xác nhận", "allowed": "Sales User"},
            {"state": "Chờ Miyano xác nhận", "action": "Từ chối", "next_state": "Từ chối", "allowed": "Sales User"},
            # Spec 2026-10-09 §5.4 — lối ra của chốt 3: giá bị sửa sau khi khách
            # đồng ý thì gửi khách duyệt lại (cùng cạnh với patch v1_41
            # `mo_rong_workflow`, dành cho site đang chạy).
            {"state": "Chờ Miyano xác nhận", "action": "Gửi khách duyệt", "next_state": STATE_KHACH, "allowed": "Sales User"},
        ],
    })
    wf.insert(ignore_permissions=True)
    return wf


def _bao_gia_states():
    from miyano_portal import bao_gia as bg

    # (trạng thái, docstatus, vai được sửa tại chỗ, kiểu hiển thị)
    return [
        (bg.TT_CHO_MIYANO, "0", "Sales User", ""),
        # Đang ở phía khách: muốn sửa giá phải "Thu hồi để sửa", không sửa tại chỗ.
        (bg.TT_CHO_KHACH, "0", "System Manager", "Warning"),
        (bg.TT_DA_DONG_Y, "1", "Sales Manager", "Success"),
        (bg.TT_KHACH_TU_CHOI, "0", "Sales Manager", "Danger"),
        (bg.TT_MIYANO_TU_CHOI, "0", "Sales Manager", "Danger"),
        (bg.TT_HET_HAN, "0", "System Manager", "Danger"),
    ]


def _bao_gia_transitions():
    from miyano_portal import bao_gia as bg

    # (từ, hành động, tới, vai, điều kiện)
    return [
        (bg.TT_CHO_MIYANO, bg.HD_GUI_KHACH, bg.TT_CHO_KHACH, "Sales User", None),
        (bg.TT_CHO_MIYANO, bg.HD_TU_CHOI, bg.TT_MIYANO_TU_CHOI, "Sales User", None),
        (bg.TT_CHO_KHACH, bg.HD_THU_HOI, bg.TT_CHO_MIYANO, "Sales User", None),
        (bg.TT_CHO_KHACH, bg.HD_KHACH_DONG_Y, bg.TT_DA_DONG_Y, "System Manager", None),
        (bg.TT_CHO_KHACH, bg.HD_KHACH_TU_CHOI, bg.TT_KHACH_TU_CHOI, "System Manager", None),
        (bg.TT_CHO_KHACH, bg.HD_KHACH_SUA_SL, bg.TT_CHO_MIYANO, "System Manager", None),
        (bg.TT_CHO_KHACH, bg.HD_HET_HAN, bg.TT_HET_HAN, "System Manager", None),
        # Báo giá nhân viên tự lập cho khách ngoài cổng: khách không có tài
        # khoản nên nhân viên ghi nhận. Điều kiện chặn bấm thay khách của cổng.
        (bg.TT_CHO_KHACH, bg.HD_GHI_NHAN, bg.TT_DA_DONG_Y, "Sales User",
         f'doc.custom_nguon_don != "{bg.NGUON_CONG}"'),
    ]


def install_quotation_workflow():
    """Spec 2026-10-12 §4.1. Frappe cho mỗi doctype MỘT workflow hoạt động và
    nó phủ mọi chứng từ, nên workflow này phủ cả Quotation nhân viên tự lập.
    Chạy lại được: đã có thì không đụng."""
    from miyano_portal import bao_gia as bg

    for ten, _ds, _vai, kieu in _bao_gia_states():
        if not frappe.db.exists("Workflow State", ten):
            frappe.get_doc({
                "doctype": "Workflow State", "workflow_state_name": ten, "style": kieu,
            }).insert(ignore_permissions=True)
    for _tu, hanh_dong, _toi, _vai, _dk in _bao_gia_transitions():
        if not frappe.db.exists("Workflow Action Master", hanh_dong):
            frappe.get_doc({
                "doctype": "Workflow Action Master", "workflow_action_name": hanh_dong,
            }).insert(ignore_permissions=True)
    if frappe.db.exists("Workflow", bg.WORKFLOW):
        return frappe.get_doc("Workflow", bg.WORKFLOW)
    wf = frappe.get_doc({
        "doctype": "Workflow",
        "workflow_name": bg.WORKFLOW,
        "document_type": "Quotation",
        "is_active": 1,
        "workflow_state_field": "workflow_state",
        "states": [
            {"state": ten, "doc_status": ds, "allow_edit": vai}
            for ten, ds, vai, _kieu in _bao_gia_states()
        ],
        "transitions": [
            {"state": tu, "action": hd, "next_state": toi, "allowed": vai,
             "condition": dk, "allow_self_approval": 1}
            for tu, hd, toi, vai, dk in _bao_gia_transitions()
        ],
    })
    wf.insert(ignore_permissions=True)
    return wf


def gan_trang_thai_bao_gia_cu() -> int:
    """Quotation có TRƯỚC workflow chưa mang `workflow_state`. Gán theo
    docstatus để chúng không kẹt: nháp → chờ Miyano báo giá, đã Submit → khách
    đã đồng ý. Chứng từ đã huỷ để nguyên. Trả số dòng vừa gán."""
    from miyano_portal import bao_gia as bg

    if not frappe.db.has_column("Quotation", "workflow_state"):
        return 0
    dem = 0
    for docstatus, trang_thai in ((0, bg.TT_CHO_MIYANO), (1, bg.TT_DA_DONG_Y)):
        ten = frappe.db.sql_list(
            "select name from `tabQuotation` where docstatus = %s "
            "and coalesce(workflow_state, '') = ''",
            docstatus,
        )
        for t in ten:
            frappe.db.set_value(
                "Quotation", t, "workflow_state", trang_thai, update_modified=False
            )
        dem += len(ten)
    return dem
