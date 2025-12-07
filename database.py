"""
Модуль для работы с SQLite базой данных
"""
import sqlite3
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Tuple

# Импортируем ADMIN_ID из конфига
from config import ADMIN_ID

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
            subscription_expires INTEGER DEFAULT NULL,
            subscription_started_at INTEGER DEFAULT NULL,
            banned BOOLEAN DEFAULT 0,
            ban_reason TEXT,
            ban_notified BOOLEAN DEFAULT 0
        )
    """)
    
    # Миграция: добавляем поле subscription_started_at если его нет
    try:
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'subscription_started_at' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN subscription_started_at INTEGER DEFAULT NULL")
            write_log("Миграция: добавлено поле subscription_started_at")
    except Exception as e:
        write_log(f"Ошибка при миграции subscription_started_at: {e}")
    
    # Миграция: если есть старое поле subscription, конвертируем его
    try:
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'subscription' in columns and 'subscription_expires' not in columns:
            # Добавляем новое поле
            cursor.execute("ALTER TABLE users ADD COLUMN subscription_expires INTEGER DEFAULT NULL")
            # Конвертируем старые данные: true -> NULL (навсегда), false -> NULL (нет подписки)
            cursor.execute("UPDATE users SET subscription_expires = NULL WHERE subscription = 0")
            cursor.execute("UPDATE users SET subscription_expires = -1 WHERE subscription = 1")
            # Удаляем старое поле (SQLite не поддерживает DROP COLUMN, поэтому просто игнорируем)
            write_log("Миграция: subscription -> subscription_expires выполнена")
    except Exception as e:
        write_log(f"Ошибка при миграции subscription: {e}")
    
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
    
    # Таблица платежей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            invoice_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'USD',
            days INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at INTEGER NOT NULL,
            paid_at INTEGER,
            crypto_id TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    
    # Миграция: добавляем поле crypto_id если его нет
    try:
        cursor.execute("PRAGMA table_info(payments)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'crypto_id' not in columns:
            cursor.execute("ALTER TABLE payments ADD COLUMN crypto_id TEXT")
            write_log("Миграция: добавлено поле crypto_id в таблицу payments")
    except Exception as e:
        write_log(f"Ошибка при миграции crypto_id: {e}")
    
    conn.commit()
    conn.close()

# === Функции для работы с пользователями ===
def add_user(user_id: int) -> bool:
    """Добавляет пользователя в базу данных. Возвращает True если добавлен впервые, False если уже был"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("INSERT INTO users (user_id, subscription_expires, banned) VALUES (?, NULL, 0)", (user_id,))
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
    """Возвращает статус подписки пользователя (активна ли сейчас).
    Автоматически проверяет и отзывает истекшие подписки"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT subscription_expires, subscription_started_at FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result or result[0] is None:
        return False
    
    expires = result[0]
    started_at = result[1]
    
    # -1 означает подписка навсегда
    if expires == -1:
        return True
    
    # Проверяем валидность timestamp (должен быть разумным значением)
    # Максимальный валидный timestamp для 2100 года примерно 4102444800
    # Если значение больше этого или меньше 0 (кроме -1), считаем некорректным
    MAX_VALID_TIMESTAMP = 4102444800  # Примерно 2100-01-01
    
    if expires is None or expires <= 0 or expires > MAX_VALID_TIMESTAMP:
        # Некорректное значение - отзываем подписку
        revoke_subscription(user_id)
        write_log(f"Подписка пользователя {user_id} отозвана из-за некорректного значения expires: {expires}")
        return False
    
    # Проверяем, не истекла ли подписка
    import time
    current_time = int(time.time())
    
    if expires <= current_time:
        # Подписка истекла - автоматически отзываем
        revoke_subscription(user_id)
        write_log(f"Подписка пользователя {user_id} истекла и была автоматически отозвана (начало: {started_at}, истечение: {expires})")
        return False
    
    return True

def get_subscription_expires(user_id: int) -> Optional[int]:
    """Возвращает время истечения подписки (Unix timestamp) или None если нет подписки, -1 если навсегда"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT subscription_expires FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result or result[0] is None:
        return None
    
    return result[0]


def update_subscription_status(user_id: int, status: bool) -> bool:
    """Обновляет статус подписки пользователя (устаревший метод, используйте give_subscription)"""
    if status:
        # Выдаем подписку навсегда (-1)
        return give_subscription(user_id, days=-1)
    else:
        # Убираем подписку
        return revoke_subscription(user_id)

def give_subscription(user_id: int, days: int = -1, extend: bool = True) -> bool:
    """Выдает подписку пользователю на указанное количество дней. days=-1 означает навсегда.
    Фиксирует дату начала подписки (subscription_started_at).
    Если extend=True и у пользователя уже есть временная подписка - продлевает её."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        import time
        current_time = int(time.time())
        
        # Проверяем текущую подписку
        cursor.execute("SELECT subscription_expires, subscription_started_at FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        
        if result and result[0] is not None:
            current_expires = result[0]
            current_started_at = result[1]
            
            # Если подписка навсегда (-1), не продлеваем
            if current_expires == -1:
                # Подписка навсегда уже есть
                conn.close()
                return False  # Возвращаем False чтобы показать что подписка уже есть
            
            # Если есть временная подписка и она еще не истекла
            if current_expires > current_time and extend:
                # Продлеваем подписку - добавляем дни к текущей дате истечения
                if days == -1:
                    # Покупаем навсегда - заменяем временную
                    expires = -1
                    started_at = current_time
                else:
                    # Продлеваем временную подписку
                    expires = current_expires + (days * 24 * 60 * 60)
                    started_at = current_started_at if current_started_at else current_time
            else:
                # Подписка истекла или extend=False - выдаем новую
                if days == -1:
                    expires = -1
                else:
                    expires = current_time + (days * 24 * 60 * 60)
                started_at = current_time
        else:
            # Подписки нет - выдаем новую
            if days == -1:
                expires = -1
            else:
                expires = current_time + (days * 24 * 60 * 60)
            started_at = current_time
        
        # Обновляем подписку
        cursor.execute("""
            UPDATE users 
            SET subscription_expires = ?, subscription_started_at = ?
            WHERE user_id = ?
        """, (expires, started_at, user_id))
        
        if cursor.rowcount == 0:
            # Пользователя нет, создаем его
            cursor.execute("""
                INSERT INTO users (user_id, subscription_expires, subscription_started_at, banned) 
                VALUES (?, ?, ?, 0)
            """, (user_id, expires, started_at))
        
        conn.commit()
        days_text = "навсегда" if days == -1 else f"{days} дней"
        action_text = "продлена" if (result and result[0] is not None and result[0] > current_time and extend) else "выдана"
        write_log(f"Подписка пользователю {user_id} {action_text} на {days_text} (начало: {started_at}, истечение: {expires})")
        return True
    except Exception as e:
        write_log(f"Ошибка при выдаче подписки пользователю {user_id}: {e}")
        return False
    finally:
        conn.close()

def revoke_subscription(user_id: int) -> bool:
    """Отзывает подписку у пользователя (сбрасывает и expires, и started_at)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE users 
            SET subscription_expires = NULL, subscription_started_at = NULL 
            WHERE user_id = ?
        """, (user_id,))
        conn.commit()
        write_log(f"Отозвана подписка у пользователя {user_id}")
        return True
    except Exception as e:
        write_log(f"Ошибка при отзыве подписки у пользователя {user_id}: {e}")
        return False
    finally:
        conn.close()

def check_and_revoke_expired_subscriptions() -> int:
    """Проверяет все подписки и автоматически отзывает истекшие.
    Возвращает количество отозванных подписок"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        import time
        current_time = int(time.time())
        
        # Находим все истекшие подписки (исключая навсегда -1)
        cursor.execute("""
            SELECT user_id, subscription_expires, subscription_started_at 
            FROM users 
            WHERE subscription_expires IS NOT NULL 
            AND subscription_expires != -1 
            AND subscription_expires <= ?
        """, (current_time,))
        
        expired_subscriptions = cursor.fetchall()
        revoked_count = 0
        
        for user_id, expires, started_at in expired_subscriptions:
            # Отзываем подписку
            cursor.execute("""
                UPDATE users 
                SET subscription_expires = NULL, subscription_started_at = NULL 
                WHERE user_id = ?
            """, (user_id,))
            revoked_count += 1
            write_log(f"Автоматически отозвана истекшая подписка у пользователя {user_id} (начало: {started_at}, истечение: {expires})")
        
        conn.commit()
        if revoked_count > 0:
            write_log(f"Проверка подписок: отозвано {revoked_count} истекших подписок")
        
        return revoked_count
    except Exception as e:
        write_log(f"Ошибка при проверке истекших подписок: {e}")
        return 0
    finally:
        conn.close()

def get_subscription_started_at(user_id: int) -> Optional[int]:
    """Возвращает дату начала подписки (Unix timestamp) или None"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT subscription_started_at FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result or result[0] is None:
        return None
    
    return result[0]


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
                INSERT OR REPLACE INTO users (user_id, subscription_expires, banned, ban_reason, ban_notified)
                VALUES (?, NULL, 0, NULL, 0)
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
    # ADMIN_ID может быть списком или одним ID
    if isinstance(ADMIN_ID, list):
        admins = ADMIN_ID.copy()  # Копируем список главных админов
    else:
        admins = [ADMIN_ID]  # Если один админ
    
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
    # Проверяем главных админов из конфига
    if isinstance(ADMIN_ID, list):
        if user_id in ADMIN_ID:
            return True
    else:
        if user_id == ADMIN_ID:
            return True
    
    # Проверяем админов из базы данных
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT 1 FROM admins WHERE admin_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def add_admin(admin_id: int) -> bool:
    """Добавляет админа в базу данных. Возвращает True если добавлен, False если уже был"""
    # Проверяем что это не главный админ из конфига
    if isinstance(ADMIN_ID, list):
        if admin_id in ADMIN_ID:
            return False  # Главный админ уже есть
    else:
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
    # Нельзя удалить главного админа из конфига
    if isinstance(ADMIN_ID, list):
        if admin_id in ADMIN_ID:
            return False  # Главного админа нельзя удалить
    else:
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
        "subscription": "Подписка"
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
        
        # Количество пользователей с активной подпиской
        import time
        current_time = int(time.time())
        cursor.execute("""
            SELECT COUNT(*) FROM users 
            WHERE subscription_expires IS NOT NULL 
            AND (subscription_expires = -1 OR subscription_expires > ?)
        """, (current_time,))
        stats['subscribed'] = cursor.fetchone()[0]
        
        
    except Exception as e:
        write_log(f"Ошибка при получении статистики: {e}")
        stats = {
            'users': 0,
            'banned': 0,
            'admins': 1,
            'whitelist': 0,
            'promocodes': 0,
            'subscribed': 0,
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

# === Функции для работы с платежами ===
def create_payment(invoice_id: str, user_id: int, amount: float, days: int, currency: str = "USD", crypto_id: Optional[str] = None) -> bool:
    """Создает запись о платеже в базе данных"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        import time
        current_time = int(time.time())
        cursor.execute("""
            INSERT INTO payments (invoice_id, user_id, amount, currency, days, status, created_at, crypto_id)
            VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
        """, (invoice_id, user_id, amount, currency, days, current_time, crypto_id))
        conn.commit()
        write_log(f"Создан платеж {invoice_id} для пользователя {user_id}: {amount} {currency} за {days} дней")
        return True
    except Exception as e:
        write_log(f"Ошибка при создании платежа {invoice_id}: {e}")
        return False
    finally:
        conn.close()

def update_payment_status(invoice_id: str, status: str) -> bool:
    """Обновляет статус платежа"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        import time
        paid_at = int(time.time()) if status == "paid" else None
        if paid_at:
            cursor.execute("""
                UPDATE payments 
                SET status = ?, paid_at = ?
                WHERE invoice_id = ?
            """, (status, paid_at, invoice_id))
        else:
            cursor.execute("""
                UPDATE payments 
                SET status = ?
                WHERE invoice_id = ?
            """, (status, invoice_id))
        conn.commit()
        write_log(f"Обновлен статус платежа {invoice_id}: {status}")
        return True
    except Exception as e:
        write_log(f"Ошибка при обновлении статуса платежа {invoice_id}: {e}")
        return False
    finally:
        conn.close()

def get_payment(invoice_id: str) -> Optional[Dict]:
    """Получает информацию о платеже"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT invoice_id, user_id, amount, currency, days, status, created_at, paid_at, crypto_id
        FROM payments WHERE invoice_id = ?
    """, (invoice_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        return None
    
    return {
        "invoice_id": result[0],
        "user_id": result[1],
        "amount": result[2],
        "currency": result[3],
        "days": result[4],
        "status": result[5],
        "created_at": result[6],
        "paid_at": result[7],
        "crypto_id": result[8] if len(result) > 8 else None
    }

def get_user_pending_payment(user_id: int) -> Optional[Dict]:
    """Получает активный платеж пользователя"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT invoice_id, user_id, amount, currency, days, status, created_at, paid_at, crypto_id
        FROM payments 
        WHERE user_id = ? AND status = 'pending'
        ORDER BY created_at DESC
        LIMIT 1
    """, (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        return None
    
    return {
        "invoice_id": result[0],
        "user_id": result[1],
        "amount": result[2],
        "currency": result[3],
        "days": result[4],
        "status": result[5],
        "created_at": result[6],
        "paid_at": result[7],
        "crypto_id": result[8] if len(result) > 8 else None
    }

def get_payments_history(limit: int = 50) -> List[Dict]:
    """Получает историю платежей, отсортированную по дате создания (новые первые)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT invoice_id, user_id, amount, currency, days, status, created_at, paid_at, crypto_id
        FROM payments 
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))
    
    results = cursor.fetchall()
    conn.close()
    
    payments = []
    for row in results:
        payments.append({
            "invoice_id": row[0],
            "user_id": row[1],
            "amount": row[2],
            "currency": row[3],
            "days": row[4],
            "status": row[5],
            "created_at": row[6],
            "paid_at": row[7],
            "crypto_id": row[8] if len(row) > 8 else None
        })
    
    return payments

# === Функция логирования ===
# Будет переопределена при импорте из syym.py
def write_log(text: str):
    """Логирование (импортируется из syym.py)"""
    pass

# Инициализируем базу данных при импорте модуля
init_database()

