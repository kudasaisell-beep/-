from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from tg_utils import safe_edit, safe_answer
from database import get_reviews, get_reviews_stats, add_review, has_user_reviewed
from keyboards import reviews_kb, review_rating_kb, review_cancel_kb, back_to_main_kb

router = Router()

class ReviewState(StatesGroup):
    waiting_text = State()

user_review_rating = {}

@router.callback_query(F.data == "reviews")
async def reviews_handler(callback: CallbackQuery):
    stats = get_reviews_stats()
    text = (
        f"⭐ <b>Отзывы</b>

"
        f"Всего отзывов: <b>{stats['count']}</b>
"
        f"Средняя оценка: <b>{stats['avg']}</b> ⭐

"
        f"Последние отзывы:"
    )
    reviews = get_reviews(limit=5)
    for r in reviews:
        stars = "⭐" * r["rating"]
        text += f"
{stars} — {r.get('username', 'Аноним')}
<i>{r.get('text', '')[:100]}</i>
"
    await safe_edit(callback, text, reply_markup=reviews_kb)
    await safe_answer(callback)

@router.callback_query(F.data == "leave_review")
async def leave_review(callback: CallbackQuery):
    if has_user_reviewed(callback.from_user.id):
        await safe_answer(callback, "❌ Вы уже оставляли отзыв", show_alert=True)
        return
    text = "⭐ Выберите оценку:"
    await safe_edit(callback, text, reply_markup=review_rating_kb)
    await safe_answer(callback)

@router.callback_query(F.data.startswith("review_rate:"))
async def review_rate(callback: CallbackQuery, state: FSMContext):
    rating = int(callback.data.split(":")[1])
    user_review_rating[callback.from_user.id] = rating
    await state.set_state(ReviewState.waiting_text)
    text = "✏️ Напишите текст отзыва (или отправьте '-', чтобы пропустить):"
    await callback.message.answer(text, reply_markup=review_cancel_kb)
    await safe_answer(callback)

@router.message(ReviewState.waiting_text, F.text)
async def review_text(message: Message, state: FSMContext):
    text = message.text.strip()
    if text == "-":
        text = ""
    rating = user_review_rating.pop(message.from_user.id, 5)
    add_review(message.from_user.id, rating, text)
    await state.clear()
    await message.answer("✅ Спасибо за отзыв!", reply_markup=back_to_main_kb)
