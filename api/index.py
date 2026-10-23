"""Semaforómetro Digital - Proyecto Tecnopatías (Feria de Arte y Ciencias)
Versión para Vercel: solo biblioteca estándar de Python.

Los contadores se guardan en Redis (Upstash, desde Vercel Marketplace) usando su API REST.
Si no hay Redis configurado (ej. probando en tu PC), usa un archivo local como respaldo.

Probar localmente:  python api/index.py   ->  http://localhost:5000
"""
import json, os, tempfile, threading
import urllib.request
from html import escape
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs

# ---------- PREGUNTAS (sin colores a la vista, para evitar sesgo) ----------
PREGUNTAS = [
    ("horas", "¿Cuántas horas creés que le dedicás a las pantallas?",
     ["Hasta 2 h", "Hasta 4 h", "Más de 4 h"]),
    ("estudio", "¿Trabajás o estudiás con dispositivos?", ["Sí", "No"]),
    ("pausas", "¿Realizás pausas de desintoxicación tecnológica?",
     ["Sí", "Frecuentemente", "Nunca"]),
    ("lentes", "¿Usás lentes o anteojos?", ["Sí", "No"]),
    ("sueno", "¿Has tenido episodios de alteración del sueño?",
     ["Sí", "A veces", "No"]),
]

# ---------- LÓGICA DEL SEMÁFORO (ajustable por el grupo) ----------
def evaluar(r):
    p, msgs = 0, []
    h = {"Hasta 2 h": 0, "Hasta 4 h": 1, "Más de 4 h": 2}[r["horas"]]
    p += h
    if r["estudio"] == "Sí":
        p += 1
        msgs.append("Tu tiempo de estudio/trabajo también cuenta como exposición a pantallas.")
    pausas = {"Sí": 0, "Frecuentemente": 1, "Nunca": 2}[r["pausas"]]
    if pausas == 2 and r["estudio"] == "No":
        # No estudia/trabaja con dispositivos: no hacer pausas no se penaliza
        pausas = 0
        msgs.append("Como no estudiás ni trabajás con dispositivos, no hacer pausas no te "
                    "perjudica tanto. Igual, si usás pantallas por ocio, un descanso "
                    "de vez en cuando siempre suma.")
    elif pausas == 2:
        msgs.append("Sin pausas, tus ojos no se relajan: probá la regla 20-20-20.")
    p += pausas
    if r["lentes"] == "No" and h >= 1 and pausas >= 1:
        p += 1
        msgs.append("Con tanto uso, conviene un control visual preventivo.")
    sueno = {"No": 0, "A veces": 1, "Sí": 2}[r["sueno"]]
    p += sueno
    if sueno:
        msgs.append("Las pantallas de noche inhiben la melatonina y alteran el sueño.")
    color = "verde" if p <= 2 else "amarillo" if p <= 5 else "rojo"
    return color, p, msgs

# ---------- ALMACENAMIENTO ----------
COLORES = ("verde", "amarillo", "rojo")
CLAVE = "semaforometro"

REDIS_URL = (os.environ.get("KV_REST_API_URL")
             or os.environ.get("UPSTASH_REDIS_REST_URL"))
REDIS_TOKEN = (os.environ.get("KV_REST_API_TOKEN")
               or os.environ.get("UPSTASH_REDIS_REST_TOKEN"))

# Respaldo local (en Vercel /tmp es temporal: solo sirve para pruebas)
ARCHIVO = os.path.join(tempfile.gettempdir(), "semaforometro_resultados.json")
lock = threading.Lock()

def _redis(*comando):
    req = urllib.request.Request(
        REDIS_URL,
        data=json.dumps(list(comando)).encode("utf-8"),
        headers={"Authorization": f"Bearer {REDIS_TOKEN}",
                 "Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.load(resp)["result"]

def leer():
    datos = {c: 0 for c in COLORES}
    if REDIS_URL and REDIS_TOKEN:
        try:
            plano = _redis("HGETALL", CLAVE) or []
            for k, v in zip(plano[::2], plano[1::2]):
                if k in datos:
                    datos[k] = int(v)
        except Exception:
            pass
        return datos
    if os.path.exists(ARCHIVO):
        try:
            with open(ARCHIVO, encoding="utf-8") as f:
                datos.update(json.load(f))
        except (OSError, ValueError):
            pass
    return datos

def sumar(color):
    if REDIS_URL and REDIS_TOKEN:
        try:
            _redis("HINCRBY", CLAVE, color, 1)  # atómico, sin pisarse entre usuarios
        except Exception:
            pass
        return
    with lock:
        d = leer()
        d[color] += 1
        with open(ARCHIVO, "w", encoding="utf-8") as f:
            json.dump(d, f)

# ---------- PÁGINAS (HTML) ----------
CSS = """
body{font-family:system-ui,sans-serif;max-width:520px;margin:0 auto;padding:16px;background:#f4f6f8;color:#222}
h1{text-align:center;font-size:1.5rem} .card{background:#fff;border-radius:12px;padding:14px;margin:12px 0;box-shadow:0 1px 4px #0002}
label{display:block;padding:10px;margin:6px 0;border:2px solid #ddd;border-radius:8px;cursor:pointer}
label:has(input:checked){border-color:#1565c0;background:#e3f2fd;font-weight:700}
button{display:block;width:100%;padding:14px;font-size:1.1rem;background:#1565c0;color:#fff;border:0;border-radius:10px}
.luz{width:140px;height:140px;border-radius:50%;margin:10px auto}
.verde{background:#2e7d32}.amarillo{background:#f9a825}.rojo{background:#c62828}
.barra{height:28px;border-radius:6px;color:#fff;padding:3px 8px;margin:6px 0;min-width:30px}
"""

def pagina(body):
    return ("<!doctype html><html lang='es'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Semaforómetro</title><style>" + CSS + "</style></head><body>"
            + body + "</body></html>")

def pag_form():
    h = ("<h1>👁️ Semaforómetro Digital</h1><p style='text-align:center'>"
         "Respondé con sinceridad. ¡Al final descubrís tu semáforo!</p>"
         "<form method='post' action='/'>")
    for i, (k, t, ops) in enumerate(PREGUNTAS, 1):
        h += f"<div class='card'><b>{i}. {escape(t)}</b>"
        for o in ops:
            h += (f"<label><input type='radio' name='{k}' value='{escape(o)}' required> "
                  f"{escape(o)}</label>")
        h += "</div>"
    return pagina(h + "<button>Ver mi semáforo</button></form>")

TITULOS = {"verde": "🟢 VERDE: ¡vas bien!", "amarillo": "🟡 AMARILLO: ¡atención!",
           "rojo": "🔴 ROJO: ¡alerta!"}

def pag_resultado(color, msgs):
    lis = "".join(f"<li>{escape(m)}</li>" for m in msgs) or \
          "<li>Tus hábitos digitales son equilibrados. ¡Seguí así!</li>"
    return pagina(f"<h1>Tu semáforo</h1><div class='luz {color}'></div>"
                  f"<h2 style='text-align:center'>{TITULOS[color]}</h2>"
                  f"<div class='card'><b>Por qué:</b><ul>{lis}</ul></div>"
                  f"<div class='card'>📌 Acercate al stand: colocá la luz <b>{color.upper()}</b> "
                  "en tu semáforo y retirá tu tríptico.</div>")

PAG_RESULTADOS = pagina("""<h1>🚦 El juego del semáforo</h1><div id="r" class="card"></div>
<script>
async function act(){const d=await (await fetch('/api/resultados')).json();
const n=d.verde+d.amarillo+d.rojo, t=Math.max(1,n);
document.getElementById('r').innerHTML=['verde','amarillo','rojo'].map(c=>
`<div class="barra ${c}" style="width:${Math.max(8,d[c]/t*100)}%">${d[c]}</div>`).join('')+
`<p>Total de participantes: <b>${n}</b></p>`}
act();setInterval(act,3000);</script>""")

# ---------- SERVIDOR (Vercel busca la clase `handler`) ----------
class handler(BaseHTTPRequestHandler):
    def _enviar(self, contenido, tipo="text/html; charset=utf-8", codigo=200):
        datos = contenido.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(datos)

    def _ruta(self):
        ruta = self.path.split("?")[0].rstrip("/") or "/"
        if ruta in ("/api/index", "/api/index.py"):
            ruta = "/"
        return ruta

    def do_GET(self):
        ruta = self._ruta()
        if ruta == "/":
            self._enviar(pag_form())
        elif ruta == "/resultados":
            self._enviar(PAG_RESULTADOS)
        elif ruta == "/api/resultados":
            self._enviar(json.dumps(leer()), "application/json")
        else:
            self._enviar("No encontrado", "text/plain; charset=utf-8", 404)

    def do_POST(self):
        largo = int(self.headers.get("Content-Length", 0))
        campos = parse_qs(self.rfile.read(largo).decode("utf-8"))
        try:
            resp = {k: campos[k][0] for k, _, _ in PREGUNTAS}
            color, puntos, msgs = evaluar(resp)
        except (KeyError, ValueError):
            self.send_response(303)          # datos incompletos: volver a la encuesta
            self.send_header("Location", "/")
            self.end_headers()
            return
        sumar(color)
        self._enviar(pag_resultado(color, msgs))

    def log_message(self, *args):  # silencia el log de cada pedido
        pass

# ---------- EJECUCIÓN LOCAL ----------
if __name__ == "__main__":
    import socket
    from http.server import ThreadingHTTPServer
    PUERTO = 5000
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1)); ip = s.getsockname()[0]
    except OSError:
        ip = "127.0.0.1"
    finally:
        s.close()
    print(f"Encuesta:   http://{ip}:{PUERTO}")
    print(f"Resultados: http://{ip}:{PUERTO}/resultados")
    print("Ctrl+C para detener.")
    ThreadingHTTPServer(("0.0.0.0", PUERTO), handler).serve_forever()
