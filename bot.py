import logging
import os
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# НАСТРОЙКИ
# ============================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8730902289:AAEzwE8QeDTwH5lNxvaR-XGbKtGgm_IBTC4")
GROUP_CHAT_ID = "@hipp_order"
GOOGLE_CREDENTIALS_FILE = "credentials.json"
SPREADSHEET_NAME = "Hipp Catalog"
ADMIN_IDS = []  # Добавьте ваш Telegram ID сюда после первого запуска

# Бренды — добавляйте новые сюда и создавайте лист в Google Sheets
BRANDS = [
    "Хипп",
    "Хипп косметика",
]

# ============================================================
# СОСТОЯНИЯ
# ============================================================
(REGISTER_NAME, REGISTER_ADDRESS, WAIT_APPROVAL,
 BRAND, PRICE_TYPE, CATALOG, PRODUCT_QTY, CART) = range(8)

# ============================================================
# ТЕКСТЫ
# ============================================================
TEXTS = {
    "ru": {
        "choose_lang": "👋 Добро пожаловать!\nВыберите язык / Tilni tanlang:",
        "enter_shop_name": "🏪 Введите название вашего магазина:",
        "enter_address": "📍 Введите адрес вашего магазина:",
        "wait_approval": "⏳ Ваша заявка отправлена администратору.\nОжидайте одобрения.",
        "approved": "✅ Ваш магазин одобрен! Напишите /start чтобы начать.",
        "rejected": "❌ Ваша заявка отклонена. Свяжитесь с администратором.",
        "blocked": "🚫 Ваш аккаунт заблокирован.",
        "choose_brand": "📦 Выберите направление:",
        "choose_price": "💰 Выберите тип оплаты:",
        "catalog_title": "🛒 Каталог товаров",
        "out_of_stock": "Нет в наличии",
        "back": "◀️ Назад",
        "cart_title": "🛒 Ваша корзина:\n\n",
        "total": "💵 Итого: ",
        "min_order": "❌ Минимальная сумма заказа: ",
        "confirm_order": "✅ Подтвердить заказ",
        "cancel_order": "❌ Отменить заказ",
        "clear_cart": "🗑 Очистить корзину",
        "order_confirmed": "✅ Заказ принят!\nУ вас есть 30 минут чтобы отменить его.",
        "order_cancelled": "❌ Заказ отменён.",
        "order_empty": "❌ Корзина пуста!",
        "search": "🔍 Поиск",
        "enter_search": "🔍 Введите название товара:",
        "no_results": "❌ Товары не найдены.",
        "repeat_order": "🔄 Повторить последний заказ",
        "history": "📋 История заказов",
        "no_history": "У вас ещё нет заказов.",
        "sum": "сум",
        "pcs": "шт",
        "add_to_cart": "➕ В корзину",
        "in_cart": "✅ В корзине",
        "qty_prompt": "Выберите количество:",
        "price_types": ["Перечисление", "Продажа"],
    },
    "uz": {
        "choose_lang": "👋 Xush kelibsiz!\nВыберите язык / Tilni tanlang:",
        "enter_shop_name": "🏪 Do'koningiz nomini kiriting:",
        "enter_address": "📍 Do'koningiz manzilini kiriting:",
        "wait_approval": "⏳ Arizangiz administratorga yuborildi.\nTasdiqlashni kuting.",
        "approved": "✅ Do'koningiz tasdiqlandi! Boshlash uchun /start yozing.",
        "rejected": "❌ Arizangiz rad etildi. Administrator bilan bog'laning.",
        "blocked": "🚫 Hisobingiz bloklangan.",
        "choose_brand": "📦 Yo'nalishni tanlang:",
        "choose_price": "💰 To'lov turini tanlang:",
        "catalog_title": "🛒 Mahsulotlar katalogi",
        "out_of_stock": "Mavjud emas",
        "back": "◀️ Orqaga",
        "cart_title": "🛒 Savatingiz:\n\n",
        "total": "💵 Jami: ",
        "min_order": "❌ Minimal buyurtma summasi: ",
        "confirm_order": "✅ Buyurtmani tasdiqlash",
        "cancel_order": "❌ Buyurtmani bekor qilish",
        "clear_cart": "🗑 Savatni tozalash",
        "order_confirmed": "✅ Buyurtma qabul qilindi!\nUni bekor qilish uchun 30 daqiqangiz bor.",
        "order_cancelled": "❌ Buyurtma bekor qilindi.",
        "order_empty": "❌ Savat bo'sh!",
        "search": "🔍 Qidiruv",
        "enter_search": "🔍 Mahsulot nomini kiriting:",
        "no_results": "❌ Mahsulotlar topilmadi.",
        "repeat_order": "🔄 Oxirgi buyurtmani takrorlash",
        "history": "📋 Buyurtmalar tarixi",
        "no_history": "Sizda hali buyurtmalar yo'q.",
        "sum": "so'm",
        "pcs": "dona",
        "add_to_cart": "➕ Savatga",
        "in_cart": "✅ Savatda",
        "qty_prompt": "Miqdorni tanlang:",
        "price_types": ["O'tkazma", "Sotuv"],
    }
}

# ============================================================
# GOOGLE SHEETS
# ============================================================
def get_sheets_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=scopes)
    return gspread.authorize(creds)

def get_products(brand):
    try:
        client = get_sheets_client()
        sheet = client.open(SPREADSHEET_NAME).worksheet(brand)
        records = sheet.get_all_records()
        return [r for r in records if int(r.get("Остаток", 0)) > 0]
    except Exception as e:
        logger.error(f"Products error: {e}")
        return []

def get_min_order():
    try:
        client = get_sheets_client()
        sheet = client.open(SPREADSHEET_NAME).worksheet("Настройки")
        val = sheet.acell("B1").value
        return int(val) if val else 0
    except:
        return 0

def get_shop(user_id):
    try:
        client = get_sheets_client()
        sheet = client.open(SPREADSHEET_NAME).worksheet("Магазины")
        records = sheet.get_all_records()
        for r in records:
            if str(r.get("TelegramID")) == str(user_id):
                return r
        return None
    except Exception as e:
        logger.error(f"Get shop error: {e}")
        return None

def register_shop(user_id, name, address, lang):
    try:
        client = get_sheets_client()
        sheet = client.open(SPREADSHEET_NAME).worksheet("Магазины")
        sheet.append_row([user_id, name, address, lang, "pending", datetime.now().strftime("%d.%m.%Y %H:%M")])
        return True
    except Exception as e:
        logger.error(f"Register error: {e}")
        return False

def update_shop_status(user_id, status):
    try:
        client = get_sheets_client()
        sheet = client.open(SPREADSHEET_NAME).worksheet("Магазины")
        records = sheet.get_all_records()
        for i, r in enumerate(records):
            if str(r.get("TelegramID")) == str(user_id):
                sheet.update_cell(i + 2, 5, status)
                return True
        return False
    except Exception as e:
        logger.error(f"Update shop error: {e}")
        return False

def save_order(order_data):
    try:
        client = get_sheets_client()
        sheet = client.open(SPREADSHEET_NAME).worksheet("Заказы")
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        order_id = f"#{int(datetime.now().timestamp())}"
        for item in order_data["items"]:
            sheet.append_row([
                order_id, now, order_data["shop_name"], order_data["address"],
                order_data["brand"], order_data["price_type"],
                item["name"], item["qty"], item["price"],
                item["qty"] * item["price"], order_data["total"], "активен"
            ])
        # Уменьшить остатки
        update_stock(order_data["brand"], order_data["items"])
        return order_id
    except Exception as e:
        logger.error(f"Save order error: {e}")
        return None

def update_stock(brand, items):
    try:
        client = get_sheets_client()
        sheet = client.open(SPREADSHEET_NAME).worksheet(brand)
        records = sheet.get_all_records()
        for item in items:
            for i, r in enumerate(records):
                if str(r.get("Название")) == item["name"]:
                    new_stock = max(0, int(r.get("Остаток", 0)) - item["qty"])
                    sheet.update_cell(i + 2, 3, new_stock)
                    # Уведомить если остаток меньше 10
                    if new_stock < 10:
                        return f"⚠️ Остаток товара '{item['name']}' меньше 10 штук! Осталось: {new_stock}"
    except Exception as e:
        logger.error(f"Stock update error: {e}")
    return None

def cancel_order_in_sheets(order_id):
    try:
        client = get_sheets_client()
        sheet = client.open(SPREADSHEET_NAME).worksheet("Заказы")
        records = sheet.get_all_records()
        for i, r in enumerate(records):
            if r.get("ID") == order_id:
                sheet.update_cell(i + 2, 12, "отменён")
        return True
    except Exception as e:
        logger.error(f"Cancel order error: {e}")
        return False

def get_order_history(shop_name):
    try:
        client = get_sheets_client()
        sheet = client.open(SPREADSHEET_NAME).worksheet("Заказы")
        records = sheet.get_all_records()
        orders = {}
        for r in records:
            if r.get("Магазин") == shop_name and r.get("Статус") == "активен":
                oid = r.get("ID")
                if oid not in orders:
                    orders[oid] = {"date": r.get("Дата"), "total": r.get("Итого"), "items": []}
                orders[oid]["items"].append(r.get("Товар"))
        return list(orders.values())[-10:]
    except Exception as e:
        logger.error(f"History error: {e}")
        return []

# ============================================================
# ОБРАБОТЧИКИ
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    user_id = update.effective_user.id
    shop = get_shop(user_id)

    if shop:
        status = shop.get("Статус", "pending")
        lang = shop.get("Язык", "ru")
        context.user_data["lang"] = lang
        context.user_data["shop"] = shop
        t = TEXTS[lang]

        if status == "blocked":
            await update.message.reply_text(t["blocked"])
            return ConversationHandler.END
        elif status == "pending":
            await update.message.reply_text(t["wait_approval"])
            return WAIT_APPROVAL
        elif status == "approved":
            context.user_data["cart"] = {}
            kb = [[InlineKeyboardButton(b, callback_data=f"brand_{i}")] for i, b in enumerate(BRANDS)]
            extra = []
            if True:  # всегда показываем доп кнопки
                extra = [
                    [InlineKeyboardButton(t["history"], callback_data="history"),
                     InlineKeyboardButton(t["repeat_order"], callback_data="repeat")],
                ]
            await update.message.reply_text(
                f"👋 {shop.get('Название', '')}\n\n{t['choose_brand']}",
                reply_markup=InlineKeyboardMarkup(kb + extra)
            )
            return BRAND
    else:
        kb = [[InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
              [InlineKeyboardButton("🇺🇿 O'zbek", callback_data="lang_uz")]]
        await update.message.reply_text(TEXTS["ru"]["choose_lang"], reply_markup=InlineKeyboardMarkup(kb))
        return REGISTER_NAME

async def lang_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang = q.data.split("_")[1]
    context.user_data["lang"] = lang
    await q.edit_message_text(TEXTS[lang]["enter_shop_name"])
    return REGISTER_NAME

async def get_shop_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["shop_name"] = update.message.text.strip()
    lang = context.user_data.get("lang", "ru")
    await update.message.reply_text(TEXTS[lang]["enter_address"])
    return REGISTER_ADDRESS

async def get_shop_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ru")
    t = TEXTS[lang]
    address = update.message.text.strip()
    user_id = update.effective_user.id
    name = context.user_data.get("shop_name", "")
    username = update.effective_user.username or str(user_id)

    register_shop(user_id, name, address, lang)

    # Уведомить админа
    msg = (f"🆕 НОВАЯ ЗАЯВКА МАГАЗИНА\n\n"
           f"🏪 Название: {name}\n"
           f"📍 Адрес: {address}\n"
           f"👤 Username: @{username}\n"
           f"🆔 ID: {user_id}")
    kb = [[InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{user_id}"),
           InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{user_id}")]]
    try:
        await update.get_bot().send_message(
            chat_id=GROUP_CHAT_ID, text=msg, reply_markup=InlineKeyboardMarkup(kb)
        )
    except Exception as e:
        logger.error(f"Admin notify error: {e}")

    await update.message.reply_text(t["wait_approval"])
    return WAIT_APPROVAL

async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    action, user_id = data.split("_")[0], data.split("_")[1]

    if action == "approve":
        update_shop_status(user_id, "approved")
        await q.edit_message_text(q.message.text + "\n\n✅ ОДОБРЕНО")
        try:
            await context.bot.send_message(
                chat_id=int(user_id),
                text=TEXTS["ru"]["approved"]
            )
        except:
            pass
    elif action == "reject":
        update_shop_status(user_id, "rejected")
        await q.edit_message_text(q.message.text + "\n\n❌ ОТКЛОНЕНО")
        try:
            await context.bot.send_message(
                chat_id=int(user_id),
                text=TEXTS["ru"]["rejected"]
            )
        except:
            pass

async def brand_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang = context.user_data.get("lang", "ru")
    t = TEXTS[lang]

    if q.data == "history":
        shop = context.user_data.get("shop", {})
        orders = get_order_history(shop.get("Название", ""))
        if not orders:
            await q.edit_message_text(t["no_history"])
        else:
            text = f"📋 История заказов:\n\n"
            for o in orders[-5:]:
                text += f"📅 {o['date']}\n💵 {o['total']:,} {t['sum']}\n"
                text += f"Товары: {', '.join(o['items'][:3])}\n\n"
            await q.edit_message_text(text)
        return BRAND

    if q.data == "repeat":
        shop = context.user_data.get("shop", {})
        orders = get_order_history(shop.get("Название", ""))
        if not orders:
            await q.edit_message_text(t["no_history"])
            return BRAND
        # Повторить последний заказ — показать корзину
        await q.edit_message_text("🔄 Функция повтора заказа: выберите направление заново.")
        return BRAND

    idx = int(q.data.split("_")[1])
    context.user_data["brand"] = BRANDS[idx]
    context.user_data["cart"] = {}
    pt = t["price_types"]
    kb = [[InlineKeyboardButton(p, callback_data=f"price_{i}")] for i, p in enumerate(pt)]
    kb.append([InlineKeyboardButton(t["back"], callback_data="back_brand")])
    await q.edit_message_text(t["choose_price"], reply_markup=InlineKeyboardMarkup(kb))
    return PRICE_TYPE

async def price_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang = context.user_data.get("lang", "ru")
    t = TEXTS[lang]

    if q.data == "back_brand":
        kb = [[InlineKeyboardButton(b, callback_data=f"brand_{i}")] for i, b in enumerate(BRANDS)]
        await q.edit_message_text(t["choose_brand"], reply_markup=InlineKeyboardMarkup(kb))
        return BRAND

    idx = int(q.data.split("_")[1])
    context.user_data["price_type"] = t["price_types"][idx]
    products = get_products(context.user_data["brand"])
    context.user_data["products"] = products
    context.user_data["page"] = 0
    await show_catalog(q, context)
    return CATALOG

async def show_catalog(q, context, page=None, search=None):
    lang = context.user_data.get("lang", "ru")
    t = TEXTS[lang]
    if page is not None:
        context.user_data["page"] = page
    page = context.user_data.get("page", 0)
    all_products = context.user_data.get("products", [])

    if search:
        products = [p for p in all_products if search.lower() in str(p.get("Название", "")).lower()]
    else:
        products = all_products

    cart = context.user_data.get("cart", {})
    PAGE = 7
    total_pages = max(1, (len(products) + PAGE - 1) // PAGE)
    page = min(page, total_pages - 1)
    items = products[page * PAGE:(page + 1) * PAGE]
    total_items = sum(v["qty"] for v in cart.values())
    total_sum = sum(v["qty"] * v["price"] for v in cart.values())

    brand = context.user_data.get("brand", "")
    text = f"📦 {brand}\n{t['catalog_title']}"
    if total_items > 0:
        text += f"\n🛒 {total_items} {t['pcs']} — {total_sum:,} {t['sum']}"
    text += f"\n📄 {page+1}/{total_pages}"

    kb = []
    for i, p in enumerate(items):
        real_i = page * PAGE + i
        name = str(p.get("Название", f"Товар {real_i+1}"))
        price = int(p.get("Цена", 0))
        stock = int(p.get("Остаток", 0))
        in_c = cart.get(real_i, {}).get("qty", 0)
        label = f"{'✅' if in_c else '+'} {name[:22]}"
        if in_c:
            label += f" [{in_c}]"
        label += f" — {price:,}"
        kb.append([InlineKeyboardButton(label, callback_data=f"item_{real_i}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"page_{page-1}"))
    nav.append(InlineKeyboardButton(t["search"], callback_data="search"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"page_{page+1}"))
    kb.append(nav)

    if cart:
        kb.append([InlineKeyboardButton(
            f"🛒 {total_items} {t['pcs']} — {total_sum:,} {t['sum']}",
            callback_data="view_cart"
        )])
    kb.append([InlineKeyboardButton(t["back"], callback_data="back_price")])
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def catalog_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    lang = context.user_data.get("lang", "ru")
    t = TEXTS[lang]

    if data.startswith("item_"):
        idx = int(data.split("_")[1])
        products = context.user_data.get("products", [])
        if idx < len(products):
            p = products[idx]
            context.user_data["selected_item"] = idx
            name = str(p.get("Название", ""))
            price = int(p.get("Цена", 0))
            stock = int(p.get("Остаток", 0))
            photo_url = p.get("Фото", "")
            cart = context.user_data.get("cart", {})
            current_qty = cart.get(idx, {}).get("qty", 0)

            text = (f"📦 {name}\n"
                   f"💵 {price:,} {t['sum']}\n"
                   f"📊 {t['out_of_stock'] if stock == 0 else f'Остаток: {stock} {t[\"pcs\"]}'}\n\n"
                   f"🛒 В корзине: {current_qty} {t['pcs']}\n\n"
                   f"{t['qty_prompt']}")

            kb = [
                [InlineKeyboardButton("1", callback_data=f"qty_1"),
                 InlineKeyboardButton("2", callback_data=f"qty_2"),
                 InlineKeyboardButton("3", callback_data=f"qty_3")],
                [InlineKeyboardButton("5", callback_data=f"qty_5"),
                 InlineKeyboardButton("10", callback_data=f"qty_10"),
                 InlineKeyboardButton("20", callback_data=f"qty_20")],
                [InlineKeyboardButton("➕ Добавить ещё", callback_data=f"qty_plus"),
                 InlineKeyboardButton("➖ Убрать", callback_data=f"qty_minus")],
                [InlineKeyboardButton(t["back"], callback_data="back_catalog")],
            ]

            if photo_url:
                try:
                    await q.message.reply_photo(photo=photo_url, caption=text, reply_markup=InlineKeyboardMarkup(kb))
                    return PRODUCT_QTY
                except:
                    pass
            await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
            return PRODUCT_QTY

    elif data.startswith("page_"):
        await show_catalog(q, context, int(data.split("_")[1]))

    elif data == "search":
        await q.edit_message_text(t["enter_search"])
        return CATALOG

    elif data == "view_cart":
        await show_cart(q, context)

    elif data == "back_price":
        pt = t["price_types"]
        kb = [[InlineKeyboardButton(p, callback_data=f"price_{i}")] for i, p in enumerate(pt)]
        kb.append([InlineKeyboardButton(t["back"], callback_data="back_brand")])
        await q.edit_message_text(t["choose_price"], reply_markup=InlineKeyboardMarkup(kb))
        return PRICE_TYPE

    elif data == "back_catalog":
        await show_catalog(q, context)

    return CATALOG

async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search = update.message.text.strip()
    lang = context.user_data.get("lang", "ru")
    t = TEXTS[lang]
    products = context.user_data.get("products", [])
    results = [p for p in products if search.lower() in str(p.get("Название", "")).lower()]
    if not results:
        await update.message.reply_text(t["no_results"])
        return CATALOG
    context.user_data["search_results"] = results
    # Показать результаты как inline
    kb = []
    for i, p in enumerate(results[:10]):
        name = str(p.get("Название", ""))
        price = int(p.get("Цена", 0))
        kb.append([InlineKeyboardButton(f"{name[:25]} — {price:,}", callback_data=f"item_{i}")])
    kb.append([InlineKeyboardButton(t["back"], callback_data="back_catalog")])
    await update.message.reply_text(f"🔍 Результаты: {len(results)}", reply_markup=InlineKeyboardMarkup(kb))
    return CATALOG

async def qty_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    lang = context.user_data.get("lang", "ru")
    t = TEXTS[lang]
    idx = context.user_data.get("selected_item")
    products = context.user_data.get("products", [])
    cart = context.user_data.get("cart", {})

    if data == "back_catalog":
        await show_catalog(q, context)
        return CATALOG

    if idx is None or idx >= len(products):
        await show_catalog(q, context)
        return CATALOG

    p = products[idx]
    name = str(p.get("Название", ""))
    price = int(p.get("Цена", 0))
    current = cart.get(idx, {}).get("qty", 0)

    if data.startswith("qty_"):
        action = data.split("_")[1]
        if action == "plus":
            current += 1
        elif action == "minus":
            current = max(0, current - 1)
        else:
            current = int(action)

    if current > 0:
        cart[idx] = {"name": name, "price": price, "qty": current}
    elif idx in cart:
        del cart[idx]
    context.user_data["cart"] = cart

    total_items = sum(v["qty"] for v in cart.values())
    total_sum = sum(v["qty"] * v["price"] for v in cart.values())

    text = (f"📦 {name}\n"
           f"💵 {price:,} {t['sum']}\n\n"
           f"🛒 В корзине: {current} {t['pcs']}\n"
           f"💵 Итого: {total_sum:,} {t['sum']}\n\n"
           f"{t['qty_prompt']}")

    kb = [
        [InlineKeyboardButton("1", callback_data="qty_1"),
         InlineKeyboardButton("2", callback_data="qty_2"),
         InlineKeyboardButton("3", callback_data="qty_3")],
        [InlineKeyboardButton("5", callback_data="qty_5"),
         InlineKeyboardButton("10", callback_data="qty_10"),
         InlineKeyboardButton("20", callback_data="qty_20")],
        [InlineKeyboardButton("➕ Добавить ещё", callback_data="qty_plus"),
         InlineKeyboardButton("➖ Убрать", callback_data="qty_minus")],
        [InlineKeyboardButton(t["back"], callback_data="back_catalog")],
    ]
    if cart:
        kb.insert(3, [InlineKeyboardButton(
            f"🛒 Корзина ({total_items} {t['pcs']}) — {total_sum:,} {t['sum']}",
            callback_data="go_cart"
        )])

    try:
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
    except:
        pass
    return PRODUCT_QTY

async def go_cart_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await show_cart(q, context)
    return CATALOG

async def show_cart(q, context):
    lang = context.user_data.get("lang", "ru")
    t = TEXTS[lang]
    cart = context.user_data.get("cart", {})
    if not cart:
        await q.edit_message_text(t["order_empty"])
        return
    text = t["cart_title"]
    total = 0
    for item in cart.values():
        sub = item["qty"] * item["price"]
        total += sub
        text += f"• {item['name']}\n  {item['qty']} {t['pcs']} × {item['price']:,} = {sub:,} {t['sum']}\n\n"
    text += f"{t['total']}{total:,} {t['sum']}"
    min_order = get_min_order()
    if min_order > 0 and total < min_order:
        text += f"\n\n⚠️ {t['min_order']}{min_order:,} {t['sum']}"
    kb = [
        [InlineKeyboardButton(t["confirm_order"], callback_data="confirm")],
        [InlineKeyboardButton(t["clear_cart"], callback_data="clear_cart")],
        [InlineKeyboardButton(t["back"], callback_data="back_catalog")],
    ]
    if min_order > 0 and total < min_order:
        kb = [[InlineKeyboardButton(t["back"], callback_data="back_catalog")]]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def confirm_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    lang = context.user_data.get("lang", "ru")
    t = TEXTS[lang]
    cart = context.user_data.get("cart", {})
    shop = context.user_data.get("shop", {})

    if data == "clear_cart":
        context.user_data["cart"] = {}
        await show_catalog(q, context)
        return CATALOG

    if data == "back_catalog":
        await show_catalog(q, context)
        return CATALOG

    if data == "confirm":
        if not cart:
            await q.edit_message_text(t["order_empty"])
            return CATALOG

        total = sum(v["qty"] * v["price"] for v in cart.values())
        min_order = get_min_order()
        if min_order > 0 and total < min_order:
            await q.edit_message_text(f"{t['min_order']}{min_order:,} {t['sum']}")
            return CATALOG

        brand = context.user_data.get("brand", "")
        price_type = context.user_data.get("price_type", "")
        items = list(cart.values())
        now = datetime.now().strftime("%d.%m.%Y %H:%M")

        order_data = {
            "shop_name": shop.get("Название", ""),
            "address": shop.get("Адрес", ""),
            "brand": brand,
            "price_type": price_type,
            "items": items,
            "total": total
        }
        order_id = save_order(order_data)

        # Красивый чек
        receipt = (f"🧾 ЗАКАЗ {order_id}\n"
                  f"📅 {now}\n"
                  f"🏪 {shop.get('Название', '')}\n"
                  f"📍 {shop.get('Адрес', '')}\n"
                  f"📦 {brand}\n"
                  f"💰 {price_type}\n\n"
                  f"Товары:\n")
        for item in items:
            receipt += f"• {item['name']} × {item['qty']} = {item['qty']*item['price']:,}\n"
        receipt += f"\n💵 ИТОГО: {total:,} {t['sum']}"

        # Отправить в группу через 30 минут (сохранить для отмены)
        context.user_data["pending_order"] = {
            "order_id": order_id,
            "receipt": receipt,
            "time": datetime.now().isoformat()
        }
        context.user_data["cart"] = {}

        kb = [[InlineKeyboardButton(t["cancel_order"], callback_data=f"cancel_order_{order_id}")]]
        await q.edit_message_text(
            f"{receipt}\n\n{t['order_confirmed']}",
            reply_markup=InlineKeyboardMarkup(kb)
        )

        # Отправить в группу сразу (можно настроить задержку)
        try:
            await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=receipt)
        except Exception as e:
            logger.error(f"Group send error: {e}")

        return CATALOG

    if data.startswith("cancel_order_"):
        order_id = data.replace("cancel_order_", "")
        pending = context.user_data.get("pending_order", {})
        order_time = datetime.fromisoformat(pending.get("time", datetime.now().isoformat()))
        if datetime.now() - order_time <= timedelta(minutes=30):
            cancel_order_in_sheets(order_id)
            await q.edit_message_text(t["order_cancelled"])
            try:
                await context.bot.send_message(
                    chat_id=GROUP_CHAT_ID,
                    text=f"❌ ЗАКАЗ {order_id} ОТМЕНЁН магазином {shop.get('Название', '')}"
                )
            except:
                pass
        else:
            await q.edit_message_text("❌ Время отмены истекло (30 минут).")
        return CATALOG

    return CATALOG

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        client = get_sheets_client()
        sheet = client.open(SPREADSHEET_NAME).worksheet("Заказы")
        records = sheet.get_all_records()
        today = datetime.now().strftime("%d.%m.%Y")
        today_orders = [r for r in records if r.get("Дата", "").startswith(today)]
        total_sum = sum(int(r.get("Итого", 0)) for r in today_orders if r.get("Статус") == "активен")
        count = len(set(r.get("ID") for r in today_orders))
        await update.message.reply_text(
            f"📊 Статистика за сегодня:\n\n"
            f"📦 Заказов: {count}\n"
            f"💵 Сумма: {total_sum:,} сум"
        )
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("До свидания! /start — начать заново.")
    return ConversationHandler.END

# ============================================================
# ЗАПУСК
# ============================================================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            REGISTER_NAME: [
                CallbackQueryHandler(lang_chosen, pattern="^lang_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_shop_name)
            ],
            REGISTER_ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_shop_address)
            ],
            WAIT_APPROVAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND,
                    lambda u, c: u.message.reply_text(TEXTS[c.user_data.get("lang","ru")]["wait_approval"]))
            ],
            BRAND: [
                CallbackQueryHandler(brand_chosen, pattern="^(brand_|history|repeat)"),
            ],
            PRICE_TYPE: [
                CallbackQueryHandler(price_chosen),
            ],
            CATALOG: [
                CallbackQueryHandler(catalog_action, pattern="^(item_|page_|search|view_cart|back_|go_cart)"),
                CallbackQueryHandler(confirm_action, pattern="^(confirm|clear_cart|cancel_order_|back_catalog)"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search),
            ],
            PRODUCT_QTY: [
                CallbackQueryHandler(qty_action, pattern="^qty_"),
                CallbackQueryHandler(go_cart_action, pattern="^go_cart"),
                CallbackQueryHandler(qty_action, pattern="^back_catalog"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CallbackQueryHandler(admin_action, pattern="^(approve|reject)_"))

    logger.info("🤖 Бот запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
