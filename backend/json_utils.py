import json
from datetime import datetime
from enum import Enum


def json_default(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def safe_json_dumps(data) -> str:
    return json.dumps(data, indent=2, default=json_default)
