import re
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from deep_translator import GoogleTranslator, single_detection

app = FastAPI(title="All-India Multi-Lingual Weather AI Chatbot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class UserQuery(BaseModel):
    message: str

LANDMARK_COORDS = {
    "connaught place": {"name": "Connaught Place, New Delhi, Delhi, India", "lat": 28.6315, "lon": 77.2167},
    "cp": {"name": "Connaught Place, New Delhi, Delhi, India", "lat": 28.6315, "lon": 77.2167},
    "chandni chowk": {"name": "Chandni Chowk, Central Delhi, Delhi, India", "lat": 28.6506, "lon": 77.2303},
    "rohini": {"name": "Rohini, North West Delhi, Delhi, India", "lat": 28.7041, "lon": 77.1025},
    "dwarka": {"name": "Dwarka, South West Delhi, Delhi, India", "lat": 28.5921, "lon": 77.0460},
}

WMO_CODES_EN = {
    0: "Clear sky ☀️", 1: "Mainly clear 🌤️", 2: "Partly cloudy ⛅", 3: "Overcast ☁️",
    45: "Foggy 🌫️", 48: "Depositing rime fog 🌫️", 51: "Light drizzle 🌦️", 53: "Moderate drizzle 🌧️",
    55: "Dense drizzle 🌧️", 61: "Slight rain 🌧️", 63: "Moderate rain 🌧️", 65: "Heavy rain 🌧️⚡",
    80: "Slight rain showers 🌦️", 81: "Moderate rain showers 🌧️", 82: "Violent rain showers ⛈️",
    95: "Thunderstorm 🌩️", 96: "Thunderstorm with slight hail ⛈️", 99: "Thunderstorm with heavy hail ⛈️🚨"
}

def detect_user_language(text: str) -> str:
    # 1. Hinglish Detection Check
    hinglish_keywords = [
        "kaisa", "kaisey", "kya", "batayo", "batao", "bata", "mausam", "kheti", "aaj", "kal",
        "kab", "baarish", "garmi", "sardi", "fasal", "mitti", "kaisa h", "kaisa hai", "kaisa rahega"
    ]
    words = text.lower().split()
    if any(word in hinglish_keywords for word in words):
        return "hinglish"

    # 2. Bengali Script Check
    if re.search(r'[\u0980-\u09FF]', text):
        return "bn"

    # 3. Hindi / Devanagari Script Check
    if re.search(r'[\u0900-\u097F]', text):
        return "hi"

    # 4. Automatic Detection for other languages
    try:
        lang = single_detection(text, api_key=None)
        return lang if lang else "en"
    except Exception:
        return "en"

def extract_location(text: str) -> str:
    msg = text.strip()
    msg_lower = msg.lower()

    # 1. Direct Landmark Check
    for landmark in LANDMARK_COORDS:
        if re.search(r'\b' + re.escape(landmark) + r'\b', msg_lower):
            return landmark

    # 2. Native script city dictionary (Hindi, Bengali, Marathi, etc.)
    script_city_map = {
        "দিল্লি": "Delhi", "দিল্লির": "Delhi", "কলকাতা": "Kolkata", "মুম্বাই": "Mumbai",
        "दिल्ली": "Delhi", "मुंबई": "Mumbai", "कोलकाता": "Kolkata", "पटना": "Patna"
    }
    for key, city in script_city_map.items():
        if key in msg:
            return city

    # 3. Regex Match for location extraction
    match = re.search(r"(?:weather|wheather|wether|temp|mausam|farming|fasal|detail|details|forecast|alert|alerts|climate|আবহাওয়া|আবহাওয়ার|বৃষ্টি|হাওয়া|हवामान|मौसम)\s+(?:in|of|at|near|for|এর|তে|का|की|के)?\s+(.+)", msg_lower, re.IGNORECASE)
    
    if match:
        loc = match.group(1).strip()
    else:
        loc = msg_lower

    loc = re.sub(r"\b(is|there|any|weather|wheather|wether|temp|mausam|farming|fasal|detail|details|info|show|give|me|forecast|alert|alerts|climate|today|tomorrow|now|right now|please|tell me|pls|আজ|আজকে|এখন|হওয়া|मौसम|हवामान|কেমন|কেমন?|kaisa|hai|kya|batao|batayo)\b", "", loc, flags=re.IGNORECASE).strip()
    loc = re.sub(r"[?.!,]+$", "", loc).strip()
    loc = re.sub(r"^[?.!,]+", "", loc).strip()

    return loc if loc else "Delhi"

def get_location_coordinates(location_name: str):
    loc_lower = location_name.lower().strip()
    
    if loc_lower in LANDMARK_COORDS:
        return LANDMARK_COORDS[loc_lower]

    geo_url = "https://geocoding-api.open-meteo.com/v1/search"
    geo_params = {"name": location_name, "count": 1, "language": "en", "format": "json"}

    try:
        res = requests.get(geo_url, params=geo_params, timeout=8).json()
        if res.get("results"):
            loc = res["results"][0]
            name = loc.get("name", "")
            district = loc.get("admin2", "")
            state = loc.get("admin1", "")
            country = loc.get("country", "")

            parts = [p for p in [name, district, state, country] if p]
            unique_parts = []
            for item in parts:
                if item not in unique_parts:
                    unique_parts.append(item)
            
            return {
                "name": ", ".join(unique_parts),
                "lat": loc["latitude"],
                "lon": loc["longitude"]
            }
    except Exception:
        pass

    return None

def fetch_weather_and_soil_data(lat: float, lon: float):
    main_url = "https://api.open-meteo.com/v1/forecast"
    main_params = {
        "latitude": lat,
        "longitude": lon,
        "current_weather": "true",
        "hourly": "temperature_2m,precipitation,weathercode,relative_humidity_2m,apparent_temperature,surface_pressure,uv_index",
        "daily": "weathercode,temperature_2m_max,temperature_2m_min",
        "timezone": "auto"
    }
    
    agri_params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "soil_temperature_0_to_10cm,soil_moisture_0_to_1cm",
        "timezone": "auto"
    }

    try:
        main_res = requests.get(main_url, params=main_params, timeout=10).json()
        agri_res = requests.get(main_url, params=agri_params, timeout=10).json()
        
        curr = main_res.get("current_weather", {})
        main_hourly = main_res.get("hourly", {})
        agri_hourly = agri_res.get("hourly", {})
        daily = main_res.get("daily", {})

        return {
            "temp": curr.get("temperature"),
            "feels_like": main_hourly.get("apparent_temperature", [None])[0],
            "humidity": main_hourly.get("relative_humidity_2m", [None])[0],
            "rain": main_hourly.get("precipitation", [None])[0] or 0.0,
            "wind": curr.get("windspeed"),
            "pressure": main_hourly.get("surface_pressure", [None])[0],
            "uv": main_hourly.get("uv_index", [None])[0],
            "code": curr.get("weathercode", 0),
            "soil_temp": agri_hourly.get("soil_temperature_0_to_10cm", [None])[0],
            "soil_moisture": agri_hourly.get("soil_moisture_0_to_1cm", [None])[0],
            "daily": daily
        }
    except Exception:
        return None

def generate_report(loc_name: str, data: dict, lang_code: str) -> str:
    temp = data["temp"]
    w_code = data["code"]
    daily = data.get("daily", {})
    condition_desc = WMO_CODES_EN.get(w_code, "Clear sky ☀️")

    # 1. HINGLISH RESPONSE (Roman Hindi)
    if lang_code == "hinglish":
        forecast_hng = ""
        if daily and "time" in daily:
            dates = daily.get("time", [])[:7]
            max_t = daily.get("temperature_2m_max", [])[:7]
            min_t = daily.get("temperature_2m_min", [])[:7]
            codes = daily.get("weathercode", [])[:7]
            for i in range(len(dates)):
                c = WMO_CODES_EN.get(codes[i], "Normal")
                forecast_hng += f"📅 **{dates[i]}:** Max {max_t[i]}°C | Min {min_t[i]}°C ({c})\n"

        return (
            f"📍 **Jagah (Location):** {loc_name}\n"
            f"🌤️ **Mausam Ka Haal:** {condition_desc}\n"
            f"────────────────────────\n"
            f"🌡️ **Taapman (Temperature):** {temp}°C (Mehsus ho raha hai: {data['feels_like']}°C)\n"
            f"💧 **Hawa Me Nami (Humidity):** {data['humidity']}%\n"
            f"🌧️ **Baarish (Rainfall):** {data['rain']} mm\n"
            f"💨 **Hawa Ki Raftar (Wind Speed):** {data['wind']} km/h\n"
            f"☀️ **UV Index:** {data['uv']} | ⏲️ **Pressure:** {data['pressure']} hPa\n"
            f"────────────────────────\n"
            f"🧪 **Kheti Aur Mitti Ki Jaankari:**\n"
            f"🌱 **Mitti Ka Taapman (0-10cm):** {data['soil_temp']}°C\n"
            f"💦 **Mitti Ki Nami (0-1cm):** {data['soil_moisture']} m³/m³\n"
            f"────────────────────────\n"
            f"🔮 **AAGLE 7 DINO KA FORECAST:**\n"
            f"{forecast_hng}"
        )

    # Base English Template for All Other Languages
    forecast_en = ""
    if daily and "time" in daily:
        dates = daily.get("time", [])[:7]
        max_t = daily.get("temperature_2m_max", [])[:7]
        min_t = daily.get("temperature_2m_min", [])[:7]
        codes = daily.get("weathercode", [])[:7]
        for i in range(len(dates)):
            c = WMO_CODES_EN.get(codes[i], "Normal")
            forecast_en += f"📅 **{dates[i]}:** Max {max_t[i]}°C | Min {min_t[i]}°C ({c})\n"

    english_report = (
        f"📍 **Location:** {loc_name}\n"
        f"🌤️ **Condition:** {condition_desc}\n"
        f"────────────────────────\n"
        f"🌡️ **Temperature:** {temp}°C (Feels like {data['feels_like']}°C)\n"
        f"💧 **Humidity:** {data['humidity']}%\n"
        f"🌧️ **Rainfall:** {data['rain']} mm\n"
        f"💨 **Wind Speed:** {data['wind']} km/h\n"
        f"☀️ **UV Index:** {data['uv']} | ⏲️ **Pressure:** {data['pressure']} hPa\n"
        f"────────────────────────\n"
        f"🧪 **Agricultural & Soil Details:**\n"
        f"🌱 **Soil Temperature (0-10cm):** {data['soil_temp']}°C\n"
        f"💦 **Soil Moisture (0-1cm):** {data['soil_moisture']} m³/m³\n"
        f"────────────────────────\n"
        f"🔮 **7-DAY WEATHER FORECAST:**\n"
        f"{forecast_en}"
    )

    if lang_code == "en":
        return english_report

    # Universal Language Translator (Bengali, Hindi, Marathi, Tamil, Telugu, etc.)
    try:
        translated_report = GoogleTranslator(source='en', target=lang_code).translate(english_report)
        return translated_report
    except Exception:
        return english_report

@app.get("/")
def home():
    return {"status": "online", "message": "All-India Multi-Lingual Weather API Ready"}

@app.post("/api/chat")
def chat(payload: UserQuery):
    msg = payload.message.strip()
    if not msg:
        return {"status": "failed", "reply": "Please send a message."}

    user_lang = detect_user_language(msg)
    target_loc = extract_location(msg)
    coords = get_location_coordinates(target_loc)

    if not coords:
        return {"status": "failed", "reply": f"Could not find coordinates for '{target_loc}'."}

    weather_data = fetch_weather_and_soil_data(coords["lat"], coords["lon"])
    
    if not weather_data:
        return {"status": "failed", "reply": "Could not fetch weather data from API."}

    report = generate_report(coords["name"], weather_data, user_lang)

    return {
        "status": "success",
        "reply": report,
        "data": weather_data
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
