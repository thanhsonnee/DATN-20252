Tổng quan dự án
Dự án này xây dựng một solver PDPTW (Pickup & Delivery with Time Windows) và một ứng dụng web quản trị để:

Tối ưu tuyến giao nhận cho đội xe (giảm số xe, giảm tổng quãng đường/thời gian).
Hỗ trợ Logistic Manager điều phối trên nhiều bộ dữ liệu chuẩn (Sartori, Li & Lim, Ropke–Cordeau) và dữ liệu thực (từ đơn hàng User).
Chuẩn bị nền tảng để mở rộng thành hệ thống vận hành thực tế (driver app, GPS, v.v.).
Core solver hiện tại được viết bằng Python, dùng ALNS + Local Search, internal model thống nhất cho cả 3 dataset.

Vai trò chính
User (người yêu cầu giao hàng)

Tạo đơn giao nhận từ A → B (địa chỉ, khối lượng, khung giờ mong muốn).
Theo dõi trạng thái đơn (chờ xử lý / đã gán tuyến / đang giao / hoàn tất / huỷ).
Logistic Manager (người điều phối)

Quản lý đơn hàng, đội xe, cấu hình solver.
Chạy tối ưu / tái tối ưu theo ca/ngày, xem và duyệt tuyến trên bản đồ.
Xuất báo cáo hiệu quả (số xe, quãng đường, độ trễ).
Admin hệ thống

Quản lý người dùng và quyền (User / Logistic Manager).
Cấu hình tích hợp (CSDL, Mapbox, tham số mặc định solver).
Theo dõi log chạy solver, tình trạng hệ thống.
Use case chính (mức cao)
UC1 – User tạo đơn giao hàng

Nhập điểm lấy (pickup), điểm giao (delivery), thời gian mong muốn, khối lượng, ghi chú.
Hệ thống lưu đơn vào database, gán trạng thái “Pending”.
UC2 – Logistic Manager duyệt và chọn đơn cho bài toán tối ưu

Lọc đơn theo ngày/ca/khu vực.
Chọn tập đơn muốn tối ưu trong một lần chạy solver (bài toán PDPTW cụ thể).
UC3 – Chạy tối ưu tuyến (construction + ALNS + LS)

Logistic Manager cấu hình:
Dataset nguồn (Sartori/Li&Lim/Ropke hoặc đơn từ DB).
Phương pháp xây nghiệm ban đầu (greedy, regret, best).
Time limit cho ALNS, seed.
Backend gọi solver:
Parser → internal Instance.
Construction → initial Solution.
ALNS + Local Search (3 stage) → best Solution.
UC4 – Logistic Manager xem và duyệt tuyến

Xem bảng tóm tắt: số xe, tổng cost, KPI (độ trễ, vi phạm TW…).
Xem chi tiết từng route trên bản đồ (marker + polyline).
Có thể khoá một số tuyến / chỉnh sửa tay (phiên bản nâng cao).
UC5 – Phát hành tuyến cho vận hành

Gắn tuyến đã duyệt cho từng xe/ca.
(Trong scope hiện tại) export file tuyến hoặc hiển thị danh sách stop theo xe.
(Tương lai) gửi xuống driver app / hệ thống khác.
UC6 – Theo dõi & tái tối ưu (re-optimization)

Khi có đơn mới / huỷ đơn / xe hỏng:
Logistic Manager cập nhật trạng thái đơn/xe.
Chọn lại tập đơn và chạy tái tối ưu (UC3) cho phần còn lại của ca.
UC7 – Quản trị hệ thống (Admin)

Tạo/sửa/xoá tài khoản User, Logistic Manager.
Cấu hình tham số mặc định solver (time limit, seed mặc định, bật/tắt các module).
Xem lịch sử các lần chạy solver (ai chạy, instance nào, kết quả bao nhiêu xe/cost).
Phân rã use case (chi tiết hơn cho web + solver)
UC1.1 – Tạo đơn đơn lẻ
Form web: nhập pickup/delivery, toạ độ hoặc địa chỉ (sẽ geocode), time window, demand.

UC1.2 – Import nhiều đơn từ file (phase sau)
Logistic Manager upload CSV (xuất từ hệ thống khác) → map cột → tạo nhiều request trong DB.

UC2.1 – Lọc & gán trạng thái đơn

Lọc theo ngày tạo, khu vực, trạng thái.
Đánh dấu đơn là “sẵn sàng tối ưu” (included in next run).
UC3.1 – Chọn dataset chuẩn để benchmark

Chọn file Sartori/Li&Lim/Ropke có sẵn → chạy solver để so sánh với best known.
UC3.2 – Chạy solver trên đơn thực trong DB (sau này)

Backend build Instance từ orders trong DB (depot + request).
Dùng chung pipeline construction+ALNS.
UC4.1 – Xem tuyến dạng bảng

Bảng các tuyến: mỗi dòng = xe, số stop, tổng thời gian/quãng đường.
Bảng stop theo tuyến.
UC4.2 – Xem tuyến trên bản đồ

Vẽ tuyến theo thứ tự stop, mỗi tuyến một màu, highlight khi chọn.
UC5.1 – Export tuyến

Export file solution theo format Sartori/Li&Lim/Ropke hoặc CSV nội bộ.
UC6.1 – Theo dõi trạng thái đơn/xe (read-only)

Status đơn: pending / assigned / in-progress / done / cancelled.
(Sau này) tích hợp GPS để xem vị trí xe.
UC7.1 – Quản lý cấu hình solver

Set max time-limit cho từng loại instance (n100, n1000…).
Bật/tắt các module cao cấp (adaptive penalty, set partitioning, F&O) khi sẵn sàng.
Các module chức năng dự định
Module Solver Core (solver/)

models.py: internal model (Node, Request, Route, Solution, Instance).
parsers/: Sartori, Li & Lim, Ropke–Cordeau → Instance.
constraints.py: kiểm tra feasibility (TW, capacity, precedence).
construction.py: xây nghiệm ban đầu (greedy, regret-k, best).
alns/:
runner.py: vòng lặp ALNS 3 stage, điều phối destroy/repair/LS/acceptance.
operators_destroy.py: random, shaw, worst, route, cluster.
operators_repair.py: greedy + regret-k + ejection nhẹ.
local_search.py: LS theo request, relocate (và sau này swap/Or-opt/2-opt*).
(tương lai) penalty.py, route_pool, exact layer.
io/: writer Sartori (hiện có), writer Li&Lim/Ropke (dự định).
config.py: tham số mặc định (time-limit, destroy fraction, SA, LS…).
Module CLI / Batch

run.py: chạy nhanh solver trên instance (Sartori), time-limit, method, seed.
solver/main.py: entry point tổng quát hơn theo --dataset-type.
Module Web Backend (dự định)

API auth & roles (User / Logistic Manager / Admin).
API quản lý orders (CRUD + query).
API chạy solver job (enqueue, status, kết quả).
API trả về tuyến, KPI, file export.
Module Web Frontend (dự định)

UI User: tạo đơn, xem trạng thái đơn.
UI Logistic Manager:
Dashboard đơn / đội xe.
Form cấu hình run solver.
Màn hình xem tuyến bảng + bản đồ.
UI Admin: quản lý người dùng, xem log, chỉnh cấu hình.
Trạng thái hiện tại của dự án
Solver core:

Đã có parser cho Sartori / Li&Lim / Ropke → internal Instance.
Đã có construction (greedy, regret-k).
Đã có ALNS 3 stage với nhiều destroy/repair + LS request-level.
Đã có CLI run.py cho Sartori, có thể chạy trên subinstance nhỏ (11/21 nodes) và instance thật (n100/n1000).
Web & DB:

Chưa triển khai, mới ở mức thiết kế use case/module như trên.

# PDPTW Solver (đang phát triển)

Dự án này bao gồm:
- **Datasets** trong `instances/` (Sartori, Li & Lim, Ropke–Cordeau)
- **Các nghiệm tham chiếu (best known / candidate)** trong `solutions/`
- **Validator** trong `validator/`
- **Visualizer** trong `visualizer/`
- Phần **solver** tự code trong `solver/` và script chạy nhanh `run.py`

Mục tiêu là xây một solver phục vụ luận văn cho bài toán **PDPTW** (Pickup & Delivery với Time Windows) theo thứ tự ưu tiên:
1) **Giảm số xe** (≈ số route)  
2) Nếu cùng số xe, **giảm tổng cost** (tổng thời gian / quãng đường)

---

## Cấu trúc dự án (phần solver)

```
solver/
  models.py                 # internal model (Node/Request/Route/Solution/Instance)
  parsers/
    sartori.py              # Sartori format (NODES + EDGES)
    lilim.py                # Li & Lim format (coordinates, Euclidean travel time)
    ropke_cordeau.py        # Ropke–Cordeau format (EXACT_2D, Euclidean travel time)
    __init__.py             # load_instance(...)
  constraints.py            # check feasibility (TW, capacity, precedence)
  construction.py           # tạo nghiệm ban đầu (greedy, regret-k)
  alns/
    state.py                # state current/best (so sánh ưu tiên số route)
    operators_destroy.py    # destroy (random, shaw, worst, route/cluster)
    operators_repair.py     # repair (greedy reinsertion)
    acceptance.py           # acceptance (simulated annealing)
    runner.py               # vòng lặp ALNS theo time limit + stages
  io/
    writer_sartori.py       # write solution format for Sartori validator
config.py                   # tham số mặc định (time limit, destroy size, SA)

run.py                      # cách chạy ngắn nhất cho Sartori instances
```

---

## Dataset và cách hiểu travel time

### Sartori (`instances/sartori-dataset/`)
- Travel time có sẵn trong file tại trường `EDGES` (số nguyên, đơn vị phút).
- Tính bởi **OSRM** theo mạng đường thực tế → có thể **bất đối xứng** (`t(i→j) != t(j→i)`).

### Li & Lim (`instances/lilim-dataset/`)
- File cho tọa độ; solver hiện tại tính travel time bằng **khoảng cách Euclid** giữa (x,y).
- Dòng đầu có: `<vehicles> <capacity> <speed>` (thường speed = 1).
- Nếu speed = 1 thì **travel time = distance** (cùng giá trị số).

### Ropke–Cordeau (`instances/ropke-cordeau-dataset/`)
- `EDGE_WEIGHT_TYPE : EXACT_2D` → travel time = **khoảng cách Euclid** giữa tọa độ.

---

## Internal model (chuẩn hoá chung)

Tất cả parser đều convert về cùng một cấu trúc nội bộ:
- **Node**: vị trí + demand + time window + service duration
- **Request**: 1 pickup node + 1 delivery node (cặp)
- **Route**: chuỗi node khách (`route.stops`) **không chứa depot**
- **Solution**: danh sách route + tổng cost
- **Instance**: nodes, requests, capacity, horizon, travel-time matrix, depot id

Với 3 dataset đang dùng, cấu trúc chuẩn thường là:
- 1 depot  
- Mỗi request = 1 pickup + 1 delivery  
- Thường có: `num_requests = (num_nodes - 1) / 2`

---

## Flow thuật toán (hiện tại)

(0) Preprocess & quick feasibility
parsers/*.py + preprocess.py:
đọc file → Instance
build requests, map pickup–delivery
tính slack TW, các precomputed bound (nếu cần)
dùng constraints.quick_feasibility(instance) để loại instance quá chặt.
Giải thích: Loại instance quá chặt = loại những instance mà vi phạm điều kiện cần để có nghiệm, nên chắc chắn vô nghiệm.
(1) Initial feasible solution – construction.py
builder theo request:
greedy insertion
regret‑k insertion
optional: nearest‑neighbor / sweep theo request. (chưa có trong code, chưa triển khai, ưu tiên chạy nhanh đến bước cuối đã)
luôn trả về Solution feasible (precedence, capacity, TW).
(2) Main loop (ALNS) – alns/runner.py
quản lý 3 stage theo time limit:
Stage 1: destroy to 15–30% request, acceptance thoáng.
Stage 2: 10–25%, LS mạnh hơn.
Stage 3: 5–15%, LS mạnh, bật SP/F&O.
(3) Destroy operators – alns/operators_destroy.py
random, shaw/related, worst, (route/cluster optional).
làm việc trên level request.
(4) Repair operators – alns/operators_repair.py
regret‑k insertion (pickup → delivery)
greedy + nhẹ nhàng eject 1–2 request nếu kẹt.
(5) Local search + mini‑repair – alns/local_search.py
relocate / swap request, Or-opt block, 2‑opt* (nếu định nghĩa rõ).
mini‑repair bản đầu (theo bạn yêu cầu):
chỉ:
sửa precedence (nếu operator lỡ phá thứ tự),
sửa time feasibility bằng propagation,
không làm split route, trick phức tạp.
(6) Adaptive penalty – alns/penalty.py
objective:
cost + λ_TW * viol_TW + λ_C * viol_capacity
precedence hard (không cho violate, hoặc bị loại ngay).
update λ theo tỉ lệ feasible gần đây (cửa sổ iteration).
(7) Exact layer (SP) – exact/set_partitioning.py
RoutePool lưu route feasible “tốt”.
Định kỳ xây mô hình SP:
biến = chọn / không chọn route,
ràng buộc: mỗi request được phục vụ đúng 1 lần,
solve bằng MILP solver (vd pulp, ortools) – sau này ta chọn cụ thể.
Solution SP → incumbent mới → tiếp tục ALNS/LS.
(8) Optional Fix‑and‑Optimize – exact/fix_and_optimize.py
chỉ dùng Stage 3, bonus.
(9) Output – io/writer_*.py
ghi solution đúng format Sartori / Li&Lim / Ropke‑Cordeau,
main.py sẽ:
nhận --instance, --dataset-type, --time-limit, --output,
gọi parser → solver → writer.

---

## Cách chạy (Sartori dataset)

### Chạy nhanh (construction + ALNS)
Tại thư mục root dự án:

```powershell
python run.py bar-n1000-3
```

Thêm time limit cho ALNS (giây):

```powershell
python run.py bar-n1000-3 --time-limit 60
```

Chọn method cho construction:
- `--method greedy` (khuyên dùng với instance lớn)
- `--method regret` (có thể rất chậm)

Example:

```powershell
python run.py bar-n1000-3 --method greedy --time-limit 60 --seed 0
```

File output được ghi vào:
`solutions/my_solver/<instance>.<vehicles>_<cost>.txt`

---

## Validate nghiệm (Sartori validator)

From workspace root:

```powershell
cd validator
python validator.py -s ..\solutions\my_solver\bar-n1000-3.<vehicles>_<cost>.txt -i ..\instances\sartori-dataset\n1000\n1000\bar-n1000-3.txt
```

---

## Ghi chú / hạn chế hiện tại

- `run.py` hiện nhắm tới **Sartori** để ghi file và validate (`writer_sartori.py`).
  Parser cho Li & Lim và Ropke–Cordeau đã có, nhưng writer cho 2 format đó chưa thêm.
- Regret-k insertion rất tốn thời gian với instance lớn; nên dùng greedy + ALNS time limit.

---

## Các bước tiếp theo (gợi ý)

1) Thêm regret-k repair + ejection nhẹ trong `operators_repair.py`
2) Thêm `alns/local_search.py` (relocate/swap/Or-opt + mini-repair)
3) Thêm writer cho Li & Lim và Ropke–Cordeau
4) Thêm route pool + set partitioning (MILP) cho “exact layer” trong luận văn

