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

# sha256 của BẢN HTML mà patch này được viết ra để giao đi.
#
# Vì sao cần một con số chép tay ở đây thay vì tính lại từ hằng số: thân patch
# gọi `v1_28.execute()`, mà hàm đó ghi ra BẤT CỨ THỨ GÌ hằng số đang chứa. Nếu
# bài test chỉ kiểm "chạy các patch sau v1_28 thì HTML hội tụ về hằng số" thì
# nó luôn xanh, kể cả khi hằng số đã đổi và KHÔNG patch nào giao thay đổi đó đi
# — site đã chạy patch này không bao giờ chạy lại nó (Frappe chạy mỗi patch
# đúng một lần theo TÊN). Đã đo đúng lỗ đó: thêm một dòng vào hằng số, không
# thêm patch, cả bộ test vẫn xanh.
#
# Con số này KHÔNG tự đi theo hằng số, nên hằng số đổi là nó lệch và bộ test
# đỏ. Cách đúng để làm nó khớp lại là **thêm một patch mới** mang hash mới,
# KHÔNG phải sửa con số này tại chỗ: patch này có thể đã chạy xong ở site
# khác, sửa hash của nó là nói dối về việc site đó đã nhận được gì.
HTML_DA_GIAO_SHA256 = "b3e5f837fc49eb59cc4f19384ba755a2bf83559c5c42794654f3c94b0adf1b7f"


def execute():
    _dong_bo_02vt()
