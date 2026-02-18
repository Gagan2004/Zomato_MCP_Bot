import os
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from config import ZOMATO_MCP_COMMAND, ZOMATO_MCP_ARGS

# Global session for simplicity in this demo
session = None

async def list_tools():
    """List available tools from the MCP server."""
    if not session:
        return []
    result = await session.list_tools()
    return result

async def search_restaurants(keyword: str, address_id: str, min_price: int = None, max_price: int = None, min_rating: float = None):
    """Search for restaurants based on a keyword and filters."""
    if not session: return "MCP Session not active"
    
    args = {"keyword": keyword, "address_id": address_id}
    menu_filter = {}
    if min_price: menu_filter["min_price"] = min_price
    if max_price: menu_filter["max_price"] = max_price
    if min_rating: menu_filter["min_rating"] = min_rating
    
    if menu_filter:
        args["filter"] = menu_filter
        
    result = await session.call_tool("get_restaurants_for_keyword", args)
    return result.content[0].text

async def get_menu(res_id: int, address_id: str):
    """Get the menu listing for a restaurant."""
    if not session: return "MCP Session not active"
    result = await session.call_tool("get_menu_items_listing", {"res_id": res_id, "address_id": address_id})
    return result.content[0].text

async def create_cart(res_id: int, address_id: str, items: list, payment_type: str = "upi_qr"):
    """Create a cart with the given items."""
    print(f"DEBUG: create_cart called with res_id={res_id}, address_id={address_id}, items={items}")
    if not session: return "MCP Session not active"
    try:
        result = await session.call_tool("create_cart", {
            "res_id": res_id, 
            "address_id": address_id, 
            "items": items,
            "payment_type": payment_type
        })
        return result.content[0].text
    except Exception as e:
        print(f"DEBUG: create_cart failed: {e}")
        return f"Error creating cart: {e}"

async def checkout_cart(cart_id: str):
    """Checkout the cart."""
    print(f"DEBUG: checkout_cart called with cart_id={cart_id}")
    if not session: return "MCP Session not active"
    try:
        result = await session.call_tool("checkout_cart", {"cart_id": cart_id})
        return result.content[0].text
    except Exception as e:
        print(f"DEBUG: checkout_cart failed: {e}")
        return f"Error checking out cart: {e}"

# Global storage for auth flow (demo purpose)
auth_packet_cache = {}

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

async def get_tracking_info():
    """Get current order tracking info."""
    if not session: return "MCP Session not active"
    result = await session.call_tool("get_order_tracking_info", {})
    return result.content[0].text

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
