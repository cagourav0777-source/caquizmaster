import logging
from typing import Optional

from telegram import Chat, ChatMemberUpdated, Update
from telegram.constants import ChatMemberStatus, ParseMode, PollType
from telegram.error import Forbidden, TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
)

import config
from database import Database
from questions_loader import QuestionsManager

logging.basicConfig(format="%(asctime)s - [%(levelname)s] - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

db = Database(config.DB_PATH)
qm = QuestionsManager()

def get_job_name(chat_id: int) -> str:
    return f"quiz_job_{chat_id}"

async def is_admin(chat: Chat, user_id: int) -> bool:
    if user_id in config.SUPER_ADMIN_IDS or chat.type in [Chat.PRIVATE, Chat.SENDER]:
        return True
    try:
        m = await chat.get_member(user_id)
        return m.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception:
        return False

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
        logger.error(f"Error in {chat_id}: {e}")
        return False

async def scheduled_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.job and context.job.data:
        await send_quiz_to_chat(context, context.job.data)

def schedule_job(app: Application, chat_id: int, minutes: int) -> None:
    if not app.job_queue:
        return
    name = get_job_name(chat_id)
    for j in app.job_queue.get_jobs_by_name(name):
        j.schedule_removal()
    app.job_queue.run_repeating(scheduled_callback, interval=minutes * 60, first=10, data=chat_id, name=name)

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
            f"🎉 **CA Foundation Quiz Bot Activated!**\nAuto-posting every **{config.DEFAULT_QUIZ_INTERVAL_MINUTES} mins**.\nCommands: `/quiz`, `/set_interval <mins>`, `/stop_quiz`, `/report`",
            parse_mode=ParseMode.MARKDOWN,
        )
    elif status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
        await db.set_chat_active_status(chat.id, False)
        if context.job_queue:
            for j in context.job_queue.get_jobs_by_name(get_job_name(chat.id)):
                j.schedule_removal()

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat:
        await db.register_or_update_chat(chat.id, chat.title or "Chat", chat.type)
        if update.message:
            await update.message.reply_text(
                "👋 Welcome to **CA Foundation Quiz Bot**!\n\n"
                "• `/quiz` — Instant question\n"
                "• `/set_interval 30` — Change auto-timer\n"
                "• `/report <reason>` — Reply to any quiz to report a mistake\n"
                "• `/set_report_group` — Set this group to receive all error reports\n"
                "• `/stats` — Quiz stats",
                parse_mode=ParseMode.MARKDOWN,
            )

async def quiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat:
        await db.register_or_update_chat(chat.id, chat.title or "Chat", chat.type)
        subj = " ".join(context.args).strip() if context.args else None
        await send_quiz_to_chat(context, chat.id, subj)

async def set_interval_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat, user = update.effective_chat, update.effective_user
    if not chat or not user or not await is_admin(chat, user.id):
        if update.message:
            await update.message.reply_text("⛔ Only group admins can change interval.")
        return
    if not context.args or not context.args[0].isdigit() or int(context.args[0]) < 1:
        if update.message:
            await update.message.reply_text("❌ Usage: `/set_interval <minutes>` (e.g. `/set_interval 30`)", parse_mode=ParseMode.MARKDOWN)
        return
    mins = int(context.args[0])
    await db.set_chat_interval(chat.id, mins)
    schedule_job(context.application, chat.id, mins)
    if update.message:
        await update.message.reply_text(f"✅ Auto-quiz interval updated to **{mins} minutes**.", parse_mode=ParseMode.MARKDOWN)

async def stop_quiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat, user = update.effective_chat, update.effective_user
    if chat and user and await is_admin(chat, user.id):
        await db.set_chat_active_status(chat.id, False)
        if context.job_queue:
            for j in context.job_queue.get_jobs_by_name(get_job_name(chat.id)):
                j.schedule_removal()
        if update.message:
            await update.message.reply_text("⏸️ Auto-quiz paused in this group.", parse_mode=ParseMode.MARKDOWN)

# --- REPORT SYSTEM ---

async def set_report_group_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sets the current group as the dedicated report receiving channel."""
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return

    # Check if sender is admin
    if not await is_admin(chat, user.id):
        if update.message:
            await update.message.reply_text("⛔ Sirf admin hi is group ko Report Group bana sakte hain.")
        return

    await db.set_setting("report_chat_id", str(chat.id))
    if update.message:
        await update.message.reply_text(
            f"🎯 **Report Group Configured Successfully!**\n\n"
            f"Ab kisi bhi study group se jab koi student `/report` karega, wo report sidha is group (**{chat.title}**) me aayegi.",
            parse_mode=ParseMode.MARKDOWN,
        )

async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles student reporting an issue with a quiz."""
    msg = update.message
    if not msg:
        return

    replied = msg.reply_to_message
    if not replied or not replied.poll:
        await msg.reply_text(
            "⚠️ **Report karne ke liye:**\nJis Quiz Poll me galti hai, us message ko **Reply** karke `/report <kya galti hai>` likhein.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    user = update.effective_user
    chat = update.effective_chat
    user_name = user.full_name if user else "Student"
    user_handle = f"@{user.username}" if (user and user.username) else f"ID: `{user.id if user else 0}`"
    chat_title = chat.title if chat and chat.title else "Private Chat"
    reason = " ".join(context.args).strip() if context.args else "Galti report ki gayi hai (No reason specified)"

    question_text = replied.poll.question
    options_text = "\n".join([f"  {idx+1}. {opt.text}" for idx, opt in enumerate(replied.poll.options)])

    # Save to SQLite database
    report_id = await db.add_report(
        chat_id=chat.id if chat else 0,
        chat_title=chat_title,
        user_id=user.id if user else 0,
        user_name=user_name,
        question_text=question_text,
        reason=reason,
    )

    # Formatted Alert Message
    alert_text = (
        f"🚨 **NEW QUESTION REPORT #{report_id}**\n\n"
        f"📍 **From Group:** {chat_title} (`{chat.id if chat else 'N/A'}`)\n"
        f"👤 **Reported By:** {user_name} ({user_handle})\n\n"
        f"❓ **Question:**\n`{question_text}`\n\n"
        f"📋 **Options:**\n{options_text}\n\n"
        f"💬 **Report Reason / Note:**\n_{reason}_"
    )

    # Check if a dedicated report group is set
    report_chat_id = await db.get_setting("report_chat_id")

    sent_somewhere = False
    if report_chat_id:
        try:
            await context.bot.send_message(
                chat_id=int(report_chat_id),
                text=alert_text,
                parse_mode=ParseMode.MARKDOWN,
            )
            sent_somewhere = True
        except Exception as e:
            logger.error(f"Failed sending report to report group {report_chat_id}: {e}")

    # Fallback to Super Admin DMs if no group is configured or if sending failed
    if not sent_somewhere:
        for admin_id in config.SUPER_ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=alert_text,
                    parse_mode=ParseMode.MARKDOWN,
                )
            except Exception as e:
                logger.warning(f"Could not send report to DM of admin {admin_id}: {e}")

    await msg.reply_text(
        "✅ **Shukriya!** Aapki report admin group me forward kar di gayi hai. Hum is question ko jald verify karenge.",
        parse_mode=ParseMode.MARKDOWN,
    )

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not chat:
        return
    stats = qm.get_stats()
    served = await db.get_served_question_ids(chat.id)
    text = f"📊 **CA Foundation Bank Stats**\n• Total Questions: **{stats['total']}**\n• Served in this Group: **{len(served)}**"
    if update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def post_init(application: Application) -> None:
    await db.init_db()
    for row in await db.get_all_active_chats():
        schedule_job(application, row["chat_id"], row["interval_minutes"])

def main() -> None:
    app = ApplicationBuilder().token(config.BOT_TOKEN).post_init(post_init).build()
    app.add_handler(ChatMemberHandler(chat_member_update, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("quiz", quiz_cmd))
    app.add_handler(CommandHandler("set_interval", set_interval_cmd))
    app.add_handler(CommandHandler("stop_quiz", stop_quiz_cmd))
    app.add_handler(CommandHandler("set_report_group", set_report_group_cmd))
    app.add_handler(CommandHandler("report", report_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
