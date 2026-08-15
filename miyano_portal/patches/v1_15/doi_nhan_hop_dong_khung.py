"""Spec 2026-08-15 §3.1 — "hợp đồng khung" thay "hợp đồng nguyên tắc"/HĐNT
trong Notification, Print Format và label Custom Field ĐÃ CÀI trên site.

`install_portal_notifications()`, `install_portal_print_formats()` và
`create_custom_fields()` đều bỏ qua bản ghi đã tồn tại, nên site đang chạy
sẽ giữ nguyên chữ cũ nếu không có patch này. Chỉ đổi CHỮ HIỂN THỊ — không
đụng `condition`, `document_type`, fieldname hay bất kỳ giá trị dữ liệu nào
(`custom_hdnt`, `thuoc_hdnt`, mã lỗi `thuoc_hdnt_hieu_luc`, giá trị đã lưu
của `custom_loai_don` — đó là dữ liệu, không phải chữ hiển thị, đổi nó là
một cuộc di trú riêng ngoài phạm vi patch này).

Kèm luôn việc thêm 2 của nhóm C: câu "và phản hồi trên cổng khách hàng" ở
Notification "Cần thêm thông tin" bảo khách làm một việc bất khả thi — màn
phản hồi đó đã bị gỡ khỏi cổng ở Task 1/2. Đổi thành hướng dẫn liên hệ nhân
viên phụ trách hoặc trả lời email. Gộp vào cùng patch/bảng THAY vì viết
patch riêng vì cùng cơ chế "cập nhật bản ghi Notification đã cài".

Idempotent: thay chuỗi trên nội dung hiện tại; chạy lại khi đã sạch thì
không có gì để thay. Cập nhật label Custom Field bằng so sánh trực tiếp,
cũng vô hại khi chạy lại.
"""

import frappe

THAY = [
    ("Hợp đồng nguyên tắc", "Hợp đồng khung"),
    ("hợp đồng nguyên tắc", "hợp đồng khung"),
    ("Theo HĐNT", "Theo hợp đồng khung"),
    ("HĐNT", "hợp đồng khung"),
    # Việc thêm 2 — "Cần thêm thông tin" bảo khách phản hồi trên một màn
    # không còn tồn tại trên cổng (Task 1/2 đã gỡ "Yêu cầu hàng hoá").
    (
        "Vui lòng xem chi tiết và phản hồi trên cổng khách hàng.",
        "Vui lòng liên hệ nhân viên phụ trách hoặc trả lời email này để "
        "cung cấp thêm thông tin.",
    ),
]


def _doi(chuoi):
    if not chuoi:
        return chuoi, False
    goc = chuoi
    for cu, moi in THAY:
        chuoi = chuoi.replace(cu, moi)
    return chuoi, chuoi != goc


def execute():
    for ten in frappe.get_all("Notification", pluck="name"):
        doc = frappe.db.get_value("Notification", ten, ["subject", "message"], as_dict=True)
        subject, s_doi = _doi(doc.subject)
        message, m_doi = _doi(doc.message)
        if s_doi or m_doi:
            frappe.db.set_value(
                "Notification", ten, {"subject": subject, "message": message}
            )

    for ten in frappe.get_all(
        "Print Format", filters={"name": ["like", "Miyano -%"]}, pluck="name"
    ):
        html, doi = _doi(frappe.db.get_value("Print Format", ten, "html"))
        if doi:
            frappe.db.set_value("Print Format", ten, "html", html)

    # Step 5 — label `custom_hdnt` trên Sales Order: "Hợp đồng nguyên tắc"
    # -> "Hợp đồng khung". Fieldname/Link options giữ nguyên.
    cf_name = frappe.db.get_value(
        "Custom Field", {"dt": "Sales Order", "fieldname": "custom_hdnt"}, "name"
    )
    if cf_name:
        label = frappe.db.get_value("Custom Field", cf_name, "label")
        if label == "Hợp đồng nguyên tắc":
            frappe.db.set_value("Custom Field", cf_name, "label", "Hợp đồng khung")
