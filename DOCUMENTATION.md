# AI Food Ordering Bot Documentation

## 1. Technical Overview

This solution implements an intelligent food ordering bot for Telegram, powered by **Google Gemini 2.5 Flash** or **OpenAI GPT-4o** as the reasoning engine and **Zomato's APIs** for real-world data access. The bot is designed to handle complex, multi-turn conversations, understand user intent (searching, menu browsing, ordering), and execute actions autonomously.

### Key Technologies
-   **LangChain**: Orchestrates the agent workflow, tool execution, and prompt management.

-   **Multi-LLM Support**: Configurable to use either Google Gemini or OpenAI.

-   **Model Context Protocol (MCP)**: Standardizes the connection between the AI agent and the Zomato toolset.
-   **Python-Telegram-Bot**: Handles the Telegram messaging interface.
-   **AsyncIO**: Ensures non-blocking, high-performance operation.

---

## 2. Architecture & Workflow

The architecture follows a modular **Agent-Tool-Client** pattern:

1.  **Telegram Interface (`main.py`)**:
    -   Receives user messages via polling.
    -   Maintains conversation context per user.
    -   Forwards text to the AI Agent.

2.  **AI Orchestrator (`agent.py`)**:
    -   **LangChain Agent**: Uses a ReAct (Reasoning + Acting) loop.
    -   **System Prompt**: Defines the persona, ordering rules, and mandatory steps (e.g., "Must get address_id before searching").
    -   **API Rotation**: Cycles through multiple Gemini API keys to handle rate limits.

3.  **Tool Layer (`tools.py`)**:
    -   Exposes specific functions to the LLM: `search_restaurants`, `get_menu`, `create_cart`, etc.
    -   Acts as a bridge to the MCP Client.

4.  **Zomato MCP Server**:
    -   An external process (running via `npx`) that holds the actual Zomato API logic.
    -   The Python bot communicates with it via Stdio (Standard Input/Output).

### Workflow Diagram (Conceptual)

```
[User] -> (Telegram Msg) -> [Main.py] 
                               |
                               v
                         [Agent.py (LangChain)]
                               | "I need to search for pizza"
                               v
                          [Tools.py] -> (MCP Request) -> [Zomato MCP] -> [Zomato API]
                               ^                                 |
                               |          (JSON Result)          |
                               +---------------------------------+
                               |
                         [Agent.py] -> "Found Domio's Pizza..."
                               |
                               v
[User] <- (Telegram Msg) <- [Main.py]
```

---

## 3. API Integration Approach


-   **Why MCP?**: It decouples the bot logic from the API implementation. The bot simply "calls a tool" without knowing the underlying HTTP endpoints.

-   **Tool Definitions**: Tools are defined in the MCP server manifest. The bot discovers them at startup (`list_tools`).
-   **Data Conversion**: Since MCP uses Protobuf-like structures, a custom helper (or LangChain's native handling) converts these objects into standard Python dictionaries for the LLM to process.

---

## 4. Challenges Faced & Solutions


### Challenge 1: API Rate Limits
**Issue**: High frequency of tool calls (thinking, searching, menu fetching) quickly hit Gemini's rate limits.
**Solution**: Implemented a **Cyclic Key Rotator**. The bot iterates through a pool of provided API keys (`GEMINI_API_KEY_1`, `_2`, etc.) for each new request, distributing the load.

### Challenge 2: Async Event Loop Conflicts
**Issue**: Running the bot (async) and the MCP client (also async) led to `RuntimeError: Cannot close a running event loop` on shutdown.
**Solution**: Patched the shutdown sequence to prevent probing closed loops and configured the telegram application to manage the loop lifecycle more gracefully (`close_loop=False`).

### Challenge 3: Prompt Injection / Hallucination
**Issue**: The bot would sometimes try to add items without knowing their "Variant ID".
**Solution**: Enforced a "Critical Ordering Flow" in the **System Prompt**. The bot is explicitly instructed that it *cannot* call `create_cart` without first calling `get_menu` to resolve specific item IDs.

### Challenge 4: Telegram Message Length Limits
**Issue**: Large search results (like "List all restaurants") often exceeded Telegram's 4096-character message limit, causing the bot to crash with `BadRequest: Message is too long`.
**Solution**: Implemented response chunking in `main.py`. If a message exceeds 4000 characters, it is automatically split into smaller chunks and sent sequentially.

---

## 5. Instructions for Testing

### Prerequisites
1.  Python 3.10+
2.  Zomato Account (phone number) for login.
3.  Gemini API Key(s).

### Setup
1.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
2.  Configure `.env`:
    ```env
    TELEGRAM_TOKEN=your_token
    GEMINI_API_KEY=your_key
    # Add optional keys GEMINI_API_KEY_2, etc.
    cookie=your_zomato_cookie
    
    # Optional: For OpenAI Support
    # LLM_PROVIDER=openai
    # OPENAI_API_KEY=sk-...
    ```

### Running the Bot
```bash
python main.py
```

### Test Cases

**1. Basic Search**
> User: "Show me pizza places in Bangalore."
> *Bot should ask for address or list saved addresses if logged in.*

**2. Menu Browsing**
> User: "Show me the menu for Dominos."
> *Bot should list categories or top items.*

**3. Complex Order**
> User: "I want 2 Margheritas and a Pepsi from Dominos."
> *Bot should:*
> 1. *Identify variants (Small/Med/Large).*
> 2. *Ask for clarification if needed.*
> 3. *Add to cart and show total.*

**4. Checkout**
> User: "Place the order."
> *Bot should generate a payment QR code (simulation).*
