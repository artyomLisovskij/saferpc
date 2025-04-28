import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from web3.auto import w3

# Настройка логирования
logger = logging.getLogger(__name__)

def normalize_address(address):
    """Нормализует Ethereum адрес"""
    return w3.to_checksum_address(address)


def format_transaction(tx_id, tx_data, simulation_result=None):
    """
    Форматирует транзакцию для отображения в сообщении Telegram
    """
    # Определяем базовую информацию о транзакции
    method = tx_data.get('method') if isinstance(tx_data, dict) else 'Unknown'
    
    formatted_text = f"🔔 *Новая транзакция*\n\n"
    formatted_text += f"*ID:* `0x{tx_data.get('tx_hash')}`\n"
    formatted_text += f"*Отправитель:* `{tx_data.get('from')}`\n"
    if tx_data.get('to') == 'None' or tx_data.get('to') == None:
        formatted_text += f"📄 *Транзакция создания контракта!*\n"
    else:
        formatted_text += f"*Получатель:* `{tx_data.get('to')}`\n"
    formatted_text += f"*Сумма:* `{tx_data.get('value')}`\n"
    formatted_text += f"*Газ:* `{tx_data.get('gas')}`\n"
    formatted_text += f"*Цена газа:* `{tx_data.get('gasPrice')}`\n"
    if len(tx_data.get('input', '')) > 2000:
        formatted_text += f"*Входные данные(сокращенно):* `{tx_data.get('input')[:20]}...`\n"
    else:
        formatted_text += f"*Входные данные:* `{tx_data.get('input')}`\n"
    formatted_text += f"*Nonce:* `{tx_data.get('nonce')}`\n"
    formatted_text += f"*Chain ID:* `{tx_data.get('chainId')}`\n"
    formatted_text += f"\n"
    for log in tx_data.get('logs', []):
        formatted_text += f"*Лог №:* `{log.get('logIndex')}`\n"
        formatted_text += f"*Адрес:* `{log.get('address')}`\n"
        formatted_text += f"*Топики:* `{log.get('topics')}`\n"
        formatted_text += f"*Данные:* `{log.get('data', '')}`\n\n"
        if log.get('decoded'):
            formatted_text += f"*Декодированные данные:*\n"
            formatted_text += f"*Событие:* `{log['decoded'].get('event')}`\n"
            formatted_text += f"*Аргументы:* `{log['decoded'].get('args')}`\n"
            if log['decoded'].get('event') == 'Transfer':
                # TODO: брать decimals из контракта
                formatted_text += f"💸 *Перевод* `{w3.from_wei(log['decoded'].get('args').get('value'), 'ether') if log['decoded'].get('args').get('value') else '0'} токенов контракта {log.get('address')} на адрес {log['decoded'].get('args').get('to')}`\n"
        formatted_text += f"\n"

    formatted_text += "\nПожалуйста, подтвердите или отклоните эту транзакцию."
    return formatted_text
