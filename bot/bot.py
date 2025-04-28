import os
import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Updater, CommandHandler, CallbackQueryHandler, 
    CallbackContext, MessageHandler, Filters,
    ConversationHandler
)

from handlers import (
    format_transaction, 
    normalize_address
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Константы для работы с Telegram API
API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
API_URL = 'http://rpc-proxy:8000'

# Константы для ConversationHandler
CHOOSING, TYPING_ADDRESS, ADDRESS_SELECTED = range(3)

class EthereumTelegramBot:
    """Класс для взаимодействия с Ethereum через Telegram Bot"""
    
    def __init__(self):
        """Инициализирует бота"""
        self.updater = Updater(token=API_TOKEN)
        self.dispatcher = self.updater.dispatcher
        self.api_base_url = API_URL
        
        # Обработчики команд
        self.dispatcher.add_handler(CommandHandler('start', self.start_command))
        self.dispatcher.add_handler(CommandHandler('help', self.help_command))
        
        # Обработчик для всех кнопок через callback_query
        self.dispatcher.add_handler(CallbackQueryHandler(self.handle_button_press))
        
        # Обработчик для ввода адреса
        self.dispatcher.add_handler(MessageHandler(
            Filters.text & ~Filters.command,
            self.handle_text_input
        ))
        
        # Обработчик ошибок
        self.dispatcher.add_error_handler(self.error_handler)
        
        logger.info("Telegram Bot инициализирован")
    
    def run_bot(self):
        """Запускает бота (асинхронная версия)"""
        logger.info("Запускаем бота")
        # Используем не await, так как start_polling - синхронный метод
        self.updater.start_polling()
        logger.info("Бот запущен")

    def notify_user_about_transaction(self, chat_id, tx_id):
        """Отправляет сообщение пользователю о новой транзакции"""
        response = requests.post(f"{self.api_base_url}/get_transaction", json={"tx_id": tx_id})
        json_response = response.json()
        if json_response.get('error'):
            logger.error(f"Ошибка при получении транзакции {tx_id}: {json_response['error']}")
        else:
            tx = json_response.get('transaction', {})
            pending = json_response.get('pending', False)
            confirmed = json_response.get('confirmed', False)
            message = format_transaction(tx_id, tx)
            print(tx_id)
            keyboard = [
                [InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_tx_{tx_id}"),
                 InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_tx_{tx_id}")
                ],
                [InlineKeyboardButton("🔙 Назад", callback_data="pending_transactions")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            self.updater.bot.send_message(chat_id=chat_id, text=message, reply_markup=reply_markup, parse_mode='Markdown')
           
    def start_command(self, update: Update, context: CallbackContext) -> None:
        """Обрабатывает команду /start"""
        user_id = str(update.effective_user.id)
        chat_id = str(update.effective_chat.id)
        
        try:
            response = requests.post(f"{self.api_base_url}/new_user", json={"user_id": user_id, "chat_id": chat_id})
            json_response = response.json()
            if json_response.get('error'):
                logger.error(f"Ошибка при создании пользователя {user_id}: {json_response['error']}")
            else:
                logger.info(f"Пользователь {user_id} успешно сохранен в базе")
        except Exception as e:
            logger.error(f"Ошибка при отклонении транзакции {tx_id}: {str(e)}")
            return {"error": str(e)}
        
        # Создаем клавиатуру для основных команд
        keyboard = [
            [InlineKeyboardButton("🔑 Управление адресами", callback_data="manage_addresses")],
            [InlineKeyboardButton("📋 Ожидающие транзакции", callback_data="pending_transactions")],
            [InlineKeyboardButton("❓ Помощь", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем приветственное сообщение
        update.message.reply_text(
            "👋 Привет! Я бот для работы с транзакциями.\n\n"
            f"Используйте безопасный proxy RPC {os.environ.get('EXTERNAL_RPC_URL')} для работы с сетью {os.environ.get('CHAIN_NAME')}.\n\n"
            "Для начала работы добавьте ваш адрес с помощью кнопки 'Управление адресами'.\n\n"
            "Вы получите уведомления о новых транзакциях на ваших адресах и сможете подтвердить или отклонить транзакции.\n\n"
            "Используйте кнопки ниже для навигации:",
            reply_markup=reply_markup
        )
    
    def help_command(self, update: Update, context: CallbackContext) -> None:
        """Отображает информацию о боте и его возможностях"""
        # Создаем клавиатуру для возврата в основное меню
        keyboard = [
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            "🚀 *Функции бота:*\n\n"
            "• *Управление адресами* — добавление и удаление EVM адресов для мониторинга\n"
            "• *Ожидающие транзакции* — просмотр и управление транзакциями, требующими подтверждения\n"
            "• *Уведомления* — получение уведомлений о новых транзакциях с ваших адресов\n\n"
            "Используйте кнопки для навигации по боту.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    def handle_button_press(self, update: Update, context: CallbackContext) -> None:
        """Обрабатывает нажатия на все кнопки"""
        query = update.callback_query
        query.answer()
        
        callback_data = query.data
        user_id = str(update.effective_user.id)
        logger.info(f"Пользователь {user_id} нажал кнопку: {callback_data}")

        # Убедимся, что пользователь сохранен в базе
        response = requests.post(f"{self.api_base_url}/get_user_id", json={"user_id": user_id})
        json_response = response.json()
        if json_response.get('error'):
            logger.error(f"Ошибка при получении пользователя {user_id}: {json_response['error']}")
        else:
            logger.info(json_response)
            user_id = json_response.get('user_id')
            logger.info(f"Пользователь {user_id} успешно получен из базы")

        # Обработка основных действий навигации
        if callback_data == "main_menu":
            self.show_main_menu(query)
        elif callback_data == "manage_addresses":
            self.show_address_menu(query)
        elif callback_data == "pending_transactions":
            self.show_pending_transactions(query)
        elif callback_data == "help":
            self.show_help(query)
            
        # Обработка управления адресами
        elif callback_data == "add_address":
            self.request_address_input(query)
            # Устанавливаем состояние для обработки текстового ввода
            context.user_data['awaiting_input'] = 'address'
        elif callback_data == "list_addresses":
            self.list_user_addresses(query, user_id)
        elif callback_data == "remove_address_menu":
            self.show_remove_address_menu(query, user_id)
        elif callback_data.startswith("remove_address_"):
            address = callback_data.replace("remove_address_", "")
            self.remove_user_address(query, user_id, address)
            
        # Обработка действий с транзакциями
        elif callback_data.startswith("confirm_tx_"):
            tx_id = callback_data.replace("confirm_tx_", "")
            self.process_transaction_action(query, tx_id, "confirm")
        elif callback_data.startswith("reject_tx_"):
            tx_id = callback_data.replace("reject_tx_", "")
            self.process_transaction_action(query, tx_id, "reject")
        elif callback_data.startswith("details_tx_"):
            tx_id = callback_data.replace("details_tx_", "")
            self.show_transaction_details(query, tx_id)
        elif callback_data == "back_to_address_menu":
            self.show_address_menu(query)
        else:
            query.edit_message_text("Неизвестная команда. Пожалуйста, вернитесь в главное меню.")
    
    def show_main_menu(self, query):
        """Показывает главное меню"""
        keyboard = [
            [InlineKeyboardButton("🔑 Управление адресами", callback_data="manage_addresses")],
            [InlineKeyboardButton("📋 Ожидающие транзакции", callback_data="pending_transactions")],
            [InlineKeyboardButton("❓ Помощь", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(
            "🏠 *Главное меню*\n\n"
            "Выберите нужное действие с помощью кнопок ниже:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    def show_help(self, query):
        """Показывает справку"""
        keyboard = [
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(
            "🚀 *Функции бота:*\n\n"
            f"Используйте безопасный proxy RPC {os.environ.get('EXTERNAL_RPC_URL')} для работы с сетью {os.environ.get('CHAIN_NAME')}.\n\n"
            "• *Управление адресами* — добавление и удаление EVM адресов для мониторинга\n"
            "• *Ожидающие транзакции* — просмотр и управление транзакциями, требующими подтверждения\n"
            "• *Уведомления* — получение уведомлений о новых транзакциях с ваших адресов\n\n"
            "Используйте кнопки для навигации по боту.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    def show_address_menu(self, query):
        """Показывает меню управления адресами"""
        keyboard = [
            [InlineKeyboardButton("➕ Добавить адрес", callback_data="add_address")],
            [InlineKeyboardButton("🗑️ Удалить адрес", callback_data="remove_address_menu")],
            [InlineKeyboardButton("📋 Список адресов", callback_data="list_addresses")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(
            "🔑 *Управление адресами*\n\n"
            "Здесь вы можете добавить новые адреса или управлять уже добавленными.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    def request_address_input(self, query):
        """Запрашивает ввод Ethereum адреса"""
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_address_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(
            "Введите EVM адрес, который вы хотите добавить.\n"
            "Например: `0x742d35Cc6634C0532925a3b844Bc454e4438f44e`",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    def list_user_addresses(self, query, user_id):
        """Отображает список адресов пользователя"""
        response = requests.post(f"{self.api_base_url}/get_user_addresses", json={"user_id": user_id})
        json_response = response.json()
        logger.info(f"Адреса пользователя {user_id}: {json_response}")
        if json_response.get('error'):
            logger.error(f"Ошибка при получении адресов для пользователя {user_id}: {json_response['error']}")
        else:
            addresses = json_response.get('addresses', [])
        
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="manage_addresses")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if not addresses:
            text = "⚠️ У вас нет сохраненных адресов.\n\nДобавьте адрес с помощью кнопки 'Добавить адрес'."
        else:
            text = "🔑 *Ваши адреса:*\n\n"
            for address in addresses:
                text += f"`{address}`\n"
        
        query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    def show_remove_address_menu(self, query, user_id):
        """Показывает меню для удаления адресов"""
        response = requests.post(f"{self.api_base_url}/get_user_addresses", json={"user_id": user_id})
        json_response = response.json()
        logger.info(f"Адреса пользователя {user_id}: {json_response}")
        if json_response.get('error'):
            logger.error(f"Ошибка при получении адресов для пользователя {user_id}: {json_response['error']}")
        else:
            addresses = json_response.get('addresses', [])
        
        if not addresses:
            keyboard = [
                [InlineKeyboardButton("🔙 Назад", callback_data="manage_addresses")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            query.edit_message_text(
                "⚠️ У вас нет сохраненных адресов.",
                reply_markup=reply_markup
            )
            return
        
        # Создаем кнопки для каждого адреса
        keyboard = []
        for address in addresses:
            # Обрезаем адрес для callback_data, так как там ограничение на длину
            short_addr = address[:10] + "..." + address[-8:]
            keyboard.append([InlineKeyboardButton(short_addr, callback_data=f"remove_address_{address}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="manage_addresses")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(
            "Выберите адрес для удаления:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    def remove_user_address(self, query, user_id, address):
        """Удаляет выбранный адрес пользователя"""
        response = requests.post(f"{self.api_base_url}/remove_address", json={"user_id": user_id, "address": address})
        json_response = response.json()
        if json_response.get('error'):
            logger.error(f"Ошибка при удалении адреса {address} для пользователя {user_id}: {json_response['error']}")
            text = f"❌ Не удалось удалить адрес. Пожалуйста, попробуйте позже."
        else:
            text = f"✅ Адрес {address} успешно удален!"

        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="manage_addresses")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(
            text,
            reply_markup=reply_markup
        )
    
    def handle_text_input(self, update: Update, context: CallbackContext) -> None:
        """Обрабатывает текстовый ввод от пользователя"""
        user_id = str(update.effective_user.id)
        text = update.message.text
        
        # Убедимся, что пользователь сохранен в базе
        response = requests.post(f"{self.api_base_url}/new_user", json={"user_id": user_id, "chat_id": str(update.message.chat_id)})
        json_response = response.json()
        if json_response.get('error'):
            logger.error(f"Ошибка при создании пользователя {user_id}: {json_response['error']}")
            update.message.reply_text(f"❌ Произошла ошибка: {json_response['error']}")
        else:
            logger.info(f"Пользователь {user_id} успешно сохранен в базе")
        # Проверяем, ожидаем ли мы ввод
        awaiting_input = context.user_data.get('awaiting_input')
        
        if awaiting_input == 'address':
            # Обрабатываем ввод Ethereum адреса
            self.process_address_input(update, context)
            # Сбрасываем состояние
            context.user_data['awaiting_input'] = None
        else:
            # Показываем главное меню, если не ожидаем конкретного ввода
            keyboard = [
                [InlineKeyboardButton("🔑 Управление адресами", callback_data="manage_addresses")],
                [InlineKeyboardButton("📋 Ожидающие транзакции", callback_data="pending_transactions")],
                [InlineKeyboardButton("❓ Помощь", callback_data="help")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            update.message.reply_text(
                "Выберите действие с помощью кнопок ниже:",
                reply_markup=reply_markup
            )
    
    def process_address_input(self, update, context):
        """Обрабатывает ввод пользователем Ethereum-адреса"""
        user_id = str(update.effective_user.id)
        chat_id = str(update.effective_chat.id)
        message_text = update.message.text
        
        try:
            # Нормализация адреса
            try:
                address = normalize_address(message_text)
                logger.info(f"Получен ввод адреса от пользователя {user_id}: {address}")
            except Exception as e:
                logger.error(f"Ошибка при нормализации адреса: {str(e)}")
                update.message.reply_text(
                    "Неверный формат EVM-адреса. Пожалуйста, проверьте адрес и попробуйте снова."
                )
                return
            
            if not address:
                logger.error(f"Неверный формат адреса: {message_text}")
                update.message.reply_text(
                    "Неверный формат EVM-адреса. Пожалуйста, проверьте адрес и попробуйте снова."
                )
                return
            
            # Добавление адреса к пользователю
            try:
                response = requests.post(f"{self.api_base_url}/add_address", json={"user_id": user_id, "address": address})
                json_response = response.json()
                if json_response.get('error'):
                    logger.error(f"Ошибка при добавлении адреса {address} для пользователя {user_id}: {json_response['error']}")
                    update.message.reply_text(
                        f"❌ Произошла ошибка: {json_response['error']}"
                    )
                else:
                    logger.info(f"Адрес {address} успешно добавлен для пользователя {user_id}")
                
                # Получаем все адреса пользователя
                response = requests.post(f"{self.api_base_url}/get_user_addresses", json={"user_id": user_id})
                json_response = response.json()
                logger.info(f"Адреса пользователя {user_id}: {json_response}")
                if json_response.get('error'):
                    logger.error(f"Ошибка при получении адресов для пользователя {user_id}: {json_response['error']}")
                    update.message.reply_text(
                        f"❌ Произошла ошибка: {json_response['error']}"
                    )
                else:
                    addresses = json_response.get('addresses', [])
                    if not addresses:
                        address_list = "У вас пока нет сохраненных адресов."
                    else:
                        address_list = "\n".join([f"• `{addr}`" for addr in addresses])
                
                
                # Формируем клавиатуру
                keyboard = [
                    [InlineKeyboardButton("➕ Добавить еще адрес", callback_data="add_address")],
                    [InlineKeyboardButton("❌ Удалить адрес", callback_data="remove_address")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
                ]
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Формируем сообщение с адресами
                address_list = "\n".join([f"• `{addr}`" for addr in addresses]) if addresses else "У вас пока нет сохраненных адресов."
                
                update.message.reply_text(
                    f"✅ Адрес успешно добавлен!\n\nВаши адреса:\n{address_list}",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                
            except Exception as e:
                logger.error(f"Ошибка при добавлении адреса {address} для пользователя {user_id}: {str(e)}")
                update.message.reply_text(
                    "Произошла ошибка при сохранении адреса. Пожалуйста, попробуйте позже."
                )
                
        except Exception as e:
            logger.error(f"Ошибка при обработке ввода адреса: {str(e)}")
            update.message.reply_text(
                "Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже."
            )
    
    def show_pending_transactions(self, query):
        """Показывает список ожидающих транзакций"""
        user_id = str(query.from_user.id)
               
        # Получаем транзакции для этих адресов
        transactions = []
        response = requests.post(f"{self.api_base_url}/get_pending_transactions", json={"user_id": user_id})
        json_response = response.json()
        if json_response.get('error'):
            logger.error(f"Ошибка при получении транзакций для пользователя {user_id}: {json_response['error']}")
            update.message.reply_text(
                f"❌ Произошла ошибка: {json_response['error']}"
            )
        else:
            transactions = json_response.get('transactions', [])
            if not transactions:
                keyboard = [
                    # [InlineKeyboardButton("🔄 Обновить", callback_data="pending_transactions")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                query.edit_message_text(
                    "У вас пока нет ожидающих транзакций",
                    reply_markup=reply_markup
                )
            else:
                # Выводим транзакции из списка
                for transaction in transactions:
                    tx_id = transaction
                    tx_data = requests.post(f"{self.api_base_url}/get_transaction", json={"tx_id": tx_id})
                    json_response = tx_data.json()
                    if json_response.get('error'):
                        logger.error(f"Ошибка при получении транзакции {tx_id}: {json_response['error']}")
                    else:
                        tx = json_response.get('transaction', {})
                        pending = json_response.get('pending', False)
                        confirmed = json_response.get('confirmed', False)
                        
                    formatted_tx = format_transaction(tx_id, tx)
                    # отправляем отдельные сообщения в чат с каждой транзакцией
                    chat_id = query.effective_chat.id
                    keyboard = [
                        [InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_tx_{tx_id}"),
                         InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_tx_{tx_id}")
                        ],
                        [InlineKeyboardButton("🔙 Назад", callback_data="pending_transactions")],
                        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    self.updater.bot.send_message(
                        chat_id=chat_id,
                        text=formatted_tx,
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
        
    
    def process_transaction_action(self, query, tx_id, action):
        """Обрабатывает действия с транзакцией (подтверждение/отклонение)"""
        if action == "confirm":
            try:
                response = requests.post(f"{self.api_base_url}/confirm-transaction", json={"tx_id": tx_id})
                json_response = response.json()
                if json_response.get('error'):
                    success_message = f"❌ Произошла ошибка: {json_response['error']}"
                else:
                    success_message = "✅ Транзакция успешно подтверждена и отправлена в блокчейн!"
            except Exception as e:
                logger.error(f"Ошибка при подтверждении транзакции {tx_id}: {str(e)}")
                success_message = f"❌ Произошла ошибка: {str(e)}"
        
        elif action == "reject":
            try:
                response = requests.post(f"{self.api_base_url}/reject-transaction", json={"tx_id": tx_id})
                json_response = response.json()
                if json_response.get('error'):
                    success_message = f"❌ Произошла ошибка: {json_response['error']}"
                else:
                    success_message = "❌ Транзакция успешно отклонена."
            except Exception as e:
                logger.error(f"Ошибка при отклонении транзакции {tx_id}: {str(e)}")
                success_message = f"❌ Произошла ошибка: {str(e)}"
        else:
            success_message = "Неизвестное действие"

        # Создаем клавиатуру для возврата в основное меню
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить транзакции", callback_data="pending_transactions")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Обновляем сообщение
        query.edit_message_text(
            success_message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    def show_transaction_details(self, query, tx_id):
        """Показывает подробную информацию о транзакции"""
        response = requests.post(f"{self.api_base_url}/get_transaction", json={"tx_id": tx_id})
        json_response = response.json()
        if json_response.get('error'):
            logger.error(f"Ошибка при получении транзакции {tx_id}: {json_response['error']}")
            return
        else:
            tx = json_response.get('transaction', {})
            pending = json_response.get('pending', False)
            confirmed = json_response.get('confirmed', False)
            
            if pending:
                status = "Ожидает подтверждения"
            elif confirmed:
                status = "Подтверждена"
            else:
                status = "Отклонена"
            formatted_tx = format_transaction(tx_id, tx)
            keyboard = [
                [InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_tx_{tx_id}"),
                 InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_tx_{tx_id}")
                ],
                [InlineKeyboardButton("🔙 Назад", callback_data="pending_transactions")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            query.edit_message_text(
                f"📝 *Транзакция ({tx_id})*\n\n{formatted_tx}",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

    
    def error_handler(self, update: Update, context: CallbackContext) -> None:
        """Обрабатывает ошибки"""
        logger.error(f"Произошла ошибка: {context.error}")
        
        if update and update.effective_chat:
            keyboard = [
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            update.effective_chat.send_message(
                "⚠️ Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже.",
                reply_markup=reply_markup
            ) 