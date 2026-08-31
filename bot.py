import asyncio
import datetime
import html
import logging
import os
import time
from typing import Any, Dict, List, Optional

from telegram import (
    Chat,
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    PollAnswer,
    Update,
)
from telegram.constants import ChatMemberStatus, ParseMode, PollType
from telegram.error import Forbidden, TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PollAnswerHandler,
    filters,
)

import config
from database import Database
from questions_loader import QuestionsManager

logging.basicConfig(format="%(asctime)s - [%(levelname)s] - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

db = Database(config.MONGO_URI)
qm = QuestionsManager()

active_mock_tests: Dict[int, Dict[str, Any]] = {}
mock_setup_state: Dict[int, Dict[str, Any]] = {}
poll_to_mock_chat: Dict[str, int] = {}
import_sessions: Dict[int, Dict[str, Any]] = {}


def get_job_name(chat_id: int) -> str:
    return f"quiz_job_{chat_id}"

def get_mock_job_name(chat_id: int) -> str:
    return f"mock_next_job_{chat_id}"

def is_bot_owner(user_id: int) -> bool:
    return user_id in config.SUPER_ADMIN_IDS

async def is_admin_or_owner(chat: Chat, user_id: int) -> bool:
    if is_bot_owner(user_id) or chat.type in [Chat.PRIVATE, Chat.SENDER]:
        return True
    try:
        m = await chat.get_member(user_id)
        return m.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception:
        return False

# ----------------- REGULAR AUTO-QUIZ SYSTEM (NO TIMER) ----------------- #

def schedule_job(app: Application, chat_id: int, minutes: int) -> None:
    if not app.job_queue:
        return
    name = get_job_name(chat_id)
    for j in app.job_queue.get_jobs_by_name(name):
        j.schedule_removal()
    app.job_queue.run_repeating(scheduled_callback, interval=minutes * 60, first=config.INITIAL_QUIZ_DELAY_SECONDS, data=chat_id, name=name)

async def group_activity_listener(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat and chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
        settings = await db.get_chat_settings(chat.id)
        if not settings:
            await db.register_or_update_chat(chat.id, chat.title or "Group", chat.type, is_active=False)

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

        correct_id = int(q_data.get("correct_option_id", 0))
        if correct_id < 0 or correct_id >= len(opts):
            correct_id = 0

        msg = await context.bot.send_poll(
            chat_id=chat_id,
            question=text,
            options=opts,
            type=PollType.QUIZ,
            correct_option_id=correct_id,
            is_anonymous=False,
            explanation=expl,
            open_period=None,
        )

        if msg and msg.poll:
            await db.record_served_question(chat_id, q_data["id"])
            await db.save_active_poll(
                poll_id=msg.poll.id,
                chat_id=chat_id,
                message_id=msg.message_id,
            )
        return True
    except Forbidden:
        await db.set_chat_active_status(chat_id, False)
        return False
    except Exception as e:
        logger.error(f"Error sending quiz to {chat_id}: {e}")
        return False

async def scheduled_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.job and context.job.data:
        chat_id = context.job.data
        if chat_id in active_mock_tests:
            return
        await send_quiz_to_chat(context, chat_id)

async def cleanup_expired_quizzes_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        expired = await db.get_expired_polls(hours=config.QUIZ_AUTO_DELETE_HOURS)
        for item in expired:
            try:
                await context.bot.delete_message(chat_id=item["chat_id"], message_id=item["message_id"])
            except Exception:
                pass
            finally:
                await db.remove_active_poll(item["poll_id"])
        if expired:
            logger.info(f"🧹 Auto-cleaned {len(expired)} expired quizzes (>{config.QUIZ_AUTO_DELETE_HOURS}h old).")
    except Exception as e:
        logger.error(f"Error during quiz auto-delete cleanup: {e}")

# ----------------- 🎯 SUBJECT PORTAL & MOCK TEST MENUS ----------------- #

def get_subject_portal_keyboard() -> InlineKeyboardMarkup:
    """Main Subject Selection Portal."""
    acc_count = len(qm.get_accounts_questions())
    acc_label = f"📊 Accounts T/F ({acc_count} Qs)" if acc_count > 0 else "📊 Accounts T/F"

    quant_count = len(qm.get_quant_questions())
    quant_label = f"🧮 Quantitative Aptitude ({quant_count} Qs)" if quant_count > 0 else "🧮 Quantitative Aptitude (Coming Soon)"

    keyboard = [
        [InlineKeyboardButton("📈 Business Economics", callback_data="msub_economics")],
        [InlineKeyboardButton(acc_label, callback_data="msub_accounts")],
        [InlineKeyboardButton(quant_label, callback_data="msub_quant")],
        [InlineKeyboardButton("❌ Cancel Setup", callback_data="mch_cancel")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_accounts_keyboard() -> InlineKeyboardMarkup:
    """Builds Accounts True/False Module Selection Keyboard."""
    mod_count = qm.get_total_count_for_target("accounts_tf")
    pyq_count = qm.get_total_count_for_target("accounts_tf_last_20_attempts")
    all_count = len(qm.get_accounts_questions())

    keyboard = [
        [InlineKeyboardButton(f"📖 Study Material / Module T/F ({mod_count} Qs)", callback_data="mch_accounts_tf")],
        [InlineKeyboardButton(f"📑 Past 20 Attempts Exam T/F ({pyq_count} Qs)", callback_data="mch_accounts_tf_last_20_attempts")],
        [InlineKeyboardButton(f"🎯 Grand Mix (All {all_count} T/F Qs)", callback_data="mch_accounts_all")],
        [
            InlineKeyboardButton("⬅️ Back to Subjects", callback_data="mportal_back"),
            InlineKeyboardButton("❌ Cancel", callback_data="mch_cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_quant_keyboard() -> InlineKeyboardMarkup:
    """🎯 NEW: Builds Quantitative Aptitude Module Selection Keyboard."""
    all_quant = qm.get_quant_questions()
    total_count = len(all_quant)

    keyboard = []

    # Show individual quant files if available
    quant_files = []
    for src in qm.quant_sources:
        q_list = qm.questions_by_source.get(src, [])
        if q_list:
            title = qm.format_source_title(src)
            quant_files.append((src, title, len(q_list)))

    if quant_files:
        for src, title, count in quant_files[:10]:  # Limit to 10 files
            keyboard.append([InlineKeyboardButton(f"📐 {title} ({count} Qs)", callback_data=f"mch_{src}")])

        if total_count > 0:
            keyboard.append([InlineKeyboardButton(f"🎯 All Quant Questions ({total_count} Qs)", callback_data="mch_quant_all")])
    else:
        keyboard.append([InlineKeyboardButton("ℹ️ No Quant files found", callback_data="mch_cancel")])

    keyboard.append([
        InlineKeyboardButton("⬅️ Back to Subjects", callback_data="mportal_back"),
        InlineKeyboardButton("❌ Cancel", callback_data="mch_cancel"),
    ])
    return InlineKeyboardMarkup(keyboard)

def get_economics_chapter_keyboard() -> InlineKeyboardMarkup:
    """Builds Economics Chapter Selection Keyboard."""
    chapters = qm.get_available_chapters()
    keyboard = []
    row = []

    for src_key, full_title, count in chapters:
        short_title = full_title.split(":")[0] if ":" in full_title else full_title
        row.append(InlineKeyboardButton(f"📖 {short_title}", callback_data=f"mch_{src_key}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("📝 Exam Question Papers (PYQs)", callback_data="msub_pyqs")])
    keyboard.append([InlineKeyboardButton("🌟 Full Syllabus Mock Tests", callback_data="msub_full")])
    keyboard.append([
        InlineKeyboardButton("⬅️ Back to Subjects", callback_data="mportal_back"),
        InlineKeyboardButton("❌ Cancel", callback_data="mch_cancel"),
    ])
    return InlineKeyboardMarkup(keyboard)

def get_pyqs_keyboard() -> InlineKeyboardMarkup:
    """Builds PYQs Keyboard (Economics only)."""
    pyqs = qm.get_available_pyqs()
    keyboard = []

    if pyqs:
        for src_key, title, count in pyqs:
            keyboard.append([InlineKeyboardButton(f"📑 {title} ({count} Qs)", callback_data=f"mch_{src_key}")])
    else:
        keyboard.append([InlineKeyboardButton("ℹ️ No PYQ files found", callback_data="mch_cancel")])

    keyboard.append([
        InlineKeyboardButton("⬅️ Back to Economics", callback_data="msub_economics"),
        InlineKeyboardButton("❌ Cancel", callback_data="mch_cancel"),
    ])
    return InlineKeyboardMarkup(keyboard)

def get_count_keyboard(total_available: int, back_callback: str = "mback_to_topics") -> InlineKeyboardMarkup:
    presets = [40, 60, 80, 100]
    valid_presets = [p for p in presets if p < total_available]

    keyboard = []
    row = []

    for p in valid_presets:
        row.append(InlineKeyboardButton(f"{p} MCQs", callback_data=f"mcnt_{p}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton(f"🌟 All Available ({total_available} MCQs)", callback_data=f"mcnt_{total_available}")])
    keyboard.append([InlineKeyboardButton("✍️ Custom Number (Type Your Own)", callback_data="mcnt_custom")])
    keyboard.append([
        InlineKeyboardButton("⬅️ Back", callback_data=back_callback),
        InlineKeyboardButton("❌ Cancel", callback_data="mch_cancel"),
    ])
    return InlineKeyboardMarkup(keyboard)

def get_timer_keyboard() -> InlineKeyboardMarkup:
    timer_keyboard = [
        [InlineKeyboardButton("⏱️ 30 Seconds", callback_data="mtim_30"), InlineKeyboardButton("⏱️ 45 Seconds", callback_data="mtim_45")],
        [InlineKeyboardButton("⏱️ 60 Seconds", callback_data="mtim_60"), InlineKeyboardButton("⏱️ 80 Seconds", callback_data="mtim_80")],
        [InlineKeyboardButton("⏱️ 120 Seconds (2 min)", callback_data="mtim_120")],
        [
            InlineKeyboardButton("⬅️ Back", callback_data="mback_to_count"),
            InlineKeyboardButton("❌ Cancel", callback_data="mch_cancel"),
        ],
    ]
    return InlineKeyboardMarkup(timer_keyboard)

async def mocktest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user or not update.message:
        return

    if chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
        if not await is_admin_or_owner(chat, user.id):
            await update.message.reply_text(
                "⛔ <b>Permission Denied</b>\n\n"
                "<i>Only Group Administrators can initiate mock tests in groups. "
                "You can practice privately by messaging the bot directly!</i>",
                parse_mode=ParseMode.HTML,
            )
            return

    if chat.id in active_mock_tests:
        await update.message.reply_text(
            "⚠️ <b>Mock Test Already in Progress!</b>\n\n"
            "Please wait for the current test to conclude, or use <code>/stoptest</code> to cancel it.",
            parse_mode=ParseMode.HTML,
        )
        return

    mock_setup_state[chat.id] = {"user_id": user.id, "chat_id": chat.id, "waiting_custom": False}

    setup_text = (
        "🏆 <b>CA Foundation Mock Examination Portal</b> 🎓\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Welcome to your personalized mock test experience!\n\n"
        "📚 <b>Step 1:</b> Select Your Subject Below"
    )

    await update.message.reply_text(
        setup_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_subject_portal_keyboard(),
    )

async def mocktest_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return

    state = mock_setup_state.get(chat.id)
    if not state:
        await query.edit_message_text(
            "⚠️ <b>Session Expired</b>\n\n"
            "<i>Please start a new mock test with /mocktest</i>",
            parse_mode=ParseMode.HTML
        )
        return

    if chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
        if not await is_admin_or_owner(chat, user.id):
            await query.answer("⛔ Only Group Admins can configure mock tests in this group.", show_alert=True)
            return
    else:
        if state.get("user_id") != user.id:
            await query.answer("⛔ Only the user who initiated /mocktest can make selections.", show_alert=True)
            return

    data = query.data

    # Cancel
    if data == "mch_cancel":
        mock_setup_state.pop(chat.id, None)
        await query.edit_message_text(
            "❌ <b>Mock Test Setup Cancelled</b>\n\n"
            "<i>You can start a new test anytime with /mocktest</i>",
            parse_mode=ParseMode.HTML
        )
        return

    # Back to Main Subject Portal
    if data in ["mportal_back", "msub_back"]:
        state["waiting_custom"] = False
        await query.edit_message_text(
            "🏆 <b>CA Foundation Mock Examination Portal</b> 🎓\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Welcome to your personalized mock test experience!\n\n"
            "📚 <b>Step 1:</b> Select Your Subject Below",
            parse_mode=ParseMode.HTML,
            reply_markup=get_subject_portal_keyboard(),
        )
        return

    # 1. Business Economics Selected
    if data == "msub_economics":
        state["current_subject"] = "Economics"
        await query.edit_message_text(
            "📈 <b>Business Economics</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Choose your desired chapter or test category below:",
            parse_mode=ParseMode.HTML,
            reply_markup=get_economics_chapter_keyboard(),
        )
        return

    # 2. Accounts T/F Selected -> Show Accounts Sub-Menu
    if data == "msub_accounts":
        acc_questions = qm.get_accounts_questions()
        total_available = len(acc_questions)
        if total_available == 0:
            await query.answer("⚠️ No Accounts T/F questions found in data folder.", show_alert=True)
            return

        state["current_subject"] = "Accounts"
        await query.edit_message_text(
            "📊 <b>Accounts True / False</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Choose your desired practice category:",
            parse_mode=ParseMode.HTML,
            reply_markup=get_accounts_keyboard(),
        )
        return

    # 3. Quantitative Aptitude
    if data == "msub_quant":
        quant_questions = qm.get_quant_questions()
        total_available = len(quant_questions)
        if total_available == 0:
            await query.answer("ℹ️ No Quantitative Aptitude questions found. Upload files with 'maths', 'stats', or 'quant' in the filename!", show_alert=True)
            return

        state["current_subject"] = "Quantitative Aptitude"
        await query.edit_message_text(
            "🧮 <b>Quantitative Aptitude</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Choose your desired practice module:",
            parse_mode=ParseMode.HTML,
            reply_markup=get_quant_keyboard(),
        )
        return

    # Economics PYQs Sub-Menu
    if data == "msub_pyqs":
        await query.edit_message_text(
            "📑 <b>Past Examination Papers (PYQs)</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Select an official examination series to practice real exam questions:",
            parse_mode=ParseMode.HTML,
            reply_markup=get_pyqs_keyboard(),
        )
        return

    # Full Syllabus Sub-Menu
    if data == "msub_full":
        full_keyboard = [
            [InlineKeyboardButton("📚 Ch 1-10 Complete Bank", callback_data="mch_all_chapters")],
            [InlineKeyboardButton("📑 All Past Exam Papers & PYQs", callback_data="mch_all_pyqs")],
            [InlineKeyboardButton("🎯 Grand Mix (Chapters + PYQs)", callback_data="mch_all_mixed")],
            [
                InlineKeyboardButton("⬅️ Back to Economics", callback_data="msub_economics"),
                InlineKeyboardButton("❌ Cancel", callback_data="mch_cancel"),
            ],
        ]
        await query.edit_message_text(
            "🌟 <b>Full Syllabus Practice Mode</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Choose comprehensive practice across the entire syllabus:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(full_keyboard),
        )
        return

    # Chapter / Paper / Module Selected
    if data.startswith("mch_"):
        ch_key = data.replace("mch_", "")
        state["chapter_key"] = ch_key
        friendly_title = qm.format_source_title(ch_key)
        state["friendly_title"] = friendly_title
        total_available = qm.get_total_count_for_target(ch_key)
        state["total_available"] = total_available

        back_cb = "msub_accounts" if "accounts" in ch_key else "msub_economics"
        state["back_callback"] = back_cb

        await query.edit_message_text(
            f"🎯 <b>Mock Test Configuration</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📖 <b>Selected Module:</b>\n<code>{friendly_title}</code>\n\n"
            f"📊 <b>Available Questions:</b> <code>{total_available} MCQs</code>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔢 <b>Step 2:</b> Select Question Volume",
            parse_mode=ParseMode.HTML,
            reply_markup=get_count_keyboard(total_available, back_callback=back_cb),
        )
        return

    # Back to Count Screen
    if data == "mback_to_count":
        state["waiting_custom"] = False
        ch_key = state.get("chapter_key", "all_mixed")
        friendly_title = state.get("friendly_title", "Selected Module")
        total_available = state.get("total_available", qm.get_total_count_for_target(ch_key))
        back_cb = state.get("back_callback", "msub_economics")

        await query.edit_message_text(
            f"🎯 <b>Mock Test Configuration</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📖 <b>Selected Module:</b>\n<code>{friendly_title}</code>\n\n"
            f"📊 <b>Available Questions:</b> <code>{total_available} MCQs</code>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔢 <b>Step 2:</b> Select Question Volume",
            parse_mode=ParseMode.HTML,
            reply_markup=get_count_keyboard(total_available, back_callback=back_cb),
        )
        return

    # Custom Count Input
    if data == "mcnt_custom":
        state["waiting_custom"] = True
        friendly_title = state.get("friendly_title", "Selected Module")
        total_available = state.get("total_available", 100)
        max_allowed = min(total_available, config.MAX_QUESTIONS_PER_TEST)

        custom_keyboard = [
            [
                InlineKeyboardButton("⬅️ Back", callback_data="mback_to_count"),
                InlineKeyboardButton("❌ Cancel", callback_data="mch_cancel"),
            ]
        ]

        await query.edit_message_text(
            f"✍️ <b>Custom Question Volume Input</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📖 <b>Module:</b> <code>{friendly_title}</code>\n"
            f"📊 <b>Available MCQs:</b> <code>{total_available} Questions</code>\n"
            f"🔢 <b>Maximum Allowed:</b> <code>{max_allowed} Questions</code>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<i>Please send a message with the number of questions you want (1-{max_allowed}):</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(custom_keyboard),
        )
        return

    # Preset Count Selected
    if data.startswith("mcnt_"):
        count = int(data.replace("mcnt_", ""))
        state["count"] = count
        state["waiting_custom"] = False
        friendly_title = state.get("friendly_title", "Selected Module")

        await query.edit_message_text(
            f"🎯 <b>Mock Test Configuration</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📖 <b>Module:</b> <code>{friendly_title}</code>\n"
            f"📝 <b>Questions Selected:</b> <code>{count} MCQs</code>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "⏱️ <b>Step 3:</b> Select Time Limit Per Question",
            parse_mode=ParseMode.HTML,
            reply_markup=get_timer_keyboard(),
        )
        return

    # Timer Selected -> START TEST
    if data.startswith("mtim_"):
        seconds = int(data.replace("mtim_", ""))
        ch_key = state.get("chapter_key", "all_mixed")
        friendly_title = state.get("friendly_title", "Full Syllabus")
        count = state.get("count", 10)

        mock_setup_state.pop(chat.id, None)

        questions = qm.get_mocktest_questions(ch_key, count)
        if not questions:
            await query.edit_message_text(
                "❌ <b>No Questions Available</b>\n\n"
                "<i>No matching questions found for this module. Please try a different selection.</i>",
                parse_mode=ParseMode.HTML
            )
            return

        session = {
            "chat_id": chat.id,
            "chapter_key": ch_key,
            "friendly_title": friendly_title,
            "questions": questions,
            "total_questions": len(questions),
            "current_index": 0,
            "time_per_question": seconds,
            "scores": {},
            "current_poll_id": None,
            "question_start_time": 0.0,
        }
        active_mock_tests[chat.id] = session

        start_card = (
            "🚀 <b>Mock Test Starting Now!</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📑 <b>Module:</b> <code>{friendly_title}</code>\n"
            f"📝 <b>Questions:</b> <code>{len(questions)} MCQs</code>\n"
            f"⏱️ <b>Time Per Question:</b> <code>{seconds} seconds</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎯 <i>Get ready! First question arriving in 3 seconds...</i>\n\n"
            "💡 <b>Tip:</b> Answer each poll before the timer expires!"
        )

        await query.edit_message_text(start_card, parse_mode=ParseMode.HTML)
        context.application.job_queue.run_once(
            send_mocktest_question_job,
            when=config.MOCK_TEST_START_DELAY_SECONDS,
            data=chat.id,
            name=get_mock_job_name(chat.id),
        )


async def custom_count_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    msg = update.message
    if not chat or not user or not msg or not msg.text:
        return

    state = mock_setup_state.get(chat.id)
    if not state or not state.get("waiting_custom"):
        if chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
            await group_activity_listener(update, context)
        return

    if state.get("user_id") != user.id and not await is_admin_or_owner(chat, user.id):
        return

    text_input = msg.text.strip()
    total_available = state.get("total_available", 100)
    max_allowed = min(total_available, config.MAX_QUESTIONS_PER_TEST)  # Maximum from config

    if not text_input.isdigit():
        await msg.reply_text(
            f"❌ <b>Invalid Input</b>\n\n"
            f"Please enter a valid number between <code>1</code> and <code>{max_allowed}</code>.",
            parse_mode=ParseMode.HTML
        )
        return

    num = int(text_input)
    if num < 1 or num > max_allowed:
        await msg.reply_text(
            f"❌ <b>Out of Range</b>\n\n"
            f"Please enter a number between <code>1</code> and <code>{max_allowed}</code>.\n"
            f"<i>Maximum {max_allowed} questions allowed per test session.</i>",
            parse_mode=ParseMode.HTML
        )
        return

    state["count"] = num
    state["waiting_custom"] = False
    friendly_title = state.get("friendly_title", "Selected Module")

    await msg.reply_text(
        f"🎯 <b>Mock Test Configuration</b>\n\n"
        f"📖 <b>Module:</b> <code>{friendly_title}</code>\n"
        f"📝 <b>Questions Selected:</b> <code>{num} MCQs</code>\n\n"
        "⏱️ <b>Select Time Limit Per Question:</b>\n"
        "Choose your desired countdown timer:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_timer_keyboard(),
    )


async def send_mocktest_question_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = context.job.data
    session = active_mock_tests.get(chat_id)
    if not session:
        return

    idx = session["current_index"]
    total = session["total_questions"]

    if idx >= total:
        await finish_mock_test(context, chat_id)
        return

    q_data = session["questions"][idx]
    timer_sec = session["time_per_question"]

    header = f"🏆 [Mock Test: Question {idx+1}/{total}]"
    text = f"{header}\n\n{q_data['question']}"[:300]
    opts = [o[:100] for o in q_data["options"]]
    expl = (q_data.get("explanation") or "")[:200]

    correct_id = int(q_data.get("correct_option_id", 0))
    if correct_id < 0 or correct_id >= len(opts):
        correct_id = 0

    try:
        msg = await context.bot.send_poll(
            chat_id=chat_id,
            question=text,
            options=opts,
            type=PollType.QUIZ,
            correct_option_id=correct_id,
            is_anonymous=False,
            explanation=expl,
            open_period=timer_sec,
        )

        if msg and msg.poll:
            session["current_poll_id"] = msg.poll.id
            session["question_start_time"] = time.time()
            poll_to_mock_chat[msg.poll.id] = chat_id
            session["current_index"] += 1

            next_delay = timer_sec + 2
            context.application.job_queue.run_once(
                send_mocktest_question_job,
                when=next_delay,
                data=chat_id,
                name=get_mock_job_name(chat_id),
            )
    except Exception as e:
        logger.error(f"Error sending mock question in {chat_id}: {e}")
        await finish_mock_test(context, chat_id)


async def poll_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    answer: PollAnswer = update.poll_answer
    if not answer or not answer.poll_id:
        return

    chat_id = poll_to_mock_chat.get(answer.poll_id)
    if not chat_id:
        return

    session = active_mock_tests.get(chat_id)
    if not session or session.get("current_poll_id") != answer.poll_id:
        return

    try:
        elapsed = max(0.1, time.time() - session.get("question_start_time", time.time()))
        curr_idx = session["current_index"] - 1
        if curr_idx < 0 or curr_idx >= len(session["questions"]):
            return

        q_data = session["questions"][curr_idx]
        correct_id = int(q_data.get("correct_option_id", 0))

        user = answer.user
        user_id = user.id
        user_name = user.full_name or "Student"
        user_handle = f"@{user.username}" if user.username else ""

        if user_id not in session["scores"]:
            session["scores"][user_id] = {
                "name": user_name,
                "handle": user_handle,
                "correct": 0,
                "total_time": 0.0,
                "attempts": 0,
            }

        user_score = session["scores"][user_id]
        user_score["attempts"] += 1

        if answer.option_ids and answer.option_ids[0] == correct_id:
            user_score["correct"] += 1
            user_score["total_time"] += elapsed
    except Exception as e:
        logger.error(f"Error processing poll answer: {e}")


async def finish_mock_test(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    session = active_mock_tests.pop(chat_id, None)
    if not session:
        return

    # Clean up poll tracking
    if session.get("current_poll_id") in poll_to_mock_chat:
        poll_to_mock_chat.pop(session["current_poll_id"], None)

    scores = session["scores"]
    total_q = session["total_questions"]
    friendly_title = session["friendly_title"]

    if not scores:
        empty_card = (
            "🏁 <b>Mock Test Completed</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📖 <b>Module:</b> <code>{friendly_title}</code>\n"
            f"📝 <b>Total Questions:</b> <code>{total_q} MCQs</code>\n"
            f"👥 <b>Participants:</b> <code>0 Students</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "ℹ️ <i>No participants recorded for this session. Start a new test anytime with /mocktest</i>"
        )
        await context.bot.send_message(chat_id=chat_id, text=empty_card, parse_mode=ParseMode.HTML)
        return

    sorted_players = sorted(
        scores.values(),
        key=lambda x: (-x["correct"], x["total_time"] / max(1, x["correct"])),
    )

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    leaderboard_lines = []

    for rank, player in enumerate(sorted_players[:10]):
        medal = medals[rank] if rank < len(medals) else f"#{rank+1}"
        correct = player["correct"]
        avg_speed = player["total_time"] / max(1, correct) if correct > 0 else 0.0
        acc = round((correct / total_q) * 100)
        p_name = html.escape(player["name"])

        line = f"{medal} <b>{p_name}</b> — <b>{correct}/{total_q}</b> ({acc}%) • <i>{avg_speed:.1f}s avg</i>"
        leaderboard_lines.append(line)

    leaderboard_text = "\n".join(leaderboard_lines)

    final_msg = (
        "🏆 <b>CA FOUNDATION MOCK TEST LEADERBOARD</b> 🏆\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📖 <b>Module:</b> <code>{friendly_title}</code>\n"
        f"📝 <b>Total Questions:</b> <code>{total_q} MCQs</code>\n"
        f"👥 <b>Total Participants:</b> <code>{len(scores)}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{leaderboard_text}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎉 <b>Outstanding performance! Keep striving for excellence.</b>"
    )

    await context.bot.send_message(chat_id=chat_id, text=final_msg, parse_mode=ParseMode.HTML)


async def stoptest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user or not update.message:
        return

    if not await is_admin_or_owner(chat, user.id):
        await update.message.reply_text(
            "⛔ <b>Permission Denied</b>\n\n"
            "<i>Only Group Administrators or Bot Owner can stop an active mock test.</i>",
            parse_mode=ParseMode.HTML
        )
        return

    if chat.id in active_mock_tests:
        active_mock_tests.pop(chat.id, None)
        name = get_mock_job_name(chat.id)
        if context.job_queue:
            for j in context.job_queue.get_jobs_by_name(name):
                j.schedule_removal()
        await update.message.reply_text(
            "🛑 <b>Mock Test Stopped</b>\n\n"
            "<i>The active mock test has been cancelled successfully.</i>",
            parse_mode=ParseMode.HTML
        )
    else:
        mock_setup_state.pop(chat.id, None)
        await update.message.reply_text(
            "ℹ️ <b>No Active Test Found</b>\n\n"
            "<i>There is no mock test currently running in this chat.</i>",
            parse_mode=ParseMode.HTML
        )

# ----------------- AUTO-QUIZ CONTROLS ----------------- #

async def start_autoquiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user or not update.message:
        return

    if not await is_admin_or_owner(chat, user.id):
        await update.message.reply_text(
            "⛔ <b>Permission Denied</b>\n\n"
            "<i>Only Group Administrators or Bot Owner can start auto-quizzes.</i>",
            parse_mode=ParseMode.HTML
        )
        return

    settings = await db.get_chat_settings(chat.id)
    interval = settings["interval_minutes"] if settings else config.DEFAULT_QUIZ_INTERVAL_MINUTES

    await db.register_or_update_chat(chat.id, chat.title or "Group", chat.type, is_active=True)
    schedule_job(context.application, chat.id, interval)

    await update.message.reply_text(
        f"▶️ <b>Auto-Quiz Activated Successfully!</b>\n\n"
        f"📅 Questions will be posted every <b>{interval} minutes</b>\n\n"
        f"<b>Available Commands:</b>\n"
        f"• <code>/stop_autoquiz</code> — Pause auto-quizzes\n"
        f"• <code>/set_interval &lt;minutes&gt;</code> — Change interval\n"
        f"• <code>/quiz</code> — Get instant on-demand quiz",
        parse_mode=ParseMode.HTML,
    )

async def stop_autoquiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user or not update.message:
        return

    if not await is_admin_or_owner(chat, user.id):
        await update.message.reply_text(
            "⛔ <b>Permission Denied</b>\n\n"
            "<i>Only Group Administrators or Bot Owner can stop auto-quizzes.</i>",
            parse_mode=ParseMode.HTML
        )
        return

    await db.set_chat_active_status(chat.id, is_active=False)
    job_name = get_job_name(chat.id)
    if context.job_queue:
        for j in context.job_queue.get_jobs_by_name(job_name):
            j.schedule_removal()

    await update.message.reply_text(
        "⏸️ <b>Auto-Quiz Paused</b>\n\n"
        "Automatic periodic questions have been stopped for this group.\n\n"
        "<b>Quick Actions:</b>\n"
        "• <code>/quiz</code> — Get instant on-demand quiz\n"
        "• <code>/mocktest</code> — Start a timed mock test\n"
        "• <code>/start_autoquiz</code> — Resume auto-quizzes",
        parse_mode=ParseMode.HTML,
    )

# ----------------- STANDARD EVENT & ADMIN HANDLERS ----------------- #

async def chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    res = update.my_chat_member
    if not res:
        return
    chat, status = res.chat, res.new_chat_member.status
    if chat.type not in [Chat.GROUP, Chat.SUPERGROUP]:
        return

    if status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR]:
        await db.register_or_update_chat(chat.id, chat.title or "Group", chat.type, is_active=False)
        await context.bot.send_message(
            chat.id,
            f"👋 <b>Welcome to CA Foundation Quiz Master!</b> 🎓\n\n"
            "Thank you for adding me to your group. I'm ready to help your study sessions!\n\n"
            "⚡ <b>Available Commands:</b>\n\n"
            "🏆 <code>/mocktest</code> — Start timed mock test with leaderboard\n"
            "🎯 <code>/quiz</code> — Get instant on-demand quiz\n"
            "▶️ <code>/start_autoquiz</code> — Enable automatic periodic quizzes (Admin)\n"
            "⏸️ <code>/stop_autoquiz</code> — Disable automatic quizzes (Admin)\n"
            "📊 <code>/stats</code> — View community & question bank statistics\n"
            "⚠️ <code>/report</code> — Report question errors\n\n"
            "💡 <i>Tip: Admins can configure auto-quiz intervals using /set_interval</i>",
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
        is_grp = chat.type in [Chat.GROUP, Chat.SUPERGROUP]
        await db.register_or_update_chat(chat.id, chat.title or (user.full_name if user else "User"), chat.type, is_active=False)

        if update.message:
            bot_info = await context.bot.get_me()
            add_to_group_url = f"https://t.me/{bot_info.username}?startgroup=true"
            developer_url = "https://t.me/Cagourav_18"

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add to Your Study Group", url=add_to_group_url)],
                [InlineKeyboardButton("👨‍💻 Contact Developer", url=developer_url)],
            ])

            user_name = user.first_name if (user and user.first_name) else "Student"
            safe_user_name = html.escape(user_name)

            welcome_text = (
                f"👋 <b>Hello, {safe_user_name}!</b> 🎓\n\n"
                f"Welcome to <b>CA Foundation Quiz Master Bot</b> — your dedicated companion for exam preparation and conceptual revision!\n\n"
                "⚡ <b>Quick Commands:</b>\n\n"
                "🏆 <code>/mocktest</code> — Start interactive timed mock test\n"
                "🛑 <code>/stoptest</code> — Cancel ongoing mock test\n"
                "🎯 <code>/quiz</code> — Get instant MCQ question\n"
                "📊 <code>/stats</code> — View question bank statistics\n"
                "⚠️ <code>/report &lt;reason&gt;</code> — Report question issues\n\n"
                "💡 <b>Pro Tip:</b> Add this bot to your study group for daily scheduled quizzes with competitive leaderboards!\n\n"
                "✨ <i>Start your journey to CA Foundation success today!</i>"
            )
            await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

async def quiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat:
        subj = " ".join(context.args).strip() if context.args else None
        await send_quiz_to_chat(context, chat.id, subj)

async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    msg = update.message
    if not user or not is_bot_owner(user.id) or not msg:
        if msg:
            await msg.reply_text("⛔ <b>Access Denied</b>\n\n<i>Only Bot Owner can send broadcasts.</i>", parse_mode=ParseMode.HTML)
        return

    replied = msg.reply_to_message
    raw_text = None

    if msg.text:
        parts = msg.text.split(None, 1)
        if len(parts) > 1:
            raw_text = parts[1].strip()
    elif msg.caption:
        parts = msg.caption.split(None, 1)
        if len(parts) > 1:
            raw_text = parts[1].strip()

    if not replied and not raw_text:
        await msg.reply_text(
            "📢 <b>Broadcast Command Usage</b>\n\n"
            "<b>Method 1 - Text Message:</b>\n"
            "<code>/broadcast Your announcement message here</code>\n\n"
            "<b>Method 2 - Media/Formatted Post:</b>\n"
            "Reply to any message with <code>/broadcast</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    all_chats = await db.get_all_broadcast_chats()
    if not all_chats:
        await msg.reply_text("❌ <b>No Active Chats Found</b>\n\n<i>No registered chats found in the database.</i>", parse_mode=ParseMode.HTML)
        return

    progress_msg = await msg.reply_text(f"⏳ <b>Broadcasting to {len(all_chats)} chats...</b>", parse_mode=ParseMode.HTML)

    success_users, success_groups, failed_count = 0, 0, 0

    for item in all_chats:
        target_id = item["chat_id"]
        c_type = item.get("chat_type", "private")
        try:
            if replied:
                await context.bot.copy_message(chat_id=target_id, from_chat_id=msg.chat.id, message_id=replied.message_id)
            else:
                await context.bot.send_message(chat_id=target_id, text=raw_text, parse_mode=ParseMode.HTML)

            if c_type in ["group", "supergroup"]:
                success_groups += 1
            else:
                success_users += 1

            await asyncio.sleep(config.BROADCAST_DELAY_SECONDS)

        except Forbidden:
            failed_count += 1
            await db.set_chat_active_status(target_id, False)
        except Exception as e:
            failed_count += 1
            logger.warning(f"Broadcast failed for {target_id}: {e}")

    total_success = success_users + success_groups
    report_text = (
        "📢 <b>Broadcast Completed Successfully!</b>\n\n"
        f"✅ <b>Delivered:</b> <code>{total_success}</code> chats\n"
        f"👤 <b>Users:</b> <code>{success_users}</code>\n"
        f"👥 <b>Groups:</b> <code>{success_groups}</code>\n"
        f"❌ <b>Failed:</b> <code>{failed_count}</code>"
    )
    await progress_msg.edit_text(report_text, parse_mode=ParseMode.HTML)

async def set_interval_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat, user = update.effective_chat, update.effective_user
    if not chat or not user:
        return

    if not await is_admin_or_owner(chat, user.id):
        if update.message:
            await update.message.reply_text(
                "⛔ <b>Permission Denied</b>\n\n"
                "<i>Only Group Administrators or Bot Owner can modify the quiz interval.</i>",
                parse_mode=ParseMode.HTML
            )
        return

    if not context.args or not context.args[0].isdigit() or int(context.args[0]) < 1:
        if update.message:
            await update.message.reply_text(
                "❌ <b>Invalid Usage</b>\n\n"
                "<b>Correct Format:</b>\n"
                "<code>/set_interval 30</code>\n\n"
                "<i>Enter the interval in minutes (minimum 1 minute)</i>",
                parse_mode=ParseMode.HTML
            )
        return

    mins = int(context.args[0])
    await db.set_chat_interval(chat.id, mins)
    settings = await db.get_chat_settings(chat.id)
    if settings and settings.get("is_active") == 1:
        schedule_job(context.application, chat.id, mins)

    if update.message:
        await update.message.reply_text(
            f"✅ <b>Interval Updated Successfully!</b>\n\n"
            f"Auto-quiz interval set to <b>{mins} minutes</b> for this group.",
            parse_mode=ParseMode.HTML
        )

async def reload_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not is_bot_owner(user.id):
        if update.message:
            await update.message.reply_text(
                "⛔ <b>Access Denied</b>\n\n"
                "<i>Only Bot Owner can reload question files.</i>",
                parse_mode=ParseMode.HTML
            )
        return

    success = qm.load_questions()
    if update.message:
        if success:
            await update.message.reply_text(
                f"✅ <b>Questions Reloaded Successfully!</b>\n\n"
                f"Total Questions in Bank: <b>{len(qm.questions)}</b>",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                "❌ <b>Error Reloading Questions</b>\n\n"
                "<i>Failed to reload question files. Please check the data folder.</i>",
                parse_mode=ParseMode.HTML
            )

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
            "⚠️ <b>How to Report a Question</b>\n\n"
            "<b>Step 1:</b> Reply to any quiz poll\n"
            "<b>Step 2:</b> Type <code>/report &lt;describe the issue&gt;</code>\n\n"
            "<b>Example:</b>\n"
            "<code>/report Wrong answer marked as correct</code>",
            parse_mode=ParseMode.HTML
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
        f"💬 <b>Issue Reported:</b>\n<i>{html.escape(reason)}</i>"
    )

    for admin_id in config.SUPER_ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=alert_text, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.warning(f"Could not send report to admin {admin_id}: {e}")

    await msg.reply_text(
        "✅ <b>Report Submitted Successfully!</b>\n\n"
        "<i>Thank you for your feedback. Your report has been sent to the administrators for review.</i>",
        parse_mode=ParseMode.HTML
    )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Unhandled Telegram exception: {context.error}")

async def post_init(application: Application) -> None:
    await db.init_db()
    active_chats = await db.get_all_active_chats()
    logger.info(f"🔄 MongoDB loaded: {len(active_chats)} active auto-quiz groups found.")
    for row in active_chats:
        if row.get("chat_type") in ["group", "supergroup"]:
            schedule_job(application, row["chat_id"], row["interval_minutes"])

    if application.job_queue:
        cleanup_interval = config.QUIZ_CLEANUP_INTERVAL_MINUTES * 60
        application.job_queue.run_repeating(cleanup_expired_quizzes_job, interval=cleanup_interval, first=60, name="auto_cleanup_quizzes")

def main() -> None:
    app = ApplicationBuilder().token(config.BOT_TOKEN).post_init(post_init).build()
    
    app.add_error_handler(error_handler)

    # 1. Custom Count Text Input Listener & Background Activity Listener
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, custom_count_text_handler), group=0)
    app.add_handler(MessageHandler(filters.ChatType.GROUPS, group_activity_listener), group=-1)

    # 2. Member join/leave updates
    app.add_handler(ChatMemberHandler(chat_member_update, ChatMemberHandler.MY_CHAT_MEMBER))
    
    # 3. Live Poll Answer Listener for Mock Test Leaderboards
    app.add_handler(PollAnswerHandler(poll_answer_handler))
    
    # 4. Interactive Callback Queries for /mocktest (including back navigation)
    app.add_handler(CallbackQueryHandler(mocktest_callback_handler, pattern=r"^m(ch|sub|cnt|tim|back|portal)_"))
    
    # 5. Public Commands
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("quiz", quiz_cmd))
    app.add_handler(CommandHandler("mocktest", mocktest_cmd))
    app.add_handler(CommandHandler("stoptest", stoptest_cmd))
    app.add_handler(CommandHandler("cancel_mocktest", stoptest_cmd))
    app.add_handler(CommandHandler("start_autoquiz", start_autoquiz_cmd))
    app.add_handler(CommandHandler("start_quiz", start_autoquiz_cmd))
    app.add_handler(CommandHandler("stop_autoquiz", stop_autoquiz_cmd))
    app.add_handler(CommandHandler("stop_quiz", stop_autoquiz_cmd))
    app.add_handler(CommandHandler("report", report_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    
    # 6. Owner-Only Commands
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("set_interval", set_interval_cmd))
    app.add_handler(CommandHandler("reload", reload_cmd))
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
