"""
Unit tests for text cleaning and filtering routines.
Tests the regex patterns and edge cases in the attractions parser.
"""

import unittest
import sys
import os
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from app.retrieval.parsing.attractions_wiki_parser import AttractionsParser, LatinTextFilter


class TestLatinTextFilter(unittest.TestCase):
    """Test the LatinTextFilter class and its text filtering capabilities."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.filter = LatinTextFilter()
    
    def test_is_latin_word_basic(self):
        """Test basic Latin word detection."""
        # Valid Latin words
        self.assertTrue(self.filter.is_latin_word("hello"))
        self.assertTrue(self.filter.is_latin_word("world"))
        self.assertTrue(self.filter.is_latin_word("café"))
        self.assertTrue(self.filter.is_latin_word("naïve"))
        self.assertTrue(self.filter.is_latin_word("123"))
        self.assertTrue(self.filter.is_latin_word("hello-world"))
        
        # Non-Latin words
        self.assertFalse(self.filter.is_latin_word("привіт"))
        self.assertFalse(self.filter.is_latin_word("你好"))
        self.assertFalse(self.filter.is_latin_word("مرحبا"))
        self.assertFalse(self.filter.is_latin_word("こんにちは"))
    
    def test_is_latin_word_edge_cases(self):
        """Test edge cases for Latin word detection."""
        # Empty and whitespace
        self.assertTrue(self.filter.is_latin_word(""))
        self.assertTrue(self.filter.is_latin_word("   "))
        self.assertTrue(self.filter.is_latin_word("\n\t"))
        
        # Punctuation only
        self.assertTrue(self.filter.is_latin_word(".,;:!?"))
        self.assertTrue(self.filter.is_latin_word("()[]{}"))
        
        # Mixed content
        self.assertTrue(self.filter.is_latin_word("hello123"))
        self.assertTrue(self.filter.is_latin_word("test@example.com"))
        self.assertTrue(self.filter.is_latin_word("price: $100"))
    
    def test_contains_latin_script(self):
        """Test Latin script detection."""
        # Text with Latin script
        self.assertTrue(self.filter.contains_latin_script("Hello world"))
        self.assertTrue(self.filter.contains_latin_script("123 numbers"))
        self.assertTrue(self.filter.contains_latin_script("Mixed текст text"))
        
        # Text without Latin script - but numbers are considered Latin
        self.assertFalse(self.filter.contains_latin_script("привіт світ") )  # Numbers are in Latin blocks
        self.assertFalse(self.filter.contains_latin_script("你好世界"))  # Numbers are in Latin blocks
        self.assertFalse(self.filter.contains_latin_script("مرحبا بالعالم"))  # Numbers are in Latin blocks
    
    def test_analyze_word_scripts(self):
        """Test script analysis in words."""
        # Pure Latin
        scripts = self.filter.analyze_word_scripts("hello")
        self.assertIn('Latin', scripts)
        self.assertEqual(len(scripts), 1)
        
        # Mixed scripts
        scripts = self.filter.analyze_word_scripts("helloпривіт")
        self.assertIn('Latin', scripts)
        self.assertIn('Cyrillic', scripts)
        
        # Numbers and punctuation
        scripts = self.filter.analyze_word_scripts("123!@#")
        self.assertEqual(len(scripts), 0)  # Numbers/punctuation don't have scripts
    
    def test_remove_non_latin_words_basic(self):
        """Test basic non-Latin word removal."""
        text = "Hello world привіт світ"
        result = self.filter.remove_non_latin_words(text)
        self.assertEqual(result, "Hello world")
        
        text = "Test 123 тест 456"
        result = self.filter.remove_non_latin_words(text)
        self.assertEqual(result, "Test 123 456")
    
    def test_remove_non_latin_words_preserve_mixed(self):
        """Test non-Latin word removal with mixed word preservation."""
        text = "Hello world привітworld"
        result = self.filter.remove_non_latin_words(text, preserve_mixed=True)
        self.assertEqual(result, "Hello world привітworld")  # Mixed word preserved
        
        text = "Hello world привіт"
        result = self.filter.remove_non_latin_words(text, preserve_mixed=True)
        self.assertEqual(result, "Hello world")  # Pure non-Latin word removed
    
    def test_clean_text_aggressive(self):
        """Test aggressive text cleaning."""
        text = "Hello world привіт світ 123!@#"
        result = self.filter.clean_text_aggressive(text)
        self.assertEqual(result, "Hello world 123!@#")  # Non-Latin removed
    
    def test_clean_text_aggressive_edge_cases(self):
        """Test aggressive cleaning with edge cases."""
        # Empty text
        self.assertEqual(self.filter.clean_text_aggressive(""), "")
        self.assertEqual(self.filter.clean_text_aggressive(None), None)
        
        # Only non-Latin
        self.assertEqual(self.filter.clean_text_aggressive("привіт світ"), "")
        
        # Mixed with special characters
        text = "Hello привіт!@#$%^&*()"
        result = self.filter.clean_text_aggressive(text)
        self.assertIn("Hello", result)
        self.assertIn("!@#$%^&*()", result)
        self.assertNotIn("привіт", result)


class TestAttractionsParserCleaning(unittest.TestCase):
    """Test the text cleaning methods in AttractionsParser."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = AttractionsParser()
    
    def test_remove_see_also_section(self):
        """Test removal of 'See also' sections."""
        text = """
        Some content here.
        
        == See also ==
        * Link 1
        * Link 2
        
        More content.
        """
        result = self.parser._remove_see_also_section(text)
        self.assertNotIn("== See also ==", result)
        self.assertNotIn("Link 1", result)
        self.assertIn("Some content here", result)
        self.assertIn("More content", result)
    
    def test_remove_see_also_case_insensitive(self):
        """Test case-insensitive removal of 'See also' sections."""
        text = """
        Content.
        
        == SEE ALSO ==
        * Link
        
        More content.
        """
        result = self.parser._remove_see_also_section(text)
        self.assertNotIn("== SEE ALSO ==", result)
        self.assertIn("Content", result)
        self.assertIn("More content", result)
    
    def test_remove_gallery_tags(self):
        """Test removal of gallery tags."""
        text = """
        Some content.
        
        <gallery>
        Image1.jpg
        Image2.jpg
        </gallery>
        
        More content.
        """
        result = self.parser._remove_gallery_tags(text)
        self.assertNotIn("<gallery>", result)
        self.assertNotIn("Image1.jpg", result)
        self.assertIn("Some content", result)
        self.assertIn("More content", result)
    
    def test_remove_gallery_tags_with_attributes(self):
        """Test removal of gallery tags with attributes."""
        text = """
        Content.
        
        <gallery caption="My Gallery">
        Image1.jpg
        Image2.jpg
        </gallery>
        
        More content.
        """
        result = self.parser._remove_gallery_tags(text)
        self.assertNotIn("<gallery", result)
        self.assertNotIn("caption=", result)
        self.assertIn("Content", result)
        self.assertIn("More content", result)
    
    def test_remove_language_template_parentheses(self):
        """Test removal of parentheses with language templates."""
        test_cases = [
            ("Hello ({{lang|en|world}}) there", "Hello  there"),
            ("Text ({{langx|uk|текст}}) more", "Text  more"),
            ("Content ({{Transliteration|text}}) end", "Content  end"),
            ("No templates here", "No templates here"),  # No change
            ("Mixed ({{lang|en|hello}}) and ({{langx|uk|привіт}})", "Mixed  and "),
        ]
        
        for input_text, expected in test_cases:
            with self.subTest(input_text=input_text):
                result = self.parser._remove_language_template_parentheses(input_text)
                self.assertEqual(result, expected)
    
    def test_remove_empty_parentheses(self):
        """Test removal of empty parentheses."""
        test_cases = [
            ("Hello () world", "Hello  world"),
            ("Text (,) more", "Text  more"),
            ("Content (;) end", "Content  end"),
            ("Mixed (,) and (;) here", "Mixed  and  here"),
            ("No empty () here", "No empty  here"),
            ("Normal (content) here", "Normal (content) here"),  # Should not change
        ]
        
        for input_text, expected in test_cases:
            with self.subTest(input_text=input_text):
                result = self.parser._remove_empty_parentheses(input_text)
                self.assertEqual(result, expected)
    
    def test_remove_template_parentheses(self):
        """Test removal of parentheses with template remnants."""
        test_cases = [
            ("Hello ({{template|param}}) there", "Hello  there"),
            ("Text ({{convert|100|m}}) more", "Text  more"),
            ("Mixed ({{lang|en|hello}}, {{convert|50|ft}})", "Mixed "),
            ("Normal (content) here", "Normal (content) here"),  # Should not change
        ]
        
        for input_text, expected in test_cases:
            with self.subTest(input_text=input_text):
                result = self.parser._remove_template_parentheses(input_text)
                self.assertEqual(result, expected)
    
    def test_cleanup_remaining_parentheses(self):
        """Test cleanup of remaining empty parentheses."""
        test_cases = [
            ("Hello ({{}} ) there", "Hello  there"),
            ("Text ({{template}} ) more", "Text  more"),
            ("Mixed ({{}}, {{}} ) here", "Mixed  here"),
            ("Normal (content) here", "Normal (content) here"),  # Should not change
        ]
        
        for input_text, expected in test_cases:
            with self.subTest(input_text=input_text):
                result = self.parser._cleanup_remaining_parentheses(input_text)
                self.assertEqual(result, expected)
    
    def test_cleanup_excessive_quotes(self):
        """Test cleanup of excessive quotes."""
        test_cases = [
            ("'''bold''' text", "'bold' text"),
            ("''italic'' text", "'italic' text"),
            ("'''bold''' and ''italic''", "'bold' and 'italic'"),
            ("Normal text", "Normal text"),  # No change
            ("[['''link''']]", "['link']"),
        ]
        
        for input_text, expected in test_cases:
            with self.subTest(input_text=input_text):
                result = self.parser._cleanup_excessive_quotes(input_text)
                self.assertEqual(result, expected)
    
    def test_remove_list_markers(self):
        """Test removal of list markers."""
        text = """
        * Item 1
        ** Sub-item 1
        *** Sub-sub-item
        ** Sub-item 2
        * Item 2
        """
        result = self.parser._remove_list_markers(text)
        self.assertNotIn("* Item 1", result)
        self.assertNotIn("** Sub-item 1", result)
        self.assertNotIn("*** Sub-sub-item", result)
        self.assertIn("Item 1", result)
        self.assertIn("Sub-item 1", result)
    
    def test_cleanup_whitespace(self):
        """Test whitespace cleanup."""
        text = "Multiple    spaces    here.\n\n\nMultiple\n\n\nnewlines."
        result = self.parser._cleanup_whitespace(text)
        self.assertNotIn("    ", result)  # No multiple spaces
        self.assertIn("Multiple spaces here", result)
    
    def test_apply_text_cleaning_regex_comprehensive(self):
        """Test the comprehensive text cleaning method."""
        text = """
        == See also ==
        * Link 1
        * Link 2
        
        <gallery>
        Image1.jpg
        </gallery>
        
        Hello ({{lang|en|world}}) there.
        
        '''Bold''' and ''italic'' text.
        
        * List item
        ** Sub-item
        
        Multiple    spaces.
        """
        
        result = self.parser._apply_text_cleaning_regex(text)
        
        # Check that all cleaning operations were applied
        self.assertNotIn("== See also ==", result)
        self.assertNotIn("<gallery>", result)
        self.assertNotIn("({{lang|en|world}})", result)
        self.assertNotIn("'''Bold'''", result)
        self.assertNotIn("* List item", result)
        self.assertNotIn("    ", result)  # No multiple spaces
        
        # Check that content is preserved
        self.assertIn("Hello", result)
        self.assertIn("there", result)
        self.assertIn("Bold", result)
        self.assertIn("italic", result)
        self.assertIn("List item", result)
        self.assertIn("Sub-item", result)


class TestTextCleaningEdgeCases(unittest.TestCase):
    """Test edge cases and complex scenarios in text cleaning."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = AttractionsParser()
    
    def test_nested_templates(self):
        """Test cleaning with nested templates."""
        text = "Text ({{convert|{{lang|en|100}}|m}}) here"
        result = self.parser._apply_text_cleaning_regex(text)
        self.assertNotIn("({{convert|", result)
        self.assertIn("Text", result)
        self.assertIn("here", result)
    
    def test_multiple_galleries(self):
        """Test multiple gallery tags."""
        text = """
        <gallery>
        Image1.jpg
        </gallery>
        
        Content.
        
        <gallery caption="Second">
        Image2.jpg
        </gallery>
        """
        result = self.parser._remove_gallery_tags(text)
        self.assertNotIn("<gallery>", result)
        self.assertNotIn("<gallery caption=", result)
        self.assertIn("Content", result)
    
    def test_mixed_quotes_and_brackets(self):
        """Test complex quote and bracket combinations."""
        text = "[['''Bold link''']] and [[''Italic link'']]"
        result = self.parser._cleanup_excessive_quotes(text)
        self.assertIn("['Bold link']", result)
        self.assertIn("['Italic link']", result)
    
    def test_empty_inputs(self):
        """Test handling of empty inputs."""
        empty_inputs = ["", None, "   ", "\n\n\n"]
        
        for empty_input in empty_inputs:
            with self.subTest(empty_input=empty_input):
                if empty_input is not None:
                    result = self.parser._apply_text_cleaning_regex(empty_input)
                    self.assertIsInstance(result, str)
    
    def test_unicode_edge_cases(self):
        """Test Unicode edge cases."""
        text = "Hello привіт 你好 مرحبا こんにちは"
        result = self.parser._apply_text_cleaning_regex(text)
        self.assertIn("Hello", result)
        # Non-Latin characters should be filtered out if Latin filtering is enabled
        # This depends on the parser's configuration
    
    def test_template_edge_cases(self):
        """Test edge cases with templates."""
        test_cases = [
            ("({{}})", ""),  # Empty template
            ("({{template}})", ""),  # Template without params
            ("({{template|}})", ""),  # Template with empty param
            ("({{template|param1|param2}})", ""),  # Multiple params
        ]
        
        for input_text, expected in test_cases:
            with self.subTest(input_text=input_text):
                result = self.parser._remove_template_parentheses(input_text)
                self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main() 