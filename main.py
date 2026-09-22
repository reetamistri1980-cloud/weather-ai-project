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

app = FastAPI(title="All-India Weather & Waterlogging API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UserQuery(BaseModel):
    message: str


WATERLOGGING_HOTSPOTS = {
    "delhi": ["minto bridge", "ito", "pul prahladpur", "loni", "dhaula kuan", "najafgarh", "laxmi nagar", "karol bagh", "dwarka", "ashok vihar", "sangam vihar", "connaught place", "cp", "rohini", "chandni chowk"],
    "mumbai": ["hindmata", "king circle", "kurla", "andheri subway", "dadar", "sion", "bandra", "malad subway"],
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

WMO = {
    0: "Clear sky ☀️", 1: "Mainly clear 🌤️", 2: "Partly cloudy ⛅", 3: "Overcast ☁️",
    45: "Foggy 🌫️", 48: "Rime fog 🌫️", 51: "Light drizzle 🌦️", 53: "Moderate drizzle 🌦️",
    55: "Dense drizzle 🌧️", 61: "Slight rain 🌧️", 63: "Moderate rain 🌧️", 65: "Heavy rain 🌧️",
    80: "Slight rain showers 🌦️", 81: "Moderate rain showers 🌧️", 82: "Violent rain showers ⛈️",
    95: "Thunderstorm ⛈️", 96: "Thunderstorm with slight hail ⛈️", 99: "Thunderstorm with heavy hail ⛈️",
}

HINGLISH_WORDS = {
    "kaisa", "kaise", "kesa", "kese", "kya", "batao", "btao", "mausam", "mosam",
    "aaj", "kal", "baarish", "barish", "garmi", "sardi", "fasal", "kheti", "mitti",
    "nami", "taapman", "hawa", "rahega", "rahegi", "hai", "hain", "mein", "me", "ka",
    "ki", "ke", "kab", "kitna", "kitni", "dikhao", "chahiye", "chhatri", "umbrella",
    "kapde", "waterlogging", "paani", "jam", "block", "water",
}


def norm(text: str) -> str:
    text = text.strip().lower().replace("’", "'")
    return re.sub(r"\s+", " ", text).strip(" ?!.,;:")


def detect_language(text: str) -> str:
    if re.search(r"[\u0900-\u097F]", text):
        return "hi"
    words = re.findall(r"[A-Za-z]+", text.lower())
    return "hinglish" if any(w in HINGLISH_WORDS for w in words) else "en"


def is_waterlogging_query(text: str) -> bool:
    raw = norm(text)
    keywords = ["waterlogging", "paani", "pani", "water", "jam", "block", "waterlog", "jal jamav"]
    return any(kw in raw for kw in keywords)


def extract_location(text: str) -> Optional[str]:
    raw = norm(text)

    # 1. Landmark & Hotspot Matching
    for key, val in LANDMARKS.items():
        if key in raw:
            return val

    for key, val in INDIA_ALIASES.items():
        if re.search(rf"\b{re.escape(key)}\b", raw, re.I):
            return val

    # 2. Regex Match for Cities/Places
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

    # 3. Clean word check
    words = [w for w in raw.split() if w not in HINGLISH_WORDS]
    if words:
        return " ".join(words)

    return None


def geocode(location: str) -> Optional[Dict[str, Any]]:
    key = norm(location)
    if key in LANDMARKS:
        search_query = LANDMARKS[key]
    else:
        search_query = INDIA_ALIASES.get(key, location)

    url = "https://geocoding-api.open-meteo.com/v1/search"
    try:
        res = requests.get(url, params={"name": search_query, "count": 1, "language": "en"}, timeout=5).json()
        results = res.get("results")
        if results:
            item = results[0]
            parts = [item.get("name"), item.get("admin2"), item.get("admin1"), item.get("country")]
            unique_parts = [p for p in parts if p and p not in []]
            return {
                "name": ", ".join(dict.fromkeys(unique_parts)),
                "latitude": item["latitude"],
                "longitude": item["longitude"],
            }
    except Exception:
        pass
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


def make_full_weather_report(location: Dict[str, Any], payload: Dict[str, Any]) -> str:
    current = payload.get("current", {})
    hourly = payload.get("hourly", {})
    daily = payload.get("daily", {})

    code = current.get("weather_code", 0)
    condition = WMO.get(code, "Clear sky ☀️")

    rain = current.get("rain", 0.0) or 0.0
    precip_prob = max((hourly.get("precipitation_probability") or [0])[:12], default=0)

    needs_umbrella = rain > 0.1 or precip_prob >= 30
    umbrella_msg = "☔ YES, UMBRELLA NEEDED! Baarish ke chances hain." if needs_umbrella else "☀️ NO UMBRELLA NEEDED! Mausam saaf hai."
    clothes_msg = "🏠 Kapde andar hi sukhayein." if needs_umbrella else "👕 Bahar kapde sukhane ke liye achha din hai."

    soil_temp = (hourly.get("soil_temperature_0_to_10cm") or ["N/A"])[0]
    soil_moisture = (hourly.get("soil_moisture_0_to_1cm") or ["N/A"])[0]

    lines = [
        f"📍 Jagah: {location['name']}",
        f"🌤️ Mausam: {condition}",
        f"🌡️ Taapman: {current.get('temperature_2m', 'N/A')}°C",
        f"🌡️ Feels like: {current.get('apparent_temperature', 'N/A')}°C",
        f"💧 Nami (Humidity): {current.get('relative_humidity_2m', 'N/A')}%",
        f"🌧️ Baarish: {rain} mm",
        f"💨 Hawa: {current.get('wind_speed_10m', 'N/A')} km/h",
        "",
        "💡 ROZMARRA KI SALAH (DAILY HELPER):",
        f"• Umbrella Advice: {umbrella_msg}",
        f"• Clothes Advice: {clothes_msg}",
        f"• Agle 12 ghante mein baarish ka chance: {precip_prob}%",
        "",
        "🌱 KHETI AUR MITTI KI JAANKARI:",
        f"Mitti ka taapman (0-10 cm): {soil_temp}°C",
        f"Mitti ki nami (0-1 cm): {soil_moisture} m³/m³",
        "",
        "⏰ AGLE 6 GHANTO KA MAUSAM:",
    ]

    times = hourly.get("time", [])[:6]
    temps = hourly.get("temperature_2m", [])[:6]
    probs = hourly.get("precipitation_probability", [])[:6]
    codes = hourly.get("weather_code", [])[:6]

    for t, temp, prob, c in zip(times, temps, probs, codes):
        t_str = t.split("T")[-1] if "T" in t else t
        lines.append(f"  • {t_str} -> {temp}°C | Baarish Chance: {prob}% | {WMO.get(c, 'Clear')}")

    lines.extend(["", "🔮 AGLE 7 DINO KA FORECAST:"])
    d_dates = daily.get("time", [])[:7]
    d_max = daily.get("temperature_2m_max", [])[:7]
    d_min = daily.get("temperature_2m_min", [])[:7]
    d_codes = daily.get("weather_code", [])[:7]
    d_probs = daily.get("precipitation_probability_max", [])[:7]

    for date, mx, mn, c, pr in zip(d_dates, d_max, d_min, d_codes, d_probs):
        lines.append(f"📅 {date} | Max {mx}°C | Min {mn}°C | {WMO.get(c, 'Clear')} | Baarish Chance: {pr}%")

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

    geo = geocode(location_query)
    if not geo:
        return {"status": "failed", "reply": f"Maaf kijiye, mujhe '{location_query}' ki location nahi mili."}

    # Weather API Call
    url = f"https://api.open-meteo.com/v1/forecast?latitude={geo['latitude']}&longitude={geo['longitude']}&current=temperature_2m,relative_humidity_2m,apparent_temperature,rain,weather_code,wind_speed_10m&hourly=temperature_2m,precipitation_probability,weather_code,soil_temperature_0_to_10cm,soil_moisture_0_to_1cm&daily=temperature_2m_max,temperature_2m_min,weather_code,precipitation_probability_max&timezone=auto"

    try:
        res = requests.get(url, timeout=8).json()
    except Exception:
        return {"status": "failed", "reply": "Data fetch karne mein dikkat aayi."}

    current_rain = res.get("current", {}).get("rain", 0.0) or 0.0

    # 1. Agar question SIRF Waterlogging se juda hai
    if is_waterlogging_query(message):
        waterlog_status = check_waterlogging_risk(geo["name"], current_rain)
        report = (
            f"📍 Jagah: {geo['name']}\n"
            f"📅 Taareekh: Today (Aaj)\n"
            f"🌧️ Aaj ki Baarish: {current_rain} mm\n\n"
            f"🌊 WATERLOGGING STATUS:\n"
            f"{waterlog_status}"
        )
        return {
            "status": "success",
            "reply": report,
            "data": {"waterlogging": waterlog_status, "current_rain_mm": current_rain},
        }

    # 2. Agar Mausam (Weather) ka poochha hai toh saare purane follow-ups ke saath answer
    full_report = make_full_weather_report(geo, res)
    return {"status": "success", "reply": full_report, "data": res}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
