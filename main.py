import re
import requests

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


app = FastAPI(title="Real-Time Weather API")


# ==============================
# CORS
# ==============================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================
# Request Model
# ==============================

class UserQuery(BaseModel):
    message: str


# ==============================
# Extract City
# ==============================

def extract_city(message: str):

    message = message.strip()

    patterns = [
        r"weather\s+(?:in|of|at)\s+(.+)",
        r"wheather\s+(?:in|of|at)\s+(.+)",
        r"temperature\s+(?:in|of|at)\s+(.+)",
        r"temp\s+(?:in|of|at)\s+(.+)",
        r"forecast\s+(?:in|of|for|at)\s+(.+)",
        r"mausam\s+(?:in|of|ka)\s+(.+)",
        r"(.+?)\s+(?:weather|wheather)$",
        r"(.+?)\s+(?:temperature|temp)$",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            message,
            re.IGNORECASE
        )

        if match:

            city = match.group(1).strip()

            city = re.sub(
                r"[?.!,]+$",
                "",
                city
            ).strip()

            city = re.sub(
                r"\s+(today|now|right now|please|batao|btao)$",
                "",
                city,
                flags=re.IGNORECASE
            ).strip()

            if city:
                return city

    return None


# ==============================
# Get Weather
# ==============================

def get_weather(city):

    # Open-Meteo Geocoding
    geo_url = "https://geocoding-api.open-meteo.com/v1/search"

    geo_params = {
        "name": city,
        "count": 1,
        "language": "en",
        "format": "json"
    }

    geo_response = requests.get(
        geo_url,
        params=geo_params,
        timeout=10
    )

    geo_response.raise_for_status()

    geo_data = geo_response.json()

    if not geo_data.get("results"):

        return None

    location = geo_data["results"][0]

    latitude = location["latitude"]
    longitude = location["longitude"]

    location_name = location.get(
        "name",
        city
    )

    country = location.get(
        "country",
        ""
    )

    timezone = location.get(
        "timezone",
        "auto"
    )


    # Real-time weather
    weather_url = "https://api.open-meteo.com/v1/forecast"

    weather_params = {

        "latitude": latitude,

        "longitude": longitude,

        "current": (
            "temperature_2m,"
            "relative_humidity_2m,"
            "apparent_temperature,"
            "precipitation,"
            "rain,"
            "weather_code,"
            "wind_speed_10m"
        ),

        "timezone": timezone,

        "temperature_unit": "celsius",

        "wind_speed_unit": "kmh"
    }


    weather_response = requests.get(
        weather_url,
        params=weather_params,
        timeout=10
    )

    weather_response.raise_for_status()

    weather_data = weather_response.json()

    current = weather_data["current"]


    return {

        "city": location_name,

        "country": country,

        "temperature": current.get(
            "temperature_2m"
        ),

        "feels_like": current.get(
            "apparent_temperature"
        ),

        "humidity": current.get(
            "relative_humidity_2m"
        ),

        "precipitation": current.get(
            "precipitation"
        ),

        "rain": current.get(
            "rain"
        ),

        "weather_code": current.get(
            "weather_code"
        ),

        "wind_speed": current.get(
            "wind_speed_10m"
        ),

        "time": current.get(
            "time"
        )
    }


# ==============================
# Weather Description
# ==============================

def weather_description(code):

    descriptions = {

        0: "Clear sky",

        1: "Mainly clear",

        2: "Partly cloudy",

        3: "Overcast",

        45: "Fog",

        48: "Fog",

        51: "Light drizzle",

        53: "Moderate drizzle",

        55: "Dense drizzle",

        61: "Slight rain",

        63: "Moderate rain",

        65: "Heavy rain",

        71: "Slight snow",

        73: "Moderate snow",

        75: "Heavy snow",

        80: "Rain showers",

        81: "Rain showers",

        82: "Heavy rain showers",

        95: "Thunderstorm",

        96: "Thunderstorm",

        99: "Thunderstorm"
    }

    return descriptions.get(
        code,
        "Unknown"
    )


# ==============================
# Create Reply
# ==============================

def create_reply(weather):

    condition = weather_description(
        weather["weather_code"]
    )

    location = weather["city"]

    if weather["country"]:

        location = (
            f"{weather['city']}, "
            f"{weather['country']}"
        )


    return (

        f"🌤️ Current weather in "
        f"{location}\n\n"

        f"🌡️ Temperature: "
        f"{weather['temperature']}°C\n"

        f"🌡️ Feels like: "
        f"{weather['feels_like']}°C\n"

        f"☁️ Condition: "
        f"{condition}\n"

        f"💧 Humidity: "
        f"{weather['humidity']}%\n"

        f"🌧️ Rain: "
        f"{weather['rain']} mm\n"

        f"🌦️ Precipitation: "
        f"{weather['precipitation']} mm\n"

        f"💨 Wind speed: "
        f"{weather['wind_speed']} km/h\n"

        f"🕐 Updated: "
        f"{weather['time']}"
    )


# ==============================
# Home
# ==============================

@app.get("/")
def home():

    return {

        "status": "success",

        "message":
        "Real-Time Weather API is running!"
    }


# ==============================
# Chat API
# ==============================

@app.post("/api/chat")
def chat(payload: UserQuery):

    message = payload.message.strip()


    if not message:

        return {

            "status": "failed",

            "reply":
            "Please enter a message.",

            "weather_card": None
        }


    city = extract_city(message)


    if not city:

        return {

            "status": "success",

            "reply":
            "Please enter a city. Example: weather in Delhi",

            "weather_card": None
        }


    try:

        weather = get_weather(city)


        if weather is None:

            return {

                "status": "success",

                "reply":
                f"I could not find weather for {city}.",

                "weather_card": None
            }


        return {

            "status": "success",

            "reply":
            create_reply(weather),

            "weather_card":
            weather
        }


    except Exception as error:

        print(
            "WEATHER ERROR:",
            error
        )


        return {

            "status": "failed",

            "reply":
            "Unable to get live weather right now.",

            "weather_card": None,

            "error":
            str(error)
        }
