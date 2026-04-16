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
ADMIN_ID = 6722242402  # o'zingning Telegram ID'ing

# To'lov linklari (o'zingnikiga almashtir)
CLICK_URL = "https://my.click.uz/"
PAYME_URL = "https://payme.uz/home/main"

# Kitoblar katalogi
# photo qiymatiga Telegram file_id yoki rasm URL qo'yish mumkin
BOOKS = {
    "atomic_habits": {
        "name": "Atomic Habits",
        "price": 50000,
        "author": "James Clear",
        "description": "Foydali odatlar yaratish haqida mashhur kitob.",
        "photo": "https://images.unsplash.com/photo-1512820790803-83ca734da794?q=80&w=1200&auto=format&fit=crop",
    },
    "it_ends_with_us": {
        "name": "It Ends with Us",
        "price": 45000,
        "author": "Colleen Hoover",
        "description": "Emotsional va mashhur badiiy asar.",
        "photo": "https://images.unsplash.com/photo-1521587760476-6c12a4b040da?q=80&w=1200&auto=format&fit=crop",
    },
    "rich_dad_poor_dad": {
        "name": "Rich Dad Poor Dad",
        "price": 55000,
        "author": "Robert Kiyosaki",
        "description": "Moliyaviy fikrlashni o'zgartiradigan bestseller.",
        "photo": "https://images.unsplash.com/photo-1516979187457-637abb4f9353?q=80&w=1200&auto=format&fit=crop",
    },
}

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


# =========================
# KLAWIATURALAR
# =========================
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📚 Kitoblar")],
        [KeyboardButton(text="📦 Buyurtmalarim"), KeyboardButton(text="ℹ️ Aloqa")],
    ],
    resize_keyboard=True,
)

payment_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💳 Click"), KeyboardButton(text="💳 Payme")],
        [KeyboardButton(text="💵 Naqd")],
    ],
    resize_keyboard=True,
)


def books_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for book_id, book in BOOKS.items():
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"📖 {book['name']} — {book['price']:,} so'm".replace(",", " "),
                    callback_data=f"book:{book_id}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def order_keyboard(book_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📦 Buyurtma berish",
                    callback_data=f"order:{book_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Orqaga",
                    callback_data="back:books",
                )
            ],
        ]
    )


def admin_order_keyboard(order_id: int, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Tasdiqlash",
                    callback_data=f"admin_confirm:{order_id}:{user_id}",
                ),
                InlineKeyboardButton(
                    text="🚚 Yuborildi",
                    callback_data=f"admin_sent:{order_id}:{user_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Bekor qilish",
                    callback_data=f"admin_cancel:{order_id}:{user_id}",
                )
            ],
        ]
    )


# =========================
# BAZA
# =========================
async def init_db():
    async with aiosqlite.connect("orders.db") as db:
        await db.execute(
            """
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
            """
        )
        await db.commit()


# =========================
# YORDAMCHI FUNKSIYALAR
# =========================
def format_order_row(row) -> str:
    return (
        f"🧾 Buyurtma #{row[0]}\n"
        f"📖 Kitob: {row[8]}\n"
        f"💰 Narx: {row[9]:,} so'm\n"
        f"📌 Holat: {row[10]}\n"
        f"🕒 Sana: {row[11]}"
    ).replace(",", " ")


async def save_order_to_db(
    user_id: int,
    username: str | None,
    full_name: str,
    phone: str,
    address: str,
    payment_method: str,
    book_id: str,
):
    book = BOOKS[book_id]
    async with aiosqlite.connect("orders.db") as db:
        cursor = await db.execute(
            """
            INSERT INTO orders (
                user_id, username, full_name, phone, address, payment_method,
                book_id, book_name, price, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                username,
                full_name,
                phone,
                address,
                payment_method,
                book_id,
                book["name"],
                book["price"],
                "yangi",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        await db.commit()
        return cursor.lastrowid


async def update_order_status(order_id: int, new_status: str):
    async with aiosqlite.connect("orders.db") as db:
        await db.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            (new_status, order_id),
        )
        await db.commit()


async def get_order_by_id(order_id: int):
    async with aiosqlite.connect("orders.db") as db:
        async with db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)) as cur:
            return await cur.fetchone()


# =========================
# BUYRUQLAR
# =========================
@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()
    text = (
        "Assalomu alaykum! 📚\n\n"
        "Kitob do'konimizga xush kelibsiz.\n"
        "Quyidagilardan birini tanlang:"
    )
    await message.answer(text, reply_markup=main_menu)


@dp.message(Command("myid"))
async def myid_handler(message: Message):
    await message.answer(f"Sizning ID: `{message.from_user.id}`", parse_mode="Markdown")


@dp.message(Command("admin"))
async def admin_panel_handler(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz admin emassiz.")
        return

    async with aiosqlite.connect("orders.db") as db:
        async with db.execute("SELECT COUNT(*) FROM orders") as cur:
            total = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM orders WHERE status = 'yangi'") as cur:
            new_count = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM orders WHERE status = 'tasdiqlandi'") as cur:
            confirmed = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM orders WHERE status = 'yuborildi'") as cur:
            sent = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM orders WHERE status = 'bekor qilindi'") as cur:
            canceled = (await cur.fetchone())[0]

    text = (
        "📊 Admin panel\n\n"
        f"Jami buyurtmalar: {total}\n"
        f"Yangi: {new_count}\n"
        f"Tasdiqlangan: {confirmed}\n"
        f"Yuborilgan: {sent}\n"
        f"Bekor qilingan: {canceled}\n\n"
        "Oxirgi buyurtmalarni ko'rish uchun: /orders"
    )
    await message.answer(text)


@dp.message(Command("orders"))
async def admin_orders_handler(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz admin emassiz.")
        return

    async with aiosqlite.connect("orders.db") as db:
        async with db.execute(
            "SELECT * FROM orders ORDER BY id DESC LIMIT 10"
        ) as cur:
            rows = await cur.fetchall()

    if not rows:
        await message.answer("📭 Hali buyurtmalar yo'q.")
        return

    for row in rows:
        text = (
            f"🧾 Buyurtma #{row[0]}\n"
            f"👤 Username: @{row[2] if row[2] else 'yo‘q'}\n"
            f"🙍 Ism: {row[3]}\n"
            f"📞 Telefon: {row[4]}\n"
            f"🏠 Manzil: {row[5]}\n"
            f"💳 To'lov: {row[6]}\n"
            f"📖 Kitob: {row[8]}\n"
            f"💰 Narx: {row[9]:,} so'm\n"
            f"📌 Holat: {row[10]}\n"
            f"🕒 Sana: {row[11]}"
        ).replace(",", " ")

        await message.answer(
            text,
            reply_markup=admin_order_keyboard(row[0], row[1]),
        )


# =========================
# FOYDALANUVCHI MENYUSI
# =========================
@dp.message(F.text == "📚 Kitoblar")
async def books_handler(message: Message):
    await message.answer(
        "📚 Mavjud kitoblar ro'yxati:",
        reply_markup=main_menu,
    )
    await message.answer(
        "Pastdagi ro'yxatdan kitobni tanlang:",
        reply_markup=books_keyboard(),
    )


@dp.message(F.text == "ℹ️ Aloqa")
async def contact_handler(message: Message):
    await message.answer(
        "ℹ️ Aloqa uchun:\n"
        "Admin: @username\n"
        "Telefon: +998 XX XXX XX XX"
    )


@dp.message(F.text == "📦 Buyurtmalarim")
async def my_orders_handler(message: Message):
    async with aiosqlite.connect("orders.db") as db:
        async with db.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC",
            (message.from_user.id,),
        ) as cur:
            rows = await cur.fetchall()

    if not rows:
        await message.answer("📭 Sizda hali buyurtmalar yo'q.")
        return

    for row in rows[:10]:
        await message.answer(format_order_row(row))


# =========================
# INLINE TUGMALAR
# =========================
@dp.callback_query(F.data == "back:books")
async def back_books_handler(callback: CallbackQuery):
    await callback.message.answer(
        "📚 Kitoblar ro'yxati:",
        reply_markup=books_keyboard(),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("book:"))
async def book_detail_handler(callback: CallbackQuery):
    book_id = callback.data.split(":")[1]
    book = BOOKS[book_id]

    caption = (
        f"📖 {book['name']}\n"
        f"✍️ Muallif: {book['author']}\n"
        f"💰 Narx: {book['price']:,} so'm\n\n"
        f"📝 {book['description']}"
    ).replace(",", " ")

    await callback.message.answer_photo(
        photo=book["photo"],
        caption=caption,
        reply_markup=order_keyboard(book_id),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("order:"))
async def start_order_handler(callback: CallbackQuery, state: FSMContext):
    book_id = callback.data.split(":")[1]
    await state.update_data(book_id=book_id)
    await state.set_state(OrderState.waiting_full_name)

    book = BOOKS[book_id]
    await callback.message.answer(
        f"📦 Siz `{book['name']}` kitobini tanladingiz.\n\n"
        "Iltimos, ism-familiyangizni yozing:",
        parse_mode="Markdown",
    )
    await callback.answer()


# =========================
# FSM BUYURTMA BOSQICHLARI
# =========================
@dp.message(OrderState.waiting_full_name)
async def get_full_name_handler(message: Message, state: FSMContext):
    full_name = message.text.strip()
    if len(full_name) < 3:
        await message.answer("Iltimos, to'liq ism-familiyangizni kiriting.")
        return

    await state.update_data(full_name=full_name)
    await state.set_state(OrderState.waiting_phone)
    await message.answer("📞 Telefon raqamingizni kiriting:\nMasalan: +998901234567")


@dp.message(OrderState.waiting_phone)
async def get_phone_handler(message: Message, state: FSMContext):
    phone = message.text.strip()
    if len(phone) < 9:
        await message.answer("Telefon raqam noto'g'ri ko'rinmoqda. Qayta kiriting.")
        return

    await state.update_data(phone=phone)
    await state.set_state(OrderState.waiting_address)
    await message.answer("🏠 Yetkazib berish manzilini yozing:")


@dp.message(OrderState.waiting_address)
async def get_address_handler(message: Message, state: FSMContext):
    address = message.text.strip()
    if len(address) < 5:
        await message.answer("Manzilni to'liqroq yozing.")
        return

    await state.update_data(address=address)
    await state.set_state(OrderState.waiting_payment)
    await message.answer(
        "💳 To'lov usulini tanlang:",
        reply_markup=payment_menu,
    )


@dp.message(OrderState.waiting_payment)
async def get_payment_handler(message: Message, state: FSMContext):
    payment_method = message.text.strip()

    allowed = {"💳 Click": "Click", "💳 Payme": "Payme", "💵 Naqd": "Naqd"}
    if payment_method not in allowed:
        await message.answer("Iltimos, tugmalardan birini tanlang.")
        return

    data = await state.get_data()
    book_id = data["book_id"]
    full_name = data["full_name"]
    phone = data["phone"]
    address = data["address"]

    order_id = await save_order_to_db(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=full_name,
        phone=phone,
        address=address,
        payment_method=allowed[payment_method],
        book_id=book_id,
    )

    book = BOOKS[book_id]

    admin_text = (
        f"🆕 Yangi buyurtma #{order_id}\n\n"
        f"👤 User ID: {message.from_user.id}\n"
        f"🔖 Username: @{message.from_user.username if message.from_user.username else 'yo‘q'}\n"
        f"🙍 Ism: {full_name}\n"
        f"📞 Telefon: {phone}\n"
        f"🏠 Manzil: {address}\n"
        f"💳 To'lov: {allowed[payment_method]}\n"
        f"📖 Kitob: {book['name']}\n"
        f"💰 Narx: {book['price']:,} so'm"
    ).replace(",", " ")

    await bot.send_message(
        ADMIN_ID,
        admin_text,
        reply_markup=admin_order_keyboard(order_id, message.from_user.id),
    )

    user_text = (
        f"✅ Buyurtmangiz qabul qilindi!\n\n"
        f"🧾 Buyurtma raqami: #{order_id}\n"
        f"📖 Kitob: {book['name']}\n"
        f"💰 Narx: {book['price']:,} so'm\n"
        f"💳 To'lov: {allowed[payment_method]}"
    ).replace(",", " ")

    if allowed[payment_method] == "Click":
        user_text += f"\n\nTo'lov havolasi:\n{CLICK_URL}"
    elif allowed[payment_method] == "Payme":
        user_text += f"\n\nTo'lov havolasi:\n{PAYME_URL}"
    else:
        user_text += "\n\nNaqd to'lov yetkazib berishda amalga oshiriladi."

    await message.answer(user_text, reply_markup=main_menu)
    await state.clear()


# =========================
# ADMIN STATUS BOSHQARUV
# =========================
@dp.callback_query(F.data.startswith("admin_confirm:"))
async def admin_confirm_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Siz admin emassiz.", show_alert=True)
        return

    _, order_id, user_id = callback.data.split(":")
    await update_order_status(int(order_id), "tasdiqlandi")

    await bot.send_message(
        int(user_id),
        f"✅ Buyurtmangiz #{order_id} tasdiqlandi.",
    )
    await callback.answer("Tasdiqlandi")
    await callback.message.answer(f"Buyurtma #{order_id} holati: tasdiqlandi")


@dp.callback_query(F.data.startswith("admin_sent:"))
async def admin_sent_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Siz admin emassiz.", show_alert=True)
        return

    _, order_id, user_id = callback.data.split(":")
    await update_order_status(int(order_id), "yuborildi")

    await bot.send_message(
        int(user_id),
        f"🚚 Buyurtmangiz #{order_id} yuborildi.",
    )
    await callback.answer("Yuborildi")
    await callback.message.answer(f"Buyurtma #{order_id} holati: yuborildi")


@dp.callback_query(F.data.startswith("admin_cancel:"))
async def admin_cancel_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Siz admin emassiz.", show_alert=True)
        return

    _, order_id, user_id = callback.data.split(":")
    await update_order_status(int(order_id), "bekor qilindi")

    await bot.send_message(
        int(user_id),
        f"❌ Buyurtmangiz #{order_id} bekor qilindi.",
    )
    await callback.answer("Bekor qilindi")
    await callback.message.answer(f"Buyurtma #{order_id} holati: bekor qilindi")


# =========================
# BOSHQA XABARLAR
# =========================
@dp.message()
async def fallback_handler(message: Message):
    await message.answer(
        "Kerakli bo'limni tanlang 👇",
        reply_markup=main_menu,
    )


# =========================
# ISHGA TUSHIRISH
# =========================
async def main():
    await init_db()
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())