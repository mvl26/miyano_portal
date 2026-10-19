# HSD tối thiểu theo yêu cầu khách hàng — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Khách ghi "HSD tối thiểu (tháng)" khi đặt hàng; SO cảnh báo khi tồn không đạt; phiếu giao không duyệt được với lô không đạt trừ khi dòng SO có ngoại lệ do nhân viên Miyano ghi.

**Architecture:** Một module logic thuần `miyano_portal/han_dung_khach.py` là nguồn công thức duy nhất. Hook SO `validate` tính kết quả và cảnh báo; hook DN `before_submit` tự chốt lô đạt cho dòng chưa có lô (trước khi ERPNext tự chọn lô ở `on_submit`) rồi kiểm mọi lô thực xuất. Fork erpnext chỉ thêm một điểm hook `han_toi_thieu_lo_xuat` để PDA gợi ý và chặn lô theo hạn của khách.

**Tech Stack:** Frappe/ERPNext v15 (Python, `doc_events`, custom field qua patch), Desk JS (`doctype_js`), Vue 3 SPA cổng (`frontend/`, test `node --test`).

**Spec:** `docs/superpowers/specs/2026-10-19-hsd-toi-thieu-khach-hang-design.md`

## Global Constraints

- Không yêu cầu HSD (số tháng rỗng/0) hoặc mặt hàng `has_batch_no = 0` → hành vi y như hiện tại, kể cả chọn lô/FEFO. Đây là bất biến, có test khoá.
- Số tháng: số nguyên 0–60 (0/rỗng = không yêu cầu). Kiểm ở server; frontend kiểm thêm.
- Cộng tháng bằng `frappe.utils.add_months` (31/01 + 1 = 28/02 hoặc 29/02).
- SO: `hsd_yeu_cau_den = add_months(delivery_date của dòng, N)`. DN: `ngay_moc = max(delivery_date dòng SO, DN.posting_date)`, `hsd_yeu_cau_den = add_months(ngay_moc, N)`.
- Sàn: không ngoại lệ → `hsd_yeu_cau_den`; có ngoại lệ → `custom_ngoai_le_hsd_den`. Lô đạt khi `expiry_date >= san`; lô không có `expiry_date` → không đạt.
- DN bỏ qua: `is_return = 1`, dòng không có `so_detail`, dòng không áp dụng.
- Cảnh báo SO không bao giờ chặn lưu/submit. Không có cờ bỏ qua chặn DN nào ngoài ngoại lệ trên dòng SO.
- Quyền ghi/gỡ ngoại lệ: `Sales User`, `Sales Manager`, `System Manager`.
- Khách cổng không nhận các trường kết quả/ngoại lệ (`custom_hsd_yeu_cau_den`, `custom_ket_qua_hsd`, `custom_hsd_ton_tot_nhat`, `custom_ngoai_le_*`) từ bất kỳ API cổng nào.
- Nhãn và thông báo tiếng Việt; câu thông báo DN theo mẫu §4.5 của spec.
- Patch: `miyano_portal.patches.v1_46.hsd_toi_thieu`, chạy lại được (`install.after_install` gọi lại mọi patch).
- Commit kết thúc bằng `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Môi trường chạy:** bench nạp code từ `/home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal`, không phải worktree. Trước Task 1, thư mục đó phải được chuyển sang nhánh `feat/hsd-toi-thieu` (hỏi người dùng cách xử lý các thay đổi chưa commit của `feat/portal-redesign`). Fork erpnext làm trên nhánh `feat/hsd-khach-lay-hang` tách từ `develop` trong `apps/erpnext`.
- Lệnh test Python: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site localhost run-tests --app <app> --module <module>`.
- Dữ liệu test: kho KHÔNG quản lý vị trí lấy từ `erpnext.warehouse_operations.tests.kho_thu.dam_bao_kho_khong_vi_tri()` (tránh luật "lấy hàng PDA bắt buộc"); mặt hàng `has_batch_no=1, has_expiry_date=1`, lô tạo với `expiry_date` cụ thể, nhập tồn bằng Stock Entry Material Receipt có `batch_no`. Test không `frappe.db.commit()`.

## Review Focus

1. Cùng mặt hàng xuất hiện hai lần trong giỏ với số tháng khác nhau (giỏ gộp theo `item_code`) → dòng SO mang số tháng LỚN hơn (chặt hơn). Test ở Task 6.
2. Phiếu giao có hai dòng cùng mặt hàng chưa chốt lô → tự chốt lô phải trừ phần đã chốt cho dòng trước, không chốt cùng một lô vượt tồn. Test ở Task 4.
3. Ngoại lệ được gỡ sau khi phiếu giao đã lập nháp → duyệt phiếu giao lại bị chặn. Test ở Task 4.
4. SO bị sửa `delivery_date` sau submit (Update Items / hẹn lịch giao mới) → DN dùng ngày mới nhất trên dòng SO, không dùng giá trị `custom_hsd_yeu_cau_den` đã lưu. Test ở Task 4.
5. Khách cổng gọi API ngoại lệ hoặc đọc chi tiết đơn → bị từ chối / không thấy trường nội bộ. Test ở Task 3 và Task 6.

---

### Task 1: Trường dữ liệu + logic thuần

**Files:**
- Create: `miyano_portal/patches/v1_46/__init__.py`, `miyano_portal/patches/v1_46/hsd_toi_thieu.py`
- Modify: `miyano_portal/patches.txt` (thêm `miyano_portal.patches.v1_46.hsd_toi_thieu` cuối file)
- Modify: `miyano_portal/miyano_portal/doctype/portal_de_xuat_mua/portal_de_xuat_mua.json`, `.../portal_de_xuat_mua_item/portal_de_xuat_mua_item.json`
- Create: `miyano_portal/han_dung_khach.py`
- Test: `miyano_portal/tests/test_hsd_logic.py`

**Interfaces:**
- Produces (patch, custom field): Sales Order `custom_hsd_toi_thieu_thang` (Int, label "HSD tối thiểu (tháng)", allow_on_submit=0). Sales Order Item: `custom_hsd_toi_thieu_thang` (Int), `custom_hsd_yeu_cau_den` (Date, read_only), `custom_ket_qua_hsd` (Select `\nĐạt\nKhông đạt\nKhông áp dụng`, read_only), `custom_hsd_ton_tot_nhat` (Date, read_only), `custom_ngoai_le_hsd` (Check), `custom_ngoai_le_hsd_den` (Date), `custom_ngoai_le_ly_do` (Small Text), `custom_ngoai_le_boi` (Link User, read_only), `custom_ngoai_le_luc` (Datetime, read_only). Năm trường `custom_ngoai_le_*` có `allow_on_submit=1`; mọi trường `no_copy=0` trừ `custom_ngoai_le_*` (`no_copy=1`). Gom các trường dòng vào một Section Break "Hạn sử dụng khách yêu cầu" (collapsible).
- Produces (doctype JSON): `Portal De Xuat Mua.hsd_toi_thieu_thang` (Int) và `Portal De Xuat Mua Item.hsd_toi_thieu_thang` (Int).
- Produces (module):
  - `ap_dung(item_code: str, so_thang) -> bool` — `cint(so_thang) > 0` và Item `has_batch_no`.
  - `kiem_so_thang(so_thang) -> int` — trả `cint`, ném `frappe.ValidationError` "HSD tối thiểu phải là số tháng từ 0 đến 60." nếu ngoài 0–60 hoặc không phải số nguyên.
  - `hsd_yeu_cau_den(ngay, so_thang) -> date | None`
  - `san_cho_phep(dong_so, ngay_moc) -> date | None` — `dong_so` có các field SO Item ở trên; None khi không yêu cầu.
  - `danh_gia_lo(expiry_date, san) -> bool`
  - `mo_ta_chenh_lech(hsd_yeu_cau, hsd_thuc_te, tu_ngay) -> dict` với khoá `con_lai` (str) và `thieu_ngay` (int ≥ 0).

- [ ] **Step 1: Viết test thất bại** trong `test_hsd_logic.py` (`FrappeTestCase`):

```python
def test_cong_thang(self):
    self.assertEqual(hsd_yeu_cau_den("2026-10-15", 3), getdate("2027-01-15"))
    self.assertEqual(hsd_yeu_cau_den("2027-01-31", 1), getdate("2027-02-28"))
    self.assertEqual(hsd_yeu_cau_den("2028-01-31", 1), getdate("2028-02-29"))
    self.assertIsNone(hsd_yeu_cau_den("2026-10-15", 0))
    self.assertIsNone(hsd_yeu_cau_den("2026-10-15", None))

def test_bien_danh_gia_lo(self):
    self.assertTrue(danh_gia_lo("2027-01-15", getdate("2027-01-15")))
    self.assertFalse(danh_gia_lo("2027-01-14", getdate("2027-01-15")))
    self.assertFalse(danh_gia_lo(None, getdate("2027-01-15")))
    self.assertTrue(danh_gia_lo(None, None))  # không yêu cầu

def test_san_ap_ngoai_le(self):
    d = frappe._dict(custom_hsd_toi_thieu_thang=3, custom_ngoai_le_hsd=0, custom_ngoai_le_hsd_den=None)
    self.assertEqual(san_cho_phep(d, "2026-10-15"), getdate("2027-01-15"))
    d.update(custom_ngoai_le_hsd=1, custom_ngoai_le_hsd_den="2026-12-30")
    self.assertEqual(san_cho_phep(d, "2026-10-15"), getdate("2026-12-30"))
    self.assertIsNone(san_cho_phep(frappe._dict(custom_hsd_toi_thieu_thang=0), "2026-10-15"))

def test_mo_ta_chenh_lech_vi_du_tai_lieu(self):
    kq = mo_ta_chenh_lech(getdate("2027-01-15"), getdate("2026-12-30"), getdate("2026-10-15"))
    self.assertEqual(kq, {"con_lai": "02 tháng 15 ngày", "thieu_ngay": 16})
    kq = mo_ta_chenh_lech(getdate("2027-01-15"), getdate("2026-10-01"), getdate("2026-10-15"))
    self.assertEqual(kq["con_lai"], "đã hết hạn")

def test_kiem_so_thang(self):
    self.assertEqual(kiem_so_thang(None), 0)
    self.assertEqual(kiem_so_thang("3"), 3)
    for xau in (-1, 61, "abc", 2.5):
        with self.assertRaises(frappe.ValidationError):
            kiem_so_thang(xau)

def test_patch_chay_lai_duoc_va_tao_truong(self):
    from miyano_portal.patches.v1_46 import hsd_toi_thieu
    hsd_toi_thieu.execute(); hsd_toi_thieu.execute()
    for f in ("custom_hsd_toi_thieu_thang", "custom_ngoai_le_hsd_den", "custom_ket_qua_hsd"):
        self.assertTrue(frappe.get_meta("Sales Order Item").has_field(f))
    self.assertTrue(frappe.get_meta("Sales Order").has_field("custom_hsd_toi_thieu_thang"))
    self.assertTrue(frappe.get_meta("Sales Order Item").get_field("custom_ngoai_le_hsd").allow_on_submit)
```

`con_lai` dùng `dateutil.relativedelta(hsd_thuc_te, tu_ngay)`, định dạng `"{MM:02d} tháng {DD:02d} ngày"`, bỏ phần ngày khi bằng 0 (`"03 tháng"`); `hsd_thuc_te < tu_ngay` → `"đã hết hạn"`. `thieu_ngay = max(0, (hsd_yeu_cau - hsd_thuc_te).days)`.

- [ ] **Step 2: Chạy, xác nhận FAIL** — `bench --site localhost run-tests --app miyano_portal --module miyano_portal.tests.test_hsd_logic` → ImportError `han_dung_khach`.
- [ ] **Step 3: Viết patch** (`execute()` gọi `create_custom_fields` + `reload_doc` hai doctype cổng, cùng mẫu `v1_45/bao_gia_theo_dot.py`), sửa hai JSON doctype, viết các hàm module.
- [ ] **Step 4: Chạy migrate rồi test** — `bench --site localhost migrate` rồi lệnh Step 2 → PASS.
- [ ] **Step 5: Commit** — `feat(hsd): truong HSD toi thieu va logic tinh han`.

### Task 2: Hook Sales Order — kế thừa số tháng, tính kết quả, cảnh báo

**Files:**
- Modify: `miyano_portal/han_dung_khach.py`, `miyano_portal/hooks.py` (`doc_events["Sales Order"]["validate"]` thêm `miyano_portal.han_dung_khach.tinh_tren_don`)
- Test: `miyano_portal/tests/test_hsd_don.py`

**Interfaces:**
- Consumes: Task 1.
- Produces:
  - `kiem_ton_cho_dong(item_code: str, warehouse: str, stock_qty: float, san) -> dict` — khoá `dat` (bool), `hsd_tot_nhat` (date|None, HSD lớn nhất trong các lô còn tồn > 0), `ton_dat` (float). Tồn theo lô lấy từ `erpnext.stock.doctype.batch.batch.get_batch_qty(item_code=…, warehouse=…)`, ghép `Batch.expiry_date`.
  - `tinh_tren_don(doc, method=None) -> None` — hook `validate`.
  - `cau_canh_bao(dong, kq_ton, tu_ngay) -> str`.

Hành vi `tinh_tren_don`:
1. `doc.custom_hsd_toi_thieu_thang = kiem_so_thang(...)`; mỗi dòng: nếu `custom_hsd_toi_thieu_thang` rỗng (None/"") → lấy giá trị đầu phiếu; sau đó `kiem_so_thang`. Dòng ghi `0` tường minh vẫn giữ 0 khi đầu phiếu khác 0 — chỉ None/"" mới kế thừa.
2. Dòng không `ap_dung` → `custom_ket_qua_hsd = "Không áp dụng"`, xoá `custom_hsd_yeu_cau_den`, `custom_hsd_ton_tot_nhat`.
3. Dòng áp dụng → set `custom_hsd_yeu_cau_den`, gọi `kiem_ton_cho_dong(..., san_cho_phep(d, d.delivery_date))`, set `custom_ket_qua_hsd` (`Đạt`/`Không đạt`), `custom_hsd_ton_tot_nhat`.
4. Ngoại lệ khi đang nháp: `custom_ngoai_le_hsd = 1` mà thiếu `custom_ngoai_le_hsd_den` hoặc `custom_ngoai_le_ly_do` → `frappe.throw`; đủ thì điền `custom_ngoai_le_boi = frappe.session.user`, `custom_ngoai_le_luc = now_datetime()` nếu còn trống.
5. Có dòng `Không đạt` → MỘT `frappe.msgprint(..., indicator="orange", title="Không đáp ứng HSD khách yêu cầu")` gom các `cau_canh_bao`. Không throw.

Mẫu `cau_canh_bao` (dòng có tồn): `"Dòng {idx} – {item_code}: Khách hàng yêu cầu hàng còn tối thiểu {NN} tháng HSD (đến {dd/mm/yyyy}). Tồn kho tốt nhất HSD {dd/mm/yyyy}, chỉ còn {con_lai} → Không đáp ứng (thiếu {thieu_ngay} ngày). Vui lòng xác nhận với Khách hàng trước khi giao hàng."` — dòng không có tồn: thay câu giữa bằng `"Không còn tồn kho lô nào."`. Dòng đã ngoại lệ thêm `" Đã ghi ngoại lệ: khách chấp nhận đến {dd/mm/yyyy}."`. `NN` = `f"{n:02d}"`.

- [ ] **Step 1: Test thất bại** (`test_hsd_don.py`, dựng mặt hàng lô + 2 lô HSD `2027-01-30` (5 cái) và `2026-12-20` (10 cái) trong kho thử):

```python
def test_dong_ke_thua_so_thang_dau_phieu(self):
    so = self._so(hsd=3, dong=[{"qty": 2}, {"qty": 2, "custom_hsd_toi_thieu_thang": 6}, {"qty": 1, "custom_hsd_toi_thieu_thang": 0}])
    self.assertEqual([d.custom_hsd_toi_thieu_thang for d in so.items], [3, 6, 0])

def test_dat_khi_du_ton_lo_dat(self):            # giao 2026-10-15, 3 tháng → sàn 2027-01-15; lô 30/01 có 5
    so = self._so(hsd=3, dong=[{"qty": 5}], delivery_date="2026-10-15")
    d = so.items[0]
    self.assertEqual((d.custom_ket_qua_hsd, str(d.custom_hsd_yeu_cau_den)), ("Đạt", "2027-01-15"))

def test_khong_dat_khi_lo_dat_khong_du(self):     # cần 6 > 5
    so = self._so(hsd=3, dong=[{"qty": 6}], delivery_date="2026-10-15")
    self.assertEqual(so.items[0].custom_ket_qua_hsd, "Không đạt")
    self.assertEqual(str(so.items[0].custom_hsd_ton_tot_nhat), "2027-01-30")

def test_canh_bao_khong_chan_submit(self):
    so = self._so(hsd=12, dong=[{"qty": 1}], submit=True)
    self.assertEqual(so.docstatus, 1)
    self.assertEqual(so.items[0].custom_ket_qua_hsd, "Không đạt")

def test_khong_ap_dung(self):                    # mặt hàng không lô, hoặc không nhập
    so = self._so(hsd=0, dong=[{"qty": 1}])
    self.assertEqual(so.items[0].custom_ket_qua_hsd, "Không áp dụng")

def test_so_thang_ngoai_khoang_bi_tu_choi(self):
    with self.assertRaises(frappe.ValidationError):
        self._so(hsd=61, dong=[{"qty": 1}])

def test_ngoai_le_tren_nhap_bat_buoc_ly_do(self):
    with self.assertRaises(frappe.ValidationError):
        self._so(hsd=12, dong=[{"qty": 1, "custom_ngoai_le_hsd": 1, "custom_ngoai_le_hsd_den": "2026-12-20"}])

def test_cau_canh_bao_dung_mau(self):
    # tu_ngay 2026-10-15, yêu cầu 3 tháng, tồn tốt nhất 2026-12-30
    ...assertIn("chỉ còn 02 tháng 15 ngày → Không đáp ứng (thiếu 16 ngày)", cau)
```

- [ ] **Step 2: Chạy → FAIL.**
- [ ] **Step 3: Cài `kiem_ton_cho_dong`, `cau_canh_bao`, `tinh_tren_don`; đăng ký hook.**
- [ ] **Step 4: Chạy test này + `test_order_place`, `test_dat_hang_core` (không vỡ đơn cũ) → PASS.**
- [ ] **Step 5: Commit** — `feat(hsd): tinh ket qua HSD va canh bao tren Sales Order`.

### Task 3: Ghi/gỡ ngoại lệ sau submit + Desk Sales Order

**Files:**
- Modify: `miyano_portal/han_dung_khach.py`, `miyano_portal/public/js/sales_order.js`
- Test: `miyano_portal/tests/test_hsd_ngoai_le.py`

**Interfaces:**
- Consumes: Task 1–2.
- Produces (whitelisted):
  - `ghi_ngoai_le(so: str, dong: str, chap_nhan_den: str, ly_do: str) -> dict` — trả `{"dong": dong, "custom_ngoai_le_hsd_den": ..., "custom_ngoai_le_boi": ...}`.
  - `go_ngoai_le(so: str, dong: str, ly_do: str) -> dict`.
  - `VAI_TRO_NGOAI_LE = {"Sales User", "Sales Manager", "System Manager"}`.

Quy tắc: kiểm vai trò trước mọi thứ (`frappe.PermissionError`); SO phải `docstatus=1` và `status` không thuộc `("Closed", "Completed")`; `dong` phải là dòng của `so` và `ap_dung`; `ly_do` không rỗng; `chap_nhan_den` bắt buộc khi ghi. Ghi bằng `frappe.db.set_value("Sales Order Item", dong, {...})` cho các trường `custom_ngoai_le_*` (gỡ: `custom_ngoai_le_hsd=0`, `custom_ngoai_le_hsd_den=None`, ghi `custom_ngoai_le_ly_do` = lý do gỡ, cập nhật `_boi/_luc`). Mỗi lần ghi/gỡ thêm một Comment trên SO: `"Ghi ngoại lệ HSD dòng {idx} ({item_code}): khách chấp nhận đến {dd/mm/yyyy} — {ly_do}"` / `"Gỡ ngoại lệ HSD dòng {idx} ({item_code}) — {ly_do}"`.

Desk (`sales_order.js`, thêm vào khối `refresh` sẵn có, không tạo `frappe.ui.form.on` thứ hai cho "Sales Order"):
- `frm.dashboard.set_headline_alert` / `frm.set_intro` (màu cam) liệt kê dòng `Không đạt`: HSD yêu cầu, HSD tồn tốt nhất, trạng thái ngoại lệ.
- Tô đỏ ô `custom_ket_qua_hsd` = "Không đạt" trên lưới bằng `frm.fields_dict.items.grid` formatter hoặc `frappe.meta.docfield_map` formatter (`indicator red`).
- SO `docstatus=1` có dòng áp dụng: nút "Ghi ngoại lệ HSD" và "Gỡ ngoại lệ HSD" trong nhóm `__("Miyano")`; hộp thoại: chọn dòng (Select theo `idx – item_code`), `chap_nhan_den` (Date, điền sẵn `custom_hsd_ton_tot_nhat`), `ly_do` (Small Text, reqd) → `frappe.call` → `frm.reload_doc()`.

- [ ] **Step 1: Test thất bại:**

```python
def test_sales_user_ghi_duoc_va_co_comment(self): ...  # trường set, _boi = user, Comment chứa "Ghi ngoại lệ HSD dòng 1"
def test_stock_user_va_khach_cong_bi_tu_choi(self):    # frappe.set_user(user chỉ Stock User), rồi user cổng role Customer
    with self.assertRaises(frappe.PermissionError): ghi_ngoai_le(so.name, d.name, "2026-12-20", "ĐT khách")
def test_so_nhap_hoac_dong_bi_tu_choi(self): ...        # docstatus 0 → ValidationError; status Closed → ValidationError
def test_thieu_ly_do_bi_tu_choi(self): ...
def test_go_ngoai_le(self): ...                         # custom_ngoai_le_hsd = 0, hsd_den None, Comment "Gỡ ngoại lệ"
def test_dong_khong_thuoc_don_bi_tu_choi(self): ...
```

- [ ] **Step 2: Chạy → FAIL.**
- [ ] **Step 3: Cài API + JS.**
- [ ] **Step 4: Chạy test → PASS; `bench build --app miyano_portal` không lỗi.**
- [ ] **Step 5: Commit** — `feat(hsd): ghi/go ngoai le HSD tren Sales Order da duyet`.

### Task 4: Phiếu giao — tự chốt lô đạt và chặn duyệt

**Files:**
- Modify: `miyano_portal/han_dung_khach.py`, `miyano_portal/hooks.py` (`doc_events["Delivery Note"]["before_submit"]` đổi thành list, giữ `portal_thoi_gian_giao.dien_thoi_gian_giao`, thêm `miyano_portal.han_dung_khach.kiem_phieu_giao`)
- Test: `miyano_portal/tests/test_hsd_phieu_giao.py`

**Interfaces:**
- Consumes: Task 1.
- Produces:
  - `han_toi_thieu_lo_xuat(doc, d) -> date | None` — sàn cho dòng DN `d`: None nếu `doc.is_return`, không `d.so_detail`, hoặc dòng SO không `ap_dung`. Đọc dòng SO TƯƠI từ DB (`delivery_date`, số tháng, ngoại lệ), `ngay_moc = max(delivery_date, doc.posting_date)`. Task 5 dùng hàm này làm hook cho erpnext.
  - `kiem_phieu_giao(doc, method=None) -> None` — hook `before_submit`.

Hành vi `kiem_phieu_giao` (chỉ dòng có `san`):
1. Dòng chưa có `batch_no` và chưa có `serial_and_batch_bundle`: chọn lô đạt có HSD sớm nhất (`expiry_date >= san`, sắp `expiry_date asc, batch_no asc`) mà tồn (`get_batch_qty(item_code, warehouse)`) trừ phần các dòng trước TRÊN CÙNG phiếu đã chốt/đã có cho cùng (mặt hàng, kho, lô) ≥ `stock_qty`. Có → `d.batch_no = lo`, `d.use_serial_batch_fields = 1`. Không lô nào đủ một mình → lỗi dòng: `"Dòng {idx} – {item_code}: không có lô nào đạt HSD yêu cầu (đến {dd/mm/yyyy}) đủ {qty} {uom}. Lô đạt hiện có: {lo1} ({sl1}), … — tách dòng theo lô, hoặc ghi ngoại lệ trên SO {so}."` (danh sách rỗng → `"Không còn lô nào đạt."`).
2. Mọi lô thực xuất của dòng (`batch_no`, hoặc các `batch_no` trong `Serial and Batch Entry` của bundle) không đạt → lỗi dòng theo đúng mẫu spec §4.5:
   `"Dòng {idx} – {item_code}, lô {lo}: Khách hàng yêu cầu hàng còn tối thiểu {NN} tháng HSD (đến {dd/mm/yyyy}). Lô này HSD {dd/mm/yyyy}, chỉ còn {con_lai} → Không đáp ứng (thiếu {thieu_ngay} ngày). Vui lòng xác nhận với Khách hàng và ghi ngoại lệ trên SO {so} trước khi giao."` — lô không HSD: `"Lô này không có HSD → Không đáp ứng."` thay đoạn giữa. Khi dòng có ngoại lệ, câu nói sàn là `"khách chấp nhận đến {dd/mm/yyyy}"`.
3. Có lỗi → MỘT `frappe.throw("<br>".join(loi), title="Không đáp ứng HSD khách yêu cầu")`.

- [ ] **Step 1: Test thất bại** (SO giao `2026-10-15`, 3 tháng; lô A HSD `2027-01-30` (5), lô B HSD `2026-12-20` (10); DN `posting_date` đặt `2026-10-15` với `set_posting_time=1`):

```python
def test_tu_chot_lo_dat(self):            # DN 4 cái, không lô → batch_no = A, submit được
def test_chan_lo_khong_dat(self):         # DN 4 cái batch_no=B → ValidationError, thông báo chứa "lô B" và "thiếu 26 ngày"
def test_khong_lo_nao_du(self):           # DN 6 cái không lô → ValidationError "không có lô nào đạt"
def test_hai_dong_cung_hang(self):        # dòng 1: 4 (→ A), dòng 2: 4 không lô → lỗi (A còn 1), KHÔNG chốt A lần hai
def test_ngoai_le_mo_den_san(self):       # ghi_ngoai_le(..., "2026-12-20") → DN batch B submit được; ngoại lệ "2026-12-25" → vẫn chặn
def test_go_ngoai_le_sau_khi_lap_nhap(self):  # lập DN nháp batch B khi có ngoại lệ, go_ngoai_le, submit → chặn
def test_giao_tre_dung_posting_date(self):    # posting 2026-11-01 → sàn 2027-02-01 → lô A (30/01) bị chặn
def test_doi_ngay_giao_tren_so(self):     # set delivery_date dòng SO = 2026-11-01 bằng db.set_value → DN posting 2026-10-15 vẫn dùng 2026-11-01
def test_bo_qua(self):                    # is_return, dòng không so_detail, SO không yêu cầu, mặt hàng không lô → không đổi batch_no, không chặn
def test_bat_bien_khong_yeu_cau(self):    # SO hsd=0, DN không lô → kiem_phieu_giao KHÔNG gán batch_no (ERPNext tự chọn như cũ)
```

- [ ] **Step 2: Chạy → FAIL.**
- [ ] **Step 3: Cài hai hàm; sửa `hooks.py`.**
- [ ] **Step 4: Chạy test này + `test_kho_delivery_hook`, `test_order_place` → PASS.**
- [ ] **Step 5: Commit** — `feat(hsd): tu chot lo dat va chan duyet phieu giao khong dat HSD`.

### Task 5: PDA (fork erpnext) — gợi ý và chặn lô theo hạn khách

Làm trong `apps/erpnext`, nhánh `feat/hsd-khach-lay-hang` từ `develop`.

**Files:**
- Modify: `erpnext/warehouse_operations/vitri/lay_hang.py`
- Modify (miyano_portal): `miyano_portal/hooks.py` thêm `han_toi_thieu_lo_xuat = ["miyano_portal.han_dung_khach.han_toi_thieu_lo_xuat"]`
- Test: `erpnext/warehouse_operations/tests/test_lay_hang_han_khach.py`

**Interfaces:**
- Consumes: hook name `han_toi_thieu_lo_xuat` — hàm `(doc, d) -> date | None` (Task 4).
- Produces (trong `lay_hang.py`):
  - `_han_toi_thieu(doc, d) -> date | None` — gọi hàm CUỐI trong `frappe.get_hooks("han_toi_thieu_lo_xuat")`; không có hook → None. erpnext không import miyano_portal.
  - `_lo_nen_lay(kho, vat_tu, han_toi_thieu=None)` — có `han_toi_thieu` thì thêm điều kiện `b.expiry_date >= %(han)s` (loại lô không HSD). None → câu SQL y như cũ.
  - `_chan_lo_duoi_han_khach(doc, d, so_lo) -> None` — sàn có giá trị và lô không đạt (HSD < sàn hoặc không HSD) → `frappe.throw("Lô {so_lo} HSD {dd/mm/yyyy} thấp hơn HSD khách yêu cầu (đến {dd/mm/yyyy}) — lấy lô khác, hoặc nhờ kinh doanh ghi ngoại lệ trên đơn.")`.
- Gọi: chỗ `_lo_nen_lay(d.warehouse, d.item_code)` trong `mo_phieu_giao` truyền `han_toi_thieu=_han_toi_thieu(doc, d)`; `_chan_lo_duoi_han_khach` gọi trong `ghi_da_lay` (sau `_dong_cua`), `doi_lo` (trước gán `d.batch_no`), `tach_dong_theo_lo` (với `so_lo_moi`).

- [ ] **Step 1: Test thất bại** — đăng ký hook giả qua `patch("frappe.get_hooks", ...)` hoặc `frappe.flags` tuỳ mẫu test sẵn có trong `warehouse_operations/tests`; dùng kho quản lý vị trí `kho_thu.dam_bao_kho_thu()`:

```python
def test_goi_y_bo_lo_duoi_han(self):      # lô gần hạn bị bỏ, gợi ý lô xa hạn
def test_khong_hook_goi_y_nhu_cu(self):   # không hook → cùng kết quả _lo_nen_lay như trước
def test_doi_lo_duoi_han_bi_chan(self):
def test_ghi_da_lay_lo_duoi_han_bi_chan(self):
def test_tach_dong_lo_duoi_han_bi_chan(self):
```

- [ ] **Step 2: Chạy** `bench --site localhost run-tests --app erpnext --module erpnext.warehouse_operations.tests.test_lay_hang_han_khach` → FAIL.
- [ ] **Step 3: Cài; thêm hook ở miyano_portal.**
- [ ] **Step 4: Chạy test mới + `test_lay_hang`, `test_lay_hang_don_vi`, `test_fefo` → PASS.**
- [ ] **Step 5: Commit hai repo** — erpnext: `feat(lay-hang): goi y va chan lo theo HSD khach yeu cau`; miyano_portal: `feat(hsd): dang ky hook han toi thieu cho PDA`.

### Task 6: Cổng — backend mang yêu cầu HSD

**Files:**
- Modify: `miyano_portal/api/portal.py` (`portal_order_place`, `portal_order_track`), `miyano_portal/dat_hang.py` (`tao_sales_order`, `_xay_don`), `miyano_portal/api/de_xuat.py` (`de_xuat_luu_nhap`, `de_xuat_chi_tiet`), `miyano_portal/de_xuat_duyet.py` (`duyet_va_tao_don`)
- Test: `miyano_portal/tests/test_hsd_cong.py`

**Interfaces:**
- Consumes: Task 1–2 (validate SO tự kế thừa/kiểm số tháng).
- Produces:
  - `portal_order_place(..., hsd_toi_thieu_thang=None)`; mỗi phần tử `items` nhận khoá tuỳ chọn `hsd_toi_thieu_thang`.
  - `tao_sales_order(customer, *, ..., hsd_toi_thieu_thang=None)`; `items[i]["hsd_toi_thieu_thang"]` → `Sales Order Item.custom_hsd_toi_thieu_thang`. Gộp theo `item_code`: lấy giá trị lớn nhất; dòng không khai để None (kế thừa đầu phiếu).
  - `de_xuat_luu_nhap(..., hsd_toi_thieu_thang=None)` ghi `Portal De Xuat Mua.hsd_toi_thieu_thang`; `items` (đã set nguyên khối) mang `hsd_toi_thieu_thang` theo dòng. `de_xuat_chi_tiet` trả hai giá trị này để màn Lập phiếu mở lại nháp.
  - `duyet_va_tao_don` chuyển `doc.hsd_toi_thieu_thang` và `hsd_toi_thieu_thang` từng dòng sang `tao_sales_order`.
  - `portal_order_track` trả `hsd_toi_thieu_thang` cho đơn và từng dòng; KHÔNG trả trường nào trong Global Constraints "khách cổng không nhận".
  - Nhánh `di_bao_gia` của `portal_order_place` (sinh Quotation): nếu có yêu cầu HSD, thêm Comment lên Quotation `"Khách yêu cầu HSD tối thiểu: {N} tháng (cả đơn); {item}: {M} tháng; …"` — chưa mang qua Quotation (ngoài phạm vi spec §5), nhưng không được mất.
  - Server kiểm `kiem_so_thang` cho đầu phiếu và từng dòng TRƯỚC khi tạo chứng từ; lỗi trả theo cách các lỗi giỏ hàng khác của `portal_order_place` đang trả.

- [ ] **Step 1: Test thất bại:**

```python
def test_order_place_mang_so_thang(self):      # hsd=3, dòng X khai 6 → SO.custom_hsd_toi_thieu_thang 3, dòng X 6, dòng khác 3
def test_gop_cung_ma_lay_max(self):            # items [X:2 tháng, X:5 tháng] → một dòng X, 5 tháng
def test_so_thang_sai_bi_tu_choi(self):        # 61 → lỗi, không SO nào được tạo
def test_de_xuat_duyet_mang_so_thang(self):    # lưu nháp đề xuất hsd=4 + dòng 6 → gửi → duyệt → SO có 4/6
def test_quotation_co_comment_hsd(self):       # giỏ hàng chưa có giá + hsd=3 → Comment trên Quotation
def test_order_track_khong_lo_truong_noi_bo(self):
    d = portal_order_track(so.name)            # với user cổng
    self.assertEqual(d["items"][0]["hsd_toi_thieu_thang"], 3)
    flat = frappe.as_json(d)
    for f in ("custom_ket_qua_hsd", "custom_hsd_ton_tot_nhat", "custom_ngoai_le", "ket_qua_hsd", "ngoai_le"):
        self.assertNotIn(f, flat)
```

Dựng khách/user cổng bằng helper của `tests/test_order_place.py`.

- [ ] **Step 2: Chạy → FAIL.**
- [ ] **Step 3: Cài.**
- [ ] **Step 4: Chạy test mới + `test_order_place`, `test_dat_hang_core`, `test_dat_hang_gop`, `test_de_xuat_duyet` → PASS.**
- [ ] **Step 5: Commit** — `feat(hsd): cong mang yeu cau HSD vao don va de xuat`.

### Task 7: Cổng — giao diện

**Files:**
- Create: `frontend/src/hsd.js`, `frontend/src/hsd.test.mjs`
- Modify: `frontend/src/views/LapPhieu.vue`, `frontend/src/views/ChiTietYeuCau.vue`

**Interfaces:**
- Consumes: Task 6 (tham số `hsd_toi_thieu_thang` của `portal_order_place`, `de_xuat_luu_nhap`, dòng `items`; payload `portal_order_track`).
- Produces (`hsd.js`):
  - `chuanHoaThang(v) -> { ok: boolean, gia_tri: number | null, loi?: string }` — `''`/null/undefined → `{ok:true, gia_tri:null}`; số nguyên 0–60 (chuỗi số cũng nhận) → `{ok:true, gia_tri:n}`; còn lại → `{ok:false, loi:'HSD tối thiểu phải là số tháng từ 0 đến 60.'}`.
  - `thangHieuLuc(dong, dauPhieu) -> number | null` — dòng có giá trị (kể cả 0) thì dùng dòng, không thì đầu phiếu.

UI:
- `LapPhieu.vue`: ô "HSD tối thiểu (tháng)" cạnh "Ngày cần"; mỗi dòng giỏ có ô nhỏ cùng nhãn, placeholder là giá trị đầu phiếu ("theo đơn"). Lỗi `chuanHoaThang` hiện dưới ô và khoá nút gửi. Gửi qua cả hai nhánh: `portal_order_place` (quản lý) và `de_xuat_luu_nhap` (khoa phòng — cùng chỗ đang gửi `ngay_can`, dùng `?? ''` như các trường khác của hàm này); mở lại nháp đọc lại hai giá trị.
- `ChiTietYeuCau.vue`: hiện "HSD tối thiểu: N tháng" ở đầu đơn khi có, và cột/nhãn trên dòng có giá trị. Không hiện gì khác về HSD.

- [ ] **Step 1: Test thất bại** (`hsd.test.mjs`):

```js
test('chuanHoaThang', () => {
  assert.deepEqual(chuanHoaThang(''), { ok: true, gia_tri: null })
  assert.deepEqual(chuanHoaThang('3'), { ok: true, gia_tri: 3 })
  assert.deepEqual(chuanHoaThang(0), { ok: true, gia_tri: 0 })
  for (const x of [-1, 61, 2.5, 'abc']) assert.equal(chuanHoaThang(x).ok, false)
})
test('thangHieuLuc', () => {
  assert.equal(thangHieuLuc({ hsd_toi_thieu_thang: null }, 3), 3)
  assert.equal(thangHieuLuc({ hsd_toi_thieu_thang: 0 }, 3), 0)
  assert.equal(thangHieuLuc({ hsd_toi_thieu_thang: 6 }, 3), 6)
  assert.equal(thangHieuLuc({}, null), null)
})
```

- [ ] **Step 2: `cd frontend && yarn test` → FAIL.**
- [ ] **Step 3: Cài `hsd.js` + hai view.**
- [ ] **Step 4: `yarn test` PASS (toàn bộ, ≥ 61 + test mới); `yarn build` không lỗi.**
- [ ] **Step 5: Commit** — `feat(portal): o HSD toi thieu tren man lap phieu va chi tiet don`.

### Task 8: Kiểm toàn bộ

- [ ] **Step 1:** `bench --site localhost migrate` → không lỗi; patch v1_46 có trong `tabPatch Log`.
- [ ] **Step 2:** Toàn bộ test miyano_portal: `bench --site localhost run-tests --app miyano_portal` → OK (so với mốc 2470 + test mới, không test cũ nào hỏng).
- [ ] **Step 3:** Test `erpnext.warehouse_operations` toàn module (`--module` từng file trong `warehouse_operations/tests`, hoặc vòng lặp) → OK.
- [ ] **Step 4:** `cd frontend && yarn test && yarn build` → OK; `bench build --app miyano_portal` → OK.
- [ ] **Step 5:** Ghi lại kết quả, không commit gì nếu không có thay đổi.
