"""Mọi `method:` trong registry hành động phải là endpoint whitelist có thật.

Frontend không có test tự động (package.json chỉ có vite). Skill
`declaring-document-actions` cảnh báo đúng lỗ này: "một typo sinh ra cái nút
404 lúc bấm, và không bước build nào bắt được". Lưới này bắt nó bằng hạ tầng
Python đã có, không phải dựng hạ tầng JS mới.

Đọc file JS bằng regex CỐ Ý — không parse JS. Registry là dữ liệu phẳng, và
một parser JS trong test Python là thứ phải bảo trì mà không đổi lại được gì.

CHÚ Ý cơ chế `frappe.whitelist()`: bản Frappe của site này KHÔNG gắn thuộc
tính `.whitelisted` lên hàm (khác giả định ngây thơ) — nó chỉ ghi hàm gốc
vào danh sách toàn cục `frappe.whitelisted`. `test_pham_vi_endpoint.py` đã
xác nhận điều này thực nghiệm; soát bằng `fn in frappe.whitelisted` thay vì
`getattr(fn, "whitelisted", ...)` để đo đúng cơ chế THẬT, không phải cơ chế
giả định (cái sau sẽ trả tập rỗng và làm lưới đỏ giả cho MỌI registry, kể
cả registry đúng).
"""

import inspect
import re
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import de_xuat as de_xuat_api

FRONTEND_SRC = Path(frappe.get_app_path("miyano_portal")).parent / "frontend" / "src"
REGISTRY = FRONTEND_SRC / "de-xuat-actions.js"
VIEWS_DIR = FRONTEND_SRC / "views"

# (a) review Task 5 — `[a-z_]+` bỏ sót method có chữ số (vd. một tên tương
# lai kiểu `de_xuat_buoc_2`): nó không khớp regex ở CẢ HAI vế (registry lẫn
# endpoint thật), nên không bao giờ bị tính là "thừa" — lưới canh hụt mà vẫn
# xanh. `\w+` khớp chữ số lẫn gạch dưới, đúng bộ ký tự hợp lệ của một tên
# hàm Python.
_METHOD_RE = re.compile(r"method:\s*['\"](\w+)['\"]")
# (c) review Task 5 — cùng bộ ký tự, dùng để quét `callDeXuat('...')` viết
# thẳng trong .vue (không đi qua registry). Chỉ bắt được LỜI GỌI TÊN HẰNG
# (chuỗi literal); `callDeXuat(action.method, ...)` — tên động lấy từ chính
# registry — không khớp, và không cần khớp: registry đã tự canh nó rồi.
_CALL_DE_XUAT_RE = re.compile(r"callDeXuat\(\s*['\"](\w+)['\"]")


class TestActionRegistry(FrappeTestCase):
	def _methods_trong_registry(self) -> set[str]:
		noi_dung = REGISTRY.read_text(encoding="utf-8")
		return set(_METHOD_RE.findall(noi_dung))

	def _methods_goi_tu_vue(self) -> set[str]:
		"""(c) review Task 5 — mọi `callDeXuat('...')` viết thẳng trong
		component (không qua registry) là CÙNG LỚP RỦI RO "404 lúc bấm"
		như registry: một tên gõ sai ở đây build vẫn xanh, chỉ lộ ra khi
		người dùng thật sự bấm."""
		ten = set()
		for f in sorted(VIEWS_DIR.glob("*.vue")):
			ten |= set(_CALL_DE_XUAT_RE.findall(f.read_text(encoding="utf-8")))
		return ten

	def _endpoint_that(self) -> set[str]:
		return {
			ten for ten, fn in inspect.getmembers(de_xuat_api, inspect.isfunction)
			if fn in frappe.whitelisted and fn.__module__ == de_xuat_api.__name__
		}

	def test_moi_method_trong_registry_la_endpoint_that(self):
		thua = self._methods_trong_registry() - self._endpoint_that()
		self.assertEqual(
			thua, set(),
			f"Registry trỏ tới method KHÔNG tồn tại ở api/de_xuat.py: {thua}. "
			"Đây là nút sẽ 404 lúc người dùng bấm.",
		)

	def test_moi_call_de_xuat_trong_vue_la_endpoint_that(self):
		"""(c) review Task 5 — mở rộng lưới ra khỏi de-xuat-actions.js."""
		thua = self._methods_goi_tu_vue() - self._endpoint_that()
		self.assertEqual(
			thua, set(),
			f"Một view .vue gọi callDeXuat() với method KHÔNG tồn tại ở "
			f"api/de_xuat.py: {thua}. Đây là nút/lời gọi sẽ 404 lúc người "
			"dùng bấm.",
		)

	def test_ham_private_khong_lot_vao_endpoint_that(self):
		"""(b) review Task 5 — nửa `frappe.whitelisted` của bộ lọc trước đây
		chỉ được chứng minh cho vế "tên không tồn tại". Chưa ai chứng minh
		lưới bắt được một registry trỏ vào một hàm PRIVATE CÓ THẬT
		(`_phieu_cua_toi`, `_ap_dieu_chinh`) — bấm nút đó cũng lỗi (không
		whitelist), cùng lớp lỗi "404/403 lúc bấm" mà lưới này tồn tại để
		canh. `_endpoint_that()` phải loại chúng ra vì `fn in frappe.
		whitelisted` chỉ đúng cho hàm có `@frappe.whitelist()`."""
		endpoint = self._endpoint_that()
		self.assertNotIn("_phieu_cua_toi", endpoint)
		self.assertNotIn("_ap_dieu_chinh", endpoint)

	def test_registry_khong_rong(self):
		"""Vế dương — thiếu nó thì một registry rỗng cũng qua bài."""
		self.assertGreaterEqual(len(self._methods_trong_registry()), 4)

	def test_file_registry_ton_tai(self):
		self.assertTrue(REGISTRY.exists(), f"Không thấy {REGISTRY}")
