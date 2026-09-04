<script setup>
// Dòng thời gian nhật ký thao tác — Task 7 (spec §9). Nâng `.vtl`/`.vst`/
// `.vdot`/`.vlb` (định nghĩa ở `style.css`, đến giờ chỉ là bản MOBILE của
// thanh tiến trình `KhoiTienTrinh.vue`) lên thành khối dùng ở MỌI kích
// thước màn (§9.2) — CỐ Ý không rẽ nhánh desktop/mobile như khối kia:
// dòng thời gian DỌC là hình dạng ĐÚNG cho cả hai, không chỉ cho di động.
// Không thêm `<style>` riêng ở đây — mọi màu SỐNG ở bốn lớp `.vdot.*` mới
// thêm vào `style.css`, dùng CHUNG với phần còn lại của cổng.
import { computed } from 'vue'
import { fmtDateTime, mauChamSuKien, nhanSuKien } from '../../format'

const props = defineProps({
  // Kết quả `portal_nhat_ky_yeu_cau` (Task 5) — mỗi phần tử mang
  // `{su_kien, thoi_diem, vai, ten, dien_thoai, tai_khoan, ghi_chu, suy_ra}`.
  // Thứ tự ĐÃ đúng (server sort theo `thoi_diem asc` — §9.5 "mới nhất ở
  // DƯỚI cùng"); component này KHÔNG tự sort/reverse — một bản sao logic
  // sắp xếp thứ hai ở client là đúng kiểu lệch mà Ruling #19 đã cảnh (xem
  // chú thích `mauChamSuKien` ở `format.js`).
  dong: { type: Array, default: () => [] },
  dangTai: { type: Boolean, default: false },
})

// Review vòng 2 (04/09/2026) — `suy_ra` đến từ server nhưng KHÔNG được
// ĐỌC ở đâu trong template trước bản vá này: đúng lỗi "lần thứ tư" mà
// `docs/BAN-DO-CHUC-NANG.md` mục 4 ghi nhận (`boi_so` được API trả về
// nhưng không màn nào đọc) — một trường chỉ có người SINH ra mà không có
// người TIÊU THỤ thì không tồn tại đối với người dùng. Sổ nhật ký tồn tại
// để ĐỐI CHIẾU khi hai bên nhớ khác nhau; một dòng DỰNG LẠI từ bốn trường
// trên phiếu (§9.6) và một dòng ghi NGAY LÚC việc xảy ra mang độ tin cậy
// khác nhau — im lặng coi chúng như nhau là mời người ta trích dẫn một
// suy luận như thể đó là bằng chứng.
const coDongSuyRa = computed(() => props.dong.some((d) => d.suy_ra))
</script>

<template>
  <div class="card mb10" style="margin-bottom: 14px">
    <div class="h3">Dòng thời gian</div>

    <!-- `dangTai` đứng TRƯỚC nhánh rỗng — thiếu bước này thì MỖI lần mở
         màn đều nháy qua dòng "Chưa có thao tác nào" trước khi dữ liệu về,
         một trạng thái RỖNG giả cho mọi yêu cầu, kể cả yêu cầu có 20 dòng. -->
    <p v-if="dangTai" class="tag">Đang tải dòng thời gian…</p>

    <!-- §9.5 — trạng thái RỖNG phải NÓI THẬT, không để trống trơn. Server
         đã suy hai dòng cho chứng từ CŨ trước khi bật nhật ký (§9.6, đi
         qua CHÍNH mảng `dong` này) — nên rỗng ở ĐÂY nghĩa là CHƯA có thao
         tác nào cả (vd một phiếu Nháp vừa tạo), không riêng "đơn cũ".
         CỐ Ý không dùng câu "Nhật ký bắt đầu ghi từ <ngày>" mà §9.5 gợi ý
         nguyên văn: tầng này không có cách nào XÁC NHẬN đúng ngày nhật ký
         được BẬT trên site khách hàng (ngày tạo doctype trong mã nguồn
         KHÔNG phải ngày migrate trên site đó) — một câu sai sự thật còn
         tệ hơn một câu tổng quát nhưng ĐÚNG trong MỌI trường hợp. -->
    <p v-else-if="!dong.length" class="tag">
      Chưa có thao tác nào được ghi cho yêu cầu này.
    </p>

    <template v-else>
      <div class="vtl" style="max-width: 640px">
        <div v-for="(d, i) in dong" :key="i" class="vst">
          <!-- Review vòng 2 — chấm dòng "dựng lại" (`d.suy_ra`, §9.6)
               phải KHÁC dòng ghi thật, không chỉ mờ đi (mờ đọc ra "ít
               quan trọng", không phải "độ tin cậy khác"). VIỀN RỖNG thay
               vì đặc — GIỮ NGUYÊN màu vai trò (không thêm màu thứ năm,
               §9.3 vẫn ba màu + một xám), chỉ đổi NỀN/VIỀN qua lớp
               `.suy-ra` (`style.css`). -->
          <div class="vdot" :class="[mauChamSuKien(d.su_kien, d.vai), { 'suy-ra': d.suy_ra }]"></div>
          <div class="vlb">
            <b>{{ nhanSuKien(d.su_kien) }}</b>
            {{ fmtDateTime(d.thoi_diem) }}
            <!-- Nhãn "Dựng lại từ phiếu" — TỰ NÓI LÊN NGHĨA (chữ thật,
                 không chỉ đổi màu/độ mờ): người dùng bệnh viện không đọc
                 chú thích kỹ thuật. Đặt cạnh mốc giờ vì đó là chỗ người
                 đọc dò khi hỏi "hôm nào" — cùng câu hỏi khiến độ tin cậy
                 của mốc giờ đó đáng nói ngay tại chỗ. -->
            <span v-if="d.suy_ra" class="tag" style="border: 1px solid var(--line); border-radius: 10px; padding: 1px 7px; margin-left: 4px">Dựng lại từ phiếu</span>
            <template v-if="d.ten"> · {{ d.ten }}</template>
            <!-- §8 — thiếu số thì KHÔNG in gì (không ô trống, không dấu
                 gạch). `v-if` trên CHÍNH giá trị số, không `|| '—'`. Điều
                 dưỡng trưởng đọc màn này trên điện thoại — bấm gọi được
                 là khác biệt giữa "thấy số" và "gọi được người" (§9.4). -->
            <a v-if="d.dien_thoai" :href="'tel:' + d.dien_thoai"> · {{ d.dien_thoai }}</a>
            <div v-if="d.ghi_chu" class="tag">{{ d.ghi_chu }}</div>
          </div>
        </div>
      </div>
      <!-- §9.3 — chú giải màu đặt DƯỚI khối (người đọc đã hiểu từ ngữ
           cảnh, chú giải chỉ để XÁC NHẬN). Dùng LẠI chính bốn lớp `.vdot.*`
           ở trên, chỉ ghi đè KÍCH THƯỚC bằng style — không phát minh một
           bộ màu inline thứ hai (đó là một nguồn màu THỨ HAI để trôi lệch
           khỏi bảng ở `format.js`/`style.css`). -->
      <p class="tag" style="margin-top: 10px">
        <span class="vdot benh-vien" style="width: 10px; height: 10px; min-width: 10px; display: inline-block"></span>
        Bệnh viện
        <span class="vdot miyano" style="width: 10px; height: 10px; min-width: 10px; display: inline-block; margin-left: 10px"></span>
        Miyano
        <span class="vdot lui" style="width: 10px; height: 10px; min-width: 10px; display: inline-block; margin-left: 10px"></span>
        Việc đi lùi
        <span class="vdot he-thong" style="width: 10px; height: 10px; min-width: 10px; display: inline-block; margin-left: 10px"></span>
        Hệ thống
      </p>
      <!-- Review vòng 2 — câu giải thích CHUNG, chỉ hiện khi CÓ ít nhất
           một dòng suy_ra (`coDongSuyRa`). CỐ Ý không nêu một ngày cụ
           thể ("Nhật ký bắt đầu ghi từ <ngày>") — CÙNG lý do đã từ chối
           câu đó ở trạng thái RỖNG phía trên: tầng này không có cách
           XÁC NHẬN đúng ngày nhật ký được BẬT trên site khách hàng cụ
           thể. Câu dưới đây chỉ nói ĐIỀU LUÔN ĐÚNG (dựng lại từ CHÍNH
           trường trên phiếu, không phải ghi trực tiếp), không đoán ngày. -->
      <p v-if="coDongSuyRa" class="tag" style="margin-top: 8px">
        Dòng có nhãn "Dựng lại từ phiếu" được suy ra từ dữ liệu đã ghi sẵn trên phiếu (ai gửi, ai duyệt), không phải ghi trực tiếp lúc thao tác xảy ra.
      </p>
    </template>
  </div>
</template>
