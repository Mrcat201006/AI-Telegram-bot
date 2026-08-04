import asyncio
from aiogram.types import  Message , Voice
from aiogram import F, Bot
import base64
import random
from io import BytesIO
from groq import AsyncGroq
from dotenv import load_dotenv
from os import getenv


load_dotenv()
api_key = getenv("API_KEY")
client = AsyncGroq(api_key=api_key)




async def parse_user_content(message: Message, bot: Bot) -> tuple[str, str | None] | None:
    
    user_text = ""
    image_base64 = None
    
    if message.text:
        user_text = message.text
    
    elif message.sticker:
        sticker_emoji = message.sticker.emoji or "✨"
        user_text = f"[Пользователь отправил тебе стикер: {sticker_emoji}]"
    
        
    elif message.video or message.document:
        await message.reply("Извини, я пока не умею обрабатывать видео и документы. Попробуй отправить текст или фото.")
        return None
        
    elif message.audio:
        user_text = await STT(message.audio, bot)
    
    elif message.voice:
        user_text = await STT(message.voice, bot)
    
    elif message.photo:
        user_text = message.caption or "Посмотри на эту картинку."
        try:
             # Скачиваем фото в оперативную память напрямую в байты
            photo = message.photo[-1]
            file_io = BytesIO()
            await bot.download(photo, destination=file_io)
                
            # Кодируем картинку в Base64 формат, который требует Groq Vision API
            image_base64 = base64.b64encode(file_io.getvalue()).decode("utf-8")
                
        except Exception as e:
            print(f"Ошибка при скачивании фото: {e}")
            await message.reply("Извини, не смогла загрузить твое фото. Попробуй еще раз.")
            return None
        
    return user_text, image_base64

#Speech-to-Text (STT) функция для обработки голосовых сообщений
async def STT(voice: Voice, bot: Bot) -> str:
    buffer = BytesIO()

    await bot.download(
        voice,
        destination=buffer
    )
    buffer.seek(0)
    buffer.name = "voice.ogg"

    result = await client.audio.transcriptions.create(
        file=buffer,
        model="whisper-large-v3"
    )

    return result.text

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
        Ответь ТОЛЬКО ОДНОЙ ЦИФРОЙ.
        """
    try:
        response = await client.chat.completions.create(
            model='llama-3.3-70b-versatile',
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