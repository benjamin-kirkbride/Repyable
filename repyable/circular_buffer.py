from collections.abc import Iterator
from typing import Generic, TypeVar

T = TypeVar("T")


class CircularBuffer(Generic[T]):
    """A circular buffer implementation that stores a fixed-size collection of items."""

    def __init__(self, size: int):
        """Initializes a CircularBuffer object.

        Args:
            size (int): The size of the circular buffer.

        Attributes:
            buffer (list): The circular buffer.
            size (int): The size of the circular buffer.
            head (int): The index of the head of the circular buffer.
            tail (int): The index of the tail of the circular buffer.
            count (int): The number of elements in the circular buffer.
        """
        self.buffer: list[T | None] = [None] * size
        self.size: int = size
        self.head: int = 0
        self.tail: int = 0
        self.count: int = 0

    def push(self, item: T) -> None:
        """Adds an item to the circular buffer.

        Args:
            item (T): The item to be added to the buffer.

        Returns:
            None
        """
        self.buffer[self.head] = item
        self.head = (self.head + 1) % self.size
        if self.count < self.size:
            self.count += 1
        else:
            self.tail = (self.tail + 1) % self.size

    def pop(self) -> T | None:
        """Removes and returns the oldest item from the circular buffer.

        Returns:
            The oldest item in the buffer, or None if the buffer is empty.
        """
        if self.count == 0:
            return None
        item = self.buffer[self.tail]
        self.tail = (self.tail + 1) % self.size
        self.count -= 1
        return item

    def __getitem__(self, index: int) -> T:
        if index >= self.count:
            msg = "CircularBuffer index out of range"
            raise IndexError(msg)

        item = self.buffer[(self.tail + index) % self.size]
        assert item is not None
        return item

    def __len__(self) -> int:
        return self.count

    def __iter__(self) -> Iterator[T]:
        for i in range(self.count):
            yield self[i]

    def __repr__(self) -> str:
        return f"CircularBuffer({list(self)})"

    def __str__(self) -> str:
        return f"CircularBuffer({list(self)})"

    def __contains__(self, item: T) -> bool:
        return item in self.buffer

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CircularBuffer):
            return False
        return list(self) == list(other)
