import base64
import pyvips
from pathlib import Path

template_dir = Path('pattern_images')
BASE_IMAGE_PATH = template_dir / 'base.png'
LINE_IMAGE_PATH = template_dir / 'line.png'
ABOUT_IMAGE_PATH = template_dir / 'about.png'
PLACEHOLDER_USER_PATH = template_dir / 'user.png'
TOP_PLACEHOLDERS = [template_dir / f'top_base{i}.png' for i in range(1, 5)]

MAX_SHIFT = 675
TEXT_POSITION = (755, 720)
AVATAR_POSITION = (132, 418)
AVATAR_SIZE = (150, 150)
NICK_POSITION = (318, 458)
PLACE_POSITION = (243, 136)
FONT_PT_VALUE = 150
FONT_PT_NICK = 90
FONT_PT_PLACE = 34
DPI = 72
FONT_VALUE = f'Sans Serif {FONT_PT_VALUE}'
FONT_NICK = f'Sans Serif {FONT_PT_NICK}'
FONT_PLACE = f'Sans Serif {FONT_PT_PLACE}'
PADDING = 10
CONTAINER_WIDTH = 550
TOP_POSITIONS = [(133, 202), (325, 202), (517, 202), (709, 202)]
TOP_SIZE = (178, 178)

async def process_image(
    value: int,
    place: int,
    nickname: str | None,
    userpic: str | None,
    tops: list[str | None],
    output_path: Path
) -> None:
    if not (0 <= value <= 100):
        raise ValueError('Value must be between 0 and 100')
    if len(tops) != 4:
        raise ValueError('tops must be a list of 4 elements')

    offset_x = int((value / 100 - 1) * MAX_SHIFT)

    base = pyvips.Image.new_from_file(str(BASE_IMAGE_PATH), access='sequential').colourspace('srgb')
    line = pyvips.Image.new_from_file(str(LINE_IMAGE_PATH), access='sequential').colourspace('srgb')
    image = base.composite2(line, 'over', x=offset_x, y=0)

    if userpic:
        data = base64.b64decode(userpic)
        avatar = pyvips.Image.new_from_buffer(data, '', access='sequential').colourspace('srgb')
    else:
        avatar = pyvips.Image.new_from_file(str(PLACEHOLDER_USER_PATH), access='sequential').colourspace('srgb')
    avatar = avatar.thumbnail_image(AVATAR_SIZE[0], height=AVATAR_SIZE[1])
    image = image.composite2(avatar, 'over', x=AVATAR_POSITION[0], y=AVATAR_POSITION[1])

    for idx, top_data in enumerate(tops):
        pos_x, pos_y = TOP_POSITIONS[idx]
        if top_data:
            top_img = pyvips.Image.new_from_file(str(top_data), access='sequential').colourspace('srgb')
        else:
            top_img = pyvips.Image.new_from_file(str(TOP_PLACEHOLDERS[idx]), access='sequential').colourspace('srgb')
        w, h = top_img.width, top_img.height
        m = min(w, h)
        left = (w - m) // 2
        top = (h - m) // 2
        square = top_img.crop(left, top, m, m)
        resized = square.thumbnail_image(TOP_SIZE[0], height=TOP_SIZE[1])
        image = image.composite2(resized, 'over', x=pos_x, y=pos_y)

    about = pyvips.Image.new_from_file(str(ABOUT_IMAGE_PATH), access='sequential').colourspace('srgb')
    image = image.composite2(about, 'over')

    name = nickname or 'Username'
    if len(name) > 10:
        name = name[:10] + '.'
    text_mask = pyvips.Image.text(name, font=FONT_NICK, dpi=DPI)
    text_mask = text_mask.embed(0, 0, text_mask.width + PADDING, text_mask.height + PADDING)
    if text_mask.width > CONTAINER_WIDTH:
        text_mask = text_mask.crop(0, 0, CONTAINER_WIDTH, text_mask.height)
    white = (pyvips.Image.black(text_mask.width, text_mask.height) + 255).bandjoin([255, 255])
    rgba_nick = white.bandjoin([text_mask]).copy(interpretation='srgb')
    image = image.composite2(rgba_nick, 'over', x=NICK_POSITION[0], y=NICK_POSITION[1])

    text_mask = pyvips.Image.text(str(value), font=FONT_VALUE, dpi=DPI)
    text_mask = text_mask.embed(0, 0, text_mask.width + PADDING, text_mask.height + PADDING)
    white = (pyvips.Image.black(text_mask.width, text_mask.height) + 255).bandjoin([255, 255])
    rgba_value = white.bandjoin([text_mask]).copy(interpretation='srgb')
    x_pos = TEXT_POSITION[0] - text_mask.width
    image = image.composite2(rgba_value, 'over', x=x_pos, y=TEXT_POSITION[1])

    place_text = f"#{place}"
    text_mask = pyvips.Image.text(place_text, font=FONT_PLACE, dpi=DPI)
    text_mask = text_mask.embed(0, 0, text_mask.width + PADDING, text_mask.height + PADDING)
    r = (pyvips.Image.black(text_mask.width, text_mask.height) + 195)
    g = (pyvips.Image.black(text_mask.width, text_mask.height) + 191)
    b = (pyvips.Image.black(text_mask.width, text_mask.height) + 203)
    rgb = r.bandjoin([g, b])
    rgba_place = rgb.bandjoin([text_mask]).copy(interpretation='srgb')
    image = image.composite2(rgba_place, 'over', x=PLACE_POSITION[0], y=PLACE_POSITION[1])

    image.write_to_file(str(output_path))