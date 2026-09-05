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
from miyano_portal.api import portal as portal_api

FRONTEND_SRC = Path(frappe.get_app_path("miyano_portal")).parent / "frontend" / "src"
REGISTRY = FRONTEND_SRC / "de-xuat-actions.js"
# Task 3 (màn chi tiết GỘP) — registry THỨ HAI, riêng cho hành động của Sales
# Order (`don-actions.js`), đối chiếu với `api/portal.py` chứ không phải
# `api/de_xuat.py`. Xem class TestActionRegistry ở dưới.
REGISTRY_DON = FRONTEND_SRC / "don-actions.js"

# C4 (review tổng 19/08) — quét TOÀN BỘ `frontend/src`, không riêng `views/`.
#
# Bản trước chỉ `views/*.vue`. Task 5 thêm hai `callDeXuat('de_xuat_danh_sach',
# ...)` vào `App.vue` — nằm ở `frontend/src/`, NGOÀI vùng quét. Một tên gõ sai
# ở đó: build xanh, cả suite xanh, và mutation test kiểu cũ vẫn đỏ ở
# `DuyetList.vue` nên lưới TRÔNG như đã canh — trong khi badge "Duyệt" im lặng
# biến mất trên MỌI trang (lời gọi nằm trong một `catch` ở tầng shell). Quản lý
# thấy 0 phiếu chờ, không vào /duyet, phiếu của khoa nằm đó không ai duyệt.
#
# `.js` cũng phải quét: `cho-duyet.js` giữ đúng những lời gọi đó sau bản này.
# Quét theo THƯ MỤC GỐC + đuôi file, không theo danh sách file/thư mục — mọi
# danh sách phải nhớ cập nhật là một danh sách sẽ quên.
DUOI_QUET = ("*.vue", "*.js")

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
# Task 3, bổ sung Ruling P13 (21/08/2026) — cùng khuôn `_CALL_DE_XUAT_RE`
# nhưng cho đường gọi `api.call('...')` (module `api/portal.py`, KHÔNG phải
# `api/de_xuat.py`). `api\.call\(` không khớp `api.callDeXuat(`/`api.callKho(`
# — ký tự ngay sau "call" trong hai lời gọi đó là "D"/"K", không phải "(".
_API_CALL_RE = re.compile(r"api\.call\(\s*['\"](\w+)['\"]")

# Review Task 3 (03/09/2026) — cả hai phép đo trên `don-actions.js` (đếm
# `method:` và đếm `nhom: 'don'`) là chuỗi thô trên TOÀN VĂN file, và một
# comment tình cờ gõ liền đúng chuỗi đang đếm sẽ bị tính là mã thật. Ca xấu
# nhất KHÔNG phải đỏ giả (tốn thời gian, tự lộ) mà là XANH GIẢ: một comment
# thừa VÀ một mục thật thiếu khoá `nhom: 'don'` triệt tiêu nhau về số đếm,
# lưới báo khớp trên một registry sai — mục thiếu khoá gọi sai module và 404
# lúc người dùng bấm. Lọc bỏ dòng comment trước khi đếm/regex-tìm để hai phép
# đo chỉ còn nhìn mã thật. Chỉ dùng cho hai bài của `don-actions.js` — không
# đụng các bài cũ canh `de-xuat-actions.js` (ngoài phạm vi rà soát này).
def _bo_chu_thich(noi_dung: str) -> str:
	return "\n".join(
		dong for dong in noi_dung.splitlines() if not dong.strip().startswith("//")
	)


class TestActionRegistry(FrappeTestCase):
	def _methods_trong_registry(self) -> set[str]:
		noi_dung = REGISTRY.read_text(encoding="utf-8")
		return set(_METHOD_RE.findall(noi_dung))

	def _file_frontend(self) -> list[Path]:
		"""Mọi file nguồn frontend, ĐỆ QUY từ `frontend/src`."""
		ra: list[Path] = []
		for duoi in DUOI_QUET:
			ra += FRONTEND_SRC.rglob(duoi)
		return sorted(set(ra))

	def _methods_goi_tu_frontend(self) -> set[str]:
		"""(c) review Task 5, mở rộng ở C4 — mọi `callDeXuat('...')` viết
		thẳng trong mã nguồn (không qua registry) là CÙNG LỚP RỦI RO "404
		lúc bấm" như registry: một tên gõ sai ở đây build vẫn xanh, chỉ lộ
		ra khi người dùng thật sự bấm — hoặc KHÔNG lộ ra chút nào, nếu lời
		gọi nằm trong một `catch` best-effort như ở `App.vue`."""
		ten = set()
		for f in self._file_frontend():
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
		"""(c) review Task 5, C4 — mở rộng lưới ra khỏi de-xuat-actions.js
		VÀ ra khỏi `views/`."""
		thua = self._methods_goi_tu_frontend() - self._endpoint_that()
		self.assertEqual(
			thua, set(),
			f"Một file frontend gọi callDeXuat() với method KHÔNG tồn tại ở "
			f"api/de_xuat.py: {thua}. Đây là nút/lời gọi sẽ 404 lúc người "
			"dùng bấm.",
		)

	def test_vung_quet_phu_ngoai_thu_muc_views(self):
		"""C4 — vế DƯƠNG cho chính vùng quét.

		`test_moi_call_de_xuat_...` xanh khi KHÔNG có tên sai — kể cả khi
		vùng quét thu về đúng một file. Nó không phân biệt được "không có
		lỗi" với "không nhìn". Bài này khẳng định lưới THẬT SỰ đọc những
		file ngoài `views/` (`App.vue`, `cho-duyet.js`) — thu hẹp vùng quét
		về như cũ sẽ làm bài này đỏ ngay, thay vì đỏ sáu tháng sau trên
		máy khách."""
		duong_dan = {f.relative_to(FRONTEND_SRC).as_posix() for f in self._file_frontend()}
		self.assertIn("App.vue", duong_dan)
		self.assertIn("cho-duyet.js", duong_dan)
		self.assertIn("de-xuat-actions.js", duong_dan)
		# Task 7b (03/09/2026) — `DeXuatDetail.vue` đã nghỉ, gộp vào màn
		# `ChiTietYeuCau.vue`; đổi mốc chứng minh "quét cả views/" sang file
		# thay thế, KHÔNG xoá bài — ý nghĩa của bài (vùng quét thật sự chạm
		# tới views/) không đổi.
		self.assertIn("views/ChiTietYeuCau.vue", duong_dan)
		# Và lưới phải thật sự BẮT ĐƯỢC tên từ những file đó — không chỉ mở
		# file rồi bỏ qua nội dung.
		self.assertIn("de_xuat_danh_sach", self._methods_goi_tu_frontend())

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

	# -- Task 3, bổ sung Ruling P13 (21/08/2026) -----------------------------
	#
	# Lưới trên chỉ soi `callDeXuat('...')` (đường tới `api/de_xuat.py`).
	# `portal_catalog_gop` (Task 3) và mọi endpoint khác của `api/portal.py`
	# đi qua `api.call('...')` — MỘT ĐƯỜNG GỌI KHÁC, không được lưới đó nhìn
	# thấy (xem ghi chú tại chỗ gọi ở `LapPhieu.vue::timKiem()`). Mở rộng
	# đúng CÙNG khuôn: quét `api.call('...')`, đối chiếu với hàm whitelist
	# của `api/portal.py` (không phải `api/de_xuat.py`).

	def _methods_api_call_tu_frontend(self) -> set[str]:
		"""Mọi `api.call('...')` viết thẳng trong `frontend/src/**` (đệ quy,
		cùng `DUOI_QUET`/`_file_frontend()` ở trên). Regex `api\\.call\\(`
		KHÔNG khớp `api.callDeXuat(`/`api.callKho(` — ký tự ngay sau
		`call` phải là `(`, còn hai hàm kia có `DeXuat`/`Kho` chen giữa."""
		ten = set()
		for f in self._file_frontend():
			ten |= set(_API_CALL_RE.findall(f.read_text(encoding="utf-8")))
		return ten

	def _endpoint_that_portal(self) -> set[str]:
		return {
			ten for ten, fn in inspect.getmembers(portal_api, inspect.isfunction)
			if fn in frappe.whitelisted and fn.__module__ == portal_api.__name__
		}

	def test_moi_api_call_trong_frontend_la_endpoint_that_cua_portal(self):
		thua = self._methods_api_call_tu_frontend() - self._endpoint_that_portal()
		self.assertEqual(
			thua, set(),
			f"Một file frontend gọi api.call() với method KHÔNG tồn tại (whitelist) "
			f"ở api/portal.py: {thua}. Đây là nút/lời gọi sẽ 404 lúc người dùng bấm.",
		)

	def test_api_call_portal_catalog_gop_duoc_quet_dung(self):
		"""Vế DƯƠNG cho chính vùng quét mới — `LapPhieu.vue::timKiem()` gọi
		`api.call('portal_catalog_gop', ...)` thật (không phải qua
		`callDeXuat`); nếu lưới không thực sự đọc được nó, test trên xanh
		vì KHÔNG NHÌN THẤY GÌ, không phải vì không có lỗi."""
		self.assertIn("portal_catalog_gop", self._methods_api_call_tu_frontend())

	def test_luoi_api_call_bat_duoc_ten_bia(self):
		"""Bắt buộc có vế dương (yêu cầu điều phối, Ruling P13) — chứng
		minh lưới THẬT SỰ bắt được: một tên BỊA (giả lập lỗi gõ sai
		`api.call('...')`) phải (a) bị chính regex trích ra được, và (b)
		KHÔNG có mặt trong tập endpoint whitelist thật của `api/portal.py`
		— tức nếu tên đó từng lọt vào frontend, `test_moi_api_call_trong_
		frontend_la_endpoint_that_cua_portal` ở trên sẽ đỏ đúng cách. Thiếu
		vế này, một hàm quét luôn trả tập RỖNG cũng qua được bài trên —
		đúng lỗ hổng dự án này đã dính BA LẦN (task-3-bo-sung.md, mục 4)."""
		ten_bia = "ten_bia_khong_ton_tai_xyz"
		mau = f"await api.call('portal_me'); await api.call('{ten_bia}')"
		tim_thay = set(_API_CALL_RE.findall(mau))
		self.assertEqual(tim_thay, {"portal_me", ten_bia})
		self.assertNotIn(ten_bia, self._endpoint_that_portal())

	# 03/09/2026 (màn chi tiết GỘP) — registry THỨ HAI, cho hành động của Sales
	# Order. Lưới cũ đối chiếu `de-xuat-actions.js` với `api/de_xuat.py`; file
	# mới phải đối chiếu với `api/portal.py`. Không mở rộng lưới cũ để nó quét
	# cả hai: khi đó nó mất khả năng nói "tên này không tồn tại" — một tên sai
	# trong file này sẽ được coi là hợp lệ chỉ vì file kia có một tên trùng.
	# -- 03/09/2026, màn chi tiết GỘP: registry THỨ HAI -----------------------

	def _noi_dung_registry_don(self) -> str:
		"""Nội dung `don-actions.js` đã lọc bỏ dòng comment (`_bo_chu_thich`)
		— dùng chung cho mọi phép đo chuỗi thô bên dưới, để một comment gõ
		liền `method:`/`nhom: 'don'` không bị tính là mã thật."""
		return _bo_chu_thich(REGISTRY_DON.read_text(encoding="utf-8"))

	def _methods_registry_don(self) -> set[str]:
		return set(_METHOD_RE.findall(self._noi_dung_registry_don()))

	def test_file_registry_don_ton_tai(self):
		self.assertTrue(REGISTRY_DON.exists(), f"Không thấy {REGISTRY_DON}")

	def test_registry_don_khong_rong(self):
		"""Vế dương — thiếu nó thì một registry rỗng cũng qua bài.

		Đếm SỐ MỤC (`_METHOD_RE.findall` có lặp), không phải số tên method
		DUY NHẤT: `portal_order_accept` xuất hiện ở 2 mục (đồng ý / không
		đồng ý), nên đếm theo tập hợp cho ra 4 trên 5 mục thật — bài "không
		rỗng" mà đo nhầm sang "có đủ tên khác nhau" là đo một thứ khác tên
		nó, và đứng sát ngưỡng không còn biên an toàn."""
		self.assertGreaterEqual(len(_METHOD_RE.findall(self._noi_dung_registry_don())), 5)

	def test_moi_method_cua_registry_don_la_endpoint_that_cua_portal(self):
		"""Đối chiếu với `api/portal.py`, KHÔNG phải `api/de_xuat.py`. Đó
		là lý do đây là file registry thứ hai chứ không phải thêm mục vào
		file cũ: trộn hai họ tên vào một mảng làm lưới mất khả năng nói
		'tên này không tồn tại' — nó không biết phải hỏi module nào."""
		thua = self._methods_registry_don() - self._endpoint_that_portal()
		self.assertEqual(
			thua, set(),
			f"don-actions.js khai method KHÔNG tồn tại (whitelist) ở "
			f"api/portal.py: {thua}. Đây là nút sẽ 404 lúc người dùng bấm.",
		)

	def test_moi_muc_registry_don_deu_mang_nhom_don(self):
		"""Màn gộp nối HAI registry rồi mới render; `nhom: 'don'` là thứ
		DUY NHẤT cho nó biết gọi `api.call` thay vì `api.callDeXuat`. Một
		mục quên khoá này sẽ được gọi sai module và 404 lúc bấm.

		Đếm trên nội dung ĐÃ LỌC COMMENT (`_noi_dung_registry_don`), không
		phải toàn văn file: một comment tình cờ gõ liền `nhom: 'don'` VÀ một
		mục thật thiếu khoá đó sẽ triệt tiêu nhau về số đếm trên toàn văn —
		bài XANH trên một registry sai (mục thiếu khoá 404 lúc bấm). Đây là
		ca XANH GIẢ, nguy hiểm hơn đỏ giả vì không ai phát hiện."""
		noi_dung = self._noi_dung_registry_don()
		so_muc = len(_METHOD_RE.findall(noi_dung))
		so_nhom = noi_dung.count("nhom: 'don'")
		self.assertEqual(
			so_nhom, so_muc,
			f"{so_muc} mục nhưng chỉ {so_nhom} mục khai `nhom: 'don'`.",
		)
