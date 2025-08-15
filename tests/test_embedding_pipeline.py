import unittest

from  app.retrieval.embedding.generate_embeddings import basic_clean

class TestBasicClean(unittest.TestCase):

    def test_none_input(self):
        self.assertEqual(basic_clean(None), "")

    def test_empty_string(self):
        self.assertEqual(basic_clean(""), "")

    def test_whitespace_only(self):
        self.assertEqual(basic_clean("   \t   \n  "), "")

    def test_remove_control_chars(self):
        self.assertEqual(basic_clean("Hello\x00World"), "HelloWorld")
        self.assertEqual(basic_clean("Hi\x1FThere"), "HiThere")

    def test_remove_empty_section_titles(self):
        self.assertEqual(basic_clean("==Title== "), "")
        self.assertEqual(basic_clean("==Title==\n"), "")
        self.assertEqual(basic_clean("==Title==\r\nNext"), "Next")
        self.assertEqual(basic_clean("Some text ==Title== "), "Some text")

    def test_collapse_multiple_spaces(self):
        self.assertEqual(basic_clean("Hello    world"), "Hello world")
        self.assertEqual(basic_clean("Hello \n world"), "Hello world")
        self.assertEqual(basic_clean("Hello\t\tworld"), "Hello world")

    def test_preserve_special_chars(self):
        text = "Café €10 🙂"
        self.assertEqual(basic_clean(text), text)

    def test_mixed_control_and_spaces(self):
        self.assertEqual(
            basic_clean("Hello \x00   \n   World"),
            "Hello World"
        )

    def test_idempotent_on_clean_input(self):
        clean_text = "This is fine."
        self.assertEqual(basic_clean(clean_text), clean_text)

if __name__ == "__main__":
    unittest.main()
