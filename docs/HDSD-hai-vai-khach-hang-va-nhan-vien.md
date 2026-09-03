# Hướng dẫn sử dụng — Cổng khách hàng & Desk nhân viên Miyano

App `miyano_portal` · Cập nhật **26/08/2026**

Tài liệu này mô tả **toàn bộ luồng nghiệp vụ và thao tác trên màn hình** cho hai
vai:

| Vai | Làm ở đâu | Phần |
|---|---|---|
| **Khách hàng** (bệnh viện, phòng xét nghiệm…) | Cổng khách hàng `/portal` | [A](#a--vai-khách-hàng) |
| **Nhân viên Miyano** (sales, kho, kế toán) | Desk ERPNext `/app` | [B](#b--vai-nhân-viên-miyano) |

Kèm theo: [C. Bảng tra trạng thái](#c--bảng-tra-trạng-thái) ·
[D. Sự cố thường gặp](#d--sự-cố-thường-gặp) ·
[E. Hệ thống cố ý KHÔNG làm](#e--hệ-thống-cố-ý-không-làm)

**Địa chỉ môi trường thử nghiệm**

- Cổng khách hàng: <http://192.168.61.129:8003/portal>
- Desk nhân viên: <http://192.168.61.129:8003/app>

> Tài liệu bổ trợ: `HDSD-tao-khach-hang-mo-kho-va-thao-tac-cong.md` — cách **tạo
> khách hàng, cấp tài khoản cổng và mở kho**. Tài liệu bạn đang đọc giả định các
> việc đó đã xong.

---

## Bản đồ toàn cảnh — một đơn hàng đi qua đâu

```
KHÁCH                                        MIYANO (Desk)
─────                                        ─────────────
Đặt hàng ─────────────────────────────────►  Đơn về "Chờ xác nhận"
   │                                              │
   │  (đơn có dòng chưa có giá)                   ├─ điền đơn giá
   │                                              ├─ khớp mã hàng khách gõ tay
   │  ◄──────── báo giá ──────────────────────────┘  bấm "Gửi khách duyệt"
   │
   ├─ Đồng ý ─────────────────────────────►  "Chờ Miyano xác nhận" → Xác nhận
   ├─ Sửa số lượng → xin báo giá lại ─────►  quay lại "Chờ xác nhận"
   └─ Huỷ đơn ────────────────────────────►  "Khách huỷ" (mở lại được)
                                                  │
                                                  ├─ Lập phiếu giao (Delivery Note)
   ◄────────── hàng tới ──────────────────────────┤
   │                                              └─ Lập hoá đơn (Sales Invoice)
   ├─ Kiểm hàng: nhận đủ / thiếu / hỏng
   │      │
   │      ├─ có hàng hỏng ──────────────►  Duyệt trả hàng → phiếu trả (nháp)
   │      │                                       └─ Kho ghi sổ = NHẬP KHO
   │      │   ◄──── "Đã thu hồi" ─────────────────┘
   │      │
   │      └─ có hàng thiếu ─────────────►  Hẹn lịch giao (giao bù / đổi ngày)
   │          ◄──── lời hẹn hiện trên trang đơn ──┘
   │
   └─ Xem hoá đơn của đơn · thanh toán
```

---

# A — VAI KHÁCH HÀNG

## A0. Đăng nhập và bố cục màn hình

Vào `/portal` → nhập email + mật khẩu đã được Miyano cấp.

Menu bên trái (trên điện thoại nằm ở thanh dưới):

| Mục | Dùng để |
|---|---|
| 🏠 **Tổng quan** | Nhìn nhanh tình hình: đơn, công nợ, hợp đồng |
| 🛒 **Đặt hàng** | Chọn hàng, bỏ vào giỏ và gửi đi |
| 📋 **Danh sách đơn hàng** | Theo dõi từ lúc soạn tới lúc nhận hàng, xem chi tiết, duyệt, kiểm hàng |
| 🏭 **Kho của tôi** | Quản lý kho nội bộ *(chỉ khách đã mở kho)* |
| 🧾 **Hoá đơn & công nợ** | Hoá đơn, hạn thanh toán, hoá đơn điện tử |
| 🔔 **Thông báo** | Việc mới, có số đỏ khi chưa đọc |
| 🏥 **Hồ sơ đơn vị** | Thông tin đơn vị, địa chỉ, hợp đồng |

**Bảy mục** cho mọi vai trò.

> **Nếu bạn quen bản cũ:** bốn mục *Giỏ hàng*, *Đơn hàng của tôi*, *Đề xuất mua*
> và *Duyệt* không còn nữa. Giỏ hàng nay là bước 2 ngay trong màn **Đặt hàng**;
> ba mục còn lại gộp thành **Danh sách đơn hàng** (tên cũ: *Yêu cầu của tôi*).
> Link cũ trong thông báo và trong trình duyệt vẫn bấm được — chúng tự chuyển
> sang màn mới.

> **Quản lý duyệt ở đâu?** Mở **Danh sách đơn hàng**, bấm chip **Chờ duyệt** —
> đó là toàn bộ hàng chờ của bạn (gồm cả đơn xin sửa số lượng), lọc thêm được
> theo **khoa phòng**. Trên mục menu này còn một **số đỏ** đếm số đơn đang chờ
> bạn. Bấm vào một đơn để xem chi tiết và **duyệt ngay tại đó**.

> **Phân trang**: mọi danh sách đều có ô chọn **10 / 20 / 50** dòng mỗi trang ở
> cuối bảng. Lựa chọn của bạn được nhớ lại cho lần sau.

---

## A1. Tổng quan

Bốn ô số ở đầu trang:

- **Đơn chờ xác nhận** — Miyano chưa chốt
- **Đơn đang giao**
- **Hoá đơn chưa thanh toán**
- **Tổng công nợ**

Bên dưới: **5 đơn gần nhất** (bấm vào dòng để mở chi tiết) và **hợp đồng khung còn
hiệu lực** kèm % hạn mức đã dùng. Bấm *"Đặt hàng →"* để sang thẳng màn Đặt hàng.

---

## A2. Đặt hàng — bước 1: chọn hàng

**Một màn, một ô tìm kiếm, một danh sách.** Không còn chọn "chế độ" nào trước khi
tìm hàng: bạn gõ tên hoặc mã mặt hàng, hệ thống tìm trong toàn bộ danh mục của
Miyano và tự nói cho bạn biết từng dòng có giá hợp đồng hay chưa.

Danh sách hiện **10 mặt hàng mỗi trang**. **Hàng thuộc hợp đồng của đơn vị bạn
đứng trước**, hết rồi mới tới các mặt hàng khác.

Mỗi dòng cho bạn bốn thông tin:

| Cột | Nghĩa |
|---|---|
| **Tình trạng** | **Còn hàng** — Miyano đang có sẵn. **Liên hệ** — hết hoặc chưa nhập, gọi nhân viên kinh doanh để biết ngày về |
| **Tầng giá** | **Giá HĐ** kèm số tiền và mã hợp đồng — đây là hàng trong hợp đồng đã ký. **Chờ báo giá** — Miyano sẽ báo giá sau |
| **Hạn mức** | Còn lại bao nhiêu trên hợp đồng, hoặc *Không giới hạn* |
| **Số lượng** | Gõ số rồi bấm **+ Giỏ** |

Hai điều màn hình sẽ nhắc ngay tại dòng:

- **Vượt hạn mức hợp đồng là cảnh báo, không phải hàng rào.** Nhân viên khoa vẫn
  xin được 100 hộp khi hợp đồng còn 40 — người duyệt của đơn vị sẽ quyết số thật.
  Nhưng **đến lúc đơn thật sự sinh ra** (quản lý bấm Đặt hàng, hoặc quản lý duyệt)
  thì hạn mức chặn cứng, kèm câu báo còn lại bao nhiêu.
- Một số mặt hàng có **bội số đặt hàng** (ví dụ chỉ đặt theo bội của 10). Gõ sai
  bội số thì màn hình báo ngay và gợi ý số hợp lệ gần nhất.

### Hàng Miyano chưa có trong hệ thống

Bấm nút **“+ Thêm dòng — hàng chưa có trong hệ thống”** ngay dưới ô tìm kiếm. Nút
này **luôn hiện**, không phải tìm không ra mới có. Tự gõ:

| Ô | Ví dụ |
|---|---|
| Tên hàng | Kẹp mạch máu cỡ S |
| Đơn vị tính | Cái |
| Số lượng | 20 |
| Ghi chú | hãng nào cũng được, cần trước 25/08 |

Miyano có trách nhiệm tìm nguồn và báo lại. **Bạn không cần biết Miyano đang có
gì trong kho.**

---

## A3. Đặt hàng — bước 2: giỏ hàng và gửi đi

Bấm **2 · Giỏ hàng** ở đầu màn. **Một giỏ duy nhất**, mọi mặt hàng nằm chung một
bảng, mỗi dòng mang nhãn giá của nó (*Giá HĐ …* hoặc *Chờ báo giá*). Sửa số lượng
ngay trong bảng, **Xoá** dòng không cần nữa.

Trước khi gửi cần điền:

- **Lý do yêu cầu** — bắt buộc, người duyệt của đơn vị sẽ đọc dòng này
- **Ngày giao mong muốn** — hệ thống chặn ngày quá gần / quá khứ
- **Địa chỉ giao hàng** (chọn từ danh sách địa chỉ của đơn vị)
- **Ghi chú** (không bắt buộc) — ví dụ *hàng cần giữ lạnh 2–8 °C*

Rồi bấm nút cuối màn. **Nút đó ghi gì là tuỳ vai của bạn:**

| Bạn là | Nút | Chuyện gì xảy ra |
|---|---|---|
| **Nhân viên khoa** | **Gửi duyệt** | Yêu cầu được cấp mã và chuyển tới quản lý đơn vị. Duyệt xong đơn mới sang Miyano |
| **Quản lý đơn vị** | **Đặt hàng** | Đơn sang Miyano ngay trong một lần bấm — bạn vốn là người duyệt. Hệ thống vẫn tự lưu lại một yêu cầu đã duyệt đứng sau để sau này còn tra được |

Nút **Lưu nháp** để soạn dở rồi quay lại sau. Bản nháp nằm ở **Danh sách đơn hàng**,
giai đoạn *Nháp*.

> Bấm nút gửi hai lần (mạng chậm, lỡ tay) **không** tạo hai đơn — hệ thống nhận
> ra và trả về đúng đơn đã tạo.

### ⚠️ Đơn có hàng chờ báo giá thì CẢ ĐƠN chờ

Đây là điều hay được hỏi nhất, nên nói thẳng.

Nếu trong giỏ có **bất kỳ** mặt hàng nào mang nhãn *Chờ báo giá*, màn hình sẽ báo:

> Đơn có hàng chờ báo giá — cả đơn sẽ chờ Miyano báo giá trước khi giao.

Nghĩa là **hàng trong hợp đồng của bạn cũng nằm chờ**, dù giá của nó đã có sẵn.
Trước đây phần hàng hợp đồng giao được ngay; nay nếu nó đứng chung đơn với hàng
chưa có giá thì nó chờ cùng.

**Vì sao:** một đơn hàng là **một** chứng từ, có **một** ngày giao và **một** hoá
đơn. Miyano báo giá cho cả đơn, bạn đồng ý cho cả đơn, rồi hàng đi một lượt.

**Cần hàng hợp đồng gấp thì làm gì:** **đặt thành hai lần**. Một yêu cầu chỉ gồm
các mặt hàng có *Giá HĐ* — nó đi thẳng, không phải chờ báo giá. Một yêu cầu riêng
cho phần *Chờ báo giá*. Hệ thống không tự tách hộ, vì tách đơn của bạn là việc chỉ
đơn vị bạn mới quyết được.

---

## A4. Xem báo giá và trả lời

Áp dụng cho **mọi đơn có dòng chưa có giá lúc đặt** — kể cả đơn trộn cả hàng hợp
đồng lẫn hàng chờ báo giá.

Khi Miyano báo giá xong, bạn nhận **thông báo trên cổng** (chuông 🔔) và đơn
chuyển sang trạng thái **"Chờ bạn đồng ý"**. Ở màn **Danh sách đơn hàng** nó nằm ở
chip **Chờ quý vị đồng ý** — nghĩa là *giá đã về, đang chờ bạn trả lời*. Mở đơn, đầu
trang có khối màu cam:

> ⏳ **Báo giá hiệu lực đến 23/08/2026.**

Bảng hàng lúc này **đã có đơn giá và thành tiền**. Ba lựa chọn:

| Nút | Kết quả |
|---|---|
| **Đồng ý đặt hàng** | Đơn chuyển sang Miyano xác nhận rồi đưa vào giao hàng |
| **Sửa số lượng…** | Bạn nhập số lượng mới từng dòng → **Gửi lại để báo giá**. Miyano báo giá lại từ đầu |
| **Huỷ đơn…** | **Huỷ thật**, cần nêu lý do. Đơn đóng lại; email báo hai bên nếu site đã cấu hình tài khoản gửi thư |

Bốn điều cần biết:
- **Nhân viên khoa đổi số lượng thì phải qua quản lý một lần nữa.** Nút của họ ghi
  **Xin sửa số lượng**: yêu cầu quay về *Chờ duyệt*, quản lý duyệt rồi đơn mới đổi.
  Còn **đồng ý** với báo giá thì nhân viên khoa tự làm xong, không cần duyệt lại.
- **"Gửi lại để báo giá" xoá sạch đơn giá cũ** — đơn quay về chờ Miyano báo lại.
  Vì vậy nút này có bước xác nhận, không bấm nhầm được.
- Quá **hạn hiệu lực** mà chưa trả lời → đơn tự chuyển "Báo giá hết hạn". Muốn
  mua tiếp thì báo nhân viên kinh doanh mở lại.
- Tải **PDF báo giá** bằng nút ⬇ trong khối báo giá. Bản PDF **lấy trên cổng**,
  không đính kèm trong email — xem ghi chú về email ở [D](#d--sự-cố-thường-gặp).

---

## A5. Theo dõi — "Danh sách đơn hàng"

**Một danh sách cho cả vòng đời.** Từ lúc bạn còn đang soạn tới lúc hàng về, yêu
cầu của bạn nằm **đúng một dòng ở đúng một chỗ** — nó không nhảy sang màn khác khi
quản lý duyệt.

Lọc bằng dải chip ở đầu danh sách:

| Chip | Nghĩa | Ai đang giữ việc |
|---|---|---|
| **Nháp** | Bạn đang soạn, chưa gửi. Bấm vào để mở lại màn Đặt hàng và sửa tiếp | Bạn |
| **Chờ duyệt** | Đã gửi, quản lý đơn vị chưa duyệt | Quản lý đơn vị |
| **Đã duyệt** | Đơn đã sang Miyano và đang chạy — kể cả khi Miyano còn đang gom giá, hoặc đã giao được một phần | Miyano |
| **Chờ quý vị đồng ý** | **Miyano đã báo giá xong, đang chờ bạn trả lời** (hoặc báo giá đã quá hạn) | Bạn |
| **Đã giao** | Đã giao đủ, hoặc đơn đã đóng | — |
| **Từ chối** · **Đã huỷ** | Yêu cầu dừng lại, vẫn giữ để tra sau | — |

> **Đọc kỹ hai chip giữa.** Đơn **đang chờ Miyano ra giá** nằm ở *Đã duyệt* —
> cùng chỗ với đơn đã có giá và đang chạy. *Chờ quý vị đồng ý* là bước SAU đó:
> **báo giá đã về, và việc đang nằm ở phía bạn.** Đơn mới giao được một phần
> cũng nằm ở *Đã duyệt*, thanh tiến độ trên dòng cho biết đã giao bao nhiêu
> phần trăm.
>
> *(Chip này trước đây tên "Chờ báo giá" — cái tên đó đọc như đang chờ Miyano,
> đúng ngược chiều việc. Link cũ có kèm tên cũ vẫn mở đúng chip.)*

Phân trang 10/20/50 như mọi danh sách khác. Bấm vào một dòng để mở **chi tiết**.

Từ 03/09/2026, chi tiết là **một** trang cho cả yêu cầu lẫn đơn hàng sinh ra từ
nó — bấm vào là thấy **tất cả**: ai xin, ai duyệt, giá, tiến trình giao hàng, hoá
đơn. Không còn cảnh xem xong phần "ai xin" phải bấm thêm một link nữa mới sang
được phần "đơn tới đâu rồi".

Trang chi tiết đơn gồm:

**Tiến trình 5 mốc** — Đặt hàng → Xác nhận → Soạn hàng → Giao hàng → Hoá đơn.
Mốc đã qua tô xanh.

**Khối "Yêu cầu & duyệt"** — ai xin, xin lúc nào, vì sao xin; ai duyệt, duyệt lúc
nào, duyệt nguyên số hay đã sửa số lượng. Khối này **tự thu gọn** khi đơn đã giao
xong — đơn cũ thì không cần giương mắt đọc lại ai đã duyệt mỗi lần mở ra, bấm vào
nhãn của khối là mở lại xem đầy đủ.

**Bảng hàng hoá** — mã, tên, ĐVT, SL đặt, đã giao, đơn giá, thành tiền.

**Khối "Đang chờ Miyano xác nhận nguồn"** — các dòng bạn tự gõ tay mà Miyano
chưa tìm được mã hàng tương ứng.

**Khối Giao hàng** — mỗi đợt giao là một mục:

- Số phiếu giao, ngày, % của đơn, hãng vận chuyển, số vận đơn
- Nút **Phiếu giao đợt n** — xem mục A5b ngay dưới
- **Kiểm hàng đợt này** (hoặc badge trạng thái nếu đã kiểm) — xem A6
- *Phiếu nhập kho* — chỉ hiện nếu đơn vị bạn đã mở kho
- *Hoá đơn nháp* — bấm ▸ để xem nội dung hoá đơn điện tử trước khi phát hành

**Khối "Miyano đã hẹn lại"** *(nếu có)* — hiện khi Miyano báo chưa đủ hàng:

> 🟠 **Sẽ giao bù** — Dự kiến giao 21/08/2026
> *Giao bù 1 hộp thay thế hàng hỏng, hàng về kho ngày 21/08*

Khối này **tự biến mất** khi Miyano đã giao đợt tiếp theo.

**Khối "Hoá đơn của đơn này"** — danh sách hoá đơn phát sinh từ chính đơn này,
kèm số tiền, còn nợ, hạn thanh toán và nút ⬇ PDF.

Cuối trang: ⬇ **PDF đơn hàng** · 🔁 **Đặt lại đơn này**.

**Đặt lại đơn này** dựng sẵn một yêu cầu **Nháp** mang đúng các mặt hàng của đơn
cũ rồi mở màn **Đặt hàng** cho bạn sửa tiếp. Mặt hàng nào không còn đặt lại được
(ngừng kinh doanh, hết hạn mức…) sẽ được nêu tên kèm lý do, không bị bỏ đi lặng lẽ.

---

## A5b. Phiếu giao hàng — tờ giấy hai bên ký

Nút **Phiếu giao đợt n** phát đúng tờ **Phiếu xuất kho kiêm biên bản bàn giao**
(mẫu 02-VT theo Thông tư 99/2025/TT-BTC) — **cùng một tờ mà lái xe đưa bạn ký lúc
nhận hàng**, cùng bố cục, có cột Số lô và Hạn dùng, có ô ký của cả hai bên.

Trước bản này nút đó phát một tờ khác — bản giao hàng thương mại. Hai tờ giấy nói
về cùng một lần giao mà khác hình thức là thứ không giải thích được lúc đối soát
công nợ hay lúc thanh tra hỏi.

Hai điều cần biết:

- **Có bản đã ký thì bạn nhận đúng bản đã ký.** Khi Miyano quét tờ hai bên đã ký
  và đính vào phiếu giao, nút này phát thẳng bản quét đó thay cho bản in lại. Nếu
  vì lý do kỹ thuật cổng không phát được bản quét, bạn vẫn nhận được bản in nhưng
  **trên đầu tờ có dòng chữ đỏ báo đây là bản in lại chưa có chữ ký** kèm số điện
  thoại của Miyano — không bao giờ có chuyện đưa bạn tờ chưa ký mà không nói gì.
- **Phiếu mở ngay trong trình duyệt**, không tải về máy. Muốn giữ lại thì lưu hoặc
  in từ chính trang đang mở. Riêng bản quét ở định dạng ảnh TIF thì trình duyệt
  không dựng được, nên nó tải về như một tệp.

---

## A6. Kiểm hàng khi nhận — nhận một phần, trả lại phần hỏng

**Áp dụng cho mọi đơn** và **mọi khách hàng**, kể cả đơn vị chưa mở kho.

Vào chi tiết đơn → khối Giao hàng → **Kiểm hàng đợt này**.

Màn hình hiện bảng đối chiếu, **mặc định là "nhận đủ"** — nếu hàng về đủ và tốt,
bạn chỉ cần bấm Gửi.

| Cột | Ý nghĩa |
|---|---|
| **SL giao** | Số Miyano ghi trên phiếu giao (không sửa được) |
| **Nhận tốt** | Số bạn nhận và dùng được |
| **Hỏng, trả lại** | Số hàng hỏng, bạn muốn Miyano thu hồi |
| **Thiếu** | Tự tính = SL giao − Nhận tốt − Hỏng. Là phần **không tới nơi** |
| **Lý do** | Bắt buộc khi có chênh lệch |

**Ví dụ:** giao 10 hộp, 6 hộp tốt, 3 hộp vỡ, 1 hộp không thấy đâu
→ Nhận tốt `6`, Hỏng trả lại `3`, cột Thiếu tự hiện `1`, lý do *"3 hộp vỡ khi
vận chuyển, thiếu 1 hộp"*.

Hai nút:

- **Lưu nháp** — kiểm dở, đóng máy, mở lại vẫn còn
- **Gửi biên bản** — có hộp xác nhận trước khi gửi. **Gửi xong không sửa được nữa**

Lỗi hiện **ngay tại dòng sai**, màu đỏ, và nút Gửi mờ đi cho tới khi sửa xong.

### Sau khi gửi

| Trạng thái | Nghĩa là |
|---|---|
| **Đã xác nhận** | Bạn nhận đủ — đóng luôn, không làm phiền ai |
| **Chờ xử lý** | Có hỏng và/hoặc thiếu, Miyano đang xem |
| **Đã duyệt trả** | Miyano đồng ý thu hồi, bộ phận giao nhận sẽ liên hệ |
| **Đã thu hồi** | Hàng hỏng đã về kho Miyano |
| **Từ chối** | Miyano không chấp nhận — **lý do hiện ngay đầu màn hình** |
| **Đã xử lý** | Miyano đã xử lý xong phần thiếu |

**Bị từ chối thì làm gì?** Màn hình hiện nút **"Kiểm lại và gửi biên bản mới"**.
Bấm vào, bảng trở về trắng để bạn đếm lại và gửi lần nữa. Biên bản cũ được giữ
nguyên làm lịch sử trao đổi.

**Phần hàng thiếu** được trả lời riêng, hiện thành khối *"Hàng thiếu — Miyano đã
trả lời"* kèm hình thức (Sẽ giao bù / Đã đổi ngày giao) và ngày hẹn.

---

## A7. Kho của tôi *(chỉ đơn vị đã mở kho)*

Tám mục con:

| Mục | Dùng để |
|---|---|
| **Phiếu nhập** | Nhận hàng vào kho. Phiếu từ đơn Miyano **tự sinh sẵn ở dạng nháp**, bạn chỉ đối chiếu rồi ghi sổ |
| **Phiếu xuất** | Cấp phát cho khoa phòng |
| **Danh mục vật tư** | Vật tư nội bộ của đơn vị, có nhập từ Excel |
| **Nhập tồn đầu kỳ** | Nạp tồn ban đầu bằng Excel |
| **Báo cáo** | Nhập – Xuất – Tồn theo khoảng thời gian |
| **Nhật ký vật tư** | Thẻ kho từng mặt hàng |
| **NCC của tôi** | Nhà cung cấp khác ngoài Miyano |
| **Khoa phòng** | Danh mục đơn vị nhận hàng nội bộ |

Ràng buộc khi ghi sổ phiếu nhập từ đơn Miyano:
- **Thực nhận không được vượt SL giao.** Nhận thừa thật thì lập phiếu "Nhập khác"
  riêng.
- Lệch so với SL giao → **bắt buộc nhập lý do**, và nhân viên Miyano nhận cảnh báo.
- Lô đã hết hạn → chặn xuất, trừ khi tick xác nhận.

> **Phiếu nhập kho** và **Biên bản kiểm hàng** (A6) là **hai việc khác nhau**:
> phiếu nhập ghi sổ tồn kho *nội bộ của bạn*; biên bản kiểm hàng là *cuộc trao
> đổi với Miyano* về đợt giao. Hai chứng từ không tự đồng bộ số liệu cho nhau.

---

## A8. Hoá đơn & công nợ

Danh sách hoá đơn kèm: ngày, số tiền, còn nợ, hạn thanh toán, trạng thái.

Đầu trang có hai cảnh báo tính trên **toàn bộ** hoá đơn còn nợ (không chỉ trang
đang xem): **tổng quá hạn thanh toán** và **số hoá đơn sắp đến hạn (0–7 ngày)**.

Nút ⬇ **Bản in** để tải hoá đơn.

Với hoá đơn điện tử: tải được **bản thể hiện PDF** của hoá đơn đã phát hành, và
**bản in thử PDF** khi chứng từ còn ở dạng nháp (xem trong khối Giao hàng của
chi tiết đơn). Hệ thống **không phát hành file XML** — module hoá đơn điện tử
đang dùng không lưu XML, nên không có gì để giao.

---

## A9. Thông báo

Chuông 🔔 có số đỏ = số thông báo chưa đọc. Mỗi dòng có **nút đi thẳng tới chứng
từ liên quan**.

Các loại thông báo bạn sẽ nhận:

| Thông báo | Bấm vào đi tới |
|---|---|
| Báo giá đã sẵn sàng | Chi tiết đơn |
| Đơn được xác nhận / bị từ chối | Chi tiết đơn |
| Miyano vừa giao hàng | Chi tiết đơn (hoặc phiếu nhập kho) |
| Kiểm hàng: đã duyệt trả / đã thu hồi / từ chối | Màn kiểm hàng của đợt giao đó |
| Hẹn lịch giao mới | Chi tiết đơn |

---

## A10. Hồ sơ đơn vị

Thông tin đơn vị, mã số thuế, địa chỉ giao hàng, người liên hệ và danh sách hợp
đồng khung. Cần sửa thông tin → liên hệ nhân viên kinh doanh Miyano.

---

# B — VAI NHÂN VIÊN MIYANO

Làm trên **Desk ERPNext** (`/app`). Vai trò cần: `Sales User`, `Sales Manager`
hoặc `System Manager` tuỳ thao tác.

## B1. Nhận đơn từ cổng

Đơn khách gửi lên là một **Sales Order** ở trạng thái **"Chờ xác nhận"**.

Vào **Sales Order** → lọc `Trạng thái workflow = Chờ xác nhận`. Phân biệt hai loại
bằng cột **Loại đơn**:

| Loại đơn | Nghĩa | Việc phải làm |
|---|---|---|
| **Theo HĐNT** | Mọi dòng đều có giá hợp đồng | Kiểm rồi xác nhận |
| **Mua lẻ** | **Đơn có ít nhất một dòng chưa có giá** | Báo giá trước (B2) |

> **Chữ "Mua lẻ" ở cột này KHÔNG còn nghĩa "đơn ngoài hợp đồng".** Khách nay đặt
> hàng hợp đồng và hàng chưa có giá **chung một đơn**, nên một đơn ghi "Mua lẻ" có
> thể chứa cả hai loại dòng: vài dòng đã có giá hợp đồng sẵn, vài dòng để trống chờ
> bạn điền. Dấu này được đóng **một lần lúc lập đơn** và **không đổi** sau khi bạn
> điền xong giá — đơn vẫn ghi "Mua lẻ" cho tới hết vòng báo giá, đó là chủ ý để
> cả thông báo tự động lẫn báo cáo cùng nhìn thấy một sự thật.
>
> **Hệ quả với khách:** cả đơn nằm chờ, kể cả phần hàng hợp đồng vốn giao được
> ngay. Nếu bệnh viện gọi hỏi, câu trả lời đúng là: đơn này có dòng chưa có giá
> nên đi trọn một vòng báo giá; lần sau cần hàng hợp đồng gấp thì đặt riêng một
> đơn chỉ gồm hàng hợp đồng.

Báo cáo hỗ trợ: **Đơn chậm xử lý** (quá SLA) và **Demand pipeline yêu cầu hàng
hoá**.

> **Chỗ mở đầu ngày làm việc**: workspace **"Kho khách hàng"** (menu Desk → tìm
> theo tên) gom sẵn mọi việc do khách đẩy sang. Mục *Việc từ cổng khách hàng*
> có hai nút kèm **con số việc đang chờ**: **Biên bản kiểm hàng** và **Yêu cầu
> hàng hoá**, cạnh đó là hai báo cáo *Đối soát giao nhận* và *Đơn chậm xử lý*.

---

## B2. Báo giá một đơn có dòng chưa có giá

> Đây là câu trả lời cho *"báo giá cho khách hàng khi khách mua vật tư không có
> trong hợp đồng"*.

Mở đơn, làm hai việc rồi bấm một nút:

**1. Xử lý bảng "Dòng đặt ngoài (chưa có trong danh mục)"** — đây là những mặt
hàng khách **tự gõ tay** vì hệ thống chưa có mã:

- Tìm được mã hàng tương ứng → điền vào cột **Mã hàng khớp** rồi **Lưu**. Hệ thống
  **tự dựng một dòng hàng thật** cho nó ngay trong bảng `Items`. Nếu mã đó nằm
  trong hợp đồng còn hiệu lực của khách thì dòng mang luôn giá hợp đồng; **nếu
  không thì đơn giá về `0` và bạn phải điền lại** — để nguyên `0` sẽ ăn chốt
  *"Thiếu giá"* lúc gửi khách duyệt. Dòng giữ chỗ `HANG-DAT-NGOAI` (nếu có) được
  gỡ luôn trong cùng lần lưu đó.
  *Trước đây bạn phải tự thêm dòng — nay đừng thêm tay nữa, sẽ thành hai dòng.*
- Không đáp ứng được → vẫn phải đánh dấu đã xử lý, và nên ghi chú lý do.

**2. Điền đơn giá** cho những dòng đang là `0` trong bảng `Items`.

**3. Bấm nút workflow "Gửi khách duyệt"** (góc trên bên phải).

Đơn chuyển sang **"Chờ khách đồng ý"**, khách nhận **thông báo trên cổng** và tự
tải được **PDF báo giá** ở đó. PDF **cố ý không đính kèm email** — xem [D](#d--sự-cố-thường-gặp).

Ba chốt chặn sẽ báo lỗi nếu bỏ sót:

| Lỗi báo ra | Nghĩa |
|---|---|
| Còn dòng đặt ngoài chưa xử lý | Chưa khớp mã hoặc chưa đánh dấu |
| Còn dòng `HANG-DAT-NGOAI` | Dòng giữ chỗ còn sót lại trong bảng hàng — gỡ đi |
| Thiếu giá | Có dòng đơn giá = 0 |

> Đơn trộn thì **những dòng đã có giá hợp đồng giữ nguyên giá đó**, bạn chỉ điền
> phần còn trống. Đừng sửa giá dòng hợp đồng — khách đã nhìn thấy giá ấy lúc đặt.

### Khách trả lời thế nào

| Khách bấm | Đơn chuyển sang | Bạn làm gì |
|---|---|---|
| Đồng ý | **Chờ Miyano xác nhận** | Bấm **Xác nhận** |
| Sửa số lượng → gửi lại | **Chờ xác nhận** | Báo giá lại (giá cũ đã bị xoá) |
| Huỷ đơn | **Khách huỷ** | Bấm **Mở lại** nếu khách đổi ý |
| Không trả lời quá hạn | **Báo giá hết hạn** | Bấm **Mở lại** |

---

## B3. Xác nhận đơn và giao hàng

**Xác nhận**: mở đơn ở "Chờ Miyano xác nhận" → nút **Xác nhận**. Đơn được Submit,
khách thấy mốc "Xác nhận" sáng lên.

**Giao hàng**: từ đơn đã xác nhận → *Create → Delivery Note*. Điền kho xuất, lô
(nếu vật tư quản lý theo lô), hãng vận chuyển, số vận đơn → **Submit**.

Ngay khi Submit:
- Khách thấy đợt giao mới trên chi tiết đơn, có nút mở phiếu giao và nút **Kiểm
  hàng đợt này**
- Nếu khách **đã mở kho**: hệ thống tự sinh **Phiếu nhập kho nháp** trong kho của
  khách và gửi thông báo

**In phiếu giao cho lái xe mang đi ký**: mẫu mặc định của phiếu giao là **Phiếu
xuất kho kiêm biên bản bàn giao** (mẫu 02-VT theo Thông tư 99/2025/TT-BTC) — tờ có
ô ký của cả hai bên. Đây cũng chính là tờ khách tải về trên cổng, nên hai bên luôn
cầm cùng một hình thức giấy.

**Ký xong thì scan và đính lại vào phiếu giao**: ô **"Biên bản bàn giao đã ký (bản
scan)"** trên chính phiếu giao đó (đính được cả khi phiếu đã Submit). Từ lúc đính,
khách bấm nút phiếu giao trên cổng sẽ nhận **đúng bản có chữ ký** thay cho bản in
lại. Nhận PDF hoặc ảnh JPG/PNG chụp từ điện thoại đều được; **đừng đính ảnh HEIC**
— máy Windows của bệnh viện phần lớn không mở được, và cổng sẽ không phát nó.

**Hoá đơn**: từ đơn → *Create → Sales Invoice* → Submit. Nếu bật module hoá đơn
điện tử, chứng từ HĐĐT được lập tự động và khách xem được bản nháp trước khi phát
hành.

---

## B4. Xem biên bản kiểm hàng của khách

> Đây là câu trả lời cho *"tôi muốn thấy được phiếu kiểm hàng, lý do nhận 1 phần,
> lý do trả lại của khách hàng"*.

**Bốn đường vào:**

0. **Workspace "Kho khách hàng"** → mục *Việc từ cổng khách hàng* → shortcut
   **Biên bản kiểm hàng**, có **con số việc đang chờ xử lý** ngay trên nút. Đây
   là chỗ mở đầu ngày làm việc — ba đường dưới là để đi từ một chứng từ cụ thể.
1. Thông báo *"Portal - Kiểm hàng có vấn đề"* → bấm thẳng vào biên bản
2. Từ **Sales Order** hoặc **Delivery Note** → nút **Miyano → Biên bản kiểm hàng**
   *(nút này do app nạp vào Desk; không thấy nút → chạy `bench build --app
   miyano_portal` rồi tải lại trang, xem [D](#d--sự-cố-thường-gặp))*
3. Danh sách **Biên bản kiểm hàng** (`Portal Delivery Inspection`), lọc theo
   khách / trạng thái / "Có hàng hỏng cần trả"

Trên biên bản, bảng **Chi tiết kiểm nhận** hiện đầy đủ, không phải bung dòng:

| Cột | |
|---|---|
| Mã hàng · Tên hàng | |
| **SL giao** | Miyano ghi trên phiếu giao |
| **Nhận tốt** | Khách nhận được và dùng được |
| **Hỏng, trả lại** | Khách đề nghị thu hồi |
| **Lý do** | **Lý do khách nêu cho từng dòng** |

Phần chênh còn lại (SL giao − Nhận tốt − Hỏng) là **hàng thiếu**. Ghi chú chung
của khách nằm ở ô **Ghi chú của khách**.

Nút **Chứng từ** dẫn sang Phiếu giao / Đơn hàng / Phiếu trả hàng liên quan.

---

## B5. Xử lý HÀNG HỎNG — duyệt trả và nhập kho

Nhóm nút **Hàng hỏng** (chỉ hiện khi biên bản đang **Chờ xử lý**):

### Duyệt trả hàng

Bấm → xác nhận → hệ thống lập **phiếu giao ngược (Delivery Note, `is_return`) ở
dạng NHÁP**:

- Chỉ chứa các mặt hàng khách báo hỏng, số lượng **âm** đúng phần hỏng
- Số lượng được **phân bổ qua nhiều dòng** nếu mặt hàng đó xuất từ nhiều lô
- Kho nhận = **«Hàng trả về»** của đúng công ty trên phiếu giao gốc

Biên bản chuyển sang **Đã duyệt trả**, khách nhận thông báo.

### Ghi sổ phiếu trả hàng = NHẬP KHO

> **Không có chứng từ thứ hai.** Việc ghi sổ phiếu trả hàng *chính là* bước nhập
> kho.

1. Mở phiếu trả hàng nháp (nút **Chứng từ → Phiếu trả hàng**)
2. Kho kiểm hàng thực nhận, sửa số lượng / lô nếu lệch
3. Đổi kho nếu hàng thực ra vẫn dùng tốt — mặc định là «Hàng trả về»
4. **Submit**

Ngay khi Submit:
- Tồn kho **«Hàng trả về»** tăng lên
- Tồn kho **bán được không đổi** — hàng hỏng không lẫn vào hàng bán
- Biên bản tự chuyển **Đã thu hồi**, khách nhận thông báo

> **Vì sao có kho riêng:** trước đây phiếu trả hàng ghi thẳng về kho đang bán,
> tức bơm tiêm gãy kim quay lại đúng kho để bán cho bệnh viện tiếp theo. Với vật
> tư y tế đây không phải chi tiết kế toán.

### Từ chối

Bấm **Từ chối biên bản** → **bắt buộc nêu lý do** (khách đọc đúng dòng đó).

Sau khi từ chối, khách **được phép kiểm lại và gửi biên bản mới**. Biên bản bị từ
chối giữ nguyên làm lịch sử.

Không từ chối được nếu bạn **đã hứa lịch giao** cho phần thiếu trên biên bản đó —
hệ thống chặn để không để lại một cam kết mồ côi trên đơn hàng.

---

## B6. Xử lý HÀNG THIẾU — hẹn lịch giao

> Đây là câu trả lời cho *"khi chưa có hàng tôi muốn thông báo lại cho khách hàng
> về hàng thiếu và sẽ vận chuyển sau hoặc đổi ngày giao hàng"*.

Nhóm nút **Hàng thiếu** hiện khi biên bản có dòng thiếu và **chưa được trả lời**.
Nhóm này **độc lập với luồng trả hàng** — một biên bản vừa có hàng hỏng vừa thiếu
hàng thì xử lý được cả hai, theo thứ tự bất kỳ.

### Hẹn lịch giao

Bấm → điền ba ô:

| Ô | |
|---|---|
| **Hình thức** | *Sẽ giao bù* hoặc *Đã đổi ngày giao* |
| **Ngày hẹn giao** | Không nhận ngày quá khứ |
| **Lý do** | Tối thiểu 5 ký tự — **khách đọc đúng dòng này** |

Khác biệt giữa hai hình thức:

| | Ngày giao của đơn | Dùng khi |
|---|---|---|
| **Sẽ giao bù** | **Giữ nguyên** | Miyano lỡ hẹn, giao phần còn lại sau. Giữ ngày gốc là giữ đúng lịch sử |
| **Đã đổi ngày giao** | **Dời cả đơn lẫn từng dòng** | Hai bên thoả thuận lại lịch |

> Đổi ngày phải đổi **cả từng dòng**, không chỉ tiêu đề — mọi báo cáo giao hàng
> trễ của ERPNext đọc ngày ở dòng. Hệ thống làm việc này giúp bạn.

Kết quả: lời hẹn ghi lên **chính đơn hàng**, khách thấy khối cam trên trang đơn và
nhận thông báo. Khối này **tự tắt** khi bạn giao đợt tiếp theo.

### Đóng, không giao bù

Dùng khi phần thiếu được xử lý ngoài hệ thống (giảm trừ công nợ, khách bỏ qua…).
Ghi chú gửi khách không bắt buộc.

---

## B7. Hẹn lịch giao khi CHƯA giao hàng

Trường hợp Miyano biết trước là chưa gom đủ hàng, **không cần đợi khách kiểm hàng**.

Mở **Sales Order** đã xác nhận → nút **Miyano → Hẹn lịch giao mới** → điền đúng ba
ô như B6.

Cùng một cơ chế, cùng chỗ ghi, cùng thông báo. Khách chỉ có một câu hỏi — *"bao
giờ tôi nhận được hàng?"* — nên chỉ có một chỗ trả lời.

Hẹn lại nhiều lần được: **mỗi lần hẹn là một thông báo riêng** gửi cho khách.

---

## B8. Báo cáo

| Báo cáo | Trả lời câu hỏi |
|---|---|
| **Đơn chậm xử lý** | Đơn nào quá SLA chưa ai đụng tới |
| **Demand pipeline yêu cầu hàng hoá** | Khách đang cần gì mà Miyano chưa có |
| **Đối soát giao nhận** | Đợt giao nào khách ghi nhận lệch số |
| **Tồn kho khách hàng** | Khách còn bao nhiêu hàng |
| **Nhập-Xuất-Tồn khách hàng** | Biến động kho khách theo kỳ |
| **Tiêu thụ và đề xuất dự trù** | Khách nên đặt gì, bao nhiêu |
| **Cảnh báo hạn dùng khách hàng** | Lô nào sắp hết hạn ở kho khách |
| **Cấp phát theo khoa phòng** | Khoa nào dùng nhiều |
| **Tỷ trọng nguồn cung** | Bao nhiêu % khách mua từ Miyano |
| **Chất lượng dữ liệu kho khách** | Dòng thiếu lô/hạn cần bổ sung |

---

# C — Bảng tra trạng thái

## C1. Đơn hàng

Đây là trạng thái Miyano nhìn thấy trên Desk. Khách nhìn thấy **giai đoạn** gộp
hơn ở màn *Danh sách đơn hàng* — đối chiếu ở cột thứ tư.

| Trạng thái (Desk) | Ai đang giữ việc | Bước tiếp | Khách thấy |
|---|---|---|---|
| Chờ xác nhận | Miyano | Báo giá (nếu đơn có dòng chưa có giá) hoặc gửi duyệt | Đã duyệt |
| Chờ khách đồng ý | **Khách** | Khách đồng ý / sửa SL / huỷ | **Chờ quý vị đồng ý** |
| Chờ Miyano xác nhận | Miyano | Bấm Xác nhận | Đã duyệt |
| Đã xác nhận | Miyano | Lập phiếu giao | Đã duyệt, rồi **Đã giao** khi giao đủ |
| Từ chối | — | Đơn đóng | Từ chối |
| Khách huỷ | — | Mở lại được | Đã huỷ |
| Báo giá hết hạn | — | Mở lại được | **Chờ quý vị đồng ý** |

## C2. Biên bản kiểm hàng

| `Trạng thái` (luồng trả hàng) | | `Xử lý hàng thiếu` (độc lập) | |
|---|---|---|---|
| Chờ xử lý | Miyano đang xem | *(trống)* | Chưa trả lời khách |
| Đã xác nhận | Khách nhận đủ, đóng | Sẽ giao bù | Giữ ngày gốc, hẹn giao phần còn lại |
| Đã duyệt trả | Đã lập phiếu trả nháp | Đã đổi ngày giao | Dời hẳn ngày giao của đơn |
| Đã thu hồi | Phiếu trả đã ghi sổ | Không giao bù | Đóng, xử lý ngoài hệ thống |
| Từ chối | Khách gửi lại được | | |
| Đã xử lý | Chỉ thiếu hàng, đã đóng | | |

**Hai cột này độc lập.** Một biên bản có thể đồng thời ở *Đã duyệt trả* (hàng
hỏng) và *Sẽ giao bù* (hàng thiếu).

---

# D — Sự cố thường gặp

| Hiện tượng | Nguyên nhân | Xử lý |
|---|---|---|
| Khách hỏi *"sao hàng hợp đồng của tôi không giao ngay"* | Đơn đó có ít nhất một dòng chưa có giá nên cả đơn đi một vòng báo giá | Giải thích theo A3, và hướng dẫn lần sau đặt riêng một đơn chỉ gồm hàng hợp đồng |
| Khách hỏi *"đơn của tôi đang chờ Miyano ra giá, sao không thấy chip nào tên vậy"* | Đơn chờ Miyano ra giá nằm ở **Đã duyệt**. Chip **Chờ quý vị đồng ý** là bước sau: giá đã về, việc đang ở phía bệnh viện | Bảo khách mở đơn và bấm Đồng ý / Sửa số lượng |
| Khách mở link cũ có `?chip=Chờ báo giá` | Tên chip đã đổi thành **Chờ quý vị đồng ý** | Không phải làm gì — link cũ vẫn mở đúng chip đó |
| Khách mở link cũ **Giỏ hàng / Đơn hàng của tôi / Đề xuất mua** | Ba màn đó đã gộp | Không phải làm gì — link tự chuyển sang màn mới |
| Không xác nhận được đơn | Còn dòng đặt ngoài chưa xử lý, hoặc còn dòng `HANG-DAT-NGOAI` | Xem B2 |
| Khớp mã xong mà bảng hàng có **hai dòng trùng nhau** | Có người thêm tay một dòng nữa, trong khi hệ thống đã tự dựng dòng đó | Xoá dòng thêm tay đi. Xem B2 |
| Khách bấm phiếu giao, mở ra bản in kèm **dòng chữ đỏ "chưa có chữ ký"** | Phiếu đã có bản scan nhưng cổng không phát được (sai định dạng tệp, hoặc tệp đã mất) | Đính lại bản scan bằng tệp PDF hoặc ảnh JPG/PNG. Không dùng ảnh HEIC |
| Khách bấm Kiểm hàng báo *"chưa ghi sổ hoặc đã huỷ"* | Phiếu giao chưa Submit | Submit phiếu giao |
| *"Phiếu giao này đã có biên bản… đã gửi"* | Đã kiểm rồi | Muốn khách gửi lại → **Từ chối** biên bản cũ |
| Không duyệt trả hàng được | Biên bản không có dòng hàng hỏng | Dùng nhóm **Hàng thiếu** |
| Phiếu trả hàng không Submit được | Phiếu giao gốc đã bị trả một phần trước đó | Kiểm lại số lượng còn trả được |
| Khách không nhận được thông báo | Tài khoản cổng chưa gắn đúng Contact | Xem `HDSD-tao-khach-hang…` mục A |
| Sales không nhận cảnh báo kiểm hàng | Khách chưa gán nhân viên phụ trách | Hệ thống tự gửi cho **Sales Manager**; nên gán `account_manager` cho khách |
| Không thấy nút **Miyano** trên Sales Order / Delivery Note | Asset của app chưa được build trên site | `bench build --app miyano_portal` rồi Ctrl+Shift+R |
| Không thấy mục **Việc từ cổng khách hàng** trên workspace | Site chưa chạy patch mới nhất | `bench --site <site> migrate` |
| Khách báo không nhận được **email** (thông báo trên cổng vẫn có) | Site chưa cấu hình **Email Account gửi ra** | Desk → Email Account → thêm tài khoản gửi. Mọi thông báo trên cổng vẫn chạy độc lập với email |

---

# E — Hệ thống cố ý KHÔNG làm

Những giới hạn dưới đây là **quyết định thiết kế**, không phải thiếu sót:

1. **Không tự Submit phiếu trả hàng.** Tồn kho chỉ được cộng lại khi hàng về tay
   kho thật.
2. **Không tự đoán mã hàng** cho dòng khách gõ tay. Sales phải tự quyết mã hàng.
   Khớp mã xong thì hệ thống mới dựng dòng hàng thật (B2) — nó làm phần cơ học,
   không làm phần phải quyết.
3. **Phiếu nhập kho của khách và Biên bản kiểm hàng không đồng bộ số liệu cho
   nhau.** Hai chứng từ, hai mục đích.
4. **Khách không sửa được biên bản đã gửi.** Đường lùi duy nhất là Miyano từ chối.
5. **"Sẽ giao bù" không đổi ngày cam kết gốc.** Ngày Miyano đã lỡ vẫn nằm đó.
6. **Khách không bao giờ nhìn thấy `HANG-DAT-NGOAI`** — nó bị lọc khỏi danh mục,
   giỏ hàng, chi tiết đơn, màn kiểm hàng và mọi mẫu in.
7. **Chỉ Sales Manager / System Manager được duyệt hoặc từ chối biên bản kiểm
   hàng.** `Sales User` xem và ghi chú được, không quyết được — đó là cam kết
   thương mại.
8. **Không tách một đơn theo tình trạng giá.** Đơn có dòng chưa có giá thì cả đơn
   đi một vòng báo giá (A3). Muốn phần có giá đi trước thì khách tự đặt hai lần —
   cắt đơn của bệnh viện là quyết định thương mại, hệ thống không làm thay.
9. **Màn Đặt hàng không hiện tổng tiền.** Từng dòng có đơn giá, nhưng không có
   "tạm tính" hay "tổng cộng" ở bất cứ đâu, kể cả hộp xác nhận — để khoa không nhớ
   một con số rồi đem so với hoá đơn cuối, trong khi Miyano còn báo giá phần
   chưa có giá ở bước sau.

---

*Tài liệu này mô tả hệ thống tại thời điểm 26/08/2026.*

*Phạm vi đã kiểm chứng: toàn bộ **luồng nghiệp vụ** của cả hai vai đã được kiểm
thử tự động và chạy thử trên dữ liệu thật; **màn hình cổng khách hàng** đã được
soát bằng mắt trên trình duyệt. **Giao diện Desk** (ba nhóm nút mô tả ở B4–B7)
chưa được soát bằng mắt tại thời điểm phát hành tài liệu — nếu thấy khác mô tả,
báo lại để cập nhật.*
