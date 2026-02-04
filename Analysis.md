# Phân tích Source Code dự án Demo Graph

## Tổng quan

Dự án này là một ứng dụng web chat cho phép người dùng hỏi về thông tin phim ảnh. Nó sửdụng kiến trúc full-stack bao gồm:

-   **Backend:** Một API được xây dựng bằng Python với FastAPI, sử dụng cơ sở dữ liệu đồ thị Neo4j để lưu trữ và truy vấn dữ liệu phim. Nó tích hợp với một mô hình ngôn ngữ lớn (LLM) để xử lý các truy vấn ngôn ngữ tự nhiên.
-   **Frontend:** Một giao diện chat được xây dựng bằng Next.js và React, cho phép người dùng tương tác với backend.

## Phân tích chi tiết

### Backend

#### Công nghệ sử dụng

-   **FastAPI:** Framework web hiệu suất cao để xây dựng các API bằng Python.
-   **Neo4j:** Cơ sở dữ liệu đồ thị được sử dụng để lưu trữ dữ liệu phim và các mối quan hệ giữa chúng (diễn viên, đạo diễn, thể loại).
-   **Uvicorn:** Máy chủ ASGI để chạy ứng dụng FastAPI.
-   **Pandas:** Được sử dụng để đọc và xử lý dữ liệu từ file CSV (`movies.csv`).
-   **HTTPX:** Thư viện client HTTP để giao tiếp với dịch vụ LLM.
-   **Docker:** `Dockerfile` và `docker-compose.yml` cho thấy dự án được thiết kế để chạy trong các container.

#### Cấu trúc file

-   `app/main.py`: Điểm vào chính của ứng dụng FastAPI. Nó định nghĩa các endpoint API, xử lý CORS, và quản lý vòng đời của ứng dụng (startup, shutdown).
    -   Endpoint `/api/chat`: Nhận câu hỏi từ người dùng, gọi `execute_graphrag_query` để lấy dữ liệu từ đồ thị, sau đó gọi `llm_client.generate_response` để tạo ra câu trả lời tự nhiên.
    -   Endpoint `/api/health`: Kiểm tra trạng thái của các dịch vụ phụ thuộc (Neo4j, vLLM).
-   `app/database.py`: Quản lý kết nối đến cơ sở dữ liệu Neo4j. Cung cấp các phương thức để kết nối, ngắt kết nối, thực thi truy vấn Cypher và tạo các chỉ mục (index).
-   `app/csv_importer.py`: Chịu trách nhiệm import dữ liệu từ file `movies.csv` vào cơ sở dữ liệu Neo4j. Nó đọc file CSV, tạo các node (Movie, Person, Genre, ProductionCompany) và các mối quan hệ giữa chúng.
-   `app/graphrag.py`: Triển khai logic GraphRAG (Retrieval-Augmented Generation trên đồ thị).
    -   `execute_graphrag_query`: Hàm chính, nhận câu hỏi của người dùng, sử dụng `llm_client.analyze_query` để phân tích và trích xuất các thực thể (diễn viên, thể loại, từ khóa). Dựa trên kết quả phân tích, nó sẽ gọi các hàm truy vấn Cypher tương ứng để lấy dữ liệu từ Neo4j.
-   `app/llm_client.py`: Client để tương tác với API của mô hình ngôn ngữ lớn (vLLM).
    -   `analyze_query`: Gửi câu hỏi của người dùng đến LLM để phân tích, xác định loại truy vấn và trích xuất các thuật ngữ chính.
    -   `generate_response`: Gửi câu hỏi và dữ liệu lấy từ đồ thị đến LLM để tạo ra một câu trả lời mạch lạc, tự nhiên theo phong cách của các nhà phê bình phim.
-   `movies.csv`: File dữ liệu chứa thông tin về các bộ phim.
-   `requirements.txt`: Liệt kê các thư viện Python cần thiết cho backend.

### Frontend

#### Công nghệ sử dụng

-   **Next.js:** Framework React để xây dựng giao diện người dùng.
-   **React:** Thư viện chính để xây dựng các thành phần UI.
-   **React Markdown:** Được sử dụng để hiển thị các câu trả lời từ backend (được định dạng bằng Markdown).
-   **TypeScript:** Cung cấp kiểu tĩnh cho mã JavaScript.

#### Cấu trúc file

-   `src/app/page.tsx`: Trang chính của ứng dụng, chỉ đơn giản là hiển thị thành phần `ChatInterface`.
-   `src/components/ChatInterface.tsx`: Thành phần chính của giao diện người dùng.
    -   Quản lý trạng thái của cuộc trò chuyện (tin nhắn, trạng thái loading).
    -   Hiển thị lịch sử tin nhắn.
    -   Cung cấp một form để người dùng nhập câu hỏi.
    -   Khi người dùng gửi câu hỏi, nó sẽ gọi đến API route `/api/chat` của Next.js.
-   `src/app/api/chat/route.ts`: Một API route của Next.js hoạt động như một proxy. Nó nhận yêu cầu từ `ChatInterface`, chuyển tiếp đến API backend của FastAPI, sau đó trả về kết quả cho frontend. Điều này giúp tránh các vấn đề về CORS và giữ an toàn cho URL của backend.
-   `package.json`: Liệt kê các thư viện JavaScript cần thiết và các script để chạy, xây dựng và lint dự án frontend.

## Luồng hoạt động

1.  **Khởi động:**
    -   Backend FastAPI khởi động, kết nối với Neo4j.
    -   Nếu cơ sở dữ liệu Neo4j trống, nó sẽ tự động import dữ liệu từ `movies.csv`.
    -   Frontend Next.js khởi động máy chủ phát triển.

2.  **Tương tác người dùng:**
    -   Người dùng truy cập trang web và thấy giao diện chat.
    -   Người dùng nhập một câu hỏi (ví dụ: "Which Crime movies are Joe Pesci in?") và nhấn gửi.

3.  **Xử lý Frontend:**
    -   `ChatInterface.tsx` bắt sự kiện, thêm tin nhắn của người dùng vào danh sách tin nhắn và đặt trạng thái `isLoading` thành `true`.
    -   Nó gửi một yêu cầu POST đến `/api/chat` (API route của Next.js) với câu hỏi của người dùng.

4.  **Proxy API (Next.js):**
    -   `route.ts` nhận yêu cầu và chuyển tiếp nó đến endpoint `/api/chat` của backend FastAPI.

5.  **Xử lý Backend:**
    -   `main.py` nhận yêu cầu.
    -   Nó gọi `execute_graphrag_query` trong `graphrag.py`.
    -   Bên trong `execute_graphrag_query`, nó gọi `llm_client.analyze_query` để phân tích câu hỏi. LLM trả về một đối tượng JSON, ví dụ: `{ "query_type": "actor_genre", "actor": "Joe Pesci", "genre": "Crime" }`.
    -   Dựa trên `query_type`, `graphrag.py` thực thi một truy vấn Cypher cụ thể trên cơ sở dữ liệu Neo4j để tìm các bộ phim phù hợp.
    -   Kết quả từ Neo4j (danh sách các phim) được trả về cho `main.py`.
    -   `main.py` sau đó gọi `llm_client.generate_response`, truyền vào câu hỏi ban đầu và danh sách phim tìm được.
    -   LLM tạo ra một câu trả lời tự nhiên, tóm tắt các kết quả.
    -   `main.py` định dạng câu trả lời cuối cùng dưới dạng Markdown, bao gồm phần bình luận của AI, một bảng dữ liệu phim và các chỉ số hiệu suất.

6.  **Trả về kết quả:**
    -   Backend FastAPI trả về câu trả lời đã định dạng cho proxy API của Next.js.
    -   Proxy API chuyển tiếp câu trả lời cho `ChatInterface.tsx`.
    -   `ChatInterface` nhận dữ liệu, thêm tin nhắn của trợ lý vào danh sách, và đặt `isLoading` thành `false`.
    -   Thành phần `ReactMarkdown` hiển thị câu trả lời được định dạng đẹp cho người dùng.

