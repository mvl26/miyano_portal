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
  //
  // Chủ đầu tư chốt 03/09/2026 — tên là "Danh sách đơn hàng" (trước là
  // "Yêu cầu của tôi"). Chỉ CHỮ đổi: đường `/yeu-cau`, tên route và mọi
  // định danh trong mã giữ nguyên — đổi đường là thêm một cặp chuyển
  // hướng nữa cho đúng một thay đổi mà người dùng chỉ thấy ở nhãn.
  //
  // `duyet: true` — badge số phiếu chờ duyệt SANG mục này cùng lúc màn
  // `/duyet` nghỉ. Nó vẫn là tín hiệu riêng của quản lý (xem
  // `hienBadgeDuyet` bên dưới), chỉ không còn một cửa riêng để dẫn tới.
  { to: '/yeu-cau', icon: '📋', label: 'Danh sách đơn hàng', short: 'Đơn hàng', key: 'yeu-cau', duyet: true },
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
  { to: '/yeu-cau', icon: '📋', short: 'Đơn hàng', key: 'yeu-cau' },
  { to: '/kho', icon: '🏭', short: 'Kho', key: 'kho' },
  { to: '/profile', icon: '☰', short: 'Thêm', key: 'profile', thongBao: true },
]

const pageTitle = computed(() => route.meta.title || 'Cổng khách hàng')
const chuaDocThongBao = computed(() => store.chuaDocThongBao)
// Việc (e) — badge hiện "200+" khi hàng chờ chạm trần một lời gọi. Con số
// trần trụi "200" là con số SAI đọc như con số đúng: quản lý duyệt hết 200
// phiếu rồi tưởng xong việc.
const choDuyetNhan = computed(() => `${store.choDuyetCount}${store.choDuyetBiCat ? '+' : ''}`)

// 03/09/2026 — mảng NAV không còn mục nào theo vai trò (mục "Duyệt" đã
// nghỉ), nên `navItems` thôi lọc. CỐ Ý bỏ hẳn cờ `requireQuanLy` + bộ lọc
// thay vì để chúng nằm lại "phòng khi cần": một bộ lọc không lọc gì, có
// test canh, là thứ đọc như một chốt phân quyền còn sống.
//
// Thứ CÒN theo vai trò là BADGE số phiếu chờ duyệt — nói thẳng ở đây,
// không dựa vào việc `capNhatChoDuyetCount()` tình cờ để `choDuyetCount`
// bằng 0 cho nhân viên khoa. Một tín hiệu phân quyền suy ra từ "giá trị
// mặc định tình cờ đúng" là thứ hỏng lặng lẽ vào ngày ai đó nạp con số
// này từ một chỗ khác.
const navItems = computed(() => NAV)
const hienBadgeDuyet = computed(() => !!store.me?.la_quan_ly && !!store.choDuyetCount)

// Việc 4 (review toàn nhánh 03/09/2026) — badge "7" phải dẫn tới ĐÚNG bảy
// phiếu đó. Trước hàm này, mục nav là `/yeu-cau` TRẦN: quản lý bấm badge
// rồi rơi vào danh sách toàn viện chưa lọc và phải tự biết bấm tiếp chip
// "Chờ duyệt" — trong khi cả file này lẫn `cho-duyet.js` đều khẳng định
// "badge và đích nó dẫn tới không nói hai con số khác nhau".
//
// Gắn chip CÓ ĐIỀU KIỆN, không viết cứng vào mảng NAV: đây là mục CHUNG
// của mọi vai trò — nhân viên khoa dùng chính nó để xem yêu cầu của mình,
// và mở sẵn một bộ lọc họ không có phiếu nào trong đó là đưa họ tới một
// danh sách rỗng. Điều kiện dùng lại ĐÚNG cờ `hienBadgeDuyet` mà template
// hỏi, không phải một phép suy vai trò thứ hai đặt cạnh nó: khi badge
// không hiện thì không có con số nào để mà "dẫn tới đúng", nên đích trở
// lại trần. `isActive()` so theo `route.name` nên query không ảnh hưởng
// tới việc mục nào sáng.
function dichNav(n) {
  if (n.duyet && hienBadgeDuyet.value) {
    return { path: n.to, query: { chip: 'cho_duyet' } }
  }
  return n.to
}

function isActive(key) {
  const name = route.name || ''
  // Task 10 — `/dat-hang/:ten` (mở lại một phiếu Nháp để sửa tiếp) là CÙNG
  // một màn, cùng một mục nav.
  if (key === 'dat-hang') return name === 'dat-hang'
  // Task 11 — MỘT mục nav ôm CẢ BA route của một yêu cầu: danh sách gộp,
  // chi tiết đơn, chi tiết phiếu.
  //
  // Việc (c) + C3 — màn chi tiết phiếu từng là ĐÍCH CHUNG của HAI mục nav,
  // nên nó phải hỏi `?tu=` để biết sáng ở đâu. Từ 03/09/2026 chỉ còn MỘT
  // mục, nên câu hỏi đó không còn nữa.
  if (key === 'yeu-cau') {
    // 03/09/2026 — vế `route.query.tu !== 'duyet'` đã bỏ cùng mục nav
    // "Duyệt". Giữ lại thì một link CŨ mang `?tu=duyet` (thông báo đã gửi
    // đi, tab được ghim) mở ra không có mục nav nào sáng — mục nó từng
    // sáng thì không còn, mục còn lại thì tự loại mình.
    return name === 'yeu-cau' || name === 'order-detail' || name === 'de-xuat-detail'
  }
  if (key === 'kho') {
    return [
      'kho', 'kho-import', 'kho-nhap', 'kho-nhap-detail', 'kho-xuat', 'kho-xuat-detail',
      'kho-bao-cao', 'kho-bao-cao-thiet-bi', 'kho-ncc', 'kho-nhat-ky', 'kho-vat-tu',
      'kho-vat-tu-import', 'kho-khoa-phong', 'kho-thiet-bi',
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

  // Man luong duyet (Task 5) — nạp `me` ở SHELL (không đợi view con): badge
  // số phiếu chờ duyệt hiện trên MỌI trang. Hai lời gọi ("Chờ duyệt" +
  // "Chờ duyệt sửa") và luật phát hiện bị cắt nằm ở `cho-duyet.js` — dùng
  // chung với màn chi tiết, để hai nơi không trôi khỏi nhau (việc (e)).
  //
  // 03/09/2026 — bộ hai trạng thái mà `cho-duyet.js` đếm ĐÚNG BẰNG bộ mà
  // chip `cho_duyet` lọc ra (`_sql_giai_doan()` gom cả hai vào một khoá).
  // Điều đó MỘT MÌNH chưa đủ để "badge và đích nó dẫn tới nói cùng một con
  // số": đích phải THẬT SỰ mang chip đó (`dichNav()` ở trên) — trước Việc 4
  // nó là `/yeu-cau` trần và câu khẳng định này sai.
  try {
    if (!store.me) store.setMe(await api.call('portal_me'))
    await capNhatChoDuyetCount(store)
  } catch (e) {
    // Badge chỉ là gợi ý phụ ở tầng shell — KHÔNG chặn cả trang, danh sách
    // đơn hàng tự tải dữ liệu thật khi khách vào đó. Nhưng cũng
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
          :to="dichNav(n)"
          :class="{ on: isActive(n.key) }"
        >
          <span>{{ n.icon }} {{ n.label }}<span v-if="n.newtag" class="newtag">MỚI</span></span>
          <span v-if="n.thongBao && chuaDocThongBao" class="cartn">{{ chuaDocThongBao }}</span>
          <span v-if="n.duyet && hienBadgeDuyet" class="cartn">{{ choDuyetNhan }}</span>
        </router-link>
      </nav>
      <!-- Chủ đầu tư chốt 25/08 — dòng dưới là TÊN TÀI KHOẢN, không phải mã
           khách. `store.me.customer` là DOCNAME của Customer, mà trên site
           này Customer đặt tên bằng chính `customer_name`, nên khối này in
           ĐÚNG MỘT chuỗi hai lần ("Bệnh viện Đa khoa Minh Đức (DEMO)" ở cả
           hai dòng) — tốn một dòng để không nói thêm gì.
           `store.me.user` (email phiên đang đăng nhập, đã có sẵn trong
           `portal_me`) là thứ DUY NHẤT phân biệt được hai người cùng một
           bệnh viện, và là thứ người dùng cần thấy để biết mình đang đăng
           nhập bằng tài khoản nào trước khi bấm Đăng xuất. -->
      <div class="who">
        <div>👤 {{ store.me?.customer_name || '…' }}</div>
        <div class="tag" style="color: #cbd5e1">{{ store.me?.user || '' }}</div>
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
