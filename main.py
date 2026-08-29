import os
import re
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

def extract_city(user_msg: str) -> str:
    stop_words = {
        "what", "is", "the", "weather", "wheather", "in", "right", "now", "today", "how", 
        "kaisa", "kaise", "kesa", "kese", "hai", "mausam", "mosam", "batao", "btao", 
        "ka", "ki", "ko", "temperature", "temp", "aaj", "kya", "kaha", "degree", 
        "tell", "me", "about", "mai", "me", "kharab", "achha", "baaris", "barish", 
        "dhop", "garmi", "sardi", "thand", "rain", "din", "hal", "haal", "please", "pls"
    }
    
    words = re.findall(r'\b[a-zA-Z]+\b', user_msg)
    for word in words:
        if len(word) > 2 and word.lower() not in stop_words:
            return word
            
    return "Delhi"

def fetch_weather(city: str):
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

@app.get("/")
def home():
    return {"status": "Backend server running!"}

@app.post("/api/chat")
def handle_chat(payload: UserQuery):
    try:
        user_msg = payload.message
        city = extract_city(user_msg)
        weather_data = fetch_weather(city)
        
        if weather_data:
            prompt = (
                f"User Asked: '{user_msg}'\n"
                f"LIVE WEATHER DATA FOR {city}: {weather_data}\n\n"
                f"INSTRUCTIONS:\n"
                f"1. Summarize the live weather details accurately based on the provided data.\n"
                f"2. The user might use broken English, simple phrases, or basic mixed inputs. Understand their intent and respond in simple, clear, and easy-to-understand English.\n"
                f"3. Do NOT say you lack real-time data."
            )
        else:
            prompt = (
                f"User Asked: '{user_msg}'\n\n"
                f"INSTRUCTIONS:\n"
                f"1. Inform the user in simple English that weather details for '{city}' could not be found right now.\n"
                f"2. Keep the explanation clear and easy to read."
            )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={GEMINI_API_KEY}"
        headers = {'Content-Type': 'application/json'}
        data = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        
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
