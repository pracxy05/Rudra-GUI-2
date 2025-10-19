from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, Property, QPointF, QRectF, QPoint
from PySide6.QtGui import QPainter, QPainterPath, QPen, QColor, QLinearGradient, QRadialGradient, QFont, QPolygon, QBrush
import math

class CompassWidget(QWidget):
    """Left-side compass indicator"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle = 0.0
        self.setFixedSize(80, 80)
        self._pointText = {0: "N", 45: "NE", 90: "E", 135: "SE", 180: "S",
                          225: "SW", 270: "W", 315: "NW"}
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Background circle
        gradient = QRadialGradient(40, 40, 40)
        gradient.setColorAt(0, QColor(30, 35, 50, 200))
        gradient.setColorAt(1, QColor(15, 20, 35, 230))
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor(80, 120, 180, 180), 2))
        painter.drawEllipse(5, 5, 70, 70)
        
        # Draw compass markings
        painter.save()
        painter.translate(40, 40)
        
        font = QFont("Segoe UI", 8, QFont.Weight.Bold)
        painter.setFont(font)
        
        for i in range(0, 360, 45):
            painter.save()
            painter.rotate(i)
            painter.setPen(QColor(200, 220, 255))
            painter.drawLine(0, -28, 0, -32)
            painter.restore()
            
            # Draw text
            angle_rad = math.radians(i - 90)
            x = 24 * math.cos(angle_rad)
            y = 24 * math.sin(angle_rad)
            text = self._pointText.get(i, "")
            painter.setPen(QColor(180, 200, 240))
            painter.drawText(int(x - 8), int(y + 4), text)
        
        # Draw needle - FIXED: Use QPoint instead of QPointF for QPolygon
        painter.rotate(self._angle)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 80, 80, 200))
        needle = QPolygon([QPoint(-3, 0), QPoint(0, -25), QPoint(3, 0), QPoint(0, 5)])
        painter.drawPolygon(needle)
        
        painter.restore()
    
    def setAngle(self, angle):
        if angle != self._angle:
            self._angle = angle
            self.update()
    
    angle = Property(float, lambda self: self._angle, setAngle)


class AccelerationGauge(QWidget):
    """Right-side acceleration/speed gauge"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0.0
        self._max_value = 3000.0  # km/h or m/s
        self.setFixedSize(80, 80)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Background
        gradient = QRadialGradient(40, 40, 40)
        gradient.setColorAt(0, QColor(30, 35, 50, 200))
        gradient.setColorAt(1, QColor(15, 20, 35, 230))
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor(80, 120, 180, 180), 2))
        painter.drawEllipse(5, 5, 70, 70)
        
        # Draw arc gauge
        painter.save()
        painter.translate(40, 40)
        
        # Arc path
        rect = QRectF(-28, -28, 56, 56)
        start_angle = 225 * 16  # Qt uses 1/16th degree
        span_angle = -270 * 16
        
        # Background arc
        painter.setPen(QPen(QColor(60, 70, 90, 150), 6))
        painter.drawArc(rect, start_angle, span_angle)
        
        # Progress arc
        progress = min(self._value / self._max_value, 1.0)
        progress_span = int(span_angle * progress)
        painter.setPen(QPen(QColor(100, 200, 255, 220), 6))
        painter.drawArc(rect, start_angle, progress_span)
        
        # Center value text
        painter.setPen(QColor(200, 220, 255))
        font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        painter.setFont(font)
        text = f"{int(self._value)}"
        painter.drawText(-20, 5, text)
        
        painter.restore()
    
    def setValue(self, value):
        if value != self._value:
            self._value = min(value, self._max_value)
            self.update()
    
    value = Property(float, lambda self: self._value, setValue)


class MissionStageBar(QWidget):
    """SpaceX-style mission stage progress bar with curved path"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(120)
        self._progress = 0.0  # 0.0 to 1.0
        self.current_stage = 0
        self.stages = ["LIFTOFF", "MAX Q", "STAGE SEP", "LANDING"]
        
        # Widgets
        self.compass = CompassWidget(self)
        self.accel_gauge = AccelerationGauge(self)
        
        # Timer label (center top)
        self.timer_label = QLabel("T+ 00:00:00", self)
        self.timer_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.timer_label.setStyleSheet("color: white; background: transparent;")
        self.timer_label.setAlignment(Qt.AlignCenter)
        
        # Mission subtitle
        self.subtitle_label = QLabel("STARSHIP FLIGHT TEST", self)
        self.subtitle_label.setFont(QFont("Segoe UI", 9))
        self.subtitle_label.setStyleSheet("color: rgba(255, 255, 255, 150); background: transparent;")
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        
        # Animation
        self.progress_animation = QPropertyAnimation(self, b"progress")
        self.progress_animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.progress_animation.setDuration(2000)
        
        # Test timer for demo
        self.demo_timer = QTimer()
        self.demo_timer.timeout.connect(self._demo_update)
        self.demo_timer.start(50)
        self._demo_counter = 0
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Position compass and gauge
        self.compass.move(20, 20)
        self.accel_gauge.move(self.width() - 100, 20)
        
        # Position labels
        self.timer_label.setGeometry(self.width()//2 - 100, 15, 200, 30)
        self.subtitle_label.setGeometry(self.width()//2 - 100, 45, 200, 20)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Background gradient (darkening sky effect)
        gradient = QLinearGradient(0, 0, 0, self.height())
        
        # Color transitions based on progress (lighter to darker blue)
        base_light = max(70 - int(self._progress * 50), 20)
        base_mid = max(90 - int(self._progress * 60), 30)
        
        gradient.setColorAt(0, QColor(50, 70, base_mid + 30))
        gradient.setColorAt(0.5, QColor(40, 60, base_mid))
        gradient.setColorAt(1, QColor(30, 45, base_light))
        
        painter.fillRect(self.rect(), gradient)
        
        # Draw curved path
        path_y = self.height() - 25
        self._draw_curved_stage_path(painter, path_y)
    
    def _draw_curved_stage_path(self, painter, center_y):
        """Draw the curved mission stage progress path"""
        width = self.width()
        padding = 140  # Space for compass and gauge
        usable_width = width - 2 * padding
        
        # Create curved path using QPainterPath
        path = QPainterPath()
        
        # Start point
        start_x = padding
        start_y = center_y
        
        # Control points for curve (simulate ascending rocket trajectory)
        num_stages = len(self.stages)
        segment_width = usable_width / (num_stages - 1)
        
        points = []
        for i in range(num_stages):
            x = start_x + i * segment_width
            # Curved upward trajectory
            curve_factor = (i / (num_stages - 1)) ** 0.7
            y = center_y - curve_factor * 15
            points.append((x, y))
        
        # Draw smooth curve through points
        path.moveTo(points[0][0], points[0][1])
        
        for i in range(1, len(points)):
            # Smooth curve using quadratic bezier
            if i < len(points) - 1:
                ctrl_x = (points[i][0] + points[i-1][0]) / 2
                ctrl_y = (points[i][1] + points[i-1][1]) / 2 - 8
                path.quadTo(ctrl_x, ctrl_y, points[i][0], points[i][1])
            else:
                path.lineTo(points[i][0], points[i][1])
        
        # Draw background path
        painter.setPen(QPen(QColor(80, 100, 140, 120), 4))
        painter.drawPath(path)
        
        # Draw progress path
        progress_path = QPainterPath()
        progress_path.moveTo(points[0][0], points[0][1])
        
        total_length = usable_width
        progress_length = total_length * self._progress
        
        current_length = 0
        for i in range(1, len(points)):
            segment_len = segment_width
            
            if current_length + segment_len <= progress_length:
                # Full segment
                if i < len(points) - 1:
                    ctrl_x = (points[i][0] + points[i-1][0]) / 2
                    ctrl_y = (points[i][1] + points[i-1][1]) / 2 - 8
                    progress_path.quadTo(ctrl_x, ctrl_y, points[i][0], points[i][1])
                else:
                    progress_path.lineTo(points[i][0], points[i][1])
            elif current_length < progress_length:
                # Partial segment
                ratio = (progress_length - current_length) / segment_len
                end_x = points[i-1][0] + (points[i][0] - points[i-1][0]) * ratio
                end_y = points[i-1][1] + (points[i][1] - points[i-1][1]) * ratio
                progress_path.lineTo(end_x, end_y)
                break
            
            current_length += segment_len
        
        # Glowing progress path
        painter.setPen(QPen(QColor(100, 200, 255, 250), 5))
        painter.drawPath(progress_path)
        
        # Draw stage markers and labels
        for i, (x, y) in enumerate(points):
            # Determine if stage is completed
            stage_progress = i / (num_stages - 1)
            is_active = self._progress >= stage_progress
            
            # Stage marker
            if is_active:
                painter.setBrush(QColor(100, 200, 255, 220))
                painter.setPen(QPen(QColor(150, 220, 255), 2))
            else:
                painter.setBrush(QColor(60, 80, 110, 180))
                painter.setPen(QPen(QColor(80, 100, 140), 2))
            
            painter.drawEllipse(QPointF(x, y), 8, 8)
            
            # Stage label
            painter.setPen(QColor(200, 220, 255) if is_active else QColor(120, 140, 180))
            font = QFont("Segoe UI", 9, QFont.Weight.Bold if is_active else QFont.Weight.Normal)
            painter.setFont(font)
            
            text = self.stages[i]
            text_width = painter.fontMetrics().horizontalAdvance(text)
            painter.drawText(int(x - text_width/2), int(y + 25), text)
    
    def advance_stage(self):
        """Move to next mission stage with animation"""
        if self.current_stage < len(self.stages) - 1:
            self.current_stage += 1
            target_progress = self.current_stage / (len(self.stages) - 1)
            
            self.progress_animation.setStartValue(self._progress)
            self.progress_animation.setEndValue(target_progress)
            self.progress_animation.start()
    
    def set_telemetry_data(self, data_dict):
        """Update from telemetry data"""
        # Update compass if heading available
        if 'heading' in data_dict or 'yaw' in data_dict:
            angle = data_dict.get('heading', data_dict.get('yaw', 0))
            self.compass.setAngle(angle)
        
        # Update acceleration gauge
        if 'velocity' in data_dict:
            self.accel_gauge.setValue(data_dict['velocity'])
        elif 'speed' in data_dict:
            self.accel_gauge.setValue(data_dict['speed'])
    
    def _demo_update(self):
        """Demo animation - remove in production"""
        self._demo_counter += 1
        
        # Auto-advance stages
        if self._demo_counter % 200 == 0:
            self.advance_stage()
        
        # Simulate telemetry
        sim_heading = (self._demo_counter * 2) % 360
        sim_speed = min(self._demo_counter * 5, 2800)
        
        self.compass.setAngle(sim_heading)
        self.accel_gauge.setValue(sim_speed)
        
        # Update timer
        seconds = self._demo_counter // 20
        mins = seconds // 60
        secs = seconds % 60
        self.timer_label.setText(f"T+ {mins:02d}:{secs:02d}")
    
    def get_progress(self):
        return self._progress
    
    def set_progress(self, value):
        if self._progress != value:
            self._progress = max(0.0, min(1.0, value))
            self.update()
    
    progress = Property(float, get_progress, set_progress)
