#!/usr/bin/env python3
"""
Script de diagnóstico para probar conexión Serial/WiFi
Úsalo para verificar que el dispositivo responde antes de ejecutar SIGO
"""
import socket
import serial
import time

# Configuración (ajusta según tu config.py)
SERIAL_PORT = 'COM8'
SERIAL_BAUD = 9600
WIFI_IP = '192.168.165.76'
WIFI_PORT = 5555

def test_serial():
    """Prueba conexión serial"""
    print("\n🔌 Probando conexión SERIAL...")
    print(f"   Puerto: {SERIAL_PORT} @ {SERIAL_BAUD} baud")
    
    try:
        ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=2)
        print("   ✅ Puerto abierto correctamente")
        
        # Intentar enviar un byte de prueba
        ser.write(bytes([0]))
        ser.flush()
        print("   ✅ Comando de prueba enviado (byte 0)")
        
        ser.close()
        print("   ✅ SERIAL funcionando correctamente\n")
        return True
        
    except serial.SerialException as e:
        print(f"   ❌ Error: {e}")
        print(f"   💡 Verifica:")
        print(f"      - ¿Está conectado el cable USB?")
        print(f"      - ¿Es el puerto correcto? (Device Manager)")
        print(f"      - ¿Está en uso por otro programa?\n")
        return False
    except Exception as e:
        print(f"   ❌ Error inesperado: {e}\n")
        return False

def test_wifi():
    """Prueba conexión WiFi"""
    print("📡 Probando conexión WIFI...")
    print(f"   IP: {WIFI_IP}:{WIFI_PORT}")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        
        print("   🔄 Intentando conectar...")
        sock.connect((WIFI_IP, WIFI_PORT))
        print("   ✅ Conexión establecida")
        
        # Intentar enviar un byte de prueba
        sock.sendall(bytes([0]))
        print("   ✅ Comando de prueba enviado (byte 0)")
        
        sock.close()
        print("   ✅ WIFI funcionando correctamente\n")
        return True
        
    except socket.timeout:
        print(f"   ❌ Timeout: El ESP no responde")
        print(f"   💡 Verifica:")
        print(f"      - ¿Está el ESP encendido?")
        print(f"      - ¿Está conectado a la misma red WiFi?")
        print(f"      - ¿Es la IP correcta? Usa 'ipconfig' para verificar")
        print(f"      - ¿El código del ESP está corriendo?\n")
        return False
    except ConnectionRefusedError:
        print(f"   ❌ Conexión rechazada")
        print(f"   💡 El puerto {WIFI_PORT} no está abierto en el ESP\n")
        return False
    except socket.gaierror:
        print(f"   ❌ IP inválida: {WIFI_IP}")
        print(f"   💡 Verifica la IP del ESP en tu router\n")
        return False
    except Exception as e:
        print(f"   ❌ Error inesperado: {e}\n")
        return False

def main():
    print("="*60)
    print("🔍 DIAGNÓSTICO DE CONEXIÓN - SIGO")
    print("="*60)
    
    # Probar ambos métodos
    serial_ok = test_serial()
    wifi_ok = test_wifi()
    
    # Resumen
    print("="*60)
    print("📊 RESUMEN:")
    print(f"   Serial (COM8): {'✅ OK' if serial_ok else '❌ FALLA'}")
    print(f"   WiFi (ESP):    {'✅ OK' if wifi_ok else '❌ FALLA'}")
    print("="*60)
    
    if serial_ok or wifi_ok:
        print("\n✅ Al menos un método de control funciona")
        print("   Puedes ejecutar SIGO con seguridad\n")
    else:
        print("\n❌ Ningún método de control funciona")
        print("   Revisa las conexiones antes de ejecutar SIGO\n")

if __name__ == "__main__":
    main()
