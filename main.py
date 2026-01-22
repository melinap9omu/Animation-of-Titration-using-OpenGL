import sys
import math
import random
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QSlider, QGroupBox)
from PyQt5.QtOpenGL import QGLWidget
from PyQt5.QtCore import QTimer, Qt
from OpenGL.GL import *
from OpenGL.GLU import *
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class Particle:
    """Represents a mixing particle in the solution"""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = random.uniform(-0.02, 0.02)
        self.vy = random.uniform(0.01, 0.03)
        self.lifetime = random.uniform(0.4, 0.8)
        self.age = 0
        
    def update(self, dt=0.016):
        self.x += self.vx
        self.y += self.vy
        self.age += dt
        self.vy -= 0.0015  # Gravity
        self.vx *= 0.95    # Friction
        
    def is_alive(self):
        return self.age < self.lifetime

class Droplet:
    """Represents a falling droplet from the burette"""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vy = 0
        self.radius = 0.02
        self.acceleration = -0.002
        
    def update(self):
        self.vy += self.acceleration
        self.y += self.vy

class GraphWidget(FigureCanvas):
    """Real-time titration curve plotter"""
    def __init__(self, parent=None):
        fig = Figure(figsize=(5, 4), dpi=100)
        self.axes = fig.add_subplot(111)
        super().__init__(fig)
        self.x_data = []
        self.y_data = []
        self.setup_plot()

    def setup_plot(self):
        self.axes.set_title("Titration Curve", fontsize=12, fontweight='bold')
        self.axes.set_xlabel("Volume of Base Added (mL)", fontsize=10)
        self.axes.set_ylabel("pH", fontsize=10)
        self.axes.set_ylim(0, 14)
        self.axes.set_xlim(0, 10)
        self.axes.grid(True, linestyle='--', alpha=0.5)
        self.axes.axhline(y=7, color='green', linestyle=':', alpha=0.5, label='Neutral pH')
        self.axes.axhline(y=8.2, color='purple', linestyle=':', alpha=0.5, label='Indicator Change')
        self.axes.axvline(x=6.0, color='blue', linestyle='--',
                  alpha=0.6, label='Equivalence Point')
        self.axes.axhline(y=8.2, color='purple', linestyle=':',
                        alpha=0.6, label='Indicator Transition')

    def update_graph(self, drops, ph):
        self.x_data.append(drops)
        self.y_data.append(ph)
        self.axes.clear()
        self.setup_plot()
        
        # Adjust x-axis dynamically
        if drops > 10:
            self.axes.set_xlim(0, drops + 10)
        
        self.axes.plot(self.x_data, self.y_data, color='#e74c3c', linewidth=2.5, marker='o', 
                      markersize=3, markerfacecolor='#c0392b')
        self.axes.legend(fontsize=8)
        self.draw()

        # Stage annotations
        if ph < 6.5:
            self.axes.text(drops * 0.6, 2, "Acidic region", fontsize=9, color="black")
        elif 6.5 <= ph <= 7.5:
            self.axes.text(drops * 0.6, 10, "Equivalence point region", fontsize=9, color="black")
        else:
            self.axes.text(drops * 0.6, 12, "Excess base region", fontsize=9, color="black")

    def reset(self):
        self.x_data = []
        self.y_data = []
        self.axes.clear()
        self.setup_plot()
        self.draw()


class TitrationAnimation(QGLWidget):
    """Main OpenGL animation widget for titration simulation"""
    def __init__(self, graph_callback):
        super().__init__()
        self.ml_per_drop = 0.05  # 1 drop ≈ 0.05 mL
        self.volume_ml = 0.0
        self.eq_volume_ml = 6.0  # equivalence point (~6 mL)
        self.graph_callback = graph_callback
        self.droplets = []
        self.particles = []
        self.mix_ratio = 0.0
        self.liquid_level = 0.15
        self.burette_valve_open = False
        self.drop_rate = 0.1
        self.frame_count = 0
        self.ph_value = 1.0  # Starting pH (strong acid)
        self.total_drops = 0
        self.indicator_active = True
        
        # Flask dimensions
        self.flask_bottom_y = -0.9
        self.flask_bottom_width = 0.7
        self.flask_neck_width = 0.2
        self.flask_neck_y = -0.2
        
        # Burette position
        self.burette_tip_x = 0.0
        self.burette_tip_y = -0.15
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(16)

    def initializeGL(self):
        glClearColor(0.96, 0.96, 0.98, 1.0)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_LINE_SMOOTH)
        glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluOrtho2D(-1, 1, -1, 1)

    def get_flask_width_at_height(self, y):
        """Calculate flask width at a given height (linear interpolation)"""
        if y <= self.flask_bottom_y:
            return self.flask_bottom_width / 2
        elif y >= self.flask_neck_y:
            return self.flask_neck_width / 2
        else:
            t = (y - self.flask_bottom_y) / (self.flask_neck_y - self.flask_bottom_y)
            width = self.flask_bottom_width + t * (self.flask_neck_width - self.flask_bottom_width)
            return width / 2

    def update_animation(self):
        self.frame_count += 1
        
        # Spawn droplets based on valve state and drop rate
        if self.burette_valve_open and random.random() < self.drop_rate:
            self.droplets.append(Droplet(self.burette_tip_x, self.burette_tip_y))
        
        # Update droplets
        surface_y = self.flask_bottom_y + self.liquid_level
        for drop in self.droplets[:]:
            drop.update()
            if drop.y < surface_y:
                # Drop hit the liquid surface
                self.total_drops += 1
                self.volume_ml = self.total_drops * self.ml_per_drop
                self.liquid_level = min(self.liquid_level + 0.0015, 0.7)

                # Logistic titration curve (strong acid + strong base)
                x = (self.volume_ml - self.eq_volume_ml) * 1.8
                self.ph_value = 1.0 + 13.0 / (1.0 + math.exp(-x))

                self.graph_callback(self.volume_ml, self.ph_value)
                
                # Create splash particles
                for _ in range(6):
                    self.particles.append(Particle(drop.x, surface_y))
                
                self.droplets.remove(drop)
        
        # Update particles
        for p in self.particles[:]:
            p.update()
            if not p.is_alive():
                self.particles.remove(p)
                
        self.update()

    def get_solution_color(self):
        """Phenolphthalein indicator: colorless < pH 8.2, pink > pH 8.2"""
        if not self.indicator_active:
            return (1.0, 1.0, 1.0)
        
        if self.ph_value < 8.2:
            return (1.0, 1.0, 1.0)  # Colorless
        else:
            # Gradual transition to pink
            intensity = min(1.0, (self.ph_value - 8.2) / 3.0)
            r = 1.0
            g = 1.0 - intensity * 0.6
            b = 1.0 - intensity * 0.3
            return (r, g, b)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT)
        glLoadIdentity()

        # 1. Draw liquid in flask
        r, g, b = self.get_solution_color()
        glColor4f(r, g, b, 0.85)
        
        liquid_height = self.liquid_level
        liquid_top_y = self.flask_bottom_y + liquid_height
        bottom_half_width = self.get_flask_width_at_height(self.flask_bottom_y)
        top_half_width = self.get_flask_width_at_height(liquid_top_y)
        
        glBegin(GL_POLYGON)
        glVertex2f(-bottom_half_width, self.flask_bottom_y)
        glVertex2f(bottom_half_width, self.flask_bottom_y)
        glVertex2f(top_half_width, liquid_top_y)
        glVertex2f(-top_half_width, liquid_top_y)
        glEnd()

        # 2. Draw mixing particles
        glPointSize(5.0)
        glBegin(GL_POINTS)
        for p in self.particles:
            alpha = 1.0 - (p.age / p.lifetime)
            glColor4f(0.1, 0.5, 0.9, alpha)
            glVertex2f(p.x, p.y)
        glEnd()

        # 3. Draw droplets
        glColor3f(0.2, 0.6, 1.0)
        for drop in self.droplets:
            glBegin(GL_POLYGON)
            for i in range(12):
                theta = 2 * math.pi * i / 12
                glVertex2f(drop.x + 0.015 * math.cos(theta), 
                          drop.y + 0.025 * math.sin(theta))
            glEnd()

        # 4. Draw flask outline
        glColor3f(0.15, 0.15, 0.15)
        glLineWidth(2.5)
        
        glBegin(GL_LINE_STRIP)
        glVertex2f(-self.flask_neck_width/2, self.flask_neck_y)
        glVertex2f(-self.flask_bottom_width/2, self.flask_bottom_y)
        glVertex2f(self.flask_bottom_width/2, self.flask_bottom_y)
        glVertex2f(self.flask_neck_width/2, self.flask_neck_y)
        glEnd()
        
        # Flask neck
        glBegin(GL_LINES)
        glVertex2f(-self.flask_neck_width/2, self.flask_neck_y)
        glVertex2f(-self.flask_neck_width/2, self.flask_neck_y + 0.15)
        glVertex2f(self.flask_neck_width/2, self.flask_neck_y)
        glVertex2f(self.flask_neck_width/2, self.flask_neck_y + 0.15)
        glEnd()

        # 5. Draw burette
        burette_width = 0.045
        burette_top = 0.85
        
        # Burette tube
        glBegin(GL_LINE_LOOP)
        glVertex2f(self.burette_tip_x - burette_width/2, self.burette_tip_y)
        glVertex2f(self.burette_tip_x + burette_width/2, self.burette_tip_y)
        glVertex2f(self.burette_tip_x + burette_width/2, burette_top)
        glVertex2f(self.burette_tip_x - burette_width/2, burette_top)
        glEnd()
        
        # Burette tip
        glBegin(GL_LINE_STRIP)
        glVertex2f(self.burette_tip_x - burette_width/2, self.burette_tip_y)
        glVertex2f(self.burette_tip_x, self.burette_tip_y - 0.035)
        glVertex2f(self.burette_tip_x + burette_width/2, self.burette_tip_y)
        glEnd()

        # 6. Draw stand and support
        stand_x = 0.75
        arm_y = 0.6
        
        # Horizontal support arm
        glLineWidth(2)
        glBegin(GL_LINES)
        glVertex2f(self.burette_tip_x + burette_width/2, arm_y)
        glVertex2f(stand_x, arm_y)
        glEnd()
        
        # Clamp
        glBegin(GL_LINE_STRIP)
        glVertex2f(stand_x - 0.05, arm_y - 0.06)
        glVertex2f(stand_x, arm_y - 0.06)
        glVertex2f(stand_x, arm_y + 0.06)
        glVertex2f(stand_x - 0.05, arm_y + 0.06)
        glEnd()
        
        # Vertical stand
        glLineWidth(5)
        glBegin(GL_LINES)
        glVertex2f(stand_x, -0.9)
        glVertex2f(stand_x, 0.9)
        glEnd()
        
        # Stand base
        glLineWidth(4)
        glBegin(GL_LINES)
        glVertex2f(stand_x - 0.18, -0.9)
        glVertex2f(stand_x + 0.18, -0.9)
        glEnd()

    def toggle_valve(self):
        self.burette_valve_open = not self.burette_valve_open
    
    def set_drop_rate(self, val):
        self.drop_rate = val / 50.0
    
    def toggle_indicator(self):
        self.indicator_active = not self.indicator_active
    
    def reset_animation(self):
        self.mix_ratio = 0.0
        self.ph_value = 1.0
        self.liquid_level = 0.15
        self.total_drops = 0
        self.volume_ml = 0.0
        self.droplets.clear()
        self.particles.clear()
        self.burette_valve_open = False

class ControlPanel(QWidget):
    """Control panel with buttons and sliders"""
    def __init__(self, animation_widget, graph_widget):
        super().__init__()
        self.animation = animation_widget
        self.graph = graph_widget
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # stage
        self.lbl_stage = QLabel("Stage: Acidic Region")
        self.lbl_stage.setStyleSheet("font-size: 14px; color: #2c3e50; padding: 6px;")
        layout.addWidget(self.lbl_stage)

        # Title
        title = QLabel("Interactive Titration Lab")
        title.setStyleSheet("font-weight: bold; font-size: 20px; color: #2c3e50; padding: 10px;")
        layout.addWidget(title)
        
        # pH Display
        self.lbl_ph = QLabel("pH: 1.00")
        self.lbl_ph.setStyleSheet("font-size: 32px; font-weight: bold; color: #e74c3c; "
                                  "background-color: #ecf0f1; padding: 15px; border-radius: 8px;")
        self.lbl_ph.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_ph)
        
        # Drops counter
        self.lbl_drops = QLabel("Drops: 0")
        self.lbl_drops.setStyleSheet("font-size: 16px; color: #34495e; padding: 5px;")
        layout.addWidget(self.lbl_drops)
        
        # Valve control
        control_group = QGroupBox("Controls")
        control_layout = QVBoxLayout()
        
        self.btn_valve = QPushButton("Open Valve")
        self.btn_valve.setStyleSheet("QPushButton { background-color: #3498db; color: white; "
                                     "font-size: 14px; padding: 10px; border-radius: 5px; }"
                                     "QPushButton:hover { background-color: #2980b9; }")
        self.btn_valve.clicked.connect(self.toggle_valve)
        control_layout.addWidget(self.btn_valve)
        
        # Flow rate slider
        control_layout.addWidget(QLabel("Flow Rate:"))
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(1, 10)
        self.slider.setValue(2)
        self.slider.valueChanged.connect(self.animation.set_drop_rate)
        control_layout.addWidget(self.slider)
        
        # Indicator toggle
        self.btn_indicator = QPushButton("Toggle Indicator")
        self.btn_indicator.setStyleSheet("padding: 8px; font-size: 12px;")
        self.btn_indicator.clicked.connect(self.animation.toggle_indicator)
        control_layout.addWidget(self.btn_indicator)
        
        # Reset button
        self.btn_reset = QPushButton("Reset Experiment")
        self.btn_reset.setStyleSheet("QPushButton { background-color: #e67e22; color: white; "
                                     "padding: 10px; border-radius: 5px; }"
                                     "QPushButton:hover { background-color: #d35400; }")
        self.btn_reset.clicked.connect(self.reset_experiment)
        control_layout.addWidget(self.btn_reset)
        
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        
        # Info section
        info = QLabel("Strong Acid (HCl) vs Strong Base (NaOH)\nIndicator: Phenolphthalein")
        info.setStyleSheet("font-size: 11px; color: #7f8c8d; padding: 10px;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        layout.addStretch()
        self.setLayout(layout)
        
        # Theory box
        self.theory_box = QLabel("")
        self.theory_box.setWordWrap(True)
        self.theory_box.setStyleSheet(
            "font-size: 12px; color: #2c3e50; background-color: #f8f9fa; "
            "padding: 10px; border-radius: 6px; border: 1px solid #dcdde1;"
        )
        layout.addWidget(self.theory_box)

        # Update timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_labels)
        self.timer.start(100)
    
    def toggle_valve(self):
        self.animation.toggle_valve()
        if self.animation.burette_valve_open:
            self.btn_valve.setText("Close Valve")
            self.btn_valve.setStyleSheet("QPushButton { background-color: #e74c3c; color: white; "
                                        "font-size: 14px; padding: 10px; border-radius: 5px; }"
                                        "QPushButton:hover { background-color: #c0392b; }")
        else:
            self.btn_valve.setText("Open Valve")
            self.btn_valve.setStyleSheet("QPushButton { background-color: #3498db; color: white; "
                                        "font-size: 14px; padding: 10px; border-radius: 5px; }"
                                        "QPushButton:hover { background-color: #2980b9; }")
    
    def reset_experiment(self):
        self.animation.reset_animation()
        self.graph.reset()
        self.animation.graph_callback = self.graph.update_graph
        self.btn_valve.setText("Open Valve")
        self.btn_valve.setStyleSheet("QPushButton { background-color: #3498db; color: white; "
                                    "font-size: 14px; padding: 10px; border-radius: 5px; }"
                                    "QPushButton:hover { background-color: #2980b9; }")
    
    def update_labels(self):
        self.lbl_ph.setText(f"pH: {self.animation.ph_value:.2f}")
        self.lbl_drops.setText(f"Drops: {self.animation.total_drops}")
        
        if self.animation.ph_value < 6.5:
            stage = "Before Equivalence (Acidic)"
        elif 6.5 <= self.animation.ph_value <= 7.5:
            stage = "Near Equivalence Point"
        else:
            stage = "After Equivalence (Basic)"

        self.lbl_stage.setText("Stage: " + stage)

        if "Before" in stage:
            theory = (
                "The solution is strongly acidic. Added NaOH is being neutralized by excess HCl.\n"
                "pH increases slowly because H+ ions are still in large excess."
            )
        elif "Near" in stage:
            theory = (
                "The equivalence point is near. Small additions of base cause a rapid pH increase.\n"
                "Moles of acid ≈ moles of base."
            )
        else:
            theory = (
                "All acid has been neutralized. The solution now contains excess OH⁻ ions.\n"
                "pH increases slowly again."
            )

        self.theory_box.setText("Theory:\n" + theory)

        # Color-code pH label
        if self.animation.ph_value < 7:
            color = "#e74c3c"  # Red for acidic
        elif self.animation.ph_value > 7:
            color = "#9b59b6"  # Purple for basic
        else:
            color = "#27ae60"  # Green for neutral
        
        self.lbl_ph.setStyleSheet(f"font-size: 32px; font-weight: bold; color: {color}; "
                                 f"background-color: #ecf0f1; padding: 15px; border-radius: 8px;")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Enhanced Interactive Titration Laboratory")
        self.setFixedSize(1400, 750)
        
        # Main container
        container = QWidget()
        main_layout = QHBoxLayout(container)
        
        # Create widgets
        self.graph = GraphWidget()
        self.animation = TitrationAnimation(self.graph.update_graph)
        self.controls = ControlPanel(self.animation, self.graph)
        
        # Add widgets to layout
        main_layout.addWidget(self.controls, 1)
        main_layout.addWidget(self.animation, 2)
        main_layout.addWidget(self.graph, 2)
        
        self.setCentralWidget(container)
        
        # Set initial drop rate
        self.animation.set_drop_rate(2)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())