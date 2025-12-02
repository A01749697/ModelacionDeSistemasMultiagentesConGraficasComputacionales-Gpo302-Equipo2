using UnityEngine;
using NativeWebSocket;
using Newtonsoft.Json.Linq;
using System.Collections.Generic;
using System.Threading.Tasks;

public class MesaSync : MonoBehaviour
{
    // =================================================================================
    // VARIABLES (FROM HEAD/UPSTREAM)
    // =================================================================================
    public static MesaSync Instance;
    private WebSocket websocket;
    
    [Header("Prefabs")]
    public GameObject carPrefab;
    public GameObject trafficLightPrefab;
    public GameObject obstaclePrefab;
    public GameObject destinationPrefab;
    
    [Header("Settings")]
    public Transform agentsRoot;
    public float stepInterval = 0.1f; // Tiempo entre pasos de simulación
    public float interpolationSpeed = 5f; // Velocidad de interpolación para movimiento suave

    [Header("Traffic Light Materials")]
    public Material greenLightMaterial;
    public Material yellowLightMaterial;
    public Material redLightMaterial;

    [Header("Parking Materials")]
    public Material parkingFreeMat;
    public Material parkingReservedMat;
    public Material parkingOccupiedMat;

    private Dictionary<int, GameObject> unityAgents = new Dictionary<int, GameObject>();
    private Dictionary<int, Vector3> targetPositions = new Dictionary<int, Vector3>();
    private float stepTimer = 0f;

    // Added to support Stashed logic (Interpolation)
    private Dictionary<int, Vector3> targetPositions = new Dictionary<int, Vector3>();
    public float interpolationSpeed = 5f;

    // =================================================================================
    // LOGIC
    // =================================================================================

    async void Awake()
    {
        Instance = this;
        websocket = new WebSocket("ws://localhost:8765");

        websocket.OnOpen += () =>
        {
            Debug.Log("Connected to Mesa WebSocket.");
        };

        websocket.OnMessage += (bytes) =>
        {
            var msg = System.Text.Encoding.UTF8.GetString(bytes);
            HandleMessage(msg);
        };

        websocket.OnError += (e) =>
        {
            Debug.LogError("WebSocket Error: " + e);
        };

        websocket.OnClose += (e) =>
        {
            Debug.Log(" WebSocket closed.");
        };

        await websocket.Connect();
    }

    private void HandleMessage(string msg)
    {
        // Ejecutamos esto en el hilo principal usando el Dispatcher
        UnityMainThreadDispatcher.Instance().Enqueue(() => {
            JObject data = JObject.Parse(msg);
            var type = (string)data["type"];

            if (type == "update")
            {
                var agents = (JArray)data["agents"];
                ApplyMesaState(agents);
            }
        });
    }

    private void ApplyMesaState(JArray agents)
    {
        // Marcamos los agentes vistos en esta actualización
        HashSet<int> seen = new HashSet<int>();
        
        foreach (var a in agents)
        {
            int id = (int)a["id"];
            int x = (int)a["x"];
            int y = (int)a["y"];
            string agentType = (string)a["agent_type"];
            string state = a["state"]?.ToString();
            string direction = a["direction"]?.ToString();
            
            seen.Add(id);

            // Crear agente si no existe
            if (!unityAgents.ContainsKey(id))
            {
                GameObject prefab = GetPrefabForType(agentType);
                if (prefab != null)
                {
                    var go = Instantiate(prefab, agentsRoot);
                    go.name = $"{agentType}_{id}";
                    
                    // Inicializar AgentController
                    var ctrl = go.GetComponent<AgentController>();
                    if (ctrl != null)
                    {
                        ctrl.Init(id, newPosition);
                    }
                    else
                    {
                        // Si no tiene AgentController, posicionar directamente
                        go.transform.localPosition = newPosition;
                    }
                    
                    unityAgents[id] = go;
                    Debug.Log($"[MesaSync] ✨ Spawned {agentType} with ID {id} at ({x}, {y})");
                }
            }
            else
            {
                GameObject go = unityAgents[id];
                if (go != null)
                {
                    var ctrl = go.GetComponent<AgentController>();
                    if (ctrl != null)
                    {
                        // Delegar interpolación al AgentController
                        ctrl.UpdatePosition(newPosition);
                    }
                    else
                    {
                        // Si no tiene AgentController, mover directamente
                        go.transform.localPosition = newPosition;
                    }
                }
            }

            // Actualizar estado específico del tipo de agente
            if (agentType == "TrafficLight")
            {
                UpdateTrafficLight(id, state, direction);
            }
            else if (agentType == "Car")
            {
                UpdateCar(id, state);
            }
            else if (agentType == "Destination")
            {
                UpdateDestination(id, state);
            }
        }

        // Eliminamos agentes que ya no existen en Mesa
        List<int> toRemove = new List<int>();
        foreach (var kv in unityAgents)
        {
            if (!seen.Contains(kv.Key))
                toRemove.Add(kv.Key);
        }
        
        foreach (int id in toRemove)
        {
            Debug.Log($"[MesaSync] 🗑️ Removing agent {id}");
            if (unityAgents.ContainsKey(id) && unityAgents[id] != null)
            {
        {
            #if !UNITY_WEBGL || UNITY_EDITOR
            websocket.DispatchMessageQueue();

        // Temporizador para enviar comandos de step
        stepTimer += Time.deltaTime;
        if (stepTimer >= stepInterval)
        {
            stepTimer = 0f;
            SendStepCommand();
        }

        // Interpolación suave de posiciones
        InterpolateAgentPositions();
    }

    private void InterpolateAgentPositions()
    {
        foreach (var kv in unityAgents)
        {
            int id = kv.Key;
            GameObject go = kv.Value;
            if (targetPositions.ContainsKey(id))
            {
                Vector3 targetPos = targetPositions[id];
                go.transform.localPosition = Vector3.Lerp(
                    go.transform.localPosition,
                    targetPos,
                    Time.deltaTime * interpolationSpeed
                );
            }
        }
    }

    private async void SendStepCommand()
    {
        if (websocket == null || websocket.State != WebSocketState.Open)
            return;

        JObject payload = new JObject();
        payload["type"] = "step";
        string msg = payload.ToString();
        
        await websocket.SendText(msg);
    }

    public async Task SendSpawnCarCommand()
    {
        if (websocket == null || websocket.State != WebSocketState.Open)
            return;

        JObject payload = new JObject();
        payload["type"] = "spawn_car";
        string msg = payload.ToString();
        
        await websocket.SendText(msg);
        Debug.Log("Spawn car command sent");
    }

    private async void OnApplicationQuit()
    {
        if (websocket != null)
            await websocket.Close();
    }
}