# Nhật ký thao tác và dòng thời gian đơn hàng — Thiết kế

**Ngày:** 03/09/2026 · **Chủ đầu tư duyệt:** đang chờ đọc bản này
**Trạng thái:** thiết kế, chưa lập kế hoạch thi công

---

## 1. Việc cần giải

Chủ đầu tư: *"muốn thấy được chi tiết trong phần tiến trình, ai là người thao tác gì, trên cổng khách hàng thấy được cả tên nhân viên xác nhận của Miyano, cách hiển thị giống Viettel Post"*, và *"chỗ nào hiện tên kể cả truy vết cũng hiển thị cả số điện thoại"*.

Hôm nay màn chi tiết đơn có khối **Tiến trình** là một thanh năm chấm: Đặt hàng · Xác nhận · Soạn hàng · Giao hàng · Hoá đơn. Nó trả lời được *"đang ở bước nào"* và không trả lời được gì thêm:

- **Không có ai trong đó.** Không một cái tên, không một mốc giờ.
- **Không thể hiện được vòng lặp.** Đơn đi báo giá ba lần, hoặc khoa xin sửa số lượng hai vòng, thì thanh năm chấm vẫn là năm chấm. Một lần Miyano từ chối cũng không hiện ra được.
- **Trạng thái là suy đoán, không phải sự thật đã ghi.** "Soạn hàng xong" được suy từ *"có tồn tại một Pick List"*. Không ai ghi lại rằng có người đã soạn hàng.

## 2. Sự thật đã đo trên hệ thống, trước khi thiết kế

Bốn dữ kiện dưới đây được kiểm trực tiếp trên `erptest.local` ngày 03/09/2026. Chúng định hình toàn bộ bản thiết kế; đọc phần sau mà bỏ qua phần này sẽ thấy nhiều quyết định là tuỳ tiện.

**(a) Nửa bệnh viện ghi đủ người thao tác.** `Portal De Xuat Mua` có `nguoi_yeu_cau`, `thoi_diem_gui`, `nguoi_duyet`, `thoi_diem_duyet`, `duyet_voi_tu_cach`.

**(b) Nửa Miyano không ghi gì cả.** `portal_order_accept` không lưu ai bấm đồng ý. Các bước workflow của Sales Order (`Chờ xác nhận` → `Chờ Miyano xác nhận` → `Đã xác nhận`, và `Chờ khách đồng ý` / `Từ chối` / `Khách huỷ` / `Báo giá hết hạn`) không ghi người thao tác vào trường nào. Chỉ còn `owner`/`modified_by` — hai thứ trả lời *"ai lưu bản ghi lần cuối"*, **không phải** *"ai xác nhận đơn"*.

**(c) Không một tài khoản nào có số điện thoại.** Cả 10 tài khoản (7 cổng + 3 nhân sự) đều trống `mobile_no` lẫn `phone`.

**(d) Tài khoản cổng đang là cấp ĐƠN VỊ, không phải cấp người.**

```
bvbm@demo.miyano       → "Bệnh viện Bạch Mai"
bvminhduc@demo.miyano  → "Khoa Dược BV Đa khoa Minh Đức"
hungvuong@demo.miyano  → "Bệnh viện Đa khoa Hùng Vương"
```

`full_name` đặt bằng chính tên đơn vị. Nên câu *"ai gửi phiếu này"* hôm nay chỉ trả lời được là *"Bệnh viện Bạch Mai"*. Đây là điều repo đã ghi nhận từ 25/08, đo trên hệ thống thật, và là lý do khối truy vết hiện phải in kèm email tài khoản — vì cái tên không phân biệt được ai với ai.

## 3. Quyết định đã chốt với chủ đầu tư

| # | Quyết định | Ghi chú |
|---|---|---|
| Đ1 | Hiện **tên người** ở những bước khách có quyền đòi hỏi trách nhiệm | Không hiện người sửa vặt nội bộ |
| Đ2 | Hiện kèm **số điện thoại**, lấy từ trường sẵn có trên `User` | Chỗ nào hiện tên thì hiện số — gồm cả khối truy vết đang có |
| Đ3 | Số điện thoại thành **mục bắt buộc** khi Miyano tạo tài khoản | Giải quyết dữ kiện (c) cho mọi tài khoản sinh ra từ nay |
| Đ4 | **Tách tài khoản theo người**, làm cùng đợt | Giải quyết dữ kiện (d) |
| Đ5 | **Miyano tạo và cấp tài khoản** cho nhân viên bệnh viện | Khớp chính sách đã có: *"Quản lý bệnh viện chưa tự cấp tài khoản được — và sẽ không bao giờ được"* |
| Đ6 | Ghi bằng **sổ nhật ký chỉ-thêm**, viết ngay lúc việc xảy ra | Không suy ngược từ `Version` |

**Hệ quả của Đ5 làm gọn phạm vi:** vì Miyano tạo và cấp tài khoản, **không cần màn hình mới nào** cho việc tách tài khoản. Cái màn "bước 9" (quản lý bệnh viện tự gán khoa, bật/tắt thành viên) mà `HDSD-phan-quyen-khoa-phong.md` §7 mục 2 ghi là còn nợ — với mô hình này chưa cần tới. Toàn bộ phần viết code nằm ở nhật ký + dòng thời gian.

**Giả định của người thiết kế, đảo ngược được:** sáu tài khoản cấp đơn vị đang chạy sẽ **giữ lại và đổi thành tài khoản của quản lý bệnh viện** (đổi `full_name` thành tên người, điền số), thay vì khoá đi. Lý do: chúng vốn đang được dùng đúng như vậy; dữ liệu cũ vẫn có chủ; không bệnh viện nào phải nghe giải thích vì sao mất tài khoản. Quyết định này làm riêng cho từng bệnh viện lúc triển khai.

## 4. Vì sao sổ nhật ký, không phải hai cách kia

**Không suy ngược từ `Version`.** `Version` là nhật ký *thay đổi trường*, không phải nhật ký *sự kiện*. Biến `docstatus 0→1` thành *"anh Tuấn xác nhận đơn"* là **diễn giải**, mà diễn giải thì trôi khỏi nguồn — đúng lớp lỗi mà phiên 03/09 vừa phải dẹp ở `giai_doan` (một bản suy ở client lệch bản gốc SQL ba nhánh trong đúng task đầu tiên dùng nó). Nặng hơn: cùng phiên đó phát hiện `frappe.delete_doc` xoá luôn `Version` của chứng từ qua `delete_dynamic_links`. Xây lịch sử cho bệnh viện nhìn trên một bảng có thể bị dọn sạch là xây trên cát.

**Không thêm cặp trường "người + thời điểm" lên chứng từ.** Số bước là cố định, mà đơn ở đây có vòng lặp. Một cặp trường chỉ giữ được lần cuối — tức mất đúng thứ tính năng này sinh ra để hiện. Đây cũng chính là lý do thanh năm chấm hiện nay không dùng được. Repo đã có bằng chứng sống cho khuyết điểm này: `HDSD-phan-quyen-khoa-phong.md` §7 mục 3b ghi *"vòng duyệt sửa chưa ghi mốc riêng — khối truy vết vẫn chỉ mang dấu của lần duyệt đầu"*.

**Sổ nhật ký giải cả hai:** mỗi vòng là một dòng mới, và người thao tác được ghi tại **khoảnh khắc việc xảy ra**, không phải suy lại về sau. Vá luôn mục 3b nói trên mà không cần task riêng.

## 5. Mô hình dữ liệu

### Doctype `Portal Nhat Ky Yeu Cau`

Chỉ-thêm. Không sửa, không xoá — `on_update` chặn khi không phải bản ghi mới, `on_trash` chặn vô điều kiện. Một bản ghi là một câu khẳng định về quá khứ; sửa nó là nói dối về quá khứ.

| Trường | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|---|---|
| `customer` | Link Customer | ✔ | Trục phạm vi. **Cố ý phi chuẩn hoá** — xem ghi chú dưới |
| `khoa_phong` | Link Customer Department | | Trục phạm vi thứ hai; rỗng nghĩa "toàn viện" |
| `de_xuat` | Link Portal De Xuat Mua | | Một trong hai (`de_xuat`/`sales_order`) phải có |
| `sales_order` | Link Sales Order | | nt |
| `thoi_diem` | Datetime | ✔ | Lúc việc xảy ra, không phải lúc ghi |
| `su_kien` | Data | ✔ | **KHOÁ nội bộ**, không phải nhãn — xem §7 |
| `nguoi_thao_tac` | Data (Email) | | Tài khoản đã làm; rỗng cho sự kiện hệ thống |
| `vai` | Select | ✔ | `khoa` / `quan_ly` / `miyano` / `he_thong` |
| `ghi_chu` | Small Text | | Lý do từ chối, tóm tắt số lượng đã đổi, số đợt giao… |

**Vì sao chép `customer`/`khoa_phong` xuống thay vì suy qua liên kết:** endpoint đọc nhật ký phải tự hỏi chốt phạm vi (role `Customer` có ZERO DocPerm trên các doctype cổng — hàm whitelist là đường sống, xem docstring `api/de_xuat.py`). Lọc trực tiếp trên hai cột này là một điều kiện `where`; suy qua `de_xuat`→`customer` **hoặc** `sales_order`→`customer` là hai nhánh join khác nhau tuỳ dòng, và một bộ lọc phân quyền có hai nhánh là một bộ lọc sớm muộn hở một nhánh.

**Đặt tên:** theo tiền lệ `Portal De Xuat Mua`, `Portal Delivery Inspection`, `Portal Member`.

### Ghi ở đâu

Ghi tại **đúng những chỗ hiện đang bắn thông báo** — chúng đã là "khoảnh khắc có việc thật xảy ra", đã được kiểm chứng qua nhiều vòng review, và không phải đi tìm chỗ móc mới:

- `PortalDeXuatMua.gui_duyet()` / `.duyet()` / `.tu_choi()` / `.huy()` / `.thu_hoi()` / `.xin_sua()` / `.duyet_sua()` / `.tu_choi_sua()`
- `api/portal.py::portal_order_accept` / `portal_order_sua_so_luong` / `portal_order_huy`
- **Chuyển trạng thái workflow của Sales Order** (Miyano thao tác trên Desk): móc vào chuỗi `Sales Order.on_update` **đã có sẵn** trong `hooks.py`, so `doc.workflow_state` với `doc.get_doc_before_save().workflow_state` — chỉ ghi khi hai giá trị khác nhau. Không dựng hook mới.
- **Sinh đơn** (`don_tao`): hai đường tạo Sales Order, cả hai đều phải ghi — `de_xuat_duyet.duyet_va_tao_don` (luồng duyệt) và `api/portal.py::_dam_bao_phieu_tu_duyet` (quản lý đặt thẳng).
- **Giao hàng**: `kho/delivery_hook.py::on_delivery_note_submit` — hook đã có.
- **Hoá đơn**: chuỗi `Sales Invoice.on_submit` **đã có sẵn** trong `hooks.py`.

**Luật "không bao giờ ném lỗi"** — giống hệt các hàm `bao_*` hiện có: một trục trặc ở khâu ghi nhật ký **không được** cuốn theo một chuyển trạng thái đã thành công. Nhưng cũng **không được rơi im lặng**: bọc `try/except` rồi `frappe.log_error`, đúng khuôn `bao_de_xuat_gui_duyet`.

**Ghi trong cùng giao dịch với chuyển trạng thái.** Nếu chuyển trạng thái bị rollback thì dòng nhật ký cũng biến mất theo — nhật ký không được kể một việc chưa từng xảy ra.

## 6. Danh sách sự kiện

`vai` quyết định cách hiển thị (§8), không phải chỗ ghi.

| Khoá sự kiện | Vai | Ghi tại | Ghi chú kèm |
|---|---|---|---|
| `khoa_gui_duyet` | khoa | `gui_duyet()` | lý do yêu cầu |
| `khoa_thu_hoi` | khoa | `thu_hoi()` | |
| `quan_ly_duyet` | quan_ly | `duyet()` | tư cách duyệt; số dòng đã điều chỉnh |
| `quan_ly_tu_choi` | quan_ly | `tu_choi()` | lý do |
| `quan_ly_huy_phieu` | quan_ly | `huy()` | |
| `khoa_xin_sua` | khoa | `xin_sua()` | tóm tắt số lượng xin đổi |
| `quan_ly_duyet_sua` | quan_ly | `duyet_sua()` | **vá §7 mục 3b** |
| `quan_ly_tu_choi_sua` | quan_ly | `tu_choi_sua()` | lý do |
| `don_tao` | he_thong | `duyet_va_tao_don` **và** `_dam_bao_phieu_tu_duyet` | mã đơn |
| `miyano_xac_nhan` | miyano | `Sales Order.on_update`, workflow → `Đã xác nhận` | |
| `miyano_bao_gia` | miyano | nt, → `Chờ khách đồng ý` | hạn hiệu lực |
| `miyano_tu_choi` | miyano | nt, → `Từ chối` | lý do |
| `khach_dong_y` | quan_ly | `portal_order_accept(dong_y)` | |
| `khach_khong_dong_y` | quan_ly | `portal_order_accept(khong_dong_y)` | lý do |
| `khach_gui_lai_bao_gia` | quan_ly | `portal_order_sua_so_luong` | dòng đã đổi |
| `khach_huy_don` | quan_ly | `portal_order_huy` | lý do |
| `giao_hang` | miyano | `on_delivery_note_submit` | đợt mấy, phần trăm |
| `hoa_don` | miyano | `Sales Invoice.on_submit` | số hoá đơn |

## 7. Khoá, không phải nhãn

`su_kien` lưu **khoá nội bộ** (`khoa_gui_duyet`), nhãn tiếng Việt sống ở `frontend/src/format.js`.

Đây là Ruling P54 của repo, đã trả giá một lần: trước P54 chính chuỗi hiển thị là khoá lọc **và** đi trong URL, nên đổi một chữ tiếng Việt làm chết mọi link đã gửi cho bệnh viện. Nhật ký này còn nặng hơn — nó là bản ghi **vĩnh viễn**: một khoá đã ghi xuống thì không sửa được nữa, nên nó tuyệt đối không được mang theo một quyết định biên tập.

## 8. Luật hiển thị tên và số điện thoại

Một hàm duy nhất ở backend trả về `{ten, dien_thoai}` cho một tài khoản, mở rộng từ `portal_context.ten_nguoi_dung()` đã có:

- **Tên**: `User.full_name`, lui về chính email khi không tra được (giữ nguyên hành vi hiện tại).
- **Số**: `User.mobile_no`, lui về `User.phone`, rỗng nếu cả hai trống.
- **Thiếu số thì không in gì** — không in ô trống, không in dấu gạch. Một dấu gạch ở chỗ đáng lẽ có số điện thoại là một câu hỏi mà màn hình không trả lời được.

**Luật riêng cho `vai = miyano`: chỉ tên và số, KHÔNG BAO GIỜ email.**

Đây là ranh giới có chủ ý. Chủ đầu tư chốt cho bệnh viện thấy tên và số nhân sự Miyano để gọi được đúng người — đó là *danh tính để liên hệ*. Email đăng nhập là *định danh kỹ thuật của hệ thống Miyano*, không phục vụ mục đích đó. Repo đã có sẵn lý lẽ này từ 21/08 cho nửa bệnh viện, nguyên văn: *"Email là ĐỊNH DANH kỹ thuật — đúng để gửi thư và để so quyền, sai để đưa cho một điều dưỡng trưởng đọc."* Bản thiết kế này **mở rộng đúng luật đó ra ngoài** thay vì đặt ra luật mới.

**Nửa bệnh viện giữ nguyên hành vi hiện tại** (tên, kèm email tài khoản khi hai thứ khác nhau), **cộng thêm số**. Không bỏ dòng email: với sáu tài khoản cấp đơn vị cũ, đó là thứ **duy nhất** phân biệt được ai với ai, và những phiếu cũ sẽ mãi mang tài khoản đó.

Áp cho **cả** khối truy vết đang có (`KhoiTruyVet.vue`) **lẫn** dòng thời gian mới — theo đúng Đ2.

## 9. Hiển thị trên màn chi tiết

**Giữ thanh năm chấm, thêm danh sách sự kiện bên dưới nó.**

Thanh năm chấm trả lời *"đang ở đâu"* trong một cái liếc; danh sách trả lời *"đã đi qua những gì, ai làm"*. Viettel Post cũng có cả hai. Thêm vào rẻ hơn và ít rủi ro hơn là thay thế.

Mỗi dòng: **thời điểm · việc · ai (tên + số) · ghi chú**. Xếp theo thời gian, việc mới nhất ở dưới cùng — vòng lặp hiện ra thành các dòng lặp lại, đọc ra ngay là đơn này đã đi tới đi lui mấy lần.

**Đơn cũ không có dòng nhật ký nào** (tạo trước khi tính năng bật): suy **hai** dòng từ dữ liệu đã ghi sẵn trên phiếu — `khoa_gui_duyet` từ `nguoi_yeu_cau`/`thoi_diem_gui`, `quan_ly_duyet` từ `nguoi_duyet`/`thoi_diem_duyet` — và **chỉ khi** không có dòng nhật ký cùng loại.

Đây **không** phải diễn giải kiểu `Version` mà §4 vừa bác: bốn trường đó là **sự kiện đã ghi tường minh, có người và có mốc giờ**, chỉ nằm trên chứng từ thay vì trong sổ. Không suy ra gì mới cả. Không backfill: dữ liệu cũ giữ nguyên trong CSDL.

## 10. Phạm vi quyền

Một endpoint đọc, nhận `de_xuat` **hoặc** `sales_order`. Nó **không** tự chế bộ lọc: gọi lại đúng chốt mà phần còn lại của cổng đang gọi — `_phieu_cua_toi()` cho phiếu, `dam_bao_xem_duoc()` cho đơn — rồi mới lấy dòng nhật ký theo chứng từ đã qua cửa.

Lý do không tự lọc: một bộ lọc phạm vi thứ hai viết riêng cho nhật ký là nơi thứ hai để hở. Endpoint phải hỏi **đúng câu** mà `pham_vi_don()` hỏi, không phải một câu tương đương.

Ghi vào `test_pham_vi_endpoint.py::DA_AP_PHAM_VI` — module mới không tự động bị lưới đếm ngược soi tới.

## 11. Không làm

- **Không** màn quản lý thành viên (bước 9) — Đ5 làm nó chưa cần thiết.
- **Không** backfill lịch sử. Không có cách nào biết người thật nào đã bấm một nút năm tháng trước; bịa ra là tệ hơn để trống.
- **Không** sửa/xoá dòng nhật ký, kể cả từ Desk.
- **Không** vị trí địa lý. Viettel Post có bưu cục; ở đây không có gì tương đương, và một cột trống là một cột nói dối.
- **Không** đổi các hàm `bao_*` hiện có. Nhật ký ghi **cạnh** chúng, không thay chúng — thông báo là thứ đẩy đi, nhật ký là thứ tra lại.

## 12. Rủi ro đã biết

| Rủi ro | Cách xử |
|---|---|
| Ghi nhật ký hỏng lặng lẽ → mất sự kiện | `log_error` như các hàm `bao_*`; test khẳng định dòng nhật ký ĐƯỢC ghi cho từng sự kiện |
| Số điện thoại cũ, người đã nghỉ | Thuộc quy trình cấp/khoá tài khoản của Miyano (Đ3) — không phải thứ code giải được |
| Sáu tài khoản đơn vị cũ mãi ở cấp đơn vị | Chấp nhận. Dữ liệu cũ không hồi tố được; màn hình phải xử tử tế ca đó **vĩnh viễn**, không phải như vá tạm |
| Lộ tên và số nhân sự Miyano ra ngoài | Quyết định của chủ đầu tư (Đ1, Đ2). Ranh giới kỹ thuật: tên + số, **không bao giờ email** (§8) |
| Nhật ký phình to | Mỗi yêu cầu vài chục dòng. Nếu về sau cần, cắt theo `thoi_diem` — chưa làm bây giờ |

## 13. Cách kiểm chứng

- **Mỗi sự kiện một test**: thực hiện thao tác thật qua đúng đường mã sản phẩm dùng, rồi khẳng định dòng nhật ký sinh ra với đúng `su_kien`, `nguoi_thao_tac`, `vai`. Không gán tay bản ghi rồi đo lại chính nó — đó là kiểu fixture-che-cổng dự án đã dính bảy lần.
- **Vế âm của phạm vi**: nhân viên khoa A đọc nhật ký của một yêu cầu thuộc khoa B → `PermissionError`. Bệnh viện X đọc của bệnh viện Y → nt.
- **Chỉ-thêm**: sửa một dòng đã ghi → chặn; xoá → chặn.
- **Ghi hỏng không làm hỏng thao tác**: giả lập lỗi ở khâu ghi nhật ký, khẳng định chuyển trạng thái vẫn thành công và lỗi vẫn được log.
- **Vòng lặp**: một yêu cầu đi qua *gửi → từ chối → gửi lại → duyệt → xin sửa → duyệt sửa* phải cho ra **sáu** dòng theo đúng thứ tự, không phải hai.
- **Ca thiếu số điện thoại**: tài khoản không có số → không in gì ở chỗ số, tên vẫn hiện.
- **Ca tài khoản cấp đơn vị**: tên hiện là tên đơn vị, email tài khoản vẫn hiện kèm (nó là thứ duy nhất phân biệt được).
