"""
Модуль для глобального бана пользователей через Telethon
Адаптирован из glban.py для работы с aiogram ботом
"""
import asyncio
import os
import time
from typing import Optional, List, Dict
from telethon import TelegramClient
from telethon.tl import functions
from telethon.tl.types import Channel, Chat, User
from telethon.errors import FloodWaitError, ChatAdminRequiredError, UserAdminInvalidError

BANNED_RIGHTS = {
    "view_messages": False,
    "send_messages": False,
    "send_media": False,
    "send_stickers": False,
    "send_gifs": False,
    "send_games": False,
    "send_inline": False,
    "send_polls": False,
    "change_info": False,
    "invite_users": False,
}

async def get_user_by_username(client: TelegramClient, username: str) -> Optional[User]:
    """
    Получает пользователя по username
    """
    username = username.strip()
    
    # Убираем @ если есть
    if username.startswith("@"):
        username = username[1:]
    
    # Убираем t.me/ если есть
    if "t.me/" in username:
        username = username.split("t.me/", maxsplit=1)[1]
    
    username = username.split("/", maxsplit=1)[0]
    
    if not username:
        return None
    
    try:
        # Пробуем получить по username
        user = await client.get_entity(username)
        if isinstance(user, User):
            return user
    except Exception:
        pass
    
    try:
        # Пробуем поиск по контактам
        result = await client(functions.contacts.SearchRequest(q=username, limit=10))
        if hasattr(result, "users") and result.users:
            for user in result.users:
                if hasattr(user, "username") and user.username and user.username.lower() == username.lower():
                    return user
            # Если не нашли точное совпадение, возвращаем первого
            if result.users:
                return result.users[0]
    except Exception:
        pass
    
    return None

async def get_admin_chats(client: TelegramClient) -> List[int]:
    """
    Получает список всех чатов где у аккаунта есть права админа для бана
    """
    chats = []
    
    try:
        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            
            # Проверяем что это чат или канал
            if not (isinstance(entity, Chat) or isinstance(entity, Channel)):
                continue
            
            # Проверяем что есть права админа
            try:
                admin_rights = getattr(entity, "admin_rights", None)
                if admin_rights and getattr(admin_rights, "ban_users", False):
                    # Есть права на бан
                    chats.append(entity.id)
                    continue
            except:
                pass
            
            # Проверяем через get_permissions
            try:
                me = await client.get_me()
                my_permissions = await client.get_permissions(entity, me)
                if my_permissions and my_permissions.is_admin:
                    # Проверяем что есть права на бан
                    admin_permissions = await client.get_permissions(entity, me)
                    if admin_permissions and hasattr(admin_permissions, "ban_users"):
                        if admin_permissions.ban_users:
                            chats.append(entity.id)
            except:
                pass
            
            # Проверяем количество участников (больше 5)
            try:
                participants_count = getattr(entity, "participants_count", 0)
                if participants_count > 5:
                    # Пробуем проверить права через get_permissions
                    try:
                        me = await client.get_me()
                        perms = await client.get_permissions(entity, me)
                        if perms and perms.is_admin:
                            chats.append(entity.id)
                    except:
                        pass
            except:
                pass
                
    except Exception as e:
        print(f"Ошибка при получении списка чатов: {e}")
    
    return chats

async def ban_user_in_chat(client: TelegramClient, chat_id: int, user: User, reason: str = "Freezer") -> bool:
    """
    Банит пользователя в конкретном чате
    """
    try:
        await client.edit_permissions(
            chat_id,
            user,
            until_date=0,  # Навсегда
            **BANNED_RIGHTS
        )
        return True
    except FloodWaitError as e:
        # Ждем если флуд-лимит
        await asyncio.sleep(e.seconds)
        return False
    except (ChatAdminRequiredError, UserAdminInvalidError):
        # Нет прав или пользователь админ
        return False
    except Exception:
        # Другая ошибка
        return False

async def global_ban_by_username(session_path: str, username: str, reason: str = "Freezer") -> Dict:
    """
    Глобальный бан пользователя по username через Telethon
    
    Args:
        session_path: Путь к .session файлу
        username: Username пользователя (без @)
        reason: Причина бана
    
    Returns:
        Dict с результатами: {
            "success": bool,
            "user": User или None,
            "total_chats": int,
            "successful_bans": int,
            "failed_bats": int,
            "error": str или None
        }
    """
    result = {
        "success": False,
        "user": None,
        "total_chats": 0,
        "successful_bans": 0,
        "failed_bans": 0,
        "error": None
    }
    
    # Проверяем что файл сессии существует
    if not os.path.exists(session_path):
        result["error"] = f"Файл сессии не найден: {session_path}"
        return result
    
    # Получаем API ID и API Hash из переменных окружения или используем дефолтные
    api_id = os.getenv("TELEGRAM_API_ID", "2040")
    api_hash = os.getenv("TELEGRAM_API_HASH", "b18441a1ff607e10a989891a5462e627")
    
    # Имя сессии (без расширения .session)
    session_name = os.path.splitext(os.path.basename(session_path))[0]
    session_dir = os.path.dirname(session_path) if os.path.dirname(session_path) else "."
    
    client = None
    try:
        # Создаем клиент Telethon
        client = TelegramClient(
            os.path.join(session_dir, session_name),
            int(api_id),
            api_hash
        )
        
        # Подключаемся
        await client.start()
        
        # Получаем пользователя по username
        user = await get_user_by_username(client, username)
        if not user:
            result["error"] = f"Пользователь @{username} не найден"
            return result
        
        # Проверяем DC ID пользователя
        dc_id = None
        try:
            # Пробуем получить DC ID из атрибутов пользователя
            dc_id = getattr(user, "dc_id", None)
            
            # Если DC ID не найден, пробуем получить полную информацию о пользователе
            if dc_id is None:
                try:
                    full_user = await client.get_entity(user)
                    dc_id = getattr(full_user, "dc_id", None)
                except:
                    pass
            
            # Если все еще не найден, пробуем через get_full_user
            if dc_id is None:
                try:
                    from telethon.tl.functions.users import GetFullUserRequest
                    full_user_info = await client(GetFullUserRequest(user))
                    if hasattr(full_user_info, "full_user") and hasattr(full_user_info.full_user, "dc_id"):
                        dc_id = full_user_info.full_user.dc_id
                except:
                    pass
        except Exception:
            pass
        
        # Проверяем что DC ID разрешен (1, 3, 5)
        # Если DC ID не удалось определить, пропускаем проверку (на случай если метод работает)
        allowed_dc_ids = [1, 3, 5]
        if dc_id is not None and dc_id not in allowed_dc_ids:
            result["error"] = f"Метод не работает на DC ID {dc_id}. Поддерживаются только DC ID: 1, 3, 5"
            return result
        
        result["user"] = user
        
        # Получаем список чатов где есть права админа
        chats = await get_admin_chats(client)
        result["total_chats"] = len(chats)
        
        if not chats:
            result["error"] = "Не найдено чатов с правами админа"
            return result
        
        # Баним во всех чатах
        for chat_id in chats:
            try:
                await asyncio.sleep(0.05)  # Задержка между запросами
                success = await ban_user_in_chat(client, chat_id, user, reason)
                if success:
                    result["successful_bans"] += 1
                else:
                    result["failed_bans"] += 1
            except Exception as e:
                result["failed_bans"] += 1
                continue
        
        result["success"] = True
        
    except Exception as e:
        result["error"] = str(e)
    finally:
        if client:
            try:
                await client.disconnect()
            except:
                pass
    
    return result

