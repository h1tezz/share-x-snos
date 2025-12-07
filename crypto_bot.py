"""
Модуль для работы с Crypto Bot API (send)
"""
import aiohttp
import json
from typing import Optional, Dict, Any

# Импортируем токен из config
try:
    from config import CRYPTO_BOT_TOKEN
except (ImportError, AttributeError):
    CRYPTO_BOT_TOKEN = None

# URL для Crypto Bot API
CRYPTO_BOT_API_URL = "https://pay.crypt.bot/api"

# Варианты подписки (дни, цена в USD)
SUBSCRIPTION_PLANS = {
    1: {"days": 1, "price": 1.0, "name": "1 день"},
    7: {"days": 7, "price": 5.0, "name": "7 дней"},
    30: {"days": 30, "price": 10.0, "name": "30 дней"},
    -1: {"days": -1, "price": 25.0, "name": "Навсегда"}
}

async def send_message_via_crypto_bot(
    user_id: int,
    message: str,
    parse_mode: Optional[str] = None,
    reply_markup: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Отправляет сообщение пользователю через Crypto Bot API (send)
    
    Args:
        user_id: ID пользователя Telegram
        message: Текст сообщения
        parse_mode: Режим парсинга (HTML, Markdown, MarkdownV2)
        reply_markup: Клавиатура (InlineKeyboardMarkup в виде словаря)
    
    Returns:
        Словарь с результатом запроса
    """
    if not CRYPTO_BOT_TOKEN:
        return {
            "ok": False,
            "error": "Crypto Bot token not configured"
        }
    
    try:
        # Формируем данные для отправки через Crypto Bot API
        # Crypto Bot API использует стандартный Telegram Bot API формат
        payload = {
            "chat_id": user_id,
            "text": message
        }
        
        if parse_mode:
            payload["parse_mode"] = parse_mode
        
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup) if isinstance(reply_markup, dict) else reply_markup
        
        # Отправляем запрос через Crypto Bot API
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{CRYPTO_BOT_API_URL}/sendMessage",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN
                }
            ) as response:
                result = await response.json()
                return result
                
    except Exception as e:
        return {
            "ok": False,
            "error": str(e)
        }

async def send_message_safe(
    user_id: int,
    message: str,
    parse_mode: Optional[str] = None,
    reply_markup: Optional[Dict] = None
) -> bool:
    """
    Безопасная отправка сообщения через Crypto Bot API
    Возвращает True если успешно, False если ошибка
    """
    result = await send_message_via_crypto_bot(user_id, message, parse_mode, reply_markup)
    return result.get("ok", False)

async def create_invoice(
    user_id: int,
    amount: float,
    asset: str = "USDT",
    description: str = "",
    payload: Optional[str] = None
) -> Dict[str, Any]:
    """
    Создает инвойс через Crypto Bot API
    
    Args:
        user_id: ID пользователя Telegram
        amount: Сумма платежа
        asset: Криптовалюта (USDT, TON, BTC, ETH, USDC, BUSD и т.д.)
        description: Описание платежа
        payload: Дополнительные данные (например, days для подписки)
    
    Returns:
        Словарь с результатом запроса (содержит invoice_id, invoice_url и т.д.)
    """
    if not CRYPTO_BOT_TOKEN:
        return {
            "ok": False,
            "error": "Crypto Bot token not configured"
        }
    
    try:
        # Формируем данные для создания инвойса
        # Crypto Bot API требует параметр "asset" (криптовалюта), а не "currency"
        payload_data = {
            "asset": asset,
            "amount": str(amount),  # Crypto Bot API требует строку для amount
        }
        
        if description:
            payload_data["description"] = description
        
        if payload:
            payload_data["payload"] = payload
        
        # Отправляем запрос через Crypto Bot API
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{CRYPTO_BOT_API_URL}/createInvoice",
                json=payload_data,
                headers={
                    "Content-Type": "application/json",
                    "Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN
                }
            ) as response:
                result = await response.json()
                return result
                
    except Exception as e:
        return {
            "ok": False,
            "error": str(e)
        }

async def get_invoice_status(invoice_id: str) -> Dict[str, Any]:
    """
    Получает статус инвойса через Crypto Bot API
    
    Args:
        invoice_id: ID инвойса
    
    Returns:
        Словарь с информацией об инвойсе
    """
    if not CRYPTO_BOT_TOKEN:
        return {
            "ok": False,
            "error": "Crypto Bot token not configured"
        }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{CRYPTO_BOT_API_URL}/getInvoices",
                params={"invoice_ids": invoice_id},
                headers={
                    "Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN
                }
            ) as response:
                result = await response.json()
                return result
                
    except Exception as e:
        return {
            "ok": False,
            "error": str(e)
        }
