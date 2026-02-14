import os
import logging
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, PicklePersistence

    # Enable logging
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
    )
    logger = logging.getLogger(__name__)

    # --- Configuration ---
    # It's highly recommended to use environment variables for sensitive info!
    # For Vercel, set a BOT_TOKEN environment variable in your project settings.
    # The default value here is just a placeholder and will not work.
    TOKEN = os.environ.get("BOT_TOKEN") # Get token from environment variable

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

    # This function is run once when the serverless function is "cold started"
    async def init_telegram_bot():
        global application
        if application is None:
            if not TOKEN:
                logger.error("BOT_TOKEN is not set. Please configure it in Vercel environment variables.")
                raise ValueError("BOT_TOKEN is not configured.")

            # Persistence is good for long-running bots, but might need proper storage
            # for serverless. For now, we use simple PicklePersistence (in-memory for serverless re-init).
            # If your bot needs to remember things across invocations, you'll need external storage (e.g., database).
            # persistence = PicklePersistence(filepath="bot_data.pkl")

            application = Application.builder().token(TOKEN).build() # .persistence(persistence).build()

            # Add Handlers
            application.add_handler(CommandHandler("start", start_command))
            application.add_handler(CommandHandler("help", help_command))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, movie_search))

            # Add Error Handler
            application.add_error_handler(error_handler)

            # Start webhook
            # This is important: tells Telegram where to send updates.
            # On Vercel, the URL is your project URL + the webhook path.
            # Example: https://cozys-movie-bot.vercel.app/telegram
            # This will be handled by the /telegram route below.
            await application.bot.set_webhook(url=os.environ.get("VERCEL_URL", "https://example.com") + "/telegram")
            logger.info("Telegram Application initialized and webhook set.")
        return application

    # This is the entry point for Vercel.
    # All incoming HTTP requests to your serverless function will come here.
    @app.route('/telegram', methods=['POST'])
    async def telegram_webhook():
        # Initialize bot application if it's not already
        bot_app = await init_telegram_bot()

        # Process the update from Telegram
        try:
            update = Update.de_json(request.get_json(force=True), bot_app.bot)
            await bot_app.process_update(update)
            logger.info(f"Processed update {update.update_id}")
            return jsonify({'status': 'ok'}), 200
        except Exception as e:
            logger.exception("Error processing Telegram update")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    # A simple route for checking if the server is alive
    @app.route('/')
    def index():
        return "Hello from your Telegram Movie Bot on Vercel!"

    # Export the Flask app for Vercel
    # Vercel will look for `app` in your `index.py`
    # You will need to explicitly set VERCEL_URL as an environment variable
    # in Vercel project settings, or ensure it's provided by Vercel automatically.
    # Often, Vercel provides this as an environment variable by default during deployment.
