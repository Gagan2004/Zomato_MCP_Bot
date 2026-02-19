import json
import os
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_core.tools import tool
from config import ZOMATO_MCP_COMMAND, ZOMATO_MCP_ARGS
from user_context import current_user_id
import database

# Global session for simplicity in this demo
session = None

async def list_tools():
    """List available tools from the MCP server."""
    if not session:
        return []
    result = await session.list_tools()
    return result

@tool
async def search_restaurants(keyword: str, address_id: str, limit: int = 20, min_price: int = None, max_price: int = None, min_rating: float = None, postback_params: str = None):
    """Search for restaurants. Default limit is 20. Pass postback_params to fetch next page."""
    if not session: return "MCP Session not active"
    
    args = {"keyword": keyword, "address_id": address_id, "page_size": limit}
    # Handle postback_params for pagination
    if postback_params:
        import json
        try:
            # If formatted as a stringified dict/json, parse it or pass as is depending on what MCP expects.
            # The MCP schema says it's an object with $ref, but implies it can be passed.
            # Let's assume the MCP tool accepts it as a raw dict or string.
            # Based on inspection, it's a "SearchPostbackParams" object.
            # if the input is a string, we might need to load it.
            if isinstance(postback_params, str):
                 params_dict = json.loads(postback_params)
                 args["postback_params"] = params_dict
            else:
                 args["postback_params"] = postback_params
        except Exception as e:
            print(f"DEBUG: Error processing postback_params: {e}")

    menu_filter = {}
    if min_price: menu_filter["min_price"] = min_price
    if max_price: menu_filter["max_price"] = max_price
    if min_rating: menu_filter["min_rating"] = min_rating
    
    if menu_filter:
        args["filter"] = menu_filter
        
    result = await session.call_tool("get_restaurants_for_keyword", args)
    
    # Debug: Check returned data
    # Parse and format the output
    content = result.content[0].text
    try:
        data = json.loads(content)
        items = []
        
        # Extract postback_params for the next page
        next_postback = data.get("postback_params")
        # specific to Zomato structure, sometimes it's nested
        
        if isinstance(data, list):
            items = data
            print(f"DEBUG: Data is a list of {len(items)} items")
        elif isinstance(data, dict):
             # Try common structure
             # Zomato sometimes puts promoted stats in 'restaurants' and organic in 'sections'
             # We should grab BOTH.
             
             # 1. Check 'restaurants'
             direct_items = data.get("restaurants", [])
             if direct_items:
                 print(f"DEBUG: Found {len(direct_items)} items in 'restaurants'")
                 items.extend(direct_items)
                 
             # 2. Check 'sections' -> 'SECTION_SEARCH_RESULT'
             sections = data.get("sections", {})
             if sections:
                 search_results = sections.get("SECTION_SEARCH_RESULT", [])
                 if search_results:
                     print(f"DEBUG: Found {len(search_results)} items in SECTION_SEARCH_RESULT")
                     items.extend(search_results)
             
             # Deduplicate by res_id to be safe
             seen_ids = set()
             unique_items = []
             for item in items:
                 info = item.get("info", item)
                 rid = info.get("res_id")
                 if rid and rid not in seen_ids:
                     seen_ids.add(rid)
                     unique_items.append(item)
             
             items = unique_items
        
        # If we have a list of items, format them nicely to ensure LLM sees all of them
        if items and isinstance(items, list):
            print(f"DEBUG: Found {len(items)} items. Formatting...")
            formatted_list = []
            for item in items:
                # Extract simplified info
                info = item.get("info", item)
                
                name = info.get("name", "Unknown")
                res_id = info.get("res_id", "N/A")
                rating = info.get("rating", {}).get("aggregate_rating", "N/A")
                if isinstance(info.get("rating"), str): rating = info.get("rating") 
                
                delivery_time = info.get("order", {}).get("delivery_time", "N/A")
                formatted_list.append(f"- {name} (ID: {res_id}) | Rating: {rating} | Time: {delivery_time}")
            
            output_str = "\n".join(formatted_list)
            if next_postback:
                # Return the postback params as a JSON string so the LLM can use it
                output_str += f"\n\n[Pagination] To see more results, call this tool again with postback_params='{json.dumps(next_postback)}'"
            return output_str
            
    except Exception as e:
        print(f"DEBUG: Error parsing/formatting: {e}")
        
    return content

@tool
async def get_menu(res_id: int, address_id: str):
    """Get the menu listing for a restaurant."""
    if not session: return "MCP Session not active"
    result = await session.call_tool("get_menu_items_listing", {"res_id": res_id, "address_id": address_id})
    return result.content[0].text

@tool
async def create_cart(res_id: int, address_id: str, items: list, payment_type: str = "upi_qr"):
    """Create a cart with the given items."""
    print(f"DEBUG: create_cart called with res_id={res_id}, address_id={address_id}, items={items}")
    if not session: return "MCP Session not active"
    try:
        if items:
            for item in items:
                # Zomato requires 'variant_id' to be present.
                # If the LLM passed 'id' which looks like a variant id (starts with v_), use it.
                if "variant_id" not in item and "id" in item:
                    if str(item["id"]).startswith("v_"):
                         item["variant_id"] = item["id"]
                    # If it starts with ctl_, it is a dish id, not variant. 
                    # But if we don't have variant_id, the API fails.
                    # We will try to rely on the LLM filtering, but let's at least not send malformed dicts.
                    
        cart_args = {
            "res_id": res_id, 
            "address_id": address_id, 
            "items": items,
            "payment_type": payment_type
        }
        import json
        print(f"DEBUG: calling create_cart with: {json.dumps(cart_args, indent=2)}")
        result = await session.call_tool("create_cart", cart_args)
        
        content = result.content[0].text
        # Try to parse cart_id
        try:
             import json
             # Zomato usually returns a Cart object which has an 'id'
             cart_data = json.loads(content)
             cart_id = cart_data.get("id") or cart_data.get("cart_id")
             if cart_id:
                  uid = current_user_id.get()
                  if uid:
                      database.log_cart_creation(uid, cart_id, res_id, items)
                      print(f"DEBUG: Logged cart {cart_id} for user {uid}")
        except Exception as db_e:
             # Handle non-string content gracefully
             print(f"DEBUG: Failed to log cart to DB. Full content: {content}. Error: {db_e}")
             
        return content
    except Exception as e:
        print(f"DEBUG: create_cart failed: {e}")
        return f"Error creating cart: {e}"

@tool
async def checkout_cart(cart_id: str):
    """Checkout the cart."""
    print(f"DEBUG: checkout_cart called with cart_id={cart_id}")
    if not session: return "MCP Session not active"
    try:
        result = await session.call_tool("checkout_cart", {"cart_id": cart_id})
        
        # Log successful checkout
        try:
             # If checkout doesn't raise exception, assume success or read status
             # Logic refinement: If we get a QR code, it means payment is PENDING.
             # "Completed" should probably be reserved for when we track it and it says confirmed.
             database.update_order_status(cart_id, "pending_payment")
             print(f"DEBUG: Updated order status for {cart_id} to pending_payment")
        except Exception as db_e:
             print(f"DEBUG: Failed to update order status: {db_e}")

        outputs = []
        for content in result.content:
            if hasattr(content, 'text'):
                outputs.append(content.text)
            elif hasattr(content, 'image'):
                # Save the image to a file so we can view/send it
                try:
                    print("DEBUG: Image content found in checkout response.")
                    import base64
                    img_data = base64.b64decode(content.data)
                    filename = f"qrcodes/checkout_{cart_id}.png"
                    os.makedirs("qrcodes", exist_ok=True)
                    with open(filename, "wb") as f:
                        f.write(img_data)
                    print(f"DEBUG: Saved QR code to {filename}")
                    outputs.append(f"[QR Code Image Saved to {filename}]")
                    # In a real bot, we'd send this file back. 
                    # For local testing, knowing the path is enough.
                except Exception as img_e:
                    print(f"DEBUG: Failed to save QR image: {img_e}")
                    outputs.append("[QR Code Image Received but failed to save]")
                    
            elif hasattr(content, 'data'): # ImageContent has .data (base64)
                 try:
                    import base64
                    img_data = base64.b64decode(content.data)
                    filename = f"qrcodes/checkout_{cart_id}.png"
                    os.makedirs("qrcodes", exist_ok=True)
                    with open(filename, "wb") as f:
                        f.write(img_data)
                    print(f"DEBUG: Saved QR code to {filename}")
                    outputs.append(f"[QR Code Image Saved to {filename}]")
                 except Exception as img_e:
                     print(f"DEBUG: Failed to save QR image: {img_e}")
                     outputs.append("[QR Code Image Received but failed to save]")
            else:
                 outputs.append(str(content))
                 
        return "\n".join(outputs)
    except Exception as e:
        print(f"DEBUG: checkout_cart failed: {e}")
        return f"Error checking out cart: {e}"

# Global storage for auth flow (demo purpose)
auth_packet_cache = {}

@tool
async def login_step_1(phone_number: str):
    """Initiate login with phone number."""
    if not session: return "MCP Session not active"
    result = await session.call_tool("bind_user_number", {"phone_number": phone_number})
    # The result usually contains the auth_packet string or object
    # For this MCP, we might need to parse it, but for now let's store the raw text if it's a string,
    # or rely on the user to provide the code.
    # Actually, the tool output likely describes what to do.
    # But for the next step, we need the auth_packet. 
    # Let's assume the MCP implementation handles state or returns it.
    # If it returns a JSON string, we might need to parse it.
    auth_packet_cache['last'] = result.content[0].text # simplified
    return result.content[0].text

@tool
async def login_step_2(code: str):
    """Verify login OTP."""
    if not session: return "MCP Session not active"
    # We need the auth_packet from step 1. 
    # In a real app, this would be cleaner.
    # Here we'll pass the 'last' cached result as auth_packet.
    if 'last' not in auth_packet_cache:
        return "Please run login_step_1 first."
        
    import json
    try:
        # Try to parse the last output as JSON if it's a structure
        auth_packet = json.loads(auth_packet_cache['last'])
    except:
        # If not json, maybe it's just the object text? 
        # For the Zomato MCP, the internal tool expects the exact object returned by bind.
        # We will try passing the raw text or the parsed dict.
        auth_packet = auth_packet_cache['last']

    result = await session.call_tool("bind_user_number_verify_code", {
        "auth_packet": auth_packet,
        "code": code
    })
    return result.content[0].text

@tool
async def get_tracking_info():
    """Get current order tracking info."""
    if not session: return "MCP Session not active"
    result = await session.call_tool("get_order_tracking_info", {})
    
    content = result.content[0].text
    # Parse info to update DB if possible
    try:
        import json
        tracking_data = json.loads(content)
        if isinstance(tracking_data, list):
             for order in tracking_data:
                 # Extract status from order structure
                 # Structure varies, looking for common keys
                 status = "unknown"
                 # Example: order -> order_status or similar
                 if "order_status" in order: status = order["order_status"]
                 elif "status" in order: status = order["status"]
                 
                 # Also try to find cart_id/order_id to link
                 cart_id = order.get("cart_id") or order.get("order_id") # Zomato uses order_id usually after checkout
                 
                 if cart_id and status != "unknown":
                      database.update_order_status(str(cart_id), status)
                      
    except Exception as e:
        print(f"DEBUG: Failed to sync tracking status to DB: {e}")
        
    return content

@tool
async def get_saved_addresses():
    """Get user's saved addresses."""
    if not session: return "MCP Session not active"
    result = await session.call_tool("get_saved_addresses_for_user", {})
    print(f"DEBUG: get_saved_addresses result: {result.content[0].text}")
    return result.content[0].text

class ZomatoClient:
    def __init__(self):
        self.server_params = StdioServerParameters(
            command=ZOMATO_MCP_COMMAND,
            args=ZOMATO_MCP_ARGS,
            env=os.environ
        )
        self.session = None
        self.exit_stack = None

    async def __aenter__(self):
        global session
        self.client = stdio_client(self.server_params)
        self.read, self.write = await self.client.__aenter__()
        self.session = ClientSession(self.read, self.write)
        await self.session.__aenter__()
        await self.session.initialize()
        session = self.session
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        global session
        try:
            if self.session:
                await self.session.__aexit__(exc_type, exc_val, exc_tb)
            if self.client:
                await self.client.__aexit__(exc_type, exc_val, exc_tb)
        except RuntimeError as e:
            # Ignore "Cannot close a running event loop" errors during shutdown
            if "Cannot close a running event loop" not in str(e):
                print(f"Error during shutdown: {e}")
        except Exception as e:
            print(f"Error during shutdown: {e}")
        finally:
            session = None
