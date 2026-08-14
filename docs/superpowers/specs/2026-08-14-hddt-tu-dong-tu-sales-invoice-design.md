# Tự động lập HĐĐT khi submit Sales Invoice, và cho khách xem hoá đơn Fast trên cổng

Ngày: 2026-08-14 · Epic: E7b · Trạng thái: chờ duyệt spec

## 1. Mục tiêu

Kế toán submit một `Sales Invoice` → hệ thống tự lập chứng từ HĐĐT từ (các) phiếu
giao của hoá đơn đó và tự lấy về **bản in thử PDF do Fast dựng**. Khách hàng mở
cổng là **nhìn thấy chính file PDF của Fast** — ở cả trang *Hoá đơn & công nợ*
lẫn *chi tiết đơn hàng*.

**Ưu tiên số một, chi phối mọi lựa chọn giao diện bên dưới: thứ khách phải thấy
là FILE PDF CỦA FAST**, không phải bảng số liệu do cổng tự dựng lại từ
`Fast EInvoice Line`. Bảng số liệu chỉ là phương án dự phòng cho lúc chưa có
file (xem §5).

Không thuộc phạm vi lần này: cổng tự gửi email; nút Duyệt / Yêu cầu sửa trên
cổng; lấy XML gốc (module không lưu XML — `docs/HDDT-ban-giao-team-module.md` §1).

## 2. Quyết định đã chốt với chủ dự án

| # | Quyết định | Lý do |
|---|---|---|
| Q1 | Tự động **dừng ở `02 - Đã xem nháp`**. KHÔNG tự gửi email cho khách. | Kế toán vẫn phải liếc bản nháp trước khi nó vào hộp thư khách. Khách vẫn xem được ngay trên cổng nên không ai phải chờ email. |
| Q2 | **Mỗi phiếu giao một chứng từ HĐĐT.** SI gộp 3 đợt giao → 3 HĐĐT. SI không tham chiếu phiếu giao nào → không tạo gì. | Đúng cơ chế sẵn có `builder.create_from_delivery_note` (nhận đúng MỘT phiếu giao). Không phải viết đường tạo thứ hai chạm vào module của team khác. |
| Q3 | Kích hoạt bằng **hook + job nền**, không phải job quét định kỳ. | Kế toán submit xong là xong, không chờ Fast. Job idempotent sẵn nhờ `_assert_no_live_invoice` nên có thể bổ sung bản quét bù sau nếu thấy job hay rơi. |

## 3. Ràng buộc từ module HĐĐT (đã đọc mã, không suy đoán)

- **Quy trình gốc là 3 nút thủ công:** `builder.create_from_delivery_note` (bản
  ghi `01 - Nháp`, **không kèm file nào**) → `actions.preview_draft` (gọi Fast
  `action=600`, sinh `draft_pdf`, sang `02`) → `actions.send_draft_to_customer`
  (email, sang `03`). Tự động hoá lần này chạy hai bước đầu.
- **Gọi Fast là HTTP đồng bộ, timeout 120 giây** (`fast_client.py:50`
  `REQUEST_TIMEOUT_SECONDS`). Không được đặt trong `on_submit`.
- **`preview_draft` chạy 16 luật kiểm** (`validation.py::validate_before_send`)
  và ném lỗi nếu vướng — thiếu MST, quá 300 dòng, tổng tiền lệch, ký tự lạ…
- **`check_enabled()` ném lỗi khi `Fast EInvoice Settings.enabled = 0`**, và
  settings không bật được nếu chưa có credential Fast thật.
- **`_assert_no_live_invoice`** đã chặn lập chứng từ thứ hai cho cùng phiếu giao
  khi bản cũ còn ở trạng thái 01–08/98.
- **Không có sự kiện nào hook được khi HĐĐT phát hành xong** (mục 3 tài liệu bàn
  giao) — nên không dựa vào đó cho bất cứ bước nào.

## 4. Kích hoạt và job nền

```
Sales Invoice.on_submit                     (hooks.py, doc_events)
  └─ miyano_portal.hddt_tu_dong.tu_sales_invoice(doc)
       └─ frappe.enqueue(lap_hddt_cho_hoa_don, sales_invoice=doc.name)
```

**Hook không bao giờ ném lỗi ra ngoài** — cùng nguyên tắc
`kho/delivery_hook._chay_an_toan` (quyết định nền tảng #4): lập HĐĐT là hiệu ứng
phụ, không có quyền chặn việc xuất hoá đơn bán hàng. Hook chỉ đẩy hàng đợi.

Hook **bỏ qua ngay** khi `si.is_return = 1`: hoá đơn trả hàng tham chiếu phiếu
trả hàng, mà `builder._load_delivery_note` từ chối thẳng phiếu trả hàng (*"phiếu
trả hàng không lập hóa đơn trực tiếp — dùng hóa đơn điều chỉnh giảm từ hóa đơn
gốc"*). Không lọc thì mỗi lần lập giấy báo có là một Comment lỗi vô nghĩa.

Tham số hàng đợi: `queue="long"`, `timeout=600`. Một lời gọi Fast có thể mất tới
120 giây (`REQUEST_TIMEOUT_SECONDS`) và một SI có thể gộp nhiều phiếu giao, nên
hàng đợi mặc định (`short`, 300 giây) không đủ chỗ cho trường hợp xấu.

**Job `lap_hddt_cho_hoa_don(sales_invoice)`** — chạy trong ngữ cảnh nền, người
dùng là `Administrator`; mọi Comment sinh ra vì thế mang tên hệ thống chứ không
phải tên kế toán vừa submit:

1. Lấy `Sales Invoice Item.delivery_note` của hoá đơn, bỏ rỗng, dedupe, giữ thứ tự.
2. Danh sách rỗng → ghi Comment *"Hoá đơn không qua phiếu giao nào — không lập
   HĐĐT tự động"* rồi kết thúc.
3. Với **mỗi** phiếu giao, bọc lỗi RIÊNG từng phiếu (một phiếu hỏng không được
   kéo theo phiếu khác):
   - `create_from_delivery_note(dn)` → tên chứng từ HĐĐT
   - `preview_draft(fei)` → PDF nháp, sang `02`
4. Ghi **một** Comment tổng kết lên chính `Sales Invoice`: phiếu nào ra chứng từ
   nào, phiếu nào bỏ qua và vì sao.

**Ba nhánh hỏng, xử lý riêng:**

| Tình huống | Hành vi |
|---|---|
| Fast chưa bật (`check_enabled` ném) | Dừng êm cả job, Comment *"Chưa bật tích hợp HĐĐT Fast"*. Không log_error (đây là cấu hình, không phải sự cố). |
| Phiếu giao đã có HĐĐT sống | Bỏ qua phiếu đó, Comment nêu tên chứng từ đang có. Đúng ý — không lập trùng. |
| 16 luật kiểm chặn, hoặc Fast trả lỗi | Bản ghi **vẫn còn ở `01 - Nháp`** (đã tạo được), Comment nêu nguyên văn lý do + `frappe.log_error`. Kế toán sửa dữ liệu rồi bấm lại nút "Xem bản nháp" ở Desk. |

Job mất do worker restart: không tự phục hồi trong bản này. Bù bằng (a) Comment
trên SI cho biết đã chạy hay chưa, (b) hai nút thủ công ở Desk còn nguyên. Nếu
thực tế job hay rơi thì thêm một job quét bù — rẻ, vì mọi bước đã idempotent.

## 5. Hiển thị trên cổng

### 5.1 Nhóm trạng thái mới

`miyano_portal/einvoice.py` hiện gộp **01–05** thành một nhóm mờ
`dang_phat_hanh` / *"Đang phát hành HĐĐT"* / `tai_duoc = False`. Tách ra:

| Trạng thái | Nhóm | Nhãn | Tải được |
|---|---|---|---|
| 01 – 04 | `nhap` (MỚI) | **Hoá đơn nháp** | PDF nháp, khi `draft_pdf` có |
| 05 | `dang_phat_hanh` | Đang phát hành HĐĐT | không |
| chưa có chứng từ HĐĐT nào | `dang_phat_hanh` | Đang phát hành HĐĐT | không |
| 06 – 08 | `da_phat_hanh` | Đã phát hành | PDF chính thức (đã có) |

Nhóm "chưa có chứng từ nào" **giữ nguyên** nhãn cũ: NL-12.1 — danh sách hoá đơn
và công nợ không được phụ thuộc tình trạng HĐĐT.

`_UU_TIEN_CHINH` (chọn bản ghi "chính" khi một hoá đơn khớp nhiều chứng từ HĐĐT)
xếp `nhap` cùng hạng với `dang_phat_hanh`/`loi` — sau "còn hiệu lực", trước "đã
bị thay thế/huỷ". Không đổi thứ hạng của các nhóm cũ.

### 5.2 Khối hiển thị — PDF Fast là thứ chính

Cả hai màn hình dùng **cùng một component**, và thứ tự ưu tiên là:

1. **Có `draft_pdf`** → hiện **trình xem PDF nhúng ngay trong trang** (nạp file
   qua endpoint kiểm quyền, dựng blob URL, đặt vào `<iframe>`), kèm nút tải về.
   Đây là "hoá đơn của Fast" theo đúng nghĩa đen — bản in thử do Fast dựng.

   *Ca biên đã tính:* nhiều trình duyệt di động (Chrome/Safari trên Android/iOS)
   **không** render PDF trong `<iframe>` — khung sẽ trắng hoặc tự tải file. Cổng
   có sẵn `useIsMobile()`, nên trên màn hình hẹp bỏ hẳn khung nhúng và hiện nút
   **"Mở hoá đơn nháp"** (mở blob URL ở tab mới) + nút tải. Không để một khung
   trắng rồi tin là "đã hiện được".
2. **Chưa có `draft_pdf`** (trạng thái 01, hoặc Fast đang lỗi) → hiện bảng dòng
   hàng + thuế + tổng dựng từ `Fast EInvoice Line`, kèm câu *"bản in thử PDF
   đang được tạo"*. Đây là DỰ PHÒNG, không phải mặc định.

Mọi trường hợp đều kèm cảnh báo cố định **do server trả** (`einvoice.CANH_BAO_NHAP`),
không gõ lại ở frontend: *bản nháp — chưa có số hoá đơn, chưa ký số, chưa gửi Cơ
quan Thuế, KHÔNG có giá trị pháp lý; số liệu có thể thay đổi trước khi phát hành.*
Lý do: `resync_from_delivery_note` ghi đè dòng hàng bất cứ lúc nào bản ghi còn ở
01–04, và chính docstring `send_draft_to_customer` của module chốt rằng gửi bản
nháp mà không nói rõ là để khách hiểu nhầm đã có hoá đơn.

### 5.3 Hai chỗ hiển thị

**Trang Hoá đơn & công nợ** (`Invoices.vue`) — khối HĐĐT sẵn có, neo theo
`Sales Invoice` qua `einvoice.block_for`. Bổ sung nhóm `nhap` + khối xem PDF.

**Chi tiết đơn hàng** (`OrderDetail.vue`, khối từng đợt giao) — neo theo
`Delivery Note`. Cần đường đọc riêng vì `create_from_delivery_note` **chỉ** gán
`fei.delivery_note`, không gán `fei.sales_invoice`: phiếu giao có thể chưa được
lập Sales Invoice nào tại thời điểm khách nhìn. Khôi phục khối E7b đã dựng ở
commit `7d84b11` (đang nằm nhánh riêng, **chưa review** — coi như code mới, review
lại từ đầu), sửa để dùng chung component ở §5.2.

### 5.4 Đường phục vụ file

Hai endpoint tải, **một** helper phục vụ file dùng chung:

```
portal_einvoice_download(invoice, loai, fei=None)   ← neo Sales Invoice (đã có)
portal_einvoice_nhap_pdf(delivery_note)             ← neo Delivery Note (mới)
        │
        └─ _phuc_vu_file(fei_row, field, ten_file)  ← dùng chung
```

`loai="nhap"` là nhánh MỚI của endpoint cũ (phục vụ `draft_pdf`, chốt trạng thái
01–04); `loai="pdf"` giữ nguyên (phục vụ `official_pdf`, chốt 06+). Hai chốt
trạng thái **ngược nhau** nên phải tách nhánh rõ ràng trong hàm, không gộp điều
kiện.

Ràng buộc giữ nguyên từ E7 (quyết định nền tảng #7/#8):

- Không endpoint nào nhận `customer`/`kho` từ client; khách suy từ phiên.
- Tham số `fei`/`delivery_note` chỉ dùng để **lọc trong tập đã tự suy ra và đã
  đối chiếu `customer`** — không bao giờ `frappe.get_doc` thẳng tên client gửi.
- Không có URL file công khai: khối JSON chỉ mang cờ boolean, không mang đường
  dẫn file. Kiểm quyền + kiểm `File` thật sự đính đúng chứng từ ở **từng lần** tải.
- Ghi `Access Log` mỗi lần phục vụ file.

## 6. Kiểm thử

**Job tự động** (mock Fast — `test_fixtures` của module HĐĐT, không gọi mạng):

- SI một phiếu giao → đúng 1 chứng từ HĐĐT, trạng thái `02`, có `draft_pdf`
- SI gộp 3 phiếu giao → 3 chứng từ, mỗi phiếu một cái
- SI không tham chiếu phiếu giao → không tạo gì, có Comment
- SI trả hàng (`is_return = 1`) → hook bỏ qua, **không** đẩy job, không Comment lỗi
- Trên màn hình hẹp: khối hiện nút "Mở hoá đơn nháp", không dựng `<iframe>`
- Fast tắt → **submit SI vẫn thành công**, không tạo gì, có Comment
- Luật kiểm chặn → bản ghi còn ở `01`, Comment nêu lý do, các phiếu khác của
  cùng SI **vẫn chạy bình thường**
- Chạy lại job cho cùng SI → không lập chứng từ thứ hai
- **Khẳng định KHÔNG tự gửi email**: trạng thái dừng ở `02`, `draft_sent_time`
  rỗng, không có Email Queue phát sinh
- Hook ném lỗi giả lập → `Sales Invoice.submit()` vẫn thành công

**Hiển thị & tải:**

- 01–04 có `draft_pdf` → nhóm `nhap`, tải được PDF nháp, ở **cả hai** màn hình
- 01 chưa có file → nhóm `nhap`, không tải được, có bảng dòng hàng dự phòng
- 05 và "chưa có chứng từ" → vẫn *Đang phát hành HĐĐT*, không tải được
- 06+ → không đổi hành vi cũ (PDF chính thức)
- Khách khác bị chặn ở cả hai endpoint; chưa đăng nhập bị chặn
- Bản ghi HĐĐT bị gán nhầm `customer` → không lộ, dù SI/DN đọc được là đúng chủ
- Khối JSON không chứa `draft_pdf`/`official_pdf` (quét toàn bộ giá trị)
- Ghi `Access Log` khi tải bản nháp

**Test cũ sẽ phải sửa (~7 ca trong `test_e7_hddt.py`)** — những ca khoá "01–05
đều là *Đang phát hành HĐĐT*" và "trạng thái chưa phát hành thì không tải được":
`test_chua_ghi_so_hddt_khong_nut_tai_cong_no_van_hien` (TC-E7-01),
`test_khong_co_fei_cung_la_dang_phat_hanh`, `test_status_meta_khop_dung_14_ma_that`,
`test_a_dieu_chinh_dang_soan_khong_che_ban_goc`,
`test_trang_thai_chua_phat_hanh_khong_tai_duoc`,
`test_trang_thai_chua_phat_hanh_chan_du_co_file_that`,
`test_bao_loi_khong_lam_mat_ca_danh_sach_hoa_don`.
Đây là đổi hành vi **có chủ ý** theo yêu cầu — sửa từng ca kèm ghi chú vì sao,
không sửa cho xanh.

## 7. Việc cần báo team module HĐĐT

Bổ sung vào `docs/HDDT-ban-giao-team-module.md` (mục 12 đã mở sẵn ở lần trước):
cổng nay phụ thuộc thêm **`draft_pdf`** và **vùng trạng thái 01–04** ở đường tự
động này, ngoài các phụ thuộc đã liệt kê. Và ghi rõ: `Sales Invoice.on_submit`
của app cổng nay gọi `builder.create_from_delivery_note` + `actions.preview_draft`
— hai hàm whitelist của module HĐĐT — nên đổi chữ ký hai hàm đó là vỡ luồng này.
