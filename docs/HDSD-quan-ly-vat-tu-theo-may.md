# Hướng dẫn thao tác — Quản lý vật tư theo máy trên cổng khách hàng

App `miyano_portal` · Cập nhật **28/08/2026**

**Tài liệu này dành cho nhân viên bệnh viện** thao tác trên cổng khách
(`/portal`). Nó trả lời năm câu hỏi thật đã gặp: khai máy ở đâu, gắn máy vào
vật tư để làm gì, xuất kho chọn máy thế nào, vì sao phiếu **nhập** lại không
có ô chọn máy, và đọc báo cáo theo máy ra sao.

---

## 0. "Máy" là gì trên cổng

**Máy** (tên kỹ thuật: Thiết bị) là máy móc dùng vật tư của bệnh viện — máy
xét nghiệm sinh hoá, máy huyết học, máy thở… Mỗi máy khai **một lần**, đặt ở
**một khoa phòng** (hoặc để trống nếu là **máy dùng chung** nhiều khoa), rồi
dùng lại nhiều lần mỗi khi lập phiếu xuất.

Máy **không gắn với kho** — nó gắn với **bệnh viện**. Vì vậy bệnh viện chưa mở
kho vật tư trên cổng vẫn khai được máy trước; và một bệnh viện chỉ có một kho
nên việc này không đổi gì trong cách dùng hằng ngày.

---

## 1. Khai máy ở đâu, ai khai được

**Kho của tôi › Thiết bị** (nút trên đầu màn Kho của tôi, cạnh nút *Khoa
phòng*) → **+ Thêm thiết bị**:

| Ô | Điền gì |
|---|---|
| **Mã máy** \* | Mã nội bộ của bệnh viện, ví dụ `MAY-SH-01`. Không trùng trong cùng bệnh viện — hệ thống tự viết hoa, bỏ khoảng trắng thừa |
| **Tên máy** \* | Ví dụ `Máy sinh hoá tự động XN-550`. Không trùng trong cùng bệnh viện (so không dấu, không phân biệt hoa thường) |
| **Khoa phòng** | Khoa đặt máy. **Để trống = máy dùng chung**, mọi khoa đều thấy và chọn được khi xuất |
| Hãng sản xuất · Xuất xứ · Model · Số serial · Năm sản xuất · Ngày lắp đặt · Ghi chú | Thông tin mô tả, không bắt buộc |
| **Đang hoạt động** | Máy thanh lý thì **bỏ tích, đừng xoá** — xem mục 7 |

### Ai khai được máy nào

| Vai trò | Thấy máy nào | Thêm/sửa máy nào |
|---|---|---|
| **Quản lý** | Mọi máy của bệnh viện | Mọi máy, kể cả **đổi khoa của một máy đã có** (điều chuyển máy) |
| **Nhân viên khoa** | Máy khoa mình **+ máy dùng chung** | Chỉ máy **khoa mình**. Ô Khoa phòng luôn **khoá cứng** ở khoa của họ — kể cả lúc tạo mới lẫn lúc sửa, không tự đổi khoa cho máy được |

**Nhân viên khoa không sửa được máy dùng chung** — dù họ nhìn thấy và chọn
được nó khi xuất. Máy dùng chung không thuộc khoa nào nên không có khoa nào
đủ thẩm quyền đổi nó; mở một máy dùng chung ra sửa, màn hình khoá toàn bộ ô và
chỉ còn nút *Đóng*, kèm dòng nhắc *"Máy dùng chung — liên hệ quản lý đơn vị để
sửa"*. Muốn sửa thì nhờ **Quản lý đơn vị**.

---

## 2. Gắn máy vào vật tư — để làm gì

Mở **Kho của tôi › Danh mục vật tư › Sửa** một vật tư → mục **"Máy sử dụng"**:
chọn một hoặc nhiều máy mà vật tư này thường dùng cho (ví dụ hộp hoá chất ALT
dùng được cho cả hai máy sinh hoá). Ô này **không bắt buộc** — để trống nếu
vật tư dùng chung, không thuộc máy nào (găng tay, bông, cồn…).

Bảng này phục vụ đúng **hai việc**, không hơn:

1. **Lọc sẵn ô chọn máy lúc lập phiếu xuất** — chọn vật tư xong, dropdown máy
   chỉ còn hiện những máy đã khai ở đây (mục 3 nói rõ cách lọc).
2. **Tra ngược "máy này đang dùng những vật tư gì"** — cột **Máy sử dụng**
   trên báo cáo (mục 6) đọc lại đúng bảng này.

**Đây là danh mục tương thích, không phải số liệu.** Không báo cáo nào cộng
số lượng qua bảng này — số lượng thật theo máy chỉ lấy từ phiếu xuất (mục 4).
Một vật tư gắn cả hai máy không có nghĩa là "chia đôi" cho mỗi máy; nó chỉ có
nghĩa "cả hai máy đều dùng được vật tư này".

---

## 3. Xuất kho có chọn máy

**Kho của tôi › Phiếu xuất › + Tạo phiếu xuất**:

- Đầu phiếu có thêm ô **Máy mặc định**, đặt cạnh ô Khoa phòng nhận — điền một
  lần rồi hệ thống tự chép xuống **các dòng còn trống**, không ghi đè dòng bạn
  đã tự chọn máy khác.
- Mỗi dòng vật tư có thêm cột **Máy**, chọn theo vật tư của chính dòng đó.

Ô chọn máy là **dropdown lọc sẵn**, không phải danh sách toàn bộ máy bệnh
viện:

- **Tầng tài khoản**: Nhân viên khoa chỉ thấy máy khoa mình + máy dùng chung;
  Quản lý thấy toàn bộ máy bệnh viện.
- **Tầng vật tư**: nếu vật tư đã khai "Máy sử dụng" (mục 2) thì dropdown chỉ
  còn đúng những máy trong danh mục đó; vật tư chưa khai máy nào thì bỏ qua
  tầng này, hiện mọi máy hợp lệ ở tầng tài khoản.
- Sau khi lọc mà **chỉ còn đúng một máy hợp lệ**, hệ thống **tự điền luôn**,
  không bắt bấm chọn.

### Gặp máy chưa khai — tạo nhanh ngay trong phiếu

Gõ tên máy vào ô chọn mà không thấy trong danh sách → dòng đầu tiên của
dropdown luôn có nút **"+ Tạo nhanh máy «chữ vừa gõ»"** (hiện cả khi đang gõ
lẫn khi đã có vài kết quả gần đúng). Bấm vào mở một form rút gọn **5 ô**: Tên
máy · Mã máy · Hãng sản xuất · Xuất xứ · Số serial — model, năm sản xuất,
ngày lắp đặt bổ sung sau ở màn **Thiết bị** (mục 1). "Nhanh" chỉ nói về **số
ô phải điền**, không nói về độ chặt: máy tạo theo lối này vẫn qua đúng những
kiểm tra như form đầy đủ (mã/tên trùng vẫn bị chặn). Tạo xong, máy mới được
điền thẳng vào đúng ô đang chọn dở, không phải tìm lại.

> **Lưu ý cho Quản lý:** form tạo nhanh **không có ô Khoa phòng** — máy tạo
> theo lối này luôn ra **máy dùng chung**, dù đang lập phiếu cho khoa nào.
> Nhân viên khoa tạo nhanh thì máy tự vào đúng khoa của họ (hệ thống ép sẵn,
> không cần chọn); Quản lý muốn máy mới thuộc một khoa cụ thể thì tạo xong
> phải mở lại **Kho của tôi › Thiết bị › Sửa** rồi gán khoa (mục 1) — quick
> create không thay được bước đó.

### Chọn máy ngoài danh mục của vật tư

Vật tư đã khai "Máy sử dụng" mà bạn chọn một máy **không** nằm trong danh mục
đó: hệ thống **không chặn**, chỉ hiện dòng cảnh báo màu vàng ngay dưới ô —
*"máy … chưa có trong danh mục máy của vật tư …"* — kèm nút **"Gắn máy này
vào vật tư"**. Bấm một lần là ghi luôn vào danh mục "Máy sử dụng" của vật tư
đó (mục 2) rồi cảnh báo tắt, không phải mở riêng màn Danh mục vật tư để làm
lại.

Máy đặt ở khoa khác với khoa nhận trên phiếu cũng chỉ ra **cảnh báo mềm**,
không chặn — có thể một máy dùng chung được mượn tạm cho khoa khác.

### Khi nào bị chặn hẳn

| Thông báo | Nghĩa là gì |
|---|---|
| *"Máy được chọn không thuộc đơn vị bạn."* | Máy không có thật, hoặc của bệnh viện khác |
| *"Máy … đã ngừng hoạt động, không chọn cho phiếu mới được."* | Máy đã bị **Quản lý** bỏ tích Đang hoạt động (mục 7). Phiếu **cũ** đã chọn máy đó trước khi tắt vẫn giữ nguyên, không bị buộc sửa |
| *"Kho đã bật 'Bắt buộc chọn máy' cho phiếu Xuất sử dụng tạo sau thời điểm đó. Còn thiếu máy ở dòng: …"* | Miyano đã bật cờ **bắt buộc chọn máy** cho kho (chỉ áp phiếu **Xuất sử dụng**, tạo **sau** lúc bật; phiếu nháp có từ trước không bị khoá) |

> Cờ này màn hình **chưa có dòng nhắc sớm** như ô Khoa phòng bắt buộc (dòng
> *"Kho đang bật bắt buộc chọn khoa phòng…"* ngay dưới ô Khoa phòng nhận) —
> thông báo chỉ hiện đúng lúc bấm **Ghi sổ** mà còn dòng thiếu máy. Biết
> trước để không bất ngờ khi Miyano báo đã bật cờ cho kho của bạn.

---

## 4. Vì sao phiếu NHẬP không có ô chọn máy

Đây không phải thiếu sót — nghĩ kỹ sẽ thấy phiếu nhập **không thể** trả lời
đúng câu "máy nào" tại thời điểm nó được lập.

Một vật tư có thể dùng cho **nhiều máy** (mục 2) — ví dụ hộp hoá chất ALT
dùng được cho cả máy sinh hoá chính lẫn máy dự phòng. Lúc thủ kho nhận 20 hộp
hoá chất về kho, **chưa ai biết** lô hàng đó rồi sẽ chạy trên máy nào, chạy
bao nhiêu hộp cho máy nào — việc đó chỉ xảy ra sau, từng lần, khi có người
**xuất** hộp hoá chất ra dùng thật.

Giả sử phiếu nhập cũng có ô chọn máy, ba cách làm đều hỏng:

- **Gán cả 20 hộp cho cả hai máy** → cột "theo máy" trên báo cáo cộng thành
  40, trong khi tổng nhập chỉ có 20 — báo cáo tự mâu thuẫn với chính nó.
- **Chia đôi 10/10** → là một **con số bịa**: không ai biết chắc lô đó sẽ
  thật sự chạy bao nhiêu cho máy nào, và không ai ký nhận được một số liệu
  đoán mò.
- **Bắt thủ kho tách dòng ngay lúc nhận hàng** → họ **chưa biết** — hàng vừa
  về kho, chưa đi đâu cả.

Vì vậy hệ thống chốt: **cột "Đã nhập" giữ nguyên là tổng theo vật tư, không
tách theo máy** (đúng như trước đây). Số lượng theo máy chỉ lấy ở **phiếu
xuất** — nơi có một người thật sự đứng ra chọn "hôm nay tôi lấy vật tư này
cho máy này", nên đó là **số có thật**, không phải số suy diễn. Tổng cộng các
dòng theo máy trên báo cáo luôn khớp đúng tổng đã cấp phát trong kỳ — không
bao giờ lệch, vì không có bước ước lượng nào ở giữa.

Nói gọn với bệnh viện khi họ hỏi: *"Nhập thì cứ nhập — hệ thống chỉ hỏi 'máy
nào' vào đúng lúc vật tư thật sự được lấy ra dùng."*

---

## 5. Đọc báo cáo — hai cột xuất nghĩa là gì

**Kho của tôi › Báo cáo vật tư · máy · khoa** (nút riêng, cạnh nút **Báo
cáo** cũ trên màn Kho của tôi) — chọn khoảng ngày, mỗi dòng là **một vật tư**:

| Cột | Nghĩa |
|---|---|
| Mã VT · Tên vật tư · ĐVT | Như danh mục |
| **Tồn đầu** | Tồn tại đầu kỳ |
| **Đã nhập** | Tổng nhập trong kỳ — **không tách theo máy** (mục 4) |
| **Đã cấp phát** | Tổng xuất **sử dụng** trong kỳ, phần đã tách được theo máy — xem bên dưới |
| **Xuất khác** | Xuất huỷ / xuất trả lại / điều chỉnh kiểm kê / phần đã bị đảo — xem bên dưới |
| **Tồn cuối** | Tồn cuối kỳ |
| **Máy sử dụng** | Danh mục máy tương thích khai ở mục 2 — **không phải số liệu**, chỉ để biết vật tư này dùng được cho máy nào |

Bấm vào một dòng để **bung xuống theo máy**: Máy · Khoa phòng · SL xuất ·
Giá trị · %. Máy nào không xuất trong kỳ **không hiện dòng số 0 giả** — chỉ
những máy thật sự có phát sinh mới lên bảng.

### Vì sao có HAI cột xuất, không gộp làm một

Cổng đang chạy **hai cách đếm khác nhau, cố ý khác nhau**, cho hai câu hỏi
khác nhau:

- **"Đã cấp phát"** — chỉ tính phiếu **Xuất sử dụng**, và **loại bỏ** phần đã
  bị huỷ (phiếu đã đảo). Đây là câu hỏi *"khoa nào đang thực sự giữ vật tư đã
  cấp"* — và đúng bằng tổng SL xuất của bảng tách theo máy bên dưới.
- **"Xuất khác"** — xuất huỷ hàng hết hạn, xuất trả lại, điều chỉnh kiểm kê.
  Những loại xuất này **không mang máy** theo thiết kế (ô chọn máy trên phiếu
  chỉ có ý nghĩa với "Xuất sử dụng" — mục 3), nên không tách theo máy được và
  cũng không cần: không ai hỏi "máy nào" cho một lô hàng đã huỷ vì hết hạn.

Tách hai cột để phép cộng luôn đúng, kiểm tra tay được ngay trên giấy:

```
Tồn đầu + Đã nhập − Đã cấp phát − Xuất khác = Tồn cuối
```

Gộp chung "Đã cấp phát" và "Xuất khác" vào một cột "Đã xuất" duy nhất sẽ làm
phép cộng này **sai** — vì "Xuất khác" không có số theo máy để cấn trừ, còn
gộp cả "Đã cấp phát" của phiếu đã bị đảo vào tổng thì tồn cuối sẽ không khớp
với tồn thật đang giữ ở khoa.

### Nhóm "Chưa gắn máy"

Phiếu xuất sử dụng lập từ **trước** khi bệnh viện bắt đầu khai máy (hoặc lập
mà người dùng bỏ trống ô Máy) vẫn được tính đủ vào "Đã cấp phát" — chỉ là
không có tên máy. Bảng tách theo máy xếp những dòng này vào nhóm **"Chưa gắn
máy"**, luôn đặt **ở cuối**, không trộn lẫn vào máy thật và **không bị giấu**
— đó là số liệu thật, không phải lỗi.

---

## 6. Lỗi khai máy thường gặp

| Thông báo | Nguyên nhân | Làm gì |
|---|---|---|
| *"Đơn vị này đã có máy mang mã …"* | Mã máy trùng trong cùng bệnh viện | Đổi mã khác |
| *"Đơn vị này đã có máy tên … (mã …)"* | Tên máy trùng (so không dấu, không phân biệt hoa/thường) | Đổi tên hoặc mở đúng máy đã có |
| *"Máy dùng chung không thuộc khoa nào — chỉ quản lý đơn vị sửa được."* | Nhân viên khoa cố sửa một máy dùng chung | Nhờ Quản lý đơn vị sửa |
| *"Máy này thuộc khoa khác."* | Nhân viên khoa cố sửa máy của khoa khác | Chỉ sửa được máy khoa mình; việc điều chuyển máy sang khoa khác là việc của Quản lý |
| *"Khoa phòng được chọn không thuộc đơn vị này."* | Chọn nhầm khoa của bệnh viện khác (không nên xảy ra qua giao diện bình thường) | Chọn lại đúng khoa của bệnh viện |
| *"Máy … đã được dùng trên phiếu xuất nên không xoá được. Hãy bỏ tích 'Đang hoạt động'…"* | Cố xoá một máy đã có phát sinh | Bỏ tích **Đang hoạt động** thay vì xoá (mục 7) |

---

## 7. Máy ngừng dùng thì làm gì

`Kho của tôi › Thiết bị › Sửa` → bỏ tích **Đang hoạt động**. **Đừng xoá** —
máy đã xuất hiện trên phiếu xuất thì hệ thống cũng không cho xoá (mục 6), và
xoá đi sẽ làm báo cáo các kỳ trước mất tên máy đã cấp phát. Máy tắt biến khỏi
mọi dropdown chọn máy của phiếu **mới**; phiếu **cũ** đã chọn máy đó trước khi
tắt giữ nguyên, không bị buộc sửa lại (mục 3).

---

## Phụ lục — Bảng trường

**`Customer Equipment`** (`TBK-.#####`) — treo vào `Customer`, không có ô kho

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `customer` | Link Customer | bắt buộc |
| `ma_thiet_bi` | Data | bắt buộc, không trùng trong một bệnh viện, tự viết hoa |
| `ten_thiet_bi` | Data | bắt buộc, không trùng trong một bệnh viện (so không dấu) |
| `khoa_phong` | Link Customer Department | để trống = máy dùng chung |
| `hang_san_xuat` · `xuat_xu` · `model` · `so_serial` · `nam_san_xuat` · `ngay_lap_dat` · `ghi_chu` | mô tả, không bắt buộc | |
| `active` | Tích | mặc định bật; tắt thay vì xoá |

**`Customer Warehouse Item`** — thêm bảng con **"Máy sử dụng"**
(`may_su_dung` → `Customer Warehouse Item Equipment`, một cột `thiet_bi`) —
danh mục máy tương thích, không phải số liệu (mục 2).

**`Customer Stock Issue Item`** (dòng phiếu xuất) — thêm `thiet_bi` (Link
Customer Equipment), không bắt buộc trừ khi kho bật cờ (mục 3).

**`Customer Stock Issue`** (đầu phiếu xuất) — thêm `thiet_bi_mac_dinh` (Link
Customer Equipment) — **chỉ để điền nhanh xuống các dòng**, không tự ghi vào
sổ và không đọc trong bất kỳ báo cáo nào.

**`Customer Warehouse`** — thêm cặp `bat_buoc_thiet_bi` (Tích) /
`bat_buoc_thiet_bi_tu` (Datetime, chỉ đọc, hệ tự ghi) — sao y cặp
`bat_buoc_khoa_phong` đang chạy cho khoa phòng. Do **Miyano** bật trên Desk
cho từng bệnh viện, không phải bệnh viện tự bật.
