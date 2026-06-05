# 🤖 SUPER BOT

### Telegram бот + Веб-панель управления с ИИ (Mistral AI) и мониторингом macOS

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Telegram](https://img.shields.io/badge/Telegram-Bot-blue.svg)
![Mistral AI](https://img.shields.io/badge/Mistral-AI-purple.svg)
![Flask](https://img.shields.io/badge/Flask-Web-orange.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

---

## 📋 Оглавление

- [Возможности](#-возможности)
- [Технологии](#-технологии)
- [Установка](#-установка)
- [Настройка](#-настройка)
- [Запуск](#-запуск)
- [Команды бота](#-команды-бота)
- [Веб-панель](#-веб-панель)
- [API эндпоинты](#-api-эндпоинты)
- [Структура проекта](#-структура-проекта)
- [Часто задаваемые вопросы](#-часто-задаваемые-вопросы)
- [Лицензия](#-лицензия)

---

## ✨ Возможности

### 🧠 Искусственный интеллект
- **Текстовый чат** с Mistral AI (`mistral-small-latest`)
- **Анализ изображений** через Pixtral 12B Vision
- Поддержка русского языка
- Автоматическое разбиение длинных ответов

### 🖥️ Управление компьютером (macOS)

| Действие | Описание |
|----------|----------|
| 🔊 ГРОМЧЕ / ТИШЕ | Увеличение/уменьшение громкости |
| 🔇 МУТ / ВКЛ | Выключение/включение звука |
| 📸 СКРИНШОТ | Скриншот всего экрана |
| ✂️ ОБЛАСТЬ | Скриншот выбранной области |
| 🔒 БЛОК | Блокировка экрана |
| 💤 СОН | Режим сна |
| 🖥️ ДЕСКТОП | Показать рабочий стол |

### 📝 Персональные данные
- **Заметки** — создание, просмотр, удаление
- **Задачи** — с приоритетами (low/medium/high)
- **Закладки** — сохранение ссылок
- **Пароли** — безопасное хранение с шифрованием

### 💻 Мониторинг системы
- Загрузка CPU (проценты, частота, ядра)
- Использование RAM и Swap
- Состояние диска
- Сетевая активность
- Информация о батарее
- Список активных процессов

### 🌐 Веб-панель
- Живая статистика пользователей и команд
- Графики активности за 7 дней
- Топ популярных команд
- История последних команд
- Управление ПК из браузера
- Мониторинг системы в реальном времени
- Адаптивный дизайн, тёмная тема

---

## 🛠️ Технологии

| Компонент | Технология |
|-----------|------------|
| 🤖 Telegram Bot | `python-telegram-bot` |
| 🧠 ИИ | Mistral AI API |
| 🌐 Веб-сервер | Flask + SocketIO |
| 🗄️ База данных | SQLite3 |
| 🎨 Фронтенд | HTML5 + CSS3 + JavaScript |
| 📊 Графики | Chart.js |
| 🔐 Шифрование | Base64 + SHA256 |
| 🖥️ Управление ПК | AppleScript |
| 📦 Системная информация | psutil |

---

## 📦 Установка

### 1. Клонирование репозитория
```bash
git clone https://github.com/yourusername/super-bot.git
cd super-bot
```

### 2. Создание виртуального окружения
```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
```

### 3. Установка зависимостей
```bash
pip install -r requirements.txt
```

Или вручную:
```bash
pip install python-telegram-bot flask flask-socketio flask-cors requests psutil qrcode feedparser
```

---

## ⚙️ Настройка

### Получение токена Telegram бота
1. Откройте Telegram
2. Найдите **@BotFather**
3. Отправьте `/newbot`
4. Скопируйте полученный токен

### Получение API ключа Mistral AI
1. Зарегистрируйтесь на [console.mistral.ai](https://console.mistral.ai)
2. Перейдите в **"API Keys"**
3. Нажмите **"Create new key"**
4. Скопируйте ключ

### Настройка прав доступа на macOS
1. **Системные настройки** → **Конфиденциальность и безопасность**
2. **Специальные возможности** → Добавить терминал/Python
3. **Запись экрана** → Добавить терминал/Python

---

## 🚀 Запуск

```bash
python bot.py
```

### В фоновом режиме
```bash
nohup python bot.py > bot.log 2>&1 &
```

---

## 📱 Команды бота

| Кнопка | Действие |
|--------|----------|
| 🖥️ УПРАВЛЕНИЕ ПК | Открыть панель управления |
| 🧠 ИИ ЧАТ | Задать вопрос Mistral AI |
| 📷 АНАЛИЗ ФОТО | Отправить фото для анализа |
| 📝 ЗАМЕТКИ | Управление заметками |
| 📋 ЗАДАЧИ | Управление задачами |
| ⭐ ЗАКЛАДКИ | Управление закладками |
| 🔐 ПАРОЛИ | Менеджер паролей |
| 💻 СИСТЕМА | Мониторинг Mac |
| 🌐 ВЕБ ПАНЕЛЬ | Открыть веб-интерфейс |
| 📊 СТАТИСТИКА | Показать статистику |

### Команды
```
/addnote Заголовок | Текст    - Заметка
/mynotes                      - Список заметок
/delnote ID                   - Удалить заметку
/addtask задача | приоритет   - Задача
/mytasks                      - Список задач
/done ID                      - Выполнить задачу
/deltask ID                   - Удалить задачу
/addbookmark Название | URL   - Закладка
/mybookmarks                  - Список закладок
/delbookmark ID               - Удалить закладку
/savepass сервис | логин | пароль - Сохранить пароль
/mypass                       - Список сервисов
/getpass сервис               - Получить пароль
/delpass ID                   - Удалить пароль
```

---

## 🌐 Веб-панель

### Доступ
- **Локально:** `http://localhost:5000`
- **Сеть:** `http://[IP-адрес]:5000`

### API эндпоинты

| Эндпоинт | Метод | Описание |
|----------|-------|----------|
| `/api/stats` | GET | Статистика |
| `/api/commands` | GET | Последние команды |
| `/api/charts` | GET | Данные для графиков |
| `/api/system` | GET | Информация о системе |
| `/api/action` | POST | Выполнить действие |

### Пример API запроса
```bash
curl -X POST http://localhost:5000/api/action \
  -H "Content-Type: application/json" \
  -d '{"action":"volume_up"}'
```

---

## 📁 Структура проекта

```
super-bot/
├── bot.py                 # Главный файл
├── requirements.txt       # Зависимости
├── README.md              # Документация
├── .gitignore             # Исключения Git
└── ~/Desktop/СуперБот/    # Данные пользователя
    ├── superbot.db        # База данных
    ├── notes/             # Заметки
    ├── logs/              # Логи
    └── backups/           # Бэкапы
```

---

## ❓ Часто задаваемые вопросы

### ❔ Как получить API ключ Mistral AI?
Зарегистрируйтесь на [console.mistral.ai](https://console.mistral.ai). Бесплатный тариф даёт 2 запроса в минуту.

### ❔ Ошибка 429 (Too Many Requests)
Бесплатный тариф ограничен 2 запросами в минуту. Подождите немного.

### ❔ Скриншоты не работают
Предоставьте разрешение в **Системные настройки** → **Конфиденциальность** → **Запись экрана**.

### ❔ Веб-панель недоступна
Проверьте: запущен ли сервер, не блокирует ли фаервол, `curl http://localhost:5000/api/stats`

### ❔ Где хранятся данные?
`~/Desktop/СуперБот/superbot.db`

---

## 📄 Лицензия

MIT License

Copyright (c) 2026 Artem Sorokin

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

## 📧 Контакты

- **Автор:** Artem Sorokin
- **Telegram:** [@iamkinger]
- **GitHub:** [данный]

---

<div align="center">

### ⭐ Поставьте звезду на GitHub, если проект полезен! ⭐

</div>
```

---
