import pytest
from simvue.serialization import Serializer

try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

@pytest.mark.skipif(not plt, reason="Matplotlib is not installed")
def test_matplotlib_figure_mime_type():
    """
    Check that a matplotlib figure has the correct mime-type
    """
    plt.plot([1, 2, 3, 4])
    figure = plt.gcf()

    _, mime_type = Serializer().serialize(figure)

    assert (mime_type == 'application/vnd.plotly.v1+json')
