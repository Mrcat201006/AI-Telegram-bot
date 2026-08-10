import asyncio
from os import getenv
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import  Message , ChatMemberUpdated
from dotenv import load_dotenv
from datetime import datetime,timedelta
from memory.long_term import LongTermMemory
from persona import BOT_PROMPT
from groq import AsyncGroq
from handlers.function import parse_user_content, evaluate_importance, introduce_typos, send_human_like_response
from aiogram.enums import ChatType



load_dotenv()
api_key = getenv("API_KEY")
client = AsyncGroq(api_key=api_key)

long_memory = LongTermMemory()

#Краткосрочная память: user_id -> список сообщений
chat_history = {}

#Мы храним время активности для КАЖДОГО пользователя отдельно
user_last_active = {}

router = Router()

@router.my_chat_member()
async def bot_added(event: ChatMemberUpdated, bot: Bot):
    # Проверяем, что это группа или супергруппа
    if event.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    # Бота только что добавили
    if (
        event.new_chat_member.status in ("member", "administrator")
        and event.old_chat_member.status == "left"
    ):
        await bot.send_message(
            event.chat.id,
            "👋 Спасибо за приглашение!\n"
            "Этот бот работает только в личных сообщениях.\n"
            "Напишите мне: @ВашБот"
        )

        await bot.leave_chat(event.chat.id)


@router.message(Command("start"))
async def start(message: Message):
    await message.answer("ai ботына қош келдіңіз!")
        
        
        
        
@router.message(F.text | F.photo | F.sticker| F.video | F.audio | F.document | F.voice)
async def generete_response(message: Message, bot: Bot):
    user_id = message.from_user.id
    current_time = datetime.now()
    
    user_text = ""
    image_base64 = None 
    
    #-------Парсинг входящего сообщения-------
    parsed_result = await parse_user_content(message, bot)
    if parsed_result is None:
        return  # Если функция вернула None, значит произошла ошибка или неподдерживаемый формат

    user_text, image_base64 = parsed_result

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
    ] + chat_history[user_id][:-1]
    
    # Добавляем СВЕЖЕЕ сообщение в этот пакет
    if image_base64:
        # Если есть картинка, собираем специальный контент (текст + изображение)
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    }
                }
            ]
        })
    else:
        messages.append({"role": "user", "content": user_text})
    
    try:
        # Уведомляем пользователя, что бот "печатает/думает", пока идет долгий запрос к ИИ
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        
        response = await client.chat.completions.create(
            model='qwen/qwen3.6-27b',
            messages=messages,
            max_tokens=1100,
            temperature=0.7,
            reasoning_format="hidden"
        )
        bot_reply = response.choices[0].message.content
        
    except Exception as e:
        print(f"🛑 Критическая ошибка API: {e}")
        await message.reply("Ой, я немного зависла... Напиши еще раз чуть позже! 💔")
        return # Прерываем функцию, чтобы не сохранить пустой ответ в историю
    
    if not bot_reply or not bot_reply.strip():
            bot_reply = "Упс... Я слишком глубоко ушла в свои мысли и забыла, что хотела сказать! Попробуй спросить иначе. 😅"
    
    # Сохраняем чистый ответ бота в историю
    chat_history[user_id].append({"role": "assistant", "content": bot_reply})
    
    
    # Очеловечивание 
    human_text = introduce_typos(bot_reply, error_rate=0.03)  # x% шанс опечатки

    
        # Отправляем ответ пользователю, имитируя печать
    await send_human_like_response(
        bot=bot, 
        chat_id=message.chat.id, 
        full_text=human_text
    )

    
