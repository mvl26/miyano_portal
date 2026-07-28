import { ref, onMounted, onUnmounted } from 'vue'

// Composable: true khi viewport < 900px (khớp breakpoint mockup).
// Dùng để chọn bố cục desktop (bảng/timeline ngang/modal) vs mobile
// (thẻ card/timeline dọc/bottom-sheet).
export function useIsMobile() {
  const isMobile = ref(false)
  let mql
  const update = () => {
    isMobile.value = window.matchMedia('(max-width: 900px)').matches
  }
  onMounted(() => {
    mql = window.matchMedia('(max-width: 900px)')
    update()
    mql.addEventListener('change', update)
  })
  onUnmounted(() => {
    if (mql) mql.removeEventListener('change', update)
  })
  return isMobile
}
