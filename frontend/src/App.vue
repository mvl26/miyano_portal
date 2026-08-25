<script setup>
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { store } from './store'
import { logout } from './api'
import api from './api'
import ToastHost from './ToastHost.vue'
import { capNhatChoDuyetCount } from './cho-duyet'

const route = useRoute()

const NAV = [
  { to: '/dashboard', icon: '🏠', label: 'Tổng quan', short: 'Tổng quan', key: 'dashboard' },
  // Task 10 (gộp "Đặt hàng" và "Lập phiếu", 21/08/2026) — MỘT mục duy nhất
  // cho việc "đi mua đồ" (QĐ-G5). Ba mục cũ ("Đặt hàng" `/catalog`, "Giỏ
  // hàng" `/cart`, "Lập phiếu đề xuất" `/de-xuat/lap`) đã gộp vào đây: hai
  // mục cùng nghĩa là để lộ lịch sử thi công ra mặt người dùng, còn giỏ
  // hàng là một BƯỚC của việc đặt hàng chứ không phải một đích đến ai đó mở
  // cổng lên để vào xem. Tên giữ nguyên "Đặt hàng" theo chủ đầu tư.
  { to: '/dat-hang', icon: '🛒', label: 'Đặt hàng', short: 'Đặt hàng', key: 'dat-hang' },
  // Task 11 (QĐ-G11, 21/08/2026) — MỘT mục cho "xem đồ mình xin đã tới
  // đâu". Hai mục cũ ("Đơn hàng của tôi" `/orders`, "Đề xuất mua"
  // `/de-xuat`) là HAI danh sách của CÙNG MỘT THỨ: một yêu cầu nằm ở mục
  // sau khi còn là phiếu rồi nhảy sang mục trước sau khi duyệt — nhân
  // viên phải biết trước giai đoạn nội bộ mới tìm lại được yêu cầu của
  // chính mình. Hiện cho MỌI vai trò: nhân viên khoa thấy yêu cầu khoa
  // mình, quản lý thấy toàn viện; server (`portal_yeu_cau_cua_toi` +
  // `pham_vi_don()`) đã lo phạm vi, mục nav không cần v-if theo vai trò.
  { to: '/yeu-cau', icon: '📋', label: 'Yêu cầu của tôi', short: 'Yêu cầu', key: 'yeu-cau' },
  // Man luong duyet (Task 5) — hàng chờ của quản lý. `requireQuanLy: true`
  // lọc ở `navItems` bên dưới, ĐÚNG khoá `me.la_quan_ly` — KHÔNG tự suy từ
  // `vai_tro === 'Quản lý'`. Lý do: kế hoạch sau thêm uỷ quyền tạm thời,
  // khi đó một Nhân viên khoa đang được uỷ quyền vẫn phải thấy mục này —
  // so chuỗi vai_tro sẽ bỏ sót và gãy lặng lẽ.
  { to: '/duyet', icon: '✅', label: 'Duyệt', short: 'Duyệt', key: 'duyet', duyet: true, requireQuanLy: true },
  { to: '/kho', icon: '🏭', label: 'Kho của tôi', short: 'Kho', key: 'kho' },
  { to: '/invoices', icon: '🧾', label: 'Hoá đơn & công nợ', short: 'Hoá đơn', key: 'invoices' },
  // Brief 2026-08-15 (trang thông báo) — mục nav MỚI, badge = số chưa đọc.
  { to: '/thong-bao', icon: '🔔', label: 'Thông báo', short: 'Thông báo', key: 'thong-bao', thongBao: true },
  { to: '/profile', icon: '🏥', label: 'Hồ sơ đơn vị', short: 'Hồ sơ', key: 'profile' },
]

// Bottom nav (mobile): Thông báo truy cập qua "Thêm" (Hồ sơ) như Hoá đơn —
// badge vẫn hiện trên chính mục "Thêm" (xem `isActive` bên dưới) để không
// mất tín hiệu.
//
// Task 10 — "Giỏ hàng" rời thanh dưới cùng lúc rời sidebar (nó là một BƯỚC
// của màn Đặt hàng, không phải một cửa).
//
// Task 11 — "Đơn hàng" và "Đề xuất" gộp thành MỘT mục "Yêu cầu": thanh
// dưới còn NĂM mục, không phải sáu như mockup gốc. CỐ Ý không lấp chỗ
// trống bằng một mục khác — lấp cho đủ số là dựng lại đúng thứ task này
// vừa dỡ (một cửa tồn tại vì có ô trống, không vì có người cần nó).
const BNAV = [
  { to: '/dashboard', icon: '🏠', short: 'Tổng quan', key: 'dashboard' },
  { to: '/dat-hang', icon: '🛒', short: 'Đặt hàng', key: 'dat-hang' },
  { to: '/yeu-cau', icon: '📋', short: 'Yêu cầu', key: 'yeu-cau' },
  { to: '/kho', icon: '🏭', short: 'Kho', key: 'kho' },
  { to: '/profile', icon: '☰', short: 'Thêm', key: 'profile', thongBao: true },
]

const pageTitle = computed(() => route.meta.title || 'Cổng khách hàng')
const chuaDocThongBao = computed(() => store.chuaDocThongBao)
const choDuyetCount = computed(() => store.choDuyetCount)
// Việc (e) — badge hiện "200+" khi hàng chờ chạm trần một lời gọi. Con số
// trần trụi "200" là con số SAI đọc như con số đúng: quản lý duyệt hết 200
// phiếu rồi tưởng xong việc.
const choDuyetNhan = computed(() => `${store.choDuyetCount}${store.choDuyetBiCat ? '+' : ''}`)

// Man luong duyet (Task 5) — mục "Duyệt" chỉ hiện cho `me.la_quan_ly`. Lọc
// TẠI ĐÂY (computed, phản ứng theo `store.me`) thay vì v-if rải trong
// template — cùng nguyên tắc "hành động là dữ liệu" của de-xuat-actions.js.
const navItems = computed(() => NAV.filter((n) => !n.requireQuanLy || store.me?.la_quan_ly))

function isActive(key) {
  const name = route.name || ''
  // Task 10 — `/dat-hang/:ten` (mở lại một phiếu Nháp để sửa tiếp) là CÙNG
  // một màn, cùng một mục nav.
  if (key === 'dat-hang') return name === 'dat-hang'
  // Task 11 — MỘT mục nav ôm CẢ BA route của một yêu cầu: danh sách gộp,
  // chi tiết đơn, chi tiết phiếu.
  //
  // Việc (c) + C3 (giữ nguyên từ Task 4) — màn chi tiết phiếu là ĐÍCH
  // CHUNG của HAI mục nav. Nó sáng ở mục nào là do NƠI ĐÃ TỚI quyết định,
  // đọc từ `?tu=` mà danh sách nguồn ghi vào lúc điều hướng (xem
  // `quayLaiTo` ở DeXuatDetail.vue). Thiếu vế này thì quản lý mở phiếu từ
  // /duyet lại thấy "Yêu cầu của tôi" sáng.
  if (key === 'yeu-cau') {
    return (
      name === 'yeu-cau'
      || name === 'order-detail'
      || (name === 'de-xuat-detail' && route.query.tu !== 'duyet')
    )
  }
  if (key === 'duyet') return name === 'duyet' || (name === 'de-xuat-detail' && route.query.tu === 'duyet')
  if (key === 'kho') {
    return [
      'kho', 'kho-import', 'kho-nhap', 'kho-nhap-detail', 'kho-xuat', 'kho-xuat-detail',
      'kho-bao-cao', 'kho-ncc', 'kho-nhat-ky', 'kho-vat-tu', 'kho-vat-tu-import',
    ].includes(name)
  }
  if (key === 'profile') return name === 'profile' || name === 'invoices' || name === 'thong-bao'
  return name === key
}

async function doLogout() {
  await logout()
  window.location.href = '/portal/login'
}

// Badge chưa đọc: nạp MỘT LẦN ở shell (mọi trang), khỏi phụ thuộc khách có
// mở trang Thông báo hay không. `ThongBao.vue` tự nạp lại số chính xác khi
// khách vào trang đó, và tự giảm tại chỗ khi khách đọc — ở đây chỉ cần một
// con số ban đầu cho badge.
onMounted(async () => {
  try {
    const res = await api.call('portal_thong_bao_list', { limit: 1 })
    store.setChuaDocThongBao(res.chua_doc || 0)
  } catch {
    // Badge chỉ là gợi ý phụ — im lặng bỏ qua, không được chặn cả trang vì
    // một lần gọi thất bại.
  }

  // Man luong duyet (Task 5) — nạp `me` ở SHELL (không đợi view con): mục
  // nav "Duyệt" và badge số phiếu chờ hiện trên MỌI trang, không riêng gì
  // `/duyet`. Hai lời gọi ("Chờ duyệt" + "Chờ duyệt sửa") và luật phát hiện
  // bị cắt nằm ở `cho-duyet.js` — dùng chung với /duyet và màn chi tiết, để
  // ba nơi không trôi khỏi nhau (việc (e)).
  try {
    if (!store.me) store.setMe(await api.call('portal_me'))
    await capNhatChoDuyetCount(store)
  } catch (e) {
    // Badge/mục nav chỉ là gợi ý phụ ở tầng shell — KHÔNG chặn cả trang,
    // view `/duyet` tự tải lại dữ liệu thật khi khách vào đó. Nhưng cũng
    // KHÔNG rơi im lặng: `catch {}` trần ở đây từng là lý do một tên endpoint
    // gõ sai làm badge biến mất trên mọi trang mà không để lại dấu vết nào.
    console.warn('Không nạp được số phiếu chờ duyệt cho badge nav:', e)
  }
})
</script>

<template>
  <div class="mp-shell">
    <!-- Desktop sidebar (>=900px) -->
    <aside class="side">
      <div class="logo">MIYANO<span>◆</span> Portal</div>
      <nav class="nav">
        <router-link
          v-for="n in navItems"
          :key="n.key"
          :to="n.to"
          :class="{ on: isActive(n.key) }"
        >
          <span>{{ n.icon }} {{ n.label }}<span v-if="n.newtag" class="newtag">MỚI</span></span>
          <span v-if="n.thongBao && chuaDocThongBao" class="cartn">{{ chuaDocThongBao }}</span>
          <span v-if="n.duyet && choDuyetCount" class="cartn">{{ choDuyetNhan }}</span>
        </router-link>
      </nav>
      <div class="who">
        <div>👤 {{ store.me?.customer_name || '…' }}</div>
        <div class="tag" style="color: #cbd5e1">{{ store.me?.customer || '' }}</div>
        <a href="#" @click.prevent="doLogout">Đăng xuất</a>
      </div>
    </aside>

    <!-- Mobile header (<900px). Task 10 — nút giỏ hàng đã bỏ: không còn
         một giỏ toàn cục nào để đếm; giỏ sống TRONG màn Đặt hàng (bước 2)
         và biến mất cùng phiếu khi khách rời màn. -->
    <header class="hdr">
      <span class="ttl">{{ pageTitle }}</span>
    </header>

    <!-- Content -->
    <main class="main">
      <router-view />
    </main>

    <!-- Mobile bottom nav (<900px) -->
    <nav class="bnav">
      <router-link
        v-for="n in BNAV"
        :key="n.key"
        :to="n.to"
        :class="{ on: isActive(n.key) }"
      >
        <span class="ic">{{ n.icon }}</span>
        <span>{{ n.short }}</span>
        <span v-if="n.thongBao && chuaDocThongBao" class="cartn2">{{ chuaDocThongBao }}</span>
      </router-link>
    </nav>

    <ToastHost />
  </div>
</template>
