import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import random

class TitrationAnimation:
    def __init__(self):
        self.burette_level = 0.8
        self.flask_level = 0.2
        self.flask_color = [1.0, 0.3, 0.3]
        self.dispensing = False
        self.titration_complete = False
        self.drops = []

    # ---------- GLU Helpers ----------
    def draw_cylinder(self, radius, height, slices=30):
        quad = gluNewQuadric()
        gluCylinder(quad, radius, radius, height, slices, 1)

    def draw_cone(self, base_radius, height, slices=20):
        quad = gluNewQuadric()
        gluCylinder(quad, base_radius, 0.0, height, slices, 1)

    def draw_sphere(self, radius, slices=12, stacks=12):
        quad = gluNewQuadric()
        gluSphere(quad, radius, slices, stacks)

    # ---------- Objects ----------
    def draw_burette(self):
        glPushMatrix()
        glTranslatef(0, 1.5, 0)

        # Burette body
        glColor4f(0.8, 0.9, 1.0, 0.3)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self.draw_cylinder(0.08, 1.5)

        # Burette liquid
        glPushMatrix()
        glColor4f(0.3, 0.3, 1.0, 0.6)
        self.draw_cylinder(0.075, 1.5 * self.burette_level)
        glPopMatrix()

        # Tip
        glPushMatrix()
        glTranslatef(0, -0.15, 0)
        glColor4f(0.8, 0.9, 1.0, 0.3)
        glRotatef(180, 1, 0, 0)
        self.draw_cone(0.04, 0.1)
        glPopMatrix()

        glPopMatrix()

    def draw_flask(self):
        glPushMatrix()
        glTranslatef(0, -0.5, 0)

        # Flask body (glass)
        glColor4f(0.8, 0.9, 1.0, 0.2)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        quad = gluNewQuadric()
        gluCylinder(quad, 0.4, 0.0, 0.8, 30, 1)

        # Neck
        glPushMatrix()
        glTranslatef(0, 0.8, 0)
        self.draw_cylinder(0.15, 0.4)
        glPopMatrix()

        # Liquid
        if self.flask_level > 0:
            glPushMatrix()
            glColor4f(*self.flask_color, 0.7)
            liquid_height = min(self.flask_level * 1.2, 0.8)
            liquid_radius = (liquid_height / 0.8) * 0.4
            glRotatef(180, 1, 0, 0)
            self.draw_cone(liquid_radius, liquid_height)
            glPopMatrix()

        glPopMatrix()

    def draw_drops(self):
        glColor4f(0.3, 0.3, 1.0, 0.8)
        for drop in self.drops:
            glPushMatrix()
            glTranslatef(drop[0], drop[1], drop[2])
            self.draw_sphere(0.02)
            glPopMatrix()

    # ---------- Update ----------
    def update(self, dt):
        if self.dispensing and not self.titration_complete:
            # Lower burette
            self.burette_level = max(0, self.burette_level - 0.05 * dt)

            # Add new drops at tip
            if len(self.drops) < 6:
                x_jitter = random.uniform(-0.01, 0.01)
                z_jitter = random.uniform(-0.01, 0.01)
                self.drops.append([x_jitter, 1.35, z_jitter])

            # Update drops
            new_drops = []
            for drop in self.drops:
                drop[1] -= 1.0 * dt  # fall speed
                # Check collision with flask liquid
                if drop[1] <= -0.5 + self.flask_level:
                    # Merge with flask
                    self.flask_level = min(0.8, self.flask_level + 0.01)
                else:
                    new_drops.append(drop)
            self.drops = new_drops

            # Color transition
            progress = min(1.0, (0.8 - self.burette_level) / 0.6)
            self.flask_color = [
                1.0 - 0.2 * progress,
                0.3 + 0.4 * progress,
                0.3 + 0.7 * progress
            ]

            # Endpoint
            if progress > 0.85:
                self.titration_complete = True
                self.flask_color = [0.9, 0.7, 1.0]

    def render(self):
        self.draw_burette()
        self.draw_flask()
        self.draw_drops()

# ---------------- MAIN ------------------
def main():
    pygame.init()
    display = (800, 600)
    pygame.display.set_mode(display, DOUBLEBUF | OPENGL)
    pygame.display.set_caption("Titration Animation")

    glEnable(GL_DEPTH_TEST)
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
    glLightfv(GL_LIGHT0, GL_POSITION, [2,2,2,1])
    glLightfv(GL_LIGHT0, GL_AMBIENT, [0.3,0.3,0.3,1])
    glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.8,0.8,0.8,1])

    gluPerspective(45, display[0]/display[1], 0.1, 50.0)
    gluLookAt(0,0,5, 0,0,0, 0,1,0)  # proper camera

    titration = TitrationAnimation()
    clock = pygame.time.Clock()
    rotation = 0
    mouse_down = False

    print("Controls: SPACE - Start/Stop, R - Reset, Mouse - Rotate, ESC - Exit")

    running = True
    while running:
        dt = clock.tick(60) / 10.0  # adjust animation speed

        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE: running = False
                elif event.key == K_SPACE: titration.dispensing = not titration.dispensing
                elif event.key == K_r: titration = TitrationAnimation()
            elif event.type == MOUSEBUTTONDOWN: mouse_down = True
            elif event.type == MOUSEBUTTONUP: mouse_down = False
            elif event.type == MOUSEMOTION and mouse_down: rotation += event.rel[0]

        # Update
        titration.update(dt)

        # Render
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glPushMatrix()
        glRotatef(rotation * 0.5, 0, 1, 0)
        titration.render()
        glPopMatrix()
        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()
