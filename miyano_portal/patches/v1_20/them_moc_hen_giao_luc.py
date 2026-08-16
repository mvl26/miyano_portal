"""Thêm `custom_hen_giao_luc` cho site ĐÃ chạy `create_hen_giao_custom_fields`.

Patch chỉ chạy MỘT LẦN mỗi site: field mới thêm vào file patch cũ sẽ có mặt
trên bản cài mới nhưng KHÔNG bao giờ tới được site đã migrate. Đây là lý do
có patch thứ hai thay vì sửa file cũ rồi mong nó chạy lại.

`create_custom_fields` tự nó idempotent nên gọi lại toàn bộ bộ field là an
toàn — và đúng hơn là chép riêng một định nghĩa field thứ hai ra đây, vì hai
bản định nghĩa rời nhau chính là chỗ sẽ trôi.
"""

from miyano_portal.patches.v1_20.create_hen_giao_custom_fields import execute as tao_field


def execute():
    tao_field()
