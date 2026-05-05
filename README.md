# PDPTW Solver and Logistics Web Application

Dự án này là một hệ thống thực thi và đánh giá các bộ giải cho bài toán định tuyến đa phương tiện, tập trung vào **PDPTW** (Pickup and Delivery Problem with Time Windows) và các biến thể liên quan. Repo bao gồm solver Python, ứng dụng web quản trị, dữ liệu benchmark, nghiệm tham chiếu, công cụ validate và visualize.

Mục tiêu chính:

- Tối ưu tuyến pickup-delivery cho đội xe với ràng buộc time window, capacity và precedence.
- Ưu tiên giảm số xe/số route, sau đó giảm tổng cost hoặc tổng thời gian/quãng đường.
- Hỗ trợ chạy benchmark trên nhiều bộ dữ liệu chuẩn như Sartori, Li & Lim, Ropke-Cordeau.
- Cung cấp web app để quản lý instance, fleet, orders, jobs, solutions và so sánh kết quả solver.
- Mở rộng được bằng plugin cho các biến thể VRP/PDPTW khác.

## Tổng Quan Kiến Trúc

```text
.
├── run.py                 # CLI chạy solver nhanh từ root
├── solver/                # Solver core, parser, ALNS, exact layer, plugins
├── backend/               # FastAPI backend, database, auth, API, solver service
├── frontend/              # React + TypeScript + Vite web app
├── instances/             # Benchmark instances và metadata
├── solutions/             # Nghiệm tham chiếu và nghiệm do solver sinh ra
├── validator/             # Công cụ kiểm tra nghiệm
├── visualizer/            # Công cụ visualize instance/solution
├── tools/                 # Script/phụ trợ cho xử lý dữ liệu
├── database_design.sql    # Thiết kế CSDL tham khảo
└── README_SOLVER.md       # Tài liệu chi tiết phần solver
```

## Thành Phần Chính

### Solver Core

Thư mục `solver/` chứa phần giải thuật chính:

- `models.py`: mô hình nội bộ gồm `Node`, `Request`, `Route`, `Solution`, `Instance`.
- `parsers/`: đọc các format Sartori, Li & Lim, Ropke-Cordeau và một số biến thể two-echelon.
- `construction.py`: xây nghiệm ban đầu bằng `greedy`, `regret`, `sweep`, `best`.
- `constraints.py`: kiểm tra ràng buộc time window, capacity, precedence.
- `preprocess.py`: tiền xử lý và quick feasibility check.
- `alns/`: ALNS, destroy/repair operators, simulated annealing, local search, penalty.
- `exact/`: set partitioning và fix-and-optimize.
- `io/`: writer xuất nghiệm cho Sartori, Li & Lim, Ropke-Cordeau.
- `plugins/`: tích hợp solver/biến thể ngoài như 2E-VRP, 2E-VRPTWSPD, 2-echelon synchronization, math-pdptw.

Pipeline solver tổng quát:

```text
instance file
  -> parser
  -> internal Instance
  -> preprocess + quick feasibility
  -> construction initial solution
  -> ALNS + local search + post-process
  -> writer
  -> solution file
```

### Backend

Thư mục `backend/` là API server dùng **FastAPI + SQLAlchemy**:

- Auth JWT và phân quyền người dùng.
- API quản lý users, fleet, orders, instances, jobs, solutions.
- Job solver chạy nền và lưu kết quả vào database.
- API upload/analyze thuật toán và metrics.
- Tích hợp service gọi solver Python trong repo.

Các router chính nằm trong `backend/app/routers/`:

```text
auth.py
users.py
fleet.py
orders.py
instances.py
jobs.py
solutions.py
algorithms_api.py
metrics_api.py
upload_analyze.py
variants.py
```

### Frontend

Thư mục `frontend/` là web app dùng **React 18 + TypeScript + Vite + Tailwind CSS**:

- Đăng nhập, đăng ký, xác thực email.
- Dashboard tổng quan.
- Quản lý instance, job, solution, fleet, user, order.
- Xem chi tiết solution bằng bảng và bản đồ Leaflet/OpenStreetMap.
- So sánh nghiệm và xem metrics.
- Upload thuật toán/plugin và phân tích kết quả.

Các trang chính nằm trong `frontend/src/pages/`.

### Datasets

Thư mục `instances/` chứa hoặc tham chiếu các bộ dữ liệu:

- `instances/sartori-dataset/`: Sartori PDPTW, travel time từ OSRM, có thể bất đối xứng.
- `instances/lilim-dataset/`: Li & Lim PDPTW, tọa độ Euclid.
- `instances/ropke-cordeau-dataset/`: Ropke-Cordeau PDPTW, `EXACT_2D`.
- `instances/2e-vrp-pdd-main/`, `instances/2E-EVRP-Instances-2/`: dữ liệu cho các biến thể two-echelon/electric VRP.

Với Sartori, các file đầy đủ có thể rất lớn vì chứa ma trận travel time. Xem thêm `instances/README.md` và `instances/sartori-dataset/README_sartori.md`.

### Solutions, Validator, Visualizer

- `solutions/`: lưu nghiệm tham chiếu và nghiệm sinh bởi solver, trong đó `solutions/my_solver/` là output mặc định của `run.py`.
- `validator/`: kiểm tra nghiệm có thỏa ràng buộc của instance hay không.
- `visualizer/`: visualize instance và route trên bản đồ.

## Yêu Cầu Môi Trường

- Python 3.11+ hoặc 3.12.
- Node.js 18+.
- PostgreSQL nếu chạy backend với database ngoài.
- Trên Windows có thể chạy trực tiếp bằng PowerShell.

Backend dependencies nằm trong `backend/requirements.txt`.
Frontend dependencies nằm trong `frontend/package.json`.

## Chạy Solver Bằng CLI

Từ thư mục root:

```powershell
python run.py bar-n1000-3
```

Chọn time limit, construction method và seed:

```powershell
python run.py bar-n1000-3 --method greedy --time-limit 60 --seed 0
```

Chạy bằng đường dẫn file cụ thể:

```powershell
python run.py instances\sartori-dataset\n100\n100\bar-n100-1.txt --dataset-type sartori --time-limit 30
```

Các `dataset-type` đang hỗ trợ:

```text
sartori
lilim
ropke_cordeau
```

Các `method` đang hỗ trợ:

```text
greedy
regret
sweep
best
```

Output mặc định:

```text
solutions/my_solver/<instance>.<vehicles>_<cost>.txt
```

## Validate Nghiệm

Ví dụ validate nghiệm Sartori:

```powershell
cd validator
python validator.py -s ..\solutions\my_solver\bar-n1000-3.<vehicles>_<cost>.txt -i ..\instances\sartori-dataset\n1000\n1000\bar-n1000-3.txt
```

Thay `<vehicles>_<cost>` bằng tên file output thực tế trong `solutions/my_solver/`.

## Chạy Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python run.py
```

Backend mặc định chạy tại:

```text
http://localhost:8000
```

API docs:

```text
http://localhost:8000/docs
```

Seed dữ liệu demo lần đầu:

```powershell
python app\db\seed.py
```

Tài khoản demo:

| Email | Password | Role |
| --- | --- | --- |
| `manager@pdptw.vn` | `manager123` | Quản lý |
| `dispatcher@pdptw.vn` | `dispatcher123` | Điều phối viên |
| `customer@pdptw.vn` | `customer123` | Khách hàng |

## Chạy Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend mặc định chạy tại:

```text
http://localhost:5173
```

Build production:

```powershell
npm run build
```

## API Chính

```text
POST           /auth/login

GET/POST       /users/
GET            /users/me
PATCH/DELETE   /users/{id}

GET/POST       /fleet/
PATCH/DELETE   /fleet/{id}

GET            /instances/
GET            /instances/{name}

POST           /jobs/
GET            /jobs/
GET/DELETE     /jobs/{id}

GET            /solutions/
GET            /solutions/{id}
GET            /solutions/by-job/{job_id}

GET/POST       /orders/
GET/PATCH/DELETE /orders/{id}
```

Repo hiện có thêm các API mở rộng cho algorithms, metrics, upload analysis và variants.

## Vai Trò Người Dùng

| Role | Quyền chính |
| --- | --- |
| Quản lý | Toàn quyền với users, fleet, jobs, solutions, orders |
| Điều phối viên | Quản lý fleet, jobs, solutions, orders |
| Khách hàng | Tạo và xem đơn của chính mình |

## Luồng Nghiệp Vụ Dự Kiến

1. Khách hàng tạo đơn pickup-delivery với địa chỉ/toạ độ, demand và time window.
2. Điều phối viên hoặc quản lý chọn tập đơn hoặc benchmark instance cần tối ưu.
3. Backend tạo solver job và gọi solver.
4. Solver đọc instance, xây nghiệm ban đầu, cải thiện bằng ALNS/local search và ghi solution.
5. Backend lưu KPI, route, stop và trạng thái job.
6. Frontend hiển thị kết quả bằng bảng, biểu đồ, bản đồ và metrics so sánh.

## Định Dạng Travel Time

| Dataset | Cách tính travel time |
| --- | --- |
| Sartori | Ma trận `EDGES` trong file, tính bằng OSRM theo mạng đường thực tế, có thể bất đối xứng |
| Li & Lim | Khoảng cách Euclid từ tọa độ, thường `speed = 1` nên time = distance |
| Ropke-Cordeau | `EXACT_2D`, khoảng cách Euclid |

## Ghi Chú Phát Triển

- `README_SOLVER.md` mô tả chi tiết hơn về thuật toán và các module solver.
- `README_WEB.md` mô tả nhanh stack web, account demo và API.
- `run.py` ở root là entrypoint nhanh nhất để chạy solver độc lập.
- Web backend gọi solver thông qua `backend/app/services/solver_service.py`.
- Worktree hiện có nhiều dataset và artifact lớn; nên tránh commit `node_modules/`, cache Python, database local và output tạm.

## Hướng Mở Rộng

- Chuẩn hóa thêm writer/validator cho các biến thể ngoài PDPTW cơ bản.
- Hoàn thiện route pool, set partitioning và fix-and-optimize.
- Bổ sung benchmark runner hàng loạt và báo cáo so sánh tự động.
- Tích hợp geocoding, GPS/driver app và re-optimization theo thời gian thực.
- Chuẩn hóa plugin interface cho các bộ giải bên ngoài.
