import requests
import csv
import time
import re
import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
import mwparserfromhell

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

import re
import unicodedata
from typing import Set, List

class LatinTextFilter:
    """Enhanced text filtering to remove non-Latin words with high accuracy"""
    
    def __init__(self):
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
        Check if a word contains only Latin characters with high accuracy
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
        """Check if text contains any Latin script characters"""
        for char in text:
            if any(start <= ord(char) <= end for start, end in self.latin_blocks):
                return True
        return False
    
    def get_script_name(self, char: str) -> str:
        """Get Unicode script name for a character"""
        try:
            return unicodedata.name(char, 'UNKNOWN').split()[0]
        except:
            return 'UNKNOWN'
    
    def analyze_word_scripts(self, word: str) -> Set[str]:
        """Analyze which scripts are present in a word"""
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
            
            filtered_lines.append(''.join(filtered_words))
        
        return '\n'.join(filtered_lines)
    
    def clean_text_aggressive(self, text: str) -> str:
        """
        More aggressive cleaning that removes any character not in Latin scripts
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
        
        # Create output directories
        self.raw_dir = Path(output_dir)
        self.debug_dir = Path(output_dir.replace("raw", "debug")) if debug_mode else None
        self.metadata_file = Path(metadata_file)
        
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        if debug_mode:
            self.debug_dir.mkdir(parents=True, exist_ok=True)

        self.use_see_also = False
        
    def read_attractions_csv(self) -> List[Dict[str, str]]:
        """Read attractions from CSV file"""
        attractions = []
        try:
            with open(self.csv_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    attractions.append(row)
            print(f"Loaded {len(attractions)} attractions from CSV")
            
            return attractions
        
        except FileNotFoundError:
            print(f"Error: CSV file {self.csv_file} not found")
            return []
        except Exception as e:
            print(f"Error reading CSV file: {e}")
            return []
    
    def extract_title_from_url(self, url: str) -> str:
        """Extract Wikipedia page title from URL"""
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
        """Get full page content from Wikipedia API"""
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
        """Clean and format wikitext using mwparserfromhell, preserving paragraph and section spacing"""
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
            
            # do we need see also?
            if not self.use_see_also:
                raw = re.sub(r'(?si)==\s*see also\s*==.*', '', raw)

            # removing gallery tags
            # Remove <gallery ...>...</gallery> blocks (with attributes)
            raw = re.sub(r'(?si)<gallery\b[^>]*>.*?</gallery>', '', raw)

            # Remove parentheses containing language templates (langx, lang) - IMPROVED VERSION
            # This pattern matches parentheses that contain langx or lang templates
            raw = re.sub(
                r'\(\s*[^()]*\{\{(?:langx?|Transliteration)[^}]*\}\}[^()]*\)',
                '',
                raw
            )
            
            # More comprehensive removal of parentheses with template remnants
            # Remove parentheses that are now empty or contain only commas, semicolons, quotes, and whitespace
            raw = re.sub(r'\(\s*[,;\'"\s]*\s*\)', '', raw)
            
            # Remove parentheses containing combinations of templates and separators
            raw = re.sub(
                r'\(\s*(?:[^()]*\{\{[^}]+\}\}[,\s;\'":]*)+[^()]*\)',
                '',
                raw
            )
            
            # Clean up any remaining empty or near-empty parentheses
            raw = re.sub(r'\(\s*(?:[,;\'"\s]|\{\{[^}]*\}\})*\s*\)', '', raw)
            
            # Clean up triple parentheses and excessive quotes
            raw = re.sub(
                r"(\[*)(?:'+)(.+?)(?:'+)(\]*)",
                r"\1'\2'\3",
                raw
            )

            # remove all list markers (“*”, “**”, etc.) at the start of any line
            raw = re.sub(
                r'^[ \t]*\*+[ \t]*',
                '',
                raw,
                flags=re.MULTILINE
            )

            # Removes excessive spaces and \n's:
            # raw = re.sub(r'\s+', ' ', raw)

            # Current approach for readability
            raw = re.sub(r'[ \t]+', ' ', raw)

            if not self.remove_non_latin or not raw:
                return cleaned_text
            
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
        """Preserve paragraph structure with proper spacing between sections and paragraphs"""
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
        """Save text content to file"""
        file_path = self.raw_dir / f"{filename}.txt"
        
        try:
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(content)
            
            # In debug mode, also save the raw content
            if self.debug_mode and debug_content:
                debug_filename = f"raw_{filename}.txt"
                debug_path = self.debug_dir / debug_filename
                with open(debug_path, 'w', encoding='utf-8') as debug_file:
                    debug_file.write(debug_content)
                print(f"Debug: Raw content saved to {debug_path}")
            
            return str(file_path)
        except Exception as e:
            print(f"Error saving file {filename}: {e}")
            return ""
    
    def generate_summary(self, text: str, max_length: int = 200) -> str:
        """Generate a summary from the text"""
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
        """Process a single attraction"""
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
        """Save metadata to CSV file"""
        if not metadata_list:
            print("No metadata to save")
            return
        
        try:
            with open(self.metadata_file, 'w', newline='', encoding='utf-8') as file:
                fieldnames = ['city', 'source_type', 'url', 'summary', 'title', 
                              'word_count', 'extraction_date', 'file_path']
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                
                for metadata in metadata_list:
                    writer.writerow(asdict(metadata))
            
            print(f"Metadata saved to {self.metadata_file}")
            
        except Exception as e:
            print(f"Error saving metadata: {e}")
    
    def run_extraction(self):
        """Main extraction process"""
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
    """Main function with command-line argument parsing"""
    parser = argparse.ArgumentParser(description="Attractions Wiki Parser")
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--output-dir', type=str, default='data/raw', 
                       help='Directory to create raw folder (default: data/raw)')
    parser.add_argument('--metadata', type=str, default='data/metadata.csv',
                       help='Path to metadata.csv (default: data/metadata.csv)')
    parser.add_argument('--csv-file', type=str, default='data/attractions_names_list.csv',
                       help='Path to attractions CSV file (default: data/attractions_names_list.csv)')
    
    args = parser.parse_args()
    
    attractions_parser = AttractionsParser(
        csv_file=args.csv_file,
        debug_mode=args.debug,
        output_dir=args.output_dir,
        metadata_file=args.metadata
    )
    attractions_parser.run_extraction()


if __name__ == "__main__":
    main() 