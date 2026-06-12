# DeepSeek Free Bot

Telegram бот на Python (aiogram 3.x), который работает через [FreeDeepseekAPI](https://github.com/ForgetMeAI/FreeDeepseekAPI) — локальный прокси для DeepSeek Web Chat.

Бот поддерживает **streaming ответов**, **историю диалогов** (20 сообщений) и **выбор модели** через inline-клавиатуру.

---

## Содержание

- [Архитектура](#архитектура)
- [Подготовка](#подготовка)
    - [1. Получить токен Telegram бота](#1-получить-токен-telegram-бота)
    - [2. Установить Python и Git](#2-установить-python-и-git)
    - [3. Установить Node.js](#3-установить-nodejs)
- [Развёртывание бота](#развёртывание-бота)
    - [4. Клонировать репозиторий](#4-клонировать-репозиторий)
    - [5. Настроить виртуальное окружение](#5-настроить-виртуальное-окружение)
    - [6. Настроить .env](#6-настроить-env)
    - [7. Запустить бота](#7-запустить-бота)
- [FreeDeepseekAPI](#freedeepseekapi)
    - [Авторизация на домашнем ПК](#авторизация-на-домашнем-пк)
    - [Перенос на VPS](#перенос-на-vps)
    - [Запуск FreeDeepseekAPI на VPS](#запуск-freedeepseekapi-на-vps)
- [Запуск через tmux](#запуск-через-tmux)
- [Автозапуск при перезагрузке](#автозапуск-при-перезагрузке)
- [Команды бота](#команды-бота)
- [Переменные окружения](#переменные-окружения)
- [Возможности](#возможности)
- [Решение проблем](#решение-проблем)
- [Структура проекта](#структура-проекта)

---

## Архитектура

```
Telegram (User)
    ↕ HTTPS (Long Polling)
Telegram Bot API
    ↕
aiogram Bot (Python, bot.py)
    ↕ HTTP (localhost:9655)
FreeDeepseekAPI (Node.js, proxy)
    ↕ HTTPS
chat.deepseek.com
```

Оба сервиса (бот + FreeDeepseekAPI) запускаются на одном сервере.

---

## Подготовка

### 1. Получить токен Telegram бота

1. Открой [@BotFather](https://t.me/BotFather) в Telegram
2. Отправь `/newbot`
3. Введи имя бота (например, `My DeepSeek Bot`)
4. Введи username (например, `my_deepseek_bot`)
5. Скопируй токен вида `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`
6. Он понадобится в файле `.env`

### 2. Установить Python и Git

**VPS (Ubuntu/Debian):**

```bash
apt update && apt install -y python3 python3-pip python3-venv git
```

**VPS (CentOS/Fedora):**

```bash
dnf install -y python3 python3-pip git
```

Проверь версию:

```bash
python3 --version   # нужно 3.10+
git --version
```

### 3. Установить Node.js

FreeDeepseekAPI требует Node.js 18+.

**VPS (Ubuntu/Debian):**

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs
node --version   # нужно 18+
```

---

## Развёртывание бота

### 4. Клонировать репозиторий

```bash
git clone https://github.com/raebaexxx/deepseek_free_rust_bot_test.git
cd deepseek_free_rust_bot_test
```

### 5. Настроить виртуальное окружение

**VPS / Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

После установки зависимостей **не закрывай терминал** — venv должен быть активным (`(venv)` в начале строки).

### 6. Настроить .env

```bash
cp .env.example .env
nano .env
```

Вставь свои значения:

```env
TELOXIDE_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
DEEPSEEK_API_URL=http://localhost:9655/v1
DEFAULT_MODEL=deepseek-chat
```

- `TELOXIDE_TOKEN` — токен от BotFather (обязательно)
- `DEEPSEEK_API_URL` — адрес FreeDeepseekAPI. Если он на том же сервере — менять не нужно
- `DEFAULT_MODEL` — модель по умолчанию

### 7. Запустить бота

Простой запуск (пока не закроешь терминал):

```bash
source venv/bin/activate
python3 bot.py
```

Бот начнёт принимать сообщения. Напиши `/start` в Telegram. Если FreeDeepseekAPI ещё не запущен — бот запустится, но API будет недоступен (ошибка).

---

## FreeDeepseekAPI

Бот сам по себе бесполезен без FreeDeepseekAPI — именно он обеспечивает доступ к DeepSeek бесплатно.

### Авторизация на домашнем ПК

На домашнем компьютере (где есть браузер с GUI):

```bash
git clone https://github.com/ForgetMeAI/FreeDeepseekAPI.git
cd FreeDeepseekAPI
npm install
npm run auth
```

Откроется меню:
1. Выбери пункт `1`
2. Откроется Chrome — войди в аккаунт DeepSeek
3. Отправь любое сообщение (просто `ok`)
4. Вернись в терминал и нажми Enter

После успешной авторизации появится файл `deepseek-auth.json`.

### Перенос на VPS

Скопируй файл на сервер:

```bash
scp deepseek-auth.json user@ваш-vps:/opt/FreeDeepseekAPI/
```

### Запуск FreeDeepseekAPI на VPS

```bash
git clone https://github.com/ForgetMeAI/FreeDeepseekAPI.git /opt/FreeDeepseekAPI
cd /opt/FreeDeepseekAPI

# Если на VPS уже есть deepseek-auth.json:
npm run auth:import -- --input ./deepseek-auth.json
chmod 600 deepseek-auth.json

# Запуск
NON_INTERACTIVE=1 npm start
```

Сервер запустится на `http://localhost:9655`. Не закрывай этот терминал — или используй tmux (см. ниже).

---

## Запуск через tmux

Чтобы бот и FreeDeepseekAPI работали после закрытия SSH-сессии, используй tmux.

Установка tmux:

```bash
apt install -y tmux       # Ubuntu/Debian
dnf install -y tmux       # CentOS/Fedora
```

**Сессия 1 — FreeDeepseekAPI:**

```bash
tmux new-session -d -s deepseek-api \
    'cd /opt/FreeDeepseekAPI && NON_INTERACTIVE=1 npm start'
```

**Сессия 2 — Telegram Bot:**

```bash
cd ~/deepseek_free_rust_bot_test
tmux new-session -d -s telegram-bot \
    'source venv/bin/activate && python3 bot.py'
```

**Полезные команды tmux:**

```bash
tmux ls                                    # список сессий
tmux attach -t telegram-bot                # подключиться к логам бота
tmux attach -t deepseek-api                # подключиться к логам API
tmux kill-session -t telegram-bot          # остановить бота
tmux kill-session -t deepseek-api          # остановить API
```

Чтобы открепиться от сессии: `Ctrl+B, D`

---

## Автозапуск при перезагрузке

Если VPS перезагрузится, tmux-сессии пропадут. Чтобы они запускались автоматически, добавь в crontab:

```bash
crontab -e
```

Добавь строки:

```
@reboot tmux new-session -d -s deepseek-api 'cd /opt/FreeDeepseekAPI && NON_INTERACTIVE=1 npm start'
@reboot tmux new-session -d -s telegram-bot 'cd /home/user/deepseek_free_rust_bot_test && /home/user/deepseek_free_rust_bot_test/venv/bin/python3 /home/user/deepseek_free_rust_bot_test/bot.py'
```

**Важно:** замени `/home/user/` на реальный путь к проекту на твоём сервере (команда `pwd` покажет текущую директорию).

---

## Команды бота

| Команда | Описание |
|---|---|
| `/start` | Приветствие |
| `/help` | Справка |
| `/reset` | Сбросить историю диалога |
| `/model` | Выбрать модель AI через inline-клавиатуру |

После выбора `/model` появится клавиатура с кнопками:

| Модель | Reasoning | Search | Описание |
|---|---|---|---|
| `deepseek-chat` | — | — | Базовая, быстрая (по умолчанию) |
| `deepseek-reasoner` | + | — | С режимом размышлений (R1) |
| `deepseek-chat-search` | — | + | С веб-поиском |
| `deepseek-expert` | — | — | Экспертный режим |
| `deepseek-v4-pro` | + | — | Expert + reasoning |

---

## Переменные окружения

Файл `.env` в корне проекта:

| Переменная | Обязательная | По умолчанию | Описание |
|---|---|---|---|
| `TELOXIDE_TOKEN` | **Да** | — | Токен Telegram бота от @BotFather |
| `DEEPSEEK_API_URL` | Нет | `http://localhost:9655/v1` | Адрес FreeDeepseekAPI |
| `DEFAULT_MODEL` | Нет | `deepseek-chat` | Модель при первом запуске |

---

## Возможности

- **Streaming** — бот выводит ответ по мере генерации, обновляя сообщение каждые 400ms
- **История диалога** — хранит последние 20 сообщений на чат, чтобы DeepSeek помнил контекст
- **5 моделей** — переключение через `/model` без перезапуска
- **Сброс истории** — `/reset` очищает контекст
- **Обработка ошибок** — если API недоступен или вернул ошибку, бот покажет сообщение
- **Нет компиляции** — Python работает сразу, никаких бинарников

---

## Решение проблем

### Бот не отвечает

1. Проверь, что `.env` существует и `TELOXIDE_TOKEN` правильный
2. Проверь, что FreeDeepseekAPI запущен: `curl http://localhost:9655/`
3. Проверь логи бота: `tmux attach -t telegram-bot`
4. Перезапусти бота: `tmux kill-session -t telegram-bot` и запусти заново

### FreeDeepseekAPI не отвечает

```bash
curl http://localhost:9655/v1/models          # список моделей
curl http://localhost:9655/health             # статус сервера
cd /opt/FreeDeepseekAPI && npm run doctor     # диагностика
```

Если `doctor` показывает ошибки — повтори `npm run auth` на домашнем ПК и обнови `deepseek-auth.json` на VPS.

### deepseek-auth.json устарел

Повтори авторизацию на домашнем ПК:

```bash
cd FreeDeepseekAPI
npm run auth
```

Затем снова скопируй `deepseek-auth.json` на VPS.

### Ошибка "API error 401"

Сессия DeepSeek истекла. Обнови `deepseek-auth.json` через `npm run auth` на домашнем ПК.

---

## Структура проекта

```
bot.py              # Telegram бот (весь код в одном файле)
requirements.txt    # Python-зависимости (aiogram, httpx, python-dotenv)
.env.example        # шаблон конфигурации
.env                # конфигурация (не попадает в git)
src/                # Rust-версия (неактивна, для истории)
```

---

## Лицензия

MIT
