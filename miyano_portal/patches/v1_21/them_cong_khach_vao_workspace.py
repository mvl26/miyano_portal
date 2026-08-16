"""Thêm "Biên bản kiểm hàng" + "Yêu cầu hàng hoá" vào workspace Kho khách hàng.

Hai doctype này mang việc do KHÁCH đẩy sang mà không nằm trong workspace nào —
nhân viên chỉ vào được bằng thông báo hoặc gõ tay tên doctype. Patch v1_2 đã
chạy rồi nên sửa file setup thôi là không đủ: cần lần chạy thứ hai, và
`install_kho_workspace()` giờ cập nhật được workspace đã tồn tại.
"""

from miyano_portal.setup.install_kho_workspace import install_kho_workspace


def execute():
    install_kho_workspace()
