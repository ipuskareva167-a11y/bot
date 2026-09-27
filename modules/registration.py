"""Модуль регистрации.

Триггер: есть новое сообщение от пользователя, которого нет в БД.
Действие: занести в БД как новичка.
"""
import logging
import time

from modules import bus, db

log = logging.getLogger(__name__)

_processed_total = 0


def _now_str():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def register(config):
    global _processed_total

    total = bus.total
    if total <= _processed_total:
        return

    for msg in bus.messages[_processed_total:total]:
        from_id = msg.get("from_id")

        if not from_id or from_id <= 0:
            continue
        if msg.get("out"):
            continue

        db.ensure(config)
        data = db.load(config)
        users = data.setdefault("users", {})
        key = str(from_id)

        if key in users:
            continue

        from_name = msg.get("from_name") or f"id{from_id}"
        date_str = msg.get("date_str") or _now_str()

        users[key] = {
            "user_id": from_id,
            "from_name": from_name,
            "status": "новичок",
            "first_seen": date_str,
            "last_seen": date_str,
            "message_count": 1,
            "welcomed": False,
        }
        db.save(config, data)
        log.info("Зарегистрирован: %s (%s)", from_name, from_id)

    _processed_total = total
