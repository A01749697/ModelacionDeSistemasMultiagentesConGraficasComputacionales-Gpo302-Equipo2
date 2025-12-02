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
from collections import deque


def detect_stuck_pattern(car):
    """Detecta si coche está atorado basado en historial."""
    if len(car.position_history) < 3:
        return False, "InsufficientData"
    
    recent_pos = list(car.position_history)[-3:]
    
    # Patrón 1: Mismo lugar 3 steps consecutivos
    if recent_pos[0] == recent_pos[1] == recent_pos[2]:
        return True, "STATIC_BLOCK"
    
    # Patrón 2: Ping-Pong (A → B → A)
    if recent_pos[0] == recent_pos[2] and recent_pos[0] != recent_pos[1]:
        return True, "PING_PONG"
    
    # Patrón 3: Stuck_counter alto
    if car.stuck_counter > 5:
        return True, "HIGH_STUCK_COUNTER"
    
    return False, "OK"


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
        
        # TRACKING PARA DEBUGGING
        self.position_history = deque(maxlen=10)  # Últimas 10 posiciones
        self.stuck_counter = 0  # Contador de steps sin movimiento
        self.decision_history = deque(maxlen=5)  # Últimas 5 decisiones
        self.is_under_observation = False  # Flag para logging intensivo
        
        self.debug = (unique_id == 0)

    def step(self):
        """Avanza un paso en la simulación con máquina de estados clara."""
        
        # [TRACK HISTORIAL DE POSICIONES]
        self.position_history.append(self.pos)
        
        # Incrementar stuck_counter si no nos movemos
        if len(self.position_history) >= 2:
            prev_pos = list(self.position_history)[-2]
            if self.pos == prev_pos:
                self.stuck_counter += 1
            else:
                self.stuck_counter = 0  # Reset al moverse
        
        # CRITICAL FIX: Mantener last_move aunque no se mueva
        # Esto es crucial para inercia cuando el coche está bloqueado
        if self.last_move is None and len(self.position_history) >= 2:
            prev_pos = list(self.position_history)[-2]
            curr_pos = self.pos
            recovered_move = (curr_pos[0] - prev_pos[0], curr_pos[1] - prev_pos[1])
            if recovered_move != (0, 0):  # Solo si realmente se movió
                self.last_move = recovered_move
        
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
                self.stuck_counter = 0  # [RESET COUNTER]
            else:
                # No se movió
                self.stuck_counter += 1
                if self.is_under_observation:
                    print(f"   ⏸️  CAR {self.unique_id} didn't move. StuckCounter={self.stuck_counter}")

    def get_wandering_move(self):
        """
        Decide el movimiento WANDERING con lógica estricta Anti-Reversa.
        
        NUEVA ESTRATEGIA (Anti-Ping-Pong):
        1. Separar opciones en "adelante/lateral" vs "atrás" (U-turn)
        2. Priorizar FUERTEMENTE continuar recto (weight * 0.1)
        3. Solo permitir U-turn si es la única opción (callejón sin salida)
        4. Si mejor opción tiene luz roja → ESPERAR (no dar vuelta en U)
        """
        
        # FIX CRÍTICO: Recuperar last_move del historial si es None
        if self.last_move is None and len(self.position_history) >= 2:
            # Calcular movimiento desde posición anterior
            prev_pos = list(self.position_history)[-2]
            curr_pos = self.pos
            self.last_move = (curr_pos[0] - prev_pos[0], curr_pos[1] - prev_pos[1])
            
            # Solo mantener si es movimiento válido (no (0,0))
            if self.last_move == (0, 0):
                self.last_move = None
            elif self.is_under_observation:
                print(f"   🔧 RECOVERED last_move from history: {self.last_move}")
        
        # [LOGGING ENTRADA]
        step_num = self.model.schedule.steps
        is_stuck, stuck_reason = detect_stuck_pattern(self)
        
        if is_stuck:
            self.is_under_observation = True
            print(f"\n🚨 STUCK DETECTION: Car {self.unique_id}")
            print(f"   Step: {step_num}, Pos: {self.pos}")
            print(f"   Reason: {stuck_reason}")
            print(f"   LastMove: {self.last_move}")
            print(f"   Destination: {self.destination}")
            print(f"   State: {self.state}")
        
        neighbors = self.model.grid.get_neighborhood(
            self.pos, moore=False, include_center=False
        )
        
        # Listas separadas para priorizar
        forward_options = []  # Opciones que NO son reversa
        backward_options = [] # Opción de volver por donde vine
        
        # Calcular vector de reversa (lo opuesto a mi último movimiento)
        backward_direction = None
        if self.last_move:
            backward_direction = (-self.last_move[0], -self.last_move[1])

        for n in neighbors:
            # Validar conectividad del grafo y semáforos
            if self.model.G.has_edge(self.pos, n):
                weight = self.model.G.edges[self.pos, n]['weight']
                dx = n[0] - self.pos[0]
                dy = n[1] - self.pos[1]
                direction = (dx, dy)
                
                # Inercia: Bonificar fuertemente seguir recto
                if self.last_move and direction == self.last_move:
                    weight *= 0.1  # Bonificación masiva (antes 0.5)
                
                # [LOGGING DETALLE DE VECINO]
                if self.is_under_observation:
                    light_ok = self.can_pass_traffic_light(n)
                    move_ok = self.can_move_to(n)
                    
                    # Obtener estado del semáforo si existe
                    light_status = "No Light"
                    cell_contents = self.model.grid.get_cell_list_contents([n])
                    for agent in cell_contents:
                        if isinstance(agent, TrafficLight):
                            light_status = f"{agent.state} ({agent.direction})"
                            break
                    
                    print(f"   → Neighbor {n}:")
                    print(f"     Weight: {weight:.1f} (direction={direction})")
                    print(f"     LightOK: {light_ok}, MoveOK: {move_ok}")
                    print(f"     LightStatus: {light_status}")
                    
                    # Si MoveOK es False, mostrar por qué
                    if not move_ok:
                        occupants = [type(a).__name__ for a in cell_contents]
                        print(f"     Occupants: {occupants}")
                
                # Clasificar opción
                option = (n, weight, direction)
                
                if backward_direction and direction == backward_direction:
                    backward_options.append(option)
                else:
                    forward_options.append(option)

        # EMERGENCIA: Si muy atorado, forzar decisión
        if self.stuck_counter > 15:
            print(f"\n🚨 EMERGENCY ESCAPE: Car {self.unique_id} forcing move after {self.stuck_counter} stuck steps")
            
            # Opción 1: Intentar U-turn forzado
            if backward_options:
                print(f"   → Taking emergency U-turn to {backward_options[0][0]}")
                return backward_options[0][0]
            
            # Opción 2: Resetear inercia y recalcular
            self.last_move = None
            self.stuck_counter = 0
            print(f"   → Resetting inercia for next step")
            return None  # Re-evaluar próximo step sin inercia

        # 1. Intentar moverse hacia adelante/lados primero
        # Ordenar por peso
        forward_options.sort(key=lambda x: x[1])
        
        # [LOGGING DECISION]
        if self.is_under_observation:
            print(f"   ✅ DECISION: Trying options in order...")
        
        for pos, weight, direction in forward_options:
            # Si semáforo ROJO en mi mejor opción, ESPERAR (no dar vuelta en U)
            if not self.can_pass_traffic_light(pos):
                if self.is_under_observation:
                    print(f"   ❌ STUCK: No valid move found. Red light blocks best option.")
                    print("")
                return None 
                
            if self.can_move_to(pos):
                if self.is_under_observation:
                    print(f"   ✅ MOVING: To {pos}")
                    print("")
                return pos
        
        # 2. Si no hay opciones adelante (callejón sin salida o bloqueado por coches)
        # Solo entonces consideramos volver atrás
        if not forward_options and backward_options:
            back_pos = backward_options[0][0]
            if self.can_pass_traffic_light(back_pos) and self.can_move_to(back_pos):
                if self.is_under_observation:
                    print(f"   ⚠️ U-TURN: No forward options, taking U-turn to {back_pos}")
                    print("")
                return back_pos

        # 3. Si todo falla (bloqueado total)
        # [LOGGING FALLBACK]
        if self.is_under_observation:
            print(f"   ❌ STUCK: No valid move found. All options blocked/red.")
            print("")
        
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
