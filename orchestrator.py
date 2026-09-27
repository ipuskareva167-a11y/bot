"""Оркестратор — дёргает модули. Каждый сам решает, работать или нет."""
from modules import vk, commands, registration, hr, status


def step(config):
    vk.step(config)
    commands.handle(config)
    registration.register(config)
    hr.greet(config)
    status.update(config)
