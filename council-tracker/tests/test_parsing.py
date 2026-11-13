"""
Regression tests for the two trickiest parsing rules in the pipeline --
both derived from patterns actually observed in the real downloaded
files (see docs/data_dictionary.md), not guessed.
"""
import pytest

from src.pipeline.load_report_request_log import _split_closed_by
from src.pipeline.load_voting_record import parse_result


@pytest.mark.parametrize(
    "result_raw,expected_outcome,expected_tie,expected_yes,expected_no",
    [
        ("Carried, 25-1", "carried", False, 25, 1),
        ("Not Carried, 10-15", "not_carried", False, 10, 15),
        ("Lost (tie), 11-11", "not_carried", True, 11, 11),
        ("Carried", "carried", False, None, None),
        ("Lost", "not_carried", False, None, None),
    ],
)
def test_parse_result(result_raw, expected_outcome, expected_tie, expected_yes, expected_no):
    parsed = parse_result(result_raw)
    assert parsed["outcome"] == expected_outcome
    assert parsed["is_tie"] == expected_tie
    assert parsed["yes_count"] == expected_yes
    assert parsed["no_count"] == expected_no


def test_parse_result_rejects_unknown_format():
    with pytest.raises(ValueError):
        parse_result("Something unexpected, 1-2-3")


def test_split_closed_by_single_item_id():
    date, item_ids = _split_closed_by("2023.PH2.10")
    assert date is None
    assert item_ids == ["2023.PH2.10"]


def test_split_closed_by_multiple_item_ids():
    date, item_ids = _split_closed_by("2023.EX3.1 \n2023.PH4.7\n2023.PH5.5")
    assert date is None
    assert item_ids == ["2023.EX3.1", "2023.PH4.7", "2023.PH5.5"]


def test_split_closed_by_date_string():
    date, item_ids = _split_closed_by("2023-02-23 00:00:00")
    assert item_ids == []
    assert date is not None
