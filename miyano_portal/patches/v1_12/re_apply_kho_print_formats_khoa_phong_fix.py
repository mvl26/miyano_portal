"""F-4 (review E8, CHẶN) sửa NỘI DUNG `update_kho_print_formats_khoa_phong()`
(v1_11): bản v1_11 in "Khoa phòng nhận" thành một dòng RIÊNG, chọi với dòng
"Nơi nhận" (`doc.noi_nhan`, free text có từ trước E8) — hai phát biểu khác
nhau về cùng một chỗ trên một chứng từ có chữ ký. Bản sửa gộp tên khoa vào
THẲNG ô "Nơi nhận" (chỉ một phát biểu, khoa thắng khi có).

`Patch Log` chỉ ghi TÊN patch v1_11 đã chạy — không so nội dung — nên một
site đã `bench migrate` với patch v1_11 CŨ (trước bản sửa này) sẽ KHÔNG tự
nhận bản vá qua `bench migrate` lần nữa. Gọi LẠI đúng hàm
`update_kho_print_formats_khoa_phong()` (đã tự idempotent-theo-nội-dung —
luôn ghi đè `html` bằng bản MỚI NHẤT, xem docstring ở đó) qua một tên patch
MỚI, đúng khuôn `v1_9/re_apply_workflow_e6_fix.py`.
"""

from miyano_portal.setup.install_kho_print_formats import update_kho_print_formats_khoa_phong


def execute():
	update_kho_print_formats_khoa_phong()
