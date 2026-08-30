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
    # 1. Bengali Script Detection
    if re.search(r'[\u0980-\u09FF]', text):
        return "bn"

    # 2. Devanagari Script (Hindi / Marathi) Detection
    if re.search(r'[\u0900-\u097F]', text):
        try:
            detected = single_detection(text, api_key=None)
            return detected if detected in ["hi", "mr"] else "hi"
        except Exception:
            return "hi"

    # 3. Hinglish (Roman Script Hindi) Check
    hinglish_words = ["kaisa", "kaisey", "hai", "kya", "batayo", "batao", "aaj", "kal", "kaise", "bata", "mausam"]
    if any(w in text.lower().split() for w in hinglish_words):
        return "hinglish"

    # 4. Dynamic Detection for all other global languages (Marathi in Latin script, Gujarati, Tamil, etc.)
    try:
        lang = single_detection(text, api_key=None)
        return lang if lang else "en"
    except Exception:
        return "en"

def extract_location(text: str) -> str:
    msg = text.strip().lower()

    for landmark in LANDMARK_COORDS:
        if re.search(r'\b' + re.escape(landmark) + r'\b', msg):
            return landmark

    match = re.search(r"(?:weather|wheather|wether|temp|mausam|farming|fasal|detail|details|forecast|alert|alerts|climate|আবহাওয়া|আবহাওয়ার|বৃষ্টি|হালকা|হাওয়া|हवामान|मौसम)\s+(?:in|of|at|near|for|এর|তে|का|की|के)?\s+(.+)", msg, re.IGNORECASE)
    
    if match:
        loc = match.group(1).strip()
    else:
        try:
            translated_text = GoogleTranslator(source='auto', target='en').translate(msg)
            match_trans = re.search(r"(?:weather|temperature|climate|forecast|alert|alerts|farming)\s+(?:in|of|at|near|for)?\s+(.+)", translated_text, re.IGNORECASE)
            loc = match_trans.group(1).strip() if match_trans else translated_text
        except Exception:
            loc = msg

    loc = re.sub(r"\b(is|there|any|weather|wheather|wether|temp|mausam|farming|fasal|detail|details|info|show|give|me|forecast|alert|alerts|climate|today|tomorrow|now|right now|please|tell me|pls|আজ|আজকে|এখন|হওয়া|मौसम|हवामान)\b", "", loc, flags=re.IGNORECASE).strip()
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
            
            display_name = ", ".join(unique_parts)

            return {
                "name": display_name,
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

        temp = curr.get("temperature")
        wind = curr.get("windspeed")
        code = curr.get("weathercode", 0)

        humidity = main_hourly.get("relative_humidity_2m", [None])[0]
        feels_like = main_hourly.get("apparent_temperature", [None])[0]
        rain = main_hourly.get("precipitation", [None])[0]
        pressure = main_hourly.get("surface_pressure", [None])[0]
        uv = main_hourly.get("uv_index", [None])[0]

        soil_temp = agri_hourly.get("soil_temperature_0_to_10cm", [None])[0]
        soil_moisture = agri_hourly.get("soil_moisture_0_to_1cm", [None])[0]

        hourly_data = {
            "time": main_hourly.get("time", [])[:24],
            "temperature_2m": main_hourly.get("temperature_2m", [])[:24],
            "precipitation": main_hourly.get("precipitation", [])[:24],
            "weathercode": main_hourly.get("weathercode", [])[:24]
        }

        return {
            "temp": temp,
            "feels_like": feels_like if feels_like is not None else temp,
            "humidity": humidity,
            "rain": rain if rain is not None else 0.0,
            "wind": wind,
            "pressure": pressure,
            "uv": uv,
            "code": code,
            "soil_temp": soil_temp,
            "soil_moisture": soil_moisture,
            "daily": daily,
            "hourly": hourly_data
        }
    except Exception:
        return None

def generate_report(loc_name: str, data: dict, lang_code: str) -> str:
    humidity = data["humidity"] if data["humidity"] is not None else 0
    moisture = data["soil_moisture"] if data["soil_moisture"] is not None else 0
    wind = data["wind"] if data["wind"] is not None else 0
    rain = data["rain"] if data["rain"] is not None else 0
    temp = data["temp"]
    w_code = data["code"]

    alerts = []
    if wind > 40:
        alerts.append("⚠️ **WIND ALERT:** High wind speeds detected!")
    if rain > 15 or w_code in [65, 82, 95, 96, 99]:
        alerts.append("🚨 **HEAVY RAIN / THUNDERSTORM ALERT:** Risk of waterlogging.")
    if temp is not None:
        if temp > 40:
            alerts.append("🔥 **HEATWAVE ALERT:** Extreme high temperature.")
        elif temp < 5:
            alerts.append("❄️ **COLD WAVE ALERT:** Low temperature alert.")
    
    alert_text = "\n".join(alerts) if alerts else "✅ **Weather Alert:** No severe weather warnings active."

    if humidity > 60 and moisture > 0.2:
        farming_advice = "🌱 **Farming Suggestion:** Optimal soil moisture & humidity for sowing and irrigation!"
    elif humidity < 35:
        farming_advice = "🌾 **Farming Suggestion:** Air is dry. Field irrigation (paani dena) is recommended."
    else:
        farming_advice = "🚜 **Farming Suggestion:** Conditions are moderate for standard agricultural activities."

    daily = data.get("daily", {})
    forecast_text = ""
    if daily and "time" in daily:
        dates = daily.get("time", [])[:7]
        max_temps = daily.get("temperature_2m_max", [])[:7]
        min_temps = daily.get("temperature_2m_min", [])[:7]
        codes = daily.get("weathercode", [])[:7]

        for i in range(len(dates)):
            cond = WMO_CODES_EN.get(codes[i], "Normal")
            forecast_text += f"📅 **{dates[i]}:** Max {max_temps[i]}°C | Min {min_temps[i]}°C ({cond})\n"

    condition_desc = WMO_CODES_EN.get(w_code, "Clear sky ☀️")
    temp_str = f"{temp}°C" if temp is not None else "N/A"
    feels_str = f"{data['feels_like']}°C" if data['feels_like'] is not None else "N/A"

    # Hinglish Specific Report
    if lang_code == "hinglish":
        hinglish_report = (
            f"📍 **Location:** {loc_name}\n"
            f"🌤️ **Mausam Ka Haal:** {condition_desc}\n"
            f"────────────────────────\n"
            f"🌡️ **Taapman (Temperature):** {temp_str} (Aisa mehsus ho raha hai {feels_str})\n"
            f"💧 **Hawa Me Nami (Humidity):** {data['humidity']}%\n"
            f"🌧️ **Baarish (Rainfall):** {data['rain']} mm\n"
            f"💨 **Hawa Ki Raftar (Wind Speed):** {data['wind']} km/h\n"
            f"☀️ **UV Index:** {data['uv']} | ⏲️ **Pressure:** {data['pressure']} hPa\n"
            f"────────────────────────\n"
            f"🔔 **MAUSAM KI CHEETAVNI (ALERTS):**\n"
            f"{alert_text}\n"
            f"────────────────────────\n"
            f"🧪 **Kheti Aur Fasal Ka Detail:**\n"
            f"🌱 **Mitti Ka Taapman (0-10cm):** {data['soil_temp']}°C\n"
            f"💦 **Mitti Ki Nami (0-1cm):** {data['soil_moisture']} m³/m³\n"
            f"{farming_advice}\n"
            f"────────────────────────\n"
            f"🔮 **AAGLE 7 DINO KA FORECAST:**\n"
            f"{forecast_text}"
        )
        return hinglish_report

    english_report = (
        f"📍 **Location:** {loc_name}\n"
        f"🌤️ **Condition:** {condition_desc}\n"
        f"────────────────────────\n"
        f"🌡️ **Temperature:** {temp_str} (Feels like {feels_str})\n"
        f"💧 **Air Humidity:** {data['humidity']}%\n"
        f"🌧️ **Rainfall:** {data['rain']} mm\n"
        f"💨 **Wind Speed:** {data['wind']} km/h\n"
        f"☀️ **UV Index:** {data['uv']} | ⏲️ **Pressure:** {data['pressure']} hPa\n"
        f"────────────────────────\n"
        f"🔔 **WEATHER ALERTS & WARNINGS:**\n"
        f"{alert_text}\n"
        f"────────────────────────\n"
        f"🧪 **Agricultural & Climate Details:**\n"
        f"🌱 **Soil Temp (0-10cm):** {data['soil_temp']}°C\n"
        f"💦 **Soil Moisture (0-1cm):** {data['soil_moisture']} m³/m³\n"
        f"{farming_advice}\n"
        f"────────────────────────\n"
        f"🔮 **7-DAY WEATHER FORECAST:**\n"
        f"{forecast_text}"
    )

    if lang_code == "en":
        return english_report

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

# Python Code Internal Auto-Reload Settings Added
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
