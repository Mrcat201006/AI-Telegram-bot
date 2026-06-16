import datetime
from os import getenv
import asyncio
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv
from handlers.routes import router
from memory.long_term import LongTermMemory

load_dotenv()
Token = getenv("bot_token")

dp = Dispatcher()
dp.include_router(router)


async def main():
    bot = Bot(token=Token)
    
    memory = LongTermMemory()
    await memory.init_db() 
       
    print("start..")
    
    await dp.start_polling(bot)
    
if __name__=="__main__":
    asyncio.run(main())