"""楽天市場 検索ページから自動パーツ収集（マイナーブランド対応）"""
import re
import json
import asyncio
import httpx
from bs4 import BeautifulSoup

from sync.brands import detect_brand
from sync.spec_parser import (
    parse_cpu, parse_gpu, parse_motherboard, parse_memory,
    parse_storage, parse_psu, parse_case, parse_cooler,
    estimate_benchmark, estimate_tdp,
)

# カテゴリ → 楽天検索キーワード + ページ URL
RAKUTEN_CATEGORIES = {
    "gpu":         "グラフィックボード GPU RX RTX Radeon GeForce",
    "cpu":         "CPU プロセッサー Core Ryzen",
    "motherboard": "マザーボード LGA1700 AM5 AM4",
    "memory":      "メモリ DDR5 DDR4 デスクトップ",
    "storage":     "SSD M.2 NVMe SATA",
    "psu":         "電源ユニット ATX 650W 750W 850W",
    "case":        "PCケース ATX ミドルタワー",
    "cooler":      "CPUクーラー 空冷 水冷",
}

# 楽天検索ページベースURL
_SEARCH_BASE = "https://search.rakuten.co.jp/search/mall/"

# User-Agent（ブラウザを偽装）
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja-JP,ja;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://search.rakuten.co.jp/",
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

# 不要なキーワードが含まれる商品を除外
_SKIP_KEYWORDS = {
    "gpu": ["Quadro", "Tesla", "FirePro", "Radeon Pro", "ノートPC", "ノート用",
            "スリムPC", "ケーブル", "変換", "延長", "対応ソフト", "ゲームソフト"],
    "cpu": ["Threadripper", "EPYC", "Xeon", "ノート用", "モバイル",
            "Core 2", "Pentium D", "Pentium 4", "Celeron D", "Atom "],
    "memory": ["ノート用", "SO-DIMM", "ノートPC用", "ラップトップ", "PS5", "PS4",
               "Nintendo", "スマホ", "SDカード", "microSD"],
    "storage": ["PS5", "PS4", "Nintendo", "外付け", "ポータブル", "USBメモリ",
                "SDカード", "microSD", "NAS用", "監視カメラ"],
    "psu": ["ノートPC", "アダプター", "変換", "ケーブル"],
    "case": ["スマートフォン", "スマホ", "タブレット", "ゲーム機"],
    "cooler": ["ノートPC", "スマホ", "タブレット", "ゲーム機冷却"],
    "motherboard": ["ノートPC", "サーバー"],
}


async def _fetch_page(keyword: str, page: int = 1, timeout: int = 15) -> str | None:
    """楽天検索ページを取得"""
    import urllib.parse
    encoded = urllib.parse.quote(keyword)
    url = f"{_SEARCH_BASE}{encoded}/"
    params = {"p": page, "s": 3}  # s=3: 売れ筋順
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS,
            follow_redirects=True,
            timeout=timeout,
        ) as client:
            r = await client.get(url, params=params)
            return r.text if r.status_code == 200 else None
    except Exception:
        return None


def _extract_initial_state(html: str) -> list[dict]:
    """window.__INITIAL_STATE__ から商品データを抽出"""
    # パターン1: window.__INITIAL_STATE__ = {...}
    m = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.+?\});\s*(?:window|</script>)", html, re.DOTALL)
    if not m:
        # パターン2: より広い範囲
        m = re.search(r"__INITIAL_STATE__[^=]*=\s*(\{.+)", html, re.DOTALL)
    if not m:
        return []

    raw = m.group(1)
    # JSONとして一番外側の } までを抽出
    depth = 0
    end = 0
    for i, ch in enumerate(raw):
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if not end:
        return []

    try:
        data = json.loads(raw[:end])
    except Exception:
        return []

    # hits / items / searchResult のどこかに商品リストがあるはず
    items = []
    _collect_item_hits(data, items)
    return items


def _collect_item_hits(obj, result: list, depth: int = 0):
    """JSON再帰探索で商品ヒットリストを見つける"""
    if depth > 8:
        return
    if isinstance(obj, list) and len(obj) > 0:
        if isinstance(obj[0], dict) and any(k in obj[0] for k in ("name", "itemName", "itemUrl", "price")):
            result.extend(obj)
            return
        for item in obj:
            _collect_item_hits(item, result, depth + 1)
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_item_hits(v, result, depth + 1)


def _extract_jsonld(html: str) -> list[dict]:
    """JSON-LD Schema.org ItemList から商品データを抽出"""
    items = []
    soup = BeautifulSoup(html, "lxml")
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except Exception:
            continue
        if isinstance(data, list):
            for d in data:
                _collect_jsonld_products(d, items)
        else:
            _collect_jsonld_products(data, items)
    return items


def _collect_jsonld_products(data: dict, result: list):
    if not isinstance(data, dict):
        return
    t = data.get("@type", "")
    if t == "Product":
        result.append(data)
    elif t in ("ItemList", "SearchResultsPage"):
        for el in data.get("itemListElement", []):
            if isinstance(el, dict):
                item = el.get("item", el)
                _collect_jsonld_products(item, result)


def _extract_html_fallback(html: str, category: str) -> list[dict]:
    """HTMLから商品名・価格を直接スクレイピング（フォールバック）"""
    soup = BeautifulSoup(html, "lxml")
    results = []

    # 楽天検索結果のHTML構造
    # .searchresultitem, .dui-card, [data-testid="SearchResultItem"]
    items = (
        soup.select(".searchresultitem") or
        soup.select("[class*='SearchResultItem']") or
        soup.select(".dui-card") or
        soup.select("li[data-item-id]")
    )

    for item in items:
        # 商品名
        title_el = (
            item.select_one("[class*='title'] a") or
            item.select_one(".title a") or
            item.select_one("a[class*='title']") or
            item.select_one("h2 a") or
            item.select_one("a[href*='item.rakuten']")
        )
        if not title_el:
            continue
        name = title_el.get_text(strip=True)
        if not name or len(name) < 5:
            continue

        # 価格
        price_el = (
            item.select_one("[class*='price']") or
            item.select_one(".price") or
            item.select_one("[class*='Price']")
        )
        price_text = price_el.get_text(strip=True) if price_el else ""
        price = _parse_price(price_text)

        results.append({"name": name, "price": price, "brand": None})

    return results


def _normalize_item(raw: dict, category: str) -> dict | None:
    """生のJSONアイテムを正規化してパーツ辞書に変換"""
    # 商品名を取得（キー名のバリエーションに対応）
    name = (
        raw.get("name") or
        raw.get("itemName") or
        raw.get("title") or
        ""
    )
    if not name or len(name) < 5:
        return None

    # 価格を取得
    price_raw = (
        raw.get("price") or
        raw.get("minPrice") or
        raw.get("salePrice") or
        (raw.get("offers", {}) or {}).get("price") or
        0
    )
    try:
        price = int(float(str(price_raw).replace(",", "").replace("¥", "")))
    except Exception:
        price = 0

    # 価格の妥当性チェック（1000円〜300万円の範囲外はスキップ）
    if price > 0 and not (1000 <= price <= 3_000_000):
        price = 0

    # ブランド検出
    maker = (
        raw.get("maker") or
        raw.get("brand") or
        (raw.get("brand", {}) or {}).get("name") or
        ""
    )
    brand = (
        detect_brand(maker, category) or
        detect_brand(name, category) or
        "不明"
    )

    # スキップチェック
    name_lower = name.lower()
    for kw in _SKIP_KEYWORDS.get(category, []):
        if kw.lower() in name_lower:
            return None

    # スペック解析
    parser = SPEC_PARSERS.get(category, lambda x: {})
    specs = parser(name)
    benchmark = estimate_benchmark(category, specs, name)
    tdp = estimate_tdp(category, specs, name)
    specs.pop("_benchmark", None)
    specs.pop("_tdp", None)
    specs.pop("tdp_estimate", None)

    model = name[:80]
    clean = name
    if brand != "不明" and clean.upper().startswith(brand.upper()):
        clean = clean[len(brand):].lstrip(" -/")
    clean = clean[:100]

    return {
        "category":        category,
        "brand":           brand,
        "name":            clean,
        "model":           model,
        "specs":           specs,
        "tdp":             tdp,
        "benchmark_score": benchmark,
        "reference_price": price,
        "release_year":    None,
        "notes":           "楽天",
    }


def _parse_price(text: str) -> int:
    """価格文字列から数値を抽出（単位: 円）"""
    m = re.search(r"[\d,]+", text.replace("，", ","))
    if not m:
        return 0
    try:
        v = int(m.group().replace(",", ""))
        return v if 1000 <= v <= 3_000_000 else 0
    except Exception:
        return 0


def _parse_and_normalize(html: str, category: str) -> list[dict]:
    """HTMLからパーツリストを生成"""
    # 優先: window.__INITIAL_STATE__
    raw_items = _extract_initial_state(html)

    # 次: JSON-LD
    if not raw_items:
        raw_items = _extract_jsonld(html)

    # 最終: HTML直接パース
    if not raw_items:
        raw_items = _extract_html_fallback(html, category)

    parts = []
    for raw in raw_items:
        p = _normalize_item(raw, category)
        if p:
            parts.append(p)
    return parts


async def sync_rakuten_category(
    category: str,
    max_pages: int = 10,
    existing_models: set[str] | None = None,
) -> list[dict]:
    """楽天市場から指定カテゴリのパーツを収集する"""
    keyword = RAKUTEN_CATEGORIES.get(category)
    if not keyword:
        return []

    all_parts: list[dict] = []
    seen_names: set[str] = set()
    consecutive_existing_pages = 0

    for page in range(1, max_pages + 1):
        html = await _fetch_page(keyword, page)
        if not html:
            break

        parts = _parse_and_normalize(html, category)
        if not parts:
            break

        new_on_page = 0
        for p in parts:
            key = f"{p['brand']}|{p['name'][:50]}"
            if key in seen_names:
                continue
            seen_names.add(key)

            if existing_models is not None:
                db_key = f"{p['brand']}|{p['model'][:80]}"
                if db_key in existing_models:
                    continue

            all_parts.append(p)
            new_on_page += 1

        # 連続5ページ全既存で早期終了
        if existing_models is not None and new_on_page == 0:
            consecutive_existing_pages += 1
            if consecutive_existing_pages >= 5:
                break
        else:
            consecutive_existing_pages = 0

        await asyncio.sleep(2.0)  # 楽天サーバー負荷軽減

    return all_parts


async def sync_all_rakuten(
    categories: list[str] | None = None,
    max_pages: int = 10,
    existing_models: set[str] | None = None,
) -> dict:
    """全カテゴリを楽天から収集"""
    targets = categories or list(RAKUTEN_CATEGORIES.keys())
    result = {}
    for cat in targets:
        parts = await sync_rakuten_category(cat, max_pages, existing_models)
        result[cat] = parts
        await asyncio.sleep(3)
    return result
