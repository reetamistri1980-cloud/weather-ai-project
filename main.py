import re
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ==========================================
# 🔑 APNI WEATHERAPI.COM KI KEY YAHAN DALEIN
# ==========================================
WEATHER_API_KEY = "YOUR_WEATHER_API_KEY_HERE"

app = FastAPI(title="Accurate Weather & Waterlogging API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UserQuery(BaseModel):
    message: str


# Waterlogging hotspot areas in major Indian cities
WATERLOGGING_HOTSPOTS = {
    "delhi": [
        "minto bridge", "ito", "pul prahladpur", "loni", "dhaula kuan",
        "najafgarh", "laxmi nagar", "karol bagh", "dwarka", "ashok vihar",
        "sangam vihar", "connaught place", "cp", "rohini", "chandni chowk"
    ],
    "mumbai": [
        "hindmata", "king circle", "kurla", "andheri subway", "dadar",
        "sion", "bandra", "malad subway"
    ],
    "kolkata": ["mg road", "thanthania", "park street", "cr avenue", "behala"],
    "bangalore": ["silk board", "outer ring road", "bellandur", "tin factory"],
    "patna": ["rajendra nagar", "kankerbagh"],
    "lucknow": ["charbagh", "hazratganj"],
}

INDIA_ALIASES = {
    "up": "Uttar Pradesh, India", "uttar pradesh": "Uttar Pradesh, India",
    "mp": "Madhya Pradesh, India", "madhya pradesh": "Madhya Pradesh, India",
    "rj": "Rajasthan, India", "rajasthan": "Rajasthan, India",
    "br": "Bihar, India", "bihar": "Bihar, India",
    "mh": "Maharashtra, India", "maharashtra": "Maharashtra, India",
    "delhi": "Delhi, India", "new delhi": "New Delhi, India",
    "mumbai": "Mumbai, India", "kolkata": "Kolkata, India",
    "lucknow": "Lucknow, India", "patna": "Patna, India",
    "jaipur": "Jaipur, India", "bengaluru": "Bengaluru, India",
    "bangalore": "Bengaluru, India", "chennai": "Chennai, India",
}

LANDMARKS = {
    "connaught place": "Connaught Place, New Delhi, Delhi, India",
    "cp": "Connaught Place, New Delhi, Delhi, India",
    "minto bridge": "Minto Bridge, New Delhi, Delhi, India",
    "chandni chowk": "Chandni Chowk, Delhi, India",
    "rohini": "Rohini, Delhi, India",
    "dwarka": "Dwarka, Delhi, India",
}

HINGLISH_WORDS = {
    "kaisa", "kaise", "kesa", "kese", "kya", "batao", "btao", "mausam", "mosam",
    "aaj", "kal", "baarish", "barish", "garmi", "sardi", "fasal", "kheti", "mitti",
    "nami", "taapman", "hawa", "rahega", "rahegi", "hai", "hain", "mein", "me", "ka",
    "ki", "ke", "kab", "kitna", "kitni", "dikhao", "chahiye", "chhatri", "umbrella",
    "kapde", "waterlogging", "paani", "pani", "jam", "block", "water", "jal", "jamav"
}


def norm(text: str) -> str:
    text = text.strip().lower().replace("’", "'")
    return re.sub(r"\s+", " ", text).strip(" ?!.,;:")


def is_waterlogging_query(text: str) -> bool:
    raw = norm(text)
    keywords = ["waterlogging", "paani", "pani", "water", "jam", "block", "waterlog", "jal jamav"]
    return any(kw in raw for kw in keywords)


def extract_location(text: str) -> Optional[str]:
    raw = norm(text)

    # 1. Check Landmark or Hotspot
    for key, val in LANDMARKS.items():
        if key in raw:
            return val

    # 2. Check State / Major City Alias
    for key, val in INDIA_ALIASES.items():
        if re.search(rf"\b{re.escape(key)}\b", raw, re.I):
            return val

    # 3. Regex Patterns for city names in sentence
    patterns = [
        r"(?:weather|mausam|mosam|rain|baarish|barish|waterlogging|paani|pani)\s+(?:in|of|for|at|near|ka|ki|ke|mein|me|par)\s+(.+)$",
        r"(?:what is|tell me|show me)\s+(?:the\s+)?(?:weather|forecast)\s+(?:in|of|for|at)\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw, re.I)
        if match:
            cand = match.group(1).strip()
            cand = re.sub(r"\s+(today|aaj|now|batao|btao)$", "", cand, flags=re.I)
            if cand:
                return cand

    # 4. Filter stop words
    words = [w for w in raw.split() if w not in HINGLISH_WORDS]
    if words:
        return " ".join(words)

    return None


def check_waterlogging_risk(location_name: str, rain_mm: float) -> str:
    loc_lower = location_name.lower()
    is_hotspot = False

    for city, spots in WATERLOGGING_HOTSPOTS.items():
        if any(spot in loc_lower for spot in spots):
            is_hotspot = True
            break

    if rain_mm > 5.0 and is_hotspot:
        return "🛑 CRITICAL WATERLOGGING RISK: Ye area paani bharne (waterlogging) ke liye prone hai! Underpass aur roads block hone ki sambhavna hai."
    elif rain_mm > 12.0:
        return "⚠️ MODERATE WATERLOGGING RISK: Tezz baarish ki wajah se neeche wale raasto par paani jama ho sakta hai."
    elif rain_mm > 0.5:
        return "ℹ️ LOW RISK: Halke paani ka jamav ho sakta hai, traffic thoda slow reh sakta hai."
    else:
        return "✅ NO WATERLOGGING: Sadke saaf hain aur aaj paani bharne ka koi risk nahi hai."


def fetch_weather_data(location_query: str) -> Optional[Dict[str, Any]]:
    """WeatherAPI.com se accurate data fetch karta hai"""
    url = f"http://api.weatherapi.com/v1/forecast.json"
    params = {
        "key": WEATHER_API_KEY,
        "q": location_query,
        "days": 7,
        "aqi": "no",
        "alerts": "yes"
    }
    try:
        res = requests.get(url, params=params, timeout=8)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None


def make_full_weather_report(data: Dict[str, Any]) -> str:
    loc = data["location"]["name"] + ", " + data["location"]["region"] + ", " + data["location"]["country"]
    curr = data["current"]
    forecast_days = data["forecast"]["forecastday"]

    condition = curr["condition"]["text"]
    temp = curr["temp_c"]
    feels_like = curr["feelslike_c"]
    humidity = curr["humidity"]
    rain_mm = curr["precip_mm"]
    wind_kmh = curr["wind_kph"]

    today_hourly = forecast_days[0]["hour"]
    precip_prob = max([h["chance_of_rain"] for h in today_hourly[:12]], default=0)

    needs_umbrella = rain_mm > 0.1 or precip_prob >= 30
    umbrella_msg = "☔ YES, UMBRELLA NEEDED! Baarish ke chances hain." if needs_umbrella else "☀️ NO UMBRELLA NEEDED! Mausam saaf hai."
    clothes_msg = "🏠 Kapde andar hi sukhayein." if needs_umbrella else "👕 Bahar kapde sukhane ke liye achha din hai."

    lines = [
        f"📍 Jagah: {loc}",
        f"🌤️ Mausam: {condition}",
        f"🌡️ Taapman: {temp}°C",
        f"🌡️ Feels like: {feels_like}°C",
        f"💧 Nami (Humidity): {humidity}%",
        f"🌧️ Live Baarish: {rain_mm} mm",
        f"💨 Hawa: {wind_kmh} km/h",
        "",
        "💡 ROZMARRA KI SALAH (DAILY HELPER):",
        f"• Umbrella Advice: {umbrella_msg}",
        f"• Clothes Advice: {clothes_msg}",
        f"• Agle 12 ghante mein baarish ka chance: {precip_prob}%",
        "",
        "⏰ AGLE 6 GHANTO KA MAUSAM:",
    ]

    for h in today_hourly[:6]:
        time_str = h["time"].split(" ")[-1]
        lines.append(f"  • {time_str} -> {h['temp_c']}°C | Baarish Chance: {h['chance_of_rain']}% | {h['condition']['text']}")

    lines.extend(["", "🔮 AGLE 7 DINO KA FORECAST:"])
    for day in forecast_days:
        date = day["date"]
        max_t = day["day"]["maxtemp_c"]
        min_t = day["day"]["mintemp_c"]
        cond = day["day"]["condition"]["text"]
        prob = day["day"]["daily_chance_of_rain"]
        lines.append(f"📅 {date} | Max {max_t}°C | Min {min_t}°C | {cond} | Baarish Chance: {prob}%")

    return "\n".join(lines)


@app.post("/api/chat")
async def chat(payload: UserQuery) -> Dict[str, Any]:
    message = payload.message.strip()
    location_query = extract_location(message)

    if not location_query:
        return {
            "status": "need_location",
            "reply": "Aap kis city ya location ka status janna chahte hain? Kripya location ka naam batayein.",
        }

    weather_data = fetch_weather_data(location_query)
    if not weather_data:
        return {
            "status": "failed",
            "reply": f"Maaf kijiye, mujhe '{location_query}' ki location ya data nahi mila. Kripya sahi spelling check karein.",
        }

    loc_name = weather_data["location"]["name"] + ", " + weather_data["location"]["region"]
    current_rain = weather_data["current"]["precip_mm"]

    # 1. Agar User ne SIRF Waterlogging / Paani bharne ke baare mein poocha hai
    if is_waterlogging_query(message):
        waterlog_status = check_waterlogging_risk(loc_name, current_rain)
        report = (
            f"📍 Jagah: {loc_name}\n"
            f"📅 Taareekh: Today (Aaj)\n"
            f"🌧️ Aaj ki Live Baarish: {current_rain} mm\n\n"
            f"🌊 WATERLOGGING STATUS:\n"
            f"{waterlog_status}"
        )
        return {
            "status": "success",
            "reply": report,
            "data": {
                "location": loc_name,
                "current_rain_mm": current_rain,
                "waterlogging": waterlog_status
            },
        }

    # 2. Agar Mausam (Weather) poocha hai toh Complete Follow-ups ke saath Output
    full_report = make_full_weather_report(weather_data)
    return {
        "status": "success",
        "reply": full_report,
        "data": weather_data
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
