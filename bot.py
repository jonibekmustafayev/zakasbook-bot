
import asyncio
import aiosqlite
from datetime import datetime
 
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
 
 
# =========================
# SOZLAMALAR
# =========================
TOKEN = "8574924900:AAHou0j8Rz0vm2xrmGTxkBZ8jQD5czoZmZM"
ADMIN_ID = 6722242402
ADMIN_USERNAME = "@admoyin_lvl"
ADMIN_PHONE = "+998931407381"
 
# To'lov rekvizitlari
HUMO_CARD = "9860 1701 3065 6763"
VISA_CARD = "4023 0602 0575 2529"
 
# Kitoblar katalogi (admin tomonidan dinamik boshqariladi)
BOOKS: dict = {}
 
bot = Bot(token=TOKEN)
dp = Dispatcher()
 
 
# =========================
# HOLATLAR (FSM)
# =========================
class OrderState(StatesGroup):
    waiting_full_name = State()
    waiting_phone = State()
    waiting_address = State()
    waiting_payment = State()
    waiting_check = State()
 
 
class AddBookState(StatesGroup):
    waiting_book_name = State()
    waiting_book_author = State()
    waiting_book_price = State()
    waiting_book_description = State()
    waiting_book_photo = State()
 
 
class SearchState(StatesGroup):
    waiting_search_query = State()
 
 
# =========================
# KLAVIATURALAR
# =========================
def main_menu_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    """Foydalanuvchi uchun asosiy menyu — admin tugmalari ko'rinmaydi"""
    buttons = [
        [KeyboardButton(text="📚 Kitoblar"), KeyboardButton(text="🔍 Kitob qidirish")],
        [KeyboardButton(text="📦 Buyurtmalarim"), KeyboardButton(text="ℹ️ Aloqa")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
 
 
def admin_menu_keyboard() -> ReplyKeyboardMarkup:
    """Faqat admin ko'radigan menyu"""
    buttons = [
        [KeyboardButton(text="📚 Kitoblar"), KeyboardButton(text="🔍 Kitob qidirish")],
        [KeyboardButton(text="📦 Buyurtmalarim"), KeyboardButton(text="ℹ️ Aloqa")],
        [KeyboardButton(text="➕ Kitob qo'shish"), KeyboardButton(text="📋 Kitob ro'yxati (Admin)")],
        [KeyboardButton(text="📊 Admin panel")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
 
 
def get_main_menu(user_id: int) -> ReplyKeyboardMarkup:
    if user_id == ADMIN_ID:
        return admin_menu_keyboard()
    return main_menu_keyboard(user_id)
 
 
payment_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💳 Humo"), KeyboardButton(text="💳 Visa")],
        [KeyboardButton(text="💵 Naqd"), KeyboardButton(text="❌ Bekor qilish")],
    ],
    resize_keyboard=True,
)
 
cancel_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
    resize_keyboard=True,
)
 
 
def books_keyboard(page: int = 0, search_results: list = None) -> InlineKeyboardMarkup:
    source = search_results if search_results is not None else list(BOOKS.keys())
    page_size = 5
    start = page * page_size
    end = start + page_size
    page_books = source[start:end]
 
    rows = []
    for book_id in page_books:
        if book_id in BOOKS:
            book = BOOKS[book_id]
            rows.append([
                InlineKeyboardButton(
                    text=f"📖 {book['name']} — {book['price']:,} so'm".replace(",", " "),
                    callback_data=f"book:{book_id}",
                )
            ])
 
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"page:{page-1}"))
    if end < len(source):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"page:{page+1}"))
    if nav:
        rows.append(nav)
 
    return InlineKeyboardMarkup(inline_keyboard=rows)
 
 
def order_keyboard(book_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📦 Buyurtma berish", callback_data=f"order:{book_id}")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back:books")],
        ]
    )
 
 
def admin_order_keyboard(order_id: int, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"admin_confirm:{order_id}:{user_id}"),
                InlineKeyboardButton(text="🚚 Yuborildi", callback_data=f"admin_sent:{order_id}:{user_id}"),
            ],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"admin_cancel:{order_id}:{user_id}")],
        ]
    )
 
 
def admin_book_keyboard(book_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"edit_book:{book_id}"),
                InlineKeyboardButton(text="🗑️ O'chirish", callback_data=f"delete_book:{book_id}"),
            ],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:books_list")],
        ]
    )
 
 
# =========================
# MA'LUMOTLAR BAZASI
# =========================
async def init_db():
    async with aiosqlite.connect("orders.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT,
                phone TEXT,
                address TEXT,
                payment_method TEXT,
                book_id TEXT NOT NULL,
                book_name TEXT NOT NULL,
                price INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'yangi',
                created_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                author TEXT NOT NULL,
                price INTEGER NOT NULL,
                description TEXT,
                photo TEXT,
                created_at TEXT NOT NULL
            )
        """)
        await db.commit()
    await load_books_from_db()
 
 
async def load_books_from_db():
    global BOOKS
    BOOKS = {}
    async with aiosqlite.connect("orders.db") as db:
        async with db.execute("SELECT * FROM books ORDER BY created_at DESC") as cur:
            rows = await cur.fetchall()
    for row in rows:
        BOOKS[row[0]] = {
            "name": row[1],
            "author": row[2],
            "price": row[3],
            "description": row[4],
            "photo": row[5],
        }
 
 
async def save_book_to_db(book_id: str, name: str, author: str, price: int, description: str, photo: str):
    async with aiosqlite.connect("orders.db") as db:
        await db.execute(
            "INSERT OR REPLACE INTO books (id, name, author, price, description, photo, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (book_id, name, author, price, description, photo, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        await db.commit()
    await load_books_from_db()
 
 
async def delete_book_from_db(book_id: str):
    async with aiosqlite.connect("orders.db") as db:
        await db.execute("DELETE FROM books WHERE id = ?", (book_id,))
        await db.commit()
    await load_books_from_db()
 
 
async def save_order_to_db(user_id, username, full_name, phone, address, payment_method, book_id):
    book = BOOKS[book_id]
    async with aiosqlite.connect("orders.db") as db:
        cursor = await db.execute(
            """INSERT INTO orders (user_id, username, full_name, phone, address, payment_method,
               book_id, book_name, price, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, username, full_name, phone, address, payment_method,
             book_id, book["name"], book["price"], "yangi",
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        await db.commit()
        return cursor.lastrowid
 
 
async def update_order_status(order_id: int, new_status: str):
    async with aiosqlite.connect("orders.db") as db:
        await db.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
        await db.commit()
 
 
async def get_order_by_id(order_id: int):
    async with aiosqlite.connect("orders.db") as db:
        async with db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)) as cur:
            return await cur.fetchone()
 
 
# =========================
# YORDAMCHI FUNKSIYALAR
# =========================
def format_order_row(row) -> str:
    status_emoji = {
        "yangi": "🆕",
        "tasdiqlandi": "✅",
        "yuborildi": "🚚",
        "bekor qilindi": "❌",
    }.get(row[10], "📌")
 
    return (
        f"━━━━━━━━━━━━━━━━\n"
        f"🧾 Buyurtma #{row[0]}\n"
        f"📖 Kitob: {row[8]}\n"
        f"💰 Narx: {row[9]:,} so'm\n"
        f"{status_emoji} Holat: {row[10]}\n"
        f"🕒 Sana: {row[11]}\n"
        f"━━━━━━━━━━━━━━━━"
    ).replace(",", " ")
 
 
def generate_book_id(name: str) -> str:
    import re
    book_id = re.sub(r'[^a-zA-Z0-9_]', '_', name.lower().replace(' ', '_'))
    return book_id[:30] + f"_{int(datetime.now().timestamp())}"
 
 
# =========================
# BOSHLASH VA ASOSIY BUYRUQLAR
# =========================
@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()
    name = message.from_user.first_name or "Foydalanuvchi"
    text = (
        f"Assalomu alaykum, {name}! 👋\n\n"
        "📚 <b>Kitob do'konimizga xush kelibsiz!</b>\n\n"
        "Bu yerda siz:\n"
        "• 📖 Kitoblarni ko'rishingiz\n"
        "• 🔍 Qidirish orqali topishingiz\n"
        "• 📦 Buyurtma berishingiz mumkin\n\n"
        "Quyidagi menyudan boshlang 👇"
    )
    await message.answer(text, reply_markup=get_main_menu(message.from_user.id), parse_mode="HTML")
 
 
@dp.message(Command("myid"))
async def myid_handler(message: Message):
    await message.answer(f"🆔 Sizning Telegram ID: <code>{message.from_user.id}</code>", parse_mode="HTML")
 
 
@dp.message(Command("admin"))
async def admin_panel_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Bu buyruq faqat admin uchun.")
        return
    await show_admin_stats(message)
 
 
async def show_admin_stats(message: Message):
    async with aiosqlite.connect("orders.db") as db:
        async with db.execute("SELECT COUNT(*) FROM orders") as cur:
            total = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM orders WHERE status='yangi'") as cur:
            new_c = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM orders WHERE status='tasdiqlandi'") as cur:
            confirmed = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM orders WHERE status='yuborildi'") as cur:
            sent = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM orders WHERE status='bekor qilindi'") as cur:
            canceled = (await cur.fetchone())[0]
        async with db.execute("SELECT SUM(price) FROM orders WHERE status='yuborildi'") as cur:
            revenue_row = await cur.fetchone()
            revenue = revenue_row[0] if revenue_row[0] else 0
 
    text = (
        "📊 <b>Admin Panel</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"📦 Jami buyurtmalar: <b>{total}</b>\n"
        f"🆕 Yangi: <b>{new_c}</b>\n"
        f"✅ Tasdiqlangan: <b>{confirmed}</b>\n"
        f"🚚 Yuborilgan: <b>{sent}</b>\n"
        f"❌ Bekor qilingan: <b>{canceled}</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"💰 Jami daromad: <b>{revenue:,} so'm</b>\n"
        f"📚 Kitoblar soni: <b>{len(BOOKS)}</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        "📋 Buyurtmalar: /orders\n"
        "➕ Kitob qo'shish: menyu tugmasidan"
    ).replace(",", " ")
    await message.answer(text, parse_mode="HTML")
 
 
@dp.message(Command("orders"))
async def admin_orders_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Bu buyruq faqat admin uchun.")
        return
 
    async with aiosqlite.connect("orders.db") as db:
        async with db.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 10") as cur:
            rows = await cur.fetchall()
 
    if not rows:
        await message.answer("📭 Hali buyurtmalar yo'q.")
        return
 
    await message.answer(f"📋 <b>So'nggi {len(rows)} ta buyurtma:</b>", parse_mode="HTML")
    for row in rows:
        text = (
            f"🧾 <b>Buyurtma #{row[0]}</b>\n"
            f"👤 @{row[2] if row[2] else 'yoq'} (ID: {row[1]})\n"
            f"🙍 {row[3]}\n"
            f"📞 {row[4]}\n"
            f"🏠 {row[5]}\n"
            f"💳 To'lov: {row[6]}\n"
            f"📖 {row[8]}\n"
            f"💰 {row[9]:,} so'm\n"
            f"📌 {row[10]}\n"
            f"🕒 {row[11]}"
        ).replace(",", " ")
        await message.answer(text, reply_markup=admin_order_keyboard(row[0], row[1]), parse_mode="HTML")
 
 
# =========================
# FOYDALANUVCHI MENYUSI
# =========================
@dp.message(F.text == "📚 Kitoblar")
async def books_handler(message: Message):
    if not BOOKS:
        await message.answer(
            "📭 Hozircha kitoblar mavjud emas.\n"
            f"Yangi kitoblar haqida ma'lumot olish uchun: {ADMIN_USERNAME}",
            reply_markup=get_main_menu(message.from_user.id),
        )
        return
    await message.answer(
        f"📚 <b>Mavjud kitoblar ({len(BOOKS)} ta):</b>\n\nKitobni tanlang 👇",
        reply_markup=books_keyboard(),
        parse_mode="HTML",
    )
 
 
@dp.message(F.text == "🔍 Kitob qidirish")
async def search_start_handler(message: Message, state: FSMContext):
    await state.set_state(SearchState.waiting_search_query)
    await message.answer(
        "🔍 <b>Kitob qidirish</b>\n\n"
        "Kitob nomi yoki muallif ismini yozing:",
        reply_markup=cancel_keyboard,
        parse_mode="HTML",
    )
 
 
@dp.message(SearchState.waiting_search_query)
async def search_query_handler(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bosh menyu:", reply_markup=get_main_menu(message.from_user.id))
        return
 
    query = message.text.strip().lower()
    results = [
        book_id for book_id, book in BOOKS.items()
        if query in book["name"].lower() or query in book["author"].lower() or query in book.get("description", "").lower()
    ]
 
    await state.clear()
 
    if not results:
        await message.answer(
            f"❌ <b>'{message.text}'</b> bo'yicha hech narsa topilmadi.\n\n"
            f"Kerakli kitob bo'lmasa, adminga murojaat qiling: {ADMIN_USERNAME}",
            reply_markup=get_main_menu(message.from_user.id),
            parse_mode="HTML",
        )
        return
 
    await message.answer(
        f"🔍 <b>Qidiruv natijalari: {len(results)} ta kitob</b>",
        reply_markup=books_keyboard(search_results=results),
        parse_mode="HTML",
    )
 
 
@dp.message(F.text == "ℹ️ Aloqa")
async def contact_handler(message: Message):
    await message.answer(
        "📞 <b>Aloqa</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"👤 Admin: {ADMIN_USERNAME}\n"
        f"📱 Telefon: {ADMIN_PHONE}\n"
        "━━━━━━━━━━━━━━━━\n"
        "📦 Buyurtma, savollar va takliflar uchun murojaat qiling!",
        parse_mode="HTML",
    )
 
 
@dp.message(F.text == "📦 Buyurtmalarim")
async def my_orders_handler(message: Message):
    async with aiosqlite.connect("orders.db") as db:
        async with db.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC", (message.from_user.id,)
        ) as cur:
            rows = await cur.fetchall()
 
    if not rows:
        await message.answer(
            "📭 Sizda hali buyurtmalar yo'q.\n"
            "Kitob xarid qilish uchun <b>📚 Kitoblar</b> bo'limiga o'ting.",
            parse_mode="HTML",
        )
        return
 
    await message.answer(f"📦 <b>Sizning buyurtmalaringiz ({len(rows)} ta):</b>", parse_mode="HTML")
    for row in rows[:10]:
        await message.answer(format_order_row(row))
 
 
# =========================
# ADMIN KITOB QO'SHISH
# =========================
@dp.message(F.text == "➕ Kitob qo'shish")
async def add_book_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Bu funksiya faqat admin uchun.")
        return
    await state.set_state(AddBookState.waiting_book_name)
    await message.answer(
        "➕ <b>Yangi kitob qo'shish</b>\n\n"
        "📌 Kitob nomini yozing:",
        reply_markup=cancel_keyboard,
        parse_mode="HTML",
    )
 
 
@dp.message(AddBookState.waiting_book_name)
async def add_book_name(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=get_main_menu(message.from_user.id))
        return
    await state.update_data(book_name=message.text.strip())
    await state.set_state(AddBookState.waiting_book_author)
    await message.answer("✍️ Muallif ismini yozing:")
 
 
@dp.message(AddBookState.waiting_book_author)
async def add_book_author(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=get_main_menu(message.from_user.id))
        return
    await state.update_data(book_author=message.text.strip())
    await state.set_state(AddBookState.waiting_book_price)
    await message.answer("💰 Narxini yozing (faqat raqam, so'mda):\nMasalan: 50000")
 
 
@dp.message(AddBookState.waiting_book_price)
async def add_book_price(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=get_main_menu(message.from_user.id))
        return
    try:
        price = int(message.text.strip().replace(" ", "").replace(",", ""))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Narx noto'g'ri. Faqat musbat raqam kiriting. Masalan: 50000")
        return
    await state.update_data(book_price=price)
    await state.set_state(AddBookState.waiting_book_description)
    await message.answer("📝 Kitob haqida qisqacha tavsif yozing:")
 
 
@dp.message(AddBookState.waiting_book_description)
async def add_book_description(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=get_main_menu(message.from_user.id))
        return
    await state.update_data(book_description=message.text.strip())
    await state.set_state(AddBookState.waiting_book_photo)
    await message.answer(
        "🖼 Kitob rasmini yuboring (foto sifatida) yoki rasm URL manzilini yozing:\n"
        "Agar rasm bo'lmasa <b>o'tkazib yuborish</b> deb yozing.",
        parse_mode="HTML",
    )
 
 
@dp.message(AddBookState.waiting_book_photo)
async def add_book_photo(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=get_main_menu(message.from_user.id))
        return
 
    photo = None
    if message.photo:
        photo = message.photo[-1].file_id
    elif message.text and message.text.lower() != "o'tkazib yuborish":
        photo = message.text.strip()
 
    data = await state.get_data()
    book_id = generate_book_id(data["book_name"])
 
    await save_book_to_db(
        book_id=book_id,
        name=data["book_name"],
        author=data["book_author"],
        price=data["book_price"],
        description=data["book_description"],
        photo=photo,
    )
 
    await state.clear()
    await message.answer(
        f"✅ <b>Kitob muvaffaqiyatli qo'shildi!</b>\n\n"
        f"📖 Nomi: {data['book_name']}\n"
        f"✍️ Muallif: {data['book_author']}\n"
        f"💰 Narxi: {data['book_price']:,} so'm\n"
        f"📚 Jami kitoblar: {len(BOOKS)} ta".replace(",", " "),
        reply_markup=get_main_menu(message.from_user.id),
        parse_mode="HTML",
    )
 
 
# =========================
# ADMIN KITOBLAR RO'YXATI
# =========================
@dp.message(F.text == "📋 Kitob ro'yxati (Admin)")
async def admin_books_list(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Bu funksiya faqat admin uchun.")
        return
 
    if not BOOKS:
        await message.answer("📭 Hech qanday kitob yo'q. Qo'shish uchun ➕ tugmasini bosing.")
        return
 
    text = f"📚 <b>Barcha kitoblar ({len(BOOKS)} ta):</b>\n\n"
    for i, (book_id, book) in enumerate(BOOKS.items(), 1):
        text += f"{i}. <b>{book['name']}</b> — {book['price']:,} so'm\n".replace(",", " ")
 
    await message.answer(text, parse_mode="HTML")
 
    for book_id, book in BOOKS.items():
        btn_text = (
            f"📖 {book['name']} | {book['price']:,} so'm".replace(",", " ")
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"🗑️ O'chirish: {book['name']}", callback_data=f"delete_book:{book_id}")]
        ])
        await message.answer(btn_text, reply_markup=kb)
 
 
@dp.message(F.text == "📊 Admin panel")
async def admin_panel_btn(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Bu funksiya faqat admin uchun.")
        return
    await show_admin_stats(message)
 
 
# =========================
# INLINE TUGMALAR
# =========================
@dp.callback_query(F.data == "back:books")
async def back_books_handler(callback: CallbackQuery):
    if not BOOKS:
        await callback.message.answer("📭 Hozircha kitoblar yo'q.")
        await callback.answer()
        return
    await callback.message.answer("📚 Kitoblar ro'yxati:", reply_markup=books_keyboard())
    await callback.answer()
 
 
@dp.callback_query(F.data.startswith("page:"))
async def page_handler(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    try:
        await callback.message.edit_reply_markup(reply_markup=books_keyboard(page=page))
    except Exception:
        await callback.message.answer("📚 Kitoblar:", reply_markup=books_keyboard(page=page))
    await callback.answer()
 
 
@dp.callback_query(F.data == "admin:books_list")
async def admin_books_inline(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Ruxsat yo'q.", show_alert=True)
        return
    await callback.answer()
    await admin_books_list(callback.message)
 
 
@dp.callback_query(F.data.startswith("delete_book:"))
async def delete_book_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Ruxsat yo'q.", show_alert=True)
        return
    book_id = callback.data.split(":", 1)[1]
    book_name = BOOKS.get(book_id, {}).get("name", "Noma'lum")
    await delete_book_from_db(book_id)
    await callback.answer(f"✅ '{book_name}' o'chirildi.", show_alert=True)
    try:
        await callback.message.delete()
    except Exception:
        pass
 
 
@dp.callback_query(F.data.startswith("book:"))
async def book_detail_handler(callback: CallbackQuery):
    book_id = callback.data.split(":")[1]
    if book_id not in BOOKS:
        await callback.answer("Bu kitob mavjud emas.", show_alert=True)
        return
 
    book = BOOKS[book_id]
    caption = (
        f"📖 <b>{book['name']}</b>\n"
        f"✍️ Muallif: {book['author']}\n"
        f"💰 Narx: <b>{book['price']:,} so'm</b>\n\n"
        f"📝 {book.get('description', '')}"
    ).replace(",", " ")
 
    try:
        if book.get("photo"):
            await callback.message.answer_photo(
                photo=book["photo"],
                caption=caption,
                reply_markup=order_keyboard(book_id),
                parse_mode="HTML",
            )
        else:
            await callback.message.answer(caption, reply_markup=order_keyboard(book_id), parse_mode="HTML")
    except Exception:
        await callback.message.answer(caption, reply_markup=order_keyboard(book_id), parse_mode="HTML")
 
    await callback.answer()
 
 
@dp.callback_query(F.data.startswith("order:"))
async def start_order_handler(callback: CallbackQuery, state: FSMContext):
    book_id = callback.data.split(":")[1]
    if book_id not in BOOKS:
        await callback.answer("Bu kitob mavjud emas.", show_alert=True)
        return
 
    await state.update_data(book_id=book_id)
    await state.set_state(OrderState.waiting_full_name)
    book = BOOKS[book_id]
 
    await callback.message.answer(
        f"📦 <b>Buyurtma berish</b>\n\n"
        f"Kitob: <b>{book['name']}</b>\n"
        f"Narx: <b>{book['price']:,} so'm</b>\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"1️⃣ Ism-familiyangizni yozing:".replace(",", " "),
        reply_markup=cancel_keyboard,
        parse_mode="HTML",
    )
    await callback.answer()
 
 
# =========================
# FSM BUYURTMA BOSQICHLARI
# =========================
@dp.message(OrderState.waiting_full_name)
async def get_full_name_handler(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Buyurtma bekor qilindi.", reply_markup=get_main_menu(message.from_user.id))
        return
 
    full_name = message.text.strip()
    if len(full_name) < 3:
        await message.answer("❌ Iltimos, to'liq ism-familiyangizni kiriting (kamida 3 harf).")
        return
 
    await state.update_data(full_name=full_name)
    await state.set_state(OrderState.waiting_phone)
    await message.answer(
        f"✅ Ism qabul qilindi: <b>{full_name}</b>\n\n"
        "2️⃣ Telefon raqamingizni kiriting:\n"
        "📱 Masalan: +998901234567",
        parse_mode="HTML",
    )
 
 
@dp.message(OrderState.waiting_phone)
async def get_phone_handler(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Buyurtma bekor qilindi.", reply_markup=get_main_menu(message.from_user.id))
        return
 
    phone = message.text.strip()
    if len(phone) < 9:
        await message.answer("❌ Telefon raqam noto'g'ri. Qayta kiriting.\nMasalan: +998901234567")
        return
 
    await state.update_data(phone=phone)
    await state.set_state(OrderState.waiting_address)
    await message.answer(
        f"✅ Telefon qabul qilindi: <b>{phone}</b>\n\n"
        "3️⃣ Yetkazib berish manzilini yozing:\n"
        "🏠 Shahar, ko'cha, uy raqami",
        parse_mode="HTML",
    )
 
 
@dp.message(OrderState.waiting_address)
async def get_address_handler(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Buyurtma bekor qilindi.", reply_markup=get_main_menu(message.from_user.id))
        return
 
    address = message.text.strip()
    if len(address) < 5:
        await message.answer("❌ Manzilni to'liqroq yozing (kamida 5 belgi).")
        return
 
    await state.update_data(address=address)
    await state.set_state(OrderState.waiting_payment)
    await message.answer(
        f"✅ Manzil qabul qilindi: <b>{address}</b>\n\n"
        "4️⃣ To'lov usulini tanlang 👇",
        reply_markup=payment_keyboard,
        parse_mode="HTML",
    )
 
 
@dp.message(OrderState.waiting_payment)
async def get_payment_handler(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Buyurtma bekor qilindi.", reply_markup=get_main_menu(message.from_user.id))
        return
 
    allowed = {
        "💳 Humo": "Humo",
        "💳 Visa": "Visa",
        "💵 Naqd": "Naqd",
    }
    if message.text not in allowed:
        await message.answer("❌ Iltimos, tugmalardan birini tanlang.")
        return
 
    payment_method = allowed[message.text]
    data = await state.get_data()
    book = BOOKS.get(data["book_id"])
 
    if not book:
        await state.clear()
        await message.answer("❌ Xatolik: kitob topilmadi.", reply_markup=get_main_menu(message.from_user.id))
        return
 
    await state.update_data(payment_method=payment_method)
 
    # Chek yuborish so'rovi
    if payment_method in ("Humo", "Visa"):
        card = HUMO_CARD if payment_method == "Humo" else VISA_CARD
        await state.set_state(OrderState.waiting_check)
        await message.answer(
            f"💳 <b>{payment_method} orqali to'lov</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"Karta raqami:\n"
            f"<code>{card}</code>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"💰 To'lov summasi: <b>{book['price']:,} so'm</b>\n\n"
            f"✅ To'lovni amalga oshirgach, <b>chek (screenshot)ni shu yerga yuboring</b>.\n"
            f"Admin tekshirib, buyurtmangizni tasdiqlaydi.".replace(",", " "),
            reply_markup=cancel_keyboard,
            parse_mode="HTML",
        )
    else:
        # Naqd to'lov — chek shart emas
        await complete_order(message, state)
 
 
@dp.message(OrderState.waiting_check)
async def get_check_handler(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Buyurtma bekor qilindi.", reply_markup=get_main_menu(message.from_user.id))
        return
 
    if not message.photo and not message.document:
        await message.answer(
            "❌ Iltimos, to'lov chekini <b>rasm</b> yoki <b>fayl</b> ko'rinishida yuboring.",
            parse_mode="HTML",
        )
        return
 
    await complete_order(message, state, has_check=True)
 
 
async def complete_order(message: Message, state: FSMContext, has_check: bool = False):
    data = await state.get_data()
    book_id = data["book_id"]
    full_name = data["full_name"]
    phone = data["phone"]
    address = data["address"]
    payment_method = data["payment_method"]
 
    book = BOOKS[book_id]
 
    order_id = await save_order_to_db(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=full_name,
        phone=phone,
        address=address,
        payment_method=payment_method,
        book_id=book_id,
    )
 
    # Admin xabari
    admin_text = (
        f"🛒 <b>Yangi buyurtma #{order_id}</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"👤 User: @{message.from_user.username if message.from_user.username else 'yoq'} (ID: {message.from_user.id})\n"
        f"🙍 Ism: {full_name}\n"
        f"📞 Tel: {phone}\n"
        f"🏠 Manzil: {address}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📖 Kitob: <b>{book['name']}</b>\n"
        f"✍️ Muallif: {book['author']}\n"
        f"💰 Narx: <b>{book['price']:,} so'm</b>\n"
        f"💳 To'lov: <b>{payment_method}</b>\n"
        f"{'✅ Chek yuborildi' if has_check else '💵 Naqd tolov'}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ).replace(",", " ")
 
    await bot.send_message(ADMIN_ID, admin_text, reply_markup=admin_order_keyboard(order_id, message.from_user.id), parse_mode="HTML")
 
    # Chek bo'lsa adminga ham yuborish
    if has_check and message.photo:
        await bot.send_photo(
            ADMIN_ID,
            message.photo[-1].file_id,
            caption=f"🧾 Buyurtma #{order_id} — To'lov cheki",
        )
    elif has_check and message.document:
        await bot.send_document(
            ADMIN_ID,
            message.document.file_id,
            caption=f"🧾 Buyurtma #{order_id} — To'lov cheki",
        )
 
    # Foydalanuvchiga tasdiqlash xabari
    user_text = (
        f"🎉 <b>Buyurtmangiz qabul qilindi!</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🧾 Buyurtma raqami: <b>#{order_id}</b>\n"
        f"📖 Kitob: <b>{book['name']}</b>\n"
        f"💰 Narx: <b>{book['price']:,} so'm</b>\n"
        f"💳 To'lov: <b>{payment_method}</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"⏳ Admin tasdiqlashini kuting.\n"
        f"📦 Buyurtma holati: <b>Yangi</b>\n\n"
        f"Savollar uchun: {ADMIN_USERNAME}"
    ).replace(",", " ")
 
    await message.answer(user_text, reply_markup=get_main_menu(message.from_user.id), parse_mode="HTML")
    await state.clear()
 
 
# =========================
# ADMIN STATUS BOSHQARUVI
# =========================
@dp.callback_query(F.data.startswith("admin_confirm:"))
async def admin_confirm_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Siz admin emassiz.", show_alert=True)
        return
 
    parts = callback.data.split(":")
    order_id, user_id = int(parts[1]), int(parts[2])
    await update_order_status(order_id, "tasdiqlandi")
 
    try:
        await bot.send_message(
            user_id,
            f"✅ <b>Buyurtmangiz tasdiqlandi!</b>\n\n"
            f"🧾 Buyurtma #{order_id}\n"
            f"📦 Tez orada yetkazib beriladi.\n\n"
            f"Savollar: {ADMIN_USERNAME}",
            parse_mode="HTML",
        )
    except Exception:
        pass
 
    await callback.answer("✅ Tasdiqlandi!", show_alert=True)
    try:
        await callback.message.edit_text(
            callback.message.text + f"\n\n✅ <b>TASDIQLANDI</b> — {datetime.now().strftime('%H:%M')}",
            parse_mode="HTML",
        )
    except Exception:
        await callback.message.answer(f"✅ Buyurtma #{order_id} tasdiqlandi.")
 
 
@dp.callback_query(F.data.startswith("admin_sent:"))
async def admin_sent_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Siz admin emassiz.", show_alert=True)
        return
 
    parts = callback.data.split(":")
    order_id, user_id = int(parts[1]), int(parts[2])
    await update_order_status(order_id, "yuborildi")
 
    try:
        await bot.send_message(
            user_id,
            f"🚚 <b>Buyurtmangiz yo'lda!</b>\n\n"
            f"🧾 Buyurtma #{order_id}\n"
            f"📬 Kitob sizga yuborildi. Yaqin orada qo'lingizga yetadi!\n\n"
            f"Savollar: {ADMIN_USERNAME}",
            parse_mode="HTML",
        )
    except Exception:
        pass
 
    await callback.answer("🚚 Yuborildi!", show_alert=True)
    try:
        await callback.message.edit_text(
            callback.message.text + f"\n\n🚚 <b>YUBORILDI</b> — {datetime.now().strftime('%H:%M')}",
            parse_mode="HTML",
        )
    except Exception:
        await callback.message.answer(f"🚚 Buyurtma #{order_id} yuborildi.")
 
 
@dp.callback_query(F.data.startswith("admin_cancel:"))
async def admin_cancel_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Siz admin emassiz.", show_alert=True)
        return
 
    parts = callback.data.split(":")
    order_id, user_id = int(parts[1]), int(parts[2])
    await update_order_status(order_id, "bekor qilindi")
 
    try:
        await bot.send_message(
            user_id,
            f"❌ <b>Buyurtmangiz bekor qilindi.</b>\n\n"
            f"🧾 Buyurtma #{order_id}\n"
            f"Sabab yoki qo'shimcha ma'lumot uchun:\n"
            f"{ADMIN_USERNAME} ga murojaat qiling.",
            parse_mode="HTML",
        )
    except Exception:
        pass
 
    await callback.answer("❌ Bekor qilindi!", show_alert=True)
    try:
        await callback.message.edit_text(
            callback.message.text + f"\n\n❌ <b>BEKOR QILINDI</b> — {datetime.now().strftime('%H:%M')}",
            parse_mode="HTML",
        )
    except Exception:
        await callback.message.answer(f"❌ Buyurtma #{order_id} bekor qilindi.")
 
 
# =========================
# BOSHQA XABARLAR
# =========================
@dp.message()
async def fallback_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        return
    await message.answer(
        "Kerakli bo'limni tanlang 👇",
        reply_markup=get_main_menu(message.from_user.id),
    )
 
 
# =========================
# ISHGA TUSHIRISH
# =========================
async def main():
    await init_db()
    print("✅ Bot muvaffaqiyatli ishga tushdi!")
    await dp.start_polling(bot)
 
 
if __name__ == "__main__":
    asyncio.run(main())
