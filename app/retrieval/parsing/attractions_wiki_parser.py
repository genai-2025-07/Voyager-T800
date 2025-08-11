import requests
import csv
import time
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Set
import mwparserfromhell

from app.utils.file_utils import ensure_directory_exists, save_text_file, save_metadata_csv, read_csv_file

@dataclass
class AttractionMetadata:
    """Data class for attraction metadata"""
    city: str
    source_type: str
    url: str
    summary: str
    title: str
    word_count: int
    extraction_date: str
    file_path: str

class LatinTextFilter:
    """Enhanced text filtering to remove non-Latin words with high accuracy"""
    
    def __init__(self):
        """
        Initialize the LatinTextFilter with Unicode character sets and filtering rules.
        
        Sets up comprehensive Latin Unicode blocks, punctuation, numbers, and symbols
        that are allowed in the filtered text. This includes Basic Latin, Latin-1 Supplement,
        and various Latin Extended blocks for thorough coverage of Latin script characters.
        """
        # Extended Latin Unicode blocks for comprehensive coverage
        self.latin_blocks = [
            (0x0020, 0x007F),   # Basic Latin (ASCII)
            (0x00A0, 0x00FF),   # Latin-1 Supplement
            (0x0100, 0x017F),   # Latin Extended-A
            (0x0180, 0x024F),   # Latin Extended-B
            (0x1E00, 0x1EFF),   # Latin Extended Additional
            (0x2C60, 0x2C7F),   # Latin Extended-C
            (0xA720, 0xA7FF),   # Latin Extended-D
            (0xAB30, 0xAB6F),   # Latin Extended-E
        ]
        
        # Common punctuation and symbols to preserve
        self.allowed_punctuation = set('.,;:!?()[]{}"\'-–—''""…•·')
        
        # Numbers and basic symbols
        self.allowed_numbers_symbols = set('0123456789$€£¥%&@#*+=<>/')
        
        # Build allowed character set
        self.allowed_chars = set()
        for start, end in self.latin_blocks:
            for code_point in range(start, end + 1):
                self.allowed_chars.add(chr(code_point))
        
        self.allowed_chars.update(self.allowed_punctuation)
        self.allowed_chars.update(self.allowed_numbers_symbols)
        self.allowed_chars.add(' ')  # Space
        self.allowed_chars.add('\n')  # Newline
        self.allowed_chars.add('\t')  # Tab
    
    def is_latin_word(self, word: str) -> bool:
        """
        Check if a word contains only Latin characters with high accuracy.
        
        Args:
            word: The word to check for Latin characters
            
        Returns:
            bool: True if the word contains only Latin characters, punctuation, and numbers;
                  False if it contains non-Latin characters
        """
        if not word or not word.strip():
            return True  # Empty words are considered valid
        
        # Remove common punctuation from word boundaries for checking
        clean_word = word.strip('.,;:!?()[]{}"\'-–—''""…')
        
        if not clean_word:
            return True  # Word was only punctuation
        
        # Check if all characters are in allowed Latin character set
        for char in clean_word:
            if char not in self.allowed_chars:
                return False
        
        return True
    
    def contains_latin_script(self, text: str) -> bool:
        """
        Check if text contains any Latin script characters.
        
        Args:
            text: The text to check for Latin script characters
            
        Returns:
            bool: True if the text contains at least one Latin script character;
                  False otherwise
        """
        for char in text:
            if char != " ":
                if any(start <= ord(char) <= end for start, end in self.latin_blocks):
                    return True
        return False
    
    def get_script_name(self, char: str) -> str:
        """
        Get Unicode script name for a character.
        
        Args:
            char: The character to get the script name for
            
        Returns:
            str: The Unicode script name for the character, or 'UNKNOWN' if not found
        """
        try:
            return unicodedata.name(char, 'UNKNOWN').split()[0]
        except:
            return 'UNKNOWN'
    
    def analyze_word_scripts(self, word: str) -> Set[str]:
        """
        Analyze which scripts are present in a word.
        
        Args:
            word: The word to analyze for different scripts
            
        Returns:
            Set[str]: A set of script names found in the word (e.g., 'Latin', 'Cyrillic', 'Greek')
        """
        scripts = set()
        for char in word:
            if char.isalpha():  # Only check alphabetic characters
                try:
                    script = unicodedata.category(char)
                    if script.startswith('L'):  # Letter category
                        # Try to determine script more precisely
                        code_point = ord(char)
                        if any(start <= code_point <= end for start, end in self.latin_blocks):
                            scripts.add('Latin')
                        elif 0x0370 <= code_point <= 0x03FF:
                            scripts.add('Greek')
                        elif 0x0400 <= code_point <= 0x04FF:
                            scripts.add('Cyrillic')
                        elif 0x0590 <= code_point <= 0x05FF:
                            scripts.add('Hebrew')
                        elif 0x0600 <= code_point <= 0x06FF:
                            scripts.add('Arabic')
                        elif 0x4E00 <= code_point <= 0x9FFF:
                            scripts.add('CJK')
                        else:
                            scripts.add('Other')
                except:
                    scripts.add('Unknown')
        return scripts
    
    def remove_non_latin_words(self, text: str, preserve_mixed: bool = False) -> str:
        """
        Remove non-Latin words from text with high accuracy
        
        Args:
            text: Input text to filter
            preserve_mixed: If True, preserve words that contain both Latin and non-Latin chars
        
        Returns:
            Filtered text with non-Latin words removed
        """
        if not text:
            return text
        
        # Split text into lines to preserve structure
        lines = text.split('\n')
        filtered_lines = []
        
        for line in lines:
            if not line.strip():
                filtered_lines.append(line)  # Preserve empty lines
                continue
            
            # Split line into words while preserving whitespace
            words = re.findall(r'\S+|\s+', line)
            filtered_words = []
            
            for word in words:
                if word.isspace():
                    filtered_words.append(word)  # Preserve whitespace
                    continue
                
                # Analyze the word
                if self.is_latin_word(word):
                    filtered_words.append(word)
                elif preserve_mixed:
                    # Check if word contains both Latin and non-Latin
                    scripts = self.analyze_word_scripts(word)
                    if 'Latin' in scripts and len(scripts) > 1:
                        # Word contains Latin + other scripts, preserve it
                        filtered_words.append(word)
                    # Otherwise, skip the word (it's purely non-Latin)
                # If preserve_mixed is False, skip all non-Latin words
            
            # Join filtered words and clean up excessive whitespace
            line_result = ''.join(filtered_words)
            # Clean up multiple spaces and normalize whitespace
            line_result = re.sub(r' +', ' ', line_result)  # Multiple spaces to single
            line_result = line_result.strip()  # Remove leading/trailing whitespace
            filtered_lines.append(line_result)
        
        return '\n'.join(filtered_lines)
    
    def clean_text_aggressive(self, text: str) -> str:
        """
        More aggressive cleaning that removes any character not in Latin scripts.
        
        This method performs character-level filtering, removing any character that
        is not in the allowed Latin character set, including punctuation and numbers.
        
        Args:
            text: Input text to filter aggressively
            
        Returns:
            str: Filtered text with only Latin characters, punctuation, numbers, and whitespace
        """
        if not text:
            return text
        
        filtered_chars = []
        for char in text:
            if char in self.allowed_chars:
                filtered_chars.append(char)
            elif char.isspace():
                filtered_chars.append(' ')  # Normalize all whitespace to regular space
        
        # Clean up multiple spaces
        result = ''.join(filtered_chars)
        result = re.sub(r' +', ' ', result)  # Multiple spaces to single
        result = re.sub(r'\n +', '\n', result)  # Remove spaces at line start
        result = re.sub(r' +\n', '\n', result)  # Remove spaces at line end
        
        return result.strip()




class AttractionsParser:
    def __init__(self, csv_file: str = "data/attractions_names_list.csv", debug_mode: bool = False, 
                 output_dir: str = "data/raw", metadata_file: str = "data/metadata.csv"):
        """
        Initialize the AttractionsParser with configuration for Wikipedia content extraction.
        
        Args:
            csv_file: Path to the CSV file containing attraction data
            debug_mode: If True, enables debug mode with additional logging and file output
            output_dir: Directory where processed text files will be saved
            metadata_file: Path to the CSV file where metadata will be saved
        """
        self.latin_filter = LatinTextFilter()
        self.csv_file = csv_file
        self.debug_mode = debug_mode
        self.content_url = "https://en.wikipedia.org/w/api.php"
        self.remove_non_latin = True  # Enable/disable non-Latin removal
        self.preserve_mixed_words = True  # Preserve words with mixed scripts
        self.aggressive_filtering = False  # Use character-level filtering
    
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'VoyagerT800AttractionsBot/1.0 (https://example.com/contact)'
        })
        
        # Create output directories using utility functions
        self.raw_dir = ensure_directory_exists(output_dir)
        self.debug_dir = ensure_directory_exists(output_dir.replace("raw", "debug")) if debug_mode else None
        self.metadata_file = Path(metadata_file)

        self.use_see_also = False
        
    def _remove_see_also_section(self, text: str) -> str:
        """
        Remove the 'See also' section from the text.
        
        Args:
            text: Text that may contain a 'See also' section
            
        Returns:
            str: Text with the 'See also' section removed
        """
        # Split into lines and find the see also section
        lines = text.split('\n')
        result_lines = []
        in_see_also = False
        
        for line in lines:
            # Check if this line starts a new section
            if re.match(r'^\s*==\s*[^=]+\s*==\s*$', line, re.IGNORECASE):
                if 'see also' in line.lower():
                    in_see_also = True
                    continue  # Skip this line
                else:
                    in_see_also = False
            
            # If we're in see also section, check if this is a list item or empty line
            if in_see_also:
                # If it's a list item (starts with *) or empty line, skip it
                if line.strip().startswith('*') or not line.strip():
                    continue
                else:
                    # If it's not a list item, we've reached the end of the see also section
                    in_see_also = False
            
            result_lines.append(line)
        
        return '\n'.join(result_lines)
    
    def _remove_gallery_tags(self, text: str) -> str:
        """
        Remove gallery tags and their content from the text.
        
        Args:
            text: Text that may contain gallery tags
            
        Returns:
            str: Text with gallery tags removed
        """
        return re.sub(r'(?si)<gallery\b[^>]*>.*?</gallery>', '', text)
    
    def _remove_language_template_parentheses(self, text: str) -> str:
        """
        Remove parentheses containing language templates (langx, lang, Transliteration).
        
        Args:
            text: Text that may contain parentheses with language templates
            
        Returns:
            str: Text with language template parentheses removed
        """
        return re.sub(
            r'\(\s*[^()]*\{\{(?:langx?|Transliteration)[^}]*\}\}[^()]*\)',
            '',
            text
        )
    
    def _remove_empty_parentheses(self, text: str) -> str:
        """
        Remove parentheses that are empty or contain only separators and whitespace.
        
        Args:
            text: Text that may contain empty parentheses
            
        Returns:
            str: Text with empty parentheses removed
        """
        return re.sub(r'\(\s*[,;\'"\s]*\s*\)', '', text)
    
    def _remove_template_parentheses(self, text: str) -> str:
        """
        Remove parentheses containing template remnants and separators.
        
        Args:
            text: Text that may contain parentheses with template remnants
            
        Returns:
            str: Text with template parentheses removed
        """
        return re.sub(
            r'\(\s*(?:[^()]*\{\{[^}]*\}\}[,\s;\'":]*)+[^()]*\)',
            '',
            text
        )
    
    def _cleanup_remaining_parentheses(self, text: str) -> str:
        """
        Clean up any remaining empty or near-empty parentheses.
        
        Args:
            text: Text that may contain remaining empty parentheses
            
        Returns:
            str: Text with remaining empty parentheses cleaned up
        """
        return re.sub(r'\(\s*(?:[,;\'"\s]|\{\{[^}]*\}\})*\s*\)', '', text)
    
    def _cleanup_excessive_quotes(self, text: str) -> str:
        """
        Clean up triple parentheses and excessive quotes.
        
        Args:
            text: Text that may contain excessive quotes
            
        Returns:
            str: Text with excessive quotes cleaned up
        """
        # First, handle triple quotes
        text = re.sub(r"'''(.+?)'''", r"'\1'", text)
        # Then handle double quotes
        text = re.sub(r"''(.+?)''", r"'\1'", text)
        # Handle double brackets around quoted content
        text = re.sub(r"\[\[([^\[\]]+)\]\]", r"[\1]", text)
        return text
    
    def _remove_list_markers(self, text: str) -> str:
        """
        Remove all list markers ("*", "**", etc.) at the start of any line.
        
        Args:
            text: Text that may contain list markers
            
        Returns:
            str: Text with list markers removed
        """
        return re.sub(
            r'^[ \t]*\*+[ \t]*',
            '',
            text,
            flags=re.MULTILINE
        )
    
    def _cleanup_whitespace(self, text: str) -> str:
        """
        Clean up excessive whitespace while preserving structure.
        
        Args:
            text: Text that may contain excessive whitespace
            
        Returns:
            str: Text with whitespace cleaned up
        """
        return re.sub(r'[ \t]+', ' ', text)
    
    def _apply_text_cleaning_regex(self, text: str) -> str:
        """
        Apply all text cleaning regular expressions in sequence.
        
        This method applies a series of regex-based cleaning operations:
        1. Remove 'See also' section
        2. Remove gallery tags
        3. Remove language template parentheses
        4. Remove empty parentheses
        5. Remove template parentheses
        6. Clean up remaining parentheses
        7. Clean up excessive quotes
        8. Remove list markers
        9. Clean up whitespace
        
        Args:
            text: Raw text to be cleaned
            
        Returns:
            str: Text cleaned using all regex patterns
        """
        text = self._remove_see_also_section(text)
        text = self._remove_gallery_tags(text)
        text = self._remove_language_template_parentheses(text)
        text = self._remove_empty_parentheses(text)
        text = self._remove_template_parentheses(text)
        text = self._cleanup_remaining_parentheses(text)
        text = self._cleanup_excessive_quotes(text)
        text = self._remove_list_markers(text)
        text = self._cleanup_whitespace(text)
        
        return text
        
    def read_attractions_csv(self) -> List[Dict[str, str]]:
        """
        Read attractions data from the configured CSV file.
        
        Returns:
            List[Dict[str, str]]: List of dictionaries containing attraction data
                                 with keys: 'City', 'Attraction', 'WikiLink'
        """
        return read_csv_file(self.csv_file)
    
    def extract_title_from_url(self, url: str) -> str:
        """
        Extract Wikipedia page title from a Wikipedia URL.
        
        Args:
            url: Wikipedia URL to extract the title from
            
        Returns:
            str: The extracted page title, or empty string if extraction fails
        """
        try:
            # Parse the URL to get the title
            parsed = urlparse(url)
            path = parsed.path
            # Remove /wiki/ prefix and decode URL encoding
            title = path.replace('/wiki/', '').replace('_', ' ')
            return title
        except Exception as e:
            print(f"Error extracting title from URL {url}: {e}")
            return ""
    
    def get_page_content(self, title: str) -> Optional[Dict]:
        """
        Get full page content from Wikipedia API.
        
        Args:
            title: Wikipedia page title to fetch content for
            
        Returns:
            Optional[Dict]: Dictionary containing page data with keys:
                           'title', 'wikitext', 'url', 'timestamp', 'pageid'
                           or None if the page cannot be fetched
        """
        params = {
            'action': 'query',
            'format': 'json',
            'titles': title,
            'prop': 'revisions',
            'rvprop': 'content',
            'rvslots': 'main',
            'inprop': 'url|timestamp'
        }
        
        try:
            response = self.session.get(self.content_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'query' in data and 'pages' in data['query']:
                pages = data['query']['pages']
                page_id = list(pages.keys())[0]
                page_data = pages[page_id]
                
                if page_id != '-1' and 'revisions' in page_data:
                    revision = page_data['revisions'][0]
                    wikitext = revision['slots']['main']['*']
                    
                    return {
                        'title': page_data.get('title', title),
                        'wikitext': wikitext,
                        'url': page_data.get('fullurl', ''),
                        'timestamp': page_data.get('touched', ''),
                        'pageid': page_id
                    }
            
            return None
            
        except requests.RequestException as e:
            print(f"Error fetching content for {title}: {e}")
            return None

    def clean_text(self, wikitext: str) -> str:
        """
        Clean and format wikitext using mwparserfromhell, preserving paragraph and section spacing.
        
        This method processes Wikipedia markup to extract clean, readable text by:
        - Removing templates, comments, and unwanted tags
        - Converting wikilinks to plain text
        - Preserving paragraph structure and spacing
        - Optionally filtering non-Latin characters
        
        Args:
            wikitext: Raw Wikipedia markup text to clean
            
        Returns:
            str: Cleaned and formatted text suitable for processing
        """
        if not wikitext:
            return ""
        
        try:
            # Parse into AST
            wikicode = mwparserfromhell.parse(wikitext)

            
            # Process and remove templates
            for tpl in list(wikicode.filter_templates()):
                try:
                    name = tpl.name.strip().lower()
                    
                    # Remove coordinate templates
                    if name.startswith('infobox') or name in ['coord', 'wikidatacoord']:
                        wikicode.remove(tpl)
                    
                    # Handle 'lang' and 'langx' templates - remove them completely
                    if name == 'lang' or name == 'langx':
                        wikicode.remove(tpl)
                    
                    # Handle nobold templates
                    elif name == 'nobold':
                        try:
                            if tpl.params:
                                inner = tpl.params[0].value.strip_code()
                                wikicode.replace(tpl, inner)
                            else:
                                wikicode.remove(tpl)
                        except Exception as e:
                            print(f"Warning: Error processing nobold template: {e}")
                            wikicode.remove(tpl)
                    
                    # Handle convert templates
                    elif name == 'convert':
                        try:
                            params = list(tpl.params)
                            if len(params) >= 2:
                                value = params[0].value.strip_code()
                                unit = params[1].value.strip_code()
                                unit_map = {'m': 'metres', 'km': 'kilometres', 'ft': 'ft', 'mi': 'miles'}
                                wikicode.replace(tpl, f"{value} {unit_map.get(unit, unit)}")
                            else:
                                wikicode.remove(tpl)
                        except Exception as e:
                            print(f"Warning: Error processing convert template: {e}")
                            wikicode.remove(tpl)
                    
                    # Handle pipe template (table separator)
                    elif name == '!':
                        wikicode.remove(tpl)
                    
                    # Remove all other templates (this will now also remove 'langx')
                    else:
                        wikicode.remove(tpl)
                        
                except Exception as e:
                    print(f"Warning: Error processing template {tpl.name}: {e}")
                    try:
                        wikicode.remove(tpl)
                    except:
                        pass
            
            # Remove comments and ref tags
            for comment in wikicode.filter_comments():
                wikicode.remove(comment)
            for tag in wikicode.filter_tags(matches=lambda n: n.tag == 'ref'):
                wikicode.remove(tag)
            
            # Remove tables and unwanted tags
            for table in wikicode.filter_tags(matches=lambda n: n.tag == 'table'):
                wikicode.remove(table)
            
            # Remove file/category links
            for link in list(wikicode.filter_wikilinks()):
                try:
                    t = link.title.lower()
                    if t.startswith(('file:', 'image:', 'category:')):
                        wikicode.remove(link)
                except Exception as e:
                    print(f"Warning: Error processing wikilink: {e}")
                    try:
                        wikicode.remove(link)
                    except:
                        pass
            
            # Replace remaining links
            for link in wikicode.filter_wikilinks():
                try:
                    repl = link.text or link.title
                    wikicode.replace(link, repl)
                except Exception as e:
                    print(f"Warning: Error replacing wikilink: {e}")
                    try:
                        wikicode.remove(link)
                    except:
                        pass
            
            for ext in wikicode.filter_external_links():
                try:
                    wikicode.replace(ext, ext.title or '')
                except Exception as e:
                    print(f"Warning: Error processing external link: {e}")
                    try:
                        wikicode.remove(ext)
                    except:
                        pass
            
            # Render to text
            raw = str(wikicode).strip()
            
            # Apply regex-based text cleaning
            raw = self._apply_text_cleaning_regex(raw)

            if not self.remove_non_latin or not raw:
                return raw
            
            # Apply Latin filtering
            if self.aggressive_filtering:
                # Character-level filtering (more aggressive)
                filtered_text = self.latin_filter.clean_text_aggressive(raw)
            else:
                # Word-level filtering (more precise)
                filtered_text = self.latin_filter.remove_non_latin_words(
                    raw, 
                    preserve_mixed=self.preserve_mixed_words
                )
            
            return filtered_text.strip()
            
        except Exception as e:
            print(f"Error in clean_text: {e}")
            # Fallback: return empty string or basic cleaning
            return ""

    def _preserve_structure(self, text: str) -> str:
        """
        Preserve paragraph structure with proper spacing between sections and paragraphs.
        
        This method processes text to maintain proper document structure by:
        - Adding blank lines before and after headers
        - Preserving paragraph breaks
        - Cleaning up excessive whitespace while maintaining readability
        
        Args:
            text: Text to process for structure preservation
            
        Returns:
            str: Text with preserved structure and proper spacing
        """
        if not text:
            return ""
        
        # Split into lines and process each line
        lines = text.split('\n')
        processed_lines = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Skip empty lines but preserve them for structure
            if not stripped:
                # Only add blank line if previous line wasn't blank
                if processed_lines and processed_lines[-1] != '':
                    processed_lines.append('')
                continue
            
            # Check if this is a header (starts with == or ===)
            if re.match(r'^=+\s*[^=]+\s*=+$', stripped):
                # Extract header text
                header_match = re.match(r'^=+\s*([^=]+?)\s*=+$', stripped)
                if header_match:
                    header_text = header_match.group(1).strip()
                    # Add blank line before header if not already there
                    if processed_lines and processed_lines[-1] != '':
                        processed_lines.append('')
                    processed_lines.append(header_text)
                    # Add blank line after header
                    processed_lines.append('')
            else:
                # Regular paragraph line
                processed_lines.append(stripped)
        
        # Join lines with proper spacing
        result = '\n'.join(processed_lines)
        
        # Clean up excessive whitespace while preserving structure
        # Replace multiple spaces with single space within lines
        result = re.sub(r'[ \t]+', ' ', result)
        
        # Replace multiple consecutive newlines with double newlines (preserve structure)
        result = re.sub(r'\n{3,}', '\n\n', result)
        
        return result.strip()

    
    def save_text_file(self, content: str, filename: str, debug_content: str = None) -> str:
        """
        Save text content to a file in the configured output directory.
        
        Args:
            content: The text content to save
            filename: Base filename (without extension) for the output file
            debug_content: Optional raw content to save in debug mode
            
        Returns:
            str: Path to the saved file, or empty string if saving fails
        """
        file_path = self.raw_dir / f"{filename}.txt"
        
        # Save main content
        if not save_text_file(content, file_path):
            return ""
        
        # In debug mode, also save the raw content
        if self.debug_mode and debug_content:
            debug_filename = f"raw_{filename}.txt"
            debug_path = self.debug_dir / debug_filename
            if save_text_file(debug_content, debug_path):
                print(f"Debug: Raw content saved to {debug_path}")
        
        return str(file_path)
    
    def generate_summary(self, text: str, max_length: int = 200) -> str:
        """
        Generate a summary from the text by taking the first paragraph.
        
        Args:
            text: The text to generate a summary from
            max_length: Maximum length of the summary (default: 200 characters)
            
        Returns:
            str: A summary of the text, truncated to max_length if necessary
        """
        if not text:
            return ""
        
        # Take the first paragraph or first max_length characters
        paragraphs = text.split('\n\n')
        if paragraphs:
            summary = paragraphs[0].strip()
            if len(summary) > max_length:
                summary = summary[:max_length] + "..."
            
            return summary.replace('\n', '')
        
        return text[:max_length].replace('\n', '') + "..." if len(text) > max_length else text
    
    def process_attraction(self, attraction_data: Dict[str, str]) -> Optional[AttractionMetadata]:
        """
        Process a single attraction by fetching and cleaning its Wikipedia content.
        
        This method performs the complete processing pipeline for one attraction:
        1. Extracts the Wikipedia title from the URL
        2. Fetches the page content from Wikipedia API
        3. Cleans and formats the text
        4. Saves the processed text to a file
        5. Creates metadata for the processed attraction
        
        Args:
            attraction_data: Dictionary containing attraction information with keys:
                           'City', 'Attraction', 'WikiLink'
            
        Returns:
            Optional[AttractionMetadata]: Metadata object for the processed attraction,
                                        or None if processing fails
        """
        city = attraction_data.get('City', '')
        attraction = attraction_data.get('Attraction', '')
        wiki_url = attraction_data.get('WikiLink', '')
        
        if not all([city, attraction, wiki_url]):
            print(f"Skipping incomplete attraction data: {attraction_data}")
            return None
        
        print(f"Processing: {attraction} in {city}")
        
        # Extract title from URL
        title = self.extract_title_from_url(wiki_url)
        if not title:
            print(f"Could not extract title from URL: {wiki_url}")
            return None
        
        # Get page content
        content_data = self.get_page_content(title)
        if not content_data:
            print(f"Could not fetch content for: {title}")
            return None
        
        # Get raw text before cleaning
        raw_text = content_data.get('wikitext', '')
        
        # Clean the text
        clean_text = self.clean_text(raw_text)
        if not clean_text:
            print(f"No content extracted for: {title}")
            return None
        
        # Create filename and save
        filename = city + "_" + attraction
        file_path = self.save_text_file(clean_text, filename, raw_text if self.debug_mode else None)
        
        if not file_path:
            return None
        
        # Create metadata
        word_count = len(clean_text.split())
        summary = self.generate_summary(clean_text)
        
        metadata = AttractionMetadata(
            city=city,
            source_type="wikipedia",
            url=wiki_url,
            summary=summary,
            title=attraction,
            word_count=word_count,
            extraction_date=time.strftime('%Y-%m-%d %H:%M:%S'),
            file_path=file_path
        )
        
        print(f"Successfully processed: {attraction} ({word_count} words)")
        
        # Debug information
        if self.debug_mode:
            print(f"Debug: Raw text length: {len(raw_text)}")
            print(f"Debug: Cleaned text length: {len(clean_text)}")
            print(f"Debug: Raw text preview: {raw_text[:200]}...")
            print(f"Debug: Cleaned text preview: {clean_text[:200]}...")
        
        return metadata
    
    def save_metadata_csv(self, metadata_list: List[AttractionMetadata]):
        """
        Save metadata to CSV file for all processed attractions.
        
        Args:
            metadata_list: List of AttractionMetadata objects to save to CSV
        """
        fieldnames = ['city', 'source_type', 'url', 'summary', 'title', 
                      'word_count', 'extraction_date', 'file_path']
        save_metadata_csv(metadata_list, self.metadata_file, fieldnames)
    
    def run_extraction(self):
        """
        Main extraction process that processes all attractions from the CSV file.
        
        This method orchestrates the complete extraction workflow:
        1. Reads attractions from the configured CSV file
        2. Processes each attraction individually
        3. Collects metadata for successful extractions
        4. Saves metadata to CSV file
        5. Reports extraction statistics
        """
        mode_str = "DEBUG" if self.debug_mode else "NORMAL"
        print(f"Starting attractions extraction in {mode_str} mode...")
        
        # Read attractions from CSV
        attractions = self.read_attractions_csv()
        if not attractions:
            print("No attractions found in CSV file")
            return
        
        metadata_list = []
        successful = 0
        failed = 0
        
        for i, attraction_data in enumerate(attractions, 1):
            print(f"\nProcessing {i}/{len(attractions)}: {attraction_data.get('Attraction', 'Unknown')}")
            
            try:
                metadata = self.process_attraction(attraction_data)
                if metadata:
                    metadata_list.append(metadata)
                    successful += 1
                else:
                    failed += 1
                
                # Rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                print(f"Error processing attraction: {e}")
                failed += 1
        
        # Save metadata
        self.save_metadata_csv(metadata_list)
        
        print(f"\nExtraction completed!")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Total: {len(attractions)}")
        print(f"Text files saved to: {self.raw_dir}")
        if self.debug_mode:
            print(f"Debug files saved to: {self.debug_dir}")
        print(f"Metadata saved to: {self.metadata_file}")


def main():
    """Main function that delegates to the CLI module"""
    from app.cli.attractions_cli import main as cli_main
    return cli_main()


if __name__ == "__main__":
    import sys
    sys.exit(main()) 