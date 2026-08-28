# Weather AI - Intelligent Weather Assistant

An AI-powered weather forecasting and advisory backend built with FastAPI, OpenWeather API, and Gemini AI.

## Features
- **Live Weather Integration**: Fetches real-time temperature, humidity, wind speed, and conditions.
- **AI Summary**: Generates conversational natural-language answers using Gemini AI.
- **Structured Output**: Provides structured JSON data (`weather_card`) for front-end visual widgets.

## API Specification

### Endpoint: `POST /api/chat`

**Request Body:**
```json
{
  "message": "What is the weather in Delhi right now?"
}
