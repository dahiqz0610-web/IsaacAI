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

# Estilo CSS personalizado
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stChatMessage {
            padding: 1rem;
            border-radius: 10px;
            margin-bottom: 0.5rem;
        }

        /* 🎬 ANIMACIÓN DE CARGA */
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
# 💬 INTERFAZ PRINCIPAL DE CHAT
# ==========================================
chat_activo = st.session_state.conversaciones[st.session_state.chat_actual_id]

st.title(f"{chat_activo['titulo']}")

# 🎛️ SELECTORES DE MODO Y POTENCIA
col_modo, col_potencia = st.columns(2)

with col_modo:
    modo_operacion = st.radio(
        "Formato de respuesta:",
        ["💬 Texto / Chat", "🎨 Generar Imagen"],
        key="selector_modo_ia"
    )

with col_potencia:
    nivel_potencia = st.radio(
        "Nivel de procesamiento:",
        ["⚡ Normal", "🚀 Pro (Auto-Reflexión)"],
        key="selector_potencia"
    )

# 📷 ÁREA DE ADJUNTAR IMAGEN (PARA MODO TEXTO CON VISIÓN)
with st.expander("📷 Adjuntar / Pegar Imagen de Análisis", expanded=False):
    st.markdown("""
    <div class="instruccion-pegar">
        📋 <b>Para pegar desde el portapapeles:</b> Haz clic en la casilla inferior y presiona <b>Ctrl + V</b> (o <b>Cmd + V</b> en Mac).
    </div>
    """, unsafe_allow_html=True)
    
    imagen_subida = st.file_uploader(
        "Sube una imagen para analizar:", 
        type=["png", "jpg", "jpeg", "webp"],
        key="uploader_imagen"
    )
    if imagen_subida:
        st.image(imagen_subida, caption="Imagen cargada correctamente", use_container_width=True)

st.markdown("---")

# Renderizar historial de conversación
for msg in chat_activo["historial"]:
    with st.chat_message(msg["role"]):
        if msg.get("tipo") == "imagen":
            st.image(msg["content"], caption=f"🎨 {msg.get('prompt', '')}", use_container_width=True)
        else:
            st.markdown(msg["content"])

mensajes_enviados = sum(1 for m in chat_activo["historial"] if m["role"] == "user")
bloqueado_por_restriccion = False
if st.session_state.tipo_usuario == "Invitado" and mensajes_enviados >= 5:
    bloqueado_por_restriccion = True
    st.error("⚠️ Límite del Modo Invitado alcanzado.")

placeholder_chat = "Escribe tu pregunta o duda..." if modo_operacion == "💬 Texto / Chat" else "Pide una imagen o solicita cambios a la anterior..."

if not bloqueado_por_restriccion:
    if prompt := st.chat_input(placeholder_chat):
        
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
        # 🎨 MODO GENERAR IMAGEN (NORMAL O PRO)
        # ==========================================
        elif modo_operacion == "🎨 Generar Imagen":
            with st.chat_message("assistant"):
                
                # 🔍 Buscar si hay memoria de una imagen anterior
                ultimo_prompt_en = ""
                for msg_h in reversed(chat_activo["historial"][:-1]):
                    if msg_h.get("tipo") == "imagen" and msg_h.get("prompt_en"):
                        ultimo_prompt_en = msg_h.get("prompt_en")
                        break

                try:
                    if nivel_potencia == "🚀 Pro (Auto-Reflexión)":
                        with st.status("🚀 **Modo Pro Imagen:** Razonando composición...", expanded=True) as status:
                            st.write("🔍 **Paso 1:** Analizando memoria contextual e intencionalidad...")
                            time.sleep(0.3)
                            
                            st.write("🎨 **Paso 2:** Estructurando perspectiva, estilo de render e iluminación...")
                            
                            system_prompt = (
                                "You are an elite AI Art Director. "
                                "Analyze the user request and generate an ultra-detailed English image prompt. "
                                "Describe environment, lighting, textures, cinematic composition, and subject precise details. "
                                "Output ONLY the final English prompt. No markdown, no quotes."
                            )
                            user_prompt = f"Previous Image Context: '{ultimo_prompt_en}'\nNew User Wish: '{prompt}'" if ultimo_prompt_en else f"User Request: '{prompt}'"
                            
                            res_prompt = client.chat.completions.create(
                                model=MODELO_TEXTO,
                                messages=[
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": user_prompt}
                                ],
                                temperature=0.4,
                                max_tokens=150
                            )
                            prompt_sintetizado = res_prompt.choices[0].message.content.strip().replace('"', '')
                            
                            st.write("✨ **Paso 3:** Perfeccionando súper-prompt para motor 8K...")
                            status.update(label="✅ **Procesamiento Pro completado**", state="complete", expanded=False)
                    else:
                        # Modo Normal
                        system_prompt = "Translate and combine into a clean, short English art prompt. Output ONLY prompt string."
                        user_prompt = f"Previous Context: '{ultimo_prompt_en}'. New Request: '{prompt}'" if ultimo_prompt_en else prompt
                        
                        res_prompt = client.chat.completions.create(
                            model=MODELO_TEXTO,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt}
                            ],
                            temperature=0.3,
                            max_tokens=100
                        )
                        prompt_sintetizado = res_prompt.choices[0].message.content.strip().replace('"', '')

                    # Construcción y despliegue final
                    prompt_enriquecido = f"{prompt_sintetizado}, highly detailed, 8k resolution, masterpiece"
                    prompt_encoded = urllib.parse.quote(prompt_enriquecido)
                    seed = int(datetime.now().timestamp())
                    url_final_imagen = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width=1024&height=1024&nologo=true&seed={seed}"
                    
                    st.image(url_final_imagen, caption=f"✨ {prompt}", use_container_width=True)

                    chat_activo["historial"].append({
                        "role": "assistant", 
                        "content": url_final_imagen, 
                        "tipo": "imagen",
                        "prompt": prompt,
                        "prompt_en": prompt_sintetizado
                    })

                except Exception as e:
                    tipo_err = type(e).__name__
                    causa_err = str(e)
                    traza_err = traceback.format_exc()
                    
                    error_formateado = f"🚨 **Error al generar la imagen**\n\n* **Tipo:** `{tipo_err}`\n* **Causa:** {causa_err}\n```text\n{traza_err}\n```"
                    st.markdown(error_formateado)
                    chat_activo["historial"].append({"role": "assistant", "content": error_formateado})

        # ==========================================
        # 📝 MODO TEXTO (NORMAL O PRO CON AUTO-REFLEXIÓN)
        # ==========================================
        else:
            with st.chat_message("assistant"):
                ahora = datetime.now()
                contexto_sistema = f"Eres Isaac AI, una IA inteligente y directa. Fecha actual: {ahora.strftime('%d/%m/%Y')}."
                
                # Prepara contexto de mensajes
                mensajes_api = [{"role": "system", "content": contexto_sistema}]
                historial_reciente = chat_activo["historial"][-4:]
                
                for m in historial_reciente:
                    role = m.get("role")
                    if role not in ["user", "assistant"]:
                        continue

                    if m.get("tipo") == "imagen":
                        content_texto = f'[Imagen generada sobre: "{m.get("prompt","")}"]'
                    else:
                        content_texto = str(m.get("content", ""))

                    if "🚨" in content_texto or "Traceback" in content_texto or "APIStatusError" in content_texto:
                        continue

                    if len(content_texto) > 1000:
                        content_texto = content_texto[:1000] + "..."

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
                        st.warning(f"Error con la imagen adjunta: {e}")

                try:
                    # 🚀 LÓGICA MODO PRO (PENSAR -> REVISAR -> MEJORAR)
                    if nivel_potencia == "🚀 Pro (Auto-Reflexión)":
                        with st.status("🧠 **Modo Pro Razonando:** Generando y puliendo respuesta...", expanded=True) as status:
                            
                            # PASO 1: Generar borrador preliminar
                            st.write("✏️ **Paso 1:** Generando borrador inicial...")
                            res_borrador = client.chat.completions.create(
                                model=modelo_a_usar,
                                messages=mensajes_api,
                                temperature=0.3,
                                max_tokens=400
                            )
                            borrador = res_borrador.choices[0].message.content

                            # PASO 2: Auto-crítica y revisión interna
                            st.write("🔍 **Paso 2:** Evaluando exactitud, tono y corrección de errores...")
                            prompt_critica = [
                                {"role": "system", "content": "Eres un auditor crítico de IA. Revisa la siguiente respuesta borrador. Identifica cualquier error lógico, omisión, imprecisión o mejora de claridad requerida. Sé breve y conciso."},
                                {"role": "user", "content": f"Pregunta original: '{prompt}'\nRespuesta borrador: '{borrador}'"}
                            ]
                            res_critica = client.chat.completions.create(
                                model=MODELO_TEXTO,
                                messages=prompt_critica,
                                temperature=0.2,
                                max_tokens=200
                            )
                            critica = res_critica.choices[0].message.content

                            # PASO 3: Redacción final pulida
                            st.write("💎 **Paso 3:** Reescritura y optimización final...")
                            prompt_final = mensajes_api + [
                                {"role": "assistant", "content": borrador},
                                {"role": "user", "content": f"Por favor reescribe la respuesta final perfeccionándola con base en esta autocrítica: {critica}"}
                            ]
                            
                            status.update(label="✅ **Pensamiento Pro completado**", state="complete", expanded=False)

                        # Mostrar respuesta final en streaming
                        marcador_texto = st.empty()
                        texto_completo = ""
                        stream = client.chat.completions.create(
                            model=modelo_a_usar,
                            messages=prompt_final,
                            stream=True,
                            temperature=0.3,
                            max_tokens=500
                        )
                        for parte in stream:
                            contenido = parte.choices[0].delta.content
                            if contenido:
                                for letra in contenido:
                                    texto_completo += letra
                                    marcador_texto.markdown(texto_completo + "▌")
                                    time.sleep(0.01)
                        marcador_texto.markdown(texto_completo)

                    # ⚡ LÓGICA MODO NORMAL (RESPUESTA DIRECTA)
                    else:
                        marcador_texto = st.empty()
                        texto_completo = ""
                        stream = client.chat.completions.create(
                            model=modelo_a_usar, 
                            messages=mensajes_api, 
                            stream=True, 
                            temperature=0.3,
                            max_tokens=500
                        )
                        for parte in stream:
                            contenido = parte.choices[0].delta.content
                            if contenido:
                                for letra in contenido:
                                    texto_completo += letra
                                    marcador_texto.markdown(texto_completo + "▌")
                                    time.sleep(0.012)
                        marcador_texto.markdown(texto_completo)

                except Exception as e:
                    tipo_err = type(e).__name__
                    causa_err = str(e)
                    traza_err = traceback.format_exc()
                    
                    texto_completo = f"🚨 **Se ha producido un error en la llamada a la API**\n\n* **Tipo:** `{tipo_err}`\n* **Descripción:** {causa_err}\n```text\n{traza_err}\n```"
                    st.markdown(texto_completo)
                    
                chat_activo["historial"].append({"role": "assistant", "content": texto_completo})
        
        # Guardar cambios
        base_datos_chats[usuario_actual] = st.session_state.conversaciones
        guardar_todas_las_conversaciones(base_datos_chats)
        st.rerun()
