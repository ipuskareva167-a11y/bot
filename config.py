"""Настройки проекта. Секреты — из .env."""
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
