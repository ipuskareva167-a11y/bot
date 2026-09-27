"""HR-модуль.

Триггер: есть пользователь с welcomed=False.
Действие: отправить приветствие с клавиатурой из двух кнопок.
"""
import json
import logging

from modules import bus, db, vk

log = logging.getLogger(__name__)

_processed_total = 0

WELCOME_TEXT = (
    "Здравствуйте, {name}!\n\n"
    "Мы — компания X, ищем сотрудника на вакансию «Менеджер».\n"
    "Коротко: удалёнка, гибкий график, обучение.\n\n"
    "Что вам интересно?"
)


def _keyboard():
    return {
        "one_time": False,
        "buttons": [
            [
                {
                    "action": {
                        "type": "text",
                        "label": "Отправить анкету",
                        "payload": json.dumps({"cmd": "anketa"}),
                    },
                    "color": "primary",
                },
                {
                    "action": {
                        "type": "text",
                        "label": "Подробнее о вакансии",
                        "payload": json.dumps({"cmd": "details"}),
                    },
                    "color": "secondary",
                },
            ]
        ],
    }


def greet(config):
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
        if user.get("welcomed"):
            continue

        text = WELCOME_TEXT.format(name=user.get("from_name", "друг"))
        vk.send_message(config, msg.get("peer_id"), text, keyboard=_keyboard())

        user["welcomed"] = True
        db.save(config, data)
        log.info("HR: приветствие отправлено %s (%s)",
                 user.get("from_name"), from_id)

    _processed_total = total
