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
    from user_context import current_user_id
    current_user_id.set(user_id)
    
    if user_id not in user_agents:
        user_agents[user_id] = Agent()
    
    agent = user_agents[user_id]
    user_message = update.message.text
    
    # Indicate typing
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    response = await agent.process_message(user_message)

    # Check for QR code in response
    import re
    # More robust regex to capture path even if slightly altered by LLM
    # Looking for the pattern we output in tools.py: [QR Code Image Saved to <path>]
    qr_match = re.search(r"\[QR Code Image Saved to\s+(.*?)\]", response)
    image_path = None
    if qr_match:
        image_path = qr_match.group(1).strip()
        # Remove the internal log message from the user response so we don't show the raw path text
        response = response.replace(qr_match.group(0), "Here is your payment QR code:")

    # Telegram message limit is 4096. To be safe, chunk at 4000.
    if len(response) > 4000:
        for i in range(0, len(response), 4000):
            chunk = response[i:i+4000]
            await context.bot.send_message(chat_id=update.effective_chat.id, text=chunk)
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response)
        
    # Send the image if found
    if image_path and os.path.exists(image_path):
        try:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=open(image_path, 'rb'))
            # Start tracking the order automatically
            # Use asyncio.create_task for robust background execution without JobQueue dependency
            asyncio.create_task(track_order_loop(
                bot=context.bot,
                chat_id=update.effective_chat.id,
                user_id=user_id
            ))
        except Exception as e:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Failed to send QR image: {e}")

async def track_order_loop(bot, chat_id, user_id):
    """Asyncio loop for tracking orders if JobQueue is unavailable."""
    from tools import get_tracking_info
    # We need to set the user context for this task
    from user_context import current_user_id
    
    # Run loop a few times (e.g., monitor for 30 minutes: 10 checks * 3 mins)
    for _ in range(10):
        # Wait 3 minutes
        await asyncio.sleep(180) 
        
        current_user_id.set(user_id)
        try:
            # We must use invoke here because tools are usually called by agent with string args, 
            # but here we call the LangChain tool directly.
            status_info = await get_tracking_info.invoke({})
            
            # Simple heuristic: report successful tracking info
            if "No active orders" not in status_info and "error" not in status_info.lower():
                 await bot.send_message(chat_id=chat_id, text=f"🔔 Order Update:\n{status_info}")
                 if "delivered" in status_info.lower():
                     break
            else:
                # print(f"DEBUG: Tracking found no active orders for user {user_id}")
                pass
                
        except Exception as e:
            print(f"Error in async tracking: {e}")

async def main():
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_TOKEN not found in environment variables.")
        return

    async with ZomatoClient():
        print("Zomato MCP Client Initialized.")
        
        # Initialize Database
        from database import init_db
        init_db()
        print("Database initialized.")
        
        # Use .post_init() to setup job queue in older versions or just build() is fine in v20+
        # But we need job_queue support
        application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        
        # In python-telegram-bot v20+, job_queue is enabled by default if dependencies are installed.
        # We need to make sure we use it correctly.
        # The 'context' in callbacks will have job_queue.
        
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
