using UnityEngine;

public class CameraSwitcher : MonoBehaviour
{
    // Arreglo para almacenar todas las cámaras que quieres rotar.
    // Asigna las cámaras en el Inspector.
    public GameObject[] cameras; 

    // Índice de la cámara actualmente activa.
    private int currentCameraIndex = 0; 

    void Start()
    {
        // Validación inicial: nos aseguramos de que haya cámaras.
        if (cameras.Length == 0)
        {
            Debug.LogError("No se han asignado cámaras al script CameraSwitcher.");
            return;
        }

        // Activamos la primera cámara y desactivamos las demás.
        ActivateCamera(currentCameraIndex);
    }

    void Update()
    {
        // Chequea si la tecla 'C' es presionada.
        if (Input.GetKeyDown(KeyCode.C))
        {
            SwitchCamera();
        }
    }

    void SwitchCamera()
    {
        // Desactiva la cámara actual.
        cameras[currentCameraIndex].SetActive(false);

        // Mueve al siguiente índice. Si llegamos al final del arreglo, 
        // volvemos al principio (0).
        currentCameraIndex = (currentCameraIndex + 1) % cameras.Length;

        // Activa la nueva cámara.
        ActivateCamera(currentCameraIndex);
    }

    void ActivateCamera(int index)
    {
        if (index >= 0 && index < cameras.Length)
        {
            cameras[index].SetActive(true);
            Debug.Log("Cambiando a: " + cameras[index].name);
        }
    }
}