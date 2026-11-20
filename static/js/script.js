// REPARTO PARA LA EXPOSICIÓN: cada marca ">>> EXPONE" indica quién explica desde ese punto
// hasta la siguiente marca. Nombre y número de parte coinciden con la guía en PDF.

// >>> EXPONE: DIEGO (parte 5) · Constantes API_BASE, SID e iniciarDiagnostico
// Si el HTML se abre directo (file://), las llamadas van al servidor Flask local.
const API_BASE = location.protocol === "file:" ? "http://127.0.0.1:5000" : "";

// Identificador de esta conversación. Se envía en cada petición para que el servidor
// recuerde el historial y el diagnóstico sin depender de cookies (también sirve con file://).
const SID = (window.crypto && crypto.randomUUID)
    ? crypto.randomUUID()
    : "s" + Date.now().toString(36) + Math.random().toString(36).slice(2);

// ==========================================================
// INICIAR DIAGNÓSTICO
// ==========================================================
function iniciarDiagnostico() {
    const seccion = document.getElementById("diagnostico");
    seccion.classList.remove("hidden");
    seccion.scrollIntoView({ behavior: "smooth" });
}

// >>> EXPONE: STEVEN (parte 5) · realizarDiagnostico: recolección de datos
// ==========================================================
// DIAGNÓSTICO
// ==========================================================
async function realizarDiagnostico(event) {
    if (event) event.preventDefault();

    const datos = {
        empresa: document.getElementById("empresa").value, 
        sector: document.getElementById("sector").value,
        experiencia: document.getElementById("experiencia").value,
        capacidad: document.getElementById("capacidad").value,
        finanzas: document.getElementById("finanzas").value,
        comercial: document.getElementById("comercial").value,
        conocimiento: document.getElementById("conocimiento").value,
        sid: SID
    };

    // >>> EXPONE: JOSÉ LUIS (parte 4) · realizarDiagnostico: validación y fetch
    if (!datos.empresa) {
        alert("Escribe el nombre de tu empresa.");
        return;
    }

    const respuesta = await fetch(API_BASE + "/diagnostico", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(datos)
    });

    const resultado = await respuesta.json();
    mostrarResultado(resultado);
}

// >>> EXPONE: CASAS (parte 4) · mostrarResultado: listas de brechas y recomendaciones
// ==========================================================
// MOSTRAR RESULTADO
// ==========================================================
function mostrarResultado(resultado) {
    const heroScore = document.getElementById("heroScore");
    if (heroScore) {
        heroScore.innerText = `${resultado.promedio}`;
    }

    const seccion = document.getElementById("resultado");
    
    let necesidades = "";
    resultado.necesidades.forEach(necesidad => {
        necesidades += `<li>${necesidad}</li>`;
    });

    let recomendaciones = "";
    resultado.recomendaciones.forEach(recomendacion => {
        recomendaciones += `<li>${recomendacion}</li>`;
    });

    // >>> EXPONE: JUANJOAR (parte 4) · mostrarResultado: tarjeta de resultado
    seccion.innerHTML = `
        <div class="resultado-card">
            <p>Empresa: <strong>${resultado.empresa}</strong></p>
            <p>Sector: <strong>${resultado.sector}</strong></p>
            <div class="puntuacion">${resultado.promedio}/100</div>
            <div class="nivel">Nivel: ${resultado.nivel}</div>
            
            <h3>Principales brechas</h3>
            <ul>${necesidades || "<li>Ninguna brecha crítica.</li>"}</ul>
            
            <h3>Recomendaciones</h3>
            <ul>${recomendaciones}</ul>
        </div>
    `;

    seccion.classList.remove("hidden");
    seccion.scrollIntoView({ behavior: "smooth" });
}

// >>> EXPONE: NICOLÁS (parte 5) · enviarMensaje: preparación
// ==========================================================
// CHAT
// ==========================================================
let enviando = false;

async function enviarMensaje(event) {
    if (event) event.preventDefault();
    if (enviando) return;  // no se envía otro mensaje mientras llega la respuesta

    const input = document.getElementById("messageInput");
    const boton = document.querySelector("#chatForm button");
    const mensaje = input.value.trim();

    if (!mensaje) return;

    enviando = true;
    input.disabled = true;
    if (boton) boton.disabled = true;

    agregarMensaje(mensaje, "usuario");
    input.value = "";
    const cargando = agregarMensaje("Analizando respuesta...", "bot", "CARGANDO");

    // >>> EXPONE: DIEGO (parte 6) · enviarMensaje: petición fetch y respuesta
    try {
        const respuesta = await fetch(API_BASE + "/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mensaje: mensaje, sid: SID })
        });

        const datos = await respuesta.json();
        cargando.remove();
        agregarMensaje(datos.response, "bot", datos.mode);

    // >>> EXPONE: RICARDO (parte 4) · enviarMensaje: catch y finally
    } catch (error) {
        console.error(error);
        cargando.remove();
        agregarMensaje("No pude conectarme con el servidor.", "bot", "ERROR");
    } finally {
        enviando = false;
        input.disabled = false;
        if (boton) boton.disabled = false;
        input.focus();
    }
}

// >>> EXPONE: MONSALVE (parte 4) · agregarMensaje
// ==========================================================
// AGREGAR MENSAJE
// ==========================================================
function agregarMensaje(texto, tipo, modo = "") {
    const chat = document.getElementById("messages");
    const div = document.createElement("div");
    
    div.className = `message ${tipo}`;
    
    if(tipo === "bot") {
        let badgeHtml = modo ? `<span class="mode">${modo}</span>` : '';
        div.innerHTML = `
            <div class="avatar">I</div>
            <div>
                ${badgeHtml}
                <p>${texto}</p>
            </div>
        `;
    } else {
        div.innerText = texto;
    }

    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
    return div;
}