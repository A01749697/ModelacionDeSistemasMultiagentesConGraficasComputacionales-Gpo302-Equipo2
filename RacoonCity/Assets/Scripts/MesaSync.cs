using UnityEngine;
using NativeWebSocket;
using Newtonsoft.Json.Linq;
using System.Collections.Generic;
using System.Threading.Tasks;

public class MesaSync : MonoBehaviour
{
    public static MesaSync Instance;
    private WebSocket websocket;
    
    [Header("Prefabs")]
    public GameObject carPrefab;
    public GameObject policeCarPrefab; 
    public GameObject chaoticCarPrefab;
    public GameObject trafficLightPrefab;
    public GameObject obstaclePrefab;
    public GameObject destinationPrefab;
    
    [Header("Settings")]
    public Transform agentsRoot;
    public float stepInterval = 0.1f;
    public float interpolationSpeed = 5f;

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

    async void Awake()
    {
        Instance = this;
        websocket = new WebSocket("ws://localhost:8765");

        websocket.OnOpen += () => Debug.Log("Connected to Mesa WebSocket.");
        
        websocket.OnMessage += (bytes) =>
        {
            var msg = System.Text.Encoding.UTF8.GetString(bytes);
            HandleMessage(msg);
        };

        websocket.OnError += (e) => Debug.LogError("WebSocket Error: " + e);
        websocket.OnClose += (e) => Debug.Log("WebSocket closed.");

        await websocket.Connect();
    }

    private void HandleMessage(string msg)
    {
        UnityMainThreadDispatcher.Instance().Enqueue(() => {
            try 
            {
                JObject data = JObject.Parse(msg);
                var type = (string)data["type"];

                if (type == "update")
                {
                    var agents = (JArray)data["agents"];
                    ApplyMesaState(agents);
                }
            }
            catch (System.Exception e)
            {
                Debug.LogError($"Error parsing message: {e.Message}");
            }
        });
    }

    private void ApplyMesaState(JArray agents)
    {
        HashSet<int> seen = new HashSet<int>();
        
        foreach (var a in agents)
        {
            int id = (int)a["id"];
            // Casting seguro a float y luego a int si es necesario, o directo a float para posición
            float x = (float)a["x"];
            float y = (float)a["y"];
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
                    
                    var ctrl = go.GetComponent<AgentController>();
                    if (ctrl != null) ctrl.agentID = id;
                    
                    unityAgents[id] = go;
                    go.transform.localPosition = new Vector3(x, 0f, y);
                    targetPositions[id] = new Vector3(x, 0f, y);
                }
                else
                {
                    Debug.LogWarning($"No prefab found for type: {agentType}");
                }
            }
            else
            {
                targetPositions[id] = new Vector3(x, 0f, y);
            }

            // Actualizar estados específicos
            if (agentType == "TrafficLight")
            {
                UpdateTrafficLight(id, state, direction);
            }
            else if (agentType == "Destination")
            {
                UpdateDestination(id, state);
            }
            // [FIX] Puedes agregar UpdateCar aquí si quieres cambiar colores luego
             else if (agentType == "Car" || agentType == "PoliceCar" || agentType == "ChaoticCar")
            {
                UpdateCar(id, state);
            }
        }

        // Eliminar agentes muertos
        List<int> toRemove = new List<int>();
        foreach (var kv in unityAgents)
        {
            if (!seen.Contains(kv.Key))
                toRemove.Add(kv.Key);
        }
        
        foreach (int id in toRemove)
        {
            Destroy(unityAgents[id]);
            unityAgents.Remove(id);
            targetPositions.Remove(id);
        }
    } // [FIX] ¡Esta es la llave que faltaba probablemente!

    // [FIX] Método corregido para incluir Policías y Caóticos
    private GameObject GetPrefabForType(string agentType)
    {
        switch (agentType)
        {
            case "Car":
                return carPrefab;
            case "PoliceCar":
                return policeCarPrefab;
            case "ChaoticCar":
                return chaoticCarPrefab;
            case "TrafficLight":
                return trafficLightPrefab;
            case "Obstacle":
                return obstaclePrefab;
            case "Destination":
                return destinationPrefab;
            default:
                Debug.LogWarning($"Unknown agent type: {agentType}");
                return null;
        }
    }

    private void UpdateTrafficLight(int id, string state, string direction)
    {
        if (!unityAgents.ContainsKey(id)) return;
        GameObject lightGO = unityAgents[id];

        TrafficLightController trafficController = lightGO.GetComponent<TrafficLightController>();
        if (trafficController != null)
        {
            trafficController.SetTrafficLightState(state);
        }
        
        // Rotación
        if (direction == "NS") lightGO.transform.localRotation = Quaternion.Euler(0, 0, 0);
        else if (direction == "EW") lightGO.transform.localRotation = Quaternion.Euler(0, 90, 0);
    }

    // [FIX] Implementación visual basada en State Codes
    private void UpdateCar(int id, string state)
    {
        if (!unityAgents.ContainsKey(id)) return;
        
        GameObject go = unityAgents[id];
        Renderer r = go.GetComponentInChildren<Renderer>(); // Busca en hijos por si el modelo es complejo
        if (r == null) r = go.GetComponent<Renderer>();     // Fallback
        
        if (r == null) return;

        // Recuperamos el state_code del último JSON procesado no es directo aquí, 
        // así que usaremos lógica de strings o colores directos por ahora.
        // MEJORA: Para ser precisos, idealmente Unity debería recibir el "state_code" integer.
        // Pero como el JSON trae "state_code", necesitamos leerlo en ApplyMesaState o inferirlo aquí.
        
        // Vamos a inferir el color basado en el nombre del objeto que pusimos en ApplyMesaState
        // go.name es algo como "PoliceCar_201" o "ChaoticCar_250"
        
        if (go.name.Contains("Police"))
        {
            if (state == "CHASE") r.material.color = Color.red;          // Sirena
            else if (state == "ARRESTING") r.material.color = Color.cyan; // Arresto
            else r.material.color = Color.blue;                          // Patrulla
        }
        else if (go.name.Contains("Chaotic"))
        {
            if (state == "ESCAPING") r.material.color = new Color(1f, 0.5f, 0f); // Naranja
            else if (state == "ARRESTED") r.material.color = Color.gray;         // Detenido
            else r.material.color = Color.magenta;                               // Caos normal
        }
        else // Car normal
        {
             r.material.color = Color.white;
        }
    }

    private void UpdateDestination(int id, string state)
    {
        if (!unityAgents.ContainsKey(id)) return;
        GameObject go = unityAgents[id];
        Renderer r = go.GetComponent<Renderer>();
        if (r == null) return;

        switch (state)
        {
            case "Free": r.material = parkingFreeMat; break;
            case "Reserved": r.material = parkingReservedMat; break;
            case "Occupied": r.material = parkingOccupiedMat; break;
        }
    }

    void Update()
    {
        if (websocket != null) websocket.DispatchMessageQueue();

        stepTimer += Time.deltaTime;
        if (stepTimer >= stepInterval)
        {
            stepTimer = 0f;
            SendStepCommand();
        }

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
                go.transform.localPosition = Vector3.Lerp(
                    go.transform.localPosition,
                    targetPositions[id],
                    Time.deltaTime * interpolationSpeed
                );
            }
        }
    }

    private async void SendStepCommand()
    {
        if (websocket == null || websocket.State != WebSocketState.Open) return;
        
        JObject payload = new JObject();
        payload["type"] = "step";
        await websocket.SendText(payload.ToString());
    }

    public async Task SendAgentUpdate(int id, int x, int y)
    {
        // Placeholder para comunicación bidireccional si se requiere
        await Task.Yield(); 
    }
    
    public async Task SendAgentRemove(int id)
    {
         await Task.Yield();
    }

    private async void OnApplicationQuit()
    {
        if (websocket != null) await websocket.Close();
    }
}