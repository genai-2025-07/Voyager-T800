import pytest
from app.utils.provide_json_itineraries import ProvideJsonItineraries, DataToCreateItinerary, Role, MessageType
from datetime import datetime
import re

@pytest.fixture
def user_data():
    data = DataToCreateItinerary(
        user_id="user_messag_id",
        session_id="user_session_id",
        started_at="2025-01-01T00:00:00+00:00",
        sender=Role.USER,
        message_type=MessageType.TEXT,
        timezone_offset="+03:00"
    )
    return data

@pytest.fixture
def assistant_data():
    data = DataToCreateItinerary(
        user_id="assistant_messag_id",
        session_id="assistant_session_id",
        started_at="2025-01-01T00:00:00+00:00",
        sender=Role.ASSISTANT,
        message_type=MessageType.TEXT,
        timezone_offset="+03:00"
    )
    return data

@pytest.fixture
def user_prompt():
    return "Generate a 3-day itinerary for a family visiting Barcelona. They enjoy museums and outdoor activities."

@pytest.fixture
def assistant_output():
    return """Certainly! Here's a detailed 3-day itinerary for a family trip to Barcelona,
tailored to your interests in museums, art, outdoor activities, and nature,
with a moderate budget and a family-friendly travel style.


### Day 1: Exploring Gothic Quarter & La Rambla


**Morning:**

- **Start at the Gothic Quarter (Barri Gòtic)**

- **Address:** Begins at La Rambla and stretches to Via Laietana

- **Opening Hours:** Open area, accessible any time

- **Activity:** Explore the narrow medieval streets filled with history. Visit
the Barcelona Cathedral (Catedral de Barcelona), and see the Plaça del Rei, a
historic square.

- **Cost:** Free to explore; Cathedral entrance fee is around €7 per person.

- **Tip:** Wear comfortable shoes for walking on cobblestone streets.


**Afternoon:**

- **Lunch at La Boqueria Market**

- **Address:** La Rambla, 91, 08001 Barcelona

- **Opening Hours:** 8:00 AM - 8:30 PM (Closed Sundays)

- **Activity:** Enjoy local Catalan cuisine at this vibrant market. Try
traditional dishes like tapas or paella.

- **Cost:** Approximately €10-€15 per person for a hearty meal.

- **Visit to Picasso Museum (Museu Picasso)**

- **Address:** Carrer Montcada, 15-23, 08003 Barcelona

- **Opening Hours:** 10:00 AM - 7:00 PM

- **Activity:** Explore the extensive collection of Pablo Picasso's artworks.

- **Cost:** €12 per adult; free for children under 18.

- **Tip:** Buy tickets online in advance to skip the line.


**Evening:**

- **Stroll down La Rambla**

- **Activity:** Experience the lively atmosphere of Barcelona's most famous
street. Watch street performers and visit the Mirador de Colom.

- **Dinner Recommendation:** Try some seafood paella at one of the restaurants
along La Rambla.

- **Cost:** Around €20 per person for dinner.


### Day 2: Montjuïc Day


**Morning:**

- **Montjuïc Cable Car to Montjuïc Castle**

- **Starting Point Address:** Avinguda Miramar, 30, 08038 Barcelona

- **Opening Hours:** 11:00 AM - 6:00 PM

- **Activity:** Enjoy panoramic views of Barcelona as you head to the castle.

- **Cost:** €13.50 for adults; €9.70 for children (round trip).

- **Explore Montjuïc Castle**

- **Cost:** Free entrance.


**Afternoon:**

- **Lunch at a nearby café**

- **Visit to Joan Miró Foundation (Fundació Joan Miró)**

- **Address:** Parc de Montjuïc, s/n, 08038 Barcelona

- **Opening Hours:** 10:00 AM - 6:00 PM

- **Activity:** Discover the works of Joan Miró, a leading figure of
surrealism.

- **Cost:** €13 per adult; free for children under 15.

- **Magic Fountain of Montjuïc (Font màgica de Montjuïc)**

- **Activity:** Watch the spectacular water and light show in the evening.

- **Cost:** Free

- **Tip:** Check show times online as they vary by season.


**Evening:**

- **Dinner at Poble Espanyol**

- **Address:** Av. Francesc Ferrer i Guàrdia, 13, 08038 Barcelona

- **Activity:** Enjoy dinner in this open-air architectural museum that
showcases Spanish architecture. Offers various dining options.

- **Cost:** Around €25 per person.


### Day 3: Park Güell & Sagrada Família


**Morning:**

- **Park Güell**

- **Address:** 08024 Barcelona

- **Opening Hours:** 7:30 AM - 8:30 PM

- **Activity:** Explore this iconic public park designed by Antoni Gaudí.
Marvel at the intricate mosaics and enjoy stunning views of the city.

- **Cost:** €10 per person for entry to the Monumental Zone; free for other
areas.

- **Tip:** Book tickets online in advance to secure your entry time.


**Afternoon:**

- **Lunch at a local restaurant in Gràcia district**

- **Visit to Sagrada Família**

- **Address:** Carrer de Mallorca, 401, 08013 Barcelona

- **Opening Hours:** 9:00 AM - 6:00 PM

- **Activity:** Tour this magnificent basilica, Gaudí's masterpiece still under
construction.

- **Cost:** €26 per adult for basic entry; discounts for students and children.

- **Tip:** Purchase tickets online to choose an entry time and avoid long
lines.


**Evening:**

- **Dinner in Eixample district**

- **Activity:** Conclude your trip with dinner in one of Barcelona's charming
neighborhoods. Try Catalan specialties like 'crema catalana' for dessert.

- **Cost:** Approximately €20-€30 per person.


### General Tips:

- Purchase a T10 transport ticket for multiple rides on public transport to
save money.

- Stay hydrated and wear sunscreen when exploring outdoor attractions.

- Be mindful of pickpockets, especially in crowded areas like La Rambla.


This itinerary blends cultural immersion with outdoor exploration, offering a
comprehensive experience of Barcelona's rich heritage and vibrant lifestyle.
Enjoy your family trip!"""


class TestProvideJsonItineraries:
    def test_provide_json_itineraries(self, user_prompt, user_data, assistant_output, assistant_data):
        provide_json_itineraries = ProvideJsonItineraries()
        print(f"User prompt: {user_prompt}")
        print(f"User data: {user_data}")

        user_json_itinerary = provide_json_itineraries.provide_dict_itinerary(user_prompt, user_data)
        assistant_json_itinerary = provide_json_itineraries.provide_dict_itinerary(assistant_output, assistant_data)
        assert user_json_itinerary is not None
        assert assistant_json_itinerary is not None
        assert user_json_itinerary != assistant_json_itinerary
        
        # Check the top-level structure
        assert user_json_itinerary["user_id"] == user_data.user_id
        assert assistant_json_itinerary["user_id"] == assistant_data.user_id
        assert user_json_itinerary["session_id"] == user_data.session_id
        assert assistant_json_itinerary["session_id"] == assistant_data.session_id
        
        assert user_json_itinerary["messages"][0]["sender"] == "user"
        assert assistant_json_itinerary["messages"][0]["sender"] == "assistant"
        assert user_json_itinerary["messages"][0]["metadata"]["message_type"] == "text"
        assert assistant_json_itinerary["messages"][0]["trip_data"] is not None  # Assistant messages have trip_data
        
        # Check timestamps
        datetime.fromisoformat(user_json_itinerary["started_at"])
        datetime.fromisoformat(assistant_json_itinerary["started_at"])

        exact_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+\d{2}:\d{2}$'
        if not re.match(exact_pattern, user_json_itinerary["started_at"]):
            assert False
        if not re.match(exact_pattern, assistant_json_itinerary["started_at"]):
            assert False