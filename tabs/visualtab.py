# visualtab.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import QTimer, Qt
from vispy import scene, io
from vispy.visuals.transforms import STTransform
from vispy.geometry import create_sphere
import numpy as np
import os
import sys
import logging
import random

# ───────────────────────────────────────────────
# 🧱 SILENCE VISPY LOGS / WEBGL WARNINGS
# ───────────────────────────────────────────────
logging.getLogger('vispy').setLevel(logging.ERROR)
sys.stderr = open(os.devnull, 'w')

class VisualTab(QWidget):
    def __init__(self):
        super().__init__()
        print("Initializing VisualTab")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # ───────────────────────────────────────────────
        # 🌌 SCENE SETUP
        # ───────────────────────────────────────────────
        try:
            self.canvas = scene.SceneCanvas(keys=None, bgcolor='black', show=False, vsync=False)
            self.view = self.canvas.central_widget.add_view()
            self.view.camera = scene.cameras.TurntableCamera(fov=45, azimuth=45, elevation=30, distance=8)
            layout.addWidget(self.canvas.native)
        except Exception as e:
            print("Error initializing VisPy canvas:", e)
            placeholder = QLabel("Visual tab cannot load 3D scene.\nCheck OpenGL support.")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(placeholder)
            return

        # ───────────────────────────────────────────────
        # 🌍 EARTH
        # ───────────────────────────────────────────────
        self.create_earth()

        # ───────────────────────────────────────────────
        # 🚀 ROCKET OBJ
        # ───────────────────────────────────────────────
        self.create_rocket()

        # ───────────────────────────────────────────────
        # 🔥 ROCKET FLAME (simple pyramid mesh)
        # ───────────────────────────────────────────────
        self.create_flame()

        # ───────────────────────────────────────────────
        # 🌟 STARFIELD
        # ───────────────────────────────────────────────
        self.create_starfield()

        # ───────────────────────────────────────────────
        # 🎮 UI CONTROLS
        # ───────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        layout.addLayout(btn_layout)

        self.launch_btn = QPushButton("🚀 Launch Rocket")
        self.launch_btn.setStyleSheet("background:#1abc9c;color:white;font-weight:bold;padding:8px 20px;border-radius:10px;")
        self.launch_btn.clicked.connect(self.start_launch)
        btn_layout.addWidget(self.launch_btn)

        self.reset_btn = QPushButton("🔁 Reset")
        self.reset_btn.setStyleSheet("background:#e74c3c;color:white;font-weight:bold;padding:8px 20px;border-radius:10px;")
        self.reset_btn.clicked.connect(self.reset_scene)
        btn_layout.addWidget(self.reset_btn)

        self.status_label = QLabel("Ready for launch 🚀")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color:#00eaff;font-weight:bold;font-size:14px;")
        layout.addWidget(self.status_label)

        # Animation variables
        self.timer = QTimer()
        self.timer.timeout.connect(self.animate_launch)
        self.launch_active = False
        self.rocket_altitude = 0.0
        self.falling = False

        # Camera orbit
        self.orbit_timer = QTimer()
        self.orbit_timer.timeout.connect(self.auto_orbit)
        self.orbit_timer.start(50)

    # ───────────────────────────────────────────────
    # 🌍 EARTH MODEL
    # ───────────────────────────────────────────────
    def create_earth(self):
        sphere = create_sphere(64, 128, radius=2.5)
        verts, faces = sphere.get_vertices(), sphere.get_faces()
        texture_path = os.path.join(os.path.dirname(__file__), "../assets/earth.jpg")
        if os.path.exists(texture_path):
            img = io.imread(texture_path)
            self.earth = scene.visuals.Mesh(vertices=verts, faces=faces, color=(1,1,1,1), parent=self.view.scene)
            from vispy.visuals.filters import TextureFilter
            self.earth.attach(TextureFilter(img))
        else:
            self.earth = scene.visuals.Mesh(vertices=verts, faces=faces, color=(0.2,0.4,1.0,1.0), parent=self.view.scene)

    # ───────────────────────────────────────────────
    # 🚀 ROCKET MODEL
    # ───────────────────────────────────────────────
    def create_rocket(self):
        rocket_path = os.path.join(os.path.dirname(__file__), "../assets/rocket.obj")
        if os.path.exists(rocket_path):
            try:
                verts, faces, normals, texcoords = io.read_mesh(rocket_path)
                self.rocket = scene.visuals.Mesh(vertices=verts, faces=faces, color=(1,0.5,0,1), parent=self.view.scene)
                self.rocket.transform = STTransform(translate=(0,0,1.8), scale=(0.005,0.005,0.005))
                return
            except Exception as e:
                print("Error loading rocket.obj:", e)
        # fallback: small orange sphere
        self.rocket = scene.visuals.Sphere(radius=0.15, color=(1,0.5,0,1), parent=self.view.scene)
        self.rocket.transform = STTransform(translate=(0,0,1.8))

    # ───────────────────────────────────────────────
    # 🔥 ROCKET FLAME
    # ───────────────────────────────────────────────
    def create_flame(self):
        # create a simple 4-vertex pyramid as flame
        vertices = np.array([
            [0,0,0],
            [-0.08,-0.08,-0.25],
            [0.08,-0.08,-0.25],
            [0,0.08,-0.25]
        ])
        faces = np.array([
            [0,1,2],
            [0,2,3],
            [0,3,1],
            [1,2,3]
        ])
        self.flame = scene.visuals.Mesh(vertices=vertices, faces=faces, color=(1,0.4,0,0.8), parent=self.view.scene)
        self.flame.transform = STTransform(translate=(0,0,1.55))
        self.flame.visible = False

    # ───────────────────────────────────────────────
    # 🌌 STARFIELD
    # ───────────────────────────────────────────────
    def create_starfield(self):
        stars = np.random.uniform(-50,50,(800,3))
        colors = np.ones((800,4))
        colors[:, :3] = np.random.uniform(0.7,1.0,(800,3))
        self.stars = scene.visuals.Markers(parent=self.view.scene)
        self.stars.set_data(stars, face_color=colors, size=1.4)

    # ───────────────────────────────────────────────
    # 🚀 LAUNCH ANIMATION
    # ───────────────────────────────────────────────
    def start_launch(self):
        if not self.launch_active:
            self.launch_active = True
            self.falling = False
            self.flame.visible = True
            self.status_label.setText("Launching 🚀")
            self.timer.start(30)

    def animate_launch(self):
        if not self.launch_active:
            return

        if not self.falling:
            # Going up
            self.rocket_altitude += 0.07
            self.rocket.transform.translate = (0,0,1.8 + self.rocket_altitude)

            # Flicker flame
            flicker = 0.05 * random.uniform(0.8,1.2)
            self.flame.transform.translate = (0,0,1.55 + self.rocket_altitude - flicker)

            self.status_label.setText(f"Altitude: {self.rocket_altitude:.2f} m")

            if self.rocket_altitude > 6.0:
                self.falling = True
                self.status_label.setText("Apogee reached 🌌")
        else:
            # Falling down with tilt
            self.rocket_altitude -= 0.05
            tilt_x = 5*np.sin(self.rocket_altitude*5)
            tilt_y = 5*np.cos(self.rocket_altitude*5)
            self.rocket.transform.rotate = (tilt_x, tilt_y, 0)
            self.rocket.transform.translate = (0,0,1.8 + self.rocket_altitude)
            self.flame.visible = False

            if self.rocket_altitude <= 0:
                self.launch_active = False
                self.rocket_altitude = 0
                self.rocket.transform.translate = (0,0,1.8)
                self.rocket.transform.rotate = (0,0,0)
                self.status_label.setText("Rocket landed safely 🪂")

    # ───────────────────────────────────────────────
    # 🔁 RESET SCENE
    # ───────────────────────────────────────────────
    def reset_scene(self):
        self.timer.stop()
        self.launch_active = False
        self.falling = False
        self.rocket_altitude = 0.0
        self.rocket.transform.translate = (0,0,1.8)
        self.rocket.transform.rotate = (0,0,0)
        self.flame.visible = False
        self.canvas.bgcolor = 'black'
        self.status_label.setText("Ready for launch 🚀")

    # ───────────────────────────────────────────────
    # 🎥 CAMERA ORBIT
    # ───────────────────────────────────────────────
    def auto_orbit(self):
        self.view.camera.azimuth += 0.3
        self.view.camera.view_changed()
