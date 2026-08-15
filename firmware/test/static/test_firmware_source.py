from __future__ import annotations

import unittest
from pathlib import Path


FIRMWARE_ROOT = Path(__file__).resolve().parents[2]


class FirmwareSourceRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.display_source = (FIRMWARE_ROOT / "src" / "display.cpp").read_text(
            encoding="utf-8"
        )

    def test_humidity_unit_prints_exactly_one_percent_character(self) -> None:
        self.assertIn('M5.Lcd.print("%")', self.display_source)
        self.assertNotIn('M5.Lcd.print("%%")', self.display_source)

    def test_instant_pm25_is_not_presented_as_an_aqi_health_category(self) -> None:
        self.assertNotIn("air_quality_label", self.display_source)
        for misleading_label in (
            "GOOD",
            "MODERATE",
            "ELEVATED",
            "UNHEALTHY",
            "HAZARDOUS",
        ):
            self.assertNotIn(f'"{misleading_label}"', self.display_source)


if __name__ == "__main__":
    unittest.main()
