# memory/long_term.py
import aiosqlite
import asyncio
import json
from datetime import datetime
from typing import List, Optional

class LongTermMemory:
    def __init__(self, db_path: str = "memory/diary.db"):
        self.db_path = db_path
    
    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    summary TEXT,
                    importance INTEGER DEFAULT 5,
                    tags TEXT
                )
            """)
            await db.commit()
            print("✅ Долгосрочная память (SQLite) инициализирована!")
    
    async def add_memory(self, user_id: int, content: str, summary: Optional[str] = None, 
                        importance: int = 5, tags: Optional[List[str]] = None):
        timestamp = datetime.now().isoformat()
        tags_json = json.dumps(tags or [])
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO memories 
                   (timestamp, user_id, content, summary, importance, tags) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (timestamp, user_id, content, summary or content[:400], importance, tags_json)
            )
            await db.commit()
    
    async def get_recent(self, user_id: int, limit: int = 15) -> List[str]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """SELECT content, timestamp FROM memories 
                   WHERE user_id = ? 
                   ORDER BY timestamp DESC LIMIT ?""",
                (user_id, limit)
            ) as cursor:
                rows = await cursor.fetchall()
                return [f"[{row[1][:16]}] {row[0]}" for row in rows]
    
    async def search_keyword(self, user_id: int, keyword: str, limit: int = 8) -> List[str]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """SELECT content FROM memories 
                   WHERE user_id = ? AND content LIKE ? 
                   ORDER BY importance DESC LIMIT ?""",
                (user_id, f"%{keyword}%", limit)
            ) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]