import unittest

from streamlit.testing.v1 import AppTest


class StreamlitAppTests(unittest.TestCase):
    def test_streamlit_app_renders_main_controls(self):
        app = AppTest.from_file("streamlit_app.py")
        app.run(timeout=10)
        self.assertFalse(app.exception)
        self.assertGreaterEqual(len(app.title), 1)
        self.assertGreaterEqual(len(app.text_input), 2)
        self.assertGreaterEqual(len(app.button), 1)


if __name__ == "__main__":
    unittest.main()
