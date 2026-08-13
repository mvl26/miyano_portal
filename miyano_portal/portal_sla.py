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


def _sla_gio() -> float:
    return float(
        frappe.db.get_single_value("Miyano Portal Settings", "sla_xu_ly_don_gio") or 8
    )


def _nguoi_nhan() -> list[str]:
    return frappe.get_all(
        "Has Role",
        filters={"role": "Sales Manager", "parenttype": "User"},
        pluck="parent",
    )


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
