import os
from io import BytesIO
import requests
from flask import Flask, request, jsonify
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, MessageHandler, Filters, CallbackQueryHandler, Dispatcher
# Assuming scraper.py exists in the same directory and has these functions
from scraper import search_movies, get_movie

# --- Configuration ---
# Use environment variables for sensitive info and dynamic URLs
TOKEN = os.environ.get("BOT_TOKEN")
# VERCEL_URL is a system environment variable provided by Vercel for the deployment URL
# It includes the protocol (https://) and domain.
URL = os.environ.get("VERCEL_URL")

# --- Flask App Initialization ---
# This needs to be a global instance for Vercel to find it as the entry point
app = Flask(__name__)

# --- Bot functions ---
def welcome(update, context) -> None:
    update.message.reply_text(f"Hello Dear, Welcome to Project - Name.\n"
                              f"🔥 Download Your Favourite Movies, Webseries & TV-Shows For 💯 Free And 🍿 Enjoy it.")
    update.message.reply_text("👇 Enter Keyword Below 👇")

def find_movie(update, context):
    search_results = update.message.reply_text("Processing")
    query = update.message.text
    movies_list = search_movies(query) # This relies on your scraper.py
    if movies_list:
        keyboards = []
        for movie in movies_list:
            keyboard = InlineKeyboardButton(movie["title"], callback_data=movie["id"])
            keyboards.append([keyboard])
        reply_markup = InlineKeyboardMarkup(keyboards)
        search_results.edit_text('Results', reply_markup=reply_markup)
    else:
        search_results.edit_text('Sorry 🙏, No result found!\nPlease retry Or contact admin.')

def movie_result(update, context) -> None:
    query = update.callback_query
    s = get_movie(query.data) # This relies on your scraper.py
    response = requests.get(s["img"])
    img = BytesIO(response.content)
    query.message.reply_photo(photo=img, caption=f"🎥 {s['title']}")
    link = ""
    links = s["links"]
    for i in links:
        link += "🎬" + i + "\n" + links[i] + "\n\n"
    caption = f"Direct Download Links:\n\n{link}"
    if len(caption) > 4095:
        # Telegram message size limit workaround
        for x in range(0, len(caption), 4095):
            query.message.reply_text(text=caption[x:x+4095])
    else:
        query.message.reply_text(text=caption)

# --- Dispatcher setup function ---
# This will be called on each incoming request
def setup_dispatcher():
    # Instantiate Bot inside the function for serverless context
    current_bot = Bot(TOKEN)
    update_queue = Queue() # Queue might not be needed for webhook-only setup
    dispatcher = Dispatcher(current_bot, update_queue, use_context=True)

    dispatcher.add_handler(CommandHandler('start', welcome))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, find_movie)) # ~Filters.command to not conflict with /start
    dispatcher.add_handler(CallbackQueryHandler(movie_result))
    return dispatcher

# --- Flask Routes ---
@app.route('/')
def home():
    # Simple check for the root URL
    return 'Hello World from your Telegram Movie Bot on Vercel!'

@app.route(f'/{TOKEN}', methods=['POST']) # Use f-string for clarity, only POST for webhook
def webhook():
    if request.method == "POST":
        # Process the Telegram update
        dispatcher = setup_dispatcher()
        update = Update.de_json(request.get_json(force=True), dispatcher.bot)
        dispatcher.process_update(update)
        return jsonify({'status': 'ok'})
    return jsonify({'status': 'method not allowed'}), 405

@app.route('/setwebhook', methods=['GET']) # Changed to GET, as it's usually for setup
def set_webhook_route():
    if not TOKEN or not URL:
        return "Error: BOT_TOKEN or VERCEL_URL environment variables not set.", 500

    webhook_url = f"{URL}/{TOKEN}" # Correctly form the webhook URL
    current_bot = Bot(TOKEN) # Instantiate bot for this call

    s = current_bot.setWebhook(webhook_url)
    if s:
        return f"Webhook set to: {webhook_url}"
    else:
        return f"Webhook setup failed for: {webhook_url}"
