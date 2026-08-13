"""Thông báo từ cổng sang nhân viên Miyano.

Chống spam bằng `Notification Log` có sẵn của Frappe thay vì dựng bảng riêng:
bản thân lịch sử thông báo đã là nơi trả lời câu "hôm nay đã báo chưa", thêm
một bảng nữa chỉ tạo thêm một thứ phải giữ đồng bộ.
"""

import frappe
from frappe.utils import today

TIEN_TO = "Portal - Thiếu giá"
TIEN_TO_CHENH_LECH = "Portal - Chênh lệch nhận hàng"
TIEN_TO_YEU_CAU_MOI = "Portal - Yêu cầu hàng hoá mới"
TIEN_TO_HO_TRO_HDDT = "Portal - Yêu cầu hỗ trợ HĐĐT"

# Hai role của module HĐĐT (team Dev) — tạo bởi
# `erpnext.einvoice.setup._make_roles()` khi `bench migrate`, KHÔNG phải role
# của app này. Chỉ THAM CHIẾU tên bằng chuỗi để tìm người nhận, không tạo
# lại/không cấp quyền gì thêm cho chúng.
_ROLE_KE_TOAN_HDDT = ("Kế toán HĐĐT", "Kế toán trưởng HĐĐT")


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


def bao_yeu_cau_moi(customer: str, name: str, ten_hang: str) -> int:
    """US-E6.3 — báo yêu cầu hàng hoá mới cho sales phụ trách VÀ mọi
    `Purchase User`. Trả số Notification Log vừa tạo.

    Khác `bao_thieu_gia`/`bao_chenh_lech`: không chống spam theo cửa sổ thời
    gian, vì sự kiện gọi hàm này (tạo `Portal Item Request`) tự nó chỉ xảy ra
    đúng MỘT lần trong đời một `name` — không có "lần tạo thứ hai" cho cùng
    một yêu cầu để phải chặn.

    Không bao giờ ném lỗi, cùng lý do với hai hàm trên: đây là hiệu ứng phụ
    sau khi yêu cầu ĐÃ được ghi nhận thành công, không được phép biến việc đó
    thành lỗi cho khách.
    """
    nguoi_nhan = set()
    sales = _sales_phu_trach(customer)
    if sales:
        nguoi_nhan.add(sales)
    nguoi_nhan.update(
        frappe.get_all(
            "Has Role",
            filters={"role": "Purchase User", "parenttype": "User"},
            pluck="parent",
        )
    )
    if not nguoi_nhan:
        return 0

    chu_de = f"{TIEN_TO_YEU_CAU_MOI}: {name}"
    dem = 0
    for u in nguoi_nhan:
        if frappe.db.exists("Notification Log", {"subject": chu_de, "for_user": u}):
            continue
        frappe.get_doc({
            "doctype": "Notification Log",
            "subject": chu_de,
            "for_user": u,
            "type": "Alert",
            "document_type": "Portal Item Request",
            "document_name": name,
            "email_content": (
                f"Khách hàng <b>{customer}</b> vừa gửi yêu cầu hàng hoá mới: "
                f"<b>{ten_hang}</b> ({name})."
            ),
        }).insert(ignore_permissions=True)
        dem += 1
    return dem


def bao_yeu_cau_ho_tro_hddt(customer: str, sales_invoice: str, fei: str | None = None) -> int:
    """NL-12.4 — nút [Yêu cầu hỗ trợ] trên khối HĐĐT tự đính mã hoá đơn, báo
    cho nhân viên giữ role "Kế toán HĐĐT" / "Kế toán trưởng HĐĐT". Trả số
    Notification Log vừa tạo (0 nếu chưa ai được gán hai role này — im lặng,
    KHÔNG ném lỗi, cùng khuôn `bao_yeu_cau_moi`: bản thân yêu cầu hỗ trợ của
    khách đã được ghi nhận thành công dù chưa có ai để báo).

    Không chống spam theo cửa sổ thời gian như `bao_thieu_gia` — khách bấm
    "Yêu cầu hỗ trợ" nhiều lần cho cùng hoá đơn (vẫn chưa được xử lý) là tín
    hiệu THẬT ("vẫn đang chờ"), không phải trùng lặp cần chặn.
    """
    nguoi_nhan = set()
    for role in _ROLE_KE_TOAN_HDDT:
        nguoi_nhan.update(
            frappe.get_all(
                "Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent"
            )
        )
    if not nguoi_nhan:
        return 0

    dem = 0
    for u in nguoi_nhan:
        frappe.get_doc({
            "doctype": "Notification Log",
            "subject": f"{TIEN_TO_HO_TRO_HDDT}: {sales_invoice}",
            "for_user": u,
            "type": "Alert",
            "document_type": "Sales Invoice",
            "document_name": sales_invoice,
            "email_content": (
                f"Khách hàng <b>{customer}</b> yêu cầu hỗ trợ hoá đơn điện tử cho "
                f"<b>{sales_invoice}</b>"
                + (f" (chứng từ HĐĐT {fei})" if fei else " (chưa có chứng từ HĐĐT)")
                + "."
            ),
        }).insert(ignore_permissions=True)
        dem += 1
    return dem


def bao_chenh_lech(customer: str, phieu: str) -> bool:
    """US-E3.3 / BR-K17. Trả `True` nếu vừa gửi, `False` nếu không gửi.

    Chống spam theo PHIẾU (không phải theo ngày như `bao_thieu_gia`): một
    `Customer Stock Receipt` chỉ ghi sổ (submit) đúng một lần trong đời của
    tên chứng từ đó — không có "lần ghi sổ thứ hai" cho cùng một `name` để
    phải chặn theo cửa sổ thời gian. Vẫn kiểm tồn tại trước khi insert để gọi
    lại (ví dụ do lỗi transient rồi retry) không sinh trùng.

    Không bao giờ ném lỗi — cùng lý do với `bao_thieu_gia`: đây là một thông
    báo phụ trợ, không được phép biến việc ghi sổ (đã thành công) thành lỗi.
    Người gọi (`CustomerStockReceipt.on_submit`) cũng tự bọc lại một lớp nữa,
    nhưng hàm này vẫn tự chịu trách nhiệm không ném lỗi cho đúng thiết kế.
    """
    nguoi_nhan = _sales_phu_trach(customer)
    if not nguoi_nhan:
        return False

    chu_de = f"{TIEN_TO_CHENH_LECH}: {phieu} ({customer})"
    if frappe.db.exists("Notification Log", {"subject": chu_de, "for_user": nguoi_nhan}):
        return False

    frappe.get_doc({
        "doctype": "Notification Log",
        "subject": chu_de,
        "for_user": nguoi_nhan,
        "type": "Alert",
        "document_type": "Customer Stock Receipt",
        "document_name": phieu,
        "email_content": (
            f"Khách hàng <b>{customer}</b> ghi sổ phiếu nhập <b>{phieu}</b> với "
            "số lượng thực nhận lệch so với số Miyano đã giao. Xem chi tiết "
            "trên phiếu (cột Lý do chênh lệch) hoặc báo cáo Đối soát giao nhận."
        ),
    }).insert(ignore_permissions=True)
    return True
