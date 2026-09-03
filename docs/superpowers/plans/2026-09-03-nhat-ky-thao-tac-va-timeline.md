# Nhật ký thao tác và dòng thời gian đơn hàng — Kế hoạch thi công

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Màn chi tiết đơn trả lời được "ai đã làm gì, lúc nào" — gồm cả tên và số điện thoại nhân sự Miyano — bằng một sổ nhật ký chỉ-thêm ghi ngay lúc việc xảy ra.

**Architecture:** Một doctype chỉ-thêm `Portal Nhat Ky Yeu Cau`, ghi qua đúng một hàm `nhat_ky.ghi()` được gọi tại những chỗ hiện đang bắn thông báo. Một endpoint đọc tự hỏi đúng chốt phạm vi sẵn có. Frontend dựng lại `.vtl`/`.vst` đã có trong `style.css`, không thêm lớp CSS bố cục nào.

**Tech Stack:** Frappe/ERPNext (Python 3.11), Vue 3 `<script setup>` + Vite 6, test bằng `bench run-tests`.

**Spec:** `docs/superpowers/specs/2026-09-03-nhat-ky-thao-tac-va-timeline-design.md` — đọc trước, kế hoạch này lập luận từ nó.

## Global Constraints

- **Nhật ký KHÔNG BAO GIỜ ném lỗi ra ngoài.** Một trục trặc ở khâu ghi không được cuốn theo một chuyển trạng thái đã thành công. Nhưng cũng **không rơi im lặng**: `try/except` + `frappe.log_error`, đúng khuôn các hàm `bao_*` ở `portal_thong_bao_khach.py`.
- **Ghi trong CÙNG giao dịch với chuyển trạng thái** — chuyển trạng thái bị rollback thì dòng nhật ký biến mất theo. Không `frappe.db.commit()` trong đường ghi.
- **Chỉ-thêm**: không sửa, không xoá, kể cả từ Desk.
- **`su_kien` lưu KHOÁ nội bộ**, nhãn tiếng Việt sống ở `frontend/src/format.js` (Ruling P54).
- **`vai = miyano` → chỉ tên và số, KHÔNG BAO GIỜ email.**
- **Thiếu số điện thoại → không in gì**, không dấu gạch, không ô trống.
- Endpoint mới phải khai trong `tests/test_pham_vi_endpoint.py::DA_AP_PHAM_VI`.
- Thụt lề: `api/portal.py` **4 dấu cách**; `api/de_xuat.py`, doctype, phần lớn file test dùng **tab** (`test_thong_bao_endpoint.py` là ngoại lệ dùng dấu cách — kiểm từng file trước khi sửa); `.vue`/`.js` **2 dấu cách**.
- Chú thích tiếng Việt, nêu **LÝ DO**, không mô tả lại code.
- **Test phải ĐỎ ĐƯỢC.** Repo tự ghi nhận tám lần dính "test trông như phủ mà chẳng kiểm gì"; phiên 03/09 bắt thêm chín bài. Mỗi bài mới: sau khi xanh, tự dựng lại bug, xác nhận ĐỎ, hoàn nguyên, dán cả hai đầu ra.
- **Số dòng trong kế hoạch là chỉ dấu, mốc nội dung mới là thẩm quyền** — cây làm việc dịch chuyển sau mỗi commit.
- Suite đầy đủ: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal` (~6 phút). Build: `cd frontend && yarn build`, `git add` cả `miyano_portal/public/frontend`.
- Soi mắt: cầu nối `http://127.0.0.1:8777/portal/login` **không còn chạy** (đã tắt cuối phiên trước). Task nào cần soi mắt phải tự dựng lại: `bench --site erptest.local serve --port 8779` rồi trỏ Host header, hoặc thêm entry `/etc/hosts` nếu có quyền. Ghi rõ trong báo cáo nếu không dựng được.

---

## Cấu trúc file

**Tạo mới**

| File | Trách nhiệm |
|---|---|
| `miyano_portal/miyano_portal/doctype/portal_nhat_ky_yeu_cau/*` | Doctype chỉ-thêm (json + py + `__init__.py`) |
| `miyano_portal/nhat_ky.py` | **Đúng một** hàm ghi, các hằng khoá sự kiện và vai |
| `miyano_portal/tests/test_nhat_ky.py` | Luật chỉ-thêm, không-ném-lỗi, ghi đúng trường |
| `miyano_portal/tests/test_nhat_ky_su_kien.py` | Mỗi sự kiện một bài, đi qua đường mã thật |
| `frontend/src/components/chi-tiet/KhoiDongThoiGian.vue` | Dòng thời gian |

**Sửa**

| File | Việc |
|---|---|
| `miyano_portal/miyano_portal/doctype/portal_de_xuat_mua/portal_de_xuat_mua.py` | Ghi 8 sự kiện của phiếu |
| `miyano_portal/api/portal.py` | Ghi 4 sự kiện của khách + endpoint đọc + số điện thoại vào `portal_order_track` |
| `miyano_portal/api/de_xuat.py` | Số điện thoại vào `de_xuat_chi_tiet` |
| `miyano_portal/de_xuat_duyet.py` | Sự kiện `don_tao` (đường duyệt) |
| `miyano_portal/portal_context.py` | `lien_he_nguoi_dung()` |
| `miyano_portal/hooks.py` | Móc `Sales Order.on_update` và `Sales Invoice.on_submit` vào nhật ký |
| `miyano_portal/kho/delivery_hook.py` | Sự kiện `giao_hang` |
| `frontend/src/format.js` | Nhãn + màu chấm cho 18 khoá sự kiện |
| `frontend/src/components/chi-tiet/KhoiTruyVet.vue` | Thêm số điện thoại |
| `frontend/src/views/ChiTietYeuCau.vue` | Lắp khối dòng thời gian |
| `frontend/src/style.css` | Bỏ giới hạn "chỉ mobile" của `.vtl`/`.vst`, thêm màu chấm theo vai |
| `miyano_portal/tests/test_pham_vi_endpoint.py` | Khai endpoint mới |
| `docs/BAN-DO-CHUC-NANG.md`, `docs/HDSD-*.md` | Cập nhật |

---

## Task 1: Doctype chỉ-thêm và hàm ghi

**Files:**
- Create: `miyano_portal/miyano_portal/doctype/portal_nhat_ky_yeu_cau/portal_nhat_ky_yeu_cau.json`, `…/portal_nhat_ky_yeu_cau.py`, `…/__init__.py`
- Create: `miyano_portal/nhat_ky.py`
- Test: `miyano_portal/tests/test_nhat_ky.py`

**Interfaces:**
- Produces:
  - `nhat_ky.ghi(su_kien, *, customer, vai, khoa_phong=None, de_xuat=None, sales_order=None, nguoi_thao_tac=None, ghi_chu=None, thoi_diem=None) -> str | None` — trả `name` của dòng vừa ghi, hoặc `None` khi ghi hỏng. **Không bao giờ ném lỗi.**
  - Hằng vai: `VAI_KHOA = "khoa"`, `VAI_QUAN_LY = "quan_ly"`, `VAI_MIYANO = "miyano"`, `VAI_HE_THONG = "he_thong"`.
  - Hằng khoá sự kiện: `SK_KHOA_GUI_DUYET`, `SK_KHOA_THU_HOI`, `SK_QUAN_LY_DUYET`, `SK_QUAN_LY_TU_CHOI`, `SK_QUAN_LY_HUY_PHIEU`, `SK_KHOA_XIN_SUA`, `SK_QUAN_LY_DUYET_SUA`, `SK_QUAN_LY_TU_CHOI_SUA`, `SK_DON_TAO`, `SK_MIYANO_XAC_NHAN`, `SK_MIYANO_BAO_GIA`, `SK_MIYANO_TU_CHOI`, `SK_KHACH_DONG_Y`, `SK_KHACH_KHONG_DONG_Y`, `SK_KHACH_GUI_LAI_BAO_GIA`, `SK_KHACH_HUY_DON`, `SK_GIAO_HANG`, `SK_HOA_DON` — giá trị đúng bằng khoá ở §6 của spec.

- [ ] **Step 1: Viết test đỏ**

Tạo `miyano_portal/tests/test_nhat_ky.py`:

```python
"""Sổ nhật ký thao tác — luật CHỈ-THÊM và luật KHÔNG-NÉM-LỖI.

Một bản ghi ở đây là một câu khẳng định về QUÁ KHỨ. Sửa nó là nói dối về
quá khứ, nên doctype chặn cả sửa lẫn xoá — kể cả từ Desk của nhân sự
Miyano, kể cả `ignore_permissions`.

Luật thứ hai quan trọng ngang: ghi nhật ký KHÔNG ĐƯỢC ném lỗi ra ngoài.
Nó được gọi ngay sau những chuyển trạng thái đã thành công (`gui_duyet`,
`duyet`, hook giao hàng…); một trục trặc ở khâu ghi mà cuốn theo cả
transaction sẽ làm mất đúng thứ vừa làm được. Cùng ràng buộc tuyệt đối mà
`portal_thong_bao_khach.bao_*` đang chịu.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import nhat_ky
from miyano_portal.tests.fixtures_de_xuat import dung_fixture


class TestNhatKyChiThem(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.khoa_a = f.khoa_huyethoc

	def _ghi(self, **kw):
		return nhat_ky.ghi(
			nhat_ky.SK_KHOA_GUI_DUYET,
			customer=self.kh_a, khoa_phong=self.khoa_a,
			de_xuat=self._phieu(), vai=nhat_ky.VAI_KHOA,
			**kw,
		)

	def _phieu(self):
		if not getattr(self, "_ten_phieu", None):
			doc = frappe.get_doc({
				"doctype": "Portal De Xuat Mua",
				"customer": self.kh_a, "khoa_phong": self.khoa_a,
				"items": [{"item_code": dung_fixture(self).item, "so_luong_de_xuat": 1}],
			}).insert(ignore_permissions=True)
			self._ten_phieu = doc.name
		return self._ten_phieu

	def test_ghi_duoc_mot_dong(self):
		ten = self._ghi(ghi_chu="Hết găng tay")
		self.assertTrue(ten)
		d = frappe.get_doc(nhat_ky.DOCTYPE, ten)
		self.assertEqual(d.su_kien, nhat_ky.SK_KHOA_GUI_DUYET)
		self.assertEqual(d.vai, nhat_ky.VAI_KHOA)
		self.assertEqual(d.customer, self.kh_a)
		self.assertTrue(d.thoi_diem)

	def test_nguoi_thao_tac_mac_dinh_la_phien_dang_goi(self):
		"""Người thao tác là NGƯỜI ĐANG GỌI tại khoảnh khắc đó — không phải
		thứ người gọi phải nhớ truyền vào. Bắt mỗi chỗ gọi tự truyền là tạo
		ra một chỗ để quên, và quên ở đây nghĩa là một dòng nhật ký không
		có ai."""
		ten = self._ghi()
		self.assertEqual(
			frappe.db.get_value(nhat_ky.DOCTYPE, ten, "nguoi_thao_tac"),
			frappe.session.user,
		)

	def test_vai_he_thong_khong_gan_nguoi(self):
		"""VẾ ÂM của bài trên. `don_tao` là việc của HỆ THỐNG — gán tên
		người đang chạy vào đó là vu cho họ một thao tác họ không làm."""
		ten = nhat_ky.ghi(
			nhat_ky.SK_DON_TAO, customer=self.kh_a,
			de_xuat=self._phieu(), vai=nhat_ky.VAI_HE_THONG,
		)
		self.assertFalse(
			frappe.db.get_value(nhat_ky.DOCTYPE, ten, "nguoi_thao_tac")
		)

	def test_khong_sua_duoc_dong_da_ghi(self):
		ten = self._ghi()
		d = frappe.get_doc(nhat_ky.DOCTYPE, ten)
		d.ghi_chu = "sửa lại"
		with self.assertRaises(frappe.ValidationError) as ctx:
			d.save(ignore_permissions=True)
		self.assertIn("chỉ ghi thêm", str(ctx.exception))

	def test_khong_xoa_duoc_dong_da_ghi(self):
		ten = self._ghi()
		with self.assertRaises(frappe.ValidationError) as ctx:
			frappe.delete_doc(nhat_ky.DOCTYPE, ten, force=True, ignore_permissions=True)
		self.assertIn("không xoá được", str(ctx.exception))

	def test_phai_gan_vao_mot_chung_tu(self):
		"""Một dòng nhật ký không gắn vào phiếu lẫn đơn là một dòng không ai
		đọc tới được."""
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc({
				"doctype": nhat_ky.DOCTYPE, "customer": self.kh_a,
				"su_kien": nhat_ky.SK_DON_TAO, "vai": nhat_ky.VAI_HE_THONG,
				"thoi_diem": frappe.utils.now_datetime(),
			}).insert(ignore_permissions=True)

	def test_ghi_hong_KHONG_nem_loi_ra_ngoai(self):
		"""Ràng buộc tuyệt đối. Hàm này chạy ngay sau những chuyển trạng
		thái ĐÃ THÀNH CÔNG; ném lỗi ở đây là cuốn theo cả transaction và
		làm mất đúng thứ vừa làm được."""
		ten = nhat_ky.ghi(
			nhat_ky.SK_KHOA_GUI_DUYET, customer="_KHACH_KHONG_TON_TAI_",
			de_xuat=self._phieu(), vai=nhat_ky.VAI_KHOA,
		)
		self.assertIsNone(ten)
```

- [ ] **Step 2: Chạy cho ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests \
  --app miyano_portal --module miyano_portal.tests.test_nhat_ky
```
Kỳ vọng: FAIL — `ModuleNotFoundError: miyano_portal.nhat_ky`.

- [ ] **Step 3: Dựng doctype**

`…/portal_nhat_ky_yeu_cau/__init__.py`: file rỗng.

`…/portal_nhat_ky_yeu_cau.json` — theo đúng khuôn `customer_department.json` (khoá `module: "Miyano Portal"`, `engine: "InnoDB"`, `sort_field: "modified"`). Trường theo §5 của spec; `search_index: 1` cho `customer`, `khoa_phong`, `de_xuat`, `sales_order` (bốn cột đều là cột lọc). `track_changes: 0` — sổ đã là chỉ-thêm, bật thêm một lớp lịch sử cho một thứ không đổi được là phí. Quyền: `System Manager` read/report (KHÔNG create/write/delete — sổ chỉ ghi bằng mã), `Sales Manager`/`Sales User` read/report. **Zero DocPerm cho role `Customer`**, đúng quy ước bốn doctype cổng khác.

`…/portal_nhat_ky_yeu_cau.py`:

```python
"""Sổ nhật ký thao tác — CHỈ THÊM.

Một bản ghi ở đây là một câu khẳng định về QUÁ KHỨ: "lúc 14:22 ngày 03/09,
anh A đã duyệt phiếu này". Sửa nó là nói dối về quá khứ, xoá nó là xoá bằng
chứng — nên cả hai đều bị chặn ở tầng doctype, không phải ở tầng endpoint:
`api/` chỉ là một trong các đường vào, còn bất biến này thuộc về chính
chứng từ.
"""

import frappe
from frappe.model.document import Document


class PortalNhatKyYeuCau(Document):
	def validate(self):
		if not (self.de_xuat or self.sales_order):
			frappe.throw(
				"Dòng nhật ký phải gắn vào một phiếu đề xuất hoặc một đơn "
				"hàng — không gắn vào đâu thì không ai đọc tới được.",
				frappe.ValidationError,
			)

	def on_update(self):
		# `on_update` chạy CẢ khi insert. `get_doc_before_save()` trả None ở
		# lần insert đầu tiên — đó là cách phân biệt "vừa ghi" với "đang sửa
		# một dòng đã ghi", và là cách duy nhất không phải tin vào `is_new()`
		# (cờ đó đã bị đặt lại ở thời điểm hook này chạy).
		if self.get_doc_before_save() is not None:
			frappe.throw(
				"Nhật ký thao tác chỉ ghi thêm, không sửa được.",
				frappe.ValidationError,
			)

	def on_trash(self):
		frappe.throw(
			"Nhật ký thao tác không xoá được — đó là bằng chứng ai đã làm gì.",
			frappe.ValidationError,
		)
```

- [ ] **Step 4: Viết `miyano_portal/nhat_ky.py`**

```python
"""Đường DUY NHẤT ghi vào sổ nhật ký thao tác.

Một hàm, không phải mỗi nơi tự dựng một `frappe.get_doc(...)`: luật
"không bao giờ ném lỗi" và luật "người thao tác là phiên đang gọi" phải
đúng ở MỌI chỗ ghi, mà một luật lặp ở mười hai nơi thì sớm muộn cũng lệch
một nơi — và nơi lệch sẽ là nơi không ai để ý.

Khoá sự kiện là KHOÁ, không phải nhãn (Ruling P54). Nhãn tiếng Việt sống ở
`frontend/src/format.js`. Sổ này là bản ghi VĨNH VIỄN — một khoá đã ghi
xuống thì không sửa được nữa, nên nó tuyệt đối không được mang theo một
quyết định biên tập.
"""

import frappe
from frappe.utils import now_datetime

DOCTYPE = "Portal Nhat Ky Yeu Cau"

VAI_KHOA = "khoa"
VAI_QUAN_LY = "quan_ly"
VAI_MIYANO = "miyano"
VAI_HE_THONG = "he_thong"

SK_KHOA_GUI_DUYET = "khoa_gui_duyet"
SK_KHOA_THU_HOI = "khoa_thu_hoi"
SK_QUAN_LY_DUYET = "quan_ly_duyet"
SK_QUAN_LY_TU_CHOI = "quan_ly_tu_choi"
SK_QUAN_LY_HUY_PHIEU = "quan_ly_huy_phieu"
SK_KHOA_XIN_SUA = "khoa_xin_sua"
SK_QUAN_LY_DUYET_SUA = "quan_ly_duyet_sua"
SK_QUAN_LY_TU_CHOI_SUA = "quan_ly_tu_choi_sua"
SK_DON_TAO = "don_tao"
SK_MIYANO_XAC_NHAN = "miyano_xac_nhan"
SK_MIYANO_BAO_GIA = "miyano_bao_gia"
SK_MIYANO_TU_CHOI = "miyano_tu_choi"
SK_KHACH_DONG_Y = "khach_dong_y"
SK_KHACH_KHONG_DONG_Y = "khach_khong_dong_y"
SK_KHACH_GUI_LAI_BAO_GIA = "khach_gui_lai_bao_gia"
SK_KHACH_HUY_DON = "khach_huy_don"
SK_GIAO_HANG = "giao_hang"
SK_HOA_DON = "hoa_don"


def ghi(su_kien, *, customer, vai, khoa_phong=None, de_xuat=None,
        sales_order=None, nguoi_thao_tac=None, ghi_chu=None,
        thoi_diem=None) -> str | None:
	"""Ghi một dòng. Trả `name`, hoặc `None` khi ghi hỏng.

	KHÔNG BAO GIỜ ném lỗi — hàm này chạy ngay sau những chuyển trạng thái
	ĐÃ THÀNH CÔNG (`gui_duyet()`, `duyet()`, hook giao hàng…). Một trục
	trặc ở khâu ghi mà cuốn theo cả transaction sẽ làm mất đúng thứ vừa
	làm được. Cùng ràng buộc tuyệt đối mà `portal_thong_bao_khach.bao_*`
	đang chịu — và cùng cách xử: nuốt lỗi nhưng để lại dấu ở Error Log,
	vì một `except: pass` trần là cách chắc chắn để mất sự kiện mà không
	ai biết.

	KHÔNG `frappe.db.commit()`: dòng nhật ký phải sống chết cùng giao dịch
	của chuyển trạng thái. Nếu chuyển trạng thái bị rollback thì dòng này
	biến mất theo — sổ không được kể một việc chưa từng xảy ra.
	"""
	try:
		if nguoi_thao_tac is None and vai != VAI_HE_THONG:
			nguoi_thao_tac = frappe.session.user
		doc = frappe.get_doc({
			"doctype": DOCTYPE,
			"customer": customer,
			"khoa_phong": khoa_phong,
			"de_xuat": de_xuat,
			"sales_order": sales_order,
			"thoi_diem": thoi_diem or now_datetime(),
			"su_kien": su_kien,
			"nguoi_thao_tac": nguoi_thao_tac,
			"vai": vai,
			"ghi_chu": ghi_chu,
		}).insert(ignore_permissions=True)
		return doc.name
	except Exception:
		try:
			frappe.log_error(
				title=f"Nhật ký thao tác: không ghi được sự kiện {su_kien}",
				message=frappe.get_traceback(with_context=True),
			)
		except Exception:
			pass
		return None
```

- [ ] **Step 5: Chạy migrate rồi chạy test**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_nhat_ky
```
Kỳ vọng: `Ran 7 tests … OK`.

- [ ] **Step 6: Chứng minh lưới ĐỎ được**

Tạm bỏ `frappe.throw` trong `on_trash`, chạy lại → `test_khong_xoa_duoc_dong_da_ghi` phải ĐỎ. Hoàn nguyên → xanh. Dán cả hai đầu ra.

- [ ] **Step 7: Commit**

```bash
git add miyano_portal/miyano_portal/doctype/portal_nhat_ky_yeu_cau miyano_portal/nhat_ky.py miyano_portal/tests/test_nhat_ky.py
git commit -m "feat(portal): so nhat ky thao tac chi-them

Mot ban ghi la mot cau khang dinh ve qua khu; sua no la noi doi ve qua
khu. Chan ca sua lan xoa o tang doctype. Ham ghi khong bao gio nem loi —
no chay ngay sau nhung chuyen trang thai da thanh cong.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 2: Ghi tám sự kiện của PHIẾU

**Files:**
- Modify: `miyano_portal/miyano_portal/doctype/portal_de_xuat_mua/portal_de_xuat_mua.py` (tám phương thức chuyển trạng thái)
- Test: `miyano_portal/tests/test_nhat_ky_su_kien.py` (tạo mới)

**Interfaces:**
- Consumes: `nhat_ky.ghi()` và các hằng từ Task 1
- Produces: mỗi chuyển trạng thái của phiếu sinh đúng **một** dòng nhật ký

- [ ] **Step 1: Viết test đỏ — bài quan trọng nhất là bài VÒNG LẶP**

Tạo `miyano_portal/tests/test_nhat_ky_su_kien.py` với lớp `TestNhatKySuKienPhieu`. Fixture theo khuôn `test_de_xuat_thu_hoi.py` (dọn phiếu cũ bằng SQL thô trước `dung_fixture`, tạo thành viên khoa + quản lý). Bài bắt buộc:

```python
	def _khoa_su_kien(self, ten_phieu):
		return [
			r.su_kien for r in frappe.get_all(
				nhat_ky.DOCTYPE, filters={"de_xuat": ten_phieu},
				fields=["su_kien"], order_by="thoi_diem asc, creation asc",
			)
		]

	def test_vong_lap_sinh_DU_moi_dong_khong_ghi_de(self):
		"""ĐÂY là bài chứng minh cả tính năng đáng tồn tại.

		Một yêu cầu đi: gửi → bị từ chối → gửi lại → duyệt → xin sửa →
		quản lý đồng ý sửa. Sáu việc, sáu dòng. Thanh năm chấm hiện nay
		hiện được ĐÚNG MỘT trong sáu; khối truy vết hiện được hai, và vòng
		duyệt sửa thì ghi đè mất (§7 mục 3b của HDSD).
		"""
		phieu = self._phieu_nhap()
		frappe.set_user(self.chu_phieu)
		phieu.reload(); phieu.gui_duyet()
		frappe.set_user(self.quan_ly)
		phieu.reload(); phieu.tu_choi("Vượt hạn mức quý này")
		frappe.set_user(self.chu_phieu)
		phieu.reload(); phieu.gui_duyet()
		frappe.set_user(self.quan_ly)
		phieu.reload(); phieu.duyet(self.quan_ly)

		self.assertEqual(
			self._khoa_su_kien(phieu.name),
			[
				nhat_ky.SK_KHOA_GUI_DUYET,
				nhat_ky.SK_QUAN_LY_TU_CHOI,
				nhat_ky.SK_KHOA_GUI_DUYET,
				nhat_ky.SK_QUAN_LY_DUYET,
			],
		)

	def test_moi_dong_mang_dung_nguoi_va_vai(self):
		"""Không đủ khi chỉ đếm số dòng: một sổ ghi đủ sáu dòng mà gán sai
		người là một sổ nói dối có trật tự."""
		phieu = self._phieu_nhap()
		frappe.set_user(self.chu_phieu)
		phieu.reload(); phieu.gui_duyet()
		frappe.set_user(self.quan_ly)
		phieu.reload(); phieu.duyet(self.quan_ly)
		dong = frappe.get_all(
			nhat_ky.DOCTYPE, filters={"de_xuat": phieu.name},
			fields=["su_kien", "nguoi_thao_tac", "vai"],
			order_by="thoi_diem asc, creation asc",
		)
		self.assertEqual(dong[0].nguoi_thao_tac, self.chu_phieu)
		self.assertEqual(dong[0].vai, nhat_ky.VAI_KHOA)
		self.assertEqual(dong[1].nguoi_thao_tac, self.quan_ly)
		self.assertEqual(dong[1].vai, nhat_ky.VAI_QUAN_LY)

	def test_thu_hoi_ghi_mot_dong(self):
		phieu = self._phieu_nhap()
		frappe.set_user(self.chu_phieu)
		phieu.reload(); phieu.gui_duyet()
		phieu.reload(); phieu.thu_hoi()
		self.assertIn(nhat_ky.SK_KHOA_THU_HOI, self._khoa_su_kien(phieu.name))

	def test_ghi_nhat_ky_hong_KHONG_lam_hong_chuyen_trang_thai(self):
		"""Ràng buộc tuyệt đối, kiểm bằng cách làm hỏng thật khâu ghi."""
		from unittest.mock import patch as mock_patch
		phieu = self._phieu_nhap()
		frappe.set_user(self.chu_phieu)
		phieu.reload()
		with mock_patch.object(nhat_ky, "ghi", side_effect=RuntimeError("hỏng")):
			with self.assertRaises(RuntimeError):
				phieu.gui_duyet()
		# ^ mock ném thẳng nên gui_duyet() vỡ; đó KHÔNG phải hành vi ta muốn.
		# Bài thật là bài dưới: hàm ghi THẬT nuốt lỗi.
```

**Ghi chú cho người thi công về bài cuối:** bài trên viết sai có chủ ý để bạn thấy cái bẫy — `mock_patch` lên chính `nhat_ky.ghi` sẽ bỏ qua lớp `try/except` nằm *bên trong* nó, nên nó đo nhầm thứ. Bài đúng là **làm hỏng ở tầng dưới**: patch `frappe.get_doc` trong module `nhat_ky` để ném lỗi, rồi khẳng định `gui_duyet()` vẫn thành công và trạng thái vẫn đổi. Viết bài đúng, xoá bài sai, và ghi lý do trong báo cáo.

- [ ] **Step 2: Chạy cho ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests \
  --app miyano_portal --module miyano_portal.tests.test_nhat_ky_su_kien
```

- [ ] **Step 3: Gọi `nhat_ky.ghi()` trong tám phương thức**

Trong `portal_de_xuat_mua.py`, sau `self.save(...)` của mỗi phương thức — **cùng chỗ, cùng lý do** với các lời gọi `bao_*` đã có. Mẫu cho `gui_duyet()`:

```python
		from miyano_portal import nhat_ky
		nhat_ky.ghi(
			nhat_ky.SK_KHOA_GUI_DUYET,
			customer=self.customer, khoa_phong=self.khoa_phong,
			de_xuat=self.name, vai=nhat_ky.VAI_KHOA,
			ghi_chu=(self.ly_do_yeu_cau or "").strip() or None,
		)
```

Bảng đối chiếu phương thức → khoá + vai + ghi chú:

| Phương thức | Khoá | Vai | `ghi_chu` |
|---|---|---|---|
| `gui_duyet()` | `SK_KHOA_GUI_DUYET` | `VAI_KHOA` | `ly_do_yeu_cau` |
| `thu_hoi()` | `SK_KHOA_THU_HOI` | `VAI_KHOA` | — |
| `duyet()` | `SK_QUAN_LY_DUYET` | `VAI_QUAN_LY` | `f"Tư cách: {self.duyet_voi_tu_cach}"` |
| `tu_choi()` | `SK_QUAN_LY_TU_CHOI` | `VAI_QUAN_LY` | lý do |
| `huy()` | `SK_QUAN_LY_HUY_PHIEU` | `VAI_QUAN_LY` | — |
| `xin_sua()` | `SK_KHOA_XIN_SUA` | `VAI_KHOA` | `f"{len(thay_doi)} dòng xin sửa"` |
| `duyet_sua()` | `SK_QUAN_LY_DUYET_SUA` | `VAI_QUAN_LY` | — |
| `tu_choi_sua()` | `SK_QUAN_LY_TU_CHOI_SUA` | `VAI_QUAN_LY` | lý do |

`import` đặt **trong hàm**, không ở đầu file — cùng khuôn các lời gọi `bao_*` hiện có, tránh vòng import giữa doctype và module tiện ích.

- [ ] **Step 4: Chạy lại module + module cũ của phiếu**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_nhat_ky_su_kien
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_de_xuat_thu_hoi
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_de_xuat_sua_sau_duyet
```
Hai module sau là lưới thật cho chính tám phương thức này — chúng phải xanh nguyên vẹn.

- [ ] **Step 5: Chứng minh ĐỎ được** — bỏ lời gọi `ghi()` trong `tu_choi()`, chạy lại, bài vòng lặp phải đỏ; hoàn nguyên.

- [ ] **Step 6: Commit**

```bash
git add miyano_portal/miyano_portal/doctype/portal_de_xuat_mua/portal_de_xuat_mua.py miyano_portal/tests/test_nhat_ky_su_kien.py
git commit -m "feat(portal): ghi nhat ky cho tam chuyen trang thai cua phieu

Moi vong la mot dong moi — va nghia la vong 'duyet sua' khong con bi ghi
de (HDSD §7 muc 3b).

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 3: Ghi bốn sự kiện do KHÁCH thao tác

**Files:**
- Modify: `miyano_portal/api/portal.py` — `portal_order_accept`, `portal_order_sua_so_luong`, `portal_order_huy`
- Test: `miyano_portal/tests/test_nhat_ky_su_kien.py` (thêm lớp `TestNhatKySuKienKhach`)

**Interfaces:**
- Consumes: `nhat_ky.ghi()` (Task 1)
- Produces: bốn khoá `SK_KHACH_DONG_Y`, `SK_KHACH_KHONG_DONG_Y`, `SK_KHACH_GUI_LAI_BAO_GIA`, `SK_KHACH_HUY_DON` gắn vào `sales_order`

`vai` cho cả bốn là `VAI_QUAN_LY` — chỉ quản lý bệnh viện mới thao tác được trên đơn (nhân viên khoa bị `dam_bao_duoc_sua_don_da_duyet` chặn). `khoa_phong` lấy từ `so.custom_khoa_phong` khi cột đó tồn tại; nếu không thì để trống.

- [ ] **Step 1: Viết test đỏ** — mỗi sự kiện một bài, gọi THẲNG endpoint dưới `frappe.set_user(...)` đúng khuôn `test_yeu_cau_list.py`, rồi khẳng định dòng nhật ký sinh ra với đúng `su_kien`/`nguoi_thao_tac`/`sales_order`. Thêm một bài vế âm: đơn của bệnh viện khác thì endpoint ném `PermissionError` **và** không sinh dòng nhật ký nào.
- [ ] **Step 2: Chạy cho ĐỎ.**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests \
  --app miyano_portal --module miyano_portal.tests.test_nhat_ky_su_kien
```

- [ ] **Step 3: Thêm lời gọi tại ba endpoint**, đặt **sau** khi thao tác đã thành công và **trước** `return`:

| Endpoint | Khoá | `ghi_chu` |
|---|---|---|
| `portal_order_accept(action="dong_y")` | `SK_KHACH_DONG_Y` | — |
| `portal_order_accept(action="khong_dong_y")` | `SK_KHACH_KHONG_DONG_Y` | lý do khách nhập |
| `portal_order_sua_so_luong` | `SK_KHACH_GUI_LAI_BAO_GIA` | `f"{n} dòng đổi số lượng"` |
| `portal_order_huy` | `SK_KHACH_HUY_DON` | lý do huỷ |

`customer` lấy từ `so.customer`; `khoa_phong` từ `so.get("custom_khoa_phong")` — dùng `.get()` vì cột đó có thể chưa tồn tại trên site chưa chạy patch v1_23, đúng lưới an toàn mà `portal_yeu_cau_cua_toi` đã dựng.

- [ ] **Step 4: Chạy lại module + `test_de_xuat_sua_sau_duyet` + `test_e2_workflow_va_accept`.** Hai module sau là lưới thật cho chính ba endpoint này.
- [ ] **Step 5: Chứng minh ĐỎ được** — bỏ lời gọi ở `portal_order_huy`, bài tương ứng phải đỏ; hoàn nguyên.
- [ ] **Step 6: Commit.**

---

## Task 4: Ghi sáu sự kiện của MIYANO và hệ thống

**Files:**
- Modify: `miyano_portal/de_xuat_duyet.py` (`don_tao`), `miyano_portal/api/portal.py` (`_dam_bao_phieu_tu_duyet` → `don_tao`), `miyano_portal/kho/delivery_hook.py` (`giao_hang`), `miyano_portal/hooks.py`
- Create: `miyano_portal/nhat_ky_hook.py` — hai hàm hook
- Test: `miyano_portal/tests/test_nhat_ky_su_kien.py` (lớp `TestNhatKySuKienMiyano`)

**Interfaces:**
- Produces: `nhat_ky_hook.tu_sales_order_on_update(doc, method=None)` và `nhat_ky_hook.tu_sales_invoice_on_submit(doc, method=None)`

- [ ] **Step 1: Viết test đỏ.** Bài trọng tâm: đổi `workflow_state` của một Sales Order qua `apply_workflow` thật (khuôn `test_yeu_cau_list.py::_miyano_tu_choi`), khẳng định sinh đúng một dòng `SK_MIYANO_TU_CHOI` mang `nguoi_thao_tac` là người đang thao tác. Bài thứ hai: **lưu lại mà KHÔNG đổi workflow_state thì KHÔNG sinh dòng nào** — thiếu bài này thì mỗi lần Miyano sửa một ghi chú vặt cũng đẻ một dòng, và sổ biến thành rác.
- [ ] **Step 2: Chạy cho ĐỎ.**
- [ ] **Step 3: Viết `nhat_ky_hook.py`:**

```python
"""Hai móc nối vào chuỗi hook ĐÃ CÓ của `Sales Order` và `Sales Invoice`.

CỐ Ý không dựng hook mới: `hooks.py` đã móc sẵn `Sales Order.on_update` và
`Sales Invoice.on_submit` cho việc khác. Thêm một tên hàm vào danh sách có
sẵn rẻ hơn và ít bất ngờ hơn là thêm một điểm móc thứ hai lên cùng một
doctype.

Chỉ ghi khi `workflow_state` THẬT SỰ đổi. Không có phép so đó thì mỗi lần
nhân sự Miyano sửa một ghi chú vặt trên đơn cũng đẻ một dòng nhật ký, và
một cuốn sổ đầy dòng vô nghĩa là một cuốn sổ không ai đọc — tức là mất
đúng thứ nó sinh ra để cho.
"""
```

Ánh xạ `workflow_state` mới → khoá: `"Đã xác nhận"` → `SK_MIYANO_XAC_NHAN`; `"Chờ khách đồng ý"` → `SK_MIYANO_BAO_GIA` (ghi chú: hạn hiệu lực); `"Từ chối"` → `SK_MIYANO_TU_CHOI` (ghi chú: `custom_ly_do_tu_choi`). Trạng thái khác → không ghi.

- [ ] **Step 4: Khai vào `hooks.py`** — thêm tên hàm vào **danh sách đã có** của `Sales Order.on_update` và `Sales Invoice.on_submit`, kèm chú thích nêu lý do.
- [ ] **Step 5: `giao_hang` và `don_tao`** — `on_delivery_note_submit` ghi `SK_GIAO_HANG` (ghi chú: đợt mấy); `duyet_va_tao_don` và `_dam_bao_phieu_tu_duyet` ghi `SK_DON_TAO` với `vai=VAI_HE_THONG`.
- [ ] **Step 6: Chạy module + `test_kho_delivery_hook` + `test_de_xuat_duyet`.**
- [ ] **Step 7: Chứng minh ĐỎ được.**
- [ ] **Step 8: Commit.**

---

## Task 5: `lien_he_nguoi_dung()` và endpoint đọc nhật ký

**Files:**
- Modify: `miyano_portal/portal_context.py`, `miyano_portal/api/portal.py`, `miyano_portal/tests/test_pham_vi_endpoint.py`
- Test: `miyano_portal/tests/test_nhat_ky_doc.py` (tạo mới)

**Interfaces:**
- Produces:
  - `portal_context.lien_he_nguoi_dung(email, *, cho_hien_tai_khoan=True) -> dict` → `{"ten": str, "dien_thoai": str, "tai_khoan": str}`. `dien_thoai` = `User.mobile_no` hoặc `User.phone`, `""` khi cả hai trống. `tai_khoan` = `""` khi `cho_hien_tai_khoan=False` **hoặc** khi `ten` trùng chính email.
  - `api/portal.py::portal_nhat_ky_yeu_cau(de_xuat=None, order=None) -> list[dict]` — mỗi phần tử: `{su_kien, thoi_diem, vai, ten, dien_thoai, tai_khoan, ghi_chu, suy_ra}`. `suy_ra = True` cho hai dòng dựng lại từ chứng từ cũ (Step 5), `False` cho dòng đã ghi thật.

- [ ] **Step 1: Viết test đỏ.** Bốn bài phải có:
  1. **Vế dương**: quản lý đọc được nhật ký của một yêu cầu thuộc đơn vị mình, đủ số dòng, đúng thứ tự thời gian.
  2. **Vế âm trục khoa**: nhân viên khoa A đọc nhật ký của yêu cầu thuộc khoa B → `PermissionError`.
  3. **Vế âm trục khách hàng**: bệnh viện X đọc của bệnh viện Y → `PermissionError`.
  4. **`vai = miyano` KHÔNG bao giờ trả email** — bài này khoá đúng ranh giới §8 của spec. Dựng một dòng `SK_MIYANO_XAC_NHAN` với `nguoi_thao_tac` là một tài khoản nhân sự, rồi khẳng định `tai_khoan == ""` trong khi `ten` vẫn có.
- [ ] **Step 2: Chạy cho ĐỎ.**
- [ ] **Step 3: Viết `lien_he_nguoi_dung()`** ngay cạnh `ten_nguoi_dung()` — dùng lại nó cho phần tên, **không chép logic lui-về-email** sang chỗ thứ hai.
- [ ] **Step 4: Viết endpoint.** Nó **không tự chế bộ lọc**: gọi `api.de_xuat._phieu_cua_toi(de_xuat, cho_quan_ly=True)` khi có `de_xuat`, hoặc `dam_bao_xem_duoc("Sales Order", order)` khi có `order`; rồi lấy dòng theo **cả hai** khoá của chứng từ đã qua cửa (một yêu cầu có cả phiếu lẫn đơn thì nhật ký nằm ở cả hai).
- [ ] **Step 5: Suy hai dòng cho chứng từ tạo TRƯỚC khi bật nhật ký** (§9.6 của spec)

Khi truy vấn không trả dòng `SK_KHOA_GUI_DUYET` nào mà phiếu **có** `thoi_diem_gui`, chèn một dòng suy từ `nguoi_yeu_cau`/`thoi_diem_gui`. Tương tự `SK_QUAN_LY_DUYET` từ `nguoi_duyet`/`thoi_diem_duyet`. Cả hai mang thêm khoá `suy_ra: True` để tầng hiển thị nói được đây là dòng dựng lại, không phải dòng đã ghi.

**Chỉ chèn khi KHÔNG có dòng thật cùng loại** — chèn cả hai sẽ hiện đôi cho mọi yêu cầu mới.

Đây **không** phải diễn giải kiểu `Version` mà spec §4 bác: bốn trường đó là sự kiện đã ghi tường minh, có người và có mốc giờ, chỉ nằm trên chứng từ thay vì trong sổ.

Hai bài test bắt buộc:

- `test_don_cu_khong_co_nhat_ky_van_suy_duoc_hai_dong` — xoá sạch dòng nhật ký của một phiếu đã duyệt bằng SQL thô, gọi endpoint, khẳng định vẫn có `SK_KHOA_GUI_DUYET` và `SK_QUAN_LY_DUYET`, và **mọi** dòng trả về đều `suy_ra is True`. Docstring nêu lý do: *phiếu tạo trước khi bật nhật ký vẫn mang người yêu cầu và người duyệt; để màn hình trống trơn là làm người dùng tưởng hệ thống hỏng.*
- `test_yeu_cau_MOI_khong_bi_hien_doi` — **vế âm**, một yêu cầu vừa đi qua luồng thật: khẳng định `SK_KHOA_GUI_DUYET` xuất hiện **đúng một lần** và không dòng nào `suy_ra`. Thiếu bài này thì phép suy chèn thêm một bản sao cho MỌI yêu cầu mới, và mỗi lần gửi duyệt sẽ hiện hai dòng giống hệt nhau.

- [ ] **Step 6: Khai vào `DA_AP_PHAM_VI`** trong `test_pham_vi_endpoint.py` kèm lý do một dòng.
- [ ] **Step 7: Chạy module + `test_pham_vi_endpoint`.**
- [ ] **Step 8: Chứng minh ĐỎ được** — bỏ lời gọi chốt phạm vi, bài vế âm phải đỏ; hoàn nguyên.
- [ ] **Step 9: Commit.**

---

## Task 6: Số điện thoại vào khối truy vết

**Files:**
- Modify: `miyano_portal/api/de_xuat.py` (`de_xuat_chi_tiet`), `frontend/src/components/chi-tiet/KhoiTruyVet.vue`
- Test: `miyano_portal/tests/test_nhat_ky_doc.py`

**Interfaces:**
- Produces: `de_xuat_chi_tiet()` trả thêm `nguoi_yeu_cau_dien_thoai` và `nguoi_duyet_ten` / `nguoi_duyet_dien_thoai`.

Hôm nay `de_xuat_chi_tiet` đã trả `nguoi_yeu_cau_ten` (giải ở BIÊN GIỚI API, không đổi giá trị lưu). Task này đi tiếp đúng đường đó — `nguoi_duyet` hiện đang hiện **email thô** trên màn (điểm Minor #6 của vòng review 03/09), nên task này vá luôn.

- [ ] **Step 1: Viết test đỏ.** Ba bài trong `test_nhat_ky_doc.py`:
  1. `de_xuat_chi_tiet` trả `nguoi_duyet_ten` là **tên hiển thị**, không phải email — vá luôn điểm Minor #6 của vòng review 03/09 (`nguoi_duyet` đang hiện email thô trên màn).
  2. Tài khoản **có** số → `nguoi_yeu_cau_dien_thoai` đúng bằng số đó.
  3. Tài khoản **không** có số → khoá đó là `""`, **không** phải `None` và **không** phải `"—"`. Ba giá trị này khác nhau ở tầng hiển thị; trả về cái thứ hai hay thứ ba là đẩy quyết định biên tập xuống backend.
- [ ] **Step 2: Chạy cho ĐỎ.**
- [ ] **Step 3: Thêm ba khoá vào `de_xuat_chi_tiet`**, giải ở **BIÊN GIỚI API** cạnh `nguoi_yeu_cau_ten` đã có — cùng chỗ, cùng lý do, không đổi giá trị LƯU.
- [ ] **Step 4: Sửa `KhoiTruyVet.vue`** — hiện số dưới dạng `<a :href="'tel:' + …">`, bọc `v-if` trên **chính giá trị số**, không dùng `|| '—'`.
- [ ] **Step 5: Lưới regex** trong `test_nhat_ky_giao_dien.py`: khẳng định `KhoiTruyVet.vue` có `tel:` và **không** chứa chuỗi `'—'` ở nhánh số điện thoại. Một dấu gạch ở chỗ đáng lẽ có số là một câu hỏi màn hình không trả lời được.
- [ ] **Step 6: `yarn build`.**
- [ ] **Step 7: Chứng minh ĐỎ được** — đổi `v-if` thành `|| '—'`, lưới phải đỏ; hoàn nguyên.
- [ ] **Step 8: Commit.**

---

## Task 7: Component `KhoiDongThoiGian.vue`

**Files:**
- Create: `frontend/src/components/chi-tiet/KhoiDongThoiGian.vue`
- Modify: `frontend/src/format.js`, `frontend/src/style.css`
- Test: `miyano_portal/tests/test_nhat_ky_giao_dien.py` (lưới regex, tạo mới)

**Interfaces:**
- Produces: props `dong: Array` (kết quả endpoint Task 5), `dangTai: Boolean`. Không emit gì.
- `format.js` xuất `NHAN_SU_KIEN` (18 khoá → nhãn tiếng Việt) và `mauChamSuKien(su_kien, vai)` → `'benh-vien' | 'miyano' | 'lui' | 'he-thong'`.

Bố cục theo §9 của spec — **dùng lại `.vtl`/`.vst` đã có**, chỉ thêm bốn lớp màu chấm. Không thêm lớp bố cục mới.

- [ ] **Step 1: Lưới regex đỏ trước.** Ba bài: (a) `format.js` có đủ **18** khoá và mỗi khoá có nhãn khác rỗng — thiếu một khoá thì một sự kiện thật sẽ hiện ra chuỗi khoá thô trước mặt bệnh viện; (b) component dùng `.vst` chứ không dựng lớp bố cục mới; (c) số điện thoại render bằng `tel:`.
- [ ] **Step 2–7**: viết nhãn, viết component, `yarn build`, chứng minh đỏ được, commit.

---

## Task 8: Lắp vào màn chi tiết và soi mắt

**Files:**
- Modify: `frontend/src/views/ChiTietYeuCau.vue`
- Test: `miyano_portal/tests/test_nhat_ky_giao_dien.py`

- [ ] **Step 1: Lưới đỏ trước** — `ChiTietYeuCau.vue` phải **gọi** `portal_nhat_ky_yeu_cau` (canh chỗ GỌI, không canh dòng import — bài học Task 7b của phiên trước) và **render** `KhoiDongThoiGian` ngay sau `KhoiTienTrinh`.
- [ ] **Step 2–4**: nạp nhật ký trong `load()` cho cả hai nhánh (vào bằng đường phiếu và bằng đường đơn), lắp component, `yarn build`.
- [ ] **Step 5: Soi mắt bốn ca** — dựng lại đường vào trình duyệt trước (xem Global Constraints):

| Ca | Kỳ vọng |
|---|---|
| Phiếu vừa gửi duyệt | Một dòng xanh dương "Khoa gửi duyệt", có tên + giờ |
| Phiếu bị từ chối rồi gửi lại | Ba dòng, dòng giữa **chấm đỏ** |
| Đơn đã giao | Có dòng xanh lá của Miyano; số điện thoại bấm được (nếu tài khoản có số) |
| Đơn cũ tạo trước khi bật nhật ký | Hai dòng suy từ phiếu, hoặc câu "Nhật ký bắt đầu ghi từ…" |

Ca nào không dựng được thì **ghi rõ**, đừng khai khống.
- [ ] **Step 6: Commit.**

---

## Task 9: Tài liệu và suite chốt

**Files:**
- Modify: `docs/BAN-DO-CHUC-NANG.md`, `docs/HDSD-phan-quyen-khoa-phong.md`, `docs/HDSD-hai-vai-khach-hang-va-nhan-vien.md`

- [ ] **Step 1**: `BAN-DO-CHUC-NANG.md` — thêm mục về sổ nhật ký và dòng thời gian.
- [ ] **Step 2**: `HDSD-phan-quyen-khoa-phong.md` — **xoá mục 3b khỏi danh sách còn nợ** (*"vòng duyệt sửa chưa ghi mốc riêng"*), vì Task 2 vá nó; ghi rõ là đã vá và vá bằng gì.
- [ ] **Step 3**: `HDSD-hai-vai-khach-hang-va-nhan-vien.md` — đoạn cho người dùng cuối: bấm vào đơn thấy được ai đã làm gì, gọi được số hiển thị.
- [ ] **Step 4**: Ghi **quy trình bắt buộc điền số điện thoại khi tạo tài khoản** (Đ3 của spec) vào `HDSD-tao-khach-hang-mo-kho-va-thao-tac-cong.md`.
- [ ] **Step 5**: `yarn build` + **suite đầy đủ**. Nếu có bài đỏ, **đừng sửa test cho xanh** — báo lại.
- [ ] **Step 6: Commit.**

---

## Rủi ro đã biết

1. **Task 4 là task khó nhất** — nó móc vào hook của doctype ERPNext lõi. Nếu phép so `workflow_state` sai, sổ sẽ đầy dòng rác hoặc thiếu dòng, và cả hai đều khó thấy. Bài "lưu mà không đổi trạng thái thì không ghi" là lưới chính; đừng bỏ.
2. **Không có test JS.** Task 7 và 8 chỉ được canh bằng lưới regex + soi mắt. Chỗ nào không kiểm chứng được phải ghi ra.
3. **Cầu nối soi mắt đã tắt** — task cần trình duyệt phải tự dựng lại; đừng giả định nó còn chạy.
4. **`_dam_bao_phieu_tu_duyet` gán `ma_de_xuat` TRƯỚC `insert()`** — nếu ghi `don_tao` ở sai vị trí trong hàm đó, `sales_order` sẽ còn rỗng. Ghi **sau** khi đơn đã có tên.
