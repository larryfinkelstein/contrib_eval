import unittest
from correlate.models import EvaluationResult
from report.renderer import render, render_html, render_markdown, render_csv

class TestRenderer(unittest.TestCase):
    def test_markdown_and_csv(self):
        r = EvaluationResult(3, 4.5, 0.8, 2.0, 5.5, 1)
        md = render_markdown(r)
        self.assertIn('Contribution Summary', md)
        csv = render_csv(r)
        self.assertIn('involvement,significance', csv)

    def test_render_html_fallback(self):
        r = EvaluationResult(1,1,1,1,1,0)
        html = render_html(r, metrics={'a':1})
        self.assertIsInstance(html, str)
        self.assertIn('Contribution Summary', html)

    def test_render_helper(self):
        r = EvaluationResult(0,0,0,0,0,0)
        self.assertIsInstance(render(r, fmt='text'), str)
        self.assertIsInstance(render(r, fmt='md'), str)
        self.assertIsInstance(render(r, fmt='csv'), str)
        self.assertIsInstance(render(r, fmt='html'), str)

if __name__ == '__main__':
    unittest.main()

