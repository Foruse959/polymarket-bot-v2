"""Test Telegram bot initialization directly"""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from telegram.ext import Application

token = os.getenv('TELEGRAM_BOT_TOKEN')
print(f"Token: {token[:10]}...")

async def test():
    print("Building app...")
    app = Application.builder().token(token).build()
    
    print("Initializing...")
    try:
        await app.initialize()
        print("Initialize OK")
    except Exception as e:
        print(f"Initialize failed: {e}")
        return
    
    print("Getting me...")
    me = await app.bot.get_me()
    print(f"Bot: {me.first_name} (@{me.username})")
    
    print("Starting...")
    await app.start()
    print("Started OK")
    
    print("Starting polling...")
    await app.updater.start_polling(drop_pending_updates=True)
    print("Polling started!")
    
    # Run for 5 seconds
    await asyncio.sleep(5)
    
    print("Stopping...")
    await app.updater.stop()
    await app.stop()
    await app.shutdown()
    print("Done!")

asyncio.run(test())
