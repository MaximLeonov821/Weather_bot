import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import requests
from datetime import datetime
import json
import os
import random
import logging
from dotenv import load_dotenv

logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    encoding='utf-8'
)

load_dotenv()
VK_TOKEN = os.getenv('VK_TOKEN')
WEATHER_API_KEY = os.getenv('WEATHER_API_KEY')
GROUP_ID = os.getenv('GROUP_ID')

vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)

user_states = {}

def get_weather(city: str, period: str = 'today') -> str:
    try:
        base_url = "http://api.openweathermap.org/data/2.5/"
        params = {
            'q': city,
            'appid': WEATHER_API_KEY,
            'units': 'metric',
            'lang': 'ru'
        }

        if period == 'today':
            url = f"{base_url}weather"
            response = requests.get(url, params=params, timeout=5).json()

            if response.get('cod') != 200:
                return None
            return format_current_weather(response)

        elif period == 'week':
            url = f"{base_url}forecast"
            response = requests.get(url, params=params, timeout=5).json()

            if response.get('cod') != '200':
                return None
            return format_forecast(response)

    except Exception as e:
        logging.error(f"[ОШИБКА API]: {e}")
        return None

def format_current_weather(data: dict) -> str:
    return (
        f"🌤 Погода в {data['name']}:\n"
        f"🌡 {data['main']['temp']:.1f}°C (ощущается {data['main']['feels_like']:.1f}°C)\n"
        f"💧 Влажность: {data['main']['humidity']}%\n"
        f"🌬 Ветер: {data['wind']['speed']} м/с\n"
        f"☁️ {data['weather'][0]['description'].capitalize()}"
    )

def format_forecast(data: dict) -> str:
    forecast = {}
    for item in data['list']:
        date = item['dt_txt'].split()[0]
        hour = int(item['dt_txt'].split()[1].split(':')[0])
        if 11 <= hour <= 14:
            if date not in forecast:
                forecast[date] = {
                    'min': item['main']['temp_min'],
                    'max': item['main']['temp_max'],
                    'desc': item['weather'][0]['description']
                }

    result = ["📆 Прогноз на ближайшие 2 дня:"]
    for date, values in list(forecast.items())[:2]:
        day_name = datetime.strptime(date, '%Y-%m-%d').strftime('%a (%d.%m)')
        result.append(f"{day_name}: {values['min']:.1f}..{values['max']:.1f}°C, {values['desc'].capitalize()}")

    return "\n".join(result)

def create_keyboard():
    return {
        "one_time": False,
        "buttons": [
            [{
                "action": {
                    "type": "text",
                    "label": "🌤 Погода сейчас",
                    "payload": "{\"type\":\"current\"}"
                },
                "color": "positive"
            }],
            [{
                "action": {
                    "type": "text",
                    "label": "📅 Погода на 2 дня",
                    "payload": "{\"type\":\"forecast\"}"
                },
                "color": "primary"
            }]
        ]
    }

def send_message(user_id: int, text: str):
    try:
        vk.messages.send(
            user_id=user_id,
            message=text,
            random_id=random.randint(1, 2**31 - 1),
            keyboard=json.dumps(create_keyboard())
        )
        logging.info(f"✅ Сообщение отправлено пользователю {user_id}: {text}")
        print(f"[SEND] -> Пользователю {user_id}: {text}")
    except Exception as e:
        logging.error(f"[ОШИБКА ОТПРАВКИ]: {e}")
        print(f"[ERROR] Ошибка при отправке: {e}")

print("Бот запущен и работает корректно!")
logging.info("Бот запущен успешно.")

for event in longpoll.listen():
    if event.type == VkBotEventType.MESSAGE_NEW:
        try:
            msg = event.object.message
            user_id = msg['from_id']
            text = msg['text'].strip().lower()

            logging.info(f"📩 Сообщение от {user_id}: {text}")
            print(f"[RECV] <- {user_id}: {text}")

            user_state = user_states.get(user_id)

            if user_state == 'current_weather':
                weather = get_weather(text, 'today')
                if weather:
                    send_message(user_id, weather)
                else:
                    send_message(user_id, f"❌ Не удалось получить данные для города '{text}'")
                user_states[user_id] = None
                continue

            elif user_state == 'forecast_weather':
                weather = get_weather(text, 'week')
                if weather:
                    send_message(user_id, weather)
                else:
                    send_message(user_id, f"❌ Не удалось получить данные для города '{text}'")
                user_states[user_id] = None
                continue

            text = text.lower()
            
            if text in ['привет', 'начать', 'старт']:
                greeting = (
                    "👋 Привет! Я бот прогноза погоды.\n"
                    "Вы можете:\n"
                    "• Получить 🌤 текущую погоду — нажмите на кнопку «Погода сейчас»\n"
                    "• Узнать 📅 прогноз на 2 дня вперед — нажмите «Погода на 2 дня»\n\n"
                    "📌 Также можно написать вручную, например:\n"
                    "• `погода Москва сейчас`\n"
                    "• `погода Москва на 2 дня`"
                )
                send_message(user_id, greeting)
                user_states[user_id] = None
                continue

            elif text in ['🌤 погода сейчас', 'погода сейчас', 'погода на сегодня']:
                user_states[user_id] = 'current_weather'
                send_message(user_id, "Введите название города для текущей погоды:")
                continue

            elif text in ['📅 погода на 2 дня', 'прогноз погоды', 'погода на 2 дня' ]:
                user_states[user_id] = 'forecast_weather'
                send_message(user_id, "Введите название города для прогноза на 2 дня:")
                continue

            elif text.startswith('погода'):
                parts = text.split(maxsplit=2)
                city = parts[1] if len(parts) > 1 else None
                period = 'today'

                if len(parts) == 3 and '2' in parts[2]:
                    period = 'week'

                if not city:
                    send_message(user_id, "ℹ️ Введите: погода [город] [Погода сейчас/Погода на 2 дня]")
                else:
                    weather_info = get_weather(city, period)
                    if weather_info:
                        send_message(user_id, weather_info)
                    else:
                        send_message(user_id, f"❌ Не удалось получить данные для города '{city}'")
                user_states[user_id] = None
                continue

            send_message(user_id, "Я бот погоды. Введите название города или выберите действие:")
            user_states[user_id] = None

        except Exception as e:
            logging.error(f"[ОШИБКА ОБРАБОТКИ СООБЩЕНИЯ]: {e}")
            print(f"[ERROR] Ошибка обработки: {e}")
