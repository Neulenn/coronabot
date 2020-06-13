#!/usr/bin/env python
import requests
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, executor, types, utils
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import re
import constants as c
import mysql.connector
from random import choice
import asyncio

bot = Bot(c.token)
dp = Dispatcher(bot, storage=MemoryStorage())


class Choose_city(StatesGroup): city = State()


@dp.message_handler(content_types=['new_chat_members'])
async def handle_text(message: types.Message):
    print(message.new_chat_members)
    if message.new_chat_members[-1].id == c.bot:
        conn = mysql.connector.connect(host=c.host, user=c.user, passwd=c.password, database=c.db)
        cursor = conn.cursor(buffered=True)
        existQuery = "SELECT EXISTS (SELECT ID FROM users WHERE chat_id=(%s))"
        insertQuery = "INSERT INTO users(chat_id) VALUES(%s)"
        cursor.execute(existQuery, [message.chat.id])
        exist = cursor.fetchone()[0]
        if exist == 1: conn.close()
        else:
            cursor.execute(insertQuery, [message.chat.id])
            conn.commit()
            conn.close()
            await bot.send_message(message.chat.id, "Активировано! Я буду присылать актуальную информацию по COVID-19 в Украине по мере обновления источника.")


@dp.message_handler(commands=['start'])
async def handle_text(message: types.Message):
    conn = mysql.connector.connect(host=c.host, user=c.user, passwd=c.password, database=c.db)
    cursor = conn.cursor(buffered=True)
    existQuery = "SELECT EXISTS (SELECT ID FROM users WHERE chat_id=(%s))"
    insertQuery = "INSERT INTO users(chat_id) VALUES(%s)"
    cursor.execute(existQuery, [message.chat.id])
    exist = cursor.fetchone()[0]
    if exist == 1: conn.close()
    else:
        cursor.execute(insertQuery, [message.chat.id])
        conn.commit()
        conn.close()
        await message.answer("Активировано! Я буду присылать актуальную информацию по COVID-19 в Украине по мере обновления источника.")


@dp.message_handler(commands=['on'])
async def handle_text(message: types.Message):
    conn = mysql.connector.connect(host=c.host, user=c.user, passwd=c.password, database=c.db)
    cursor = conn.cursor(buffered=True)
    updateQuery = "UPDATE users SET enable=1 WHERE chat_id=(%s)"
    cursor.execute(updateQuery, [message.chat.id])
    conn.commit()
    conn.close()
    await message.answer("Я включился")


@dp.message_handler(commands=['off'])
async def handle_text(message: types.Message):
    conn = mysql.connector.connect(host=c.host, user=c.user, passwd=c.password, database=c.db)
    cursor = conn.cursor(buffered=True)
    updateQuery = "UPDATE users SET enable=0 WHERE chat_id=(%s)"
    cursor.execute(updateQuery, [message.chat.id])
    conn.commit()
    conn.close()
    await message.answer("Я выключился")


@dp.message_handler(commands=['city'])
async def handle_text(message: types.Message):
    await message.reply("<b>Выбери свою область:</b>\n\n" + c.cityset, parse_mode="HTML")
    await Choose_city.city.set()


@dp.message_handler(regexp="^/\\d+$", state=Choose_city)
async def set_city(message: types.Message, state: FSMContext):
    await state.finish()
    city = int(message.text)
    if city not in range(1, 26):
        await message.answer("Неправильный ввод")
        return
    conn = mysql.connector.connect(host=c.host, user=c.user, passwd=c.password, database=c.db)
    cursor = conn.cursor(buffered=True)
    updateQuery = "UPDATE users SET city=(%s) WHERE chat_id=(%s)"
    cursor.execute(updateQuery, [city - 1, message.chat.id])
    conn.commit()
    conn.close()
    await message.answer(f"Выбрана область № {city}")


@dp.message_handler(commands=['users'])
async def handle_text(message: types.Message):
    if message.from_user.id == c.admin:
        conn = mysql.connector.connect(host=c.host, user=c.user, passwd=c.password, database=c.db)
        cursor = conn.cursor(buffered=True)
        selectQuery = "SELECT chat_id FROM users"
        cursor.execute(selectQuery)
        result = cursor.fetchall()
        conn.close()
        text = ""
        for user in result:
            text += f"[{user[0]}](tg://user?id={user[0]})\n"
        await message.answer(text, parse_mode="Markdown")


async def send(text, city=None, sticker=None):
    conn = mysql.connector.connect(host=c.host, user=c.user, passwd=c.password, database=c.db)
    cursor = conn.cursor(buffered=True)
    selectCityQuery = "SELECT chat_id FROM users WHERE city=(%s) AND enable=1"
    selectAllQuery = "SELECT chat_id FROM users WHERE enable=1"
    if city is None: cursor.execute(selectAllQuery)
    else: cursor.execute(selectCityQuery, [city])
    try:
        result = cursor.fetchall()
    except IndexError:
        conn.close()
        return
    conn.close()
    for user in result:
        try:
            await bot.send_message(user[0], text, parse_mode="Markdown")
            if sticker is not None: await bot.send_sticker(user[0], c.stickers[sticker])
        except utils.exceptions.BotBlocked: pass
        except utils.exceptions.BotKicked: pass
        except utils.exceptions.UserDeactivated: pass
        except utils.exceptions.ChatNotFound: pass


async def check_updates_loop():
    res = requests.get('https://www.worldometers.info/coronavirus/#countries').text
    html = BeautifulSoup(res, 'html.parser')
    for row in html.select("tr"):
        if row.text.find("Ukraine") != -1:
            data = str(row.text)[1:].split("\n")
            ill = str(data[2]).replace(",", "")
            with open("count/save.txt", "r") as f:
                save = str(f.read())
            if ill == save:
                return
            else:
                sticker = False
                with open("count/tests.txt", "r") as f: tests = str(f.read())
                with open("count/tests.txt", "wt") as f: f.write(str(data[11]).replace(',', ''))
                text = "🦠 *Короновости!* 🦠\n\n😷 Всего случаев: _{} ({})_\n💀 Всего смертей: _{} ({})_\n" \
                       "😇 Всего вылечено: _{} ({})_\n🤒 Больных сейчас: _{}_\n😵 В критич. состоянии: _{}_\n🔬 Проведено тестов: _{}_" \
                       .format(data[2], data[3], data[4], data[5], data[6], data[7], data[8], data[9], data[12])
                try:
                    tests_diff = int(data[11].replace(',', '')) - int(tests)
                    text += f" _(+{tests_diff})_"
                    percent = '%.2f' % float(int(str(data[3]).replace(',', '')[1:]) / int(tests_diff) * 100)
                    text += f"\n📈 Отношение обнаруженных случаев: _{percent}%_"
                except ZeroDivisionError: pass
                except ValueError as e: print(e)
                with open("count/save.txt", "wt") as f:
                    f.write(ill)
                if int(save) // 5000 < int(ill) // 5000:
                    text += f"\n\nОчередных 5000 заболевших! {choice(c.quotes_5000)}...!"
                    sticker = True
                with open("count/joke.txt", "r") as f: joke = int(f.read()) + 1
                text += "\n\n_" + str(c.quotes[joke % len(c.quotes)]) + "_"
                with open("count/joke.txt", "wt") as f: f.write(str(joke))
                if sticker:
                    with open("count/sticker.txt", "r") as f: n = int(f.read()) + 1
                    with open("count/sticker.txt", "wt") as f: f.write(str(n))
                    await send(text, sticker=n % len(c.stickers))
                else: await send(text)
                await asyncio.sleep(1800)
                await check_city()
            break


async def check_city():
    link = 'https://moz.gov.ua/article/news/operativna-informacija-pro-poshirennja-koronavirusnoi-infekcii-2019-ncov-1'
    res = requests.get(link).text
    html = BeautifulSoup(res, 'html.parser')
    try: data = html.select(".editor")[0]
    except IndexError:
        await bot.send_message(c.admin, f"[Сайт]({link}) не работает", parse_mode="Markdown")
        return
    i = 0
    for city in c.cities:
        index = data.text.find(city)
        num = re.search("\\d+", str(data.text)[index:]).group()
        with open("count/save.txt", "r") as f:
            save = str(f.read())
        percent = '%.2f' % float(int(num) / int(save) * 100)
        text = f"🦠 *{c.citytext[i]}* 🦠\n\n😷 Всего случаев: _{num} ({percent}%)_"
        await send(text, city=i)
        i += 1


if __name__ == "__main__":
    dp.loop.create_task(check_updates_loop())
    executor.start_polling(dp, skip_updates=True)
