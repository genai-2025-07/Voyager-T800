import re
from typing import List, Optional, Dict
from dataclasses import dataclass
from enum import Enum

from app.models.llms.itinerary import ItineraryDay, TravelItinerary


class TransportationType(Enum):
    """Supported transportation types"""
    DRIVING = "driving"
    WALKING = "walking"
    CYCLING = "cycling"
    PUBLIC_TRANSIT = "public_transit"
    FLIGHT = "flight"
    MIXED = "mixed"


class ParsingError(Exception):
    """Base exception for parsing errors"""
    pass


class InvalidTextError(ParsingError):
    """Raised when input text is invalid or empty"""
    pass

@dataclass
class ParsingConfig:
    """Configuration for parsing behavior"""
    max_activities_per_day: int = 8
    max_fallback_activities: int = 10
    default_day_for_orphaned_activities: int = 1
    default_last_day_guess: int = 3
    min_activity_length: int = 3
    min_destination_length: int = 2
@dataclass
class ParsingPatterns:
    """Container for all regex patterns used in parsing"""
    
    DAY_PATTERNS = [
        r'день\s*(\d+)',
        r'day\s*(\d+)',
        r'(\d+)[-\s]*й?\s*день',
        r'(\d+)(?:st|nd|rd|th)\s*day',
        r'^(\d+)\.?\s*(?=\w)',
        r'перший\s*день',
        r'другий\s*день',
        r'третій\s*день',
        r'останній\s*день',
    ]
    
    DAY_WORD_MAP = {
        'перший': 1, 'другий': 2, 'третій': 3, 'четвертий': 4, "п'ятий": 5,
        'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
        'останній': 999, 'last': 999
    }
    
    LOCATION_PATTERNS = [
        r'(?:поїздка|подорож)\s+(?:в|до|у)\s+([А-Яєіїґa-z\s-]+?)(?:\s+на|\s*[,\.\n]|$)',
        r'(?:поїхати|їхати|летіти|відвідати)\s+(?:в|до|у)\s+([А-Яєіїґa-z\s-]+?)(?:\s+на|\s*[,\.\n]|$)',
        r'(?:trip|travel|visit|go)\s+to\s+([A-Za-z\s-]+?)(?:\s+for|\s*[,\.\n]|$)',
        r'in\s+([A-Z][A-Za-z\s-]+?)(?:\s+for|\s*[,\.\n]|$)',
        r'([А-ЯA-Z][А-Яєіїґa-z\s-]+?)(?=\s*[-–:]\s*(?:день|day|прибуття|arrival))',
    ]
    
    ACTIVITY_PATTERNS = [
        r'^\s*[-•*]\s*(.+)$',
        r'^\s*\d+\.\s*(.+)$',
        r'^\s*\d+\)\s*(.+)$',
        r'(?:відвідування|відвідати)\s+(.+)$',
        r'(?:visit|visiting)\s+(.+)$',
        r'(?:прогулянка|прогулятися)\s+(.+)$',
        r'(?:walk|walking)\s+(.+)$',
        r'(?:вечеря|обід|сніданок)\s+(.+)$',
        r'(?:dinner|lunch|breakfast)\s+(.+)$',
        r'(?:екскурсія|тур)\s+(.+)$',
        r'(?:tour|excursion)\s+(.+)$',
    ]
    
    TRANSPORT_KEYWORDS = {
        TransportationType.DRIVING: ['машина', 'автомобіль', 'car', 'drive', 'driving'],
        TransportationType.WALKING: ['пішки', 'ходьба', 'walk', 'walking', 'on foot'],
        TransportationType.CYCLING: ['велосипед', 'bike', 'bicycle', 'cycling', 'велосипедна'],
        TransportationType.PUBLIC_TRANSIT: ['транспорт', 'автобус', 'метро', 'bus', 'metro', 'train', 'tram'],
        TransportationType.FLIGHT: ['літак', 'авіа', 'flight', 'plane', 'airplane'],
    }
    
    NOISE_WORDS = {
        'день', 'day', 'активності', 'activities', 'план', 'plan', 'маршрут', 'itinerary',
        'розклад', 'schedule', 'програма', 'program', 'поїздка', 'trip', 'подорож', 'travel',
        'прибуття', 'arrival', "від'їзд", 'departure', 'ввечері', 'evening', 'потім', 'then'
    }


class TextNormalizer:
    """Handles text normalization and cleaning"""
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """Clean and normalize input text while preserving line structure"""
        lines = text.split('\n')
        normalized_lines = []
        
        for line in lines:
            line = re.sub(r'[ \t]+', ' ', line)
            line = re.sub(r'[^\w\s\-\.\,\:\;\!\?\(\)№àáâãäåæçèéêëìíîïñòóôõöøùúûüýÿ]', ' ', line)
            line = line.replace('—', '-').replace('–', '-')
            
            line = line.strip()
            if line:
                normalized_lines.append(line)
        
        return '\n'.join(normalized_lines)


class ActivityExtractor:
    """Handles extraction of activities from text"""
    
    def __init__(self, patterns: ParsingPatterns, config: ParsingConfig):
        self.patterns = patterns
        self.config = config
    
    def extract_activity(self, line: str) -> Optional[str]:
        """Extract activity from a single line"""
        for pattern in self.patterns.ACTIVITY_PATTERNS:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                activity = match.group(1).strip()
                if self._is_valid_activity(activity):
                    return activity
        
        # Fallback: try to clean the line directly
        clean_line = re.sub(r'^[-•*\d\.\)\s:]+', '', line).strip()
        if self._is_valid_activity(clean_line) and len(clean_line) > self.config.min_activity_length + 2:
            return clean_line
        
        return None
    
    def _is_valid_activity(self, activity: str) -> bool:
        """Check if extracted text is a valid activity"""
        if len(activity) <= self.config.min_activity_length:
            return False
        
        if any(noise in activity.lower() for noise in self.patterns.NOISE_WORDS):
            return False
        
        # Check if contains meaningful text
        return bool(re.search(r'[а-яєіїґА-ЯЄІЇҐa-zA-Z]{3,}', activity))
    
    def clean_activity(self, activity: str) -> str:
        """Clean up activity text"""
        activity = re.sub(r'\s+', ' ', activity).strip()
        activity = re.sub(r'[,;]+$', '', activity)
        
        if activity:
            activity = activity[0].upper() + activity[1:]
        
        return activity


class DayParser:
    """Handles parsing of day numbers and day-related content"""
    
    def __init__(self, patterns: ParsingPatterns, config: ParsingConfig):
        self.patterns = patterns
        self.config = config
    
    def extract_day_number(self, line: str) -> Optional[int]:
        """Extract day number from line"""
        # Try numeric patterns
        for pattern in self.patterns.DAY_PATTERNS:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    continue
        
        # Try word patterns
        for word, number in self.patterns.DAY_WORD_MAP.items():
            if word in line.lower():
                if number == 999:  # "останній" or "last"
                    return self._guess_last_day_number(line)
                return number
        
        return None
    
    def extract_activity_from_day_line(self, line: str) -> Optional[str]:
        """Extract activity from line that also contains day number"""
        original_line = line
        
        # Remove day patterns
        for pattern in self.patterns.DAY_PATTERNS:
            line = re.sub(pattern, '', line, flags=re.IGNORECASE)
        
        # Remove day words
        for word in self.patterns.DAY_WORD_MAP.keys():
            line = re.sub(r'\b' + word + r'\b', '', line, flags=re.IGNORECASE)
        
        # Clean up remaining text
        line = re.sub(r'^[-:.\s]+', '', line).strip()
        
        if len(line) > 3 and not any(noise in line.lower() for noise in self.patterns.NOISE_WORDS):
            return line
        
        return None
    
    def _guess_last_day_number(self, line: str) -> int:
        """Guess the number for 'last day' based on context"""
        duration_match = re.search(r'на\s*(\d+)\s*дні?', line, re.IGNORECASE)
        return int(duration_match.group(1)) if duration_match else self.config.default_last_day_guess


class DestinationExtractor:
    """Handles extraction of travel destinations"""
    
    def __init__(self, patterns: ParsingPatterns, config: ParsingConfig):
        self.patterns = patterns
        self.config = config
    
    def extract_destination(self, text: str) -> Optional[str]:
        """Extract main destination from text"""
        for pattern in self.patterns.LOCATION_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            
            if matches:
                destination = matches[0].strip()
                destination = self._clean_destination(destination)
                
                if self._is_valid_destination(destination):
                    return destination
        
        return None
    
    def _clean_destination(self, destination: str) -> str:
        """Clean extracted destination text"""
        # Remove duration info
        destination = re.sub(r'\s*на\s*\d+\s*дні?.*$', '', destination, flags=re.IGNORECASE)
        destination = re.sub(r'\s*for\s*\d+\s*days?.*$', '', destination, flags=re.IGNORECASE)
        return destination.strip()
    
    def _is_valid_destination(self, destination: str) -> bool:
        """Check if extracted text is a valid destination"""
        return (len(destination) > self.config.min_destination_length and 
                destination.lower() not in self.patterns.NOISE_WORDS)


class TransportationDetector:
    """Handles detection of transportation methods"""
    
    def __init__(self, patterns: ParsingPatterns):
        self.patterns = patterns
    
    def detect_transportation(self, text: str) -> TransportationType:
        """Determine primary transportation method"""
        text_lower = text.lower()
        transport_scores = {mode: 0 for mode in self.patterns.TRANSPORT_KEYWORDS}
        
        for mode, keywords in self.patterns.TRANSPORT_KEYWORDS.items():
            for keyword in keywords:
                transport_scores[mode] += text_lower.count(keyword)
        
        best_mode = max(transport_scores, key=transport_scores.get)
        return best_mode if transport_scores[best_mode] > 0 else TransportationType.MIXED


class ManualItineraryParser:
    """Main parser class that orchestrates the parsing process"""
    
    def __init__(self, config: Optional[ParsingConfig] = None, debug: bool = False):
        self.debug = debug
        self.config = config or ParsingConfig()
        self.patterns = ParsingPatterns()
        
        # Initialize specialized parsers
        self.text_normalizer = TextNormalizer()
        self.activity_extractor = ActivityExtractor(self.patterns, self.config)
        self.day_parser = DayParser(self.patterns, self.config)
        self.destination_extractor = DestinationExtractor(self.patterns, self.config)
        self.transport_detector = TransportationDetector(self.patterns)
    
    def parse_itinerary_text(self, text: str) -> TravelItinerary:
        """Parse travel itinerary from free-form text"""
        if not text or not text.strip():
            raise InvalidTextError("Input text cannot be empty")
        
        self._log("Starting itinerary parsing")
        
        try:
            normalized_text = self.text_normalizer.normalize_text(text)
            lines = self._split_into_lines(normalized_text)
            
            destination = self.destination_extractor.extract_destination(normalized_text)
            transportation = self.transport_detector.detect_transportation(normalized_text)
            
            days_data = self._parse_days_and_activities(lines)
            itinerary_days = self._build_itinerary_days(days_data, destination)
            
            # Fallback if no structured days found
            if not itinerary_days:
                itinerary_days = self._create_fallback_itinerary(lines, destination)
            
            return TravelItinerary(
                destination=destination or "Unknown",
                duration_days=len(itinerary_days),
                transportation=transportation.value,  # Convert enum to string
                itinerary=itinerary_days
            )
        except Exception as e:
            self._log(f"Error during parsing: {e}")
            raise ParsingError(f"Failed to parse itinerary: {e}") from e
    
    def _split_into_lines(self, text: str) -> List[str]:
        """Split text into non-empty lines"""
        return [line.strip() for line in text.split('\n') if line.strip()]
    
    def _parse_days_and_activities(self, lines: List[str]) -> Dict[int, List[str]]:
        """Parse text lines into day-activity mapping"""
        days_data = {}
        current_day = None
        
        for line_idx, line in enumerate(lines):
            self._log(f"Processing line: {line}")
            
            # Check if line contains a day number
            day_number = self.day_parser.extract_day_number(line)
            if day_number:
                current_day = day_number
                if current_day not in days_data:
                    days_data[current_day] = []
                
                # Try to extract activity from the same line
                activity = self.day_parser.extract_activity_from_day_line(line)
                if activity:
                    days_data[current_day].append(activity)
                continue
            
            # Extract regular activity
            activity = self.activity_extractor.extract_activity(line)
            if activity:
                target_day = (current_day or 
                            self._infer_day_from_context(line_idx, lines) or 
                            self.config.default_day_for_orphaned_activities)
                
                if target_day not in days_data:
                    days_data[target_day] = []
                days_data[target_day].append(activity)
        
        return days_data
    
    def _infer_day_from_context(self, line_idx: int, lines: List[str]) -> Optional[int]:
        """Try to infer day number from surrounding context"""
        # Look at previous lines for day context
        for i in range(max(0, line_idx - 3), line_idx):
            day_num = self.day_parser.extract_day_number(lines[i])
            if day_num:
                return day_num
        return None
    
    def _build_itinerary_days(self, days_data: Dict[int, List[str]], default_location: str) -> List[ItineraryDay]:
        """Build ItineraryDay objects from parsed data"""
        if not days_data:
            return []
        
        itinerary_days = []
        for day_num in sorted(days_data.keys()):
            activities = days_data[day_num]
            
            # Clean and limit activities
            cleaned_activities = [
                self.activity_extractor.clean_activity(act) 
                for act in activities[:self.config.max_activities_per_day]
            ]
            cleaned_activities = [act for act in cleaned_activities if act]
            
            if not cleaned_activities:
                cleaned_activities = ["Free time"]
            
            itinerary_days.append(ItineraryDay(
                day=day_num,
                location=default_location or "Unknown",
                activities=cleaned_activities
            ))
        
        return itinerary_days
    
    def _create_fallback_itinerary(self, lines: List[str], destination: str) -> List[ItineraryDay]:
        """Create fallback itinerary when structured parsing fails"""
        self._log("Creating fallback itinerary")
        
        activities = []
        for line in lines:
            activity = self.activity_extractor.extract_activity(line)
            if activity:
                activities.append(activity)
        
        if not activities:
            activities = ["Plan your activities"]
        else:
            activities = activities[:self.config.max_fallback_activities]
        
        return [ItineraryDay(
            day=1,
            location=destination or "Unknown",
            activities=activities
        )]
    
    def _log(self, message: str) -> None:
        """Debug logging helper"""
        if self.debug:
            print(f"ManualItineraryParser: {message}")  # Could be replaced with proper logger