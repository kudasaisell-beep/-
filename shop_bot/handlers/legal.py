from aiogram import Router, F
from aiogram.types import CallbackQuery
from tg_utils import safe_edit, safe_answer
from keyboards import legal_kb, legal_back_kb

router = Router()

@router.callback_query(F.data == "legal_menu")
async def legal_menu(callback: CallbackQuery):
    text = "📜 <b>Документы</b>

Выберите документ:"
    await safe_edit(callback, text, reply_markup=legal_kb)
    await safe_answer(callback)

@router.callback_query(F.data == "privacy_policy")
async def privacy_policy(callback: CallbackQuery):
    text = (
        "🔐 <b>Политика конфиденциальности</b>

"
        "1. Мы не передаём данные третьим лицам.
"
        "2. Данные аккаунтов хранятся в зашифрованном виде.
"
        "3. Вы можете запросить удаление данных."
    )
    await safe_edit(callback, text, reply_markup=legal_back_kb)
    await safe_answer(callback)

@router.callback_query(F.data == "terms_of_service")
async def terms_of_service(callback: CallbackQuery):
    text = (
        "📄 <b>Пользовательское соглашение</b>

"
        "1. Аккаунты предоставляются 'как есть'.
"
        "2. Гарантия распространяется только на техническую работоспособность.
"
        "3. Возврат средств возможен только в течение гарантийного срока."
    )
    await safe_edit(callback, text, reply_markup=legal_back_kb)
    await safe_answer(callback)
