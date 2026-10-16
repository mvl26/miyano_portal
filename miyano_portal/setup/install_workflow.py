import frappe

WORKFLOW = "Sales Order - Client Portal"

# Đơn từ cổng chỉ còn vòng Miyano xác nhận: vòng báo giá đi trên Quotation
# (spec 2026-10-12). Các patch cũ (v1_4, v1_8, v1_18, v1_41) vẫn thêm trạng
# thái của vòng báo giá cũ; patch v1_44 xoá chúng, nên site mới và site nâng
# cấp kết thúc với CÙNG một workflow.


def _ensure_states():
    for s, style in [
        ("Chờ xác nhận", ""), ("Chờ Miyano xác nhận", ""), ("Đã xác nhận", ""),
        ("Từ chối", ""),
    ]:
        if not frappe.db.exists("Workflow State", s):
            frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": s, "style": style}).insert(ignore_permissions=True)
    for a in ["Gửi duyệt", "Xác nhận", "Từ chối"]:
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
        ],
        "transitions": [
            {"state": "Chờ xác nhận", "action": "Gửi duyệt", "next_state": "Chờ Miyano xác nhận", "allowed": "Sales User"},
            {"state": "Chờ Miyano xác nhận", "action": "Xác nhận", "next_state": "Đã xác nhận", "allowed": "Sales User"},
            {"state": "Chờ Miyano xác nhận", "action": "Từ chối", "next_state": "Từ chối", "allowed": "Sales User"},
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
        # Báo giá theo đợt (spec 2026-10-15 §3.2). Cả hai giữ docstatus 0: phiếu
        # gốc luôn là nháp để dòng của đợt bị từ chối/hết hạn quay về được.
        (bg.TT_DA_BAO_HET, "0", "System Manager", "Info"),
        (bg.TT_HUY_CON_LAI, "0", "Sales Manager", "Danger"),
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
        _canh_mo_lai(),
        *_canh_theo_dot(),
    ]


def _canh_mo_lai():
    """Lối ra duy nhất của "Báo giá hết hạn" (chủ dự án chốt 13/10/2026):
    Sales Manager mở lại, báo giá về "Chờ Miyano báo giá" để gửi khách lần
    nữa. Đứng CUỐI danh sách bước chuyển: `mo_rong_workflow_bao_gia()` nối nó
    vào cuối workflow đã cài, nên site mới và site nâng cấp ra cùng thứ tự."""
    from miyano_portal import bao_gia as bg

    return (bg.TT_HET_HAN, bg.HD_MO_LAI, bg.TT_CHO_MIYANO, "Sales Manager", None)


def _canh_theo_dot():
    """Ba bước của báo giá theo đợt (spec 2026-10-15 §3.2), đứng SAU «Mở lại»
    vì `mo_rong_workflow_theo_dot()` nối chúng vào cuối workflow đã cài.

    Điều kiện "đã có ít nhất một đợt" giấu «Huỷ phần còn lại» trên phiếu chưa
    tách đợt (phiếu đó dùng «Từ chối» như cũ) — `apply_workflow` cũng lọc theo
    điều kiện nên không gọi lách được. Hai bước «Hệ thống: …» khai vai
    `Administrator`: chỉ code (`bao_gia_theo_dot`) áp chúng."""
    from miyano_portal import bao_gia as bg

    co_dot = 'frappe.db.get_value("Quotation", {"custom_phieu_goc": doc.name}, "name")'
    return [
        (bg.TT_CHO_MIYANO, bg.HD_HUY_CON_LAI, bg.TT_HUY_CON_LAI, "Sales User", co_dot),
        (bg.TT_CHO_MIYANO, bg.HD_BAO_HET, bg.TT_DA_BAO_HET, "Administrator", co_dot),
        (bg.TT_DA_BAO_HET, bg.HD_CON_HANG, bg.TT_CHO_MIYANO, "Administrator", None),
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


def mo_rong_workflow_bao_gia() -> bool:
    """Thêm bước "Báo giá hết hạn" → «Mở lại» → "Chờ Miyano báo giá" vào
    workflow ĐÃ CÀI (`install_quotation_workflow()` thoát sớm khi workflow đã
    có). Cùng khuôn `patches/v1_41/gia_theo_price_list.mo_rong_workflow`:
    idempotent theo nội dung, chỉ thêm khi chưa có đúng bộ bốn khoá. Site mới
    có sẵn bước này từ `_bao_gia_transitions()`, nên ở đó hàm không làm gì.
    Workflow Action Master do `install_quotation_workflow()` đảm bảo."""
    from miyano_portal import bao_gia as bg

    if not frappe.db.exists("Workflow", bg.WORKFLOW):
        return False
    state, action, next_state, allowed, condition = _canh_mo_lai()
    wf = frappe.get_doc("Workflow", bg.WORKFLOW)
    if not {state, next_state} <= {s.state for s in wf.states}:
        return False
    if (state, action, next_state, allowed) in {
        (t.state, t.action, t.next_state, t.allowed) for t in wf.transitions
    }:
        return False
    wf.append("transitions", {
        "state": state, "action": action, "next_state": next_state, "allowed": allowed,
        "condition": condition, "allow_self_approval": 1,
    })
    wf.flags.ignore_permissions = True
    wf.save()
    return True


def mo_rong_workflow_theo_dot() -> bool:
    """Thêm hai trạng thái và ba bước của báo giá theo đợt vào workflow ĐÃ CÀI.
    Cùng khuôn `mo_rong_workflow_bao_gia`: idempotent theo nội dung. Workflow
    State / Workflow Action Master do `install_quotation_workflow()` đảm bảo —
    gọi hàm đó trước."""
    from miyano_portal import bao_gia as bg

    if not frappe.db.exists("Workflow", bg.WORKFLOW):
        return False
    wf = frappe.get_doc("Workflow", bg.WORKFLOW)
    doi = False
    co_trang_thai = {s.state for s in wf.states}
    for ten, ds, vai, _kieu in _bao_gia_states():
        if ten not in co_trang_thai:
            wf.append("states", {"state": ten, "doc_status": ds, "allow_edit": vai})
            doi = True
    co_canh = {(t.state, t.action, t.next_state, t.allowed) for t in wf.transitions}
    for tu, hd, toi, vai, dk in _canh_theo_dot():
        if (tu, hd, toi, vai) not in co_canh:
            wf.append("transitions", {
                "state": tu, "action": hd, "next_state": toi, "allowed": vai,
                "condition": dk, "allow_self_approval": 1,
            })
            doi = True
    if doi:
        wf.flags.ignore_permissions = True
        wf.save()
    return doi


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
