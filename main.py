"""Точка входа."""
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
