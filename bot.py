import asyncio
import html
import logging
from typing import Optional

from telegram import (
    Chat,
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ChatMemberStatus, ParseMode, PollType
from telegram.error import Forbidden, TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
from database import Database
from questions_loader import QuestionsManager

logging.basicConfig(format="%(asctime)s - [%(levelname)s] - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

db = Database(config.MONGO_URI)
qm = QuestionsManager()

def get_job_name(chat_id: int) -> str:
    return f"quiz_job_{chat_id}"

def is_bot_owner(user_id: int) -> bool:
    """Strictly checks if the user is the Bot Owner (configured in SUPER_ADMIN_IDS)."""
    return user_id in config.SUPER_ADMIN_IDS

def schedule_job(app: Application, chat_id: int, minutes: int) -> None:
    if not app.job_queue:
        return
    name = get_job_name(chat_id)
    for j in app.job_queue.get_jobs_by_name(name):
        j.schedule_removal()
    app.job_queue.run_repeating(scheduled_callback, interval=minutes * 60, first=10, data=chat_id, name=name)

async def auto_recover_and_schedule(app: Application, chat: Chat) -> None:
    """Silently registers and starts auto-quiz for any active group."""
    if not chat or chat.type not in [Chat.GROUP, Chat.SUPERGROUP]:
        return
    job_name = get_job_name(chat.id)
    if app.job_queue and not app.job_queue.get_jobs_by_name(job_name):
        await db.register_or_update_chat(chat.id, chat.title or "Group", chat.type, is_active=True)
        settings = await db.get_chat_settings(chat.id)
        interval = settings["interval_minutes"] if settings else config.DEFAULT_QUIZ_INTERVAL_MINUTES
        schedule_job(app, chat.id, interval)
        logger.info(f"🔄 Auto-recovered and scheduled quiz for group: {chat.title} ({chat.id}) every {interval} mins")

async def group_activity_listener(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Background listener that wakes up auto-quiz on ANY activity in groups."""
    chat = update.effective_chat
    if chat and chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
        await auto_recover_and_schedule(context.application, chat)

async def send_quiz_to_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int, subject: Optional[str] = None) -> bool:
    try:
        served = await db.get_served_question_ids(chat_id)
        q_data, reset = qm.select_question(served, subject)
        if not q_data:
            return False
        if reset:
            await db.reset_served_questions_for_chat(chat_id)

        header = f"📚 [{q_data.get('subject', 'CA Foundation')}]"
        text = f"{header}\n\n{q_data['question']}"[:300]
        opts = [o[:100] for o in q_data["options"]]
        expl = (q_data.get("explanation") or "")[:200]

        await context.bot.send_poll(
            chat_id=chat_id,
            question=text,
            options=opts,
            type=PollType.QUIZ,
            correct_option_id=int(q_data["correct_option_id"]),
            is_anonymous=False,
            explanation=expl,
            open_period=None,
        )
        await db.record_served_question(chat_id, q_data["id"])
        return True
    except Forbidden:
        await db.set_chat_active_status(chat_id, False)
        return False
    except Exception as e:
        logger.error(f"Error sending quiz to {chat_id}: {e}")
        return False

async def scheduled_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.job and context.job.data:
        await send_quiz_to_chat(context, context.job.data)

async def chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    res = update.my_chat_member
    if not res:
        return
    chat, status = res.chat, res.new_chat_member.status
    if status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR]:
        await db.register_or_update_chat(chat.id, chat.title or "Group", chat.type, is_active=True)
        schedule_job(context.application, chat.id, config.DEFAULT_QUIZ_INTERVAL_MINUTES)
        await context.bot.send_message(
            chat.id,
            f"🎉 <b>CA Foundation Quiz Bot Activated!</b>\nAuto-posting every <b>{config.DEFAULT_QUIZ_INTERVAL_MINUTES} mins</b>.\nCommands: <code>/quiz</code>, <code>/report</code>, <code>/stats</code>",
            parse_mode=ParseMode.HTML,
        )
    elif status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
        await db.set_chat_active_status(chat.id, False)
        if context.job_queue:
            for j in context.job_queue.get_jobs_by_name(get_job_name(chat.id)):
                j.schedule_removal()

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    if chat:
        # Register user / group in database
        await db.register_or_update_chat(chat.id, chat.title or (user.full_name if user else "User"), chat.type)
        if update.message:
            bot_info = await context.bot.get_me()
            add_to_group_url = f"https://t.me/{bot_info.username}?startgroup=true"

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Me to Your Group", url=add_to_group_url)]
            ])

            user_name = user.first_name if (user and user.first_name) else "Student"
            safe_user_name = html.escape(user_name)

            welcome_text = (
                f"👋 <b>Hello {safe_user_name}!</b> 🎓\n\n"
                f"Welcome <b>{safe_user_name}</b> to the <b>CA Foundation Quiz Master Bot</b> — aapka daily practice partner\n\n"
                "⚡ <b>Quick Commands:</b>\n"
                "🎯 <code>/quiz</code> — Get an instant MCQ\n"
                "📊 <code>/stats</code> — View question bank stats\n"
                "⚠️ <code>/report &lt;reason&gt;</code> — Reply to any quiz to report an issue\n\n"
                "💡 <i>Tip: Is bot ko apne study group me add karein aur doston ke sath daily scheduled practice karein!</i>"
            )
            await update.message.reply_text(
                welcome_text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )

async def quiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat:
        await auto_recover_and_schedule(context.application, chat)
        subj = " ".join(context.args).strip() if context.args else None
        await send_quiz_to_chat(context, chat.id, subj)

# ----------------- STRICT BOT OWNER ONLY COMMANDS ----------------- #

async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Strictly Owner-Only command to broadcast message to all users & groups."""
    user = update.effective_user
    msg = update.message
    if not user or not is_bot_owner(user.id) or not msg:
        if msg:
            await msg.reply_text("⛔ Sirf Bot Owner hi broadcast bhej sakte hain.")
        return

    # Check if message is a reply or contains raw text
    replied = msg.reply_to_message
    raw_text = " ".join(context.args).strip() if context.args else None

    if not replied and not raw_text:
        await msg.reply_text(
            "📢 <b>Broadcast Usage:</b>\n\n"
            "1. <b>Text Broadcast:</b> <code>/broadcast Aapka message yahan likhein</code>\n"
            "2. <b>Media/Photo Broadcast:</b> Kisi bhi photo ya post ko <b>Reply</b> karke <code>/broadcast</code> likhein.",
            parse_mode=ParseMode.HTML,
        )
        return

    all_chats = await db.get_all_broadcast_chats()
    if not all_chats:
        await msg.reply_text("❌ Database me koi users ya groups nahi mile.")
        return

    progress_msg = await msg.reply_text(f"⏳ <b>Broadcasting to {len(all_chats)} chats...</b>", parse_mode=ParseMode.HTML)

    success_users = 0
    success_groups = 0
    failed_count = 0

    for item in all_chats:
        target_id = item["chat_id"]
        c_type = item.get("chat_type", "private")
        try:
            if replied:
                # Copy exact message (with media, caption, buttons etc.)
                await context.bot.copy_message(
                    chat_id=target_id,
                    from_chat_id=msg.chat.id,
                    message_id=replied.message_id,
                )
            else:
                # Send text message
                await context.bot.send_message(
                    chat_id=target_id,
                    text=raw_text,
                    parse_mode=ParseMode.HTML,
                )

            if c_type in ["group", "supergroup"]:
                success_groups += 1
            else:
                success_users += 1

            # Sleep slightly to prevent Telegram flood limits (max 30 msgs/sec)
            await asyncio.sleep(0.05)

        except Forbidden:
            failed_count += 1
            await db.set_chat_active_status(target_id, False)
        except Exception as e:
            failed_count += 1
            logger.warning(f"Broadcast failed for {target_id}: {e}")

    total_success = success_users + success_groups
    report_text = (
        "📢 <b>Broadcast Completed!</b>\n\n"
        f"✅ <b>Total Delivered:</b> <code>{total_success}</code> chats\n"
        f"• 👤 <b>Users (DMs):</b> <code>{success_users}</code>\n"
        f"• 👥 <b>Groups:</b> <code>{success_groups}</code>\n\n"
        f"❌ <b>Failed / Blocked:</b> <code>{failed_count}</code>"
    )
    await progress_msg.edit_text(report_text, parse_mode=ParseMode.HTML)

async def set_interval_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat, user = update.effective_chat, update.effective_user
    if not chat or not user or not is_bot_owner(user.id):
        if update.message:
            await update.message.reply_text("⛔ Sirf Bot Owner hi interval set kar sakte hain.")
        return

    if not context.args or not context.args[0].isdigit() or int(context.args[0]) < 1:
        if update.message:
            await update.message.reply_text("❌ Usage: <code>/set_interval 30</code>", parse_mode=ParseMode.HTML)
        return

    mins = int(context.args[0])
    await db.set_chat_interval(chat.id, mins)
    schedule_job(context.application, chat.id, mins)
    if update.message:
        await update.message.reply_text(f"✅ Auto-quiz interval updated to <b>{mins} minutes</b> for this group.", parse_mode=ParseMode.HTML)

async def stop_quiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat, user = update.effective_chat, update.effective_user
    if not chat or not user or not is_bot_owner(user.id):
        if update.message:
            await update.message.reply_text("⛔ Sirf Bot Owner hi auto-quiz pause kar sakte hain.")
        return

    await db.set_chat_active_status(chat.id, False)
    if context.job_queue:
        for j in context.job_queue.get_jobs_by_name(get_job_name(chat.id)):
            j.schedule_removal()
    if update.message:
        await update.message.reply_text("⏸️ Auto-quiz paused in this group by Bot Owner.", parse_mode=ParseMode.HTML)

async def start_quiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat, user = update.effective_chat, update.effective_user
    if not chat or not user or not is_bot_owner(user.id):
        if update.message:
            await update.message.reply_text("⛔ Sirf Bot Owner hi auto-quiz start kar sakte hain.")
        return

    settings = await db.get_chat_settings(chat.id)
    interval = settings["interval_minutes"] if settings else config.DEFAULT_QUIZ_INTERVAL_MINUTES

    await db.set_chat_active_status(chat.id, is_active=True)
    schedule_job(context.application, chat.id, interval)

    if update.message:
        await update.message.reply_text(
            f"▶️ <b>Auto-Quiz Resumed!</b>\nInterval: har <b>{interval} minutes</b>.",
            parse_mode=ParseMode.HTML,
        )

async def set_report_group_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user or not is_bot_owner(user.id):
        if update.message:
            await update.message.reply_text("⛔ Sirf Bot Owner hi Report Group set kar sakte hain.")
        return

    await db.set_setting("report_chat_id", str(chat.id))
    if update.message:
        await update.message.reply_text(
            f"🎯 <b>Report Group Configured Successfully!</b>\n\n"
            f"Ab sabhi groups ki reports sidha is group (<b>{html.escape(chat.title or 'This Group')}</b>) me aayengi.",
            parse_mode=ParseMode.HTML,
        )

async def reload_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not is_bot_owner(user.id):
        if update.message:
            await update.message.reply_text("⛔ Sirf Bot Owner hi questions reload kar sakte hain.")
        return

    success = qm.load_questions()
    if update.message:
        if success:
            await update.message.reply_text(f"✅ Questions reload ho gaye! Total count: <b>{len(qm.questions)}</b>", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text("❌ Error reloading questions file.", parse_mode=ParseMode.HTML)

# ----------------- PUBLIC STUDENT COMMANDS ----------------- #

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not chat:
        return
    
    stats = qm.get_stats()
    db_stats = await db.get_system_stats()
    served = await db.get_served_question_ids(chat.id)

    text = (
        "📊 <b>CA Foundation Quiz Master Stats</b>\n\n"
        "👥 <b>Bot Community:</b>\n"
        f"• 👤 <b>Total Users (DMs):</b> <code>{db_stats['total_users']}</code>\n"
        f"• 👥 <b>Total Groups:</b> <code>{db_stats['total_groups']}</code> (Active: <code>{db_stats['active_groups']}</code>)\n\n"
        "📚 <b>Question Bank:</b>\n"
        f"• 📝 <b>Total Questions:</b> <code>{stats['total']}</code>\n"
        f"• 🎯 <b>Served in this Chat:</b> <code>{len(served)}</code>"
    )
    if update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg:
        return

    replied = msg.reply_to_message
    if not replied or not replied.poll:
        await msg.reply_text(
            "⚠️ <b>Report karne ke liye:</b>\nJis Quiz Poll me galti hai, us message ko <b>Reply</b> karke <code>/report &lt;kya galti hai&gt;</code> likhein.",
            parse_mode=ParseMode.HTML,
        )
        return

    user = update.effective_user
    chat = update.effective_chat
    user_name = user.full_name if user else "Student"
    user_handle = f"@{user.username}" if (user and user.username) else f"ID: {user.id if user else 0}"
    chat_title = chat.title if chat and chat.title else "Private Chat"
    reason = " ".join(context.args).strip() if context.args else "No specific reason provided"

    question_text = replied.poll.question
    options_text = "\n".join([f"  {idx+1}. {opt.text}" for idx, opt in enumerate(replied.poll.options)])

    report_id = await db.add_report(
        chat_id=chat.id if chat else 0,
        chat_title=chat_title,
        user_id=user.id if user else 0,
        user_name=user_name,
        question_text=question_text,
        reason=reason,
    )

    alert_text = (
        f"🚨 <b>NEW QUESTION REPORT #{report_id}</b>\n\n"
        f"📍 <b>From Group:</b> {html.escape(chat_title)} (<code>{chat.id if chat else 0}</code>)\n"
        f"👤 <b>Reported By:</b> {html.escape(user_name)} ({html.escape(user_handle)})\n\n"
        f"❓ <b>Question:</b>\n<code>{html.escape(question_text)}</code>\n\n"
        f"📋 <b>Options:</b>\n{html.escape(options_text)}\n\n"
        f"💬 <b>Report Reason / Note:</b>\n<i>{html.escape(reason)}</i>"
    )

    report_chat_id = await db.get_setting("report_chat_id")

    sent_somewhere = False
    if report_chat_id:
        try:
            await context.bot.send_message(
                chat_id=int(report_chat_id),
                text=alert_text,
                parse_mode=ParseMode.HTML,
            )
            sent_somewhere = True
        except Exception as e:
            logger.error(f"Failed sending report to group {report_chat_id}: {e}")

    if not sent_somewhere:
        for admin_id in config.SUPER_ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=alert_text,
                    parse_mode=ParseMode.HTML,
                )
            except Exception as e:
                logger.warning(f"Could not send report to DM of admin {admin_id}: {e}")

    await msg.reply_text(
        "✅ <b>Shukriya!</b> Aapki report admin group me forward kar di gayi hai.",
        parse_mode=ParseMode.HTML,
    )

async def post_init(application: Application) -> None:
    await db.init_db()
    active_chats = await db.get_all_active_chats()
    logger.info(f"🔄 MongoDB loaded: {len(active_chats)} active groups found.")
    for row in active_chats:
        if row.get("chat_type") in ["group", "supergroup"]:
            schedule_job(application, row["chat_id"], row["interval_minutes"])

def main() -> None:
    app = ApplicationBuilder().token(config.BOT_TOKEN).post_init(post_init).build()
    
    # 1. Background Auto-Recovery Listener for ALL groups
    app.add_handler(MessageHandler(filters.ChatType.GROUPS, group_activity_listener), group=-1)

    # 2. Member join/leave updates
    app.add_handler(ChatMemberHandler(chat_member_update, ChatMemberHandler.MY_CHAT_MEMBER))
    
    # 3. Public Commands
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("quiz", quiz_cmd))
    app.add_handler(CommandHandler("report", report_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    
    # 4. Owner-Only Commands
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("set_interval", set_interval_cmd))
    app.add_handler(CommandHandler("stop_quiz", stop_quiz_cmd))
    app.add_handler(CommandHandler("start_quiz", start_quiz_cmd))
    app.add_handler(CommandHandler("set_report_group", set_report_group_cmd))
    app.add_handler(CommandHandler("reload", reload_cmd))
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
