import json
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from database import get_db

router = APIRouter()


def _load_parts(conn, part_ids: list[int]) -> dict:
    """Return {id: part_dict} for given ids."""
    result = {}
    for pid in part_ids:
        row = conn.execute("SELECT * FROM parts WHERE id=?", (pid,)).fetchone()
        if row:
            d = dict(row)
            try:
                d["specs"] = json.loads(d["specs"])
            except Exception:
                d["specs"] = {}
            result[pid] = d
    return result


def _norm(s: str) -> str:
    """ソケット表記ゆれ正規化: 'Socket AM4' → 'AM4'"""
    return s.replace("Socket ", "").strip() if s else ""


def check_compatibility(parts_by_category: dict) -> list[dict]:
    """
    parts_by_category: {"cpu": part_dict, "gpu": part_dict, ...}
    Returns list of {"level": "error"|"warning"|"ok", "message": str}
    """
    issues = []

    cpu = parts_by_category.get("cpu")
    gpu = parts_by_category.get("gpu")
    mobo = parts_by_category.get("motherboard")
    mem = parts_by_category.get("memory")
    case = parts_by_category.get("case")
    psu = parts_by_category.get("psu")
    cooler = parts_by_category.get("cooler")
    storage_list = parts_by_category.get("storage", [])
    if not isinstance(storage_list, list):
        storage_list = [storage_list]

    # ── CPU ↔ Motherboard ─────────────────────────────────────────────
    if cpu and mobo:
        cpu_socket = _norm(cpu["specs"].get("socket", ""))
        mobo_socket = _norm(mobo["specs"].get("socket", ""))
        if cpu_socket and mobo_socket:
            if cpu_socket != mobo_socket:
                issues.append({
                    "level": "error",
                    "category": "cpu-motherboard",
                    "message": f"❌ CPUソケット({cpu_socket}) と マザーボードソケット({mobo_socket}) が一致しません",
                })
            else:
                issues.append({"level": "ok", "category": "cpu-motherboard",
                                "message": f"✅ ソケット互換 ({cpu_socket})"})

    # ── CPU ↔ Memory ──────────────────────────────────────────────────
    if cpu and mem:
        cpu_mem = cpu["specs"].get("memory_type", []) or []
        ram_type = mem["specs"].get("memory_type", "")
        if isinstance(cpu_mem, str):
            cpu_mem = [cpu_mem]
        if ram_type and cpu_mem:
            if ram_type not in cpu_mem:
                issues.append({
                    "level": "error",
                    "category": "cpu-memory",
                    "message": f"❌ CPUは{'/'.join(cpu_mem)}をサポートしますが、選択メモリは{ram_type}です",
                })
            else:
                issues.append({"level": "ok", "category": "cpu-memory",
                                "message": f"✅ メモリ規格互換 ({ram_type})"})

    # ── Motherboard ↔ Memory ──────────────────────────────────────────
    if mobo and mem:
        mobo_mem = mobo["specs"].get("memory_type", [])
        ram_type = mem["specs"].get("memory_type", "")
        ram_speed = mem["specs"].get("speed", 0)
        max_speed = mobo["specs"].get("max_memory_speed", 0)
        if isinstance(mobo_mem, str):
            mobo_mem = [mobo_mem]
        if ram_type and mobo_mem:
            if ram_type not in mobo_mem:
                issues.append({
                    "level": "error",
                    "category": "motherboard-memory",
                    "message": f"❌ マザーボードは{'/'.join(mobo_mem)}をサポートしますが、選択メモリは{ram_type}です",
                })
            else:
                issues.append({"level": "ok", "category": "motherboard-memory",
                                "message": f"✅ マザーボード・メモリ規格互換"})
        if ram_speed and max_speed and ram_speed > max_speed:
            issues.append({
                "level": "warning",
                "category": "motherboard-memory-speed",
                "message": f"⚠️ メモリ速度({ram_speed}MHz)はマザーボード最大({max_speed}MHz)を超えます。XMPで動作するか確認してください",
            })

    # ── Motherboard ↔ Case ────────────────────────────────────────────
    if mobo and case:
        mobo_ff = mobo["specs"].get("form_factor", "")
        case_ffs = case["specs"].get("form_factors", [])
        if mobo_ff and case_ffs:
            if mobo_ff not in case_ffs:
                issues.append({
                    "level": "error",
                    "category": "motherboard-case",
                    "message": f"❌ マザーボード({mobo_ff}) はケース対応フォームファクター({', '.join(case_ffs)})に非対応です",
                })
            else:
                issues.append({"level": "ok", "category": "motherboard-case",
                                "message": f"✅ フォームファクター互換 ({mobo_ff})"})

    # ── GPU ↔ Case ────────────────────────────────────────────────────
    if gpu and case:
        gpu_len = gpu["specs"].get("length", 0)
        case_max = case["specs"].get("max_gpu_length", 0)
        if gpu_len and case_max:
            if gpu_len > case_max:
                issues.append({
                    "level": "error",
                    "category": "gpu-case",
                    "message": f"❌ GPU長({gpu_len}mm) がケースの最大GPU長({case_max}mm)を超えます",
                })
            elif gpu_len > case_max * 0.9:
                issues.append({
                    "level": "warning",
                    "category": "gpu-case",
                    "message": f"⚠️ GPU長({gpu_len}mm) がケースの最大GPU長({case_max}mm)に近いです。実際の搭載は要確認",
                })
            else:
                issues.append({"level": "ok", "category": "gpu-case",
                                "message": f"✅ GPU長互換 ({gpu_len}mm / 最大{case_max}mm)"})

    # ── Cooler ↔ CPU ──────────────────────────────────────────────────
    if cooler and cpu:
        cooler_sockets_raw = cooler["specs"].get("sockets", []) or []
        cooler_sockets = [_norm(s) for s in cooler_sockets_raw]
        cpu_socket = _norm(cpu["specs"].get("socket", ""))
        cooler_tdp = cooler["specs"].get("max_tdp", 0)
        cpu_tdp = cpu.get("tdp", 0)
        if cpu_socket and cooler_sockets:
            if cpu_socket not in cooler_sockets:
                issues.append({
                    "level": "error",
                    "category": "cooler-cpu",
                    "message": f"❌ クーラーは{cpu_socket}に非対応です (対応: {', '.join(cooler_sockets)})",
                })
            else:
                issues.append({"level": "ok", "category": "cooler-cpu",
                                "message": f"✅ クーラー・ソケット互換"})
        if cooler_tdp and cpu_tdp:
            if cpu_tdp > cooler_tdp:
                issues.append({
                    "level": "warning",
                    "category": "cooler-tdp",
                    "message": f"⚠️ CPU TDP({cpu_tdp}W) がクーラー最大TDP({cooler_tdp}W)を超えます",
                })
            elif cpu_tdp > cooler_tdp * 0.85:
                issues.append({
                    "level": "warning",
                    "category": "cooler-tdp",
                    "message": f"⚠️ CPU TDP({cpu_tdp}W) がクーラー最大TDP({cooler_tdp}W)に近いです",
                })

    # ── Cooler ↔ Case ─────────────────────────────────────────────────
    if cooler and case:
        cooler_type = cooler["specs"].get("type", "Air")
        cooler_h = cooler["specs"].get("height", 0)
        case_max_h = case["specs"].get("max_cpu_cooler_height", 0)
        if cooler_type == "Air" and cooler_h and case_max_h:
            if cooler_h > case_max_h:
                issues.append({
                    "level": "error",
                    "category": "cooler-case",
                    "message": f"❌ クーラー高さ({cooler_h}mm) がケース最大({case_max_h}mm)を超えます",
                })
            else:
                issues.append({"level": "ok", "category": "cooler-case",
                                "message": f"✅ クーラー高さ互換 ({cooler_h}mm / 最大{case_max_h}mm)"})

    # ── Power Budget ──────────────────────────────────────────────────
    if psu:
        psu_w = psu["specs"].get("wattage", 0)
        total_tdp = 0
        if cpu:
            total_tdp += cpu.get("tdp", 0)
        if gpu:
            total_tdp += gpu.get("tdp", 0)
        total_tdp += 30  # system misc

        if psu_w and total_tdp:
            ratio = total_tdp / psu_w
            recommended = int(total_tdp * 1.25)
            if ratio > 0.85:
                issues.append({
                    "level": "error",
                    "category": "power",
                    "message": f"❌ 電源容量不足の可能性があります (推定消費{total_tdp}W / PSU {psu_w}W)。{recommended}W以上を推奨",
                })
            elif ratio > 0.80:
                issues.append({
                    "level": "warning",
                    "category": "power",
                    "message": f"⚠️ 電源容量がタイトです (推定{total_tdp}W / PSU {psu_w}W)。{recommended}W以上を推奨",
                })
            else:
                issues.append({"level": "ok", "category": "power",
                                "message": f"✅ 電源容量十分 (推定{total_tdp}W / PSU {psu_w}W)"})

    # ── Bottleneck Detection ──────────────────────────────────────────
    if cpu and gpu:
        cpu_score = cpu.get("benchmark_score", 0)
        gpu_score = gpu.get("benchmark_score", 0)
        if cpu_score and gpu_score:
            ratio = cpu_score / gpu_score
            if ratio < 0.25:
                issues.append({
                    "level": "warning",
                    "category": "bottleneck",
                    "message": f"⚠️ CPUボトルネックの可能性があります。GPUに対してCPU性能が低いです",
                })
            elif ratio > 2.5:
                issues.append({
                    "level": "warning",
                    "category": "bottleneck",
                    "message": f"⚠️ GPUがCPUに対して性能不足です。よりハイエンドなGPUを検討してください",
                })
            else:
                issues.append({"level": "ok", "category": "bottleneck",
                                "message": "✅ CPU・GPUバランス良好"})

    return issues


@router.post("/check")
def check_build_compatibility(
    build_id: Optional[int] = Query(default=None),
    part_ids: list[int] = Query(default=[]),
):
    """Check compatibility for a build or a list of part IDs."""
    conn = get_db()

    if build_id:
        rows = conn.execute(
            """SELECT p.* FROM build_parts bp
               JOIN parts p ON bp.part_id = p.id
               WHERE bp.build_id=?""",
            (build_id,),
        ).fetchall()
        part_dicts = []
        for r in rows:
            d = dict(r)
            try:
                d["specs"] = json.loads(d["specs"])
            except Exception:
                d["specs"] = {}
            part_dicts.append(d)
    elif part_ids:
        part_dicts = []
        for pid in part_ids:
            row = conn.execute("SELECT * FROM parts WHERE id=?", (pid,)).fetchone()
            if row:
                d = dict(row)
                try:
                    d["specs"] = json.loads(d["specs"])
                except Exception:
                    d["specs"] = {}
                part_dicts.append(d)
    else:
        conn.close()
        raise HTTPException(400, "build_id か part_ids を指定してください")

    conn.close()

    # Group by category
    by_cat = {}
    storage_parts = []
    for p in part_dicts:
        cat = p["category"]
        if cat == "storage":
            storage_parts.append(p)
        else:
            by_cat[cat] = p
    if storage_parts:
        by_cat["storage"] = storage_parts

    issues = check_compatibility(by_cat)

    errors = [i for i in issues if i["level"] == "error"]
    warnings = [i for i in issues if i["level"] == "warning"]
    oks = [i for i in issues if i["level"] == "ok"]

    return {
        "compatible": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "ok": oks,
        "summary": f"エラー {len(errors)}件 / 警告 {len(warnings)}件",
    }
