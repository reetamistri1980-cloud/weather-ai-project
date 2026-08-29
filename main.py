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
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric"
        res = requests.get(url).json()
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

def extract_city_with_gemini(user_msg: str) -> str:
    """Uses Gemini to reliably extract the city name from any language or phrasing."""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={GEMINI_API_KEY}"
        headers = {'Content-Type': 'application/json'}
        prompt = (
            f"Extract only the target city name from this user query: '{user_msg}'. "
            f"If no specific city is mentioned, reply with 'Delhi'. "
            f"Return ONLY the city name in English, nothing else."
        )
        data = {"contents": [{"parts": [{"text": prompt}]}]}
        res = requests.post(url, headers=headers, json=data).json()
        extracted = res['candidates'][0]['content']['parts'][0]['text'].strip()
        return extracted if extracted else "Delhi"
    except Exception:
        return "Delhi"

@app.get("/")
def home():
    return {"status": "Backend server running!"}

@app.post("/api/chat")
def handle_chat(payload: UserQuery):
    try:
        user_msg = payload.message
        
        # Smart City Extraction using AI
        city = extract_city_with_gemini(user_msg)
        weather_data = fetch_weather(city)
        
        if weather_data:
            prompt = (
                f"User Query: '{user_msg}'\n"
                f"Real-time Live Weather Data for {city}: {weather_data}\n\n"
                f"INSTRUCTION:\n"
                f"1. You HAVE real-time live data provided above. Answer the user's question directly using this data.\n"
                f"2. Detect the language/script of the user query (English, Hindi, or Hinglish).\n"
                f"3. Respond ONLY in that EXACT SAME language/style (e.g. if Hinglish, answer in Hinglish)."
            )
        else:
            prompt = (
                f"User Query: '{user_msg}'\n\n"
                f"INSTRUCTION:\n"
                f"1. Explain politely that you couldn't fetch live weather details for '{city}' at this moment.\n"
                f"2. Respond in the exact same language (English, Hindi, or Hinglish)."
            )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={GEMINI_API_KEY}"
        headers = {'Content-Type': 'application/json'}
        data = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        
        response = requests.post(url, headers=headers, json=data)
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
