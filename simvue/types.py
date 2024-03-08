import typing

if typing.TYPE_CHECKING:
    from numpy import ndarray
    from pandas import DataFrame
    from plotly.graph_objects import Figure, FigureWidget
    from torch import Tensor
    from typing_extensions import Buffer


DeserializedContent: typing.TypeAlias = typing.Union[
    "DataFrame", "ndarray", "Tensor", "Figure", "FigureWidget", "Buffer"
]
