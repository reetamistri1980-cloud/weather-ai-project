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
    ignore_list = {
        "what", "is", "the", "weather", "wheather", "in", "right", "now", "today", "how", 
        "kaisa", "kaise", "kesa", "kese", "hai", "mausam", "mosam", "batao", "btao", 
        "ka", "ki", "ko", "temperature", "temp", "aaj", "kya", "kaha", "degree", 
        "tell", "me", "about", "mai", "me", "kharab", "achha", "baaris", "barish", 
        "dhop", "garmi", "sardi", "thand", "rain", "din", "hal", "haal", "please", "pls",
        "like", "give", "show", "can", "you", "city", "of", "for"
    }
    
    cleaned_msg = re.sub(r'[^\w\s]', '', user_msg)
    words = cleaned_msg.split()
    
    for word in words:
        if word.lower() not in ignore_list and len(word) > 2:
            return word
            
    return "Delhi"

def fetch_weather(city: str):
    if not OPENWEATHER_API_KEY:
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

@app.get("/")
def home():
    return {"status": "Backend server running!"}

@app.post("/api/chat")
def handle_chat(payload: UserQuery):
    try:
        user_msg = payload.message
        city = extract_city(user_msg)
        weather_data = fetch_weather(city)
        
        # If extracted city fails on OpenWeather, default to Delhi
        if not weather_data and city != "Delhi":
            city = "Delhi"
            weather_data = fetch_weather("Delhi")

        # FIX: Agar weather data mil gaya, toh AI key rate-limit skip karke direct 100% success response do!
        if weather_data:
            reply_text = f"The current temperature in {weather_data['city']} is {weather_data['temperature']}°C with {weather_data['condition']}. Humidity is {weather_data['humidity']}% and wind speed is {weather_data['wind_speed']} m/s."
            return {
                "reply": reply_text,
                "weather_card": weather_data,
                "status": "success"
            }
        
        # Non-weather questions fallback to Gemini
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
        headers = {'Content-Type': 'application/json'}
        prompt = f"Answer this question in simple English: '{user_msg}'"
        data = {"contents": [{"parts": [{"text": prompt}]}]}
        
        response = requests.post(url, headers=headers, json=data, timeout=10)
        res_data = response.json()
        
        if response.status_code == 200:
            reply_text = res_data['candidates'][0]['content']['parts'][0]['text']
            return {
                "reply": reply_text,
                "weather_card": None,
                "status": "success"
            }
        else:
            return {
                "reply": "I could not fetch an answer right now. Please try again in a few moments.",
                "weather_card": None,
                "status": "failed",
                "error_detail": res_data
            }

    except Exception as e:
        return {"reply": f"Error occurred: {str(e)}", "weather_card": None, "status": "failed"}
