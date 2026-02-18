import os
import itertools
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from tools import search_restaurants, get_menu, create_cart, get_tracking_info, get_saved_addresses, checkout_cart, login_step_1, login_step_2

# Define the tools available to the model
tools = [
    search_restaurants,
    get_menu,
    create_cart,
    checkout_cart,
    get_tracking_info,
    get_saved_addresses,
    login_step_1,
    login_step_2
]

SYSTEM_INSTRUCTION = """
You are a helpful AI assistant for ordering food using Zomato.
You can search for restaurants, view menus, create carts, and track orders.

Follow these steps:
1.  **Identify User Intent**: Determine if the user wants to search, view menu, order, or track.
2.  **Login**: If the user needs to login (or if tools fail with auth errors), use `login_step_1` (phone) and `login_step_2` (OTP).

**CRITICAL ORDERING FLOW**:
To place an order ("Add to cart"), you **MUST** have the following information. If you don't have it, you **MUST** get it first using tools:
1.  **Address ID**: Call `get_saved_addresses` to get the user's `address_id` (and location). Ask user to pick one if multiple.
2.  **Restaurant ID**: Use `search_restaurants(keyword=..., address_id=...)` to find the restaurant and get its `res_id`. even if the user names the restaurant, you MUST search to get the ID.
3.  **Variant Selection**: 
    - You CANNOT add an item without a variant if the item has multiple variants.
    - Call `get_menu(res_id=..., address_id=...)` first to find the exact item and its available variants.
    - Ask the user to clarify the variant if needed (e.g., "Medium" vs "Large", "Veg" vs "Non-Veg").
4.  **Create Cart**: Only ONCE you have `res_id`, `address_id`, and `items` (with variants), call `create_cart`.

**Steps for "Add [Item] from [Restaurant]"**:
1. `get_saved_addresses()` -> get `address_id`.
2. `search_restaurants("Restaurant Name", address_id)` -> get `res_id`.
3. `get_menu(res_id, address_id)` -> check item details/variants.
4. `create_cart(res_id, address_id, [{"id": "...", "name": "...", "quantity": ...}])`

**Present Results**: Summarize the tool outputs in a user-friendly way.
    - When showing restaurants, show rating and delivery time.
    - When showing menu, list top items with prices.
    - Before ordering, always show the estimated total and ask for confirmation.
6.  **Confirm Orders**: When adding to cart, confirm the exact items and variants.
7.  **Checkout**: Use `create_cart` then `checkout_cart`.
"""

apis = {
    "1": os.getenv('GEMINI_API_KEY'),
}

api_cycle = itertools.cycle(apis.values())

class Agent:
    def __init__(self):
        # We will initialize the agent executor lazily or rebuild it on each turn if we want to rotate keys strictly per message,
        # but LangChain Client init is usually heavy.
        # A better approach for key rotation in LangChain is to just rotate the model instance or key.
        # For simplicity, we'll store the tools and prompt here.
        self.tools = tools
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_INSTRUCTION),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ])
        # We need to maintain memory manually or use LangChain's memory.
        # For this refactor, let's keep it simple and stateless (or pass history from main.py if we were using it).
        # But wait, the previous `agent.py` was managing `self.chat` which implies session state.
        # `main.py` creates a new Agent instance per User ID.
        # So we should maintain history here.
        from langchain_core.messages import SystemMessage
        from langchain.memory import ConversationBufferMemory
        
        # We'll use a simple list for history to pass to the agent
        self.chat_history = [] 

    async def process_message(self, user_message: str):
        """
        Process a user message and return the response using LangChain.
        """
        try:
            # Rotate API Key
            next_key = next(api_cycle)
            print(f"DEBUG: Using API Key ending in ...{next_key[-4:]}")
            
            # Initialize Model with new key
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                google_api_key=next_key,
                temperature=0
            )
            
            # Create Agent
            agent = create_tool_calling_agent(llm, self.tools, self.prompt)
            agent_executor = AgentExecutor(agent=agent, tools=self.tools, verbose=True)
            
            # Use the executor
            # Note: We are passing chat_history manually.
            response = await agent_executor.ainvoke({
                "input": user_message,
                "chat_history": self.chat_history
            })
            
            # Update history
            from langchain_core.messages import HumanMessage, AIMessage
            self.chat_history.append(HumanMessage(content=user_message))
            self.chat_history.append(AIMessage(content=response["output"]))
            
            return response["output"]

        except Exception as e:
            # traceback.print_exc()
            print(f"Error processing message: {e}")
            return f"Error processing message: {str(e)}"
