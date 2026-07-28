import { reactive } from 'vue'

// Toast store tối giản (không thêm dependency). Danh sách phản ứng + hàm bắn toast.
export const toasts = reactive([])

let seq = 0

// showToast(message, type) — type: 'success' (mặc định) | 'error'. Tự ẩn ~2.5s.
export function showToast(message, type = 'success') {
  const id = ++seq
  toasts.push({ id, message, type })
  setTimeout(() => {
    const i = toasts.findIndex((t) => t.id === id)
    if (i !== -1) toasts.splice(i, 1)
  }, 2500)
  return id
}

export default { toasts, showToast }
