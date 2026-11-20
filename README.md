# IDEAPRO SmartPath

Asistente web que diagnostica qué tan preparada está una empresa para participar en el mercado público y conversa con ella mediante IA.

## Estructura

```
.
├─ app.py              Servidor Flask: rutas, chat con IA y diagnóstico
├─ requirements.txt    Dependencias de Python
├─ .env                Llaves y modelos (no se comparte, ver abajo)
├─ templates/
│  └─ index.html       Página principal
├─ static/
│  ├─ css/style.css    Estilos
│  └─ js/script.js     Lógica del navegador (diagnóstico y chat)
├─ data/
│  └─ ideapro.db       Base de datos SQLite con los diagnósticos
└─ docs/
   └─ demo-ideapro-smartpath.mp4   Video de demostración
```

## Cómo ejecutarlo

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python app.py
```

Luego abre http://127.0.0.1:5000

## Configuración (.env)

| Variable | Para qué sirve |
|---|---|
| `GEMINI_API_KEY` | Llave de Google Gemini (motor principal) |
| `GEMINI_MODELS` | Modelos de Gemini en orden de prioridad, separados por comas |
| `GROQ_API_KEY` | Llave de Groq (respaldo si Gemini falla) |
| `GROQ_MODELS` | Modelos de Groq en orden de prioridad |
| `FLASK_SECRET_KEY` | Clave para las cookies de sesión |

Sin ninguna llave válida, el chat responde en modo DEMO con respuestas fijas.
