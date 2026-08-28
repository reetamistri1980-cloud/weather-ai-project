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

@app.get("/")
def home():
    return {"status": "Backend server running!"}

@app.post("/api/chat")
def handle_chat(payload: UserQuery):
    try:
        user_msg = payload.message
        
        city = "Delhi"
        for word in user_msg.split():
            if word.isalpha() and len(word) > 2 and word.lower() not in ["what", "is", "the", "weather", "in", "right", "now", "today", "how"]:
                city = word
                break
                
        weather_data = fetch_weather(city)
        
        if weather_data:
            prompt = f"User asked: '{user_msg}'. Live Weather Data for {city}: {weather_data}. Summarize this accurately in a natural friendly AI tone."
        else:
            prompt = user_msg

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