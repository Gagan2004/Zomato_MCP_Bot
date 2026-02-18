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
    git clone <repo_url>
    cd ai_food_bot
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
    TELEGRAM_TOKEN=your_telegram_bot_token
    GEMINI_API_KEY=your_gemini_api_key
    ZOMATO_MCP_COMMAND=npx.cmd          # Command to run Zomato MCP (Windows: npx.cmd, Mac/Linux: npx)
    ZOMATO_MCP_ARGS=-y mcp-remote https://mcp-server.zomato.com/mcp
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
-   `agent.py`: Gemini agent logic with tool calling.
-   `tools.py`: Zomato MCP client wrapper.
-   `config.py`: Configuration loader.
