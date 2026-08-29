import os
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

app = FastAPI(title="Weather AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class UserQuery(BaseModel):
    message: str

def fetch_weather(city: str):
    if not city or city.lower() == "none":
        return None
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric"
        res = requests.get(url, timeout=5).json()
        if res.get("cod") == 200:
            return {
                "city": res["name"],
                "temperature": res["main"]["temp"],
                "feels_like": res["main"]["feels_like"],
                "humidity": res["main"]["humidity"],
                "condition": res["weather"][0]["description"],
                "wind_speed": res["wind"]["speed"]
            }
    except Exception:
        pass
    return None

def extract_city_smart(user_msg: str) -> str:
    """Uses Gemini to identify if a city is mentioned in ANY sentence format."""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={GEMINI_API_KEY}"
        headers = {'Content-Type': 'application/json'}
        prompt = (
            f"Analyze this query: '{user_msg}'. "
            f"If the user is asking about weather in a specific city, return ONLY that city name in English. "
            f"If no city is explicitly named but they ask about weather, return 'Delhi'. "
            f"If the query is NOT about weather, return 'NONE'. Do not include punctuation or extra words."
        )
        data = {"contents": [{"parts": [{"text": prompt}]}]}
        res = requests.post(url, headers=headers, json=data, timeout=5).json()
        city = res['candidates'][0]['content']['parts'][0]['text'].strip()
        return city
    except Exception:
        return "Delhi"

@app.get("/")
def home():
    return {"status": "Backend server running!"}

@app.post("/api/chat")
def handle_chat(payload: UserQuery):
    try:
        user_msg = payload.message
        city = extract_city_smart(user_msg)
        
        weather_data = None
        if city != "NONE":
            weather_data = fetch_weather(city)

        if weather_data:
            prompt = (
                f"User Question: '{user_msg}'\n"
                f"LIVE WEATHER DATA FOR {city}: {weather_data}\n\n"
                f"INSTRUCTIONS:\n"
                f"1. Answer the user's question accurately using the live weather data provided.\n"
                f"2. Keep the response clear, natural, and simple in English."
            )
        else:
            prompt = (
                f"User Question: '{user_msg}'\n\n"
                f"INSTRUCTIONS:\n"
                f"1. Answer the user's question directly and helpfully.\n"
                f"2. Keep the response in clear, simple English."
            )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={GEMINI_API_KEY}"
        headers = {'Content-Type': 'application/json'}
        data = {"contents": [{"parts": [{"text": prompt}]}]}
        
        response = requests.post(url, headers=headers, json=data, timeout=10)
        res_data = response.json()
        
        if response.status_code == 200:
            reply_text = res_data['candidates'][0]['content']['parts'][0]['text']
            return {
                "reply": reply_text,
                "weather_card": weather_data,
                "status": "success"
            }
        else:
            return {"error_detail": res_data, "status": "failed"}

    except Exception as e:
        return {"error_detail": str(e), "status": "failed"}
