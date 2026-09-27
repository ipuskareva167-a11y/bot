"""БД — статическая шина. JSON-файл. Только хранит."""
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
