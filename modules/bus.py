"""Общая шина: динамические данные, которые видят все модули."""
import json

messages = []
last = None
total = 0

DUMP_FIELDS = ("from_name", "from_id", "date_str", "text")


def _slim(msg):
    if msg is None:
        return None
    return {k: msg.get(k) for k in DUMP_FIELDS}


def dump(path="bus.json", max_messages=50):
    """Сохранить снимок шины в JSON."""
    if not path:
        return

    snapshot = {
        "total": total,
        "last": _slim(last),
        "messages": [_slim(m) for m in messages[-max_messages:]] if messages else [],
    }

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2, default=str)
    except Exception:
        pass
