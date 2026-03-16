"""
wb_scraper.py — обход защиты Wildberries
Имитирует поведение реального браузера:
  - Полный набор заголовков Chrome
  - Сессионные куки (берём с главной страницы)
  - Случайные задержки между запросами
  - Автоматический retry при ошибках
  - Ротация User-Agent
"""

import time
import random
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)

# ── Пул реалистичных User-Agent строк (Chrome/Firefox/Edge) ──────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]


def _make_session() -> requests.Session:
    """
    Создаёт сессию с:
    - случайным User-Agent
    - полным набором заголовков как у Chrome
    - автоматическим retry (3 попытки)
    - реалистичными TLS-параметрами
    """
    session = requests.Session()

    ua = random.choice(USER_AGENTS)

    # Полный набор заголовков реального Chrome
    session.headers.update({
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Cache-Control": "max-age=0",
        "DNT": "1",
    })

    # Retry стратегия: 3 попытки с паузой
    retry = Retry(
        total=3,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


def _warm_up_session(session: requests.Session):
    """
    «Прогрев» сессии — сначала заходим на главную страницу WB
    чтобы получить настоящие сессионные куки, как делает браузер.
    """
    try:
        # Шаг 1: главная страница — получаем базовые куки
        session.headers.update({
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
        })
        session.get("https://www.wildberries.ru/", timeout=10)
        _human_delay(0.8, 1.8)

        # Шаг 2: имитируем переход на страницу поиска
        session.headers.update({
            "Referer": "https://www.wildberries.ru/",
            "Sec-Fetch-Site": "same-origin",
        })
        session.get("https://www.wildberries.ru/catalog/0/search.aspx", timeout=10)
        _human_delay(0.5, 1.2)

    except Exception as e:
        log.warning(f"Warm-up failed (non-critical): {e}")


def _human_delay(min_s: float = 0.5, max_s: float = 2.0):
    """Случайная задержка, имитирующая время реакции человека."""
    time.sleep(random.uniform(min_s, max_s))


def _build_api_headers(session: requests.Session) -> dict:
    """Заголовки для обращения к search API (отличаются от браузерных)."""
    return {
        **session.headers,
        "Accept": "*/*",
        "Referer": "https://www.wildberries.ru/",
        "Origin": "https://www.wildberries.ru",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "cross-site",
        "X-Requested-With": "XMLHttpRequest",
    }


# ── Главная функция ───────────────────────────────────────────────────────────

# Глобальная сессия — переиспользуем между запросами
_session: requests.Session | None = None
_session_created_at: float = 0
SESSION_TTL = 600  # пересоздаём сессию каждые 10 минут


def _get_session() -> requests.Session:
    global _session, _session_created_at
    now = time.time()
    if _session is None or (now - _session_created_at) > SESSION_TTL:
        log.info("Creating new WB session...")
        _session = _make_session()
        _warm_up_session(_session)
        _session_created_at = now
        log.info("Session ready ✓")
    return _session


def search_wb(query: str, top_n: int = 5) -> list[dict]:
    """
    Ищет товары на WB по запросу, возвращает топ-N результатов.

    Возвращает список словарей:
      {query, name, seller, price, url}
    """
    session = _get_session()

    url = "https://search.wb.ru/exactmatch/ru/common/v5/search"
    params = {
        "appType":           "1",
        "curr":              "rub",
        "dest":              "-1257786",
        "query":             query,
        "resultset":         "catalog",
        "sort":              "popular",
        "spp":               "30",
        "suppressSpellcheck": "false",
        "lang":              "ru",
    }

    api_headers = _build_api_headers(session)

    # Несколько попыток с нарастающей задержкой
    for attempt in range(3):
        try:
            if attempt > 0:
                wait = 2 ** attempt + random.uniform(0.5, 1.5)
                log.info(f"Retry {attempt} for '{query}', waiting {wait:.1f}s")
                time.sleep(wait)
            else:
                # Небольшая пауза перед каждым запросом
                _human_delay(0.3, 0.9)

            resp = session.get(
                url,
                params=params,
                headers=api_headers,
                timeout=15,
            )

            # 429 = Too Many Requests — ждём дольше
            if resp.status_code == 429:
                wait = 5 + random.uniform(2, 5)
                log.warning(f"Rate limited! Waiting {wait:.1f}s...")
                time.sleep(wait)
                continue

            # 403 = сессия протухла — пересоздаём
            if resp.status_code == 403:
                log.warning("403 received, refreshing session...")
                global _session
                _session = None
                session = _get_session()
                continue

            resp.raise_for_status()
            data = resp.json()
            products = data.get("data", {}).get("products", [])

            results = []
            for item in products[:top_n]:
                price = (item.get("salePriceU") or item.get("priceU") or 0) // 100
                pid   = item.get("id", "")
                results.append({
                    "query":  query,
                    "name":   item.get("name", "—"),
                    "seller": item.get("supplier") or item.get("brand") or "—",
                    "price":  price,
                    "url":    f"https://www.wildberries.ru/catalog/{pid}/detail.aspx" if pid else "",
                })
            return results

        except requests.exceptions.Timeout:
            log.warning(f"Timeout for '{query}' (attempt {attempt+1})")
        except requests.exceptions.ConnectionError as e:
            log.warning(f"Connection error for '{query}': {e}")
        except Exception as e:
            log.warning(f"Unexpected error for '{query}': {e}")
            break

    log.error(f"All attempts failed for '{query}'")
    return []
