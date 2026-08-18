# Nền phân quyền theo khoa phòng — Kế hoạch thi công (bước 1–4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dựng tầng danh tính và tầng phạm vi dữ liệu theo khoa phòng cho cổng khách, **không đổi một hành vi nào** mà người dùng hiện tại nhìn thấy.

**Architecture:** Thay `Contact` bằng doctype mới `Portal Member` làm nguồn sự thật duy nhất cho danh tính cổng (cả hai chiều User↔Customer); chuyển `Customer Department` từ khoá theo kho sang khoá theo khách hàng; đưa mọi quyết định phạm vi về đúng hai hàm `pham_vi_don()` / `dam_bao_xem_duoc()` và bắt buộc mọi endpoint whitelist khai báo qua một test đếm ngược. Sau bốn bước này mọi tài khoản hiện có là `Quản lý` không gắn khoa → phạm vi vẫn là toàn bộ đơn của bệnh viện, y hệt hôm nay.

**Tech Stack:** Frappe v15.113.4, ERPNext (bản Miyano), MariaDB `utf8mb4_unicode_ci`, site `erptest.local`, Vue 3 SPA (không đụng tới trong kế hoạch này).

**Spec:** `docs/superpowers/specs/2026-08-18-phan-quyen-khoa-phong-va-duyet-don-design.md`

## Global Constraints

- **Không đổi hành vi người dùng.** Sau mọi task, `bench --site erptest.local run-tests --app miyano_portal` phải xanh **mà không sửa một test cũ nào**. Sửa test cũ = tín hiệu đã đổi hành vi → dừng và báo.
- **TDD bắt buộc.** Không viết code sản xuất trước khi có test đỏ và đã **nhìn thấy** nó đỏ đúng lý do.
- Patch mới đặt ở `miyano_portal/patches/v1_23/`, khai trong `miyano_portal/patches.txt`. **Patch chạy đúng một lần cho mỗi site** — sửa một patch đã chạy sẽ không bao giờ tới được site đã migrate; cần thay đổi thì viết patch mới.
- `FrappeTestCase` rollback **một lần cho cả CLASS**, không phải từng test → fixture phải tự dọn trong `setUp`.
- Bình luận và thông báo lỗi viết **tiếng Việt**, theo đúng mật độ và giọng của mã hiện có.
- Không chạy `seed_demo` (mật khẩu demo là công khai trên GitHub).
- Tên khoa phòng so trùng **không dấu** qua `miyano_portal.kho.similarity.la_trung_tuyet_doi`, **không** dùng unique index của MariaDB — hai phép so lệch nhau tạo khe hở.

---

## File Structure

| File | Trách nhiệm |
|---|---|
| `miyano_portal/dat_hang.py` *(mới)* | Lõi tạo Sales Order từ giỏ hàng, **nhận `customer` làm tham số** thay vì đọc phiên đăng nhập. Dùng chung cho đường đặt trực tiếp và (sau này) đường duyệt đề nghị |
| `miyano_portal/miyano_portal/doctype/portal_member/` *(mới)* | Doctype thành viên cổng + `validate` chặn hai luật |
| `miyano_portal/portal_context.py` *(sửa)* | Đọc `Portal Member`; thêm `get_portal_member`, `la_quan_ly`, `pham_vi_don`, `dam_bao_xem_duoc` |
| `miyano_portal/api/portal.py` *(sửa)* | `portal_order_place` thành vỏ mỏng; các endpoint đơn hàng áp phạm vi |
| `miyano_portal/portal_thong_bao_khach.py` *(sửa)* | `_portal_users_cua_khach` đọc `Portal Member` |
| `miyano_portal/miyano_portal/doctype/customer_department/` *(sửa)* | Thêm `customer`, chuyển chốt trùng tên sang khoá `customer`, siết `ma_khoa` |
| `miyano_portal/patches/v1_23/` *(mới)* | Bốn patch: field khoa phòng, `Customer.custom_ma_ngan`, `Sales Order.custom_khoa_phong`, backfill `Portal Member` |
| `miyano_portal/tests/test_portal_member.py` *(mới)* | Test danh tính, phạm vi, tương thích ngược |
| `miyano_portal/tests/test_pham_vi_endpoint.py` *(mới)* | Test đếm ngược cho endpoint whitelist |

---

## Task 1: Tách lõi đặt hàng ra `dat_hang.py`

Không đổi hành vi. Chỉ chuyển chỗ ở của mã, để đường "duyệt đề nghị" sau này gọi được cùng một lõi — hai chỗ tính giá và kiểm hạn mức là hai chỗ sẽ lệch.

**Files:**
- Create: `miyano_portal/dat_hang.py`
- Modify: `miyano_portal/api/portal.py` (hàm `portal_order_place`, dòng 805–944)
- Test: `miyano_portal/tests/test_dat_hang_core.py` *(mới)*

**Interfaces:**
- Consumes: `_xay_don_ban_le`, `_xay_don_hdnt`, `_insert_so_idempotent`, `dam_bao_duoc_mua_le`, `ngay_giao_mac_dinh`, `_customer_addresses` (đã có trong `api/portal.py`)
- Produces:
  ```python
  def tao_sales_order(
      customer: str, *, mode: str = "hdnt", contract=None, items=None,
      dat_ngoai=None, po=None, delivery_date=None, note=None, address=None,
      request_id=None, khoa_phong=None,
  ) -> dict:
      """Trả {"sales_order": str, "da_ton_tai": bool, "total": float}"""
  ```
  `khoa_phong` ở task này **chỉ nhận và bỏ qua** (chưa có field để ghi) — Task 8 nối nó vào.

- [ ] **Step 1: Viết test đỏ — lõi nhận `customer` làm tham số, không đọc phiên**

Tạo `miyano_portal/tests/test_dat_hang_core.py`:

```python
"""Lõi đặt hàng tách khỏi endpoint (bước 1 của kế hoạch nền phân quyền).

Điểm của bộ test này KHÔNG phải là "đặt hàng chạy được" — chuyện đó đã có
test_e6_*/test_e2_* lo. Nó chốt đúng một tính chất mới: lõi **nhận customer
làm tham số** thay vì suy từ phiên đăng nhập, để đường duyệt đề nghị sau này
gọi được cùng một lõi khi người bấm duyệt KHÁC người đặt.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import dat_hang

KHACH_BM = "Bệnh viện Bạch Mai"


class TestLoiDatHangNhanCustomerLamThamSo(FrappeTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_tao_duoc_don_khi_chay_duoi_administrator(self):
		"""Administrator KHÔNG có Contact nào trỏ tới khách hàng nào, nên nếu
		lõi còn gọi get_portal_customer() thì test này ném PermissionError."""
		frappe.set_user("Administrator")
		ket_qua = dat_hang.tao_sales_order(
			KHACH_BM,
			mode="ban_le",
			items=[{"item_code": "MYN-GLOVE-M", "qty": 2}],
			request_id=frappe.generate_hash(length=20),
		)
		self.assertTrue(ket_qua["sales_order"])
		self.assertEqual(
			frappe.db.get_value("Sales Order", ket_qua["sales_order"], "customer"),
			KHACH_BM,
		)
```

- [ ] **Step 2: Chạy để thấy đỏ**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --module miyano_portal.tests.test_dat_hang_core`
Expected: FAIL với `ModuleNotFoundError: No module named 'miyano_portal.dat_hang'`

- [ ] **Step 3: Chuyển thân hàm sang `dat_hang.py`**

Tạo `miyano_portal/dat_hang.py` chứa **nguyên văn** thân `portal_order_place` từ dòng ngay sau `customer = get_portal_customer()` tới hết, đổi chữ ký thành `tao_sales_order(customer, *, mode="hdnt", ...)`. Không sửa một dòng logic nào. Các hàm phụ trợ (`_xay_don_ban_le`, `_xay_don_hdnt`, `_insert_so_idempotent`, `dam_bao_duoc_mua_le`, `ngay_giao_mac_dinh`, `_customer_addresses`) **chuyển sang cùng file này**, và `api/portal.py` import lại từ đây nếu còn chỗ khác dùng.

Đầu file:

```python
"""Lõi đặt hàng — dựng dòng hàng, kiểm hạn mức HĐNT, định giá, tạo Sales Order.

Tách khỏi `api/portal.py` ngày 18/08/2026 (bước 1,
`docs/superpowers/plans/2026-08-18-nen-phan-quyen-khoa-phong.md`) vì sắp có
đường thứ hai đi vào đây: quản lý bệnh viện DUYỆT một `Đề nghị mua` của khoa
phòng. Ở đường đó, người bấm nút KHÁC người đặt hàng, nên lõi không được suy
khách hàng từ phiên đăng nhập nữa — nó NHẬN `customer` làm tham số, và việc
xác định khách hàng thuộc về người gọi.

Hai đường tính giá và kiểm hạn mức là hai đường sẽ lệch nhau. Chỉ có một.
"""
```

- [ ] **Step 4: `portal_order_place` thành vỏ mỏng**

```python
@frappe.whitelist()
def portal_order_place(
    contract=None, items=None, po=None, delivery_date=None, note=None, address=None,
    request_id=None, mode="hdnt", dat_ngoai=None,
) -> dict:
    """API Spec §1.1. Vỏ mỏng: xác định khách hàng từ PHIÊN ĐĂNG NHẬP rồi giao
    cho `dat_hang.tao_sales_order`. Chữ ký giữ NGUYÊN (`frontend/src/views/
    Cart.vue` đang gọi) — đổi tên tham số ở đây là đổi API mà không có gì buộc
    phía SPA phải đổi theo."""
    return dat_hang.tao_sales_order(
        get_portal_customer(),
        mode=mode, contract=contract, items=items, dat_ngoai=dat_ngoai,
        po=po, delivery_date=delivery_date, note=note, address=address,
        request_id=request_id,
    )
```

- [ ] **Step 5: Chạy test mới + toàn bộ suite**

Run: `bench --site erptest.local run-tests --module miyano_portal.tests.test_dat_hang_core`
Expected: PASS

Run: `bench --site erptest.local run-tests --app miyano_portal`
Expected: `OK`. **Nếu có test cũ đỏ → dừng lại.** Việc tách lõi không được đổi hành vi; một test cũ đỏ nghĩa là đã đổi.

- [ ] **Step 6: Commit**

```bash
git add miyano_portal/dat_hang.py miyano_portal/api/portal.py miyano_portal/tests/test_dat_hang_core.py
git commit -m "refactor(dat-hang): tách lõi tạo Sales Order khỏi endpoint cổng

Lõi nhận customer làm tham số thay vì suy từ phiên đăng nhập, để đường
duyệt đề nghị mua (người bấm khác người đặt) dùng chung được. Không đổi
một dòng logic nào; portal_order_place thành vỏ mỏng, chữ ký giữ nguyên
cho Cart.vue. Suite xanh không sửa test cũ nào."
```

---

## Task 2: `Customer Department` chuyển khoá từ kho sang khách hàng

**Files:**
- Modify: `miyano_portal/miyano_portal/doctype/customer_department/customer_department.json`
- Modify: `miyano_portal/miyano_portal/doctype/customer_department/customer_department.py`
- Create: `miyano_portal/patches/v1_23/__init__.py`, `miyano_portal/patches/v1_23/khoa_phong_theo_khach_hang.py`
- Modify: `miyano_portal/patches.txt`
- Test: `miyano_portal/tests/test_khoa_phong_theo_khach.py` *(mới)*

**Interfaces:**
- Produces: `Customer Department.customer` (Link Customer, reqd, search_index), `ma_khoa` viết hoa và duy nhất trong một khách hàng.

- [ ] **Step 1: Viết test đỏ**

```python
"""Khoa phòng thuộc về BỆNH VIỆN, không thuộc về kho (bước 2).

Lý do đổi: đặt hàng thì bệnh viện nào cũng làm, kho thì chỉ vài bệnh viện
có. Giữ khoá theo kho thì khách chưa mở kho (Hi-medic) không có khoa phòng
nào để mà phân quyền.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

KHACH_BM = "Bệnh viện Bạch Mai"


class TestKhoaPhongThuocKhachHang(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Customer Department", {"ten_khoa_phong": ["like", "ZZTEST%"]})

	def _tao(self, ten, ma=None, customer=KHACH_BM):
		return frappe.get_doc({
			"doctype": "Customer Department", "customer": customer,
			"ten_khoa_phong": ten, "ma_khoa": ma,
		}).insert(ignore_permissions=True)

	def test_khai_duoc_khoa_phong_cho_khach_chua_co_kho(self):
		kp = self._tao("ZZTEST Khoa Huyết học")
		self.assertEqual(kp.customer, KHACH_BM)
		self.assertFalse(kp.kho, "không cần kho mới khai được khoa phòng")

	def test_ma_khoa_tu_viet_hoa(self):
		self.assertEqual(self._tao("ZZTEST Hoá sinh", ma="hs").ma_khoa, "HS")

	def test_ma_khoa_chi_nhan_chu_va_so(self):
		with self.assertRaises(frappe.ValidationError):
			self._tao("ZZTEST Xét nghiệm", ma="XN-01")

	def test_ma_khoa_khong_duoc_trung_trong_mot_benh_vien(self):
		self._tao("ZZTEST Khoa A", ma="KA")
		with self.assertRaises(frappe.ValidationError):
			self._tao("ZZTEST Khoa B", ma="ka")

	def test_ma_khoa_CHUNG_la_ma_danh_rieng(self):
		"""`CHUNG` dành cho đơn quản lý đặt "Toàn viện" (spec §5.5)."""
		with self.assertRaises(frappe.ValidationError):
			self._tao("ZZTEST Khoa chung", ma="CHUNG")
```

- [ ] **Step 2: Chạy để thấy đỏ**

Run: `bench --site erptest.local run-tests --module miyano_portal.tests.test_khoa_phong_theo_khach`
Expected: FAIL — `customer` chưa phải field hợp lệ; `ma_khoa` chưa viết hoa.

- [ ] **Step 3: Sửa JSON doctype**

Trong `field_order`, đặt `customer` **trước** `kho`. Thêm/sửa hai field:

```json
{"fieldname": "customer", "fieldtype": "Link", "label": "Khách hàng", "options": "Customer", "reqd": 1, "search_index": 1},
{"fieldname": "kho", "fieldtype": "Link", "label": "Kho", "options": "Customer Warehouse", "search_index": 1, "description": "Tuỳ chọn — khoa phòng thuộc về bệnh viện, không thuộc về kho"}
```

(bỏ `"reqd": 1` khỏi `kho`)

- [ ] **Step 4: Sửa controller**

Trong `customer_department.py`:

```python
	MA_DANH_RIENG = {"CHUNG"}

	def validate(self):
		self.ten_khoa_phong = (self.ten_khoa_phong or "").strip()
		if not self.ten_khoa_phong:
			frappe.throw("Thiếu Tên khoa phòng.", frappe.ValidationError)
		if self.kho:
			# Kho nào cũng phải thuộc đúng bệnh viện của khoa phòng này —
			# không chặn thì một khoa của bệnh viện A trỏ được vào kho của B.
			kho_cua = frappe.db.get_value("Customer Warehouse", self.kho, "customer")
			if kho_cua != self.customer:
				frappe.throw(
					"Kho được chọn không thuộc khách hàng này.", frappe.ValidationError
				)
		self._chuan_hoa_ma_khoa()
		self._chan_trung_tuyet_doi()

	def _chuan_hoa_ma_khoa(self):
		"""Mã khoa đi vào TÊN của phiếu Đề nghị mua (spec §6.1) nên phải là
		một định danh, không phải chữ tự do: viết hoa, chỉ A-Z0-9, không trùng
		trong cùng bệnh viện, và không được lấy mã dành riêng."""
		self.ma_khoa = (self.ma_khoa or "").strip().upper() or None
		if not self.ma_khoa:
			return
		if len(self.ma_khoa) > 20:
			frappe.throw("Mã khoa không được quá 20 ký tự.", frappe.ValidationError)
		if not self.ma_khoa.isalnum() or not self.ma_khoa.isascii():
			frappe.throw(
				"Mã khoa chỉ được dùng chữ cái không dấu và chữ số (ví dụ HUYETHOC).",
				frappe.ValidationError,
			)
		if self.ma_khoa in self.MA_DANH_RIENG:
			frappe.throw(
				f'"{self.ma_khoa}" là mã dành riêng của hệ thống, không đặt cho '
				"khoa phòng được.",
				frappe.ValidationError,
			)
		trung = frappe.db.exists(
			"Customer Department",
			{"customer": self.customer, "ma_khoa": self.ma_khoa, "name": ["!=", self.name or ""]},
		)
		if trung:
			frappe.throw(
				f'Bệnh viện này đã có khoa phòng mang mã "{self.ma_khoa}".',
				frappe.ValidationError,
			)
```

Và trong `_chan_trung_tuyet_doi`, đổi bộ lọc `{"kho": self.kho, ...}` thành `{"customer": self.customer, ...}`, sửa docstring và thông báo lỗi từ "trong cùng một kho" thành "trong cùng một bệnh viện".

- [ ] **Step 5: Viết patch**

`miyano_portal/patches/v1_23/__init__.py` — file rỗng.

`miyano_portal/patches/v1_23/khoa_phong_theo_khach_hang.py`:

```python
"""Điền `Customer Department.customer` từ `kho.customer`, và viết hoa `ma_khoa`.

Chạy MỘT LẦN cho mỗi site. Bản ghi nào không suy ra được khách hàng (kho đã
bị xoá) thì KHÔNG đoán — ghi Error Log để vận hành xử tay, vì đoán sai ở đây
là gán một khoa phòng cho nhầm bệnh viện.
"""

import frappe


def execute():
	rows = frappe.get_all(
		"Customer Department", fields=["name", "kho", "customer", "ma_khoa"]
	)
	mo_coi = []
	for r in rows:
		gia_tri = {}
		if not r.customer:
			cust = frappe.db.get_value("Customer Warehouse", r.kho, "customer") if r.kho else None
			if not cust:
				mo_coi.append(r.name)
				continue
			gia_tri["customer"] = cust
		if r.ma_khoa and r.ma_khoa != r.ma_khoa.strip().upper():
			gia_tri["ma_khoa"] = r.ma_khoa.strip().upper()
		if gia_tri:
			frappe.db.set_value("Customer Department", r.name, gia_tri, update_modified=False)

	if mo_coi:
		frappe.log_error(
			title="Khoa phòng không suy ra được khách hàng",
			message=(
				"Các khoa phòng sau không có `kho` hợp lệ để suy ra `customer`, "
				"cần gán tay: " + ", ".join(mo_coi)
			),
		)
```

Thêm dòng cuối `miyano_portal/patches.txt`:

```
miyano_portal.patches.v1_23.khoa_phong_theo_khach_hang
```

- [ ] **Step 6: Chạy patch rồi chạy test**

Run: `bench --site erptest.local migrate`
Expected: patch `khoa_phong_theo_khach_hang` chạy, không lỗi.

Run: `bench --site erptest.local run-tests --module miyano_portal.tests.test_khoa_phong_theo_khach`
Expected: PASS

Run: `bench --site erptest.local run-tests --app miyano_portal`
Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add miyano_portal/miyano_portal/doctype/customer_department/ miyano_portal/patches/v1_23/ miyano_portal/patches.txt miyano_portal/tests/test_khoa_phong_theo_khach.py
git commit -m "feat(khoa-phong): khoa phòng thuộc bệnh viện thay vì thuộc kho

Thêm Customer Department.customer (bắt buộc), hạ kho xuống tuỳ chọn, patch
điền ngược từ kho.customer. Khách chưa mở kho (Hi-medic) giờ khai được khoa
phòng. Siết ma_khoa: viết hoa, chỉ A-Z0-9, duy nhất trong một bệnh viện,
chặn mã dành riêng CHUNG — vì mã khoa sắp đi vào tên phiếu Đề nghị mua."
```

---

## Task 3: `Customer.custom_ma_ngan`

**Files:**
- Create: `miyano_portal/patches/v1_23/them_ma_ngan_khach_hang.py`
- Modify: `miyano_portal/patches.txt`
- Test: thêm class vào `miyano_portal/tests/test_khoa_phong_theo_khach.py`

**Interfaces:**
- Produces: `Customer.custom_ma_ngan` (Data, length 10, unique, có index).

- [ ] **Step 1: Viết test đỏ**

```python
class TestMaNganKhachHang(FrappeTestCase):
	def test_field_ma_ngan_ton_tai_va_unique(self):
		cf = frappe.db.get_value(
			"Custom Field", {"dt": "Customer", "fieldname": "custom_ma_ngan"},
			["fieldtype", "unique", "length"], as_dict=True,
		)
		self.assertIsNotNone(cf, "chưa có Customer.custom_ma_ngan")
		self.assertEqual(cf.fieldtype, "Data")
		self.assertEqual(cf.unique, 1)
		self.assertEqual(cf.length, 10)
```

- [ ] **Step 2: Chạy để thấy đỏ**

Run: `bench --site erptest.local run-tests --module miyano_portal.tests.test_khoa_phong_theo_khach`
Expected: FAIL — `chưa có Customer.custom_ma_ngan`

- [ ] **Step 3: Viết patch**

```python
"""Thêm `Customer.custom_ma_ngan` — mã ngắn của bệnh viện.

Dùng làm phần đầu tên phiếu `Đề nghị mua` (spec §6.1). BẮT BUỘC với khách
dùng cổng, nhưng KHÔNG đặt `reqd=1` trên field: hàng trăm Customer nội bộ
không dùng cổng sẽ không lưu được nữa. Chốt bắt buộc nằm ở
`Portal Member.validate` (Task 4) — kiểm đúng lúc bật tính năng cho một
bệnh viện, không phải lúc nhân viên bấm gửi.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def execute():
	create_custom_field("Customer", {
		"fieldname": "custom_ma_ngan",
		"label": "Mã ngắn (cổng khách)",
		"fieldtype": "Data",
		"length": 10,
		"unique": 1,
		"insert_after": "customer_name",
		"description": "Chữ hoa không dấu, ví dụ BM. Dùng làm phần đầu mã đề nghị mua.",
	})
```

Thêm vào `patches.txt`: `miyano_portal.patches.v1_23.them_ma_ngan_khach_hang`

- [ ] **Step 4: Migrate và chạy test**

Run: `bench --site erptest.local migrate && bench --site erptest.local run-tests --module miyano_portal.tests.test_khoa_phong_theo_khach`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add miyano_portal/patches/v1_23/them_ma_ngan_khach_hang.py miyano_portal/patches.txt miyano_portal/tests/test_khoa_phong_theo_khach.py
git commit -m "feat(khach-hang): thêm Customer.custom_ma_ngan cho mã đề nghị mua"
```

---

## Task 4: Doctype `Portal Member`

**Files:**
- Create: `miyano_portal/miyano_portal/doctype/portal_member/portal_member.json`, `portal_member.py`, `__init__.py`
- Test: `miyano_portal/tests/test_portal_member.py` *(mới)*

**Interfaces:**
- Produces: doctype `Portal Member` (`TVC-.#####`) với `user` (unique), `customer`, `vai_tro`, `khoa_phong`, `active`.

- [ ] **Step 1: Viết test đỏ**

```python
"""`Portal Member` — nguồn sự thật duy nhất cho danh tính cổng (bước 3)."""

import frappe
from frappe.tests.utils import FrappeTestCase

KHACH_BM = "Bệnh viện Bạch Mai"
KHACH_PXN = "PXN ABC"


class _NenThanhVien(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Portal Member", {"user": ["like", "zztest%"]})
		frappe.db.delete("Customer Department", {"ten_khoa_phong": ["like", "ZZTEST%"]})
		self.kp_bm = frappe.get_doc({
			"doctype": "Customer Department", "customer": KHACH_BM,
			"ten_khoa_phong": "ZZTEST Huyết học", "ma_khoa": "ZZHH",
		}).insert(ignore_permissions=True)
		self.kp_pxn = frappe.get_doc({
			"doctype": "Customer Department", "customer": KHACH_PXN,
			"ten_khoa_phong": "ZZTEST Xét nghiệm", "ma_khoa": "ZZXN",
		}).insert(ignore_permissions=True)

	def _user(self, email):
		if not frappe.db.exists("User", email):
			frappe.get_doc({
				"doctype": "User", "email": email, "first_name": "ZZ",
				"user_type": "Website User", "send_welcome_email": 0,
			}).insert(ignore_permissions=True)
		return email

	def _tv(self, email, vai_tro="Quản lý", customer=KHACH_BM, khoa_phong=None):
		return frappe.get_doc({
			"doctype": "Portal Member", "user": self._user(email),
			"customer": customer, "vai_tro": vai_tro, "khoa_phong": khoa_phong,
		}).insert(ignore_permissions=True)


class TestPortalMemberRangBuoc(_NenThanhVien):
	def test_moi_benh_vien_dung_mot_quan_ly_dang_hoat_dong(self):
		self._tv("zztest.ql1@demo.miyano")
		with self.assertRaises(frappe.ValidationError):
			self._tv("zztest.ql2@demo.miyano")

	def test_nhan_vien_khoa_bat_buoc_co_khoa_phong(self):
		with self.assertRaises(frappe.ValidationError):
			self._tv("zztest.nv@demo.miyano", vai_tro="Nhân viên khoa")

	def test_quan_ly_khong_duoc_gan_khoa_phong(self):
		with self.assertRaises(frappe.ValidationError):
			self._tv("zztest.ql3@demo.miyano", khoa_phong=self.kp_bm.name)

	def test_khoa_phong_phai_thuoc_dung_benh_vien(self):
		"""Lỗ phân quyền mở được bằng một thao tác nhập liệu."""
		self._tv("zztest.ql4@demo.miyano")
		with self.assertRaises(frappe.ValidationError):
			self._tv(
				"zztest.nv2@demo.miyano", vai_tro="Nhân viên khoa",
				customer=KHACH_BM, khoa_phong=self.kp_pxn.name,
			)

	def test_mot_user_chi_thuoc_mot_benh_vien(self):
		self._tv("zztest.ql5@demo.miyano")
		with self.assertRaises(Exception):
			self._tv("zztest.ql5@demo.miyano", customer=KHACH_PXN)

	def test_bat_buoc_khach_hang_co_ma_ngan_truoc_khi_cap_tai_khoan_khoa(self):
		"""Kiểm đúng lúc BẬT tính năng, không phải lúc nhân viên bấm gửi."""
		frappe.db.set_value("Customer", KHACH_BM, "custom_ma_ngan", None)
		self._tv("zztest.ql6@demo.miyano")
		with self.assertRaises(frappe.ValidationError):
			self._tv(
				"zztest.nv3@demo.miyano", vai_tro="Nhân viên khoa",
				khoa_phong=self.kp_bm.name,
			)
```

- [ ] **Step 2: Chạy để thấy đỏ**

Run: `bench --site erptest.local run-tests --module miyano_portal.tests.test_portal_member`
Expected: FAIL — `DocType Portal Member not found`

- [ ] **Step 3: Tạo doctype JSON**

`miyano_portal/miyano_portal/doctype/portal_member/portal_member.json`:

```json
{
 "actions": [],
 "allow_rename": 0,
 "autoname": "TVC-.#####",
 "creation": "2026-08-18 00:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 1,
 "engine": "InnoDB",
 "field_order": ["user", "customer", "col_1", "vai_tro", "khoa_phong", "active"],
 "fields": [
  {"fieldname": "user", "fieldtype": "Link", "label": "Tài khoản", "options": "User", "reqd": 1, "unique": 1, "search_index": 1, "in_list_view": 1},
  {"fieldname": "customer", "fieldtype": "Link", "label": "Khách hàng", "options": "Customer", "reqd": 1, "search_index": 1, "in_list_view": 1},
  {"fieldname": "col_1", "fieldtype": "Column Break"},
  {"fieldname": "vai_tro", "fieldtype": "Select", "label": "Vai trò", "options": "Quản lý\nNhân viên khoa", "reqd": 1, "default": "Nhân viên khoa", "in_list_view": 1},
  {"fieldname": "khoa_phong", "fieldtype": "Link", "label": "Khoa phòng", "options": "Customer Department", "search_index": 1, "in_list_view": 1},
  {"fieldname": "active", "fieldtype": "Check", "label": "Hoạt động", "default": "1"}
 ],
 "index_web_pages_for_search": 0,
 "links": [],
 "modified": "2026-08-18 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Miyano Portal",
 "name": "Portal Member",
 "owner": "Administrator",
 "permissions": [
  {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1},
  {"role": "Sales Manager", "read": 1, "write": 1, "create": 1, "report": 1, "export": 1},
  {"role": "Sales User", "read": 1, "report": 1}
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "track_changes": 1
}
```

> Cố ý **không** có DocPerm nào cho role `Customer`: khách không đọc bảng này qua Desk; cổng thật là `api/portal.py`.

`__init__.py`: file rỗng.

- [ ] **Step 4: Viết controller**

`portal_member.py`:

```python
"""Thành viên cổng khách — nguồn sự thật DUY NHẤT cho danh tính cổng.

Trước 18/08/2026 danh tính suy từ `Contact` (field `user`) + `Dynamic Link`.
Cách đó trả lời được "user này thuộc bệnh viện nào" nhưng không mang nổi hai
chiều mới: VAI TRÒ (quản lý / nhân viên khoa) và KHOA PHÒNG. Giữ cả hai
đường song song sẽ tạo hai câu trả lời cho cùng một câu hỏi — nên `Contact`
thôi làm căn cứ phân quyền, chỉ còn giữ email/liên hệ.
"""

import frappe
from frappe.model.document import Document

QUAN_LY = "Quản lý"
NHAN_VIEN_KHOA = "Nhân viên khoa"


class PortalMember(Document):
	def validate(self):
		self._chan_vai_tro_va_khoa_phong()
		self._chan_khoa_cua_benh_vien_khac()
		self._chan_hai_quan_ly()
		self._chan_thieu_ma_ngan()

	def _chan_vai_tro_va_khoa_phong(self):
		if self.vai_tro == NHAN_VIEN_KHOA and not self.khoa_phong:
			frappe.throw(
				"Nhân viên khoa phải được gán một khoa phòng.", frappe.ValidationError
			)
		if self.vai_tro == QUAN_LY and self.khoa_phong:
			frappe.throw(
				"Quản lý nhìn xuyên mọi khoa nên không gắn vào khoa phòng nào. "
				"Bỏ trống ô Khoa phòng.",
				frappe.ValidationError,
			)

	def _chan_khoa_cua_benh_vien_khac(self):
		"""Không chặn thì gán được khoa của bệnh viện khác — một lỗ phân quyền
		mở bằng đúng một thao tác nhập liệu."""
		if not self.khoa_phong:
			return
		cua = frappe.db.get_value("Customer Department", self.khoa_phong, "customer")
		if cua != self.customer:
			frappe.throw(
				"Khoa phòng được chọn không thuộc khách hàng này.", frappe.ValidationError
			)

	def _chan_hai_quan_ly(self):
		"""Mỗi bệnh viện đúng MỘT quản lý đang hoạt động. Nhiều quản lý cùng
		lúc làm khái niệm uỷ quyền tạm thời trở nên vô nghĩa (spec QĐ-KP-4)."""
		if self.vai_tro != QUAN_LY or not self.active:
			return
		da_co = frappe.db.get_value(
			"Portal Member",
			{"customer": self.customer, "vai_tro": QUAN_LY, "active": 1,
			 "name": ["!=", self.name or ""]},
			["name", "user"], as_dict=True,
		)
		if da_co:
			frappe.throw(
				f"Bệnh viện này đã có quản lý là {da_co.user}. Tắt thành viên đó "
				"trước, hoặc đặt tài khoản này là Nhân viên khoa.",
				frappe.ValidationError,
			)

	def _chan_thieu_ma_ngan(self):
		"""Mã ngắn của bệnh viện đi vào tên phiếu Đề nghị mua. Kiểm ĐÚNG LÚC
		bật tính năng khoa phòng cho một bệnh viện — để tới lúc nhân viên bấm
		gửi mới báo thiếu là bắt họ soạn xong rồi mới nhận một lỗi khó hiểu."""
		if self.vai_tro != NHAN_VIEN_KHOA:
			return
		if not frappe.db.get_value("Customer", self.customer, "custom_ma_ngan"):
			frappe.throw(
				f'Khách hàng "{self.customer}" chưa có Mã ngắn. Đặt mã ngắn trước '
				"khi cấp tài khoản theo khoa phòng.",
				frappe.ValidationError,
			)
```

- [ ] **Step 5: Migrate và chạy test**

Run: `bench --site erptest.local migrate && bench --site erptest.local run-tests --module miyano_portal.tests.test_portal_member`
Expected: PASS (6/6)

- [ ] **Step 6: Commit**

```bash
git add miyano_portal/miyano_portal/doctype/portal_member/ miyano_portal/tests/test_portal_member.py
git commit -m "feat(danh-tinh): doctype Portal Member — thành viên cổng theo vai trò và khoa phòng

Nguồn sự thật duy nhất cho danh tính cổng, thay Contact. Bốn luật chặn:
nhân viên khoa phải có khoa phòng, quản lý không được có, khoa phòng phải
thuộc đúng bệnh viện, mỗi bệnh viện đúng một quản lý đang hoạt động. Cộng
một chốt: khách chưa có mã ngắn thì chưa cấp được tài khoản theo khoa."
```

---

## Task 5: `portal_context` đọc `Portal Member` + patch backfill

**Files:**
- Modify: `miyano_portal/portal_context.py`
- Create: `miyano_portal/patches/v1_23/backfill_portal_member.py`
- Modify: `miyano_portal/patches.txt`
- Test: thêm class vào `miyano_portal/tests/test_portal_member.py`

**Interfaces:**
- Consumes: doctype `Portal Member` (Task 4)
- Produces:
  ```python
  def get_portal_member(user: str | None = None) -> frappe._dict   # PermissionError nếu không có
  def la_quan_ly(user: str | None = None) -> bool
  def pham_vi_don(user: str | None = None) -> dict   # {} hoặc {"custom_khoa_phong": "<KP-xxxxx>"}
  ```
  `get_allowed_customers()` giữ **nguyên chữ ký** (trả `list[str]`) — mọi lời gọi hiện có không phải đổi.

- [ ] **Step 1: Viết test đỏ**

```python
from miyano_portal import portal_context


class TestPhamViTheoVaiTro(_NenThanhVien):
	def test_quan_ly_khong_bi_gioi_han_khoa(self):
		tv = self._tv("zztest.ql7@demo.miyano")
		self.assertEqual(portal_context.pham_vi_don(tv.user), {})
		self.assertTrue(portal_context.la_quan_ly(tv.user))

	def test_nhan_vien_khoa_bi_gioi_han_dung_khoa_cua_minh(self):
		frappe.db.set_value("Customer", KHACH_BM, "custom_ma_ngan", "ZZBM")
		self._tv("zztest.ql8@demo.miyano")
		tv = self._tv(
			"zztest.nv4@demo.miyano", vai_tro="Nhân viên khoa",
			khoa_phong=self.kp_bm.name,
		)
		self.assertEqual(
			portal_context.pham_vi_don(tv.user),
			{"custom_khoa_phong": self.kp_bm.name},
		)
		self.assertFalse(portal_context.la_quan_ly(tv.user))

	def test_get_allowed_customers_doc_portal_member(self):
		tv = self._tv("zztest.ql9@demo.miyano")
		self.assertEqual(portal_context.get_allowed_customers(tv.user), [KHACH_BM])

	def test_thanh_vien_da_tat_khong_con_pham_vi_nao(self):
		tv = self._tv("zztest.ql10@demo.miyano")
		frappe.db.set_value("Portal Member", tv.name, "active", 0)
		self.assertEqual(portal_context.get_allowed_customers(tv.user), [])


class TestTuongThichNguoc(FrappeTestCase):
	def test_sau_patch_moi_tai_khoan_cong_cu_deu_la_quan_ly(self):
		"""Ràng buộc tự đặt cho cả đề án: không làm phiền khách đang dùng."""
		for user in ("bvbm@demo.miyano", "bvminhduc@demo.miyano"):
			tv = frappe.db.get_value(
				"Portal Member", {"user": user}, ["vai_tro", "khoa_phong", "active"],
				as_dict=True,
			)
			self.assertIsNotNone(tv, f"{user} chưa có Portal Member sau patch")
			self.assertEqual(tv.vai_tro, "Quản lý")
			self.assertFalse(tv.khoa_phong)
			self.assertEqual(tv.active, 1)
			self.assertEqual(portal_context.pham_vi_don(user), {})
```

- [ ] **Step 2: Chạy để thấy đỏ**

Run: `bench --site erptest.local run-tests --module miyano_portal.tests.test_portal_member`
Expected: FAIL — `module 'miyano_portal.portal_context' has no attribute 'pham_vi_don'`

- [ ] **Step 3: Viết patch backfill**

`miyano_portal/patches/v1_23/backfill_portal_member.py`:

```python
"""Sinh `Portal Member` cho mọi tài khoản cổng đang có.

Tất cả đều thành `Quản lý` KHÔNG gắn khoa phòng → `pham_vi_don()` trả {} →
phạm vi vẫn là toàn bộ đơn của bệnh viện, y hệt trước khi có đề án này. Đây
là ràng buộc tự đặt cho cả đề án: không làm phiền khách đang dùng.

Một bệnh viện lỡ có hai tài khoản (chưa xảy ra trên site nào tính tới
18/08/2026 — đã đo, 6 user / 6 khách) thì tài khoản CŨ NHẤT làm quản lý,
các tài khoản còn lại thành `Nhân viên khoa` KHÔNG gắn khoa và bị TẮT, kèm
Error Log — không đoán ai là quản lý thật.
"""

import frappe


def execute():
	contacts = frappe.get_all(
		"Contact", filters={"user": ["is", "set"]}, fields=["name", "user"]
	)
	cap = {}
	for c in contacts:
		for cust in frappe.get_all(
			"Dynamic Link",
			filters={"parenttype": "Contact", "parent": c.name, "link_doctype": "Customer"},
			pluck="link_name",
		):
			cap.setdefault(cust, []).append(c.user)

	can_xu_tay = []
	for cust, users in cap.items():
		users = sorted(dict.fromkeys(users))
		for i, user in enumerate(users):
			if frappe.db.exists("Portal Member", {"user": user}):
				continue
			la_quan_ly = i == 0
			frappe.get_doc({
				"doctype": "Portal Member", "user": user, "customer": cust,
				"vai_tro": "Quản lý" if la_quan_ly else "Nhân viên khoa",
				"active": 1 if la_quan_ly else 0,
			}).insert(ignore_permissions=True)
			if not la_quan_ly:
				can_xu_tay.append(f"{user} ({cust})")

	if can_xu_tay:
		frappe.log_error(
			title="Portal Member: bệnh viện có nhiều tài khoản, cần gán vai trò tay",
			message=(
				"Các tài khoản sau đã tạo ở trạng thái TẮT vì bệnh viện của họ đã "
				"có quản lý. Vận hành cần gán khoa phòng và bật lại: "
				+ ", ".join(can_xu_tay)
			),
		)
```

Thêm vào `patches.txt`: `miyano_portal.patches.v1_23.backfill_portal_member`

- [ ] **Step 4: Viết lại `portal_context`**

Thay `get_allowed_customers` và thêm ba hàm:

```python
def get_portal_member(user: str | None = None) -> frappe._dict:
    """Bản ghi thành viên cổng của user. Ném PermissionError nếu không có.

    Đây là NGUỒN DUY NHẤT — không có nhánh dự phòng đọc `Contact`. Một
    `Contact` có `user` mà không có `Portal Member` là LỖI CẤU HÌNH (patch
    v1_23 điền cho tài khoản cũ, `portal_provision` tạo cho tài khoản mới),
    không phải một trường hợp hợp lệ cần đỡ. Đỡ nó chính là dựng lại hai
    nguồn sự thật mà việc chuyển đổi này tồn tại để dẹp.
    """
    user = user or frappe.session.user
    tv = frappe.db.get_value(
        "Portal Member", {"user": user, "active": 1},
        ["name", "customer", "vai_tro", "khoa_phong"], as_dict=True,
    )
    if not tv:
        raise frappe.PermissionError("Tài khoản chưa gắn với khách hàng nào.")
    return tv


def get_allowed_customers(user: str | None = None) -> list[str]:
    """Khách hàng của user. Giữ nguyên chữ ký trả LIST (dù mỗi user đúng một
    khách) để mọi lời gọi hiện có không phải đổi."""
    user = user or frappe.session.user
    cust = frappe.db.get_value("Portal Member", {"user": user, "active": 1}, "customer")
    return [cust] if cust else []


def la_quan_ly(user: str | None = None) -> bool:
    """Có quyền quản lý TẠI THỜI ĐIỂM NÀY.

    Hàm này PHỤ THUỘC THỜI GIAN. Bước 7 của đề án thêm uỷ quyền tạm thời và
    vế thứ hai sẽ mọc ra ở đây — mọi nơi gọi phải hỏi hàm này, KHÔNG được tự
    đọc `vai_tro`: người được uỷ quyền vẫn mang vai trò "Nhân viên khoa"
    trong hồ sơ nhưng phải nhìn xuyên mọi khoa trong thời gian uỷ quyền.
    """
    try:
        return get_portal_member(user).vai_tro == "Quản lý"
    except frappe.PermissionError:
        return False


def pham_vi_don(user: str | None = None) -> dict:
    """Điều kiện lọc đơn hàng cho user hiện tại.

    `{}` = không giới hạn theo khoa (vẫn giới hạn theo khách hàng ở chỗ gọi).
    Đây là MỘT trong hai hàm duy nhất được quyết định phạm vi — xem
    `test_pham_vi_endpoint.py` cho chốt "mọi endpoint phải khai báo".
    """
    if la_quan_ly(user):
        return {}
    return {"custom_khoa_phong": get_portal_member(user).khoa_phong}
```

- [ ] **Step 5: Migrate, chạy test, chạy suite**

Run: `bench --site erptest.local migrate`
Expected: patch `backfill_portal_member` chạy xong

Run: `bench --site erptest.local run-tests --module miyano_portal.tests.test_portal_member`
Expected: PASS

Run: `bench --site erptest.local run-tests --app miyano_portal`
Expected: `OK`. Nếu có test cũ đỏ vì `get_allowed_customers` trả rỗng → tài khoản test đó chưa có `Portal Member`; **sửa fixture của test đó**, không thêm nhánh dự phòng vào `portal_context`.

- [ ] **Step 6: Commit**

```bash
git add miyano_portal/portal_context.py miyano_portal/patches/v1_23/backfill_portal_member.py miyano_portal/patches.txt miyano_portal/tests/test_portal_member.py
git commit -m "feat(danh-tinh): portal_context đọc Portal Member, thêm pham_vi_don/la_quan_ly

Contact thôi làm căn cứ phân quyền. Patch sinh Portal Member cho 6 tài
khoản đang có, tất cả là Quản lý không gắn khoa -> phạm vi vẫn là toàn bộ
đơn của bệnh viện, hành vi y hệt trước. la_quan_ly() là hàm phụ thuộc thời
gian (bước 7 thêm uỷ quyền) nên mọi nơi phải hỏi nó, không đọc vai_tro."
```

---

## Task 6: Chiều ngược — `_portal_users_cua_khach` và `portal_provision`

Không làm task này thì lời hứa "một nguồn sự thật" chỉ đúng một chiều: user có `Portal Member` mà không có `Contact` sẽ **không nhận được thông báo nào**, và **mọi tài khoản cấp sau patch đều vô hình** với tầng danh tính mới.

**Files:**
- Modify: `miyano_portal/portal_thong_bao_khach.py` (hàm `_portal_users_cua_khach`, dòng 37–66)
- Modify: `miyano_portal/api/portal.py` (hàm `portal_provision`, dòng 1758)
- Test: thêm class vào `miyano_portal/tests/test_portal_member.py`

**Interfaces:**
- Consumes: `Portal Member` (Task 4), `get_portal_member` (Task 5)

- [ ] **Step 1: Viết test đỏ**

```python
from miyano_portal import portal_thong_bao_khach


class TestChieuNguocDanhTinh(_NenThanhVien):
	def test_nguoi_nhan_thong_bao_lay_tu_portal_member(self):
		"""User có Portal Member nhưng KHÔNG có Contact vẫn phải nhận thông báo."""
		tv = self._tv("zztest.ql11@demo.miyano")
		self.assertFalse(
			frappe.db.exists("Contact", {"user": tv.user}),
			"fixture phải là user KHÔNG có Contact",
		)
		self.assertIn(
			tv.user, portal_thong_bao_khach._portal_users_cua_khach(KHACH_BM)
		)

	def test_thanh_vien_da_tat_khong_nhan_thong_bao(self):
		tv = self._tv("zztest.ql12@demo.miyano")
		frappe.db.set_value("Portal Member", tv.name, "active", 0)
		self.assertNotIn(
			tv.user, portal_thong_bao_khach._portal_users_cua_khach(KHACH_BM)
		)
```

- [ ] **Step 2: Chạy để thấy đỏ**

Run: `bench --site erptest.local run-tests --module miyano_portal.tests.test_portal_member`
Expected: FAIL — `'zztest.ql11@demo.miyano' not found in []`

- [ ] **Step 3: Sửa `_portal_users_cua_khach`**

```python
def _portal_users_cua_khach(customer: str) -> list[str]:
	"""Tài khoản cổng (User) gắn với khách hàng — chiều NGƯỢC của
	`portal_context.get_allowed_customers`.

	Từ 18/08/2026 đọc `Portal Member`, không đi qua `Contact` nữa. Giữ đường
	Contact ở đây trong khi `portal_context` đã chuyển sang `Portal Member`
	sẽ tạo đúng thứ mà việc chuyển đổi này tồn tại để dẹp: hai câu trả lời
	cho một câu hỏi. Cụ thể là hai kiểu sai đối xứng — user có Portal Member
	mà thiếu Contact thì KHÔNG nhận được thông báo nào; user còn Contact cũ
	mà đã tắt Portal Member thì NHẬN thông báo về dữ liệu mình không mở được.

	Chỉ trả User còn `enabled`: `_get_user_ids` của Frappe cũng lọc y hệt,
	báo cho một tài khoản đã khoá là báo cho không ai cả.
	"""
	users = frappe.get_all(
		"Portal Member", filters={"customer": customer, "active": 1}, pluck="user"
	)
	if not users:
		return []
	return frappe.get_all(
		"User", filters={"name": ["in", set(users)], "enabled": 1}, pluck="name"
	)
```

- [ ] **Step 4: Sửa `portal_provision`**

Sau đoạn tạo `Contact` và `User Permission`, thêm:

```python
    # Tài khoản mới PHẢI có Portal Member, nếu không nó vô hình với tầng
    # danh tính (`portal_context.get_portal_member`) và người dùng đăng nhập
    # được nhưng không thấy gì cả. Mặc định `Quản lý` khi bệnh viện chưa có
    # ai, `Nhân viên khoa` (chưa gán khoa, TẮT) khi đã có quản lý — không
    # đoán ai là quản lý thật.
    if not frappe.db.exists("Portal Member", {"user": email}):
        da_co_ql = frappe.db.exists(
            "Portal Member", {"customer": customer, "vai_tro": "Quản lý", "active": 1}
        )
        frappe.get_doc({
            "doctype": "Portal Member", "user": email, "customer": customer,
            "vai_tro": "Nhân viên khoa" if da_co_ql else "Quản lý",
            "active": 0 if da_co_ql else 1,
        }).insert(ignore_permissions=True)
```

- [ ] **Step 5: Chạy test + suite**

Run: `bench --site erptest.local run-tests --module miyano_portal.tests.test_portal_member`
Expected: PASS

Run: `bench --site erptest.local run-tests --app miyano_portal`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add miyano_portal/portal_thong_bao_khach.py miyano_portal/api/portal.py miyano_portal/tests/test_portal_member.py
git commit -m "fix(danh-tinh): chiều ngược Customer->User cũng đọc Portal Member

_portal_users_cua_khach() và portal_provision() còn đi qua Contact trong
khi portal_context đã chuyển — đúng cái hai-nguồn-sự-thật mà việc chuyển
đổi tồn tại để dẹp. Bỏ sót thì user có Portal Member mà thiếu Contact
không nhận thông báo nào, và mọi tài khoản cấp sau patch đều vô hình."
```

---

## Task 7: Test đếm ngược cho endpoint whitelist

Chốt chống lỗi *sẽ* xảy ra sáu tháng nữa, khi ai đó thêm endpoint thứ 28 mà quên phân quyền.

**Files:**
- Create: `miyano_portal/tests/test_pham_vi_endpoint.py`

- [ ] **Step 1: Viết test (task này test CHÍNH LÀ sản phẩm)**

```python
"""Mọi endpoint whitelist phải KHAI BÁO lập trường về phạm vi khoa phòng.

Đây không phải test một hành vi — nó là một cái chốt. Cổng có 27 endpoint ở
`api/portal.py` và 38 ở `api/kho.py`; nếu mỗi cái tự viết điều kiện lọc thì
việc MỘT cái quên lọc là chắc chắn xảy ra. App đã dính đúng kiểu đó hai lần
trong tuần 17–18/08 (phiếu trả hàng lọt vào danh sách đợt giao; phiếu giao
nháp lọt ra cổng khách).

Thêm endpoint mới mà không thêm tên nó vào một trong hai tập dưới đây thì
test này ĐỎ. Đó là toàn bộ mục đích của nó.
"""

import inspect

from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import kho as kho_api
from miyano_portal.api import portal as portal_api

# Endpoint ĐÃ đi qua `pham_vi_don()` hoặc `dam_bao_xem_duoc()`.
DA_AP_PHAM_VI: set[str] = {
	"portal_order_history", "portal_order_track", "portal_dashboard_kpi",
	"portal_deliveries", "portal_invoices", "portal_reorder",
	"portal_order_accept", "portal_order_sua_so_luong", "portal_order_huy",
	"portal_request_cancel", "portal_bao_gia_pdf", "portal_document_download",
	"portal_kiem_hang_get", "portal_kiem_hang_luu", "portal_kiem_hang_gui",
	"portal_einvoice_download", "portal_einvoice_nhap",
	"portal_einvoice_nhap_pdf", "portal_einvoice_ho_tro",
	"portal_thong_bao_list", "portal_thong_bao_doc",
}

# Endpoint CỐ Ý không lọc theo khoa — mỗi cái kèm lý do bằng chữ. Sửa tập
# này là một quyết định phân quyền, không phải một thao tác dọn dẹp.
MIEN_PHAM_VI: dict[str, str] = {
	"portal_me": "hồ sơ của chính người đăng nhập, không có dữ liệu đơn hàng",
	"portal_contracts": "hợp đồng khung ký ở cấp bệnh viện, không thuộc khoa nào",
	"portal_catalog": "danh mục hàng theo hợp đồng — cấp bệnh viện",
	"portal_catalog_ban_le": "danh mục hàng bán lẻ — cấp bệnh viện",
	"portal_order_place": "đường GHI; phạm vi do dat_hang.tao_sales_order chốt",
	"portal_provision": "chỉ nhân viên Miyano gọi, không phải endpoint của khách",
}


class TestMoiEndpointKhaiBaoPhamVi(FrappeTestCase):
	def _endpoints(self, module) -> set[str]:
		return {
			ten for ten, fn in inspect.getmembers(module, inspect.isfunction)
			if getattr(fn, "whitelisted", False) and fn.__module__ == module.__name__
		}

	def test_moi_endpoint_portal_deu_da_khai_bao(self):
		thuc_te = self._endpoints(portal_api)
		da_khai = DA_AP_PHAM_VI | set(MIEN_PHAM_VI)
		chua_khai = thuc_te - da_khai
		self.assertFalse(
			chua_khai,
			"Endpoint chưa khai báo lập trường về phạm vi khoa phòng: "
			f"{sorted(chua_khai)}. Thêm vào DA_AP_PHAM_VI (đã lọc) hoặc "
			"MIEN_PHAM_VI (kèm lý do) trong test này.",
		)

	def test_khong_khai_bao_thua(self):
		"""Tên trong hai tập mà không còn là endpoint nữa → tập đã mục."""
		thuc_te = self._endpoints(portal_api)
		thua = (DA_AP_PHAM_VI | set(MIEN_PHAM_VI)) - thuc_te
		self.assertFalse(thua, f"Khai báo cho endpoint không còn tồn tại: {sorted(thua)}")

	def test_module_kho_chua_ap_pham_vi_la_no_biet_dieu_do(self):
		"""Bước 8 của đề án mới cách ly module kho. Cho tới lúc đó, test này
		giữ CON SỐ để việc thêm endpoint kho mới không lặng lẽ trôi qua."""
		self.assertEqual(
			len(self._endpoints(kho_api)), 38,
			"Số endpoint api/kho.py đã đổi. Bước 8 phân loại 38 cái này thành "
			"13 phải lọc / 8 phải thu hẹp / 17 chặn theo vai trò — xem spec "
			"§7.1c. Cập nhật cả hai chỗ cùng lúc.",
		)
```

- [ ] **Step 2: Chạy — kỳ vọng ĐỎ ở test thứ nhất**

Run: `bench --site erptest.local run-tests --module miyano_portal.tests.test_pham_vi_endpoint`
Expected: FAIL — liệt kê các endpoint chưa khai báo. Đây là bản đồ công việc của Task 8.

> Test này **cố ý để đỏ tới hết Task 8**. Ghi nhận danh sách nó in ra; đó là danh sách phải xử.

- [ ] **Step 3: Commit (test đỏ, có chủ đích)**

```bash
git add miyano_portal/tests/test_pham_vi_endpoint.py
git commit -m "test: chốt đếm ngược — mọi endpoint whitelist phải khai báo phạm vi

CỐ Ý ĐỎ cho tới hết Task 8. Danh sách nó in ra chính là bản đồ công việc.
Thêm endpoint mới mà quên phân quyền thì test này đỏ — đó là mục đích."
```

---

## Task 8: `Sales Order.custom_khoa_phong` và áp phạm vi lên endpoint đơn hàng

**Files:**
- Create: `miyano_portal/patches/v1_23/them_khoa_phong_vao_don_hang.py`
- Modify: `miyano_portal/patches.txt`
- Modify: `miyano_portal/dat_hang.py`, `miyano_portal/api/portal.py`, `miyano_portal/portal_context.py`
- Test: `miyano_portal/tests/test_cach_ly_khoa_phong.py` *(mới)*

**Interfaces:**
- Consumes: `pham_vi_don()` (Task 5)
- Produces: `dam_bao_xem_duoc(doctype: str, name: str) -> None` trong `portal_context`; `Sales Order.custom_khoa_phong`

- [ ] **Step 1: Viết test đỏ — cách ly thật**

```python
"""Cách ly giữa các khoa: khoa A không đọc được chứng từ của khoa B.

Không được lộ CẢ SỰ TỒN TẠI của chứng từ — thông báo lỗi phải giống hệt
trường hợp chứng từ không có thật.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import dat_hang
from miyano_portal.api import portal as portal_api

KHACH_BM = "Bệnh viện Bạch Mai"


class TestCachLyGiuaCacKhoa(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.delete("Portal Member", {"user": ["like", "zzcl%"]})
		frappe.db.delete("Customer Department", {"ten_khoa_phong": ["like", "ZZCL%"]})
		frappe.db.set_value("Customer", KHACH_BM, "custom_ma_ngan", "ZZBM")
		self.kp_a = self._kp("ZZCL Khoa A", "ZZCLA")
		self.kp_b = self._kp("ZZCL Khoa B", "ZZCLB")
		self.ql = self._tv("zzcl.ql@demo.miyano", "Quản lý", None)
		self.nv_a = self._tv("zzcl.a@demo.miyano", "Nhân viên khoa", self.kp_a.name)
		self.nv_b = self._tv("zzcl.b@demo.miyano", "Nhân viên khoa", self.kp_b.name)
		self.don_a = self._don(self.kp_a.name)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _kp(self, ten, ma):
		return frappe.get_doc({
			"doctype": "Customer Department", "customer": KHACH_BM,
			"ten_khoa_phong": ten, "ma_khoa": ma,
		}).insert(ignore_permissions=True)

	def _tv(self, email, vai_tro, khoa_phong):
		if not frappe.db.exists("User", email):
			frappe.get_doc({
				"doctype": "User", "email": email, "first_name": "ZZ",
				"user_type": "Website User", "send_welcome_email": 0,
			}).insert(ignore_permissions=True)
		return frappe.get_doc({
			"doctype": "Portal Member", "user": email, "customer": KHACH_BM,
			"vai_tro": vai_tro, "khoa_phong": khoa_phong,
		}).insert(ignore_permissions=True)

	def _don(self, khoa_phong):
		kq = dat_hang.tao_sales_order(
			KHACH_BM, mode="ban_le",
			items=[{"item_code": "MYN-GLOVE-M", "qty": 2}],
			request_id=frappe.generate_hash(length=20), khoa_phong=khoa_phong,
		)
		return kq["sales_order"]

	def test_don_ghi_dung_khoa_phong(self):
		self.assertEqual(
			frappe.db.get_value("Sales Order", self.don_a, "custom_khoa_phong"),
			self.kp_a.name,
		)

	def test_khoa_khac_khong_doc_duoc_chi_tiet_don(self):
		frappe.set_user(self.nv_b.user)
		with self.assertRaises(frappe.PermissionError):
			portal_api.portal_order_track(self.don_a)

	def test_khoa_khac_khong_thay_don_trong_danh_sach(self):
		frappe.set_user(self.nv_b.user)
		ds = portal_api.portal_order_history()
		self.assertNotIn(self.don_a, [r["name"] for r in ds["rows"]])

	def test_chinh_khoa_do_van_doc_duoc(self):
		frappe.set_user(self.nv_a.user)
		self.assertEqual(portal_api.portal_order_track(self.don_a)["order"], self.don_a)

	def test_quan_ly_doc_duoc_don_cua_moi_khoa(self):
		frappe.set_user(self.ql.user)
		self.assertEqual(portal_api.portal_order_track(self.don_a)["order"], self.don_a)

	def test_don_khong_co_that_va_don_khoa_khac_bao_loi_GIONG_NHAU(self):
		"""Không được lộ cả sự tồn tại của chứng từ."""
		frappe.set_user(self.nv_b.user)
		with self.assertRaises(frappe.PermissionError) as khoa_khac:
			portal_api.portal_order_track(self.don_a)
		with self.assertRaises(frappe.PermissionError) as khong_co:
			portal_api.portal_order_track("SAL-ORD-KHONG-CO-THAT")
		self.assertEqual(str(khoa_khac.exception), str(khong_co.exception))
```

- [ ] **Step 2: Chạy để thấy đỏ**

Run: `bench --site erptest.local run-tests --module miyano_portal.tests.test_cach_ly_khoa_phong`
Expected: FAIL — `custom_khoa_phong` chưa tồn tại; `portal_order_track` chưa chặn.

- [ ] **Step 3: Patch thêm field**

`miyano_portal/patches/v1_23/them_khoa_phong_vao_don_hang.py`:

```python
"""Thêm `Sales Order.custom_khoa_phong`.

Chỉ đọc, ghi lúc tạo đơn. Thứ dẫn xuất (phiếu giao, hoá đơn, biên bản kiểm)
CỐ Ý không có field riêng — chúng lọc qua đơn cha, để không bao giờ có
chuyện phiếu giao nói khoa A còn đơn nói khoa B.

Đơn CŨ để trống: chúng thuộc thời kỳ một-bệnh-viện-một-tài-khoản, không quy
về khoa nào được, và `pham_vi_don()` cho quản lý thấy hết nên không đơn nào
biến mất khỏi màn hình ai cả.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def execute():
	create_custom_field("Sales Order", {
		"fieldname": "custom_khoa_phong",
		"label": "Khoa phòng",
		"fieldtype": "Link",
		"options": "Customer Department",
		"read_only": 1,
		"search_index": 1,
		"insert_after": "custom_so_po_khach",
	})
```

Thêm vào `patches.txt`: `miyano_portal.patches.v1_23.them_khoa_phong_vao_don_hang`

- [ ] **Step 4: Ghi `khoa_phong` khi tạo đơn**

Trong `dat_hang.tao_sales_order`, sau khi dựng `so` và trước `_insert_so_idempotent`:

```python
    # Khoa phòng đứng tên đơn — nguồn của MỌI phép lọc theo khoa về sau
    # (phiếu giao, hoá đơn, biên bản kiểm đều lọc qua đơn cha, không có
    # field riêng). `None` = đơn cấp bệnh viện, chỉ quản lý thấy.
    if khoa_phong:
        cua = frappe.db.get_value("Customer Department", khoa_phong, "customer")
        if cua != customer:
            raise frappe.PermissionError("Khoa phòng không thuộc đơn vị của bạn.")
        so.custom_khoa_phong = khoa_phong
```

- [ ] **Step 5: Thêm `dam_bao_xem_duoc` vào `portal_context`**

```python
LOI_KHONG_THAY = "Không tìm thấy chứng từ."


def dam_bao_xem_duoc(doctype: str, name: str) -> None:
    """Chặn ở mọi endpoint ĐỌC MỘT chứng từ.

    Thông báo lỗi CỐ Ý giống hệt cho hai trường hợp "không có thật" và "của
    khoa khác": phân biệt hai cái đó là để lộ sự tồn tại của chứng từ, và
    trong bệnh viện thì "khoa Dược có đơn mã X" đã là thông tin.

    `Sales Order` mang `custom_khoa_phong` trực tiếp; mọi doctype khác quy về
    đơn cha — MỘT nguồn sự thật, không nhân bản field khoa phòng đi các nơi.
    """
    pham_vi = pham_vi_don()
    if not pham_vi:
        return
    if doctype == "Sales Order":
        cua = frappe.db.get_value("Sales Order", name, "custom_khoa_phong")
    else:
        raise NotImplementedError(
            f"dam_bao_xem_duoc chưa biết quy {doctype} về đơn cha — "
            "thêm nhánh ở đây, đừng viết điều kiện lọc rời tại endpoint."
        )
    if cua != pham_vi["custom_khoa_phong"]:
        raise frappe.PermissionError(LOI_KHONG_THAY)
```

> Nhánh cho `Delivery Note` / `Sales Invoice` / `Portal Delivery Inspection` thêm ở đây khi Task 8 xử tới endpoint tương ứng — **mỗi nhánh kèm một test cách ly riêng**, không gộp.

- [ ] **Step 6: Áp lên từng endpoint trong `DA_AP_PHAM_VI`**

Với mỗi endpoint **đọc một chứng từ**, thêm `dam_bao_xem_duoc(...)` ngay sau bước kiểm khách hàng đã có. Với mỗi endpoint **liệt kê**, trộn `pham_vi_don()` vào bộ lọc. Làm **từng endpoint một**, mỗi cái kèm một test cách ly như mẫu ở Step 1, commit riêng.

- [ ] **Step 7: Chạy hết**

Run: `bench --site erptest.local migrate`
Run: `bench --site erptest.local run-tests --module miyano_portal.tests.test_cach_ly_khoa_phong`
Expected: PASS

Run: `bench --site erptest.local run-tests --module miyano_portal.tests.test_pham_vi_endpoint`
Expected: PASS — test đếm ngược từ Task 7 giờ mới được xanh.

Run: `bench --site erptest.local run-tests --app miyano_portal`
Expected: `OK`

- [ ] **Step 8: Chứng minh RED cho một test cách ly**

Bỏ tạm dòng `if cua != pham_vi["custom_khoa_phong"]: raise ...` trong `dam_bao_xem_duoc`, chạy lại `test_cach_ly_khoa_phong`, **xác nhận nó đỏ đúng chỗ**, rồi trả lại. Một test cách ly không bao giờ đỏ là một test không kiểm gì cả.

Ghi kết quả bước này vào thông điệp commit.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(phan-quyen): Sales Order.custom_khoa_phong và chốt phạm vi theo khoa

pham_vi_don() vào mọi endpoint liệt kê, dam_bao_xem_duoc() vào mọi endpoint
đọc một chứng từ. Thứ dẫn xuất lọc qua đơn cha, không nhân bản field khoa
phòng. Lỗi 'của khoa khác' và 'không có thật' báo giống hệt nhau.

Test đếm ngược (Task 7) giờ mới xanh. Đã chứng minh RED: bỏ vế chặn trong
dam_bao_xem_duoc -> test cách ly đỏ đúng chỗ, rồi trả lại."
```

---

## Task 9: Nghiệm thu — chưa gán khoa thì không gì đổi

**Files:**
- Test: thêm class vào `miyano_portal/tests/test_cach_ly_khoa_phong.py`

- [ ] **Step 1: Viết test**

```python
class TestKhongLamPhienKhachDangDung(FrappeTestCase):
	"""Ràng buộc tự đặt cho cả đề án. Sau bốn bước nền, mọi tài khoản hiện có
	là Quản lý không gắn khoa → thấy đúng những gì họ thấy hôm qua."""

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_tai_khoan_cu_van_thay_toan_bo_don_cua_benh_vien(self):
		frappe.set_user("bvbm@demo.miyano")
		ds = portal_api.portal_order_history(limit=100)
		frappe.set_user("Administrator")
		that = frappe.db.count("Sales Order", {"customer": KHACH_BM, "docstatus": ["<", 2]})
		self.assertEqual(ds["tong"], that)

	def test_tai_khoan_cu_khong_bi_gioi_han_khoa_nao(self):
		from miyano_portal import portal_context
		self.assertEqual(portal_context.pham_vi_don("bvbm@demo.miyano"), {})
```

- [ ] **Step 2: Chạy**

Run: `bench --site erptest.local run-tests --module miyano_portal.tests.test_cach_ly_khoa_phong`
Expected: PASS

- [ ] **Step 3: Chạy toàn bộ suite lần cuối**

Run: `bench --site erptest.local run-tests --app miyano_portal`
Expected: `OK`, và **số test tăng đúng bằng số test mới thêm** — không test cũ nào bị xoá hay sửa.

- [ ] **Step 4: Commit và đẩy**

```bash
git add miyano_portal/tests/test_cach_ly_khoa_phong.py
git commit -m "test: nghiệm thu — tài khoản cũ không đổi hành vi sau bốn bước nền"
git push origin main
```

---

## Sau kế hoạch này

Bước 5–9 của spec (`Đề nghị mua`, màn duyệt, uỷ quyền, cách ly kho, màn thành viên) cần **một kế hoạch riêng**, viết sau khi bốn bước nền đã chạy thật trên site một thời gian. Năm câu hỏi còn mở ở §12 của spec phải có câu trả lời trước khi lập kế hoạch đó.
