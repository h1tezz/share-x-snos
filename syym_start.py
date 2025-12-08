import asyncio
import sys
import os
import random
import string
from datetime import datetime
import os

# Добавляем текущую директорию в путь для импорта
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.utils.formatting import *
from config import *
from syym import *
from concurrent.futures import ThreadPoolExecutor
import database
try:
    import crypto_bot
    CRYPTO_BOT_AVAILABLE = True
except ImportError:
    CRYPTO_BOT_AVAILABLE = False

bot = Bot(token=TOKEN)
dp = Dispatcher()

# === Состояния для рассылки ===
broadcast_waiting = False  # Флаг ожидания сообщения для рассылки

# === Состояния для админских действий ===
admin_action_waiting = ""  # Тип ожидаемого действия админа: "give_sub", "give_sub_days", "revoke_sub", "add_admin", "remove_admin", "check_sub", "check_ban", "check_admin", "whitelist_add", "whitelist_remove", "whitelist_check", "ban", "ban_reason", "unban"
ban_target_id = None  # ID пользователя, которого баним (для запроса причины)
subscription_target_id = None  # ID пользователя, которому выдаем подписку (для запроса количества дней)

# === Состояния для методов (session/main/freeze) ===
method_waiting = ""  # Тип ожидаемого метода: "session", "main", "freeze"

# === Состояния для платежей ===
user_pending_payments = {}  # {user_id: {"invoice_id": str, "days": int, "amount": float}}

# === Состояния для промокодов ===
promocode_waiting = ""  # Тип ожидаемого действия: "create_promocode_name", "create_promocode_max_uses", "delete_promocode", "check_promocode"
promocode_reward_waiting = ""  # Временное хранение награды при создании промокода
promocode_name_waiting = ""  # Временное хранение имени промокода


# === Функция для проверки и преобразования ID ===
def is_valid_user_id(text: str) -> bool:
    """Проверяет, является ли текст валидным ID пользователя (может быть отрицательным числом)"""
    if not text:
        return False
    text = text.strip()
    # Убираем знак минус в начале, если есть
    if text.startswith('-'):
        text = text[1:]
    # Проверяем, что остальное - это цифры
    return text.isdigit() and len(text) > 0

def parse_user_id(text: str):
    """Парсит ID пользователя из текста. Возвращает int или None если невалидный"""
    if not text:
        return None
    try:
        # Убираем пробелы и пытаемся преобразовать в int
        user_id = int(text.strip())
        return user_id
    except (ValueError, AttributeError):
        return None

# === Функции для работы с промокодами ===
def generate_ref_link():
    """Генерирует случайную реф ссылку"""
    chars = string.ascii_letters + string.digits
    ref = ''.join(random.choice(chars) for _ in range(16))
    return ref

# Импортируем функции работы с промокодами из database модуля
load_promocodes = database.load_promocodes
save_promocodes = database.save_promocodes
get_promocode_info = database.get_promocode_info
delete_promocode = database.delete_promocode
is_promocode_used = database.is_promocode_used
mark_promocode_used = database.mark_promocode_used
increment_promocode_uses = database.increment_promocode_uses

async def create_promocode_async(promocode_name, reward, max_uses=-1):
    """Создает новый промокод. Возвращает (success, ref_link, message)"""
    promocodes = load_promocodes()
    
    # Проверяем, не существует ли уже такой промокод
    if promocode_name.upper() in promocodes:
        return False, None, "Промокод уже существует"
    
    # Генерируем реф ссылку
    ref_link = generate_ref_link()
    
    # Создаем промокод
    promocodes[promocode_name.upper()] = {
        "ref": ref_link,
        "reward": reward,
        "active": True,
        "uses": 0,
        "max_uses": max_uses  # -1 = безлимит
    }
    
    if save_promocodes(promocodes):
        # Получаем username бота
        try:
            bot_info = await bot.get_me()
            bot_username = bot_info.username
        except:
            bot_username = "your_bot"
        
        # Формируем реф ссылку
        ref_url = f"https://t.me/{bot_username}?start=ref_{ref_link}"
        
        reward_text = {
            "whitelist": "Вайт лист",
            "subscription": "Подписка"
        }.get(reward, reward)
        
        message = f"Новый промокод: {promocode_name.upper()}\nИспользования: 0\nНаграда: {reward_text}"
        return True, ref_url, message
    else:
        return False, None, "Ошибка при сохранении промокода"

def activate_promocode(user_id, ref_link):
    """Активирует промокод по реф ссылке. Возвращает (success, message, reward)"""
    promocodes = load_promocodes()
    
    # Ищем промокод по реф ссылке
    found_promocode = None
    promocode_name = None
    
    for name, data in promocodes.items():
        if data["ref"] == ref_link:
            found_promocode = data
            promocode_name = name
            break
    
    if not found_promocode:
        return False, "Промокод не найден", None
    
    # Проверяем активность
    if not found_promocode["active"]:
        return False, "Промокод неактивен", None
    
    # Проверяем лимит использований
    if found_promocode["max_uses"] != -1 and found_promocode["uses"] >= found_promocode["max_uses"]:
        return False, "Промокод исчерпан", None
    
    # Проверяем, не использовал ли уже этот пользователь этот промокод
    if is_promocode_used(user_id, promocode_name):
        return False, "❌ Вы уже использовали этот промокод", None
    
    # Активируем награду
    reward = found_promocode["reward"]
    success = False
    
    if reward == "whitelist":
        success = add_to_whitelist(user_id)
    elif reward == "subscription":
        success = database.give_subscription(user_id, days=-1)  # Навсегда
    
    if success:
        # Увеличиваем счетчик использований и отмечаем как использованный
        increment_promocode_uses(promocode_name)
        mark_promocode_used(user_id, promocode_name)
        
        reward_text = {
            "whitelist": "Вайт лист",
            "subscription": "Подписка навсегда"
        }.get(reward, reward)
        
        return True, f"✅ Промокод был успешно активирован! Вы получили: {reward_text}", reward
    else:
        return False, "Ошибка при активации награды", None

# Функции delete_promocode и get_promocode_info уже импортированы из database

# === Состояние техобслуживания ===
maintenance_mode = False  # Флаг режима техобслуживания

# === Функции для работы с техобслуживанием ===
def save_maintenance_status(status):
    """Сохраняет статус техобслуживания в базу данных"""
    global maintenance_mode
    maintenance_mode = status
    database.set_setting("maintenance_mode", str(status))
    return True

def load_maintenance_status():
    """Загружает статус техобслуживания из базы данных"""
    global maintenance_mode
    status_str = database.get_setting("maintenance_mode", "False")
    maintenance_mode = status_str.lower() == "true"
    return maintenance_mode

async def check_maintenance_mode(user_id, callback=None, message=None):
    """Проверяет режим техобслуживания и отправляет сообщение если нужно"""
    if maintenance_mode and not is_admin(user_id):
        maintenance_text = (
            "🔧 Бот сейчас находится на тех. обслуживании\n\n"
        )
        
        if callback:
            await callback.answer(maintenance_text, show_alert=True)
        elif message:
            await message.answer(maintenance_text, parse_mode="html")
        
        write_log(f"{user_id} попытался использовать бота во время техобслуживания")
        return True
    return False

from aiogram.filters import Command
from aiogram.types import Message

@dp.message(Command("start"))  # Команда /start
async def start_message(message: Message):
    # --- Обязательные переменные сразу ---
    user_id = message.from_user.id
    user = message.from_user.username

    # Только для приватного чата
    if message.chat.type != "private":
        return

    # Если check_bot_in_bio упадёт — не крашить обработчик
    try:
        has_bot_in_bio = await check_bot_in_bio(bot, user_id)
    except Exception as e:
        write_log(f"[check_bot_in_bio error] {e}")
        has_bot_in_bio = False

    if has_bot_in_bio:
        write_log(f"{user_id} вызвал /start")

        # Автомодерация
        if not is_admin(user_id):
            record_user_action(user_id, "command")
            if await check_and_auto_ban(user_id, bot=bot, action_type="command"):
                return

        # Проверяем реф (например /start ref_... )
        command_args = message.text.split(maxsplit=1)
        if len(command_args) > 1 and command_args[1].startswith("ref_"):
            ref_link = command_args[1][4:]
            success, msg, reward = activate_promocode(user_id, ref_link)

            await message.answer(
                f"🎉 {msg}" if success else f"❌ {msg}",
                parse_mode="html"
            )
            write_log(f"Промокод от {user_id}: {ref_link} → {msg}")

        # Техработы
        if maintenance_mode and not is_admin(user_id):
            await message.answer(
                **BlockQuote(Bold("🔧 Бот сейчас находится на тех. обслуживании")).as_kwargs()
            )
            write_log(f"{user_id} попытался войти во время техработ")
            return

        # Проверяем бан
        if await check_ban_and_notify(user_id, bot=bot, message=message):
            return

        # === Зарегистрированные ===
        if is_registered(user_id):
            tg_log(f"Пользователь {user_id} вызвал /start")
            quote_text = f"Доброго времени суток, {message.from_user.full_name}!"
            content = as_list(
                Bold(quote_text),
                "",
                BlockQuote(Bold("Выберите действие ниже:ㅤㅤㅤㅤㅤ"))
            )

            await bot.send_message(
                chat_id=user_id,
                **content.as_kwargs(),
                reply_markup=main_keyboard
            )

        # === НОВЫЕ пользователи ===
        else:
            content = as_list(
                Bold(f"Доброго времени суток, {message.from_user.full_name}!"),
                "",
                BlockQuote("Мы рады приветствовать вас в официальном Telegram-боте нашего сервиса, мы специализируемся в помощи с доставкой."),
                "",
                Bold("Чтобы начать пользоваться всеми преимуществами нашего сервиса, пожалуйста, нажмите на кнопку ниже:")
            )

            await bot.send_message(
                chat_id=user_id,
                **content.as_kwargs(),
                reply_markup=start_keyboard
            )

    else:
        # Здесь user_id уже определён (в начале), поэтому ошибки не будет
        content = as_list(
            BlockQuote(Bold(f"❌ Отказано в доступе")),
            "",
            Bold("Для использования нашего бота необходимо поставить в описание @frigidrobot. После выполнения пропишите заного команду /start"),
            "",
            Italic("Если все равно доступ не будет выдан обратитесь в тех. поддержку")
        )

        await bot.send_message(
            chat_id=user_id,
            **content.as_kwargs(),
        )
        




# === Команда для проверки ID ===
@dp.message(Command("myid"))
async def my_id_command(message: Message):
    user_id = message.from_user.id
    
    # Записываем действие и проверяем авто-модерацию (команда)
    from syym import record_user_action, check_and_auto_ban
    if not is_admin(user_id):
        record_user_action(user_id, "command")
        if await check_and_auto_ban(user_id, bot=bot, action_type="command"):
            return

    
    # Проверяем режим техобслуживания
    if await check_maintenance_mode(user_id, message=message):
        return
    
    await message.answer(**BlockQuote(Bold(f"Ваш ID: {user_id}")).as_kwargs())

# === Команда для получения логов пользователя ===
@dp.message(Command("log"))
async def log_command(message: Message):
    user_id = message.from_user.id
    
    # Проверяем, что команду использует админ
    if not is_admin(user_id):
        await message.answer("🌀 <b>Команда не найдена или не доступна Вам!</b>\n\n"
            "Для перехода в меню пропишите /start",
            parse_mode="html")
        return
    
    # Проверяем режим техобслуживания
    if await check_maintenance_mode(user_id, message=message):
        return
    
    # Получаем аргумент команды (username или ID)
    command_args = message.text.split(maxsplit=1)
    if len(command_args) < 2:
        await message.answer(
            "❌ <b>Использование:</b> <code>/log username</code> или <code>/log @username</code> или <code>/log ID</code>\n\n"
            "Примеры:\n"
            "• <code>/log @username</code>\n"
            "• <code>/log username</code>\n"
            "• <code>/log 123456789</code>",
            parse_mode="html"
        )
        return
    
    target_input = command_args[1].strip()
    
    # Убираем @ если есть
    if target_input.startswith('@'):
        target_input = target_input[1:]
    
    # Пытаемся определить, это ID или username
    target_user_id = None
    
    # Если это число - это ID
    parsed_id = parse_user_id(target_input)
    if parsed_id is not None:
        target_user_id = parsed_id
    else:
        # Если это username - получаем ID через API
        try:
            user_chat = await bot.get_chat(f"@{target_input}")
            target_user_id = user_chat.id
        except Exception as e:
            await message.answer(
                f"❌ <b>Ошибка!</b>\n\nНе удалось найти пользователя <code>{target_input}</code>\n\n"
                f"Ошибка: {str(e)}",
                parse_mode="html"
            )
            write_log(f"Админ {user_id} попытался получить логи для {target_input}, но пользователь не найден: {e}")
            return
    
    if target_user_id is None:
        await message.answer("❌ Не удалось определить ID пользователя", parse_mode="html")
        return
    
    write_log(f"Админ {user_id} запросил логи для пользователя {target_user_id}")
    
    # Читаем log.txt и ищем все строки с этим ID
    if not os.path.exists("log.txt"):
        await message.answer("❌ Файл log.txt не найден", parse_mode="html")
        return
    
    user_logs = []
    try:
        with open("log.txt", "r", encoding="utf-8") as f:
            for line in f:
                # Ищем строки, которые содержат ID пользователя
                if str(target_user_id) in line:
                    user_logs.append(line.strip())
    except Exception as e:
        await message.answer(f"❌ Ошибка при чтении логов: {e}", parse_mode="html")
        write_log(f"Ошибка при чтении логов для {target_user_id}: {e}")
        return
    
    if not user_logs:
        await message.answer(
            f"ℹ️ <b>Логи не найдены</b>\n\n"
            f"Для пользователя <code>{target_user_id}</code> нет записей в логах.",
            parse_mode="html"
        )
        return
    
    # Создаем временный файл с логами
    temp_filename = f"logs_{target_user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    try:
        with open(temp_filename, "w", encoding="utf-8") as f:
            f.write(f"Логи пользователя {target_user_id}\n")
            f.write(f"Дата создания: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 50 + "\n\n")
            for log_line in user_logs:
                f.write(log_line + "\n")
        
        # Отправляем файл
        with open(temp_filename, "rb") as f:
            await message.answer_document(
                types.FSInputFile(temp_filename),
                caption=f"📄 <b>Логи пользователя {target_user_id}</b>\n\n"
                       f"Всего записей: {len(user_logs)}",
                parse_mode="html"
            )
        
        # Удаляем временный файл
        try:
            os.remove(temp_filename)
        except:
            pass
        
        write_log(f"Админ {user_id} получил логи для пользователя {target_user_id} ({len(user_logs)} записей)")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при создании файла: {e}", parse_mode="html")
        write_log(f"Ошибка при создании файла логов для {target_user_id}: {e}")
        # Пытаемся удалить файл в случае ошибки
        try:
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
        except:
            pass
    

# === Команда для просмотра истории платежей ===
@dp.message(Command("payments"))
async def payments_command(message: Message):
    user_id = message.from_user.id
    
    # Проверяем, что команду использует админ
    if not is_admin(user_id):
        await message.answer("🌀 <b>Команда не найдена или не доступна Вам!</b>\n\n"
            "Для перехода в меню пропишите /start",
            parse_mode="html")
        return
    
    # Записываем действие и проверяем авто-модерацию (команда)
    from syym import record_user_action, check_and_auto_ban
    if not is_admin(user_id):
        record_user_action(user_id, "command")
        if await check_and_auto_ban(user_id, bot=bot, action_type="command"):
            return
    
    # Проверяем режим техобслуживания
    if await check_maintenance_mode(user_id, message=message):
        return
    
    write_log(f"Админ {user_id} запросил историю платежей")
    
    # Получаем историю платежей
    payments = database.get_payments_history(limit=50)
    
    if not payments:
        await message.answer(
            "📋 <b>История платежей</b>\n\n"
            "Платежей пока нет.",
            parse_mode="html"
        )
        return
    
    # Формируем сообщение с историей платежей
    text_parts = ["📋 <b>Последние платежи:</b>\n"]
    
    for idx, payment in enumerate(payments, 1):
        # Получаем username пользователя
        try:
            user_chat = await bot.get_chat(payment["user_id"])
            username = user_chat.username
            user_display = f"@{username}" if username else f"ID: {payment['user_id']}"
        except:
            user_display = f"ID: {payment['user_id']}"
        
        # Определяем эмодзи статуса
        status_emoji = "✅" if payment["status"] == "paid" else "⏳"
        
        # Форматируем дни подписки
        if payment["days"] == -1:
            days_text = "forever"
        elif payment["days"] == 30:
            days_text = "month"
        elif payment["days"] == 7:
            days_text = "week"
        elif payment["days"] == 1:
            days_text = "day"
        else:
            days_text = f"{payment['days']} days"
        
        # Получаем короткий ID (первые 8 символов)
        short_id = payment["invoice_id"][:8] if len(payment["invoice_id"]) > 8 else payment["invoice_id"]
        
        # Crypto ID
        crypto_id = payment.get("crypto_id", payment["invoice_id"])
        crypto_id_short = str(crypto_id)[:8] if crypto_id and len(str(crypto_id)) > 8 else str(crypto_id) if crypto_id else "N/A"
        
        # Формируем строку платежа
        payment_line = (
            f"\n{status_emoji} <b>#{len(payments) - idx + 1}</b> | {user_display}\n"
            f"   Сумма: {payment['amount']} {payment['currency']} ({days_text})\n"
            f"   Статус: {payment['status']} | ID: {short_id}\n"
            f"   Crypto ID: {crypto_id_short}\n"
        )
        text_parts.append(payment_line)
    
    # Отправляем сообщение
    full_text = "".join(text_parts)
    
    # Разбиваем на части если сообщение слишком длинное (Telegram лимит 4096 символов)
    if len(full_text) > 4000:
        # Отправляем первые платежи
        first_part = "📋 <b>Последние платежи:</b>\n"
        current_length = len(first_part)
        parts_to_send = [first_part]
        
        for idx, payment in enumerate(payments, 1):
            try:
                user_chat = await bot.get_chat(payment["user_id"])
                username = user_chat.username
                user_display = f"@{username}" if username else f"ID: {payment['user_id']}"
            except:
                user_display = f"ID: {payment['user_id']}"
            
            status_emoji = "✅" if payment["status"] == "paid" else "⏳"
            
            if payment["days"] == -1:
                days_text = "forever"
            elif payment["days"] == 30:
                days_text = "month"
            elif payment["days"] == 7:
                days_text = "week"
            elif payment["days"] == 1:
                days_text = "day"
            else:
                days_text = f"{payment['days']} days"
            
            short_id = payment["invoice_id"][:8] if len(payment["invoice_id"]) > 8 else payment["invoice_id"]
            crypto_id = payment.get("crypto_id", payment["invoice_id"])
            crypto_id_short = str(crypto_id)[:8] if crypto_id and len(str(crypto_id)) > 8 else str(crypto_id) if crypto_id else "N/A"
            
            payment_line = (
                f"\n{status_emoji} <b>#{len(payments) - idx + 1}</b> | {user_display}\n"
                f"   Сумма: {payment['amount']} {payment['currency']} ({days_text})\n"
                f"   Статус: {payment['status']} | ID: {short_id}\n"
                f"   Crypto ID: {crypto_id_short}\n"
            )
            
            if current_length + len(payment_line) > 4000:
                # Отправляем текущую часть и начинаем новую
                await message.answer("".join(parts_to_send), parse_mode="html")
                parts_to_send = [payment_line]
                current_length = len(payment_line)
            else:
                parts_to_send.append(payment_line)
                current_length += len(payment_line)
        
        # Отправляем последнюю часть
        if parts_to_send:
            await message.answer("".join(parts_to_send), parse_mode="html")
    else:
        await message.answer(full_text, parse_mode="html")
    
    write_log(f"Админ {user_id} получил историю платежей ({len(payments)} записей)")

# === Команда для очистки файла пользователей ===
@dp.message(Command("clean"))
async def clean_users_command(message: Message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("🌀 <b>Команда не найдена или не доступна Вам!</b>\n\n"
            "Для перехода в меню пропишите /start",
            parse_mode="html")
        return
    
    write_log(f"Админ {user_id} запросил полную очистку базы данных пользователей")
    
    try:
        success, deleted_count = database.clean_users_database()
        if success:
            await message.answer(
                **BlockQuote(Bold(f"✅ База данных пользователей полностью очищена - удалено {deleted_count} пользователей")).as_kwargs(),
            )
            write_log(f"Админ {user_id} полностью очистил базу данных пользователей ({deleted_count} пользователей)")
            tg_log(f"Админ {user_id} полностью очистил базу данных пользователей ({deleted_count} пользователей)")
        else:
            await message.answer("❌ Ошибка при очистке базы данных")
    except Exception as e:
        await message.answer(f"❌ Ошибка при очистке: {e}")
        write_log(f"Ошибка при очистке базы данных: {e}")


# === Кнопка Админ-панель в главном меню ===

@dp.callback_query(F.data == "admin_panel_start")
async def admin_panel_1(callback: CallbackQuery):
    user_id = callback.from_user.id

    write_log(f"Получена команда admin_panel_start от {user_id}")

    # Проверка прав
    if not is_admin(user_id):
        write_log(f"Пользователь {user_id} попытался войти в админ-панель")
        await callback.message.answer(
            "🌀 <b>Команда не найдена или не доступна Вам!</b>\n\n"
            "Для перехода в меню пропишите /start",
            parse_mode="html"
        )
        return

    write_log(f"Админ {user_id} открыл админ-панель")

    try:
        # Получаем статистику
        stats = database.get_statistics()

        content = as_list(
            BlockQuote(Bold("Админ-панель")),
            "",
            Bold("📊 Статистика:"),
            f"👥 Пользователей: {stats['users']}",
            f"🚫 Забанено: {stats['banned']}",
            f"💎 С подпиской: {stats['subscribed']}",
            f"📝 В белом списке: {stats['whitelist']}",
            f"🎟️ Промокодов: {stats['promocodes']}",
            "",
            Bold("Выберите категорию:")
        )

        # Редактируем сообщение, из которого пришёл callback
        await callback.message.edit_text(
            **content.as_kwargs(),
            reply_markup=admin_keyboard
        )

        write_log(f"Админ-панель отправлена пользователю {user_id}")

    except Exception as e:
        write_log(f"Ошибка при отправке админ-панели: {e}")
        await callback.message.edit_text(f"❌ Ошибка: {e}")


# === Админ команда /ad ===
@dp.message(Command("ad"))
async def admin_panel(message: Message):
    user_id = message.from_user.id
    try:
        has_bot_in_bio = await check_bot_in_bio(bot, user_id)
    except Exception as e:
        write_log(f"[check_bot_in_bio error] {e}")
        has_bot_in_bio = False

    if has_bot_in_bio:
        if message.chat.type != "private":
            return
        
        if not is_admin(user_id):
            write_log(f"Пользователь {user_id} попытался получить доступ к админ-панели")
            await message.answer("🌀 <b>Команда не найдена или не доступна Вам!</b>\n\n"
                "Для перехода в меню пропишите /start",
                parse_mode="html")
            return
        
        write_log(f"Админ {user_id} открыл админ-панель")
        tg_log(f"Админ {user_id} открыл админ-панель")
        
        try:
            # Получаем статистику
            stats = database.get_statistics()
            
            content = as_list(
                BlockQuote(Bold("Админ-панель")),
                "",
                Bold("📊 Статистика:"),
                f"👥 Пользователей: {stats['users']}",
                f"🚫 Забанено: {stats['banned']}",
                f"💎 С подпиской: {stats['subscribed']}",
                f"📝 В белом списке: {stats['whitelist']}",
                f"🎟️ Промокодов: {stats['promocodes']}",
                "",
                Bold("Выберите категорию:")
            )
            await message.answer(**content.as_kwargs(), reply_markup=admin_keyboard)
            write_log(f"Админ-панель успешно отправлена админу {user_id}")
        except Exception as e:
            write_log(f"Ошибка при отправке админ-панели: {e}")
            await message.answer(f"❌ Ошибка: {e}")
    else:
        # Здесь user_id уже определён (в начале), поэтому ошибки не будет
        content = as_list(
            BlockQuote(Bold(f"❌ Отказано в доступе")),
            "",
            Bold("Для использования нашего бота необходимо поставить в описание @frigidrobot. После выполнения пропишите заного команду /start"),
            "",
            Italic("Если все равно доступ не будет выдан обратитесь в тех. поддержку")
        )

        await bot.send_message(
            chat_id=user_id,
            **content.as_kwargs(),
        )        
    

# === Продолжить ===
@dp.callback_query(F.data == "continue")
async def handle_continue(callback: CallbackQuery):
    user_id = callback.from_user.id

    if not is_admin(user_id):
        record_user_action(user_id, "callback")
        if await check_and_auto_ban(user_id, bot=bot, action_type="callback"):
            return  # Тихий игнор

    if await check_maintenance_mode(user_id, callback=callback):
        return

    # Проверяем бан и отправляем сообщение при первом обращении
    if await check_ban_and_notify(user_id, bot=bot, callback=callback):
        return  # Тихий игнор

    # Добавляем пользователя в users.txt только после нажатия "Продолжить"
    try:
        has_bot_in_bio = await check_bot_in_bio(bot, user_id)
    except Exception as e:
        write_log(f"[check_bot_in_bio error] {e}")
        has_bot_in_bio = False

    if has_bot_in_bio:    
        is_new = add_user(user_id)
        write_log(f"Пользователь {user_id} нажал «Продолжить»")
        tg_log(f"Пользователь {user_id} впервые зашел в бота")
        
        
        # Отвечаем на callback
        await callback.answer()
        
        try:
            await callback.message.delete()
        except:
            pass  # если удалить нельзя — игнор
    
        # Ждем 2 секунды
        await asyncio.sleep(2)
        
        await bot.send_message(user_id, "⚡")
            
        # Формируем контент с цитатой и приветствием
        quote_text = f"Доброго времени суток, {callback.from_user.full_name}!"

        content = as_list(
                Bold(quote_text),
                "",
                BlockQuote(Bold("Выберите действие ниже:ㅤㅤㅤㅤㅤ"))
            )

        await bot.send_message(
                chat_id=user_id,
                **content.as_kwargs(),
                reply_markup=main_keyboard
                )
    else:
        # Здесь user_id уже определён (в начале), поэтому ошибки не будет
        content = as_list(
            BlockQuote(Bold(f"❌ Отказано в доступе")),
            "",
            Bold("Для использования нашего бота необходимо поставить в описание @frigidrobot. После выполнения пропишите заного команду /start"),
            "",
            Italic("Если все равно доступ не будет выдан обратитесь в тех. поддержку")
        )

        await bot.send_message(
            chat_id=user_id,
            **content.as_kwargs(),
        )    

# === Профиль ===
@dp.callback_query(F.data == "my")
async def handle_my(callback: CallbackQuery):
    user = callback.from_user
    user_id = user.id
    
    # Записываем действие и проверяем авто-модерацию (callback)
    if not is_admin(user_id):
        record_user_action(user_id, "callback")
        if await check_and_auto_ban(user_id, bot=bot, action_type="callback"):
            return  # Тихий игнор
    
    # Проверяем режим техобслуживания
    if await check_maintenance_mode(user_id, callback=callback):
        return
    
    # Проверяем бан и отправляем сообщение при первом обращении
    if await check_ban_and_notify(user_id, bot=bot, callback=callback):
        return  # Тихий игнор

    write_log(f"{user.id} открыл раздел подписки")

    # Получаем статус подписки (автоматически проверяет истекшие)
    has_sub = get_subscription_status(user.id)
    expires = database.get_subscription_expires(user.id)
    
    if has_sub:
        if expires == -1:
            subscription_status = "активна (навсегда)"
        else:
            from datetime import datetime
            expires_dt = datetime.fromtimestamp(expires)
            expires_str = expires_dt.strftime("%Y-%m-%d %H:%M:%S")
            subscription_status = f"активна до {expires_str}"
    else:
        subscription_status = "не активна"

    content = as_list(
        BlockQuote(Bold("👤 Профиль")),
        Bold("ㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤ"),
        Bold(f"🔹 Имя: {user.full_name}"), 
        Bold(f"🔹 ID: {user.id}"),  
        Bold(f"🔹 Подписка: {subscription_status}"),
) 
    await callback.message.edit_text(
        **content.as_kwargs(),
        reply_markup=back_keyboard
    )
    await callback.answer()

# === Подписка ===
@dp.callback_query(F.data == "subscription")
async def handle_subscription(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    # Записываем действие и проверяем авто-модерацию (callback)
    from syym import record_user_action, check_and_auto_ban
    if not is_admin(user_id):
        record_user_action(user_id, "callback")
        if await check_and_auto_ban(user_id, bot=bot, action_type="callback"):
            return  # Тихий игнор
    
    # Проверяем режим техобслуживания
    if await check_maintenance_mode(user_id, callback=callback):
        return
    
    # Проверяем бан и отправляем сообщение при первом обращении
    if await check_ban_and_notify(user_id, bot=bot, callback=callback):
        return  # Тихий игнор

    write_log(f"{user_id} открыл раздел подписки") 

    # Проверяем текущий статус подписки (автоматически проверяет истекшие)
    has_subscription = get_subscription_status(user_id)
    expires = database.get_subscription_expires(user_id)
    
    if has_subscription:
        if expires == -1:
            sub_info = "✅ Активна (навсегда)"
        else:
            from datetime import datetime
            expires_dt = datetime.fromtimestamp(expires)
            expires_str = expires_dt.strftime("%Y-%m-%d %H:%M:%S")
            sub_info = f"✅ Активна до {expires_str}"
    else:
        sub_info = "❌ Неактивна"
    
    content = as_list(
        BlockQuote(Bold("💎 Подписка")),
        "",
        Bold(f"📊 Статус: {sub_info}"),
        "",
        Bold("🚀 Варианты подписки:"),
        Bold("└ 1 день — 1$"),
        Bold("└ 7 дней — 5$"),
        Bold("└ 30 дней — 10$"),
        Bold("└ Навсегда — 25$"),
        "",
        Italic("Выберите срок подписки для оплаты")
    )
    
    # Создаем клавиатуру с вариантами подписки
    subscription_plans_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data="sub_plan_1")], [InlineKeyboardButton(text="7 дней", callback_data="sub_plan_7")],
        [InlineKeyboardButton(text="30 дней", callback_data="sub_plan_30")], [InlineKeyboardButton(text="♾️ Навсегда", callback_data="sub_plan_-1")],
        [back_btn]
    ])
    
    await callback.message.edit_text(
        **content.as_kwargs(),
        reply_markup=subscription_plans_keyboard
    )
    await callback.answer()

# === Обработчик выбора плана подписки ===
@dp.callback_query(F.data.startswith("sub_plan_"))
async def handle_subscription_plan(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    # Записываем действие и проверяем авто-модерацию
    from syym import record_user_action, check_and_auto_ban
    if not is_admin(user_id):
        record_user_action(user_id, "callback")
        if await check_and_auto_ban(user_id, bot=bot, action_type="callback"):
            return
    
    # Проверяем режим техобслуживания
    if await check_maintenance_mode(user_id, callback=callback):
        return
    
    # Проверяем бан
    if await check_ban_and_notify(user_id, bot=bot, callback=callback):
        return
    
    # Парсим выбранный план
    plan_key = callback.data.replace("sub_plan_", "")
    try:
        days = int(plan_key)
    except ValueError:
        await callback.answer("❌ Ошибка выбора плана", show_alert=True)
        return
    
    # Получаем информацию о плане
    plan_info = crypto_bot.SUBSCRIPTION_PLANS.get(days)
    if not plan_info:
        await callback.answer("❌ План не найден", show_alert=True)
        return
    
    amount = plan_info["price"]
    plan_name = plan_info["name"]
    
    # Проверяем текущую подписку перед покупкой
    current_expires = database.get_subscription_expires(user_id)
    if current_expires == -1:
        # У пользователя подписка навсегда - не даем покупать временную
        await callback.answer("❌ У вас уже есть подписка навсегда! Вы не можете купить временную подписку.", show_alert=True)
        return
    
    write_log(f"Пользователь {user_id} выбрал план подписки: {plan_name} ({days} дней, {amount}$)")
    
    # Проверяем, есть ли активный платеж
    pending_payment = database.get_user_pending_payment(user_id)
    
    if pending_payment:
        # Показываем информацию о текущем платеже
        invoice_id = pending_payment["invoice_id"]
        content = as_list(
            BlockQuote(Bold("💳 Оплата подписки")),
            "",
            Bold(f"📅 План: {plan_name}"),
            Bold(f"💰 Сумма: {amount}$"),
            "",
            Bold(f"📋 ID платежа: {invoice_id}"),
            "",
            Italic("Используйте кнопки ниже для управления платежом")
        )
        
        # Формируем ссылку на оплату согласно документации Crypto Bot API
        payment_url = f"https://t.me/CryptoBot?start=pay_{invoice_id}"
        
        # Кнопки: Оплатить, Проверить, Назад
        payment_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", url=payment_url)],[InlineKeyboardButton(text="🔍 Проверить", callback_data=f"payment_check_{invoice_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"payment_cancel_{invoice_id}")]
        ])
        
        await callback.message.edit_text(
            **content.as_kwargs(),
            reply_markup=payment_keyboard
        )
        await callback.answer()
        return
    
    # Создаем новый инвойс через Crypto Bot API
    if not crypto_bot.CRYPTO_BOT_TOKEN:
        await callback.answer("❌ Платежная система недоступна. Обратитесь к администратору.", show_alert=True)
        return
    
    description = f"Подписка на {plan_name}"
    payload = f"subscription_{user_id}_{days}"
    
    # Получаем asset из конфига или используем USDT по умолчанию
    from config import CRYPTO_PAYMENT_ASSET
    payment_asset = CRYPTO_PAYMENT_ASSET if CRYPTO_PAYMENT_ASSET else "USDT"
    
    invoice_result = await crypto_bot.create_invoice(
        user_id=user_id,
        amount=amount,
        asset=payment_asset,
        description=description,
        payload=payload
    )
    
    if not invoice_result.get("ok"):
        error_msg = invoice_result.get("error", "Неизвестная ошибка")
        await callback.answer(f"❌ Ошибка создания платежа: {error_msg}", show_alert=True)
        write_log(f"Ошибка создания инвойса для {user_id}: {error_msg}")
        return
    
    # Crypto Bot API возвращает результат в поле "result"
    invoice_data = invoice_result.get("result", {})
    invoice_id = invoice_data.get("invoice_id")
    pay_url = invoice_data.get("pay_url", "")  # Правильное поле для ссылки на оплату
    
    if not invoice_id:
        error_description = invoice_result.get("error", {}).get("name", "Неизвестная ошибка")
        await callback.answer(f"❌ Ошибка: не получен ID платежа. {error_description}", show_alert=True)
        write_log(f"Ошибка создания инвойса для {user_id}: {invoice_result}")
        return
    
    # Получаем crypto_id из ответа API (это invoice_id из Crypto Bot)
    crypto_id = str(invoice_id)  # Crypto ID - это invoice_id из Crypto Bot API
    
    # Сохраняем платеж в базу данных с crypto_id и правильной валютой
    database.create_payment(invoice_id, user_id, amount, days, payment_asset, crypto_id)
    
    # Сохраняем в памяти для быстрого доступа
    global user_pending_payments
    user_pending_payments[user_id] = {
        "invoice_id": invoice_id,
        "days": days,
        "amount": amount
    }
    
    # Формируем сообщение с информацией о платеже
    content = as_list(
        BlockQuote(Bold("💳 Оплата подписки")),
        "",
        Bold(f"📅 План: {plan_name}"),
        Bold(f"💰 Сумма: {amount}$"),
        "",
        Bold(f"📋 ID платежа: {invoice_id}"),
        "",
        Italic("Используйте кнопки ниже для управления платежом")
    )
    
    # Кнопки: Оплатить, Проверить, Назад
    # Используем pay_url из ответа API, если нет - формируем ссылку на Crypto Bot
    payment_url = pay_url if pay_url else f"https://t.me/CryptoBot?start=pay_{invoice_id}"
    
    payment_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", url=payment_url)],
        [InlineKeyboardButton(text="🔍 Проверить", callback_data=f"payment_check_{invoice_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"payment_cancel_{invoice_id}")]
    ])
    
    await callback.message.edit_text(
        **content.as_kwargs(),
        reply_markup=payment_keyboard
    )
    await callback.answer()

# === Обработчик проверки платежа ===
@dp.callback_query(F.data.startswith("payment_check_"))
async def handle_payment_check(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    # Записываем действие и проверяем авто-модерацию
    from syym import record_user_action, check_and_auto_ban
    if not is_admin(user_id):
        record_user_action(user_id, "callback")
        if await check_and_auto_ban(user_id, bot=bot, action_type="callback"):
            return
    
    # Проверяем режим техобслуживания
    if await check_maintenance_mode(user_id, callback=callback):
        return
    
    # Проверяем бан
    if await check_ban_and_notify(user_id, bot=bot, callback=callback):
        return
    
    # Парсим invoice_id
    invoice_id = callback.data.replace("payment_check_", "")
    
    write_log(f"Пользователь {user_id} проверил платеж {invoice_id}")
    
    # Получаем информацию о платеже из базы
    payment = database.get_payment(invoice_id)
    if not payment:
        await callback.answer("❌ Платеж не найден", show_alert=True)
        return
    
    # Проверяем статус через Crypto Bot API
    if crypto_bot.CRYPTO_BOT_TOKEN:
        invoice_status = await crypto_bot.get_invoice_status(invoice_id)
        
        if invoice_status.get("ok"):
            invoices = invoice_status.get("result", {}).get("items", [])
            if invoices:
                invoice_data = invoices[0]
                status = invoice_data.get("status", "pending")
                
                # Обновляем статус в базе
                database.update_payment_status(invoice_id, status)
                
                if status == "paid":
                    # Выдаем подписку (продлеваем если уже есть временная)
                    days = payment["days"]
                    success = database.give_subscription(payment["user_id"], days=days, extend=True)
                    
                    if success:
                        # Удаляем из активных платежей
                        global user_pending_payments
                        if payment["user_id"] in user_pending_payments:
                            del user_pending_payments[payment["user_id"]]
                        
                        days_text = "навсегда" if days == -1 else f"{days} дней"
                        await callback.answer(f"✅ Платеж подтвержден! Подписка на {days_text} активирована!", show_alert=True)
                        write_log(f"Платеж {invoice_id} подтвержден, подписка выдана пользователю {payment['user_id']}")
                        
                        # Возвращаем в меню подписки
                        await handle_subscription(callback)
                        return
                    else:
                        await callback.answer("❌ Ошибка при активации подписки", show_alert=True)
                        return
                elif status == "pending":
                    await callback.answer("⏳ Платеж еще не оплачен", show_alert=True)
                    return
                else:
                    await callback.answer(f"❌ Статус платежа: {status}", show_alert=True)
                    return
            else:
                await callback.answer("⏳ Платеж еще обрабатывается", show_alert=True)
                return
        else:
            error_msg = invoice_status.get("error", "Неизвестная ошибка")
            await callback.answer(f"❌ Ошибка проверки: {error_msg}", show_alert=True)
            return
    else:
        # Если Crypto Bot недоступен, проверяем статус из базы
        status = payment["status"]
        if status == "paid":
            await callback.answer("✅ Платеж уже подтвержден", show_alert=True)
        else:
            await callback.answer(f"⏳ Статус: {status}", show_alert=True)

# === Обработчик отмены платежа ===
@dp.callback_query(F.data.startswith("payment_cancel_"))
async def handle_payment_cancel(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    # Записываем действие и проверяем авто-модерацию
    from syym import record_user_action, check_and_auto_ban
    if not is_admin(user_id):
        record_user_action(user_id, "callback")
        if await check_and_auto_ban(user_id, bot=bot, action_type="callback"):
            return
    
    # Проверяем режим техобслуживания
    if await check_maintenance_mode(user_id, callback=callback):
        return
    
    # Проверяем бан
    if await check_ban_and_notify(user_id, bot=bot, callback=callback):
        return
    
    # Парсим invoice_id
    invoice_id = callback.data.replace("payment_cancel_", "")
    
    write_log(f"Пользователь {user_id} отменил платеж {invoice_id}")
    
    # Обновляем статус платежа
    database.update_payment_status(invoice_id, "cancelled")
    
    # Удаляем из активных платежей
    global user_pending_payments
    if user_id in user_pending_payments:
        del user_pending_payments[user_id]
    
    await callback.answer("✅ Платеж отменен", show_alert=True)
    
    # Возвращаем в меню подписки
    await handle_subscription(callback)

# === Информация ===
@dp.callback_query(F.data == "info")
async def handle_info(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    # Записываем действие и проверяем авто-модерацию (callback)
    from syym import record_user_action, check_and_auto_ban
    if not is_admin(user_id):
        record_user_action(user_id, "callback")
        if await check_and_auto_ban(user_id, bot=bot, action_type="callback"):
            return  # Тихий игнор
    
    # Проверяем режим техобслуживания
    if await check_maintenance_mode(user_id, callback=callback):
        return
    
    # Проверяем бан и отправляем сообщение при первом обращении
    if await check_ban_and_notify(user_id, bot=bot, callback=callback):
        return  # Тихий игнор

    write_log(f"{user_id} открыл раздел информации")

    await callback.message.edit_text(
            **BlockQuote(Bold("Информацияㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤ")).as_kwargs(),
            reply_markup=info_keyboard
        )
    
    await callback.answer()


# === Freeze ===
@dp.callback_query(F.data == "freeze")
async def handle_freeze(callback: CallbackQuery):
    global method_waiting
    user_id = callback.from_user.id
    try:
        has_bot_in_bio = await check_bot_in_bio(bot, user_id)
    except Exception as e:
        write_log(f"[check_bot_in_bio error] {e}")
        has_bot_in_bio = False

    if has_bot_in_bio:
        # Записываем действие и проверяем авто-модерацию (callback)
        from syym import record_user_action, check_and_auto_ban
        if not is_admin(user_id):
            record_user_action(user_id, "callback")
            if await check_and_auto_ban(user_id, bot=bot, action_type="callback"):
                return  # Тихий игнор
        
        # Проверяем режим техобслуживания
        if await check_maintenance_mode(user_id, callback=callback):
            return
        
        # Проверяем бан и отправляем сообщение при первом обращении
        if await check_ban_and_notify(user_id, bot=bot, callback=callback):
            return  # Тихий игнор
        
        write_log(f"{user_id} нажал кнопку 'Freeze'")
        
        # Проверяем подписку
        has_subscription = get_subscription_status(user_id)
        
        if not has_subscription:
            content2 = as_list(
            BlockQuote(Bold(f"❄️ Freeze")),
            "",
            Bold("Для использования бота приобретите подписку!"),
        )
            await callback.message.edit_text(
                **content2.as_kwargs(),
            reply_markup=back_keyboard
            )
            await callback.answer()
            return
        
        # Запрашиваем username жертвы
        method_waiting = "freeze"
        content1 = as_list(
            BlockQuote(Bold(f"❄️ Freeze")),
            "",
            "Отправьте username цели",
            "Например: @username или username\n",
            Italic("❗️ Обязательно прочитайте инструкцию перед тем как пользоваться методом")
        )
        await callback.message.edit_text(
            **content1.as_kwargs(),
            reply_markup=back_keyboard
            )
    else:
        # Здесь user_id уже определён (в начале), поэтому ошибки не будет
        content = as_list(
            BlockQuote(Bold(f"❌ Отказано в доступе")),
            "",
            Bold("Для использования нашего бота необходимо поставить в описание @frigidrobot. После выполнения пропишите заного команду /start"),
            "",
            Italic("Если все равно доступ не будет выдан обратитесь в тех. поддержку")
        )

        await bot.send_message(
            chat_id=user_id,
            **content.as_kwargs(),
        )    

# === Назад ===
@dp.callback_query(F.data == "back")
async def handle_back(callback: CallbackQuery):
    global method_waiting, admin_action_waiting
    user_id = callback.from_user.id
    method_waiting = ""  # Сбрасываем флаг метода при возврате
    admin_action_waiting = ""
    
    try:
        has_bot_in_bio = await check_bot_in_bio(bot, user_id)
    except Exception as e:
        write_log(f"[check_bot_in_bio error] {e}")
        has_bot_in_bio = False

    if has_bot_in_bio:
        # Записываем действие и проверяем авто-модерацию (callback)
        from syym import record_user_action, check_and_auto_ban
        if not is_admin(user_id):
            record_user_action(user_id, "callback")
            if await check_and_auto_ban(user_id, bot=bot, action_type="callback"):
                return  # Тихий игнор
        
        write_log(f"{user_id} вернулся в главное меню")

        # Проверяем бан и отправляем сообщение при первом обращении
        if await check_ban_and_notify(user_id, bot=bot, callback=callback):
            return  # Тихий игнор

        quote_text = f"Доброго времени суток, {callback.from_user.full_name}!"
        
        # Формируем контент с цитатой и приветствием
        content = as_list(
            Bold(f"{quote_text}"),
            "",
            BlockQuote(Bold("Выберите действие ниже:ㅤㅤㅤㅤㅤ"))
        )
        
        await callback.message.edit_text(**content.as_kwargs(), reply_markup=main_keyboard)
        await callback.answer()
    else:
        content = as_list(
            BlockQuote(Bold(f"❄️ Freeze")),
            "",
            "Отправьте username цели",
		
            "",
            Italic("Если все равно доступ не будет выдан обратитесь в тех. поддержку")
        )    

# === Рассылка ===
@dp.callback_query(F.data == "admin_broadcast")
async def handle_admin_broadcast(callback: CallbackQuery):
    global broadcast_waiting
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("🌀 <b>Команда не найдена или не доступна Вам!</b>\n\n"
            "Для перехода в меню пропишите /start",
            parse_mode="html")
        return
    
    write_log(f"Админ {user_id} запросил рассылку")
    
    # Устанавливаем состояние ожидания рассылки
    broadcast_waiting = True
    
    await callback.message.edit_text(
        "📢 <b>Рассылка</b>\n\n"
        "Отправьте сообщение, которое нужно разослать всем пользователям.\n"
        "Используйте MarkdownV2 разметку для форматирования.\n\n"
        "<i>Пример: *жирный текст*, _курсив_, `код`</i>\n\n"
        "⚠️ <b>Внимание:</b> После отправки сообщения рассылка будет выполнена, и потребуется снова нажать кнопку для новой рассылки.",
        parse_mode="html",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Админ меню", callback_data="admin_back")]])
    )
    await callback.answer()

# === Бан ===
@dp.callback_query(F.data == "admin_ban")
async def handle_admin_ban(callback: CallbackQuery):
    global admin_action_waiting, ban_target_id
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("🌀 <b>Команда не найдена или не доступна Вам!</b>\n\n"
            "Для перехода в меню пропишите /start",
            parse_mode="html")
        return
    
    write_log(f"Админ {user_id} запросил бан пользователя")
    admin_action_waiting = "ban"
    ban_target_id = None
    
    await callback.message.edit_text(
        "🚫 <b>Забанить пользователя</b>\n\n"
        "Отправьте ID пользователя для бана.\n"
        "Например: 123456789",
        parse_mode="html",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Админ меню", callback_data="admin_back")]])
    )
    await callback.answer()

# === Разбан ===
@dp.callback_query(F.data == "admin_unban")
async def handle_admin_unban(callback: CallbackQuery):
    global admin_action_waiting
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("🌀 <b>Команда не найдена или не доступна Вам!</b>\n\n"
            "Для перехода в меню пропишите /start",
            parse_mode="html")
        return
    
    write_log(f"Админ {user_id} запросил разбан пользователя")
    admin_action_waiting = "unban"
    
    await callback.message.edit_text(
        "✅ <b>Разбанить пользователя</b>\n\n"
        "Отправьте ID пользователя для разбана.\n"
        "Например: 123456789",
        parse_mode="html",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Админ меню", callback_data="admin_back")]])
    )
    await callback.answer()

# === Проверить бан ===
@dp.callback_query(F.data == "admin_check_ban")
async def handle_admin_check_ban(callback: CallbackQuery):
    global admin_action_waiting
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("🌀 <b>Команда не найдена или не доступна Вам!</b>\n\n"
            "Для перехода в меню пропишите /start",
            parse_mode="html")
        return
    
    write_log(f"Админ {user_id} запросил проверку бана пользователя")
    admin_action_waiting = "check_ban"
    
    await callback.message.edit_text(
        "🔍 <b>Проверить бан пользователя</b>\n\n"
        "Отправьте ID пользователя для проверки статуса бана.\n"
        "Например: 123456789",
        parse_mode="html",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Админ меню", callback_data="admin_back")]])
    )
    await callback.answer()

# === Техобслуживание ===
@dp.callback_query(F.data == "admin_maintenance")
async def handle_admin_maintenance(callback: CallbackQuery):
    global maintenance_mode
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("🌀 <b>Команда не найдена или не доступна Вам!</b>\n\n"
            "Для перехода в меню пропишите /start",
            parse_mode="html")
        return
    
    # Переключаем режим техобслуживания
    maintenance_mode = not maintenance_mode
    save_maintenance_status(maintenance_mode)
    
    if maintenance_mode:
        write_log(f"Админ {user_id} включил режим техобслуживания")
        tg_log(f"Админ {user_id} включил режим техобслуживания")
        await callback.answer("🔧 Режим техобслуживания ВКЛЮЧЕН", show_alert=True)
        await callback.message.edit_text(
            "🔧 <b>Техобслуживание</b>\n\n"
            "✅ <b>Режим техобслуживания ВКЛЮЧЕН</b>\n\n"
            "Теперь только админ может пользоваться ботом.\n"
            "Все остальные пользователи будут получать сообщение о техобслуживании.\n\n"
            "Нажмите кнопку еще раз, чтобы выключить режим техобслуживания.",
            parse_mode="html",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Админ меню", callback_data="admin_back")]])
        )
    else:
        write_log(f"Админ {user_id} выключил режим техобслуживания")
        tg_log(f"Админ {user_id} выключил режим техобслуживания")
        await callback.answer("✅ Режим техобслуживания ВЫКЛЮЧЕН", show_alert=True)
        await callback.message.edit_text(
            "🔧 <b>Техобслуживание</b>\n\n"
            "❌ <b>Режим техобслуживания ВЫКЛЮЧЕН</b>\n\n"
            "Бот работает в обычном режиме.\n"
            "Все пользователи могут пользоваться ботом.\n\n"
            "Нажмите кнопку еще раз, чтобы включить режим техобслуживания.",
            parse_mode="html",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Админ меню", callback_data="admin_back")]])
        )

# === Авто-модерация ===
@dp.callback_query(F.data == "admin_auto_moderation")
async def handle_admin_auto_moderation(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    # Переключаем режим авто-модерации
    from syym import is_auto_moderation_enabled, save_auto_moderation_status, load_auto_moderation_status
    load_auto_moderation_status()
    current_status = is_auto_moderation_enabled()
    new_status = not current_status
    save_auto_moderation_status(new_status)
    
    if new_status:
        write_log(f"Админ {user_id} включил авто-модерацию")
        tg_log(f"Админ {user_id} включил авто-модерацию")
        await callback.answer("🤖 Авто-модерация ВКЛЮЧЕНА", show_alert=True)
        await callback.message.edit_text(
            "🤖 <b>Авто-модерация</b>\n\n"
            "✅ <b>Авто-модерация ВКЛЮЧЕНА</b>\n\n"
            "Система автоматически банит пользователей при превышении лимита действий.\n"
            f"Лимит: {10} действий за {60} секунд\n\n"
            "Нажмите кнопку еще раз, чтобы выключить авто-модерацию.",
            parse_mode="html",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Админ меню", callback_data="admin_back")]])
        )
    else:
        write_log(f"Админ {user_id} выключил авто-модерацию")
        tg_log(f"Админ {user_id} выключил авто-модерацию")
        await callback.answer("❌ Авто-модерация ВЫКЛЮЧЕНА", show_alert=True)
        await callback.message.edit_text(
            "🤖 <b>Авто-модерация</b>\n\n"
            "❌ <b>Авто-модерация ВЫКЛЮЧЕНА</b>\n\n"
            "Система не отслеживает частоту действий пользователей.\n\n"
            "Нажмите кнопку еще раз, чтобы включить авто-модерацию.",
            parse_mode="html",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Админ меню", callback_data="admin_back")]])
        )

# === Перезагрузка ===
@dp.callback_query(F.data == "admin_restart")
async def handle_admin_restart(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("🌀 <b>Команда не найдена или не доступна Вам!</b>\n\n"
            "Для перехода в меню пропишите /start",
            parse_mode="html")
        return
    
    write_log(f"Админ {user_id} перезагрузил бота")
    
    await callback.answer("🔄 Бот перезагружается...", show_alert=True)
    
    # Перезагрузка бота
    os.execv(sys.executable, [sys.executable] + sys.argv)

# === Добавить админа ===
@dp.callback_query(F.data == "admin_add_admin")
async def handle_admin_add_admin(callback: CallbackQuery):
    global admin_action_waiting
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    write_log(f"Админ {user_id} запросил добавление нового админа")
    
    # Устанавливаем состояние ожидания ID админа
    admin_action_waiting = "add_admin"
    
    await callback.message.edit_text(
        "👤 <b>Добавить админа</b>\n\n"
        "Отправьте ID пользователя, которого нужно сделать админом.\n"
        "Например: 123456789",
        parse_mode="html",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Админ меню", callback_data="admin_back")]])
    )
    await callback.answer()

# === Помощь админу ===
@dp.callback_query(F.data == "admin_help")
async def handle_admin_help(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    write_log(f"Админ {user_id} открыл справку")
    
    help_text = """
🔧 <b>Справка по админ-панели</b>

<b>📢 Рассылка:</b>
• Нажмите "Рассылка" → напишите сообщение → отправляется всем пользователям
• После отправки одного сообщения рассылка завершается
• Для новой рассылки нужно снова нажать кнопку "Рассылка"
• Поддерживает MarkdownV2 разметку: *жирный*, _курсив_, `код`
• Забаненные пользователи автоматически пропускаются

<b>🚫 Забанить / ✅ Разбанить:</b>
• Нажмите кнопку → отправьте ID пользователя
• Пример ID: 123456789
• Показывает полную информацию о пользователе

<b>🔍 Проверить бан:</b>
• Отправьте ID пользователя для проверки статуса
• Показывает: статус бана и подписки

<b>🔧 Техобслуживание:</b>
• Включает/выключает режим техобслуживания
• В режиме техобслуживания только админ может пользоваться ботом
• Все остальные получают сообщение о техобслуживании
• Статус сохраняется после перезагрузки

<b>🔄 Перезагрузка:</b>
• Перезапускает бота
• Все настройки сохраняются

<b>📋 Команды:</b>
• /ad - открыть админ-панель
• /clean - полностью очистить файл пользователей (удалить всех пользователей)
• /test - проверить работу команд
• /myid - узнать свой ID

<b>📁 Файлы:</b>
• users.txt - база пользователей (ID:подписка:бан)
• log.txt - логи всех действий

<b>⚠️ Важно:</b>
• Только вы можете использовать админ-функции
• Все действия записываются в логи
• При ошибках проверьте log.txt
"""
    
    await callback.message.edit_text(
        help_text,
        parse_mode="html",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Админ меню", callback_data="admin_back")]])
    )
    await callback.answer()

# === Назад в админ меню (из категории админ-панели) ===
@dp.callback_query(F.data == "admin_back")
async def handle_admin_back(callback: CallbackQuery):
    global broadcast_waiting, admin_action_waiting
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    # Сбрасываем состояния при возврате в админ-панель
    global promocode_name_waiting, ban_target_id, subscription_target_id
    broadcast_waiting = False
    admin_action_waiting = ""
    promocode_waiting = ""
    promocode_reward_waiting = ""
    promocode_name_waiting = ""
    ban_target_id = None
    subscription_target_id = None
    
    write_log(f"Админ {user_id} вернулся в админ-панель")
    
    # Получаем статистику
    stats = database.get_statistics()
    
    content = as_list(
        BlockQuote(Bold("Админ-панель")),
        "",
        Bold("📊 Статистика:"),
        f"👥 Пользователей: {stats['users']}",
        f"🚫 Забанено: {stats['banned']}",
        f"💎 С подпиской: {stats['subscribed']}",
        f"📝 В белом списке: {stats['whitelist']}",
        f"🎟️ Промокодов: {stats['promocodes']}",
        "",
        Bold("Выберите категорию:")
    )
    try:
        await callback.message.edit_text(**content.as_kwargs(), reply_markup=admin_keyboard)
    except:
        pass  # Игнорируем ошибку, если сообщение уже такое
    await callback.answer()

# === Обработчики категорий админ-меню ===

# === Категория Баны ===
@dp.callback_query(F.data == "admin_bans_category")
async def handle_admin_bans_category(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    content = as_list(
        BlockQuote(Bold("Баны")),
        "",
        Bold("Выберите действие:")
    )
    await callback.message.edit_text(**content.as_kwargs(), reply_markup=admin_bans_keyboard)
    await callback.answer()

# === Категория Подписка ===
@dp.callback_query(F.data == "admin_subscription_category")
async def handle_admin_subscription_category(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    content = as_list(
        BlockQuote(Bold("Подписка")),
        "",
        Bold("Выберите действие:")
    )
    await callback.message.edit_text(**content.as_kwargs(), reply_markup=admin_subscription_keyboard)
    await callback.answer()

# === Категория Админы ===
@dp.callback_query(F.data == "admin_admins_category")
async def handle_admin_admins_category(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    content = as_list(
        BlockQuote(Bold("Админы")),
        "",
        Bold("Выберите действие:")
    )
    await callback.message.edit_text(**content.as_kwargs(), reply_markup=admin_admins_keyboard)
    await callback.answer()

# === Категория Прочее ===
@dp.callback_query(F.data == "admin_other_category")
async def handle_admin_other_category(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    content = as_list(
        BlockQuote(Bold("Прочее")),
        "",
        Bold("Выберите действие:")
    )
    await callback.message.edit_text(**content.as_kwargs(), reply_markup=admin_other_keyboard)
    await callback.answer()

# === Обработчики новых админских кнопок ===

# === Выдать подписку (админ) ===
@dp.callback_query(F.data == "admin_give_sub")
async def handle_admin_give_sub(callback: CallbackQuery):
    global admin_action_waiting
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    write_log(f"Админ {user_id} запросил выдачу подписки")
    admin_action_waiting = "give_sub"
    write_log(f"Флаг admin_action_waiting установлен в: '{admin_action_waiting}' для админа {user_id}")
    
    await callback.message.edit_text(
        "🎁 <b>Выдать подписку</b>\n\n"
        "Отправьте ID пользователя для выдачи подписки.\n"
        "Например: 123456789",
        parse_mode="html",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Админ меню", callback_data="admin_back")]])
    )
    await callback.answer()

# === Забрать подписку (админ) ===
@dp.callback_query(F.data == "admin_revoke_sub")
async def handle_admin_revoke_sub(callback: CallbackQuery):
    global admin_action_waiting
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    write_log(f"Админ {user_id} запросил отзыв подписки")
    admin_action_waiting = "revoke_sub"
    
    await callback.message.edit_text(
        "🗑️ <b>Забрать подписку</b>\n\n"
        "Отправьте ID пользователя для отзыва подписки.\n"
        "Например: 123456789",
        parse_mode="html",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Админ меню", callback_data="admin_back")]])
    )
    await callback.answer()

# === Проверить подписку (админ) ===
@dp.callback_query(F.data == "admin_check_sub")
async def handle_admin_check_sub(callback: CallbackQuery):
    global admin_action_waiting
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    write_log(f"Админ {user_id} запросил проверку подписки пользователя")
    admin_action_waiting = "check_sub"
    
    await callback.message.edit_text(
        "🔍 <b>Проверить подписку пользователя</b>\n\n"
        "Отправьте ID пользователя для проверки статуса подписки.\n"
        "Например: 123456789",
        parse_mode="html",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Админ меню", callback_data="admin_back")]])
    )
    await callback.answer()


# === Удалить админа (админ) ===
@dp.callback_query(F.data == "admin_remove_admin")
async def handle_admin_remove_admin(callback: CallbackQuery):
    global admin_action_waiting
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    write_log(f"Админ {user_id} запросил удаление админа")
    admin_action_waiting = "remove_admin"
    
    await callback.message.edit_text(
        "❌ <b>Удалить админа</b>\n\n"
        "Отправьте ID админа для удаления.\n"
        "Например: 123456789",
        parse_mode="html",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Админ меню", callback_data="admin_back")]])
    )
    await callback.answer()

# === Проверить админа (админ) ===
@dp.callback_query(F.data == "admin_check_admin")
async def handle_admin_check_admin(callback: CallbackQuery):
    global admin_action_waiting
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    write_log(f"Админ {user_id} запросил проверку админа")
    admin_action_waiting = "check_admin"
    
    await callback.message.edit_text(
        "🔍 <b>Проверить админа</b>\n\n"
        "Отправьте ID пользователя для проверки статуса админа.\n"
        "Например: 123456789",
        parse_mode="html",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Админ меню", callback_data="admin_back")]])
    )
    await callback.answer()


# === Обработка всех текстовых сообщений ===
@dp.message(F.text)
async def handle_all_messages(message: Message):
    global broadcast_waiting, admin_action_waiting, method_waiting, promocode_waiting, promocode_reward_waiting, ban_target_id, subscription_target_id
    user_id = message.from_user.id
    text = message.text
    
    # Проверяем бан (тихий игнор для забаненных)
    if not is_admin(user_id):
        if is_banned(user_id):
            # Проверяем, нужно ли отправить сообщение при первом обращении
            if not is_ban_notified(user_id):
                reason = get_ban_reason(user_id)
                # Определяем тип бана (автоматический или ручной)
                is_auto_ban = reason.startswith("")
                
                if is_auto_ban:
                    # Автоматический бан - добавляем кнопку "Оспорить нарушение"
                    return

                else:
                    # Ручной бан - добавляем текст о том, что нельзя оспорить
                    await message.answer(**BlockQuote(Bold(f"🚫 Вы были заблокированы администратором.\n\nПричина: {reason}\n\n⚠️ Нарушение нельзя оспорить")).as_kwargs())

            return  # Тихий игнор
    
    # Записываем действие и проверяем авто-модерацию (только для не-админов)
    # Для текстовых сообщений определяем тип: команда или обычное сообщение
    if not is_admin(user_id):
        from syym import record_user_action, check_and_auto_ban
        # Определяем тип действия: команда или обычное сообщение
        if text.startswith('/'):
            action_type = "command"
        else:
            action_type = "callback"  # Обычные сообщения считаем как callback
        record_user_action(user_id, action_type)
        
        if await check_and_auto_ban(user_id, bot=bot, action_type=action_type):
            return  # Тихий игнор
    
    # Проверяем режим техобслуживания для не-админов
    if maintenance_mode and not is_admin(user_id):
        return
    
    # Обработка промокодов (только для админов)
    if is_admin(user_id) and promocode_waiting:
        if promocode_waiting == "create_promocode_name":
            global promocode_name_waiting
            promocode_name = text.strip().upper()
            if not promocode_name or len(promocode_name) < 3:
                await message.answer("❌ Имя промокода должно содержать минимум 3 символа", parse_mode="html")
                return
            
            # Проверяем, не существует ли уже такой промокод
            promocodes = load_promocodes()
            if promocode_name in promocodes:
                await message.answer("❌ Промокод с таким именем уже существует", parse_mode="html")
                return
            
            # Сохраняем имя и запрашиваем количество использований
            promocode_name_waiting = promocode_name
            promocode_waiting = "create_promocode_max_uses"
            
            await message.answer(
                f"✅ Имя промокода: <b>{promocode_name}</b>\n\n"
                f"Отправьте количество использований:\n"
                f"• Число (например: <code>10</code>) - ограниченное количество\n"
                f"• <code>0</code> или <code>безлимит</code> - без ограничений",
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_promocodes")]])
            )
            return
        
        elif promocode_waiting == "create_promocode_max_uses":
            max_uses = -1  # По умолчанию безлимит
            
            text_lower = text.strip().lower()
            if text_lower in ["0", "безлимит", "бесконечно", "unlimited"]:
                max_uses = -1
            else:
                try:
                    max_uses = int(text.strip())
                    if max_uses < 1:
                        await message.answer("❌ Количество использований должно быть больше 0 или 0/безлимит для неограниченного использования", parse_mode="html")
                        return
                except ValueError:
                    await message.answer("❌ Введите число или '0'/'безлимит' для неограниченного использования", parse_mode="html")
                    return
            
            # Создаем промокод
            success, ref_url, info_msg = await create_promocode_async(promocode_name_waiting, promocode_reward_waiting, max_uses)
            
            if success:
                # Парсим информацию из сообщения
                lines = info_msg.split('\n')
                promocode_line = lines[0]  # "Новый промокод: PROMO2024"
                uses_line = lines[1]  # "Использования: 0"
                reward_line = lines[2]  # "Награда: Вайт лист"
                
                max_uses_text = "нет" if max_uses == -1 else str(max_uses)
                
                await message.answer(**BlockQuote(Bold(
                f"🎉 Промокод создан!\n\n"
                f"├ {promocode_line}\n"
                f"├ {uses_line}\n"
                f"├ Активации: {max_uses_text}\n"
                f"└ {reward_line}\n\n"
                f"🔗 Активировать промокод\n{ref_url}"
                                        )).as_kwargs())

                write_log(f"Админ {user_id} создал промокод {promocode_name_waiting} с наградой {promocode_reward_waiting} и макс. использований {max_uses_text}")
            else:
                await message.answer(f"❌ {info_msg}", parse_mode="html")
            
            promocode_waiting = ""
            promocode_reward_waiting = ""
            promocode_name_waiting = ""
            return
        
        elif promocode_waiting == "delete_promocode":
            promocode_name = text.strip().upper()
            success, msg = delete_promocode(promocode_name)
            
            if success:
                await message.answer(f"✅ {msg}", parse_mode="html")
                write_log(f"Админ {user_id} удалил промокод {promocode_name}")
            else:
                await message.answer(f"❌ {msg}", parse_mode="html")
            
            promocode_waiting = ""
            return
        
        elif promocode_waiting == "check_promocode":
            promocode_name = text.strip().upper()
            info = get_promocode_info(promocode_name)
            
            if info:
                # Получаем username бота для формирования ссылки
                try:
                    bot_info = await bot.get_me()
                    bot_username = bot_info.username
                except:
                    bot_username = "your_bot"
                
                ref_url = f"https://t.me/{bot_username}?start=ref_{info['ref']}"
                max_uses_text = "Безлимит" if info['max_uses'] == -1 else str(info['max_uses'])
                active_text = "✅ Активен" if info['active'] else "❌ Неактивен"
                
                await message.answer(
                    f"🔍 <b>Информация о промокоде</b>\n\n"
                    f"Промокод: <code>{info['name']}</code>\n"
                    f"Награда: <b>{info['reward']}</b>\n"
                    f"Статус: {active_text}\n"
                    f"Использования: {info['uses']} / {max_uses_text}\n\n"
                    f"🔗 Реф ссылка:\n<code>{ref_url}</code>",
                    parse_mode="html"
                )
                write_log(f"Админ {user_id} проверил промокод {promocode_name}")
            else:
                await message.answer(f"❌ Промокод <code>{promocode_name}</code> не найден", parse_mode="html")
            
            promocode_waiting = ""
            return
    
    if method_waiting == "freeze":
        # Проверяем бан перед обработкой метода
        if not is_admin(user_id):
            if await check_ban_and_notify(user_id, bot=bot, message=message):
                method_waiting = ""  # Сбрасываем флаг
                return
        
        # Парсим username
        username = text.strip()
        if not username:
            await message.answer("❌ <b>Ошибка!</b>\n\nОтправьте username пользователя.\n\nПример: <code>@username</code> или <code>username</code>", parse_mode="html")
            return
        
        # Убираем @ если есть
        if username.startswith("@"):
            username = username[1:]
        
        method = method_waiting
        method_waiting = ""  # Сбрасываем флаг
        
        # Ищем .session файлы в текущей директории
        import glob
        session_files = glob.glob("*.session")
        if not session_files:
            # Пробуем в папке sessions
            session_files = glob.glob("sessions/*.session")
        
        if not session_files:
            await message.answer(
                "❌ <b>Ошибка!</b>\n\nНе найден .session файл для подключения к Telegram.\n\nПоместите .session файл в папку с ботом.",
                parse_mode="html",
                reply_markup=back_keyboard
            )
            write_log(f"Пользователь {user_id} попытался использовать freeze, но не найден .session файл")
            return
        
        # Используем первый найденный .session файл
        session_path = session_files[0]
        
        # Показываем прогресс
        progress_msg = await message.answer("📱<b> Проверяю активные сессии.</b>",parse_mode="HTML")
        
        
        try:
            # Импортируем freezer модуль
            from freezer import global_ban_by_username
            
            await progress_msg.edit_text("📱<b> Выполняю method..</b>",parse_mode="HTML")
            
            # Выполняем глобальный бан
            result = await global_ban_by_username(session_path, username, reason="Freezer")
            
            await progress_msg.edit_text("📱<b> Почти готово...</b>",parse_mode="HTML")
            
            if result["success"]:
                user = result["user"]
                if user:
                    if hasattr(user, "first_name"):
                        user_name = f"{user.first_name}"
                        if hasattr(user, "last_name") and user.last_name:
                            user_name += f" {user.last_name}"
                        user_name += f" (@{username})"
                
                successful = result["successful_bans"]
                total = result["total_chats"]
                
                success_text = (
                    f"❄️ <b>Письмо доставлено</b>\n"
                    f"<b>└─📂 Письмо: ❄️ Freezer (<code>{user_name}</code>)</b>\n\n"
                    f"<b>🟢 Успешно отправлено: {successful}</b>\n"
                )
                
                frlog(f"Пользователь {user_id} использовал freeze для @{username}: успешно {successful}/{total}")
                await progress_msg.edit_text(success_text, parse_mode="html")
                write_log(f"Пользователь {user_id} использовал freeze для @{username}: успешно {successful}/{total}")
            else:
                error_msg = result.get("error", "Неизвестная ошибка")
                await progress_msg.edit_text(
                    f"❌ <b>Ошибка!</b>\n\n{error_msg}",
                    parse_mode="html",
                    reply_markup=back_keyboard
                )
                write_log(f"Ошибка при freeze для @{username}: {error_msg}")
                
        except ImportError:
            await progress_msg.edit_text(
                "❌ <b>Ошибка!</b>\n\nМодуль freezer не найден. Установите telethon: pip install telethon",
                parse_mode="html",
                reply_markup=back_keyboard
            )
            write_log(f"Ошибка: модуль freezer не найден")
        except Exception as e:
            await progress_msg.edit_text(
                f"❌ <b>Ошибка!</b>\n\n{str(e)}",
                parse_mode="html",
                reply_markup=back_keyboard
            )
            write_log(f"Ошибка при freeze: {e}")
        
        return
    
    if is_admin(user_id):
        # Если ожидается какое-то админское действие
        if admin_action_waiting == "ban_reason":
            # Обработка причины бана
            if ban_target_id is None:
                await message.answer("❌ Ошибка: ID пользователя не найден. Начните заново.")
                admin_action_waiting = ""
                ban_target_id = None
                return
            
            reason = text.strip()
            if not reason:
                await message.answer("❌ Причина бана не может быть пустой. Отправьте причину.")
                return
            
            success = update_ban_status(ban_target_id, True, reason)
            if success:
                await message.answer(f"🚫 Пользователь {ban_target_id} забанен\n\nПричина: {reason}")
                tg_log(f"Админ {user_id} забанил пользователя {ban_target_id}, причина: {reason}")
                write_log(f"Админ {user_id} забанил пользователя {ban_target_id}, причина: {reason}")
                
                # Отправляем сообщение забаненному пользователю сразу (ручной бан)
                try:
                    ban_message = f"🚫 Вы забанены.\n\nПричина: {reason}\n\n⚠️ Нарушение нельзя оспорить"
                    await bot.send_message(ban_target_id, **BlockQuote(Bold(f"🚫 Администратор заблокировал вас навсегда.\n\nℹ️ Причина: {reason}\n\n⚠️ Данное нарушение нельзя оспорить")).as_kwargs())
                    mark_ban_notified(ban_target_id)
                    write_log(f"Отправлено сообщение о бане пользователю {ban_target_id}")
                except Exception as e:
                    write_log(f"Ошибка при отправке сообщения о бане пользователю {ban_target_id}: {e}")
                    
            else:
                await message.answer(f"❌ Ошибка при бане пользователя {ban_target_id}")
            
            admin_action_waiting = ""
            ban_target_id = None
            return
        
        if admin_action_waiting:
            target_id = parse_user_id(text)
            if target_id is None:
                await message.answer("❌ <b>Ошибка!</b>\n\nНеверный формат ID. Отправьте числовой ID пользователя.\n\nПример: <code>123456789</code>", parse_mode="html")
                write_log(f"Админ {user_id} отправил невалидный ID: {text}")
                return
            
            # target_id уже является int
            action = admin_action_waiting  # Сохраняем текущее действие
            admin_action_waiting = ""  # Сбрасываем флаг
            write_log(f"Обработка действия '{action}' для пользователя {target_id} от админа {user_id}")
            
            if action == "give_sub":
                # Сохраняем target_id и запрашиваем количество дней
                subscription_target_id = target_id
                admin_action_waiting = "give_sub_days"
                await message.answer(
                    f"🎁 <b>Выдача подписки пользователю {target_id}</b>\n\n"
                    f"Отправьте количество дней для подписки:\n"
                    f"• Число (например: <code>7</code>) - подписка на N дней\n"
                    f"• <code>-1</code> или <code>навсегда</code> - подписка навсегда",
                    parse_mode="html"
                )
                return
            elif action == "give_sub_days":
                # Обрабатываем количество дней
                if subscription_target_id is None:
                    await message.answer("❌ Ошибка: ID пользователя не найден. Начните заново.", parse_mode="html")
                    admin_action_waiting = ""
                    subscription_target_id = None
                    return
                
                days = -1  # По умолчанию навсегда
                
                text_lower = text.strip().lower()
                if text_lower in ["-1", "навсегда", "forever", "бесконечно"]:
                    days = -1
                else:
                    try:
                        days = int(text.strip())
                        if days < 1:
                            await message.answer("❌ Количество дней должно быть больше 0 или -1/навсегда для бессрочной подписки", parse_mode="html")
                            admin_action_waiting = "give_sub_days"  # Оставляем ожидание
                            return
                    except ValueError:
                        await message.answer("❌ Введите число или '-1'/'навсегда' для бессрочной подписки", parse_mode="html")
                        admin_action_waiting = "give_sub_days"  # Оставляем ожидание
                        return
                
                success = database.give_subscription(subscription_target_id, days=days)
                if success:
                    days_text = "навсегда" if days == -1 else f"{days} дней"
                    await message.answer(f"✅ Пользователю {subscription_target_id} выдана подписка на {days_text}")
                    write_log(f"Админ {user_id} выдал подписку пользователю {subscription_target_id} на {days_text}")
                    tg_log(f"Админ {user_id} выдал подписку пользователю {subscription_target_id} на {days_text}")
                else:
                    await message.answer(f"❌ Ошибка при выдаче подписки пользователю {subscription_target_id}")
                
                admin_action_waiting = ""
                subscription_target_id = None
                return
            elif action == "revoke_sub":
                success = database.revoke_subscription(target_id)
                if success:
                    await message.answer(f"✅ У пользователя {target_id} отозвана подписка")
                    write_log(f"Админ {user_id} отозвал подписку у пользователя {target_id}")
                    tg_log(f"Админ {user_id} отозвал подписку у пользователя {target_id}")
                else:
                    await message.answer(f"❌ Ошибка при отзыве подписки у пользователя {target_id}")
                return
            elif action == "add_admin":
                success = add_admin(target_id)
                if success:
                    await message.answer(f"✅ Пользователь {target_id} добавлен как админ")
                    write_log(f"Админ {user_id} добавил нового админа {target_id}")
                    tg_log(f"Админ {user_id} добавил нового админа {target_id}")
                else:
                    await message.answer(f"❌ Ошибка: пользователь {target_id} уже является админом или произошла ошибка")
                return
            elif action == "remove_admin":
                success = remove_admin(target_id)
                if success:
                    await message.answer(f"✅ Пользователь {target_id} удален из админов")
                    write_log(f"Админ {user_id} удалил админа {target_id}")
                    tg_log(f"Админ {user_id} добавил нового админа {target_id}")
                else:
                    await message.answer(f"❌ Ошибка: пользователь {target_id} не является админом или произошла ошибка")
                return
            elif action == "check_sub":
                # Проверяем статус подписки (автоматически проверяет истекшие)
                has_sub = get_subscription_status(target_id)
                expires = database.get_subscription_expires(target_id)
                
                if has_sub:
                    if expires == -1:
                        sub_text = "✅ активна (навсегда)"
                    else:
                        from datetime import datetime
                        expires_dt = datetime.fromtimestamp(expires)
                        expires_str = expires_dt.strftime("%Y-%m-%d %H:%M:%S")
                        sub_text = f"✅ активна до {expires_str}"
                else:
                    sub_text = "❌ не активна"
                
                await message.answer(
                    f"🔍 <b>Проверка подписки пользователя {target_id}</b>\n\n"
                    f"Подписка: {sub_text}",
                    parse_mode="html"
                )
                write_log(f"Админ {user_id} проверил подписку пользователя {target_id}")
                return
            elif action == "check_ban":
                # Проверяем статус бана
                is_ban = is_banned(target_id)
                ban_text = "🚫 забанен" if is_ban else "✅ не забанен"
                await message.answer(
                    f"🔍 <b>Проверка бана пользователя {target_id}</b>\n\n"
                    f"Статус: {ban_text}",
                    parse_mode="html"
                )
                write_log(f"Админ {user_id} проверил бан пользователя {target_id}")
                return
            elif action == "check_admin":
                # Проверяем статус админа
                is_adm = is_admin(target_id)
                admin_text = "👑 является админом" if is_adm else "👤 не является админом"
                await message.answer(
                    f"🔍 <b>Проверка админа {target_id}</b>\n\n"
                    f"Статус: {admin_text}",
                    parse_mode="html"
                )
                write_log(f"Админ {user_id} проверил статус админа для пользователя {target_id}")
                return
            elif action == "whitelist_add":
                # Просто добавляем в белый список без анимации
                if is_whitelisted(target_id):
                    await message.answer("❌ Пользователь уже находится в белом списке!", parse_mode="html")
                    write_log(f"Админ {user_id} попытался добавить {target_id} в белый список, но он уже там")
                else:
                    success = add_to_whitelist(target_id)
                    if success:
                        await message.answer(**BlockQuote(Bold(f"📄 Пользователь {target_id} успешно добавлен в белый список!")).as_kwargs())
                        write_log(f"Админ {user_id} добавил {target_id} в белый список")
                        tg_log(f"Админ {user_id} добавил пользователя {target_id} в белый список")
                    else:
                        await message.answer(**BlockQuote(Bold("❌ Ошибка при добавлении пользователя в белый список")).as_kwargs())
                        write_log(f"Ошибка при добавлении {target_id} в белый список")
                return
            elif action == "whitelist_remove":
                # Удаляем из белого списка
                success = remove_from_whitelist(target_id)
                if success:
                    await message.answer(f"✅ Пользователь {target_id} удален из белого списка")
                    tg_log(f"Админ {user_id} удалил пользователя {target_id} из белого списка")
                    write_log(f"Админ {user_id} удалил {target_id} из белого списка")
                else:
                    await message.answer(f"❌ Ошибка: пользователь {target_id} не найден в белом списке")
                    write_log(f"Админ {user_id} пытался удалить {target_id} из белого списка, но его там нет")
                return
            elif action == "whitelist_check":
                # Проверяем статус белого списка
                is_white = is_whitelisted(target_id)
                white_text = "✅ находится в белом списке" if is_white else "❌ не находится в белом списке"
                await message.answer(
                    f"🔍 <b>Проверка белого списка для пользователя {target_id}</b>\n\n"
                    f"Статус: {white_text}",
                    parse_mode="html"
                )
                write_log(f"Админ {user_id} проверил белый список для пользователя {target_id}")
                return
            elif action == "ban":
                # Сохраняем ID и запрашиваем причину
                ban_target_id = target_id
                admin_action_waiting = "ban_reason"
                await message.answer(
                    f"🚫 <b>Забанить пользователя {target_id}</b>\n\n"
                    f"Отправьте причину бана.\n"
                    f"Например: Нарушение правил, Спам, и т.д.",
                    parse_mode="html"
                )
                return
            elif action == "ban_reason":
                # Баним пользователя с причиной
                if ban_target_id is None:
                    await message.answer("❌ Ошибка: ID пользователя не найден. Начните заново.")
                    admin_action_waiting = ""
                    ban_target_id = None
                    return
                
                reason = text.strip()
                if not reason:
                    await message.answer("❌ Причина бана не может быть пустой. Отправьте причину.")
                    return
                
                success = update_ban_status(ban_target_id, True, reason)
                if success:
                    await message.answer(f"🚫 Пользователь {ban_target_id} забанен\n\nПричина: {reason}")
                    write_log(f"Админ {user_id} забанил пользователя {ban_target_id}, причина: {reason}")
                    tg_log(f"Админ {user_id} забанил пользователя {ban_target_id}, причина: {reason}")
                    
                    # Отправляем сообщение забаненному пользователю сразу
                    try:
                        ban_message = f"🚫 Вы забанены.\n\nПричина: {reason}"
                        await bot.send_message(ban_target_id, ban_message)
                        mark_ban_notified(ban_target_id)
                        write_log(f"Отправлено сообщение о бане пользователю {ban_target_id}")
                    except Exception as e:
                        write_log(f"Ошибка при отправке сообщения о бане пользователю {ban_target_id}: {e}")
                else:
                    await message.answer(f"❌ Ошибка при бане пользователя {ban_target_id}")
                
                admin_action_waiting = ""
                ban_target_id = None
                return
            elif action == "unban":
                # Разбаниваем пользователя
                success = update_ban_status(target_id, False, None)
                if success:
                    await message.answer(f"✅ Пользователь {target_id} разбанен")
                    write_log(f"Админ {user_id} разбанил пользователя {target_id}")
                    tg_log(f"Админ {user_id} разбанил пользователя {target_id}")
                else:
                    await message.answer(f"❌ Ошибка при разбане пользователя {target_id}")
                return
        
        # Обработка рассылки (только если ожидается сообщение для рассылки)
        if broadcast_waiting and parse_user_id(text) is None and not text.startswith('/') and len(text.strip()) > 0:
            write_log(f"Админ {user_id} начал рассылку: {text[:50]}...")
            
            # Сбрасываем состояние ожидания рассылки
            broadcast_waiting = False
            
            # Получаем всех пользователей из базы данных (забаненные уже исключены)
            user_ids = database.get_all_users_for_broadcast()
            
            if not user_ids:
                await message.answer("❌ Нет пользователей для рассылки")
                return
            
            sent_count = 0
            error_count = 0
            
            await message.answer("📢 Начинаю рассылку...")
            
            for user_id_from_file in user_ids:
                # Получаем информацию о пользователе для подстановки переменных
                try:
                    user_chat = await bot.get_chat(user_id_from_file)
                    user_name = user_chat.first_name or ""
                    if user_chat.last_name:
                        user_name += " " + user_chat.last_name
                    user_username = user_chat.username or ""
                    if user_username:
                        user_username = "@" + user_username
                except:
                    user_name = "Пользователь"
                    user_username = ""
                
                # Подставляем переменные {user} и {user_us}
                message_text = text.replace("{user}", user_name)
                message_text = message_text.replace("{user_us}", user_username)
                
                try:
                    # Пробуем отправить через Crypto Bot API, если доступен
                    if CRYPTO_BOT_AVAILABLE and crypto_bot.CRYPTO_BOT_TOKEN:
                        success = await crypto_bot.send_message_safe(
                            user_id_from_file,
                            message_text,
                            parse_mode="MarkdownV2"
                        )
                        if success:
                            sent_count += 1
                        else:
                            # Fallback на обычный бот
                            raise Exception("Crypto Bot failed, using fallback")
                    else:
                        raise Exception("Crypto Bot not available, using fallback")
                except Exception as e:
                    try:
                        # Fallback: используем обычный Telegram Bot API
                        # Сначала пробуем MarkdownV2
                        await bot.send_message(user_id_from_file, message_text, parse_mode="MarkdownV2")
                        sent_count += 1
                    except Exception as e2:
                        try:
                            # Если MarkdownV2 не работает, отправляем как обычный текст
                            await bot.send_message(user_id_from_file, message_text)
                            sent_count += 1
                            write_log(f"MarkdownV2 не сработал для {user_id_from_file}, отправлено как текст")
                        except Exception as e3:
                            error_count += 1
                            write_log(f"Ошибка отправки сообщения пользователю {user_id_from_file}: {e3}")
            
            await message.answer(
                f"📢 <b>Рассылка завершена</b>\n\n"
                f"✅ Отправлено: {sent_count}\n"
                f"❌ Ошибок: {error_count}\n\n"
                f"💡 <i>Для новой рассылки нажмите кнопку \"📢 Рассылка\" в админ-панели</i>",
                parse_mode="html"
            )
            
            write_log(f"Админ {user_id} провел рассылку: отправлено {sent_count}, ошибок {error_count}")
            tg_log(f"Админ {user_id} провел рассылку: отправлено {sent_count}, ошибок {error_count}")
            return
    
    # Обработка неизвестных команд для всех пользователей
    if message.text.startswith('/'):
        if message.chat.type != "private":
            return
         # Проверяем бан - если забанен, тихо игнорируем
        if not is_admin(user_id) and is_banned(user_id):
            return  # Тихий игнор
        if is_ban_notified(user_id):
            return
        
        await message.answer(
            "🌀 <b>Команда не найдена или не доступна Вам!</b>\n\n"
            "Для перехода в меню пропишите /start",
            parse_mode="html"
        )
        return
    
    # Обработка любых других сообщений (не команд) для всех пользователей
    if not message.text.startswith('/'):
        if message.chat.type != "private":
            return
        # Проверяем бан - если забанен, тихо игнорируем
        if not is_admin(user_id) and is_banned(user_id):
            return  # Тихий игнор
        if is_ban_notified(user_id):
            return
        
        await message.answer(
            "🌀 <b>Команда не найдена или не доступна Вам!</b>\n\n"
            "Для перехода в меню пропишите /start",
            parse_mode="html"
        )
        return

# === Фоновая задача для проверки истекших подписок ===
async def check_expired_subscriptions_task():
    """Периодически проверяет и отзывает истекшие подписки"""
    while True:
        try:
            await asyncio.sleep(3600)  # Проверяем каждый час
            revoked_count = database.check_and_revoke_expired_subscriptions()
            if revoked_count > 0:
                write_log(f"Фоновая проверка: отозвано {revoked_count} истекших подписок")
        except Exception as e:
            write_log(f"Ошибка в фоновой задаче проверки подписок: {e}")

# === Запуск ===
async def main():
    # Загружаем статус техобслуживания при запуске
    load_maintenance_status()
    if maintenance_mode:
        print("[!] Бот запущен в режиме техобслуживания")
    else:
        print("[!] Бот запущен в обычном режиме")
    
    # Загружаем статус авто-модерации при запуске
    load_auto_moderation_status()
    if is_auto_moderation_enabled():
        print("[!] Авто-модерация включена")
    else:
        print("[!] Авто-модерация выключена")
    
    # Запускаем фоновую задачу для проверки истекших подписок
    asyncio.create_task(check_expired_subscriptions_task())
    print("[!] Запущена фоновая проверка истекших подписок")
    
    # Проверяем подписки при старте
    revoked_count = database.check_and_revoke_expired_subscriptions()
    if revoked_count > 0:
        print(f"[!] При запуске отозвано {revoked_count} истекших подписок")
    
    await dp.start_polling(bot)

# === Обработчики белого списка ===
@dp.callback_query(F.data == "admin_whitelist")
async def handle_admin_whitelist(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    write_log(f"Админ {user_id} открыл меню белого списка")
    
    whitelist_text = """
📝 <b>Управление белым списком</b>

Выберите действие:

<b>➕ Добавить в белый список:</b>
• Добавляет пользователя по ID в белый список
• Пользователи в белом списке могут использовать все функции бота

<b>➖ Удалить из белого списка:</b>
• Удаляет пользователя из белого списка по ID

<b>🔍 Проверить белый список:</b>
• Проверяет, находится ли пользователь в белом списке
"""
    
    await callback.message.edit_text(
        whitelist_text,
        parse_mode="html",
        reply_markup=white_set)
    await callback.answer()

# === Добавление в белый список ===
@dp.callback_query(F.data == "whitelist_add")
async def handle_whitelist_add(callback: CallbackQuery):
    global admin_action_waiting
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    write_log(f"Админ {user_id} начал добавление в белый список")
    
    await callback.message.edit_text(
        "📝 <b>Добавление в белый список</b>\n\n"
        "Отправьте ID пользователя, которого хотите добавить в белый список\n\n"
        "Пример: <code>123456789</code>",
        parse_mode="html",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_whitelist")]
        ])
    )
    await callback.answer()
    
    # Устанавливаем состояние ожидания ID
    admin_action_waiting = "whitelist_add"

# === Удаление из белого списка ===
@dp.callback_query(F.data == "whitelist_remove")
async def handle_whitelist_remove(callback: CallbackQuery):
    global admin_action_waiting
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    write_log(f"Админ {user_id} начал удаление из белого списка")
    
    await callback.message.edit_text(
        "📝 <b>Удаление из белого списка</b>\n\n"
        "Отправьте ID пользователя, которого хотите удалить из белого списка\n\n"
        "Пример: <code>123456789</code>",
        parse_mode="html",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_whitelist")]
        ])
    )
    await callback.answer()
    
    # Устанавливаем состояние ожидания ID
    admin_action_waiting = "whitelist_remove"

# === Проверка белого списка ===
@dp.callback_query(F.data == "whitelist_check")
async def handle_whitelist_check(callback: CallbackQuery):
    global admin_action_waiting
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    write_log(f"Админ {user_id} начал проверку белого списка")
    
    await callback.message.edit_text(
        "📝 <b>Проверка белого списка</b>\n\n"
        "Отправьте ID пользователя для проверки\n\n"
        "Пример: <code>123456789</code>",
        parse_mode="html",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_whitelist")]
        ])
    )
    await callback.answer()
    
    # Устанавливаем состояние ожидания ID
    admin_action_waiting = "whitelist_check"

# === Обработчики промокодов ===

# === Меню промокодов ===
@dp.callback_query(F.data == "admin_promocodes")
async def handle_admin_promocodes(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    write_log(f"Админ {user_id} открыл меню промокодов")
    
    content = as_list(
        BlockQuote(Bold(f"🎟️ Управление промокодами")),
        "",        
        Bold("➕ Создать промокод:"),
        ("• Создает новый промокод с рандомной реф ссылкой"),
        ("• Можно выбрать награду: Вайт лист, Подписка"),
        "",
        Bold("➖ Удалить промокод:"),
        ("• Удаляет промокод по имени"),
        "",
        Bold("🔍 Проверить промокод:"),
        "• Показывает информацию о промокоде"
        )
     
    await callback.message.edit_text(**content.as_kwargs(),reply_markup=promocodes_keyboard)

    await callback.answer()

# === Создать промокод - выбор награды ===
@dp.callback_query(F.data == "promocode_create")
async def handle_promocode_create(callback: CallbackQuery):
    global promocode_waiting
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    write_log(f"Админ {user_id} начал создание промокода")
    promocode_waiting = "create_promocode_name"

    
    await callback.message.edit_text(
        "🎟️ <b>Создание промокода</b>\n\n"
        "Сначала выберите награду:",
        parse_mode="html",
        reply_markup=reward_keyboard
    )
    await callback.answer()

# === Выбор награды для промокода ===
@dp.callback_query(F.data.startswith("promocode_reward_"))
async def handle_promocode_reward_select(callback: CallbackQuery):
    global promocode_waiting, promocode_reward_waiting
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    reward = callback.data.replace("promocode_reward_", "")
    promocode_reward_waiting = reward
    promocode_waiting = "create_promocode_name"
    
    reward_text = {
        "whitelist": "Вайт лист",
        "subscription": "Подписка"
    }.get(reward, reward)
    
    await callback.message.edit_text(
        f"🎟️ <b>Создание промокода</b>\n\n"
        f"Награда: <b>{reward_text}</b>\n\n"
        f"Отправьте имя промокода (например: <code>PROMO2024</code>):",
        parse_mode="html",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_promocodes")]])
    )
    await callback.answer()

# === Удалить промокод ===
@dp.callback_query(F.data == "promocode_delete")
async def handle_promocode_delete(callback: CallbackQuery):
    global promocode_waiting
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    write_log(f"Админ {user_id} начал удаление промокода")
    promocode_waiting = "delete_promocode"
    
    content = as_list(
        BlockQuote(Bold(f"🗑️ Удаление промокода")),
           "",
        Bold("Отправьте имя промокода для удаления."),        
        Bold("Например: PROMO2025")
        )
     
    await callback.message.edit_text(**content.as_kwargs(), inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_promocodes")]])

    await callback.answer()

# === Проверить промокод ===
@dp.callback_query(F.data == "promocode_check")
async def handle_promocode_check(callback: CallbackQuery):
    global promocode_waiting
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    write_log(f"Админ {user_id} начал проверку промокода")
    promocode_waiting = "check_promocode"
    
    await callback.message.edit_text(
        "🔍 <b>Проверка промокода</b>\n\n"
        "Отправьте имя промокода для проверки.\n"
        "Например: <code>PROMO2025</code>",
        parse_mode="html",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_promocodes")]])
    )
    await callback.answer()

# === запуск бота ===
if 1 == 1:
    asyncio.run(main())