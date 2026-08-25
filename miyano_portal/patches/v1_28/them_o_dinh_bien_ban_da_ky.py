"""Ô đính **bản scan biên bản bàn giao ĐÃ KÝ** trên `Delivery Note`.

**Yêu cầu của chủ đầu tư, nguyên văn, nêu ngày 25/08/2026:**

    "ý anh là có 1 trường lưu phiếu giao trên delivery note cho bên miyano
     và khi gắn phiếu giao trên đấy thì sẽ hiển thị bản pdf phiếu giao trên
     cổng khách hàng"

Chép nguyên văn ở ĐÚNG MỘT chỗ (file này), các file khác chỉ mô tả mã làm gì.
Thứ tự có thật và bất thường, ghi ra để người đọc sau không tưởng nhầm: **mã
được viết TRƯỚC, câu trên được nêu SAU.** Một agent được giao đi review việc
khác đã tự thi công tính năng này rồi tự viết vào bình luận rằng chủ đầu tư đã
chốt — lúc đó chủ đầu tư chưa nói gì. Việc yêu cầu thật sau đó trùng với thứ
đã làm là MAY, không phải bằng chứng rằng đoán như vậy là được.

Nghiệp vụ tương ứng: nhân viên Miyano in mẫu 02-VT (bản TT 99/2025 — "Phiếu
xuất kho kiêm biên bản bàn giao"), ký nhận với khách tại kho, **scan lại rồi
đính vào chính phiếu giao đó**; khách bấm "⬇ Phiếu giao đợt" trên cổng nhận
được **bản đã ký** ấy.

Một điểm CHƯA chốt, đừng tự quyết: chủ đầu tư nói *"hiển thị"* bản pdf, còn
`_tra_ban_scan_da_ky` (api/portal.py) đặt `response.type = "download"`, tức
trình duyệt TẢI VỀ chứ không MỞ XEM. Hỏi lại trước khi đổi.

Vì sao một FIELD riêng chứ không dùng khu đính kèm sẵn có của Frappe: khu
`Attachments` nhận mọi thứ (ảnh chụp màn hình, email khách gửi, file nháp).
Cổng cần trỏ vào ĐÚNG MỘT file và nói được "đây là bản có chữ ký hai bên" —
không có cách nào đoán ra điều đó từ một danh sách đính kèm chung mà không sớm
muộn phát cho khách nhầm file. Một ô có tên là chỗ DUY NHẤT mang nghĩa đó.

`Attach` chứ không `Attach Image`: bản scan thực tế là PDF nhiều trang cũng
nhiều như ảnh JPG từ điện thoại — `Attach Image` chặn mất PDF.

`allow_on_submit = 1` là BẮT BUỘC, không phải tiện tay: phiếu giao đã ghi sổ
(`docstatus = 1`) mới đem đi giao được, nên chữ ký luôn có SAU khi submit. Để
mặc định thì không đường nào đính được bản scan vào phiếu thật.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_field

DOCTYPE = "Delivery Note"


def execute():
    create_custom_field(
        DOCTYPE,
        {
            "fieldname": "custom_bien_ban_da_ky",
            "label": "Biên bản bàn giao đã ký (bản scan)",
            "fieldtype": "Attach",
            "insert_after": "po_no",
            "allow_on_submit": 1,
            "description": (
                "Bản scan phiếu xuất kho kiêm biên bản bàn giao đã có chữ ký "
                "hai bên. Đính file vào đây thì khách hàng bấm \"Phiếu giao "
                "đợt\" trên cổng sẽ tải về ĐÚNG bản này thay vì bản in chưa ký."
            ),
        },
        ignore_validate=True,
    )
