from mesa import Model, Agent
from mesa.space import MultiGrid
from mesa.time import RandomActivation
import networkx as nx
import random

# Ciudad Mapeada 24x24 (Racoon City)

city_map = [
    "v<<<<<<<<<<<S<<<<<<<<<<<", 
    "v<<<<<<<<<<<S<<<<<<<<<<^", 
    "vv##vv##vvSS########D#^^",
    "SS#Dvv##vv^^#D########^^",  
    "vvS<<<<<vv^^>>>>>>>>>S^^",  
    "vvS<<<<<vv^^>>>>>>>>>S^^", 
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
    "vv>>>>>S>>>>>>>S>>>>>>^^",
    ">>>>>>>S>>>>>>>S>>>>>>^^"   
]

class Car(Agent):
    """Agente que representa un vehículo en la simulación."""
    
    def __init__(self, unique_id, model, destination=None):
        super().__init__(unique_id, model)
        self.destination = destination  # Coordenada (x, y) del destino
        self.path = []  # Lista de coordenadas para seguir
        self.parking_time = 0  # Contador para tiempo en estacionamiento
        self.patience = 5 # Paciencia para recalcular ruta si se atasca
        
    def step(self):
        """Ejecuta un paso de movimiento del vehículo."""
        # Si estamos en el destino, esperar y luego desaparecer
        if self.pos == self.destination:
            self.parking_time += 1
            if self.parking_time > 3:
                # Liberar destino y eliminar agente
                if self.destination in self.model.occupied_destinations:
                    self.model.occupied_destinations.remove(self.destination)
                self.model.grid.remove_agent(self)
                self.model.schedule.remove(self)
            return
        
        # Si no tenemos ruta, calcularla
        if not self.path and self.destination:
            self.calculate_path()
        
        # Intentar moverse
        if self.path:
            next_pos = self.path[0]
            can_move = self.can_move_to(next_pos)
            
            if can_move:
                self.model.grid.move_agent(self, next_pos)
                self.path.pop(0)
                self.patience = 5 # Reset patience on move
            else:
                # Si no puede moverse, decrementar paciencia
                self.patience -= 1
                if self.patience <= 0:
                    # Paciencia agotada: intentar recalcular ruta (back-off)
                    self.calculate_path()
                    self.patience = 5 # Reset patience after recalc
    
    def calculate_path(self):
        """Calcula el camino más corto usando A* en el grafo de NetworkX."""
        if self.destination and self.pos in self.model.G and self.destination in self.model.G:
            try:
                self.path = nx.shortest_path(self.model.G, self.pos, self.destination)
                self.path.pop(0)  # Remover posición actual
            except nx.NetworkXNoPath:
                # No hay ruta posible - eliminar agente para evitar bloqueos
                # print(f"Car {self.unique_id} removed: No Path from {self.pos} to {self.destination}")
                self.model.grid.remove_agent(self)
                self.model.schedule.remove(self)
                self.path = []
    
    def can_move_to(self, pos):
        """Verifica si el coche puede moverse a la posición dada."""
        cell_contents = self.model.grid.get_cell_list_contents([pos])
        
        # No puede moverse si hay otro coche
        for agent in cell_contents:
            if isinstance(agent, Car):
                return False
            
            # Lógica estricta de semáforos
            if isinstance(agent, TrafficLight):
                # Detectar eje de movimiento real
                dx = pos[0] - self.pos[0]
                dy = pos[1] - self.pos[1]
                moving_vertically = (dy != 0)
                moving_horizontally = (dx != 0)
                
                if agent.direction == "NS":
                    if agent.state == "Green":
                        # NS pasa, EW espera
                        if moving_horizontally: return False
                    else:
                        # Red/Yellow: NS espera, EW pasa
                        if moving_vertically: return False
                        
                elif agent.direction == "EW":
                    if agent.state == "Green":
                        # EW pasa, NS espera
                        if moving_vertically: return False
                    else:
                        # Red/Yellow: EW espera, NS pasa
                        if moving_horizontally: return False
                
                return True # Si no bloquea, permite (el semáforo es pasable)
        
        return True


class TrafficLight(Agent):
    """Agente que representa un semáforo con 3 estados: Green, Yellow, Red."""
    
    def __init__(self, unique_id, model, direction="NS", state="Green", time_offset=0):
        super().__init__(unique_id, model)
        self.direction = direction  # "NS" (Norte-Sur) o "EW" (Este-Oeste)
        self.state = state
        self.timer = 10 - time_offset if state == "Green" else 10 # Ajuste simple
        
        # Tiempos por estado
        self.green_time = 10
        self.yellow_time = 3
        self.red_time = 10
        
    def step(self):
        """Cambia el estado del semáforo según el timer."""
        self.timer -= 1
        
        if self.timer <= 0:
            # Cambiar de estado cíclicamente
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
    """Agente que representa un edificio u obstáculo estático."""
    
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
    
    def step(self):
        """Los obstáculos no tienen lógica de paso."""
        pass


class Destination(Agent):
    """Agente que representa un destino/estacionamiento."""
    
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
    
    def step(self):
        """Los destinos no tienen lógica de paso."""
        pass


class CityModel(Model):
    """Modelo de la ciudad con tráfico urbano."""
    
    def __init__(self, pre_spawn=0, width=24, height=24):
        super().__init__()
        self.grid = MultiGrid(width, height, torus=False)  # NO TOROIDAL
        self.schedule = RandomActivation(self)
        
        # Grafo dirigido para navegación
        self.G = nx.DiGraph()
        
        # Listas para trackear agentes
        self.destinations = []
        self.occupied_destinations = set()  # Track de estacionamientos ocupados
        
        # Timer para prevenir teletransportación
        self.spawn_timer = 0
        
        # Inicializar el mapa
        self.setup_map()
        
        # Crear el grafo de navegación
        self.setup_graph()
        
        self.running = True # Required for Mesa visualization
        
        # Spawn inicial - 13 carros únicos
        while len([a for a in self.schedule.agents if isinstance(a, Car)]) < 13:
            if not self.spawn_car():
                break # Parar si no hay espacio o destinos
    
    def setup_map(self):
        """Lee city_map y coloca los agentes correspondientes en la grilla."""
        for row in range(len(city_map)):
            for col in range(len(city_map[row])):
                cell = city_map[row][col]
                
                # Conversión de coordenadas: (col, 23-row) para invertir Y
                x = col
                y = 23 - row
                
                if cell == '#':
                    # Crear obstáculo
                    obstacle = Obstacle(self.next_id(), self)
                    self.grid.place_agent(obstacle, (x, y))
                    self.schedule.add(obstacle)
                    
                elif cell == 'S':
                    # Crear semáforo con Sincronización por Vecindad
                    
                    direction = None
                    state = None
                    timer_value = 10
                    
                    # 1. Chequeo de Grupo (Sync): Verificar si hay semáforo a la IZQUIERDA
                    if col > 0 and city_map[row][col-1] == 'S':
                        # Buscar el agente TrafficLight en la posición izquierda
                        left_x = col - 1
                        left_y = 23 - row
                        left_agents = self.grid.get_cell_list_contents([(left_x, left_y)])
                        
                        for agent in left_agents:
                            if isinstance(agent, TrafficLight):
                                # Copiar atributos del semáforo vecino (Sincronización)
                                direction = agent.direction
                                state = agent.state
                                timer_value = agent.timer
                                break
                    
                    # 2. Si no hay vecino 'S' a la izquierda (Es un Líder)
                    if direction is None:
                        # Determinar dirección mirando el flujo de la calle
                        is_vertical = False
                        is_horizontal = False
                        
                        # Checar flujo vertical (v arriba o ^ abajo)
                        if row > 0 and city_map[row-1][col] == 'v': is_vertical = True
                        if row < len(city_map)-1 and city_map[row+1][col] == '^': is_vertical = True
                        
                        # Checar flujo horizontal (> izquierda o < derecha)
                        if col > 0 and city_map[row][col-1] == '>': is_horizontal = True
                        if col < len(city_map[row])-1 and city_map[row][col+1] == '<': is_horizontal = True
                        
                        # Determinar dirección basado en flujo detectado
                        if is_vertical:
                            direction = "NS"
                        elif is_horizontal:
                            direction = "EW"
                        else:
                            # Fallback: usar heurística original si no se detecta flujo claro
                            has_vertical = False
                            has_horizontal = False
                            
                            if row > 0 and city_map[row-1][col] in ['v', '^', 'S']: has_vertical = True
                            if row < len(city_map)-1 and city_map[row+1][col] in ['v', '^', 'S']: has_vertical = True
                            
                            if col > 0 and city_map[row][col-1] in ['<', '>', 'S']: has_horizontal = True
                            if col < len(city_map[row])-1 and city_map[row][col+1] in ['<', '>', 'S']: has_horizontal = True
                            
                            if has_vertical and not has_horizontal:
                                direction = "NS"
                            elif has_horizontal and not has_vertical:
                                direction = "EW"
                            else:
                                # Intersección: Alternar
                                direction = "NS" if (row + col) % 2 == 0 else "EW"
                        
                        # Establecer estado inicial basado en Exclusión Mutua
                        if direction == "NS":
                            state = "Green"
                            timer_value = 10
                        else:  # "EW"
                            state = "Red"
                            timer_value = 10  # Desfasado
                    
                    # Crear el semáforo con los atributos determinados/copiados
                    traffic_light = TrafficLight(self.next_id(), self, direction, state, 0)
                    traffic_light.timer = timer_value  # Asignar timer después de creación
                    self.grid.place_agent(traffic_light, (x, y))
                    self.schedule.add(traffic_light)
                    
                elif cell == 'D':
                    # Crear destino
                    destination = Destination(self.next_id(), self)
                    self.grid.place_agent(destination, (x, y))
                    self.schedule.add(destination)
                    self.destinations.append((x, y))
    
    def setup_graph(self):
        """Crea un grafo dirigido estricto basado en las flechas y reglas de tránsito."""
        self.G.clear()
        
        w = self.grid.width
        h = self.grid.height
        
        # Mapeo de direcciones a deltas (dx, dy)
        direction_deltas = {
            '^': (0, 1),
            'v': (0, -1),
            '>': (1, 0),
            '<': (-1, 0)
        }
        
        neighbor_offsets = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        
        for row in range(len(city_map)):
            for col in range(len(city_map[row])):
                cell = city_map[row][col]
                x = col
                y = 23 - row
                
                if cell == '#':
                    continue
                
                self.G.add_node((x, y))
                
                # REGLA DE INTEGRIDAD DE AUTOPISTA
                # 1. Identificar si la celda actual es parte de una vía multicarril
                is_highway = False
                if cell in direction_deltas:
                    # Determinar vecinos laterales según dirección
                    if cell in ['^', 'v']:  # Vertical: laterales son izquierda/derecha
                        lateral_offsets = [(1, 0), (-1, 0)]
                    else:  # Horizontal '<', '>': laterales son arriba/abajo
                        lateral_offsets = [(0, 1), (0, -1)]
                    
                    # Verificar si algún lateral tiene la misma dirección
                    for lat_dx, lat_dy in lateral_offsets:
                        lat_x = x + lat_dx
                        lat_y = y + lat_dy
                        
                        if 0 <= lat_x < w and 0 <= lat_y < h:
                            lat_row = 23 - lat_y
                            lat_col = lat_x
                            lateral_cell = city_map[lat_row][lat_col]
                            
                            if lateral_cell == cell:  # Misma dirección = Highway
                                is_highway = True
                                break
                
                for dx, dy in neighbor_offsets:
                    nx_x = x + dx
                    nx_y = y + dy
                    
                    if not (0 <= nx_x < w and 0 <= nx_y < h):
                        continue
                        
                    n_row = 23 - nx_y
                    n_col = nx_x
                    neighbor_cell = city_map[n_row][n_col]
                    
                    if neighbor_cell == '#':
                        continue
                        
                    can_connect = False
                    reason = ""
                    
                    # A. Conexión Frontal
                    if cell in direction_deltas:
                        expected_dx, expected_dy = direction_deltas[cell]
                        if (dx, dy) == (expected_dx, expected_dy):
                            is_contraflow = False
                            if cell == '^' and neighbor_cell == 'v': is_contraflow = True
                            if cell == 'v' and neighbor_cell == '^': is_contraflow = True
                            if cell == '>' and neighbor_cell == '<': is_contraflow = True
                            if cell == '<' and neighbor_cell == '>': is_contraflow = True
                            
                            if not is_contraflow:
                                can_connect = True
                                reason = "Forward"
                    
                    # B. Cambio de Carril
                    if cell in ['^', 'v', '<', '>'] and neighbor_cell == cell:
                        my_dir = direction_deltas[cell]
                        if my_dir[0]*dx + my_dir[1]*dy == 0:
                            can_connect = True
                            reason = "LaneChange"
                            
                    # C. Giros
                    if cell in direction_deltas and neighbor_cell in direction_deltas:
                        if cell in ['^', 'v'] and neighbor_cell in ['<', '>']:
                            n_dir = direction_deltas[neighbor_cell]
                            if (dx, dy) == n_dir:
                                can_connect = True
                                reason = "Turn"
                        elif cell in ['<', '>'] and neighbor_cell in ['^', 'v']:
                            n_dir = direction_deltas[neighbor_cell]
                            if (dx, dy) == n_dir:
                                can_connect = True
                                reason = "Turn"

                    # D. Intersecciones
                    if neighbor_cell in ['S', 'D']:
                        can_connect = True
                        reason = "ToIntersection"
                        
                    if cell in ['S', 'D']:
                        if neighbor_cell in direction_deltas:
                            n_dir = direction_deltas[neighbor_cell]
                            if (dx, dy) == n_dir:
                                can_connect = True
                                reason = "FromIntersection"
                        elif neighbor_cell in ['S', 'D']:
                            can_connect = True
                            reason = "IntersectionLink"
                    
                    # 2. APLICAR RESTRICCIÓN DE AUTOPISTA
                    # Bloquear giros ilegales desde highways
                    if is_highway and reason == "Turn":
                        can_connect = False

                    if can_connect:
                        self.G.add_edge((x, y), (nx_x, nx_y))
    
    def spawn_car(self, start_pos=None, destination=None):
        """Genera un nuevo coche en la simulación."""
        if start_pos is None:
            start_pos = self.get_random_spawn_point()
        
        # Seleccionar destino no ocupado CON DISTANCIA MÍNIMA
        if destination is None:
            available_destinations = [d for d in self.destinations if d not in self.occupied_destinations]
            if not available_destinations:
                return None
            
            # Intentar encontrar un destino con distancia mínima de 10 celdas
            max_attempts = 20
            for _ in range(max_attempts):
                candidate = random.choice(available_destinations)
                
                # Calcular distancia Manhattan considerando toroide
                dx = abs(candidate[0] - start_pos[0])
                dy = abs(candidate[1] - start_pos[1])
                dx = min(dx, self.grid.width - dx)
                dy = min(dy, self.grid.height - dy)
                manhattan_dist = dx + dy
                
                if manhattan_dist >= 10:
                    # Verificar si existe ruta en el grafo
                    if nx.has_path(self.G, start_pos, candidate):
                        destination = candidate
                        break
            else:
                # Si falla el intento de distancia, buscar cualquiera válido
                random.shuffle(available_destinations)
                for d in available_destinations:
                    if nx.has_path(self.G, start_pos, d):
                        destination = d
                        break
        
        if destination is None:
            return None # No se encontró destino válido
        
        # Marcar destino como ocupado
        self.occupied_destinations.add(destination)
        
        car = Car(self.next_id(), self, destination)
        self.grid.place_agent(car, start_pos)
        self.schedule.add(car)
        return car
    
    def get_random_spawn_point(self):
        """Obtiene un punto de spawn aleatorio en las calles."""
        valid_positions = []
        for row in range(len(city_map)):
            for col in range(len(city_map[row])):
                cell = city_map[row][col]
                if cell in ['v', '^', '>', '<']:
                    x = col
                    y = 23 - row
                    valid_positions.append((x, y))
        
        return random.choice(valid_positions) if valid_positions else (1, 1)
    
    def step(self):
        """Ejecuta un paso de la simulación."""
        self.schedule.step()
        
        # Dinámica de Población: Mantener ~13 coches
        car_count = len([a for a in self.schedule.agents if isinstance(a, Car)])
        
        if car_count < 13:
            self.spawn_timer += 1
            if self.spawn_timer >= 2: # Intentar cada 2 ticks
                self.spawn_timer = 0
                self.spawn_car()
        
    def serialize_grid(self):
        """Serializa el grid para Unity con información detallada."""
        data = []
        for cell_content, (x, y) in self.grid.coord_iter():
            for agent in cell_content:
                agent_data = {
                    "id": agent.unique_id,
                    "x": x,
                    "y": y,
                    "agent_type": type(agent).__name__,
                    "state": None,
                    "direction": None
                }
                
                # Agregar información específica por tipo
                if isinstance(agent, TrafficLight):
                    agent_data["state"] = agent.state
                    agent_data["direction"] = agent.direction
                elif isinstance(agent, Car):
                    agent_data["state"] = "Moving"
                
                data.append(agent_data)
        
        return data
