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

# ============================================================
# НАСТРОЙКИ — замените на свои значения
# ============================================================
BOT_TOKEN = "8730902289:AAEzwE8QeDTwH5lNxvaR-XGbKtGgm_IBTC4"
GROUP_CHAT_ID = "@hipp_order"
GOOGLE_CREDENTIALS_FILE = "credentials.json"
SPREADSHEET_NAME = "Hipp Catalog"  # Название вашей Google таблицы

# Логины и пароли магазинов: {логин: (пароль, название магазина)}
SHOP_USERS = {
    "shop001": ("pass001", "Магазин Ташкент 1"),
    "shop002": ("pass002", "Магазин Ташкент 2"),
    "shop003": ("pass003", "Магазин Самарканд"),
}

BRANDS = ["1. Хипп", "2. Хипп косметика"]
PRICE_TYPES = {"ru": ["Перечисление", "Продажа"], "uz": ["O'tkazma", "Sotuv"]}
# ============================================================

# Состояния разговора
(LANG, LOGIN, PASSWORD, BRAND, PRICE_TYPE, CATALOG, CONFIRM) = range(7)

TEXTS = {
    "ru": {
        "welcome": "👋 Добро пожаловать!\nВыберите язык / Tilni tanlang:",
        "enter_login": "🔐 Введите ваш логин:",
        "enter_password": "🔑 Введите ваш пароль:",
        "wrong_creds": "❌ Неверный логин или пароль. Попробуйте снова.\nВведите логин:",
        "choose_brand": "📦 Выберите направление:",
        "choose_price": "💰 Выберите тип цены:",
        "catalog_title": "🛒 Каталог товаров\nНажмите + чтобы добавить товар:",
        "cart_empty": "Корзина пуста",
        "cart": "🛒 Ваша корзина:\n\n",
        "total": "\n💵 Итого: ",
        "confirm": "✅ Подтвердить заказ",
        "clear": "🗑 Очистить корзину",
        "back": "◀️ Назад",
        "order_confirmed": "✅ Заказ принят! Спасибо!\n\nМы свяжемся с вами в ближайшее время.",
        "order_empty": "❌ Корзина пуста! Добавьте товары.",
        "in_stock": "На складе",
        "price": "Цена",
        "sum": "сум",
    },
    "uz": {
        "welcome": "👋 Xush kelibsiz!\nВыберите язык / Tilni tanlang:",
        "enter_login": "🔐 Loginingizni kiriting:",
        "enter_password": "🔑 Parolingizni kiriting:",
        "wrong_creds": "❌ Noto'g'ri login yoki parol. Qaytadan urinib ko'ring.\nLoginni kiriting:",
        "choose_brand": "📦 Yo'nalishni tanlang:",
        "choose_price": "💰 Narx turini tanlang:",
        "catalog_title": "🛒 Mahsulotlar katalogi\nQo'shish uchun + ni bosing:",
        "cart_empty": "Savat bo'sh",
        "cart": "🛒 Savatingiz:\n\n",
        "total": "\n💵 Jami: ",
        "confirm": "✅ Buyurtmani tasdiqlash",
        "clear": "🗑 Savatni tozalash",
        "back": "◀️ Orqaga",
        "order_confirmed": "✅ Buyurtma qabul qilindi! Rahmat!\n\nTez orada siz bilan bog'lanamiz.",
        "order_empty": "❌ Savat bo'sh! Mahsulot qo'shing.",
        "in_stock": "Omborda",
        "price": "Narx",
        "sum": "so'm",
    }
}

def get_products_from_sheets(brand: str):
    """Получить товары из Google Sheets по бренду"""
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets",
                  "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open(SPREADSHEET_NAME).worksheet(brand)
        records = sheet.get_all_records()
        return records
    except Exception as e:
        logger.error(f"Ошибка Google Sheets: {e}")
        return []

def save_order_to_sheets(order_data: dict):
    """Сохранить заказ в Google Sheets"""
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets",
                  "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open(SPREADSHEET_NAME).worksheet("Заказы")
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        for item in order_data["items"]:
            sheet.append_row([
                now,
                order_data["shop_name"],
                order_data["brand"],
                order_data["price_type"],
                item["name"],
                item["qty"],
                item["price"],
                item["qty"] * item["price"],
                order_data["total"]
            ])
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения заказа: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    keyboard = [
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton("🇺🇿 O'zbek", callback_data="lang_uz")],
    ]
    await update.message.reply_text(
        TEXTS["ru"]["welcome"],
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return LANG

async def lang_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.split("_")[1]
    context.user_data["lang"] = lang
    t = TEXTS[lang]
    await query.edit_message_text(t["enter_login"])
    return LOGIN

async def get_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["login_attempt"] = update.message.text.strip()
    lang = context.user_data.get("lang", "ru")
    await update.message.reply_text(TEXTS[lang]["enter_password"])
    return PASSWORD

async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ru")
    t = TEXTS[lang]
    login = context.user_data.get("login_attempt", "")
    password = update.message.text.strip()

    if login in SHOP_USERS and SHOP_USERS[login][1] and SHOP_USERS[login][0] == password:
        context.user_data["shop_name"] = SHOP_USERS[login][1]
        context.user_data["cart"] = {}
        keyboard = [[InlineKeyboardButton(b, callback_data=f"brand_{i}")] for i, b in enumerate(BRANDS)]
        await update.message.reply_text(
            f"✅ {context.user_data['shop_name']}\n\n{t['choose_brand']}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return BRAND
    else:
        await update.message.reply_text(t["wrong_creds"])
        return LOGIN

async def brand_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "ru")
    t = TEXTS[lang]
    brand_idx = int(query.data.split("_")[1])
    context.user_data["brand"] = BRANDS[brand_idx]
    price_types = PRICE_TYPES[lang]
    keyboard = [[InlineKeyboardButton(p, callback_data=f"price_{i}")] for i, p in enumerate(price_types)]
    keyboard.append([InlineKeyboardButton(t["back"], callback_data="back_brand")])
    await query.edit_message_text(t["choose_price"], reply_markup=InlineKeyboardMarkup(keyboard))
    return PRICE_TYPE

async def price_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "ru")
    price_idx = int(query.data.split("_")[1])
    context.user_data["price_type"] = PRICE_TYPES[lang][price_idx]
    context.user_data["cart"] = {}
    await show_catalog(query, context)
    return CATALOG

async def show_catalog(query, context: ContextTypes.DEFAULT_TYPE, page=0):
    lang = context.user_data.get("lang", "ru")
    t = TEXTS[lang]
    brand = context.user_data.get("brand", "")
    brand_key = "Хипп" if "косметика" not in brand else "Хипп косметика"
    products = get_products_from_sheets(brand_key)
    context.user_data["products"] = products

    if not products:
        await query.edit_message_text("❌ Товары не найдены. Проверьте Google Sheets.")
        return

    PAGE_SIZE = 5
    total_pages = (len(products) + PAGE_SIZE - 1) // PAGE_SIZE
    start_idx = page * PAGE_SIZE
    page_products = products[start_idx:start_idx + PAGE_SIZE]
    context.user_data["catalog_page"] = page

    cart = context.user_data.get("cart", {})
    total_items = sum(v["qty"] for v in cart.values())

    text = t["catalog_title"] + f"\n📄 Страница {page+1}/{total_pages}\n"
    if total_items > 0:
        text += f"\n🛒 В корзине: {total_items} товаров"

    keyboard = []
    for i, p in enumerate(page_products):
        real_idx = start_idx + i
        name = str(p.get("Название", p.get("name", f"Товар {real_idx+1}")))
        price = p.get("Цена", p.get("price", 0))
        stock = p.get("Остаток", p.get("stock", 0))
        in_cart = cart.get(real_idx, {}).get("qty", 0)
        cart_info = f" [{in_cart}шт]" if in_cart > 0 else ""
        btn_text = f"{name[:25]}{cart_info} — {price:,} {t['sum']}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"add_{real_idx}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"page_{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"page_{page+1}"))
    if nav:
        keyboard.append(nav)

    cart_total = sum(v["qty"] * v["price"] for v in cart.values())
    bottom = []
    if cart:
        bottom.append(InlineKeyboardButton(
            f"🛒 Корзина ({total_items} шт) — {cart_total:,} {t['sum']}",
            callback_data="view_cart"
        ))
    keyboard.append(bottom if bottom else [])
    keyboard.append([InlineKeyboardButton(t["back"], callback_data="back_price")])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def catalog_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    lang = context.user_data.get("lang", "ru")
    t = TEXTS[lang]

    if data.startswith("add_"):
        idx = int(data.split("_")[1])
        products = context.user_data.get("products", [])
        if idx < len(products):
            p = products[idx]
            name = str(p.get("Название", p.get("name", f"Товар {idx+1}")))
            price = int(p.get("Цена", p.get("price", 0)))
            cart = context.user_data.get("cart", {})
            if idx in cart:
                cart[idx]["qty"] += 1
            else:
                cart[idx] = {"name": name, "price": price, "qty": 1}
            context.user_data["cart"] = cart
        page = context.user_data.get("catalog_page", 0)
        await show_catalog(query, context, page)

    elif data.startswith("page_"):
        page = int(data.split("_")[1])
        await show_catalog(query, context, page)

    elif data == "view_cart":
        await show_cart(query, context)

    elif data == "confirm_order":
        await confirm_order(query, context)

    elif data == "clear_cart":
        context.user_data["cart"] = {}
        page = context.user_data.get("catalog_page", 0)
        await show_catalog(query, context, page)

    elif data == "back_price":
        keyboard = [[InlineKeyboardButton(b, callback_data=f"brand_{i}")] for i, b in enumerate(BRANDS)]
        await query.edit_message_text(t["choose_brand"], reply_markup=InlineKeyboardMarkup(keyboard))
        return BRAND

    elif data == "back_catalog":
        page = context.user_data.get("catalog_page", 0)
        await show_catalog(query, context, page)

    elif data == "back_brand":
        keyboard = [[InlineKeyboardButton(b, callback_data=f"brand_{i}")] for i, b in enumerate(BRANDS)]
        await query.edit_message_text(t["choose_brand"], reply_markup=InlineKeyboardMarkup(keyboard))
        return BRAND

    return CATALOG

async def show_cart(query, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ru")
    t = TEXTS[lang]
    cart = context.user_data.get("cart", {})

    if not cart:
        await query.edit_message_text(t["cart_empty"])
        return

    text = t["cart"]
    total = 0
    for idx, item in cart.items():
        subtotal = item["qty"] * item["price"]
        total += subtotal
        text += f"• {item['name']}\n  {item['qty']} шт × {item['price']:,} = {subtotal:,} {t['sum']}\n\n"
    text += f"{t['total']}{total:,} {t['sum']}"

    keyboard = [
        [InlineKeyboardButton(t["confirm"], callback_data="confirm_order")],
        [InlineKeyboardButton(t["clear"], callback_data="clear_cart")],
        [InlineKeyboardButton(t["back"], callback_data="back_catalog")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def confirm_order(query, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ru")
    t = TEXTS[lang]
    cart = context.user_data.get("cart", {})

    if not cart:
        await query.edit_message_text(t["order_empty"])
        return

    shop_name = context.user_data.get("shop_name", "Неизвестный магазин")
    brand = context.user_data.get("brand", "")
    price_type = context.user_data.get("price_type", "")
    total = sum(v["qty"] * v["price"] for v in cart.values())
    items = list(cart.values())

    order_data = {
        "shop_name": shop_name,
        "brand": brand,
        "price_type": price_type,
        "items": items,
        "total": total
    }

    # Сообщение в группу
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    msg = f"🛒 НОВЫЙ ЗАКАЗ\n"
    msg += f"📅 {now}\n"
    msg += f"🏪 {shop_name}\n"
    msg += f"📦 {brand}\n"
    msg += f"💰 {price_type}\n\n"
    msg += "Товары:\n"
    for item in items:
        msg += f"• {item['name']} — {item['qty']} шт × {item['price']:,} = {item['qty']*item['price']:,}\n"
    msg += f"\n💵 ИТОГО: {total:,} сум"

    try:
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=msg)
    except Exception as e:
        logger.error(f"Ошибка отправки в группу: {e}")

    save_order_to_sheets(order_data)

    context.user_data["cart"] = {}
    await query.edit_message_text(t["order_confirmed"])

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("До свидания! Напишите /start чтобы начать снова.")
    return ConversationHandler.END

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANG: [CallbackQueryHandler(lang_chosen, pattern="^lang_")],
            LOGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_login)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)],
            BRAND: [CallbackQueryHandler(brand_chosen, pattern="^brand_"),
                    CallbackQueryHandler(catalog_action, pattern="^back_")],
            PRICE_TYPE: [CallbackQueryHandler(price_chosen, pattern="^price_"),
                         CallbackQueryHandler(catalog_action, pattern="^back_")],
            CATALOG: [CallbackQueryHandler(catalog_action)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )

    app.add_handler(conv_handler)
    logger.info("Бот запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
