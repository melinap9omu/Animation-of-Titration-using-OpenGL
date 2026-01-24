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
        fig = Figure(dpi=100)
        fig.tight_layout()
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

        # Mark equivalence point
        self.axes.scatter([6.0], [7.0], color="blue", s=60, zorder=5)
        self.axes.text(6.1, 7.2, "Equivalence Point", fontsize=9, color="blue")

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

    def draw_lathed_surface(profile, slices=64):
        """
        Revolves a 2D profile around Y axis to form a solid.
        profile = [(y, radius), ...]
        """
        for i in range(len(profile)-1):
            y1, r1 = profile[i]
            y2, r2 = profile[i+1]

            glBegin(GL_QUAD_STRIP)
            for j in range(slices+1):
                theta = 2 * math.pi * j / slices
                x1 = r1 * math.cos(theta)
                z1 = r1 * math.sin(theta)
                x2 = r2 * math.cos(theta)
                z2 = r2 * math.sin(theta)

                glVertex3f(x1, y1, z1)
                glVertex3f(x2, y2, z2)
            glEnd()

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
        self.reaction_type = "SA_SB"  # or "weak"
        self.acid_molarity = 0.1
        self.base_molarity = 0.1
        self.acid_volume_ml = 50
        self.rot_y = 0
        self.last_mouse_pos = None

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
        glEnable(GL_LINE_SMOOTH)
        glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)
        glEnable(GL_NORMALIZE)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)
        glEnable(GL_DEPTH_TEST)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)

        glLightfv(GL_LIGHT0, GL_POSITION, [2, 5, 5, 1])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [1, 1, 1, 1])
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.3, 0.3, 0.3, 1])
        glLightfv(GL_LIGHT0, GL_SPECULAR, [1, 1, 1, 1])

        glDepthFunc(GL_LEQUAL)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDisable(GL_CULL_FACE)

    def draw_disk(self, r, slices=32):
        quad = gluNewQuadric()
        gluDisk(quad, 0, r, slices, 1)

    def draw_lathed_surface(self, profile, slices=64):
        for i in range(len(profile) - 1):
            y1, r1 = profile[i]
            y2, r2 = profile[i + 1]

            glBegin(GL_QUAD_STRIP)
            for j in range(slices + 1):
                theta = 2 * math.pi * j / slices
                c = math.cos(theta)
                s = math.sin(theta)

                glNormal3f(c, 0, s)
                glVertex3f(r1 * c, y1, r1 * s)
                glVertex3f(r2 * c, y2, r2 * s)
            glEnd()

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(-2, 2, -2, 2, -10, 10)
        glMatrixMode(GL_MODELVIEW)

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
            self.droplets.append(Droplet(0.0, 0.8))
        
        # Update droplets
        surface_y = self.flask_bottom_y + self.liquid_level
        for drop in self.droplets[:]:
            drop.update()
            if drop.y < surface_y:
                # Drop hit the liquid surface
                self.total_drops += 1
                self.volume_ml = self.total_drops * self.ml_per_drop
                self.liquid_level = min(self.liquid_level + 0.0015, 0.7)

                # CHEMISTRY MODEL
                Ka = 1.8e-5   # weak acid (acetic acid)
                Kb = 1.8e-5   # weak base (ammonia)

                added_base_ml = self.volume_ml
                acid_moles = self.acid_molarity * (self.acid_volume_ml / 1000)
                base_moles = self.base_molarity * (added_base_ml / 1000)

                total_volume_L = (self.acid_volume_ml + added_base_ml) / 1000
                eps = 1e-12

                rt = self.reaction_type

                # STRONG ACID + STRONG BASE
                if rt == "SA_SB":
                    if base_moles < acid_moles:
                        H = (acid_moles - base_moles) / total_volume_L
                        self.ph_value = -math.log10(max(H, eps))
                    elif abs(base_moles - acid_moles) < 1e-6:
                        self.ph_value = 7.0
                    else:
                        OH = (base_moles - acid_moles) / total_volume_L
                        pOH = -math.log10(max(OH, eps))
                        self.ph_value = 14 - pOH

                # WEAK ACID + STRONG BASE
                elif rt == "WA_SB":
                    if base_moles < acid_moles:
                        # Henderson-Hasselbalch
                        HA = acid_moles - base_moles
                        A = base_moles
                        if A < eps:
                            H = math.sqrt(Ka * self.acid_molarity)
                            self.ph_value = -math.log10(H)
                        else:
                            pKa = -math.log10(Ka)
                            self.ph_value = pKa + math.log10(A / HA)
                    elif abs(base_moles - acid_moles) < 1e-6:
                        # weak acid salt
                        C = acid_moles / total_volume_L
                        Kb_eff = 1e-14 / Ka
                        OH = math.sqrt(Kb_eff * C)
                        self.ph_value = 14 + math.log10(OH)
                    else:
                        OH = (base_moles - acid_moles) / total_volume_L
                        pOH = -math.log10(max(OH, eps))
                        self.ph_value = 14 - pOH

                # STRONG ACID + WEAK BASE
                elif rt == "SA_WB":
                    if base_moles < acid_moles:
                        H = (acid_moles - base_moles) / total_volume_L
                        self.ph_value = -math.log10(max(H, eps))
                    elif abs(base_moles - acid_moles) < 1e-6:
                        # acidic salt
                        C = acid_moles / total_volume_L
                        Ka_eff = 1e-14 / Kb
                        H = math.sqrt(Ka_eff * C)
                        self.ph_value = -math.log10(H)
                    else:
                        B = base_moles - acid_moles
                        OH = math.sqrt(Kb * (B / total_volume_L))
                        pOH = -math.log10(max(OH, eps))
                        self.ph_value = 14 - pOH

                # WEAK ACID + WEAK BASE
                else:  # WA_WB
                    # depends on Ka vs Kb
                    if abs(Ka - Kb) < 1e-10:
                        self.ph_value = 7.0
                    elif Ka > Kb:
                        self.ph_value = 6.0
                    else:
                        self.ph_value = 8.0
                
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
        glDisable(GL_LIGHTING)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glTranslatef(0, -0.3, -5.5)
        glRotatef(-10, 1, 0, 0)

        # STAND
        glColor3f(0.15, 0.15, 0.15)

        # Base
        glPushMatrix()
        glTranslatef(1.2, -1.25, 0)
        glScalef(0.8, 0.05, 0.8)
        self.draw_disk(1.0)
        glPopMatrix()

        # Vertical rod
        glPushMatrix()
        glTranslatef(1.2, -1.25, 0)
        self.draw_cylinder(0.05, 2.6)
        glPopMatrix()

        # Horizontal arm
        glPushMatrix()
        glTranslatef(1.2, 0.8, 0)
        glRotatef(90, 0, 0, 1)
        self.draw_cylinder(0.04, 1.0)
        glPopMatrix()

        # Clamp block
        glPushMatrix()
        glTranslatef(0.7, 0.8, 0)
        glScalef(0.15, 0.15, 0.15)
        self.draw_sphere(1)
        glPopMatrix()

        # BURETTE
        glColor4f(0.85, 0.92, 1.0, 0.25)
        glPushMatrix()
        glTranslatef(0.0, 1.0, 0)
        self.draw_cylinder(0.08, 2.4)
        glPopMatrix()

        # Tip
        glColor3f(0.6, 0.6, 0.6)
        glPushMatrix()
        glTranslatef(0.0, -0.2, 0)
        self.draw_cylinder(0.025, 0.25)
        glPopMatrix()

        # SHADOW
        glColor4f(0, 0, 0, 0.2)
        glPushMatrix()
        glTranslatef(0.1, -1.25, -0.5)
        glScalef(1.2, 0.3, 1)
        self.draw_disk(0.9)
        glPopMatrix()

        # FLASK BODY (2.5D)
        glColor4f(0.7, 0.85, 1.0, 0.5)
        glBegin(GL_POLYGON)
        glVertex2f(-0.6, -1.0)
        glVertex2f(-0.8, -0.2)
        glVertex2f(-0.3, 0.3)
        glVertex2f(0.3, 0.3)
        glVertex2f(0.8, -0.2)
        glVertex2f(0.6, -1.0)
        glEnd()

        # FLASK OUTLINE
        glColor3f(0,0,0)
        glLineWidth(2)
        glBegin(GL_LINE_LOOP)
        glVertex2f(-0.6, -1.0)
        glVertex2f(-0.8, -0.2)
        glVertex2f(-0.3, 0.3)
        glVertex2f(0.3, 0.3)
        glVertex2f(0.8, -0.2)
        glVertex2f(0.6, -1.0)
        glEnd()

        # LIQUID
        r,g,b = self.get_solution_color()
        h = min(0.9, self.liquid_level * 1.2)

        glColor4f(r, g, b, 0.8)
        glBegin(GL_POLYGON)
        glVertex2f(-0.5, -1.0)
        glVertex2f(-0.6, -1.0 + h)
        glVertex2f(0.6, -1.0 + h)
        glVertex2f(0.5, -1.0)
        glEnd()

        # DROPLETS
        glColor3f(0.2, 0.6, 1.0)
        for drop in self.droplets:
            glBegin(GL_POLYGON)
            for i in range(12):
                a = 2*math.pi*i/12
                glVertex2f(0.0 + 0.03*math.cos(a), drop.y + 0.03*math.sin(a))
            glEnd()

    def draw_cylinder(self, r, h, slices=32):
        quad = gluNewQuadric()
        gluCylinder(quad, r, r, h, slices, 1)

    def draw_sphere(self, r):
        quad = gluNewQuadric()
        gluSphere(quad, r, 20, 20)

    def mousePressEvent(self, event):
        self.last_mouse_pos = event.pos()

    def mouseMoveEvent(self, event):
        if self.last_mouse_pos:
            dx = event.x() - self.last_mouse_pos.x()
            self.last_mouse_pos = event.pos()
            self.update()

    def toggle_valve(self):
        self.burette_valve_open = not self.burette_valve_open
    
    def set_drop_rate(self, val):
        self.drop_rate = val / 50.0
    
    def toggle_indicator(self):
        self.indicator_active = not self.indicator_active
    
    def toggle_reaction_type(self):
        order = ["SA_SB", "WA_SB", "SA_WB", "WA_WB"]
        i = order.index(self.reaction_type)
        self.reaction_type = order[(i + 1) % len(order)]
        self.reset_animation()

    def set_parameters(self, acid_M, base_M, acid_vol):
        self.acid_molarity = acid_M
        self.base_molarity = base_M
        self.acid_volume_ml = acid_vol

        # Calculate equivalence volume
        # M1 V1 = M2 V2
        self.eq_volume_ml = (acid_M * acid_vol) / base_M

        self.reset_animation()

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
        
        # Parameters
        param_group = QGroupBox("Experiment Parameters")
        param_layout = QVBoxLayout()

        self.lbl_acid = QLabel("Acid Molarity (M): 0.10")
        self.lbl_base = QLabel("Base Molarity (M): 0.10")
        self.lbl_vol = QLabel("Acid Volume (mL): 50")

        self.slider_acid = QSlider(Qt.Horizontal)
        self.slider_acid.setRange(1, 100)
        self.slider_acid.setValue(10)

        self.slider_base = QSlider(Qt.Horizontal)
        self.slider_base.setRange(1, 100)
        self.slider_base.setValue(10)

        self.slider_vol = QSlider(Qt.Horizontal)
        self.slider_vol.setRange(10, 100)
        self.slider_vol.setValue(50)

        self.slider_acid.valueChanged.connect(self.update_params)
        self.slider_base.valueChanged.connect(self.update_params)
        self.slider_vol.valueChanged.connect(self.update_params)

        param_layout.addWidget(self.lbl_acid)
        param_layout.addWidget(self.slider_acid)
        param_layout.addWidget(self.lbl_base)
        param_layout.addWidget(self.slider_base)
        param_layout.addWidget(self.lbl_vol)
        param_layout.addWidget(self.slider_vol)

        param_group.setLayout(param_layout)
        layout.addWidget(param_group)

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
        
        # Reaction type toggle
        self.btn_reaction = QPushButton("Reaction: Strong Acid vs Strong Base")
        self.btn_reaction.setStyleSheet("padding: 8px; font-size: 12px;")
        self.btn_reaction.clicked.connect(self.toggle_reaction)
        control_layout.addWidget(self.btn_reaction)

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
    
    def toggle_reaction(self):
        self.animation.toggle_reaction_type()

        rt = self.animation.reaction_type

        if rt == "SA_SB":
            self.btn_reaction.setText("Strong Acid vs Strong Base")
        elif rt == "WA_SB":
            self.btn_reaction.setText("Weak Acid vs Strong Base")
        elif rt == "SA_WB":
            self.btn_reaction.setText("Strong Acid vs Weak Base")
        else:
            self.btn_reaction.setText("Weak Acid vs Weak Base")

    def reset_experiment(self):
        self.animation.reset_animation()
        self.graph.reset()
        self.animation.graph_callback = self.graph.update_graph
        self.btn_valve.setText("Open Valve")
        self.btn_valve.setStyleSheet("QPushButton { background-color: #3498db; color: white; "
                                    "font-size: 14px; padding: 10px; border-radius: 5px; }"
                                    "QPushButton:hover { background-color: #2980b9; }")
    
    def update_params(self):
        acid = self.slider_acid.value() / 100
        base = self.slider_base.value() / 100
        vol = self.slider_vol.value()

        self.lbl_acid.setText(f"Acid Molarity (M): {acid:.2f}")
        self.lbl_base.setText(f"Base Molarity (M): {base:.2f}")
        self.lbl_vol.setText(f"Acid Volume (mL): {vol}")

        self.animation.set_parameters(acid, base, vol)

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
        self.resize(1600, 900)
        self.setMinimumSize(1200, 700)
        self.showMaximized()
        
        # Main container
        container = QWidget()
        main_layout = QHBoxLayout(container)
        
        # Create widgets
        self.graph = GraphWidget()
        self.animation = TitrationAnimation(self.graph.update_graph)
        self.controls = ControlPanel(self.animation, self.graph)
        
        # Add widgets to layout
        main_layout.addWidget(self.controls, 2)
        main_layout.addWidget(self.animation, 5)
        main_layout.addWidget(self.graph, 5)

        self.setCentralWidget(container)
        
        # Set initial drop rate
        self.animation.set_drop_rate(2)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())