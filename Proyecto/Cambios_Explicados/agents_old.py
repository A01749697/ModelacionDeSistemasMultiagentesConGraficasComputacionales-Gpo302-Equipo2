"""
AGENTS.PY - Refactorización Completa
====================================
Fixes implementados:
- BUG A: Ciclo PARKED → release() → WANDERING sin desapariciones
- BUG B: get_wandering_move() espera en semáforos en lugar de bailar
- BUG C: Eliminación de stuck_counter y lógica de despawn
- BUG D: Spawn mejorado con get_random_spawn_point()
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
        self.patience = 3  # Intentos antes de recalcular ruta
        self.do_not_park_here = None  # Evitar re-parking inmediato
        
        # DIAGNÓSTICO
        self.debug = (unique_id == 0)  # Solo agente 0 por defecto

    def step(self):
        """Avanza un paso en la simulación con máquina de estados clara."""
        
        if self.debug:
            print(f"🚗 CAR {self.unique_id} | pos={self.pos}, dest={self.destination}, state={self.state}")

        # 1. ESTADO CRASHED - Inmóvil permanentemente
        if self.state == "CRASHED":
            return

        # 2. ESTADO PARKED - Temporizador hasta salida
        if self.state == "PARKED":
            self.parking_timer -= 1
            
            if self.parking_timer <= 0:
                # *** FIX BUG A: Ciclo completo de liberación ***
                if self.destination:
                    self.do_not_park_here = self.destination
                    self.destination.release()  # Libera reserva Y ocupante
                    self.destination = None
                
                self.state = "WANDERING"
                self.path = []  # Limpiar ruta anterior
                
                if self.debug:
                    print(f"🚗 CAR {self.unique_id} EXITING PARKING → WANDERING")
            
            return  # Permanece en posición hasta salir

        # 3. ESTADO DRIVING - Navegación con destino
        if self.destination:
            # 3.A. Llegada al destino
            if self.pos == self.destination.pos:
                self.state = "PARKED"
                self.parking_timer = self.parking_limit
                self.destination.occupant = self
                
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
                    self.model.grid.move_agent(self, next_pos)
                    self.path.pop(0)
                    self.patience = 3
                else:
                    # Paciencia: si estoy bloqueado, recalcular ruta después de N intentos
                    self.patience -= 1
                    if self.patience <= 0:
                        self.calculate_path()
                        self.patience = 3

        # 4. ESTADO WANDERING - Búsqueda de destino
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

            # 4.C. Si no encontró, vagar aleatoriamente
            self.state = "WANDERING"
            next_pos = self.get_wandering_move()
            
            if next_pos:
                self.model.grid.move_agent(self, next_pos)
            # Si next_pos es None, espera (por semáforo rojo)

    def get_wandering_move(self):
        """
        *** FIX BUG B: Decide movimiento WANDERING evitando "baile" en semáforos ***
        
        Estrategia:
        1. Si mejor opción (recto) está bloqueada por SEMÁFORO → ESPERAR (return None)
        2. Si mejor opción está bloqueada por COCHE → Intentar siguiente opción
        3. Priorizar peso bajo (ir recto) sobre cambio de carril
        """
        
        neighbors = self.model.grid.get_neighborhood(
            self.pos, moore=False, include_center=False
        )
        valid_options = []

        # Obtener vecinos conectados en el grafo
        for n in neighbors:
            if self.model.G.has_edge(self.pos, n):
                weight = self.model.G.edges[self.pos, n]['weight']
                valid_options.append((n, weight))

        # Ordenar por peso (peso 1 = recto, peso 10 = cambio carril)
        valid_options.sort(key=lambda x: x[1])

        if not valid_options:
            return None

        # REGLA PRIORITARIA: Evaluación del primer candidato (recto)
        best_pos, best_weight = valid_options[0]

        # *** CLAVE: Si semáforo ROJO/AMARILLO bloquea la mejor opción, ESPERAR ***
        if not self.can_pass_traffic_light(best_pos):
            if self.debug:
                print(f"🛑 CAR {self.unique_id} WAITING at red light towards {best_pos}")
            return None  # NO BAILAR - solo esperar

        # Si recto está disponible (semáforo verde y sin coches), tomar
        if self.can_move_to(best_pos):
            return best_pos

        # Si recto no está disponible (otro coche), intentar alternativas
        for next_pos, weight in valid_options[1:]:
            # Verificar semáforo para esta opción
            if not self.can_pass_traffic_light(next_pos):
                continue  # Esta alternativa también tiene rojo, saltar
            
            if self.can_move_to(next_pos):
                return next_pos

        return None

    def can_pass_traffic_light(self, pos):
        """
        Verifica si el semáforo permite el paso hacia 'pos'.
        
        Regla de Oro: Si ya estoy DENTRO de una intersección (en self.pos),
        siempre permitir avance para despejar el cruce.
        """
        
        # 1. ¿Estoy ya dentro de una intersección?
        my_cell_contents = self.model.grid.get_cell_list_contents([self.pos])
        am_in_intersection = any(
            isinstance(a, TrafficLight) for a in my_cell_contents
        )
        
        if am_in_intersection:
            return True  # Siempre despejar intersección

        # 2. ¿Hay semáforo en la celda destino?
        cell_contents = self.model.grid.get_cell_list_contents([pos])
        
        for agent in cell_contents:
            if isinstance(agent, TrafficLight):
                if agent.state == "Green":
                    return True

                elif agent.state in ["Red", "Yellow"]:
                    # Bloqueo por ejes: NS bloquea movimiento vertical, EW bloquea horizontal
                    dx = pos[0] - self.pos[0]
                    dy = pos[1] - self.pos[1]

                    if agent.direction == "NS":  # Bloquea N-S (dy != 0)
                        if dy != 0:
                            return False  # Movimiento vertical bloqueado
                    
                    elif agent.direction == "EW":  # Bloquea E-W (dx != 0)
                        if dx != 0:
                            return False  # Movimiento horizontal bloqueado

                return True

        return True  # Sin semáforo, permitir

    def can_move_to(self, pos):
        """
        Verifica si el coche puede moverse a la posición.
        Chequea: límites grafo, semáforos, coches, obstáculos, protección parking.
        """
        
        # Verificar si pos está en grafo y hay arista
        if pos not in self.model.G:
            return False
        
        if not self.model.G.has_edge(self.pos, pos):
            return False

        # Verificar semáforo (usa lógica reutilizada)
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
        """
        Contract Net Protocol: Solicita ofertas de todos los destinos.
        Elige el más cercano disponible.
        """
        
        best_bid = float('inf')
        best_dest = None

        for dest in self.model.destinations:
            # Ignorar el parking del que acabo de salir
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
        """Calcula ruta usando Dijkstra ponderado (A* simplificado)."""
        
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
            
            # Remover el primer nodo (posición actual)
            if len(self.path) > 0:
                self.path.pop(0)
        
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            # Ruta imposible - liberar destino y volver a WANDERING
            self.destination.release()
            self.destination = None
            self.state = "WANDERING"
            self.path = []


class TrafficLight(Agent):
    """Semáforo con ciclo Green → Yellow → Red → Green."""

    def __init__(self, unique_id, model, direction="NS", state="Green", time_offset=0):
        super().__init__(unique_id, model)
        self.direction = direction  # "NS" (Norte-Sur) o "EW" (Este-Oeste)
        self.state = state
        self.timer = 10 - time_offset if state == "Green" else 10
        
        # Tiempos fijos por fase
        self.green_time = 10
        self.yellow_time = 3
        self.red_time = 10

    def step(self):
        """Decrementa timer y cambia estado cíclicamente."""
        
        self.timer -= 1

        if self.timer <= 0:
            # Cambiar de estado
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
    """Edificio u obstáculo estático (no se mueve)."""

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
        self.occupant = None  # Coche estacionado
        self.reserved_by = None  # Coche en ruta

    def step(self):
        pass

    def calculate_bid(self, car_pos):
        """Calcula oferta de distancia si está disponible."""
        
        if self.occupant is not None or self.reserved_by is not None:
            return float('inf')  # No disponible

        # Distancia Manhattan
        dx = abs(self.pos[0] - car_pos[0])
        dy = abs(self.pos[1] - car_pos[1])
        return dx + dy

    def book(self, car_agent):
        """Reserva destino para un coche (cambiar a amarillo)."""
        self.reserved_by = car_agent
        return True

    def release(self):
        """
        Libera destino completamente.
        FIX BUG A: Resetear AMBOS occupant y reserved_by
        """
        self.occupant = None
        self.reserved_by = None


class ChaoticCar(Car):
    """
    Vehículo caótico que ignora semáforos y causa choques.
    Hereda de Car pero sobrescribe can_move_to() y step().
    """
    def can_pass_traffic_light(self, pos):
        return True  # ¡Soy caótico, siempre paso!

    def __init__(self, unique_id, model, destination=None, parking_limit=3):
        super().__init__(unique_id, model, destination, parking_limit)
        self.state = "CHAOS"

    def can_move_to(self, pos):
        """Ignora semáforos, solo verifica grafo y obstáculos estáticos."""
        
        if pos not in self.model.G:
            return False

        if not self.model.G.has_edge(self.pos, pos):
            return False

        cell_contents = self.model.grid.get_cell_list_contents([pos])

        # Solo bloquea obstáculos estáticos, IGNORA semáforos y otros coches
        for agent in cell_contents:
            if isinstance(agent, Obstacle):
                return False

        return True

    def step(self):
        """Movimiento caótico sin reglas de tránsito normales."""
        
        # 1. Calcular ruta si tiene destino
        if self.destination and not self.path:
            self.calculate_path()

        # 2. Vagar si no tiene destino
        if not self.destination:
            self.state = "WANDERING"
            neighbors = self.model.grid.get_neighborhood(
                self.pos, moore=False, include_center=False
            )
            valid = [n for n in neighbors if self.can_move_to(n)]
            
            if valid:
                self.model.grid.move_agent(self, random.choice(valid))
            return

        # 3. Seguir ruta o buscar nuevos objetivos
        if self.path:
            next_pos = self.path[0]

            # Detectar colisión con Car normal
            cell_contents = self.model.grid.get_cell_list_contents([next_pos])
            victim = None
            
            for agent in cell_contents:
                if isinstance(agent, Car) and not isinstance(agent, ChaoticCar):
                    victim = agent
                    break

            if victim:
                # CRASH: Marcar víctima como CRASHED
                victim.state = "CRASHED"

                # ChaoticCar huye
                self.destination = None
                self.path = []

                # Escapar a vecino aleatorio
                neighbors = self.model.grid.get_neighborhood(
                    self.pos, moore=False, include_center=False
                )
                valid = [n for n in neighbors if self.can_move_to(n)]
                
                if valid:
                    self.model.grid.move_agent(self, random.choice(valid))
            else:
                # Sin colisión, avanzar
                if self.can_move_to(next_pos):
                    self.model.grid.move_agent(self, next_pos)
                    self.path.pop(0)
                else:
                    # Recalcular ruta si está bloqueado
                    self.path = []



class PoliceCar(Car):
    """
    Patrulla que persigue ChaoticCars.
    Hereda de Car pero sobrescribe step() con lógica PATROL/CHASE.
    """

    def __init__(self, unique_id, model, destination=None, parking_limit=3, checkpoints=None):
        super().__init__(unique_id, model, destination, parking_limit)
        self.checkpoints = checkpoints if checkpoints else []
        self.current_checkpoint_index = 0
        self.state = "PATROL"

    def step(self):
        """PATROL → detect ChaoticCar → CHASE → pursue → return PATROL."""
        
        # 1. Detectar ChaoticCar en radio
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
                    self.model.grid.move_agent(self, next_pos)
                return

            # Con checkpoints: patrullar
            target_pos = self.checkpoints[self.current_checkpoint_index]

            if self.pos == target_pos:
                # Avanzar al siguiente checkpoint
                self.current_checkpoint_index = (
                    self.current_checkpoint_index + 1
                ) % len(self.checkpoints)
                target_pos = self.checkpoints[self.current_checkpoint_index]

            try:
                path = nx.shortest_path(self.model.G, self.pos, target_pos)
                
                if len(path) > 1:
                    next_pos = path[1]
                    if self.can_move_to(next_pos):
                        self.model.grid.move_agent(self, next_pos)
            
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                # Checkpoint inalcanzable, pasar al siguiente
                self.current_checkpoint_index = (
                    self.current_checkpoint_index + 1
                ) % len(self.checkpoints)