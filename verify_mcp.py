import asyncio
from tools import ZomatoClient, list_tools

async def verify():
    print("Verifying Zomato MCP connection...")
    try:
        async with ZomatoClient():
            tools = await list_tools()
            print(f"Successfully connected! Found {len(tools.tools)} tools.")
            for t in tools.tools:
                print(f"- {t.name}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Verification failed: {e}")

if __name__ == "__main__":
    asyncio.run(verify())
