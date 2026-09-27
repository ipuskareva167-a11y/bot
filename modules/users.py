"""Модуль пользователей."""
import logging
import time

from modules import bus, db, vk

log = logging.getLogger(__name__)

WELCOME_TEXT = "Привет, {name}! Я бот. Чем могу помочь?"

_processed_total = 0


def _now_str():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _handle(config, msg):
    from_id = msg.get("from_id")
    if not from_id or from_id <= 0:
        return
    if msg.get("out"):
        return

    date_str = msg.get("date_str") or _now_str()
    from_name = msg.get("from_name") or f"id{from_id}"
    peer_id = msg.get("peer_id")

    if db.get_user(from_id) is None:
        db.add_user(from_id, from_name, date_str)
        log.info("Новый пользователь: %s (%s)", from_name, from_id)
        vk.send_message(config, peer_id, WELCOME_TEXT.format(name=from_name))
    else:
        db.touch_user(from_id, from_name, date_str)


def step(config):
    global _processed_total
    total = bus.total
    if total <= _processed_total:
        return
    for msg in bus.messages[_processed_total:total]:
        _handle(config, msg)
    _processed_total = total