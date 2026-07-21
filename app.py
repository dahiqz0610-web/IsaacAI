import streamlit as st
from groq import Groq
from datetime import datetime
import os
import json
import time
import urllib.request
import urllib.parse
import traceback
import re
import base64

# ==========================================
# CONFIGURACIÓN VISUAL DE LA INTERFAZ (UI)
# ==========================================
st.set_page_config(
    page_title="Isaac AI", 
    page_icon="🤖", 
    layout="centered"
)

# Estilo CSS con animación y módulo de pegado
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stChatMessage {
            padding: 1rem;
            border-radius: 10px;
            margin-bottom: 0.5rem;
        }

        /* 🎬 ANIMACIÓN ARRIBA Y ABAJO */
        @keyframes moverArribaAbajo {
            0% { transform: translateY(0px); }
            50% { transform: translateY(-8px); }
            100% { transform: translateY(0px); }
        }

        .animacion-cargando {
            display: inline-block;
            font-weight: bold;
            color: #00e5ff;
            animation: moverArribaAbajo 0.9s ease-in-out infinite;
            padding: 10px 18px;
            background: rgba(0, 229, 255, 0.1);
            border-radius: 15px;
            border: 1px solid rgba(0, 229, 255, 0.3);
            margin-bottom: 12px;
        }

        .instruccion-pegar {
            background-color: rgba(255, 255, 255, 0.05);
            border: 1px dashed rgba(255, 255, 255, 0.2);
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 0.85rem;
            margin-bottom: 8px;
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# CONFIGURACIÓN DE ARCHIVOS Y PERSISTENCIA
# ==========================================
ARCHIVO_CHATS_PERMANENTE = "historial_chats.json"

def cargar_todas_las_conversaciones():
    if os.path.exists(ARCHIVO_CHATS_PERMANENTE):
        with open(ARCHIVO_CHATS_PERMANENTE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def guardar_todas_las_conversaciones(datos_totales):
    with open(ARCHIVO_CHATS_PERMANENTE, "w", encoding="utf-8") as f:
        json.dump(datos_totales, f, indent=4, ensure_ascii=False)

# ==========================================
# 🔍 BUSCADOR DE INFORMACIÓN Y AUXILIARES
# ==========================================
def buscar_informacion_web(consulta):
    try:
        url_busqueda = f"https://es.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(consulta)}&format=json"
        req = urllib.request.Request(url_busqueda, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            datos = json.loads(response.read().decode())
            resultados = datos.get("query", {}).get("search", [])
            if resultados:
                snippet = resultados[0]["snippet"]
                snippet_limpio = re.sub('<[^<]+?>', '', snippet)
                titulo = resultados[0]["title"]
                return f"Personaje/Tema: {titulo}. Descripción: {snippet_limpio}"
    except Exception:
        pass
    return ""

def encode_image_to_base64(image_file):
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

# ==========================================
# 🔐 GESTIÓN DE SESIÓN Y CÓDIGO DE COMANDO
# ==========================================
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.tipo_usuario = None  
    st.session_state.usuario_info = ""

if "codigo_actualizacion" not in st.session_state:
    st.session_state.codigo_actualizacion = "123"

if not st.session_state.autenticado:
    st.title("🤖 Bienvenido a Isaac AI")
    st.write("Inicia sesión para recuperar tus conversaciones y diseños guardados:")
    
    opcion_acceso = st.radio("Selecciona tu método de acceso:", ["Continuar con Cuenta Google / Gmail", "Acceder como Invitado"])
    
    if opcion_acceso == "Continuar con Cuenta Google / Gmail":
        correo = st.text_input("Introduce tu correo electrónico:", placeholder="usuario@gmail.com")
        if st.button("Verificar e Iniciar Sesión", use_container_width=True):
            if correo.lower().endswith("@gmail.com"):
                st.session_state.autenticado = True
                st.session_state.tipo_usuario = "Privilegiado"
                st.session_state.usuario_info = correo.lower().strip()
                st.success(f"Sesión iniciada como {correo}")
                st.rerun()
            else:
                st.error("Se requiere una cuenta de Gmail válida (@gmail.com).")
    else:
        st.write("⚠️ El modo invitado no almacena conversaciones de forma permanente.")
        if st.button("Entrar en Modo Invitado", use_container_width=True):
            st.session_state.autenticado = True
            st.session_state.tipo_usuario = "Invitado"
            st.session_state.usuario_info = "Invitado"
            st.rerun()
            
    st.stop()

# ==========================================
# CONEXIÓN A GROQ API
# ==========================================
@st.cache_resource
def conectar_groq():
    api_key = st.secrets.get("GROQ_API_KEY", "")
    return Groq(api_key=api_key)

client = conectar_groq()
MODELO_TEXTO = "llama-3.1-8b-instant"
MODELO_VISION = "llama-3.2-11b-vision-preview"

@st.cache_data(ttl=3600)
def detectar_pais_silencioso():
    try:
        url = "http://ip-api.com/json/"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=1) as response:
            datos = json.loads(response.read().decode())
            return f"{datos.get('city', 'Desconocida')}, {datos.get('country', 'Desconocido')}"
    except Exception:
        return "Ubicación Desconocida"

if "ubicacion" not in st.session_state:
    st.session_state.ubicacion = detectar_pais_silencioso()

# ==========================================
# 🔄 SINCRONIZACIÓN DE HISTORIAL
# ==========================================
base_datos_chats = cargar_todas_las_conversaciones()
usuario_actual = st.session_state.usuario_info

if usuario_actual not in base_datos_chats or not base_datos_chats[usuario_actual]:
    base_datos_chats[usuario_actual] = {
        "chat_inicial": {"titulo": "Nueva Conversación", "historial": []}
    }
    guardar_todas_las_conversaciones(base_datos_chats)

st.session_state.conversaciones = base_datos_chats[usuario_actual]

if ("chat_actual_id" not in st.session_state or 
    st.session_state.chat_actual_id not in st.session_state.conversaciones):
    st.session_state.chat_actual_id = list(st.session_state.conversaciones.keys())[0]

# ==========================================
# 💾 BARRA LATERAL CON AJUSTES
# ==========================================
with st.sidebar:
    st.write(f"### 👤 {st.session_state.usuario_info}")
    st.caption(f"📍 {st.session_state.ubicacion}")
    
    if st.button("➕ Nueva conversación", use_container_width=True):
        nuevo_id = f"chat_{int(datetime.now().timestamp())}"
        st.session_state.conversaciones[nuevo_id] = {"titulo": "Nueva Conversación", "historial": []}
        st.session_state.chat_actual_id = nuevo_id
        
        base_datos_chats[usuario_actual] = st.session_state.conversaciones
        guardar_todas_las_conversaciones(base_datos_chats)
        st.rerun()
        
    st.markdown("---")
    
    with st.expander("🔑 Código de actualización rápida", expanded=False):
        nuevo_codigo = st.text_input("Código de comando:", value=st.session_state.codigo_actualizacion)
        if nuevo_codigo:
            st.session_state.codigo_actualizacion = nuevo_codigo.strip()
        st.caption("Escribe en el chat `[CÓDIGO] actualizar` (ej: `123 actualizar`) para recargar.")

    criterio_busqueda = st.text_input("🔍 Buscar conversación...", placeholder="Filtrar por tema...")
    
    st.write("#### 💬 Recientes")
    for id_chat, datos_chat in list(st.session_state.conversaciones.items()):
        if criterio_busqueda.lower() in datos_chat["titulo"].lower():
            es_activo = id_chat == st.session_state.chat_actual_id
            marcador = "📌 " if es_activo else "• "
            
            col_btn, col_del = st.columns([0.8, 0.2])
            with col_btn:
                if st.button(f"{marcador}{datos_chat['titulo']}", key=f"btn_{id_chat}", use_container_width=True):
                    st.session_state.chat_actual_id = id_chat
                    st.rerun()
            with col_del:
                if st.button("🗑️", key=f"del_{id_chat}"):
                    del st.session_state.conversaciones[id_chat]
                    if not st.session_state.conversaciones:
                        nuevo_id = f"chat_{int(datetime.now().timestamp())}"
                        st.session_state.conversaciones[nuevo_id] = {"titulo": "Nueva Conversación", "historial": []}
                    st.session_state.chat_actual_id = list(st.session_state.conversaciones.keys())[0]
                    base_datos_chats[usuario_actual] = st.session_state.conversaciones
                    guardar_todas_las_conversaciones(base_datos_chats)
                    st.rerun()

    st.markdown("---")
    if st.button("🔒 Cerrar Sesión", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# ==========================================
# 💬 INTERFAZ Y CHAT
# ==========================================
chat_activo = st.session_state.conversaciones[st.session_state.chat_actual_id]

st.title(f"{chat_activo['titulo']}")

# 📷 ÁREA DE PEGAR / CARGAR IMÁGENES
with st.expander("📷 Adjuntar o Pegar Imagen (Portapapeles / Archivo)", expanded=False):
    st.markdown("""
    <div class="instruccion-pegar">
        📋 <b>Para pegar desde el portapapeles:</b> Haz clic en la casilla inferior y presiona <b>Ctrl + V</b> (o <b>Cmd + V</b> en Mac).
    </div>
    """, unsafe_allow_html=True)
    
    imagen_subida = st.file_uploader(
        "Sube, arrastra o pega una imagen:", 
        type=["png", "jpg", "jpeg", "webp"],
        key="uploader_imagen"
    )
    if imagen_subida:
        st.image(imagen_subida, caption="Imagen cargada correctamente", use_container_width=True)

st.markdown("---")

# Renderizar historial en la pantalla
for msg in chat_activo["historial"]:
    with st.chat_message(msg["role"]):
        if msg.get("tipo") == "imagen":
            st.image(msg["content"], use_container_width=True)
        else:
            st.markdown(msg["content"])

mensajes_enviados = sum(1 for m in chat_activo["historial"] if m["role"] == "user")
bloqueado_por_restriccion = False
if st.session_state.tipo_usuario == "Invitado" and mensajes_enviados >= 5:
    bloqueado_por_restriccion = True
    st.error("⚠️ Límite del Modo Invitado alcanzado.")

if not bloqueado_por_restriccion:
    if prompt := st.chat_input("Escribe una pregunta, 'cuanto es 1+1', 'dibuja a Tanjiro' o '123 actualizar'..."):
        
        with st.chat_message("user"):
            st.markdown(prompt)
        chat_activo["historial"].append({"role": "user", "content": prompt})
        
        if len(chat_activo["historial"]) == 1:
            chat_activo["titulo"] = prompt[:30].strip() + ("..." if len(prompt) > 30 else "")

        # ==========================================
        # ⚡ COMANDO DE ACTUALIZACIÓN RÁPIDA
        # ==========================================
        prompt_limpio_cmd = prompt.strip().lower()
        codigo_cmd = st.session_state.codigo_actualizacion.lower()

        if prompt_limpio_cmd.startswith(codigo_cmd) and ("actualiz" in prompt_limpio_cmd or "reload" in prompt_limpio_cmd or "reset" in prompt_limpio_cmd):
            st.cache_data.clear()
            st.cache_resource.clear()
            
            msg_exito = f"🔄 **Sistema actualizado.** Código utilizado: `{st.session_state.codigo_actualizacion}`. Memoria caché limpia."
            with st.chat_message("assistant"):
                st.markdown(msg_exito)
            
            chat_activo["historial"].append({"role": "assistant", "content": msg_exito})
            base_datos_chats[usuario_actual] = st.session_state.conversaciones
            guardar_todas_las_conversaciones(base_datos_chats)
            time.sleep(0.5)
            st.rerun()

        # ==========================================
        # 🤖 EJECUCIÓN (TEXTO O IMAGEN)
        # ==========================================
        else:
            with st.chat_message("assistant"):
                marcador_animado = st.empty()
                
                marcador_animado.markdown(
                    '<div class="animacion-cargando">🧠 Clasificando consulta...</div>', 
                    unsafe_allow_html=True
                )
                time.sleep(0.2)

                texto_lower = prompt.lower()
                palabras_creacion = ["dibuja", "dibujame", "crea una imagen", "creame una imagen", "genera una imagen", "pinta", "pintame", "haz una imagen", "foto de", "imagen de"]
                exclusiones = ["codigo", "código", "programa", "python", "escribe", "explica", "resuelve", "cuanto", "cuánto", "+", "-", "*", "/"]

                quiere_imagen = any(p in texto_lower for p in palabras_creacion) and not any(e in texto_lower for e in exclusiones)

                # 🎨 CASO 1: GENERACIÓN DE IMAGEN
                if quiere_imagen:
                    marcador_animado.markdown(
                        '<div class="animacion-cargando">🔍 Obteniendo contexto visual...</div>', 
                        unsafe_allow_html=True
                    )
                    
                    prompt_limpio = prompt.lower()
                    for p in palabras_creacion:
                        prompt_limpio = prompt_limpio.replace(p, "")
                    nombre_personaje = prompt_limpio.strip()

                    info_web = buscar_informacion_web(nombre_personaje)

                    marcador_animado.markdown(
                        '<div class="animacion-cargando">🎨 Ilustrando y generando imagen...</div>', 
                        unsafe_allow_html=True
                    )

                    try:
                        base_prompt = f"{nombre_personaje}, {info_web}".strip(", ")
                        prompt_optimizado = f"{base_prompt}, highly detailed, 8k resolution, cinematic atmosphere"
                        prompt_url = urllib.parse.quote(prompt_optimizado)
                        seed = int(datetime.now().timestamp())

                        url_final_imagen = f"https://image.pollinations.ai/prompt/{prompt_url}?width=1024&height=1024&nologo=true&seed={seed}"
                        
                        req = urllib.request.Request(url_final_imagen, headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(req, timeout=25):
                            pass

                        marcador_animado.image(url_final_imagen, use_container_width=True)

                        chat_activo["historial"].append({
                            "role": "assistant", 
                            "content": url_final_imagen, 
                            "tipo": "imagen",
                            "prompt": nombre_personaje
                        })

                    except Exception as e:
                        tipo_err = type(e).__name__
                        causa_err = str(e)
                        traza_err = traceback.format_exc()
                        
                        error_formateado = f"""🚨 **Error al generar la imagen**
                        
* **Tipo / Código:** `{tipo_err}`
* **Causa:** {causa_err}

```text
{traza_err}
```"""
                        marcador_animado.markdown(error_formateado)
                        chat_activo["historial"].append({"role": "assistant", "content": error_formateado})

                # 📝 CASO 2: TEXTO / CÓDIGO / MATEMÁTICAS (OPTIMIZADO PARA TOKEN RATE LIMITS)
                else:
                    ahora = datetime.now()
                    contexto_sistema = f"Eres Isaac AI, una IA inteligente y directa. Fecha actual: {ahora.strftime('%d/%m/%Y')}."
                    
                    mensajes_api = [{"role": "system", "content": contexto_sistema}]
                    
                    # 🛠️ FILTRO CRÍTICO: Tomar solo los últimos 4 mensajes y OMITIR errores previos
                    historial_reciente = chat_activo["historial"][-4:]
                    
                    for m in historial_reciente:
                        role = m.get("role")
                        if role not in ["user", "assistant"]:
                            continue

                        if m.get("tipo") == "imagen":
                            content_texto = f'[Imagen previa sobre: "{m.get("prompt","")}"]'
                        else:
                            content_texto = str(m.get("content", ""))

                        # IGNORAR errores anteriores con Tracebacks gigantes para no saturar tokens
                        if "🚨" in content_texto or "Traceback (most recent call last)" in content_texto or "APIStatusError" in content_texto:
                            continue

                        # Si un mensaje individual es colosal, recortarlo a un tamaño seguro
                        if len(content_texto) > 1200:
                            content_texto = content_texto[:1200] + "... [texto resumido para ahorrar cuota]"

                        if not content_texto.strip():
                            continue

                        if mensajes_api[-1]["role"] == role:
                            mensajes_api[-1]["content"] += "\n" + content_texto
                        else:
                            mensajes_api.append({"role": role, "content": content_texto})

                    modelo_a_usar = MODELO_TEXTO
                    if imagen_subida is not None:
                        try:
                            base64_img = encode_image_to_base64(imagen_subida)
                            modelo_a_usar = MODELO_VISION
                            mensajes_api[-1] = {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
                                ]
                            }
                        except Exception as e:
                            st.warning(f"Error con la imagen de referencia: {e}")

                    marcador_texto = st.empty()
                    texto_completo = ""
                    
                    try:
                        stream = client.chat.completions.create(
                            model=modelo_a_usar, 
                            messages=mensajes_api, 
                            stream=True, 
                            temperature=0.3,
                            max_tokens=500  # Reducido para no rebasar el límite de 6000 TPM
                        )
                        
                        for parte in stream:
                            contenido = parte.choices[0].delta.content
                            if contenido:
                                for letra in contenido:
                                    texto_completo += letra
                                    marcador_texto.markdown(texto_completo + "▌")
                                    time.sleep(0.015)
                                    
                        marcador_texto.markdown(texto_completo)

                    except Exception as e:
                        tipo_err = type(e).__name__
                        causa_err = str(e)
                        traza_err = traceback.format_exc()
                        
                        texto_completo = f"""🚨 **Se ha producido un error en la llamada a la API**

* **Código / Tipo de Error:** `{tipo_err}`
* **Descripción:** {causa_err}

```text
{traza_err}
```"""
                        marcador_texto.markdown(texto_completo)
                        
                    chat_activo["historial"].append({"role": "assistant", "content": texto_completo})
            
            base_datos_chats[usuario_actual] = st.session_state.conversaciones
            guardar_todas_las_conversaciones(base_datos_chats)
            st.rerun()
