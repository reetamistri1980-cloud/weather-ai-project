import os
import re
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai

app = FastAPI(title="Smart Gemini Weather Chatbot")

# CORS SETUP
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class UserQuery(BaseModel):
    message: str

# Gemini Client Setup
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# State/Region Capital Mapper
STATE_CAPITAL_MAP = {
    "west bengal": "Kolkata",
    "bengal": "Kolkata",
    "maharashtra": "Mumbai",
    "tamil nadu": "Chennai",
    "karnataka": "Bengaluru",
    "uttar pradesh": "Lucknow",
    "gujarat": "Gandhinagar",
    "rajasthan": "Jaipur",
    "punjab": "Chandigarh",
    "bihar": "Patna"
}

def extract_city(message: str):
    msg_lower = message.strip().lower()
    
    # State check
    for state_key, capital in STATE_CAPITAL_MAP.items():
        if state_key in msg_lower:
            return capital

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
                return STATE_CAPITAL_MAP.get(city.lower(), city)

    weather_keywords = ["weather", "wheather", "temp", "temperature", "mausam", "mosam", "rain", "forecast"]
    if any(k in msg_lower for k in weather_keywords):
        return "Delhi"

    return None

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
        45: "Foggy 🌫️", 51: "Light drizzle 🌦️", 61: "Slight rain 🌧️", 80: "Rain showers 🌦️", 95: "Thunderstorm 🌩️"
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
        f"🤖 **Weather Report**\n\n"
        f"📍 **Location:** {full_location}\n"
        f"────────────────────────\n"
        f"🌡️ **Temperature:** {weather['temperature']}°C (Feels like {weather['feels_like']}°C)\n"
        f"☁️ **Condition:** {condition}\n"
        f"💧 **Humidity:** {weather['humidity']}%\n"
        f"🌧️ **Rainfall:** {weather['rain']} mm\n"
        f"💨 **Wind Speed:** {weather['wind_speed']} km/h\n"
        f"🕐 **Updated:** {weather['time'].replace('T', ' ')}"
    )

def ask_gemini(prompt: str) -> str:
    if not client:
        return f"I can help with general queries! Regarding '{prompt}': Please configure GEMINI_API_KEY in server environment for full AI functionality."
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text
    except Exception as err:
        return f"Hello! I am your AI assistant. I couldn't process that specific query right now, but feel free to ask me weather updates or general questions!"

@app.get("/")
def home():
    return {"status": "success", "message": "Smart Gemini Weather Chatbot API is running!"}

@app.post("/api/chat")
def chat(payload: UserQuery):
    user_msg = payload.message.strip()

    if not user_msg:
        return {"status": "failed", "reply": "Please enter a message.", "weather_card": None}

    # Check if user is asking for Weather
    city = extract_city(user_msg)

    if city:
        try:
            weather = get_weather(city)
            if weather:
                return {"status": "success", "reply": create_weather_report(weather), "weather_card": weather}
        except Exception:
            pass

    # If not weather query, route to Gemini AI
    ai_reply = ask_gemini(user_msg)
    return {"status": "success", "reply": ai_reply, "weather_card": None}
