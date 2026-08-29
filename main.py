import re
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Weather AI Chatbot")

# ==============================
# CORS SETUP
# ==============================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================
# REQUEST MODEL
# ==============================
class UserQuery(BaseModel):
    message: str

# ==============================
# INTENT & LOCATION EXTRACTION
# ==============================
def detect_intent_and_location(message: str):
    msg_lower = message.strip().lower()
    
    # Weather Intent Patterns
    weather_keywords = ["weather", "wheather", "temp", "temperature", "mausam", "mosam", "rain", "forecast", "barish"]
    is_weather_query = any(keyword in msg_lower for keyword in weather_keywords)
    
    # General Chat Intents
    if any(greet in msg_lower for greet in ["hi", "hello", "hey", "hlo", "namaste", "salam"]):
        return "greeting", None
        
    if any(q in msg_lower for q in ["who are you", "kaun ho", "what can you do", "help", "kya kar sakte ho"]):
        return "identity", None

    # Extract Location for Weather
    patterns = [
        r"weather\s+(?:in|of|at)\s+(.+)",
        r"wheather\s+(?:in|of|at)\s+(.+)",
        r"temperature\s+(?:in|of|at)\s+(.+)",
        r"temp\s+(?:in|of|at)\s+(.+)",
        r"forecast\s+(?:in|of|for|at)\s+(.+)",
        r"mausam\s+(?:in|of|ka)\s+(.+)",
        r"(.+?)\s+(?:weather|wheather|temperature|temp|mausam)$",
    ]

    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            city = match.group(1).strip()
            city = re.sub(r"[?.!,]+$", "", city).strip()
            city = re.sub(r"\s+(today|now|right now|please|batao|btao)$", "", city, flags=re.IGNORECASE).strip()
            if city:
                return "weather", city

    if is_weather_query:
        # If user asks "weather" without city, default to Delhi
        return "weather", "Delhi"

    return "general_chat", None

# ==============================
# OPEN-METEO WEATHER FETCHING
# ==============================
def get_weather(city: str):
    geo_url = "https://geocoding-api.open-meteo.com/v1/search"
    geo_params = {"name": city, "count": 1, "language": "en", "format": "json"}

    geo_response = requests.get(geo_url, params=geo_params, timeout=10)
    geo_response.raise_for_status()
    geo_data = geo_response.json()

    if not geo_data.get("results"):
        return None

    location = geo_data["results"][0]
    latitude = location["latitude"]
    longitude = location["longitude"]
    location_name = location.get("name", city)
    district = location.get("admin2", "")
    state = location.get("admin1", "")
    country = location.get("country", "")
    timezone = location.get("timezone", "auto")

    weather_url = "https://api.open-meteo.com/v1/forecast"
    weather_params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": (
            "temperature_2m,relative_humidity_2m,apparent_temperature,"
            "precipitation,rain,weather_code,wind_speed_10m"
        ),
        "timezone": timezone,
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh"
    }

    weather_response = requests.get(weather_url, params=weather_params, timeout=10)
    weather_response.raise_for_status()
    current = weather_response.json()["current"]

    return {
        "city": location_name,
        "district": district,
        "state": state,
        "country": country,
        "temperature": current.get("temperature_2m"),
        "feels_like": current.get("apparent_temperature"),
        "humidity": current.get("relative_humidity_2m"),
        "precipitation": current.get("precipitation"),
        "rain": current.get("rain"),
        "weather_code": current.get("weather_code"),
        "wind_speed": current.get("wind_speed_10m"),
        "time": current.get("time")
    }

def weather_description(code: int) -> str:
    descriptions = {
        0: "Clear sky ☀️", 1: "Mainly clear 🌤️", 2: "Partly cloudy ⛅", 3: "Overcast ☁️",
        45: "Foggy 🌫️", 48: "Depositing rime fog 🌫️", 51: "Light drizzle 🌦️",
        53: "Moderate drizzle 🌦️", 55: "Dense drizzle 🌧️", 61: "Slight rain 🌧️",
        63: "Moderate rain 🌧️", 65: "Heavy rain 🌧️", 71: "Slight snow 🌨️",
        75: "Heavy snow ❄️", 80: "Rain showers 🌦️", 95: "Thunderstorm 🌩️"
    }
    return descriptions.get(code, "Clear/Partly Cloudy")

def create_weather_report(weather: dict) -> str:
    condition = weather_description(weather["weather_code"])
    location_parts = [weather["city"]]
    
    if weather["district"] and weather["district"].lower() != weather["city"].lower():
        location_parts.append(weather["district"])
    if weather["state"]:
        location_parts.append(weather["state"])
    if weather["country"]:
        location_parts.append(weather["country"])
        
    full_location = ", ".join(location_parts)

    return (
        f"🤖 **Weather Assistant Bot**\n\n"
        f"📍 **Location:** {full_location}\n"
        f"────────────────────────\n"
        f"🌡️ **Temperature:** {weather['temperature']}°C (Feels like {weather['feels_like']}°C)\n"
        f"☁️ **Condition:** {condition}\n"
        f"💧 **Humidity:** {weather['humidity']}%\n"
        f"🌧️ **Rainfall:** {weather['rain']} mm\n"
        f"💨 **Wind Speed:** {weather['wind_speed']} km/h\n"
        f"🕐 **Updated:** {weather['time'].replace('T', ' ')}"
    )

# ==============================
# ENDPOINTS
# ==============================
@app.get("/")
def home():
    return {"status": "success", "message": "Weather AI Chatbot API is online!"}

@app.post("/api/chat")
def chat(payload: UserQuery):
    user_msg = payload.message.strip()

    if not user_msg:
        return {
            "status": "failed",
            "reply": "Hey there! Please type a message or ask for a city's weather.",
            "weather_card": None
        }

    intent, location = detect_intent_and_location(user_msg)

    # Chatbot Logic Responses
    if intent == "greeting":
        return {
            "status": "success",
            "reply": "Hello! 👋 I am your Weather AI Assistant. Ask me about the weather in any city, district, or country! (e.g., 'weather in Delhi')",
            "weather_card": None
        }

    if intent == "identity":
        return {
            "status": "success",
            "reply": "I am a Real-Time Weather Chatbot! 🤖 I can provide live temperature, humidity, wind speed, and rain reports for any location worldwide.",
            "weather_card": None
        }

    if intent == "weather" or location:
        try:
            weather = get_weather(location or "Delhi")
            if weather is None:
                return {
                    "status": "success",
                    "reply": f"Sorry, I couldn't find weather details for '{location}'. Please check the city name and try again!",
                    "weather_card": None
                }
            return {
                "status": "success",
                "reply": create_weather_report(weather),
                "weather_card": weather
            }
        except Exception as err:
            return {
                "status": "failed",
                "reply": "I ran into an issue fetching the live weather right now. Please try again in a few seconds.",
                "weather_card": None,
                "error": str(err)
            }

    # Fallback response for unhandled inputs
    return {
        "status": "success",
        "reply": f"I am optimized for weather reporting! Try asking me: 'Weather in {user_msg}' or 'How is the weather in Mumbai?'",
        "weather_card": None
    }
