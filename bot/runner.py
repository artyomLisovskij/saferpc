import logging
import traceback
from fastapi import FastAPI, Request
from bot import EthereumTelegramBot


# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s",
    handlers=[
        logging.StreamHandler()  # Добавляем вывод в консоль
    ]
)
logger = logging.getLogger(__name__)
logger.info("Bot Runner сервис запущен")

# Создаем FastAPI приложение
app = FastAPI(title="Telegram Bot Notification API")

bot = EthereumTelegramBot()

# API эндпоинты
@app.post("/notify-transaction")
async def notify_transaction(request: Request):
    """Обрабатывает запрос на уведомление от основного сервиса"""
    try:
        # Получаем данные из запроса
        data = await request.json()
        logger.info(f"Получены данные: {data}")
        tx_id = data.get('tx_id')
        chat_id = data.get('chat_id')
        
        logger.info(f"Получено уведомление о транзакции: {tx_id}")
        
        # Вызываем функцию обработки уведомления напрямую
        bot.notify_user_about_transaction(chat_id, tx_id)
        logger.info(f"Уведомление о транзакции {tx_id} отправлено пользователю {chat_id}")
        
        return {"status": "success"}
    except Exception as e:
        error_msg = f"Ошибка при обработке уведомления: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return {"status": "error", "message": error_msg}

# Запуск телеграм-бота
def start_telegram_bot():
    """Запускает телеграм-бота"""
    try:
        logger.info("Запуск Telegram Bot...")
        bot.run_bot()
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {str(e)}")
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    import threading
    threading.Thread(target=start_telegram_bot, daemon=True).start()
    import uvicorn
    # Запускаем FastAPI через uvicorn
    uvicorn.run("runner:app", host="0.0.0.0", port=8000)