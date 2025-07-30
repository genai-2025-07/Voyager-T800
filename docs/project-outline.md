# Project Outline

**Target Users**  
- Independent travelers and tourists planning multi‑city trips in Ukraine (initial focus: Kyiv & Lviv)  
- History, culture and food enthusiasts seeking personalized, image‑augmented journey plans  

**Core Features**  
- Conversational Interface: Text and image input for travel preferences
- City Selection: Initial focus on Kyiv and Lviv with scalability for additional cities
- Intelligent Itinerary Generation: AI-powered journey plans based on user interests, budget, and duration
- Iterative Refinement: Context-aware adjustments to generated itineraries
- Conversation History: Access to past interactions and generated itineraries
- Multi-modal Input: Support for images (e.g., landmarks) to enhance context

**Required Data / APIs**  
- Static attractions data: MediaWiki, Google Places
- Restaurant/Dining: Google Places
- Transportation schedules: Google Maps API (train/bus routes)  
- Events: Eventbrite, Facebook Events, local platforms 
- Image Recognition: AWS Rekognition, CLIP for landmark identification
- Semantic search & vector store: FAISS, Chroma or Pinecone  

**Sample Prompt / Response**  
- **Input:**  
  “I want to spend 5 days in Ukraine, visiting Kyiv and Lviv. I love history and food. Traveling in June with a moderate budget.”  
  *(Optionally upload an image of St. Sophia Cathedral)*  
- **Output:**  
  - **Day 1 – Kyiv:** Morning at **St. Sophia Cathedral** (UNESCO site)  
  - **Day 2 – Kyiv:** Explore **Kyiv Pechersk Lavra** catacombs  
  - **Day 3 – Train to Lviv:** Scenic intercity train ride.

**Initial Component Plan**  
- **Frontend:** Landing page with city selector, conversational chat interface, itinerary display component, history sidebar 
- **Backend:** FastAPI endpoints for chat, itinerary generation, session management  
- **Data Layer:** Vector database with embeddings for attractions, restaurants, events 
- **AI Pipeline:** LangChain/LangGraph orchestration with GPT/Claude integration
- **Image Processing:** Vision API integration for landmark recognition



