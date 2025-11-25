# model_mesa_example.py
# Copia/pega esto como referencia; adapta nombres/paths si ya tienes model.py
from mesa import Model, Agent
from mesa.space import MultiGrid
from mesa.time import RandomActivation
import networkx as nx
import random

# Mapa simplificado 24x24 (usa tu city_map si lo tienes)
city_map = [
    "v<<<<<<<<<<<S<<<<<<<<<<<",
    "v<<<<<<<<<<<S<<<<<<<<<<^",
    "vv##vv##vvSS########D#^^",
    "SS#Dvv##vv^^#D########^^",
    "vvS<<<<<vv^^>>>>>>>>>>S^",
    "vvS<<<<<vv^^>>>>>>>>>>S^",
    "vv##^^##vv^^#######D##SS",
    "SS##^^##vv^^##########^^",
    "vvS<<<<<<<<<<<<<<<<<<<^^",
    "vvS<<<<<v##^>>>>>>>>>>^^",
    "vv>>>>>>v##^>>>>>>>>>S^^",
    "vv>>>>>>>>>>>>>>>>>>>S^^",
    "vv#D^^##vv^^####vv####SS",
    "vv##^^##vv^^####vv####^^",
    "vv##^^##vv^^##D#vv####^^",
    "vv##^^D#vv^^<<<<vv###D^^",
    "vv>>>>>>vv^^<<<<vv####^^",
    "vv>>>>>>vv^^####vv####^^",
    "vv####D#vv^^D###vv####^^",
    "vv######vv^^####vvD###^^",
    "vv######vv^^####vv####^^",
    "vv##D###SS^^##D#SS####^^",
    "vv>>>>>>S>>>>>>S>>>>>>^^",
    ">>>>>>>>S>>>>>>S>>>>>>^^"
]

class Car(Agent):
    """Vehículo agent con destino y path (usa networkx shortest_path)."""
    def __init__(self, unique_id, model, destination=None, origin=None):
        super().__init__(unique_id, model)
        self.destination = destination
        self.path = []
        self.origin = origin
        self.arrived = False

    def step(self):
        if self.arrived:
            return
        if not self.path and self.destination:
            self.calculate_path()
        if self.path:
            next_pos = self.path[0]
            if self.can_move_to(next_pos):
                try:
                    self.model.grid.move_agent(self, next_pos)
                except Exception:
                    pass
                self.path.pop(0)
                if self.pos == self.destination:
                    self.arrived = True
                    # opcional: eliminar del schedule / grid
                    try:
                        self.model.grid.remove_agent(self)
                    except Exception:
                        pass
                    try:
                        self.model.schedule.remove(self)
                    except Exception:
                        pass

    def calculate_path(self):
        if self.destination and self.pos in self.model.G and self.destination in self.model.G:
            try:
                sp = nx.shortest_path(self.model.G, self.pos, self.destination)
                if len(sp) > 0:
                    # quitar la posición actual
                    if sp[0] == self.pos:
                        sp = sp[1:]
                self.path = sp
            except nx.NetworkXNoPath:
                self.path = []

    def can_move_to(self, pos):
        # Evitar colisión con otro coche
        contents = self.model.grid.get_cell_list_contents([pos])
        for a in contents:
            if isinstance(a, Car):
                return False
            if isinstance(a, TrafficLight):
                dx = pos[0] - self.pos[0]
                dy = pos[1] - self.pos[1]
                if dy != 0 and a.direction == "NS":
                    return a.state == "Green"
                if dx != 0 and a.direction == "EW":
                    return a.state == "Green"
        return True

class TrafficLight(Agent):
    """Semáforo que cicla Green->Yellow->Red con timers."""
    def __init__(self, unique_id, model, direction="NS", green_time=6, yellow_time=2, red_time=6):
        super().__init__(unique_id, model)
        self.state = "Green"
        self.direction = direction
        self.timer = green_time
        self.green_time = green_time
        self.yellow_time = yellow_time
        self.red_time = red_time

    def step(self):
        self.timer -= 1
        if self.timer <= 0:
            if self.state == "Green":
                self.state = "Yellow"
                self.timer = self.yellow_time
            elif self.state == "Yellow":
                self.state = "Red"
                self.timer = self.red_time
            elif self.state == "Red":
                self.state = "Green"
                self.timer = self.green_time

class Obstacle(Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
    def step(self): pass

class Destination(Agent):
    def __init__(self, unique_id, model, parking_number=None):
        super().__init__(unique_id, model)
        self.parking_number = parking_number
    def step(self): pass

class CityModel(Model):
    """Modelo principal. Mantiene grid, schedule, grafo de navegación y lista de destinos."""
    def __init__(self, width=24, height=24):
        super().__init__()
        self.grid = MultiGrid(width, height, torus=False)
        self.schedule = RandomActivation(self)
        self.next_id = 1
        self.G = nx.DiGraph()
        self.destinations = []
        self.setup_map()
        self.setup_graph()

    def setup_map(self):
        for row in range(len(city_map)):
            for col in range(len(city_map[row])):
                cell = city_map[row][col]
                x = col
                y = 23 - row
                if cell == '#':
                    o = Obstacle(self.next_id, self)
                    self.next_id += 1
                    self.grid.place_agent(o, (x,y))
                    self.schedule.add(o)
                elif cell == 'S':
                    d = "NS" if (row+col)%2==0 else "EW"
                    t = TrafficLight(self.next_id, self, direction=d)
                    self.next_id += 1
                    self.grid.place_agent(t,(x,y))
                    self.schedule.add(t)
                elif cell == 'D':
                    dest = Destination(self.next_id, self, parking_number=len(self.destinations)+1)
                    self.next_id += 1
                    self.grid.place_agent(dest,(x,y))
                    self.schedule.add(dest)
                    self.destinations.append((x,y))
        # Nota: no colocamos coches en setup_map por defecto

    def setup_graph(self):
        W, H = 24, 24
        for row in range(len(city_map)):
            for col in range(len(city_map[row])):
                cell = city_map[row][col]
                x = col; y = 23 - row
                if cell in ['v','^','<','>','S','D']:
                    self.G.add_node((x,y))
                    if cell == 'v' and y>0: self.G.add_edge((x,y),(x,y-1))
                    if cell == '^' and y< H-1: self.G.add_edge((x,y),(x,y+1))
                    if cell == '>' and x< W-1: self.G.add_edge((x,y),(x+1,y))
                    if cell == '<' and x>0: self.G.add_edge((x,y),(x-1,y))
                    if cell == 'S' or cell == 'D':
                        for dx,dy in [(0,1),(0,-1),(1,0),(-1,0)]:
                            nx_pos = (x+dx, y+dy)
                            if 0<=nx_pos[0]<W and 0<=nx_pos[1]<H:
                                self.G.add_edge((x,y), nx_pos)

    def spawn_car(self, start_pos=None, destination=None):
        if start_pos is None:
            start_pos = self.get_random_spawn_point()
        if destination is None and self.destinations:
            destination = random.choice(self.destinations)
        car = Car(self.next_id, self, destination=destination, origin=start_pos)
        self.next_id += 1
        self.grid.place_agent(car, start_pos)
        self.schedule.add(car)
        return car

    def get_random_spawn_point(self):
        valid = []
        for row in range(len(city_map)):
            for col in range(len(city_map[row])):
                cell = city_map[row][col]
                if cell in ['v','^','<','>']:
                    x = col; y = 23-row
                    valid.append((x,y))
        return random.choice(valid) if valid else (0,0)

    def step(self):
        self.schedule.step()

    def all_cars_arrived(self):
        for a in self.schedule.agents:
            if isinstance(a, Car) and not a.arrived:
                return False
        return True

    def serialize_grid(self):
        """Devuelve lista de dicts para visualización/servidor."""
        data = []
        for contents, x, y in self.grid.coord_iter():
            for a in contents:
                data.append({
                    "id": getattr(a, "unique_id", None),
                    "x": x, "y": y,
                    "agent_type": type(a).__name__,
                    "state": getattr(a, "state", None),
                    "direction": getattr(a, "direction", None),
                    "origin": getattr(a, "origin", None),
                    "destination": getattr(a, "destination", None),
                    "parking_number": getattr(a, "parking_number", None),
                    "arrived": getattr(a, "arrived", None)
                })
        return data