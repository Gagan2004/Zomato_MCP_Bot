import os
import itertools
import traceback
from config import GEMINI_API_KEY
from tools import search_restaurants, get_menu, create_cart, get_tracking_info, get_saved_addresses, checkout_cart, login_step_1, login_step_2

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage

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
4. `create_cart(res_id, address_id, [{{ "id": "...", "name": "...", "quantity": ... }}])`

**Present Results**: Summarize the tool outputs in a user-friendly way.
    - When showing restaurants, show rating and delivery time. List up to 10 relevant options if found.
    - When showing menu, list top items with prices.
    - Before ordering, always show the estimated total and ask for confirmation.
6.  **Confirm Orders**: When adding to cart, confirm the exact items and variants.
7.  **Checkout**: Use `create_cart` then `checkout_cart`.
"""


# apis = {
#     "1": os.getenv("GEMINI_API_KEY_1", os.getenv("GEMINI_API_KEY")),
#     "2": os.getenv("GEMINI_API_KEY_2", os.getenv("GEMINI_API_KEY")),
#     "3": os.getenv("GEMINI_API_KEY_3", os.getenv("GEMINI_API_KEY")),
#     "4": os.getenv("GEMINI_API_KEY_4", os.getenv("GEMINI_API_KEY")),
#     "5": os.getenv("GEMINI_API_KEY_5", os.getenv("GEMINI_API_KEY")),
#     "6": os.getenv("GEMINI_API_KEY_6", os.getenv("GEMINI_API_KEY")),
#     "7": os.getenv("GEMINI_API_KEY_7", os.getenv("GEMINI_API_KEY")),
# }
# Filter out None values
# apis = {k: v for k, v in apis.items() if v}

# Cyclic iterator for API keys
# api_cycle = itertools.cycle(apis.values())


class Agent:
    def __init__(self):
        self.chat_history = []
        self._setup_agent()

    def _setup_agent(self):
        # We will create the agent dynamically per request to handle API key rotation,
        # or we could just set it up once if we weren't rotating.
        # But to keep the "one class" structure for main.py, we'll initialize basic things here.

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_INSTRUCTION),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ])

    async def process_message(self, user_message: str):
        """
        Process a user message using LangChain AgentExecutor.
        """
        try:
            # Determine which LLM to use
            llm_provider = os.getenv("LLM_PROVIDER", "gemini").lower()
            
            if llm_provider == "openai":
                from langchain_openai import ChatOpenAI
                print("DEBUG: Using OpenAI")
                llm = ChatOpenAI(
                    model="gpt-4o",
                    api_key=os.getenv("OPENAI_API_KEY"),
                    temperature=0
                )
            else:
                # Default to Gemini
                # Fallback to single key if cycle not defined
                try:
                   next_key = next(api_cycle)
                   print(f"DEBUG: Using Gemini API Key from rotation...")
                except NameError:
                   next_key = os.getenv("GEMINI_API_KEY")
                   print(f"DEBUG: Using Single Gemini API Key")
                   
                llm = ChatGoogleGenerativeAI(
                    model="gemini-2.0-flash-exp",
                    google_api_key=next_key,
                    temperature=0
                )

            # Create Agent
            agent = create_tool_calling_agent(llm, tools, self.prompt)
            agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

            # Execute
            response_dict = await agent_executor.ainvoke({
                "input": user_message, 
                "chat_history": self.chat_history
            })
            
            response_text = response_dict["output"]
            
            # Update memory
            self.chat_history.append(HumanMessage(content=user_message))
            self.chat_history.append(AIMessage(content=response_text))
            
            # Keep history manageable (last 10 messages = 5 turns)
            if len(self.chat_history) > 10:
                self.chat_history = self.chat_history[-10:]

            return response_text

        except Exception as e:
            traceback.print_exc()
            return f"Error processing message: {str(e)}"
