import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "naver_order_crawler.py"
SPEC = importlib.util.spec_from_file_location("naver_order_crawler", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
split_date_ranges = MODULE.split_date_ranges


class SplitDateRangesTest(unittest.TestCase):
    def test_one_month_creates_twelve_calendar_months(self) -> None:
        ranges = split_date_ranges("20210101", "20211231", 1)

        self.assertEqual(len(ranges), 12)
        self.assertEqual(ranges[0], ("20210101", "20210131"))
        self.assertEqual(ranges[1], ("20210201", "20210228"))
        self.assertEqual(ranges[-1], ("20211201", "20211231"))

    def test_three_months_creates_four_ranges(self) -> None:
        ranges = split_date_ranges("20210101", "20211231", 3)

        self.assertEqual(
            ranges,
            [
                ("20210101", "20210331"),
                ("20210401", "20210630"),
                ("20210701", "20210930"),
                ("20211001", "20211231"),
            ],
        )

    def test_partial_ranges_do_not_exceed_original_range(self) -> None:
        ranges = split_date_ranges("20210115", "20210510", 2)

        self.assertEqual(ranges[0][0], "20210115")
        self.assertEqual(ranges[-1][1], "20210510")
        self.assertTrue(all(start >= "20210115" for start, _ in ranges))
        self.assertTrue(all(end <= "20210510" for _, end in ranges))


if __name__ == "__main__":
    unittest.main()
