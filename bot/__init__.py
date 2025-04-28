# Телеграм-бот сервис
from app.bot import EthereumTelegramBot

# Создаем экземпляр бота для использования в других модулях
telegram_bot = EthereumTelegramBot()

__all__ = ['telegram_bot'] 