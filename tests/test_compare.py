from __future__ import annotations

from decimal import Decimal

import pytest

from querylab.engines.base import QueryResult
from querylab.grading.compare import compare_results
from querylab.models import GradingConfig


def result(columns: tuple[str, ...], *rows: tuple[object, ...]) -> QueryResult:
    return QueryResult(columns=columns, rows=rows, duration_ms=0)


def test_row_order_is_ignored_when_not_required() -> None:
    expected = result(("id",), (1,), (2,), (2,))
    actual = result(("id",), (2,), (1,), (2,))

    comparison = compare_results(expected, actual, GradingConfig(order_matters=False))

    assert comparison.passed


def test_row_order_fails_when_required() -> None:
    expected = result(("id",), (1,), (2,))
    actual = result(("id",), (2,), (1,))

    comparison = compare_results(expected, actual, GradingConfig(order_matters=True))

    assert not comparison.passed
    assert comparison.differing_rows == 2


def test_nulls_compare_deterministically() -> None:
    expected = result(("value",), (None,), ("x",))

    assert compare_results(expected, expected, GradingConfig()).passed
    assert not compare_results(
        expected,
        result(("value",), (0,), ("x",)),
        GradingConfig(),
    ).passed


def test_numeric_tolerance_is_applied_to_values() -> None:
    expected = result(("rate",), (0.031,))
    close = result(("rate",), (0.0310004,))
    far = result(("rate",), (0.03101,))
    config = GradingConfig(numeric_tolerance=0.000001)

    assert compare_results(expected, close, config).passed
    assert not compare_results(expected, far, config).passed


def test_column_names_are_part_of_the_contract() -> None:
    expected = result(("conversion_rate",), (0.031,))
    actual = result(("rate",), (0.031,))

    comparison = compare_results(expected, actual, GradingConfig())

    assert not comparison.passed
    assert not comparison.columns_match


@pytest.mark.parametrize("order", [False, True])
@pytest.mark.parametrize(
    "expected,actual,tolerance,passed",
    [
        (True, 1, 0, False),
        (0, False, 0, False),
        (True, True, 0, True),
        (2**53, 2**53 + 1, 0, False),
        (2**53 + 1, float(2**53), 0, False),
        (2**53, Decimal(2**53), 0, True),
        (
            Decimal("123456789012345678901234567890.01"),
            Decimal("123456789012345678901234567890.02"),
            0.001,
            False,
        ),
        (
            Decimal("123456789012345678901234567890.01"),
            Decimal("123456789012345678901234567890.02"),
            0.02,
            True,
        ),
        (float("nan"), float("nan"), 0, True),
        (float("inf"), float("inf"), 0, True),
        (float("inf"), float("-inf"), 0, False),
        (10**400, float("inf"), 0, False),
    ],
)
def test_numeric_types_and_precision(expected, actual, tolerance, passed, order):
    comparison = compare_results(
        result(("v",), (expected,)),
        result(("v",), (actual,)),
        GradingConfig(order_matters=order, numeric_tolerance=tolerance),
    )
    assert comparison.passed is passed
