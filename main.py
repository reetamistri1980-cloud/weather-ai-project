import os
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai

app = FastAPI(title="Weather AI API")

# -------------------------
# CORS
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# Gemini API
# -------------------------
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not configured")

client = genai.Client(api_key=API_KEY)

# Primary + fallback models
MODELS = [
    "gemini-3.7-flash",
    "gemini-3.5-flash",
]

# -------------------------
# Request model
# -------------------------
class ChatRequest(BaseModel):
    message: str


# -------------------------
# Health check
# -------------------------
@app.get("/")
def home():
    return {
        "status": "ok",
        "message": "Weather AI API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


# -------------------------
# Gemini function
# -------------------------
async def ask_gemini(message: str):

    last_error = None

    for model in MODELS:

        for attempt in range(3):

            try:
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=model,
                    contents=message
                )

                text = response.text

                if text:
                    return {
                        "reply": text,
                        "model": model
                    }

                last_error = "Gemini returned an empty response"

            except Exception as e:

                last_error = str(e)

                error_text = str(e).lower()

                # Retry temporary errors
                temporary_error = any(
                    word in error_text
                    for word in [
                        "503",
                        "unavailable",
                        "overloaded",
                        "temporarily",
                        "high demand",
                        "429",
                        "rate limit"
                    ]
                )

                if temporary_error and attempt < 2:
                    await asyncio.sleep(2 * (attempt + 1))
                    continue

                break

    raise RuntimeError(last_error)


# -------------------------
# Chat endpoint
# -------------------------
@app.post("/api/chat")
async def chat(request: ChatRequest):

    message = request.message.strip()

    if not message:
        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty"
        )

    try:

        result = await ask_gemini(message)

        return {
            "status": "success",
            "message": result["reply"],
            "model": result["model"]
        }

    except Exception as e:

        print("Gemini Error:", e)

        raise HTTPException(
            status_code=503,
            detail={
                "status": "failed",
                "message": "AI service is temporarily unavailable. Please try again."
            }
        )
