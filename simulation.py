import math

class TitrationSimulation:
    def __init__(self):
        self.volume = 0.0
        self.max_volume = 50.0
        self.running = False
        self.finished = False

        self.data = []  # (volume, pH)

    def reset(self):
        self.__init__()

    def start_stop(self):
        self.running = not self.running

    def update(self, dt):
        if not self.running or self.finished:
            return

        self.volume += dt * 0.5  # speed

        if self.volume >= self.max_volume:
            self.finished = True
            self.running = False

        pH = self.compute_pH(self.volume)
        self.data.append((self.volume, pH))

    def compute_pH(self, v):
        # kinda lowk fake but realistic titration curve using sigmoid
        x = (v - 25) / 3
        sigmoid = 1 / (1 + math.exp(-x))
        return 2 + 10 * sigmoid  # from ~2 to ~12