import typing

if typing.TYPE_CHECKING:
    from numpy import ndarray
    from pandas import DataFrame
    from torch import Tensor
    from plotly.graph_objects import Figure, FigureWidget
    from typing_extensions import Buffer


DeserializedContent: typing.TypeAlias = typing.Union[
    "DataFrame",
    "ndarray",
    "Tensor",
    "Figure",
    "FigureWidget",
    "Buffer"
]
