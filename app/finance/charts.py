import matplotlib

matplotlib.use('agg')

import matplotlib.pyplot as plt
from io import BytesIO
import base64


def generate_chart(x_data, y_data, title=None):
    plt.figure()
    plt.bar(x_data, y_data)
    if title:
        plt.title(title)

    figfile = BytesIO()
    plt.savefig(figfile, format='png')

    figdata_png = base64.b64encode(figfile.getvalue()).decode()
    return figdata_png
