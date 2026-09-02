import cv2
import numpy as np
import time
import math
import sqlite3
import sys
from collections import deque

# ID del alumno y ejercicio pasados como argumento (por defecto 1 si se prueba solo)
alumno_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
ejercicio = sys.argv[2] if len(sys.argv) > 2 else "Transferencia de Clavijas (Peg Transfer)"

# Iniciar cámara con optimización de latencia
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    cap = cv2.VideoCapture(1)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

# Calibración precisa original
VERDE_BAJO = np.array([35, 80, 80])
VERDE_ALTO = np.array([85, 255, 255])
AZUL_BAJO = np.array([95, 100, 100])
AZUL_ALTO = np.array([135, 255, 255])

puntos_izq = deque(maxlen=32)
puntos_der = deque(maxlen=32)
dist_izq = 0.0
dist_der = 0.0
ult_izq = None
ult_der = None

t_inicio = time.time()
tiempo_sobre_boton = 0
BTN_X1, BTN_Y1, BTN_X2, BTN_Y2 = 470, 10, 630, 60

print(f"Tracking iniciado para Alumno ID: {alumno_id}. Presiona 'q' o toca FINALIZAR en pantalla.")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # Mano Izquierda (Verde)
    mask_v = cv2.inRange(hsv, VERDE_BAJO, VERDE_ALTO)
    mask_v = cv2.erode(mask_v, None, iterations=1)
    mask_v = cv2.dilate(mask_v, None, iterations=1)
    cnts_v, _ = cv2.findContours(mask_v, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    c_izq = None
    if len(cnts_v) > 0:
        c = max(cnts_v, key=cv2.contourArea)
        if cv2.contourArea(c) > 70:
            ((x, y), _) = cv2.minEnclosingCircle(c)
            c_izq = (int(x), int(y))
            cv2.circle(frame, c_izq, 6, (0, 255, 0), -1)
            cv2.putText(frame, "Izq", (c_izq[0] + 8, c_izq[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
            if ult_izq is not None:
                dist_izq += math.hypot(c_izq[0] - ult_izq[0], c_izq[1] - ult_izq[1])
            ult_izq = c_izq
    puntos_izq.appendleft(c_izq)

    # Mano Derecha (Azul)
    mask_a = cv2.inRange(hsv, AZUL_BAJO, AZUL_ALTO)
    mask_a = cv2.erode(mask_a, None, iterations=1)
    mask_a = cv2.dilate(mask_a, None, iterations=1)
    cnts_a, _ = cv2.findContours(mask_a, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    c_der = None
    if len(cnts_a) > 0:
        c = max(cnts_a, key=cv2.contourArea)
        if cv2.contourArea(c) > 70:
            ((x, y), _) = cv2.minEnclosingCircle(c)
            c_der = (int(x), int(y))
            cv2.circle(frame, c_der, 6, (255, 0, 0), -1)
            cv2.putText(frame, "Der", (c_der[0] + 8, c_der[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)
            if ult_der is not None:
                dist_der += math.hypot(c_der[0] - ult_der[0], c_der[1] - ult_der[1])
            ult_der = c_der
    puntos_der.appendleft(c_der)

    # Estelas
    for i in range(1, len(puntos_izq)):
        if puntos_izq[i - 1] and puntos_izq[i]:
            cv2.line(frame, puntos_izq[i - 1], puntos_izq[i], (0, 255, 0), 2)
    for i in range(1, len(puntos_der)):
        if puntos_der[i - 1] and puntos_der[i]:
            cv2.line(frame, puntos_der[i - 1], puntos_der[i], (255, 0, 0), 2)

    t_actual = round(time.time() - t_inicio, 1)

    # Overlay Métricas
    cv2.rectangle(frame, (10, 10), (250, 95), (0, 0, 0), -1)
    cv2.putText(frame, f"Tiempo: {t_actual} s", (20, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    cv2.putText(frame, f"Dist. Izq: {int(dist_izq)} px", (20, 57), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    cv2.putText(frame, f"Dist. Der: {int(dist_der)} px", (20, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 100, 100), 1)

    # Botón en pantalla
    pinza_en_boton = False
    for pt in [c_izq, c_der]:
        if pt and (BTN_X1 <= pt[0] <= BTN_X2) and (BTN_Y1 <= pt[1] <= BTN_Y2):
            pinza_en_boton = True
            break

    if pinza_en_boton:
        tiempo_sobre_boton += 1
        color_btn = (0, 255, 0)
    else:
        tiempo_sobre_boton = 0
        color_btn = (0, 0, 255)

    cv2.rectangle(frame, (BTN_X1, BTN_Y1), (BTN_X2, BTN_Y2), color_btn, -1)
    cv2.rectangle(frame, (BTN_X1, BTN_Y1), (BTN_X2, BTN_Y2), (255, 255, 255), 2)
    cv2.putText(frame, "FINALIZAR", (BTN_X1 + 18, BTN_Y1 + 32), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

    cv2.imshow("Box Trainer - Presiona 'q' o toca FINALIZAR", frame)

    if (cv2.waitKey(1) & 0xFF == ord('q')) or tiempo_sobre_boton >= 15:
        break

cap.release()
cv2.destroyAllWindows()

# Guardado directo en SQLite
t_fin = max(round(time.time() - t_inicio, 1), 1.0)
d_tot = round(dist_izq + dist_der, 1)

if dist_der > 0 and dist_izq > 0:
    ratio = round(dist_izq / dist_der, 2)
elif dist_der > 0 and dist_izq == 0:
    ratio = 0.0
elif dist_izq > 0 and dist_der == 0:
    ratio = 9.9
else:
    ratio = 1.0

goals_auto = 22 if (t_fin <= 100 and d_tot < 4000) else (18 if t_fin <= 140 else 14)

conn = sqlite3.connect("simulacion_laparo.db")
c = conn.cursor()
c.execute('''
INSERT INTO evaluaciones (
    alumno_id, ejercicio, tiempo_segundos, errores,
    distancia_izq, distancia_der, distancia_total, ratio_bimanual,
    puntaje_goals, comentarios
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', (alumno_id, ejercicio, t_fin, 0, round(dist_izq, 1), round(dist_der, 1), d_tot, ratio, goals_auto, f"Tracking cinemático. Izq: {int(dist_izq)}px | Der: {int(dist_der)}px | Ratio: {ratio}"))
conn.commit()
conn.close()
print("Datos guardados exitosamente en la base de datos.")