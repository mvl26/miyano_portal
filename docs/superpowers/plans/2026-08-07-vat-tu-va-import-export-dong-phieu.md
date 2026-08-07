# Danh mục vật tư trên cổng + import/export bảng dòng phiếu — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Khách hàng tự quản lý danh mục vật tư của kho mình trên cổng, import/export bảng dòng của phiếu nhập và phiếu xuất, và tạo nhanh một vật tư ngay tại dòng đang soạn khi gặp mã chưa có.

**Architecture:** Không thêm doctype. Hai module nghiệp vụ mới (`kho/vat_tu.py`, `kho/dong_phieu.py`) đứng cùng tầng với `ledger.py` / `reports.py` / `import_ton_dau.py`: chúng nhận `kho` đã resolve từ nơi gọi và không biết gì về phiên đăng nhập. Tầng `api/kho.py` lo phiên, quyền và kiểm sở hữu tham số client gửi. Phần đọc `.xlsx` dùng lại nguyên bộ hàm của `import_ton_dau.py` sau một refactor thuần tách chúng ra khỏi bộ cột cứng.

**Tech Stack:** Frappe v15.113 · ERPNext v15 · Python 3.12 · openpyxl · Vue 3.4 + vue-router 4.3 + Vite 6 (SPA tại `/portal`) · MariaDB 10.11.

**Spec:** `docs/superpowers/specs/2026-08-07-vat-tu-va-import-export-dong-phieu-design.md`

## Global Constraints

- Site làm việc: **`erptest.local`**, dev server `:8003` (`systemctl --user restart erptest-dev.service`). **Không bao giờ** chạm `supplycore-miyano.local` hay bench `:8002`.
- **Không cấp thêm bất kỳ DocPerm nào cho role `Customer`** trên tám doctype kho. Mọi truy cập của cổng đi qua `miyano_portal.api.kho.*`.
- Mọi endpoint kho **tự suy kho từ phiên** qua `get_portal_kho()`; không endpoint nào nhận tên kho hay tên khách hàng từ client.
- Định danh do client gửi (`name` của vật tư, `name` của phiếu) phải qua `_vat_tu_cua_kho()` / `_phieu_cua_kho()` **trước** mọi `frappe.get_doc` — `get_doc` không chạy hook `has_permission` ở build này.
- **Tham số whitelist nhận số KHÔNG được gắn type hint** (`limit`, `ca_tat`, `so_luong`…). `frappe.utils.typing_validations` kích hoạt cả trong test và ném lỗi tiếng Anh trước khi hàm chạy. Ép kiểu bằng `_so_nguyen()` / `_so_thuc()` sẵn có.
- Mọi thông điệp lỗi bằng **tiếng Việt**, không lộ tên doctype.
- Validation đặt ở `validate` / `before_save` / `before_cancel`, **không** ở `on_update` / `on_submit` / `on_cancel`.
- Doctype đặt tên tiếng Anh, fieldname tiếng Việt không dấu, label tiếng Việt.
- **Không gọi `frappe.db.commit()`** trong bất kỳ module nào (kể cả helper của test).
- Test dùng `FrappeTestCase` + `seed_kho_demo()`; **không sửa test đang có** trừ nơi kế hoạch nói rõ. `FrappeTestCase` chỉ rollback một lần mỗi **class**, nên test tự dọn dữ liệu mình tạo trong `tearDown`.
- Frontend **không có test runner**. Kiểm chứng frontend = `bench build --app miyano_portal` không lỗi + thao tác thật trên `http://192.168.61.129:8003/portal` bằng tài khoản `bvminhduc@demo.miyano` / `Portal@123`.
- Commit tiếng Việt theo khuôn repo: `feat(kho): …`, `fix(kho): …`, `refactor(kho): …`, `test(kho): …`, `docs(kho): …`.

---

## File Structure

**Tạo mới**

| File | Trách nhiệm |
|---|---|
| `miyano_portal/kho/vat_tu.py` | danh mục vật tư: tạo · sửa có rào · `co_phat_sinh` · đọc/ghi file danh mục |
| `miyano_portal/kho/dong_phieu.py` | bảng dòng phiếu: bộ cột · file mẫu · đọc file thành dòng · xuất dòng ra `.xlsx` |
| `miyano_portal/tests/test_kho_vat_tu.py` | test cho `kho/vat_tu.py` (phần tạo/sửa) + endpoint |
| `miyano_portal/tests/test_kho_vat_tu_import.py` | test import/export danh mục |
| `miyano_portal/tests/test_kho_dong_phieu.py` | test `kho/dong_phieu.py` + endpoint |
| `frontend/src/views/DanhMucVatTu.vue` | màn danh mục vật tư |
| `frontend/src/views/ImportDanhMuc.vue` | màn import danh mục (3 bước) |
| `frontend/src/components/VatTuModal.vue` | modal tạo/sửa vật tư, dùng chung 3 màn |

**Sửa**

| File | Việc |
|---|---|
| `miyano_portal/kho/import_ton_dau.py` | refactor thuần: tách `mo_workbook()` và `read_header(ws, columns, required)` khỏi bộ cột cứng |
| `miyano_portal/api/kho.py` | 8 endpoint mới + mở rộng `kho_vat_tu_list` |
| `frontend/src/router.js` | 2 route mới |
| `frontend/src/views/Kho.vue` | nút **Danh mục vật tư** |
| `frontend/src/views/PhieuNhapDetail.vue` | thanh import/export + trạng thái dòng + tạo nhanh |
| `frontend/src/views/PhieuXuatDetail.vue` | như trên + cảnh báo "chưa có tồn" |
| `docs/HDSD-tao-khach-hang-mo-kho-va-thao-tac-cong.md` | mục C mới cho danh mục và import dòng |

---

## Task 1: Tách phần dùng chung của bộ đọc `.xlsx`

Refactor thuần, **không đổi hành vi**. `_read_header()` hiện đang đóng đinh vào `COLUMNS`/`REQUIRED_FIELDS` của tồn đầu kỳ qua biến module `_ALIASES`, nên hai bộ cột mới (danh mục, dòng phiếu) không dùng lại được.

**Files:**
- Modify: `miyano_portal/kho/import_ton_dau.py:42-48` (`_ALIASES`), `:111-134` (`_read_header`), `:182-191` (mở workbook trong `parse_workbook`)
- Test: `miyano_portal/tests/test_kho_import.py` (chạy lại, không sửa)

**Interfaces:**
- Produces:
  - `build_aliases(columns: list[tuple[str, str]]) -> dict[str, str]`
  - `read_header(ws, columns, required_fields) -> tuple[int, dict[str, int]]`
  - `mo_workbook(content: bytes)` → `ws` (worksheet đang hoạt động), throw tiếng Việt nếu tệp hỏng
  - `_read_header(ws)` giữ nguyên chữ ký cũ (wrapper)

- [ ] **Step 1: Chạy test hiện có để chốt mốc xanh**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_import`
Expected: PASS toàn bộ. Ghi lại số ca — sau refactor phải bằng đúng số này.

- [ ] **Step 2: Thay `_ALIASES` bằng hàm dựng alias**

Thay khối `import_ton_dau.py:42-48`:

```python
def build_aliases(columns: list[tuple[str, str]]) -> dict[str, str]:
	"""Bảng nhận diện tiêu đề cột: nhãn hiển thị (đã NFC + trim + lower) và
	chính tên field đều trỏ về field. Nhờ vậy header gõ lệch hoa/thường hay
	đảo thứ tự cột vẫn nhận ra được.

	Là HÀM chứ không phải hằng số module: ba bộ cột (tồn đầu kỳ, danh mục vật
	tư, dòng phiếu) dùng chung đúng một cơ chế nhận diện này.
	"""
	aliases: dict[str, str] = {}
	for label, field in columns:
		aliases[unicodedata.normalize("NFC", label).strip().lower()] = field
		aliases[field] = field
	return aliases


_ALIASES = build_aliases(COLUMNS)
```

- [ ] **Step 3: Tổng quát hoá `_read_header`**

Thay `import_ton_dau.py:111-134` bằng:

```python
def read_header(ws, columns, required_fields) -> tuple[int, dict[str, int]]:
	"""Tìm dòng tiêu đề trong 5 dòng đầu và ánh xạ field -> chỉ số cột.

	`columns`/`required_fields` là tham số chứ không phải hằng số module: hàm
	này phục vụ cả ba bộ cột. `required_fields` ở đây là các cột BẮT BUỘC PHẢI
	CÓ MẶT trong header — khác với "bắt buộc có giá trị ở mỗi dòng", việc đó
	do từng hàm parse tự kiểm.
	"""
	aliases = build_aliases(columns)
	header_row = None
	header_cells = None
	for r, row_cells in enumerate(ws.iter_rows(min_row=1, max_row=min(ws.max_row, 5)), start=1):
		if any(c.value not in (None, "") for c in row_cells):
			header_row = r
			header_cells = row_cells
			break
	if header_row is None:
		frappe.throw("Tệp trống, không có dữ liệu.", frappe.ValidationError)

	col_index: dict[str, int] = {}
	for idx, cell in enumerate(header_cells, start=1):
		field = aliases.get(_fold(cell.value))
		if field:
			col_index[field] = idx

	missing = [label for label, field in columns if field in required_fields and field not in col_index]
	if missing:
		frappe.throw(
			"Tệp thiếu cột bắt buộc: " + ", ".join(missing) + ". Vui lòng tải lại tệp mẫu.",
			frappe.ValidationError,
		)
	return header_row, col_index


def _read_header(ws) -> tuple[int, dict[str, int]]:
	"""Bộ cột tồn đầu kỳ. Giữ lại để nơi gọi cũ và test cũ không phải đổi."""
	return read_header(ws, COLUMNS, REQUIRED_FIELDS)
```

- [ ] **Step 4: Tách bước mở workbook**

Thêm ngay trên `parse_workbook`:

```python
def mo_workbook(content: bytes):
	"""Mở nội dung .xlsx và trả về sheet đang hoạt động.

	Tách riêng vì cả ba đường import đều cần đúng một thông điệp tiếng Việt khi
	tệp hỏng — openpyxl ném lỗi tiếng Anh nêu chi tiết nội bộ của tệp zip.
	"""
	try:
		wb = load_workbook(io.BytesIO(content), data_only=True)
	except Exception:
		frappe.throw(
			"Tệp không đúng định dạng .xlsx hoặc đã hỏng. Vui lòng dùng tệp mẫu.",
			frappe.ValidationError,
		)
	return wb.active
```

Rồi thay đoạn mở workbook trong `parse_workbook` (`:182-191`) bằng:

```python
	ws = mo_workbook(content)
	header_row, col_index = _read_header(ws)
```

- [ ] **Step 5: Chạy lại test, phải xanh y hệt Step 1**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_import`
Expected: PASS, đúng số ca như Step 1. Một ca đỏ ở đây nghĩa là refactor đã đổi hành vi — sửa cho bằng, đừng sửa test.

- [ ] **Step 6: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal
git add miyano_portal/kho/import_ton_dau.py
git commit -m "refactor(kho): tách read_header và mo_workbook khỏi bộ cột tồn đầu kỳ"
```

---

## Task 2: `kho/vat_tu.py` — tạo và sửa có rào

**Files:**
- Create: `miyano_portal/kho/vat_tu.py`
- Test: `miyano_portal/tests/test_kho_vat_tu.py`

**Interfaces:**
- Consumes: `import_ton_dau._match_vat_tu`, `import_ton_dau._norm`, `ledger.get_lot_balances`, `ledger.EPS`
- Produces:
  - `co_phat_sinh(vat_tu: str) -> bool`
  - `cac_vat_tu_co_phat_sinh(kho: str) -> set[str]`
  - `ra_dict(name: str, da_co: bool = False) -> dict` — khoá: `name, ma_vat_tu, ten_vat_tu, dvt, item_code, quy_cach, nhom, ghi_chu, active, co_phat_sinh, da_co`
  - `tao(kho: str, du_lieu: dict) -> dict`
  - `sua(kho: str, vat_tu: str, du_lieu: dict) -> dict`

- [ ] **Step 1: Viết test thất bại**

Tạo `miyano_portal/tests/test_kho_vat_tu.py`:

```python
"""Danh mục vật tư trên cổng — tạo, sửa có rào."""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.kho import vat_tu as vat_tu_mod
from miyano_portal.setup.seed_kho_demo import seed_kho_demo


class TestVatTuTao(FrappeTestCase):
	def setUp(self):
		self.kho = seed_kho_demo()
		self.kho_bm = self.kho["kho_bm"]
		self._da_tao = []

	def tearDown(self):
		for name in self._da_tao:
			if frappe.db.exists("Customer Warehouse Item", name):
				frappe.delete_doc("Customer Warehouse Item", name, force=True, ignore_permissions=True)

	def _tao(self, **kwargs):
		row = vat_tu_mod.tao(self.kho_bm, kwargs)
		self._da_tao.append(row["name"])
		return row

	def test_ma_khop_item_miyano_thi_tu_gan_item_code(self):
		# VT0005 chứ không phải MYN-*: seed_demo() (do seed_kho_demo() gọi) tạo
		# VT0005 và HC0009 trên MỌI site, còn các Item MYN-* chỉ có nếu
		# uat_scenario đã chạy — một test phụ thuộc dữ liệu ngoài phạm vi seed
		# của chính nó là test đỏ ngẫu nhiên.
		row = self._tao(ma_vat_tu="vt0005", ten_vat_tu="Găng tay khám", dvt="Cái")
		self.assertEqual(row["item_code"], "VT0005")
		# Chính tả chuẩn của Miyano, không phải cách người dùng gõ.
		self.assertEqual(row["ma_vat_tu"], "VT0005")

	def test_ma_rieng_thi_item_code_trong(self):
		row = self._tao(ma_vat_tu="BM-TU-MUA-01", ten_vat_tu="Băng ép", dvt="Cuộn")
		self.assertEqual(row["item_code"], "")

	def test_item_code_client_gui_bi_bo_qua(self):
		# HC0009 là một Item CÓ THẬT, nên nếu server nhận item_code từ client
		# thì trường này sẽ có giá trị — test bắt đúng nhánh đó, không phải bắt
		# một mã bịa mà đằng nào cũng rỗng.
		row = self._tao(
			ma_vat_tu="BM-TU-MUA-02", ten_vat_tu="Gạc", dvt="Gói", item_code="HC0009"
		)
		self.assertEqual(row["item_code"], "")

	def test_tao_trung_ma_tra_ve_vat_tu_dang_co(self):
		row = vat_tu_mod.tao(
			self.kho_bm, {"ma_vat_tu": "MYN-GLOVE-M", "ten_vat_tu": "X", "dvt": "Hộp"}
		)
		self.assertTrue(row["da_co"])
		self.assertEqual(row["name"], self.kho["vt_bm"])

	def test_thieu_ten_bi_chan(self):
		with self.assertRaises(frappe.ValidationError) as ctx:
			vat_tu_mod.tao(self.kho_bm, {"ma_vat_tu": "BM-X", "dvt": "Cái"})
		self.assertIn("Tên vật tư", str(ctx.exception))


class TestVatTuSua(FrappeTestCase):
	def setUp(self):
		self.kho = seed_kho_demo()
		self.kho_bm = self.kho["kho_bm"]
		self.vt_moi = vat_tu_mod.tao(
			self.kho_bm, {"ma_vat_tu": "BM-SUA-01", "ten_vat_tu": "Chưa phát sinh", "dvt": "Cái"}
		)["name"]

	def tearDown(self):
		if frappe.db.exists("Customer Warehouse Item", self.vt_moi):
			frappe.delete_doc("Customer Warehouse Item", self.vt_moi, force=True, ignore_permissions=True)

	def test_sua_ten_luon_duoc(self):
		row = vat_tu_mod.sua(self.kho_bm, self.kho["vt_bm"], {"ten_vat_tu": "Tên mới"})
		self.assertEqual(row["ten_vat_tu"], "Tên mới")

	def test_sua_dvt_khi_chua_phat_sinh_thi_duoc(self):
		row = vat_tu_mod.sua(self.kho_bm, self.vt_moi, {"dvt": "Hộp"})
		self.assertEqual(row["dvt"], "Hộp")

	def test_sua_dvt_khi_da_phat_sinh_bi_chan(self):
		# vt_bm đã có phát sinh? Nếu chưa, tạo một phiếu nhập đã ghi sổ trước.
		self._bao_dam_co_phat_sinh(self.kho["vt_bm"])
		with self.assertRaises(frappe.ValidationError) as ctx:
			vat_tu_mod.sua(self.kho_bm, self.kho["vt_bm"], {"dvt": "Cái"})
		self.assertIn("đã có phát sinh", str(ctx.exception))

	def test_sua_ma_khi_da_phat_sinh_bi_chan(self):
		self._bao_dam_co_phat_sinh(self.kho["vt_bm"])
		with self.assertRaises(frappe.ValidationError) as ctx:
			vat_tu_mod.sua(self.kho_bm, self.kho["vt_bm"], {"ma_vat_tu": "MA-KHAC"})
		self.assertIn("đã có phát sinh", str(ctx.exception))

	def test_tat_vat_tu_con_ton_bi_chan(self):
		self._bao_dam_co_phat_sinh(self.kho["vt_bm"])
		with self.assertRaises(frappe.ValidationError) as ctx:
			vat_tu_mod.sua(self.kho_bm, self.kho["vt_bm"], {"active": 0})
		self.assertIn("còn tồn", str(ctx.exception))

	def test_tat_vat_tu_khong_ton_thi_duoc(self):
		row = vat_tu_mod.sua(self.kho_bm, self.vt_moi, {"active": 0})
		self.assertEqual(row["active"], 0)

	def _bao_dam_co_phat_sinh(self, vat_tu):
		if vat_tu_mod.co_phat_sinh(vat_tu):
			return
		doc = frappe.get_doc({
			"doctype": "Customer Stock Receipt",
			"kho": self.kho_bm,
			"ngay": frappe.utils.today(),
			"loai_nhap": "Nhập khác",
			"items": [{
				"vat_tu": vat_tu, "so_lo": "LO-TEST-PS",
				"so_luong": 5, "don_gia": 1000,
			}],
		})
		doc.insert(ignore_permissions=True)
		doc.submit()
```

- [ ] **Step 2: Chạy để xác nhận đỏ**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_vat_tu`
Expected: FAIL — `ModuleNotFoundError: No module named 'miyano_portal.kho.vat_tu'`

- [ ] **Step 3: Viết `kho/vat_tu.py`**

```python
"""Danh mục vật tư của kho khách hàng — tạo, sửa có rào, đọc/ghi file.

Tầng này KHÔNG biết gì về phiên đăng nhập: `kho` luôn do nơi gọi (api/kho.py)
truyền vào sau khi đã resolve từ phiên, đúng khuôn ledger.py / reports.py /
import_ton_dau.py.

Hai rào của module này tồn tại vì sổ kho không quy đổi đơn vị và không sửa
được quá khứ:
  * `dvt` và `ma_vat_tu` khoá lại khi vật tư đã có dòng sổ — đổi ĐVT làm tồn
    133 Hộp đọc thành 133 Cái mà không có gì tự lộ ra.
  * không tắt được vật tư còn tồn — nó sẽ biến mất khỏi ô chọn (danh sách lọc
    active=1) trong khi báo cáo tồn vẫn hiện số của nó.
"""

import frappe

from miyano_portal.kho import ledger
from miyano_portal.kho.import_ton_dau import _match_vat_tu, _norm

# Trường DUY NHẤT được nhận từ client. Không bao giờ doc.update(payload):
# `kho` phải đến từ phiên, và `item_code` phải do server suy ra (xem _item_miyano).
TRUONG_NHAN_TU_CLIENT = ("ma_vat_tu", "ten_vat_tu", "dvt", "quy_cach", "nhom", "ghi_chu")

# Sửa được kể cả khi đã có phát sinh — chúng chỉ là mô tả, không tham gia phép cộng nào.
TRUONG_MO_TA = ("ten_vat_tu", "quy_cach", "nhom", "ghi_chu")

# Khoá lại khi đã có phát sinh.
TRUONG_KHOA = ("ma_vat_tu", "dvt")

_NHAN = {"ma_vat_tu": "Mã vật tư", "dvt": "ĐVT"}


def co_phat_sinh(vat_tu: str) -> bool:
	return bool(frappe.db.exists("Customer Stock Ledger Entry", {"vat_tu": vat_tu}))


def cac_vat_tu_co_phat_sinh(kho: str) -> set[str]:
	"""Bản gộp của co_phat_sinh() cho cả một kho — MỘT truy vấn cho toàn danh
	mục, không phải mỗi vật tư một truy vấn (kho_vat_tu_list gọi nó trên mọi
	lần mở màn phiếu)."""
	rows = frappe.db.sql(
		"select distinct vat_tu from `tabCustomer Stock Ledger Entry` where kho=%s", (kho,)
	)
	return {r[0] for r in rows}


def _item_miyano(ma_vat_tu: str) -> str | None:
	"""item_code thật của Miyano nếu mã trùng, theo đúng chính tả trong DB."""
	row = frappe.db.sql(
		"select item_code from `tabItem` where lower(item_code)=%s limit 1",
		(ma_vat_tu.strip().lower(),),
	)
	return row[0][0] if row else None


def ra_dict(name: str, da_co: bool = False) -> dict:
	row = frappe.db.get_value(
		"Customer Warehouse Item", name,
		["name", "ma_vat_tu", "ten_vat_tu", "dvt", "item_code",
		 "quy_cach", "nhom", "ghi_chu", "active"],
		as_dict=True,
	)
	row["item_code"] = row["item_code"] or ""
	row["quy_cach"] = row["quy_cach"] or ""
	row["nhom"] = row["nhom"] or ""
	row["ghi_chu"] = row["ghi_chu"] or ""
	row["active"] = int(row["active"] or 0)
	row["co_phat_sinh"] = co_phat_sinh(name)
	# `da_co` cho giao diện biết đây là vật tư đã tồn tại chứ không phải vừa
	# tạo — nút "Tạo vật tư" ở dòng thứ hai cùng mã không được báo lỗi.
	row["da_co"] = da_co
	return row


def tao(kho: str, du_lieu: dict) -> dict:
	ma = _norm(du_lieu.get("ma_vat_tu"))
	ten = _norm(du_lieu.get("ten_vat_tu"))
	dvt = _norm(du_lieu.get("dvt"))
	if not ma:
		frappe.throw("Thiếu Mã vật tư.", frappe.ValidationError)
	if not ten:
		frappe.throw("Thiếu Tên vật tư.", frappe.ValidationError)
	if not dvt:
		frappe.throw("Thiếu ĐVT.", frappe.ValidationError)

	# Kiểm TRƯỚC, không bắt ValidationError của controller: bắt ngoại lệ giữa
	# một transaction đang mở là cách chắc chắn để lại trạng thái nửa vời.
	match_type, item_code, vat_tu_name = _match_vat_tu(kho, ma)
	if match_type == "existing":
		return ra_dict(vat_tu_name, da_co=True)

	doc = frappe.get_doc({
		"doctype": "Customer Warehouse Item",
		"kho": kho,
		# Mã khớp Item của Miyano thì lấy chính tả chuẩn trong hệ thống Miyano,
		# không lấy cách khách gõ.
		"ma_vat_tu": item_code or ma,
		"ten_vat_tu": ten,
		"dvt": dvt,
		"active": 1,
		"item_code": item_code or None,
		"quy_cach": _norm(du_lieu.get("quy_cach")) or None,
		"nhom": _norm(du_lieu.get("nhom")) or None,
		"ghi_chu": _norm(du_lieu.get("ghi_chu")) or None,
	})
	doc.insert(ignore_permissions=True)
	return ra_dict(doc.name)


def _chan_tat_khi_con_ton(doc) -> None:
	ton = sum(float(r["so_luong"]) for r in ledger.get_lot_balances(doc.kho, doc.name))
	if ton > ledger.EPS:
		frappe.throw(
			f"Vật tư {doc.ma_vat_tu} còn tồn {ton:g} {doc.dvt or ''}. "
			"Hãy xuất hết trước khi ngừng dùng.",
			frappe.ValidationError,
		)


def sua(kho: str, vat_tu: str, du_lieu: dict) -> dict:
	"""Nơi gọi PHẢI kiểm `vat_tu` thuộc `kho` trước (api/kho.py._vat_tu_cua_kho)."""
	doc = frappe.get_doc("Customer Warehouse Item", vat_tu)
	da_phat_sinh = co_phat_sinh(vat_tu)
	ma_cu = doc.ma_vat_tu

	for truong in TRUONG_MO_TA:
		if truong in du_lieu:
			setattr(doc, truong, _norm(du_lieu.get(truong)) or None)
	if not doc.ten_vat_tu:
		frappe.throw("Thiếu Tên vật tư.", frappe.ValidationError)

	for truong in TRUONG_KHOA:
		if truong not in du_lieu:
			continue
		gia_tri = _norm(du_lieu.get(truong))
		if gia_tri == _norm(getattr(doc, truong)):
			continue  # gửi lên giá trị y hệt thì không tính là sửa
		if da_phat_sinh:
			frappe.throw(
				f"{_NHAN[truong]} không sửa được vì vật tư {ma_cu} đã có phát sinh "
				"trong sổ kho. Số liệu cũ đã tính theo giá trị hiện tại và hệ thống "
				"không quy đổi.",
				frappe.ValidationError,
			)
		if not gia_tri:
			frappe.throw(f"Thiếu {_NHAN[truong]}.", frappe.ValidationError)
		setattr(doc, truong, gia_tri)

	if doc.ma_vat_tu != ma_cu:
		# Mã mới có thể trùng một Item của Miyano, hoặc thôi không trùng nữa.
		doc.item_code = _item_miyano(doc.ma_vat_tu)

	if "active" in du_lieu:
		active = 1 if frappe.utils.cint(du_lieu.get("active")) else 0
		if not active and doc.active:
			_chan_tat_khi_con_ton(doc)
		doc.active = active

	doc.save(ignore_permissions=True)
	return ra_dict(doc.name)
```

- [ ] **Step 4: Chạy test, phải xanh**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_vat_tu`
Expected: PASS (11 ca)

- [ ] **Step 5: Commit**

```bash
git add miyano_portal/kho/vat_tu.py miyano_portal/tests/test_kho_vat_tu.py
git commit -m "feat(kho): danh mục vật tư — tạo và sửa có rào theo phát sinh sổ"
```

---

## Task 3: Endpoint tạo/sửa vật tư + mở rộng `kho_vat_tu_list`

**Files:**
- Modify: `miyano_portal/api/kho.py:215-232` (`kho_vat_tu_list`) và thêm hai endpoint ngay sau nó
- Test: `miyano_portal/tests/test_kho_vat_tu.py` (thêm class)

**Interfaces:**
- Consumes: `vat_tu.tao/sua/cac_vat_tu_co_phat_sinh`, `_parse_payload`, `_vat_tu_cua_kho`, `_so_nguyen`, `_phieu_action`
- Produces:
  - `kho_vat_tu_tao(payload) -> dict`
  - `kho_vat_tu_sua(name, payload) -> dict`
  - `kho_vat_tu_list(tim=None, ca_tat=0) -> list` — mỗi dòng thêm `quy_cach, nhom, ghi_chu, active, co_phat_sinh`

- [ ] **Step 1: Viết test thất bại**

Thêm vào cuối `miyano_portal/tests/test_kho_vat_tu.py`:

```python
from miyano_portal.api import kho as kho_api

BM_USER = "bvbm@demo.miyano"
PXN_USER = "pxnabc@demo.miyano"


class TestVatTuEndpoint(FrappeTestCase):
	def setUp(self):
		self.kho = seed_kho_demo()
		frappe.set_user(BM_USER)
		self._da_tao = []

	def tearDown(self):
		frappe.set_user("Administrator")
		for name in self._da_tao:
			if frappe.db.exists("Customer Warehouse Item", name):
				frappe.delete_doc("Customer Warehouse Item", name, force=True, ignore_permissions=True)

	def test_tao_qua_endpoint_gan_vao_kho_cua_phien(self):
		row = kho_api.kho_vat_tu_tao({
			"ma_vat_tu": "BM-API-01", "ten_vat_tu": "Vật tư API", "dvt": "Cái",
		})
		self._da_tao.append(row["name"])
		self.assertEqual(
			frappe.db.get_value("Customer Warehouse Item", row["name"], "kho"),
			self.kho["kho_bm"],
		)

	def test_khong_sua_duoc_vat_tu_cua_kho_khac(self):
		with self.assertRaises(frappe.PermissionError):
			kho_api.kho_vat_tu_sua(self.kho["vt_pxn"], {"ten_vat_tu": "Đổi trộm"})

	def test_list_tra_them_co_phat_sinh_va_active(self):
		rows = kho_api.kho_vat_tu_list()
		self.assertTrue(rows)
		for r in rows:
			self.assertIn("co_phat_sinh", r)
			self.assertIn("active", r)
			self.assertIn("quy_cach", r)

	def test_list_mac_dinh_chi_tra_vat_tu_dang_dung(self):
		row = kho_api.kho_vat_tu_tao({
			"ma_vat_tu": "BM-TAT-01", "ten_vat_tu": "Sẽ tắt", "dvt": "Cái",
		})
		self._da_tao.append(row["name"])
		kho_api.kho_vat_tu_sua(row["name"], {"active": 0})
		self.assertNotIn(row["name"], [r["name"] for r in kho_api.kho_vat_tu_list()])
		self.assertIn(row["name"], [r["name"] for r in kho_api.kho_vat_tu_list(ca_tat=1)])

	def test_tim_loc_theo_ma_va_ten(self):
		rows = kho_api.kho_vat_tu_list(tim="glove")
		self.assertTrue(rows)
		self.assertTrue(all("glove" in f"{r['ma_vat_tu']} {r['ten_vat_tu']}".lower() for r in rows))
```

- [ ] **Step 2: Chạy để xác nhận đỏ**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_vat_tu`
Expected: FAIL — `AttributeError: module 'miyano_portal.api.kho' has no attribute 'kho_vat_tu_tao'`

- [ ] **Step 3: Sửa `api/kho.py`**

Thêm import ở đầu file, cạnh các import `kho` khác:

```python
from miyano_portal.kho import vat_tu as vat_tu_mod
```

Thay trọn `kho_vat_tu_list` (`:215-232`) bằng:

```python
@frappe.whitelist()
def kho_vat_tu_list(tim=None, ca_tat=0) -> list:
	"""Danh mục vật tư của kho — nguồn cho ô chọn vật tư ở hai màn phiếu VÀ
	cho màn danh mục.

	`ca_tat` CỐ Ý không có type hint (xem _so_nguyen): tham số số có type hint
	bị lớp typing của Frappe chặn bằng thông điệp tiếng Anh trước khi hàm chạy.
	Mặc định 0 nên hành vi cũ (chỉ trả vật tư đang dùng) giữ nguyên cho hai màn
	phiếu vốn gọi hàm này không tham số.
	"""
	kho = get_portal_kho()
	filters = {"kho": kho}
	if not _so_nguyen(ca_tat, "Tham số hiển thị vật tư đã tắt", 0):
		filters["active"] = 1
	rows = frappe.get_all(
		"Customer Warehouse Item",
		filters=filters,
		fields=["name", "ma_vat_tu", "ten_vat_tu", "dvt", "item_code",
		        "quy_cach", "nhom", "ghi_chu", "active"],
		order_by="ten_vat_tu asc",
	)
	if tim:
		hay = str(tim).strip().lower()
		rows = [r for r in rows if hay in f"{r['ma_vat_tu']} {r['ten_vat_tu']}".lower()]
	# MỘT truy vấn cho cả danh mục, không phải mỗi dòng một truy vấn.
	co_ps = vat_tu_mod.cac_vat_tu_co_phat_sinh(kho)
	for r in rows:
		r["item_code"] = r["item_code"] or ""
		r["quy_cach"] = r["quy_cach"] or ""
		r["nhom"] = r["nhom"] or ""
		r["ghi_chu"] = r["ghi_chu"] or ""
		r["active"] = int(r["active"] or 0)
		r["co_phat_sinh"] = r["name"] in co_ps
	return rows


@frappe.whitelist()
@_phieu_action
def kho_vat_tu_tao(payload) -> dict:
	"""Tạo một vật tư trong kho của người gọi.

	`kho` lấy từ phiên; `item_code` KHÔNG nhận từ client mà do vat_tu.tao() tự
	suy từ mã — nhận item_code từ client cho phép khách nối vật tư của mình vào
	một mặt hàng Miyano bất kỳ, và từ đó hook Delivery Note cộng hàng vào đúng
	dòng danh mục sai đó.
	"""
	kho = get_portal_kho()
	return vat_tu_mod.tao(kho, _parse_payload(payload))


@frappe.whitelist()
@_phieu_action
def kho_vat_tu_sua(name: str, payload) -> dict:
	kho = get_portal_kho()
	_vat_tu_cua_kho(name, kho)
	return vat_tu_mod.sua(kho, name, _parse_payload(payload))
```

- [ ] **Step 4: Chạy test, phải xanh**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_vat_tu`
Expected: PASS (16 ca)

- [ ] **Step 5: Chạy lại toàn bộ test kho để chắc `kho_vat_tu_list` mở rộng không phá gì**

Run: `bench --site erptest.local run-tests --app miyano_portal`
Expected: chỉ còn đúng ca đỏ đã biết từ trước (`test_ma_kho_unique_across_customers`, đỏ vì site có sẵn kho của khách Himedic). Bất kỳ ca đỏ nào khác là do thay đổi này.

- [ ] **Step 6: Commit**

```bash
git add miyano_portal/api/kho.py miyano_portal/tests/test_kho_vat_tu.py
git commit -m "feat(kho): endpoint tạo/sửa vật tư, kho_vat_tu_list trả thêm trạng thái"
```

---

## Task 4: Modal tạo/sửa vật tư + nút "➕ Tạo vật tư mới…" trong hai màn phiếu

**Files:**
- Create: `frontend/src/components/VatTuModal.vue`
- Modify: `frontend/src/views/PhieuNhapDetail.vue`, `frontend/src/views/PhieuXuatDetail.vue`

**Interfaces:**
- Consumes: `api.callKho('kho_vat_tu_tao' | 'kho_vat_tu_sua')`
- Produces: component `VatTuModal` — props `open: Boolean`, `initial: Object`, `mode: 'tao'|'sua'`, `vatTu: String`; emits `saved(row)` và `close`

- [ ] **Step 1: Tạo component**

`frontend/src/components/VatTuModal.vue`:

```vue
<script setup>
import { ref, watch, computed } from 'vue'
import api from '../api'
import { showToast } from '../toast'
import { useIsMobile } from '../useMobile'

const props = defineProps({
  open: { type: Boolean, default: false },
  // Giá trị điền sẵn — khi mở từ một dòng import thì đây là dữ liệu đọc từ file.
  initial: { type: Object, default: () => ({}) },
  mode: { type: String, default: 'tao' }, // 'tao' | 'sua'
  vatTu: { type: String, default: '' },
  coPhatSinh: { type: Boolean, default: false },
})
const emit = defineEmits(['saved', 'close'])

const isMobile = useIsMobile()
const saving = ref(false)
const form = ref({ ma_vat_tu: '', ten_vat_tu: '', dvt: '', quy_cach: '', nhom: '', ghi_chu: '', active: 1 })

watch(
  () => props.open,
  (v) => {
    if (!v) return
    form.value = {
      ma_vat_tu: '', ten_vat_tu: '', dvt: '', quy_cach: '', nhom: '', ghi_chu: '', active: 1,
      ...props.initial,
    }
  },
  { immediate: true }
)

// Mã và ĐVT khoá lại khi vật tư đã có dòng sổ: số liệu cũ đã tính theo giá trị
// hiện tại và hệ thống không quy đổi. Backend chặn lần nữa — đây chỉ là lớp
// hiển thị để người dùng biết TRƯỚC KHI gõ, kèm lý do đọc được.
const khoa = computed(() => props.mode === 'sua' && props.coPhatSinh)

async function onSave() {
  if (saving.value) return
  saving.value = true
  try {
    const payload = { ...form.value }
    const row =
      props.mode === 'sua'
        ? await api.callKho('kho_vat_tu_sua', { name: props.vatTu, payload })
        : await api.callKho('kho_vat_tu_tao', { payload })
    showToast(row.da_co ? `Mã ${row.ma_vat_tu} đã có sẵn — đã chọn vật tư đó.` : 'Đã lưu vật tư.')
    emit('saved', row)
  } catch (e) {
    showToast(e.message || 'Không lưu được vật tư.', 'error')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div v-if="open" :class="isMobile ? 'sheet' : 'modal'" @click.self="emit('close')">
    <div class="card">
      <h3>{{ mode === 'sua' ? 'Sửa vật tư' : 'Tạo vật tư mới' }}</h3>

      <div class="field">
        <label>Mã vật tư *</label>
        <input v-model="form.ma_vat_tu" :disabled="khoa" placeholder="VD: BV-KIM-22G" />
        <p v-if="khoa" class="tag">🔒 Vật tư đã có phát sinh trong sổ — không đổi được mã.</p>
      </div>
      <div class="field">
        <label>Tên vật tư *</label>
        <input v-model="form.ten_vat_tu" />
      </div>
      <div class="field">
        <label>ĐVT *</label>
        <input v-model="form.dvt" :disabled="khoa" placeholder="VD: Hộp" />
        <p v-if="khoa" class="tag">🔒 Đã có phát sinh — đổi ĐVT sẽ làm sai số tồn cũ.</p>
      </div>
      <div class="grid2">
        <div class="field"><label>Quy cách</label><input v-model="form.quy_cach" /></div>
        <div class="field"><label>Nhóm</label><input v-model="form.nhom" /></div>
      </div>
      <div class="field"><label>Ghi chú</label><input v-model="form.ghi_chu" /></div>
      <div v-if="mode === 'sua'" class="field">
        <label style="display: flex; align-items: center; gap: 6px">
          <input type="checkbox" :checked="form.active === 1" @change="form.active = $event.target.checked ? 1 : 0" />
          Đang dùng
        </label>
      </div>

      <div class="flex" style="justify-content: flex-end; margin-top: 14px; gap: 8px">
        <button class="btn-o" @click="emit('close')">Huỷ</button>
        <button class="btn" :disabled="saving" @click="onSave">
          {{ saving ? 'Đang lưu…' : 'Lưu' }}
        </button>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: Nối vào `PhieuNhapDetail.vue`**

Trong `<script setup>`, thêm import và trạng thái:

```js
import VatTuModal from '../components/VatTuModal.vue'

const MUC_TAO_MOI = '__tao_moi__'
const modalOpen = ref(false)
const modalInitial = ref({})
const modalRowIdx = ref(-1)

// Chọn "➕ Tạo vật tư mới…" trong ô chọn: mở modal cho ĐÚNG dòng đó và trả ô
// chọn về rỗng, để dòng không bị kẹt ở một giá trị không phải vật tư nào.
function onVatTuSelect(row, idx) {
  if (row.vat_tu !== MUC_TAO_MOI) return
  row.vat_tu = ''
  modalRowIdx.value = idx
  modalInitial.value = { ma_vat_tu: row._ma_vat_tu || '', ten_vat_tu: '', dvt: '' }
  modalOpen.value = true
}

function onVatTuSaved(vt) {
  // Cập nhật danh mục trong bộ nhớ TRƯỚC khi gán vào dòng, để mọi dòng khác
  // cùng mã cũng khớp được ngay mà không phải tải lại danh mục.
  if (!vatTuList.value.some((v) => v.name === vt.name)) vatTuList.value.push(vt)
  if (modalRowIdx.value >= 0) {
    const row = doc.items[modalRowIdx.value]
    row.vat_tu = vt.name
    row._trang_thai = 'khop'
    row._loi = []
  }
  modalOpen.value = false
  modalRowIdx.value = -1
}
```

Trong `<template>`, thêm mục cuối vào ô chọn vật tư (ngay sau vòng `v-for` các option) và gắn `@change`:

```html
<select v-if="editable" v-model="r.vat_tu" style="width: 100%" @change="onVatTuSelect(r, idx)">
  <option value="" disabled>-- Chọn vật tư --</option>
  <option v-for="v in vatTuList" :key="v.name" :value="v.name">
    {{ v.ma_vat_tu }} — {{ v.ten_vat_tu }}
  </option>
  <option :value="MUC_TAO_MOI">➕ Tạo vật tư mới…</option>
</select>
```

Và đặt modal ngay trước thẻ đóng của `<template v-else>`:

```html
<VatTuModal
  :open="modalOpen"
  :initial="modalInitial"
  mode="tao"
  @saved="onVatTuSaved"
  @close="modalOpen = false"
/>
```

- [ ] **Step 3: Làm y hệt cho `PhieuXuatDetail.vue`**

Cùng import, cùng bốn hàm, cùng hai đoạn template. Khác một điểm: sau khi gán vật tư mới vào dòng, phải nạp lô cho dòng đó như khi người dùng đổi ô chọn — thêm vào cuối `onVatTuSaved`:

```js
  // Vật tư vừa tạo chưa có lô nào; vẫn gọi để dòng đi qua đúng đường nạp lô
  // như mọi dòng khác, và để cảnh báo "chưa có tồn" hiện ra từ chính dữ liệu
  // trả về chứ không phải từ một suy đoán của giao diện.
  if (modalRowIdx.value >= 0) onVatTuChange(doc.items[modalRowIdx.value])
```

(Thứ tự: gọi trước khi đặt lại `modalRowIdx.value = -1`.)

- [ ] **Step 4: Build và kiểm chứng trên trình duyệt**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench build --app miyano_portal
```
Expected: build xong, không lỗi.

Rồi mở `http://192.168.61.129:8003/portal/kho/nhap`, đăng nhập `bvminhduc@demo.miyano` / `Portal@123`, bấm **+ Tạo phiếu nhập** → ở ô Vật tư chọn **➕ Tạo vật tư mới…** → điền `BV-TEST-01` / `Vật tư thử` / `Cái` → Lưu. Kỳ vọng: modal đóng, ô chọn của đúng dòng đó hiển thị vật tư vừa tạo. Làm lại tương tự ở `/portal/kho/xuat`, kỳ vọng thêm: cột Lô hiện *"Vật tư này chưa còn tồn lô nào."*

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/VatTuModal.vue frontend/src/views/PhieuNhapDetail.vue frontend/src/views/PhieuXuatDetail.vue
git commit -m "feat(portal): tạo nhanh vật tư ngay trong ô chọn của phiếu nhập/xuất"
```

---

## Task 5: `kho/vat_tu.py` — export, preview và commit file danh mục

**Files:**
- Modify: `miyano_portal/kho/vat_tu.py` (thêm phần file vào cuối)
- Test: `miyano_portal/tests/test_kho_vat_tu_import.py`

**Interfaces:**
- Consumes: `import_ton_dau.mo_workbook/read_header/_cell_value/_norm/_match_vat_tu`, `reports.build_xlsx`, `ledger.get_lot_balances/EPS`
- Produces:
  - `DANH_MUC_COLUMNS: list[tuple[str, str]]`, `DANH_MUC_REQUIRED: set[str]`
  - `export_rows(kho: str) -> list[dict]`
  - `build_danh_muc_xlsx(kho: str) -> bytes`
  - `parse_danh_muc(content: bytes, kho: str) -> dict` — `{total, ok_count, error_count, summary: {tao_moi, cap_nhat}, rows_ok, rows_error}`
  - `commit_danh_muc(content: bytes, kho: str) -> dict` — `{tao_moi, cap_nhat}`

- [ ] **Step 1: Viết test thất bại**

Tạo `miyano_portal/tests/test_kho_vat_tu_import.py`:

```python
"""Import/export danh mục vật tư qua cổng."""

import io

import frappe
from frappe.tests.utils import FrappeTestCase
from openpyxl import Workbook, load_workbook

from miyano_portal.kho import vat_tu as vat_tu_mod
from miyano_portal.setup.seed_kho_demo import seed_kho_demo

HEADERS = [label for label, _ in vat_tu_mod.DANH_MUC_COLUMNS]


def _xlsx(rows, headers=None):
	wb = Workbook()
	ws = wb.active
	ws.append(headers if headers is not None else HEADERS)
	for r in rows:
		ws.append(r)
	buf = io.BytesIO()
	wb.save(buf)
	return buf.getvalue()


class TestDanhMucFile(FrappeTestCase):
	def setUp(self):
		self.kho = seed_kho_demo()
		self.kho_bm = self.kho["kho_bm"]
		self._da_tao = []

	def tearDown(self):
		for name in self._da_tao:
			if frappe.db.exists("Customer Warehouse Item", name):
				frappe.delete_doc("Customer Warehouse Item", name, force=True, ignore_permissions=True)

	def test_preview_khong_ghi_gi(self):
		truoc = frappe.db.count("Customer Warehouse Item", {"kho": self.kho_bm})
		vat_tu_mod.parse_danh_muc(
			_xlsx([["BM-NEW-01", "Vật tư mới", "Cái", "", "", "", 1]]), self.kho_bm
		)
		self.assertEqual(frappe.db.count("Customer Warehouse Item", {"kho": self.kho_bm}), truoc)

	def test_ma_moi_thi_tao_ma_da_co_thi_cap_nhat(self):
		content = _xlsx([
			["BM-NEW-02", "Vật tư mới 2", "Cái", "", "Gói 10", "Tiêu hao", 1],
			["MYN-GLOVE-M", "Găng tay ĐỔI TÊN", "Hộp", "", "", "", 1],
		])
		parsed = vat_tu_mod.parse_danh_muc(content, self.kho_bm)
		self.assertEqual(parsed["error_count"], 0)
		self.assertEqual(parsed["summary"], {"tao_moi": 1, "cap_nhat": 1})

		kq = vat_tu_mod.commit_danh_muc(content, self.kho_bm)
		moi = frappe.db.get_value("Customer Warehouse Item", {"kho": self.kho_bm, "ma_vat_tu": "BM-NEW-02"})
		self._da_tao.append(moi)
		self.assertEqual(kq, {"tao_moi": 1, "cap_nhat": 1})
		self.assertEqual(
			frappe.db.get_value("Customer Warehouse Item", self.kho["vt_bm"], "ten_vat_tu"),
			"Găng tay ĐỔI TÊN",
		)

	def test_mot_dong_loi_thi_khong_ghi_gi(self):
		truoc = frappe.db.count("Customer Warehouse Item", {"kho": self.kho_bm})
		content = _xlsx([
			["BM-NEW-03", "Hợp lệ", "Cái", "", "", "", 1],
			["", "Thiếu mã", "Cái", "", "", "", 1],
		])
		with self.assertRaises(frappe.ValidationError):
			vat_tu_mod.commit_danh_muc(content, self.kho_bm)
		self.assertEqual(frappe.db.count("Customer Warehouse Item", {"kho": self.kho_bm}), truoc)

	def test_doi_dvt_vat_tu_da_phat_sinh_la_dong_loi(self):
		self._bao_dam_co_phat_sinh(self.kho["vt_bm"])
		parsed = vat_tu_mod.parse_danh_muc(
			_xlsx([["MYN-GLOVE-M", "Găng tay y tế size M", "Cái", "", "", "", 1]]), self.kho_bm
		)
		self.assertEqual(parsed["error_count"], 1)
		self.assertIn("ĐVT", " ".join(parsed["rows_error"][0]["errors"]))

	def test_tat_vat_tu_con_ton_la_dong_loi(self):
		self._bao_dam_co_phat_sinh(self.kho["vt_bm"])
		parsed = vat_tu_mod.parse_danh_muc(
			_xlsx([["MYN-GLOVE-M", "Găng tay y tế size M", "Hộp", "", "", "", 0]]), self.kho_bm
		)
		self.assertEqual(parsed["error_count"], 1)
		self.assertIn("còn tồn", " ".join(parsed["rows_error"][0]["errors"]))

	def test_round_trip_xuat_roi_nap_lai_khong_doi_du_lieu(self):
		content = vat_tu_mod.build_danh_muc_xlsx(self.kho_bm)
		ws = load_workbook(io.BytesIO(content), data_only=True).active
		self.assertEqual([c.value for c in ws[1]], HEADERS)
		parsed = vat_tu_mod.parse_danh_muc(content, self.kho_bm)
		self.assertEqual(parsed["error_count"], 0)
		self.assertEqual(parsed["summary"]["tao_moi"], 0)

	def _bao_dam_co_phat_sinh(self, vat_tu):
		if vat_tu_mod.co_phat_sinh(vat_tu):
			return
		doc = frappe.get_doc({
			"doctype": "Customer Stock Receipt",
			"kho": self.kho_bm,
			"ngay": frappe.utils.today(),
			"loai_nhap": "Nhập khác",
			"items": [{"vat_tu": vat_tu, "so_lo": "LO-DM-01", "so_luong": 5, "don_gia": 1000}],
		})
		doc.insert(ignore_permissions=True)
		doc.submit()
```

- [ ] **Step 2: Chạy để xác nhận đỏ**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_vat_tu_import`
Expected: FAIL — `AttributeError: module 'miyano_portal.kho.vat_tu' has no attribute 'DANH_MUC_COLUMNS'`

- [ ] **Step 3: Thêm phần file vào `kho/vat_tu.py`**

```python
# --------------------------------------------------------------------------
# File danh mục: export → sửa → nạp lại. MỘT bộ cột duy nhất cho cả ba việc
# (xuất, mẫu, đọc), đúng nguyên tắc round-tripping-spreadsheets.
# --------------------------------------------------------------------------

DANH_MUC_COLUMNS = [
	("Mã vật tư", "ma_vat_tu"),
	("Tên vật tư", "ten_vat_tu"),
	("ĐVT", "dvt"),
	("Mã hàng Miyano", "item_code"),
	("Quy cách", "quy_cach"),
	("Nhóm", "nhom"),
	("Đang dùng", "active"),
]

# Cột phải CÓ MẶT trong header. `item_code` không nằm đây vì nó chỉ đọc:
# xuất ra cho khách đối chiếu, nạp vào thì bỏ qua (server tự suy từ mã).
DANH_MUC_REQUIRED = {"ma_vat_tu", "ten_vat_tu", "dvt"}

_TRUE_VALUES = {"1", "x", "co", "có", "true", "yes", "y", "dang dung", "đang dùng"}
_FALSE_VALUES = {"", "0", "khong", "không", "false", "no", "n", "tat", "tắt"}


def _coerce_bool(value) -> tuple[int | None, str | None]:
	"""Cột 'Đang dùng': nhận 1/0, x, có/không, true/false. Trống = đang dùng."""
	if value in (None, ""):
		return 1, None
	if isinstance(value, bool):
		return int(value), None
	if isinstance(value, (int, float)):
		return int(bool(value)), None
	s = _norm(value).lower()
	if s in _TRUE_VALUES:
		return 1, None
	if s in _FALSE_VALUES:
		return 0, None
	return None, f"Cột 'Đang dùng' không hợp lệ: '{value}' (dùng 1/0 hoặc x/trống)"


def export_rows(kho: str) -> list[dict]:
	rows = frappe.get_all(
		"Customer Warehouse Item",
		filters={"kho": kho},
		fields=["ma_vat_tu", "ten_vat_tu", "dvt", "item_code", "quy_cach", "nhom", "active"],
		order_by="ma_vat_tu asc",
	)
	for r in rows:
		r["item_code"] = r["item_code"] or ""
		r["quy_cach"] = r["quy_cach"] or ""
		r["nhom"] = r["nhom"] or ""
		r["active"] = int(r["active"] or 0)
	return rows


def build_danh_muc_xlsx(kho: str) -> bytes:
	from miyano_portal.kho import reports

	return reports.build_xlsx(DANH_MUC_COLUMNS, export_rows(kho), "Danh muc vat tu")


def _ton_cua(kho: str, vat_tu: str) -> float:
	return sum(float(r["so_luong"]) for r in ledger.get_lot_balances(kho, vat_tu))


def parse_danh_muc(content: bytes, kho: str) -> dict:
	"""Đọc và validate toàn bộ file danh mục, KHÔNG GHI GÌ.

	Mỗi dòng ra một trong hai hành động: `tao_moi` (mã chưa có) hoặc `cap_nhat`
	(mã đã có). Rào §4.2/§4.3 của thiết kế được kiểm NGAY Ở ĐÂY chứ không để
	đến lúc ghi, để dòng vi phạm hiện thành dòng lỗi trong bản xem trước thay
	vì một thay đổi bị bỏ qua im lặng.
	"""
	from miyano_portal.kho.import_ton_dau import _cell_value, mo_workbook, read_header

	ws = mo_workbook(content)
	header_row, col_index = read_header(ws, DANH_MUC_COLUMNS, DANH_MUC_REQUIRED)

	rows_ok: list[dict] = []
	rows_error: list[dict] = []

	for line, row_cells in enumerate(
		ws.iter_rows(min_row=header_row + 1, max_row=ws.max_row), start=header_row + 1
	):
		raw = {field: _cell_value(row_cells, col) for field, col in col_index.items()}
		if all(v is None or (isinstance(v, str) and not v.strip()) for v in raw.values()):
			continue

		errors: list[str] = []
		ma = _norm(raw.get("ma_vat_tu"))
		ten = _norm(raw.get("ten_vat_tu"))
		dvt = _norm(raw.get("dvt"))
		if not ma:
			errors.append("Thiếu Mã vật tư")
		if not ten:
			errors.append("Thiếu Tên vật tư")
		if not dvt:
			errors.append("Thiếu ĐVT")

		active, bool_err = _coerce_bool(raw.get("active"))
		if bool_err:
			errors.append(bool_err)

		vat_tu_name = None
		hanh_dong = "tao_moi"
		if ma and not errors:
			match_type, item_code, vat_tu_name = _match_vat_tu(kho, ma)
			if match_type == "existing":
				hanh_dong = "cap_nhat"
				hien = frappe.db.get_value(
					"Customer Warehouse Item", vat_tu_name, ["dvt", "active"], as_dict=True
				)
				if _fold_khac(hien.dvt, dvt) and co_phat_sinh(vat_tu_name):
					errors.append(
						f"ĐVT không sửa được: {ma} đã có phát sinh trong sổ "
						f"(ĐVT hiện tại: {hien.dvt})"
					)
				if active == 0 and int(hien.active or 0) == 1:
					ton = _ton_cua(kho, vat_tu_name)
					if ton > ledger.EPS:
						errors.append(f"Không tắt được: {ma} còn tồn {ton:g} {hien.dvt or ''}")

		if errors:
			rows_error.append({"line": line, "ma_vat_tu": ma or f"(dòng {line})", "errors": errors})
			continue

		rows_ok.append({
			"line": line, "ma_vat_tu": ma, "ten_vat_tu": ten, "dvt": dvt,
			"quy_cach": _norm(raw.get("quy_cach")), "nhom": _norm(raw.get("nhom")),
			"active": active, "hanh_dong": hanh_dong, "vat_tu": vat_tu_name,
		})

	summary = {"tao_moi": 0, "cap_nhat": 0}
	for r in rows_ok:
		summary[r["hanh_dong"]] += 1

	return {
		"total": len(rows_ok) + len(rows_error),
		"ok_count": len(rows_ok),
		"error_count": len(rows_error),
		"summary": summary,
		"rows_ok": rows_ok,
		"rows_error": rows_error,
	}


def _fold_khac(a, b) -> bool:
	return _norm(a).lower() != _norm(b).lower()


def commit_danh_muc(content: bytes, kho: str) -> dict:
	"""Đọc lại TỪ ĐẦU trên server rồi ghi. Tất-cả-hoặc-không."""
	parsed = parse_danh_muc(content, kho)
	if parsed["error_count"]:
		first = parsed["rows_error"][0]
		frappe.throw(
			f"Tệp có {parsed['error_count']} dòng lỗi trong tổng số {parsed['total']} dòng "
			f"(ví dụ dòng {first['line']}: {'; '.join(first['errors'])}). "
			"Vui lòng sửa và tải lại — chưa có dữ liệu nào được ghi.",
			frappe.ValidationError,
		)
	if not parsed["rows_ok"]:
		frappe.throw("Tệp không có dòng dữ liệu hợp lệ nào.", frappe.ValidationError)

	sp = "kho_danh_muc_commit_sp"
	frappe.db.savepoint(sp)
	try:
		for row in parsed["rows_ok"]:
			du_lieu = {
				"ma_vat_tu": row["ma_vat_tu"], "ten_vat_tu": row["ten_vat_tu"],
				"dvt": row["dvt"], "quy_cach": row["quy_cach"], "nhom": row["nhom"],
			}
			if row["hanh_dong"] == "tao_moi":
				tao(kho, du_lieu)
			else:
				sua(kho, row["vat_tu"], {**du_lieu, "active": row["active"]})
	except Exception:
		frappe.db.rollback(save_point=sp)
		raise

	return parsed["summary"]
```

- [ ] **Step 4: Chạy test, phải xanh**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_vat_tu_import`
Expected: PASS (6 ca)

- [ ] **Step 5: Commit**

```bash
git add miyano_portal/kho/vat_tu.py miyano_portal/tests/test_kho_vat_tu_import.py
git commit -m "feat(kho): export và import danh mục vật tư, tất-cả-hoặc-không"
```

---

## Task 6: Ba endpoint file danh mục

**Files:**
- Modify: `miyano_portal/api/kho.py` (thêm sau `kho_vat_tu_sua`)
- Test: `miyano_portal/tests/test_kho_vat_tu_import.py` (thêm class)

**Interfaces:**
- Consumes: `_resolve_owned_spreadsheet`, `vat_tu_mod.build_danh_muc_xlsx/parse_danh_muc/commit_danh_muc`
- Produces: `kho_vat_tu_export()`, `kho_vat_tu_import_preview(file_url)`, `kho_vat_tu_import_commit(file_url)`

- [ ] **Step 1: Viết test thất bại**

Thêm vào cuối `test_kho_vat_tu_import.py`:

```python
from miyano_portal.api import kho as kho_api

BM_USER = "bvbm@demo.miyano"


class TestDanhMucEndpoint(FrappeTestCase):
	def setUp(self):
		self.kho = seed_kho_demo()
		frappe.set_user(BM_USER)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_export_dat_response_dung_dinh_dang(self):
		kho_api.kho_vat_tu_export()
		self.assertEqual(frappe.local.response.filename, "danh_muc_vat_tu.xlsx")
		self.assertEqual(frappe.local.response.type, "download")
		self.assertTrue(frappe.local.response.filecontent)

	def test_preview_file_cua_nguoi_khac_bi_chan(self):
		f = frappe.get_doc({
			"doctype": "File", "file_name": "cua_nguoi_khac.xlsx",
			"content": "x", "is_private": 1,
		}).insert(ignore_permissions=True)
		frappe.db.set_value("File", f.name, "owner", "Administrator")
		with self.assertRaises(frappe.PermissionError):
			kho_api.kho_vat_tu_import_preview(f.file_url)
```

- [ ] **Step 2: Chạy để xác nhận đỏ**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_vat_tu_import`
Expected: FAIL — `AttributeError: … has no attribute 'kho_vat_tu_export'`

- [ ] **Step 3: Thêm ba endpoint**

```python
@frappe.whitelist()
def kho_vat_tu_export() -> None:
	kho = get_portal_kho()
	frappe.local.response.filename = "danh_muc_vat_tu.xlsx"
	frappe.local.response.filecontent = vat_tu_mod.build_danh_muc_xlsx(kho)
	frappe.local.response.type = "download"
	frappe.local.response.content_type = (
		"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
	)


@frappe.whitelist()
def kho_vat_tu_import_preview(file_url) -> dict:
	"""Đọc và phân tích file danh mục, KHÔNG GHI GÌ."""
	kho = get_portal_kho()
	content = _resolve_owned_spreadsheet(file_url)
	return vat_tu_mod.parse_danh_muc(content, kho)


@frappe.whitelist()
def kho_vat_tu_import_commit(file_url) -> dict:
	"""Đọc lại VÀ kiểm tra lại từ đầu ở server rồi mới ghi."""
	kho = get_portal_kho()
	content = _resolve_owned_spreadsheet(file_url)
	return vat_tu_mod.commit_danh_muc(content, kho)
```

- [ ] **Step 4: Chạy test, phải xanh**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_vat_tu_import`
Expected: PASS (8 ca)

- [ ] **Step 5: Commit**

```bash
git add miyano_portal/api/kho.py miyano_portal/tests/test_kho_vat_tu_import.py
git commit -m "feat(kho): endpoint export/import danh mục vật tư"
```

---

## Task 7: Màn danh mục vật tư trên cổng

**Files:**
- Create: `frontend/src/views/DanhMucVatTu.vue`, `frontend/src/views/ImportDanhMuc.vue`
- Modify: `frontend/src/router.js`, `frontend/src/views/Kho.vue`

**Interfaces:**
- Consumes: `kho_vat_tu_list`, `kho_vat_tu_sua`, `kho_vat_tu_export`, `kho_vat_tu_import_preview`, `kho_vat_tu_import_commit`, component `VatTuModal`

- [ ] **Step 1: Thêm hai route**

`frontend/src/router.js` — thêm import và hai mục vào mảng `routes`, ngay sau route `/kho/import`:

```js
import DanhMucVatTu from './views/DanhMucVatTu.vue'
import ImportDanhMuc from './views/ImportDanhMuc.vue'
```

```js
  { path: '/kho/vat-tu', name: 'kho-vat-tu', component: DanhMucVatTu, meta: { title: 'Danh mục vật tư' } },
  { path: '/kho/vat-tu/import', name: 'kho-vat-tu-import', component: ImportDanhMuc, meta: { title: 'Nhập danh mục vật tư' } },
```

- [ ] **Step 2: Thêm nút vào `Kho.vue`**

Ở CẢ HAI cụm nút (dòng ~108 và ~131 — bản desktop và bản mobile), thêm:

```html
<router-link to="/kho/vat-tu" class="btn-o btn-sm">Danh mục vật tư</router-link>
```

- [ ] **Step 3: Viết `DanhMucVatTu.vue`**

```vue
<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api'
import { showToast } from '../toast'
import { useIsMobile } from '../useMobile'
import VatTuModal from '../components/VatTuModal.vue'

const isMobile = useIsMobile()
const rows = ref([])
const loading = ref(true)
const error = ref('')
const tim = ref('')
const caTat = ref(false)

const modalOpen = ref(false)
const modalMode = ref('tao')
const modalInitial = ref({})
const modalVatTu = ref('')
const modalCoPhatSinh = ref(false)

const exportUrl = api.khoDownloadUrl('kho_vat_tu_export')

const hienThi = computed(() => {
  const q = tim.value.trim().toLowerCase()
  if (!q) return rows.value
  return rows.value.filter((r) => `${r.ma_vat_tu} ${r.ten_vat_tu}`.toLowerCase().includes(q))
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    rows.value = await api.callKho('kho_vat_tu_list', { ca_tat: caTat.value ? 1 : 0 })
  } catch (e) {
    error.value = e.message || 'Không tải được danh mục vật tư.'
  } finally {
    loading.value = false
  }
}

function moTao() {
  modalMode.value = 'tao'
  modalInitial.value = {}
  modalVatTu.value = ''
  modalCoPhatSinh.value = false
  modalOpen.value = true
}

function moSua(r) {
  modalMode.value = 'sua'
  modalInitial.value = { ...r }
  modalVatTu.value = r.name
  modalCoPhatSinh.value = !!r.co_phat_sinh
  modalOpen.value = true
}

function onSaved() {
  modalOpen.value = false
  showToast('Đã lưu danh mục.')
  load()
}

onMounted(load)
</script>

<template>
  <div>
    <div class="topbar">
      <h2>Danh mục vật tư</h2>
      <div class="flex" style="gap: 8px; flex-wrap: wrap">
        <button class="btn btn-sm" @click="moTao">+ Thêm vật tư</button>
        <a class="btn-o btn-sm" :href="exportUrl">⬇ Xuất danh mục</a>
        <router-link to="/kho/vat-tu/import" class="btn-o btn-sm">⬆ Nhập danh mục</router-link>
        <router-link to="/kho" class="btn-o btn-sm">Quay lại</router-link>
      </div>
    </div>

    <div class="card mb10 flex" style="gap: 12px; align-items: center; flex-wrap: wrap">
      <input v-model="tim" placeholder="Tìm theo mã hoặc tên…" style="flex: 1; min-width: 200px" />
      <label style="display: flex; align-items: center; gap: 6px">
        <input type="checkbox" v-model="caTat" @change="load" />
        Hiện cả vật tư đã tắt
      </label>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <div v-else-if="!hienThi.length" class="empty">Chưa có vật tư nào.</div>

    <div v-else-if="!isMobile" class="card" style="padding: 0; overflow-x: auto">
      <table>
        <thead>
          <tr>
            <th>Mã</th><th>Tên</th><th>ĐVT</th><th>Mã hàng Miyano</th>
            <th>Quy cách</th><th>Nhóm</th><th>Đang dùng</th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in hienThi" :key="r.name">
            <td>{{ r.ma_vat_tu }}</td>
            <td>{{ r.ten_vat_tu }}</td>
            <td>{{ r.dvt }}</td>
            <td>{{ r.item_code || '—' }}</td>
            <td>{{ r.quy_cach || '—' }}</td>
            <td>{{ r.nhom || '—' }}</td>
            <td>
              <span class="badge" :class="r.active ? 'b-green' : 'b-gray'">
                {{ r.active ? 'Đang dùng' : 'Đã tắt' }}
              </span>
            </td>
            <td><button class="btn-o btn-sm" @click="moSua(r)">Sửa</button></td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-else>
      <div v-for="r in hienThi" :key="r.name" class="card mb10">
        <div class="sb">
          <b>{{ r.ma_vat_tu }}</b>
          <span class="badge" :class="r.active ? 'b-green' : 'b-gray'">
            {{ r.active ? 'Đang dùng' : 'Đã tắt' }}
          </span>
        </div>
        <div>{{ r.ten_vat_tu }}</div>
        <p class="tag">ĐVT {{ r.dvt }} · {{ r.item_code ? 'Mã Miyano ' + r.item_code : 'Mã riêng' }}</p>
        <button class="btn-o btn-sm" @click="moSua(r)">Sửa</button>
      </div>
    </div>

    <VatTuModal
      :open="modalOpen"
      :initial="modalInitial"
      :mode="modalMode"
      :vat-tu="modalVatTu"
      :co-phat-sinh="modalCoPhatSinh"
      @saved="onSaved"
      @close="modalOpen = false"
    />
  </div>
</template>
```

- [ ] **Step 4: Viết `ImportDanhMuc.vue`**

Chạy `cp frontend/src/views/ImportTonDau.vue frontend/src/views/ImportDanhMuc.vue`, rồi sửa **đúng năm chỗ** dưới đây và không sửa gì khác — cấu trúc ba bước (chọn tệp → xem trước → xác nhận), phần xử lý lỗi và phần hiển thị mobile giữ nguyên:

```js
const templateUrl = api.khoDownloadUrl('kho_vat_tu_export')   // "mẫu" = chính danh mục hiện tại
// preview:
preview.value = await api.callKho('kho_vat_tu_import_preview', { file_url: fileUrl.value })
// commit:
result.value = await api.callKho('kho_vat_tu_import_commit', { file_url: fileUrl.value })
```

Chỗ thứ tư — bảng xem trước hiển thị `hanh_dong` thay cho `match_type` (đổi cả hằng số `MATCH_LABEL` và chỗ tra nó trong `<template>`):

```js
const HANH_DONG_LABEL = {
  tao_moi: { text: 'Tạo mới', cls: 'b-blue' },
  cap_nhat: { text: 'Cập nhật', cls: 'b-green' },
}
```

Chỗ thứ năm — màn kết quả: thay dòng `Phiếu nhập: {{ result.receipt }}` bằng
`Tạo mới: {{ result.tao_moi }} · Cập nhật: {{ result.cap_nhat }}`, và nút
**Xem tồn kho** đổi thành **Xem danh mục** trỏ `/kho/vat-tu` (sửa `goToKho()`
thành `router.push('/kho/vat-tu')`). Bốn cột `Số lô` / `Hạn dùng` / `Số lượng` /
`Đơn giá` trong bảng xem trước đổi thành `Mã hàng Miyano` / `Quy cách` / `Nhóm` /
`Đang dùng`, khớp `DANH_MUC_COLUMNS`.

- [ ] **Step 5: Build và kiểm chứng**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct && bench build --app miyano_portal
```

Trên trình duyệt: `/portal/kho` → **Danh mục vật tư** → thấy 4 vật tư của kho MD → **Sửa** một vật tư đã có phát sinh, kỳ vọng ô Mã và ĐVT bị khoá kèm dòng 🔒 → **⬇ Xuất danh mục** tải được file → sửa một tên trong file → **⬆ Nhập danh mục** → xem trước báo `Cập nhật: 4` → xác nhận → tên mới hiện trên danh mục.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/router.js frontend/src/views/Kho.vue frontend/src/views/DanhMucVatTu.vue frontend/src/views/ImportDanhMuc.vue
git commit -m "feat(portal): màn danh mục vật tư — thêm, sửa, xuất và nhập"
```

---

## Task 8: `kho/dong_phieu.py` — bộ cột, file mẫu, đọc file, xuất dòng

**Files:**
- Create: `miyano_portal/kho/dong_phieu.py`
- Test: `miyano_portal/tests/test_kho_dong_phieu.py`

**Interfaces:**
- Consumes: `import_ton_dau.mo_workbook/read_header/_cell_value/_coerce_date/_coerce_num/_norm/_match_vat_tu`, `ledger.LOT_KHONG_CO`, `reports.build_xlsx`
- Produces:
  - `COLUMNS = {"nhap": [...], "xuat": [...]}`, `REQUIRED = {"nhap": {...}, "xuat": {...}}`
  - `build_mau_xlsx(loai: str) -> bytes`
  - `doc_file(content: bytes, kho: str, loai: str) -> dict` — `{total, rows: [...]}`; mỗi dòng có `line, trang_thai ∈ {khop, ma_moi, loi}, vat_tu, ma_vat_tu, ten_vat_tu, dvt, so_lo, so_luong, ghi_chu, loi[]` (+ `han_su_dung, don_gia, quy_cach, nhom` cho `nhap`)
  - `export_rows(doctype: str, name: str) -> list[dict]`
  - `build_export_xlsx(doctype: str, name: str) -> bytes`

- [ ] **Step 1: Viết test thất bại**

Tạo `miyano_portal/tests/test_kho_dong_phieu.py`:

```python
"""Import/export bảng dòng của phiếu nhập và phiếu xuất."""

import io

import frappe
from frappe.tests.utils import FrappeTestCase
from openpyxl import Workbook, load_workbook

from miyano_portal.kho import dong_phieu
from miyano_portal.setup.seed_kho_demo import seed_kho_demo


def _xlsx(loai, rows):
	wb = Workbook()
	ws = wb.active
	ws.append([label for label, _ in dong_phieu.COLUMNS[loai]])
	for r in rows:
		ws.append(r)
	buf = io.BytesIO()
	wb.save(buf)
	return buf.getvalue()


class TestDocFileNhap(FrappeTestCase):
	def setUp(self):
		self.kho = seed_kho_demo()
		self.kho_bm = self.kho["kho_bm"]

	def test_ma_da_co_thi_trang_thai_khop_va_gan_san_vat_tu(self):
		kq = dong_phieu.doc_file(
			_xlsx("nhap", [["MYN-GLOVE-M", "", "", "LO-1", None, 10, 1000, "", "", ""]]),
			self.kho_bm, "nhap",
		)
		row = kq["rows"][0]
		self.assertEqual(row["trang_thai"], "khop")
		self.assertEqual(row["vat_tu"], self.kho["vt_bm"])

	def test_ma_la_thi_trang_thai_ma_moi(self):
		kq = dong_phieu.doc_file(
			_xlsx("nhap", [["BM-LA-01", "Vật tư lạ", "Cái", "LO-2", None, 5, 2000, "", "", ""]]),
			self.kho_bm, "nhap",
		)
		row = kq["rows"][0]
		self.assertEqual(row["trang_thai"], "ma_moi")
		self.assertEqual(row["vat_tu"], "")
		self.assertEqual(row["ten_vat_tu"], "Vật tư lạ")

	def test_so_luong_sai_thi_trang_thai_loi_neu_dung_so_dong(self):
		kq = dong_phieu.doc_file(
			_xlsx("nhap", [["MYN-GLOVE-M", "", "", "LO-1", None, "abc", 1000, "", "", ""]]),
			self.kho_bm, "nhap",
		)
		row = kq["rows"][0]
		self.assertEqual(row["trang_thai"], "loi")
		self.assertEqual(row["line"], 2)  # header ở dòng 1
		self.assertIn("Số lượng", " ".join(row["loi"]))

	def test_ma_moi_thieu_ten_hoac_dvt_thi_loi(self):
		kq = dong_phieu.doc_file(
			_xlsx("nhap", [["BM-LA-02", "", "", "LO-3", None, 5, 2000, "", "", ""]]),
			self.kho_bm, "nhap",
		)
		self.assertEqual(kq["rows"][0]["trang_thai"], "loi")

	def test_ma_da_co_thi_bo_qua_ten_va_dvt_trong_file(self):
		kq = dong_phieu.doc_file(
			_xlsx("nhap", [["MYN-GLOVE-M", "TÊN SAI", "ĐVT SAI", "LO-1", None, 10, 1000, "", "", ""]]),
			self.kho_bm, "nhap",
		)
		row = kq["rows"][0]
		self.assertEqual(row["ten_vat_tu"], "Găng tay y tế size M")
		self.assertNotEqual(row["dvt"], "ĐVT SAI")

	def test_so_lo_trong_thi_nhan_lo_mac_dinh(self):
		kq = dong_phieu.doc_file(
			_xlsx("nhap", [["MYN-GLOVE-M", "", "", "", None, 10, 1000, "", "", ""]]),
			self.kho_bm, "nhap",
		)
		self.assertEqual(kq["rows"][0]["so_lo"], "KHONG-LO")


class TestDocFileXuat(FrappeTestCase):
	def setUp(self):
		self.kho = seed_kho_demo()
		self.kho_bm = self.kho["kho_bm"]

	def test_file_xuat_khong_co_cot_don_gia(self):
		labels = [label for label, _ in dong_phieu.COLUMNS["xuat"]]
		self.assertNotIn("Đơn giá", labels)
		self.assertNotIn("Hạn sử dụng", labels)

	def test_doc_file_xuat_khong_tra_don_gia(self):
		kq = dong_phieu.doc_file(
			_xlsx("xuat", [["MYN-GLOVE-M", "", "", "LO-1", 3, "", "", ""]]),
			self.kho_bm, "xuat",
		)
		self.assertNotIn("don_gia", kq["rows"][0])

	def test_loai_la_bi_chan(self):
		with self.assertRaises(frappe.ValidationError):
			dong_phieu.doc_file(b"", self.kho_bm, "linh tinh")


class TestExportDong(FrappeTestCase):
	def setUp(self):
		self.kho = seed_kho_demo()
		self.phieu = frappe.get_doc({
			"doctype": "Customer Stock Receipt",
			"kho": self.kho["kho_bm"],
			"ngay": frappe.utils.today(),
			"loai_nhap": "Nhập khác",
			"items": [{
				"vat_tu": self.kho["vt_bm"], "so_lo": "LO-EXP-01",
				"so_luong": 7, "don_gia": 1234,
			}],
		})
		self.phieu.insert(ignore_permissions=True)

	def test_export_ra_dung_bo_cot_va_du_lieu(self):
		content = dong_phieu.build_export_xlsx("Customer Stock Receipt", self.phieu.name)
		ws = load_workbook(io.BytesIO(content), data_only=True).active
		self.assertEqual([c.value for c in ws[1]], [label for label, _ in dong_phieu.COLUMNS["nhap"]])
		self.assertEqual(ws.cell(row=2, column=1).value, "MYN-GLOVE-M")
		self.assertEqual(ws.cell(row=2, column=6).value, 7)

	def test_export_roi_nap_lai_ra_dong_khop(self):
		content = dong_phieu.build_export_xlsx("Customer Stock Receipt", self.phieu.name)
		kq = dong_phieu.doc_file(content, self.kho["kho_bm"], "nhap")
		self.assertEqual(kq["rows"][0]["trang_thai"], "khop")
		self.assertEqual(kq["rows"][0]["so_luong"], 7)
```

- [ ] **Step 2: Chạy để xác nhận đỏ**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_dong_phieu`
Expected: FAIL — `ModuleNotFoundError: No module named 'miyano_portal.kho.dong_phieu'`

- [ ] **Step 3: Viết `kho/dong_phieu.py`**

```python
"""Bảng dòng của phiếu nhập/phiếu xuất: đọc từ .xlsx, xuất ra .xlsx.

Module này KHÔNG GHI GÌ vào database. Nó chỉ dịch giữa một tệp Excel và danh
sách dòng mà màn hình phiếu đang soạn — việc ghi vẫn đi qua đúng
kho_phieu_nhap_save / kho_phieu_xuat_save như mọi dòng gõ tay.

Vì sao phiếu xuất không có cột Đơn giá và Hạn sử dụng: controller của
Customer Stock Issue luôn ghi đè hai giá trị đó bằng giá/hạn hiện hành của lô
(_lay_gia_va_han_tu_lo). Nhận chúng từ tệp chỉ tạo ảo giác là người dùng đặt
được giá vốn.
"""

import frappe

from miyano_portal.kho import ledger
from miyano_portal.kho.import_ton_dau import (
	_cell_value,
	_coerce_date,
	_coerce_num,
	_norm,
	_match_vat_tu,
	mo_workbook,
	read_header,
)

COLUMNS = {
	"nhap": [
		("Mã vật tư", "ma_vat_tu"),
		("Tên vật tư", "ten_vat_tu"),
		("ĐVT", "dvt"),
		("Số lô", "so_lo"),
		("Hạn sử dụng", "han_su_dung"),
		("Số lượng", "so_luong"),
		("Đơn giá", "don_gia"),
		("Quy cách", "quy_cach"),
		("Nhóm", "nhom"),
		("Ghi chú", "ghi_chu"),
	],
	"xuat": [
		("Mã vật tư", "ma_vat_tu"),
		("Tên vật tư", "ten_vat_tu"),
		("ĐVT", "dvt"),
		("Số lô", "so_lo"),
		("Số lượng", "so_luong"),
		("Quy cách", "quy_cach"),
		("Nhóm", "nhom"),
		("Ghi chú", "ghi_chu"),
	],
}

# Cột phải CÓ MẶT trong header. `Tên vật tư`/`ĐVT` KHÔNG bắt buộc ở đây: chúng
# chỉ cần thiết cho dòng mang mã chưa có (để tạo nhanh), và điều đó được kiểm
# theo TỪNG DÒNG bên dưới.
REQUIRED = {
	"nhap": {"ma_vat_tu", "so_luong", "don_gia"},
	"xuat": {"ma_vat_tu", "so_luong"},
}

DOCTYPE_THEO_LOAI = {
	"nhap": "Customer Stock Receipt",
	"xuat": "Customer Stock Issue",
}
LOAI_THEO_DOCTYPE = {v: k for k, v in DOCTYPE_THEO_LOAI.items()}


def _kiem_loai(loai: str) -> str:
	if loai not in COLUMNS:
		frappe.throw(
			'Loại phiếu không hợp lệ. Chỉ chấp nhận "nhap" hoặc "xuat".',
			frappe.ValidationError,
		)
	return loai


def build_mau_xlsx(loai: str) -> bytes:
	"""Tệp mẫu rỗng, đúng bộ cột — không kèm dòng ví dụ, vì người dùng dán dữ
	liệu thật vào ngay dưới header và một dòng ví dụ bị bỏ quên sẽ thành một
	dòng phiếu thật."""
	from miyano_portal.kho import reports

	_kiem_loai(loai)
	return reports.build_xlsx(COLUMNS[loai], [], "Dong phieu")


def doc_file(content: bytes, kho: str, loai: str) -> dict:
	"""Đọc tệp thành các dòng phiếu. KHÔNG GHI GÌ.

	Mỗi dòng nhận đúng một trạng thái:
	  * "khop"   — mã đã có trong kho; `vat_tu` gán sẵn, tên/ĐVT lấy THEO DANH
	               MỤC (bỏ qua cột mô tả trong tệp, để một tệp cũ nạp lại không
	               âm thầm đổi ĐVT của vật tư đã có phát sinh).
	  * "ma_moi" — mã chưa có; giữ nguyên mô tả đọc từ tệp để modal tạo nhanh
	               điền sẵn. Bắt buộc phải có Tên và ĐVT, không thì thành "loi".
	  * "loi"    — thiếu trường bắt buộc hoặc sai định dạng; `loi` liệt kê MỌI
	               lý do của dòng đó, kèm số dòng thật trong tệp.
	"""
	_kiem_loai(loai)
	ws = mo_workbook(content)
	header_row, col_index = read_header(ws, COLUMNS[loai], REQUIRED[loai])
	co_don_gia = loai == "nhap"

	rows: list[dict] = []
	for line, row_cells in enumerate(
		ws.iter_rows(min_row=header_row + 1, max_row=ws.max_row), start=header_row + 1
	):
		raw = {field: _cell_value(row_cells, col) for field, col in col_index.items()}
		if all(v is None or (isinstance(v, str) and not v.strip()) for v in raw.values()):
			continue

		loi: list[str] = []
		ma = _norm(raw.get("ma_vat_tu"))
		ten = _norm(raw.get("ten_vat_tu"))
		dvt = _norm(raw.get("dvt"))
		so_lo = _norm(raw.get("so_lo")) or ledger.LOT_KHONG_CO
		ghi_chu = _norm(raw.get("ghi_chu"))

		if not ma:
			loi.append("Thiếu Mã vật tư")

		so_luong = None
		if raw.get("so_luong") in (None, ""):
			loi.append("Thiếu Số lượng")
		else:
			so_luong, err = _coerce_num(raw.get("so_luong"))
			if err:
				loi.append(f"Số lượng không hợp lệ: {err}")
			elif so_luong <= 0:
				loi.append("Số lượng phải lớn hơn 0")

		don_gia = None
		han_su_dung = None
		if co_don_gia:
			if raw.get("don_gia") in (None, ""):
				loi.append("Thiếu Đơn giá")
			else:
				don_gia, err = _coerce_num(raw.get("don_gia"))
				if err:
					loi.append(f"Đơn giá không hợp lệ: {err}")
				elif don_gia < 0:
					loi.append("Đơn giá không được âm")
			han_su_dung, han_err = _coerce_date(raw.get("han_su_dung"))
			if han_err:
				loi.append(han_err)

		vat_tu_name = ""
		trang_thai = "ma_moi"
		if ma and not loi:
			match_type, _item_code, found = _match_vat_tu(kho, ma)
			if match_type == "existing":
				trang_thai = "khop"
				vat_tu_name = found
				hien = frappe.db.get_value(
					"Customer Warehouse Item", found, ["ma_vat_tu", "ten_vat_tu", "dvt"], as_dict=True
				)
				ma, ten, dvt = hien.ma_vat_tu, hien.ten_vat_tu, hien.dvt
			else:
				if not ten:
					loi.append("Mã chưa có trong kho — cần Tên vật tư để tạo mới")
				if not dvt:
					loi.append("Mã chưa có trong kho — cần ĐVT để tạo mới")

		row = {
			"line": line,
			"trang_thai": "loi" if loi else trang_thai,
			"vat_tu": vat_tu_name,
			"ma_vat_tu": ma,
			"ten_vat_tu": ten,
			"dvt": dvt,
			"so_lo": so_lo,
			"so_luong": so_luong,
			"quy_cach": _norm(raw.get("quy_cach")),
			"nhom": _norm(raw.get("nhom")),
			"ghi_chu": ghi_chu,
			"loi": loi,
		}
		if co_don_gia:
			row["don_gia"] = don_gia
			row["han_su_dung"] = han_su_dung
		rows.append(row)

	return {"total": len(rows), "rows": rows}


def export_rows(doctype: str, name: str) -> list[dict]:
	"""Nơi gọi PHẢI kiểm phiếu thuộc kho của người gọi trước (_phieu_cua_kho)."""
	loai = LOAI_THEO_DOCTYPE.get(doctype)
	if not loai:
		frappe.throw("Loại chứng từ không hợp lệ.", frappe.ValidationError)

	doc = frappe.get_doc(doctype, name)
	out = []
	for r in doc.items:
		vt = frappe.db.get_value(
			"Customer Warehouse Item", r.vat_tu,
			["ma_vat_tu", "ten_vat_tu", "dvt", "quy_cach", "nhom"], as_dict=True,
		) or frappe._dict()
		row = {
			"ma_vat_tu": vt.get("ma_vat_tu") or "",
			"ten_vat_tu": r.ten_vat_tu or vt.get("ten_vat_tu") or "",
			"dvt": r.dvt or vt.get("dvt") or "",
			"so_lo": r.so_lo,
			"so_luong": float(r.so_luong or 0),
			"quy_cach": vt.get("quy_cach") or "",
			"nhom": vt.get("nhom") or "",
			"ghi_chu": r.ghi_chu or "",
		}
		if loai == "nhap":
			row["han_su_dung"] = r.han_su_dung
			row["don_gia"] = float(r.don_gia or 0)
		out.append(row)
	return out


def build_export_xlsx(doctype: str, name: str) -> bytes:
	from miyano_portal.kho import reports

	loai = LOAI_THEO_DOCTYPE.get(doctype)
	if not loai:
		frappe.throw("Loại chứng từ không hợp lệ.", frappe.ValidationError)
	return reports.build_xlsx(COLUMNS[loai], export_rows(doctype, name), "Dong phieu")
```

- [ ] **Step 4: Chạy test, phải xanh**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_dong_phieu`
Expected: PASS (11 ca)

- [ ] **Step 5: Commit**

```bash
git add miyano_portal/kho/dong_phieu.py miyano_portal/tests/test_kho_dong_phieu.py
git commit -m "feat(kho): đọc và xuất bảng dòng phiếu nhập/xuất qua Excel"
```

---

## Task 9: Ba endpoint dòng phiếu + test chốt chặn server

**Files:**
- Modify: `miyano_portal/api/kho.py` (thêm sau `kho_phieu_cancel`)
- Test: `miyano_portal/tests/test_kho_dong_phieu.py` (thêm class)

**Interfaces:**
- Consumes: `dong_phieu.build_mau_xlsx/doc_file/build_export_xlsx`, `_phieu_cua_kho`, `_resolve_owned_spreadsheet`
- Produces: `kho_dong_phieu_mau(loai)`, `kho_dong_phieu_doc_file(loai, file_url)`, `kho_dong_phieu_export(doctype, name)`

**Lưu ý:** chốt chặn "dòng chưa chọn vật tư" ở server **đã có sẵn** trong `_validate_items_present` (`api/kho.py:377-385`). Task này chỉ bổ sung test khoá lại hành vi đó, không viết thêm guard.

- [ ] **Step 1: Viết test thất bại**

Thêm vào cuối `test_kho_dong_phieu.py`:

```python
from miyano_portal.api import kho as kho_api

BM_USER = "bvbm@demo.miyano"
PXN_USER = "pxnabc@demo.miyano"


class TestDongPhieuEndpoint(FrappeTestCase):
	def setUp(self):
		self.kho = seed_kho_demo()
		self.phieu_bm = frappe.get_doc({
			"doctype": "Customer Stock Receipt",
			"kho": self.kho["kho_bm"],
			"ngay": frappe.utils.today(),
			"loai_nhap": "Nhập khác",
			"items": [{
				"vat_tu": self.kho["vt_bm"], "so_lo": "LO-EP-01",
				"so_luong": 2, "don_gia": 100,
			}],
		})
		self.phieu_bm.insert(ignore_permissions=True)
		frappe.set_user(BM_USER)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_mau_tra_ve_file(self):
		kho_api.kho_dong_phieu_mau("nhap")
		self.assertEqual(frappe.local.response.type, "download")
		self.assertTrue(frappe.local.response.filecontent)

	def test_export_phieu_cua_kho_khac_bi_chan(self):
		frappe.set_user(PXN_USER)
		with self.assertRaises(frappe.PermissionError):
			kho_api.kho_dong_phieu_export("Customer Stock Receipt", self.phieu_bm.name)

	def test_export_doctype_ngoai_danh_sach_trang_bi_chan(self):
		with self.assertRaises(frappe.ValidationError):
			kho_api.kho_dong_phieu_export("Sales Invoice", self.phieu_bm.name)

	def test_luu_phieu_co_dong_thieu_vat_tu_bi_chan_o_server(self):
		with self.assertRaises(frappe.ValidationError) as ctx:
			kho_api.kho_phieu_nhap_save({
				"ngay": frappe.utils.today(),
				"loai_nhap": "Nhập khác",
				"items": [{"vat_tu": "", "so_lo": "LO-X", "so_luong": 1, "don_gia": 100}],
			})
		self.assertIn("chưa chọn vật tư", str(ctx.exception))
```

- [ ] **Step 2: Chạy để xác nhận đỏ**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_dong_phieu`
Expected: FAIL — `AttributeError: … has no attribute 'kho_dong_phieu_mau'` (ca cuối cùng phải XANH ngay, vì guard đã có sẵn)

- [ ] **Step 3: Thêm ba endpoint vào `api/kho.py`**

Thêm import cạnh các import `kho` khác:

```python
from miyano_portal.kho import dong_phieu
```

Rồi thêm sau `kho_phieu_cancel`:

```python
@frappe.whitelist()
@_phieu_action
def kho_dong_phieu_mau(loai: str) -> None:
	"""Tệp .xlsx rỗng đúng bộ cột của loại phiếu, để khách điền rồi nạp vào."""
	get_portal_kho()  # khách chưa mở kho nhận cùng thông báo như mọi endpoint kho
	frappe.local.response.filename = f"mau_dong_phieu_{loai}.xlsx"
	frappe.local.response.filecontent = dong_phieu.build_mau_xlsx(loai)
	frappe.local.response.type = "download"
	frappe.local.response.content_type = (
		"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
	)


@frappe.whitelist()
@_phieu_action
def kho_dong_phieu_doc_file(loai: str, file_url) -> dict:
	"""Đọc tệp thành các dòng phiếu. KHÔNG GHI GÌ — việc ghi vẫn đi qua
	kho_phieu_nhap_save / kho_phieu_xuat_save như dòng gõ tay."""
	kho = get_portal_kho()
	content = _resolve_owned_spreadsheet(file_url)
	return dong_phieu.doc_file(content, kho, loai)


@frappe.whitelist()
@_phieu_action
def kho_dong_phieu_export(doctype: str, name: str) -> None:
	kho = get_portal_kho()
	_phieu_cua_kho(doctype, name, kho)
	frappe.local.response.filename = f"{name}-dong.xlsx"
	frappe.local.response.filecontent = dong_phieu.build_export_xlsx(doctype, name)
	frappe.local.response.type = "download"
	frappe.local.response.content_type = (
		"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
	)
```

- [ ] **Step 4: Chạy test, phải xanh**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_dong_phieu`
Expected: PASS (15 ca)

- [ ] **Step 5: Commit**

```bash
git add miyano_portal/api/kho.py miyano_portal/tests/test_kho_dong_phieu.py
git commit -m "feat(kho): endpoint file mẫu, đọc file và xuất dòng phiếu"
```

---

## Task 10: Import/export bảng dòng trên màn phiếu nhập

**Files:**
- Modify: `frontend/src/views/PhieuNhapDetail.vue`

- [ ] **Step 1: Thêm trạng thái và ba hàm vào `<script setup>`**

```js
const importing = ref(false)
const importInput = ref(null)
const mauUrl = api.khoDownloadUrl('kho_dong_phieu_mau') + '?loai=nhap'
const exportUrl = computed(() =>
  api.khoDownloadUrl('kho_dong_phieu_export') +
  `?doctype=${encodeURIComponent(DOCTYPE)}&name=${encodeURIComponent(doc.name)}`
)

// Còn dòng đỏ hoặc dòng chưa có vật tư thì không cho lưu. Server chặn lần nữa
// (_validate_items_present) — đây chỉ là lớp phản hồi nhanh.
const dongChuaXuLy = computed(
  () => doc.items.filter((r) => r._trang_thai === 'loi' || !r.vat_tu).length
)

async function onImportFile(e) {
  const f = e.target.files && e.target.files[0]
  if (!f) return
  importing.value = true
  try {
    const uploaded = await api.uploadFile(f)
    const kq = await api.callKho('kho_dong_phieu_doc_file', {
      loai: 'nhap',
      file_url: uploaded.file_url,
    })
    // NỐI vào cuối, không xoá dòng đang có — người dùng có thể đã gõ tay vài dòng.
    for (const r of kq.rows) {
      doc.items.push({
        vat_tu: r.vat_tu || '',
        so_lo: r.so_lo,
        han_su_dung: r.han_su_dung || '',
        so_luong: r.so_luong || 0,
        don_gia: r.don_gia || 0,
        ghi_chu: r.ghi_chu || '',
        _trang_thai: r.trang_thai,
        _loi: r.loi || [],
        _loi_line: r.line,
        _ma_vat_tu: r.ma_vat_tu,
        _ten_vat_tu: r.ten_vat_tu,
        _dvt: r.dvt,
        _quy_cach: r.quy_cach,
        _nhom: r.nhom,
      })
    }
    showToast(`Đã đọc ${kq.total} dòng từ tệp.`)
  } catch (err) {
    showToast(err.message || 'Không đọc được tệp.', 'error')
  } finally {
    importing.value = false
    if (importInput.value) importInput.value.value = ''
  }
}

// Mở modal tạo nhanh cho ĐÚNG dòng import, điền sẵn mọi thứ đọc được từ tệp.
function moTaoTuDong(row, idx) {
  modalRowIdx.value = idx
  modalInitial.value = {
    ma_vat_tu: row._ma_vat_tu || '',
    ten_vat_tu: row._ten_vat_tu || '',
    dvt: row._dvt || '',
    quy_cach: row._quy_cach || '',
    nhom: row._nhom || '',
  }
  modalOpen.value = true
}
```

Sửa `onVatTuSaved` (đã viết ở Task 4) để mọi dòng khác cùng mã cũng khớp theo:

```js
function onVatTuSaved(vt) {
  if (!vatTuList.value.some((v) => v.name === vt.name)) vatTuList.value.push(vt)
  // Mọi dòng đang chờ đúng mã này đều khớp theo — import 20 dòng cùng một mã
  // lạ chỉ phải bấm OK một lần.
  const ma = (vt.ma_vat_tu || '').toLowerCase()
  for (const r of doc.items) {
    if (!r.vat_tu && (r._ma_vat_tu || '').toLowerCase() === ma) {
      r.vat_tu = vt.name
      r._trang_thai = 'khop'
      r._loi = []
    }
  }
  if (modalRowIdx.value >= 0) {
    const row = doc.items[modalRowIdx.value]
    row.vat_tu = vt.name
    row._trang_thai = 'khop'
    row._loi = []
  }
  modalOpen.value = false
  modalRowIdx.value = -1
}
```

Và chặn lưu trong `save()` — thêm ngay đầu hàm:

```js
  if (dongChuaXuLy.value) {
    showToast(`Còn ${dongChuaXuLy.value} dòng chưa xử lý (thiếu vật tư hoặc sai dữ liệu).`, 'error')
    return
  }
```

- [ ] **Step 2: Thêm thanh nút và cột trạng thái vào `<template>`**

Ngay trên thẻ `<div class="card" style="padding: 0; overflow-x: auto">` của bảng dòng:

```html
<div v-if="editable" class="flex mb10" style="gap: 8px; flex-wrap: wrap">
  <a class="btn-o btn-sm" :href="mauUrl">Tải file mẫu</a>
  <button class="btn-o btn-sm" :disabled="importing" @click="importInput.click()">
    {{ importing ? 'Đang đọc…' : '⬆ Nhập từ Excel' }}
  </button>
  <a v-if="!isNew" class="btn-o btn-sm" :href="exportUrl">⬇ Xuất Excel</a>
  <input ref="importInput" type="file" accept=".xlsx" style="display: none" @change="onImportFile" />
</div>
```

Trong `<tbody>`, đổi thẻ `<tr>` để tô nền theo trạng thái và thêm khối cảnh báo dưới ô Vật tư:

```html
<tr v-for="(r, idx) in doc.items" :key="idx"
    :style="r._trang_thai === 'loi' ? 'background:#fff1f0' : (r._trang_thai === 'ma_moi' ? 'background:#fffbe6' : '')">
  <td>
    <select v-if="editable" v-model="r.vat_tu" style="width: 100%" @change="onVatTuSelect(r, idx)">
      <option value="" disabled>-- Chọn vật tư --</option>
      <option v-for="v in vatTuList" :key="v.name" :value="v.name">
        {{ v.ma_vat_tu }} — {{ v.ten_vat_tu }}
      </option>
      <option :value="MUC_TAO_MOI">➕ Tạo vật tư mới…</option>
    </select>
    <span v-else>{{ r.ten_vat_tu || tenVatTu(r.vat_tu) }}</span>

    <div v-if="editable && r._trang_thai === 'ma_moi' && !r.vat_tu" class="warn" style="margin-top: 4px">
      ⚠ Mã <b>{{ r._ma_vat_tu }}</b> chưa có trong kho.
      <button class="btn-o btn-sm" @click="moTaoTuDong(r, idx)">Tạo vật tư mới</button>
    </div>
    <div v-if="r._loi && r._loi.length" class="tag" style="color: #cf1322; margin-top: 4px">
      ✗ Dòng {{ r._loi_line }} trong tệp: {{ r._loi.join('; ') }}
    </div>
  </td>
```

`_loi_line` chính là `r.line` đã đẩy vào ở Step 1 — số dòng **thật trong tệp
Excel**, để người dùng mở tệp ra sửa đúng chỗ chứ không phải đếm dòng trên màn hình.

- [ ] **Step 3: Build và kiểm chứng**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct && bench build --app miyano_portal
```

Trên trình duyệt, `/portal/kho/nhap` → **+ Tạo phiếu nhập** → **Tải file mẫu** → điền 3 dòng: một mã đã có (`MYN-SYR-10`), một mã lạ (`BV-KIM-22G` kèm tên và ĐVT), một dòng số lượng ghi `abc` → **⬆ Nhập từ Excel**. Kỳ vọng: dòng 1 bình thường; dòng 2 nền vàng kèm nút **Tạo vật tư mới**; dòng 3 nền đỏ kèm lý do và số dòng. Bấm **Lưu nháp** khi còn dòng đỏ → phải bị chặn kèm thông báo. Bấm **Tạo vật tư mới** ở dòng 2 → OK → nền vàng biến mất. Xoá dòng đỏ → **Lưu nháp** thành công → **⬇ Xuất Excel** tải về đúng các dòng vừa lưu.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/PhieuNhapDetail.vue
git commit -m "feat(portal): import/export bảng dòng phiếu nhập, tạo nhanh vật tư tại dòng"
```

---

## Task 11: Import/export bảng dòng trên màn phiếu xuất

**Files:**
- Modify: `frontend/src/views/PhieuXuatDetail.vue`

- [ ] **Step 1: Chép nguyên phần import của Task 10 sang, rồi sửa đúng bốn chỗ**

Chép sang `PhieuXuatDetail.vue` toàn bộ mã của Task 10 Step 1 (`importing`, `importInput`, `mauUrl`, `exportUrl`, `dongChuaXuLy`, `onImportFile`, `moTaoTuDong`, bản `onVatTuSaved` mới, và đoạn chặn đầu hàm `save()`) và Task 10 Step 2 (thanh nút + thẻ `<tr>` tô nền + khối cảnh báo dưới ô Vật tư). Bốn khác biệt:

**(1)** URL file mẫu và loại phiếu:

```js
const mauUrl = api.khoDownloadUrl('kho_dong_phieu_mau') + '?loai=xuat'
```

**(2)** trong `onImportFile`, gọi `loai: 'xuat'` và đẩy dòng **không có** `don_gia`/`han_su_dung` (controller lấy từ lô), có thêm các trường trạng thái lô mà màn xuất cần:

```js
      doc.items.push({
        vat_tu: r.vat_tu || '',
        so_lo: r.so_lo,
        so_luong: r.so_luong || 0,
        xac_nhan_het_han: 0,
        ghi_chu: r.ghi_chu || '',
        _lots: [],
        _lotsLoading: false,
        _hetHan: false,
        _trang_thai: r.trang_thai,
        _loi: r.loi || [],
        _loi_line: r.line,
        _ma_vat_tu: r.ma_vat_tu,
        _ten_vat_tu: r.ten_vat_tu,
        _dvt: r.dvt,
        _quy_cach: r.quy_cach,
        _nhom: r.nhom,
      })
```

**(3)** nạp lô cho các dòng đã khớp, đặt ngay sau vòng lặp đẩy dòng và trước `showToast`:

```js
    // Dòng khớp mã thì nạp lô ngay để người dùng thấy lô nào còn tồn; dòng
    // chưa có vật tư thì bỏ qua, sẽ nạp khi tạo nhanh xong.
    for (const r of doc.items) {
      if (r.vat_tu && !r._lots.length) await onVatTuChange(r)
    }
```

- [ ] **Step 2: Khác biệt (4) — cảnh báo "chưa có tồn"**

Trong ô Lô của `<template>`, ngay dưới nhánh `v-else-if="r.vat_tu"` hiện có:

```html
<span v-else-if="r.vat_tu" class="tag">
  Vật tư này chưa còn tồn lô nào.
  <template v-if="r._vua_tao">
    Đây là vật tư vừa tạo — phải nhập kho trước khi ghi sổ phiếu xuất này.
  </template>
</span>
```

và đặt cờ trong `onVatTuSaved`, ngay sau khi gán `row.vat_tu`:

```js
    row._vua_tao = true
```

- [ ] **Step 3: Build và kiểm chứng**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct && bench build --app miyano_portal
```

`/portal/kho/xuat` → **+ Tạo phiếu xuất** → nhập tệp có một mã lạ → nền vàng + nút Tạo vật tư → bấm OK → kỳ vọng cột Lô hiện *"Vật tư này chưa còn tồn lô nào. Đây là vật tư vừa tạo — phải nhập kho trước khi ghi sổ phiếu xuất này."* → **Lưu nháp** thành công → **Ghi sổ** bị chặn với thông báo tồn.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/PhieuXuatDetail.vue
git commit -m "feat(portal): import/export bảng dòng phiếu xuất, cảnh báo vật tư chưa có tồn"
```

---

## Task 12: Cập nhật tài liệu và kiểm chứng toàn cục

**Files:**
- Modify: `docs/HDSD-tao-khach-hang-mo-kho-va-thao-tac-cong.md`

- [ ] **Step 1: Chạy toàn bộ test**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal`
Expected: PASS, trừ đúng một ca đỏ đã biết từ trước (`test_ma_kho_unique_across_customers` — đỏ vì site có sẵn kho của khách "Himedic", không liên quan tính năng này). Bất kỳ ca đỏ nào khác phải sửa trước khi đi tiếp.

- [ ] **Step 2: Thêm mục C5b vào tài liệu vận hành**

Chèn ngay sau mục **C5 · Kho của tôi**:

```markdown
### C5b. Danh mục vật tư

**Kho của tôi › Danh mục vật tư** liệt kê mọi vật tư của kho: mã · tên · ĐVT ·
mã hàng Miyano · quy cách · nhóm · đang dùng.

- **+ Thêm vật tư** — mã trùng một mặt hàng của Miyano thì hệ thống tự nối
  (cột *Mã hàng Miyano* có giá trị); mã lạ thì thành mã riêng của bệnh viện.
- **Sửa** — tên, quy cách, nhóm, ghi chú sửa lúc nào cũng được. **Mã vật tư và
  ĐVT bị khoá 🔒 khi vật tư đã có phát sinh trong sổ**: mọi số liệu cũ đã tính
  theo ĐVT đó và hệ thống không quy đổi.
- **Ngừng dùng** — bỏ tick *Đang dùng*. Không tắt được vật tư còn tồn; xuất hết
  rồi mới tắt.
- **⬇ Xuất danh mục / ⬆ Nhập danh mục** — tệp xuất ra sửa rồi nạp lại được. Mã
  đã có thì **cập nhật**, mã chưa có thì **tạo mới**. Cột *Mã hàng Miyano* chỉ
  để đối chiếu, nạp vào sẽ bị bỏ qua (hệ thống tự suy từ mã).
```

- [ ] **Step 3: Thêm mục C7b**

Chèn ngay sau mục **C8 · Nhập hàng mua ngoài**:

```markdown
### C8b. Nhập bảng dòng từ Excel

Trong màn lập phiếu nhập hoặc phiếu xuất: **Tải file mẫu** → điền → **⬆ Nhập từ
Excel**. Các dòng **nối vào cuối bảng**, không xoá dòng đã gõ tay.

| Màu dòng | Nghĩa | Việc cần làm |
|---|---|---|
| bình thường | mã đã có trong kho | không phải làm gì |
| nền vàng | mã chưa có | bấm **Tạo vật tư mới** — điền sẵn từ chính dòng đó |
| nền đỏ | sai dữ liệu | sửa tại ô, lý do và số dòng trong tệp hiện ngay dưới |

Còn dòng đỏ hoặc dòng chưa có vật tư thì **Lưu nháp bị chặn**.

Bấm **Tạo vật tư mới** một lần là mọi dòng khác cùng mã cũng tự khớp theo.

**⬇ Xuất Excel** chỉ bật khi phiếu đã lưu — tệp xuất ra nạp lại được.

Riêng phiếu xuất: tệp **không có** cột Đơn giá và Hạn dùng (hệ thống luôn lấy
theo lô), và vật tư vừa tạo nhanh sẽ báo *chưa có tồn* — lưu nháp được nhưng
phải nhập kho trước khi ghi sổ.
```

- [ ] **Step 4: Kiểm chứng end-to-end trên tài khoản demo**

Đăng nhập `http://192.168.61.129:8003/portal/login` bằng `bvminhduc@demo.miyano` / `Portal@123` và đi trọn một vòng: Danh mục vật tư → thêm một mã riêng → xuất danh mục → sửa tên trong tệp → nhập lại → Phiếu nhập mới → nhập tệp có mã lạ → tạo nhanh → lưu nháp → ghi sổ → Kho của tôi thấy tồn tăng đúng.

- [ ] **Step 5: Commit**

```bash
git add docs/HDSD-tao-khach-hang-mo-kho-va-thao-tac-cong.md
git commit -m "docs(kho): hướng dẫn danh mục vật tư và nhập bảng dòng từ Excel"
```

---

## Đối chiếu với spec

| Mục spec | Task |
|---|---|
| §3.1 hai module mới | 2, 5, 8 |
| §3.2 chín endpoint | 3, 6, 9 |
| §4.1 tạo vật tư, tự suy `item_code` | 2, 3 |
| §4.2 sửa có rào | 2 |
| §4.3 không tắt vật tư còn tồn | 2 |
| §4.3b import danh mục cập nhật/tạo | 5 |
| §4.4 ba trạng thái dòng, tạo nhanh lan sang dòng cùng mã | 8, 10 |
| §4.5 riêng phiếu xuất | 8, 11 |
| §4.6 chặn lưu nháp (client + server) | 9, 10 |
| §5 ba bộ cột, round-trip | 5, 8 |
| §6.1 màn danh mục | 7 |
| §6.2 thanh nút, ô chọn có mục tạo mới, mobile | 4, 10, 11 |
| §7 cách ly | 3, 6, 9 |
| §8 xử lý lỗi | xuyên suốt (Global Constraints) |
| §9 kiểm thử | 2, 3, 5, 6, 8, 9 |
| §11 thứ tự triển khai | thứ tự Task 2→11 |
