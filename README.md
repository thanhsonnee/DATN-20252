Đề tài: Phát triển công cụ hỗ trợ thực thi và đánh giá các bộ giải cho bài toán định tuyến đa phương tiện trên nhiều bộ dữ liệu khác nhau

Repo hiện bao gồm:

- Solver chứa các thuật toán
- Web backend FastAPI để quản lý instance, job, solution và users.
- Frontend React/Vite để thao tác, chạy bộ giải (solver) và xem kết quả.
- Bộ dữ liệu benchmark, best known solution tham chiếu cho 1 số bộ dữ liệu, validator và visualizer.

## Cấu Trúc Dự Án

```text
.
├── run.py                  # CLI chạy solver nhanh từ root
├── solver/                 # Solver core, parser, ALNS, exact layer, plugins
├── backend/                # FastAPI backend + SQLAlchemy + solver service
├── frontend/               # React 18 + TypeScript + Vite + Tailwind CSS
├── instances/              # Benchmark instances và tài liệu dataset
├── solutions/              # Best known/candidate solutions và output mẫu
├── validator/              # Công cụ kiểm tra nghiệm
├── visualizer/             # Công cụ visualize instance/solution
├── tools/                  # Script hỗ trợ xử lý dữ liệu
├── database_design.sql     # Thiết kế CSDL tham khảo
├── README_SOLVER.md        # Ghi chú chi tiết về solver
└── README_WEB.md           # Ghi chú chi tiết về web app
```

## Solver Core

Thư mục `solver/` là phần giải thuật chính:

- `models.py`: model nội bộ `Node`, `Request`, `Route`, `Solution`, `Instance`.
- `parsers/`: parser cho Sartori, Li & Lim, Ropke-Cordeau và two-echelon variants.
- `construction.py`: tạo nghiệm ban đầu bằng `greedy`, `regret`, `sweep`, `best`.
- `constraints.py`: kiểm tra feasibility.
- `preprocess.py`: tiền xử lý và quick feasibility check.
- `alns/`: ALNS runner, destroy/repair operators, acceptance, local search, penalty.
- `exact/`: set partitioning và fix-and-optimize.
- `io/`: writer xuất solution theo từng dataset format.
- `plugins/`: tích hợp các folder thuật toán khác nhau đã cài đặt được: 2E-VRP, 2E-VRPTWSPD, 2-echelon synchronization, math-pdptw.

## Web Application

Backend nằm trong `backend/`, dùng:

- FastAPI
- SQLAlchemy
- JWT auth
- Pydantic
- SQLite/PostgreSQL tùy cấu hình môi trường

Frontend nằm trong `frontend/`, dùng:

- React 18
- TypeScript
- Vite
- Tailwind CSS
- React Leaflet/OpenStreetMap
- Recharts

Sản phẩm kỳ vọng
Website hỗ trợ người dùng thực thi và đánh giá thuật toán tối ưu

## Datasets

Các bộ dữ liệu chính nằm trong `instances/`:

- `instances/sartori-dataset/`: PDPTW Sartori, travel time lấy từ OSRM theo mạng đường thực tế, có thể bất đối xứng.
- `instances/lilim-dataset/`: Li & Lim PDPTW, travel time tính từ tọa độ Euclid.
- `instances/ropke-cordeau-dataset/`: Ropke-Cordeau PDPTW, `EXACT_2D`.
- `instances/2E-EVRP-Instances-2/` và `instances/2e-vrp-pdd-main/`: dữ liệu cho các biến thể two-echelon/electric VRP.

Một số dataset lớn không nên commit nếu chỉ là bản tải về tạm hoặc metadata sinh tự động. `.gitignore` đã chặn các file `*.meta.json`, `*.analysis.json` và các thư mục output/cache.

## Cài Đặt

Yêu cầu khuyến nghị:

- Python 3.11 hoặc 3.12.
- Node.js 18+.
- PostgreSQL nếu muốn chạy backend với DB ngoài; SQLite có thể dùng cho local tùy `.env`.

Không commit các file môi trường hoặc dữ liệu local:

- `.env`
- `*.db`
- `frontend/node_modules/`
- `__pycache__/`
- `solutions/my_solver/`

## Chạy Solver Từ CLI

Từ root dự án:

```powershell
python run.py bar-n1000-3
```

Chạy với tham số rõ hơn:

```powershell
python run.py bar-n1000-3 --method greedy --time-limit 60 --seed 0
```

Chạy bằng đường dẫn file:

```powershell
python run.py instances\sartori-dataset\n100\n100\bar-n100-1.txt --dataset-type sartori --time-limit 30
```

Các dataset type đang hỗ trợ:

```text
sartori
lilim
ropke_cordeau
```

Các construction method:

```text
greedy
regret
sweep
best
```

Output mặc định:

```text
solutions/my_solver/<instance>.<routes>_<cost>.txt
```

## Validate Solution

Ví dụ validate nghiệm Sartori:

```powershell
cd validator
python validator.py -s ..\solutions\my_solver\bar-n1000-3.<routes>_<cost>.txt -i ..\instances\sartori-dataset\n1000\n1000\bar-n1000-3.txt
```

Thay `<routes>_<cost>` bằng tên file thực tế solver sinh ra.

## Chạy Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python run.py
```

Backend mặc định:

```text
http://localhost:8000
```

API docs:

```text
http://localhost:8000/docs
```

Seed dữ liệu demo:

```powershell
python app\db\seed.py
```

Demo accounts:

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

Frontend mặc định:

```text
http://localhost:5173
```

Build production:

```powershell
npm run build
```

Các role người dùng: 
- role 1: Người chạy thuật toán
- role 2: Người đề xuất dataset mới
- role 3: Người đề xuất các độ đo mới cho thuật toán
- role 4: Admin

## Git

Nên commit:

- Source code trong `solver/`, `backend/app/`, `frontend/src/`.
- File cấu hình cần thiết như `requirements.txt`, `package.json`, `package-lock.json`, `vite.config.ts`, `tailwind.config.js`.
- Tài liệu: `README.md`, `README_SOLVER.md`, `README_WEB.md`, README dataset.
- Dataset benchmark nhỏ/cần thiết cho tái lập kết quả.
- Nghiệm tham chiếu trong `solutions/files-*` và `solutions/bks.dat`.

Không nên commit:

- `.env`, database local, secret key.
- `node_modules/`, `__pycache__/`, `.pyc`.
- `solutions/my_solver/` vì đây là output chạy thử.
- `*.meta.json`, `*.analysis.json` vì đây là metadata sinh tự động.
- Output plugin, binary build, file log.

## Tài Liệu Liên Quan

- `README_SOLVER.md`: mô tả sâu hơn về thuật toán ALNS và hướng phát triển solver.
- `README_WEB.md`: mô tả web, cách chạy và API.
- `instances/README.md`: thông tin dataset Sartori gốc và cách tải dữ liệu.
- `instances/sartori-dataset/README_sartori.md`: mô tả bộ Sartori.
