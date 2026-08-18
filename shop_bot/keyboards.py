from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import get_min_price

# ========== ГЛАВНОЕ МЕНЮ ==========
main_menu_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🛒 Покупка", callback_data="buy_menu")],
    [InlineKeyboardButton(text="👤 Личный кабинет", callback_data="profile")],
    [InlineKeyboardButton(text="📞 Поддержка", callback_data="support_menu")],
    [InlineKeyboardButton(text="📜 Документы", callback_data="legal_menu")],
])

legal_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔐 Политика конфиденциальности", callback_data="privacy_policy")],
    [InlineKeyboardButton(text="📄 Пользовательское соглашение", callback_data="terms_of_service")],
    [InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")],
])

legal_back_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="◀️ Назад к документам", callback_data="legal_menu")],
    [InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")],
])

back_to_main_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")],
])

back_to_support_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="◀️ Назад в поддержку", callback_data="support_menu")],
])

back_to_buy_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="◀️ Назад", callback_data="buy_menu")],
])

back_to_countries_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="◀️ Назад к странам", callback_data="view_countries")],
])

back_to_balance_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="◀️ Назад", callback_data="top_up")],
])

back_to_profile_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="◀️ Назад в личный кабинет", callback_data="profile")],
])

# ========== ПОДДЕРЖКА ==========
support_menu_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="❓ FAQ", callback_data="faq")],
    [InlineKeyboardButton(text="📦 Как купить?", callback_data="faq_how_to_buy")],
    [InlineKeyboardButton(text="🎫 Создать тикет", callback_data="create_ticket")],
    [InlineKeyboardButton(text="📋 Мои тикеты", callback_data="my_tickets")],
    [InlineKeyboardButton(text="📜 Документы", callback_data="legal_menu")],
    [InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")],
])

faq_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📦 Как купить?", callback_data="faq_how_to_buy")],
    [InlineKeyboardButton(text="🛡 Гарантия", callback_data="faq_guarantee")],
    [InlineKeyboardButton(text="💰 Пополнение", callback_data="faq_payment")],
    [InlineKeyboardButton(text="⚠️ Аккаунт не работает", callback_data="faq_broken")],
    [InlineKeyboardButton(text="🎁 Реферальная программа", callback_data="faq_referral")],
    [InlineKeyboardButton(text="◀️ Назад в поддержку", callback_data="support_menu")],
])

ticket_type_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🛍 Вопрос по покупке", callback_data="ticket_type:purchase")],
    [InlineKeyboardButton(text="💰 Вопрос по пополнению", callback_data="ticket_type:payment")],
    [InlineKeyboardButton(text="🔧 Техническая проблема", callback_data="ticket_type:tech")],
    [InlineKeyboardButton(text="❓ Другой вопрос", callback_data="ticket_type:other")],
    [InlineKeyboardButton(text="◀️ Назад в поддержку", callback_data="support_menu")],
])

# ========== ПОКУПКА: КАТЕГОРИИ ==========
buy_main_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="💬 Мессенджеры", callback_data="buy_category:messengers")],
    [InlineKeyboardButton(text="🎮 Игры", callback_data="buy_category:games")],
    [InlineKeyboardButton(text="🎬 Сервисы", callback_data="buy_category:services")],
    [InlineKeyboardButton(text="⭐ Избранное", callback_data="my_favorites")],
    [InlineKeyboardButton(text="🛒 Корзина", callback_data="cart")],
    [InlineKeyboardButton(text="⭐ Отзывы", callback_data="reviews")],
    [InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")],
])

# Подкатегории
def subcategory_kb(category: str):
    messengers = [
        ("📱 Telegram", "telegram"),
        ("🎵 TikTok", "tiktok"),
        ("💬 Discord", "discord"),
        ("📸 Instagram", "instagram"),
        ("🐦 Twitter/X", "twitter"),
        ("🔵 VK", "vk"),
        ("🔴 Reddit", "reddit"),
    ]
    games = [
        ("🗡️ Genshin Impact", "genshin"),
        ("⛏️ Minecraft", "minecraft"),
        ("🎮 Steam", "steam"),
        ("🔫 Fortnite", "fortnite"),
        ("🎯 Valorant", "valorant"),
        ("🧱 Roblox", "roblox"),
        ("🎲 Epic Games", "epic"),
    ]
    services = [
        ("🎧 Spotify", "spotify"),
        ("🎬 Netflix", "netflix"),
        ("🤖 ChatGPT", "chatgpt"),
        ("🎨 Canva", "canva"),
        ("📺 YouTube Premium", "youtube"),
        ("☁️ iCloud", "icloud"),
    ]
    mapping = {"messengers": messengers, "games": games, "services": services}
    items = mapping.get(category, [])
    buttons = []
    for name, key in items:
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"buy_subcat:{key}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="buy_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ========== СТРАНЫ (универсальные) ==========
def countries_kb(page: int = 0, subcat_key: str = "telegram"):
    countries = [
        ("US", "США", "🇺🇸"), ("KZ", "Казахстан", "🇰🇿"), ("IN", "Индия", "🇮🇳"),
        ("ID", "Индонезия", "🇮🇩"), ("PH", "Филиппины", "🇵🇭"), ("VN", "Вьетнам", "🇻🇳"),
        ("BR", "Бразилия", "🇧🇷"), ("AR", "Аргентина", "🇦🇷"), ("TR", "Турция", "🇹🇷"),
        ("RO", "Румыния", "🇷🇴"), ("PL", "Польша", "🇵🇱"), ("DE", "Германия", "🇩🇪"),
        ("GB", "Великобритания", "🇬🇧"), ("IT", "Италия", "🇮🇹"), ("ES", "Испания", "🇪🇸"),
        ("FR", "Франция", "🇫🇷"), ("NL", "Нидерланды", "🇳🇱"), ("CZ", "Чехия", "🇨🇿"),
        ("BG", "Болгария", "🇧🇬"), ("MX", "Мексика", "🇲🇽"), ("CL", "Чили", "🇨🇱"),
        ("PE", "Перу", "🇵🇪"), ("CO", "Колумбия", "🇨🇴"), ("TH", "Таиланд", "🇹🇭"),
        ("MY", "Малайзия", "🇲🇾"), ("PK", "Пакистан", "🇵🇰"), ("BD", "Бангладеш", "🇧🇩"),
        ("EG", "Египет", "🇪🇬"), ("MA", "Марокко", "🇲🇦"), ("NG", "Нигерия", "🇳🇬"),
        ("KE", "Кения", "🇰🇪"), ("ZA", "ЮАР", "🇿🇦"), ("RU", "Россия", "🇷🇺"),
        ("UA", "Украина", "🇺🇦"), ("BY", "Беларусь", "🇧🇾"),
    ]
    per_page = 10
    total_pages = (len(countries) + per_page - 1) // per_page
    start = page * per_page
    end = min(start + per_page, len(countries))
    page_countries = countries[start:end]

    buttons = []
    for i in range(0, len(page_countries), 2):
        row = []
        for j in range(2):
            if i + j < len(page_countries):
                code, name, flag = page_countries[i + j]
                min_price = get_min_price(code)
                try:
                    price_text = f"От {int(min_price)}₽" if min_price else ""
                except (TypeError, ValueError):
                    price_text = ""
                btn_text = f"{flag} {name}"
                if price_text:
                    btn_text += f" · {price_text}"
                row.append(InlineKeyboardButton(text=btn_text, callback_data=f"select_country:{code}:{subcat_key}"))
        buttons.append(row)

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"country_page:{page - 1}:{subcat_key}"))
    nav_row.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"country_page:{page + 1}:{subcat_key}"))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton(text="🔍 Поиск страны", callback_data=f"search_country:{subcat_key}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"buy_subcat:{subcat_key}")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ========== ТИП АККАУНТА (для Telegram) ==========
def country_type_kb(country_code: str, subcat_key: str = "telegram"):
    if subcat_key == "telegram":
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🧑 Саморег (физ)", callback_data=f"select_type:{country_code}:samoreg:{subcat_key}"),
                InlineKeyboardButton(text="🤖 Авторег (вирт)", callback_data=f"select_type:{country_code}:autoreg:{subcat_key}"),
            ],
            [InlineKeyboardButton(text="⭐ В избранное", callback_data=f"add_fav:{country_code}:{subcat_key}")],
            [InlineKeyboardButton(text="◀️ Назад к странам", callback_data=f"view_countries:{subcat_key}")],
        ])
    # Для других категорий — сразу показываем товары
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Показать товары", callback_data=f"show_items:{country_code}:any:{subcat_key}")],
        [InlineKeyboardButton(text="◀️ Назад к странам", callback_data=f"view_countries:{subcat_key}")],
    ])

# ========== КАРТОЧКА ТОВАРА ==========
def account_card_kb(item_id: int, price: float, country_code: str, account_type: str, subcat_key: str = "telegram"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"☑️ Купить за {price:.0f}₽", callback_data=f"pre_buy:{item_id}:{subcat_key}")],
        [InlineKeyboardButton(text="🛒 В корзину", callback_data=f"add_to_cart:{item_id}:{subcat_key}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"select_country:{country_code}:{subcat_key}")],
    ])

# ========== КОРЗИНА LZT ==========
def lzt_cart_kb(country_code: str, account_type: str, qty: int, available: int, total_price: float, subcat_key: str = "telegram"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➖", callback_data=f"cart_minus:{country_code}:{account_type}:{subcat_key}"),
            InlineKeyboardButton(text=f"{qty} шт", callback_data="noop"),
            InlineKeyboardButton(text="➕", callback_data=f"cart_plus:{country_code}:{account_type}:{subcat_key}"),
        ],
        [InlineKeyboardButton(text=f"☑️ Купить за {int(total_price)}₽", callback_data=f"buy_lzt:{country_code}:{account_type}:{qty}:{subcat_key}")],
        [InlineKeyboardButton(text="🗑 Очистить", callback_data=f"cart_remove:{country_code}:{account_type}:{subcat_key}")],
        [InlineKeyboardButton(text="◀️ Назад к странам", callback_data=f"view_countries:{subcat_key}")],
    ])

# ========== СТРАХОВКА ==========
insurance_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🛡 Застраховать (+20%) — пожизненная гарантия", callback_data="buy_insured")],
    [InlineKeyboardButton(text="✅ Без страховки — 24ч гарантия", callback_data="buy_no_insurance")],
    [InlineKeyboardButton(text="◀️ Назад", callback_data="buy_menu")],
])

# ========== ПРОФИЛЬ ==========
profile_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="💰 Пополнить", callback_data="top_up"),
        InlineKeyboardButton(text="🛍 Покупки", callback_data="my_purchases"),
    ],
    [
        InlineKeyboardButton(text="🎁 Рефералка", callback_data="referral"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="my_stats"),
    ],
    [InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")],
])

# ========== БАЛАНС / ПОПОЛНЕНИЕ ==========
balance_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="💳 Перевод на карту", callback_data="pay_card")],
    [InlineKeyboardButton(text="📱 QR СБП", callback_data="pay_qr")],
    [InlineKeyboardButton(text="⭐ Telegram Stars", callback_data="pay_stars_menu")],
    [InlineKeyboardButton(text="◀️ Назад", callback_data="profile")],
])

stars_amount_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="⭐ 50 Stars → 65₽", callback_data="pay_stars:50")],
    [InlineKeyboardButton(text="⭐ 100 Stars → 130₽", callback_data="pay_stars:100")],
    [InlineKeyboardButton(text="⭐ 250 Stars → 325₽", callback_data="pay_stars:250")],
    [InlineKeyboardButton(text="⭐ 500 Stars → 650₽", callback_data="pay_stars:500")],
    [InlineKeyboardButton(text="💰 Своя сумма", callback_data="pay_stars_custom")],
    [InlineKeyboardButton(text="◀️ Назад", callback_data="top_up")],
])

# ========== АДМИН ==========
def admin_kb(user_id: int, admin_ids: list):
    if user_id not in admin_ids:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="➕ Демо-аккаунты", callback_data="add_demo_account")],
        [InlineKeyboardButton(text="🔄 Синхронизация LZT", callback_data="sync_lzt")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")],
    ])

def admin_price_type_kb(country_code: str, price: float):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧑 Саморег", callback_data=f"admin_set_price:{country_code}:samoreg:{price}")],
        [InlineKeyboardButton(text="🤖 Авторег", callback_data=f"admin_set_price:{country_code}:autoreg:{price}")],
        [InlineKeyboardButton(text="🌐 Оба типа", callback_data=f"admin_set_price:{country_code}:both:{price}")],
    ])

def admin_ticket_kb(ticket_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ответить", callback_data=f"admin_reply_ticket:{ticket_id}"),
            InlineKeyboardButton(text="❌ Закрыть", callback_data=f"admin_close_ticket:{ticket_id}"),
        ],
        [InlineKeyboardButton(text="⏳ В ожидании", callback_data=f"admin_wait_ticket:{ticket_id}")],
    ])

# Кнопки для подтверждения пополнения баланса
def admin_deposit_kb(deposit_id: int, user_id: int, amount: float):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"✅ Принять +{int(amount)}₽", callback_data=f"admin_deposit_accept:{deposit_id}:{user_id}:{amount}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_deposit_reject:{deposit_id}:{user_id}"),
        ],
    ])

# ========== ФИЛЬТРЫ ==========
filters_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔄 Тип: дешёвые / все", callback_data="filter_type")],
    [InlineKeyboardButton(text="📞 Страна: любая / выбор", callback_data="filter_country")],
    [InlineKeyboardButton(text="🛡 Спамблок: без / любой", callback_data="filter_spam")],
    [InlineKeyboardButton(text="⏱ Отлёжка: любой / новые / старые", callback_data="filter_age")],
    [InlineKeyboardButton(text="⭐ Премиум: неважно / есть / нет", callback_data="filter_premium")],
    [InlineKeyboardButton(text="💰 Цена: любая / диапазон", callback_data="filter_price")],
    [InlineKeyboardButton(text="🔄 Сортировка: цена ↑ / ↓", callback_data="filter_sort")],
    [InlineKeyboardButton(text="🧳 Показать результаты", callback_data="apply_filters")],
    [InlineKeyboardButton(text="📞 Оптом (от 5 шт)", callback_data="bulk_order")],
    [InlineKeyboardButton(text="🔄 Сбросить фильтры", callback_data="reset_filters")],
    [InlineKeyboardButton(text="◀️ Назад", callback_data="buy_menu")],
])

# ========== ПОСЛЕ ПОКУПКИ ==========
post_purchase_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="⭐ Оставить отзыв", callback_data="leave_review")],
    [InlineKeyboardButton(text="🛒 Купить ещё", callback_data="buy_menu")],
    [InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")],
])

# ========== ОТЗЫВЫ ==========
reviews_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✍️ Написать отзыв", callback_data="leave_review")],
    [InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")],
])

review_rating_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="⭐", callback_data="review_rate:1"),
        InlineKeyboardButton(text="⭐⭐", callback_data="review_rate:2"),
        InlineKeyboardButton(text="⭐⭐⭐", callback_data="review_rate:3"),
        InlineKeyboardButton(text="⭐⭐⭐⭐", callback_data="review_rate:4"),
        InlineKeyboardButton(text="⭐⭐⭐⭐⭐", callback_data="review_rate:5"),
    ],
    [InlineKeyboardButton(text="❌ Отмена", callback_data="review_cancel")],
])

review_cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="❌ Отмена", callback_data="review_cancel")],
])

# ========== КОРЗИНА ==========
def cart_kb(items):
    buttons = []
    for item in items:
        buttons.append([
            InlineKeyboardButton(
                text=f"❌ {item['country_name']} — {item['price']:.0f}₽",
                callback_data=f"remove_cart:{item['id']}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="💳 Оформить заказ", callback_data="checkout")])
    buttons.append([InlineKeyboardButton(text="🗑 Очистить всё", callback_data="clear_cart")])
    buttons.append([InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ========== ИЗБРАННОЕ ==========
def favorites_kb(favorites):
    buttons = []
    country_names = {
        "US": "США", "KZ": "Казахстан", "IN": "Индия", "ID": "Индонезия",
        "PH": "Филиппины", "VN": "Вьетнам", "BR": "Бразилия", "AR": "Аргентина",
        "TR": "Турция", "RO": "Румыния", "PL": "Польша", "DE": "Германия",
        "GB": "Великобритания", "IT": "Италия", "ES": "Испания", "FR": "Франция",
        "NL": "Нидерланды", "CZ": "Чехия", "BG": "Болгария", "MX": "Мексика",
        "CL": "Чили", "PE": "Перу", "CO": "Колумбия", "TH": "Таиланд",
        "MY": "Малайзия", "PK": "Пакистан", "BD": "Бангладеш", "EG": "Египет",
        "MA": "Марокко", "NG": "Нигерия", "KE": "Кения", "ZA": "ЮАР",
        "RU": "Россия", "UA": "Украина", "BY": "Беларусь",
    }
    flags = {
        "US": "🇺🇸", "KZ": "🇰🇿", "IN": "🇮🇳", "ID": "🇮🇩", "PH": "🇵🇭", "VN": "🇻🇳",
        "BR": "🇧🇷", "AR": "🇦🇷", "TR": "🇹🇷", "RO": "🇷🇴", "PL": "🇵🇱", "DE": "🇩🇪",
        "GB": "🇬🇧", "IT": "🇮🇹", "ES": "🇪🇸", "FR": "🇫🇷", "NL": "🇳🇱", "CZ": "🇨🇿",
        "BG": "🇧🇬", "MX": "🇲🇽", "CL": "🇨🇱", "PE": "🇵🇪", "CO": "🇨🇴", "TH": "🇹🇭",
        "MY": "🇲🇾", "PK": "🇵🇰", "BD": "🇧🇩", "EG": "🇪🇬", "MA": "🇲🇦", "NG": "🇳🇬",
        "KE": "🇰🇪", "ZA": "🇿🇦", "RU": "🇷🇺", "UA": "🇺🇦", "BY": "🇧🇾",
    }
    for fav in favorites:
        code = fav["country_code"]
        name = country_names.get(code, code)
        flag = flags.get(code, "🏳️")
        atype = fav["account_type"]
        label = "🧑 Саморег" if atype == "samoreg" else "🤖 Авторег"
        subcat = fav.get("subcat_key", "telegram")
        buttons.append([
            InlineKeyboardButton(
                text=f"{flag} {name} — {label}",
                callback_data=f"select_type:{code}:{atype}:{subcat}"
            ),
            InlineKeyboardButton(
                text="❌",
                callback_data=f"remove_fav:{code}:{atype}:{subcat}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="buy_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ========== ПРОГРЕСС ==========
def progress_kb(step: int, total: int = 4):
    emojis = ["⏳", "✅"]
    steps = ["🔍 Поиск", "🔒 Резерв", "🛡 Проверка", "📦 Выдача"]
    text = " ".join(
        f"{emojis[1 if i < step else 0]} {s}" for i, s in enumerate(steps)
    )
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data="noop")],
    ])

# ========== ДАННЫЕ АККАУНТА ==========
def copy_data_kb(account_data: str, purchase_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Копировать данные", callback_data=f"copy_data:{purchase_id}")],
        [InlineKeyboardButton(text="🔑 Запросить код", callback_data=f"request_code:{purchase_id}")],
        [InlineKeyboardButton(text="🔄 Сбросить сессии", callback_data=f"reset_sessions:{purchase_id}")],
        [InlineKeyboardButton(text="✅ Проверить валидность", callback_data=f"validate_acc:{purchase_id}")],
        [InlineKeyboardButton(text="🎫 Тикет по аккаунту", callback_data=f"ticket_from_purchase:{purchase_id}")],
        [InlineKeyboardButton(text="🛍 Мои покупки", callback_data="my_purchases")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")],
    ])
