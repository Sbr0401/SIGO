# SIGO - Sistema Inteligente de Guiado y Orientación

**Sistema de Navegación Completo con IA**

Este es el directorio consolidado de SIGO con todos los archivos necesarios.

## 📁 Estructura de Directorios

```
SIGO-FINAL/
├── SIGO1.py                         # Aplicación principal
├── config.py                        # Configuración centralizada del sistema
├── face_recognition_insightface.py  # Motor de reconocimiento facial (ArcFace ONNX)
├── yolov8s-pose.pt                  # Modelo YOLOv8 de detección de poses
├── yolo11n.pt                       # Modelo YOLOv11 de detección de objetos
├── .env.example                     # Plantilla de variables de entorno
├── run_sigo_local.bat               # Lanzador con Ollama (LLM local)
├── setup_sigo.bat                   # Instalación automatizada (menú interactivo)
├── setup_scrcpy.bat                 # Configuración de scrcpy (Android)
├── launch_scrcpy_wireless.bat       # Conexión wireless scrcpy
│
├── Utilidades
│   ├── calibrate_distance.py        # Calibración de distancias por pose
│   └── test_connection.py           # Prueba de conexión Serial/WiFi
│
├── calibration/
│   ├── calINSPIRO.npz               # Calibración de cámara (estándar)
│   └── calS24.npz                   # Calibración de cámara (Samsung S24)
│
├── requirements/
│   ├── requirements.txt             # Dependencias principales
│   ├── requirements-cpu.txt         # Optimizado para CPU
│   ├── requirements-performance.txt # Paquetes de rendimiento
│   └── requirements-face.txt        # Reconocimiento facial (onnxruntime-gpu)
│
├── face_database/                   # Base de datos facial (empieza vacía)
│
└── docs/
    ├── README.md                    # Documentación completa (inglés)
    ├── KEYBINDS.md                  # Atajos de teclado
    ├── INSTALLATION.md              # Instrucciones de instalación
    ├── FACE_RECOGNITION.md          # Guía de reconocimiento facial
    ├── POSE_DISTANCE_INTEGRATION.md # Estimación de distancia por pose
    └── ... (más documentos)
```

## 🚀 Inicio Rápido

### Método 1: Instalación Automática (Recomendado) ⭐

**Doble clic en `setup_sigo.bat`** y sigue el menú interactivo:

```
1. Selecciona "Instalación Completa" (opción 1)
2. Espera a que termine (creará entorno virtual e instalará todo)
3. Configura tu OpenAI API Key (opción 8) o usa Ollama local
4. ¡Listo! Ejecuta: python SIGO1.py
```

El script automáticamente:
- ✅ Verifica Python
- ✅ Crea entorno virtual
- ✅ Instala todas las dependencias
- ✅ Descarga modelo ArcFace para reconocimiento facial
- ✅ Verifica la instalación

### Método 2: Instalación Manual

#### 1. Configurar Entorno
```bash
cd SIGO-FINAL

# Crear entorno virtual
python -m venv .venv

# Activar
.venv\Scripts\activate  # Windows

# Instalar dependencias
pip install -r requirements\requirements.txt

# Opcional: Reconocimiento facial (ArcFace via ONNX Runtime)
pip install -r requirements\requirements-face.txt
```

#### 2. Ejecutar SIGO
```bash
python SIGO1.py
```

Los modelos YOLO se descargan automáticamente en la primera ejecución.
El modelo ArcFace (~174MB) se descarga automáticamente al activar reconocimiento facial.

#### 3. (Opcional) Reconocimiento Facial
El reconocimiento facial se activa automáticamente al iniciar. Para registrar
rostros, usa la consola integrada:
```
save person 1 as Juan       ← Registrar persona 1 como "Juan"
remove Juan                  ← Eliminar a Juan de la base de datos
go to Juan                   ← Navegar hacia Juan
```

## 📋 Requisitos del Sistema

- Python 3.12 (recomendado)
- Windows 10/11
- NVIDIA GPU (RTX series recomendado) o CPU
- Webcam o teléfono Android con depuración USB
- Ollama (para LLM local gratuito) o Clave API de OpenAI

## 🎯 Características

- ✅ Seguimiento de personas con YOLOv8-Pose + ByteTrack
- ✅ Reconocimiento facial en tiempo real (ArcFace ONNX, ~10ms/GPU)
- ✅ Registro de rostros en vivo desde la consola
- ✅ Navegación por nombre ("ve a Juan", "sigue a María")
- ✅ Control por voz (Español/Inglés via faster-whisper)
- ✅ Comandos en lenguaje natural vía LLM (Ollama local o OpenAI)
- ✅ Descarga automática de modelos (YOLO + ArcFace)
- ✅ Cámara de teléfono Android (scrcpy / Smart View / MJPEG)
- ✅ Estimación de distancia en tiempo real (pose-based)
- ✅ Control manual y autónomo
- ✅ GUI dual: System Log + Command Console
- ✅ Video de múltiples fuentes (webcam/IP/scrcpy/Smart View)

## 🎮 Controles

| Tecla | Acción |
|-----|--------|
| `TAB` | Salir de SIGO |
| `3` (mantener) | Grabar comando de voz (4 segundos) |
| `4` | Activar/desactivar reconocimiento facial |
| `5` | Cancelar navegación |
| `6` | Modo velocidad segura |
| `7` | Activar/desactivar control manual |
| `8` | Activar/desactivar reconocimiento gestual |

### Modo Manual (tecla `7`)
| Tecla | Acción | Bit |
|-------|--------|-----|
| `J` | Rotar anti-horario | 0 |
| `L` | Rotar horario | 1 |
| `I` | Izquierda | 2 |
| `K` | Derecha | 3 |
| `U` | Avanzar | 4 |
| `O` | Retroceder | 5 |
| `F` | Velocidad rápida | 7 |

## 💬 Ejemplos de Comandos

```
Texto: "ve a la persona 1"
       "sigue a Juan"
       "busca a María"
       "save person 1 as Juan"
       "remove Juan"

Voz:   "Ve a la persona uno"
       "Sigue a Juan"
       "Busca a María"
```

## 🌐 LLM Local (Ollama - Gratuito)

```bash
# Instalar Ollama desde https://ollama.com/download
# Luego:
ollama pull llama3.1

# Ejecutar SIGO con LLM local:
run_sigo_local.bat
```

O copia `.env.example` y configura las variables de entorno manualmente.

## 📚 Documentación

Ver carpeta `docs/` para guías completas:
- [docs/README.md](docs/README.md) - Documentación completa del sistema
- [docs/KEYBINDS.md](docs/KEYBINDS.md) - Todos los atajos de teclado
- [docs/INSTALLATION.md](docs/INSTALLATION.md) - Instalación detallada
- [docs/FACE_RECOGNITION.md](docs/FACE_RECOGNITION.md) - Guía de reconocimiento facial
- [docs/POSE_DISTANCE_INTEGRATION.md](docs/POSE_DISTANCE_INTEGRATION.md) - Estimación de distancia

## 🔧 Configuración

Editar `config.py` para personalizar:
- Conexiones de hardware (Serial auto-detecta Arduino, WiFi necesita IPs)
- Resolución scrcpy (`Config.Source.SCRCPY_WIDTH/HEIGHT`)
- Modelos de IA (YOLO, Whisper, ArcFace)
- Parámetros de navegación
- Opciones de reconocimiento facial
- Atajos de teclado

Ver `.env.example` para variables de entorno (LLM).

## 🖥️ GPU (RTX 50-series / Blackwell)

Si tienes una RTX 5060/5070/5080/5090, necesitas PyTorch nightly con CUDA 12.8:

```bash
pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128
```

## 🛠️ Soporte

1. Consultar documentación en `docs/`
2. Verificar conexión: `python test_connection.py`
3. Verificar instalación: opción 6 en `setup_sigo.bat`

## 📝 Licencia

Uso de Investigación/Educativo

---

**Autor**: Yosef
**Versión**: 2.0
**Actualizado**: Febrero 2026
