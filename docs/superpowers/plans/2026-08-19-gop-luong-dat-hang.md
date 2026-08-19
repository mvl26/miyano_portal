# Gộp một luồng đặt hàng — Kế hoạch thi công

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bỏ vách ngăn hai chế độ đặt hàng. Nhân viên tìm trong **một** danh sách, hệ thống tự phân loại **theo từng dòng** — có giá hợp đồng / chờ báo giá / hàng mới — và gửi Miyano **một đơn** trộn cả có giá lẫn chưa có giá.

**Architecture:** Quyết định chuyển từ **cấp ĐƠN** (tham số `mode`) xuống **cấp DÒNG** (field `nguon_gia` trên dòng phiếu). Hai hàm dựng đơn gộp làm một, rẽ theo từng dòng thay vì rẽ ở đầu hàm. Ba cơ chế cần thiết **đã tồn tại** — hợp đồng, danh mục đầy đủ, bảng đặt ngoài — việc chính là gỡ vách ngăn, không phải xây mới.

**Tech Stack:** Frappe v15.113.4, ERPNext (bản Miyano), site `erptest.local`, Vue 3 SPA.

**Spec:** `docs/superpowers/specs/2026-08-18-phan-quyen-khoa-phong-va-duyet-don-design.md` **§13** (chủ đầu tư chốt 19/08)

**Phụ thuộc:** làm **SAU** `2026-08-19-man-luong-duyet.md`. Ba màn ở kế hoạch đó không phụ thuộc thay đổi này; màn **lập phiếu** thì có, nên nó nằm ở đây (Task 8).

## Global Constraints

- **TDD.** Test trước, CHẠY, nhìn thấy **đỏ ở mức khẳng định** (không phải `ImportError`), rồi mới viết code.
- **Mọi test cách ly phải có VẾ DƯƠNG.** Thiếu nó thì một hàm trả rỗng cũng qua bài — lỗi này đã lọt **ba lần** trong dự án: thiếu vế dương, vế dương bị nhiễm bởi thông báo bước trước, và **fixture tự vá quanh chốt đang kiểm**.
- **Cấm fixture vá quanh chốt nó đang kiểm.** Nếu một test phải ép `custom_loai_don` hay `workflow_state` để đi qua được, dừng lại và hỏi: chốt đó có chặn luồng thật không? Hai lỗi Critical ngày 19/08 ẩn đúng theo cách này.
- **Mọi `assertRaises(ValidationError)` phải khẳng định cả THÔNG ĐIỆP** (`as ctx` + `assertIn`). `MandatoryError` và `DoesNotExistError` đều là con của nó. (`PermissionError` kế thừa thẳng `Exception` — bare an toàn.)
- **CHẠY TEST TIỀN CẢNH.** Không nền, không `&`, **không vòng chờ `pgrep`** (tự khớp chính dòng lệnh → treo vĩnh viễn). Timeout công cụ 600000 ms. Một tiến trình test tại một thời điểm.
- `FrappeTestCase` rollback **một lần cho cả CLASS** → fixture tự dọn trong `setUp`. `frappe.set_user("Administrator")` trong `tearDown`.
- Test tạo Sales Order phải **xoá sạch Sales Order test trước khi xoá phiếu** trong `setUp` — `revert_series_if_last` cấp trùng tên phiếu, chốt chống-trùng-đơn trả nhầm đơn cũ.
- Bình luận và thông báo lỗi: **tiếng Việt**.
- Patch mới ở `miyano_portal/patches/v1_25/`, khai trong `patches.txt`. Dùng `create_custom_field` (**số ít**). Patch chạy **đúng một lần mỗi site** — sửa patch đã chạy sẽ không bao giờ tới site đã migrate.
- **Không sửa test cũ** trừ nơi kế hoạch này cho phép tường minh (Task 1). Ngoài đó: DỪNG và báo.
- Suite nền khi bắt đầu: **1309 test** (sau kế hoạch màn hình).

**Về độ chi tiết của kế hoạch này:** kế hoạch màn hình (`2026-08-19-man-luong-duyet.md`) viết đủ từng bước TDD kèm mã. Kế hoạch này **cố ý viết ở mức quyết định + giao diện + danh sách khẳng định**, không trải hết chu trình 5 bước cho cả 8 task. Lý do: Task 4 đụng vào lõi tạo đơn mà 6 tài khoản thật đang dùng, và hình dạng đúng của nó **chỉ lộ ra sau khi Task 1–3 chạy xong** (bỏ cờ, có `nguon_gia`, có endpoint gộp). Viết sẵn mã cho Task 4 lúc này là viết một thứ gần như chắc chắn phải sửa. **Người điều phối phải sinh brief chi tiết cho từng task ngay trước khi giao**, dựa trên trạng thái mã lúc đó — không giao thẳng mục này cho người thi công.

---

## Quyết định đã chốt

**QĐ-G1 — `nguon_gia` là field SUY RA, không nhập tay.** Đặt trên `Portal De Xuat Mua Item`, Select: `Hợp đồng` / `Chờ báo giá`. Hệ thống ghi lúc thêm dòng, dựa trên việc mã hàng có dòng hợp đồng còn hiệu lực hay không. Không cho client gửi lên — một giá trị tự khai thì đúng lúc cần đối chiếu nhất sẽ sai.
*Sai thì mất gì:* nếu nghiệp vụ cần quản lý ép một dòng sang "chờ báo giá" thủ công thì phải mở ra sau; rẻ.

**QĐ-G2 — `loai_don` ở đầu phiếu GIỮ LẠI làm field suy ra, không xoá.** Chủ đầu tư nói nó "sai chỗ" — đúng, nó không được **quyết định** gì nữa. Nhưng xoá hẳn sẽ làm vỡ mọi báo cáo và mọi chỗ đọc nó. Chuyển thành **suy ra từ các dòng**: có ít nhất một dòng `Chờ báo giá` → `Hỗn hợp`; toàn bộ `Hợp đồng` → `HĐNT`. Chỉ đọc, hệ thống ghi.
*Sai thì mất gì:* một field thừa nếu không ai đọc; rẻ hơn nhiều so với rà mọi nơi đọc nó.

**QĐ-G3 — Đơn trộn đi MỘT vòng báo giá, cả đơn cùng chờ.** Chủ đầu tư xác nhận rõ và **chấp nhận cái giá**: hàng trong hợp đồng vốn giao được ngay, giờ phải chờ. Ghi vào tài liệu vận hành — đây là thứ bệnh viện sẽ hỏi.
*Sai thì mất gì:* nếu sau này cần tách, phải dựng cơ chế tách đơn — việc lớn. Nhưng làm sẵn cơ chế tách khi chưa cần là YAGNI.

**QĐ-G4 — Bỏ cờ `custom_cho_phep_mua_le` là XOÁ MỘT CHỐT ĐANG CHẠY**, không phải dọn mã chết. Sau khi bỏ, **mọi khách hàng đều xin được hàng ngoài hợp đồng** — đó là điều mong muốn, nhưng nó **mở rộng quyền cho toàn bộ khách hiện có**. Phải nói ra, không để lẳng lặng xảy ra.

---

## File Structure

| File | Trách nhiệm |
|---|---|
| `miyano_portal/portal_mua_le.py` *(sửa)* | Bỏ `dam_bao_duoc_mua_le`; giữ `qua_han_hieu_luc`/`han_hieu_luc_bao_gia`/`la_dong_giu_cho` |
| `miyano_portal/api/portal.py` *(sửa)* | Bỏ chốt cờ; `portal_me` bỏ `cho_phep_mua_le`; thêm `portal_catalog_gop` |
| `miyano_portal/dat_hang.py` *(sửa)* | **Gộp hai hàm dựng đơn thành một, rẽ theo dòng** |
| `.../portal_de_xuat_mua_item/*.json` *(sửa)* | Thêm `nguon_gia` |
| `.../portal_de_xuat_mua/portal_de_xuat_mua.py` *(sửa)* | Suy `nguon_gia` mỗi dòng; suy `loai_don` từ dòng |
| `miyano_portal/de_xuat_duyet.py` *(sửa)* | Bỏ rẽ nhánh `mode`; hạn mức chỉ trên dòng hợp đồng |
| `miyano_portal/patches/v1_25/` *(mới)* | `them_nguon_gia_dong_phieu.py`, `xoa_co_mua_le.py` |
| `frontend/src/views/LapPhieu.vue` *(mới)* | Màn lập phiếu — tìm một danh sách, ba tầng |
| `frontend/src/views/Catalog.vue` *(sửa)* | Bỏ bộ chuyển chế độ |

---

## Task 1: Bỏ cờ `custom_cho_phep_mua_le`

**Files:**
- Modify: `miyano_portal/portal_mua_le.py`, `miyano_portal/api/portal.py`, `miyano_portal/dat_hang.py`
- Modify: `frontend/src/views/Catalog.vue` *(bỏ bộ chuyển chế độ)*
- Create: `miyano_portal/patches/v1_25/xoa_co_mua_le.py`
- Modify (**có phê chuẩn, xem dưới**): `tests/test_e6_mua_le.py`, `tests/test_dat_hang_core.py`, `tests/test_mua_le_mac_dinh_bat.py`

**Đây là task đổi hành vi có chủ đích. Ba điều kiện, cấp sẵn ở đây:**

**(a) Luật nào bị bỏ:** `Customer.custom_cho_phep_mua_le` gác quyền mua ngoài hợp đồng (NL-10.1) — `dam_bao_duoc_mua_le` ném 403 `khong_duoc_mua_le`, `portal_catalog_ban_le` từ chối trước khi trả danh mục. Chủ đầu tư chốt 19/08: *"nghiệp vụ đó áp dụng cho toàn bộ khách hàng"* → không còn gì để gác.

**(b) Bằng chứng ĐỎ bắt buộc:** với **mỗi** test bị sửa, phải chạy và **nhìn thấy nó đỏ** trước khi có mã mới. Test khẳng định "khách chưa bật cờ bị 403" phải được **viết lại thành khẳng định ngược** — *"mọi khách đều mua được"* — và đỏ trước khi bỏ chốt. **Tuyệt đối không xoá test cho suite xanh.** Đó chính xác là cách một chốt biến mất mà không ai biết, và dự án này đã chứng kiến nó xảy ra.

**(c) Phê chuẩn:** cấp bằng chính đoạn này.

**Phạm vi đã đo (19/08):** 3 chỗ `portal_mua_le.py`, 5 chỗ `api/portal.py`, 2 chỗ `dat_hang.py`, 1 file Vue, 4 file test. **Không sửa** `patches/v1_8` và `v1_15` — patch đã chạy không bao giờ tới lại site đã migrate.

**Field trên `Customer`: xoá bằng patch trong chính task này.** Giữ lại một field trông như chốt kiểm soát mà không còn gác gì là **phiên bản schema của "bình luận nói sai về code"** — người sau nhìn `custom_cho_phep_mua_le = 0` sẽ tưởng khách đó đang bị chặn.

- [ ] **Step 1:** Viết lại 4 file test theo khẳng định ngược. CHẠY, **nhìn thấy đỏ**, ghi output vào report.
- [ ] **Step 2:** Bỏ `dam_bao_duoc_mua_le` và mọi lời gọi. Bỏ `cho_phep_mua_le` khỏi `portal_me`.
- [ ] **Step 3:** Bỏ bộ chuyển chế độ khỏi `Catalog.vue`. `cd frontend && yarn build` phải thành công.
- [ ] **Step 4:** Viết patch `v1_25/xoa_co_mua_le.py` — xoá `Custom Field` `Customer-custom_cho_phep_mua_le`. Khai vào `patches.txt`.
- [ ] **Step 5:** `bench --site erptest.local migrate`, rồi **xác minh patch chạy thật**:
```bash
bench --site erptest.local mariadb -e "select name, skipped from \`tabPatch Log\` where patch like '%xoa_co_mua_le%'"
bench --site erptest.local mariadb -e "select count(*) from \`tabCustom Field\` where fieldname='custom_cho_phep_mua_le'"
```
Dòng đầu phải có, `skipped = 0`; dòng sau phải trả `0`.
- [ ] **Step 6:** Full suite TIỀN CẢNH, xanh.
- [ ] **Step 7:** Commit — `feat(dat-hang): bo co cho_phep_mua_le - moi khach deu xin duoc hang ngoai hop dong`

---

## Task 2: `nguon_gia` xuống cấp dòng

**Files:**
- Modify: `.../portal_de_xuat_mua_item/portal_de_xuat_mua_item.json` — thêm `nguon_gia` (Select: `Hợp đồng` / `Chờ báo giá`, read-only)
- Modify: `.../portal_de_xuat_mua/portal_de_xuat_mua.py`
- Create: `miyano_portal/patches/v1_25/them_nguon_gia_dong_phieu.py`
- Test: `miyano_portal/tests/test_nguon_gia_dong.py` *(mới)*

**Interfaces:**
- Produces: `PortalDeXuatMua._suy_nguon_gia()` — chạy trong `validate()`, ghi `nguon_gia` cho mọi dòng.
- Produces: `loai_don` ở đầu phiếu thành **suy ra** (QĐ-G2): có dòng `Chờ báo giá` → `Hỗn hợp`; toàn `Hợp đồng` → `HĐNT`.

**Cách suy `nguon_gia` cho một dòng:** mã hàng có dòng trong hợp đồng khung của phiếu **và** hợp đồng còn hiệu lực → `Hợp đồng`; ngược lại → `Chờ báo giá`. Dòng đặt ngoài (chưa có mã) luôn `Chờ báo giá`.

**Test tối thiểu:**
- Dòng có trong hợp đồng → `nguon_gia == "Hợp đồng"` **(vế dương)**
- Dòng có mã nhưng ngoài hợp đồng → `"Chờ báo giá"`
- Phiếu toàn dòng hợp đồng → `loai_don == "HĐNT"`
- Phiếu trộn → `loai_don == "Hỗn hợp"` **(đây là ca chính của cả kế hoạch)**
- Client gửi `nguon_gia` sai → **bị ghi đè**, không tin client (QĐ-G1)

**Patch:** backfill `nguon_gia` cho phiếu đã có — phiếu cũ đều thuần một loại, suy từ `loai_don` đầu phiếu.

---

## Task 3: Endpoint tìm kiếm gộp

**Files:**
- Modify: `miyano_portal/api/portal.py` — thêm `portal_catalog_gop`
- Modify: `miyano_portal/tests/test_pham_vi_endpoint.py` — **khai tên mới ngay trong task này**
- Test: `miyano_portal/tests/test_catalog_gop.py` *(mới)*

**Interfaces:**
- Produces: `portal_catalog_gop(tu_khoa=None, contract=None, start=0, limit=50) -> dict`

Mỗi phần tử trả về: `{item_code, item_name, dvt, tang, don_gia, blanket_order}` với `tang` ∈ `{"hop_dong", "cho_bao_gia"}`. Hàng chưa có mã **không** đến từ endpoint này — nó là dòng khách gõ tay, đi qua bảng đặt ngoài.

**Test tối thiểu:**
- Mã trong hợp đồng → `tang == "hop_dong"`, có `don_gia` **(vế dương)**
- Mã ngoài hợp đồng → `tang == "cho_bao_gia"`, `don_gia` là `None` (**không phải `0`** — `0` là một giá hợp lệ)
- Tìm không dấu vẫn ra (collation `utf8mb4_unicode_ci` đã lo, đã kiểm ở spec §2)
- **Cách ly:** khách A không thấy giá hợp đồng của khách B

---

## Task 4: Gộp hai hàm dựng đơn

**Files:**
- Modify: `miyano_portal/dat_hang.py`
- Test: `miyano_portal/tests/test_dat_hang_gop.py` *(mới)*

**Đây là task lớn nhất và rủi ro nhất của kế hoạch.**

`tao_sales_order` hiện rẽ ở đầu hàm thành `_xay_don_hdnt` / `_xay_don_ban_le`. Gộp thành một hàm dựng, quyết **theo từng dòng**:

| Dòng | Xử lý |
|---|---|
| Có dòng hợp đồng | `rate` = giá hợp đồng, gắn `blanket_order`, **trừ hạn mức** |
| Có mã, ngoài hợp đồng | `rate = 0`, chờ Miyano báo giá |
| Chưa có mã | vào `custom_dat_ngoai`, **không bao giờ** append vào `items` |

**Bỏ chốt `dat_hang.py:651`** — *"Dòng đặt ngoài chỉ áp dụng cho chế độ Mua lẻ"*. Chính nó là vách ngăn.

**Giữ nguyên, không được đụng:**
- Hợp đồng lỗi có cấu trúc: `frappe.local.response["loi"]` + `frappe.throw` — nhiều test phụ thuộc.
- Chống trùng đơn qua `custom_request_id`.
- Dòng giữ chỗ khi giỏ toàn hàng đặt ngoài (ERPNext không lưu được `items` rỗng).

**Test tối thiểu:**
- **Đơn trộn**: 1 dòng hợp đồng + 1 dòng chờ báo giá + 1 dòng đặt ngoài → **một** Sales Order, dòng hợp đồng có giá, dòng kia `rate = 0`, dòng đặt ngoài ở `custom_dat_ngoai` **(ca chính)**
- Đơn thuần hợp đồng → hành vi **y hệt hôm nay** (chốt tương thích ngược, phải xanh cả trước lẫn sau)
- Đơn thuần chờ báo giá → như "mua lẻ" hôm nay
- Đặt ngoài **không** lọt vào `items`

---

## Task 5: Hạn mức chỉ trên dòng hợp đồng

**Files:**
- Modify: `miyano_portal/de_xuat_duyet.py` (`_kiem_han_muc`)
- Test: `miyano_portal/tests/test_han_muc_don_tron.py` *(mới)*

Hôm nay nhánh HĐNT giả định **mọi** dòng đều trên hợp đồng. Đơn trộn phá giả định đó.

**Giữ nguyên hành vi đã chốt:** hết hạn mức → **thất bại kèm TÊN KHOA đã tiêu mất**, tuyệt đối **không im lặng cắt số lượng**.

**Test tối thiểu:**
- Đơn trộn, dòng hợp đồng còn hạn mức → duyệt được **(vế dương)**
- Đơn trộn, dòng hợp đồng vượt hạn mức → throw kèm tên khoa
- Dòng chờ báo giá **không** bị kiểm hạn mức (nó chưa thuộc hợp đồng nào)

---

## Task 6: Đơn trộn đi một vòng báo giá

**Files:**
- Modify: `miyano_portal/dat_hang.py`, `miyano_portal/portal_mua_le.py`
- Test: `miyano_portal/tests/test_don_tron_bao_gia.py` *(mới)*

Theo QĐ-G3: đơn **có ít nhất một dòng chưa có giá** → đi vòng báo giá; Miyano điền giá → khách đồng ý → tiếp tục như cũ. Đơn **toàn hàng hợp đồng** → giữ nguyên đường hôm nay, **không** ép qua vòng báo giá.

**Test tối thiểu:** đơn trộn vào đúng trạng thái chờ báo giá **(vế dương)**; đơn thuần hợp đồng **không** bị đổi đường **(chốt tương thích ngược)**.

---

## Task 7: Rà lại năm chốt của `portal_order_sua_so_luong`

**Files:**
- Modify: `miyano_portal/api/portal.py`, `.../portal_de_xuat_mua.py`
- Test: `miyano_portal/tests/test_de_xuat_sua_sau_duyet.py` *(mở rộng)*

Chốt `custom_loai_don != "Mua lẻ"` → throw **trở nên sai hình dạng** dưới mô hình gộp: giờ đơn trộn cũng đi vòng báo giá, nên nó cũng phải sửa số lượng được.

Đây chính là **nguyên nhân gốc** của lỗi Critical C1 ngày 19/08. Mô hình gộp gỡ được gốc; task này thu hoạch điều đó.

**Cẩn thận:** `_kiem_don_dung_duoc_xin_sua()` hiện soi gương **đủ 5 chốt**. Đổi lõi mà quên đổi bản soi gương → hai bên lệch nhau, và phiếu lại vào ngõ cụt. **Sửa cả hai trong cùng task, có test cho từng chốt.**

---

## Task 8: Màn lập phiếu

**Files:**
- Create: `frontend/src/views/LapPhieu.vue`
- Modify: `frontend/src/router.js`, `frontend/src/App.vue`

Một ô tìm, một danh sách kết quả, mỗi dòng gắn nhãn tầng:

| Nhãn | Nghĩa |
|---|---|
| Giá hợp đồng · *(số tiền)* | tầng 1 |
| **Chờ báo giá** | tầng 2 |

Không tìm thấy → nút **"Hàng chưa có trong hệ thống"** mở ô gõ tay tên/ĐVT/số lượng (tầng 3, vào bảng đặt ngoài).

**Nói rõ trên màn, đúng QĐ-G3:** *"Đơn có hàng chờ báo giá — cả đơn sẽ chờ Miyano báo giá trước khi giao."* Người dùng phải biết trước khi bấm, không phải phát hiện sau.

**Bỏ hoàn toàn** khái niệm "chuyển chế độ" khỏi giao diện.

---

## Nghiệm thu cuối kế hoạch

- [ ] Full suite xanh, chạy **hai lần liên tiếp**, tiền cảnh.
- [ ] `cd frontend && yarn build` thành công.
- [ ] `bench --site erptest.local migrate` không ném lỗi; **xác minh cả hai patch v1_25 chạy thật** bằng `tabPatch Log` và bằng truy vấn schema.
- [ ] **Đi một vòng thật:** lập phiếu trộn ba tầng → gửi duyệt → quản lý duyệt → **một** đơn sinh ra chứa cả ba loại dòng → Miyano điền giá → khách đồng ý → đơn đi tiếp.
- [ ] **Chốt tương thích ngược:** đặt một đơn thuần hợp đồng bằng tài khoản quản lý, xác nhận hành vi **y hệt trước kế hoạch này**.
- [ ] Cập nhật `docs/HDSD-phan-quyen-khoa-phong.md`: bỏ mọi mô tả "hai chế độ"; thêm ba tầng; **ghi rõ hàng hợp đồng giờ phải chờ nếu đứng chung đơn với hàng chưa có giá** — đây là thứ bệnh viện sẽ hỏi. Chạy lại `docs/md2docx.py`.
- [ ] Ba màn của kế hoạch trước: thêm **cột trạng thái giá** trên bảng dòng hàng.

---

## Rủi ro lớn nhất

**Task 4 đụng vào đường tạo đơn mà 6 tài khoản đang chạy thật dùng mỗi ngày.** Hợp đồng lỗi có cấu trúc (`frappe.local.response["loi"]`) có nhiều test phụ thuộc, và một thay đổi ở đó đổi hành vi cho **mọi** người dùng, không riêng luồng mới. Chốt tương thích ngược ở phần nghiệm thu **không phải formality** — nó là thứ canh chính.
