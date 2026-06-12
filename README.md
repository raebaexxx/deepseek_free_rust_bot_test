# DeepSeek Free Rust Bot

Telegram бот на Rust, который работает через [FreeDeepseekAPI](https://github.com/ForgetMeAI/FreeDeepseekAPI) — локальный OpenAI-compatible прокси для DeepSeek Web Chat.

Бот поддерживает **streaming ответов**, **историю диалогов**, **выбор модели** и **inline-клавиатуру**.

---

## Архитектура

```
Telegram (User)
    ↕ HTTPS (Long Polling)
Telegram Bot API
    ↕
Teloxide Bot (Rust, localhost:8080)
    ↕ HTTP (localhost:9655)
FreeDeepseekAPI (Node.js)
    ↕ WebSocket / HTTPS
chat.deepseek.com
```

Оба сервиса запускаются на одном VPS и общаются через localhost.

---

## Возможности

-   **Streaming** — бот выводит ответ по мере генерации (обновление каждые 400ms)
-   **История диалога** — хранит последние 20 сообщений на один чат
-   **Выбор модели** — inline-клавиатура с 5 моделями
-   **Сброс истории** — команда `/reset`
-   **Обработка ошибок** — при сбое API бот показывает сообщение об ошибке
-   **Логирование** — через `tracing` с поддержкой `RUST_LOG`

---

## Команды

| Команда | Описание |
|---|---|
| `/start` | Приветствие, список команд |
| `/help` | Справка |
| `/reset` | Сбросить историю диалога для текущего чата |
| `/model` | Выбрать модель AI (inline-клавиатура) |

### Доступные модели

| Модель | Reasoning | Web Search | Описание |
|---|---|---|---|
| `deepseek-chat` | — | — | Базовая, быстрая (по умолчанию) |
| `deepseek-reasoner` | + | — | С режимом размышлений (R1) |
| `deepseek-chat-search` | — | + | С веб-поиском |
| `deepseek-expert` | — | — | Экспертный режим |
| `deepseek-v4-pro` | + | — | Expert + reasoning |

---

## Установка и настройка

### 1. Клонировать репозиторий

```bash
git clone https://github.com/raebaexxx/deepseek_free_rust_bot_test.git
cd deepseek_free_rust_bot_test
```

### 2. Настроить `.env`

```bash
cp .env.example .env
```

Отредактировать `.env`:

```env
TELOXIDE_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
DEEPSEEK_API_URL=http://localhost:9655/v1
DEFAULT_MODEL=deepseek-chat
```

- `TELOXIDE_TOKEN` — токен бота от [@BotFather](https://t.me/BotFather)
- `DEEPSEEK_API_URL` — адрес FreeDeepseekAPI (менять не нужно, если он на том же сервере)
- `DEFAULT_MODEL` — модель по умолчанию

### 3. Собрать

```bash
cargo build --release
```

Бинарник: `target/release/deepseek_free_rust_bot`

---

## Деплой на VPS

### Установка Rust (если нет)

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"
```

### Установка FreeDeepseekAPI

```bash
git clone https://github.com/ForgetMeAI/FreeDeepseekAPI.git /opt/FreeDeepseekAPI
cd /opt/FreeDeepseekAPI
npm run auth        # авторизация в DeepSeek (нужен GUI)
# После авторизации скопировать deepseek-auth.json на VPS
```

> Подробнее: [FreeDeepseekAPI — VPS / headless запуск](https://github.com/ForgetMeAI/FreeDeepseekAPI?tab=readme-ov-file#-vps--headless-%D0%B7%D0%B0%D0%BF%D1%83%D1%81%D0%BA)

### Запуск через tmux

**Сессия 1 — FreeDeepseekAPI:**

```bash
tmux new-session -d -s deepseek-api \
    'cd /opt/FreeDeepseekAPI && NON_INTERACTIVE=1 npm start'
```

**Сессия 2 — Telegram Bot:**

```bash
cd deepseek_free_rust_bot_test
tmux new-session -d -s telegram-bot \
    './target/release/deepseek_free_rust_bot'
```

### Автозапуск при перезагрузке (crontab)

```bash
crontab -e
```

Добавить:

```
@reboot tmux new-session -d -s deepseek-api 'cd /opt/FreeDeepseekAPI && NON_INTERACTIVE=1 npm start'
@reboot tmux new-session -d -s telegram-bot 'cd /home/user/deepseek_free_rust_bot_test && /home/user/deepseek_free_rust_bot_test/target/release/deepseek_free_rust_bot'
```

### Полезные tmux команды

```bash
tmux ls                            # список сессий
tmux attach -t telegram-bot        # подключиться к сессии бота
tmux attach -t deepseek-api        # подключиться к сессии API
tmux kill-session -t telegram-bot  # остановить сессию
Ctrl+B, D                          # открепиться от сессии
```

---

## Локальная разработка

### Запуск без FreeDeepseekAPI (тест структуры)

```bash
cargo check
```

### Запуск с FreeDeepseekAPI локально

```bash
# Терминал 1: FreeDeepseekAPI
cd /opt/FreeDeepseekAPI
NON_INTERACTIVE=1 npm start

# Терминал 2: бот
cd deepseek_free_rust_bot_test
cargo run
```

### Логи

Уровень логирования задаётся через `RUST_LOG`:

```bash
RUST_LOG=debug cargo run
```

По умолчанию: `info`.

---

## Переменные окружения

| Переменная | Обязательная | По умолчанию | Описание |
|---|---|---|---|
| `TELOXIDE_TOKEN` | + | — | Токен Telegram бота |
| `DEEPSEEK_API_URL` | — | `http://localhost:9655/v1` | Адрес FreeDeepseekAPI |
| `DEFAULT_MODEL` | — | `deepseek-chat` | Модель по умолчанию |
| `RUST_LOG` | — | `info` | Уровень логирования |

---

## Структура проекта

```
src/
├── main.rs           # Точка входа, создание Dispatcher
├── config.rs         # Загрузка .env
├── handler.rs        # Обработчики команд, сообщений, callback'ов
├── api_client.rs     # HTTP клиент к FreeDeepseekAPI (SSE streaming)
├── conversation.rs   # История диалогов (20 сообщений на чат)
└── model_state.rs    # Выбранная модель per-user
```

---

## Лицензия

MIT
