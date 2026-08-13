# Epic E2 — Duyệt đơn theo ngưỡng & máy trạng thái Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Siết quy trình duyệt đơn theo QT2: đơn nhỏ Sales User tự xác nhận, đơn từ ngưỡng trở lên bắt buộc Sales Manager, từ chối nào cũng phải có lý do đến tay khách, đơn treo quá SLA thì leo thang, và bổ sung trạng thái "Chờ khách đồng ý" làm nền cho E6.

**Architecture:** Không thêm doctype nào. Nghiệp vụ duyệt tách vào module mới `portal_duyet_don.py` (ngưỡng + lý do từ chối) và `portal_sla.py` (job quét đơn treo), nối vào `Sales Order` bằng `doc_events` trong `hooks.py`; máy trạng thái mở rộng bằng patch **sửa tại chỗ** workflow đang chạy. `api/portal.py` nhận thêm đúng một endpoint `portal_order_accept`.

**Tech Stack:** Frappe v15.113.4, ERPNext v15.83.0, Python 3.12, MariaDB, Vue 3 + Vite. Test bằng `FrappeTestCase`.

## Global Constraints

- Spec nguồn: [`DevHandoff/11_PRD_E2_DuyetDon.md`](../../Miyano-Portal%28Client%29_V2/DevHandoff/11_PRD_E2_DuyetDon.md). Quy tắc gốc: `BA-miyano_portal_v2.md` §4.2 dòng NL-2.1…2.8. API: `30_API_Spec.md` §2.4. Test: `40_TestCases.md` nhóm **TC-E2**.
- App: `apps/miyano_portal`. Nhánh mới: `feature/e2-duyet-don`, tách từ `feature/e1-dat-hang-han-muc` (đã có `Miyano Portal Settings` với sẵn `nguong_duyet_2_tang` và `sla_xu_ly_don_gio`).
- Site test/dev: `erptest.local`. Bench: `/home/hoangvietyeuem/frappe-bench-yhct`.
- **Baseline: 435 test phải giữ xanh.**
- Đặt tên: DocType tiếng Anh, fieldname tiếng Việt **không dấu**, label tiếng Việt có dấu.
- Tiền VND `1.234.567 ₫` không thập phân; ngày `dd/mm/yyyy`.
- Mọi chốt chặn nghiệp vụ ở **server**. Patch **idempotent**: `bench migrate` hai lần liên tiếp không lỗi, không sinh trùng.
- `frappe.get_all` **luôn** bỏ qua phân quyền; `frappe.get_doc` **không** chạy hook `has_permission`.
- `FrappeTestCase` rollback một lần mỗi **class**, không phải mỗi test.
- Role `Customer` **không** được có DocPerm mới nào, và **không** được nằm trong `allowed` của bất kỳ workflow transition nào.
- Commit sau mỗi task. **Không push.**

### BẪY 1 — ngưỡng để trống đọc ra chuỗi `'0'`, không phải rỗng

Đã kiểm thực nghiệm trên `erptest.local`. Lưu Single với `nguong_duyet_2_tang = None` rồi đọc lại:

| Cách đọc | Kết quả |
|---|---|
| `frappe.db.get_value("Miyano Portal Settings", None, "nguong_duyet_2_tang")` | `'0'` — **chuỗi, truthy** |
| `frappe.db.get_single_value("Miyano Portal Settings", "nguong_duyet_2_tang")` | `0.0` |

Nên điều kiện viết theo lối tự nhiên `not nguong or tong < float(nguong)` cho ra **False** khi ngưỡng để trống, tức là **Sales User mất sạch quyền duyệt mọi đơn** ngay khi patch chạy — ngược hoàn toàn US-E2.1 ("để trống → một tầng như cũ"). Bảng kiểm sáu ca:

| ngưỡng | tổng | `not N or ...` | `float(N or 0) <= 0 or ...` |
|---|---|---|---|
| 50.000.000 | 49.000.000 | True | True |
| 50.000.000 | 50.000.000 | False | False |
| 50.000.000 | 51.000.000 | False | False |
| `None` | 100.000.000 | True | True |
| `0` | 100.000.000 | **False ← sai** | True |
| `''` | 100.000.000 | True | True |

**Quy tắc bắt buộc: mọi chỗ đọc ngưỡng đều dùng `float(... or 0)` và coi `<= 0` là "một tầng".** Dùng `get_single_value` (trả float) chứ đừng dùng `get_value` khi ở trong Python thường.

### BẪY 2 — `apply_workflow` ném lỗi TRƯỚC khi `validate`/`before_submit` chạy

`frappe/model/workflow.py:113-115`: nếu không transition nào khớp (do role hoặc do `condition`), Frappe `frappe.throw(_("Not a valid Workflow Action"), WorkflowTransitionError)` **trước** mọi `doc.save()`/`doc.submit()`.

Hệ quả: **không thể** vừa đặt ngưỡng vào `condition` của transition vừa hiện đúng câu NL-2.5. Đặt condition → hook không bao giờ chạy → khách nhận câu "Not a valid Workflow Action".

AC của US-E2.1 đòi đúng câu *"Đơn ≥ 50.000.000 ₫ — cần Sales Manager xác nhận"*. Khi hướng dẫn hiện thực trong PRD ("điều kiện trên transition") mâu thuẫn với AC, **AC thắng**. Kế hoạch này chốt: giữ transition `Xác nhận` cho `Sales User` **không có condition**, chặn bằng `before_submit` để nêu đúng câu. NL-2.5 vẫn đúng nguyên văn ("đơn chờ ở Chờ Miyano xác nhận") vì exception làm rollback, `workflow_state` không đổi.

### BẪY 3 — hai hàm `install_*` hiện có KHÔNG sửa được bản ghi đã tồn tại

- `setup/install_workflow.py:17-18` — `if frappe.db.exists("Workflow", WORKFLOW): return`.
- `setup/install_notifications.py:50-51` — `if frappe.db.exists("Notification", d["name"]): continue`.

Nên **không được** sửa hai file đó rồi trông chờ migrate áp dụng. Mọi thay đổi E2 phải là **patch mới sửa tại chỗ**, idempotent theo *nội dung* chứ không theo *sự tồn tại*.

### BẪY 4 — không gán `workflow_state` trước `insert()` (phát hiện khi làm Task 1)

`frappe/model/workflow.py::validate_workflow`: với doc **mới**, nếu state đích khác state đầu tiên của workflow và `_doc_before_save` chưa tồn tại, Frappe ném `WorkflowPermissionError` **vô điều kiện**. Mọi helper test muốn dựng Sales Order ở một trạng thái giữa chừng đều phải theo khuôn này:

```python
    so.insert(ignore_permissions=True)          # để insert tự gán state đầu
    if so.workflow_state != trang_thai:
        frappe.db.set_value(                    # ghi thẳng DB, không qua ORM
            "Sales Order", so.name, "workflow_state", trang_thai, update_modified=False
        )
        so.reload()                             # nếu không, .save() sau dính TimestampMismatchError
```

`update_modified=False` là bắt buộc với Task 6: job SLA đọc `modified` để tính giờ treo, để `set_value` chạm vào nó là hỏng chính thứ đang thử.

### Giả định phải nêu rõ — "giờ làm việc" của SLA

`sla_xu_ly_don_gio = 8` tính theo **giờ làm việc**, nhưng app không có bảng giờ làm việc lẫn bảng ngày lễ. Theo đúng tiền lệ BR-O13 (`portal_dat_hang.ngay_giao_mac_dinh`): **chỉ bỏ Thứ Bảy và Chủ Nhật, không trừ ngày lễ, không có khung giờ hành chính trong ngày**. Lý do giữ nguyên: một bảng ngày lễ chỉ tồn tại ở một phía sẽ sai lệch âm thầm — tệ hơn là không có, vì nó tạo cảm giác đã được xử lý.

### Phạm vi bị cắt có chủ ý

**US-E2.4 chỉ làm nửa hiển thị.** PRD ghi rõ *"phần hoàn hạn mức chỉ làm khi VĐ-7 chốt — đánh dấu TODO tham chiếu VĐ-7"*. Task 8 sửa nhãn trạng thái; phần hoàn hạn mức Blanket Order **không** làm, để lại TODO trỏ VĐ-7. Đây là cắt theo chỉ dẫn của spec, không phải bỏ sót.

## Điểm nối [Hiện có] — KHÔNG code lại

- Workflow `Sales Order - Client Portal` đã có 4 state (`Chờ xác nhận`, `Chờ Miyano xác nhận`, `Đã xác nhận`, `Từ chối`) và 3 transition (`setup/install_workflow.py:25-35`). E2 **thêm**, không dựng lại.
- Notification `Portal - Đơn bị từ chối` đã tồn tại và **đang bật** (`install_notifications.py:20-27`), nhưng nội dung là *"Vui lòng liên hệ để biết thêm chi tiết"* — chưa có lý do. Task 5 **sửa nội dung**, không tạo mới.
- `Miyano Portal Settings.nguong_duyet_2_tang` và `.sla_xu_ly_don_gio` đã tạo ở E1 — không cần patch schema.
- Mọi Sales Manager trên site đều đã có sẵn role Sales User (kiểm: `mgr - usr == []`), nên Manager duyệt được qua transition hiện có. Task 3 vẫn thêm transition riêng cho Manager để một tài khoản Manager-thuần cũng duyệt được.

## Nợ kỹ thuật đã biết, CỐ Ý không xử lý ở đây

| Hiện trạng | Chỗ | Hệ quả |
|---|---|---|
| `portal_catalog` trả `vat_pct: 0` cứng | `api/portal.py` | Tổng tiền báo thấp hơn thực tế |
| Danh mục rơi về `Blanket Order Item.rate` còn `order_place` chỉ nhận `Item Price` | `api/portal.py:196-200` vs `_gia_hien_hanh` | Khách thấy giá rồi bị từ chối "chưa có giá" — chờ BA chốt |
| `test_rest_guard._login_bvbm` chỉ bắt `ConnectionError`, không bắt `ReadTimeout` | `tests/test_rest_guard.py:84` | Suite đỏ ngẫu nhiên khi bench chậm |

## File Structure

| File | Trách nhiệm | Task |
|---|---|---|
| `miyano_portal/patches/v1_4/__init__.py` | **Tạo.** | 1 |
| `miyano_portal/patches/v1_4/create_e2_custom_fields.py` | **Tạo.** `Sales Order.custom_ly_do_tu_choi` | 1 |
| `miyano_portal/portal_duyet_don.py` | **Tạo.** Ngưỡng duyệt + bắt buộc lý do từ chối | 1, 2 |
| `miyano_portal/hooks.py` | **Sửa.** `doc_events` cho Sales Order; `scheduler_events.hourly` | 1, 2, 6 |
| `miyano_portal/patches/v1_4/mo_rong_workflow_e2.py` | **Tạo.** Thêm state "Chờ khách đồng ý" + 4 transition | 3 |
| `miyano_portal/api/portal.py` | **Sửa.** `portal_order_accept`; `_so_status_vi` | 4, 8 |
| `miyano_portal/patches/v1_4/sua_mail_tu_choi.py` | **Tạo.** Nhét lý do vào Notification đã có | 5 |
| `miyano_portal/portal_sla.py` | **Tạo.** Quét đơn treo + leo thang | 6 |
| `miyano_portal/patches/v1_4/tao_bao_cao_don_cham.py` | **Tạo.** Query Report "Đơn chậm xử lý" | 7 |
| `miyano_portal/patches.txt` | **Sửa.** Thêm 4 patch | 1, 3, 5, 7 |
| `miyano_portal/tests/test_e2_nguong_duyet.py` | **Tạo.** | 1, 2 |
| `miyano_portal/tests/test_e2_workflow_va_accept.py` | **Tạo.** | 3, 4 |
| `miyano_portal/tests/test_e2_sla_va_trang_thai.py` | **Tạo.** | 5, 6, 7, 8 |

Ghi chú cách ly: E2 **không** thêm doctype nào vào module `Miyano Portal`, nên lưới an toàn `test_kho_isolation._nap_doctype_kho()` không bị chạm (nó chỉ liệt kê doctype theo `module = "Miyano Portal"`). `Workflow State` / `Workflow Action Master` là doctype lõi của Frappe, nằm ngoài vòng đó.

---

## Task 1: Bắt buộc lý do khi từ chối (US-E2.2 nửa server, BR-O14, NL-2.1)

**Files:**
- Create: `miyano_portal/patches/v1_4/__init__.py`, `miyano_portal/patches/v1_4/create_e2_custom_fields.py`, `miyano_portal/portal_duyet_don.py`
- Modify: `miyano_portal/patches.txt`, `miyano_portal/hooks.py`
- Test: `miyano_portal/tests/test_e2_nguong_duyet.py`

**Interfaces:**
- Produces: `portal_duyet_don.kiem_ly_do_tu_choi(doc, method=None)` — hook `validate` của Sales Order; `portal_duyet_don.LY_DO_TOI_THIEU = 10`.

- [ ] **Step 1: Viết test thất bại**

```python
"""US-E2.2 / BR-O14 — từ chối phải có lý do. TC-E2-04."""
import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.seed_demo import seed_demo


class TestLyDoTuChoi(FrappeTestCase):
    def setUp(self):
        seed_demo()
        self.so = _tao_so_nhap("Chờ Miyano xác nhận")

    def test_khong_co_ly_do_thi_khong_chuyen_duoc(self):
        self.so.workflow_state = "Từ chối"
        with self.assertRaises(frappe.ValidationError) as ctx:
            self.so.save()
        self.assertIn("lý do từ chối", str(ctx.exception).lower())

    def test_ly_do_qua_ngan_bi_chan(self):
        self.so.workflow_state = "Từ chối"
        self.so.custom_ly_do_tu_choi = "hết hàng"   # 8 ký tự < 10
        with self.assertRaises(frappe.ValidationError):
            self.so.save()

    def test_ly_do_du_dai_thi_luu_duoc(self):
        self.so.workflow_state = "Từ chối"
        self.so.custom_ly_do_tu_choi = "Hết hàng trong kho, dự kiến về ngày 20/08."
        self.so.save()
        self.assertEqual(
            frappe.db.get_value("Sales Order", self.so.name, "workflow_state"), "Từ chối"
        )

    def test_trang_thai_khac_khong_bi_doi_hoi_ly_do(self):
        """Đơn nội bộ đi qua máy trạng thái như cũ — DoD E2."""
        self.so.workflow_state = "Chờ Miyano xác nhận"
        self.so.save()   # không được ném
```

Helper đặt cùng file:

```python
def _tao_so_nhap(trang_thai: str, tong_muc_tieu: float = 1200):
    """Sales Order nháp của khách demo, ở đúng workflow_state cần thử.

    `qty = 1` nên `rate` chính là `grand_total` — miễn là không có thuế. Ca
    ngưỡng phụ thuộc vào con số này nên phải KHẲNG ĐỊNH, không phỏng đoán:
    site có `Sales Taxes and Charges Template` mặc định là mọi ca ngưỡng lệch
    đi 8-10% và đỏ vì lý do chẳng liên quan gì tới quy tắc đang thử.
    """
    from miyano_portal.setup.seed_demo import PRICE_LIST
    so = frappe.new_doc("Sales Order")
    so.customer = "Bệnh viện Bạch Mai"
    so.transaction_date = frappe.utils.today()
    so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 7)
    so.selling_price_list = PRICE_LIST
    so.append("items", {
        "item_code": "VT0005",
        "qty": 1,
        "rate": tong_muc_tieu,
        "delivery_date": so.delivery_date,
    })
    so.taxes = []            # không để template thuế mặc định chen vào
    so.taxes_and_charges = None
    so.workflow_state = trang_thai
    so.flags.ignore_permissions = True
    so.insert(ignore_permissions=True)
    assert float(so.grand_total) == float(tong_muc_tieu), (
        f"grand_total={so.grand_total} khác mức cần thử {tong_muc_tieu} — "
        "có thuế hoặc chiết khấu chen vào, ca ngưỡng sẽ vô nghĩa"
    )
    return so
```

- [ ] **Step 2: Chạy để thấy FAIL**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e2_nguong_duyet`
Expected: FAIL — `custom_ly_do_tu_choi` chưa tồn tại (`AttributeError`/field bị bỏ qua) và không có ai ném lỗi.

- [ ] **Step 3: Tạo thư mục patch v1_4**

```bash
mkdir -p miyano_portal/patches/v1_4 && touch miyano_portal/patches/v1_4/__init__.py
```

- [ ] **Step 4: Viết patch custom field**

`miyano_portal/patches/v1_4/create_e2_custom_fields.py`:

```python
"""BR-O14 — ô lý do từ chối trên Sales Order.

`create_custom_fields` tự nó đã idempotent: gọi lại chỉ cập nhật thuộc tính,
không sinh bản ghi thứ hai.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields(
        {
            "Sales Order": [
                {
                    "fieldname": "custom_ly_do_tu_choi",
                    "label": "Lý do từ chối",
                    "fieldtype": "Small Text",
                    "insert_after": "custom_hdnt",
                    "no_copy": 1,
                    # CỐ Ý không đặt `depends_on` theo workflow_state: ô phải
                    # nhập được TRƯỚC khi bấm Từ chối. Giấu ô cho tới lúc đã ở
                    # trạng thái "Từ chối" thì người duyệt không bao giờ điền
                    # được, và quy tắc bắt buộc lý do thành cái bẫy không lối ra.
                    "translatable": 0,
                }
            ]
        },
        ignore_validate=True,
    )
```

- [ ] **Step 5: Viết `portal_duyet_don.py`**

```python
"""Quy tắc duyệt đơn của QT2 — ngưỡng hai tầng và lý do từ chối.

Tách khỏi `api/portal.py` vì đây là quy tắc áp cho MỌI Sales Order (kể cả đơn
nội bộ Miyano tự lập), không riêng đơn từ cổng — nó thuộc về `doc_events`,
không thuộc về một endpoint nào.
"""

import frappe
from frappe import _

LY_DO_TOI_THIEU = 10


def kiem_ly_do_tu_choi(doc, method=None):
    """BR-O14 / NL-2.1. Không có lý do thì không chuyển sang "Từ chối" được.

    Đặt ở `validate` chứ không ở `before_submit`: state "Từ chối" mang
    `doc_status = 0`, nên `apply_workflow` đi nhánh `doc.save()` — `before_submit`
    không bao giờ chạy cho chuyển tiếp này.
    """
    if (doc.get("workflow_state") or "") != "Từ chối":
        return
    ly_do = (doc.get("custom_ly_do_tu_choi") or "").strip()
    if len(ly_do) < LY_DO_TOI_THIEU:
        frappe.throw(
            _("Phải nhập lý do từ chối (tối thiểu {0} ký tự) trước khi chuyển trạng thái.").format(
                LY_DO_TOI_THIEU
            ),
            frappe.ValidationError,
        )
```

- [ ] **Step 6: Nối hook và patch**

`hooks.py` — thêm (hoặc bổ sung vào `doc_events` đã có):

```python
doc_events = {
    "Sales Order": {
        "validate": "miyano_portal.portal_duyet_don.kiem_ly_do_tu_choi",
    },
}
```

**Cảnh báo:** `hooks.py` có thể đã khai `doc_events` cho `Delivery Note`. Đọc trước, **gộp vào dict đang có**, đừng khai lần thứ hai — khai trùng key thì bản sau đè bản trước và hook giao hàng biến mất.

`patches.txt` — nối thêm (dùng script để chắc chắn có newline cuối, xem bài học E1):

```python
p = "miyano_portal/patches.txt"
noi_dung = open(p).read()
if not noi_dung.endswith("\n"):
    noi_dung += "\n"
noi_dung += "miyano_portal.patches.v1_4.create_e2_custom_fields\n"
open(p, "w").write(noi_dung)
```

- [ ] **Step 7: Migrate rồi chạy test**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local migrate && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e2_nguong_duyet`
Expected: 4 PASS.

- [ ] **Step 8: Migrate lần hai để kiểm idempotent**

Run: `bench --site erptest.local migrate`
Expected: không lỗi, không sinh Custom Field thứ hai.

- [ ] **Step 9: Commit**

```bash
git add miyano_portal/patches miyano_portal/portal_duyet_don.py miyano_portal/hooks.py miyano_portal/patches.txt miyano_portal/tests/test_e2_nguong_duyet.py
git commit -m "feat(portal): bắt buộc lý do khi từ chối đơn (BR-O14, NL-2.1)"
```

---

## Task 2: Ngưỡng duyệt hai tầng (US-E2.1, BR-O9, NL-2.5)

**Files:**
- Modify: `miyano_portal/portal_duyet_don.py`, `miyano_portal/hooks.py`
- Test: `miyano_portal/tests/test_e2_nguong_duyet.py`

**Interfaces:**
- Consumes: `portal_duyet_don` từ Task 1.
- Produces: `portal_duyet_don.nguong_duyet() -> float`, `portal_duyet_don.kiem_nguong_duyet(doc, method=None)` — hook `before_submit`.

- [ ] **Step 1: Viết test thất bại** (thêm class vào cùng file)

```python
from miyano_portal.portal_duyet_don import nguong_duyet

NGUONG = 50_000_000


class TestNguongDuyet(FrappeTestCase):
    def setUp(self):
        seed_demo()
        frappe.db.set_single_value("Miyano Portal Settings", "nguong_duyet_2_tang", NGUONG)
        self.addCleanup(frappe.set_user, "Administrator")

    # ---------- đọc ngưỡng: BẪY 1 ----------
    def test_nguong_de_trong_doc_ra_0(self):
        frappe.db.set_single_value("Miyano Portal Settings", "nguong_duyet_2_tang", None)
        self.assertEqual(nguong_duyet(), 0.0)

    def test_nguong_bang_0_cung_la_mot_tang(self):
        """`0` và rỗng PHẢI cư xử giống nhau. Field Currency lưu rỗng thành 0,
        nên phân biệt hai thứ này là khoá sạch quyền duyệt của Sales User."""
        frappe.db.set_single_value("Miyano Portal Settings", "nguong_duyet_2_tang", 0)
        self.assertEqual(nguong_duyet(), 0.0)

    # ---------- TC-E2-01 ----------
    def test_sales_user_duyet_duoc_don_duoi_nguong(self):
        so = _tao_so_nhap("Chờ Miyano xác nhận", tong_muc_tieu=49_000_000)
        frappe.set_user("sales_user@demo.miyano")
        so.submit()
        self.assertEqual(so.docstatus, 1)

    def test_sales_user_bi_chan_o_dung_nguong(self):
        so = _tao_so_nhap("Chờ Miyano xác nhận", tong_muc_tieu=NGUONG)
        frappe.set_user("sales_user@demo.miyano")
        with self.assertRaises(frappe.ValidationError) as ctx:
            so.submit()
        loi = str(ctx.exception)
        self.assertIn("50.000.000", loi)
        self.assertIn("Sales Manager", loi)

    def test_don_bi_chan_van_o_nguyen_trang_thai_cu(self):
        """NL-2.5 — "đơn chờ ở Chờ Miyano xác nhận", không rơi sang trạng thái lửng."""
        so = _tao_so_nhap("Chờ Miyano xác nhận", tong_muc_tieu=NGUONG)
        frappe.set_user("sales_user@demo.miyano")
        with self.assertRaises(frappe.ValidationError):
            so.submit()
        frappe.set_user("Administrator")
        self.assertEqual(
            frappe.db.get_value("Sales Order", so.name, "docstatus"), 0
        )

    # ---------- TC-E2-02 ----------
    def test_sales_manager_duyet_duoc_don_tu_nguong(self):
        so = _tao_so_nhap("Chờ Miyano xác nhận", tong_muc_tieu=NGUONG)
        frappe.set_user("buiviet9802@gmail.com")   # có role Sales Manager
        so.submit()
        self.assertEqual(so.docstatus, 1)

    # ---------- TC-E2-03 ----------
    def test_nguong_de_trong_thi_sales_user_duyet_duoc_don_100tr(self):
        frappe.db.set_single_value("Miyano Portal Settings", "nguong_duyet_2_tang", None)
        so = _tao_so_nhap("Chờ Miyano xác nhận", tong_muc_tieu=100_000_000)
        frappe.set_user("sales_user@demo.miyano")
        so.submit()
        self.assertEqual(so.docstatus, 1)
```

**Lưu ý khi viết test:** `sales_user@demo.miyano` phải có role `Sales User` và **không** có `Sales Manager`. Kiểm trong `setUp` và gán nếu thiếu, đừng giả định seed đã làm:

```python
        u = frappe.get_doc("User", "sales_user@demo.miyano")
        vai = {r.role for r in u.roles}
        if "Sales User" not in vai:
            u.append("roles", {"role": "Sales User"})
            u.save(ignore_permissions=True)
        if "Sales Manager" in vai:
            u.roles = [r for r in u.roles if r.role != "Sales Manager"]
            u.save(ignore_permissions=True)
```

- [ ] **Step 2: Chạy để thấy FAIL**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e2_nguong_duyet`
Expected: FAIL — `ImportError: cannot import name 'nguong_duyet'`.

- [ ] **Step 3: Viết `nguong_duyet` và `kiem_nguong_duyet`**

Thêm vào `portal_duyet_don.py`:

```python
def nguong_duyet() -> float:
    """Ngưỡng duyệt hai tầng. `0` = một tầng (không chặn ai).

    BẮT BUỘC dùng `get_single_value` (trả float) chứ không `get_value`: field
    Currency để trống được lưu thành chuỗi `'0'`, mà `not '0'` là False — đọc
    kiểu đó thì ngưỡng-để-trống biến thành "mọi đơn đều cần Manager", khoá
    sạch quyền duyệt của Sales User. Đã kiểm thực nghiệm, xem BẪY 1 của kế hoạch.
    """
    return float(
        frappe.db.get_single_value("Miyano Portal Settings", "nguong_duyet_2_tang") or 0
    )


def _tien_vn(so: float) -> str:
    """50000000.0 -> "50.000.000". Không thập phân, dấu chấm ngăn nghìn."""
    return f"{int(so):,}".replace(",", ".")


def kiem_nguong_duyet(doc, method=None):
    """BR-O9 / NL-2.5. Đơn từ ngưỡng trở lên chỉ Sales Manager xác nhận được.

    Đặt ở `before_submit` chứ KHÔNG ở `condition` của workflow transition:
    `apply_workflow` ném `WorkflowTransitionError` ngay khi không transition nào
    khớp, TRƯỚC mọi save/submit (`frappe/model/workflow.py:113-115`), nên hook
    sẽ không bao giờ chạy và khách chỉ nhận được câu "Not a valid Workflow
    Action" thay vì câu NL-2.5. Exception ở đây làm rollback, nên đơn nằm
    nguyên ở "Chờ Miyano xác nhận" — đúng như NL-2.5 mô tả.
    """
    nguong = nguong_duyet()
    if nguong <= 0:
        return
    if float(doc.get("grand_total") or 0) < nguong:
        return
    if "Sales Manager" in frappe.get_roles():
        return
    frappe.throw(
        _("Đơn ≥ {0} ₫ — cần Sales Manager xác nhận.").format(_tien_vn(nguong)),
        frappe.ValidationError,
    )
```

- [ ] **Step 4: Nối hook**

Bổ sung vào `doc_events["Sales Order"]` đã tạo ở Task 1:

```python
        "before_submit": "miyano_portal.portal_duyet_don.kiem_nguong_duyet",
```

- [ ] **Step 5: Chạy test**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e2_nguong_duyet`
Expected: toàn bộ PASS (4 của Task 1 + 7 của Task 2).

- [ ] **Step 6: Chạy toàn suite**

Run: `bench --site erptest.local run-tests --app miyano_portal`
Expected: 435 + số ca mới, tất cả xanh. **Đặc biệt để ý** các test cũ có `so.submit()` — nếu ngưỡng còn sót giá trị từ test khác thì chúng sẽ đỏ. Đó là lý do `setUp` phải luôn set ngưỡng tường minh.

- [ ] **Step 7: Commit**

```bash
git add miyano_portal/portal_duyet_don.py miyano_portal/hooks.py miyano_portal/tests/test_e2_nguong_duyet.py
git commit -m "feat(portal): duyệt hai tầng theo ngưỡng (BR-O9, NL-2.5)"
```

---

## Task 3: Mở rộng máy trạng thái — "Chờ khách đồng ý" + 4 transition (US-E2.5 nửa schema)

**Files:**
- Create: `miyano_portal/patches/v1_4/mo_rong_workflow_e2.py`
- Modify: `miyano_portal/patches.txt`
- Test: `miyano_portal/tests/test_e2_workflow_va_accept.py`

**Interfaces:**
- Produces: state `"Chờ khách đồng ý"` (doc_status 0) và 4 transition dưới đây trên workflow `Sales Order - Client Portal`.

Bốn transition thêm mới:

| Từ | Hành động | Sang | `allowed` |
|---|---|---|---|
| Chờ xác nhận | Gửi khách duyệt | Chờ khách đồng ý | Sales User |
| Chờ khách đồng ý | Khách đồng ý | Chờ Miyano xác nhận | System Manager |
| Chờ khách đồng ý | Khách không đồng ý | Chờ xác nhận | System Manager |
| Chờ Miyano xác nhận | Xác nhận | Đã xác nhận | Sales Manager |

Hai transition của khách để `allowed = System Manager` vì endpoint chạy **dưới quyền hệ thống** (`30_API_Spec` §2.4). **Không bao giờ** đặt role `Customer` vào đây.

- [ ] **Step 1: Viết test thất bại**

```python
"""US-E2.5 — trạng thái "Chờ khách đồng ý" và endpoint portal_order_accept."""
import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.seed_demo import seed_demo

WF = "Sales Order - Client Portal"
STATE_KHACH = "Chờ khách đồng ý"


class TestWorkflowMoRong(FrappeTestCase):
    def test_co_state_cho_khach_dong_y(self):
        wf = frappe.get_doc("Workflow", WF)
        s = next((x for x in wf.states if x.state == STATE_KHACH), None)
        self.assertIsNotNone(s, "thiếu state 'Chờ khách đồng ý'")
        self.assertEqual(str(s.doc_status), "0")

    def test_du_bon_transition_moi(self):
        wf = frappe.get_doc("Workflow", WF)
        co = {(t.state, t.action, t.next_state) for t in wf.transitions}
        for mong_doi in [
            ("Chờ xác nhận", "Gửi khách duyệt", STATE_KHACH),
            (STATE_KHACH, "Khách đồng ý", "Chờ Miyano xác nhận"),
            (STATE_KHACH, "Khách không đồng ý", "Chờ xác nhận"),
            ("Chờ Miyano xác nhận", "Xác nhận", "Đã xác nhận"),
        ]:
            with self.subTest(t=mong_doi):
                self.assertIn(mong_doi, co)

    def test_khong_transition_nao_mo_cho_role_customer(self):
        """Rào an toàn: role `Customer` lọt vào `allowed` là khách tự duyệt
        được đơn của chính mình từ Desk."""
        wf = frappe.get_doc("Workflow", WF)
        for t in wf.transitions:
            with self.subTest(t=f"{t.state}->{t.next_state}"):
                self.assertNotIn("Customer", (t.allowed or ""))

    def test_transition_cu_van_con_nguyen(self):
        """Không được dựng lại workflow — đơn nội bộ vẫn đi đường cũ (DoD)."""
        wf = frappe.get_doc("Workflow", WF)
        co = {(t.state, t.action, t.next_state) for t in wf.transitions}
        self.assertIn(("Chờ xác nhận", "Gửi duyệt", "Chờ Miyano xác nhận"), co)
        self.assertIn(("Chờ Miyano xác nhận", "Từ chối", "Từ chối"), co)
```

- [ ] **Step 2: Chạy để thấy FAIL**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e2_workflow_va_accept`
Expected: FAIL — thiếu state và 4 transition.

- [ ] **Step 3: Viết patch sửa workflow tại chỗ**

`miyano_portal/patches/v1_4/mo_rong_workflow_e2.py`:

```python
"""US-E2.5 — thêm state "Chờ khách đồng ý" và 4 transition vào workflow ĐANG CHẠY.

KHÔNG dùng `setup/install_workflow.install_portal_workflow()`: hàm đó thoát sớm
khi workflow đã tồn tại (`install_workflow.py:17-18`), nên nó không sửa được gì.

Idempotent theo NỘI DUNG: mỗi state/transition chỉ thêm khi chưa có đúng bộ
khoá của nó, nên chạy `migrate` bao nhiêu lần cũng không sinh dòng trùng.
"""

import frappe

WF = "Sales Order - Client Portal"
STATE_KHACH = "Chờ khách đồng ý"

TRANSITIONS = [
    ("Chờ xác nhận", "Gửi khách duyệt", STATE_KHACH, "Sales User"),
    (STATE_KHACH, "Khách đồng ý", "Chờ Miyano xác nhận", "System Manager"),
    (STATE_KHACH, "Khách không đồng ý", "Chờ xác nhận", "System Manager"),
    ("Chờ Miyano xác nhận", "Xác nhận", "Đã xác nhận", "Sales Manager"),
]


def execute():
    if not frappe.db.exists("Workflow", WF):
        # Site chưa cài workflow gốc (patch v1_0 chưa chạy) — không có gì để mở rộng.
        return

    if not frappe.db.exists("Workflow State", STATE_KHACH):
        frappe.get_doc(
            {"doctype": "Workflow State", "workflow_state_name": STATE_KHACH, "style": "Warning"}
        ).insert(ignore_permissions=True)
    for hanh_dong in ("Gửi khách duyệt", "Khách đồng ý", "Khách không đồng ý"):
        if not frappe.db.exists("Workflow Action Master", hanh_dong):
            frappe.get_doc(
                {"doctype": "Workflow Action Master", "workflow_action_name": hanh_dong}
            ).insert(ignore_permissions=True)

    wf = frappe.get_doc("Workflow", WF)
    thay_doi = False

    if not any(s.state == STATE_KHACH for s in wf.states):
        wf.append("states", {
            "state": STATE_KHACH,
            "doc_status": "0",
            "allow_edit": "Sales User",
        })
        thay_doi = True

    dang_co = {(t.state, t.action, t.next_state, t.allowed) for t in wf.transitions}
    for state, action, next_state, allowed in TRANSITIONS:
        if (state, action, next_state, allowed) not in dang_co:
            wf.append("transitions", {
                "state": state,
                "action": action,
                "next_state": next_state,
                "allowed": allowed,
            })
            thay_doi = True

    if thay_doi:
        wf.flags.ignore_permissions = True
        wf.save()
```

- [ ] **Step 4: Nối patch vào `patches.txt`**

Dùng cùng script nối-có-newline như Task 1, thêm dòng:
`miyano_portal.patches.v1_4.mo_rong_workflow_e2`

- [ ] **Step 5: Migrate hai lần rồi chạy test**

Run: `bench --site erptest.local migrate && bench --site erptest.local migrate && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e2_workflow_va_accept`
Expected: 4 PASS. Migrate lần hai **không** được sinh transition trùng — nếu `test_du_bon_transition_moi` xanh mà số dòng transition tăng gấp đôi thì patch chưa idempotent; kiểm bằng:

```bash
echo 'exec(open("/tmp/dem_tr.py").read(), {})' | bench --site erptest.local console
```
với `/tmp/dem_tr.py`:
```python
import frappe
wf = frappe.get_doc("Workflow", "Sales Order - Client Portal")
print("SO TRANSITION:", len(wf.transitions))   # phải là 7, không phải 11
```

- [ ] **Step 6: Commit**

```bash
git add miyano_portal/patches/v1_4/mo_rong_workflow_e2.py miyano_portal/patches.txt miyano_portal/tests/test_e2_workflow_va_accept.py
git commit -m "feat(portal): state 'Chờ khách đồng ý' + 4 transition (US-E2.5)"
```

---

## Task 4: Endpoint `portal_order_accept` (US-E2.5, API Spec §2.4)

**Files:**
- Modify: `miyano_portal/api/portal.py`
- Test: `miyano_portal/tests/test_e2_workflow_va_accept.py`

**Interfaces:**
- Consumes: state + transition từ Task 3; `get_portal_customer()` từ `portal_context`.
- Produces: `portal.portal_order_accept(order, action, ly_do=None) -> {"trang_thai_moi": str}`.

- [ ] **Step 1: Viết test thất bại** (thêm class)

```python
from miyano_portal.api import portal


class TestOrderAccept(FrappeTestCase):
    def setUp(self):
        seed_demo()
        self.so = _tao_so_cho_khach_duyet()   # helper dưới
        self.addCleanup(frappe.set_user, "Administrator")

    def test_dong_y_chuyen_sang_cho_miyano_xac_nhan(self):
        frappe.set_user("bvbm@demo.miyano")
        kq = portal.portal_order_accept(self.so.name, "dong_y")
        self.assertEqual(kq["trang_thai_moi"], "Chờ Miyano xác nhận")
        frappe.set_user("Administrator")
        self.assertEqual(
            frappe.db.get_value("Sales Order", self.so.name, "workflow_state"),
            "Chờ Miyano xác nhận",
        )

    def test_dong_y_ghi_log_nguoi_bam_vao_comment(self):
        frappe.set_user("bvbm@demo.miyano")
        portal.portal_order_accept(self.so.name, "dong_y")
        frappe.set_user("Administrator")
        cmt = frappe.get_all(
            "Comment",
            filters={"reference_doctype": "Sales Order", "reference_name": self.so.name},
            pluck="content",
        )
        self.assertTrue(
            any("bvbm@demo.miyano" in (c or "") for c in cmt),
            "phải ghi lại AI bấm đồng ý — không có log thì không truy được trách nhiệm",
        )

    def test_khong_dong_y_bat_buoc_ly_do(self):
        frappe.set_user("bvbm@demo.miyano")
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_accept(self.so.name, "khong_dong_y")

    def test_khong_dong_y_kem_ly_do_ve_cho_xac_nhan(self):
        frappe.set_user("bvbm@demo.miyano")
        kq = portal.portal_order_accept(
            self.so.name, "khong_dong_y", ly_do="Giá cao hơn dự toán của đơn vị."
        )
        self.assertEqual(kq["trang_thai_moi"], "Chờ xác nhận")

    # ---------- TC-E2-06 ----------
    def test_don_cua_khach_khac_bi_tu_choi_403(self):
        frappe.set_user("pxnabc@demo.miyano")
        with self.assertRaises(frappe.PermissionError):
            portal.portal_order_accept(self.so.name, "dong_y")
        frappe.set_user("Administrator")
        self.assertEqual(
            frappe.db.get_value("Sales Order", self.so.name, "workflow_state"),
            "Chờ khách đồng ý",
            "đơn không được đổi trạng thái khi bị chặn",
        )

    def test_don_khong_o_trang_thai_cho_khach_thi_chan(self):
        frappe.db.set_value("Sales Order", self.so.name, "workflow_state", "Chờ xác nhận")
        frappe.set_user("bvbm@demo.miyano")
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_accept(self.so.name, "dong_y")
```

Helper:

```python
def _tao_so_cho_khach_duyet():
    from miyano_portal.setup.seed_demo import PRICE_LIST
    so = frappe.new_doc("Sales Order")
    so.customer = "Bệnh viện Bạch Mai"
    so.transaction_date = frappe.utils.today()
    so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 7)
    so.selling_price_list = PRICE_LIST
    so.append("items", {
        "item_code": "VT0005", "qty": 1, "rate": 1200,
        "delivery_date": so.delivery_date,
    })
    so.taxes = []
    so.taxes_and_charges = None
    so.insert(ignore_permissions=True)
    # BẪY 4 — không gán workflow_state trước insert(). Xem Global Constraints.
    frappe.db.set_value(
        "Sales Order", so.name, "workflow_state", "Chờ khách đồng ý",
        update_modified=False,
    )
    so.reload()
    return so
```

- [ ] **Step 2: Chạy để thấy FAIL**

Expected: `AttributeError: module ... has no attribute 'portal_order_accept'`.

- [ ] **Step 3: Viết endpoint**

Thêm vào `api/portal.py`:

```python
LY_DO_TOI_THIEU_KHACH = 10


@frappe.whitelist()
def portal_order_accept(order, action, ly_do=None) -> dict:
    """US-E2.5 / API Spec §2.4 — khách đồng ý hoặc không đồng ý báo giá.

    Chuyển trạng thái chạy DƯỚI QUYỀN HỆ THỐNG: transition được mở cho
    `System Manager`, không phải cho role `Customer` — khách không bao giờ có
    quyền workflow trên Desk. Nhưng người bấm vẫn được ghi vào Comment, nếu
    không thì mọi thao tác đồng ý đều mang danh "Administrator" và không truy
    được ai đã đồng ý.
    """
    customer = get_portal_customer()
    so = frappe.get_doc("Sales Order", order)
    # `frappe.get_doc` KHÔNG chạy hook has_permission ở build này — phải tự kiểm.
    if so.customer != customer:
        raise frappe.PermissionError("Đơn hàng không thuộc đơn vị của bạn.")
    if so.get("workflow_state") != "Chờ khách đồng ý":
        frappe.throw(
            "Đơn này không ở trạng thái chờ quý khách đồng ý.", frappe.ValidationError
        )

    if action == "dong_y":
        hanh_dong, ghi_chu = "Khách đồng ý", ""
    elif action == "khong_dong_y":
        ly_do = (ly_do or "").strip()
        if len(ly_do) < LY_DO_TOI_THIEU_KHACH:
            frappe.throw(
                f"Vui lòng nêu lý do (tối thiểu {LY_DO_TOI_THIEU_KHACH} ký tự).",
                frappe.ValidationError,
            )
        hanh_dong, ghi_chu = "Khách không đồng ý", ly_do
    else:
        frappe.throw("Hành động không hợp lệ.", frappe.ValidationError)

    nguoi_bam = frappe.session.user
    from frappe.model.workflow import apply_workflow

    frappe.set_user("Administrator")
    try:
        so = apply_workflow(so, hanh_dong)
        noi_dung = f"{hanh_dong} bởi {nguoi_bam}"
        if ghi_chu:
            noi_dung += f" — lý do: {ghi_chu}"
        so.add_comment("Comment", noi_dung)
    finally:
        # Trả phiên về NGAY, kể cả khi apply_workflow ném: bỏ finally là để
        # phần còn lại của request chạy dưới quyền Administrator.
        frappe.set_user(nguoi_bam)

    return {"trang_thai_moi": so.get("workflow_state")}
```

- [ ] **Step 4: Chạy test**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e2_workflow_va_accept`
Expected: toàn bộ PASS (4 của Task 3 + 6 của Task 4).

- [ ] **Step 5: Commit**

```bash
git add miyano_portal/api/portal.py miyano_portal/tests/test_e2_workflow_va_accept.py
git commit -m "feat(portal): endpoint portal_order_accept (US-E2.5, API Spec §2.4)"
```

---

## Task 5: Email từ chối mang đúng lý do + cổng hiển thị lý do (US-E2.2 nửa còn lại)

**Files:**
- Create: `miyano_portal/patches/v1_4/sua_mail_tu_choi.py`
- Modify: `miyano_portal/patches.txt`, `miyano_portal/api/portal.py`
- Test: `miyano_portal/tests/test_e2_sla_va_trang_thai.py`

**Interfaces:**
- Consumes: `custom_ly_do_tu_choi` từ Task 1.
- Produces: `portal_order_track` trả thêm khoá `ly_do_tu_choi: str`.

- [ ] **Step 1: Viết test thất bại**

```python
"""US-E2.2 (email lý do), US-E2.3 (SLA), US-E2.4 (đóng sớm)."""
import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.api import portal
from miyano_portal.setup.seed_demo import seed_demo

MAIL_TU_CHOI = "Portal - Đơn bị từ chối"


class TestMailTuChoi(FrappeTestCase):
    def test_mail_co_chen_lay_do_tu_choi(self):
        msg = frappe.db.get_value("Notification", MAIL_TU_CHOI, "message")
        self.assertIn(
            "custom_ly_do_tu_choi", msg,
            "email từ chối phải mang đúng lý do (US-E2.2), không phải câu "
            "'liên hệ để biết thêm chi tiết'",
        )

    def test_mail_van_bat_va_dung_dieu_kien_cu(self):
        n = frappe.get_doc("Notification", MAIL_TU_CHOI)
        self.assertTrue(n.enabled)
        self.assertEqual(n.value_changed, "workflow_state")
        self.assertIn("Từ chối", n.condition)

    def test_order_track_tra_ly_do_tu_choi(self):
        so = _tao_so_bi_tu_choi("Hết hàng trong kho, dự kiến về ngày 20/08.")
        frappe.set_user("bvbm@demo.miyano")
        self.addCleanup(frappe.set_user, "Administrator")
        kq = portal.portal_order_track(so.name)
        self.assertIn("ngày 20/08", kq["ly_do_tu_choi"])
```

- [ ] **Step 2: Chạy để thấy FAIL**

Expected: FAIL cả ba — message hiện tại chưa có `custom_ly_do_tu_choi`, `portal_order_track` chưa có khoá.

- [ ] **Step 3: Viết patch sửa nội dung mail**

`miyano_portal/patches/v1_4/sua_mail_tu_choi.py`:

```python
"""US-E2.2 — email từ chối phải mang ĐÚNG lý do.

`setup/install_notifications.install_portal_notifications()` bỏ qua Notification
đã tồn tại (`continue` ở dòng 50-51), nên sửa DEFS trong file đó KHÔNG có tác
dụng trên site đã cài. Patch này sửa bản ghi tại chỗ.

Idempotent theo NỘI DUNG: chỉ ghi khi message hiện tại chưa chứa placeholder.
Cố ý không đụng `condition`, `event`, `recipients` — bản ghi này đang bật và
đang gửi mail thật, sửa quá tay là làm hỏng một luồng đang chạy.
"""

import frappe

TEN = "Portal - Đơn bị từ chối"

NOI_DUNG = """Kính gửi Quý khách,

Đơn hàng {{ doc.name }} đã bị Miyano từ chối.

Lý do: {{ doc.custom_ly_do_tu_choi }}

Quý khách vui lòng liên hệ nhân viên phụ trách nếu cần trao đổi thêm."""


def execute():
    if not frappe.db.exists("Notification", TEN):
        return
    hien_tai = frappe.db.get_value("Notification", TEN, "message") or ""
    if "custom_ly_do_tu_choi" in hien_tai:
        return
    doc = frappe.get_doc("Notification", TEN)
    doc.message = NOI_DUNG
    doc.flags.ignore_permissions = True
    doc.save()
```

- [ ] **Step 4: Trả lý do trong `portal_order_track`**

Trong `api/portal.py`, hàm `portal_order_track`, thêm vào dict trả về (cạnh khoá `hdnt`):

```python
        # US-E2.2 — khách phải đọc được lý do ngay trên chi tiết đơn, không
        # phải đi tìm lại email.
        "ly_do_tu_choi": so.get("custom_ly_do_tu_choi") or "",
```

- [ ] **Step 5: Nối patch, migrate, chạy test**

Thêm `miyano_portal.patches.v1_4.sua_mail_tu_choi` vào `patches.txt`, rồi:

Run: `bench --site erptest.local migrate && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e2_sla_va_trang_thai`
Expected: 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add miyano_portal/patches/v1_4/sua_mail_tu_choi.py miyano_portal/patches.txt miyano_portal/api/portal.py miyano_portal/tests/test_e2_sla_va_trang_thai.py
git commit -m "feat(portal): email từ chối mang đúng lý do + hiện trên cổng (US-E2.2)"
```

---

## Task 6: Job SLA quét đơn treo (US-E2.3, NL-2.6)

**Files:**
- Create: `miyano_portal/portal_sla.py`
- Modify: `miyano_portal/hooks.py`
- Test: `miyano_portal/tests/test_e2_sla_va_trang_thai.py`

**Interfaces:**
- Produces: `portal_sla.gio_lam_viec_troi_qua(tu_luc) -> float`, `portal_sla.quet_don_treo() -> int` (số đơn đã nhắc).

- [ ] **Step 1: Viết test thất bại** (thêm class)

```python
from miyano_portal.portal_sla import gio_lam_viec_troi_qua, quet_don_treo


class TestSLADonTreo(FrappeTestCase):
    def setUp(self):
        seed_demo()
        frappe.db.set_single_value("Miyano Portal Settings", "sla_xu_ly_don_gio", 8)
        frappe.db.delete("Notification Log", {"subject": ("like", "Portal - Đơn treo%")})

    # ---------- đếm giờ làm việc ----------
    def test_bo_qua_cuoi_tuan(self):
        """T6 17:00 -> T2 09:00 chỉ tính 16 giờ làm việc, không phải 64 giờ."""
        self.assertAlmostEqual(
            gio_lam_viec_troi_qua("2026-08-07 17:00:00", moc="2026-08-10 09:00:00"),
            16.0, delta=0.1,
        )

    def test_trong_tuan_tinh_binh_thuong(self):
        self.assertAlmostEqual(
            gio_lam_viec_troi_qua("2026-08-11 09:00:00", moc="2026-08-11 17:00:00"),
            8.0, delta=0.1,
        )

    # ---------- TC-E2-05 ----------
    # MOC cố định (Thứ Tư 16:00) để ca test không phụ thuộc lúc chạy. Dùng giờ
    # thực: chạy vào sáng Thứ Hai thì "9 giờ trước" rơi vào Chủ Nhật, số giờ
    # làm việc ra gần 0, và ca sẽ đỏ vì lịch chứ không vì code.
    MOC = "2026-08-12 16:00:00"

    def test_don_treo_qua_sla_thi_nhac_manager(self):
        so = _tao_so_treo("2026-08-12 07:00:00")   # 9 giờ làm việc trước MOC
        self.assertEqual(quet_don_treo(moc=self.MOC), 1)
        self.assertTrue(
            frappe.db.exists(
                "Notification Log", {"subject": ("like", f"%{so.name}%")}
            )
        )

    def test_don_chua_qua_sla_thi_im(self):
        _tao_so_treo("2026-08-12 13:00:00")        # 3 giờ trước MOC
        self.assertEqual(quet_don_treo(moc=self.MOC), 0)

    def test_moi_don_chi_nhac_mot_lan_moi_ngay(self):
        _tao_so_treo("2026-08-12 07:00:00")
        self.assertEqual(quet_don_treo(moc=self.MOC), 1)
        self.assertEqual(
            quet_don_treo(moc=self.MOC), 0, "chạy hourly mà nhắc mỗi giờ là spam"
        )

    def test_don_da_xac_nhan_khong_bi_nhac(self):
        so = _tao_so_treo("2026-08-12 07:00:00")
        frappe.db.set_value("Sales Order", so.name, "workflow_state", "Đã xác nhận")
        self.assertEqual(quet_don_treo(moc=self.MOC), 0)
```

Helper:

```python
def _tao_so_treo(cho_tu_luc: str):
    """Sales Order ở "Chờ Miyano xác nhận", `modified` đặt về `cho_tu_luc`.

    Lùi `modified` bằng SQL thẳng: `doc.save()` luôn đặt lại `modified` = bây
    giờ, nên không có cách nào dựng được đơn treo qua đường document bình thường.
    Nhận mốc TUYỆT ĐỐI chứ không nhận "số giờ trước" — số giờ trước phụ thuộc
    vào lúc chạy test, mốc tuyệt đối thì không.
    """
    from miyano_portal.setup.seed_demo import PRICE_LIST
    so = frappe.new_doc("Sales Order")
    so.customer = "Bệnh viện Bạch Mai"
    so.transaction_date = frappe.utils.today()
    so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 7)
    so.selling_price_list = PRICE_LIST
    so.append("items", {
        "item_code": "VT0005", "qty": 1, "rate": 1200,
        "delivery_date": so.delivery_date,
    })
    so.taxes = []
    so.taxes_and_charges = None
    so.insert(ignore_permissions=True)
    # BẪY 4 — không gán workflow_state trước insert(). Xem Global Constraints.
    # `update_modified=False` là BẮT BUỘC ở đây: job SLA tính giờ treo từ
    # `modified`, để set_value chạm vào nó là phá chính thứ đang thử.
    frappe.db.set_value(
        "Sales Order", so.name, "workflow_state", "Chờ Miyano xác nhận",
        update_modified=False,
    )
    frappe.db.sql(
        "update `tabSales Order` set modified=%s where name=%s", (cho_tu_luc, so.name)
    )
    return so
```

**Vì sao phải neo cả hai đầu:** `quet_don_treo` mặc định so với `now_datetime()`. Nếu test để mặc định thì kết quả đổi theo ngày trong tuần lúc chạy — đúng loại test xanh-đỏ thất thường mà người sau sẽ đánh dấu `skip` thay vì đi tìm nguyên nhân. Neo `modified` bằng mốc tuyệt đối **và** truyền `moc` cố định thì phép thử chỉ còn phụ thuộc vào code.

- [ ] **Step 2: Chạy để thấy FAIL**

Expected: `ModuleNotFoundError: miyano_portal.portal_sla`.

- [ ] **Step 3: Viết `portal_sla.py`**

```python
"""NL-2.6 — đơn treo quá SLA thì leo thang cho Sales Manager.

"Giờ làm việc" ở đây CHỈ bỏ Thứ Bảy và Chủ Nhật: không trừ ngày lễ, không có
khung giờ hành chính trong ngày. Đây là đúng quy ước đã dùng cho BR-O13
(`portal_dat_hang.ngay_giao_mac_dinh`) — một bảng ngày lễ không ai duy trì sẽ
sai lệch âm thầm, tệ hơn là không có vì nó tạo cảm giác đã được xử lý.
"""

import frappe
from frappe.utils import get_datetime, now_datetime

TRANG_THAI_TREO = "Chờ Miyano xác nhận"
TIEU_DE = "Portal - Đơn treo SLA"


def gio_lam_viec_troi_qua(tu_luc, moc=None) -> float:
    """Số giờ từ `tu_luc` tới `moc`, KHÔNG tính giờ rơi vào T7/CN."""
    dau = get_datetime(tu_luc)
    cuoi = get_datetime(moc) if moc else now_datetime()
    if cuoi <= dau:
        return 0.0
    tong = 0.0
    buoc = dau
    while buoc < cuoi:
        # Cắt theo từng mốc nửa đêm để không phải giả định gì về độ dài khoảng.
        het_ngay = get_datetime(buoc.date().isoformat() + " 23:59:59")
        ket = min(cuoi, het_ngay)
        if buoc.weekday() < 5:   # 0=T2 … 4=T6
            tong += (ket - buoc).total_seconds() / 3600.0
        buoc = get_datetime(
            frappe.utils.add_to_date(buoc.date().isoformat() + " 00:00:00", days=1)
        )
    return tong


def _sla_gio() -> float:
    return float(
        frappe.db.get_single_value("Miyano Portal Settings", "sla_xu_ly_don_gio") or 8
    )


def _nguoi_nhan() -> list[str]:
    return frappe.get_all(
        "Has Role",
        filters={"role": "Sales Manager", "parenttype": "User"},
        pluck="parent",
    )


def quet_don_treo(moc=None) -> int:
    """Quét đơn treo quá SLA, tạo Notification leo thang. Trả số đơn đã nhắc.

    Mỗi đơn tối đa MỘT lần mỗi ngày: job chạy hourly, không chặn thì mỗi đơn
    treo sẽ đẻ ra 24 thông báo một ngày và Sales Manager sẽ tắt hết thông báo.
    """
    sla = _sla_gio()
    nguoi_nhan = _nguoi_nhan()
    if not nguoi_nhan:
        return 0
    hom_nay = frappe.utils.nowdate()
    dem = 0
    for so in frappe.get_all(
        "Sales Order",
        filters={"workflow_state": TRANG_THAI_TREO, "docstatus": 0},
        fields=["name", "customer", "modified", "grand_total"],
    ):
        if gio_lam_viec_troi_qua(so.modified, moc=moc) < sla:
            continue
        tieu_de = f"{TIEU_DE}: {so.name}"
        da_nhac = frappe.db.exists(
            "Notification Log",
            {"subject": tieu_de, "creation": (">=", hom_nay + " 00:00:00")},
        )
        if da_nhac:
            continue
        for u in nguoi_nhan:
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": tieu_de,
                "for_user": u,
                "type": "Alert",
                "document_type": "Sales Order",
                "document_name": so.name,
                "email_content": (
                    f"Đơn {so.name} của {so.customer} đã chờ xác nhận quá "
                    f"{sla:g} giờ làm việc."
                ),
            }).insert(ignore_permissions=True)
        dem += 1
    return dem
```

- [ ] **Step 4: Bật scheduler hourly**

`hooks.py` — `scheduler_events` hiện đang **bị comment toàn bộ** (dòng 256-272). Thêm khai báo thật:

```python
scheduler_events = {
    "hourly": [
        "miyano_portal.portal_sla.quet_don_treo",
    ],
}
```

- [ ] **Step 5: Chạy test rồi toàn suite**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e2_sla_va_trang_thai && bench --site erptest.local run-tests --app miyano_portal`
Expected: tất cả xanh.

- [ ] **Step 6: Commit**

```bash
git add miyano_portal/portal_sla.py miyano_portal/hooks.py miyano_portal/tests/test_e2_sla_va_trang_thai.py
git commit -m "feat(portal): job SLA leo thang đơn treo (NL-2.6, US-E2.3)"
```

---

## Task 7: Báo cáo "Đơn chậm xử lý" (US-E2.3 nửa còn lại)

**Files:**
- Create: `miyano_portal/patches/v1_4/tao_bao_cao_don_cham.py`
- Modify: `miyano_portal/patches.txt`
- Test: `miyano_portal/tests/test_e2_sla_va_trang_thai.py`

**Interfaces:**
- Produces: Report `Đơn chậm xử lý` (Query Report, ref doctype `Sales Order`).

- [ ] **Step 1: Viết test thất bại** (thêm class)

```python
class TestBaoCaoDonCham(FrappeTestCase):
    def test_bao_cao_ton_tai_va_chay_duoc(self):
        from frappe.desk.query_report import run
        self.assertTrue(frappe.db.exists("Report", "Đơn chậm xử lý"))
        kq = run("Đơn chậm xử lý", ignore_prepared_report=True)
        self.assertIn("columns", kq)

    def test_bao_cao_chi_danh_cho_nhan_vien(self):
        """Role `Customer` mà đọc được báo cáo này là thấy đơn của khách khác."""
        roles = frappe.get_all(
            "Has Role", filters={"parent": "Đơn chậm xử lý", "parenttype": "Report"},
            pluck="role",
        )
        self.assertNotIn("Customer", roles)
        self.assertTrue(roles, "báo cáo không khai role nào là mặc định mở quá rộng")
```

- [ ] **Step 2: Chạy để thấy FAIL**

Expected: `Report "Đơn chậm xử lý"` chưa tồn tại.

- [ ] **Step 3: Viết patch tạo báo cáo**

`miyano_portal/patches/v1_4/tao_bao_cao_don_cham.py`:

```python
"""NL-2.6 — báo cáo đơn chậm xử lý cho Sales Manager.

Query Report thay vì Script Report: nội dung chỉ là một câu SELECT, và Script
Report phải nằm trong module có thư mục report/ trên đĩa — thêm một chỗ nữa
phải giữ đồng bộ mà không được lợi gì.
"""

import frappe

TEN = "Đơn chậm xử lý"

CAU_TRUY_VAN = """
select
    so.name            as "Đơn hàng:Link/Sales Order:140",
    so.customer        as "Khách hàng:Link/Customer:220",
    so.grand_total     as "Giá trị:Currency:120",
    so.modified        as "Chờ từ lúc:Datetime:160",
    round(timestampdiff(hour, so.modified, now()), 1) as "Số giờ treo:Float:110"
from `tabSales Order` so
where so.docstatus = 0
  and so.workflow_state = 'Chờ Miyano xác nhận'
order by so.modified asc
"""


def execute():
    if frappe.db.exists("Report", TEN):
        return
    frappe.get_doc({
        "doctype": "Report",
        "report_name": TEN,
        "ref_doctype": "Sales Order",
        "report_type": "Query Report",
        "module": "Miyano Portal",
        "is_standard": "No",
        "query": CAU_TRUY_VAN,
        "roles": [{"role": "Sales Manager"}, {"role": "Sales User"}],
    }).insert(ignore_permissions=True)
```

**Lưu ý:** cột "Số giờ treo" dùng `timestampdiff` giờ đồng hồ, **không** phải giờ làm việc — SQL không biết quy ước bỏ T7/CN. Đây là số để sắp xếp và nhìn nhanh; chốt chặn SLA thật nằm ở `portal_sla.gio_lam_viec_troi_qua`. Ghi chú này phải nằm trong docstring của patch để người sau không tưởng hai con số phải khớp nhau.

- [ ] **Step 4: Nối patch, migrate, chạy test**

Thêm `miyano_portal.patches.v1_4.tao_bao_cao_don_cham` vào `patches.txt`.

Run: `bench --site erptest.local migrate && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e2_sla_va_trang_thai`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add miyano_portal/patches/v1_4/tao_bao_cao_don_cham.py miyano_portal/patches.txt miyano_portal/tests/test_e2_sla_va_trang_thai.py
git commit -m "feat(portal): báo cáo Đơn chậm xử lý (NL-2.6)"
```

---

## Task 8: Đơn đóng sớm hiện đúng trạng thái (US-E2.4 nửa hiển thị, NL-2.8)

**Files:**
- Modify: `miyano_portal/api/portal.py:447-467`
- Test: `miyano_portal/tests/test_e2_sla_va_trang_thai.py`

**Interfaces:**
- Consumes: `_so_status_vi(so_status, per_delivered=None)`.
- Produces: cùng chữ ký, thêm nhánh `Closed`.

**Lỗi đang có:** `_so_status_vi` gộp `Cancelled` và `Closed` vào **"Đã huỷ"** (`portal.py:460-461`). Một đơn đã giao 60% rồi đóng sớm hiện ra với khách là "đã huỷ" — khách hiểu là không có gì được giao. NL-2.8 đòi "Hoàn thành (đóng sớm)".

- [ ] **Step 1: Viết test thất bại** (thêm class)

```python
from miyano_portal.api.portal import _so_status_vi


class TestTrangThaiDongSom(FrappeTestCase):
    def test_closed_khong_con_la_da_huy(self):
        """Đơn giao dở rồi đóng sớm KHÔNG phải đơn bị huỷ — khách đọc "Đã huỷ"
        sẽ tưởng chưa nhận được gì, trong khi đã nhận 60%."""
        self.assertEqual(_so_status_vi("Closed", per_delivered=60), "Hoàn thành (đóng sớm)")

    def test_closed_khi_chua_giao_gi_van_la_dong_som(self):
        self.assertEqual(_so_status_vi("Closed", per_delivered=0), "Hoàn thành (đóng sớm)")

    def test_cancelled_van_la_da_huy(self):
        self.assertEqual(_so_status_vi("Cancelled", per_delivered=0), "Đã huỷ")

    def test_cac_trang_thai_khac_khong_doi(self):
        self.assertEqual(_so_status_vi("Completed", per_delivered=100), "Hoàn thành")
        self.assertEqual(_so_status_vi("Draft", per_delivered=0), "Chờ xác nhận")
        self.assertEqual(_so_status_vi("To Deliver and Bill", per_delivered=30), "Đang giao")
```

- [ ] **Step 2: Chạy để thấy FAIL**

Expected: `AssertionError: 'Đã huỷ' != 'Hoàn thành (đóng sớm)'`.

- [ ] **Step 3: Sửa `_so_status_vi`**

Thay hai dòng 460-461 bằng:

```python
    if so_status == "Closed":
        # NL-2.8 — đóng sớm KHÁC huỷ: phần đã giao vẫn là hàng khách đã nhận.
        # Gộp chung vào "Đã huỷ" khiến khách tưởng không nhận được gì.
        # TODO(VĐ-7): phần chưa giao hiện KHÔNG được hoàn vào hạn mức Blanket
        # Order. Chỉ làm khi chủ đầu tư chốt cơ chế — xem BA §VĐ-7.
        return "Hoàn thành (đóng sớm)"
    if so_status == "Cancelled":
        return "Đã huỷ"
```

- [ ] **Step 4: Cập nhật bảng màu badge ở SPA**

`frontend/src/format.js`, hàm `statusBadge` — thêm khoá mới, nếu không badge sẽ rơi về xám mặc định:

```js
    'Hoàn thành (đóng sớm)': 'b-green',
```

- [ ] **Step 5: Chạy test, build, chạy toàn suite**

Run:
```bash
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e2_sla_va_trang_thai
cd apps/miyano_portal/frontend && yarn build && cd -
bench --site erptest.local run-tests --app miyano_portal
```
Expected: tất cả xanh, build sạch.

- [ ] **Step 6: Commit**

```bash
git add miyano_portal/api/portal.py frontend/src/format.js miyano_portal/public/frontend miyano_portal/tests/test_e2_sla_va_trang_thai.py
git commit -m "fix(portal): đơn đóng sớm không còn hiện là 'Đã huỷ' (NL-2.8)"
```

---

## Nghiệm thu toàn epic

- [ ] `bench --site erptest.local migrate` chạy **hai lần** liên tiếp, không lỗi, không sinh bản ghi trùng (đặc biệt: đếm transition của workflow = 7).
- [ ] Toàn suite xanh.
- [ ] TC-E2-01…06 đều có ca test tương ứng và đều xanh.
- [ ] Đơn nội bộ (không từ cổng) vẫn lập và xác nhận được như trước — chạy `bench --site erptest.local execute miyano_portal.setup.uat_runner.<hàm>` nếu có, hoặc lập thủ công một SO trên Desk.
- [ ] Nghiệm thu bằng mắt trên Desk: ô "Lý do từ chối" hiện trên form Sales Order; bấm Từ chối khi bỏ trống thì bị chặn kèm câu tiếng Việt.
- [ ] **Còn nợ có chủ ý:** hoàn hạn mức khi Close SO (VĐ-7) — TODO trong `_so_status_vi`.
