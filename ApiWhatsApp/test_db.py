import os
import asyncio
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import ssl

load_dotenv()

async def run():
    _connect_args = {"statement_cache_size": 0}
    if 'supabase' in os.getenv('DATABASE_URL'):
        _connect_args['ssl'] = ssl._create_unverified_context()
    engine = create_async_engine(os.getenv('DATABASE_URL'), connect_args=_connect_args)
    async with engine.begin() as conn:
        res = await conn.execute(text("SELECT id, status FROM whatsapp_notifications ORDER BY created_at DESC LIMIT 5"))
        for row in res.fetchall():
            print(row)
    await engine.dispose()

if __name__ == '__main__':
    asyncio.run(run())
