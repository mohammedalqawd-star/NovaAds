import os, sqlite3, asyncio
from .config import settings

class DB:
    def __init__(self):
        path = settings.database_url.replace("sqlite:///", "")
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    async def init(self):
        def work():
            with sqlite3.connect(self.path) as c:
                c.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, credits INTEGER NOT NULL, referrals INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
                c.execute("CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, kind TEXT, status TEXT, input_path TEXT, output_path TEXT, error TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
                c.commit()
        await asyncio.to_thread(work)
    async def user(self, uid, username=None):
        def work():
            with sqlite3.connect(self.path) as c:
                row=c.execute("SELECT id,username,credits,referrals FROM users WHERE id=?",(uid,)).fetchone()
                if not row:
                    c.execute("INSERT INTO users(id,username,credits) VALUES(?,?,?)",(uid,username or "",settings.free_credits)); c.commit()
                    return (uid,username or "",settings.free_credits,0)
                return row
        return await asyncio.to_thread(work)
    async def spend(self, uid):
        def work():
            with sqlite3.connect(self.path) as c:
                cur=c.execute("UPDATE users SET credits=credits-1 WHERE id=? AND credits>0",(uid,)); c.commit(); return cur.rowcount==1
        return await asyncio.to_thread(work)
    async def add_credits(self, uid, n):
        def work():
            with sqlite3.connect(self.path) as c: c.execute("UPDATE users SET credits=credits+? WHERE id=?",(n,uid)); c.commit()
        await asyncio.to_thread(work)
    async def job(self, uid, kind, inp, out=None, status="queued", error=None):
        def work():
            with sqlite3.connect(self.path) as c:
                cur=c.execute("INSERT INTO jobs(user_id,kind,status,input_path,output_path,error) VALUES(?,?,?,?,?,?)",(uid,kind,status,inp,out,error)); c.commit(); return cur.lastrowid
        return await asyncio.to_thread(work)
    async def set_job(self, jid, status, out=None, error=None):
        def work():
            with sqlite3.connect(self.path) as c: c.execute("UPDATE jobs SET status=?,output_path=?,error=? WHERE id=?",(status,out,error,jid)); c.commit()
        await asyncio.to_thread(work)
