# Đặc tả giao diện — hiển thị & thao tác từng trường của từng form — `miyano_portal` v2.0

| Mục | Nội dung |
|---|---|
| Tài liệu cha | [`BA-miyano_portal_v2.md`](BA-miyano_portal_v2.md) — mã QT/UC/BR/NL trích dẫn từ đó |
| Ngày lập / phiên bản | 2026-08-11 — **v2.3** *(2.1: thêm F-21…F-23, khối HĐĐT ở F-08. 2.2: "Không giới hạn" khi hạn mức 0. 2.3 — 12/08: cấp phát khoa phòng — F-16 mở rộng, F-24 mới, tab cấp phát ở F-19 — QĐ-9)* |
| Nguồn chuẩn giao diện | `Mockup_Client_Portal_Miyano.html` + `..._Mobile.html` (V1, 27/07/2026) — token màu, badge, bố cục kế thừa nguyên trạng |
| Nhãn | **[Hiện có]** = màn hình/trường đã có trong SPA; **[MỚI]** = phải xây |

Cách đọc: mỗi form có (a) bảng trường, (b) hành động, (c) trạng thái màn hình, (d) ghi chú mobile.
Cột bảng trường: **Trường** · **Điều khiển** · **Nguồn / mặc định** · **BB** (bắt buộc) ·
**Ràng buộc & validate** · **Hành vi, thao tác, thông báo lỗi**.

---

## 1. Quy ước giao diện chung (áp dụng mọi form)

### 1.1 Token thị giác (từ mockup V1)

| Token | Giá trị | Dùng cho |
|---|---|---|
| `--blue` `#1f4e79` / `--blue2` `#2d6da3` | Màu chủ đạo Miyano | Nút chính, sidebar, tiêu đề số liệu |
| `--bg` `#f4f6f9` · `--line` `#e2e8f0` | Nền trang · viền | Card trắng, bo góc 12px, viền 1px |
| `--green #16a34a` · `--orange #ea580c` · `--red #dc2626` · `--gray #64748b` | Màu trạng thái | Badge, cảnh báo |
| Badge trạng thái đơn | xám=Chờ xác nhận · xanh dương=Đang xử lý · cam=Đang giao · xanh lá=Hoàn thành · đỏ=Đã huỷ/Quá hạn | Thống nhất toàn cổng, email, PDF |
| Badge phiếu kho | xám=Nháp · xanh lá=Đã ghi sổ · đỏ=Đã huỷ · cam viền=Có chênh lệch **[MỚI]** · vàng=Thiếu chứng từ **[MỚI]** | Danh sách + chi tiết phiếu |
| Input | viền `#cbd5e1`, bo 8px, focus outline `#93c5fd` 2px | Mọi ô nhập |

### 1.2 Định dạng dữ liệu

| Loại | Quy tắc |
|---|---|
| Tiền | `1.234.567 ₫`, không thập phân, căn phải; số âm (đối trừ) hiển thị `−1.234.567 ₫` màu đỏ |
| Ngày | `dd/mm/yyyy`; date picker tiếng Việt, tuần bắt đầu Thứ 2 |
| Số lượng | Tối đa 3 lẻ thập phân, bỏ số 0 thừa; căn phải; bàn phím mobile `inputmode="decimal"` |
| % | Số nguyên + thanh progress khi thể hiện mức dùng/mức giao |
| Tìm kiếm | Debounce 300ms, không phân biệt hoa thường và **không dấu** (tim "gang tay" ra "găng tay") |
| Mã chứng từ | Font mono, luôn là link mở chi tiết |

### 1.3 Hiển thị lỗi — 3 tầng, thống nhất toàn cổng

| Tầng | Khi nào | Cách hiển thị |
|---|---|---|
| Tại trường | Ngay khi rời ô (blur) hoặc gõ xong | Viền đỏ + dòng chữ đỏ 12px ngay dưới ô, nêu cách sửa ("SL phải là bội số của 10") |
| Tại dòng bảng | Lỗi thuộc một dòng (giỏ hàng, dòng phiếu, preview Excel) | Nền dòng hồng nhạt + icon ⚠ đầu dòng, tooltip liệt kê **đủ mọi lý do** của dòng (BR-K14) |
| Toàn form | Server trả lỗi khi lưu/ghi sổ/đặt hàng | Alert đỏ đầu form, liệt kê **tất cả** lỗi một lần (BR-O3), mỗi lỗi có anchor cuộn tới dòng/trường; form không mất dữ liệu đã nhập |

Quy tắc chung: **không dùng `alert()` trình duyệt**; lỗi server 5xx → thông điệp "Hệ thống đang bận,
dữ liệu của bạn chưa bị mất — thử lại" + nút thử lại; không bao giờ hiển thị traceback.

### 1.4 Trạng thái màn hình

| Trạng thái | Quy tắc |
|---|---|
| Đang tải | Skeleton (khung xám nhấp nháy) đúng hình dạng bảng/thẻ; không spinner toàn trang |
| Rỗng | Icon + 1 câu giải thích + 1 nút hành động chính (VD giỏ trống → "Vào Đặt hàng") |
| Đang gửi | Nút chính disable + spinner trong nút; mọi nút ghi/đặt **khoá chống bấm đúp** (BR-O12) |
| Chưa lưu | Rời trang khi form có thay đổi chưa lưu → hộp thoại xác nhận rời |
| Thành công | Toast xanh góc phải trên (desktop) / trên cùng (mobile), tự ẩn 4s, kèm link đối tượng vừa tạo |

### 1.5 Chuẩn mobile (< 900px — kế thừa mockup mobile V1)

- **Bottom nav 5 mục**: Tổng quan · Đặt hàng · Giỏ (badge số dòng) · Đơn hàng · **Kho** [MỚI].
  Hoá đơn & Hồ sơ đi từ Tổng quan (thẻ + menu avatar).
- Bảng → **thẻ dòng** (`rowline`): mỗi bản ghi một card, trường phụ xếp dọc; cột hành động thành nút full-width.
- Bộ lọc → **chips** cuộn ngang; ô số lượng → **stepper − / +**; hộp thoại → **bottom sheet**.
- Giỏ hàng có **thanh sticky** trên bottom nav: tổng tiền + nút "Xác nhận đặt hàng".
- Vùng chạm tối thiểu 44px; bảng dài giữ tiêu đề cột dính (sticky header) ở desktop.

---

## 2. Nhóm mua hàng

### F-01 Đăng nhập — `/portal/login` — UC-01 **[Hiện có]**

| Trường | Điều khiển | Nguồn / mặc định | BB | Ràng buộc & validate | Hành vi, thao tác, lỗi |
|---|---|---|---|---|---|
| Email đăng nhập | Input email, autofocus | — | ✔ | Định dạng email | Trim khoảng trắng; sai định dạng báo tại trường |
| Mật khẩu | Input password + nút 👁 hiện/ẩn | — | ✔ | ≥ 8 ký tự | Enter = đăng nhập |
| Đăng nhập | Nút chính full-width | — | — | — | Sai thông tin → thông điệp chung "Email hoặc mật khẩu không đúng" (không lộ email có tồn tại hay không); khoá tài khoản sau 5 lần sai → "Tài khoản tạm khoá, thử lại sau hoặc liên hệ Miyano" |
| Quên mật khẩu? | Link | — | — | — | Nhập email → gửi link đặt lại; thông điệp trung tính "Nếu email tồn tại, hướng dẫn đã được gửi" |
| Ghi chú cấp tài khoản | Text tĩnh | Hotline + email sales | — | — | — |

Trạng thái: tài khoản Disabled → như sai mật khẩu (không phân biệt). Chuyển hướng sau đăng nhập:
`/portal/dashboard`.

### F-02 Tổng quan — `/portal/dashboard` — UC-02 **[Hiện có, mở rộng]**

Màn chỉ đọc; đặc tả **khối hiển thị** thay cho bảng trường:

| Khối | Nội dung & nguồn | Thao tác |
|---|---|---|
| 4 thẻ KPI | Đơn chờ xác nhận · Đơn đang giao · Hoá đơn chưa thanh toán · Tổng công nợ (đỏ) — từ `portal_order_history`, `portal_invoices` | Bấm thẻ → danh sách tương ứng đã lọc sẵn |
| Đơn hàng gần đây | 5 đơn mới nhất: mã, ngày, giá trị, badge | Bấm dòng → chi tiết đơn |
| HĐNT đang hiệu lực | Số HĐ, hiệu lực, số mặt hàng, % hạn mức dùng (bar); cảnh báo vàng khi có mặt hàng ≥ 80%. **% và cảnh báo chỉ tính trên dòng có hạn mức > 0** — dòng "Không giới hạn" không vào mẫu số (BR-O15) | Bấm → danh mục đặt hàng |
| **Cảnh báo kho** [MỚI] | 2 thẻ: *Vật tư dưới mức tồn* (n) — từ `kho_canh_bao_ton`; *Lô sắp hết hạn 30 ngày* (n) — từ `kho_canh_bao_han`. Chỉ hiện khi khách có kho hoạt động | Bấm → màn dự trù / báo cáo hạn dùng |
| **Phiếu nhập chờ ghi sổ** [MỚI] | Số phiếu tự sinh còn nháp — nhắc thủ kho kiểm nhận | Bấm → danh sách phiếu nhập lọc Nháp |
| Nút "+ Đặt hàng mới" | Nút chính góc phải đầu trang | → F-03 |

### F-03 Danh mục đặt hàng theo HĐNT — `/portal/catalog` — UC-03/04 **[Hiện có, mở rộng]**

**Chế độ danh mục [MỚI — QT10]:** khách được bật mua lẻ (`custom_cho_phep_mua_le = 1`) thấy bộ
chuyển hai chế độ `Theo HĐNT | Mua lẻ` trên đầu trang (segmented control; mobile: 2 chips). Chế độ
Mua lẻ đặc tả tại **F-21**. Khách không được bật: không thấy bộ chuyển. Ô tìm kiếm không có kết
quả ở cả hai chế độ → empty state kèm nút **"Không tìm thấy hàng cần mua? Gửi yêu cầu"** → F-22.

| Trường | Điều khiển | Nguồn / mặc định | BB | Ràng buộc & validate | Hành vi, thao tác, lỗi |
|---|---|---|---|---|---|
| Hợp đồng nguyên tắc | Select | `portal_contracts`; tự chọn nếu chỉ có 1 HĐNT còn hiệu lực | ✔ | Chỉ HĐNT còn hiệu lực chọn để đặt được | HĐNT hết hiệu lực vẫn liệt kê nhưng disable + chú thích "Hết hiệu lực dd/mm/yyyy" (NL-1.1); đổi HĐNT khi giỏ có hàng → hỏi xác nhận (giỏ theo một HĐNT) |
| Tìm kiếm | Input + icon 🔍 | — | — | — | Theo mã + tên, không dấu, debounce 300ms; rỗng kết quả → "Không có mặt hàng khớp — mặt hàng ngoài HĐNT không hiển thị" |
| Nhóm hàng | Select (desktop) / chips (mobile) | Nhóm distinct trong HĐNT + "Tất cả" | — | — | Lọc tức thời |
| **Bảng mặt hàng** — mỗi dòng: | | | | | |
| · Mã / Tên / quy cách | Text 2 dòng + tag "VAT n%" | `portal_catalog` | — | — | — |
| · ĐVT | Text | Item UOM | — | — | — |
| · Đơn giá (chưa VAT) | Tiền, căn phải | `Item Price` của Price List khách | — | Chỉ đọc — khách không bao giờ sửa được giá | Thiếu giá → dòng disable + "Chưa có giá — đã báo Miyano" (NL-1.4) |
| · Hạn mức còn lại | `còn/tổng ĐVT` + progress bar | `Blanket Order` | — | — | Bar đỏ khi dùng ≥ 80% + nhãn "Sắp hết hạn mức"; đã đặt đủ tổng → dòng disable, nhãn "Hết hạn mức" (NL-1.2). **Hạn mức khai 0 → badge "Không giới hạn"** (không bar, không khoá SL; hiển thị kèm "đã đặt n ĐVT" để tham khảo — BR-O15/NL-1.11) [MỚI] |
| · Tình trạng hàng | Badge "Còn hàng"/"Liên hệ" | Tính phía server, không lộ số tồn | — | — | FR-B6 — tuỳ chọn bật theo cấu hình |
| · Số lượng | Input số (desktop) / stepper (mobile) | 1 hoặc = bội số | — | > 0; bội số quy cách nếu có (BR-O11); ≤ hạn mức còn lại — **bỏ giới hạn max với dòng "Không giới hạn"** (BR-O15) | Bước nhảy stepper = bội số; sai → lỗi tại dòng nêu số đúng gần nhất |
| · + Giỏ | Nút nhỏ | — | — | — | Thêm/cộng dồn vào giỏ; toast "Đã thêm n ĐVT"; badge giỏ ở nav cập nhật; vượt hạn mức → lỗi tại dòng kèm số tối đa còn đặt được (NL-1.3) |

### F-04 Giỏ hàng & xác nhận đơn — `/portal/cart` — UC-05/15 **[Hiện có, mở rộng]**

**Giỏ hai ngăn [MỚI — BR-R2]:** tab `Theo HĐNT (n)` / `Mua lẻ (m)` — tab Mua lẻ chỉ hiện khi khách
được bật. Mỗi ngăn có bảng dòng, khối tổng tiền và nút xác nhận **riêng**; đặt thành hai đơn riêng.
Badge giỏ trên nav = tổng dòng hai ngăn. Ngăn Mua lẻ: không có cột hạn mức; chú thích cố định
"Đơn mua lẻ ngoài HĐNT — Miyano sẽ xác nhận trước khi giao"; modal xác nhận dùng câu điều khoản
riêng (không nhắc HĐNT).

| Trường | Điều khiển | Nguồn / mặc định | BB | Ràng buộc & validate | Hành vi, thao tác, lỗi |
|---|---|---|---|---|---|
| Bảng dòng giỏ: mặt hàng · ĐVT · đơn giá · SL · thành tiền · xoá | SL: input/stepper; xoá: nút ✕ | Giỏ lưu **phía máy chủ** theo tài khoản (giữ khi đăng xuất — NL-1.9) | ✔ ≥1 dòng | SL: như F-03 (bội số, hạn mức — revalidate khi sửa) | Sửa SL → tổng tiền cập nhật tức thời; xoá dòng → undo trong toast 5s; giỏ trống → empty state |
| Ngày giao mong muốn | Date picker | +2 ngày làm việc từ hôm nay (BR-O13) | ✔ | Không quá khứ; bỏ qua T7/CN khi tính mặc định | Chọn ngày quá khứ → chặn tại trường, gợi ý ngày hợp lệ gần nhất (NL-1.7) |
| Địa chỉ giao hàng | Select | Danh sách `Address` của Customer; mặc định = địa chỉ mặc định | ✔ | Chỉ địa chỉ thuộc đơn vị mình (BR-O1) | Kèm dòng địa chỉ đầy đủ dưới select; cần thêm địa chỉ → chú thích "liên hệ Miyano" |
| Số dự trù / PO của đơn vị | Input text, placeholder "VD: DT-2026-0715" | — | — | ≤ 50 ký tự | In lên chứng từ (`custom_so_po_khach`) |
| Ghi chú | Textarea 2–4 dòng | — | — | ≤ 500 ký tự, đếm ký tự | `custom_yeu_cau_khach` |
| Khối tổng tiền | Chỉ đọc: Tạm tính · **VAT tách từng thuế suất** (dòng "VAT 5%", "VAT 8%") · Tổng cộng | Tính từ giỏ | — | — | Cập nhật realtime; số làm tròn đồng |
| Xác nhận đặt hàng → | Nút chính | — | — | Giỏ ≥ 1 dòng hợp lệ | Mở **modal xác nhận**: tóm tắt HĐNT, số dòng, tổng tiền + câu điều khoản "đồng ý đặt theo đơn giá và điều khoản HĐNT đã ký"; nút [Quay lại] [Xác nhận] |
| (ẩn) `request_id` | — | UUID sinh khi mở modal | — | BR-O12 | Bấm Xác nhận → nút khoá + spinner; timeout/gửi lại dùng cùng id → nhận về đơn đã tạo, không tạo trùng (NL-1.8); lỗi hạn mức server → alert đầu form liệt kê đủ mã hàng + số còn lại, giỏ giữ nguyên |

### F-05 Đặt hàng thành công — UC-05 **[Hiện có]**

Khối giữa trang: icon ✅ · "Đặt hàng thành công!" · mã đơn (mono, đậm) + badge "Chờ xác nhận" ·
dòng "Email xác nhận đã gửi tới …" · 2 nút: [Xem đơn hàng] [Tiếp tục đặt hàng]. Không có nút Back
tạo lại đơn (giỏ đã trống, `request_id` đã dùng).

### F-06 Đơn hàng của tôi — `/portal/orders` — UC-06 **[Hiện có]**

| Trường | Điều khiển | Nguồn / mặc định | BB | Ràng buộc & validate | Hành vi, thao tác, lỗi |
|---|---|---|---|---|---|
| Lọc trạng thái | Select: Tất cả / Chờ xác nhận / Đang xử lý / Đang giao / Hoàn thành / Đã huỷ | Tất cả | — | Nhãn theo BR-O7 | Lọc server-side, giữ trong URL (share/back được) |
| Khoảng ngày đặt | Date range | 90 ngày gần nhất | — | từ ≤ đến | — |
| Tìm mã đơn | Input | — | — | — | Khớp một phần mã SO |
| Bảng: Mã đơn · Ngày đặt · Ngày giao Y/C · Giá trị · **Đã giao** · Trạng thái · Hành động | — | `portal_order_history` | — | — | "Đã giao" = % + mini progress (theo đợt — QT3); hành động theo trạng thái: Chờ xác nhận → [Huỷ/Sửa]; còn lại → [Chi tiết]; phân trang 20 dòng |

### F-07 Chi tiết đơn hàng — `/portal/orders/:name` — UC-07/08/10/14 **[Hiện có, mở rộng]**

| Khối / trường | Hiển thị | Thao tác & lỗi |
|---|---|---|
| Đầu trang | Mã đơn + badge trạng thái; ngày đặt · HĐNT · số PO khách; lý do từ chối (nếu Từ chối — NL-2.1) | [⬇ PDF đơn hàng] · [← Quay lại] · [🔁 Đặt lại đơn này] **[MỚI]** (UC-14): điền lại giỏ theo giá hiện hành, thông báo các mặt hàng bị loại (hết hạn mức/ngoài HĐNT) |
| Timeline 5 bước | Đặt hàng → Miyano xác nhận → Soạn hàng → Giao hàng → Hoá đơn; bước xong = xanh + timestamp, bước hiện tại = cam | Chỉ đọc |
| Bảng dòng hàng | Mặt hàng · ĐVT · SL đặt · **Đã giao** · **Còn lại** · Đơn giá · Thành tiền | SL do Miyano sửa trước xác nhận hiển thị giá trị mới + icon 🕑 lịch sử (NL-2.3) |
| **Khối các đợt giao** [MỚI — QT3] | Mỗi đợt một thẻ: "Đợt n — dd/mm/yyyy (x%)" · số phiếu giao (link PDF) · hãng vận chuyển + AWB nếu có · **trạng thái nhập kho** (nếu khách có kho): "Phiếu nhập PNK-xxx — Nháp, chờ kiểm nhận" (link sang F-15) hoặc "Đã ghi sổ" hoặc "Có chênh lệch ⚠" | Bấm thẻ đợt → mở phiếu giao/phiếu nhập; đợt kế tiếp dự kiến hiển thị "Đang soạn hàng tại kho Miyano" |
| Yêu cầu huỷ | Nút — **chỉ hiện khi Chờ xác nhận** (BR-O8) | Modal: lý do bắt buộc (≥ 10 ký tự) → gửi `portal_request_cancel`; toast "Đã gửi yêu cầu — Miyano sẽ xử lý"; sau khi xác nhận chỉ còn [💬 Yêu cầu hỗ trợ] (NL-2.2, TC-D-07) |
| Yêu cầu hỗ trợ | Nút luôn hiện | Modal nội dung tự do ≤ 1000 ký tự → ghi Comment vào đơn + báo sales |
| **Đơn mua lẻ** [MỚI — QT10] | Badge "Mua lẻ" cạnh trạng thái; không hiển thị HĐNT/hạn mức; nếu lập từ yêu cầu → link "Từ yêu cầu YCH-xxx" | Chỉ đọc |
| **Trạng thái "Chờ bạn đồng ý"** [MỚI — QĐ-6] | Banner cam: giá trị đơn + "Báo giá hiệu lực đến dd/mm/yyyy" + bảng dòng giá sales đã chốt | [✔ Đồng ý đặt hàng] → modal xác nhận ("đồng ý đặt theo giá trên", log người bấm + thời điểm) → `portal_order_accept` → trạng thái "Chờ Miyano xác nhận"; [✕ Không đồng ý] → lý do bắt buộc ≥ 10 ký tự → về sales xử lý (NL-10.4); quá hạn hiệu lực → banner xám "Báo giá đã hết hiệu lực" + nút [Yêu cầu báo giá lại] → F-22 (NL-10.5) |

### F-08 Hoá đơn & công nợ — `/portal/invoices` — UC-09 **[Hiện có, mở rộng]**

| Khối / trường | Hiển thị | Thao tác |
|---|---|---|
| 3 thẻ KPI | Tổng công nợ hiện tại (đỏ) · Quá hạn thanh toán (cam) · Hoá đơn đến hạn 7 ngày (n) | Bấm → lọc bảng tương ứng |
| Bảng hoá đơn | Số HĐ · Ngày · Đơn hàng liên quan (link) · Giá trị · Đã thanh toán · Hạn TT · Badge (Chưa TT / TT một phần / Đã TT / Quá hạn / Trả hàng / Đã huỷ) · [⬇ PDF] | Hoá đơn điều chỉnh (Credit Note) giá trị âm đỏ, badge "Trả hàng" (NL-6.2) |
| Mở rộng dòng **[MỚI]** (NL-6.4) | Bấm dòng → xổ lịch sử thanh toán: số `Payment Entry`, ngày, số tiền | Chỉ đọc |
| **Khối HĐĐT** [MỚI — UC-18, QT12] | Trong phần mở rộng dòng: badge trạng thái HĐĐT (Đang phát hành / Đã phát hành / Đã huỷ / Bị thay thế / Bị điều chỉnh) · số + ký hiệu · ngày phát hành · mã tra cứu + nút 📋 copy · chú thích cố định *"File XML là bản gốc có giá trị pháp lý; PDF là bản thể hiện"* | [⬇ XML gốc] [⬇ PDF] chỉ hiện khi "Đã phát hành" (BR-E2), gọi `portal_einvoice_download` — kiểm sở hữu từng lần, không có URL công khai (BR-E4); [🔗 Tra cứu] mở tab hệ thống CQT; "Đang phát hành HĐĐT" → không nút tải (NL-12.1); huỷ/thay thế/điều chỉnh → badge + link hoá đơn liên quan hai chiều (NL-12.2/12.3); file lỗi → nút disable + [Yêu cầu hỗ trợ] tự đính mã hoá đơn (NL-12.4) |

### F-09 Hồ sơ đơn vị — `/portal/profile` — UC-12 **[Hiện có]**

Toàn bộ **chỉ đọc** (dữ liệu do Miyano quản lý — muốn sửa liên hệ sales): thông tin đơn vị + MST;
bảng HĐNT (số, hiệu lực, số mặt hàng, % hạn mức + bar — chỉ tính dòng có hạn mức > 0, dòng "Không giới hạn" ghi chú riêng; HĐNT hết hiệu lực mờ); danh sách người dùng
cổng (tên, email, vai trò); danh sách địa chỉ giao; sales phụ trách (tên, SĐT, email). Nút duy nhất:
[Đổi mật khẩu] → form mật khẩu cũ / mới ×2, quy tắc ≥ 8 ký tự.

---

## 3. Nhóm kho khách hàng

### F-10 Kho — Tồn kho — `/portal/kho` — UC-20/21/22 **[Hiện có]**

| Trường | Điều khiển | Nguồn / mặc định | BB | Ràng buộc & validate | Hành vi, thao tác, lỗi |
|---|---|---|---|---|---|
| Đầu trang | Tên kho, thủ kho, ngày bắt đầu | `kho_me` | — | — | Kho tắt → toàn phần kho hiển thị màn "Kho tạm ngừng — liên hệ Miyano" (NL-4.8) |
| Tìm vật tư | Input | — | — | — | Không dấu, theo mã + tên |
| Bảng tồn: Mã VT · Tên · ĐVT · Tồn hiện tại · Giá trị tồn · Số lô · Cảnh báo | Chỉ đọc | `kho_ton` | — | — | Cột cảnh báo: badge "Sắp hết hạn" (lô gần nhất < 30 ngày) / "Không thời hạn" / **"Dưới mức tồn"** [MỚI] khi tồn < min |
| Mở rộng dòng (tồn theo lô) | Bấm dòng → xổ bảng lô | `kho_lo` | — | — | Cột: Số lô · Hạn dùng (đỏ nếu < 30 ngày, "Không thời hạn" nếu rỗng) · Tồn lô · Đơn giá BQ lô · Giá trị |
| Nút nhanh | [+ Phiếu nhập] [+ Phiếu xuất] | — | — | — | → F-15 / F-16 |

### F-11 Kho — Danh mục vật tư — `/portal/kho/vat-tu` — UC-23/24 **[Hiện có, mở rộng]**

Danh sách: tìm kiếm, bảng (Mã VT · Tên · ĐVT · Quy cách · Mã hàng Miyano nếu có · Tồn · Min/ROP/Max
[MỚI] · Trạng thái), nút [+ Thêm vật tư] [⬆ Nhập Excel] [⬇ Xuất Excel].

**Form thêm/sửa vật tư** (modal desktop / trang mobile):

| Trường | Điều khiển | Nguồn / mặc định | BB | Ràng buộc & validate | Hành vi, thao tác, lỗi |
|---|---|---|---|---|---|
| Tên vật tư | Input | — | ✔ | ≤ 200 ký tự | Lưu → so gần đúng với danh mục: có tên giống ≥ 85% → cảnh báo mềm liệt kê, [Vẫn tạo]/[Huỷ] (NL-4.5) |
| ĐVT | Input gợi ý (hộp, cái, chai…) | — | ✔ | — | — |
| Quy cách đóng gói | Input | — | — | — | VD "Hộp 100 cái" |
| Mã hàng Miyano | Chỉ đọc | Tự gắn khi phiếu Miyano tạo VT (BR-K3) | — | Không sửa tay | Rỗng = vật tư riêng của khách |
| Nhóm vật tư | Select tự do (tạo mới được) | — | — | — | Dùng cho lọc & báo cáo |
| **Bội số đặt** [MỚI] | Input số | — | — | Số nguyên > 0 | Dùng làm bước nhảy khi đặt bổ sung (BR-P4) |
| **Tồn tối thiểu (min)** [MỚI] | Input số | — | — | ≥ 0 | Cạnh nút [💡 Gợi ý từ tiêu thụ] → gọi `kho_min_max_goi_y`, điền 3 ô + chú thích "ADU 90 ngày = x/ngày"; chưa đủ dữ liệu → "Chưa đủ 30 ngày dữ liệu" (NL-9.1) |
| **Điểm đặt lại (ROP)** [MỚI] | Input số | — | — | ≥ min | Tooltip công thức BR-P2 |
| **Tồn tối đa (max)** [MỚI] | Input số | — | — | ≥ ROP | — |
| **Lead time (ngày)** [MỚI] | Input số | 3 | — | 1–60 | Thời gian từ đặt đến nhận |
| Trạng thái | Toggle Hoạt động | Bật | — | — | Vật tư đã có phát sinh sổ → không xoá được, chỉ tắt |

### F-12 / F-13 Nhập Excel (danh mục vật tư / tồn đầu kỳ) — UC-26/27 **[Hiện có]**

Chung một khuôn 4 bước (BR-K14), thanh bước hiển thị trên đầu:

| Bước | Nội dung | Hành vi & lỗi |
|---|---|---|
| 1. Tải mẫu | Nút [⬇ Tải file mẫu] (`kho_import_template` / `kho_dong_phieu_mau`) | File mẫu có sẵn dòng ví dụ + chú thích từng cột |
| 2. Tải lên | Vùng kéo-thả + nút chọn file | Chỉ .xlsx; > 5MB hoặc sai định dạng → báo ngay |
| 3. Xem trước | Bảng toàn bộ dòng đọc được; đếm "n hợp lệ · m lỗi"; lọc [Chỉ xem dòng lỗi] | Dòng lỗi nền hồng, tooltip **đủ mọi lý do**; sửa trực tiếp trên ô trong bảng preview → revalidate tức thời; không dòng nào bị âm thầm bỏ |
| 4. Ghi | Nút [Ghi n dòng hợp lệ] | Còn m dòng lỗi → hộp xác nhận "Bỏ qua m dòng lỗi?"; riêng **tồn đầu kỳ**: kho đã nhập tồn đầu → chặn từ bước 2 kèm hướng dẫn dùng Điều chỉnh kiểm kê (BR-K21, NL-4.4); ghi xong → toast + link phiếu/danh mục |

### F-14 Kho — Danh sách phiếu nhập / phiếu xuất — `/portal/kho/nhap`, `/portal/kho/xuat` — UC-28 **[Hiện có, mở rộng]**

| Trường | Điều khiển | Mặc định | Hành vi |
|---|---|---|---|
| Tab | Phiếu nhập / Phiếu xuất | Theo URL | — |
| Lọc trạng thái | Chips: Tất cả · Nháp · Đã ghi sổ · Đã huỷ | Tất cả | Badge đếm phiếu Nháp cần xử lý |
| Lọc loại phiếu | Select theo `loai_nhap`/`loai_xuat` | Tất cả | — |
| **Lọc nguồn** [MỚI] | Select: Miyano / NCC khác (chọn NCC) / Khác | Tất cả | Phục vụ tra theo nguồn cung |
| **Lọc cờ** [MỚI] | Checkbox: Có chênh lệch · Thiếu chứng từ | Tắt | NL-3.3, NL-7.2 |
| Khoảng ngày | Date range | 30 ngày | — |
| Bảng | Số phiếu · Ngày · Loại · Nguồn/NCC · Tham chiếu (DN/SO/chứng từ NCC) · Số dòng · Tổng SL · Tổng giá trị · Badge trạng thái + cờ | Bấm dòng → F-15/F-16; nút [+ Lập phiếu] |

### F-15 Kho — Phiếu nhập — `/portal/kho/nhap/:name` — UC-29/32/33/34/35/36/47 **[Hiện có, mở rộng]**

Ba biến thể cùng một form: **(a)** tự sinh từ Miyano, **(b)** mua ngoài NCC khác [MỚI], **(c)** khác
(tồn đầu kỳ/điều chỉnh/nhập khác). Trường không thuộc biến thể thì ẩn.

**Phần đầu phiếu:**

| Trường | Điều khiển | Nguồn / mặc định | BB | Ràng buộc & validate | Hành vi, thao tác, lỗi |
|---|---|---|---|---|---|
| Số phiếu | Chỉ đọc | Hệ cấp khi lưu | — | — | Font mono |
| Trạng thái | Badge | Nháp | — | — | + cờ "Có chênh lệch" / "Thiếu chứng từ" khi có |
| Loại nhập | Select: Tồn đầu kỳ · Từ đơn hàng Miyano · **Mua ngoài (NCC khác)** [MỚI] · **Điều chỉnh kiểm kê (tăng)** [MỚI] · Nhập khác | Tay: "Mua ngoài" | ✔ | "Phiếu đảo" **không có trong lựa chọn** người dùng (BR-K9); "Từ đơn hàng Miyano" chỉ do hệ tạo | Đổi loại → hiện/ẩn nhóm trường nguồn |
| Ngày phiếu | Date | Hôm nay | ✔ | ≥ `ngay_bat_dau` kho (BR-K10); không tương lai | Lỗi tại trường |
| **NCC** *(biến thể b)* | Select tìm kiếm + [+ Tạo nhanh] | `kho_ncc_list` | ✔ khi Mua ngoài (BR-N1) | NCC active của kho | Tạo nhanh mở modal F-17 thu gọn (tên + SĐT); thiếu → chặn lưu |
| **Số chứng từ NCC** *(b)* | Input | — | — (BR-N2) | ≤ 50 ký tự | Bỏ trống → khi lưu hỏi nhẹ "Chưa có số chứng từ — phiếu sẽ gắn cờ Thiếu chứng từ"; bổ sung sau được khi phiếu còn nháp |
| **Ngày chứng từ** *(b)* | Date | — | — | ≤ ngày phiếu | — |
| Tham chiếu Miyano *(a)* | Chỉ đọc: link SO · link DN · **Đợt n** | Hook điền | — | Không sửa | Bấm mở chứng từ gốc |
| Ghi chú | Textarea | — | — | ≤ 500 | — |

**Bảng dòng phiếu** (thêm dòng: [+ Dòng] · [⬆ Nhập dòng từ Excel] · [⬇ Xuất Excel]):

| Cột | Điều khiển | BB | Ràng buộc & validate | Hành vi, lỗi |
|---|---|---|---|---|
| Vật tư | Select tìm kiếm trong danh mục kho + [+ Tạo nhanh] | ✔ | Thuộc kho (BR-K2) | Tạo nhanh: tên + ĐVT (NL-7.4); biến thể (a): chỉ đọc |
| ĐVT | Tự điền theo vật tư | — | — | Chỉ đọc |
| Số lô | Input, tự UPPER + trim | — | — | Rỗng → hệ ghi `KHONG-LO`; biến thể (a): chỉ đọc từ bundle lô |
| Hạn dùng | Date | — | — | Quá khứ → cảnh báo vàng "Lô đã quá hạn" (vẫn cho nhập — hàng thật có thể như vậy); (a): chỉ đọc; rỗng + có lô → dòng gắn nhãn "thiếu hạn" (NL-3.7) |
| **SL giao** *(a)* [MỚI] | Chỉ đọc | Từ DN | — | — | Mốc đối soát |
| SL thực nhận | Input số | ✔ | > 0; **(a): ≤ SL giao** (BR-K17, NL-3.10) | (a): nhập < SL giao → ô "Lý do chênh lệch" của dòng bật bắt buộc |
| **Lý do chênh lệch** *(a)* [MỚI] | Input | ✔ khi lệch | ≥ 5 ký tự | VD "thiếu 2 hộp", "vỡ 1 chai" |
| Đơn giá | Input tiền | ✔ | ≥ 0 | (a): chỉ đọc theo DN; giá đi theo lô (BR-K6) |
| Thành tiền | Tự tính | — | — | Chỉ đọc |

**Hành động phiếu:**

| Nút | Điều kiện hiện | Hành vi |
|---|---|---|
| [Lưu nháp] | Nháp | Validate mềm; lỗi liệt kê nhưng vẫn lưu được nếu chỉ là cảnh báo (BR-K14) |
| [Ghi sổ] | Nháp, ≥ 1 dòng hợp lệ | Modal xác nhận: số dòng, tổng SL, tổng giá trị; (a) có chênh lệch → cảnh báo cam liệt kê dòng lệch + "Miyano sẽ nhận được thông báo chênh lệch" (NL-3.3); xác nhận → tồn tăng, badge Đã ghi sổ, khoá toàn form |
| [Huỷ phiếu] | Đã ghi sổ | Modal đỏ: "Sổ kho không xoá dòng — hệ thống sẽ tạo **phiếu đảo** ngược dấu" + lý do bắt buộc; bị chặn khi hàng đã xuất (NL-5.2) → thông điệp nêu lô còn bao nhiêu, hướng dẫn huỷ phiếu xuất trước |
| [⬇ In phiếu PDF] | Mọi trạng thái | `kho_phieu_pdf` — mẫu TT107/TT200 theo cấu hình kho |

### F-16 Kho — Phiếu xuất — `/portal/kho/xuat/:name` — UC-30/31/32/33 **[Hiện có, mở rộng]**

Phần đầu như F-15 (không có nhóm trường NCC). Loại xuất: Xuất sử dụng · Xuất huỷ - hết hạn ·
Xuất trả lại · Điều chỉnh kiểm kê ("Phiếu đảo" không trong lựa chọn).

**Nhóm trường cấp phát [MỚI — QĐ-9]**, chỉ hiện với loại "Xuất sử dụng":

| Trường | Điều khiển | BB | Ràng buộc & validate | Hành vi, lỗi |
|---|---|---|---|---|
| Khoa phòng nhận | Select tìm kiếm từ danh mục khoa phòng của kho + [+ Tạo nhanh] | ✔ khi kho bật `bat_buoc_khoa_phong` (BR-CP2) | Chỉ khoa `active` | Thiếu khi bắt buộc → chặn ở **ghi sổ** (NL-4.11), phiếu nháp cũ trước khi bật cờ không bị khoá; khoa bị tắt còn trên nháp → cảnh báo chọn lại (NL-4.12) |
| Người nhận | Input tự do + autocomplete | — | ≤ 100 ký tự | Gợi ý từ lịch sử phiếu của **chính khoa đã chọn** (`kho_nguoi_nhan_goi_y` — BR-CP3); nên nhập với hoá chất |

Khoa phòng + người nhận in lên phiếu (mẫu TT107/TT200 — phần "người nhận" có sẵn, ký trên bản giấy).

**Bảng dòng phiếu xuất:**

| Cột | Điều khiển | BB | Ràng buộc & validate | Hành vi, lỗi |
|---|---|---|---|---|
| Vật tư | Select tìm kiếm | ✔ | Thuộc kho; hiển thị **tồn khả dụng** cạnh tên | — |
| SL cần xuất | Input số | ✔ | > 0 | Nhập xong → nút [💡 Gợi ý lô FEFO] sáng |
| Phân bổ lô | Bảng con mỗi dòng: Lô · Hạn dùng · Tồn lô · SL lấy | ✔ tổng = SL cần | SL lấy ≤ tồn lô | [Gợi ý FEFO] (`kho_lo_goi_y`): tự điền theo hạn gần nhất trước, lô không hạn cuối (BR-K13) — **chỉ gợi ý, sửa tay được**; lô đã quá hạn + loại "Xuất sử dụng" → dòng cảnh báo đỏ, khi ghi sổ bắt tick "Tôi xác nhận xuất lô quá hạn" hoặc đổi loại "Xuất huỷ - hết hạn" (BR-K20, NL-4.9) |
| Đơn giá | Tự theo giá BQ lô | — | Chỉ đọc | BR-K6 |
| Thành tiền | Tự tính | — | — | — |

Hành động như F-15. Riêng [Ghi sổ]: chốt chặn tồn âm tại server (BR-K5, NL-4.1) — lỗi trả về nêu
đúng "lô L123 chỉ còn 5 hộp, phiếu cần 8" và giữ nguyên phiếu nháp.

### F-17 Kho — NCC của tôi — `/portal/kho/ncc` — UC-42 **[MỚI]**

Danh sách: tìm kiếm, bảng (Tên NCC · MST · SĐT · Email · Số phiếu đã nhập · Giá trị 90 ngày ·
Trạng thái), nút [+ Thêm NCC].

| Trường (form) | Điều khiển | BB | Ràng buộc & validate | Hành vi, lỗi |
|---|---|---|---|---|
| Tên NCC | Input | ✔ | ≤ 200 ký tự; unique trong kho (BR-N3) | Gõ xong kiểm gần đúng: giống NCC có sẵn → gợi ý chọn thay vì tạo (NL-7.3); trùng tuyệt đối → chặn |
| MST | Input | — | 10 hoặc 13 chữ số nếu nhập | Lỗi định dạng tại trường |
| SĐT / Email / Địa chỉ / Ghi chú | Input | — | Email đúng định dạng | — |
| Trạng thái | Toggle Hoạt động | — | — | NCC đã dùng trên phiếu: không xoá, chỉ tắt; tắt rồi không chọn được trên phiếu mới |

### F-18 Kho — Nhật ký vật tư — `/portal/kho/nhat-ky` — UC-43 **[MỚI]**

| Trường | Điều khiển | Mặc định | Hành vi |
|---|---|---|---|
| Vật tư | Select tìm kiếm | — (bắt buộc chọn trước khi có dữ liệu) | Empty state: "Chọn vật tư để xem nhật ký" |
| Kỳ | Date range | 30 ngày | Bắt buộc chọn kỳ khi xuất Excel (NL-8.3) |
| Lọc thêm | Chips: Lô · Loại phiếu · Nguồn (Miyano/NCC/khác) · Đợt | Tất cả | — |
| Bảng nhật ký | Ngày · Số phiếu (link) · Loại · Nguồn/NCC · Đợt · Lô · Hạn dùng · SL nhập · SL xuất · Đơn giá · **Tồn sau giao dịch** · Người ghi sổ | — | Chỉ đọc (BR-D2); dòng `da_dao=1` mờ + nhãn "đã đảo" (NL-8.2); phân trang server 50 dòng; [⬇ Excel] |

### F-19 Kho — Báo cáo — `/portal/kho/bao-cao` — UC-37/38/39/40/44 **[Hiện có, mở rộng]**

Tab chọn báo cáo; mọi tab có [⬇ Excel]; bộ lọc chung: kỳ (mặc định tháng hiện tại), vật tư, nhóm.

| Tab | Cột chính | Ghi chú |
|---|---|---|
| NXT theo kỳ [Hiện có] | VT · ĐVT · Tồn đầu (SL/GT) · Nhập · Xuất · Tồn cuối | — |
| Thẻ kho [Hiện có] | Ngày · Chứng từ · Diễn giải · Nhập · Xuất · Tồn | Một vật tư/kỳ; in được theo mẫu |
| Cảnh báo hạn dùng [Hiện có, mở rộng] | Lô · VT · Hạn · Tồn · Số ngày còn | Nhóm: Đã hết hạn (đỏ) · ≤ 30 ngày (cam) · ≤ 90 ngày (vàng) · **"Không có hạn dùng" tách nhóm riêng, không tính sắp hết hạn** (VĐ-2) |
| **NXT theo đợt hàng** [MỚI — UC-44] | Đợt (phiếu nhập, link) · Ngày nhận · Nguồn/NCC · Chứng từ · VT · Lô · SL nhập · GT nhập · **Đã xuất** · **Còn lại** · Tuổi tồn (ngày) · %TT | Phân bổ FIFO trong lô (BR-D1) — chú thích ngay dưới tiêu đề; cờ đỏ "chậm luân chuyển" khi tuổi > ngưỡng (BR-D3) |
| **Cấp phát theo khoa phòng** [MỚI — UC-56, QĐ-9] | Khoa phòng · VT · ĐVT · SL · Giá trị · Người nhận · Số phiếu (link) — nhóm theo khoa, dòng tổng %/khoa | Lọc kỳ + khoa + vật tư; dòng "Chưa gắn khoa" tách riêng (phiếu cũ/kho không bắt buộc); drill mở đúng phiếu xuất |

### F-20 Kho — Dự trù & mức tồn — `/portal/kho/du-tru` — UC-45/46 **[MỚI]**

| Khối / trường | Hiển thị / điều khiển | Hành vi, lỗi |
|---|---|---|
| 3 thẻ đếm | Thiếu tồn (dưới min) · Chạm điểm đặt lại · Chưa thiết lập min/max | Bấm → lọc bảng |
| Bảng vật tư | VT · Tồn khả dụng · ADU 30/90 ngày · **Ngày phủ tồn** · Min · ROP · Max (3 ô sửa inline) · Trạng thái (badge: Đủ / Sắp thiếu / **Thiếu** đỏ) · Hành động | Min/ROP/Max sửa inline, lưu từng dòng, validate min ≤ ROP ≤ max; ADU trống nếu < 30 ngày dữ liệu → tooltip NL-9.1 |
| [💡 Gợi ý] (từng dòng / chọn nhiều) | Gọi `kho_min_max_goi_y` | Điền gợi ý theo BR-P2 vào 3 ô — **chưa lưu**, người dùng xem rồi bấm lưu; hiển thị cả ADU 30 và 90 để tự đối chiếu đột biến (NL-9.2) |
| [🛒 Thêm vào giỏ bổ sung] | Chỉ hiện ở dòng Thiếu/Sắp thiếu **và** vật tư thuộc HĐNT còn hiệu lực (BR-P4) | SL điền sẵn = max − tồn, làm tròn lên theo bội số; gộp các dòng chọn → chuyển sang F-04 với giỏ đã điền |
| [📨 Nhờ Miyano tìm nguồn] [MỚI — QT11] | Hiện ở dòng Thiếu/Sắp thiếu của vật tư **ngoài HĐNT** (kể cả vật tư riêng đang mua NCC khác) | Mở F-22 điền sẵn: tên/quy cách/ĐVT từ `Customer Warehouse Item`, SL dự kiến = max − tồn, kèm chú thích ADU; gửi xong dòng gắn nhãn "Đã gửi yêu cầu YCH-xxx" (NL-11.1 chống trùng) |

---

## 3b. Nhóm mua lẻ, yêu cầu hàng hoá **[MỚI — v2.1]**

### F-21 Danh mục mua lẻ — `/portal/catalog` (chế độ Mua lẻ) — UC-15 **[MỚI]**

Cùng khung với F-03; bảng dưới chỉ nêu **khác biệt**:

| Hạng mục | Khác với F-03 |
|---|---|
| Điều kiện hiển thị | Chỉ khi `Customer.custom_cho_phep_mua_le = 1`; server kiểm lại mọi API (NL-10.1) |
| Banner đầu trang | Nền vàng nhạt: "Giá bán lẻ ngoài HĐNT — đơn cần Miyano xác nhận trước khi giao" |
| Nguồn mặt hàng | Item có `custom_ban_le_portal = 1` (BR-R6), qua `portal_catalog_ban_le` |
| Cột giá | "Giá bán lẻ (chưa VAT)" từ Price List bán lẻ — chỉ đọc (BR-R3) |
| Cột hạn mức | **Bỏ** — thay bằng cột "Tình trạng hàng" (Còn hàng / Liên hệ) |
| Mặt hàng đã thuộc HĐNT còn hiệu lực | Dòng disable + nhãn "Có trong HĐNT — đặt ở chế độ Theo HĐNT" (BR-R7, NL-10.7), bấm nhãn → chuyển chế độ kèm filter sẵn |
| Mặt hàng thiếu giá lẻ | Thay ô SL + nút [+ Giỏ] bằng nút **[Yêu cầu báo giá]** → F-22 điền sẵn loại "Báo giá mua lẻ" + tên hàng (NL-10.2) |
| Thêm giỏ | Vào **ngăn Mua lẻ** của giỏ (F-04) |

### F-22 Yêu cầu hàng hoá — tạo mới & danh sách — `/portal/yeu-cau` — UC-16/17 **[MỚI]**

**Form tạo yêu cầu** (modal desktop / trang mobile; mở từ 3 đường vào QT11 — trường điền sẵn theo ngữ cảnh):

| Trường | Điều khiển | Nguồn / mặc định | BB | Ràng buộc & validate | Hành vi, thao tác, lỗi |
|---|---|---|---|---|---|
| Loại yêu cầu | Select: Bổ sung HĐNT / Báo giá mua lẻ / Tìm nguồn hàng mới | Theo đường vào | ✔ | — | Đổi loại không xoá dữ liệu đã nhập |
| Tên hàng hoá | Input | Prefill từ ô tìm kiếm / vật tư kho / dòng mua lẻ | ✔ | ≤ 200 ký tự | Gõ xong so gần đúng với yêu cầu đang mở → cảnh báo "đã có yêu cầu {mã} đang xử lý", vẫn gửi được (NL-11.1) |
| Quy cách đóng gói | Input | Prefill nếu có | — | ≤ 100 | VD "Hộp 4 lọ × 100ml" |
| ĐVT | Input gợi ý | Prefill | ✔ | — | — |
| Số lượng dự kiến | Input số | Prefill = max − tồn (từ F-20) | ✔ | > 0 | — |
| Tần suất | Select: Một lần / Định kỳ | Một lần | ✔ | — | "Định kỳ" → hiện thêm ô "Chu kỳ (tháng)" ≥ 1 — nhóm này vào đề xuất HĐNT (NL-11.7) |
| Ngày cần hàng | Date | +7 ngày | — | ≥ hôm nay | — |
| Hãng / xuất xứ mong muốn | Input | — | — | ≤ 200 | — |
| Ghi chú | Textarea | — | — | ≤ 1000, đếm ký tự | — |
| Đính kèm | Upload nhiều file | — | — | ≤ 5 file; ≤ 10MB/file; pdf/jpg/png/xlsx (NL-11.6) | Ảnh nhãn hàng, tài liệu kỹ thuật; private file (BR-Y5) |
| [Gửi yêu cầu] | Nút chính | — | — | — | Khoá khi đang gửi; thành công → toast + email cho sales/purchasing; về danh sách |

**Danh sách yêu cầu:** cột Mã (YCH-xxx) · Ngày gửi · Tên hàng · Loại · SL · **Trạng thái** (badge:
Mới xám · Đang tìm nguồn xanh dương · Cần thêm thông tin vàng · Đã báo giá cam · Đã có hàng xanh lá
· Đã chuyển thành đơn xanh lá đậm · Không đáp ứng đỏ · Khách huỷ/Hết hạn xám) · Hạn phản hồi (SLA
còn lại, đỏ khi quá hạn). Lọc theo trạng thái/loại/kỳ; bấm dòng → F-23.

### F-23 Chi tiết yêu cầu hàng hoá — `/portal/yeu-cau/:name` — UC-17 **[MỚI]**

| Khối | Hiển thị | Thao tác |
|---|---|---|
| Đầu trang | Mã + badge trạng thái + loại; SLA phản hồi còn lại | [← Quay lại] |
| Timeline trạng thái | Mới → Đang tìm nguồn → (Cần thêm thông tin) → Đã báo giá / Đã có hàng → kết thúc; mỗi mốc có timestamp | Chỉ đọc |
| Nội dung yêu cầu | Toàn bộ trường đã gửi + đính kèm (xem/tải) | Sửa được **chỉ khi** trạng thái Mới (chưa ai nhận xử lý) |
| Phản hồi Miyano | Giá báo · lead time · item liên kết (nếu đã tạo) · ghi chú của người xử lý | Chỉ đọc |
| Trao đổi bổ sung | Chuỗi comment 2 chiều (khách ⇄ Miyano), đính kèm được; trạng thái "Cần thêm thông tin" → ô nhập được highlight + banner nêu câu hỏi của Miyano (NL-11.3) | Gửi trả lời → trạng thái tự về "Đang tìm nguồn" |
| Khi "Đã báo giá" | Thẻ nổi bật: link đơn `SAL-ORD-…` + giá trị + hạn hiệu lực | [Xem & đồng ý đơn] → F-07 (khối "Chờ bạn đồng ý") |
| Khi "Đã có hàng" | Thẻ: item đã mở bán (tên + giá) | [Đặt ngay] → F-03/F-21 với filter mặt hàng |
| Khi "Không đáp ứng được" | Lý do từ Miyano (BR-Y2) | [Gửi yêu cầu khác] |
| [Huỷ yêu cầu] | Hiện khi chưa ở trạng thái kết thúc | Modal + lý do; đóng "Khách huỷ", giữ lịch sử (NL-11.5) |

### F-24 Kho — Danh mục khoa phòng — `/portal/kho/khoa-phong` — UC-54 **[MỚI — QĐ-9]**

Danh sách: bảng (Tên khoa phòng · Mã khoa · Số phiếu cấp phát 90 ngày · Giá trị 90 ngày · Trạng thái),
nút [+ Thêm khoa phòng]. Cài đặt kho hiển thị công tắc **"Bắt buộc chọn khoa phòng khi xuất sử dụng"**
(BR-CP2 — chỉ quản trị kho bật).

| Trường (form) | Điều khiển | BB | Ràng buộc & validate | Hành vi, lỗi |
|---|---|---|---|---|
| Tên khoa phòng | Input | ✔ | ≤ 140 ký tự; unique trong kho (BR-CP1) | Gần giống khoa có sẵn → gợi ý chọn thay vì tạo (NL-4.13); trùng tuyệt đối → chặn |
| Mã khoa | Input | — | ≤ 20 ký tự | Tuỳ chọn — khớp mã nội bộ bệnh viện |
| Ghi chú | Input | — | — | — |
| Trạng thái | Toggle Hoạt động | — | — | Khoa đã dùng trên phiếu: không xoá, chỉ tắt; tắt → không chọn được trên phiếu mới (NL-4.12) |

---

## 4. Thành phần dùng chung

| Thành phần | Đặc tả |
|---|---|
| Modal xác nhận | 3 mức: thường (xanh — xác nhận đặt hàng, ghi sổ), cảnh báo (cam — có chênh lệch, bỏ dòng lỗi), nguy hiểm (đỏ — huỷ phiếu, kèm ô lý do). Luôn 2 nút [Quay lại] [Hành động]; nút hành động khoá khi đang gửi; Esc = quay lại |
| Toast | Xanh thành công / đỏ lỗi hệ thống; 4s; tối đa 1 toast, cái mới thay cái cũ; kèm link đối tượng khi phù hợp; hành động phá huỷ có [Hoàn tác] 5s nếu khả thi (xoá dòng giỏ) |
| PDF | Mở tab mới qua endpoint whitelist (`portal_document_download`, `kho_phieu_pdf`) — **không** dùng `/printview` (mục 8 BA); lỗi quyền → trang "Không tìm thấy chứng từ" trung tính |
| Bảng dữ liệu | Sticky header; sort click tiêu đề (server-side với danh sách lớn); phân trang 20–50 dòng; trạng thái lọc giữ trong URL |
| Ô số | `inputmode="decimal"`; chặn ký tự chữ ngay khi gõ; paste số có dấu chấm ngăn cách được chuẩn hoá |
| Quyền theo ngữ cảnh | Nút không đủ điều kiện thì **ẩn** (không disable mù mờ), trừ khi việc "sắp làm được" cần thấy — khi đó disable + tooltip lý do (VD [Ghi sổ] khi phiếu chưa có dòng) |
| Phím | Enter gửi form một trường; Ctrl/Cmd+S = Lưu nháp trong form phiếu; Esc đóng modal |

## 5. Ma trận thông điệp lỗi chuẩn (trích các NL hay gặp)

| Mã | Tình huống | Thông điệp mẫu (hiển thị đúng nguyên văn) |
|---|---|---|
| NL-1.2 | Hết hạn mức | "**{mã} – {tên}** đã dùng hết hạn mức theo HĐNT. Liên hệ {sales} để bổ sung." |
| NL-1.3 | Vượt hạn mức | "Không đặt được: **{mã}** chỉ còn **{n} {đvt}** theo hạn mức HĐNT (đã đặt {đã}/{tổng})." — liệt kê đủ mọi mã sai trong một alert |
| NL-1.4 | Thiếu giá | "**{mã}** chưa có giá trong hợp đồng. Miyano đã nhận được thông báo để bổ sung." |
| NL-1.6 | Sai bội số | "Số lượng phải là bội số của **{bội số}**. Gần nhất: {gợi ý}." |
| NL-1.7 | Ngày giao sai | "Ngày giao sớm nhất là **{ngày}** (sau 2 ngày làm việc)." |
| NL-1.8 | Trùng yêu cầu | *(không hiện lỗi)* — chuyển thẳng tới đơn đã tạo kèm toast "Đơn **{mã}** đã được tạo trước đó." |
| NL-2.5 | Cần Manager duyệt | *(Desk)* "Đơn ≥ {ngưỡng} — cần Sales Manager xác nhận." |
| NL-3.3 | Chênh lệch nhận | "Dòng {vt}: thực nhận {a} / giao {b}. Nhập lý do chênh lệch để tiếp tục." |
| NL-4.1 | Xuất quá tồn | "Lô **{lô}** của **{vt}** chỉ còn **{tồn} {đvt}**, phiếu cần {cần}. Sửa số lượng hoặc chọn lô khác." |
| NL-4.4 | Tồn đầu lần 2 | "Kho đã nhập tồn đầu kỳ ngày {ngày}. Dùng phiếu **Điều chỉnh kiểm kê** cho chênh lệch." |
| NL-4.9 | Xuất lô hết hạn | "Lô **{lô}** đã hết hạn {ngày}. Xác nhận vẫn xuất sử dụng, hoặc chuyển loại *Xuất huỷ - hết hạn*." |
| NL-5.1 | Huỷ phiếu đảo | "Phiếu đảo không huỷ được — nó tồn tại để bù trừ phiếu {gốc}." |
| NL-5.2 | Đảo làm âm tồn | "Không huỷ được: lô **{lô}** đã xuất {x}, chỉ còn {tồn}. Huỷ phiếu xuất {phiếu} trước." |
| NL-7.1 | Thiếu NCC | "Chọn nhà cung cấp cho phiếu mua ngoài." |
| NL-7.3 | NCC trùng | "Kho đã có NCC tên tương tự: **{tên}**. Chọn NCC có sẵn hay vẫn tạo mới?" |
| NL-10.2 | Mua lẻ thiếu giá | "**{tên hàng}** chưa có giá bán lẻ. Gửi yêu cầu báo giá — Miyano phản hồi trong {SLA} giờ làm việc." |
| NL-10.5 | Báo giá hết hiệu lực | "Báo giá cho đơn **{mã}** đã hết hiệu lực ngày {ngày}. Gửi yêu cầu báo giá mới nếu vẫn cần hàng." |
| NL-10.7 | Né hạn mức | "**{tên hàng}** đang thuộc HĐNT {số HĐ} — vui lòng đặt ở chế độ *Theo HĐNT* để hưởng giá hợp đồng." |
| NL-11.1 | Yêu cầu trùng | "Bạn có yêu cầu **{mã}** cho hàng tương tự đang xử lý ({trạng thái}). Vẫn gửi yêu cầu mới?" |
| NL-11.6 | Đính kèm sai | "Tối đa 5 file, mỗi file ≤ 10MB, định dạng pdf/jpg/png/xlsx." |
| NL-12.1 | HĐĐT chưa phát hành | "Hoá đơn điện tử đang được phát hành — file tải sẽ xuất hiện tại đây khi hoàn tất." |
| NL-12.4 | File HĐĐT lỗi | "Chưa tải được file hoá đơn. Yêu cầu hỗ trợ đã đính kèm mã **{số HĐ}** — Miyano sẽ gửi lại sớm." |

## 6. Truy vết Form ↔ UC/QT

| Form | UC | QT liên quan |
|---|---|---|
| F-01…F-05 | UC-01…05, 14, 15 | QT1, QT10 |
| F-06, F-07 | UC-06…11, 17 | QT2, QT3, QT6, QT10 |
| F-08, F-09 | UC-09, 12, 18 | QT6, QT12 |
| F-10…F-14 | UC-20…28 | QT4 |
| F-15 | UC-29, 32…36, 47 | QT3, QT4, QT5, QT7 |
| F-16 | UC-30…33 | QT4, QT5 |
| F-17 | UC-42 | QT7 |
| F-18 | UC-43 | QT8 |
| F-19 | UC-37…40, 44 | QT4, QT8 |
| F-20 | UC-45, 46 | QT9, QT11 |
| F-21 | UC-15 | QT10 |
| F-22, F-23 | UC-16, 17 | QT10, QT11 |
| F-24 | UC-54 | QT4 (cấp phát — QĐ-9) |

