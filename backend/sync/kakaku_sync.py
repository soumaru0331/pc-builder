"""価格.com カテゴリページから自動パーツ収集"""
import re
import asyncio
import urllib.parse
from bs4 import BeautifulSoup
from scrapers.base import HEADERS
import httpx

from sync.brands import detect_brand
from sync.spec_parser import (
    parse_cpu, parse_gpu, parse_motherboard, parse_memory,
    parse_storage, parse_psu, parse_case, parse_cooler,
    estimate_benchmark, estimate_tdp,
)

# カテゴリ → 価格.com URL + パーサー
KAKAKU_CATEGORIES = {
    "cpu":         "https://kakaku.com/pc/cpu/itemlist.aspx",
    "gpu":         "https://kakaku.com/pc/videocard/itemlist.aspx",
    "motherboard": "https://kakaku.com/pc/motherboard/itemlist.aspx",
    "memory":      "https://kakaku.com/pc/pc-memory/itemlist.aspx",
    "storage":     "https://kakaku.com/pc/ssd/itemlist.aspx",
    "psu":         "https://kakaku.com/pc/power-supply/itemlist.aspx",
    "case":        "https://kakaku.com/pc/pc-case/itemlist.aspx",
    "cooler":      "https://kakaku.com/pc/cpu-cooler/itemlist.aspx",
}

SPEC_PARSERS = {
    "cpu":         parse_cpu,
    "gpu":         parse_gpu,
    "motherboard": parse_motherboard,
    "memory":      parse_memory,
    "storage":     parse_storage,
    "psu":         parse_psu,
    "case":        parse_case,
    "cooler":      parse_cooler,
}


async def _fetch(url: str, timeout: int = 15) -> str | None:
    try:
        async with httpx.AsyncClient(
            headers={**HEADERS, "Referer": "https://kakaku.com/"},
            follow_redirects=True,
            timeout=timeout,
        ) as client:
            r = await client.get(url)
            return r.text if r.status_code == 200 else None
    except Exception:
        return None


def _parse_page(html: str, category: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    results = []

    # 価格.com 実際の DOM: table.tbl-compare02 の中に商品が並ぶ
    # fixedHeader でない方のテーブルを使う（fixedHeaderは空のヘッダー専用）
    tables = soup.select("table.tbl-compare02")
    table = next((t for t in tables if "fixedHeader" not in (t.get("class") or [])), None)
    if table:
        results = _parse_compare_table(table, category)

    # フォールバック: 旧レイアウト対応
    if not results:
        results = _parse_legacy(soup, category)

    return results


def _parse_compare_table(table, category: str) -> list[dict]:
    """table.tbl-compare02 形式のパース"""
    results = []
    # tr.tr-border で全商品行を取得（ネストを超えて検索）
    rows = table.find_all("tr", class_="tr-border")

    current_name = None
    current_url = None

    for row in rows:
        # 商品名行: a.ckitanker を含む
        name_link = row.select_one("a.ckitanker")
        if name_link:
            current_name = name_link.get_text(" ", strip=True)
            current_url = name_link.get("href", "")
            continue

        # スペック/価格行: td.td-price を含む
        price_td = row.find("td", class_="td-price")
        if price_td and current_name:
            cells = row.find_all("td")
            price_text = cells[1].get_text(strip=True) if len(cells) > 1 else price_td.get_text(strip=True)
            price = _parse_price(price_text)

            # スペック列の抽出
            # [0]=checkbox [1]=price [2]=rank1 [3]=rank2 [4]=reviews [5]=views
            # [6]=date1 [7]=date2 [8]=model [9]=clock [10]=socket [11]=cores [12]=threads [13]=notes
            def cell_text(idx):
                return cells[idx].get_text(strip=True) if idx < len(cells) else ""

            name = current_name
            brand = detect_brand(name, category) or "不明"
            parser = SPEC_PARSERS.get(category, lambda x: {})
            specs = parser(name)

            # CPUのみ: socket/cores 列から補完（他カテゴリは列レイアウトが異なる）
            if category == "cpu":
                socket_text = cell_text(10)
                cores_text  = cell_text(11)
                if socket_text and "socket" not in specs:
                    specs["socket"] = socket_text
                if cores_text:
                    m = re.search(r"(\d+)", cores_text)
                    if m and "cores" not in specs:
                        specs["cores"] = int(m.group(1))

            benchmark = estimate_benchmark(category, specs, name)
            tdp = estimate_tdp(category, specs, name)
            specs.pop("_benchmark", None)
            specs.pop("_tdp", None)
            specs.pop("tdp_estimate", None)

            model = _extract_model(name, category) or name[:80]

            results.append({
                "category":        category,
                "brand":           brand,
                "name":            _clean_name(name, brand),
                "model":           model,
                "specs":           specs,
                "tdp":             tdp,
                "benchmark_score": benchmark,
                "reference_price": price,
                "release_year":    None,
                "notes":           "",
            })
            current_name = None
            current_url = None

    return results


def _parse_legacy(soup, category: str) -> list[dict]:
    """旧レイアウト対応フォールバック"""
    results = []
    items = (
        soup.select(".p-item_unit") or
        soup.select(".itemUnit") or
        soup.select("li.p-result_item")
    )
    for item in items:
        title_el = (
            item.select_one(".p-item_unit__title a") or
            item.select_one(".itmTtlNmLink") or
            item.select_one("a[href*='/item/']")
        )
        if not title_el:
            continue
        name = title_el.get_text(strip=True)
        if not name or len(name) < 4:
            continue

        price_el = (
            item.select_one(".p-item_unit__price") or
            item.select_one(".priceValue") or
            item.select_one("[class*='price']")
        )
        price_text = price_el.get_text(strip=True) if price_el else ""
        price = _parse_price(price_text)

        brand = detect_brand(name, category) or "不明"
        parser = SPEC_PARSERS.get(category, lambda x: {})
        specs = parser(name)
        benchmark = estimate_benchmark(category, specs, name)
        tdp = estimate_tdp(category, specs, name)
        specs.pop("_benchmark", None)
        specs.pop("_tdp", None)
        specs.pop("tdp_estimate", None)
        model = _extract_model(name, category) or name[:80]

        results.append({
            "category":        category,
            "brand":           brand,
            "name":            _clean_name(name, brand),
            "model":           model,
            "specs":           specs,
            "tdp":             tdp,
            "benchmark_score": benchmark,
            "reference_price": price,
            "release_year":    None,
            "notes":           "",
        })
    return results


def _parse_price(text: str) -> int:
    # 最初の価格数字だけ取る（例: "¥60,000電子問屋（全33店舗）" → 60000）
    m = re.search(r"[\d,]+", text)
    if not m:
        return 0
    try:
        v = int(m.group().replace(",", ""))
        return v if 1000 <= v <= 10_000_000 else 0
    except Exception:
        return 0


def _extract_model(name: str, category: str) -> str:
    """商品名から型番らしき文字列を抽出"""
    # CPU: "Core i9-14900K" → "BX8071514900K" は不明なので名前をモデルとして使う
    # GPU: "ROG STRIX RTX 4090 OC 24GB" のような名前
    # とりあえず名前そのまま（80文字制限）
    return name[:80]


def _clean_name(name: str, brand: str) -> str:
    """商品名からブランド名の重複を除去して短くする"""
    # ブランド名が先頭にある場合は除去
    cleaned = name
    if cleaned.upper().startswith(brand.upper()):
        cleaned = cleaned[len(brand):].lstrip(" -/")
    return cleaned[:100]


# CPU/GPU 除外キーワード（サーバー向け・超高額・旧世代）
_SKIP_KEYWORDS = {
    "cpu": ["Threadripper", "EPYC", "Xeon", "Core 2", "Core Duo", "Core Solo",
            "Pentium D", "Pentium 4", "Celeron D", "Atom ", "Sempron", "Opteron",
            "A4-", "A6-", "A8-", "A10-", "E1-", "E2-", "FX-"],
    "gpu": ["Quadro", "Tesla", "FirePro", "Radeon Pro", "A2000", "A4000", "A5000", "A6000"],
}

def _should_skip(part: dict) -> bool:
    """サーバー向け・超旧世代・高額すぎるパーツをスキップ"""
    name = part.get("name", "")
    cat  = part.get("category", "")
    for kw in _SKIP_KEYWORDS.get(cat, []):
        if kw.lower() in name.lower():
            return True
    # 価格が異常に高い（ワークステーション向けと判断）
    price = part.get("reference_price", 0)
    if cat == "cpu" and price > 300_000:
        return True
    if cat == "gpu" and price > 500_000:
        return True
    return False


async def sync_category(category: str, max_pages: int = 3) -> list[dict]:
    """指定カテゴリの最大 max_pages ページを取得してパーツリストを返す"""
    base_url = KAKAKU_CATEGORIES.get(category)
    if not base_url:
        return []

    all_parts: list[dict] = []
    seen_names: set[str] = set()

    for page in range(1, max_pages + 1):
        url = base_url if page == 1 else base_url + f"?pdf_pg={page}"
        html = await _fetch(url)
        if not html:
            break

        parts = _parse_page(html, category)
        if not parts:
            break  # ページに商品がなければ終了

        for p in parts:
            if _should_skip(p):
                continue
            key = f"{p['brand']}|{p['name'][:50]}"
            if key not in seen_names:
                seen_names.add(key)
                all_parts.append(p)

        # 最終ページ判定: .pageNextOn があれば次ページあり
        soup = BeautifulSoup(html, "lxml")
        has_next = bool(
            soup.select_one(".pageNextOn") or
            soup.select_one("a.arrow_next") or
            soup.select_one("a[class*='next']")
        )
        if not has_next:
            break

        await asyncio.sleep(1.5)  # サーバー負荷軽減

    return all_parts


async def sync_all_categories(categories: list[str] | None = None, max_pages: int = 3) -> dict:
    """複数カテゴリを順番に取得（並列だと ban される可能性があるため逐次）"""
    targets = categories or list(KAKAKU_CATEGORIES.keys())
    result = {}
    for cat in targets:
        parts = await sync_category(cat, max_pages)
        result[cat] = parts
        await asyncio.sleep(2)  # カテゴリ間のウェイト
    return result
