from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.formatting import *
import asyncio
import os
import time
from collections import defaultdict
from config import *
import database

bot = Bot(token=TOKEN)
dp = Dispatcher()

async def check_bot_in_bio(bot, user_id: int) -> bool: 
    try:
        bot_info = await bot.get_me()
        bot_username = bot_info.username.lower()

        user_chat = await bot.get_chat(user_id)
        bio = (user_chat.bio or "").lower()

        # Все возможные варианты ссылки 
        patterns = [
            f"@{bot_username}",
            f"https://t.me/{bot_username}",
            f"http://t.me/{bot_username}",
            f"t.me/{bot_username}",
            f"http://{bot_username}.t.me",
            f"{bot_username}.t.me"
        ]

        return any(p in bio for p in patterns)
    except Exception:
        return False


async def _send_log(text: str, chat_id: int, thread_id: Optional[int]):
    try:
        kwargs = {
            "chat_id": chat_id,
            "text": f"<b>{text}</b>",
            "disable_web_page_preview": True,
            "parse_mode": "HTML"
        }

        if thread_id:
            kwargs["message_thread_id"] = int(thread_id)

        await bot.send_message(**kwargs)
    except Exception as e:
        print(f"[tg_log error] {e}")

def tg_log(text: str, thread_id: Optional[int] = None, chat_id: Optional[int] = None):
    LOG_CHAT_ID = -1003464522727
    LOG_THREAD_ID_DEFAULT = 2

    target_chat = chat_id if chat_id is not None else LOG_CHAT_ID
    target_thread = thread_id if thread_id is not None else (LOG_THREAD_ID_DEFAULT or None)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(_send_log(text, target_chat, target_thread))
        else:
            loop.run_until_complete(_send_log(text, target_chat, target_thread))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_send_log(text, target_chat, target_thread))

def frlog(text: str, thread_id: Optional[int] = None, chat_id: Optional[int] = None):
    LOG_CHAT_ID = -1003464522727
    LOG_THREAD_ID_DEFAULT = 107

    target_chat = chat_id if chat_id is not None else LOG_CHAT_ID
    target_thread = thread_id if thread_id is not None else (LOG_THREAD_ID_DEFAULT or None)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(_send_log(text, target_chat, target_thread))
        else:
            loop.run_until_complete(_send_log(text, target_chat, target_thread))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_send_log(text, target_chat, target_thread))        

# === Кастомное логирование ===
def write_log(text: str):
    time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("log.txt", "a", encoding="utf-8") as f:
        f.write(f"[{time}] {text}\n")

# Обновляем функцию логирования в database модуле
database.write_log = write_log

# === Система авто-модерации ===
# Словарь для отслеживания действий пользователей: {user_id: {"callback": [timestamps], "command": [timestamps]}}
user_actions = defaultdict(lambda: {"callback": [], "command": []})

# Настройки авто-модерации
AUTO_MODERATION_ENABLED = False
AUTO_MODERATION_MAX_ACTIONS = 10  # Максимальное количество действий
AUTO_MODERATION_TIME_WINDOW = 30  # Окно времени в секундах (60 секунд = 1 минута)

def load_auto_moderation_status():
    """Загружает статус авто-модерации из базы данных"""
    global AUTO_MODERATION_ENABLED
    try:
        status_str = database.get_setting("auto_moderation_enabled", "False")
        AUTO_MODERATION_ENABLED = status_str.lower() == "true"
        return AUTO_MODERATION_ENABLED
    except Exception as e:
        write_log(f"Ошибка при загрузке статуса авто-модерации: {e}")
        AUTO_MODERATION_ENABLED = False
        return False

def save_auto_moderation_status(enabled: bool):
    """Сохраняет статус авто-модерации в базу данных"""
    global AUTO_MODERATION_ENABLED
    try:
        AUTO_MODERATION_ENABLED = enabled
        database.set_setting("auto_moderation_enabled", str(enabled))
        return True
    except Exception as e:
        write_log(f"Ошибка при сохранении статуса авто-модерации: {e}")
        return False

def is_auto_moderation_enabled() -> bool:
    """Проверяет, включена ли авто-модерация"""
    return AUTO_MODERATION_ENABLED

def record_user_action(user_id: int, action_type: str = "callback"):
    """Записывает действие пользователя с текущей временной меткой.
    action_type: "callback" для нажатий кнопок, "command" для команд"""
    current_time = time.time()
    if action_type not in user_actions[user_id]:
        user_actions[user_id][action_type] = []
    
    user_actions[user_id][action_type].append(current_time)
    
    # Очищаем старые действия (старше окна времени)
    window_start = current_time - AUTO_MODERATION_TIME_WINDOW
    user_actions[user_id][action_type] = [t for t in user_actions[user_id][action_type] if t > window_start]

def check_user_action_rate(user_id: int, action_type: str = "callback") -> tuple[bool, int]:
    """Проверяет частоту действий пользователя определенного типа.
    Возвращает (превышен_лимит, количество_действий)"""
    if not AUTO_MODERATION_ENABLED:
        return False, 0
    
    current_time = time.time()
    window_start = current_time - AUTO_MODERATION_TIME_WINDOW
    
    if action_type not in user_actions[user_id]:
        user_actions[user_id][action_type] = []
    
    # Очищаем старые действия
    user_actions[user_id][action_type] = [t for t in user_actions[user_id][action_type] if t > window_start]
    
    action_count = len(user_actions[user_id][action_type])
    exceeded = action_count >= AUTO_MODERATION_MAX_ACTIONS
    
    return exceeded, action_count

def clear_user_actions(user_id: int):
    """Очищает историю действий пользователя"""
    if user_id in user_actions:
        del user_actions[user_id]

# локальный кэш для отметок отправленных уведомлений
ban_notify_cache = {}

async def check_and_auto_ban(user_id: int, bot=None, action_type: str = "callback") -> bool:
    """Проверяет частоту действий и автоматически банит при превышении лимита.
    Уведомление об авто-бане отправляется строго один раз."""

    # ВНУТРЕННИЕ ФУНКЦИИ (по запросу всё в одной функции)
    def was_ban_notified(uid: int) -> bool:
        return ban_notify_cache.get(uid, False)

    def mark_ban_notified(uid: int):
        ban_notify_cache[uid] = True

    # Авто-модерация выключена
    if not AUTO_MODERATION_ENABLED:
        return False

    # Админов не трогаем
    if is_admin(user_id):
        return False

    # Уже забанён → если автозабанен, просто игнорируем
    if is_banned(user_id):
        reason = get_ban_reason(user_id)
        if reason and reason.startswith("Автоматический бан"):
            return True
        return False

    # Проверяем частоту действий
    exceeded, action_count = check_user_action_rate(user_id, action_type)

    if exceeded:
        # Формируем причину
        if action_type == "callback":
            reason = (
                f"Автоматический бан: Слишком много callback запросов "
                f"({action_count} нажатий за {AUTO_MODERATION_TIME_WINDOW} сек.)"
            )
        else:
            reason = (
                f"Автоматический бан: Слишком частые команды "
                f"({action_count} за {AUTO_MODERATION_TIME_WINDOW} сек.)"
            )

        # Ставим бан
        success = update_ban_status(user_id, True, reason)

        if success:
            write_log(
                f"Авто-бан: пользователь {user_id} забанен "
                f"({action_count} действий, тип {action_type})"
            )

            # Уведомление — ТОЛЬКО ОДИН РАЗ
            try:
                if bot and not was_ban_notified(user_id):
                    await bot.send_message(
                        user_id,
                        **BlockQuote(
                            Bold(
                                "👮 Вы превысили лимит запросов и были заблокированы навсегда")
                        ).as_kwargs(),
                        reply_markup=InlineKeyboardMarkup(
                            inline_keyboard=[
                                [
                                    InlineKeyboardButton(
                                        text="⚡️ Оспорить нарушение",
                                        url="https://t.me/unsedb"
                                    )
                                ]
                            ]
                        )
                    )
                    mark_ban_notified(user_id)

            except Exception as e:
                write_log(
                    f"Ошибка при уведомлении пользователя {user_id}: {e}"
                )

            # Чистим историю
            clear_user_actions(user_id)
            return True

    return False



# Импортируем функции из database модуля
load_admins = database.load_admins
is_admin = database.is_admin
add_admin = database.add_admin
remove_admin = database.remove_admin

# === Проверка наличия username бота в описании профиля ===
async def check_bot_username_in_bio(user_id: int, bot_instance) -> bool:
    """
    Проверяет, есть ли username бота в описании профиля пользователя.
    Возвращает True если username найден, False если нет.
    
    Примечание: Telegram Bot API не позволяет напрямую получить bio пользователя.
    Используется альтернативный метод - проверка через get_chat (может не работать для всех пользователей).
    """
    try:
        # Получаем информацию о боте
        bot_info = await bot_instance.get_me()
        bot_username = bot_info.username
        if not bot_username:
            # Если у бота нет username, пропускаем проверку
            write_log(f"У бота нет username, пропускаем проверку bio для {user_id}")
            return True
        
        bot_username_lower = bot_username.lower()
        bot_mention = f"@{bot_username_lower}"
        
        # Пытаемся получить информацию о пользователе через get_chat
        # Это может не работать для всех пользователей, но попробуем
        try:
            user_chat = await bot_instance.get_chat(user_id)
            
            # Проверяем bio если доступно (обычно недоступно через Bot API)
            if hasattr(user_chat, 'bio') and user_chat.bio:
                bio_lower = user_chat.bio.lower()
                if bot_username_lower in bio_lower or bot_mention in bio_lower:
                    write_log(f"Username бота найден в bio пользователя {user_id}")
                    return True
            
            # Проверяем описание (description) если доступно
            if hasattr(user_chat, 'description') and user_chat.description:
                desc_lower = user_chat.description.lower()
                if bot_username_lower in desc_lower or bot_mention in desc_lower:
                    write_log(f"Username бота найден в описании пользователя {user_id}")
                    return True
            
            # Проверяем username пользователя (на случай если там упоминается бот)
            if hasattr(user_chat, 'username') and user_chat.username:
                username_lower = user_chat.username.lower()
                # Это не то что нужно, но оставим для полноты
                pass
                
        except Exception as e:
            # Если не удалось получить информацию через get_chat
            # Это нормально для обычных пользователей, так как Bot API не позволяет получить bio
            write_log(f"Не удалось получить bio для {user_id} через Bot API (это нормально): {e}")
            # Возвращаем False, чтобы требовать от пользователя добавить бота в описание
            return False
        
        # Если bio недоступно или пустое, возвращаем False
        # Пользователь должен добавить username бота в описание профиля
        return False
        
    except Exception as e:
        write_log(f"Ошибка при проверке bot username в bio для {user_id}: {e}")
        return False

async def check_and_notify_bot_username(user_id: int, bot_instance, message=None, callback=None) -> bool:
    """
    Проверяет наличие username бота в описании профиля.
    Если нет - отправляет сообщение об ошибке.
    Возвращает True если проверка не прошла (нужно прервать выполнение), False если все ОК.
    """
    # Админы пропускают проверку
    if is_admin(user_id):
        return False
    
    # Проверяем наличие username бота в bio
    has_bot_username = await check_bot_username_in_bio(user_id, bot_instance)
    
    if not has_bot_username:
        error_text = (
            "❌ <b>Ошибка доступа!</b>\n\n"
            "Для использования бота необходимо добавить username бота в описание вашего профиля Telegram.\n\n"
            "📝 <b>Как это сделать:</b>\n"
            "1. Откройте настройки Telegram\n"
            "2. Перейдите в 'Редактировать профиль'\n"
            "3. Добавьте в описание (Bio) username бота\n"
            "4. Сохраните изменения\n\n"
            "После этого попробуйте снова."
        )
        
        if callback:
            try:
                await callback.answer(error_text, show_alert=True)
            except:
                try:
                    await callback.message.answer(error_text, parse_mode="html")
                except:
                    pass
        elif message:
            try:
                await message.answer(error_text, parse_mode="html")
            except:
                pass
        
        write_log(f"Пользователь {user_id} попытался использовать бота без username бота в bio")
        return True  # Прерываем выполнение
    
    return False  # Все ОК, продолжаем

# Импортируем функции работы с пользователями из database модуля
add_user = database.add_user
is_banned = database.is_banned
get_subscription_status = database.get_subscription_status
is_registered = database.is_registered
update_subscription_status = database.update_subscription_status

# Импортируем функции работы с банами из database модуля
get_ban_reason = database.get_ban_reason
is_ban_notified = database.is_ban_notified
mark_ban_notified = database.mark_ban_notified
unmark_ban_notified = database.unmark_ban_notified
update_ban_status = database.update_ban_status

async def check_ban_and_notify(user_id: int, bot=None, message=None, callback=None):
    """Проверяет бан пользователя и отправляет сообщение при первом обращении.
    Возвращает True если пользователь забанен, False если нет.
    Если пользователь забанен и сообщение еще не отправлялось, отправляет его."""
    if not is_banned(user_id):
        return False
    
    # Если сообщение еще не отправлялось, отправляем его
    if not is_ban_notified(user_id):
        reason = get_ban_reason(user_id)
        
        # Определяем тип бана (автоматический или ручной)
        is_auto_ban = reason.startswith("Автоматический бан:")
        
        if is_auto_ban:
            await message.answer(**BlockQuote(Bold("👮 Вы превысили лимит запросов и были заблокированы навсегда")).as_kwargs(),reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⚡️ Оспорить нарушение", url="https://t.me/unsedb")]]))

        else:
            await message.answer(**BlockQuote(Bold(f"🚫 Вы были заблокированы администратором.\n\nПричина: {reason}\n\n⚠️ Нарушение нельзя оспорить")).as_kwargs())

            mark_ban_notified(user_id)
            write_log(f"Отправлено сообщение о бане пользователю {user_id}, причина: {reason}")
    return True

# Импортируем функции работы с белым списком из database модуля
is_whitelisted = database.is_whitelisted
add_to_whitelist = database.add_to_whitelist
remove_from_whitelist = database.remove_from_whitelist



# === Тестовая команда ===
@dp.message(Command("test"))
async def test_command(message: Message):
    await message.answer("✅ Команды работают!")

# === Команда для проверки ID ===
@dp.message(Command("myid"))
async def my_id_command(message: Message):
    user_id = message.from_user.id
    await message.answer(f"Ваш ID: <code>{user_id}</code>", parse_mode="HTML")

# === Команда для очистки базы данных пользователей ===
@dp.message(Command("clean"))
async def clean_users_command(message: Message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("❌ Доступ запрещен")
        return
    
    write_log(f"Админ {user_id} запросил очистку базы данных пользователей")
    
    try:
        success, deleted_count = database.clean_users_database()
        if success:
            await message.answer(f"✅ База данных пользователей очищена\n\nУдалено пользователей: {deleted_count}")
        else:
            await message.answer("❌ Ошибка при очистке базы данных")
    except Exception as e:
        await message.answer(f"❌ Ошибка при очистке: {e}")
        write_log(f"Ошибка при очистке базы данных: {e}")

# === Продолжить ===
@dp.callback_query(F.data == "continue")
async def handle_continue(callback: CallbackQuery):
    user_id = callback.from_user.id

    if is_banned(user_id):
        await callback.message.answer("<b>🚫 Вы заблокированы.</b>", parse_mode="HTML")
        write_log(f"{user_id} попытался нажать кнопку, но он заблокирован.")
        await callback.answer()
        return

    # Добавляем пользователя в users.txt только после нажатия "Продолжить"
    is_new = add_user(user_id)
    write_log(f"Пользователь {user_id} нажал «Продолжить»")

    # Определяем приветствие в зависимости от времени
    hour = datetime.now().hour
    if 5 <= hour < 12:
        greet = "☀️ Доброе утро"
    elif 12 <= hour < 18:
        greet = "🌤️ Добрый день"
    elif 18 <= hour < 23:
        greet = "🌙 Добрый вечер"
    else:
        greet = "🌌 Доброй ночи"

    await callback.message.edit_text(
        f"<b>{greet}, {callback.from_user.full_name}!</b>\n\n"
        "<b>Выберите действие ниже:</b>",
        parse_mode="html",
        reply_markup=main_keyboard
    )
    await callback.answer()

# === Профиль ===
@dp.callback_query(F.data == "my")
async def handle_my(callback: CallbackQuery):
    user = callback.from_user
    if is_banned(user.id):
        await callback.message.answer("<b>🚫 Вы заблокированы.</b>", parse_mode="HTML")
        return

    write_log(f"{user.id} открыл раздел подписки")

    # Получаем статус подписки из users.txt
    subscription_status = "true" if get_subscription_status(user.id) else "false"

    await callback.message.edit_text(
        f"👤 <b>Профиль</b>\n\n"
        f"✦ Имя: {user.full_name}\n"
        f"✦ ID: <code>{user.id}</code>\n"
        f"✦ Подписка: <b>{subscription_status}</b>\n"
        f"✦ Статус: <b>активен</b>",
        parse_mode="html",
        reply_markup=back_keyboard
    )
    await callback.answer()

# === Подписка ===
@dp.callback_query(F.data == "subscription")
async def handle_subscription(callback: CallbackQuery):
    user_id = callback.from_user.id
    if is_banned(user_id):
        await callback.message.answer("🚫 Вы заблокированы.")
        return

    write_log(f"{user_id} открыл раздел подписки")

    # Проверяем текущий статус подписки
    has_subscription = get_subscription_status(user_id)
    subscription_text = "✅ Активна" if has_subscription else "❌ Неактивна"
    
    # Выбираем клавиатуру в зависимости от статуса подписки
    keyboard = subscription_keyboard_with_sub if has_subscription else subscription_keyboard_without_sub

    await callback.message.edit_text(
        f"💎 <b>Подписка</b>\n\n"
        f"<b>Статус:</b> {subscription_text}\n\n"
        f"<b>🎯 Бета-тест</b>\n"
        f"Сейчас идет бета-тест, поэтому все подписки <b>бесплатные</b>!\n\n"
        f"<i>Получите подписку прямо сейчас и получите доступ ко всем функциям бота.</i>",
        parse_mode="html",
        reply_markup=keyboard
    )
    await callback.answer()

# === Получить подписку ===
@dp.callback_query(F.data == "get_subscription")
async def handle_get_subscription(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if is_banned(user_id):
        await callback.message.answer("🚫 Вы заблокированы.")
        write_log(f"{user_id} попытался получить подписку, но он заблокирован.")
        await callback.answer()
        return

    write_log(f"{user_id} запросил получение подписки")
    
    # Проверяем, есть ли уже подписка
    if get_subscription_status(user_id):
        await callback.answer("✅ У вас уже есть активная подписка!", show_alert=True)
        return
    
    # Выдаем подписку навсегда
    success = database.give_subscription(user_id, days=-1)
    
    if success:
        await callback.answer("🎉 Подписка успешно активирована!", show_alert=True)
        write_log(f"Пользователю {user_id} выдана подписка")
        
        # Обновляем сообщение
        await callback.message.edit_text(
            f"💎 <b>Подписка</b>\n\n"
            f"<b>Статус:</b> ✅ Активна\n\n"
            f"<b>🎯 Бета-тест</b>\n"
            f"Сейчас идет бета-тест, поэтому все подписки <b>бесплатные</b>!\n\n"
            f"<i>🎉 Поздравляем! Ваша подписка активирована.</i>",
            parse_mode="html",
            reply_markup=subscription_keyboard_with_sub
        )
    else:
        await callback.answer("❌ Ошибка при активации подписки", show_alert=True)
        write_log(f"Ошибка при выдаче подписки пользователю {user_id}")

# === Забрать подписку ===
@dp.callback_query(F.data == "remove_subscription")
async def handle_remove_subscription(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if is_banned(user_id):
        await callback.message.answer("🚫 Вы заблокированы.")
        write_log(f"{user_id} попытался забрать подписку, но он заблокирован.")
        await callback.answer()
        return

    write_log(f"{user_id} запросил отзыв подписки")
    
    # Проверяем, есть ли подписка
    if not get_subscription_status(user_id):
        await callback.answer("❌ У вас нет активной подписки!", show_alert=True)
        return
    
    # Забираем подписку
    success = database.revoke_subscription(user_id)
    
    if success:
        await callback.answer("🗑️ Подписка успешно отозвана!", show_alert=True)
        write_log(f"У пользователя {user_id} отозвана подписка")
        
        # Обновляем сообщение
        await callback.message.edit_text(
            f"💎 <b>Подписка</b>\n\n"
            f"<b>Статус:</b> ❌ Неактивна\n\n"
            f"<b>🎯 Бета-тест</b>\n"
            f"Сейчас идет бета-тест, поэтому все подписки <b>бесплатные</b>!\n\n"
            f"<i>Подписка отозвана. Вы можете получить её снова в любое время.</i>",
            parse_mode="html",
            reply_markup=subscription_keyboard_without_sub
        )
    else:
        await callback.answer("❌ Ошибка при отзыве подписки", show_alert=True)
        write_log(f"Ошибка при отзыве подписки у пользователя {user_id}")

# === Информация ===
@dp.callback_query(F.data == "info")
async def handle_info(callback: CallbackQuery):
    user_id = callback.from_user.id
    if is_banned(user_id):
        await callback.message.answer("🚫 Вы заблокированы.")
        return

    write_log(f"{user_id} открыл раздел информации")

    await callback.message.edit_text(
        "<b>ℹ️ Информация:</b>\n\n",
        parse_mode="html",
        reply_markup=info_keyboard
    )
    await callback.answer()

# === Знакдемона zN0s ===
@dp.callback_query(F.data == "demon")
async def handle_demon(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if is_banned(user_id):
        await callback.message.answer("🚫 Вы заблокированы.")
        write_log(f"{user_id} попытался нажать кнопку, но он заблокирован.")
        await callback.answer()
        return

    write_log(f"{user_id} нажал кнопку 'знакдемона zN0s'")
    
    # Проверяем подписку
    has_subscription = get_subscription_status(user_id)
    
    if has_subscription:
        await callback.answer("✅ Успешно!", show_alert=True)
    else:
        await callback.answer("❌ У вас нет подписки!", show_alert=True)

# === Назад ===
@dp.callback_query(F.data == "back")
async def handle_back(callback: CallbackQuery):
    user_id = callback.from_user.id
    write_log(f"{user_id} вернулся в главное меню")

    if is_banned(user_id):
        await callback.message.answer("🚫 Вы заблокированы.")
        write_log(f"{user_id} попытался нажать кнопку, но он заблокирован.")
        await callback.answer()
        return

    hour = datetime.now().hour
    if 5 <= hour < 12:
        greet = "Доброе утро"
    elif 12 <= hour < 18:
        greet = "Добрый день"
    elif 18 <= hour < 23:
        greet = "Добрый вечер"
    else:
        greet = "Доброй ночи"

    await callback.message.edit_text(
        f"<b>{greet}, {callback.from_user.full_name}!</b>\n\n"
        "<b>Выберите действие ниже:</b>",
        parse_mode="html",
        reply_markup=main_keyboard
    )
    await callback.answer()

# === Запуск ===
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    print("[!] Главное меню запущено")
    asyncio.run(main())