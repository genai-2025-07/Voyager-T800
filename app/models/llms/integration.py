#!/usr/bin/env python3
import os
import time
import logging
from typing import Dict, Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('itinerary_generation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ItineraryGenerator:  
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable or pass it to constructor.")
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4-turbo-preview"
        self.max_tokens = 2000
        self.temperature = 0.7
        
        logger.info("ItineraryGenerator initialized successfully")
    
    '''
    This is the context that ChatGPT needs to provide better responses. In our case, it replaces memory.
    '''
    def _create_system_prompt(self) -> str:
        return """You are Voyager T800, an expert travel planning AI assistant specializing in creating detailed, personalized itineraries. 

Your expertise includes:
- Deep knowledge of global destinations, attractions, and cultural experiences
- Understanding of different travel styles (budget, luxury, adventure, cultural, etc.)
- Seasonal considerations and local events
- Practical travel logistics and timing
- Cultural sensitivity and local customs

When creating itineraries, you should:
1. Structure each day with clear morning, afternoon, and evening activities
2. Include specific landmark names, addresses, and opening hours when relevant
3. Consider travel time between locations
4. Suggest local cuisine and dining experiences
5. Include cultural and historical context
6. Provide practical tips (best times to visit, dress codes, etc.)
7. Consider the traveler's interests, budget, and travel style
8. Include transportation options between cities when applicable

Format your response as a structured itinerary with:
- Day-by-day breakdown
- Specific times and locations
- Brief descriptions of each activity
- Cultural/historical context
- Practical tips and recommendations
- Estimated costs for budget-conscious travelers

Be engaging, informative, and practical while maintaining a warm, helpful tone."""










    '''
    In this code, unfortunately, I rudely and shamelessly throw the necessary information into the prompt and that's it. 
    No complex implementation. If something more complex or interesting is needed, I can rewrite it.
    '''
    def _create_user_prompt(self, destination: str, duration: str, interests: str, 
                           budget: str, travel_style: str, additional_context: str = "") -> str:
        prompt = f"""Please create a detailed {duration} itinerary for a trip to {destination}.

Traveler Profile:
- Interests: {interests}
- Budget: {budget}
- Travel Style: {travel_style}

{f"Additional Context: {additional_context}" if additional_context else ""}

Please provide:
1. A day-by-day itinerary with specific activities
2. Cultural and historical context for major attractions
3. Local cuisine recommendations
4. Practical travel tips
5. Estimated costs for budget planning
6. Best times to visit each location
7. Transportation options between activities

Make the itinerary engaging, informative, and tailored to the traveler's preferences."""
        
        return prompt

    def generate_itinerary(self, prompt_text: str) -> str:
        
        start_time = time.time()
        
        try:
            logger.info("Starting itinerary generation")
            
            system_prompt = self._create_system_prompt()
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt_text}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                top_p=0.9,
                frequency_penalty=0.1,
                presence_penalty=0.1
            )
            
            itinerary = response.choices[0].message.content.strip()
            
            end_time = time.time()
            response_time = end_time - start_time
            tokens_used = response.usage.total_tokens
            
            logger.info(f"Itinerary generated successfully in {response_time:.2f}s using {tokens_used} tokens")
            
            return itinerary
            
        except Exception as e:
            if "authentication" in str(e).lower() or "api_key" in str(e).lower():
                error_msg = "Authentication failed. Please check your OpenAI API key."
                logger.error(error_msg)
                raise ValueError(error_msg)
            elif "rate limit" in str(e).lower():
                error_msg = "Rate limit exceeded. Please try again later."
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            else:
                error_msg = f"OpenAI API error: {str(e)}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
        except Exception as e:
            error_msg = f"Unexpected error during itinerary generation: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

    def get_days(self, user_input_lower: str) -> str:
        import re
        
        day_pattern = r'(\d+)\s*-?\s*days?'
        day_match = re.search(day_pattern, user_input_lower)
        
        if day_match:
            days = int(day_match.group(1))
            return f"{days} days"
        
        written_numbers = {
            'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
            'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
            'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15
        }
        
        for word, number in written_numbers.items():
            if f"{word} days" in user_input_lower or f"{word} day" in user_input_lower:
                return f"{number} days"
        
        week_pattern = r'(\d+)\s*weeks?'
        week_match = re.search(week_pattern, user_input_lower)
        
        if week_match:
            weeks = int(week_match.group(1))
            days = weeks * 7
            return f"{days} days"
        
        written_weeks = {
            'one week': 7, 'two weeks': 14, 'three weeks': 21, 'four weeks': 28
        }
        
        for week_phrase, days in written_weeks.items():
            if week_phrase in user_input_lower:
                return f"{days} days"
        
        '''I think it's better to return 3 days than to show an error to the user 
        in this situation, because the user might not even know 
        how much time they want to spend on the trip.'''
        return "3 days"

    def get_destinations(self, user_input_lower: str) -> str:
        ukrainian_destinations = {
            'kyiv': 'Kyiv',
            'kiev': 'Kyiv',  # Alternative spelling
            'lviv': 'Lviv',
            'lwow': 'Lviv',  # Alternative spelling
            'kharkiv': 'Kharkiv',
            'kharkov': 'Kharkiv',  # Alternative spelling
            'odesa': 'Odesa',
            'odessa': 'Odesa',  # Alternative spelling
            'dnipro': 'Dnipro',
            'dnepr': 'Dnipro',  # Alternative spelling
            'donetsk': 'Donetsk',
            'zaporizhzhia': 'Zaporizhzhia',
            'zaporozhye': 'Zaporizhzhia',  # Alternative spelling
            'luhansk': 'Luhansk',
            'lugansk': 'Luhansk',  # Alternative spelling
            'mykolaiv': 'Mykolaiv',
            'nikolaev': 'Mykolaiv',  # Alternative spelling
            'mariupol': 'Mariupol',
            'kherson': 'Kherson',
            'poltava': 'Poltava',
            'chernihiv': 'Chernihiv',
            'chernigov': 'Chernihiv',  # Alternative spelling
            'sumy': 'Sumy',
            'vinnytsia': 'Vinnytsia',
            'vinnytsya': 'Vinnytsia',  # Alternative spelling
            'khmelnytskyi': 'Khmelnytskyi',
            'khmelnitsky': 'Khmelnytskyi',  # Alternative spelling
            'rivne': 'Rivne',
            'rovno': 'Rivne',  # Alternative spelling
            'ternopil': 'Ternopil',
            'lutsk': 'Lutsk',
            'uzhhorod': 'Uzhhorod',
            'uzhgorod': 'Uzhhorod',  # Alternative spelling
            'ivano-frankivsk': 'Ivano-Frankivsk',
            'stanislav': 'Ivano-Frankivsk',  # Alternative spelling
            'chernivtsi': 'Chernivtsi',
            'chernovtsy': 'Chernivtsi',  # Alternative spelling
            
            # Regions and areas
            'ukraine': 'Ukraine',
            'carpathians': 'Carpathian Mountains',
            'carpathian': 'Carpathian Mountains',
            'crimea': 'Crimea',
            'bukovina': 'Bukovina',
            'galicia': 'Galicia',
            'volhynia': 'Volhynia',
            'podolia': 'Podolia',
            'sloboda': 'Sloboda Ukraine',
            'zaporizhian': 'Zaporizhian Sich',
            'cossack': 'Cossack Lands'
        }
        
        found_destinations = []
        
        for dest_key, dest_name in ukrainian_destinations.items():
            if dest_key in user_input_lower:
                if dest_name not in found_destinations:
                    found_destinations.append(dest_name)
        
        if len(found_destinations) > 1:
            if 'Ukraine' in found_destinations and len(found_destinations) > 1:
                found_destinations.remove('Ukraine')
            
            if len(found_destinations) == 2:
                return f"{found_destinations[0]} and {found_destinations[1]}"
            else:
                return f"{', '.join(found_destinations[:-1])}, and {found_destinations[-1]}"
        
        elif len(found_destinations) == 1:
            return found_destinations[0]
        
        else:
            return "Ukraine"

    def parse_travel_request(self, user_input: str) -> Dict[str, str]:
        
        preferences = {
            'destination': 'Unknown',
            'duration': '3 days',
            'interests': 'General sightseeing',
            'budget': 'Moderate',
            'travel_style': 'Cultural',
            'additional_context': ''
        }
        
        user_input_lower = user_input.lower()
        
        preferences['duration'] = self.get_days(user_input_lower)
        
        preferences['destination'] = self.get_destinations(user_input_lower)
                
        # Some context
        if 'history' in user_input_lower:
            preferences['interests'] = 'History and cultural heritage'
        if 'food' in user_input_lower or 'cuisine' in user_input_lower:
            preferences['interests'] = 'Food and local cuisine'
        if 'museums' in user_input_lower:
            preferences['interests'] = 'Museums and art'
        if 'outdoor' in user_input_lower or 'nature' in user_input_lower:
            preferences['interests'] = 'Outdoor activities and nature'
        
        # It would be better to give LLM information about the budget, 
        if 'budget' in user_input_lower or 'cheap' in user_input_lower:
            preferences['budget'] = 'Budget-friendly'
        elif 'luxury' in user_input_lower or 'high-end' in user_input_lower:
            preferences['budget'] = 'Luxury'
        else:
            preferences['budget'] = 'Moderate'
        
        # More context
        if 'family' in user_input_lower:
            preferences['travel_style'] = 'Family-friendly'
        elif 'adventure' in user_input_lower:
            preferences['travel_style'] = 'Adventure'
        elif 'cultural' in user_input_lower:
            preferences['travel_style'] = 'Cultural'
        
        # The other text that the user wrote
        preferences['additional_context'] = user_input
        
        return preferences

    def generate_enhanced_itinerary(self, user_input: str) -> str:
        
        preferences = self.parse_travel_request(user_input)
        
        detailed_prompt = self._create_user_prompt(
            destination=preferences['destination'],
            duration=preferences['duration'],
            interests=preferences['interests'],
            budget=preferences['budget'],
            travel_style=preferences['travel_style'],
            additional_context=preferences['additional_context']
        )
        
        logger.info(f"Generating itinerary for {preferences['destination']} ({preferences['duration']})")
        
        return self.generate_itinerary(detailed_prompt)

def main():
    try:
        generator = ItineraryGenerator()
        
        example_input = "I want to spend 5 days in Ukraine, visiting Kyiv and Lviv. I love history and food. Traveling in June with a moderate budget."
        
        itinerary = generator.generate_enhanced_itinerary(example_input)
        
        print("\n📋 Generated Itinerary:")
        print("=" * 30)
        print(itinerary)
        print("\n" + "=" * 30)
        print("🎯 Interactive Mode - Enter your travel request (or 'quit' to exit):")
        
        while True:
            user_input = input("\n🌍 Your travel request: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("👋 Thank you for using Voyager T800!")
                break
            
            if not user_input:
                print("❌ Please enter a valid travel request.")
                continue
            
            try:
                print("\n🔄 Generating your personalized itinerary...")
                itinerary = generator.generate_enhanced_itinerary(user_input)
                
                print("\n📋 Your Personalized Itinerary:")
                print("=" * 50)
                print(itinerary)
                print("=" * 50)
                
            except Exception as e:
                print(f"❌ Error generating itinerary: {str(e)}")
                logger.error(f"Error in interactive mode: {str(e)}")
    
    except Exception as e:
        print(f"❌ Failed to initialize Voyager T800: {str(e)}")
        logger.error(f"Initialization error: {str(e)}")

if __name__ == "__main__":
    main()
