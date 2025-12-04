# MesaServer/server.py
import asyncio
import websockets
import json
from model import CityModel

MODEL_WIDTH = 24
MODEL_HEIGHT = 24
WS_HOST = "localhost"
WS_PORT = 8765
DEBUG_DIAGNOSTICS = True

# Instanciamos el modelo de la ciudad
model = CityModel(width=MODEL_WIDTH, height=MODEL_HEIGHT)
connected = set()

def analyze_agents(agents_data):
    """Analiza y loguea estadísticas y anomalías de los agentes."""
    if not DEBUG_DIAGNOSTICS:
        return 0

    counts = {
        "Car": 0, "PoliceCar": 0, "ChaoticCar": 0, 
        "TrafficLight": 0, "Destination": 0, "Obstacle": 0
    }
    
    states = {
        "Car": {}, "ChaoticCar": {}, "PoliceCar": {}
    }
    
    min_x, max_x = MODEL_WIDTH, -1
    min_y, max_y = MODEL_HEIGHT, -1
    border_agents = 0
    anomalies = 0
    
    # Valid States Definition
    VALID_STATES = {
        "Car": {"DRIVING", "WANDERING", "PARKED", "CRASHED", None},
        "ChaoticCar": {"CHAOS", "ESCAPING", "ARRESTED", None},
        "PoliceCar": {"PATROL", "CHASE", "ARRESTING", "COOLDOWN", None},
        "TrafficLight": {"Green", "Yellow", "Red"},
        "Destination": {"Free", "Reserved", "Occupied", None},
    }

    cell_counts = {}

    for agent in agents_data:
        a_type = agent["agent_type"]
        state = agent.get("state") # Use .get() to avoid KeyError if state is missing
        x, y = agent["x"], agent["y"]
        
        # 1. Counts
        if a_type in counts:
            counts[a_type] += 1
        else:
            print(f"⚠️ ANOMALÍA: agent_type desconocido: {a_type} para ID={agent['id']}")
            anomalies += 1
            
        # 2. State Distributions
        if a_type in states:
            if state not in states[a_type]:
                states[a_type][state] = 0
            states[a_type][state] += 1
            
        # 3. Spatial Stats
        min_x = min(min_x, x)
        max_x = max(max_x, x)
        min_y = min(min_y, y)
        max_y = max(max_y, y)
        
        if x == 0 or x == MODEL_WIDTH - 1 or y == 0 or y == MODEL_HEIGHT - 1:
            border_agents += 1
            
        # 4. Anomalies
        # Out of bounds
        if not (0 <= x < MODEL_WIDTH and 0 <= y < MODEL_HEIGHT):
            print(f"⚠️ ANOMALÍA: Agent ID={agent['id']} tipo={a_type} fuera de rango en pos=({x},{y})")
            anomalies += 1
            
        # Invalid State
        if a_type in VALID_STATES:
            if state not in VALID_STATES[a_type]:
                print(f"⚠️ ANOMALÍA: Estado inesperado state={state} para tipo={a_type} (ID={agent['id']})")
                anomalies += 1
        
        # High Density
        pos = (x, y)
        cell_counts[pos] = cell_counts.get(pos, 0) + 1
        if cell_counts[pos] > 4:
             print(f"⚠️ ANOMALÍA: Alta densidad en celda ({x},{y}): {cell_counts[pos]} agentes")
             anomalies += 1

    # Logic Anomaly: Chaotic active but no Police
    if counts["ChaoticCar"] > 0 and counts["PoliceCar"] == 0:
        print("⚠️ ANOMALÍA: Hay caóticos activos pero ningún PoliceCar presente.")
        anomalies += 1

    # --- PRINT REPORT ---
    print(f"\n--- STEP REPORT ---")
    print(f"🧮 Stats -> Cars: {counts['Car']} | Police: {counts['PoliceCar']} | Chaotic: {counts['ChaoticCar']} | TL: {counts['TrafficLight']} | Dest: {counts['Destination']} | Obst: {counts['Obstacle']}")
    
    # Format States
    def fmt_states(d): return ", ".join([f"{k}: {v}" for k, v in d.items()])
    
    print(f"🎭 Estados Car -> {fmt_states(states['Car'])}")
    print(f"😈 Estados Chaotic -> {fmt_states(states['ChaoticCar'])}")
    print(f"🚓 Estados Police -> {fmt_states(states['PoliceCar'])}")
    print(f"🧭 Bounds -> x:[{min_x},{max_x}], y:[{min_y},{max_y}], Bordes ocupados: {border_agents}")
    
    if anomalies == 0:
        print("✅ Diagnostics OK (0 anomalías)")
    else:
        print(f"⚠️ Diagnostics: {anomalies} anomalías detectadas este step (ver líneas anteriores)")
        
    return anomalies

async def broadcast_state():
    """Envía el estado actual del modelo a todos los clientes conectados."""
    if not connected:
        return
        
    agents_data = model.serialize_grid()
    
    # [DIAGNÓSTICO]
    analyze_agents(agents_data)
    
    world_state = {
        "type": "update", 
        "agents": agents_data
    }
    msg = json.dumps(world_state)
    
    # Enviar a todos los clientes conectados
    await asyncio.gather(*[ws.send(msg) for ws in connected])

async def process_message(message: str):
    """Procesa mensajes JSON desde Unity."""
    try:
        data = json.loads(message)
    except Exception as e:
        print("Error parseando JSON:", e)
        return
    
    msg_type = data.get("type", "")
    
    if msg_type == "step":
        # Ejecutar un paso de la simulación
        model.step()
    else:
        print(f"⚠️ Tipo de mensaje desconocido: {msg_type}")

async def handler(ws):
    """Maneja la conexión de un cliente (Unity)."""
    # print("🎮 Unity conectado")
    connected.add(ws)
    try:
        # Enviar estado inicial al conectar
        # print("📤 Enviando estado inicial...")
        await broadcast_state()
        
        # Procesar mensajes de Unity
        async for message in ws:
            await process_message(message)
            # Enviar estado actualizado inmediatamente después de procesar
            await broadcast_state()
            
    except websockets.ConnectionClosed:
        pass  # print("🔌 Unity desconectado")
    finally:
        connected.remove(ws)

async def main():
    async with websockets.serve(handler, WS_HOST, WS_PORT):
        print(f"🚀 Servidor Mesa corriendo en ws://{WS_HOST}:{WS_PORT}")
        print(f"📊 Modelo inicializado: {MODEL_WIDTH}x{MODEL_HEIGHT}")
        print(f"🗺️ Grafo: {len(model.G.nodes)} nodos, {len(model.G.edges)} aristas")
        print(f"🎯 Destinos: {len(model.destinations)}")
        print("⏳ Esperando conexión de Unity...")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Servidor detenido.")