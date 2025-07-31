# Ukraine Travel Assistant - Project Plan

**Last updated:** 2025-07-31 | **Version:** 0.2 (Outline Draft)

## Project Summary
AI-powered assistant for personalized and image-aware travel planning across Ukraine, featuring conversational interfaces and intelligent itinerary generation.

## Target Users
- Independent travelers and tourists planning multi-city trips in Ukraine (initial focus: Kyiv & Lviv)
- Ukrainian users and diaspora, as well as foreign guests seeking authentic local experiences
- History, culture and food enthusiasts seeking personalized, image-augmented journey plans

## Core Features
- **Conversational Interface:** Chat-based UI using Streamlit or React with text and image input for travel preferences
- **City Selection:** Initial focus on Kyiv and Lviv with scalability for additional cities
- **Intelligent Itinerary Generation:** AI-powered journey plans based on user interests, budget, and duration
- **Iterative Refinement:** Context-aware adjustments to generated itineraries using LangChain memory/conversation context for follow-up prompts
- **Conversation History:** Access to past interactions and generated itineraries
- **Multi-modal Input:** Support for images (e.g., landmarks) to enhance context using AWS Rekognition or CLIP for landmark identification

## Required Data / APIs
- **Static attractions data:** MediaWiki, Google Places (with local static JSON fallback for bootstrapping)
- **Restaurant/Dining:** Google Places
- **Transportation schedules:** Google Maps API (train/bus routes)
- **Events:** Eventbrite, Tavily Search, Google Custom Search (Facebook Events API access limited)
- **Image Recognition:** AWS Rekognition, CLIP for landmark identification - extracting landmark names, scene tags, and inferred interests (e.g., food, nature)
- **Semantic search & vector store:** FAISS, Chroma or Pinecone

## Sample Prompt / Response
**Input:**
"I want to spend 5 days in Ukraine, visiting Kyiv and Lviv. I love history and food. Traveling in June with a moderate budget."
*(Optionally upload an image of St. Sophia Cathedral)*

**Output:**
- **Day 1 – Kyiv:** Morning at **St. Sophia Cathedral** (UNESCO site)
- **Day 2 – Kyiv:** Explore **Kyiv Pechersk Lavra** catacombs
- **Day 3 – Train to Lviv:** Scenic intercity train ride

**Follow-up Example:**
*User:* "Make Day 2 more relaxing"
*Assistant:* Adjusts itinerary to include fewer walking-intensive activities and adds café stops.

## Initial Component Plan
- **Frontend:** Landing page with city selector, conversational chat interface using Streamlit or React, itinerary display component, history sidebar
- **Backend:** FastAPI endpoints for chat, itinerary generation, session management
- **Data Layer:** Vector database with embeddings for attractions, restaurants, events
- **AI Pipeline:** LangChain/LangGraph orchestration with Claude integration, including prompt templates and tool use (RAG, memory, agents) as internal pipeline layers
- **Image Processing:** Vision API integration for landmark recognition

## Stretch Goals
- Google Maps APIs for Route Planning
- Telegram bot integration
- Live event lookup via Tavily
- Travel safety layer (e.g., shelter API)
- Expansion to 5 additional cities: Bratislava, Prague, Warsaw, Berlin, Krakow

## Security & Privacy Notice
- No personal data is stored
- Images processed locally or via secure cloud API