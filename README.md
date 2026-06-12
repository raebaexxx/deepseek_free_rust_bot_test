# DeepSeek Free Bot

Telegram бот на Python (aiogram 3.x), который работает через [FreeDeepseekAPI](https://github.com/ForgetMeAI/FreeDeepseekAPI) — локальный OpenAI-compatible прокси для DeepSeek Web Chat.

> Ранее проект был на Rust. Rust-код остаётся в `src/` для истории, но активная версия — Python.

---

## Архитектура

```
Telegram (User)  ←→  Bot (bot.py, aiogram)  ←→  FreeDeepseekAPI (localhost:9655)  ←→  chat.deepseek.com
```

---

## Возможности

- **Streaming** — бот выводит ответ по мере генерации (обновление каждые 400ms)
- **История диалога** — хранит последние 20 сообщений на чат
- **Выбор модели** — inline-клавиатура с 5 моделями
- **Команды**: `/start`, `/help`, `/reset`, `/model`
- **Обработка ошибок** — при сбое API бот показывает сообщение

---

## Команды

| Команда | Описание |
|---|---|
| `/start` | Приветствие |
| `/help` | Справка |
| `/reset` | Сбросить историю диалога |
| `/model` | Выбрать модель AI |

### Модели

| Модель | Reasoning | Search | Описание |
|---|---|---|---|
| `deepseek-chat` | — | — | Базовая (по умолчанию) |
| `deepseek-reasoner` | + | — | С режимом размышлений |
| `deepseek-chat-search` | — | + | С веб-поиском |
| `deepseek-expert` | — | — | Экспертный режим |
| `deepseek-v4-pro` | + | — | Expert + reasoning |

---

## Быстрый старт

### На VPS

```bash
cd ~/deepseek_free_rust_bot_test
git pull

# установить зависимости
pip install -r requirements.txt

# настроить .env
cp .env.example .env
nano .env   # вставить TELOXIDE_TOKEN

# запустить
python3 bot.py
```

Через tmux:

```bash
tmux new-session -d -s telegram-bot 'cd ~/deepseek_free_rust_bot_test && python3 bot.py'
```

### Локально

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # заполнить TELOXIDE_TOKEN
python3 bot.py
```

---

## Переменные окружения (`.env`)

| Переменная | Обязательная | По умолчанию | Описание |
|---|---|---|---|
| `TELOXIDE_TOKEN` | + | — | Токен Telegram бота |
| `DEEPSEEK_API_URL` | — | `http://localhost:9655/v1` | Адрес FreeDeepseekAPI |
| `DEFAULT_MODEL` | — | `deepseek-chat` | Модель по умолчанию |

---

## Структура

```
bot.py              # весь бот (один файл)
requirements.txt    # зависимости
.env.example        # пример конфига
src/                # Rust-версия (неактивна)
```

---

## FreeDeepseekAPI

На VPS без GUI авторизация делается на домашнем ПК:

```bash
# Домашний ПК
git clone https://github.com/ForgetMeAI/FreeDeepseekAPI.git
cd FreeDeepseekAPI
npm run auth   # войти в DeepSeek через Chrome
```

Файл `deepseek-auth.json` скопировать на VPS:

```bash
scp deepseek-auth.json user@vps:/opt/FreeDeepseekAPI/
```

На VPS импортировать и запустить:

```bash
cd /opt/FreeDeepseekAPI
npm run auth:import -- --input ./deepseek-auth.json
NON_INTERACTIVE=1 npm start
```

---

## Лицензия

MIT
