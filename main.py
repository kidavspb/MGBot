import telebot
from pdf2image import convert_from_path
from PIL import Image
import time
import os
import logging
from utils import *
from secret_file import *

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(module)s - %(levelname)s: %(lineno)d - %(message)s",
    handlers=[
        logging.FileHandler("MG.log"),
        logging.StreamHandler()
    ],
    datefmt='%d/%b %H:%M:%S',
)

bot = telebot.TeleBot(TOKEN)

while True:
    try:
        @bot.message_handler(commands=['start'])
        def welcome_message(message):
            logging.info(f"Start message from user @{message.from_user.username}")
            bot.send_message(message.chat.id, "Здравствуйте! Пожалуйста, выберите тип справки:\n\n"
                                              "<b>Электронная</b> — подходит для большинства случаев и делается практически мгновенно\n\n"
                                              "<b>Бумажная</b> — делается долго, потому что на нее ставится живая подпись с печатью "
                                              "(заказывайте только если уверены, что нужна именно бумажная)",
                             parse_mode='HTML', reply_markup=create_response_markup_type())


        def create_response_markup_type():
            markup = telebot.types.InlineKeyboardMarkup()
            markup.add(telebot.types.InlineKeyboardButton("💻 Электронная", callback_data="Digital"),
                       telebot.types.InlineKeyboardButton("📃 Бумажная", callback_data="Paper"))
            return markup


        def get_full_name(message, isDigital):
            if message.text == "/cancel":
                logging.info(f"Cancel message from user @{message.from_user.username}")
                bot.send_message(message.chat.id, "Отменено")
                return

            full_name = message.text
            bot.send_message(message.chat.id,
                             "Хорошо! Теперь, пожалуйста, введите причину для справки в формате «принимает участие в ...»")
            bot.register_next_step_handler(message, get_reason, full_name=full_name, isDigital=isDigital)


        def get_reason(message, full_name, isDigital):
            if message.text == "/cancel":
                logging.info(f"Cancel message from user @{message.from_user.username}")
                bot.send_message(message.chat.id, "Отменено")
                return

            start_length = len("принимает участие в")
            try:
                if len(message.text) <= start_length:
                    raise Exception("подозрительно короткая причина")
                if "\n" in message.text:
                    raise Exception("в причине не должно быть переносов строк")
                reason = message.text[0].lower() + message.text[1:]
                if reason[:start_length] != "принимает участие в":
                    raise Exception("причина должна начинаться со слов «принимает участие в ...»")
                reason = reason.strip(".")

            except Exception as e:
                bot.send_message(message.chat.id, f"Не подходит: {e}. Попробуйте еще раз")
                bot.register_next_step_handler(message, get_reason, full_name=full_name, isDigital=isDigital)
            else:
                bot.send_message(message.chat.id, "Почти готово! Осталось уточнить, когда было это мероприятие")
                bot.register_next_step_handler(message, get_date, full_name=full_name, reason=reason,
                                               isDigital=isDigital)


        def get_date(message, full_name, reason, isDigital):
            if message.text == "/cancel":
                logging.info(f"Cancel message from user @{message.from_user.username}")
                bot.send_message(message.chat.id, "Отменено")
                return

            words = "".join(c for c in message.text.replace(".", " ") if c.isalnum() or c == " ").strip().split()
            year = current_year = int(datetime.date.today().strftime("%Y"))

            try:
                day = int(words[0])
                if words[1].isdigit():
                    month = months[int(words[1]) - 1]
                elif words[1] in months:
                    month = words[1]
                else:
                    raise Exception("Месяц странный")

                if len(words) > 2:
                    year = int(words[2])
                    if year < 100:
                        year += current_year // 100 * 100
                    if abs(year - int(datetime.date.today().strftime("%Y"))) > 2:
                        raise Exception("Год странный")
            except Exception as e:
                bot.send_message(message.chat.id, f"Что-то не то с датой, попробуйте еще раз\n\n<code>{e}</code>",
                                 parse_mode='HTML')
                bot.register_next_step_handler(message, get_date, full_name=full_name, reason=reason, isDigital=isDigital)
            else:
                date = f"{day} {month} {year} года"

                user_username = "@" + message.from_user.username
                user_name = message.from_user.full_name
                info_text = f"📨 Заявка на справку от {user_username} ({user_name})"
                user_message = f"<b>Тип:</b> {'электронная' if isDigital else 'бумажная'}\n\n<b>ФИО:</b> {full_name}\n\n<b>Причина:</b> {reason}\n\n<b>Дата:</b> {date} "

                id_of_message_in_channel = bot.send_message(CHANNEL_ID, f"{info_text}\n\n{user_message}",
                                                            parse_mode='HTML').message_id
                bot.send_message(ADMIN_CHAT_ID,
                                 f"{message.chat.id} {int(time.time())} {id_of_message_in_channel}\n\n"
                                 f"{info_text}\n\n{user_message}",
                                 parse_mode='HTML', reply_markup=create_response_markup_approval())
                logging.info(f"Received {'digital' if isDigital else 'paper'} request from user @{message.from_user.username}")

                bot.send_message(message.chat.id,
                                 f"Спасибо! Справка отправлена на согласование, нужно немного подождать "
                                 f"(примерно {beautiful_time(count_average_time(isDigital)*1.5).split('. ')[0]}.)")


        def create_response_markup_approval():
            markup = telebot.types.InlineKeyboardMarkup()
            markup.add(telebot.types.InlineKeyboardButton("✅ Одобрить", callback_data="Approve"),
                       telebot.types.InlineKeyboardButton("❌ Отклонить", callback_data="Reject"))
            return markup


        @bot.callback_query_handler(func=lambda call: True)
        def callback(call):
            if call.data == "Digital":
                bot.send_message(call.message.chat.id,
                                 "Хороший выбор! Пожалуйста, введите теперь полное ФИО человека, которому нужна справка")
                bot.register_next_step_handler(call.message, get_full_name, isDigital=True)
            elif call.data == "Paper":
                bot.send_message(call.message.chat.id,
                                 "Хорошо! Пожалуйста, введите теперь полное ФИО человека, которому нужна справка")
                bot.register_next_step_handler(call.message, get_full_name, isDigital=False)

            elif call.data == "Reject":
                id_of_user = call.message.text.split('\n')[0].split(' ')[0]
                start_time = int(call.message.text.split('\n')[0].split(' ')[1])
                id_of_message_in_channel = call.message.text.split('\n')[0].split(' ')[2]
                isDigital = True if (call.message.text.split('Тип: '))[1].split('\n')[0] == "электронная" else False

                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text=call.message.text + "\n\n❌ Отклонено")
                bot.send_message(id_of_user, "К сожалению, справка не была согласована 🤷‍")
                logging.info(f"Reject request from user @{bot.get_chat(id_of_user).username}")

                count_average_time(isDigital, int(time.time() - start_time))
                bot.edit_message_text(chat_id=CHANNEL_ID, message_id=id_of_message_in_channel,
                                      text=call.message.text.split("\n\n", 1)[1] + "\n\n❌ Отклонено")
                bot.delete_message(chat_id=CHANNEL_ID, message_id=id_of_message_in_channel)

            elif call.data == "Approve":
                id_of_user = call.message.text.split('\n')[0].split(' ')[0]
                start_time = int(call.message.text.split('\n')[0].split(' ')[1])
                id_of_message_in_channel = call.message.text.split('\n')[0].split(' ')[2]

                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text=call.message.text + "\n\n✅ Одобрено")
                bot.send_message(id_of_user, "Ура, справка согласована 🎉")
                logging.info(f"Approve request from user @{bot.get_chat(id_of_user).username}")

                full_name = (call.message.text.split('ФИО: '))[1].split('\n')[0]
                reason = (call.message.text.split('Причина: '))[1].split('\n')[0]
                date = (call.message.text.split('Дата: '))[1].split('\n')[0]

                isDigital = True if (call.message.text.split('Тип: '))[1].split('\n')[0] == "электронная" else False

                create_PDF_certificate(full_name, reason, date, isDigital)

                if isDigital:
                    # Convert .pdf to .png
                    pages = convert_from_path('edited_file.pdf', 500)
                    pages[0].save('edited_file.png', 'PNG')

                    result_filename = full_name + ".pdf"

                    # Convert .png to .pdf
                    img = Image.open("edited_file.png")
                    img.save(result_filename)

                    # Send modified file to the user
                    with open(result_filename, "rb") as f:
                        bot.send_document(id_of_user, f)
                        logging.info(f"Send digital file to user @{bot.get_chat(id_of_user).username}")

                    count_average_time(isDigital, int(time.time() - start_time))
                    bot.edit_message_text(chat_id=CHANNEL_ID, message_id=id_of_message_in_channel,
                                          text=call.message.text.split("\n\n", 1)[1] + "\n\n✅ Выполнено")
                    bot.delete_message(chat_id=CHANNEL_ID, message_id=id_of_message_in_channel)
                else:
                    bot.send_message(id_of_user, "Уже печатаем справку. Сообщим, как только она будет готова 👌")
                    result_filename = "НА ПЕЧАТЬ - " + full_name + ".pdf"
                    os.rename("edited_file.pdf", result_filename)
                    with open(result_filename, "rb") as f:
                        bot.send_document(PRINTER_CHAT_ID, f,
                                          caption=call.message.text,
                                          reply_markup=telebot.types.InlineKeyboardMarkup().add(
                                              telebot.types.InlineKeyboardButton("🖨️ Напечатано", callback_data="Printed")))
                        logging.info(f"Send file to printer")

                    bot.edit_message_text(chat_id=CHANNEL_ID, message_id=id_of_message_in_channel,
                                          text=call.message.text.split("\n\n", 1)[1] + "\n\n🧑‍💻 Согласовано, но пока не напечатано")

                # Сlean up after ourselves
                os.remove(result_filename)

            elif call.data == "Printed":
                id_of_user = call.message.caption.split('\n')[0].split(' ')[0]
                start_time = int(call.message.caption.split('\n')[0].split(' ')[1])
                id_of_message_in_channel = call.message.caption.split('\n')[0].split(' ')[2]

                bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                         caption=call.message.caption + "\n\n🖨️ Напечатано")
                bot.send_message(id_of_user,
                                 "Cправка для " + (call.message.caption.split('ФИО: '))[1].split('\n')[0]
                                 + " готова, можно забирать в " + PLACE)
                logging.info("Send notification to user @" + bot.get_chat(id_of_user).username)

                count_average_time(False, int(time.time() - start_time))
                bot.edit_message_text(chat_id=CHANNEL_ID, message_id=id_of_message_in_channel,
                                      text=call.message.caption.split("\n\n", 1)[1] + "\n\n✅ Выполнено")
                bot.delete_message(chat_id=CHANNEL_ID, message_id=id_of_message_in_channel)


        logging.info("Bot running...")
        bot.polling(none_stop=True)

    except Exception as e:
        logging.error(e)
        bot.stop_polling()

        time.sleep(15)

        logging.info("Running again!")

# bot.polling()
