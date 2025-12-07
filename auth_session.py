"""
Скрипт для авторизации Telethon сессии для метода freezer
Создает .session файл для использования в freezer.py
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
    
    # Запрашиваем API ID
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
    
    # Запрашиваем API Hash
    while True:
        api_hash = input("🔑 Введите API Hash: ").strip()
        if not api_hash:
            print("❌ API Hash не может быть пустым!")
            continue
        break
    
    # Запрашиваем имя сессии
    session_name = input("📝 Введите имя сессии (без .session, по умолчанию 'freezer'): ").strip()
    if not session_name:
        session_name = "freezer"
    
    print()
    print("=" * 50)
    print(f"📋 Параметры:")
    print(f"   API ID: {api_id}")
    print(f"   API Hash: {api_hash[:10]}...")
    print(f"   Имя сессии: {session_name}")
    print("=" * 50)
    print()
    
    # Создаем клиент
    client = TelegramClient(session_name, api_id, api_hash)
    
    try:
        print("🔄 Подключение к Telegram...")
        await client.start()
        
        # Проверяем, авторизован ли уже
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
            # Запрашиваем номер телефона
            print()
            phone = input("📞 Введите номер телефона (с кодом страны, например +79991234567): ").strip()
            if not phone:
                print("❌ Номер телефона не может быть пустым!")
                await client.disconnect()
                return
            
            print(f"📤 Отправка кода на {phone}...")
            await client.send_code_request(phone)
            
            # Запрашиваем код
            code = input("🔢 Введите код из Telegram: ").strip()
            if not code:
                print("❌ Код не может быть пустым!")
                await client.disconnect()
                return
            
            try:
                # Пытаемся войти с кодом
                await client.sign_in(phone, code)
                me = await client.get_me()
                print(f"✅ Успешно авторизован как: {me.first_name} (@{me.username if me.username else 'без username'})")
            except SessionPasswordNeededError:
                # Нужен пароль 2FA
                password = input("🔒 Введите пароль двухфакторной аутентификации: ").strip()
                if not password:
                    print("❌ Пароль не может быть пустым!")
                    await client.disconnect()
                    return
                
                await client.sign_in(password=password)
                me = await client.get_me()
                print(f"✅ Успешно авторизован как: {me.first_name} (@{me.username if me.username else 'без username'})")
        
        # Проверяем что сессия создана
        session_file = f"{session_name}.session"
        if os.path.exists(session_file):
            print()
            print("=" * 50)
            print("✅ Сессия успешно создана!")
            print(f"📁 Файл: {os.path.abspath(session_file)}")
            print()
            print("💡 Теперь вы можете использовать этот .session файл в freezer")
            print("=" * 50)
        else:
            print("⚠️  Файл сессии не найден, но авторизация прошла успешно")
        
    except Exception as e:
        print(f"❌ Ошибка при авторизации: {e}")
        print()
        print("Проверьте:")
        print("  - Правильность API ID и API Hash")
        print("  - Правильность номера телефона")
        print("  - Правильность кода подтверждения")
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

