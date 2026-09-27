"""VK-модуль. Читает LongPoll и кладёт сообщения в bus."""
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
