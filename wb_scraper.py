import requests
import random
import asyncio
import time
import re
from urllib.parse import urlparse, parse_qs, unquote
from concurrent.futures import ThreadPoolExecutor

# Большой пул User-Agent'ов для ротации
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
]


def get_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.wildberries.ru/",
        "Origin": "https://www.wildberries.ru",
    })
    return s


def extract_query_from_url(url: str) -> str | None:
    """Извлекает поисковый запрос из ссылки WB поиска.
    Поддерживает как обычные, так и процентно-закодированные URL.
    """
    try:
        # Декодируем URL если он закодирован дважды
        decoded_url = unquote(url)
        parsed = urlparse(decoded_url)
        params = parse_qs(parsed.query)
        # Поддерживаем оба варианта параметра
        query = params.get("search") or params.get("query")
        if query:
            return unquote(query[0])
    except Exception:
        pass
    return None


def extract_article_from_url(url: str) -> str | None:
    """Извлекает артикул товара из прямой ссылки WB."""
    try:
        # Паттерн: /catalog/123456789/detail.aspx или /catalog/123456789/
        match = re.search(r"/catalog/(\d+)", url)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None


def search_wb(query: str) -> list[dict]:
    """Поиск товаров по запросу через WB API. До 3 попыток с задержкой при 429."""
    url = "https://search.wb.ru/exactmatch/ru/common/v5/search"

    params = {
        "appType": 1,
        "curr": "rub",
        "dest": "-1257786",
        "query": query,
        "resultset": "catalog",
        "sort": "popular",
        "spp": 30,
        "suppressSpellcheck": "false",
        "lang": "ru",
    }

    for attempt in range(3):
        # Задержка растёт с каждой попыткой: 1-2с, 3-5с, 6-10с
        delay = random.uniform(1.0 + attempt * 2, 2.0 + attempt * 4)
        time.sleep(delay)

        session = get_session()
        try:
            r = session.get(url, params=params, timeout=15)

            if r.status_code == 429:
                print(f"[search_wb] 429 для '{query}', попытка {attempt + 1}/3, жду {delay:.1f}с...")
                continue

            r.raise_for_status()
            data = r.json()
            products = data.get("data", {}).get("products", [])

            out = []
            for p in products[:5]:
                price_raw = p.get("salePriceU") or p.get("priceU") or 0
                price = price_raw // 100
                article_id = p.get("id", "")
                out.append({
                    "query": query,
                    "name": p.get("name", "—"),
                    "brand": p.get("brand", "—"),
                    "price": price,
                    "url": f"https://www.wildberries.ru/catalog/{article_id}/detail.aspx"
                })
            return out

        except Exception as e:
            print(f"[search_wb] Ошибка для '{query}' (попытка {attempt + 1}/3): {e}")

    print(f"[search_wb] Все попытки исчерпаны для '{query}'")
    return []


def get_product_by_article(article: str, original_url: str) -> list[dict]:
    """Получает данные о конкретном товаре по артикулу через WB API."""
    session = get_session()

    # WB API для получения карточки товара
    # Определяем номер корзины (basket) по артикулу — стандартная логика WB
    art_int = int(article)
    if art_int <= 143:
        basket = "01"
    elif art_int <= 287:
        basket = "02"
    elif art_int <= 431:
        basket = "03"
    elif art_int <= 719:
        basket = "04"
    elif art_int <= 1007:
        basket = "05"
    elif art_int <= 1061:
        basket = "06"
    elif art_int <= 1115:
        basket = "07"
    elif art_int <= 1169:
        basket = "08"
    elif art_int <= 1313:
        basket = "09"
    elif art_int <= 1601:
        basket = "10"
    elif art_int <= 1655:
        basket = "11"
    elif art_int <= 1919:
        basket = "12"
    elif art_int <= 2045:
        basket = "13"
    elif art_int <= 2189:
        basket = "14"
    elif art_int <= 2405:
        basket = "15"
    elif art_int <= 2621:
        basket = "16"
    elif art_int <= 2837:
        basket = "17"
    else:
        basket = "18"

    vol = art_int // 100000
    part = art_int // 1000

    card_url = (
        f"https://basket-{basket}.wbbasket.ru/vol{vol}/part{part}/{article}/info/ru/card.json"
    )

    time.sleep(random.uniform(0.3, 1.0))

    try:
        r = session.get(card_url, timeout=15)
        r.raise_for_status()
        data = r.json()

        name = data.get("imt_name") or data.get("subj_name") or "—"
        brand = data.get("brand_name") or "—"

        # Цену берём через отдельный price API
        price = get_price_by_article(article)

        return [{
            "query": original_url,
            "name": name,
            "brand": brand,
            "price": price,
            "url": f"https://www.wildberries.ru/catalog/{article}/detail.aspx"
        }]
    except Exception as e:
        print(f"[get_product_by_article] Ошибка для артикула {article}: {e}")
        return []


def get_price_by_article(article: str) -> int:
    """Получает цену товара через WB price API."""
    session = get_session()
    url = f"https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&nm={article}"

    try:
        r = session.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        products = data.get("data", {}).get("products", [])
        if products:
            p = products[0]
            price_raw = p.get("salePriceU") or p.get("priceU") or 0
            return price_raw // 100
    except Exception:
        pass
    return 0


def process_line(line: str) -> list[dict]:
    """Определяет тип строки и запускает нужный парсер."""
    line = line.strip()

    if not line:
        return []

    # Это ссылка WB?
    if "wildberries.ru" in line or "wb.ru" in line:
        # Ссылка поиска?
        query = extract_query_from_url(line)
        if query:
            return search_wb(query)

        # Прямая ссылка на товар?
        article = extract_article_from_url(line)
        if article:
            return get_product_by_article(article, line)

        # Неизвестный формат ссылки — пропускаем
        print(f"[process_line] Не удалось распознать ссылку: {line}")
        return []

    # Просто текстовый запрос
    return search_wb(line)


async def process_queries(queries: list[str]) -> list[dict]:
    """Параллельно обрабатывает все строки из файла."""
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=3)  # 3 потока — WB не банит

    tasks = [
        loop.run_in_executor(executor, process_line, q)
        for q in queries
    ]

    results = await asyncio.gather(*tasks)

    merged = []
    for r in results:
        merged.extend(r)

    return merged
