import telebot
import wikipedia
import re
import os
import json
import time
import requests
import base64
from PIL import Image
from io import BytesIO
from config import TOKEN, API_FB, SECRET_KEY


bot = telebot.TeleBot(TOKEN)
wikipedia.set_lang("ru")


user_stats = {}


class Text2ImageAPI:
    def __init__(self, url, api_key, secret_key):
        self.URL = url
        self.AUTH_HEADERS = {
            'X-Key': f'Key {api_key}',
            'X-Secret': f'Secret {secret_key}',
        }

    def get_model(self):
        response = requests.get(self.URL + 'key/api/v1/models', headers=self.AUTH_HEADERS)
        data = response.json()
        return data[0]['id']

    def generate(self, prompt, model, images=1, width=1024, height=1024):
        params = {
            "type": "GENERATE",
            "numImages": images,
            "width": width,
            "height": height,
            "generateParams": {
                "query": f"{prompt}"
            }
        }
        data = {
            'model_id': (None, model),
            'params': (None, json.dumps(params), 'application/json')
        }
        response = requests.post(self.URL + 'key/api/v1/text2image/run', headers=self.AUTH_HEADERS, files=data)
        data = response.json()
        return data['uuid']

    def check_generation(self, request_id, attempts=10, delay=10):
        while attempts > 0:
            response = requests.get(self.URL + 'key/api/v1/text2image/status/' + request_id, headers=self.AUTH_HEADERS)
            data = response.json()
            if data['status'] == 'DONE':
                return data['images']
            attempts -= 1
            time.sleep(delay)

    def save_image(self, base64_string, file_path):
        decoded_data = base64.b64decode(base64_string)
        image = Image.open(BytesIO(decoded_data))
        image.save(file_path)


def getwiki(s):
    try:
        ny = wikipedia.page(s)
        wikitext = ny.content[:1000]
        wikimas = wikitext.split('.')
        wikimas = wikimas[:-1]
        wikitext2 = ''
        for x in wikimas:
            if not ('==' in x):
                if len((x.strip())) > 3:
                    wikitext2 = wikitext2 + x + '.'
            else:
                break
        wikitext2 = re.sub('$[^()]*$', '', wikitext2)
        wikitext2 = re.sub('\{[^\{\}]*\}', '', wikitext2)
        return wikitext2
    except Exception as e:
        return 'В энциклопедии нет информации об этом'


def update_stats(user_id, action):
    if user_id not in user_stats:
        user_stats[user_id] = {'image_requests': 0, 'wiki_requests': 0}
    user_stats[user_id][action] += 1


def create_keyboard():
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(telebot.types.KeyboardButton("Генерировать изображение"),
                 telebot.types.KeyboardButton("Получить информацию из Wikipedia"),
                 telebot.types.KeyboardButton("Статистика"))
    return keyboard


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Я бот для генерации изображений и поиска информации в Wikipedia.\nВыберите действие:", reply_markup=create_keyboard())

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.chat.id
    if message.text == "Генерировать изображение":
        prompt_message = bot.send_message(user_id, "Введите текстовый запрос (начните с '!' для генерации изображения):")
        bot.register_next_step_handler(prompt_message, handle_image_generation)
    elif message.text == "Получить информацию из Wikipedia":
        info_message = bot.send_message(user_id, "Введите слово или фразу, чтобы получить информацию:")
        bot.register_next_step_handler(info_message, handle_wiki_request)
    elif message.text == "Статистика":
        stats = user_stats.get(user_id, {'image_requests': 0, 'wiki_requests': 0})
        bot.send_message(user_id, f"Статистика:\nИзображения запрошены: {stats['image_requests']}\nWikipedia запросы: {stats['wiki_requests']}")
    else:
        bot.send_message(user_id, "Пожалуйста, выберите одно из действий на клавиатуре.")

def handle_image_generation(message):
    prompt = message.text[1:] 
    typing_message = bot.send_message(message.chat.id, "Генерирую картинку..")

    api = Text2ImageAPI('https://api-key.fusionbrain.ai/', API_FB, SECRET_KEY)
    model_id = api.get_model()
    uuid = api.generate(prompt, model_id)
    images = api.check_generation(uuid)[0]
    api.save_image(images, 'decoded_image.jpg')

    with open('decoded_image.jpg', 'rb') as photo:
        bot.send_photo(message.chat.id, photo)

    os.remove('decoded_image.jpg')
    bot.delete_message(message.chat.id, typing_message.message_id)

    update_stats(message.chat.id, 'image_requests')  

def handle_wiki_request(message):
    result = getwiki(message.text)
    bot.send_message(message.chat.id, result)
    update_stats(message.chat.id, 'wiki_requests')  

bot.polling(none_stop=True, interval=0)