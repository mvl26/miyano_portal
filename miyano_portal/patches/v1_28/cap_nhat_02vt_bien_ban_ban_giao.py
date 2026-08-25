"""Cập nhật mẫu 02-VT sang bản TT 99/2025 — "Phiếu xuất kho kiêm biên bản bàn giao".

`install_bien_ban_print_formats()` idempotent theo kiểu "bỏ qua nếu đã có" —
site đã chạy patch cài mẫu sẽ KHÔNG bao giờ nhận được bản sửa. Ghi đè thẳng
HTML của đúng một mẫu, cùng khuôn `cap_nhat_02vt_tien_bang_chu` (v1_21) và
`update_kho_print_formats_khoa_phong` (v1_11).

Không đụng `gan_mau_in_mac_dinh`: 02-VT ĐÃ là mẫu mặc định của `Delivery Note`
từ trước (`setup/gan_mau_in_mac_dinh.py`), nên nhân viên bấm In là ra bản mới
mà không phải chọn gì.

**Ghi đè phải NHÌN THẤY ĐƯỢC.** Bản đầu của patch này ghi đè vô điều kiện kèm
`update_modified=False`: không so sánh, không dấu vết. Đo được trên
`erptest.local` — `tabPatch Log` ghi patch chạy 25/08 12:14 trong khi
`Print Format.modified` vẫn là 16/08. Việc đó quan trọng vì site chạy thật
(`miyano`) CHƯA chạy patch này: nếu ở đó mẫu in từng được sửa tay (logo, số
tài khoản, mẫu tiêu đề thư), patch xoá bản sửa ấy mà không ai biết. Ba quyết
định, ghi ra để lần sau không phải đoán:

  * **Nội dung vẫn hội tụ về mã nguồn.** Giữ một bản sửa tay lại là để hai
    phiên bản mẫu chạy song song trên các site khác nhau — thứ mà chính patch
    này sinh ra để chấm dứt.
  * **Không đổi gì thì KHÔNG ghi gì.** So HTML trước; giống nhau thì thoát.
    `bench migrate` chạy lại không được để lại dấu vết giả, và không được dời
    `modified`.
  * **Ghi đè thật thì để `modified` chạy theo** (bỏ `update_modified=False`,
    đúng khuôn v1_11) và ghi MỘT dòng `Error Log` mang độ dài + sha256 của
    bản cũ. Không lưu nguyên bản cũ vào log: nó vài chục KB, và Error Log
    không phải chỗ chứa bản sao lưu. Độ dài + hash chỉ để **PHÁT HIỆN** đã có
    thay đổi và nhận ra bản nào bị thay — **không phục hồi được gì**, và
    không có bản sao lưu nào được xác lập ở đâu để "đối chiếu". Muốn giữ lại
    bản cũ thì phải TỰ chụp sao lưu TRƯỚC khi chạy `bench migrate`. (Lời trong
    chính dòng log nói đúng như vậy — hai chỗ phải khớp nhau.)
"""

import hashlib

import frappe

from miyano_portal.setup.install_bien_ban_print_formats import (
    HTML_PHIEU_XUAT_02VT,
    NAME_PHIEU_XUAT_02VT,
)

# Tiêu đề dòng Error Log ghi lại việc ghi đè. Đặt tên hằng để cả patch lẫn
# test cùng trỏ vào một chuỗi — dòng log phải tra được bằng `method`.
TIEU_DE_LOG = "cap_nhat_02vt_bien_ban_ban_giao"


def execute():
    if not frappe.db.exists("Print Format", NAME_PHIEU_XUAT_02VT):
        # Dựng ĐÚNG một mẫu. Bản trước gọi `install_bien_ban_print_formats()`,
        # hàm đó dựng CẢ BA mẫu — hồi sinh cả mẫu mà một site có thể đã CỐ Ý
        # gỡ bỏ. Một patch mang tên "cập nhật 02-VT" không được tự ý làm việc
        # đó nhân tiện.
        frappe.get_doc({
            "doctype": "Print Format",
            "name": NAME_PHIEU_XUAT_02VT,
            "doc_type": "Delivery Note",
            "standard": "No",
            "custom_format": 1,
            "print_format_type": "Jinja",
            "html": HTML_PHIEU_XUAT_02VT,
        }).insert(ignore_permissions=True)
        return

    cu = frappe.db.get_value("Print Format", NAME_PHIEU_XUAT_02VT, "html") or ""
    if cu == HTML_PHIEU_XUAT_02VT:
        return

    frappe.log_error(
        TIEU_DE_LOG,
        f"Đã ghi đè HTML của mẫu in «{NAME_PHIEU_XUAT_02VT}».\n"
        f"Bản BỊ THAY: {len(cu)} ký tự, "
        f"sha256={hashlib.sha256(cu.encode('utf-8')).hexdigest()}\n"
        f"Bản MỚI: {len(HTML_PHIEU_XUAT_02VT)} ký tự, "
        f"sha256={hashlib.sha256(HTML_PHIEU_XUAT_02VT.encode('utf-8')).hexdigest()}\n"
        "Nếu mẫu trên site này từng được sửa tay (logo, số tài khoản, mẫu "
        "tiêu đề thư), bản sửa đó vừa bị thay bằng mẫu của mã nguồn.\n"
        "Bản cũ KHÔNG được lưu lại ở đâu cả: độ dài + hash trên đây chỉ để "
        "PHÁT HIỆN đã có thay đổi, không phục hồi được. Muốn giữ được bản cũ "
        "thì phải tự chụp bản sao lưu TRƯỚC khi chạy `bench migrate`.",
    )
    # `bench migrate` chạy trong terminal của người vận hành — in ra đây để họ
    # THẤY ngay. Một dòng Error Log chỉ tìm được khi đã biết mà đi tìm.
    print(
        f"[miyano_portal] Đã ghi đè HTML mẫu in «{NAME_PHIEU_XUAT_02VT}» "
        f"({len(cu)} → {len(HTML_PHIEU_XUAT_02VT)} ký tự). "
        f"Chi tiết trong Error Log, method = {TIEU_DE_LOG}."
    )
    frappe.db.set_value(
        "Print Format", NAME_PHIEU_XUAT_02VT, "html", HTML_PHIEU_XUAT_02VT
    )
