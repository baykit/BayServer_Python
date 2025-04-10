from typing import Callable

ContentConsumeListener = Callable[[int, bool], None]


def content_consume_listener_dev_null(length: int, resume: bool) -> None:
    pass