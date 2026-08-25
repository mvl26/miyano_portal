"""Ruling P46 — tắt mẫu in `Phiếu xuất kho (02-VT)` (KHÔNG tiền tố Miyano).

Site mang **ba** mẫu in cho `Delivery Note`. Mẫu này (`module = Regional`,
`creation = modified = 16/07/2026 10:00:00` — dấu vết của một bản nhập tay,
không do app này cài) chỉ khác mẫu của Miyano đúng tiền tố "Miyano - ", và
nằm ngay cạnh nó trong dropdown "In" trên Desk. Bấm nhầm là in ra một tờ có
trích TT 99/2025 nhưng KHÔNG có cột Số lô/Hạn dùng, KHÔNG có đoạn cam kết bàn
giao, KHÔNG có bốn ô ký của bản mẫu — tức một tờ giấy khác cho cùng một lần
giao hàng, đúng lớp sự việc mà cả Task 14 sinh ra để dẹp.

Đã tra trước khi tắt: KHÔNG `Property Setter` nào (`default_print_format`) và
KHÔNG chuỗi nào trong mã app trỏ vào mẫu này.

**Tắt (`disabled = 1`), KHÔNG xoá.** Giữ bản ghi thì còn trả lời được "tờ
phiếu tháng 7 đó in bằng mẫu nào"; xoá thì mất luôn khả năng ấy. Nếu mẫu đã
bị gỡ khỏi site thì patch KHÔNG dựng lại — patch này để tắt một thứ, không để
hồi sinh nó.

Khớp theo TÊN CHÍNH XÁC (khoá chính), không `like`: tên mẫu của Miyano chứa
nguyên văn tên này, một phép khớp mờ sẽ tắt luôn mẫu mà cổng đang phát cho
khách.
"""

import frappe

TEN_MAU_TRAN = "Phiếu xuất kho (02-VT)"


def execute():
    if not frappe.db.exists("Print Format", TEN_MAU_TRAN):
        return
    if frappe.db.get_value("Print Format", TEN_MAU_TRAN, "disabled"):
        return
    frappe.db.set_value("Print Format", TEN_MAU_TRAN, "disabled", 1)
    print(
        f"[miyano_portal] Đã TẮT mẫu in «{TEN_MAU_TRAN}» (giữ nguyên bản ghi, "
        "không xoá) — Ruling P46."
    )
