# AI Restaurant Order Automation Assistant

This is an AI-powered conversational bot for ordering food from Zomato via Telegram. It uses Google's Gemini Flash model for natural language understanding and connects to Zomato via the Model Context Protocol (MCP).

## Prerequisites

- Python 3.10+
- Telegram Bot Token
- Gemini API Key
- Zomato MCP Server installed/configured

## Setup

1.  **Clone the repository** (if you haven't already):
    ```bash
    git clone https://github.com/Gagan2004/Zomato_MCP_Bot.git
    cd Zomato_MCP_Bot
    ```

2.  **Create and activate a virtual environment**:
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # Linux/Mac
    source venv/bin/activate
    ```

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment**:
    Rename `.env.example` to `.env` (or create `.env`) and fill in the values:
    ```env
    ZOMATO_MCP_COMMAND=npx.cmd          # Command to run Zomato MCP (Windows: npx.cmd, Mac/Linux: npx)
    ZOMATO_MCP_ARGS=-y mcp-remote https://mcp-server.zomato.com/mcp

    LLM_PROVIDER=openai 
    # if LLM_PROVIDER is not set to openai , ageny.py will look for GEMINI_API_KEY

    OPENAI_API_KEY=<your_openai_api_key>

    TELEGRAM_TOKEN=your_telegram_bot_token

    GEMINI_API_KEY=your_gemini_api_key
    
    ```
    *Note: This configuration connects to the remote Zomato MCP server.*

## Running the Bot

1.  **Start the bot**:
    ```bash
    python main.py
    ```

2.  **Interact**:
    Open your Telegram bot and send `/start`. You can then ask:
    - "Show pizza places near [Location]"
    - "Show me the menu for [Restaurant Name]"
    - "Order 1 Margherita Pizza"
    - "Track my order"

## Troubleshooting

-   **MCP Connection Failed**: If the bot says "MCP Session not active", check your `ZOMATO_MCP_COMMAND`. You can verify execution by running `python verify_mcp.py`.

-   **Gemini Error**: Ensure your API key is valid and has access to `gemini-2.5-flash`.

## Project Structure

-   `main.py`: Entry point, Telegram bot handler.
-   `agent.py`: LangChain agent logic with tool calling and multi-LLM support.
-   `tools.py`: Zomato MCP client wrapper with pagination support.
-   `config.py`: Configuration loader.

## Features
-   **Multi-LLM Support**: Switch between Google Gemini and OpenAI (GPT-4o) using the `LLM_PROVIDER` env variable.
-   **Advanced Search**: Fetch all restaurants with automated pagination and smart filtering.
-   **Robust Error Handling**: Automatic retry for API limits and intelligent message splitting for long responses.

## Configuration
Add these to your `.env` file for advanced features:

```env
# Optional: Use OpenAI instead of Gemini
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# API Key Rotation (Optional)
GEMINI_API_KEY_2=...
GEMINI_API_KEY_3=...
```
