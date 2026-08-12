# Đợt 1 — Chặn máu (P0) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bịt bốn lỗ P0 của BA v2 (rò rỉ dữ liệu giữa khách hàng, hạn mức không tính đơn nháp, số tiền khách xác nhận không khớp đơn, huỷ phiếu giao mà kho khách không đảo được), cộng phần thuế VAT thật và precision tiền VND.

**Architecture:** Không đổi kiến trúc. Ba tầng giữ nguyên: `api/*.py` lo phiên + quyền + kiểm tham số client; `kho/*.py` và `portal_context.py` lo nghiệp vụ thuần; frontend Vue gọi qua `api.js`. Ba thứ **mới** được thêm: một module chắn `search_guard.py` đứng trước hai endpoint framework, một doctype `Portal Quote Lock` để lưu báo giá chốt (vừa chặn lệch giá vừa là bằng chứng khi khách thắc mắc), và một module `portal_pricing.py` gom toàn bộ việc đọc giá + tính thuế + làm tròn vào một chỗ — hiện việc này đang nằm rải trong `portal_catalog` và `portal_order_place` với hai bản sao khác nhau.

**Tech Stack:** Frappe v15.113.4, ERPNext v15.83.0, Python 3.12, MariaDB, Vue 3 + Vite. Test bằng `FrappeTestCase`.

## Global Constraints

- Spec nguồn: [`docs/BA-v2-ngoai-le-va-UX-miyano_portal.md`](../../BA-v2-ngoai-le-va-UX-miyano_portal.md). Mọi kết luận ✅ trong đó là ràng buộc.
- **Sổ theo dõi:** [`docs/CHANGELOG-khac-phuc-BA-v2.md`](../../CHANGELOG-khac-phuc-BA-v2.md). **Mỗi task kết thúc bằng một mục trong sổ này, ghi trong CÙNG commit với code.** Trước khi mở một file, đọc §3 "Các điểm chồng lấn đã biết" của sổ.
- App: `apps/miyano_portal`, nhánh `develop`, điểm gốc `0ba68b4`. Module Frappe: `Miyano Portal`.
- Site test và dev: `erptest.local`. Bench: `/home/hoangvietyeuem/frappe-bench-yhct`.
- Quyết định đã chốt: **QĐ-01 = A** (giữ chỗ mềm, **3 ngày làm việc**) · **QĐ-02 = A** (có VAT, `Sales Taxes and Charges Template` theo Customer) · **QĐ-03 = B** (đợt 2) · **QĐ-04 = A** (giữ một tầng, không đổi workflow).
- Tiền VND: **precision 0**. Làm tròn **tại thời điểm tính, trước khi cộng dồn** — không bao giờ để `grand_total` dẫn xuất từ float thô trong khi các dòng đã lưu là số đã làm tròn.
- **Không** sửa `precision` của trường tiền trên `Sales Order` / `Sales Invoice` — doctype lõi ERPNext, ngoài phạm vi (BA v2 §NG-12).
- **Không** sửa `blanket_order.py` của ERPNext (QĐ-01 A: hạn mức thật tính ở tầng cổng).
- **Không** bật `track_changes` trên `Customer Stock Ledger Entry` / `Customer Stock Lot Balance`.
- `frappe.get_doc` **không** chạy hook `has_permission` ở build này — mọi chỗ lấy doc theo tên client gửi phải gọi `doc.check_permission("read")` tường minh.
- `frappe.get_all` **luôn** bỏ qua phân quyền, kể cả khi truyền `ignore_permissions=False`. `frappe.get_list` thì không.
- `FrappeTestCase` rollback một lần mỗi **class**, không phải mỗi test. **Không bao giờ** save một document `DocType` trong test (controller của nó `commit()` vô điều kiện — đã từng xoá thật dữ liệu sổ kho trên bench này).
- Mọi thông báo lỗi ra **tiếng Việt**, không lộ tên doctype tiếng Anh, không lộ traceback.
- Chạy test: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.<tên module>`
- Migrate sau khi đổi doctype JSON / thêm patch: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local migrate`
- Build frontend: `cd apps/miyano_portal/frontend && yarn build` (đầu ra `../miyano_portal/public/frontend`). Cache-bust theo **mtime của bundle**, không theo hằng số `__version__`.
- Commit sau mỗi task. **Không push.**

## ⚠️ Ranh giới triển khai — đọc trước khi lên site thật

**Task 3 → 11 là MỘT đơn vị triển khai.** Task 6 làm tham số `quote` thành bắt buộc trên
`portal_order_place`; Task 11 mới dạy giao diện gửi tham số đó. Giữa hai commit ấy,
**mọi khách hàng đều không đặt hàng được**.

| Đơn vị triển khai | Task | Lên site thật riêng được? |
|---|---|---|
| Chắn rò rỉ tìm kiếm | 1 | ✅ Có |
| Precision tiền kho | 2 | ✅ Có (kèm patch dữ liệu) |
| **Giá → thuế → báo giá chốt → giữ chỗ → giao diện** | **3–11** | ❌ **Không.** Chỉ `migrate` + restart khi cả chín task đã xong và bundle đã build |
| Báo động huỷ phiếu giao | 10 | ✅ Có (không phụ thuộc 3–9) |
| Khung bản đồ lỗi | 12 | ✅ Có |

Commit từng task như bình thường — ranh giới ở đây là **triển khai**, không phải commit.

## Thứ tự task và lý do

Task 1 và 2 độc lập hoàn toàn — làm song song được. Từ Task 3 trở đi là một chuỗi
phụ thuộc trên cùng vài hàm; đảo thứ tự sẽ phải sửa lại thứ vừa viết.

```
Task 1  NG-37  search guard          ─── độc lập, ship riêng được
Task 2  NG-12  precision + làm tròn  ─── độc lập

Task 3  NG-10 NG-11  portal_pricing._gia_ban()      ← nền cho mọi thứ sau
   └─ Task 4  NG-09   portal_pricing.tinh_thue()
        └─ Task 5  NG-08  doctype Portal Quote Lock + API-03
             └─ Task 6  NG-08  portal_order_place nhận mã chốt + API-04
                  └─ Task 7  NG-02…NG-05  lọc hợp đồng
                       └─ Task 8  NG-01  giữ chỗ mềm (đọc)
                            └─ Task 9  NG-01  nhả giữ chỗ (job + thông báo)

Task 10 NG-31  báo động ba lớp + API-08   ─── độc lập với 3→9
Task 11 frontend: giỏ hàng + danh mục
Task 12 frontend: khung bản đồ lỗi (3 mã đầu của UX-08)
```

## File Structure

| File | Trách nhiệm | Task |
|---|---|---|
| `miyano_portal/search_guard.py` | **Tạo.** Chắn `search_link` / `search_widget` cho Website User | 1 |
| `miyano_portal/hooks.py` | **Sửa.** Mở `override_whitelisted_methods`; thêm scheduler event | 1, 9 |
| `miyano_portal/tests/test_search_guard.py` | **Tạo.** | 1 |
| 6 file `doctype/*/*.json` kho | **Sửa.** `precision: "0"` cho 10 trường Currency | 2 |
| `miyano_portal/patches/v1_3/round_kho_currency.py` | **Tạo.** Làm tròn dữ liệu cũ rồi dựng lại cache tồn | 2 |
| `miyano_portal/kho/ledger.py` | **Sửa.** Làm tròn trước khi cộng dồn trong `post_lines` | 2 |
| `miyano_portal/kho/voucher.py` | **Sửa.** `tong_tien` = tổng các `thanh_tien` đã làm tròn | 2 |
| `miyano_portal/portal_pricing.py` | **Tạo.** Một chỗ duy nhất đọc giá, tính thuế, làm tròn | 3, 4 |
| `.../doctype/portal_quote_lock/` | **Tạo.** Doctype lưu báo giá chốt | 5 |
| `.../doctype/portal_quote_lock_item/` | **Tạo.** Bảng con | 5 |
| `miyano_portal/api/portal.py` | **Sửa.** `portal_catalog`, `portal_contracts`, `portal_order_place`, + `portal_quote_lock` | 3–8 |
| `miyano_portal/portal_context.py` | **Sửa.** `remaining_qty` → tách lý do + trừ giữ chỗ | 7, 8 |
| `miyano_portal/portal_reservation.py` | **Tạo.** Tính và nhả giữ chỗ mềm | 8, 9 |
| `miyano_portal/kho/delivery_hook.py` | **Sửa.** Ba lớp báo động khi đảo thất bại | 10 |
| `miyano_portal/kho/doi_soat.py` | **Tạo.** Báo cáo đối soát phiếu nhập mồ côi | 10 |
| `frontend/src/store.js`, `views/Cart.vue`, `views/Catalog.vue` | **Sửa.** | 11 |
| `frontend/src/errors.js`, `api.js` | **Tạo/Sửa.** Khung bản đồ lỗi | 12 |

---

## Task 1: NG-37 — bịt rò rỉ sổ hoá đơn giữa các khách hàng

**Files:**
- Create: `miyano_portal/search_guard.py`
- Modify: `miyano_portal/hooks.py:279-288`
- Test: `miyano_portal/tests/test_search_guard.py`

**Interfaces:**
- Produces: `miyano_portal.search_guard.search_link(...)`, `miyano_portal.search_guard.search_widget(...)` — cùng chữ ký với bản gốc của Frappe, đăng ký qua `override_whitelisted_methods`.

**Bối cảnh phải đọc trước khi viết.** BA v2 §NG-37 chỉ nêu `frappe.desk.search.search_link`.
Đọc `apps/frappe/frappe/desk/search.py:36-72` thì thấy `search_link` chỉ gọi `search_widget`,
và **`search_widget` cũng là `@frappe.whitelist()` trần** — gọi thẳng được từ trình duyệt.
Nó còn nhận `filter_fields`, cho phép người gọi chọn cột trả về; đây đúng là đường lấy
`grand_total` / `outstanding_amount` mà BA v2 mô tả. **Bọc mỗi `search_link` là vá nửa vời.**

Cơ chế rò: `search_widget` gọi `frappe.get_list(..., ignore_permissions=ignore_permissions)`
(`search.py:195-205`), và `ignore_permissions` bật lên khi client truyền
`ignore_user_permissions=1` (`search.py:185-192`). `get_list` với `ignore_permissions=True`
bỏ qua `permission_query_conditions` — tức bỏ qua toàn bộ `miyano_portal/permissions.py`.
Ép cờ đó về `False` là đủ để `permission_query_conditions` sống lại.

Đã kiểm: SPA của cổng **không** gọi `search_link` / `search_widget` ở bất kỳ đâu
(`grep -rn "search_link\|search_widget" frontend/src/` → rỗng). Nên siết chặt cho
Website User không làm hỏng màn nào.

- [ ] **Step 1: Chứng minh lỗ có thật trước khi vá (bước RED bắt buộc)**

Tạo `miyano_portal/tests/test_search_guard.py`:

```python
import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.desk.search import search_widget as frappe_search_widget

from miyano_portal.setup.seed_demo import seed_demo

BVBM = "Bệnh viện Bạch Mai"
KHAC = "PXN ABC"
USER_BVBM = "bvbm@demo.miyano"


def _draft_so(customer: str) -> str:
    """Một Sales Order nháp tối thiểu, đủ để search tìm thấy."""
    item = frappe.get_all("Item", limit=1, pluck="name")[0]
    company = frappe.get_all("Company", limit=1, pluck="name")[0]
    so = frappe.new_doc("Sales Order")
    so.customer = customer
    so.company = company
    so.transaction_date = frappe.utils.today()
    so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 2)
    so.append("items", {
        "item_code": item, "qty": 1, "rate": 1000,
        "delivery_date": so.delivery_date,
    })
    so.flags.ignore_permissions = True
    so.insert(ignore_permissions=True)
    return so.name


class TestSearchGuardLeak(FrappeTestCase):
    """RED: chứng minh lỗ trước khi vá. Test này PHẢI fail trên mã hiện tại."""

    def setUp(self):
        seed_demo()
        self.so_khac = _draft_so(KHAC)
        self.addCleanup(frappe.set_user, "Administrator")

    def test_portal_user_khong_thay_don_cua_khach_khac(self):
        frappe.set_user(USER_BVBM)
        rows = frappe_search_widget(
            doctype="Sales Order",
            txt=self.so_khac,
            ignore_user_permissions=1,
        )
        names = [r[0] for r in rows]
        self.assertNotIn(
            self.so_khac, names,
            "RÒ RỈ: tài khoản cổng của Bạch Mai đọc được đơn của khách khác",
        )
```

- [ ] **Step 2: Chạy để thấy nó FAIL — đây là bằng chứng lỗ có thật**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_search_guard`

Expected: **FAIL** — `AssertionError: RÒ RỈ: tài khoản cổng của Bạch Mai đọc được đơn của khách khác`

Nếu test PASS ở bước này thì **dừng lại**: nghĩa là test chưa chạm tới đường dễ tổn thương, và vá xong sẽ không phân biệt được "vá đúng" với "test không kiểm gì". Kiểm lại `frappe.set_user` đã có hiệu lực chưa (`frappe.session.user`).

- [ ] **Step 3: Viết module chắn**

Tạo `miyano_portal/search_guard.py`:

```python
"""Chắn hai endpoint tìm kiếm của framework trước Website User.

BA v2 §NG-37. `frappe.desk.search.search_link` và `search_widget` đều là
`@frappe.whitelist()` trần: bất kỳ phiên đăng nhập nào không phải Guest đều gọi
được, và khi client tự truyền `ignore_user_permissions=1` thì `search_widget`
chuyển thẳng cờ đó xuống `frappe.get_list(ignore_permissions=...)`, bỏ qua toàn
bộ `permission_query_conditions` của `miyano_portal/permissions.py`. Kết quả:
một tài khoản cổng bất kỳ kéo về được sổ Sales Invoice / Sales Order /
Delivery Note của khách hàng khác, kèm tổng tiền và số còn phải trả.

Chắn CẢ HAI hàm, không chỉ `search_link`: `search_link` chỉ là lớp mỏng gọi
`search_widget`, nên bọc một mình nó để hở nguyên đường gọi thẳng.

Chỉ siết Website User. Nhân viên Miyano ngồi Desk đi thẳng qua bản gốc — đây là
casualty thường gặp nhất của loại sửa này và nó phải không xảy ra.
"""

import frappe
from frappe.desk import search as _frappe_search

# Tám doctype kho: role `Customer` vốn KHÔNG có DocPerm nào trên chúng, nên
# `get_list` sẽ ném PermissionError chứ không trả rỗng. Trả [] tường minh để
# khách không nhận một lỗi tiếng Anh thô từ một ô tìm kiếm.
_TU_CHOI = {
    "Customer Warehouse",
    "Customer Warehouse Item",
    "Customer Stock Receipt",
    "Customer Stock Receipt Item",
    "Customer Stock Issue",
    "Customer Stock Issue Item",
    "Customer Stock Ledger Entry",
    "Customer Stock Lot Balance",
}


def _la_khach_cong(user: str | None = None) -> bool:
    user = user or frappe.session.user
    if user in ("Administrator", "Guest"):
        return False
    return frappe.get_cached_value("User", user, "user_type") == "Website User"


@frappe.whitelist()
def search_link(
    doctype: str,
    txt: str,
    query: str | None = None,
    filters: str | dict | list | None = None,
    page_length: int = 10,
    searchfield: str | None = None,
    reference_doctype: str | None = None,
    ignore_user_permissions: bool = False,
):
    if _la_khach_cong():
        if doctype in _TU_CHOI:
            return []
        try:
            return _frappe_search.search_link(
                doctype,
                txt,
                # `query` cho phép chỉ định một hàm truy vấn tuỳ ý; với khách
                # cổng thì không có nhu cầu nào chính đáng, và mỗi hàm như vậy
                # là một bộ lọc riêng nằm ngoài permission_query_conditions.
                query=None,
                filters=filters,
                page_length=page_length,
                searchfield=searchfield,
                reference_doctype=reference_doctype,
                # ĐÂY là dòng bịt lỗ.
                ignore_user_permissions=False,
            )
        except frappe.PermissionError:
            return []
    return _frappe_search.search_link(
        doctype, txt, query, filters, page_length,
        searchfield, reference_doctype, ignore_user_permissions,
    )


@frappe.whitelist()
def search_widget(
    doctype: str,
    txt: str,
    query: str | None = None,
    searchfield: str | None = None,
    start: int = 0,
    page_length: int = 10,
    filters: str | None | dict | list = None,
    filter_fields=None,
    as_dict: bool = False,
    reference_doctype: str | None = None,
    ignore_user_permissions: bool = False,
):
    if _la_khach_cong():
        if doctype in _TU_CHOI:
            return []
        try:
            return _frappe_search.search_widget(
                doctype,
                txt,
                query=None,
                searchfield=searchfield,
                start=start,
                page_length=page_length,
                filters=filters,
                # `filter_fields` là đường client tự chọn cột trả về — đúng chỗ
                # `grand_total` và `outstanding_amount` lọt ra ngoài trong BA v2.
                filter_fields=None,
                as_dict=as_dict,
                reference_doctype=reference_doctype,
                ignore_user_permissions=False,
            )
        except frappe.PermissionError:
            return []
    return _frappe_search.search_widget(
        doctype, txt, query, searchfield, start, page_length,
        filters, filter_fields, as_dict, reference_doctype,
        ignore_user_permissions,
    )
```

- [ ] **Step 4: Đăng ký override trong hooks**

Sửa `miyano_portal/hooks.py` — thay khối comment ở dòng 279-288 bằng:

```python
# ------------------------------------------------------------------
# Overriding Methods — BA v2 §NG-37
# ------------------------------------------------------------------
# `search_link` và `search_widget` của Frappe nhận `ignore_user_permissions`
# TỪ CLIENT và chuyển thẳng xuống `get_list(ignore_permissions=...)`, bỏ qua
# permission_query_conditions. Phải bọc CẢ HAI: `search_link` chỉ gọi
# `search_widget`, nên bọc một mình nó vẫn hở đường gọi thẳng.
# Xem miyano_portal/search_guard.py.
# ------------------------------------------------------------------
override_whitelisted_methods = {
	"frappe.desk.search.search_link": "miyano_portal.search_guard.search_link",
	"frappe.desk.search.search_widget": "miyano_portal.search_guard.search_widget",
}
```

- [ ] **Step 5: Đổi test RED thành test GREEN và bổ sung ba trường hợp còn lại**

Sửa `miyano_portal/tests/test_search_guard.py` — đổi import và thêm test. Class đổi tên thành `TestSearchGuard`, import từ module chắn:

```python
import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.search_guard import search_link, search_widget
from miyano_portal.setup.seed_demo import seed_demo

BVBM = "Bệnh viện Bạch Mai"
KHAC = "PXN ABC"
USER_BVBM = "bvbm@demo.miyano"


def _draft_so(customer: str) -> str:
    item = frappe.get_all("Item", limit=1, pluck="name")[0]
    company = frappe.get_all("Company", limit=1, pluck="name")[0]
    so = frappe.new_doc("Sales Order")
    so.customer = customer
    so.company = company
    so.transaction_date = frappe.utils.today()
    so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 2)
    so.append("items", {
        "item_code": item, "qty": 1, "rate": 1000,
        "delivery_date": so.delivery_date,
    })
    so.flags.ignore_permissions = True
    so.insert(ignore_permissions=True)
    return so.name


class TestSearchGuard(FrappeTestCase):
    def setUp(self):
        seed_demo()
        self.so_khac = _draft_so(KHAC)
        self.so_minh = _draft_so(BVBM)
        self.addCleanup(frappe.set_user, "Administrator")

    # ---------- chặn được ----------
    def test_search_widget_khong_ro_ri_don_khach_khac(self):
        frappe.set_user(USER_BVBM)
        rows = search_widget("Sales Order", self.so_khac, ignore_user_permissions=1)
        self.assertNotIn(self.so_khac, [r[0] for r in rows])

    def test_search_link_khong_ro_ri_don_khach_khac(self):
        frappe.set_user(USER_BVBM)
        rows = search_link("Sales Order", self.so_khac, ignore_user_permissions=1)
        self.assertNotIn(self.so_khac, [r.get("value") for r in rows])

    def test_filter_fields_khong_keo_duoc_tong_tien(self):
        """filter_fields là đường lấy grand_total / outstanding_amount."""
        frappe.set_user(USER_BVBM)
        rows = search_widget(
            "Sales Order", self.so_khac,
            filter_fields=["name", "grand_total"],
            as_dict=True, ignore_user_permissions=1,
        )
        for r in rows:
            self.assertNotEqual(r.get("name"), self.so_khac)
            self.assertNotIn("grand_total", r)

    def test_doctype_kho_tra_rong_chu_khong_nem_loi(self):
        frappe.set_user(USER_BVBM)
        self.assertEqual(search_widget("Customer Stock Receipt", ""), [])
        self.assertEqual(search_link("Customer Warehouse Item", ""), [])

    # ---------- vẫn thấy phần của mình ----------
    def test_khach_van_thay_don_cua_chinh_minh(self):
        frappe.set_user(USER_BVBM)
        rows = search_widget("Sales Order", self.so_minh)
        self.assertIn(self.so_minh, [r[0] for r in rows])

    # ---------- không chặn nhầm nhân viên Miyano ----------
    def test_desk_user_van_tim_duoc_moi_don(self):
        frappe.set_user("Administrator")
        rows = search_widget("Sales Order", self.so_khac, ignore_user_permissions=1)
        self.assertIn(self.so_khac, [r[0] for r in rows])

    # ---------- override thật sự được đăng ký ----------
    def test_hooks_da_dang_ky_ca_hai_endpoint(self):
        h = frappe.get_hooks("override_whitelisted_methods") or {}
        self.assertEqual(
            h.get("frappe.desk.search.search_link"),
            ["miyano_portal.search_guard.search_link"],
        )
        self.assertEqual(
            h.get("frappe.desk.search.search_widget"),
            ["miyano_portal.search_guard.search_widget"],
        )
```

- [ ] **Step 6: Xoá cache hook rồi chạy test**

Run:
```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local clear-cache
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_search_guard
```
Expected: **7 tests PASS**.

- [ ] **Step 7: Chạy lại bộ cách ly cũ để chắc không chặn nhầm**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_isolation`
Expected: PASS, không regression.

- [ ] **Step 8: Quét toàn bộ 38 endpoint whitelist còn lại**

Lỗ này thuộc họ "mỗi lỗ độc lập, vá một cái không lộ ra cái sau". Quét cho hết trong cùng task, đừng để lần sau:

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal
grep -rn "@frappe.whitelist" --include=*.py . | wc -l   # kỳ vọng 40 sau task này
grep -rn "@frappe.whitelist" -A3 --include=*.py miyano_portal/
```

Với **mỗi** hàm, trả lời hai câu: *(a)* gọi được từ phiên cổng không? *(b)* nó có kiểm gì ngoài quyền doctype không? Nếu (a) có và (b) không → ghi vào phần "Phát hiện" của mục sổ theo dõi, **không** sửa trong task này (ngoài phạm vi NG-37) mà mở mục mới trong bảng tiến độ.

Ghi kết quả quét — kể cả khi không tìm thấy gì thêm — vào mục sổ theo dõi ở Step 9.

- [ ] **Step 9: Ghi sổ theo dõi + commit**

Thêm vào §4 của `docs/CHANGELOG-khac-phuc-BA-v2.md`:

```markdown
### NG-37 · Rò rỉ sổ hoá đơn giữa các khách hàng — 2026-08-12 · commit <sha>
**Trước:** `frappe.desk.search.search_link` và `search_widget` nhận `ignore_user_permissions` từ client và chuyển thẳng xuống `get_list(ignore_permissions=True)`, bỏ qua toàn bộ `permission_query_conditions`. Một tài khoản cổng bất kỳ đọc được `Sales Order` / `Delivery Note` / `Sales Invoice` của khách khác, kèm `grand_total` và `outstanding_amount` qua `filter_fields`.
**Sau:** Cả hai endpoint được bọc qua `override_whitelisted_methods`. Với Website User: ép `ignore_user_permissions=False`, bỏ `query`, bỏ `filter_fields`, trả `[]` cho 8 doctype kho, nuốt `PermissionError` thành `[]`. Desk user đi thẳng qua bản gốc, không đổi hành vi.
**Đụng vào:** `miyano_portal/search_guard.py` (mới) · `miyano_portal/hooks.py:279-288` (mở khối `override_whitelisted_methods`)
**Phá vỡ:** Không. SPA không gọi hai endpoint này (đã grep). Desk không đổi.
**Test:** `miyano_portal/tests/test_search_guard.py` — 7 test, gồm một test RED đã chứng minh lỗ trước khi vá, một test assert Desk user không bị chặn, một test assert hooks đăng ký đủ cả hai.
**Cảnh báo chồng lấn:** `override_whitelisted_methods` từ nay **đã mở**. Ai thêm override sau này thì thêm khoá vào cùng dict, đừng khai lại biến.
**Phát hiện thêm khi quét 38 endpoint:** <ghi kết quả Step 8 vào đây>
```

Cập nhật bảng tiến độ §1: `NG-37` → ✅.

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal
git add miyano_portal/search_guard.py miyano_portal/hooks.py \
        miyano_portal/tests/test_search_guard.py \
        docs/CHANGELOG-khac-phuc-BA-v2.md
git commit -m "fix(portal): bịt rò rỉ sổ chứng từ giữa các khách hàng qua search_link/search_widget (NG-37)"
```

---

## Task 1b: NG-37b — rò rỉ dòng hàng qua `frappe.client` trên doctype con

> **Task này không có trong bản plan gốc.** Nó được thêm ngày 2026-08-12 sau khi
> reviewer của Task 1 chứng minh bằng probe thật trên site rằng còn một lỗ nữa, cùng họ
> với NG-37 nhưng BA v2 không nêu. Human đã duyệt đưa vào đợt 1.

**Files:**
- Modify: `miyano_portal/search_guard.py` (thêm hai wrapper), hoặc tách `miyano_portal/client_guard.py` nếu file đầu đã dài
- Modify: `miyano_portal/hooks.py` (thêm khoá vào `override_whitelisted_methods` **đã mở sẵn** ở Task 1)
- Test: `miyano_portal/tests/test_search_guard.py` (mở rộng) hoặc module mới

**Interfaces:**
- Consumes: `search_guard._la_khach_cong()` (Task 1) — **dùng lại**, đừng viết bản thứ hai
- Produces: wrapper cho `frappe.client.get_list` và `frappe.client.get`

**Lỗ, đã chứng minh trên site.** Với phiên `bvbm@demo.miyano`:

```python
frappe.client.get_list("Sales Order Item",
    fields=["parent", "item_code", "rate", "amount"], parent="Sales Order")
```

trả về dòng hàng — kèm **`rate` và `amount`** — của **năm** khách hàng khác nhau
(Bạch Mai · Minh Đức · Hùng Vương · Miyano · Himedic), trong khi cùng phiên đó
`frappe.get_list("Sales Order")` ở tầng cha lọc đúng, chỉ ra Bạch Mai.

**Cơ chế, ba mảnh ghép lại:**
1. `db_query.py:1305-1317` — `check_parent_permission("Sales Order", …)` chỉ hỏi
   `has_permission("Sales Order")` **không kèm doc**, nên nó chỉ kiểm quyền ở mức doctype
   và bỏ qua hoàn toàn việc đơn đó thuộc khách nào.
2. `hooks.py:131-155` — `Sales Order Item` / `Delivery Note Item` / `Sales Invoice Item`
   **không có** entry trong `permission_query_conditions`. Hook phân giải theo **doctype
   đang được truy vấn**, không đi ngược lên cha.
3. `db_query.py:1004-1008` — `istable` cắt nhánh shared-only trước khi tới chỗ có thể cứu.

Khớp với điều đã ghi trong `frappe-v15-gotchas`: hook `has_permission` **không bao giờ
chạy** cho doctype `istable`, vì `has_child_permission()` rẽ nhánh sang kiểm cha trước.
Nghĩa là **đăng ký `has_permission` cho doctype con là một chốt chặn giả** — đừng làm.

**Tiền lệ trên chính bench này.** `supplycore/supplycore/hooks.py:170-175` đã bọc
`frappe.client.get` đúng vì lý do này; comment của nó nêu đích danh SO Item / DN Item /
SI Item. **Đọc nó trước khi viết** — dùng lại hình dạng đã được review ở đó thay vì
phát minh lại.

- [ ] **Step 1: RED — chứng minh lỗ trước khi vá**

Viết test dựng hai khách hàng, mỗi khách một Sales Order nháp có dòng hàng mang `rate`
khác nhau; đăng nhập khách A; gọi `frappe.client.get_list("Sales Order Item",
fields=["parent","item_code","rate","amount"], parent="Sales Order")`; assert **không**
thấy `parent` của khách B. Chạy và xác nhận **FAIL**.

Lặp cho `Delivery Note Item` và `Sales Invoice Item` nếu seed có dữ liệu; nếu không thì
ghi rõ trong report là chưa dựng lại được và chỉ suy ra từ cùng cơ chế.

Cũng viết một test cho `frappe.client.get` — nó nạp **một** dòng con theo tên hoặc theo
`filters`, và `parent_doc` phân giải thành `None` nên rơi về kiểm mức doctype. Đây là
đường thứ hai, không phải cùng một đường với `get_list`.

- [ ] **Step 2: Chạy để thấy FAIL.** Nếu PASS thì **dừng và báo** — test chưa chạm đường dễ tổn thương.

- [ ] **Step 3: Viết wrapper**

Nguyên tắc: **chặn thẳng, đừng lọc.** Cổng không có màn nào cần đọc dòng con qua
`frappe.client` (SPA dùng endpoint riêng — grep để xác nhận trước khi tin). Nên với
Website User, mọi lời gọi hai hàm này trên ba doctype con → ném `frappe.PermissionError`
với thông điệp tiếng Việt, hoặc trả rỗng với `get_list`. Với mọi người khác → uỷ quyền
nguyên trạng cho bản gốc.

**Deny-list role cổng trên endpoint nội bộ, đừng allow-list từng hàm** — cách đó khiến
một endpoint mới mặc định bị **chặn** thay vì mặc định **mở**.

Chữ ký phải khớp bản gốc của Frappe từng tham số một; `execute_cmd` lọc kwargs theo chữ
ký, nên một tham số lệch là một đường đi vòng.

- [ ] **Step 4: Đăng ký trong hooks**

Thêm vào dict `override_whitelisted_methods` **đã có sẵn** từ Task 1 — đừng khai lại biến:
```python
	"frappe.client.get_list": "miyano_portal.search_guard.client_get_list",
	"frappe.client.get": "miyano_portal.search_guard.client_get",
```

- [ ] **Step 5: `clear-cache` rồi chạy test** — RED phải chuyển GREEN.

- [ ] **Step 6: Kiểm không chặn nhầm Desk**

`sales_user@demo.miyano` (System User thật, **không** dùng Administrator — Administrator
đi tắt trước cả bước kiểm `user_type` nên test bằng nó không chứng minh gì) phải vẫn
`frappe.client.get_list("Sales Order Item", …)` được bình thường.

Chạy lại `test_search_guard`, `test_isolation`, `test_portal_read`, `test_kho_isolation`.

- [ ] **Step 7: Quét nốt họ này**

`frappe.client` còn `get_value`, `get_single_value`, `set_value`, `insert`, `delete`,
`submit`. Với **mỗi** hàm, trả lời: gọi được từ phiên cổng không? có kiểm gì ngoài quyền
doctype không? Chú ý riêng các hàm **ghi** — không phải rò rỉ mà là leo thang quyền, tệ
hơn. Ghi kết quả vào sổ theo dõi; **không** sửa cái ngoài phạm vi, mở mã số mới thay vì
lặng lẽ mở rộng task.

`get_list` và `get_value` được cho là có đi qua `permission_query_conditions` — **xác minh
điều đó bằng probe**, đừng tin lời.

- [ ] **Step 8: Ghi sổ theo dõi + commit**

Mục sổ theo dõi phải nói rõ đây là **NG-37b, mã mới, không có trong BA v2**, và ghi lại
kết quả quét Step 7. Cập nhật dòng tracker mà Task 1 đã thêm.

```bash
git commit -m "fix(portal): chặn rò rỉ dòng hàng qua frappe.client trên doctype con (NG-37b)"
```

---

## Task 2: NG-12 — precision 0 cho tiền VND và làm tròn dữ liệu đã có

**Files:**
- Modify: `miyano_portal/miyano_portal/doctype/customer_stock_receipt/customer_stock_receipt.json` (`tong_tien`)
- Modify: `.../customer_stock_receipt_item/customer_stock_receipt_item.json` (`don_gia`, `thanh_tien`)
- Modify: `.../customer_stock_issue/customer_stock_issue.json` (`tong_tien`)
- Modify: `.../customer_stock_issue_item/customer_stock_issue_item.json` (`don_gia`, `thanh_tien`)
- Modify: `.../customer_stock_ledger_entry/customer_stock_ledger_entry.json` (`don_gia`, `gia_tri`)
- Modify: `.../customer_stock_lot_balance/customer_stock_lot_balance.json` (`don_gia`, `gia_tri`)
- Modify: `miyano_portal/kho/voucher.py`, `miyano_portal/kho/ledger.py`
- Create: `miyano_portal/patches/v1_3/__init__.py`, `miyano_portal/patches/v1_3/round_kho_currency.py`
- Modify: `miyano_portal/patches.txt`
- Test: `miyano_portal/tests/test_kho_precision.py`

**Interfaces:**
- Produces: `miyano_portal.kho.ledger.lam_tron_tien(x) -> float` — hàm làm tròn tiền dùng chung, 0 chữ số thập phân. Task 3 và 4 dùng lại chính hàm này; đừng viết bản thứ hai.

**Đính chính phạm vi so với BA v2.** Tài liệu ghi *"10 trường Currency của 8 doctype kho"*.
Đúng **10 trường**, nhưng trên **6** doctype — `Customer Warehouse` và `Customer Warehouse Item`
không có trường Currency nào. Không đổi khối lượng công việc.

**Nguyên tắc bắt buộc: làm tròn TẠI THỜI ĐIỂM TÍNH, TRƯỚC KHI CỘNG DỒN.**
Chỉ đặt `precision: "0"` là chưa đủ và còn nguy hiểm hơn hiện trạng: framework sẽ làm tròn
**từng trường độc lập lúc ghi**, trong khi `tong_tien` đã được tính từ float thô trước đó —
tổng đầu phiếu sẽ lệch khỏi tổng các dòng đúng bằng phần dư. Phải sửa cả chỗ tính.

- [ ] **Step 1: Viết test thất bại, dùng một ca cố tình xấu**

Tạo `miyano_portal/tests/test_kho_precision.py`:

```python
import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.setup.seed_demo import seed_demo


class TestKhoPrecision(FrappeTestCase):
    """Ca cố tình xấu: số lượng lẻ + đơn giá lẻ. Với số nguyên thì bug vô hình."""

    def setUp(self):
        seed_demo()
        from miyano_portal.tests.helpers_kho import tao_kho_va_vat_tu  # có sẵn
        self.kho, self.vat_tu = tao_kho_va_vat_tu()

    def _phieu_nhap_le(self):
        p = frappe.new_doc("Customer Stock Receipt")
        p.kho = self.kho
        p.ngay = frappe.utils.today()
        p.loai_nhap = "Nhập mua"
        # 7.5 × 133_333 = 999_997.5 — không rơi vào số nguyên
        p.append("items", {
            "vat_tu": self.vat_tu, "so_lo": "KHONG-LO",
            "so_luong": 7.5, "don_gia": 133333,
        })
        # 3.333 × 66_666 = 222_197.778
        p.append("items", {
            "vat_tu": self.vat_tu, "so_lo": "LO-B",
            "so_luong": 3.333, "don_gia": 66666,
        })
        p.flags.ignore_permissions = True
        p.insert(ignore_permissions=True)
        p.submit()
        return p.name

    def test_tong_dau_phieu_bang_tong_cac_dong(self):
        name = self._phieu_nhap_le()
        # Đọc LẠI TỪ CSDL — giá trị trong bộ nhớ vẫn mang float thô và sẽ
        # pass một test mà production fail.
        doc = frappe.get_doc("Customer Stock Receipt", name)
        tong_dong = sum(r.thanh_tien for r in doc.items)
        self.assertEqual(doc.tong_tien, tong_dong)

    def test_moi_truong_tien_deu_la_so_nguyen(self):
        name = self._phieu_nhap_le()
        doc = frappe.get_doc("Customer Stock Receipt", name)
        self.assertEqual(doc.tong_tien, int(doc.tong_tien))
        for r in doc.items:
            self.assertEqual(r.don_gia, int(r.don_gia))
            self.assertEqual(r.thanh_tien, int(r.thanh_tien))

    def test_so_kho_khop_voi_dong_phieu(self):
        name = self._phieu_nhap_le()
        doc = frappe.get_doc("Customer Stock Receipt", name)
        sle = frappe.get_all(
            "Customer Stock Ledger Entry",
            filters={"chung_tu": name},
            fields=["gia_tri", "don_gia"],
        )
        self.assertEqual(
            sum(r.gia_tri for r in sle),
            sum(r.thanh_tien for r in doc.items),
        )
        for r in sle:
            self.assertEqual(r.gia_tri, int(r.gia_tri))

    def test_ton_theo_lo_khop_voi_so(self):
        self._phieu_nhap_le()
        for lo in frappe.get_all(
            "Customer Stock Lot Balance",
            filters={"kho": self.kho}, fields=["name", "gia_tri", "so_lo", "vat_tu"],
        ):
            tong_so = frappe.db.sql(
                """select sum(gia_tri) from `tabCustomer Stock Ledger Entry`
                   where kho=%s and vat_tu=%s and so_lo=%s and da_dao=0""",
                (self.kho, lo.vat_tu, lo.so_lo),
            )[0][0] or 0
            self.assertEqual(lo.gia_tri, tong_so)
```

> Nếu `miyano_portal/tests/helpers_kho.py` chưa tồn tại, tạo nó bằng cách tách hàm dựng kho + vật tư đang lặp trong `test_kho_receipt.py` ra — đừng viết bản sao thứ ba.

- [ ] **Step 2: Chạy để thấy FAIL**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_precision`
Expected: FAIL — `tong_tien` lệch khỏi tổng dòng và/hoặc các trường mang phần thập phân.

- [ ] **Step 3: Đặt `precision: "0"` cho đúng 10 trường**

Trong mỗi file JSON, tìm khối của trường và thêm `"precision": "0"`. Ví dụ với `customer_stock_receipt_item.json`:

```json
{
 "fieldname": "don_gia",
 "fieldtype": "Currency",
 "label": "Đơn giá",
 "precision": "0"
},
{
 "fieldname": "thanh_tien",
 "fieldtype": "Currency",
 "label": "Thành tiền",
 "read_only": 1,
 "precision": "0"
}
```

Làm y hệt cho: `customer_stock_receipt.tong_tien` · `customer_stock_issue.tong_tien` ·
`customer_stock_issue_item.don_gia` · `customer_stock_issue_item.thanh_tien` ·
`customer_stock_ledger_entry.don_gia` · `customer_stock_ledger_entry.gia_tri` ·
`customer_stock_lot_balance.don_gia` · `customer_stock_lot_balance.gia_tri`.

**Không** đụng `so_luong` (`precision: "3"` là đúng — số lượng có phần lẻ thật).

Kiểm lại đã đủ 10:
```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal/miyano_portal/miyano_portal/doctype
grep -rl '"fieldtype": "Currency"' . | xargs grep -c '"precision": "0"' | sort
```
Expected: tổng cộng 10.

- [ ] **Step 4: Làm tròn trước khi cộng dồn, ở chỗ tính**

Thêm vào đầu `miyano_portal/kho/ledger.py`:

```python
def lam_tron_tien(x) -> float:
    """Làm tròn tiền VND về số nguyên. MỘT hàm duy nhất cho toàn app.

    VND không có phần thập phân. Quan trọng hơn việc định dạng: mọi con số
    tiền phải được làm tròn TẠI CHỖ TÍNH rồi mới cộng dồn. Nếu để `tong_tien`
    dẫn xuất từ float thô trong khi từng `thanh_tien` bị framework làm tròn
    lúc ghi, thì tổng đầu phiếu sẽ lệch khỏi tổng các dòng — và sổ kho lệch
    khỏi phiếu.
    """
    return float(round(flt(x)))
```
(thêm `from frappe.utils import flt` nếu chưa có)

Trong `miyano_portal/kho/voucher.py`, ở chỗ tính `thanh_tien` / `tong_tien`, đổi thành:

```python
from miyano_portal.kho.ledger import lam_tron_tien

def _tinh_tien(self):
    tong = 0.0
    for row in self.items:
        row.don_gia = lam_tron_tien(row.don_gia)
        # Làm tròn TỪNG dòng TRƯỚC, rồi mới cộng — không cộng float thô rồi
        # làm tròn ở cuối (chỉ dời chỗ lệch từ header-vs-total sang
        # lines-vs-header).
        row.thanh_tien = lam_tron_tien(flt(row.so_luong) * flt(row.don_gia))
        tong += row.thanh_tien
    # `tong` giờ là tổng của các số nguyên — không thể trôi.
    self.tong_tien = tong
```

Trong `miyano_portal/kho/ledger.py::post_lines`, làm y hệt với `don_gia` và `gia_tri`:

```python
don_gia = lam_tron_tien(line["don_gia"])
gia_tri = lam_tron_tien(flt(line["so_luong"]) * don_gia)
```

Và trong `_apply_to_balance`, `gia_tri` của lô cộng dồn từ các `gia_tri` **đã làm tròn**, không tính lại từ `so_luong × don_gia` của lô.

- [ ] **Step 5: Migrate rồi chạy test**

Run:
```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_precision
```
Expected: **4 tests PASS**.

- [ ] **Step 6: Patch làm tròn dữ liệu đã có — đúng thứ tự**

Tạo `miyano_portal/patches/v1_3/__init__.py` (rỗng) và `miyano_portal/patches/v1_3/round_kho_currency.py`:

```python
"""Làm tròn về số nguyên toàn bộ tiền đã ghi trong sổ kho — BA v2 §NG-12.

THỨ TỰ LÀ BẮT BUỘC và không đảo được:

  1. don_gia  → làm tròn
  2. thanh_tien / gia_tri = so_luong × don_gia ĐÃ LÀM TRÒN  (không làm tròn
     riêng giá trị cũ: nó được sinh từ đơn giá cũ có phần lẻ, làm tròn nó sẽ
     ra một số không khớp với đơn giá mới)
  3. tong_tien = tổng các thanh_tien đã làm tròn
  4. dựng lại `Customer Stock Lot Balance` từ sổ

Dựng lại cache (4) TRƯỚC khi làm tròn (1-3) sẽ khôi phục lại đúng những con số
cũ — cache dẫn xuất từ sổ, nên sổ phải đúng trước.

Tiền lệ đi theo: `miyano_portal.patches.v1_2.repair_kho_ledger_replay`.
Patch này idempotent: chạy lần hai trên dữ liệu đã tròn là no-op.
"""

import frappe

from miyano_portal.kho.ledger import rebuild_lot_balance


def execute():
    # 1 + 2: bảng dòng của hai loại phiếu
    for child in ("Customer Stock Receipt Item", "Customer Stock Issue Item"):
        frappe.db.sql(f"update `tab{child}` set don_gia = round(don_gia, 0)")
        frappe.db.sql(
            f"update `tab{child}` set thanh_tien = round(so_luong * don_gia, 0)"
        )

    # 3: tổng đầu phiếu = tổng các dòng đã làm tròn
    for parent, child in (
        ("Customer Stock Receipt", "Customer Stock Receipt Item"),
        ("Customer Stock Issue", "Customer Stock Issue Item"),
    ):
        frappe.db.sql(
            f"""update `tab{parent}` p
                set p.tong_tien = ifnull(
                    (select sum(c.thanh_tien) from `tab{child}` c
                     where c.parent = p.name), 0)"""
        )

    # 1 + 2 cho sổ (append-only: sửa tại chỗ, không sinh bút toán mới — đây là
    # sửa đơn vị đo của con số, không phải sửa nghiệp vụ)
    frappe.db.sql(
        "update `tabCustomer Stock Ledger Entry` set don_gia = round(don_gia, 0)"
    )
    frappe.db.sql(
        """update `tabCustomer Stock Ledger Entry`
           set gia_tri = round(so_luong * don_gia, 0)"""
    )

    # 4: dựng lại cache tồn theo lô TỪ sổ đã đúng
    rebuild_lot_balance()

    frappe.db.commit()
```

Thêm vào cuối `miyano_portal/patches.txt`, khối `[post_model_sync]`:
```
miyano_portal.patches.v1_3.round_kho_currency
```

- [ ] **Step 7: Test cho patch — chạy hai lần phải cho cùng kết quả**

Thêm vào `miyano_portal/tests/test_kho_precision.py`:

```python
    def test_patch_lam_tron_du_lieu_cu_va_idempotent(self):
        from miyano_portal.patches.v1_3.round_kho_currency import execute

        name = self._phieu_nhap_le()
        # Giả lập dữ liệu cũ: nhét lại phần lẻ vào CSDL, bỏ qua tầng document
        frappe.db.sql(
            """update `tabCustomer Stock Receipt Item`
               set don_gia = 133333.47, thanh_tien = 999999.99
               where parent = %s limit 1""",
            name,
        )
        execute()
        doc = frappe.get_doc("Customer Stock Receipt", name)
        for r in doc.items:
            self.assertEqual(r.don_gia, int(r.don_gia))
            self.assertEqual(r.thanh_tien, int(r.thanh_tien))
        self.assertEqual(doc.tong_tien, sum(r.thanh_tien for r in doc.items))

        lan_1 = doc.tong_tien
        execute()  # chạy lần hai
        self.assertEqual(
            frappe.db.get_value("Customer Stock Receipt", name, "tong_tien"),
            lan_1,
            "patch không idempotent — chạy lần hai đổi số",
        )
```

- [ ] **Step 8: Chạy patch thật trên site rồi chạy toàn bộ bộ test kho**

Run:
```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_precision
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_ledger
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_receipt
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_issue
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_reports
```
Expected: tất cả PASS. Nếu `test_kho_reports` fail vì con số kỳ vọng có phần lẻ — đó là test đang khoá lại hành vi sai; sửa số kỳ vọng thành số nguyên và ghi vào mục sổ theo dõi.

- [ ] **Step 9: Ghi sổ theo dõi + commit**

Thêm vào §4 của `docs/CHANGELOG-khac-phuc-BA-v2.md`:

```markdown
### NG-12 · Trường tiền chưa đặt precision 0 — 2026-08-12 · commit <sha>
**Trước:** 10 trường Currency của sổ kho đều `precision = None` (mặc định 2 chữ số). Đơn giá lô mang phần lẻ → thành tiền từng dòng làm tròn khác nhau → tổng đầu phiếu ≠ tổng các dòng; giá trị tồn trong bảng cache lệch dần khỏi sổ.
**Sau:** `precision: "0"` cho đúng 10 trường / 6 doctype. Quan trọng hơn: tiền được làm tròn **tại chỗ tính, trước khi cộng dồn** — `lam_tron_tien()` trong `kho/ledger.py` là hàm duy nhất, `voucher.py::_tinh_tien` và `ledger.py::post_lines` đều gọi nó. `tong_tien` giờ là tổng của các số nguyên nên không thể trôi.
**Đụng vào:** 6 file JSON doctype (10 trường) · `kho/ledger.py` (thêm `lam_tron_tien`, sửa `post_lines`, `_apply_to_balance`) · `kho/voucher.py::_tinh_tien` · `patches/v1_3/round_kho_currency.py` (mới) · `patches.txt`
**Phá vỡ:** Dữ liệu tiền đã ghi trên site bị làm tròn (patch `v1_3.round_kho_currency`, idempotent, dựng lại cache tồn sau khi làm tròn sổ). Test cũ nào kỳ vọng số có phần lẻ phải sửa số kỳ vọng.
**Test:** `miyano_portal/tests/test_kho_precision.py` — 5 test, dùng ca cố tình xấu (7.5 × 133 333). Assert đọc **lại từ CSDL**, không phải từ document trong bộ nhớ.
**Cảnh báo chồng lấn:** Task 3 và 4 (giá bán, VAT) **phải** dùng lại `lam_tron_tien` chứ không viết hàm làm tròn thứ hai. Trường tiền của `Sales Order` / `Sales Invoice` **cố ý không** đổi — ngoài phạm vi, cần bàn với kế toán.
```

Cập nhật bảng tiến độ §1: `NG-12` → ✅.

```bash
git add miyano_portal/miyano_portal/doctype miyano_portal/kho/ledger.py \
        miyano_portal/kho/voucher.py miyano_portal/patches \
        miyano_portal/tests/test_kho_precision.py \
        docs/CHANGELOG-khac-phuc-BA-v2.md
git commit -m "fix(kho): tiền VND precision 0, làm tròn trước khi cộng dồn, patch dữ liệu cũ (NG-12)"
```

---

## Task 3: NG-10 + NG-11 — một hàm đọc giá duy nhất, lọc ngày và xác định

**Files:**
- Create: `miyano_portal/portal_pricing.py`
- Modify: `miyano_portal/api/portal.py:170-175` (trong `portal_catalog`), `:254-259` (trong `portal_order_place`)
- Test: `miyano_portal/tests/test_portal_pricing.py`

**Interfaces:**
- Produces: `miyano_portal.portal_pricing.gia_ban(item_code: str, price_list: str, ngay: str | None = None) -> float | None` — trả `None` khi không có giá hiệu lực, **không** ném lỗi (người gọi quyết định thông điệp).

**Vì sao gộp hai mã số.** NG-10 (không lọc ngày hiệu lực) và NG-11 (không `order_by` nên
lấy tuỳ ý) nằm trên **cùng hai lời gọi `frappe.db.get_value`** ở hai chỗ trong
`api/portal.py`. Sửa riêng nghĩa là mở cùng hai chỗ hai lần. Và chúng cộng hưởng: sửa giá
bằng cách thêm bản ghi mới (cách làm phổ biến) khiến cổng báo giá cũ hay giá mới **một
cách ngẫu nhiên**. Đây cũng là lý do phải làm Task 3 **trước** NG-08: một báo giá chốt
dựng trên hàm đọc giá không xác định thì chốt cái gì.

Hiện có **hai bản sao** của cùng câu truy vấn, một trong `portal_catalog` một trong
`portal_order_place` — và chúng đã lệch nhau: bản trong catalog có `or row["rate"]`
(lùi về giá hợp đồng), bản trong order_place thì `frappe.throw`. Task này gộp về một.

- [ ] **Step 1: Viết test thất bại**

Tạo `miyano_portal/tests/test_portal_pricing.py`:

```python
import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.portal_pricing import gia_ban
from miyano_portal.setup.seed_demo import seed_demo

PRICE_LIST = "Bảng giá Miyano"  # khớp seed_demo.PRICE_LIST


def _gia(item_code, rate, valid_from=None, valid_upto=None):
    d = frappe.get_doc({
        "doctype": "Item Price",
        "item_code": item_code,
        "price_list": PRICE_LIST,
        "selling": 1,
        "price_list_rate": rate,
        "currency": "VND",
        "valid_from": valid_from,
        "valid_upto": valid_upto,
    })
    d.insert(ignore_permissions=True)
    return d.name


class TestGiaBan(FrappeTestCase):
    def setUp(self):
        seed_demo()
        self.item = frappe.get_all("Item", limit=1, pluck="name")[0]
        frappe.db.delete("Item Price", {"item_code": self.item, "price_list": PRICE_LIST})
        self.hom_nay = frappe.utils.today()

    # ---------- NG-10: lọc ngày hiệu lực ----------
    def test_bo_qua_gia_da_het_hieu_luc(self):
        _gia(self.item, 50000,
             valid_from=frappe.utils.add_days(self.hom_nay, -60),
             valid_upto=frappe.utils.add_days(self.hom_nay, -30))
        self.assertIsNone(gia_ban(self.item, PRICE_LIST))

    def test_bo_qua_gia_chua_toi_ngay_hieu_luc(self):
        _gia(self.item, 50000, valid_from=frappe.utils.add_days(self.hom_nay, 30))
        self.assertIsNone(gia_ban(self.item, PRICE_LIST))

    def test_gia_khong_khai_ngay_van_dung_duoc(self):
        """valid_from/valid_upto rỗng = luôn hiệu lực. Đây là phần lớn dữ liệu
        hiện có, nên lọc ngày mà quét sạch chúng là làm hỏng cổng."""
        _gia(self.item, 78000)
        self.assertEqual(gia_ban(self.item, PRICE_LIST), 78000)

    # ---------- NG-11: xác định, không tuỳ ý ----------
    def test_nhieu_ban_ghi_lay_ban_hieu_luc_moi_nhat(self):
        _gia(self.item, 70000, valid_from=frappe.utils.add_days(self.hom_nay, -30))
        _gia(self.item, 78000, valid_from=frappe.utils.add_days(self.hom_nay, -1))
        for _ in range(5):  # gọi nhiều lần: kết quả phải luôn như nhau
            self.assertEqual(gia_ban(self.item, PRICE_LIST), 78000)

    def test_hai_ban_ghi_cung_ngay_van_xac_dinh(self):
        a = _gia(self.item, 70000, valid_from=self.hom_nay)
        b = _gia(self.item, 78000, valid_from=self.hom_nay)
        # b sửa sau a → thắng. Không phụ thuộc thứ tự CSDL trả về.
        self.assertEqual(gia_ban(self.item, PRICE_LIST), 78000)
        self.assertTrue(a and b)

    # ---------- tiền VND ----------
    def test_gia_tra_ve_la_so_nguyen(self):
        _gia(self.item, 78000.6)
        self.assertEqual(gia_ban(self.item, PRICE_LIST), 78001)

    # ---------- không có giá ----------
    def test_khong_co_gia_tra_none_chu_khong_nem_loi(self):
        self.assertIsNone(gia_ban(self.item, PRICE_LIST))
```

- [ ] **Step 2: Chạy để thấy FAIL**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_portal_pricing`
Expected: FAIL — `ModuleNotFoundError: No module named 'miyano_portal.portal_pricing'`

- [ ] **Step 3: Viết module**

Tạo `miyano_portal/portal_pricing.py`:

```python
"""Đọc giá bán và tính thuế cho cổng khách hàng.

MỘT chỗ duy nhất. Trước đây cùng một câu truy vấn `Item Price` được viết hai
lần — một trong `portal_catalog`, một trong `portal_order_place` — và hai bản
đã lệch nhau về cách xử lý khi không có giá. Hai bản sao của một quy tắc giá là
đúng thứ sinh ra NG-08 (số tiền khách xác nhận không khớp đơn hàng).
"""

import frappe
from frappe.utils import flt, getdate

from miyano_portal.kho.ledger import lam_tron_tien


def gia_ban(item_code: str, price_list: str, ngay: str | None = None) -> float | None:
    """Đơn giá bán hiệu lực tại `ngay` (mặc định hôm nay), hoặc None.

    Hai lỗi cũ được sửa ở đây, đọc cùng nhau vì chúng cộng hưởng:

    NG-10 — bản cũ không lọc `valid_from` / `valid_upto`, nên một mức giá đã
    hết hiệu lực vẫn được báo cho khách và dùng để tạo đơn.

    NG-11 — bản cũ không có `order_by`, nên khi có nhiều `Item Price` thoả điều
    kiện thì bản ghi nào được trả về là KHÔNG XÁC ĐỊNH. Cộng với NG-10: sửa giá
    bằng cách thêm bản ghi mới (cách làm phổ biến) khiến cổng báo giá cũ hay giá
    mới một cách ngẫu nhiên, giữa hai lần tải trang.

    `valid_from` / `valid_upto` rỗng nghĩa là LUÔN hiệu lực — phần lớn dữ liệu
    hiện có không khai ngày, nên lọc mà quét sạch chúng sẽ làm trắng danh mục.

    Sắp xếp `valid_from desc, modified desc`: bản hiệu lực muộn nhất thắng; khi
    hai bản cùng ngày hiệu lực thì bản sửa sau thắng. Xác định trong mọi trường
    hợp, không phụ thuộc thứ tự CSDL trả về.
    """
    ngay = getdate(ngay or frappe.utils.today())
    rows = frappe.get_all(
        "Item Price",
        filters=[
            ["item_code", "=", item_code],
            ["price_list", "=", price_list],
            ["selling", "=", 1],
        ],
        or_filters=None,
        fields=["price_list_rate", "valid_from", "valid_upto"],
        order_by="valid_from desc, modified desc",
    )
    for r in rows:
        if r.valid_from and getdate(r.valid_from) > ngay:
            continue
        if r.valid_upto and getdate(r.valid_upto) < ngay:
            continue
        return lam_tron_tien(r.price_list_rate)
    return None
```

> Lọc ngày làm bằng Python chứ không bằng SQL là **có chủ ý**: trình dựng truy vấn
> của Frappe bọc điều kiện so sánh trong `ifnull()` theo cách khiến bản ghi có ngày
> rỗng lọt qua bộ lọc `<=` — đúng cơ chế đã sinh ra NG-28 ở báo cáo hạn dùng
> (`kho/reports.py:355-363`). Đừng "tối ưu" đoạn này thành `filters` SQL.

- [ ] **Step 4: Chạy test — PASS**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_portal_pricing`
Expected: **7 tests PASS**.

- [ ] **Step 5: Thay hai bản sao cũ trong `api/portal.py`**

Thêm import ở đầu file: `from miyano_portal.portal_pricing import gia_ban`

Trong `portal_catalog` (khoảng dòng 170-175), thay:
```python
        rate = frappe.db.get_value(
            "Item Price",
            {"item_code": row["item_code"], "price_list": price_list, "selling": 1},
            "price_list_rate",
        ) or row["rate"]
```
bằng:
```python
        # Không có Item Price hiệu lực thì lùi về đơn giá đã ký trên hợp đồng.
        rate = gia_ban(row["item_code"], price_list)
        if rate is None:
            rate = lam_tron_tien(row["rate"])
```
(thêm `from miyano_portal.kho.ledger import lam_tron_tien` vào import)

Trong `portal_order_place` (khoảng dòng 254-259), thay:
```python
        rate = frappe.db.get_value(
            "Item Price",
            {"item_code": item_code, "price_list": price_list, "selling": 1},
            "price_list_rate",
        )
        if not rate:
            frappe.throw(f"Không tìm thấy giá bán cho mặt hàng {item_code}.")
```
bằng:
```python
        rate = gia_ban(item_code, price_list)
        if rate is None:
            frappe.throw(
                f"Không tìm thấy giá bán còn hiệu lực cho mặt hàng {item_code}. "
                "Vui lòng liên hệ nhân viên kinh doanh Miyano."
            )
```

> Hai nhánh **cố ý khác nhau** và đây là chủ ý, không phải sót: danh mục lùi về giá
> hợp đồng để khách vẫn xem được hàng; đặt hàng thì từ chối, vì tạo một đơn với giá
> không rõ nguồn chính là NG-08. Ghi vào sổ theo dõi để lần sau không ai "thống nhất" lại.

- [ ] **Step 6: Chạy bộ test đặt hàng và đọc cổng**

Run:
```bash
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_order_place
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_portal_read
```
Expected: PASS.

- [ ] **Step 7: Ghi sổ theo dõi + commit**

```markdown
### NG-10 + NG-11 · Bảng giá không lọc ngày, nhiều bản ghi lấy tuỳ ý — 2026-08-12 · commit <sha>
**Trước:** Hai bản sao của cùng câu `frappe.db.get_value("Item Price", ...)` — một trong `portal_catalog`, một trong `portal_order_place` — không lọc `valid_from`/`valid_upto` và không có `order_by`. Giá đã hết hiệu lực vẫn dùng được; nhiều bản ghi thoả điều kiện thì bản nào thắng là ngẫu nhiên.
**Sau:** Một hàm duy nhất `portal_pricing.gia_ban(item_code, price_list, ngay)`. Lọc ngày hiệu lực (rỗng = luôn hiệu lực), sắp xếp `valid_from desc, modified desc`, trả số nguyên VND qua `lam_tron_tien`, trả `None` khi không có giá.
**Đụng vào:** `miyano_portal/portal_pricing.py` (mới) · `api/portal.py::portal_catalog` · `api/portal.py::portal_order_place`
**Phá vỡ:** Mặt hàng chỉ có `Item Price` đã hết hiệu lực: danh mục lùi về giá hợp đồng, **đặt hàng bị từ chối** (trước đây vẫn đặt được với giá cũ). Đây là hành vi mong muốn.
**Test:** `miyano_portal/tests/test_portal_pricing.py` — 7 test.
**Cảnh báo chồng lấn:** Hai nhánh xử lý "không có giá" **cố ý khác nhau** (catalog lùi về giá hợp đồng, order_place từ chối). Đừng "thống nhất" lại. Lọc ngày làm bằng Python **cố ý**, không phải bằng `filters` SQL — trình dựng truy vấn Frappe bọc `ifnull()` làm ngày rỗng lọt bộ lọc (cùng cơ chế NG-28).
```

Cập nhật bảng tiến độ: `NG-10` ✅, `NG-11` ✅.

```bash
git add miyano_portal/portal_pricing.py miyano_portal/api/portal.py \
        miyano_portal/tests/test_portal_pricing.py docs/CHANGELOG-khac-phuc-BA-v2.md
git commit -m "fix(portal): một hàm đọc giá duy nhất, lọc ngày hiệu lực và xác định (NG-10, NG-11)"
```

---

## Task 4: NG-09 — tính VAT thật theo mẫu thuế của khách hàng (QĐ-02 = A)

**Files:**
- Modify: `miyano_portal/portal_pricing.py`
- Modify: `miyano_portal/api/portal.py::portal_catalog`
- Test: `miyano_portal/tests/test_portal_thue.py`

**Interfaces:**
- Consumes: `portal_pricing.gia_ban()` (Task 3), `kho.ledger.lam_tron_tien()` (Task 2)
- Produces:
  - `portal_pricing.mau_thue(customer: str, company: str, ngay: str | None = None) -> str | None`
  - `portal_pricing.thue_suat(customer: str, company: str) -> float` — tổng thuế suất % của mẫu; `0.0` khi không có mẫu
  - `portal_pricing.tinh_tong(dong: list[dict], thue_pct: float) -> dict` — trả `{"tam_tinh", "thue", "tong"}`, tất cả số nguyên

**Bối cảnh quyết định.** QĐ-02 chốt **A**: Miyano **có** xuất hoá đơn VAT; dữ liệu
0/7 hoá đơn không thuế trên `erptest.local` là **dữ liệu thử**. Nghĩa là đang ở nhánh
thứ hai của bảng trong BA v2 §NG-09: *cổng đang thiếu hẳn phần thuế, và mọi tổng tiền
hiển thị cho khách đều thấp hơn số phải trả*. Đây là P0 thật.

**Cách ERPNext gắn mẫu thuế với khách hàng.** `Customer` **không** có trường trỏ thẳng
tới `Sales Taxes and Charges Template`. Đường đi là `Customer.tax_category` →
`Tax Rule` / `Sales Taxes and Charges Template.tax_category`, có nhánh lùi về template
`is_default = 1` của company. ERPNext đã có hàm giải quyết đúng chuỗi này:
`erpnext.accounts.party.set_taxes()`. **Dùng nó, đừng tự viết lại** — viết lại nghĩa là
cổng và hoá đơn dùng hai quy tắc chọn thuế khác nhau, và độ lệch sẽ chỉ lộ ra ở khâu
thanh toán.

**⚠️ Việc ngoài code chặn task này:** cần kế toán khai `Sales Taxes and Charges Template`
(và `tax_category` trên từng `Customer` nếu dùng nhiều thuế suất) **trước** khi chạy được
trên dữ liệu thật. Không có template thì `thue_suat()` trả `0.0` và cổng hiển thị đúng
"chưa khai thuế" — không sai, nhưng cũng chưa xong. Xem lộ trình §4.1.

- [ ] **Step 1: Viết test thất bại**

Tạo `miyano_portal/tests/test_portal_thue.py`:

```python
import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.portal_pricing import mau_thue, thue_suat, tinh_tong
from miyano_portal.setup.seed_demo import seed_demo

BVBM = "Bệnh viện Bạch Mai"


def _mau_thue_8(company: str) -> str:
    ten = "VAT 8% cổng (test)"
    if frappe.db.exists("Sales Taxes and Charges Template", {"title": ten}):
        return frappe.db.get_value(
            "Sales Taxes and Charges Template", {"title": ten}, "name"
        )
    tk = frappe.get_all(
        "Account",
        filters={"company": company, "account_type": "Tax", "is_group": 0},
        limit=1, pluck="name",
    )
    if not tk:
        tk = frappe.get_all(
            "Account", filters={"company": company, "is_group": 0}, limit=1, pluck="name"
        )
    d = frappe.get_doc({
        "doctype": "Sales Taxes and Charges Template",
        "title": ten,
        "company": company,
        "is_default": 1,
        "taxes": [{
            "charge_type": "On Net Total",
            "account_head": tk[0],
            "description": "VAT 8%",
            "rate": 8,
        }],
    })
    d.insert(ignore_permissions=True)
    return d.name


class TestThuePortal(FrappeTestCase):
    def setUp(self):
        seed_demo()
        self.company = frappe.get_all("Company", limit=1, pluck="name")[0]

    def test_khong_co_mau_thue_thi_suat_bang_0(self):
        frappe.db.set_value(
            "Sales Taxes and Charges Template",
            {"company": self.company}, "is_default", 0, update_modified=False,
        )
        self.assertEqual(thue_suat(BVBM, self.company), 0.0)

    def test_lay_duoc_mau_thue_mac_dinh_cua_company(self):
        _mau_thue_8(self.company)
        self.assertIsNotNone(mau_thue(BVBM, self.company))
        self.assertEqual(thue_suat(BVBM, self.company), 8.0)

    # ---------- làm tròn: đây là phần dễ sai nhất ----------
    def test_tong_bang_tam_tinh_cong_thue_khong_lech_1_dong(self):
        """Ca cố tình xấu: số lượng lẻ, đơn giá lẻ, thuế suất phần trăm."""
        dong = [
            {"qty": 7.5, "rate": 133333},   # 999 997,5
            {"qty": 3, "rate": 66667},      # 200 001
        ]
        kq = tinh_tong(dong, 8.0)
        self.assertEqual(kq["tam_tinh"], 999998 + 200001)
        self.assertEqual(kq["thue"], round((999998 + 200001) * 0.08))
        self.assertEqual(kq["tong"], kq["tam_tinh"] + kq["thue"])
        for v in kq.values():
            self.assertEqual(v, int(v), "còn phần thập phân trong tổng kết")

    def test_thanh_tien_tung_dong_duoc_lam_tron_truoc_khi_cong(self):
        """Nếu cộng float thô rồi mới làm tròn ở cuối thì test này fail."""
        dong = [{"qty": 1, "rate": 0.5}] * 4   # 4 × 0,5
        kq = tinh_tong(dong, 0.0)
        # 4 dòng, mỗi dòng làm tròn thành 1 (round-half-even → 0 với 0.5!)
        # nên khẳng định điều duy nhất luôn đúng: tổng = tổng các dòng đã tròn
        self.assertEqual(kq["tam_tinh"], sum(d["thanh_tien"] for d in kq["dong"]))

    def test_thue_suat_0_thi_tong_bang_tam_tinh(self):
        kq = tinh_tong([{"qty": 2, "rate": 50000}], 0.0)
        self.assertEqual(kq["thue"], 0)
        self.assertEqual(kq["tong"], kq["tam_tinh"])
```

- [ ] **Step 2: Chạy để thấy FAIL**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_portal_thue`
Expected: FAIL — `ImportError: cannot import name 'mau_thue'`

- [ ] **Step 3: Bổ sung vào `portal_pricing.py`**

```python
def mau_thue(customer: str, company: str, ngay: str | None = None) -> str | None:
    """Tên `Sales Taxes and Charges Template` áp cho khách này — QĐ-02 phương án A.

    `Customer` KHÔNG có trường trỏ thẳng tới template. Chuỗi thật là
    `Customer.tax_category` → `Tax Rule` / `Sales Taxes and Charges Template`,
    có nhánh lùi về template `is_default = 1` của company. ERPNext đã giải
    quyết đúng chuỗi này trong `erpnext.accounts.party.set_taxes()`.

    Gọi lại nó thay vì tự viết: nếu cổng chọn thuế theo một quy tắc và hoá đơn
    chọn theo quy tắc khác thì độ lệch chỉ lộ ra ở khâu thanh toán, hàng tuần
    sau — đúng loại sai lệch không tự lộ ra mà NG-08 mô tả.
    """
    from erpnext.accounts.party import set_taxes

    try:
        return set_taxes(
            party=customer,
            party_type="Customer",
            posting_date=ngay or frappe.utils.today(),
            company=company,
        )
    except Exception:
        # Khai thiếu Tax Category / Tax Rule không được phép làm trắng danh mục.
        frappe.log_error(
            title="Cổng khách: không giải được mẫu thuế",
            message=frappe.get_traceback(with_context=True),
        )
        return None


def thue_suat(customer: str, company: str, ngay: str | None = None) -> float:
    """Tổng thuế suất % của mẫu thuế áp cho khách. 0.0 khi chưa khai mẫu nào.

    Chỉ cộng các dòng `On Net Total` — đó là dạng duy nhất quy được về một
    thuế suất phần trăm áp đều cho mọi dòng hàng. Mẫu có `Actual` hoặc
    `On Previous Row` không quy về một con số được; trả về phần trăm của riêng
    các dòng `On Net Total` và ghi log, để cổng không âm thầm báo sai.
    """
    ten = mau_thue(customer, company, ngay)
    if not ten:
        return 0.0
    tong = 0.0
    co_dong_phuc_tap = False
    for d in frappe.get_all(
        "Sales Taxes and Charges",
        filters={"parent": ten, "parenttype": "Sales Taxes and Charges Template"},
        fields=["charge_type", "rate"],
    ):
        if d.charge_type == "On Net Total":
            tong += flt(d.rate)
        else:
            co_dong_phuc_tap = True
    if co_dong_phuc_tap:
        frappe.log_error(
            title="Cổng khách: mẫu thuế có dòng không quy về % được",
            message=f"Mẫu {ten} có dòng charge_type khác 'On Net Total'. "
                    f"Cổng chỉ hiển thị phần {tong}% và có thể lệch so với hoá đơn.",
        )
    return tong


def tinh_tong(dong: list[dict], thue_pct: float) -> dict:
    """Tạm tính / thuế / tổng — tất cả là số nguyên VND.

    Làm tròn TỪNG dòng TRƯỚC rồi mới cộng dồn. Nếu cộng float thô rồi làm tròn
    ở cuối thì `tam_tinh` sẽ không bằng tổng các `thanh_tien` mà khách nhìn
    thấy trên màn hình, và độ lệch chỉ hiện ra khi có số lượng lẻ.

    `tong` = `tam_tinh` + `thue`, cả hai đều đã là số nguyên → không thể trôi.
    Đây chính là bất biến mà BA v2 §NG-12 mô tả cho phía sổ kho, áp sang phía
    bán hàng.
    """
    ra = []
    tam_tinh = 0.0
    for d in dong:
        thanh_tien = lam_tron_tien(flt(d["qty"]) * flt(d["rate"]))
        ra.append({**d, "thanh_tien": thanh_tien})
        tam_tinh += thanh_tien
    thue = lam_tron_tien(tam_tinh * flt(thue_pct) / 100.0)
    return {
        "dong": ra,
        "tam_tinh": tam_tinh,
        "thue_pct": flt(thue_pct),
        "thue": thue,
        "tong": tam_tinh + thue,
    }
```

- [ ] **Step 4: Chạy test — PASS**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_portal_thue`
Expected: **6 tests PASS**.

- [ ] **Step 5: Bỏ `"vat_pct": 0` gán cứng trong `portal_catalog`**

Trong `api/portal.py::portal_catalog`, trước vòng lặp thêm:
```python
    company = frappe.db.get_value("Blanket Order", contract, "company")
    vat_pct = thue_suat(customer, company)
```
và trong dict trả về, thay `"vat_pct": 0,` bằng `"vat_pct": vat_pct,`.

Thêm import: `from miyano_portal.portal_pricing import gia_ban, thue_suat`

> Danh mục nay trả **thuế suất thật**. Giỏ hàng ở Task 11 sẽ không còn tự nhân
> `vat_pct` ở phía trình duyệt nữa — nó sẽ đọc tổng kết từ báo giá chốt (Task 5).
> Giữ `vat_pct` trong danh mục vì màn danh mục vẫn hiển thị nó ở dòng phụ (BA v2 §C2 Màn 1).

- [ ] **Step 6: Chạy lại bộ đọc cổng**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_portal_read`
Expected: PASS. Nếu có test khoá cứng `vat_pct == 0` thì đó là test đang khoá lại hành vi sai — sửa nó và ghi vào sổ theo dõi.

- [ ] **Step 7: Ghi sổ theo dõi + commit**

```markdown
### NG-09 · Toàn hệ thống không tính VAT nhưng giao diện hứa có — 2026-08-12 · commit <sha>
**Quyết định:** QĐ-02 = **A**. Miyano **có** xuất hoá đơn VAT trong thực tế; dữ liệu 0/7 hoá đơn không thuế trên `erptest.local` là dữ liệu thử. Tức đang ở nhánh hai của bảng BA v2 §NG-09 — cổng thiếu hẳn phần thuế, mọi tổng tiền báo cho khách đều **thấp hơn** số phải trả.
**Trước:** `portal_catalog` trả `"vat_pct": 0` gán cứng cho mọi mặt hàng; `portal_order_place` không gắn `taxes_and_charges`; giỏ hàng vẫn hiện dòng "VAT (5–8%)" luôn bằng 0.
**Sau:** `portal_pricing.mau_thue()` giải mẫu thuế qua `erpnext.accounts.party.set_taxes()` (cùng quy tắc hoá đơn dùng, không viết lại). `thue_suat()` quy về một % từ các dòng `On Net Total`, ghi log khi mẫu có dòng không quy được. `tinh_tong()` làm tròn từng dòng trước khi cộng, `tong = tam_tinh + thue` toàn số nguyên. `portal_catalog` trả thuế suất thật.
**Đụng vào:** `miyano_portal/portal_pricing.py` (thêm 3 hàm) · `api/portal.py::portal_catalog`
**Phá vỡ:** Danh mục trả `vat_pct` khác 0 → tổng tiền khách nhìn thấy **tăng lên** so với trước. Đây là con số đúng. Việc gắn `taxes_and_charges` lên Sales Order nằm ở Task 6, không phải task này.
**Chặn bởi việc ngoài code:** kế toán phải khai `Sales Taxes and Charges Template` (+ `tax_category` trên Customer nếu nhiều thuế suất). Chưa khai thì `thue_suat()` trả 0.0 — không sai, nhưng chưa xong.
**Test:** `miyano_portal/tests/test_portal_thue.py` — 6 test, gồm ca cố tình xấu 7.5 × 133 333 với thuế 8%.
**Cảnh báo chồng lấn:** Mẫu thuế có `charge_type` khác `On Net Total` **không** quy về một % được — cổng chỉ hiển thị phần `On Net Total` và ghi Error Log. Nếu Miyano dùng mẫu như vậy thì cần mở lại QĐ-02 nhánh B (thuế theo mặt hàng).
```

Cập nhật bảng tiến độ: `NG-09` ✅.

```bash
git add miyano_portal/portal_pricing.py miyano_portal/api/portal.py \
        miyano_portal/tests/test_portal_thue.py docs/CHANGELOG-khac-phuc-BA-v2.md
git commit -m "feat(portal): tính VAT thật theo mẫu thuế của khách hàng (NG-09, QĐ-02 A)"
```

---

## Task 5: NG-08 / API-03 — doctype `Portal Quote Lock` và endpoint báo giá chốt

**Files:**
- Create: `miyano_portal/miyano_portal/doctype/portal_quote_lock/portal_quote_lock.json`
- Create: `miyano_portal/miyano_portal/doctype/portal_quote_lock/portal_quote_lock.py`
- Create: `miyano_portal/miyano_portal/doctype/portal_quote_lock/__init__.py`
- Create: `miyano_portal/miyano_portal/doctype/portal_quote_lock_item/portal_quote_lock_item.json`
- Create: `miyano_portal/miyano_portal/doctype/portal_quote_lock_item/__init__.py`
- Modify: `miyano_portal/api/portal.py` (thêm `portal_quote`)
- Test: `miyano_portal/tests/test_portal_quote.py`

**Interfaces:**
- Consumes: `portal_pricing.gia_ban()`, `portal_pricing.thue_suat()`, `portal_pricing.tinh_tong()` (Task 3, 4)
- Produces: `@frappe.whitelist() portal_quote(contract, items) -> dict` trả:
  ```
  {"quote": "<tên bản ghi>", "het_han": "<datetime>", "tam_tinh": int,
   "thue_pct": float, "thue": int, "tong": int,
   "dong": [{"item_code", "item_name", "uom", "qty", "rate", "thanh_tien"}]}
  ```
- Produces: `PortalQuoteLock.doi_chieu(items) -> list[dict]` — so giỏ hàng hiện tại với bản đã chốt, trả danh sách dòng lệch (rỗng = khớp). Task 6 dùng.

**Vì sao là doctype chứ không phải cache.** BA v2 §NG-12 ghi thẳng: *"Phiếu báo giá chốt
ở NG-08, nếu được **lưu lại**, giải quyết luôn một nhu cầu nữa: khi khách thắc mắc 'lúc
tôi đặt giá là 78.000', hiện không có gì để tra."* Cache Redis mất khi restart và không
tra lại được. Một doctype nhẹ, chỉ đọc, là câu trả lời cho cả hai nhu cầu.

**Thời hạn chốt: 30 phút.** Đủ dài cho một lần điền giỏ hàng bình thường, đủ ngắn để
không giữ một mức giá qua đêm — chính kịch bản "tab để mở qua đêm" mà BA v2 §NG-08 nêu.

- [ ] **Step 1: Viết test thất bại**

Tạo `miyano_portal/tests/test_portal_quote.py`:

```python
import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api.portal import portal_quote
from miyano_portal.setup.seed_demo import seed_demo

USER_BVBM = "bvbm@demo.miyano"
BVBM = "Bệnh viện Bạch Mai"


def _hop_dong_cua(customer):
    return frappe.db.get_value(
        "Blanket Order",
        {"customer": customer, "blanket_order_type": "Selling"},
        "name",
    )


class TestPortalQuote(FrappeTestCase):
    def setUp(self):
        seed_demo()
        self.hd = _hop_dong_cua(BVBM)
        self.item = frappe.db.get_value(
            "Blanket Order Item", {"parent": self.hd}, "item_code"
        )
        self.addCleanup(frappe.set_user, "Administrator")
        frappe.set_user(USER_BVBM)

    def test_tra_ve_ma_chot_va_thoi_han(self):
        kq = portal_quote(self.hd, [{"item_code": self.item, "qty": 2}])
        self.assertTrue(kq["quote"])
        self.assertTrue(kq["het_han"])
        self.assertTrue(frappe.db.exists("Portal Quote Lock", kq["quote"]))

    def test_tong_do_may_chu_tinh_va_la_so_nguyen(self):
        kq = portal_quote(self.hd, [{"item_code": self.item, "qty": 3}])
        self.assertEqual(kq["tong"], kq["tam_tinh"] + kq["thue"])
        for k in ("tam_tinh", "thue", "tong"):
            self.assertEqual(kq[k], int(kq[k]))
        self.assertEqual(kq["tam_tinh"], sum(d["thanh_tien"] for d in kq["dong"]))

    def test_gop_dong_trung_cung_mat_hang(self):
        kq = portal_quote(self.hd, [
            {"item_code": self.item, "qty": 2},
            {"item_code": self.item, "qty": 3},
        ])
        self.assertEqual(len(kq["dong"]), 1)
        self.assertEqual(kq["dong"][0]["qty"], 5)

    def test_khong_chot_duoc_hop_dong_cua_khach_khac(self):
        hd_khac = _hop_dong_cua("PXN ABC")
        if not hd_khac:
            self.skipTest("seed chưa có hợp đồng cho khách thứ hai")
        with self.assertRaises(frappe.PermissionError):
            portal_quote(hd_khac, [{"item_code": self.item, "qty": 1}])

    def test_doi_chieu_phat_hien_gia_doi(self):
        kq = portal_quote(self.hd, [{"item_code": self.item, "qty": 2}])
        doc = frappe.get_doc("Portal Quote Lock", kq["quote"])
        # Không lệch khi giá chưa đổi
        self.assertEqual(doc.doi_chieu([{"item_code": self.item, "qty": 2}]), [])
        # Đổi giá đã chốt → lệch
        frappe.db.set_value(
            "Portal Quote Lock Item",
            {"parent": doc.name, "item_code": self.item},
            "rate", 1, update_modified=False,
        )
        doc.reload()
        lech = doc.doi_chieu([{"item_code": self.item, "qty": 2}])
        self.assertEqual(len(lech), 1)
        self.assertEqual(lech[0]["item_code"], self.item)
        self.assertIn("gia_cu", lech[0])
        self.assertIn("gia_moi", lech[0])

    def test_doi_chieu_phat_hien_them_mat_hang_ngoai_bao_gia(self):
        kq = portal_quote(self.hd, [{"item_code": self.item, "qty": 2}])
        doc = frappe.get_doc("Portal Quote Lock", kq["quote"])
        khac = frappe.db.get_value(
            "Blanket Order Item",
            {"parent": self.hd, "item_code": ["!=", self.item]},
            "item_code",
        )
        if not khac:
            self.skipTest("hợp đồng chỉ có một mặt hàng")
        lech = doc.doi_chieu([
            {"item_code": self.item, "qty": 2},
            {"item_code": khac, "qty": 1},
        ])
        self.assertTrue(lech)

    def test_doi_chieu_phat_hien_doi_so_luong(self):
        kq = portal_quote(self.hd, [{"item_code": self.item, "qty": 2}])
        doc = frappe.get_doc("Portal Quote Lock", kq["quote"])
        self.assertTrue(doc.doi_chieu([{"item_code": self.item, "qty": 5}]))

    def test_het_han_thi_bao_het_han(self):
        kq = portal_quote(self.hd, [{"item_code": self.item, "qty": 2}])
        frappe.db.set_value(
            "Portal Quote Lock", kq["quote"], "het_han",
            frappe.utils.add_to_date(frappe.utils.now(), minutes=-1),
            update_modified=False,
        )
        doc = frappe.get_doc("Portal Quote Lock", kq["quote"])
        self.assertTrue(doc.da_het_han())
```

- [ ] **Step 2: Chạy để thấy FAIL**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_portal_quote`
Expected: FAIL — `ImportError: cannot import name 'portal_quote'`

- [ ] **Step 3: Tạo doctype bảng con**

`miyano_portal/miyano_portal/doctype/portal_quote_lock_item/__init__.py` (rỗng)

`portal_quote_lock_item.json`:
```json
{
 "actions": [],
 "creation": "2026-08-12 00:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 1,
 "engine": "InnoDB",
 "field_order": ["item_code", "item_name", "uom", "qty", "rate", "thanh_tien"],
 "fields": [
  {"fieldname": "item_code", "fieldtype": "Link", "options": "Item", "label": "Mã hàng", "in_list_view": 1, "reqd": 1},
  {"fieldname": "item_name", "fieldtype": "Data", "label": "Tên hàng", "in_list_view": 1},
  {"fieldname": "uom", "fieldtype": "Data", "label": "ĐVT"},
  {"fieldname": "qty", "fieldtype": "Float", "label": "Số lượng", "precision": "3", "in_list_view": 1, "reqd": 1},
  {"fieldname": "rate", "fieldtype": "Currency", "label": "Đơn giá", "precision": "0", "in_list_view": 1},
  {"fieldname": "thanh_tien", "fieldtype": "Currency", "label": "Thành tiền", "precision": "0", "read_only": 1}
 ],
 "istable": 1,
 "module": "Miyano Portal",
 "name": "Portal Quote Lock Item",
 "owner": "Administrator",
 "permissions": [],
 "sort_field": "modified",
 "sort_order": "DESC"
}
```

- [ ] **Step 4: Tạo doctype cha**

`portal_quote_lock/__init__.py` (rỗng)

`portal_quote_lock.json`:
```json
{
 "actions": [],
 "autoname": "format:BGC-{YY}{MM}-{#####}",
 "creation": "2026-08-12 00:00:00.000000",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": [
  "customer", "contract", "company", "column_break_1", "het_han", "da_dung", "sales_order",
  "section_dong", "items",
  "section_tong", "tam_tinh", "thue_pct", "thue", "tong"
 ],
 "fields": [
  {"fieldname": "customer", "fieldtype": "Link", "options": "Customer", "label": "Khách hàng", "reqd": 1, "read_only": 1, "in_list_view": 1},
  {"fieldname": "contract", "fieldtype": "Link", "options": "Blanket Order", "label": "Hợp đồng nguyên tắc", "reqd": 1, "read_only": 1},
  {"fieldname": "company", "fieldtype": "Link", "options": "Company", "label": "Công ty", "read_only": 1},
  {"fieldname": "column_break_1", "fieldtype": "Column Break"},
  {"fieldname": "het_han", "fieldtype": "Datetime", "label": "Hiệu lực đến", "reqd": 1, "read_only": 1, "in_list_view": 1},
  {"fieldname": "da_dung", "fieldtype": "Check", "label": "Đã dùng để đặt hàng", "read_only": 1},
  {"fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "label": "Đơn hàng đã tạo", "read_only": 1},
  {"fieldname": "section_dong", "fieldtype": "Section Break", "label": "Dòng hàng"},
  {"fieldname": "items", "fieldtype": "Table", "options": "Portal Quote Lock Item", "label": "Dòng hàng", "read_only": 1},
  {"fieldname": "section_tong", "fieldtype": "Section Break", "label": "Tổng kết"},
  {"fieldname": "tam_tinh", "fieldtype": "Currency", "label": "Tạm tính", "precision": "0", "read_only": 1},
  {"fieldname": "thue_pct", "fieldtype": "Percent", "label": "Thuế suất", "read_only": 1},
  {"fieldname": "thue", "fieldtype": "Currency", "label": "Tiền thuế", "precision": "0", "read_only": 1},
  {"fieldname": "tong", "fieldtype": "Currency", "label": "Tổng cộng", "precision": "0", "read_only": 1, "in_list_view": 1}
 ],
 "index_web_pages_for_search": 0,
 "module": "Miyano Portal",
 "name": "Portal Quote Lock",
 "owner": "Administrator",
 "permissions": [
  {"role": "System Manager", "read": 1, "write": 0, "create": 0, "delete": 1, "report": 1, "export": 1},
  {"role": "Sales User", "read": 1, "report": 1, "export": 1}
 ],
 "sort_field": "creation",
 "sort_order": "DESC",
 "track_changes": 0
}
```

> **Role `Customer` cố ý KHÔNG có DocPerm.** Khách đọc báo giá của mình qua endpoint
> `portal_quote`, không qua doctype — đúng mô hình cách ly hiện tại (BA v1 §8.2). Cấp
> DocPerm ở đây sẽ mở lại đúng loại lỗ mà `permission_query_conditions` không đóng được
> hết. **`track_changes: 0`** vì bản ghi này chỉ ghi một lần, không sửa.

- [ ] **Step 5: Viết controller**

`portal_quote_lock.py`:
```python
"""Báo giá chốt — BA v2 §NG-08.

Vấn đề gốc: `portal_order_place` đọc lại đơn giá từ `Item Price` TẠI THỜI ĐIỂM
ĐẶT, trong khi giỏ hàng đang giữ đơn giá lấy về lúc mở danh mục. Khách bấm "Xác
nhận đặt hàng" trên một tổng tiền, đơn hàng được tạo với một tổng tiền khác,
không thông báo, không xác nhận lại.

Bản ghi này là "số tiền khách đã nhìn thấy", do máy chủ tính và lưu lại. Đặt
hàng phải kèm mã chốt; nếu giá đã đổi thì từ chối và hiện bảng so cũ/mới.

Lưu lại (chứ không để trong cache) còn giải quyết một nhu cầu thứ hai mà BA v2
§NG-12 nêu: khi khách thắc mắc "lúc tôi đặt giá là 78.000" thì có chỗ để tra.
"""

import frappe
from frappe.model.document import Document
from frappe.utils import flt, now_datetime, get_datetime


class PortalQuoteLock(Document):
    def da_het_han(self) -> bool:
        return get_datetime(self.het_han) < now_datetime()

    def doi_chieu(self, items: list[dict]) -> list[dict]:
        """So giỏ hàng gửi lên với bản đã chốt. Rỗng = khớp.

        Kiểm cả ba chiều, vì mỗi chiều là một cách đơn hàng khác đi so với thứ
        khách đã xác nhận:
          - đơn giá đổi        → tổng tiền khác
          - số lượng đổi       → tổng tiền khác
          - thêm/bớt mặt hàng  → đơn khác hẳn

        Đơn giá "mới" đọc lại bằng ĐÚNG hàm đã dùng lúc chốt, nên chênh lệch ở
        đây phản ánh giá thật đổi chứ không phải hai quy tắc đọc giá khác nhau.
        """
        from miyano_portal.portal_pricing import gia_ban

        price_list = frappe.db.get_value("Customer", self.customer, "default_price_list")
        da_chot = {r.item_code: r for r in self.items}

        gio = {}
        for line in items:
            ma = line.get("item_code")
            gio[ma] = gio.get(ma, 0.0) + flt(line.get("qty"))

        lech = []
        for ma, qty in gio.items():
            row = da_chot.get(ma)
            if not row:
                lech.append({
                    "item_code": ma, "ly_do": "them_moi",
                    "gia_cu": None, "gia_moi": gia_ban(ma, price_list),
                    "sl_cu": None, "sl_moi": qty,
                })
                continue
            gia_moi = gia_ban(ma, price_list)
            if gia_moi is None or flt(gia_moi) != flt(row.rate):
                lech.append({
                    "item_code": ma, "item_name": row.item_name, "ly_do": "gia_doi",
                    "gia_cu": flt(row.rate), "gia_moi": gia_moi,
                    "sl_cu": flt(row.qty), "sl_moi": qty,
                })
            elif flt(qty) != flt(row.qty):
                lech.append({
                    "item_code": ma, "item_name": row.item_name, "ly_do": "so_luong_doi",
                    "gia_cu": flt(row.rate), "gia_moi": gia_moi,
                    "sl_cu": flt(row.qty), "sl_moi": qty,
                })
        for ma, row in da_chot.items():
            if ma not in gio:
                lech.append({
                    "item_code": ma, "item_name": row.item_name, "ly_do": "da_bo",
                    "gia_cu": flt(row.rate), "gia_moi": None,
                    "sl_cu": flt(row.qty), "sl_moi": 0,
                })
        return lech
```

- [ ] **Step 6: Viết endpoint `portal_quote` (API-03)**

Thêm vào `miyano_portal/api/portal.py`:

```python
# Thời hạn báo giá chốt. 30 phút: đủ cho một lần điền giỏ hàng bình thường, đủ
# ngắn để không giữ một mức giá qua đêm — chính kịch bản "tab để mở qua đêm"
# mà BA v2 §NG-08 nêu.
QUOTE_TTL_PHUT = 30


@frappe.whitelist()
def portal_quote(contract, items) -> dict:
    """API-03 — nhận giỏ hàng, trả bảng giá + thuế + tổng + mã chốt + thời hạn.

    Máy chủ tính, không phải trình duyệt. Đây là con số duy nhất khách được
    phép nhìn thấy trước khi bấm xác nhận, và `portal_order_place` sẽ từ chối
    nếu nó đã đổi.
    """
    customer = get_portal_customer()
    bo = frappe.db.get_value(
        "Blanket Order", contract, ["customer", "company"], as_dict=True
    )
    if not bo or bo.customer != customer:
        raise frappe.PermissionError("Hợp đồng không thuộc đơn vị của bạn.")

    if isinstance(items, str):
        items = frappe.parse_json(items)
    if not items:
        frappe.throw("Giỏ hàng trống.")

    price_list = frappe.db.get_value("Customer", customer, "default_price_list")

    # Gộp dòng trùng TRƯỚC khi tính, giống portal_order_place — nếu hai chỗ gộp
    # khác nhau thì báo giá và đơn hàng lệch nhau ngay từ đầu.
    gop = {}
    for line in items:
        ma = line.get("item_code")
        gop[ma] = gop.get(ma, 0.0) + float(line.get("qty") or 0)

    dong = []
    for ma, qty in gop.items():
        if qty <= 0:
            frappe.throw(f"{ma}: số lượng phải > 0")
        rate = gia_ban(ma, price_list)
        if rate is None:
            frappe.throw(
                f"Không tìm thấy giá bán còn hiệu lực cho mặt hàng {ma}. "
                "Vui lòng liên hệ nhân viên kinh doanh Miyano."
            )
        it = frappe.db.get_value("Item", ma, ["item_name", "stock_uom"], as_dict=True)
        dong.append({
            "item_code": ma,
            "item_name": (it.item_name if it else ma),
            "uom": (it.stock_uom if it else ""),
            "qty": qty,
            "rate": rate,
        })

    kq = tinh_tong(dong, thue_suat(customer, bo.company))

    doc = frappe.new_doc("Portal Quote Lock")
    doc.customer = customer
    doc.contract = contract
    doc.company = bo.company
    doc.het_han = frappe.utils.add_to_date(
        frappe.utils.now(), minutes=QUOTE_TTL_PHUT
    )
    doc.tam_tinh = kq["tam_tinh"]
    doc.thue_pct = kq["thue_pct"]
    doc.thue = kq["thue"]
    doc.tong = kq["tong"]
    for d in kq["dong"]:
        doc.append("items", d)
    doc.insert(ignore_permissions=True)

    return {
        "quote": doc.name,
        "het_han": str(doc.het_han),
        "tam_tinh": kq["tam_tinh"],
        "thue_pct": kq["thue_pct"],
        "thue": kq["thue"],
        "tong": kq["tong"],
        "dong": kq["dong"],
    }
```

Thêm import: `from miyano_portal.portal_pricing import gia_ban, thue_suat, tinh_tong`

- [ ] **Step 7: Migrate rồi chạy test**

Run:
```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_portal_quote
```
Expected: **8 tests PASS**.

- [ ] **Step 8: Kiểm cách ly — khách không đọc được doctype trực tiếp**

Thêm vào `miyano_portal/tests/test_portal_quote.py`:

```python
    def test_khach_khong_doc_duoc_doctype_truc_tiep(self):
        """Role Customer cố ý không có DocPerm. Khách đọc báo giá qua endpoint."""
        frappe.set_user(USER_BVBM)
        self.assertFalse(
            frappe.has_permission("Portal Quote Lock", "read", user=USER_BVBM)
        )
```

Run lại module. Expected: **9 tests PASS**.

- [ ] **Step 9: Ghi sổ theo dõi + commit**

```markdown
### NG-08 (phần 1/2) · API-03 báo giá chốt — 2026-08-12 · commit <sha>
**Trước:** Không có bước chốt giá. Giỏ hàng giữ đơn giá lấy về lúc mở danh mục; `portal_order_place` đọc lại giá tại thời điểm đặt. Khách xác nhận một tổng tiền, đơn tạo với tổng tiền khác, không báo.
**Sau:** Doctype `Portal Quote Lock` (+ `Portal Quote Lock Item`) lưu bảng giá do **máy chủ** tính, kèm `het_han` (TTL 30 phút). Endpoint `portal_quote(contract, items)` = API-03. `PortalQuoteLock.doi_chieu(items)` so giỏ hàng với bản chốt theo ba chiều: giá đổi · số lượng đổi · thêm/bớt mặt hàng.
**Đụng vào:** `doctype/portal_quote_lock/*` (mới) · `doctype/portal_quote_lock_item/*` (mới) · `api/portal.py` (thêm `portal_quote`, hằng `QUOTE_TTL_PHUT`)
**Phá vỡ:** Chưa. Task này chỉ **thêm** endpoint; `portal_order_place` chưa bắt buộc mã chốt (Task 6).
**Test:** `miyano_portal/tests/test_portal_quote.py` — 9 test.
**Cảnh báo chồng lấn:** Role `Customer` **cố ý không có DocPerm** trên `Portal Quote Lock`. Đừng cấp — khách đọc qua endpoint. `track_changes: 0` vì bản ghi chỉ ghi một lần. Việc gộp dòng trùng trong `portal_quote` phải **giống hệt** `portal_order_place`; sửa một chỗ thì sửa cả hai.
```

Cập nhật bảng tiến độ: `NG-08` → 🟨 (phần 1/2 xong).

```bash
git add miyano_portal/miyano_portal/doctype/portal_quote_lock \
        miyano_portal/miyano_portal/doctype/portal_quote_lock_item \
        miyano_portal/api/portal.py miyano_portal/tests/test_portal_quote.py \
        docs/CHANGELOG-khac-phuc-BA-v2.md
git commit -m "feat(portal): doctype báo giá chốt và endpoint portal_quote (NG-08, API-03)"
```

---

## Task 6: NG-08 / API-04 — `portal_order_place` nhận mã chốt và gắn thuế lên đơn

**Files:**
- Modify: `miyano_portal/api/portal.py:191-283` (`portal_order_place`)
- Test: `miyano_portal/tests/test_order_place.py` (mở rộng)

**Interfaces:**
- Consumes: `PortalQuoteLock.doi_chieu()`, `PortalQuoteLock.da_het_han()` (Task 5); `portal_pricing.mau_thue()` (Task 4)
- Produces: `portal_order_place(contract, items, quote=None, po=None, delivery_date=None, note=None, address=None)` — thêm tham số `quote` ở **vị trí thứ ba**, các tham số cũ giữ nguyên tên nên lời gọi bằng keyword của frontend không vỡ.
- Ném `frappe.ValidationError` với `frappe.local.response["gia_lech"] = [...]` khi giá đã đổi, để frontend dựng bảng so cũ/mới.

- [ ] **Step 1: Viết test thất bại**

Thêm vào `miyano_portal/tests/test_order_place.py`:

```python
class TestOrderPlaceQuoteLock(FrappeTestCase):
    def setUp(self):
        seed_demo()
        self.hd = frappe.db.get_value(
            "Blanket Order",
            {"customer": "Bệnh viện Bạch Mai", "blanket_order_type": "Selling"},
            "name",
        )
        self.item = frappe.db.get_value(
            "Blanket Order Item", {"parent": self.hd}, "item_code"
        )
        self.addCleanup(frappe.set_user, "Administrator")
        frappe.set_user("bvbm@demo.miyano")

    def _chot(self, qty=1):
        from miyano_portal.api.portal import portal_quote
        return portal_quote(self.hd, [{"item_code": self.item, "qty": qty}])

    def test_dat_hang_khop_bao_gia_thi_thanh_cong(self):
        from miyano_portal.api.portal import portal_order_place
        bg = self._chot(1)
        kq = portal_order_place(
            self.hd, [{"item_code": self.item, "qty": 1}], quote=bg["quote"]
        )
        so = frappe.get_doc("Sales Order", kq["sales_order"])
        self.assertEqual(float(so.grand_total), float(bg["tong"]))

    def test_tu_choi_khi_gia_da_doi_va_tra_ve_bang_so_sanh(self):
        from miyano_portal.api.portal import portal_order_place
        bg = self._chot(1)
        frappe.db.set_value(
            "Portal Quote Lock Item",
            {"parent": bg["quote"], "item_code": self.item},
            "rate", 1, update_modified=False,
        )
        with self.assertRaises(frappe.ValidationError):
            portal_order_place(
                self.hd, [{"item_code": self.item, "qty": 1}], quote=bg["quote"]
            )
        # LƯU Ý: đây là kiểm trong tiến trình. Nó chứng minh máy chủ ĐÍNH khoá
        # `gia_lech` vào response, KHÔNG chứng minh khoá đó sống sót qua bước
        # tuần tự hoá HTTP để tới trình duyệt — mà toàn bộ hộp thoại so cũ/mới
        # phụ thuộc vào đúng điều đó. Cửa nghiệm thu thật là kịch bản thủ công
        # #4 ở Task 11 Step 6; đừng coi test này là bằng chứng thay thế.
        self.assertTrue(frappe.local.response.get("gia_lech"))

    def test_tu_choi_bao_gia_het_han(self):
        from miyano_portal.api.portal import portal_order_place
        bg = self._chot(1)
        frappe.db.set_value(
            "Portal Quote Lock", bg["quote"], "het_han",
            frappe.utils.add_to_date(frappe.utils.now(), minutes=-1),
            update_modified=False,
        )
        with self.assertRaises(frappe.ValidationError):
            portal_order_place(
                self.hd, [{"item_code": self.item, "qty": 1}], quote=bg["quote"]
            )

    def test_khong_dung_lai_duoc_bao_gia_da_dat(self):
        from miyano_portal.api.portal import portal_order_place
        bg = self._chot(1)
        portal_order_place(
            self.hd, [{"item_code": self.item, "qty": 1}], quote=bg["quote"]
        )
        with self.assertRaises(frappe.ValidationError):
            portal_order_place(
                self.hd, [{"item_code": self.item, "qty": 1}], quote=bg["quote"]
            )

    def test_khong_dung_duoc_bao_gia_cua_khach_khac(self):
        from miyano_portal.api.portal import portal_order_place
        bg = self._chot(1)
        frappe.db.set_value(
            "Portal Quote Lock", bg["quote"], "customer", "PXN ABC",
            update_modified=False,
        )
        with self.assertRaises(frappe.PermissionError):
            portal_order_place(
                self.hd, [{"item_code": self.item, "qty": 1}], quote=bg["quote"]
            )

    def test_don_hang_duoc_gan_mau_thue(self):
        from miyano_portal.api.portal import portal_order_place
        from miyano_portal.portal_pricing import mau_thue
        bg = self._chot(1)
        kq = portal_order_place(
            self.hd, [{"item_code": self.item, "qty": 1}], quote=bg["quote"]
        )
        so = frappe.get_doc("Sales Order", kq["sales_order"])
        mau = mau_thue("Bệnh viện Bạch Mai", so.company)
        if mau:
            self.assertEqual(so.taxes_and_charges, mau)
            self.assertGreater(len(so.taxes), 0)

    def test_thieu_ma_chot_thi_tu_choi(self):
        from miyano_portal.api.portal import portal_order_place
        with self.assertRaises(frappe.ValidationError):
            portal_order_place(self.hd, [{"item_code": self.item, "qty": 1}])
```

- [ ] **Step 2: Chạy để thấy FAIL**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_order_place`
Expected: FAIL — `portal_order_place() got an unexpected keyword argument 'quote'`

- [ ] **Step 3: Sửa chữ ký và thêm khối kiểm mã chốt**

Trong `api/portal.py`, đổi dòng đầu của `portal_order_place`:

```python
@frappe.whitelist()
def portal_order_place(
    contract, items, quote=None, po=None, delivery_date=None, note=None, address=None
) -> dict:
```

Ngay **sau** khối kiểm `bo.customer` và **trước** khối gộp `aggregated`, chèn:

```python
    if isinstance(items, str):
        items = frappe.parse_json(items)
    if not items:
        frappe.throw("Giỏ hàng trống.")

    # ---------------------------------------------------------------- API-04
    # Đơn hàng chỉ được tạo trên một báo giá chốt còn hiệu lực. Đây là điểm
    # bảo đảm "số tiền khách bấm xác nhận == số tiền của đơn hàng" (NG-08).
    if not quote:
        frappe.throw(
            "Phiên đặt hàng đã cũ. Vui lòng mở lại giỏ hàng để cổng báo giá lại.",
            frappe.ValidationError,
        )
    bao_gia = frappe.get_doc("Portal Quote Lock", quote)
    if bao_gia.customer != customer or bao_gia.contract != contract:
        raise frappe.PermissionError("Báo giá không thuộc đơn vị của bạn.")
    if bao_gia.da_dung:
        frappe.throw(
            "Báo giá này đã được dùng để đặt một đơn hàng. Vui lòng mở lại giỏ "
            "hàng để cổng báo giá mới.",
            frappe.ValidationError,
        )
    if bao_gia.da_het_han():
        frappe.throw(
            "Báo giá đã hết hiệu lực. Vui lòng mở lại giỏ hàng để cổng báo giá mới.",
            frappe.ValidationError,
        )
    lech = bao_gia.doi_chieu(items)
    if lech:
        # Trả bảng so cũ/mới ra ngoài để giao diện dựng hộp thoại xác nhận lại,
        # thay vì âm thầm đặt theo giá mới.
        frappe.local.response["gia_lech"] = lech
        frappe.throw(
            "Giá hoặc nội dung giỏ hàng đã thay đổi so với lúc bạn xem. "
            "Vui lòng xem bảng so sánh và xác nhận lại.",
            frappe.ValidationError,
        )
```

Xoá hai dòng `if isinstance(items, str)` / `if not items` **cũ** ở phía dưới (giờ đã chuyển lên trên) để không parse hai lần.

- [ ] **Step 4: Lấy đơn giá TỪ BÁO GIÁ, không đọc lại `Item Price`**

Trong vòng lặp tạo dòng hàng, thay lời gọi `gia_ban(...)` (đã đặt ở Task 3) bằng:

```python
    # Đơn giá lấy TỪ BÁO GIÁ ĐÃ CHỐT, không đọc lại Item Price. `doi_chieu()`
    # ở trên đã bảo đảm hai nguồn khớp nhau; đọc lại ở đây chỉ mở lại đúng
    # khoảng thời gian mà NG-08 mô tả (giá đổi giữa lúc kiểm và lúc ghi).
    gia_theo_bao_gia = {r.item_code: float(r.rate) for r in bao_gia.items}
```
(đặt dòng này ngay trước vòng lặp), và trong thân vòng lặp:
```python
        rate = gia_theo_bao_gia.get(item_code)
        if rate is None:
            frappe.throw(
                f"Mặt hàng {item_code} không có trong báo giá đã chốt.",
                frappe.ValidationError,
            )
```

- [ ] **Step 5: Gắn mẫu thuế lên Sales Order (hoàn tất NG-09)**

Ngay **trước** `so.flags.ignore_permissions = True`, thêm:

```python
    # NG-09 / QĐ-02 A — gắn mẫu thuế để grand_total của Sales Order khớp với
    # tổng mà khách đã xác nhận. Không gắn thì grand_total = tiền hàng, và mọi
    # con số cổng hiển thị đều thấp hơn số phải trả.
    mau = mau_thue(customer, so.company)
    if mau:
        so.taxes_and_charges = mau
        for t in frappe.get_all(
            "Sales Taxes and Charges",
            filters={"parent": mau, "parenttype": "Sales Taxes and Charges Template"},
            fields=["charge_type", "account_head", "description", "rate",
                    "cost_center", "included_in_print_rate"],
            order_by="idx asc",
        ):
            so.append("taxes", t)
```

Thêm `mau_thue` vào dòng import từ `portal_pricing`.

- [ ] **Step 6: Đánh dấu báo giá đã dùng**

Ngay **sau** `so.insert(ignore_permissions=True)`, thêm:

```python
    bao_gia.db_set("da_dung", 1, update_modified=False)
    bao_gia.db_set("sales_order", so.name, update_modified=False)
```

và đổi câu `return`:
```python
    return {
        "sales_order": so.name,
        "total": float(so.grand_total),
        "quote": bao_gia.name,
    }
```

- [ ] **Step 7: Chạy test**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_order_place`
Expected: PASS — 7 test mới + toàn bộ test cũ.

> Test cũ nào gọi `portal_order_place` không truyền `quote` giờ sẽ fail. **Đó là đúng.**
> Sửa chúng thành: gọi `portal_quote` trước, rồi truyền `quote=bg["quote"]`. Ghi số
> lượng test phải sửa vào mục sổ theo dõi.

- [ ] **Step 8: Chạy bộ e2e và UAT**

Run:
```bash
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e2e_flow
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_uat_scenario
```
Expected: PASS sau khi sửa lời gọi tương tự.

- [ ] **Step 9: Ghi sổ theo dõi + commit**

```markdown
### NG-08 (phần 2/2) · API-04 — 2026-08-12 · commit <sha>
**Trước:** `portal_order_place(contract, items, po, delivery_date, note, address)` đọc lại đơn giá từ `Item Price` tại thời điểm đặt; không gắn `taxes_and_charges` nên `grand_total` = tiền hàng.
**Sau:** Thêm tham số `quote` (vị trí 3, bắt buộc). Từ chối khi: thiếu mã chốt · báo giá của khách khác · đã dùng · hết hạn · `doi_chieu()` phát hiện lệch (kèm `frappe.local.response["gia_lech"]` để frontend dựng bảng so cũ/mới). Đơn giá lấy **từ báo giá**, không đọc lại `Item Price`. Gắn `taxes_and_charges` + copy dòng thuế → `grand_total` khớp tổng khách đã xác nhận. Báo giá được đánh dấu `da_dung` + trỏ `sales_order`.
**Đụng vào:** `api/portal.py::portal_order_place`
**Phá vỡ:** **Đây là thay đổi phá vỡ API.** Mọi lời gọi `portal_order_place` không có `quote` sẽ bị từ chối. Frontend phải gọi `portal_quote` trước (Task 11). Số test cũ phải sửa: <ghi số>. `grand_total` của đơn mới **tăng** đúng bằng phần thuế.
**Test:** `miyano_portal/tests/test_order_place.py::TestOrderPlaceQuoteLock` — 7 test.
**Cảnh báo chồng lấn:** Task 7 (NG-04 kiểm ngày hiệu lực hợp đồng) và Task 8 (NG-01 hạn mức thật) đều chèn thêm khối kiểm vào **cùng hàm này**. Thứ tự bắt buộc: kiểm hợp đồng → kiểm báo giá → kiểm ngày → kiểm hạn mức → tạo đơn. Đừng chèn khối mới lên trên khối báo giá.
```

Cập nhật bảng tiến độ: `NG-08` ✅.

```bash
git add miyano_portal/api/portal.py miyano_portal/tests/ docs/CHANGELOG-khac-phuc-BA-v2.md
git commit -m "feat(portal): đặt hàng bắt buộc mã báo giá chốt, gắn mẫu thuế lên đơn (NG-08 API-04, NG-09)"
```

---

## Task 7: NG-02 → NG-05 — lọc hợp đồng cho đúng, và nói đúng lý do

**Files:**
- Modify: `miyano_portal/api/portal.py::portal_contracts` (dòng 128-152), `::portal_catalog`, `::portal_order_place`
- Modify: `miyano_portal/portal_context.py::remaining_qty`
- Test: `miyano_portal/tests/test_portal_contracts.py`

**Interfaces:**
- Produces: `portal_context.remaining_qty(blanket_order, item_code) -> float` — **giữ nguyên chữ ký** (Task 8 sẽ đổi ngữ nghĩa, không đổi chữ ký)
- Produces: `portal_context.trang_thai_hop_dong_item(blanket_order, item_code) -> tuple[str, float]` — trả `("co", con_lai)` · `("khong_co_trong_hop_dong", 0.0)`. Đây là chỗ tách hai lý do của NG-05.

**Bốn mã số, một hàm.** NG-02 (hợp đồng nháp), NG-03 (chưa tới ngày hiệu lực), NG-04
(hết hạn giữa lúc có giỏ hàng), NG-05 (mặt hàng bị gỡ khỏi hợp đồng) đều là điều kiện
lọc trên cùng một chuỗi `portal_contracts` → `portal_catalog` → `portal_order_place`.
Làm rời nhau nghĩa là mở cùng ba chỗ bốn lần.

**NG-05 không phải lỗi lọc — là lỗi thông điệp.** `remaining_qty` trả `0.0` khi không tìm
thấy dòng hợp đồng, nên khách nhận *"vượt hạn mức (còn 0)"* trong khi bản chất là *"mặt
hàng không còn trong hợp đồng"*. Thông báo sai bản chất khiến khách gọi điện hỏi
*"sao hết hạn mức, tôi mới đặt có 5 hộp"*. Đây là ví dụ điển hình cho UX-08.

- [ ] **Step 1: Viết test thất bại**

Tạo `miyano_portal/tests/test_portal_contracts.py`:

```python
import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api.portal import portal_contracts, portal_catalog, portal_order_place
from miyano_portal.portal_context import trang_thai_hop_dong_item
from miyano_portal.setup.seed_demo import seed_demo

BVBM = "Bệnh viện Bạch Mai"
USER_BVBM = "bvbm@demo.miyano"


class TestLocHopDong(FrappeTestCase):
    def setUp(self):
        seed_demo()
        self.hd = frappe.db.get_value(
            "Blanket Order", {"customer": BVBM, "blanket_order_type": "Selling"}, "name"
        )
        self.item = frappe.db.get_value(
            "Blanket Order Item", {"parent": self.hd}, "item_code"
        )
        self.addCleanup(frappe.set_user, "Administrator")

    def _ten_hop_dong(self):
        frappe.set_user(USER_BVBM)
        return [r["name"] for r in portal_contracts()]

    # ---------- NG-02: hợp đồng nháp ----------
    def test_hop_dong_nhap_khong_hien_tren_cong(self):
        frappe.db.set_value("Blanket Order", self.hd, "docstatus", 0, update_modified=False)
        self.assertNotIn(self.hd, self._ten_hop_dong())

    def test_hop_dong_da_ghi_so_van_hien(self):
        frappe.db.set_value("Blanket Order", self.hd, "docstatus", 1, update_modified=False)
        self.assertIn(self.hd, self._ten_hop_dong())

    # ---------- NG-03: chưa tới ngày hiệu lực ----------
    def test_hop_dong_nam_sau_khong_hien(self):
        frappe.db.set_value(
            "Blanket Order", self.hd, "from_date",
            frappe.utils.add_days(frappe.utils.today(), 30), update_modified=False,
        )
        self.assertNotIn(self.hd, self._ten_hop_dong())

    # ---------- NG-02 + NG-03 phải áp cả ở catalog ----------
    def test_catalog_tu_choi_hop_dong_nhap(self):
        frappe.db.set_value("Blanket Order", self.hd, "docstatus", 0, update_modified=False)
        frappe.set_user(USER_BVBM)
        with self.assertRaises(frappe.ValidationError):
            portal_catalog(self.hd)

    # ---------- NG-04: hết hạn giữa lúc có giỏ hàng ----------
    def test_khong_dat_duoc_tren_hop_dong_da_het_han(self):
        from miyano_portal.api.portal import portal_quote
        frappe.set_user(USER_BVBM)
        bg = portal_quote(self.hd, [{"item_code": self.item, "qty": 1}])
        # Hợp đồng hết hạn SAU khi khách đã chốt báo giá — đúng kịch bản
        # "mở cổng lúc 23h50, bấm đặt lúc 00h05".
        frappe.db.set_value(
            "Blanket Order", self.hd, "to_date",
            frappe.utils.add_days(frappe.utils.today(), -1), update_modified=False,
        )
        with self.assertRaises(frappe.ValidationError) as ctx:
            portal_order_place(
                self.hd, [{"item_code": self.item, "qty": 1}], quote=bg["quote"]
            )
        self.assertIn("hiệu lực", str(ctx.exception).lower())

    # ---------- NG-05: hai lý do, hai thông điệp ----------
    def test_mat_hang_khong_co_trong_hop_dong_bao_dung_ly_do(self):
        ly_do, con_lai = trang_thai_hop_dong_item(self.hd, "MA-KHONG-TON-TAI")
        self.assertEqual(ly_do, "khong_co_trong_hop_dong")
        self.assertEqual(con_lai, 0.0)

    def test_mat_hang_con_trong_hop_dong_bao_co(self):
        ly_do, con_lai = trang_thai_hop_dong_item(self.hd, self.item)
        self.assertEqual(ly_do, "co")

    def test_thong_bao_dat_hang_phan_biet_hai_truong_hop(self):
        from miyano_portal.api.portal import portal_quote
        frappe.set_user(USER_BVBM)
        bg = portal_quote(self.hd, [{"item_code": self.item, "qty": 1}])
        # Gỡ mặt hàng khỏi hợp đồng sau khi khách đã cho vào giỏ
        frappe.db.delete("Blanket Order Item", {"parent": self.hd, "item_code": self.item})
        with self.assertRaises(frappe.ValidationError) as ctx:
            portal_order_place(
                self.hd, [{"item_code": self.item, "qty": 1}], quote=bg["quote"]
            )
        msg = str(ctx.exception).lower()
        self.assertIn("không còn trong hợp đồng", msg)
        self.assertNotIn("vượt hạn mức", msg)
```

- [ ] **Step 2: Chạy để thấy FAIL**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_portal_contracts`
Expected: FAIL — `ImportError: cannot import name 'trang_thai_hop_dong_item'`

- [ ] **Step 3: Thêm bộ lọc cho `portal_contracts` (NG-02, NG-03)**

Trong `api/portal.py::portal_contracts`, thay khối `filters`:

```python
    rows = frappe.get_all(
        "Blanket Order",
        filters={
            "customer": customer,
            "blanket_order_type": "Selling",
            # NG-02 — hợp đồng còn đang soạn (nháp) không được hiện cho khách:
            # đó có thể là điều khoản chưa duyệt nội bộ, hoặc giá đang đàm phán.
            "docstatus": 1,
            # NG-03 — hợp đồng năm sau đã nhập trước không được đặt hôm nay.
            "from_date": ["<=", today],
            "to_date": [">=", today],
        },
        fields=["name", "from_date", "to_date"],
        order_by="to_date asc",
    )
```

- [ ] **Step 4: Thêm hàm kiểm dùng chung**

Trong `api/portal.py`, thêm trước `portal_catalog`:

```python
def _hop_dong_con_hieu_luc(contract: str, customer: str) -> frappe._dict:
    """Hợp đồng phải: thuộc khách này · đã ghi sổ · đang trong hiệu lực.

    Ba điều kiện, kiểm ở MỘT chỗ và gọi từ cả `portal_catalog` lẫn
    `portal_order_place`. Kiểm ở tầng danh sách thôi là không đủ: khách có thể
    mở cổng lúc 23h50 ngày 31/12 rồi bấm đặt lúc 00h05 ngày 01/01, hoặc để một
    tab mở qua đêm — không hiếm ở khoa dược (NG-04).
    """
    bo = frappe.db.get_value(
        "Blanket Order", contract,
        ["customer", "company", "docstatus", "from_date", "to_date"],
        as_dict=True,
    )
    if not bo or bo.customer != customer:
        raise frappe.PermissionError("Hợp đồng không thuộc đơn vị của bạn.")
    if bo.docstatus != 1:
        frappe.throw(
            "Hợp đồng này chưa được duyệt. Vui lòng chọn hợp đồng khác hoặc "
            "liên hệ nhân viên kinh doanh Miyano.",
            frappe.ValidationError,
        )
    hom_nay = frappe.utils.getdate()
    if bo.from_date and frappe.utils.getdate(bo.from_date) > hom_nay:
        frappe.throw(
            f"Hợp đồng {contract} chưa tới ngày hiệu lực "
            f"({frappe.utils.formatdate(bo.from_date)}). Vui lòng chọn hợp đồng khác.",
            frappe.ValidationError,
        )
    if bo.to_date and frappe.utils.getdate(bo.to_date) < hom_nay:
        frappe.throw(
            f"Hợp đồng {contract} đã hết hiệu lực ngày "
            f"{frappe.utils.formatdate(bo.to_date)}. Vui lòng chọn hợp đồng khác.",
            frappe.ValidationError,
        )
    return bo
```

- [ ] **Step 5: Gọi hàm đó ở cả ba endpoint**

Trong `portal_catalog`, thay:
```python
    if frappe.db.get_value("Blanket Order", contract, "customer") != customer:
        raise frappe.PermissionError("Hợp đồng không thuộc đơn vị của bạn.")
```
bằng:
```python
    bo = _hop_dong_con_hieu_luc(contract, customer)
    company = bo.company
```
(và bỏ dòng `company = frappe.db.get_value("Blanket Order", contract, "company")` đã thêm ở Task 4).

Trong `portal_quote` và `portal_order_place`, thay khối `bo = frappe.db.get_value(...)` + kiểm `bo.customer` bằng:
```python
    bo = _hop_dong_con_hieu_luc(contract, customer)
```

> **Thứ tự trong `portal_order_place`:** kiểm hợp đồng (khối này) → kiểm báo giá chốt
> (Task 6) → kiểm hạn mức (Task 8). Hợp đồng hết hạn phải báo trước "giá đã đổi" —
> nếu không khách sẽ được mời xác nhận lại một mức giá trên một hợp đồng đã chết.

- [ ] **Step 6: Tách hai lý do của NG-05**

Trong `miyano_portal/portal_context.py`, thay `remaining_qty` bằng:

```python
def trang_thai_hop_dong_item(blanket_order: str, item_code: str) -> tuple[str, float]:
    """Trả ("co", còn_lại) hoặc ("khong_co_trong_hop_dong", 0.0).

    NG-05 — bản cũ trả thẳng 0.0 cho cả hai trường hợp, nên khách nhận thông
    báo "vượt hạn mức (còn 0)" trong khi bản chất là "mặt hàng không còn trong
    hợp đồng". Thông báo sai bản chất khiến khách gọi điện hỏi "sao hết hạn
    mức, tôi mới đặt có 5 hộp". Hai trường hợp, hai thông điệp.
    """
    row = frappe.get_all(
        "Blanket Order Item",
        filters={"parent": blanket_order, "item_code": item_code},
        fields=["qty", "ordered_qty"],
        limit=1,
    )
    if not row:
        return ("khong_co_trong_hop_dong", 0.0)
    con_lai = float(row[0].qty or 0) - float(row[0].ordered_qty or 0)
    return ("co", max(con_lai, 0.0))


def remaining_qty(blanket_order: str, item_code: str) -> float:
    """Giữ lại cho các nơi gọi cũ. Mất thông tin lý do — nơi nào cần phân biệt
    thì gọi `trang_thai_hop_dong_item()`."""
    _, con_lai = trang_thai_hop_dong_item(blanket_order, item_code)
    return con_lai
```

- [ ] **Step 7: Dùng lý do đó trong `portal_order_place`**

Trong vòng lặp kiểm hạn mức, thay:
```python
        rem = remaining_qty(contract, item_code)
        if qty > rem:
            errors.append(f"{item_code}: vượt hạn mức (còn {rem:g})")
```
bằng:
```python
        ly_do, rem = trang_thai_hop_dong_item(contract, item_code)
        if ly_do == "khong_co_trong_hop_dong":
            ten = frappe.db.get_value("Item", item_code, "item_name") or item_code
            errors.append(
                f"{ten} ({item_code}): mặt hàng không còn trong hợp đồng "
                f"{contract}. Vui lòng bỏ khỏi giỏ hàng hoặc chọn hợp đồng khác."
            )
        elif qty > rem:
            errors.append(f"{item_code}: vượt hạn mức (còn {rem:g})")
```
Sửa import: `from miyano_portal.portal_context import get_portal_customer, trang_thai_hop_dong_item`

- [ ] **Step 8: Chạy test**

Run:
```bash
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_portal_contracts
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_portal_context
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_order_place
```
Expected: PASS.

> `seed_demo` có thể tạo Blanket Order ở trạng thái nháp. Nếu `test_portal_contracts`
> báo hợp đồng biến mất khỏi danh sách trên site thật, sửa `seed_demo` để `submit()`
> hợp đồng — đó là dữ liệu seed sai, không phải bộ lọc sai. Ghi vào sổ theo dõi.

- [ ] **Step 9: Ghi sổ theo dõi + commit**

```markdown
### NG-02 · NG-03 · NG-04 · NG-05 · Lọc hợp đồng và thông điệp đúng bản chất — 2026-08-12 · commit <sha>
**Trước:** `portal_contracts` lọc `customer` + `blanket_order_type` + `to_date >= today`, **không** lọc `docstatus` (NG-02) và **không** lọc `from_date` (NG-03). `portal_order_place` chỉ kiểm `bo.customer`, không kiểm ngày (NG-04). `remaining_qty` trả `0.0` cho cả "hết hạn mức" lẫn "không có trong hợp đồng" (NG-05).
**Sau:** `portal_contracts` lọc thêm `docstatus: 1` và `from_date <= today`. Hàm dùng chung `_hop_dong_con_hieu_luc(contract, customer)` kiểm ba điều kiện, gọi từ `portal_catalog`, `portal_quote` và `portal_order_place` — tức kiểm lại **tại thời điểm đặt**, không chỉ ở tầng danh sách. `trang_thai_hop_dong_item()` tách hai lý do; thông báo đặt hàng nay phân biệt "không còn trong hợp đồng" với "vượt hạn mức".
**Đụng vào:** `api/portal.py::portal_contracts` · `::_hop_dong_con_hieu_luc` (mới) · `::portal_catalog` · `::portal_quote` · `::portal_order_place` · `portal_context.py::trang_thai_hop_dong_item` (mới), `::remaining_qty` (giữ chữ ký, uỷ quyền)
**Phá vỡ:** Hợp đồng nháp / chưa hiệu lực / đã hết hạn biến mất khỏi cổng. Nếu `seed_demo` tạo Blanket Order nháp thì phải `submit()` — dữ liệu seed sai, không phải bộ lọc sai.
**Test:** `miyano_portal/tests/test_portal_contracts.py` — 8 test.
**Cảnh báo chồng lấn:** Thứ tự kiểm trong `portal_order_place` là **bắt buộc**: hợp đồng → báo giá chốt → hạn mức. Hợp đồng hết hạn phải báo trước "giá đã đổi", nếu không khách được mời xác nhận lại giá trên một hợp đồng đã chết. Task 8 sẽ đổi **ngữ nghĩa** của `remaining_qty` (trừ thêm phần giữ chỗ) nhưng **không** đổi chữ ký.
```

Cập nhật bảng tiến độ: `NG-02` `NG-03` `NG-04` `NG-05` → ✅.

```bash
git add miyano_portal/api/portal.py miyano_portal/portal_context.py \
        miyano_portal/tests/test_portal_contracts.py docs/CHANGELOG-khac-phuc-BA-v2.md
git commit -m "fix(portal): lọc hợp đồng theo docstatus và ngày hiệu lực, tách lý do hết hạn mức (NG-02..NG-05)"
```

---

## Task 8: NG-01 — giữ chỗ mềm (QĐ-01 phương án A), phần đọc

**Files:**
- Create: `miyano_portal/portal_reservation.py`
- Modify: `miyano_portal/portal_context.py::trang_thai_hop_dong_item`
- Modify: `miyano_portal/api/portal.py::portal_catalog`
- Test: `miyano_portal/tests/test_giu_cho.py`

**Interfaces:**
- Produces: `portal_reservation.GIU_CHO_NGAY_LAM_VIEC = 3`
- Produces: `portal_reservation.han_giu_cho(tu_ngay=None) -> str` — mốc `transaction_date` sớm nhất còn được tính là đang giữ chỗ
- Produces: `portal_reservation.dang_giu_cho(blanket_order, item_code=None) -> dict[str, float]` — `{item_code: qty}` từ các Sales Order **nháp** của cổng còn trong thời hạn
- Đổi ngữ nghĩa (không đổi chữ ký): `trang_thai_hop_dong_item()` nay trừ thêm phần giữ chỗ; thêm giá trị trả về thứ ba qua dict.

**Chứng minh gốc (BA v2 §NG-01, đã kiểm lại 2026-08-12).** `ordered_qty` được tính ở
`blanket_order.py:97-119` với điều kiện cứng `trans.docstatus == 1`, và hàm đó chỉ được
gọi từ `sales_order.py:431` (`on_submit`) và `:464` (`on_cancel`). `portal_order_place`
tạo đơn ở `docstatus = 0`. **Kết luận là tất yếu:** đơn chưa xác nhận không thể ảnh hưởng
`ordered_qty`, nên không thể làm giảm con số hạn mức mà cổng báo cho khách.

**QĐ-01 = A.** Cổng tự tính "hạn mức còn lại thật" = `qty − ordered_qty − đang giữ chỗ`.
**Không sửa `blanket_order.py` của ERPNext** — sửa ở đó là đổi hành vi cho toàn hệ thống,
kể cả các đơn không đến từ cổng.

**Giữ chỗ là gì, chính xác.** Một dòng `Sales Order Item` thoả **cả bốn**:
`docstatus = 0` · `Sales Order.custom_nguon_don = "Client Portal"` ·
`Sales Order Item.blanket_order = <hợp đồng>` · `Sales Order.transaction_date >= mốc 3 ngày làm việc`.
Đơn nháp do nhân viên Miyano tự lập trên Desk **không** tính là giữ chỗ của cổng — cổng
chỉ chịu trách nhiệm cho phần nó sinh ra.

- [ ] **Step 1: Viết test thất bại**

Tạo `miyano_portal/tests/test_giu_cho.py`:

```python
import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.portal_reservation import (
    GIU_CHO_NGAY_LAM_VIEC, han_giu_cho, dang_giu_cho,
)
from miyano_portal.portal_context import trang_thai_hop_dong_item
from miyano_portal.setup.seed_demo import seed_demo

BVBM = "Bệnh viện Bạch Mai"
USER_BVBM = "bvbm@demo.miyano"


class TestGiuCho(FrappeTestCase):
    def setUp(self):
        seed_demo()
        self.hd = frappe.db.get_value(
            "Blanket Order", {"customer": BVBM, "blanket_order_type": "Selling"}, "name"
        )
        self.item = frappe.db.get_value(
            "Blanket Order Item", {"parent": self.hd}, "item_code"
        )
        self.addCleanup(frappe.set_user, "Administrator")

    def _don_nhap(self, qty, ngay=None, nguon="Client Portal"):
        company = frappe.db.get_value("Blanket Order", self.hd, "company")
        so = frappe.new_doc("Sales Order")
        so.customer = BVBM
        so.company = company
        so.transaction_date = ngay or frappe.utils.today()
        so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 2)
        so.custom_nguon_don = nguon
        so.append("items", {
            "item_code": self.item, "qty": qty, "rate": 1000,
            "delivery_date": so.delivery_date,
            "blanket_order": self.hd, "against_blanket_order": 1,
        })
        so.flags.ignore_permissions = True
        so.insert(ignore_permissions=True)
        return so.name

    def test_don_nhap_cua_cong_duoc_tinh_la_giu_cho(self):
        self._don_nhap(4)
        self.assertEqual(dang_giu_cho(self.hd).get(self.item), 4)

    def test_nhieu_don_nhap_cong_don(self):
        self._don_nhap(2)
        self._don_nhap(3)
        self.assertEqual(dang_giu_cho(self.hd).get(self.item), 5)

    def test_don_nhap_cua_desk_khong_tinh_la_giu_cho(self):
        self._don_nhap(4, nguon="")
        self.assertIsNone(dang_giu_cho(self.hd).get(self.item))

    def test_don_da_ghi_so_khong_tinh_hai_lan(self):
        """Đơn đã submit đã nằm trong ordered_qty — đếm lại là trừ hai lần."""
        name = self._don_nhap(3)
        frappe.get_doc("Sales Order", name).submit()
        self.assertIsNone(dang_giu_cho(self.hd).get(self.item))

    def test_don_nhap_qua_han_khong_con_giu_cho(self):
        cu = frappe.utils.add_days(frappe.utils.today(), -30)
        self._don_nhap(4, ngay=cu)
        self.assertIsNone(dang_giu_cho(self.hd).get(self.item))

    def test_han_giu_cho_bo_qua_cuoi_tuan(self):
        """3 NGÀY LÀM VIỆC, không phải 3 ngày lịch."""
        # Thứ hai 2026-08-17 → lùi 3 ngày làm việc → thứ tư 2026-08-12
        self.assertEqual(han_giu_cho("2026-08-17"), "2026-08-12")
        self.assertEqual(GIU_CHO_NGAY_LAM_VIEC, 3)

    # ---------- hạn mức thật ----------
    def test_han_muc_con_lai_tru_phan_giu_cho(self):
        row = frappe.db.get_value(
            "Blanket Order Item", {"parent": self.hd, "item_code": self.item},
            ["qty", "ordered_qty"], as_dict=True,
        )
        con_lai_cu = float(row.qty) - float(row.ordered_qty)
        self._don_nhap(1)
        ly_do, con_lai = trang_thai_hop_dong_item(self.hd, self.item)
        self.assertEqual(ly_do, "co")
        self.assertEqual(con_lai, con_lai_cu - 1)

    def test_khong_dat_duoc_phan_da_giu_cho(self):
        from miyano_portal.api.portal import portal_quote, portal_order_place
        row = frappe.db.get_value(
            "Blanket Order Item", {"parent": self.hd, "item_code": self.item},
            ["qty", "ordered_qty"], as_dict=True,
        )
        con_lai = float(row.qty) - float(row.ordered_qty)
        self._don_nhap(con_lai)          # giữ chỗ hết phần còn lại
        frappe.set_user(USER_BVBM)
        bg = portal_quote(self.hd, [{"item_code": self.item, "qty": 1}])
        with self.assertRaises(frappe.ValidationError) as ctx:
            portal_order_place(
                self.hd, [{"item_code": self.item, "qty": 1}], quote=bg["quote"]
            )
        self.assertIn("hạn mức", str(ctx.exception).lower())

    def test_catalog_hien_cot_da_dat_chua_xac_nhan(self):
        from miyano_portal.api.portal import portal_catalog
        self._don_nhap(2)
        frappe.set_user(USER_BVBM)
        dong = [r for r in portal_catalog(self.hd) if r["item_code"] == self.item][0]
        self.assertEqual(dong["giu_cho"], 2)
        self.assertEqual(dong["remaining"], dong["total"] - dong["used"] - 2)
```

- [ ] **Step 2: Chạy để thấy FAIL**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_giu_cho`
Expected: FAIL — `ModuleNotFoundError: No module named 'miyano_portal.portal_reservation'`

- [ ] **Step 3: Viết module giữ chỗ**

Tạo `miyano_portal/portal_reservation.py`:

```python
"""Giữ chỗ mềm trên hạn mức hợp đồng — BA v2 §NG-01, QĐ-01 phương án A.

Vì sao cần. `ordered_qty` của `Blanket Order Item` được ERPNext tính với điều
kiện cứng `Sales Order.docstatus == 1` (`blanket_order.py:97-119`), và hàm đó
chỉ chạy trong `on_submit` / `on_cancel` của Sales Order. `portal_order_place`
tạo đơn ở `docstatus = 0`. Nên đơn khách vừa đặt mà Miyano chưa xác nhận là
HOÀN TOÀN VÔ HÌNH với bộ kiểm hạn mức: bệnh viện đặt liên tiếp nhiều đơn, mỗi
đơn đều "trong hạn mức", tổng cộng vượt xa hạn mức đã ký. Va chạm bị đẩy về
phía nhân viên Miyano lúc xác nhận đơn thứ hai — đúng thứ mà việc kiểm hạn mức
sinh ra để tránh.

Vì sao tính ở đây chứ không sửa ERPNext. QĐ-01 phương án A: đổi
`blanket_order.py` sẽ đổi hành vi cho MỌI đơn, kể cả đơn nhân viên tự lập trên
Desk và đơn của khách không dùng cổng. Cổng chỉ chịu trách nhiệm cho phần nó
sinh ra.

Thời hạn giữ chỗ: 3 NGÀY LÀM VIỆC (không phải 3 ngày lịch — đơn đặt chiều thứ
sáu không được nhả vào sáng thứ hai). Quá hạn thì đơn nháp vẫn còn đó, chỉ là
không giữ chỗ nữa; việc nhả và báo cho khách nằm ở `portal_reservation.nha_giu_cho`.
"""

import frappe
from frappe.utils import add_days, getdate

GIU_CHO_NGAY_LAM_VIEC = 3

# Chỉ đơn do cổng sinh ra mới được tính là giữ chỗ của cổng.
NGUON_CONG = "Client Portal"


def han_giu_cho(tu_ngay: str | None = None) -> str:
    """`transaction_date` sớm nhất còn được tính là đang giữ chỗ.

    Lùi `GIU_CHO_NGAY_LAM_VIEC` ngày LÀM VIỆC từ `tu_ngay` (mặc định hôm nay).
    Bỏ qua thứ bảy và chủ nhật: một đơn đặt chiều thứ sáu mà nhả vào sáng thứ
    hai thì khách chưa kịp thấy Miyano phản hồi đã mất chỗ.
    """
    ngay = getdate(tu_ngay or frappe.utils.today())
    con = GIU_CHO_NGAY_LAM_VIEC
    while con > 0:
        ngay = add_days(ngay, -1)
        if getdate(ngay).weekday() < 5:   # 0=T2 … 4=T6
            con -= 1
    return str(getdate(ngay))


def dang_giu_cho(blanket_order: str, item_code: str | None = None) -> dict:
    """{item_code: tổng qty} đang được giữ chỗ trên hợp đồng này.

    Bốn điều kiện, thiếu một là sai:
      - `Sales Order.docstatus = 0`      — đã submit thì nằm trong ordered_qty
                                            rồi, đếm lại là trừ hai lần
      - `custom_nguon_don = "Client Portal"` — đơn Desk không thuộc phạm vi cổng
      - `Sales Order Item.blanket_order`  — đúng hợp đồng
      - `transaction_date >= han_giu_cho()` — chưa quá 3 ngày làm việc
    """
    so = frappe.qb.DocType("Sales Order")
    soi = frappe.qb.DocType("Sales Order Item")
    q = (
        frappe.qb.from_(soi)
        .join(so).on(so.name == soi.parent)
        .select(soi.item_code, frappe.qb.functions.Sum(soi.qty).as_("qty"))
        .where(
            (soi.blanket_order == blanket_order)
            & (so.docstatus == 0)
            & (so.custom_nguon_don == NGUON_CONG)
            & (so.transaction_date >= han_giu_cho())
        )
        .groupby(soi.item_code)
    )
    if item_code:
        q = q.where(soi.item_code == item_code)
    return {r[0]: float(r[1] or 0) for r in q.run()}
```

- [ ] **Step 4: Trừ phần giữ chỗ trong `trang_thai_hop_dong_item`**

Trong `portal_context.py`, sửa hàm đã viết ở Task 7:

```python
def trang_thai_hop_dong_item(blanket_order: str, item_code: str) -> tuple[str, float]:
    """Trả ("co", còn_lại_THẬT) hoặc ("khong_co_trong_hop_dong", 0.0).

    "Thật" = hạn mức ký − đã ghi sổ − ĐANG GIỮ CHỖ trong đơn nháp của cổng
    (NG-01, QĐ-01 A). Con số ERPNext biết (`ordered_qty`) chỉ đếm phần đã ghi
    sổ; phần khách vừa đặt mà Miyano chưa xác nhận là vô hình với nó.
    """
    from miyano_portal.portal_reservation import dang_giu_cho

    row = frappe.get_all(
        "Blanket Order Item",
        filters={"parent": blanket_order, "item_code": item_code},
        fields=["qty", "ordered_qty"],
        limit=1,
    )
    if not row:
        return ("khong_co_trong_hop_dong", 0.0)
    giu = dang_giu_cho(blanket_order, item_code).get(item_code, 0.0)
    con_lai = float(row[0].qty or 0) - float(row[0].ordered_qty or 0) - giu
    return ("co", max(con_lai, 0.0))
```

- [ ] **Step 5: Thêm cột "Đã đặt nhưng chưa xác nhận" vào danh mục**

Trong `api/portal.py::portal_catalog`, trước vòng lặp:
```python
    giu_cho_map = dang_giu_cho(contract)
```
và trong dict trả về, thay `"remaining": max(total - used, 0.0),` bằng:
```python
            # BA v2 §C2 Màn 1 — khách phải thấy phần đang giữ chỗ, nếu không
            # con số "còn lại" tự nhiên nhỏ đi mà không rõ vì sao.
            "giu_cho": giu_cho_map.get(row["item_code"], 0.0),
            "remaining": max(total - used - giu_cho_map.get(row["item_code"], 0.0), 0.0),
```
Thêm import: `from miyano_portal.portal_reservation import dang_giu_cho`

- [ ] **Step 6: Chạy test**

Run:
```bash
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_giu_cho
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_order_place
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_portal_context
```
Expected: PASS — 9 test mới.

- [ ] **Step 7: Ghi sổ theo dõi + commit**

```markdown
### NG-01 (phần 1/2) · Hạn mức không tính đơn chưa xác nhận — 2026-08-12 · commit <sha>
**Quyết định:** QĐ-01 = **A** (giữ chỗ mềm, hết hạn **3 ngày làm việc**).
**Trước:** `remaining_qty` = `Blanket Order Item.qty − ordered_qty`. `ordered_qty` chỉ đếm đơn `docstatus = 1` (`blanket_order.py:97-119`, gọi từ `sales_order.py:431/464`), còn `portal_order_place` tạo đơn `docstatus = 0`. Đơn chưa xác nhận **vô hình** với bộ kiểm hạn mức; bệnh viện đặt nhiều đơn, mỗi đơn "trong hạn mức", tổng vượt xa hạn mức đã ký.
**Sau:** `portal_reservation.dang_giu_cho()` cộng số lượng trong các Sales Order **nháp** của cổng (4 điều kiện: `docstatus=0` + `custom_nguon_don="Client Portal"` + đúng `blanket_order` + `transaction_date >= han_giu_cho()`). `trang_thai_hop_dong_item()` trừ phần này. `portal_catalog` trả thêm cột `giu_cho`. **Không sửa `blanket_order.py` của ERPNext.**
**Đụng vào:** `miyano_portal/portal_reservation.py` (mới) · `portal_context.py::trang_thai_hop_dong_item` · `api/portal.py::portal_catalog`
**Phá vỡ:** `remaining` mà cổng báo cho khách **giảm xuống** đúng bằng phần đang giữ chỗ. Đây là con số đúng. Frontend phải hiện cột `giu_cho` (Task 11), nếu không khách sẽ thấy con số nhỏ đi mà không rõ vì sao.
**Test:** `miyano_portal/tests/test_giu_cho.py` — 9 test, gồm một test khẳng định `han_giu_cho` bỏ qua cuối tuần.
**Cảnh báo chồng lấn:** `remaining_qty()` giữ nguyên chữ ký nhưng **đổi ngữ nghĩa** — nay đã trừ giữ chỗ. Mọi nơi gọi nó tự động nhận con số mới. Đơn nháp do nhân viên Desk lập **cố ý không** tính là giữ chỗ. Phần nhả giữ chỗ + thông báo ở Task 9.
```

Cập nhật bảng tiến độ: `NG-01` → 🟨.

```bash
git add miyano_portal/portal_reservation.py miyano_portal/portal_context.py \
        miyano_portal/api/portal.py miyano_portal/tests/test_giu_cho.py \
        docs/CHANGELOG-khac-phuc-BA-v2.md
git commit -m "feat(portal): giữ chỗ mềm hạn mức theo đơn nháp của cổng (NG-01, QĐ-01 A)"
```

---

## Task 9: NG-01 phần 2 — nhả giữ chỗ sau 3 ngày làm việc và báo cho khách

**Files:**
- Modify: `miyano_portal/portal_reservation.py`
- Modify: `miyano_portal/hooks.py` (`scheduler_events`)
- Create: `miyano_portal/setup/install_notifications.py` — thêm mẫu "Portal - Giữ chỗ hết hạn"
- Create: `miyano_portal/patches/v1_3/install_notification_giu_cho.py`
- Modify: `miyano_portal/patches.txt`
- Test: `miyano_portal/tests/test_giu_cho.py` (mở rộng), `miyano_portal/tests/test_notifications.py`

**Interfaces:**
- Consumes: `portal_reservation.han_giu_cho()` (Task 8)
- Produces: `portal_reservation.nha_giu_cho() -> list[str]` — trả danh sách tên Sales Order vừa hết giữ chỗ. Chạy hằng ngày.

**Đơn KHÔNG bị huỷ.** Quá 3 ngày làm việc, đơn nháp vẫn nằm nguyên đó chờ Miyano xử lý —
huỷ tự động một đơn khách đã đặt là hành vi tệ hơn hẳn cái nó sửa. Chỉ có **chỗ giữ**
được nhả ra (điều này đã tự động xảy ra nhờ bộ lọc ngày ở Task 8), và **khách được báo**.
Đánh dấu bằng một trường để không báo lại mỗi ngày.

- [ ] **Step 1: Viết test thất bại**

Thêm vào `miyano_portal/tests/test_giu_cho.py`:

```python
class TestNhaGiuCho(TestGiuCho):
    def test_nha_giu_cho_danh_dau_don_qua_han(self):
        from miyano_portal.portal_reservation import nha_giu_cho
        cu = frappe.utils.add_days(frappe.utils.today(), -30)
        name = self._don_nhap(4, ngay=cu)
        ket_qua = nha_giu_cho()
        self.assertIn(name, ket_qua)
        self.assertEqual(
            frappe.db.get_value("Sales Order", name, "custom_giu_cho_het_han"), 1
        )

    def test_khong_danh_dau_don_con_han(self):
        from miyano_portal.portal_reservation import nha_giu_cho
        name = self._don_nhap(4)
        self.assertNotIn(name, nha_giu_cho())
        self.assertFalse(
            frappe.db.get_value("Sales Order", name, "custom_giu_cho_het_han")
        )

    def test_khong_bao_lai_lan_hai(self):
        """Chạy hằng ngày — không được gửi lại email mỗi sáng."""
        from miyano_portal.portal_reservation import nha_giu_cho
        cu = frappe.utils.add_days(frappe.utils.today(), -30)
        self._don_nhap(4, ngay=cu)
        lan_1 = nha_giu_cho()
        self.assertTrue(lan_1)
        self.assertEqual(nha_giu_cho(), [])

    def test_don_da_xac_nhan_khong_bi_danh_dau(self):
        from miyano_portal.portal_reservation import nha_giu_cho
        cu = frappe.utils.add_days(frappe.utils.today(), -30)
        name = self._don_nhap(4, ngay=cu)
        frappe.get_doc("Sales Order", name).submit()
        self.assertNotIn(name, nha_giu_cho())

    # ---------- THÔNG BÁO LÀ TOÀN BỘ GIÁ TRỊ CỦA TASK NÀY ----------
    def test_email_that_su_duoc_xep_hang_gui(self):
        """Không có test này thì Task 9 chỉ là "bật một ô check".

        Chỗ giữ trên hạn mức đã tự nhả nhờ bộ lọc ngày trong `dang_giu_cho()`
        từ Task 8. Việc DUY NHẤT Task 9 thêm vào là BÁO cho khách. Nếu email
        không đi thì task này không giao gì cả — và nó sẽ trông như đã xong,
        vì cờ vẫn được bật và job vẫn chạy êm.
        """
        from miyano_portal.portal_reservation import nha_giu_cho

        cu = frappe.utils.add_days(frappe.utils.today(), -30)
        name = self._don_nhap(4, ngay=cu)
        # Đơn phải có contact_email, nếu không mẫu không có người nhận.
        frappe.db.set_value(
            "Sales Order", name, "contact_email", USER_BVBM, update_modified=False
        )
        truoc = frappe.db.count("Email Queue")
        nha_giu_cho()
        self.assertGreater(
            frappe.db.count("Email Queue"), truoc,
            "không có email nào được xếp hàng — mẫu thông báo không khớp/không gửi",
        )
        gan_nhat = frappe.get_all(
            "Email Queue", fields=["message"], order_by="creation desc", limit=1
        )[0]
        self.assertIn(name, gan_nhat.message)

    def test_don_dep_bao_gia_cu_giu_lai_ban_da_dung(self):
        from miyano_portal.portal_reservation import _don_dep_bao_gia_cu
        from miyano_portal.api.portal import portal_quote

        frappe.set_user(USER_BVBM)
        bg_cu = portal_quote(self.hd, [{"item_code": self.item, "qty": 1}])
        bg_giu = portal_quote(self.hd, [{"item_code": self.item, "qty": 2}])
        frappe.set_user("Administrator")
        qua_han = frappe.utils.add_days(frappe.utils.today(), -60)
        for n in (bg_cu["quote"], bg_giu["quote"]):
            frappe.db.set_value(
                "Portal Quote Lock", n, "het_han", qua_han, update_modified=False
            )
        # Bản đã dùng để đặt hàng phải được giữ lại — đó là bằng chứng khi khách
        # thắc mắc "lúc tôi đặt giá là 78.000" (BA v2 §NG-12).
        frappe.db.set_value(
            "Portal Quote Lock", bg_giu["quote"], "da_dung", 1, update_modified=False
        )
        _don_dep_bao_gia_cu()
        self.assertFalse(frappe.db.exists("Portal Quote Lock", bg_cu["quote"]))
        self.assertTrue(frappe.db.exists("Portal Quote Lock", bg_giu["quote"]))
```

> **Lưu ý về `Email Queue` trong test.** Nếu site test chưa cấu hình outgoing email,
> Frappe vẫn tạo bản ghi `Email Queue` (trạng thái `Not Sent`) — test trên vẫn đúng.
> Nếu bench này chặn hẳn việc tạo hàng đợi trong test, đổi sang assert trên
> `frappe.flags` hoặc mock `frappe.sendmail`; **đừng bỏ test này đi**, hãy đổi cách đo.

- [ ] **Step 2: Chạy để thấy FAIL**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_giu_cho`
Expected: FAIL — `ImportError: cannot import name 'nha_giu_cho'`

- [ ] **Step 3: Thêm custom field đánh dấu**

Trong `miyano_portal/patches/v1_3/`, tạo `install_notification_giu_cho.py`:

```python
"""Trường đánh dấu đơn đã hết giữ chỗ + mẫu thông báo — BA v2 §NG-01 (QĐ-01 A)."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields({
        "Sales Order": [{
            "fieldname": "custom_giu_cho_het_han",
            "label": "Giữ chỗ hạn mức đã hết hạn",
            "fieldtype": "Check",
            "insert_after": "custom_nguon_don",
            "read_only": 1,
            "no_copy": 1,
            "description": "Đơn đặt qua cổng quá 3 ngày làm việc chưa được xác "
                           "nhận. Chỗ giữ trên hạn mức hợp đồng đã được nhả; đơn "
                           "vẫn còn hiệu lực và vẫn xác nhận được.",
        }]
    }, ignore_validate=True)

    from miyano_portal.setup.install_notifications import install_notification_giu_cho
    install_notification_giu_cho()
```

Thêm vào `patches.txt`:
```
miyano_portal.patches.v1_3.install_notification_giu_cho
```

- [ ] **Step 4: Thêm mẫu thông báo**

Trong `miyano_portal/setup/install_notifications.py`, thêm hàm:

```python
def install_notification_giu_cho():
    """Mẫu "Portal - Giữ chỗ hết hạn".

    Điều kiện lọc `custom_nguon_don == "Client Portal"` — KHÔNG để rỗng. Hai mẫu
    hiện có ("Portal - Xuất giao", "Portal - Hoá đơn phát hành") để rỗng và vì
    thế gửi cho cả khách chưa bao giờ dùng cổng (NG-42). Đừng lặp lại lỗi đó.
    """
    ten = "Portal - Giữ chỗ hết hạn"
    if frappe.db.exists("Notification", ten):
        return
    frappe.get_doc({
        "doctype": "Notification",
        "name": ten,
        "subject": "Đơn hàng {{ doc.name }} vẫn đang chờ Miyano xác nhận",
        "document_type": "Sales Order",
        # `event: "Method"` chứ KHÔNG phải "Value Change".
        #
        # "Value Change" so trường với `doc._doc_before_save`, thứ chỉ được nạp
        # bởi `load_doc_before_save()` bên trong `save()`. `nha_giu_cho()` dùng
        # `db_set()` — không đi qua `save()`, nên `_doc_before_save` là None và
        # phép so không có gì để so: mẫu sẽ KHÔNG BAO GIỜ gửi. Đó là cách
        # Task 9 âm thầm biến thành "chỉ bật một ô check".
        #
        # "Method" thì không tự chạy; `nha_giu_cho()` gọi `.send(doc)` tường minh.
        "event": "Method",
        "method": "miyano_portal.portal_reservation.nha_giu_cho",
        "condition": 'doc.custom_nguon_don == "Client Portal" and doc.custom_giu_cho_het_han',
        "channel": "Email",
        "recipients": [{"receiver_by_document_field": "contact_email"}],
        "message": (
            "Kính gửi Quý khách,\n\n"
            "Đơn hàng **{{ doc.name }}** đặt ngày {{ frappe.utils.formatdate(doc.transaction_date) }} "
            "vẫn đang chờ Miyano xác nhận sau 3 ngày làm việc.\n\n"
            "Phần hạn mức hợp đồng mà đơn này tạm giữ đã được nhả lại, nên hạn mức "
            "khả dụng trên cổng của Quý khách sẽ tăng lên tương ứng. "
            "**Đơn hàng vẫn còn hiệu lực** và vẫn sẽ được Miyano xử lý.\n\n"
            "Nếu cần gấp, xin liên hệ nhân viên kinh doanh phụ trách.\n"
        ),
    }).insert(ignore_permissions=True)
```

- [ ] **Step 5: Viết `nha_giu_cho()`**

Thêm vào `miyano_portal/portal_reservation.py`:

```python
def nha_giu_cho() -> list[str]:
    """Đánh dấu các đơn nháp của cổng đã quá thời hạn giữ chỗ. Chạy hằng ngày.

    ĐƠN KHÔNG BỊ HUỶ. Huỷ tự động một đơn khách đã đặt là hành vi tệ hơn hẳn
    cái nó sửa: khách mất đơn mà không ai quyết định gì. Chỗ giữ trên hạn mức
    đã tự nhả nhờ bộ lọc ngày trong `dang_giu_cho()`; việc duy nhất còn thiếu
    là BÁO cho khách, vì nếu không thì hạn mức trên cổng tự nhiên tăng lại mà
    không rõ lý do — đúng loại im lặng mà BA v2 §NG-07 phàn nàn.

    Cờ `custom_giu_cho_het_han` vừa là bằng chứng đã báo, vừa là chốt chặn để
    job chạy hằng ngày không gửi lại email mỗi sáng.
    """
    moc = han_giu_cho()
    ra = []
    for name in frappe.get_all(
        "Sales Order",
        filters={
            "docstatus": 0,
            "custom_nguon_don": NGUON_CONG,
            "transaction_date": ["<", moc],
            "custom_giu_cho_het_han": 0,
        },
        pluck="name",
    ):
        doc = frappe.get_doc("Sales Order", name)
        doc.db_set("custom_giu_cho_het_han", 1, update_modified=False)
        _gui_thong_bao_giu_cho(doc)
        ra.append(name)

    _don_dep_bao_gia_cu()
    return ra


def _gui_thong_bao_giu_cho(doc) -> None:
    """Gửi mẫu "Portal - Giữ chỗ hết hạn" một cách TƯỜNG MINH.

    Không dùng `doc.run_notifications()`: cơ chế "Value Change" của Frappe so
    trường với `doc._doc_before_save`, thứ chỉ được nạp bên trong `save()`.
    Đường đi ở đây là `get_doc` → `db_set`, nên `_doc_before_save` là None và
    mẫu sẽ không bao giờ khớp — job chạy êm mỗi sáng, cờ được bật, và khách
    không nhận gì cả. Đúng loại im lặng mà cả đợt này sinh ra để chặn.

    Gửi hỏng thì KHÔNG được làm đổ job: các đơn còn lại vẫn phải được xử lý.
    """
    try:
        frappe.get_doc("Notification", "Portal - Giữ chỗ hết hạn").send(doc)
    except Exception:
        frappe.log_error(
            title="Cổng khách: không gửi được thông báo giữ chỗ hết hạn",
            message=frappe.get_traceback(with_context=True),
            reference_doctype="Sales Order",
            reference_name=doc.name,
        )


# Báo giá chốt được sinh mỗi lần giỏ hàng đổi (debounce 400ms ở giao diện), nên
# một phiên mua hàng để lại hàng chục bản ghi. Dọn phần KHÔNG dùng tới; giữ lại
# `da_dung = 1` vĩnh viễn vì đó chính là thứ trả lời câu "lúc tôi đặt giá là
# 78.000" mà BA v2 §NG-12 nêu.
BAO_GIA_GIU_NGAY = 30


def _don_dep_bao_gia_cu() -> int:
    moc = frappe.utils.add_days(frappe.utils.today(), -BAO_GIA_GIU_NGAY)
    ten = frappe.get_all(
        "Portal Quote Lock",
        filters={"da_dung": 0, "het_han": ["<", moc]},
        pluck="name",
    )
    for n in ten:
        frappe.delete_doc(
            "Portal Quote Lock", n, ignore_permissions=True, delete_permanently=True
        )
    return len(ten)
```

- [ ] **Step 6: Đăng ký job hằng ngày**

Trong `miyano_portal/hooks.py`, thêm (hoặc bổ sung vào `scheduler_events` đã có):

```python
scheduler_events = {
	"daily": [
		# BA v2 §NG-01 / QĐ-01 A — nhả giữ chỗ hạn mức của đơn nháp quá 3 ngày
		# làm việc và báo cho khách. Đơn KHÔNG bị huỷ.
		"miyano_portal.portal_reservation.nha_giu_cho",
	],
}
```

- [ ] **Step 7: Migrate và chạy test**

Run:
```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_giu_cho
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_notifications
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_custom_fields
```
Expected: PASS — 13 test trong `test_giu_cho`.

- [ ] **Step 8: Kiểm mẫu thông báo có điều kiện lọc (chống lặp lại NG-42)**

Thêm vào `miyano_portal/tests/test_notifications.py`:

```python
    def test_mau_giu_cho_co_dieu_kien_loc_nguon_don(self):
        """NG-42: hai mẫu cũ để condition rỗng nên gửi cho cả khách không dùng
        cổng. Mẫu mới không được lặp lại lỗi đó."""
        dk = frappe.db.get_value("Notification", "Portal - Giữ chỗ hết hạn", "condition")
        self.assertIn("Client Portal", dk or "")
```

- [ ] **Step 9: Ghi sổ theo dõi + commit**

```markdown
### NG-01 (phần 2/2) · Nhả giữ chỗ sau 3 ngày làm việc — 2026-08-12 · commit <sha>
**Trước:** Không có gì — phần 1 chỉ tính giữ chỗ, chưa nhả và chưa báo.
**Sau:** Job `daily` gọi `portal_reservation.nha_giu_cho()`: đánh dấu `Sales Order.custom_giu_cho_het_han = 1` cho đơn nháp của cổng có `transaction_date < han_giu_cho()`, rồi gửi mẫu "Portal - Giữ chỗ hết hạn" **tường minh** qua `Notification.send(doc)`. **Đơn không bị huỷ.** Cờ vừa là bằng chứng đã báo vừa là chốt chặn chống gửi lại mỗi sáng. Job cũng dọn `Portal Quote Lock` chưa dùng quá 30 ngày.
**Đụng vào:** `portal_reservation.py::nha_giu_cho`, `::_gui_thong_bao_giu_cho`, `::_don_dep_bao_gia_cu` · `hooks.py::scheduler_events` · `setup/install_notifications.py::install_notification_giu_cho` · `patches/v1_3/install_notification_giu_cho.py` (mới, thêm custom field `custom_giu_cho_het_han`) · `patches.txt`
**Phá vỡ:** Thêm một custom field trên `Sales Order`. Thêm một mẫu Notification (thứ 6).
**Test:** `miyano_portal/tests/test_giu_cho.py::TestNhaGiuCho` — 6 test · `test_notifications.py` — 1 test.
**Cảnh báo chồng lấn:** Mẫu dùng `event: "Method"`, **không** `"Value Change"`. Lý do: "Value Change" so với `doc._doc_before_save`, thứ chỉ được nạp bên trong `save()`; `nha_giu_cho()` dùng `db_set()` nên giá trị đó là `None` và mẫu **không bao giờ khớp** — job chạy êm, cờ được bật, khách không nhận gì. Nếu ai đổi lại sang "Value Change" thì task này lặng lẽ trở thành "chỉ bật một ô check". Test `test_email_that_su_duoc_xep_hang_gui` là chốt chặn cho đúng chuyện đó.
Mẫu thông báo mới **có** `condition` lọc `custom_nguon_don == "Client Portal"`. Hai mẫu cũ ("Portal - Xuất giao", "Portal - Hoá đơn phát hành") vẫn để rỗng — đó là **NG-42, chưa sửa**, xếp đợt 5. Đừng copy hai mẫu đó làm khuôn.
**Dọn dữ liệu:** `Portal Quote Lock` sinh ra hàng chục bản ghi mỗi phiên mua hàng (debounce 400ms). Job xoá bản `da_dung = 0` đã quá hạn > 30 ngày; bản `da_dung = 1` **giữ vĩnh viễn** vì đó là bằng chứng trả lời "lúc tôi đặt giá là 78.000".
```

Cập nhật bảng tiến độ: `NG-01` → ✅.

```bash
git add miyano_portal/portal_reservation.py miyano_portal/hooks.py \
        miyano_portal/setup/install_notifications.py miyano_portal/patches \
        miyano_portal/tests/ docs/CHANGELOG-khac-phuc-BA-v2.md
git commit -m "feat(portal): nhả giữ chỗ hạn mức sau 3 ngày làm việc và báo cho khách (NG-01)"
```

---

## Task 10: NG-31 — huỷ phiếu giao mà kho khách không đảo được, không được im lặng

**Files:**
- Modify: `miyano_portal/kho/delivery_hook.py:40-84`, `:201-232`
- Create: `miyano_portal/kho/doi_soat.py`
- Modify: `miyano_portal/miyano_portal/doctype/customer_stock_receipt/customer_stock_receipt.json` (thêm `dn_da_huy`)
- Modify: `miyano_portal/api/kho.py` (thêm `kho_doi_soat_phieu_mo_coi`)
- Test: `miyano_portal/tests/test_kho_delivery_hook.py` (mở rộng)

**Interfaces:**
- Produces: `kho.doi_soat.ghi_nhan_dao_that_bai(dn, receipt_name, loi) -> None` — dựng ba lớp báo động
- Produces: `kho.doi_soat.phieu_nhap_mo_coi(kho=None) -> list[dict]` — mọi phiếu nhập đã ghi sổ mà phiếu giao nguồn đã bị huỷ
- Produces: `@frappe.whitelist() kho_doi_soat_phieu_mo_coi() -> list[dict]` = API-08

**Đây không phải lỗi lập trình — là hai quy tắc đúng va nhau.** BA v2 §NG-31 nói rõ:
BR-K12 (móc không được chặn việc giao hàng) và BR-K8 (không cho đảo làm âm tồn) đều cần
thiết, nhưng chưa ai định nghĩa chuyện gì xảy ra khi chúng gặp nhau.

Chuỗi sự kiện đầy đủ:
```
Miyano giao 200 hộp  →  thủ kho ghi sổ phiếu nhập  →  bệnh viện xuất 150 hộp dùng
                     →  Miyano phát hiện giao nhầm, huỷ phiếu giao
                     →  hook chạy → cancel() → BR-K8 chặn (đã xuất mất 150)
                     →  _chay_an_toan nuốt lỗi, quay lui
                     →  KẾT QUẢ: phiếu giao ĐÃ HUỶ bên Miyano
                                 phiếu nhập VẪN GHI SỔ bên bệnh viện
                                 200 hộp vẫn nằm trong sổ kho bệnh viện
```

**Việc nuốt lỗi phải giữ nguyên.** BR-K12 là đúng: một móc không được làm vỡ việc giao
hàng của Miyano. Cái sai là **sự im lặng**. Ba lớp theo BA v2:
1. Việc cần xử lý cho nhân viên kinh doanh phụ trách
2. Cờ cảnh báo trên phiếu nhập của bệnh viện
3. Báo cáo đối soát chạy được bất cứ lúc nào

- [ ] **Step 1: Viết test thất bại**

Thêm vào `miyano_portal/tests/test_kho_delivery_hook.py`:

```python
class TestDaoThatBaiKhongImLang(FrappeTestCase):
    """BA v2 §NG-31 — huỷ DN mà kho khách không đảo được thì phải BÁO."""

    def setUp(self):
        seed_demo()
        # dựng: DN đã submit → phiếu nhập tự sinh → thủ kho ghi sổ → xuất bớt
        self.dn, self.receipt = self._giao_va_ghi_so(so_luong=200)
        self._xuat_bot(150)

    def test_phieu_nhap_van_ghi_so_sau_khi_huy_dn(self):
        """Hành vi hiện tại, giữ nguyên: BR-K12 không cho móc làm vỡ DN."""
        frappe.get_doc("Delivery Note", self.dn).cancel()
        self.assertEqual(
            frappe.db.get_value("Customer Stock Receipt", self.receipt, "docstatus"), 1
        )

    def test_sinh_viec_can_xu_ly_cho_nhan_vien(self):
        frappe.get_doc("Delivery Note", self.dn).cancel()
        todo = frappe.get_all(
            "ToDo",
            filters={"reference_type": "Delivery Note", "reference_name": self.dn},
            fields=["description", "status"],
        )
        self.assertTrue(todo, "không có việc cần xử lý nào được sinh ra")
        self.assertIn(self.receipt, todo[0].description)

    def test_danh_dau_co_canh_bao_tren_phieu_nhap(self):
        frappe.get_doc("Delivery Note", self.dn).cancel()
        self.assertEqual(
            frappe.db.get_value("Customer Stock Receipt", self.receipt, "dn_da_huy"), 1
        )

    def test_bao_cao_doi_soat_liet_ke_phieu_mo_coi(self):
        from miyano_portal.kho.doi_soat import phieu_nhap_mo_coi
        frappe.get_doc("Delivery Note", self.dn).cancel()
        rows = phieu_nhap_mo_coi()
        self.assertIn(self.receipt, [r["phieu_nhap"] for r in rows])

    def test_dao_thanh_cong_thi_khong_bao_dong_gi(self):
        """Chưa xuất gì → đảo được → không sinh ToDo, không bật cờ."""
        dn2, receipt2 = self._giao_va_ghi_so(so_luong=50)
        frappe.get_doc("Delivery Note", dn2).cancel()
        self.assertEqual(
            frappe.db.get_value("Customer Stock Receipt", receipt2, "docstatus"), 2
        )
        self.assertFalse(
            frappe.db.get_value("Customer Stock Receipt", receipt2, "dn_da_huy")
        )
        self.assertFalse(frappe.get_all(
            "ToDo", filters={"reference_type": "Delivery Note", "reference_name": dn2}
        ))

    def test_api_doi_soat_chi_tra_kho_cua_minh(self):
        from miyano_portal.api.kho import kho_doi_soat_phieu_mo_coi
        frappe.get_doc("Delivery Note", self.dn).cancel()
        self.addCleanup(frappe.set_user, "Administrator")
        frappe.set_user("bvbm@demo.miyano")
        rows = kho_doi_soat_phieu_mo_coi()
        kho_minh = frappe.db.get_value(
            "Customer Warehouse", {"customer": "Bệnh viện Bạch Mai"}, "name"
        )
        for r in rows:
            self.assertEqual(r["kho"], kho_minh)
```

> Tách hai hàm dựng `_giao_va_ghi_so()` và `_xuat_bot()` ra `tests/helpers_kho.py`
> nếu chúng đã tồn tại dưới dạng khác trong file này — đừng viết bản sao thứ hai.

- [ ] **Step 2: Chạy để thấy FAIL**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_delivery_hook`
Expected: FAIL — không có ToDo, không có trường `dn_da_huy`, không có module `doi_soat`.

- [ ] **Step 3: Thêm trường cờ cảnh báo**

Trong `customer_stock_receipt.json`, thêm vào `field_order` (sau `delivery_note`) và vào `fields`:

```json
{
 "fieldname": "dn_da_huy",
 "fieldtype": "Check",
 "label": "Phiếu giao nguồn đã bị huỷ",
 "read_only": 1,
 "no_copy": 1,
 "description": "Miyano đã huỷ phiếu giao hàng nguồn nhưng phiếu nhập này không đảo được (hàng đã xuất mất một phần). Hai sổ đang lệch nhau — vui lòng liên hệ Miyano."
}
```

- [ ] **Step 4: Viết module đối soát**

Tạo `miyano_portal/kho/doi_soat.py`:

```python
"""Đối soát phiếu nhập với phiếu giao nguồn — BA v2 §NG-31.

Khi Miyano huỷ một Delivery Note mà phiếu nhập tương ứng bên kho bệnh viện
KHÔNG đảo được (BR-K8 chặn vì hàng đã bị xuất mất), `_chay_an_toan` nuốt lỗi và
quay lui — đúng theo BR-K12, và việc nuốt lỗi đó phải giữ nguyên. Cái sai là sự
IM LẶNG: hai sổ lệch nhau, dấu vết duy nhất là một dòng Error Log mà thủ kho
không có quyền xem và nhân viên Miyano không có lý do để mở. Phát hiện ra khi
kiểm kê, có thể vài tháng sau.

Ba lớp báo động, không lớp nào thay được lớp nào:
  1. ToDo cho nhân viên kinh doanh — người DUY NHẤT xử lý tay được
  2. Cờ trên phiếu nhập — thủ kho nhìn thấy ngay trên chứng từ của mình
  3. Báo cáo đối soát — chạy được bất cứ lúc nào, không phụ thuộc ai còn nhớ
"""

import frappe


def ghi_nhan_dao_that_bai(dn, receipt_name: str, loi: str) -> None:
    """Dựng ba lớp báo động. TUYỆT ĐỐI không được ném lỗi ra ngoài.

    Hàm này chạy bên trong `except` của `_chay_an_toan`. Nếu nó ném thì lỗi sẽ
    thoát ra Delivery Note — đúng thứ mà BR-K12 sinh ra để chặn, và tệ hơn hẳn
    tình trạng im lặng mà nó đang sửa.
    """
    try:
        frappe.db.set_value(
            "Customer Stock Receipt", receipt_name, "dn_da_huy", 1,
            update_modified=False,
        )
    except Exception:
        pass

    try:
        kho = frappe.db.get_value("Customer Stock Receipt", receipt_name, "kho")
        nguoi = _nhan_vien_phu_trach(dn)
        frappe.get_doc({
            "doctype": "ToDo",
            "allocated_to": nguoi,
            "reference_type": "Delivery Note",
            "reference_name": dn.name,
            "priority": "High",
            "status": "Open",
            "description": (
                f"<b>Kho khách không đảo được — cần xử lý tay.</b><br><br>"
                f"Phiếu giao <b>{dn.name}</b> đã huỷ, nhưng phiếu nhập "
                f"<b>{receipt_name}</b> của kho <b>{kho}</b> vẫn đang ghi sổ: "
                f"bệnh viện đã xuất mất một phần số hàng đó nên không đảo được "
                f"(BR-K8).<br><br>"
                f"Hai sổ hiện lệch nhau. Cần liên hệ thủ kho bệnh viện để thống "
                f"nhất cách xử lý (lập phiếu xuất điều chỉnh, hoặc giữ nguyên và "
                f"ghi nhận chênh lệch).<br><br>"
                f"<i>Lỗi gốc: {frappe.utils.cstr(loi)[:500]}</i>"
            ),
        }).insert(ignore_permissions=True)
    except Exception:
        # Không có người phụ trách, ToDo doctype hỏng, transaction đang lỗi…
        # Lớp 1 mất thì lớp 2 và 3 vẫn còn. Không được ném.
        pass


def _nhan_vien_phu_trach(dn) -> str:
    """Người nhận việc: `sales_person` của DN → owner của DN → Administrator."""
    nguoi = None
    for row in (dn.get("sales_team") or []):
        nguoi = frappe.db.get_value("Sales Person", row.sales_person, "email")
        if nguoi:
            break
    return nguoi or dn.owner or "Administrator"


def phieu_nhap_mo_coi(kho: str | None = None) -> list[dict]:
    """Mọi phiếu nhập ĐÃ GHI SỔ mà phiếu giao nguồn đã bị huỷ.

    Không đọc cờ `dn_da_huy` mà đối chiếu thẳng `docstatus` của Delivery Note:
    cờ có thể chưa được bật (lớp 1 và 2 chạy trong `except` và có thể trượt),
    còn phép đối chiếu này thì luôn đúng. Đó là lý do báo cáo là lớp thứ ba chứ
    không phải một cách hiển thị của lớp thứ hai.
    """
    return frappe.db.sql(
        """
        select csr.name           as phieu_nhap,
               csr.kho            as kho,
               csr.ngay           as ngay,
               csr.delivery_note  as phieu_giao,
               csr.tong_tien      as tong_tien,
               csr.dn_da_huy      as da_canh_bao
        from `tabCustomer Stock Receipt` csr
        join `tabDelivery Note` dn on dn.name = csr.delivery_note
        where csr.docstatus = 1
          and dn.docstatus = 2
          and (%(kho)s is null or csr.kho = %(kho)s)
        order by csr.ngay desc
        """,
        {"kho": kho},
        as_dict=True,
    )
```

- [ ] **Step 5: Gọi lớp báo động từ `_chay_an_toan`**

`_chay_an_toan` là hàm chung cho cả `on_submit` lẫn `on_cancel`, nên không tự biết
phiếu nhập nào thất bại. Truyền thông tin đó vào qua một callback.

Trong `kho/delivery_hook.py`, sửa `on_delivery_note_cancel`:

```python
def on_delivery_note_cancel(doc, method=None):
	_chay_an_toan(
		doc, _huy_theo_delivery_note,
		"Kho khách: lỗi khi huỷ phiếu nhập theo Delivery Note",
		khi_that_bai=_bao_dong_dao_that_bai,
	)
```

Thêm hàm:

```python
def _bao_dong_dao_that_bai(dn, loi) -> None:
	"""BA v2 §NG-31 — nuốt lỗi thì giữ nguyên, im lặng thì không.

	Chạy SAU khi `_chay_an_toan` đã rollback về savepoint, nên mọi thứ nó ghi
	là ghi mới trên một transaction sạch.
	"""
	from miyano_portal.kho.doi_soat import ghi_nhan_dao_that_bai

	for name in frappe.get_all(
		"Customer Stock Receipt",
		filters={"delivery_note": dn.name, "docstatus": 1},
		pluck="name",
	):
		ghi_nhan_dao_that_bai(dn, name, loi)
```

Sửa `_chay_an_toan` để nhận và gọi callback:

```python
def _chay_an_toan(doc, fn, title: str, khi_that_bai=None) -> None:
	so_message = len(getattr(frappe.local, "message_log", []) or [])
	frappe.db.savepoint(_SAVEPOINT)
	try:
		fn(doc)
	except Exception as loi:
		try:
			frappe.db.rollback(save_point=_SAVEPOINT)
		except Exception:
			pass
		try:
			del frappe.local.message_log[so_message:]
		except Exception:
			pass
		try:
			frappe.log_error(
				title=title,
				message=frappe.get_traceback(with_context=True),
				reference_doctype=doc.doctype,
				reference_name=doc.name,
			)
		except Exception:
			pass
		# BA v2 §NG-31 — lớp báo động chạy SAU rollback, trên transaction sạch.
		# Bản thân nó không bao giờ được ném (xem ghi_nhan_dao_that_bai).
		if khi_that_bai:
			try:
				khi_that_bai(doc, loi)
			except Exception:
				pass
```

- [ ] **Step 6: Thêm endpoint API-08**

Trong `miyano_portal/api/kho.py`:

```python
@frappe.whitelist()
def kho_doi_soat_phieu_mo_coi() -> list:
    """API-08 — phiếu nhập đã ghi sổ mà phiếu giao nguồn đã bị huỷ.

    Kho suy TỪ PHIÊN ĐĂNG NHẬP, không nhận từ client — đúng nguyên tắc của mọi
    endpoint kho trong app này.
    """
    from miyano_portal.kho.doi_soat import phieu_nhap_mo_coi

    return phieu_nhap_mo_coi(kho=get_portal_kho())
```

- [ ] **Step 7: Migrate và chạy test**

Run:
```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_delivery_hook
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_isolation
```
Expected: PASS — 6 test mới, không regression.

- [ ] **Step 8: Ghi sổ theo dõi + commit**

```markdown
### NG-31 · Huỷ phiếu giao nhưng kho bệnh viện không đảo được, âm thầm — 2026-08-12 · commit <sha>
**Trước:** `_huy_theo_delivery_note` gọi `phieu.cancel()`; `before_cancel` → `_chan_neu_dao_lam_am_ton()` ném lỗi khi hàng đã bị xuất mất (BR-K8); `_chay_an_toan` nuốt lỗi, rollback, ghi Error Log, **không báo ai**. Kết quả: DN đã huỷ bên Miyano, phiếu nhập vẫn ghi sổ bên bệnh viện, hai sổ lệch nhau. Dấu vết duy nhất là Error Log mà thủ kho không có quyền xem.
**Sau:** Việc nuốt lỗi **giữ nguyên** (BR-K12 vẫn đúng). Thêm ba lớp báo động chạy sau rollback trên transaction sạch: **(1)** `ToDo` ưu tiên High cho nhân viên kinh doanh phụ trách (`sales_team.sales_person.email` → `dn.owner` → Administrator), mô tả rõ phiếu nào, kho nào, lỗi gốc là gì; **(2)** cờ `Customer Stock Receipt.dn_da_huy` hiện trên chứng từ của thủ kho; **(3)** `doi_soat.phieu_nhap_mo_coi()` đối chiếu thẳng `docstatus` của DN (không đọc cờ) + endpoint `kho_doi_soat_phieu_mo_coi` = API-08.
**Đụng vào:** `kho/delivery_hook.py::_chay_an_toan` (thêm tham số `khi_that_bai`), `::on_delivery_note_cancel`, `::_bao_dong_dao_that_bai` (mới) · `kho/doi_soat.py` (mới) · `customer_stock_receipt.json` (thêm `dn_da_huy`) · `api/kho.py::kho_doi_soat_phieu_mo_coi` (mới)
**Phá vỡ:** Không. `_chay_an_toan` vẫn không bao giờ ném; tham số `khi_that_bai` mặc định `None` nên `on_delivery_note_submit` không đổi hành vi.
**Test:** `miyano_portal/tests/test_kho_delivery_hook.py::TestDaoThatBaiKhongImLang` — 6 test, gồm một test khẳng định đảo **thành công** thì không sinh báo động nào.
**Cảnh báo chồng lấn:** `ghi_nhan_dao_that_bai` chạy trong `except` — **tuyệt đối không được ném**, mọi thao tác bọc `try/except: pass`. Báo cáo (lớp 3) **cố ý không** đọc cờ `dn_da_huy` mà đối chiếu `docstatus` của DN, vì lớp 1 và 2 có thể trượt. NG-32 (phiếu nháp mồ côi) **đang đúng** — không đụng.
```

Cập nhật bảng tiến độ: `NG-31` → ✅.

```bash
git add miyano_portal/kho/delivery_hook.py miyano_portal/kho/doi_soat.py \
        miyano_portal/miyano_portal/doctype/customer_stock_receipt \
        miyano_portal/api/kho.py miyano_portal/tests/test_kho_delivery_hook.py \
        docs/CHANGELOG-khac-phuc-BA-v2.md
git commit -m "fix(kho): huỷ phiếu giao mà không đảo được thì báo động ba lớp (NG-31, API-08)"
```

---

## Task 11: Frontend — giỏ hàng dùng báo giá chốt, danh mục hiện phần giữ chỗ

**Files:**
- Modify: `frontend/src/api.js` (thêm `quoteCart`)
- Modify: `frontend/src/store.js` (bỏ `cartVat` tính ở trình duyệt)
- Modify: `frontend/src/views/Cart.vue`
- Modify: `frontend/src/views/Catalog.vue`
- Test: thủ công theo kịch bản ở Step 6 (cổng chưa có bộ test frontend tự động — xem ghi chú)

**Interfaces:**
- Consumes: `portal_quote` (Task 5), `portal_order_place(quote=...)` (Task 6), `portal_catalog` trả thêm `giu_cho` và `vat_pct` thật (Task 4, 8)

**Điều phải bỏ.** `store.js:30-36` đang tự tính `cartVat` ở trình duyệt bằng
`qty × rate × vat_pct / 100`, và `Cart.vue:195` hiển thị dòng `VAT (5–8%)`. Cả hai phải
đi. **Tổng kết giỏ hàng từ nay do máy chủ tính** — đó là toàn bộ nội dung của NG-08.
Giữ lại phép tính phía trình duyệt nghĩa là vẫn còn hai nguồn sự thật.

- [ ] **Step 1: Thêm lời gọi API**

Trong `frontend/src/api.js`, thêm:

```js
// Chốt giá cho giỏ hàng hiện tại. Máy chủ tính tạm tính / thuế / tổng và trả
// về một mã chốt có thời hạn. Đặt hàng bắt buộc phải kèm mã này (NG-08).
export async function quoteCart(contract, items) {
  return call('portal_quote', { contract, items: JSON.stringify(items) })
}
```

- [ ] **Step 2: Bỏ phép tính thuế phía trình duyệt**

Trong `frontend/src/store.js`, xoá getter `cartVat` và `cartTotal`, thay bằng state do máy chủ cấp:

```js
  // Tổng kết KHÔNG còn tính ở trình duyệt. Máy chủ trả về qua portal_quote và
  // đó là con số duy nhất khách được nhìn thấy trước khi xác nhận (NG-08).
  // Hai nguồn sự thật cho cùng một tổng tiền chính là lỗi đang sửa.
  baoGia: null,          // { quote, het_han, tam_tinh, thue_pct, thue, tong, dong }
  baoGiaDangTai: false,
  giaLech: null,         // bảng so cũ/mới khi máy chủ từ chối

  get cartSubtotal() {
    return this.baoGia ? this.baoGia.tam_tinh
      : this.cartLines.reduce((a, l) => a + l.qty * l.rate, 0)
  },
```

> `cartSubtotal` giữ nhánh lùi để giỏ hàng vẫn hiện một con số **tạm tính** trong lúc
> chờ báo giá. Nhãn của nó phải ghi rõ "tạm tính" và tổng cộng thì **chỉ** hiện khi đã
> có `baoGia` — không bao giờ đoán tổng cộng ở trình duyệt.

- [ ] **Step 3: Giỏ hàng — chốt giá rồi mới cho xác nhận**

Trong `frontend/src/views/Cart.vue`:

Thay khối tổng kết (quanh dòng 195) bằng:
```html
<div v-if="store.baoGiaDangTai" class="sb"><span>Đang lấy báo giá…</span></div>
<template v-else-if="store.baoGia">
  <div class="sb"><span>Tạm tính</span><b>{{ fmtVND(store.baoGia.tam_tinh) }}</b></div>
  <div class="sb" v-if="store.baoGia.thue_pct">
    <span>VAT {{ store.baoGia.thue_pct }}%</span><b>{{ fmtVND(store.baoGia.thue) }}</b>
  </div>
  <div class="sb total"><span>Tổng cộng</span><b>{{ fmtVND(store.baoGia.tong) }}</b></div>
  <div class="hint">Giá có hiệu lực đến {{ gioHetHan }}</div>
</template>
<div v-else class="sb"><span>Tạm tính</span><b>{{ fmtVND(store.cartSubtotal) }}</b></div>
```

Gọi chốt giá khi giỏ hàng đổi (debounce 400ms) và khi mở màn:
```js
let hen = null
function chotGia() {
  clearTimeout(hen)
  hen = setTimeout(async () => {
    if (!store.cartLines.length) { store.baoGia = null; return }
    store.baoGiaDangTai = true
    try {
      store.baoGia = await quoteCart(
        store.contract,
        store.cartLines.map(l => ({ item_code: l.item_code, qty: l.qty })),
      )
      store.giaLech = null
    } catch (e) {
      store.baoGia = null
      toastLoi(e)
    } finally {
      store.baoGiaDangTai = false
    }
  }, 400)
}
watch(() => store.cartLines.map(l => `${l.item_code}:${l.qty}`).join('|'), chotGia,
      { immediate: true })
```

- [ ] **Step 4: Xác nhận đặt hàng — gửi mã chốt, xử lý bảng so cũ/mới**

```js
async function datHang() {
  if (!store.baoGia) return
  dangGui.value = true                       // UX-10: khoá nút, đổi chữ
  try {
    const kq = await call('portal_order_place', {
      contract: store.contract,
      items: JSON.stringify(store.cartLines.map(l => ({
        item_code: l.item_code, qty: l.qty,
      }))),
      quote: store.baoGia.quote,
      po: store.po, delivery_date: store.ngayGiao,
      note: store.ghiChu, address: store.diaChi,
    })
    store.clearCart(); store.baoGia = null
    router.push(`/don-hang/${kq.sales_order}`)
  } catch (e) {
    // Máy chủ trả bảng so cũ/mới trong response khi giá đã đổi (NG-08).
    if (e.giaLech) {
      store.giaLech = e.giaLech      // mở hộp thoại so sánh, buộc xác nhận lại
      chotGia()                       // chốt lại theo giá mới
    } else {
      toastLoi(e)
    }
  } finally {
    dangGui.value = false
  }
}
```

Để `e.giaLech` tới được đây, trong `api.js::callUrl` thêm ngay trước `throw err`:
```js
    // NG-08 — máy chủ đính bảng so cũ/mới vào response khi từ chối vì giá đổi.
    if (data && data.gia_lech) err.giaLech = data.gia_lech
```

Hộp thoại so sánh (UX-09: đặt hàng thì **có** xác nhận, kèm tổng tiền và tên hợp đồng):
```html
<dialog v-if="store.giaLech" open class="modal">
  <h3>Giá đã thay đổi so với lúc bạn xem</h3>
  <table>
    <thead><tr><th>Mặt hàng</th><th>Giá cũ</th><th>Giá mới</th><th>Lý do</th></tr></thead>
    <tbody>
      <tr v-for="d in store.giaLech" :key="d.item_code">
        <td>{{ d.item_name || d.item_code }}</td>
        <td class="num">{{ d.gia_cu == null ? '—' : fmtVND(d.gia_cu) }}</td>
        <td class="num">{{ d.gia_moi == null ? '—' : fmtVND(d.gia_moi) }}</td>
        <td>{{ nhanLyDo(d.ly_do) }}</td>
      </tr>
    </tbody>
  </table>
  <p>Tổng mới: <b>{{ store.baoGia ? fmtVND(store.baoGia.tong) : '…' }}</b></p>
  <button @click="store.giaLech = null">Xem lại giỏ hàng</button>
  <button class="primary" :disabled="!store.baoGia"
          @click="store.giaLech = null; datHang()">Xác nhận theo giá mới</button>
</dialog>
```
```js
const NHAN_LY_DO = {
  gia_doi: 'Đơn giá đã thay đổi',
  so_luong_doi: 'Số lượng trong giỏ đã thay đổi',
  them_moi: 'Mặt hàng thêm sau khi báo giá',
  da_bo: 'Mặt hàng đã bỏ khỏi giỏ',
}
const nhanLyDo = (m) => NHAN_LY_DO[m] || m
```

- [ ] **Step 5: Danh mục — cột "Đã đặt nhưng chưa xác nhận"**

Trong `frontend/src/views/Catalog.vue`, thêm cột và sửa nhãn hạn mức:
```html
<td class="num" :title="'Đang giữ chỗ trong đơn chờ Miyano xác nhận'">
  {{ r.giu_cho ? fmtSo(r.giu_cho) : '—' }}
</td>
<td class="num">
  còn {{ fmtSo(r.remaining) }}/{{ fmtSo(r.total) }} {{ r.uom }}
  <div class="bar"><i :style="{width: pct(r) + '%'}"
       :class="{ canh: pct(r) >= 80 }"></i></div>
</td>
```
Tiêu đề cột: `Đã đặt, chờ xác nhận`. Thêm chú thích dưới bảng:
> *Hạn mức còn lại đã trừ cả phần đang chờ Miyano xác nhận. Đơn chưa được xác nhận sau 3 ngày làm việc sẽ tự nhả lại phần giữ chỗ.*

- [ ] **Step 6: Build và thử tay theo bảy kịch bản**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal/frontend && yarn build
cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local clear-cache
```

Đăng nhập `bvbm@demo.miyano` và kiểm:

| # | Kịch bản | Kỳ vọng |
|---|---|---|
| 1 | Thêm hàng vào giỏ | Tổng kết hiện "Đang lấy báo giá…" rồi ra tạm tính / VAT / tổng cộng + "Giá có hiệu lực đến hh:mm" |
| 2 | Đổi số lượng | Báo giá tự chốt lại sau ~0,4s, tổng đổi theo |
| 3 | Đặt hàng bình thường | Tạo đơn, `grand_total` của Sales Order **bằng đúng** con số màn hình đã hiện |
| 4 | Sửa `Item Price` ở Desk rồi bấm đặt | Hộp thoại so cũ/mới hiện ra, **không** đặt âm thầm theo giá mới |
| 5 | Để tab 31 phút rồi bấm đặt | Báo "Báo giá đã hết hiệu lực", tự chốt lại |
| 6 | Danh mục sau khi có 1 đơn nháp | Cột "Đã đặt, chờ xác nhận" hiện số; "còn lại" giảm tương ứng |
| 7 | Bấm "Xác nhận đặt hàng" hai lần thật nhanh | Nút khoá và đổi chữ; **chỉ một** đơn được tạo |

> **Ghi chú về kiểm thử.** Cổng chưa có bộ test frontend tự động. Đây là món nợ kỹ
> thuật thật, không phải chuyện bỏ qua được: bảy kịch bản trên sẽ phải thử tay lại sau
> **mỗi** đợt. Đề nghị đưa "dựng bộ e2e cho SPA" vào đợt 3 cùng với `organizing-e2e-suites`.
> Ghi vào sổ theo dõi để không trôi mất.

- [ ] **Step 7: Ghi sổ theo dõi + commit**

```markdown
### NG-08 · NG-09 · NG-01 (phần giao diện) — 2026-08-12 · commit <sha>
**Trước:** `store.js` tự tính `cartVat = qty × rate × vat_pct / 100` ở trình duyệt (luôn ra 0 vì `vat_pct` gán cứng 0); `Cart.vue:195` hiện dòng "VAT (5–8%)" — giao diện hứa một thứ phía sau không có. Đặt hàng gửi thẳng giỏ hàng, không có bước chốt giá.
**Sau:** Tổng kết giỏ hàng **do máy chủ tính** qua `portal_quote` (debounce 400ms khi giỏ đổi), hiện "Giá có hiệu lực đến hh:mm". Đặt hàng gửi kèm `quote`. Máy chủ từ chối vì giá đổi → hộp thoại so cũ/mới với bốn nhãn lý do, buộc xác nhận lại. Danh mục thêm cột "Đã đặt, chờ xác nhận" + chú thích về giữ chỗ 3 ngày làm việc. Nút xác nhận khoá và đổi chữ khi đang gửi (UX-10).
**Đụng vào:** `frontend/src/api.js` (thêm `quoteCart`, đính `err.giaLech`) · `frontend/src/store.js` (**bỏ** getter `cartVat` và `cartTotal`, thêm `baoGia` / `baoGiaDangTai` / `giaLech`) · `views/Cart.vue` · `views/Catalog.vue` · bundle `miyano_portal/public/frontend`
**Phá vỡ:** `store.cartVat` và `store.cartTotal` **không còn tồn tại**. Bất kỳ component nào còn đọc chúng sẽ ra `undefined` — grep trước khi thêm màn mới.
**Test:** Thủ công, 7 kịch bản (xem plan Task 11 Step 6). **Nợ kỹ thuật:** SPA chưa có bộ test tự động; 7 kịch bản này phải thử tay lại sau mỗi đợt. Đề nghị đưa "dựng bộ e2e cho SPA" vào đợt 3.
**Cảnh báo chồng lấn:** Đừng khôi phục phép tính thuế phía trình duyệt dưới bất kỳ hình thức nào — hai nguồn sự thật cho cùng một tổng tiền chính là NG-08.
```

```bash
git add frontend/src miyano_portal/public/frontend docs/CHANGELOG-khac-phuc-BA-v2.md
git commit -m "feat(portal-ui): giỏ hàng dùng báo giá chốt từ máy chủ, danh mục hiện phần giữ chỗ (NG-08, NG-09, NG-01)"
```

---

## Task 12: Khung bản đồ lỗi — ba mã đầu của UX-08

**Files:**
- Create: `frontend/src/errors.js`
- Modify: `frontend/src/api.js`
- Test: thủ công (xem Step 4)

**Phạm vi cố ý hẹp.** Bảng đầy đủ `MYN-E101…E107` thuộc **đợt 2**. Đợt 1 chỉ dựng
**khung** cộng ba mã, vì đợt 1 sinh ra loại lỗi mới ("báo giá hết hạn", "giá đã đổi")
và cần chỗ đặt nó ngay. Làm hẳn bảng đầy đủ ở đây là kéo đợt 2 vào đợt 1.

**Nguyên tắc quan trọng nhất, đừng bỏ:** *lỗi chưa ánh xạ thì **giữ nguyên văn**.*
Tuyệt đối không thay bằng "Đã có lỗi xảy ra" — một lỗi tiếng Anh xấu xí vẫn chẩn đoán
được, còn câu chung chung thì giấu đi mọi thứ chưa ánh xạ. Và **không ánh xạ các lỗi
nghiệp vụ do chính mình ném ra**: *"Găng tay: cần xuất 500 Hộp nhưng tồn chỉ còn 398 Hộp"*
đã là thông báo tốt nhất có thể.

- [ ] **Step 1: Viết module bản đồ lỗi**

Tạo `frontend/src/errors.js`:

```js
// Bản đồ lỗi — BA v2 §UX-08. Đợt 1 dựng KHUNG + ba mã; bảng đầy đủ
// MYN-E101…E107 thuộc đợt 2.
//
// Ba nguyên tắc, mỗi cái đều đã có tiền lệ hỏng ở nơi khác:
//   1. Mỗi thông báo phải nói VIỆC CẦN LÀM, không chỉ mô tả hiện tượng.
//   2. Lỗi chưa ánh xạ thì GIỮ NGUYÊN VĂN. Không bao giờ thay bằng "Đã có lỗi
//      xảy ra" — lỗi tiếng Anh xấu xí vẫn chẩn đoán được, câu chung chung thì
//      giấu đi mọi thứ chưa ánh xạ.
//   3. KHÔNG ánh xạ lỗi nghiệp vụ do chính máy chủ mình ném ra — chúng đã là
//      thông báo tiếng Việt tốt nhất có thể; dịch lại chỉ làm tệ đi.

const BAN_DO = [
  {
    ma: 'MYN-E101',
    khop: (name) => name === 'TimestampMismatchError',
    text: 'Bản ghi đã được người khác cập nhật. Vui lòng tải lại trang và thử lại.',
  },
  {
    ma: 'MYN-E102',
    khop: (name, status) => name === 'PermissionError' || status === 403,
    text: 'Bạn không còn quyền thao tác trên mục này. Có thể phiên đăng nhập đã '
        + 'hết hạn — vui lòng đăng nhập lại.',
  },
  {
    ma: 'MYN-E103',
    khop: (name) => name === 'DoesNotExistError',
    text: 'Không tìm thấy bản ghi. Có thể nó đã bị xoá hoặc bạn mở từ một đường '
        + 'dẫn cũ.',
  },
]

// Lỗi do máy chủ của mình chủ động ném ra đã là tiếng Việt. Nhận diện thô mà
// đủ dùng: có dấu tiếng Việt trong thông điệp.
const CO_DAU_TIENG_VIET = /[àáảãạăâèéẻẽẹêìíỉĩịòóỏõọôơùúủũụưỳýỷỹỵđ]/i

export function dichLoi(errName, message, status) {
  if (message && CO_DAU_TIENG_VIET.test(message)) {
    return { ma: null, text: message }        // nguyên tắc 3
  }
  for (const e of BAN_DO) {
    if (e.khop(errName, status)) {
      return { ma: e.ma, text: e.text }       // nguyên tắc 1
    }
  }
  return { ma: null, text: message }          // nguyên tắc 2 — giữ nguyên văn
}
```

- [ ] **Step 2: Áp ở MỌI kênh máy chủ trả lỗi**

BA v2 §UX-08 nói rõ: phải áp ở cả bốn kênh `_server_messages`, `exception`,
`_error_message`, `message` — **bỏ sót một kênh thì lỗi thô vẫn lọt qua đúng đường đó,
và người dùng thấy nó ngẫu nhiên.**

Trong `frontend/src/api.js::callUrl`, thay khối xử lý lỗi:

```js
  if (!res.ok) {
    let msg = null
    // Bốn kênh, thử theo thứ tự cụ thể → chung chung.
    if (data) {
      if (data._server_messages) {
        try {
          const ds = JSON.parse(data._server_messages)
          const d0 = typeof ds[0] === 'string' ? JSON.parse(ds[0]) : ds[0]
          msg = (d0 && (d0.message || d0.title)) || null
        } catch { msg = data._server_messages }
      }
      msg = msg || data.exception || data._error_message || data.message
    }

    let errName = ''
    if (msg && typeof msg === 'string') {
      const m = msg.match(/^([\w.]*Error):\s*(.+)$/s)
      if (m) { errName = m[1].split('.').pop(); msg = m[2] }
    }

    const { ma, text } = dichLoi(errName, msg, res.status)
    const err = new Error(text || ('HTTP ' + res.status))
    if (errName) err.name = errName
    if (ma) err.maLoi = ma           // để giao diện hiện "Mã lỗi: MYN-E102"
    if (data && data.gia_lech) err.giaLech = data.gia_lech
    throw err
  }
```
Thêm import: `import { dichLoi } from './errors'`

- [ ] **Step 3: Hiện mã lỗi trong toast**

Trong `frontend/src/toast.js`, khi dựng toast lỗi, nếu `err.maLoi` thì thêm dòng phụ
`Mã lỗi: {maLoi}` cỡ chữ nhỏ. Toast lỗi **ở lại cho tới khi người dùng đóng** (UX-10);
toast thành công tự tắt sau 4 giây.

- [ ] **Step 4: Build và thử bốn kịch bản**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal/frontend && yarn build
```

| # | Cách dựng | Kỳ vọng |
|---|---|---|
| 1 | Mở một mã đơn không tồn tại | Tiếng Việt + `Mã lỗi: MYN-E103`, **không** hiện `DoesNotExistError` |
| 2 | Xoá cookie phiên rồi bấm lưu | Tiếng Việt + `MYN-E102` |
| 3 | Đặt vượt hạn mức | Nguyên văn tiếng Việt của máy chủ (*"vượt hạn mức (còn 2)"*), **không** có mã lỗi |
| 4 | Một lỗi Python chưa ánh xạ | **Giữ nguyên văn tiếng Anh**, không thay bằng "Đã có lỗi xảy ra" |

- [ ] **Step 5: Ghi sổ theo dõi + commit**

```markdown
### UX-08 (khung + 3 mã) — 2026-08-12 · commit <sha>
**Trước:** `api.js` chỉ cắt tiền tố tên lớp lỗi rồi hiện nguyên văn; không có bản đồ lỗi nào (NG-41). Chỉ đọc `data.exception || data._server_messages || data.message` — bỏ sót kênh `_error_message` và không bóc JSON của `_server_messages`.
**Sau:** `frontend/src/errors.js` với `dichLoi(errName, message, status)`. Ba mã: `MYN-E101` TimestampMismatch · `MYN-E102` Permission/403 · `MYN-E103` DoesNotExist. Áp ở **cả bốn** kênh, `_server_messages` được bóc JSON đúng cách. Lỗi nghiệp vụ tiếng Việt của máy chủ **không** bị ánh xạ lại (nhận diện bằng dấu tiếng Việt). Lỗi chưa ánh xạ **giữ nguyên văn**. `err.maLoi` hiện trong toast.
**Đụng vào:** `frontend/src/errors.js` (mới) · `frontend/src/api.js::callUrl` · `frontend/src/toast.js`
**Phá vỡ:** Không.
**Test:** Thủ công, 4 kịch bản.
**Phạm vi cố ý hẹp:** Bốn mã còn lại (`MYN-E104` MandatoryError · `E105` DuplicateEntry · `E106` LinkValidation · `E107` hết phiên/CSRF) thuộc **đợt 2** cùng UX-11. Thêm vào mảng `BAN_DO`, không dựng lại khung.
```

Cập nhật bảng tiến độ §1: thêm dòng `UX-08 (khung)` → ✅ ở đợt 1.

```bash
git add frontend/src docs/CHANGELOG-khac-phuc-BA-v2.md
git commit -m "feat(portal-ui): khung bản đồ lỗi và ba mã đầu (UX-08, NG-41 một phần)"
```

---

# Nghiệm thu đợt 1

Đợt 1 xong khi **tất cả** dòng dưới đây đúng:

| # | Tiêu chí | Cách kiểm |
|---|---|---|
| 1 | Tài khoản cổng của khách A không đọc được bất kỳ chứng từ nào của khách B qua **mọi** đường whitelist | `test_search_guard.py` + `test_isolation.py` + kết quả quét 38 endpoint ở Task 1 Step 8 |
| 2 | Nhân viên Miyano trên Desk không bị chặn nhầm | `test_search_guard.py::test_desk_user_van_tim_duoc_moi_don` |
| 3 | Mọi trường tiền của sổ kho là số nguyên; tổng đầu phiếu = tổng các dòng = tổng sổ = tổng cache | `test_kho_precision.py`, assert đọc **lại từ CSDL** |
| 4 | Số tiền màn hình hiện = `grand_total` của Sales Order được tạo | `test_order_place.py::test_dat_hang_khop_bao_gia_thi_thanh_cong` + kịch bản tay #3 |
| 5 | Giá đổi giữa lúc xem và lúc đặt → **từ chối** + bảng so cũ/mới, không đặt âm thầm | kịch bản tay #4 |
| 6 | `grand_total` của đơn đặt qua cổng bao gồm VAT theo mẫu thuế của khách | `test_order_place.py::test_don_hang_duoc_gan_mau_thue` |
| 7 | Hợp đồng nháp / chưa hiệu lực / đã hết hạn không đặt được, kể cả khi đã có giỏ hàng | `test_portal_contracts.py` |
| 8 | Mặt hàng bị gỡ khỏi hợp đồng báo đúng lý do, **không** báo "vượt hạn mức" | `test_portal_contracts.py::test_thong_bao_dat_hang_phan_biet_hai_truong_hop` |
| 9 | Hạn mức cổng báo cho khách đã trừ phần đơn nháp chưa xác nhận | `test_giu_cho.py` + kịch bản tay #6 |
| 10 | Đơn nháp quá 3 ngày làm việc → nhả chỗ + **email thật sự được xếp hàng gửi** một lần, đơn **không** bị huỷ | `test_giu_cho.py::TestNhaGiuCho::test_email_that_su_duoc_xep_hang_gui` (không phải chỉ test cờ) |
| 10b | `Portal Quote Lock` chưa dùng quá 30 ngày bị dọn; bản đã dùng giữ lại | `test_giu_cho.py::test_don_dep_bao_gia_cu_giu_lai_ban_da_dung` |
| 11 | Huỷ phiếu giao mà kho khách không đảo được → ToDo + cờ trên phiếu + có trong báo cáo đối soát | `test_kho_delivery_hook.py::TestDaoThatBaiKhongImLang` |
| 12 | Đảo **thành công** thì không sinh báo động nào | cùng module, `test_dao_thanh_cong_thi_khong_bao_dong_gi` |
| 13 | Lỗi chưa ánh xạ **giữ nguyên văn**; lỗi nghiệp vụ tiếng Việt không bị dịch lại | kịch bản tay #3, #4 của Task 12 |
| 14 | Sổ theo dõi có đủ **12** mục, bảng tiến độ khớp thực tế | đọc `docs/CHANGELOG-khac-phuc-BA-v2.md` |

Chạy toàn bộ trước khi tuyên bố xong:
```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_portal
```

## Việc ngoài code chặn nghiệm thu

1. **Kế toán khai `Sales Taxes and Charges Template`** (+ `tax_category` trên từng
   `Customer` nếu nhiều thuế suất). Chưa khai thì tiêu chí #6 không kiểm được trên dữ
   liệu thật — `thue_suat()` trả `0.0` và cổng hiển thị đúng "chưa khai thuế".
2. **`seed_demo` phải `submit()` Blanket Order.** Nếu seed tạo hợp đồng nháp thì sau
   Task 7 chúng biến mất khỏi cổng và mọi test dùng seed sẽ đổ.
3. **Buổi khảo sát nhóm A8** với phòng kinh doanh — xếp **song song** với đợt 1 để kết
   quả kịp đưa vào đợt 3.

## Nợ kỹ thuật ghi nhận trong đợt này

- **SPA chưa có bộ test tự động.** 11 kịch bản thủ công (7 của Task 11 + 4 của Task 12)
  phải thử tay lại sau mỗi đợt. Đề nghị đưa "dựng bộ e2e cho SPA" vào đợt 3.
- **NG-42 chưa sửa** — hai mẫu Notification cũ vẫn có `condition` rỗng nên gửi cho cả
  khách không dùng cổng. Xếp đợt 5. Mẫu mới ở Task 9 **có** điều kiện lọc; đừng dùng
  hai mẫu cũ làm khuôn.
- **Trường tiền của `Sales Order` / `Sales Invoice` vẫn `precision` mặc định.** Ngoài
  phạm vi BA v2 §NG-12, cần bàn riêng với kế toán.
