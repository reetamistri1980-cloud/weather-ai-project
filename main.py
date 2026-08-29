import re
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Hyper-Local & Agricultural Weather AI Chatbot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class UserQuery(BaseModel):
    message: str

# Local Landmark Coordinates Mapping
LANDMARK_COORDS = {
    "connaught place": {"name": "Connaught Place, New Delhi, Delhi, India", "lat": 28.6315, "lon": 77.2167},
    "cp": {"name": "Connaught Place, New Delhi, Delhi, India", "lat": 28.6315, "lon": 77.2167},
    "chandni chowk": {"name": "Chandni Chowk, Central Delhi, Delhi, India", "lat": 28.6506, "lon": 77.2303},
    "rohini": {"name": "Rohini, North West Delhi, Delhi, India", "lat": 28.7041, "lon": 77.1025},
    "dwarka": {"name": "Dwarka, South West Delhi, Delhi, India", "lat": 28.5921, "lon": 77.0460},
}

def extract_location(text: str) -> str:
    msg = text.strip().lower()

    # Check for direct local landmark first
    for landmark in LANDMARK_COORDS:
        if re.search(r'\b' + re.escape(landmark) + r'\b', msg):
            return landmark

    # Extract location after prepositions (in, of, at, near, for)
    match = re.search(r"(?:weather|wheather|wether|temp|mausam|farming|fasal|detail|details)\s+(?:in|of|at|near|for)\s+(.+)", msg, re.IGNORECASE)
    if match:
        loc = match.group(1).strip()
        loc = re.sub(r"[?.!,]+$", "", loc).strip()
        return loc

    # Remove generic keywords to leave location string
    cleaned = re.sub(r"\b(weather|wheather|wether|temp|mausam|farming|fasal|detail|details|info|show|give|me)\b", "", msg, flags=re.IGNORECASE).strip()
    return cleaned if cleaned else "Delhi"

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
            
            # Extract City/Area, District, State, and Country details
            name = loc.get("name", "")
            district = loc.get("admin2", "")
            state = loc.get("admin1", "")
            country = loc.get("country", "")

            # Build detailed hierarchy string
            parts = [p for p in [name, district, state, country] if p and p.lower() not in [x.lower() for x in [name] if x != p]]
            # Deduplicate location hierarchy elements
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

def fetch_agri_and_local_weather(lat: float, lon: float):
    weather_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,rain,weather_code,wind_speed_10m",
        "hourly": "soil_temperature_0_to_10cm,soil_moisture_0_to_1cm",
        "timezone": "auto"
    }

    res = requests.get(weather_url, params=params, timeout=10).json()
    current = res.get("current", {})
    hourly = res.get("hourly", {})

    soil_temp = hourly.get("soil_temperature_0_to_10cm", [None])[0]
    soil_moisture = hourly.get("soil_moisture_0_to_1cm", [None])[0]

    return {
        "temp": current.get("temperature_2m"),
        "feels_like": current.get("apparent_temperature"),
        "humidity": current.get("relative_humidity_2m"),
        "rain": current.get("rain"),
        "wind": current.get("wind_speed_10m"),
        "soil_temp": soil_temp,
        "soil_moisture": soil_moisture,
    }

def generate_report(loc_name: str, data: dict) -> str:
    humidity = data["humidity"] if data["humidity"] is not None else 0
    moisture = data["soil_moisture"] if data["soil_moisture"] is not None else 0
    
    if humidity > 60 and moisture > 0.2:
        farming_advice = "🌱 **Farming Suggestion:** Soil moisture and humidity are optimal for sowing and irrigation!"
    elif humidity < 35:
        farming_advice = "🌾 **Farming Suggestion:** Air is dry. Proper field irrigation (paani dena) is recommended."
    else:
        farming_advice = "🚜 **Farming Suggestion:** Conditions are moderate for standard agricultural activities."

    return (
        f"📍 **Location:** {loc_name}\n"
        f"────────────────────────\n"
        f"🌡️ **Temperature:** {data['temp']}°C (Feels like {data['feels_like']}°C)\n"
        f"💧 **Air Humidity:** {data['humidity']}%\n"
        f"🌧️ **Rainfall:** {data['rain']} mm\n"
        f"💨 **Wind Speed:** {data['wind']} km/h\n"
        f"────────────────────────\n"
        f"🧪 **Agricultural / Soil Data:**\n"
        f"🌱 **Soil Temp (0-10cm):** {data['soil_temp']}°C\n"
        f"💦 **Soil Moisture (0-1cm):** {data['soil_moisture']} m³/m³\n\n"
        f"{farming_advice}"
    )

@app.get("/")
def home():
    return {"status": "online", "message": "Hyper-local & Agricultural Weather API Ready"}

@app.post("/api/chat")
def chat(payload: UserQuery):
    msg = payload.message.strip()
    if not msg:
        return {"status": "failed", "reply": "Please send a message."}

    target_loc = extract_location(msg)
    coords = get_location_coordinates(target_loc)

    if not coords:
        return {"status": "failed", "reply": f"Could not find coordinates for '{target_loc}'."}

    weather_data = fetch_agri_and_local_weather(coords["lat"], coords["lon"])
    report = generate_report(coords["name"], weather_data)

    return {
        "status": "success",
        "reply": report,
        "data": weather_data
    }
