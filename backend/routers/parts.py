import json
from fastapi import APIRouter, HTTPException, Depends
from database import get_db
from models import PartCreate, PartUpdate
from auth import require_admin

router = APIRouter()

CATEGORIES = ["cpu", "gpu", "motherboard", "memory", "storage", "psu", "case", "cooler"]


def row_to_part(row):
    d = dict(row)
    try:
        d["specs"] = json.loads(d["specs"])
    except Exception:
        d["specs"] = {}
    return d


@router.get("")
def list_parts(category: str = None, q: str = None, brand: str = None):
    conn = get_db()
    sql = "SELECT * FROM parts WHERE 1=1"
    params = []
    if category:
        sql += " AND category=?"
        params.append(category)
    if brand:
        sql += " AND brand LIKE ?"
        params.append(f"%{brand}%")
    if q:
        sql += " AND (name LIKE ? OR model LIKE ? OR brand LIKE ?)"
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    sql += " ORDER BY category, brand, name"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [row_to_part(r) for r in rows]


@router.get("/count")
def count_parts(category: str = None):
    conn = get_db()
    if category:
        row = conn.execute("SELECT COUNT(*) FROM parts WHERE category=?", (category,)).fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) FROM parts").fetchone()
    conn.close()
    return {"count": row[0]}


@router.get("/categories")
def get_categories():
    return CATEGORIES


@router.get("/brands")
def get_brands(category: str = None):
    conn = get_db()
    if category:
        rows = conn.execute("SELECT DISTINCT brand FROM parts WHERE category=? ORDER BY brand", (category,)).fetchall()
    else:
        rows = conn.execute("SELECT DISTINCT brand FROM parts ORDER BY brand").fetchall()
    conn.close()
    return [r[0] for r in rows]


@router.get("/{part_id}/price-history")
def get_price_history(part_id: int):
    """パーツの価格履歴を返す（直近30件）"""
    conn = get_db()
    part = conn.execute("SELECT id FROM parts WHERE id=?", (part_id,)).fetchone()
    if not part:
        conn.close()
        raise HTTPException(404, "パーツが見つかりません")
    rows = conn.execute(
        """SELECT price, source, recorded_at FROM price_history
           WHERE part_id=? ORDER BY id DESC LIMIT 30""",
        (part_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/{part_id}")
def get_part(part_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM parts WHERE id=?", (part_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "パーツが見つかりません")
    return row_to_part(row)


@router.post("", status_code=201, dependencies=[Depends(require_admin)])
def create_part(part: PartCreate):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        """INSERT INTO parts (category,brand,name,model,specs,tdp,benchmark_score,reference_price,release_year,notes)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (part.category, part.brand, part.name, part.model,
         json.dumps(part.specs, ensure_ascii=False),
         part.tdp, part.benchmark_score, part.reference_price,
         part.release_year, part.notes),
    )
    conn.commit()
    part_id = c.lastrowid
    conn.close()
    return {"id": part_id, "message": "パーツを追加しました"}


@router.put("/{part_id}", dependencies=[Depends(require_admin)])
def update_part(part_id: int, part: PartUpdate):
    conn = get_db()
    existing = conn.execute("SELECT * FROM parts WHERE id=?", (part_id,)).fetchone()
    if not existing:
        conn.close()
        raise HTTPException(404, "パーツが見つかりません")

    updates = part.model_dump(exclude_none=True)
    if not updates:
        conn.close()
        return {"message": "変更なし"}

    if "specs" in updates:
        updates["specs"] = json.dumps(updates["specs"], ensure_ascii=False)

    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [part_id]
    conn.execute(f"UPDATE parts SET {set_clause} WHERE id=?", values)
    conn.commit()
    conn.close()
    return {"message": "パーツを更新しました"}


@router.delete("/{part_id}", dependencies=[Depends(require_admin)])
def delete_part(part_id: int):
    conn = get_db()
    conn.execute("DELETE FROM parts WHERE id=?", (part_id,))
    conn.commit()
    conn.close()
    return {"message": "パーツを削除しました"}
