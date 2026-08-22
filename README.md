# 🎓 CA Foundation Quiz Master Bot

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Telegram Bot API](https://img.shields.io/badge/Telegram-Bot%20API%20v20%2B-2CA5E0.svg?logo=telegram&logoColor=white)](https://core.telegram.org/bots/api)
[![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-47A248.svg?logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![Render](https://img.shields.io/badge/Render-Deploy%20Ready-black.svg?logo=render&logoColor=white)](https://render.com/)

An automated, asynchronous Telegram Quiz Bot built for **CA Foundation** aspirants. It delivers chapter-wise multiple-choice questions (MCQs) with detailed explanations, automated study group scheduling, anti-duplication tracking, student report handling, and cloud persistence with MongoDB.

---

## ✨ Features

- ⏰ **Automated Group Quizzes:** Automatically posts quizzes in Telegram study groups at customizable intervals (e.g., every 30 mins).
- 🔄 **Anti-Duplication Engine:** Ensures questions are never repeated in a group until the entire question bank is exhausted, followed by a clean auto-reset.
- 📚 **Multi-File Question Bank:** Automatically scans and loads all `.txt` and `.json` files inside the `data/` folder.
- ⚡ **Instant Quizzes (`/quiz`):** Students can request on-demand MCQs anytime.
- ⚠️ **Interactive Question Reporting (`/report`):** Students can reply to any quiz poll to report errors, which are instantly forwarded to the admin group.
- 👥 **Personalized Greetings & 1-Click Group Add:** Custom welcome message displaying the user's name with an inline button to easily add the bot to study groups.
- 📢 **Owner Broadcast System (`/broadcast`):** Allows Bot Owners to broadcast text, photos, and formatted announcements to all private users and groups.
- 📊 **Community & Bank Analytics (`/stats`):** Displays real-time counts of active users, total groups, and question bank statistics.
- ☁️ **Zero Data-Loss with MongoDB:** Cloud database integration ensures active chats and question records persist across server restarts and deployments.
- 🔄 **Zero-Touch Auto-Recovery:** Listens for group activity to automatically register and schedule existing groups without requiring manual removal and re-addition.

---

## 📁 Project Structure

```text
├── bot.py                # Main bot application, handlers, and scheduler
├── database.py           # Async MongoDB database engine (Motor)
├── config.py             # Environment variables & constants
├── questions_loader.py   # Multi-file question parser & manager
├── data/                 # Directory containing chapter-wise question files
│   └── questions.txt     # Human-readable question bank
├── requirements.txt      # Python dependencies
├── Procfile              # Worker command for cloud platforms
├── render.yaml           # Render deployment configuration
└── README.md             # Project documentation
