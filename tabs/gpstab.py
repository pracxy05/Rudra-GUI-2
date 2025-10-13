from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
import tempfile
import plotly.express as px
import plotly.graph_objects as go


class GPSTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.label = QLabel("🗺️ Rocket GPS Tracking - Hyderabad")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)

        lat = [17.3850, 17.3860, 17.3870, 17.3880]
        lon = [78.4867, 78.4875, 78.4885, 78.4895]

        fig = px.scatter_mapbox(
            lat=lat, lon=lon,
            zoom=12,
            mapbox_style="open-street-map",
            title="Rocket GPS Tracking - Hyderabad"
        )

        fig.add_trace(go.Scattermapbox(
            lat=[lat[-1]],
            lon=[lon[-1]],
            mode='markers',
            marker=dict(size=15, color="red"),
            name="Rocket Position"
        ))

        temp = tempfile.NamedTemporaryFile(delete=False, suffix='.html')
        fig.write_html(temp.name)
        temp.close()

        self.webview = QWebEngineView()
        self.webview.load(QUrl.fromLocalFile(temp.name))
        layout.addWidget(self.webview, stretch=1)
        self.setLayout(layout)
