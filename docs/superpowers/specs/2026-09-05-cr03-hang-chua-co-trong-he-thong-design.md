# CR-03 — Khai chi tiết hàng chưa có trong hệ thống

**Ngày:** 05/09/2026 · **Chủ đầu tư chốt trong phiên**

## 1. Vấn đề

Khách gõ tay một mặt hàng không có trong danh mục, hôm nay khai được đúng
**bốn** thứ: `ten_hang`, `dvt`, `so_luong`, `ghi_chu`. Purchasing của Miyano
nhận về một dòng chữ như *"Găng tay nitrile không bột size M"* rồi phải tự đi
hỏi lại khách: hãng nào, hộp bao nhiêu chiếc, có mã trên hộp không.

Mỗi vòng hỏi lại là một ngày trôi qua trên một đơn hàng bệnh viện đang cần.

## 2. Bốn dữ kiện đã ĐO, không phải giả định

Bốn điều dưới đây được kiểm bằng cách đọc thẳng mã nguồn trước khi viết đặc
tả này — chúng quyết định gần như toàn bộ thiết kế:

**(a) Một bảng con phục vụ CẢ HAI chặng.** `Sales Order Dat Ngoai Item` là
`options` của `Portal De Xuat Mua.dat_ngoai` (nơi khách gõ) LẪN
`Sales Order.custom_dat_ngoai` (sau khi duyệt). Thêm trường một chỗ là phủ cả
hai đường — không phải đồng bộ hai bảng.

**(b) Khách gõ vào PHIẾU ĐỀ XUẤT, không phải vào đơn hàng.** `de_xuat_tao_nhap`
tạo phiếu Nháp **trước**, nên lúc khách đang gõ, đã có một bản ghi mang tên để
đính tệp vào. Đây là điều làm cho việc tải ảnh khả thi mà không phải dựng một
kho tệp tạm.

**(c) Cổng CHƯA có chỗ nào tải tệp lên.** Không màn nào — kể cả kiểm hàng.
Nên "bắt buộc ít nhất một ảnh" không phải thêm một trường, mà là thêm một
**năng lực mới** cho cổng.

**(d) Đường tệp riêng tư mặc định của Frappe KHÔNG dùng được ở đây.** Role
`Customer` có ZERO DocPerm trên `Portal De Xuat Mua`, nên `/private/files/…`
sẽ 403 cho chính người vừa tải ảnh lên. Phải có endpoint phục vụ riêng, đúng
khuôn `portal_einvoice_download`/`_phuc_vu_file` đã có.

## 3. Chín trường mới

Đặt trên `Sales Order Dat Ngoai Item`, ngay sau `ghi_chu`.

| Trường | Kiểu | Bắt buộc | Nghĩa |
|---|---|---|---|
| `model_ma` | Data | không | Model hoặc mã catalogue in trên hộp |
| `hang_san_xuat` | Data | không | Hãng sản xuất |
| `nuoc_san_xuat` | Data | không | Nước sản xuất |
| `quy_cach` | Data | không | VD "hộp 100 test", "chai 500ml" |
| `ncc_hien_tai` | Data | không | Nhà cung cấp khách đang mua |
| `gia_hien_tai` | Currency | không | Giá khách đang mua |
| `anh` | Small Text | **có điều kiện** | Danh sách `file_url`, JSON |
| `khong_co_anh` | Check | không | Lối thoát khi không chụp được |
| `mo_ta_nhan_dang` | Small Text | **có điều kiện** | Mô tả bằng lời, ≥ 50 ký tự |

`quy_cach` dùng ĐÚNG tên trường của `Portal Item Request` — hai chỗ mô tả
cùng một thứ thì phải cùng một tên, nếu không báo cáo gộp sau này phải viết
một bảng ánh xạ.

`dvt` GIỮ NGUYÊN tên đã có — trùng với `Portal De Xuat Mua Item` và
`Portal Item Request`, nhất quán toàn hệ thống như chủ đầu tư yêu cầu.

**Tám trong chín trường là TUỲ CHỌN** (chủ đầu tư chốt). Lý do ghi lại để
người sau không "siết cho chặt": đây là ô gõ giữa lúc khách đang đặt hàng
gấp. Bắt buộc một ô khách không biết câu trả lời thì họ gõ *"không rõ"* cho
qua — dữ liệu thành rác mà bảng vẫn trông đầy đủ, tức mất luôn khả năng phân
biệt "khách không biết" với "khách chưa điền".

## 4. Ràng buộc ảnh — ràng buộc quan trọng nhất của CR này

**BR-Y5 (bắt buộc ít nhất một ảnh).** Ảnh là dữ kiện tìm nguồn giá trị nhất;
một tấm ảnh nhãn hộp thay được cả bốn trường mô tả phía trên.

**Lối thoát `khong_co_anh`.** Nhãn mờ, hộp đã bỏ, hàng chưa từng mua — có
thật. Bật cờ này thì `mo_ta_nhan_dang` trở thành **bắt buộc, tối thiểu 50 ký
tự**.

Ngưỡng 50 ký tự là một phép đo thô nhưng cố ý: nó chặn được *"không có ảnh"*,
*"như cũ"*, *"gọi cho tôi"* — những câu không cho purchasing manh mối nào.
Nó **không** chặn được một chuỗi 50 ký tự vô nghĩa, và đặc tả này không giả
vờ là có: chốt máy làm được đến đó, phần còn lại là việc của người đọc.

**Giới hạn tệp — dùng lại nguyên văn BR-Y5 đã có trong tài liệu BA:** tệp
riêng tư, **≤ 5 tệp mỗi dòng**, **≤ 10MB mỗi tệp**. Chỉ nhận ảnh
(`image/jpeg`, `image/png`, `image/webp`, `image/heic`).

**Chốt chạy lúc GỬI DUYỆT, không phải lúc lưu nháp.** Khách gõ nửa chừng rồi
lưu lại làm tiếp buổi chiều là việc bình thường; bắt đủ ảnh mới cho lưu là
biến nút Lưu thành một cái bẫy. Chốt đặt ở đường `gửi duyệt`, cùng chỗ mọi
chốt "phiếu đã đủ điều kiện đi tiếp" khác đang đứng.

## 5. Ảnh sống ở đâu

Tệp đính vào **`Portal De Xuat Mua`** (bản ghi đã có tên từ lúc tạo nháp),
`is_private = 1`. Dòng con giữ danh sách `file_url` trong `anh`.

**Không đính vào dòng con.** Dòng con bị xoá và dựng lại mỗi lần khách sửa
giỏ (`doc.set("dat_ngoai", …)` trong `de_xuat_luu_nhap` thay TOÀN BỘ bảng),
nên một tệp đính theo tên dòng con sẽ thành mồ côi ngay lần lưu kế tiếp.

**Không chép tệp sang Sales Order.** Đơn hàng đã mang `custom_de_xuat` trỏ về
phiếu; chép tệp là dựng bản thứ hai của cùng một thứ, rồi hai bản trôi lệch.

## 6. Hai endpoint mới

`portal_dat_ngoai_tai_anh(de_xuat)` — nhận một tệp, kiểm: phiếu thuộc người
gọi và đang Nháp, đúng loại ảnh, ≤10MB, chưa quá 5 tệp. Trả `file_url`.

`portal_dat_ngoai_xem_anh(de_xuat, file_url)` — phục vụ tệp, kiểm sở hữu
**từng lần tải** (không tin cờ đã tính lúc liệt kê), đúng khuôn
`_phuc_vu_file` của HĐĐT. Cả hai vào `DA_AP_PHAM_VI`.

## 7. Giao diện

Khối *"Hàng chưa có trong hệ thống"* trên màn Đặt hàng (`LapPhieu.vue`) giữ
nguyên vị trí và cách xổ. Mỗi dòng thêm:

- Một khối **Ảnh** đặt NGAY DƯỚI tên hàng — trên cả các ô mô tả, vì nó là
  thứ giá trị nhất và là thứ bắt buộc. Hiện ảnh thu nhỏ đã tải, cho xoá.
- Bốn ô mô tả (model, hãng, nước, quy cách) trong một khối `<details>` gọn,
  nhãn *"Thông tin trên hộp (giúp Miyano tìm đúng hàng)"* — mở sẵn khi chưa
  có ảnh nào, thu lại khi đã có ảnh.
- Hai ô nhạy cảm (NCC, giá đang mua) trong một `<details>` RIÊNG, nhãn nói
  thẳng *"Tuỳ chọn — giúp Miyano báo giá cạnh tranh hơn"*. Tách riêng vì đây
  là thông tin thương mại của bệnh viện; gộp chung với mô tả kỹ thuật là làm
  người ta khai mà không nhận ra mình vừa khai gì.
- Ô *"Tôi không chụp được ảnh"* + ô mô tả nhận dạng hiện ra khi tick, kèm
  đếm ký tự còn thiếu.

`ChiTietYeuCau.vue` (sửa và gửi lại sau khi bị từ chối) mang theo đủ chín
trường — quên một trường ở đường này là dữ liệu khách đã khai bị xoá lặng lẽ
khi họ sửa phiếu.

## 8. Phía Miyano

Chín trường hiện trên lưới bảng con ở Desk. Mẫu in đơn hàng
(`install_print_formats.py`) đã in khối "chờ nguồn" — bổ sung model/hãng/quy
cách vào đó, vì tờ giấy đó chính là thứ purchasing cầm đi hỏi nhà cung cấp.

## 9. Ngoài phạm vi

`Portal Item Request` (luồng Desk-only) KHÔNG đụng tới. Báo cáo
`demand_pipeline` không đổi. Không làm OCR ảnh, không tự suy model từ ảnh.
