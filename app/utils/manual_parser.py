import json
import re
from typing import List, Optional
from models.llms.itinerary import ItineraryDay, TravelItinerary
import logging
logger = logging.getLogger(__name__)

class ManualItineraryParser:
    """Manual regex-based parser for travel itineraries with debug logging"""
    
    def __init__(self, debug=False):
        self.debug = debug
        
        self.day_patterns = [
            r'день\s*(\d+)',                           # "День 1"
            r'day\s*(\d+)',                            # "Day 1"
            r'(\d+)[-\s]*й?\s*день',                   # "1-й день", "1 день"
            r'(\d+)(?:st|nd|rd|th)\s*day',             # "1st day", "2nd day"
            r'^(\d+)\.?\s*(?=\w)',                     # "1. Activity" (number at line start)
            r'перший\s*день',                          # "Перший день"
            r'другий\s*день',                          # "Другий день"
            r'третій\s*день',                          # "Третій день"
            r'останній\s*день',                        # "Останній день"
        ]
        
        self.day_word_map = {
            'перший': 1, 'другий': 2, 'третій': 3, 'четвертий': 4, 'п\'ятий': 5,
            'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
            'останній': 999, 'last': 999
        }
        
        self.location_patterns = [
            r'(?:поїздка|подорож)\s+(?:в|до|у)\s+([А-ЯІЇЄа-яіїєA-Za-z\s-]+?)(?:\s+на|\s*[,\.\n]|$)',
            r'(?:поїхати|їхати|летіти|відвідати)\s+(?:в|до|у)\s+([А-ЯІЇЄа-яіїєA-Za-z\s-]+?)(?:\s+на|\s*[,\.\n]|$)',
            r'(?:trip|travel|visit|go)\s+to\s+([A-Za-z\s-]+?)(?:\s+for|\s*[,\.\n]|$)',
            r'in\s+([A-Z][A-Za-z\s-]+?)(?:\s+for|\s*[,\.\n]|$)',
            r'([А-ЯA-Z][А-ЯІЇЄа-яіїєA-Za-z\s-]+?)(?=\s*[-–:]\s*(?:день|day|прибуття|arrival))',
        ]
        
        self.activity_patterns = [
            r'^\s*[-•*]\s*(.+)$',                      # "- Activity", "• Activity"
            r'^\s*\d+\.\s*(.+)$',                      # "1. Activity"
            r'^\s*\d+\)\s*(.+)$',                      # "1) Activity"
            r'(?:відвідування|відвідати)\s+(.+)$',     # "відвідування музею"
            r'(?:visit|visiting)\s+(.+)$',             # "visit museum"
            r'(?:прогулянка|прогулятися)\s+(.+)$',     # "прогулянка по парку"
            r'(?:walk|walking)\s+(.+)$',               # "walk in park"
            r'(?:вечеря|обід|сніданок)\s+(.+)$',       # "вечеря в ресторані"
            r'(?:dinner|lunch|breakfast)\s+(.+)$',     # "dinner at restaurant"
            r'(?:екскурсія|тур)\s+(.+)$',              # "екскурсія по місту"
            r'(?:tour|excursion)\s+(.+)$',             # "tour of city"
        ]
        
        self.transport_keywords = {
            'driving': ['машина', 'автомобіль', 'car', 'drive', 'driving'],
            'walking': ['пішки', 'ходьба', 'walk', 'walking', 'on foot'],
            'cycling': ['велосипед', 'bike', 'bicycle', 'cycling', 'велосипедна'],
            'public_transit': ['транспорт', 'автобус', 'метро', 'bus', 'metro', 'train', 'tram'],
            'flight': ['літак', 'авіа', 'flight', 'plane', 'airplane'],
        }
        
        self.noise_words = {
            'день', 'day', 'активності', 'activities', 'план', 'plan', 'маршрут', 'itinerary',
            'розклад', 'schedule', 'програма', 'program', 'поїздка', 'trip', 'подорож', 'travel',
            'прибуття', 'arrival', 'від\'їзд', 'departure', 'ввечері', 'evening', 'потім', 'then'
        }

    def _log(self, message):
        """Debug logging helper"""
        if self.debug:
            print(f"DEBUG: {message}")
    
    def parse_itinerary_text(self, text: str) -> TravelItinerary:
        """Parse travel itinerary from free-form text"""
        self._log("=== STARTING MANUAL PARSING ===")
        self._log(f"Original text length: {len(text)} chars")
        
        normalized_text = self._normalize_text(text)
        self._log(f"Normalized text:\n{repr(normalized_text)}")
        
        lines = [line.strip() for line in normalized_text.split('\n') if line.strip()]
        self._log(f"Split into {len(lines)} lines:")
        for i, line in enumerate(lines):
            self._log(f"  Line {i}: '{line}'")
        
        destination = self._extract_destination(normalized_text)
        self._log(f"Extracted destination: {destination}")
        
        transportation = self._extract_transportation(normalized_text)
        self._log(f"Extracted transportation: {transportation}")
        
        days_data = self._parse_days_and_activities(lines)
        self._log(f"Parsed days data: {days_data}")
        
        itinerary_days = self._build_itinerary_days(days_data, destination)
        self._log(f"Built {len(itinerary_days)} itinerary days")
        
        if not itinerary_days:
            self._log("No structured days found, trying fallback")
            activities = self._extract_all_activities(lines)
            self._log(f"Fallback activities: {activities}")
            
            if activities:
                itinerary_days = [ItineraryDay(
                    day=1,
                    location=destination or "Unknown",
                    activities=activities
                )]
            else:
                itinerary_days = [ItineraryDay(
                    day=1,
                    location=destination or "Unknown",
                    activities=["Plan your activities"]
                )]
        
        result = TravelItinerary(
            destination=destination or "Unknown",
            duration_days=len(itinerary_days),
            transportation=transportation,
            itinerary=itinerary_days
        )
        
        self._log("=== PARSING COMPLETE ===")
        return result
    
  
    def _normalize_text(self, text: str) -> str:
        """Clean and normalize input text while preserving line structure"""
        self._log(f"Normalizing text: {repr(text[:100])}...")
        
        lines = text.split('\n')
        normalized_lines = []
        
        for line in lines:
            line = re.sub(r'[ \t]+', ' ', line)
            
            line = re.sub(r'[^\w\s\-\.\,\:\;\!\?\(\)№àáâãäåæçèéêëìíîïñòóôõöøùúûüýÿ]', ' ', line)
            
            line = line.replace('—', '-').replace('–', '-')
            
            line = line.strip()
            if line:
                normalized_lines.append(line)
        
        normalized = '\n'.join(normalized_lines)
        self._log(f"Normalized result: {repr(normalized[:100])}...")
        return normalized
    
    def _extract_destination(self, text: str) -> Optional[str]:
        """Extract main destination from text"""
        self._log("Extracting destination...")
        
        for i, pattern in enumerate(self.location_patterns):
            self._log(f"  Trying pattern {i+1}: {pattern}")
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            self._log(f"    Matches: {matches}")
            
            if matches:
                destination = matches[0].strip()
                destination = re.sub(r'\s*на\s*\d+\s*дні?.*$', '', destination, flags=re.IGNORECASE)
                destination = re.sub(r'\s*for\s*\d+\s*days?.*$', '', destination, flags=re.IGNORECASE)
                
                self._log(f"    Cleaned destination: '{destination}'")
                
                if len(destination) > 2 and destination.lower() not in self.noise_words:
                    self._log(f"  Found valid destination: {destination}")
                    return destination
        
        self._log("  No destination found")
        return None
    
    def _extract_transportation(self, text: str) -> str:
        """Determine primary transportation method"""
        self._log("Extracting transportation...")
        text_lower = text.lower()
        
        transport_scores = {mode: 0 for mode in self.transport_keywords}
        
        for mode, keywords in self.transport_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    count = text_lower.count(keyword)
                    transport_scores[mode] += count
                    self._log(f"  Found '{keyword}' {count} times for {mode}")
        
        best_mode = max(transport_scores, key=transport_scores.get)
        result = best_mode if transport_scores[best_mode] > 0 else "mixed"
        self._log(f"  Transport scores: {transport_scores}")
        self._log(f"  Selected transport: {result}")
        return result
    
    def _parse_days_and_activities(self, lines: List[str]) -> dict[int, List[str]]:
        """Parse text lines into day-activity mapping"""
        self._log(f"Parsing {len(lines)} lines for days and activities")
        days_data = {}
        current_day = None
        
        for line_idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            self._log(f"  Processing line {line_idx}: '{line}'")
            
            day_number = self._extract_day_number(line)
            if day_number:
                self._log(f"    Found day number: {day_number}")
                current_day = day_number
                if current_day not in days_data:
                    days_data[current_day] = []
                
                activity = self._extract_activity_from_day_line(line)
                if activity:
                    self._log(f"    Activity from day line: '{activity}'")
                    days_data[current_day].append(activity)
                continue
            
            activity = self._extract_activity(line)
            if activity:
                self._log(f"    Found activity: '{activity}'")
                if current_day is not None:
                    self._log(f"    Adding to day {current_day}")
                    days_data[current_day].append(activity)
                else:
                    inferred_day = self._infer_day_from_context(line_idx, lines) or 1
                    self._log(f"    No current day, inferred day {inferred_day}")
                    if inferred_day not in days_data:
                        days_data[inferred_day] = []
                    days_data[inferred_day].append(activity)
            else:
                self._log(f"    No activity found in line")
        
        self._log(f"Final days data: {days_data}")
        return days_data
    
    def _extract_day_number(self, line: str) -> Optional[int]:
        """Extract day number from line"""
        self._log(f"    Extracting day number from: '{line}'")
        
        for i, pattern in enumerate(self.day_patterns):
            self._log(f"      Trying pattern {i+1}: {pattern}")
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                try:
                    day_num = int(match.group(1))
                    self._log(f"      MATCH! Day number: {day_num}")
                    return day_num
                except (ValueError, IndexError):
                    self._log(f"      Match but conversion failed: {match.groups()}")
                    continue
        
        for word, number in self.day_word_map.items():
            if word in line.lower():
                self._log(f"      Found day word '{word}' -> {number}")
                if number == 999:  # "останній" or "last"
                    result = self._guess_last_day_number(line)
                    self._log(f"      'Last day' guessed as: {result}")
                    return result
                return number
        
        self._log(f"      No day number found")
        return None
    
    def _guess_last_day_number(self, line: str) -> int:
        """Guess the number for 'last day' based on context"""
        duration_match = re.search(r'на\s*(\d+)\s*дні?', line, re.IGNORECASE)
        if duration_match:
            return int(duration_match.group(1))
        return 3  
    
    def _extract_activity_from_day_line(self, line: str) -> Optional[str]:
        """Extract activity from line that also contains day number"""
        self._log(f"      Extracting activity from day line: '{line}'")
        original_line = line
        
        for pattern in self.day_patterns:
            line = re.sub(pattern, '', line, flags=re.IGNORECASE)
        
        for word in self.day_word_map.keys():
            line = re.sub(r'\b' + word + r'\b', '', line, flags=re.IGNORECASE)
        
        line = re.sub(r'^[-:.\s]+', '', line).strip()
        
        self._log(f"      After cleaning: '{line}'")
        
        if len(line) > 3 and not any(noise in line.lower() for noise in self.noise_words):
            self._log(f"      Found activity: '{line}'")
            return line
        
        self._log(f"      No activity found")
        return None
    
    def _extract_activity(self, line: str) -> Optional[str]:
        """Extract activity from a single line"""
        original_line = line
        self._log(f"      Extracting activity from: '{line}'")
        
        for i, pattern in enumerate(self.activity_patterns):
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                activity = match.group(1).strip()
                self._log(f"        Pattern {i+1} matched: '{activity}'")
                if len(activity) > 3 and not any(noise in activity.lower() for noise in self.noise_words):
                    self._log(f"        Valid activity: '{activity}'")
                    return activity
        
        clean_line = re.sub(r'^[-•*\d\.\)\s:]+', '', original_line).strip()
        if len(clean_line) > 5 and not any(noise in clean_line.lower() for noise in self.noise_words):
            if re.search(r'[а-яіїєА-ЯІЇЄa-zA-Z]{3,}', clean_line):
                self._log(f"        Fallback activity: '{clean_line}'")
                return clean_line
        
        self._log(f"        No activity found")
        return None
    
    def _infer_day_from_context(self, line_idx: int, lines: List[str]) -> Optional[int]:
        """Try to infer day number from surrounding context"""
        for i in range(max(0, line_idx - 3), line_idx):
            day_num = self._extract_day_number(lines[i])
            if day_num:
                return day_num
        return None
    
    def _extract_all_activities(self, lines: List[str]) -> List[str]:
        """Extract all activities when day parsing fails"""
        self._log("Extracting all activities as fallback")
        activities = []
        for line in lines:
            activity = self._extract_activity(line)
            if activity:
                self._log(f"  Found activity: '{activity}'")
                activities.append(activity)
        
        result = activities[:10]  
        self._log(f"Fallback activities: {result}")
        return result
    
    def _build_itinerary_days(self, days_data: dict[int, List[str]], default_location: str) -> List[ItineraryDay]:
        """Build ItineraryDay objects from parsed data"""
        if not days_data:
            self._log("No days data to build from")
            return []
        
        self._log(f"Building itinerary from days data: {days_data}")
        
        itinerary_days = []
        sorted_days = sorted(days_data.keys())
        
        for day_num in sorted_days:
            activities = days_data[day_num]
            if not activities:
                activities = ["Free time"]
            
            activities = [self._clean_activity(act) for act in activities[:8]]
            activities = [act for act in activities if act]  # Remove empty ones
            
            if not activities:
                activities = ["Free time"]
            
            self._log(f"Day {day_num}: {len(activities)} activities")
            
            itinerary_days.append(ItineraryDay(
                day=day_num,
                location=default_location or "Unknown",
                activities=activities
            ))
        
        return itinerary_days
    
    def _clean_activity(self, activity: str) -> str:
        """Clean up activity text"""
        activity = re.sub(r'\s+', ' ', activity).strip()
        
        activity = re.sub(r'[,;]+$', '', activity)
        
        if activity:
            activity = activity[0].upper() + activity[1:]
        
        return activity