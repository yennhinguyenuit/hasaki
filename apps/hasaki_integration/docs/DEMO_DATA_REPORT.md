# BÁO CÁO HASAKI DEMO DATASET V1.0

**Dữ liệu giả lập phục vụ đồ án, không phải số liệu kinh doanh nội bộ Hasaki.**

Ngày kiểm tra: 27/11/2026. Trạng thái: Đã import qua Migration Patch; xem DEMO_DATA_DEPLOYMENT_REPORT.md cho kết quả kiểm thử runtime mới nhất.

## Thống kê dataset

| Chỉ tiêu | Giá trị |
|---|---:|
| Khách có giao dịch | 100 |
| Order | 1,200 |
| Order Item | 3,663 |
| Payment | 1,200 |
| Payment Paid | 1,083 |
| Payment Pending | 117 |
| Sự kiện nghiệp vụ trong JSON | 3,622 |
| Đơn lịch sử bổ sung | 0 |
| Tổng giá trị đơn VND | 1,691,883,950 |
| AOV toàn bộ đơn VND | 1,409,903.29 |
| Doanh thu Completed + Paid VND | 1,436,163,950 |
| Chiết khấu toàn bộ đơn VND | 64,947,050 |
| Giá vốn toàn bộ đơn VND | 1,229,020,000 |
| Giá vốn đơn doanh thu VND | 1,040,716,000 |
| Doanh thu trừ giá vốn hàng bán VND | 395,447,950 |
| Tỷ lệ khách có hơn một đơn (mọi trạng thái) | 90% |

Doanh thu gồm phí vận chuyển; hiệu số doanh thu–giá vốn chưa trừ chi phí vận chuyển, Marketing hoặc chi phí ABC. Không phải lợi nhuận ròng.

## Kênh

| Nhóm | Giá trị |
|---|---:|
| POS | 480 |
| WooCommerce | 660 |
| Manual | 60 |

## Trạng thái

| Nhóm | Giá trị |
|---|---:|
| Completed | 1,020 |
| Pending | 24 |
| Cancelled | 72 |
| Shipping | 48 |
| Processing | 36 |

## Tháng

| Nhóm | Giá trị |
|---|---:|
| 2025-11 | 98 |
| 2025-12 | 98 |
| 2026-01 | 101 |
| 2026-02 | 153 |
| 2026-03 | 96 |
| 2026-04 | 70 |
| 2026-05 | 83 |
| 2026-06 | 66 |
| 2026-07 | 89 |
| 2026-08 | 85 |
| 2026-09 | 68 |
| 2026-10 | 193 |

## Doanh số dòng hàng Completed theo danh mục, chưa gồm phí vận chuyển

| Nhóm | Giá trị |
|---|---:|
| CAT-73243996 — Serum | 425,050,550 |
| CAT-3FAAFCEB — Kem dưỡng | 195,975,050 |
| CAT-031EC227 — Chống nắng | 187,456,150 |
| CAT-C91AF8C5 — Sữa rửa mặt | 144,886,300 |
| CAT-90FDB548 — Toner | 125,179,150 |
| CAT-379DF228 — Tẩy trang | 115,863,650 |
| CAT-24B86273 — Son thỏi | 80,517,450 |
| CAT-01E2B9DC — Dầu gội và dầu xả | 68,949,450 |
| CAT-E1DCA3E0 — Mặt nạ | 56,564,100 |
| CAT-C1EA97B9 — Sữa tắm và dưỡng thể | 35,047,100 |

## Giả định hành vi và giỏ hàng

100 mã KH được chia theo thứ tự mã: 10 khách mới × 1 đơn; 20 khách không thường xuyên × 3; 20 khách định kỳ × 10; 20 khách thân thiết × 20; 20 khách giá trị cao × 25; 10 khách lâu chưa quay lại × 3. Đây là phân nhóm mô phỏng, không ghi nhãn vào Contact. Khách mới phát sinh tháng 10; khách lâu chưa quay lại chỉ phát sinh trước tháng 3. Ngày mua còn lại lấy mẫu có trọng số; không phải lịch định kỳ bảo đảm cùng ngày hàng tháng.

Giỏ hàng được ghép theo tên sản phẩm thành nhóm chăm sóc da/tóc/cơ thể/trang điểm/thiết bị, ưu tiên cùng nhóm và chỉ dùng SKU có thật. Đây là quy tắc sinh giỏ, không tạo danh mục mới. Mỗi đơn 1–4 dòng; nhóm giá trị cao có thể mua số lượng lớn hơn. Ngày 11/11, 12/12, 8/3, 20/10 có trọng số 4; nửa đầu tháng 2 trọng số 3; giữa/cuối tháng trọng số 2; ngày thường 1. Các đơn chưa hoàn thành đặt 28–31/10. Không mô phỏng chi nhánh thật; source_store là namespace demo.

Giá bán/giá vốn lấy snapshot hiện hữu và giả định cố định cả kỳ. Chiết khấu giả lập 0/5/10/15%, làm tròn xuống VND. POS không phí giao; kênh khác phí 25.000 khi giá trị hàng dưới 500.000, còn lại miễn phí. Completed luôn có Payment Paid; Pending/Cancelled có Payment Pending (bản ghi dự kiến, chưa thu tiền); Processing/Shipping chỉ Paid khi không phải COD. Không có Refund hoặc chứng từ thanh toán đính kèm.

## Giao dịch demo

| Scenario | Thành viên | Khóa tra cứu |
|---|---|---|
| NGHI-01 | Nghi | demo:v1:pos:DEMO-V1-0024 |
| NGHI-02 | Nghi | demo:v1:pos:DEMO-V1-0005 |
| TRAM-01 | Trâm | demo:v1:pos:DEMO-V1-0002 |
| TRAM-02 | Trâm | woo:hasaki-demo-v1:DEMO-V1-0041 |
| TUONG-01 | Tường | demo:v1:pos:DEMO-V1-0001 |
| NHI-BLOCKED | Nhi | BLOCKED: chưa có SKU Havatek |

Các điều kiện đổi trả tính tại mốc 31/10/2026 và còn phải đối chiếu chính sách của nhóm; không khẳng định còn hạn vào ngày 27/11/2026. Ngày Completed online trong JSON chỉ là ngày nhận hàng giả lập, không dùng như bằng chứng giao nhận hoặc ngày bắt đầu bảo hành thật.

## Audit thực tế

Frappe 15.127.1, CRM 1.92.0, hasaki_integration 0.0.1. Bench thấy ba App cài trên site: frappe, crm, hasaki_integration. BeautyMatch có source trong Bench nhưng không nằm trong installed_apps của site; không chỉnh sửa. Counts trước import: Contact 108; Address 100; User 6; CRM Lead 99; CRM Deal 30; CRM Product 200; CRM Lead Source 8; HSK Product Category 14; Order 57; Item 57; History 69; Payment 15; Integration Event 257.

100 Contact có mã KH; 8 Contact không có mã được loại khỏi mapping, không chỉnh sửa. CRM Product.custom_category trống; liên kết danh mục thực tế là custom_product_category. 200 SKU có giá bán/giá vốn dương và mapping duy nhất. Không có Havatek. Controller không tự gán loyalty_eligible, receiver chỉ giữ cờ cũ hoặc mặc định 0.

Không phát hiện Notification/Webhook đang bật. Safety preflight đối chiếu Document Events đã audit, hash controller và các rule động liên quan Order/Payment; thay đổi sẽ làm import dừng thay vì tắt hook. Site khác có hook Loyalty/Refund/Notification phải được chủ App rà soát trước; không sửa policy để bỏ qua lỗi.

## Giới hạn và việc còn lại

- Dữ liệu giả lập đồ án, không phải số liệu nội bộ Hasaki.
- Không có SKU Havatek; không tạo đơn lịch sử hoặc phiếu bảo hành.
- Lịch sử nghiệp vụ riêng; audit trail database ghi thời điểm import thực.
- Giá bán/giá vốn snapshot được giả định cố định cả kỳ; chiết khấu 0/5/10/15%.
- Giữ loyalty_eligible=0 vì chưa có quy tắc nhóm được triển khai.
- Demo đổi trả tính tại 31/10/2026; không xác nhận đủ điều kiện tại ngày hiện tại.
- Ngày Completed online chỉ là ngày nhận giả lập trong JSON, không phải bằng chứng giao nhận.
- CAC/ABC cần dữ liệu chi phí; không tạo marketing cost hoặc voucher.

- Migration Patch, migrate lần hai, seeder độc lập và regression A4.8 37/37 đã Passed trên crm.localhost; dữ liệu test đã dọn đúng phạm vi.
- Install-app lần đầu end-to-end vẫn Not Tested; không tạo/cài lại App để kiểm thử trên site hiện tại. Desk đã được người dùng kiểm tra thủ công và xác nhận đúng.
- Không tạo site thay thế, không restore database và không tạo lại Master Data để vượt giới hạn này.
- Đã backup, xác nhận và bật demo trên crm.localhost; không bật cờ trên production.
- Build wheel bằng flit_core 3.12.0 cô lập trong thư mục tạm Passed: đủ 8 JSON nguyên byte và patch; không cài vào site hoặc thay thư viện Bench.

Bằng chứng: demo_site_audit.json, demo_dry_run.json, demo_offline_results.json, demo_package_results.json; manifest chứa checksum từng JSON.
