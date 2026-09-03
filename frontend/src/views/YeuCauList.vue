<script setup>
// Task 11 (QĐ-G11, chủ đầu tư chốt 21/08/2026) — "Danh sách đơn hàng"
// (tên do chủ đầu tư chốt 03/09/2026; trước đó là "Yêu cầu của tôi" — chỉ
// CHỮ đổi, đường `/yeu-cau` và mọi định danh trong mã giữ nguyên).
//
// Màn này NUỐT hai màn cũ: `Orders.vue` (`/orders`, danh sách Sales Order)
// và `DeXuatList.vue` (`/de-xuat`, danh sách phiếu đề xuất). Lý do gộp:
// một yêu cầu của khoa nằm ở "Đề xuất mua" khi còn là phiếu rồi NHẢY sang
// "Đơn hàng của tôi" sau khi quản lý duyệt — để tìm lại yêu cầu của chính
// mình, nhân viên phải biết trước nó đang ở giai đoạn NỘI BỘ nào, tức phải
// học sơ đồ kiến trúc của hệ thống.
//
// Một yêu cầu xuất hiện ĐÚNG MỘT LẦN, ở bất kỳ giai đoạn nào. Phiếu và đơn
// sinh ra từ nó là MỘT dòng — server đã gộp (`portal_yeu_cau_cua_toi`), client
// KHÔNG tự ghép hai danh sách.
//
// 03/09/2026 — màn duyệt riêng (`/duyet`) ĐÃ NGHỈ và hàng chờ của quản lý
// nay CHÍNH LÀ màn này lọc chip "Chờ duyệt". Task 11 từng cố ý không gộp
// hai thứ đó ("hàng chờ việc" khác "danh sách của tôi"); điều đổi ý kiến
// là việc DUYỆT vốn đã nằm ở màn CHI TIẾT chứ không ở màn danh sách, nên
// `/duyet` không phải một chỗ làm việc — nó chỉ là bản sao thứ hai của
// cùng bộ dữ liệu, kèm một bộ lọc khoa mà màn này thiếu. Bộ lọc đó đã
// mang sang (`khoaFilter` bên dưới), nên không còn gì ở đó để mất.
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { fmtVND, fmtDate, giaiDoanBadge, nhanGiaiDoan, khoaGiaiDoan, GIAI_DOAN } from '../format'
import { useIsMobile } from '../useMobile'
import { store } from '../store'
import PhanTrang from '../components/PhanTrang.vue'

const route = useRoute()
const router = useRouter()
const isMobile = useIsMobile()

const loading = ref(true)
const error = ref('')
const rows = ref([])
const filter = ref('') // '' = Tất cả
// Mang sang từ `DuyetList.vue` (03/09/2026). Yêu cầu gốc chủ đầu tư ghi ở
// đó: "quản lý sẽ filter theo khoa … cốt lõi là để quản lý biết được khoa
// nào đang mua cái gì mà để duyệt". `'' = Tất cả các khoa`.
//
// CHỈ hiện cho quản lý: nhân viên khoa đã bị `pham_vi_don()` kẹp về đúng
// khoa mình, một ô lọc chỉ có một lựa chọn là một ô hỏi câu đã trả lời rồi.
const khoaFilter = ref('')
const trang = ref(1)
const soDong = ref(20)
const tong = ref(0)

// ĐÚNG bộ `GIAI_DOAN_HOP_LE` của backend, không nhiều không ít: một chip
// backend không biết sẽ ăn lỗi "Giai đoạn không hợp lệ", còn một giai đoạn
// thiếu chip thì yêu cầu ở đó chỉ tìm được qua "Tất cả".
//
// Ruling P54 — KHOÁ, không phải nhãn. `FILTERS` vừa vẽ chip, vừa được ghi
// vào `?chip=`, vừa gửi lên `giai_doan`; để chữ tiếng Việt ở đây là buộc
// URL và bộ lọc vào một quyết định biên tập. Chữ hiện trên chip lấy từ
// `nhanGiaiDoan()`. `''` đứng đầu = chip "Tất cả".
const FILTERS = ['', ...GIAI_DOAN]

// Khoa phòng chỉ có MÃ (`KP-00001`) trong payload — nạp danh mục rồi tự map
// mã -> tên. Best-effort: một khách chưa mở kho vẫn phải xem được danh
// sách, chỉ mất phần dịch tên khoa.
//
// 03/09/2026 — ĐỔI sang `kho_khoa_phong_list_khach` (Task 12b), cùng lý do
// `ThietBiModal.vue` đã đổi: bản cũ (`kho_khoa_phong_list`) suy kho qua
// `get_portal_kho()` và ném lỗi cho bệnh viện CHƯA MỞ KHO. Trước đây hậu
// quả chỉ là cột khoa hiện mã thô; từ bản này danh mục còn NUÔI Ô LỌC KHOA
// của quản lý, và một ô lọc rỗng không nói được rằng nó rỗng vì thiếu kho.
// Endpoint mới suy khách thẳng từ phiên và tự lọc theo vai trò.
const khoaPhongList = ref([])
async function loadKhoaPhongList() {
  try {
    khoaPhongList.value = await api.callKho('kho_khoa_phong_list_khach', { ca_inactive: 1 })
  } catch (e) {
    // Im lặng — cột khoa phòng rơi về hiện mã thô, không chặn cả danh sách.
  }
}
function tenKhoa(ma) {
  if (!ma) return ''
  const k = khoaPhongList.value.find((x) => x.name === ma)
  return k ? k.ten_khoa_phong : ma
}

// Danh mục ĐẦY ĐỦ của bệnh viện, KHÔNG suy từ `rows`: `DuyetList.vue` dựng
// ô lọc từ chính các phiếu đang hiện vì nó tải một phát 200 dòng. Màn này
// phân trang 20 dòng — suy từ trang đang xem sẽ cho một ô lọc mà nội dung
// đổi mỗi lần sang trang, và khoa nào không có dòng nào ở trang 1 thì không
// lọc tới được.
const khoaOptions = computed(() =>
  khoaPhongList.value
    .map((k) => ({ ma: k.name, ten: k.ten_khoa_phong || k.name }))
    .sort((a, b) => a.ten.localeCompare(b.ten, 'vi'))
)

function pct(r) {
  return Math.round(Number(r.per_delivered || 0))
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.call('portal_yeu_cau_cua_toi', {
      start: (trang.value - 1) * soDong.value,
      limit: soDong.value,
      // '' (chip "Tất cả") bị JSON.stringify loại khỏi body -> backend
      // nhận `giai_doan=None` -> không lọc.
      giai_doan: filter.value || undefined,
      // Lọc ở SERVER, không trên trang đã tải: danh sách này phân trang, nên
      // lọc phía client sẽ hiện 3 dòng và ngầm bảo khoa đó chỉ có 3 (đúng
      // cái bẫy `DuyetList.vue` từng tự cảnh báo về trần `limit` của nó).
      khoa_phong: khoaFilter.value || undefined,
    })
    rows.value = res?.rows || []
    tong.value = res?.tong || 0
  } catch (e) {
    error.value = e.message || 'Không tải được danh sách đơn hàng.'
  } finally {
    loading.value = false
  }
}

// Đổi chip -> về trang 1 (kết quả lọc mới có thể ít hơn trang đang xem).
// Chip đang chọn sống trong URL để nút "Quay lại" của màn chi tiết dựng
// lại được đúng nó (C3, giữ nguyên cơ chế của DeXuatList.vue).
watch([filter, khoaFilter], () => {
  trang.value = 1
  router.replace({
    name: 'yeu-cau',
    query: {
      ...(filter.value ? { chip: filter.value } : {}),
      ...(khoaFilter.value ? { khoa: khoaFilter.value } : {}),
    },
  })
})
watch([trang, soDong, filter, khoaFilter], load)

// SỬA được ⟺ đúng quyền `de_xuat_luu_nhap` phía server (owner HOẶC quản
// lý). Client đoán khác server thì khách gõ xong mới ăn "Phiếu này không
// phải của bạn" và mất sạch công sửa — cùng điều kiện DeXuatList.vue đã
// dùng, mang nguyên sang.
function coTheSuaNhap(r) {
  return (
    r.giai_doan === 'nhap'
    && !!r.de_xuat
    && (r.owner === store.me?.user || !!store.me?.la_quan_ly)
  )
}

// Đích của một dòng = CHỨNG TỪ CHÍNH LÀ yêu cầu đó:
//   * phiếu Nháp sửa được  -> màn Đặt hàng (`/dat-hang/:ten`), nơi duy
//     nhất có ô nhập số lượng cho một phiếu chưa gửi duyệt;
//   * có phiếu             -> chi tiết phiếu (khối truy vết + link sang
//     đơn đứng sau nó, xem DeXuatDetail.vue);
//   * không có phiếu       -> chi tiết đơn (đơn cũ, có trước luồng duyệt).
// 03/09/2026 — MỘT đích cho mọi dòng. Nút "Đơn hàng" riêng ở cột cuối đã
// bỏ cùng lúc hai màn chi tiết gộp làm một: nó từng là lối vào NỬA KIA của
// cùng một yêu cầu, nay là cửa thứ hai vào đúng một phòng.
function moYeuCau(r) {
  if (coTheSuaNhap(r)) {
    router.push({ name: 'dat-hang', params: { ten: r.de_xuat } })
    return
  }
  if (r.de_xuat) {
    router.push({
      name: 'de-xuat-detail',
      params: { ten: r.de_xuat },
      query: {
        tu: 'yeu-cau',
        ...(filter.value ? { chip: filter.value } : {}),
        // Nút "Quay lại" ở màn chi tiết dựng lại CẢ HAI bộ lọc — quản lý
        // lọc khoa "Huyết học", mở phiếu, duyệt, quay lại mà rơi vào danh
        // sách toàn viện là mất đúng chỗ họ đang đứng (bài học C3).
        ...(khoaFilter.value ? { khoa: khoaFilter.value } : {}),
      },
    })
    return
  }
  router.push({ name: 'order-detail', params: { name: r.sales_order } })
}

onMounted(async () => {
  loadKhoaPhongList()
  // Khôi phục chip từ URL (nút "Quay lại" của màn chi tiết dựng lại nó).
  // Gán vào `filter` KÍCH HOẠT watcher, tức `load()` đã được xếp hàng —
  // gọi thêm `load()` ở cuối hàm là MỘT REQUEST THỪA, và nó về sau lời gọi
  // kia nên còn có thể ghi đè kết quả đúng bằng kết quả cũ. `DeXuatList.
  // vue` chấp nhận lời gọi thừa đó ("rẻ hơn một nhánh điều kiện"); ở đây
  // nhánh điều kiện là đúng một biến, nên không có gì để đánh đổi.
  let daXepHangLoad = false
  // Ruling P54 — `khoaGiaiDoan()` nhận CẢ khoá mới LẪN nhãn cũ, nên một
  // link `?chip=Chờ báo giá` đã gửi cho bệnh viện vẫn mở đúng chip. Rào
  // `FILTERS.includes()` cũ trả `false` cho chuỗi cũ và thả người dùng về
  // "Tất cả" trong im lặng — bí danh phía backend không cứu được, vì khi
  // đó `giai_doan` gửi lên đã là `undefined` và không bao giờ tới nó.
  const chip = khoaGiaiDoan(route.query.chip)
  if (chip) {
    filter.value = chip
    daXepHangLoad = true
  }
  // Cùng cơ chế cho bộ lọc khoa (`?khoa=`) — nó sống trong URL để nút "Quay
  // lại" của màn chi tiết dựng lại đúng chỗ quản lý đang đứng, và để một
  // link `/duyet` cũ (nay chuyển hướng kèm `?chip=cho_duyet`) vẫn ghép được
  // với khoa nếu ai đó đã lưu cả hai.
  if (route.query.khoa) {
    khoaFilter.value = String(route.query.khoa)
    daXepHangLoad = true
  }
  if (!store.me) {
    try {
      store.setMe(await api.call('portal_me'))
    } catch (e) {
      // Subtitle phạm vi + nút "Sửa" chỉ là gợi ý phụ — im lặng bỏ qua.
    }
  }
  if (!daXepHangLoad) load()
})
</script>

<template>
  <div>
    <div class="topbar" v-if="!isMobile">
      <div>
        <h2>Danh sách đơn hàng</h2>
        <div class="sub">
          {{ store.me?.la_quan_ly
            ? 'Mọi đơn hàng của đơn vị — từ lúc còn là đề xuất tới lúc nhận hàng'
            : 'Mọi đơn hàng của khoa bạn — từ lúc còn là đề xuất tới lúc nhận hàng' }}
        </div>
      </div>
      <router-link :to="{ name: 'dat-hang' }"><button class="btn">+ Đặt hàng</button></router-link>
    </div>
    <div v-else class="mb10">
      <router-link :to="{ name: 'dat-hang' }"><button class="btn btn-sm">+ Đặt hàng</button></router-link>
    </div>

    <!-- Ô lọc khoa — CHỈ quản lý. Đứng TRÊN dải chip: quản lý chọn khoa
         trước ("khoa nào đang mua gì"), rồi mới lọc giai đoạn trong khoa
         đó. Mang từ `DuyetList.vue` sang cùng lúc màn đó nghỉ. -->
    <div v-if="store.me?.la_quan_ly && khoaOptions.length" class="card mb10">
      <div class="field" style="margin-bottom: 0; max-width: 320px">
        <label>Khoa phòng</label>
        <select v-model="khoaFilter">
          <option value="">— Tất cả các khoa —</option>
          <option v-for="k in khoaOptions" :key="k.ma" :value="k.ma">{{ k.ten }}</option>
        </select>
      </div>
    </div>

    <div class="chips">
      <button
        v-for="f in FILTERS"
        :key="f"
        class="chip"
        :class="{ on: filter === f }"
        @click="filter = f"
      >
        {{ f ? nhanGiaiDoan(f) : 'Tất cả' }}
      </button>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <!-- Câu rỗng phải nói ĐÚNG VAI người đang đọc — cùng bài học "Việc (b)"
         của DeXuatList.vue: quản lý xem phạm vi toàn đơn vị mà câu rỗng lại
         bảo "Khoa chưa có…" là hai câu trên cùng một màn nói hai phạm vi
         khác nhau, và câu sai là câu DUY NHẤT hiện khi màn trống. -->
    <div v-else-if="!rows.length" class="empty">
      {{ store.me?.la_quan_ly ? 'Đơn vị chưa có đơn hàng nào.' : 'Khoa chưa có đơn hàng nào.' }}
    </div>

    <!-- DESKTOP: bảng -->
    <div v-else-if="!isMobile" class="card" style="padding: 0; overflow-x: auto">
      <table>
        <thead>
          <tr>
            <th>Mã đơn hàng</th><th>Khoa phòng</th><th>Ngày đặt</th>
            <th class="right">Giá trị</th><th style="min-width: 130px">Đã giao</th>
            <th>Giai đoạn</th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.khoa_sap_xep" class="clickable" @click="moYeuCau(r)">
            <td>
              <b v-if="r.ma">{{ r.ma }}</b>
              <span v-else class="tag">(chưa gửi duyệt)</span>
            </td>
            <td>{{ tenKhoa(r.khoa_phong) }}</td>
            <td>{{ fmtDate(r.thoi_diem) }}</td>
            <!-- Yêu cầu chưa thành đơn chưa có giá trị nào để nói — "—",
                 không phải một số 0 đọc như một con số thật. -->
            <td class="right">{{ r.sales_order ? fmtVND(r.grand_total) : '—' }}</td>
            <td>
              <template v-if="r.sales_order">
                {{ pct(r) }}%
                <div class="bar"><i :style="{ width: pct(r) + '%', background: 'var(--orange)' }"></i></div>
              </template>
              <span v-else class="tag">—</span>
            </td>
            <td>
              <span class="badge" :class="giaiDoanBadge(r.giai_doan)">{{ nhanGiaiDoan(r.giai_doan) }}</span>
              <!-- Giai đoạn gộp KHÔNG được nuốt mất tín hiệu chi tiết của
                   đơn ("Chờ xác nhận"/"Đang giao"/…) — nó là thứ nói ai
                   đang giữ việc. -->
              <div v-if="r.trang_thai_don" class="tag" style="margin-top: 2px">{{ r.trang_thai_don }}</div>
            </td>
            <td style="white-space: nowrap">
              <button v-if="coTheSuaNhap(r)" class="btn-o btn-sm" @click.stop="moYeuCau(r)">Sửa</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- MOBILE: thẻ -->
    <template v-else>
      <div
        v-for="r in rows"
        :key="r.khoa_sap_xep"
        class="card mb10 clickable"
        @click="moYeuCau(r)"
      >
        <div class="sb">
          <b v-if="r.ma">{{ r.ma }}</b>
          <span v-else class="tag">(chưa gửi duyệt)</span>
          <span class="badge" :class="giaiDoanBadge(r.giai_doan)">{{ nhanGiaiDoan(r.giai_doan) }}</span>
        </div>
        <p class="tag" style="margin-top: 4px">
          {{ tenKhoa(r.khoa_phong) }} · {{ fmtDate(r.thoi_diem) }}
          <template v-if="r.sales_order"> · {{ fmtVND(r.grand_total) }}</template>
          <template v-if="r.trang_thai_don"> · {{ r.trang_thai_don }}</template>
        </p>
        <template v-if="r.sales_order && pct(r) > 0">
          <p style="font-size: 12px; margin-top: 6px">Đã giao <b>{{ pct(r) }}%</b></p>
          <div class="bar"><i :style="{ width: pct(r) + '%', background: 'var(--orange)' }"></i></div>
        </template>
        <div style="margin-top: 8px">
          <button v-if="coTheSuaNhap(r)" class="btn-o btn-sm" @click.stop="moYeuCau(r)">Sửa</button>
        </div>
      </div>
    </template>

    <PhanTrang v-if="!loading && !error" v-model:trang="trang" v-model:so-dong="soDong" :tong="tong" />
  </div>
</template>
