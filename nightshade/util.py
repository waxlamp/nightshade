from typing import List, TypeVar


T = TypeVar("T")


def is_subslice(subslice: List[T], full: List[T]) -> bool:
    if len(subslice) > len(full):
        return False

    return full[: len(subslice)] == subslice or is_subslice(subslice, full[1:])
