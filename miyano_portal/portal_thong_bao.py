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
TIEN_TO_KIEM_HANG = "Portal - Kiểm hàng có vấn đề"

# Hai role của module HĐĐT (team Dev) — tạo bởi
# `erpnext.einvoice.setup._make_roles()` khi `bench migrate`, KHÔNG phải role
# của app này. Chỉ THAM CHIẾU tên bằng chuỗi để tìm người nhận, không tạo
# lại/không cấp quyền gì thêm cho chúng.
_ROLE_KE_TOAN_HDDT = ("Kế toán HĐĐT", "Kế toán trưởng HĐĐT")


def _sales_phu_trach(customer: str) -> str | None:
    """Nhân viên kinh doanh của khách. Rỗng thì không gửi cho ai cả."""
    return frappe.db.get_value("Customer", customer, "account_manager")


def _nguoi_nhan_kiem_hang(customer: str) -> list[str]:
    """Người nhận cảnh báo biên bản kiểm hàng có vấn đề.

    KHÁC `_sales_phu_trach` ở đúng một điểm và điểm đó là cả lý do hàm này tồn
    tại: `account_manager` rỗng thì **không** im lặng bỏ qua. Một biên bản
    kiểm hàng có vấn đề là khiếu nại về hàng hỏng/thiếu — khách đang chờ
    Miyano trả lời, và một khiếu nại rơi vào im lặng vì khách chưa được gán
    nhân viên phụ trách là hỏng nghiệp vụ, không phải "không có ai để gửi".
    Phát hiện trong UAT 2026-08-16: Bệnh viện Bạch Mai không có
    `account_manager`, biên bản gửi đi mà không sales nào biết.

    Đường lui là role `Sales Manager` — CHÍNH role được phép duyệt/từ chối
    biên bản (`portal_kiem_hang.ROLE_DUYET`), nên người nhận luôn là người
    làm được gì đó với nó. Chỉ dùng khi không có `account_manager`, không
    phải gửi thêm song song: một khiếu nại không cần cả phòng cùng đọc.
    """
    sales = _sales_phu_trach(customer)
    if sales and frappe.db.get_value("User", sales, "enabled"):
        return [sales]
    ung_vien = frappe.get_all(
        "Has Role",
        filters={"role": "Sales Manager", "parenttype": "User",
                 "parent": ["not in", ("Administrator", "Guest")]},
        pluck="parent",
    )
    # Lọc tài khoản đã tắt: `Has Role` không bị dọn khi User bị disable, nên
    # không lọc ở đây là gửi cảnh báo vào một hộp thư không ai mở.
    return [
        u for u in dict.fromkeys(ung_vien)
        if frappe.db.get_value("User", u, "enabled")
    ]


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

    Chống spam theo CẶP (hoá đơn, ngày) mỗi người nhận — review round 1 M-8:
    khách vô tình bấm lại nút nhiều lần (double-click, tải lại trang) không
    được tạo một Notification Log riêng cho mỗi lần bấm; ý định "vẫn đang
    chờ" của một yêu cầu thật vẫn giữ được vì cửa sổ chặn chỉ một ngày, cùng
    khuôn `bao_thieu_gia`.
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

    chu_de = f"{TIEN_TO_HO_TRO_HDDT}: {sales_invoice}"
    dem = 0
    for u in nguoi_nhan:
        da_gui = frappe.db.exists(
            "Notification Log",
            {
                "subject": chu_de,
                "for_user": u,
                "creation": [">=", f"{today()} 00:00:00"],
            },
        )
        if da_gui:
            continue
        frappe.get_doc({
            "doctype": "Notification Log",
            "subject": chu_de,
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


def bao_khach_sua_so_luong(customer: str, order: str, thay_doi: list) -> bool:
    """Việc 1/brief 2026-08-15 — khách sửa số lượng ở "Chờ khách đồng ý" ->
    đơn về "Chờ xác nhận" cho sales báo giá lại (`portal_order_sua_so_luong`).
    Trả `True` nếu vừa gửi.

    KHÔNG chống spam theo cửa sổ thời gian: mỗi lần gọi hàm này ứng với
    ĐÚNG một lần khách bấm "Gửi lại để báo giá" — một `name` (mã đơn) có thể
    hợp lệ nhận nhiều thông báo khác nhau qua thời gian (sửa lần 1, sales
    báo giá lại, khách sửa lần 2...), khác `bao_thieu_gia` (chặn theo NGÀY
    vì một mặt hàng thiếu giá là MỘT sự kiện lặp lại mỗi lần khách thử đặt).
    Cùng khuôn `bao_yeu_cau_moi`.

    Không bao giờ ném lỗi: đây là hiệu ứng phụ SAU KHI đơn đã ghi nhận thay
    đổi thành công, không được phép biến việc đó thành lỗi cho khách.
    """
    nguoi_nhan = _sales_phu_trach(customer)
    if not nguoi_nhan:
        return False

    frappe.get_doc({
        "doctype": "Notification Log",
        "subject": f"Portal - Khách sửa số lượng: {order}",
        "for_user": nguoi_nhan,
        "type": "Alert",
        "document_type": "Sales Order",
        "document_name": order,
        "email_content": (
            f"Khách hàng <b>{customer}</b> vừa sửa số lượng trên đơn "
            f"<b>{order}</b>, đơn đã về \"Chờ xác nhận\" để báo giá lại:<br>"
            + "<br>".join(thay_doi)
        ),
    }).insert(ignore_permissions=True)
    return True


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


def bao_kiem_hang_co_van_de(doc) -> bool:
    """Khách gửi biên bản kiểm hàng có hàng thiếu/hỏng → báo sales phụ trách.

    Chống trùng theo TÊN BIÊN BẢN (không theo ngày), cùng khuôn
    `bao_chenh_lech`: một `Portal Delivery Inspection` chỉ submit đúng một
    lần trong đời của tên chứng từ đó.

    Không bao giờ ném lỗi — người gọi (`PortalDeliveryInspection.on_submit`)
    đã bọc một lớp, hàm này vẫn tự chịu trách nhiệm cho đúng thiết kế của cả
    cụm thông báo.
    """
    try:
        nguoi_nhan = _nguoi_nhan_kiem_hang(doc.customer)
        if not nguoi_nhan:
            frappe.log_error(
                title="Kiểm hàng: không tìm được người nhận cảnh báo",
                message=(
                    f"Biên bản {doc.name} của {doc.customer} có vấn đề nhưng "
                    "site không có Sales Manager nào đang bật. Khiếu nại này "
                    "hiện KHÔNG đến tay ai — gán account_manager cho khách "
                    "hoặc bật một tài khoản Sales Manager."
                ),
            )
            return False

        chu_de = f"{TIEN_TO_KIEM_HANG}: {doc.name} ({doc.customer})"

        if doc.co_hang_hong:
            tom_tat = "báo có hàng <b>hỏng cần trả lại</b>"
        else:
            tom_tat = "báo <b>thiếu hàng</b> so với phiếu giao"

        noi_dung = (
            f"Khách hàng <b>{doc.customer}</b> đã kiểm phiếu giao "
            f"<b>{doc.delivery_note}</b> và {tom_tat}. Mở biên bản "
            f"<b>{doc.name}</b> để duyệt trả hàng hoặc từ chối."
        )
        da_gui = 0
        for u in nguoi_nhan:
            if frappe.db.exists("Notification Log", {"subject": chu_de, "for_user": u}):
                continue
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": chu_de,
                "for_user": u,
                "type": "Alert",
                "document_type": "Portal Delivery Inspection",
                "document_name": doc.name,
                "email_content": noi_dung,
            }).insert(ignore_permissions=True)
            da_gui += 1
        return da_gui > 0
    except Exception:
        try:
            frappe.log_error(
                title="Kiểm hàng: lỗi khi báo sales biên bản có vấn đề",
                message=frappe.get_traceback(with_context=True),
                reference_doctype="Portal Delivery Inspection",
                reference_name=doc.name,
            )
        except Exception:
            pass
        return False
