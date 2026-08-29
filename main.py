import re
import requests

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


app = FastAPI(title="Weather AI API")


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
# Request Model
# -----------------------------

class ChatRequest(BaseModel):
    message: str


# -----------------------------
# Home
# -----------------------------

@app.get("/")
def home():
    return {
        "status": "ok",
        "message": "Weather AI API is running"
    }


# -----------------------------
# Extract city from message
# -----------------------------

def extract_city(message: str):

    message = message.strip()

    patterns = [
        r"weather\s+(?:in|of|at)\s+(.+)",
        r"temperature\s+(?:in|of|at)\s+(.+)",
        r"forecast\s+(?:in|of|for)\s+(.+)",
        r"rain\s+(?:in|at)\s+(.+)",
        r"climate\s+(?:in|of)\s+(.+)",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            message,
            re.IGNORECASE
        )

        if match:

            city = match.group(1)

            # Remove question marks etc.
            city = re.sub(
                r"[?.!,]+$",
                "",
                city
            ).strip()

            return city

    return None


# -----------------------------
# Get coordinates
# -----------------------------

def get_location(city):

    url = "https://geocoding-api.open-meteo.com/v1/search"

    params = {
        "name": city,
        "count": 1,
        "language": "en",
        "format": "json"
    }

    response = requests.get(
        url,
        params=params,
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    if not data.get("results"):
        return None

    location = data["results"][0]

    return {
        "name": location.get("name"),
        "country": location.get("country"),
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
        "timezone": location.get("timezone")
    }


# -----------------------------
# Get current weather
# -----------------------------

def get_weather(latitude, longitude, timezone):

    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": latitude,
        "longitude": longitude,

        "current": (
            "temperature_2m,"
            "relative_humidity_2m,"
            "apparent_temperature,"
            "precipitation,"
            "rain,"
            "weather_code,"
            "wind_speed_10m,"
            "wind_direction_10m"
        ),

        "timezone": timezone,
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh"
    }

    response = requests.get(
        url,
        params=params,
        timeout=10
    )

    response.raise_for_status()

    return response.json()


# -----------------------------
# Weather description
# -----------------------------

def weather_description(code):

    descriptions = {

        0: "Clear sky",

        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",

        45: "Fog",
        48: "Depositing rime fog",

        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",

        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",

        71: "Slight snow",
        73: "Moderate snow",
        75: "Heavy snow",

        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",

        95: "Thunderstorm",

        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail"
    }

    return descriptions.get(
        code,
        "Unknown weather"
    )


# -----------------------------
# Chat API
# -----------------------------

@app.post("/api/chat")
def chat(request: ChatRequest):

    message = request.message.strip()

    if not message:

        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty"
        )


    # Check whether user is asking about weather

    weather_keywords = [
        "weather",
        "temperature",
        "forecast",
        "rain",
        "humidity",
        "wind",
        "climate"
    ]

    is_weather_question = any(
        keyword in message.lower()
        for keyword in weather_keywords
    )


    if not is_weather_question:

        return {
            "status": "success",
            "message": (
                "I am currently configured for "
                "real-time weather information. "
                "Please ask something like "
                "'What is the weather in Delhi?'"
            )
        }


    # Extract city

    city = extract_city(message)


    if not city:

        return {
            "status": "success",
            "message": (
                "Please tell me the city. "
                "For example: What is the weather in Delhi?"
            )
        }


    try:

        # Get coordinates

        location = get_location(city)


        if not location:

            return {
                "status": "success",
                "message": f"I couldn't find the location '{city}'."
            }


        # Get current weather

        weather = get_weather(
            location["latitude"],
            location["longitude"],
            location["timezone"]
        )


        current = weather["current"]


        temperature = current.get(
            "temperature_2m"
        )

        humidity = current.get(
            "relative_humidity_2m"
        )

        feels_like = current.get(
            "apparent_temperature"
        )

        precipitation = current.get(
            "precipitation"
        )

        rain = current.get(
            "rain"
        )

        wind = current.get(
            "wind_speed_10m"
        )

        wind_direction = current.get(
            "wind_direction_10m"
        )

        code = current.get(
            "weather_code"
        )


        description = weather_description(
            code
        )


        answer = (
            f"Current weather in "
            f"{location['name']}, "
            f"{location['country']}:\n\n"

            f"🌡️ Temperature: {temperature}°C\n"
            f"🌡️ Feels like: {feels_like}°C\n"
            f"☁️ Condition: {description}\n"
            f"💧 Humidity: {humidity}%\n"
            f"🌧️ Rain: {rain} mm\n"
            f"🌦️ Precipitation: {precipitation} mm\n"
            f"💨 Wind: {wind} km/h\n"
            f"🧭 Wind direction: {wind_direction}°\n"
            f"🕐 Updated time: {current.get('time')}"
        )


        return {

            "status": "success",

            "message": answer,

            "weather": {

                "location": location["name"],

                "country": location["country"],

                "temperature": temperature,

                "feels_like": feels_like,

                "humidity": humidity,

                "rain": rain,

                "precipitation": precipitation,

                "wind_speed": wind,

                "wind_direction": wind_direction,

                "condition": description,

                "time": current.get("time")
            }
        }


    except requests.RequestException as e:

        print("Weather API Error:", e)

        raise HTTPException(
            status_code=503,
            detail="Weather service is temporarily unavailable."
        )
