from mesa.visualization.modules import CanvasGrid
from mesa.visualization.ModularVisualization import ModularServer

from model import CityModel, Car, TrafficLight, Obstacle, Destination

def agent_portrayal(agent):
    """
    Define cómo se visualiza cada agente en la interfaz web.
    """
    if agent is None:
        return
    
    portrayal = {
        "Shape": "circle",
        "Filled": "true",
        "Layer": 0,
        "w": 1,
        "h": 1
    }

    if isinstance(agent, Car):
        portrayal["Shape"] = "circle"
        portrayal["Color"] = "red"
        portrayal["r"] = 0.5
        portrayal["Layer"] = 1
        portrayal["text"] = str(agent.unique_id)
        portrayal["text_color"] = "white"

    elif isinstance(agent, TrafficLight):
        portrayal["Shape"] = "circle"
        portrayal["Color"] = "green" if agent.state == "Green" else ("yellow" if agent.state == "Yellow" else "red")
        portrayal["r"] = 0.5
        portrayal["Layer"] = 1
        portrayal["text"] = agent.direction
        portrayal["text_color"] = "black"

    elif isinstance(agent, Obstacle):
        portrayal["Shape"] = "rect"
        portrayal["Color"] = "grey"
        portrayal["w"] = 1
        portrayal["h"] = 1
        portrayal["Layer"] = 0

    elif isinstance(agent, Destination):
        portrayal["Shape"] = "rect"
        portrayal["Color"] = "blue"
        portrayal["w"] = 1
        portrayal["h"] = 1
        portrayal["Layer"] = 0
        
    return portrayal

# Configuración del grid
# El mapa es de 24x24
width = 24
height = 24
pixel_ratio = 20  # Pixeles por celda
grid = CanvasGrid(agent_portrayal, width, height, width * pixel_ratio, height * pixel_ratio)

# Configuración del servidor
server = ModularServer(
    CityModel,
    [grid],
    "Traffic Simulation",
    {"width": width, "height": height}
)

server.port = 8521 # Puerto por defecto

if __name__ == "__main__":
    server.launch()
