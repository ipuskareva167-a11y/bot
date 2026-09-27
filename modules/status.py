"""Модуль статусов.

Триггер: есть новое сообщение от знакомого пользователя.
Действие: обновить last_seen, message_count и пересчитать статус.
"""
import logging

from modules import bus, db

log = logging.getLogger(__name__)

_processed_total = 0


def _decide(user, config):
    count = user.get("message_count", 0)
    for threshold, status in config.STATUS_TRIGGERS:
        if count >= threshold:
            return status
    return "новичок"


def update(config):
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

        data = db.load(config)
        users = data.get("users", {})
        user = users.get(str(from_id))

        if user is None:
            continue

        user["last_seen"] = msg.get("date_str") or user.get("last_seen")
        user["message_count"] = user.get("message_count", 0) + 1

        old = user.get("status")
        new = _decide(user, config)
        user["status"] = new

        if new != old:
            log.info("Статус %s: %s → %s (%s)",
                     from_id, old, new, user.get("from_name"))
        else:
            log.info("Активность %s: сообщений=%s, статус=%s",
                     from_id, user["message_count"], new)

        db.save(config, data)

    _processed_total = total
