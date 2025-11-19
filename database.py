"""
Модуль для работы с SQLite базой данных
"""
import sqlite3
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Tuple

# Импортируем ADMIN_ID из конфига
try:
    from config import ADMIN_ID
except ImportError:
    ADMIN_ID = 8428752149  # Значение по умолчанию, если конфиг не найден

DB_PATH = "sql.sql"

# === Инициализация базы данных ===
def init_database():
    """Инициализирует базу данных и создает все необходимые таблицы"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            subscription BOOLEAN DEFAULT 0,
            premium BOOLEAN DEFAULT 0,
            banned BOOLEAN DEFAULT 0,
            ban_reason TEXT,
            ban_notified BOOLEAN DEFAULT 0
        )
    """)
    
    # Таблица админов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            admin_id INTEGER PRIMARY KEY
        )
    """)
    
    # Таблица белого списка
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS whitelist (
            user_id INTEGER PRIMARY KEY
        )
    """)
    
    # Таблица промокодов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS promocodes (
            name TEXT PRIMARY KEY,
            ref TEXT UNIQUE NOT NULL,
            reward TEXT NOT NULL,
            active BOOLEAN DEFAULT 1,
            uses INTEGER DEFAULT 0,
            max_uses INTEGER DEFAULT -1
        )
    """)
    
    # Таблица использованных промокодов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS used_promocodes (
            user_id INTEGER,
            promocode_name TEXT,
            PRIMARY KEY (user_id, promocode_name)
        )
    """)
    
    # Таблица настроек
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    # Таблица забаненных пользователей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS banned_users (
            user_id INTEGER PRIMARY KEY,
            ban_reason TEXT,
            ban_notified BOOLEAN DEFAULT 0
        )
    """)
    
    conn.commit()
    conn.close()

# === Функции для работы с пользователями ===
def add_user(user_id: int) -> bool:
    """Добавляет пользователя в базу данных. Возвращает True если добавлен впервые, False если уже был"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("INSERT INTO users (user_id, subscription, premium, banned) VALUES (?, 0, 0, 0)", (user_id,))
        conn.commit()
        write_log(f"Добавлен новый пользователь {user_id}")
        return True
    except sqlite3.IntegrityError:
        # Пользователь уже существует
        return False
    except Exception as e:
        write_log(f"Ошибка при добавлении пользователя {user_id}: {e}")
        return False
    finally:
        conn.close()

def is_registered(user_id: int) -> bool:
    """Проверяет, зарегистрирован ли пользователь"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def is_banned(user_id: int) -> bool:
    """Проверяет, заблокирован ли пользователь (проверяет таблицу banned_users)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT 1 FROM banned_users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def get_subscription_status(user_id: int) -> bool:
    """Возвращает статус подписки пользователя"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT subscription FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] == 1 if result else False

def get_premium_status(user_id: int) -> bool:
    """Возвращает статус премиума пользователя"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT premium FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] == 1 if result else False

def update_subscription_status(user_id: int, status: bool) -> bool:
    """Обновляет статус подписки пользователя"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("UPDATE users SET subscription = ? WHERE user_id = ?", (1 if status else 0, user_id))
        if cursor.rowcount == 0:
            # Пользователя нет, создаем его
            cursor.execute("INSERT INTO users (user_id, subscription, premium, banned) VALUES (?, ?, 0, 0)", 
                         (user_id, 1 if status else 0))
        conn.commit()
        write_log(f"Обновлен статус подписки для {user_id}: {status}")
        return True
    except Exception as e:
        write_log(f"Ошибка при обновлении подписки для {user_id}: {e}")
        return False
    finally:
        conn.close()

def update_premium_status(user_id: int, status: bool) -> bool:
    """Обновляет статус премиума пользователя"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("UPDATE users SET premium = ? WHERE user_id = ?", (1 if status else 0, user_id))
        if cursor.rowcount == 0:
            # Пользователя нет, создаем его
            cursor.execute("INSERT INTO users (user_id, subscription, premium, banned) VALUES (?, 0, ?, 0)", 
                         (user_id, 1 if status else 0))
        conn.commit()
        write_log(f"Обновлен статус премиума для {user_id}: {status}")
        return True
    except Exception as e:
        write_log(f"Ошибка при обновлении премиума для {user_id}: {e}")
        return False
    finally:
        conn.close()

def update_ban_status(user_id: int, status: bool, reason: Optional[str] = None) -> bool:
    """Обновляет статус бана пользователя. Если status=True, reason обязателен.
    При бане удаляет пользователя из базы (чтобы не получал рассылки)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        if status:
            # При бане удаляем пользователя из базы (чтобы не получал рассылки)
            # Но сохраняем информацию о бане в отдельной таблице для проверки
            cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            
            # Сохраняем информацию о бане в таблице banned_users
            cursor.execute("""
                INSERT OR REPLACE INTO banned_users (user_id, ban_reason, ban_notified) 
                VALUES (?, ?, 0)
            """, (user_id, reason))
            
            write_log(f"Пользователь {user_id} забанен и удален из users. Причина: {reason}")
        else:
            # При разбане восстанавливаем пользователя
            cursor.execute("DELETE FROM banned_users WHERE user_id = ?", (user_id,))
            # Восстанавливаем пользователя с базовыми настройками
            cursor.execute("""
                INSERT OR REPLACE INTO users (user_id, subscription, premium, banned, ban_reason, ban_notified)
                VALUES (?, 0, 0, 0, NULL, 0)
            """, (user_id,))
            write_log(f"Пользователь {user_id} разбанен и восстановлен в users")
        
        conn.commit()
        return True
    except Exception as e:
        write_log(f"Ошибка при обновлении бана для {user_id}: {e}")
        return False
    finally:
        conn.close()

def get_ban_reason(user_id: int) -> str:
    """Получает причину бана пользователя"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT ban_reason FROM banned_users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result and result[0] else "Не указана"

def is_ban_notified(user_id: int) -> bool:
    """Проверяет, было ли уже отправлено сообщение о бане пользователю"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT ban_notified FROM banned_users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] == 1 if result else False

def mark_ban_notified(user_id: int):
    """Отмечает, что пользователю было отправлено сообщение о бане"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("UPDATE banned_users SET ban_notified = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def unmark_ban_notified(user_id: int):
    """Убирает отметку о том, что пользователю было отправлено сообщение о бане"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("UPDATE banned_users SET ban_notified = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# === Функции для работы с админами ===
def load_admins() -> List[int]:
    """Загружает список админов из базы данных"""
    admins = [ADMIN_ID]  # Главный админ из конфига
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT admin_id FROM admins")
    results = cursor.fetchall()
    for row in results:
        if row[0] not in admins:
            admins.append(row[0])
    
    conn.close()
    return admins

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь админом"""
    if user_id == ADMIN_ID:
        return True
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT 1 FROM admins WHERE admin_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def add_admin(admin_id: int) -> bool:
    """Добавляет админа в базу данных. Возвращает True если добавлен, False если уже был"""
    if admin_id == ADMIN_ID:
        return False  # Главный админ уже есть
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("INSERT INTO admins (admin_id) VALUES (?)", (admin_id,))
        conn.commit()
        write_log(f"Добавлен новый админ {admin_id}")
        return True
    except sqlite3.IntegrityError:
        return False  # Уже есть
    except Exception as e:
        write_log(f"Ошибка при добавлении админа {admin_id}: {e}")
        return False
    finally:
        conn.close()

def remove_admin(admin_id: int) -> bool:
    """Удаляет админа из базы данных. Возвращает True если удален"""
    if admin_id == ADMIN_ID:
        return False  # Главного админа нельзя удалить
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM admins WHERE admin_id = ?", (admin_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    
    if deleted:
        write_log(f"Удален админ {admin_id}")
    
    return deleted

# === Функции для работы с белым списком ===
def is_whitelisted(user_id: int) -> bool:
    """Проверяет, находится ли пользователь в белом списке"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT 1 FROM whitelist WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def add_to_whitelist(user_id: int) -> bool:
    """Добавляет пользователя в белый список"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("INSERT INTO whitelist (user_id) VALUES (?)", (user_id,))
        conn.commit()
        write_log(f"Пользователь {user_id} добавлен в белый список")
        return True
    except sqlite3.IntegrityError:
        return False  # Уже в белом списке
    except Exception as e:
        write_log(f"Ошибка при добавлении в белый список {user_id}: {e}")
        return False
    finally:
        conn.close()

def remove_from_whitelist(user_id: int) -> bool:
    """Удаляет пользователя из белого списка"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM whitelist WHERE user_id = ?", (user_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    
    if deleted:
        write_log(f"Пользователь {user_id} удален из белого списка")
    
    return deleted

# === Функции для работы с промокодами ===
def load_promocodes() -> Dict:
    """Загружает промокоды из базы данных"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name, ref, reward, active, uses, max_uses FROM promocodes")
    promocodes = {}
    for row in cursor.fetchall():
        promocodes[row[0]] = {
            "ref": row[1],
            "reward": row[2],
            "active": bool(row[3]),
            "uses": row[4],
            "max_uses": row[5]
        }
    
    conn.close()
    return promocodes

def save_promocodes(promocodes: Dict) -> bool:
    """Сохраняет промокоды в базу данных"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Очищаем старые промокоды
        cursor.execute("DELETE FROM promocodes")
        
        # Добавляем новые
        for name, data in promocodes.items():
            cursor.execute("""
                INSERT INTO promocodes (name, ref, reward, active, uses, max_uses)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, data["ref"], data["reward"], 
                  1 if data["active"] else 0, data["uses"], data["max_uses"]))
        
        conn.commit()
        return True
    except Exception as e:
        write_log(f"Ошибка при сохранении промокодов: {e}")
        return False
    finally:
        conn.close()

def get_promocode_info(promocode_name: str) -> Optional[Dict]:
    """Получает информацию о промокоде"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT name, ref, reward, active, uses, max_uses 
        FROM promocodes 
        WHERE name = ?
    """, (promocode_name.upper(),))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
    
    reward_text = {
        "whitelist": "Вайт лист",
        "subscription": "Подписка",
        "premium": "Премиум",
        "premium_sub": "Премиум + Подписка"
    }.get(row[2], row[2])
    
    return {
        "name": row[0],
        "ref": row[1],
        "reward": reward_text,
        "active": bool(row[3]),
        "uses": row[4],
        "max_uses": row[5]
    }

def delete_promocode(promocode_name: str) -> Tuple[bool, str]:
    """Удаляет промокод"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM promocodes WHERE name = ?", (promocode_name.upper(),))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    
    if deleted:
        return True, "Промокод удален"
    else:
        return False, "Промокод не найден"

def is_promocode_used(user_id: int, promocode_name: str) -> bool:
    """Проверяет, использовал ли пользователь промокод"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 1 FROM used_promocodes 
        WHERE user_id = ? AND promocode_name = ?
    """, (user_id, promocode_name.upper()))
    
    result = cursor.fetchone()
    conn.close()
    return result is not None

def mark_promocode_used(user_id: int, promocode_name: str):
    """Отмечает промокод как использованный"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR IGNORE INTO used_promocodes (user_id, promocode_name)
        VALUES (?, ?)
    """, (user_id, promocode_name.upper()))
    
    conn.commit()
    conn.close()

def increment_promocode_uses(promocode_name: str):
    """Увеличивает счетчик использований промокода"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE promocodes 
        SET uses = uses + 1 
        WHERE name = ?
    """, (promocode_name.upper(),))
    
    conn.commit()
    conn.close()

# === Функции для работы с настройками ===
def get_setting(key: str, default: str = "") -> str:
    """Получает значение настройки"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else default

def set_setting(key: str, value: str):
    """Устанавливает значение настройки"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO settings (key, value)
        VALUES (?, ?)
    """, (key, value))
    
    conn.commit()
    conn.close()

# === Функция для получения всех пользователей для рассылки ===
def get_all_users_for_broadcast() -> List[int]:
    """Получает список всех пользователей для рассылки (исключая забаненных)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Получаем всех пользователей, которые не забанены
    # Забаненные пользователи удалены из users, поэтому просто получаем всех из users
    cursor.execute("SELECT user_id FROM users")
    results = cursor.fetchall()
    user_ids = [row[0] for row in results]
    
    conn.close()
    return user_ids

# === Функция для получения статистики ===
def get_statistics() -> dict:
    """Получает статистику бота"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    stats = {}
    
    try:
        # Количество пользователей
        cursor.execute("SELECT COUNT(*) FROM users")
        stats['users'] = cursor.fetchone()[0]
        
        # Количество забаненных
        cursor.execute("SELECT COUNT(*) FROM banned_users")
        stats['banned'] = cursor.fetchone()[0]
        
        # Количество админов
        cursor.execute("SELECT COUNT(*) FROM admins")
        stats['admins'] = cursor.fetchone()[0] + 1  # +1 главный админ
        
        # Количество в белом списке
        cursor.execute("SELECT COUNT(*) FROM whitelist")
        stats['whitelist'] = cursor.fetchone()[0]
        
        # Количество промокодов
        cursor.execute("SELECT COUNT(*) FROM promocodes")
        stats['promocodes'] = cursor.fetchone()[0]
        
        # Количество пользователей с подпиской
        cursor.execute("SELECT COUNT(*) FROM users WHERE subscription = 1")
        stats['subscribed'] = cursor.fetchone()[0]
        
        # Количество пользователей с премиумом
        cursor.execute("SELECT COUNT(*) FROM users WHERE premium = 1")
        stats['premium'] = cursor.fetchone()[0]
        
    except Exception as e:
        write_log(f"Ошибка при получении статистики: {e}")
        stats = {
            'users': 0,
            'banned': 0,
            'admins': 1,
            'whitelist': 0,
            'promocodes': 0,
            'subscribed': 0,
            'premium': 0
        }
    finally:
        conn.close()
    
    return stats

# === Функция для очистки базы данных пользователей ===
def clean_users_database() -> tuple[bool, int]:
    """Очищает таблицу users от всех пользователей. Возвращает (success, deleted_count)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Получаем количество пользователей перед удалением
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        
        # Удаляем всех пользователей
        cursor.execute("DELETE FROM users")
        conn.commit()
        
        write_log(f"База данных пользователей очищена, удалено {count} пользователей")
        return True, count
    except Exception as e:
        write_log(f"Ошибка при очистке базы данных пользователей: {e}")
        return False, 0
    finally:
        conn.close()

# === Функция логирования ===
# Будет переопределена при импорте из syym.py
def write_log(text: str):
    """Логирование (импортируется из syym.py)"""
    pass

# Инициализируем базу данных при импорте модуля
init_database()

