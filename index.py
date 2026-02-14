import os
import logging
import asyncio
import json
from io import BytesIO
from http.server import BaseHTTPRequestHandler, HTTPServer # Added HTTPServer import
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Configuration ---
# It's highly recommended to use environment variables for sensitive info!
# For Vercel, set a BOT_TOKEN environment variable in your project settings.
TOKEN = os.environ.get("BOT_TOKEN", "8306413141:AAE_O6b19Xyh3k99Jlp9KVC2CEgr5OpSEac") # <<< IMPORTANT: REPLACE THIS!

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

# --- Vercel Specific Handling ---
# This part sets up the Application and handles incoming webhooks from Vercel.

application = None # Global variable to hold the Telegram Application instance

async def initialize_application():
    """Initializes the Telegram Application instance with handlers."""
    global application
    if application is None:
        # Check if the placeholder token is still present
        if TOKEN == "8306413141:AAE_O6b19Xyh3k99Jlp9KVC2CEgr5OpSEac" or not TOKEN: # Added `or not TOKEN` check
            logger.error("BOT_TOKEN is not set. Please configure it in Vercel environment variables or directly in index.py.")
            raise ValueError("BOT_TOKEN is not configured.")

        application = Application.builder().token(TOKEN).build()

        # Add Handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, movie_search))

        # Add Error Handler
        application.add_error_handler(error_handler)
        logger.info("Telegram Application initialized successfully.")
    return application

# This custom request handler is necessary to bridge Vercel's HTTP request format
# with how python-telegram-bot's Application expects updates.
class VercelRequestHandler(BaseHTTPRequestHandler):
    def __init__(self, request, client_address, server, app_instance):
        self.app_instance = app_instance
        super().__init__(request, client_address, server)

    def do_POST(self):
        async def handle_update_async():
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)

            try:
                update_json = json.loads(post_data.decode('utf-8'))
            except json.JSONDecodeError:
                logger.error("Failed to decode JSON from POST request.")
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'Bad Request: Invalid JSON')
                return

            update = Update.de_json(update_json, self.app_instance.bot)
            logger.info(f"Update received: {update.update_id} (From: {update.effective_user.full_name if update.effective_user else 'N/A'})")

            # CRITICAL FIX: AWAITING THE PROCESS_UPDATE CALL
            await self.app_instance.process_update(update)

            logger.info("Update processed by dispatcher.")
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'ok')

        # Run the async handling in the current event loop
        asyncio.run(handle_update_async())

    # Suppress logging in BaseHTTPRequestHandler to avoid duplicate log entries
    def log_message(self, format, *args):
        return

# Vercel's entry point for the serverless function
async def handler(request, response):
    app = await initialize_application()

    # Create a mock socket and HTTP server to pass to VercelRequestHandler
    class MockSocket:
        def makefile(self, mode='r', buffering=None, encoding=None, errors=None, newline=None):
            if 'r' in mode:
                # Provide the request body to the mock rfile
                return BytesIO(request.body)
            return BytesIO()

    class MockHTTPServer(HTTPServer):
        # Override constructor to prevent actual server binding
        def __init__(self, *args, **kwargs):
            # Pass a dummy server_address to the base class constructor
            super().__init__(('0.0.0.0', 0), VercelRequestHandler)
            self.address_family = 0
            self.socket = MockSocket() # Set the mock socket here

    mock_server = MockHTTPServer(('0.0.0.0', 0), lambda *args, **kwargs: VercelRequestHandler(*args, **kwargs, app_instance=app))

    # Manually create and call the request handler
    # We simulate the HTTP request being handled
    request_handler = VercelRequestHandler(
        MockSocket(), # Pass the mock socket
        ('127.0.0.1', 12345), # Dummy client address
        mock_server,
        app_instance=app # Pass the initialized application instance
    )

    # Set the command and headers for the simulated request
    request_handler.command = 'POST'
    request_handler.path = '/'
    request_handler.headers = request.headers

    # This will run the do_POST method, which then calls app.process_update
    # We need to run this in a thread because do_POST is synchronous,
    # but our event loop is already running via asyncio.run() inside do_POST
    await asyncio.to_thread(request_handler.do_POST)

    # Vercel expects a standard web response. The Telegram part is handled.
    response.status_code = 200
    response.headers['Content-Type'] = 'text/plain'
    response.send('ok') # Corrected the missing parenthesis
