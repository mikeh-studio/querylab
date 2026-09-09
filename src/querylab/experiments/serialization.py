"""JSON display encoding; comparison always uses original database values."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from math import isfinite
from uuid import UUID


def display_json(value):
    if isinstance(value, dict):
        return {str(key): display_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [display_json(item) for item in value]
    if isinstance(value, float) and not isfinite(value):
        return str(value)
    if isinstance(value, (Decimal, date, datetime, time, timedelta, UUID)):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    return value
