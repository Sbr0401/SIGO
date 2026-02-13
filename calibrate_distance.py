"""
Script de calibración de distancia para SIGO
Usa este script para calibrar FOCAL_LENGTH_PIX y DISTANCE_CORRECTION
"""
import cv2
import numpy as np
from ultralytics import YOLO
import math

# Constantes iniciales
CONF_MIN_KPT = 0.5
TORSO_AVG_WIDTH_M = 0.40  # 40cm ancho de hombros promedio
TORSO_AVG_HEIGHT_M = 0.50  # 50cm altura de torso promedio

# Valores a calibrar
FOCAL_PIX = 400.0  # Valor inicial a ajustar
DISTANCE_CORRECTION = 1.0  # Factor de corrección

def distance_between_kpts(p1, p2):
    """Calcula distancia euclidiana entre dos keypoints"""
    return math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)

def estimate_distance(kpts, bbox, focal_pix):
    """Estima distancia usando múltiples métodos"""
    L_SH, R_SH = 5, 6
    L_HP, R_HP = 11, 12
    L_ELB = 7
    
    results = {}
    
    # Método 1: Ancho de hombros
    if all(kpts[i][2] > CONF_MIN_KPT for i in [L_SH, R_SH]):
        shoulder_width_pix = distance_between_kpts(
            (kpts[L_SH][0], kpts[L_SH][1]),
            (kpts[R_SH][0], kpts[R_SH][1])
        )
        if shoulder_width_pix > 10:
            results['shoulders'] = {
                'pixels': shoulder_width_pix,
                'distance': (TORSO_AVG_WIDTH_M * focal_pix) / shoulder_width_pix
            }
    
    # Método 2: Altura del torso
    if all(kpts[i][2] > CONF_MIN_KPT for i in [L_SH, R_SH, L_HP, R_HP]):
        y_shoulders = min(kpts[L_SH][1], kpts[R_SH][1])
        y_hips = max(kpts[L_HP][1], kpts[R_HP][1])
        torso_height_pix = y_hips - y_shoulders
        if torso_height_pix > 10:
            results['torso_height'] = {
                'pixels': torso_height_pix,
                'distance': (TORSO_AVG_HEIGHT_M * focal_pix) / torso_height_pix
            }
    
    # Método 3: Longitud de brazo
    if all(kpts[i][2] > CONF_MIN_KPT for i in [L_SH, L_ELB]):
        arm_length_pix = distance_between_kpts(
            (kpts[L_SH][0], kpts[L_SH][1]),
            (kpts[L_ELB][0], kpts[L_ELB][1])
        )
        if arm_length_pix > 5:
            results['arm'] = {
                'pixels': arm_length_pix,
                'distance': (0.30 * focal_pix) / arm_length_pix
            }
    
    return results

def main():
    print("="*60)
    print("CALIBRADOR DE DISTANCIA PARA SIGO")
    print("="*60)
    print("\nInstrucciones:")
    print("1. Párate a una DISTANCIA CONOCIDA de la cámara (ej: 1.0m, 1.5m, 2.0m)")
    print("2. Presiona ESPACIO para capturar medición")
    print("3. Ingresa la distancia real en metros")
    print("4. Repite con 3-5 distancias diferentes")
    print("5. Presiona ESC para calcular calibración\n")
    print(f"Focal length inicial: {FOCAL_PIX} píxeles")
    print(f"Factor de corrección inicial: {DISTANCE_CORRECTION}")
    print("="*60 + "\n")
    
    model = YOLO('yolov8s-pose.pt')
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: No se puede abrir la cámara")
        return
    
    measurements = []
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Detectar pose
        results = model(frame, conf=0.5, verbose=False)
        res = results[0]
        
        display = frame.copy()
        
        if res.boxes is not None and res.keypoints is not None:
            boxes = res.boxes.xyxy.cpu().numpy()
            kpts_xy = res.keypoints.xy.cpu().numpy()
            kpts_conf = res.keypoints.conf.cpu().numpy() if res.keypoints.conf is not None else np.ones(kpts_xy.shape[:2])
            
            for i in range(boxes.shape[0]):
                box = boxes[i]
                xy = kpts_xy[i]
                confs = kpts_conf[i]
                kpts = np.concatenate([xy, confs.reshape(-1, 1)], axis=1)
                
                # Calcular distancias
                distances = estimate_distance(kpts, box, FOCAL_PIX)
                
                # Dibujar bbox
                x1, y1, x2, y2 = box.astype(int)
                cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)
                
                # Mostrar distancias calculadas
                y_text = y1 - 10
                for method, data in distances.items():
                    dist = data['distance'] * DISTANCE_CORRECTION
                    pix = data['pixels']
                    text = f"{method}: {dist:.2f}m ({pix:.0f}px)"
                    cv2.putText(display, text, (x1, y_text), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    y_text -= 20
                
                # Instrucciones
                cv2.putText(display, "ESPACIO: Capturar | ESC: Calcular", 
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                cv2.putText(display, f"Mediciones: {len(measurements)}", 
                           (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        cv2.imshow("Calibración de Distancia", display)
        
        key = cv2.waitKey(1) & 0xFF
        
        if key == 27:  # ESC
            break
        elif key == 32:  # SPACE
            if res.boxes is not None and res.keypoints is not None and boxes.shape[0] > 0:
                # Usar primera persona detectada
                box = boxes[0]
                xy = kpts_xy[0]
                confs = kpts_conf[0]
                kpts = np.concatenate([xy, confs.reshape(-1, 1)], axis=1)
                
                distances = estimate_distance(kpts, box, FOCAL_PIX)
                
                if distances:
                    print("\n" + "="*60)
                    print("MEDICIÓN CAPTURADA")
                    print("="*60)
                    for method, data in distances.items():
                        dist = data['distance'] * DISTANCE_CORRECTION
                        print(f"{method:15s}: {dist:.2f}m ({data['pixels']:.0f} píxeles)")
                    
                    real_distance = input("\nIngresa la distancia REAL en metros: ")
                    try:
                        real_distance = float(real_distance)
                        measurements.append({
                            'real': real_distance,
                            'calculated': distances
                        })
                        print(f"✓ Medición {len(measurements)} guardada")
                    except ValueError:
                        print("✗ Entrada inválida, medición descartada")
            else:
                print("✗ No se detectó ninguna persona")
    
    cap.release()
    cv2.destroyAllWindows()
    
    # Calcular calibración
    if len(measurements) < 2:
        print("\n✗ Se necesitan al menos 2 mediciones para calibrar")
        return
    
    print("\n" + "="*60)
    print("RESULTADOS DE CALIBRACIÓN")
    print("="*60)
    
    # Analizar cada método
    methods_data = {}
    
    for measurement in measurements:
        real = measurement['real']
        for method, data in measurement['calculated'].items():
            calculated = data['distance'] * DISTANCE_CORRECTION
            error = calculated - real
            error_pct = (error / real) * 100
            
            if method not in methods_data:
                methods_data[method] = []
            
            methods_data[method].append({
                'real': real,
                'calculated': calculated,
                'error': error,
                'error_pct': error_pct
            })
    
    # Calcular factores de corrección para cada método
    print("\nAnálisis por método:\n")
    
    best_method = None
    best_error = float('inf')
    
    for method, data in methods_data.items():
        errors = [abs(d['error_pct']) for d in data]
        avg_error = np.mean(errors)
        std_error = np.std(errors)
        
        # Calcular factor de corrección óptimo
        ratios = [d['real'] / d['calculated'] * DISTANCE_CORRECTION for d in data]
        optimal_correction = np.mean(ratios)
        
        print(f"{method.upper()}:")
        print(f"  Error promedio: {avg_error:.1f}%")
        print(f"  Desviación estándar: {std_error:.1f}%")
        print(f"  Factor de corrección óptimo: {optimal_correction:.3f}")
        print()
        
        if avg_error < best_error:
            best_error = avg_error
            best_method = method
    
    print("="*60)
    print(f"MEJOR MÉTODO: {best_method.upper()}")
    print(f"Error promedio: {best_error:.1f}%")
    print("="*60)
    
    # Calcular focal length óptimo
    if 'shoulders' in methods_data:
        # Usar método de hombros para calibrar focal length
        focal_corrections = []
        for measurement in measurements:
            if 'shoulders' in measurement['calculated']:
                real = measurement['real']
                shoulder_pix = measurement['calculated']['shoulders']['pixels']
                # focal = (real_distance * pixels) / real_width
                focal_optimal = (real * shoulder_pix) / TORSO_AVG_WIDTH_M
                focal_corrections.append(focal_optimal)
        
        if focal_corrections:
            optimal_focal = np.mean(focal_corrections)
            print(f"\nFOCAL LENGTH ÓPTIMO: {optimal_focal:.1f} píxeles")
            print(f"  (actual: {FOCAL_PIX})")
    
    print("\n" + "="*60)
    print("ACTUALIZA TU config.py CON ESTOS VALORES:")
    print("="*60)
    
    if 'shoulders' in methods_data:
        ratios = [d['real'] / d['calculated'] * DISTANCE_CORRECTION for d in methods_data['shoulders']]
        optimal_correction = np.mean(ratios)
        print(f"\nDISTANCE_CORRECTION = {optimal_correction:.3f}")
    
    if focal_corrections:
        print(f"FOCAL_LENGTH_PIX = {optimal_focal:.1f}")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    main()
