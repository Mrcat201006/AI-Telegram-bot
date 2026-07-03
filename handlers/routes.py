import asyncio
from os import getenv
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import (Message , CallbackQuery, ReplyKeyboardMarkup, 
                           KeyboardButton , InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from dotenv import load_dotenv
from datetime import datetime,timedelta
from memory.long_term import LongTermMemory
from persona import BOT_PROMPT
from groq import AsyncGroq


load_dotenv()
api_key =getenv("API_KEY")

client = AsyncGroq(api_key=api_key)

long_memory = LongTermMemory()

#Краткосрочная память: user_id -> список сообщений
chat_history = {}

#Мы храним время активности для КАЖДОГО пользователя отдельно
user_last_active = {}

router = Router()


def get_main_reply_keybord():
    keybord = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="бот туралы")],
            [KeyboardButton(text="көмек")] 
        ],
        resize_keyboard=True
    )
    return keybord


# === НОВАЯ ФУНКЦИЯ ДЛЯ ОЦЕНКИ ВАЖНОСТИ ===
async def evaluate_importance(text: str) -> int:
    """
    Нейросеть решает, нужно ли сохранять сообщение в базу навсегда (от 1 до 10).
    """
    system_instruction = f"""
    Оцени от 1 до 10, содержит ли этот текст важный факт о пользователе, 
    который боту нужно запомнить (имя, хобби, факты, учеба, планы).
    Обычная болтовня вроде "привет", "ок", "помоги" = 1.
    Текст: "{text}"
    Ответь ТОЛЬКО ОДНОЙ ЦИФРОЙ.
    """
    try:
        response = await client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct", 
            messages=[{"role": "system", "content": system_instruction},
                {"role": "user", "content": f'Текст пользователя: "{text}"'}],
            max_tokens=20,
            temperature=0.1
        )
        score_str = response.choices[0].message.content.strip()
        
        # 1. Если ИИ вернул пустоту (твоя ошибка)
        if not score_str:
            print("⚠️ ИИ прислал пустой ответ. Ставим важность 1.")
            return 1
            
        # 2. Если ИИ прислал не цифру, а текст (например, "Оценка 5" или "Ок")
        if not score_str.isdigit():
            print(f"⚠️ ИИ прислал текст вместо цифры: '{score_str}'. Ставим важность 1.")
            return 1
        
        # Если всё хорошо и там чистая цифра — превращаем в int и возвращаем
        return int(score_str)
    
    except Exception as e:
        print(f"Ошибка ИИ при оценке: {e}")
        return 1 # Если ИИ запнулся, считаем сообщение неважным


@router.message(Command("start"))
async def start(message: Message):
    await message.answer("ai ботына қош келдіңіз!")
        

@router.message(Command('help'))
@router.message(F.text.lower() == "көмек")
async def help(message: Message):
    await message.answer(
        "Командалар:\n /help - команда тізімі\n /about - бот сипаттамасы\n",
        reply_markup=get_main_reply_keybord()
    )
    
    
@router.message(Command("about"))
@router.message(F.text.lower() == "бот туралы")
async def about(message: Message):
    await message.answer("Бұл бот регестрация командасын қолданылуын көрсету үшін арналған")
    

@router.message()
async def generete_response(message: Message):
    user_id = message.from_user.id
    user_text = message.text
    current_time = datetime.now()


    #-------краткосрочная память (временная)-------
    # Очистка по времени
    # Проверяем, общался ли человек с нами раньше
    if user_id in user_last_active:
        # Если он молчал дольше 2 часов, забываем контекст ЕГО диалога
        if current_time - user_last_active[user_id] > timedelta(hours=2):
            chat_history[user_id] = []
            print(f"🧹 История пользователя {user_id} забыта из-за долгого молчания.")
            
    user_last_active[user_id] = current_time        
            
            
    # Проверяем, есть ли уже история для этого пользователя
    if user_id not in chat_history:
        chat_history[user_id] = []
        
    # Добавляем сообщение пользователя в историю
    chat_history[user_id].append({"role": "user", "content": user_text})
    
    # Ограничиваем длину истории
    if len(chat_history[user_id]) > 20:
        chat_history[user_id] = chat_history[user_id][-20:]
    
    
    #-------долгосрочная память (SQLite)-------
    importance_score = await evaluate_importance(user_text)
    print(f"Оценка важности от ИИ: {importance_score}/10")
    
    # Сохраняем в базу только если оценка 6 или выше
    if importance_score >= 6:
        await long_memory.add_memory(
            user_id=user_id,
            content=f"Пользователь: {user_text}",
            importance=importance_score
        )
        print("💾 Важный факт сохранен в долгосрочную память!")
        
        
     # Достаем старые важные воспоминания из базы (если они есть)
    recent_memories = await long_memory.get_recent(user_id, limit=8)
    long_context = "\n".join(recent_memories) if recent_memories else "Пока нет воспоминаний."
    
    #-----Ответ бота с учетом краткосрочной и долгосрочной памяти-----
       
    # Склеиваем характер бота (из файла persona.py) и воспоминания
    system_prompt = f"{BOT_PROMPT}\n\nВот важные воспоминания об этом пользователе:\n{long_context}"
        
    messages = [
        {"role": "system", "content": system_prompt},
    ] + chat_history[user_id]    
        
        
    response =  await client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=messages,
        max_tokens=1000,
        temperature=0.7
        )
    
    bot_reply = response.choices[0].message.content
    
    chat_history[user_id].append({"role": "assistant", "content": bot_reply})
    
    await message.answer(bot_reply)

    
