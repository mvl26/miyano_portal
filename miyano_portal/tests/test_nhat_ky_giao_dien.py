"""Lưới REGEX cho phần GIAO DIỆN của "sổ nhật ký thao tác + dòng thời gian"
(Task 6/7/8, xem `.superpowers/sdd/2026-09-03-nhat-ky-thao-tac-va-timeline/
task-678-brief.md` và `docs/superpowers/specs/2026-09-03-nhat-ky-thao-tac-
va-timeline-design.md` §9).

Frontend KHÔNG có hạ tầng test tự động (`package.json` chỉ có `vite build`)
— đây là lưới DUY NHẤT canh các bất biến giao diện của khối này. Cùng khuôn
`test_de_xuat_action_registry.py`/`test_giai_doan_khoa_va_nhan.py`: đọc file
`.vue`/`.js` bằng REGEX có chủ đích, KHÔNG parse JS/Vue — một parser JS
trong test Python là thứ phải bảo trì mà không đổi lại được gì.

HAI BÀI HỌC ĐẮT của nhánh này, ghi lại để không lặp:

1. **Canh chỗ GỌI/DÙNG, không canh dòng import.** Một bài `assertIn(tên
   module, nội_dung_file)` chỉ khớp đúng dòng `import ... from '...'` —
   xoá sạch phần DÙNG module đó (nút gọi API, prop truyền xuống…) mà dòng
   import còn nguyên thì bài này vẫn xanh trong khi tính năng đã chết.
   Mọi bài "component X gọi Y" ở đây đều regex vào cú pháp GỌI THẬT (tên
   hàm kèm dấu ngoặc, hoặc thẻ component kèm thuộc tính), không phải một
   `assertIn` tên chuỗi suông.
2. **Không canh bằng nhãn tiếng Việt của nút/nhãn hiển thị.** Đổi nhãn vì
   lý do biên tập (chốt đổi chữ, chủ đầu tư yêu cầu diễn đạt khác) không
   được làm lưới đỏ — lưới phải canh KHOÁ/thuộc tính/tên hàm, không canh
   chữ hiển thị cho người dùng cuối.

`_bo_comment()` bóc chú thích TRƯỚC khi regex chạy — nếu không, một câu MÔ
TẢ luật trong docstring/chú thích (ví dụ nhắc tới `|| '—'` như một PHẢN VÍ
DỤ cần tránh) tự nó khớp lưới và tạo báo động giả. Lưới phải soi ĐÚNG DÒNG
CODE THẬT, không soi chú thích nói VỀ code.
"""

import re
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

FRONTEND_SRC = Path(frappe.get_app_path("miyano_portal")).parent / "frontend" / "src"
FORMAT_JS = FRONTEND_SRC / "format.js"
KHOI_TRUY_VET = FRONTEND_SRC / "components" / "chi-tiet" / "KhoiTruyVet.vue"
KHOI_DONG_THOI_GIAN = FRONTEND_SRC / "components" / "chi-tiet" / "KhoiDongThoiGian.vue"
CHI_TIET_YEU_CAU = FRONTEND_SRC / "views" / "ChiTietYeuCau.vue"
STYLE_CSS = FRONTEND_SRC / "style.css"


def _bo_comment(text: str) -> str:
	"""Bóc chú thích HTML (`<!-- -->`, nhiều dòng) và chú thích JS DÒNG RIÊNG
	(dòng mà sau khi bỏ khoảng trắng đầu bắt đầu bằng `//`) khỏi một file
	`.vue`/`.js`, để lưới regex chỉ soi CODE THẬT — xem docstring module.

	CỐ Ý không bóc `//` nằm CUỐI một dòng code (trailing comment): quy ước
	của app này (đã kiểm thực nghiệm ở các file bị lưới này soi) là mọi chú
	thích JS đều chiếm TRỌN một dòng riêng, không có trailing comment — bóc
	thêm trường hợp đó là một regex phức tạp hơn để xử lý một ca không xảy
	ra trong codebase này."""
	text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
	dong = [d for d in text.splitlines() if not d.strip().startswith("//")]
	return "\n".join(dong)


class TestKhoiTruyVetDienThoai(FrappeTestCase):
	"""Task 6, Step 5 — `KhoiTruyVet.vue` phải hiện số điện thoại (người yêu
	cầu LẪN người duyệt) bằng liên kết `tel:`, và KHÔNG bao giờ dùng dấu
	gạch `'—'` làm giá trị thế chỗ cho một số bị thiếu (§8: thiếu số thì
	không in gì, không ô trống, không dấu gạch)."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.raw = KHOI_TRUY_VET.read_text(encoding="utf-8")
		cls.code = _bo_comment(cls.raw)

	def test_nguoi_yeu_cau_va_nguoi_duyet_deu_hien_tel(self):
		"""Canh chỗ DÙNG — cú pháp `href="'tel:' + <khoá số điện thoại>"` cho
		ĐÚNG cả hai khoá `nguoi_yeu_cau_dien_thoai` và `nguoi_duyet_dien_
		thoai` (brief Task 6, Interfaces). Thiếu MỘT trong hai là một nửa
		khối truy vết mất nút bấm-gọi mà không ai biết."""
		self.assertRegex(
			self.code, r"href=\"'tel:'\s*\+\s*phieu\.nguoi_yeu_cau_dien_thoai\"",
			"Thiếu liên kết tel: cho số điện thoại người YÊU CẦU",
		)
		self.assertRegex(
			self.code, r"href=\"'tel:'\s*\+\s*phieu\.nguoi_duyet_dien_thoai\"",
			"Thiếu liên kết tel: cho số điện thoại người DUYỆT",
		)

	def test_khong_dung_gach_ngang_lam_gia_tri_the_cho_so_dien_thoai(self):
		"""§8 + brief ràng buộc #5 — KHÔNG `|| '—'`. Sau khi đã bóc chú thích
		(dòng chỉ MÔ TẢ luật này, xem docstring module), mọi chuỗi `'—'` còn
		lại trong CODE THẬT là một giá trị thế chỗ đang được gán."""
		self.assertNotIn("'—'", self.code)
		self.assertNotIn('"—"', self.code)

