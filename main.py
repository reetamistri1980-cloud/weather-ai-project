import os
import re
import requests

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

app = FastAPI(title="Weather AI Backend")

# -----------------------------
# CORS
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# Request model
# -----------------------------
class UserQuery(BaseModel):
    message: str


# -----------------------------
# Detect city from user message
# -----------------------------
def extract_city(user_msg: str) -> str | None:
    text = user_msg.strip()

    # Examples:
    # weather in Delhi
    # what is the weather in Mumbai?
    # temperature of Pune
    # forecast for Kolkata
    patterns = [
        r"(?:weather|wheather|temperature|temp|forecast|rain|mausam|mosam)\s+(?:in|of|for|at)\s+(.+)",
        r"(?:what\s+is|what's)\s+(?:the\s+)?(?:weather|temperature|temp)\s+(?:in|of|for|at)\s+(.+)",
        r"(?:weather|wheather|mausam|mosam)\s+(?:of|in)\s+(.+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            city = match.group(1).strip()
            city = re.sub(r"[?.!,]+$", "", city).strip()

            # Remove common trailing words
            city = re.sub(
                r"\s+(?:right now|today|now|please|batao|btao|kaisa hai|kaise hai)$",
                "",
                city,
                flags=re.IGNORECASE,
            ).strip()

            if city:
                return city

    # Handle simple queries such as:
    # Delhi weather
    # Mumbai temperature
    match = re.search(
        r"^(.+?)\s+(?:weather|wheather|temperature|temp|forecast)$",
        text,
        re.IGNORECASE,
    )

    if match:
        city = match.group(1).strip()
        if city:
            return city

    # Handle Hinglish:
    # Delhi ka mausam
    # Mumbai ka weather
    match = re.search(
        r"^(.+?)\s+(?:ka|ki|ke)\s+(?:mausam|mosam|weather)$",
        text,
        re.IGNORECASE,
    )

    if match:
        city = match.group(1).strip()
        if city:
            return city

    return None


# -----------------------------
# Fetch REAL-TIME weather
# -----------------------------
def fetch_weather(city: str):
    if not OPENWEATHER_API_KEY:
        raise RuntimeError(
            "OPENWEATHER_API_KEY is missing in the .env file."
        )

    url = "https://api.openweathermap.org/data/2.5/weather"

    params = {
        "q": city,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
    }

    response = requests.get(
        url,
        params=params,
        timeout=10,
    )

    # OpenWeather returns useful error messages such as 401 or 404.
    try:
        data = response.json()
    except Exception:
        data = {}

    if response.status_code != 200:
        error_code = data.get("cod", response.status_code)
        error_message = data.get(
            "message",
            "Unable to get weather data."
        )

        if str(error_code) == "401":
            raise RuntimeError(
                "OpenWeather API key is invalid or not activated yet."
            )

        if str(error_code) == "404":
            raise RuntimeError(
                f"City '{city}' was not found."
            )

        raise RuntimeError(
            f"OpenWeather error {error_code}: {error_message}"
        )

    return {
        "city": data.get("name", city),
        "country": data.get("sys", {}).get("country", ""),
        "temperature": data.get("main", {}).get("temp"),
        "feels_like": data.get("main", {}).get("feels_like"),
        "humidity": data.get("main", {}).get("humidity"),
        "pressure": data.get("main", {}).get("pressure"),
        "condition": data.get("weather", [{}])[0].get(
            "description", "Unknown"
        ),
        "weather_main": data.get("weather", [{}])[0].get(
            "main", "Unknown"
        ),
        "wind_speed": data.get("wind", {}).get("speed"),
        "wind_direction": data.get("wind", {}).get("deg"),
        "visibility": data.get("visibility"),
        "clouds": data.get("clouds", {}).get("all"),
        "sunrise": data.get("sys", {}).get("sunrise"),
        "sunset": data.get("sys", {}).get("sunset"),
        "updated_at": data.get("dt"),
    }


# -----------------------------
# Create weather reply
# -----------------------------
def make_weather_reply(weather):
    city = weather["city"]
    country = weather["country"]

    location = f"{city}, {country}" if country else city

    return (
        f"🌤️ Current weather in {location}\n\n"
        f"🌡️ Temperature: {weather['temperature']}°C\n"
        f"🌡️ Feels like: {weather['feels_like']}°C\n"
        f"☁️ Condition: {weather['condition'].title()}\n"
        f"💧 Humidity: {weather['humidity']}%\n"
        f"💨 Wind speed: {weather['wind_speed']} m/s\n"
        f"🧭 Wind direction: {weather['wind_direction']}°\n"
        f"☁️ Cloud cover: {weather['clouds']}%\n"
        f"👁️ Visibility: {weather['visibility']} m\n\n"
        f"🔄 This data is fetched directly from the weather service."
    )


# -----------------------------
# Home
# -----------------------------
@app.get("/")
def home():
    return {
        "status": "success",
        "message": "Weather AI Backend is running!"
    }


# -----------------------------
# Chat endpoint
# -----------------------------
@app.post("/api/chat")
def handle_chat(payload: UserQuery):
    user_msg = payload.message.strip()

    if not user_msg:
        return {
            "status": "failed",
            "reply": "Please enter a message.",
            "weather_card": None,
        }

    city = extract_city(user_msg)

    if not city:
        return {
            "status": "success",
            "reply": (
                "Please tell me the city you want the weather for. "
                "For example: 'What is the weather in Delhi?'"
            ),
            "weather_card": None,
        }

    try:
        # IMPORTANT:
        # Weather requests DO NOT call Gemini.
        # This avoids the Gemini 429 quota error.
        weather_data = fetch_weather(city)

        return {
            "status": "success",
            "reply": make_weather_reply(weather_data),
            "weather_card": weather_data,
        }

    except Exception as e:
        print("Weather Error:", e)

        return {
            "status": "failed",
            "reply": f"❌ {str(e)}",
            "weather_card": None,
        }
