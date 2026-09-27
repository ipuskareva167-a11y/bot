"""Разворачивает проект: создаёт все файлы с нуля.

Запусти:  python setup.py
"""
import os

FILES = {}

FILES["config.py"] = '''"""Настройки проекта. Секреты — из .env."""
import os
from dotenv import load_dotenv

load_dotenv()

VK_TOKEN = os.getenv("VK_TOKEN")
if not VK_TOKEN:
    raise RuntimeError("VK_TOKEN не задан. Проверь файл .env")

_vk_group_raw = os.getenv("VK_GROUP_ID", "").strip()
VK_GROUP_ID = int(_vk_group_raw) if _vk_group_raw else None

POLL_WAIT = 25
RESOLVE_NAMES = True

BUS_FILE = "bus.json"
BUS_MAX_MESSAGES = 50
DB_FILE = "bot.db.json"

STATUS_TRIGGERS = [
    (20, "постоянный"),
    (5,  "активный"),
    (2,  "знакомый"),
    (1,  "новичок"),
]
'''

FILES["modules/__init__.py"] = "# modules package\\n"

FILES["modules/bus.py"] = '''"""Общая шина: динамические данные, которые видят все модули."""
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
'''

FILES["modules/db.py"] = '''"""БД — статическая шина. JSON-файл. Только хранит."""
import json
import logging
import os

log = logging.getLogger(__name__)

_loaded = False


def _path(config):
    return getattr(config, "DB_FILE", "bot.db.json")


def ensure(config):
    """Есть ли БД? Нет — создать. Возвращает True, если только что создали."""
    global _loaded

    if _loaded:
        return False

    path = _path(config)

    if os.path.exists(path):
        log.info("БД найдена: %s", path)
        _loaded = True
        return False

    with open(path, "w", encoding="utf-8") as f:
        json.dump({"users": {}}, f, ensure_ascii=False, indent=2)

    log.info("БД не найдена — создана: %s", path)
    _loaded = True
    return True


def load(config):
    """Прочитать содержимое БД."""
    ensure(config)
    with open(_path(config), "r", encoding="utf-8") as f:
        return json.load(f)


def save(config, data):
    """Записать содержимое БД."""
    with open(_path(config), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
'''

FILES["modules/vk.py"] = '''"""VK-модуль. Читает LongPoll и кладёт сообщения в bus."""
import json
import logging
import time
import requests

from modules import bus

log = logging.getLogger(__name__)

API_VERSION = "5.199"
API_URL = "https://api.vk.com/method/"

_session = requests.Session()

_state = {"server": None, "key": None, "ts": None}
_names_cache = {}


def _call(config, method, **params):
    params.update(access_token=config.VK_TOKEN, v=API_VERSION)
    data = _session.get(API_URL + method, params=params, timeout=15).json()
    if "error" in data:
        raise RuntimeError(f"VK API error: {data['error']}")
    return data["response"]


def _init_longpoll(config):
    if config.VK_GROUP_ID:
        d = _call(config, "groups.getLongPollServer", group_id=config.VK_GROUP_ID)
    else:
        d = _call(config, "messages.getLongPollServer", need_pts=1, lp_version=3)
    _state["server"] = d["server"]
    _state["key"] = d["key"]
    _state["ts"] = d["ts"]
    log.info("VK LongPoll инициализирован")


def _resolve_name(config, user_id):
    if user_id in _names_cache:
        return _names_cache[user_id]
    try:
        result = _call(config, "users.get", user_ids=user_id)
        if result:
            u = result[0]
            name = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
            _names_cache[user_id] = name
            return name
    except Exception as e:
        log.warning("Не удалось получить имя для %s: %s", user_id, e)
    _names_cache[user_id] = None
    return None


def _format_message(config, obj):
    from_id = obj.get("from_id")
    date = obj.get("date")

    date_str = None
    if date:
        date_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(date))

    from_name = None
    if config.RESOLVE_NAMES and from_id and from_id > 0:
        from_name = _resolve_name(config, from_id)

    return {
        "id": obj.get("id"),
        "peer_id": obj.get("peer_id"),
        "from_id": from_id,
        "from_name": from_name,
        "text": obj.get("text", ""),
        "attachments": obj.get("attachments", []),
        "reply_message": obj.get("reply_message"),
        "fwd_messages": obj.get("fwd_messages", []),
        "payload": obj.get("payload"),
        "geo": obj.get("geo"),
        "date": date,
        "date_str": date_str,
        "out": obj.get("out", 0),
    }


def _parse_updates(config, updates):
    out = []
    for u in updates:
        utype = u.get("type")
        obj = u.get("object", {})
        if utype == "message_new":
            if "message" in obj:
                obj = obj["message"]
        else:
            continue
        out.append(_format_message(config, obj))
    return out


def step(config):
    """Один шаг: спросить VK, есть ли новое, и положить в bus."""
    if _state["ts"] is None:
        _init_longpoll(config)

    data = _session.get(_state["server"], params={
        "act": "a_check",
        "key": _state["key"],
        "ts": _state["ts"],
        "wait": config.POLL_WAIT,
        "mode": 2,
    }, timeout=config.POLL_WAIT + 10).json()

    if "failed" in data:
        if data["failed"] == 1:
            _state["ts"] = data["ts"]
        else:
            _init_longpoll(config)
        return

    _state["ts"] = data["ts"]

    for msg in _parse_updates(config, data.get("updates", [])):
        bus.messages.append(msg)
        bus.last = msg
        bus.total += 1
        log.info("VK: новое сообщение от %s (%s): %s",
                 msg["from_name"], msg["from_id"], msg["text"])


def send_message(config, peer_id, text, keyboard=None):
    """Отправить сообщение. keyboard — dict или None."""
    params = {
        "peer_id": peer_id,
        "message": text,
        "random_id": 0,
    }
    if keyboard is not None:
        params["keyboard"] = json.dumps(keyboard, ensure_ascii=False)

    try:
        _call(config, "messages.send", **params)
        log.info("VK: отправлено в %s: %s", peer_id, text[:60])
        return True
    except Exception as e:
        log.error("VK: не удалось отправить: %s", e)
        return False
'''

FILES["modules/registration.py"] = '''"""Модуль регистрации.

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
'''

FILES["modules/hr.py"] = '''"""HR-модуль.

Триггер: есть пользователь с welcomed=False.
Действие: отправить приветствие с клавиатурой из двух кнопок.
"""
import json
import logging

from modules import bus, db, vk

log = logging.getLogger(__name__)

_processed_total = 0

WELCOME_TEXT = (
    "Здравствуйте, {name}!\\n\\n"
    "Мы — компания X, ищем сотрудника на вакансию «Менеджер».\\n"
    "Коротко: удалёнка, гибкий график, обучение.\\n\\n"
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
'''

FILES["modules/status.py"] = '''"""Модуль статусов.

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
'''

FILES["modules/commands.py"] = '''"""Модуль команд.

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
'''

FILES["orchestrator.py"] = '''"""Оркестратор — дёргает модули. Каждый сам решает, работать или нет."""
from modules import vk, commands, registration, hr, status


def step(config):
    vk.step(config)
    commands.handle(config)
    registration.register(config)
    hr.greet(config)
    status.update(config)
'''

FILES["main.py"] = '''"""Точка входа."""
import logging
import config
from orchestrator import step
from modules import bus, db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def main():
    logging.info("Запуск")

    db.ensure(config)
    bus.dump(config.BUS_FILE, config.BUS_MAX_MESSAGES)

    try:
        while True:
            step(config)
            bus.dump(config.BUS_FILE, config.BUS_MAX_MESSAGES)
    except KeyboardInterrupt:
        logging.info("Остановка по Ctrl+C")


if __name__ == "__main__":
    main()
'''

FILES["requirements.txt"] = "requests\\npython-dotenv\\n"


def write(path, content):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  записан: {path}")


def main():
    print("Разворачиваю проект...")
    print()

    for path, content in FILES.items():
        write(path, content)

    # .env — только если его нет, чтобы не затереть токен
    if not os.path.exists(".env"):
        with open(".env", "w", encoding="utf-8") as f:
            f.write("VK_TOKEN=\\nVK_GROUP_ID=\\n")
        print("  создан: .env  (впиши токен!)")
    else:
        print("  .env уже есть — не тронут")

    print()
    print("Готово.")
    print()
    print("Дальше:")
    print("  1. pip install requests python-dotenv")
    print("  2. впиши VK_TOKEN в .env")
    print("  3. python main.py")


if __name__ == "__main__":
    main()