# Ba màn luồng duyệt — Kế hoạch thi công

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dựng ba màn hình để luồng duyệt đã có ở backend **nhìn thấy và dùng được**: nhân viên khoa xem phiếu của khoa mình, quản lý mở hàng chờ và duyệt, cả hai xem chi tiết phiếu với hai cột SL đề xuất / SL duyệt.

**Architecture:** Ba màn Vue mỏng gọi thẳng các endpoint đã có ở `miyano_portal/api/de_xuat.py`. Mọi quyết định "nút nào hiện lúc nào" gom vào **một registry hành động** dạng dữ liệu (`de-xuat-actions.js`), theo skill `declaring-document-actions` của dự án — không rải `v-if` khắp component. Registry là **trình bày**, không phải chốt an ninh: server đã enforce đủ và đã có 1303 test canh.

**Tech Stack:** Vue 3 SPA (`frontend/`, vite, không có Vue Router lazy-load), Frappe v15.113.4, site `erptest.local`.

**Spec:** `docs/superpowers/specs/2026-08-18-phan-quyen-khoa-phong-va-duyet-don-design.md` §5, §10

**Không thuộc kế hoạch này:** màn **lập phiếu** (tìm hàng, thêm vào giỏ) — nó phụ thuộc mô hình gộp ba tầng ở spec §13, làm trước sẽ phải làm lại. Xem `docs/superpowers/plans/2026-08-19-gop-luong-dat-hang.md`.

## Global Constraints

- **Frontend KHÔNG có hạ tầng test tự động.** `frontend/package.json` chỉ có `vite`; không vitest, không jest, không một file `.spec.js` nào. **Đừng dựng hạ tầng test JS trong kế hoạch này** — đó là một quyết định riêng, không phải việc kèm theo.
- **Vì thế, ba chốt thay cho test JS, bắt buộc cả ba:**
  1. `cd frontend && yarn build` **phải chạy thành công** sau mỗi task (bắt lỗi cú pháp, import sai, biến chưa khai).
  2. **Một test PYTHON đọc file registry** và khẳng định mọi chuỗi `method:` trong đó là endpoint whitelist có thật ở `api/de_xuat.py`. Đây là lưới bắt đúng lỗi mà skill `declaring-document-actions` cảnh báo: *"nút 404 lúc bấm, không bước build nào bắt được"*.
  3. Bộ test Python hiện có **phải giữ xanh**: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal`. Nền: **1303 test**.
- **CHẠY TEST Ở TIỀN CẢNH.** Không `run_in_background`, không `&`, **không vòng chờ `pgrep`** (nó tự khớp chính dòng lệnh chứa nó → treo vĩnh viễn). Timeout công cụ 600000 ms.
- **Chỉ một tiến trình test tại một thời điểm** trên bench này.
- **Hide, don't disable.** Nút không hợp lệ thì **biến mất**, không xám. Một nút xám đặt ra câu hỏi nó không trả lời được.
- **Server là chốt duy nhất.** Registry quyết định *hiện gì*; nó **không** là ranh giới an ninh. Không bao giờ để một `when()` phía client là thứ duy nhất ngăn một chuyển trạng thái sai.
- **Sau mỗi hành động thành công: toast + tải lại phiếu.** Màn hình cũ vẫn ghi "chờ duyệt" sau khi duyệt thành công là than phiền phổ biến nhất của khuôn này.
- Nhãn, thông báo, bình luận: **tiếng Việt**, theo giọng mã hiện có.
- **Không sửa test cũ.** Nếu buộc phải, DỪNG và báo.
- Nhánh: tiếp tục trên `feat/de-xuat-mua` (đã có toàn bộ backend). Commit sau mỗi task.

---

## Quyết định đã chốt trong kế hoạch này

**QĐ-M1 — Màn chi tiết viết BESPOKE, không dựng config renderer.**
Skill `config-driven-detail-views` nói rõ: *"Dựng màn giàu nhất bằng tay trước — một cái thật — rồi mới factor. Đừng phát minh từ vựng slot trước, bạn sẽ sai."* App này có **một** màn chi tiết mới cần dựng, và đã có ba màn chi tiết bespoke đang chạy (`OrderDetail.vue` 733 dòng, `PhieuNhapDetail.vue`, `PhieuXuatDetail.vue`). Dựng một renderer cấu hình cho đúng một màn là trừu tượng non.
*Sai thì mất gì:* khi có màn chi tiết thứ tư, thứ năm, sẽ phải factor lại — đúng lúc đã biết cần slot gì.

**QĐ-M2 — Registry hành động thì CÓ làm, ngay từ màn đầu.**
Khác với renderer: phiếu đề xuất có **6 hành động trên 5 trạng thái và 2 vai trò**. Đó đúng là ca mà skill mô tả, và rải `v-if` sẽ sinh ra chính "nút luôn hiện rồi lỗi lúc bấm" mà skill cảnh báo.
*Sai thì mất gì:* một file JS ~60 dòng thừa nếu sau này chỉ còn 2 hành động.

**QĐ-M3 — `portal_me` trả thêm vai trò và khoa phòng.**
Frontend hôm nay **không có đường nào biết** người đăng nhập là Quản lý hay Nhân viên khoa — `portal_me` chỉ trả tên khách, mã số thuế, công nợ, địa chỉ. Không có nó thì không gating được menu, và mọi màn phải đoán.
*Sai thì mất gì:* thêm hai khoá vào một payload đã có; nếu thừa thì bỏ đi rẻ.

---

## File Structure

| File | Trách nhiệm |
|---|---|
| `miyano_portal/api/portal.py` *(sửa)* | `portal_me` trả thêm `vai_tro`, `khoa_phong`, `la_quan_ly` |
| `miyano_portal/tests/test_portal_me_vai_tro.py` *(mới)* | Test cho phần thêm ở trên |
| `frontend/src/api.js` *(sửa)* | Thêm `callDeXuat()` — prefix `miyano_portal.api.de_xuat.` |
| `frontend/src/de-xuat-actions.js` *(mới)* | **Registry hành động** — dữ liệu thuần, không import Vue |
| `miyano_portal/tests/test_de_xuat_action_registry.py` *(mới)* | **Lưới Python** đọc registry, khẳng định mọi `method:` là endpoint thật |
| `frontend/src/views/DeXuatList.vue` *(mới)* | `/de-xuat` — danh sách phiếu trong phạm vi người dùng |
| `frontend/src/views/DeXuatDetail.vue` *(mới)* | `/de-xuat/:ten` — chi tiết, hai cột SL, panel hành động |
| `frontend/src/views/DuyetList.vue` *(mới)* | `/duyet` — hàng chờ của quản lý, lọc theo khoa |
| `frontend/src/router.js` *(sửa)* | Ba route mới |
| `frontend/src/App.vue` *(sửa)* | Menu bên theo vai trò |

---

## Task 1: `portal_me` trả vai trò và khoa phòng

**Files:**
- Modify: `miyano_portal/api/portal.py` (hàm `portal_me`)
- Test: `miyano_portal/tests/test_portal_me_vai_tro.py` *(mới)*

**Interfaces:**
- Consumes: `portal_context.get_portal_member()`, `portal_context.la_quan_ly()`.
- Produces: `portal_me()` trả thêm ba khoá — `vai_tro` (str), `khoa_phong` (str | None), `la_quan_ly` (bool).

**Vì sao `la_quan_ly` là khoá RIÊNG, không để client tự suy từ `vai_tro`:** kế hoạch C thêm uỷ quyền tạm thời, khi đó một `Nhân viên khoa` **đang được uỷ quyền** phải nhìn thấy menu Duyệt. Client tự suy `vai_tro === 'Quản lý'` sẽ bỏ sót đúng ca đó. Docstring của `portal_context.la_quan_ly()` đã dặn nguyên văn: *"mọi nơi gọi PHẢI hỏi hàm này, KHÔNG được tự đọc `vai_tro`"*.

- [ ] **Step 1: Viết test đỏ**

```python
"""`portal_me` phải trả vai trò để frontend gating được menu.

Không có ba khoá này thì SPA không có đường nào biết người đăng nhập là
Quản lý hay Nhân viên khoa — `portal_me` hôm nay chỉ trả tên khách, mã số
thuế, công nợ, địa chỉ.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import portal
from miyano_portal.tests.fixtures_de_xuat import dung_fixture


class TestPortalMeVaiTro(FrappeTestCase):
	def setUp(self):
		self.f = dung_fixture(self)
		# ... dựng user quản lý + user nhân viên khoa như các test khác

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_quan_ly_thay_vai_tro_va_co_quyen_duyet(self):
		frappe.set_user(self.user_quan_ly)
		me = portal.portal_me()
		self.assertEqual(me["vai_tro"], "Quản lý")
		self.assertTrue(me["la_quan_ly"])
		self.assertIsNone(me["khoa_phong"])

	def test_nhan_vien_khoa_thay_dung_khoa_cua_minh(self):
		frappe.set_user(self.user_huyethoc)
		me = portal.portal_me()
		self.assertEqual(me["vai_tro"], "Nhân viên khoa")
		self.assertFalse(me["la_quan_ly"])
		self.assertEqual(me["khoa_phong"], self.f.khoa_huyethoc)

	def test_khoa_phong_KHONG_nhan_tu_client(self):
		"""Vế canh: `portal_me` không có tham số nào, mọi giá trị suy từ phiên."""
		import inspect
		sig = inspect.signature(portal.portal_me)
		self.assertEqual(len(sig.parameters), 0)
```

- [ ] **Step 2: Chạy, xác nhận đỏ đúng lý do**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --module miyano_portal.tests.test_portal_me_vai_tro
```
Kỳ vọng: **FAIL** với `KeyError: 'vai_tro'` — đỏ ở mức khẳng định, không phải `ImportError`.

- [ ] **Step 3: Sửa `portal_me`**

```python
    # Frontend cần biết vai trò để gating menu (màn Duyệt chỉ cho người có
    # quyền duyệt). `la_quan_ly` là khoá RIÊNG, không để client tự suy từ
    # `vai_tro`: kế hoạch C thêm uỷ quyền tạm thời, khi đó một Nhân viên
    # khoa ĐANG ĐƯỢC UỶ QUYỀN phải thấy menu Duyệt — client tự suy
    # `vai_tro === "Quản lý"` sẽ bỏ sót đúng ca đó.
    tv = get_portal_member()
    ...
        "vai_tro": tv.vai_tro,
        "khoa_phong": tv.khoa_phong or None,
        "la_quan_ly": la_quan_ly(),
```

- [ ] **Step 4: Chạy test module, xác nhận 3 test xanh**
- [ ] **Step 5: Chạy full suite ở TIỀN CẢNH, kỳ vọng 1306 OK**
- [ ] **Step 6: Commit** — `feat(cong): portal_me tra vai tro va khoa phong`

---

## Task 2: API client + registry hành động + lưới Python

**Files:**
- Modify: `frontend/src/api.js`
- Create: `frontend/src/de-xuat-actions.js`
- Test: `miyano_portal/tests/test_de_xuat_action_registry.py` *(mới)*

**Interfaces:**
- Produces: `callDeXuat(method, args)` trong `api.js`.
- Produces: `ACTIONS_DE_XUAT` — mảng object `{method, label, variant, when(d, me), args?}`.
- Produces: `hanhDongChoPhep(doc, me)` → mảng hành động hợp lệ.

**Đây là task quan trọng nhất về mặt chống lỗi.** Nó dựng cái lưới thay cho test JS.

- [ ] **Step 1: Viết lưới Python trước (đỏ vì chưa có file registry)**

```python
"""Mọi `method:` trong registry hành động phải là endpoint whitelist có thật.

Frontend không có test tự động (package.json chỉ có vite). Skill
`declaring-document-actions` cảnh báo đúng lỗ này: "một typo sinh ra cái nút
404 lúc bấm, và không bước build nào bắt được". Lưới này bắt nó bằng hạ tầng
Python đã có, không phải dựng hạ tầng JS mới.

Đọc file JS bằng regex CỐ Ý — không parse JS. Registry là dữ liệu phẳng, và
một parser JS trong test Python là thứ phải bảo trì mà không đổi lại được gì.
"""

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
		import inspect
		return {
			ten for ten, ham in inspect.getmembers(de_xuat_api, inspect.isfunction)
			if getattr(ham, "whitelisted", False)
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
```

- [ ] **Step 2: Chạy, xác nhận đỏ** — `AssertionError: Không thấy .../de-xuat-actions.js`

- [ ] **Step 3: Thêm `callDeXuat` vào `api.js`**

Cạnh `KHO_PREFIX` đã có:

```js
const DE_XUAT_PREFIX = '/api/method/miyano_portal.api.de_xuat.'

export async function callDeXuat(method, args) {
  return callUrl(DE_XUAT_PREFIX + method, args)
}
```
Và thêm `callDeXuat` vào object export mặc định ở cuối file (cạnh `call, callKho, ...`).

- [ ] **Step 4: Viết `de-xuat-actions.js`**

```js
// Registry hành động cho phiếu Đề xuất mua.
//
// Hành động là DỮ LIỆU: một bảng ánh xạ trạng thái + vai trò -> nút được
// phép. Rải v-if khắp component sẽ sinh ra đúng lỗi "nút luôn hiện rồi lỗi
// lúc bấm" — người dùng học cách sợ thanh công cụ.
//
// ĐÂY KHÔNG PHẢI CHỐT AN NINH. Server đã enforce đủ (1303 test canh). Registry
// chỉ quyết định HIỆN GÌ. Không bao giờ để một when() ở đây là thứ duy nhất
// ngăn một chuyển trạng thái sai.
//
// Mọi chuỗi `method` phải là endpoint whitelist có thật ở api/de_xuat.py —
// `tests/test_de_xuat_action_registry.py` canh điều đó.

export const ACTIONS_DE_XUAT = [
  { method: 'de_xuat_gui_duyet', label: 'Gửi duyệt', variant: 'primary',
    when: (d, me) => d.trang_thai === 'Nháp' && d.owner === me.user },

  { method: 'de_xuat_xoa_nhap', label: 'Xoá', variant: 'danger',
    when: (d, me) => d.trang_thai === 'Nháp' && (d.owner === me.user || me.la_quan_ly) },

  { method: 'de_xuat_duyet_phieu', label: 'Duyệt', variant: 'success',
    when: (d, me) => d.trang_thai === 'Chờ duyệt' && me.la_quan_ly },

  { method: 'de_xuat_tu_choi', label: 'Từ chối', variant: 'secondary',
    when: (d, me) => d.trang_thai === 'Chờ duyệt' && me.la_quan_ly,
    args: [{ key: 'ly_do', label: 'Lý do từ chối', type: 'textarea', required: true }] },

  { method: 'de_xuat_huy', label: 'Huỷ phiếu', variant: 'danger',
    when: (d, me) => ['Chờ duyệt', 'Từ chối'].includes(d.trang_thai) && me.la_quan_ly },

  { method: 'de_xuat_duyet_sua', label: 'Đồng ý sửa', variant: 'success',
    when: (d, me) => d.trang_thai === 'Chờ duyệt sửa' && me.la_quan_ly },

  { method: 'de_xuat_tu_choi_sua', label: 'Không đồng ý sửa', variant: 'secondary',
    when: (d, me) => d.trang_thai === 'Chờ duyệt sửa' && me.la_quan_ly,
    args: [{ key: 'ly_do', label: 'Lý do', type: 'textarea', required: true }] },
]

export function hanhDongChoPhep(doc, me) {
  if (!doc || !me) return []
  return ACTIONS_DE_XUAT.filter((a) => {
    try { return a.when(doc, me) } catch (e) { return false }
  })
}
```

**Chú ý cho người thi công:** `variant: 'danger'` chỉ dùng cho việc **không đảo ngược được** — "Xoá" (xoá thật khỏi CSDL) và "Huỷ phiếu". Đừng gắn đỏ cho "Từ chối", vì phiếu bị từ chối vẫn sửa và gửi lại được; gắn đỏ bừa thì người dùng thôi đọc màu.

- [ ] **Step 5: Chạy lưới Python, xác nhận 3 test xanh**
- [ ] **Step 6: `cd frontend && yarn build`** — phải thành công
- [ ] **Step 7: Chạy full suite TIỀN CẢNH, kỳ vọng 1309 OK**
- [ ] **Step 8: Commit** — `feat(cong): api client de_xuat + registry hanh dong + luoi python`

---

## Task 3: Màn `/de-xuat` — danh sách phiếu

**Files:**
- Create: `frontend/src/views/DeXuatList.vue`
- Modify: `frontend/src/router.js`, `frontend/src/App.vue`

**Interfaces:**
- Consumes: `callDeXuat('de_xuat_danh_sach', {trang_thai, limit})` → mảng `{name, ma_de_xuat, khoa_phong, trang_thai, thoi_diem_gui, owner}`.
- Produces: route `name: 'de-xuat'`, path `/de-xuat`.

**Nội dung màn:**
- Bộ lọc trạng thái (chip): Tất cả / Nháp / Chờ duyệt / Đã duyệt / Từ chối / Đã huỷ.
- Mỗi dòng: **mã phiếu** (đậm, là thứ người dùng gọi tên), khoa phòng, trạng thái (badge), thời điểm gửi.
- Phiếu **Nháp chưa có mã** → hiện `(chưa gửi duyệt)` thay vì ô trống. Ô trống trông như dữ liệu hỏng.
- Rỗng → *"Khoa chưa có phiếu đề xuất nào."* Không để màn trắng.

**Theo skill `showing-names-not-codes`:** tên hàng/khoa hiện dạng tên người đọc được; mã phiếu là **định danh người dùng thật sự gọi tên nhau**, nên nó đứng đầu dòng chứ không bị giấu.

- [ ] **Step 1: Viết view + thêm route**

Route (`router.js`, cạnh `/orders`):
```js
import DeXuatList from './views/DeXuatList.vue'
...
{ path: '/de-xuat', name: 'de-xuat', component: DeXuatList, meta: { title: 'Đề xuất mua' } },
```

- [ ] **Step 2 (Ruling P1 — KHÔNG nối link sang màn chi tiết ở task này; route đó do Task 4 tạo, nối trước là link chết): Thêm mục menu trong `App.vue`** — hiện cho **mọi** vai trò (nhân viên xem phiếu khoa mình, quản lý xem toàn viện). Bám đúng khuôn `router-link` đang dùng cho `/orders`.

- [ ] **Step 3: `cd frontend && yarn build`** — phải thành công

- [ ] **Step 4: Kiểm bằng mắt trên site thật.** Mở `http://erptest.local:8002/portal/de-xuat` bằng tài khoản quản lý. Kỳ vọng: màn tải được, không lỗi console, danh sách rỗng hiện đúng câu tiếng Việt (chưa có phiếu nào trên site test).

- [ ] **Step 5: Chạy full suite TIỀN CẢNH** — phải vẫn **1309 OK** (task này không đụng Python; nếu số đổi thì có gì sai)
- [ ] **Step 6: Commit** — `feat(cong): man /de-xuat danh sach phieu`

---

## Task 4: Màn `/de-xuat/:ten` — chi tiết phiếu

**Files:**
- Create: `frontend/src/views/DeXuatDetail.vue`
- Modify: `frontend/src/router.js`

**Interfaces:**
- Consumes: `callDeXuat('de_xuat_chi_tiet', {ten})` → `doc.as_dict()` của phiếu (đã lọc `so_luong_xin_sua` âm thành `null`).
- Consumes: `hanhDongChoPhep(doc, me)` từ Task 2.
- Consumes: `call('portal_me')` cho `me` (có `la_quan_ly`, `user`).
- Produces: route `name: 'de-xuat-detail'`, path `/de-xuat/:ten`.

**Đây là màn giàu nhất của kế hoạch — dựng BESPOKE (QĐ-M1), không dựng renderer cấu hình.**

**Bố cục, theo khuôn `OrderDetail.vue` đang chạy:**

*Đầu phiếu:* mã phiếu (lớn) + badge trạng thái; khoa phòng; **khối truy vết** — người yêu cầu, thời điểm gửi, lý do yêu cầu. Ba thứ này hiện **ngay đầu**, không phải đi tìm trong lịch sử (§5.2).

*Bảng dòng hàng — ba cột số, đây là điểm cốt lõi của màn:*

| Mặt hàng | SL đề xuất | SL duyệt | SL xin sửa |
|---|---|---|---|

- **SL đề xuất khoá vĩnh viễn** từ lúc gửi — hiện chỉ đọc, có chú thích khi rê chuột.
- Dòng bị **hạ về 0** → gạch ngang cả dòng, badge *"Không duyệt"*. **Không ẩn dòng** — giữ nguyên là cách hệ thống trả lời "khoa xin gì / duyệt gì".
- Dòng **quản lý thêm** (`nguon_dong === 'Quản lý thêm'`) → badge *"Quản lý thêm"*.
- Cột **SL xin sửa** chỉ hiện khi phiếu ở `Chờ duyệt sửa`, và chỉ ở dòng có giá trị (backend đã đổi mốc "chưa có yêu cầu" thành `null`).

*Panel hành động:* render từ `hanhDongChoPhep(doc, me)`. Hành động có `args` → mở modal, kiểm `required`, rồi gọi.

*Sau mỗi hành động thành công:* toast + **tải lại phiếu**. Màn cũ vẫn ghi "Chờ duyệt" sau khi duyệt xong là than phiền phổ biến nhất của khuôn này.

*Lỗi từ server:* hiện **thông điệp tiếng Việt** mà backend trả về — chúng đã được viết để người dùng đọc (ví dụ *"Báo giá cho đơn … đã hết hiệu lực ngày …"*). `api.js` đã bóc phần tên lớp lỗi sẵn.

*Nếu phiếu đã sinh đơn:* hiện dòng **"Đơn hàng: SAL-ORD-…"** có link sang `/orders/:name`, và nếu có `custom_ma_tra_cuu` thì hiện mã đó **trước**, mã hệ thống sau — đúng QĐ-A4 (khách thấy mã của họ).

- [ ] **Step 1: Viết view + route**
```js
{ path: '/de-xuat/:ten', name: 'de-xuat-detail', component: DeXuatDetail, meta: { title: 'Chi tiết đề xuất' } },
```
- [ ] **Step 2: Nối dòng ở `/de-xuat` sang màn này** (`router-link` theo `name`)
- [ ] **Step 3: `cd frontend && yarn build`** — phải thành công
- [ ] **Step 4: Kiểm bằng mắt** — cần một phiếu thật. Dựng bằng `bench --site erptest.local console` hoặc gọi API: tạo nháp → thêm dòng → gửi duyệt. Rồi mở màn, xác nhận: khối truy vết hiện đủ ba thứ; ba cột số đúng; panel hành động hiện **đúng** nút theo vai trò (quản lý thấy Duyệt/Từ chối/Huỷ; nhân viên không thấy cái nào ở trạng thái Chờ duyệt).
- [ ] **Step 5: Chạy full suite TIỀN CẢNH** — vẫn 1309 OK
- [ ] **Step 6: Commit** — `feat(cong): man chi tiet phieu de xuat`

---

## Task 5: Màn `/duyet` — hàng chờ của quản lý

**Files:**
- Create: `frontend/src/views/DuyetList.vue`
- Modify: `frontend/src/router.js`, `frontend/src/App.vue`

**Interfaces:**
- Consumes: `callDeXuat('de_xuat_danh_sach', {trang_thai: 'Chờ duyệt'})`.
- Consumes: `call('portal_me')` → `la_quan_ly`.
- Produces: route `name: 'duyet'`, path `/duyet`.

**Nội dung:**
- **Lọc theo khoa phòng** — đây là yêu cầu gốc của chủ đầu tư: *"quản lý sẽ filter theo khoa … cốt lõi là để quản lý biết được khoa nào đang mua cái gì mà để duyệt"*. Dropdown khoa, lấy danh sách khoa từ phiếu đang hiện (không cần endpoint mới).
- **Badge số phiếu chờ** trên mục menu.
- Gộp cả `Chờ duyệt` và `Chờ duyệt sửa` — hai thứ đều là việc đang chờ quản lý. Phiếu xin sửa có badge riêng để phân biệt.
- Mỗi dòng bấm được → sang `/de-xuat/:ten`.
- Rỗng → *"Không có phiếu nào chờ duyệt."*

**Chưa làm trong kế hoạch này:** ô tìm theo tên/mã vật tư (§6.3) — nó cần endpoint `de_xuat_mua_tim` **chưa tồn tại**. Ghi vào "Sau kế hoạch này".

**Menu gating:** mục Duyệt chỉ hiện khi `me.la_quan_ly` — **dùng khoá đó**, không tự suy từ `vai_tro` (xem lý do ở Task 1).

- [ ] **Step 1: Viết view + route + mục menu có điều kiện**
- [ ] **Step 2: `cd frontend && yarn build`** — phải thành công
- [ ] **Step 3: Kiểm bằng mắt bằng CẢ HAI tài khoản.** Quản lý: thấy mục Duyệt, thấy phiếu chờ, lọc khoa chạy. Nhân viên khoa: **không** thấy mục Duyệt. Đây là vế âm — kiểm bằng mắt vẫn phải có đủ hai vế.
- [ ] **Step 4: Chạy full suite TIỀN CẢNH** — vẫn 1309 OK
- [ ] **Step 5: Commit** — `feat(cong): man /duyet hang cho cua quan ly`

---

## Nghiệm thu cuối kế hoạch

- [ ] `cd frontend && yarn build` thành công, không cảnh báo mới.
- [ ] `bench --site erptest.local run-tests --app miyano_portal` — **1309 OK**, chạy hai lần liên tiếp.
- [ ] **Đi hết một vòng thật trên `erptest.local`**: nhân viên khoa lập nháp → gửi duyệt → quản lý mở `/duyet` → lọc khoa → mở chi tiết → sửa số lượng duyệt → bấm Duyệt → đơn hàng sinh ra → mở `/orders` thấy đơn đó mang đúng khoa.
- [ ] Cập nhật `docs/HDSD-phan-quyen-khoa-phong.md` §4 — thêm phần "Thao tác trên màn hình", và chạy lại `python3 docs/md2docx.py docs/HDSD-phan-quyen-khoa-phong.md`.

---

## Sau kế hoạch này

**Ô tìm theo mã / tên vật tư (§6.3)** — cần endpoint `de_xuat_mua_tim(tu_khoa, khoa_phong, gom_da_xu_ly)` chưa tồn tại. Nó phải khớp cả **dòng đặt ngoài**; bỏ sót thì một phiếu toàn hàng chưa có mã sẽ **vô hình** trước ô tìm kiếm — đúng loại phiếu quản lý cần xem kỹ nhất. §6.1 lấy chính ô tìm kiếm này làm lý do biện minh cho việc mã theo khoa thay vì theo nhóm sản phẩm, nên **đừng đọc §6.1 là đã thoả**.

**Màn lập phiếu** — thuộc `docs/superpowers/plans/2026-08-19-gop-luong-dat-hang.md`.

**Màn `/thanh-vien`** (quản lý gán khoa, bật/tắt thành viên, lập uỷ quyền) — bước 9, chưa có kế hoạch.

**Sau khi mô hình gộp ba tầng xong**, ba màn của kế hoạch này cần **thêm một cột trạng thái giá** trên bảng dòng hàng (có giá hợp đồng / chờ báo giá). Đó là **bổ sung, không phải viết lại** — đó cũng là lý do làm ba màn này trước là an toàn.
