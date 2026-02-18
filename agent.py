import os
import google.generativeai as genai
from google.ai.generativelanguage_v1beta.types import content
from config import GEMINI_API_KEY
from tools import search_restaurants, get_menu, create_cart, get_tracking_info, get_saved_addresses, checkout_cart, login_step_1, login_step_2
import traceback

genai.configure(api_key=GEMINI_API_KEY)

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
    "1": "[REDACTED_API_KEY]",
   
}


model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    tools=tools,
    system_instruction=SYSTEM_INSTRUCTION
)

import itertools
api_cycle = itertools.cycle(apis.values())

class Agent:
    def __init__(self):
        # Disable automatic function calling so we can handle async tools manually
        self.chat = model.start_chat(enable_automatic_function_calling=False)
        self.tools_map = {t.__name__: t for t in tools}

    async def process_message(self, user_message: str):
        """
        Process a user message and return the response, handling tool calls manually.
        """
        try:
            # Rotate API Key
            next_key = next(api_cycle)
            print(f"DEBUG: Using API Key ending in ...{next_key[-4:]}")
            genai.configure(api_key=next_key)

            # Send initial message
            response = await self.chat.send_message_async(user_message)
            
            # Loop to handle function calls if any
            # We check if the response contains function calls
            # The simplified check is to look at parts
            while response.parts and any(part.function_call for part in response.parts):
                
                # Prepare parts for the next request (outputs)
                next_parts = []
                
                for part in response.parts:
                    if part.function_call:
                        fn_name = part.function_call.name
                        fn_args = dict(part.function_call.args)
                        
                        # print(f"Calling tool: {fn_name} with {fn_args}") # Debug
                        
                        # Helper to recursively convert proto types to dict/list
                        def to_native(obj):
                            try:
                                # Check if it's a MapComposite (dict-like) - Check this FIRST
                                if hasattr(obj, 'items'):
                                    return {k: to_native(v) for k, v in obj.items()}
                                # Check if it's a RepeatedComposite (list-like)
                                elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, dict)):
                                    return [to_native(i) for i in obj]
                                else:
                                    return obj
                            except:
                                return obj

                        # Convert arguments to native python types
                        native_fn_args = {k: to_native(v) for k, v in fn_args.items()}

                        result_content = {}
                        if fn_name in self.tools_map:
                            tool_func = self.tools_map[fn_name]
                            try:
                                # Await the async tool function
                                # print(f"Executing {fn_name}...")
                                tool_result = await tool_func(**native_fn_args)
                                result_content = {"result": tool_result}
                            except Exception as e:
                                result_content = {"error": str(e)}
                        else:
                            result_content = {"error": f"Tool {fn_name} not found."}
                        
                        # Create the FunctionResponse part
                        # We use the raw dictionary format which the SDK accepts for 'parts'
                        # or specifically construct the protobuf object if needed.
                        # The SDK `send_message` usually accepts a list of Parts.
                        
                        next_parts.append(
                            content.Part(
                                function_response=content.FunctionResponse(
                                    name=fn_name,
                                    response=result_content
                                )
                            )
                        )
                
                # If we collected function responses, send them back to the model
                if next_parts:
                    response = await self.chat.send_message_async(next_parts)
                else:
                    # Should not happen if loop condition met, but break just in case
                    break
            
            return response.text
        except Exception as e:
            traceback.print_exc()
            return f"Error processing message: {str(e)}"
