# 🐾 Cuteness AI Bot — Telegram бот для оценки милоты изображений

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![PyTorch](https://img.shields.io/badge/PyTorch-ML-orange?logo=pytorch)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Async](https://img.shields.io/badge/Asyncio-Aiogram-blueviolet)

## 📌 Описание проекта

**Cuteness AI Bot** — это учебный проект по машинному обучению, который умеет оценивать "милоту" изображений 🐶🐱 и выдавать процент «cuteness».  
В основе — **MobileNetV3**, дообученная на кастомном датасете с помощью PyTorch.  
Бот интегрирован с Telegram и может:

- 📸 Принимать фото от пользователей
- 📊 Оценивать их милоту в процентах
- 🏆 Формировать **топ милейших картинок**
- 🚫 Отсеивать NSFW с помощью NudeNet
- 🗄 Хранить данные в PostgreSQL
- ⚡ Работать быстро благодаря PyVips и асинхронным очередям

💡 Результаты можно использовать в алгоритмах или через API для других приложений.

---

## 🔗 Полезные ссылки

- 🤖 **Бот в Telegram**: [@cutecheckbot](https://t.me/cutecheckbot)
- 📢 **Telegram-канал проекта**: [Cuteness AI News](https://t.me/bloomofficialyt)
- 💬 **Discord-сервер**: [Вступить в комьюнити](https://discord.gg/n89PDURbTg)

---

## ⚙️ Технологии

- **Python** 3.10+
- [Aiogram](https://docs.aiogram.dev/) — асинхронный Telegram API
- [PyTorch](https://pytorch.org/) — обучение модели
- [Torchvision](https://pytorch.org/vision/stable/index.html) — MobileNetV3 + аугментации
- [NudeNet](https://github.com/notAI-tech/NudeNet) — NSFW фильтр
- [PyVips](https://libvips.github.io/pyvips/) — генерация изображений
- **PostgreSQL** — база данных
- **FastAPI** — API для интеграций

---

## 📦 Установка и запуск

```bash
# Клонируем репозиторий
git clone https://github.com/Read1dno/cuteness-ai-bot.git
cd cuteness-ai-bot

# Устанавливаем зависимости
pip install -r requirements.txt

# Меняем .env файл с переменными окружения
# Запускаем бота
python main.py
```
## 🔑 Переменные окружения (.env)

```
BOT_TOKEN=Токен Telegram бота
DATABASE_URL=URL для подключения к PostgreSQL
ADMIN_ID=ID администратора
ADMIN_PANEL_PASSWORD=Пароль для панели модерации
STORAGE_CHAT_ID=ID чата для хранения изображений
```

## 📄 License
This project is licensed under the MIT License.  
See the [LICENSE](https://github.com/Read1dno/ExternalAutoWallCS2/blob/main/LICENSE) file for details.
