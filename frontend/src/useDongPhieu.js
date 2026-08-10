import { ref } from 'vue'

// Giá trị đặc biệt cho mục "➕ Tạo vật tư mới…" trong ô chọn vật tư — không
// phải tên (name) của một vật tư thật, chỉ dùng để nhận ra người dùng vừa
// chọn mục này rồi trả ô chọn về rỗng ngay (xem onVatTuSelect bên dưới).
export const MUC_TAO_MOI = '__tao_moi__'

// Composable dùng chung cho PhieuNhapDetail.vue và PhieuXuatDetail.vue: giữ
// trạng thái modal "Tạo vật tư mới…" mở từ ô chọn của một dòng, và xử lý gán
// vật tư vừa tạo vào đúng dòng đó. Hai màn hình chỉ khác nhau ở MỘT điểm —
// sau khi gán, Xuất kho còn phải nạp lô cho dòng (như khi người dùng tự đổi
// ô chọn) — nên điểm khác đó được tiêm vào qua tham số onAssigned thay vì rẽ
// nhánh bằng cờ bên trong composable.
//
// Tham số (đối tượng):
//   doc        - đối tượng reactive của phiếu (PhieuNhapDetail/PhieuXuatDetail
//                đều dùng reactive({...})). Đọc doc.items TẠI THỜI ĐIỂM gán,
//                không giữ tham chiếu mảng cũ — Xuất kho có lúc gán lại hẳn
//                doc.items = savedItems.map(...) sau khi lưu, giữ tham chiếu
//                cũ sẽ ghi nhầm vào mảng đã bỏ.
//   vatTuList  - ref chứa danh mục vật tư đang tải trong bộ nhớ của màn hình;
//                được thêm vật tư vừa tạo vào để các dòng khác cùng mã cũng
//                khớp ngay, không cần tải lại danh mục.
//   onAssigned - (tuỳ chọn) hàm chạy SAU khi vật tư vừa tạo được gán vào
//                dòng, nhận đúng dòng đó làm tham số. Đây là chỗ
//                PhieuXuatDetail truyền onVatTuChange(row) vào để nạp lô;
//                PhieuNhapDetail không cần bước này nên có thể bỏ qua.
//
// Trả về: { MUC_TAO_MOI, modalOpen, modalInitial, modalRowIdx, onVatTuSelect,
// onVatTuSaved } — dùng trực tiếp trong <template> của màn gọi.
//
// Task 10/11 sẽ mở rộng composable NÀY thêm luồng import Excel (chưa viết ở
// đây) — vì vậy state được đặt tên theo "dòng phiếu" nói chung, không riêng
// cho luồng chọn thủ công trong ô select.
//
// Ba trường đọc/ghi trên `row` bên dưới — `row._ma_vat_tu` (đọc, prefill mã
// khi mở modal), `row._trang_thai` và `row._loi` (ghi, đánh dấu dòng "khớp"
// sau khi gán) — hiện KHÔNG có màn nào đọc lại (đã grep xác nhận). Đây là chỗ
// móc sẵn cho luồng import Excel của Task 10/11 (dòng đọc từ file mang mã thô
// chưa khớp danh mục, và trạng thái khớp/lỗi của từng dòng); vô hại ở luồng
// chọn thủ công hiện tại vì không <template> nào tham chiếu tới chúng.
export function useDongPhieu({ doc, vatTuList, onAssigned } = {}) {
  const modalOpen = ref(false)
  const modalInitial = ref({})
  const modalRowIdx = ref(-1)

  // Chọn "➕ Tạo vật tư mới…" trong ô chọn: mở modal cho ĐÚNG dòng đó và trả
  // ô chọn về rỗng, để dòng không bị kẹt ở một giá trị không phải vật tư nào.
  function onVatTuSelect(row, idx) {
    if (row.vat_tu !== MUC_TAO_MOI) return
    row.vat_tu = ''
    modalRowIdx.value = idx
    modalInitial.value = { ma_vat_tu: row._ma_vat_tu || '', ten_vat_tu: '', dvt: '' }
    modalOpen.value = true
  }

  function onVatTuSaved(vt) {
    // Cập nhật danh mục trong bộ nhớ TRƯỚC khi gán vào dòng, để mọi dòng khác
    // cùng mã cũng khớp được ngay mà không phải tải lại danh mục.
    if (!vatTuList.value.some((v) => v.name === vt.name)) vatTuList.value.push(vt)
    if (modalRowIdx.value >= 0) {
      const row = doc.items[modalRowIdx.value]
      row.vat_tu = vt.name
      row._trang_thai = 'khop'
      row._loi = []
      if (onAssigned) onAssigned(row)
    }
    modalOpen.value = false
    modalRowIdx.value = -1
  }

  return { MUC_TAO_MOI, modalOpen, modalInitial, modalRowIdx, onVatTuSelect, onVatTuSaved }
}
