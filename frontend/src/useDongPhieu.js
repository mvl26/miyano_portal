import { ref, computed } from 'vue'
import api from './api'
import { showToast } from './toast'

// Giá trị đặc biệt cho mục "➕ Tạo vật tư mới…" trong ô chọn vật tư — không
// phải tên (name) của một vật tư thật, chỉ dùng để nhận ra người dùng vừa
// chọn mục này rồi trả ô chọn về rỗng ngay (xem onVatTuSelect bên dưới).
export const MUC_TAO_MOI = '__tao_moi__'

// Composable dùng chung cho PhieuNhapDetail.vue và PhieuXuatDetail.vue: giữ
// trạng thái modal "Tạo vật tư mới…" mở từ ô chọn của một dòng (Task 4), VÀ
// (Task 10/11) toàn bộ luồng import/export Excel của bảng dòng — file mẫu,
// chọn tệp + tải lên + đọc file, nối dòng đọc được vào cuối bảng, đếm dòng
// chưa xử lý để chặn lưu, và mở modal tạo nhanh vật tư từ một dòng import.
//
// Hai màn hình khác nhau ở NHỮNG ĐIỂM SAU — mỗi điểm được tiêm vào qua tham
// số thay vì rẽ nhánh bằng cờ isXuat bên trong composable:
//   - onAssigned(row)     : chạy sau khi một dòng được gán vật tư (qua modal
//                           tạo nhanh, dù mở từ ô chọn hay từ nút "Tạo vật tư
//                           mới" của một dòng import). Xuất kho truyền
//                           onVatTuChange(row) vào để nạp lô cho dòng đó.
//   - extraRowFields(r)   : nhận một dòng thô từ kho_dong_phieu_doc_file, trả
//                           về các trường CHỈ riêng màn đó cần gộp thêm vào
//                           dòng chung. Phiếu nhập có don_gia/han_su_dung.
//
//                           ĐÂY LÀ KÊNH DUY NHẤT để một màn bơm trường riêng
//                           vào dòng import — composable KHÔNG biết gì về
//                           trường nào template của màn đó cần. Mọi trường mà
//                           <template> của màn đọc KHÔNG PHÒNG THỦ (không có
//                           `v-if`/`?? default`/optional-chaining bọc ngoài)
//                           BẮT BUỘC phải có mặt trên MỌI dòng ngay từ khi
//                           push, kể cả dòng `trang_thai` là "ma_moi"/"loi" —
//                           nếu không dòng đó sẽ thiếu trường và ném lỗi
//                           render ngay khi Vue vẽ nó, TRƯỚC khi bất kỳ
//                           callback nào (kể cả onRowImported) có cơ hội chạy.
//                           Ví dụ cụ thể: PhieuXuatDetail.vue có
//                           `v-else-if="r._lots.length"` không phòng thủ ở
//                           dòng chọn lô — Task 11 PHẢI trả `_lots: []`,
//                           `_lotsLoading: false`, `_hetHan: false`,
//                           `xac_nhan_het_han: false` từ extraRowFields (y hệt
//                           blankRow() hiện có), KHÔNG được trông cậy vào
//                           onRowImported để khởi tạo các trường này — dòng đã
//                           render (và có thể đã vỡ) trước khi onRowImported
//                           kịp chạy.
//   - onRowImported(row)  : chạy MỘT LẦN cho MỌI dòng vừa nối vào bảng sau
//                           import — kể cả dòng "ma_moi"/"loi" chưa có
//                           vat_tu, KHÔNG được gác lại bằng `if (row.vat_tu)`
//                           hay tương tự bên trong hàm truyền vào. Phiếu nhập
//                           không cần bước gì thêm nên không truyền. Phiếu
//                           xuất (Task 11) dùng để nạp lô cho dòng đã khớp
//                           mã (trang_thai == "khop") — nhưng chính callback
//                           đó, không phải composable, chịu trách nhiệm tự
//                           kiểm tra row.vat_tu trước khi gọi kho_lo_goi_y().
//
// Tham số (đối tượng):
//   doc            - đối tượng reactive của phiếu (PhieuNhapDetail/
//                    PhieuXuatDetail đều dùng reactive({...})). Đọc doc.items
//                    TẠI THỜI ĐIỂM gán, không giữ tham chiếu mảng cũ — Xuất
//                    kho có lúc gán lại hẳn doc.items = savedItems.map(...)
//                    sau khi lưu, giữ tham chiếu cũ sẽ ghi nhầm vào mảng đã bỏ.
//   vatTuList      - ref chứa danh mục vật tư đang tải trong bộ nhớ của màn
//                    hình; được thêm vật tư vừa tạo vào để các dòng khác cùng
//                    mã cũng khớp ngay, không cần tải lại danh mục.
//   onAssigned     - (tuỳ chọn) xem trên.
//   loai           - 'nhap' | 'xuat', tham số `loai` gửi cho
//                    kho_dong_phieu_mau/kho_dong_phieu_doc_file. Bắt buộc nếu
//                    màn có dùng import/export (mauUrl/onImportFile).
//   DOCTYPE        - doctype của phiếu ('Customer Stock Receipt' /
//                    'Customer Stock Issue'), dùng để dựng exportUrl. Bắt
//                    buộc nếu màn có dùng export.
//   extraRowFields - (tuỳ chọn) xem trên.
//   onRowImported  - (tuỳ chọn) xem trên.
//
// Trả về: { MUC_TAO_MOI, modalOpen, modalInitial, modalRowIdx, onVatTuSelect,
// onVatTuSaved, importing, importInput, mauUrl, exportUrl, dongChuaXuLy,
// onImportFile, moTaoTuDong } — dùng trực tiếp trong <template> của màn gọi.
// PhieuXuatDetail.vue hiện chỉ dùng năm cái đầu (chưa nối import/export —
// đó là việc của Task 11); các trường mới không phá gì vì không <template>
// nào của phiếu xuất tham chiếu tới chúng cho tới khi Task 11 nối vào.
//
// Bất biến của backend (kho_dong_phieu_doc_file) mà giao diện PHẢI tôn
// trọng: dòng `trang_thai == "loi"` LUÔN có `vat_tu == ""`. Rẽ nhánh hiển thị
// theo `_trang_thai`, KHÔNG theo "có vat_tu hay không".
export function useDongPhieu({
  doc,
  vatTuList,
  onAssigned,
  loai,
  DOCTYPE,
  extraRowFields,
  onRowImported,
} = {}) {
  const modalOpen = ref(false)
  const modalInitial = ref({})
  const modalRowIdx = ref(-1)

  // Chọn "➕ Tạo vật tư mới…" trong ô chọn: mở modal cho ĐÚNG dòng đó và trả
  // ô chọn về rỗng, để dòng không bị kẹt ở một giá trị không phải vật tư nào.
  //
  // CỐ Ý KHÔNG xoá `_trang_thai`/`_loi` khi người dùng chọn một vật tư thật
  // cho một dòng đọc từ tệp. `_loi` là toàn bộ bằng chứng mà bước đọc tệp thu
  // được, còn client chỉ kiểm lại được một lớp (số lượng > 0). Xoá nó đi thì
  // hai lớp lỗi lọt qua cả client lẫn server:
  //   - "Hạn sử dụng không hợp lệ" → han_su_dung = null → lô vào sổ KHÔNG CÓ
  //     hạn dùng. ledger.get_lot_balances() xếp lô không hạn xuống CUỐI FEFO
  //     và _chan_lo_het_han_chua_xac_nhan() bỏ qua dòng không có han_su_dung,
  //     nên lô đó vĩnh viễn miễn chốt hạn dùng ở mọi lần xuất về sau — chỉ gỡ
  //     được bằng huỷ phiếu + phiếu đảo. Không trường nào ở server bắt lại:
  //     han_su_dung không reqd, _validate_items_present chỉ kiểm vat_tu/so_lo.
  //   - "Thiếu/sai Đơn giá" → don_gia = 0, dòng nhập giá 0.
  // Dòng vẫn LƯU NHÁP ĐƯỢC (xem dongChuaXuLy bên dưới) — nền đỏ và danh sách
  // lý do chỉ ở lại để người dùng còn thấy dòng đó có gì chưa xử lý, cho tới
  // khi họ sửa tệp và nạp lại.
  function onVatTuSelect(row, idx) {
    if (row.vat_tu !== MUC_TAO_MOI) return
    row.vat_tu = ''
    modalRowIdx.value = idx
    modalInitial.value = { ma_vat_tu: row._ma_vat_tu || '', ten_vat_tu: '', dvt: '' }
    modalOpen.value = true
  }

  // Gán vật tư vừa tạo vào một dòng.
  //
  // Chỉ dòng 'ma_moi' mới được xoá trạng thái import: với dòng đó, MÃ LẠ là
  // vấn đề duy nhất và nó vừa được giải quyết, nên nền vàng và cờ phải biến
  // mất. Dòng 'loi' thì khác — nó lọt vào đây khi mã của nó trùng mã vừa tạo
  // (một tệp có hai dòng cùng mã mới, một dòng sạch một dòng sai hạn dùng là
  // đủ) và nó CÒN mang những lý do khác mà client không kiểm lại được; xoá
  // `_loi` ở đó là vứt đúng bằng chứng nói ở onVatTuSelect(). Vẫn gán
  // `vat_tu` — công người dùng bấm "Tạo vật tư mới" không mất, và dòng thành
  // lưu nháp được — chỉ giữ nguyên nền đỏ + lý do.
  function ganVatTuVaoDong(row, vt) {
    row.vat_tu = vt.name
    if (row._trang_thai !== 'loi') {
      row._trang_thai = 'khop'
      row._loi = []
    }
    if (onAssigned) onAssigned(row)
  }

  function onVatTuSaved(vt) {
    // Cập nhật danh mục trong bộ nhớ TRƯỚC khi gán vào dòng, để mọi dòng khác
    // cùng mã cũng khớp được ngay mà không phải tải lại danh mục.
    if (!vatTuList.value.some((v) => v.name === vt.name)) vatTuList.value.push(vt)

    // Mọi dòng đang chờ đúng mã này đều khớp theo — import 20 dòng cùng một
    // mã lạ chỉ phải bấm "Tạo vật tư mới" một lần.
    const ma = (vt.ma_vat_tu || '').toLowerCase()
    if (ma) {
      for (const r of doc.items) {
        if (!r.vat_tu && (r._ma_vat_tu || '').toLowerCase() === ma) {
          ganVatTuVaoDong(r, vt)
        }
      }
    }

    // Dòng mở modal (nếu có) có thể đã được khớp ở vòng lặp trên (khi mã của
    // nó trùng vt.ma_vat_tu) — chỉ gán lại/gọi onAssigned nếu chưa, để không
    // xử lý hai lần cùng một dòng.
    if (modalRowIdx.value >= 0) {
      const row = doc.items[modalRowIdx.value]
      if (row && row.vat_tu !== vt.name) {
        ganVatTuVaoDong(row, vt)
      }
    }
    modalOpen.value = false
    modalRowIdx.value = -1
  }

  const importing = ref(false)
  const importInput = ref(null)
  const mauUrl = api.khoDownloadUrl('kho_dong_phieu_mau') + '?loai=' + encodeURIComponent(loai)
  const exportUrl = computed(
    () =>
      api.khoDownloadUrl('kho_dong_phieu_export') +
      `?doctype=${encodeURIComponent(DOCTYPE)}&name=${encodeURIComponent(doc.name)}`
  )

  // Dòng đọc từ tệp bị lỗi mà CHƯA gán được vật tư thì không cho lưu.
  //
  // Điều kiện cũ (`r._trang_thai === 'loi' || !r.vat_tu`) chặn theo cờ 'loi'
  // bất kể dòng đã được sửa hay chưa, mà không có đường nào xoá cờ đó cho một
  // dòng sửa tại chỗ — "Lưu nháp" bị khoá vĩnh viễn, chỉ thoát bằng cách xoá
  // dòng. Vế `&& !r.vat_tu` mở đúng chỗ đó ra: người dùng chọn được vật tư cho
  // dòng đỏ là lưu nháp được ngay, TRONG KHI cờ 'loi' và `_loi` vẫn nằm
  // nguyên trên màn hình làm bằng chứng (xem onVatTuSelect). Đây là lý do
  // không đơn giản hoá được thành `!r.vat_tu`.
  //
  // Dòng 'ma_moi' và dòng gõ tay còn trống KHÔNG lọt: chúng rơi vào chốt
  // `!r.vat_tu` của validateClient() ở mỗi màn, vốn nêu đúng số dòng
  // ("Dòng 3: chưa chọn vật tư."). Server chặn lần thứ ba bằng
  // _validate_items_present.
  const dongChuaXuLy = computed(
    () => doc.items.filter((r) => r._trang_thai === 'loi' && !r.vat_tu).length
  )

  async function onImportFile(e) {
    const f = e.target.files && e.target.files[0]
    if (!f) return
    importing.value = true
    try {
      const uploaded = await api.uploadFile(f)
      const kq = await api.callKho('kho_dong_phieu_doc_file', {
        loai,
        file_url: uploaded.file_url,
      })
      // NỐI vào cuối, không xoá dòng đang có — người dùng có thể đã gõ tay
      // vài dòng trước khi import.
      for (const r of kq.rows) {
        const row = {
          vat_tu: r.vat_tu || '',
          so_lo: r.so_lo,
          so_luong: r.so_luong || 0,
          ghi_chu: r.ghi_chu || '',
          _trang_thai: r.trang_thai,
          _loi: r.loi || [],
          _loi_line: r.line,
          _ma_vat_tu: r.ma_vat_tu,
          _ten_vat_tu: r.ten_vat_tu,
          _dvt: r.dvt,
          _quy_cach: r.quy_cach,
          _nhom: r.nhom,
          ...(extraRowFields ? extraRowFields(r) : {}),
        }
        doc.items.push(row)
        if (onRowImported) onRowImported(row)
      }
      showToast(`Đã đọc ${kq.total} dòng từ tệp.`)
    } catch (err) {
      showToast(err.message || 'Không đọc được tệp.', 'error')
    } finally {
      importing.value = false
      if (importInput.value) importInput.value.value = ''
    }
  }

  // Mở modal tạo nhanh cho ĐÚNG dòng import, điền sẵn mọi thứ đọc được từ
  // tệp (mã, tên, ĐVT, quy cách, nhóm).
  function moTaoTuDong(row, idx) {
    modalRowIdx.value = idx
    modalInitial.value = {
      ma_vat_tu: row._ma_vat_tu || '',
      ten_vat_tu: row._ten_vat_tu || '',
      dvt: row._dvt || '',
      quy_cach: row._quy_cach || '',
      nhom: row._nhom || '',
    }
    modalOpen.value = true
  }

  return {
    MUC_TAO_MOI,
    modalOpen,
    modalInitial,
    modalRowIdx,
    onVatTuSelect,
    onVatTuSaved,
    importing,
    importInput,
    mauUrl,
    exportUrl,
    dongChuaXuLy,
    onImportFile,
    moTaoTuDong,
  }
}
