# Kumon AI Receptionist

AI-powered WhatsApp receptionist for Kumon centers that can answer questions, suggest schedules, and book appointments.

## Features

- 🤖 AI-powered conversation handling
- 📅 Google Calendar integration for scheduling
- 📋 Lead collection and management
- 💬 WhatsApp Business API integration
- 🔍 RAG-powered question answering
- 📊 Google Sheets integration for data storage

## Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in your credentials
4. Run the application: `uvicorn app.main:app --reload`

## Environment Variables

See `.env.example` for all required environment variables.

## Development

The project structure follows a clean architecture pattern with separate layers for:

- API endpoints (`app/api/`)
- Business logic (`app/services/`)
- External integrations (`app/clients/`)
- Data models (`app/models/`)
- Configuration (`app/core/`)

## TODO

- [ ] Implement WhatsApp webhook handling
- [ ] Add Google Calendar integration
- [ ] Implement RAG engine with Qdrant
- [ ] Add proper date/time parsing
- [ ] Implement database migrations
- [ ] Add comprehensive testing
