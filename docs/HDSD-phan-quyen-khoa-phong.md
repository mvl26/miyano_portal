# Hướng dẫn thao tác — Phân quyền theo khoa phòng trên cổng khách hàng

App `miyano_portal` · Cập nhật **03/09/2026** · Áp dụng từ bản nền (bước 1–4)

**Tài liệu này dành cho nhân viên Miyano** làm việc trên Desk (`/app`). Vòng
"khoa yêu cầu → quản lý duyệt → đơn sang Miyano" nay **chạy trọn vẹn trên cổng
khách**: nhân viên khoa tự lập yêu cầu ở màn **Đặt hàng**, quản lý duyệt **ngay
trên màn chi tiết đơn**, cả hai theo dõi ở màn **Danh sách đơn hàng** — xem §4,
mục "Thao tác trên màn hình". (Màn **Duyệt** riêng đã gỡ 03/09/2026 — hàng chờ
nay là chip **Chờ duyệt** của chính danh sách đó.) Màn quản lý thành viên vẫn chưa làm (§7 mục 2).

---

## 0. Điều quan trọng nhất: chưa làm gì thì chưa đổi gì

Sau khi cài bản này, **mọi bệnh viện đang dùng cổng vẫn hoạt động y như trước**.
Mọi tài khoản hiện có được hệ thống tự đánh là **Quản lý** không gắn khoa phòng,
nên họ vẫn thấy toàn bộ đơn hàng của bệnh viện mình.

Việc cách ly theo khoa **chỉ bắt đầu có tác dụng** khi bạn thật sự tạo một thành
viên có vai trò **Nhân viên khoa**. Nghĩa là bạn bật cho từng bệnh viện một, khi
họ sẵn sàng — không có ngày "cả hệ thống đổi cách hoạt động".

> **Hệ quả cần nhớ:** một bệnh viện chưa bật thì không cần làm gì cả. Đừng khai mã
> ngắn hay khoa phòng cho họ "cho đủ".

---

## 1. Ba khái niệm mới

| Khái niệm | Là gì | Ở đâu trên Desk |
|---|---|---|
| **Mã ngắn khách hàng** | Mã viết tắt của bệnh viện, ví dụ `BM`. Dùng làm phần đầu mã phiếu đề xuất mua sau này | `Customer` → ô **Mã ngắn (cổng khách)** |
| **Khoa phòng** | Khoa/phòng/đơn vị của bệnh viện. Trước đây thuộc về **kho**, nay thuộc về **bệnh viện** | Doctype `Customer Department` |
| **Thành viên cổng** | Một tài khoản cổng thuộc bệnh viện nào, vai trò gì, khoa nào | Doctype `Portal Member` |

**Hai vai trò, và chỉ hai:**

- **Quản lý** — nhìn thấy **toàn bộ** đơn của bệnh viện. **Mỗi bệnh viện đúng một
  quản lý đang hoạt động.** Không gắn vào khoa phòng nào.
- **Nhân viên khoa** — chỉ nhìn thấy đơn của **khoa mình**. Bắt buộc phải có khoa
  phòng khi được kích hoạt.

---

## 2. Bật phân quyền khoa phòng cho một bệnh viện

**Ba bước, và thứ tự là bắt buộc** — hệ thống sẽ chặn nếu làm sai thứ tự. Bước 4
chỉ dùng cho tài khoản cấp lẻ, không đi qua bảng nhân sự.

### Bước 1 — Đặt Mã ngắn cho bệnh viện

`Customer` → mở bệnh viện → ô **Mã ngắn (cổng khách)** → điền, ví dụ `BM`.

- Chữ hoa không dấu, tối đa 10 ký tự.
- **Không được trùng** với bệnh viện khác.

> **Vì sao phải làm trước:** mã này đi vào tên phiếu đề xuất mua. Hệ thống **không
> cho** tạo Nhân viên khoa cho một bệnh viện chưa có mã ngắn — và nó chặn ngay lúc
> bạn cấp tài khoản, chứ không để tới lúc nhân viên bệnh viện bấm gửi mới báo lỗi.

### Bước 2 — Khai khoa phòng

**Khai trước là tuỳ chọn.** Bảng nhân sự ở bước 3 có cột Khoa và Mã khoa; khoa nào
chưa có, hệ thống tạo luôn khi bạn bấm Ghi, và bản xem trước nói rõ nó sắp tạo
những khoa nào. Khai tay trước chỉ cần khi bệnh viện muốn gắn kho cho khoa, hoặc
khi bạn muốn chốt sẵn tên và mã khoa cho đúng.

`Customer Department` → **New** cho từng khoa:

| Ô | Điền gì |
|---|---|
| **Khách hàng** | bệnh viện — **bắt buộc** |
| **Tên khoa phòng** | tên đầy đủ, ví dụ `Khoa Huyết học`. Chữ tự do, nên khai được cả `Phòng khám 1`, `Phòng Xét nghiệm` |
| **Mã khoa** | viết tắt, ví dụ `HUYETHOC` |
| **Kho** | **để trống** nếu bệnh viện chưa dùng kho trên cổng |

Quy tắc **Mã khoa** — hệ thống tự viết hoa và kiểm:

- chỉ chữ cái không dấu và chữ số (`HUYETHOC` được, `HUYẾT HỌC` và `XN-01` bị chặn);
- **không trùng trong cùng một bệnh viện** (hai bệnh viện khác nhau được phép trùng);
- **`CHUNG` là mã dành riêng của hệ thống**, không đặt cho khoa phòng được.

**Tên khoa phòng** cũng không được trùng trong cùng bệnh viện, và hệ thống so
**không dấu** — `Khoa Hồi sức` và `Khoa Hoi suc` bị coi là một.

### Bước 3 — Cấp tài khoản

Dùng màn **Nhập nhân sự bệnh viện** trên Desk (workspace *Kho khách hàng*): tải
bảng mẫu Excel cho bệnh viện điền, tải lên, xem trước rồi ghi. Cách làm chi tiết
nằm ở tài liệu *tạo khách hàng · mở kho · thao tác trên cổng*, mục A5.

Bảng nhân sự nói rõ từng người là **Quản lý** hay **Nhân viên khoa**, và nhân
viên khoa thuộc khoa nào. Tài khoản cấp theo bảng này **đang hoạt động và đã gán
khoa ngay** — dùng được luôn, không còn bước gán khoa sau.

Ba điều bảng xem trước sẽ nhắc trước khi bạn ghi:

- Bệnh viện **chưa có Mã ngắn** mà bảng có nhân viên khoa → từ chối, làm bước 1 trước.
- Bảng **không có ai làm Quản lý** và bệnh viện cũng chưa có quản lý đang hoạt
  động → cảnh báo: sẽ không ai duyệt được yêu cầu của các khoa.
- Một email **đã thuộc bệnh viện khác** → cảnh báo, không tạo lại và không đổi mật
  khẩu của người đó. Bạn tự quyết là gõ nhầm hay đúng là một người làm hai nơi.

### Bước 4 — Chỉ khi cấp tài khoản lẻ

Tài khoản cấp lẻ (không qua bảng nhân sự) cho một bệnh viện **đã có quản lý** sẽ
thành **Nhân viên khoa**, **chưa hoạt động**, **chưa gán khoa**. Nó chưa dùng được:

`Portal Member` → mở bản ghi vừa tạo:

1. **Vai trò** = `Nhân viên khoa`
2. **Khoa phòng** = chọn khoa của người đó
3. Tích **Hoạt động**
4. **Lưu**

> Hiện quản lý bệnh viện **chưa có màn hình** để tự làm việc này — màn "Thành viên
> & phân quyền" thuộc bước 9, chưa làm. Tạm thời Miyano làm hộ trên Desk.

---

## 3. Thao tác hằng ngày

### Nhân viên chuyển khoa

`Portal Member` → đổi ô **Khoa phòng** → Lưu. Có hiệu lực ngay.

Đơn **đã đặt** vẫn mang khoa cũ — đó là chủ đích: đơn ghi lại nơi đã yêu cầu hàng
tại thời điểm đặt, không phải nơi người đó đang làm việc hôm nay.

### Nhân viên nghỉ việc

**Bỏ tích Hoạt động**, đừng xoá bản ghi. Xoá đi là mất luôn dấu vết ai đã đặt
những đơn cũ.

Tài khoản bị tắt thì **không đăng nhập dùng được và không nhận thông báo nữa**.

### Đổi quản lý bệnh viện

Hệ thống chỉ cho **một quản lý đang hoạt động** cho mỗi bệnh viện, nên phải làm
**đúng thứ tự này**:

1. Mở bản ghi quản lý **cũ** → bỏ tích **Hoạt động** → Lưu.
2. Mở bản ghi người **mới** → Vai trò = `Quản lý` → **xoá trống ô Khoa phòng** →
   tích **Hoạt động** → Lưu.

Làm ngược lại sẽ bị chặn với thông báo *"Bệnh viện này đã có quản lý là …"*.

### Tắt một khoa phòng

`Customer Department` → bỏ tích **Hoạt động**. **Đừng xoá** — khoa phòng đã dùng
trên phiếu xuất kho thì hệ thống cũng không cho xoá.

---

## 4. Luồng đề xuất mua — nhân viên đề xuất, quản lý duyệt

**Đây là phần mới nhất, và là lý do cả đề án tồn tại.** Trước đây một bệnh viện một
tài khoản, ai cũng đặt hàng thẳng. Giờ nhân viên khoa **đề xuất**, quản lý **duyệt**,
rồi đơn mới sang Miyano.

**Cả hai vai làm việc đó ở cùng một chỗ: màn Đặt hàng.** Không còn hai lối "đặt
hàng" và "lập phiếu đề xuất" chạy song song, cũng không còn hai chế độ "theo hợp
đồng khung" và "mua lẻ". Người dùng tìm hàng trong một danh sách, bỏ vào một giỏ,
rồi bấm nút cuối màn — nút đó ghi **Gửi duyệt** với nhân viên khoa và **Đặt hàng**
với quản lý.

### Ai làm được gì

| Việc | Nhân viên khoa | Quản lý |
|---|---|---|
| Lập yêu cầu ở màn Đặt hàng | ✔ | ✔ |
| Sửa số lượng khi yêu cầu còn **Nháp** | ✔ | ✔ |
| Xoá yêu cầu **Nháp** | ✔ (của mình) | ✔ |
| Gửi duyệt | ✔ (của mình) | — |
| Duyệt / Từ chối | ✘ | ✔ |
| Huỷ yêu cầu đã gửi | ✘ | ✔ |
| Đặt hàng thẳng, không qua duyệt | ✘ | ✔ |

**Nhân viên khoa không đặt hàng thẳng được nữa.** Màn Đặt hàng chỉ cho họ nút **Gửi
duyệt**; không có nút nào đưa đơn sang Miyano mà không qua quản lý. Đây là thay đổi
hành vi có chủ đích — nếu để họ đặt thẳng thì cổng duyệt chỉ là trang trí.

### Một danh sách, ba loại dòng hàng

Màn Đặt hàng có **một ô tìm kiếm** và **một danh sách**, 10 dòng mỗi trang. Hàng
thuộc hợp đồng của chính bệnh viện đó đứng trước, hết rồi mới tới danh mục chung
của Miyano. Mỗi dòng hiện tình trạng hàng — **Còn hàng** hoặc **Liên hệ** — và một
trong hai nhãn giá:

| Loại dòng | Nhãn trên màn hình | Nghĩa |
|---|---|---|
| Hàng trong hợp đồng của bệnh viện | **Giá HĐ** kèm số tiền và mã hợp đồng | Giá đã ký, đặt là biết ngay bao nhiêu tiền |
| Hàng Miyano có bán nhưng ngoài hợp đồng | **Chờ báo giá** | Miyano ra giá sau |
| Hàng Miyano chưa có mã | **Chờ báo giá** | Người dùng bấm nút *"+ Thêm dòng — hàng chưa có trong hệ thống"* rồi tự gõ tên hàng, đơn vị tính, số lượng. Miyano tìm nguồn và báo lại |

Nút thêm dòng hàng chưa có mã **luôn hiện**, không phải tìm không ra mới xuất hiện.

Vượt hạn mức hợp đồng ở màn này là **cảnh báo**, không chặn: khoa vẫn xin được 100
khi hợp đồng còn 40, và quản lý gõ số duyệt thật lúc duyệt. Hệ thống không tự cắt
số lượng thay quản lý. Nhưng **lúc thật sự sinh đơn** — quản lý duyệt, hoặc quản lý
bấm Đặt hàng thẳng — thì hạn mức là chốt cứng và việc đó thất bại; xem mục *"Quản
lý duyệt như thế nào"* bên dưới.

### Điều bệnh viện sẽ hỏi: vì sao hàng hợp đồng phải chờ

**Một đơn có bất kỳ dòng nào chưa có giá thì CẢ ĐƠN chờ Miyano báo giá rồi mới
giao — kể cả những dòng đã có giá hợp đồng.** Trước đây hàng hợp đồng giao được
ngay; nay nếu nó đứng chung đơn với hàng chưa có giá thì nó chờ cùng.

Màn Đặt hàng nói thẳng điều này ngay trên nút gửi:

> Đơn có hàng chờ báo giá — cả đơn sẽ chờ Miyano báo giá trước khi giao.

**Vì sao:** một đơn hàng là **một** chứng từ, có **một** ngày giao và **một** hoá
đơn. Muốn phần có giá đi trước thì phải cắt nó thành hai đơn — và hệ thống không
tự cắt, vì cắt đơn của bệnh viện là một quyết định thương mại mà nó không đủ thông
tin để ra thay người dùng.

**Khoa cần hàng gấp thì làm gì:** đặt **hai lần**. Một yêu cầu chỉ gồm hàng có giá
hợp đồng — nó đi thẳng, Miyano xác nhận rồi giao như trước. Một yêu cầu riêng cho
phần chờ báo giá. Đây là câu trả lời đúng khi bệnh viện gọi hỏi *"sao hàng hợp
đồng của chúng tôi lâu nay giao ngay mà giờ nằm chờ"*.

### Vòng đời một phiếu

```
Nháp ──Gửi duyệt──► Chờ duyệt ──Duyệt──► Đã duyệt ──► sinh đơn hàng gửi Miyano
 │                      │
 │                      └──Từ chối (bắt buộc ghi lý do)──► Từ chối ──sửa──► Chờ duyệt
 └──Xoá thật                Chờ duyệt trở đi ──Huỷ──► Đã huỷ (phiếu còn nguyên)
```

**Xoá và huỷ là hai việc khác nhau.** Phiếu **Nháp** chưa ai ngoài người lập nhìn
thấy, chưa có mã — xoá thật khỏi hệ thống. Từ **Chờ duyệt** trở đi phiếu đã có mã và
đã vào hàng chờ của quản lý — chỉ **huỷ**, phiếu ở lại để truy vết. Nút trên màn hình
ghi đúng việc đang làm: "Xoá" ở Nháp, "Huỷ phiếu" từ Chờ duyệt trở đi.

### Bệnh viện nhìn thấy vòng đời đó như thế nào

Trên cổng, khách không thấy "phiếu" và "đơn" là hai thứ. Họ thấy **một** danh sách
**Danh sách đơn hàng**, mỗi yêu cầu đúng một dòng từ lúc soạn tới lúc nhận hàng:

| Giai đoạn | Nghĩa là | Ai đang giữ việc |
|---|---|---|
| **Nháp** | Đang soạn, chưa gửi | Người lập |
| **Chờ duyệt** | Đã gửi, gồm cả yêu cầu xin sửa số lượng | Quản lý bệnh viện |
| **Đã duyệt** | Quản lý đã duyệt, đơn đã sang Miyano và đang chạy — kể cả khi Miyano còn đang gom giá, hoặc đã giao được một phần | Miyano |
| **Chờ quý vị đồng ý** | **Miyano đã báo giá xong và đang chờ bệnh viện trả lời** (hoặc báo giá đã quá hạn) | Bệnh viện |
| **Đã giao** | Đã giao đủ, hoặc đơn đã đóng | — |
| **Từ chối** · **Đã huỷ** | Hai ngõ cụt, yêu cầu ở lại để truy vết | — |

> **Đọc kỹ hai dòng giữa.** Một yêu cầu **đang chờ Miyano ra giá** nằm ở *"Đã
> duyệt"* — cùng chỗ với yêu cầu đã có giá và đang chạy. *"Chờ quý vị đồng ý"* là
> bước SAU đó: **giá đã về, bệnh viện cần mở yêu cầu ra và trả lời.** Nói ngược
> hai dòng này là để bệnh viện ngồi chờ một việc đang thuộc về chính họ.
>
> *(Giai đoạn này trước đây tên "Chờ báo giá" — cái tên đó đọc như đang chờ
> Miyano, đúng ngược chiều việc, và là lý do chủ đầu tư cho đổi tên ngày
> 26/08/2026. Link cũ mang tên cũ vẫn mở đúng chip.)*

Trước bản này, một yêu cầu nằm ở màn "Đề xuất mua" khi còn là phiếu rồi **nhảy**
sang màn "Đơn hàng của tôi" sau khi quản lý duyệt — muốn tìm lại yêu cầu của chính
mình, nhân viên phải đoán trước nó đang ở giai đoạn nào. Nay nó không nhảy đi đâu
cả. Các đường dẫn cũ vẫn dùng được, chúng tự chuyển sang màn mới.

### Mã phiếu

```
BM-HUYETHOC-260819-01
│   │        │      └─ số thứ tự trong ngày của chính khoa đó
│   │        └─ ngày gửi duyệt (YYMMDD)
│   └─ mã khoa phòng
└─ mã ngắn bệnh viện
```

**Mã sinh lúc bấm Gửi duyệt**, không sớm hơn — lúc còn Nháp giỏ hàng vẫn đang đổi.
Sinh **đúng một lần**: phiếu bị từ chối rồi gửi lại vẫn giữ mã cũ, vì quản lý và khoa
đã gọi tên nó bằng mã đó trong lúc trao đổi. Không sửa tay được.

Vượt 99 phiếu cùng khoa trong một ngày thì tràn sang 3 chữ số (`…-100`), không quay
vòng — mã trùng tệ hơn mã dài.

Đơn quản lý đặt cho **toàn viện** dùng mã khoa dành riêng `CHUNG`: `BM-CHUNG-260819-01`.

**Đơn sinh ra từ một phiếu được duyệt nay MANG CHÍNH MÃ ĐÓ làm số đơn.** Bệnh viện
và Miyano gọi tên cùng một chứng từ bằng cùng một mã — hết cảnh khoa đọc mã phiếu
còn sales tra số đơn rồi hai bên nói về hai tờ giấy.

**Một ngoại lệ, nhớ cho kỹ:** đơn quản lý **bấm Đặt hàng thẳng** từ màn Đặt hàng
vẫn mang số đơn cũ dạng `SAL-ORD-…`, còn mã phiếu được ghi kèm bên cạnh làm mã tra
cứu. Chỉ đơn đi qua **duyệt** mới lấy mã phiếu làm số đơn. Đừng nói với bệnh viện
rằng mọi đơn đều mang mã mới.

### Ba thứ ghi trên phiếu để sau này truy vết

Hiện ngay đầu phiếu, không phải đi tìm trong lịch sử:

- **Người yêu cầu** — hệ thống ghi từ tài khoản thao tác, không gõ tay.
- **Thời điểm gửi** — ghi lúc bấm Gửi duyệt, không phải lúc tạo nháp. Nháp soạn ba
  ngày rồi mới gửi thì mốc truy vết là lúc gửi.
- **Lý do yêu cầu** — **bắt buộc khi Gửi duyệt**, không bắt lúc lưu nháp. Bắt điền
  ngay từ dòng đầu sẽ khiến người ta gõ "abc" cho xong.

### Quản lý duyệt như thế nào

Quản lý sửa được **cột Số lượng duyệt**, không sửa được cột Số lượng đề xuất — cột đó
**khoá vĩnh viễn** từ lúc khoa bấm gửi. Đó là cách hệ thống trả lời được câu "khoa xin
gì / duyệt gì" mà không cần lưu hai bản dữ liệu song song.

- Bỏ một mặt hàng = **hạ Số lượng duyệt về 0**, không xoá dòng.
- Thêm mặt hàng = dòng mới, Số lượng đề xuất bằng 0, đánh dấu "Quản lý thêm".
- Chỉ dòng có Số lượng duyệt lớn hơn 0 mới đi vào đơn hàng gửi Miyano.

**Hết hạn mức hợp đồng thì việc duyệt thất bại kèm tên khoa đã tiêu mất** — hệ thống
không lặng lẽ cắt số lượng xuống. Hạn mức là tài nguyên chung giữa các khoa; trước đây
một bệnh viện một tài khoản nên chuyện này không xảy ra.

**Giá tính lại tại thời điểm duyệt.** Nếu khác giá khoa đã nhìn thấy lúc gửi, hệ thống
trả về cảnh báo lệch giá — **không chặn việc duyệt**, chỉ báo.

### Sửa số lượng sau khi Miyano đã báo giá

Đây là chỗ dễ hiểu nhầm nhất, nên nói rõ:

- Nhân viên **đồng ý** với báo giá → **tự làm xong**, đơn đi tiếp. Không cần duyệt lại.
- Nhân viên muốn **đổi số lượng** → phải bấm **Xin sửa số lượng**, phiếu quay về
  **Chờ duyệt sửa**, quản lý duyệt lần nữa rồi đơn mới đổi.

Nếu để nhân viên đổi thẳng thì quản lý duyệt 10 hộp mà hàng về 100 hộp — đó là lỗ hổng
của chính cổng duyệt. Còn bắt duyệt lại cả khi họ chỉ **đồng ý** thì làm tắc con đường
thông thường mà không kiểm soát thêm được gì.

Số khoa xin đổi ghi ở **cột thứ ba** riêng, không đè lên số đã duyệt — quản lý phải
nhìn thấy cả hai để so.

### Quản lý đặt hàng trực tiếp

Quản lý bấm **Đặt hàng** ở cuối giỏ thì đơn sang Miyano **ngay trong một lần bấm** —
họ vốn là người duyệt, bắt họ gửi duyệt rồi tự duyệt là bắt bấm hai lần cho một việc.
Hệ thống **tự lập một phiếu đề xuất đã duyệt** đứng sau. Không phải bấm thêm nút nào.
Mục đích: **mọi đơn trên hệ thống đều có đúng một chứng từ đứng sau** — không có hai
loại đơn với hai lịch sử khác nhau.

**Đơn quản lý đặt thẳng là đơn của TOÀN VIỆN, không gắn khoa nào.** Màn Đặt hàng
không còn ô chọn khoa phòng, nên **chỉ quản lý nhìn thấy đơn đó** — nhân viên của
khoa sẽ không thấy đơn quản lý đặt hộ mình, cũng không thấy phiếu giao và hoá đơn
của nó. Muốn đơn thuộc về một khoa và khoa đó theo dõi được, để **chính nhân viên
khoa** lập yêu cầu rồi quản lý duyệt.

**Bệnh viện chưa có Mã ngắn vẫn đặt hàng được.** Phiếu sinh ra sẽ không có mã tra cứu
cho tới khi Miyano đặt Mã ngắn. Mã tra cứu là tiện ích đối chiếu, không phải điều kiện
để mua hàng.

### Thao tác trên màn hình

Phần trên nói *luật*. Phần này nói *bấm ở đâu* — và **những gì màn hình chưa làm
được**, để người triển khai không hứa nhầm với bệnh viện.

**Ba màn của luồng này trên cổng khách:**

| Màn | Ai thấy | Làm được gì |
|---|---|---|
| **Đặt hàng** | mọi vai trò | Tìm hàng, bỏ vào giỏ, điền lý do yêu cầu, ngày giao mong muốn, địa chỉ giao — rồi **Gửi duyệt** (nhân viên khoa) hoặc **Đặt hàng** (quản lý). Có nút **Lưu nháp** để soạn dở |
| **Danh sách đơn hàng** | mọi vai trò | Danh sách gộp — nhân viên khoa thấy đơn **khoa mình**, quản lý thấy **toàn đơn vị**. Lọc bằng dải chip giai đoạn (`Tất cả / Nháp / Chờ duyệt / Đã duyệt / Chờ quý vị đồng ý / Đã giao / Từ chối / Đã huỷ`), quản lý lọc thêm được theo **khoa phòng**. Chip **Chờ duyệt** CHÍNH LÀ hàng chờ của quản lý (gộp `Chờ duyệt` + `Chờ duyệt sửa`); con số đỏ trên mục menu là số đơn đang chờ, **chỉ quản lý thấy** |
| **Chi tiết yêu cầu** | ai mở được yêu cầu đó | Đầu phiếu (truy vết), bảng dòng hàng kèm nhãn giá từng dòng, và thanh nút hành động theo trạng thái + vai trò |

**Toàn bộ menu của khách nay còn 7 mục, giống nhau cho mọi vai trò**: Tổng quan ·
Đặt hàng · Danh sách đơn hàng · Kho của tôi · Hoá đơn & công nợ · Thông báo · Hồ sơ
đơn vị. Bốn mục cũ *Giỏ hàng*, *Đơn hàng của tôi*, *Đề xuất mua*, *Duyệt* đã biến
mất; đường dẫn cũ của chúng tự chuyển sang màn mới nên link trong thông báo đã gửi
đi và bookmark của khách vẫn dùng được (`/duyet` chuyển sang danh sách đơn hàng đã
lọc sẵn chip **Chờ duyệt**).

**Quản lý sửa số lượng rồi duyệt — thao tác chính, làm ở màn chi tiết:**

1. Vào **Danh sách đơn hàng** → chip **Chờ duyệt** → chọn khoa nếu muốn → bấm
   vào đơn.
2. Phiếu ở trạng thái **Chờ duyệt** thì cột **SL duyệt** là **ô nhập được**, và mỗi
   dòng có thêm một ô **ghi chú của quản lý**. Cột **SL đề xuất** không sửa được —
   khoá vĩnh viễn từ lúc khoa bấm Gửi duyệt.
3. Ba quy ước phải nhớ, màn hình cũng nhắc ngay trên thanh nút:
   - **Ô để trống = giữ nguyên dòng đó.** Không phải "duyệt 0".
   - **Gõ số 0 = bỏ mặt hàng khỏi đơn.** Dòng vẫn nằm lại trên phiếu (gạch ngang,
     gắn nhãn "Không duyệt") để sau này còn truy vết được là khoa đã xin gì.
   - **Không sửa gì thì cứ bấm Duyệt** — phiếu được duyệt nguyên số khoa đã xin.
     Không bắt buộc phải nhập gì.
4. Bấm **Duyệt** → hộp xác nhận liệt kê từng điều chỉnh (`hạ 100 → 40`, `BỎ khỏi
   đơn`…) → đồng ý → đơn hàng gửi Miyano sinh ra **theo số đã duyệt**.

Ví dụ đúng tình huống hay gặp: khoa xin 100 hộp, quản lý chỉ đồng ý 40 → gõ `40` vào
ô SL duyệt của dòng đó, bấm Duyệt. Đơn sang Miyano mang số **40**.

**Nút "Quay lại"** đưa về đúng danh sách đã tới, giữ nguyên bộ lọc khoa **và** chip
trạng thái đang mở — duyệt liên tiếp nhiều phiếu của một khoa không phải chọn lại
bộ lọc sau mỗi phiếu.

### Nhân viên khoa sửa đơn đang "Chờ duyệt"

Gõ nhầm số rồi mới bấm Gửi duyệt là chuyện thường. Từ 03/09/2026, **chủ đơn** (đúng
người đã lập) mở đơn ở trạng thái **Chờ duyệt** sẽ thấy nút **Thu hồi để sửa**:

1. Bấm nút → hộp xác nhận nói rõ đơn sẽ **về Nháp** và **rời hàng chờ của quản lý**.
2. Hệ thống đưa thẳng sang màn **Đặt hàng** với đúng đơn đó, sửa thoải mái.
3. Sửa xong bấm **Gửi duyệt** lại. **Mã đơn giữ nguyên** — quản lý và khoa vẫn gọi
   tên nó bằng đúng mã cũ.

Vì sao phải đi vòng qua Nháp thay vì sửa tại chỗ: cột **Số lượng đề xuất** khoá
vĩnh viễn từ lúc Gửi duyệt (đó là cách hệ thống trả lời "khoa xin gì / duyệt gì").
Thu hồi là cách mở khoá đó mà không phá phép so sánh ấy.

**Ai KHÔNG có nút này:** đồng nghiệp cùng khoa, và quản lý (trên đơn của người
khác). Quản lý muốn trả đơn về cho khoa thì dùng **Từ chối** — bắt buộc ghi lý do,
để khoa biết vì sao. Quản lý cũng không cần nút này: họ sửa số lượng thẳng ở cột
**SL duyệt** ngay trên màn chi tiết.

**Quản lý đang mở đúng đơn vừa bị thu hồi** rồi bấm Duyệt sẽ nhận báo lỗi "không
chuyển được phiếu từ Nháp sang Đã duyệt" — đơn đã rời hàng chờ, không có gì bị
duyệt nhầm.

**Nhân viên khoa xin sửa số lượng** (sau khi Miyano đã báo giá): mở phiếu **Đã
duyệt** → nút **Xin sửa số lượng** → nhập số mong muốn từng dòng → gửi. Cũng đúng
quy ước trên: ô để trống nghĩa là không đổi dòng đó, gõ 0 nghĩa là xin bỏ mặt hàng.
Phiếu chuyển sang **Chờ duyệt sửa** và quay lại hàng chờ của quản lý.

Màn chi tiết **chưa có ô thêm mặt hàng mới** cho quản lý. Trên cổng, quản
lý hiện chỉ **hạ số lượng, bỏ mặt hàng và ghi chú** — muốn **thêm** một mặt hàng mà
khoa không xin thì **quản lý bệnh viện không tự làm được**, phải báo nhân viên Miyano
thêm giúp trên Desk. (Tài khoản bệnh viện là Website User, **không vào được** màn
quản trị — đừng hướng dẫn họ "vào Desk mà làm".)

### Thông báo giờ gửi đúng người

| Việc | Ai nhận |
|---|---|
| Khoa gửi đề xuất | Quản lý |
| Quản lý duyệt / từ chối | Người lập phiếu + thành viên khác của khoa đó |
| Miyano hẹn giao, giao hàng | Quản lý + thành viên của khoa đứng tên đơn |

Trước đây thông báo giao hàng gửi cho **mọi** tài khoản của bệnh viện. Với một tài
khoản thì đúng; với mười lăm tài khoản thì khoa Dược nhận thông báo về hàng của khoa
Huyết học mỗi ngày.

**Một ngoại lệ còn lại:** thông báo *"Miyano đã xác nhận đơn"* vẫn gửi theo email liên
hệ trên đơn, không lọc theo khoa — thông báo đó do nền tảng Frappe tự định tuyến, phần
mềm mình không chen vào được. Không phải quên, là giới hạn kỹ thuật thật.

---

## 5. Gặp lỗi thì tra ở đây

| Thông báo | Nghĩa là gì | Làm gì |
|---|---|---|
| *"Nhân viên khoa phải được gán một khoa phòng."* | Đang bật Hoạt động cho một Nhân viên khoa chưa chọn khoa | Chọn khoa phòng rồi lưu lại |
| *"Quản lý nhìn xuyên mọi khoa nên không gắn vào khoa phòng nào."* | Quản lý mà lại điền ô Khoa phòng | Xoá trống ô Khoa phòng |
| *"Khoa phòng được chọn không thuộc khách hàng này."* | Chọn nhầm khoa của bệnh viện khác | Chọn lại đúng khoa của bệnh viện đó |
| *"Bệnh viện này đã có quản lý là …"* | Đang tạo quản lý thứ hai | Tắt quản lý cũ trước — xem mục 3 |
| *"Khách hàng … chưa có Mã ngắn."* | Cấp Nhân viên khoa cho bệnh viện chưa khai mã ngắn | Làm bước 1 trước |
| *"Bệnh viện này đã có khoa phòng mang mã …"* | Mã khoa trùng trong cùng bệnh viện | Đổi mã khoa |
| *"Mã khoa chỉ được dùng chữ cái không dấu và chữ số"* | Mã khoa có dấu, khoảng trắng hoặc ký tự lạ | Ví dụ đúng: `HUYETHOC` |
| Khách báo **"không tìm thấy chứng từ"** khi mở một đơn | Đơn đó thuộc khoa khác | Đúng như thiết kế. Muốn xem hết thì phải là Quản lý |
| Khách báo **"Tài khoản chưa được kích hoạt"** | Tài khoản đã cấp nhưng chưa gán khoa và chưa bật | Làm **bước 4** — gán khoa phòng rồi tích Hoạt động |
| Khách báo **"Tài khoản chưa gắn với khách hàng nào"** | Tài khoản **không có** bản ghi Thành viên cổng nào — lỗi cấu hình | Tạo `Portal Member` cho tài khoản đó. Hai thông báo này khác nhau, đừng nhầm |

> **Vì sao "của khoa khác" và "không có thật" báo giống hệt nhau:** phân biệt hai
> cái đó chính là tiết lộ rằng chứng từ tồn tại. Trong bệnh viện, *"khoa Dược có
> đơn mã X"* đã là thông tin.

---

## 6. Checklist triển khai — đọc trước khi lên bản

**Ba việc, thiếu một là hỏng:**

1. **`bench --site <site> migrate`** — bắt buộc. Bản này thêm cột mới vào bảng đơn
   hàng. Chưa migrate mà chạy mã mới thì cổng khách **từ chối mọi truy vấn**.
2. **Khởi động lại worker sau khi migrate.** Hệ thống nhớ kết quả kiểm "cột đã có
   chưa" trong bộ nhớ tiến trình để khỏi hỏi lại mỗi truy vấn. Worker cũ vẫn nhớ
   giá trị trước migrate cho tới khi được khởi động lại — và nó sẽ **từ chối mọi
   truy vấn** dù cơ sở dữ liệu đã đúng.
3. **Kiểm patch đã chạy THẬT.** Có một bẫy đã gặp trên dự án này: `install_app`
   **ghi nhật ký patch mà không thật sự chạy nó**. Nên dòng khai báo trong
   `patches.txt` không phải bằng chứng. Chạy trên chính site đích:

```sql
-- phải trả về 3 dòng (bản này thêm 2 cột nữa cho luồng đề xuất)
select column_name from information_schema.columns
 where table_name='tabSales Order'
   and column_name in ('custom_khoa_phong','custom_de_xuat','custom_ma_tra_cuu');

-- phải có dòng cho CẢ HAI patch, và skipped = 0
select name, patch, creation, skipped from `tabPatch Log`
 where patch like '%them_khoa_phong_vao_don_hang%'
    or patch like '%them_de_xuat_vao_don_hang%';
```

Ba cột trên là của **bản phân quyền khoa phòng**. Thiếu chúng thì chốt "nhân viên
không sửa số lượng sau khi đã duyệt" **không có gì để đọc** — hệ thống sẽ **chặn
nhân viên khoa** kèm thông báo "Hệ thống chưa hoàn tất cập nhật", chứ không mở
toang. An toàn, nhưng họ không làm việc được cho tới khi anh chạy migrate.

> **Truy vấn trên chỉ kiểm bản phân quyền, không kiểm bản anh đang cài.** Mỗi bản
> sau lại thêm cột và bản vá riêng. Cách kiểm đúng cho **mọi** bản: sau khi migrate,
> mở `tabPatch Log` và xác nhận **mọi** bản vá của bản đang cài đều có một dòng và
> `skipped = 0`. Danh sách bản vá của một bản nằm trong ghi chú phát hành của chính
> bản đó — đừng dựa vào truy vấn cố định ở đây.

**Nếu quên bước 2 hoặc 3:** cổng khách từ chối mọi thứ (an toàn, không rò rỉ), và
có một dòng trong `Error Log` nói rõ thiếu cột. Chạy migrate, restart, xong.

---

## 7. Hệ thống cố ý CHƯA làm

Nói rõ để không ai chờ nhầm:

1. **Kho vật tư chưa cách ly theo khoa.** Nhân viên khoa vẫn thấy toàn bộ màn Kho —
   thuộc bước 8 của thiết kế.

   **Điều này có hệ quả cần biết, không phải chi tiết kỹ thuật:** phiếu nhập kho có
   ghi số đơn hàng sinh ra nó. Nên tới khi bước 8 xong, một nhân viên khoa vẫn có
   thể mở màn Kho, xem phiếu nhập và **đọc được số đơn của khoa khác** kèm mặt hàng
   và tổng tiền của đợt giao đó. Họ không mở được chính đơn hàng, nhưng cách ly theo
   khoa **chưa trọn vẹn** chừng nào bước 8 chưa chạy. Nếu bệnh viện hỏi, đừng nói
   là đã cách ly xong.
2. **Quản lý bệnh viện chưa có màn hình quản lý thành viên.** Vòng "khoa yêu cầu →
   quản lý duyệt → đơn sang Miyano" đã khép kín trên cổng (§4), nhưng việc gán khoa
   và bật/tắt thành viên thì quản lý bệnh viện chưa tự làm được — Miyano vẫn làm hộ
   trên Desk.
3. **Chưa có uỷ quyền tạm thời.** Quản lý đi vắng thì chưa có ai duyệt thay —
   thuộc kế hoạch C.
3b. **Vòng "duyệt sửa" chưa ghi mốc riêng.** Khi quản lý duyệt một yêu cầu sửa số
   lượng, phiếu không ghi thêm người duyệt và thời điểm cho vòng đó — khối truy vết
   vẫn chỉ mang dấu của lần duyệt đầu.
4. **Quản lý bệnh viện chưa tự cấp tài khoản được** — và sẽ không bao giờ được.
   Tạo tài khoản là tạo tài khoản trên hệ thống Miyano. Quản lý sẽ chỉ được gán
   khoa và bật/tắt thành viên (bước 9).
5. **Con số thông báo chưa đọc chưa lọc theo khoa.** Nội dung thông báo thì đã lọc
   — chỉ riêng con số trên huy hiệu là đếm chung.
6. **Không tách đơn theo tình trạng giá.** Đơn trộn hàng có giá và hàng chưa có giá
   đi **một** vòng báo giá, cả đơn cùng chờ (§4). Khoa muốn phần có giá đi trước thì
   tự đặt thành hai yêu cầu.
7. **Quản lý không chọn được khoa khi đặt hàng thẳng.** Đơn họ bấm đặt luôn là đơn
   toàn viện; muốn đơn thuộc về một khoa thì để nhân viên khoa lập yêu cầu rồi duyệt.

---

## Phụ lục — Bảng trường

**`Portal Member`** (`TVC-.#####`)

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `user` | Link User | **duy nhất** — một tài khoản thuộc đúng một bệnh viện |
| `customer` | Link Customer | bắt buộc |
| `vai_tro` | Chọn | `Quản lý` / `Nhân viên khoa` |
| `khoa_phong` | Link Customer Department | bắt buộc khi Nhân viên khoa đang hoạt động; **phải trống** với Quản lý |
| `active` | Tích | tắt thay vì xoá |

**`Customer Department`** (`KP-.#####`)

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `customer` | Link Customer | **bắt buộc** (trước đây khoá theo kho) |
| `kho` | Link Customer Warehouse | tuỳ chọn |
| `ten_khoa_phong` | Data | bắt buộc, không trùng trong một bệnh viện (so không dấu) |
| `ma_khoa` | Data | chữ hoa `A–Z0–9`, không trùng trong một bệnh viện, `CHUNG` là mã dành riêng |
| `active` | Tích | |

**`Customer`** — thêm một trường

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `custom_ma_ngan` | Data(10) | **duy nhất toàn hệ thống**. Bắt buộc trước khi cấp Nhân viên khoa |

**`Sales Order`** — thêm một trường

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `custom_khoa_phong` | Link Customer Department | **chỉ đọc**, hệ thống ghi lúc tạo đơn từ khoa phòng của người đặt. Đơn cũ để trống |
| `custom_de_xuat` | Link Portal De Xuat Mua | **chỉ đọc**, trỏ ngược về phiếu đề xuất sinh ra đơn. 102 đơn cũ để trống |
| `custom_ma_tra_cuu` | Data | mã dễ đọc của khách (`BM-HUYETHOC-260819-01`). Đơn sinh ra **từ một phiếu được duyệt** lấy luôn mã này làm tên đơn. Đơn quản lý **đặt thẳng** giữ tên `SAL-ORD-*` và chỉ mang mã này bên cạnh |
