# MesaServer/server.py
import asyncio
import websockets
import json
from model import CityModel

MODEL_WIDTH = 24
MODEL_HEIGHT = 24
WS_HOST = "localhost"
WS_PORT = 8765

# Instanciamos el modelo de la ciudad
model = CityModel(width=MODEL_WIDTH, height=MODEL_HEIGHT)
connected = set()


async def broadcast_state():
    """Envía el estado actual del modelo a todos los clientes conectados.
    
    Formato del mensaje:
    {
        "type": "update",
        "agents": [
            {
                "id": 1,
                "x": 5,
                "y": 10,
                "agent_type": "Car" | "TrafficLight" | "Obstacle" | "Destination",
                "state": "Green" | "Yellow" | "Red" (para semáforos) | "Moving" (coches) | null,
                "direction": "NS" | "EW" (solo semáforos) | null
            },
            ...
        ]
    }
    """
    if not connected:
        return
        
    agents_data = model.serialize_grid()
    
    # [DIAGNÓSTICO] Interceptar y analizar datos antes de enviar
    police_info = []
    chaotic_info = []
    
    for agent in agents_data:
        a_type = agent["agent_type"]
        pos_str = f"{agent['id']}:({agent['x']},{agent['y']})"
        
        if a_type == "PoliceCar":
            police_info.append(pos_str)
        elif a_type == "ChaoticCar":
            chaotic_info.append(pos_str)
    
    # Imprimir reporte detallado
    print(f"\n--- STEP REPORT ---")
    print(f"📊 Total Agentes: {len(agents_data)}")
    print(f"🚓 Policías ({len(police_info)}): {', '.join(police_info) if police_info else 'NINGUNO'}")
    print(f"😈 Caóticos ({len(chaotic_info)}): {', '.join(chaotic_info) if chaotic_info else 'NINGUNO'}")
    print(f"-------------------")
    
    world_state = {
        "type": "update", 
        "agents": agents_data
    }
    msg = json.dumps(world_state)
    
    # Enviar a todos los clientes conectados
    await asyncio.gather(*[ws.send(msg) for ws in connected])
    # print(f"➡️ Estado enviado a Unity: {len(agents_data)} agentes")


async def process_message(message: str):
    """Procesa mensajes JSON desde Unity.
    
    Simulación paso a paso controlada por el cliente:
    - Unity envía {'type': 'step'} para avanzar la simulación
    - El servidor ejecuta model.step() y responde automáticamente con el estado actualizado
    """
    try:
        data = json.loads(message)
    except Exception as e:
        print("Error parseando JSON:", e)
        return
    
    msg_type = data.get("type", "")
    
    if msg_type == "step":
        # Ejecutar un paso de la simulación
        model.step()
        
        # [MEJORA] Log detallado por tipo (comentado, usamos STEP REPORT)
        # police = [a for a in model.schedule.agents if type(a).__name__ == 'PoliceCar']
        # chaotic = [a for a in model.schedule.agents if type(a).__name__ == 'ChaoticCar']
        # cars = [a for a in model.schedule.agents if type(a).__name__ == 'Car']
        # print(f"✅ Step. Stats -> 🚓 Policías: {len(police)} | 😈 Caos: {len(chaotic)} | 🚙 Civiles: {len(cars)}")
    else:
        print(f"⚠️ Tipo de mensaje desconocido: {msg_type}")


async def handler(ws):
    """Maneja la conexión de un cliente (Unity).
    
    Flujo de simulación paso a paso:
    1. Unity se conecta → Se envía estado inicial
    2. Unity envía {'type': 'step'} → model.step() se ejecuta → Estado actualizado se envía
    3. Unity recibe {'type': 'update', 'agents': [...]} con todos los agentes y sus estados
    """
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