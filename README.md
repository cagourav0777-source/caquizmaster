# 🎓 CA Foundation Quiz Master Bot

> An automated, high-speed Telegram Quiz Bot built for **CA Foundation** students with MongoDB cloud persistence, auto-scheduling, and question error reporting.

---

## ✨ Features

- ⏰ **Auto-Quiz in Groups:** Automated quizzes at custom intervals (e.g. every 30m).
- 🔄 **Zero-Repeat Engine:** Never repeats a question in a group until all are completed.
- 📚 **Multi-File Bank:** Automatically reads all `.txt` files from the `data/` folder.
- ⚡ **Instant Quiz (`/quiz`):** Get on-demand MCQs anytime.
- ⚠️ **Error Reporting (`/report`):** Students reply to any quiz poll to report issues directly to admins.
- 📢 **Broadcast (`/broadcast`):** Owner can broadcast text and media posts to all users & groups.
- 📊 **Live Stats (`/stats`):** Real-time count of total users, active groups, and question bank stats.
- ☁️ **MongoDB Persistence:** No data loss on cloud restarts/redeployments.

---

## 🚀 How to Deploy (Render)

1. Fork or upload this repository to your **GitHub**.
2. Go to **[Render.com](https://render.com)** ➡️ Click **New +** ➡️ **Background Worker** (or Web Service).
3. Connect your GitHub repository.
4. Set the following build settings:
   - **Environment:** `Python`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
5. Add the **Environment Variables** (see below) and click **Deploy**!

---

## 🔑 Environment Variables

| Key | Description | Example |
| :--- | :--- | :--- |
| `BOT_TOKEN` | Telegram Bot Token from @BotFather | `123456789:ABCdef...` |
| `MONGO_URI` | MongoDB Atlas Connection String | `mongodb+srv://user:pass@cluster...` |
| `SUPER_ADMIN_IDS` | Telegram User IDs of Owners (comma-separated) | `8679167067,8709673662` |
| `DEFAULT_QUIZ_INTERVAL_MINUTES` | Auto-quiz timer in minutes | `30` |

---

## 📖 Commands

- `/start` — Start bot & get group add button
- `/quiz` — Get an instant MCQ
- `/stats` — View live community & quiz stats
- `/report <reason>` — Reply to any quiz to report a mistake
- `/broadcast <msg>` — Broadcast announcement (Admin Only)
- `/set_interval <mins>` — Change group quiz interval (Admin Only)
- `/start_quiz` / `/stop_quiz` — Resume or pause auto-quizzes (Admin Only)
- `/reload` — Reload question files without restart (Admin Only)

---

## 👨‍💻 Developer

Developed with ❤️ by **ɢᴏᴜʀᴀᴠ**  
📩 Telegram: [@Cagourav_18](https://t.me/Cagourav_18)
