import json
from fastapi import APIRouter, HTTPException
from database import get_db
from models import BuildCreate, BuildUpdate, BuildPartAdd

router = APIRouter()


def row_to_dict(row):
    return dict(row)


def get_build_full(conn, build_id: int):
    build = conn.execute("SELECT * FROM builds WHERE id=?", (build_id,)).fetchone()
    if not build:
        return None
    build = dict(build)

    rows = conn.execute(
        """SELECT bp.id AS build_part_id, bp.build_id, bp.part_id,
                  bp.quantity, bp.custom_price, bp.is_used,
                  p.id AS id, p.category, p.brand, p.name, p.model, p.specs,
                  p.tdp, p.benchmark_score, p.reference_price
           FROM build_parts bp
           JOIN parts p ON bp.part_id = p.id
           WHERE bp.build_id=?""",
        (build_id,),
    ).fetchall()

    parts = []
    total_new = 0
    total_tdp = 0
    for r in rows:
        d = dict(r)
        try:
            d["specs"] = json.loads(d["specs"])
        except Exception:
            d["specs"] = {}
        price = d["custom_price"] if d["custom_price"] else d["reference_price"]
        d["effective_price"] = price
        total_new += price * d["quantity"]
        total_tdp += (d["tdp"] or 0) * d["quantity"]
        parts.append(d)

    build["parts"] = parts
    build["total_price"] = total_new
    build["total_tdp"] = total_tdp
    return build


@router.get("")
def list_builds():
    conn = get_db()
    rows = conn.execute("SELECT * FROM builds ORDER BY updated_at DESC").fetchall()
    result = []
    for row in rows:
        b = dict(row)
        # total_price・パーツ情報をまとめて取得
        part_rows = conn.execute(
            """SELECT p.category, p.brand, p.name,
                      CASE WHEN bp.custom_price IS NOT NULL THEN bp.custom_price
                           ELSE p.reference_price END AS price,
                      bp.quantity,
                      COALESCE(p.tdp, 0) * bp.quantity AS tdp_contrib
               FROM build_parts bp JOIN parts p ON bp.part_id = p.id
               WHERE bp.build_id=?""",
            (b["id"],),
        ).fetchall()
        total = 0
        total_tdp = 0
        categories_filled = []
        part_summary = []
        for pr in part_rows:
            total += pr["price"] * pr["quantity"]
            total_tdp += pr["tdp_contrib"]
            categories_filled.append(pr["category"])
            part_summary.append({
                "category": pr["category"],
                "label": f'{pr["brand"]} {pr["name"]}',
            })
        b["total_price"] = total
        b["total_tdp"] = total_tdp
        b["part_count"] = len(part_rows)
        b["categories_filled"] = categories_filled
        b["part_summary"] = part_summary
        result.append(b)
    conn.close()
    return result


@router.get("/{build_id}")
def get_build(build_id: int):
    conn = get_db()
    build = get_build_full(conn, build_id)
    conn.close()
    if not build:
        raise HTTPException(404, "構成が見つかりません")
    return build


@router.post("", status_code=201)
def create_build(build: BuildCreate):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO builds (name,description,purpose,budget) VALUES (?,?,?,?)",
        (build.name, build.description, build.purpose, build.budget),
    )
    conn.commit()
    build_id = c.lastrowid
    conn.close()
    return {"id": build_id, "message": "構成を作成しました"}


@router.put("/{build_id}")
def update_build(build_id: int, build: BuildUpdate):
    conn = get_db()
    existing = conn.execute("SELECT id FROM builds WHERE id=?", (build_id,)).fetchone()
    if not existing:
        conn.close()
        raise HTTPException(404, "構成が見つかりません")
    updates = build.model_dump(exclude_none=True)
    if updates:
        updates["updated_at"] = "datetime('now')"
        set_clause = ", ".join(f"{k}=?" for k in updates if k != "updated_at")
        set_clause += ", updated_at=datetime('now')"
        values = [v for k, v in updates.items() if k != "updated_at"] + [build_id]
        conn.execute(f"UPDATE builds SET {set_clause} WHERE id=?", values)
        conn.commit()
    conn.close()
    return {"message": "構成を更新しました"}


@router.delete("/{build_id}")
def delete_build(build_id: int):
    conn = get_db()
    conn.execute("DELETE FROM builds WHERE id=?", (build_id,))
    conn.commit()
    conn.close()
    return {"message": "構成を削除しました"}


@router.post("/{build_id}/parts")
def add_part_to_build(build_id: int, req: BuildPartAdd):
    conn = get_db()
    build = conn.execute("SELECT id FROM builds WHERE id=?", (build_id,)).fetchone()
    if not build:
        conn.close()
        raise HTTPException(404, "構成が見つかりません")
    part = conn.execute("SELECT id, category FROM parts WHERE id=?", (req.part_id,)).fetchone()
    if not part:
        conn.close()
        raise HTTPException(404, "パーツが見つかりません")

    # remove existing part of same category (one per category rule, except storage)
    if part["category"] not in ("storage",):
        conn.execute(
            """DELETE FROM build_parts WHERE build_id=? AND part_id IN
               (SELECT id FROM parts WHERE category=?)""",
            (build_id, part["category"]),
        )

    conn.execute(
        "INSERT INTO build_parts (build_id,part_id,quantity,custom_price,is_used) VALUES (?,?,?,?,?)",
        (build_id, req.part_id, req.quantity, req.custom_price, 1 if req.is_used else 0),
    )
    conn.execute("UPDATE builds SET updated_at=datetime('now') WHERE id=?", (build_id,))
    conn.commit()
    conn.close()
    return {"message": "パーツを追加しました"}


@router.delete("/{build_id}/parts/{part_id}")
def remove_part_from_build(build_id: int, part_id: int):
    conn = get_db()
    conn.execute("DELETE FROM build_parts WHERE part_id=? AND build_id=?", (part_id, build_id))
    conn.execute("UPDATE builds SET updated_at=datetime('now') WHERE id=?", (build_id,))
    conn.commit()
    conn.close()
    return {"message": "パーツを削除しました"}


from pydantic import BaseModel

class PriceUpdate(BaseModel):
    custom_price: int
    is_used: bool = False


@router.put("/{build_id}/parts/{part_id}/price")
def update_part_price(build_id: int, part_id: int, req: PriceUpdate):
    """選択済みパーツのカスタム価格を更新する"""
    conn = get_db()
    conn.execute(
        "UPDATE build_parts SET custom_price=?, is_used=? WHERE build_id=? AND part_id=?",
        (req.custom_price, 1 if req.is_used else 0, build_id, part_id),
    )
    conn.execute("UPDATE builds SET updated_at=datetime('now') WHERE id=?", (build_id,))
    conn.commit()
    conn.close()
    return {"message": "価格を更新しました"}
