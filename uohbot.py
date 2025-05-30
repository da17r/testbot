import logging
import os
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler
)
import fitz  # PyMuPDF

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Conversation states
(SELECT_STAGE, ENTER_NAME, SELECT_GENDER, ENTER_DETAILS, VERIFY_CODE, EDIT_INFO, ADMIN_PANEL, SPECIFY_GENDER) = range(8)

# Global storage
CODE_FILE = "codes.pdf"
USER_DATA = {}
ADMIN_CODE = "Dadyar.admin"
VALID_CODES = set()
CODE_USAGE = {}

STAGES = {
    "Stage 1": [],
    "Stage 2": [],
    "Stage 3": [],
    "Stage 4": [],
}

def load_codes_from_pdf(filepath):
    codes = set()
    try:
        doc = fitz.open(filepath)
        for page in doc:
            text = page.get_text()
            lines = text.splitlines()
            for line in lines:
                line = line.strip()
                if line:
                    codes.add(line)
        doc.close()
    except Exception as e:
        print(f"Error reading code file: {e}")
    return codes

VALID_CODES = load_codes_from_pdf(CODE_FILE)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📋 View Stages", callback_data='view_stages')],
        [InlineKeyboardButton("➕ Add My Info", callback_data='add_info')],
        [InlineKeyboardButton("✏️ Edit My Info", callback_data='edit_info')],
        [InlineKeyboardButton("🛠️ Admin Panel", callback_data='admin')],
    ]
    if update.message:
        await update.message.reply_text("👋 Welcome! Please choose an option:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif update.callback_query:
        await update.callback_query.edit_message_text("👋 Welcome! Please choose an option:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'view_stages':
        keyboard = [[InlineKeyboardButton(stage, callback_data=f"show_stage_{stage}")] for stage in STAGES]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='start')])
        await query.edit_message_text("📚 Choose your stage:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == 'add_info':
        await query.edit_message_text("🔑 Please enter your access code:")
        return VERIFY_CODE

    elif data == 'edit_info':
        await query.edit_message_text("📝 Enter your access code to edit your information:")
        return EDIT_INFO

    elif data == 'admin':
        await query.edit_message_text("🔐 Enter admin code:")
        return ADMIN_PANEL

    elif data.startswith("show_stage_"):
        stage_name = data.split("show_stage_")[1]
        members = STAGES.get(stage_name, [])
        if not members:
            await query.edit_message_text(f"😕 No users in {stage_name} yet.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='view_stages')]]))
        else:
            message = f"📄 Members of {stage_name}:\n\n"
            for user in members:
                message += f"👤 Name: {user['name']}\n🚻 Gender: {user['gender']}\n📝 Details: {user['details']}\n\n"
            await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='view_stages')]]))

    elif data == 'start':
        await start(update, context)

    elif data == 'back_to_stage':
        keyboard = [[InlineKeyboardButton(stage, callback_data=f"choose_stage_{stage}")] for stage in STAGES]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='start')])
        await query.edit_message_text("📚 Choose your stage:", reply_markup=InlineKeyboardMarkup(keyboard))
        return SELECT_STAGE

    elif data == 'back_to_name':
        await query.edit_message_text("👤 What is your name?")
        return ENTER_NAME

    elif data == 'back_to_gender':
        keyboard = [
            [InlineKeyboardButton("♂️ Male", callback_data='gender_Male')],
            [InlineKeyboardButton("♀️ Female", callback_data='gender_Female')],
            [InlineKeyboardButton("🌈 Other", callback_data='gender_Other')],
            [InlineKeyboardButton("🔙 Back", callback_data='back_to_name')],
        ]
        await query.edit_message_text("🚻 Choose your gender:", reply_markup=InlineKeyboardMarkup(keyboard))
        return SELECT_GENDER

    return ConversationHandler.END

async def verify_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    user_id = update.effective_user.id
    if code in VALID_CODES and (code not in CODE_USAGE or CODE_USAGE[code] == user_id):
        CODE_USAGE[code] = user_id
        context.user_data['code'] = code
        keyboard = [[InlineKeyboardButton(stage, callback_data=f"choose_stage_{stage}")] for stage in STAGES]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='start')])
        await update.message.reply_text("📚 Choose your stage:", reply_markup=InlineKeyboardMarkup(keyboard))
        return SELECT_STAGE
    else:
        await update.message.reply_text("❌ Invalid code. Please try again.")
        return VERIFY_CODE

async def choose_stage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    stage = query.data.split("choose_stage_")[1]
    context.user_data['stage'] = stage
    await query.edit_message_text("👤 What is your name?")
    return ENTER_NAME

async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text.strip()
    keyboard = [
        [InlineKeyboardButton("♂️ Male", callback_data='gender_Male')],
        [InlineKeyboardButton("♀️ Female", callback_data='gender_Female')],
        [InlineKeyboardButton("🌈 Other", callback_data='gender_Other')],
        [InlineKeyboardButton("🔙 Back", callback_data='back_to_stage')],
    ]
    await update.message.reply_text("🚻 Choose your gender:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_GENDER

async def select_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    gender = query.data.split("gender_")[1]
    if gender == "Other":
        await query.edit_message_text("💬 Please specify your gender:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='back_to_gender')]]))
        return SPECIFY_GENDER
    context.user_data['gender'] = gender
    await query.edit_message_text("📝 Write your details (bio/script):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='back_to_gender')]]))
    return ENTER_DETAILS

async def specify_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['gender'] = update.message.text.strip()
    await update.message.reply_text("📝 Write your details (bio/script):")
    return ENTER_DETAILS

async def enter_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = context.user_data['code']
    stage = context.user_data['stage']
    user = {
        "name": context.user_data['name'],
        "gender": context.user_data['gender'],
        "details": update.message.text.strip(),
        "user_id": update.effective_user.id
    }
    STAGES[stage] = [u for u in STAGES[stage] if u.get('user_id') != user['user_id']]
    STAGES[stage].append(user)
    USER_DATA[code] = user
    await update.message.reply_text("✅ Your information has been saved. Thank you!")
    return ConversationHandler.END

async def edit_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    user_id = update.effective_user.id
    if code in CODE_USAGE and CODE_USAGE[code] == user_id:
        context.user_data['code'] = code
        await update.message.reply_text("✏️ Please re-enter your name:")
        return ENTER_NAME
    else:
        await update.message.reply_text("❌ Invalid or unauthorized code.")
        return EDIT_INFO

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    if code == ADMIN_CODE:
        message = "📑 Registered Codes and Data:\n"
        for code, user in USER_DATA.items():
            message += f"\n🔑 Code: {code}\n  👤 Name: {user['name']}\n  🚻 Gender: {user['gender']}\n  📝 Details: {user['details']}\n"
        await update.message.reply_text(message)
        return ConversationHandler.END
    else:
        await update.message.reply_text("❌ Invalid admin code.")
        return ADMIN_PANEL

if __name__ == '__main__':
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        print("❌ BOT_TOKEN environment variable not set!")
        sys.exit(1)

    try:
        app = ApplicationBuilder().token(TOKEN).build()

        conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(handle_menu)],
            states={
                VERIFY_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, verify_code)],
                SELECT_STAGE: [
                    CallbackQueryHandler(choose_stage, pattern="^choose_stage_"),
                    CallbackQueryHandler(handle_menu, pattern='^back_to_stage$')
                ],
                ENTER_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name),
                    CallbackQueryHandler(handle_menu, pattern='^back_to_stage$')
                ],
                SELECT_GENDER: [
                    CallbackQueryHandler(select_gender, pattern="^gender_"),
                    CallbackQueryHandler(handle_menu, pattern='^back_to_name$')
                ],
                SPECIFY_GENDER: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, specify_gender),
                    CallbackQueryHandler(handle_menu, pattern='^back_to_gender$')
                ],
                ENTER_DETAILS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, enter_details),
                    CallbackQueryHandler(handle_menu, pattern='^back_to_gender$')
                ],
                EDIT_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_info)],
                ADMIN_PANEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_panel)],
            },
            fallbacks=[CallbackQueryHandler(handle_menu, pattern='^start$')],
        )

        app.add_handler(CommandHandler("start", start))
        app.add_handler(conv_handler)
        app.run_polling()

    except Exception as e:
        print(f"❌ Bot crashed: {e}")
        input("Press Enter to exit...")
        sys.exit(1)
