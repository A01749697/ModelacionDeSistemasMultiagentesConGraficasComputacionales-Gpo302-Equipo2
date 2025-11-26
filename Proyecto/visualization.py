# visualization.py
from mesa.visualization.ModularVisualization import ModularServer  # type: ignore
from mesa.visualization.modules import CanvasGrid, TextElement  # type: ignore
from model import CityModel, Car, TrafficLight, Obstacle, Destination
import threading
import time

# Texto lateral: lista de autos con origen -> destino y estado
class CarInfoText(TextElement):
    def render(self, model):
        lines = []
        for a in model.schedule.agents:
            if type(a).__name__ == "Car":
                uid = getattr(a, "unique_id", "?")
                origin = getattr(a, "origin", None)
                dest = getattr(a, "destination", None)
                arrived = getattr(a, "arrived", False)
                status = "ARR" if arrived else "MOV"
                lines.append(f"{uid}: {origin} → {dest} [{status}]")
        return "<br/>".join(lines)

# Comprobación auxiliar: todos los coches llegaron?
def all_cars_arrived(model):
    for a in model.schedule.agents:
        if type(a).__name__ == "Car":
            if not getattr(a, "arrived", False):
                return False
    return True


# Portrayal visual
def agent_portrayal(agent):
    if agent is None:
        return None

    t = type(agent).__name__

    if t == "Car":
        return {
            "Shape": "rect",
            "w": 0.8,
            "h": 0.4,
            "Filled": "true",
            "Color": "blue" if not getattr(agent, "arrived", False) else "gray",
            "Layer": 3,
            "text": "A",
            "text_color": "white"
        }

    if t == "TrafficLight":
        state = getattr(agent, "state", "Green")
        color = {"Green": "green", "Yellow": "yellow", "Red": "red"}.get(state, "green")
        return {
            "Shape": "circle",
            "r": 0.5,
            "Filled": "true",
            "Color": color,
            "Layer": 2,
            "text": getattr(agent, "direction", ""),
            "text_color": "black"
        }

    if t == "Obstacle":
        return {
            "Shape": "rect",
            "w": 1,
            "h": 1,
            "Filled": "true",
            "Color": "black",
            "Layer": 0
        }

    if t == "Destination":
        return {
            "Shape": "rect",
            "w": 0.8,
            "h": 0.8,
            "Filled": "true",
            "Color": "purple",
            "Layer": 1,
            "text": str(getattr(agent, "parking_number", "")),
            "text_color": "white"
        }

    return None


# Grid y server
GRID_SIZE = 24
grid = CanvasGrid(agent_portrayal, GRID_SIZE, GRID_SIZE, 600, 600)
car_info = CarInfoText()

# ------------- INTEGRACIÓN CORRECTA DE PRE-SPAWN -------------
PRE_SPAWN = 5  # número de coches iniciales

server = ModularServer(
    CityModel,
    [grid, car_info],
    "CityModel Visualizer",
    {"pre_spawn": PRE_SPAWN}   # <-- se pasa aquí al modelo
)
# -------------------------------------------------------------


# Opcional: correr automáticamente
AUTO_RUN = False
STEP_INTERVAL = 0.2

def _auto_runner():
    time.sleep(1.0)
    m = server.model
    while not all_cars_arrived(m):
        m.step()
        time.sleep(STEP_INTERVAL)
    print("Auto-run: todos los coches llegaron.")

if AUTO_RUN:
    threading.Thread(target=_auto_runner, daemon=True).start()


if __name__ == "__main__":
    server.launch()