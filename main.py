import re
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from deep_translator import GoogleTranslator
except ImportError:
    GoogleTranslator = None

app = FastAPI(title="All-India Waterlogging & Emergency Alert Weather API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UserQuery(BaseModel):
    message: str


# --- KNOWN WATERLOGGING HOTSPOTS (Bina kisi API Key ke bilkul free check ke liye) ---
WATERLOGGING_HOTSPOTS = {
    "delhi": ["minto bridge", "ito", "pul prahladpur", "loni", "dhaula kuan", "najafgarh", "laxmi nagar", "karol bagh", "dwarka", "ashok vihar", "sangam vihar"],
    "mumbai": ["hindmata", "king circle", "kurla", "andheri subway", "dadar", "sion", "bandra", "malad subway"],
    "kolkata": ["mg road", "thanthania", "park street", "cr avenue", "behala"],
    "bangalore": ["silk board", "outer ring road", "bellandur", "tin factory"],
    "patna": ["rajendra nagar", "kankerbagh"],
    "lucknow": ["charbagh", "hazratganj"],
}

WMO = {
    0: "Clear sky ☀️", 1: "Mainly clear 🌤️", 2: "Partly cloudy ⛅", 3: "Overcast ☁️",
    45: "Foggy 🌫️", 48: "Rime fog 🌫️", 51: "Light drizzle 🌦️", 53: "Moderate drizzle 🌦️",
    55: "Dense drizzle 🌧️", 61: "Slight rain 🌧️", 63: "Moderate rain 🌧️", 65: "Heavy rain 🌧️",
    80: "Slight rain showers 🌦️", 81: "Moderate rain showers 🌧️", 82: "Violent rain showers ⛈️",
    95: "Thunderstorm ⛈️", 96: "Thunderstorm with slight hail ⛈️", 99: "Thunderstorm with heavy hail ⛈️",
}

HINGLISH_WORDS = {
    "kaisa", "kaise", "kesa", "kese", "kya", "batao", "btao", "mausam", "mosam",
    "aaj", "kal", "baarish", "barish", "garmi", "sardi", "waterlogging", "jam", "paani",
}


def norm(text: str) -> str:
    text = text.strip().lower().replace("’", "'")
    return re.sub(r"\s+", " ", text).strip(" ?!.,;:")


def detect_language(text: str) -> str:
    if re.search(r"[\u0980-\u09FF]", text):
        return "bn"
    if re.search(r"[\u0900-\u097F]", text):
        return "hi"
    words = re.findall(r"[A-Za-z]+", text.lower())
    return "hinglish" if any(w in HINGLISH_WORDS for w in words) else "en"


def extract_location(text: str) -> Optional[str]:
    raw = norm(text)
    patterns = [
        r"(?:weather|mausam|mosam|rain|baarish|barish|waterlogging|paani)\s+(?:in|of|for|at|near|ka|ki|ke|mein|me|par)\s+(.+)$",
        r"(?:what is|tell me|show me)\s+(?:the\s+)?(?:weather|forecast)\s+(?:in|of|for|at)\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw, re.I)
        if match:
            return match.group(1).strip()

    words = raw.split()
    if len(words) <= 3 and not any(w in HINGLISH_WORDS for w in words):
        return raw

    return None


def geocode(location: str) -> Optional[Dict[str, Any]]:
    url = "https://geocoding-api.open-meteo.com/v1/search"
    try:
        res = requests.get(url, params={"name": location, "count": 1, "language": "en"}, timeout=5).json()
        results = res.get("results")
        if results:
            item = results[0]
            return {
                "name": f"{item.get('name')}, {item.get('admin1', '')}, {item.get('country', '')}",
                "latitude": item["latitude"],
                "longitude": item["longitude"],
            }
    except Exception:
        pass
    return None


# --- EMERGENCY & WATERLOGGING LOGIC ---
def check_disaster_alerts(current_rain: float, current_wind: float, weather_code: int) -> List[str]:
    alerts = []
    if weather_code in [95, 96, 99]:
        alerts.append("🌩️ EMERGENCY ALERT: Aas-paas tezz bijli aur bijli ke sath toofan (Thunderstorm) ki chetavni hai!")
    if current_rain >= 30.0:
        alerts.append("🚨 EXTREME WEATHER ALERT: Bhot tezz baarish / Baadal phatne (Cloudburst) ki sthiti! Severe flooding risk!")
    elif current_rain >= 10.0:
        alerts.append("⚠️ HEAVY RAIN WARNING: Bhot tezz baarish ho rahi hai. Sadko par visibility kam hai.")
    if current_wind >= 50.0:
        alerts.append("🌪️ HIGH WIND ALERT: Tezz hawaein (>50 km/h) chal rahi hain. Pedo aur bijli ke khambho se door rahein.")
    return alerts


def check_waterlogging_risk(location_name: str, rain_mm: float) -> Dict[str, Any]:
    loc_lower = location_name.lower()
    is_hotspot = False

    for city, spots in WATERLOGGING_HOTSPOTS.items():
        if any(spot in loc_lower for spot in spots):
            is_hotspot = True
            break

    if rain_mm > 5.0 and is_hotspot:
        return {
            "level": "HIGH",
            "message": "🛑 CRITICAL WATERLOGGING RISK: Ye jagah paani bharne ke liye prone hai! Underpasses aur main roads block hone ki poori sambhavna hai.",
        }
    elif rain_mm > 12.0:
        return {
            "level": "MODERATE",
            "message": "⚠️ MODERATE WATERLOGGING RISK: Zyada baarish ki wajah se neeche wale raasto par paani jama ho sakta hai. Dhyan se drive karein.",
        }
    elif rain_mm > 0.5:
        return {
            "level": "LOW",
            "message": "ℹ️ LOW RISK: Halke paani ka jamav ho sakta hai, traffic thoda slow ho sakta hai.",
        }
    else:
        return {"level": "NONE", "message": "✅ NO WATERLOGGING: Sadke saaf hain aur paani bharne ka koi chance nahi hai."}


# --- API ENDPOINTS ---
@app.get("/")
def home() -> Dict[str, str]:
    return {"status": "online", "message": "Weather & Waterlogging Alert API Ready"}


@app.post("/api/chat")
async def chat(payload: UserQuery) -> Dict[str, Any]:
    message = payload.message.strip()
    language = detect_language(message)
    location_query = extract_location(message)

    if not location_query:
        return {
            "status": "need_location",
            "reply": "Aap kis city ya jagah ka mausam aur waterlogging status janna chahte hain? Kripya location ka naam batayein.",
        }

    geo = geocode(location_query)
    if not geo:
        return {"status": "failed", "reply": f"Maaf kijiye, mujhe '{location_query}' ki location nahi mili."}

    # Free Open-Meteo Live API Call
    url = f"https://api.open-meteo.com/v1/forecast?latitude={geo['latitude']}&longitude={geo['longitude']}&current=temperature_2m,relative_humidity_2m,rain,weather_code,wind_speed_10m&timezone=auto"
    try:
        w_data = requests.get(url, timeout=5).json().get("current", {})
    except Exception:
        return {"status": "failed", "reply": "Weather data fetch karne mein dikkat aayi."}

    current_rain = w_data.get("rain", 0.0) or 0.0
    current_wind = w_data.get("wind_speed_10m", 0.0) or 0.0
    weather_code = w_data.get("weather_code", 0)

    # Process Alerts and Waterlogging
    disaster_alerts = check_disaster_alerts(current_rain, current_wind, weather_code)
    waterlogging_info = check_waterlogging_risk(geo["name"], current_rain)

    # Build Text Reply
    report_lines = [
        f"📍 Location: {geo['name']}",
        f"🌤️ Condition: {WMO.get(weather_code, 'Clear')}",
        f"🌡️ Temperature: {w_data.get('temperature_2m')}°C",
        f"🌧️ Current Rain: {current_rain} mm",
        "",
        "🌊 WATERLOGGING REPORT:",
        f"• Status: {waterlogging_info['message']}",
    ]

    if disaster_alerts:
        report_lines.append("\n🚨 EMERGENCY ALERTS:")
        for alert in disaster_alerts:
            report_lines.append(f"• {alert}")

    return {
        "status": "success",
        "reply": "\n".join(report_lines),
        "data": {
            "weather": w_data,
            "alerts": disaster_alerts,
            "waterlogging": waterlogging_info,
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
