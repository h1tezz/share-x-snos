from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.filters import Command
import asyncio
import os
import sys
from syym_cfg import admin_keyboard, TOKEN

bot = Bot(token=TOKEN)
dp = Dispatcher()

# === Админ ===
ADMIN_ID = 8428752149

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь админом"""
    return user_id == ADMIN_ID

# === Кастомное логирование ===
def write_log(text: str):
    time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("log.txt", "a", encoding="utf-8") as f:
        f.write(f"[{time}] {text}\n")

# === Работа с users.txt ===
def is_banned(user_id: int) -> bool:
    """Проверяет, заблокирован ли пользователь"""
    if not os.path.exists("users.txt"):
        return False
    with open("users.txt", "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(":")
            if len(parts) == 3 and parts[0] == str(user_id):
                ban_value = parts[2].lower()
                # Поддерживаем и старые (true/false) и новые (t/f) значения
                return ban_value in ["true", "t"]
    return False

def get_subscription_status(user_id: int) -> bool:
    """Возвращает статус подписки пользователя из users.txt"""
    if not os.path.exists("users.txt"):
        return False
    with open("users.txt", "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(":")
            if len(parts) == 3 and parts[0] == str(user_id):
                subscription_value = parts[1].lower()
                # Поддерживаем и старые (true/false) и новые (t/f) значения
                return subscription_value in ["true", "t"]
    return False

def update_ban_status(user_id: int, status: bool) -> bool:
    """Обновляет статус бана пользователя"""
    if not os.path.exists("users.txt"):
        return False
    
    lines = []
    updated = False
    
    with open("users.txt", "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(":")
            if len(parts) == 3 and parts[0] == str(user_id):
                # Обновляем статус бана, сохраняем остальные значения
                new_status = "t" if status else "f"
                lines.append(f"{parts[0]}:{parts[1]}:{new_status}\n")
                updated = True
                write_log(f"Обновлен статус бана для {user_id}: {new_status}")
            else:
                lines.append(line)
    
    if updated:
        with open("users.txt", "w", encoding="utf-8") as f:
            f.writelines(lines)
    
    return updated

# === Админ команда /ad ===
@dp.message(Command("ad"))
async def admin_panel(message: Message):
    user_id = message.from_user.id
    
    write_log(f"Получена команда /ad от пользователя {user_id}")
    
    if not is_admin(user_id):
        write_log(f"Пользователь {user_id} попытался получить доступ к админ-панели")
        await message.answer("❌ Доступ запрещен")
        return
    
    write_log(f"Админ {user_id} открыл админ-панель")
    
    try:
        await message.answer(
            "🔧 <b>Админ-панель</b>\n\n"
            "Выберите действие:",
            parse_mode="html",
            reply_markup=admin_keyboard
        )
        write_log(f"Админ-панель успешно отправлена админу {user_id}")
    except Exception as e:
        write_log(f"Ошибка при отправке админ-панели: {e}")
        await message.answer(f"❌ Ошибка: {e}")

# === Админ обработчики ===

# === Рассылка ===
@dp.callback_query(F.data == "admin_broadcast")
async def handle_admin_broadcast(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    write_log(f"Админ {user_id} запросил рассылку")
    
    await callback.message.edit_text(
        "📢 <b>Рассылка</b>\n\n"
        "Отправьте сообщение, которое нужно разослать всем пользователям.\n"
        "Используйте MarkdownV2 разметку для форматирования.\n\n"
        "<i>Пример: *жирный текст*, _курсив_, `код`</i>",
        parse_mode="html",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]])
    )
    await callback.answer()

# === Бан ===
@dp.callback_query(F.data == "admin_ban")
async def handle_admin_ban(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    write_log(f"Админ {user_id} запросил бан пользователя")
    
    await callback.message.edit_text(
        "🚫 <b>Забанить пользователя</b>\n\n"
        "Отправьте ID пользователя для бана.\n"
        "Например: 123456789",
        parse_mode="html",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]])
    )
    await callback.answer()

# === Разбан ===
@dp.callback_query(F.data == "admin_unban")
async def handle_admin_unban(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    write_log(f"Админ {user_id} запросил разбан пользователя")
    
    await callback.message.edit_text(
        "✅ <b>Разбанить пользователя</b>\n\n"
        "Отправьте ID пользователя для разбана.\n"
        "Например: 123456789",
        parse_mode="html",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]])
    )
    await callback.answer()

# === Проверить бан ===
@dp.callback_query(F.data == "admin_check_ban")
async def handle_admin_check_ban(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    write_log(f"Админ {user_id} запросил проверку бана пользователя")
    
    await callback.message.edit_text(
        "🔍 <b>Проверить бан пользователя</b>\n\n"
        "Отправьте ID пользователя для проверки статуса бана.\n"
        "Например: 123456789",
        parse_mode="html",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]])
    )
    await callback.answer()

# === Перезагрузка ===
@dp.callback_query(F.data == "admin_restart")
async def handle_admin_restart(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    write_log(f"Админ {user_id} перезагрузил бота")
    
    await callback.answer("🔄 Бот перезагружается...", show_alert=True)
    
    # Перезагрузка бота
    os.execv(sys.executable, [sys.executable] + sys.argv)

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
• Поддерживает MarkdownV2 разметку: *жирный*, _курсив_, `код`
• Забаненные пользователи автоматически пропускаются

<b>🚫 Забанить / ✅ Разбанить:</b>
• Нажмите кнопку → отправьте ID пользователя
• Пример ID: 123456789
• Показывает полную информацию о пользователе

<b>🔍 Проверить бан:</b>
• Отправьте ID пользователя для проверки статуса
• Показывает: статус бана и подписки

<b>🔄 Перезагрузка:</b>
• Перезапускает бота
• Все настройки сохраняются

<b>📋 Команды:</b>
• /ad - открыть админ-панель
• /clean - очистить файл пользователей от некорректных строк
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
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]])
    )
    await callback.answer()

# === Назад в админ-панель ===
@dp.callback_query(F.data == "admin_back")
async def handle_admin_back(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔧 <b>Админ-панель</b>\n\n"
        "Выберите действие:",
        parse_mode="html",
        reply_markup=admin_keyboard
    )
    await callback.answer()

# === Обработка текстовых команд админа ===
@dp.message(F.text)
async def handle_admin_commands(message: Message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        return  # Игнорируем не-админов
    
    # Пропускаем команды
    if message.text.startswith('/'):
        return
    
    text = message.text
    
    # Функция для парсинга ID
    def parse_user_id(text):
        """Парсит ID пользователя из текста. Возвращает int или None если невалидный"""
        if not text:
            return None
        try:
            user_id = int(text.strip())
            return user_id
        except (ValueError, AttributeError):
            return None
    
    # Обработка ID для бана/разбана
    target_id = parse_user_id(text)
    if target_id is not None:
        
        # Проверяем, забанен ли пользователь
        if is_banned(target_id):
            # Разбаниваем
            success = update_ban_status(target_id, False)
            if success:
                await message.answer(f"✅ Пользователь {target_id} разбанен")
                write_log(f"Админ {user_id} разбанил пользователя {target_id}")
            else:
                await message.answer(f"❌ Ошибка при разбане пользователя {target_id}")
        else:
            # Баним
            success = update_ban_status(target_id, True)
            if success:
                await message.answer(f"🚫 Пользователь {target_id} забанен")
                write_log(f"Админ {user_id} забанил пользователя {target_id}")
            else:
                await message.answer(f"❌ Ошибка при бане пользователя {target_id}")
        return
    
    # Обработка рассылки (любое сообщение от админа, кроме команд и ID)
    if parse_user_id(text) is None and not text.startswith('/') and len(text.strip()) > 0:
        write_log(f"Админ {user_id} начал рассылку: {text[:50]}...")
        
        # Получаем всех пользователей
        if not os.path.exists("users.txt"):
            await message.answer("❌ Файл пользователей не найден")
            return
        
        with open("users.txt", "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        if not lines:
            await message.answer("❌ Нет пользователей для рассылки")
            return
        
        sent_count = 0
        error_count = 0
        banned_count = 0
        
        await message.answer("📢 Начинаю рассылку...")
        
        for line in lines:
            if ":" in line:
                try:
                    user_id_from_file = int(line.split(":")[0])
                except ValueError:
                    # Пропускаем строки, которые не содержат числовой ID
                    write_log(f"Пропущена некорректная строка в users.txt: {line.strip()}")
                    continue
                
                # Пропускаем забаненных пользователей
                if is_banned(user_id_from_file):
                    banned_count += 1
                    continue
                
                try:
                    # Сначала пробуем MarkdownV2
                    await bot.send_message(user_id_from_file, text, parse_mode="MarkdownV2")
                    sent_count += 1
                except Exception as e:
                    try:
                        # Если MarkdownV2 не работает, отправляем как обычный текст
                        await bot.send_message(user_id_from_file, text)
                        sent_count += 1
                        write_log(f"MarkdownV2 не сработал для {user_id_from_file}, отправлено как текст")
                    except Exception as e2:
                        error_count += 1
                        write_log(f"Ошибка отправки сообщения пользователю {user_id_from_file}: {e2}")
        
        await message.answer(
            f"📢 <b>Рассылка завершена</b>\n\n"
            f"✅ Отправлено: {sent_count}\n"
            f"❌ Ошибок: {error_count}\n"
            f"🚫 Забаненных пропущено: {banned_count}",
            parse_mode="html"
        )
        
        write_log(f"Админ {user_id} провел рассылку: отправлено {sent_count}, ошибок {error_count}, забаненных {banned_count}")

# === Запуск ===
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    print("[!] Админ панель запущена")
    asyncio.run(main())