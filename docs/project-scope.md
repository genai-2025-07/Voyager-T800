# Voyager T800 – Project Scope

A generative AI-powered multimodal travel planning assistant developed during a 12-week Data Science internship.

---

## 1. Project Vision

**Goal**:  
To build an AI assistant that generates personalized, fact-grounded travel itineraries using both **text** and **image** inputs, powered by LLMs and enhanced with retrieval-augmented generation (RAG), agentic reasoning, and vision-based tools.

---

## 2. Target Users

The primary users of the application:

- [ ] Families planning vacations
- [ ] Budget-conscious solo travelers
- [ ] Photographers / travel bloggers
- [ ] First-time city explorers
- [ ] Adventure seekers / active travelers
- [ ] International travelers
- [ ] Couples planning romantic getaways
- [ ] Locals exploring nearby destinations
- [ ] Students on cultural trips
- [ ] Other: `__________`

---

## 3. Key Use Case Scenarios

| **Scenario**                                                | **Input Type**   | **Expected Output**                                                                 |
| ----------------------------------------------------------- | ---------------- | ----------------------------------------------------------------------------------- |
| “Plan a 5-day trip to Paris for a foodie couple”            | Text             | Day-by-day itinerary with food stops                                                |
| "I want to spend a week exploring Kyiv and Lviv"            | Text             | Day-by-day itinerary with main attractions and travel route between cities included |
| Upload a beach photo + "I want something similar in Europe" | Image + Text     | Destination guess + itinerary with beach options                                    |
| “Make Day 2 more relaxing”                                  | Follow-up Prompt | Adjusted itinerary                                                                  |
| Upload a blurry or unrelated photo + "I want to go here"    | Image + Text     | Generic popular destinations itinerary or last saved location itinerary             |
| Empty or nonsensical input (e.g., “asdfghjkl”)              | Text             | Default help itinerary with sample queries                                          |
| “Make Day 5 more exciting” when itinerary only has 3 days   | Follow-up Prompt | Revised 3-day itinerary with more activities on Day 3                               |

---

## 4. Core Features (MVP Milestones)

- [ ] Text-to-itinerary generation with LLM
- [ ] Prompt templates (simple & structured)
- [ ] Basic Streamlit UI (text input + output)
- [ ] LangChain chain for itinerary generation
- [ ] Knowledge base (3 cities max)
- [ ] Basic RAG with manual retrieval
- [ ] Multimodal input (image upload)
- [ ] Vision model integration (tags/captions)
- [ ] Agent prototype for follow-ups or tools
- [ ] JSON-structured output
- [ ] Conversation History

---

## 5. Tech Stack

- **Frontend**: Streamlit or React
- **Backend**: FastAPI
- **LLMs**: OpenAI GPT, Claude via AWS Bedrock
- **LangChain / LangGraph** for orchestration
- **Vision Models**: AWS Rekognition / CLIP
- **Vector DB**: FAISS / Chroma
- **Prompt Injection + RAG**
- **Dev Tools**: Cursor IDE, Docker, GitHub Classroom

---

## 6. Cities Covered in Knowledge Base

- [ ] Kyiv
- [ ] Lviv
- [ ] Add more later as part of scale-up

---

## 7. External APIs / Tools (Proposed)

- UZ API (Ukrzaliznytsia train search)
- OpenStreetMap (route + map rendering)
- Tavily / SerpAPI / Eventbrite API for event search
- Weather API (OpenWeather or Tomorrow.io)
- Shelter location (for Ukraine-specific safety)
- Text-to-speech (e.g., gTTS, Amazon Polly)
- Public transport schedules (Google Maps API)
- Travel plan transfer to calendar (Google Calendar API)
- Reviews and working hours of places (Google Places API / Yelp API)
- User Authentication (Auth0 / Firebase Auth)

---

##  8. Stretch Goals

- [ ] Expansion to 5 additional cities
- [ ] Downloadable PDF of itinerary
- [ ] Multilingual support
- [ ] Image-based destination guessing
- [ ] Map display of daily routes
- [ ] Auto-updated knowledge base scripts
- [ ] Telegram bot version
- [ ] Itinerary rating system
- [ ] Text-to-speech output for itineraries
- [ ] Weather-aware itinerary generation
- [ ] Real-time retrieval of nearest bomb shelters
- [ ] Transport availability search (trains, buses, etc.)
- [ ] Voice-based excursion generation
- [ ] Display ratings and reviews for located points of interest
- [ ] User profile system to save preferences (travel type like Slow Traveler”, “Food Explorer”, “Night Owl”)  

---

##  9. Weekly Milestone Alignment

| **Week** | **Goal** |
|----------|----------|
| 1 | Prompt engineering, project outline |
| 2 | LLM prototype, UI draft |
| 3 | LangChain chain, itinerary logic |
| 4 | Vector DB + early RAG |
| 5–7 | Vision integration, agents, follow-up UX |
| 8–10 | Deployment, evaluation, expansion |
| 11–12 | Final polish and demo prep |

---

## 10. Evaluation Criteria

- Accuracy and realism of itineraries
- Personalization based on inputs: user goals, budget, preferences
- UI usability
- Multimodal support
- Retrieval and agent reasoning
- Response clarity and coherence
- Performance / latency
- Team collaboration and code quality
- Ethical and safety awareness
- Scalability and extensibility
- System robustness and error handling

---

## 11. Team Notes

- Repo: [Voyager-T800](https://github.com/genai-2025-07/Voyager-T800)
- Demo Days: Weeks 4, 7, 10, and 12
- Mentor: @DmyMi  @mehalyna 
- Communication: Discord [`#team-voyager`](https://discord.gg/8yh7dStW)

---

*This document is a living artifact. Update as the project evolves.*
