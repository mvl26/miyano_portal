# Cổng hai chế độ đặt hàng — Kế hoạch triển khai

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cổng khách hàng chỉ còn hai chế độ đặt hàng — Theo hợp đồng khung và Mua lẻ — trong đó Mua lẻ cho khách tìm toàn bộ danh mục Miyano, tự gõ vật tư chưa có mã, và nhận báo giá PDF từ Miyano.

**Architecture:** Không thêm doctype nào cho chứng từ. Đơn mua lẻ vẫn là `Sales Order` với `custom_loai_don = "Mua lẻ"`; hàng khách tự gõ nằm ở bảng con `custom_dat_ngoai` (`Sales Order Dat Ngoai Item`) đã có sẵn; báo giá đi qua máy trạng thái workflow đã có (`Chờ xác nhận → Gửi khách duyệt → Chờ khách đồng ý`). Doctype `Portal Item Request` được gỡ khỏi cổng nhưng giữ nguyên cho Miyano Desk.

**Tech Stack:** Frappe v15 + ERPNext, Python 3.12 · SPA Vue 3 (`frontend/`, build vào `public/frontend/`) · MariaDB · `FrappeTestCase`

**Spec:** `docs/superpowers/specs/2026-08-15-hai-che-do-dat-hang-bo-yeu-cau-hang-hoa-design.md`

**Nhánh:** `feature/mua-le-toan-danh-muc` (đã có, cây sạch tại `e77a2f8`)

## Global Constraints

Áp cho **mọi** task; không nhắc lại trong từng task.

- **Fieldname tiếng Việt KHÔNG DẤU** (`ten_hang`, `so_luong`); label tiếng Việt có dấu; DocType tiếng Anh. Không camelCase cho fieldname.
- **Giao diện toàn tiếng Việt**; tiền `1.234.567 ₫` không thập phân; ngày `dd/mm/yyyy`.
- **API chỉ là `@frappe.whitelist()` trong `miyano_portal/api/portal.py`** — không REST controller riêng, không route tự chế.
- **SPA gọi API bằng `fetch` + CSRF** qua `frontend/src/api.js`; `frappe.call` KHÔNG tồn tại trên trang web.
- **Mọi chốt nghiệp vụ ở server** (`validate` / `before_submit` / trong endpoint). Client chỉ báo lỗi sớm cho UX.
- **KHÔNG endpoint nào nhận `customer` từ client** — luôn suy từ phiên qua `get_portal_customer()`. `frappe.get_doc` KHÔNG tự kiểm quyền: endpoint nhận tên chứng từ từ client **bắt buộc** tự kiểm sở hữu.
- **Không có URL file công khai** — PDF đi qua endpoint kiểm phiên + sở hữu từng lần.
- **Patch idempotent**: `bench migrate` chạy lại nhiều lần không sinh trùng/lỗi. Mỗi patch mới phải thêm một dòng vào `miyano_portal/patches.txt`.
- **339 test hiện có phải giữ xanh** (trừ `test_e6_yeu_cau.py` bị xoá ở Task 1).
- **Không nới BR-R7**: hàng thuộc hợp đồng khung còn hiệu lực của khách không đặt lẻ được; server trả `417 thuoc_hdnt_hieu_luc`.
- **Không đổi fieldname/tham số API** chứa "hdnt" (`custom_hdnt`, `thuoc_hdnt`, `mode="hdnt"`). Chỉ đổi **chuỗi hiển thị**.

**Lệnh dùng suốt kế hoạch:**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_portal
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.<ten_module>
bench build --app miyano_portal
```

**Thứ tự bắt buộc:** Task 1–2 (gỡ) → Task 3–4 (sửa màn hỏng) → Task 5–7 (đặt ngoài) → Task 8 (bật mặc định) → Task 9 (báo giá) → Task 10–11 (đổi tên, tài liệu).

Hai ràng buộc thứ tự có lý do, đừng đảo:

- **Task 3 trước Task 6**: dựng tính năng mới trên một màn đang hỏng thì không phân biệt được lỗi mới với lỗi cũ.
- **Task 5 (server) trước Task 6 (UI)**: Task 6 mở nút Xác nhận cho giỏ chỉ có dòng tự nhập. Làm ngược lại thì giữa hai commit có một bản build cho khách bấm nút rồi nhận `"Giỏ hàng trống."` từ server.

Task 3 một mình đã làm **màn Mua lẻ chạy lại được** — xem được bằng mắt trên cổng trước khi phần còn lại xong.

---

### Task 1: Gỡ 6 endpoint "Yêu cầu hàng hoá" khỏi cổng

**Files:**
- Modify: `miyano_portal/api/portal.py:1645-2090` (xoá khối endpoint yêu cầu)
- Delete: `miyano_portal/tests/test_e6_yeu_cau.py`
- Create: `miyano_portal/tests/test_go_yeu_cau_khoi_cong.py`

**Interfaces:**
- Consumes: không
- Produces: `api/portal.py` không còn thuộc tính `portal_yeu_cau_list`, `portal_yeu_cau_detail`, `portal_yeu_cau_save`, `portal_yeu_cau_cancel`, `portal_yeu_cau_tra_loi`, `portal_yeu_cau_file`. Doctype `Portal Item Request` vẫn dùng được trên Desk.

- [ ] **Step 1: Viết test thất bại**

Tạo `miyano_portal/tests/test_go_yeu_cau_khoi_cong.py`:

```python
"""Spec 2026-08-15 §3.2 — "Yêu cầu hàng hoá" bị gỡ khỏi CỔNG, GIỮ cho Desk.

Hai nửa của một quyết định, nên nằm chung một file: nếu ai đó "dọn dẹp" nốt
doctype thì nửa dưới đỏ ngay, thay vì mất im lặng khả năng theo dõi nhu cầu
của back-office.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import portal

ENDPOINT_DA_GO = [
    "portal_yeu_cau_list",
    "portal_yeu_cau_detail",
    "portal_yeu_cau_save",
    "portal_yeu_cau_cancel",
    "portal_yeu_cau_tra_loi",
    "portal_yeu_cau_file",
]


class TestGoYeuCauKhoiCong(FrappeTestCase):
    def test_khong_con_endpoint_yeu_cau_tren_cong(self):
        con_sot = [ten for ten in ENDPOINT_DA_GO if hasattr(portal, ten)]
        self.assertEqual(
            con_sot, [],
            f"còn endpoint cổng chưa gỡ: {con_sot} — khách vẫn gọi được",
        )

    def test_doctype_van_con_cho_desk(self):
        """Cơ sở của quyết định "giữ cho Desk" — xoá doctype là đổi quyết
        định, không phải dọn dẹp."""
        self.assertTrue(
            frappe.db.exists("DocType", "Portal Item Request"),
            "doctype bị xoá — back-office mất công cụ theo dõi nhu cầu",
        )

    def test_nhan_vien_desk_van_co_quyen(self):
        perms = frappe.get_meta("Portal Item Request").permissions
        roles = {p.role for p in perms if p.read}
        for role in ("Sales Manager", "Sales User", "Purchase User"):
            self.assertIn(role, roles, f"{role} mất quyền đọc trên Desk")
```

- [ ] **Step 2: Chạy test — phải ĐỎ**

```bash
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_go_yeu_cau_khoi_cong
```

Kỳ vọng: `test_khong_con_endpoint_yeu_cau_tren_cong` FAIL, liệt kê đủ 6 tên. Hai test kia PASS ngay (doctype còn nguyên) — đó là chủ ý: chúng là lưới bảo vệ, không phải việc cần làm.

- [ ] **Step 3: Xoá 6 endpoint và hàm phụ trợ riêng của chúng**

Trong `miyano_portal/api/portal.py`, xoá nguyên khối từ comment mở đầu ở dòng ~1645 (`# E6/US-E6.3, US-E6.4 — Yêu cầu hàng hoá...`) đến hết `portal_yeu_cau_file` (~dòng 2090), gồm cả các hàm phụ trợ chỉ phục vụ khối này (hàm kiểm trùng gần đúng tên, hàm nạp doc theo quyền sở hữu ở dòng ~1899/1916).

Trước khi xoá, chạy để chắc không có ai ngoài khối đó gọi tới:

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal
grep -rn "portal_yeu_cau\|_yeu_cau_" miyano_portal/ --include="*.py" | grep -v "tests/test_e6_yeu_cau.py"
```

**Dọn import chết theo.** Bốn tên chỉ được dùng bên trong khối vừa xoá (đã kiểm: `sla_yeu_cau_gio` ở 1686/1970, `gio_lam_viec_troi_qua` ở 1695, `cong_gio_lam_viec` ở 1970, `bao_yeu_cau_moi` ở 1989 — tất cả nằm trong khối). Xoá nguyên dòng 25:

```python
from miyano_portal.portal_sla import cong_gio_lam_viec, gio_lam_viec_troi_qua, sla_yeu_cau_gio
```

Và bỏ `bao_yeu_cau_moi` khỏi dòng 26:

```python
from miyano_portal.portal_thong_bao import bao_thieu_gia, bao_yeu_cau_ho_tro_hddt
```

Kiểm lại sau khi xoá:

```bash
grep -n "sla_yeu_cau_gio\|cong_gio_lam_viec\|gio_lam_viec_troi_qua\|bao_yeu_cau_moi" miyano_portal/api/portal.py
```

Kỳ vọng: không còn kết quả nào. (Các hàm đó vẫn sống trong `portal_sla.py`/`portal_thong_bao.py` cho job Desk — chỉ `api/portal.py` thôi ngừng dùng.)

**GIỮ NGUYÊN, không đụng:** `portal_mua_le.cap_nhat_yeu_cau_goc` (sales vẫn lập đơn từ yêu cầu trên Desk), `permissions.yeu_cau_query`, `portal_sla.quet_yeu_cau_qua_han`, `portal_thong_bao.bao_yeu_cau_moi`, `demand_pipeline.py`, `hooks.py:153`, `hooks.py:192`, `hooks.py:359`.

- [ ] **Step 4: Xoá file test cũ**

```bash
git rm miyano_portal/tests/test_e6_yeu_cau.py
```

- [ ] **Step 5: Chạy lại — phải XANH**

```bash
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_go_yeu_cau_khoi_cong
bench --site erptest.local run-tests --app miyano_portal
```

Kỳ vọng: module mới 3/3 PASS. Toàn bộ suite xanh, tổng số test giảm đúng bằng số test trong `test_e6_yeu_cau.py`.

- [ ] **Step 6: Commit**

```bash
git add -A miyano_portal/api/portal.py miyano_portal/tests/
git commit -m "feat(portal): gỡ 6 endpoint Yêu cầu hàng hoá khỏi cổng, giữ doctype cho Desk"
```

---

### Task 2: Gỡ "Yêu cầu hàng hoá" khỏi SPA

**Files:**
- Modify: `frontend/src/App.vue:15,37,44`
- Modify: `frontend/src/router.js:22-23,32-33`
- Modify: `frontend/src/views/Profile.vue:107`
- Modify: `frontend/src/views/Catalog.vue` (import, 3 hàm, 2 nút, khối `<p>`, thẻ modal)
- Modify: `frontend/src/format.js:96-110` (xoá `yeuCauBadge`)
- Delete: `frontend/src/views/YeuCauList.vue`, `frontend/src/views/YeuCauDetail.vue`, `frontend/src/components/YeuCauModal.vue`

**Interfaces:**
- Consumes: Task 1 (endpoint đã biến mất — SPA gọi tới sẽ lỗi, nên phải gỡ ngay sau)
- Produces: SPA không còn route `/yeu-cau`; `Catalog.vue` không còn state `ycModalOpen`/`ycPrefill`

- [ ] **Step 1: Xoá ba file view/component**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal
git rm frontend/src/views/YeuCauList.vue frontend/src/views/YeuCauDetail.vue frontend/src/components/YeuCauModal.vue
```

- [ ] **Step 2: Gỡ khỏi `App.vue`**

Xoá dòng 15 khỏi mảng `NAV`:

```js
  { to: '/yeu-cau', icon: '📨', label: 'Yêu cầu hàng hoá', short: 'Yêu cầu', key: 'yeu-cau', newtag: true },
```

Xoá dòng 37 trong `isActive()`:

```js
  if (key === 'yeu-cau') return name === 'yeu-cau' || name === 'yeu-cau-detail'
```

Sửa dòng 44 — bỏ hai tên route đã chết:

```js
  if (key === 'profile') return name === 'profile' || name === 'invoices'
```

- [ ] **Step 3: Gỡ khỏi `router.js`**

Xoá hai dòng import (22–23) và hai route (32–33). Không thêm redirect từ `/yeu-cau` — route không còn thì `router` rơi về nhánh không khớp sẵn có; thêm redirect là giữ lại một khái niệm đã bỏ.

- [ ] **Step 4: Gỡ khỏi `Profile.vue` và `format.js`**

`Profile.vue:107` — xoá cả nút:

```html
<button class="btn-o" @click="router.push('/yeu-cau')">Xem yêu cầu hàng hoá →</button>
```

`format.js` — xoá hàm `yeuCauBadge` cùng comment của nó (dòng ~96–110). Kiểm không còn ai gọi:

```bash
grep -rn "yeuCauBadge" frontend/src
```

- [ ] **Step 5: Gỡ ba đường vào khỏi `Catalog.vue`**

Xoá dòng 9: `import YeuCauModal from '../components/YeuCauModal.vue'`

Xoá nguyên khối dòng ~233–255 (comment "Nối luồng E6 #1", `ycModalOpen`, `ycPrefill`, `moYeuCauKhongThay`, `moYeuCauBaoGia`, `onYcSaved`).

Trong template, xoá dòng 476 và 508 (hai nút "Yêu cầu báo giá →"), khối `<p>` "Không tìm thấy hàng cần mua?" ở dòng ~529–533, và thẻ `<YeuCauModal ... />` ở dòng 544.

**Lưu ý:** sau bước này hai nhánh `v-else-if="!it.co_gia"` (dòng 473 và 506) còn lại một `<td>`/`<div>` trống. **Đừng vá tạm** — Task 3 xoá hẳn cả hai nhánh đó. Ở bước này chỉ cần build không lỗi cú pháp.

- [ ] **Step 6: Build và kiểm không còn tham chiếu chết**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench build --app miyano_portal
cd apps/miyano_portal && grep -rn "YeuCau\|yeu-cau" frontend/src
```

Kỳ vọng: build thành công; `grep` không ra kết quả nào.

- [ ] **Step 7: Commit**

```bash
git add -A frontend/ miyano_portal/public/frontend/
git commit -m "feat(portal): gỡ màn Yêu cầu hàng hoá và 3 đường vào khỏi SPA"
```

---

### Task 3: Sửa màn Mua lẻ cho khớp back-end không giá

Đây là **sửa lỗi đang tồn tại**, không phải tính năng mới: `portal_catalog_ban_le` đã bỏ trả `gia_ban_le`/`co_gia`/`vat` từ commit `b938bea`, front-end chưa cập nhật.

**Files:**
- Modify: `frontend/src/views/Catalog.vue:190-204` (`addLe`), `:444-545` (template ngăn Mua lẻ)
- Modify: `frontend/src/store.js:86-96` (xoá 3 getter tiền)
- Modify: `frontend/src/views/Cart.vue` (ngăn Mua lẻ: bỏ cột tiền + khối tổng cộng)

**Interfaces:**
- Consumes: Task 2 (các nút "Yêu cầu báo giá" đã gỡ)
- Produces: `store.cartLe` mỗi dòng chỉ còn `{ item_code, item_name, uom, qty }` — **không còn `rate`, `vat_pct`**. `store.cartLeSubtotal`/`cartLeVat`/`cartLeTotal` không còn tồn tại.

- [ ] **Step 1: Kiểm chính xác endpoint trả gì**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal
sed -n '330,354p' miyano_portal/api/portal.py
```

Kỳ vọng đúng 7 khoá mỗi dòng: `item_code`, `ten`, `quy_cach`, `dvt`, `trang_thai_hang`, `thuoc_hdnt`, `san_sang_ban`. Ghi nhớ: **không có** `gia_ban_le`, `co_gia`, `vat`.

- [ ] **Step 2: Tìm hết chỗ front-end đọc trường đã chết**

```bash
grep -rn "gia_ban_le\|co_gia\|it\.vat\|cartLeTotal\|cartLeSubtotal\|cartLeVat" frontend/src
```

Danh sách này là đúng phạm vi phải sửa ở task này. Không sửa thiếu chỗ nào.

- [ ] **Step 3: Sửa `store.js` — bỏ ba getter tiền của ngăn lẻ**

Xoá dòng 86–96 (`cartLeSubtotal`, `cartLeVat`, `cartLeTotal`) và thay bằng comment giải thích:

```js
  // Spec 2026-08-15 §3.3 — ngăn Mua lẻ KHÔNG có tiền: `portal_catalog_ban_le`
  // không trả giá (mọi đơn mua lẻ đi qua báo giá của Miyano), nên không có gì
  // để cộng. Ba getter `cartLeSubtotal`/`cartLeVat`/`cartLeTotal` đã bị xoá —
  // đừng dựng lại: chúng chỉ cộng ra 0 ₫ và làm khách tưởng hàng miễn phí.
  // `cartCount` (đếm DÒNG, không đếm tiền) vẫn tính cả hai ngăn như cũ.
```

Sửa `addToCartLe` — bỏ `rate`/`vat_pct` khỏi hình dạng dòng lẻ:

```js
  addToCartLe(item, qty) {
    const c = this.cartLe[item.item_code]
    if (c) c.qty += qty
    // Dòng lẻ chỉ mang thông tin nhận dạng + số lượng. KHÔNG có `rate`.
    else this.cartLe[item.item_code] = {
      item_code: item.item_code,
      item_name: item.item_name,
      uom: item.uom,
      qty,
    }
  },
```

- [ ] **Step 4: Sửa `Catalog.vue` — hàm `addLe`**

Thay dòng 190–204:

```js
function addLe(it) {
  const qty = Math.max(1, parseInt(leQtys[it.item_code]) || 1)
  // §3.3 — KHÔNG truyền `rate`/`vat_pct`: endpoint không trả giá nữa.
  store.addToCartLe(
    { item_code: it.item_code, item_name: it.ten, uom: it.dvt },
    qty
  )
  showToast(`Đã thêm ${qty} ${it.dvt} · ${it.ten} vào giỏ mua lẻ`)
  leQtys[it.item_code] = 1
}
```

- [ ] **Step 5: Sửa `Catalog.vue` — bảng desktop ngăn Mua lẻ**

Thay `<thead>` (dòng 453–459) — bỏ cột giá:

```html
          <thead>
            <tr>
              <th>Mã</th><th>Tên / quy cách</th><th>ĐVT</th>
              <th>Tình trạng</th>
              <th style="width: 120px">Số lượng</th><th></th>
            </tr>
          </thead>
```

Thay toàn bộ `<tr v-for=...>` (dòng 461–490):

```html
            <tr v-for="it in leItems" :key="it.item_code" :style="it.thuoc_hdnt ? 'opacity:.6' : ''">
              <td><b>{{ it.item_code }}</b></td>
              <td>{{ it.ten }}<br /><span v-if="it.quy_cach" class="tag">{{ it.quy_cach }}</span></td>
              <td>{{ it.dvt }}</td>
              <template v-if="it.thuoc_hdnt">
                <td colspan="3">
                  <a href="#" @click.prevent="chuyenSangHdnt(it.item_code)">
                    <span class="badge b-blue">Có trong HĐNT — đặt ở chế độ Theo HĐNT</span>
                  </a>
                </td>
              </template>
              <template v-else-if="!it.san_sang_ban">
                <td colspan="3">
                  <span class="badge b-gray">Miyano đang cập nhật — vui lòng liên hệ</span>
                </td>
              </template>
              <template v-else>
                <td><span class="badge" :class="it.trang_thai_hang === 'Còn hàng' ? 'b-green' : 'b-gray'">{{ it.trang_thai_hang }}</span></td>
                <td>
                  <div class="step">
                    <button @click="leQtys[it.item_code] = Math.max(1, availableLeQty(it.item_code) - 1)">−</button>
                    <input v-model="leQtys[it.item_code]" inputmode="numeric" />
                    <button @click="leQtys[it.item_code] = availableLeQty(it.item_code) + 1">+</button>
                  </div>
                </td>
                <td><button class="btn btn-sm" @click="addLe(it)">+ Giỏ lẻ</button></td>
              </template>
            </tr>
```

Nhánh `!it.san_sang_ban` là **mới** — endpoint đã trả cờ này từ `b938bea` nhưng template chưa bao giờ dùng. Không có nó, khách điền hết giỏ rồi mới nhận lỗi cấu hình ở bước Xác nhận.

- [ ] **Step 6: Sửa `Catalog.vue` — thẻ mobile ngăn Mua lẻ**

Thay khối dòng 497–528:

```html
        <div v-for="it in leItems" :key="it.item_code" class="card item mb10" :style="it.thuoc_hdnt ? 'opacity:.6' : ''">
          <div class="nm">{{ it.item_code }} · {{ it.ten }}</div>
          <div class="tag" style="margin: 2px 0 6px">{{ it.quy_cach ? it.quy_cach + ' · ' : '' }}{{ it.dvt }}</div>

          <template v-if="it.thuoc_hdnt">
            <a href="#" @click.prevent="chuyenSangHdnt(it.item_code)">
              <span class="badge b-blue">Có trong HĐNT — đặt ở chế độ Theo HĐNT</span>
            </a>
          </template>
          <template v-else-if="!it.san_sang_ban">
            <div class="sb"><span class="badge b-gray">Miyano đang cập nhật — vui lòng liên hệ</span></div>
          </template>
          <template v-else>
            <div class="sb">
              <span class="badge" :class="it.trang_thai_hang === 'Còn hàng' ? 'b-green' : 'b-gray'">{{ it.trang_thai_hang }}</span>
            </div>
            <div class="sb" style="margin-top: 10px">
              <div class="step">
                <button @click="leQtys[it.item_code] = Math.max(1, availableLeQty(it.item_code) - 1)">−</button>
                <input v-model="leQtys[it.item_code]" inputmode="numeric" />
                <button @click="leQtys[it.item_code] = availableLeQty(it.item_code) + 1">+</button>
              </div>
              <button class="btn btn-sm" @click="addLe(it)">+ Thêm vào giỏ lẻ</button>
            </div>
          </template>
        </div>
```

- [ ] **Step 7: Sửa thanh giỏ nổi ở `Catalog.vue`**

Dòng ~537 đang hiện `store.cartTotal + store.cartLeTotal` — getter thứ hai vừa bị xoá. Thay bằng số dòng:

```html
      <button class="btn" @click="router.push('/cart')">
        <span>🧺 {{ store.cartCount }} mặt hàng</span>
        <span>Xem giỏ ›</span>
      </button>
```

- [ ] **Step 8: Sửa `Cart.vue` — bảng desktop ngăn Mua lẻ**

Thay `<thead>`/`<tbody>` của bảng ngăn Mua lẻ (dòng ~349–369):

```html
                  <thead>
                    <tr>
                      <th>MẶT HÀNG</th><th>ĐVT</th>
                      <th style="width: 120px">SL</th><th></th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="l in leLines" :key="l.item_code" :class="{ 'dong-loi': leMaLoi.has(l.item_code) }">
                      <td><b>{{ l.item_code }}</b> {{ l.item_name }}</td>
                      <td>{{ l.uom }}</td>
                      <td>
                        <div class="step">
                          <button @click="leStepDown(l.item_code, l.qty)">−</button>
                          <input :value="l.qty" @change="leQtyInput(l, $event)" inputmode="numeric" />
                          <button @click="leStepUp(l)">+</button>
                        </div>
                      </td>
                      <td><button class="btn-o btn-sm" style="color: var(--red); border-color: var(--red)" @click="store.removeFromCartLe(l.item_code)">✕</button></td>
                    </tr>
                  </tbody>
```

- [ ] **Step 9: Sửa `Cart.vue` — thẻ mobile ngăn Mua lẻ**

Thay khối `<template v-else>` của danh sách dòng lẻ (dòng ~372–389):

```html
              <template v-else>
                <div v-for="l in leLines" :key="l.item_code" class="card mb10" :class="{ 'dong-loi': leMaLoi.has(l.item_code) }">
                  <div class="sb">
                    <span><b>{{ l.item_code }}</b><br /><span style="font-size: 13px">{{ l.item_name }}</span></span>
                    <button class="btn-o btn-sm" style="color: var(--red); border-color: var(--red)" @click="store.removeFromCartLe(l.item_code)">✕</button>
                  </div>
                  <div class="tag" style="margin: 4px 0 8px">{{ l.uom }}</div>
                  <div class="sb">
                    <div class="step">
                      <button @click="leStepDown(l.item_code, l.qty)">−</button>
                      <input :value="l.qty" @change="leQtyInput(l, $event)" inputmode="numeric" />
                      <button @click="leStepUp(l)">+</button>
                    </div>
                  </div>
                </div>
              </template>
```

- [ ] **Step 10: Sửa `Cart.vue` — khối tổng cộng ngăn Mua lẻ**

Thay khối `<div class="card">` cuối cùng của ngăn lẻ (dòng ~410–417) — ba dòng tiền đọc getter vừa bị xoá:

```html
              <div class="card">
                <p class="tag">
                  Miyano sẽ báo giá sau khi tiếp nhận đơn. Bạn xác nhận giá trước khi đơn được giao.
                </p>
                <button class="btn" style="width: 100%; margin-top: 14px; background: var(--purple)" @click="leMoXacNhan">Xác nhận đặt đơn MUA LẺ →</button>
                <p class="tag" style="margin-top: 8px">Đơn ngoài HĐNT, không áp dụng hạn mức — Miyano sẽ xác nhận trước khi giao.</p>
              </div>
```

Sửa luôn dòng `<div class="note">` ở đầu ngăn lẻ (dòng ~337) — bỏ chữ "xác nhận giá và lượng" đang hứa nhầm:

```html
          <div class="note">
            Ngăn <b>Mua lẻ</b> — không thuộc HĐNT, không hạn mức. Miyano sẽ báo giá rồi
            bạn xác nhận trước khi giao. Đặt thành <b>đơn riêng</b>.
          </div>
```

`leConfirmOrder()` (dòng 132–165) **không đổi** ở task này — payload đã chỉ gửi `item_code` + `qty`. (Task 5 sẽ thêm `dat_ngoai`.)

Ngăn Theo HĐNT **không đụng gì**: ở đó giá đến từ hợp đồng và vẫn hiện đầy đủ.

- [ ] **Step 11: Build và kiểm sạch**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct && bench build --app miyano_portal
cd apps/miyano_portal && grep -rn "gia_ban_le\|co_gia\|it\.vat\|cartLeTotal\|cartLeSubtotal\|cartLeVat" frontend/src
```

Kỳ vọng: build thành công; `grep` **không ra kết quả nào**.

- [ ] **Step 12: Kiểm bằng mắt trên cổng**

Đăng nhập `http://192.168.61.129:8003/portal` bằng `bvbm@demo.miyano` / `Portal@123` → Đặt hàng → chuyển sang **Mua lẻ**.

Kỳ vọng: danh mục hiện mặt hàng **không có cột giá**, không còn dòng nào ghi "Chưa có giá lẻ", không còn nút "Yêu cầu báo giá". Thêm được vào giỏ lẻ; giỏ hiện số dòng, không hiện 0 ₫.

- [ ] **Step 13: Chạy toàn bộ test**

```bash
bench --site erptest.local run-tests --app miyano_portal
```

Kỳ vọng: xanh. (Test back-end không chạm front-end; bước này để chắc không có gì lây.)

- [ ] **Step 14: Commit**

```bash
git add -A frontend/ miyano_portal/public/frontend/
git commit -m "fix(portal): đồng bộ màn Mua lẻ với back-end không giá + dùng cờ san_sang_ban"
```

---

### Task 4: Phân trang và tìm kiếm server-side cho danh mục lẻ

`portal_catalog_ban_le` đã nhận `start`/`limit` và trả `tong` từ `b938bea`; `loadLe()` chưa dùng, nên khách chỉ thấy 50 mã đầu của **toàn bộ** danh mục Miyano mà không có dấu hiệu nào là còn nữa.

**Files:**
- Modify: `frontend/src/views/Catalog.vue:146-188` (`loadLe`), template ngăn Mua lẻ (thêm nút "Tải thêm")

**Interfaces:**
- Consumes: Task 3 (template ngăn Mua lẻ đã đúng hình dạng dữ liệu)
- Produces: `leTong` (ref số) — tổng số mã khớp tìm kiếm, dùng ở Task 5 để biết khi nào "không tìm thấy"

- [ ] **Step 1: Thêm state phân trang vào `Catalog.vue`**

Ngay dưới `const leQtys = reactive({})` (dòng 149):

```js
const leTong = ref(0)
const leStart = ref(0)
const LE_LIMIT = 50
const leConNua = computed(() => leItems.value.length < leTong.value)
```

- [ ] **Step 2: Sửa `loadLe()` nhận cờ nối trang**

```js
async function loadLe(noiTiep = false) {
  leLoading.value = true
  leError.value = ''
  try {
    // `noiTiep = false` (đổi từ khoá / vào ngăn) → nạp lại từ đầu.
    // `noiTiep = true` (bấm "Tải thêm") → nối vào cuối danh sách hiện có.
    if (!noiTiep) leStart.value = 0
    const res = await api.call('portal_catalog_ban_le', {
      tim_kiem: search.value.trim() || undefined,
      start: leStart.value,
      limit: LE_LIMIT,
    })
    const moi = res.items || []
    leItems.value = noiTiep ? [...leItems.value, ...moi] : moi
    leTong.value = res.tong || 0
    leStart.value = leItems.value.length
    leItems.value.forEach((it) => {
      if (!(it.item_code in leQtys)) leQtys[it.item_code] = 1
    })
  } catch (e) {
    if (e.name === 'PermissionError') {
      if (mode.value === 'le') mode.value = 'hd'
      leError.value = e.message || 'Đơn vị của bạn chưa được bật chế độ Mua lẻ.'
    } else {
      leError.value = e.message || 'Không tải được danh mục mua lẻ.'
    }
  } finally {
    leLoading.value = false
  }
}
```

- [ ] **Step 3: Thêm dòng đếm và nút "Tải thêm" vào template**

Ngay dưới bảng desktop và dưới danh sách thẻ mobile của ngăn Mua lẻ:

```html
      <p v-if="leItems.length" class="tag" style="margin-top: 10px">
        Đang hiện {{ leItems.length }} / {{ leTong }} mặt hàng
      </p>
      <button
        v-if="leConNua"
        class="btn-o"
        style="width: 100%; margin-top: 8px"
        :disabled="leLoading"
        @click="loadLe(true)"
      >{{ leLoading ? 'Đang tải…' : 'Tải thêm' }}</button>
```

- [ ] **Step 4: Build và kiểm trên cổng**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct && bench build --app miyano_portal
```

Vào ngăn Mua lẻ. Kỳ vọng: dòng "Đang hiện 50 / N mặt hàng" với N là tổng thật; bấm "Tải thêm" nối thêm 50 dòng nữa và số bên trái tăng; gõ từ khoá thì danh sách **nạp lại từ đầu** (không nối vào kết quả cũ) và `N` đổi theo.

- [ ] **Step 5: Commit**

```bash
git add -A frontend/ miyano_portal/public/frontend/
git commit -m "feat(portal): phân trang server-side cho danh mục mua lẻ"
```

---

### Task 5: Item giữ chỗ cho đơn toàn hàng chưa có mã

**Files:**
- Create: `miyano_portal/patches/v1_15/__init__.py`, `miyano_portal/patches/v1_15/create_item_giu_cho_dat_ngoai.py`
- Modify: `miyano_portal/patches.txt`
- Modify: `miyano_portal/portal_mua_le.py` (thêm hằng + hàm)
- Modify: `miyano_portal/api/portal.py` (`portal_order_place` nhánh `ban_le`)
- Create: `miyano_portal/tests/test_dat_ngoai_giu_cho.py`

**Interfaces:**
- Consumes: không (test gọi thẳng `portal.portal_order_place` bằng Python — **không** cần UI của Task 6)
- Produces: `portal_mua_le.ITEM_GIU_CHO` (str = `"HANG-DAT-NGOAI"`), `portal_mua_le.can_chen_giu_cho(items, dat_ngoai) -> bool`, `portal_mua_le.la_dong_giu_cho(item_code) -> bool`. Server chấp nhận đơn `items` rỗng khi có `dat_ngoai`.

**Vì sao task này đứng TRƯỚC phần UI:** nếu làm ngược lại, bản build sau Task-UI sẽ cho khách bấm "Xác nhận" trên giỏ chỉ có dòng tự nhập, còn server vẫn ném `"Giỏ hàng trống."` — một trạng thái hỏng ship ra giữa hai commit. Server mở đường trước, UI đi sau.

- [ ] **Step 1: Viết test thất bại**

Tạo `miyano_portal/tests/test_dat_ngoai_giu_cho.py`:

```python
"""Spec 2026-08-15 §3.4 — đơn mua lẻ TOÀN hàng chưa có mã.

ERPNext không lưu nổi Sales Order với `items` rỗng (đã kiểm thực nghiệm, ghi
ở api/portal.py:655). Item giữ chỗ `HANG-DAT-NGOAI` là lối ra — nhưng CHỈ khi
giỏ không còn mặt hàng thật nào: `resolve_ban_le_company()` GIAO tập company
của mọi mặt hàng trong giỏ, nên chèn vô điều kiện có thể làm RỖNG phép giao
và hỏng một đơn giỏ hỗn hợp vốn đang hợp lệ.
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import portal
from miyano_portal.portal_mua_le import ITEM_GIU_CHO
from miyano_portal.tests.test_e6_mua_le import (
    BVBM, RETAIL_CO_GIA, USER_BVBM, _rid, _seed_mua_le,
)

DAT_NGOAI_MAU = [
    {"ten_hang": "Găng tay nitrile size M", "dvt": "Hộp", "so_luong": 5},
    {"ten_hang": "Dây truyền dịch", "dvt": "Cái", "so_luong": 20},
]


class TestDatNgoaiGiuCho(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _seed_mua_le()

    def setUp(self):
        frappe.set_user(USER_BVBM)
        frappe.db.set_value("Customer", BVBM, "custom_cho_phep_mua_le", 1)

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_don_toan_hang_chua_co_ma_van_dat_duoc(self):
        res = portal.portal_order_place(
            items=json.dumps([]),
            dat_ngoai=json.dumps(DAT_NGOAI_MAU),
            request_id=_rid(),
            mode="ban_le",
        )
        so = frappe.get_doc("Sales Order", res["sales_order"])
        self.assertEqual(
            [i.item_code for i in so.items], [ITEM_GIU_CHO],
            "đơn toàn hàng lạ phải có đúng MỘT dòng giữ chỗ",
        )
        self.assertEqual(len(so.custom_dat_ngoai), 2)

    def test_gio_hon_hop_KHONG_chen_dong_giu_cho(self):
        res = portal.portal_order_place(
            items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 2}]),
            dat_ngoai=json.dumps(DAT_NGOAI_MAU),
            request_id=_rid(),
            mode="ban_le",
        )
        so = frappe.get_doc("Sales Order", res["sales_order"])
        ma = [i.item_code for i in so.items]
        self.assertNotIn(
            ITEM_GIU_CHO, ma,
            "chèn giữ chỗ vào giỏ hỗn hợp sẽ thu hẹp resolve_ban_le_company()",
        )
        self.assertEqual(ma, [RETAIL_CO_GIA])

    def test_gio_rong_hoan_toan_van_bi_tu_choi(self):
        """Không hàng có mã, KHÔNG cả dòng đặt ngoài — không có nhu cầu nào
        để phục vụ, đơn rỗng là lỗi client chứ không phải tình huống nghiệp vụ."""
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_place(
                items=json.dumps([]),
                dat_ngoai=json.dumps([]),
                request_id=_rid(),
                mode="ban_le",
            )

    def test_khong_submit_duoc_khi_con_dong_chua_khop_ma(self):
        res = portal.portal_order_place(
            items=json.dumps([]),
            dat_ngoai=json.dumps(DAT_NGOAI_MAU),
            request_id=_rid(),
            mode="ban_le",
        )
        frappe.set_user("Administrator")
        so = frappe.get_doc("Sales Order", res["sales_order"])
        with self.assertRaises(frappe.ValidationError):
            so.submit()
```

- [ ] **Step 2: Chạy test — phải ĐỎ**

```bash
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_dat_ngoai_giu_cho
```

Kỳ vọng: `ImportError: cannot import name 'ITEM_GIU_CHO'`.

- [ ] **Step 3: Thêm hằng và hàm quyết định vào `portal_mua_le.py`**

Cạnh `TRANG_THAI_CHO_KHACH` (dòng 15):

```python
# Spec 2026-08-15 §3.4 — mã kỹ thuật giữ chỗ cho đơn TOÀN hàng chưa có mã.
# Dựng bởi `patches/v1_15/create_item_giu_cho_dat_ngoai.py`.
ITEM_GIU_CHO = "HANG-DAT-NGOAI"
```

Thêm hàm (cạnh `kiem_dat_ngoai_da_xu_ly`):

```python
def la_dong_giu_cho(item_code) -> bool:
    """Dùng CHUNG bởi Python và Jinja (đăng ký trong `hooks.py::jinja`).

    Mẫu in "Miyano - Báo giá" phải lọc dòng giữ chỗ. Viết `{% if i.item_code
    != "HANG-DAT-NGOAI" %}` trong template là chép hằng số sang một nơi
    không ai grep tới: đổi `ITEM_GIU_CHO` thì template lặng lẽ hết lọc và
    khách nhận báo giá có một dòng kỹ thuật, không test nào đỏ.
    """
    return item_code == ITEM_GIU_CHO


def can_chen_giu_cho(items, dat_ngoai) -> bool:
    """CHỈ chèn `ITEM_GIU_CHO` khi giỏ không còn mặt hàng thật nào.

    Đây là ràng buộc cứng, không phải tối ưu. `resolve_ban_le_company()`
    GIAO tập company của MỌI mặt hàng trong giỏ (chỉ company nào khai
    `default_warehouse` cho đủ mọi mã mới hợp lệ). Chèn `ITEM_GIU_CHO` vào
    một giỏ hỗn hợp sẽ thu hẹp phép giao đó và có thể làm nó RỖNG — tức là
    làm hỏng một đơn vốn đang đặt được, vì một dòng khách không hề yêu cầu.

    Giỏ rỗng hoàn toàn (không hàng thật, không dòng đặt ngoài) trả False:
    không có nhu cầu nào để phục vụ, để `portal_order_place` từ chối như cũ.
    """
    return not items and bool(dat_ngoai)
```

- [ ] **Step 4: Tạo patch dựng Item giữ chỗ**

`miyano_portal/patches/v1_15/__init__.py` — file rỗng.

`miyano_portal/patches/v1_15/create_item_giu_cho_dat_ngoai.py`:

```python
"""Spec 2026-08-15 §3.4 — Item kỹ thuật `HANG-DAT-NGOAI`.

`is_stock_item = 0`: mặt hàng này không bao giờ tồn tại trong kho, nó chỉ
giữ chỗ để ERPNext lưu được đơn (bảng `items` rỗng thì `Sales Order` crash ở
`accounts_controller.set_payment_schedule` — đã kiểm thực nghiệm).

Item Default với `default_warehouse` là BẮT BUỘC, không phải trang trí:
`portal_mua_le.resolve_ban_le_company()` chỉ nhận company nào có
`default_warehouse` khai cho mọi mặt hàng trong giỏ. Thiếu dòng này thì đơn
toàn hàng lạ bị từ chối vì "không xác định được công ty giao hàng" — đúng
thứ Item này sinh ra để tránh, hỏng vì một lý do khác.

Idempotent: chạy lại chỉ bổ sung phần còn thiếu, không sinh trùng.
"""

import frappe

# Một nguồn duy nhất cho mã này. Khai lại chuỗi ở đây thì patch và runtime
# có thể trỏ vào hai Item khác nhau sau một lần đổi tên, và không có gì báo.
from miyano_portal.portal_mua_le import ITEM_GIU_CHO as MA

TEN = "Hàng đặt ngoài (chờ Miyano khớp mã)"


def _nhom_item():
    return (
        frappe.db.get_value("Item Group", {"item_group_name": "Vật tư tiêu hao"}, "name")
        or frappe.db.get_value("Item Group", {"is_group": 0}, "name")
    )


def execute():
    company = frappe.defaults.get_global_default("company")
    if not company:
        company = frappe.db.get_value("Company", {}, "name")
    kho = frappe.db.get_value(
        "Warehouse", {"company": company, "is_group": 0}, "name"
    ) if company else None

    if not frappe.db.exists("Item", MA):
        doc = frappe.get_doc({
            "doctype": "Item",
            "item_code": MA,
            "item_name": TEN,
            "item_group": _nhom_item(),
            "stock_uom": "Cái",
            "is_stock_item": 0,
            "is_sales_item": 1,
            "is_purchase_item": 0,
            "description": TEN,
        })
        if company and kho:
            doc.append("item_defaults", {"company": company, "default_warehouse": kho})
        doc.insert(ignore_permissions=True)
        return

    doc = frappe.get_doc("Item", MA)
    thay_doi = False
    if doc.is_stock_item:
        doc.is_stock_item = 0
        thay_doi = True
    if company and kho and not any(
        d.company == company and d.default_warehouse for d in doc.item_defaults
    ):
        doc.append("item_defaults", {"company": company, "default_warehouse": kho})
        thay_doi = True
    if thay_doi:
        doc.save(ignore_permissions=True)
```

Thêm vào cuối `miyano_portal/patches.txt`:

```
miyano_portal.patches.v1_15.create_item_giu_cho_dat_ngoai
```

- [ ] **Step 5: Nới chốt "Giỏ hàng trống" trong `portal_order_place`**

`api/portal.py:788-795` hiện chặn mọi đơn `items` rỗng. Thay bằng:

```python
    if not items and not (mode == "ban_le" and dat_ngoai):
        # ERPNext không lưu được `Sales Order` với bảng `items` rỗng (xác
        # nhận thực nghiệm, xem docstring `_xay_don_ban_le`). Trước spec
        # 15/08 điều đó được dịch thẳng thành "phải có ít nhất một mặt hàng
        # thật" — nhưng khách cần TOÀN hàng Miyano chưa có mã thì không đặt
        # được gì cả, ngược nguyên tắc "khách đặt hàng, Miyano có trách
        # nhiệm gửi". §3.4: giỏ toàn dòng đặt ngoài đi tiếp, `_xay_don_ban_le`
        # chèn một dòng giữ chỗ để ERPNext lưu được đơn.
        #
        # Giỏ rỗng HOÀN TOÀN (không hàng thật, không dòng đặt ngoài) vẫn bị
        # từ chối: không có nhu cầu nào để phục vụ.
        frappe.throw("Giỏ hàng trống.")
```

- [ ] **Step 6: Chèn dòng giữ chỗ trong `_xay_don_ban_le`**

`aggregated` và `dong_dat_ngoai` chỉ cùng tồn tại **bên trong** `_xay_don_ban_le` (dòng 546–707) — `dong_dat_ngoai` được dựng ở ~619-650, `aggregated` là tham số. Chèn ngay **sau** vòng lặp dựng `dong_dat_ngoai` và **trước** dòng `company = resolve_ban_le_company(...)` (hiện ở dòng 662):

```python
    # §3.4 — đơn TOÀN hàng chưa có mã: chèn đúng MỘT dòng giữ chỗ để ERPNext
    # lưu được đơn. Phải đặt TRƯỚC `resolve_ban_le_company()` vì hàm đó suy
    # company từ chính `aggregated`. Xem `can_chen_giu_cho` để biết vì sao
    # điều kiện là "giỏ không còn hàng thật", không phải "có dòng đặt ngoài".
    if can_chen_giu_cho(aggregated, dong_dat_ngoai):
        if not frappe.db.exists("Item", ITEM_GIU_CHO):
            frappe.throw(
                "Hệ thống chưa sẵn sàng nhận đơn toàn hàng chưa có mã. "
                "Vui lòng liên hệ Miyano.",
                frappe.ValidationError,
            )
        aggregated[ITEM_GIU_CHO] = 1
```

Thêm hai tên vào khối import sẵn có ở `api/portal.py:15` (giữ thứ tự chữ cái):

```python
from miyano_portal.portal_mua_le import (
    ITEM_GIU_CHO,
    can_chen_giu_cho,
    cap_nhat_yeu_cau_goc,
    dam_bao_duoc_mua_le,
    ...
)
```

- [ ] **Step 7: Chạy migrate rồi chạy test — phải XANH**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_dat_ngoai_giu_cho
```

Kỳ vọng: 4/4 PASS.

- [ ] **Step 8: Chạy patch hai lần để chứng minh idempotent**

```bash
bench --site erptest.local execute miyano_portal.patches.v1_15.create_item_giu_cho_dat_ngoai.execute
bench --site erptest.local execute miyano_portal.patches.v1_15.create_item_giu_cho_dat_ngoai.execute
```

Kỳ vọng: cả hai lần chạy xong không lỗi. Kiểm không sinh Item Default trùng:

```bash
bench --site erptest.local console
```

```python
doc = frappe.get_doc("Item", "HANG-DAT-NGOAI")
print(doc.is_stock_item, [(d.company, d.default_warehouse) for d in doc.item_defaults])
```

Kỳ vọng: `0` và **đúng một** dòng Item Default.

- [ ] **Step 9: Chạy toàn bộ test**

```bash
bench --site erptest.local run-tests --app miyano_portal
```

- [ ] **Step 10: Commit**

```bash
git add -A miyano_portal/
git commit -m "feat(portal): Item giữ chỗ cho đơn mua lẻ toàn hàng chưa có mã"
```

---

### Task 6: Khối khách tự nhập "hàng chưa có trong kho, cần đặt ngoài"

Back-end đã sẵn sàng từ `b938bea`: bảng con `custom_dat_ngoai`, tham số `dat_ngoai` của `portal_order_place`, validate tên/ĐVT/số lượng. Task này dựng đường vào cho khách.

**Files:**
- Modify: `frontend/src/store.js` (thêm ngăn `cartDatNgoai`)
- Modify: `frontend/src/views/Catalog.vue` (khối nhập trong ngăn Mua lẻ)
- Modify: `frontend/src/views/Cart.vue` (hiện nhóm dòng đặt ngoài + gửi lên)

**Interfaces:**
- Consumes: Task 3, Task 4 (`leTong`), **Task 5** (server đã nhận đơn toàn dòng tự nhập — nếu chưa, nút Xác nhận sẽ ném `"Giỏ hàng trống."`)
- Produces: `store.cartDatNgoai` — **mảng** các `{ ten_hang, dvt, so_luong, ghi_chu }`; `store.themDongDatNgoai()`, `store.xoaDongDatNgoai(i)`, `store.clearDatNgoai()`, getter `store.datNgoaiHopLe`. `store.cartCount` cộng thêm độ dài mảng này.

- [ ] **Step 1: Thêm ngăn `cartDatNgoai` vào `store.js`**

Thêm vào object `store` (cạnh `cartLe`):

```js
  // Spec 2026-08-15 §3.4 — "hàng chưa có trong kho, cần đặt ngoài".
  //
  // MẢNG, không phải map theo `item_code` như hai ngăn kia: các dòng này
  // CHƯA CÓ MÃ. Hai dòng cùng tên hàng là hợp lệ (khách đặt hai quy cách
  // khác nhau mà chưa biết mã) — dùng map sẽ âm thầm nuốt mất dòng thứ hai.
  cartDatNgoai: [],
```

Và các thao tác (cạnh `clearCartLe`):

```js
  themDongDatNgoai(dong) {
    this.cartDatNgoai.push({
      ten_hang: dong?.ten_hang || '',
      dvt: dong?.dvt || '',
      so_luong: dong?.so_luong || 1,
      ghi_chu: dong?.ghi_chu || '',
    })
  },

  xoaDongDatNgoai(i) {
    this.cartDatNgoai.splice(i, 1)
  },

  clearDatNgoai() {
    this.cartDatNgoai = []
  },

  // Dòng hợp lệ để gửi lên server — server vẫn validate lại (NL: client chỉ
  // báo lỗi sớm), nhưng không gửi dòng rỗng khách bỏ trống là phép lịch sự
  // tối thiểu với endpoint.
  get datNgoaiHopLe() {
    return this.cartDatNgoai.filter(
      (d) => d.ten_hang.trim() && d.dvt.trim() && Number(d.so_luong) > 0
    )
  },
```

Sửa `cartCount`:

```js
  get cartCount() {
    return (
      Object.keys(this.cart).length +
      Object.keys(this.cartLe).length +
      this.cartDatNgoai.length
    )
  },
```

- [ ] **Step 2: Thêm khối nhập vào `Catalog.vue` — phần script**

```js
// §3.4 — khối "hàng chưa có trong kho, cần đặt ngoài". Mở sẵn khi tìm không
// ra kết quả: đúng chỗ và đúng ý định mà nút "Gửi yêu cầu cho Miyano" cũ
// phục vụ, nhưng ở lại trên chính phiếu mua thay vì đẩy sang chứng từ khác.
const dnMoKhoi = ref(false)

const timKhongRa = computed(
  () => mode.value === 'le' && !leLoading.value && !leError.value && leTong.value === 0
)

watch(timKhongRa, (khong) => {
  if (!khong) return
  dnMoKhoi.value = true
  if (!store.cartDatNgoai.length) {
    store.themDongDatNgoai({ ten_hang: search.value.trim() })
  }
})

function themDongTrong() {
  store.themDongDatNgoai({})
  dnMoKhoi.value = true
}
```

- [ ] **Step 3: Thêm khối nhập vào `Catalog.vue` — phần template**

Đặt ngay chỗ khối `<p>` "Không tìm thấy hàng cần mua?" cũ đứng (đã xoá ở Task 2), **bên trong** `<template v-else>` của ngăn Mua lẻ:

```html
      <div class="card" style="margin-top: 12px">
        <div class="sb" style="cursor: pointer" @click="dnMoKhoi = !dnMoKhoi">
          <b>Không tìm thấy vật tư cần mua?</b>
          <span>{{ dnMoKhoi ? '▾' : '▸' }}</span>
        </div>
        <p class="tag" style="margin: 4px 0 0">
          Ghi thẳng vào đây. Miyano sẽ tìm nguồn và báo giá cho bạn.
        </p>

        <template v-if="dnMoKhoi">
          <div v-for="(d, i) in store.cartDatNgoai" :key="i" class="card mb10" style="margin-top: 10px">
            <div class="field">
              <label>Tên hàng <span class="req">*</span></label>
              <input v-model="d.ten_hang" placeholder="VD: Găng tay nitrile không bột size M" />
            </div>
            <div class="sb" style="gap: 8px">
              <div class="field" style="flex: 1">
                <label>ĐVT <span class="req">*</span></label>
                <input v-model="d.dvt" placeholder="Hộp" />
              </div>
              <div class="field" style="flex: 1">
                <label>Số lượng <span class="req">*</span></label>
                <input v-model="d.so_luong" inputmode="numeric" />
              </div>
            </div>
            <div class="field">
              <label>Ghi chú</label>
              <input v-model="d.ghi_chu" placeholder="Quy cách, hãng mong muốn…" />
            </div>
            <button class="btn-o btn-sm" @click="store.xoaDongDatNgoai(i)">Xoá dòng</button>
          </div>

          <button class="btn-o" style="width: 100%" @click="themDongTrong">+ Thêm dòng</button>
        </template>
      </div>
```

- [ ] **Step 4: Hiện nhóm đặt ngoài ở `Cart.vue` — phần script**

Thêm cạnh `leLines`:

```js
// §3.4 — nhóm "hàng chưa có mã" nằm trong ngăn Mua lẻ, không phải một ngăn
// thứ ba trên UI: với khách đó vẫn là một phiếu mua lẻ.
const dnLines = computed(() => store.cartDatNgoai)
const leTrong = computed(() => leLines.value.length === 0 && store.datNgoaiHopLe.length === 0)
```

Sửa `leConfirmOrder()` — gửi thêm `dat_ngoai` và dọn ngăn khi xong:

```js
    const res = await api.call('portal_order_place', {
      items: JSON.stringify(itemsPayload),
      dat_ngoai: JSON.stringify(store.datNgoaiHopLe),
      po: lePo.value || null,
      delivery_date: leDeliveryDate.value || null,
      note: leNote.value || null,
      address: leAddress.value || null,
      request_id: store.requestIdLe,
      mode: 'ban_le',
    })
```

Trong nhánh thành công, thêm `store.clearDatNgoai()` ngay sau `store.clearCartLe()`.

- [ ] **Step 5: Hiện nhóm đặt ngoài ở `Cart.vue` — phần template**

Ngay dưới bảng hàng có mã của ngăn Mua lẻ:

```html
              <template v-if="dnLines.length">
                <h4 style="margin: 14px 0 6px">Hàng chưa có mã — Miyano sẽ tìm nguồn</h4>
                <div v-for="(d, i) in dnLines" :key="i" class="card mb10">
                  <div class="field">
                    <label>Tên hàng</label>
                    <input v-model="d.ten_hang" />
                  </div>
                  <div class="sb" style="gap: 8px">
                    <div class="field" style="flex: 1"><label>ĐVT</label><input v-model="d.dvt" /></div>
                    <div class="field" style="flex: 1"><label>Số lượng</label><input v-model="d.so_luong" inputmode="numeric" /></div>
                  </div>
                  <div class="field"><label>Ghi chú</label><input v-model="d.ghi_chu" /></div>
                  <button class="btn-o btn-sm" @click="store.xoaDongDatNgoai(i)">Xoá dòng</button>
                </div>
              </template>
```

**Đổi `leEmpty` → `leTrong` ở CẢ HAI chỗ dùng nó, không chỉ nút xác nhận:**

1. Dòng ~330: `<div v-else-if="leEmpty" class="card" ...>Ngăn Mua lẻ trống…</div>` → `v-else-if="leTrong"`.

   Đây là chỗ dễ sót và hỏng nặng nhất: `leEmpty` chỉ đếm dòng **có mã**, nên giỏ chỉ có dòng tự nhập vẫn tính là "trống" — cả khối `<template v-else>` bị ẩn, kể cả nhóm hàng khách vừa gõ. Khách gõ xong vào giỏ thấy "Ngăn Mua lẻ trống" và mất trắng những gì mình nhập.

2. Điều kiện disable nút "Xác nhận đặt đơn MUA LẺ" → `leTrong`. Giỏ chỉ có dòng đặt ngoài phải xác nhận được (Task 6 lo phần server).

Sửa xong kiểm:

```bash
grep -n "leEmpty" frontend/src/views/Cart.vue
```

Kỳ vọng: chỉ còn dòng khai báo `const leEmpty = ...`, hoặc không còn gì nếu bạn xoá luôn (không ai dùng nữa thì xoá).

- [ ] **Step 6: Build và kiểm trên cổng**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct && bench build --app miyano_portal
```

Kỳ vọng: gõ một từ khoá chắc chắn không có (`"zzzkhongtontai"`) → khối tự nhập **mở sẵn**, ô Tên hàng đã điền sẵn từ khoá đó. Thêm được nhiều dòng, xoá được. Vào giỏ thấy nhóm "Hàng chưa có mã". Đặt đơn kèm ít nhất một mặt hàng có mã → đơn tạo thành công.

- [ ] **Step 7: Kiểm dòng đặt ngoài đã vào đúng bảng con**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local console
```

```python
so = frappe.get_last_doc("Sales Order", filters={"custom_loai_don": "Mua lẻ"})
print(so.name, [(d.ten_hang, d.dvt, d.so_luong, d.da_xu_ly) for d in so.custom_dat_ngoai])
```

Kỳ vọng: đúng các dòng vừa gõ, `da_xu_ly = 0`.

- [ ] **Step 8: Commit**

```bash
git add -A frontend/ miyano_portal/public/frontend/
git commit -m "feat(portal): khối khách tự nhập hàng chưa có mã trên phiếu mua lẻ"
```

---

### Task 7: Hiện dòng đặt ngoài trên chi tiết đơn, giấu dòng giữ chỗ

**Files:**
- Modify: `miyano_portal/api/portal.py` (`portal_order_track` ~dòng 1105-1130)
- Modify: `frontend/src/views/OrderDetail.vue`
- Modify: `miyano_portal/tests/test_dat_ngoai_giu_cho.py` (thêm test)

**Interfaces:**
- Consumes: Task 5 (`ITEM_GIU_CHO`), Task 6 (có dòng đặt ngoài thật để hiện)
- Produces: `portal_order_track` trả thêm khoá `dat_ngoai` — list `{ ten_hang, dvt, so_luong, ghi_chu, da_xu_ly, item_khop }`; khoá `items` **không** chứa `ITEM_GIU_CHO`

- [ ] **Step 1: Viết test thất bại**

Thêm vào `miyano_portal/tests/test_dat_ngoai_giu_cho.py`:

```python
    def test_cong_khong_bao_gio_thay_dong_giu_cho(self):
        res = portal.portal_order_place(
            items=json.dumps([]),
            dat_ngoai=json.dumps(DAT_NGOAI_MAU),
            request_id=_rid(),
            mode="ban_le",
        )
        track = portal.portal_order_track(order=res["sales_order"])
        ma = [i["item_code"] for i in track["items"]]
        self.assertNotIn(
            ITEM_GIU_CHO, ma,
            "dòng giữ chỗ là chi tiết kỹ thuật nội bộ, không được lọt ra cổng",
        )
        self.assertEqual(len(track["dat_ngoai"]), 2)
        self.assertEqual(track["dat_ngoai"][0]["ten_hang"], DAT_NGOAI_MAU[0]["ten_hang"])
        self.assertFalse(track["dat_ngoai"][0]["da_xu_ly"])
```

- [ ] **Step 2: Chạy — phải ĐỎ**

```bash
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_dat_ngoai_giu_cho
```

Kỳ vọng: `KeyError: 'dat_ngoai'`.

- [ ] **Step 3: Sửa `portal_order_track`**

Thay khối `"items": [...]` trong dict trả về:

```python
        # §3.4 — LỌC dòng giữ chỗ khỏi phía khách. Khách không gõ ra nó,
        # không đặt nó, và nó không phải hàng: để nó lọt ra cổng là phơi một
        # chi tiết kỹ thuật nội bộ ra đúng chỗ nguyên tắc nền cấm.
        "items": [
            {"item_code": i.item_code,
             "item_name": i.item_name or frappe.db.get_value("Item", i.item_code, "item_name"),
             "qty": i.qty, "delivered_qty": i.delivered_qty,
             "rate": float(i.rate or 0), "uom": i.uom, "amount": float(i.amount or 0)}
            for i in so.items
            if i.item_code != ITEM_GIU_CHO
        ],
        # §3.4 — nhóm "hàng chưa có mã". `item_khop`/`da_xu_ly` để client
        # tách được dòng Miyano đã tìm ra nguồn khỏi dòng còn đang chờ.
        "dat_ngoai": [
            {"ten_hang": d.ten_hang, "dvt": d.dvt, "so_luong": float(d.so_luong or 0),
             "ghi_chu": d.ghi_chu or "", "da_xu_ly": bool(d.da_xu_ly),
             "item_khop": d.item_khop or ""}
            for d in (so.get("custom_dat_ngoai") or [])
        ],
```

- [ ] **Step 4: Chạy — phải XANH**

```bash
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_dat_ngoai_giu_cho
```

Kỳ vọng: 5/5 PASS.

- [ ] **Step 5: Hiện nhóm này trên `OrderDetail.vue`**

Ngay dưới bảng hàng của đơn:

```html
      <template v-if="(data.dat_ngoai || []).length">
        <h4 style="margin: 14px 0 6px">Đang chờ Miyano xác nhận nguồn</h4>
        <div class="card" style="padding: 0; overflow-x: auto">
          <table>
            <thead>
              <tr><th>Tên hàng</th><th>ĐVT</th><th class="right">SL</th><th>Tình trạng</th></tr>
            </thead>
            <tbody>
              <tr v-for="(d, i) in data.dat_ngoai" :key="i">
                <td>{{ d.ten_hang }}<br /><span v-if="d.ghi_chu" class="tag">{{ d.ghi_chu }}</span></td>
                <td>{{ d.dvt }}</td>
                <td class="right">{{ d.so_luong }}</td>
                <td>
                  <span v-if="d.da_xu_ly" class="badge b-green">Đã tìm được nguồn</span>
                  <span v-else class="badge b-gray">Miyano đang tìm nguồn</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
```

- [ ] **Step 6: Build và kiểm bằng mắt**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct && bench build --app miyano_portal
```

Mở chi tiết một đơn mua lẻ có dòng đặt ngoài. Kỳ vọng: thấy nhóm "Đang chờ Miyano xác nhận nguồn"; **không** thấy dòng nào tên `HANG-DAT-NGOAI`.

- [ ] **Step 7: Commit**

```bash
git add -A miyano_portal/ frontend/ 
git commit -m "feat(portal): chi tiết đơn hiện nhóm hàng chờ tìm nguồn, giấu dòng giữ chỗ"
```

---

### Task 8: Mua lẻ mặc định BẬT cho mọi khách

**Files:**
- Create: `miyano_portal/patches/v1_15/bat_mua_le_mac_dinh.py`
- Modify: `miyano_portal/patches.txt`
- Create: `miyano_portal/tests/test_mua_le_mac_dinh_bat.py`

**Interfaces:**
- Consumes: không
- Produces: `Customer.custom_cho_phep_mua_le` có `default = "1"`; mọi Customer hiện hữu đã bật

- [ ] **Step 1: Viết test thất bại**

```python
"""Spec 2026-08-15 §3.5 — Mua lẻ mặc định BẬT.

Bỏ "Yêu cầu hàng hoá" khỏi cổng nghĩa là khách chưa bật cờ KHÔNG CÒN cách nào
đặt hàng ngoài hợp đồng khung. Đổi mặc định là điều kiện để việc gỡ ở Task 1-2
không cắt đường của ai.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

TEN_KHACH_MOI = "Khách Test Mặc Định Mua Lẻ"


class TestMuaLeMacDinhBat(FrappeTestCase):
    def test_custom_field_co_default_bang_1(self):
        default = frappe.db.get_value(
            "Custom Field",
            {"dt": "Customer", "fieldname": "custom_cho_phep_mua_le"},
            "default",
        )
        self.assertEqual(str(default), "1", "đổi default là cốt lõi của §3.5")

    def test_khach_moi_tao_duoc_bat_san(self):
        if frappe.db.exists("Customer", TEN_KHACH_MOI):
            frappe.delete_doc("Customer", TEN_KHACH_MOI, force=True, ignore_permissions=True)
        kh = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": TEN_KHACH_MOI,
            "customer_type": "Company",
        }).insert(ignore_permissions=True)
        self.assertTrue(kh.custom_cho_phep_mua_le, "khách mới phải mua lẻ được ngay")

    def test_khong_con_khach_nao_bi_tat(self):
        con_tat = frappe.get_all(
            "Customer",
            filters={"custom_cho_phep_mua_le": 0, "disabled": 0},
            pluck="name",
        )
        self.assertEqual(con_tat, [], f"patch chưa bật cho khách hiện hữu: {con_tat}")
```

**Lưu ý cho người cài:** `test_e6_mua_le.py:105` cố ý đặt `PXN ABC` về `0` để kiểm chốt 403. Đó là fixture đặt trong `setUpClass` của module đó và `FrappeTestCase` rollback mỗi class, nên không ảnh hưởng test này. Nếu test thứ ba đỏ vì `PXN ABC`, nguyên nhân là thứ tự chạy — đọc lại `_seed_mua_le()` trước khi sửa test.

- [ ] **Step 2: Chạy — phải ĐỎ**

```bash
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_mua_le_mac_dinh_bat
```

- [ ] **Step 3: Viết patch**

`miyano_portal/patches/v1_15/bat_mua_le_mac_dinh.py`:

```python
"""Spec 2026-08-15 §3.5 — Mua lẻ mặc định BẬT.

Hai việc, thiếu một là hỏng nửa: đổi `default` (khách TẠO MỚI từ nay) và
UPDATE khách HIỆN HỮU (những người đã tồn tại trước patch).

KHÔNG bỏ chốt `dam_bao_duoc_mua_le()` ở server — cờ vẫn còn tác dụng, sales
vẫn tắt được cho một khách cụ thể (khách nợ quá hạn, chỉ cho mua theo hợp
đồng). Đây là đổi GIÁ TRỊ MẶC ĐỊNH, không phải bỏ cơ chế.

Idempotent: đặt `default` về đúng "1" (đã đúng thì không lưu lại) và chỉ
UPDATE các dòng đang là 0/NULL.
"""

import frappe

FIELD = {"dt": "Customer", "fieldname": "custom_cho_phep_mua_le"}


def execute():
    ten = frappe.db.get_value("Custom Field", FIELD, "name")
    if not ten:
        # Patch v1_8 chưa chạy — không có field để đổi mặc định.
        return

    if str(frappe.db.get_value("Custom Field", ten, "default") or "") != "1":
        frappe.db.set_value("Custom Field", ten, "default", "1")
        frappe.clear_cache(doctype="Customer")

    frappe.db.sql(
        """update `tabCustomer`
           set custom_cho_phep_mua_le = 1
           where ifnull(custom_cho_phep_mua_le, 0) = 0"""
    )
```

Thêm vào `miyano_portal/patches.txt`:

```
miyano_portal.patches.v1_15.bat_mua_le_mac_dinh
```

- [ ] **Step 4: Migrate rồi chạy — phải XANH**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_mua_le_mac_dinh_bat
```

Kỳ vọng: 3/3 PASS.

- [ ] **Step 5: Chứng minh chốt 403 vẫn còn**

```bash
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e6_mua_le
```

Kỳ vọng: xanh — trong đó có ca khách bị tắt cờ vẫn nhận 403 `khong_duoc_mua_le`. Đổi mặc định **không phải** bỏ chốt; test này là bằng chứng.

- [ ] **Step 6: Chạy toàn bộ test và commit**

```bash
bench --site erptest.local run-tests --app miyano_portal
cd apps/miyano_portal && git add -A miyano_portal/
git commit -m "feat(portal): mua lẻ mặc định BẬT cho mọi khách, giữ nguyên chốt 403"
```

---

### Task 9: PDF báo giá

**Files:**
- Modify: `miyano_portal/setup/install_print_formats.py` (thêm mẫu Báo giá)
- Modify: `miyano_portal/setup/install_notifications.py` (đính PDF vào Notification đã có)
- Create: `miyano_portal/patches/v1_15/install_print_format_bao_gia.py`
- Modify: `miyano_portal/patches.txt`
- Modify: `miyano_portal/api/portal.py` (endpoint `portal_bao_gia_pdf`)
- Modify: `frontend/src/views/OrderDetail.vue` (nút tải)
- Create: `miyano_portal/tests/test_bao_gia_pdf.py`

**Interfaces:**
- Consumes: Task 5 (`ITEM_GIU_CHO`, `la_dong_giu_cho`), Task 7 (nguyên tắc lọc dòng giữ chỗ)
- Produces: Print Format `"Miyano - Báo giá"` (doc_type `Sales Order`); endpoint `portal_bao_gia_pdf(order)` trả PDF qua `frappe.local.response`

- [ ] **Step 1: Viết test thất bại**

Tạo `miyano_portal/tests/test_bao_gia_pdf.py`:

```python
"""Spec 2026-08-15 §3.6 — PDF báo giá.

Ba thứ được bảo vệ ở đây, theo thứ tự quan trọng: KHÔNG lộ đơn của khách
khác; KHÔNG lộ giá sales chưa gửi; và bản báo giá phải ĐỦ — thiếu dòng đặt
ngoài đã khớp mã là khách nhận báo giá thiếu đúng món họ lo nhất.
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import portal
from miyano_portal.portal_mua_le import ITEM_GIU_CHO, TRANG_THAI_CHO_KHACH
from miyano_portal.tests.test_e6_mua_le import (
    BVBM, PXN, RETAIL_CO_GIA, USER_BVBM, USER_PXN, _rid, _seed_mua_le,
)

PRINT_FORMAT = "Miyano - Báo giá"


class TestBaoGiaPdf(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _seed_mua_le()

    def setUp(self):
        frappe.set_user(USER_BVBM)

    def tearDown(self):
        frappe.set_user("Administrator")

    def _don_cho_khach_dong_y(self):
        res = portal.portal_order_place(
            items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 3}]),
            dat_ngoai=json.dumps([
                {"ten_hang": "Găng tay nitrile size M", "dvt": "Hộp", "so_luong": 5},
            ]),
            request_id=_rid(),
            mode="ban_le",
        )
        frappe.set_user("Administrator")
        so = frappe.get_doc("Sales Order", res["sales_order"])
        so.items[0].rate = 25000
        # Khớp mã cho dòng đặt ngoài — đúng thao tác sales làm khi báo giá.
        so.custom_dat_ngoai[0].item_khop = RETAIL_CO_GIA
        so.workflow_state = TRANG_THAI_CHO_KHACH
        so.save(ignore_permissions=True)
        frappe.set_user(USER_BVBM)
        return so.name

    def test_print_format_da_duoc_cai(self):
        self.assertTrue(frappe.db.exists("Print Format", PRINT_FORMAT))
        self.assertEqual(
            frappe.db.get_value("Print Format", PRINT_FORMAT, "doc_type"), "Sales Order"
        )

    def test_pdf_chua_dong_dat_ngoai_da_khop_ma(self):
        ten = self._don_cho_khach_dong_y()
        html = frappe.get_print(
            "Sales Order", ten, print_format=PRINT_FORMAT, no_letterhead=1
        )
        self.assertIn("Găng tay nitrile size M", html)

    def test_pdf_khong_chua_dong_giu_cho(self):
        res = portal.portal_order_place(
            items=json.dumps([]),
            dat_ngoai=json.dumps([{"ten_hang": "Dây truyền dịch", "dvt": "Cái", "so_luong": 20}]),
            request_id=_rid(),
            mode="ban_le",
        )
        frappe.set_user("Administrator")
        html = frappe.get_print(
            "Sales Order", res["sales_order"], print_format=PRINT_FORMAT, no_letterhead=1
        )
        self.assertNotIn(ITEM_GIU_CHO, html)

    def test_khach_khac_khong_tai_duoc(self):
        ten = self._don_cho_khach_dong_y()
        frappe.set_user(USER_PXN)
        with self.assertRaises(frappe.PermissionError):
            portal.portal_bao_gia_pdf(order=ten)

    def test_don_chua_gui_khach_thi_khong_tai_duoc(self):
        """Đơn còn ở "Chờ xác nhận" = sales chưa chốt giá. Cho tải là lộ
        giá nháp và biến một con số đang sửa thành cam kết với khách."""
        res = portal.portal_order_place(
            items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 1}]),
            request_id=_rid(),
            mode="ban_le",
        )
        with self.assertRaises(frappe.ValidationError):
            portal.portal_bao_gia_pdf(order=res["sales_order"])
```

- [ ] **Step 2: Chạy — phải ĐỎ**

```bash
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_pdf
```

Kỳ vọng: `AttributeError: module ... has no attribute 'portal_bao_gia_pdf'` và Print Format chưa tồn tại.

- [ ] **Step 3: Thêm mẫu in vào `setup/install_print_formats.py`**

Thêm trước danh sách `FORMATS`:

```python
NAME_BG = "Miyano - Báo giá"
HTML_BG = """
<div class="print-heading"><h2>BÁO GIÁ / QUOTATION</h2></div>
<p><b>Khách hàng / Customer:</b> {{ doc.customer_name }}</p>
<p><b>Số đơn / Order No:</b> {{ doc.name }}
   &nbsp; <b>Ngày báo giá / Quotation Date:</b>
   {{ frappe.utils.formatdate(doc.custom_ngay_gui_khach_duyet or doc.transaction_date, "dd/mm/yyyy") }}</p>
<p><b>Hiệu lực đến / Valid Until:</b>
   {{ han_hieu_luc_bao_gia(doc).strftime('%d/%m/%Y') }}</p>
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
      <td class="text-right">{{ "{:,.0f}".format(i.rate) }} ₫</td>
      <td class="text-right">{{ "{:,.0f}".format(i.amount) }} ₫</td>
    </tr>
    {%- endif %}
  {% endfor %}
  </tbody>
</table>
{% set cho_nguon = doc.get("custom_dat_ngoai") | selectattr("da_xu_ly", "equalto", 0) | list %}
{% if cho_nguon %}
<h4>Hàng đang tìm nguồn / Items being sourced</h4>
<table class="table table-bordered">
  <thead><tr><th>Tên hàng / Item</th><th>ĐVT / UoM</th><th>SL / Qty</th></tr></thead>
  <tbody>
  {% for d in cho_nguon %}
    <tr><td>{{ d.ten_hang }}</td><td>{{ d.dvt }}</td>
        <td class="text-right">{{ d.so_luong }}</td></tr>
  {% endfor %}
  </tbody>
</table>
<p class="text-muted">Các mặt hàng trên chưa có trong báo giá; Miyano sẽ báo giá bổ sung sau khi tìm được nguồn.</p>
{% endif %}
<p class="text-right"><b>Tổng cộng / Total:</b> {{ "{:,.0f}".format(doc.grand_total) }} ₫</p>
"""
```

Thêm `(NAME_BG, "Sales Order", HTML_BG),` vào `FORMATS`.

**Vì sao dòng đã khớp mã lại nằm ở bảng TRÊN:** khi sales đặt `item_khop`, hook `dong_bo_da_xu_ly_dat_ngoai` bật `da_xu_ly = 1` và sales chuyển nó thành dòng hàng thật trong `doc.items` — nên nó đã có mặt ở bảng đầu, kèm giá. Bảng dưới chỉ liệt kê phần **chưa** xử lý, để khách biết món nào còn đang chờ.

**Đăng ký `la_dong_giu_cho` làm global Jinja.** `hooks.py:99` đã có khối `jinja` với `han_hieu_luc_bao_gia` (đã kiểm trên site: render ra `21/08/2026`, hoạt động thật). Thêm hàm thứ hai vào đúng khối đó:

```python
jinja = {
	"methods": [
		"miyano_portal.portal_mua_le.han_hieu_luc_bao_gia",
		# §3.6 — mẫu in "Miyano - Báo giá" lọc dòng giữ chỗ qua hàm này,
		# KHÔNG hardcode mã trong template (xem docstring của hàm).
		"miyano_portal.portal_mua_le.la_dong_giu_cho",
	],
}
```

- [ ] **Step 4: Đính PDF vào Notification đã có**

Trong `setup/install_notifications.py`, thêm hai khoá vào định nghĩa `"Portal - Báo giá sẵn sàng"` (dòng ~113):

```python
        "attach_print": 1,
        "print_format": "Miyano - Báo giá",
```

Và trong `install_portal_notifications()`, thêm vào dict `frappe.get_doc({...})`:

```python
            "attach_print": d.get("attach_print", 0),
            "print_format": d.get("print_format"),
```

- [ ] **Step 5: Patch cài mẫu in + cập nhật Notification đã tồn tại**

`miyano_portal/patches/v1_15/install_print_format_bao_gia.py`:

```python
"""Spec 2026-08-15 §3.6 — cài Print Format "Miyano - Báo giá" và đính nó vào
Notification "Portal - Báo giá sẵn sàng" đã cài từ v1_14.

Hai hàm cài đặt gốc đều BỎ QUA bản ghi đã tồn tại (`install_print_formats.py`
và `install_notifications.py` cùng khuôn "exists → continue"), nên Notification
cũ sẽ KHÔNG tự nhận `attach_print` — phải set thẳng ở đây.

Idempotent: `install_portal_print_formats()` tự bỏ qua mẫu đã có;
`frappe.db.set_value` ghi cùng giá trị nhiều lần là vô hại.
"""

import frappe

from miyano_portal.setup.install_print_formats import install_portal_print_formats

NOTI = "Portal - Báo giá sẵn sàng"
PF = "Miyano - Báo giá"


def execute():
    install_portal_print_formats()
    if frappe.db.exists("Notification", NOTI) and frappe.db.exists("Print Format", PF):
        frappe.db.set_value("Notification", NOTI, {"attach_print": 1, "print_format": PF})
```

Thêm vào `miyano_portal/patches.txt`:

```
miyano_portal.patches.v1_15.install_print_format_bao_gia
```

- [ ] **Step 6: Viết endpoint `portal_bao_gia_pdf`**

Trước tiên thêm `TRANG_THAI_CHO_KHACH` vào khối import ở `api/portal.py:15` — **hiện chưa có** (đã kiểm), endpoint dưới đây dùng tới:

```python
from miyano_portal.portal_mua_le import (
    ITEM_GIU_CHO,
    TRANG_THAI_CHO_KHACH,
    can_chen_giu_cho,
    ...
)
```

Rồi thêm endpoint, cạnh các endpoint tải chứng từ đã có:

```python
@frappe.whitelist()
def portal_bao_gia_pdf(order) -> None:
    """§3.6 — tải PDF báo giá của MỘT đơn mua lẻ.

    Cùng khuôn `kho_phieu_pdf`/`portal_einvoice_download` (Quyết định nền số
    8): trả file qua response, KHÔNG sinh URL công khai — người dùng cổng
    không dùng được `/printview`.

    `frappe.get_doc` KHÔNG tự kiểm quyền trong bản này, nên phải tự đối chiếu
    `customer` của đơn với khách suy từ PHIÊN (Quyết định nền số 7) — không
    nhận `customer` từ client dưới bất kỳ hình thức nào.
    """
    customer = get_portal_customer()
    so = frappe.db.get_value(
        "Sales Order", order,
        ["name", "customer", "workflow_state", "custom_loai_don"],
        as_dict=True,
    )
    if not so:
        frappe.throw("Không tìm thấy đơn hàng.", frappe.DoesNotExistError)
    if so.customer != customer:
        raise frappe.PermissionError("Đơn hàng này không thuộc đơn vị của bạn.")

    # Chỉ từ lúc báo giá ĐÃ GỬI cho khách trở đi. Trước đó `rate` là con số
    # sales đang sửa — cho tải là biến một bản nháp thành cam kết.
    if so.workflow_state not in (TRANG_THAI_CHO_KHACH, "Chờ Miyano xác nhận", "Đã xác nhận"):
        frappe.throw(
            "Báo giá cho đơn này chưa được gửi. Vui lòng đợi Miyano báo giá.",
            frappe.ValidationError,
        )

    pdf = frappe.get_print(
        "Sales Order", so.name, print_format="Miyano - Báo giá", as_pdf=True
    )
    frappe.local.response.filename = f"BaoGia-{so.name}.pdf"
    frappe.local.response.filecontent = pdf
    frappe.local.response.type = "pdf"
```

- [ ] **Step 7: Migrate rồi chạy test — phải XANH**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_bao_gia_pdf
```

Kỳ vọng: 5/5 PASS.

- [ ] **Step 8: Thêm nút tải trên `OrderDetail.vue`**

Trong khối "Chờ bạn đồng ý" (quanh dòng 247, cạnh nút "✔ Đồng ý đặt hàng"):

```html
            <a
              class="btn-o"
              :href="`/api/method/miyano_portal.api.portal.portal_bao_gia_pdf?order=${encodeURIComponent(name)}`"
              target="_blank"
              rel="noopener"
            >⬇ Tải báo giá (PDF)</a>
```

- [ ] **Step 9: Build và kiểm bằng mắt**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct && bench build --app miyano_portal
```

Dựng một đơn mua lẻ, ở Desk điền giá rồi bấm hành động workflow **"Gửi khách duyệt"**. Kỳ vọng: khách nhận email kèm PDF; trên cổng đơn hiện nút "Tải báo giá (PDF)" và bấm ra đúng file có bảng hàng, hạn hiệu lực, và nhóm hàng đang tìm nguồn.

- [ ] **Step 10: Chạy toàn bộ test và commit**

```bash
bench --site erptest.local run-tests --app miyano_portal
cd apps/miyano_portal && git add -A miyano_portal/ frontend/
git commit -m "feat(portal): PDF báo giá — mẫu in, endpoint tải, đính vào email"
```

---

### Task 10: Đổi tên "hợp đồng khung" ở mọi chuỗi hiển thị

**Files:**
- Modify: `frontend/src/views/Catalog.vue`, `Cart.vue`, `Dashboard.vue`, `Profile.vue`, `Orders.vue`, `OrderDetail.vue`, `frontend/src/store.js`, `frontend/src/style.css`
- Modify: `miyano_portal/api/portal.py`, `miyano_portal/portal_mua_le.py` (thông báo lỗi)
- Modify: `miyano_portal/setup/install_notifications.py`, `miyano_portal/setup/install_print_formats.py`
- Create: `miyano_portal/patches/v1_15/doi_nhan_hop_dong_khung.py`
- Modify: `miyano_portal/patches.txt`

**Interfaces:**
- Consumes: Task 3–9 (làm sau cùng để không phải đổi hai lần trên file đang viết lại)
- Produces: không có API mới

- [ ] **Step 1: Liệt kê chính xác phạm vi**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal
grep -rn "HĐNT\|nguyên tắc" frontend/src miyano_portal/ --include="*.vue" --include="*.js" --include="*.py" --include="*.css" | grep -v "\.pyc"
```

Chia kết quả làm hai nhóm và **chỉ sửa nhóm đầu**:
- **Chuỗi hiển thị** (trong `<template>`, trong `showToast(...)`, `frappe.throw(...)`, `label`, `subject`, `message`, HTML print format) → ĐỔI
- **Tên biến, fieldname, comment, tên class CSS** (`hdnt`, `custom_hdnt`, `thuoc_hdnt`, `mode: 'hdnt'`) → GIỮ NGUYÊN

- [ ] **Step 2: Đổi chuỗi trong SPA**

Bảng thay thế:

| Cũ | Mới |
|---|---|
| `Theo HĐNT` | `Theo hợp đồng khung` |
| `Có trong HĐNT — đặt ở chế độ Theo HĐNT` | `Có trong hợp đồng khung — đặt ở chế độ Theo hợp đồng khung` |
| `hạn mức HĐNT` | `hạn mức hợp đồng khung` |
| `Hợp đồng nguyên tắc` | `Hợp đồng khung` |
| `hợp đồng nguyên tắc` | `hợp đồng khung` |
| `HĐNT` (đứng một mình trong chuỗi hiển thị) | `hợp đồng khung` |

Trong `store.js`, các chỗ "HĐNT" nằm trong **comment** — giữ nguyên, chúng giải thích quan hệ với `custom_hdnt`.

- [ ] **Step 3: Đổi chuỗi trong thông báo lỗi server**

```bash
grep -rn "HĐNT\|nguyên tắc" miyano_portal/api/portal.py miyano_portal/portal_mua_le.py | grep -E "frappe\.throw|\"message\"|_\("
```

Đổi từng câu theo bảng trên. **Không đổi** mã lỗi `thuoc_hdnt_hieu_luc` — đó là hợp đồng API với client, không phải chữ khách đọc.

- [ ] **Step 4: Đổi chuỗi trong Notification và Print Format**

Sửa `setup/install_notifications.py` và `setup/install_print_formats.py` (gồm cả mẫu Báo giá vừa thêm ở Task 9).

Vì hai hàm cài đặt đều bỏ qua bản ghi đã tồn tại, viết patch cập nhật bản ghi cũ — `miyano_portal/patches/v1_15/doi_nhan_hop_dong_khung.py`:

```python
"""Spec 2026-08-15 §3.1 — "hợp đồng khung" thay "hợp đồng nguyên tắc"/HĐNT
trong Notification và Print Format ĐÃ CÀI trên site.

`install_portal_notifications()` và `install_portal_print_formats()` đều bỏ
qua bản ghi đã tồn tại, nên site đang chạy sẽ giữ nguyên chữ cũ nếu không có
patch này. Chỉ đổi CHỮ HIỂN THỊ — không đụng `condition`, `document_type`
hay bất kỳ fieldname nào.

Idempotent: thay chuỗi trên nội dung hiện tại; chạy lại khi đã sạch thì
không có gì để thay.
"""

import frappe

THAY = [
    ("Hợp đồng nguyên tắc", "Hợp đồng khung"),
    ("hợp đồng nguyên tắc", "hợp đồng khung"),
    ("Theo HĐNT", "Theo hợp đồng khung"),
    ("HĐNT", "hợp đồng khung"),
]


def _doi(chuoi):
    if not chuoi:
        return chuoi, False
    goc = chuoi
    for cu, moi in THAY:
        chuoi = chuoi.replace(cu, moi)
    return chuoi, chuoi != goc


def execute():
    for ten in frappe.get_all("Notification", pluck="name"):
        doc = frappe.db.get_value("Notification", ten, ["subject", "message"], as_dict=True)
        subject, s_doi = _doi(doc.subject)
        message, m_doi = _doi(doc.message)
        if s_doi or m_doi:
            frappe.db.set_value(
                "Notification", ten, {"subject": subject, "message": message}
            )

    for ten in frappe.get_all(
        "Print Format", filters={"name": ["like", "Miyano -%"]}, pluck="name"
    ):
        html, doi = _doi(frappe.db.get_value("Print Format", ten, "html"))
        if doi:
            frappe.db.set_value("Print Format", ten, "html", html)
```

Thêm vào `miyano_portal/patches.txt`:

```
miyano_portal.patches.v1_15.doi_nhan_hop_dong_khung
```

- [ ] **Step 5: Đổi label field trên Desk**

```bash
bench --site erptest.local console
```

```python
for fn, label in [("custom_hdnt", "Hợp đồng khung")]:
    name = frappe.db.get_value("Custom Field", {"dt": "Sales Order", "fieldname": fn}, "name")
    print(fn, name, frappe.db.get_value("Custom Field", name, "label") if name else None)
```

Nếu label hiện tại chứa "nguyên tắc"/"HĐNT", thêm phần cập nhật label vào patch ở Step 4 (cùng khuôn `frappe.db.set_value` trên `Custom Field`).

- [ ] **Step 6: Migrate, build, kiểm sạch**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench build --app miyano_portal
cd apps/miyano_portal
grep -rn "HĐNT\|nguyên tắc" frontend/src --include="*.vue" | grep -vE "^\S+:\s*//|/\*"
```

Kỳ vọng: không còn kết quả nào nằm trong `<template>` hay trong chuỗi hiển thị.

- [ ] **Step 7: Chạy toàn bộ test**

```bash
bench --site erptest.local run-tests --app miyano_portal
```

Nếu test nào so sánh chuỗi tiếng Việt cũ, sửa **test** cho khớp chữ mới — đó là đúng, chuỗi hiển thị vừa đổi có chủ ý.

- [ ] **Step 8: Kiểm bằng mắt và commit**

Vào cổng: bộ chuyển hiện `Theo hợp đồng khung | Mua lẻ`; không còn chữ "HĐNT" hay "nguyên tắc" ở đâu.

```bash
git add -A
git commit -m "feat(portal): đổi tên hiển thị sang 'hợp đồng khung' ở toàn bộ cổng, email, mẫu in"
```

---

### Task 11: Cập nhật bộ tài liệu BA

**Files:**
- Rename: `docs/Miyano-Portal(Client)_V2/DevHandoff/15_PRD_E6_MuaLeYeuCauHang.md` → `15_PRD_E6_MuaLe.md`
- Modify: `docs/Miyano-Portal(Client)_V2/BA-miyano_portal_v2.md`, `FormSpec-miyano_portal_v2.md`
- Modify: `DevHandoff/00_INDEX.md`, `20_DataDict.md`, `30_API_Spec.md`, `40_TestCases.md`
- Modify: `docs/CHANGELOG-khac-phuc-BA-v2.md`

**Interfaces:**
- Consumes: Task 1–10 (tài liệu mô tả cái đã chạy, không phải cái dự định)
- Produces: không có mã

- [ ] **Step 1: Đổi tên và sửa PRD E6**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal/docs/Miyano-Portal\(Client\)_V2/DevHandoff
git mv 15_PRD_E6_MuaLe_YeuCauHang.md 15_PRD_E6_MuaLe.md
```

Trong file: bỏ US-E6.3, US-E6.4, US-E6.6 khỏi phạm vi cổng, gom vào một mục **"Desk-only — không còn trên cổng khách"**; sửa US-E6.1 (mặc định BẬT, danh mục toàn bộ Item, không giá); thêm US mới cho khối đặt ngoài (§3.4), Item giữ chỗ, và PDF báo giá (§3.6). Sửa dòng `Phụ thuộc` — bỏ VĐ-12 (đã tan khi danh mục không hiện giá).

- [ ] **Step 2: Sửa `BA-miyano_portal_v2.md`**

Đánh dấu **Desk-only** cho QT11, UC-16, UC-17, UC-52, UC-53, BR-Y1…BR-Y5, NL-11.x. Không xoá — chúng vẫn mô tả đúng quy trình back-office.

Đổi cách gọi "hợp đồng nguyên tắc"/"HĐNT" → "hợp đồng khung" trong phần mô tả nghiệp vụ; **giữ nguyên** mã BR-O*/QT2 và tên trường.

- [ ] **Step 3: Sửa `30_API_Spec.md`**

Xoá 6 endpoint `portal_yeu_cau_*`. Thêm `portal_bao_gia_pdf(order)`. Cập nhật `portal_catalog_ban_le` (không trả giá; có `start`/`limit`/`tong`) và `portal_order_place` (tham số `dat_ngoai`, hành vi chèn Item giữ chỗ). Cập nhật `portal_order_track` (thêm khoá `dat_ngoai`, `items` đã lọc dòng giữ chỗ).

- [ ] **Step 4: Sửa `20_DataDict.md`**

Chuyển `Portal Item Request` sang mục Desk. Thêm `Sales Order Dat Ngoai Item` (6 trường, đúng bảng ở spec §3.4 của thiết kế 14/08) và Item kỹ thuật `HANG-DAT-NGOAI`. Ghi `Customer.custom_cho_phep_mua_le` mặc định = 1.

- [ ] **Step 5: Sửa `40_TestCases.md` và `FormSpec`**

`40_TestCases.md`: sửa TC-E6-02; chuyển TC-E6-05/06 sang Desk-only; thêm các TC mới ở §5 của spec.

`FormSpec-miyano_portal_v2.md`: bỏ F-22, F-23 khỏi cổng; sửa F-21 theo §3.3/§3.4; F-07 thêm nút Tải báo giá.

- [ ] **Step 6: Ghi vào `CHANGELOG-khac-phuc-BA-v2.md`**

Thêm mục mới với ngày 2026-08-15, dẫn tới spec, liệt kê bốn quyết định của chủ dự án và các mã bị ảnh hưởng. Tài liệu này tự nhận là "nguồn sự thật duy nhất về trạng thái khắc phục" — bỏ qua nó là để lại một nguồn sự thật nói sai.

- [ ] **Step 7: Sửa `00_INDEX.md`**

Cập nhật tên file PRD E6 và thứ tự đọc.

- [ ] **Step 8: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal
git add -A docs/
git commit -m "docs: cập nhật bộ BA theo spec 15/08 — cổng hai chế độ, Yêu cầu hàng hoá thành Desk-only"
```

---

## Kiểm tra cuối cùng

- [ ] **Toàn bộ test xanh**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_portal
```

Kỳ vọng: xanh. Tổng số test = 339 − (số test trong `test_e6_yeu_cau.py` đã xoá) + (test mới của Task 1, 6, 7, 8, 9).

- [ ] **Migrate lại từ đầu không lỗi**

```bash
bench --site erptest.local migrate
bench --site erptest.local migrate
```

Kỳ vọng: cả hai lần sạch — chứng minh 4 patch mới của v1_15 idempotent.

- [ ] **Đi hết luồng trên cổng bằng tay**

Đăng nhập `bvbm@demo.miyano` / `Portal@123` tại `http://192.168.61.129:8003/portal`:

1. Đặt hàng → thấy đúng hai chế độ `Theo hợp đồng khung | Mua lẻ`, không có mục "Yêu cầu hàng hoá" ở nav.
2. Mua lẻ → tìm được mã bất kỳ trong danh mục Miyano, **không thấy giá**.
3. Gõ từ khoá không tồn tại → khối tự nhập mở sẵn, prefill đúng từ khoá.
4. Thêm 2 dòng tự nhập, không chọn mặt hàng nào có mã → đặt đơn **thành công**.
5. Chi tiết đơn → thấy nhóm "Đang chờ Miyano xác nhận nguồn", **không** thấy `HANG-DAT-NGOAI`.
6. Ở Desk: điền giá, khớp mã cho dòng đặt ngoài, bấm "Gửi khách duyệt".
7. Trên cổng: thấy hạn hiệu lực báo giá, tải được PDF, bấm Đồng ý được.
