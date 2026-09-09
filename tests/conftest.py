from __future__ import annotations

import pytest

from querylab.exercises import get_static_exercise
from querylab.models import Exercise


@pytest.fixture
def exercise() -> Exercise:
    return get_static_exercise()
