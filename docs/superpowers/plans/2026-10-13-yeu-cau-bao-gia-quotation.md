# Yêu cầu báo giá bằng Quotation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Yêu cầu báo giá của khách trở thành chứng từ Quotation của ERPNext (không còn là Sales Order `"Mua lẻ"`), có tab riêng trên cổng; Sales Order chỉ sinh ra khi khách đồng ý.

**Architecture:** Một module mới `bao_gia.py` giữ toàn bộ vòng đời Quotation của cổng (dựng, chốt gửi khách, đồng ý → sinh đơn, từ chối, sửa số lượng, hết hạn). Quotation đi workflow mới `Quotation - Client Portal`; bước phía khách khai `System Manager` và chạy qua một hàm nâng quyền dùng chung. Tài khoản cổng không có DocPerm trên Quotation: cổng chỉ đọc/ghi qua endpoint trong `api/portal.py`, mỗi endpoint tự kiểm khách và khoa. Hai đường tạo đơn (`duyet_va_tao_don`, `portal_order_place`) rẽ sang Quotation ở task gần cuối, nên mọi thứ trước đó là mã chưa được gọi tới.

**Tech Stack:** Frappe 15.113 / ERPNext 15.83 (Python 3.12), Vue 3.4 + Vite 6, MariaDB. Test: `FrappeTestCase` qua `bench run-tests`; frontend `node --test`.

**Spec:** `docs/superpowers/specs/2026-10-12-yeu-cau-bao-gia-quotation-design.md` — đọc trước khi làm bất kỳ task nào. Mục "Đính chính spec" ngay dưới thay cho các câu tương ứng trong spec.

## Global Constraints

- **Nơi chạy.** `bench` nạp mã từ `/home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal` (APP), không nạp worktree. Kế hoạch này chỉ chạy được khi nhánh `feat/thoi-gian-giao-hang-va-gia-bang-gia` đã vào `main` VÀ phiên đang làm việc trong APP đã nhả thư mục. Task 0 kiểm hai điều đó; chưa đạt thì dừng và hỏi chủ dự án, không tự `git switch` trong APP.
- Nhánh làm việc: `feat/yeu-cau-bao-gia-quotation`, rebase lên `main` sau khi Price List gộp xong.
- Mã nguồn được nhắc theo TÊN HÀM, không theo số dòng (số dòng đổi sau rebase). Trước khi sửa một hàm, mở nó ra đọc.
- Chạy test: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.<ten_file>`.
- `erptest.local` cũng là site chủ dự án đang mở qua `192.168.61.129`. Không xoá dữ liệu ngoài dữ liệu test (`_TEST DX%`). Không Submit chứng từ thật, không đổi cấu hình ERP ngoài những gì patch của kế hoạch này làm.
- Thụt lề theo file đang sửa: `api/portal.py`, `dat_hang.py`, `portal_mua_le.py`, `portal_context.py`, `permissions.py`, `rest_guard.py`, `portal_bao_gia.py`, `portal_sla.py`, `setup/install_*.py` (trừ `install_kho_workspace.py`) dùng 4 dấu cách; `hooks.py`, `de_xuat_duyet.py`, `install_kho_workspace.py`, `public/js/*.js` và mọi file MỚI dùng tab.
- Tên trường, hằng số, thông báo: tiếng Việt, fieldname không dấu. Commit message không dấu, tiền tố `feat(portal):` / `test(portal):` / `docs:`; kết thúc bằng `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Không push, không mở PR khi chưa được yêu cầu.
- Không commit ba file `miyano_portal/tests/test_e7_hddt.py`, `test_e7_hddt_nhap.py`, `test_e7b_tu_dong.py` nếu chúng còn thay đổi dở.
- Giá `<= 0` là CHƯA khai giá, không phải "bán 0 đồng".
- Chuỗi cố định (chép nguyên văn):
  - Workflow: `"Quotation - Client Portal"`.
  - Trạng thái: `"Chờ Miyano báo giá"`, `"Chờ khách đồng ý"`, `"Khách đã đồng ý"`, `"Khách từ chối"`, `"Miyano từ chối"`, `"Báo giá hết hạn"`.
  - Hành động: `"Gửi khách duyệt"`, `"Từ chối"`, `"Thu hồi để sửa"`, `"Khách đồng ý"`, `"Khách từ chối"`, `"Khách sửa số lượng"`, `"Báo giá hết hạn"`, `"Ghi nhận khách đồng ý"`.
  - Loại đơn mới: `"Theo báo giá"`. Nguồn đơn: `"Client Portal"`. Hậu tố mã yêu cầu của đơn sinh từ báo giá: `":don"`.
  - Khoá nhóm của tab báo giá: `nhap`, `dang_bao_gia`, `cho_dong_y`, `da_dong_y`, `da_dong`. KHÔNG thêm các khoá này vào `GIAI_DOAN` (`format.js`) hay `GIAI_DOAN_HOP_LE` (`api/portal.py`): `test_giai_doan_khoa_va_nhan` soi hai danh sách đó.
- Mọi endpoint cổng mới nằm trong `miyano_portal/api/portal.py` (`test_de_xuat_action_registry` quét mọi `api.call('...')` của frontend và đòi hàm whitelist cùng tên trong file đó).
- Bundle `miyano_portal/public/frontend/` được commit. Chỉ build một lần ở Task 15; sau mỗi lần rebase thì build lại, không merge bundle.
- Bộ test đầy đủ có lỗi sẵn có ở `test_kho_isolation`, `test_e7_hddt`, `test_e7_hddt_nhap`, `test_tb6_bao_cao`, `test_notifications`. Task 0 ghi lại danh sách lỗi nền; mọi lỗi ngoài danh sách đó là của kế hoạch này.

## Đính chính spec (đo trên mã ngày 13/10/2026)

| # | Spec viết | Thực tế | Kế hoạch làm |
|---|---|---|---|
| D1 | §4.4: đặt trạng thái đơn bằng `frappe.db.set_value` "theo tiền lệ `duyet_va_tao_don`" | Hàm đó không đặt trạng thái; đơn mới nhận trạng thái đầu của workflow | Chèn đơn ở "Chờ xác nhận" rồi `apply_workflow(so, "Gửi duyệt")` dưới quyền hệ thống → "Chờ Miyano xác nhận". Là bước chuyển thật nên hook chạy đủ |
| D2 | §8: cần "đo" `/orders` | Tài khoản cổng có dòng `Portal User` trên Customer (vd. `bvminhduc@demo.miyano`) qua được chốt trang web của ERPNext cho cả Sales Order lẫn Quotation | Task 3 chặn `/quotations`, `/quotations/<tên>` và đường in. `/orders` là lỗ có từ trước, ngoài phạm vi; báo chủ dự án |
| D3 | §7: quá hạn xử lý "cùng ngưỡng với đơn chờ báo giá hiện nay" | Không có job nào quét đơn chờ báo giá | Dùng `sla_xu_ly_don_gio` (Miyano Portal Settings), tính giờ làm việc từ `modified` của Quotation |
| D4 | §6.4: thẻ Dashboard "đếm báo giá chờ đồng ý" | Dashboard chưa có thẻ này | Thêm khoá `bao_gia_cho_dong_y` vào `portal_dashboard_kpi` và một thẻ mới |
| D5 | §10: `ghi_gia_da_dong_y` "nhận Quotation" | Hàm đọc dòng mang dấu `"Báo giá"` của một Sales Order | Truyền chính Sales Order vừa sinh (dòng đã mang dấu và giá). Không sửa `bang_gia_khach.py` |
| D6 | §7: mẫu in tên "Miyano - Báo giá" cho Quotation | Tên đó đã thuộc mẫu của Sales Order; tên Print Format là duy nhất | Mẫu mới tên `"Miyano - Yêu cầu báo giá"` |
| D7 | §6.3: dùng lại `ChiTietYeuCau.vue` | View đó 967 dòng, hai chế độ phiếu/đơn đan nhau | View mới `ChiTietBaoGia.vue`, dùng lại component con (`KhoiDongThoiGian`, `ReasonModal`) |
| D8 | §3.1: ba trường `no_copy` | `custom_dat_ngoai` cùng tên, cùng bảng con trên hai doctype nên mapper tự chép, mang theo `dong_hang` trỏ sai | `Quotation.custom_dat_ngoai` cũng `no_copy`. Đơn sinh ra không mang dòng gõ tay (Q4: lúc đó mọi dòng đã có mã) |
| D9 | §3.1 không có trường trên Quotation Item | Hook khớp dòng gõ tay ghi `custom_nguon_gia` lên dòng hàng | Thêm `Quotation Item.custom_nguon_gia` (Select, chỉ đọc, `no_copy`) |
| D10 | §6.4: sáu endpoint | Dải tab cần số đếm ở cả hai màn | Thêm endpoint thứ bảy `portal_bao_gia_dem` |

Quyết định spec để ngỏ, kế hoạch chọn (đổi được, mỗi cái nằm gọn trong một task):

- **Ai được bấm.** Đồng ý / từ chối: mọi tài khoản trong phạm vi (đúng khách, đúng khoa), như `portal_order_accept` hôm nay. Sửa số lượng: chỉ quản lý. Nhân viên khoa "xin sửa số lượng" qua phiếu (`de_xuat_xin_sua`) KHÔNG có cho báo giá trong đợt này: nút đó vốn đòi phiếu có `sales_order`, nên tự ẩn (Task 8).
- **Ngày giao của đơn sinh ra.** Lấy `ngay_can` của phiếu gốc nếu còn hợp lệ, không thì `ngay_giao_mac_dinh()` (Task 7).
- **Phiếu nháp còn trộn** (có cả dòng có giá lẫn dòng chờ báo giá, chưa tách) ở lại tab Đơn hàng cho tới khi gửi duyệt và được tách (Task 11).
- **Q6** (workflow phủ mọi Quotation) chưa được chủ dự án xác nhận bằng lời. Nó nằm gọn trong Task 2; hỏi lại ở bước bàn giao kế hoạch.

## Review Focus

1. **Hai người cùng bấm Đồng ý.** Chỉ được sinh MỘT đơn; lần sau trả về đúng đơn đó. Test: Task 7 `test_goi_lai_khong_sinh_don_thu_hai`.
2. **Nhân viên Miyano gõ đơn giá khác giá Price List.** Đơn sinh ra phải mang đúng đơn giá khách đã đồng ý, không bị `set_missing_values` hay trường margin kéo về giá bảng. Test: Task 7 `test_gia_don_dung_gia_khach_dong_y_khi_khac_bang_gia`.
3. **Dòng gõ tay được khớp vào mã ĐÃ CÓ giá trong Price List.** Dòng hàng sinh ra phải nhận giá bảng (trên Quotation không có cột `customer`, đọc nhầm thì mọi dòng lặng lẽ về giá 0). Test: Task 6 `test_khop_ma_co_gia_bang_gia_nhan_gia_bang`.
4. **Báo giá quá hạn nhưng job chưa chạy.** Khách bấm Đồng ý phải bị từ chối với thông báo hết hạn. Test: Task 7 `test_qua_han_khong_dong_y_duoc`.
5. **Tài khoản cổng có dòng `Portal User` mở `/quotations`, `/quotations/<tên>`, `/printview?doctype=Quotation`.** Cả ba phải bị từ chối, kể cả với báo giá của chính bệnh viện họ. Test: Task 3 `test_trang_web_erpnext_bi_chan` và `TestBaoGiaHTTP`.
6. **Nhân viên có vai System Manager bấm "Khách đồng ý" trên Desk cho báo giá của cổng.** Phải bị chặn (không có đơn nào sinh ra theo đường đó). Test: Task 2 `test_khong_dong_y_thay_khach_cong_tren_desk`.
7. **Ngày cần hàng trên phiếu đã trôi qua lúc khách đồng ý.** Đơn vẫn sinh, với ngày giao mặc định. Test: Task 7 `test_ngay_can_da_qua_dung_ngay_mac_dinh`.
8. **Đơn `"Mua lẻ"` đang ở "Chờ khách đồng ý" lúc triển khai.** Vẫn đồng ý được và vẫn ghi giá. Test: Task 13 `test_don_mua_le_cu_van_dong_y_duoc`.

## File Structure

| Tệp | Trách nhiệm |
|---|---|
| Create `miyano_portal/bao_gia.py` | Hằng số; hook của Quotation; dựng Quotation; đồng ý / từ chối / sửa số lượng; hết hạn; báo nhân viên |
| Create `miyano_portal/nang_quyen.py` | `quyen_he_thong()` — chạy một khối dưới quyền hệ thống mà không hỏng phiên của khách |
| Create `miyano_portal/patches/v1_42/__init__.py`, `bao_gia_quotation.py` | Custom field, lựa chọn `"Theo báo giá"`, workflow, mẫu in, thông báo, workspace |
| Modify `miyano_portal/miyano_portal/doctype/portal_de_xuat_mua/portal_de_xuat_mua.json` | Trường `bao_gia` |
| Modify `miyano_portal/setup/install_workflow.py` | `install_quotation_workflow()` |
| Modify `miyano_portal/setup/install_print_formats.py`, `install_notifications.py`, `install_kho_workspace.py` | Mẫu in, thông báo, lối tắt hàng việc |
| Modify `miyano_portal/permissions.py`, `rest_guard.py`, `portal_context.py`, `hooks.py` | Cách ly Quotation |
| Modify `miyano_portal/portal_mua_le.py` | `ben_mua()`; hook khớp dòng gõ tay chạy được trên Quotation |
| Modify `miyano_portal/api/portal.py` | Bảy endpoint; tab Đơn hàng loại phiếu chờ báo giá; KPI; đường dẫn thông báo; rẽ nhánh `portal_order_place`; dùng `quyen_he_thong` |
| Modify `miyano_portal/de_xuat_duyet.py` | Rẽ nhánh `duyet_va_tao_don` |
| Modify `miyano_portal/chot_bao_gia.py` | Chốt 3 cho đơn `"Theo báo giá"` |
| Modify `miyano_portal/portal_bao_gia.py`, `portal_sla.py` | Job hết hạn và SLA quét thêm Quotation |
| Create `miyano_portal/public/js/hang_moi_khach_khai.js`, `quotation.js`; modify `sales_order.js` | Khối "Hàng chưa có mã" dùng chung |
| Create `frontend/src/bao-gia.js`, `bao-gia.test.mjs` | Nhóm, nhãn, hành động của báo giá (JS thuần, có test) |
| Create `frontend/src/components/TabDonBaoGia.vue`, `views/BaoGiaList.vue`, `views/ChiTietBaoGia.vue` | Dải hai tab, danh sách, chi tiết |
| Modify `frontend/src/router.js`, `App.vue`, `views/YeuCauList.vue`, `views/ChiTietYeuCau.vue`, `views/Dashboard.vue`, `views/LapPhieu.vue`, `format.js` | Nối tab và đường dẫn |
| Create `miyano_portal/tests/test_patch_bao_gia_quotation.py`, `test_bao_gia_workflow.py`, `test_bao_gia_cach_ly.py`, `test_nang_quyen.py`, `test_tao_bao_gia.py`, `test_bao_gia_gui_khach.py`, `test_bao_gia_dong_y.py`, `test_bao_gia_tu_choi_sua.py`, `test_bao_gia_het_han.py`, `test_bao_gia_cai_dat.py`, `test_bao_gia_endpoint.py`, `test_bao_gia_re_nhanh.py`, `test_don_theo_bao_gia.py`, `test_bao_gia_giao_dien.py` | Mỗi task một file test |

Lớp nền dùng chung cho test (định nghĩa ở Task 2, các task sau `import`): `miyano_portal/tests/nen_bao_gia.py`.

---

### Task 0: Điều kiện bắt đầu

**Files:** không sửa file nào.

- [ ] **Step 1: Kiểm Price List đã vào `main`**

Run: `cd /home/hoangvietyeuem/worktrees/miyano_portal-bao-gia-quotation && git fetch origin && git ls-tree -r origin/main --name-only | grep -c -E "miyano_portal/(bang_gia_khach|tach_phieu|chot_bao_gia)\.py"`
Expected: `3`. Nếu nhỏ hơn 3: DỪNG, báo chủ dự án rằng nhánh Price List chưa gộp.

- [ ] **Step 2: Rebase nhánh lên `main`**

Run: `git rebase origin/main && git log --oneline -3`
Expected: hai commit tài liệu (spec, plan) nằm trên đầu `origin/main`, không xung đột.

- [ ] **Step 3: Kiểm APP đã được nhả**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal && git status --short && git branch --show-current`
Expected: không còn thay đổi dở nào ngoài ba file `test_e7*`. Nếu còn thay đổi khác hoặc chưa chắc phiên kia đã xong: DỪNG và hỏi chủ dự án. Chỉ khi chủ dự án đồng ý mới chuyển APP sang nhánh này (`git switch feat/yeu-cau-bao-gia-quotation`), và từ đó mọi sửa đổi làm trong APP.

- [ ] **Step 4: Ghi lỗi nền của bộ test**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal 2>&1 | tee /tmp/nen.log | grep -E "^(ERROR|FAIL):" | sort > /tmp/nen-loi.txt; grep -E "^Ran |^OK|^FAILED" /tmp/nen.log; wc -l < /tmp/nen-loi.txt`
Expected: một dòng `Ran N tests` và số lỗi nền. Giữ `/tmp/nen-loi.txt` để so ở Task 15.

- [ ] **Step 5: Kiểm Quotation có sẵn trên site**

Run: `bench --site erptest.local execute frappe.db.sql --args "['select docstatus, count(*) from tabQuotation group by docstatus']"`
Expected: `()` hoặc vài dòng. Ghi con số lại: Task 2 gán trạng thái cho các Quotation có sẵn này.

---

### Task 1: Trường mới và lựa chọn "Theo báo giá"

**Files:**
- Create: `miyano_portal/patches/v1_42/__init__.py` (rỗng)
- Create: `miyano_portal/patches/v1_42/bao_gia_quotation.py`
- Modify: `miyano_portal/miyano_portal/doctype/portal_de_xuat_mua/portal_de_xuat_mua.json`
- Modify: `miyano_portal/patches.txt`
- Test: `miyano_portal/tests/test_patch_bao_gia_quotation.py`

**Interfaces:**
- Produces: custom field trên `Quotation`: `custom_nguon_don`, `custom_de_xuat`, `custom_khoa_phong`, `custom_ten_don_hang`, `custom_request_id` (unique, no_copy), `custom_ngay_gui_khach_duyet` (Datetime, no_copy), `custom_ly_do_tu_choi` (no_copy), `custom_dat_ngoai` (Table, no_copy); trên `Quotation Item`: `custom_nguon_gia`; `Portal De Xuat Mua.bao_gia` (Link → Quotation); lựa chọn `"Theo báo giá"` của `Sales Order.custom_loai_don`. Hàm `bao_gia_quotation.them_truong()` và `execute()`.

- [ ] **Step 1: Viết test hỏng**

```python
"""Patch v1_42 — trường của Quotation và lựa chọn "Theo báo giá" (spec 2026-10-12 §3, §9)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.patches.v1_42 import bao_gia_quotation


class TestPatchBaoGiaQuotation(FrappeTestCase):
	def test_truong_tren_quotation(self):
		bao_gia_quotation.them_truong()
		meta = frappe.get_meta("Quotation")
		for ten in (
			"custom_nguon_don", "custom_de_xuat", "custom_khoa_phong",
			"custom_ten_don_hang", "custom_request_id",
			"custom_ngay_gui_khach_duyet", "custom_ly_do_tu_choi", "custom_dat_ngoai",
		):
			self.assertTrue(meta.has_field(ten), ten)
		self.assertEqual(meta.get_field("custom_dat_ngoai").options, "Sales Order Dat Ngoai Item")
		self.assertEqual(meta.get_field("custom_ngay_gui_khach_duyet").fieldtype, "Datetime")
		self.assertTrue(meta.get_field("custom_request_id").unique)

	def test_bon_truong_khong_chep_sang_don(self):
		bao_gia_quotation.them_truong()
		meta = frappe.get_meta("Quotation")
		for ten in (
			"custom_request_id", "custom_ngay_gui_khach_duyet",
			"custom_ly_do_tu_choi", "custom_dat_ngoai",
		):
			self.assertEqual(meta.get_field(ten).no_copy, 1, ten)

	def test_dau_nguon_gia_tren_dong_bao_gia(self):
		bao_gia_quotation.them_truong()
		truong = frappe.get_meta("Quotation Item").get_field("custom_nguon_gia")
		self.assertEqual(truong.options, "\nBảng giá\nBáo giá")
		self.assertEqual(truong.no_copy, 1)

	def test_phieu_co_truong_bao_gia(self):
		bao_gia_quotation.them_truong()
		truong = frappe.get_meta("Portal De Xuat Mua").get_field("bao_gia")
		self.assertEqual((truong.fieldtype, truong.options), ("Link", "Quotation"))
		self.assertEqual(truong.no_copy, 1)

	def test_lua_chon_theo_bao_gia(self):
		bao_gia_quotation.them_truong()
		lua_chon = frappe.get_meta("Sales Order").get_field("custom_loai_don").options.split("\n")
		self.assertIn("Theo báo giá", lua_chon)
		self.assertIn("Mua lẻ", lua_chon)

	def test_chay_hai_lan_cung_ket_qua(self):
		bao_gia_quotation.them_truong()
		bao_gia_quotation.them_truong()
		lua_chon = frappe.get_meta("Sales Order").get_field("custom_loai_don").options.split("\n")
		self.assertEqual(lua_chon.count("Theo báo giá"), 1)
		self.assertEqual(
			frappe.db.count("Custom Field", {"dt": "Quotation", "fieldname": "custom_request_id"}), 1
		)
```

- [ ] **Step 2: Chạy, xác nhận hỏng**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_patch_bao_gia_quotation`
Expected: FAIL — `ModuleNotFoundError: No module named 'miyano_portal.patches.v1_42'`.

- [ ] **Step 3: Thêm trường `bao_gia` vào doctype phiếu**

Trong `portal_de_xuat_mua.json`: thêm `"bao_gia"` vào `field_order` ngay SAU `"sales_order"`, và thêm vào `fields` ngay sau định nghĩa `sales_order`:

```json
  {
   "fieldname": "bao_gia",
   "fieldtype": "Link",
   "label": "Yêu cầu báo giá",
   "options": "Quotation",
   "read_only": 1,
   "no_copy": 1,
   "search_index": 1
  },
```

- [ ] **Step 4: Viết patch**

`miyano_portal/patches/v1_42/__init__.py`: file rỗng.

`miyano_portal/patches/v1_42/bao_gia_quotation.py`:

```python
"""Yêu cầu báo giá bằng Quotation (spec 2026-10-12 §3, §9).

Chạy lại được: `install.py::after_install` gọi lại mọi patch, nên từng bước
phải cho cùng kết quả ở lần chạy thứ hai.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

LOAI_DON_THEO_BAO_GIA = "Theo báo giá"


def them_truong():
	# Trường `bao_gia` nằm trong .json của phiếu: site cũ chỉ thấy sau khi nạp lại.
	frappe.reload_doc("miyano_portal", "doctype", "portal_de_xuat_mua")
	create_custom_fields({
		"Quotation": [
			{
				"fieldname": "custom_sec_cong_khach_hang", "label": "Cổng khách hàng",
				"fieldtype": "Section Break", "insert_after": "amended_from",
				"collapsible": 1,
			},
			{
				"fieldname": "custom_nguon_don", "label": "Nguồn",
				"fieldtype": "Select", "options": "Nội bộ\nClient Portal",
				"default": "Nội bộ", "insert_after": "custom_sec_cong_khach_hang",
				"read_only": 1, "in_standard_filter": 1,
			},
			{
				"fieldname": "custom_de_xuat", "label": "Phiếu gốc",
				"fieldtype": "Link", "options": "Portal De Xuat Mua",
				"insert_after": "custom_nguon_don", "read_only": 1, "search_index": 1,
			},
			{
				"fieldname": "custom_khoa_phong", "label": "Khoa phòng",
				"fieldtype": "Link", "options": "Customer Department",
				"insert_after": "custom_de_xuat", "read_only": 1, "search_index": 1,
			},
			{
				"fieldname": "custom_ten_don_hang", "label": "Tên đơn hàng",
				"fieldtype": "Data", "insert_after": "custom_khoa_phong",
			},
			{
				"fieldname": "custom_request_id", "label": "Mã yêu cầu",
				"fieldtype": "Data", "insert_after": "custom_ten_don_hang",
				"read_only": 1, "unique": 1, "no_copy": 1,
			},
			{
				"fieldname": "custom_ngay_gui_khach_duyet", "label": "Gửi khách duyệt lúc",
				"fieldtype": "Datetime", "insert_after": "custom_request_id",
				"read_only": 1, "no_copy": 1,
			},
			{
				"fieldname": "custom_ly_do_tu_choi", "label": "Lý do từ chối",
				"fieldtype": "Small Text", "insert_after": "custom_ngay_gui_khach_duyet",
				"no_copy": 1,
			},
			{
				# `no_copy` là BẮT BUỘC: Sales Order có bảng cùng tên, cùng bảng
				# con, nên mapper Quotation → Sales Order sẽ tự chép dòng gõ tay
				# sang đơn, mang theo `dong_hang` trỏ vào dòng của BÁO GIÁ.
				"fieldname": "custom_dat_ngoai", "label": "Hàng khách gõ tay (chưa có mã)",
				"fieldtype": "Table", "options": "Sales Order Dat Ngoai Item",
				"insert_after": "items", "no_copy": 1,
			},
		],
		"Quotation Item": [
			{
				"fieldname": "custom_nguon_gia", "label": "Nguồn giá",
				"fieldtype": "Select", "options": "\nBảng giá\nBáo giá",
				"insert_after": "rate", "read_only": 1, "no_copy": 1,
				"in_list_view": 1, "columns": 1,
			},
		],
	}, ignore_validate=True)

	# `custom_loai_don` là Custom Field: lựa chọn nằm ở `options` của chính nó.
	ten = frappe.db.get_value(
		"Custom Field", {"dt": "Sales Order", "fieldname": "custom_loai_don"}, "name"
	)
	if not ten:
		frappe.log_error(
			title="Patch v1_42: thiếu Custom Field custom_loai_don",
			message=(
				"Không tìm thấy Custom Field `custom_loai_don` trên Sales Order nên "
				f'CHƯA thêm được lựa chọn "{LOAI_DON_THEO_BAO_GIA}". Tạo lại field '
				"(patch v1_8) rồi chạy lại "
				"`miyano_portal.patches.v1_42.bao_gia_quotation.them_truong`."
			),
		)
		return
	lua_chon = (frappe.db.get_value("Custom Field", ten, "options") or "").split("\n")
	if LOAI_DON_THEO_BAO_GIA not in lua_chon:
		lua_chon.append(LOAI_DON_THEO_BAO_GIA)
		frappe.db.set_value("Custom Field", ten, "options", "\n".join(lua_chon))
		frappe.clear_cache(doctype="Sales Order")


def execute():
	them_truong()
```

Thêm vào cuối `miyano_portal/patches.txt`:

```
miyano_portal.patches.v1_42.bao_gia_quotation
```

- [ ] **Step 5: Chạy, xác nhận qua**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_patch_bao_gia_quotation`
Expected: `Ran 6 tests` … `OK`.

- [ ] **Step 6: Áp patch lên site test (để các task sau có cột thật)**

Run: `bench --site erptest.local execute miyano_portal.patches.v1_42.bao_gia_quotation.execute && bench --site erptest.local execute frappe.db.has_column --args "['Quotation', 'custom_request_id']"`
Expected: `True`.

- [ ] **Step 7: Commit**

```bash
git add miyano_portal/patches/v1_42 miyano_portal/patches.txt miyano_portal/miyano_portal/doctype/portal_de_xuat_mua/portal_de_xuat_mua.json miyano_portal/tests/test_patch_bao_gia_quotation.py
git commit -m "feat(portal): truong cua Quotation, phieu.bao_gia va loai don Theo bao gia (patch v1_42)"
```

---

### Task 2: Workflow `Quotation - Client Portal`

**Files:**
- Create: `miyano_portal/bao_gia.py`
- Create: `miyano_portal/tests/nen_bao_gia.py`
- Modify: `miyano_portal/setup/install_workflow.py`
- Modify: `miyano_portal/patches/v1_42/bao_gia_quotation.py`
- Modify: `miyano_portal/hooks.py`
- Test: `miyano_portal/tests/test_bao_gia_workflow.py`

**Interfaces:**
- Consumes: trường của Task 1.
- Produces:
  - `bao_gia.WORKFLOW`, `NGUON_CONG = "Client Portal"`, `LOAI_DON_THEO_BAO_GIA`, `HAU_TO_DON = ":don"`; trạng thái `TT_CHO_MIYANO`, `TT_CHO_KHACH`, `TT_DA_DONG_Y`, `TT_KHACH_TU_CHOI`, `TT_MIYANO_TU_CHOI`, `TT_HET_HAN`; hành động `HD_GUI_KHACH`, `HD_TU_CHOI`, `HD_THU_HOI`, `HD_KHACH_DONG_Y`, `HD_KHACH_TU_CHOI`, `HD_KHACH_SUA_SL`, `HD_HET_HAN`, `HD_GHI_NHAN`.
  - Hook `bao_gia.chan_dong_y_ngoai_cong(doc, method=None)` (`before_submit`), `bao_gia.kiem_ly_do_tu_choi(doc, method=None)` (`validate`).
  - Cờ `frappe.flags.bao_gia_dong_y_qua_cong` = tên báo giá đang được khách đồng ý qua cổng (Task 7 đặt).
  - `install_workflow.install_quotation_workflow()`, `install_workflow.gan_trang_thai_bao_gia_cu() -> int`.
  - `tests/nen_bao_gia.py`: `NenBaoGia(FrappeTestCase)` với `self.kh_a`, `self.kh_b`, `self.khoa_huyethoc`, `self.khoa_duoc`, `self.item_ngoai` (có giá 54000), `self.item_boi_so` (chưa có giá, bội số 10), `self.price_list`, `self.user_a`, `self.user_b`; `_bao_gia_tho(nguon="Client Portal", khach=None, khoa=None, **them) -> Document`; `_quan_ly(email, khach) -> str`.

- [ ] **Step 1: Viết lớp nền cho test**

`miyano_portal/tests/nen_bao_gia.py`:

```python
"""Dữ liệu nền cho mọi test của Quotation (kế hoạch 2026-10-13).

Mượn `setUp` của `TestPortalCatalogGop` (khách A/B, khoa, mặt hàng, Price List)
như `test_chot_bao_gia`, rồi đưa hai mặt hàng về đúng một trạng thái giá:
`item_ngoai` CÓ giá 54000, `item_boi_so` CHƯA có giá.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import bao_gia
from miyano_portal.tests import test_catalog_gop as goc


class NenBaoGia(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		# Bản Workflow trong cache tài liệu không theo giao dịch: xoá SAU rollback.
		cls.addClassCleanup(frappe.clear_document_cache, "Workflow", bao_gia.WORKFLOW)
		super().setUpClass()
		from miyano_portal.patches.v1_42 import bao_gia_quotation

		bao_gia_quotation.execute()

	def setUp(self):
		goc.TestPortalCatalogGop.setUp(self)
		for ma in (self.item_ngoai, self.item_boi_so):
			for ten in frappe.get_all(
				"Item Price", filters={"item_code": ma, "selling": 1}, pluck="name"
			):
				frappe.delete_doc("Item Price", ten, force=True)
		self._tao_gia(self.item_ngoai, self.price_list, 54000)
		for ten in frappe.get_all(
			"Quotation", filters={"party_name": ["like", "_TEST DX%"], "docstatus": 0},
			pluck="name",
		):
			frappe.delete_doc("Quotation", ten, force=True)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.flags.bao_gia_dong_y_qua_cong = None

	# Mượn nguyên các hàm dựng dữ liệu của lớp gốc.
	_tao_item = goc.TestPortalCatalogGop._tao_item
	_tao_bin = goc.TestPortalCatalogGop._tao_bin
	_tao_price_list = goc.TestPortalCatalogGop._tao_price_list
	_tao_gia = goc.TestPortalCatalogGop._tao_gia
	_dam_bao_thanh_vien = goc.TestPortalCatalogGop._dam_bao_thanh_vien

	def _quan_ly(self, email, khach):
		return self._dam_bao_thanh_vien(email, khach, "Quản lý", None)

	def _bao_gia_tho(self, nguon="Client Portal", khach=None, khoa=None, **them):
		"""Một Quotation chèn thẳng, không qua `bao_gia.tao_bao_gia` (Task 5)."""
		bg = frappe.get_doc({
			"doctype": "Quotation", "quotation_to": "Customer",
			"party_name": khach or self.kh_a, "company": goc.COMPANY,
			"selling_price_list": self.price_list, "ignore_pricing_rule": 1,
			"custom_nguon_don": nguon, "custom_khoa_phong": khoa,
			"custom_request_id": frappe.generate_hash(length=12),
			"items": [{
				"item_code": self.item_ngoai, "qty": 10,
				"rate": 54000, "price_list_rate": 54000,
			}],
			**them,
		})
		bg.insert(ignore_permissions=True)
		return bg
```

- [ ] **Step 2: Viết test hỏng**

`miyano_portal/tests/test_bao_gia_workflow.py`:

```python
"""Workflow "Quotation - Client Portal" (spec 2026-10-12 §4.1)."""

import frappe
from frappe.model.workflow import apply_workflow, get_transitions

from miyano_portal import bao_gia
from miyano_portal.setup import install_workflow
from miyano_portal.tests.nen_bao_gia import NenBaoGia


class TestBaoGiaWorkflow(NenBaoGia):
	def test_cai_dat_chay_lai_duoc(self):
		install_workflow.install_quotation_workflow()
		install_workflow.install_quotation_workflow()
		wf = frappe.get_doc("Workflow", bao_gia.WORKFLOW)
		self.assertEqual(wf.document_type, "Quotation")
		self.assertEqual(wf.is_active, 1)
		self.assertEqual(len(wf.states), 6)
		self.assertEqual(len(wf.transitions), 8)

	def test_workflow_don_hang_van_hoat_dong(self):
		self.assertEqual(
			frappe.db.get_value("Workflow", "Sales Order - Client Portal", "is_active"), 1
		)

	def test_trang_thai_va_docstatus(self):
		wf = frappe.get_doc("Workflow", bao_gia.WORKFLOW)
		theo_ten = {s.state: int(s.doc_status) for s in wf.states}
		self.assertEqual(theo_ten, {
			bao_gia.TT_CHO_MIYANO: 0, bao_gia.TT_CHO_KHACH: 0, bao_gia.TT_DA_DONG_Y: 1,
			bao_gia.TT_KHACH_TU_CHOI: 0, bao_gia.TT_MIYANO_TU_CHOI: 0, bao_gia.TT_HET_HAN: 0,
		})
		self.assertEqual(wf.states[0].state, bao_gia.TT_CHO_MIYANO)

	def test_buoc_phia_khach_chi_cho_system_manager(self):
		wf = frappe.get_doc("Workflow", bao_gia.WORKFLOW)
		for t in wf.transitions:
			if t.action in (
				bao_gia.HD_KHACH_DONG_Y, bao_gia.HD_KHACH_TU_CHOI,
				bao_gia.HD_KHACH_SUA_SL, bao_gia.HD_HET_HAN,
			):
				self.assertEqual(t.allowed, "System Manager", t.action)

	def test_bao_gia_moi_o_cho_miyano_bao_gia(self):
		bg = self._bao_gia_tho()
		self.assertEqual(bg.workflow_state, bao_gia.TT_CHO_MIYANO)
		self.assertEqual(bg.docstatus, 0)

	def test_bao_gia_noi_bo_nhan_vien_ghi_nhan_dong_y(self):
		bg = self._bao_gia_tho(nguon="Nội bộ")
		bg = apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		bg = apply_workflow(bg, bao_gia.HD_GHI_NHAN)
		self.assertEqual((bg.workflow_state, bg.docstatus), (bao_gia.TT_DA_DONG_Y, 1))

	def test_bao_gia_cong_khong_co_buoc_ghi_nhan(self):
		bg = self._bao_gia_tho()
		frappe.db.set_value("Quotation", bg.name, "workflow_state", bao_gia.TT_CHO_KHACH)
		bg.reload()
		hanh_dong = {t["action"] for t in get_transitions(bg)}
		self.assertNotIn(bao_gia.HD_GHI_NHAN, hanh_dong)

	def test_khong_dong_y_thay_khach_cong_tren_desk(self):
		"""Review Focus 6 — Administrator có vai System Manager nên workflow cho
		bấm "Khách đồng ý"; hook `before_submit` phải chặn."""
		bg = self._bao_gia_tho()
		frappe.db.set_value("Quotation", bg.name, "workflow_state", bao_gia.TT_CHO_KHACH)
		bg.reload()
		with self.assertRaises(frappe.ValidationError) as ctx:
			apply_workflow(bg, bao_gia.HD_KHACH_DONG_Y)
		self.assertIn("trên cổng", str(ctx.exception))
		self.assertEqual(frappe.db.get_value("Quotation", bg.name, "docstatus"), 0)

	def test_miyano_tu_choi_bat_buoc_ly_do(self):
		bg = self._bao_gia_tho()
		with self.assertRaises(frappe.ValidationError):
			apply_workflow(bg, bao_gia.HD_TU_CHOI)
		bg.reload()
		bg.custom_ly_do_tu_choi = "Miyano không phân phối mặt hàng này."
		bg.save()
		bg = apply_workflow(bg, bao_gia.HD_TU_CHOI)
		self.assertEqual(bg.workflow_state, bao_gia.TT_MIYANO_TU_CHOI)

	def test_thu_hoi_de_sua(self):
		bg = self._bao_gia_tho(nguon="Nội bộ")
		bg = apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		bg = apply_workflow(bg, bao_gia.HD_THU_HOI)
		self.assertEqual(bg.workflow_state, bao_gia.TT_CHO_MIYANO)

	def test_gan_trang_thai_cho_bao_gia_co_san(self):
		bg = self._bao_gia_tho(nguon="Nội bộ")
		frappe.db.set_value("Quotation", bg.name, "workflow_state", None)
		self.assertGreaterEqual(install_workflow.gan_trang_thai_bao_gia_cu(), 1)
		self.assertEqual(
			frappe.db.get_value("Quotation", bg.name, "workflow_state"), bao_gia.TT_CHO_MIYANO
		)
		self.assertEqual(install_workflow.gan_trang_thai_bao_gia_cu(), 0)
```

- [ ] **Step 3: Chạy, xác nhận hỏng**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_workflow`
Expected: FAIL — `ImportError: cannot import name 'bao_gia' from 'miyano_portal'`.

- [ ] **Step 4: Tạo `bao_gia.py` với hằng số và hai hook**

`miyano_portal/bao_gia.py`:

```python
"""Yêu cầu báo giá bằng Quotation (spec 2026-10-12).

Một yêu cầu báo giá của khách là một Quotation đi workflow `WORKFLOW`. Sales
Order chỉ sinh ra khi khách đồng ý (`dong_y`). Tài khoản cổng KHÔNG có DocPerm
trên Quotation: mọi hàm ghi ở đây chạy bước chuyển trạng thái dưới
`nang_quyen.quyen_he_thong()`, và NGƯỜI GỌI (endpoint trong `api/portal.py`)
phải kiểm quyền của khách trên đúng báo giá đó trước khi gọi vào đây.
"""

import frappe

WORKFLOW = "Quotation - Client Portal"
NGUON_CONG = "Client Portal"
LOAI_DON_THEO_BAO_GIA = "Theo báo giá"
HAU_TO_DON = ":don"

TT_CHO_MIYANO = "Chờ Miyano báo giá"
TT_CHO_KHACH = "Chờ khách đồng ý"
TT_DA_DONG_Y = "Khách đã đồng ý"
TT_KHACH_TU_CHOI = "Khách từ chối"
TT_MIYANO_TU_CHOI = "Miyano từ chối"
TT_HET_HAN = "Báo giá hết hạn"

HD_GUI_KHACH = "Gửi khách duyệt"
HD_TU_CHOI = "Từ chối"
HD_THU_HOI = "Thu hồi để sửa"
HD_KHACH_DONG_Y = "Khách đồng ý"
HD_KHACH_TU_CHOI = "Khách từ chối"
HD_KHACH_SUA_SL = "Khách sửa số lượng"
HD_HET_HAN = "Báo giá hết hạn"
HD_GHI_NHAN = "Ghi nhận khách đồng ý"

LY_DO_TOI_THIEU = 10


def _trang_thai_truoc(doc) -> str | None:
	truoc = doc.get_doc_before_save()
	return truoc.get("workflow_state") if truoc else None


def chan_dong_y_ngoai_cong(doc, method=None) -> None:
	"""Hook `before_submit` của Quotation.

	Báo giá của cổng chỉ được Submit bởi `dong_y()`, nơi sinh luôn Sales Order.
	Bước "Khách đồng ý" khai `System Manager`, nên một nhân viên có vai đó bấm
	được nó trên Desk; đi đường đó thì báo giá "đã đồng ý" mà không có đơn.
	"""
	if doc.get("custom_nguon_don") != NGUON_CONG:
		return
	if frappe.flags.get("bao_gia_dong_y_qua_cong") == doc.name:
		return
	frappe.throw(
		"Báo giá của cổng khách hàng chỉ được đồng ý bởi chính khách trên cổng.",
		frappe.ValidationError,
	)


def kiem_ly_do_tu_choi(doc, method=None) -> None:
	"""Hook `validate` — Miyano từ chối thì phải có lý do (spec §4.1)."""
	if doc.get("workflow_state") != TT_MIYANO_TU_CHOI:
		return
	if _trang_thai_truoc(doc) == TT_MIYANO_TU_CHOI:
		return
	if len((doc.get("custom_ly_do_tu_choi") or "").strip()) < LY_DO_TOI_THIEU:
		frappe.throw(
			f"Phải nhập lý do từ chối (tối thiểu {LY_DO_TOI_THIEU} ký tự) trước khi "
			"chuyển trạng thái.",
			frappe.ValidationError,
		)
```

- [ ] **Step 5: Thêm bộ cài workflow**

Thêm vào CUỐI `miyano_portal/setup/install_workflow.py` (4 dấu cách):

```python
def _bao_gia_states():
    from miyano_portal import bao_gia as bg

    # (trạng thái, docstatus, vai được sửa tại chỗ, kiểu hiển thị)
    return [
        (bg.TT_CHO_MIYANO, "0", "Sales User", ""),
        # Đang ở phía khách: muốn sửa giá phải "Thu hồi để sửa", không sửa tại chỗ.
        (bg.TT_CHO_KHACH, "0", "System Manager", "Warning"),
        (bg.TT_DA_DONG_Y, "1", "Sales Manager", "Success"),
        (bg.TT_KHACH_TU_CHOI, "0", "Sales Manager", "Danger"),
        (bg.TT_MIYANO_TU_CHOI, "0", "Sales Manager", "Danger"),
        (bg.TT_HET_HAN, "0", "System Manager", "Danger"),
    ]


def _bao_gia_transitions():
    from miyano_portal import bao_gia as bg

    # (từ, hành động, tới, vai, điều kiện)
    return [
        (bg.TT_CHO_MIYANO, bg.HD_GUI_KHACH, bg.TT_CHO_KHACH, "Sales User", None),
        (bg.TT_CHO_MIYANO, bg.HD_TU_CHOI, bg.TT_MIYANO_TU_CHOI, "Sales User", None),
        (bg.TT_CHO_KHACH, bg.HD_THU_HOI, bg.TT_CHO_MIYANO, "Sales User", None),
        (bg.TT_CHO_KHACH, bg.HD_KHACH_DONG_Y, bg.TT_DA_DONG_Y, "System Manager", None),
        (bg.TT_CHO_KHACH, bg.HD_KHACH_TU_CHOI, bg.TT_KHACH_TU_CHOI, "System Manager", None),
        (bg.TT_CHO_KHACH, bg.HD_KHACH_SUA_SL, bg.TT_CHO_MIYANO, "System Manager", None),
        (bg.TT_CHO_KHACH, bg.HD_HET_HAN, bg.TT_HET_HAN, "System Manager", None),
        # Báo giá nhân viên tự lập cho khách ngoài cổng: khách không có tài
        # khoản nên nhân viên ghi nhận. Điều kiện chặn bấm thay khách của cổng.
        (bg.TT_CHO_KHACH, bg.HD_GHI_NHAN, bg.TT_DA_DONG_Y, "Sales User",
         f'doc.custom_nguon_don != "{bg.NGUON_CONG}"'),
    ]


def install_quotation_workflow():
    """Spec 2026-10-12 §4.1. Frappe cho mỗi doctype MỘT workflow hoạt động và
    nó phủ mọi chứng từ, nên workflow này phủ cả Quotation nhân viên tự lập.
    Chạy lại được: đã có thì không đụng."""
    from miyano_portal import bao_gia as bg

    for ten, _ds, _vai, kieu in _bao_gia_states():
        if not frappe.db.exists("Workflow State", ten):
            frappe.get_doc({
                "doctype": "Workflow State", "workflow_state_name": ten, "style": kieu,
            }).insert(ignore_permissions=True)
    for _tu, hanh_dong, _toi, _vai, _dk in _bao_gia_transitions():
        if not frappe.db.exists("Workflow Action Master", hanh_dong):
            frappe.get_doc({
                "doctype": "Workflow Action Master", "workflow_action_name": hanh_dong,
            }).insert(ignore_permissions=True)
    if frappe.db.exists("Workflow", bg.WORKFLOW):
        return frappe.get_doc("Workflow", bg.WORKFLOW)
    wf = frappe.get_doc({
        "doctype": "Workflow",
        "workflow_name": bg.WORKFLOW,
        "document_type": "Quotation",
        "is_active": 1,
        "workflow_state_field": "workflow_state",
        "states": [
            {"state": ten, "doc_status": ds, "allow_edit": vai}
            for ten, ds, vai, _kieu in _bao_gia_states()
        ],
        "transitions": [
            {"state": tu, "action": hd, "next_state": toi, "allowed": vai,
             "condition": dk, "allow_self_approval": 1}
            for tu, hd, toi, vai, dk in _bao_gia_transitions()
        ],
    })
    wf.insert(ignore_permissions=True)
    return wf


def gan_trang_thai_bao_gia_cu() -> int:
    """Quotation có TRƯỚC workflow chưa mang `workflow_state`. Gán theo
    docstatus để chúng không kẹt: nháp → chờ Miyano báo giá, đã Submit → khách
    đã đồng ý. Chứng từ đã huỷ để nguyên. Trả số dòng vừa gán."""
    from miyano_portal import bao_gia as bg

    if not frappe.db.has_column("Quotation", "workflow_state"):
        return 0
    dem = 0
    for docstatus, trang_thai in ((0, bg.TT_CHO_MIYANO), (1, bg.TT_DA_DONG_Y)):
        ten = frappe.db.sql_list(
            "select name from `tabQuotation` where docstatus = %s "
            "and coalesce(workflow_state, '') = ''",
            docstatus,
        )
        for t in ten:
            frappe.db.set_value(
                "Quotation", t, "workflow_state", trang_thai, update_modified=False
            )
        dem += len(ten)
    return dem
```

- [ ] **Step 6: Gọi từ patch và đăng ký hook**

Trong `patches/v1_42/bao_gia_quotation.py`, thay hàm `execute`:

```python
def cai_workflow():
	from miyano_portal.setup.install_workflow import (
		gan_trang_thai_bao_gia_cu,
		install_quotation_workflow,
	)

	install_quotation_workflow()
	frappe.clear_cache(doctype="Quotation")
	gan_trang_thai_bao_gia_cu()


def execute():
	them_truong()
	cai_workflow()
```

Trong `hooks.py`, thêm vào dict `doc_events` (cùng cấp với `"Sales Order"`):

```python
	# Spec 2026-10-12 — yêu cầu báo giá bằng Quotation. Thêm hook ở đây thì
	# nhớ: workflow của Quotation phủ CẢ báo giá nhân viên tự lập, nên mỗi
	# hook phải tự nói rõ nó áp cho báo giá của cổng hay cho mọi báo giá.
	"Quotation": {
		"validate": [
			"miyano_portal.bao_gia.kiem_ly_do_tu_choi",
		],
		"before_submit": [
			"miyano_portal.bao_gia.chan_dong_y_ngoai_cong",
		],
	},
```

- [ ] **Step 7: Chạy, xác nhận qua**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_workflow`
Expected: `Ran 11 tests` … `OK`.

- [ ] **Step 8: Workflow đơn hàng không bị ảnh hưởng**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_workflow`
Expected: `OK`.

- [ ] **Step 9: Commit**

```bash
git add miyano_portal/bao_gia.py miyano_portal/setup/install_workflow.py miyano_portal/patches/v1_42/bao_gia_quotation.py miyano_portal/hooks.py miyano_portal/tests/nen_bao_gia.py miyano_portal/tests/test_bao_gia_workflow.py
git commit -m "feat(portal): workflow Quotation - Client Portal, chan dong y thay khach tren Desk"
```

---

### Task 3: Cách ly Quotation với tài khoản cổng

**Files:**
- Modify: `miyano_portal/permissions.py`
- Modify: `miyano_portal/rest_guard.py`
- Modify: `miyano_portal/portal_context.py` (hàm `dam_bao_xem_duoc`)
- Modify: `miyano_portal/hooks.py`
- Test: `miyano_portal/tests/test_bao_gia_cach_ly.py`

**Interfaces:**
- Consumes: `NenBaoGia` (Task 2).
- Produces: `permissions.bao_gia_query(user=None) -> str`, `permissions.bao_gia_has_permission(doc, ptype=None, user=None) -> bool`, `permissions.bao_gia_khong_qua_trang_web(doc, ptype=None, user=None, verbose=False) -> bool`, `rest_guard.chan_trang_bao_gia_erpnext()`; `dam_bao_xem_duoc("Quotation", ten)` kiểm khoa theo `custom_khoa_phong`.

- [ ] **Step 1: Viết test hỏng**

`miyano_portal/tests/test_bao_gia_cach_ly.py`:

```python
"""Cách ly Quotation (spec 2026-10-12 §8). Thiếu một chốt là lộ báo giá của
bệnh viện này sang bệnh viện khác."""

import frappe
import requests

from miyano_portal import permissions, search_guard
from miyano_portal.portal_context import dam_bao_xem_duoc
from miyano_portal.tests import test_rest_guard as rg
from miyano_portal.tests.nen_bao_gia import NenBaoGia


class TestBaoGiaCachLy(NenBaoGia):
	def setUp(self):
		super().setUp()
		self.bg_a = self._bao_gia_tho(khoa=self.khoa_huyethoc)
		self.ql_a = self._quan_ly("bgcl.ql.a@demo.miyano", self.kh_a)

	def _them_portal_user(self, user, khach):
		"""Dòng `Portal User` là thứ khiến chốt trang web của ERPNext cho qua."""
		kh = frappe.get_doc("Customer", khach)
		kh.append("portal_users", {"user": user})
		kh.save(ignore_permissions=True)

	def test_vai_customer_khong_co_docperm(self):
		quyen = frappe.get_all(
			"DocPerm", filters={"parent": "Quotation", "role": "Customer"}
		) + frappe.get_all(
			"Custom DocPerm", filters={"parent": "Quotation", "role": "Customer"}
		)
		self.assertEqual(quyen, [])

	def test_doc_chung_bi_tu_choi_ke_ca_dung_khach(self):
		frappe.set_user(self.ql_a)
		self.assertFalse(frappe.has_permission("Quotation", "read", doc=self.bg_a))
		with self.assertRaises(frappe.PermissionError):
			frappe.get_list("Quotation", fields=["name"])
		with self.assertRaises(frappe.PermissionError):
			search_guard.client_get("Quotation", self.bg_a.name)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc("Quotation", self.bg_a.name).check_permission("read")

	def test_make_sales_order_bi_tu_choi(self):
		from erpnext.selling.doctype.quotation.quotation import make_sales_order

		frappe.set_user(self.ql_a)
		with self.assertRaises(frappe.PermissionError):
			make_sales_order(self.bg_a.name)

	def test_run_doc_method_bi_tu_choi(self):
		from frappe.handler import run_doc_method

		frappe.set_user(self.ql_a)
		with self.assertRaises(frappe.PermissionError):
			run_doc_method("declare_enquiry_lost", dt="Quotation", dn=self.bg_a.name)

	def test_trang_web_erpnext_bi_chan(self):
		"""Review Focus 5."""
		self._them_portal_user(self.ql_a, self.kh_a)
		frappe.set_user(self.ql_a)
		self.assertFalse(frappe.has_website_permission(self.bg_a))

	def test_nhan_vien_noi_bo_van_qua_chot_trang_web(self):
		self.assertTrue(permissions.bao_gia_khong_qua_trang_web(self.bg_a, user="Administrator"))

	def test_lop_hai_khach_khac_khong_thay(self):
		self.assertFalse(permissions.bao_gia_has_permission(self.bg_a, user=self.user_b))
		self.assertTrue(permissions.bao_gia_has_permission(self.bg_a, user=self.ql_a))

	def test_lop_hai_khoa_khac_khong_thay(self):
		nv_duoc_a = self._dam_bao_thanh_vien(
			"bgcl.duoc.a@demo.miyano", self.kh_a, "Nhân viên khoa", self._khoa_khac_cua_a()
		)
		self.assertFalse(permissions.bao_gia_has_permission(self.bg_a, user=nv_duoc_a))
		self.assertTrue(permissions.bao_gia_has_permission(self.bg_a, user=self.user_a))

	def test_lop_hai_bao_gia_noi_bo_khong_hien(self):
		noi_bo = self._bao_gia_tho(nguon="Nội bộ")
		self.assertFalse(permissions.bao_gia_has_permission(noi_bo, user=self.ql_a))

	def test_dieu_kien_truy_van(self):
		dk = permissions.bao_gia_query(self.user_a)
		self.assertIn("`tabQuotation`.`party_name` in", dk)
		self.assertIn("'Client Portal'", dk)
		self.assertIn("`tabQuotation`.`custom_khoa_phong` =", dk)
		self.assertEqual(permissions.bao_gia_query("Administrator"), "")
		self.assertNotIn("custom_khoa_phong", permissions.bao_gia_query(self.ql_a))

	def test_dam_bao_xem_duoc_theo_khoa(self):
		dam_bao_xem_duoc("Quotation", self.bg_a.name, user=self.user_a)
		nv_duoc_a = self._dam_bao_thanh_vien(
			"bgcl.duoc.a@demo.miyano", self.kh_a, "Nhân viên khoa", self._khoa_khac_cua_a()
		)
		with self.assertRaises(frappe.PermissionError):
			dam_bao_xem_duoc("Quotation", self.bg_a.name, user=nv_duoc_a)

	def _khoa_khac_cua_a(self):
		ten = frappe.db.get_value(
			"Customer Department", {"customer": self.kh_a, "ma_khoa": "BGCL"}, "name"
		)
		if ten:
			return ten
		return frappe.get_doc({
			"doctype": "Customer Department", "customer": self.kh_a,
			"ten_khoa_phong": "Khoa thử cách ly báo giá", "ma_khoa": "BGCL", "active": 1,
		}).insert(ignore_permissions=True).name


class TestBaoGiaHTTP(NenBaoGia):
	"""Đăng nhập thật: `before_request` chỉ chạy trên request thật."""

	def setUp(self):
		super().setUp()
		self.session = rg._login_bvbm()
		if self.session is None:
			self.skipTest("bench không phản hồi trên loopback")

	def _get(self, duong_dan):
		return self.session.get(f"{rg.BASE_URL}{duong_dan}", timeout=30, allow_redirects=False)

	def test_danh_sach_bao_gia_erpnext_bi_chan(self):
		self.assertEqual(self._get("/quotations").status_code, 403)

	def test_chi_tiet_bao_gia_erpnext_bi_chan(self):
		self.assertEqual(self._get("/quotations/SAL-QTN-KHONG-CO").status_code, 403)

	def test_trang_cong_van_mo(self):
		self.assertEqual(self._get("/portal/yeu-cau").status_code, 200)
```

- [ ] **Step 2: Chạy, xác nhận hỏng**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_cach_ly`
Expected: FAIL — `AttributeError: module 'miyano_portal.permissions' has no attribute 'bao_gia_khong_qua_trang_web'`, `NotImplementedError` ở `test_dam_bao_xem_duoc_theo_khoa`, và `200 != 403` ở hai test HTTP (hoặc `skipped` nếu bench không chạy). Sáu test đầu về DocPerm có thể đã qua: chúng ghim hiện trạng, không được hỏng về sau.

- [ ] **Step 3: Viết ba hàm quyền**

Thêm vào `miyano_portal/permissions.py`, ngay sau `de_xuat_item_query`:

```python
def bao_gia_query(user=None) -> str:
    """Spec 2026-10-12 §8 — lớp phòng thủ THỨ HAI cho Quotation.

    Vai `Customer` không có DocPerm nào trên Quotation nên với tài khoản cổng
    hôm nay hàm này không bao giờ được gọi tới. Nó chỉ có nghĩa nếu về sau ai
    đó cấp quyền đọc: khi đó họ vẫn chỉ thấy báo giá CỦA CỔNG, của khách mình,
    của khoa mình. Quotation dùng `party_name`, không có cột `customer`.
    """
    user = user or frappe.session.user
    if not _is_restricted_user(user):
        return ""
    customers = get_allowed_customers(user)
    if not customers:
        return "1=0"
    joined = ", ".join(frappe.db.escape(c) for c in customers)
    dk = (
        "`tabQuotation`.`quotation_to` = 'Customer' and "
        f"`tabQuotation`.`party_name` in ({joined}) and "
        "`tabQuotation`.`custom_nguon_don` = 'Client Portal'"
    )
    try:
        pv = pham_vi_don(user)
    except frappe.PermissionError:
        return "1=0"
    khoa = pv.get("custom_khoa_phong")
    if khoa:
        dk += f" and `tabQuotation`.`custom_khoa_phong` = {frappe.db.escape(khoa)}"
    return dk


def bao_gia_has_permission(doc, ptype=None, user=None):
    user = user or frappe.session.user
    if not _is_restricted_user(user):
        return True
    if doc.get("quotation_to") != "Customer" or doc.get("custom_nguon_don") != "Client Portal":
        return False
    if doc.get("party_name") not in get_allowed_customers(user):
        return False
    try:
        pv = pham_vi_don(user)
    except frappe.PermissionError:
        return False
    khoa = pv.get("custom_khoa_phong")
    return not khoa or doc.get("custom_khoa_phong") == khoa


def bao_gia_khong_qua_trang_web(doc, ptype=None, user=None, verbose=False):
    """Hook `has_website_permission` của Quotation.

    ERPNext đăng ký sẵn một hook cho Quotation, cho qua mọi tài khoản có dòng
    `Portal User` trên Customer. Đường đó không qua DocPerm, không biết trục
    khoa, và là thứ `/quotations/<tên>`, `/printview`, `download_pdf` rơi về
    khi DocPerm từ chối. Frappe từ chối nếu BẤT KỲ hook nào trả giá trị sai,
    nên trả False ở đây là đủ đóng cả ba. Cổng đọc báo giá qua endpoint riêng.
    """
    return not _is_restricted_user(user or frappe.session.user)
```

- [ ] **Step 4: Chặn trang danh sách `/quotations`**

Trang danh sách dùng `get_transaction_list(ignore_permissions=True)` và không hỏi hook ở Step 3. Thêm vào cuối `miyano_portal/rest_guard.py`:

```python
def chan_trang_bao_gia_erpnext():
    """Hook `before_request` — spec 2026-10-12 §8.

    ERPNext đăng ký sẵn `/quotations` và `/quotations/<tên>` cho vai Customer.
    Trang danh sách đọc bằng `ignore_permissions=True`, lọc theo khách qua
    bảng `Portal User`, không biết trục khoa và hiện cả giá: chặn theo đường
    dẫn, vì không có hook quyền nào nằm trên đường đó.
    """
    if not getattr(frappe.local, "request", None):
        return
    duong_dan = (frappe.request.path or "").rstrip("/")
    if duong_dan != "/quotations" and not duong_dan.startswith("/quotations/"):
        return
    if not _la_khach_cong(frappe.session.user):
        return
    frappe.throw(_("Không có quyền truy cập dữ liệu này"), frappe.PermissionError)
```

Nếu `rest_guard.py` chưa có `_la_khach_cong` ở phạm vi module (mở file kiểm): dùng đúng phép kiểm mà `chan_rest_doctype_con` đang dùng cho "là Website User".

- [ ] **Step 5: Nhánh Quotation trong `dam_bao_xem_duoc`**

Trong `portal_context.py`, hàm `dam_bao_xem_duoc`, thêm một nhánh NGAY TRƯỚC nhánh `else: raise NotImplementedError`:

```python
    elif doctype == "Quotation":
        cua = frappe.db.get_value("Quotation", name, "custom_khoa_phong")
```

- [ ] **Step 6: Đăng ký hook**

Trong `hooks.py`:

- dict `permission_query_conditions`, thêm: `"Quotation": "miyano_portal.permissions.bao_gia_query",`
- dict `has_permission`, thêm: `"Quotation": "miyano_portal.permissions.bao_gia_has_permission",`
- list `before_request`, thêm: `"miyano_portal.rest_guard.chan_trang_bao_gia_erpnext",`
- thêm khối mới ngay sau dict `has_permission`:

```python
# Spec 2026-10-12 §8 — đóng đường trang web có sẵn của ERPNext cho Quotation
# (`/quotations/<tên>`, `/printview`, `download_pdf`). Xem docstring hàm.
has_website_permission = {
	"Quotation": "miyano_portal.permissions.bao_gia_khong_qua_trang_web",
}
```

KHÔNG thêm entry nào cho `Quotation Item`: bảng con đã bị `rest_guard`/`search_guard` chặn theo thuộc tính `istable`, và một entry `has_permission` trên bảng con không bao giờ được gọi (xem khối chú thích dài trong `hooks.py`).

- [ ] **Step 7: Nạp lại hook và chạy**

Run: `bench --site erptest.local clear-cache && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_cach_ly`
Expected: `Ran 14 tests` … `OK`. Ba test HTTP gọi tiến trình web ở `test_rest_guard.BASE_URL` (cổng 8002). Tiến trình đó phải được nạp lại để thấy hook mới; nếu test báo `skipped` hoặc vẫn `200`, khởi động lại tiến trình web rồi chạy lại. Chúng PHẢI chạy thật (không `skipped`) ít nhất một lần trước khi commit.

- [ ] **Step 8: Không làm hỏng các chốt đang có**

Run: `for m in test_rest_guard test_search_guard test_isolation test_cach_ly_khoa_phong; do bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.$m 2>&1 | grep -E "^Ran |^OK|^FAILED"; done`
Expected: bốn cặp `Ran …` / `OK`.

- [ ] **Step 9: Commit**

```bash
git add miyano_portal/permissions.py miyano_portal/rest_guard.py miyano_portal/portal_context.py miyano_portal/hooks.py miyano_portal/tests/test_bao_gia_cach_ly.py
git commit -m "feat(portal): cach ly Quotation - chan /quotations, printview va lop quyen thu hai"
```

---

### Task 4: Hàm nâng quyền dùng chung

**Files:**
- Create: `miyano_portal/nang_quyen.py`
- Modify: `miyano_portal/api/portal.py` (hàm `portal_order_accept`, `portal_order_sua_so_luong`)
- Test: `miyano_portal/tests/test_nang_quyen.py`

**Interfaces:**
- Produces: `nang_quyen.quyen_he_thong()` — context manager; trong khối `frappe.session.user == "Administrator"`, ra khỏi khối (kể cả khi ném lỗi) trả về người gọi; giá trị `yield` là tên người gọi.

- [ ] **Step 1: Viết test hỏng**

`miyano_portal/tests/test_nang_quyen.py`:

```python
"""`quyen_he_thong` — chạy một khối dưới quyền hệ thống (spec 2026-10-12 §4.1)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.nang_quyen import quyen_he_thong


class TestNangQuyen(FrappeTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_trong_khoi_la_administrator_ra_khoi_tra_lai(self):
		frappe.set_user("Guest")
		with quyen_he_thong() as nguoi_goi:
			self.assertEqual(nguoi_goi, "Guest")
			self.assertEqual(frappe.session.user, "Administrator")
			self.assertIn("System Manager", frappe.get_roles())
		self.assertEqual(frappe.session.user, "Guest")

	def test_nem_loi_van_tra_lai_phien(self):
		frappe.set_user("Guest")
		with self.assertRaises(ValueError):
			with quyen_he_thong():
				raise ValueError("hỏng giữa chừng")
		self.assertEqual(frappe.session.user, "Guest")

	def test_khong_dung_toi_sid_va_data(self):
		frappe.set_user("Guest")
		session = frappe.local.session
		session.sid, session.data = "sid-that", frappe._dict(csrf_token="abc")
		with quyen_he_thong():
			pass
		self.assertEqual(session.sid, "sid-that")
		self.assertEqual(session.data.csrf_token, "abc")
```

- [ ] **Step 2: Chạy, xác nhận hỏng**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_nang_quyen`
Expected: FAIL — `ModuleNotFoundError: No module named 'miyano_portal.nang_quyen'`.

- [ ] **Step 3: Viết module**

`miyano_portal/nang_quyen.py`. Khối chú thích dài về `frappe.set_user()` hiện nằm trong `portal_order_accept`: CHUYỂN nguyên văn nó vào docstring dưới đây (thay cho đoạn tóm tắt), để lý do chỉ còn sống ở một chỗ.

```python
"""Chạy một khối dưới quyền hệ thống mà không làm hỏng phiên của khách.

Các bước chuyển trạng thái phía khách (đồng ý, từ chối, sửa số lượng) khai
`allowed = System Manager` trong workflow: khách không bao giờ có vai nào
trên Desk. Endpoint cổng tự kiểm quyền của khách trên đúng chứng từ rồi mới
vào khối này.

CỐ Ý KHÔNG dùng `frappe.set_user()`: nó ghi đè `local.session.sid` bằng tên
người dùng và xoá `local.session.data` (mất csrf_token). `Session.update()`
cuối mỗi request thật lại ghi dữ liệu đã hỏng đó đè lên phiên THẬT của khách,
nên mọi POST sau đó trên tab đang mở lỗi CSRF tới khi tải lại trang.
`apply_workflow()` chỉ tra vai qua `frappe.get_roles()` → `session.user`, nên
đổi ĐÚNG MỘT thuộc tính `session.user` là đủ.
"""

from contextlib import contextmanager

import frappe


@contextmanager
def quyen_he_thong():
	session = frappe.local.session
	nguoi_goi = session.user
	frappe.local.user_perms = None  # tránh dùng nhầm cache quyền của người cũ
	session.user = "Administrator"
	try:
		yield nguoi_goi
	finally:
		# Trả phiên về NGAY, kể cả khi khối ném lỗi: thiếu `finally` thì phần
		# còn lại của request chạy dưới quyền Administrator.
		session.user = nguoi_goi
		frappe.local.user_perms = None
```

- [ ] **Step 4: Chạy, xác nhận qua**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_nang_quyen`
Expected: `Ran 3 tests` … `OK`.

- [ ] **Step 5: Hai chỗ đang chép tay dùng hàm chung**

Trong `api/portal.py`, thêm import `from miyano_portal.nang_quyen import quyen_he_thong`.

Trong `portal_order_accept`: thay khối từ `session = frappe.local.session` tới hết `finally:` (gồm cả khối chú thích dài phía trên nó, đã chuyển sang `nang_quyen.py`) bằng:

```python
    with quyen_he_thong():
        so = apply_workflow(so, hanh_dong)
        noi_dung = f"{hanh_dong} bởi {nguoi_bam}"
        if ghi_chu:
            noi_dung += f" — lý do: {ghi_chu}"
        so.add_comment("Comment", noi_dung)
```

Trong `portal_order_sua_so_luong`: thay khối `session = frappe.local.session` … `finally:` bằng `with quyen_he_thong():` bọc đúng phần thân của `try:` hiện có (giữ nguyên chú thích "Lưu thay đổi số lượng TRƯỚC…"). Biến `nguoi_bam = frappe.session.user` gán TRƯỚC khối `with` giữ nguyên.

- [ ] **Step 6: Luồng cũ không đổi hành vi**

Run: `for m in test_e2_workflow_va_accept test_e6_mua_le test_chot_bao_gia test_ghi_gia_da_dong_y; do bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.$m 2>&1 | grep -E "^Ran |^OK|^FAILED"; done`
Expected: bốn cặp `Ran …` / `OK`.

- [ ] **Step 7: Commit**

```bash
git add miyano_portal/nang_quyen.py miyano_portal/api/portal.py miyano_portal/tests/test_nang_quyen.py
git commit -m "feat(portal): tach co che nang quyen cua portal_order_accept thanh quyen_he_thong"
```

---

### Task 5: Dựng Quotation từ giỏ hàng

**Files:**
- Modify: `miyano_portal/bao_gia.py`
- Test: `miyano_portal/tests/test_tao_bao_gia.py`

**Interfaces:**
- Consumes: `dat_hang._xay_don(customer, aggregated, dat_ngoai, delivery_date, address, po, note, request_id)` (trả Sales Order CHƯA lưu, đã kiểm bội số / hàng ngừng bán / dòng gõ tay, đã chọn công ty, kho, Price List và chèn dòng giữ chỗ); `tach_phieu.chia_dong(customer, items) -> (co_gia, cho_bao_gia)`; `dat_hang._customer_addresses(customer)`; `portal_dat_hang.ngay_giao_mac_dinh()`.
- Produces:
  - `bao_gia.can_bao_gia(customer: str, items: list[dict], dat_ngoai: list) -> bool`
  - `bao_gia.tao_bao_gia(customer: str, *, items=None, dat_ngoai=None, delivery_date=None, note=None, address=None, request_id=None, khoa_phong=None) -> dict` trả `{"bao_gia": str, "da_ton_tai": bool, "total": float}`
  - `bao_gia.TRUONG_DAT_NGOAI` (tuple 13 tên trường của dòng gõ tay).

- [ ] **Step 1: Viết test hỏng**

`miyano_portal/tests/test_tao_bao_gia.py`:

```python
"""Dựng Quotation từ giỏ hàng (spec 2026-10-12 §3, §5)."""

import frappe

from miyano_portal import bao_gia
from miyano_portal.portal_mua_le import ITEM_GIU_CHO
from miyano_portal.tests.nen_bao_gia import NenBaoGia

DONG_GO_TAY = {"ten_hang": "Kim sinh thiết thử", "dvt": "Cái", "so_luong": 2, "hang_san_xuat": "ACME"}


class TestTaoBaoGia(NenBaoGia):
	def _rid(self):
		return frappe.generate_hash(length=12)

	def _tao(self, **them):
		tham_so = {
			"items": [
				{"item_code": self.item_ngoai, "qty": 10},
				{"item_code": self.item_boi_so, "qty": 20},
			],
			"request_id": self._rid(), "khoa_phong": self.khoa_huyethoc,
		}
		tham_so.update(them)
		kq = bao_gia.tao_bao_gia(self.kh_a, **tham_so)
		return kq, frappe.get_doc("Quotation", kq["bao_gia"])

	def test_can_bao_gia(self):
		co_gia = [{"item_code": self.item_ngoai, "qty": 10}]
		chua_gia = [{"item_code": self.item_boi_so, "qty": 10}]
		self.assertFalse(bao_gia.can_bao_gia(self.kh_a, co_gia, []))
		self.assertTrue(bao_gia.can_bao_gia(self.kh_a, co_gia + chua_gia, []))
		self.assertTrue(bao_gia.can_bao_gia(self.kh_a, co_gia, [DONG_GO_TAY]))

	def test_dau_chung_tu(self):
		kq, bg = self._tao()
		self.assertFalse(kq["da_ton_tai"])
		self.assertEqual((bg.quotation_to, bg.party_name), ("Customer", self.kh_a))
		self.assertEqual(bg.order_type, "Sales")
		self.assertEqual(bg.custom_nguon_don, "Client Portal")
		self.assertEqual(bg.custom_khoa_phong, self.khoa_huyethoc)
		self.assertEqual((bg.workflow_state, bg.docstatus), (bao_gia.TT_CHO_MIYANO, 0))
		self.assertEqual(bg.selling_price_list, self.price_list)
		self.assertEqual(bg.ignore_pricing_rule, 1)
		self.assertFalse(bg.valid_till)

	def test_dong_co_gia_nhan_gia_dong_chua_gia_bang_khong(self):
		_kq, bg = self._tao()
		theo_ma = {d.item_code: d for d in bg.items}
		self.assertEqual(theo_ma[self.item_ngoai].rate, 54000)
		self.assertEqual(theo_ma[self.item_ngoai].custom_nguon_gia, "Bảng giá")
		self.assertEqual(theo_ma[self.item_boi_so].rate, 0)
		self.assertEqual(theo_ma[self.item_boi_so].custom_nguon_gia, "Báo giá")
		self.assertEqual(theo_ma[self.item_boi_so].qty, 20)

	def test_khong_sinh_sales_order(self):
		rid = self._rid()
		self._tao(request_id=rid)
		self.assertFalse(frappe.db.exists("Sales Order", {"custom_request_id": rid}))

	def test_dong_go_tay_vao_bang_rieng(self):
		_kq, bg = self._tao(dat_ngoai=[DONG_GO_TAY])
		self.assertEqual(len(bg.custom_dat_ngoai), 1)
		dong = bg.custom_dat_ngoai[0]
		self.assertEqual((dong.ten_hang, dong.so_luong, dong.hang_san_xuat),
		                 ("Kim sinh thiết thử", 2, "ACME"))
		self.assertEqual(dong.da_xu_ly, 0)
		self.assertNotIn(ITEM_GIU_CHO, [d.item_code for d in bg.items])

	def test_chi_co_dong_go_tay_thi_co_dong_giu_cho(self):
		_kq, bg = self._tao(items=[], dat_ngoai=[DONG_GO_TAY])
		self.assertEqual([d.item_code for d in bg.items], [ITEM_GIU_CHO])
		self.assertEqual(bg.items[0].rate, 0)

	def test_gui_trung_khong_sinh_bao_gia_thu_hai(self):
		rid = self._rid()
		kq1, _ = self._tao(request_id=rid)
		kq2, _ = self._tao(request_id=rid)
		self.assertEqual(kq1["bao_gia"], kq2["bao_gia"])
		self.assertTrue(kq2["da_ton_tai"])
		self.assertEqual(frappe.db.count("Quotation", {"custom_request_id": rid}), 1)

	def test_ma_yeu_cau_cua_khach_khac(self):
		rid = self._rid()
		self._tao(request_id=rid)
		with self.assertRaises(frappe.PermissionError):
			bao_gia.tao_bao_gia(
				self.kh_b, items=[{"item_code": self.item_boi_so, "qty": 10}], request_id=rid
			)

	def test_sai_boi_so_bi_chan_nhu_dat_hang(self):
		with self.assertRaises(frappe.ValidationError):
			self._tao(items=[{"item_code": self.item_boi_so, "qty": 7}])

	def test_khoa_cua_khach_khac_bi_tu_choi(self):
		with self.assertRaises(frappe.PermissionError):
			self._tao(khoa_phong=self.khoa_duoc)

	def test_thieu_ma_yeu_cau(self):
		with self.assertRaises(frappe.ValidationError):
			self._tao(request_id=None)
```

- [ ] **Step 2: Chạy, xác nhận hỏng**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_tao_bao_gia`
Expected: FAIL — `AttributeError: module 'miyano_portal.bao_gia' has no attribute 'can_bao_gia'`.

- [ ] **Step 3: Viết `can_bao_gia` và `tao_bao_gia`**

Thêm vào `miyano_portal/bao_gia.py` (sau các hook của Task 2). Thêm `from frappe.utils import flt` vào đầu file.

```python
# Trường của một dòng khách gõ tay được chép từ giỏ sang báo giá. Cùng danh
# sách trắng mà `dat_hang._xay_don` dùng; không chép `da_chuyen`/`dong_hang`.
TRUONG_DAT_NGOAI = (
	"ten_hang", "dvt", "so_luong", "ghi_chu", "model_ma", "hang_san_xuat",
	"nuoc_san_xuat", "quy_cach", "ncc_hien_tai", "gia_hien_tai", "anh",
	"khong_co_anh", "mo_ta_nhan_dang",
)


def can_bao_gia(customer: str, items: list, dat_ngoai: list) -> bool:
	"""Giỏ này phải đi báo giá: có dòng gõ tay, hoặc có mã chưa có giá trong
	Price List của khách. Cùng phép chia mà `tach_phieu` dùng để tách phiếu."""
	from miyano_portal import tach_phieu

	if dat_ngoai:
		return True
	_co_gia, cho_bao_gia = tach_phieu.chia_dong(customer, items or [])
	return bool(cho_bao_gia)


def tao_bao_gia(
	customer: str, *, items=None, dat_ngoai=None, delivery_date=None, note=None,
	address=None, request_id=None, khoa_phong=None,
) -> dict:
	"""Dựng một Quotation ở "Chờ Miyano báo giá". Trả
	`{"bao_gia": str, "da_ton_tai": bool, "total": float}`.

	Mọi phép kiểm của giỏ hàng (bội số, hàng ngừng bán, dòng gõ tay thiếu tên,
	ngày giao, công ty, kho, dòng giữ chỗ) là của `dat_hang._xay_don`: hàm đó
	dựng một Sales Order CHƯA lưu, ở đây chỉ chép nó sang Quotation. Viết lại
	các phép kiểm ấy lần hai là để hai đường đặt hàng nói khác nhau về cùng
	một giỏ.
	"""
	from miyano_portal import dat_hang
	from miyano_portal.portal_dat_hang import ngay_giao_mac_dinh

	if not request_id:
		frappe.throw(
			"Thiếu mã yêu cầu đặt hàng. Tải lại trang rồi thử lại.",
			frappe.ValidationError,
		)
	da_co = frappe.db.get_value(
		"Quotation", {"custom_request_id": request_id},
		["name", "party_name", "grand_total"], as_dict=True,
	)
	if da_co:
		if da_co.party_name != customer:
			# Mã yêu cầu của khách khác: không xác nhận cả sự tồn tại của nó.
			raise frappe.PermissionError("Mã yêu cầu không hợp lệ.")
		return {
			"bao_gia": da_co.name, "da_ton_tai": True,
			"total": float(da_co.grand_total or 0),
		}

	if address:
		hop_le = {a["name"] for a in dat_hang._customer_addresses(customer)}
		if address not in hop_le:
			raise frappe.PermissionError("Địa chỉ giao hàng không thuộc đơn vị của bạn.")
	if isinstance(items, str):
		items = frappe.parse_json(items)
	if isinstance(dat_ngoai, str):
		dat_ngoai = frappe.parse_json(dat_ngoai)
	items, dat_ngoai = items or [], dat_ngoai or []
	if not items and not dat_ngoai:
		frappe.throw("Giỏ hàng trống.")

	gop: dict[str, float] = {}
	for dong in items:
		ma_tho = (dong.get("item_code") or "").strip()
		ma = frappe.db.get_value("Item", ma_tho, "name") if ma_tho else None
		if not ma:
			frappe.throw(
				f"Không tìm thấy mặt hàng '{ma_tho or '(trống)'}'.", frappe.ValidationError
			)
		gop[ma] = gop.get(ma, 0) + float(dong.get("qty") or 0)

	so = dat_hang._xay_don(
		customer, gop, dat_ngoai, delivery_date or ngay_giao_mac_dinh(),
		address, None, note, request_id,
	)

	bg = frappe.new_doc("Quotation")
	bg.quotation_to = "Customer"
	bg.party_name = customer
	bg.order_type = "Sales"
	bg.company = so.company
	bg.transaction_date = frappe.utils.today()
	bg.selling_price_list = so.selling_price_list
	# Một nguồn giá duy nhất: Price List của khách, không Pricing Rule.
	bg.ignore_pricing_rule = 1
	bg.custom_nguon_don = NGUON_CONG
	bg.custom_request_id = request_id
	for truong in ("customer_address", "shipping_address_name", "contact_person", "contact_email"):
		if so.get(truong):
			bg.set(truong, so.get(truong))
	for d in so.items:
		bg.append("items", {
			"item_code": d.item_code, "qty": d.qty, "rate": d.rate,
			# BẪY ERPNext: `price_list_rate` phải là số TƯỜNG MINH, kể cả 0. Để
			# None thì `set_missing_item_details` tự tra bảng giá rồi thay rate.
			"price_list_rate": d.rate,
			"uom": d.uom, "stock_uom": d.stock_uom, "conversion_factor": 1,
			"warehouse": d.warehouse, "custom_nguon_gia": d.get("custom_nguon_gia"),
		})
	for d in so.get("custom_dat_ngoai") or []:
		bg.append("custom_dat_ngoai", {t: d.get(t) for t in TRUONG_DAT_NGOAI})

	if khoa_phong:
		kp = frappe.db.get_value(
			"Customer Department", khoa_phong, ["customer", "active"], as_dict=True
		)
		if not kp or kp.customer != customer or not kp.active:
			raise frappe.PermissionError("Khoa phòng không thuộc đơn vị của bạn.")
		bg.custom_khoa_phong = khoa_phong

	return _chen_khong_trung(bg, request_id)


def _chen_khong_trung(bg, request_id) -> dict:
	"""Cùng luật với `dat_hang._insert_so_idempotent`: hai lần bấm đua nhau thì
	lần thua nhận lại báo giá của lần thắng."""
	bg.flags.ignore_permissions = True
	try:
		bg.insert(ignore_permissions=True)
	except frappe.UniqueValidationError:
		cu = frappe.db.get_value(
			"Quotation", {"custom_request_id": request_id},
			["name", "grand_total"], as_dict=True, for_update=True,
		)
		if not cu:
			raise
		return {"bao_gia": cu.name, "da_ton_tai": True, "total": float(cu.grand_total or 0)}
	return {"bao_gia": bg.name, "da_ton_tai": False, "total": float(bg.grand_total or 0)}
```

- [ ] **Step 4: Chạy, xác nhận qua**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_tao_bao_gia`
Expected: `Ran 11 tests` … `OK`. Nếu `test_dong_co_gia_nhan_gia…` báo giá dòng có giá bị đổi: ERPNext đã tra lại giá; kiểm `price_list_rate` được truyền tường minh như chú thích "BẪY".

- [ ] **Step 5: Commit**

```bash
git add miyano_portal/bao_gia.py miyano_portal/tests/test_tao_bao_gia.py
git commit -m "feat(portal): dung Quotation tu gio hang, chong tao trung theo ma yeu cau"
```

---

### Task 6: Khớp dòng gõ tay trên Quotation và chốt gửi khách

**Files:**
- Modify: `miyano_portal/portal_mua_le.py`
- Modify: `miyano_portal/bao_gia.py`
- Modify: `miyano_portal/hooks.py`
- Test: `miyano_portal/tests/test_bao_gia_gui_khach.py`

**Interfaces:**
- Consumes: `bao_gia.tao_bao_gia` (Task 5); hook có sẵn `portal_mua_le.chuyen_dong_dat_ngoai_thanh_hang`, `dong_bo_da_xu_ly_dat_ngoai`; `portal_mua_le.hieu_luc_bao_gia_ngay()`, `la_dong_giu_cho()`, `ITEM_GIU_CHO`.
- Produces: `portal_mua_le.ben_mua(doc) -> str | None` (khách của một Sales Order HOẶC Quotation); hook `bao_gia.chot_gui_khach(doc, method=None)` (`validate`): chặn gửi khách khi chưa đủ điều kiện, đặt `custom_ngay_gui_khach_duyet` và `valid_till` khi qua chốt, xoá hai trường đó khi báo giá quay về "Chờ Miyano báo giá".

- [ ] **Step 1: Viết test hỏng**

`miyano_portal/tests/test_bao_gia_gui_khach.py`:

```python
"""Khớp dòng gõ tay trên Quotation và chốt gửi khách (spec 2026-10-12 §3.3, §4.2)."""

import frappe
from frappe.model.workflow import apply_workflow
from frappe.utils import add_days, getdate, nowdate

from miyano_portal import bao_gia
from miyano_portal.portal_mua_le import ITEM_GIU_CHO, ben_mua
from miyano_portal.tests.nen_bao_gia import NenBaoGia

DONG_GO_TAY = {"ten_hang": "Kim sinh thiết thử", "dvt": "Cái", "so_luong": 2}


class TestBaoGiaGuiKhach(NenBaoGia):
	def _bao_gia(self, items=None, dat_ngoai=None):
		kq = bao_gia.tao_bao_gia(
			self.kh_a,
			items=[{"item_code": self.item_boi_so, "qty": 20}] if items is None else items,
			dat_ngoai=dat_ngoai or [], request_id=frappe.generate_hash(length=12),
			khoa_phong=self.khoa_huyethoc,
		)
		return frappe.get_doc("Quotation", kq["bao_gia"])

	def _dien_gia(self, bg, gia=7000):
		for d in bg.items:
			if not d.rate:
				d.rate = gia
				d.price_list_rate = gia
		bg.save()
		return bg

	def test_ben_mua(self):
		bg = self._bao_gia()
		self.assertEqual(ben_mua(bg), self.kh_a)
		so = frappe.new_doc("Sales Order")
		so.customer = self.kh_b
		self.assertEqual(ben_mua(so), self.kh_b)

	def test_khop_ma_co_gia_bang_gia_nhan_gia_bang(self):
		"""Review Focus 3 — Quotation không có cột `customer`."""
		bg = self._bao_gia(items=[], dat_ngoai=[DONG_GO_TAY])
		bg.custom_dat_ngoai[0].item_khop = self.item_ngoai
		bg.save()
		bg.reload()
		self.assertEqual([d.item_code for d in bg.items], [self.item_ngoai])
		self.assertEqual(bg.items[0].qty, 2)
		self.assertEqual(bg.items[0].rate, 54000)
		self.assertEqual(bg.items[0].custom_nguon_gia, "Bảng giá")
		self.assertEqual(bg.custom_dat_ngoai[0].da_xu_ly, 1)

	def test_khop_ma_chua_co_gia_thi_cho_bao_gia(self):
		bg = self._bao_gia(items=[], dat_ngoai=[DONG_GO_TAY])
		bg.custom_dat_ngoai[0].item_khop = self.item_boi_so
		bg.save()
		bg.reload()
		self.assertEqual(bg.items[0].rate, 0)
		self.assertEqual(bg.items[0].custom_nguon_gia, "Báo giá")
		self.assertNotIn(ITEM_GIU_CHO, [d.item_code for d in bg.items])

	def test_chan_khi_con_dong_go_tay_chua_khop(self):
		bg = self._dien_gia(self._bao_gia(dat_ngoai=[DONG_GO_TAY]))
		with self.assertRaises(frappe.ValidationError) as ctx:
			apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		self.assertIn("Kim sinh thiết thử", str(ctx.exception))

	def test_chan_khi_con_dong_giu_cho(self):
		bg = self._bao_gia(items=[], dat_ngoai=[DONG_GO_TAY])
		with self.assertRaises(frappe.ValidationError) as ctx:
			apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		self.assertIn(ITEM_GIU_CHO, str(ctx.exception))

	def test_chan_khi_con_dong_gia_khong(self):
		bg = self._bao_gia()
		with self.assertRaises(frappe.ValidationError) as ctx:
			apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		self.assertIn(self.item_boi_so, str(ctx.exception))
		self.assertEqual(
			frappe.db.get_value("Quotation", bg.name, "workflow_state"), bao_gia.TT_CHO_MIYANO
		)

	def test_qua_chot_thi_co_han_hieu_luc(self):
		frappe.db.set_single_value("Miyano Portal Settings", "hieu_luc_bao_gia_ngay", 5)
		bg = self._dien_gia(self._bao_gia())
		bg = apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		self.assertEqual(bg.workflow_state, bao_gia.TT_CHO_KHACH)
		self.assertEqual(getdate(bg.valid_till), getdate(add_days(nowdate(), 5)))
		self.assertTrue(bg.custom_ngay_gui_khach_duyet)

	def test_thu_hoi_xoa_han(self):
		bg = self._dien_gia(self._bao_gia())
		bg = apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		bg = apply_workflow(bg, bao_gia.HD_THU_HOI)
		self.assertFalse(bg.valid_till)
		self.assertFalse(bg.custom_ngay_gui_khach_duyet)
		self.assertEqual(bg.items[0].rate, 7000)

	def test_bao_gia_noi_bo_khong_bi_chot(self):
		bg = self._bao_gia_tho(nguon="Nội bộ")
		bg.items[0].rate = 0
		bg.items[0].price_list_rate = 0
		bg.save()
		bg = apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		self.assertEqual(bg.workflow_state, bao_gia.TT_CHO_KHACH)
		self.assertFalse(bg.valid_till)
```

- [ ] **Step 2: Chạy, xác nhận hỏng**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_gui_khach`
Expected: FAIL — `ImportError: cannot import name 'ben_mua' from 'miyano_portal.portal_mua_le'`.

- [ ] **Step 3: `ben_mua` và sửa chỗ đọc `doc.customer`**

Trong `portal_mua_le.py`, thêm ngay trước `chuyen_dong_dat_ngoai_thanh_hang`:

```python
def ben_mua(doc) -> str | None:
    """Khách hàng của một chứng từ bán. Sales Order giữ ở `customer`;
    Quotation giữ ở `party_name` (và chỉ là khách khi `quotation_to` là
    "Customer"). Các hook khớp dòng gõ tay chạy trên CẢ HAI doctype, nên phải
    hỏi qua hàm này: đọc thẳng `doc.customer` trên Quotation cho None, và mọi
    dòng khớp mã lặng lẽ mất giá bảng."""
    if doc.doctype == "Quotation":
        return doc.get("party_name") if doc.get("quotation_to") == "Customer" else None
    return doc.get("customer")
```

Trong `_gop_hoac_them_dong_hang`, đổi dòng `gia = bang_gia_khach.gia_bang_gia(doc.customer, item_code)` thành:

```python
    gia = bang_gia_khach.gia_bang_gia(ben_mua(doc), item_code)
```

Rồi rà cả file: `grep -n "doc\.customer\|so\.customer" miyano_portal/portal_mua_le.py`. Mọi chỗ còn lại nằm trong hàm được gọi từ `chuyen_dong_dat_ngoai_thanh_hang` hoặc `dong_bo_da_xu_ly_dat_ngoai` thì đổi sang `ben_mua(doc)`; chỗ chỉ chạy cho Sales Order (`cap_nhat_yeu_cau_goc`, `han_hieu_luc_bao_gia`…) giữ nguyên.

Khoá `"delivery_date"` mà `_gop_hoac_them_dong_hang` và `_dam_bao_con_dong_hang` đặt lên dòng hàng không có trên Quotation Item; Frappe bỏ qua khoá lạ khi lưu, không cần rẽ nhánh.

- [ ] **Step 4: Hook `chot_gui_khach`**

Thêm vào `bao_gia.py` (sau `kiem_ly_do_tu_choi`); bổ sung import `from frappe.utils import add_days, flt, now_datetime, nowdate`:

```python
def chot_gui_khach(doc, method=None) -> None:
	"""Hook `validate` — spec §4.2. Chỉ báo giá của cổng; báo giá nhân viên tự
	lập do họ tự chịu trách nhiệm về giá và hạn hiệu lực.

	Vào "Chờ khách đồng ý": chặn khi còn dòng gõ tay chưa khớp mã, còn dòng giữ
	chỗ, hoặc còn dòng chưa có đơn giá; qua chốt thì đóng mốc gửi và hạn hiệu
	lực. Quay về "Chờ Miyano báo giá" (thu hồi, khách sửa số lượng): xoá mốc và
	hạn, vì báo giá cũ không còn là thứ khách đang xem.
	"""
	from miyano_portal.portal_mua_le import (
		ITEM_GIU_CHO,
		hieu_luc_bao_gia_ngay,
		la_dong_giu_cho,
	)

	if doc.is_new() or doc.get("custom_nguon_don") != NGUON_CONG:
		return
	truoc, nay = _trang_thai_truoc(doc), doc.get("workflow_state")
	if truoc == nay:
		return
	if nay == TT_CHO_MIYANO and truoc == TT_CHO_KHACH:
		doc.valid_till = None
		doc.custom_ngay_gui_khach_duyet = None
		return
	if nay != TT_CHO_KHACH:
		return

	loi = []
	chua_khop = [
		d.get("ten_hang") or "?" for d in doc.get("custom_dat_ngoai") or []
		if not d.get("da_xu_ly")
	]
	if chua_khop:
		loi.append("còn hàng khách gõ tay chưa khớp mã: " + ", ".join(chua_khop))
	if any(la_dong_giu_cho(d.item_code) for d in doc.items):
		loi.append(f"còn dòng giữ chỗ kỹ thuật {ITEM_GIU_CHO}")
	thieu_gia = [
		d.item_code for d in doc.items
		if not la_dong_giu_cho(d.item_code) and flt(d.rate) <= 0
	]
	if thieu_gia:
		loi.append("còn mặt hàng chưa có đơn giá: " + ", ".join(thieu_gia))
	if loi:
		frappe.throw(
			"Chưa gửi khách được — " + "; ".join(loi) + ".", frappe.ValidationError
		)

	doc.custom_ngay_gui_khach_duyet = now_datetime()
	doc.valid_till = add_days(nowdate(), hieu_luc_bao_gia_ngay())
```

- [ ] **Step 5: Đăng ký hook**

Trong `hooks.py`, khối `"Quotation"` của `doc_events` thành:

```python
	"Quotation": {
		"before_validate": [
			# Cùng hook với Sales Order: khớp mã cho dòng khách gõ tay.
			"miyano_portal.portal_mua_le.chuyen_dong_dat_ngoai_thanh_hang",
		],
		"validate": [
			# Thứ tự có nghĩa: `dong_bo…` tính `da_xu_ly` mà `chot_gui_khach` đọc.
			"miyano_portal.portal_mua_le.dong_bo_da_xu_ly_dat_ngoai",
			"miyano_portal.bao_gia.kiem_ly_do_tu_choi",
			"miyano_portal.bao_gia.chot_gui_khach",
		],
		"before_submit": [
			"miyano_portal.bao_gia.chan_dong_y_ngoai_cong",
		],
	},
```

Và trong `doctype_js`, thêm (file `quotation.js` tới ở Task 10; ô ảnh của dòng gõ tay cần ngay):

```python
	"Quotation": ["public/js/dat_ngoai_anh.js"],
```

- [ ] **Step 6: Chạy, xác nhận qua**

Run: `bench --site erptest.local clear-cache && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_gui_khach`
Expected: `Ran 9 tests` … `OK`.

- [ ] **Step 7: Hook trên Sales Order không đổi hành vi**

Run: `for m in test_e6_mua_le test_don_tron_bao_gia test_nguon_gia_dong test_tao_bao_gia test_bao_gia_workflow; do bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.$m 2>&1 | grep -E "^Ran |^OK|^FAILED"; done`
Expected: năm cặp `Ran …` / `OK`.

- [ ] **Step 8: Commit**

```bash
git add miyano_portal/portal_mua_le.py miyano_portal/bao_gia.py miyano_portal/hooks.py miyano_portal/tests/test_bao_gia_gui_khach.py
git commit -m "feat(portal): khop dong go tay tren Quotation va chot gui khach duyet"
```

---

### Task 7: Khách đồng ý → sinh Sales Order

**Files:**
- Modify: `miyano_portal/bao_gia.py`
- Test: `miyano_portal/tests/test_bao_gia_dong_y.py`

**Interfaces:**
- Consumes: `quyen_he_thong()` (Task 4); `erpnext.selling.doctype.quotation.quotation._make_sales_order(source_name, target_doc=None, ignore_permissions=False, args=None)` (trả Sales Order CHƯA lưu, đòi Quotation đã Submit); `bang_gia_khach.ghi_gia_da_dong_y(so, nguoi_dong_y=None)`; `bang_gia_khach.NGUON_BAO_GIA`; `portal_mua_le.xoa_chenh_lech_gia(dong)`; `dat_hang._resolve_item_warehouse(item_code, company)`; `portal_thong_bao.bao_loi_ghi_gia(customer, sales_order)`; `nhat_ky.ghi(...)`.
- Produces:
  - `bao_gia.dong_y(ten: str) -> dict` trả `{"bao_gia": str, "sales_order": str, "da_ton_tai": bool, "trang_thai_moi": str}`. NGƯỜI GỌI đã kiểm quyền của khách.
  - `bao_gia.don_cua_bao_gia(bg) -> str | None` — tên Sales Order đã sinh từ báo giá (tra theo `custom_request_id = <rid>:don`).
  - `bao_gia.qua_han(bg, hom_nay=None) -> bool`.

- [ ] **Step 1: Viết test hỏng**

`miyano_portal/tests/test_bao_gia_dong_y.py`:

```python
"""Khách đồng ý báo giá → sinh Sales Order (spec 2026-10-12 §4.4)."""

from unittest.mock import patch

import frappe
from frappe.model.workflow import apply_workflow
from frappe.utils import add_days, getdate, nowdate

from miyano_portal import bang_gia_khach, bao_gia
from miyano_portal.portal_dat_hang import ngay_giao_mac_dinh
from miyano_portal.tests.nen_bao_gia import NenBaoGia


class TestBaoGiaDongY(NenBaoGia):
	def setUp(self):
		super().setUp()
		self.ql = self._quan_ly("bgdy.ql@demo.miyano", self.kh_a)

	def _phieu(self, ngay_can=None):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua", "customer": self.kh_a,
			"khoa_phong": self.khoa_huyethoc, "ly_do_yeu_cau": "Hết hàng trong kho khoa",
			"ten_don_hang": "Đợt thử báo giá", "ghi_chu": "Giao giờ hành chính",
			"ngay_can": ngay_can or add_days(nowdate(), 10),
			"trang_thai": "Đã duyệt",
			"items": [{"item_code": self.item_boi_so, "so_luong_de_xuat": 20, "so_luong_duyet": 20}],
		})
		doc.insert(ignore_permissions=True)
		return doc

	def _cho_khach(self, gia=7000, gia_dong_co_gia=None, ngay_can=None):
		"""Một báo giá của cổng đã được Miyano điền giá và gửi khách."""
		phieu = self._phieu(ngay_can)
		kq = bao_gia.tao_bao_gia(
			self.kh_a,
			items=[
				{"item_code": self.item_ngoai, "qty": 10},
				{"item_code": self.item_boi_so, "qty": 20},
			],
			request_id=frappe.generate_hash(length=12), khoa_phong=self.khoa_huyethoc,
		)
		bg = frappe.get_doc("Quotation", kq["bao_gia"])
		bg.custom_de_xuat = phieu.name
		bg.custom_ten_don_hang = phieu.ten_don_hang
		for d in bg.items:
			if d.item_code == self.item_boi_so:
				d.rate = d.price_list_rate = gia
			elif gia_dong_co_gia:
				d.rate = gia_dong_co_gia
		bg.save()
		frappe.db.set_value("Portal De Xuat Mua", phieu.name, "bao_gia", bg.name)
		return apply_workflow(bg, bao_gia.HD_GUI_KHACH), phieu

	def _dong_y(self, bg):
		frappe.set_user(self.ql)
		try:
			return bao_gia.dong_y(bg.name)
		finally:
			frappe.set_user("Administrator")

	def test_bao_gia_duoc_submit(self):
		bg, _ = self._cho_khach()
		kq = self._dong_y(bg)
		bg.reload()
		self.assertEqual((bg.workflow_state, bg.docstatus), (bao_gia.TT_DA_DONG_Y, 1))
		self.assertEqual(kq["trang_thai_moi"], bao_gia.TT_DA_DONG_Y)
		self.assertFalse(kq["da_ton_tai"])

	def test_sinh_dung_mot_don_theo_bao_gia(self):
		bg, phieu = self._cho_khach()
		kq = self._dong_y(bg)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(so.customer, self.kh_a)
		self.assertEqual(so.custom_loai_don, "Theo báo giá")
		self.assertEqual((so.workflow_state, so.docstatus), ("Chờ Miyano xác nhận", 0))
		self.assertEqual(so.custom_nguon_don, "Client Portal")
		self.assertEqual(so.custom_khoa_phong, self.khoa_huyethoc)
		self.assertEqual(so.custom_de_xuat, phieu.name)
		self.assertEqual(so.custom_ten_don_hang, "Đợt thử báo giá")
		self.assertEqual(so.custom_yeu_cau_khach, "Giao giờ hành chính")
		self.assertEqual(so.custom_request_id, bg.custom_request_id + ":don")
		self.assertEqual(len(so.items), 2)

	def test_dong_don_mang_gia_dau_nguon_va_gia_da_dong_y(self):
		bg, _ = self._cho_khach()
		so = frappe.get_doc("Sales Order", self._dong_y(bg)["sales_order"])
		theo_ma = {d.item_code: d for d in so.items}
		self.assertEqual(theo_ma[self.item_boi_so].rate, 7000)
		self.assertEqual(theo_ma[self.item_ngoai].rate, 54000)
		for d in so.items:
			self.assertEqual(d.custom_nguon_gia, "Báo giá")
			self.assertEqual(d.custom_gia_khach_dong_y, d.rate)
			self.assertTrue(d.warehouse)
			self.assertEqual(d.prevdoc_docname, bg.name)

	def test_gia_don_dung_gia_khach_dong_y_khi_khac_bang_gia(self):
		"""Review Focus 2 — Miyano gõ 60000 cho mặt hàng có giá bảng 54000."""
		bg, _ = self._cho_khach(gia_dong_co_gia=60000)
		so = frappe.get_doc("Sales Order", self._dong_y(bg)["sales_order"])
		dong = next(d for d in so.items if d.item_code == self.item_ngoai)
		self.assertEqual(dong.rate, 60000)
		self.assertEqual(dong.price_list_rate, 60000)
		self.assertEqual(dong.discount_amount or 0, 0)
		self.assertEqual(dong.custom_gia_khach_dong_y, 60000)

	def test_don_khong_mang_truong_rieng_cua_bao_gia(self):
		bg, _ = self._cho_khach()
		so = frappe.get_doc("Sales Order", self._dong_y(bg)["sales_order"])
		self.assertNotEqual(so.custom_request_id, bg.custom_request_id)
		self.assertFalse(so.get("custom_ngay_gui_khach_duyet"))
		self.assertFalse(so.get("custom_ly_do_tu_choi"))
		self.assertEqual(len(so.get("custom_dat_ngoai") or []), 0)

	def test_phieu_co_sales_order(self):
		bg, phieu = self._cho_khach()
		kq = self._dong_y(bg)
		self.assertEqual(
			frappe.db.get_value("Portal De Xuat Mua", phieu.name, ["sales_order", "bao_gia"]),
			(kq["sales_order"], bg.name),
		)

	def test_gia_duoc_ghi_vao_price_list(self):
		bg, _ = self._cho_khach(gia=7000)
		self._dong_y(bg)
		self.assertEqual(bang_gia_khach.gia_bang_gia(self.kh_a, self.item_boi_so), 7000)

	def test_goi_lai_khong_sinh_don_thu_hai(self):
		"""Review Focus 1."""
		bg, _ = self._cho_khach()
		kq1 = self._dong_y(bg)
		kq2 = self._dong_y(bg)
		self.assertEqual(kq1["sales_order"], kq2["sales_order"])
		self.assertTrue(kq2["da_ton_tai"])
		self.assertEqual(
			frappe.db.count("Sales Order", {"custom_request_id": bg.custom_request_id + ":don"}), 1
		)

	def test_qua_han_khong_dong_y_duoc(self):
		"""Review Focus 4 — job hết hạn chưa chạy."""
		bg, _ = self._cho_khach()
		frappe.db.set_value("Quotation", bg.name, {
			"valid_till": add_days(nowdate(), -1), "transaction_date": add_days(nowdate(), -9),
		})
		with self.assertRaises(frappe.ValidationError) as ctx:
			self._dong_y(bg)
		self.assertIn("hết hiệu lực", str(ctx.exception))
		self.assertEqual(frappe.db.get_value("Quotation", bg.name, "docstatus"), 0)

	def test_khong_o_cho_khach_thi_tu_choi(self):
		bg, _ = self._cho_khach()
		bg = apply_workflow(bg, bao_gia.HD_THU_HOI)
		with self.assertRaises(frappe.ValidationError):
			self._dong_y(bg)

	def test_loi_ghi_gia_khong_lam_hong_viec_dong_y(self):
		bg, _ = self._cho_khach()
		with patch.object(bang_gia_khach, "ghi_gia_da_dong_y", side_effect=RuntimeError("hỏng")):
			kq = self._dong_y(bg)
		self.assertTrue(frappe.db.exists("Sales Order", kq["sales_order"]))
		self.assertEqual(
			frappe.db.get_value("Quotation", bg.name, "workflow_state"), bao_gia.TT_DA_DONG_Y
		)
		self.assertTrue(frappe.db.exists(
			"Error Log", {"reference_doctype": "Sales Order", "reference_name": kq["sales_order"]}
		))

	def test_loi_sinh_don_thi_bao_gia_khong_o_trang_thai_da_dong_y(self):
		bg, phieu = self._cho_khach()
		with patch.object(bao_gia, "_sinh_don", side_effect=frappe.ValidationError("hỏng")):
			with self.assertRaises(frappe.ValidationError):
				self._dong_y(bg)
		self.assertEqual(
			frappe.db.get_value("Quotation", bg.name, ["workflow_state", "docstatus"]),
			(bao_gia.TT_CHO_KHACH, 0),
		)
		self.assertFalse(frappe.db.get_value("Portal De Xuat Mua", phieu.name, "sales_order"))

	def test_ngay_giao_lay_tu_phieu(self):
		ngay = add_days(nowdate(), 10)
		bg, _ = self._cho_khach(ngay_can=ngay)
		so = frappe.get_doc("Sales Order", self._dong_y(bg)["sales_order"])
		self.assertEqual(getdate(so.delivery_date), getdate(ngay))
		self.assertEqual(getdate(so.items[0].delivery_date), getdate(ngay))

	def test_ngay_can_da_qua_dung_ngay_mac_dinh(self):
		"""Review Focus 7."""
		bg, phieu = self._cho_khach()
		frappe.db.set_value("Portal De Xuat Mua", phieu.name, "ngay_can", add_days(nowdate(), -3))
		so = frappe.get_doc("Sales Order", self._dong_y(bg)["sales_order"])
		self.assertEqual(getdate(so.delivery_date), getdate(ngay_giao_mac_dinh()))

	def test_phien_tra_ve_nguoi_bam(self):
		bg, _ = self._cho_khach()
		frappe.set_user(self.ql)
		bao_gia.dong_y(bg.name)
		self.assertEqual(frappe.session.user, self.ql)
```

- [ ] **Step 2: Chạy, xác nhận hỏng**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_dong_y`
Expected: FAIL — `AttributeError: module 'miyano_portal.bao_gia' has no attribute 'dong_y'`.

- [ ] **Step 3: Viết `dong_y` và các hàm phụ**

Thêm vào `bao_gia.py`; bổ sung import `from frappe.utils import add_days, flt, formatdate, getdate, now_datetime, nowdate`:

```python
def qua_han(bg, hom_nay=None) -> bool:
	"""Báo giá đã quá `valid_till`. Không có hạn thì không bao giờ quá hạn."""
	if not bg.get("valid_till"):
		return False
	return getdate(bg.valid_till) < getdate(hom_nay or nowdate())


def don_cua_bao_gia(bg) -> str | None:
	"""Sales Order đã sinh từ báo giá này, tra theo mã yêu cầu `<rid>:don`."""
	rid = bg.get("custom_request_id")
	if not rid:
		return None
	return frappe.db.get_value("Sales Order", {"custom_request_id": rid + HAU_TO_DON}, "name")


def _dam_bao_cho_khach(bg) -> None:
	if bg.get("workflow_state") != TT_CHO_KHACH:
		frappe.throw(
			"Báo giá này không ở trạng thái chờ quý khách đồng ý.", frappe.ValidationError
		)


def _dam_bao_con_han(bg) -> None:
	if qua_han(bg):
		frappe.local.response["ly_do"] = "qua_han_hieu_luc"
		frappe.throw(
			f"Báo giá {bg.name} đã hết hiệu lực ngày "
			f"{formatdate(bg.valid_till, 'dd/mm/yyyy')}. Gửi yêu cầu báo giá mới nếu "
			"vẫn cần hàng.",
			frappe.ValidationError,
		)


def _ngay_giao(phieu) -> str:
	"""Ngày cần hàng của phiếu gốc nếu chưa trôi qua, không thì ngày mặc định.
	Báo giá có thể nằm chờ nhiều ngày; chặn khách đồng ý chỉ vì ngày họ chọn
	lúc gửi yêu cầu đã qua là chặn nhầm chỗ."""
	from miyano_portal.portal_dat_hang import ngay_giao_mac_dinh

	ngay = phieu.get("ngay_can") if phieu else None
	if ngay and getdate(ngay) >= getdate(nowdate()):
		return ngay
	return ngay_giao_mac_dinh()


def _sinh_don(bg):
	"""Sinh Sales Order "Theo báo giá" từ một Quotation ĐÃ Submit, đưa nó tới
	"Chờ Miyano xác nhận". Gọi trong khối `quyen_he_thong()`.

	Dùng bản nội bộ `_make_sales_order`: bản whitelist kiểm quyền người gọi,
	mà khách không có quyền nào trên Quotation.
	"""
	from erpnext.selling.doctype.quotation.quotation import _make_sales_order
	from frappe.model.naming import validate_name
	from frappe.model.workflow import apply_workflow

	from miyano_portal.bang_gia_khach import NGUON_BAO_GIA
	from miyano_portal.dat_hang import _resolve_item_warehouse
	from miyano_portal.portal_mua_le import xoa_chenh_lech_gia

	phieu = None
	if bg.get("custom_de_xuat"):
		phieu = frappe.db.get_value(
			"Portal De Xuat Mua", bg.custom_de_xuat,
			["ngay_can", "ghi_chu", "ma_de_xuat"], as_dict=True,
		)
	ngay = _ngay_giao(phieu)

	so = _make_sales_order(bg.name, ignore_permissions=True)
	so.delivery_date = ngay
	so.custom_nguon_don = NGUON_CONG
	so.custom_loai_don = LOAI_DON_THEO_BAO_GIA
	so.custom_request_id = bg.custom_request_id + HAU_TO_DON
	so.custom_hdnt = None
	so.ignore_pricing_rule = 1
	# Gán tường minh, không dựa vào việc mapper chép trường cùng tên.
	so.custom_khoa_phong = bg.get("custom_khoa_phong")
	so.custom_de_xuat = bg.get("custom_de_xuat")
	so.custom_ten_don_hang = bg.get("custom_ten_don_hang") or ""
	if phieu:
		so.custom_ma_tra_cuu = phieu.ma_de_xuat
		so.custom_yeu_cau_khach = phieu.ghi_chu
	for d in so.items:
		d.delivery_date = ngay
		d.warehouse = d.warehouse or _resolve_item_warehouse(d.item_code, so.company)
		# Đơn giá khách đã đồng ý là đơn giá của đơn. Đặt `price_list_rate`
		# bằng nó và xoá margin/chiết khấu, nếu không ERPNext tính lại `rate`
		# từ giá bảng khi lưu.
		d.price_list_rate = d.rate
		xoa_chenh_lech_gia(d)
		d.custom_nguon_gia = NGUON_BAO_GIA
		d.custom_gia_khach_dong_y = flt(d.rate)
	# Mã đơn = mã của khách trên phiếu, như đơn sinh từ `duyet_va_tao_don`.
	if phieu and phieu.ma_de_xuat and not frappe.db.exists("Sales Order", phieu.ma_de_xuat):
		so.name = validate_name("Sales Order", phieu.ma_de_xuat)
		so.flags.name_set = True
	so.flags.ignore_permissions = True
	so.insert(ignore_permissions=True)
	# Đơn mới sinh ở trạng thái đầu của workflow. Vòng báo giá đã xong trên
	# Quotation nên đưa thẳng sang "Chờ Miyano xác nhận" bằng bước chuyển thật.
	return apply_workflow(so, "Gửi duyệt")


def dong_y(ten: str) -> dict:
	"""Khách đồng ý báo giá (spec §4.4). NGƯỜI GỌI đã kiểm quyền của khách.

	Submit Quotation, sinh Sales Order và gắn đơn vào phiếu gốc là MỘT đơn vị:
	hỏng bước nào thì lùi cả ba. Ghi giá vào Price List đứng ngoài đơn vị đó —
	lỗi ở đấy chỉ được ghi Error Log và báo nhân viên.
	"""
	from frappe.model.workflow import apply_workflow

	from miyano_portal import bang_gia_khach, nhat_ky
	from miyano_portal.nang_quyen import quyen_he_thong
	from miyano_portal.portal_thong_bao import bao_loi_ghi_gia

	# Khoá dòng: hai người cùng bấm thì người sau chờ, rồi thấy "đã đồng ý".
	bg = frappe.get_doc("Quotation", ten, for_update=True)
	if bg.get("workflow_state") == TT_DA_DONG_Y:
		return {
			"bao_gia": bg.name, "sales_order": don_cua_bao_gia(bg),
			"da_ton_tai": True, "trang_thai_moi": TT_DA_DONG_Y,
		}
	_dam_bao_cho_khach(bg)
	_dam_bao_con_han(bg)

	nguoi_bam = frappe.session.user
	khach = bg.party_name
	frappe.db.savepoint("bao_gia_dong_y")
	try:
		with quyen_he_thong():
			frappe.flags.bao_gia_dong_y_qua_cong = bg.name
			try:
				bg = apply_workflow(bg, HD_KHACH_DONG_Y)
			finally:
				frappe.flags.bao_gia_dong_y_qua_cong = None
			bg.add_comment("Comment", f"{HD_KHACH_DONG_Y} bởi {nguoi_bam}")
			so = _sinh_don(bg)
		if bg.get("custom_de_xuat"):
			frappe.db.set_value(
				"Portal De Xuat Mua", bg.custom_de_xuat, "sales_order", so.name
			)
	except Exception:
		frappe.db.rollback(save_point="bao_gia_dong_y")
		raise

	try:
		frappe.db.savepoint("bao_gia_ghi_gia")
		so.reload()
		bang_gia_khach.ghi_gia_da_dong_y(so, nguoi_dong_y=nguoi_bam)
	except Exception:
		loi = frappe.get_traceback(with_context=True)
		try:
			frappe.db.rollback(save_point="bao_gia_ghi_gia")
		except Exception:
			loi += "\n[rollback savepoint cũng lỗi]\n" + frappe.get_traceback()
		frappe.log_error(
			title=f"Không ghi được giá đã đồng ý của đơn {so.name} vào Price List",
			message=loi, reference_doctype="Sales Order", reference_name=so.name,
		)
		bao_loi_ghi_gia(khach, so.name)

	nhat_ky.ghi(
		nhat_ky.SK_KHACH_DONG_Y, customer=khach,
		khoa_phong=bg.get("custom_khoa_phong"), de_xuat=bg.get("custom_de_xuat"),
		sales_order=so.name, vai=nhat_ky.VAI_QUAN_LY,
	)
	return {
		"bao_gia": bg.name, "sales_order": so.name,
		"da_ton_tai": False, "trang_thai_moi": bg.get("workflow_state"),
	}
```

- [ ] **Step 4: Chạy, xác nhận qua**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_dong_y`
Expected: `Ran 15 tests` … `OK`.

Hai chỗ dễ hỏng, xử lý theo nguyên nhân chứ không nới test:
- `test_sinh_dung_mot_don…` báo trạng thái "Chờ xác nhận": một hook `validate` của Sales Order đã chặn "Gửi duyệt". Đọc lỗi; chốt 1 của `chot_bao_gia.kiem_chuyen_trang_thai` chỉ áp cho `"Mua lẻ"` nên không phải nó.
- `test_gia_don_dung_gia…` báo `rate` là 54000: ERPNext đã tính lại từ giá bảng. Kiểm `price_list_rate` và `xoa_chenh_lech_gia` được gọi TRƯỚC `insert`.

- [ ] **Step 5: Commit**

```bash
git add miyano_portal/bao_gia.py miyano_portal/tests/test_bao_gia_dong_y.py
git commit -m "feat(portal): khach dong y bao gia - Submit Quotation, sinh don Theo bao gia, ghi gia"
```

---

### Task 8: Khách từ chối và sửa số lượng

**Files:**
- Modify: `miyano_portal/bao_gia.py`
- Test: `miyano_portal/tests/test_bao_gia_tu_choi_sua.py`

**Interfaces:**
- Consumes: `_dam_bao_cho_khach`, `_dam_bao_con_han`, `quyen_he_thong`; `portal_dat_hang.kiem_boi_so(item_code, qty) -> dict | None` (dict lỗi có khoá `"thong_diep"`); `portal_thong_bao._nguoi_nhan_kiem_hang(customer) -> list[str]`.
- Produces:
  - `bao_gia.tu_choi(ten: str, ly_do: str | None = None) -> dict` trả `{"trang_thai_moi": str}`.
  - `bao_gia.sua_so_luong(ten: str, dong: list[dict]) -> dict`; `dong` là `[{"name": <tên dòng Quotation Item>, "qty": float}]`; trả `{"trang_thai_moi": str, "thay_doi": list[str], "ap_dung": {item_code: qty}}`.
  - `bao_gia.bao_nhan_vien(bg, tieu_de: str, noi_dung: str) -> int` — Notification Log cho nhân viên phụ trách khách, trỏ tới Quotation; không bao giờ ném lỗi.

- [ ] **Step 1: Viết test hỏng**

`miyano_portal/tests/test_bao_gia_tu_choi_sua.py`:

```python
"""Khách từ chối và sửa số lượng báo giá (spec 2026-10-12 §4.3)."""

import frappe
from frappe.model.workflow import apply_workflow

from miyano_portal import bang_gia_khach, bao_gia
from miyano_portal.tests.nen_bao_gia import NenBaoGia


class TestBaoGiaTuChoiSua(NenBaoGia):
	def setUp(self):
		super().setUp()
		self.ql = self._quan_ly("bgtc.ql@demo.miyano", self.kh_a)
		frappe.db.set_value("Customer", self.kh_a, "account_manager", "Administrator")

	def _cho_khach(self):
		kq = bao_gia.tao_bao_gia(
			self.kh_a,
			items=[
				{"item_code": self.item_ngoai, "qty": 10},
				{"item_code": self.item_boi_so, "qty": 20},
			],
			request_id=frappe.generate_hash(length=12), khoa_phong=self.khoa_huyethoc,
		)
		bg = frappe.get_doc("Quotation", kq["bao_gia"])
		for d in bg.items:
			if d.item_code == self.item_boi_so:
				d.rate = d.price_list_rate = 7000
		bg.save()
		return apply_workflow(bg, bao_gia.HD_GUI_KHACH)

	def _dong(self, bg, ma):
		return next(d for d in bg.items if d.item_code == ma)

	def _voi_khach(self, ham, *tham_so):
		frappe.set_user(self.ql)
		try:
			return ham(*tham_so)
		finally:
			frappe.set_user("Administrator")

	def test_tu_choi_khong_sinh_don_khong_ghi_gia(self):
		bg = self._cho_khach()
		kq = self._voi_khach(bao_gia.tu_choi, bg.name, "Giá cao hơn nhà cung cấp hiện tại")
		bg.reload()
		self.assertEqual(kq["trang_thai_moi"], bao_gia.TT_KHACH_TU_CHOI)
		self.assertEqual((bg.workflow_state, bg.docstatus), (bao_gia.TT_KHACH_TU_CHOI, 0))
		self.assertEqual(bg.custom_ly_do_tu_choi, "Giá cao hơn nhà cung cấp hiện tại")
		self.assertIsNone(bao_gia.don_cua_bao_gia(bg))
		self.assertIsNone(bang_gia_khach.gia_bang_gia(self.kh_a, self.item_boi_so))

	def test_tu_choi_khong_can_ly_do(self):
		bg = self._cho_khach()
		self._voi_khach(bao_gia.tu_choi, bg.name, None)
		self.assertEqual(
			frappe.db.get_value("Quotation", bg.name, "workflow_state"), bao_gia.TT_KHACH_TU_CHOI
		)

	def test_tu_choi_sai_trang_thai(self):
		bg = apply_workflow(self._cho_khach(), bao_gia.HD_THU_HOI)
		with self.assertRaises(frappe.ValidationError):
			self._voi_khach(bao_gia.tu_choi, bg.name, None)

	def test_sua_so_luong_ve_cho_miyano_giu_gia_xoa_han(self):
		bg = self._cho_khach()
		dong = self._dong(bg, self.item_boi_so)
		kq = self._voi_khach(bao_gia.sua_so_luong, bg.name, [{"name": dong.name, "qty": 40}])
		bg.reload()
		self.assertEqual(kq["trang_thai_moi"], bao_gia.TT_CHO_MIYANO)
		self.assertEqual(kq["ap_dung"], {self.item_boi_so: 40.0})
		self.assertEqual(self._dong(bg, self.item_boi_so).qty, 40)
		self.assertEqual(self._dong(bg, self.item_boi_so).rate, 7000)
		self.assertEqual(self._dong(bg, self.item_ngoai).qty, 10)
		self.assertFalse(bg.valid_till)
		self.assertFalse(bg.custom_ngay_gui_khach_duyet)

	def test_khong_them_dong(self):
		bg = self._cho_khach()
		with self.assertRaises(frappe.ValidationError):
			self._voi_khach(bao_gia.sua_so_luong, bg.name, [{"name": "khong-co-dong-nay", "qty": 5}])

	def test_khong_dat_ve_khong(self):
		bg = self._cho_khach()
		dong = self._dong(bg, self.item_ngoai)
		with self.assertRaises(frappe.ValidationError) as ctx:
			self._voi_khach(bao_gia.sua_so_luong, bg.name, [{"name": dong.name, "qty": 0}])
		self.assertIn("từ chối", str(ctx.exception))

	def test_sai_boi_so_bi_chan(self):
		bg = self._cho_khach()
		dong = self._dong(bg, self.item_boi_so)
		with self.assertRaises(frappe.ValidationError):
			self._voi_khach(bao_gia.sua_so_luong, bg.name, [{"name": dong.name, "qty": 25}])

	def test_khong_doi_gi_thi_bao_loi(self):
		bg = self._cho_khach()
		dong = self._dong(bg, self.item_ngoai)
		with self.assertRaises(frappe.ValidationError):
			self._voi_khach(bao_gia.sua_so_luong, bg.name, [{"name": dong.name, "qty": 10}])
		self.assertEqual(
			frappe.db.get_value("Quotation", bg.name, "workflow_state"), bao_gia.TT_CHO_KHACH
		)

	def test_nhan_vien_duoc_bao(self):
		bg = self._cho_khach()
		dong = self._dong(bg, self.item_boi_so)
		self._voi_khach(bao_gia.sua_so_luong, bg.name, [{"name": dong.name, "qty": 40}])
		log = frappe.get_all(
			"Notification Log",
			filters={"document_type": "Quotation", "document_name": bg.name,
			         "for_user": "Administrator"},
			fields=["subject", "email_content"],
		)
		self.assertEqual(len(log), 1)
		self.assertIn(self.item_boi_so, log[0].email_content)

	def test_gui_lai_sau_khi_sua_thi_dong_y_duoc(self):
		bg = self._cho_khach()
		dong = self._dong(bg, self.item_boi_so)
		self._voi_khach(bao_gia.sua_so_luong, bg.name, [{"name": dong.name, "qty": 40}])
		bg.reload()
		bg = apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		kq = self._voi_khach(bao_gia.dong_y, bg.name)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(next(d.qty for d in so.items if d.item_code == self.item_boi_so), 40)
```

- [ ] **Step 2: Chạy, xác nhận hỏng**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_tu_choi_sua`
Expected: FAIL — `AttributeError: module 'miyano_portal.bao_gia' has no attribute 'tu_choi'`.

- [ ] **Step 3: Viết ba hàm**

Thêm vào `bao_gia.py`:

```python
def bao_nhan_vien(bg, tieu_de: str, noi_dung: str) -> int:
	"""Notification Log cho nhân viên phụ trách khách (đường lui: Sales
	Manager), trỏ tới Quotation. Không bao giờ ném lỗi: chạy sau một việc ĐÃ
	thành công. Trả số thông báo vừa tạo."""
	try:
		from miyano_portal.portal_thong_bao import _nguoi_nhan_kiem_hang

		dem = 0
		for nguoi in _nguoi_nhan_kiem_hang(bg.party_name):
			frappe.get_doc({
				"doctype": "Notification Log", "subject": f"{tieu_de}: {bg.name}",
				"for_user": nguoi, "type": "Alert",
				"document_type": "Quotation", "document_name": bg.name,
				"email_content": noi_dung,
			}).insert(ignore_permissions=True)
			dem += 1
		return dem
	except Exception:
		frappe.log_error(
			title=f"bao_gia: không báo được nhân viên về {bg.name}",
			message=frappe.get_traceback(),
		)
		return 0


def tu_choi(ten: str, ly_do: str | None = None) -> dict:
	"""Khách từ chối báo giá. Lý do tuỳ chọn. NGƯỜI GỌI đã kiểm quyền."""
	from frappe.model.workflow import apply_workflow

	from miyano_portal import nhat_ky
	from miyano_portal.nang_quyen import quyen_he_thong

	bg = frappe.get_doc("Quotation", ten, for_update=True)
	_dam_bao_cho_khach(bg)
	ly_do = (ly_do or "").strip()
	nguoi_bam = frappe.session.user
	if ly_do:
		# Ghi thẳng: `apply_workflow` nạp lại chứng từ từ CSDL trước khi lưu.
		frappe.db.set_value(
			"Quotation", bg.name, "custom_ly_do_tu_choi", ly_do, update_modified=False
		)
	with quyen_he_thong():
		bg = apply_workflow(bg, HD_KHACH_TU_CHOI)
		bg.add_comment(
			"Comment",
			f"{HD_KHACH_TU_CHOI} bởi {nguoi_bam}" + (f" — lý do: {ly_do}" if ly_do else ""),
		)
	bao_nhan_vien(
		bg, "Portal - Khách từ chối báo giá",
		f"Khách hàng <b>{bg.party_name}</b> đã từ chối báo giá <b>{bg.name}</b>."
		+ (f"<br>Lý do: {frappe.utils.escape_html(ly_do)}" if ly_do else ""),
	)
	nhat_ky.ghi(
		nhat_ky.SK_KHACH_KHONG_DONG_Y, customer=bg.party_name,
		khoa_phong=bg.get("custom_khoa_phong"), de_xuat=bg.get("custom_de_xuat"),
		vai=nhat_ky.VAI_QUAN_LY, ghi_chu=ly_do or None,
	)
	return {"trang_thai_moi": bg.get("workflow_state")}


def sua_so_luong(ten: str, dong: list) -> dict:
	"""Khách sửa số lượng các dòng ĐÃ CÓ trên báo giá (spec §4.3). Không thêm,
	không xoá, không đặt về 0. Đơn giá giữ nguyên làm gợi ý; báo giá quay về
	"Chờ Miyano báo giá" và hook `chot_gui_khach` xoá hạn hiệu lực.
	NGƯỜI GỌI đã kiểm quyền."""
	from frappe.model.workflow import apply_workflow

	from miyano_portal import nhat_ky
	from miyano_portal.nang_quyen import quyen_he_thong
	from miyano_portal.portal_dat_hang import kiem_boi_so
	from miyano_portal.portal_mua_le import la_dong_giu_cho

	bg = frappe.get_doc("Quotation", ten, for_update=True)
	_dam_bao_cho_khach(bg)
	_dam_bao_con_han(bg)
	if isinstance(dong, str):
		dong = frappe.parse_json(dong)

	theo_ten = {d.name: d for d in bg.items if not la_dong_giu_cho(d.item_code)}
	thay_doi: list[str] = []
	ap_dung: dict[str, float] = {}
	for yc in dong or []:
		hang = theo_ten.get(yc.get("name"))
		if not hang:
			frappe.throw(
				"Không tìm thấy dòng hàng trong báo giá — không thêm được dòng mới "
				"qua sửa số lượng.",
				frappe.ValidationError,
			)
		try:
			moi = float(yc.get("qty"))
		except (TypeError, ValueError):
			frappe.throw(f"{hang.item_code}: số lượng không hợp lệ.", frappe.ValidationError)
		if moi <= 0:
			frappe.throw(
				f"{hang.item_code}: số lượng phải lớn hơn 0. Không cần mặt hàng "
				"nào nữa thì từ chối báo giá.",
				frappe.ValidationError,
			)
		loi = kiem_boi_so(hang.item_code, moi)
		if loi:
			frappe.throw(loi["thong_diep"], frappe.ValidationError)
		if flt(hang.qty) == moi:
			continue
		thay_doi.append(f"{hang.item_code}: {flt(hang.qty):g} → {moi:g}")
		hang.qty = moi
		ap_dung[hang.item_code] = moi
	if not thay_doi:
		frappe.throw("Không có thay đổi số lượng nào để gửi.", frappe.ValidationError)

	nguoi_bam = frappe.session.user
	with quyen_he_thong():
		# Lưu TRƯỚC: `apply_workflow` nạp lại chứng từ từ CSDL ngay đầu hàm.
		bg.save()
		bg = apply_workflow(bg, HD_KHACH_SUA_SL)
		bg.add_comment(
			"Comment",
			f"[Portal] {HD_KHACH_SUA_SL} bởi {nguoi_bam}:<br>" + "<br>".join(thay_doi),
		)
	bao_nhan_vien(
		bg, "Portal - Khách sửa số lượng báo giá",
		f"Khách hàng <b>{bg.party_name}</b> vừa sửa số lượng trên báo giá "
		f"<b>{bg.name}</b>; báo giá đã về \"{TT_CHO_MIYANO}\" để xem lại giá:<br>"
		+ "<br>".join(thay_doi),
	)
	nhat_ky.ghi(
		nhat_ky.SK_KHACH_GUI_LAI_BAO_GIA, customer=bg.party_name,
		khoa_phong=bg.get("custom_khoa_phong"), de_xuat=bg.get("custom_de_xuat"),
		vai=nhat_ky.VAI_QUAN_LY, ghi_chu=f"{len(thay_doi)} dòng thay đổi",
	)
	return {
		"trang_thai_moi": bg.get("workflow_state"), "thay_doi": thay_doi, "ap_dung": ap_dung,
	}
```

- [ ] **Step 4: Chạy, xác nhận qua**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_tu_choi_sua`
Expected: `Ran 10 tests` … `OK`.

- [ ] **Step 5: Commit**

```bash
git add miyano_portal/bao_gia.py miyano_portal/tests/test_bao_gia_tu_choi_sua.py
git commit -m "feat(portal): khach tu choi va sua so luong tren bao gia, giu don gia lam goi y"
```

---

### Task 9: Hết hạn, quá hạn xử lý, nhật ký

**Files:**
- Modify: `miyano_portal/bao_gia.py`
- Modify: `miyano_portal/portal_bao_gia.py` (hàm `quet_bao_gia_het_han`)
- Modify: `miyano_portal/portal_sla.py` (hàm `quet_don_treo`)
- Modify: `miyano_portal/nhat_ky.py`, `miyano_portal/hooks.py`
- Test: `miyano_portal/tests/test_bao_gia_het_han.py`

**Interfaces:**
- Consumes: `bao_gia.bao_nhan_vien`, `qua_han`; `portal_sla.gio_lam_viec_troi_qua(tu_luc, moc=None)`, `_sla_gio()`, `_nguoi_nhan()`; `portal_bao_gia._email_sales_phu_trach(customer)`.
- Produces:
  - `bao_gia.quet_het_han(moc=None) -> int` — chuyển "Báo giá hết hạn" mọi Quotation ở "Chờ khách đồng ý" có `valid_till` trước `moc`.
  - `bao_gia.ghi_nhat_ky_chuyen_trang_thai(doc, method=None)` — hook `on_update`.
  - `nhat_ky.SK_BAO_GIA_TAO = "bao_gia_tao"`, `nhat_ky.SK_BAO_GIA_HET_HAN = "bao_gia_het_han"`.
  - `portal_sla.TIEU_DE_BAO_GIA = "Portal - Báo giá treo SLA"`.

- [ ] **Step 1: Viết test hỏng**

`miyano_portal/tests/test_bao_gia_het_han.py`:

```python
"""Hết hạn, quá hạn xử lý và nhật ký của báo giá (spec 2026-10-12 §4.6, §7)."""

import frappe
from frappe.model.workflow import apply_workflow
from frappe.utils import add_days, add_to_date, now_datetime, nowdate

from miyano_portal import bao_gia, nhat_ky, portal_bao_gia, portal_sla
from miyano_portal.tests.nen_bao_gia import NenBaoGia


class TestBaoGiaHetHan(NenBaoGia):
	def _cho_khach(self, **them):
		bg = self._bao_gia_tho(khoa=self.khoa_huyethoc, **them)
		return apply_workflow(bg, bao_gia.HD_GUI_KHACH)

	def _lui_han(self, bg, so_ngay):
		frappe.db.set_value("Quotation", bg.name, {
			"valid_till": add_days(nowdate(), -so_ngay),
			"transaction_date": add_days(nowdate(), -so_ngay - 7),
		}, update_modified=False)

	def test_bao_gia_qua_han_bi_dong(self):
		bg = self._cho_khach()
		self._lui_han(bg, 1)
		self.assertEqual(bao_gia.quet_het_han(), 1)
		self.assertEqual(
			frappe.db.get_value("Quotation", bg.name, ["workflow_state", "docstatus"]),
			(bao_gia.TT_HET_HAN, 0),
		)

	def test_bao_gia_con_han_khong_bi_dung(self):
		bg = self._cho_khach()
		self.assertEqual(bao_gia.quet_het_han(), 0)
		self.assertEqual(
			frappe.db.get_value("Quotation", bg.name, "workflow_state"), bao_gia.TT_CHO_KHACH
		)

	def test_het_han_dung_ngay_cuoi_van_con_hieu_luc(self):
		bg = self._cho_khach()
		self._lui_han(bg, 0)
		self.assertEqual(bao_gia.quet_het_han(), 0)

	def test_job_hang_ngay_quet_ca_quotation(self):
		bg = self._cho_khach()
		self._lui_han(bg, 2)
		self.assertGreaterEqual(portal_bao_gia.quet_bao_gia_het_han(), 1)
		self.assertEqual(
			frappe.db.get_value("Quotation", bg.name, "workflow_state"), bao_gia.TT_HET_HAN
		)

	def test_het_han_ghi_nhat_ky(self):
		phieu = frappe.get_doc({
			"doctype": "Portal De Xuat Mua", "customer": self.kh_a,
			"khoa_phong": self.khoa_huyethoc, "ly_do_yeu_cau": "Hết hàng trong kho khoa",
			"items": [{"item_code": self.item_boi_so, "so_luong_de_xuat": 10}],
		}).insert(ignore_permissions=True)
		bg = self._cho_khach(custom_de_xuat=phieu.name)
		self._lui_han(bg, 1)
		bao_gia.quet_het_han()
		su_kien = frappe.get_all(
			nhat_ky.DOCTYPE, filters={"de_xuat": phieu.name}, pluck="su_kien"
		)
		self.assertIn(nhat_ky.SK_MIYANO_BAO_GIA, su_kien)
		self.assertIn(nhat_ky.SK_BAO_GIA_HET_HAN, su_kien)

	def test_sla_nhac_bao_gia_treo(self):
		bg = self._bao_gia_tho(khoa=self.khoa_huyethoc)
		frappe.db.set_value(
			"Quotation", bg.name, "modified", add_to_date(now_datetime(), days=-14),
			update_modified=False,
		)
		portal_sla.quet_don_treo()
		self.assertTrue(frappe.db.exists(
			"Notification Log", {"subject": f"{portal_sla.TIEU_DE_BAO_GIA}: {bg.name}"}
		))

	def test_sla_khong_nhac_bao_gia_noi_bo_va_bao_gia_dang_o_phia_khach(self):
		noi_bo = self._bao_gia_tho(nguon="Nội bộ")
		o_khach = self._cho_khach()
		for bg in (noi_bo, o_khach):
			frappe.db.set_value(
				"Quotation", bg.name, "modified", add_to_date(now_datetime(), days=-14),
				update_modified=False,
			)
		portal_sla.quet_don_treo()
		for bg in (noi_bo, o_khach):
			self.assertFalse(frappe.db.exists(
				"Notification Log", {"subject": f"{portal_sla.TIEU_DE_BAO_GIA}: {bg.name}"}
			))
```

- [ ] **Step 2: Chạy, xác nhận hỏng**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_het_han`
Expected: FAIL — `AttributeError: module 'miyano_portal.bao_gia' has no attribute 'quet_het_han'`.

- [ ] **Step 3: Hằng số nhật ký**

Trong `nhat_ky.py`, cạnh các hằng `SK_*`:

```python
# Spec 2026-10-12 — yêu cầu báo giá bằng Quotation.
SK_BAO_GIA_TAO = "bao_gia_tao"
SK_BAO_GIA_HET_HAN = "bao_gia_het_han"
```

`su_kien` là trường Data (nhãn sống ở frontend, Task 14 thêm nhãn), không cần sửa doctype.

- [ ] **Step 4: Job hết hạn và hook nhật ký**

Thêm vào `bao_gia.py`:

```python
# Trạng thái MỚI của báo giá → sự kiện nhật ký. Bước phía khách (đồng ý, từ
# chối, sửa số lượng) tự ghi ở hàm của nó, kèm người bấm.
_SU_KIEN_THEO_TRANG_THAI = {
	TT_CHO_KHACH: "SK_MIYANO_BAO_GIA",
	TT_MIYANO_TU_CHOI: "SK_MIYANO_TU_CHOI",
	TT_HET_HAN: "SK_BAO_GIA_HET_HAN",
}


def ghi_nhat_ky_chuyen_trang_thai(doc, method=None) -> None:
	"""Hook `on_update` — một dòng nhật ký khi báo giá của cổng CHUYỂN tới một
	trạng thái trong bảng trên. Chỉ khi trạng thái thật sự đổi."""
	from miyano_portal import nhat_ky

	if doc.get("custom_nguon_don") != NGUON_CONG:
		return
	truoc, nay = _trang_thai_truoc(doc), doc.get("workflow_state")
	if not truoc or truoc == nay or nay not in _SU_KIEN_THEO_TRANG_THAI:
		return
	nhat_ky.ghi(
		getattr(nhat_ky, _SU_KIEN_THEO_TRANG_THAI[nay]), customer=doc.party_name,
		khoa_phong=doc.get("custom_khoa_phong"), de_xuat=doc.get("custom_de_xuat"),
		vai=nhat_ky.VAI_HE_THONG if nay == TT_HET_HAN else nhat_ky.VAI_MIYANO,
		ghi_chu=(doc.get("custom_ly_do_tu_choi") or None) if nay == TT_MIYANO_TU_CHOI else None,
	)


def _gui_email_het_han(bg, han) -> None:
	"""Email hai phía. Lỗi gửi mail không được chặn việc đóng báo giá."""
	from miyano_portal.portal_bao_gia import _email_sales_phu_trach

	han_str = formatdate(han, "dd/mm/yyyy")
	noi_dung = (
		f"<p>Báo giá <b>{bg.name}</b> (khách hàng {bg.party_name}) đã hết hiệu lực "
		f"ngày <b>{han_str}</b> mà chưa được đồng ý trên cổng khách hàng.</p>"
		"<p>Nếu vẫn cần hàng, vui lòng gửi yêu cầu báo giá mới.</p>"
	)
	for nguoi_nhan in {bg.get("contact_email"), _email_sales_phu_trach(bg.party_name)}:
		if not nguoi_nhan:
			continue
		try:
			frappe.sendmail(
				recipients=[nguoi_nhan], subject=f"Báo giá {bg.name} đã hết hiệu lực",
				message=noi_dung, reference_doctype="Quotation", reference_name=bg.name,
				now=False,
			)
		except Exception:
			frappe.log_error(
				title="bao_gia: gửi email hết hạn thất bại", message=frappe.get_traceback()
			)


def quet_het_han(moc=None) -> int:
	"""Spec §4.6 — đóng mọi báo giá ở "Chờ khách đồng ý" có `valid_till` trước
	`moc` (mặc định hôm nay). Gọi từ job hằng ngày `portal_bao_gia.
	quet_bao_gia_het_han`, chạy dưới Administrator nên không cần nâng quyền.
	Job gốc `set_expired_status` của ERPNext chỉ đụng Quotation đã Submit."""
	from frappe.model.workflow import apply_workflow

	hom_nay = getdate(moc) if moc else getdate(nowdate())
	dem = 0
	for ten in frappe.get_all(
		"Quotation",
		filters={"workflow_state": TT_CHO_KHACH, "docstatus": 0, "valid_till": ("<", hom_nay)},
		pluck="name",
	):
		bg = frappe.get_doc("Quotation", ten)
		han = bg.valid_till
		bg = apply_workflow(bg, HD_HET_HAN)
		bg.add_comment(
			"Comment",
			f"[Hệ thống] Báo giá hết hiệu lực ngày {formatdate(han, 'dd/mm/yyyy')} — tự đóng.",
		)
		if bg.get("custom_nguon_don") == NGUON_CONG:
			_gui_email_het_han(bg, han)
		dem += 1
	return dem
```

Trong `hooks.py`, khối `"Quotation"` của `doc_events`, thêm:

```python
		"on_update": [
			"miyano_portal.bao_gia.ghi_nhat_ky_chuyen_trang_thai",
		],
```

- [ ] **Step 5: Nối vào hai job đang có**

Trong `portal_bao_gia.py`, hàm `quet_bao_gia_het_han`, thay dòng `return dem` cuối hàm bằng:

```python
    # Spec 2026-10-12 §4.6 — yêu cầu báo giá mới là Quotation. Vòng lặp trên
    # vẫn phải chạy cho tới khi hết đơn "Mua lẻ" dở của luồng cũ.
    from miyano_portal import bao_gia

    return dem + bao_gia.quet_het_han(hom_nay)
```

Trong `portal_sla.py`: thêm hằng `TIEU_DE_BAO_GIA = "Portal - Báo giá treo SLA"` cạnh `TIEU_DE`, và trong `quet_don_treo`, thay dòng `return dem` cuối hàm bằng:

```python
    # Spec 2026-10-12 §7 — báo giá của cổng nằm ở "Chờ Miyano báo giá" quá
    # ngưỡng. Cùng ngưỡng `sla_xu_ly_don_gio`, tính từ lần sửa cuối, mỗi báo
    # giá tối đa một lần mỗi ngày.
    from miyano_portal import bao_gia

    for bg in frappe.get_all(
        "Quotation",
        filters={
            "workflow_state": bao_gia.TT_CHO_MIYANO, "docstatus": 0,
            "custom_nguon_don": bao_gia.NGUON_CONG,
        },
        fields=["name", "party_name", "modified"],
    ):
        if gio_lam_viec_troi_qua(bg.modified, moc=moc) < sla:
            continue
        tieu_de = f"{TIEU_DE_BAO_GIA}: {bg.name}"
        if frappe.db.exists(
            "Notification Log",
            {"subject": tieu_de, "creation": (">=", hom_nay + " 00:00:00")},
        ):
            continue
        for u in nguoi_nhan:
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": tieu_de,
                "for_user": u,
                "type": "Alert",
                "document_type": "Quotation",
                "document_name": bg.name,
                "email_content": (
                    f"Yêu cầu báo giá {bg.name} của {bg.party_name} đã chờ Miyano "
                    f"báo giá quá {sla:g} giờ làm việc."
                ),
            }).insert(ignore_permissions=True)
        dem += 1
    return dem
```

- [ ] **Step 6: Chạy, xác nhận qua**

Run: `bench --site erptest.local clear-cache && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_het_han`
Expected: `Ran 7 tests` … `OK`.

- [ ] **Step 7: Job cũ không đổi hành vi**

Run: `for m in test_e6_mua_le test_e2_sla_va_trang_thai; do bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.$m 2>&1 | grep -E "^Ran |^OK|^FAILED"; done`
Expected: hai cặp `Ran …` / `OK`.

- [ ] **Step 8: Commit**

```bash
git add miyano_portal/bao_gia.py miyano_portal/portal_bao_gia.py miyano_portal/portal_sla.py miyano_portal/nhat_ky.py miyano_portal/hooks.py miyano_portal/tests/test_bao_gia_het_han.py
git commit -m "feat(portal): bao gia het han, nhac SLA va nhat ky cho Quotation"
```

---

### Task 10: Mẫu in, thông báo, hàng việc và form Quotation

**Files:**
- Modify: `miyano_portal/setup/install_print_formats.py`, `install_notifications.py`, `install_kho_workspace.py`
- Modify: `miyano_portal/patches/v1_42/bao_gia_quotation.py`
- Create: `miyano_portal/public/js/hang_moi_khach_khai.js`, `miyano_portal/public/js/quotation.js`
- Modify: `miyano_portal/public/js/sales_order.js`, `miyano_portal/hooks.py`
- Test: `miyano_portal/tests/test_bao_gia_cai_dat.py`

**Interfaces:**
- Produces: Print Format `"Miyano - Yêu cầu báo giá"` (doctype Quotation; hằng `install_print_formats.NAME_YCBG`, `HTML_YCBG`); Notification `"Portal - Yêu cầu báo giá sẵn sàng"` (hằng `install_notifications.TEN_TB_BAO_GIA`); lối tắt workspace `"Yêu cầu báo giá"`; hàm JS toàn cục `miyano_portal.hien_thong_tin_hang_moi(frm)`.

- [ ] **Step 1: Viết test hỏng**

`miyano_portal/tests/test_bao_gia_cai_dat.py`:

```python
"""Mẫu in, thông báo và hàng việc của Quotation (spec 2026-10-12 §7, §9)."""

from pathlib import Path

import frappe
from frappe.model.workflow import apply_workflow

from miyano_portal import bao_gia
from miyano_portal.patches.v1_42 import bao_gia_quotation
from miyano_portal.setup import install_kho_workspace, install_notifications, install_print_formats
from miyano_portal.tests.nen_bao_gia import NenBaoGia

JS = Path(frappe.get_app_path("miyano_portal", "public", "js"))


class TestBaoGiaCaiDat(NenBaoGia):
	def test_mau_in_cho_quotation(self):
		pf = frappe.get_doc("Print Format", install_print_formats.NAME_YCBG)
		self.assertEqual(pf.doc_type, "Quotation")
		self.assertEqual(install_print_formats.NAME_YCBG, "Miyano - Yêu cầu báo giá")

	def test_mau_in_dung_duoc(self):
		bg = apply_workflow(self._bao_gia_tho(), bao_gia.HD_GUI_KHACH)
		html = frappe.get_print(
			"Quotation", bg.name, print_format=install_print_formats.NAME_YCBG
		)
		self.assertIn(self.item_ngoai, html)
		self.assertIn("54.000", html)
		self.assertIn(frappe.utils.formatdate(bg.valid_till, "dd/mm/yyyy"), html)

	def test_thong_bao_cho_quotation(self):
		tb = frappe.get_doc("Notification", install_notifications.TEN_TB_BAO_GIA)
		self.assertEqual((tb.document_type, tb.event, tb.value_changed),
		                 ("Quotation", "Value Change", "workflow_state"))
		self.assertEqual(tb.print_format, install_print_formats.NAME_YCBG)
		self.assertEqual(tb.attach_print, 1)
		bg = self._bao_gia_tho()
		ngu_canh = {"doc": bg, "frappe": frappe}
		self.assertFalse(frappe.safe_eval(tb.condition, None, ngu_canh))
		bg.workflow_state = bao_gia.TT_CHO_KHACH
		self.assertTrue(frappe.safe_eval(tb.condition, None, ngu_canh))
		bg.custom_nguon_don = "Nội bộ"
		self.assertFalse(frappe.safe_eval(tb.condition, None, ngu_canh))

	def test_loi_tat_hang_viec(self):
		ws = frappe.get_doc("Workspace", install_kho_workspace.TITLE)
		sc = [s for s in ws.shortcuts if s.label == "Yêu cầu báo giá"]
		self.assertEqual(len(sc), 1)
		self.assertEqual(sc[0].link_to, "Quotation")
		loc = frappe.parse_json(sc[0].stats_filter)
		self.assertEqual(loc, {
			"custom_nguon_don": "Client Portal", "workflow_state": bao_gia.TT_CHO_MIYANO,
		})

	def test_patch_chay_hai_lan(self):
		bao_gia_quotation.execute()
		bao_gia_quotation.execute()
		self.assertEqual(frappe.db.count("Workflow", {"document_type": "Quotation"}), 1)
		self.assertEqual(
			frappe.db.count("Print Format", {"name": install_print_formats.NAME_YCBG}), 1
		)
		self.assertEqual(
			frappe.db.count("Notification", {"name": install_notifications.TEN_TB_BAO_GIA}), 1
		)

	def test_khoi_hang_moi_dung_chung_hai_form(self):
		chung = (JS / "hang_moi_khach_khai.js").read_text()
		self.assertIn("miyano_portal.hien_thong_tin_hang_moi = function", chung)
		self.assertIn("Hàng chưa có mã — thông tin khách khai", chung)
		for ten in ("sales_order.js", "quotation.js"):
			nguon = (JS / ten).read_text()
			self.assertIn("miyano_portal.hien_thong_tin_hang_moi(frm)", nguon, ten)
			self.assertNotIn("function hien_thong_tin_hang_moi", nguon, ten)
		js = frappe.get_hooks("doctype_js")
		for dt in ("Sales Order", "Quotation"):
			self.assertIn("public/js/hang_moi_khach_khai.js", js[dt], dt)
			self.assertIn("public/js/dat_ngoai_anh.js", js[dt], dt)
```

- [ ] **Step 2: Chạy, xác nhận hỏng**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_cai_dat`
Expected: FAIL — `AttributeError: module 'miyano_portal.setup.install_print_formats' has no attribute 'NAME_YCBG'`.

- [ ] **Step 3: Mẫu in**

Trong `install_print_formats.py`, thêm ngay TRƯỚC `FORMATS = [`:

```python
# Spec 2026-10-12 §7 — báo giá gửi khách là một Quotation. Tên KHÁC mẫu
# "Miyano - Báo giá" của Sales Order (giữ cho đơn "Mua lẻ" cũ): tên Print
# Format là duy nhất trên cả site.
NAME_YCBG = "Miyano - Yêu cầu báo giá"
HTML_YCBG = """
<div class="print-heading"><h2>BÁO GIÁ / QUOTATION</h2></div>
<p><b>Khách hàng / Customer:</b> {{ doc.customer_name }}</p>
<p><b>Số báo giá / Quotation No:</b> {{ doc.name }}
   &nbsp; <b>Ngày báo giá / Quotation Date:</b>
   {{ frappe.utils.formatdate(doc.custom_ngay_gui_khach_duyet or doc.transaction_date, "dd/mm/yyyy") }}</p>
{% if doc.custom_ten_don_hang %}<p><b>Tên đơn hàng / Reference:</b> {{ doc.custom_ten_don_hang }}</p>{% endif %}
{% if doc.valid_till %}
<p><b>Hiệu lực đến / Valid Until:</b> {{ frappe.utils.formatdate(doc.valid_till, "dd/mm/yyyy") }}</p>
{% endif %}
<table class="table table-bordered">
  <thead><tr>
    <th>Mã / Code</th><th>Tên hàng / Item</th><th>ĐVT / UoM</th><th>SL / Qty</th>
    <th>Đơn giá / Rate</th><th>Thành tiền / Amount</th>
  </tr></thead>
  <tbody>
  {% for i in doc.items %}
    {%- if not la_dong_giu_cho(i.item_code) %}
    <tr>
      <td>{{ i.item_code }}</td><td>{{ i.item_name }}</td><td>{{ i.uom }}</td>
      <td class="text-right">{{ i.qty }}</td>
      <td class="text-right">{{ "{:,.0f}".format(i.rate).replace(",", ".") }} ₫</td>
      <td class="text-right">{{ "{:,.0f}".format(i.amount).replace(",", ".") }} ₫</td>
    </tr>
    {%- endif %}
  {% endfor %}
  </tbody>
</table>
{% set da_khop = doc.get("custom_dat_ngoai") | selectattr("da_xu_ly", "equalto", 1) | list %}
{% if da_khop %}
<h4>Hàng quý khách mô tả đã được khớp mã / Matched items</h4>
<table class="table table-bordered">
  <thead><tr>
    <th>Tên hàng khách yêu cầu / Requested</th>
    <th>Mã đã khớp / Matched code</th>
    <th>SL / Qty</th>
  </tr></thead>
  <tbody>
  {% for d in da_khop %}
    <tr><td>{{ d.ten_hang }}</td><td>{{ d.item_khop }}</td>
        <td class="text-right">{{ d.so_luong }}</td></tr>
  {% endfor %}
  </tbody>
</table>
{% endif %}
<p class="text-right"><b>Tổng cộng / Total:</b> {{ "{:,.0f}".format(doc.grand_total).replace(",", ".") }} ₫</p>
"""
```

và thêm `(NAME_YCBG, "Quotation", HTML_YCBG),` vào cuối list `FORMATS`.

- [ ] **Step 4: Thông báo**

Trong `install_notifications.py`: thêm hằng ở đầu file `TEN_TB_BAO_GIA = "Portal - Yêu cầu báo giá sẵn sàng"`, và thêm một phần tử vào cuối list `DEFS`:

```python
    {
        # Spec 2026-10-12 §7 — bản cho Quotation của "Portal - Báo giá sẵn
        # sàng". Bản trên Sales Order giữ lại cho đơn "Mua lẻ" cũ.
        # `attach_print`/`print_format` do patch v1_42 đặt SAU khi mẫu in đã
        # có: `print_format` là Link, được kiểm ngay lúc insert.
        "name": TEN_TB_BAO_GIA,
        "subject": "Báo giá {{ doc.name }} đã sẵn sàng",
        "document_type": "Quotation",
        "event": "Value Change",
        "value_changed": "workflow_state",
        "condition": (
            "doc.custom_nguon_don == 'Client Portal' and "
            "doc.workflow_state == 'Chờ khách đồng ý'"
        ),
        "message": (
            "Kính gửi Quý khách,\n\nMiyano đã gửi báo giá {{ doc.name }}, tổng giá "
            "trị {{ frappe.utils.fmt_money(doc.grand_total, currency='VND') }}.\n\n"
            "{% if doc.valid_till %}Báo giá có hiệu lực đến hết ngày "
            "{{ frappe.utils.formatdate(doc.valid_till, 'dd/mm/yyyy') }}. Sau thời "
            "hạn này, nếu Quý khách chưa phản hồi, báo giá sẽ tự động đóng.\n\n"
            "{% endif %}Vui lòng đăng nhập cổng khách hàng, mở tab \"Yêu cầu báo "
            "giá\" để xem chi tiết và xác nhận."
        ),
        "send_system_notification": 1,
    },
```

- [ ] **Step 5: Lối tắt hàng việc**

Trong `install_kho_workspace.py`, thêm vào cuối list `_CONG_KHACH_SHORTCUTS` (tab):

```python
	{
		# Spec 2026-10-12 §7 — hàng việc của bộ phận báo giá.
		"label": "Yêu cầu báo giá",
		"link_to": "Quotation",
		"color": "purple",
		"stats_filter": {
			"custom_nguon_don": "Client Portal",
			"workflow_state": "Chờ Miyano báo giá",
		},
	},
```

- [ ] **Step 6: Gọi từ patch**

Trong `patches/v1_42/bao_gia_quotation.py`, thêm hàm và sửa `execute`:

```python
def cai_mau_in_thong_bao_hang_viec():
	from miyano_portal.setup.install_kho_workspace import install_kho_workspace
	from miyano_portal.setup.install_notifications import (
		TEN_TB_BAO_GIA,
		install_portal_notifications,
	)
	from miyano_portal.setup.install_print_formats import (
		NAME_YCBG,
		install_portal_print_formats,
	)

	install_portal_print_formats()
	install_portal_notifications()
	if frappe.db.exists("Notification", TEN_TB_BAO_GIA) and frappe.db.exists(
		"Print Format", NAME_YCBG
	):
		frappe.db.set_value(
			"Notification", TEN_TB_BAO_GIA, {"attach_print": 1, "print_format": NAME_YCBG}
		)
	install_kho_workspace()


def execute():
	them_truong()
	cai_workflow()
	cai_mau_in_thong_bao_hang_viec()
```

- [ ] **Step 7: Khối "Hàng chưa có mã" dùng chung**

Tạo `public/js/hang_moi_khach_khai.js`: CHUYỂN nguyên thân hàm `hien_thong_tin_hang_moi(frm)` từ `sales_order.js` sang, kèm khối chú thích đứng trên nó, đổi dòng khai báo thành gán vào không gian tên của app:

```js
// Khối "Hàng chưa có mã — thông tin khách khai" trên form Sales Order VÀ
// Quotation (spec 2026-10-12 §7). Cả hai doctype mang bảng `custom_dat_ngoai`
// cùng bảng con, nên một hàm phục vụ cả hai; file này nạp TRƯỚC file form
// trong `hooks.py::doctype_js`.
frappe.provide("miyano_portal");

miyano_portal.hien_thong_tin_hang_moi = function (frm) {
	// … thân hàm chuyển nguyên văn từ sales_order.js, không sửa dòng nào …
};
```

Trong `sales_order.js`: xoá định nghĩa `function hien_thong_tin_hang_moi(frm) {…}` và đổi lời gọi trong `refresh` thành `miyano_portal.hien_thong_tin_hang_moi(frm);`.

Tạo `public/js/quotation.js`:

```js
// Form Quotation — yêu cầu báo giá từ cổng khách hàng (spec 2026-10-12 §7).
frappe.ui.form.on("Quotation", {
	refresh(frm) {
		miyano_portal.hien_thong_tin_hang_moi(frm);
	},
});
```

Trong `hooks.py`, `doctype_js`:

```python
	"Sales Order": [
		"public/js/hang_moi_khach_khai.js",
		"public/js/sales_order.js",
		"public/js/dat_ngoai_anh.js",
	],
	"Quotation": [
		"public/js/hang_moi_khach_khai.js",
		"public/js/quotation.js",
		"public/js/dat_ngoai_anh.js",
	],
```

- [ ] **Step 8: Áp patch và chạy**

Run: `bench --site erptest.local execute miyano_portal.patches.v1_42.bao_gia_quotation.execute && bench --site erptest.local clear-cache && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_cai_dat`
Expected: `Ran 6 tests` … `OK`.

- [ ] **Step 9: Test đang ghim `sales_order.js` và các bộ cài**

Run: `for m in test_cr05_khoi_hang_moi test_print_formats test_notifications test_kho_desk_install; do bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.$m 2>&1 | grep -E "^Ran |^OK|^FAILED"; done`
Expected: `OK` cho cả bốn, trừ lỗi nền đã ghi ở Task 0 (`test_notifications`). Nếu một test ghim chuỗi `function hien_thong_tin_hang_moi` trong `sales_order.js`: sửa test đó trỏ sang `hang_moi_khach_khai.js` (hàm đã chuyển nhà, hành vi không đổi).

- [ ] **Step 10: Commit**

```bash
git add miyano_portal/setup miyano_portal/patches/v1_42/bao_gia_quotation.py miyano_portal/public/js miyano_portal/hooks.py miyano_portal/tests/test_bao_gia_cai_dat.py
git commit -m "feat(portal): mau in, thong bao, hang viec va khoi hang chua co ma tren form Quotation"
```

---

### Task 11: Endpoint của cổng

**Files:**
- Modify: `miyano_portal/api/portal.py`
- Modify: `miyano_portal/permissions.py` (hàm `notification_khoa_query`, hằng `_THONG_BAO_DOCTYPE_LOC_KHOA`)
- Test: `miyano_portal/tests/test_bao_gia_endpoint.py`

**Interfaces:**
- Consumes: `bao_gia.dong_y`, `tu_choi`, `sua_so_luong`, `qua_han`, `don_cua_bao_gia`, hằng trạng thái; `get_portal_member()`, `pham_vi_don()`, `la_quan_ly()`, `portal_context.LOI_KHONG_THAY`; `_dong_bo_so_luong_duyet_ve_phieu(ten_phieu, doi_items_ap_dung)` (có sẵn trong `api/portal.py`).
- Produces (đều `@frappe.whitelist()` trong `api/portal.py`):
  - `portal_bao_gia_danh_sach(nhom=None, khoa_phong=None, limit=20, start=0) -> {"rows": [...], "tong": int}`; mỗi dòng: `de_xuat, bao_gia, sales_order, ma, ten_don_hang, khoa_phong, thoi_diem, trang_thai_phieu, owner, trang_thai_bao_gia, grand_total (None khi chưa được xem giá), han_hieu_luc, nhom`.
  - `portal_bao_gia_dem() -> {"cho_dong_y": int}`.
  - `portal_bao_gia_chi_tiet(ten) -> dict` với khoá: `bao_gia, trang_thai, nhom, de_xuat, sales_order, ma, ten_don_hang, khoa_phong, ngay_tao, han_hieu_luc, het_han, hien_gia, tong_tien, ly_do_tu_choi, duoc_dong_y, duoc_sua_so_luong, items[{name, item_code, item_name, uom, qty, rate, amount}], dat_ngoai[{ten_hang, dvt, so_luong, da_xu_ly, item_khop}]`.
  - `portal_bao_gia_dong_y(ten) -> dict`, `portal_bao_gia_tu_choi(ten, ly_do=None) -> dict`, `portal_bao_gia_sua_so_luong(ten, dong) -> dict`.
  - `portal_bao_gia_pdf(order=None, quotation=None)` — thêm tham số `quotation`.
  - `portal_dashboard_kpi()` thêm khoá `bao_gia_cho_dong_y`.
  - Hằng `NHOM_BAO_GIA = ("nhap", "dang_bao_gia", "cho_dong_y", "da_dong_y", "da_dong")`.

- [ ] **Step 1: Viết test hỏng**

`miyano_portal/tests/test_bao_gia_endpoint.py`:

```python
"""Endpoint báo giá của cổng (spec 2026-10-12 §6, §8)."""

import frappe
from frappe.model.workflow import apply_workflow

from miyano_portal import bao_gia
from miyano_portal.api import portal
from miyano_portal.tests.nen_bao_gia import NenBaoGia


class TestBaoGiaEndpoint(NenBaoGia):
	def setUp(self):
		super().setUp()
		self.ql_a = self._quan_ly("bgep.ql.a@demo.miyano", self.kh_a)
		self.ql_b = self._quan_ly("bgep.ql.b@demo.miyano", self.kh_b)
		for ten in frappe.get_all(
			"Portal De Xuat Mua", filters={"customer": ["like", "_TEST DX%"]}, pluck="name"
		):
			frappe.delete_doc("Portal De Xuat Mua", ten, force=True)

	def tearDown(self):
		super().tearDown()
		frappe.local.response.pop("filecontent", None)

	def _phieu(self, ma_hang, khach=None, khoa=None, trang_thai="Nháp"):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua", "customer": khach or self.kh_a,
			"khoa_phong": khoa or self.khoa_huyethoc,
			"ly_do_yeu_cau": "Hết hàng trong kho khoa", "trang_thai": trang_thai,
			"items": [{"item_code": ma_hang, "so_luong_de_xuat": 20, "so_luong_duyet": 20}],
		})
		doc.insert(ignore_permissions=True)
		return doc

	def _phieu_co_bao_gia(self, gui_khach=True):
		"""Phiếu chờ báo giá đã duyệt, có Quotation đứng sau (việc của Task 12)."""
		phieu = self._phieu(self.item_boi_so, trang_thai="Đã duyệt")
		kq = bao_gia.tao_bao_gia(
			self.kh_a, items=[{"item_code": self.item_boi_so, "qty": 20}],
			request_id=frappe.generate_hash(length=12), khoa_phong=self.khoa_huyethoc,
		)
		frappe.db.set_value("Quotation", kq["bao_gia"], "custom_de_xuat", phieu.name)
		frappe.db.set_value("Portal De Xuat Mua", phieu.name, "bao_gia", kq["bao_gia"])
		bg = frappe.get_doc("Quotation", kq["bao_gia"])
		bg.items[0].rate = bg.items[0].price_list_rate = 7000
		bg.save()
		if gui_khach:
			bg = apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		return phieu, bg

	def _goi(self, user, ham, *a, **kw):
		frappe.set_user(user)
		try:
			return ham(*a, **kw)
		finally:
			frappe.set_user("Administrator")

	# ---- hai tab

	def test_phieu_cho_bao_gia_roi_khoi_tab_don_hang(self):
		nhap_bg = self._phieu(self.item_boi_so)
		nhap_gia = self._phieu(self.item_ngoai)
		co_bg, _ = self._phieu_co_bao_gia()
		don = {r["de_xuat"] for r in self._goi(self.ql_a, portal.portal_yeu_cau_cua_toi)["rows"]}
		self.assertIn(nhap_gia.name, don)
		self.assertNotIn(nhap_bg.name, don)
		self.assertNotIn(co_bg.name, don)

	def test_tab_bao_gia_du_nam_nhom(self):
		nhap = self._phieu(self.item_boi_so)
		dang, bg_dang = self._phieu_co_bao_gia(gui_khach=False)
		cho, _ = self._phieu_co_bao_gia()
		dong_y, bg_dy = self._phieu_co_bao_gia()
		self._goi(self.ql_a, bao_gia.dong_y, bg_dy.name)
		dong, bg_dong = self._phieu_co_bao_gia()
		self._goi(self.ql_a, bao_gia.tu_choi, bg_dong.name, None)
		self._phieu(self.item_ngoai)  # phiếu có giá: không thuộc tab này

		rows = self._goi(self.ql_a, portal.portal_bao_gia_danh_sach)["rows"]
		theo_phieu = {r["de_xuat"]: r["nhom"] for r in rows}
		self.assertEqual(theo_phieu, {
			nhap.name: "nhap", dang.name: "dang_bao_gia", cho.name: "cho_dong_y",
			dong_y.name: "da_dong_y", dong.name: "da_dong",
		})
		loc = self._goi(self.ql_a, portal.portal_bao_gia_danh_sach, nhom="cho_dong_y")
		self.assertEqual((loc["tong"], loc["rows"][0]["de_xuat"]), (1, cho.name))
		self.assertEqual(self._goi(self.ql_a, portal.portal_bao_gia_dem), {"cho_dong_y": 1})

	def test_don_sinh_tu_bao_gia_hien_o_tab_don_hang(self):
		phieu, bg = self._phieu_co_bao_gia()
		kq = self._goi(self.ql_a, bao_gia.dong_y, bg.name)
		rows = self._goi(self.ql_a, portal.portal_yeu_cau_cua_toi)["rows"]
		dong = next(r for r in rows if r["de_xuat"] == phieu.name)
		self.assertEqual(dong["sales_order"], kq["sales_order"])

	def test_danh_sach_khong_lo_tong_tien_khi_miyano_dang_bao_gia(self):
		_, bg = self._phieu_co_bao_gia(gui_khach=False)
		row = self._goi(self.ql_a, portal.portal_bao_gia_danh_sach)["rows"][0]
		self.assertEqual(row["bao_gia"], bg.name)
		self.assertIsNone(row["grand_total"])

	def test_nhom_khong_hop_le(self):
		with self.assertRaises(frappe.ValidationError):
			self._goi(self.ql_a, portal.portal_bao_gia_danh_sach, nhom="tat_ca")

	# ---- cách ly

	def test_khach_khac_khong_thay_trong_danh_sach(self):
		self._phieu_co_bao_gia()
		self.assertEqual(self._goi(self.ql_b, portal.portal_bao_gia_danh_sach)["rows"], [])

	def test_khach_khac_khong_doc_khong_dong_y_khong_sua(self):
		_, bg = self._phieu_co_bao_gia()
		for ham, tham_so in (
			(portal.portal_bao_gia_chi_tiet, (bg.name,)),
			(portal.portal_bao_gia_dong_y, (bg.name,)),
			(portal.portal_bao_gia_tu_choi, (bg.name,)),
			(portal.portal_bao_gia_sua_so_luong, (bg.name, [{"name": bg.items[0].name, "qty": 40}])),
			(portal.portal_bao_gia_pdf, (None, bg.name)),
		):
			with self.assertRaises(frappe.PermissionError, msg=ham.__name__):
				self._goi(self.ql_b, ham, *tham_so)
		self.assertEqual(
			frappe.db.get_value("Quotation", bg.name, "workflow_state"), bao_gia.TT_CHO_KHACH
		)

	def test_khoa_khac_khong_thay(self):
		_, bg = self._phieu_co_bao_gia()
		khoa_khac = frappe.get_doc({
			"doctype": "Customer Department", "customer": self.kh_a,
			"ten_khoa_phong": "Khoa thử endpoint báo giá", "ma_khoa": "BGEP", "active": 1,
		}).insert(ignore_permissions=True).name
		nv = self._dam_bao_thanh_vien("bgep.nv@demo.miyano", self.kh_a, "Nhân viên khoa", khoa_khac)
		self.assertEqual(self._goi(nv, portal.portal_bao_gia_danh_sach)["rows"], [])
		with self.assertRaises(frappe.PermissionError):
			self._goi(nv, portal.portal_bao_gia_chi_tiet, bg.name)

	def test_bao_gia_noi_bo_cung_khach_khong_hien(self):
		noi_bo = self._bao_gia_tho(nguon="Nội bộ")
		with self.assertRaises(frappe.PermissionError):
			self._goi(self.ql_a, portal.portal_bao_gia_chi_tiet, noi_bo.name)

	# ---- chi tiết

	def test_chi_tiet_cho_khach_dong_y(self):
		phieu, bg = self._phieu_co_bao_gia()
		ct = self._goi(self.ql_a, portal.portal_bao_gia_chi_tiet, bg.name)
		self.assertEqual((ct["nhom"], ct["de_xuat"]), ("cho_dong_y", phieu.name))
		self.assertTrue(ct["hien_gia"])
		self.assertTrue(ct["duoc_dong_y"])
		self.assertTrue(ct["duoc_sua_so_luong"])
		self.assertEqual(ct["items"][0]["rate"], 7000)
		self.assertEqual(ct["tong_tien"], 140000)
		self.assertEqual(ct["han_hieu_luc"], str(bg.valid_till))

	def test_khong_thay_don_gia_khi_miyano_dang_bao_gia(self):
		_, bg = self._phieu_co_bao_gia(gui_khach=False)
		ct = self._goi(self.ql_a, portal.portal_bao_gia_chi_tiet, bg.name)
		self.assertFalse(ct["hien_gia"])
		self.assertIsNone(ct["items"][0]["rate"])
		self.assertIsNone(ct["items"][0]["amount"])
		self.assertIsNone(ct["tong_tien"])
		self.assertFalse(ct["duoc_dong_y"])

	def test_nhan_vien_khoa_dong_y_duoc_nhung_khong_sua_so_luong(self):
		_, bg = self._phieu_co_bao_gia()
		ct = self._goi(self.user_a, portal.portal_bao_gia_chi_tiet, bg.name)
		self.assertTrue(ct["duoc_dong_y"])
		self.assertFalse(ct["duoc_sua_so_luong"])
		with self.assertRaises(frappe.PermissionError):
			self._goi(self.user_a, portal.portal_bao_gia_sua_so_luong, bg.name,
			          [{"name": bg.items[0].name, "qty": 40}])

	# ---- hành động

	def test_dong_y_qua_endpoint(self):
		phieu, bg = self._phieu_co_bao_gia()
		kq = self._goi(self.ql_a, portal.portal_bao_gia_dong_y, bg.name)
		self.assertTrue(frappe.db.exists("Sales Order", kq["sales_order"]))
		ct = self._goi(self.ql_a, portal.portal_bao_gia_chi_tiet, bg.name)
		self.assertEqual((ct["nhom"], ct["sales_order"]), ("da_dong_y", kq["sales_order"]))

	def test_sua_so_luong_dong_bo_ve_phieu(self):
		phieu, bg = self._phieu_co_bao_gia()
		self._goi(self.ql_a, portal.portal_bao_gia_sua_so_luong, bg.name,
		          frappe.as_json([{"name": bg.items[0].name, "qty": 40}]))
		phieu.reload()
		self.assertEqual(phieu.items[0].so_luong_duyet, 40)

	def test_pdf(self):
		_, dang = self._phieu_co_bao_gia(gui_khach=False)
		with self.assertRaises(frappe.ValidationError):
			self._goi(self.ql_a, portal.portal_bao_gia_pdf, None, dang.name)
		_, bg = self._phieu_co_bao_gia()
		self._goi(self.ql_a, portal.portal_bao_gia_pdf, None, bg.name)
		self.assertEqual(frappe.local.response.type, "pdf")
		self.assertEqual(frappe.local.response.filename, f"BaoGia-{bg.name}.pdf")

	# ---- tổng quan và thông báo

	def test_kpi_dem_bao_gia_cho_dong_y(self):
		truoc = self._goi(self.ql_a, portal.portal_dashboard_kpi)["bao_gia_cho_dong_y"]
		self._phieu_co_bao_gia()
		self.assertEqual(
			self._goi(self.ql_a, portal.portal_dashboard_kpi)["bao_gia_cho_dong_y"], truoc + 1
		)

	def test_duong_dan_thong_bao(self):
		_, bg = self._phieu_co_bao_gia()
		self.assertEqual(
			portal._lien_ket_thong_bao("Quotation", bg.name, self.kh_a),
			f"/yeu-cau-bao-gia/{bg.name}",
		)
		self.assertIsNone(portal._lien_ket_thong_bao("Quotation", bg.name, self.kh_b))
```

- [ ] **Step 2: Chạy, xác nhận hỏng**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_endpoint`
Expected: FAIL — `AttributeError: module 'miyano_portal.api.portal' has no attribute 'portal_bao_gia_danh_sach'`.

- [ ] **Step 3: Mảnh SQL dùng chung và tab Đơn hàng**

Trong `api/portal.py`: thêm import `from miyano_portal import bao_gia` (gộp vào dòng `from miyano_portal import …` đang có) và `LOI_KHONG_THAY` vào khối import từ `portal_context`. Thêm ngay TRƯỚC `portal_yeu_cau_cua_toi`:

```python
# ---------------------------------------------------------------------------
# Yêu cầu báo giá (spec 2026-10-12 §6). Hai tab của màn danh sách dùng CHUNG
# các mảnh SQL dưới đây: tab này nhận đúng những phiếu tab kia bỏ ra, nên một
# luật viết hai lần là hai tab hoặc cùng hiện, hoặc cùng giấu một phiếu.
# ---------------------------------------------------------------------------
NHOM_BAO_GIA = ("nhap", "dang_bao_gia", "cho_dong_y", "da_dong_y", "da_dong")

# Trạng thái mà khách được xem đơn giá. "Chờ Miyano báo giá" KHÔNG có ở đây,
# kể cả khi báo giá còn giữ giá gợi ý sau một lần khách sửa số lượng: giá
# Miyano chưa gửi lại không phải là báo giá.
_BAO_GIA_HIEN_GIA = (
    bao_gia.TT_CHO_KHACH, bao_gia.TT_DA_DONG_Y, bao_gia.TT_KHACH_TU_CHOI, bao_gia.TT_HET_HAN,
)


def _cot_bao_gia_ton_tai() -> bool:
    """Lưới an toàn lúc triển khai: mã mới chạy trên site chưa `bench migrate`
    thì chưa có cột `bao_gia` trên phiếu."""
    return frappe.db.has_column("Portal De Xuat Mua", "bao_gia")


def _sql_phieu_cho_bao_gia(p: str) -> str:
    """Phiếu THUẦN chờ báo giá: có dòng chờ báo giá hoặc dòng gõ tay, và không
    có dòng nào đã có giá. Phiếu nháp còn trộn (chưa gửi duyệt nên chưa tách)
    không thuộc nhóm này."""
    return f"""(
        (exists (select 1 from `tabPortal De Xuat Mua Item` i
                 where i.parent = {p}.name and i.nguon_gia = 'Chờ báo giá')
         or exists (select 1 from `tabSales Order Dat Ngoai Item` d
                    where d.parent = {p}.name and d.parenttype = 'Portal De Xuat Mua'))
        and not exists (select 1 from `tabPortal De Xuat Mua Item` i2
                        where i2.parent = {p}.name
                          and i2.nguon_gia in ('Bảng giá', 'Hợp đồng'))
    )"""


def _sql_thuoc_tab_bao_gia(p: str) -> str:
    """§6.1 — có `bao_gia`, hoặc chưa có cả đơn lẫn báo giá mà là phiếu chờ báo
    giá. Phiếu có `sales_order` mà không có `bao_gia` là đơn "Mua lẻ" của luồng
    cũ: ở lại tab Đơn hàng."""
    return (
        f"(coalesce({p}.bao_gia, '') != '' or (coalesce({p}.sales_order, '') = '' "
        f"and {_sql_phieu_cho_bao_gia(p)}))"
    )


def _sql_an_khoi_tab_don(p: str) -> str:
    """§6.4 — tab Đơn hàng chỉ bỏ phiếu chờ báo giá CHƯA có đơn. Phiếu đã có
    đơn (khách đã đồng ý) hiện ở cả hai tab: bên kia là báo giá, bên này là
    đơn sinh ra từ nó."""
    return (
        f"(coalesce({p}.sales_order, '') = '' and (coalesce({p}.bao_gia, '') != '' "
        f"or {_sql_phieu_cho_bao_gia(p)}))"
    )


def _sql_nhom_bao_gia(q: str) -> str:
    return f"""case
        when {q}.name is null then 'nhap'
        when {q}.workflow_state = '{bao_gia.TT_CHO_MIYANO}' then 'dang_bao_gia'
        when {q}.workflow_state = '{bao_gia.TT_CHO_KHACH}' then 'cho_dong_y'
        when {q}.workflow_state = '{bao_gia.TT_DA_DONG_Y}' then 'da_dong_y'
        else 'da_dong'
    end"""
```

Trong `portal_yeu_cau_cua_toi`: ngay sau dòng `co_nhanh_don = co_cot_khoa or not khoa` thêm

```python
    # Spec 2026-10-12 §6.4 — phiếu chờ báo giá chưa có đơn thuộc tab kia.
    an_bao_gia = (
        f" and not {_sql_an_khoi_tab_don('p')}" if _cot_bao_gia_ton_tai() else ""
    )
```

và đổi dòng `where {dk_phieu}` của `nhanh_phieu` thành `where {dk_phieu}{an_bao_gia}`.

- [ ] **Step 4: Danh sách, số đếm, chi tiết**

Thêm vào `api/portal.py`, ngay sau `portal_yeu_cau_cua_toi`:

```python
def _truy_van_tab_bao_gia() -> tuple[str, dict]:
    """SQL trong và tham số của tab báo giá, đã kẹp phạm vi khách + khoa."""
    tv = get_portal_member()
    tham_so = {"kh": tv.customer}
    dk = "p.customer = %(kh)s"
    khoa = pham_vi_don().get("custom_khoa_phong")
    if khoa:
        tham_so["khoa"] = khoa
        dk += " and p.khoa_phong = %(khoa)s"
    trong = f"""
        select p.name as de_xuat, coalesce(p.bao_gia, '') as bao_gia,
               coalesce(p.sales_order, '') as sales_order,
               coalesce(nullif(p.ma_de_xuat, ''), '') as ma,
               coalesce(p.ten_don_hang, '') as ten_don_hang,
               coalesce(p.khoa_phong, '') as khoa_phong, p.creation as thoi_diem,
               p.trang_thai as trang_thai_phieu, p.owner as owner,
               coalesce(q.workflow_state, '') as trang_thai_bao_gia,
               q.grand_total as grand_total, q.valid_till as han_hieu_luc,
               {_sql_nhom_bao_gia("q")} as nhom
        from `tabPortal De Xuat Mua` p
        left join `tabQuotation` q
               on q.name = p.bao_gia and q.quotation_to = 'Customer'
              and q.party_name = %(kh)s and q.custom_nguon_don = '{bao_gia.NGUON_CONG}'
        where {dk} and {_sql_thuoc_tab_bao_gia("p")}
    """
    return trong, tham_so


@frappe.whitelist()
def portal_bao_gia_danh_sach(nhom=None, khoa_phong=None, limit=20, start=0) -> dict:
    """Tab "Yêu cầu báo giá" (spec 2026-10-12 §6.2). SQL thô như
    `portal_yeu_cau_cua_toi`, vì vai Customer không có DocPerm trên phiếu lẫn
    Quotation; hàm tự kẹp phạm vi khách và khoa."""
    if nhom and nhom not in NHOM_BAO_GIA:
        frappe.throw(f"Nhóm không hợp lệ: {nhom}", frappe.ValidationError)
    if not _cot_bao_gia_ton_tai():
        return {"rows": [], "tong": 0}
    trong, tham_so = _truy_van_tab_bao_gia()
    dieu_kien = []
    if nhom:
        tham_so["nhom"] = nhom
        dieu_kien.append("t.nhom = %(nhom)s")
    if khoa_phong:
        tham_so["kp"] = khoa_phong
        dieu_kien.append("t.khoa_phong = %(kp)s")
    dk_ngoai = (" where " + " and ".join(dieu_kien)) if dieu_kien else ""
    tong = frappe.db.sql(f"select count(*) from ({trong}) t{dk_ngoai}", tham_so)[0][0]
    rows = frappe.db.sql(
        f"""select * from ({trong}) t{dk_ngoai}
            order by t.thoi_diem desc, t.de_xuat desc
            limit %(limit)s offset %(start)s""",
        {**tham_so, "limit": int(limit), "start": int(start)},
        as_dict=True,
    )
    for r in rows:
        duoc_xem_gia = r["trang_thai_bao_gia"] in _BAO_GIA_HIEN_GIA
        r["grand_total"] = float(r["grand_total"] or 0) if duoc_xem_gia else None
        r["han_hieu_luc"] = str(r["han_hieu_luc"]) if r.get("han_hieu_luc") else ""
        r["owner"] = r.get("owner") or ""
    return {"rows": rows, "tong": int(tong)}


@frappe.whitelist()
def portal_bao_gia_dem() -> dict:
    """Số báo giá đang chờ khách đồng ý — huy hiệu trên tab."""
    if not _cot_bao_gia_ton_tai():
        return {"cho_dong_y": 0}
    trong, tham_so = _truy_van_tab_bao_gia()
    n = frappe.db.sql(
        f"select count(*) from ({trong}) t where t.nhom = 'cho_dong_y'", tham_so
    )[0][0]
    return {"cho_dong_y": int(n)}


def _bao_gia_cua_toi(ten: str):
    """Chốt hai trục cho MỌI endpoint báo giá (spec §8). Trả `Document`.

    Quotation dùng `party_name`, không có cột `customer`: các hàm kiểm của
    Sales Order không dùng lại được. Báo giá không phải của cổng (nhân viên tự
    lập) không hiện, kể cả khi cùng khách. Mọi lý do từ chối trả CÙNG một
    thông điệp: không xác nhận cả sự tồn tại của báo giá thuộc khách khác.
    """
    tv = get_portal_member()
    gt = frappe.db.get_value(
        "Quotation", ten,
        ["quotation_to", "party_name", "custom_nguon_don", "custom_khoa_phong"],
        as_dict=True,
    )
    if (
        not gt or gt.quotation_to != "Customer" or gt.party_name != tv.customer
        or gt.custom_nguon_don != bao_gia.NGUON_CONG
    ):
        raise frappe.PermissionError(LOI_KHONG_THAY)
    khoa = pham_vi_don().get("custom_khoa_phong")
    if khoa and gt.custom_khoa_phong != khoa:
        raise frappe.PermissionError(LOI_KHONG_THAY)
    return frappe.get_doc("Quotation", ten)


_NHOM_THEO_TRANG_THAI = {
    bao_gia.TT_CHO_MIYANO: "dang_bao_gia",
    bao_gia.TT_CHO_KHACH: "cho_dong_y",
    bao_gia.TT_DA_DONG_Y: "da_dong_y",
}


@frappe.whitelist()
def portal_bao_gia_chi_tiet(ten) -> dict:
    bg = _bao_gia_cua_toi(ten)
    trang_thai = bg.get("workflow_state") or ""
    hien_gia = trang_thai in _BAO_GIA_HIEN_GIA
    het_han = bao_gia.qua_han(bg)
    cho_khach = trang_thai == bao_gia.TT_CHO_KHACH
    ma = ""
    if bg.get("custom_de_xuat"):
        ma = frappe.db.get_value("Portal De Xuat Mua", bg.custom_de_xuat, "ma_de_xuat") or ""
    return {
        "bao_gia": bg.name,
        "trang_thai": trang_thai,
        "nhom": _NHOM_THEO_TRANG_THAI.get(trang_thai, "da_dong"),
        "de_xuat": bg.get("custom_de_xuat") or "",
        "sales_order": bao_gia.don_cua_bao_gia(bg) or "",
        "ma": ma,
        "ten_don_hang": bg.get("custom_ten_don_hang") or "",
        "khoa_phong": bg.get("custom_khoa_phong") or "",
        "ngay_tao": str(bg.transaction_date),
        "han_hieu_luc": str(bg.valid_till) if bg.get("valid_till") else "",
        "het_han": het_han,
        "hien_gia": hien_gia,
        "tong_tien": float(bg.grand_total or 0) if hien_gia else None,
        "ly_do_tu_choi": bg.get("custom_ly_do_tu_choi") or "",
        "duoc_dong_y": cho_khach and not het_han,
        "duoc_sua_so_luong": cho_khach and not het_han and la_quan_ly(),
        "items": [
            {
                "name": d.name, "item_code": d.item_code, "item_name": d.item_name,
                "uom": d.uom, "qty": float(d.qty or 0),
                "rate": float(d.rate or 0) if hien_gia else None,
                "amount": float(d.amount or 0) if hien_gia else None,
            }
            for d in bg.items if d.item_code != ITEM_GIU_CHO
        ],
        "dat_ngoai": [
            {
                "ten_hang": d.ten_hang, "dvt": d.dvt, "so_luong": float(d.so_luong or 0),
                "da_xu_ly": int(d.da_xu_ly or 0), "item_khop": d.get("item_khop") or "",
            }
            for d in bg.get("custom_dat_ngoai") or []
        ],
    }
```

- [ ] **Step 5: Ba hành động và PDF**

Thêm tiếp:

```python
@frappe.whitelist()
def portal_bao_gia_dong_y(ten) -> dict:
    """Khách đồng ý báo giá → sinh đơn hàng (spec §4.4). Mọi tài khoản trong
    phạm vi bấm được, như `portal_order_accept`."""
    bg = _bao_gia_cua_toi(ten)
    return bao_gia.dong_y(bg.name)


@frappe.whitelist()
def portal_bao_gia_tu_choi(ten, ly_do=None) -> dict:
    bg = _bao_gia_cua_toi(ten)
    return bao_gia.tu_choi(bg.name, ly_do)


@frappe.whitelist()
def portal_bao_gia_sua_so_luong(ten, dong) -> dict:
    """Chỉ quản lý. Nhân viên khoa không có đường "xin sửa" cho báo giá trong
    đợt này (kế hoạch 2026-10-13, mục quyết định để ngỏ)."""
    bg = _bao_gia_cua_toi(ten)
    if not la_quan_ly():
        raise frappe.PermissionError(
            "Chỉ quản lý của quý đơn vị sửa được số lượng trên báo giá."
        )
    kq = bao_gia.sua_so_luong(bg.name, dong)
    if bg.get("custom_de_xuat") and kq["ap_dung"]:
        _dong_bo_so_luong_duyet_ve_phieu(bg.custom_de_xuat, kq["ap_dung"])
    return {"trang_thai_moi": kq["trang_thai_moi"], "thay_doi": kq["thay_doi"]}


def _bao_gia_pdf_quotation(ten) -> None:
    from miyano_portal.setup.install_print_formats import NAME_YCBG

    bg = _bao_gia_cua_toi(ten)
    # Chỉ từ lúc báo giá ĐÃ GỬI cho khách: trước đó giá chưa phải báo giá.
    if bg.get("workflow_state") not in _BAO_GIA_HIEN_GIA:
        frappe.throw(
            "Báo giá này chưa được gửi. Vui lòng đợi Miyano báo giá.", frappe.ValidationError
        )
    if not frappe.db.exists("Print Format", NAME_YCBG):
        frappe.throw(
            "Mẫu in báo giá chưa sẵn sàng. Vui lòng liên hệ quản trị viên hệ thống.",
            frappe.ValidationError,
        )
    pdf = frappe.get_print("Quotation", bg.name, print_format=NAME_YCBG, as_pdf=True)
    frappe.local.response.filename = f"BaoGia-{bg.name}.pdf"
    frappe.local.response.filecontent = pdf
    frappe.local.response.type = "pdf"
```

Sửa `portal_bao_gia_pdf`: đổi chữ ký thành `def portal_bao_gia_pdf(order=None, quotation=None) -> None:` và thêm làm HAI dòng đầu thân hàm (trước `dam_bao_xem_duoc("Sales Order", order)`):

```python
    if quotation:
        return _bao_gia_pdf_quotation(quotation)
```

- [ ] **Step 6: KPI và thông báo**

Trong `portal_dashboard_kpi`, thêm vào dict trả về:

```python
        # Spec 2026-10-12 §6.4 — báo giá chờ đồng ý: Quotation của luồng mới,
        # cộng đơn "Mua lẻ" còn dở của luồng cũ.
        "bao_gia_cho_dong_y": portal_bao_gia_dem()["cho_dong_y"] + frappe.get_list(
            "Sales Order",
            filters=[
                ["workflow_state", "=", TRANG_THAI_CHO_KHACH], ["docstatus", "=", 0],
                ["custom_loai_don", "=", "Mua lẻ"],
            ] + _pham_vi_filters(),
            fields=["count(name) as n"],
        )[0].n,
```

Trong `_lien_ket_thong_bao`, thêm một nhánh ngay sau nhánh `"Portal De Xuat Mua"`:

```python
        if document_type == "Quotation":
            gt = frappe.db.get_value(
                "Quotation", document_name,
                ["quotation_to", "party_name", "custom_nguon_don"], as_dict=True,
            )
            if (
                not gt or gt.quotation_to != "Customer" or gt.party_name != customer
                or gt.custom_nguon_don != bao_gia.NGUON_CONG
            ):
                return None
            return f"/yeu-cau-bao-gia/{document_name}"
```

Thêm `"Quotation"` vào tuple `_THONG_BAO_DOCTYPE_LOC_KHOA` ở CẢ `api/portal.py` LẪN `permissions.py` (hai hằng sinh đôi; `_thong_bao_trong_pham_vi` gọi `dam_bao_xem_duoc`, đã biết Quotation từ Task 3). Trong `permissions.notification_khoa_query`, thêm vào dict `dieu_kien_theo_loai`:

```python
        "Quotation": (
            f"exists (select 1 from `tabQuotation` where "
            f"`tabQuotation`.name = {dname_col} and "
            f"`tabQuotation`.custom_khoa_phong = {escaped})"
        ),
```

- [ ] **Step 7: Chạy, xác nhận qua**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_endpoint`
Expected: `Ran 18 tests` … `OK`.

- [ ] **Step 8: Danh sách đơn hàng và thông báo không hỏng**

Run: `for m in test_yeu_cau_list test_phan_trang test_giai_doan_khoa_va_nhan test_thong_bao_endpoint test_cach_ly_khoa_phong test_bao_gia_pdf test_pham_vi_endpoint; do bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.$m 2>&1 | grep -E "^Ran |^OK|^FAILED"; done`
Expected: bảy cặp `Ran …` / `OK`. Một test đang đòi phiếu NHÁP chỉ có dòng chờ báo giá hiện trong `portal_yeu_cau_cua_toi` thì nay sai theo spec §6.1: sửa test đó để đọc `portal_bao_gia_danh_sach`.

- [ ] **Step 9: Commit**

```bash
git add miyano_portal/api/portal.py miyano_portal/permissions.py miyano_portal/tests/test_bao_gia_endpoint.py
git commit -m "feat(portal): endpoint bao gia cua cong, tab Don hang loai phieu cho bao gia"
```

---

### Task 12: Rẽ nhánh tạo — không còn sinh đơn "Mua lẻ"

**Files:**
- Modify: `miyano_portal/de_xuat_duyet.py` (hàm `duyet_va_tao_don`)
- Modify: `miyano_portal/api/portal.py` (hàm `portal_order_place`, `_dam_bao_phieu_tu_duyet`)
- Modify: `miyano_portal/api/de_xuat.py` (hàm `de_xuat_duyet_phieu`)
- Test: `miyano_portal/tests/test_bao_gia_re_nhanh.py`

**Interfaces:**
- Consumes: `bao_gia.can_bao_gia`, `tao_bao_gia`, `bao_nhan_vien`; `nhat_ky.SK_BAO_GIA_TAO`.
- Produces:
  - `duyet_va_tao_don` trả `{"sales_order": str | None, "bao_gia": str | None, "de_xuat": str, "canh_bao_gia": list}`.
  - `portal_order_place` trả thêm `bao_gia` ở gốc và trong từng phần tử `don[]`; phần tử báo giá có `sales_order = None`, `loai_don = "Yêu cầu báo giá"`.
  - `_dam_bao_phieu_tu_duyet(..., sales_order, da_ton_tai, ten_don_hang=None, bao_gia_ten=None)`.

- [ ] **Step 1: Viết test hỏng**

`miyano_portal/tests/test_bao_gia_re_nhanh.py`:

```python
"""Hai đường tạo đơn rẽ sang Quotation (spec 2026-10-12 §5)."""

import frappe

from miyano_portal import bao_gia, de_xuat_duyet
from miyano_portal.api import portal
from miyano_portal.portal_mua_le import ITEM_GIU_CHO
from miyano_portal.tests.nen_bao_gia import NenBaoGia
from miyano_portal.tests.test_tach_phieu import TestTachPhieu

DONG_GO_TAY = {"ten_hang": "Kim sinh thiết thử", "dvt": "Cái", "so_luong": 2}


class TestBaoGiaReNhanh(NenBaoGia):
	# Quản lý có Contact gắn với khách: ERPNext từ chối `contact_person` lạ.
	_quan_ly_cua = TestTachPhieu._quan_ly_cua

	def setUp(self):
		super().setUp()
		self.ql = self._quan_ly_cua("bgrn.ql@demo.miyano", self.kh_a)
		frappe.db.set_value("Customer", self.kh_a, "account_manager", "Administrator")
		for ten in frappe.get_all(
			"Portal De Xuat Mua", filters={"customer": ["like", "_TEST DX%"]}, pluck="name"
		):
			frappe.delete_doc("Portal De Xuat Mua", ten, force=True)

	def _phieu_cho_duyet(self, ma_hang, dat_ngoai=None):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua", "customer": self.kh_a,
			"khoa_phong": self.khoa_huyethoc, "ly_do_yeu_cau": "Hết hàng trong kho khoa",
			"ten_don_hang": "Đợt thử rẽ nhánh",
			"items": [{"item_code": ma_hang, "so_luong_de_xuat": 20}] if ma_hang else [],
			"dat_ngoai": dat_ngoai or [],
		}).insert(ignore_permissions=True)
		frappe.db.set_value("Portal De Xuat Mua", doc.name, "owner", self.user_a)
		doc.reload()
		doc.gui_duyet()
		return doc

	def _duyet(self, doc):
		frappe.set_user(self.ql)
		try:
			return de_xuat_duyet.duyet_va_tao_don(doc.name, self.ql)
		finally:
			frappe.set_user("Administrator")

	def _dat(self, **gio):
		frappe.set_user(self.ql)
		try:
			return portal.portal_order_place(request_id=frappe.generate_hash(length=12), **gio)
		finally:
			frappe.set_user("Administrator")

	# ---- khoa gửi đề xuất, quản lý duyệt

	def test_phieu_cho_bao_gia_sinh_quotation_khong_sinh_don(self):
		doc = self._phieu_cho_duyet(self.item_boi_so)
		kq = self._duyet(doc)
		self.assertIsNone(kq["sales_order"])
		bg = frappe.get_doc("Quotation", kq["bao_gia"])
		self.assertEqual(bg.workflow_state, bao_gia.TT_CHO_MIYANO)
		self.assertEqual(bg.custom_de_xuat, doc.name)
		self.assertEqual(bg.custom_khoa_phong, self.khoa_huyethoc)
		self.assertEqual(bg.custom_ten_don_hang, "Đợt thử rẽ nhánh")
		doc.reload()
		self.assertEqual((doc.trang_thai, doc.bao_gia), ("Đã duyệt", bg.name))
		self.assertFalse(doc.sales_order)
		self.assertFalse(frappe.db.exists("Sales Order", {"custom_de_xuat": doc.name}))

	def test_phieu_co_gia_van_sinh_don(self):
		doc = self._phieu_cho_duyet(self.item_ngoai)
		kq = self._duyet(doc)
		self.assertIsNone(kq["bao_gia"])
		self.assertEqual(
			frappe.db.get_value("Sales Order", kq["sales_order"], "custom_loai_don"),
			"Theo bảng giá",
		)

	def test_moi_dong_vua_co_gia_thi_di_thang_don(self):
		doc = self._phieu_cho_duyet(self.item_boi_so)
		self._tao_gia(self.item_boi_so, self.price_list, 7000)
		kq = self._duyet(doc)
		self.assertIsNone(kq["bao_gia"])
		self.assertTrue(frappe.db.exists("Sales Order", kq["sales_order"]))

	def test_phieu_chi_co_dong_go_tay(self):
		doc = self._phieu_cho_duyet(None, dat_ngoai=[DONG_GO_TAY])
		bg = frappe.get_doc("Quotation", self._duyet(doc)["bao_gia"])
		self.assertEqual([d.item_code for d in bg.items], [ITEM_GIU_CHO])
		self.assertEqual(bg.custom_dat_ngoai[0].ten_hang, "Kim sinh thiết thử")

	def test_nhan_vien_phu_trach_duoc_bao(self):
		kq = self._duyet(self._phieu_cho_duyet(self.item_boi_so))
		self.assertTrue(frappe.db.exists("Notification Log", {
			"document_type": "Quotation", "document_name": kq["bao_gia"],
			"for_user": "Administrator",
		}))

	def test_duyet_lai_khong_sinh_bao_gia_thu_hai(self):
		doc = self._phieu_cho_duyet(self.item_boi_so)
		self._duyet(doc)
		with self.assertRaises(frappe.ValidationError):
			self._duyet(doc)
		self.assertEqual(frappe.db.count("Quotation", {"custom_de_xuat": doc.name}), 1)

	# ---- quản lý đặt trực tiếp

	def test_gio_tron_mot_don_mot_bao_gia(self):
		kq = self._dat(items=[
			{"item_code": self.item_ngoai, "qty": 10},
			{"item_code": self.item_boi_so, "qty": 20},
		], khoa_phong=self.khoa_huyethoc)
		self.assertEqual(len(kq["don"]), 2)
		don, bg = kq["don"]
		self.assertEqual(don["loai_don"], "Theo bảng giá")
		self.assertTrue(frappe.db.exists("Sales Order", don["sales_order"]))
		self.assertIsNone(bg["sales_order"])
		self.assertEqual(bg["loai_don"], "Yêu cầu báo giá")
		phieu = frappe.get_doc("Portal De Xuat Mua", bg["de_xuat"])
		self.assertEqual((phieu.bao_gia, phieu.trang_thai), (bg["bao_gia"], "Đã duyệt"))
		self.assertFalse(phieu.sales_order)
		self.assertEqual(
			frappe.db.get_value("Quotation", bg["bao_gia"], "custom_de_xuat"), phieu.name
		)

	def test_gio_chi_co_hang_chua_gia(self):
		kq = self._dat(items=[{"item_code": self.item_boi_so, "qty": 20}],
		               khoa_phong=self.khoa_huyethoc)
		self.assertEqual(len(kq["don"]), 1)
		self.assertIsNone(kq["sales_order"])
		self.assertTrue(frappe.db.exists("Quotation", kq["bao_gia"]))

	def test_bam_lai_khong_sinh_trung(self):
		rid = frappe.generate_hash(length=12)
		gio = {"items": [{"item_code": self.item_boi_so, "qty": 20}],
		       "khoa_phong": self.khoa_huyethoc, "request_id": rid}
		frappe.set_user(self.ql)
		kq1 = portal.portal_order_place(**gio)
		kq2 = portal.portal_order_place(**gio)
		frappe.set_user("Administrator")
		self.assertEqual(kq1["bao_gia"], kq2["bao_gia"])
		self.assertEqual(kq1["de_xuat"], kq2["de_xuat"])
		self.assertEqual(frappe.db.count("Quotation", {"custom_request_id": rid}), 1)

	def test_khong_con_don_mua_le_moi(self):
		truoc = frappe.db.count("Sales Order", {"custom_loai_don": "Mua lẻ"})
		self._duyet(self._phieu_cho_duyet(self.item_boi_so))
		self._dat(items=[{"item_code": self.item_boi_so, "qty": 20}], dat_ngoai=[DONG_GO_TAY],
		          khoa_phong=self.khoa_huyethoc)
		self.assertEqual(frappe.db.count("Sales Order", {"custom_loai_don": "Mua lẻ"}), truoc)
```

- [ ] **Step 2: Chạy, xác nhận hỏng**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_re_nhanh`
Expected: FAIL — `KeyError: 'bao_gia'` ở các test đọc `kq["bao_gia"]`, và `test_khong_con_don_mua_le_moi` đếm thêm đơn `"Mua lẻ"`.

- [ ] **Step 3: `duyet_va_tao_don`**

Trong `de_xuat_duyet.py`: đổi import thành `from miyano_portal import bao_gia, dat_hang, nhat_ky`. Trong `duyet_va_tao_don`, ngay SAU dòng `canh_bao_gia = _kiem_gia_doi(doc)` và TRƯỚC lời gọi `dat_hang.tao_sales_order`, thêm:

```python
	# Spec 2026-10-12 §5 — phiếu còn dòng chưa có giá hoặc dòng gõ tay sinh
	# một Quotation, không sinh Sales Order "Mua lẻ" nữa. Hỏi lại Price List
	# LÚC DUYỆT: phiếu chờ báo giá mà mọi dòng vừa có giá thì đi thẳng đơn.
	dat_ngoai = [d.as_dict() for d in doc.dat_ngoai]
	if bao_gia.can_bao_gia(doc.customer, dong, dat_ngoai):
		return _duyet_va_tao_bao_gia(
			doc, dong, dat_ngoai, nguoi_duyet, tu_cach, uy_quyen, canh_bao_gia
		)
```

Ở câu `return {...}` cuối hàm, thêm khoá `"bao_gia": None`. Thêm hàm mới ngay sau `duyet_va_tao_don`:

```python
def _duyet_va_tao_bao_gia(doc, dong, dat_ngoai, nguoi_duyet, tu_cach, uy_quyen,
                          canh_bao_gia) -> dict:
	"""Nhánh Quotation của `duyet_va_tao_don`. Cùng thứ tự với nhánh đơn: tạo
	chứng từ, gắn vào phiếu, rồi mới `duyet()`."""
	kq = bao_gia.tao_bao_gia(
		doc.customer, items=dong, dat_ngoai=dat_ngoai,
		delivery_date=doc.ngay_can, address=doc.dia_chi_giao, note=doc.ghi_chu,
		request_id=doc.request_id or doc.name, khoa_phong=doc.khoa_phong,
	)
	if kq.get("da_ton_tai"):
		frappe.throw(
			f'Yêu cầu báo giá {kq["bao_gia"]} đã được tạo trước đó cho mã yêu cầu '
			f'"{doc.request_id or doc.name}" — phiếu này có thể đã được duyệt rồi. '
			"Tải lại trang để xem trạng thái mới nhất; nếu phiếu vẫn đang chờ "
			"duyệt thì liên hệ Miyano, KHÔNG bấm duyệt lại.",
			frappe.ValidationError,
		)
	doc.bao_gia = kq["bao_gia"]
	doc.duyet(nguoi_duyet, tu_cach=tu_cach, uy_quyen=uy_quyen)
	frappe.db.set_value("Quotation", kq["bao_gia"], {
		"custom_de_xuat": doc.name,
		"custom_ten_don_hang": doc.get("ten_don_hang") or "",
	})
	nhat_ky.ghi(
		nhat_ky.SK_BAO_GIA_TAO, customer=doc.customer, khoa_phong=doc.khoa_phong,
		de_xuat=doc.name, vai=nhat_ky.VAI_HE_THONG,
	)
	bao_gia.bao_nhan_vien(
		frappe.get_doc("Quotation", kq["bao_gia"]), "Portal - Yêu cầu báo giá mới",
		f"Khách hàng <b>{doc.customer}</b> vừa gửi yêu cầu báo giá "
		f"<b>{kq['bao_gia']}</b> ({doc.ma_de_xuat or doc.name}).",
	)
	return {
		"sales_order": None, "bao_gia": kq["bao_gia"], "de_xuat": doc.name,
		"canh_bao_gia": canh_bao_gia,
	}
```

Trong `api/de_xuat.py`, hàm `de_xuat_duyet_phieu`: phần tử `phieu_cung_lan_dat` thêm khoá `"bao_gia": kq_kia.get("bao_gia")`.

- [ ] **Step 4: `_dam_bao_phieu_tu_duyet` nhận Quotation**

Trong `api/portal.py`, hàm `_dam_bao_phieu_tu_duyet`: thêm tham số cuối `bao_gia_ten=None`, rồi sửa bốn chỗ.

Khối `if da_ton_tai:` — tra theo chứng từ thật đứng sau:

```python
    if da_ton_tai:
        khoa_tra = {"bao_gia": bao_gia_ten} if bao_gia_ten else {"sales_order": sales_order}
        return frappe.db.get_value(
            "Portal De Xuat Mua", {**khoa_tra, "request_id": request_id}, "name"
        )
```

Câu đọc dòng hàng — đọc từ đúng chứng từ:

```python
    bang_dong, cha = (
        ("Quotation Item", bao_gia_ten) if bao_gia_ten else ("Sales Order Item", sales_order)
    )
```

và trong `frappe.get_all(...)` đổi `"Sales Order Item", filters={"parent": sales_order}` thành `bang_dong, filters={"parent": cha}`.

Dict của `frappe.get_doc({...})` — thêm khoá `"bao_gia": bao_gia_ten,` cạnh `"sales_order": sales_order,`.

Phần ghi ngược sau `doc.insert(...)` — bọc nhánh:

```python
    if bao_gia_ten:
        frappe.db.set_value("Quotation", bao_gia_ten, {
            "custom_de_xuat": doc.name,
            "custom_ten_don_hang": doc.get("ten_don_hang") or "",
        })
    else:
        # … khối `gia_tri_don = {...}` và `frappe.db.set_value("Sales Order", …)`
        # hiện có, giữ nguyên, thụt vào một cấp …
```

và lời gọi `nhat_ky.ghi` cuối hàm:

```python
    nhat_ky.ghi(
        nhat_ky.SK_BAO_GIA_TAO if bao_gia_ten else nhat_ky.SK_DON_TAO,
        customer=customer, khoa_phong=khoa_phong, de_xuat=doc.name,
        sales_order=sales_order, vai=nhat_ky.VAI_HE_THONG,
    )
```

- [ ] **Step 5: `portal_order_place`**

Trong `portal_order_place`:

Hàm con `_da_co_don` — một lô đã chạy có thể đã sinh Quotation:

```python
    def _da_co_don(*ds_rid):
        if frappe.db.exists(
            "Sales Order", {"custom_request_id": ["in", list(ds_rid)], "customer": customer}
        ):
            return True
        return bool(frappe.db.exists(
            "Quotation", {"custom_request_id": ["in", list(ds_rid)], "party_name": customer}
        ))
```

Thân vòng `for lo_items, lo_ngoai, rid in lo:` — thay bằng:

```python
    for lo_items, lo_ngoai, rid in lo:
        # Spec 2026-10-12 §5 — lô còn dòng chưa có giá hoặc dòng gõ tay sinh
        # Quotation. Một lô đã sinh Quotation ở lần bấm trước thì lần bấm lại
        # cũng phải đi nhánh này, dù Price List vừa có thêm giá.
        da_la_bao_gia = bool(frappe.db.exists(
            "Quotation", {"custom_request_id": rid, "party_name": customer}
        ))
        if da_la_bao_gia or bao_gia.can_bao_gia(customer, lo_items, lo_ngoai):
            kq = bao_gia.tao_bao_gia(
                customer, items=lo_items, dat_ngoai=lo_ngoai,
                delivery_date=delivery_date, note=note, address=address,
                request_id=rid, khoa_phong=khoa,
            )
            kq["sales_order"] = None
            kq["loai_don"] = "Yêu cầu báo giá"
        else:
            kq = dat_hang.tao_sales_order(
                customer, mode=mode, items=lo_items, dat_ngoai=lo_ngoai,
                po=po, delivery_date=delivery_date, note=note, address=address,
                request_id=rid, khoa_phong=khoa,
            )
            kq["bao_gia"] = None
            kq["loai_don"] = frappe.db.get_value(
                "Sales Order", kq["sales_order"], "custom_loai_don"
            )
        kq["de_xuat"] = _dam_bao_phieu_tu_duyet(
            customer=customer, khoa_phong=khoa, mode=mode, contract=None,
            dat_ngoai=lo_ngoai, delivery_date=delivery_date, address=address,
            note=note, request_id=rid, ten_don_hang=ten_don_hang,
            sales_order=kq["sales_order"], da_ton_tai=bool(kq.get("da_ton_tai")),
            bao_gia_ten=kq["bao_gia"],
        )
        if kq["bao_gia"] and not kq.get("da_ton_tai"):
            bao_gia.bao_nhan_vien(
                frappe.get_doc("Quotation", kq["bao_gia"]), "Portal - Yêu cầu báo giá mới",
                f"Khách hàng <b>{customer}</b> vừa gửi yêu cầu báo giá <b>{kq['bao_gia']}</b>.",
            )
        don.append(kq)
```

Câu `return` cuối hàm — thêm `bao_gia` vào từng phần tử:

```python
            {"sales_order": d["sales_order"], "bao_gia": d["bao_gia"],
             "de_xuat": d["de_xuat"], "loai_don": d["loai_don"]}
```

- [ ] **Step 6: Chạy, xác nhận qua**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_re_nhanh`
Expected: `Ran 10 tests` … `OK`.

- [ ] **Step 7: Sửa các test của luồng cũ đang đi qua hai đường này**

Run: `for m in test_tach_phieu test_don_tron_bao_gia test_phieu_bang_gia test_api_lan_dat test_e6_mua_le test_xay_don_bang_gia test_chi_tiet_gop test_de_xuat_cach_ly test_huy_hieu_cho_bao_gia; do echo "== $m"; bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.$m 2>&1 | grep -E "^(ERROR|FAIL):|^Ran |^OK|^FAILED"; done`
Expected: một số test hỏng. Xử lý từng test theo đúng một luật:

- Test dựng đơn bằng `dat_hang.tao_sales_order(...)` TRỰC TIẾP rồi kiểm luồng `"Mua lẻ"`: phải vẫn qua. Hỏng thì là lỗi của kế hoạch này, tìm nguyên nhân.
- Test đi qua `duyet_va_tao_don` hoặc `portal_order_place` với hàng chưa có giá / dòng gõ tay và đòi một Sales Order `"Mua lẻ"`: hành vi đó đã bị spec §5 thay. Sửa phần khẳng định: `kq["sales_order"]` là `None`, `kq["bao_gia"]` là một Quotation ở `"Chờ Miyano báo giá"`, phiếu mang `bao_gia`. Nếu test còn kiểm bước sau của đơn `"Mua lẻ"` (điền giá, gửi khách, đồng ý), đổi phần dựng dữ liệu sang `dat_hang.tao_sales_order` trực tiếp để nó tiếp tục canh luồng cũ.

Không xoá test nào. Chạy lại vòng lặp tới khi cả chín file `OK`.

- [ ] **Step 8: Commit**

```bash
git add miyano_portal/de_xuat_duyet.py miyano_portal/api/portal.py miyano_portal/api/de_xuat.py miyano_portal/tests
git commit -m "feat(portal): phieu cho bao gia sinh Quotation, khong con sinh don Mua le moi"
```

---

### Task 13: Đơn "Theo báo giá" và luồng cũ

**Files:**
- Modify: `miyano_portal/chot_bao_gia.py`
- Modify: `miyano_portal/api/portal.py` (hàm `portal_order_accept`)
- Test: `miyano_portal/tests/test_don_theo_bao_gia.py`

**Interfaces:**
- Consumes: `bao_gia.dong_y`; `portal_mua_le.di_vong_bao_gia(so)`; `bang_gia_khach.dong_dau_gia_khach_dong_y(so)`, `ghi_gia_da_dong_y`.
- Produces: `chot_bao_gia.co_gia_khach_dong_y(doc) -> bool` — đơn mang giá khách đã đồng ý: đơn `"Mua lẻ"` HOẶC `"Theo báo giá"`.

- [ ] **Step 1: Viết test hỏng**

`miyano_portal/tests/test_don_theo_bao_gia.py`:

```python
"""Đơn "Theo báo giá" là đơn thường với mọi chốt của luồng cũ, trừ chốt 3
(spec 2026-10-12 §4.5). Và luồng "Mua lẻ" cũ vẫn chạy nốt (§9)."""

from pathlib import Path

import frappe
from frappe.model.workflow import apply_workflow
from frappe.utils import add_days, nowdate

from miyano_portal import bang_gia_khach, bao_gia, chot_bao_gia, dat_hang, portal_bao_gia
from miyano_portal.api import portal
from miyano_portal.portal_mua_le import di_vong_bao_gia
from miyano_portal.tests.nen_bao_gia import NenBaoGia

FRONTEND = Path(frappe.get_app_path("miyano_portal")).parent / "frontend" / "src"


class TestDonTheoBaoGia(NenBaoGia):
	@classmethod
	def setUpClass(cls):
		cls.addClassCleanup(frappe.clear_document_cache, "Workflow", "Sales Order - Client Portal")
		super().setUpClass()
		from miyano_portal.patches.v1_41 import gia_theo_price_list

		gia_theo_price_list.mo_rong_workflow()

	def setUp(self):
		super().setUp()
		self.ql = self._quan_ly("dtbg.ql@demo.miyano", self.kh_a)

	def _voi_khach(self, ham, *a, **kw):
		frappe.set_user(self.ql)
		try:
			return ham(*a, **kw)
		finally:
			frappe.set_user("Administrator")

	def _don_theo_bao_gia(self):
		phieu = frappe.get_doc({
			"doctype": "Portal De Xuat Mua", "customer": self.kh_a,
			"khoa_phong": self.khoa_huyethoc, "ly_do_yeu_cau": "Hết hàng trong kho khoa",
			"trang_thai": "Đã duyệt", "ngay_can": add_days(nowdate(), 10),
			"items": [{"item_code": self.item_boi_so, "so_luong_de_xuat": 20, "so_luong_duyet": 20}],
		}).insert(ignore_permissions=True)
		kq = bao_gia.tao_bao_gia(
			self.kh_a, items=[{"item_code": self.item_boi_so, "qty": 20}],
			request_id=frappe.generate_hash(length=12), khoa_phong=self.khoa_huyethoc,
		)
		bg = frappe.get_doc("Quotation", kq["bao_gia"])
		bg.custom_de_xuat = phieu.name
		bg.items[0].rate = bg.items[0].price_list_rate = 7000
		bg.save()
		frappe.db.set_value("Portal De Xuat Mua", phieu.name, "bao_gia", bg.name)
		bg = apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		ten = self._voi_khach(bao_gia.dong_y, bg.name)["sales_order"]
		return frappe.get_doc("Sales Order", ten), phieu

	# ---- bảng §4.5

	def test_khong_di_vong_bao_gia(self):
		so, _ = self._don_theo_bao_gia()
		self.assertFalse(di_vong_bao_gia(so))
		self.assertTrue(chot_bao_gia.co_gia_khach_dong_y(so))

	def test_track_khong_co_khoi_chap_nhan(self):
		so, _ = self._don_theo_bao_gia()
		kq = self._voi_khach(portal.portal_order_track, so.name)
		self.assertIsNone(kq["chap_nhan"])
		self.assertEqual(kq["loai_don"], "Theo báo giá")

	def test_pdf_bao_gia_tren_don_khong_ap_dung(self):
		so, _ = self._don_theo_bao_gia()
		with self.assertRaises(frappe.ValidationError):
			self._voi_khach(portal.portal_bao_gia_pdf, so.name)

	def test_sua_so_luong_tren_don_bi_tu_choi(self):
		so, _ = self._don_theo_bao_gia()
		with self.assertRaises(frappe.ValidationError):
			self._voi_khach(portal.portal_order_sua_so_luong, so.name,
			                {"items": [{"item_code": self.item_boi_so, "qty": 40}]})

	def test_job_het_han_cua_luong_cu_khong_quet(self):
		so, _ = self._don_theo_bao_gia()
		frappe.db.set_value("Sales Order", so.name, {
			"workflow_state": "Chờ khách đồng ý",
			"custom_ngay_gui_khach_duyet": add_days(nowdate(), -60),
		}, update_modified=False)
		portal_bao_gia.quet_bao_gia_het_han()
		self.assertEqual(
			frappe.db.get_value("Sales Order", so.name, "workflow_state"), "Chờ khách đồng ý"
		)

	def test_thong_bao_bao_gia_san_sang_tren_don_khong_gui(self):
		so, _ = self._don_theo_bao_gia()
		dieu_kien = frappe.db.get_value("Notification", "Portal - Báo giá sẵn sàng", "condition")
		so.workflow_state = "Chờ khách đồng ý"
		self.assertFalse(frappe.safe_eval(dieu_kien, None, {"doc": so, "frappe": frappe}))

	def test_xin_sua_qua_phieu_bi_tu_choi_nhu_don_thuong(self):
		_so, phieu = self._don_theo_bao_gia()
		phieu.reload()
		with self.assertRaises(frappe.ValidationError) as ctx:
			phieu._kiem_don_dung_duoc_xin_sua()
		self.assertIn("không có dòng nào chờ báo giá", str(ctx.exception))

	def test_giao_dien_van_so_dung_chuoi_mua_le(self):
		for ten in ("components/chi-tiet/KhoiBaoGia.vue", "don-actions.js"):
			nguon = (FRONTEND / ten).read_text()
			self.assertIn("'Mua lẻ'", nguon, ten)
			self.assertNotIn("Theo báo giá", nguon, ten)

	# ---- chốt 3 mở rộng

	def test_xac_nhan_duoc_khi_gia_khop(self):
		so, _ = self._don_theo_bao_gia()
		so = apply_workflow(so, "Xác nhận")
		self.assertEqual((so.workflow_state, so.docstatus), ("Đã xác nhận", 1))

	def test_khong_xac_nhan_khi_gia_khac_gia_khach_dong_y(self):
		so, _ = self._don_theo_bao_gia()
		so.items[0].rate = 9000
		so.save()
		with self.assertRaises(frappe.ValidationError) as ctx:
			apply_workflow(so, "Xác nhận")
		self.assertIn("khác giá khách đã đồng ý", str(ctx.exception))

	def test_gui_khach_duyet_lai_thi_dong_dau_gia_moi(self):
		so, _ = self._don_theo_bao_gia()
		so.items[0].rate = so.items[0].price_list_rate = 9000
		so.save()
		so = apply_workflow(so, "Gửi khách duyệt")
		self._voi_khach(portal.portal_order_accept, so.name, "dong_y")
		so.reload()
		self.assertEqual(so.workflow_state, "Chờ Miyano xác nhận")
		self.assertEqual(so.items[0].custom_gia_khach_dong_y, 9000)
		self.assertEqual(bang_gia_khach.gia_bang_gia(self.kh_a, self.item_boi_so), 9000)

	# ---- luồng cũ

	def test_don_mua_le_cu_van_dong_y_duoc(self):
		"""Review Focus 8."""
		kq = dat_hang.tao_sales_order(
			self.kh_a, items=[{"item_code": self.item_boi_so, "qty": 20}],
			request_id=frappe.generate_hash(length=12),
		)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(so.custom_loai_don, "Mua lẻ")
		so.items[0].rate = 7000
		so.save()
		so = apply_workflow(so, "Gửi khách duyệt")
		self._voi_khach(portal.portal_order_accept, so.name, "dong_y")
		so.reload()
		self.assertEqual(so.workflow_state, "Chờ Miyano xác nhận")
		self.assertEqual(bang_gia_khach.gia_bang_gia(self.kh_a, self.item_boi_so), 7000)
```

- [ ] **Step 2: Chạy, xác nhận hỏng**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_don_theo_bao_gia`
Expected: FAIL — `AttributeError: module 'miyano_portal.chot_bao_gia' has no attribute 'co_gia_khach_dong_y'`; sau khi có hàm, `test_khong_xac_nhan_khi_gia_khac…` và `test_gui_khach_duyet_lai…` còn hỏng cho tới Step 3–4. Các test còn lại của bảng §4.5 có thể qua ngay: chúng ghim việc `"Theo báo giá"` KHÁC `"Mua lẻ"`.

- [ ] **Step 3: Chốt 3 nhận đơn "Theo báo giá"**

Trong `chot_bao_gia.py`, thêm sau `_trang_thai_truoc`:

```python
def co_gia_khach_dong_y(doc) -> bool:
	"""Đơn mang giá khách ĐÃ ĐỒNG Ý trên từng dòng: đơn "Mua lẻ" của luồng cũ
	(khách đồng ý trên chính đơn) và đơn "Theo báo giá" (khách đồng ý trên
	Quotation, spec 2026-10-12 §4.5). KHÁC `di_vong_bao_gia`: đơn "Theo báo
	giá" không đi vòng báo giá trên Sales Order, nhưng vẫn không được xác nhận
	với một đơn giá khách chưa từng đồng ý."""
	from miyano_portal.bao_gia import LOAI_DON_THEO_BAO_GIA

	return di_vong_bao_gia(doc) or doc.get("custom_loai_don") == LOAI_DON_THEO_BAO_GIA
```

Trong `kiem_gia_khop_gia_da_dong_y`, đổi điều kiện thoát đầu hàm thành:

```python
	if doc.get("custom_nguon_don") != "Client Portal" or not co_gia_khach_dong_y(doc):
		return
```

- [ ] **Step 4: Gửi khách duyệt lại trên đơn "Theo báo giá"**

Chốt 3 chỉ có một lối ra: «Gửi khách duyệt» lại từ "Chờ Miyano xác nhận" (cạnh có sẵn từ patch v1_41), khách đồng ý lại bằng `portal_order_accept`. Trong hàm đó, nhánh `if action == "dong_y":`, đổi `if di_vong_bao_gia(so):` (dòng đứng trước `so.reload()` / `dong_dau_gia_khach_dong_y`) thành:

```python
        if chot_bao_gia.co_gia_khach_dong_y(so):
```

và thêm `chot_bao_gia` vào dòng `from miyano_portal import …` đầu file. KHÔNG đổi `di_vong_bao_gia(so)` ở phép kiểm hạn hiệu lực phía trên: hạn N ngày là của vòng báo giá `"Mua lẻ"`.

- [ ] **Step 5: Chạy, xác nhận qua**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_don_theo_bao_gia`
Expected: `Ran 12 tests` … `OK`.

- [ ] **Step 6: Chốt của luồng cũ không đổi hành vi**

Run: `for m in test_chot_bao_gia test_ghi_gia_da_dong_y test_e2_workflow_va_accept test_e6_mua_le; do bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.$m 2>&1 | grep -E "^Ran |^OK|^FAILED"; done`
Expected: bốn cặp `Ran …` / `OK`.

- [ ] **Step 7: Commit**

```bash
git add miyano_portal/chot_bao_gia.py miyano_portal/api/portal.py miyano_portal/tests/test_don_theo_bao_gia.py
git commit -m "feat(portal): chot gia khop gia da dong y cho don Theo bao gia, luong Mua le cu chay not"
```

---

### Task 14: Cổng — tab "Yêu cầu báo giá"

**Files:**
- Create: `frontend/src/bao-gia.js`, `frontend/src/bao-gia.test.mjs`
- Create: `frontend/src/components/TabDonBaoGia.vue`
- Create: `frontend/src/views/BaoGiaList.vue`, `frontend/src/views/ChiTietBaoGia.vue`
- Modify: `frontend/src/router.js`, `frontend/src/App.vue`, `frontend/src/format.js`
- Modify: `frontend/src/views/YeuCauList.vue`, `ChiTietYeuCau.vue`, `Dashboard.vue`, `LapPhieu.vue`
- Test: `miyano_portal/tests/test_bao_gia_giao_dien.py`

**Interfaces:**
- Consumes: endpoint của Task 11 (`portal_bao_gia_danh_sach`, `portal_bao_gia_dem`, `portal_bao_gia_chi_tiet`, `portal_bao_gia_dong_y`, `portal_bao_gia_tu_choi`, `portal_bao_gia_sua_so_luong`, `portal_bao_gia_pdf?quotation=`), `portal_nhat_ky_yeu_cau({de_xuat})`; `api.call`, `showToast`, `fmtVND`, `fmtDate`, `store`, `useIsMobile`, `PhanTrang`, `ReasonModal` (props `open, title, desc, placeholder, minLen, submitting, submitLabel`; emit `submit(value)`, `close`), `KhoiDongThoiGian` (props `dong`, `dangTai`).
- Produces: route `bao-gia` (`/yeu-cau-bao-gia`) và `bao-gia-detail` (`/yeu-cau-bao-gia/:ten`); module `bao-gia.js` xuất `NHOM_BAO_GIA`, `nhanNhomBaoGia(khoa)`, `nhomBaoGiaBadge(khoa)`, `khoaNhomBaoGia(gt)`, `dichDongBaoGia(dong)`, `hanhDongBaoGia(bg)`, `dongDaSua(items, soLuongMoi)`.

- [ ] **Step 1: Viết test hỏng cho module JS**

`frontend/src/bao-gia.test.mjs`:

```js
// Nhóm, nhãn và hành động của tab "Yêu cầu báo giá" (spec 2026-10-12 §6).
// Chạy bằng `node --test src/*.test.mjs` (`yarn test`).

import test from 'node:test'
import assert from 'node:assert/strict'
import {
  NHOM_BAO_GIA, nhanNhomBaoGia, nhomBaoGiaBadge, khoaNhomBaoGia,
  dichDongBaoGia, hanhDongBaoGia, dongDaSua,
} from './bao-gia.js'

test('năm nhóm, đúng thứ tự vòng đời', () => {
  assert.deepEqual(NHOM_BAO_GIA, ['nhap', 'dang_bao_gia', 'cho_dong_y', 'da_dong_y', 'da_dong'])
})

test('nhãn nói rõ việc đang ở phía ai, không dùng lại "Chờ báo giá"', () => {
  assert.equal(nhanNhomBaoGia('dang_bao_gia'), 'Miyano đang báo giá')
  assert.equal(nhanNhomBaoGia('cho_dong_y'), 'Chờ anh/chị đồng ý')
  for (const k of NHOM_BAO_GIA) assert.notEqual(nhanNhomBaoGia(k), 'Chờ báo giá')
})

test('nhóm lạ không làm vỡ nhãn và huy hiệu', () => {
  assert.equal(nhanNhomBaoGia('la'), 'la')
  assert.equal(nhomBaoGiaBadge('la'), 'b-gray')
  assert.equal(nhomBaoGiaBadge('cho_dong_y'), 'b-orange')
})

test('?nhom= chỉ nhận khoá hợp lệ', () => {
  assert.equal(khoaNhomBaoGia('cho_dong_y'), 'cho_dong_y')
  assert.equal(khoaNhomBaoGia('cho_duyet'), '')
  assert.equal(khoaNhomBaoGia(undefined), '')
})

test('dòng đã có báo giá mở màn báo giá; chưa có thì mở phiếu', () => {
  assert.deepEqual(dichDongBaoGia({ bao_gia: 'SAL-QTN-1', de_xuat: 'DXM-1' }),
    { name: 'bao-gia-detail', params: { ten: 'SAL-QTN-1' } })
  assert.deepEqual(dichDongBaoGia({ bao_gia: '', de_xuat: 'DXM-1' }),
    { name: 'de-xuat-detail', params: { ten: 'DXM-1' } })
})

test('hành động theo cờ của server', () => {
  assert.deepEqual(hanhDongBaoGia({ duoc_dong_y: true, duoc_sua_so_luong: true }),
    ['dong_y', 'tu_choi', 'sua_so_luong'])
  assert.deepEqual(hanhDongBaoGia({ duoc_dong_y: true, duoc_sua_so_luong: false }),
    ['dong_y', 'tu_choi'])
  assert.deepEqual(hanhDongBaoGia({ duoc_dong_y: false }), [])
  assert.deepEqual(hanhDongBaoGia(null), [])
})

test('chỉ gửi dòng có số lượng thật sự đổi và hợp lệ', () => {
  const items = [{ name: 'a', qty: 10 }, { name: 'b', qty: 20 }, { name: 'c', qty: 5 }]
  assert.deepEqual(dongDaSua(items, { a: 10, b: 40, c: '' }), [{ name: 'b', qty: 40 }])
  assert.deepEqual(dongDaSua(items, {}), [])
})
```

- [ ] **Step 2: Chạy, xác nhận hỏng**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal/frontend && yarn -s test 2>&1 | tail -8`
Expected: FAIL — `Cannot find module … bao-gia.js`.

- [ ] **Step 3: Viết module JS**

`frontend/src/bao-gia.js`:

```js
// Tab "Yêu cầu báo giá" (spec 2026-10-12 §6). JS thuần để test được bằng
// `node --test`; view chỉ vẽ theo những gì module này trả.
//
// Khoá nhóm KHÁC khoá giai đoạn của tab Đơn hàng (`GIAI_DOAN` ở format.js) và
// không được nhập vào đó: hai tab là hai vòng đời.

export const NHOM_BAO_GIA = ['nhap', 'dang_bao_gia', 'cho_dong_y', 'da_dong_y', 'da_dong']

// Hai nhãn giữa nói rõ việc đang ở phía ai. Nhãn "Chờ báo giá" từng bị đọc
// ngược (khách tưởng mình đang chờ trong khi việc ở phía họ) nên không dùng.
const NHAN = {
  nhap: 'Nháp / chờ duyệt nội bộ',
  dang_bao_gia: 'Miyano đang báo giá',
  cho_dong_y: 'Chờ anh/chị đồng ý',
  da_dong_y: 'Đã đồng ý',
  da_dong: 'Đã đóng',
}

const BADGE = {
  nhap: 'b-gray', dang_bao_gia: 'b-blue', cho_dong_y: 'b-orange',
  da_dong_y: 'b-green', da_dong: 'b-red',
}

export function nhanNhomBaoGia(khoa) { return NHAN[khoa] || khoa || '' }
export function nhomBaoGiaBadge(khoa) { return BADGE[khoa] || 'b-gray' }

export function khoaNhomBaoGia(gt) {
  const s = String(gt || '')
  return NHOM_BAO_GIA.includes(s) ? s : ''
}

// Phiếu chưa có Quotation (nháp, chờ duyệt nội bộ) mở màn chi tiết phiếu đang
// có: việc gửi duyệt / duyệt vẫn nằm ở đó.
export function dichDongBaoGia(dong) {
  if (dong.bao_gia) return { name: 'bao-gia-detail', params: { ten: dong.bao_gia } }
  return { name: 'de-xuat-detail', params: { ten: dong.de_xuat } }
}

export function hanhDongBaoGia(bg) {
  if (!bg || !bg.duoc_dong_y) return []
  const kq = ['dong_y', 'tu_choi']
  if (bg.duoc_sua_so_luong) kq.push('sua_so_luong')
  return kq
}

export function dongDaSua(items, soLuongMoi) {
  const kq = []
  for (const it of items || []) {
    const moi = Number(soLuongMoi?.[it.name])
    if (!Number.isFinite(moi) || moi <= 0 || moi === Number(it.qty)) continue
    kq.push({ name: it.name, qty: moi })
  }
  return kq
}
```

- [ ] **Step 4: Chạy, xác nhận qua**

Run: `yarn -s test 2>&1 | tail -8`
Expected: mọi test `pass`, `fail 0`.

- [ ] **Step 5: Viết test Python ghim phần nối dây**

`miyano_portal/tests/test_bao_gia_giao_dien.py`:

```python
"""Nối dây giao diện của tab "Yêu cầu báo giá" (spec 2026-10-12 §6)."""

import re
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import portal

SRC = Path(frappe.get_app_path("miyano_portal")).parent / "frontend" / "src"


def _doc(ten):
	return (SRC / ten).read_text()


class TestBaoGiaGiaoDien(FrappeTestCase):
	def test_hai_route(self):
		router = _doc("router.js")
		self.assertIn("path: '/yeu-cau-bao-gia', name: 'bao-gia'", router)
		self.assertIn("path: '/yeu-cau-bao-gia/:ten', name: 'bao-gia-detail'", router)

	def test_muc_nav_sang_o_ca_hai_tab(self):
		app = _doc("App.vue")
		self.assertIn("name === 'bao-gia'", app)
		self.assertIn("name === 'bao-gia-detail'", app)

	def test_ca_hai_man_danh_sach_co_dai_tab(self):
		for ten in ("views/YeuCauList.vue", "views/BaoGiaList.vue"):
			self.assertIn("<TabDonBaoGia", _doc(ten), ten)

	def test_nhom_cua_frontend_khop_backend(self):
		nguon = _doc("bao-gia.js")
		khoa = re.search(r"NHOM_BAO_GIA = \[([^\]]+)\]", nguon).group(1)
		self.assertEqual(tuple(re.findall(r"'(\w+)'", khoa)), portal.NHOM_BAO_GIA)

	def test_khoa_nhom_khong_lot_vao_giai_doan(self):
		khoi = re.search(r"export const GIAI_DOAN = \[([^\]]+)\]", _doc("format.js")).group(1)
		for khoa in ("dang_bao_gia", "cho_dong_y", "da_dong"):
			self.assertNotIn(khoa, khoi)

	def test_endpoint_frontend_goi_deu_ton_tai(self):
		for ten in ("views/BaoGiaList.vue", "views/ChiTietBaoGia.vue",
		            "components/TabDonBaoGia.vue"):
			for ham in re.findall(r"api\.call\(\s*['\"](\w+)['\"]", _doc(ten)):
				self.assertTrue(callable(getattr(portal, ham, None)), f"{ten}: {ham}")

	def test_chi_tiet_khong_ve_gia_khi_server_giau(self):
		nguon = _doc("views/ChiTietBaoGia.vue")
		self.assertIn("bg.hien_gia", nguon)
		self.assertIn("quotation=", nguon)

	def test_su_kien_nhat_ky_moi_co_nhan(self):
		fmt = _doc("format.js")
		for khoa in ("bao_gia_tao", "bao_gia_het_han"):
			self.assertIn(f"{khoa}:", fmt)

	def test_dashboard_co_the_bao_gia(self):
		self.assertIn("bao_gia_cho_dong_y", _doc("views/Dashboard.vue"))
```

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_giao_dien`
Expected: FAIL — `test_nhom_cua_frontend_khop_backend` qua, các test còn lại hỏng (`AssertionError` / `FileNotFoundError`).

- [ ] **Step 6: Dải hai tab**

`frontend/src/components/TabDonBaoGia.vue`:

```vue
<script setup>
// Dải hai tab của màn "Danh sách đơn hàng" (spec 2026-10-12 §6.1): Đơn hàng
// và Yêu cầu báo giá là HAI danh sách, mỗi tab một route. Số trên tab báo giá
// là số báo giá đang chờ khách đồng ý.
import { ref, onMounted } from 'vue'
import api from '../api'

defineProps({ dang: { type: String, required: true } }) // 'don' | 'bao-gia'

const choDongY = ref(0)

onMounted(async () => {
  try {
    const res = await api.call('portal_bao_gia_dem')
    choDongY.value = res?.cho_dong_y || 0
  } catch (e) {
    // Số đếm là tiện ích: không tải được thì tab vẫn dùng được, chỉ thiếu số.
    console.warn('[TabDonBaoGia] không tải được số báo giá chờ đồng ý:', e)
  }
})
</script>

<template>
  <div class="tabs mb10">
    <router-link :to="{ name: 'yeu-cau' }" custom v-slot="{ navigate }">
      <button :class="{ on: dang === 'don' }" @click="navigate">Đơn hàng</button>
    </router-link>
    <router-link :to="{ name: 'bao-gia' }" custom v-slot="{ navigate }">
      <button :class="{ on: dang === 'bao-gia' }" @click="navigate">
        Yêu cầu báo giá
        <span v-if="choDongY" class="cartn">{{ choDongY }}</span>
      </button>
    </router-link>
  </div>
</template>
```

- [ ] **Step 7: Màn danh sách**

`frontend/src/views/BaoGiaList.vue`:

```vue
<script setup>
// Tab "Yêu cầu báo giá" (spec 2026-10-12 §6.2). Lọc nhóm và khoa ở SERVER,
// cắt trang ở SERVER — cùng lý do đã ghi ở YeuCauList.vue.
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { fmtVND, fmtDate } from '../format'
import { useIsMobile } from '../useMobile'
import { store } from '../store'
import PhanTrang from '../components/PhanTrang.vue'
import TabDonBaoGia from '../components/TabDonBaoGia.vue'
import {
  NHOM_BAO_GIA, nhanNhomBaoGia, nhomBaoGiaBadge, khoaNhomBaoGia, dichDongBaoGia,
} from '../bao-gia'

const route = useRoute()
const router = useRouter()
const isMobile = useIsMobile()

const loading = ref(true)
const error = ref('')
const rows = ref([])
const nhom = ref(khoaNhomBaoGia(route.query.nhom))
const khoaFilter = ref(String(route.query.khoa || ''))
const trang = ref(1)
const soDong = ref(20)
const tong = ref(0)
const khoaPhongList = ref([])

const NHOM = ['', ...NHOM_BAO_GIA]

// Cùng endpoint và cùng cách dựng ô lọc khoa với YeuCauList.vue.
function tenKhoa(ma) {
  if (!ma) return ''
  const k = khoaPhongList.value.find((x) => x.name === ma)
  return k ? k.ten_khoa_phong : ma
}
const khoaOptions = computed(() =>
  khoaPhongList.value
    .map((k) => ({ ma: k.name, ten: k.ten_khoa_phong || k.name }))
    .sort((a, b) => a.ten.localeCompare(b.ten, 'vi'))
)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.call('portal_bao_gia_danh_sach', {
      start: (trang.value - 1) * soDong.value,
      limit: soDong.value,
      nhom: nhom.value || undefined,
      khoa_phong: khoaFilter.value || undefined,
    })
    rows.value = res?.rows || []
    tong.value = res?.tong || 0
  } catch (e) {
    error.value = e.message || 'Không tải được danh sách yêu cầu báo giá.'
  } finally {
    loading.value = false
  }
}

watch([nhom, khoaFilter], () => {
  trang.value = 1
  router.replace({
    name: 'bao-gia',
    query: {
      ...(nhom.value ? { nhom: nhom.value } : {}),
      ...(khoaFilter.value ? { khoa: khoaFilter.value } : {}),
    },
  })
})
watch([trang, soDong, nhom, khoaFilter], load)
watch(() => route.query.nhom, (moi) => {
  const k = khoaNhomBaoGia(moi)
  if (k !== nhom.value) nhom.value = k
})

function mo(r) { router.push(dichDongBaoGia(r)) }

onMounted(async () => {
  try {
    khoaPhongList.value = await api.callKho('kho_khoa_phong_list_khach', { ca_inactive: 1 })
  } catch (e) {
    // Thiếu danh sách khoa thì cột khoa hiện mã thay cho tên; danh sách vẫn dùng được.
  }
  if (!store.me) {
    try { store.setMe(await api.call('portal_me')) } catch (e) { /* App.vue xử lý phiên hỏng */ }
  }
  load()
})
</script>

<template>
  <div>
    <div class="topbar" v-if="!isMobile">
      <div>
        <h2>Danh sách đơn hàng</h2>
        <div class="sub">Hàng chưa có giá hoặc chưa có mã — Miyano báo giá, quý vị đồng ý rồi mới thành đơn hàng</div>
      </div>
      <router-link :to="{ name: 'dat-hang' }"><button class="btn">+ Đặt hàng</button></router-link>
    </div>

    <TabDonBaoGia dang="bao-gia" />

    <div v-if="store.me?.la_quan_ly && khoaOptions.length" class="card mb10">
      <div class="field" style="margin-bottom: 0; max-width: 320px">
        <label>Khoa phòng</label>
        <select v-model="khoaFilter">
          <option value="">— Tất cả các khoa —</option>
          <option v-for="k in khoaOptions" :key="k.ma" :value="k.ma">{{ k.ten }}</option>
        </select>
      </div>
    </div>

    <div class="chips">
      <button v-for="n in NHOM" :key="n" class="chip" :class="{ on: nhom === n }" @click="nhom = n">
        {{ n ? nhanNhomBaoGia(n) : 'Tất cả' }}
      </button>
    </div>

    <div v-if="loading" class="empty">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <div v-else-if="!rows.length" class="empty">Chưa có yêu cầu báo giá nào ở nhóm này.</div>

    <div v-else-if="!isMobile" class="card">
      <table>
        <thead>
          <tr>
            <th>Mã yêu cầu</th><th>Khoa phòng</th><th>Ngày gửi</th>
            <th class="right">Giá trị báo giá</th><th>Hiệu lực đến</th><th>Tình trạng</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.de_xuat" class="clickable" @click="mo(r)">
            <td>
              <b>{{ r.ma || '(chưa gửi duyệt)' }}</b>
              <div v-if="r.ten_don_hang" class="sub">{{ r.ten_don_hang }}</div>
            </td>
            <td>{{ tenKhoa(r.khoa_phong) }}</td>
            <td>{{ fmtDate(r.thoi_diem) }}</td>
            <td class="right">{{ r.grand_total === null ? '—' : fmtVND(r.grand_total) }}</td>
            <td>{{ r.han_hieu_luc ? fmtDate(r.han_hieu_luc) : '—' }}</td>
            <td>
              <span class="badge" :class="nhomBaoGiaBadge(r.nhom)">{{ nhanNhomBaoGia(r.nhom) }}</span>
              <div class="sub">{{ r.trang_thai_bao_gia || r.trang_thai_phieu }}</div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-else>
      <div v-for="r in rows" :key="r.de_xuat" class="card mb10 clickable" @click="mo(r)">
        <div class="rowline">
          <b>{{ r.ma || '(chưa gửi duyệt)' }}</b>
          <span class="badge" :class="nhomBaoGiaBadge(r.nhom)">{{ nhanNhomBaoGia(r.nhom) }}</span>
        </div>
        <div v-if="r.ten_don_hang" class="sub">{{ r.ten_don_hang }}</div>
        <div class="sub">
          {{ tenKhoa(r.khoa_phong) }} · {{ fmtDate(r.thoi_diem) }}
          <template v-if="r.grand_total !== null"> · {{ fmtVND(r.grand_total) }}</template>
          <template v-if="r.han_hieu_luc"> · hiệu lực đến {{ fmtDate(r.han_hieu_luc) }}</template>
        </div>
      </div>
    </div>

    <PhanTrang v-if="!loading && !error" v-model:trang="trang" v-model:so-dong="soDong" :tong="tong" />
  </div>
</template>
```

Test `test_endpoint_frontend_goi_deu_ton_tai` chỉ soi `api.call(...)`; `api.callKho('kho_khoa_phong_list_khach')` là endpoint kho có sẵn, YeuCauList.vue đang gọi đúng như vậy.

- [ ] **Step 8: Màn chi tiết**

`frontend/src/views/ChiTietBaoGia.vue`:

```vue
<script setup>
// Chi tiết một yêu cầu báo giá (spec 2026-10-12 §6.3). Server quyết định khách
// được thấy gì và làm gì (`hien_gia`, `duoc_dong_y`, `duoc_sua_so_luong`); màn
// này không tự suy từ trạng thái.
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'
import { fmtVND, fmtDate } from '../format'
import { showToast } from '../toast'
import { nhanNhomBaoGia, nhomBaoGiaBadge, hanhDongBaoGia, dongDaSua } from '../bao-gia'
import ReasonModal from '../components/ReasonModal.vue'
import KhoiDongThoiGian from '../components/chi-tiet/KhoiDongThoiGian.vue'

const route = useRoute()

const loading = ref(true)
const error = ref('')
const bg = ref(null)
const nhatKy = ref([])
const dangTaiNhatKy = ref(false)
const dangChay = ref('')
const moTuChoi = ref(false)
const dangSua = ref(false)
const soLuongMoi = ref({})

const hanhDong = computed(() => hanhDongBaoGia(bg.value))
const dongChuaKhop = computed(() => (bg.value?.dat_ngoai || []).filter((d) => !d.da_xu_ly))
const pdfUrl = computed(() =>
  `/api/method/miyano_portal.api.portal.portal_bao_gia_pdf?quotation=${encodeURIComponent(bg.value?.bao_gia || '')}`)

async function load() {
  loading.value = true
  error.value = ''
  try {
    bg.value = await api.call('portal_bao_gia_chi_tiet', { ten: route.params.ten })
    soLuongMoi.value = Object.fromEntries(bg.value.items.map((it) => [it.name, it.qty]))
    dangSua.value = false
    napNhatKy()
  } catch (e) {
    bg.value = null
    error.value = e.message || 'Không tải được yêu cầu báo giá.'
  } finally {
    loading.value = false
  }
}

async function napNhatKy() {
  if (!bg.value?.de_xuat) { nhatKy.value = []; return }
  dangTaiNhatKy.value = true
  try {
    nhatKy.value = (await api.call('portal_nhat_ky_yeu_cau', { de_xuat: bg.value.de_xuat })) || []
  } catch (e) {
    console.warn('[ChiTietBaoGia] không tải được nhật ký:', e)
    nhatKy.value = []
  } finally {
    dangTaiNhatKy.value = false
  }
}

async function chay(ten, viec, thanhCong) {
  dangChay.value = ten
  try {
    await viec()
    showToast(thanhCong)
    await load()
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

function tuChoi(lyDo) {
  moTuChoi.value = false
  return chay(
    'tu_choi',
    () => api.call('portal_bao_gia_tu_choi', { ten: bg.value.bao_gia, ly_do: lyDo || undefined }),
    'Đã từ chối báo giá.',
  )
}

function guiSuaSoLuong() {
  const dong = dongDaSua(bg.value.items, soLuongMoi.value)
  if (!dong.length) return showToast('Chưa sửa số lượng dòng nào.', 'error')
  return chay(
    'sua_so_luong',
    () => api.call('portal_bao_gia_sua_so_luong', { ten: bg.value.bao_gia, dong: JSON.stringify(dong) }),
    'Đã gửi lại — Miyano sẽ xem lại giá theo số lượng mới.',
  )
}

watch(() => route.params.ten, (moi) => { if (moi && route.name === 'bao-gia-detail') load() })
onMounted(load)
</script>

<template>
  <div>
    <router-link :to="{ name: 'bao-gia' }" class="sub">← Quay lại</router-link>

    <div v-if="loading" class="empty">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>

    <template v-else-if="bg">
      <div class="card mb10">
        <div class="rowline">
          <h3 style="margin: 0">{{ bg.ma || bg.bao_gia }}</h3>
          <span class="badge" :class="nhomBaoGiaBadge(bg.nhom)">{{ nhanNhomBaoGia(bg.nhom) }}</span>
        </div>
        <div v-if="bg.ten_don_hang" class="sub">{{ bg.ten_don_hang }}</div>
        <div class="sub">
          Yêu cầu báo giá {{ bg.bao_gia }} · gửi ngày {{ fmtDate(bg.ngay_tao) }}
          <template v-if="bg.han_hieu_luc"> · hiệu lực đến <b>{{ fmtDate(bg.han_hieu_luc) }}</b></template>
        </div>
        <p v-if="bg.het_han" class="tag" style="margin-top: 6px">
          Báo giá đã quá hạn hiệu lực. Gửi yêu cầu báo giá mới nếu vẫn cần hàng.
        </p>
        <p v-if="bg.ly_do_tu_choi" class="sub" style="margin-top: 6px">Lý do từ chối: {{ bg.ly_do_tu_choi }}</p>
        <p v-if="bg.sales_order" style="margin-top: 6px">
          <router-link :to="{ name: 'order-detail', params: { name: bg.sales_order } }">
            Xem đơn hàng {{ bg.sales_order }} →
          </router-link>
        </p>
        <p v-else-if="bg.de_xuat" class="sub" style="margin-top: 6px">
          <router-link :to="{ name: 'de-xuat-detail', params: { ten: bg.de_xuat } }">Xem phiếu đề xuất gốc</router-link>
        </p>
      </div>

      <div v-if="hanhDong.length" class="card mb10">
        <h4 style="margin-top: 0">Việc đang chờ bạn</h4>
        <p class="sub">Bấm <b>Đồng ý</b> = chấp nhận đặt hàng theo giá dưới đây. Hệ thống ghi lại người bấm và thời điểm.</p>
        <div class="rowline" style="gap: 8px; flex-wrap: wrap; justify-content: flex-start">
          <button class="btn-g" :disabled="!!dangChay" @click="dongY">
            {{ dangChay === 'dong_y' ? 'Đang gửi…' : '✔ Đồng ý báo giá' }}
          </button>
          <button class="btn-o" :disabled="!!dangChay" @click="moTuChoi = true">✕ Từ chối…</button>
          <button v-if="hanhDong.includes('sua_so_luong')" class="btn-o" :disabled="!!dangChay"
                  @click="dangSua = !dangSua">✎ Sửa số lượng</button>
          <a class="btn-o" :href="pdfUrl" target="_blank" rel="noopener">⬇ Tải báo giá (PDF)</a>
        </div>
      </div>
      <div v-else-if="bg.hien_gia" class="mb10">
        <a class="btn-o" :href="pdfUrl" target="_blank" rel="noopener">⬇ Tải báo giá (PDF)</a>
      </div>

      <div v-if="bg.nhom === 'dang_bao_gia'" class="card mb10">
        <span class="badge b-blue">Miyano đang báo giá</span>
        <span class="sub"> Đơn giá sẽ hiện khi Miyano gửi báo giá cho quý vị.</span>
      </div>

      <div class="card mb10">
        <h4 style="margin-top: 0">Mặt hàng</h4>
        <table>
          <thead>
            <tr>
              <th>Mặt hàng</th><th>ĐVT</th><th class="right">Số lượng</th>
              <th v-if="bg.hien_gia" class="right">Đơn giá</th>
              <th v-if="bg.hien_gia" class="right">Thành tiền</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="it in bg.items" :key="it.name">
              <td><b>{{ it.item_code }}</b><div class="sub">{{ it.item_name }}</div></td>
              <td>{{ it.uom }}</td>
              <td class="right">
                <input v-if="dangSua" v-model.number="soLuongMoi[it.name]" type="number" min="0"
                       step="any" style="width: 90px; text-align: right" />
                <template v-else>{{ it.qty }}</template>
              </td>
              <td v-if="bg.hien_gia" class="right">{{ fmtVND(it.rate) }}</td>
              <td v-if="bg.hien_gia" class="right">{{ fmtVND(it.amount) }}</td>
            </tr>
          </tbody>
        </table>
        <p v-if="bg.hien_gia" class="right" style="margin-bottom: 0">
          <b>Tổng cộng: {{ fmtVND(bg.tong_tien) }}</b>
        </p>
        <div v-if="dangSua" class="rowline" style="margin-top: 10px; justify-content: flex-start; gap: 8px">
          <button class="btn" :disabled="!!dangChay" @click="guiSuaSoLuong">
            {{ dangChay === 'sua_so_luong' ? 'Đang gửi…' : 'Gửi lại để báo giá' }}
          </button>
          <span class="sub">Miyano xem lại giá theo số lượng mới rồi gửi báo giá lại. Muốn bỏ hẳn thì từ chối báo giá.</span>
        </div>
      </div>

      <div v-if="dongChuaKhop.length" class="card mb10">
        <h4 style="margin-top: 0">Hàng quý vị mô tả — Miyano đang tìm mã</h4>
        <div v-for="(d, i) in dongChuaKhop" :key="i" class="rowline">
          <span>{{ d.ten_hang }}</span><span class="sub">{{ d.so_luong }} {{ d.dvt }}</span>
        </div>
      </div>

      <KhoiDongThoiGian :dong="nhatKy" :dang-tai="dangTaiNhatKy" />

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
    </template>
  </div>
</template>
```

`ReasonModal` chỉ chặn khi `value.trim().length < minLen`, nên `:min-len="0"` cho gửi ô trống: lý do từ chối là tuỳ chọn (spec §6.3).

- [ ] **Step 9: Nối route, nav, nhãn**

`frontend/src/router.js` — import hai view và thêm hai route ngay sau route `de-xuat-detail`:

```js
import BaoGiaList from './views/BaoGiaList.vue'
import ChiTietBaoGia from './views/ChiTietBaoGia.vue'
```

```js
  { path: '/yeu-cau-bao-gia', name: 'bao-gia', component: BaoGiaList, meta: { title: 'Yêu cầu báo giá' } },
  { path: '/yeu-cau-bao-gia/:ten', name: 'bao-gia-detail', component: ChiTietBaoGia, meta: { title: 'Chi tiết yêu cầu báo giá' } },
```

`frontend/src/App.vue`, hàm `isActive`, nhánh `key === 'yeu-cau'`:

```js
    return name === 'yeu-cau' || name === 'order-detail' || name === 'de-xuat-detail'
      || name === 'bao-gia' || name === 'bao-gia-detail'
```

`frontend/src/format.js` — thêm vào `NHAN_SU_KIEN`:

```js
  bao_gia_tao: 'Gửi yêu cầu báo giá cho Miyano',
  bao_gia_het_han: 'Báo giá hết hạn',
```

và vào bảng màu chấm của `mauChamSuKien` (cùng bảng đang có `miyano_bao_gia: 'miyano'`): `bao_gia_tao: 'benh-vien',` và `bao_gia_het_han: 'miyano',`.

- [ ] **Step 10: Bốn view đang có**

`views/YeuCauList.vue`: import `TabDonBaoGia from '../components/TabDonBaoGia.vue'` và đặt `<TabDonBaoGia dang="don" />` ngay TRƯỚC khối ô lọc khoa (trước chú thích `<!-- Ô lọc khoa — CHỈ quản lý.`). Không sửa gì khác trong file này.

`views/ChiTietYeuCau.vue`: trong thẻ đầu trang, ngay sau đoạn `<p v-if="phieu?.phieu_cung_lan_dat" …>…</p>`, thêm:

```html
        <p v-if="phieu?.bao_gia" style="margin-top: 4px">
          <router-link :to="{ name: 'bao-gia-detail', params: { ten: phieu.bao_gia } }">
            Xem yêu cầu báo giá {{ phieu.bao_gia }} →
          </router-link>
        </p>
```

`views/Dashboard.vue`: thêm `bao_gia_cho_dong_y: 0` vào giá trị khởi tạo của `kpi`, và một thẻ vào đầu `<div class="kpis">`:

```html
      <router-link :to="{ name: 'bao-gia', query: { nhom: 'cho_dong_y' } }" class="card kpi" style="text-decoration: none; color: inherit">
        <div class="n" style="color: var(--orange)">{{ kpi.bao_gia_cho_dong_y }}</div>
        <div class="t">Báo giá chờ đồng ý</div>
      </router-link>
```


`views/LapPhieu.vue`, sau lời gọi `portal_order_place`: giỏ có hàng chờ báo giá nay ra một yêu cầu báo giá, không ra "đơn chờ báo giá". Thay khối `if ((res.don || []).length === 2) {…}` và dòng `if (res.da_ton_tai) …` bằng:

```js
    const coBaoGia = (res.don || []).some((d) => d.bao_gia)
    if ((res.don || []).length === 2) {
      // Giỏ trộn ra MỘT đơn và MỘT yêu cầu báo giá: về danh sách đơn hàng,
      // tab bên cạnh đang mang huy hiệu của yêu cầu báo giá.
      showToast('Đã tạo 1 đơn đặt ngay và 1 yêu cầu báo giá.', 'success')
      router.push({ name: 'yeu-cau' })
      return
    }
    if (coBaoGia) {
      // Chỉ có hàng chưa có giá / chưa có mã: không có đơn nào để hiện màn
      // xác nhận đơn, sang thẳng yêu cầu báo giá vừa tạo.
      showToast('Đã gửi yêu cầu báo giá cho Miyano.', 'success')
      router.push({ name: 'bao-gia-detail', params: { ten: res.bao_gia } })
      return
    }
    if (res.da_ton_tai) showToast(`Đơn ${res.sales_order} đã được tạo trước đó.`)
```

Rồi rà mọi nơi còn đọc kết quả duyệt / đặt hàng như thể luôn có đơn: `grep -rn "sales_order" frontend/src/views/LapPhieu.vue frontend/src/views/ChiTietYeuCau.vue frontend/src/de-xuat-actions.js | grep -v "^.*//"`. Chỗ nào điều hướng tới `order-detail` bằng `sales_order` của một kết quả vừa nhận thì bọc `if (… .sales_order)`.

- [ ] **Step 11: Chạy test**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal/frontend && yarn -s test 2>&1 | tail -6 && cd /home/hoangvietyeuem/frappe-bench-yhct && for m in test_bao_gia_giao_dien test_de_xuat_action_registry test_yeu_cau_list test_giai_doan_khoa_va_nhan test_nhat_ky_giao_dien test_chi_tiet_gop test_huy_hieu_cho_bao_gia; do bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.$m 2>&1 | grep -E "^Ran |^OK|^FAILED"; done`
Expected: `fail 0`; bảy cặp `Ran …` / `OK`. `test_nhat_ky_giao_dien` có thể đòi mọi hằng `SK_*` có nhãn ở `format.js` — hai nhãn ở Step 9 là để qua nó.

- [ ] **Step 12: Build thử (chưa commit bundle)**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal/frontend && yarn -s build 2>&1 | tail -5 && git -C .. checkout -- miyano_portal/public/frontend`
Expected: `✓ built in …`, không lỗi biên dịch template. Bundle được trả về trạng thái cũ; Task 15 build và commit một lần.

- [ ] **Step 13: Commit**

```bash
git add frontend/src miyano_portal/tests/test_bao_gia_giao_dien.py
git commit -m "feat(portal): tab Yeu cau bao gia tren cong - danh sach, chi tiet, dong y, tu choi, sua so luong"
```

---

### Task 15: Kiểm tra toàn bộ, build, xem trên trình duyệt

**Files:**
- Modify: `miyano_portal/public/frontend/` (bundle)

- [ ] **Step 1: Bộ test đầy đủ, so với lỗi nền**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal 2>&1 | tee /tmp/cuoi.log | grep -E "^(ERROR|FAIL):" | sort > /tmp/cuoi-loi.txt; grep -E "^Ran |^OK|^FAILED" /tmp/cuoi.log; comm -13 /tmp/nen-loi.txt /tmp/cuoi-loi.txt`
Expected: lệnh `comm` không in dòng nào (không có lỗi mới so với Task 0). Có dòng nào thì đó là lỗi của kế hoạch này: sửa tới khi hết, không ghi thêm vào danh sách nền.

- [ ] **Step 2: Patch chạy lại được trên site**

Run: `bench --site erptest.local execute miyano_portal.patches.v1_42.bao_gia_quotation.execute && bench --site erptest.local execute miyano_portal.patches.v1_42.bao_gia_quotation.execute && bench --site erptest.local execute frappe.db.sql --args "['select name, document_type, is_active from tabWorkflow']"`
Expected: hai workflow, cả hai `is_active = 1`: `Sales Order - Client Portal` và `Quotation - Client Portal`.

- [ ] **Step 3: Ba test HTTP chạy thật**

Khởi động lại tiến trình web (để nạp `hooks.py` mới), rồi:

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_cach_ly 2>&1 | grep -E "skipped|^Ran |^OK|^FAILED"`
Expected: `Ran 14 tests` … `OK`, KHÔNG có chữ `skipped`.

- [ ] **Step 4: Build và commit bundle**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal/frontend && yarn -s test 2>&1 | tail -4 && yarn -s build 2>&1 | tail -3`
Expected: `fail 0`; `✓ built in …`.

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal
git add miyano_portal/public/frontend
git commit -m "feat(portal): build giao dien tab Yeu cau bao gia"
```

- [ ] **Step 5: Xem trên trình duyệt**

Các bước dưới tạo chứng từ THẬT trên `erptest.local` và có một bước Submit Quotation (khách bấm Đồng ý). Trước khi làm: báo chủ dự án và chờ đồng ý; chỉ dùng khách DEMO.

1. Cổng `http://192.168.61.129:8003/portal`, tài khoản quản lý của một khách DEMO. Đặt một giỏ gồm một mặt hàng có giá và một mặt hàng chưa có giá → thông báo "1 đơn đặt ngay và 1 yêu cầu báo giá"; tab "Yêu cầu báo giá" có một dòng ở "Miyano đang báo giá", mở ra KHÔNG thấy đơn giá.
2. Desk, workspace "Kho khách hàng" → lối tắt "Yêu cầu báo giá" → mở Quotation, điền đơn giá, bấm "Gửi khách duyệt". Thử bấm khi còn dòng giá 0: bị chặn với tên mặt hàng.
3. Cổng: tab có huy hiệu 1; mở báo giá thấy đơn giá, hạn hiệu lực, tải được PDF. Sửa số lượng → báo giá về "Miyano đang báo giá", Desk có thông báo.
4. Desk gửi lại; cổng bấm Đồng ý → sang được "Xem đơn hàng"; đơn ở tab Đơn hàng, loại "Theo báo giá", trạng thái chờ Miyano xác nhận. Desk: Item Price của khách có giá vừa đồng ý.
5. Cùng tài khoản cổng, mở thẳng `http://192.168.61.129:8003/quotations` → bị từ chối.
6. Tài khoản nhân viên khoa KHÁC khoa của báo giá: tab không có dòng đó.

Ghi lại kết quả từng bước trong thông điệp bàn giao. Bước nào không khớp là lỗi phải sửa trước khi báo xong.

- [ ] **Step 6: Việc để lại cho chủ dự án (không tự làm)**

Nêu trong thông điệp bàn giao:
- Trên site thật: chạy `bench migrate` (patch v1_42), rồi kiểm số Quotation có sẵn đã nhận trạng thái (Task 0 Step 5).
- `/orders` của ERPNext vẫn mở với tài khoản cổng có dòng `Portal User` (lỗ có từ trước, ngoài phạm vi).
- Nhân viên khoa chưa có đường "xin sửa số lượng" cho báo giá.
- Mã luồng `"Mua lẻ"` cũ còn nguyên; gỡ ở đợt riêng khi không còn đơn `"Mua lẻ"` nào mở.



