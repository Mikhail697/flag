from aiogram import Bot, Dispatcher, executor, types
from aiogram import *
from aiogram.types import *
TOKEN = "8174108813:AAHvhCCyAcy5f4ZFo8Qh5eDBMYUteGftxyI" # Токен бота
admin_id = 7943900933 # ИД админа (узнать можно в боте @username_to_id_bot )

boty = Bot(token=TOKEN)
dp = Dispatcher(boty)


@dp.message_handler(commands=['start'])
async def process_start_command(message: types.Message):
    if message['from'].id == admin_id:
        await message.answer(f"Hi, admin") # Если сообщение от админа
    else:
        await message.answer(f"Привет {message['from'].first_name}! Если у тебя есть предложение, скриптик, новость или идея - напиши мне!")  # пишет всем, кто не админ


@dp.message_handler()
async def process_start_command(message: types.Message):
    if message.reply_to_message == None:
        if '/start' not in message.text:
            await boty.forward_message(admin_id, message.from_user.id, message.message_id)
            await message.answer('Спасибо за сообщение! Я уже передал админам паблика эту инфу!')
    else:
        if message['from'].id == admin_id:
            if message.reply_to_message.forward_from.id:
                await boty.send_message(message.reply_to_message.forward_from.id, message.text)
        else:
            await message.answer('На сообщения нельзя отвечать!') # Пишет всем юзерам, которые отвечают на сообщения


@dp.message_handler(content_types=['photo']) # повторение, только с фото
async def handle_docs_photo(message):
    await boty.forward_message(admin_id, message.from_user.id, message.message_id)
    await message.answer('Спасибо что с нами! Передал админам паблика!')


@dp.message_handler(content_types=['document']) # тут с файлом
async def handle_docs_photo(message):
    await boty.forward_message(admin_id, message.from_user.id, message.message_id)
    await message.answer('Файлик? Спасибо, передал админам паблика)')


if __name__ == '__main__':
    print("starting")
    executor.start_polling(dp)
