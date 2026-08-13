"""Cài đặt app trên site MỚI.

Vì sao file này cần tồn tại:

`frappe.installer.install_app()` gọi `set_all_patches_as_completed(name)` rồi
MỚI chạy hook `after_install` (frappe/installer.py:324-329). Nghĩa là trên một
site vừa dựng, toàn bộ patch trong `patches.txt` bị đánh dấu ĐÃ CHẠY mà thực tế
KHÔNG chạy dòng nào. Hệ quả: site mới không có workflow `Sales Order - Client
Portal`, không có custom field nào của Sales Order, không có Notification, báo
cáo, print format — và `bench migrate` sau đó cũng không cứu được, vì nó bỏ qua
patch đã nằm trong Patch Log.

Lỗi này im lặng: app cài "thành công", chỉ tới khi ai đó đặt hàng hoặc duyệt đơn
mới lộ ra là máy trạng thái không tồn tại. Nó chỉ không lộ trên `erptest.local`
vì site đó sống lâu và đã migrate liên tục qua từng patch.

Cách chữa: chạy lại chính những patch đó ngay trong `after_install`. Không chép
lại việc của chúng vào đây — chép là tạo ra bản thứ hai để lệch nhau. Mọi patch
của app này đều idempotent theo yêu cầu của dự án, nên chạy lại là an toàn.
"""

import frappe
from frappe.modules.patch_handler import execute_patch, get_patches_from_app


def after_install():
    """Chạy thật các patch mà `install_app` vừa đánh dấu khống là đã chạy."""
    for patch in get_patches_from_app("miyano_portal"):
        # `execute_patch` chứ không `run_single`: `run_single` kiểm Patch Log
        # trước và sẽ bỏ qua đúng những patch ta cần chạy, vì chúng vừa bị
        # `set_all_patches_as_completed` ghi khống vào đó.
        execute_patch(patch)
    frappe.db.commit()
