from __future__ import annotations

import random
from pathlib import Path
from typing import Dict, List, Tuple


def load_sartori_instance(path: str) -> tuple[list[str], Dict[int, list[str]], list[list[int]], list[tuple[int, int]]]:
    """
    Đọc file Sartori (ví dụ bar-n100-1.txt) và trả về:
    - header_lines (list[str])
    - nodes: dict[node_id] -> list[str] (các field đã split)
    - full_tt: ma trận travel-time (int) size N×N
    - requests: list[(pickup_id, delivery_id)]
    """
    p = Path(path)
    lines = [l.rstrip("\n") for l in p.read_text(encoding="utf-8").splitlines()]

    idx_nodes = lines.index("NODES")
    idx_edges = lines.index("EDGES")

    header = lines[:idx_nodes]
    node_lines = lines[idx_nodes + 1:idx_edges]
    edge_lines = lines[idx_edges + 1:]

    # Parse nodes
    nodes: Dict[int, list[str]] = {}
    for line in node_lines:
        if not line.strip():
            continue
        parts = line.split()
        nid = int(parts[0])
        nodes[nid] = parts

    # Parse edges -> full_tt
    full_tt: List[List[int]] = []
    for line in edge_lines:
        s = line.strip()
        if not s:
            continue
        # Một số file Sartori kết thúc bằng marker 'EOF' hoặc text khác sau EDGES.
        # Khi gặp dòng không phải toàn số, ta dừng ở đây.
        parts = s.split()
        try:
            row = list(map(int, parts))
        except ValueError:
            break
        full_tt.append(row)

    # Build request list: lấy các node có demand > 0 và cột cuối (delivery-id) != 0
    requests: List[tuple[int, int]] = []
    for nid, parts in nodes.items():
        demand = int(parts[3])
        delivery_id = int(parts[8])
        if nid == 0:
            continue
        if demand > 0 and delivery_id != 0:
            requests.append((nid, delivery_id))

    return header, nodes, full_tt, requests


def build_subinstance_lines(
    header: list[str],
    nodes: Dict[int, list[str]],
    full_tt: list[list[int]],
    chosen_requests: list[tuple[int, int]],
) -> list[str]:
    """
    Xây text-lines cho 1 instance con từ:
    - header gốc
    - nodes gốc
    - full_tt gốc
    - chosen_requests: list[(pickup_id, delivery_id)]
    """
    # Tập node giữ lại: depot (0) + tất cả pickup & delivery
    keep_ids: List[int] = [0]
    for pu, de in chosen_requests:
        if pu not in keep_ids:
            keep_ids.append(pu)
        if de not in keep_ids:
            keep_ids.append(de)
    keep_ids = sorted(keep_ids)

    # Map id cũ -> id mới (0..M-1)
    old_to_new = {old: new for new, old in enumerate(keep_ids)}

    # Header mới: sửa SIZE:
    new_header: List[str] = []
    for line in header:
        if line.startswith("SIZE:"):
            new_header.append(f"SIZE: {len(keep_ids)}")
        else:
            new_header.append(line)

    # NODES mới
    new_node_lines: List[str] = []
    for old_id in keep_ids:
        parts = nodes[old_id][:]
        # id mới
        parts[0] = str(old_to_new[old_id])
        # update pickup / delivery (cột 7,8)
        pick = int(parts[7])
        drop = int(parts[8])
        if pick != 0:
            parts[7] = str(old_to_new[pick])
        if drop != 0:
            parts[8] = str(old_to_new[drop])
        new_node_lines.append(" ".join(parts))

    # EDGES mới (sub-ma trận)
    new_tt_lines: List[str] = []
    for oi in keep_ids:
        row_old = full_tt[oi]
        row_new = [row_old[oj] for oj in keep_ids]
        new_tt_lines.append(" ".join(str(x) for x in row_new))

    # Gộp tất cả thành list[str]
    out_lines: List[str] = []
    out_lines.extend(new_header)
    out_lines.append("NODES")
    out_lines.extend(new_node_lines)
    out_lines.append("EDGES")
    out_lines.extend(new_tt_lines)
    return out_lines


def generate_random_subinstances(
    src_path: str,
    out_dir: str,
    num_requests_per_sub: int = 5,
    num_samples: int = 3,
    seed: int = 0,
) -> None:
    """
    Gen nhiều instance con từ 1 file Sartori:
    - src_path: đường dẫn file gốc (vd 'instances/n100/n100/bar-n100-1.txt')
    - out_dir: thư mục output (vd 'instances/n100/n100/subinstances')
    - num_requests_per_sub: số request trong mỗi instance con (5 -> 1 depot + 10 node)
    - num_samples: số file muốn gen ra
    """
    header, nodes, full_tt, requests = load_sartori_instance(src_path)

    rng = random.Random(seed)
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    base_name = Path(src_path).stem  # 'bar-n100-1'

    if num_requests_per_sub > len(requests):
        raise ValueError("num_requests_per_sub lớn hơn số request sẵn có trong file gốc.")

    for i in range(num_samples):
        chosen = rng.sample(requests, num_requests_per_sub)
        lines = build_subinstance_lines(header, nodes, full_tt, chosen)
        out_name = f"{base_name}_sub_{num_requests_per_sub}req_{seed}_{i}.txt"
        out_path = out_root / out_name
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Wrote {out_path} (requests={chosen})")


if __name__ == "__main__":
    # Ví dụ dùng nhanh:
    # python tools/gen_small_sartori.py
    generate_random_subinstances(
        src_path="instances/n100/n100/bar-n100-3.txt",
        out_dir="instances/n100/n100/subinstances",
        num_requests_per_sub=10,  # 1 depot + 5 request = 11 nodes
        num_samples=3,
        seed=0,
    )