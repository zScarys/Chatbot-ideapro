# REPARTO PARA LA EXPOSICIÓN: cada marca ">>> EXPONE" indica quién explica desde ese punto
# hasta la siguiente marca. Nombre y número de parte coinciden con la guía en PDF.

# >>> EXPONE: JOSÉ LUIS (parte 1) · Importaciones
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv
from google import genai
from google.genai import types
import os
import re
import sqlite3
import threading
import time
import uuid

# ==========================================
# CONFIGURACIÓN
# ==========================================

# >>> EXPONE: STEVEN (parte 1) · Configuración inicial de Flask y base de datos
# Lee el archivo .env para tener las claves disponibles
load_dotenv()
app = Flask(__name__)

# La base de datos vive en la carpeta data/, junto a este archivo.
CARPETA_BASE = os.path.dirname(os.path.abspath(__file__))
RUTA_DB = os.path.join(CARPETA_BASE, "data", "ideapro.db")
# Crea la carpeta data/ si todavía no existe
os.makedirs(os.path.dirname(RUTA_DB), exist_ok=True)
# Necesaria para recordar el diagnóstico de cada visitante (cookie de sesión).
app.secret_key = os.getenv("FLASK_SECRET_KEY", "ideapro-clave-de-desarrollo")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Si Google vuelve a retirar el modelo, solo cambia este valor
# (o agrega GEMINI_MODEL=nuevo-modelo en tu archivo .env).
MODELO_IA = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

# >>> EXPONE: CASAS (parte 1) · Lista de modelos de IA y modelos en pausa
# Lista de modelos en orden de prioridad. En el .env puedes poner varios separados
# por comas:  GEMINI_MODELS=modelo-1,modelo-2,modelo-3
# La cuota gratuita se cuenta por modelo, así que más modelos = más margen.
_lista = os.getenv("GEMINI_MODELS", "")
if _lista.strip():
    MODELOS = [m.strip() for m in _lista.split(",") if m.strip()]
else:
    MODELOS = [m for m in [MODELO_IA, os.getenv("GEMINI_MODEL_RESPALDO")] if m]

# Modelos que se saltan por un rato porque agotaron su cuota: {modelo: hora de reintento}
EN_PAUSA = {}
PAUSA_SATURACION = 45  # segundos que se salta un modelo saturado o que no respondió

# >>> EXPONE: RICARDO (parte 1) · Instrucciones del asistente y validación de claves
INSTRUCCIONES = (
    "Eres SmartPath, el asistente virtual de IDEAPRO S.A.S. "
    "Tu objetivo es ayudar a empresas a conocer su nivel de preparación "
    "para participar en el mercado público. Responde de manera clara y "
    "profesional, en español, y haz una sola pregunta a la vez. "
    "No uses emojis ni emoticones. "
    "Lee todo el historial de la conversación: nunca repitas una pregunta que el "
    "usuario ya respondió y no vuelvas a saludar. Toma cada respuesta como un dato "
    "y avanza con la información que falte (nombre y sector de la empresa, experiencia "
    "con el Estado, capacidad operativa, situación financiera y preparación comercial). "
    "Si ya tienes esos datos, resume lo que sabes y sugiere usar el diagnóstico de la página."
)

def clave_valida(clave):
    return bool(clave) and not clave.startswith("TU_CLAVE")


# >>> EXPONE: STEVEN (parte 2) · Eliminación de emojis con expresión regular
# Rangos Unicode donde están los emojis
EMOJIS = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]")


def quitar_emojis(texto):
    """Elimina emojis de la respuesta de la IA, aunque el modelo los use."""
    return re.sub(r"[ \t]{2,}", " ", EMOJIS.sub("", texto)).strip()


# >>> EXPONE: NICOLÁS (parte 1) · Configuración de Groq
# ------------------------------------------
# Groq -> clave en https://console.groq.com/keys
# API compatible con OpenAI. Sirve de respaldo cuando Gemini falla o está saturado.
# ------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")  # empieza con "gsk_"
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
_gq = os.getenv("GROQ_MODELS") or os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b"
GROQ_MODELOS = [m.strip() for m in _gq.split(",") if m.strip()]

# >>> EXPONE: STEVEN (parte 3) · Creación de los clientes de Gemini y Groq
gemini_client = None
if clave_valida(GEMINI_API_KEY):
    try:
        gemini_client = genai.Client(
            api_key=GEMINI_API_KEY,
            http_options=types.HttpOptions(timeout=15000),  # 15 segundos por modelo
        )
    except Exception as e:
        print("Error configurando Gemini:", e)

groq_client = None
if clave_valida(GROQ_API_KEY):
    try:
        from openai import OpenAI
        groq_client = OpenAI(
            api_key=GROQ_API_KEY,
            base_url=GROQ_BASE_URL,
            timeout=15,  # 15 segundos por modelo
            max_retries=0,
        )
    except Exception as e:
        print("Error configurando Groq:", e)

# >>> EXPONE: DIEGO (parte 1) · Lista de motores de IA
# Motores en orden de prioridad: (nombre, cliente, modelos)
MOTORES = []
# Gemini va primero; Groq queda como respaldo
if gemini_client:
    MOTORES.append(("gemini", gemini_client, MODELOS))
if groq_client:
    MOTORES.append(("groq", groq_client, GROQ_MODELOS))

print("Motores de IA:", [(n, m) for n, _, m in MOTORES] or "ninguno (modo DEMO)")

# >>> EXPONE: CASAS (parte 2) · Creación de la base de datos SQLite
# ==========================================
# BASE DE DATOS
# ==========================================
def crear_base_datos():
    conexion = sqlite3.connect(RUTA_DB)
    cursor = conexion.cursor()
    # IF NOT EXISTS: crea la tabla solo si todavía no existe
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS diagnosticos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT,
            sector TEXT,
            experiencia INTEGER,
            capacidad INTEGER,
            finanzas INTEGER,
            comercial INTEGER,
            conocimiento INTEGER,
            promedio REAL,
            nivel TEXT
        )
    """)
    conexion.commit()
    conexion.close()

crear_base_datos()

# ==========================================
# RESPUESTAS DEL MODO DEMO (RESPALDO FLEXIBLE)
# ==========================================

# >>> EXPONE: JUANJOAR (parte 1) · Respuestas del modo DEMO
DEMO_ETAPAS = {}  # sid -> en qué paso de la conversación DEMO va cada visitante


def respuesta_demo(mensaje, sid=None):
    """Modo DEMO con memoria de paso: avanza en orden y nunca regresa a una pregunta anterior."""
    etapa = DEMO_ETAPAS.get(sid, 0)
    texto = mensaje.lower()

    if etapa == 0:
        # any(): True si el mensaje contiene alguna de estas palabras
        if any(palabra in texto for palabra in ["hola", "buenas", "saludos"]):
            DEMO_ETAPAS[sid] = 1
            return "¡Hola! Soy SmartPath, el asistente virtual de IDEAPRO. Estoy aquí para ayudarte a conocer qué tan preparada está tu empresa para participar en el mercado público. Para comenzar, ¿a qué se dedica tu empresa o qué productos/servicios ofrece?"
        etapa = 1  # si no saluda, el mensaje se toma como la actividad de la empresa

    if etapa == 1:
        DEMO_ETAPAS[sid] = 2
        return "Excelente actividad. Para avanzar con el perfil, cuéntame: ¿Has trabajado o vendido anteriormente con entidades del Estado?"

    if etapa == 2:
        DEMO_ETAPAS[sid] = 3
        return "Entendido. Esa experiencia es clave. ¿Cómo calificarías del 0 al 100 el conocimiento actual de tu empresa sobre contratación pública?"

    if etapa == 3:
        DEMO_ETAPAS[sid] = 4
        return "Gracias por la información. Con estos datos preliminares podemos ver que hay potencial. Te sugiero utilizar el módulo de diagnóstico interactivo de arriba para obtener una evaluación completa y detallada."

    return "Ya tengo los datos básicos de tu perfil. Para una evaluación completa usa el diagnóstico de arriba; por ahora solo puedo dar respuestas básicas (modo DEMO)."

# >>> EXPONE: DIEGO (parte 2) · Memoria del servidor y candados
# ==========================================
# CHAT
# ==========================================
# Historial de conversación por visitante (se guarda en memoria del servidor;
# se pierde si reinicias la app, lo cual es normal en un prototipo).
HISTORIALES = {}    # sid -> mensajes de la conversación
DIAGNOSTICOS = {}   # sid -> último diagnóstico de ese visitante
CANDADOS = {}       # sid -> candado para atender un mensaje a la vez por visitante
MAX_TURNOS = 10     # cuántos intercambios recuerda la IA
MAX_VISITANTES = 500  # tope para que la memoria del servidor no crezca sin límite


def limitar_memoria():
    for d in (HISTORIALES, DIAGNOSTICOS, CANDADOS, DEMO_ETAPAS):
        while len(d) > MAX_VISITANTES:
            # Borra el visitante más antiguo (el primero que entró)
            d.pop(next(iter(d)))


def candado_de(sid):
    return CANDADOS.setdefault(sid, threading.Lock())


# >>> EXPONE: JUANJOAR (parte 2) · Identificación del visitante (sid)
def obtener_sid(datos):
    """Identifica al visitante. Usa el 'sid' que envía la página en cada petición: así
    funciona aunque el navegador no guarde cookies (por ejemplo, HTML abierto como file://).
    Si no llega, usa la cookie de sesión como respaldo."""
    sid = str(datos.get("sid") or "")
    # Solo acepta ids de 8 a 64 caracteres (letras, números, _ y -)
    if re.fullmatch(r"[A-Za-z0-9_-]{8,64}", sid):
        return sid
    if "sid" not in session:
        session["sid"] = uuid.uuid4().hex
    return session["sid"]


# >>> EXPONE: JOSÉ LUIS (parte 2) · Construcción de las instrucciones con el diagnóstico
def construir_instrucciones(sid):
    """Instrucciones base + el último diagnóstico del visitante (si ya lo hizo)."""
    texto = INSTRUCCIONES
    d = DIAGNOSTICOS.get(sid)
    if d:
        puntajes = "\n".join(f"  - {area}: {valor}/100" for area, valor in d["puntajes"].items())
        necesidades = ", ".join(d["necesidades"]) or "Ninguna"
        recomendaciones = "\n".join(f"  - {r}" for r in d["recomendaciones"])
        texto += (
            "\n\nEl usuario ya completó el diagnóstico interactivo de la página. "
            "Estos son sus resultados:\n"
            f"- Empresa: {d['empresa']}\n"
            f"- Sector: {d['sector']}\n"
            f"- Promedio: {d['promedio']}/100\n"
            f"- Nivel: {d['nivel']}\n"
            f"- Descripción: {d['descripcion']}\n"
            f"- Puntajes por área:\n{puntajes}\n"
            f"- Áreas a fortalecer: {necesidades}\n"
            f"- Recomendaciones:\n{recomendaciones}\n\n"
            "Cuando el usuario pida explicar, reorganizar, resumir o ajustar su "
            "diagnóstico, trabaja con estos datos reales. No inventes puntajes ni "
            "cambies los números; solo redacta, ordena o amplía la información."
        )
    return texto


# >>> EXPONE: JUANJOAR (parte 3) · generar_con_modelo: rama de Groq
def generar_con_modelo(motor, cliente, modelo, mensajes, instrucciones):
    """Hace UNA llamada al motor indicado y devuelve el texto de la respuesta.
    `mensajes` es una lista de {"role": "user"|"assistant", "content": "..."}."""
    if motor == "groq":
        respuesta = cliente.chat.completions.create(
            model=modelo,
            messages=[{"role": "system", "content": instrucciones}] + mensajes,
            temperature=0.5,
            max_tokens=1024,
        )
        return quitar_emojis((respuesta.choices[0].message.content or "").strip())

    # >>> EXPONE: NICOLÁS (parte 2) · generar_con_modelo: rama de Gemini
    # Gemini
    contenido = [
        types.Content(
            # Gemini llama "model" al asistente
            role="user" if m["role"] == "user" else "model",
            parts=[types.Part(text=m["content"])],
        )
        for m in mensajes
    ]
    respuesta = cliente.models.generate_content(
        model=modelo,
        contents=contenido,
        config=types.GenerateContentConfig(system_instruction=instrucciones),
    )
    return quitar_emojis((respuesta.text or "").strip())


# >>> EXPONE: MONSALVE (parte 1) · llamar_ia: preparación y recorrido de motores
def llamar_ia(mensajes, instrucciones):
    """Recorre los motores (Gemini, luego Groq) y sus modelos en orden, una sola vez
    cada uno. Si un modelo agotó su cuota o está saturado, se salta durante un rato."""
    ultimo_error = None
    ahora = time.time()
    hubo_candidatos = False

    for motor, cliente, modelos in MOTORES:
        for modelo in modelos:
            clave = f"{motor}:{modelo}"
            # Si el modelo está en pausa, se salta
            if EN_PAUSA.get(clave, 0) > ahora:
                continue
            hubo_candidatos = True
            # >>> EXPONE: DIEGO (parte 3) · llamar_ia: llamada al modelo y captura del error
            try:
                texto = generar_con_modelo(motor, cliente, modelo, mensajes, instrucciones)
                if texto:
                    return texto
                print(f"{clave} respondió vacío, probando el siguiente...")
            except Exception as error:
                ultimo_error = error
                detalle = str(error)

                # >>> EXPONE: RICARDO (parte 2) · llamar_ia: error 429 (cuota agotada)
                # 429 = cuota agotada (demasiadas peticiones)
                if "429" in detalle or "RESOURCE_EXHAUSTED" in detalle:
                    diaria = "PerDay" in detalle or "per day" in detalle
                    m = re.search(r"retryDelay'?:\s*'(\d+)s'", detalle)
                    espera = int(m.group(1)) + 1 if m else (21600 if diaria else 70)
                    EN_PAUSA[clave] = time.time() + espera
                    motivo = "cuota diaria agotada" if diaria else "límite por minuto"
                # >>> EXPONE: NICOLÁS (parte 3) · llamar_ia: otros errores y error final
                # 503 = servicio saturado
                elif "503" in detalle or "UNAVAILABLE" in detalle:
                    motivo = "servicio saturado"
                    EN_PAUSA[clave] = time.time() + PAUSA_SATURACION
                elif "504" in detalle or "DEADLINE" in detalle or "Timeout" in type(error).__name__:
                    motivo = "tiempo agotado"
                    EN_PAUSA[clave] = time.time() + PAUSA_SATURACION
                else:
                    motivo = type(error).__name__
                print(f"{clave} falló ({motivo}), probando el siguiente...")

    if not hubo_candidatos:
        raise RuntimeError("Todos los modelos están en pausa temporal (cuota o saturación)")
    raise ultimo_error or RuntimeError("La IA devolvió una respuesta vacía")


# >>> EXPONE: STEVEN (parte 4) · Ruta /chat: entrada y candado
@app.route("/chat", methods=["POST"])
def chat():
    datos = request.get_json(silent=True) or {}
    mensaje = str(datos.get("mensaje", "")).strip()

    if not mensaje:
        return jsonify({"response": "Escribe un mensaje para comenzar.", "mode": "DEMO"})

    sid = obtener_sid(datos)

    # Un mensaje a la vez por visitante: si llega otro antes de terminar el anterior,
    # espera su turno y ya encuentra la respuesta guardada en el historial.
    with candado_de(sid):
        historial = HISTORIALES.setdefault(sid, [])
        turno_usuario = {"role": "user", "content": mensaje}
        texto, modo = None, "IA"

        # >>> EXPONE: CASAS (parte 3) · Ruta /chat: IA, modo DEMO e historial
        if MOTORES:
            try:
                texto = llamar_ia(historial + [turno_usuario], construir_instrucciones(sid))
            except Exception as error:
                print("--- ERROR CRÍTICO DE LA IA ---")
                print(error)
                print("------------------------------")

        if texto is None:
            texto, modo = respuesta_demo(mensaje, sid), "DEMO"

        # Se guarda siempre (también las respuestas DEMO), para que la IA, cuando vuelva,
        # sepa qué se le dijo al usuario y no repita preguntas.
        historial.append(turno_usuario)
        historial.append({"role": "assistant", "content": texto})
        # Conserva solo los últimos 10 intercambios
        del historial[:-2 * MAX_TURNOS]
        limitar_memoria()

    return jsonify({"response": texto, "mode": modo})

# ==========================================
# DIAGNÓSTICO
# ==========================================



# >>> EXPONE: MONSALVE (parte 2) · Conversión de datos y cálculo del promedio
def a_entero(valor):
    """Convierte a entero y limita el valor entre 0 y 100."""
    try:
        # Deja el valor siempre entre 0 y 100
        return max(0, min(100, int(valor)))
    except (TypeError, ValueError):
        return 0


@app.route("/diagnostico", methods=["POST"])
def diagnostico():
    datos = request.get_json(silent=True) or {}
    sid = obtener_sid(datos)

    experiencia = a_entero(datos.get("experiencia", 0))
    capacidad = a_entero(datos.get("capacidad", 0))
    finanzas = a_entero(datos.get("finanzas", 0))
    comercial = a_entero(datos.get("comercial", 0))
    conocimiento = a_entero(datos.get("conocimiento", 0))

    # Promedio de las cinco áreas
    promedio = (experiencia + capacidad + finanzas + comercial + conocimiento) / 5

    # >>> EXPONE: NICOLÁS (parte 4) · Nivel y descripción según el promedio
    if promedio <= 25:
        nivel = "Explorador"
        descripcion = "La empresa se encuentra en una etapa inicial y necesita fortalecer sus conocimientos y capacidades."
    elif promedio <= 50:
        nivel = "Preparándose"
        descripcion = "La empresa presenta algunas capacidades, pero todavía tiene áreas importantes que debe fortalecer."
    elif promedio <= 75:
        nivel = "Competente"
        descripcion = "La empresa cuenta con una base sólida para avanzar hacia oportunidades en el mercado público."
    else:
        nivel = "Avanzado"
        descripcion = "La empresa presenta un alto nivel de preparación para participar en el mercado público."

    # >>> EXPONE: MONSALVE (parte 3) · Áreas y necesidades
    areas = {
        "Experiencia": experiencia,
        "Capacidad operativa": capacidad,
        "Finanzas": finanzas,
        "Preparación comercial": comercial,
        "Conocimiento del mercado público": conocimiento
    }

    # Brechas: áreas con menos de 50 puntos
    necesidades = [area for area, puntuacion in areas.items() if puntuacion < 50]

    # >>> EXPONE: DIEGO (parte 4) · Recomendaciones
    recomendaciones = []
    if experiencia < 50:
        recomendaciones.append("Fortalecer el conocimiento sobre procesos de contratación pública.")
    if capacidad < 50:
        recomendaciones.append("Revisar la capacidad operativa para responder a posibles contratos.")
    if finanzas < 50:
        recomendaciones.append("Mejorar la planificación financiera y capacidad de cumplimiento.")
    if comercial < 50:
        recomendaciones.append("Fortalecer la propuesta comercial y presentación de la empresa.")
    if conocimiento < 50:
        recomendaciones.append("Aprender sobre oportunidades, requisitos y procesos del mercado público.")
    if not recomendaciones:
        recomendaciones.append("Mantener las capacidades actuales y buscar oportunidades para seguir creciendo.")



    # >>> EXPONE: RICARDO (parte 3) · Inserción en la base de datos y respuesta del diagnóstico
    conexion = sqlite3.connect(RUTA_DB)
    cursor = conexion.cursor()
    # Los signos ? evitan la inyección SQL
    cursor.execute("""
        INSERT INTO diagnosticos
        (empresa, sector, experiencia, capacidad, finanzas, comercial, conocimiento, promedio, nivel)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datos.get("empresa", ""),
        datos.get("sector", ""),
        experiencia, capacidad, finanzas, comercial, conocimiento, promedio, nivel
    ))
    conexion.commit()
    conexion.close()

    resultado = {
        "empresa": datos.get("empresa") or "Tu empresa",
        "sector": datos.get("sector") or "No especificado",
        "promedio": round(promedio, 1),
        "nivel": nivel,
        "descripcion": descripcion,
        "necesidades": necesidades,
        "recomendaciones": recomendaciones
    }

    # Se guarda (por visitante) para que el chat pueda usarlo en la conversación
    DIAGNOSTICOS[sid] = {**resultado, "puntajes": areas}
    limitar_memoria()

    return jsonify(resultado)

# >>> EXPONE: JOSÉ LUIS (parte 3) · CORS, página principal y ejecución
# Permite que el HTML abierto directo (file://) pueda hablar con este servidor.
@app.after_request
def permitir_cors(respuesta):
    respuesta.headers["Access-Control-Allow-Origin"] = "*"
    respuesta.headers["Access-Control-Allow-Headers"] = "Content-Type"
    respuesta.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return respuesta

# ==========================================
# PÁGINA PRINCIPAL
# ==========================================
@app.route("/")
def inicio():
    return render_template("index.html")

if __name__ == "__main__":
    # debug=True reinicia solo y muestra errores (solo para desarrollo)
    app.run(debug=True)