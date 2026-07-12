import unittest
from pathlib import Path


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "custom_htl_pilot"


class CustomHtlOrcaParserTests(unittest.TestCase):
    def test_parser_extracts_successful_orca_result(self) -> None:
        from scripts.custom_htl.parse_orca_outputs import parse_orca_output

        result = parse_orca_output(
            FIXTURE_DIR / "orca_success.out",
            calculation_id="calc-1",
            input_sha256="a" * 64,
        )

        self.assertEqual(result["calculation_id"], "calc-1")
        self.assertTrue(result["converged"])
        self.assertEqual(result["properties"]["homo_ev"], -5.987)
        self.assertEqual(result["properties"]["lumo_ev"], -2.449)
        self.assertEqual(result["properties"]["band_gap_ev"], 3.537)
        self.assertEqual(result["warnings"], [])

    def test_parser_fails_closed_on_scf_failure(self) -> None:
        from scripts.custom_htl.parse_orca_outputs import parse_orca_output

        result = parse_orca_output(
            FIXTURE_DIR / "orca_scf_failure.out",
            calculation_id="calc-fail",
            input_sha256="b" * 64,
        )

        self.assertFalse(result["converged"])
        self.assertIn("scf_not_converged", result["warnings"])
        self.assertEqual(result["properties"], {})

    def test_parser_flags_imaginary_frequency(self) -> None:
        from scripts.custom_htl.parse_orca_outputs import parse_orca_output

        result = parse_orca_output(
            FIXTURE_DIR / "orca_imaginary_frequency.out",
            calculation_id="calc-imag",
            input_sha256="c" * 64,
        )

        self.assertTrue(result["converged"])
        self.assertIn("imaginary_frequency", result["warnings"])


if __name__ == "__main__":
    unittest.main()
