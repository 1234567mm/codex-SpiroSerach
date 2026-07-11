import unittest

from spirosearch.surrogate import SklearnSurrogate, UnsupportedSurrogateError


class SklearnSurrogateTests(unittest.TestCase):
    def test_fit_returns_valid_state_and_predictive_uncertainty(self):
        model = SklearnSurrogate(random_seed=7)
        result = model.fit(
            [{"x": 0.0}, {"x": 1.0}, {"x": 2.0}, {"x": 3.0}],
            [1.0, 3.0, 5.0, 7.0],
        )

        self.assertEqual(result.state.surrogate_type, "SKLEARN_GPR")
        self.assertEqual(result.state.posterior_version, 1)
        self.assertEqual(len(model.predict([{"x": 1.5}])), 1)
        self.assertGreater(model.uncertainty([{"x": 1.5}])[0], 0.0)

    def test_fit_rejects_mismatched_lengths(self):
        with self.assertRaisesRegex(ValueError, "same length"):
            SklearnSurrogate().fit([{"x": 0.0}, {"x": 1.0}], [1.0])

    def test_unknown_acquisition_fails_closed(self):
        model = SklearnSurrogate()
        with self.assertRaises(UnsupportedSurrogateError):
            model.acquisition([], "typo")


if __name__ == "__main__":
    unittest.main()
