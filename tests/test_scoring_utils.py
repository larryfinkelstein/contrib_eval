import unittest
from scoring.utils import compute_weighted_score, load_weights

class TestScoringUtils(unittest.TestCase):
    def test_compute_weighted_score_simple(self):
        metrics = {'involvement': 2, 'significance': 3}
        weights = {'involvement': 1.0, 'significance': 2.0}
        score = compute_weighted_score(metrics, weights)
        self.assertEqual(score, 2*1.0 + 3*2.0)

    def test_load_weights_defaults(self):
        weights = load_weights(path=None)
        # ensure default keys exist
        for k in ('involvement','significance','effectiveness','complexity'):
            self.assertIn(k, weights)

if __name__ == '__main__':
    unittest.main()

