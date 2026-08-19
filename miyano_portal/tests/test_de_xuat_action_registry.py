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

REGISTRY = (
	Path(frappe.get_app_path("miyano_portal")).parent
	/ "frontend" / "src" / "de-xuat-actions.js"
)


class TestActionRegistry(FrappeTestCase):
	def _methods_trong_registry(self) -> set[str]:
		noi_dung = REGISTRY.read_text(encoding="utf-8")
		return set(re.findall(r"method:\s*['\"]([a-z_]+)['\"]", noi_dung))

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

	def test_registry_khong_rong(self):
		"""Vế dương — thiếu nó thì một registry rỗng cũng qua bài."""
		self.assertGreaterEqual(len(self._methods_trong_registry()), 4)

	def test_file_registry_ton_tai(self):
		self.assertTrue(REGISTRY.exists(), f"Không thấy {REGISTRY}")
