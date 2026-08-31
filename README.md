# 🎓 CA Foundation Quiz Master Bot

> A professional, feature-rich Telegram Quiz Bot designed for **CA Foundation** students, featuring automated quizzes, timed mock tests with leaderboards, MongoDB cloud persistence, and comprehensive question management.

---

## ✨ Features

### 🎯 Core Features
- ⏰ **Auto-Scheduled Quizzes** — Automated quizzes at customizable intervals in groups
- 🏆 **Interactive Mock Tests** — Timed mock tests with real-time leaderboards
- 🔄 **Smart Question Engine** — Never repeats questions until all are completed
- 📚 **Multi-Source Question Bank** — Supports Chapters, PYQs, and Accounts T/F modules
- ⚡ **Instant Quiz Mode** — Get on-demand MCQs anytime with `/quiz`
- 📊 **Live Statistics** — Real-time user, group, and question bank analytics

### 🛠️ Administrative Features
- ⚠️ **Error Reporting System** — Students can report question issues directly to admins
- 📢 **Broadcast System** — Send announcements to all users and groups
- 🔧 **Flexible Configuration** — Customizable quiz intervals and test parameters
- ☁️ **Cloud Persistence** — MongoDB-backed data storage (survives restarts)
- 🗑️ **Auto-Cleanup** — Automatic deletion of 24-hour old quiz polls

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10 or higher
- MongoDB Atlas account (free tier works)
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)

### Installation

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd caquizmaster-main
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   
   Create a `.env` file in the project root:
   ```env
   BOT_TOKEN=your_telegram_bot_token_here
   MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/quiz_bot_db
   SUPER_ADMIN_IDS=123456789,987654321
   DEFAULT_QUIZ_INTERVAL_MINUTES=30
   ```

4. **Run the bot**
   ```bash
   python bot.py
   ```

---

## 🔧 Environment Variables

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `BOT_TOKEN` | Telegram Bot Token from @BotFather | `123456789:ABCdef...` | ✅ Yes |
| `MONGO_URI` | MongoDB Atlas Connection String | `mongodb+srv://user:pass@cluster...` | ✅ Yes |
| `SUPER_ADMIN_IDS` | Comma-separated Telegram User IDs of bot owners | `8679167067,8709673662` | ✅ Yes |
| `DEFAULT_QUIZ_INTERVAL_MINUTES` | Auto-quiz interval in minutes | `30` | ❌ No (default: 30) |
| `QUIZ_OPEN_PERIOD_SECONDS` | How long quiz polls stay open | `60` | ❌ No (default: 60) |

---

## 📖 User Commands

### For All Users
- `/start` — Start the bot and view welcome message
- `/quiz` — Get an instant MCQ question
- `/mocktest` — Start an interactive timed mock test
- `/stoptest` — Cancel ongoing mock test
- `/stats` — View question bank and community statistics
- `/report <reason>` — Reply to any quiz poll to report an issue

### For Group Admins
- `/start_autoquiz` — Enable automatic periodic quizzes
- `/stop_autoquiz` — Disable automatic quizzes
- `/set_interval <minutes>` — Change auto-quiz interval

### For Bot Owners Only
- `/broadcast <message>` — Send broadcast to all users/groups
- `/reload` — Reload question files without restarting

---

## 🏗️ Project Structure

```
caquizmaster-main/
├── bot.py                  # Main bot logic and handlers
├── config.py               # Configuration and environment variables
├── database.py             # MongoDB operations and queries
├── questions_loader.py     # Question parsing and management
├── data/                   # Question bank files
│   ├── Chapter1.txt        # Economics chapters (1-10)
│   ├── accounts_tf.txt     # Accounts True/False questions
│   └── *.txt               # Past papers and exam questions
├── requirements.txt        # Python dependencies
├── Procfile               # Render.com deployment config
├── render.yaml            # Render service configuration
└── README.md              # Documentation
```

---

## 📝 Question File Format

Questions should be in `.txt` files in the `data/` folder:

```
Q: What is the capital of France?
A) London
B) Berlin
C) Paris
D) Madrid
Ans: C
Exp: Paris is the capital and largest city of France.

---

Q: Which planet is known as the Red Planet?
A) Venus
B) Mars
C) Jupiter
D) Saturn
Ans: B
Exp: Mars appears red due to iron oxide on its surface.
```

**Format Rules:**
- Questions separated by `---` or `===`
- Question starts with `Q:` or `Question:`
- Options labeled `A)`, `B)`, `C)`, `D)`
- Answer marked with `Ans:` or `Answer:`
- Optional explanation with `Exp:` or `Explanation:`

---

## 🌐 Deploy to Render.com

1. **Fork/Upload this repository to GitHub**

2. **Create a new Background Worker on Render**
   - Go to [Render.com](https://render.com)
   - Click **New +** → **Background Worker**
   - Connect your GitHub repository

3. **Configure Build Settings**
   - **Environment:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`

4. **Add Environment Variables**
   - Add `BOT_TOKEN`, `MONGO_URI`, `SUPER_ADMIN_IDS` in the Render dashboard

5. **Deploy!** 🚀

---

## 🐛 Bug Fixes in This Version

### Critical Fixes
✅ Fixed `broadcast_cmd()` list.strip() error (lines 879, 883)  
✅ Fixed `get_default_database()` incorrect argument  
✅ Added exception handling to poll answer handler  
✅ Added validation for custom question count (max 200)  
✅ Fixed memory leak in `poll_to_mock_chat` dictionary  
✅ Added error logging for invalid question answers  

### Improvements
✅ Converted all Hindi text to professional English  
✅ Added attractive emojis throughout the interface  
✅ Extracted magic numbers to config constants  
✅ Improved error messages with clear formatting  
✅ Enhanced user experience with better visual structure  

---

## 🔒 Security Features

- ✅ HTML escaping for all user-generated content
- ✅ Permission checks for admin commands
- ✅ Rate limiting on broadcast operations
- ✅ Validation on all user inputs
- ✅ MongoDB connection with TLS/SSL

---

## 📊 Statistics

Track your bot's performance:
- Total registered users (DMs)
- Total groups (active and inactive)
- Questions served per chat
- Total questions in the database

---

## 👨‍💻 Developer

Developed with ❤️ by **Gourav**  
📩 Telegram: [@Cagourav_18](https://t.me/Cagourav_18)

---

## 📄 License

This project is open-source and available for educational purposes.

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📞 Support

For support, contact [@Cagourav_18](https://t.me/Cagourav_18) on Telegram.

---

**⭐ If you find this bot useful, please give it a star on GitHub!**
