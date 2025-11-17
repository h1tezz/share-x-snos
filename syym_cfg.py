from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.filters import Command

# === Кнопки ===
continue_btn = InlineKeyboardButton(text="✈️ Продолжить", callback_data="continue")
sub_btn = InlineKeyboardButton(text="💎 Подписка", callback_data="subscription")
my_btn = InlineKeyboardButton(text="👤 Профиль", callback_data="my")
info_btn = InlineKeyboardButton(text="🚀 Информация", callback_data="info")
back_btn = InlineKeyboardButton(text="🔙 Назад", callback_data="back")
demon_btn = InlineKeyboardButton(text="❤️‍🔥 Начать", callback_data="demon")
get_sub_btn = InlineKeyboardButton(text="🎁 Получить подписку", callback_data="get_subscription")
session_btn = InlineKeyboardButton(text="📱 Session method", callback_data="session")
main_btn = InlineKeyboardButton(text="📨 Mail method", callback_data="main")
premium_btn = InlineKeyboardButton(text="👑 Premium method", callback_data="premium")
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
clean_btn = InlineKeyboardButton(text="🧹 Очистить файл пользователей", callback_data="admin_clean")
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
    [session_btn, main_btn],
    [premium_btn],
    [back_btn]
])

# === Админ клавиатуры ===
admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [bans_category_btn],
    [subscription_category_btn],
    [admins_category_btn],
    [promocodes_btn],
    [whitelist_btn],
    [other_category_btn],
    [back_btn]
])

# === Клавиатуры категорий админ меню ===
admin_bans_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [ban_btn, unban_btn],
    [check_ban_btn],
    [admin_menu_back_btn]
])

admin_subscription_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [give_sub_btn],
    [revoke_sub_btn],
    [check_sub_btn],
    [give_premium_btn],
    [revoke_premium_btn],
    [admin_menu_back_btn]
])

admin_admins_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [add_admin_btn, remove_admin_btn],
    [check_admin_btn],
    [admin_menu_back_btn]
])

admin_other_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [broadcast_btn],
    [maintenance_btn],
    [auto_moderation_btn],
    [restart_btn],
    [clean_btn],
    [help_btn],
    [admin_menu_back_btn]
])

sub_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [buy_btn],
    [back_btn]
])
TOKEN = '8256862820:AAHkQn_8fAP-XV01-x9xneC5XZSZhubOi6c'