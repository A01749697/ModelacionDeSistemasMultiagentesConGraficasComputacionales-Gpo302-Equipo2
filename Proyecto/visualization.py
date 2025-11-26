from mesa.visualization.modules import CanvasGrid #type: ignore
from mesa.visualization.ModularVisualization import ModularServer #type: ignore
from mesa.visualization.UserParam import Slider #type: ignore

from model import CityModel,Car,TrafficLight,Obstacle,Destination


def agent_portrayal(agent):
    
    if isinstance(agent,Car):
        return{
            "shape":"rect",
            "w":0.8,
            "h":0.4,
            "color":"blue",
            "Layer": 2,
            "text": f"agent position: {agent.destination}",
            "text_color": "white"
        }
        
    if isinstance(agent, TrafficLight):
        color = {
            "Green": "green",
            "Yellow": "yellow",
            "Red": "red"
        }[agent.state]

        return {
            "Shape": "circle",
            "r": 0.5,
            "Color": color,
            "Layer": 3,
            "text": agent.direction,
            "text_color": "black"
        }
        
    # OBSTÁCULOS
    if isinstance(agent, Obstacle):
        return {
            "Shape": "rect",
            "w": 1,
            "h": 1,
            "Color": "black",
            "Layer": 0
        }

    # DESTINOS
    if isinstance(agent, Destination):
        return {
            "Shape": "rect",
            "w": 0.8,
            "h": 0.8,
            "Color": "purple",
            "Layer": 1
        }
