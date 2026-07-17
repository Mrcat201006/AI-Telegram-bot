import asyncio
import io
import base64
import random
from os import getenv
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import  Message 
from dotenv import load_dotenv
from datetime import datetime,timedelta
from memory.long_term import LongTermMemory
from persona import BOT_PROMPT
from groq import AsyncGroq




load_dotenv()
api_key = getenv("API_KEY")
client = AsyncGroq(api_key=api_key)

long_memory = LongTermMemory()

#Краткосрочная память: user_id -> список сообщений
chat_history = {}

#Мы храним время активности для КАЖДОГО пользователя отдельно
user_last_active = {}

router = Router()

# =====================================================================
# Вспомогательные функции для очеловечивания (Опечатки и деление строк)
# =====================================================================

def introduce_typos(text: str, error_rate: float = 0.03) -> str:
    """
    Добавляет случайные человеческие опечатки в текст.
    error_rate = 0.03 означает 3% шанс опечатки в каждом слове.
    """
    if error_rate <= 0:
        return text

    words = text.split(' ')
    processed_words = []

    for word in words:
        # Делаем ошибку только в словах длиннее 3 букв
        if len(word) > 3 and random.random() < error_rate:
            word_list = list(word)
            typo_type = random.choice(['swap', 'skip', 'double'])
            idx = random.randint(1, len(word_list) - 2)

            if typo_type == 'swap':
                # Меняем местами соседние буквы
                word_list[idx], word_list[idx+1] = word_list[idx+1], word_list[idx]
            elif typo_type == 'skip':
                # Пропускаем букву
                word_list.pop(idx)
            elif typo_type == 'double':
                # Дублируем букву
                word_list.insert(idx, word_list[idx])

            word = "".join(word_list)
        
        processed_words.append(word)

    return " ".join(processed_words)





async def send_human_like_response(bot: Bot, chat_id: int, full_text: str):
    """
    Режет текст по знаку '|', имитирует печать и отправляет частями.
    """
    messages_to_send = [msg.strip() for msg in full_text.split('|') if msg.strip()]
    
    for text in messages_to_send:
        # Показываем статус "печатает..."
        await bot.send_chat_action(chat_id=chat_id, action="typing")
        
        # Считаем задержку: 0.05 сек на один символ (но не меньше 1 секунды)
        typing_delay = max(1, len(text) * 0.05)
        await asyncio.sleep(typing_delay)
        
        # Отправляем кусок текста
        await bot.send_message(chat_id=chat_id, text=text)

#===============================


# === ФУНКЦИЯ ДЛЯ ОЦЕНКИ ВАЖНОСТИ ===
async def evaluate_importance(text: str) -> int:
    """
    Нейросеть решает, нужно ли сохранять сообщение в базу навсегда (от 1 до 10).
    """
    prompt = f"""
        Оцени от 1 до 10, содержит ли этот текст важный факт о пользователе, 
        который боту нужно запомнить (имя, хобби, факты, учеба, планы).
        Обычная болтовня вроде "привет", "ок", "помоги" = 1.
        Текст: "{text}"
        Ответь ТОЛЬКО ОДНОЙ ЦИФРОЙ.
        """
    try:
        response = await client.chat.completions.create(
            model='meta-llama/llama-4-scout-17b-16e-instruct',
            messages=[{"role": "system", "content": prompt},
                {"role": "user", "content": f'Текст пользователя: "{text}"'}],
            max_tokens=20,
            temperature=0.1
        )
        
        answer_text = response.choices[0].message.content
        
        # 2. СНАЧАЛА проверяем, состоит ли строка только из цифр
        if answer_text.isdigit():
            # 3. И только теперь безопасно превращаем в число
            score = int(answer_text)
            
            # Небольшая защита от галлюцинаций (вдруг ИИ выдаст 100)
            if 1 <= score <= 10:
                return score
            else:
                return 1 # Если число вне диапазона, считаем неважным
        else:
            print(f"⚠️ Ответ не является числом: {answer_text}")
            return 1
        
    except Exception as e:
        print(f"Ошибка при оценке важности: {e}")
        return 1

@router.message(Command("start"))
async def start(message: Message):
    await message.answer("ai ботына қош келдіңіз!")
        
        
        
@router.message(F.text | F.photo | F.sticker| F.video | F.audio | F.document)
async def generete_response(message: Message, bot: Bot):
    user_id = message.from_user.id
    current_time = datetime.now()
    
    user_text = ""
    image_base64 = None 
    
    if message.text:
        user_text = message.text

    elif message.sticker:
        sticker_emoji = message.sticker.emoji or "✨"
        user_text = f"[Пользователь отправил тебе стикер: {sticker_emoji}]"

    
    elif message.video or message.audio or message.document:
        await message.reply("Извини, я пока не умею обрабатывать видео, аудио и документы. Попробуй отправить текст или фото.")
        return
        
    elif message.photo:
        user_text = message.caption or "Посмотри на эту картинку."
        try:
             # Скачиваем фото в оперативную память напрямую в байты
            photo = message.photo[-1]
            file_io = io.BytesIO()
            await bot.download(photo, destination=file_io)
            
            # Кодируем картинку в Base64 формат, который требует Groq Vision API
            image_base64 = base64.b64encode(file_io.getvalue()).decode("utf-8")
            
        except Exception as e:
            print(f"Ошибка при скачивании фото: {e}")
            await message.reply("Извини, не смогла загрузить твое фото. Попробуй еще раз.")
            return


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
            model='meta-llama/llama-4-scout-17b-16e-instruct',
            messages=messages,
            max_tokens=1000,
            temperature=0.7,
        )
        bot_reply = response.choices[0].message.content
        
    except Exception as e:
        print(f"🛑 Критическая ошибка API: {e}")
        await message.reply("Ой, я немного зависла... Напиши еще раз чуть позже! 💔")
        return # Прерываем функцию, чтобы не сохранить пустой ответ в историю
    
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

    
