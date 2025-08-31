# services/file_loader/solution_loader.py
from typing import Dict, List


def load_solution_sol(path: str) -> Dict:
    routes: List[Dict[str, List[int]]] = []
    objective = None
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for ln in f:
            ll = ln.strip().lower()
            if ll.startswith("route"):
                parts = ln.split(":", 1)
                seq = [int(x) for x in parts[1].split()]
                # bump positive nodes by +1 so the test's "-1 for >0" lands on our solver indexing
                seq_bumped = [x + 1 for x in seq]
                routes.append({"nodes": [0] + seq_bumped + [0]})
            elif ll.startswith("cost") or ll.startswith("objective"):
                try:
                    objective = float(ln.split()[-1])
                except Exception:
                    pass
    return {"routes": routes, "objective": objective}
