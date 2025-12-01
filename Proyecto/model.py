"""
MODEL.PY - Refactorización Completa
===================================
Fixes implementados:
- BUG D: Grafo mejorado con pesos correctos (Recto=1, Giro=2, LaneChange=10, Parking=100)
- BUG D: Spawn mejorado usando get_random_spawn_point()
- Validación de conectividad de destinos
"""

from mesa import Model, Agent
from mesa.space import MultiGrid
from mesa.time import RandomActivation
import networkx as nx
import random

# Mapa de la ciudad (24x24 - No toroidal)
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

from agents import Car, TrafficLight, Obstacle, Destination, ChaoticCar, PoliceCar


class CityModel(Model):
    """Modelo de ciudad con tráfico urbano multiagente."""

    def __init__(self, width=24, height=24, num_cars=10, parking_time=3, num_police=2, num_chaotic=2):
        super().__init__()
        self.width = width
        self.height = height
        self.num_cars = num_cars
        self.num_police = num_police
        self.num_chaotic = num_chaotic
        self.parking_time = parking_time
        self.spawn_timer = 0

        # Scheduler y Grid
        self.schedule = RandomActivation(self)
        self.grid = MultiGrid(width, height, torus=False)
        
        # Grafo de navegación (dirigido, ponderado)
        self.G = nx.DiGraph()
        self.destinations = []

        # 1. Crear mapa con agentes
        self.setup_map()

        # 2. Crear grafo de navegación
        self.setup_graph()

        # 3. Spawnear agentes iniciales (Policía → Caótico → Normal)
        for _ in range(self.num_police):
            self.spawn_car(agent_type=PoliceCar)

        for _ in range(self.num_chaotic):
            self.spawn_car(agent_type=ChaoticCar)

        for _ in range(self.num_cars):
            self.spawn_car(agent_type=Car)

        self.running = True  # Required for Mesa visualization

    def setup_map(self):
        """Lee city_map y coloca agentes en la grilla."""
        
        for row in range(len(city_map)):
            for col in range(len(city_map[row])):
                cell = city_map[row][col]

                # Conversión: (col, 23-row) para invertir eje Y
                x = col
                y = 23 - row

                if cell == '#':
                    # Obstáculo
                    obstacle = Obstacle(self.next_id(), self)
                    self.grid.place_agent(obstacle, (x, y))
                    self.schedule.add(obstacle)

                elif cell == 'S':
                    # Semáforo con sincronización por vecindad
                    direction = None
                    state = None
                    timer_value = 10

                    # 1. Chequeo de sincronización: ¿Hay semáforo a la IZQUIERDA?
                    if col > 0 and city_map[row][col - 1] == 'S':
                        left_x = col - 1
                        left_y = 23 - row
                        left_agents = self.grid.get_cell_list_contents([(left_x, left_y)])
                        
                        for agent in left_agents:
                            if isinstance(agent, TrafficLight):
                                # Copiar atributos del semáforo vecino
                                direction = agent.direction
                                state = agent.state
                                timer_value = agent.timer
                                break

                    # 2. Si es un líder (no hay vecino izquierda), determinar dirección
                    if direction is None:
                        is_vertical = False
                        is_horizontal = False

                        # Chequear flujo vertical
                        if row > 0 and city_map[row - 1][col] == 'v':
                            is_vertical = True
                        if row < len(city_map) - 1 and city_map[row + 1][col] == '^':
                            is_vertical = True

                        # Chequear flujo horizontal
                        if col > 0 and city_map[row][col - 1] == '>':
                            is_horizontal = True
                        if col < len(city_map[row]) - 1 and city_map[row][col + 1] == '<':
                            is_horizontal = True

                        # Determinar por flujo detectado
                        if is_vertical:
                            direction = "NS"
                        elif is_horizontal:
                            direction = "EW"
                        else:
                            # Fallback: heurística de vecindad
                            has_vertical = False
                            has_horizontal = False

                            if row > 0 and city_map[row - 1][col] in ['v', '^', 'S']:
                                has_vertical = True
                            if row < len(city_map) - 1 and city_map[row + 1][col] in ['v', '^', 'S']:
                                has_vertical = True
                            if col > 0 and city_map[row][col - 1] in ['<', '>', 'S']:
                                has_horizontal = True
                            if col < len(city_map[row]) - 1 and city_map[row][col + 1] in ['<', '>', 'S']:
                                has_horizontal = True

                            if has_vertical and not has_horizontal:
                                direction = "NS"
                            elif has_horizontal and not has_vertical:
                                direction = "EW"
                            else:
                                # Intersección compleja: alternar
                                direction = "NS" if (row + col) % 2 == 0 else "EW"

                        # Establecer estado inicial (Exclusión Mutua)
                        if direction == "NS":
                            state = "Green"
                            timer_value = 10
                        else:  # "EW"
                            state = "Red"
                            timer_value = 10

                    # Crear semáforo
                    traffic_light = TrafficLight(self.next_id(), self, direction, state, 0)
                    traffic_light.timer = timer_value
                    self.grid.place_agent(traffic_light, (x, y))
                    self.schedule.add(traffic_light)

                elif cell == 'D':
                    # Destino/Parking
                    destination = Destination(self.next_id(), self)
                    self.grid.place_agent(destination, (x, y))
                    self.schedule.add(destination)
                    self.destinations.append(destination)

    def setup_graph(self):
        """
        Crea grafo dirigido estricto basado en flechas del mapa.
        
        PESOS:
        - Movimiento Frontal (Forward): 1
        - Giro en Intersección: 2
        - Cambio de Carril (LaneChange): 10 (costo alto, desalentado)
        - Entrada a Parking: 100 (costo muy alto, solo si desesperado)
        """
        
        self.G.clear()
        w = self.grid.width
        h = self.grid.height

        # Mapeo de dirección a delta (dx, dy)
        direction_deltas = {
            '^': (0, 1),   # Norte
            'v': (0, -1),  # Sur
            '>': (1, 0),   # Este
            '<': (-1, 0)   # Oeste
        }

        # Von Neumann (4-vecinos): solo ortogonal
        neighbor_offsets = [(0, 1), (0, -1), (1, 0), (-1, 0)]

        # Añadir nodos y aristas
        for row in range(len(city_map)):
            for col in range(len(city_map[row])):
                cell = city_map[row][col]

                x = col
                y = 23 - row

                if cell == '#':
                    continue

                # Añadir nodo
                self.G.add_node((x, y))

                # Procesar vecinos
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
                    weight = 1

                    # ========== CASO 1: ESTOY EN CALLE (^, v, <, >) ==========
                    if cell in direction_deltas:
                        my_dir = direction_deltas[cell]

                        # A. Movimiento Frontal (Forward)
                        if (dx, dy) == my_dir:
                            can_connect = True
                            weight = 1  # Recto

                        # B. Cambio de Carril (LaneChange) - ALTO COSTO
                        elif neighbor_cell in direction_deltas:
                            n_dir = direction_deltas[neighbor_cell]
                            
                            if n_dir == my_dir:  # Misma dirección
                                # Verificar ortogonalidad (producto punto = 0)
                                dot_prod = my_dir[0] * dx + my_dir[1] * dy
                                
                                if dot_prod == 0:  # Movimiento perpendicular
                                    can_connect = True
                                    weight = 10  # *** PENALIZACIÓN ALTA ***

                        # C. Entrada a Intersección (S, D)
                        elif neighbor_cell in ['S', 'D']:
                            # Verificar que no sea contraflujo
                            dot_prod = my_dir[0] * dx + my_dir[1] * dy
                            
                            if dot_prod >= 0:  # Ángulo <= 90 grados
                                can_connect = True
                                weight = 1  # Normal
                                
                                if neighbor_cell == 'D':
                                    weight = 100  # *** COSTO MUY ALTO PARA PARKING ***

                    # ========== CASO 2: ESTOY EN INTERSECCIÓN (S, D) ==========
                    elif cell in ['S', 'D']:
                        # A. Salida a Calle (no contraflujo)
                        if neighbor_cell in direction_deltas:
                            n_dir = direction_deltas[neighbor_cell]
                            
                            # Contraflujo: NO entrar si (dx,dy) == -n_dir
                            if (dx, dy) != (-n_dir[0], -n_dir[1]):
                                can_connect = True
                                weight = 1  # Recto al salir

                        # B. Conexión Interna S-S, S-D, D-S
                        elif neighbor_cell in ['S', 'D']:
                            can_connect = True
                            weight = 1

                    if can_connect:
                        self.G.add_edge((x, y), (nx_x, nx_y), weight=weight)

        # ========== VALIDACIÓN DE CONECTIVIDAD ==========
        print(f"\n{'='*50}")
        print(f"📊 REPORTE DE GRAFO")
        print(f"{'='*50}")
        print(f"✓ Nodos: {self.G.number_of_nodes()}")
        print(f"✓ Aristas: {self.G.number_of_edges()}")

        # Verificar que todos los destinos sean alcanzables
        unreachable = []
        
        for dest in self.destinations:
            if dest.pos not in self.G:
                unreachable.append(f"{dest.unique_id} (NO en Grafo)")
            else:
                in_degree = self.G.in_degree(dest.pos)
                if in_degree == 0:
                    unreachable.append(f"{dest.unique_id} at {dest.pos} (Grado Entrada=0)")

        if unreachable:
            print(f"\n⚠️  DESTINOS INALCANZABLES:")
            for dest_id in unreachable:
                print(f"   - {dest_id}")
        else:
            print(f"\n✅ TODOS los destinos son alcanzables")

        print(f"{'='*50}\n")

    def spawn_car(self, start_pos=None, agent_type=Car):
        """
        Genera un nuevo coche en la simulación.
        
        FIX BUG D: Usa get_random_spawn_point() para spawn en calles válidas.
        """
        
        if start_pos is None:
            start_pos = self.get_random_spawn_point()

        # Crear coche sin destino inicial (lo buscará en su broadcast_request)
        car = agent_type(
            self.next_id(),
            self,
            destination=None,
            parking_limit=self.parking_time
        )

        self.grid.place_agent(car, start_pos)
        self.schedule.add(car)

        return car

    def get_random_spawn_point(self):
        """
        Obtiene un punto de spawn aleatorio en cualquier calle válida.
        
        FIX BUG D: Asegurar que los coches spawneen distribuidos,
        no solo cerca de destinos.
        """
        
        valid_positions = []

        for row in range(len(city_map)):
            for col in range(len(city_map[row])):
                cell = city_map[row][col]

                # Solo en calles (no en semáforos, parking, obstáculos)
                if cell in ['v', '^', '>', '<']:
                    x = col
                    y = 23 - row
                    valid_positions.append((x, y))

        if valid_positions:
            return random.choice(valid_positions)
        else:
            # Fallback (nunca debería ocurrir con mapa correcto)
            return (1, 1)

    def step(self):
        """Ejecuta un paso de la simulación."""
        
        self.schedule.step()

        # ========== DINÁMICA DE POBLACIÓN ==========
        # Mantener counts de cada tipo de agente
        current_cars = 0
        current_police = 0
        current_chaotic = 0

        for agent in self.schedule.agents:
            if isinstance(agent, PoliceCar):
                current_police += 1
            elif isinstance(agent, ChaoticCar):
                current_chaotic += 1
            elif type(agent) == Car:  # Tipo exacto (no subclases)
                current_cars += 1

        # Spawn respawn: Intentar cada 2 ticks con prioridad
        self.spawn_timer += 1

        if self.spawn_timer >= 2:
            self.spawn_timer = 0

            if current_police < self.num_police:
                self.spawn_car(agent_type=PoliceCar)
            elif current_chaotic < self.num_chaotic:
                self.spawn_car(agent_type=ChaoticCar)
            elif current_cars < self.num_cars:
                self.spawn_car(agent_type=Car)

    def serialize_grid(self):
        """Serializa grid para visualización (Unity/WebSocket)."""
        
        data = []

        for cell_content, (x, y) in self.grid.coord_iter():
            for agent in cell_content:
                agent_data = {
                    "id": agent.unique_id,
                    "x": x,
                    "y": y,
                    "agent_type": type(agent).__name__,
                    "state": None,
                    "direction": None,
                    "state_code": 0
                }

                # Información específica por tipo
                if isinstance(agent, TrafficLight):
                    agent_data["state"] = agent.state
                    agent_data["direction"] = agent.direction

                elif isinstance(agent, Car):
                    agent_data["state"] = agent.state

                    # Códigos de estado para visualización
                    if isinstance(agent, ChaoticCar):
                        agent_data["state_code"] = 2 if agent.state == "CRASHED" else 0

                    elif isinstance(agent, PoliceCar):
                        if agent.state == "PATROL":
                            agent_data["state_code"] = 3
                        elif agent.state == "CHASE":
                            agent_data["state_code"] = 4

                    else:  # Car normal
                        if agent.state == "DRIVING":
                            agent_data["state_code"] = 0
                        elif agent.state == "WANDERING":
                            agent_data["state_code"] = 1
                        elif agent.state == "CRASHED":
                            agent_data["state_code"] = 2

                elif isinstance(agent, Destination):
                    if agent.occupant is not None:
                        agent_data["state"] = "Occupied"  # Rojo
                    elif agent.reserved_by is not None:
                        agent_data["state"] = "Reserved"  # Amarillo
                    else:
                        agent_data["state"] = "Free"  # Verde

                data.append(agent_data)

        return data