# `Đề xuất mua` — Kế hoạch thi công (bước 5, phần nền)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dựng chứng từ `Đề xuất mua` với đầy đủ vòng đời, mã đề xuất, và đường duyệt sinh ra Sales Order — **toàn bộ ở tầng backend**, không đụng một dòng Vue nào.

**Architecture:** Một doctype mới `Portal De Xuat Mua` (+ child) làm chứng từ đứng trước mọi Sales Order của cổng. Vòng đời là một máy trạng thái viết tay trên field `trang_thai` (theo đúng khuôn `Portal Item Request` đã chạy, **không** dùng module Workflow của Frappe). Phạm vi theo khoa được đóng **ở tầng hook** (`permission_query_conditions` + `has_permission`) trước, tầng endpoint sau — ngược lại thứ tự đã làm hỏng bước 4. Đường duyệt gọi lại `dat_hang.tao_sales_order` đã có, không viết đường tạo đơn thứ hai.

**Tech Stack:** Frappe v15.113.4, ERPNext (bản Miyano), MariaDB `utf8mb4_unicode_ci`, site `erptest.local`. Vue 3 SPA — **ngoài phạm vi kế hoạch này**.

**Spec:** `docs/superpowers/specs/2026-08-18-phan-quyen-khoa-phong-va-duyet-don-design.md` (§5, §6.1, §6.2)

**Kế hoạch này KHÔNG bao gồm:** ô tìm theo vật tư (§6.3) và mọi màn hình (§10) → kế hoạch B; uỷ quyền tạm thời (§5.7) → kế hoạch C. Xem "Sau kế hoạch này" ở cuối.

## Global Constraints

- **TDD bắt buộc.** Không viết code sản xuất trước khi có test đỏ và đã **nhìn thấy** nó đỏ **đúng lý do đã ghi trong plan**. Đỏ vì `ImportError` khi plan nói "đỏ vì thiếu guard" là **chưa đạt** — sửa test cho nó đỏ đúng chỗ rồi mới đi tiếp.
- **Mọi test cách ly phải có VẾ DƯƠNG.** Cấm test chỉ khẳng định "khoa A không thấy của khoa B". Mỗi test cách ly phải khẳng định **cả hai**: khoa A **không** thấy của khoa B, **và** khoa A **có** thấy của chính mình. Thiếu vế dương thì `return []` cũng qua bài — đúng lỗi đã lọt ở bước 4, nơi bộ test xanh trong khi tính năng chết hẳn.
- **Mỗi endpoint mới phải khai tập trong `test_pham_vi_endpoint.py` NGAY TRONG TASK sinh ra nó.** Không được để task sau dọn. Khai vào `MIEN_PHAM_VI` là một **quyết định phân quyền** — phải kèm lý do bằng chữ, không phải một thao tác làm cho test hết đỏ.
- Sau mọi task: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal` phải **xanh**. Suite nền là **1135 test**.
- **Đúng MỘT tiến trình test chạy trên bench này tại một thời điểm.** Chạy chồng sẽ sinh hàng chục `Deadlock found when trying to get lock` — lỗi giả, không phải hồi quy.
- **Mọi `assertRaises(ValidationError)` phải khẳng định cả THÔNG ĐIỆP.** **đã kiểm `frappe/exceptions.py` trên v15.113.4** — `MandatoryError` VÀ `DoesNotExistError` đều là **con** của `ValidationError`. Nên một phiếu thiếu field bắt buộc, hoặc một fixture gõ sai tên, đều làm test xanh vì lý do hoàn toàn khác thứ test định canh. (`PermissionError` kế thừa thẳng `Exception` — bare `assertRaises` với nó là an toàn.) Dùng `with self.assertRaises(...) as ctx:` rồi `self.assertIn("<chữ đặc trưng>", str(ctx.exception))`. Không có ngoại lệ.
- **Không sửa test cũ.** Nếu buộc phải sửa: dừng lại, báo cáo, và chỉ được sửa khi có **cả ba**: (a) nêu rõ hành vi cũ nào đổi, (b) chứng minh test sửa xong vẫn **ĐỎ** trước khi có code mới, (c) người review chấp thuận.
- `FrappeTestCase` rollback **một lần cho cả CLASS**, không phải từng test → fixture tự dọn trong `setUp`.
- `frappe.db.delete(...)` là SQL thô, **không** cascade sang child table. Dọn fixture có child phải dùng `frappe.delete_doc(..., force=True)`.
- Patch mới đặt ở `miyano_portal/patches/v1_24/`, khai trong `patches.txt`. Patch chạy **đúng một lần mỗi site**.
- Bình luận và thông báo lỗi viết **tiếng Việt**, theo đúng mật độ và giọng của mã hiện có.
- Không chạy `seed_demo` (mật khẩu demo công khai trên GitHub).
- Nhánh: `feat/de-xuat-mua`, tách từ `feat/nen-phan-quyen-khoa-phong`. Commit sau mỗi task.

---

## Quyết định đã chốt trong kế hoạch này

Ba thứ spec để mở, chốt ở đây để người thi công không phải đoán:

**QĐ-A1 — Tên doctype là ASCII: `Portal De Xuat Mua`, child `Portal De Xuat Mua Item`.**
Spec §5.2 viết "Đề xuất mua" (có dấu). Mọi doctype hiện có của app đều ASCII, kể cả tiếng Việt không dấu (`Sales Order Dat Ngoai Item`). Tên có dấu tạo bảng `tabĐề xuất mua` và thư mục module `đề_xuất_mua` — import Python và đường dẫn file thành gánh nặng vĩnh viễn. Tên doctype **gần như không lộ ra người dùng**: Miyano không có DocPerm (§5.1), khách dùng SPA Vue tự đặt nhãn. Chữ "Đề xuất mua" có dấu vẫn dùng ở **mọi** nhãn và thông báo.
*Sai thì mất gì:* đổi tên doctype sau khi có dữ liệu là một patch rename bảng — làm được nhưng phiền. Chốt bây giờ rẻ hơn.

**QĐ-A2 — `so_luong_de_xuat` khoá bằng `validate()`, chấp nhận `db_set` đi vòng.**
§5.3 nói khoá "kể cả Miyano". `validate()` chặn mọi đường qua `Document.save()`. `frappe.db.set_value`/`doc.db_set()` vẫn đi vòng được — đây là giới hạn đã biết của Frappe, cùng loại với `_chan_hai_quan_ly` trong `portal_member.py`. Không dựng trigger DB: Miyano **không có DocPerm nào** trên doctype này nên không có màn desk nào để bấm, và không đường code nào trong app gọi `db_set` lên field này. Guard ở `validate()` là đủ **trên thực tế**; ghi rõ giới hạn vào docstring thay vì giả vờ nó tuyệt đối.
*Sai thì mất gì:* một script chạy tay có thể sửa số lượng gốc mà không để lại dấu. Chấp nhận được vì chỉ Miyano chạy được script, và Miyano không phải bên bị kiểm soát ở đây.

**QĐ-A3 — Quản lý ở bệnh viện chưa có `custom_ma_ngan` thì bị chặn với thông báo tự xử lý được.**
`_chan_thieu_ma_ngan` chỉ ràng `Nhân viên khoa` (đã kiểm: guard `return` sớm khi `vai_tro != NHAN_VIEN_KHOA`). Nên một bệnh viện **chỉ có quản lý** có thể chưa có mã ngắn — mà mã ngắn là đoạn đầu của **mọi** mã đề xuất, kể cả đơn `CHUNG` của quản lý (§5.5). Không tự sinh mã thay: một mã tự đoán sẽ đi vào tên chứng từ vĩnh viễn.
*Sai thì mất gì:* nếu chủ đầu tư muốn quản lý đặt hàng được ngay không cần mã ngắn, thì chỗ phải sửa là §6.1 (bỏ đoạn mã bệnh viện), không phải chỗ này.

**QĐ-A4 — Hai mã song song, không thay thế nhau (chủ đầu tư chốt 19/08).**
Khách hàng nhìn thấy **mã của họ** (`DXA-HUYETHOC-260819-01`); Miyano nhìn thấy **cả hai**; hoá đơn ghi **mã của bên đặt**; nhưng bản ghi nhận trên hệ thống **vẫn là `SAL-ORD-*` tự sinh**. Nghĩa là: `Sales Order.name` **không đổi** (§11 mục 4 đã chốt không đổi tên 102 đơn cũ), `custom_ma_tra_cuu` là chỗ chứa mã khách, và mọi nơi **hiển thị** cho khách phải đọc `custom_ma_tra_cuu` trước, rơi về `name` khi rỗng.
Kế hoạch này chỉ **ghi dữ liệu và phơi qua API**. Việc **hiển thị** (cổng khách, màn desk Miyano) thuộc kế hoạch B; **mẫu in hoá đơn** là việc riêng chưa có kế hoạch.
*Sai thì mất gì:* nếu chủ đầu tư thật sự muốn đổi luôn `Sales Order.name` thành mã khách, đó là một patch rename 102 đơn + mọi link trỏ tới chúng — việc lớn hơn nhiều và đi ngược §11 mục 4.

---

## File Structure

| File | Trách nhiệm |
|---|---|
| `miyano_portal/miyano_portal/doctype/portal_de_xuat_mua/` *(mới)* | Doctype cha: field, guard cấu trúc, máy trạng thái, `on_trash` |
| `miyano_portal/miyano_portal/doctype/portal_de_xuat_mua_item/` *(mới)* | Child table dòng hàng |
| `miyano_portal/ma_de_xuat.py` *(mới)* | **Chỉ một việc**: sinh mã `BM-HUYETHOC-260817-01`. Tách riêng vì đây là chỗ duy nhất có tranh chấp đồng thời, cần test riêng |
| `miyano_portal/de_xuat_duyet.py` *(mới)* | Lõi duyệt: kiểm hạn mức, tính lại giá, gọi `dat_hang.tao_sales_order`. Tách khỏi endpoint theo đúng khuôn `dat_hang.py` |
| `miyano_portal/permissions.py` *(sửa)* | Hook phạm vi cho doctype mới |
| `miyano_portal/hooks.py` *(sửa)* | Khai `permission_query_conditions` + `has_permission` |
| `miyano_portal/api/de_xuat.py` *(mới)* | Endpoint cổng — module riêng, **phải thêm vào test đếm ngược** |
| `miyano_portal/api/portal.py` *(sửa)* | `portal_order_place` đi qua đường đề xuất (§5.5) |
| `miyano_portal/portal_thong_bao_khach.py` *(sửa)* | Chọn người nhận theo khoa (§5.8) |
| `miyano_portal/patches/v1_24/` *(mới)* | `Sales Order.custom_de_xuat` + `custom_ma_tra_cuu` |
| `miyano_portal/tests/test_de_xuat_doctype.py` *(mới)* | Guard cấu trúc + vòng đời |
| `miyano_portal/tests/test_ma_de_xuat.py` *(mới)* | Sinh mã, đếm theo ngày, tràn 3 chữ số |
| `miyano_portal/tests/test_de_xuat_cach_ly.py` *(mới)* | Cách ly **qua `frappe.get_list`**, không qua endpoint |
| `miyano_portal/tests/test_de_xuat_duyet.py` *(mới)* | Đường duyệt, hạn mức, giá |
| `miyano_portal/tests/test_de_xuat_endpoint.py` *(mới)* | Endpoint cổng |

---

## Task 1: Doctype `Portal De Xuat Mua` + child

**Files:**
- Create: `miyano_portal/miyano_portal/doctype/portal_de_xuat_mua_item/portal_de_xuat_mua_item.json`
- Create: `miyano_portal/miyano_portal/doctype/portal_de_xuat_mua_item/portal_de_xuat_mua_item.py`
- Create: `miyano_portal/miyano_portal/doctype/portal_de_xuat_mua/portal_de_xuat_mua.json`
- Create: `miyano_portal/miyano_portal/doctype/portal_de_xuat_mua/portal_de_xuat_mua.py`
- Test: `miyano_portal/tests/test_de_xuat_doctype.py`

**Interfaces:**
- Produces: doctype `Portal De Xuat Mua` với field `customer`, `khoa_phong`, `loai_don`, `hdnt`, `ngay_can`, `dia_chi_giao`, `ghi_chu`, `trang_thai`, `request_id`, `nguoi_yeu_cau`, `thoi_diem_gui`, `ly_do_yeu_cau`, `nguoi_duyet`, `thoi_diem_duyet`, `duyet_voi_tu_cach`, `uy_quyen`, `tu_duyet`, `ly_do_tu_choi`, `sales_order`, `ma_de_xuat`, child `items`, `dat_ngoai`.
- Produces: hằng `TRANG_THAI_NHAP = "Nháp"`, `TRANG_THAI_CHO_DUYET = "Chờ duyệt"`, `TRANG_THAI_DA_DUYET = "Đã duyệt"`, `TRANG_THAI_TU_CHOI = "Từ chối"`, `TRANG_THAI_DA_HUY = "Đã huỷ"`, `TRANG_THAI_CHO_DUYET_SUA = "Chờ duyệt sửa"` (Task 9) trong `portal_de_xuat_mua.py`.

**Ghi chú thiết kế cho người thi công:**
- `autoname` = `field:ma_de_xuat`. Mã sinh ở Task 2, nhưng **phiếu Nháp chưa có mã** → dùng `autoname = "hash"` cho tới lúc gửi duyệt là sai (đổi tên chứng từ giữa vòng đời làm hỏng mọi link). Chốt: `autoname = "naming_series"` với series `DXM-.YYYY.-.#####` làm **tên nội bộ**, còn `ma_de_xuat` là **mã tra cứu** hiển thị cho người dùng, unique, để trống lúc Nháp. Hai thứ khác nhau, đúng như §11 mục 4 đã tách "tên đơn `SAL-ORD-*`" khỏi "mã dễ đọc".
- `customer` và `khoa_phong` là `Link`, **read-only trên form** — nhưng read-only ở tầng UI **không phải** phân quyền; chốt thật nằm ở endpoint (Task 5) và hook (Task 4).
- Không có `docstatus` — doctype **không submittable**, đúng khuôn `Portal Item Request`.
- Child `items`: `item_code` (Link Item), `item_name` (Data), `dvt` (Data), `so_luong_de_xuat` (Float), `so_luong_duyet` (Float), `don_gia` (Currency), `thanh_tien` (Currency), `nguon_dong` (Select: `Khoa đề xuất` / `Quản lý thêm`), `ghi_chu_quan_ly` (Small Text).
- `dat_ngoai` **dùng lại child doctype đã có** `Sales Order Dat Ngoai Item` — không tạo bảng mới (§5.2).

- [ ] **Step 1: Viết test đỏ — guard khoa phòng phải thuộc đúng bệnh viện**

Tạo `miyano_portal/tests/test_de_xuat_doctype.py`:

```python
"""Guard cấu trúc của `Portal De Xuat Mua` (spec §5.2).

Ba guard ở đây đều là chốt DỮ LIỆU, không phải chốt phân quyền — chốt phân
quyền theo phiên đăng nhập nằm ở endpoint (Task 5) và hook (Task 4). Doctype
không tự biết ai đang gọi nó, nên không giả vờ kiểm điều đó.
"""

import frappe
from frappe.tests.utils import FrappeTestCase


class TestDeXuatGuard(FrappeTestCase):
	def setUp(self):
		# FrappeTestCase rollback MỘT LẦN cho cả class → tự dọn ở đây.
		for dt in ("Portal De Xuat Mua",):
			for r in frappe.get_all(dt, filters={"customer": ["like", "_TEST DX%"]}):
				frappe.delete_doc(dt, r.name, force=True)
		self.kh_a = self._customer("_TEST DX A", "DXA")
		self.kh_b = self._customer("_TEST DX B", "DXB")
		self.khoa_a = self._khoa(self.kh_a, "Huyết học", "HUYETHOC")
		self.khoa_b = self._khoa(self.kh_b, "Dược", "DUOC")

	def _customer(self, ten, ma_ngan):
		if not frappe.db.exists("Customer", ten):
			frappe.get_doc({
				"doctype": "Customer", "customer_name": ten,
				"customer_group": frappe.db.get_value("Customer Group", {}, "name"),
				"territory": frappe.db.get_value("Territory", {}, "name"),
			}).insert(ignore_permissions=True)
		frappe.db.set_value("Customer", ten, "custom_ma_ngan", ma_ngan)
		return ten

	def _khoa(self, customer, ten, ma):
		ten_bp = frappe.db.get_value(
			"Customer Department", {"customer": customer, "ma_khoa": ma}, "name"
		)
		if ten_bp:
			return ten_bp
		return frappe.get_doc({
			"doctype": "Customer Department", "customer": customer,
			"ten_khoa_phong": ten, "ma_khoa": ma, "active": 1,
		}).insert(ignore_permissions=True).name

	def _phieu(self, customer, khoa_phong, **kw):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": customer, "khoa_phong": khoa_phong,
			"loai_don": kw.pop("loai_don", "HĐNT"),
			"items": kw.pop("items", [
				{"item_code": self._item(), "so_luong_de_xuat": 5},
			]),
			**kw,
		})
		return doc

	def _item(self):
		ten = "_TEST DX ITEM"
		if not frappe.db.exists("Item", ten):
			frappe.get_doc({
				"doctype": "Item", "item_code": ten, "item_name": ten,
				"item_group": frappe.db.get_value("Item Group", {}, "name"),
				"stock_uom": "Nos", "is_stock_item": 0,
			}).insert(ignore_permissions=True)
		return ten

	def test_khoa_phong_phai_thuoc_dung_benh_vien(self):
		"""Khoa của bệnh viện B không gắn được lên phiếu của bệnh viện A."""
		doc = self._phieu(self.kh_a, self.khoa_b)
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.insert(ignore_permissions=True)
		# KHÔNG dùng assertRaises(ValidationError) trần: frappe.MandatoryError
		# là con của ValidationError nên một phiếu thiếu field bắt buộc cũng
		# làm test này XANH vì lý do hoàn toàn khác.
		self.assertIn("không thuộc", str(ctx.exception))

	def test_khoa_phong_dung_benh_vien_thi_luu_duoc(self):
		"""VẾ DƯƠNG — bắt buộc theo Global Constraints."""
		doc = self._phieu(self.kh_a, self.khoa_a)
		doc.insert(ignore_permissions=True)
		self.assertEqual(doc.trang_thai, "Nháp")
		self.assertFalse(doc.ma_de_xuat)
```

- [ ] **Step 2: Chạy test, xác nhận đỏ đúng lý do**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --module miyano_portal.tests.test_de_xuat_doctype
```

Kỳ vọng: **FAIL** vì `DocType Portal De Xuat Mua not found`. Đây là "đỏ vì chưa có doctype" — đúng lý do cho bước này.

- [ ] **Step 3: Tạo child doctype JSON**

`portal_de_xuat_mua_item.json` — `istable: 1`, `editable_grid: 1`, các field đã liệt kê ở Interfaces. `portal_de_xuat_mua_item.py` chỉ là `class PortalDeXuatMuaItem(Document): pass`.

- [ ] **Step 4: Tạo doctype cha JSON + controller tối thiểu**

`portal_de_xuat_mua.py`:

```python
"""Chứng từ đề xuất mua của khoa phòng (spec §5).

KHÔNG dùng module Workflow của Frappe — `trang_thai` là Select thường, đúng
khuôn `Portal Item Request`. Lý do: máy trạng thái ở §5.4 có cạnh quay lui
(`Từ chối --sửa--> Chờ duyệt`) và vài chốt theo nội dung (bắt buộc lý do khi
từ chối) mà Workflow không biểu diễn gọn hơn một bảng viết tay.

Miyano KHÔNG có DocPerm nào trên doctype này (§5.1) — đó là toàn bộ điểm của
việc tách chứng từ này ra khỏi Sales Order: "Miyano không thấy đơn chưa
duyệt" thành tính chất của schema, không phải một bộ lọc phải nhớ áp đúng.
"""

import frappe
from frappe.model.document import Document

TRANG_THAI_NHAP = "Nháp"
TRANG_THAI_CHO_DUYET = "Chờ duyệt"
TRANG_THAI_DA_DUYET = "Đã duyệt"
TRANG_THAI_TU_CHOI = "Từ chối"
TRANG_THAI_DA_HUY = "Đã huỷ"


class PortalDeXuatMua(Document):
	def validate(self):
		self._chan_khoa_phong_khac_benh_vien()

	def _chan_khoa_phong_khac_benh_vien(self):
		"""Khoa phòng phải thuộc chính bệnh viện đứng tên phiếu.

		`khoa_phong` rỗng là HỢP LỆ — đó là phiếu cấp bệnh viện của quản lý
		("Toàn viện", §5.5), mang mã khoa dành riêng CHUNG.
		"""
		if not self.khoa_phong:
			return
		cua = frappe.db.get_value("Customer Department", self.khoa_phong, "customer")
		if cua != self.customer:
			frappe.throw(
				f'Khoa phòng "{self.khoa_phong}" không thuộc đơn vị '
				f'"{self.customer}".',
				frappe.ValidationError,
			)
```

- [ ] **Step 5: Chạy test, xác nhận xanh**

```bash
bench --site erptest.local run-tests --module miyano_portal.tests.test_de_xuat_doctype
```
Kỳ vọng: 2 test PASS.

- [ ] **Step 6: Chạy toàn bộ suite**

```bash
bench --site erptest.local run-tests --app miyano_portal
```
Kỳ vọng: **1137 OK** (1135 nền + 2 mới). Số test giảm hoặc có lỗi = dừng, báo cáo.

- [ ] **Step 7: Commit**

```bash
git add miyano_portal/miyano_portal/doctype/portal_de_xuat_mua miyano_portal/miyano_portal/doctype/portal_de_xuat_mua_item miyano_portal/tests/test_de_xuat_doctype.py
git commit -m "feat(de-xuat): doctype Portal De Xuat Mua va child item"
```

---

## Task 2: Sinh mã đề xuất

**Files:**
- Create: `miyano_portal/ma_de_xuat.py`
- Test: `miyano_portal/tests/test_ma_de_xuat.py`

**Interfaces:**
- Consumes: `Customer.custom_ma_ngan`, `Customer Department.ma_khoa` (Task 2 của kế hoạch trước, đã có).
- Produces: `sinh_ma(customer: str, khoa_phong: str | None, ngay=None) -> str` — trả mã dạng `DXA-HUYETHOC-260819-01`. `khoa_phong=None` → dùng `CHUNG`.

**Ghi chú thiết kế — đọc kỹ, đây là chỗ dễ sai nhất:**

Bộ đếm là **theo bộ ba (bệnh viện, khoa, ngày)**. Frappe `naming_series` không làm được việc này (nó đếm theo một chuỗi tiền tố cố định). Cơ chế chốt:

```
SELECT ... FOR UPDATE trên hàng đếm  →  +1  →  ghép mã
```

Không dùng `SELECT MAX(...)` trên `tabPortal De Xuat Mua` rồi +1: hai phiên cùng đọc `MAX` sẽ ra cùng một số, và lỗi chỉ lộ ra khi hai khoa bấm gửi trong cùng một giây — tức là không bao giờ lộ trên máy dev, và lộ đúng lúc bệnh viện đông người dùng.

Dùng bảng đếm sẵn có của Frappe: `frappe.model.naming.getseries(prefix, digits)` đã làm đúng việc này (`tabSeries`, `INSERT ... ON DUPLICATE KEY UPDATE current = current + 1`, nguyên tử ở tầng MariaDB). Tiền tố truyền vào chính là `f"{ma_ngan}-{ma_khoa}-{yymmdd}-"`.

Tràn 3 chữ số: **đã đọc mã nguồn v15.113.4** — dòng cuối `getseries` là `("%0" + str(digits) + "d") % current`, và `"%02d" % 100` cho ra `"100"`. **Tràn tự nhiên, không quay vòng**, đúng yêu cầu §6.1. Test vẫn phải chứng minh (hành vi framework đổi được giữa các bản), nhưng nếu nó đỏ thì lỗi ở code mình, không phải ở giả định của plan.

- [ ] **Step 1: Viết test đỏ**

```python
"""Sinh mã đề xuất (spec §6.1, §6.2)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import ma_de_xuat


from miyano_portal.tests.fixtures_de_xuat import dung_fixture


class TestMaDeXuat(FrappeTestCase):
	def setUp(self):
		# Bộ đếm sống trong `tabSeries`. `getseries` chạy SQL thường trong
		# CHÍNH transaction hiện tại (đã đọc `frappe/model/naming.py`: SELECT
		# ... FOR UPDATE rồi UPDATE, không commit riêng) — nên rollback CÓ
		# dọn nó. Nhưng `FrappeTestCase` rollback MỘT LẦN cho cả CLASS, nên
		# các test TRONG CÙNG class vẫn cộng dồn số của nhau: không dọn thì
		# `test_tran_sang_ba_chu_so` xanh/đỏ tuỳ thứ tự chạy.
		frappe.db.delete("Series", {"name": ["like", "DXA-%"]})
		frappe.db.delete("Series", {"name": ["like", "DXB-%"]})
		# Fixture dùng chung với test_de_xuat_doctype.py — tách ra module
		# riêng để hai bộ test không trôi lệch định nghĩa khách/khoa/vật tư.
		f = dung_fixture(self)
		self.khoa, self.khoa2 = f.khoa_huyethoc, f.khoa_duoc

	def test_cau_truc_ma(self):
		ma = ma_de_xuat.sinh_ma("_TEST DX A", self.khoa, ngay="2026-08-19")
		self.assertEqual(ma, "DXA-HUYETHOC-260819-01")

	def test_dem_rieng_cho_tung_khoa(self):
		"""Khoa khác nhau có dãy số RIÊNG, không dùng chung bộ đếm."""
		a1 = ma_de_xuat.sinh_ma("_TEST DX A", self.khoa, ngay="2026-08-19")
		b1 = ma_de_xuat.sinh_ma("_TEST DX A", self.khoa2, ngay="2026-08-19")
		a2 = ma_de_xuat.sinh_ma("_TEST DX A", self.khoa, ngay="2026-08-19")
		self.assertTrue(a1.endswith("-01"))
		self.assertTrue(b1.endswith("-01"))   # khoa khác → lại bắt đầu từ 01
		self.assertTrue(a2.endswith("-02"))

	def test_dem_rieng_cho_tung_ngay(self):
		h = ma_de_xuat.sinh_ma("_TEST DX A", self.khoa, ngay="2026-08-19")
		mai = ma_de_xuat.sinh_ma("_TEST DX A", self.khoa, ngay="2026-08-20")
		self.assertTrue(h.endswith("-01"))
		self.assertTrue(mai.endswith("-01"))

	def test_tran_sang_ba_chu_so_khong_quay_vong(self):
		"""§6.1: vượt 99 thì tràn sang 3 chữ số, KHÔNG quay vòng về 01."""
		for _ in range(99):
			ma_de_xuat.sinh_ma("_TEST DX A", self.khoa, ngay="2026-08-19")
		thu_100 = ma_de_xuat.sinh_ma("_TEST DX A", self.khoa, ngay="2026-08-19")
		self.assertTrue(thu_100.endswith("-100"), thu_100)

	def test_khong_co_khoa_thi_dung_ma_CHUNG(self):
		"""§5.5 — đơn 'Toàn viện' của quản lý."""
		ma = ma_de_xuat.sinh_ma("_TEST DX A", None, ngay="2026-08-19")
		self.assertEqual(ma, "DXA-CHUNG-260819-01")

	def test_thieu_ma_ngan_thi_bao_loi_tu_xu_ly_duoc(self):
		"""QĐ-A3 — không tự đoán mã bệnh viện."""
		frappe.db.set_value("Customer", "_TEST DX B", "custom_ma_ngan", None)
		with self.assertRaises(frappe.ValidationError) as ctx:
			ma_de_xuat.sinh_ma("_TEST DX B", None, ngay="2026-08-19")
		self.assertIn("Mã ngắn", str(ctx.exception))
```

*Việc đầu tiên của task này:* tách khối fixture `_customer`/`_khoa`/`_item` đã viết ở Task 1 ra `miyano_portal/tests/fixtures_de_xuat.py`, phơi ra một hàm `dung_fixture(case) -> frappe._dict` trả `{kh_a, kh_b, khoa_huyethoc, khoa_duoc, item}`; sửa `test_de_xuat_doctype.py` dùng nó. Đây là **sửa test cũ trong cùng một nhánh chưa merge, không đổi hành vi test nào** — không thuộc diện phải xin phép ở Global Constraints, nhưng vẫn phải chạy lại `test_de_xuat_doctype` và thấy nó xanh **trước** khi đi tiếp.

- [ ] **Step 2: Chạy, xác nhận đỏ vì `ModuleNotFoundError: miyano_portal.ma_de_xuat`**

```bash
bench --site erptest.local run-tests --module miyano_portal.tests.test_ma_de_xuat
```

- [ ] **Step 3: Viết `ma_de_xuat.py`**

```python
"""Sinh mã đề xuất `DXA-HUYETHOC-260819-01` (spec §6.1).

Bộ đếm theo bộ ba (bệnh viện, khoa, ngày) — KHÔNG phải một naming_series của
Frappe, vốn chỉ đếm theo một tiền tố cố định. Dùng `getseries()` với tiền tố
động: nó ghi vào `tabSeries` bằng `INSERT ... ON DUPLICATE KEY UPDATE current
= current + 1`, nguyên tử ở tầng MariaDB.

KHÔNG được thay bằng `SELECT MAX(ma_de_xuat) + 1`: hai phiên cùng đọc MAX sẽ
ra cùng một số, và lỗi đó chỉ lộ khi hai khoa bấm gửi trong cùng một giây —
tức là không bao giờ lộ trên máy dev.
"""

import frappe
from frappe.model.naming import getseries
from frappe.utils import getdate, nowdate

MA_TOAN_VIEN = "CHUNG"


def sinh_ma(customer: str, khoa_phong: str | None, ngay=None) -> str:
	ma_ngan = frappe.db.get_value("Customer", customer, "custom_ma_ngan")
	if not ma_ngan:
		frappe.throw(
			f'Đơn vị "{customer}" chưa có Mã ngắn. Liên hệ Miyano để đặt Mã '
			"ngắn trước khi dùng chức năng đề xuất mua.",
			frappe.ValidationError,
		)
	if khoa_phong:
		ma_khoa = frappe.db.get_value("Customer Department", khoa_phong, "ma_khoa")
		if not ma_khoa:
			frappe.throw(
				f'Khoa phòng "{khoa_phong}" chưa có Mã khoa.', frappe.ValidationError
			)
	else:
		ma_khoa = MA_TOAN_VIEN
	yymmdd = getdate(ngay or nowdate()).strftime("%y%m%d")
	tien_to = f"{ma_ngan}-{ma_khoa}-{yymmdd}-"
	return tien_to + getseries(tien_to, 2)
```

- [ ] **Step 4: Chạy test, xác nhận 6 test xanh**

Nếu `test_tran_sang_ba_chu_so_khong_quay_vong` đỏ: **không** sửa test. Đọc `frappe/model/naming.py::getseries` để xem nó thật sự làm gì khi vượt `digits`, rồi báo cáo — hành vi thật của framework thắng giả định của plan.

- [ ] **Step 5: Chạy toàn bộ suite, kỳ vọng 1143 OK**

- [ ] **Step 6: Commit**

```bash
git add miyano_portal/ma_de_xuat.py miyano_portal/tests/test_ma_de_xuat.py miyano_portal/tests/fixtures_de_xuat.py
git commit -m "feat(de-xuat): sinh ma de xuat theo (benh vien, khoa, ngay)"
```

---

## Task 3: Máy trạng thái + xoá/huỷ

**Files:**
- Modify: `miyano_portal/miyano_portal/doctype/portal_de_xuat_mua/portal_de_xuat_mua.py`
- Test: `miyano_portal/tests/test_de_xuat_doctype.py` *(thêm class mới, không sửa class cũ)*

**Interfaces:**
- Consumes: `ma_de_xuat.sinh_ma` (Task 2), các hằng trạng thái (Task 1).
- Produces: `PortalDeXuatMua.gui_duyet()`, `.duyet(nguoi_duyet, tu_cach="Quản lý chính", uy_quyen=None)`, `.tu_choi(ly_do)`, `.huy()`; `on_trash` chặn xoá phiếu đã gửi.
- **Ruling preflight C3:** plan chỉ đưa khối mã cho `gui_duyet()`. Ba phương thức còn lại **vẫn phải cài đủ trong task này** theo đúng máy trạng thái ở trên — Task 6 và Task 9 đều gọi chúng. `.duyet()` là nơi DUY NHẤT viết `trang_thai = "Đã duyệt"` cùng cả khối truy vết (`nguoi_duyet`, `thoi_diem_duyet`, `duyet_voi_tu_cach`, `uy_quyen`, `tu_duyet` suy từ `nguoi_duyet == owner`). `.tu_choi(ly_do)` bắt buộc lý do (thông điệp chứa "Lý do từ chối"). `.huy()` chuyển `Đã huỷ`.

**Máy trạng thái (§5.4):**

```
Nháp ──gui_duyet()──► Chờ duyệt ──duyet()──► Đã duyệt
 │                        │
 │                        └──tu_choi(ly_do)──► Từ chối ──gui_duyet()──► Chờ duyệt
 └──XOÁ THẬT                                   
                      Chờ duyệt/Từ chối ──huy()──► Đã huỷ
```

**Xoá và huỷ là hai việc khác nhau (§5.4b):** Nháp → xoá thật khỏi CSDL (chưa ai thấy, chưa có mã, không có gì để truy vết). Từ Chờ duyệt trở đi → chuyển `Đã huỷ`, phiếu còn nguyên.

- [ ] **Step 1: Viết test đỏ**

```python
class TestDeXuatVongDoi(FrappeTestCase):
	def test_gui_duyet_sinh_ma_va_dong_bang_so_luong(self):
		doc = self._nhap()
		self.assertFalse(doc.ma_de_xuat)
		doc.ly_do_yeu_cau = "Hết găng tay cỡ M"
		doc.gui_duyet()
		self.assertEqual(doc.trang_thai, "Chờ duyệt")
		self.assertTrue(doc.ma_de_xuat)
		self.assertTrue(doc.thoi_diem_gui)

	def test_gui_duyet_thieu_ly_do_thi_chan(self):
		"""§5.2 — `ly_do_yeu_cau` bắt buộc Ở BƯỚC GỬI, không phải lúc lưu nháp."""
		doc = self._nhap()
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.gui_duyet()
		self.assertIn("Lý do", str(ctx.exception))

	def test_nhap_luu_duoc_khi_chua_co_ly_do(self):
		"""VẾ DƯƠNG của test trên — bắt điền ngay từ dòng đầu sẽ khiến
		người ta gõ 'abc' cho xong (§5.2)."""
		doc = self._nhap()
		self.assertEqual(doc.trang_thai, "Nháp")

	def test_so_luong_de_xuat_khoa_vinh_vien_sau_khi_gui(self):
		"""§5.3 — không ai sửa được nữa, kể cả quản lý, kể cả Miyano."""
		doc = self._nhap()
		doc.ly_do_yeu_cau = "x"
		doc.gui_duyet()
		doc.items[0].so_luong_de_xuat = 999
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.save(ignore_permissions=True)
		self.assertIn("đã khoá", str(ctx.exception))

	def test_so_luong_duyet_van_sua_duoc_sau_khi_gui(self):
		"""VẾ DƯƠNG — khoá cột đề xuất KHÔNG được khoá luôn cột duyệt."""
		doc = self._nhap()
		doc.ly_do_yeu_cau = "x"
		doc.gui_duyet()
		doc.items[0].so_luong_duyet = 3
		doc.save(ignore_permissions=True)
		self.assertEqual(doc.items[0].so_luong_duyet, 3)

	def test_xoa_phieu_nhap_duoc(self):
		doc = self._nhap()
		ten = doc.name
		frappe.delete_doc("Portal De Xuat Mua", ten, force=True)
		self.assertFalse(frappe.db.exists("Portal De Xuat Mua", ten))

	def test_khong_xoa_duoc_phieu_da_gui(self):
		"""§5.4b — đã có mã, quản lý đã nhìn thấy → huỷ chứ không xoá."""
		doc = self._nhap()
		doc.ly_do_yeu_cau = "x"
		doc.gui_duyet()
		with self.assertRaises(frappe.ValidationError) as ctx:
			frappe.delete_doc("Portal De Xuat Mua", doc.name)
		self.assertIn("Huỷ phiếu", str(ctx.exception))

	def test_tu_choi_bat_buoc_ly_do(self):
		doc = self._cho_duyet()
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.tu_choi("")
		self.assertIn("Lý do từ chối", str(ctx.exception))

	def test_tu_choi_roi_sua_roi_gui_lai(self):
		"""Cạnh quay lui của §5.4 — mã KHÔNG sinh lại lần hai."""
		doc = self._cho_duyet()
		ma_cu = doc.ma_de_xuat
		doc.tu_choi("Vượt dự toán")
		self.assertEqual(doc.trang_thai, "Từ chối")
		doc.gui_duyet()
		self.assertEqual(doc.trang_thai, "Chờ duyệt")
		self.assertEqual(doc.ma_de_xuat, ma_cu)

	def test_khong_di_tat_tu_nhap_sang_da_duyet(self):
		"""Bare assertRaises KHÔNG đủ ở đây: một phiếu Nháp thiếu field
		bắt buộc ném MandatoryError — con của ValidationError — nên test
		sẽ xanh vì lý do hoàn toàn khác cái nó định canh.
		"""
		doc = self._nhap()
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.duyet("Administrator")
		self.assertIn("Không chuyển được phiếu", str(ctx.exception))
```

- [ ] **Step 2: Chạy, xác nhận đỏ vì `AttributeError: gui_duyet`**

- [ ] **Step 3: Cài máy trạng thái**

Thêm vào đầu `portal_de_xuat_mua.py`:

```python
from frappe.utils import now_datetime

from miyano_portal.ma_de_xuat import sinh_ma
```

Rồi trong `class PortalDeXuatMua`:

```python
	CHUYEN_HOP_LE = {
		TRANG_THAI_NHAP: {TRANG_THAI_CHO_DUYET},
		TRANG_THAI_CHO_DUYET: {TRANG_THAI_DA_DUYET, TRANG_THAI_TU_CHOI, TRANG_THAI_DA_HUY},
		TRANG_THAI_TU_CHOI: {TRANG_THAI_CHO_DUYET, TRANG_THAI_DA_HUY},
	}
	# Trạng thái kết thúc CỐ Ý không xuất hiện làm chìa khoá — không có cạnh
	# đi ra từ chúng. Cùng khuôn với `Portal Item Request`.

	def _kiem_chuyen(self, dich):
		if dich not in self.CHUYEN_HOP_LE.get(self.trang_thai, set()):
			frappe.throw(
				f'Không chuyển được phiếu từ "{self.trang_thai}" sang "{dich}".',
				frappe.ValidationError,
			)

	def gui_duyet(self):
		self._kiem_chuyen(TRANG_THAI_CHO_DUYET)
		if not (self.ly_do_yeu_cau or "").strip():
			frappe.throw(
				"Lý do yêu cầu là bắt buộc khi gửi duyệt.", frappe.ValidationError
			)
		if not self.ma_de_xuat:
			# Sinh ĐÚNG MỘT LẦN. Phiếu bị từ chối rồi gửi lại giữ nguyên mã cũ:
			# quản lý và khoa đã gọi tên nó bằng mã đó trong lúc trao đổi.
			self.ma_de_xuat = sinh_ma(self.customer, self.khoa_phong)
		self.thoi_diem_gui = now_datetime()
		self.trang_thai = TRANG_THAI_CHO_DUYET
		self.save(ignore_permissions=True)
```

Khoá `so_luong_de_xuat` trong `validate()` (QĐ-A2). **Nhớ nối vào `validate()`** — Task 1 mới chỉ gọi một guard:

```python
	def validate(self):
		self._chan_khoa_phong_khac_benh_vien()
		self._chan_sua_so_luong_de_xuat()      # ← thêm dòng này
```

```python
	def _chan_sua_so_luong_de_xuat(self):
		"""§5.3 — cột đề xuất khoá vĩnh viễn từ lúc Gửi duyệt.

		GIỚI HẠN ĐÃ BIẾT (QĐ-A2): `frappe.db.set_value`/`doc.db_set()` đi
		vòng được guard này — cùng loại giới hạn với `_chan_hai_quan_ly`
		trong `portal_member.py`. Chấp nhận: Miyano không có DocPerm nào
		trên doctype này nên không có màn desk để bấm, và không đường code
		nào trong app gọi db_set lên field này.
		"""
		if self.is_new() or self.trang_thai == TRANG_THAI_NHAP:
			return
		truoc = {d.name: d.so_luong_de_xuat for d in self.get_doc_before_save().items}
		for d in self.items:
			if d.name in truoc and float(d.so_luong_de_xuat or 0) != float(truoc[d.name] or 0):
				frappe.throw(
					f'Số lượng đề xuất của "{d.item_code}" đã khoá từ lúc gửi '
					"duyệt. Quản lý điều chỉnh ở cột Số lượng duyệt.",
					frappe.ValidationError,
				)
```

`on_trash`:

```python
	def on_trash(self):
		if self.trang_thai != TRANG_THAI_NHAP:
			frappe.throw(
				"Phiếu đã gửi duyệt thì không xoá được. Dùng Huỷ phiếu để giữ "
				"lại dấu vết.",
				frappe.ValidationError,
			)
```

- [ ] **Step 4: Chạy test module, xác nhận 10 test mới xanh**
- [ ] **Step 5: Chạy toàn bộ suite, kỳ vọng 1153 OK**
- [ ] **Step 6: Commit** — `feat(de-xuat): may trang thai, khoa so luong goc, xoa vs huy`

---

## Task 4: Phạm vi theo khoa Ở TẦNG HOOK

**Files:**
- Modify: `miyano_portal/permissions.py`
- Modify: `miyano_portal/hooks.py`
- Test: `miyano_portal/tests/test_de_xuat_cach_ly.py` *(mới)*

**Vì sao task này đứng TRƯỚC endpoint, không phải sau:**

Ở bước 4 của kế hoạch trước, phạm vi theo khoa được xây **chỉ ở tầng endpoint**. Kết quả: `GET /api/resource/Sales Order` trả đơn của mọi khoa. §5.1 nói Miyano không có DocPerm trên doctype này — đó là **trục Miyano**. Trục **khoa phòng** vẫn cần hook riêng. Test phải đi qua `frappe.get_list`, **không** qua endpoint — endpoint là thứ task sau mới có.

**Interfaces:**
- Consumes: `portal_context.pham_vi_don()`, `portal_context.get_allowed_customers()`.
- Produces: `permissions.de_xuat_query_condition(user)`, `permissions.de_xuat_co_quyen(doc, user, ptype)`.

- [ ] **Step 1: Viết test đỏ — cách ly qua `frappe.get_list`**

```python
"""Cách ly `Portal De Xuat Mua` theo khoa phòng — Ở TẦNG HOOK.

Test này CỐ Ý đi qua `frappe.get_list`, KHÔNG qua endpoint của app. Ở bước 4
phạm vi được xây chỉ ở tầng endpoint và `GET /api/resource/...` trả về mọi
khoa — bộ test khi đó xanh vì nó chỉ hỏi endpoint. Đừng lặp lại.
"""

class TestDeXuatCachLy(FrappeTestCase):
	def test_nhan_vien_khoa_khong_thay_phieu_khoa_khac(self):
		frappe.set_user(self.user_huyethoc)
		ten = [r.name for r in frappe.get_list("Portal De Xuat Mua")]
		self.assertNotIn(self.phieu_duoc, ten)

	def test_nhan_vien_khoa_VAN_THAY_phieu_khoa_minh(self):
		"""VẾ DƯƠNG — thiếu test này thì `return []` cũng qua bài.

		Đây chính xác là lỗ hổng đã làm bộ test bước 4 xanh trong khi tính
		năng chết hẳn: nhân viên đặt đơn xong thì chính họ không mở lại được.
		"""
		frappe.set_user(self.user_huyethoc)
		ten = [r.name for r in frappe.get_list("Portal De Xuat Mua")]
		self.assertIn(self.phieu_huyethoc, ten)

	def test_quan_ly_thay_ca_hai_khoa(self):
		frappe.set_user(self.user_quan_ly)
		ten = [r.name for r in frappe.get_list("Portal De Xuat Mua")]
		self.assertIn(self.phieu_huyethoc, ten)
		self.assertIn(self.phieu_duoc, ten)

	def test_khong_thay_phieu_benh_vien_khac(self):
		"""Trục KHÁCH HÀNG vẫn phải nguyên — hook mới không được nới nó."""
		frappe.set_user(self.user_quan_ly)
		ten = [r.name for r in frappe.get_list("Portal De Xuat Mua")]
		self.assertNotIn(self.phieu_benh_vien_b, ten)

	def test_get_doc_truc_tiep_cung_bi_chan(self):
		"""`get_list` lọc, nhưng `has_permission` mới chặn đường đọc thẳng."""
		frappe.set_user(self.user_huyethoc)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc("Portal De Xuat Mua", self.phieu_duoc).check_permission("read")

	def tearDown(self):
		frappe.set_user("Administrator")
```

- [ ] **Step 2: Chạy, xác nhận đỏ — cả 5 test đỏ vì chưa có hook nào**

Chú ý: `test_nhan_vien_khoa_VAN_THAY_phieu_khoa_minh` có thể **xanh sẵn** (chưa có hook = thấy hết). Đó là bình thường — nó là vế dương, nó canh việc hook mới **không** chặn nhầm. Ba test còn lại phải đỏ.

- [ ] **Step 3: Viết hook trong `permissions.py`**

```python
def de_xuat_query_condition(user=None):
	"""Điều kiện lọc `Portal De Xuat Mua` theo khách hàng VÀ theo khoa.

	Hook của nhiều app được AND lại chứ không thay thế nhau (đã kiểm ở
	`frappe/model/db_query.py:1125-1138`), nên điều kiện trả về đây cộng
	dồn với các hook khác, không đè.
	"""
	user = user or frappe.session.user
	if "System Manager" in frappe.get_roles(user):
		return ""
	khachs = get_allowed_customers(user)
	if not khachs:
		return "1=0"   # fail-closed
	dk = f"""`tabPortal De Xuat Mua`.customer = {frappe.db.escape(khachs[0])}"""
	pv = pham_vi_don(user)
	if pv.get("custom_khoa_phong"):
		dk += (
			" and `tabPortal De Xuat Mua`.khoa_phong = "
			f"{frappe.db.escape(pv['custom_khoa_phong'])}"
		)
	return dk
```

`de_xuat_co_quyen(doc, user, ptype)` — cùng logic, dạng kiểm một bản ghi.

- [ ] **Step 4: Khai trong `hooks.py`**

```python
permission_query_conditions = {
	# ... các mục đã có, KHÔNG sửa
	"Portal De Xuat Mua": "miyano_portal.permissions.de_xuat_query_condition",
}
has_permission = {
	"Portal De Xuat Mua": "miyano_portal.permissions.de_xuat_co_quyen",
}
```

*Người thi công:* `hooks.py` đã có hai dict này — **thêm khoá mới, không viết đè cả dict**.

- [ ] **Step 5: Chạy test module, xác nhận 5 test xanh**
- [ ] **Step 6: Chạy toàn bộ suite, kỳ vọng 1158 OK**
- [ ] **Step 7: Commit** — `feat(de-xuat): pham vi theo khoa o tang hook (query condition + has_permission)`

---

## Task 5: Endpoint của nhân viên khoa

**Files:**
- Create: `miyano_portal/api/de_xuat.py`
- Modify: `miyano_portal/tests/test_pham_vi_endpoint.py`
- Test: `miyano_portal/tests/test_de_xuat_endpoint.py` *(mới)*

**Interfaces:**
- Produces 6 endpoint whitelist: `de_xuat_tao_nhap`, `de_xuat_luu_nhap`, `de_xuat_xoa_nhap`, `de_xuat_gui_duyet`, `de_xuat_danh_sach`, `de_xuat_chi_tiet`.

**Bắt buộc trong task này:**
1. Thêm `from miyano_portal.api import de_xuat as de_xuat_api` vào `test_pham_vi_endpoint.py` và đưa module mới vào phép liệt kê. **Module mới không tự động bị đếm** — quên bước này thì test đếm ngược vẫn xanh trong khi 6 endpoint không ai canh.
2. Cả 6 tên vào `DA_AP_PHAM_VI`. Không cái nào vào `MIEN_PHAM_VI`.

**Chốt phân quyền của mỗi endpoint:**
- `customer` và `khoa_phong` **suy từ `get_portal_member()` của phiên**, không nhận từ client — cùng luật C1 của `portal_order_place`.
- `de_xuat_xoa_nhap`: chỉ `owner` của phiếu hoặc quản lý (§5.4b).
- `de_xuat_gui_duyet`: chỉ `owner`.

- [ ] **Step 1: Viết test đỏ**

```python
	def test_nhan_vien_tao_phieu_thi_khoa_lay_tu_PHIEN(self):
		"""Không nhận khoa từ client — nhân viên khoa Huyết học không lập
		được phiếu mang tên khoa Dược kể cả khi sửa payload."""
		frappe.set_user(self.user_huyethoc)
		ten = de_xuat.de_xuat_tao_nhap(khoa_phong=self.khoa_duoc)["name"]
		doc = frappe.get_doc("Portal De Xuat Mua", ten)
		self.assertEqual(doc.khoa_phong, self.khoa_huyethoc)

	def test_nhan_vien_khong_xoa_duoc_phieu_nhap_cua_nguoi_khac(self):
		frappe.set_user(self.user_huyethoc2)
		with self.assertRaises(frappe.PermissionError):
			de_xuat.de_xuat_xoa_nhap(self.phieu_nhap_cua_nguoi_khac)

	def test_chinh_chu_xoa_duoc_phieu_nhap_cua_minh(self):
		"""VẾ DƯƠNG."""
		frappe.set_user(self.user_huyethoc)
		de_xuat.de_xuat_xoa_nhap(self.phieu_nhap_cua_toi)
		self.assertFalse(
			frappe.db.exists("Portal De Xuat Mua", self.phieu_nhap_cua_toi)
		)

	def test_danh_sach_chi_tra_phieu_trong_pham_vi(self):
		frappe.set_user(self.user_huyethoc)
		ten = [r["name"] for r in de_xuat.de_xuat_danh_sach()]
		self.assertIn(self.phieu_huyethoc, ten)      # vế dương
		self.assertNotIn(self.phieu_duoc, ten)       # vế âm
```

- [ ] **Step 2: Chạy, xác nhận đỏ vì thiếu module `api/de_xuat.py`**
- [ ] **Step 3: Viết `api/de_xuat.py`**

Mỗi hàm là **vỏ mỏng**: suy khách/khoa từ phiên rồi gọi phương thức doctype (Task 3). Logic nghiệp vụ **không** viết lại ở đây — cùng khuôn `portal_order_place` → `dat_hang.tao_sales_order`.

```python
"""Endpoint cổng cho `Portal De Xuat Mua` (spec §5).

MỌI hàm ở đây suy `customer` và `khoa_phong` từ PHIÊN ĐĂNG NHẬP qua
`get_portal_member()`, KHÔNG nhận từ client — cùng luật C1 đã áp cho
`portal_order_place`. Một tham số `khoa_phong` nhận từ client sẽ cho nhân
viên khoa A lập phiếu mang tên khoa B.

Module này PHẢI có tên trong `tests/test_pham_vi_endpoint.py` — module mới
không tự động bị test đếm ngược soi tới.
"""

import frappe

from miyano_portal.portal_context import get_portal_member, la_quan_ly

DOCTYPE = "Portal De Xuat Mua"


def _phieu_cua_toi(ten: str, *, cho_quan_ly=False):
	"""Lấy phiếu sau khi đã kiểm quyền. Trả `Document`.

	`check_permission` đi qua hook `has_permission` của Task 4 — đó là chỗ
	DUY NHẤT quyết định phạm vi, không kiểm lại bằng tay ở đây (hai phép
	kiểm song song sớm muộn cũng lệch nhau).
	"""
	doc = frappe.get_doc(DOCTYPE, ten)
	doc.check_permission("read")
	if not cho_quan_ly and doc.owner != frappe.session.user and not la_quan_ly():
		raise frappe.PermissionError("Phiếu này không phải của bạn.")
	return doc


@frappe.whitelist()
def de_xuat_tao_nhap(loai_don="HĐNT", hdnt=None, **_bo_qua) -> dict:
	"""`**_bo_qua` là CỐ Ý: client cũ/độc hại gửi thêm `customer` hay
	`khoa_phong` thì chúng rơi vào đây và bị vứt, không đi vào doc."""
	tv = get_portal_member()
	doc = frappe.get_doc({
		"doctype": DOCTYPE,
		"customer": tv.customer,
		"khoa_phong": tv.khoa_phong,
		"loai_don": loai_don,
		"hdnt": hdnt,
		"trang_thai": "Nháp",
	}).insert(ignore_permissions=True)
	return {"name": doc.name}


@frappe.whitelist()
def de_xuat_luu_nhap(ten, items=None, dat_ngoai=None, ngay_can=None,
                     dia_chi_giao=None, ghi_chu=None, ly_do_yeu_cau=None) -> dict:
	doc = _phieu_cua_toi(ten)
	if doc.trang_thai != "Nháp":
		frappe.throw("Chỉ sửa được phiếu đang ở trạng thái Nháp.",
		             frappe.ValidationError)
	if items is not None:
		doc.set("items", frappe.parse_json(items) if isinstance(items, str) else items)
	if dat_ngoai is not None:
		doc.set("dat_ngoai",
		        frappe.parse_json(dat_ngoai) if isinstance(dat_ngoai, str) else dat_ngoai)
	for f, v in (("ngay_can", ngay_can), ("dia_chi_giao", dia_chi_giao),
	             ("ghi_chu", ghi_chu), ("ly_do_yeu_cau", ly_do_yeu_cau)):
		if v is not None:
			doc.set(f, v)
	doc.save(ignore_permissions=True)
	return {"name": doc.name}


@frappe.whitelist()
def de_xuat_xoa_nhap(ten) -> dict:
	"""§5.4b — XOÁ THẬT, chỉ ở trạng thái Nháp. `on_trash` của doctype là
	chốt cuối; kiểm ở đây chỉ để báo lỗi dễ hiểu hơn."""
	doc = _phieu_cua_toi(ten)
	frappe.delete_doc(DOCTYPE, doc.name, ignore_permissions=True)
	return {"ok": True}


@frappe.whitelist()
def de_xuat_gui_duyet(ten) -> dict:
	doc = _phieu_cua_toi(ten)
	doc.gui_duyet()
	return {"name": doc.name, "ma_de_xuat": doc.ma_de_xuat}


@frappe.whitelist()
def de_xuat_danh_sach(trang_thai=None, limit=50) -> list[dict]:
	"""Phạm vi do hook Task 4 lo — `frappe.get_list` đã đi qua
	`permission_query_conditions`. KHÔNG tự thêm bộ lọc khoa ở đây."""
	loc = {}
	if trang_thai:
		loc["trang_thai"] = trang_thai
	return frappe.get_list(
		DOCTYPE, filters=loc,
		fields=["name", "ma_de_xuat", "khoa_phong", "trang_thai",
		        "thoi_diem_gui", "owner"],
		order_by="modified desc", limit_page_length=int(limit),
	)


@frappe.whitelist()
def de_xuat_chi_tiet(ten) -> dict:
	doc = _phieu_cua_toi(ten, cho_quan_ly=True)
	return doc.as_dict()
```
- [ ] **Step 4: Cập nhật `test_pham_vi_endpoint.py`** — import module mới + 6 tên vào `DA_AP_PHAM_VI`.
- [ ] **Step 5: Chạy test đếm ngược riêng, xác nhận xanh**

```bash
bench --site erptest.local run-tests --module miyano_portal.tests.test_pham_vi_endpoint
```

- [ ] **Step 6: Chạy toàn bộ suite, kỳ vọng 1162 OK**
- [ ] **Step 7: Commit** — `feat(de-xuat): endpoint cua nhan vien khoa`

---

## Task 6: Đường duyệt → Sales Order

**Files:**
- Create: `miyano_portal/de_xuat_duyet.py`
- Modify: `miyano_portal/api/de_xuat.py` *(thêm 3 endpoint)*
- Modify: `miyano_portal/tests/test_pham_vi_endpoint.py`
- Create: `miyano_portal/patches/v1_24/them_de_xuat_vao_don_hang.py`
- Test: `miyano_portal/tests/test_de_xuat_duyet.py` *(mới)*

**Interfaces:**
- Consumes: `dat_hang.tao_sales_order(customer, *, mode, contract, items, dat_ngoai, po, delivery_date, note, address, request_id, khoa_phong)` — **chữ ký đã có, không đổi**.
- Produces: `de_xuat_duyet.duyet_va_tao_don(ten_phieu, nguoi_duyet, tu_cach="Quản lý chính", uy_quyen=None) -> dict`; endpoint `de_xuat_duyet_phieu`, `de_xuat_tu_choi`, `de_xuat_huy`.
- **Ruling preflight C1+C2:** hàm module đổi tên thành `duyet_va_tao_don` (hai hàm cùng tên `duyet` ở hai tầng là mồi cho lỗi gọi nhầm), và nó **KHÔNG tự viết trạng thái**: nó lo hạn mức + giá + tạo Sales Order rồi **gọi `doc.duyet(nguoi_duyet, tu_cach, uy_quyen)`** của Task 3. Doctype là nơi DUY NHẤT viết trạng thái đã duyệt và khối truy vết. `dieu_chinh` do endpoint xử lý qua `_ap_dieu_chinh` TRƯỚC khi gọi hàm này.
- Produces: `Sales Order.custom_de_xuat` (Link) + `custom_ma_tra_cuu` (Data) — patch v1_24.

**`_ap_dieu_chinh(doc, dieu_chinh)`** — quản lý sửa số lượng trước khi bấm duyệt (QĐ-KP-3). Viết cùng task này, trong `api/de_xuat.py`:

```python
def _ap_dieu_chinh(doc, dieu_chinh):
	"""Quản lý chỉ chạm `so_luong_duyet` và `ghi_chu_quan_ly`. Bỏ một mặt
	hàng = HẠ VỀ 0, không xoá dòng (§5.3). Thêm mặt hàng → dòng mới có
	`so_luong_de_xuat = 0`, `nguon_dong = "Quản lý thêm"`.

	CHỈ đọc `item_code` (để KHỚP dòng ĐÃ CÓ) và `so_luong_duyet` — mọi field
	khác trong payload bị bỏ qua, cùng khuôn `portal_order_sua_so_luong`.
	"""
	dc = frappe.parse_json(dieu_chinh) if isinstance(dieu_chinh, str) else dieu_chinh
	theo_ma = {d.item_code: d for d in doc.items}
	for row in dc.get("items", []):
		ma = row.get("item_code")
		if ma in theo_ma:
			theo_ma[ma].so_luong_duyet = float(row.get("so_luong_duyet") or 0)
			if row.get("ghi_chu_quan_ly") is not None:
				theo_ma[ma].ghi_chu_quan_ly = row["ghi_chu_quan_ly"]
		else:
			doc.append("items", {
				"item_code": ma, "so_luong_de_xuat": 0,
				"so_luong_duyet": float(row.get("so_luong_duyet") or 0),
				"nguon_dong": "Quản lý thêm",
			})
	doc.save(ignore_permissions=True)
```

**`request_id` chuyển từ tầng đơn hàng xuống phiếu (§5.2).** Hôm nay `dat_hang.tao_sales_order` **bắt buộc** `request_id` và tự trả lại đơn cũ nếu trùng — đó là chốt chống tạo đơn trùng (BR-O12), không được bỏ. Đường duyệt truyền `doc.request_id or doc.name` (xem code Step 4): tên phiếu là một khoá đã duy nhất toàn cục, nên **bấm Duyệt hai lần trả về cùng một Sales Order** thay vì tạo hai đơn. Viết một test riêng cho việc này:

```python
	def test_bam_duyet_hai_lan_khong_tao_hai_don(self):
		doc = self._cho_duyet()
		a = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		doc.reload()
		doc.trang_thai = "Chờ duyệt"      # giả lập bấm lại khi UI chưa kịp cập nhật
		doc.db_update()
		b = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		self.assertEqual(a["sales_order"], b["sales_order"])
```

**Phiếu `Đã duyệt` (§5.4b dòng 3):** đã thành Sales Order → **không** thêm luật huỷ mới ở doctype này. Huỷ đi theo đúng luật huỷ đơn đang chạy (`portal_order_huy`), và phiếu đề xuất giữ nguyên trạng thái `Đã duyệt` trỏ về đơn đã huỷ. Dựng một trạng thái thứ hai ở đây sẽ tạo hai nguồn sự thật về "đơn này còn sống không".

**Hai cái bẫy phải cài (§5.6):**
1. **Hạn mức hợp đồng khung là tài nguyên chung giữa các khoa.** Đề xuất chỉ **cảnh báo**; hạn mức chỉ **trừ lúc DUYỆT**. Hết hạn mức lúc duyệt → duyệt **thất bại kèm tên khoa đã tiêu mất**, không im lặng cắt số lượng.
2. **Giá tính lại tại thời điểm duyệt**, nhưng khác giá khoa đã thấy thì **báo cho quản lý trước khi họ bấm**, không đổi lặng lẽ.

- [ ] **Step 1: Viết test đỏ**

```python
	def test_duyet_sinh_sales_order_chi_tu_dong_co_so_luong_duyet(self):
		"""§5.3 — dòng hạ về 0 KHÔNG đi vào đơn, nhưng VẪN CÒN trên phiếu."""
		doc = self._cho_duyet_hai_dong()
		doc.items[1].so_luong_duyet = 0
		doc.save(ignore_permissions=True)
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(len(so.items), 1)
		doc.reload()
		self.assertEqual(len(doc.items), 2)          # phiếu gốc còn nguyên
		self.assertEqual(doc.items[1].so_luong_de_xuat, 5)

	def test_don_mang_dung_khoa_cua_phieu(self):
		"""Chốt của cả đề án: đơn sinh ra PHẢI mang khoa, nếu không thì
		chính nhân viên khoa đó không mở lại được đơn mình vừa đặt."""
		doc = self._cho_duyet()
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		self.assertEqual(
			frappe.db.get_value("Sales Order", kq["sales_order"], "custom_khoa_phong"),
			doc.khoa_phong,
		)

	def test_don_tro_nguoc_ve_phieu_goc(self):
		doc = self._cho_duyet()
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		self.assertEqual(
			frappe.db.get_value("Sales Order", kq["sales_order"], "custom_de_xuat"),
			doc.name,
		)

	def test_het_han_muc_thi_duyet_that_bai_kem_ten_khoa(self):
		"""§5.6 — không im lặng cắt số lượng xuống."""
		doc = self._cho_duyet_vuot_han_muc()
		with self.assertRaises(frappe.ValidationError) as ctx:
			de_xuat_duyet.duyet(doc.name)
		self.assertIn("Dược", str(ctx.exception))    # tên khoa đã tiêu mất

	def test_nhan_vien_khoa_khong_duyet_duoc(self):
		frappe.set_user(self.user_huyethoc)
		with self.assertRaises(frappe.PermissionError):
			de_xuat.de_xuat_duyet_phieu(self.phieu_huyethoc)

	def test_quan_ly_duyet_duoc(self):
		"""VẾ DƯƠNG."""
		frappe.set_user(self.user_quan_ly)
		kq = de_xuat.de_xuat_duyet_phieu(self.phieu_huyethoc)
		self.assertTrue(kq["sales_order"])

	def test_duyet_ghi_du_khoi_truy_vet(self):
		"""§5.2 — người duyệt, thời điểm, tư cách."""
		frappe.set_user(self.user_quan_ly)
		de_xuat.de_xuat_duyet_phieu(self.phieu_huyethoc)
		doc = frappe.get_doc("Portal De Xuat Mua", self.phieu_huyethoc)
		self.assertEqual(doc.nguoi_duyet, self.user_quan_ly)
		self.assertTrue(doc.thoi_diem_duyet)
		self.assertEqual(doc.duyet_voi_tu_cach, "Quản lý chính")
```

- [ ] **Step 2: Chạy, xác nhận đỏ**
- [ ] **Step 3: Viết patch v1_24 thêm 2 custom field lên Sales Order**

Dùng `create_custom_field` (**số ít** — bản số nhiều `create_custom_fields` không đồng bộ schema theo cách này). Khai vào `patches.txt`. Nhớ: `CustomField.validate_insert_after()` tồn tại nhưng **không bao giờ được gọi** — `insert_after` sai sẽ im lặng đặt sai chỗ.

- [ ] **Step 4: Viết `de_xuat_duyet.py`**

```python
"""Lõi duyệt đề xuất → Sales Order (spec §5.6).

Tách khỏi endpoint theo đúng khuôn `dat_hang.py`: hàm này nhận tên phiếu,
KHÔNG đọc `frappe.session.user` để quyết định quyền — việc xác định người
gọi có được duyệt hay không thuộc TRÁCH NHIỆM của endpoint gọi nó. Nhờ vậy
kế hoạch C (uỷ quyền) chỉ phải sửa một chỗ ở tầng endpoint.
"""

import frappe
from frappe.utils import now_datetime

from miyano_portal import dat_hang
from miyano_portal.portal_context import han_muc_con


def duyet_va_tao_don(ten_phieu: str, nguoi_duyet: str,
                     tu_cach="Quản lý chính", uy_quyen=None) -> dict:
	doc = frappe.get_doc("Portal De Xuat Mua", ten_phieu)
	doc._kiem_chuyen("Đã duyệt")

	# §5.3 — CHỈ dòng có so_luong_duyet > 0 đi vào đơn. Dòng hạ về 0 VẪN
	# CÒN trên phiếu: đó là cách giữ "khoa xin gì / duyệt gì" mà không cần
	# một bản snapshot song song sớm muộn cũng lệch.
	dong = [
		{"item_code": d.item_code, "qty": float(d.so_luong_duyet or 0)}
		for d in doc.items if float(d.so_luong_duyet or 0) > 0
	]
	if not dong and not doc.dat_ngoai:
		frappe.throw(
			"Không còn dòng nào có số lượng duyệt lớn hơn 0.",
			frappe.ValidationError,
		)

	if doc.loai_don == "HĐNT" and doc.hdnt:
		_kiem_han_muc(doc, dong)

	kq = dat_hang.tao_sales_order(
		doc.customer,
		mode="hdnt" if doc.loai_don == "HĐNT" else "ban_le",
		contract=doc.hdnt, items=dong,
		dat_ngoai=[d.as_dict() for d in doc.dat_ngoai],
		delivery_date=doc.ngay_can, address=doc.dia_chi_giao,
		note=doc.ghi_chu, request_id=doc.request_id or doc.name,
		khoa_phong=doc.khoa_phong,
	)

	# Ruling preflight C2 — KHÔNG tự viết trạng thái ở đây. `doc.duyet()`
	# (Task 3) là nơi duy nhất viết trạng thái đã duyệt + khối truy vết;
	# hai chỗ cùng viết một sự thật thì sớm muộn cũng lệch.
	doc.sales_order = kq["sales_order"]
	doc.duyet(nguoi_duyet, tu_cach=tu_cach, uy_quyen=uy_quyen)

	frappe.db.set_value("Sales Order", kq["sales_order"], {
		"custom_de_xuat": doc.name,
		"custom_ma_tra_cuu": doc.ma_de_xuat,
	})
	return {"sales_order": kq["sales_order"], "de_xuat": doc.name}


def _kiem_han_muc(doc, dong):
	"""§5.6 — hạn mức HĐNT là tài nguyên CHUNG giữa các khoa.

	Trừ ở lúc DUYỆT, không phải lúc đề xuất. Hết hạn mức thì THẤT BẠI kèm
	tên khoa đã tiêu mất — KHÔNG im lặng cắt số lượng xuống, vì người duyệt
	sẽ không biết mình vừa duyệt một số khác số họ nhìn thấy.
	"""
	for d in dong:
		han, da_dung = han_muc_con(doc.hdnt, d["item_code"])
		if han is None:
			continue
		if d["qty"] > han:
			khoa_da_tieu = frappe.get_all(
				"Sales Order",
				filters={"custom_hdnt": doc.hdnt, "docstatus": ["<", 2]},
				fields=["distinct custom_khoa_phong as khoa"],
			)
			ten_khoa = ", ".join(
				frappe.db.get_value("Customer Department", r.khoa, "ten_khoa_phong")
				or "Toàn viện" for r in khoa_da_tieu if r.khoa
			) or "khoa khác"
			frappe.throw(
				f'Hạn mức hợp đồng cho "{d["item_code"]}" chỉ còn {han}, '
				f"phiếu này duyệt {d['qty']}. Đã dùng bởi: {ten_khoa}.",
				frappe.ValidationError,
			)
```

*Người thi công:* `han_muc_con(blanket_order, item_code) -> tuple[float | None, float]` đã có sẵn ở `portal_context.py:336` — dùng lại, không viết mới. Field `Sales Order.custom_hdnt` **đã kiểm trên `erptest.local`**, có thật (`information_schema.columns`, 19/08). `Sales Order Item` còn có `blanket_order` chuẩn ERPNext — **không** nhầm hai cái: `custom_hdnt` ở đầu đơn là hợp đồng khung của Miyano, `blanket_order` ở dòng hàng là cơ chế lõi ERPNext.

- [ ] **Step 4b: Phơi `ma_tra_cuu` qua API đơn hàng (QĐ-A4)**

Thêm `custom_ma_tra_cuu` vào danh sách field mà `portal_order_history` và `portal_order_track` trả về, dưới khoá `ma_tra_cuu`. **Không** thay `name`: khách cần mã của họ để đọc, Miyano cần `SAL-ORD-*` để đối chiếu, và cổng phải trả **cả hai** cho kế hoạch B chọn cách hiển thị.

```python
	def test_api_don_hang_tra_ca_hai_ma(self):
		frappe.set_user(self.user_quan_ly)
		rows = portal.portal_order_history()
		r = next(x for x in rows if x["name"] == self.don_da_duyet)
		self.assertTrue(r["name"].startswith("SAL-ORD-"))   # mã hệ thống
		self.assertIn("-HUYETHOC-", r["ma_tra_cuu"])        # mã của khách

	def test_don_cu_khong_co_ma_tra_cuu_thi_khong_vo(self):
		# 102 đơn cũ không có phiếu đề xuất đứng sau — field rỗng, KHÔNG lỗi.
		# Đây là chốt tương thích ngược, phải xanh cả trước lẫn sau.
		frappe.set_user(self.user_quan_ly)
		rows = portal.portal_order_history()
		r = next(x for x in rows if x["name"] == self.don_cu_khong_co_de_xuat)
		self.assertFalse(r.get("ma_tra_cuu"))
```

- [ ] **Step 5: Thêm 3 endpoint + khai vào `DA_AP_PHAM_VI`**

```python
@frappe.whitelist()
def de_xuat_duyet_phieu(ten, dieu_chinh=None) -> dict:
	"""Chốt quyền DUY NHẤT của đường duyệt. Kế hoạch C (uỷ quyền) sửa ĐÚNG
	dòng `la_quan_ly()` này, không đụng `de_xuat_duyet.duyet`."""
	if not la_quan_ly():
		raise frappe.PermissionError("Chỉ quản lý mới duyệt được đề xuất.")
	doc = _phieu_cua_toi(ten, cho_quan_ly=True)
	if dieu_chinh:
		_ap_dieu_chinh(doc, dieu_chinh)
	from miyano_portal import de_xuat_duyet
	return de_xuat_duyet.duyet_va_tao_don(doc.name, frappe.session.user)


@frappe.whitelist()
def de_xuat_tu_choi(ten, ly_do) -> dict:
	if not la_quan_ly():
		raise frappe.PermissionError("Chỉ quản lý mới từ chối được đề xuất.")
	doc = _phieu_cua_toi(ten, cho_quan_ly=True)
	doc.tu_choi(ly_do)
	return {"name": doc.name}


@frappe.whitelist()
def de_xuat_huy(ten) -> dict:
	"""§5.4b — từ Chờ duyệt trở đi CHỈ quản lý huỷ được. Nhân viên không
	huỷ phiếu đã gửi: một phiếu đang nằm trong danh sách chờ của quản lý mà
	biến mất giữa chừng là thứ khó chịu nhất cho người duyệt."""
	if not la_quan_ly():
		raise frappe.PermissionError("Chỉ quản lý mới huỷ được phiếu đã gửi.")
	doc = _phieu_cua_toi(ten, cho_quan_ly=True)
	doc.huy()
	return {"name": doc.name}
```
- [ ] **Step 6: Chạy `bench --site erptest.local migrate`, xác nhận patch CHẠY THẬT**

```bash
bench --site erptest.local mariadb -e "select name, creation from \`tabPatch Log\` where patch like '%them_de_xuat%'"
```
Không có dòng nào = patch chưa chạy (bẫy `install_app` fake-complete). Dừng, báo cáo.

- [ ] **Step 7: Chạy toàn bộ suite, kỳ vọng 1169 OK**
- [ ] **Step 8: Commit** — `feat(de-xuat): duong duyet sinh Sales Order, han muc va gia tinh lai`

---

## Task 7: Quản lý đặt trực tiếp vẫn đi qua một đường giấy tờ (§5.5)

**Files:**
- Modify: `miyano_portal/api/portal.py` *(`portal_order_place`)*
- Modify: `miyano_portal/portal_context.py` *(thêm helper)*
- Modify: `miyano_portal/tests/test_pham_vi_endpoint.py` *(sửa lý do trong `MIEN_PHAM_VI`)*
- Test: `miyano_portal/tests/test_de_xuat_duyet.py` *(thêm class)*

**Mâu thuẫn phải gỡ trong task này — đọc trước khi viết code:**

`portal_order_place` hiện có bình luận C1: *"hàm này KHÔNG có tham số `khoa_phong`, và không được thêm"*. Nhưng §5.5 nói giỏ hàng của quản lý **có ô chọn khoa**, mặc định "Toàn viện". Hai điều này không cùng đứng được như đang viết.

Sự thật phân biệt: `dat_hang.tao_sales_order` kiểm khoa ↔ **khách hàng**; `portal_order_place` suy khoa từ **phiên**. **Không chỗ nào kiểm khoa ↔ NGƯỜI GỌI.** Đó chính là phép kiểm còn thiếu.

**Chốt:** thêm một helper có tên, **role-aware**, ở `portal_context.py`:

```python
def khoa_phong_cho_don(khoa_phong_client=None, user=None) -> str | None:
	"""Khoa phòng được phép đóng dấu lên đơn/phiếu của phiên hiện tại.

	Đây là phép kiểm khoa ↔ NGƯỜI GỌI — thứ mà `dat_hang.tao_sales_order`
	(kiểm khoa ↔ KHÁCH HÀNG) và `portal_order_place` (suy khoa từ phiên)
	đều KHÔNG làm.

	- Nhân viên khoa: BỎ QUA hoàn toàn giá trị client gửi, luôn trả khoa
	  của chính họ. Nhận từ client sẽ cho nhân viên khoa A đóng dấu đơn
	  thành khoa B.
	- Quản lý: được chọn, vì họ nhìn xuyên mọi khoa. Nhưng vẫn phải kiểm
	  khoa đó THUỘC bệnh viện của họ và đang `active`. `None` = Toàn viện.
	"""
```

Rồi `portal_order_place` nhận thêm tham số `khoa_phong=None` và **đi qua helper này**, không dùng thẳng. Cập nhật bình luận C1 cho khớp thực tế mới — bình luận nói sai về code là nợ tệ hơn không có bình luận.

- [ ] **Step 1: Viết test đỏ**

```python
	def test_nhan_vien_khoa_gui_khoa_khac_van_bi_ep_ve_khoa_minh(self):
		"""C1 vẫn đứng: client không tự chọn khoa được — với NHÂN VIÊN."""
		frappe.set_user(self.user_huyethoc)
		kq = portal.portal_order_place(..., khoa_phong=self.khoa_duoc)
		self.assertEqual(
			frappe.db.get_value("Sales Order", kq["sales_order"], "custom_khoa_phong"),
			self.khoa_huyethoc,
		)

	def test_quan_ly_dat_ho_mot_khoa(self):
		"""§5.5 — VẾ DƯƠNG của test trên."""
		frappe.set_user(self.user_quan_ly)
		kq = portal.portal_order_place(..., khoa_phong=self.khoa_duoc)
		self.assertEqual(
			frappe.db.get_value("Sales Order", kq["sales_order"], "custom_khoa_phong"),
			self.khoa_duoc,
		)

	def test_quan_ly_khong_dat_duoc_cho_khoa_benh_vien_khac(self):
		frappe.set_user(self.user_quan_ly)
		with self.assertRaises(frappe.PermissionError):
			portal.portal_order_place(..., khoa_phong=self.khoa_benh_vien_b)

	def test_quan_ly_dat_toan_vien_thi_ma_la_CHUNG(self):
		frappe.set_user(self.user_quan_ly)
		kq = portal.portal_order_place(..., khoa_phong=None)
		phieu = frappe.get_doc("Portal De Xuat Mua", kq["de_xuat"])
		self.assertIn("-CHUNG-", phieu.ma_de_xuat)
		self.assertEqual(phieu.trang_thai, "Đã duyệt")

	def test_moi_don_deu_co_dung_mot_phieu_dung_sau(self):
		"""§5.5 — không có hai loại đơn với hai lịch sử khác nhau."""
		frappe.set_user(self.user_quan_ly)
		kq = portal.portal_order_place(...)
		self.assertTrue(
			frappe.db.get_value("Sales Order", kq["sales_order"], "custom_de_xuat")
		)

	def test_nhan_vien_khoa_goi_thang_portal_order_place_bi_tu_choi_ro_rang(self):
		"""§5.5 — không phải lỗi 500 khó hiểu."""
		frappe.set_user(self.user_huyethoc)
		with self.assertRaises(frappe.ValidationError) as ctx:
			portal.portal_order_place(...)
		self.assertIn("gửi duyệt", str(ctx.exception))
```

*Chú ý mâu thuẫn giữa test 1 và test cuối:* nếu nhân viên khoa **bị chặn hẳn** ở `portal_order_place` (§5.5 câu cuối) thì test 1 không có nghĩa. Chốt: **chặn hẳn** là đúng spec; giữ test 1 dưới dạng kiểm `khoa_phong_cho_don()` trực tiếp thay vì qua endpoint. Người thi công sửa test 1 cho khớp **trước** khi viết code, và ghi lý do vào commit.

- [ ] **Step 2: Chạy, xác nhận đỏ**
- [ ] **Step 3: Viết `khoa_phong_cho_don()` trong `portal_context.py`**
- [ ] **Step 4: Sửa `portal_order_place` đi qua đường đề xuất tự duyệt**
- [ ] **Step 5: Cập nhật lý do của `portal_order_place` trong `MIEN_PHAM_VI`** — lý do cũ ("phạm vi do dat_hang chốt, suy khoa TỪ phiên") **không còn đúng** sau task này.
- [ ] **Step 6: Chạy toàn bộ suite, kỳ vọng 1175 OK**
- [ ] **Step 7: Commit** — `feat(de-xuat): quan ly dat truc tiep van sinh mot phieu de xuat tu duyet`

---

## Task 8: Thông báo theo khoa (§5.8)

**Files:**
- Modify: `miyano_portal/portal_thong_bao_khach.py`
- Test: `miyano_portal/tests/test_de_xuat_thong_bao.py` *(mới)*

**Việc này cũng sửa một chỗ đang thô:** hôm nay thông báo giao hàng gửi cho **mọi** tài khoản của bệnh viện. Với một tài khoản thì đúng; với mười lăm tài khoản thì khoa Dược nhận thông báo về hàng của khoa Huyết học mỗi ngày.

| Việc | Ai nhận |
|---|---|
| Khoa gửi đề xuất | Quản lý *(+ người được uỷ quyền — kế hoạch C)* |
| Quản lý duyệt / từ chối | Người lập đề xuất + thành viên khác của khoa đó |
| Miyano xác nhận, hẹn giao, giao hàng | Quản lý + thành viên của khoa đứng tên đơn |

- [ ] **Step 1: Viết test đỏ** — gồm **vế dương** (người đúng khoa **có** nhận) và **vế âm** (khoa khác **không** nhận).
- [ ] **Step 2: Chạy, xác nhận đỏ**
- [ ] **Step 3: Thêm `_portal_users_theo_khoa(customer, khoa_phong)` cạnh `_portal_users_cua_khach` đã có**
- [ ] **Step 4–5: Test module xanh, suite xanh, kỳ vọng 1181 OK**
- [ ] **Step 6: Commit** — `feat(de-xuat): thong bao chon nguoi nhan theo khoa`

---

## Task 9: Bịt lỗ "sửa số lượng sau khi đã duyệt"

**Files:**
- Modify: `miyano_portal/miyano_portal/doctype/portal_de_xuat_mua/portal_de_xuat_mua.py`
- Modify: `miyano_portal/miyano_portal/doctype/portal_de_xuat_mua_item/portal_de_xuat_mua_item.json`
- Modify: `miyano_portal/api/de_xuat.py`
- Modify: `miyano_portal/api/portal.py` *(`portal_order_sua_so_luong`)*
- Modify: `miyano_portal/tests/test_pham_vi_endpoint.py`
- Test: `miyano_portal/tests/test_de_xuat_sua_sau_duyet.py` *(mới)*

**Lỗ hổng đang có (đã đo trên code, 19/08):** `portal_order_sua_so_luong` chỉ chặn theo `workflow_state == "Chờ khách đồng ý"` — không chặn theo vai trò. Sau khi quản lý duyệt 10 hộp và Miyano báo giá, **nhân viên khoa** đổi được thành 100 hộp và đơn quay về "Chờ xác nhận" mà **không ai duyệt lại**. Cổng duyệt sẽ có lỗ ngay từ ngày bật.

**Chủ đầu tư chốt 19/08 (§12 Q4):** nhân viên **vẫn sửa được**, nhưng sửa xong đơn **quay lại quản lý duyệt lần nữa**.

**Thiết kế:**

Nhân viên **không** chạm thẳng vào Sales Order nữa. Họ ghi số lượng muốn sửa lên **phiếu đề xuất**, phiếu chuyển sang trạng thái mới `Chờ duyệt sửa`; quản lý duyệt thì lúc đó mới gọi lõi `portal_order_sua_so_luong` đang có.

Thêm một cạnh đi ra khỏi `Đã duyệt` — trạng thái này thôi là trạng thái kết thúc:

```python
	CHUYEN_HOP_LE = {
		TRANG_THAI_NHAP: {TRANG_THAI_CHO_DUYET},
		TRANG_THAI_CHO_DUYET: {TRANG_THAI_DA_DUYET, TRANG_THAI_TU_CHOI, TRANG_THAI_DA_HUY},
		TRANG_THAI_TU_CHOI: {TRANG_THAI_CHO_DUYET, TRANG_THAI_DA_HUY},
		# Task 9 — `Đã duyệt` THÔI là trạng thái kết thúc. Cạnh này là chỗ
		# duy nhất đi ra, và nó quay về đúng `Đã duyệt` sau khi quản lý xử lý.
		TRANG_THAI_DA_DUYET: {TRANG_THAI_CHO_DUYET_SUA},
		TRANG_THAI_CHO_DUYET_SUA: {TRANG_THAI_DA_DUYET},
	}
```

Thêm field child `so_luong_xin_sua` (Float) — **cột thứ ba**, không đè lên `so_luong_duyet`: quản lý phải nhìn thấy *đã duyệt bao nhiêu* cạnh *khoa xin đổi thành bao nhiêu*, đúng tinh thần §5.3 (không xoá dữ liệu gốc để ghi dữ liệu mới).

- [ ] **Step 1: Viết test đỏ**

```python
	def test_nhan_vien_khoa_khong_goi_thang_portal_order_sua_so_luong(self):
		"""Lỗ hổng chính. Chặn theo VAI TRÒ, không chỉ theo workflow_state."""
		frappe.set_user(self.user_huyethoc)
		with self.assertRaises(frappe.PermissionError) as ctx:
			portal.portal_order_sua_so_luong(self.don_da_duyet, self.dong_moi)
		self.assertIn("xin sửa", str(ctx.exception))

	def test_quan_ly_sua_thang_thi_phieu_de_xuat_CUNG_cap_nhat(self):
		"""VẾ DƯƠNG — và phải PHÂN BIỆT ĐƯỢC, không phải một test xanh sẵn.

		Khẳng định đầu (đơn về "Chờ xác nhận") xanh từ trước khi có task này
		nên tự nó không canh gì. Khẳng định thứ hai mới là thứ mới: quản lý
		sửa thẳng thì phiếu đề xuất đứng sau PHẢI đi theo — nếu không, hai
		chứng từ nói hai số khác nhau và khối truy vết §5.2 thành vô nghĩa.
		Hôm nay chưa có phiếu nào nên khẳng định này ĐỎ.
		"""
		frappe.set_user(self.user_quan_ly)
		portal.portal_order_sua_so_luong(self.don_da_duyet, self.dong_moi)
		self.assertEqual(
			frappe.db.get_value("Sales Order", self.don_da_duyet, "workflow_state"),
			"Chờ xác nhận",
		)
		doc = frappe.get_doc("Portal De Xuat Mua", self.phieu_da_duyet)
		self.assertEqual(doc.items[0].so_luong_duyet, 100)
		self.assertEqual(doc.trang_thai, "Đã duyệt")

	def test_don_KHONG_qua_duong_de_xuat_thi_giu_nguyen_hanh_vi_cu(self):
		"""Sáu tài khoản đang chạy: đơn cũ không có `custom_de_xuat` →
		không được đổi hành vi. Đây là chốt tương thích ngược."""
		frappe.set_user(self.user_quan_ly)
		portal.portal_order_sua_so_luong(self.don_cu_khong_co_de_xuat, self.dong_moi)
		self.assertEqual(
			frappe.db.get_value(
				"Sales Order", self.don_cu_khong_co_de_xuat, "workflow_state"
			),
			"Chờ xác nhận",
		)

	def test_nhan_vien_xin_sua_thi_phieu_ve_cho_duyet_sua(self):
		frappe.set_user(self.user_huyethoc)
		de_xuat.de_xuat_xin_sua(self.phieu_da_duyet, self.dong_moi)
		doc = frappe.get_doc("Portal De Xuat Mua", self.phieu_da_duyet)
		self.assertEqual(doc.trang_thai, "Chờ duyệt sửa")
		self.assertEqual(doc.items[0].so_luong_xin_sua, 100)
		self.assertEqual(doc.items[0].so_luong_duyet, 10)   # cột cũ CÒN NGUYÊN

	def test_don_chua_doi_gi_truoc_khi_quan_ly_duyet_sua(self):
		"""Chốt của cả task: xin sửa KHÔNG tự nó chạm vào đơn."""
		frappe.set_user(self.user_huyethoc)
		de_xuat.de_xuat_xin_sua(self.phieu_da_duyet, self.dong_moi)
		so = frappe.get_doc("Sales Order", self.don_da_duyet)
		self.assertEqual(so.items[0].qty, 10)

	def test_quan_ly_duyet_sua_thi_don_moi_doi(self):
		frappe.set_user(self.user_huyethoc)
		de_xuat.de_xuat_xin_sua(self.phieu_da_duyet, self.dong_moi)
		frappe.set_user(self.user_quan_ly)
		de_xuat.de_xuat_duyet_sua(self.phieu_da_duyet)
		so = frappe.get_doc("Sales Order", self.don_da_duyet)
		self.assertEqual(so.items[0].qty, 100)
		doc = frappe.get_doc("Portal De Xuat Mua", self.phieu_da_duyet)
		self.assertEqual(doc.trang_thai, "Đã duyệt")
		self.assertEqual(doc.items[0].so_luong_duyet, 100)

	def test_quan_ly_tu_choi_sua_thi_don_giu_nguyen(self):
		frappe.set_user(self.user_huyethoc)
		de_xuat.de_xuat_xin_sua(self.phieu_da_duyet, self.dong_moi)
		frappe.set_user(self.user_quan_ly)
		de_xuat.de_xuat_tu_choi_sua(self.phieu_da_duyet, "Vượt dự toán quý")
		so = frappe.get_doc("Sales Order", self.don_da_duyet)
		self.assertEqual(so.items[0].qty, 10)
		doc = frappe.get_doc("Portal De Xuat Mua", self.phieu_da_duyet)
		self.assertEqual(doc.trang_thai, "Đã duyệt")
		self.assertFalse(doc.items[0].so_luong_xin_sua)   # dọn sạch yêu cầu cũ
```

- [ ] **Step 2: Chạy, xác nhận đỏ**

Chú ý: `test_don_KHONG_qua_duong_de_xuat_thi_giu_nguyen_hanh_vi_cu` **phải xanh sẵn** — nó là chốt tương thích ngược cho 6 tài khoản đang chạy, nhiệm vụ của nó là **vẫn xanh sau khi sửa**. Đây là test **duy nhất** trong task được phép xanh từ đầu. Bảy test còn lại phải đỏ; cái nào xanh sẵn thì nó không canh gì cả — sửa cho nó phân biệt được rồi mới đi tiếp.

- [ ] **Step 3: Chặn theo vai trò — qua MỘT helper có tên, không viết inline**

Guard này **không** viết thẳng trong `portal_order_sua_so_luong`. Task 7 đã dựng `khoa_phong_cho_don()` ở `portal_context.py` đúng vì các phép kiểm "khoa ↔ người gọi" trước đó nằm rải rác; viết thêm một cổng role-aware inline ở module khác là quay lại đúng vấn đề đó. Đặt cạnh nó:

```python
def dam_bao_duoc_sua_don_da_duyet(so, user=None):
	"""Chốt §12 Q4 — nhân viên khoa KHÔNG sửa thẳng số lượng trên đơn đã
	được quản lý duyệt. Quản lý duyệt 10 hộp mà hàng về 100 hộp là lỗ hổng
	của chính cổng duyệt.

	CHỈ áp cho đơn ĐI QUA đường đề xuất. Đơn cũ không có phiếu đứng sau thì
	không có gì để quay về duyệt lại — chặn chúng chỉ lấy mất một thao tác
	mà không đổi lại được gì.

	FAIL-CLOSED KHI THIẾU CỘT (bài học sự cố `custom_khoa_phong`): nếu patch
	v1_24 chưa chạy thì `custom_de_xuat` KHÔNG tồn tại, `so.get()` trả
	falsy, và cổng này **mở toang trong im lặng** — tệ hơn sự cố cũ, vốn ít
	ra còn nổ thành lỗi 1054 nhìn thấy được. Nên kiểm cột tồn tại TRƯỚC, và
	thiếu cột thì CHẶN nhân viên khoa chứ không thả.
	"""
	if la_quan_ly(user):
		return
	if not _cot_de_xuat_ton_tai():
		raise frappe.PermissionError(
			"Hệ thống chưa hoàn tất cập nhật. Liên hệ Miyano."
		)
	if not so.get("custom_de_xuat"):
		return
	raise frappe.PermissionError(
		"Đơn này đã được quản lý duyệt. Dùng chức năng xin sửa số lượng để "
		"gửi lại cho quản lý xem."
	)
```

`_cot_de_xuat_ton_tai()` viết theo đúng khuôn `_cot_khoa_phong_ton_tai()` đã có ở `portal_context.py:132` (cache cấp tiến trình). Rồi `portal_order_sua_so_luong` chỉ thêm **một dòng**: `dam_bao_duoc_sua_don_da_duyet(so)`.

Thêm test cho chính nhánh fail-closed này — nếu không có nó thì nhánh nguy hiểm nhất là nhánh duy nhất không ai chạy qua:

```python
	def test_nhan_vien_VAN_chap_nhan_bao_gia_duoc(self):
		# Chủ đầu tư chốt 19/08: "quản lý duyệt 10 hộp, Miyano báo giá,
		# nhân viên là xong là đơn đi thành sales order".
		#
		# CHỈ đổi số lượng mới phải quay lại quản lý. ĐỒNG Ý với báo giá —
		# không đổi gì — thì nhân viên tự làm xong. Bắt duyệt lại ở đây sẽ
		# làm tắc đúng con đường thông thường mà không kiểm soát thêm được
		# gì: số lượng vẫn đúng số quản lý đã duyệt.
		# KHÔNG khẳng định tên trạng thái đích: nó do Workflow document quyết
		# định, không do code này, và plan chưa đọc Workflow đó. Khẳng định
		# đúng thứ test này canh — nhân viên KHÔNG bị chặn, và đơn đã rời
		# trạng thái chờ.
		frappe.set_user(self.user_huyethoc)
		portal.portal_order_accept(self.don_da_duyet, action="dong_y")
		self.assertNotEqual(
			frappe.db.get_value("Sales Order", self.don_da_duyet, "workflow_state"),
			"Chờ khách đồng ý",
		)

	def test_thieu_cot_custom_de_xuat_thi_CHAN_chu_khong_tha(self):
		"""Patch v1_24 chưa chạy → cổng phải ĐÓNG, không mở im lặng."""
		frappe.set_user(self.user_huyethoc)
		with patch.object(portal_context, "_cot_de_xuat_ton_tai", return_value=False):
			with self.assertRaises(frappe.PermissionError) as ctx:
				portal.portal_order_sua_so_luong(self.don_da_duyet, self.dong_moi)
		self.assertIn("chưa hoàn tất", str(ctx.exception))
```

- [ ] **Step 4: Thêm `de_xuat_xin_sua`, `de_xuat_duyet_sua`, `de_xuat_tu_choi_sua`**

`de_xuat_xin_sua` — chỉ `owner` hoặc thành viên cùng khoa; ghi `so_luong_xin_sua`, chuyển `Chờ duyệt sửa`, thông báo quản lý (dùng hàm Task 8).
`de_xuat_duyet_sua` — chỉ quản lý; gọi lõi `portal_order_sua_so_luong` **với tư cách quản lý**, chép `so_luong_xin_sua` → `so_luong_duyet`, xoá `so_luong_xin_sua`, về `Đã duyệt`.
`de_xuat_tu_choi_sua` — chỉ quản lý; xoá `so_luong_xin_sua`, về `Đã duyệt`, ghi lý do vào `ghi_chu_quan_ly` của dòng.

- [ ] **Step 4b: Ghi ngược về phiếu khi QUẢN LÝ sửa thẳng (Ruling preflight C4)**

`test_quan_ly_sua_thang_thi_phieu_de_xuat_CUNG_cap_nhat` đòi việc này nhưng plan gốc không có Step nào cài. Sau khi `portal_order_sua_so_luong` sửa đơn thành công, nếu đơn có `custom_de_xuat` thì đồng bộ `so_luong_duyet` trên phiếu theo số mới. Không có nó thì hai chứng từ nói hai số khác nhau và khối truy vết §5.2 thành vô nghĩa.

- [ ] **Step 5: Ba tên mới vào `DA_AP_PHAM_VI`**
- [ ] **Step 5b: Xác nhận patch v1_24 ĐÃ CHẠY trên site đang test**

Guard ở Step 3 phụ thuộc cột `Sales Order.custom_de_xuat` do patch v1_24 (Task 6) tạo. Kiểm lại **ở chính task này**, không tin kết quả của Task 6:

```bash
bench --site erptest.local mariadb -e "select name, creation from \`tabPatch Log\` where patch like '%them_de_xuat%'"
```

Không có dòng nào = patch chưa chạy trên site này (bẫy `install_app` fake-complete đã ghi trong bộ nhớ dự án). Dừng, chạy `bench --site erptest.local migrate`, kiểm lại.
- [ ] **Step 6: Chạy toàn bộ suite, kỳ vọng 1188 OK**
- [ ] **Step 7: Commit** — `feat(de-xuat): sua so luong sau duyet phai quay lai quan ly (Q4)`

---

## Nghiệm thu cuối kế hoạch

- [ ] `bench --site erptest.local run-tests --app miyano_portal` — xanh, **chạy hai lần liên tiếp**, đúng một tiến trình.
- [ ] `bench --site erptest.local migrate` trên site đã có dữ liệu — không ném lỗi giữa chừng.
- [ ] Xác nhận patch v1_24 **đã chạy thật** bằng truy vấn `tabPatch Log`.
- [ ] **Nghiệm thu quan trọng nhất:** trên site chưa có `Nhân viên khoa` nào, mọi hành vi giữ nguyên như trước kế hoạch này (§9). Đặt một đơn bằng tài khoản quản lý hiện có, xác nhận nó vẫn ra đơn — và giờ kèm một phiếu đề xuất tự duyệt đứng sau.
- [ ] Cập nhật `docs/HDSD-phan-quyen-khoa-phong.md` + chạy lại `docs/md2docx.py`.

---

## Sau kế hoạch này

**Kế hoạch B — bước 6 (`docs/superpowers/plans/…-de-xuat-man-hinh.md`):** endpoint `de_xuat_mua_tim(tu_khoa, khoa_phong, gom_da_xu_ly)` (§6.3, khớp cả dòng đặt ngoài — bỏ sót thì phiếu toàn hàng chưa có mã sẽ **vô hình** trước ô tìm kiếm, đúng loại phiếu quản lý cần xem kỹ nhất); ba màn `/de-xuat`, `/de-xuat/:ma`, `/duyet`; sửa `Cart.vue`, `Orders.vue`, `OrderDetail.vue`, menu bên theo vai trò.

**Kế hoạch C — bước 7:** doctype `Portal Delegation` + vế thứ hai của `la_quan_ly()` (hàm đã có docstring dặn trước chỗ này) + cờ `tu_duyet` suy ra + bộ lọc "Đơn tự duyệt khi tôi vắng".

**Mẫu in hoá đơn (QĐ-A4) chưa có kế hoạch.** Chủ đầu tư yêu cầu hoá đơn ghi **mã của bên đặt**. Dữ liệu đã có sau kế hoạch này (`Sales Order.custom_ma_tra_cuu`); việc còn lại là sửa Print Format của Sales Invoice và đối chiếu với module hoá đơn điện tử Fast — **chưa khảo sát**, và bộ nhớ dự án đã ghi rằng hợp đồng dữ liệu của Fast khác với giả định của tài liệu BA. Không gộp bừa vào kế hoạch B.

**Bước 8 (cách ly module kho) vẫn còn nợ** và **không trung lập**: `kho_phieu_get` trả field `sales_order` của phiếu nhập, nên nhân viên khoa vẫn đọc được số đơn, mặt hàng và tổng tiền của khoa khác. Xem spec §11b.
