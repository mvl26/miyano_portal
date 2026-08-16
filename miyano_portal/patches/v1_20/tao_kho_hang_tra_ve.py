"""Tạo kho "Hàng trả về" cho mọi công ty. Idempotent.

Nghiệp vụ + lý do nằm ở `miyano_portal/kho_hang_tra_ve.py` — patch này chỉ
gọi, vì cùng hàm đó còn được dùng lúc chạy (`portal_kiem_hang.
_tao_phieu_tra_hang`) cho công ty lập sau khi patch đã chạy.
"""

from miyano_portal.kho_hang_tra_ve import dam_bao_moi_cong_ty


def execute():
    dam_bao_moi_cong_ty()
