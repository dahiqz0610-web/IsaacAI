import base64
from datetime import datetime
import json
import os
import re
import time
import traceback
import urllib.parse
import urllib.request
from groq import Groq
import streamlit as st

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
# CONEXIÓN A GROQ API Y MODELOS
# ==========================================
@st.cache_resource
def conectar_groq():
    api_key = st.secrets.get("GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
    return Groq(api_key=api_key)

client = conectar_groq()

# Modelos recomendados y actualizados de Groq
MODELO_TEXTO = "llama-3.3-70b-versatile"     # Excelente para razonamiento y respuestas en español
MODELO_RAPIDO = "llama-3.1-8b-instant"        # Para revisiones y tareas auxiliares ultra rápidas
MODELO_VISION = "llama-3.2-11b-vision-preview" # Modelo multitarea con capacidad visual

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
        ["⚡ Normal", "🚀 Pro (Doble Revisión)"],
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
    st.error("⚠️ Límite del Modo Invitado alcanzado. Inicia sesión con Gmail para continuar.")

placeholder_chat = "Escribe tu pregunta..." if modo_operacion == "💬 Texto / Chat" else "Describe la imagen que deseas generar..."

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

        if prompt_limpio_cmd.startswith(codigo_cmd) and any(kw in prompt_limpio_cmd for kw in ["actualiz", "reload", "reset"]):
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
        # 🎨 MODO GENERAR IMAGEN
        # ==========================================
        elif modo_operacion == "🎨 Generar Imagen":
            with st.chat_message("assistant"):
                
                patrones_nueva_imagen = [
                    "nueva imagen", "imagen nueva", "pinta uno nuevo", "crea uno nuevo",
                    "haz uno nuevo", "desde cero", "otra imagen", "otro dibujo", "nuevo dibujo",
                    "crea imagen nueva", "haz una imagen nueva", "pinta algo nuevo", "haz otro"
                ]
                
                quiere_imagen_nueva = any(p in prompt.lower() for p in patrones_nueva_imagen)
                
                ultimo_prompt_en = ""
                if not quiere_imagen_nueva:
                    for msg_h in reversed(chat_activo["historial"][:-1]):
                        if msg_h.get("tipo") == "imagen" and msg_h.get("prompt_en"):
                            ultimo_prompt_en = msg_h.get("prompt_en")
                            break

                try:
                    if nivel_potencia == "🚀 Pro (Doble Revisión)":
                        with st.status("🚀 **Modo Pro Imagen:** Razonamiento visual avanzado...", expanded=True) as status:
                            
                            st.write("🎨 **Fase 1:** Diseñando estructura y perspectiva base...")
                            system_p1 = "You are an AI Art Director. Translate user request into a rich visual concept prompt in English. Output ONLY the prompt string."
                            user_p1 = f"Previous Context: '{ultimo_prompt_en}'. Request: '{prompt}'" if ultimo_prompt_en else f"Request: '{prompt}'"
                            
                            r1 = client.chat.completions.create(
                                model=MODELO_RAPIDO,
                                messages=[{"role": "system", "content": system_p1}, {"role": "user", "content": user_p1}],
                                temperature=0.4,
                                max_tokens=120
                            )
                            prompt_v1 = r1.choices[0].message.content.strip().replace('"', '')

                            st.write("🔍 **Fase 2 (Revisión 1):** Auditando composición, encuadre e iluminación...")
                            system_p2 = "Improve this image prompt by enhancing cinematic lighting, shadow depth, camera angle, and lens detail. Output ONLY the improved prompt string."
                            
                            r2 = client.chat.completions.create(
                                model=MODELO_RAPIDO,
                                messages=[{"role": "system", "content": system_p2}, {"role": "user", "content": prompt_v1}],
                                temperature=0.3,
                                max_tokens=130
                            )
                            prompt_v2 = r2.choices[0].message.content.strip().replace('"', '')

                            st.write("💎 **Fase 3 (Revisión 2):** Pulido de texturas, realismo y calidad 8K...")
                            system_p3 = "Final polish on this art prompt: add photographic realism, materials texture, 8k resolution tags. Keep it under 80 words. Output ONLY the final prompt."
                            
                            r3 = client.chat.completions.create(
                                model=MODELO_RAPIDO,
                                messages=[{"role": "system", "content": system_p3}, {"role": "user", "content": prompt_v2}],
                                temperature=0.2,
                                max_tokens=140
                            )
                            prompt_sintetizado = r3.choices[0].message.content.strip().replace('"', '')

                            status.update(label="✅ **Doble revisión de imagen completada**", state="complete", expanded=False)
                    else:
                        system_prompt = "Translate and combine into a clean English art prompt. Output ONLY prompt string."
                        user_prompt = f"Previous Context: '{ultimo_prompt_en}'. Request: '{prompt}'" if ultimo_prompt_en else prompt
                        
                        res_prompt = client.chat.completions.create(
                            model=MODELO_RAPIDO,
                            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                            temperature=0.3,
                            max_tokens=100
                        )
                        prompt_sintetizado = res_prompt.choices[0].message.content.strip().replace('"', '')

                    # Construcción del enlace
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
        # 📝 MODO TEXTO
        # ==========================================
        else:
            with st.chat_message("assistant"):
                ahora = datetime.now()
                contexto_sistema = f"Eres Isaac AI, una IA inteligente y directa. Fecha actual: {ahora.strftime('%d/%m/%Y')}."
                
                mensajes_api = [{"role": "system", "content": contexto_sistema}]
                historial_reciente = chat_activo["historial"][-5:]
                
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
                        st.warning(f"Error al procesar la imagen adjunta: {e}")

                try:
                    mensajes_envio = mensajes_api

                    # 🚀 MODO PRO CON DOBLE REVISIÓN
                    if nivel_potencia == "🚀 Pro (Doble Revisión)":
                        with st.status("🧠 **Modo Pro:** Pensando, revisando (2x) y puliendo...", expanded=True) as status:
                            
                            # PASO 1: Borrador inicial
                            st.write("✏️ **Paso 1:** Generando respuesta borrador...")
                            res_borrador = client.chat.completions.create(
                                model=modelo_a_usar,
                                messages=mensajes_api,
                                temperature=0.3,
                                max_tokens=600
                            )
                            borrador_1 = res_borrador.choices[0].message.content

                            # PASO 2: Primera Revisión
                            st.write("🔍 **Paso 2 (Revisión 1):** Auditando precisión y lógica...")
                            p_critica_1 = [
                                {"role": "system", "content": "Eres un editor crítico. Identifica cualquier falta de lógica, omisión o imprecisión en el borrador. Sé breve."},
                                {"role": "user", "content": f"Pregunta: '{prompt}'\nBorrador: '{borrador_1}'"}
                            ]
                            c1 = client.chat.completions.create(model=MODELO_RAPIDO, messages=p_critica_1, temperature=0.2, max_tokens=150).choices[0].message.content

                            # PASO 3: Primera Mejora
                            st.write("🔧 **Paso 3:** Aplicando primera ronda de mejoras...")
                            p_mejora_1 = mensajes_api + [
                                {"role": "assistant", "content": borrador_1},
                                {"role": "user", "content": f"Aplica estas correcciones a la respuesta: {c1}"}
                            ]
                            borrador_2 = client.chat.completions.create(model=modelo_a_usar, messages=p_mejora_1, temperature=0.3, max_tokens=700).choices[0].message.content

                            # PASO 4: Segunda Revisión
                            st.write("🔎 **Paso 4 (Revisión 2):** Auditando claridad y fluidez final...")
                            p_critica_2 = [
                                {"role": "system", "content": "Revisa este texto mejorado y da sugerencias para maximizar su claridad y utilidad en español."},
                                {"role": "user", "content": f"Pregunta original: '{prompt}'\nTexto mejorado: '{borrador_2}'"}
                            ]
                            c2 = client.chat.completions.create(model=MODELO_RAPIDO, messages=p_critica_2, temperature=0.2, max_tokens=150).choices[0].message.content

                            # PASO 5: Construcción del prompt final
                            mensajes_envio = mensajes_api + [
                                {"role": "assistant", "content": borrador_2},
                                {"role": "user", "content": f"Reescribe la respuesta final perfeccionándola con esta última revisión de calidad: {c2}"}
                            ]
                            
                            status.update(label="✅ **Doble revisión Pro completada**", state="complete", expanded=False)

                    # Generación final con streaming
                    marcador_texto = st.empty()
                    texto_completo = ""
                    stream = client.chat.completions.create(
                        model=modelo_a_usar,
                        messages=mensajes_envio,
                        stream=True,
                        temperature=0.3,
                        max_tokens=800
                    )
                    
                    for parte in stream:
                        contenido = parte.choices[0].delta.content if parte.choices and parte.choices[0].delta else None
                        if contenido:
                            texto_completo += contenido
                            marcador_texto.markdown(texto_completo + "▌")
                            time.sleep(0.005)
                            
                    marcador_texto.markdown(texto_completo)

                except Exception as e:
                    tipo_err = type(e).__name__
                    causa_err = str(e)
                    traza_err = traceback.format_exc()
                    
                    texto_completo = f"🚨 **Se ha producido un error en la llamada a la API**\n\n* **Tipo:** `{tipo_err}`\n* **Descripción:** {causa_err}\n```text\n{traza_err}\n```"
                    st.markdown(texto_completo)
                    
                chat_activo["historial"].append({"role": "assistant", "content": texto_completo})
        
        # Guardar cambios en el archivo
        base_datos_chats[usuario_actual] = st.session_state.conversaciones
        guardar_todas_las_conversaciones(base_datos_chats)
        st.rerun()
