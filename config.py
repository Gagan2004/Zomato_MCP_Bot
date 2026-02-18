import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ZOMATO_MCP_COMMAND = os.getenv("ZOMATO_MCP_COMMAND", "uvx")
ZOMATO_MCP_ARGS = os.getenv("ZOMATO_MCP_ARGS", "zomato-mcp").split()
