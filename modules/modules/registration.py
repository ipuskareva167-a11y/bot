"""Модуль регистрации.

На каждое сообщение от пользователя:
    1. Убедиться, что БД есть (создать, если нет).
    2. Найти пользователя по from_id.
    3. Если нет — занести.
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
        return []

    newbies = []

    for msg in bus.messages[_processed_total:total]:
        from_id = msg.get("from_id")

        # только входящие от пользователей
        if not from_id or from_id <= 0:
            continue
        if msg.get("out"):
            continue

        # --- ШАГ 1: есть ли БД? ---
        db.ensure_db(config)

        # --- ШАГ 2: ищем пользователя по from_id ---
        existing = db.get_user(config, from_id)
        if existing is not None:
            continue

        # --- ШАГ 3: заносим ---
        from_name = msg.get("from_name") or f"id{from_id}"
        date_str = msg.get("date_str") or _now_str()
        db.add_user(config, from_id, from_name, date_str)
        log.info("Зарегистрирован: %s (%s)", from_name, from_id)
        newbies.append({"user_id": from_id, "from_name": from_name})

    _processed_total = total
    return newbies