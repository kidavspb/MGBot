from pdf2image import convert_from_path
from PIL import Image
import time
import os
from code_modules.utils import *
from code_modules.auth import *

while True:
    try:
        @bot.message_handler(commands=['start'])
        @check_message
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


        @check_message
        def get_full_name(message, isDigital):
            full_name = message.text
            bot.send_message(message.chat.id,
                             "Хорошо! Теперь, пожалуйста, введите причину для справки в формате «принимает участие в ...»")
            bot.register_next_step_handler(message, get_reason, full_name=full_name, isDigital=isDigital)


        @check_message
        def get_reason(message, full_name, isDigital):
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


        @check_message
        def get_date(message, full_name, reason, isDigital):
            words = "".join(c for c in message.text.replace(".", " ") if
                            c.isalnum() or c == " ").strip().split()  # список слов, которые были в исходной строке, но без знаков препинания и точек
            year = current_year = int(datetime.date.today().strftime("%Y"))

            try:
                day = int(words[0])
                if day < 1 or day > 31:
                    raise Exception("День странный")

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
                bot.register_next_step_handler(message, get_date, full_name=full_name, reason=reason,
                                               isDigital=isDigital)
            else:
                date = f"{day} {month} {year} года"
                make_request(message, full_name, reason, date, isDigital)


        def make_request(message, full_name, reason, date, isDigital):
            user_username = "@" + message.from_user.username
            user_name = message.from_user.full_name
            user_id = message.chat.id
            info_text = f"📨 Заявка на справку от {user_username} ({user_name})"

            if (int(users_manager.get_data()[user_id]["counter"]["digital"]["approved"]) +
                    int(users_manager.get_data()[user_id]["counter"]["paper"]["approved"]) == 0):
                info_text += "\n⚠️ Еще не была одобрена ни одна справка"

            user_message = f"<b>Тип:</b> {'электронная' if isDigital else 'бумажная'}\n\n<b>ФИО:</b> {full_name}\n\n<b>Причина:</b> {reason}\n\n<b>Дата:</b> {date} "

            id_of_message_in_channel = bot.send_message(CHANNEL_ID, f"{info_text}\n\n{user_message}",
                                                        parse_mode='HTML').message_id
            bot.send_message(ADMIN_CHAT_ID,
                             f"{user_id} {int(time.time())} {id_of_message_in_channel}\n\n"
                             f"{info_text}\n\n{user_message}",
                             parse_mode='HTML', reply_markup=create_response_markup_approval())
            logging.info(
                f"Received {'digital' if isDigital else 'paper'} request from user {user_username}")

            bot.send_message(user_id,
                             f"Спасибо! Справка отправлена на согласование, нужно немного подождать "
                             f"(примерно {beautiful_time(count_average_time(isDigital) * 1.5).split('. ')[0].strip('.')}.)")


        def create_response_markup_approval():
            markup = telebot.types.InlineKeyboardMarkup()
            markup.add(telebot.types.InlineKeyboardButton("✅ Одобрить", callback_data="Approve"),
                       telebot.types.InlineKeyboardButton("❌ Отклонить", callback_data="Reject"))
            return markup


        @check_message
        def rejection(message, system_message, request_message):
            if message.text == "↩️ Отменить":
                bot.delete_message(chat_id=system_message.chat.id, message_id=system_message.message_id)
                bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
                return
            elif message.text == "⏩ Пропустить":
                rejection_reason = ""
            else:
                rejection_reason = message.text

            user_id = int(request_message.text.split('\n')[0].split(' ')[0])
            start_time = int(request_message.text.split('\n')[0].split(' ')[1])
            id_of_message_in_channel = request_message.text.split('\n')[0].split(' ')[2]
            isDigital = True if (request_message.text.split('Тип: '))[1].split('\n')[0] == "электронная" else False
            FIO = (request_message.text.split('ФИО: '))[1].split('\n')[0]

            appendix = "\n\n❌ Отклонено"
            if rejection_reason:
                appendix += f" ({rejection_reason})"

            bot.edit_message_text(chat_id=request_message.chat.id,
                                  message_id=request_message.message_id,
                                  text=request_message.text + appendix)
            bot.send_message(message.chat.id,
                             "Заявка отклонена" + (f" ({rejection_reason})" if rejection_reason else ""),
                             reply_to_message_id=request_message.message_id,
                             reply_markup=telebot.types.ReplyKeyboardRemove())

            bot.send_message(user_id, f"К сожалению, справка для {FIO} не была согласована "
                             + ("🤷‍" if not rejection_reason else f"({rejection_reason})"))
            logging.info(f"Reject request from user @{bot.get_chat(user_id).username}"
                         + (f' with reason "{rejection_reason}"' if rejection_reason else " without reason"))

            count_average_time(isDigital, int(time.time() - start_time))
            users_manager.increment(user_id, "digital" if isDigital else "paper", "rejected")
            bot.edit_message_text(chat_id=CHANNEL_ID, message_id=id_of_message_in_channel,
                                  text=request_message.text.split("\n\n", 1)[1] + appendix)
            bot.delete_message(chat_id=CHANNEL_ID, message_id=id_of_message_in_channel)


        @bot.callback_query_handler(func=lambda call: True)
        def callback(call):
            if call.data == "Digital":
                bot.delete_message(chat_id=call.message.chat.id,
                                   message_id=call.message.message_id)
                bot.send_message(call.message.chat.id,
                                 "Хороший выбор! Пожалуйста, введите теперь полное ФИО человека, которому нужна справка")
                bot.register_next_step_handler(call.message, get_full_name, isDigital=True)
            elif call.data == "Paper":
                bot.delete_message(chat_id=call.message.chat.id,
                                   message_id=call.message.message_id)
                bot.send_message(call.message.chat.id,
                                 "Хорошо! Пожалуйста, введите теперь полное ФИО человека, которому нужна справка")
                bot.register_next_step_handler(call.message, get_full_name, isDigital=False)

            elif call.data == "Reject":
                reject_menu = telebot.types.ReplyKeyboardMarkup(True, True)
                btn1 = telebot.types.KeyboardButton("↩️ Отменить")
                btn2 = telebot.types.KeyboardButton("⏩ Пропустить")
                reject_menu.add(btn1, btn2)

                system_message = bot.send_message(call.message.chat.id, "Пожалуйста, введите причину отклонения",
                                                  reply_markup=reject_menu)
                bot.register_next_step_handler(call.message, rejection, system_message, request_message=call.message)

            elif call.data == "Approve":
                user_id = int(call.message.text.split('\n')[0].split(' ')[0])
                user_username = bot.get_chat(user_id).username

                start_time = int(call.message.text.split('\n')[0].split(' ')[1])
                id_of_message_in_channel = call.message.text.split('\n')[0].split(' ')[2]

                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text=call.message.text + "\n\n✅ Одобрено")
                bot.send_message(user_id, "Ура, справка согласована 🎉")
                logging.info(f"Approve request from user @{user_username}")

                full_name = (call.message.text.split('ФИО: '))[1].split('\n')[0]
                reason = (call.message.text.split('Причина: '))[1].split('\n')[0]
                date = (call.message.text.split('Дата: '))[1].split('\n')[0]

                isDigital = True if (call.message.text.split('Тип: '))[1].split('\n')[0] == "электронная" else False

                create_PDF_certificate(full_name, reason, date, isDigital)

                if isDigital:
                    bot.send_chat_action(user_id, "upload_document")

                    # Convert .pdf to .png
                    pages = convert_from_path(path_to_docs_file + 'edited_file.pdf', 500)
                    pages[0].save(path_to_docs_file + 'edited_file.png', 'PNG')

                    result_filename = full_name + ".pdf"

                    # Convert .png to .pdf
                    img = Image.open(path_to_docs_file + "edited_file.png")
                    img.save(path_to_docs_file + result_filename)

                    # Send modified file to the user
                    with open(path_to_docs_file + result_filename, "rb") as f:
                        bot.send_document(user_id, f)
                        logging.info(f"Send digital file to user @{bot.get_chat(user_id).username}")

                    count_average_time(isDigital, int(time.time() - start_time))
                    users_manager.increment(user_id, "digital", "approved")
                    bot.edit_message_text(chat_id=CHANNEL_ID, message_id=id_of_message_in_channel,
                                          text=call.message.text.split("\n\n", 1)[1] + "\n\n✅ Выполнено")
                    bot.delete_message(chat_id=CHANNEL_ID, message_id=id_of_message_in_channel)
                else:
                    bot.send_message(user_id, "Уже печатаем справку. Сообщим, как только она будет готова 👌")
                    result_filename = "НА ПЕЧАТЬ - " + full_name + ".pdf"
                    os.rename(path_to_docs_file + "edited_file.pdf", path_to_docs_file + result_filename)
                    with open(path_to_docs_file + result_filename, "rb") as f:
                        bot.send_document(PRINTER_CHAT_ID, f,
                                          caption=call.message.text,
                                          reply_markup=telebot.types.InlineKeyboardMarkup().add(
                                              telebot.types.InlineKeyboardButton("🖨️ Напечатано",
                                                                                 callback_data="Printed")))
                        logging.info(f"Send file to printer")

                    bot.edit_message_text(chat_id=CHANNEL_ID, message_id=id_of_message_in_channel,
                                          text=call.message.text.split("\n\n", 1)[
                                                   1] + "\n\n🧑‍💻 Согласовано, но пока не напечатано")

                # Сlean up after ourselves
                os.remove(path_to_docs_file + result_filename)

            elif call.data == "Printed":
                user_id = int(call.message.caption.split('\n')[0].split(' ')[0])
                start_time = int(call.message.caption.split('\n')[0].split(' ')[1])
                id_of_message_in_channel = call.message.caption.split('\n')[0].split(' ')[2]

                bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                         caption=call.message.caption + "\n\n🖨️ Напечатано")
                bot.send_message(user_id,
                                 "Cправка для " + (call.message.caption.split('ФИО: '))[1].split('\n')[0]
                                 + " готова, можно забирать в " + PLACE)
                logging.info("Send notification to user @" + bot.get_chat(user_id).username)

                count_average_time(False, int(time.time() - start_time))
                users_manager.increment(user_id, "paper", "approved")
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
