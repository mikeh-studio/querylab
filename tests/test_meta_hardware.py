from querylab.exercises.meta_hardware import get_meta_hardware_exercise_set
from querylab.grading.grader import Grader


def test_hardware_questions_execute_on_both_datasets():
    pack = get_meta_hardware_exercise_set()
    grader = Grader()
    for exercise in pack.exercises():
        grade = grader.grade(exercise, exercise.reference_sql)
        assert grade.passed
        assert len(grade.datasets) == 2


def test_hardware_sales_totals_and_boundary_regression():
    pack = get_meta_hardware_exercise_set()
    exercise = pack.exercises()[0]
    grader = Grader()
    result = grader._execute(
        exercise, list(exercise.datasets())[0], exercise.reference_sql
    )
    assert list(result.rows) == [
        ("Ray-Ban Meta", "Retail", 10, 2800),
        ("Ray-Ban Meta", "Online", 8, 2400),
        ("Quest 3", "Online", 4, 2000),
        ("Quest 3S", "Online", 6, 1800),
        ("Quest 3S", "Retail", 5, 1450),
        ("Quest 3", "Retail", 3, 1440),
    ]
    wrong = exercise.reference_sql.replace(
        "s.sale_date < DATE '2025-02-01'", "s.sale_date <= DATE '2025-02-01'"
    )
    assert not grader.grade(exercise, wrong).passed


def test_return_rates_and_net_revenue_are_not_duplicated():
    pack = get_meta_hardware_exercise_set()
    grader = Grader()
    exercise = pack.exercises()[1]
    result = grader._execute(
        exercise, list(exercise.datasets())[0], exercise.reference_sql
    )
    assert list(result.rows) == [
        ("Quest 3", 7, 2, 0.286),
        ("Quest 3S", 11, 1, 0.091),
        ("Ray-Ban Meta", 18, 2, 0.111),
    ]
    exercise = pack.exercises()[2]
    result = grader._execute(
        exercise, list(exercise.datasets())[1], exercise.reference_sql
    )
    assert list(result.rows) == [
        ("Quest 3", "Online", 2350, 875, 1475),
        ("Quest 3S", "Online", 1000, 0, 1000),
        ("Quest 3S", "Retail", 1000, 0, 1000),
        ("Quest accessory", "Retail", 100, 100, 0),
    ]
