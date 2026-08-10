import { ref, computed } from 'vue'
import api from './api'
import { showToast } from './toast'

// Composable dùng chung cho các màn nhập Excel theo khung ba bước "chọn tệp →
// xem trước → xác nhận" (ImportTonDau.vue, ImportDanhMuc.vue). Cả hai method
// preview trả về CÙNG một hình dạng { total, ok_count, error_count, summary,
// rows_ok, rows_error } — nên phần chọn tệp/upload/gọi preview/gọi commit và
// xử lý lỗi tải tệp giống hệt nhau giữa hai màn, chỉ khác tên method backend
// và thông điệp toast. Phần KHÁC nhau (cột bảng xem trước, nhãn badge, màn
// kết quả) vẫn do từng <template> tự vẽ — composable này không biết gì về nội
// dung dòng.
//
// Tham số:
//   previewMethod - tên method kho_*_preview (vd. "kho_import_preview")
//   commitMethod  - tên method kho_*_commit
//   successMsg    - thông điệp toast khi xác nhận thành công
//   failMsg       - thông điệp toast mặc định khi xác nhận lỗi (server có thể
//                   trả thông điệp cụ thể hơn, dùng cái đó nếu có)
export function useImportWizard({ previewMethod, commitMethod, successMsg, failMsg }) {
  const fileInput = ref(null)
  const selectedFile = ref(null)
  const fileUrl = ref('') // file_url của lần upload GẦN NHẤT — preview và commit dùng chung

  const previewing = ref(false)
  const committing = ref(false)
  const previewError = ref('')
  const preview = ref(null) // kết quả *_preview
  const result = ref(null) // kết quả *_commit (khi đã xác nhận xong)

  const canConfirm = computed(
    () => !!preview.value && preview.value.error_count === 0 && preview.value.ok_count > 0
  )

  function onPickFile(e) {
    const f = e.target.files && e.target.files[0]
    selectedFile.value = f || null
    // Chọn tệp khác thì bỏ kết quả preview cũ — tránh xác nhận nhầm dữ liệu
    // của tệp trước đó trong khi màn hình đang hiển thị tệp mới.
    preview.value = null
    fileUrl.value = ''
    previewError.value = ''
    result.value = null
  }

  async function onPreview() {
    if (!selectedFile.value) return
    previewing.value = true
    previewError.value = ''
    preview.value = null
    try {
      const uploaded = await api.uploadFile(selectedFile.value)
      fileUrl.value = uploaded.file_url
      preview.value = await api.callKho(previewMethod, { file_url: fileUrl.value })
    } catch (e) {
      previewError.value = e.message || 'Không đọc được tệp. Vui lòng kiểm tra lại định dạng.'
    } finally {
      previewing.value = false
    }
  }

  async function onCommit() {
    if (!canConfirm.value || committing.value) return
    committing.value = true
    try {
      result.value = await api.callKho(commitMethod, { file_url: fileUrl.value })
      showToast(successMsg)
    } catch (e) {
      showToast(e.message || failMsg, 'error')
    } finally {
      committing.value = false
    }
  }

  function startOver() {
    selectedFile.value = null
    fileUrl.value = ''
    preview.value = null
    previewError.value = ''
    result.value = null
    if (fileInput.value) fileInput.value.value = ''
  }

  return {
    fileInput, selectedFile, fileUrl,
    previewing, committing, previewError, preview, result,
    canConfirm, onPickFile, onPreview, onCommit, startOver,
  }
}
