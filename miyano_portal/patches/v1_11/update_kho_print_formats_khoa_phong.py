"""E8 (US-E8.4/BR-CP5) — mẫu in TT107/TT200 phần Xuất kho hiển thị thêm
"Khoa phòng nhận". `install_kho_print_formats()` (patch v1_1) chỉ insert khi
Print Format CHƯA TỒN TẠI nên gọi lại nó là no-op trên site đã cài — phải
ghi đè nội dung HTML bằng một hàm riêng, `update_kho_print_formats_khoa_phong()`
(idempotent theo kiểu "hội tụ về cùng giá trị": gọi lại nhiều lần vẫn ra
đúng nội dung mới nhất).
"""

from miyano_portal.setup.install_kho_print_formats import update_kho_print_formats_khoa_phong


def execute():
	update_kho_print_formats_khoa_phong()
