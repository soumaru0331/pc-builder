import httpx
import asyncio
from typing import Optional

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


async def fetch_html(url: str, timeout: int = 10) -> Optional[str]:
    try:
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=timeout) as client:
            r = await client.get(url)
            if r.status_code == 200:
                return r.text
    except Exception:
        pass
    return None


async def fetch_json(url: str, timeout: int = 10) -> Optional[dict]:
    try:
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=timeout) as client:
            r = await client.get(url)
            if r.status_code == 200:
                return r.json()
    except Exception:
        pass
    return None
