# SIGO — Sistema Inteligente de Guiado y Orientación

> Sistema de navegación autónoma con IA para plataformas robóticas.
> Detección de personas (YOLOv8-Pose), reconocimiento facial (ArcFace),
> comandos de voz (Whisper) y control adaptativo vía Arduino.

## 📁 Estructura del Proyecto

```
SIGO-FINAL/
├── SIGO1.py                         # Aplicación principal (~4 700 líneas)
├── config.py                        # Configuración centralizada
├── face_recognition_insightface.py  # Reconocimiento facial (ArcFace / ONNX)
├── calibrate_distance.py            # Calibración de distancia por pose
├── test_connection.py               # Prueba de conexión Serial / WiFi
│
├── yolov8s-pose.pt                  # Modelo de pose (17 keypoints)
├── yolo11n.pt                       # YOLO fallback (detección de personas)
├── .env.example                     # Plantilla de variables de entorno
│
├── setup_sigo.bat                   # Instalador interactivo (recomendado)
├── run_sigo_local.bat               # Lanzador con Ollama (LLM local)
├── setup_scrcpy.bat                 # Configurar scrcpy (Android)
├── launch_scrcpy_wireless.bat       # Conexión wireless scrcpy
│
├── calibration/                     # Archivos de calibración de cámara
│   ├── calINSPIRO.npz
│   └── calS24.npz
│
├── requirements/                    # Dependencias (pip)
│   ├── requirements.txt
│   ├── requirements-cpu.txt
│   ├── requirements-face.txt
│   └── requirements-performance.txt
│
├── face_database/                   # Base de datos facial (empieza vacía)
│
└── docs/                            # Documentación extendida
    ├── KEYBINDS.md
    ├── INSTALLATION.md
    ├── FACE_RECOGNITION.md
    ├── POSE_DISTANCE_INTEGRATION.md
    └── ...
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
- ✅ Reconocimiento gestual (mano alzada = ven, ambas manos = alto)
- ✅ Comandos de voz con números en palabras ("persona uno" → persona 1)

## 🎮 Controles

| Tecla | Acción |
|-----|--------|
| `TAB` | Salir de SIGO |
| `Shift+3` (mantener) | Grabar comando de voz (4 segundos) |
| `Shift+4` | Activar/desactivar reconocimiento facial |
| `Shift+5` | Emergency stop / cancelar navegación |
| `Shift+6` | Modo velocidad segura |
| `Shift+7` | Activar/desactivar control manual |
| `Shift+8` | Activar/desactivar reconocimiento gestual |
| `Shift+9` | Buscar persona (escaneo 360°) |

### Modo Manual (`Shift+7`)
| Tecla | Acción |
|-------|--------|
| `J` | Rotar anti-horario |
| `L` | Rotar horario |
| `I` | Subir |
| `K` | Bajar |
| `U` | Avanzar |
| `O` | Retroceder |
| `N` | Strafe izquierda |
| `M` | Strafe derecha |
| `F` | Velocidad rápida (modificador) |

## 💬 Ejemplos de Comandos

```
Texto: "ve a la persona 1"
       "sigue a Juan"
       "busca a María"
       "save person 1 as Juan"
       "remove Juan"

Voz:   "Ve a la persona uno"       ← convierte 'uno' → 1
       "Sigue al número tres"     ← convierte 'tres' → 3
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
**Versión**: 2.1
**Actualizado**: Marzo 2026
