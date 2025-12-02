using UnityEngine;

public class TrafficLightController : MonoBehaviour
{
    [Header("Luz Components")]
    public GameObject greenLightObject;   // Child: GreenLight
    public GameObject yellowLightObject;  // Child: YellowLight
    public GameObject redLightObject;     // Child: RedLight

    [Header("Renderers")]
    private Renderer greenRenderer;
    private Renderer yellowRenderer;
    private Renderer redRenderer;

    [Header("Materials")]
    public Material greenMaterial;
    public Material yellowMaterial;
    public Material redMaterial;

    private string currentState = "Green";

    void Awake()
    {
        // Obtener Renderers de cada luz
        if (greenLightObject != null)
            greenRenderer = greenLightObject.GetComponent<Renderer>();
        
        if (yellowLightObject != null)
            yellowRenderer = yellowLightObject.GetComponent<Renderer>();
        
        if (redLightObject != null)
            redRenderer = redLightObject.GetComponent<Renderer>();
    }

    /// <summary>
    /// Actualiza el estado del semáforo (Green, Yellow, Red).
    /// Solo la luz correspondiente se enciende; las otras se apagan.
    /// </summary>
    public void SetTrafficLightState(string state)
    {
        currentState = state;

        // Apagar todas las luces primero
        SetLightActive(greenRenderer, false);
        SetLightActive(yellowRenderer, false);
        SetLightActive(redRenderer, false);

        // Encender solo la que corresponde
        switch (state.ToLower())
        {
            case "green":
                SetLightActive(greenRenderer, true, greenMaterial);
                break;
            case "yellow":
                SetLightActive(yellowRenderer, true, yellowMaterial);
                break;
            case "red":
                SetLightActive(redRenderer, true, redMaterial);
                break;
            default:
                Debug.LogWarning($"Estado desconocido para semáforo: {state}");
                break;
        }
    }

    /// <summary>
    /// Activa o desactiva una luz cambiando su material.
    /// </summary>
    private void SetLightActive(Renderer renderer, bool isActive, Material activeMaterial = null)
    {
        if (renderer == null) return;

        if (isActive && activeMaterial != null)
        {
            renderer.material = activeMaterial;
            renderer.enabled = true;
        }
        else
        {
            renderer.enabled = false;
        }
    }

    public string GetCurrentState()
    {
        return currentState;
    }
}
