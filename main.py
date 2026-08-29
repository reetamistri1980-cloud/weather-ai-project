import re
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Smart AI Weather & General Chatbot")

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

class UserQuery(BaseModel):
    message: str

# ==============================
# WIKIPEDIA / GENERAL KNOWLEDGE FETCH
# ==============================
def get_general_knowledge(query: str):
    try:
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{query.strip().replace(' ', '_')}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if "extract" in data and data["extract"]:
                return data["extract"]
    except Exception:
        pass
    return None

# ==============================
# INTENT & LOCATION DETECTOR
# ==============================
def detect_intent(message: str):
    msg_lower = message.strip().lower()
    
    # Greetings
    if any(greet in msg_lower for greet in ["hi", "hello", "hey", "hlo", "namaste"]):
        return "greeting", None
        
    # Identity
    if any(q in msg_lower for q in ["who are you", "kaun ho", "what can you do", "help"]):
        return "identity", None

    # Weather Keywords Check
    weather_keywords = ["weather", "wheather", "temp", "temperature", "mausam", "mosam", "rain", "forecast", "barish", "humidity", "wind"]
    is_weather_query = any(k in msg_lower for k in weather_keywords)

    # Extract Location Regex
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
        return "weather", "Delhi"

    # General Knowledge Query (e.g., Photosynthesis)
    clean_query = re.sub(r"^(what is|what are|tell me about|explain|define)\s+", "", msg_lower, flags=re.IGNORECASE)
    clean_query = re.sub(r"[?.!,]+$", "", clean_query).strip()
    
    return "gk", clean_query

# ==============================
# ACCURATE WEATHER FETCH
# ==============================
def get_weather(city: str):
    geo_url = "https://geocoding-api.open-meteo.com/v1/search"
    geo_params = {"name": city, "count": 5, "language": "en", "format": "json"}

    geo_response = requests.get(geo_url, params=geo_params, timeout=10)
    geo_response.raise_for_status()
    geo_data = geo_response.json()

    if not geo_data.get("results"):
        return None

    results = geo_data["results"]
    location = results[0]

    # Specific fix for "Bengal" or Indian regions preference
    for res in results:
        if "bengal" in city.lower() and res.get("country_code") == "IN":
            location = res
            break

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
        80: "Rain showers 🌦️", 95: "Thunderstorm 🌩️"
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
        f"🤖 **Weather Assistant**\n\n"
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
# CHAT ENDPOINT
# ==============================
@app.get("/")
def home():
    return {"status": "success", "message": "Smart AI Chatbot API is running!"}

@app.post("/api/chat")
def chat(payload: UserQuery):
    user_msg = payload.message.strip()

    if not user_msg:
        return {"status": "failed", "reply": "Please enter a message.", "weather_card": None}

    intent, data = detect_intent(user_msg)

    if intent == "greeting":
        return {
            "status": "success",
            "reply": "Hello! 👋 I am your Smart AI Assistant. Ask me about weather in any location or general science/knowledge questions!",
            "weather_card": None
        }

    if intent == "identity":
        return {
            "status": "success",
            "reply": "I am an AI Chatbot! 🤖 I provide live weather reports and answer general questions.",
            "weather_card": None
        }

    if intent == "weather":
        try:
            weather = get_weather(data)
            if weather is None:
                return {"status": "success", "reply": f"Could not find weather for '{data}'.", "weather_card": None}
            return {"status": "success", "reply": create_weather_report(weather), "weather_card": weather}
        except Exception as err:
            return {"status": "failed", "reply": "Unable to fetch live weather.", "weather_card": None, "error": str(err)}

    if intent == "gk":
        answer = get_general_knowledge(data)
        if answer:
            return {"status": "success", "reply": f"🤖 **Answer:**\n\n{answer}", "weather_card": None}

    return {
        "status": "success",
        "reply": f"I couldn't find an exact answer for '{user_msg}'. Try asking 'weather in West Bengal' or 'what is photosynthesis'.",
        "weather_card": None
    }
