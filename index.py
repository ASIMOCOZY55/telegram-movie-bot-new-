import os
import logging
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram.constants import ParseMode

# Enable logging to see what's happening
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Configuration ---
TOKEN = os.environ.get("BOT_TOKEN")

# --- Bot Handlers ---
async def start_command(update: Update, context):
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        f"Hi {user.mention_html()}! I'm your movie bot. Send me a movie name, and I'll see what I can find!",
        parse_mode=ParseMode.HTML
    )
    logger.info(f"User {user.full_name} ({user.id}) started the bot.")

async def help_command(update: Update, context):
    """Send a message when the command /help is issued."""
    await update.message.reply_text("Send me a movie title and I'll try to find it for you!")
    logger.info(f"User {update.effective_user.full_name} requested help.")

async def movie_search(update: Update, context):
    """Echo the user message (placeholder for actual movie search)."""
    movie_title = update.message.text
    await update.message.reply_text(
        f"Searching for '{movie_title}'... (This feature is still under development, macha!)"
    )
    logger.info(f"User {update.effective_user.full_name} requested movie: {movie_title}")

async def error_handler(update: Update, context):
    """Log the error and send a telegram message to notify the developer."""
    logger.warning(f"Update {update} caused error {context.error}")
    if update.effective_message:
        await update.effective_message.reply_text("Oops! Something went wrong. I'm telling my developer!")

# --- Initialize Flask App ---
app = Flask(__name__)

# --- Vercel Serverless Function Entry Point ---
@app.route('/', methods=['GET', 'POST'])
async def telegram_webhook():
    if request.method == 'GET':
        logger.info("Received GET request at root.")
        return "Hello from your Telegram Movie Bot on Vercel! (Server is running.)"

    logger.info("Received POST request at root (potential Telegram webhook).")

    if not TOKEN:
        logger.error("BOT_TOKEN is not set. Please configure it in Vercel environment variables.")
        return jsonify({'status': 'error', 'message': 'BOT_TOKEN not configured'}), 500

    try:
        # Build the Application instance for each request in webhook mode
        application = Application.builder().token(TOKEN).build()

        # Add all your handlers here
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, movie_search))
        application.add_error_handler(error_handler)

        logger.info("Telegram Application instance created and handlers added for this request.")

        # Process the incoming webhook update using run_webhook
        await application.process_update(
            Update.de_json(request.get_json(force=True), application.bot)
        )

        logger.info(f"Successfully processed an update.")
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        logger.exception("Error processing Telegram update")
        return jsonify({'status': 'error', 'message': str(e)}), 500
