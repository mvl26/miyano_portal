"""Thêm shortcut màn "Nhập nhân sự bệnh viện" vào workspace Kho khách hàng.

Cùng lý do như `v1_21.them_cong_khach_vao_workspace`: patch cài workspace đã
chạy từ lâu trên site thật, nên sửa `install_kho_workspace.py` thôi là không
đủ — phải có một lần chạy nữa thì shortcut mới tới được site đã cài.
"""

from miyano_portal.setup.install_kho_workspace import install_kho_workspace


def execute():
	install_kho_workspace()
