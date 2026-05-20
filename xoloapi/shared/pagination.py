import math
from typing import Generic, TypeVar

T = TypeVar("T")


class PageResult(Generic[T]):
    def __init__(self, items: list[T], total: int, page: int, size: int) -> None:
        self.items = items
        self.total = total
        self.page  = page
        self.size  = size

    @property
    def total_pages(self) -> int:
        return math.ceil(self.total / self.size) if self.size > 0 else 0
