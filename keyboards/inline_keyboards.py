from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

show_image_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📷 Показать картинку", callback_data="show_image_request")]
])

def moderation_kb(image_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Approve", callback_data=f"approve_{image_id}"),
            InlineKeyboardButton(text="❌ Ban", callback_data=f"ban_{image_id}")
        ]
    ])
