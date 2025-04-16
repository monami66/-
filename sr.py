import aiohttp
import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

TOKEN = '8069494650:AAEWjEPFhJjE4yjcDE3bacIuEM3onBiY5UE'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GENRE_MAPPING = {
    "Экшен": "1",
    "Комедия": "4",
    "Фэнтези": "10"
}

async def get_anime_info_shikimori(query):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        async with aiohttp.ClientSession() as session:
            async with session.get("https://shikimori.one/api/animes", params={"search": query}, headers=headers) as response:
                response.raise_for_status()
                results = await response.json()

                if results:
                    anime = results[0]
                    title = anime['russian'] or anime['name']
                    image_url = f"https://shikimori.one{anime['image']['original']}"
                    anime_id = anime['id']

                    async with session.get(f"https://shikimori.one/api/animes/{anime_id}", headers=headers) as details_response:
                        details = await details_response.json()
                        description = details.get('description', 'Описание недоступно.')

                    return title, description, image_url
        return None, None, None
    except Exception as e:
        logger.error(f"Ошибка с Shikimori API: {e}")
        return None, None, None

async def get_watch_url_anilibria(query):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.anilibria.tv/v3/title/search", params={"search": query}) as response:
                response.raise_for_status()
                data = await response.json()
                if data and 'list' in data and data['list']:
                    item = data['list'][0]
                    if 'code' in item:
                        code = item['code']
                        return f"https://www.anilibria.tv/release/{code}.html"
    except Exception as e:
        logger.error(f"Ошибка с Anilibria API: {e}")
    return None

async def get_random_anime():
    try:
        random_id = random.randint(1, 20000)
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://shikimori.one/api/animes/{random_id}") as response:
                if response.status != 200:
                    return None, None, None
                data = await response.json()
                title = data.get("russian") or data.get("name")
                image_url = f"https://shikimori.one{data['image']['original']}"
                description = data.get("description", "Описание недоступно.")
                return title, description, image_url
    except Exception as e:
        logger.error(f"Ошибка при получении случайного аниме: {e}")
        return None, None, None

async def get_anime_by_genre(genre_id):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://shikimori.one/api/animes", params={
                "limit": 50,
                "genre": genre_id,
                "order": "popularity"
            }) as response:
                response.raise_for_status()
                results = await response.json()

                if results:
                    selected = random.sample(results, min(3, len(results)))
                    anime_list = []
                    for anime in selected:
                        anime_id = anime["id"]
                        async with session.get(f"https://shikimori.one/api/animes/{anime_id}") as detail_resp:
                            details = await detail_resp.json()
                            title = details.get("russian") or details.get("name")
                            image_url = f"https://shikimori.one{details['image']['original']}"
                            description = details.get("description", "Описание недоступно.")
                            anime_list.append((title, description, image_url))
                    return anime_list
    except Exception as e:
        logger.error(f"Ошибка при получении аниме по жанру: {e}")
    return []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔍 Поиск по названию", callback_data='search')],
        [InlineKeyboardButton("🎲 Случайное аниме", callback_data='random')],
        [InlineKeyboardButton("🎭 Выбрать жанр", callback_data='choose_genre')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выбери действие:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'search':
        await query.message.reply_text("Напиши название аниме 📝")
    elif query.data == 'random':
        title, desc, img = await get_random_anime()
        if title:
            await query.message.reply_photo(photo=img, caption=f"🎬 <b>{title}</b>\n\n📝 {desc}", parse_mode='HTML')
        else:
            await query.message.reply_text("Не удалось найти случайное аниме 😢")
    elif query.data == 'choose_genre':
        keyboard = [
            [InlineKeyboardButton(genre, callback_data=f'genre_{gid}')]
            for genre, gid in GENRE_MAPPING.items()
        ]
        await query.message.reply_text("Выберите жанр:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif query.data.startswith("genre_"):
        genre_id = query.data.split("_")[1]
        anime_list = await get_anime_by_genre(genre_id)
        if anime_list:
            for title, desc, img in anime_list:
                await query.message.reply_photo(photo=img, caption=f"🎬 <b>{title}</b>\n\n📝 {desc}", parse_mode='HTML')
        else:
            await query.message.reply_text("Не удалось найти аниме по жанру 😢")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    title, description, image_url = await get_anime_info_shikimori(query)
    watch_url = await get_watch_url_anilibria(query)

    if title:
        await update.message.reply_photo(photo=image_url)
        await update.message.reply_text(f"🎬 <b>{title}</b>\n\n📝 {description}", parse_mode='HTML')
        if watch_url:
            keyboard = [[InlineKeyboardButton("🎥 Смотреть на Anilibria", url=watch_url)]]
            markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Ссылка на просмотр:", reply_markup=markup)
        else:
            await update.message.reply_text("К сожалению, ссылка на просмотр не найдена 😢")
    else:
        await update.message.reply_text("Аниме не найдено 😔 Попробуй другое название.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == '__main__':
    main()