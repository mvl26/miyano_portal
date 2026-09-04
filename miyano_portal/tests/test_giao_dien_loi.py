"""Lỗi máy chủ không bao giờ được đổ HTML thô ra trước mặt người dùng.

Lượt chạy thử toàn tuyến 04/09/2026 ghi nhận một toast hiện nguyên văn
`<details><summary>Bạn không được phép truy cập chức năng này...` — thẻ HTML
chưa lọc, kèm thuật ngữ máy móc. Người đọc là điều dưỡng và quản lý bệnh
viện, không phải lập trình viên.

`frontend/src/api.js` nay có một cặp hàm làm việc đó: `_trichLoiTuResponse()`
móc thông điệp ra khỏi phản hồi, `_dichLoiMayChu()` lọc thẻ và dịch những lỗi
không đọc được thành một câu tiếng Việt. Có một bộ test JS chạy bằng
`node --test` (`frontend/src/api.dich-loi.test.mjs`, gọi bằng `yarn test`) đo
phép biến đổi chuỗi đó.

VÌ SAO VẪN CẦN LƯỚI PYTHON NÀY: bộ test JS kia KHÔNG chạy trong suite của
app — `bench run-tests` không biết `node --test`. Một bộ test không có ai gọi
là một bộ test sẽ mục đi trong im lặng, và cả kho này đã trả giá nhiều lần cho
đúng dạng "trông như lưới nhưng không canh gì". Suite Python là cửa thật, nên
bất biến KIẾN TRÚC phải có một bài ở đây.

Bài này KHÔNG đo phép biến đổi chuỗi (test JS làm việc đó rồi). Nó đo thứ test
JS không thể thấy: **mọi nơi móc thông điệp lỗi ra khỏi phản hồi đều phải đưa
nó qua bộ lọc trước khi ném lên giao diện.** Thêm một lời gọi mạng thứ năm mà
quên bước lọc là đúng cách lỗi cũ quay lại.
"""

import re
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase


def _doc_api_js() -> str:
	return (
		Path(frappe.get_app_path("miyano_portal")).parent / "frontend" / "src" / "api.js"
	).read_text(encoding="utf-8")


class TestLoiKhongDoHtmlThoRaManHinh(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.ma = _doc_api_js()

	def test_moi_lan_trich_loi_deu_di_qua_bo_loc(self):
		"""Số lần DÙNG `_trichLoiTuResponse` phải bằng số lần DÙNG `_dichLoiMayChu`.

		Đếm lần DÙNG, không đếm dòng khai báo — `export function` bị loại ra.

		Lệch số nghĩa là có một chỗ móc được thông điệp của máy chủ rồi ném
		thẳng lên giao diện: đúng đường mà `<details><summary>...` đã đi ra
		trước mặt người dùng.
		"""
		def dem_dung(ten: str) -> int:
			return len(
				[
					d
					for d in self.ma.splitlines()
					if ten in d and not re.search(rf"export\s+function\s+{ten}\b", d)
				]
			)

		so_trich = dem_dung("_trichLoiTuResponse")
		so_dich = dem_dung("_dichLoiMayChu")
		self.assertGreater(so_trich, 0, "Không tìm thấy lời gọi `_trichLoiTuResponse` nào")
		self.assertEqual(
			so_trich,
			so_dich,
			f"Có {so_trich} chỗ móc thông điệp lỗi ra nhưng chỉ {so_dich} chỗ đưa nó "
			"qua bộ lọc. Chỗ còn lại đang ném thẳng thông điệp máy chủ (có thể kèm "
			"thẻ HTML) lên giao diện của bệnh viện.",
		)

	def test_bo_loc_that_su_lot_the_html(self):
		"""`_dichLoiMayChu` phải gọi `_lotTheHtml`, không chỉ dịch câu chữ.

		Không có phép lột đó thì hàm vẫn chạy, vẫn trả về một chuỗi, mọi bài
		test dịch-câu-chữ vẫn xanh — và thẻ `<details>` vẫn đi thẳng ra màn.
		"""
		than = self.ma.split("export function _dichLoiMayChu", 1)
		self.assertEqual(len(than), 2, "Không tìm thấy hàm `_dichLoiMayChu`")
		# Cắt tới hàm export kế tiếp để chỉ soi trong thân hàm này.
		than_ham = re.split(r"\nexport ", than[1], maxsplit=1)[0]
		self.assertIn(
			"_lotTheHtml",
			than_ham,
			"`_dichLoiMayChu` không gọi `_lotTheHtml` — thông điệp máy chủ sẽ ra "
			"màn hình kèm nguyên thẻ HTML.",
		)
