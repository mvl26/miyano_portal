"""NL-2.6 — đơn treo quá SLA thì leo thang cho Sales Manager.

"Giờ làm việc" ở đây CHỈ bỏ Thứ Bảy và Chủ Nhật: không trừ ngày lễ, không có
khung giờ hành chính trong ngày. Đây là đúng quy ước đã dùng cho BR-O13
(`portal_dat_hang.ngay_giao_mac_dinh`) — một bảng ngày lễ không ai duy trì sẽ
sai lệch âm thầm, tệ hơn là không có vì nó tạo cảm giác đã được xử lý.
"""

import frappe
from frappe.utils import get_datetime, now_datetime

TRANG_THAI_TREO = "Chờ Miyano xác nhận"
TIEU_DE = "Portal - Đơn treo SLA"

# E6/NL-11.2 — leo thang yêu cầu hàng hoá đứng quá lâu ở "Mới".
TRANG_THAI_YEU_CAU_MOI = "Mới"
TIEU_DE_YEU_CAU = "Portal - Yêu cầu hàng hoá treo SLA"


def gio_lam_viec_troi_qua(tu_luc, moc=None) -> float:
    """Số giờ từ `tu_luc` tới `moc`, KHÔNG tính giờ rơi vào T7/CN."""
    dau = get_datetime(tu_luc)
    cuoi = get_datetime(moc) if moc else now_datetime()
    if cuoi <= dau:
        return 0.0
    tong = 0.0
    buoc = dau
    while buoc < cuoi:
        # Cắt theo từng mốc nửa đêm để không phải giả định gì về độ dài khoảng.
        het_ngay = get_datetime(buoc.date().isoformat() + " 23:59:59")
        ket = min(cuoi, het_ngay)
        if buoc.weekday() < 5:   # 0=T2 … 4=T6
            tong += (ket - buoc).total_seconds() / 3600.0
        buoc = get_datetime(
            frappe.utils.add_to_date(buoc.date().isoformat() + " 00:00:00", days=1)
        )
    return tong


def cong_gio_lam_viec(tu_luc, so_gio: float):
    """Chiều NGƯỢC của `gio_lam_viec_troi_qua`: cộng tiến `so_gio` giờ làm
    việc (bỏ T7/CN) kể từ `tu_luc`, trả về mốc Datetime.

    Sống trong CÙNG file với `gio_lam_viec_troi_qua` và dùng đúng một quy ước
    "giờ làm việc" (weekday() < 5, cắt theo mốc 23:59:59 mỗi ngày) — không
    phải một cách đếm giờ độc lập. Dùng để tính `Portal Item Request.sla_den_han`
    (hiển thị "hạn phản hồi" cho khách); chốt chặn SLA THẬT để leo thang vẫn
    luôn là `gio_lam_viec_troi_qua` gọi trong `quet_yeu_cau_qua_han`, không
    phải so sánh với mốc trả về từ đây — hai hướng cùng thuật toán nhưng cắt
    ngày theo 23:59:59 nên có thể lệch vài giây tại biên ngày, không đủ để
    ảnh hưởng quyết định "đã quá SLA hay chưa" ở thang giờ.
    """
    con_lai = float(so_gio)
    diem = get_datetime(tu_luc)
    if con_lai <= 0:
        return diem
    while con_lai > 0:
        het_ngay = get_datetime(diem.date().isoformat() + " 23:59:59")
        gio_con_trong_ngay = (het_ngay - diem).total_seconds() / 3600.0
        if diem.weekday() < 5 and gio_con_trong_ngay > 0:
            if con_lai <= gio_con_trong_ngay:
                return frappe.utils.add_to_date(diem, hours=con_lai)
            con_lai -= gio_con_trong_ngay
        diem = get_datetime(
            frappe.utils.add_to_date(diem.date().isoformat() + " 00:00:00", days=1)
        )
    return diem


def _sla_gio() -> float:
    return float(
        frappe.db.get_single_value("Miyano Portal Settings", "sla_xu_ly_don_gio") or 8
    )


def _sla_yeu_cau_gio() -> float:
    """BR-Y1 — mặc định 48 giờ làm việc.

    `frappe.db.get_single_value` đọc thẳng `tabSingles`, KHÔNG rơi về
    `default` khai trong DocType JSON khi Settings chưa từng được lưu (xem
    patches/v1_6/seed_portal_settings_defaults.py) — fallback `or 48` tường
    minh ở đây là bắt buộc, không phải phòng thủ thừa.
    """
    return float(
        frappe.db.get_single_value("Miyano Portal Settings", "sla_yeu_cau_gio") or 48
    )


def _nguoi_co_role(role: str) -> list[str]:
    return frappe.get_all(
        "Has Role",
        filters={"role": role, "parenttype": "User"},
        pluck="parent",
    )


def _nguoi_nhan() -> list[str]:
    return _nguoi_co_role("Sales Manager")


def quet_don_treo(moc=None) -> int:
    """Quét đơn treo quá SLA, tạo Notification leo thang. Trả số đơn đã nhắc.

    Mỗi đơn tối đa MỘT lần mỗi ngày: job chạy hourly, không chặn thì mỗi đơn
    treo sẽ đẻ ra 24 thông báo một ngày và Sales Manager sẽ tắt hết thông báo.
    """
    sla = _sla_gio()
    nguoi_nhan = _nguoi_nhan()
    if not nguoi_nhan:
        return 0
    hom_nay = frappe.utils.nowdate()
    dem = 0
    for so in frappe.get_all(
        "Sales Order",
        filters={"workflow_state": TRANG_THAI_TREO, "docstatus": 0},
        fields=["name", "customer", "modified", "grand_total"],
    ):
        if gio_lam_viec_troi_qua(so.modified, moc=moc) < sla:
            continue
        tieu_de = f"{TIEU_DE}: {so.name}"
        da_nhac = frappe.db.exists(
            "Notification Log",
            {"subject": tieu_de, "creation": (">=", hom_nay + " 00:00:00")},
        )
        if da_nhac:
            continue
        for u in nguoi_nhan:
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": tieu_de,
                "for_user": u,
                "type": "Alert",
                "document_type": "Sales Order",
                "document_name": so.name,
                "email_content": (
                    f"Đơn {so.name} của {so.customer} đã chờ xác nhận quá "
                    f"{sla:g} giờ làm việc."
                ),
            }).insert(ignore_permissions=True)
        dem += 1
    return dem


def quet_yeu_cau_qua_han(moc=None) -> int:
    """E6/NL-11.2/BR-Y1 — yêu cầu hàng hoá đứng quá `sla_yeu_cau_gio` giờ làm
    việc mà chưa chuyển khỏi "Mới" thì leo thang Sales Manager.

    Đếm giờ trôi qua tính từ `creation`, KHÔNG phải `modified` như
    `quet_don_treo` dùng cho Sales Order: khách được sửa yêu cầu của mình khi
    còn "Mới" (US-E6.3/portal_yeu_cau_save), và mỗi lần sửa cập nhật
    `modified` — dùng `modified` ở đây sẽ để khách tự (vô tình) reset đồng hồ
    SLA của chính họ mỗi lần sửa nháp, trong khi SLA đo thời gian NỘI BỘ
    Miyano trả lời, không phải thời gian khách còn chỉnh sửa.

    Cùng khuôn chống spam với `quet_don_treo`: tối đa một Notification Log
    mỗi yêu cầu mỗi ngày, dù job chạy hourly.
    """
    sla = _sla_yeu_cau_gio()
    nguoi_nhan = _nguoi_nhan()
    if not nguoi_nhan:
        return 0
    hom_nay = frappe.utils.nowdate()
    dem = 0
    for yc in frappe.get_all(
        "Portal Item Request",
        filters={"trang_thai": TRANG_THAI_YEU_CAU_MOI},
        fields=["name", "customer", "ten_hang", "creation"],
    ):
        if gio_lam_viec_troi_qua(yc.creation, moc=moc) < sla:
            continue
        tieu_de = f"{TIEU_DE_YEU_CAU}: {yc.name}"
        da_nhac = frappe.db.exists(
            "Notification Log",
            {"subject": tieu_de, "creation": (">=", hom_nay + " 00:00:00")},
        )
        if da_nhac:
            continue
        for u in nguoi_nhan:
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": tieu_de,
                "for_user": u,
                "type": "Alert",
                "document_type": "Portal Item Request",
                "document_name": yc.name,
                "email_content": (
                    f"Yêu cầu {yc.name} ({yc.ten_hang}) của {yc.customer} vẫn "
                    f"ở trạng thái Mới sau {sla:g} giờ làm việc — chưa ai xử lý."
                ),
            }).insert(ignore_permissions=True)
        dem += 1
    return dem
