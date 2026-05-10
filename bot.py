import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8730902289:AAEzwE8QeDTwH5lNxvaR-XGbKtGgm_IBTC4")
GROUP_CHAT_ID = "@hipp_order"
GOOGLE_CREDENTIALS_FILE = "credentials.json"
SPREADSHEET_NAME = "Hipp Catalog"

SHOP_USERS = {
    "shop001": ("pass001", "Магазин 1"),
    "shop002": ("pass002", "Магазин 2"),
    "shop003": ("pass003", "Магазин 3"),
}

BRANDS = ["1. Хипп", "2. Хипп косметика"]
PRICE_TYPES = {
    "ru": ["Перечисление", "Продажа"],
    "uz": ["O'tkazma", "Sotuv"]
}

LANG, LOGIN, PASSWORD, BRAND, PRICE_TYPE, CATALOG, CART = range(7)

TEXTS = {
    "ru": {
        "welcome": "👋 Добро пожаловать! Выберите язык:",
        "enter_login": "🔐 Введите логин:",
        "enter_password": "🔑 Введите пароль:",
        "wrong_creds": "❌ Неверный логин или пароль.\nВведите логин:",
        "choose_brand": "📦 Выберите направление:",
        "choose_price": "💰 Выберите тип цены:",
        "catalog_title": "🛒 Каталог товаров:",
        "back": "◀️ Назад",
        "order_confirmed": "✅ Заказ принят! Спасибо!",
        "order_empty": "❌ Корзина пуста!",
        "sum": "сум",
        "in_cart": "В корзине",
        "cart_title": "🛒 Ваша корзина:\n\n",
        "total": "\n💵 Итого: ",
        "confirm": "✅ Подтвердить заказ",
        "clear": "🗑 Очистить корзину",
    },
    "uz": {
        "welcome": "👋 Xush kelibsiz! Tilni tanlang:",
        "enter_login": "🔐 Loginni kiriting:",
        "enter_password": "🔑 Parolni kiriting:",
        "wrong_creds": "❌ Noto'g'ri login yoki parol.\nLoginni kiriting:",
        "choose_brand": "📦 Yo'nalishni tanlang:",
        "choose_price": "💰 Narx turini tanlang:",
        "catalog_title": "🛒 Mahsulotlar:",
        "back": "◀️ Orqaga",
        "order_confirmed": "✅ Buyurtma qabul qilindi! Rahmat!",
        "order_empty": "❌ Savat bo'sh!",
        "sum": "so'm",
        "in_cart": "Savatda",
        "cart_title": "🛒 Savatingiz:\n\n",
        "total": "\n💵 Jami: ",
        "confirm": "✅ Buyurtmani tasdiqlash",
        "clear": "🗑 Savatni tozalash",
    }
}

def get_products(brand):
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=scopes)
        client = gspread.authorize(creds)
        sheet_name = "Хипп" if "косметика" not in brand else "Хипп косметика"
        sheet = client.open(SPREADSHEET_NAME).worksheet(sheet_name)
        return sheet.get_all_records()
    except Exception as e:
        logger.error(f"Sheets error: {e}")
        return []

def save_order(order_data):
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open(SPREADSHEET_NAME).worksheet("Заказы")
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        for item in order_data["items"]:
            sheet.append_row([
                now, order_data["shop"], order_data["brand"],
                order_data["price_type"], item["name"],
                item["qty"], item["price"], item["qty"] * item["price"]
            ])
    except Exception as e:
        logger.error(f"Save error: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    kb = [[InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
          [InlineKeyboardButton("🇺🇿 O'zbek", callback_data="lang_uz")]]
    await update.message.reply_text("👋 Выберите язык / Tilni tanlang:", reply_markup=InlineKeyboardMarkup(kb))
    return LANG

async def lang_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang = q.data.split("_")[1]
    context.user_data["lang"] = lang
    await q.edit_message_text(TEXTS[lang]["enter_login"])
    return LOGIN

async def get_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["login_try"] = update.message.text.strip()
    lang = context.user_data.get("lang", "ru")
    await update.message.reply_text(TEXTS[lang]["enter_password"])
    return PASSWORD

async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ru")
    t = TEXTS[lang]
    login = context.user_data.get("login_try", "")
    pwd = update.message.text.strip()
    if login in SHOP_USERS and SHOP_USERS[login][0] == pwd:
        context.user_data["shop"] = SHOP_USERS[login][1]
        context.user_data["cart"] = {}
        kb = [[InlineKeyboardButton(b, callback_data=f"brand_{i}")] for i, b in enumerate(BRANDS)]
        await update.message.reply_text(f"✅ {SHOP_USERS[login][1]}\n\n{t['choose_brand']}", reply_markup=InlineKeyboardMarkup(kb))
        return BRAND
    else:
        await update.message.reply_text(t["wrong_creds"])
        return LOGIN

async def brand_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang = context.user_data.get("lang", "ru")
    idx = int(q.data.split("_")[1])
    context.user_data["brand"] = BRANDS[idx]
    context.user_data["cart"] = {}
    pt = PRICE_TYPES[lang]
    kb = [[InlineKeyboardButton(p, callback_data=f"price_{i}")] for i, p in enumerate(pt)]
    await q.edit_message_text(TEXTS[lang]["choose_price"], reply_markup=InlineKeyboardMarkup(kb))
    return PRICE_TYPE

async def price_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang = context.user_data.get("lang", "ru")
    idx = int(q.data.split("_")[1])
    context.user_data["price_type"] = PRICE_TYPES[lang][idx]
    products = get_products(context.user_data["brand"])
    context.user_data["products"] = products
    context.user_data["page"] = 0
    await show_catalog(q, context)
    return CATALOG

async def show_catalog(q, context, page=None):
    lang = context.user_data.get("lang", "ru")
    t = TEXTS[lang]
    if page is not None:
        context.user_data["page"] = page
    page = context.user_data.get("page", 0)
    products = context.user_data.get("products", [])
    cart = context.user_data.get("cart", {})
    PAGE = 5
    total_pages = max(1, (len(products) + PAGE - 1) // PAGE)
    items = products[page * PAGE:(page + 1) * PAGE]
    total_items = sum(v["qty"] for v in cart.values())
    total_sum = sum(v["qty"] * v["price"] for v in cart.values())
    text = t["catalog_title"]
    if total_items > 0:
        text += f"\n🛒 {total_items} шт — {total_sum:,} {t['sum']}"
    text += f"\n📄 {page+1}/{total_pages}"
    kb = []
    for i, p in enumerate(items):
        real_i = page * PAGE + i
        name = str(p.get("Название", f"Товар {real_i+1}"))
        price = int(p.get("Цена", 0))
        stock = p.get("Остаток", 0)
        in_c = cart.get(real_i, {}).get("qty", 0)
        label = f"{'✅' if in_c else '+'} {name[:20]} — {price:,}"
        if in_c:
            label += f" [{in_c}]"
        kb.append([InlineKeyboardButton(label, callback_data=f"add_{real_i}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"page_{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"page_{page+1}"))
    if nav:
        kb.append(nav)
    if cart:
        kb.append([InlineKeyboardButton(f"🛒 Корзина ({total_items} шт)", callback_data="view_cart")])
    kb.append([InlineKeyboardButton(t["back"], callback_data="back_brand")])
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def catalog_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    lang = context.user_data.get("lang", "ru")
    t = TEXTS[lang]

    if data.startswith("add_"):
        idx = int(data.split("_")[1])
        products = context.user_data.get("products", [])
        if idx < len(products):
            p = products[idx]
            name = str(p.get("Название", f"Товар {idx+1}"))
            price = int(p.get("Цена", 0))
            cart = context.user_data.get("cart", {})
            cart[idx] = {"name": name, "price": price, "qty": cart.get(idx, {}).get("qty", 0) + 1}
            context.user_data["cart"] = cart
        await show_catalog(q, context)

    elif data.startswith("page_"):
        await show_catalog(q, context, int(data.split("_")[1]))

    elif data == "view_cart":
        cart = context.user_data.get("cart", {})
        if not cart:
            await q.edit_message_text(t["order_empty"])
            return CATALOG
        text = t["cart_title"]
        total = 0
        for item in cart.values():
            sub = item["qty"] * item["price"]
            total += sub
            text += f"• {item['name']}\n  {item['qty']} × {item['price']:,} = {sub:,} {t['sum']}\n\n"
        text += f"{t['total']}{total:,} {t['sum']}"
        kb = [
            [InlineKeyboardButton(t["confirm"], callback_data="confirm")],
            [InlineKeyboardButton(t["clear"], callback_data="clear_cart")],
            [InlineKeyboardButton(t["back"], callback_data="back_catalog")],
        ]
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

    elif data == "confirm":
        cart = context.user_data.get("cart", {})
        if not cart:
            await q.edit_message_text(t["order_empty"])
            return CATALOG
        shop = context.user_data.get("shop", "")
        brand = context.user_data.get("brand", "")
        price_type = context.user_data.get("price_type", "")
        total = sum(v["qty"] * v["price"] for v in cart.values())
        items = list(cart.values())
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        msg = f"🛒 НОВЫЙ ЗАКАЗ\n📅 {now}\n🏪 {shop}\n📦 {brand}\n💰 {price_type}\n\nТовары:\n"
        for item in items:
            msg += f"• {item['name']} — {item['qty']} шт × {item['price']:,} = {item['qty']*item['price']:,}\n"
        msg += f"\n💵 ИТОГО: {total:,} сум"
        try:
            await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=msg)
        except Exception as e:
            logger.error(f"Group error: {e}")
        save_order({"shop": shop, "brand": brand, "price_type": price_type, "items": items, "total": total})
        context.user_data["cart"] = {}
        await q.edit_message_text(t["order_confirmed"])

    elif data == "clear_cart":
        context.user_data["cart"] = {}
        await show_catalog(q, context)

    elif data == "back_catalog":
        await show_catalog(q, context)

    elif data == "back_brand":
        kb = [[InlineKeyboardButton(b, callback_data=f"brand_{i}")] for i, b in enumerate(BRANDS)]
        await q.edit_message_text(t["choose_brand"], reply_markup=InlineKeyboardMarkup(kb))
        return BRAND

    return CATALOG

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("До свидания! /start — начать заново.")
    return ConversationHandler.END

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANG: [CallbackQueryHandler(lang_chosen, pattern="^lang_")],
            LOGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_login)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)],
            BRAND: [CallbackQueryHandler(brand_chosen, pattern="^brand_"),
                    CallbackQueryHandler(catalog_action, pattern="^back_")],
            PRICE_TYPE: [CallbackQueryHandler(price_chosen, pattern="^price_")],
            CATALOG: [CallbackQueryHandler(catalog_action)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )
    app.add_handler(conv)
    logger.info("Bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
