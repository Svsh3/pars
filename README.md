# WB Parser Bot

Telegram-бот для парсинга товаров Wildberries. Принимает TXT файл со списком запросов или ссылок, возвращает Excel с TOP-5 товарами по каждому запросу.

## Установка

```bash
pip install -r requirements.txt
```

## Настройка

Задай переменные окружения:

```bash
export BOT_TOKEN="твой_токен_от_BotFather"
export BOT_PASSWORD="твой_пароль"   # default: wb2024
```

На Railway/Heroku — добавь эти переменные в настройках проекта.

## Запуск

```bash
python bot.py
```

## Формат TXT файла

Каждая строка — это одно из:

- Текстовый запрос: `беспроводные наушники`
- Ссылка поиска WB: `https://www.wildberries.ru/catalog/0/search.aspx?search=айфон`
- Прямая ссылка на товар: `https://www.wildberries.ru/catalog/123456789/detail.aspx`

Пример:
```
беспроводные наушники
кроссовки мужские
https://www.wildberries.ru/catalog/0/search.aspx?search=смартфон
https://www.wildberries.ru/catalog/187082527/detail.aspx
```

## Структура проекта

```
wb_parser_bot/
├── bot.py           # Telegram бот (aiogram v3)
├── wb_scraper.py    # Парсер WB API
├── excel_builder.py # Генерация Excel
├── requirements.txt
└── README.md
```

## Как работает

1. Пользователь авторизуется по паролю
2. Отправляет TXT файл
3. Бот парсит каждую строку параллельно (10 потоков)
4. Для каждого запроса получает TOP-5 товаров с WB API
5. Формирует Excel с группировкой по запросам
6. Отправляет файл пользователю
