# 🤖 Custom LLM Character AI Telegram Bot

An asynchronous Telegram bot powered by LLM integration, featuring customizable **Character AI personalities** and **long-term conversation memory**

---
## 🎯 Goals

- Create an authentic AI character capable of remembering users, conversations, and context across restarts.
- Provide a clean, modular **Python (Asyncio)** framework for LLM-powered Telegram bots.
---

## 🧠 Human Behavior Replication & Architecture

### 1. Persona & System Prompts (`persona.py` / `persons.py`)
The character's identity, mood, guidelines, and behavioral traits are defined in a dedicated prompt file. The system injects this instruction into every LLM request to maintain a consistent personality and tone.

### 2. Long-Term Memory System (`memory/long_term.py` & `diary.db`)
* **Context Persistence:** Past interactions, facts, and user preferences are automatically stored in an SQLite database (`diary.db`).
* **Dynamic Context Injection:** Before sending a prompt to the LLM, the handler (`handlers/function.py`) queries the long-term memory for relevant entries and appends them to the system prompt.
* **Token Optimization:** Cleans up or structures conversation history so the context window remains lightweight without losing critical details.
---

## 🚀 Quick Start & Deployment

### Prerequisites
```bash
Python 3.10+
Telegram Bot Token (Obtained from [@BotFather](https://t.me/BotFather))
AI API Key (OpenAI, Groq, or custom LLM endpoint)
```
## Setup Steps
1. Clone the Repository
git clone https://github.com/Mrcat201006/AI-Telegram-bot.git cd AI-Telegram-bot
2. Create Virtual Environment
Linux / macOS:
python3 -m venv .venv
source .venv/bin/activate
Windows:
python -m venv .venv
.venv\Scripts\activate
3. Install Dependencies
pip install -r requirements.txt

## ⚙️ Configuration
Before launching the bot, you must set up the environment variables and character persona.
1. Configure .env
Create a .env file in the root directory:
  BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyZ
  API_KEY=your_ai_service_api_key_here
2. Define the Persona (persona.py or persons.py)
Create persona.py (or persons.py) in the project root to set up your character's behavior:
  # persona.py
  SYSTEM_PROMPT = """
  You are an intelligent, empathetic AI character.
  You remember details about the user, maintain your distinct personality, 
  and answer questions accurately and naturally.
  """
  ⚠️ Note on File Naming:
  If your script imports from persons.py instead of persona.py, make sure the filename matches the import statement inside handlers/function.py or main.py:
  from persona import SYSTEM_PROMPT  # or: from persons import SYSTEM_PROMPT

## 🛠️ Execution
Start the bot:
  python main.py

## Community
- **Telegram**: https://t.me/mrcat201006me

## 📁 Project Structure
```text
AI-Telegram-bot/
├── handlers/
│   ├── function.py       # Core LLM processing and prompt management
│   └── routes.py         # Telegram event handlers and commands
├── memory/
│   ├── long_term.py      # Long-term memory engine (database operations)
│   └── diary.db          # SQLite database (auto-generated)
├── main.py               # Main application entry point
├── persona.py            # LLM Character AI configuration & system prompt
├── .env                  # API keys and environment variables
├── .gitignore            # Git exclusion settings
└── requirements.txt      # Python dependencies


