"""Đồng bộ lại mẫu 02-VT sau bản vá cột "SL yêu cầu" (Ruling P43).

**Vì sao phải có một patch MỚI thay vì sửa `v1_28`:** Frappe chạy mỗi patch
ĐÚNG MỘT LẦN — `tabPatch Log` ghi TÊN patch, không so nội dung. Site nào đã
chạy `v1_28.cap_nhat_02vt_bien_ban_ban_giao` sẽ không bao giờ chạy lại nó, nên
mọi sửa đổi sau đó trong `HTML_PHIEU_XUAT_02VT` **không tới được site đó bằng
`bench migrate`**. Không có patch này, site đã chạy v1_28 giữ vĩnh viễn bản mẫu
in cùng một con số vào cả hai cột "SL yêu cầu"/"SL thực xuất" — tờ giấy khai
"giao đầy đủ" cho một đơn giao thiếu, ngay trên chỗ khách đặt bút ký.

Bán kính hẹp trên thực tế (bản có lỗi chỉ tồn tại 46 phút, chỉ `erptest.local`
kịp chạy), nhưng phục hồi site đó từ một bản sao lưu chụp trong khoảng ấy sẽ
âm thầm quay lại đúng tờ phiếu bịa số. Patch này là đường duy nhất đưa nó về.

Cùng khuôn `v1_12.re_apply_kho_print_formats_khoa_phong_fix` — gọi LẠI đúng
hàm đã tự idempotent-theo-nội-dung, dưới một TÊN PATCH mới. Không chép lại
thân hàm: bản vá "ghi đè phải nhìn thấy được" (so nội dung trước, ghi Error
Log + in ra stdout khi có thay đổi thật) nằm ở đó, chép ra đây là để hai bản
trôi dần khỏi nhau.
"""

from miyano_portal.patches.v1_28.cap_nhat_02vt_bien_ban_ban_giao import (
    execute as _dong_bo_02vt,
)


def execute():
    _dong_bo_02vt()
