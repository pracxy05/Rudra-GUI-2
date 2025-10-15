# serial_preprocessor.py
# Handles XBee telemetry via COM port and emits parsed rows in real time

import serial
import threading
import re
from PySide6.QtCore import QObject, Signal


class XBeeTelemetryWorker(QObject):
    """
    Reads incoming serial data from XBee, parses telemetry lines, and emits complete rows
    as dictionaries through the rowReady signal.
    Emits:
      - rowReady(dict)
      - connected(str)         -> when port opened successfully (payload: port string)
      - connection_lost(str)   -> when port unexpectedly closes or an error occurs
    """
    rowReady = Signal(dict)
    connected = Signal(str)
    connection_lost = Signal(str)

    def __init__(self, port, baudrate=9600, parent=None):
        super().__init__(parent)
        self.port = port
        self.baud = baudrate
        self._run_flag = False
        self._thread = None
        self._ser = None

    # -------------------------------
    # Thread Lifecycle Management
    # -------------------------------
    def start(self):
        """Start telemetry reading thread."""
        if self._thread and self._thread.is_alive():
            return
        self._run_flag = True
        self._thread = threading.Thread(target=self._run_worker, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop telemetry reading thread (clean stop)."""
        self._run_flag = False
        # closing port will cause read to stop if blocking
        try:
            if self._ser and self._ser.is_open:
                self._ser.close()
        except Exception:
            pass

    # -------------------------------
    # Data Parsing Logic
    # -------------------------------
    def _parse_frame(self, raw_lines):
        """Parse lines into a structured dictionary for one full telemetry frame."""
        row = {}
        for line in raw_lines:
            line = line.strip()
            if not line:
                continue

            # PRIMARY SENSORS
            if line.startswith("Gyro:"):
                matches = re.findall(r"([-+]?\d*\.?\d+)", line)
                if len(matches) >= 3:
                    row["gyro_x"], row["gyro_y"], row["gyro_z"] = map(float, matches[:3])

            elif line.startswith("BME:"):
                t = re.search(r"T=([-+]?\d*\.?\d+)", line)
                h = re.search(r"H=([-+]?\d*\.?\d+)", line)
                p = re.search(r"P=([-+]?\d*\.?\d+)", line)
                if t and h and p:
                    row["bme_temp"] = float(t.group(1))
                    row["bme_h"] = float(h.group(1))
                    row["bme_p"] = float(p.group(1))

            elif line.startswith("BMP:"):
                t = re.search(r"T=([-+]?\d*\.?\d+)", line)
                p = re.search(r"P=([-+]?\d*\.?\d+)", line)
                alt = re.search(r"Alt=([-+]?\d*\.?\d+)", line)
                if t and p and alt:
                    row["bmp_temp"] = float(t.group(1))
                    row["bmp_p"] = float(p.group(1))
                    row["bmp_alt"] = float(alt.group(1))

            elif line.startswith("GPS:"):
                lat = re.search(r"Lat=([-+]?\d*\.?\d+)", line)
                lon = re.search(r"Lon=([-+]?\d*\.?\d+)", line)
                alt = re.search(r"Alt=([-+]?\d*\.?\d+)", line)
                vel = re.search(r"Vel=([-+]?\d*\.?\d+)", line)
                if lat and lon and alt:
                    row["gps_lat"] = float(lat.group(1))
                    row["gps_lon"] = float(lon.group(1))
                    row["gps_alt"] = float(alt.group(1))
                if vel:
                    row["gps_vel"] = float(vel.group(1))

            # REDUNDANT SENSORS (suffix _R)
            elif line.startswith("Gyro(R):"):
                matches = re.findall(r"([-+]?\d*\.?\d+)", line)
                if len(matches) >= 3:
                    row["gyro_x_R"], row["gyro_y_R"], row["gyro_z_R"] = map(float, matches[:3])

            elif line.startswith("BME(R):"):
                t = re.search(r"T=([-+]?\d*\.?\d+)", line)
                h = re.search(r"H=([-+]?\d*\.?\d+)", line)
                p = re.search(r"P=([-+]?\d*\.?\d+)", line)
                if t and h and p:
                    row["bme_temp_R"] = float(t.group(1))
                    row["bme_h_R"] = float(h.group(1))
                    row["bme_p_R"] = float(p.group(1))

            elif line.startswith("BMP(R):"):
                t = re.search(r"T=([-+]?\d*\.?\d+)", line)
                p = re.search(r"P=([-+]?\d*\.?\d+)", line)
                alt = re.search(r"Alt=([-+]?\d*\.?\d+)", line)
                if t and p and alt:
                    row["bmp_temp_R"] = float(t.group(1))
                    row["bmp_p_R"] = float(p.group(1))
                    row["bmp_alt_R"] = float(alt.group(1))

            elif line.startswith("GPS(R):"):
                lat = re.search(r"Lat=([-+]?\d*\.?\d+)", line)
                lon = re.search(r"Lon=([-+]?\d*\.?\d+)", line)
                alt = re.search(r"Alt=([-+]?\d*\.?\d+)", line)
                if lat and lon and alt:
                    row["gps_lat_R"] = float(lat.group(1))
                    row["gps_lon_R"] = float(lon.group(1))
                    row["gps_alt_R"] = float(alt.group(1))

        return row

    # -------------------------------
    # Worker Loop
    # -------------------------------
    def _run_worker(self):
        """Main loop: open serial, read lines, parse frames, and emit."""
        try:
            self._ser = serial.Serial(self.port, self.baud, timeout=1)
            self.connected.emit(self.port)
        except Exception as e:
            # open failed
            self.connection_lost.emit(f"OPEN FAIL: {e}")
            return

        buffer_lines = []
        try:
            while self._run_flag:
                try:
                    raw = self._ser.readline()
                    if not raw:
                        continue
                    line = raw.decode(errors="ignore").strip()
                except Exception as e:
                    # something wrong with read; report and break
                    self.connection_lost.emit(f"READ ERR: {e}")
                    break

                if "Data transmitted via XBee" in line:
                    if buffer_lines:
                        parsed = self._parse_frame(buffer_lines)
                        if parsed:
                            self.rowReady.emit(parsed)
                    buffer_lines = []
                elif not line.startswith("---"):
                    buffer_lines.append(line)

        except Exception as e:
            # unexpected exception in loop
            self.connection_lost.emit(f"THREAD ERR: {e}")
        finally:
            try:
                if self._ser and self._ser.is_open:
                    self._ser.close()
            except Exception:
                pass
            self.connection_lost.emit("PORT CLOSED")
