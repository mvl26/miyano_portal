# Báo giá theo đợt — Kế hoạch triển khai

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nhân viên Miyano báo giá một yêu cầu báo giá của cổng thành nhiều đợt; mỗi đợt là một Quotation con khách đồng ý/từ chối riêng, mặt hàng chưa báo nằm lại phiếu gốc để báo tiếp hoặc huỷ.

**Architecture:** Module mới `miyano_portal/bao_gia_theo_dot.py` chứa toàn bộ luật đợt (tách, trả dòng về, huỷ phần còn lại) và các hook Quotation mới. Workflow "Quotation - Client Portal" thêm 2 trạng thái + 3 bước chuyển; bước chuyển "do code" khai vai `Administrator` và được áp dưới `nang_quyen.quyen_he_thong()`. Cổng đọc đợt qua `portal_bao_gia_chi_tiet` (thêm `dot`/`con_lai`) và vẽ mỗi đợt bằng một component `KhoiBaoGia.vue` tách ra từ `ChiTietBaoGia.vue`.

**Tech Stack:** Frappe/ERPNext v15 (Python, MariaDB), Vue 3 + Vite (frontend cổng), `node --test` cho JS thuần, `bench run-tests` cho Python.

**Spec:** `docs/superpowers/specs/2026-10-15-bao-gia-theo-dot-design.md`

## Global Constraints

- Chỉ áp cho Quotation `custom_nguon_don = "Client Portal"` (D8). Báo giá nội bộ không đổi hành vi.
- Báo cả phiếu một lần (không tách đợt) chạy **y như hôm nay** (D6). Mọi test `test_bao_gia_*` hiện có phải xanh.
- Quy tắc "1 Quotation → 1 Sales Order" giữ nguyên (D1).
- Patch mới: `v1_45` (`miyano_portal.patches.v1_45.bao_gia_theo_dot`), chạy lại được (idempotent) vì `install.py::after_install` gọi lại mọi patch.
- `custom_request_id` của đợt = `<request_id gốc>:dot<N>`; đơn sinh từ đợt = `<request_id gốc>:dot<N>:don`.
- Lý do Miyano huỷ phần còn lại ≥ `bao_gia.LY_DO_TOI_THIEU` (10) ký tự; lý do của khách tuỳ chọn.
- Thụt lề giữ kiểu của từng file: **tab** ở `bao_gia.py`, `hooks.py`, `tests/*.py`, `public/js/quotation.js`, module mới `bao_gia_theo_dot.py`, patch mới; **4 dấu cách** ở `api/portal.py`, `setup/install_workflow.py`, `setup/install_notifications.py`; **2 dấu cách** ở `frontend/src/*`.
- Chú thích/docstring tiếng Việt, cùng mật độ với file xung quanh.
- Commit kết thúc bằng dòng `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Lệnh test Python chạy từ thư mục bench: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site localhost run-tests --app miyano_portal --module <module>`.
- Lệnh test JS: `cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal/frontend && yarn test`.

**Lệch nhỏ so với spec (có chủ đích, ghi lại để người duyệt biết):**
- Spec nói "kiểm trong `before_transition`". Frappe v15 không có hook đó; các chốt đặt ở hook `validate` (so trạng thái trước/sau), đúng khuôn `bao_gia.kiem_ly_do_tu_choi` đang dùng.
- `custom_ly_do_huy_con_lai` **không** read-only: nhân viên gõ lý do vào ô rồi bấm hành động "Huỷ phần còn lại", y như ô "Lý do từ chối" hiện nay. Chỉ hiện trên phiếu gốc của cổng (`depends_on`).
- Thêm một chốt spec chưa nói: phiếu gốc đã có đợt thì cũng chặn "Từ chối" (Miyano) — dùng "Huỷ phần còn lại". Không chặn thì dòng trả về rơi vào một phiếu đã từ chối.

## Review Focus

1. **Phiếu gốc rỗng dòng phải lưu được.** `Quotation.items` là bắt buộc (`reqd=1`); tách hết dòng thì phiếu gốc rỗng và mọi lần lưu sau (chuyển "Đã báo hết", nhận dòng trả về, huỷ phần còn lại) phải qua được. Test: `test_tach_het_dong_thanh_da_bao_het` và `test_dong_tra_ve_mo_lai_phieu_da_bao_het` (Task 2, Task 4).
2. **Hai nhân viên tách cùng lúc / bấm hai lần.** Dưới REPEATABLE READ, dòng con đọc thường có thể là ảnh chụp cũ sau khi chờ khoá; `tach_dot` phải đọc lại dòng bằng `for update`. Test: `test_tach_dong_khong_con_tren_phieu_bi_chan` + `test_tach_hai_lan_cung_dong_bi_chan` (Task 2).
3. **Nhân viên chỉ có vai Sales User bấm "Báo giá đợt này".** Bước "Hệ thống: đã báo hết" khai vai `Administrator`; nếu quên `quyen_he_thong()` thì nhân viên thường nhận "Not a valid Workflow Action". Test: `test_nhan_vien_sales_user_tach_het_duoc` (Task 2).
4. **Site chưa `bench migrate`** (mã mới, chưa có cột `custom_phieu_goc`): SQL danh sách cổng và hook Quotation không được ném lỗi 1054. Test: `test_danh_sach_khong_vo_khi_chua_co_cot` (Task 7) và `test_hook_bo_qua_khi_chua_co_cot` (Task 2).
5. **Liên kết thông báo/email trỏ tên đợt.** Email "Báo giá sẵn sàng" và Notification Log trỏ tới Quotation đợt; mở `/yeu-cau-bao-gia/<tên đợt>` phải ra trang phiếu gốc có đủ các đợt, không phải trang lỗi. Test: `test_chi_tiet_theo_ten_dot_tra_phieu_goc` (Task 7).

---

## File Structure

| File | Trách nhiệm |
|---|---|
| `miyano_portal/bao_gia.py` (sửa) | Hằng số trạng thái/hành động mới; `dong_y` ghi bảng `don_hang`; email hết hạn theo đợt. |
| `miyano_portal/bao_gia_theo_dot.py` (mới) | `tach_dot` (whitelist), `them_don_hang`, `huy_con_lai_boi_khach`, các hook: `cho_phep_phieu_goc_rong`, `kiem_chuyen_theo_dot`, `tra_dong_ve_khi_dot_dong`, `bao_khi_huy_con_lai`. |
| `miyano_portal/miyano_portal/doctype/portal_de_xuat_mua_don_hang/` (mới) | Child doctype `Portal De Xuat Mua Don Hang`. |
| `miyano_portal/miyano_portal/doctype/portal_de_xuat_mua/portal_de_xuat_mua.json` (sửa) | Thêm bảng `don_hang`. |
| `miyano_portal/setup/install_workflow.py` (sửa) | 2 trạng thái, 3 bước chuyển mới; `mo_rong_workflow_theo_dot()`. |
| `miyano_portal/setup/install_notifications.py` (sửa) | Tiêu đề "Báo giá sẵn sàng" có "(đợt N)". |
| `miyano_portal/patches/v1_45/bao_gia_theo_dot.py` (mới) + `patches.txt` | Patch dữ liệu. |
| `miyano_portal/hooks.py` (sửa) | Đăng ký 4 hook Quotation mới. |
| `miyano_portal/api/portal.py` (sửa) | Nhóm danh sách, đếm, chi tiết `dot`/`con_lai`, endpoint `portal_bao_gia_huy_con_lai`. |
| `miyano_portal/public/js/quotation.js` (sửa) | Nút "Báo giá đợt này", "Các đợt", lời giới thiệu trên đợt. |
| `frontend/src/bao-gia.js` + `bao-gia.test.mjs` (sửa) | `nhanDot()`. |
| `frontend/src/components/KhoiBaoGia.vue` (mới) | Một báo giá gửi khách (cả phiếu hoặc một đợt): hành động, bảng giá, sửa số lượng, PDF. |
| `frontend/src/views/ChiTietBaoGia.vue` (sửa) | Đầu trang + danh sách đợt + khối "Chờ Miyano báo giá" + huỷ phần còn lại. |
| `miyano_portal/public/frontend/*` (build) | Bản build cổng (đã commit trong repo). |
| `miyano_portal/tests/nen_bao_gia.py` (sửa) | Helper `NenBaoGiaTheoDot`, `_goc_ba_dong`. |
| `miyano_portal/tests/test_bao_gia_theo_dot_*.py` (mới) | Test theo task. |

---

### Task 1: Nền dữ liệu — trường, child doctype, workflow, patch v1_45

**Files:**
- Modify: `miyano_portal/bao_gia.py:20-37` (hằng số)
- Create: `miyano_portal/bao_gia_theo_dot.py` (chỉ `them_don_hang` + `san_sang` ở task này)
- Create: `miyano_portal/miyano_portal/doctype/portal_de_xuat_mua_don_hang/__init__.py`, `portal_de_xuat_mua_don_hang.json`, `portal_de_xuat_mua_don_hang.py`
- Modify: `miyano_portal/miyano_portal/doctype/portal_de_xuat_mua/portal_de_xuat_mua.json`
- Modify: `miyano_portal/setup/install_workflow.py:49-93` + hàm mới
- Modify: `miyano_portal/setup/install_notifications.py:158`
- Create: `miyano_portal/patches/v1_45/__init__.py`, `miyano_portal/patches/v1_45/bao_gia_theo_dot.py`
- Modify: `miyano_portal/patches.txt` (thêm dòng cuối)
- Modify: `miyano_portal/tests/nen_bao_gia.py`
- Modify: `miyano_portal/tests/test_bao_gia_workflow.py:33-34,170,176`, `miyano_portal/tests/test_bao_gia_cai_dat.py:107`
- Test: `miyano_portal/tests/test_bao_gia_theo_dot_patch.py`

**Interfaces:**
- Produces (bao_gia.py): `TT_DA_BAO_HET = "Đã báo hết"`, `TT_HUY_CON_LAI = "Đã huỷ phần còn lại"`, `HD_HUY_CON_LAI = "Huỷ phần còn lại"`, `HD_BAO_HET = "Hệ thống: đã báo hết"`, `HD_CON_HANG = "Hệ thống: có hàng trả về"`, `NGUOI_KHACH = "Khách"`.
- Produces (bao_gia_theo_dot.py): `san_sang() -> bool`, `them_don_hang(phieu: str, sales_order: str, bao_gia: str | None, so_dot: int) -> None`.
- Produces (install_workflow.py): `_canh_theo_dot() -> list[tuple]`, `mo_rong_workflow_theo_dot() -> bool`.
- Produces (patch): `them_truong()`, `cai_workflow()`, `cap_nhat_thong_bao()`, `chep_don_hang()`, `execute()`.
- Produces (tests/nen_bao_gia.py): lớp `NenBaoGiaTheoDot(NenBaoGia)` với `_goc_ba_dong(**them) -> Document` và `_nhan_vien(email) -> str`.

- [ ] **Step 1: Thêm hằng số vào `bao_gia.py`**

Ngay sau dòng `HD_MO_LAI = "Mở lại"` (dòng 37):

```python
HD_MO_LAI = "Mở lại"

# Báo giá theo đợt (spec 2026-10-15). Phiếu gốc đã tách hết dòng → "Đã báo
# hết"; dòng của một đợt bị từ chối/hết hạn quay về thì phiếu mở lại. Hai bước
# đó do CODE áp (`bao_gia_theo_dot`), khai vai `Administrator` nên nhân viên
# không thấy thành nút; code áp chúng dưới `nang_quyen.quyen_he_thong()`.
TT_DA_BAO_HET = "Đã báo hết"
TT_HUY_CON_LAI = "Đã huỷ phần còn lại"
HD_HUY_CON_LAI = "Huỷ phần còn lại"
HD_BAO_HET = "Hệ thống: đã báo hết"
HD_CON_HANG = "Hệ thống: có hàng trả về"
# Giá trị `custom_nguoi_huy_con_lai` khi khách huỷ trên cổng.
NGUOI_KHACH = "Khách"
```

- [ ] **Step 2: Tạo child doctype `Portal De Xuat Mua Don Hang`**

`miyano_portal/miyano_portal/doctype/portal_de_xuat_mua_don_hang/__init__.py`: file rỗng.

`portal_de_xuat_mua_don_hang.py`:

```python
"""Một đơn hàng sinh từ phiếu đề xuất (spec 2026-10-15 §3.3).

Báo giá theo đợt cho một phiếu ra NHIỀU đơn; `Portal De Xuat Mua.sales_order`
chỉ giữ đơn đầu tiên. Không có DocPerm riêng: đọc qua phiếu cha như
`Portal De Xuat Mua Item`."""

from frappe.model.document import Document


class PortalDeXuatMuaDonHang(Document):
	pass
```

`portal_de_xuat_mua_don_hang.json`:

```json
{
 "actions": [],
 "creation": "2026-10-16 00:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 1,
 "engine": "InnoDB",
 "field_order": ["sales_order", "bao_gia", "so_dot"],
 "fields": [
  {"fieldname": "sales_order", "fieldtype": "Link", "in_list_view": 1, "label": "Đơn hàng", "options": "Sales Order", "read_only": 1},
  {"fieldname": "bao_gia", "fieldtype": "Link", "in_list_view": 1, "label": "Báo giá (đợt)", "options": "Quotation", "read_only": 1},
  {"fieldname": "so_dot", "fieldtype": "Int", "in_list_view": 1, "label": "Đợt", "read_only": 1}
 ],
 "index_web_pages_for_search": 0,
 "istable": 1,
 "links": [],
 "modified": "2026-10-16 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Miyano Portal",
 "name": "Portal De Xuat Mua Don Hang",
 "owner": "Administrator",
 "permissions": [],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": []
}
```

- [ ] **Step 3: Thêm bảng `don_hang` vào `portal_de_xuat_mua.json`**

Trong `field_order`, chèn `"don_hang"` ngay sau `"bao_gia"`. Trong `fields`, chèn ngay sau định nghĩa field `bao_gia`:

```json
  {
   "fieldname": "don_hang",
   "fieldtype": "Table",
   "label": "Đơn hàng theo đợt",
   "options": "Portal De Xuat Mua Don Hang",
   "read_only": 1
  },
```

Đổi `"modified"` ở đầu file thành `"2026-10-16 00:00:00.000000"`.

- [ ] **Step 4: Tạo `bao_gia_theo_dot.py` với `san_sang` và `them_don_hang`**

```python
"""Báo giá theo đợt trên một yêu cầu báo giá (spec 2026-10-15).

Phiếu gốc là Quotation của cổng do `bao_gia.tao_bao_gia` dựng. Nhân viên tách
từng nhóm dòng ĐÃ CÓ GIÁ thành một Quotation con ("đợt", `custom_phieu_goc`)
đi nguyên workflow của `bao_gia`; phiếu gốc giữ phần chưa báo và không bao giờ
gửi khách nữa (D7). Mọi luật về đợt nằm ở module này; `bao_gia` chỉ gọi sang
ở `dong_y` (ghi bảng `don_hang`).
"""

import frappe

from miyano_portal import bao_gia

BANG_DON_HANG = "Portal De Xuat Mua Don Hang"

_san_sang_cache: bool | None = None


def san_sang() -> bool:
	"""Có cột `Quotation.custom_phieu_goc` THẬT chưa (patch v1_45). Cùng khuôn
	`bao_gia.san_sang()`: mã mới trên site chưa `bench migrate` không được ném
	1054 ở các hook chạy cho MỌI báo giá của cổng."""
	global _san_sang_cache
	if _san_sang_cache is None:
		_san_sang_cache = bool(frappe.db.has_column("Quotation", "custom_phieu_goc"))
	return _san_sang_cache


def them_don_hang(phieu: str, sales_order: str, bao_gia: str | None, so_dot: int) -> None:
	"""Ghi một dòng `don_hang` lên phiếu đề xuất; `sales_order` của phiếu chỉ
	đặt khi đang trống (luôn trỏ ĐƠN ĐẦU TIÊN — màn và báo cáo cũ đọc nó).

	Chèn thẳng dòng con, không lưu lại phiếu: lưu phiếu đi qua các chốt sửa
	phiếu (`_chan_sua_so_luong_de_xuat`…) không liên quan tới việc này. Chạy
	lại được: đơn đã có dòng thì thôi."""
	if frappe.db.table_exists(BANG_DON_HANG):
		if not frappe.db.exists(BANG_DON_HANG, {"parent": phieu, "sales_order": sales_order}):
			idx = frappe.db.sql(
				f"select coalesce(max(idx), 0) from `tab{BANG_DON_HANG}` where parent = %s", phieu
			)[0][0]
			frappe.get_doc({
				"doctype": BANG_DON_HANG, "parent": phieu, "parenttype": "Portal De Xuat Mua",
				"parentfield": "don_hang", "idx": int(idx) + 1, "sales_order": sales_order,
				"bao_gia": bao_gia, "so_dot": so_dot or 0,
			}).db_insert()
	if not frappe.db.get_value("Portal De Xuat Mua", phieu, "sales_order"):
		frappe.db.set_value("Portal De Xuat Mua", phieu, "sales_order", sales_order)
```

- [ ] **Step 5: Workflow — trạng thái, bước chuyển, hàm mở rộng**

Trong `miyano_portal/setup/install_workflow.py`, `_bao_gia_states()` thêm hai dòng cuối danh sách:

```python
        (bg.TT_HET_HAN, "0", "System Manager", "Danger"),
        # Báo giá theo đợt (spec 2026-10-15 §3.2). Cả hai giữ docstatus 0: phiếu
        # gốc luôn là nháp để dòng của đợt bị từ chối/hết hạn quay về được.
        (bg.TT_DA_BAO_HET, "0", "System Manager", "Info"),
        (bg.TT_HUY_CON_LAI, "0", "Sales Manager", "Danger"),
    ]
```

`_bao_gia_transitions()` đổi phần cuối thành:

```python
        _canh_mo_lai(),
        *_canh_theo_dot(),
    ]
```

Thêm ngay sau `_canh_mo_lai()`:

```python
def _canh_theo_dot():
    """Ba bước của báo giá theo đợt (spec 2026-10-15 §3.2), đứng SAU «Mở lại»
    vì `mo_rong_workflow_theo_dot()` nối chúng vào cuối workflow đã cài.

    Điều kiện "đã có ít nhất một đợt" giấu «Huỷ phần còn lại» trên phiếu chưa
    tách đợt (phiếu đó dùng «Từ chối» như cũ) — `apply_workflow` cũng lọc theo
    điều kiện nên không gọi lách được. Hai bước «Hệ thống: …» khai vai
    `Administrator`: chỉ code (`bao_gia_theo_dot`) áp chúng."""
    from miyano_portal import bao_gia as bg

    co_dot = 'frappe.db.get_value("Quotation", {"custom_phieu_goc": doc.name}, "name")'
    return [
        (bg.TT_CHO_MIYANO, bg.HD_HUY_CON_LAI, bg.TT_HUY_CON_LAI, "Sales User", co_dot),
        (bg.TT_CHO_MIYANO, bg.HD_BAO_HET, bg.TT_DA_BAO_HET, "Administrator", co_dot),
        (bg.TT_DA_BAO_HET, bg.HD_CON_HANG, bg.TT_CHO_MIYANO, "Administrator", None),
    ]
```

Thêm sau `mo_rong_workflow_bao_gia()`:

```python
def mo_rong_workflow_theo_dot() -> bool:
    """Thêm hai trạng thái và ba bước của báo giá theo đợt vào workflow ĐÃ CÀI.
    Cùng khuôn `mo_rong_workflow_bao_gia`: idempotent theo nội dung. Workflow
    State / Workflow Action Master do `install_quotation_workflow()` đảm bảo —
    gọi hàm đó trước."""
    from miyano_portal import bao_gia as bg

    if not frappe.db.exists("Workflow", bg.WORKFLOW):
        return False
    wf = frappe.get_doc("Workflow", bg.WORKFLOW)
    doi = False
    co_trang_thai = {s.state for s in wf.states}
    for ten, ds, vai, _kieu in _bao_gia_states():
        if ten not in co_trang_thai:
            wf.append("states", {"state": ten, "doc_status": ds, "allow_edit": vai})
            doi = True
    co_canh = {(t.state, t.action, t.next_state, t.allowed) for t in wf.transitions}
    for tu, hd, toi, vai, dk in _canh_theo_dot():
        if (tu, hd, toi, vai) not in co_canh:
            wf.append("transitions", {
                "state": tu, "action": hd, "next_state": toi, "allowed": vai,
                "condition": dk, "allow_self_approval": 1,
            })
            doi = True
    if doi:
        wf.flags.ignore_permissions = True
        wf.save()
    return doi
```

- [ ] **Step 6: Tiêu đề thông báo "Báo giá sẵn sàng" có số đợt**

`miyano_portal/setup/install_notifications.py:158`:

```python
        "subject": (
            "Báo giá {{ doc.name }}{% if doc.custom_so_dot %} (đợt "
            "{{ doc.custom_so_dot }}){% endif %} đã sẵn sàng"
        ),
```

- [ ] **Step 7: Viết patch v1_45**

`miyano_portal/patches/v1_45/__init__.py`: rỗng.

`miyano_portal/patches/v1_45/bao_gia_theo_dot.py`:

```python
"""Báo giá theo đợt (spec 2026-10-15 §3).

Chạy lại được: `install.py::after_install` gọi lại mọi patch.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def them_truong():
	frappe.reload_doc("miyano_portal", "doctype", "portal_de_xuat_mua_don_hang", force=True)
	frappe.reload_doc("miyano_portal", "doctype", "portal_de_xuat_mua", force=True)
	# Mọi trường `no_copy`: bản «Duplicate»/«Amend» trên Desk là báo giá nội bộ
	# bình thường (cùng lý do với bốn trường của patch v1_42).
	create_custom_fields({
		"Quotation": [
			{
				"fieldname": "custom_phieu_goc", "label": "Phiếu gốc (báo giá theo đợt)",
				"fieldtype": "Link", "options": "Quotation",
				"insert_after": "custom_ly_do_tu_choi", "read_only": 1, "no_copy": 1,
				"search_index": 1,
			},
			{
				"fieldname": "custom_so_dot", "label": "Đợt", "fieldtype": "Int",
				"insert_after": "custom_phieu_goc", "read_only": 1, "no_copy": 1,
			},
			{
				"fieldname": "custom_da_tra_ve", "label": "Đã trả mặt hàng về phiếu gốc",
				"fieldtype": "Check", "insert_after": "custom_so_dot", "read_only": 1,
				"no_copy": 1,
			},
			{
				# KHÔNG read-only: nhân viên gõ lý do rồi bấm «Huỷ phần còn lại»,
				# như ô «Lý do từ chối». Chỉ hiện trên phiếu gốc của cổng.
				"fieldname": "custom_ly_do_huy_con_lai", "label": "Lý do huỷ phần còn lại",
				"fieldtype": "Small Text", "insert_after": "custom_da_tra_ve", "no_copy": 1,
				"depends_on": "eval:doc.custom_nguon_don=='Client Portal' && !doc.custom_phieu_goc",
			},
			{
				"fieldname": "custom_nguoi_huy_con_lai", "label": "Người huỷ phần còn lại",
				"fieldtype": "Data", "insert_after": "custom_ly_do_huy_con_lai",
				"read_only": 1, "no_copy": 1,
			},
		],
	}, ignore_validate=True)


def cai_workflow():
	from miyano_portal.setup.install_workflow import (
		install_quotation_workflow,
		mo_rong_workflow_theo_dot,
	)

	# Đảm bảo Workflow State / Action Master mới (thoát sớm phần Workflow).
	install_quotation_workflow()
	mo_rong_workflow_theo_dot()
	frappe.clear_cache(doctype="Quotation")


def cap_nhat_thong_bao():
	"""`install_portal_notifications` bỏ qua thông báo đã có: ghi đè tiêu đề."""
	from miyano_portal.setup.install_notifications import DEFS, TEN_TB_BAO_GIA

	if frappe.db.exists("Notification", TEN_TB_BAO_GIA):
		tieu_de = next(d["subject"] for d in DEFS if d["name"] == TEN_TB_BAO_GIA)
		frappe.db.set_value("Notification", TEN_TB_BAO_GIA, "subject", tieu_de)


def chep_don_hang():
	"""Liên kết `sales_order`/`bao_gia` đang có của phiếu → một dòng `don_hang`."""
	from miyano_portal.bao_gia_theo_dot import them_don_hang

	for p in frappe.db.sql(
		"""select name, sales_order, bao_gia from `tabPortal De Xuat Mua`
		where coalesce(sales_order, '') != ''""",
		as_dict=True,
	):
		them_don_hang(p.name, p.sales_order, p.bao_gia or None, 0)


def execute():
	them_truong()
	cai_workflow()
	cap_nhat_thong_bao()
	chep_don_hang()
```

Cuối `miyano_portal/patches.txt` thêm:

```
miyano_portal.patches.v1_45.bao_gia_theo_dot
```

- [ ] **Step 8: Helper test `NenBaoGiaTheoDot`**

Cuối `miyano_portal/tests/nen_bao_gia.py`:

```python
class NenBaoGiaTheoDot(NenBaoGia):
	"""Nền cho test báo giá theo đợt (kế hoạch 2026-10-16)."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from miyano_portal.patches.v1_45 import bao_gia_theo_dot

		bao_gia_theo_dot.execute()

	def setUp(self):
		# Đợt trỏ về phiếu gốc bằng Link: xoá đợt TRƯỚC khi lớp cha xoá phiếu gốc.
		for ten in frappe.get_all(
			"Quotation",
			filters={"party_name": ["like", "_TEST DX%"], "custom_phieu_goc": ["is", "set"]},
			pluck="name",
		):
			frappe.db.set_value("Quotation", ten, "docstatus", 0, update_modified=False)
			frappe.delete_doc("Quotation", ten, force=True)
		super().setUp()

	def _goc_ba_dong(self, **them):
		"""Yêu cầu báo giá của cổng, ba mặt hàng đều đã có giá, ở «Chờ Miyano báo giá»."""
		gia = {self.item_ngoai: 54000, self.item_boi_so: 7000, self.item_co_dau: 12000}
		return self._bao_gia_tho(
			items=[
				{"item_code": ma, "qty": 10, "rate": g, "price_list_rate": g}
				for ma, g in gia.items()
			],
			**them,
		)

	def _nhan_vien(self, email="dot.nv@demo.miyano"):
		"""Nhân viên chỉ có vai Sales User."""
		if not frappe.db.exists("User", email):
			frappe.get_doc({
				"doctype": "User", "email": email, "first_name": "NV đợt",
				"send_welcome_email": 0, "roles": [{"role": "Sales User"}],
			}).insert(ignore_permissions=True)
		return email
```

- [ ] **Step 9: Viết test patch (thất bại trước)**

`miyano_portal/tests/test_bao_gia_theo_dot_patch.py`:

```python
"""Patch v1_45 — báo giá theo đợt (spec 2026-10-15 §3)."""

import frappe

from miyano_portal import bao_gia
from miyano_portal.patches.v1_45 import bao_gia_theo_dot as patch
from miyano_portal.setup import install_workflow
from miyano_portal.tests.nen_bao_gia import NenBaoGiaTheoDot


class TestPatchBaoGiaTheoDot(NenBaoGiaTheoDot):
	def test_truong_moi_tren_quotation(self):
		meta = frappe.get_meta("Quotation")
		for f in ("custom_phieu_goc", "custom_so_dot", "custom_da_tra_ve",
		          "custom_ly_do_huy_con_lai", "custom_nguoi_huy_con_lai"):
			self.assertTrue(meta.has_field(f), f)
			self.assertTrue(meta.get_field(f).no_copy, f)

	def test_bang_don_hang_tren_phieu(self):
		self.assertEqual(
			frappe.get_meta("Portal De Xuat Mua").get_field("don_hang").options,
			"Portal De Xuat Mua Don Hang",
		)

	def test_workflow_co_trang_thai_va_buoc_moi(self):
		wf = frappe.get_doc("Workflow", bao_gia.WORKFLOW)
		self.assertTrue({bao_gia.TT_DA_BAO_HET, bao_gia.TT_HUY_CON_LAI} <= {s.state for s in wf.states})
		canh = {(t.state, t.action, t.next_state, t.allowed) for t in wf.transitions}
		for tu, hd, toi, vai, _dk in install_workflow._canh_theo_dot():
			self.assertIn((tu, hd, toi, vai), canh)

	def test_chay_lai_khong_nhan_doi(self):
		wf = frappe.get_doc("Workflow", bao_gia.WORKFLOW)
		truoc = (len(wf.states), len(wf.transitions))
		patch.execute()
		frappe.clear_document_cache("Workflow", bao_gia.WORKFLOW)
		wf = frappe.get_doc("Workflow", bao_gia.WORKFLOW)
		self.assertEqual((len(wf.states), len(wf.transitions)), truoc)

	def test_site_cu_duoc_bo_sung(self):
		wf = frappe.get_doc("Workflow", bao_gia.WORKFLOW)
		moi = {bao_gia.TT_DA_BAO_HET, bao_gia.TT_HUY_CON_LAI}
		wf.set("states", [s for s in wf.states if s.state not in moi])
		wf.set("transitions", [
			t for t in wf.transitions if t.state not in moi and t.next_state not in moi
		])
		wf.flags.ignore_permissions = True
		wf.save()
		self.assertTrue(install_workflow.mo_rong_workflow_theo_dot())
		wf.reload()
		self.assertEqual((len(wf.states), len(wf.transitions)), (8, 12))

	def test_tieu_de_thong_bao_co_so_dot(self):
		from miyano_portal.setup.install_notifications import TEN_TB_BAO_GIA

		tieu_de = frappe.db.get_value("Notification", TEN_TB_BAO_GIA, "subject")
		bg = frappe._dict(name="SAL-QTN-X", custom_so_dot=2)
		self.assertEqual(frappe.render_template(tieu_de, {"doc": bg}), "Báo giá SAL-QTN-X (đợt 2) đã sẵn sàng")
		bg.custom_so_dot = 0
		self.assertEqual(frappe.render_template(tieu_de, {"doc": bg}), "Báo giá SAL-QTN-X đã sẵn sàng")

	def test_chep_sales_order_vao_don_hang_mot_lan(self):
		phieu = frappe.get_doc({
			"doctype": "Portal De Xuat Mua", "customer": self.kh_a,
			"khoa_phong": self.khoa_huyethoc, "ly_do_yeu_cau": "Hết hàng trong kho khoa",
			"trang_thai": "Đã duyệt",
			"items": [{"item_code": self.item_ngoai, "so_luong_de_xuat": 1, "so_luong_duyet": 1}],
		}).insert(ignore_permissions=True)
		frappe.db.set_value("Portal De Xuat Mua", phieu.name, "sales_order", "SO-DOT-PATCH-1")
		patch.chep_don_hang()
		patch.chep_don_hang()
		dong = frappe.get_all(
			"Portal De Xuat Mua Don Hang", filters={"parent": phieu.name},
			fields=["sales_order", "so_dot", "parenttype", "parentfield"],
		)
		self.assertEqual(len(dong), 1)
		self.assertEqual(dong[0].sales_order, "SO-DOT-PATCH-1")
		self.assertEqual((dong[0].parenttype, dong[0].parentfield), ("Portal De Xuat Mua", "don_hang"))
```

- [ ] **Step 10: Chạy test patch**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site localhost migrate && bench --site localhost run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_theo_dot_patch`
Expected: PASS 7/7. (Không có `migrate` thì bảng `tabPortal De Xuat Mua Don Hang` vẫn được `reload_doc` tạo trong `setUpClass`; migrate để site dev khớp.)

- [ ] **Step 11: Cập nhật số đếm trong test workflow cũ rồi chạy**

`miyano_portal/tests/test_bao_gia_workflow.py`: dòng 33 `6` → `8`; dòng 34 `9` → `12`; dòng 170 `8` → `11`; dòng 176 `9` → `12`.
`miyano_portal/tests/test_bao_gia_cai_dat.py:107`: `9` → `12`.

Run: `bench --site localhost run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_workflow && bench --site localhost run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_cai_dat && bench --site localhost run-tests --app miyano_portal --module miyano_portal.tests.test_patch_bao_gia_quotation`
Expected: PASS. Nếu một test khác so tiêu đề "Báo giá … đã sẵn sàng" bằng chuỗi cố định, sửa kỳ vọng sang tiêu đề mới của Step 6.

- [ ] **Step 12: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal
git add miyano_portal/bao_gia.py miyano_portal/bao_gia_theo_dot.py \
  miyano_portal/miyano_portal/doctype/portal_de_xuat_mua_don_hang \
  miyano_portal/miyano_portal/doctype/portal_de_xuat_mua/portal_de_xuat_mua.json \
  miyano_portal/setup/install_workflow.py miyano_portal/setup/install_notifications.py \
  miyano_portal/patches/v1_45 miyano_portal/patches.txt miyano_portal/tests/nen_bao_gia.py \
  miyano_portal/tests/test_bao_gia_theo_dot_patch.py miyano_portal/tests/test_bao_gia_workflow.py \
  miyano_portal/tests/test_bao_gia_cai_dat.py
git commit -m "feat(bao-gia): nen du lieu bao gia theo dot (patch v1_45)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Tách đợt (`tach_dot`) và các chốt trên phiếu gốc

**Files:**
- Modify: `miyano_portal/bao_gia_theo_dot.py`
- Modify: `miyano_portal/hooks.py:470-490` (Quotation `before_validate`, `validate`)
- Test: `miyano_portal/tests/test_bao_gia_theo_dot_tach.py`

**Interfaces:**
- Consumes: hằng số Task 1; `bao_gia._trang_thai_truoc(doc)`, `bao_gia.HD_GUI_KHACH`, `nang_quyen.quyen_he_thong()`.
- Produces: `tach_dot(phieu_goc: str, dong: list[str] | str) -> dict` (whitelist; trả `{"dot": str, "so_dot": int, "trang_thai_goc": str}`), `co_dot(ten: str) -> bool`, `la_phieu_goc_cong(doc) -> bool`, `_dong_moi(d) -> dict`, hook `cho_phep_phieu_goc_rong(doc, method=None)`, hook `kiem_chuyen_theo_dot(doc, method=None)`.

- [ ] **Step 1: Viết test (thất bại trước)**

`miyano_portal/tests/test_bao_gia_theo_dot_tach.py`:

```python
"""Tách đợt trên yêu cầu báo giá (spec 2026-10-15 §4.1)."""

from unittest.mock import patch

import frappe
from frappe.model.workflow import apply_workflow, get_transitions

from miyano_portal import bao_gia, bao_gia_theo_dot as dot
from miyano_portal.tests.nen_bao_gia import NenBaoGiaTheoDot


class TestTachDot(NenBaoGiaTheoDot):
	def _ten_dong(self, goc, *ma):
		return [d.name for d in goc.items if d.item_code in ma]

	def test_tach_hop_le(self):
		goc = self._goc_ba_dong()
		kq = dot.tach_dot(goc.name, self._ten_dong(goc, self.item_ngoai, self.item_boi_so))
		d1 = frappe.get_doc("Quotation", kq["dot"])
		self.assertEqual(kq["so_dot"], 1)
		self.assertEqual(d1.custom_phieu_goc, goc.name)
		self.assertEqual(d1.custom_so_dot, 1)
		self.assertEqual(d1.custom_request_id, goc.custom_request_id + ":dot1")
		self.assertEqual(d1.workflow_state, bao_gia.TT_CHO_KHACH)
		self.assertTrue(d1.valid_till)
		self.assertEqual(d1.custom_nguon_don, bao_gia.NGUON_CONG)
		self.assertEqual((d1.party_name, d1.custom_khoa_phong), (goc.party_name, goc.custom_khoa_phong))
		self.assertEqual(
			sorted((d.item_code, d.rate) for d in d1.items),
			sorted([(self.item_ngoai, 54000), (self.item_boi_so, 7000)]),
		)
		goc.reload()
		self.assertEqual([d.item_code for d in goc.items], [self.item_co_dau])
		self.assertEqual(goc.workflow_state, bao_gia.TT_CHO_MIYANO)
		self.assertEqual(kq["trang_thai_goc"], bao_gia.TT_CHO_MIYANO)

	def test_dot_thu_hai_tang_so(self):
		goc = self._goc_ba_dong()
		dot.tach_dot(goc.name, self._ten_dong(goc, self.item_ngoai))
		goc.reload()
		kq = dot.tach_dot(goc.name, self._ten_dong(goc, self.item_boi_so))
		self.assertEqual(kq["so_dot"], 2)
		self.assertTrue(kq["dot"])
		self.assertEqual(
			frappe.db.get_value("Quotation", kq["dot"], "custom_request_id"),
			goc.custom_request_id + ":dot2",
		)

	def test_tach_het_dong_thanh_da_bao_het(self):
		goc = self._goc_ba_dong()
		kq = dot.tach_dot(goc.name, [d.name for d in goc.items])
		goc.reload()
		self.assertEqual(goc.items, [])
		self.assertEqual(goc.workflow_state, bao_gia.TT_DA_BAO_HET)
		self.assertEqual(kq["trang_thai_goc"], bao_gia.TT_DA_BAO_HET)

	def test_con_dong_go_tay_chua_khop_thi_khong_bao_het(self):
		goc = self._goc_ba_dong(custom_dat_ngoai=[
			{"ten_hang": "Kim lạ chưa có mã", "dvt": "Cái", "so_luong": 2},
		])
		dot.tach_dot(goc.name, [d.name for d in goc.items])
		goc.reload()
		self.assertEqual(goc.workflow_state, bao_gia.TT_CHO_MIYANO)

	def test_dong_thieu_gia_bi_chan(self):
		goc = self._goc_ba_dong()
		goc.items[0].rate = goc.items[0].price_list_rate = 0
		goc.save()
		with self.assertRaisesRegex(frappe.ValidationError, "Chưa có đơn giá"):
			dot.tach_dot(goc.name, [goc.items[0].name])
		self.assertFalse(frappe.db.exists("Quotation", {"custom_phieu_goc": goc.name}))

	def test_tach_dong_khong_con_tren_phieu_bi_chan(self):
		goc = self._goc_ba_dong()
		with self.assertRaisesRegex(frappe.ValidationError, "đã được báo ở đợt khác"):
			dot.tach_dot(goc.name, ["khong-ton-tai-123"])

	def test_tach_hai_lan_cung_dong_bi_chan(self):
		goc = self._goc_ba_dong()
		chon = self._ten_dong(goc, self.item_ngoai)
		dot.tach_dot(goc.name, chon)
		with self.assertRaisesRegex(frappe.ValidationError, "đã được báo ở đợt khác"):
			dot.tach_dot(goc.name, chon)
		self.assertEqual(
			frappe.db.count("Quotation", {"custom_phieu_goc": goc.name}), 1
		)

	def test_loi_giua_chung_lui_ca_ba_buoc(self):
		goc = self._goc_ba_dong()
		chon = self._ten_dong(goc, self.item_ngoai)

		# Hỏng đúng ở bước CUỐI (gửi khách đợt): đợt đã chèn, dòng đã xoá khỏi
		# phiếu gốc — cả hai phải lùi. Frappe tra hook theo chuỗi mỗi lần gọi
		# nên `patch` thay được.
		def hong_khi_gui_khach(doc, method=None):
			if doc.get("workflow_state") == bao_gia.TT_CHO_KHACH:
				raise frappe.ValidationError("hỏng")

		with patch("miyano_portal.bao_gia.chot_gui_khach", side_effect=hong_khi_gui_khach):
			with self.assertRaises(frappe.ValidationError):
				dot.tach_dot(goc.name, chon)
		goc.reload()
		self.assertEqual(len(goc.items), 3)
		self.assertFalse(frappe.db.exists("Quotation", {"custom_phieu_goc": goc.name}))

	def test_chi_tach_tren_phieu_goc_cua_cong_dang_cho_miyano(self):
		noi_bo = self._goc_ba_dong(nguon="Nội bộ")
		with self.assertRaises(frappe.ValidationError):
			dot.tach_dot(noi_bo.name, [noi_bo.items[0].name])
		goc = self._goc_ba_dong()
		kq = dot.tach_dot(goc.name, [goc.items[0].name])
		d1 = frappe.get_doc("Quotation", kq["dot"])
		with self.assertRaises(frappe.ValidationError):
			dot.tach_dot(d1.name, [d1.items[0].name])

	def test_dong_rong_bi_chan(self):
		goc = self._goc_ba_dong()
		for xau in ([], "[]", "khong-phai-json", [1, 2], None):
			with self.assertRaises(frappe.ValidationError):
				dot.tach_dot(goc.name, xau)

	def test_chan_gui_khach_va_tu_choi_tren_phieu_goc_da_co_dot(self):
		goc = self._goc_ba_dong()
		dot.tach_dot(goc.name, [goc.items[0].name])
		goc.reload()
		with self.assertRaisesRegex(frappe.ValidationError, "Báo giá đợt này"):
			apply_workflow(goc, bao_gia.HD_GUI_KHACH)
		goc.reload()
		goc.custom_ly_do_tu_choi = "Không còn nhà cung cấp nào"
		goc.save()
		with self.assertRaisesRegex(frappe.ValidationError, "Huỷ phần còn lại"):
			apply_workflow(goc, bao_gia.HD_TU_CHOI)

	def test_phieu_chua_tach_khong_thay_huy_con_lai_va_bao_het(self):
		goc = self._goc_ba_dong()
		hd = {t["action"] for t in get_transitions(goc)}
		self.assertNotIn(bao_gia.HD_HUY_CON_LAI, hd)
		self.assertNotIn(bao_gia.HD_BAO_HET, hd)

	def test_nhan_vien_sales_user_tach_het_duoc(self):
		goc = self._goc_ba_dong()
		frappe.set_user(self._nhan_vien())
		try:
			kq = dot.tach_dot(goc.name, [d.name for d in goc.items])
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(kq["trang_thai_goc"], bao_gia.TT_DA_BAO_HET)

	def test_khong_xoa_duoc_phieu_goc_con_dot(self):
		goc = self._goc_ba_dong()
		dot.tach_dot(goc.name, [goc.items[0].name])
		with self.assertRaises(frappe.LinkExistsError):
			frappe.delete_doc("Quotation", goc.name)

	def test_hook_bo_qua_khi_chua_co_cot(self):
		goc = self._goc_ba_dong()
		with patch.object(dot, "san_sang", return_value=False):
			goc.custom_ten_don_hang = "Lưu khi chưa migrate"
			goc.save()
			self.assertFalse(dot.co_dot(goc.name))
```

- [ ] **Step 2: Chạy test, xác nhận thất bại**

Run: `bench --site localhost run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_theo_dot_tach`
Expected: FAIL — `AttributeError: module 'miyano_portal.bao_gia_theo_dot' has no attribute 'tach_dot'`.

- [ ] **Step 3: Cài đặt trong `bao_gia_theo_dot.py`**

Thêm `from frappe.utils import flt` vào khối import. Thêm sau `them_don_hang`:

```python
# Trường đầu phiếu chép từ phiếu gốc sang đợt (spec §3.1). Các `custom_*` là
# `no_copy` nên KHÔNG dùng `frappe.copy_doc`: dựng đợt tường minh.
TRUONG_DAU_PHIEU = (
	"quotation_to", "party_name", "company", "currency", "selling_price_list",
	"order_type", "customer_address", "shipping_address_name", "contact_person",
	"contact_email", "custom_nguon_don", "custom_de_xuat", "custom_khoa_phong",
	"custom_ten_don_hang",
)
# Trường của một dòng hàng khi đi từ phiếu gốc sang đợt và ngược lại.
TRUONG_DONG = (
	"item_code", "item_name", "description", "qty", "rate", "uom", "stock_uom",
	"conversion_factor", "warehouse", "custom_nguon_gia",
)


def _dong_moi(d) -> dict:
	kq = {t: d.get(t) for t in TRUONG_DONG}
	# BẪY ERPNext (xem `bao_gia.tao_bao_gia`): `price_list_rate` phải tường minh,
	# không thì `set_missing_item_details` tra bảng giá và thay đơn giá vừa báo.
	kq["price_list_rate"] = flt(d.get("rate"))
	return kq


def la_phieu_goc_cong(doc) -> bool:
	return doc.get("custom_nguon_don") == bao_gia.NGUON_CONG and not doc.get("custom_phieu_goc")


def co_dot(ten: str) -> bool:
	"""Phiếu `ten` đã tách ít nhất một đợt."""
	if not ten or not san_sang():
		return False
	return bool(frappe.db.exists("Quotation", {"custom_phieu_goc": ten}))


def _con_dong_chua_bao(goc) -> bool:
	"""Còn dòng hàng, hoặc còn dòng khách gõ tay chưa khớp mã (§4.1 bước 3, 5)."""
	return bool(goc.get("items")) or any(
		not d.get("da_xu_ly") for d in goc.get("custom_dat_ngoai") or []
	)


def cho_phep_phieu_goc_rong(doc, method=None) -> None:
	"""Hook `before_validate` của Quotation. `items` là bắt buộc; phiếu gốc đã
	tách hết dòng sang các đợt thì rỗng là ĐÚNG — lưu nó (chuyển "Đã báo hết",
	nhận dòng trả về, huỷ phần còn lại) không được vấp chốt bắt buộc. Chạy ở
	`before_validate` vì Frappe kiểm bắt buộc ngay sau bước đó."""
	if doc.get("items") or doc.is_new() or not la_phieu_goc_cong(doc):
		return
	if co_dot(doc.name):
		doc.flags.ignore_mandatory = True


def kiem_chuyen_theo_dot(doc, method=None) -> None:
	"""Hook `validate` của Quotation — các chốt chuyển trạng thái của báo giá
	theo đợt (spec §3.2, §4.1, §4.3). Frappe v15 không có `before_transition`:
	so trạng thái trước/sau như `bao_gia.kiem_ly_do_tu_choi`."""
	if doc.is_new() or doc.get("custom_nguon_don") != bao_gia.NGUON_CONG or not san_sang():
		return
	truoc, nay = bao_gia._trang_thai_truoc(doc), doc.get("workflow_state")
	if truoc == nay:
		return
	if doc.get("custom_da_tra_ve"):
		frappe.throw(
			f"Đợt {doc.name} đã trả các mặt hàng về phiếu gốc {doc.custom_phieu_goc} — "
			"không mở lại được. Muốn báo lại thì tách đợt mới từ phiếu gốc.",
			frappe.ValidationError,
		)
	if doc.get("custom_phieu_goc") or not co_dot(doc.name):
		return
	if nay in (bao_gia.TT_CHO_KHACH, bao_gia.TT_MIYANO_TU_CHOI):
		frappe.throw(
			"Phiếu đã báo theo đợt — dùng nút «Báo giá đợt này» để gửi khách các mặt "
			"hàng còn lại, hoặc «Huỷ phần còn lại» nếu không báo nữa.",
			frappe.ValidationError,
		)


def _dung_dot(goc, dong: list, so_dot: int):
	d = frappe.new_doc("Quotation")
	for t in TRUONG_DAU_PHIEU:
		if goc.get(t) is not None:
			d.set(t, goc.get(t))
	d.transaction_date = frappe.utils.today()
	d.ignore_pricing_rule = 1
	d.custom_phieu_goc = goc.name
	d.custom_so_dot = so_dot
	d.custom_request_id = f"{goc.custom_request_id}:dot{so_dot}"
	for hang in dong:
		d.append("items", _dong_moi(hang))
	d.insert()
	return d


@frappe.whitelist()
def tach_dot(phieu_goc, dong) -> dict:
	"""Desk — «Báo giá đợt này» (spec §4.1). Tạo đợt từ các dòng `dong` (tên
	dòng `Quotation Item` của phiếu gốc), xoá chúng khỏi phiếu gốc và gửi khách
	đợt đó: MỘT đơn vị, hỏng bước nào lùi cả ba."""
	from frappe.model.workflow import apply_workflow

	from miyano_portal.nang_quyen import quyen_he_thong

	if isinstance(dong, str):
		try:
			dong = frappe.parse_json(dong)
		except ValueError:
			dong = None
	if (
		not isinstance(phieu_goc, str) or not isinstance(dong, list) or not dong
		or not all(isinstance(x, str) for x in dong)
	):
		frappe.throw("Chọn ít nhất một mặt hàng để báo giá đợt này.", frappe.ValidationError)

	goc = frappe.get_doc("Quotation", phieu_goc, for_update=True)
	goc.check_permission("write")
	if not la_phieu_goc_cong(goc) or not goc.get("custom_request_id"):
		frappe.throw(
			"Chỉ tách đợt được trên yêu cầu báo giá của cổng khách hàng (không tách từ một đợt).",
			frappe.ValidationError,
		)
	if goc.docstatus != 0 or goc.get("workflow_state") != bao_gia.TT_CHO_MIYANO:
		frappe.throw(
			f"Phiếu phải ở «{bao_gia.TT_CHO_MIYANO}» mới tách đợt được.", frappe.ValidationError
		)

	chon = list(dict.fromkeys(dong))
	# Đọc lại dòng bằng `for update`: dưới REPEATABLE READ, `goc.items` của
	# request thứ hai (chờ khoá phiếu gốc xong) là ẢNH CHỤP CŨ — vẫn thấy các
	# dòng request đầu đã chuyển sang đợt.
	con_that = set(frappe.db.sql_list(
		"select name from `tabQuotation Item` where parent = %s and parenttype = 'Quotation' "
		"and name in %s for update",
		(goc.name, tuple(chon)),
	))
	theo_ten = {d.name: d for d in goc.items if d.name in con_that}
	if any(t not in theo_ten for t in chon):
		frappe.throw(
			"Có mặt hàng đã được báo ở đợt khác hoặc không còn trên phiếu — tải lại "
			"phiếu rồi chọn lại.",
			frappe.ValidationError,
		)
	thieu_gia = [theo_ten[t].item_code for t in chon if flt(theo_ten[t].rate) <= 0]
	if thieu_gia:
		frappe.throw("Chưa có đơn giá: " + ", ".join(thieu_gia) + ".", frappe.ValidationError)

	so_dot = int(frappe.db.sql(
		"select coalesce(max(custom_so_dot), 0) from `tabQuotation` "
		"where custom_phieu_goc = %s for update",
		goc.name,
	)[0][0]) + 1
	nguoi_bam = frappe.session.user
	frappe.db.savepoint("tach_dot")
	try:
		d = _dung_dot(goc, [theo_ten[t] for t in chon], so_dot)
		bo = set(chon)
		goc.set("items", [h for h in goc.items if h.name not in bo])
		for i, h in enumerate(goc.items, 1):
			h.idx = i
		goc.save()
		d = apply_workflow(d, bao_gia.HD_GUI_KHACH)
		if not _con_dong_chua_bao(goc):
			with quyen_he_thong():
				goc = apply_workflow(goc, bao_gia.HD_BAO_HET)
		goc.add_comment(
			"Comment",
			f"Tách đợt {so_dot} ({len(chon)} mặt hàng) → {d.name}, gửi khách bởi {nguoi_bam}",
		)
	except Exception:
		frappe.db.rollback(save_point="tach_dot")
		raise
	return {"dot": d.name, "so_dot": so_dot, "trang_thai_goc": goc.get("workflow_state")}
```

- [ ] **Step 4: Đăng ký hook**

`miyano_portal/hooks.py`, khối `"Quotation"`:

```python
		"before_validate": [
			# Khớp mã cho dòng khách gõ tay: chuyển thành dòng hàng thật.
			"miyano_portal.portal_mua_le.chuyen_dong_dat_ngoai_thanh_hang",
			# Phiếu gốc đã tách hết dòng sang các đợt được phép rỗng `items`.
			# SAU phép chuyển ở trên: phép đó có thể vừa thêm dòng.
			"miyano_portal.bao_gia_theo_dot.cho_phep_phieu_goc_rong",
		],
		"validate": [
			# Thứ tự có nghĩa: `dong_bo…` tính `da_xu_ly` mà `chot_gui_khach` đọc.
			"miyano_portal.portal_mua_le.dong_bo_da_xu_ly_dat_ngoai",
			"miyano_portal.bao_gia.kiem_ly_do_tu_choi",
			"miyano_portal.bao_gia.chot_gui_khach",
			# Báo giá theo đợt: chặn gửi khách/từ chối trên phiếu gốc đã có
			# đợt, chặn mở lại đợt đã trả dòng về, kiểm «Huỷ phần còn lại».
			"miyano_portal.bao_gia_theo_dot.kiem_chuyen_theo_dot",
		],
```

- [ ] **Step 5: Chạy test**

Run: `bench --site localhost run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_theo_dot_tach`
Expected: PASS 15/15.

Nếu `test_tach_het_dong_thanh_da_bao_het` hỏng trong `calculate_taxes_and_totals`/`make_packing_list` của ERPNext với `items` rỗng: đọc traceback, đặt cờ bỏ qua đúng phép tính đó trong `cho_phep_phieu_goc_rong` (không bỏ cả `validate`), ghi lý do vào docstring.

- [ ] **Step 6: Chạy hồi quy báo giá**

Run: `for m in test_bao_gia_gui_khach test_bao_gia_tu_choi_sua test_bao_gia_workflow test_tao_bao_gia; do bench --site localhost run-tests --app miyano_portal --module miyano_portal.tests.$m || break; done`
Expected: PASS hết.

- [ ] **Step 7: Commit**

```bash
git add miyano_portal/bao_gia_theo_dot.py miyano_portal/hooks.py miyano_portal/tests/test_bao_gia_theo_dot_tach.py
git commit -m "feat(bao-gia): tach dot tu yeu cau bao gia cua cong

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Khách đồng ý một đợt → đơn + bảng `don_hang`

**Files:**
- Modify: `miyano_portal/bao_gia.py:577-580` (`dong_y`)
- Test: `miyano_portal/tests/test_bao_gia_theo_dot_dong_y.py`

**Interfaces:**
- Consumes: `bao_gia_theo_dot.them_don_hang(phieu, sales_order, bao_gia, so_dot)`, `bao_gia_theo_dot.tach_dot`.
- Produces: `dong_y(ten)` không đổi chữ ký; ghi `don_hang` thay vì ghi đè `sales_order`.

- [ ] **Step 1: Viết test (thất bại trước)**

`miyano_portal/tests/test_bao_gia_theo_dot_dong_y.py`:

```python
"""Khách đồng ý một đợt (spec 2026-10-15 §4.2)."""

import frappe
from frappe.utils import add_days, nowdate

from miyano_portal import bao_gia, bao_gia_theo_dot as dot
from miyano_portal.tests.nen_bao_gia import NenBaoGiaTheoDot


class TestDongYDot(NenBaoGiaTheoDot):
	def setUp(self):
		super().setUp()
		self.ql = self._quan_ly("dotdy.ql@demo.miyano", self.kh_a)
		self.phieu = frappe.get_doc({
			"doctype": "Portal De Xuat Mua", "customer": self.kh_a,
			"khoa_phong": self.khoa_huyethoc, "ly_do_yeu_cau": "Hết hàng trong kho khoa",
			"ngay_can": add_days(nowdate(), 10), "trang_thai": "Đã duyệt",
			"items": [{"item_code": self.item_ngoai, "so_luong_de_xuat": 10, "so_luong_duyet": 10}],
		}).insert(ignore_permissions=True)
		self.goc = self._goc_ba_dong(custom_de_xuat=self.phieu.name)
		frappe.db.set_value("Portal De Xuat Mua", self.phieu.name, "bao_gia", self.goc.name)

	def _dong_y(self, ten):
		frappe.set_user(self.ql)
		try:
			return bao_gia.dong_y(ten)
		finally:
			frappe.set_user("Administrator")

	def _tach(self, ma):
		self.goc.reload()
		return dot.tach_dot(self.goc.name, [d.name for d in self.goc.items if d.item_code == ma])["dot"]

	def test_dong_y_dot_sinh_don_dung_ma_yeu_cau(self):
		d1 = self._tach(self.item_ngoai)
		kq = self._dong_y(d1)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(so.custom_request_id, self.goc.custom_request_id + ":dot1:don")
		self.assertEqual([d.item_code for d in so.items], [self.item_ngoai])
		self.assertEqual(bao_gia.bao_gia_cua_don(so), d1)

	def test_hai_dot_hai_don_bang_don_hang(self):
		d1 = self._tach(self.item_ngoai)
		so1 = self._dong_y(d1)["sales_order"]
		d2 = self._tach(self.item_boi_so)
		so2 = self._dong_y(d2)["sales_order"]
		self.assertNotEqual(so1, so2)
		# `sales_order` của phiếu giữ ĐƠN ĐẦU TIÊN.
		self.assertEqual(frappe.db.get_value("Portal De Xuat Mua", self.phieu.name, "sales_order"), so1)
		dong = frappe.get_all(
			"Portal De Xuat Mua Don Hang", filters={"parent": self.phieu.name},
			fields=["sales_order", "bao_gia", "so_dot"], order_by="idx asc",
		)
		self.assertEqual(
			[(r.sales_order, r.bao_gia, r.so_dot) for r in dong],
			[(so1, d1, 1), (so2, d2, 2)],
		)

	def test_bao_gia_khong_tach_dot_van_nhu_cu(self):
		goc = self._goc_ba_dong(custom_de_xuat=self.phieu.name)
		from frappe.model.workflow import apply_workflow

		apply_workflow(goc, bao_gia.HD_GUI_KHACH)
		so = self._dong_y(goc.name)["sales_order"]
		self.assertEqual(frappe.db.get_value("Portal De Xuat Mua", self.phieu.name, "sales_order"), so)
		self.assertEqual(
			frappe.get_all("Portal De Xuat Mua Don Hang", filters={"parent": self.phieu.name},
			               pluck="so_dot"),
			[0],
		)
```

- [ ] **Step 2: Chạy, xác nhận thất bại**

Run: `bench --site localhost run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_theo_dot_dong_y`
Expected: FAIL ở `test_hai_dot_hai_don_bang_don_hang` (`sales_order` bị ghi đè bằng `so2`, bảng `don_hang` rỗng).

- [ ] **Step 3: Sửa `dong_y`**

`miyano_portal/bao_gia.py`, thay khối:

```python
			if bg.get("custom_de_xuat"):
				frappe.db.set_value(
					"Portal De Xuat Mua", bg.custom_de_xuat, "sales_order", so.name
				)
```

bằng:

```python
			if bg.get("custom_de_xuat"):
				# Báo giá theo đợt: một phiếu ra nhiều đơn. Ghi một dòng
				# `don_hang`; `sales_order` của phiếu chỉ đặt khi còn trống.
				from miyano_portal.bao_gia_theo_dot import them_don_hang

				them_don_hang(
					bg.custom_de_xuat, so.name, bg.name, int(bg.get("custom_so_dot") or 0)
				)
```

- [ ] **Step 4: Chạy test + hồi quy đồng ý**

Run: `for m in test_bao_gia_theo_dot_dong_y test_bao_gia_dong_y test_don_theo_bao_gia test_don_tron_bao_gia; do bench --site localhost run-tests --app miyano_portal --module miyano_portal.tests.$m || break; done`
Expected: PASS hết.

- [ ] **Step 5: Commit**

```bash
git add miyano_portal/bao_gia.py miyano_portal/tests/test_bao_gia_theo_dot_dong_y.py
git commit -m "feat(bao-gia): dong y dot ghi bang don_hang tren phieu de xuat

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Đợt bị từ chối / hết hạn → dòng quay về phiếu gốc

**Files:**
- Modify: `miyano_portal/bao_gia_theo_dot.py`
- Modify: `miyano_portal/hooks.py` (Quotation `on_update`)
- Test: `miyano_portal/tests/test_bao_gia_theo_dot_tra_ve.py`

**Interfaces:**
- Consumes: `_dong_moi`, `bao_gia.HD_CON_HANG`, `bao_gia.quet_het_han`, `bao_gia.tu_choi`.
- Produces: hook `tra_dong_ve_khi_dot_dong(doc, method=None)`; hằng `TT_TRA_VE`.

- [ ] **Step 1: Viết test (thất bại trước)**

`miyano_portal/tests/test_bao_gia_theo_dot_tra_ve.py`:

```python
"""Đợt bị từ chối hoặc hết hạn → dòng quay về phiếu gốc (spec 2026-10-15 §4.3)."""

import frappe
from frappe.model.workflow import apply_workflow
from frappe.utils import add_days, nowdate

from miyano_portal import bao_gia, bao_gia_theo_dot as dot
from miyano_portal.tests.nen_bao_gia import NenBaoGiaTheoDot


class TestTraDongVe(NenBaoGiaTheoDot):
	def setUp(self):
		super().setUp()
		self.ql = self._quan_ly("dottv.ql@demo.miyano", self.kh_a)

	def _tach(self, goc, *ma):
		goc.reload()
		ten = [d.name for d in goc.items if d.item_code in ma]
		return frappe.get_doc("Quotation", dot.tach_dot(goc.name, ten)["dot"])

	def _khach_tu_choi(self, ten):
		frappe.set_user(self.ql)
		try:
			bao_gia.tu_choi(ten, "Giá cao")
		finally:
			frappe.set_user("Administrator")

	def test_khach_tu_choi_tra_dong_ve_giu_gia(self):
		goc = self._goc_ba_dong()
		d1 = self._tach(goc, self.item_ngoai)
		self._khach_tu_choi(d1.name)
		goc.reload()
		self.assertEqual(
			sorted((d.item_code, d.rate) for d in goc.items),
			sorted([(self.item_boi_so, 7000), (self.item_co_dau, 12000), (self.item_ngoai, 54000)]),
		)
		self.assertEqual(frappe.db.get_value("Quotation", d1.name, "custom_da_tra_ve"), 1)
		self.assertEqual(frappe.db.get_value("Quotation", d1.name, "workflow_state"), bao_gia.TT_KHACH_TU_CHOI)
		self.assertTrue(frappe.db.exists("Comment", {
			"reference_name": goc.name, "content": ["like", "%đã trả về 1 dòng%"],
		}))

	def test_miyano_tu_choi_dot_tra_dong_ve(self):
		goc = self._goc_ba_dong()
		d1 = self._tach(goc, self.item_ngoai)
		d1 = apply_workflow(d1, bao_gia.HD_THU_HOI)
		d1.custom_ly_do_tu_choi = "Nhà cung cấp báo hết hàng"
		d1.save()
		apply_workflow(d1, bao_gia.HD_TU_CHOI)
		goc.reload()
		self.assertIn(self.item_ngoai, [d.item_code for d in goc.items])

	def test_het_han_tra_dong_ve(self):
		goc = self._goc_ba_dong()
		d1 = self._tach(goc, self.item_ngoai)
		frappe.db.set_value("Quotation", d1.name, "valid_till", add_days(nowdate(), -1))
		self.assertGreaterEqual(bao_gia.quet_het_han(), 1)
		goc.reload()
		self.assertIn(self.item_ngoai, [d.item_code for d in goc.items])
		self.assertEqual(frappe.db.get_value("Quotation", d1.name, "custom_da_tra_ve"), 1)

	def test_dong_tra_ve_mo_lai_phieu_da_bao_het(self):
		goc = self._goc_ba_dong()
		goc.reload()
		dot.tach_dot(goc.name, [d.name for d in goc.items if d.item_code == self.item_ngoai])
		d2 = self._tach(goc, self.item_boi_so, self.item_co_dau)
		goc.reload()
		self.assertEqual(goc.workflow_state, bao_gia.TT_DA_BAO_HET)
		self._khach_tu_choi(d2.name)
		goc.reload()
		self.assertEqual(goc.workflow_state, bao_gia.TT_CHO_MIYANO)
		self.assertEqual(sorted(d.item_code for d in goc.items), sorted([self.item_boi_so, self.item_co_dau]))

	def test_khong_gop_voi_dong_trung_ma(self):
		goc = self._goc_ba_dong()
		goc.append("items", {"item_code": self.item_ngoai, "qty": 3, "rate": 50000, "price_list_rate": 50000})
		goc.save()
		dau = [d for d in goc.items if d.item_code == self.item_ngoai][0]
		d1 = frappe.get_doc("Quotation", dot.tach_dot(goc.name, [dau.name])["dot"])
		self._khach_tu_choi(d1.name)
		goc.reload()
		self.assertEqual(len([d for d in goc.items if d.item_code == self.item_ngoai]), 2)

	def test_khong_tra_hai_lan_va_chan_mo_lai(self):
		goc = self._goc_ba_dong()
		d1 = self._tach(goc, self.item_ngoai)
		frappe.db.set_value("Quotation", d1.name, "valid_till", add_days(nowdate(), -1))
		bao_gia.quet_het_han()
		bao_gia.quet_het_han()
		goc.reload()
		self.assertEqual(len([d for d in goc.items if d.item_code == self.item_ngoai]), 1)
		d1.reload()
		with self.assertRaisesRegex(frappe.ValidationError, "không mở lại được"):
			apply_workflow(d1, bao_gia.HD_MO_LAI)

	def test_dot_da_dong_y_khong_tra_ve(self):
		goc = self._goc_ba_dong()
		d1 = self._tach(goc, self.item_ngoai)
		frappe.set_user(self.ql)
		try:
			bao_gia.dong_y(d1.name)
		finally:
			frappe.set_user("Administrator")
		goc.reload()
		self.assertNotIn(self.item_ngoai, [d.item_code for d in goc.items])
```

- [ ] **Step 2: Chạy, xác nhận thất bại**

Run: `bench --site localhost run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_theo_dot_tra_ve`
Expected: FAIL — dòng không quay về (`item_ngoai` không có trên phiếu gốc).

- [ ] **Step 3: Cài đặt hook trong `bao_gia_theo_dot.py`**

```python
# Đợt rơi vào một trong các trạng thái này thì các dòng của nó quay về phiếu
# gốc (D3). "Khách đã đồng ý" không có ở đây: đơn đã sinh.
TT_TRA_VE = (bao_gia.TT_KHACH_TU_CHOI, bao_gia.TT_MIYANO_TU_CHOI, bao_gia.TT_HET_HAN)


def tra_dong_ve_khi_dot_dong(doc, method=None) -> None:
	"""Hook `on_update` của Quotation (spec §4.3). Chạy cho MỌI lối vào trạng
	thái kết thúc — nút trên Desk, `bao_gia.tu_choi` của khách, job
	`quet_het_han` — trong CÙNG giao dịch với bước chuyển. Cờ
	`custom_da_tra_ve` chặn trả hai lần; `kiem_chuyen_theo_dot` chặn mở lại.

	Phiếu gốc không còn nhận dòng (đã «Huỷ phần còn lại») thì đợt kết thúc,
	không trả gì. Dòng trả về giữ giá vừa báo và KHÔNG gộp với dòng trùng mã."""
	from frappe.model.workflow import apply_workflow

	from miyano_portal.nang_quyen import quyen_he_thong

	if not doc.get("custom_phieu_goc") or doc.get("custom_da_tra_ve"):
		return
	truoc, nay = bao_gia._trang_thai_truoc(doc), doc.get("workflow_state")
	if truoc == nay or nay not in TT_TRA_VE:
		return
	goc = frappe.get_doc("Quotation", doc.custom_phieu_goc, for_update=True)
	if goc.get("workflow_state") not in (bao_gia.TT_CHO_MIYANO, bao_gia.TT_DA_BAO_HET):
		goc.add_comment(
			"Comment",
			f"Đợt {doc.custom_so_dot} ({doc.name}) chuyển «{nay}» — phiếu đã "
			f"«{goc.workflow_state}», không trả mặt hàng về.",
		)
		return
	# Nâng quyền: khách (qua `bao_gia.tu_choi`) và job không có quyền ghi
	# phiếu gốc; bước «Hệ thống: có hàng trả về» khai vai Administrator.
	with quyen_he_thong():
		for hang in doc.items:
			goc.append("items", _dong_moi(hang))
		goc.save()
		if goc.get("workflow_state") == bao_gia.TT_DA_BAO_HET:
			goc = apply_workflow(goc, bao_gia.HD_CON_HANG)
		goc.add_comment(
			"Comment",
			f"Đợt {doc.custom_so_dot} ({doc.name}) «{nay}» — đã trả về {len(doc.items)} dòng.",
		)
	frappe.db.set_value("Quotation", doc.name, "custom_da_tra_ve", 1, update_modified=False)
	doc.custom_da_tra_ve = 1
```

- [ ] **Step 4: Đăng ký hook**

`miyano_portal/hooks.py`, khối Quotation `on_update`:

```python
		"on_update": [
			"miyano_portal.bao_gia.ghi_nhat_ky_chuyen_trang_thai",
			# Đợt bị từ chối/hết hạn: trả dòng về phiếu gốc (spec 2026-10-15 §4.3).
			"miyano_portal.bao_gia_theo_dot.tra_dong_ve_khi_dot_dong",
		],
```

- [ ] **Step 5: Chạy test + hồi quy**

Run: `for m in test_bao_gia_theo_dot_tra_ve test_bao_gia_theo_dot_tach test_bao_gia_het_han test_bao_gia_tu_choi_sua; do bench --site localhost run-tests --app miyano_portal --module miyano_portal.tests.$m || break; done`
Expected: PASS hết.

- [ ] **Step 6: Commit**

```bash
git add miyano_portal/bao_gia_theo_dot.py miyano_portal/hooks.py miyano_portal/tests/test_bao_gia_theo_dot_tra_ve.py
git commit -m "feat(bao-gia): dot bi tu choi hoac het han tra dong ve phieu goc

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Huỷ phần còn lại (Miyano + khách) và email báo bên kia

**Files:**
- Modify: `miyano_portal/bao_gia_theo_dot.py` (`kiem_chuyen_theo_dot`, hàm mới)
- Modify: `miyano_portal/hooks.py` (Quotation `on_update`)
- Test: `miyano_portal/tests/test_bao_gia_theo_dot_huy.py`

**Interfaces:**
- Consumes: `bao_gia.HD_HUY_CON_LAI`, `bao_gia.TT_HUY_CON_LAI`, `bao_gia.NGUOI_KHACH`, `bao_gia.bao_nhan_vien`, `bao_gia._dam_bao_cua_cong`, `portal_bao_gia._email_sales_phu_trach`.
- Produces: `huy_con_lai_boi_khach(ten: str, ly_do: str | None = None) -> dict` (`{"trang_thai_moi": str}`; NGƯỜI GỌI đã kiểm quyền), hook `bao_khi_huy_con_lai(doc, method=None)`.

- [ ] **Step 1: Viết test (thất bại trước)**

`miyano_portal/tests/test_bao_gia_theo_dot_huy.py`:

```python
"""Huỷ phần còn lại của phiếu gốc (spec 2026-10-15 §4.4, §6)."""

from unittest.mock import patch

import frappe
from frappe.model.workflow import apply_workflow

from miyano_portal import bao_gia, bao_gia_theo_dot as dot
from miyano_portal.tests.nen_bao_gia import NenBaoGiaTheoDot


class TestHuyConLai(NenBaoGiaTheoDot):
	def setUp(self):
		super().setUp()
		self.ql = self._quan_ly("dothuy.ql@demo.miyano", self.kh_a)
		self.goc = self._goc_ba_dong(contact_email="khach.dot@demo.miyano")
		self.d1 = dot.tach_dot(
			self.goc.name, [d.name for d in self.goc.items if d.item_code == self.item_ngoai]
		)["dot"]
		self.goc.reload()

	def _khach_huy(self, ly_do=None):
		frappe.set_user(self.ql)
		try:
			return dot.huy_con_lai_boi_khach(self.goc.name, ly_do)
		finally:
			frappe.set_user("Administrator")

	def test_miyano_phai_ghi_ly_do(self):
		with self.assertRaisesRegex(frappe.ValidationError, "lý do"):
			apply_workflow(self.goc, bao_gia.HD_HUY_CON_LAI)
		self.goc.reload()
		self.goc.custom_ly_do_huy_con_lai = "Khách chuyển sang mua thầu"
		self.goc.save()
		with patch("frappe.sendmail") as gui:
			goc = apply_workflow(self.goc, bao_gia.HD_HUY_CON_LAI)
		self.assertEqual(goc.workflow_state, bao_gia.TT_HUY_CON_LAI)
		self.assertEqual(goc.custom_nguoi_huy_con_lai, "Administrator")
		self.assertEqual(gui.call_args.kwargs["recipients"], ["khach.dot@demo.miyano"])
		self.assertIn("Khách chuyển sang mua thầu", gui.call_args.kwargs["message"])

	def test_khach_huy_khong_can_ly_do(self):
		frappe.db.set_value("Customer", self.kh_a, "account_manager", "Administrator")
		with patch("frappe.sendmail") as gui, patch("miyano_portal.bao_gia.bao_nhan_vien") as bao:
			kq = self._khach_huy()
		self.assertEqual(kq["trang_thai_moi"], bao_gia.TT_HUY_CON_LAI)
		self.goc.reload()
		self.assertEqual(self.goc.custom_nguoi_huy_con_lai, bao_gia.NGUOI_KHACH)
		self.assertEqual(gui.call_args.kwargs["recipients"], ["Administrator"])
		# Người nhận Notification Log tuỳ dữ liệu site: kiểm lời gọi, không kiểm bảng.
		self.assertIn("huỷ phần còn lại", bao.call_args.args[1])

	def test_khach_huy_ghi_ly_do_neu_co(self):
		with patch("frappe.sendmail"):
			self._khach_huy("Đã mua chỗ khác")
		self.assertEqual(
			frappe.db.get_value("Quotation", self.goc.name, "custom_ly_do_huy_con_lai"),
			"Đã mua chỗ khác",
		)

	def test_dot_dang_cho_van_con_hieu_luc_roi_tu_choi_khong_tra_ve(self):
		with patch("frappe.sendmail"):
			self._khach_huy()
		self.assertEqual(frappe.db.get_value("Quotation", self.d1, "workflow_state"), bao_gia.TT_CHO_KHACH)
		frappe.set_user(self.ql)
		try:
			bao_gia.tu_choi(self.d1)
		finally:
			frappe.set_user("Administrator")
		self.goc.reload()
		self.assertNotIn(self.item_ngoai, [d.item_code for d in self.goc.items])
		self.assertEqual(self.goc.workflow_state, bao_gia.TT_HUY_CON_LAI)
		self.assertFalse(frappe.db.get_value("Quotation", self.d1, "custom_da_tra_ve"))

	def test_khach_khong_huy_duoc_phieu_chua_tach(self):
		goc = self._goc_ba_dong()
		frappe.set_user(self.ql)
		try:
			with self.assertRaises(frappe.ValidationError):
				dot.huy_con_lai_boi_khach(goc.name)
		finally:
			frappe.set_user("Administrator")

	def test_khach_khong_huy_duoc_phieu_da_bao_het(self):
		self.goc.reload()
		dot.tach_dot(self.goc.name, [d.name for d in self.goc.items])
		with self.assertRaises(frappe.ValidationError):
			self._khach_huy()
```

- [ ] **Step 2: Chạy, xác nhận thất bại**

Run: `bench --site localhost run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_theo_dot_huy`
Expected: FAIL — `AttributeError: ... has no attribute 'huy_con_lai_boi_khach'` và test lý do không ném lỗi.

- [ ] **Step 3: Cài đặt**

Trong `kiem_chuyen_theo_dot`, ngay sau khối `if doc.get("custom_da_tra_ve"): ...`, thêm:

```python
	if nay == bao_gia.TT_HUY_CON_LAI:
		_kiem_huy_con_lai(doc)
		return
```

Thêm vào `bao_gia_theo_dot.py`:

```python
def _kiem_huy_con_lai(doc) -> None:
	"""Miyano phải ghi lý do (≥ `LY_DO_TOI_THIEU`); khách thì tuỳ (D4). Ghi
	người huỷ ở đây — nơi duy nhất biết bước chuyển đến từ đâu."""
	if frappe.flags.get("huy_con_lai_boi_khach") == doc.name:
		doc.custom_nguoi_huy_con_lai = bao_gia.NGUOI_KHACH
		return
	if len((doc.get("custom_ly_do_huy_con_lai") or "").strip()) < bao_gia.LY_DO_TOI_THIEU:
		frappe.throw(
			f"Phải nhập lý do huỷ phần còn lại (tối thiểu {bao_gia.LY_DO_TOI_THIEU} ký tự) "
			"trước khi chuyển trạng thái. Nhập ở mục «Cổng khách hàng» → ô «Lý do huỷ "
			"phần còn lại» rồi lưu, sau đó bấm lại «Huỷ phần còn lại».",
			frappe.ValidationError,
		)
	doc.custom_nguoi_huy_con_lai = frappe.session.user


def huy_con_lai_boi_khach(ten: str, ly_do: str | None = None) -> dict:
	"""Khách huỷ các mặt hàng chưa báo của phiếu gốc (spec §4.4). NGƯỜI GỌI đã
	kiểm quyền của khách. Đợt đang chờ khách vẫn còn hiệu lực."""
	from frappe.model.workflow import apply_workflow

	from miyano_portal.nang_quyen import quyen_he_thong

	goc = frappe.get_doc("Quotation", ten, for_update=True)
	bao_gia._dam_bao_cua_cong(goc)
	if (
		goc.get("custom_phieu_goc") or not co_dot(goc.name)
		or goc.get("workflow_state") != bao_gia.TT_CHO_MIYANO
	):
		frappe.throw(
			"Yêu cầu báo giá này không còn mặt hàng chờ báo giá nào để huỷ.",
			frappe.ValidationError,
		)
	ly_do = (ly_do or "").strip()
	nguoi_bam = frappe.session.user
	if ly_do:
		# Ghi thẳng: `apply_workflow` nạp lại chứng từ từ CSDL trước khi lưu.
		frappe.db.set_value(
			"Quotation", goc.name, "custom_ly_do_huy_con_lai", ly_do, update_modified=False
		)
	with quyen_he_thong():
		frappe.flags.huy_con_lai_boi_khach = goc.name
		try:
			goc = apply_workflow(goc, bao_gia.HD_HUY_CON_LAI)
		finally:
			frappe.flags.huy_con_lai_boi_khach = None
		goc.add_comment(
			"Comment",
			f"{bao_gia.HD_HUY_CON_LAI} bởi {nguoi_bam}" + (f" — lý do: {ly_do}" if ly_do else ""),
		)
	return {"trang_thai_moi": goc.get("workflow_state")}


def bao_khi_huy_con_lai(doc, method=None) -> None:
	"""Hook `on_update` — báo bên kia khi phiếu gốc vào «Đã huỷ phần còn lại»
	(spec §6): khách huỷ → nhân viên phụ trách (Notification Log + email); Miyano
	huỷ → email khách. Lỗi gửi không được làm hỏng việc huỷ."""
	from miyano_portal.portal_bao_gia import _email_sales_phu_trach

	if doc.get("custom_nguon_don") != bao_gia.NGUON_CONG:
		return
	truoc, nay = bao_gia._trang_thai_truoc(doc), doc.get("workflow_state")
	if truoc == nay or nay != bao_gia.TT_HUY_CON_LAI:
		return
	ly_do = (doc.get("custom_ly_do_huy_con_lai") or "").strip()
	dong_ly_do = f"<p>Lý do: {frappe.utils.escape_html(ly_do)}</p>" if ly_do else ""
	if doc.get("custom_nguoi_huy_con_lai") == bao_gia.NGUOI_KHACH:
		noi_dung = (
			f"<p>Khách hàng <b>{doc.party_name}</b> đã huỷ các mặt hàng chưa báo giá "
			f"của yêu cầu <b>{doc.name}</b>.</p>{dong_ly_do}"
		)
		bao_gia.bao_nhan_vien(doc, "Portal - Khách huỷ phần còn lại của yêu cầu báo giá", noi_dung)
		nguoi_nhan = _email_sales_phu_trach(doc.party_name)
		tieu_de = f"Khách huỷ phần còn lại của yêu cầu báo giá {doc.name}"
	else:
		noi_dung = (
			f"<p>Miyano không tiếp tục báo giá các mặt hàng còn lại của yêu cầu "
			f"<b>{doc.name}</b>. Các đợt đã gửi trước đó vẫn giữ nguyên.</p>{dong_ly_do}"
		)
		nguoi_nhan = doc.get("contact_email")
		tieu_de = f"Yêu cầu báo giá {doc.name}: Miyano dừng báo giá phần còn lại"
	if not nguoi_nhan:
		return
	try:
		frappe.sendmail(
			recipients=[nguoi_nhan], subject=tieu_de, message=noi_dung,
			reference_doctype="Quotation", reference_name=doc.name, now=False,
		)
	except Exception:
		frappe.log_error(
			title="bao_gia_theo_dot: gửi email huỷ phần còn lại thất bại",
			message=frappe.get_traceback(),
		)
```

- [ ] **Step 4: Đăng ký hook**

`miyano_portal/hooks.py`, Quotation `on_update` thêm dòng cuối:

```python
			"miyano_portal.bao_gia_theo_dot.bao_khi_huy_con_lai",
```

- [ ] **Step 5: Chạy test**

Run: `for m in test_bao_gia_theo_dot_huy test_bao_gia_theo_dot_tach test_bao_gia_theo_dot_tra_ve; do bench --site localhost run-tests --app miyano_portal --module miyano_portal.tests.$m || break; done`
Expected: PASS hết.

- [ ] **Step 6: Commit**

```bash
git add miyano_portal/bao_gia_theo_dot.py miyano_portal/hooks.py miyano_portal/tests/test_bao_gia_theo_dot_huy.py
git commit -m "feat(bao-gia): huy phan con lai cua yeu cau bao gia theo dot

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Email hết hạn theo đợt

**Files:**
- Modify: `miyano_portal/bao_gia.py:786-808` (`_gui_email_het_han`)
- Test: `miyano_portal/tests/test_bao_gia_theo_dot_tra_ve.py` (thêm test)

**Interfaces:**
- Consumes: `custom_so_dot`, `custom_da_tra_ve`, `custom_phieu_goc` (Task 1, Task 4).
- Produces: `_gui_email_het_han(bg, han)` không đổi chữ ký.

- [ ] **Step 1: Thêm test (thất bại trước)**

Cuối lớp `TestTraDongVe`:

```python
	def test_email_het_han_noi_ro_dot_va_tra_ve(self):
		from unittest.mock import patch

		goc = self._goc_ba_dong(contact_email="khach.hh@demo.miyano")
		d1 = self._tach(goc, self.item_ngoai)
		frappe.db.set_value("Quotation", d1.name, "valid_till", add_days(nowdate(), -1))
		with patch("frappe.sendmail") as gui:
			bao_gia.quet_het_han()
		thu = [c.kwargs for c in gui.call_args_list if c.kwargs["reference_name"] == d1.name]
		self.assertTrue(thu)
		self.assertIn("(đợt 1)", thu[0]["subject"])
		self.assertIn(f"đã trả về phiếu {goc.name}", thu[0]["message"])
		self.assertNotIn("gửi yêu cầu báo giá mới", thu[0]["message"])
```

- [ ] **Step 2: Chạy, xác nhận thất bại**

Run: `bench --site localhost run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_theo_dot_tra_ve`
Expected: FAIL ở `test_email_het_han_noi_ro_dot_va_tra_ve` (tiêu đề không có "(đợt 1)").

- [ ] **Step 3: Sửa `_gui_email_het_han`**

```python
def _gui_email_het_han(bg, han) -> None:
	"""Email hai phía. Lỗi gửi mail không được chặn việc đóng báo giá.

	Báo giá theo đợt (spec 2026-10-15 §6): tiêu đề nêu số đợt; đợt đã trả mặt
	hàng về phiếu gốc thì nói vậy thay vì bảo khách gửi yêu cầu mới."""
	from miyano_portal.portal_bao_gia import _email_sales_phu_trach

	han_str = formatdate(han, "dd/mm/yyyy")
	ten_dot = f" (đợt {bg.custom_so_dot})" if bg.get("custom_so_dot") else ""
	if bg.get("custom_phieu_goc") and frappe.db.get_value(
		"Quotation", bg.name, "custom_da_tra_ve"
	):
		tiep = (
			f"<p>Các mặt hàng của đợt này đã trả về phiếu {bg.custom_phieu_goc}; "
			"Miyano sẽ báo giá lại.</p>"
		)
	else:
		tiep = "<p>Nếu vẫn cần hàng, vui lòng gửi yêu cầu báo giá mới.</p>"
	noi_dung = (
		f"<p>Báo giá <b>{bg.name}</b>{ten_dot} (khách hàng {bg.party_name}) đã hết hiệu "
		f"lực ngày <b>{han_str}</b> mà chưa được đồng ý trên cổng khách hàng.</p>" + tiep
	)
	for nguoi_nhan in {bg.get("contact_email"), _email_sales_phu_trach(bg.party_name)}:
		if not nguoi_nhan:
			continue
		try:
			frappe.sendmail(
				recipients=[nguoi_nhan],
				subject=f"Báo giá {bg.name}{ten_dot} đã hết hiệu lực",
				message=noi_dung, reference_doctype="Quotation", reference_name=bg.name,
				now=False,
			)
		except Exception:
			frappe.log_error(
				title="bao_gia: gửi email hết hạn thất bại", message=frappe.get_traceback()
			)
```

- [ ] **Step 4: Chạy test + hồi quy hết hạn**

Run: `for m in test_bao_gia_theo_dot_tra_ve test_bao_gia_het_han; do bench --site localhost run-tests --app miyano_portal --module miyano_portal.tests.$m || break; done`
Expected: PASS hết.

- [ ] **Step 5: Commit**

```bash
git add miyano_portal/bao_gia.py miyano_portal/tests/test_bao_gia_theo_dot_tra_ve.py
git commit -m "feat(bao-gia): email het han neu so dot va mat hang da tra ve

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: API cổng — danh sách, đếm, chi tiết theo đợt, huỷ phần còn lại

**Files:**
- Modify: `miyano_portal/api/portal.py:1121-1128` (`_sql_nhom_bao_gia`), `:1325-1352` (`_truy_van_tab_bao_gia`), `:1394-1403` (`portal_bao_gia_dem`), `:1475-1521` (`portal_bao_gia_chi_tiet`), thêm endpoint sau `portal_bao_gia_tu_choi`
- Test: `miyano_portal/tests/test_bao_gia_theo_dot_cong.py`

**Interfaces:**
- Consumes: `bao_gia_theo_dot.san_sang()`, `bao_gia_theo_dot.huy_con_lai_boi_khach`, `bao_gia.TT_*`.
- Produces:
  - `portal_bao_gia_chi_tiet(ten) -> dict` thêm khoá `dot: list[dict]` (mỗi phần tử = các khoá cũ của chi tiết + `so_dot: int`, `da_tra_ve: bool`), `con_lai: list[{name, item_code, item_name, uom, qty}]`, `duoc_huy_con_lai: bool`. Gọi bằng tên đợt → trả phiếu gốc.
  - Dòng danh sách thêm `so_cho_dong_y: int`.
  - `portal_bao_gia_huy_con_lai(ten, ly_do=None) -> {"trang_thai_moi": str}` (whitelist).

- [ ] **Step 1: Viết test (thất bại trước)**

`miyano_portal/tests/test_bao_gia_theo_dot_cong.py`:

```python
"""API cổng cho báo giá theo đợt (spec 2026-10-15 §5)."""

from unittest.mock import patch

import frappe

from miyano_portal import bao_gia, bao_gia_theo_dot as dot
from miyano_portal.api import portal
from miyano_portal.portal_context import LOI_KHONG_THAY
from miyano_portal.tests.nen_bao_gia import NenBaoGiaTheoDot


class TestCongTheoDot(NenBaoGiaTheoDot):
	def setUp(self):
		super().setUp()
		self.ql_a = self._quan_ly("dotcong.ql.a@demo.miyano", self.kh_a)
		self.ql_b = self._quan_ly("dotcong.ql.b@demo.miyano", self.kh_b)
		for ten in frappe.get_all(
			"Portal De Xuat Mua", filters={"customer": ["like", "_TEST DX%"]}, pluck="name"
		):
			frappe.delete_doc("Portal De Xuat Mua", ten, force=True)
		self.phieu = frappe.get_doc({
			"doctype": "Portal De Xuat Mua", "customer": self.kh_a,
			"khoa_phong": self.khoa_huyethoc, "ly_do_yeu_cau": "Hết hàng trong kho khoa",
			"trang_thai": "Đã duyệt",
			"items": [{"item_code": self.item_ngoai, "so_luong_de_xuat": 10, "so_luong_duyet": 10}],
		}).insert(ignore_permissions=True)
		self.goc = self._goc_ba_dong(custom_de_xuat=self.phieu.name, khoa=self.khoa_huyethoc)
		frappe.db.set_value("Portal De Xuat Mua", self.phieu.name, "bao_gia", self.goc.name)

	def _goi(self, user, ham, *a, **kw):
		frappe.set_user(user)
		try:
			return ham(*a, **kw)
		finally:
			frappe.set_user("Administrator")

	def _tach(self, *ma):
		self.goc.reload()
		return dot.tach_dot(self.goc.name, [d.name for d in self.goc.items if d.item_code in ma])["dot"]

	def _dong_cua_phieu(self):
		rows = self._goi(self.ql_a, portal.portal_bao_gia_danh_sach)["rows"]
		return [r for r in rows if r["de_xuat"] == self.phieu.name]

	def test_danh_sach_chi_hien_phieu_goc_nhom_cho_dong_y(self):
		self._tach(self.item_ngoai)
		self._tach(self.item_boi_so)
		dong = self._dong_cua_phieu()
		self.assertEqual(len(dong), 1)
		self.assertEqual(dong[0]["bao_gia"], self.goc.name)
		self.assertEqual(dong[0]["nhom"], "cho_dong_y")
		self.assertEqual(self._goi(self.ql_a, portal.portal_bao_gia_dem)["cho_dong_y"], 2)

	def test_nhom_dang_bao_gia_khi_khong_dot_nao_cho_khach(self):
		d1 = self._tach(self.item_ngoai)
		self._goi(self.ql_a, bao_gia.dong_y, d1)
		self.assertEqual(self._dong_cua_phieu()[0]["nhom"], "dang_bao_gia")

	def test_nhom_da_dong_khi_bao_het_va_khong_dot_nao_cho(self):
		d1 = self._tach(self.item_ngoai, self.item_boi_so, self.item_co_dau)
		self._goi(self.ql_a, bao_gia.dong_y, d1)
		self.assertEqual(self._dong_cua_phieu()[0]["nhom"], "da_dong")

	def test_chi_tiet_co_dot_va_con_lai(self):
		d1 = self._tach(self.item_ngoai)
		kq = self._goi(self.ql_a, portal.portal_bao_gia_chi_tiet, self.goc.name)
		self.assertEqual(kq["bao_gia"], self.goc.name)
		self.assertEqual(kq["nhom"], "cho_dong_y")
		self.assertEqual([d["bao_gia"] for d in kq["dot"]], [d1])
		dot1 = kq["dot"][0]
		self.assertEqual(dot1["so_dot"], 1)
		self.assertTrue(dot1["hien_gia"])
		self.assertTrue(dot1["duoc_dong_y"])
		self.assertFalse(dot1["da_tra_ve"])
		self.assertEqual(dot1["items"][0]["rate"], 54000)
		self.assertEqual(
			sorted(d["item_code"] for d in kq["con_lai"]), sorted([self.item_boi_so, self.item_co_dau])
		)
		self.assertNotIn("rate", kq["con_lai"][0])
		self.assertTrue(kq["duoc_huy_con_lai"])

	def test_chi_tiet_phieu_chua_tach_nhu_cu(self):
		kq = self._goi(self.ql_a, portal.portal_bao_gia_chi_tiet, self.goc.name)
		self.assertEqual((kq["dot"], kq["con_lai"], kq["duoc_huy_con_lai"]), ([], [], False))
		self.assertEqual(kq["nhom"], "dang_bao_gia")

	def test_chi_tiet_theo_ten_dot_tra_phieu_goc(self):
		d1 = self._tach(self.item_ngoai)
		kq = self._goi(self.ql_a, portal.portal_bao_gia_chi_tiet, d1)
		self.assertEqual(kq["bao_gia"], self.goc.name)
		self.assertEqual([d["bao_gia"] for d in kq["dot"]], [d1])

	def test_sua_so_luong_tren_dot_roi_gui_lai(self):
		from frappe.model.workflow import apply_workflow

		d1 = self._tach(self.item_ngoai)
		ten_dong = frappe.get_doc("Quotation", d1).items[0].name
		kq = self._goi(
			self.ql_a, portal.portal_bao_gia_sua_so_luong, d1, [{"name": ten_dong, "qty": 20}]
		)
		self.assertEqual(kq["trang_thai_moi"], bao_gia.TT_CHO_MIYANO)
		# Đợt (không phải phiếu gốc) gửi lại được: chốt D7 chỉ áp cho phiếu gốc.
		d = apply_workflow(frappe.get_doc("Quotation", d1), bao_gia.HD_GUI_KHACH)
		self.assertEqual(d.workflow_state, bao_gia.TT_CHO_KHACH)
		self.assertEqual(d.items[0].qty, 20)

	def test_dong_y_tu_choi_theo_ten_dot(self):
		d1 = self._tach(self.item_ngoai)
		d2 = self._tach(self.item_boi_so)
		self.assertTrue(self._goi(self.ql_a, portal.portal_bao_gia_dong_y, d1)["sales_order"])
		self.assertEqual(
			self._goi(self.ql_a, portal.portal_bao_gia_tu_choi, d2)["trang_thai_moi"],
			bao_gia.TT_KHACH_TU_CHOI,
		)

	def test_khach_khac_khong_thay_dot(self):
		d1 = self._tach(self.item_ngoai)
		for ham, tham in (
			(portal.portal_bao_gia_chi_tiet, (d1,)),
			(portal.portal_bao_gia_dong_y, (d1,)),
			(portal.portal_bao_gia_huy_con_lai, (self.goc.name,)),
		):
			with self.assertRaisesRegex(frappe.PermissionError, LOI_KHONG_THAY):
				self._goi(self.ql_b, ham, *tham)

	def test_huy_con_lai_qua_cong(self):
		self._tach(self.item_ngoai)
		with patch("frappe.sendmail"):
			kq = self._goi(self.ql_a, portal.portal_bao_gia_huy_con_lai, self.goc.name, "Đủ hàng rồi")
		self.assertEqual(kq["trang_thai_moi"], bao_gia.TT_HUY_CON_LAI)
		ct = self._goi(self.ql_a, portal.portal_bao_gia_chi_tiet, self.goc.name)
		self.assertFalse(ct["duoc_huy_con_lai"])

	def test_don_dot_hai_hien_o_tab_don_hang(self):
		d1 = self._tach(self.item_ngoai)
		so1 = self._goi(self.ql_a, bao_gia.dong_y, d1)["sales_order"]
		d2 = self._tach(self.item_boi_so)
		so2 = self._goi(self.ql_a, bao_gia.dong_y, d2)["sales_order"]
		rows = self._goi(self.ql_a, portal.portal_yeu_cau_cua_toi, limit=200)["rows"]
		don = {r["sales_order"] for r in rows}
		self.assertTrue({so1, so2} <= don)

	def test_danh_sach_khong_vo_khi_chua_co_cot(self):
		self._tach(self.item_ngoai)
		with patch.object(dot, "san_sang", return_value=False):
			rows = self._goi(self.ql_a, portal.portal_bao_gia_danh_sach)["rows"]
			self._goi(self.ql_a, portal.portal_bao_gia_dem)
			kq = self._goi(self.ql_a, portal.portal_bao_gia_chi_tiet, self.goc.name)
		self.assertTrue(rows)
		self.assertEqual(kq["dot"], [])
```

- [ ] **Step 2: Chạy, xác nhận thất bại**

Run: `bench --site localhost run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_theo_dot_cong`
Expected: FAIL — `KeyError: 'dot'`, `AttributeError: ... portal_bao_gia_huy_con_lai`.

- [ ] **Step 3: Danh sách và đếm**

`miyano_portal/api/portal.py` — thay `_sql_nhom_bao_gia`:

```python
def _sql_dot_cho_khach(q: str) -> str:
    """Có đợt của báo giá `q` đang chờ khách đồng ý (spec 2026-10-15 §5.1).
    `'0'` khi site chưa có cột `custom_phieu_goc` (patch v1_45): 1054 lúc
    PARSE, không có short-circuit theo giá trị."""
    from miyano_portal import bao_gia_theo_dot

    if not bao_gia_theo_dot.san_sang():
        return "0"
    return f"""(select count(*) from `tabQuotation` dq
                where dq.custom_phieu_goc = {q}.name and dq.docstatus = 0
                  and dq.workflow_state = '{bao_gia.TT_CHO_KHACH}')"""


def _sql_nhom_bao_gia(q: str) -> str:
    # Phiếu gốc đã tách đợt: có đợt chờ khách thì nhóm "chờ đồng ý" thắng mọi
    # thứ; "Đã báo hết" / "Đã huỷ phần còn lại" rơi vào `else` → 'da_dong'.
    # Bản Python cùng luật: `_nhom_phieu_goc`.
    return f"""case
        when {q}.name is null then 'nhap'
        when {_sql_dot_cho_khach(q)} > 0 then 'cho_dong_y'
        when {q}.workflow_state = '{bao_gia.TT_CHO_MIYANO}' then 'dang_bao_gia'
        when {q}.workflow_state = '{bao_gia.TT_CHO_KHACH}' then 'cho_dong_y'
        when {q}.workflow_state = '{bao_gia.TT_DA_DONG_Y}' then 'da_dong_y'
        else 'da_dong'
    end"""
```

Trong `_truy_van_tab_bao_gia`, thêm cột ngay sau dòng `{_sql_nhom_bao_gia("q")} as nhom`:

```python
               {_sql_nhom_bao_gia("q")} as nhom,
               -- Số báo giá đang chờ khách trên dòng này: chính phiếu (chưa
               -- tách đợt) hoặc các đợt của nó — huy hiệu đếm ĐỢT (§5.1).
               case when q.workflow_state = '{bao_gia.TT_CHO_KHACH}' then 1
                    else coalesce({_sql_dot_cho_khach("q")}, 0) end as so_cho_dong_y
```

(Chú ý thêm dấu phẩy sau `as nhom`.)

Thay thân `portal_bao_gia_dem`:

```python
@frappe.whitelist()
def portal_bao_gia_dem() -> dict:
    """Số báo giá đang chờ khách đồng ý — huy hiệu trên tab. Phiếu báo theo
    đợt đếm từng đợt đang chờ (spec 2026-10-15 §5.1)."""
    if not _cot_bao_gia_ton_tai():
        return {"cho_dong_y": 0}
    trong, tham_so = _truy_van_tab_bao_gia()
    n = frappe.db.sql(
        f"select coalesce(sum(t.so_cho_dong_y), 0) from ({trong}) t", tham_so
    )[0][0]
    return {"cho_dong_y": int(n)}
```

Trong vòng lặp cuối `portal_bao_gia_danh_sach`, thêm: `r["so_cho_dong_y"] = int(r.get("so_cho_dong_y") or 0)`.

- [ ] **Step 4: Chi tiết**

Thay `portal_bao_gia_chi_tiet` bằng:

```python
def _mo_ta_bao_gia(bg) -> dict:
    """Thứ khách được thấy của MỘT Quotation (cả phiếu hoặc một đợt)."""
    trang_thai = bg.get("workflow_state") or ""
    hien_gia = trang_thai in _BAO_GIA_HIEN_GIA
    het_han = bao_gia.qua_han(bg)
    cho_khach = trang_thai == bao_gia.TT_CHO_KHACH
    ma = ""
    if bg.get("custom_de_xuat"):
        ma = frappe.db.get_value("Portal De Xuat Mua", bg.custom_de_xuat, "ma_de_xuat") or ""
    return {
        # ... GIỮ NGUYÊN mọi khoá của dict cũ, từ "bao_gia": bg.name tới hết
        # "dat_ngoai": [...] — chép nguyên khối return cũ vào đây ...
    }


def _cac_dot(goc) -> list:
    """Các đợt của phiếu gốc, theo số đợt. Đợt chép khách/khoa của phiếu gốc
    nên đã nằm trong phạm vi người gọi khi phiếu gốc nằm trong đó."""
    from miyano_portal import bao_gia_theo_dot

    if not bao_gia_theo_dot.san_sang():
        return []
    return [
        frappe.get_doc("Quotation", ten)
        for ten in frappe.get_all(
            "Quotation", filters={"custom_phieu_goc": goc.name},
            order_by="custom_so_dot asc", pluck="name",
        )
    ]


def _nhom_phieu_goc(goc, dot) -> str:
    """Bản Python của `_sql_nhom_bao_gia` cho phiếu đã tách đợt."""
    if any(d.docstatus == 0 and d.workflow_state == bao_gia.TT_CHO_KHACH for d in dot):
        return "cho_dong_y"
    if goc.get("workflow_state") == bao_gia.TT_CHO_MIYANO:
        return "dang_bao_gia"
    return "da_dong"


@frappe.whitelist()
def portal_bao_gia_chi_tiet(ten) -> dict:
    bg = _bao_gia_cua_toi(ten)
    # Email/thông báo trỏ tới tên ĐỢT: trang chi tiết luôn là của phiếu gốc.
    if bg.get("custom_phieu_goc"):
        bg = _bao_gia_cua_toi(bg.custom_phieu_goc)
    kq = _mo_ta_bao_gia(bg)
    dot = _cac_dot(bg)
    kq["dot"] = [
        {**_mo_ta_bao_gia(d), "so_dot": int(d.get("custom_so_dot") or 0),
         "da_tra_ve": bool(d.get("custom_da_tra_ve"))}
        for d in dot
    ]
    kq["con_lai"] = [
        {"name": d.name, "item_code": d.item_code, "item_name": d.item_name,
         "uom": d.uom, "qty": float(d.qty or 0)}
        for d in bg.items if d.item_code != ITEM_GIU_CHO
    ] if dot else []
    kq["duoc_huy_con_lai"] = bool(dot) and bg.get("workflow_state") == bao_gia.TT_CHO_MIYANO
    if dot:
        kq["nhom"] = _nhom_phieu_goc(bg, dot)
    return kq
```

Thân `_mo_ta_bao_gia` = nguyên khối `return {...}` của `portal_bao_gia_chi_tiet` cũ (dòng 1485-1521), không đổi khoá nào.

- [ ] **Step 5: Endpoint huỷ phần còn lại**

Ngay sau `portal_bao_gia_tu_choi`:

```python
@frappe.whitelist()
def portal_bao_gia_huy_con_lai(ten, ly_do=None) -> dict:
    """Spec 2026-10-15 §4.4 — huỷ các mặt hàng chưa báo của phiếu gốc. Mọi tài
    khoản trong phạm vi bấm được, như đồng ý; lý do tuỳ chọn."""
    from miyano_portal import bao_gia_theo_dot

    bg = _bao_gia_cua_toi(ten)
    return bao_gia_theo_dot.huy_con_lai_boi_khach(bg.name, ly_do)
```

- [ ] **Step 6: Chạy test + hồi quy API cổng**

Run: `for m in test_bao_gia_theo_dot_cong test_bao_gia_endpoint test_bao_gia_cach_ly test_bao_gia_pdf test_huy_hieu_cho_bao_gia; do bench --site localhost run-tests --app miyano_portal --module miyano_portal.tests.$m || break; done`
Expected: PASS hết.

- [ ] **Step 7: Commit**

```bash
git add miyano_portal/api/portal.py miyano_portal/tests/test_bao_gia_theo_dot_cong.py
git commit -m "feat(portal): api bao gia theo dot (danh sach, dem, chi tiet, huy con lai)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Giao diện cổng — mỗi đợt một khối

**Files:**
- Modify: `frontend/src/bao-gia.js`, `frontend/src/bao-gia.test.mjs`
- Create: `frontend/src/components/KhoiBaoGia.vue`
- Modify: `frontend/src/views/ChiTietBaoGia.vue`
- Modify: `miyano_portal/tests/test_bao_gia_giao_dien.py`
- Build: `miyano_portal/public/frontend/*`

**Interfaces:**
- Consumes: kết quả `portal_bao_gia_chi_tiet` (Task 7): `dot[]`, `con_lai[]`, `duoc_huy_con_lai`; endpoint `portal_bao_gia_huy_con_lai`.
- Produces: `nhanDot(dot) -> string` trong `bao-gia.js`; component `KhoiBaoGia` (props `bg: Object`, `tieuDe: String`; emit `xong`).

- [ ] **Step 1: Test JS (thất bại trước)**

Thêm `nhanDot` vào khối import đầu `frontend/src/bao-gia.test.mjs`, rồi cuối file:

```js
test('nhãn đợt: số đợt + trạng thái, đợt đã trả về nói rõ', () => {
  assert.equal(nhanDot({ so_dot: 2, nhom: 'cho_dong_y' }), 'Đợt 2 · Chờ anh/chị đồng ý')
  assert.equal(nhanDot({ so_dot: 1, nhom: 'da_dong', da_tra_ve: true }), 'Đợt 1 · đã trả về phiếu')
  assert.equal(nhanDot({ so_dot: 3, nhom: 'da_dong_y' }), 'Đợt 3 · Đã đồng ý')
})
```

Run: `cd frontend && yarn test`
Expected: FAIL — `nhanDot` không được export.

- [ ] **Step 2: `nhanDot` trong `bao-gia.js`**

Sau `badgeDongBaoGia`:

```js
// Tiêu đề khối của một đợt trong trang chi tiết (spec 2026-10-15 §5.2). Đợt
// bị từ chối/hết hạn đã trả mặt hàng về phiếu: nói thẳng điều đó thay vì
// "Đã đóng", để khách biết mặt hàng chưa mất.
export function nhanDot(dot) {
  const so = `Đợt ${dot?.so_dot || '?'}`
  if (dot?.da_tra_ve) return `${so} · đã trả về phiếu`
  return `${so} · ${nhanNhomBaoGia(dot?.nhom)}`
}
```

Run: `yarn test` → PASS.

- [ ] **Step 3: Tạo `components/KhoiBaoGia.vue`**

Chuyển nguyên phần "báo giá gửi khách" của `ChiTietBaoGia.vue` sang đây. `bg` là `toRef` của prop nên script vẫn viết `bg.value…` và template vẫn viết `bg.…` như cũ.

```vue
<script setup>
// Một báo giá gửi khách (spec 2026-10-12 §6.3, 2026-10-15 §5.2): cả phiếu khi
// chưa tách đợt, hoặc MỘT đợt. Server quyết định thấy gì, làm gì
// (`hien_gia`, `duoc_dong_y`, `duoc_sua_so_luong`); khối này không tự suy.
import { ref, toRef, computed, watch } from 'vue'
import api from '../api'
import { fmtVND, fmtDate } from '../format'
import { showToast } from '../toast'
import {
  nhanNhomBaoGia, nhomBaoGiaBadge, hanhDongBaoGia, dongDaSua, loiSoLuong,
} from '../bao-gia'
import ReasonModal from './ReasonModal.vue'
import CotTenHang from './CotTenHang.vue'

const props = defineProps({
  bg: { type: Object, required: true },
  // Có tiêu đề = khối của một đợt: vẽ đầu khối riêng (hạn, đơn, nhãn).
  tieuDe: { type: String, default: '' },
})
const emit = defineEmits(['xong'])
const bg = toRef(props, 'bg')

const dangChay = ref('')
const moTuChoi = ref(false)
const dangSua = ref(false)
const soLuongMoi = ref({})

const hanhDong = computed(() => hanhDongBaoGia(bg.value))
const pdfUrl = computed(() =>
  `/api/method/miyano_portal.api.portal.portal_bao_gia_pdf?quotation=${encodeURIComponent(bg.value?.bao_gia || '')}`)

function datLaiSoLuong() {
  soLuongMoi.value = Object.fromEntries((bg.value?.items || []).map((it) => [it.name, it.qty]))
}

// Server trả bản mới sau mỗi thao tác: ô sửa về số lượng đang có.
watch(bg, () => { datLaiSoLuong(); dangSua.value = false }, { immediate: true })

// Tắt chế độ sửa là HUỶ: các ô trở về số lượng đang có, để lần mở sau không
// mang theo con số gõ dở của lần trước.
function batTatSua() {
  if (dangSua.value) datLaiSoLuong()
  dangSua.value = !dangSua.value
}

async function chay(ten, viec, thanhCong) {
  if (dangChay.value) return
  dangChay.value = ten
  try {
    await viec()
    showToast(thanhCong)
    emit('xong')
  } catch (e) {
    showToast(e.message || 'Không thực hiện được thao tác này.', 'error')
  } finally {
    dangChay.value = ''
  }
}

const dongY = () => chay(
  'dong_y',
  () => api.call('portal_bao_gia_dong_y', { ten: bg.value.bao_gia }),
  'Đã đồng ý — đơn hàng đã được tạo và chuyển cho Miyano xác nhận.',
)

// Hộp lý do chỉ đóng khi server đã nhận: lỗi thì hộp còn mở, lý do vừa gõ còn
// nguyên để gửi lại.
function tuChoi(lyDo) {
  return chay(
    'tu_choi',
    async () => {
      await api.call('portal_bao_gia_tu_choi', { ten: bg.value.bao_gia, ly_do: lyDo || undefined })
      moTuChoi.value = false
    },
    'Đã từ chối báo giá.',
  )
}

function guiSuaSoLuong() {
  // Số 0, số âm, ô trống: chặn và nói rõ dòng nào, không lặng lẽ bỏ dòng đó
  // khỏi lời gửi rồi báo thành công.
  const loi = loiSoLuong(bg.value.items, soLuongMoi.value)
  if (loi) return showToast(loi, 'error')
  const dong = dongDaSua(bg.value.items, soLuongMoi.value)
  if (!dong.length) return showToast('Chưa sửa số lượng dòng nào.', 'error')
  return chay(
    'sua_so_luong',
    () => api.call('portal_bao_gia_sua_so_luong', { ten: bg.value.bao_gia, dong: JSON.stringify(dong) }),
    'Đã gửi lại — Miyano sẽ xem lại giá theo số lượng mới.',
  )
}
</script>

<template>
  <div class="mb10">
    <div v-if="tieuDe" class="card mb10">
      <div class="sb">
        <div class="h3" style="margin: 0">{{ tieuDe }}</div>
        <span class="badge" :class="bg.da_tra_ve ? 'b-gray' : nhomBaoGiaBadge(bg.nhom)">
          {{ bg.da_tra_ve ? 'Đã trả về phiếu' : nhanNhomBaoGia(bg.nhom) }}
        </span>
      </div>
      <p class="tag" style="margin-top: 4px">
        Báo giá {{ bg.bao_gia }}
        <template v-if="bg.han_hieu_luc"> · hiệu lực đến <b>{{ fmtDate(bg.han_hieu_luc) }}</b></template>
      </p>
      <p v-if="bg.da_tra_ve" class="tag" style="margin-top: 6px">
        Các mặt hàng của đợt này đã trả về phiếu để Miyano báo giá lại.
      </p>
      <p v-if="bg.ly_do_tu_choi" class="tag" style="margin-top: 6px; color: var(--red)">
        Lý do từ chối: {{ bg.ly_do_tu_choi }}
      </p>
      <p v-if="bg.sales_order" style="margin-top: 6px">
        <router-link :to="{ name: 'order-detail', params: { name: bg.sales_order } }">
          Xem đơn hàng {{ bg.sales_order }} →
        </router-link>
      </p>
    </div>

    <div v-if="hanhDong.length" class="card mb10">
      <div class="h3">Việc đang chờ bạn</div>
      <p class="tag" style="margin-bottom: 10px">
        Bấm <b>Đồng ý</b> = chấp nhận đặt hàng theo giá dưới đây. Hệ thống ghi lại người bấm và thời điểm.
      </p>
      <div class="flex" style="flex-wrap: wrap">
        <button class="btn-g" :disabled="!!dangChay" @click="dongY">
          {{ dangChay === 'dong_y' ? 'Đang gửi…' : (tieuDe ? '✔ Đồng ý cả đợt' : '✔ Đồng ý báo giá') }}
        </button>
        <button class="btn-o" :disabled="!!dangChay" @click="moTuChoi = true">✕ Từ chối…</button>
        <button v-if="hanhDong.includes('sua_so_luong')" class="btn-o" :disabled="!!dangChay"
                @click="batTatSua">{{ dangSua ? '✕ Huỷ sửa số lượng' : '✎ Sửa số lượng' }}</button>
        <a class="btn-o nut-pdf" :href="pdfUrl" target="_blank" rel="noopener">⬇ Tải báo giá (PDF)</a>
      </div>
    </div>
    <!-- Hết việc phải làm nhưng vẫn được xem giá: báo giá còn tải về được. -->
    <div v-else-if="bg.hien_gia" class="mb10">
      <a class="btn-o nut-pdf" :href="pdfUrl" target="_blank" rel="noopener">⬇ Tải báo giá (PDF)</a>
    </div>

    <div v-if="!bg.hien_gia && bg.nhom === 'dang_bao_gia'" class="card mb10">
      <span class="badge b-blue">Miyano đang báo giá</span>
      <span class="tag"> Đơn giá sẽ hiện khi Miyano gửi báo giá cho quý vị.</span>
    </div>

    <!-- Ba cột Mã / Tên mặt hàng / Tên thường gọi theo quy tắc chung của mọi
         bảng mặt hàng trên cổng (`CotTenHang`, `ten-hang.js`); bảng rộng hơn
         khung thì cuộn ngang trong thẻ. Cột giá CHỈ vẽ khi server cho xem
         (`bg.hien_gia`) — lúc đó `rate`/`amount` mới khác `null`. -->
    <div class="card mb10" style="padding: 0; overflow-x: auto">
      <div class="h3" style="padding: 12px 14px 0">Mặt hàng</div>
      <table>
        <thead>
          <tr>
            <CotTenHang head />
            <th>ĐVT</th><th class="right">Số lượng</th>
            <th v-if="bg.hien_gia" class="right">Đơn giá</th>
            <th v-if="bg.hien_gia" class="right">Thành tiền</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="it in bg.items" :key="it.name">
            <CotTenHang :ma="it.item_code" :ten="it.item_name || ''" />
            <td>{{ it.uom }}</td>
            <td class="right">
              <input v-if="dangSua" v-model.number="soLuongMoi[it.name]" type="number" min="0.001"
                     step="any" style="width: 90px; text-align: right" />
              <template v-else>{{ it.qty }}</template>
            </td>
            <td v-if="bg.hien_gia" class="right">{{ fmtVND(it.rate) }}</td>
            <td v-if="bg.hien_gia" class="right">{{ fmtVND(it.amount) }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="bg.hien_gia" class="right" style="padding: 10px 14px">
        <b>Tổng cộng: {{ fmtVND(bg.tong_tien) }}</b>
      </p>
      <div v-if="dangSua" class="flex" style="padding: 0 14px 12px; flex-wrap: wrap">
        <button class="btn" :disabled="!!dangChay" @click="guiSuaSoLuong">
          {{ dangChay === 'sua_so_luong' ? 'Đang gửi…' : 'Gửi lại để báo giá' }}
        </button>
        <span class="tag">Miyano xem lại giá theo số lượng mới rồi gửi báo giá lại. Muốn bỏ hẳn thì từ chối báo giá.</span>
      </div>
    </div>

    <ReasonModal
      :open="moTuChoi"
      title="Từ chối báo giá"
      desc="Lý do không bắt buộc, nhưng giúp Miyano báo giá sát hơn ở lần sau."
      placeholder="VD: Giá cao hơn nhà cung cấp hiện tại…"
      :min-len="0"
      :submitting="dangChay === 'tu_choi'"
      submit-label="Từ chối báo giá"
      @submit="tuChoi"
      @close="moTuChoi = false"
    />
  </div>
</template>

<style scoped>
/* Liên kết tải PDF mang dáng nút `.btn-o` (vốn viết cho <button>). */
.nut-pdf {
  display: inline-block;
  text-decoration: none;
  font-size: 14px;
}
</style>
```

- [ ] **Step 4: Viết lại `views/ChiTietBaoGia.vue`**

Script: giữ `route`, `loading`, `error`, `bg`, `nhatKy`, `dangTaiNhatKy`, `dongChuaKhop`, `load` (bỏ `datLaiSoLuong()`/`dangSua` trong `load`), `napNhatKy`, `watch`, `onMounted`. Xoá `dangChay`/`moTuChoi`/`dangSua`/`soLuongMoi`/`hanhDong`/`pdfUrl`/`datLaiSoLuong`/`batTatSua`/`chay`/`dongY`/`tuChoi`/`guiSuaSoLuong` (đã sang `KhoiBaoGia`). Import:

```js
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'
import { fmtDate } from '../format'
import { showToast } from '../toast'
import { nhanNhomBaoGia, nhomBaoGiaBadge, nhanDot } from '../bao-gia'
import ReasonModal from '../components/ReasonModal.vue'
import CotTenHang from '../components/CotTenHang.vue'
import KhoiBaoGia from '../components/KhoiBaoGia.vue'
import KhoiDongThoiGian from '../components/chi-tiet/KhoiDongThoiGian.vue'
```

Thêm:

```js
const coDot = computed(() => (bg.value?.dot || []).length > 0)
const moHuy = ref(false)
const dangHuy = ref(false)

// Huỷ các mặt hàng CHƯA báo (spec 2026-10-15 §4.4). Đợt đang chờ đồng ý vẫn
// còn hiệu lực. Hộp lý do chỉ đóng khi server đã nhận.
async function huyConLai(lyDo) {
  if (dangHuy.value) return
  dangHuy.value = true
  try {
    await api.call('portal_bao_gia_huy_con_lai', { ten: bg.value.bao_gia, ly_do: lyDo || undefined })
    moHuy.value = false
    showToast('Đã huỷ các mặt hàng chưa báo giá.')
    await load()
  } catch (e) {
    showToast(e.message || 'Không huỷ được phần còn lại.', 'error')
  } finally {
    dangHuy.value = false
  }
}
```

Template (thay toàn bộ phần sau thẻ đầu trang cho tới trước `<KhoiDongThoiGian`):

```vue
      <!-- Thẻ đầu trang giữ nguyên như cũ (mã, tên đơn, ngày, hạn, lý do, link đơn / phiếu gốc). -->

      <template v-if="coDot">
        <KhoiBaoGia v-for="d in bg.dot" :key="d.bao_gia" :bg="d" :tieu-de="nhanDot(d)" @xong="load" />

        <div v-if="bg.con_lai.length || dongChuaKhop.length || bg.duoc_huy_con_lai" class="card mb10"
             style="padding: 0; overflow-x: auto">
          <div class="sb" style="padding: 12px 14px 0">
            <div class="h3" style="margin: 0">Chờ Miyano báo giá</div>
            <span class="badge b-blue">{{ bg.con_lai.length }} mặt hàng</span>
          </div>
          <table v-if="bg.con_lai.length">
            <thead><tr><CotTenHang head /><th>ĐVT</th><th class="right">Số lượng</th></tr></thead>
            <tbody>
              <tr v-for="it in bg.con_lai" :key="it.name">
                <CotTenHang :ma="it.item_code" :ten="it.item_name || ''" />
                <td>{{ it.uom }}</td><td class="right">{{ it.qty }}</td>
              </tr>
            </tbody>
          </table>
          <div v-if="bg.duoc_huy_con_lai" style="padding: 10px 14px">
            <button class="btn-o" :disabled="dangHuy" @click="moHuy = true">✕ Huỷ phần còn lại…</button>
            <span class="tag"> Các đợt đã gửi vẫn giữ nguyên.</span>
          </div>
        </div>
      </template>
      <KhoiBaoGia v-else :bg="bg" @xong="load" />

      <div v-if="dongChuaKhop.length" class="card mb10">
        <!-- khối "Hàng quý vị mô tả — Miyano đang tìm mã" giữ nguyên -->
      </div>

      <KhoiDongThoiGian :dong="nhatKy" :dang-tai="dangTaiNhatKy" />

      <ReasonModal
        :open="moHuy"
        title="Huỷ phần còn lại"
        desc="Các mặt hàng chưa được báo giá sẽ không được báo nữa. Lý do không bắt buộc."
        placeholder="VD: Đã mua được ở nơi khác…"
        :min-len="0"
        :submitting="dangHuy"
        submit-label="Huỷ phần còn lại"
        @submit="huyConLai"
        @close="moHuy = false"
      />
```

Xoá `<style scoped>` `.nut-pdf` khỏi trang (đã sang component). Hai comment HTML "giữ nguyên" ở trên là chỉ dẫn cho người làm — trong file thật để nguyên mã cũ của hai khối đó, không để comment này.

- [ ] **Step 5: Cập nhật test nối dây giao diện**

`miyano_portal/tests/test_bao_gia_giao_dien.py`:
- `test_endpoint_frontend_goi_deu_ton_tai`: thêm `"components/KhoiBaoGia.vue"` vào bộ file quét.
- `test_chi_tiet_khong_ve_gia_khi_server_giau`, `test_thong_bao_gia_chua_co_theo_co_cua_server`, `test_sua_so_luong_chan_so_khong_hop_le`, `test_chi_tiet_dung_ba_cot_ten_hang_chung`: đổi `_doc("views/ChiTietBaoGia.vue")` → `_doc("components/KhoiBaoGia.vue")`.
- Thêm:

```python
	def test_chi_tiet_ve_moi_dot_mot_khoi(self):
		nguon = _doc("views/ChiTietBaoGia.vue")
		self.assertIn('<KhoiBaoGia v-for="d in bg.dot"', nguon)
		self.assertIn("portal_bao_gia_huy_con_lai", nguon)
		self.assertIn('v-if="bg.duoc_huy_con_lai"', nguon)
		# Dòng chưa báo không bao giờ mang giá.
		khoi = nguon.split('v-for="it in bg.con_lai"', 1)[1].split("</tr>", 1)[0]
		self.assertNotIn("fmtVND", khoi)
```

- [ ] **Step 6: Chạy test JS + Python + build**

Run:
```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal/frontend && yarn test && yarn build
cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site localhost run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_giao_dien
```
Expected: JS PASS; build xong không lỗi, `miyano_portal/public/frontend/` có file mới; Python PASS.

- [ ] **Step 7: Xem trên trình duyệt**

`bench restart` (gunicorn dev cổng 8002 cần nạp lại mã Python). Đăng nhập cổng bằng một tài khoản quản lý thử, mở một yêu cầu báo giá đã tách 2 đợt (dựng bằng `bench --site localhost console` gọi `bao_gia_theo_dot.tach_dot`). Kiểm: mỗi đợt một khối có giá + nút Đồng ý cả đợt/Từ chối; khối "Chờ Miyano báo giá" không có giá và có nút Huỷ phần còn lại; ở bề rộng 375px không cuộn ngang trang.

- [ ] **Step 8: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal
git add frontend/src/bao-gia.js frontend/src/bao-gia.test.mjs frontend/src/components/KhoiBaoGia.vue \
  frontend/src/views/ChiTietBaoGia.vue miyano_portal/tests/test_bao_gia_giao_dien.py miyano_portal/public/frontend
git commit -m "feat(portal): trang chi tiet bao gia gom cac dot

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Desk — nút "Báo giá đợt này", "Các đợt", lời giới thiệu trên đợt

**Files:**
- Modify: `miyano_portal/public/js/quotation.js`
- Test: `miyano_portal/tests/test_bao_gia_giao_dien.py` (test nối dây)

**Interfaces:**
- Consumes: `miyano_portal.bao_gia_theo_dot.tach_dot(phieu_goc, dong)` (Task 2).

- [ ] **Step 1: Test nối dây (thất bại trước)**

Cuối lớp `TestBaoGiaGiaoDien`:

```python
	def test_desk_quotation_co_nut_bao_gia_dot(self):
		js = (Path(frappe.get_app_path("miyano_portal")) / "public" / "js" / "quotation.js").read_text()
		self.assertIn('method: "miyano_portal.bao_gia_theo_dot.tach_dot"', js)
		self.assertIn('__("Báo giá đợt này")', js)
		from miyano_portal import bao_gia_theo_dot

		self.assertIn(bao_gia_theo_dot.tach_dot, frappe.whitelisted)
```

Run: `bench --site localhost run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_giao_dien`
Expected: FAIL ở test mới.

- [ ] **Step 2: Sửa `quotation.js`**

Trong `refresh(frm)`:

```js
	refresh(frm) {
		miyano_portal.hien_thong_tin_hang_moi(frm);
		gioi_thieu_dot(frm);
		nut_theo_dot(frm);
		dan_toi_don_da_sinh(frm);
	},
```

Cuối file:

```js
// Báo giá theo đợt (spec 2026-10-15 §4.1). Chốt thật nằm ở server
// (`bao_gia_theo_dot.tach_dot`, `kiem_chuyen_theo_dot`); ở đây chỉ dựng lối bấm.
function la_phieu_goc_cong(frm) {
	return frm.doc.custom_nguon_don === "Client Portal" && !frm.doc.custom_phieu_goc && !frm.is_new();
}

function nut_theo_dot(frm) {
	if (!la_phieu_goc_cong(frm)) return;
	frm.add_custom_button(__("Các đợt"), () =>
		frappe.set_route("List", "Quotation", { custom_phieu_goc: frm.doc.name })
	);
	if (frm.doc.docstatus !== 0 || frm.doc.workflow_state !== "Chờ Miyano báo giá") return;
	frm.add_custom_button(__("Báo giá đợt này"), () => hop_thoai_tach_dot(frm));
}

function hop_thoai_tach_dot(frm) {
	if (frm.is_dirty()) {
		frappe.msgprint(__("Lưu phiếu trước khi tách đợt."));
		return;
	}
	const co_gia = (frm.doc.items || []).filter((d) => flt(d.rate) > 0);
	if (!co_gia.length) {
		frappe.msgprint(__("Chưa có mặt hàng nào có đơn giá để báo."));
		return;
	}
	const dlg = new frappe.ui.Dialog({
		title: __("Báo giá đợt này"),
		fields: [
			{
				fieldtype: "HTML",
				options: `<p>${__("Chọn các mặt hàng gửi khách trong đợt này. Mặt hàng chưa có đơn giá không hiện ở đây.")}</p>`,
			},
			...co_gia.map((d) => ({
				fieldtype: "Check",
				fieldname: "d_" + d.idx,
				label: `${d.item_code} — ${d.item_name || ""} · ${d.qty} ${d.uom || ""} × ${format_currency(d.rate, frm.doc.currency)}`,
			})),
		],
		primary_action_label: __("Tạo đợt và gửi khách"),
		primary_action(v) {
			const dong = co_gia.filter((d) => v["d_" + d.idx]).map((d) => d.name);
			if (!dong.length) {
				frappe.msgprint(__("Chọn ít nhất một mặt hàng."));
				return;
			}
			frappe
				.call({
					method: "miyano_portal.bao_gia_theo_dot.tach_dot",
					args: { phieu_goc: frm.doc.name, dong: JSON.stringify(dong) },
					freeze: true,
				})
				.then((r) => {
					dlg.hide();
					frappe.show_alert({
						message: __("Đã gửi khách đợt {0}: {1}", [r.message.so_dot, r.message.dot]),
						indicator: "green",
					});
					frm.reload_doc();
				});
		},
	});
	dlg.show();
}

function gioi_thieu_dot(frm) {
	if (!frm.doc.custom_phieu_goc) return;
	const goc = frm.doc.custom_phieu_goc;
	frm.set_intro(
		__("Đợt {0} của yêu cầu báo giá {1}.", [
			frm.doc.custom_so_dot,
			`<a href="/app/quotation/${encodeURIComponent(goc)}">${frappe.utils.escape_html(goc)}</a>`,
		]) + (frm.doc.custom_da_tra_ve ? " " + __("Các mặt hàng đã trả về phiếu gốc.") : ""),
		"blue"
	);
}
```

- [ ] **Step 3: Chạy test, build asset, thử trên Desk**

Run:
```bash
cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site localhost run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_giao_dien && bench build --app miyano_portal
```
Expected: PASS; build xong.

Mở `/app/quotation/<phiếu gốc cổng ở Chờ Miyano báo giá>`: có nút "Báo giá đợt này" và "Các đợt"; chọn 1 dòng → đợt mới ở "Chờ khách đồng ý", phiếu gốc còn các dòng kia. Mở đợt: có dòng giới thiệu "Đợt 1 của yêu cầu báo giá …". Với user Administrator, các nút «Hệ thống: …» chỉ hiện khi phiếu có đợt — chấp nhận được.

- [ ] **Step 4: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal
git add miyano_portal/public/js/quotation.js miyano_portal/tests/test_bao_gia_giao_dien.py
git commit -m "feat(desk): nut bao gia dot nay tren yeu cau bao gia cua cong

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Hồi quy toàn bộ và migrate site dev

**Files:** không sửa mã (chỉ sửa nếu hồi quy lộ lỗi; mỗi chỗ sửa một commit riêng).

- [ ] **Step 1: Migrate site dev**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site localhost migrate`
Expected: chạy patch `v1_45`, không lỗi. Kiểm: `bench --site localhost execute frappe.db.get_value --args "['Workflow', 'Quotation - Client Portal', 'name']"` trả tên workflow; `bench --site localhost console` → `len(frappe.get_doc("Workflow","Quotation - Client Portal").transitions) == 12`.

- [ ] **Step 2: Toàn bộ test miyano_portal**

Run: `bench --site localhost run-tests --app miyano_portal 2>&1 | tail -20`
Expected: `OK` — 2404 test cũ + test mới, không FAILED. Lỗi nào thì đọc traceback, sửa tận gốc, commit riêng, chạy lại.

- [ ] **Step 3: Test frontend**

Run: `cd apps/miyano_portal/frontend && yarn test`
Expected: PASS.

- [ ] **Step 4: Kiểm tay luồng đầy đủ trên cổng (bench restart trước)**

1. Desk: phiếu 3 mặt hàng → tách đợt 1 (2 mặt hàng). Cổng: danh sách 1 dòng, nhóm "Chờ anh/chị đồng ý", huy hiệu = 1.
2. Cổng: đồng ý đợt 1 → có đơn; khối đợt 1 có link đơn.
3. Desk: tách đợt 2 (mặt hàng còn lại) → phiếu gốc "Đã báo hết".
4. Cổng: từ chối đợt 2 → khối đợt 2 "đã trả về phiếu"; khối "Chờ Miyano báo giá" có lại mặt hàng; phiếu gốc về "Chờ Miyano báo giá".
5. Cổng: "Huỷ phần còn lại" → nhóm "Đã đóng"; nhân viên phụ trách có Notification Log.

- [ ] **Step 5: Báo cáo**

Nêu số test chạy/đạt, các chỗ phải sửa trong hồi quy (nếu có), và việc còn lại: push nhánh `feat/bao-gia-theo-dot`, mở PR vào `main`.
