from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.formatting import *
import asyncio
import os
import time
from collections import defaultdict
from syym_cfg import *

bot = Bot(token=TOKEN)
dp = Dispatcher()

# === Админ ===
ADMIN_ID = 7832587042

# === Кастомное логирование ===
def write_log(text: str):
    time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("log.txt", "a", encoding="utf-8") as f:
        f.write(f"[{time}] {text}\n")

# === Система авто-модерации ===
# Словарь для отслеживания действий пользователей: {user_id: {"callback": [timestamps], "command": [timestamps]}}
user_actions = defaultdict(lambda: {"callback": [], "command": []})

# Настройки авто-модерации
AUTO_MODERATION_ENABLED = False
AUTO_MODERATION_MAX_ACTIONS = 10  # Максимальное количество действий
AUTO_MODERATION_TIME_WINDOW = 60  # Окно времени в секундах (60 секунд = 1 минута)

def load_auto_moderation_status():
    """Загружает статус авто-модерации из файла"""
    global AUTO_MODERATION_ENABLED
    try:
        if os.path.exists("auto_moderation.txt"):
            with open("auto_moderation.txt", "r", encoding="utf-8") as f:
                content = f.read().strip().lower()
                AUTO_MODERATION_ENABLED = content == "true"
        else:
            AUTO_MODERATION_ENABLED = False
        return AUTO_MODERATION_ENABLED
    except Exception as e:
        write_log(f"Ошибка при загрузке статуса авто-модерации: {e}")
        AUTO_MODERATION_ENABLED = False
        return False

def save_auto_moderation_status(enabled: bool):
    """Сохраняет статус авто-модерации в файл"""
    global AUTO_MODERATION_ENABLED
    try:
        AUTO_MODERATION_ENABLED = enabled
        with open("auto_moderation.txt", "w", encoding="utf-8") as f:
            f.write(str(enabled))
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
                                "👮‍♂️ Auto-ban\n\n🚫 Вы превысили лимит запросов и были заблокированы навсегда"
                            )
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



def load_admins():
    """Загружает список админов из файла"""
    admins = [ADMIN_ID]  # Главный админ всегда в списке
    if os.path.exists("admins.txt"):
        try:
            with open("admins.txt", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            admin_id = int(line)
                            if admin_id not in admins:
                                admins.append(admin_id)
                        except ValueError:
                            # Пропускаем некорректные строки
                            continue
        except Exception as e:
            write_log(f"Ошибка при загрузке админов: {e}")
    return admins

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь админом"""
    admins = load_admins()
    return user_id in admins

def add_admin(admin_id: int) -> bool:
    """Добавляет админа в файл. Возвращает True если добавлен, False если уже был"""
    if admin_id == ADMIN_ID:
        return False  # Главный админ уже есть
    
    admins = load_admins()
    if admin_id in admins:
        return False  # Уже есть
    
    try:
        with open("admins.txt", "a", encoding="utf-8") as f:
            f.write(f"{admin_id}\n")
        write_log(f"Добавлен новый админ {admin_id}")
        return True
    except Exception as e:
        write_log(f"Ошибка при добавлении админа: {e}")
        return False

def remove_admin(admin_id: int) -> bool:
    """Удаляет админа из файла. Возвращает True если удален"""
    if admin_id == ADMIN_ID:
        return False  # Главного админа нельзя удалить
    
    if not os.path.exists("admins.txt"):
        return False
    
    try:
        admins = []
        with open("admins.txt", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        line_id = int(line)
                        if line_id != admin_id:
                            admins.append(line)
                    except ValueError:
                        # Пропускаем некорректные строки
                        continue
        
        with open("admins.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(admins))
            if admins:
                f.write("\n")
        
        write_log(f"Удален админ {admin_id}")
        return True
    except Exception as e:
        write_log(f"Ошибка при удалении админа: {e}")
        return False

def clean_users_file():
    """Очищает файл users.txt от некорректных строк"""
    if not os.path.exists("users.txt"):
        return
    
    clean_lines = []
    with open("users.txt", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if ":" in line:
                parts = line.split(":")
                if len(parts) == 3:
                    try:
                        # Проверяем, что первый элемент - это число
                        int(parts[0])
                        clean_lines.append(line + "\n")
                    except ValueError:
                        write_log(f"Удалена некорректная строка: {line}")
                        continue
    
    with open("users.txt", "w", encoding="utf-8") as f:
        f.writelines(clean_lines)
    
    write_log(f"Файл users.txt очищен, осталось {len(clean_lines)} корректных записей")

# === Работа с users.txt ===
def add_user(user_id: int) -> bool:
    """Добавляет пользователя в users.txt, если его нет.
    Возвращает True, если добавлен впервые, False — если уже был."""
    if not os.path.exists("users.txt"):
        open("users.txt", "w", encoding="utf-8").close()

    with open("users.txt", "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        parts = line.strip().split(":")
        if len(parts) >= 1 and parts[0] == str(user_id):
            return False  # Уже есть

    with open("users.txt", "a", encoding="utf-8") as f:
        f.write(f"{user_id}:f:f:f\n")  # ID:подписка:бан:премиум
    write_log(f"Добавлен новый пользователь {user_id}")
    return True  # Новый пользователь

def is_banned(user_id: int) -> bool:
    """Проверяет, заблокирован ли пользователь"""
    if not os.path.exists("users.txt"):
        return False
    with open("users.txt", "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(":")
            if len(parts) >= 1 and parts[0] == str(user_id):
                # Старый формат: 3 части (ID:подписка:бан)
                if len(parts) == 3:
                    ban_value = parts[2].lower()
                    return ban_value in ["true", "t"]
                # Новый формат: 4 части (ID:подписка:бан:премиум)
                elif len(parts) == 4:
                    ban_value = parts[2].lower()
                    return ban_value in ["true", "t"]
    return False

def get_subscription_status(user_id: int) -> bool:
    """Возвращает статус подписки пользователя из users.txt"""
    if not os.path.exists("users.txt"):
        return False
    with open("users.txt", "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(":")
            if len(parts) >= 1 and parts[0] == str(user_id):
                # Старый формат: 3 части (ID:подписка:бан)
                if len(parts) == 3:
                    subscription_value = parts[1].lower()
                    return subscription_value in ["true", "t"]
                # Новый формат: 4 части (ID:подписка:бан:премиум)
                elif len(parts) == 4:
                    subscription_value = parts[1].lower()
                    return subscription_value in ["true", "t"]
    return False

def get_premium_status(user_id: int) -> bool:
    """Возвращает статус премиума пользователя из users.txt"""
    if not os.path.exists("users.txt"):
        return False
    with open("users.txt", "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(":")
            if len(parts) == 4 and parts[0] == str(user_id):
                premium_value = parts[3].lower()
                return premium_value in ["true", "t"]
    return False

def is_registered(user_id: int) -> bool:
    """Проверяет, зарегистрирован ли пользователь"""
    if not os.path.exists("users.txt"):
        return False
    with open("users.txt", "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(":")
            if len(parts) >= 1 and parts[0] == str(user_id):
                return True
    return False

def update_subscription_status(user_id: int, status: bool) -> bool:
    """Обновляет статус подписки пользователя"""
    if not os.path.exists("users.txt"):
        return False
    
    lines = []
    updated = False
    
    with open("users.txt", "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(":")
            if len(parts) >= 1 and parts[0] == str(user_id):
                new_status = "t" if status else "f"
                # Старый формат: 3 части (ID:подписка:бан)
                if len(parts) == 3:
                    lines.append(f"{parts[0]}:{new_status}:{parts[2]}\n")
                # Новый формат: 4 части (ID:подписка:бан:премиум)
                elif len(parts) == 4:
                    lines.append(f"{parts[0]}:{new_status}:{parts[2]}:{parts[3]}\n")
                updated = True
                write_log(f"Обновлен статус подписки для {user_id}: {new_status}")
            else:
                lines.append(line)
    
    if updated:
        with open("users.txt", "w", encoding="utf-8") as f:
            f.writelines(lines)
    
    return updated

def load_ban_reasons():
    """Загружает причины банов из файла"""
    if not os.path.exists("ban_reasons.json"):
        return {}
    try:
        import json
        with open("ban_reasons.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        write_log(f"Ошибка при загрузке причин банов: {e}")
        return {}

def save_ban_reasons(ban_reasons):
    """Сохраняет причины банов в файл"""
    try:
        import json
        with open("ban_reasons.json", "w", encoding="utf-8") as f:
            json.dump(ban_reasons, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        write_log(f"Ошибка при сохранении причин банов: {e}")
        return False

def get_ban_reason(user_id: int) -> str:
    """Получает причину бана пользователя"""
    ban_reasons = load_ban_reasons()
    return ban_reasons.get(str(user_id), "Не указана")

def set_ban_reason(user_id: int, reason: str):
    """Устанавливает причину бана пользователя"""
    ban_reasons = load_ban_reasons()
    ban_reasons[str(user_id)] = reason
    save_ban_reasons(ban_reasons)

def remove_ban_reason(user_id: int):
    """Удаляет причину бана пользователя"""
    ban_reasons = load_ban_reasons()
    if str(user_id) in ban_reasons:
        del ban_reasons[str(user_id)]
        save_ban_reasons(ban_reasons)

def load_ban_notified():
    """Загружает список пользователей, которым уже отправлено сообщение о бане"""
    if not os.path.exists("ban_notified.txt"):
        return set()
    try:
        with open("ban_notified.txt", "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    except Exception as e:
        write_log(f"Ошибка при загрузке списка уведомленных о бане: {e}")
        return set()

def save_ban_notified(notified_set):
    """Сохраняет список пользователей, которым уже отправлено сообщение о бане"""
    try:
        with open("ban_notified.txt", "w", encoding="utf-8") as f:
            for user_id in notified_set:
                f.write(f"{user_id}\n")
        return True
    except Exception as e:
        write_log(f"Ошибка при сохранении списка уведомленных о бане: {e}")
        return False

def is_ban_notified(user_id: int) -> bool:
    """Проверяет, было ли уже отправлено сообщение о бане пользователю"""
    notified = load_ban_notified()
    return str(user_id) in notified

def mark_ban_notified(user_id: int):
    """Отмечает, что пользователю было отправлено сообщение о бане"""
    notified = load_ban_notified()
    notified.add(str(user_id))
    save_ban_notified(notified)

def unmark_ban_notified(user_id: int):
    """Убирает отметку о том, что пользователю было отправлено сообщение о бане"""
    notified = load_ban_notified()
    notified.discard(str(user_id))
    save_ban_notified(notified)

def update_ban_status(user_id: int, status: bool, reason: str = None) -> bool:
    """Обновляет статус бана пользователя. Если status=True, reason обязателен"""
    if not os.path.exists("users.txt"):
        return False
    
    lines = []
    updated = False
    
    with open("users.txt", "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(":")
            if len(parts) >= 1 and parts[0] == str(user_id):
                # Старый формат: 3 части (ID:подписка:бан)
                if len(parts) == 3:
                    subscription = parts[1]
                    ban = "t" if status else "f"
                    lines.append(f"{user_id}:{subscription}:{ban}\n")
                # Новый формат: 4 части (ID:подписка:бан:премиум)
                elif len(parts) == 4:
                    subscription = parts[1]
                    premium = parts[3]
                    ban = "t" if status else "f"
                    lines.append(f"{user_id}:{subscription}:{ban}:{premium}\n")
                updated = True
            else:
                lines.append(line)
    
    if not updated:
        # Если пользователя нет в файле, добавляем его
        with open("users.txt", "a", encoding="utf-8") as f:
            f.write(f"{user_id}:f:t:f\n")  # ID:подписка:бан:премиум
        updated = True
    
    if updated:
        with open("users.txt", "w", encoding="utf-8") as f:
            f.writelines(lines)
        
        # Сохраняем или удаляем причину бана
        if status:
            if reason:
                set_ban_reason(user_id, reason)
                unmark_ban_notified(user_id)  # Сбрасываем флаг уведомления при новом бане
            else:
                write_log(f"Предупреждение: бан пользователя {user_id} без указания причины")
        else:
            remove_ban_reason(user_id)
            unmark_ban_notified(user_id)
    
    return updated

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
            # Автоматический бан - добавляем кнопку "Оспорить нарушение"
            await message.answer(**BlockQuote(Bold("👮‍♂️ Auto-ban\n\n🚫 Вы превысили лимит запросов и были заблокированы навсегда")).as_kwargs(),reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⚡️ Оспорить нарушение", url="https://t.me/unsedb")]]))

        else:
            await message.answer(**BlockQuote(Bold(f"🚫 Вы были заблокированы администратором.\n\nПричина: {reason}\n\n⚠️ Нарушение нельзя оспорить")).as_kwargs())

            mark_ban_notified(user_id)
            write_log(f"Отправлено сообщение о бане пользователю {user_id}, причина: {reason}")
    return True

def is_whitelisted(user_id: int) -> bool:
    """Проверяет, находится ли пользователь в белом списке"""
    if not os.path.exists("whitelist.txt"):
        return False
    with open("whitelist.txt", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip() == str(user_id):
                return True
    return False

def add_to_whitelist(user_id: int) -> bool:
    """Добавляет пользователя в белый список"""
    try:
        # Проверяем, есть ли уже пользователь в белом списке
        if is_whitelisted(user_id):
            return False  # Уже в белом списке
        
        # Добавляем в белый список
        with open("whitelist.txt", "a", encoding="utf-8") as f:
            f.write(f"{user_id}\n")
        
        write_log(f"Пользователь {user_id} добавлен в белый список")
        return True
    except Exception as e:
        write_log(f"Ошибка при добавлении в белый список: {e}")
        return False

def remove_from_whitelist(user_id: int) -> bool:
    """Удаляет пользователя из белого списка"""
    if not os.path.exists("whitelist.txt"):
        return False
    
    lines = []
    removed = False
    
    with open("whitelist.txt", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip() != str(user_id):
                lines.append(line)
            else:
                removed = True
    
    if removed:
        with open("whitelist.txt", "w", encoding="utf-8") as f:
            f.writelines(lines)
        write_log(f"Пользователь {user_id} удален из белого списка")
    
    return removed

def update_premium_status(user_id: int, status: bool) -> bool:
    """Обновляет статус премиума пользователя"""
    if not os.path.exists("users.txt"):
        return False
    
    lines = []
    updated = False
    
    with open("users.txt", "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(":")
            if len(parts) >= 1 and parts[0] == str(user_id):
                new_status = "t" if status else "f"
                # Старый формат: 3 части - конвертируем в новый
                if len(parts) == 3:
                    lines.append(f"{parts[0]}:{parts[1]}:{parts[2]}:{new_status}\n")
                # Новый формат: 4 части
                elif len(parts) == 4:
                    lines.append(f"{parts[0]}:{parts[1]}:{parts[2]}:{new_status}\n")
                updated = True
                write_log(f"Обновлен статус премиума для {user_id}: {new_status}")
            else:
                lines.append(line)
    
    if updated:
        with open("users.txt", "w", encoding="utf-8") as f:
            f.writelines(lines)
    
    return updated

# === Тестовая команда ===
@dp.message(Command("test"))
async def test_command(message: Message):
    await message.answer("✅ Команды работают!")

# === Команда для проверки ID ===
@dp.message(Command("myid"))
async def my_id_command(message: Message):
    user_id = message.from_user.id
    await message.answer(f"Ваш ID: {user_id}")

# === Команда для очистки файла пользователей ===
@dp.message(Command("clean"))
async def clean_users_command(message: Message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("❌ Доступ запрещен")
        return
    
    write_log(f"Админ {user_id} запросил очистку файла пользователей")
    
    try:
        clean_users_file()
        await message.answer("✅ Файл users.txt очищен от некорректных строк")
    except Exception as e:
        await message.answer(f"❌ Ошибка при очистке: {e}")
        write_log(f"Ошибка при очистке файла: {e}")

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
    
    # Выдаем подписку
    success = update_subscription_status(user_id, True)
    
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
    success = update_subscription_status(user_id, False)
    
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