import sys
import threading
import collections
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QLineEdit, QGridLayout)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QImage, QPixmap
import pyqtgraph as pg
import numpy as np

# Import your corrected client functions here
from client_interface import (client_get_vision_context, client_dispatch_task, 
                              client_pause_robot, client_rotate_base, decode_image, VLA_API_URL)
import requests

PRESET_TASKS = {
    Qt.Key_1: "pick up foam ball",
    Qt.Key_2: "add held object to skewer",
    Qt.Key_3: "drop held object in cup",

}

class NetworkWorker(QThread):
    """Background thread to poll the VLA without freezing the GUI."""
    data_ready = pyqtSignal(dict, dict, str)
    
    def __init__(self):
        super().__init__()
        self.running = True

    def run(self):
        while self.running:
            try:
                b64_imgs, motors, task = client_get_vision_context()
                self.data_ready.emit(b64_imgs, motors, task)
                self.msleep(100) # ~10 FPS polling limit to save CPU
            except Exception as e:
                self.msleep(500) # Back off on error

    def stop(self):
        self.running = False
        self.wait()

class VLADashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VLA Orchestration Dashboard")
        self.resize(1200, 800)
        self.motors_active = False

        # --- UI Layout Setup ---
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # 1. Camera Feeds (Horizontal)
        self.cam_layout = QHBoxLayout()
        main_layout.addLayout(self.cam_layout)
        self.cam_labels = {} # Store labels dynamically based on API keys

        # 2. Joint Angle Plots (Grid)
        self.plot_layout = QGridLayout()
        main_layout.addLayout(self.plot_layout)
        self.plots = {}
        self.curves = {}
        self.data_buffers = {}

        # 3. Controls (Bottom Row)
        control_layout = QHBoxLayout()
        
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Enter new VLA task...")
        self.btn_send = QPushButton("Dispatch Task (Enter)")
        self.btn_send.clicked.connect(self.dispatch_task)
        self.btn_task_1 = QPushButton("Pick Foam Ball (1)")
        self.btn_task_1.clicked.connect(
            lambda: self.dispatch_task(PRESET_TASKS[Qt.Key_1])
        )
        self.btn_task_2 = QPushButton("Add Held Object To Skewer (2)")
        self.btn_task_2.clicked.connect(
            lambda: self.dispatch_task(PRESET_TASKS[Qt.Key_2])
        )
        self.btn_task_3 = QPushButton("Drop Held Object In Cup (3)")
        self.btn_task_3.clicked.connect(
            lambda: self.dispatch_task(PRESET_TASKS[Qt.Key_3])
        )
        
        self.btn_toggle = QPushButton("Enable Motors (Space)")
        self.btn_toggle.clicked.connect(self.toggle_motors)
        
        self.btn_left = QPushButton("Base Left (<-)")
        self.btn_left.clicked.connect(lambda: self.step_base(500))
        
        self.btn_right = QPushButton("Base Right (->)")
        self.btn_right.clicked.connect(lambda: self.step_base(-500))

        control_layout.addWidget(self.prompt_input)
        control_layout.addWidget(self.btn_send)
        control_layout.addWidget(self.btn_task_1)
        control_layout.addWidget(self.btn_task_2)
        control_layout.addWidget(self.btn_task_3)
        control_layout.addWidget(self.btn_toggle)
        control_layout.addWidget(self.btn_left)
        control_layout.addWidget(self.btn_right)
        main_layout.addLayout(control_layout)

        # --- Start Networking ---
        self.worker = NetworkWorker()
        self.worker.data_ready.connect(self.update_ui)
        self.worker.start()

    def update_ui(self, b64_imgs, motors, task):
        # Update Task Label/Placeholder
        if task and not self.prompt_input.hasFocus():
            self.prompt_input.setPlaceholderText(f"Current: {task}")

        # Update Images
        for cam_name, b64_str in b64_imgs.items():
            if cam_name not in self.cam_labels:
                lbl = QLabel()
                lbl.setMinimumSize(300, 300)
                lbl.setScaledContents(True)
                self.cam_layout.addWidget(lbl)
                self.cam_labels[cam_name] = lbl
                
            img_bgr = decode_image(b64_str)
            h, w, ch = img_bgr.shape
            bytes_per_line = ch * w
            img_rgb = img_bgr[..., ::-1].copy() # BGR to RGB for Qt
            q_img = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            self.cam_labels[cam_name].setPixmap(QPixmap.fromImage(q_img))

        # Flatten motor arrays to handle 12 discrete joints
        flat_motors = {}
        for k, v in motors.items():
            if isinstance(v, list):
                for i, val in enumerate(v):
                    flat_motors[f"{k}_{i}"] = val
            else:
                flat_motors[k] = v

        # Update Plots Dynamically
        row, col = 0, 0
        for joint_name, val in flat_motors.items():
            if joint_name not in self.plots:
                plot_widget = pg.PlotWidget(title=joint_name)
                plot_widget.setFixedHeight(150)
                self.plot_layout.addWidget(plot_widget, row, col)
                self.plots[joint_name] = plot_widget
                self.curves[joint_name] = plot_widget.plot(pen='y')
                self.data_buffers[joint_name] = collections.deque(maxlen=50)
                
                col += 1
                if col > 3: # 4 columns wide
                    col = 0
                    row += 1

            self.data_buffers[joint_name].append(val)
            self.curves[joint_name].setData(self.data_buffers[joint_name])

    # --- Controls (Fire & Forget Threads to prevent UI freeze) ---
    def dispatch_task(self, task=None):
        task = task if task is not None else self.prompt_input.text()
        if task:
            threading.Thread(target=client_dispatch_task, args=(task,), daemon=True).start()
            self.prompt_input.clear()
            self.motors_active = True
            self.btn_toggle.setText("Disable Motors (Space)")

    def toggle_motors(self):
        self.motors_active = not self.motors_active
        if self.motors_active:
            # Assumes you updated your API to use {"allow": True} or updated client to match
            threading.Thread(target=requests.post, args=(f"{VLA_API_URL}/allow_act",), 
                             kwargs={"json": {"allow_act": True}}, daemon=True).start()
            self.btn_toggle.setText("Disable Motors (Space)")
        else:
            threading.Thread(target=client_pause_robot, daemon=True).start()
            self.btn_toggle.setText("Enable Motors (Space)")

    def step_base(self, steps):
        # Enforce the +/- 2000 hardware limit
        clamped_steps = max(min(steps, 2000), -2000)
        threading.Thread(target=client_rotate_base, args=(clamped_steps,), daemon=True).start()

    # --- Keyboard Bindings ---
    def keyPressEvent(self, event):
        # Ignore hotkeys if the user is typing a prompt
        if self.prompt_input.hasFocus():
            if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                self.dispatch_task()
            return

        if event.key() == Qt.Key_Space:
            self.toggle_motors()
        elif event.key() == Qt.Key_Left:
            self.step_base(500)
        elif event.key() == Qt.Key_Right:
            self.step_base(-500)
        elif event.key() in PRESET_TASKS:
            self.dispatch_task(PRESET_TASKS[event.key()])

    def closeEvent(self, event):
        self.worker.stop()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VLADashboard()
    window.show()
    sys.exit(app.exec_())