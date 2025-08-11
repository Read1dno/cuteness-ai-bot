import asyncpg
from typing import Any, List, Optional
from config import DATABASE_URL

_pool: Optional[asyncpg.Pool] = None

async def init_db() -> None:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with _pool.acquire() as conn:
        await conn.execute('''
        CREATE TABLE IF NOT EXISTS images (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            username TEXT,
            message_id BIGINT NOT NULL,
            image_hash TEXT NOT NULL,
            raw_score REAL,
            nsfw INTEGER,
            approved INTEGER DEFAULT 0,
            filename TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ''')
        await conn.execute('''
        CREATE TABLE IF NOT EXISTS user_avatars (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            userpic TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ''')
        await conn.execute('''
        CREATE TABLE IF NOT EXISTS user_warnings (
            user_id BIGINT PRIMARY KEY,
            warnings INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0
        );
        ''')
        await conn.execute('''
        CREATE TABLE IF NOT EXISTS image_hashes (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            image_hash TEXT NOT NULL,
            perceptual_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ''')
        try:
            await conn.execute('ALTER TABLE images ADD COLUMN filename TEXT;')
        except asyncpg.exceptions.DuplicateColumnError:
            pass
        except Exception:
            pass
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_image_hash ON image_hashes(image_hash);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_perceptual_hash ON image_hashes(perceptual_hash);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_user_warnings ON user_warnings(user_id);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_user_avatars ON user_avatars(user_id);')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_images_score ON images(raw_score DESC) WHERE nsfw=0 AND approved=1;')

async def close_db() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None

async def fetch(query: str, *args: Any) -> List[asyncpg.Record]:
    global _pool
    if _pool is None:
        await init_db()
    async with _pool.acquire() as conn:
        return await conn.fetch(query, *args)

async def fetchrow(query: str, *args: Any) -> Optional[asyncpg.Record]:
    global _pool
    if _pool is None:
        await init_db()
    async with _pool.acquire() as conn:
        return await conn.fetchrow(query, *args)

async def execute(query: str, *args: Any) -> None:
    global _pool
    if _pool is None:
        await init_db()
    async with _pool.acquire() as conn:
        await conn.execute(query, *args)