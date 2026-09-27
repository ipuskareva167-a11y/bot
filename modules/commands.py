"""Модуль команд.

Триггер: в сообщении есть payload от нажатой кнопки.
Действие: разобрать команду и ответить.
"""
import json
import logging

from modules import bus, vk

log = logging.getLogger(__name__)

_processed_total = 0


def handle(config):
    global _processed_total

    total = bus.total
    if total <= _processed_total:
        return

    for msg in bus.messages[_processed_total:total]:
        payload_raw = msg.get("payload")
        if not payload_raw:
            continue

        try:
            payload = json.loads(payload_raw)
        except (TypeError, ValueError):
            continue

        cmd = payload.get("cmd")
        peer_id = msg.get("peer_id")
        from_name = msg.get("from_name") or "друг"

        if cmd == "anketa":
            vk.send_message(config, peer_id,
                            f"{from_name}, вот ссылка на анкету: example.com/anketa")
            log.info("commands: anketa → %s", from_name)

        elif cmd == "details":
            vk.send_message(config, peer_id,
                            "Подробнее о вакансии: удалёнка, гибкий график, "
                            "обучение за счёт компании, зарплата по итогам собеседования.")
            log.info("commands: details → %s", from_name)

        else:
            log.warning("commands: неизвестная команда %s", cmd)

    _processed_total = total
