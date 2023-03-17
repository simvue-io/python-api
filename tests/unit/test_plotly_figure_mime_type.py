from simvue.serialization import Serializer, Deserializer
import matplotlib.pyplot as plt
import plotly

def test_plotly_figure_mime_type():
    """
    Check that a plotly figure has the correct mime-type
    """
    plt.plot([1, 2, 3, 4])
    figure = plt.gcf()
    plotly_figure = plotly.tools.mpl_to_plotly(figure)

    _, mime_type = Serializer().serialize(plotly_figure)

    assert (mime_type == 'application/vnd.plotly.v1+json')
