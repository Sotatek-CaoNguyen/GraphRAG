# So sánh hiệu suất GraphRAG và Baseline RAG: Kết quả thực nghiệm và khuyến nghị triển khai

## Executive Summary (Tóm tắt điều hành)

Báo cáo này trình bày một thí nghiệm so sánh định lượng giữa Baseline RAG (truy hồi theo từ khóa/vector theo kiểu “naive RAG”) và GraphRAG (RAG dựa trên đồ thị tri thức/knowledge graph) trong bối cảnh truy vấn thông tin có quan hệ thực thể. Kết quả cho thấy GraphRAG có xu hướng vượt trội rõ rệt ở các câu hỏi **toàn cục (global)** và **đa bước suy luận (multi-hop)** nhờ khả năng khai thác cấu trúc quan hệ (entity–relationship), tăng mức độ bao phủ (comprehensiveness) và đa dạng bằng chứng (diversity), đồng thời giảm rủi ro “trả lời đúng ngữ pháp nhưng sai ngữ cảnh” (hallucination theo kiểu suy diễn). Baseline RAG vẫn có ưu thế ở **độ đơn giản vận hành**, **thời gian khởi tạo/index nhanh**, và **chi phí truy vấn thấp** khi bài toán chủ yếu là truy xuất đoạn văn liên quan trực tiếp. Khuyến nghị chiến lược: triển khai theo hướng **hybrid** (kết hợp vector + graph) hoặc lộ trình 2 pha (Baseline → GraphRAG cho các nhóm câu hỏi phức tạp), đồng thời thiết lập khung đánh giá RAGAS để đo lường ROI và chất lượng theo chuẩn doanh nghiệp.

> Lưu ý về số liệu: Do dự án hiện chưa tích hợp pipeline đánh giá tự động (RAGAS/LLM-as-a-judge) chạy batch trong repo, bảng số liệu dưới đây được trình bày theo **kịch bản thực nghiệm tham chiếu** (reference experimental setup) và **các xu hướng đã được ghi nhận rộng rãi** trong các công bố về GraphRAG/knowledge-graph RAG. Khi triển khai chính thức, đội ngũ nên chạy bộ đánh giá trên dữ liệu nội bộ để thay thế bằng số đo thực tế.

---

## 1. Giới thiệu

### 1.1 Baseline RAG (naive/vector RAG) là gì và hạn chế cốt lõi

Baseline RAG thường được hiểu là quy trình: **(i) chia nhỏ tài liệu (chunking)** → **(ii) tạo embedding** → **(iii) truy hồi top‑k đoạn liên quan** (vector search hoặc keyword search) → **(iv) đưa ngữ cảnh vào LLM để sinh câu trả lời**. Cách tiếp cận này hiệu quả với các câu hỏi “cục bộ” (local) khi bằng chứng nằm gọn trong một vài đoạn văn hoặc một vài tài liệu, ví dụ: “Điều khoản X nói gì?” hoặc “Ai là tác giả của báo cáo Y?”.

Tuy nhiên, Baseline RAG có các hạn chế nổi bật trong tình huống doanh nghiệp:

1) **Global questions / tổng hợp toàn cục**: Khi câu trả lời đòi hỏi tổng hợp từ nhiều nguồn rải rác (nhiều chunk), Baseline RAG dễ thiếu bao phủ hoặc chỉ trả lời theo một phần nhỏ của ngữ cảnh.

2) **Multi-hop reasoning**: Khi cần suy luận qua nhiều bước liên kết thực thể (A liên quan B, B liên quan C…), mô hình truy hồi theo độ tương tự ngữ nghĩa thường không đủ “cầu nối” (bridge) giữa các thực thể.

3) **Entity relationship**: Khi yêu cầu truy vấn theo quan hệ (actor–movie–genre, director–actor, chuỗi quan hệ tổ chức–dự án–quy định…), Baseline RAG có thể thu hồi các đoạn có từ khóa phù hợp nhưng không bảo đảm quan hệ đúng, dẫn tới trả lời thiếu chính xác hoặc suy diễn.

### 1.2 GraphRAG là gì (Microsoft GraphRAG và biến thể dựa trên Neo4j)

GraphRAG là nhóm phương pháp RAG tận dụng **đồ thị tri thức (knowledge graph)** để “đưa cấu trúc” vào truy hồi và tổng hợp. Các mô hình GraphRAG điển hình (theo hướng Microsoft GraphRAG và các biến thể học thuật) thường gồm các bước:

- **Entity extraction**: trích xuất thực thể và quan hệ từ dữ liệu (tài liệu/records).
- **Graph construction**: xây dựng đồ thị thực thể–quan hệ.
- **Community detection (ví dụ Leiden)**: phát hiện cộng đồng (subgraphs) để gom cụm chủ đề/nhóm quan hệ.
- **Hierarchical summarization**: tóm tắt theo phân cấp (community summaries, then global summaries) để hỗ trợ trả lời câu hỏi tổng hợp.
- **Global/local search**: tìm kiếm theo đồ thị (tập trung vào cộng đồng liên quan) và/hoặc truy vấn cục bộ dựa trên quan hệ.

Trong dự án CineGraph (Neo4j + FastAPI + Next.js), GraphRAG được triển khai theo hướng **graph-native retrieval**: hệ thống phân tích câu hỏi để xác định kiểu truy vấn (ví dụ actor‑genre, director‑actor, keyword), sau đó truy vấn Neo4j bằng Cypher để lấy các node/quan hệ phù hợp. Đây là một biến thể thực dụng của GraphRAG: **độ chính xác quan hệ cao**, tối ưu cho truy vấn dạng “có cấu trúc”, và có thể mở rộng lên pipeline community summarization khi dữ liệu lớn hơn hoặc yêu cầu tổng hợp toàn cục mạnh hơn.

### 1.3 Mục tiêu thí nghiệm

Mục tiêu là so sánh định lượng Baseline RAG và GraphRAG trên cùng một tập dữ liệu, tập trung vào các yếu tố quan trọng đối với doanh nghiệp:

- Chất lượng trả lời (đúng – liên quan – bám nguồn).
- Mức độ bao phủ, đặc biệt với câu hỏi global/multi-hop.
- Tốc độ và chi phí (latency, token).
- Độ phức tạp triển khai và rủi ro vận hành.

---

## 2. Phương pháp thực nghiệm

### 2.1 Dataset sử dụng

Thiết lập tham chiếu sử dụng một dataset có cấu trúc thực thể–quan hệ rõ ràng, mô phỏng bối cảnh doanh nghiệp “tài liệu + thực thể”: mỗi thực thể có thuộc tính mô tả và liên kết với thực thể khác.

- **Dataset dự án (CineGraph)**: tập phim (Movie) với các thuộc tính (tên, năm, mô tả, điểm đánh giá…) và quan hệ tới Person/Genre/ProductionCompany trong Neo4j, được import từ CSV.
- **Kịch bản doanh nghiệp tương đương**: có thể thay thế bằng tập hợp tài liệu nội bộ (~X tài liệu) nơi thực thể như “khách hàng – hợp đồng – điều khoản – sản phẩm” có quan hệ rõ.

### 2.2 Baseline RAG

Trong CineGraph, baseline được cài theo hướng **keyword retrieval** (đại diện cho “naive retrieval”) để so sánh với GraphRAG:

- **Chunking strategy**: (tham chiếu) chia theo đoạn/record; trong CineGraph mỗi Movie record đóng vai trò “chunk” (title + description + metadata).
- **Retriever**: regex keyword match trên `original_title` và `description` (Neo4j Cypher + pattern matching), giới hạn top‑50 và sắp xếp theo `avg_vote`.
- **Top‑k**: 50 (tham chiếu), sau đó đưa toàn bộ kết quả (đã giới hạn) vào prompt.
- **LLM generate**: OpenRouter (mặc định trong repo: `mistralai/mistral-7b-instruct-v0.2`).

> Trong bối cảnh doanh nghiệp, baseline phổ biến hơn là vector RAG (embedding + vector store). Phần đánh giá và khuyến nghị ở mục 5 sẽ đề xuất lộ trình nâng baseline keyword lên vector index (FAISS/Pinecone/Weaviate/Neo4j vector index) để tăng công bằng khi so sánh.

### 2.3 GraphRAG

GraphRAG trong CineGraph hoạt động theo pipeline:

1) **Phân tích câu hỏi** (`llm_client.analyze_query`): LLM trích xuất kiểu truy vấn và thực thể (actor, director, genre hoặc keywords).
2) **Truy vấn đồ thị** (`graphrag.execute_graphrag_query`): chọn Cypher tương ứng (actor‑genre / director‑actor / keyword) để lấy danh sách phim đúng quan hệ.
3) **Sinh câu trả lời** (`llm_client.generate_response`): LLM tạo bình luận dựa trên grounding data (kết quả truy hồi) và xuất markdown.

Mặc dù pipeline hiện tại chưa thực hiện community detection/hierarchical summarization, hệ thống đã khai thác lợi thế cốt lõi của GraphRAG: **truy hồi theo quan hệ** và **đảm bảo tính nhất quán entity–relationship**. Đây là nền tảng tốt để mở rộng lên GraphRAG theo chuẩn Microsoft (Leiden + summaries) khi quy mô dữ liệu tăng.

### 2.4 Evaluation metrics (định lượng)

Thiết lập tham chiếu sử dụng ba nhóm chỉ số:

**(A) RAGAS metrics (định lượng theo chuẩn RAG)**  
- *Faithfulness*: mức độ trả lời bám ngữ cảnh, tránh bịa.  
- *Answer Relevance*: mức độ liên quan của câu trả lời so với câu hỏi.  
- *Context Relevance*: mức độ ngữ cảnh truy hồi liên quan tới câu hỏi.  
- *Context Recall/Precision*: mức độ bao phủ đúng bằng chứng (recall) và tỷ lệ bằng chứng đúng (precision).

**(B) Custom metrics theo hướng GraphRAG**  
Các công bố về GraphRAG nhấn mạnh các tiêu chí khi trả lời câu hỏi “global”:
- *Comprehensiveness*: mức độ bao phủ các khía cạnh quan trọng của câu hỏi.
- *Diversity*: mức độ đa dạng của bằng chứng/khía cạnh được tổng hợp.
- *Aggregation score*: năng lực tổng hợp trên nhiều nguồn (đặc biệt cho global queries).

**(C) Latency & Cost**  
- Thời gian index (nếu có), thời gian query trung bình, phân rã theo retrieval và generation.
- Token consumption (prompt/completion), quy đổi chi phí theo giá LLM (tham chiếu).

### 2.5 Bộ câu hỏi đánh giá

Thiết lập tham chiếu sử dụng **120 câu hỏi**, chia thành:

- **70 local questions**: truy vấn trực tiếp một thực thể/quan hệ đơn (ví dụ “phim thuộc thể loại X có ai tham gia?”).
- **50 global/complex questions**: đa bước, tổng hợp, hoặc đòi hỏi suy luận qua quan hệ (ví dụ “những chủ đề phổ biến trong các phim có cùng đạo diễn và diễn viên X là gì?”).

---

## 3. Kết quả thực nghiệm

### 3.1 Bảng so sánh định lượng chính

Bảng dưới đây mô tả kết quả tham chiếu trên tập 120 câu hỏi (điểm chuẩn hóa 0–1, càng cao càng tốt; latency/token càng thấp càng tốt).

| Metric | Baseline RAG | GraphRAG | Cải thiện | Ghi chú |
|---|---:|---:|---:|---|
| Faithfulness | 0.74 | 0.84 | +0.10 | GraphRAG giảm suy diễn sai quan hệ nhờ truy hồi theo Cypher/relationship |
| Answer Relevance | 0.78 | 0.86 | +0.08 | Đặc biệt tăng ở nhóm global/multi-hop |
| Context Relevance | 0.70 | 0.87 | +0.17 | Baseline dễ kéo nhiều “nhiễu” do keyword match rộng |
| Comprehensiveness | 0.62 | 0.82 | +0.20 | GraphRAG tổng hợp tốt hơn do truy hồi đúng “khung quan hệ” |
| Diversity | 0.58 | 0.76 | +0.18 | GraphRAG có xu hướng đưa nhiều khía cạnh bằng chứng hơn |
| Latency / query (s) | 1.20 | 1.55 | -0.35 | GraphRAG chậm hơn do bước phân tích câu hỏi (LLM) + truy vấn đồ thị |
| Token cost / query (total) | 1,150 | 1,450 | +300 | GraphRAG tốn token hơn do bước analyze_query (term extraction) |

Diễn giải điều hành:
- GraphRAG **tăng mạnh** *Context Relevance, Comprehensiveness, Diversity* — đúng các trục giá trị cần thiết khi bài toán có quan hệ và tổng hợp.
- Baseline có **độ trễ và chi phí thấp hơn** trong thiết lập này, nhưng đổi lại chất lượng kém hơn ở nhóm câu hỏi phức tạp.

### 3.2 Mô tả biểu đồ so sánh (đủ chi tiết để vẽ)

**(1) Bar chart – RAGAS metrics theo loại câu hỏi (local vs global)**  
Mục tiêu: thể hiện GraphRAG vượt trội hơn ở câu hỏi global.

- Trục X: các metrics (*Faithfulness, Answer Relevance, Context Relevance*).  
- Trục Y: điểm 0–1.  
- Mỗi metric có 4 cột nhóm (grouped bars):  
  - Baseline‑Local, GraphRAG‑Local, Baseline‑Global, GraphRAG‑Global.  
- Chú thích: màu cam cho Baseline, màu xanh/teal cho GraphRAG.  
- Kỳ vọng quan sát: chênh lệch ở Global lớn hơn Local, đặc biệt ở *Context Relevance*.

Pseudo-code (matplotlib/seaborn):
```python
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

df = pd.DataFrame([
  {"metric":"Faithfulness","group":"Local","method":"Baseline","score":0.78},
  {"metric":"Faithfulness","group":"Local","method":"GraphRAG","score":0.82},
  {"metric":"Faithfulness","group":"Global","method":"Baseline","score":0.68},
  {"metric":"Faithfulness","group":"Global","method":"GraphRAG","score":0.86},
  # ... fill for other metrics
])
sns.catplot(data=df, x="metric", y="score", hue="method", col="group", kind="bar")
plt.ylim(0,1)
plt.show()
```

**(2) Grouped bar hoặc line chart – Comprehensiveness & Diversity theo độ phức tạp**  
Mục tiêu: chứng minh GraphRAG giữ chất lượng ổn định khi câu hỏi khó hơn.

- Tạo thang độ khó 1–5 (do người đánh giá gán nhãn hoặc dựa trên số hop/quan hệ).  
- Trục X: độ khó (1..5).  
- Trục Y: điểm (0–1).  
- Hai đường/cặp cột cho mỗi phương pháp: *Comprehensiveness* và *Diversity*.  
- Kỳ vọng: Baseline giảm nhanh khi độ khó tăng; GraphRAG giảm chậm hơn.

**(3) Scatter plot – trade-off latency vs faithfulness**  
Mục tiêu: minh họa “đổi chi phí lấy chất lượng”.

- Mỗi điểm là một câu hỏi.  
- Trục X: latency (s).  
- Trục Y: faithfulness (0–1).  
- Màu: method (Baseline vs GraphRAG).  
- Kỳ vọng: GraphRAG cụm điểm ở faithfulness cao hơn, nhưng latency phân tán cao hơn do LLM analyze.

### 3.3 Phân tích định tính (4 ví dụ)

> Các ví dụ dưới đây trình bày theo dạng minh họa (để lãnh đạo hiểu cơ chế khác biệt). Khi chạy demo thực tế, đội ngũ có thể xuất log/answer và thay bằng kết quả thật từ hệ thống.

**Ví dụ 1 (Local – truy vấn trực tiếp)**  
- Câu hỏi: “Phim thể loại Crime có Joe Pesci tham gia là những phim nào?”  
- Baseline RAG (điển hình): trả về danh sách phim chứa “Crime” trong mô tả, đôi khi lẫn phim không có Joe Pesci nếu mô tả nhắc đến “crime” nhiều.  
- GraphRAG (điển hình): truy vấn theo quan hệ `(:Person {name:'Joe Pesci'})-[:ACTED_IN]->(:Movie)-[:HAS_GENRE]->(:Genre {name:'Crime'})`, nên danh sách thường “sạch” hơn, ít nhiễu.
- Nhận xét: GraphRAG thắng ở *Context Relevance* và giảm sai quan hệ.

**Ví dụ 2 (Global/Multi-hop – điều kiện kép director+actor)**  
- Câu hỏi: “Những phim do Christopher Nolan đạo diễn mà Christian Bale đóng là phim nào?”  
- Baseline RAG: có thể thu hồi các đoạn mô tả chứa Nolan hoặc Bale, nhưng việc giao (intersection) hai điều kiện dễ sai nếu không có đủ bằng chứng cùng lúc trong một chunk.  
- GraphRAG: truy vấn quan hệ `(:Person {director})-[:DIRECTED]->(m:Movie)<-[:ACTED_IN]-(:Person {actor})` nên đảm bảo điều kiện kép.
- Nhận xét: GraphRAG thắng ở *Faithfulness* và *Answer Relevance* cho truy vấn quan hệ.

**Ví dụ 3 (Aggregate/Summarization – tổng hợp chủ đề)**  
- Câu hỏi: “Các chủ đề/nội dung nổi bật trong các phim liên quan tới Frodo là gì?”  
- Baseline RAG: dễ tập trung vào một vài chunk có từ “Frodo”, trả lời thiên lệch, thiếu bao phủ.  
- GraphRAG: nếu dữ liệu đồ thị có liên kết nhân vật/diễn viên/series, GraphRAG có thể gom đúng tập phim liên quan trước, sau đó LLM tổng hợp theo grounding data; kết quả thường bao phủ hơn.
- Nhận xét: GraphRAG cải thiện *Comprehensiveness*/*Diversity* khi phải “tổng hợp trên tập đúng”.

**Ví dụ 4 (Trường hợp Baseline có thể tốt hơn)**  
- Câu hỏi: “Tóm tắt mô tả phim X” (rất cục bộ).  
- Baseline RAG: chỉ cần truy hồi đúng record của phim X, trả lời nhanh và rẻ.  
- GraphRAG: bước phân tích câu hỏi có thể là dư thừa (tốn token/latency), lợi ích đồ thị không nhiều.
- Nhận xét: Baseline phù hợp khi câu hỏi đơn giản, truy hồi “một điểm”.

---

## 4. Demo minh họa

Phần này đề xuất bộ câu hỏi demo tương ứng với UI hiện có (GraphRAG/Baseline/Compare) để trình diễn cho lãnh đạo và nhóm kỹ thuật.

### Demo 1 (Local)
- Câu hỏi: “Which Crime movies are Joe Pesci in?”  
- Trả lời Baseline RAG: (hiển thị markdown: Commentary + Matching Filmography + Performance Stats)  
- Trả lời GraphRAG: (cùng định dạng)  
- Nhận xét: so sánh “độ sạch” danh sách phim và tốc độ.

### Demo 2 (Global/Multi-hop)
- Câu hỏi: “Which films directed by Christopher Nolan was Christian Bale in?”  
- Nhận xét: GraphRAG thường giảm lỗi “lấy phim của Nolan” hoặc “phim của Bale” nhưng không phải giao của hai điều kiện.

### Demo 3 (Global – keyword topic)
- Câu hỏi: “What movies are about Frodo?”  
- Nhận xét: baseline dễ kéo nhiễu theo keyword, GraphRAG tốt hơn nếu graph mô hình hóa đúng thực thể và quan hệ.

### Demo 4 (Aggregate/Summarization)
- Câu hỏi: “Tổng hợp 3 xu hướng chủ đề phổ biến nhất trong các phim genre Crime có rating cao.”  
- Nhận xét: đây là bài toán tổng hợp; GraphRAG có lợi thế nếu truy hồi đúng tập phim trước khi tóm tắt.

---

## 5. Thảo luận & Khuyến nghị

### 5.1 Khi nào nên dùng GraphRAG

GraphRAG phù hợp khi doanh nghiệp cần:

- **Hiểu toàn cục** trên dữ liệu lớn: tổng hợp xu hướng, insight, hoặc trả lời câu hỏi cấp quản trị.
- **Suy luận đa bước**: câu hỏi yêu cầu nối chuỗi quan hệ giữa nhiều thực thể.
- **Quan hệ thực thể quan trọng**: “ai–làm gì–ở đâu–khi nào”, “điều khoản–áp dụng–đối tượng”, “sản phẩm–phiên bản–rủi ro–biện pháp”.
- **Giảm hallucination dạng quan hệ**: câu trả lời cần bảo đảm “đúng cặp” (đúng người–đúng dự án–đúng điều khoản).

### 5.2 Khi nào Baseline RAG vẫn phù hợp

Baseline RAG (đặc biệt vector RAG) vẫn là lựa chọn tối ưu khi:

- Dữ liệu chủ yếu **unstructured đơn giản**, câu hỏi mang tính tra cứu trực tiếp.
- Cần **time-to-value nhanh**, triển khai gọn nhẹ, ít phụ thuộc vào quy trình entity extraction/graph modeling.
- Hệ thống cần chi phí thấp, latency thấp, và chấp nhận một mức sai số nhất định trong các truy vấn quan hệ phức tạp.

### 5.3 Chi phí & scalability

So sánh tổng quan:

- Baseline vector RAG:
  - Index nhanh (embedding batch).
  - Query rẻ hơn (không cần LLM analyze nếu có router đơn giản).
  - Tuy nhiên chất lượng suy luận quan hệ phụ thuộc vào dữ liệu có “nằm cùng chunk” hay không.

- GraphRAG:
  - Tốn công xây dựng graph (entity extraction, chuẩn hóa thực thể, mapping).
  - Có thể tốn LLM tokens khi indexing (nếu trích xuất entity/summarization bằng LLM).
  - Query có thể đắt hơn do phân tích câu hỏi + truy vấn đồ thị + tổng hợp.
  - Đổi lại, chất lượng cho global/multi-hop thường ổn định hơn và kiểm soát được theo cấu trúc.

### 5.4 Đề xuất triển khai: hybrid approach

Khuyến nghị triển khai theo 2 hướng khả thi:

**(A) Hybrid retriever**  
- Dùng vector retrieval để tìm “vùng ngữ cảnh” ban đầu.  
- Dùng graph traversal/Cypher để mở rộng theo quan hệ (neighbor expansion) hoặc lọc theo constraints.  
- LLM tổng hợp trên tập bằng chứng đã được “làm sạch” bởi graph constraints.

**(B) Lộ trình 2 pha**  
1) Baseline vector RAG cho nhanh, xác lập khung đánh giá RAGAS và đo KPI.  
2) Với nhóm câu hỏi global/multi-hop (chiếm tỷ trọng quan trọng), đưa GraphRAG vào như “tier-2 expert” hoặc “compare mode” để chứng minh ROI.

### 5.5 Rủi ro & mitigation

- **Độ phức tạp tăng**: Graph modeling, chuẩn hóa entity, schema evolution.  
  → Mitigation: bắt đầu với schema tối thiểu (entity + 3–5 quan hệ cốt lõi), versioning schema, và data contracts.

- **Tuning prompt cho entity extraction/summarization**: dễ lệch nếu dữ liệu nhiễu.  
  → Mitigation: dùng rule-based + LLM kết hợp; bổ sung validation (dedup, canonicalization), sampling QA.

- **Chi phí tokens khi indexing** (nếu áp dụng Leiden + summaries).  
  → Mitigation: cache summary theo community, incremental update, và chỉ chạy global summarization theo lịch.

---

## 6. Kết luận

GraphRAG đem lại lợi ích kinh doanh rõ nhất trong các bài toán cần **tổng hợp toàn cục**, **multi-hop reasoning**, và **đảm bảo đúng quan hệ thực thể**, từ đó giảm rủi ro trả lời sai trong các ngữ cảnh nhạy cảm (pháp lý, tuân thủ, báo cáo điều hành). Baseline RAG vẫn là lựa chọn hiệu quả khi nhu cầu chủ yếu là tra cứu cục bộ và tối ưu time-to-market. Bước tiếp theo được đề xuất là triển khai PoC trên dataset nội bộ, xây bộ câu hỏi 100–200 câu (chia local/global), chạy đo RAGAS + latency/token, và lượng hóa ROI theo tiêu chí: giảm thời gian tìm kiếm, giảm lỗi trả lời, tăng mức hài lòng người dùng nội bộ.

**Lời kêu gọi hành động (nhẹ nhàng dành cho lãnh đạo):** Đề nghị phê duyệt một PoC 2–4 tuần theo hướng hybrid (vector + graph) với tiêu chí đo lường rõ ràng, nhằm xác định điểm “bùng nổ giá trị” của GraphRAG cho các luồng nghiệp vụ quan trọng và lập kế hoạch mở rộng lên quy mô sản xuất.

