"""
Скрипт для авторизации Telethon сессии для метода freezer
Создает .session файл в папке sessions/ для использования в freezer.py
"""
import asyncio
import os
import sys
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError


async def create_session():
    """Создает Telethon сессию с авторизацией"""

    print("=" * 50)
    print("🔐 Авторизация Telethon сессии для Freezer")
    print("=" * 50)
    print()

    # --- API ID ---
    while True:
        try:
            api_id_input = input("📱 Введите API ID: ").strip()
            if not api_id_input:
                print("❌ API ID не может быть пустым!")
                continue
            api_id = int(api_id_input)
            break
        except ValueError:
            print("❌ API ID должен быть числом!")
        except KeyboardInterrupt:
            print("\n\n❌ Отменено пользователем")
            sys.exit(0)

    # --- API HASH ---
    while True:
        api_hash = input("🔑 Введите API Hash: ").strip()
        if not api_hash:
            print("❌ API Hash не может быть пустым!")
            continue
        break

    # --- Имя сессии ---
    session_name = input("📝 Введите имя сессии (по умолчанию: freezer): ").strip()
    if not session_name:
        session_name = "freezer"

    # --- Папка для сессий ---
    session_dir = "sessions"
    os.makedirs(session_dir, exist_ok=True)

    # Полный путь к файлу сессии
    session_path = os.path.join(session_dir, session_name)

    print()
    print("=" * 50)
    print(f"📋 Параметры:")
    print(f"   API ID: {api_id}")
    print(f"   API Hash: {api_hash[:10]}...")
    print(f"   Имя сессии: {session_name}")
    print(f"   Папка: {os.path.abspath(session_dir)}")
    print("=" * 50)
    print()

    # --- Создаем клиента Telethon ---
    client = TelegramClient(session_path, api_id, api_hash)

    try:
        print("🔄 Подключение к Telegram...")
        await client.start()

        # Проверка авторизации
        if await client.is_user_authorized():
            me = await client.get_me()
            print(f"✅ Уже авторизован как: {me.first_name} (@{me.username if me.username else 'без username'})")
            print()
            confirm = input("Использовать эту сессию? (y/n): ").strip().lower()
            if confirm != 'y':
                print("❌ Отменено")
                await client.disconnect()
                return
        else:
            # --- Телефон ---
            print()
            phone = input("📞 Введите номер телефона (например +79991234567): ").strip()
            if not phone:
                print("❌ Номер телефона не может быть пустым!")
                await client.disconnect()
                return

            print(f"📤 Отправка кода на {phone}...")
            await client.send_code_request(phone)

            # --- Код ---
            code = input("🔢 Введите код из Telegram: ").strip()
            if not code:
                print("❌ Код не может быть пустым!")
                await client.disconnect()
                return

            try:
                await client.sign_in(phone, code)
                me = await client.get_me()
                print(f"✅ Успешно авторизован как: {me.first_name} (@{me.username if me.username else 'без username'})")
            except SessionPasswordNeededError:
                # --- 2FA ---
                password = input("🔒 Введите пароль двухфакторной аутентификации: ").strip()
                if not password:
                    print("❌ Пароль не может быть пустым!")
                    await client.disconnect()
                    return

                await client.sign_in(password=password)
                me = await client.get_me()
                print(f"✅ Успешно авторизован как: {me.first_name} (@{me.username if me.username else 'без username'})")

        # --- Проверка файла сессии ---
        session_file = f"{session_path}.session"
        if os.path.exists(session_file):
            print()
            print("=" * 50)
            print("✅ Сессия успешно создана!")
            print(f"📁 Путь: {os.path.abspath(session_file)}")
            print("💡 Готово! Можешь использовать этот файл в freezer.py")
            print("=" * 50)
        else:
            print("⚠️ Файл сессии не найден, но вход выполнен")

    except Exception as e:
        print(f"❌ Ошибка при авторизации: {e}")
        print()
        print("Проверьте:")
        print(" - API ID и API Hash")
        print(" - Номер телефона")
        print(" - Код подтверждения")
    finally:
        try:
            await client.disconnect()
        except:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(create_session())
    except KeyboardInterrupt:
        print("\n\n❌ Отменено пользователем")
        sys.exit(0)
