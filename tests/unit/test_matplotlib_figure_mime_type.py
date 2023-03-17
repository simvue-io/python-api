from simvue.serialization import Serializer, Deserializer
import matplotlib.pyplot as plt

def test_matplotlib_figure_mime_type():
    """
    Check that a matplotlib figure has the correct mime-type
    """
    plt.plot([1, 2, 3, 4])
    figure = plt.gcf()

    _, mime_type = Serializer().serialize(figure)

    assert (mime_type == 'application/vnd.plotly.v1+json')
