<script setup>
// Khối "Hàng chưa có trong hệ thống" — HIỆN RIÊNG cho quản lý xem trước khi
// duyệt.
//
// VÌ SAO CÓ KHỐI NÀY (chủ đầu tư báo 05/09/2026): quản lý duyệt KHÔNG NHÌN
// THẤY các dòng hàng gõ tay. Nguyên nhân: `BangMatHang.vue` đọc
// `don.dat_ngoai` — tức từ ĐƠN HÀNG, mà đơn chỉ tồn tại SAU khi duyệt. Ở
// "Chờ duyệt" chỉ có PHIẾU, nên đúng khoảnh khắc quản lý bấm duyệt thì các
// dòng đó vô hình. Họ duyệt một thứ họ không nhìn thấy.
//
// VÌ SAO RIÊNG, KHÔNG NHÉT VÀO BẢNG: chủ đầu tư chốt, và lý do của chính họ
// đứng vững — "hàng này có nhiều trường và là hàng mới cần xem xét kĩ".
// Chín trường nhồi vào một hàng của bảng thì hoặc bảng tràn ngang, hoặc phải
// giấu bớt trường — mà giấu bớt đúng là thứ vừa gây ra lỗi này.
//
// CHỈ DÒNG CHƯA KHỚP MÃ (chủ đầu tư 08/09/2026: "sau khi đã khớp mã hàng từ
// Miyano thì chỉ hiển thị đúng 1 bảng"). Việc LỌC nằm ở màn cha
// (`ChiTietYeuCau.vue`) chứ không ở đây: cờ `da_xu_ly` chỉ sống trên ĐƠN,
// nên chọn nguồn dòng là một quyết định về CHỨNG TỪ NÀO ĐANG CÓ — đúng câu
// hỏi màn cha đã trả lời cho mọi khối khác. Khối này giữ đúng một việc: vẽ.
//
// Hệ quả cố ý: khớp hết thì `dong` rỗng và khối TỰ BIẾN MẤT — màn còn đúng
// một bảng, không cần một cờ bật/tắt theo giai đoạn nào (cờ như vậy sẽ vỡ ở
// ca khớp một nửa, là trạng thái bình thường lúc Miyano đang làm dở).
import TheHangMoi from './TheHangMoi.vue'

defineProps({
  dong: { type: Array, default: () => [] },
  deXuat: { type: String, default: '' },
  // ĐÃ CÓ ĐƠN hay chưa — quyết định khối này đang kể chuyện gì.
  //
  // TRƯỚC duyệt: đây là thứ quản lý phải xem kỹ để mà duyệt.
  // SAU duyệt: đơn đã chạy, những dòng còn ở đây là hàng MIYANO ĐANG TÌM
  // NGUỒN, chưa báo giá — và người đọc lúc này thường là KHÁCH, không phải
  // quản lý.
  //
  // Không có cờ này thì một đơn đã duyệt còn dòng chưa khớp (đúng ca thiết
  // kế theo-từng-dòng sinh ra để đỡ) sẽ nói với khách "cần xem kỹ trước khi
  // duyệt" — báo sai giai đoạn — và mất hẳn trạng thái "đang tìm nguồn" mà
  // bảng phụ cũ vẫn nói. Đó là thứ chủ đầu tư đòi: *"bên khách hàng có thể
  // nhìn thấy hàng được báo giá"*.
  daCoDon: { type: Boolean, default: false },
})
</script>

<template>
  <template v-if="dong && dong.length">
    <div class="card mb10">
      <div v-if="daCoDon" class="h3">Hàng chưa có mã — Miyano đang tìm nguồn</div>
      <div v-else class="h3">Hàng chưa có trong hệ thống — cần xem kỹ trước khi duyệt</div>
      <p v-if="daCoDon" class="tag" style="margin: 4px 0 10px">
        {{ dong.length }} mặt hàng chưa có trong danh mục. Miyano đang tìm nguồn;
        khi tìm được, hàng sẽ hiện ở bảng mặt hàng phía dưới kèm đơn giá.
      </p>
      <p v-else class="tag" style="margin: 4px 0 10px">
        {{ dong.length }} mặt hàng nhân viên tự khai vì không tìm thấy trong danh
        mục. Miyano sẽ tìm nguồn và báo giá sau khi được duyệt.
      </p>

      <TheHangMoi
        v-for="(d, i) in dong"
        :key="d.name || i"
        :d="d"
        :de-xuat="deXuat"
        :nhan="daCoDon ? 'Miyano đang tìm nguồn' : ''"
      />
    </div>
  </template>
</template>
