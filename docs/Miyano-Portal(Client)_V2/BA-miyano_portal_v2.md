# Tài liệu phân tích nghiệp vụ — ứng dụng `miyano_portal` — **v2.0 (trạng thái đích)**

| Mục | Nội dung |
|---|---|
| Ứng dụng | `miyano_portal` (Miyano Portal) — cổng khách hàng của SupplyCore v2 |
| Nền tảng | Frappe v15 + ERPNext (`required_apps = ["frappe/frappe", "erpnext"]`) |
| Site tham chiếu | `erptest.local` (prod: `erp.miyano.com.vn`) |
| Phiên bản tài liệu | **2.3 — trạng thái đích (target-state)**, thay thế bản 1.0 ngày 2026-08-10. *(2.1: thêm QT10/11/12. 2.2: QĐ-8 hạn mức 0 = không giới hạn. 2.3 — 12/08: QĐ-9 cấp phát hoá chất – vật tư cho khoa phòng/cá nhân — UC-54…56, BR-CP)* |
| Ngày lập | 2026-08-11 |
| Mức độ kiểm chứng | Nội dung nhãn **[Hiện có]** được đối chiếu trực tiếp với mã nguồn nhánh `feature/vat-tu-danh-muc` (commit đầu `971cc4b`) — không viết theo trí nhớ. Nội dung nhãn **[MỚI]** là yêu cầu thiết kế cho V2, **chưa có trong mã nguồn**, phải xây dựng. |

**Quy ước nhãn trong toàn tài liệu:**

| Nhãn | Ý nghĩa |
|---|---|
| **[Hiện có]** | Đã hiện thực và kiểm chứng trên mã nguồn |
| **[MỚI]** | Yêu cầu thiết kế bổ sung của v2.0 — chưa hiện thực |
| **[Hiện có, mở rộng]** | Cơ chế đã có, v2.0 bổ sung thêm trường/quy tắc/màn hình |

**Các quyết định của chủ đầu tư đã chốt ngày 2026-08-11** (căn cứ cho phần [MỚI]):

| # | Quyết định |
|---|---|
| QĐ-1 | Duyệt đơn phía Miyano theo **ngưỡng giá trị**: dưới ngưỡng Sales User tự xác nhận; từ ngưỡng trở lên bắt buộc Sales Manager (giải quyết VĐ-3) |
| QĐ-2 | **Không cho giao vượt** số lượng đặt: tổng luỹ kế các đợt giao ≤ SL đặt từng dòng (over-delivery allowance = 0) |
| QĐ-3 | BA viết theo **trạng thái đích**, gắn nhãn [Hiện có]/[MỚI] |
| QĐ-4 | Bộ tài liệu gồm 3 file: BA v2 + Form Spec + Workflow HTML v2 |
| QĐ-5 | **Mua lẻ ngoài hợp đồng khung**: danh mục toàn bộ Item, không hiện giá, mọi phiếu đều qua báo giá của sales (thiết kế lại 15/08 — bỏ "nhánh A đặt thẳng theo giá bán lẻ" của bản gốc). Bật/tắt theo từng khách, **mặc định BẬT** từ 15/08 |
| QĐ-6 | Đơn mua lẻ lập từ báo giá phải được khách **Đồng ý trên cổng** (trạng thái "Chờ khách đồng ý", có log, báo giá có hạn hiệu lực) |
| QĐ-7 | Hoá đơn điện tử: khách tải được **XML gốc + PDF bản thể hiện + link tra cứu CQT** trên cổng |
| QĐ-8 | *(góp ý review 12/08)* **Hạn mức khai 0 trong hợp đồng khung = đặt KHÔNG GIỚI HẠN** — hiển thị "Không giới hạn", không kiểm/không chặn hạn mức cho dòng đó (BR-O15) |
| QĐ-9 | *(góp ý review 12/08)* **Cấp phát cho khoa phòng/cá nhân**: theo dõi trên chính phiếu Xuất sử dụng — khoa phòng là danh mục cứng (bắt buộc chọn **theo cấu hình từng kho**), người nhận là ô nhập tự do có gợi ý lịch sử; "phiếu lĩnh online" của khoa phòng đưa vào backlog (VĐ-14) |

**Tài liệu này KHÔNG phải hướng dẫn thao tác.** Phần "bấm nút nào, ở màn nào" của từng trường dữ liệu nằm ở
[`FormSpec-miyano_portal_v2.md`](FormSpec-miyano_portal_v2.md). Bản trực quan của các quy trình nằm ở
[`01_Workflow-miyano_portal_v2.html`](01_Workflow-miyano_portal_v2.html).

Tài liệu nguồn phía trước: `YeuCau_NghiepVu_ThietKe_ClientPortal_Miyano.docx` (BRD V1, 27/07/2026),
`BA-miyano_portal.md` v1.0 (as-built, 10/08/2026), bộ kịch bản test `KichBan_DuLieu_Test_ClientPortal_Miyano_v1.0.xlsx`,
2 mockup HTML V1 (desktop + mobile).

---

## 1. Bối cảnh và mục tiêu nghiệp vụ

Miyano là nhà cung cấp vật tư — hoá chất, sinh phẩm, vật tư tiêu hao — cho bệnh viện và
phòng xét nghiệm. Cổng khách hàng giải quyết hai bài toán:

1. **Vòng đời đơn hàng Miyano ↔ khách**: đặt hàng theo hợp đồng khung, theo dõi đơn,
   phiếu giao, hoá đơn, công nợ — không qua điện thoại/email/Excel.
2. **Kho của chính khách hàng**: bệnh viện tự quản lý nhập – xuất – tồn vật tư của mình,
   theo lô và hạn dùng, in chứng từ theo mẫu.

**Điểm mấu chốt của v2.0**: khách hàng **không chỉ mua từ Miyano** — họ nhập hàng từ nhiều nhà
cung ứng khác. Cổng vì vậy phải quản lý được kho **đa nguồn** (Miyano + NCC khác), kiểm soát
xuất – nhập – tồn **theo từng đợt hàng**, và từ dòng dữ liệu tiêu thụ thật đó, Miyano phân tích
để đưa ra **số lượng dự trù chính xác cho từng loại vật tư** — hướng đến giao hàng Just-in-Time,
tối ưu nguồn lực vận hành chuỗi cung ứng cho cả hai phía.

| # | Mục tiêu | Chỉ báo đạt được | Nhãn |
|---|---|---|---|
| MT1 | Khách tự đặt hàng theo hợp đồng khung, không qua trung gian | Đơn hàng sinh thẳng thành `Sales Order` với `custom_nguon_don = "Client Portal"` | Hiện có |
| MT2 | Hạn mức hợp đồng được máy kiểm, không kiểm bằng mắt | Vượt hạn mức bị chặn ngay lúc đặt, kèm số còn lại | Hiện có |
| MT3 | Khách tự tra cứu đơn / phiếu giao / hoá đơn / công nợ | Không còn yêu cầu tra cứu qua nhân viên kinh doanh | Hiện có |
| MT4 | Bệnh viện quản lý kho của mình ngay trên cổng, có lô và hạn dùng | Sổ kho, thẻ kho, báo cáo NXT, cảnh báo hạn dùng | Hiện có |
| MT5 | Hàng Miyano giao đến tự chảy vào kho khách, không nhập lại — **kể cả khi một đơn giao làm nhiều đợt** | Mỗi `Delivery Note` sinh một phiếu nhập **nháp** riêng; đơn giao N đợt → N phiếu nhập | Hiện có, mở rộng |
| MT6 | Chứng từ kho in được theo mẫu của từng đơn vị | `Print Format` chọn theo từng kho | Hiện có |
| MT7 | Dữ liệu khách này tuyệt đối không lọt sang khách khác | Xem mục 8 | Hiện có |
| MT8 | **Kho đa nguồn**: quản lý được hàng mua từ NCC khác ngoài Miyano, có danh mục NCC, chứng từ nguồn | Phiếu nhập "Mua ngoài" gắn NCC + số chứng từ; báo cáo tách được theo nguồn | **MỚI** |
| MT9 | **Kiểm soát NXT theo từng đợt hàng**: mỗi đợt nhận biết đã tiêu thụ bao nhiêu, còn bao nhiêu, tồn bao lâu | Nhật ký vật tư + báo cáo NXT theo đợt (mục 4, QT8) | **MỚI** |
| MT10 | **Dự trù chính xác — Just-in-Time**: từ dữ liệu tiêu thụ thật, hệ thống gợi ý mức tồn min/max, điểm đặt hàng lại; Miyano có báo cáo tiêu thụ – dự báo – độ phủ để lập kế hoạch cung ứng | Vòng lặp QT9: tiêu thụ → ADU → cảnh báo dưới min → giỏ hàng bổ sung → đơn hàng | **MỚI** |
| MT11 | **Mua lẻ ngoài hợp đồng khung**: khách được phép đặt bất kỳ mặt hàng nào ngay trên cổng, kể cả chưa có mã — giá do Miyano báo sau, khách duyệt trước khi giao | Đơn `custom_loai_don = "Mua lẻ"`, không trừ hạn mức, luôn qua xác nhận + báo giá (QT10, thiết kế lại 15/08) | **MỚI** |
| MT12 | **Không bỏ sót nhu cầu**: hàng khách cần mà không có trong hợp đồng khung / chưa có Item đều đặt được ngay trên phiếu mua lẻ (khối "chưa có mã", §4.10); Desk vẫn dùng `Portal Item Request` cho nhu cầu cần tìm nguồn phức tạp hơn | Khối tự nhập trên phiếu Mua lẻ (khách) + `Portal Item Request`/SLA/demand pipeline (Desk, QT11) | **MỚI, sửa 15/08** |
| MT13 | **Hoá đơn điện tử tự phục vụ**: khách tự tải XML gốc + PDF + mã tra cứu, kế toán hai bên không phải gửi tay | Khối HĐĐT trên cổng, đọc từ module HĐĐT của team Dev (QT12) | **MỚI** |

---

## 2. Phạm vi

### 2.1 Trong phạm vi

- Cổng web (SPA) tại `/portal` cho người dùng phía khách hàng. **[Hiện có]**
- Đặt hàng theo hợp đồng khung, kiểm hạn mức, theo dõi đơn, xem phiếu giao, xem hoá đơn
  và công nợ. **[Hiện có]**
- **Giao hàng nhiều đợt trên một đơn**: theo dõi từng đợt, % đã giao, đối soát chênh lệch
  giao – nhận. **[Hiện có, mở rộng]**
- Kho khách hàng: danh mục vật tư riêng, tồn đầu kỳ, phiếu nhập, phiếu xuất, sổ kho theo lô,
  báo cáo NXT, thẻ kho, cảnh báo hạn dùng, in phiếu, xuất/nhập Excel. **[Hiện có]**
- **Nhập hàng mua ngoài từ NCC khác**: danh mục NCC của từng kho, phiếu nhập gắn NCC và chứng từ
  nguồn. **[MỚI]**
- **Nhật ký vật tư và kiểm soát NXT theo đợt hàng**. **[MỚI]**
- **Mức tồn min/max, điểm đặt hàng lại, cảnh báo thiếu tồn, giỏ hàng bổ sung 1 chạm**. **[MỚI]**
- **Phân tích phía Miyano**: tiêu thụ, dự báo nhu cầu, độ phủ tồn kho khách, tỷ trọng
  Miyano/NCC khác, đề xuất dự trù. **[MỚI]**
- **Mua lẻ ngoài hợp đồng khung** (mặc định bật): danh mục toàn bộ mặt hàng không hiện giá, gõ
  thẳng tên hàng khi không tìm ra mã, qua báo giá của sales, khách đồng ý trên cổng, tải PDF báo
  giá. **[MỚI, thiết kế lại 15/08]**
- **Yêu cầu hàng hoá & tìm nguồn** *(Desk-only, đổi 15/08)*: ghi nhận nhu cầu ngoài danh mục (kể cả
  hàng chưa có Item trong ERPNext), định tuyến cho sales/purchasing kèm SLA — nay nhân viên Miyano
  tạo thay khách; đường vào từ cổng đã thay bằng khối "chưa có mã" ngay trên phiếu mua lẻ. **[MỚI]**
- **Hoá đơn điện tử**: hiển thị trạng thái, tải XML gốc + PDF, mã và link tra cứu CQT. **[MỚI]**
- **Cấp phát hoá chất – vật tư cho khoa phòng/cá nhân**: danh mục khoa phòng của kho, ghi nhận
  nơi/người nhận trên phiếu xuất sử dụng, báo cáo cấp phát theo khoa. **[MỚI — QĐ-9]**
- Móc tích hợp một chiều từ `Delivery Note` của Miyano sang kho khách. **[Hiện có]**
- Phân quyền và cách ly dữ liệu theo từng khách hàng. **[Hiện có]**
- Màn hình phía Desk cho nhân viên Miyano tra cứu kho khách. **[Hiện có, mở rộng]**

### 2.2 Ngoài phạm vi — và lý do

| Không làm | Lý do |
|---|---|
| **Kho khách hàng KHÔNG dùng tồn kho ERPNext** — không `Warehouse`, không `Bin`, không `Stock Entry`, không `Stock Ledger Entry`, không gắn `Company` | Cả hai công ty Miyano đều bật `enable_perpetual_inventory = 1`. Một phiếu xuất của bệnh viện đi qua tồn kho ERPNext sẽ ghi bút toán giá vốn **lên sổ sách của Miyano**. Quyết định nền tảng, giữ nguyên ở v2.0 — hàng mua từ NCC khác lại càng không được phép chạm sổ Miyano. |
| NCC khác **không có tài khoản** trên cổng | NCC khác chỉ là **dữ liệu danh mục** phục vụ ghi nhận nguồn nhập; cổng không phải sàn nhiều nhà cung cấp. Giữ ứng dụng tinh gọn. |
| Khách tự huỷ đơn trên cổng | Chỉ có *yêu cầu huỷ* (`portal_request_cancel`); quyết định huỷ thuộc Miyano |
| Thanh toán trực tuyến | Cổng chỉ hiển thị công nợ, không thu tiền |
| Khách sửa giá / sửa hợp đồng | Giá lấy từ `Price List` riêng của khách, chỉ đọc |
| Đấu thầu, so sánh giá cạnh tranh giữa nhiều NCC | Không nằm trong vòng đời cổng. *Riêng báo giá mua lẻ đơn giản (một người bán) thuộc phạm vi từ v2.1 — QT10/QT11* |
| Phát hành / huỷ / điều chỉnh HĐĐT từ cổng | Cổng chỉ **đọc** kết quả từ module HĐĐT của team Dev (BR-E5); nghiệp vụ phát hành thuộc kế toán trên Desk |
| Phê duyệt nội bộ phía khách (người đặt → người duyệt của khách) | FR-A4 của BRD V1, mức "tuỳ chọn". Chưa có nhu cầu thực; đưa vào backlog (VĐ-9) để giữ luồng đặt hàng 3 bước |
| Quản lý nhiều kho cho một khách | Mỗi khách hàng một kho đang hoạt động (BR-K1); mở rộng là VĐ-6 |
| Ứng dụng di động đóng gói (native) | Cổng chạy responsive trên trình duyệt |

---

## 3. Tác nhân và vai trò

| Tác nhân | Vai trò kỹ thuật | Làm được gì | Nơi làm việc |
|---|---|---|---|
| **Người dùng cổng của khách hàng** (thủ kho / kế toán / điều dưỡng trưởng) | `Website User` + role `Customer`, `Contact` trỏ về `Customer` | Đặt hàng, tra cứu, toàn bộ nghiệp vụ kho của đơn vị mình — gồm nhập mua ngoài, nhật ký vật tư, thiết lập min/max **[MỚI]** | `/portal` |
| **Nhân viên kinh doanh Miyano** | `Sales User` | Xác nhận / từ chối đơn **dưới ngưỡng**, lập `Delivery Note`, `Sales Invoice`, xử lý chênh lệch giao – nhận | Desk ERPNext |
| **Quản lý kinh doanh Miyano** | `Sales Manager` | Như trên; **bắt buộc** với đơn **từ ngưỡng trở lên** (QĐ-1) **[MỚI]**; sửa đơn đã xác nhận / từ chối | Desk ERPNext |
| **Nhân viên kế hoạch / cung ứng Miyano** **[MỚI]** | `Sales Manager` hoặc role đọc báo cáo | Xem báo cáo tiêu thụ, dự báo, độ phủ, đề xuất dự trù để lập kế hoạch mua và tồn kho Miyano | Desk ERPNext |
| **Nhân viên mua hàng (purchasing) Miyano** **[MỚI]** | `Purchase User` | Tiếp nhận yêu cầu hàng hoá cần tìm nguồn (QT11), tạo Item mới qua chuẩn hoá, phản hồi giá + lead time | Desk ERPNext |
| **Kế toán Miyano** | `Accounts User` | Lập `Sales Invoice`, phát hành HĐĐT bằng module của team Dev; cổng tự hiển thị kết quả (QT12) | Desk ERPNext |
| **Quản trị hệ thống** | `System Manager` | Tạo khách hàng, cấp tài khoản cổng, mở kho, chọn mẫu in, bật/tắt kho, cấu hình ngưỡng duyệt và tham số dự trù **[MỚI]** | Desk ERPNext |
| *(Dữ liệu, không phải người dùng)* **NCC khác của khách** **[MỚI]** | Doctype `Customer Supplier` | Không đăng nhập; chỉ được ghi nhận trên phiếu nhập mua ngoài | — |

Một điểm cần nêu rõ vì dễ hiểu sai: **người dùng cổng không hề có quyền trên các doctype kho.**
Họ thao tác được là nhờ tầng API whitelist tự suy ra kho từ phiên đăng nhập, không phải nhờ
được cấp quyền doctype. Xem mục 8. Nguyên tắc này áp dụng **y hệt** cho các doctype [MỚI].

---

## 4. Quy trình nghiệp vụ

Mười hai luồng dưới đây là "xương sống", trùng cấu trúc với file
[`01_Workflow-miyano_portal_v2.html`](01_Workflow-miyano_portal_v2.html). Mỗi luồng gồm **luồng chính**
và bảng **luồng ngoại lệ** (mã `NL-x.y`). Nguyên tắc viết ngoại lệ: mỗi dòng nêu rõ *tình huống*,
*chốt chặn/cách phát hiện*, *hệ thống làm gì*, *kết cục* — theo triết lý phòng ngừa: ngoại lệ phải
được thiết kế trước, không xử lý tuỳ hứng khi xảy ra.

### 4.1 QT1 — Đặt hàng trên cổng **[Hiện có, mở rộng]**

**Luồng chính:**

```
Khách chọn hợp đồng (Blanket Order)
   → xem danh mục = các mặt hàng trong hợp đồng + giá từ Price List riêng + hạn mức còn lại
   → thêm vào giỏ (kiểm SL > 0, bội số quy cách [MỚI], không vượt hạn mức còn lại)
   → nhập ngày giao mong muốn, địa chỉ giao, số PO nội bộ, ghi chú
   → đặt hàng  ──► portal_order_place
                     ├─ kiểm mã yêu cầu chống tạo trùng (request_id)      [MỚI]
                     ├─ kiểm hợp đồng thuộc đúng khách                    (BR-O1)
                     ├─ kiểm địa chỉ giao thuộc đúng khách (nếu có chọn)  (BR-O1)
                     ├─ GỘP các dòng trùng mã hàng                        (BR-O2)
                     ├─ kiểm hạn mức từng mã hàng, gom hết lỗi báo 1 lần  (BR-O3)
                     │    · dòng hạn mức khai 0 = KHÔNG GIỚI HẠN → bỏ qua kiểm (BR-O15) [MỚI]
                     ├─ kiểm bội số quy cách đóng gói                     (BR-O11) [MỚI]
                     ├─ kiểm ngày giao mong muốn hợp lệ                   (BR-O13) [MỚI]
                     ├─ lấy giá từ Item Price của Price List khách        (BR-O5)
                     ├─ chọn kho xuất theo TỪNG mặt hàng                  (BR-O4)
                     └─ tạo Sales Order NHÁP, gắn contact_email để gửi thông báo
   → email "Portal - Đơn mới" gửi cho khách
```

Kết quả: một `Sales Order` `docstatus = 0`, `workflow_state = "Chờ xác nhận"` (Frappe gán mặc định
theo trạng thái đầu của workflow — `portal_order_place` **không** tự đặt trường này).

**Luồng ngoại lệ QT1:**

| Mã | Tình huống | Chốt chặn / phát hiện | Xử lý | Nhãn |
|---|---|---|---|---|
| NL-1.1 | hợp đồng khung hết hiệu lực hoặc khách không có hợp đồng khung nào còn hiệu lực | So `from_date`/`to_date` của `Blanket Order` với ngày hiện tại | Danh mục khoá đặt hàng, hiển thị cảnh báo + đầu mối sales phụ trách; **lịch sử đơn thuộc hợp đồng khung cũ vẫn tra cứu được** | Hiện có |
| NL-1.2 | Một mặt hàng đã dùng **hết** hạn mức (đã đặt đủ tổng hạn mức > 0) | Hạn mức còn lại tính từ `Blanket Order` | Ô số lượng và nút thêm giỏ bị khoá tại dòng, ghi "Hết hạn mức". **Phân biệt** với hạn mức *khai* bằng 0 = Không giới hạn (NL-1.11) | Hiện có, mở rộng |
| NL-1.3 | Tổng đặt (sau khi gộp dòng trùng mã) vượt hạn mức còn lại | `portal_order_place` — kiểm sau khi gộp (BR-O2) | Chặn toàn đơn; báo **một lần đủ mọi mã hàng sai**, kèm số còn được đặt của từng mã (BR-O3) | Hiện có |
| NL-1.4 | Mặt hàng không có giá trong `Price List` của khách | BR-O5 tại `portal_order_place` | Chặn đặt hàng, nêu rõ mã hàng; **[MỚI]** đồng thời notification cho sales phụ trách để bổ sung giá — khách không phải tự đi đòi giá | Hiện có, mở rộng |
| NL-1.5 | Địa chỉ giao không thuộc đơn vị (giả mạo request) | BR-O1 tại `portal_order_place` | Chặn, trả lỗi 403; không lộ địa chỉ của khách khác | Hiện có |
| NL-1.6 | Số lượng sai bội số quy cách đóng gói (VD bội số 10, nhập 15) | BR-O11 — kiểm ở giỏ hàng (tức thời) và kiểm lại ở `portal_order_place` (chốt) | Báo lỗi ngay tại dòng, nêu bội số đúng; server là chốt chặn cuối | **MỚI** |
| NL-1.7 | Ngày giao mong muốn ở quá khứ hoặc sớm hơn chuẩn giao | BR-O13 — mặc định +2 ngày làm việc, chặn ngày quá khứ | Báo lỗi tại trường, gợi ý ngày hợp lệ gần nhất | **MỚI** |
| NL-1.8 | Mất mạng / timeout đúng lúc bấm "Xác nhận đặt hàng" → nguy cơ bấm lại tạo đơn trùng | BR-O12 — mỗi lần mở màn xác nhận sinh một `request_id`; server nhớ id đã xử lý | Nút khoá khi đang gửi; gửi lại cùng `request_id` → trả về **đơn đã tạo**, không tạo đơn thứ hai | **MỚI** |
| NL-1.9 | Phiên đăng nhập hết hạn giữa chừng | HTTP 401/403 từ API | Đưa về màn đăng nhập; giỏ hàng lưu phía máy chủ theo tài khoản nên **không mất** | **MỚI** |
| NL-1.10 | Hai người dùng cùng đơn vị đặt song song, tổng vượt hạn mức (race) | Kiểm tại `portal_order_place` là chốt thời điểm đặt; kiểm lần cuối khi Miyano **xác nhận** (submit) là chốt sau cùng của ERPNext | Đơn đặt sau bị chặn hoặc bị phát hiện lúc xác nhận → xử lý theo NL-2.4 | Hiện có (2 tầng chốt) |
| NL-1.11 | Hạn mức của mặt hàng trong hợp đồng khung **khai bằng 0** | Quy ước QĐ-8 / BR-O15 | Hiểu là **KHÔNG GIỚI HẠN**: hiển thị nhãn "Không giới hạn", không kiểm hạn mức; dòng SO **không gắn** `against_blanket_order` (cơ chế gốc ERPNext coi 0 là cấm đặt); vẫn gắn `custom_hdnt` để truy vết và thống kê SL đã đặt luỹ kế | **MỚI** |

### 4.2 QT2 — Miyano xử lý đơn: máy trạng thái + duyệt theo ngưỡng **[Hiện có, mở rộng]**

Workflow `Sales Order - Client Portal` cài trên doctype `Sales Order`:

| Trạng thái | `docstatus` | Ai được sửa |
|---|---|---|
| Chờ xác nhận | 0 (nháp) | `Sales User` |
| Chờ Miyano xác nhận | 0 (nháp) | `Sales User` |
| Đã xác nhận | 1 (đã ghi sổ) | `Sales Manager` |
| Từ chối | 0 (nháp) | `Sales Manager` |
| **Chờ khách đồng ý** *(chỉ đơn mua lẻ lập từ báo giá — QT10)* | 0 (nháp) | `Sales User` | 

**Chuyển tiếp theo QĐ-1 (duyệt theo ngưỡng) [MỚI — thay cấu hình hiện tại]:**

| Từ | Hành động | Sang | Ai được làm | Điều kiện |
|---|---|---|---|---|
| Chờ xác nhận | Gửi duyệt | Chờ Miyano xác nhận | `Sales User` | — |
| Chờ Miyano xác nhận | Xác nhận | Đã xác nhận | `Sales User` | `grand_total` **<** ngưỡng duyệt |
| Chờ Miyano xác nhận | Xác nhận | Đã xác nhận | `Sales Manager` | `grand_total` **≥** ngưỡng duyệt |
| Chờ Miyano xác nhận | Từ chối | Từ chối | `Sales User` | dưới ngưỡng; **bắt buộc nhập lý do** |
| Chờ Miyano xác nhận | Từ chối | Từ chối | `Sales Manager` | từ ngưỡng trở lên; **bắt buộc nhập lý do** |
| Chờ khách đồng ý | Khách đồng ý *(qua `portal_order_accept`)* | Chờ Miyano xác nhận | hệ thống thay mặt khách, ghi log người bấm + thời điểm | chỉ đơn `custom_loai_don = "Mua lẻ"` **[MỚI]** |
| Chờ khách đồng ý | Khách không đồng ý *(kèm lý do)* | Chờ xác nhận | hệ thống, ghi log | sales sửa giá / huỷ nháp **[MỚI]** |

- Ngưỡng duyệt đặt trong `Miyano Portal Settings.nguong_duyet_2_tang` **[MỚI]** (giá trị cụ thể:
  VĐ-8). Ngưỡng để trống = mọi đơn một tầng (hành vi hiện tại).
- Hiện trạng mã nguồn: cả ba chuyển tiếp đều mở cho `Sales User` — tức chưa có duyệt hai tầng.
  Cấu hình trên là **thay đổi phải làm** để thực thi QĐ-1.
- **Workflow áp cho MỌI `Sales Order`**, không riêng đơn từ cổng (Frappe Workflow gắn theo doctype).
  Chủ đầu tư đã chấp nhận (VĐ-4).

Thông báo email theo trạng thái **[Hiện có]**:

| Sự kiện | Thông báo | Điều kiện |
|---|---|---|
| Tạo mới `Sales Order` | Portal - Đơn mới | `custom_nguon_don == "Client Portal"` |
| Ghi sổ `Sales Order` | Portal - Đơn xác nhận | `custom_nguon_don == "Client Portal"` |
| `workflow_state` = "Từ chối" | Portal - Đơn bị từ chối (kèm lý do) | `custom_nguon_don == "Client Portal"` |
| Ghi sổ `Delivery Note` | Portal - Xuất giao | mọi phiếu giao |
| Ghi sổ `Sales Invoice` | Portal - Hoá đơn phát hành | mọi hoá đơn |

Trạng thái hiển thị cho khách trên cổng **không** phải `workflow_state` mà là nhãn suy ra từ
`status` + `per_delivered` (BR-O7): Chờ xác nhận → Đang xử lý → Đang giao → Hoàn thành / Đã huỷ.

**Luồng ngoại lệ QT2:**

| Mã | Tình huống | Chốt chặn / phát hiện | Xử lý | Nhãn |
|---|---|---|---|---|
| NL-2.1 | Miyano từ chối đơn | Chuyển tiếp "Từ chối" | **Bắt buộc nhập lý do** mới chuyển được trạng thái; khách nhận email kèm đúng lý do; đơn nằm ở "Từ chối" (`docstatus 0`) để truy vết, không xoá | Hiện có, mở rộng (bắt buộc lý do là [MỚI]) |
| NL-2.2 | Khách gửi yêu cầu huỷ khi đơn còn Chờ xác nhận | `portal_request_cancel` (BR-O8) | Yêu cầu + lý do ghi vào đơn (Comment) và báo sales; sales huỷ nháp → hạn mức không bị chiếm; khách thấy trạng thái Đã huỷ | Hiện có |
| NL-2.3 | Khách yêu cầu sửa đơn khi còn Chờ xác nhận | Yêu cầu hỗ trợ trên chi tiết đơn | Sales sửa trực tiếp bản nháp; **mọi chỉnh sửa hiển thị lại cho khách trên chi tiết đơn trước khi xác nhận** (nguyên tắc FR-C6 của BRD V1) | Hiện có |
| NL-2.4 | Lúc xác nhận phát hiện vượt hạn mức (do 2 đơn nháp song song — NL-1.10) | Kiểm hạn mức gốc của ERPNext khi submit (`against_blanket_order`) | Không submit được; sales liên hệ khách điều chỉnh số lượng hoặc từ chối đơn theo NL-2.1 | Hiện có |
| NL-2.5 | Đơn từ ngưỡng trở lên nhưng Sales User bấm Xác nhận | Điều kiện chuyển tiếp theo ngưỡng (QĐ-1) | Workflow không cho chuyển; hiển thị "cần Sales Manager duyệt"; đơn chờ ở "Chờ Miyano xác nhận" | **MỚI** |
| NL-2.6 | Đơn treo quá SLA xử lý (mặc định 8 giờ làm việc, cấu hình được) | Job nền quét đơn "Chờ Miyano xác nhận" quá hạn | Notification leo thang cho Sales Manager; đơn hiện trong báo cáo đơn chậm xử lý | **MỚI** |
| NL-2.7 | Miyano cần huỷ đơn **đã xác nhận, chưa giao** | Cancel `Sales Order` chuẩn ERPNext | Hạn mức hoàn tự động (ordered qty giảm); email "đơn bị huỷ + lý do" cho khách; trạng thái cổng = Đã huỷ | Hiện có (email huỷ là [MỚI]) |
| NL-2.8 | Đơn **đã giao một phần**, phần còn lại không giao nữa (khách đổi nhu cầu / hết hàng) | Không cancel được vì đã có DN | **Close** `Sales Order`; phần chưa giao được **hoàn hạn mức** bằng bước điều chỉnh Blanket Order (cơ chế: VĐ-7); khách thấy đơn "Hoàn thành (đóng sớm)" kèm ghi chú | **MỚI** |

### 4.3 QT3 — Giao hàng nhiều đợt trên một đơn → phiếu nhập tự sinh từng đợt **[Hiện có, mở rộng]**

Một `Sales Order` được phép giao **nhiều lần (nhiều đợt)**. Mỗi đợt là một `Delivery Note`
độc lập. Đây là cơ chế gốc của ERPNext (`per_delivered`, nhiều DN trỏ về một SO) — v2.0 bổ sung
phần **hiển thị theo đợt** cho khách và **đối soát chênh lệch giao – nhận**.

**Luồng chính:**

```
Sales Order (Đã xác nhận)
   → Miyano lập Delivery Note đợt 1 (một phần số lượng), ghi sổ
   → ... lập tiếp đợt 2, đợt 3 ... cho tới đủ         (tổng luỹ kế ≤ SL đặt — BR-O10 [MỚI])
        │
        │  mỗi lần ghi sổ DN:  doc_events["Delivery Note"]["on_submit"]
        ▼
   miyano_portal.kho.delivery_hook.on_delivery_note_submit
        ├─ tìm kho ĐANG HOẠT ĐỘNG của khách; không có → dừng im lặng      (BR-K12)
        ├─ DN này đã có phiếu nhập (docstatus < 2) → dừng, không sinh trùng (BR-K11)
        ├─ với mỗi dòng: khớp/tạo Customer Warehouse Item trong kho khách
        ├─ lấy số lô + hạn dùng từ bundle lô do ERPNext sinh
        ├─ ghi SL giao vào sl_giao từng dòng để đối soát                   [MỚI]
        ├─ gắn số đợt (thứ tự DN trong phạm vi SO)                         [MỚI]
        └─ tạo Customer Stock Receipt NHÁP, loai_nhap = "Từ đơn hàng Miyano",
           ghi delivery_note / sales_order để truy vết
   → thủ kho bệnh viện kiểm hàng thực tế → sửa SL thực nhận nếu lệch → ghi sổ
   → cổng hiển thị trên chi tiết đơn: danh sách đợt giao, % đã giao, phiếu nhập tương ứng
```

**Ba tính chất thiết kế của móc — đều cố ý, giữ nguyên [Hiện có]:**

- Đặt ở `on_submit`/`on_cancel` chứ không phải `before_*`: móc chỉ sinh hiệu ứng phụ, không kiểm tra.
- **Không bao giờ ném lỗi ra ngoài** (BR-K12): việc giao hàng của Miyano không phụ thuộc kho khách.
- Phiếu sinh ra ở trạng thái **nháp**: hàng chưa kiểm nhận mà tồn đã tăng là sai nghiệp vụ.

**Luồng ngoại lệ QT3:**

| Mã | Tình huống | Chốt chặn / phát hiện | Xử lý | Nhãn |
|---|---|---|---|---|
| NL-3.1 | Khách không có kho hoặc kho đã tắt (`active = 0`) | `_kho_cua_khach` | Móc dừng **im lặng**, DN vẫn ghi sổ bình thường; không sinh phiếu | Hiện có |
| NL-3.2 | DN đã sinh phiếu nhập trước đó (chạy lại hook, sửa – submit lại) | BR-K11 (`_phieu_dang_song`) | Không sinh phiếu thứ hai — tránh cộng tồn hai lần | Hiện có |
| NL-3.3 | **Nhận thiếu / hàng hỏng**: SL thực nhận < SL trên phiếu giao | Thủ kho sửa SL trên phiếu nháp; hệ so `so_luong` với `sl_giao` | Bắt buộc ghi **lý do chênh lệch** từng dòng lệch (BR-K17); khi ghi sổ, phiếu gắn cờ `co_chenh_lech`; notification "Chênh lệch nhận hàng" cho sales phụ trách; hai bên đối soát qua báo cáo Đối soát giao – nhận (UC-48) | **MỚI** |
| NL-3.4 | Khách **từ chối nhận toàn bộ** đợt giao | Phiếu nháp không được ghi sổ | Thủ kho không ghi sổ (tồn không đổi); Miyano huỷ DN → phiếu nháp bị gỡ tự động; nếu cần chứng từ trả: quy trình Sales Return phía Miyano | Hiện có (cơ chế gỡ) + quy ước [MỚI] |
| NL-3.5 | Miyano huỷ DN khi phiếu nhập **còn nháp** | `on_cancel` hook | Phiếu nháp bị gỡ | Hiện có |
| NL-3.6 | Miyano huỷ DN khi phiếu nhập **đã ghi sổ** | `on_cancel` hook | Phiếu bị **đảo** theo QT5 — không xoá dòng sổ nào | Hiện có |
| NL-3.7 | Hàng giao **không có số lô / hạn dùng** (Miyano chưa bật batch/expiry cho item) | Dòng phiếu nhận `KHONG-LO`, hạn dùng rỗng | Phiếu vẫn sinh (không chặn giao — BR-K12), nhưng dòng bị đánh dấu "thiếu lô/hạn"; báo cáo chất lượng dữ liệu phía Desk liệt kê để Miyano bật batch/expiry — tiền đề của FEFO, cảnh báo hạn và VĐ-2 | **MỚI** |
| NL-3.8 | Miyano lập DN **vượt** SL đặt còn lại | Over-delivery allowance = 0 (QĐ-2, BR-O10) | ERPNext chặn ngay khi ghi sổ DN | **MỚI** (cấu hình) |
| NL-3.9 | Khách **trả hàng sau khi đã nhận** (sai hàng, hỏng, hết hạn) | Hai chứng từ hai phía | Phía khách: phiếu xuất `loai_xuat = "Xuất trả lại"` (trừ tồn); phía Miyano: Sales Return / Credit Note theo quy trình hiện hành; hạn mức hợp đồng khung hoàn theo VĐ-7; báo cáo đối soát khớp hai phía qua tham chiếu DN gốc | **MỚI** (quy ước + đối soát) |
| NL-3.10 | Thủ kho **sửa tăng** SL thực nhận vượt SL giao | BR-K17 | Chặn: SL thực nhận ≤ SL giao từng dòng (phiếu nguồn Miyano); nhận thừa thật sự → xử lý bằng phiếu "Nhập khác" kèm ghi chú, không sửa phiếu tự sinh | **MỚI** |

### 4.4 QT4 — Nghiệp vụ kho của khách hàng **[Hiện có, mở rộng]**

```
Mở kho  ──►  Danh mục vật tư  ──►  Nhập tồn đầu kỳ (một lần)
                   │                        │
                   │                        ▼
                   │              ┌──── SỔ KHO (append-only) ────┐
                   ▼              │                              │
        Phiếu nhập  ──ghi sổ──────┤  Customer Stock Ledger Entry │
        (tự sinh / tay / Excel /  │              +               │──► Báo cáo NXT
         mua ngoài NCC khác [MỚI])│  Customer Stock Lot Balance  │──► Thẻ kho
                                  │        (cache dẫn xuất)      │──► Cảnh báo hạn
        Phiếu xuất  ──ghi sổ──────┤                              │──► Nhật ký vật tư   [MỚI]
        (gợi ý lô FEFO)           └──────────────────────────────┘──► NXT theo đợt     [MỚI]
                                                                 ──► Cảnh báo tồn min  [MỚI]
```

Vòng đời một phiếu (cả nhập lẫn xuất): **Nháp** (`docstatus 0`) → **Đã ghi sổ** (`docstatus 1`,
sinh dòng sổ) → **Đã huỷ** (`docstatus 2`, sinh phiếu đảo). Không có bước duyệt trung gian —
thủ kho tự chịu trách nhiệm trên phiếu của mình.

Các loại phiếu (trạng thái đích):

| Chiều | `loai_nhap` / `loai_xuat` | Nhãn |
|---|---|---|
| Nhập | Tồn đầu kỳ | Hiện có |
| Nhập | Từ đơn hàng Miyano | Hiện có |
| Nhập | **Mua ngoài (NCC khác)** — bắt buộc gắn NCC, xem QT7 | **MỚI** |
| Nhập | **Điều chỉnh kiểm kê (tăng)** — tách khỏi "Nhập khác" để không méo số liệu tiêu thụ | **MỚI** |
| Nhập | Nhập khác | Hiện có |
| Nhập | Phiếu đảo *(chỉ hệ thống tạo — BR-K9)* | Hiện có |
| Xuất | Xuất sử dụng *(nguồn duy nhất tính tiêu thụ — BR-P1)* | Hiện có |
| Xuất | Xuất huỷ - hết hạn | Hiện có |
| Xuất | Xuất trả lại | Hiện có |
| Xuất | Điều chỉnh kiểm kê | Hiện có |
| Xuất | Phiếu đảo *(chỉ hệ thống tạo)* | Hiện có |

Xuất kho có gợi ý lô theo **FEFO** (`kho_lo_goi_y`, BR-K13): đi từ lô hết hạn gần nhất, lô không
có hạn xếp cuối, phân bổ tham lam cho tới đủ. Đây **chỉ là gợi ý hiển thị**, không chặn; chốt chặn
thật nằm ở `before_submit` của `Customer Stock Issue` (BR-K5).

**Cấp phát cho khoa phòng / cá nhân [MỚI — QĐ-9]:** phiếu "Xuất sử dụng" chính là chứng từ cấp phát —
không sinh loại phiếu mới. Phiếu ghi thêm **khoa phòng nhận** (chọn từ danh mục khoa phòng của kho —
bắt buộc khi kho bật cờ `bat_buoc_khoa_phong`, BR-CP2) và **người nhận** (nhập tự do, gợi ý từ lịch
sử của khoa đó — BR-CP3; quan trọng với hoá chất cần vết ai nhận). Khoa phòng + người nhận in lên
phiếu xuất (mẫu TT107 có sẵn phần người nhận — ký nhận trên bản giấy theo quy trình của bệnh viện).
Từ dữ liệu này: báo cáo **Cấp phát theo khoa phòng** (mục 10) và lọc theo khoa ở nhật ký vật tư.
Khoa phòng tự gửi *phiếu lĩnh online* chưa nằm trong phạm vi (VĐ-14).

**Luồng ngoại lệ QT4:**

| Mã | Tình huống | Chốt chặn / phát hiện | Xử lý | Nhãn |
|---|---|---|---|---|
| NL-4.1 | Xuất quá tồn của lô | BR-K5 tại `before_submit` | Chặn ghi sổ, nêu rõ lô nào thiếu bao nhiêu; phiếu vẫn ở nháp để sửa | Hiện có |
| NL-4.2 | Vật tư trên phiếu không thuộc kho của phiếu | BR-K2 `validate_vat_tu_thuoc_kho` | Chặn lưu | Hiện có |
| NL-4.3 | Import Excel (danh mục / tồn đầu kỳ / dòng phiếu) có dòng lỗi | BR-K14 — luôn **xem trước rồi mới ghi** | Từng dòng lỗi nêu đủ mọi lý do, sửa tại chỗ trên màn preview; dòng lỗi không khoá vĩnh viễn nút Lưu nháp | Hiện có |
| NL-4.4 | Nhập tồn đầu kỳ lần thứ hai | Quy tắc BR-K21 [MỚI]: tồn đầu kỳ chỉ nhập **một lần** cho mỗi kho | Chặn kèm hướng dẫn: sai lệch sau này xử lý bằng phiếu "Điều chỉnh kiểm kê", không nhập lại tồn đầu | **MỚI** |
| NL-4.5 | Tạo vật tư trùng (tên gần giống vật tư đã có) | So khớp gần đúng tên khi lưu | Cảnh báo mềm liệt kê vật tư giống, cho phép tiếp tục (không chặn cứng) — giảm rác danh mục | **MỚI** |
| NL-4.6 | Kiểm kê phát hiện chênh lệch tồn thực tế | Đối chiếu thủ công định kỳ | Lập phiếu "Điều chỉnh kiểm kê" (nhập nếu thừa [MỚI], xuất nếu thiếu [Hiện có]) kèm ghi chú; không sửa phiếu quá khứ | Hiện có, mở rộng |
| NL-4.7 | Ngày phiếu trước `ngay_bat_dau` của kho | BR-K10 | Chặn | Hiện có |
| NL-4.8 | Kho bị tắt (`active = 0`) | BR-K1 | Cổng không truy cập được phần kho; phiếu tự sinh dừng; dữ liệu giữ nguyên | Hiện có |
| NL-4.9 | Xuất **sử dụng** một lô đã quá hạn dùng | BR-K20 so `han_su_dung` với ngày phiếu | Cảnh báo bắt xác nhận thêm ("lô đã hết hạn — vẫn xuất sử dụng?"), khuyến nghị chuyển "Xuất huỷ - hết hạn"; không chặn cứng vì có tình huống dùng nội bộ hợp lệ | **MỚI** |
| NL-4.10 | Sửa/xoá phiếu **đã ghi sổ** | Cơ chế docstatus | Không sửa được; con đường duy nhất là huỷ → phiếu đảo (QT5) rồi lập phiếu mới | Hiện có |
| NL-4.11 | Kho bật "bắt buộc khoa phòng" nhưng phiếu Xuất sử dụng chưa chọn khoa | BR-CP2 tại `before_submit` | Chặn ghi sổ, nêu rõ; **chỉ áp cho phiếu tạo sau khi bật cờ** — phiếu nháp tồn trước đó vẫn ghi sổ được (tránh khoá tồn đọng) | **MỚI** |
| NL-4.12 | Khoa phòng bị tắt (`active = 0`) còn nằm trên phiếu nháp | Kiểm khi ghi sổ | Cảnh báo yêu cầu chọn lại khoa đang hoạt động; khoa đã dùng trên phiếu không xoá được, chỉ tắt (BR-CP1) | **MỚI** |
| NL-4.13 | Tạo khoa phòng trùng tên gần giống | So gần đúng trong kho | Gợi ý chọn khoa có sẵn; trùng tuyệt đối → chặn | **MỚI** |

### 4.5 QT5 — Huỷ phiếu đã ghi sổ → phiếu đảo **[Hiện có]**

Quy tắc kế toán nền tảng của sổ kho: **không dòng sổ nào bị xoá.**

```
Huỷ phiếu đã ghi sổ
   ├─ before_cancel: chặn nếu phiếu này CHÍNH LÀ phiếu đảo      (BR-K7)
   ├─ before_cancel: chặn nếu hàng của lô đó đã bị xuất mất rồi (BR-K8)
   └─ on_cancel:
        ├─ sinh MỘT phiếu đảo mới, đã ghi sổ, số lượng ngược dấu
        └─ đánh dấu các dòng sổ gốc `da_dao = 1`
```

**Luồng ngoại lệ QT5** (chính là các chốt chặn của luồng):

| Mã | Tình huống | Chốt chặn | Xử lý | Nhãn |
|---|---|---|---|---|
| NL-5.1 | Huỷ một phiếu đảo | BR-K7 | Chặn tuyệt đối — phiếu đảo tồn tại để bù trừ, huỷ nó là vòng lặp không lối ra | Hiện có |
| NL-5.2 | Huỷ phiếu nhập khi hàng của lô đã bị xuất | BR-K8 — cộng dồn theo (vật tư, lô) trước khi so | Chặn, nêu rõ lô còn bao nhiêu / phiếu đã nhập bao nhiêu; yêu cầu huỷ phiếu xuất tương ứng trước | Hiện có |
| NL-5.3 | Người dùng tự tạo phiếu loại "Phiếu đảo" bằng tay | BR-K9 — chỉ chấp nhận cờ bộ nhớ `flags.dang_tao_dao` | Chặn; mọi điều kiện dựa trên giá trị field đều giả được từ ngoài (đã từng có sự cố thật) | Hiện có |
| NL-5.4 | Đảo một phiếu nhập có nhiều mức giá trong cùng lô | BR-K6 — bình quân gia quyền tính lại cả khi delta âm | Phiếu đảo mang đúng giá phiếu gốc; bỏ qua bước tính lại sẽ làm giá trị sổ lệch vĩnh viễn (đã đo: 352.941 VND sinh từ hư không) | Hiện có |

### 4.6 QT6 — Hoá đơn và công nợ **[Hiện có, mở rộng]**

Miyano lập `Sales Invoice` trên Desk → ghi sổ → email "Portal - Hoá đơn phát hành" → khách xem
trên `/portal/invoices` với trạng thái Việt hoá và số dư còn phải trả (`outstanding_amount`).
Cổng không thu tiền, không sinh chứng từ thanh toán. **[MỚI]** Hoá đơn điện tử (XML gốc, PDF,
mã tra cứu) hiển thị và tải theo **QT12**.

**Luồng ngoại lệ QT6:**

| Mã | Tình huống | Chốt chặn / phát hiện | Xử lý | Nhãn |
|---|---|---|---|---|
| NL-6.1 | Hoá đơn phát hành sai (giá, số lượng, thông tin) | Khách phản hồi qua yêu cầu hỗ trợ / sales phát hiện | Miyano Cancel/Amend `Sales Invoice` theo chuẩn ERPNext; cổng tự phản ánh bản mới; bản huỷ hiển thị trạng thái "Đã huỷ" | Hiện có (cơ chế ERPNext) |
| NL-6.2 | Trả hàng đã xuất hoá đơn | Sales Return → Credit Note | Cổng hiển thị hoá đơn điều chỉnh (giá trị âm/đối trừ) trong danh sách, trạng thái "Trả hàng"; công nợ giảm tương ứng | Hiện có (trạng thái) + hiển thị đối trừ [MỚI] |
| NL-6.3 | Hoá đơn quá hạn thanh toán | `due_date` < hôm nay và `outstanding_amount > 0` | Badge "Quá hạn" đỏ; thẻ "Quá hạn thanh toán" trên Dashboard và màn hoá đơn; danh sách hoá đơn đến hạn trong 7 ngày | Hiện có (badge) + thẻ nhắc [MỚI] |
| NL-6.4 | Khách thắc mắc chênh lệch công nợ | Đối chiếu lịch sử thanh toán | Màn chi tiết hoá đơn liệt kê các `Payment Entry` đã đối trừ (số phiếu, ngày, số tiền) | **MỚI** |

### 4.7 QT7 — Nhập hàng mua ngoài từ NCC khác **[MỚI]**

Khách hàng mua vật tư từ nhiều nhà cung ứng. Mọi đợt hàng về kho — dù của ai — đều phải vào
**cùng một sổ kho** thì tồn mới đúng và dữ liệu tiêu thụ mới đủ để dự trù. NCC khác không có
tài khoản trên cổng; họ chỉ là danh mục dữ liệu.

**Luồng chính:**

```
Thủ kho nhận hàng từ NCC khác (kèm hoá đơn / phiếu giao của NCC)
   → Lập phiếu nhập:  loai_nhap = "Mua ngoài (NCC khác)"
        ├─ chọn NCC từ danh mục NCC của kho (tạo nhanh tại chỗ nếu chưa có)
        ├─ nhập số chứng từ NCC + ngày chứng từ (khuyến nghị — BR-N2)
        └─ dòng hàng: vật tư, số lô, hạn dùng, SL, đơn giá, ĐVT
   → Lưu nháp → kiểm hàng thực tế → Ghi sổ
   → Sổ kho ghi nhận như mọi phiếu nhập khác; đợt hàng mang nguồn "NCC khác"
```

**Luồng ngoại lệ QT7:**

| Mã | Tình huống | Chốt chặn / phát hiện | Xử lý | Nhãn |
|---|---|---|---|---|
| NL-7.1 | Chọn loại "Mua ngoài" nhưng không chọn NCC | BR-N1 | Chặn lưu — thiếu NCC thì số liệu nguồn cung vô nghĩa | MỚI |
| NL-7.2 | Thiếu số chứng từ NCC lúc nhận hàng | BR-N2 | **Không chặn** (thực tế thủ kho có thể chưa cầm hoá đơn); phiếu gắn cờ "thiếu chứng từ" để bổ sung sau; danh sách phiếu lọc được theo cờ này | MỚI |
| NL-7.3 | Tạo NCC trùng tên NCC đã có | So khớp gần đúng tên trong kho (unique theo (kho, tên)) | Cảnh báo gợi ý chọn NCC có sẵn; trùng tuyệt đối thì chặn | MỚI |
| NL-7.4 | Vật tư NCC giao chưa có trong danh mục kho | Danh mục vật tư của kho | Tạo nhanh vật tư ngay trong phiếu (vật tư riêng của khách, `item_code` rỗng — BR-K3) | Hiện có (cơ chế) |
| NL-7.5 | Nhập nhầm đơn giá / SL, phát hiện sau ghi sổ | Cơ chế docstatus | Huỷ phiếu → phiếu đảo (QT5) → lập phiếu mới đúng | Hiện có |

### 4.8 QT8 — Nhật ký vật tư & kiểm soát NXT theo từng đợt hàng **[MỚI]**

**Định nghĩa "đợt hàng":** một **phiếu nhập đã ghi sổ** là một đợt nhận (bất kể nguồn: Miyano,
NCC khác, tồn đầu kỳ, điều chỉnh). Mã phiếu nhập chính là mã đợt. Với đơn Miyano giao nhiều lần,
mỗi `Delivery Note` → một phiếu nhập → **một đợt riêng** (khớp QT3).

**Hai công cụ kiểm soát:**

1. **Nhật ký vật tư (log)** — màn hình chỉ đọc, dựng trực tiếp từ sổ kho
   (`Customer Stock Ledger Entry` — nguồn sự thật, append-only):

```
Chọn vật tư (+ lọc kỳ, lô, loại phiếu, nguồn)
   → bảng thời gian đầy đủ mọi biến động:
     ngày · phiếu · loại (nhập/xuất) · nguồn/NCC · đợt · lô · hạn dùng
     · SL nhập · SL xuất · đơn giá · TỒN SAU GIAO DỊCH (luỹ kế) · người ghi sổ
   → dòng bị đảo hiển thị mờ + nhãn "đã đảo" (da_dao = 1), không giấu
   → bấm vào phiếu → mở đúng phiếu gốc; xuất Excel toàn nhật ký
```

2. **Báo cáo NXT theo đợt hàng** — trả lời "đợt hàng này về, đã dùng hết chưa, còn bao nhiêu,
   nằm kho bao lâu":

| Cột | Nguồn |
|---|---|
| Mã đợt (phiếu nhập), ngày nhận, nguồn (Miyano / NCC nào), số chứng từ, số đơn hàng | Phiếu nhập |
| Vật tư, lô, hạn dùng, SL nhập, đơn giá, giá trị nhập | Dòng phiếu |
| **SL đã xuất** phân bổ cho đợt, **SL còn lại** của đợt | Phân bổ FIFO trong từng (vật tư, lô) — BR-D1 |
| Tuổi tồn (ngày từ ngày nhận), % đã tiêu thụ | Tính |
| Cờ chậm luân chuyển (tuổi tồn > ngưỡng cấu hình, mặc định 90 ngày) | Tính |

**Quy tắc phân bổ (BR-D1):** mức theo dõi vật lý của sổ là **(vật tư, lô)**. Khi cùng một lô được
nhận ở nhiều đợt, số xuất được **phân bổ cho đợt cũ trước (FIFO)** trong phạm vi lô đó. Đây là quy
ước phân tích, không phải bút toán — sổ kho không đổi.

**Luồng ngoại lệ QT8:**

| Mã | Tình huống | Xử lý | Nhãn |
|---|---|---|---|
| NL-8.1 | Cùng số lô nhận từ 2 NCC khác nhau | Vẫn tách được theo đợt (đợt mang NCC); phân bổ xuất theo FIFO trong lô — báo cáo ghi chú rõ giới hạn này | MỚI |
| NL-8.2 | Đợt có phiếu bị đảo | SL nhập của đợt trừ phần đã đảo; nhật ký hiển thị cả dòng gốc (mờ) lẫn dòng đảo | MỚI |
| NL-8.3 | Dữ liệu nhật ký quá dài (kho lâu năm) | Phân trang phía máy chủ + bắt buộc chọn kỳ khi xuất Excel | MỚI |

### 4.9 QT9 — Dự trù vật tư & vòng lặp Just-in-Time **[MỚI]**

Mục đích cuối của toàn bộ dữ liệu: **đặt đúng thứ cần, đúng lúc, đúng số lượng.** Vòng lặp:

```
Tiêu thụ thật (phiếu XUẤT SỬ DỤNG, mọi nguồn hàng)
   → hệ thống tính ADU (mức dùng bình quân/ngày, kỳ trượt 90 ngày — BR-P1)
   → gợi ý cho từng vật tư:  min = tồn an toàn,  ROP = ADU × lead time + tồn an toàn,
     max = ROP + lượng đặt kinh tế         (khách chỉnh tay được — BR-P2)
   → tồn khả dụng < min hoặc < ROP  ──►  CẢNH BÁO THIẾU TỒN trên cổng
        ├─ vật tư CÓ trong hợp đồng khung Miyano → nút "Thêm vào giỏ bổ sung" điền sẵn
        │  số lượng gợi ý = max − tồn hiện tại (làm tròn theo bội số) → QT1
        └─ vật tư ngoài hợp đồng khung → cảnh báo + nút "Nhờ Miyano tìm nguồn" → tạo yêu cầu
           hàng hoá điền sẵn tên/quy cách/ĐVT/SL gợi ý (QT11) — đường chuyển dần
           share-of-wallet về Miyano
   → PHÍA MIYANO (Desk): báo cáo tiêu thụ theo khách/vật tư · ngày phủ tồn
     · dự báo ngày hết hàng · tỷ trọng Miyano vs NCC khác (share-of-wallet)
     · ĐỀ XUẤT DỰ TRÙ tổng hợp → kế hoạch mua/tồn của Miyano → giao Just-in-Time
```

**Luồng ngoại lệ QT9:**

| Mã | Tình huống | Xử lý | Nhãn |
|---|---|---|---|
| NL-9.1 | Vật tư chưa đủ dữ liệu (< 30 ngày ghi nhận xuất) | Không tự cảnh báo (BR-P3); màn thiết lập ghi "chưa đủ dữ liệu — nhập min/max tay nếu cần" | MỚI |
| NL-9.2 | Tiêu thụ đột biến (dịch, chiến dịch) làm ADU nhiễu | ADU dùng kỳ trượt + hiển thị cả ADU 30/90 ngày để người dùng đối chiếu; min/max do người chốt, hệ thống chỉ gợi ý | MỚI |
| NL-9.3 | Khách không cập nhật phiếu xuất (dữ liệu chết) | Báo cáo Desk "kho không hoạt động" (không có phiếu xuất N ngày) để sales nhắc khách — dữ liệu xấu thì dự trù sai | MỚI |
| NL-9.4 | Xuất huỷ/trả lại/điều chỉnh lẫn vào tiêu thụ | BR-P1: ADU **chỉ** tính từ "Xuất sử dụng", loại trừ phiếu đảo và dòng `da_dao` | MỚI |
| NL-9.5 | Khách phản đối việc Miyano xem dữ liệu mua ngoài | Điều khoản chia sẻ dữ liệu trong hợp đồng dịch vụ kho (VĐ-10); phạm vi Miyano xem được ghi rõ ở mục 8 | MỚI |

### 4.10 QT10 — Mua lẻ ngoài hợp đồng khung **[MỚI — THIẾT KẾ LẠI 2026-08-15]**

> Bản mô tả dưới đây thay bản gốc (hai nhánh A/B qua `Portal Item Request`) — xem
> `CHANGELOG-khac-phuc-BA-v2.md` §2026-08-15 và `DevHandoff/15_PRD_E6_MuaLe.md` cho đầy đủ AC/luồng.
> Lý do đổi: nhánh A (danh mục tuyển chọn có giá thẳng) buộc khách phải biết trước Miyano có mặt
> hàng gì; nhánh B (mọi trường hợp thiếu giá đều thành `Portal Item Request` — một chứng từ khác,
> một màn khác) làm khách rời khỏi phiếu đang mở giữa chừng. Bản mới: **một** ngăn Mua lẻ duy nhất,
> danh mục là toàn bộ Item, không hiện giá, không cần biết mã hàng.

Không phải nhu cầu nào cũng nằm trong hợp đồng khung: phòng khám/PXN tư mua theo nhu cầu phát sinh,
bệnh viện cần gấp mặt hàng ngoài phụ lục. Mua lẻ **mặc định BẬT** cho mọi khách (đổi từ mặc định tắt
— patch `v1_15.bat_mua_le_mac_dinh`); sales vẫn tắt được cho một khách cụ thể (nợ quá hạn, chỉ cho
mua theo hợp đồng) — đổi giá trị mặc định, không bỏ chốt `BR-R1` ở server.

**Luồng chính:**

```
Khách vào ngăn "Mua lẻ" (luôn hiện, trừ khi sales tắt cờ cho khách đó)
   → danh mục = TOÀN BỘ Item đang hoạt động (không còn lọc custom_ban_le_portal), phân trang
     server-side, tìm không dấu, KHÔNG hiện đơn giá
   → item đang thuộc hợp đồng khung còn hiệu lực → dòng mờ, badge "Có trong hợp đồng khung — đặt ở
     chế độ Theo hợp đồng khung" (chống né hạn mức, NL-10.7)
   → tìm không ra mã → khối "Không tìm thấy vật tư cần mua?" tự mở, prefill từ khoá, khách gõ thẳng
     Tên hàng/ĐVT/SL — KHÔNG rời phiếu, không tạo chứng từ khác
   → thêm vào GIỎ MUA LẺ — ngăn giỏ riêng, không trộn với giỏ hợp đồng khung (BR-R2)
   → đặt hàng ──► portal_order_place (mode = ban_le, tham số dat_ngoai cho dòng chưa có mã)
                    ├─ KHÔNG kiểm hạn mức, KHÔNG gắn Blanket Order            (BR-R4)
                    ├─ dòng có mã: rate = 0, sales điền giá khi báo giá       (BR-R3, sửa 15/08)
                    ├─ dòng chưa có mã: lưu bảng con custom_dat_ngoai, không phải Sales Order Item
                    ├─ vẫn kiểm: sở hữu địa chỉ, bội số, ngày giao, request_id
                    └─ Sales Order NHÁP, custom_loai_don = "Mua lẻ"
   → sales điền giá + khớp mã dòng đặt ngoài trên Desk → "Chờ khách đồng ý" (QĐ-6) — khách thấy giá,
     hạn hiệu lực báo giá, tải được PDF báo giá (mẫu in "Miyano - Báo giá")
        ├─ khách bấm Đồng ý trên cổng (log người bấm + thời điểm) → Chờ Miyano xác nhận → QT2
        ├─ khách Không đồng ý (kèm lý do) → về sales sửa giá hoặc huỷ nháp
        └─ quá hạn hiệu lực (Settings.hieu_luc_bao_gia_ngay, mặc định 7 ngày) → tự đóng + email
   → luôn qua Miyano xác nhận (QT2) + duyệt ngưỡng BR-O9 → giao (QT3) → hoá đơn (QT6/QT12)
```

**Luồng ngoại lệ QT10:**

| Mã | Tình huống | Chốt chặn / phát hiện | Xử lý | Nhãn |
|---|---|---|---|---|
| NL-10.1 | Khách không được bật mua lẻ nhưng gọi API mua lẻ | `custom_cho_phep_mua_le` kiểm phía server | Trả 403; UI không hiển thị chế độ Mua lẻ ngay từ đầu | MỚI |
| NL-10.2 | *(gỡ 15/08 — danh mục không còn hiện giá nên không còn "item thiếu giá" ở màn danh mục; mọi dòng đều rate=0 chờ báo giá)* | — | — | — |
| NL-10.3 | Khách cố trộn hàng hợp đồng khung và mua lẻ vào một đơn | BR-R2 — hai ngăn giỏ, hai đơn | Không xảy ra theo thiết kế; server từ chối dòng sai loại | MỚI |
| NL-10.4 | Khách không đồng ý giá báo | Nút "Không đồng ý" + lý do bắt buộc | Đơn về "Chờ xác nhận" cho sales sửa; lý do lưu vào đơn | MỚI |
| NL-10.5 | Đơn "Chờ khách đồng ý" quá hạn hiệu lực báo giá | Job nền so ngày; **chỉ áp cho đơn Mua lẻ** (đơn hợp đồng khung ở luồng E2 gốc không có hiệu lực N ngày) | Tự đóng (huỷ nháp) + email hai phía | MỚI |
| NL-10.6 | Đơn mua lẻ giá trị lớn | BR-O9 dùng chung | Từ ngưỡng trở lên bắt buộc Sales Manager duyệt | MỚI |
| NL-10.7 | Khách lạm dụng mua lẻ để né hạn mức hợp đồng khung (cùng mặt hàng có trong hợp đồng khung) | So `item_code` với danh mục hợp đồng khung còn hiệu lực khi đặt lẻ | Mặt hàng đã thuộc hợp đồng khung còn hiệu lực → **không cho mua lẻ**, hướng về giỏ hợp đồng khung (giá hợp đồng khung thường tốt hơn; hạn mức phải được tiêu đúng chỗ) | MỚI |

### 4.11 QT11 — Yêu cầu hàng hoá & tìm nguồn cung **[MỚI — DESK-ONLY, đổi 2026-08-15]**

> **Không còn lối vào từ cổng khách.** Cả ba đường vào của khách mô tả bên dưới đã bị gỡ khỏi
> `/portal` (kế hoạch 2026-08-15, Task 1–2): nút "Gửi yêu cầu" ở danh mục và ở màn dự trù không còn;
> nhánh "Mua lẻ thiếu giá → Báo giá mua lẻ" không còn tồn tại (QT10 thiết kế lại không còn khái niệm
> "danh mục có giá" để thiếu — xem §4.10). Thay các đường vào đó: khối "hàng chưa có mã" ngay trên
> phiếu Mua lẻ (§4.10, `Sales Order Dat Ngoai Item`) — khách gõ thẳng, không cần biết mã hàng, không
> rời phiếu. `Portal Item Request` và toàn bộ mục dưới đây **vẫn đúng và vẫn chạy**, nhưng chỉ còn là
> quy trình nội bộ: nhân viên Miyano tạo/xử lý yêu cầu **trên Desk** (điện thoại, Zalo, email khách
> gửi trực tiếp cho sales…), không phải khách tự thao tác trên cổng nữa.

Bắt trọn nhu cầu ngoài danh mục: hàng **ngoài Blanket Order**, thậm chí **chưa có Item trong ERPNext
của Miyano**. Mỗi nhu cầu là một bản ghi `Portal Item Request` — purchasing có hàng đợi tìm nguồn
tập trung, và Miyano có số liệu **demand pipeline** (nhu cầu chưa được đáp ứng) để quyết định mở
rộng danh mục.

**Luồng chính (nội bộ, Desk):**

```
Nhân viên Miyano tạo Yêu cầu hàng hoá trên Desk (thay mặt khách gọi điện/Zalo/email)
   (loại · tên hàng · quy cách · ĐVT · SL dự kiến · tần suất · ngày cần · hãng/xuất xứ · đính kèm)
   → trạng thái MỚI ──► notification: sales phụ trách + bộ phận mua hàng; SLA 48h làm việc (BR-Y1)
   → Miyano xử lý trên Desk:
        ├─ hàng ĐÃ có Item + giá → phản hồi "Đã có hàng":
        │    thêm Item Price / Party Specific Item, hoặc trình phụ lục bổ sung hợp đồng khung
        │    → khách đặt được ngay theo QT1, hoặc đặt qua ngăn Mua lẻ (§4.10)
        ├─ hàng CHƯA có Item → purchasing tìm nguồn:
        │    trạng thái "Đang tìm nguồn" → tạo Item mới (qua chuẩn hoá mã/tên/ĐVT — BR-Y3)
        │    + Item Price → phản hồi "Đã báo giá" kèm giá + lead time
        │    → (tuỳ chọn) lập luôn SO nháp Mua lẻ "Chờ khách đồng ý" (§4.10)
        └─ không tìm được nguồn phù hợp → "Không đáp ứng được" + lý do bắt buộc (BR-Y2)
   → mọi đổi trạng thái: email cho khách (khách KHÔNG còn xem/bổ sung thông tin trên cổng — trả lời
     qua email hoặc liên hệ nhân viên phụ trách); huỷ được khi chưa kết thúc, thao tác trên Desk
```

**Trạng thái yêu cầu:** Mới → Đang tìm nguồn → Cần thêm thông tin ⇄ → Đã báo giá / Đã có hàng →
Đã chuyển thành đơn · Không đáp ứng được · Khách huỷ · Hết hạn. Không trạng thái nào bị xoá (BR-Y4).

**Luồng ngoại lệ QT11:**

| Mã | Tình huống | Chốt chặn / phát hiện | Xử lý | Nhãn |
|---|---|---|---|---|
| NL-11.1 | Gửi trùng yêu cầu cho hàng đang có yêu cầu mở | So gần đúng tên hàng trong yêu cầu đang mở của khách | Cảnh báo "đã có yêu cầu {mã} đang xử lý", vẫn cho gửi nếu cố ý | MỚI |
| NL-11.2 | Quá SLA chưa ai phản hồi | Job nền quét | Leo thang Sales Manager; hiện trong báo cáo yêu cầu chậm | MỚI |
| NL-11.3 | Thông tin không đủ để tìm nguồn | Người xử lý chuyển "Cần thêm thông tin" kèm câu hỏi | Khách nhận email; trả lời qua email hoặc liên hệ nhân viên phụ trách — **không còn màn "chi tiết yêu cầu" trên cổng để bổ sung trực tiếp** (đổi 15/08, xem CHANGELOG) | MỚI, Desk-only |
| NL-11.4 | Item mới đặt mã/ĐVT/nhóm sai chuẩn | BR-Y3 — bước chuẩn hoá dữ liệu trước khi mở bán | Purchasing đề xuất, người giữ chuẩn dữ liệu duyệt; không mở bán item chưa chuẩn | MỚI |
| NL-11.5 | Khách huỷ sau khi Miyano đã báo giá | Nút huỷ + lý do | Đóng "Khách huỷ", giữ lịch sử — dữ liệu cho tỷ lệ chuyển đổi và đánh giá giá cạnh tranh | MỚI |
| NL-11.6 | Đính kèm quá cỡ / sai định dạng | ≤ 5 file, mỗi file ≤ 10MB, pdf/jpg/png/xlsx | Chặn ngay tại chỗ, nêu giới hạn | MỚI |
| NL-11.7 | Nhu cầu định kỳ (không phải mua một lần) | Trường `tan_suat = "Định kỳ"` | Phản hồi kèm đề xuất đưa vào hợp đồng khung kỳ tới; báo cáo demand pipeline tách nhóm định kỳ — đầu vào đàm phán hợp đồng | MỚI |

### 4.12 QT12 — Hoá đơn điện tử trên cổng **[MỚI]**

Team Dev đã có tính năng phát hành HĐĐT từ ERPNext. Cổng **chỉ đọc** kết quả (BR-E5) và cho khách
tự tải chứng từ — theo NĐ 123/2020 và TT 78/2021: **file XML là bản gốc có giá trị pháp lý,
PDF là bản thể hiện**, tra cứu bằng mã trên hệ thống của cơ quan thuế.

**Hợp đồng dữ liệu (data contract)** giữa cổng và module HĐĐT đặt tại mục 7.3 — tên trường là
**tên tạm**, phải đối chiếu với module thực tế của team Dev trước khi code (VĐ-11).

**Luồng chính:**

```
Kế toán ghi sổ Sales Invoice → module HĐĐT phát hành (ký số, cấp mã CQT)
   → module cập nhật trường HĐĐT + đính file XML/PDF (private file) lên SI
   → sự kiện "HĐĐT đã phát hành" ──► email cho khách: số HĐĐT + ký hiệu + link vào cổng
   → cổng /portal/invoices — khối HĐĐT trên từng hoá đơn:
        trạng thái · số + ký hiệu · ngày phát hành · mã tra cứu (copy được)
        · nút tải XML (bản gốc) · nút tải PDF (bản thể hiện) · link tra cứu CQT
   → tải qua portal_einvoice_download: kiểm phiên + sở hữu TỪNG LẦN, đọc private file,
     ghi log ai tải lúc nào (BR-E4)
```

**Luồng ngoại lệ QT12:**

| Mã | Tình huống | Chốt chặn / phát hiện | Xử lý | Nhãn |
|---|---|---|---|---|
| NL-12.1 | SI đã ghi sổ nhưng HĐĐT chưa phát hành (chờ ký số / lỗi kết nối NCC HĐĐT) | `einvoice_trang_thai ≠ "Đã phát hành"` | Khối HĐĐT hiển thị "Đang phát hành HĐĐT", không có nút tải (BR-E2); công nợ vẫn hiển thị bình thường | MỚI |
| NL-12.2 | HĐĐT bị huỷ (sai sót, lập hoá đơn thay thế) | Trạng thái "Đã huỷ" / "Bị thay thế" từ module | Badge rõ ràng + liên kết sang hoá đơn thay thế; hoá đơn cũ không bị giấu (BR-E3) | MỚI |
| NL-12.3 | HĐĐT điều chỉnh tăng/giảm | Trạng thái "Bị điều chỉnh" + SI điều chỉnh trỏ về gốc | Hai chiều liên kết gốc ⇄ điều chỉnh hiển thị trên cả hai dòng | MỚI |
| NL-12.4 | File XML/PDF thiếu hoặc hỏng | Endpoint đọc file thất bại | Nút tải disable + thông điệp; nút "Yêu cầu hỗ trợ" tự đính mã hoá đơn; notification nội bộ cho kế toán | MỚI |
| NL-12.5 | Chia sẻ URL tải cho người ngoài | BR-E4 — không có URL công khai | Mỗi lần tải kiểm phiên + sở hữu; link dán sang máy khác không đăng nhập → 403 | MỚI |
| NL-12.6 | Khách cần hoá đơn cũ trước khi có tính năng này | Dữ liệu lịch sử | Backfill: job một lần quét SI cũ có HĐĐT, đổ đủ khối HĐĐT cho hoá đơn lịch sử | MỚI |

---

## 5. Danh mục ca sử dụng

UC-01…UC-41 giữ nguyên từ bản as-built **[Hiện có]**; các UC mới đánh dấu **[MỚI]**.

### 5.1 Nhóm mua hàng

| Mã | Ca sử dụng | Màn hình | Endpoint | Nhãn |
|---|---|---|---|---|
| UC-01 | Đăng nhập cổng | `/portal/login` | trang web riêng, không qua SPA | Hiện có |
| UC-02 | Xem tổng quan | `/portal/dashboard` | `portal_me`, `portal_order_history`, `portal_invoices` | Hiện có |
| UC-03 | Xem hợp đồng khung và hạn mức còn lại | `/portal/catalog` | `portal_contracts` | Hiện có |
| UC-04 | Xem danh mục hàng theo hợp đồng, có giá riêng | `/portal/catalog` | `portal_catalog` | Hiện có |
| UC-05 | Đặt hàng từ giỏ | `/portal/cart` | `portal_order_place` (+ `request_id` [MỚI]) | Hiện có, mở rộng |
| UC-06 | Xem lịch sử đơn hàng | `/portal/orders` | `portal_order_history` | Hiện có |
| UC-07 | Theo dõi tiến độ một đơn — gồm **danh sách các đợt giao** | `/portal/orders/:name` | `portal_order_track` | Hiện có, mở rộng |
| UC-08 | Xem phiếu giao hàng | `/portal/orders/:name` | `portal_deliveries` | Hiện có |
| UC-09 | Xem hoá đơn và công nợ | `/portal/invoices` | `portal_invoices` | Hiện có |
| UC-10 | Gửi yêu cầu huỷ đơn | `/portal/orders/:name` | `portal_request_cancel` | Hiện có |
| UC-11 | Tải chứng từ PDF (đơn / phiếu giao / hoá đơn) | nhiều màn | `portal_document_download` | Hiện có |
| UC-12 | Xem hồ sơ đơn vị | `/portal/profile` | `portal_me` | Hiện có |
| UC-13 | Cấp tài khoản cổng cho khách *(nhân viên Miyano)* | Desk | `portal_provision` | Hiện có |
| UC-14 | **Đặt lại nhanh theo đơn cũ (re-order)**: điền lại giỏ theo đơn đã chọn, giá hiện hành; mặt hàng hết hạn mức/ngoài hợp đồng khung bị loại kèm thông báo | `/portal/orders/:name` | `portal_reorder` | **MỚI** |
| UC-15 | **Đặt mua lẻ ngoài hợp đồng khung** (mặc định bật): danh mục = toàn bộ Item, KHÔNG hiện giá, giỏ riêng, không hạn mức; gõ thẳng tên hàng khi không tìm ra mã (§4.10, sửa 15/08) | `/portal/catalog` (chế độ Mua lẻ) | `portal_catalog_ban_le`, `portal_order_place` (tham số `dat_ngoai`) | **MỚI** |
| UC-16 | ~~Gửi yêu cầu hàng hoá qua màn riêng~~ **[DESK-ONLY, đổi 15/08]** — không còn route cổng; thay bằng khối "hàng chưa có mã" ngay trên phiếu Mua lẻ (UC-15). `portal_yeu_cau_save` đã xoá khỏi API cổng; `Portal Item Request` vẫn tạo được trên Desk | — | Desk: tạo trực tiếp doctype `Portal Item Request` | **MỚI, Desk-only** |
| UC-17 | ~~Theo dõi yêu cầu hàng hoá trên cổng~~ **[DESK-ONLY, đổi 15/08]** — không còn route/endpoint cổng (`portal_yeu_cau_list`/`portal_yeu_cau_cancel` đã xoá). "Đồng ý/Không đồng ý" báo giá **vẫn trên cổng**, nhưng nay thuộc đơn Mua lẻ (§4.10), không còn gắn với `Portal Item Request` | `/portal/orders/:name` (chỉ phần Đồng ý/Không đồng ý) | `portal_order_accept` | **MỚI, Desk-only** |
| UC-18 | **Tải hoá đơn điện tử**: XML gốc + PDF, mã tra cứu, link tra cứu CQT | `/portal/invoices` | `portal_einvoice_download` | **MỚI** |

### 5.2 Nhóm kho khách hàng

| Mã | Ca sử dụng | Màn hình | Endpoint | Nhãn |
|---|---|---|---|---|
| UC-20 | Xem thông tin kho của mình | `/portal/kho` | `kho_me` | Hiện có |
| UC-21 | Xem tồn kho theo vật tư | `/portal/kho` | `kho_ton` | Hiện có |
| UC-22 | Xem tồn theo lô của một vật tư | `/portal/kho` | `kho_lo` | Hiện có |
| UC-23 | Xem / tìm danh mục vật tư | `/portal/kho/vat-tu` | `kho_vat_tu_list` | Hiện có |
| UC-24 | Thêm, sửa vật tư — gồm **min/max, lead time** [MỚI] | `/portal/kho/vat-tu` | `kho_vat_tu_tao`, `kho_vat_tu_sua` | Hiện có, mở rộng |
| UC-25 | Xuất danh mục vật tư ra Excel | `/portal/kho/vat-tu` | `kho_vat_tu_export` | Hiện có |
| UC-26 | Nhập danh mục vật tư từ Excel (xem trước → ghi) | `/portal/kho/vat-tu/import` | `kho_vat_tu_import_preview`, `kho_vat_tu_import_commit` | Hiện có |
| UC-27 | Nhập tồn đầu kỳ từ Excel (xem trước → ghi) | `/portal/kho/import` | `kho_import_template`, `kho_import_preview`, `kho_import_commit` | Hiện có |
| UC-28 | Xem danh sách phiếu nhập / phiếu xuất | `/portal/kho/nhap`, `/portal/kho/xuat` | `kho_phieu_list` | Hiện có |
| UC-29 | Lập / sửa phiếu nhập — gồm biến thể **mua ngoài** và **đối soát SL giao** [MỚI] | `/portal/kho/nhap/:name` | `kho_phieu_nhap_save`, `kho_phieu_get` | Hiện có, mở rộng |
| UC-30 | Lập / sửa phiếu xuất | `/portal/kho/xuat/:name` | `kho_phieu_xuat_save`, `kho_phieu_get` | Hiện có |
| UC-31 | Xem gợi ý lô theo FEFO khi xuất | `/portal/kho/xuat/:name` | `kho_lo_goi_y` | Hiện có |
| UC-32 | Ghi sổ phiếu | hai màn chi tiết | `kho_phieu_submit` | Hiện có |
| UC-33 | Huỷ phiếu đã ghi sổ (sinh phiếu đảo) | hai màn chi tiết | `kho_phieu_cancel` | Hiện có |
| UC-34 | Nhập bảng dòng phiếu từ Excel | hai màn chi tiết | `kho_dong_phieu_mau`, `kho_dong_phieu_doc_file` | Hiện có |
| UC-35 | Xuất bảng dòng phiếu ra Excel | hai màn chi tiết | `kho_dong_phieu_export` | Hiện có |
| UC-36 | In phiếu (PDF theo mẫu của kho) | hai màn chi tiết | `kho_phieu_pdf` | Hiện có |
| UC-37 | Báo cáo nhập–xuất–tồn theo kỳ | `/portal/kho/bao-cao` | `kho_bao_cao_nxt` | Hiện có |
| UC-38 | Thẻ kho một vật tư theo kỳ | `/portal/kho/bao-cao` | `kho_the_kho` | Hiện có |
| UC-39 | Cảnh báo hạn dùng (tách nhóm "không có hạn" — VĐ-2) | `/portal/kho/bao-cao` | `kho_canh_bao_han` | Hiện có, mở rộng |
| UC-40 | Xuất báo cáo ra Excel | `/portal/kho/bao-cao` | `kho_bao_cao_excel` | Hiện có |
| UC-42 | **Quản lý danh mục NCC của kho** (thêm / sửa / tắt) | `/portal/kho/ncc` | `kho_ncc_list`, `kho_ncc_save` | **MỚI** |
| UC-43 | **Xem nhật ký vật tư** (log biến động, lọc kỳ/lô/nguồn/đợt, xuất Excel) | `/portal/kho/nhat-ky` | `kho_nhat_ky` | **MỚI** |
| UC-44 | **Báo cáo NXT theo đợt hàng** (tiêu thụ, còn lại, tuổi tồn từng đợt) | `/portal/kho/bao-cao` | `kho_bao_cao_dot` | **MỚI** |
| UC-45 | **Xem cảnh báo thiếu tồn (dưới min/ROP) + tạo giỏ hàng bổ sung 1 chạm** | `/portal/kho/du-tru` | `kho_canh_bao_ton`, `portal_reorder` | **MỚI** |
| UC-46 | **Nhận gợi ý min/max/ROP từ dữ liệu tiêu thụ** rồi chốt bằng tay | `/portal/kho/du-tru` | `kho_min_max_goi_y` | **MỚI** |
| UC-47 | **Ghi nhận chênh lệch nhận hàng** trên phiếu nhập từ Miyano (SL thực nhận + lý do) | `/portal/kho/nhap/:name` | `kho_phieu_nhap_save` (mở rộng) | **MỚI** |
| UC-54 | **Quản lý danh mục khoa phòng của kho** (thêm / sửa / tắt) | `/portal/kho/khoa-phong` | `kho_khoa_phong_list`, `kho_khoa_phong_save` | **MỚI** |
| UC-55 | **Cấp phát theo khoa phòng / cá nhân** trên phiếu Xuất sử dụng (chọn khoa, ghi người nhận có gợi ý) | `/portal/kho/xuat/:name` | `kho_phieu_xuat_save` (mở rộng), `kho_nguoi_nhan_goi_y` | **MỚI** |
| UC-56 | **Báo cáo cấp phát theo khoa phòng** (kỳ · khoa · vật tư · SL · giá trị, drill xuống phiếu) | `/portal/kho/bao-cao` | `kho_bao_cao_cap_phat` | **MỚI** |

### 5.3 Nhóm Desk phía Miyano

| Mã | Ca sử dụng | Màn hình | Nhãn |
|---|---|---|---|
| UC-41 | Tra cứu kho khách (tồn, NXT, cảnh báo hạn) — workspace "Kho khách hàng" + 3 report | Desk | Hiện có |
| UC-48 | **Đối soát giao – nhận**: DN đã giao vs phiếu nhập khách đã ghi sổ, các dòng chênh lệch + lý do | Desk (report) | **MỚI** |
| UC-49 | **Báo cáo tiêu thụ & dự trù**: ADU theo khách/vật tư, ngày phủ tồn, dự báo ngày hết hàng, đề xuất dự trù tổng hợp | Desk (report) | **MỚI** |
| UC-50 | **Tỷ trọng nguồn cung (share-of-wallet)**: giá trị/SL nhập từ Miyano vs từng NCC khác theo kỳ | Desk (report) | **MỚI** |
| UC-51 | **Chất lượng dữ liệu**: dòng giao thiếu lô/hạn, kho không hoạt động, phiếu thiếu chứng từ | Desk (report) | **MỚI** |
| UC-52 | **Xử lý yêu cầu hàng hoá**: hàng đợi tập trung cho sales + purchasing — tiếp nhận, hỏi thêm thông tin, tìm nguồn, tạo Item (qua chuẩn hoá), báo giá, lập SO nháp từ yêu cầu | Desk (list + form `Portal Item Request`) | **MỚI, Desk-only** |
| UC-53 | **Báo cáo nhu cầu chưa đáp ứng (demand pipeline)**: yêu cầu theo trạng thái/khách/nhóm hàng, tỷ lệ chuyển thành đơn, thời gian xử lý, nhóm nhu cầu định kỳ đề xuất đưa vào hợp đồng khung | Desk (report) | **MỚI, Desk-only** |

---

## 6. Quy tắc nghiệp vụ

### 6.1 Đặt hàng (BR-O)

| Mã | Quy tắc | Nơi thực thi | Nhãn |
|---|---|---|---|
| BR-O1 | Chỉ đặt theo hợp đồng khung thuộc chính đơn vị mình; địa chỉ giao cũng phải thuộc đơn vị mình | `portal_order_place` | Hiện có |
| BR-O2 | Các dòng giỏ trùng mã hàng phải **gộp trước** khi kiểm hạn mức | `portal_order_place` | Hiện có |
| BR-O3 | Vượt hạn mức thì chặn, báo **tất cả** mã hàng sai một lần kèm số còn lại | `portal_order_place` | Hiện có |
| BR-O4 | Mỗi dòng xuất từ kho mặc định **của chính mặt hàng đó** | `_resolve_item_warehouse` | Hiện có |
| BR-O5 | Không có giá bán trong `Price List` của khách → chặn đặt | `portal_order_place` | Hiện có |
| BR-O6 | Hạn mức trừ theo `Blanket Order` (`against_blanket_order = 1`) — cơ chế gốc ERPNext | `portal_order_place` | Hiện có |
| BR-O7 | Trạng thái hiển thị suy từ `status` + `per_delivered` | `_so_status_vi` | Hiện có |
| BR-O8 | Khách không huỷ đơn, chỉ gửi yêu cầu huỷ kèm lý do | `portal_request_cancel` | Hiện có |
| BR-O9 | **Duyệt theo ngưỡng**: đơn `grand_total ≥` ngưỡng cấu hình → chỉ `Sales Manager` được Xác nhận/Từ chối; dưới ngưỡng → `Sales User`. Ngưỡng rỗng = một tầng | Điều kiện transition của Workflow | **MỚI** (QĐ-1) |
| BR-O10 | **Không giao vượt**: tổng luỹ kế SL giao ≤ SL đặt từng dòng; over-delivery allowance = 0 | Cấu hình ERPNext + validate DN | **MỚI** (QĐ-2) |
| BR-O11 | SL đặt phải là **bội số quy cách** nếu mặt hàng có khai bội số | Giỏ hàng (tức thời) + `portal_order_place` (chốt) | **MỚI** |
| BR-O12 | **Idempotency**: một `request_id` chỉ tạo tối đa một `Sales Order`; gửi lại trả về đơn đã tạo | `portal_order_place` | **MỚI** |
| BR-O13 | Ngày giao mong muốn: mặc định +2 ngày làm việc, không nhận ngày quá khứ | Giỏ hàng + `portal_order_place` | **MỚI** |
| BR-O14 | Từ chối đơn **bắt buộc có lý do**; lý do đi vào email cho khách | Workflow + Notification | **MỚI** |
| BR-O15 | **Hạn mức 0 = không giới hạn** (QĐ-8): dòng Blanket Order có qty = 0 → cổng hiển thị "Không giới hạn"; BR-O2/O3 chỉ áp cho dòng có hạn mức > 0; dòng SO tương ứng **không gắn** `against_blanket_order` (cơ chế gốc ERPNext sẽ coi 0 là cấm đặt) nhưng vẫn gắn `custom_hdnt` để truy vết và thống kê SL đã đặt; cảnh báo dùng ≥ 80% hạn mức bỏ qua dòng này; màn khai Blanket Order phía Desk hiển thị chú thích quy ước để tránh nhập nhầm 0 | `portal_catalog`, `portal_order_place` | **MỚI** |

### 6.2 Kho khách hàng (BR-K)

BR-K1…BR-K15 giữ nguyên **[Hiện có]** (một khách một kho; vật tư thuộc kho; sổ append-only là nguồn
sự thật, lot balance là cache; không tồn âm; đơn giá theo lô + bình quân gia quyền tính cả delta âm;
huỷ → phiếu đảo, phiếu đảo không huỷ được; chặn đảo làm âm tồn — cộng dồn theo (vật tư, lô); chỉ hệ
thống tạo phiếu đảo qua `flags.dang_tao_dao`; ngày phiếu ≥ `ngay_bat_dau`; một DN một phiếu nhập;
móc không ném lỗi; FEFO chỉ gợi ý; import luôn xem trước; mẫu in chọn theo kho). Bổ sung:

| Mã | Quy tắc | Nơi thực thi | Nhãn |
|---|---|---|---|
| BR-K16 | Mỗi DN = **một đợt nhận riêng**; phiếu nhập tự sinh mang `so_dot` = thứ tự DN đã ghi sổ trong phạm vi SO | `delivery_hook` | **MỚI** |
| BR-K17 | Phiếu nhập nguồn Miyano: `so_luong` (thực nhận) ≤ `sl_giao` từng dòng; mọi dòng lệch **bắt buộc lý do**; phiếu lệch gắn cờ `co_chenh_lech` và phát notification cho sales | `validate` + `before_submit` phiếu nhập | **MỚI** |
| BR-K18 | Phiếu "Mua ngoài (NCC khác)": bắt buộc chọn NCC (BR-N1); các trường nguồn (NCC, số chứng từ) bị khoá sau ghi sổ như mọi trường khác | `validate` | **MỚI** |
| BR-K19 | "Điều chỉnh kiểm kê (tăng)" là loại nhập riêng — không dùng "Nhập khác" cho kiểm kê | Danh sách `loai_nhap` | **MỚI** |
| BR-K20 | Xuất **sử dụng** lô đã quá hạn: cảnh báo bắt xác nhận thêm, khuyến nghị chuyển "Xuất huỷ - hết hạn"; không chặn cứng | Màn phiếu xuất + `before_submit` (cờ xác nhận) | **MỚI** |
| BR-K21 | Tồn đầu kỳ chỉ nhập **một lần** cho mỗi kho; sai lệch sau đó dùng phiếu điều chỉnh kiểm kê | `kho_import_commit` | **MỚI** |

### 6.3 NCC khác (BR-N) **[MỚI]**

| Mã | Quy tắc |
|---|---|
| BR-N1 | Phiếu nhập loại "Mua ngoài (NCC khác)" bắt buộc gắn một `Customer Supplier` **của chính kho đó** |
| BR-N2 | Số chứng từ NCC là khuyến nghị, không bắt buộc; thiếu → phiếu mang cờ "thiếu chứng từ", lọc được để bổ sung |
| BR-N3 | NCC thuộc kho nào chỉ dùng cho kho đó; tên NCC không trùng trong một kho; NCC đã dùng trên phiếu không xoá được, chỉ tắt (`active = 0`) |

### 6.4 Đợt hàng & nhật ký (BR-D) **[MỚI]**

| Mã | Quy tắc |
|---|---|
| BR-D1 | Đợt = một phiếu nhập đã ghi sổ. NXT theo đợt phân bổ số xuất theo **FIFO trong từng (vật tư, lô)**; đây là quy ước phân tích, không phải bút toán |
| BR-D2 | Nhật ký vật tư **chỉ đọc**, dựng từ sổ kho; dòng `da_dao = 1` hiển thị mờ kèm nhãn, không bị giấu |
| BR-D3 | Đợt chậm luân chuyển khi tuổi tồn phần còn lại > ngưỡng cấu hình (mặc định 90 ngày) |

### 6.5 Dự trù & phân tích (BR-P) **[MỚI]**

| Mã | Quy tắc |
|---|---|
| BR-P1 | ADU (mức dùng bình quân/ngày) tính **chỉ** từ phiếu "Xuất sử dụng" đã ghi sổ trong kỳ trượt (mặc định 90 ngày), loại trừ phiếu đảo và dòng `da_dao`; tính trên **mọi nguồn hàng** (Miyano + mua ngoài) |
| BR-P2 | Gợi ý: `ROP = ADU × lead_time_ngay + ton_an_toan`; `min = ton_an_toan`; `max` do khách chốt. Hệ thống **chỉ gợi ý**, giá trị hiệu lực là giá trị khách lưu |
| BR-P3 | Cảnh báo thiếu tồn chỉ chạy khi: khách đã khai min/ROP, hoặc vật tư có ≥ 30 ngày dữ liệu xuất (cấu hình) |
| BR-P4 | Số lượng gợi ý đặt bổ sung = `max − tồn khả dụng`, làm tròn **lên** theo bội số quy cách; chỉ gắn nút đặt hàng khi vật tư khớp `item_code` thuộc hợp đồng khung còn hiệu lực |
| BR-P5 | Báo cáo phía Miyano đọc dữ liệu kho khách (gồm hàng mua ngoài) — điều kiện: hợp đồng dịch vụ có điều khoản chia sẻ dữ liệu (VĐ-10); phạm vi xem đúng như mục 8 |

### 6.6 Mua lẻ ngoài hợp đồng khung (BR-R) **[MỚI]**

| Mã | Quy tắc |
|---|---|
| BR-R1 | Mua lẻ bật/tắt **theo từng khách** (`Customer.custom_cho_phep_mua_le`), mặc định **BẬT** từ 15/08 (đổi từ tắt — `v1_15.bat_mua_le_mac_dinh`); sales tắt thủ công cho khách cụ thể khi cần (nợ quá hạn, chỉ cho mua theo hợp đồng — thay VĐ-13, không còn yêu cầu khách tự xác nhận trước khi bật) |
| BR-R2 | Giỏ hợp đồng khung và giỏ mua lẻ **tách riêng**, mỗi giỏ đặt thành một `Sales Order` riêng — không trộn hai loại dòng trong một đơn (khác Price List, khác cơ chế kiểm soát) |
| BR-R3 | *(sửa 15/08)* Dòng mua lẻ luôn vào đơn với `rate = 0` — không còn tra giá ở bước đặt hàng; sales điền giá khi báo giá (§4.10). Price List bán lẻ (`Settings.price_list_ban_le`) không còn dùng ở đường đọc danh mục |
| BR-R4 | Đơn mua lẻ: không gắn Blanket Order, không trừ hạn mức, `custom_loai_don = "Mua lẻ"`, **luôn** qua Miyano xác nhận và chịu duyệt ngưỡng BR-O9 |
| BR-R5 | Đơn lập từ báo giá phải được khách **Đồng ý trên cổng** (log người bấm + thời điểm); báo giá có hiệu lực N ngày (Settings), quá hạn tự đóng; khách tải được PDF báo giá (§4.10) |
| BR-R6 | *(sửa 15/08)* Danh mục mua lẻ = **toàn bộ** Item đang hoạt động (`disabled = 0`), không còn lọc theo `custom_ban_le_portal` — không hiện giá nên không còn lý do giấu bớt mặt hàng |
| BR-R7 | Mặt hàng đang thuộc hợp đồng khung còn hiệu lực của khách → **không mua lẻ được** mặt hàng đó (chống né hạn mức — NL-10.7) |

### 6.7 Yêu cầu hàng hoá (BR-Y) **[MỚI, DESK-ONLY — đổi 15/08]**

> Toàn bộ mục này mô tả quy trình nội bộ trên Desk (xem §4.11). Khách không còn tương tác trực tiếp
> với `Portal Item Request` qua cổng — mã BR-Y1…Y5 vẫn đúng, chỉ đổi ai là người thao tác.

| Mã | Quy tắc |
|---|---|
| BR-Y1 | Mọi yêu cầu có SLA phản hồi (`Settings.sla_yeu_cau_gio`, mặc định 48 giờ làm việc); quá hạn leo thang Sales Manager |
| BR-Y2 | Đóng yêu cầu "Không đáp ứng được" bắt buộc lý do; khách nhận email kèm đúng lý do |
| BR-Y3 | Item mới sinh từ yêu cầu phải qua **chuẩn hoá dữ liệu** (mã, tên, ĐVT, nhóm, %VAT, batch/expiry) trước khi mở bán — purchasing đề xuất, người giữ chuẩn dữ liệu duyệt |
| BR-Y4 | Yêu cầu không bị xoá; mọi trạng thái kết thúc đều lưu — nguồn của báo cáo demand pipeline và tỷ lệ chuyển đổi (UC-53) |
| BR-Y5 | Đính kèm là private file: chỉ khách sở hữu và nhân viên Miyano xem được; giới hạn ≤ 5 file, ≤ 10MB/file |

### 6.8 Hoá đơn điện tử (BR-E) **[MỚI]**

| Mã | Quy tắc |
|---|---|
| BR-E1 | **XML là bản gốc pháp lý, PDF là bản thể hiện** (NĐ 123/2020, TT 78/2021); cổng cung cấp cả hai kèm mã tra cứu và link tra cứu CQT (QĐ-7) |
| BR-E2 | Nút tải chỉ hiện khi `einvoice_trang_thai = "Đã phát hành"`; SI ghi sổ mà chưa phát hành → "Đang phát hành HĐĐT" |
| BR-E3 | HĐĐT huỷ / thay thế / điều chỉnh: hiển thị trạng thái + chuỗi liên kết hai chiều gốc ⇄ thay thế/điều chỉnh; không giấu hoá đơn cũ |
| BR-E4 | File tải qua endpoint kiểm phiên + sở hữu **từng lần** (`portal_einvoice_download`), private file, ghi log lượt tải; không tồn tại URL công khai |
| BR-E5 | Cổng chỉ **đọc** dữ liệu HĐĐT; phát hành / huỷ / điều chỉnh là nghiệp vụ kế toán trên Desk qua module của team Dev |

### 6.9 Cấp phát khoa phòng / cá nhân (BR-CP) **[MỚI — QĐ-9]**

| Mã | Quy tắc |
|---|---|
| BR-CP1 | Khoa phòng là danh mục **thuộc riêng một kho**; tên không trùng trong kho; khoa đã dùng trên phiếu không xoá được, chỉ tắt (`active = 0`); khoa tắt không chọn được trên phiếu mới |
| BR-CP2 | Kho có cờ `bat_buoc_khoa_phong`: bật → phiếu **"Xuất sử dụng"** bắt buộc chọn khoa phòng khi ghi sổ; chỉ áp cho phiếu tạo sau khi bật (NL-4.11). Các loại xuất khác (huỷ, trả lại, điều chỉnh) không bắt buộc |
| BR-CP3 | Người nhận là **ô nhập tự do** kèm gợi ý từ lịch sử phiếu của chính khoa đó (không quản danh mục nhân sự); với hoá chất, người nhận là vết truy xuất ai nhận — nên nhập |
| BR-CP4 | Báo cáo cấp phát đọc từ **sổ kho join qua phiếu xuất** (khoa/người nhận nằm trên đầu phiếu) — **không** đổi schema sổ kho append-only |
| BR-CP5 | Không sinh loại phiếu mới: phiếu Xuất sử dụng chính là chứng từ cấp phát; khoa phòng + người nhận in lên mẫu phiếu (TT107/TT200), ký nhận trên bản giấy theo quy trình đơn vị |

---

## 7. Mô hình dữ liệu

### 7.1 Doctype riêng của kho khách hàng

| Doctype | Vai trò | Đặc điểm | Nhãn |
|---|---|---|---|
| `Customer Warehouse` | Kho của một khách hàng | `KKH-.#####`; thông tin in phiếu + 2 `Print Format` riêng. **[MỚI]** thêm cờ `bat_buoc_khoa_phong` (Check, mặc định 0 — BR-CP2) | Hiện có, mở rộng |
| `Customer Warehouse Item` | Danh mục vật tư của kho | `VTK-.#####`; `item_code` rỗng = vật tư riêng (BR-K3). **[MỚI]** thêm: `ton_toi_thieu`, `ton_toi_da`, `diem_dat_lai`, `lead_time_ngay`, `boi_so_dat`, `adu_90` (readonly, hệ tính) | Hiện có, mở rộng |
| `Customer Stock Receipt` | Phiếu nhập kho — **một phiếu = một đợt nhận** | `loai_nhap` thêm "Mua ngoài (NCC khác)", "Điều chỉnh kiểm kê (tăng)" **[MỚI]**; trường mới: `ncc` (Link), `so_chung_tu_ncc`, `ngay_chung_tu`, `so_dot` (Int), `co_chenh_lech` (Check, hệ đặt), `thieu_chung_tu` (Check, hệ đặt) | Hiện có, mở rộng |
| `Customer Stock Receipt Item` | Dòng phiếu nhập | **[MỚI]** thêm: `sl_giao` (readonly, từ DN), `ly_do_chenh_lech` (bắt buộc khi `so_luong ≠ sl_giao`) | Hiện có, mở rộng |
| `Customer Stock Issue` | Phiếu xuất kho — **kiêm chứng từ cấp phát** (BR-CP5) | `loai_xuat` giữ nguyên; **[MỚI]** cờ `xac_nhan_xuat_het_han` (BR-K20), `khoa_phong` (Link `Customer Department` — thay trường tự do `bo_phan_nhan` dự kiến trước đây), `nguoi_nhan` (Data, gợi ý lịch sử — BR-CP3) | Hiện có, mở rộng |
| `Customer Stock Issue Item` | Dòng phiếu xuất | `istable = 1` | Hiện có |
| `Customer Stock Ledger Entry` | **Sổ kho — nguồn sự thật** | `SKK-.#########`; chỉ ghi thêm; có `da_dao` | Hiện có |
| `Customer Stock Lot Balance` | Tồn theo lô — cache dẫn xuất | Dựng lại được từ sổ | Hiện có |
| `Customer Supplier` | **Danh mục NCC khác của một kho** | `NCC-.#####`; `kho` (Link, bắt buộc), `ten_ncc` (unique trong kho), `mst`, `dien_thoai`, `email`, `dia_chi`, `ghi_chu`, `active` | **MỚI** |
| `Customer Department` | **Danh mục khoa phòng của một kho** (QĐ-9) | `KP-.#####`; `kho` (Link, bắt buộc), `ten_khoa_phong` (unique trong kho — BR-CP1), `ma_khoa` (Data, tuỳ chọn), `ghi_chu`, `active` | **MỚI** |
| `Miyano Portal Settings` | Tham số vận hành cổng (Single) | `nguong_duyet_2_tang` (Currency), `so_ngay_adu` (90), `so_ngay_du_lieu_toi_thieu` (30), `nguong_cham_luan_chuyen_ngay` (90), `sla_xu_ly_don_gio` (8), `price_list_ban_le` (Link Price List), `sla_yeu_cau_gio` (48), `hieu_luc_bao_gia_ngay` (7) | **MỚI** |
| `Portal Item Request` | **Yêu cầu hàng hoá của khách** — nhu cầu ngoài danh mục / cần tìm nguồn | `YCH-.#####`; `customer` (auto từ phiên), `nguoi_yeu_cau`, `loai` (Bổ sung HĐNT / Báo giá mua lẻ / Tìm nguồn hàng mới — giá trị lưu trong Select field, KHÔNG
đổi theo tên gọi mới; đây là dữ liệu, không phải chữ hiển thị), `ten_hang`, `quy_cach`, `dvt`, `so_luong_du_kien`, `tan_suat` (Một lần/Định kỳ), `ngay_can`, `hang_xuat_xu`, `ghi_chu`, đính kèm (private, ≤5×10MB), `vat_tu_kho` (Link `Customer Warehouse Item` — khi tạo từ dự trù), `trang_thai`, `phan_hoi`, `gia_bao`, `lead_time_ngay`, `item_lien_ket` (Link Item), `don_lien_ket` (Link SO), `ly_do_khong_dap_ung`, `sla_den_han` (hệ tính) | **MỚI** |

Quan hệ chính (trạng thái đích):

```
Customer (ERPNext)
   └─1:1─ Customer Warehouse
             ├─1:n─ Customer Warehouse Item ──(0..1)──► Item (ERPNext)
             ├─1:n─ Customer Supplier                                   [MỚI]
             ├─1:n─ Customer Stock Receipt ─1:n─ Customer Stock Receipt Item
             │         ├──(0..1)──► Delivery Note (nguồn Miyano)
             │         └──(0..1)──► Customer Supplier (nguồn mua ngoài) [MỚI]
             ├─1:n─ Customer Stock Issue   ─1:n─ Customer Stock Issue Item
             ├─1:n─ Customer Stock Ledger Entry     (ghi bởi ghi sổ phiếu)
             └─1:n─ Customer Stock Lot Balance      (dẫn xuất từ sổ)
```

### 7.2 Doctype ERPNext dùng lại **[Hiện có]**

| Khái niệm nghiệp vụ | Doctype ERPNext |
|---|---|
| Hợp đồng khung *(trước 15/08/2026: "hợp đồng nguyên tắc"/HĐNT — đổi tên hiển thị, xem CHANGELOG)* | `Blanket Order` (Selling) + `Price List` + `Item Price` |
| Đơn hàng / Phiếu giao / Hoá đơn | `Sales Order` / `Delivery Note` / `Sales Invoice` |
| Khách hàng, địa chỉ, người liên hệ | `Customer`, `Address`, `Contact` |
| Tài khoản cổng | `User` (Website User) + role `Customer` |

### 7.3 Trường mở rộng trên doctype ERPNext

**`Sales Order`** — [Hiện có] `custom_nguon_don` ("Client Portal"), `custom_hdnt` (Link Blanket
Order), `custom_so_po_khach`, `custom_yeu_cau_khach`. **[MỚI]** thêm: `custom_request_id` (Data,
unique — BR-O12), `custom_ly_do_tu_choi` (Small Text — BR-O14), `custom_loai_don` (Select:
Theo HĐNT / Mua lẻ, mặc định Theo HĐNT — BR-R4), `custom_yeu_cau_goc` (Link `Portal Item Request`).

**`Customer`** **[MỚI]**: `custom_cho_phep_mua_le` (Check, mặc định **1** — đổi từ 0 ở
`v1_15.bat_mua_le_mac_dinh`, §4.10/BR-R1; sales vẫn tắt được cho một khách cụ thể).

**`Item`** **[MỚI]**: `custom_ban_le_portal` (Check — BR-R6 gốc; *từ 15/08 không còn dùng để lọc
danh mục mua lẻ*, xem BR-R6 hiện hành).

**`Sales Invoice` — hợp đồng dữ liệu HĐĐT** **[MỚI]** *(tên trường TẠM — phải đối chiếu với module
HĐĐT thực tế của team Dev trước khi code, VĐ-11)*:

| Trường (tạm) | Ý nghĩa |
|---|---|
| `einvoice_trang_thai` | Select: Chưa phát hành / Đã phát hành / Đã huỷ / Bị thay thế / Bị điều chỉnh |
| `einvoice_so`, `einvoice_ky_hieu` | Số hoá đơn + mẫu số–ký hiệu |
| `einvoice_ma_tra_cuu` | Mã tra cứu trên hệ thống CQT / NCC dịch vụ HĐĐT |
| `einvoice_ngay_phat_hanh` | Ngày phát hành |
| `einvoice_file_xml`, `einvoice_file_pdf` | Private file — XML bản gốc, PDF bản thể hiện |
| `einvoice_link_tra_cuu` | URL trang tra cứu công khai |
| `einvoice_lien_ket_goc` | Link SI gốc (khi là hoá đơn thay thế / điều chỉnh) |
| Sự kiện "phát hành thành công" | Móc để cổng gửi email + cập nhật hiển thị (mục 9) |

### 7.4 Cài đặt tự động khi `bench migrate` **[Hiện có, mở rộng]**

11 patch hiện có giữ nguyên. Các patch mới phải bổ sung: trường mở rộng mục 7.1/7.3, doctype mới,
notification mới (mục 9), report Desk mới (mục 10), cấu hình over-delivery = 0, workflow theo ngưỡng.
Nguyên tắc idempotent (chạy lại nhiều lần được) áp dụng cho mọi patch mới.

---

## 8. Phân quyền và cách ly dữ liệu

Toàn bộ mô hình **[Hiện có]** giữ nguyên — đây là phần rủi ro cao nhất của hệ thống:

1. Nhóm chứng từ bán hàng: `permission_query_conditions` + `has_permission` theo `customer`;
   mọi endpoint lấy tài liệu theo tên **bắt buộc** tự gọi `check_permission` (Frappe bản này
   không tự gọi trong `frappe.get_doc`).
2. Nhóm doctype kho: role `Customer` **không có DocPerm nào** — chịu lực chính; query conditions
   và hook `has_permission` là lớp hai; API whitelist tự suy kho từ phiên (`get_portal_kho()`)
   là cổng duy nhất. Hệ quả: người dùng cổng không dùng `/printview`; PDF đi qua `kho_phieu_pdf`.
3. Hai bảng con cố ý **không** có entry `has_permission` (cơ chế `has_child_permission` rẽ nhánh
   sang cha — entry ở con không bao giờ chạy).

**Áp dụng cho phần [MỚI]:**

| Đối tượng mới | Quy tắc |
|---|---|
| `Customer Supplier`, `Customer Department`, `Miyano Portal Settings`, `Portal Item Request` | Theo đúng mô hình kho: role `Customer` **không có DocPerm**; mọi truy cập qua endpoint whitelist suy khách/kho từ phiên; Settings chỉ `System Manager` sửa; đính kèm yêu cầu và file HĐĐT là **private file**, không có URL công khai |
| Endpoint mới (`kho_ncc_*`, `kho_nhat_ky`, `kho_bao_cao_dot`, `kho_canh_bao_ton`, `kho_min_max_goi_y`, `portal_reorder`, `portal_catalog_ban_le`, `portal_order_accept`, `portal_bao_gia_pdf`, `portal_einvoice_download`) | Cùng khuôn `get_portal_kho()` / `check_permission`; không endpoint nào nhận `customer`/`kho` từ client; `portal_order_accept` chỉ chuyển trạng thái khi đơn thuộc đúng khách **và** đang ở "Chờ khách đồng ý". *(`portal_yeu_cau_*` đã xoá khỏi API cổng 15/08 — UC-16/17)* |
| **VĐ-1 (bắt buộc sửa trước go-live v2)** | Bọc `frappe.desk.search.search_link` bằng `override_whitelisted_methods`: với Website User ép tắt `ignore_user_permissions` và bỏ `filter_fields` — bịt đường rò `Sales Invoice` của khách khác |
| Dữ liệu Miyano xem được (UC-48…51) | Nhân viên Miyano (role nội bộ) xem **toàn bộ** kho khách qua report Desk — như UC-41 hiện có; phạm vi này phải được nêu trong điều khoản chia sẻ dữ liệu (VĐ-10) |

---

## 9. Tích hợp và sự kiện

| Sự kiện | Móc / kênh | Hướng | Tính chất | Nhãn |
|---|---|---|---|---|
| `Delivery Note.on_submit` | `on_delivery_note_submit` | ERPNext → kho khách | Sinh phiếu nhập **nháp** từng đợt; không bao giờ ném lỗi | Hiện có, mở rộng (`sl_giao`, `so_dot`) |
| `Delivery Note.on_cancel` | `on_delivery_note_cancel` | ERPNext → kho khách | Gỡ phiếu nháp / đảo phiếu đã ghi sổ | Hiện có |
| Ghi sổ phiếu nhập/xuất | `ledger.post_lines` | Phiếu → sổ kho | Ghi `Ledger Entry` + cập nhật `Lot Balance` | Hiện có |
| Huỷ phiếu | `_tao_phieu_dao` + `mark_reversed` | Phiếu → sổ kho | Bù trừ, không xoá | Hiện có |
| 5 `Notification` bán hàng | Email | Hệ thống → khách | Người nhận theo `contact_email` | Hiện có |
| **Chênh lệch nhận hàng** (BR-K17) | Notification | Kho khách → sales Miyano | Khi ghi sổ phiếu có `co_chenh_lech` | **MỚI** |
| **Thiếu giá bán** (NL-1.4) | Notification | Cổng → sales Miyano | Khi khách bị chặn vì thiếu giá | **MỚI** |
| **Đơn treo quá SLA** (NL-2.6) | Job nền + Notification | Hệ thống → Sales Manager | Quét định kỳ đơn "Chờ Miyano xác nhận" | **MỚI** |
| **Cảnh báo thiếu tồn** (QT9) | Job nền + email tuỳ chọn | Hệ thống → khách | Tính từ Lot Balance + min/ROP; hiển thị trên cổng, email tần suất cấu hình | **MỚI** |
| **Yêu cầu hàng hoá đổi trạng thái** (QT11, Desk-only) | Notification | Sales/purchasing → khách (email, không còn hiển thị trên cổng) | Mỗi lần đổi trạng thái → email khách; quá SLA → leo thang nội bộ | **MỚI** |
| **Đơn chờ khách đồng ý** (QT10) | Notification + job hạn hiệu lực | Miyano → khách | Lập SO từ báo giá → email khách kèm hạn hiệu lực + PDF báo giá; quá hạn → tự đóng, email hai phía | **MỚI** |
| **HĐĐT phát hành** (QT12) | Sự kiện từ module HĐĐT → Notification | Kế toán → khách | Email kèm số + ký hiệu + link cổng; thay thế/huỷ/điều chỉnh cũng gửi thông báo | **MỚI** |

**Không có chiều ngược lại vào sổ sách Miyano.** Phiếu kho của khách không tác động tồn kho,
giá vốn, hay kế toán của Miyano — nguyên tắc nền tảng giữ nguyên ở v2.0.

---

## 10. Báo cáo và chứng từ in

| Báo cáo | Khách (cổng) | Miyano (Desk) | Nguồn dữ liệu | Nhãn |
|---|---|---|---|---|
| Tồn kho theo vật tư / theo lô | ✔ | ✔ | `Customer Stock Lot Balance` | Hiện có |
| Nhập – xuất – tồn theo kỳ | ✔ | ✔ | `Customer Stock Ledger Entry` | Hiện có |
| Thẻ kho một vật tư | ✔ | — | `Customer Stock Ledger Entry` | Hiện có |
| Cảnh báo hạn dùng (nhóm "không hạn" tách riêng — VĐ-2) | ✔ | ✔ | `Customer Stock Lot Balance` | Hiện có, mở rộng |
| **Nhật ký vật tư** | ✔ | ✔ | Sổ kho | **MỚI** |
| **NXT theo đợt hàng** (tiêu thụ / còn lại / tuổi tồn / chậm luân chuyển) | ✔ | ✔ | Sổ kho + phiếu nhập | **MỚI** |
| **Cảnh báo thiếu tồn (min/ROP)** | ✔ | ✔ | Lot Balance + min/max | **MỚI** |
| **Đối soát giao – nhận** | — | ✔ | DN + phiếu nhập (`sl_giao` vs `so_luong`) | **MỚI** |
| **Tiêu thụ & đề xuất dự trù** (ADU, coverage, dự báo hết hàng) | — | ✔ | Sổ kho (Xuất sử dụng) | **MỚI** |
| **Tỷ trọng nguồn cung (share-of-wallet)** | — | ✔ | Phiếu nhập theo nguồn | **MỚI** |
| **Chất lượng dữ liệu** (thiếu lô/hạn, kho không hoạt động, thiếu chứng từ) | — | ✔ | Sổ kho + phiếu | **MỚI** |
| **Nhu cầu chưa đáp ứng (demand pipeline)** — theo trạng thái/khách/nhóm, tỷ lệ chuyển thành đơn, thời gian xử lý, nhóm định kỳ đề xuất vào hợp đồng khung | — | ✔ | `Portal Item Request` | **MỚI** |
| **Đơn mua lẻ theo khách/kỳ** — giá trị, tỷ trọng so với đơn hợp đồng khung | — | ✔ | `Sales Order` (`custom_loai_don`) | **MỚI** |
| **Cấp phát theo khoa phòng** (kỳ · khoa · vật tư · SL · giá trị · người nhận, drill xuống phiếu; % tiêu thụ từng khoa) | ✔ | ✔ | Sổ kho join phiếu xuất (BR-CP4) | **MỚI** |
| Xuất Excel các báo cáo | ✔ | ✔ | — | Hiện có, mở rộng |

Chứng từ in: phiếu nhập / phiếu xuất theo mẫu **TT107** (mặc định) hoặc **TT200**, chọn theo kho;
chứng từ bán hàng song ngữ. **[Hiện có]** — mẫu thật của từng bệnh viện bổ sung dần (VĐ-5).

---

## 11. Yêu cầu phi chức năng và vận hành

| Nhóm | Yêu cầu | Nhãn |
|---|---|---|
| Ngôn ngữ | Giao diện cổng tiếng Việt; nhãn doctype tiếng Việt, tên doctype tiếng Anh | Hiện có |
| Tiền tệ / định dạng | VND `1.234.567 ₫`, không thập phân; ngày `dd/mm/yyyy` — thống nhất mọi màn, email, PDF | Hiện có |
| Thiết bị | Responsive; mobile có xử lý riêng (`useMobile.js`); chuẩn thao tác mobile theo Form Spec mục 2 | Hiện có |
| Cách ly dữ liệu | Mục 8 — ràng buộc nhất; **VĐ-1 phải sửa trước go-live v2** | Hiện có + MỚI |
| Chịu lỗi | Trục trặc kho khách không được chặn giao hàng Miyano (BR-K12) | Hiện có |
| Khôi phục | `Lot Balance` dựng lại từ sổ; `replay_vouchers_into_ledger` dựng sổ từ phiếu | Hiện có |
| Idempotent | Script setup/patch chạy lại được; **đặt hàng idempotent theo `request_id`** | Hiện có + MỚI |
| **Chất lượng dữ liệu nguồn** | Item Miyano bán cho khách có kho phải bật **Has Batch No + Has Expiry Date** và xuất theo bundle lô — tiền đề của FEFO, cảnh báo hạn, dự trù. Theo dõi bằng báo cáo UC-51 | **MỚI** |
| **Pháp lý dữ liệu** | Hợp đồng dịch vụ kho phải có điều khoản khách đồng ý cho Miyano truy cập dữ liệu kho (gồm hàng mua ngoài) phục vụ dự trù (VĐ-10) | **MỚI** |
| Hiệu năng | Danh mục 500 mặt hàng < 3s; tạo SO < 60s; 50 người dùng đồng thời; nhật ký/báo cáo phân trang máy chủ | Từ BRD V1 + MỚI |
| Kiểm thử | 339 test hiện có phải giữ xanh; phần [MỚI] bổ sung test cùng chuẩn (cách ly, ngoại lệ, e2e); bộ 73 TC UAT V1 mở rộng cho tính năng mới | Hiện có + MỚI |
| Vận hành | Audit log thao tác cổng lưu ≥ 24 tháng; khoá tài khoản khi khách nghỉ việc; backup theo chính sách site | Từ BRD V1 |

---

## 12. Vấn đề mở và rủi ro

| Mã | Vấn đề | Trạng thái v2.0 |
|---|---|---|
| VĐ-1 | Rò rỉ dữ liệu tài chính giữa khách hàng qua `search_link` (`ignore_user_permissions=1`) | **Nâng mức: BẮT BUỘC sửa trước go-live v2** — phương án tại mục 8 |
| VĐ-2 | Báo cáo cảnh báo hạn dùng nhiễu vì lô không hạn bị coi như hết hạn hôm nay | **Đã chốt hướng**: tách nhóm "Không có hạn dùng" riêng, không tính sắp hết hạn; gốc rễ xử lý bằng yêu cầu chất lượng dữ liệu (mục 11) |
| VĐ-3 | Workflow chưa có duyệt hai tầng | **ĐÃ QUYẾT (QĐ-1, 2026-08-11)**: duyệt theo ngưỡng — BR-O9; còn lại VĐ-8 |
| VĐ-4 | Workflow áp cho mọi `Sales Order` | Đã chấp nhận |
| VĐ-5 | Chưa có mẫu phiếu in thật của từng bệnh viện | Chờ nghiệp vụ cung cấp; dùng TT107/TT200 |
| VĐ-6 | Một khách một kho (`unique` tầng CSDL) | Giữ; nhu cầu nhiều kho/khoa phòng đánh giá sau — đổi schema + `get_portal_kho` trả danh sách |
| VĐ-7 **[MỚI]** | **Hoàn hạn mức** khi (a) Close SO giao dở (NL-2.8) và (b) trả hàng (NL-3.9): `ordered_qty` của Blanket Order không tự giảm trong hai tình huống này | Cần xác nhận cơ chế kỹ thuật: script điều chỉnh khi Close/Return; nếu không làm, chấp nhận hạn mức "mất" phần đã đặt |
| VĐ-8 **[MỚI]** | Giá trị `nguong_duyet_2_tang` | Đề xuất 50.000.000 ₫; chủ đầu tư chốt số khi triển khai |
| VĐ-9 **[MỚI]** | Phê duyệt nội bộ phía khách (FR-A4 BRD V1) | Backlog — bật theo nhu cầu từng khách, không nằm trong v2.0 |
| VĐ-10 **[MỚI]** | Điều khoản chia sẻ dữ liệu kho (gồm hàng mua ngoài) trong hợp đồng dịch vụ | Pháp chế soạn trước khi bật tính năng kho cho khách mới |
| VĐ-11 **[MỚI]** | **Hợp đồng dữ liệu HĐĐT**: tên trường, trạng thái, sự kiện "phát hành thành công" của module HĐĐT team Dev — BA đang dùng tên tạm (mục 7.3) | Họp với team Dev đối chiếu trước khi code QT12; xác nhận cả cách lưu file XML/PDF (private file hay storage khác) |
| VĐ-12 **[ĐÃ TAN — 15/08]** | ~~Chuẩn hoá Price List bán lẻ trước khi bật QT10 nhánh A~~ | Thiết kế lại §4.10 bỏ hẳn "nhánh A đặt thẳng theo giá bán lẻ" — danh mục mua lẻ không còn hiện giá, mọi phiếu đều đi qua báo giá của sales. Không còn Price List bán lẻ nào cần chuẩn hoá cho đường đọc danh mục |
| VĐ-13 **[QUYẾT LẠI — 15/08]** | Pháp lý mua sắm của khách công lập khi mua lẻ ngoài hợp đồng | Chủ dự án chốt: bật mặc định cho MỌI khách (`v1_15.bat_mua_le_mac_dinh`), chấp nhận rủi ro pháp lý phía khách công lập tự chịu trách nhiệm khi bấm mua; sales vẫn tắt được thủ công cho khách cụ thể nếu cần |
| VĐ-14 **[MỚI]** | **Phiếu lĩnh online của khoa phòng** (khoa tự gửi yêu cầu lĩnh → thủ kho duyệt → xuất): cần tài khoản/phân quyền theo khoa + máy trạng thái duyệt — scope lớn | Backlog theo QĐ-9; đánh giá sau khi cấp phát trên phiếu xuất chạy ổn và có nhu cầu thật |

---

## 13. Từ điển thuật ngữ

Giữ toàn bộ bảng thuật ngữ v1.0 (hợp đồng khung/`Blanket Order`, hạn mức, `Sales Order`, `Delivery Note`,
`Sales Invoice`, `Customer Warehouse`, `Customer Warehouse Item`, lô `so_lo`, hạn dùng `han_su_dung`,
phiếu nhập/xuất, sổ kho, tồn theo lô, phiếu đảo, `da_dao`, docstatus 0/1/2, tồn đầu kỳ, NXT, thẻ kho,
FEFO, thủ kho, ĐVT). Bổ sung:

| Tiếng Việt | Tiếng Anh / kỹ thuật | Ghi chú |
|---|---|---|
| Đợt giao | delivery tranche | Một `Delivery Note` trên một SO |
| Đợt nhận / đợt hàng | receipt batch | Một `Customer Stock Receipt` đã ghi sổ; mã phiếu = mã đợt |
| NCC khác | `Customer Supplier` | Nhà cung ứng ngoài Miyano của khách; dữ liệu danh mục, không có tài khoản |
| Nhật ký vật tư | item movement log | Màn chỉ đọc dựng từ sổ kho |
| Chênh lệch nhận | receiving discrepancy | `so_luong` thực nhận ≠ `sl_giao` |
| Đối soát giao – nhận | delivery reconciliation | Report Desk UC-48 |
| Mức dùng bình quân ngày | ADU (average daily usage) | BR-P1 |
| Ngày phủ tồn | days of cover | tồn khả dụng ÷ ADU |
| Điểm đặt hàng lại | ROP (reorder point) | BR-P2 |
| Tồn an toàn / min / max | safety stock / min / max | Trên `Customer Warehouse Item` |
| Tỷ trọng nguồn cung | share-of-wallet | Giá trị nhập Miyano vs NCC khác |
| Đúng thời điểm | JIT (Just-in-Time) | Mục tiêu MT10 |
| Ngưỡng duyệt hai tầng | approval threshold | BR-O9 |
| Mã yêu cầu | `request_id` | Chống tạo đơn trùng — BR-O12 |
| Mua lẻ | ad-hoc / retail order | Đơn ngoài hợp đồng khung, `custom_loai_don = "Mua lẻ"` — QT10 |
| Yêu cầu hàng hoá | `Portal Item Request` | Nhu cầu ngoài danh mục, cần tìm nguồn — QT11 |
| Tìm nguồn | sourcing | Purchasing tìm NCC cho hàng chưa có Item |
| Nhu cầu chưa đáp ứng | demand pipeline | Báo cáo UC-53 |
| Chờ khách đồng ý | pending customer acceptance | Trạng thái đơn lập từ báo giá — QĐ-6 |
| Hiệu lực báo giá | quote validity | `hieu_luc_bao_gia_ngay`, quá hạn tự đóng |
| Hạn mức 0 / Không giới hạn | unlimited quota | Quy ước QĐ-8 — BR-O15, NL-1.11 |
| Khoa phòng | `Customer Department` | Danh mục nơi nhận cấp phát của một kho — QĐ-9 |
| Cấp phát | dispensing / allocation | Ghi khoa phòng + người nhận trên phiếu Xuất sử dụng (BR-CP5) |
| Người nhận | recipient | Ô nhập tự do có gợi ý lịch sử — BR-CP3 |
| Phiếu lĩnh | requisition slip | Khoa tự gửi yêu cầu lĩnh — backlog VĐ-14 |
| Hoá đơn điện tử (HĐĐT) | e-invoice | NĐ 123/2020 + TT 78/2021 |
| Bản gốc XML / bản thể hiện PDF | original XML / rendered PDF | BR-E1 |
| Mã tra cứu | lookup code | Tra trên hệ thống CQT / NCC dịch vụ HĐĐT |
| HĐĐT thay thế / điều chỉnh | replacement / adjustment invoice | Chuỗi liên kết gốc ⇄ mới — BR-E3 |

---

## 14. Phụ lục — danh mục endpoint whitelist

**`miyano_portal.api.portal`** — [Hiện có] `portal_me` · `portal_contracts` · `portal_catalog` ·
`portal_order_place` · `portal_order_history` · `portal_order_track` · `portal_deliveries` ·
`portal_invoices` · `portal_request_cancel` · `portal_provision` · `portal_document_download`
— [MỚI] `portal_reorder` · `portal_catalog_ban_le` · `portal_order_accept` · `portal_bao_gia_pdf` ·
`portal_einvoice_download`. *(`portal_yeu_cau_list`/`portal_yeu_cau_save`/`portal_yeu_cau_cancel` —
xoá khỏi API cổng 15/08, xem UC-16/17 và `30_API_Spec.md`.)*

**`miyano_portal.api.kho`** — [Hiện có] `kho_me` · `kho_ton` · `kho_lo` · `kho_vat_tu_list` ·
`kho_vat_tu_tao` · `kho_vat_tu_sua` · `kho_vat_tu_export` · `kho_vat_tu_import_preview` ·
`kho_vat_tu_import_commit` · `kho_import_template` · `kho_import_preview` · `kho_import_commit` ·
`kho_phieu_list` · `kho_phieu_get` · `kho_phieu_nhap_save` · `kho_phieu_xuat_save` ·
`kho_phieu_submit` · `kho_phieu_cancel` · `kho_dong_phieu_mau` · `kho_dong_phieu_doc_file` ·
`kho_dong_phieu_export` · `kho_lo_goi_y` · `kho_phieu_pdf` · `kho_bao_cao_nxt` · `kho_the_kho` ·
`kho_canh_bao_han` · `kho_bao_cao_excel`
— [MỚI] `kho_ncc_list` · `kho_ncc_save` · `kho_nhat_ky` · `kho_bao_cao_dot` · `kho_canh_bao_ton` ·
`kho_min_max_goi_y` · `kho_khoa_phong_list` · `kho_khoa_phong_save` · `kho_nguoi_nhan_goi_y` ·
`kho_bao_cao_cap_phat`

Không có đường nào khác được phép. Endpoint [MỚI] tuân thủ cùng khuôn an toàn (mục 8).

---

## 15. Tài liệu liên quan

| Tài liệu | Nội dung |
|---|---|
| [`FormSpec-miyano_portal_v2.md`](FormSpec-miyano_portal_v2.md) | Đặc tả hiển thị và thao tác **từng trường của từng form** — bản đồng hành bắt buộc của tài liệu này |
| [`01_Workflow-miyano_portal_v2.html`](01_Workflow-miyano_portal_v2.html) | Sơ đồ 9 quy trình + luồng ngoại lệ, mở bằng trình duyệt, in được A4 |
| `BA-miyano_portal.md` (v1.0, 2026-08-10) | Bản as-built — nguồn của mọi mục [Hiện có] |
| `YeuCau_NghiepVu_ThietKe_ClientPortal_Miyano.docx` (27/07/2026) | BRD V1 — nguồn của FR-A…G, S-01…S-09 |
| `KichBan_DuLieu_Test_ClientPortal_Miyano_v1.0.xlsx` | 73 kịch bản test V1 — nền để mở rộng UAT v2 |
| `Mockup_Client_Portal_Miyano.html` / `..._Mobile.html` | Chuẩn giao diện V1 — nguồn của quy ước trong Form Spec |
| `HDSD-tao-khach-hang-mo-kho-va-thao-tac-cong.md` | Hướng dẫn thao tác cho quản trị viên và khách |
| `superpowers/specs/2026-08-06-kho-khach-hang-design.md`, `2026-08-07-vat-tu-va-import-export-dong-phieu-design.md` | Thiết kế chi tiết kho hiện có |
| Tài liệu kỹ thuật module HĐĐT *(team Dev cung cấp)* | Nguồn đối chiếu hợp đồng dữ liệu mục 7.3 — bắt buộc trước khi code QT12 (VĐ-11) |

