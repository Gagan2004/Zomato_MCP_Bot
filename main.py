import os
import asyncio
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import nest_asyncio
from config import TELEGRAM_TOKEN
from tools import ZomatoClient
from agent import Agent

nest_asyncio.apply()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Store user agents
user_agents = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_agents[user_id] = Agent()
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Hello! I'm your Zomato AI assistant. What would you like to order today?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_agents:
        user_agents[user_id] = Agent()
    
    agent = user_agents[user_id]
    user_message = update.message.text
    
    # Indicate typing
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    response = await agent.process_message(user_message)

    # Telegram message limit is 4096. To be safe, chunk at 4000.
    if len(response) > 4000:
        for i in range(0, len(response), 4000):
            chunk = response[i:i+4000]
            await context.bot.send_message(chat_id=update.effective_chat.id, text=chunk)
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response)

async def main():
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_TOKEN not found in environment variables.")
        return

    async with ZomatoClient():
        print("Zomato MCP Client Initialized.")
        
        application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        
        start_handler = CommandHandler('start', start)
        message_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
        
        application.add_handler(start_handler)
        application.add_handler(message_handler) # This handler handles all text messages that are not commands
        
        print("Bot is polling...")
        await application.run_polling(close_loop=False)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped.")
