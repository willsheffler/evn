import sys
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    cast as cast,
    IO,
    Iterator,
    TypeVar,
    Union,
)

if sys.version_info.minor >= 10:
    from typing import ParamSpec
else:
    from typing_extensions import ParamSpec

KW = dict[str, Any]
IOBytes = IO[bytes]
IO = IO[str]
"""Type alias for keyword arguments represented as a dictionary with string keys and any type of value."""

FieldSpec = Union[str, list[str], tuple[str], Callable[..., str], tuple]
EnumerIter = Iterator[int]
EnumerListIter = Iterator[list[Any]]

T = TypeVar('T')
R = TypeVar('R')
C = TypeVar('C')
if sys.version_info.minor >= 10 or TYPE_CHECKING:
    P = ParamSpec('P')
    F = Callable[P, R]
else:
    P = TypeVar('P')
    P.args = list[Any]
    P.kwargs = KW
    F = Callable[[Any, ...], R]


def basic_typevars(which) -> list[Union[TypeVar, ParamSpec]]:
    result = [globals()[k] for k in which]
    return result
