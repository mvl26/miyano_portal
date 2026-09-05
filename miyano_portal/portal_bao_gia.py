"""US-E6.5 / NL-10.5 — job daily đóng báo giá "Chờ khách đồng ý" quá hạn
hiệu lực: huỷ nháp (chuyển workflow_state "Báo giá hết hạn") + email HAI
PHÍA (khách + sales phụ trách) + yêu cầu gốc chuyển "Hết hạn".

Dùng `frappe.sendmail` trực tiếp thay vì định nghĩa `Notification` khai báo
(khuôn `setup/install_notifications.py` đang dùng cho các email khác của
app): một bản ghi `Notification` chỉ định tuyến người nhận theo TRƯỜNG của
CHÍNH doctype đang kích hoạt sự kiện — `Sales Order` không có trường nào trỏ
tới "sales phụ trách" (trường đó nằm trên `Customer.account_manager`), nên
không diễn đạt được "gửi cho CẢ khách lẫn sales phụ trách của khách đó" chỉ
bằng khai báo. Job này biết cả hai địa chỉ ngay tại chỗ nên gọi thẳng.
"""

import frappe
from frappe.utils import format_date, getdate, nowdate

from miyano_portal.portal_mua_le import (
    LOAI_DON_BAO_GIA,
    TRANG_THAI_CHO_KHACH,
    cap_nhat_yeu_cau_goc,
    han_hieu_luc_bao_gia,
)

WF = "Sales Order - Client Portal"
ACTION_HET_HAN = "Báo giá hết hạn"


def _email_khach(so) -> str | None:
    if so.get("contact_email"):
        return so.contact_email
    parent = frappe.db.get_value(
        "Dynamic Link",
        {"parenttype": "Contact", "link_doctype": "Customer", "link_name": so.customer},
        "parent",
    )
    if not parent:
        return None
    return frappe.db.get_value(
        "Contact Email", {"parent": parent, "is_primary": 1}, "email_id"
    ) or frappe.db.get_value("Contact Email", {"parent": parent}, "email_id")


def _email_sales_phu_trach(customer: str) -> str | None:
    return frappe.db.get_value("Customer", customer, "account_manager")


def _gui_email_het_han(so, han_hieu_luc) -> None:
    """Không bao giờ để lỗi gửi mail chặn việc đóng đơn/cập nhật yêu cầu gốc
    — cùng nguyên tắc phòng thủ với `portal_thong_bao.py`. Gửi được người
    nào thì gửi người đó, một địa chỉ thiếu không chặn địa chỉ còn lại.
    """
    han_str = format_date(han_hieu_luc, "dd/mm/yyyy")
    noi_dung = (
        f"<p>Báo giá cho đơn <b>{so.name}</b> (khách hàng {so.customer}) đã "
        f"hết hiệu lực ngày <b>{han_str}</b> mà chưa được đồng ý trên cổng "
        f"khách hàng. Đơn đã tự động đóng.</p>"
        f"<p>Nếu vẫn cần hàng, vui lòng gửi yêu cầu báo giá mới.</p>"
    )
    for nguoi_nhan in {_email_khach(so), _email_sales_phu_trach(so.customer)}:
        if not nguoi_nhan:
            continue
        try:
            frappe.sendmail(
                recipients=[nguoi_nhan],
                subject=f"Báo giá {so.name} đã hết hiệu lực",
                message=noi_dung,
                reference_doctype="Sales Order",
                reference_name=so.name,
                now=False,
            )
        except Exception:
            frappe.log_error(
                title="portal_bao_gia: gửi email hết hạn thất bại",
                message=frappe.get_traceback(),
            )


def gui_email_khach_huy(so, ly_do: str) -> None:
    """Việc 2 / brief 2026-08-15 (bao-gia-hai-chieu) — email HAI PHÍA khi
    khách bấm nút Huỷ ở "Chờ khách đồng ý" (`api/portal.py::portal_order_
    huy`). Cùng khuôn `_gui_email_het_han`: không bao giờ để lỗi gửi mail
    chặn hành động chính (đơn đã huỷ THẬT, khách/sales cần biết, không phải
    ngược lại), gửi được người nào thì gửi người đó.
    """
    noi_dung = (
        f"<p>Đơn <b>{so.name}</b> (khách hàng {so.customer}) đã được "
        f"<b>chính khách hàng huỷ</b> trên cổng khách hàng.</p>"
        f"<p>Lý do: {ly_do}</p>"
    )
    for nguoi_nhan in {_email_khach(so), _email_sales_phu_trach(so.customer)}:
        if not nguoi_nhan:
            continue
        try:
            frappe.sendmail(
                recipients=[nguoi_nhan],
                subject=f"Đơn {so.name} đã bị khách hàng huỷ",
                message=noi_dung,
                reference_doctype="Sales Order",
                reference_name=so.name,
                now=False,
            )
        except Exception:
            frappe.log_error(
                title="portal_bao_gia: gửi email khách huỷ thất bại",
                message=frappe.get_traceback(),
            )


def quet_bao_gia_het_han(moc=None) -> int:
    """Quét MỌI SO còn ở "Chờ khách đồng ý" (nháp, `docstatus=0`) mà
    `han_hieu_luc_bao_gia(so)` đã trôi qua so với `moc` (mặc định hôm nay).
    Trả số đơn vừa đóng.

    Đăng ký ở `hooks.py::scheduler_events["daily"]`.
    """
    hom_nay = getdate(moc) if moc else getdate(nowdate())
    dem = 0
    for so_row in frappe.get_all(
        "Sales Order",
        # review I-2(c) — CHỈ quét đơn "Mua lẻ". State "Chờ khách đồng ý"
        # không phải riêng của E6: E2 (US-E2.5) đã dùng nó cho MỌI loại đơn
        # cần khách duyệt giá, không có khái niệm hiệu lực N ngày. Thiếu
        # điều kiện này thì một đơn HĐNT đang chờ khách duyệt theo luồng E2
        # gốc (có thể mở nhiều tuần, không ai coi là "hết hạn") cũng bị job
        # này tự đóng — một hành vi BR-R5 (phạm vi QT10/mua lẻ) chưa từng
        # yêu cầu cho nhánh HĐNT.
        #
        # Task 6 (QĐ-G2b) — chốt này KHÔNG gọi được `portal_mua_le.
        # di_vong_bao_gia()`: đây là FILTER CSDL, không phải một phép hỏi
        # trên một `doc` đã tải. Đó cũng chính là một trong hai lý do vị ngữ
        # kia đọc DẤU ĐÓNG `custom_loai_don` chứ không suy lại từ dòng — nếu
        # nó suy lại từ dòng thì job này và các endpoint sẽ nói khác nhau về
        # CÙNG một đơn. Đổi vị ngữ kia mà quên đây là làm hai bên lệch nhau.
        filters={
            "workflow_state": TRANG_THAI_CHO_KHACH, "docstatus": 0,
            "custom_loai_don": LOAI_DON_BAO_GIA,
        },
        # review I-2(a) round 2 — thêm custom_ngay_gui_khach_duyet: mốc tính
        # hạn hiệu lực giờ là ngày GỬI khách duyệt, không phải transaction_date.
        fields=["name", "customer", "transaction_date", "custom_yeu_cau_goc",
                "custom_ngay_gui_khach_duyet"],
    ):
        han = han_hieu_luc_bao_gia(so_row)
        if hom_nay <= han:
            continue

        so = frappe.get_doc("Sales Order", so_row.name)
        from frappe.model.workflow import apply_workflow

        # Job scheduler chạy dưới quyền Administrator (không phải phiên
        # khách/sales như `portal_order_accept`) — không cần trò đổi
        # `session.user` tạm thời ở đó, `apply_workflow` tự thấy đủ vai trò
        # "System Manager" mà transition này yêu cầu.
        so = apply_workflow(so, ACTION_HET_HAN)
        so.add_comment(
            "Comment",
            f"[Hệ thống] Báo giá hết hiệu lực ngày {format_date(han, 'dd/mm/yyyy')} — tự đóng.",
        )

        cap_nhat_yeu_cau_goc(so, "Hết hạn")
        _gui_email_het_han(so, han)
        dem += 1
    return dem
