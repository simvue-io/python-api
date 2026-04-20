import typing

try:
    from typing import TypeAlias
except ImportError:
    from typing import TypeAlias


if typing.TYPE_CHECKING:
    from collections.abc import Buffer

    from numpy import ndarray
    from pandas import DataFrame
    from plotly.graph_objects import Figure, FigureWidget
    from torch import Tensor


DeserializedContent: TypeAlias = typing.Union[
    "DataFrame", "ndarray", "Tensor", "Figure", "FigureWidget", "Buffer"
]
