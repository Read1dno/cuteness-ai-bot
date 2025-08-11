import hashlib
import io
from typing import Optional, Tuple
from PIL import Image
import numpy as np
from nudenet import NudeDetector
from database import db
from config import RAW_MIN, RAW_MAX

import os
import tempfile

detector = NudeDetector()

def calculate_image_hash(image_bytes: bytes) -> str:
    return hashlib.sha256(image_bytes).hexdigest()

def calculate_perceptual_hash(image_bytes: bytes) -> str:
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        img = img.resize((8, 8), Image.Resampling.LANCZOS)
        pixels = np.array(img)
        avg = pixels.mean()
        bits = ''.join('1' if pixel.mean() > avg else '0' for row in pixels for pixel in row)
        return bits
    except Exception:
        return ""

def hamming_distance(hash1: str, hash2: str) -> int:
    if not hash1 or not hash2 or len(hash1) != len(hash2):
        return 9999
    return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))

async def check_duplicate_image(user_id: int, image_bytes: bytes, similarity_threshold: int = 5) -> Tuple[bool, Optional[int]]:
    img_hash = calculate_image_hash(image_bytes)
    perceptual_hash = calculate_perceptual_hash(image_bytes)

    row = await db.fetchrow('SELECT user_id FROM image_hashes WHERE image_hash=$1', img_hash)
    if row:
        return True, row['user_id']

    if perceptual_hash:
        all_hashes = await db.fetch('SELECT user_id, perceptual_hash FROM image_hashes')
        for r in all_hashes:
            stored_hash = r['perceptual_hash']
            if stored_hash and hamming_distance(perceptual_hash, stored_hash) <= similarity_threshold:
                return True, r['user_id']

    await db.execute(
        'INSERT INTO image_hashes (user_id, image_hash, perceptual_hash) VALUES ($1, $2, $3)',
        user_id, img_hash, perceptual_hash
    )

    return False, None

async def get_user_warnings(user_id: int) -> Tuple[int, bool]:
    row = await db.fetchrow('SELECT warnings, banned FROM user_warnings WHERE user_id=$1', user_id)
    if row:
        return int(row['warnings']), bool(row['banned'])
    return 0, False

async def add_warning(user_id: int) -> Tuple[int, bool]:
    row = await db.fetchrow('SELECT warnings FROM user_warnings WHERE user_id=$1', user_id)
    if row:
        new_warnings = int(row['warnings']) + 1
        banned = 1 if new_warnings >= 2 else 0
        await db.execute('UPDATE user_warnings SET warnings=$1, banned=$2 WHERE user_id=$3', new_warnings, banned, user_id)
    else:
        new_warnings = 1
        banned = 0
        await db.execute('INSERT INTO user_warnings (user_id, warnings, banned) VALUES ($1, $2, $3)', user_id, new_warnings, banned)
    return new_warnings, bool(banned)

async def is_nsfw(image_bytes: bytes) -> bool:
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as f:
            f.write(image_bytes)
            temp_file = f.name
        
        results = detector.detect(temp_file)
        for r in results:
            if 'EXPOSED' in r.get('class', ''):
                return True
    except Exception as e:
        print(f"NSFW detection error: {e}")
        return False
    finally:
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
            except:
                pass
    return False

def map_score(raw: float) -> int:
    raw = max(RAW_MIN, min(raw, RAW_MAX))
    pct = (raw - RAW_MIN) / (RAW_MAX - RAW_MIN) * 100
    return int(round(pct))
