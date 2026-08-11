# Tài liệu phân tích nghiệp vụ — ứng dụng `miyano_portal`

| Mục | Nội dung |
|---|---|
| Ứng dụng | `miyano_portal` (Miyano Portal) — cổng khách hàng của SupplyCore v2 |
| Nền tảng | Frappe v15 + ERPNext (`required_apps = ["frappe/frappe", "erpnext"]`) |
| Site tham chiếu | `erptest.local` |
| Nhánh mô tả trong tài liệu này | `feature/vat-tu-danh-muc` (commit đầu `971cc4b`) |
| Ngày lập | 2026-08-10 |
| Mức độ kiểm chứng | Toàn bộ mục 4–9 được đối chiếu trực tiếp với mã nguồn trên nhánh nêu trên, không viết theo trí nhớ |

**Tài liệu này KHÔNG phải hướng dẫn thao tác.** Phần "bấm nút nào, ở màn nào" nằm ở
[`docs/HDSD-tao-khach-hang-mo-kho-va-thao-tac-cong.md`](HDSD-tao-khach-hang-mo-kho-va-thao-tac-cong.md).
Tài liệu này trả lời: *hệ thống giải quyết vấn đề nghiệp vụ gì, theo luật nào, dữ liệu ra sao,
và tại sao lại thiết kế như vậy.*

Tài liệu nguồn phía trước: `apps/erpnext/doc/DESIGN_supplycore_v2_client_portal.md`,
`apps/erpnext/doc/YeuCau_NghiepVu_ThietKe_ClientPortal_Miyano.docx`.
Thiết kế chi tiết phần kho: `docs/superpowers/specs/2026-08-06-kho-khach-hang-design.md` và
`docs/superpowers/specs/2026-08-07-vat-tu-va-import-export-dong-phieu-design.md`.

---

## 1. Bối cảnh và mục tiêu nghiệp vụ

Miyano là nhà cung cấp vật tư — hoá chất, sinh phẩm, vật tư tiêu hao — cho bệnh viện và
phòng xét nghiệm. Trước cổng khách hàng, vòng đời một đơn hàng đi qua điện thoại, email và
file Excel: khách gửi yêu cầu, nhân viên kinh doanh nhập tay vào ERPNext, khách không tự
biết đơn của mình đang ở đâu, đã giao bao nhiêu, còn nợ bao nhiêu và còn bao nhiêu hạn mức
trong hợp đồng nguyên tắc.

Đồng thời, phía bệnh viện tồn tại một bài toán thứ hai không thuộc ERPNext của Miyano:
**bệnh viện phải tự quản lý kho vật tư của chính mình** — nhập về, xuất sử dụng, theo dõi
lô và hạn dùng, in phiếu nhập/phiếu xuất theo mẫu TT107/TT200 để lưu chứng từ. Phần lớn đang
làm bằng Excel, tách rời khỏi số liệu giao hàng của Miyano.

Mục tiêu của `miyano_portal`:

| # | Mục tiêu | Chỉ báo đạt được |
|---|---|---|
| MT1 | Khách tự đặt hàng theo hợp đồng nguyên tắc, không qua trung gian | Đơn hàng sinh thẳng thành `Sales Order` với `custom_nguon_don = "Client Portal"` |
| MT2 | Hạn mức hợp đồng được máy kiểm, không kiểm bằng mắt | Vượt hạn mức bị chặn ngay lúc đặt, kèm số còn lại |
| MT3 | Khách tự tra cứu đơn / phiếu giao / hoá đơn / công nợ | Không còn yêu cầu tra cứu qua nhân viên kinh doanh |
| MT4 | Bệnh viện quản lý kho của mình ngay trên cổng, có lô và hạn dùng | Sổ kho, thẻ kho, báo cáo NXT, cảnh báo hạn dùng |
| MT5 | Hàng Miyano giao đến tự chảy vào kho khách, không nhập lại | Phiếu nhập **nháp** tự sinh từ `Delivery Note` |
| MT6 | Chứng từ kho in được theo mẫu của từng đơn vị | `Print Format` chọn theo từng kho |
| MT7 | Dữ liệu khách này tuyệt đối không lọt sang khách khác | Xem mục 8 |

---

## 2. Phạm vi

### 2.1 Trong phạm vi

- Cổng web (SPA) tại `/portal` cho người dùng phía khách hàng.
- Đặt hàng theo hợp đồng nguyên tắc, kiểm hạn mức, theo dõi đơn, xem phiếu giao, xem hoá đơn
  và công nợ.
- Kho khách hàng: danh mục vật tư riêng, tồn đầu kỳ, phiếu nhập, phiếu xuất, sổ kho theo lô,
  báo cáo nhập–xuất–tồn, thẻ kho, cảnh báo hạn dùng, in phiếu, xuất/nhập Excel.
- Móc tích hợp một chiều từ `Delivery Note` của Miyano sang kho khách.
- Phân quyền và cách ly dữ liệu theo từng khách hàng.
- Màn hình phía Desk cho nhân viên Miyano tra cứu kho khách (workspace + 3 report).

### 2.2 Ngoài phạm vi — và lý do

| Không làm | Lý do |
|---|---|
| **Kho khách hàng KHÔNG dùng tồn kho ERPNext** — không `Warehouse`, không `Bin`, không `Stock Entry`, không `Stock Ledger Entry`, không gắn `Company` | Cả hai công ty Miyano đều bật `enable_perpetual_inventory = 1`. Một phiếu xuất của bệnh viện đi qua tồn kho ERPNext sẽ ghi bút toán giá vốn **lên sổ sách của Miyano**; và một `Delivery Note` giao vào kho như vậy trở thành điều chuyển nội bộ, không bao giờ làm giảm tồn kho thật của Miyano. Đây là quyết định nền tảng — mọi phương án "gộp lại cho gọn" đều làm hỏng sổ sách Miyano. |
| Khách tự huỷ đơn trên cổng | Chỉ có *yêu cầu huỷ* (`portal_request_cancel`); quyết định huỷ thuộc Miyano |
| Thanh toán trực tuyến | Cổng chỉ hiển thị công nợ, không thu tiền |
| Khách sửa giá / sửa hợp đồng | Giá lấy từ `Price List` riêng của khách, chỉ đọc |
| Đấu thầu, báo giá | Không nằm trong vòng đời cổng |
| Quản lý nhiều kho cho một khách | Mỗi khách hàng một kho đang hoạt động (mục 6, BR-K1) |
| Ứng dụng di động đóng gói (native) | Cổng chạy responsive trên trình duyệt |

---

## 3. Tác nhân và vai trò

| Tác nhân | Vai trò kỹ thuật | Làm được gì | Nơi làm việc |
|---|---|---|---|
| **Người dùng cổng của khách hàng** (thủ kho / kế toán / điều dưỡng trưởng bệnh viện) | `Website User` + role `Customer`, `Contact` trỏ về `Customer` | Đặt hàng, tra cứu, toàn bộ nghiệp vụ kho của chính đơn vị mình | `/portal` |
| **Nhân viên kinh doanh Miyano** | `Sales User` | Xác nhận / từ chối đơn từ cổng, lập `Delivery Note`, lập `Sales Invoice` | Desk ERPNext |
| **Quản lý kinh doanh Miyano** | `Sales Manager` | Như trên, thêm quyền sửa đơn đã xác nhận / đã từ chối | Desk ERPNext |
| **Quản trị hệ thống** | `System Manager` | Tạo khách hàng, cấp tài khoản cổng, mở kho, chọn mẫu in, bật/tắt kho | Desk ERPNext |

Một điểm cần nêu rõ vì dễ hiểu sai: **người dùng cổng không hề có quyền trên tám doctype kho.**
Họ thao tác được là nhờ tầng API whitelist tự suy ra kho từ phiên đăng nhập, không phải nhờ
được cấp quyền doctype. Xem mục 8.

---

## 4. Quy trình nghiệp vụ

Sáu luồng dưới đây là "xương sống" chung với file
[`Workflow-miyano_portal.html`](Workflow-miyano_portal.html) — bản trực quan của cùng nội dung.

### 4.1 QT1 — Đặt hàng trên cổng

```
Khách chọn hợp đồng (Blanket Order)
   → xem danh mục = các mặt hàng trong hợp đồng + giá từ Price List riêng + hạn mức còn lại
   → thêm vào giỏ
   → đặt hàng  ──► portal_order_place
                     ├─ kiểm hợp đồng thuộc đúng khách
                     ├─ kiểm địa chỉ giao thuộc đúng khách (nếu có chọn)
                     ├─ GỘP các dòng trùng mã hàng  (BR-O2)
                     ├─ kiểm hạn mức từng mã hàng, gom hết lỗi rồi báo một lần
                     ├─ lấy giá từ Item Price của Price List khách
                     ├─ chọn kho xuất theo TỪNG mặt hàng  (BR-O4)
                     └─ tạo Sales Order NHÁP, gắn contact_email để gửi thông báo
   → email "Portal - Đơn mới" gửi cho khách
```

Kết quả: một `Sales Order` `docstatus = 0`, `workflow_state = "Chờ xác nhận"` (trạng thái đầu
của workflow, do Frappe gán mặc định — `portal_order_place` **không** tự đặt trường này).

### 4.2 QT2 — Miyano xử lý đơn (máy trạng thái)

Workflow `Sales Order - Client Portal` cài trên doctype `Sales Order`:

| Trạng thái | `docstatus` | Ai được sửa |
|---|---|---|
| Chờ xác nhận | 0 (nháp) | `Sales User` |
| Chờ Miyano xác nhận | 0 (nháp) | `Sales User` |
| Đã xác nhận | 1 (đã ghi sổ) | `Sales Manager` |
| Từ chối | 0 (nháp) | `Sales Manager` |

| Từ | Hành động | Sang | Ai được làm |
|---|---|---|---|
| Chờ xác nhận | Gửi duyệt | Chờ Miyano xác nhận | `Sales User` |
| Chờ Miyano xác nhận | Xác nhận | Đã xác nhận | `Sales User` |
| Chờ Miyano xác nhận | Từ chối | Từ chối | `Sales User` |

**Hai điểm phải nêu, không được "vẽ lại cho đẹp":**

1. **Cả ba chuyển tiếp đều mở cho `Sales User`**, kể cả chuyển tiếp đi vào hai trạng thái mà
   `allow_edit` là `Sales Manager`. Nghĩa là hiện tại **không có cấp duyệt hai tầng**: nhân viên
   kinh doanh tự xác nhận được đơn. Nhìn cấu hình thì giống một quy trình leo thang đang làm dở.
   Cần chủ đầu tư quyết: giữ nguyên (một tầng) hay đổi `allowed` của "Xác nhận"/"Từ chối" sang
   `Sales Manager`. Xem mục 12, VĐ-3.
2. **Workflow này áp cho MỌI `Sales Order`**, không chỉ đơn từ cổng — Frappe Workflow gắn theo
   doctype, không lọc theo điều kiện được. Chủ đầu tư đã chấp nhận điều này.

Thông báo email theo trạng thái:

| Sự kiện | Thông báo | Điều kiện |
|---|---|---|
| Tạo mới `Sales Order` | Portal - Đơn mới | `custom_nguon_don == "Client Portal"` |
| Ghi sổ `Sales Order` | Portal - Đơn xác nhận | `custom_nguon_don == "Client Portal"` |
| `workflow_state` đổi thành "Từ chối" | Portal - Đơn bị từ chối | `custom_nguon_don == "Client Portal"` |
| Ghi sổ `Delivery Note` | Portal - Xuất giao | (mọi phiếu giao) |
| Ghi sổ `Sales Invoice` | Portal - Hoá đơn phát hành | (mọi hoá đơn) |

Trạng thái hiển thị cho khách trên cổng **không** phải `workflow_state` mà là nhãn suy ra từ
`status` + `per_delivered` (BR-O5): Chờ xác nhận → Đang xử lý → Đang giao → Hoàn thành / Đã huỷ.

### 4.3 QT3 — Miyano giao hàng → phiếu nhập tự sinh trong kho khách

```
Sales Order (Đã xác nhận)
   → Miyano lập Delivery Note, ghi sổ (submit)
        │
        │  doc_events["Delivery Note"]["on_submit"]
        ▼
   miyano_portal.kho.delivery_hook.on_delivery_note_submit
        ├─ tìm kho ĐANG HOẠT ĐỘNG của khách; không có → dừng im lặng
        ├─ đã có phiếu cho DN này (docstatus < 2) → dừng, không sinh trùng
        ├─ với mỗi dòng: khớp/tạo Customer Warehouse Item trong kho khách
        ├─ lấy số lô + hạn dùng từ bundle lô do ERPNext sinh
        ├─ chọn `ngay` phiếu sao cho không rơi trước ngay_bat_dau của kho
        └─ tạo Customer Stock Receipt NHÁP, loai_nhap = "Từ đơn hàng Miyano",
           ghi delivery_note / sales_order để truy vết
```

**Ba tính chất thiết kế của móc này, đều cố ý:**

- Đặt ở `on_submit`/`on_cancel` chứ không phải `before_*`: móc này không kiểm tra gì cả, nó chỉ
  sinh hiệu ứng phụ. Đặt ở `before_submit` sẽ biến mọi trục trặc phía kho khách thành lỗi chặn
  Miyano giao hàng.
- **Không bao giờ ném lỗi ra ngoài** (`delivery_hook._chay_an_toan`). Ràng buộc cao nhất của tính
  năng: *việc giao hàng của Miyano không được phụ thuộc vào kho của khách.*
- Phiếu sinh ra ở trạng thái **nháp**. Thủ kho bệnh viện phải kiểm hàng thực tế rồi mới ghi sổ.
  Hàng chưa nhận mà tồn đã tăng là sai nghiệp vụ.

Huỷ `Delivery Note`: phiếu còn nháp thì bị gỡ; phiếu đã ghi sổ thì bị **đảo** (mục 4.5).

### 4.4 QT4 — Nghiệp vụ kho của khách hàng

```
Mở kho  ──►  Danh mục vật tư  ──►  Nhập tồn đầu kỳ (một lần)
                   │                        │
                   │                        ▼
                   │              ┌──── SỔ KHO (append-only) ────┐
                   ▼              │                              │
        Phiếu nhập  ──ghi sổ──────┤  Customer Stock Ledger Entry │
        (tự sinh / tay / Excel)   │              +               │
                                  │  Customer Stock Lot Balance  │──► Báo cáo NXT
        Phiếu xuất  ──ghi sổ──────┤        (cache dẫn xuất)      │──► Thẻ kho
        (gợi ý lô FEFO)           └──────────────────────────────┘──► Cảnh báo hạn
```

Vòng đời một phiếu (cả nhập lẫn xuất): **Nháp** (`docstatus 0`) → **Đã ghi sổ** (`docstatus 1`,
sinh dòng sổ) → **Đã huỷ** (`docstatus 2`, sinh phiếu đảo). Không có bước duyệt trung gian —
thủ kho tự chịu trách nhiệm trên phiếu của mình.

Xuất kho có gợi ý lô theo **FEFO** (`kho_lo_goi_y`): đi từ lô hết hạn gần nhất, lô không có hạn
xếp cuối, phân bổ tham lam cho tới đủ. Đây **chỉ là gợi ý hiển thị**, không chặn; chốt chặn thật
nằm ở `before_submit` của `Customer Stock Issue`.

### 4.5 QT5 — Huỷ phiếu đã ghi sổ → phiếu đảo

Đây là quy tắc kế toán nền tảng của sổ kho, không phải chi tiết kỹ thuật:

```
Huỷ phiếu đã ghi sổ
   ├─ before_cancel: chặn nếu phiếu này CHÍNH LÀ phiếu đảo      (BR-K7)
   ├─ before_cancel: chặn nếu hàng của lô đó đã bị xuất mất rồi (BR-K8)
   └─ on_cancel:
        ├─ sinh MỘT phiếu đảo mới, đã ghi sổ, số lượng ngược dấu
        └─ đánh dấu các dòng sổ gốc `da_dao = 1`
```

**Không dòng sổ nào bị xoá.** Sổ vẫn cộng dồn ra đúng tồn; lịch sử vẫn đọc được đầy đủ, kể cả
phần đã bị đảo. `"Phiếu đảo"` là một lựa chọn nhìn thấy được trong dropdown `loai_nhap`/`loai_xuat`,
nên phải có chốt: điều kiện *duy nhất* được chấp nhận để tạo phiếu đảo là cờ trong bộ nhớ
`flags.dang_tao_dao` — mọi điều kiện dựa trên giá trị field đều giả được từ ngoài (đã từng phát
hành rồi bị bắt lại một lần).

### 4.6 QT6 — Hoá đơn và công nợ

Miyano lập `Sales Invoice` trên Desk → ghi sổ → email "Portal - Hoá đơn phát hành" → khách xem
trên `/portal/invoices` với trạng thái đã Việt hoá và số dư còn phải trả (`outstanding_amount`).
Cổng không thu tiền, không sinh chứng từ thanh toán.

---

## 5. Danh mục ca sử dụng

Bảng dựng từ `frontend/src/router.js` (17 route) đối chiếu với các endpoint whitelist trong
`api/portal.py` và `api/kho.py`.

### 5.1 Nhóm mua hàng

| Mã | Ca sử dụng | Màn hình | Endpoint |
|---|---|---|---|
| UC-01 | Đăng nhập cổng | `/portal/login` | trang web riêng, không qua SPA |
| UC-02 | Xem tổng quan | `/portal/dashboard` | `portal_me`, `portal_order_history`, `portal_invoices` |
| UC-03 | Xem hợp đồng nguyên tắc và hạn mức còn lại | `/portal/catalog` | `portal_contracts` |
| UC-04 | Xem danh mục hàng theo hợp đồng, có giá riêng | `/portal/catalog` | `portal_catalog` |
| UC-05 | Đặt hàng từ giỏ | `/portal/cart` | `portal_order_place` |
| UC-06 | Xem lịch sử đơn hàng | `/portal/orders` | `portal_order_history` |
| UC-07 | Theo dõi tiến độ một đơn | `/portal/orders/:name` | `portal_order_track` |
| UC-08 | Xem phiếu giao hàng | `/portal/orders/:name` | `portal_deliveries` |
| UC-09 | Xem hoá đơn và công nợ | `/portal/invoices` | `portal_invoices` |
| UC-10 | Gửi yêu cầu huỷ đơn | `/portal/orders/:name` | `portal_request_cancel` |
| UC-11 | Tải chứng từ PDF (đơn / phiếu giao / hoá đơn) | nhiều màn | `portal_document_download` |
| UC-12 | Xem hồ sơ đơn vị | `/portal/profile` | `portal_me` |
| UC-13 | Cấp tài khoản cổng cho khách *(nhân viên Miyano)* | Desk | `portal_provision` |

### 5.2 Nhóm kho khách hàng

| Mã | Ca sử dụng | Màn hình | Endpoint |
|---|---|---|---|
| UC-20 | Xem thông tin kho của mình | `/portal/kho` | `kho_me` |
| UC-21 | Xem tồn kho theo vật tư | `/portal/kho` | `kho_ton` |
| UC-22 | Xem tồn theo lô của một vật tư | `/portal/kho` | `kho_lo` |
| UC-23 | Xem / tìm danh mục vật tư | `/portal/kho/vat-tu` | `kho_vat_tu_list` |
| UC-24 | Thêm, sửa vật tư | `/portal/kho/vat-tu` | `kho_vat_tu_tao`, `kho_vat_tu_sua` |
| UC-25 | Xuất danh mục vật tư ra Excel | `/portal/kho/vat-tu` | `kho_vat_tu_export` |
| UC-26 | Nhập danh mục vật tư từ Excel, xem trước rồi mới ghi | `/portal/kho/vat-tu/import` | `kho_vat_tu_import_preview`, `kho_vat_tu_import_commit` |
| UC-27 | Nhập tồn đầu kỳ từ Excel, xem trước rồi mới ghi | `/portal/kho/import` | `kho_import_template`, `kho_import_preview`, `kho_import_commit` |
| UC-28 | Xem danh sách phiếu nhập / phiếu xuất | `/portal/kho/nhap`, `/portal/kho/xuat` | `kho_phieu_list` |
| UC-29 | Lập / sửa phiếu nhập | `/portal/kho/nhap/:name` | `kho_phieu_nhap_save`, `kho_phieu_get` |
| UC-30 | Lập / sửa phiếu xuất | `/portal/kho/xuat/:name` | `kho_phieu_xuat_save`, `kho_phieu_get` |
| UC-31 | Xem gợi ý lô theo FEFO khi xuất | `/portal/kho/xuat/:name` | `kho_lo_goi_y` |
| UC-32 | Ghi sổ phiếu | hai màn chi tiết | `kho_phieu_submit` |
| UC-33 | Huỷ phiếu đã ghi sổ (sinh phiếu đảo) | hai màn chi tiết | `kho_phieu_cancel` |
| UC-34 | Nhập bảng dòng phiếu từ Excel | hai màn chi tiết | `kho_dong_phieu_mau`, `kho_dong_phieu_doc_file` |
| UC-35 | Xuất bảng dòng phiếu ra Excel | hai màn chi tiết | `kho_dong_phieu_export` |
| UC-36 | In phiếu (PDF theo mẫu của kho) | hai màn chi tiết | `kho_phieu_pdf` |
| UC-37 | Báo cáo nhập–xuất–tồn theo kỳ | `/portal/kho/bao-cao` | `kho_bao_cao_nxt` |
| UC-38 | Thẻ kho một vật tư theo kỳ | `/portal/kho/bao-cao` | `kho_the_kho` |
| UC-39 | Cảnh báo hạn dùng | `/portal/kho/bao-cao` | `kho_canh_bao_han` |
| UC-40 | Xuất báo cáo ra Excel | `/portal/kho/bao-cao` | `kho_bao_cao_excel` |
| UC-41 | Nhân viên Miyano tra cứu kho khách *(Desk)* | Workspace "Kho khách hàng" | 3 Query/Script Report |

---

## 6. Quy tắc nghiệp vụ

### 6.1 Đặt hàng

| Mã | Quy tắc | Nơi thực thi |
|---|---|---|
| BR-O1 | Chỉ đặt được theo hợp đồng nguyên tắc thuộc chính đơn vị mình; địa chỉ giao cũng phải thuộc đơn vị mình | `portal_order_place` |
| BR-O2 | Các dòng giỏ hàng trùng mã hàng phải được **gộp trước** khi kiểm hạn mức. Nếu kiểm từng dòng riêng lẻ, hai dòng cùng mã đều "lọt" trong khi tổng vượt hạn mức | `portal_order_place` |
| BR-O3 | Vượt hạn mức thì chặn, và báo **tất cả** mã hàng sai một lần kèm số còn lại, không báo từng cái | `portal_order_place` |
| BR-O4 | Mỗi dòng xuất từ kho mặc định **của chính mặt hàng đó**, không ép cả đơn về một kho — nếu không, mặt hàng để ở kho khác sẽ làm `Delivery Note` báo âm kho | `_resolve_item_warehouse` |
| BR-O5 | Không có giá bán trong `Price List` của khách → chặn đặt hàng | `portal_order_place` |
| BR-O6 | Hạn mức trừ theo `Blanket Order` nhờ `against_blanket_order = 1` trên từng dòng — cơ chế gốc của ERPNext, không tự tính | `portal_order_place` |
| BR-O7 | Trạng thái hiển thị cho khách suy ra từ `status` + `per_delivered`: đã bắt đầu giao (`per_delivered > 0`) mà chưa xong thì luôn là "Đang giao", vì `status` gốc gộp lẫn "Đang xử lý" và "Đang giao" | `_so_status_vi` |
| BR-O8 | Khách không huỷ được đơn, chỉ gửi yêu cầu huỷ kèm lý do | `portal_request_cancel` |

### 6.2 Kho khách hàng

| Mã | Quy tắc | Nơi thực thi |
|---|---|---|
| BR-K1 | **Mỗi khách hàng đúng một kho** — ràng buộc cứng ở tầng CSDL: trường `customer` của `Customer Warehouse` là `unique` và bắt buộc. Kho đã tắt (`active = 0`) không nhận phiếu tự sinh và không truy cập được từ cổng; đó là công tắc thủ công để ngừng tính năng kho cho một khách | doctype `Customer Warehouse`; `portal_context.get_portal_kho`; `delivery_hook._kho_cua_khach` |
| BR-K2 | Vật tư trên phiếu phải thuộc đúng kho của phiếu | `voucher.validate_vat_tu_thuoc_kho` |
| BR-K3 | Vật tư riêng của khách có `item_code` rỗng và **không** sinh `Item` trong ERPNext. Danh mục của bệnh viện là danh mục của bệnh viện | doctype `Customer Warehouse Item` |
| BR-K4 | Sổ kho `Customer Stock Ledger Entry` là **chỉ ghi thêm** (append-only) và là nguồn sự thật duy nhất; `Customer Stock Lot Balance` là cache dẫn xuất, dựng lại được bất cứ lúc nào bằng `ledger.rebuild_lot_balance` | `kho/ledger.py` |
| BR-K5 | **Không cho tồn âm.** Xuất quá tồn của lô bị chặn ở `before_submit` | `ledger._ensure_non_negative` |
| BR-K6 | Đơn giá đi theo **lô**, nên định giá không cần engine tính giá vốn. Bình quân gia quyền phải tính lại cả khi delta **âm**: với phiếu xuất thì đó là phép rỗng (xuất theo giá bình quân hiện hành), nhưng phiếu **đảo của một phiếu nhập** mang đúng giá của phiếu gốc — bỏ qua bước tính lại ở đó làm giá trị sổ lệch vĩnh viễn khỏi giá trị cache, không sửa được. Đã đo: 352.941 VND sinh ra từ hư không trên một lô nhiều mức giá | `ledger._apply_to_balance` |
| BR-K7 | Huỷ phiếu **không xoá dòng sổ**, mà sinh phiếu đảo ngược dấu rồi đánh dấu dòng gốc `da_dao = 1`. Phiếu đảo thì **không huỷ được** | `voucher.block_cancel_of_reversal` |
| BR-K8 | Không huỷ được phiếu nhập nếu hàng của lô đó đã bị xuất mất — phải huỷ phiếu xuất trước. Phải **cộng dồn theo (vật tư, lô)** trước khi so với tồn, vì hai dòng cùng lô xét riêng lẻ đều "đủ" | `_chan_neu_dao_lam_am_ton` |
| BR-K9 | Chỉ hệ thống được tạo phiếu loại `"Phiếu đảo"`; điều kiện duy nhất là cờ bộ nhớ `flags.dang_tao_dao`, tuyệt đối không dùng điều kiện dựa trên field | `_chan_tu_tao_phieu_dao` |
| BR-K10 | Ngày phiếu tự sinh không được rơi trước `ngay_bat_dau` của kho | `_ngay_phieu_khong_mat_hang` |
| BR-K11 | Một `Delivery Note` chỉ sinh **một** phiếu nhập (tính cả phiếu đã ghi sổ, `docstatus < 2`) — nếu không, thủ kho ghi sổ xong sẽ cộng tồn lần thứ hai | `_phieu_dang_song` |
| BR-K12 | Móc từ `Delivery Note` **không bao giờ** ném lỗi ra ngoài | `_chay_an_toan` |
| BR-K13 | Gợi ý lô theo FEFO: hạn gần nhất trước, lô không hạn xếp cuối; chỉ gợi ý, không chặn | `kho_lo_goi_y` |
| BR-K14 | Mọi thao tác nhập từ Excel đều **xem trước rồi mới ghi**: dòng lỗi được nêu đủ lý do và sửa tại chỗ được, không chặn cứng nút Lưu nháp | `import_ton_dau.py`, `dong_phieu.py` |
| BR-K15 | Mẫu in chọn theo kho (`mau_phieu_nhap` / `mau_phieu_xuat`); mẫu cấu hình sai `doc_type` bị bỏ qua và rơi về mẫu TT107 mặc định thay vì render rác | `_print_format_cho_kho` |

---

## 7. Mô hình dữ liệu

### 7.1 Doctype riêng của kho khách hàng (8)

Tên doctype tiếng Anh, tên trường tiếng Việt không dấu, nhãn tiếng Việt có dấu.

| Doctype | Vai trò | Đặc điểm |
|---|---|---|
| `Customer Warehouse` | Kho của một khách hàng | `KKH-.#####`; chứa thông tin in phiếu và hai `Print Format` riêng |
| `Customer Warehouse Item` | Danh mục vật tư của kho | `VTK-.#####`; `item_code` rỗng = vật tư riêng của khách (BR-K3) |
| `Customer Stock Receipt` | Phiếu nhập kho | Ghi sổ được; `loai_nhap`: Tồn đầu kỳ / Từ đơn hàng Miyano / Nhập khác / **Phiếu đảo** |
| `Customer Stock Receipt Item` | Dòng phiếu nhập | `istable = 1` |
| `Customer Stock Issue` | Phiếu xuất kho | Ghi sổ được; `loai_xuat`: Xuất sử dụng / Xuất huỷ - hết hạn / Xuất trả lại / Điều chỉnh kiểm kê / **Phiếu đảo** |
| `Customer Stock Issue Item` | Dòng phiếu xuất | `istable = 1` |
| `Customer Stock Ledger Entry` | **Sổ kho — nguồn sự thật** | `SKK-.#########`; chỉ ghi thêm; có `da_dao` |
| `Customer Stock Lot Balance` | Tồn theo lô — **cache dẫn xuất** | Dựng lại được từ sổ |

Quan hệ chính:

```
Customer (ERPNext)
   └─1:1─ Customer Warehouse
             ├─1:n─ Customer Warehouse Item ──(0..1)──► Item (ERPNext)
             ├─1:n─ Customer Stock Receipt ─1:n─ Customer Stock Receipt Item
             ├─1:n─ Customer Stock Issue   ─1:n─ Customer Stock Issue Item
             ├─1:n─ Customer Stock Ledger Entry     (ghi bởi ghi sổ phiếu)
             └─1:n─ Customer Stock Lot Balance      (dẫn xuất từ sổ)
```

### 7.2 Doctype ERPNext dùng lại

| Khái niệm nghiệp vụ | Doctype ERPNext |
|---|---|
| Hợp đồng nguyên tắc (HĐNT) | `Blanket Order` (Selling) + `Price List` + `Item Price` |
| Đơn hàng | `Sales Order` |
| Phiếu giao hàng | `Delivery Note` |
| Hoá đơn / công nợ | `Sales Invoice` |
| Khách hàng, địa chỉ, người liên hệ | `Customer`, `Address`, `Contact` |
| Tài khoản cổng | `User` (Website User) + role `Customer` |

### 7.3 Trường mở rộng trên `Sales Order`

Cài bằng patch `v1_0.create_sales_order_custom_fields`:

| Trường | Ý nghĩa |
|---|---|
| `custom_nguon_don` | `"Client Portal"` — dấu nhận biết đơn từ cổng, là điều kiện của 3 thông báo |
| `custom_hdnt` | Hợp đồng nguyên tắc áp dụng |
| `custom_so_po_khach` | Số PO nội bộ của khách |
| `custom_yeu_cau_khach` | Ghi chú/yêu cầu của khách |

### 7.4 Cài đặt tự động khi `bench migrate`

`patches.txt` (11 patch) cài: trường mở rộng, quyền đọc cho role `Customer`, workflow, 5 thông báo,
các `Print Format` (song ngữ cho chứng từ bán hàng; TT107/TT200 cho phiếu kho), 3 report kho phía Desk,
workspace "Kho khách hàng", và một patch sửa dữ liệu `repair_kho_ledger_replay`.

---

## 8. Phân quyền và cách ly dữ liệu

Đây là phần rủi ro cao nhất của hệ thống: một cổng nhiều khách hàng dùng chung một site.

### 8.1 Nhóm chứng từ bán hàng (`Sales Order`, `Delivery Note`, `Sales Invoice`, `Blanket Order`)

- `permission_query_conditions` lọc theo `customer` suy từ phiên đăng nhập.
- `has_permission` chặn truy cập từng bản ghi.
- **Cạm bẫy đã gặp:** trong bản Frappe này `frappe.get_doc` **không** tự động gọi `has_permission`.
  Mọi endpoint lấy tài liệu theo tên do người gọi truyền vào **bắt buộc** phải tự gọi `check_permission`.

### 8.2 Nhóm tám doctype kho — mô hình khác hẳn

Cách ly ở đây tựa trên **bốn thứ cùng lúc**, và thứ **chịu lực chính** không phải là các hook:

1. **Role `Customer` không có bất kỳ `DocPerm` nào trên sáu doctype cha.** Đây là phần chịu lực.
   Không có quyền nền thì Website User bị chặn ngay ở vòng kiểm role, **trên mọi đường gọi**:
   `/printview`, `download_pdf`, `frappe.client.get_list`, REST v1/v2, Desk.
2. `permission_query_conditions` cho cả 8 doctype — **lớp phòng thủ thứ hai**, hiện không bao giờ
   được gọi tới; chỉ sống lại nếu ai đó cấp lại `DocPerm` cho `Customer`.
3. `has_permission` hook + override trên class controller của hai bảng con — cũng là lớp hai.
4. **API whitelist tự suy kho từ phiên đăng nhập** (`get_portal_kho()`) rồi lọc tường minh theo kho
   đó. Đây là cổng **duy nhất** được phép của portal; nó an toàn **nhờ cấu trúc truy vấn**, không
   nhờ tầng phân quyền của framework.

**Hệ quả nghiệp vụ phải biết:** vì role `Customer` không có quyền doctype, người dùng cổng
**không dùng được `/printview`**. PDF phiếu kho đi qua endpoint whitelist `kho_phieu_pdf`, tự kiểm
sở hữu rồi render phía máy chủ.

**Hai bảng con `Customer Stock Receipt Item` / `Customer Stock Issue Item` cố ý KHÔNG có entry
`has_permission`.** `frappe.permissions.has_child_permission()` rẽ nhánh sang kiểm doctype **cha**
trước khi bất kỳ hook nào đăng ký cho chính doctype con có cơ hội chạy — một entry ở đó sẽ không
bao giờ được gọi, dù cấu hình thế nào. Thêm lại nó tạo ra một chốt chặn *trông có vẻ đúng* nhưng chết.

### 8.3 Ranh giới tin cậy

| Đường vào | Ai dùng | Kiểm gì |
|---|---|---|
| `/portal/*` (SPA) | Website User | Mọi lời gọi đi qua `api.portal.*` / `api.kho.*`; xác thực bằng session + CSRF |
| Desk | Nhân viên Miyano | Phân quyền ERPNext tiêu chuẩn |
| REST/`frappe.client.*` | — | Với 8 doctype kho: chặn ở vòng role, không có quyền nền |

**Lưu ý triển khai:** SPA gọi API bằng `fetch` + CSRF token, **không** dùng `frappe.call` — hàm đó
không tồn tại trên trang web (chỉ có trong Desk).

---

## 9. Tích hợp và sự kiện

| Sự kiện | Móc | Hướng | Tính chất |
|---|---|---|---|
| `Delivery Note.on_submit` | `kho.delivery_hook.on_delivery_note_submit` | ERPNext → kho khách | Sinh phiếu nhập **nháp**; không bao giờ ném lỗi |
| `Delivery Note.on_cancel` | `kho.delivery_hook.on_delivery_note_cancel` | ERPNext → kho khách | Gỡ phiếu nháp / đảo phiếu đã ghi sổ |
| Ghi sổ phiếu nhập/xuất | `kho.ledger.post_lines` | Phiếu → sổ kho | Ghi `Ledger Entry` + cập nhật `Lot Balance` |
| Huỷ phiếu | `_tao_phieu_dao` + `ledger.mark_reversed` | Phiếu → sổ kho | Bù trừ, không xoá |
| 5 `Notification` | Email | Hệ thống → khách | Người nhận lấy theo `contact_email` |

**Không có chiều ngược lại.** Phiếu kho của khách không tác động gì đến tồn kho, giá vốn, hay sổ
sách kế toán của Miyano. Đó là toàn bộ điểm của mục 2.2.

---

## 10. Báo cáo và chứng từ in

| Báo cáo | Cho khách (cổng) | Cho Miyano (Desk) | Nguồn dữ liệu |
|---|---|---|---|
| Tồn kho theo vật tư / theo lô | ✔ | ✔ (`Tồn kho khách hàng`) | `Customer Stock Lot Balance` |
| Nhập – xuất – tồn theo kỳ | ✔ | ✔ (`Nhập xuất tồn khách hàng`) | `Customer Stock Ledger Entry` |
| Thẻ kho một vật tư | ✔ | — | `Customer Stock Ledger Entry` |
| Cảnh báo hạn dùng | ✔ | ✔ (`Cảnh báo hạn dùng khách hàng`) | `Customer Stock Lot Balance` |
| Xuất Excel các báo cáo trên | ✔ | (sẵn có của Desk) | — |

Chứng từ in: phiếu nhập / phiếu xuất theo mẫu **TT107** (mặc định) hoặc **TT200**, chọn được cho
từng kho. Chứng từ bán hàng có mẫu in song ngữ.

---

## 11. Yêu cầu phi chức năng và vận hành

| Nhóm | Yêu cầu |
|---|---|
| Ngôn ngữ | Toàn bộ giao diện cổng bằng tiếng Việt; nhãn doctype tiếng Việt, tên doctype tiếng Anh |
| Tiền tệ | VND — không có phần thập phân khi hiển thị |
| Thiết bị | Cổng responsive, có xử lý riêng cho màn hình nhỏ (`useMobile.js`) |
| Cách ly dữ liệu | Xem mục 8 — yêu cầu ràng buộc nhất của hệ thống |
| Chịu lỗi | Trục trặc phía kho khách **không được** chặn nghiệp vụ giao hàng của Miyano (BR-K12) |
| Khôi phục | `Lot Balance` dựng lại được từ sổ; `replay_vouchers_into_ledger` dựng lại sổ từ phiếu |
| Idempotent | Toàn bộ script `setup/*` và patch chạy lại được nhiều lần |
| Kiểm thử | 339 test method trong 30 file, gồm test cách ly, test workflow, test e2e, test kịch bản UAT |
| Triển khai | Cài bằng `bench migrate`; SPA build sẵn vào `public/frontend/` |

Dữ liệu demo/UAT dựng đầy đủ bằng `setup/demo_kho_flow.py` (`chay_tat_ca`): tạo
"Bệnh viện Đa khoa Minh Đức (DEMO)", tài khoản cổng, hợp đồng nguyên tắc, kho, lô tồn đầu kỳ
trải đều các mốc hạn dùng, rồi chạy đơn hàng và phiếu kho qua đúng API mà khách dùng.

---

## 12. Vấn đề mở và rủi ro

| Mã | Vấn đề | Ảnh hưởng nghiệp vụ | Đề xuất | Trạng thái *(kiểm lại 2026-08-10 trên nhánh hiện tại)* |
|---|---|---|---|---|
| VĐ-1 | `frappe.desk.search.search_link` với `ignore_user_permissions=1` cho phép một tài khoản cổng bất kỳ kéo về sổ `Sales Invoice` của **khách hàng khác**, gồm cả `grand_total` và `outstanding_amount`. Ảnh hưởng `Sales Order` / `Delivery Note` / `Sales Invoice` | **Rò rỉ dữ liệu tài chính giữa các khách hàng** | Bọc bằng `override_whitelisted_methods`, ép tắt cờ và bỏ `filter_fields` với Website User | **Chưa sửa** — `hooks.py` chưa có `override_whitelisted_methods` |
| VĐ-2 | `reports.canh_bao_han_rows` lọc `han_su_dung <= han_toi`; query builder của Frappe bọc thành `ifnull()`, nên lô **không có hạn dùng** cũng lọt, rồi `getdate(None)` hiển thị chúng như hết hạn **hôm nay**, trạng thái "Sắp hết hạn" | Báo cáo cảnh báo hạn dùng nhiễu nặng — mọi lô đến từ `Delivery Note` trên site này đều là `KHONG-LO` không hạn | Chủ đầu tư quyết: loại bỏ hay tách nhóm riêng. (Màn `kho_ton` thì đúng — hiển thị "Không thời hạn") | **Chưa sửa** — bộ lọc ở `kho/reports.py:355-363` vẫn nguyên |
| VĐ-3 | Workflow đơn hàng cho `Sales User` thực hiện cả ba chuyển tiếp, kể cả vào trạng thái mà `allow_edit` là `Sales Manager` → không có duyệt hai tầng | Nhân viên kinh doanh tự xác nhận đơn của mình | Quyết định: giữ một tầng, hoặc đổi `allowed` của "Xác nhận"/"Từ chối" sang `Sales Manager` | **Cần quyết định** |
| VĐ-4 | Workflow áp cho **mọi** `Sales Order`, không riêng đơn từ cổng | Đơn nhập tay cũng phải đi qua máy trạng thái | Đã chấp nhận | Đã chấp nhận |
| VĐ-5 | Chưa có mẫu phiếu nhập/xuất thật mà BV Bạch Mai đang dùng | Phải dùng tạm TT107/TT200 | Lấy mẫu thật, thêm vào danh sách `Print Format` chọn theo kho | Chờ nghiệp vụ cung cấp |
| VĐ-6 | Một khách hàng chỉ một kho — ràng buộc `unique` ở tầng CSDL, không phải quy ước lỏng | Đơn vị nhiều kho (nhiều khoa/phòng, nhiều cơ sở) chưa dùng được | Mở rộng cần đổi schema (`customer` thôi `unique`) **và** đổi `get_portal_kho` từ trả về một chuỗi sang danh sách + cho người dùng chọn kho — không phải sửa nhỏ | Chưa cần; đánh giá nhu cầu trước |

---

## 13. Từ điển thuật ngữ

Bảng này chịu lực thật, không phải phụ lục cho đủ: tên doctype tiếng Anh còn tên trường tiếng Việt,
nên đọc mã nguồn mà không có nó rất dễ hiểu nhầm.

| Tiếng Việt | Tiếng Anh / kỹ thuật | Ghi chú |
|---|---|---|
| Hợp đồng nguyên tắc (HĐNT) | `Blanket Order` (Selling) | Kèm `Price List` + `Item Price` riêng cho khách |
| Hạn mức | quota | Trừ qua `against_blanket_order = 1` |
| Đơn hàng | `Sales Order` | Đơn từ cổng có `custom_nguon_don = "Client Portal"` |
| Phiếu giao hàng | `Delivery Note` | |
| Hoá đơn | `Sales Invoice` | |
| Kho (của khách) | `Customer Warehouse` | **Không** phải `Warehouse` của ERPNext |
| Vật tư | `Customer Warehouse Item` | Khác `Item` của ERPNext |
| Mã hàng Miyano | `item_code` | Rỗng = vật tư riêng của khách |
| Lô | `so_lo` | Chuỗi tự do, không phải `Batch` của ERPNext |
| Hạn dùng | `han_su_dung` | |
| Phiếu nhập kho | `Customer Stock Receipt` | |
| Phiếu xuất kho | `Customer Stock Issue` | |
| Sổ kho | `Customer Stock Ledger Entry` | Chỉ ghi thêm, nguồn sự thật |
| Tồn theo lô | `Customer Stock Lot Balance` | Cache dẫn xuất |
| Phiếu đảo | reversal voucher | Sinh tự động khi huỷ phiếu đã ghi sổ |
| Đã bị đảo | `da_dao` | Cờ trên dòng sổ gốc |
| Nháp / Đã ghi sổ / Đã huỷ | `docstatus` 0 / 1 / 2 | |
| Tồn đầu kỳ | opening stock | `loai_nhap = "Tồn đầu kỳ"` |
| Nhập – xuất – tồn (NXT) | opening / in / out / closing | |
| Thẻ kho | stock card / bin card | |
| FEFO | First Expired, First Out | Hết hạn trước, xuất trước |
| Thủ kho | storekeeper | `Customer Warehouse.thu_kho` |
| ĐVT | đơn vị tính / UoM | `dvt` |

---

## 14. Phụ lục — danh mục endpoint whitelist

Toàn bộ bề mặt API mà cổng gọi tới. Không có đường nào khác được phép.

**`miyano_portal.api.portal`** — `portal_me` · `portal_contracts` · `portal_catalog` ·
`portal_order_place` · `portal_order_history` · `portal_order_track` · `portal_deliveries` ·
`portal_invoices` · `portal_request_cancel` · `portal_provision` · `portal_document_download`

**`miyano_portal.api.kho`** — `kho_me` · `kho_ton` · `kho_lo` · `kho_vat_tu_list` ·
`kho_vat_tu_tao` · `kho_vat_tu_sua` · `kho_vat_tu_export` · `kho_vat_tu_import_preview` ·
`kho_vat_tu_import_commit` · `kho_import_template` · `kho_import_preview` · `kho_import_commit` ·
`kho_phieu_list` · `kho_phieu_get` · `kho_phieu_nhap_save` · `kho_phieu_xuat_save` ·
`kho_phieu_submit` · `kho_phieu_cancel` · `kho_dong_phieu_mau` · `kho_dong_phieu_doc_file` ·
`kho_dong_phieu_export` · `kho_lo_goi_y` · `kho_phieu_pdf` · `kho_bao_cao_nxt` · `kho_the_kho` ·
`kho_canh_bao_han` · `kho_bao_cao_excel`

---

## 15. Tài liệu liên quan

| Tài liệu | Nội dung |
|---|---|
| [`BA-v2-ngoai-le-va-UX-miyano_portal.md`](BA-v2-ngoai-le-va-UX-miyano_portal.md) | **Tài liệu v2 — luồng ngoại lệ & chuẩn giao diện.** 42 ngoại lệ chưa xử lý (NG-01…NG-42), 4 quyết định cần chủ đầu tư, 16 chuẩn UX, đặc tả trường cho 5 màn chính. Bao gồm các mục VĐ-1…VĐ-6 của tài liệu này, đã kiểm chứng lại |
| [`HDSD-tao-khach-hang-mo-kho-va-thao-tac-cong.md`](HDSD-tao-khach-hang-mo-kho-va-thao-tac-cong.md) | Hướng dẫn thao tác chi tiết cho quản trị viên và khách hàng |
| [`Workflow-miyano_portal.html`](Workflow-miyano_portal.html) | Sơ đồ quy trình trực quan, mở bằng trình duyệt, in được A4 |
| [`Workflow-UI-miyano_portal.html`](Workflow-UI-miyano_portal.html) | **Mô phỏng thao tác trên giao diện** — 29 bước bấm qua đúng màn hình thật của cổng và Desk Miyano, mỗi bước chú thích quy tắc nghiệp vụ (mã BR-*) đang chi phối. Mở thẳng một bước bằng `?step=N` |
| `superpowers/specs/2026-08-06-kho-khach-hang-design.md` | Thiết kế chi tiết kho khách hàng |
| `superpowers/specs/2026-08-07-vat-tu-va-import-export-dong-phieu-design.md` | Thiết kế danh mục vật tư và nhập/xuất Excel |
| `apps/erpnext/doc/DESIGN_supplycore_v2_client_portal.md` | Thiết kế cổng khách hàng (giai đoạn 1) |
