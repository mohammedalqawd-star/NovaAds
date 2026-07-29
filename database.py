import aiosqlite
import os
from datetime import datetime

class Database:
    _instance = None
    
    def __new__(cls, db_path=None):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance.db_path = db_path or "nova_ads.db"
            cls._instance.connection = None
        return cls._instance
    
    async def connect(self):
        if self.connection is None:
            self.connection = await aiosqlite.connect(self.db_path)
            self.connection.row_factory = aiosqlite.Row
            await self.connection.execute("PRAGMA foreign_keys = ON")
        return self.connection
    
    async def close(self):
        if self.connection:
            await self.connection.close()
            self.connection = None
    
    async def execute(self, query, params=None):
        conn = await self.connect()
        if params:
            cursor = await conn.execute(query, params)
        else:
            cursor = await conn.execute(query)
        await conn.commit()
        return cursor
    
    async def fetchone(self, query, params=None):
        conn = await self.connect()
        if params:
            cursor = await conn.execute(query, params)
        else:
            cursor = await conn.execute(query)
        return await cursor.fetchone()
    
    async def fetchall(self, query, params=None):
        conn = await self.connect()
        if params:
            cursor = await conn.execute(query, params)
        else:
            cursor = await conn.execute(query)
        return await cursor.fetchall()
    
    async def initialize(self):
        conn = await self.connect()
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        await conn.executescript(schema_sql)
        await conn.commit()
        print("✅ تم إنشاء/تحديث قاعدة البيانات بنجاح")
        await self._insert_default_subscriptions()
    
    async def _insert_default_subscriptions(self):
        from config import Config
        for key, sub in Config.SUBSCRIPTIONS.items():
            existing = await self.fetchone(
                "SELECT id FROM subscriptions WHERE name = ?",
                (sub['name'],)
            )
            if not existing:
                await self.execute(
                    """INSERT INTO subscriptions 
                    (name, price, channels_limit, ads_limit, priority, features, is_active) 
                    VALUES (?, ?, ?, ?, ?, ?, 1)""",
                    (sub['name'], sub['price'], sub['channels_limit'], 
                     sub['ads_limit'], sub['priority'], sub['features'])
                )
