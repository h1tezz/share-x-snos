from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

ADMIN_ID = 7832587042
TOKEN = '8256862820:AAHkQn_8fAP-XV01-x9xneC5XZSZhubOi6c'

# === Кнопки ===
continue_btn = InlineKeyboardButton(text="✈️ Продолжить", callback_data="continue")
sub_btn = InlineKeyboardButton(text="💎 Подписка", callback_data="subscription")
my_btn = InlineKeyboardButton(text="👤 Профиль", callback_data="my")
info_btn = InlineKeyboardButton(text="🚀 Информация", callback_data="info")
back_btn = InlineKeyboardButton(text="🔙 Назад", callback_data="back")
demon_btn = InlineKeyboardButton(text="❤️‍🔥 Начать", callback_data="start")
get_sub_btn = InlineKeyboardButton(text="🎁 Получить подписку", callback_data="get_subscription")
session_btn = InlineKeyboardButton(text="📱 Session", callback_data="session")
main_btn = InlineKeyboardButton(text="📨 Mail", callback_data="mail")
premium_btn = InlineKeyboardButton(text="👑 Premium", callback_data="premium")
codes = InlineKeyboardButton(text="📪 Telegram Notification", callback_data="sms")
remove_sub_btn = InlineKeyboardButton(text="🗑️ Забрать подписку", callback_data="remove_subscription")

s_btn = InlineKeyboardButton(text="👥 Поддержка", url="https://t.me/unsedb")
ch_btn = InlineKeyboardButton(text="📚 Правила", url="https://t.me/unsedb")
buy_btn = InlineKeyboardButton(text="⚡ Приобрести подписку ", url="https://t.me/unsedb")

# === Админ кнопки ===
broadcast_btn = InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")
ban_btn = InlineKeyboardButton(text="🚫 Забанить", callback_data="admin_ban")
unban_btn = InlineKeyboardButton(text="✅ Разбанить", callback_data="admin_unban")
check_ban_btn = InlineKeyboardButton(text="🔍 Проверить бан", callback_data="admin_check_ban")
maintenance_btn = InlineKeyboardButton(text="🔧 Техобслуживание", callback_data="admin_maintenance")
restart_btn = InlineKeyboardButton(text="🔄 Перезагрузка", callback_data="admin_restart")
add_admin_btn = InlineKeyboardButton(text="👤 Добавить админа", callback_data="admin_add_admin")
help_btn = InlineKeyboardButton(text="❓ Помощь", callback_data="admin_help")
admin_back_btn = InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")
whitelist_btn = InlineKeyboardButton(text="📝 Белый список", callback_data="admin_whitelist")
promocodes_btn = InlineKeyboardButton(text="🎟️ Промокоды", callback_data="admin_promocodes")

# === Новые админ кнопки для категорий ===
bans_category_btn = InlineKeyboardButton(text="🚫 Баны", callback_data="admin_bans_category")
subscription_category_btn = InlineKeyboardButton(text="💎 Подписка", callback_data="admin_subscription_category")
admins_category_btn = InlineKeyboardButton(text="👥 Админы", callback_data="admin_admins_category")
other_category_btn = InlineKeyboardButton(text="📋 Прочее", callback_data="admin_other_category")

# === Кнопки категории Подписка ===
give_sub_btn = InlineKeyboardButton(text="🎁 Выдать подписку", callback_data="admin_give_sub")
revoke_sub_btn = InlineKeyboardButton(text="🗑️ Забрать подписку", callback_data="admin_revoke_sub")
check_sub_btn = InlineKeyboardButton(text="🔍 Проверить подписку", callback_data="admin_check_sub")
give_premium_btn = InlineKeyboardButton(text="👑 Выдать премиум", callback_data="admin_give_premium")
revoke_premium_btn = InlineKeyboardButton(text="❌ Забрать премиум", callback_data="admin_revoke_premium")

# === Кнопки категории Админы ===
remove_admin_btn = InlineKeyboardButton(text="❌ Удалить админа", callback_data="admin_remove_admin")
check_admin_btn = InlineKeyboardButton(text="🔍 Проверить админа", callback_data="admin_check_admin")

# === Кнопки категории Прочее ===
auto_moderation_btn = InlineKeyboardButton(text="🤖 Авто-модерация", callback_data="admin_auto_moderation")


# === Кнопка вернуться в админ меню ===
admin_menu_back_btn = InlineKeyboardButton(text="🔙 Админ меню", callback_data="admin_back")

white_set = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить", callback_data="whitelist_add")],
            [InlineKeyboardButton(text="➖ Удалить", callback_data="whitelist_remove")],
            [InlineKeyboardButton(text="🔍 Проверить", callback_data="whitelist_check")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
        ])
# === Выбор награды в вайт листе ===
reward_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Вайт лист", callback_data="promocode_reward_whitelist")],
        [InlineKeyboardButton(text="💎 Подписка", callback_data="promocode_reward_subscription")],
        [InlineKeyboardButton(text="👑 Премиум", callback_data="promocode_reward_premium")],
        [InlineKeyboardButton(text="👑💎 Премиум + Подписка", callback_data="promocode_reward_premium_sub")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_promocodes")]
    ])

# === Меню промокодов ===
promocodes_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать", callback_data="promocode_create")],
        [InlineKeyboardButton(text="➖ Удалить", callback_data="promocode_delete")],
        [InlineKeyboardButton(text="🔍 Проверить", callback_data="promocode_check")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
    ])

# === Клавиатуры ===
start_keyboard = InlineKeyboardMarkup(inline_keyboard=[[continue_btn]])
main_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [demon_btn],
    [sub_btn, my_btn],
    [info_btn],
])
back_keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_btn]])
info_keyboard = InlineKeyboardMarkup(inline_keyboard=[[s_btn],
                                                      [ch_btn],
                                                      [back_btn]])
subscription_keyboard_with_sub = InlineKeyboardMarkup(inline_keyboard=[[back_btn]])
subscription_keyboard_without_sub = InlineKeyboardMarkup(inline_keyboard=[[back_btn]])
snos_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [session_btn, main_btn,premium_btn],
    [codes],
    [back_btn]
])

# === Админ клавиатуры ===
admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [bans_category_btn, subscription_category_btn],
    [admins_category_btn, promocodes_btn],
    [whitelist_btn, other_category_btn],
    [back_btn]
])

# === Клавиатуры категорий админ меню ===
admin_bans_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [ban_btn, unban_btn],
    [check_ban_btn],
    [admin_menu_back_btn]
])

admin_subscription_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [give_sub_btn, revoke_sub_btn],
    [check_sub_btn],
    [give_premium_btn, revoke_premium_btn],
    [admin_menu_back_btn]
])

admin_admins_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [add_admin_btn, remove_admin_btn],
    [check_admin_btn],
    [admin_menu_back_btn]
])

admin_other_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [broadcast_btn],
    [maintenance_btn, auto_moderation_btn],
    [restart_btn, help_btn],
    [admin_menu_back_btn]
])

sub_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [buy_btn],
    [back_btn]
])



# === БОМБЕР КОНФИГ ===

api_id = 25394384
api_hash = "218ec784d11055d1a0bce26c68cfb1d9"

DEVICE_CONFIGS = [
    # Android
    {"device_model": "Samsung Galaxy S23 Ultra", "system_version": "Android 14", "app_version": "10.3.2", "system_lang_code": "en", "platform": "android"},
    {"device_model": "Google Pixel 7 Pro", "system_version": "Android 13", "app_version": "10.2.1", "system_lang_code": "en", "platform": "android"},
    {"device_model": "Xiaomi 13 Pro", "system_version": "Android 13", "app_version": "10.1.5", "system_lang_code": "en", "platform": "android"},
    {"device_model": "OnePlus 11", "system_version": "Android 13", "app_version": "10.2.0", "system_lang_code": "en", "platform": "android"},
    {"device_model": "Huawei P60 Pro", "system_version": "Android 12", "app_version": "10.1.8", "system_lang_code": "en", "platform": "android"},
    {"device_model": "Sony Xperia 1 V", "system_version": "Android 13", "app_version": "10.2.3", "system_lang_code": "en", "platform": "android"},
    {"device_model": "OPPO Find X6 Pro", "system_version": "Android 13", "app_version": "10.1.9", "system_lang_code": "en", "platform": "android"},
    {"device_model": "Realme GT 3", "system_version": "Android 13", "app_version": "10.1.7", "system_lang_code": "en", "platform": "android"},
    {"device_model": "Vivo X90 Pro", "system_version": "Android 13", "app_version": "10.2.2", "system_lang_code": "en", "platform": "android"},
    {"device_model": "Nothing Phone 2", "system_version": "Android 13", "app_version": "10.1.6", "system_lang_code": "en", "platform": "android"},
    
    # iOS
    {"device_model": "iPhone 15 Pro Max", "system_version": "iOS 17.2", "app_version": "10.3.0", "system_lang_code": "en", "platform": "ios"},
    {"device_model": "iPhone 14 Pro", "system_version": "iOS 16.6", "app_version": "10.2.8", "system_lang_code": "en", "platform": "ios"},
    {"device_model": "iPhone 13 mini", "system_version": "iOS 16.5", "app_version": "10.2.5", "system_lang_code": "en", "platform": "ios"},
    {"device_model": "iPhone 12", "system_version": "iOS 16.4", "app_version": "10.2.3", "system_lang_code": "en", "platform": "ios"},
    {"device_model": "iPhone SE 3", "system_version": "iOS 16.3", "app_version": "10.2.1", "system_lang_code": "en", "platform": "ios"},
    {"device_model": "iPad Pro 12.9", "system_version": "iPadOS 17.0", "app_version": "10.3.1", "system_lang_code": "en", "platform": "ios"},
    {"device_model": "iPad Air 5", "system_version": "iPadOS 16.7", "app_version": "10.2.9", "system_lang_code": "en", "platform": "ios"},
    {"device_model": "iPad mini 6", "system_version": "iPadOS 16.6", "app_version": "10.2.7", "system_lang_code": "en", "platform": "ios"},
    
    # Desktop
    {"device_model": "Desktop Win", "system_version": "Windows 11", "app_version": "4.9.4", "system_lang_code": "en", "platform": "windows"},
    {"device_model": "Desktop Win", "system_version": "Windows 10", "app_version": "4.9.2", "system_lang_code": "en", "platform": "windows"},
    {"device_model": "Desktop Mac", "system_version": "macOS 14.0", "app_version": "4.9.3", "system_lang_code": "en", "platform": "macos"},
    {"device_model": "Desktop Linux", "system_version": "Ubuntu 22.04", "app_version": "4.9.1", "system_lang_code": "en", "platform": "linux"},
    
    # Web
    {"device_model": "Browser Chrome", "system_version": "Windows 11", "app_version": "2.0.0", "system_lang_code": "en", "platform": "web"},
    {"device_model": "Browser Firefox", "system_version": "Windows 10", "app_version": "2.0.1", "system_lang_code": "en", "platform": "web"},
    {"device_model": "Browser Safari", "system_version": "macOS 14.0", "app_version": "2.0.2", "system_lang_code": "en", "platform": "web"},
    {"device_model": "Browser Edge", "system_version": "Windows 11", "app_version": "2.0.3", "system_lang_code": "en", "platform": "web"},
]

# сайты для эмуляции
TELEGRAM_SITES = [
    "web.telegram.org",
    "webk.telegram.org",
    "webz.telegram.org",
]

url = "https://my.telegram.org/auth/send_password"

    
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'en-US,en;q=0.9',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'Origin': 'https://my.telegram.org',
    'Referer': 'https://my.telegram.org/auth',
    'X-Requested-With': 'XMLHttpRequest'
    }