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

app = FastAPI(title="All-India Multilingual Real-Time Weather API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UserQuery(BaseModel):
    message: str


# Prevent ambiguous searches such as "Bengal" from resolving to Indonesia.
INDIA_ALIASES = {
    "up": "Uttar Pradesh, India",
    "u.p.": "Uttar Pradesh, India",
    "uttar pradesh": "Uttar Pradesh, India",
    "west bengal": "West Bengal, India",
    "wb": "West Bengal, India",
    "w.b.": "West Bengal, India",
    "bengal": "West Bengal, India",
    "mp": "Madhya Pradesh, India",
    "m.p.": "Madhya Pradesh, India",
    "madhya pradesh": "Madhya Pradesh, India",
    "rj": "Rajasthan, India",
    "rajasthan": "Rajasthan, India",
    "br": "Bihar, India",
    "bihar": "Bihar, India",
    "mh": "Maharashtra, India",
    "maharashtra": "Maharashtra, India",
    "gj": "Gujarat, India",
    "gujarat": "Gujarat, India",
    "pb": "Punjab, India",
    "punjab": "Punjab, India",
    "hr": "Haryana, India",
    "haryana": "Haryana, India",
    "hp": "Himachal Pradesh, India",
    "himachal pradesh": "Himachal Pradesh, India",
    "jk": "Jammu and Kashmir, India",
    "j&k": "Jammu and Kashmir, India",
    "odisha": "Odisha, India",
    "orissa": "Odisha, India",
    "jharkhand": "Jharkhand, India",
    "chhattisgarh": "Chhattisgarh, India",
    "uttarakhand": "Uttarakhand, India",
    "uk": "Uttarakhand, India",
    "goa": "Goa, India",
    "assam": "Assam, India",
    "meghalaya": "Meghalaya, India",
    "manipur": "Manipur, India",
    "mizoram": "Mizoram, India",
    "nagaland": "Nagaland, India",
    "tripura": "Tripura, India",
    "sikkim": "Sikkim, India",
    "arunachal pradesh": "Arunachal Pradesh, India",
    "tamil nadu": "Tamil Nadu, India",
    "tn": "Tamil Nadu, India",
    "kerala": "Kerala, India",
    "karnataka": "Karnataka, India",
    "andhra pradesh": "Andhra Pradesh, India",
    "ap": "Andhra Pradesh, India",
    "telangana": "Telangana, India",
    "delhi": "Delhi, India",
    "new delhi": "New Delhi, India",
    "mumbai": "Mumbai, India",
    "kolkata": "Kolkata, India",
    "calcutta": "Kolkata, India",
    "lucknow": "Lucknow, India",
    "kanpur": "Kanpur, India",
    "agra": "Agra, India",
    "varanasi": "Varanasi, India",
    "patna": "Patna, India",
    "jaipur": "Jaipur, India",
    "bhopal": "Bhopal, India",
    "indore": "Indore, India",
    "chandigarh": "Chandigarh, India",
    "hyderabad": "Hyderabad, India",
    "bengaluru": "Bengaluru, India",
    "bangalore": "Bengaluru, India",
    "chennai": "Chennai, India",
    "pune": "Pune, India",
    "ahmedabad": "Ahmedabad, India",
}

SCRIPT_ALIASES = {
    "दिल्ली": "Delhi, India", "नई दिल्ली": "New Delhi, India",
    "मुंबई": "Mumbai, India", "कोलकाता": "Kolkata, India",
    "लखनऊ": "Lucknow, India", "पटना": "Patna, India",
    "जयपुर": "Jaipur, India", "वाराणसी": "Varanasi, India",
    "उत्तर प्रदेश": "Uttar Pradesh, India",
    "पश्चिम बंगाल": "West Bengal, India",
    "দিল্লি": "Delhi, India", "মুম্বাই": "Mumbai, India",
    "কলকাতা": "Kolkata, India", "লখনউ": "Lucknow, India",
    "উত্তর প্রদেশ": "Uttar Pradesh, India",
    "পশ্চিমবঙ্গ": "West Bengal, India",
}

LANDMARKS = {
    "connaught place": {
        "name": "Connaught Place, New Delhi, Delhi, India",
        "latitude": 28.6315, "longitude": 77.2167,
        "country_code": "IN", "admin1": "Delhi", "admin2": "Central Delhi",
    },
    "cp": {
        "name": "Connaught Place, New Delhi, Delhi, India",
        "latitude": 28.6315, "longitude": 77.2167,
        "country_code": "IN", "admin1": "Delhi", "admin2": "Central Delhi",
    },
    "chandni chowk": {
        "name": "Chandni Chowk, Delhi, India",
        "latitude": 28.6506, "longitude": 77.2303,
        "country_code": "IN", "admin1": "Delhi", "admin2": "Central Delhi",
    },
    "rohini": {
        "name": "Rohini, Delhi, India",
        "latitude": 28.7041, "longitude": 77.1025,
        "country_code": "IN", "admin1": "Delhi", "admin2": "North West Delhi",
    },
    "dwarka": {
        "name": "Dwarka, Delhi, India",
        "latitude": 28.5921, "longitude": 77.0460,
        "country_code": "IN", "admin1": "Delhi", "admin2": "South West Delhi",
    },
}

WMO = {
    0: "Clear sky ☀️", 1: "Mainly clear 🌤️", 2: "Partly cloudy ⛅", 3: "Overcast ☁️",
    45: "Foggy 🌫️", 48: "Rime fog 🌫️", 51: "Light drizzle 🌦️", 53: "Moderate drizzle 🌦️",
    55: "Dense drizzle 🌧️", 56: "Freezing drizzle 🌧️", 57: "Freezing drizzle 🌧️",
    61: "Slight rain 🌧️", 63: "Moderate rain 🌧️", 65: "Heavy rain 🌧️",
    66: "Freezing rain 🌧️", 67: "Heavy freezing rain 🌧️", 71: "Slight snow 🌨️",
    73: "Moderate snow 🌨️", 75: "Heavy snow ❄️", 77: "Snow grains ❄️",
    80: "Slight rain showers 🌦️", 81: "Moderate rain showers 🌧️", 82: "Violent rain showers ⛈️",
    85: "Slight snow showers 🌨️", 86: "Heavy snow showers ❄️", 95: "Thunderstorm ⛈️",
    96: "Thunderstorm with slight hail ⛈️", 99: "Thunderstorm with heavy hail ⛈️",
}

HINGLISH_WORDS = {
    "kaisa", "kaise", "kesa", "kese", "kya", "batao", "btao", "mausam", "mosam",
    "aaj", "kal", "baarish", "barish", "garmi", "sardi", "fasal", "kheti", "mitti",
    "nami", "taapman", "hawa", "rahega", "rahegi", "hai", "hain", "mein", "me", "ka",
    "ki", "ke", "kab", "kitna", "kitni", "dikhao", "chahiye",
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


def clean_candidate(value: str) -> str:
    value = re.sub(r"[?.!,;:]+$", "", value.strip())
    value = re.sub(r"\s+(today|tomorrow|now|right now|please|pls|batao|btao)$", "", value, flags=re.I)
    return value.strip()


def extract_location(text: str) -> str:
    raw = norm(text)

    for key, value in sorted(SCRIPT_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
        if key.lower() in raw:
            return value

    patterns = [
        r"(?:weather|wheather|wether|temperature|temp|forecast|climate|mausam|mosam|rain|baarish|barish|farming|fasal|kheti)\s+(?:in|of|for|at|near|ka|ki|ke|mein|me|par)\s+(.+)$",
        r"(?:what is|what's|tell me|show me|give me)\s+(?:the\s+)?(?:weather|temperature|forecast|climate)\s+(?:in|of|for|at|near)\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw, re.I)
        if match:
            return clean_candidate(match.group(1)) or "Delhi"

    match = re.match(r"^(.+?)\s+(?:weather|wheather|wether|temperature|temp|forecast|climate)$", raw, re.I)
    if match:
        return clean_candidate(match.group(1)) or "Delhi"

    match = re.match(r"^(.+?)\s+(?:ka|ki|ke)\s+(?:mausam|mosam|weather|temperature|temp)$", raw, re.I)
    if match:
        return clean_candidate(match.group(1)) or "Delhi"

    # If the user typed only a location, accept the whole phrase.
    filler = re.sub(r"\b(please|pls|tell|me|show|give|weather|temperature|forecast|mausam|mosam)\b", "", raw, flags=re.I)
    filler = re.sub(r"\s+", " ", filler).strip()
    return clean_candidate(filler) or "Delhi"


def geocode(location: str) -> Optional[Dict[str, Any]]:
    key = norm(location)
    if key in LANDMARKS:
        return LANDMARKS[key]

    search_name = INDIA_ALIASES.get(key, location)
    queries = [search_name] if search_name.lower().endswith(", india") else [f"{location}, India", location]

    best = None
    best_score = -9999
    url = "https://geocoding-api.open-meteo.com/v1/search"

    for query in queries:
        params = {"name": query, "count": 20, "language": "en", "format": "json"}
        if query.lower().endswith(", india") or key in INDIA_ALIASES:
            params["countryCode"] = "IN"
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            results = response.json().get("results") or []
        except (requests.RequestException, ValueError):
            continue

        for item in results:
            score = 0
            country_code = str(item.get("country_code", "")).upper()
            name = norm(str(item.get("name", "")))
            admin1 = norm(str(item.get("admin1", "")))
            admin2 = norm(str(item.get("admin2", "")))
            if country_code == "IN":
                score += 100
            elif key in INDIA_ALIASES:
                score -= 200
            if name == key:
                score += 40
            if admin1 == key:
                score += 35
            if admin2 == key:
                score += 30
            if str(item.get("feature_code", "")).upper().startswith(("ADM", "PPL")):
                score += 10
            score += min(int(item.get("population") or 0) // 100000, 10)
            if score > best_score:
                best_score = score
                best = item

        if best is not None and best_score >= 120:
            break

    if not best:
        return None

    parts = [best.get("name"), best.get("admin2"), best.get("admin1"), best.get("country")]
    unique = []
    for part in parts:
        if part and part not in unique:
            unique.append(part)

    return {
        "name": ", ".join(unique),
        "latitude": best["latitude"],
        "longitude": best["longitude"],
        "country_code": best.get("country_code", ""),
        "admin1": best.get("admin1", ""),
        "admin2": best.get("admin2", ""),
        "feature_code": best.get("feature_code", ""),
        "timezone": best.get("timezone", "auto"),
    }


def fetch_weather(latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": ",".join([
            "temperature_2m", "relative_humidity_2m", "apparent_temperature",
            "precipitation", "rain", "weather_code", "surface_pressure",
            "wind_speed_10m", "wind_direction_10m", "uv_index", "is_day",
        ]),
        "hourly": ",".join([
            "temperature_2m", "relative_humidity_2m", "apparent_temperature",
            "precipitation_probability", "precipitation", "rain", "weather_code",
            "surface_pressure", "wind_speed_10m", "wind_direction_10m", "uv_index",
            "soil_temperature_0_to_10cm", "soil_moisture_0_to_1cm",
        ]),
        "daily": ",".join([
            "weather_code", "temperature_2m_max", "temperature_2m_min",
            "precipitation_sum", "precipitation_probability_max", "wind_speed_10m_max",
            "sunrise", "sunset", "uv_index_max",
        ]),
        "forecast_days": 7,
        "timezone": "auto",
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        print("Weather API error:", exc)
        return None


def list_value(mapping: Dict[str, Any], key: str) -> List[Any]:
    value = mapping.get(key)
    return value if isinstance(value, list) else []


def next_24_hours(hourly: Dict[str, Any], current_time: Optional[str] = None) -> List[Dict[str, Any]]:
    times = list_value(hourly, "time")
    start_index = 0
    if current_time and current_time in times:
        start_index = times.index(current_time)
    fields = [
        "temperature_2m", "relative_humidity_2m", "apparent_temperature",
        "precipitation_probability", "precipitation", "rain", "weather_code",
        "surface_pressure", "wind_speed_10m", "wind_direction_10m", "uv_index",
        "soil_temperature_0_to_10cm", "soil_moisture_0_to_1cm",
    ]
    rows = []
    selected_times = times[start_index:start_index + 24]
    for i, time_value in enumerate(selected_times, start=start_index):
        row = {"time": time_value}
        for field in fields:
            values = list_value(hourly, field)
            row[field] = values[i] if i < len(values) else None
        rows.append(row)
    return rows


def forecast_7_days(daily: Dict[str, Any]) -> List[Dict[str, Any]]:
    dates = list_value(daily, "time")
    fields = {
        "weather_code": "weather_code", "max_temperature": "temperature_2m_max",
        "min_temperature": "temperature_2m_min", "precipitation_sum": "precipitation_sum",
        "rain_probability": "precipitation_probability_max", "max_wind_speed": "wind_speed_10m_max",
        "sunrise": "sunrise", "sunset": "sunset", "uv_index_max": "uv_index_max",
    }
    rows = []
    for i, date_value in enumerate(dates[:7]):
        row = {"date": date_value}
        for output_name, source_name in fields.items():
            values = list_value(daily, source_name)
            row[output_name] = values[i] if i < len(values) else None
        row["condition"] = WMO.get(row["weather_code"], "Unknown")
        rows.append(row)
    return rows


def translate_report(text: str, language: str) -> str:
    if language in {"en", "hinglish"} or GoogleTranslator is None:
        return text
    try:
        return GoogleTranslator(source="en", target=language).translate(text)
    except Exception:
        return text


def make_report(location: Dict[str, Any], payload: Dict[str, Any], language: str) -> str:
    current = payload.get("current", {})
    hourly = payload.get("hourly", {})
    daily = payload.get("daily", {})
    code = current.get("weather_code")
    condition = WMO.get(code, "Unknown")

    first_24 = next_24_hours(hourly, current.get("time"))
    seven_days = forecast_7_days(daily)

    soil_temp = first_24[0].get("soil_temperature_0_to_10cm") if first_24 else None
    soil_moisture = first_24[0].get("soil_moisture_0_to_1cm") if first_24 else None

    lines = [
        f"📍 Location: {location['name']}",
        f"🌤️ Condition: {condition}",
        f"🌡️ Temperature: {current.get('temperature_2m', 'N/A')}°C",
        f"🌡️ Feels like: {current.get('apparent_temperature', 'N/A')}°C",
        f"💧 Humidity: {current.get('relative_humidity_2m', 'N/A')}%",
        f"🌧️ Rain: {current.get('rain', 'N/A')} mm",
        f"🌧️ Precipitation: {current.get('precipitation', 'N/A')} mm",
        f"💨 Wind: {current.get('wind_speed_10m', 'N/A')} km/h",
        f"🧭 Wind direction: {current.get('wind_direction_10m', 'N/A')}°",
        f"☀️ UV Index: {current.get('uv_index', 'N/A')}",
        f"⏲️ Pressure: {current.get('surface_pressure', 'N/A')} hPa",
        f"🕐 Updated: {current.get('time', 'N/A')}",
        "",
        "🌱 AGRICULTURE & SOIL DATA:",
        f"Soil temperature (0-10 cm): {soil_temp}°C",
        f"Soil moisture (0-1 cm): {soil_moisture} m³/m³",
        "",
        "🕐 NEXT 24 HOURS:",
    ]

    for row in first_24:
        lines.append(
            f"{row['time']} | {row['temperature_2m']}°C | "
            f"{WMO.get(row['weather_code'], 'Unknown')} | "
            f"Rain chance: {row['precipitation_probability']}% | Rain: {row['rain']} mm"
        )

    lines.append("")
    lines.append("🔮 7-DAY FORECAST:")
    for day in seven_days:
        lines.append(
            f"{day['date']} | Max {day['max_temperature']}°C | "
            f"Min {day['min_temperature']}°C | {day['condition']} | "
            f"Rain chance {day['rain_probability']}%"
        )

    english = "\n".join(lines)
    if language == "hinglish":
        # Keep data labels understandable while avoiding unreliable machine translation.
        english = english.replace("Location", "Jagah").replace("Condition", "Mausam")
        english = english.replace("Temperature", "Taapman").replace("Humidity", "Nami")
        english = english.replace("Rain", "Baarish").replace("Wind", "Hawa")
        english = english.replace("Agriculture & Soil Data", "Kheti aur Mitti ki Jaankari")
        english = english.replace("Soil temperature", "Mitti ka temperature")
        english = english.replace("Soil moisture", "Mitti ki nami")
        english = english.replace("NEXT 24 HOURS", "AGLE 24 GHANTE")
        english = english.replace("7-DAY FORECAST", "AGLE 7 DIN KA FORECAST")
        return english
    return translate_report(english, language)


@app.get("/")
def home() -> Dict[str, str]:
    return {"status": "online", "message": "All-India Multilingual Weather API is ready"}


@app.post("/api/chat")
def chat(payload: UserQuery) -> Dict[str, Any]:
    message = payload.message.strip()
    if not message:
        return {"status": "failed", "reply": "Please send a location or weather question.", "data": None}

    language = detect_language(message)
    location_query = extract_location(message)
    location = geocode(location_query)

    if not location:
        return {
            "status": "failed",
            "reply": f"Could not find '{location_query}'. Try a city, district, state, or country name.",
            "data": None,
        }

    weather = fetch_weather(location["latitude"], location["longitude"])
    if not weather:
        return {"status": "failed", "reply": "Could not fetch live weather data right now.", "data": None}

    first_24 = next_24_hours(weather.get("hourly", {}), weather.get("current", {}).get("time"))
    seven_days = forecast_7_days(weather.get("daily", {}))
    report = make_report(location, weather, language)

    return {
        "status": "success",
        "reply": report,
        "location": location,
        "data": {
            "current": weather.get("current", {}),
            "next_24_hours": first_24,
            "seven_day_forecast": seven_days,
            "timezone": weather.get("timezone", "auto"),
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
