import matplotlib.pyplot as plt

class TitrationGraph:
    def __init__(self):
        plt.ion()
        self.fig, self.ax = plt.subplots()
        self.line, = self.ax.plot([], [])
        self.ax.set_xlabel("Volume")
        self.ax.set_ylabel("pH")
        self.ax.set_title("Titration Curve")

    def update(self, data):
        if not data:
            return
        x = [d[0] for d in data]
        y = [d[1] for d in data]
        self.line.set_data(x, y)
        self.ax.relim()
        self.ax.autoscale_view()
        plt.draw()
        plt.pause(0.001)