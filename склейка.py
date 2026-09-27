# склейка.py — собирает все файлы проекта в один дамп, уважая .gitignore
# Запуск: python склейка.py

import os
import fnmatch
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.resolve()
OUTPUT = ROOT / "project_dump.txt"

# Всегда исключаем (плюс всё из .gitignore)
ALWAYS_EXCLUDE = {
    ".git", ".gitignore",
    "склейка.py", "project_dump.txt",
    ".venv", "venv", "__pycache__",
    ".vscode", ".idea", "node_modules",
    ".env",  # страховка на случай, если забыли в .gitignore
}

# --- читаем .gitignore ---
patterns = []
gitignore = ROOT / ".gitignore"
if gitignore.exists():
    for line in gitignore.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            patterns.append(line)


def is_ignored(rel_path: str) -> bool:
    """Проверяет, попадает ли путь под исключения."""
    rel_path = rel_path.replace("\\", "/")
    parts = rel_path.split("/")

    # по имени любой части пути (папки типа __pycache__)
    for part in parts:
        if part in ALWAYS_EXCLUDE:
            return True

    # верхнеуровневые исключения
    for ex in ALWAYS_EXCLUDE:
        if rel_path == ex or rel_path.startswith(ex + "/"):
            return True

    # правила из .gitignore
    for pat in patterns:
        p = pat.rstrip("/")
        # точное совпадение или вложенность
        if rel_path == p or rel_path.startswith(p + "/"):
            return True
        # glob-совпадение (например *.pyc)
        if fnmatch.fnmatch(rel_path, pat) or fnmatch.fnmatch(Path(rel_path).name, pat):
            return True

    return False


# --- собираем файлы ---
files = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    # исключаем папки на лету
    dirnames[:] = [
        d for d in dirnames
        if not is_ignored(str(Path(dirpath, d).relative_to(ROOT)))
    ]
    for fn in filenames:
        full = Path(dirpath, fn)
        rel = str(full.relative_to(ROOT))
        if not is_ignored(rel):
            files.append(full)

files.sort()

# --- формируем дамп ---
lines = []
lines.append(f"# Дамп проекта: {ROOT.name}")
lines.append(f"# Создан: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
lines.append(f"# Файлов: {len(files)}")
lines.append("#" + "=" * 70)
lines.append("")

for f in files:
    rel = str(f.relative_to(ROOT)).replace("\\", "/")
    lines.append("")
    lines.append("#" + "=" * 70)
    lines.append(f"# FILE: {rel}")
    lines.append("#" + "=" * 70)
    try:
        content = f.read_text(encoding="utf-8")
        lines.append(content)
    except UnicodeDecodeError:
        lines.append("[бинарный файл — пропущен]")
    except Exception as e:
        lines.append(f"[не удалось прочитать: {e}]")
    lines.append("")

OUTPUT.write_text("\n".join(lines), encoding="utf-8")

# --- отчёт ---
print()
print(f"Готово: {OUTPUT.name}")
print(f"Файлов склеено: {len(files)}")
print()
print("Проверка (не попал ли .env):")
dump = OUTPUT.read_text(encoding="utf-8")
if "# FILE: .env" in dump or "# FILE: .env.local" in dump:
    print("  ВНИМАНИЕ: .env попал в дамп!")
else:
    print("  .env НЕ попал — всё чисто")