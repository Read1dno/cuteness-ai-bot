from aiogram import Router, Bot, types
from aiogram.filters import Command
from aiogram.types import FSInputFile, CallbackQuery
import base64
import time
import uuid
import asyncio

from config import ADMIN_ID, RATE_LIMIT_SECONDS, TOP_THRESHOLD, STORAGE_CHAT_ID, IMAGES_DIR, CUTE_COMMANDS, NSFW_FILTER_ENABLED
from database import db
from utils import func
from model import model
from keyboards.messages import MESSAGES
from keyboards.inline_keyboards import show_image_kb, moderation_kb

router = Router()
_last_call: dict[int, float] = {}
_user_states: dict[int, str] = {}
_storage_queue = asyncio.Queue()

async def storage_worker(bot: Bot):
    while True:
        try:
            image_bytes = await _storage_queue.get()
            temp_path = IMAGES_DIR / f'storage_{uuid.uuid4().hex}.jpg'
            temp_path.write_bytes(image_bytes)
            try:
                await bot.send_photo(STORAGE_CHAT_ID, FSInputFile(temp_path))
                await asyncio.sleep(0.1)
            finally:
                if temp_path.exists():
                    temp_path.unlink()
        except Exception:
            pass

@router.message(Command(commands=['start']))
async def cmd_start(message: types.Message):
    await message.reply(MESSAGES["start"])

@router.message(Command(commands=['top']))
async def cmd_top(message: types.Message):
    rows = await db.fetch('''
        SELECT ROW_NUMBER() OVER (ORDER BY raw_score DESC) AS place, username, user_id, message_id, raw_score, filename
        FROM images WHERE nsfw=0 AND approved=1 ORDER BY raw_score DESC LIMIT 30
    ''')
    if not rows:
        await message.reply(MESSAGES["top_empty"])
        return
    text = MESSAGES["top_list_header"]
    for r in rows:
        text += f"{r['place']}) {r['username'] or 'аноним'} - {r['raw_score']:.4f}%\n"
    await message.reply(text, reply_markup=show_image_kb)

async def _save_image_record(user_id: int, username: str | None, message_id: int, raw: float, nsfw: int, image_hash: str, filename: str) -> int:
    await db.execute('''
        INSERT INTO images (user_id, username, message_id, image_hash, raw_score, nsfw, filename)
        VALUES ($1,$2,$3,$4,$5,$6,$7)
    ''', user_id, username, message_id, image_hash, raw, nsfw, filename)
    row = await db.fetchrow('SELECT id FROM images WHERE image_hash=$1 ORDER BY created_at DESC LIMIT 1', image_hash)
    return int(row['id']) if row else 0

async def _update_user_avatar(user_id: int, username: str | None, userpic_b64: str | None):
    existing = await db.fetchrow('SELECT userpic FROM user_avatars WHERE user_id=$1', user_id)
    if existing:
        if existing['userpic'] != userpic_b64:
            await db.execute('UPDATE user_avatars SET userpic=$1, username=$2 WHERE user_id=$3', userpic_b64, username, user_id)
    else:
        await db.execute('INSERT INTO user_avatars (user_id, username, userpic) VALUES ($1,$2,$3)', user_id, username, userpic_b64)

async def _cache_top_images(bot: Bot):
    rows = await db.fetch('''
        SELECT id, message_id, filename FROM images 
        WHERE nsfw=0 AND approved=1 AND filename IS NOT NULL
        ORDER BY raw_score DESC LIMIT 30
    ''')
    for row in rows:
        cache_path = IMAGES_DIR / row['filename']
        if not cache_path.exists():
            try:
                msg = await bot.forward_message(STORAGE_CHAT_ID, STORAGE_CHAT_ID, row['message_id'])
                if msg.photo:
                    file_obj = await bot.get_file(msg.photo[-1].file_id)
                    buf = await bot.download_file(file_obj.file_path)
                    cache_path.write_bytes(buf.getvalue())
                await bot.delete_message(STORAGE_CHAT_ID, msg.message_id)
            except Exception:
                pass

async def _find_duplicate_image_info(image_bytes: bytes):
    img_hash = func.calculate_image_hash(image_bytes)
    perceptual_hash = func.calculate_perceptual_hash(image_bytes)
    
    exact_match = await db.fetchrow('''
        SELECT i.filename, i.raw_score, i.user_id
        FROM images i
        INNER JOIN image_hashes ih ON i.image_hash = ih.image_hash
        WHERE ih.image_hash = $1
        LIMIT 1
    ''', img_hash)
    
    if exact_match:
        place_row = await db.fetchrow('SELECT COUNT(*)+1 AS place FROM images WHERE raw_score>$1', exact_match['raw_score'])
        exact_match = dict(exact_match)
        exact_match['place'] = int(place_row['place']) if place_row else 1
        return exact_match
    
    if perceptual_hash:
        all_hashes = await db.fetch('''
            SELECT ih.user_id, ih.perceptual_hash, i.filename, i.raw_score
            FROM image_hashes ih
            INNER JOIN images i ON ih.image_hash = i.image_hash
            WHERE ih.perceptual_hash IS NOT NULL
        ''')
        
        for r in all_hashes:
            stored_hash = r['perceptual_hash']
            if stored_hash and func.hamming_distance(perceptual_hash, stored_hash) <= 5:
                place_row = await db.fetchrow('SELECT COUNT(*)+1 AS place FROM images WHERE raw_score>$1', r['raw_score'])
                result = dict(r)
                result['place'] = int(place_row['place']) if place_row else 1
                return result
    
    return None

@router.message(Command(commands=['cute']))
async def cmd_cute(message: types.Message, bot: Bot):
    if message.reply_to_message and message.reply_to_message.photo:
        await process_cute_command(message, message.reply_to_message, bot)
    else:
        await process_cute_command(message, None, bot)

@router.message(lambda m: m.photo and m.caption and m.caption.lower().strip() in CUTE_COMMANDS)
async def handle_cute_photo_with_caption(message: types.Message, bot: Bot):
    await process_cute_command(message, message, bot)

@router.message(lambda m: m.text and m.text.lower().strip() in CUTE_COMMANDS)
async def handle_cute_text(message: types.Message, bot: Bot):
    if message.reply_to_message and message.reply_to_message.photo:
        await process_cute_command(message, message.reply_to_message, bot)
    else:
        await process_cute_command(message, None, bot)

async def process_cute_command(message: types.Message, photo_message: types.Message | None, bot: Bot):
    user = message.from_user
    user_id = user.id
    warnings, banned = await func.get_user_warnings(user_id)
    if banned:
        return
    now = time.time()
    last = _last_call.get(user_id, 0)
    if now - last < RATE_LIMIT_SECONDS:
        wait = int(RATE_LIMIT_SECONDS - (now - last))
        await message.reply(MESSAGES["rate_limited"].format(seconds=wait))
        return
    _last_call[user_id] = now
    target = photo_message or message
    if not target.photo:
        await message.reply(MESSAGES["no_image"])
        return
    file_obj = await bot.get_file(target.photo[-1].file_id)
    buf = await bot.download_file(file_obj.file_path)
    image_bytes = buf.getvalue()
    is_dup, orig_uid = await func.check_duplicate_image(user_id, image_bytes)
    if is_dup:
        if orig_uid == user_id:
            await message.reply(MESSAGES["duplicate_own"])
        else:
            dup_info = await _find_duplicate_image_info(image_bytes)
            if dup_info:
                caption = MESSAGES["duplicate_other_with_score"].format(
                    score=func.map_score(dup_info['raw_score']),
                    place=dup_info['place']
                )
                if dup_info['filename']:
                    cached_path = IMAGES_DIR / dup_info['filename']
                    if cached_path.exists():
                        await message.reply_photo(FSInputFile(cached_path), caption=caption)
                    else:
                        await message.reply(caption)
                else:
                    await message.reply(caption)
        return
    temp_path = IMAGES_DIR / f'temp_{uuid.uuid4().hex}.jpg'
    temp_path.write_bytes(image_bytes)
    try:
        nsfw_flag = 0
        if NSFW_FILTER_ENABLED:
            try:
                nsfw_flag = 1 if await func.is_nsfw(image_bytes) else 0
                if nsfw_flag:
                    await message.reply(MESSAGES["nsfw"])
                    return
            except Exception as e:
                print(f"NSFW check error: {e}")
                nsfw_flag = 0
        
        image_hash = func.calculate_image_hash(image_bytes)
        storage_msg = await bot.send_photo(STORAGE_CHAT_ID, FSInputFile(temp_path))
        await _storage_queue.put(image_bytes)
        userpic_b64 = None
        try:
            photos = await bot.get_user_profile_photos(user_id, limit=1)
            if photos.total_count > 0:
                file2 = await bot.get_file(photos.photos[0][-1].file_id)
                buf2 = await bot.download_file(file2.file_path)
                userpic_b64 = base64.b64encode(buf2.getvalue()).decode()
        except Exception:
            userpic_b64 = None
        await _update_user_avatar(user_id, user.username, userpic_b64)
        raw = await model.get_cuteness_score(image_bytes)
        score = func.map_score(raw)
        cached_filename = f'cached_{uuid.uuid4().hex}.jpg'
        cached_path = IMAGES_DIR / cached_filename
        cached_path.write_bytes(image_bytes)
        image_id = await _save_image_record(user_id, user.username, storage_msg.message_id, raw, nsfw_flag, image_hash, cached_filename)
        row = await db.fetchrow('SELECT COUNT(*)+1 AS rank FROM images WHERE raw_score>$1', raw)
        place = int(row['rank']) if row else 1
        top_images = []
        top_rows = await db.fetch('''
            SELECT filename FROM images 
            WHERE nsfw=0 AND approved=1 AND filename IS NOT NULL
            ORDER BY raw_score DESC LIMIT 4
        ''')
        for top_row in top_rows:
            top_path = IMAGES_DIR / top_row['filename']
            top_images.append(str(top_path) if top_path.exists() else None)
        while len(top_images) < 4:
            top_images.append(None)
        output_filename = f'result_{uuid.uuid4().hex}.png'
        output_path = IMAGES_DIR / output_filename
        from utils.stats_generator import process_image
        await process_image(score, place, user.username, userpic_b64, top_images, output_path)
        await message.reply_photo(FSInputFile(output_path), caption=MESSAGES["cute_result"].format(score=score, place=place))
        if place <= TOP_THRESHOLD:
            username_safe = user.username.replace('_', r'\_').replace('*', r'\*').replace('[', r'\[').replace(']', r'\]').replace('(', r'\(').replace(')', r'\)').replace('~', r'\~').replace('`', r'\`').replace('>', r'\>').replace('#', r'\#').replace('+', r'\+').replace('-', r'\-').replace('=', r'\=').replace('|', r'\|').replace('{', r'\{').replace('}', r'\}').replace('.', r'\.').replace('!', r'\!') if user.username else 'неизвестно'
            await bot.send_photo(
                chat_id=ADMIN_ID,
                photo=FSInputFile(cached_path),
                caption=f"🔍 Модерация\n👤 Пользователь: @{username_safe} (ID: {user_id})\n⭐ Оценка: {score}%\n🏆 Место: #{place}",
                reply_markup=moderation_kb(image_id)
            )
        if output_path.exists():
            output_path.unlink()
    finally:
        if temp_path.exists():
            temp_path.unlink()

@router.callback_query(lambda c: c.data == "show_image_request")
async def handle_show_image_request(callback: CallbackQuery):
    _user_states[callback.from_user.id] = "waiting_for_rank"
    await callback.message.answer(MESSAGES["ask_rank"])
    await callback.answer()

@router.message(lambda m: m.text and m.text.isdigit())
async def handle_rank_input(message: types.Message, bot: Bot):
    user_id = message.from_user.id
    if _user_states.get(user_id) != "waiting_for_rank":
        return
    rank = int(message.text)
    if rank < 1 or rank > 30:
        await message.reply(MESSAGES["rank_invalid"])
        return
    row = await db.fetchrow('''
        WITH ranked AS (
            SELECT message_id, username, raw_score, filename,
                   ROW_NUMBER() OVER (ORDER BY raw_score DESC) as place
            FROM images WHERE nsfw=0 AND approved=1
        )
        SELECT message_id, username, raw_score, filename, place FROM ranked WHERE place=$1
    ''', rank)
    if not row:
        await message.reply(MESSAGES["rank_not_found"].format(rank=rank))
        _user_states.pop(user_id, None)
        return
    try:
        username = row['username']
        username_link = f"[{username}](https://t.me/{username})" if username else "аноним"
        caption = MESSAGES["rank_result"].format(rank=rank, username_link=username_link, score=row['raw_score'])
        if row['filename']:
            cached_path = IMAGES_DIR / row['filename']
            if cached_path.exists():
                await message.reply_photo(FSInputFile(cached_path), caption=caption, parse_mode="Markdown")
            else:
                msg = await bot.forward_message(message.chat.id, STORAGE_CHAT_ID, row['message_id'])
                try:
                    await msg.edit_caption(caption, parse_mode="Markdown")
                except:
                    pass
        else:
            msg = await bot.forward_message(message.chat.id, STORAGE_CHAT_ID, row['message_id'])
            try:
                await msg.edit_caption(caption, parse_mode="Markdown")
            except:
                pass
    except Exception:
        await message.reply(MESSAGES["rank_load_error"])
    _user_states.pop(user_id, None)

@router.callback_query(lambda c: c.data.startswith('approve_'))
async def handle_approve(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer(MESSAGES["approve_no_permissions"])
        return
    image_id = int(callback.data.split('_', 1)[1])
    await db.execute('UPDATE images SET approved=1 WHERE id=$1', image_id)
    await callback.message.edit_caption(callback.message.caption + MESSAGES["approved_suffix"], reply_markup=None)
    await callback.answer(MESSAGES["approved"])
    await _cache_top_images(bot)

@router.callback_query(lambda c: c.data.startswith('ban_'))
async def handle_ban(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer(MESSAGES["approve_no_permissions"])
        return
    image_id = int(callback.data.split('_', 1)[1])
    row = await db.fetchrow('SELECT user_id, filename FROM images WHERE id=$1', image_id)
    if row:
        user_id = int(row['user_id'])
        await db.execute('UPDATE images SET approved=0 WHERE id=$1', image_id)
        if row['filename']:
            cached_path = IMAGES_DIR / row['filename']
            if cached_path.exists():
                try:
                    cached_path.unlink()
                except Exception:
                    pass
        await func.add_warning(user_id)
        warnings_row = await db.fetchrow('SELECT warnings, banned FROM user_warnings WHERE user_id=$1', user_id)
        warnings = int(warnings_row['warnings']) if warnings_row else 0
        banned = bool(warnings_row['banned']) if warnings_row else False
        try:
            if banned:
                await bot.send_message(user_id, MESSAGES["user_blocked_message"])
            else:
                await bot.send_message(user_id, MESSAGES["user_warn_message"].format(warnings=warnings))
        except Exception:
            pass
    await callback.message.edit_caption(callback.message.caption + MESSAGES["banned_suffix"], reply_markup=None)
    await callback.answer(MESSAGES["banned"])
    await _cache_top_images(bot)