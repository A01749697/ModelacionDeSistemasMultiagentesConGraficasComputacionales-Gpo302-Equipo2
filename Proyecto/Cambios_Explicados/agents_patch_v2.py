"""
AGENTS.PY - PATCH 2: COMPORTAMIENTO REFINADO
=============================================

Correcciones Implementadas:
- PROBLEMA 1: Indecisión en Intersecciones → Agregar INERCIA a get_wandering_move()
- PROBLEMA 2: ChaoticCar Zig-Zag → Nuevo método get_chaotic_move() con INERCIA + bloqueo Destination

Cambios Clave:
1. Car.__init__() → Agregar self.last_move (vector direccional)
2. Car.get_wandering_move() → REFACTORIZADO con inercia
3. ChaoticCar.step() → COMPLETAMENTE REESCRITO con get_chaotic_move()
4. ChaoticCar.can_move_to() → Agregar protección contra Destination
"""

from mesa import Agent
import networkx as nx
import random


class Car(Agent):
    """Agente que representa un vehículo en la simulación."""

    def __init__(self, unique_id, model, destination=None, parking_limit=3):
        super().__init__(unique_id, model)
        self.destination = destination
        self.state = "WANDERING" if destination is None else "DRIVING"
        self.parking_timer = 0
        self.parking_limit = parking_limit
        self.path = []
        self.patience = 3
        self.do_not_park_here = None
        
        # *** NUEVO: INERCIA DIRECCIONAL para evitar zig-zag ***
        self.last_move = None  # Tupla (dx, dy) o None
        
        self.debug = (unique_id == 0)

    def step(self):
        """Avanza un paso en la simulación con máquina de estados clara."""
        
        if self.debug:
            print(f"🚗 CAR {self.unique_id} | pos={self.pos}, dest={self.destination}, state={self.state}")

        # 1. ESTADO CRASHED
        if self.state == "CRASHED":
            return

        # 2. ESTADO PARKED
        if self.state == "PARKED":
            self.parking_timer -= 1
            
            if self.parking_timer <= 0:
                if self.destination:
                    self.do_not_park_here = self.destination
                    self.destination.release()
                    self.destination = None
                
                self.state = "WANDERING"
                self.path = []
                self.last_move = None  # Reset inercia al salir de parking
                
                if self.debug:
                    print(f"🚗 CAR {self.unique_id} EXITING PARKING → WANDERING")
            
            return

        # 3. ESTADO DRIVING
        if self.destination:
            # 3.A. Llegada al destino
            if self.pos == self.destination.pos:
                self.state = "PARKED"
                self.parking_timer = self.parking_limit
                self.destination.occupant = self
                self.last_move = None  # Reset inercia
                
                if self.debug:
                    print(f"🚗 CAR {self.unique_id} ARRIVED at {self.destination.pos} → PARKED")
                
                return

            # 3.B. Calcular ruta si no existe
            if not self.path:
                self.calculate_path()

            # 3.C. Seguir ruta
            if self.path:
                next_pos = self.path[0]
                
                if self.can_move_to(next_pos):
                    # Guardar movimiento para inercia
                    dx = next_pos[0] - self.pos[0]
                    dy = next_pos[1] - self.pos[1]
                    self.last_move = (dx, dy)
                    
                    self.model.grid.move_agent(self, next_pos)
                    self.path.pop(0)
                    self.patience = 3
                else:
                    self.patience -= 1
                    if self.patience <= 0:
                        self.calculate_path()
                        self.patience = 3

        # 4. ESTADO WANDERING
        else:
            # 4.A. Intentar negociar destino
            if self.debug:
                print(f"🔍 CAR {self.unique_id} WANDERING, broadcasting request...")
            
            self.broadcast_request()

            # 4.B. Si encontró destino, cambiar a DRIVING
            if self.destination:
                self.do_not_park_here = None
                self.state = "DRIVING"
                self.calculate_path()
                return

            # 4.C. Si no encontró, vagar aleatoriamente CON INERCIA
            self.state = "WANDERING"
            next_pos = self.get_wandering_move()
            
            if next_pos:
                # Guardar movimiento para inercia
                dx = next_pos[0] - self.pos[0]
                dy = next_pos[1] - self.pos[1]
                self.last_move = (dx, dy)
                
                self.model.grid.move_agent(self, next_pos)

    def get_wandering_move(self):
        """
        *** REFACTORIZADO CON INERCIA PROBLEMA 1 ***
        
        Decide movimiento WANDERING evitando "baile" en semáforos.
        NUEVA ESTRATEGIA:
        1. Obtener vecinos y calcular pesos
        2. REFORZAR último movimiento (weight *= 0.5 si es continuación)
        3. Ordenar por peso ajustado
        4. Si mejor opción tiene semáforo rojo → ESPERAR (return None)
        5. Si mejor opción está libre → TOMAR
        6. Si mejor está ocupada → intentar alternativas
        7. Si todo está bloqueado → ESPERAR
        """
        
        neighbors = self.model.grid.get_neighborhood(
            self.pos, moore=False, include_center=False
        )
        valid_options = []

        # Obtener vecinos conectados en el grafo
        for n in neighbors:
            if self.model.G.has_edge(self.pos, n):
                weight = self.model.G.edges[self.pos, n]['weight']
                dx = n[0] - self.pos[0]
                dy = n[1] - self.pos[1]
                direction = (dx, dy)
                valid_options.append((n, weight, direction))

        # *** INERCIA: Reforzar si es continuación del movimiento anterior ***
        if self.last_move:
            adjusted_options = []
            for pos, weight, direction in valid_options:
                # Si es continuación (mismo vector), reducir peso en 50%
                if direction == self.last_move:
                    adjusted_weight = weight * 0.5  # PREFERENCIA de inercia
                else:
                    adjusted_weight = weight
                adjusted_options.append((pos, adjusted_weight, direction))
            valid_options = adjusted_options

        # Ordenar por peso ajustado
        valid_options.sort(key=lambda x: x[1])

        if not valid_options:
            self.last_move = None
            return None

        # Evaluar primera opción (mejor según peso)
        best_pos, best_weight, best_direction = valid_options[0]

        # *** CLAVE: Si semáforo ROJO/AMARILLO bloquea la mejor opción, ESPERAR ***
        if not self.can_pass_traffic_light(best_pos):
            if self.debug:
                print(f"🛑 CAR {self.unique_id} WAITING at red light (inercia={self.last_move})")
            return None  # NO BAILAR - solo esperar

        # Si recto está disponible (semáforo verde y sin coches), tomar
        if self.can_move_to(best_pos):
            return best_pos

        # Si mejor está ocupada por coche, intentar alternativas
        for next_pos, next_weight, next_direction in valid_options[1:]:
            if not self.can_pass_traffic_light(next_pos):
                continue  # Semáforo rojo, saltar
            
            if self.can_move_to(next_pos):
                return next_pos

        # Completamente bloqueado
        return None

    def can_pass_traffic_light(self, pos):
        """
        Verifica si el semáforo permite el paso hacia 'pos'.
        Regla de Oro: Si ya estoy DENTRO de una intersección, permitir avance.
        """
        
        # 1. ¿Estoy ya dentro de una intersección?
        my_cell_contents = self.model.grid.get_cell_list_contents([self.pos])
        am_in_intersection = any(
            isinstance(a, TrafficLight) for a in my_cell_contents
        )
        
        if am_in_intersection:
            return True  # Despejar intersección

        # 2. ¿Hay semáforo en la celda destino?
        cell_contents = self.model.grid.get_cell_list_contents([pos])
        
        for agent in cell_contents:
            if isinstance(agent, TrafficLight):
                if agent.state == "Green":
                    return True
                elif agent.state in ["Red", "Yellow"]:
                    dx = pos[0] - self.pos[0]
                    dy = pos[1] - self.pos[1]

                    if agent.direction == "NS":
                        if dy != 0:
                            return False
                    elif agent.direction == "EW":
                        if dx != 0:
                            return False

                return True

        return True

    def can_move_to(self, pos):
        """
        Verifica si el coche puede moverse a la posición.
        """
        
        if pos not in self.model.G:
            return False
        
        if not self.model.G.has_edge(self.pos, pos):
            return False

        if not self.can_pass_traffic_light(pos):
            return False

        cell_contents = self.model.grid.get_cell_list_contents([pos])

        # PROTECCIÓN: No entrar a Destination ajeno
        for agent in cell_contents:
            if isinstance(agent, Destination):
                if agent != self.destination:
                    return False

        # No puede moverse si hay otro coche u obstáculo
        for agent in cell_contents:
            if isinstance(agent, Car):
                return False
            
            if isinstance(agent, Obstacle):
                return False

        return True

    def broadcast_request(self):
        """Contract Net Protocol: Solicita ofertas de todos los destinos."""
        
        best_bid = float('inf')
        best_dest = None

        for dest in self.model.destinations:
            if dest == self.do_not_park_here:
                continue

            bid = dest.calculate_bid(self.pos)
            
            if bid < best_bid:
                best_bid = bid
                best_dest = dest

        if best_dest:
            best_dest.book(self)
            self.destination = best_dest
            self.state = "DRIVING"
            self.calculate_path()

    def calculate_path(self):
        """Calcula ruta usando Dijkstra ponderado."""
        
        if (
            not self.destination
            or self.pos not in self.model.G
            or self.destination.pos not in self.model.G
        ):
            return

        try:
            self.path = nx.shortest_path(
                self.model.G, self.pos, self.destination.pos, weight='weight'
            )
            
            if len(self.path) > 0:
                self.path.pop(0)
        
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            self.destination.release()
            self.destination = None
            self.state = "WANDERING"
            self.path = []
            self.last_move = None


class TrafficLight(Agent):
    """Semáforo con ciclo Green → Yellow → Red → Green."""

    def __init__(self, unique_id, model, direction="NS", state="Green", time_offset=0):
        super().__init__(unique_id, model)
        self.direction = direction
        self.state = state
        self.timer = 10 - time_offset if state == "Green" else 10
        self.green_time = 10
        self.yellow_time = 3
        self.red_time = 10

    def step(self):
        """Decrementa timer y cambia estado cíclicamente."""
        
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
    """Edificio u obstáculo estático."""

    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)

    def step(self):
        pass


class Destination(Agent):
    """
    Destino/Parking: Agente pasivo con 3 estados visuales.
    - Libre (Verde): occupant=None, reserved_by=None
    - Reservado (Amarillo): reserved_by=Car
    - Ocupado (Rojo): occupant=Car
    """

    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.occupant = None
        self.reserved_by = None

    def step(self):
        pass

    def calculate_bid(self, car_pos):
        """Calcula oferta de distancia si está disponible."""
        
        if self.occupant is not None or self.reserved_by is not None:
            return float('inf')

        dx = abs(self.pos[0] - car_pos[0])
        dy = abs(self.pos[1] - car_pos[1])
        return dx + dy

    def book(self, car_agent):
        """Reserva destino para un coche."""
        self.reserved_by = car_agent
        return True

    def release(self):
        """Libera destino completamente."""
        self.occupant = None
        self.reserved_by = None


class ChaoticCar(Car):
    """
    *** REFACTORIZADO COMPLETAMENTE PARA PROBLEMA 2 ***
    
    Vehículo caótico que ignora semáforos y causa choques.
    NUEVA ESTRATEGIA:
    - Movimiento direccional con inercia (no random.choice)
    - Ignorar semáforos
    - NUNCA buscar Destination
    - NUNCA entrar a celdas de Destination
    - Velocidad consistente (ir recto siempre si es posible)
    """

    def __init__(self, unique_id, model, destination=None, parking_limit=3):
        super().__init__(unique_id, model, destination, parking_limit)
        self.state = "CHAOS"
        # *** INERCIA FUERTE para ChaoticCar ***
        self.last_move = None  # Vector direccional persistente

    def can_pass_traffic_light(self, pos):
        """Ignora todos los semáforos - ¡soy caótico!"""
        return True

    def can_move_to(self, pos):
        """
        *** PROTECCIÓN MEJORADA PARA CHAOTICCAR ***
        
        Ignora semáforos, pero:
        1. Verifica límites de grafo
        2. Verifica obstáculos estáticos
        3. NUNCA entra a celdas de Destination (NUEVA RESTRICCIÓN)
        4. NUNCA considera coches como bloqueantes (zig-zag a través)
        """
        
        if pos not in self.model.G:
            return False

        if not self.model.G.has_edge(self.pos, pos):
            return False

        cell_contents = self.model.grid.get_cell_list_contents([pos])

        # *** NUEVA: Bloquear Destination completamente ***
        for agent in cell_contents:
            if isinstance(agent, Destination):
                return False  # NUNCA entrar a parking
            
            if isinstance(agent, Obstacle):
                return False  # Bloquear obstáculos

        # Nota: Ignora Car y TrafficLight (se puede colisionar)
        return True

    def get_chaotic_move(self):
        """
        *** NUEVO MÉTODO: Movimiento caótico pero DIRECCIONAL ***
        
        Estrategia:
        1. Obtener vecinos válidos
        2. SI hay last_move → PREFERIR continuación (inercia fuerte)
        3. SI está bloqueado → GIRAR a random
        4. Ignorar semáforos (can_pass_traffic_light siempre True)
        
        RESULTADO: Movimiento rápido y direccional, no zig-zag
        """
        
        neighbors = self.model.grid.get_neighborhood(
            self.pos, moore=False, include_center=False
        )
        valid_moves = []

        # Obtener movimientos válidos con pesos
        for n in neighbors:
            if self.can_move_to(n):
                weight = self.model.G.edges[self.pos, n]['weight'] if self.model.G.has_edge(self.pos, n) else 100
                dx = n[0] - self.pos[0]
                dy = n[1] - self.pos[1]
                direction = (dx, dy)
                valid_moves.append((n, weight, direction))

        if not valid_moves:
            return None

        # *** INERCIA FUERTE: Si hay last_move, preferir continuación ***
        if self.last_move:
            # Buscar continuación
            for n, weight, direction in valid_moves:
                if direction == self.last_move:
                    # Continuar en dirección actual (ignorar peso)
                    return n
        
        # Si no hay continuación o último paso es None, elegir mejor peso disponible
        valid_moves.sort(key=lambda x: x[1])
        best_pos = valid_moves[0][0]
        
        return best_pos

    def step(self):
        """
        *** MOVIMIENTO CAÓTICO SIMPLIFICADO ***
        
        ChaoticCar no busca parking, solo va rápido en línea recta.
        Si choca con coche normal → crash.
        Si está bloqueado → gira.
        """
        
        # NUNCA buscar destino (override totalmente)
        self.destination = None
        self.path = []
        self.state = "CHAOS"

        # Obtener movimiento (con inercia)
        next_pos = self.get_chaotic_move()

        if not next_pos:
            # Completamente bloqueado → esperar o girar random
            neighbors = self.model.grid.get_neighborhood(
                self.pos, moore=False, include_center=False
            )
            valid = [n for n in neighbors if self.can_move_to(n)]
            if valid:
                next_pos = random.choice(valid)
            else:
                # Pared total, no moverse
                self.last_move = None
                return

        # Detectar colisión con coche normal
        cell_contents = self.model.grid.get_cell_list_contents([next_pos])
        victim = None
        
        for agent in cell_contents:
            if isinstance(agent, Car) and not isinstance(agent, ChaoticCar):
                victim = agent
                break

        if victim:
            # CRASH: Marcar víctima como CRASHED
            victim.state = "CRASHED"

            # ChaoticCar huye (elegir dirección ortogonal)
            neighbors = self.model.grid.get_neighborhood(
                self.pos, moore=False, include_center=False
            )
            valid = [n for n in neighbors if self.can_move_to(n)]
            
            if valid:
                # Huir a dirección aleatoria (romper inercia por caos)
                escape_pos = random.choice(valid)
                dx = escape_pos[0] - self.pos[0]
                dy = escape_pos[1] - self.pos[1]
                self.last_move = (dx, dy)
                self.model.grid.move_agent(self, escape_pos)
                self.destination = None
                self.path = []
            
            self.last_move = None  # Reset después de crash
        else:
            # Sin colisión, avanzar normalmente
            dx = next_pos[0] - self.pos[0]
            dy = next_pos[1] - self.pos[1]
            self.last_move = (dx, dy)
            
            self.model.grid.move_agent(self, next_pos)


class PoliceCar(Car):
    """Patrulla que persigue ChaoticCars."""

    def __init__(self, unique_id, model, destination=None, parking_limit=3, checkpoints=None):
        super().__init__(unique_id, model, destination, parking_limit)
        self.checkpoints = checkpoints if checkpoints else []
        self.current_checkpoint_index = 0
        self.state = "PATROL"

    def step(self):
        """PATROL → detect ChaoticCar → CHASE → pursue → return PATROL."""
        
        # Detectar ChaoticCar en radio
        neighbors = self.model.grid.get_neighbors(
            self.pos, moore=True, radius=5, include_center=False
        )
        
        target = None
        for n in neighbors:
            if isinstance(n, ChaoticCar):
                target = n
                break

        if target:
            # CHASE MODE
            self.state = "CHASE"
            
            try:
                path = nx.shortest_path(self.model.G, self.pos, target.pos)
                
                if len(path) > 1:
                    next_pos = path[1]
                    if self.can_move_to(next_pos):
                        # Guardar movimiento para inercia
                        dx = next_pos[0] - self.pos[0]
                        dy = next_pos[1] - self.pos[1]
                        self.last_move = (dx, dy)
                        
                        self.model.grid.move_agent(self, next_pos)
            
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                pass

        else:
            # PATROL MODE
            self.state = "PATROL"

            if not self.checkpoints:
                # Sin checkpoints: vagar
                next_pos = self.get_wandering_move()
                if next_pos:
                    dx = next_pos[0] - self.pos[0]
                    dy = next_pos[1] - self.pos[1]
                    self.last_move = (dx, dy)
                    
                    self.model.grid.move_agent(self, next_pos)
                return

            # Con checkpoints: patrullar
            target_pos = self.checkpoints[self.current_checkpoint_index]

            if self.pos == target_pos:
                self.current_checkpoint_index = (
                    self.current_checkpoint_index + 1
                ) % len(self.checkpoints)
                target_pos = self.checkpoints[self.current_checkpoint_index]

            try:
                path = nx.shortest_path(self.model.G, self.pos, target_pos)
                
                if len(path) > 1:
                    next_pos = path[1]
                    if self.can_move_to(next_pos):
                        dx = next_pos[0] - self.pos[0]
                        dy = next_pos[1] - self.pos[1]
                        self.last_move = (dx, dy)
                        
                        self.model.grid.move_agent(self, next_pos)
            
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                self.current_checkpoint_index = (
                    self.current_checkpoint_index + 1
                ) % len(self.checkpoints)
