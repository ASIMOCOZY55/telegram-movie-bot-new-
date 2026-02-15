import os
import logging
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Enable logging to see what's happening
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Configuration ---
# Get your bot token from environment variables.
# This is crucial for security and Vercel deployments.
# Make sure you have a BOT_TOKEN environment variable set in Vercel project settings.
TOKEN = os.environ.get("BOT_TOKEN")

# --- Bot Handlers ---
async def start_command(update: Update, context):
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        f"Hi {user.mention_html()}! I'm your movie bot. Send me a movie name, and I'll see what I can find!",
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
    # Optionally, send an error message to the user or to a specific chat_id for debugging
    if update.effective_message:
        await update.effective_message.reply_text("Oops! Something went wrong. I'm telling my developer!")

# --- Initialize Flask App and Telegram Bot ---
app = Flask(__name__)

# Global variable for the Telegram Application instance
application = None

# This function is designed to initialize the Telegram Application
# It's called once when the serverless function is "cold started" to reduce overhead.
async def init_telegram_bot():
    global application
    if application is None:
        if not TOKEN:
            logger.error("BOT_TOKEN is not set. Please configure it in Vercel environment variables.")
            # It's good practice to raise an error if critical config is missing
            raise ValueError("BOT_TOKEN is not configured.")

        # Build the Application instance
        application = Application.builder().token(TOKEN).build()

        # Add all your handlers here
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, movie_search))

        # Add the error handler
        application.add_error_handler(error_handler)

        # Retrieve the Vercel URL, which is automatically set by Vercel in environment variables.
        webhook_url = os.environ.get("VERCEL_URL")
        if not webhook_url:
            logger.error("VERCEL_URL environment variable is not set. Webhook cannot be configured properly.")
            # For local testing, you might set a dummy URL, but for Vercel it MUST be present.
            raise ValueError("VERCEL_URL is not set. Cannot configure webhook.")

        # Set the webhook for the bot
        # We are setting it to the root of your Vercel deployment for simplicity.
        await application.bot.set_webhook(url=f"https://{webhook_url}/")
        logger.info(f"Telegram Application initialized and webhook set to https://{webhook_url}/")
    return application

# This is the main entry point for your Vercel serverless function.
# It will handle both GET and POST requests to the root path '/'.
@app.route('/', methods=['GET', 'POST']) # <--- CRITICAL CHANGE HERE
async def telegram_webhook():
    # If it's a GET request, just return a simple message to indicate the server is alive.
    if request.method == 'GET':
        logger.info("Received GET request at root.")
        return "Hello from your Telegram Movie Bot on Vercel! (Server is running.)"

    # For POST requests, proceed with Telegram update processing.
    logger.info("Received POST request at root (potential Telegram webhook).") 
    # Initialize the bot application if it hasn't been already
    bot_app = await init_telegram_bot()

    try:
        # Parse the incoming JSON update from Telegram
        update = Update.de_json(request.get_json(force=True), bot_app.bot)
        # Process the update using the bot's application instance
        await bot_app.process_update(update)
        logger.info(f"Successfully processed update {update.update_id}")
        # Return a success response to Telegram
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        # Log any errors during update processing and return an error response
        logger.exception("Error processing Telegram update")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Vercel looks for a variable named 'app' to serve your Flask application.
# This line makes sure it's exported correctly.
# 'app' is the Flask application instance.
