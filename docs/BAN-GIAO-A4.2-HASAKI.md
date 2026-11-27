# Bàn giao A4.2 · Frappe CRM Hasaki

Mốc đối soát: 27/11/2026. Môi trường kiểm tra: site `crm.localhost`, Frappe **15.127.1**, Frappe CRM **1.92.0**, chạy bằng Docker. Dữ liệu trong báo cáo dùng để mô phỏng nghiệp vụ Hasaki.

## 1. Dữ liệu đã kiểm tra trên site

| DocType | Số bản ghi | Ghi chú bàn giao |
| --- | ---: | --- |
| `Contact` | 108 | 100 khách demo có mã `KH0001`–`KH0100`, cả 100 có `mobile_no`. |
| `Address` | 100 | Cả 100 có tiền tố `HSK-DEMO-ADDR`. Địa chỉ liên kết với Contact qua bảng `links`. |
| `CRM Product` | 200 | Cả 200 có giá trị trong trường `image`. SKU nằm ở `product_code`. Danh mục liên kết qua `custom_product_category`, giá vốn ở `custom_cost_price`. |
| `HSK Product Category` | 14 | 4 danh mục cha và 10 danh mục con theo báo cáo bàn giao dữ liệu. |
| `CRM Lead` | 61 | 60 bản ghi demo và 1 bản ghi có trước. Có 30 bản ghi mang cờ `converted = 1`. |
| `CRM Deal` | 30 | Deal có thể liên kết về Lead, Contact và chứa bảng dòng sản phẩm. |
| `CRM Call Log` | 100 | Nhật ký gọi liên kết với Lead hoặc Deal. |
| `CRM Task` | 50 | Tác vụ có người phụ trách và liên kết với Lead hoặc Deal. |
| `User` | 6 | Administrator, Guest và 4 tài khoản demo nghiệp vụ theo báo cáo bàn giao. |
| `CRM Lead Source` | 8 | Danh sách ở mục 2. |
| `CRM Lead Status` | 7 | Danh sách ở mục 2. |
| `CRM Deal Status` | 8 | Danh sách ở mục 2. |
| `CRM Lost Reason` | 14 | Dùng lại lý do thất bại đã có trên site. |
| `Email Template` | 2 | Đã có cấu hình gửi mail và ảnh email nhận được trong tài liệu nhóm. |
| `Assignment Rule` | 1 | Rule phân Lead cho tư vấn viên. |

Số lượng lấy từ Bench Console của site đã kiểm tra. Danh sách Leads trên giao diện có thể ẩn Lead đã chuyển đổi. Khi đối soát số liệu, dùng tổng trong database và ghi rõ tiêu chí lọc. Với ảnh sản phẩm, trường đúng để đếm là `image`. Có thể mở một vài sản phẩm để kiểm tra tệp ảnh hiển thị sau khi restore.

## 2. Pipeline và cấu hình CRM

| Hạng mục | Giá trị đã bàn giao |
| --- | --- |
| Nguồn Lead | TikTok Shop, WooCommerce, App Hasaki, Hotline, Zalo OA, Web Form, Website, Facebook |
| Trạng thái Lead | `New`, `Contacted`, `Nurture`, `Qualified`, `Converted`, `Unqualified`, `Junk` |
| Các cột Deal | `Qualification`, `Demo/Making`, `Proposal/Quotation`, `Negotiation`, `Ready to Close`, `Cho giao hang`, `Won`, `Lost` |
| Phân công | 1 Assignment Rule chia Lead cho tư vấn viên, kèm Sales Hierarchy cho nhóm nghiệp vụ |
| Vai trò demo | Quản trị dùng `System Manager`, quản lý dùng `Sales Manager`, tư vấn dùng `Sales User`, hai tài khoản CSKH dùng Role Profile `CSKH Hasaki` gồm `Sales User` và vai trò CSKH |
| Thiết lập | VND, `Asia/Ho_Chi_Minh`, giao diện tiếng Anh và tiếng Việt, avatar tài khoản quản trị |
| Mẫu in | Đã thấy bản in hóa đơn GTGT minh họa trên `CRM Deal` trong tab *Cấu hình CRM*. Bản in báo giá riêng còn cần bổ sung minh chứng nếu nhóm nộp cả hai mẫu. |

**Luồng demo đề xuất:** Tạo Lead, chọn nguồn và kiểm tra người phụ trách. Chuyển Lead đủ điều kiện thành Deal, thêm sản phẩm rồi cập nhật giai đoạn theo kịch bản. Kết thúc bằng `Won` hoặc `Lost`; với `Lost`, lưu lý do. Danh sách trạng thái trên mô tả các giá trị đã cấu hình. Khi viết integration hoặc báo cáo, kiểm tra tên trạng thái và điều kiện chuyển ngay trên site tích hợp.

## 3. Nhận dữ liệu qua Git

- - **Snapshot mới (27/11/2026)** nằm tại `backups/hasaki_site_snapshot.hskenc`. SHA-256: `0746be15b3100bb5ebbbc2a642f1f80f80deea172f92a0c9f28dc7fca1d50351`. Snapshot cũ vẫn có thể lấy ở commit `6c93a2e`.
- **Nếu site đã có dữ liệu Hasaki**, dùng site hiện tại và đối chiếu 14 danh mục, 200 sản phẩm và 100 Contact demo có số điện thoại. **Nếu site thiếu dữ liệu nền**, nhận mật khẩu giải mã riêng từ nhóm, kiểm tra SHA-256 rồi giải mã snapshot. Khôi phục database và các tệp đính kèm lên một site riêng có phiên bản tương thích. Đối soát theo mục 1 sau khi khôi phục. Nhóm đã ghi nhận một lần khôi phục trên `hasaki-test.localhost`.
- Snapshot lưu trạng thái ở thời điểm tạo. Dùng các ảnh trong tab *Cấu hình CRM* cho minh chứng chụp sau mốc đó. Khi tích hợp phần việc mới, đồng bộ source của app, kiểm tra app đã cài và sao lưu site trước khi migrate. Giữ mật khẩu, token, SQL thô và `site_config.json` ngoài Git.

## 4. Liên kết dữ liệu cho Custom App

| Đối tượng | Khóa dùng cho Link hoặc đối chiếu |
| --- | --- |
| Khách hàng | `Contact.name`. `custom_customer_id` như `KH0001` dùng để tìm kiếm và đối soát. |
| Sản phẩm | `CRM Product.name` dùng cho Link. `CRM Product.product_code` dùng để đối chiếu SKU từ WooCommerce. |
| Danh mục | `HSK Product Category.name` |
| Lead và Deal | `CRM Lead.name` và `CRM Deal.name` |
| Tài khoản phụ trách | `User.name` |
| Nguồn tiếp nhận | `CRM Lead Source.name`. Form WordPress dùng nguồn `Web Form` theo bàn giao A4.8. |

Dùng lại master data đã bàn giao. Theo Technical Contract v1.1, cửa hàng, kênh bán và phương thức thanh toán có thể biểu diễn bằng trường `Select` hoặc `Data` khi nghiệp vụ cần. `HSK Order.source_channel` đã dùng các giá trị `WooCommerce`, `POS`, `Manual`. `HSK Payment.payment_method` dùng `Data`. Nguồn khách hàng và ngày mua đầu tiên phục vụ CAC/Retention được truy vết từ Lead, Deal và Order. Trường hợp thiếu liên kết được ghi là *Không xác định*.

| Phần việc | Dữ liệu cần dùng hoặc bàn giao sau |
| --- | --- |
| WordPress và WooCommerce · Nhi | Tích hợp dùng Contact, SKU của CRM Product và nguồn Lead `Web Form`. Source `hasaki_integration` có `HSK Order`, `HSK Order Item`, `HSK Order Status History`, `HSK Payment` và `HSK Integration Event`. Nhóm cần chốt quyền sở hữu Order và Payment trước khi tích hợp nhiều app. |
| Khiếu nại và đổi trả · Nghi | Chuẩn bị bản ghi demo cho Complaint, Return Request, Return Inspection và Refund. Liên kết tới Contact, Order và Payment có liên quan theo nghiệp vụ. |
| Hội viên, quà và Social Inbox · Trâm | Liên kết hội viên với Contact hiện có, chuẩn bị tài khoản hội viên, quà và giao dịch demo theo kịch bản. Social Inbox tái sử dụng Contact và Lead khi có liên kết. |
| Voucher, chi phí và báo cáo · Tường | Chuẩn bị dữ liệu voucher và chi phí của phần mình. Dùng Lead/Deal cho chuyển đổi, Order/Payment cho giao dịch, Refund cho hoàn tiền và bản ghi nghiệp vụ tương ứng cho quà, voucher và chi phí. |

Việc cài hoặc migrate app đưa **cấu trúc DocType và cấu hình có trong source** lên site. Bản ghi demo xuất hiện khi app có bước nạp dữ liệu hoặc khi người phụ trách nhập chúng. Các số lượng dự kiến ở tab *CƠ SỞ DỮ LIỆU* và *Tab 15* dùng để thiết kế kịch bản. Dùng các bản ghi cần thiết cho từng luồng demo, theo quyền sở hữu đã chốt trong Technical Contract v1.1.

## Nguồn đối chiếu

- Google Docs nội bộ *ĐỒ ÁN - HASAKI*, các tab *Cài đặt*, *Cấu hình CRM*, *Report - trâm*, *QUY TẮC* và *Báo cáo CRM/Sales*.
- Kết quả đối soát Bench Console trên `crm.localhost` ngày 27/11/2026.
- [Bàn giao kỹ thuật A4.8](https://github.com/yennhinguyenuit/hasaki/blob/main/apps/hasaki_integration/docs/HANDOVER.md).
