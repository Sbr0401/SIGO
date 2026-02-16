# SIGO - Keybinds Reference

## 📝 Configuración
Todos los keybinds se pueden modificar en **`config.py`** → Clase **`KeybindConfig`**

---

## 🎮 Controles Principales

### Ventana Principal
| Tecla | Función | Config Variable |
|-------|---------|-----------------|
| **TAB** | Salir del programa | `KEY_EXIT = 9` |
| **Backspace** | Borrar último carácter | `KEY_BACKSPACE = 8` |
| **Enter** | Enviar comando | `KEY_ENTER = 13` |
| **↑** | Historial arriba | `KEY_ARROW_UP = 72` |
| **↓** | Historial abajo | `KEY_ARROW_DOWN = 80` |

### Control por Voz
| Tecla | Función | Config Variable |
|-------|---------|-----------------|
| **3** (mantener) | Grabar voz con Whisper | `KEY_VOICE_RECORD = '3'` |

### Navegación
| Tecla | Función | Config Variable |
|-------|---------|-----------------|
| **5** | Cancelar navegación activa | `KEY_CANCEL_NAV = '5'` |

### Reconocimiento Facial
| Tecla | Función | Config Variable |
|-------|---------|------------------|
| **4** | Activar/desactivar reconocimiento facial | `KEY_FACE_RECOGNITION = ord('4')` |

---

## 🕹️ Modo Manual

### Activación
| Comando | Función | Config Variable |
|---------|---------|-----------------|
| **7** (en consola) | Activar/desactivar modo manual | `KEY_MANUAL_TOGGLE = '7'` |
| **7** (en modo manual) | Salir del modo manual | `KEY_MANUAL_EXIT = '7'` |

### Controles de Movimiento
| Tecla | Función | Bit | Config Variable |
|-------|---------|-----|------------------|
| **J** | Rotar anti-horario (CCW) | 0 | `MANUAL_ROTATE_CCW = 'j'` |
| **L** | Rotar horario (CW) | 1 | `MANUAL_ROTATE_CW = 'l'` |
| **I** | Izquierda | 2 | `MANUAL_LEFT = 'i'` |
| **K** | Derecha | 3 | `MANUAL_RIGHT = 'k'` |
| **U** | Avanzar | 4 | `MANUAL_FORWARD = 'u'` |
| **O** | Retroceder | 5 | `MANUAL_BACK = 'o'` |
| **P** | Reservado | 6 | `MANUAL_RESERVED = 'p'` |
| **F** | Velocidad rápida | 7 | `MANUAL_FAST = 'f'` |

**Nota:** Los controles se envían como un byte (8 bits) cada 500ms donde cada bit representa una tecla.

---

## ⚙️ Personalizar Keybinds

### Archivo: `config.py`

```python
class KeybindConfig:
    # Cambiar tecla de salida (ejemplo: de TAB a ESC)
    KEY_EXIT = 27  # ESC key code
    
    # Cambiar tecla de voz (ejemplo: de 3 a SPACE)
    KEY_VOICE_RECORD = ' '  # Space bar
    
    # Cambiar controles manuales (ejemplo: WASD style)
    MANUAL_ROTATE_CCW = 'a'  # En lugar de 'j'
    MANUAL_ROTATE_CW = 'd'   # En lugar de 'l'
    MANUAL_LEFT = 'w'         # Izquierda, en lugar de 'i'
    MANUAL_RIGHT = 's'        # Derecha, en lugar de 'k'
    MANUAL_FORWARD = 'e'     # En lugar de 'u'
    MANUAL_BACK = 'q'        # En lugar de 'o'
    
    # Cambiar tecla de cancelar navegación
    KEY_CANCEL_NAV = 'x'  # En lugar de '5'
```

### Códigos de Teclas Comunes (OpenCV)
| Tecla | Código |
|-------|--------|
| TAB | 9 |
| Enter | 13 |
| ESC | 27 |
| Space | 32 |
| Backspace | 8 |
| Delete | 127 |
| A-Z | 97-122 (minúsculas) |
| 0-9 | 48-57 |

---

## 🔧 Ejemplos de Configuración

### Setup 1: Controles Gaming (WASD)
```python
class KeybindConfig:
    KEY_EXIT = 27  # ESC
    KEY_VOICE_RECORD = ' '  # Space
    KEY_CANCEL_NAV = 'x'  # En lugar de '5'
    KEY_FACE_RECOGNITION = ord('r')  # En lugar de ord('4')
    
    MANUAL_FORWARD = 'w'
    MANUAL_BACK = 's'
    MANUAL_ROTATE_CCW = 'a'
    MANUAL_ROTATE_CW = 'd'
    MANUAL_LEFT = 'e'
    MANUAL_RIGHT = 'q'
    MANUAL_FAST = 'shift'  # Requiere modificación adicional
```

### Setup 2: Controles de Flecha
```python
class KeybindConfig:
    KEY_EXIT = 9  # TAB
    KEY_VOICE_RECORD = 'r'  # R for Record
    KEY_CANCEL_NAV = 'c'  # C for Cancel
    
    MANUAL_FORWARD = 'up'     # Requiere código especial
    MANUAL_BACK = 'down'
    MANUAL_ROTATE_CCW = 'left'
    MANUAL_ROTATE_CW = 'right'
    MANUAL_LEFT = 'pageup'
    MANUAL_RIGHT = 'pagedown'
```

### Setup 3: Una Mano (Numpad)
```python
class KeybindConfig:
    KEY_EXIT = 27  # ESC
    KEY_VOICE_RECORD = '0'
    
    MANUAL_FORWARD = '8'
    MANUAL_BACK = '2'
    MANUAL_ROTATE_CCW = '4'
    MANUAL_ROTATE_CW = '6'
    MANUAL_LEFT = '9'
    MANUAL_RIGHT = '3'
    MANUAL_FAST = '5'
```

---

## 📋 Comandos de Consola

### Comandos de Texto
| Comando | Función |
|---------|---------|
| `7` | Activar/desactivar modo manual |
| `go to person 1` | Navegar a persona 1 |
| `follow person 2` | Seguir a persona 2 || `go to Juan` | Navegar a persona identificada como Juan |
| `follow Juan` | Seguir a persona identificada como Juan |
| `save person 1 as Juan` | Registrar rostro de persona 1 como "Juan" |
| `remove Juan` | Eliminar a Juan de la base de datos facial || `go to marker 5` | Navegar a marcador ArUco 5 |

### Comandos de Voz
Mantén presionada la tecla configurada (`KEY_VOICE_RECORD`, por defecto **3**) y di:
- "Ve a la persona uno"
- "Sigue a la persona dos"
- "Ve al marcador tres"

---

## 🚨 Notas Importantes

1. **Teclas Especiales**: Algunas teclas como flechas, shift, ctrl requieren manejo especial en OpenCV
2. **Conflictos**: Evita usar la misma tecla para múltiples funciones
3. **Sensibilidad**: El modo manual detecta teclas cada 10ms y envía comandos cada 500ms
4. **Prioridad**: En modo manual, la navegación automática se desactiva
5. **Seguridad**: Siempre ten una forma rápida de salir (KEY_EXIT) y cancelar (KEY_CANCEL_NAV)

---

## 🔍 Debugging Keybinds

Si un keybind no funciona:

1. **Verificar código de tecla:**
```python
# Añadir en display_thread() después de key = cv2.waitKey(delay)
print(f"Tecla presionada: {key}")
```

2. **Verificar importación:**
```python
from config import Config
print(f"EXIT key: {Config.Keybinds.KEY_EXIT}")
```

3. **Probar en modo manual:**
```python
import keyboard
print(keyboard.is_pressed('j'))  # Debe retornar True/False
```

---

## 📚 Referencias

- **OpenCV waitKey**: Retorna código ASCII o -1 si no hay tecla
- **keyboard module**: Detecta teclas del sistema operativo
- **config.py**: Archivo de configuración centralizado
- **SIGO1.py**: Implementación de keybinds (líneas 1665-1750)
