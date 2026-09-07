import json
import logging
import os
import re
from datetime import datetime
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError

from google import genai
from google.genai import types


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("gemini-weather-api")


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="Gemini Real-Time Multilingual Weather API",
    version="3.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# GEMINI CLIENT
# ============================================================

if not GEMINI_API_KEY:
    logger.warning(
        "GEMINI_API_KEY is missing. "
        "Create a .env file and add GEMINI_API_KEY."
    )
    gemini_client = None
else:
    try:
        gemini_client = genai.Client(
            api_key=GEMINI_API_KEY
        )
        logger.info(
            "Gemini client initialized. Model=%s",
            GEMINI_MODEL,
        )
    except Exception as exc:
        gemini_client = None
        logger.exception(
            "Failed to initialize Gemini client: %s",
            exc,
        )


# ============================================================
# REQUEST MODEL
# ============================================================

class UserQuery(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
    )


# ============================================================
# WEATHER MODELS
# ============================================================

class CurrentWeather(BaseModel):
    temperature_c: Optional[float] = None
    feels_like_c: Optional[float] = None
    humidity_percent: Optional[float] = None

    precipitation_mm: Optional[float] = None
    rain_mm: Optional[float] = None
    precipitation_probability_percent: Optional[float] = None

    wind_speed_kmh: Optional[float] = None
    wind_direction_deg: Optional[float] = None

    pressure_hpa: Optional[float] = None
    uv_index: Optional[float] = None

    condition: str = "Unknown"


class HourlyForecast(BaseModel):
    time: str
    temperature_c: Optional[float] = None
    feels_like_c: Optional[float] = None
    precipitation_probability_percent: Optional[float] = None
    precipitation_mm: Optional[float] = None
    rain_mm: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    condition: str = "Unknown"


class DailyForecast(BaseModel):
    date: str

    max_temperature_c: Optional[float] = None
    min_temperature_c: Optional[float] = None

    precipitation_probability_percent: Optional[float] = None
    precipitation_mm: Optional[float] = None

    max_wind_speed_kmh: Optional[float] = None
    uv_index_max: Optional[float] = None

    sunrise: Optional[str] = None
    sunset: Optional[str] = None

    condition: str = "Unknown"


class AgricultureInfo(BaseModel):
    soil_condition: Optional[str] = None
    irrigation_advice: Optional[str] = None
    rainfall_advice: Optional[str] = None
    farming_advice: Optional[str] = None


class WeatherResponse(BaseModel):
    location: str

    country: str = "India"

    timezone: Optional[str] = None

    observation_time: Optional[str] = None

    current: CurrentWeather

    hourly_forecast: List[HourlyForecast] = Field(
        default_factory=list
    )

    daily_forecast: List[DailyForecast] = Field(
        default_factory=list
    )

    agriculture: AgricultureInfo = Field(
        default_factory=AgricultureInfo
    )

    summary: str

    language: str = "en"

    sources: List[str] = Field(
        default_factory=list
    )


# ============================================================
# LANGUAGE DETECTION
# ============================================================

HINGLISH_WORDS = {
    "kaisa",
    "kaise",
    "kesa",
    "kese",
    "kya",
    "batao",
    "btao",
    "mausam",
    "mosam",
    "aaj",
    "kal",
    "baarish",
    "barish",
    "garmi",
    "sardi",
    "fasal",
    "kheti",
    "mitti",
    "nami",
    "taapman",
    "hawa",
    "rahega",
    "rahegi",
    "hai",
    "hain",
    "mein",
    "me",
    "ka",
    "ki",
    "ke",
    "kab",
    "kitna",
    "kitni",
    "dikhao",
    "chahiye",
}


def detect_language(text: str) -> str:
    """
    Detect:
      hi = Hindi
      bn = Bengali
      hinglish = Roman Hindi/Hinglish
      en = English
    """

    if re.search(r"[\u0980-\u09FF]", text):
        return "bn"

    if re.search(r"[\u0900-\u097F]", text):
        return "hi"

    words = re.findall(
        r"[A-Za-z]+",
        text.lower(),
    )

    if any(word in HINGLISH_WORDS for word in words):
        return "hinglish"

    return "en"


# ============================================================
# LANGUAGE NAMES
# ============================================================

LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "bn": "Bengali",
    "hinglish": "Hinglish",
}


# ============================================================
# GEMINI PROMPT
# ============================================================

def build_weather_prompt(
    user_message: str,
    language: str,
) -> str:

    language_name = LANGUAGE_NAMES.get(
        language,
        "English",
    )

    current_date = datetime.now().strftime(
        "%Y-%m-%d"
    )

    return f"""
You are a real-time weather assistant for India.

IMPORTANT:
- Use Google Search to obtain CURRENT weather information.
- Do NOT rely only on your internal knowledge.
- Do NOT invent weather values.
- Search for the requested location specifically.
- Prefer reliable weather sources and official/recognized meteorological sources.
- The current date is {current_date}.
- If the user asks for "today", use today's date.
- If the user asks for "tomorrow", use tomorrow's date.
- If the user asks for a forecast, provide actual forecast information.
- If a value genuinely cannot be found, return null.
- NEVER replace an unknown value with 0.
- NEVER guess a numeric weather value.
- Keep all temperatures in Celsius.
- Keep wind speed in km/h.
- Keep pressure in hPa.
- Keep precipitation in mm.
- UV index should be numeric when available.

USER LANGUAGE:
{language_name}

USER REQUEST:
{user_message}

WEATHER DATA REQUIREMENTS:

Current:
- temperature
- feels like
- humidity
- precipitation
- rain
- precipitation probability
- wind speed
- wind direction
- pressure
- UV index
- weather condition

Hourly:
Provide the next 24 hours when the information is available.

Daily:
Provide up to 7 days when available.

Agriculture:
If the user asks about farming, crops, soil, irrigation, rain,
or agriculture, provide useful weather-based advice.
Do not invent soil measurements.
If actual soil information cannot be established from reliable
sources, leave soil_condition null.

LOCATION:
Resolve the requested city, district, state, or landmark accurately.

SUMMARY:
Write a concise natural-language summary in {language_name}.

SOURCE:
The data must be grounded using Google Search.
Return source URLs when available.

Remember:
Numeric values must come from searched information.
If unavailable, use null instead of guessing.
"""


# ============================================================
# GEMINI CALL
# ============================================================

def call_gemini_weather(
    user_message: str,
    language: str,
) -> WeatherResponse:

    if gemini_client is None:
        raise RuntimeError(
            "Gemini client is not initialized. "
            "Check GEMINI_API_KEY."
        )

    prompt = build_weather_prompt(
        user_message=user_message,
        language=language,
    )

    search_tool = types.Tool(
        google_search=types.GoogleSearch()
    )

    config = types.GenerateContentConfig(
        tools=[search_tool],

        response_mime_type="application/json",

        response_schema=WeatherResponse,

        temperature=0.1,

        system_instruction=(
            "You are a precise real-time weather data assistant. "
            "Always use Google Search grounding for weather data. "
            "Never fabricate numerical values. "
            "Use null when a value cannot be verified."
        ),
    )

    logger.info(
        "Sending weather request to Gemini. Model=%s",
        GEMINI_MODEL,
    )

    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=config,
    )

    if response is None:
        raise RuntimeError(
            "Gemini returned an empty response."
        )

    raw_text = getattr(
        response,
        "text",
        None,
    )

    if not raw_text:
        raise RuntimeError(
            "Gemini returned no text output."
        )

    logger.info(
        "Gemini response received successfully."
    )

    logger.debug(
        "Gemini raw response: %s",
        raw_text,
    )

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Gemini returned invalid JSON: {exc}"
        ) from exc

    try:
        result = WeatherResponse.model_validate(data)
    except ValidationError as exc:
        raise RuntimeError(
            f"Gemini weather response failed validation: {exc}"
        ) from exc

    # --------------------------------------------------------
    # Grounding sources
    # --------------------------------------------------------

    sources = extract_grounding_sources(
        response
    )

    if sources:
        result.sources = sources

    return result


# ============================================================
# GROUNDING SOURCE EXTRACTION
# ============================================================

def extract_grounding_sources(
    response: Any,
) -> List[str]:

    sources: List[str] = []

    """
    Gemini SDK response structures can vary between SDK/model
    versions, so this function intentionally checks defensively.
    """

    try:
        candidates = getattr(
            response,
            "candidates",
            None,
        )

        if not candidates:
            return sources

        for candidate in candidates:

            grounding_metadata = getattr(
                candidate,
                "grounding_metadata",
                None,
            )

            if not grounding_metadata:
                continue

            chunks = getattr(
                grounding_metadata,
                "grounding_chunks",
                None,
            )

            if not chunks:
                continue

            for chunk in chunks:

                web = getattr(
                    chunk,
                    "web",
                    None,
                )

                if not web:
                    continue

                uri = getattr(
                    web,
                    "uri",
                    None,
                )

                if uri and uri not in sources:
                    sources.append(uri)

    except Exception as exc:
        logger.warning(
            "Could not extract grounding sources: %s",
            exc,
        )

    return sources[:10]


# ============================================================
# NULL / MISSING VALUE CHECK
# ============================================================

def find_missing_current_values(
    weather: WeatherResponse,
) -> List[str]:

    current = weather.current

    required_fields = {
        "temperature_c": current.temperature_c,
        "feels_like_c": current.feels_like_c,
        "humidity_percent": current.humidity_percent,
        "condition": current.condition,
    }

    missing = [
        name
        for name, value in required_fields.items()
        if value is None
        or (
            isinstance(value, str)
            and not value.strip()
        )
    ]

    return missing


# ============================================================
# USER-FRIENDLY RESPONSE
# ============================================================

def make_fallback_reply(
    weather: WeatherResponse,
) -> str:

    current = weather.current

    parts = [
        f"📍 {weather.location}",
        f"🌤️ {current.condition}",
    ]

    if current.temperature_c is not None:
        parts.append(
            f"🌡️ Temperature: "
            f"{current.temperature_c}°C"
        )

    if current.feels_like_c is not None:
        parts.append(
            f"🌡️ Feels like: "
            f"{current.feels_like_c}°C"
        )

    if current.humidity_percent is not None:
        parts.append(
            f"💧 Humidity: "
            f"{current.humidity_percent}%"
        )

    if current.precipitation_mm is not None:
        parts.append(
            f"🌧️ Precipitation: "
            f"{current.precipitation_mm} mm"
        )

    if current.rain_mm is not None:
        parts.append(
            f"🌧️ Rain: "
            f"{current.rain_mm} mm"
        )

    if current.wind_speed_kmh is not None:
        parts.append(
            f"💨 Wind: "
            f"{current.wind_speed_kmh} km/h"
        )

    if current.wind_direction_deg is not None:
        parts.append(
            f"🧭 Wind direction: "
            f"{current.wind_direction_deg}°"
        )

    if current.pressure_hpa is not None:
        parts.append(
            f"⏲️ Pressure: "
            f"{current.pressure_hpa} hPa"
        )

    if current.uv_index is not None:
        parts.append(
            f"☀️ UV Index: "
            f"{current.uv_index}"
        )

    if weather.observation_time:
        parts.append(
            f"🕐 Updated: "
            f"{weather.observation_time}"
        )

    if weather.summary:
        parts.append(
            f"\n{weather.summary}"
        )

    return "\n".join(parts)


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/")
def home():
    return {
        "status": "online",
        "service": "Gemini Real-Time Weather API",
        "gemini_configured": gemini_client is not None,
        "model": GEMINI_MODEL,
        "grounding": "Google Search",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "gemini_configured": gemini_client is not None,
        "model": GEMINI_MODEL,
    }


# ============================================================
# MAIN CHAT ENDPOINT
# ============================================================

@app.post("/api/chat")
def chat(payload: UserQuery):

    message = payload.message.strip()

    if not message:
        return {
            "status": "failed",
            "reply": "Please send a weather question.",
            "data": None,
        }

    language = detect_language(message)

    logger.info(
        "User query: %s | language=%s",
        message,
        language,
    )

    # --------------------------------------------------------
    # Gemini
    # --------------------------------------------------------

    try:
        weather = call_gemini_weather(
            user_message=message,
            language=language,
        )

    except Exception as exc:

        logger.exception(
            "Weather request failed."
        )

        return {
            "status": "failed",
            "reply": (
                "Live weather data fetch nahi ho paya. "
                "Gemini/Search service error hua hai."
            ),
            "error": str(exc),
            "data": None,
        }

    # --------------------------------------------------------
    # Check important values
    # --------------------------------------------------------

    missing_values = find_missing_current_values(
        weather
    )

    # We don't convert missing values into fake 0/N/A.
    # We explicitly expose what is missing.

    reply = make_fallback_reply(
        weather
    )

    # --------------------------------------------------------
    # Final response
    # --------------------------------------------------------

    return {
        "status": "success",

        "reply": reply,

        "language": language,

        "location": {
            "name": weather.location,
            "country": weather.country,
            "timezone": weather.timezone,
        },

        "data": {
            "current": weather.current.model_dump(),

            "hourly_forecast": [
                item.model_dump()
                for item in weather.hourly_forecast
            ],

            "daily_forecast": [
                item.model_dump()
                for item in weather.daily_forecast
            ],

            "agriculture": (
                weather.agriculture.model_dump()
            ),

            "observation_time": (
                weather.observation_time
            ),

            "timezone": weather.timezone,

            "sources": weather.sources,

            "missing_current_values": missing_values,
        },

        "meta": {
            "provider": "Google Gemini",
            "model": GEMINI_MODEL,
            "grounding": "Google Search",
            "generated_at": datetime.utcnow().isoformat()
            + "Z",
        },
    }


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )
