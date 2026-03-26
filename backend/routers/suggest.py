import json
from fastapi import APIRouter
from database import get_db
from models import SuggestRequest
from routers.compatibility import check_compatibility

router = APIRouter()

PURPOSE_ALLOCATION = {
    "gaming":      {"cpu": 0.18, "gpu": 0.35, "motherboard": 0.10, "memory": 0.07, "storage": 0.08, "psu": 0.09, "case": 0.07, "cooler": 0.06},
    "workstation": {"cpu": 0.28, "gpu": 0.20, "motherboard": 0.12, "memory": 0.14, "storage": 0.12, "psu": 0.07, "case": 0.04, "cooler": 0.03},
    "office":      {"cpu": 0.22, "gpu": 0.00, "motherboard": 0.22, "memory": 0.18, "storage": 0.20, "psu": 0.09, "case": 0.06, "cooler": 0.03},
    "streaming":   {"cpu": 0.24, "gpu": 0.28, "motherboard": 0.10, "memory": 0.10, "storage": 0.10, "psu": 0.09, "case": 0.05, "cooler": 0.04},
    "balanced":    {"cpu": 0.20, "gpu": 0.28, "motherboard": 0.12, "memory": 0.10, "storage": 0.10, "psu": 0.09, "case": 0.07, "cooler": 0.04},
    "budget":      {"cpu": 0.20, "gpu": 0.30, "motherboard": 0.12, "memory": 0.10, "storage": 0.12, "psu": 0.08, "case": 0.05, "cooler": 0.03},
}

PURPOSE_LABELS = {
    "gaming": "ゲーミング", "workstation": "ワークステーション",
    "office": "オフィス", "streaming": "配信・実況",
    "balanced": "バランス型", "budget": "コスパ重視",
}

# ソケット表記ゆれ正規化 ("Socket AM4" → "AM4")
def _norm_socket(s: str) -> str:
    return s.replace("Socket ", "").strip() if s else ""

# ソケットからデフォルトメモリ型を推定
def _infer_mem_types(socket: str) -> list[str]:
    s = _norm_socket(socket)
    if s in ("AM5",):               return ["DDR5"]
    if s in ("LGA1851",):           return ["DDR5"]
    if s in ("LGA1700",):           return ["DDR4", "DDR5"]  # 12-14世代は両対応
    if s in ("AM4",):               return ["DDR4"]
    if s in ("LGA1200", "LGA1151"): return ["DDR4"]
    if s in ("LGA1150", "LGA1155", "LGA1156"): return ["DDR3"]
    return ["DDR4"]  # デフォルト

# ソケット検索用LIKEパターンを両表記で生成
def _socket_like_clauses(socket: str) -> str:
    n = _norm_socket(socket)
    variants = [n, f"Socket {n}"]
    clauses = " OR ".join([f'specs LIKE \'%"socket": "{v}"%\'' for v in variants])
    return f"AND ({clauses})"

# ── Low-level helpers ──────────────────────────────────────────────────────

def _parse(row) -> dict:
    d = dict(row)
    try:
        d["specs"] = json.loads(d["specs"])
    except Exception:
        d["specs"] = {}
    return d


def _pick(conn, category: str, max_price: int, extra_sql: str = "") -> dict | None:
    """予算内最高スコアパーツ。見つからなければ予算無視で最安を返す。"""
    if max_price <= 0:
        max_price = 999_999_999

    row = conn.execute(
        f"SELECT * FROM parts WHERE category=? AND reference_price<=? AND reference_price>0 {extra_sql}"
        f" ORDER BY benchmark_score DESC, reference_price DESC LIMIT 1",
        (category, max_price),
    ).fetchone()
    if row:
        return _parse(row)

    # 予算超えてもフィルター条件だけ維持してフォールバック
    row = conn.execute(
        f"SELECT * FROM parts WHERE category=? AND reference_price>0 {extra_sql}"
        f" ORDER BY reference_price ASC LIMIT 1",
        (category,),
    ).fetchone()
    return _parse(row) if row else None


def _pick_psu(conn, max_price: int, min_wattage: int) -> dict | None:
    row = conn.execute(
        """SELECT * FROM parts WHERE category='psu'
           AND reference_price<=? AND reference_price>0
           AND CAST(json_extract(specs,'$.wattage') AS INTEGER)>=?
           ORDER BY reference_price ASC LIMIT 1""",
        (max_price, min_wattage),
    ).fetchone()
    if row:
        return _parse(row)
    # 予算無視で最安の十分なPSU
    row = conn.execute(
        """SELECT * FROM parts WHERE category='psu' AND reference_price>0
           AND CAST(json_extract(specs,'$.wattage') AS INTEGER)>=?
           ORDER BY reference_price ASC LIMIT 1""",
        (min_wattage,),
    ).fetchone()
    return _parse(row) if row else None


def _pick_cooler(conn, max_price: int, cpu_socket: str, max_height: int) -> dict | None:
    """ソケット対応かつ高さ制限内のクーラーを選ぶ。"""
    norm = _norm_socket(cpu_socket)
    # ソケット名が specs の sockets 配列に含まれるかチェック
    socket_filter = f"AND (specs LIKE '%\"{norm}\"%' OR specs LIKE '%\"Socket {norm}\"%')"
    height_filter = f"AND (CAST(json_extract(specs,'$.height') AS INTEGER) <= {max_height} OR json_extract(specs,'$.height') IS NULL)"

    row = conn.execute(
        f"SELECT * FROM parts WHERE category='cooler' AND reference_price<=? AND reference_price>0"
        f" {socket_filter} {height_filter}"
        f" ORDER BY benchmark_score DESC, reference_price DESC LIMIT 1",
        (max_price,),
    ).fetchone()
    if row:
        return _parse(row)

    # 高さ制約を外してソケットだけで検索
    row = conn.execute(
        f"SELECT * FROM parts WHERE category='cooler' AND reference_price<=? AND reference_price>0"
        f" {socket_filter}"
        f" ORDER BY benchmark_score DESC, reference_price DESC LIMIT 1",
        (max_price,),
    ).fetchone()
    if row:
        return _parse(row)

    # 何もなければ無条件フォールバック
    return _pick(conn, "cooler", max_price)


# ── Core builder ───────────────────────────────────────────────────────────

def _build_suggestion(conn, budget: int, purpose: str, bias: str = "balanced") -> dict:
    alloc = dict(PURPOSE_ALLOCATION.get(purpose, PURPOSE_ALLOCATION["balanced"]))

    if bias == "cpu_heavy":
        alloc["cpu"] = min(alloc["cpu"] * 1.3, 0.40)
        alloc["gpu"] = max(alloc["gpu"] * 0.85, 0.05)
    elif bias == "gpu_heavy":
        alloc["gpu"] = min(alloc["gpu"] * 1.30, 0.50)
        alloc["cpu"] = max(alloc["cpu"] * 0.80, 0.10)

    total_ratio = sum(alloc.values())
    alloc = {k: v / total_ratio for k, v in alloc.items()}

    sel: dict[str, dict] = {}

    # ── 1. CPU ────────────────────────────────────────────────────────────
    cpu = _pick(conn, "cpu", int(budget * alloc["cpu"]))
    if not cpu:
        return _empty(budget, purpose, bias)
    sel["cpu"] = cpu

    raw_socket  = cpu["specs"].get("socket", "")
    cpu_socket  = _norm_socket(raw_socket)
    cpu_mem_raw = cpu["specs"].get("memory_type", [])
    if isinstance(cpu_mem_raw, str):
        cpu_mem_raw = [cpu_mem_raw] if cpu_mem_raw else []
    # memory_type が空なら socket から推定
    cpu_mem_types = cpu_mem_raw if cpu_mem_raw else _infer_mem_types(cpu_socket)
    preferred_mem = "DDR5" if "DDR5" in cpu_mem_types else (cpu_mem_types[0] if cpu_mem_types else "DDR4")

    # ── 2. Motherboard (ソケット一致) ────────────────────────────────────
    mobo_sql = _socket_like_clauses(cpu_socket) if cpu_socket else ""
    mobo = _pick(conn, "motherboard", int(budget * alloc["motherboard"]), mobo_sql)
    if mobo:
        sel["motherboard"] = mobo
        mobo_mem_raw   = mobo["specs"].get("memory_type", [])
        mobo_mem_types = [mobo_mem_raw] if isinstance(mobo_mem_raw, str) else (mobo_mem_raw or [])
        # CPU と MB の交差
        intersect = [t for t in cpu_mem_types if t in mobo_mem_types]
        if intersect:
            preferred_mem = "DDR5" if "DDR5" in intersect else intersect[0]
        mobo_form = mobo["specs"].get("form_factor", "ATX")
    else:
        mobo_form = "ATX"

    # ── 3. Memory (メモリ規格一致 + マザボ最大速度以内) ─────────────────
    mobo_max_spd = (mobo["specs"].get("max_memory_speed", 0) or 0) if mobo else 0
    spd_filter = f" AND (CAST(json_extract(specs,'$.speed') AS INTEGER) <= {mobo_max_spd} OR json_extract(specs,'$.speed') IS NULL)" if mobo_max_spd else ""
    mem_sql = f"AND specs LIKE '%\"memory_type\": \"{preferred_mem}\"%'" + spd_filter
    memory = _pick(conn, "memory", int(budget * alloc["memory"]), mem_sql)
    if not memory:
        # 速度制限を外して再試行
        mem_sql_nospd = f"AND specs LIKE '%\"memory_type\": \"{preferred_mem}\"%'"
        memory = _pick(conn, "memory", int(budget * alloc["memory"]), mem_sql_nospd)
    if not memory:
        # 代替規格で再試行
        for alt in [t for t in cpu_mem_types if t != preferred_mem]:
            memory = _pick(conn, "memory", int(budget * alloc["memory"]),
                           f"AND specs LIKE '%\"memory_type\": \"{alt}\"%'")
            if memory:
                break
    if not memory:
        memory = _pick(conn, "memory", int(budget * alloc["memory"]))
    if memory:
        sel["memory"] = memory

    # ── 4. GPU (office は不要) ────────────────────────────────────────────
    if alloc.get("gpu", 0) > 0.01:
        gpu = _pick(conn, "gpu", int(budget * alloc["gpu"]))
        if gpu:
            sel["gpu"] = gpu

    # ── 5. Storage ────────────────────────────────────────────────────────
    storage = _pick(conn, "storage", int(budget * alloc["storage"]))
    if storage:
        sel["storage"] = storage

    # ── 6. Case (MBフォームファクター対応) ──────────────────────────────
    case_sql = f"AND specs LIKE '%\"{mobo_form}\"%'" if mobo_form else ""
    case = _pick(conn, "case", int(budget * alloc["case"]), case_sql)
    if case:
        sel["case"] = case

    # ── 7. Cooler (ソケット対応 + ケース高さ制限) ─────────────────────
    case_max_h = (sel.get("case") or {}).get("specs", {}).get("max_cpu_cooler_height", 999)
    cooler = _pick_cooler(conn, int(budget * alloc["cooler"]), cpu_socket, case_max_h)
    if cooler:
        sel["cooler"] = cooler

    # ── 8. PSU (CPU+GPU TDP×1.3、最低450W) ─────────────────────────────
    cpu_tdp = cpu.get("tdp", 0) or 0
    gpu_tdp = sel.get("gpu", {}).get("tdp", 0) or 0
    required_w = max(450, int((cpu_tdp + gpu_tdp + 30) * 1.3))
    psu = _pick_psu(conn, int(budget * alloc["psu"]), required_w)
    if psu:
        sel["psu"] = psu

    used_budget = sum(p["reference_price"] for p in sel.values())
    compat = check_compatibility(sel)
    errors = [i for i in compat if i["level"] == "error"]

    return {
        "parts": sel,
        "total_price": used_budget,
        "budget": budget,
        "purpose": purpose,
        "purpose_label": PURPOSE_LABELS.get(purpose, purpose),
        "bias": bias,
        "compatibility": compat,
        "compatible": len(errors) == 0,
    }


def _empty(budget, purpose, bias):
    return {
        "parts": {}, "total_price": 0, "budget": budget,
        "purpose": purpose, "purpose_label": PURPOSE_LABELS.get(purpose, purpose),
        "bias": bias, "compatibility": [], "compatible": False,
    }


# ── Routes ─────────────────────────────────────────────────────────────────

@router.post("")
def get_suggestions(req: SuggestRequest):
    conn = get_db()
    purpose = req.purpose if req.purpose in PURPOSE_ALLOCATION else "balanced"

    plans = [
        _build_suggestion(conn, req.budget, purpose, "balanced"),
        _build_suggestion(conn, req.budget, purpose, "gpu_heavy"),
        _build_suggestion(conn, req.budget, purpose, "cpu_heavy"),
    ]
    labels = ["バランス型", "GPU重視", "CPU重視"]
    for i, plan in enumerate(plans):
        plan["label"] = labels[i]

    conn.close()
    return {"suggestions": plans}


@router.get("/part-suggest/{part_id}")
def suggest_compatible_parts(part_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM parts WHERE id=?", (part_id,)).fetchone()
    if not row:
        conn.close()
        return {"suggestions": {}}

    part = _parse(row)
    suggestions = {}
    cat   = part["category"]
    specs = part["specs"]

    if cat == "cpu":
        socket = _norm_socket(specs.get("socket", ""))
        mem_raw = specs.get("memory_type", [])
        mem_types = [mem_raw] if isinstance(mem_raw, str) and mem_raw else (mem_raw or _infer_mem_types(socket))

        if socket:
            sql = _socket_like_clauses(socket)
            rows = conn.execute(
                f"SELECT * FROM parts WHERE category='motherboard' {sql} ORDER BY benchmark_score DESC LIMIT 5",
            ).fetchall()
            suggestions["motherboard"] = [_parse(r) for r in rows]

        if mem_types:
            mem_q = " OR ".join([f"specs LIKE '%\"memory_type\": \"{mt}\"%'" for mt in mem_types])
            rows = conn.execute(
                f"SELECT * FROM parts WHERE category='memory' AND ({mem_q}) ORDER BY benchmark_score DESC LIMIT 5",
            ).fetchall()
            suggestions["memory"] = [_parse(r) for r in rows]

    elif cat == "motherboard":
        socket = _norm_socket(specs.get("socket", ""))
        mem_raw = specs.get("memory_type", [])
        mem_types = [mem_raw] if isinstance(mem_raw, str) and mem_raw else (mem_raw or [])

        if socket:
            sql = _socket_like_clauses(socket)
            rows = conn.execute(
                f"SELECT * FROM parts WHERE category='cpu' {sql} ORDER BY benchmark_score DESC LIMIT 5",
            ).fetchall()
            suggestions["cpu"] = [_parse(r) for r in rows]

        if mem_types:
            mem_q = " OR ".join([f"specs LIKE '%\"memory_type\": \"{mt}\"%'" for mt in mem_types])
            rows = conn.execute(
                f"SELECT * FROM parts WHERE category='memory' AND ({mem_q}) ORDER BY benchmark_score DESC LIMIT 5",
            ).fetchall()
            suggestions["memory"] = [_parse(r) for r in rows]

    conn.close()
    return {"base_part": part, "suggestions": suggestions}
