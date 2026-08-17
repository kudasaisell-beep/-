from aiogram import Router, F
from tg_utils import safe_answer, safe_edit
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import add_review, get_reviews, get_reviews_stats, get_user_purchases, has_user_reviewed, add_log
from keyboards import reviews_kb, review_rating_kb, review_cancel_kb, back_to_main_kb

router = Router()


class ReviewState(StatesGroup):
    waiting_text = State()


def _mask_name(review: dict) -> str:
    """Имя автора отзыва (username или имя), слегка маскируем."""
    name = review.get("username") or review.get("full_name") or "Покупатель"
    if review.get("username"):
        name = "@" + review["username"].lstrip("@")
    if len(name) > 4:
        return name[:4] + "***"
    return name


def _build_reviews_text() -> str:
    stats = get_reviews_stats()
    reviews = get_reviews(limit=5)

    if stats["count"] == 0:
        return (
            "⭐ <b>Отзывы</b>\n\n"
            "Пока никто не оставил отзыв — станьте первым!\n"
            "Нажмите «✍️ Написать отзыв» после покупки."
        )

    text = (
        f"⭐ <b>Отзывы покупателей</b>\n\n"
        f"📊 Средняя оценка: <b>{stats['avg']}</b> / 5 "
        f"(всего отзывов: {stats['count']})\n"
        f"━━━━━━━━━━━━━━━\n\n"
    )
    for r in reviews:
        stars = "⭐" * int(r["rating"] or 0)
        author = _mask_name(r)
        date = (r.get("created_at") or "")[:10]
        body = (r.get("text") or "").strip()
        text += f"{stars} <b>{author}</b> · <i>{date}</i>\n{body}\n\n"
    text += "✍️ Оставьте свой отзыв — это помогает другим покупателям!"
    return text


@router.callback_query(F.data == "reviews")
async def reviews_handler(callback: CallbackQuery):
    await safe_edit(callback, _build_reviews_text(), reply_markup=reviews_kb)
    await safe_answer(callback, )


@router.callback_query(F.data == "leave_review")
async def leave_review(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id

    # Отзыв могут оставить только покупатели
    if not get_user_purchases(user_id):
        await safe_answer(callback, 
            "❌ Отзыв можно оставить только после первой покупки.",
            show_alert=True
        )
        return

    if has_user_reviewed(user_id):
        await safe_answer(callback, 
            "⭐ Вы уже оставляли отзыв. Спасибо!",
            show_alert=True
        )
        return

    await state.clear()
    await safe_edit(callback, 
        "⭐ <b>Оставить отзыв</b>\n\n"
        "Оцените работу магазина от 1 до 5:",
        reply_markup=review_rating_kb
    )
    await safe_answer(callback, )


@router.callback_query(F.data.startswith("review_rate:"))
async def review_rate(callback: CallbackQuery, state: FSMContext):
    rating = int(callback.data.split(":")[1])
    await state.set_state(ReviewState.waiting_text)
    await state.update_data(rating=rating)

    stars = "⭐" * rating
    await safe_edit(callback, 
        f"⭐ <b>Ваша оценка: {stars}</b>\n\n"
        "Теперь напишите пару слов о покупке:\n"
        "<i>(например: скорость выдачи, качество аккаунта, поддержка)</i>",
        reply_markup=review_cancel_kb
    )
    await safe_answer(callback, )


@router.message(ReviewState.waiting_text, F.text)
async def review_text(message: Message, state: FSMContext):
    data = await state.get_data()
    rating = int(data.get("rating", 5))
    text = message.text.strip()

    if len(text) < 3:
        await message.answer(
            "❌ Отзыв слишком короткий. Напишите хотя бы пару слов.",
            reply_markup=review_cancel_kb
        )
        return
    if len(text) > 500:
        text = text[:500]

    add_review(message.from_user.id, rating, text)
    add_log(message.from_user.id, "review", f"rating={rating}")
    await state.clear()

    await message.answer(
        "✅ <b>Спасибо за отзыв!</b>\n\n"
        "Ваше мнение очень важно для нас 💙",
        reply_markup=back_to_main_kb
    )


@router.callback_query(F.data == "review_cancel")
async def review_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit(callback, 
        "❌ Отзыв отменён.",
        reply_markup=back_to_main_kb
    )
    await safe_answer(callback, )
