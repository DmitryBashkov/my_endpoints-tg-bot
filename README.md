# my_endpoints Telegram ingest bot

Маленький отдельный Telegram-бот: принимает изображения (визитки, скриншоты email-подписей и т.п.),
извлекает контактные данные через vision-модель OpenRouter, показывает превью и **по подтверждению**
сохраняет контакт в [my_endpoints](https://ct.bshkv.ru) через REST API.

- Архитектура — самостоятельный микросервис (Docker)
- Доступ — по белому списку Telegram user_id
- Перед сохранением — всегда подтверждение

## Поток работы

1. `/start` — короткая инструкция.
2. `/health` — проверка my_endpoints и наличия ключей OpenRouter.
3. Пользователь шлёт фото/картинку.
4. Бот скачивает изображение, отправляет в OpenRouter vision, парсит JSON.
5. Из извлечённого строится канонический JSON-контакт (см. ниже).
6. Бот показывает превью с кнопками **✅ Сохранить / ❌ Отмена / 📄 JSON**.
7. По «Сохранить» — `POST {base}/api/v1/contacts` с телом `{"data": <contact>}`.

## Установка

### 1. Создать Telegram-бота
- Открыть [@BotFather](https://t.me/BotFather), команда `/newbot`.
- Скопировать токен → `TELEGRAM_BOT_TOKEN`.

### 2. Узнать свой Telegram user_id
- Написать [@userinfobot](https://t.me/userinfobot).
- Записать число в `TELEGRAM_ALLOWED_USER_IDS` (можно через запятую несколько).

### 3. OpenRouter
- Зарегистрироваться на [openrouter.ai](https://openrouter.ai), создать ключ → `OPENROUTER_API_KEY`.
- Выбрать vision-модель → `OPENROUTER_MODEL` (например `openai/gpt-4o-mini`,
  `anthropic/claude-3.5-sonnet`, `google/gemini-2.0-flash-001`).

### 4. my_endpoints
- `MY_ENDPOINTS_API_BASE_URL=https://ct.bshkv.ru` (или свой адрес).
- При необходимости — `MY_ENDPOINTS_BEARER_TOKEN`.

### 5. .env
```bash
cp .env.example .env
# заполнить переменные
```

## Запуск

```bash
docker compose up -d --build
docker compose logs -f
docker compose down
```

Без Docker:
```bash
pip install -r requirements.txt
python bot.py
```

## Безопасность

- Бот по умолчанию **fail-closed**: пустой `TELEGRAM_ALLOWED_USER_IDS` означает «никого не пускать».
- `.env` в `.gitignore` и `.dockerignore`.
- Контейнер запускается под непривилегированным пользователем.

## Канонический JSON-контакт

Бот строит объект формата:

```json
{
  "doc-type": "person",
  "created-date": "YYYY-MM-DD",
  "modified-date": "YYYY-MM-DD",
  "deleted": false,
  "known": true,
  "person": {
    "uuid": "",
    "origin": "telegram-image-ingest",
    "quick-notes": [{"date": "YYYY-MM-DD", "note": "..."}],
    "name": {"raw": [], "full_name": "", "first_name": "", "middle_name": "", "last_name": ""},
    "gender": "",
    "contact-details": {
      "raw": [],
      "phone": {"home": [], "mobile": [], "work": [], "emergency": [], "prefered": ""},
      "messengers": {"telegram": {"login": "", "phone": ""}, "whatsapp": {"phone": ""}}
    },
    "occupation": [{"last-date": "", "city": "", "country": "", "address": ""}],
    "first-met": {"date": "", "who": {"person-uuid": "", "full-name": ""}, "where": "", "context": ""},
    "jobs": [{"last-date": "", "company": {"organization-uuid": "", "organization-name": ""}, "position": "", "comments": ""}],
    "important-dates": [],
    "interests": [],
    "capabilities": [],
    "realated-persons": []
  }
}
```

Поля, для которых в схеме нет места (email, сайт, прочий распознанный текст), кладутся в
`person.contact-details.raw` как строки вида `email: ...`, `website: ...`.

## Структура

| Файл | Назначение |
|---|---|
| `bot.py` | Точка входа, обработчики Telegram |
| `config.py` | Загрузка переменных окружения |
| `contact_model.py` | Сборка канонического JSON-контакта |
| `openrouter_client.py` | Vision-запрос в OpenRouter |
| `my_endpoints_client.py` | Клиент REST API my_endpoints |
| `requirements.txt`, `Dockerfile`, `docker-compose.yml` | Сборка/запуск |
| `tests/` | Минимальные unit-тесты для маппинга |

## Диагностика

### `telegram.error.TimedOut` при старте

Бот падает с `telegram.error.TimedOut` внутри `Application.initialize → bot.get_me`,
если контейнер не может достучаться до `api.telegram.org`. Что проверить на VPS:

1. **Интернет и DNS:**
   ```bash
   docker compose exec bot sh -c "getent hosts api.telegram.org && \
     wget -qO- https://api.telegram.org/ >/dev/null && echo OK"
   ```
2. **Достижимость Telegram Bot API** (в РФ часто блокируется): если предыдущий
   шаг падает по таймауту, нужен прокси.
3. **Настроить прокси** в `.env`:
   ```env
   TELEGRAM_PROXY_URL=socks5://user:pass@proxy.example.com:1080
   # или http://user:pass@proxy.example.com:8080
   ```
   SOCKS-зависимости уже подключены в `requirements.txt`
   (`python-telegram-bot[socks]`).
4. Перезапустить:
   ```bash
   docker compose up -d --build
   docker compose logs -f
   ```

В логах при старте видно фактические таймауты и факт наличия прокси
(без учётных данных), например:

```
Telegram timeouts: connect=30.0s read=30.0s write=30.0s pool=30.0s; proxy=socks5://proxy.example.com:1080; get_updates_proxy=socks5://proxy.example.com:1080
```

Бот при сетевой ошибке старта **не выходит**, а повторяет попытку через
`TELEGRAM_STARTUP_RETRY_DELAY` секунд (по умолчанию 15).

## Тесты

```bash
python -m pytest -q
# или просто компиляция:
python -m py_compile bot.py config.py contact_model.py openrouter_client.py my_endpoints_client.py
```
