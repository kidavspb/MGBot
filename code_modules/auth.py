from functools import wraps
from secret_file import *
from code_modules.filehandling import *


@bot.message_handler(commands=['authorize'])
def authorize(message):
    if message.from_user.id in users_manager.get_data():
        bot.reply_to(message, "Вы уже авторизованы.")
    else:
        request_phone_number(message)


def request_phone_number(message):
    keyboard = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
    button_phone = telebot.types.KeyboardButton(text="📱 Отправить номер телефона", request_contact=True)
    keyboard.add(button_phone)
    bot.send_message(message.chat.id, "Пожалуйста, отправьте ваш номер телефона для авторизации.",
                     reply_markup=keyboard)


@bot.message_handler(content_types=['contact'])
def contact_handler(message):
    if message.contact is not None:
        user_id = message.contact.user_id
        if user_id == message.from_user.id:  # Проверяем, что контакт принадлежит пользователю, который отправил его
            users_manager.add_new_user(user_id, message.from_user.username, message.contact.phone_number)
            bot.send_message(message.chat.id, "✅ Теперь вы авторизованы, можете продолжить использование бота.",
                             reply_markup=telebot.types.ReplyKeyboardRemove())
        else:
            bot.send_sticker(message.chat.id,
                             "CAACAgIAAxkBAAEKtrdlTJWVLWbM59-4Qbz5OlSnCDoYFQACjDkAAkmraUr9LAf5qT-zIzME")  # из пацанов
            bot.reply_to(message, "Номер телефона не соответствует вашему аккаунту.")
    else:
        bot.send_message(message.chat.id, "Не удалось получить номер телефона.")


def is_authorized(message):
    return message.from_user.id in users_manager.get_data()


def is_blocked(message):
    return users_manager.get_data()[message.from_user.id]["blocked"]


def is_cancel_command(message):
    return message.text == '/cancel'


def check_message(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        message = args[0]
        if not is_authorized(message):
            bot.send_message(message.chat.id,
                             "Вы не авторизованы для использования этого бота. Чтобы авторизоваться — /authorize"
                             "\n\nБез авторизации работает — @mp3_2_voice_bot"
                             )
            return
        if is_blocked(message):
            return
        if is_cancel_command(message):
            logging.info(f"Cancel message from user @{message.from_user.username}")
            bot.send_message(message.chat.id, "Отменено", reply_markup=telebot.types.ReplyKeyboardRemove())
            return
        else:
            return func(*args, **kwargs)

    return wrapper


@bot.message_handler(commands=['block'], func=lambda message: message.from_user.id == ADMIN_CHAT_ID)
def block_user(message):
    splitted_text = message.text.split(maxsplit=2)
    if len(splitted_text) == 2:
        user_id = int(splitted_text[1])
        if users_manager.block_user(user_id):
            username = users_manager.get_data()[user_id]["username"]
            logging.info(f"User @{username} was blocked by @{message.from_user.username}")
            bot.send_message(message.from_user.id, f"Пользователь @{username} заблокирован")
        else:
            bot.send_message(message.from_user.id, f"Что-то пошло не так. Скорее всего ошибка в <code>user_id</code>",
                             parse_mode="HTML")
    else:
        bot.send_message(message.from_user.id, "Неверный формат команды: `/block user_id`", parse_mode="MarkdownV2")


@bot.message_handler(commands=['unblock'], func=lambda message: message.from_user.id == ADMIN_CHAT_ID)
def unblock_user(message):
    splitted_text = message.text.split(maxsplit=2)
    if len(splitted_text) == 2:
        user_id = int(splitted_text[1])
        if users_manager.unblock_user(user_id):
            username = users_manager.get_data()[user_id]["username"]
            logging.info(f"User @{username} was unblocked by @{message.from_user.username}")
            bot.send_message(message.from_user.id, f"Пользователь @{username} разблокирован")
        else:
            bot.send_message(message.from_user.id, f"Что-то пошло не так. Скорее всего ошибка в <code>user_id</code>",
                             parse_mode="HTML")
    else:
        bot.send_message(message.from_user.id, "Неверный формат команды: `/unblock user_id`", parse_mode="MarkdownV2")
