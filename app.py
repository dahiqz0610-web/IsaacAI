import base64
from datetime import datetime
import json
import os
import random
import re
import smtplib
import time
import urllib.parse
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

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

st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stChatMessage {
            padding: 1rem;
            border-radius: 10px;
            margin-bottom: 0.5rem;
        }
        .caja-otp {
            background-color: rgba(0, 229, 255, 0.05);
            border: 1px solid rgba(0, 229, 255, 0.3);
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 15px;
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# ARCHIVOS Y BASE DE DATOS
# ==========================================
ARCHIVO_CHATS_PERMANENTE = "historial_chats.json"
ARCHIVO_USUARIOS = "usuarios.json"

def cargar_usuarios():
    if os.path.exists(ARCHIVO_USUARIOS):
        with open(ARCHIVO_USUARIOS, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def guardar_usuarios(datos_usuarios):
    with open(ARCHIVO_USUARIOS, "w", encoding="utf-8") as f:
        json.dump(datos_usuarios, f, indent=4, ensure_ascii=False)

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

def es_correo_valido(correo: str) -> bool:
    patron = r'^[a-zA-Z0-9._%+-]+@gmail\.com$'
    return bool(re.match(patron, correo.strip().lower()))

def enviar_email_otp(correo_destino, codigo_otp):
    smtp_server = st.secrets.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(st.secrets.get("SMTP_PORT", 587))
    smtp_user = st.secrets.get("SMTP_USER", "")
    smtp_password = st.secrets.get("SMTP_PASSWORD", "")

    if not smtp_user or not smtp_password:
        return False, "⚠️ No has configurado las credenciales de Gmail en los Secrets."

    try:
        msg = MIMEMultipart()
        msg['From'] = f"Isaac AI <{smtp_user}>"
        msg['To'] = correo_destino
        msg['Subject'] = f"{codigo_otp} - Tu código de verificación de Isaac AI"
        
        cuerpo_mensaje = f"""
        Hola,

        Tu código de verificación para ingresar a Isaac AI es:
        
        👉  {codigo_otp}  👈
        
        Si no solicitaste este código, ignora este mensaje.
        """
        msg.attach(MIMEText(cuerpo_mensaje, 'plain'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, correo_destino, msg.as_string())
        server.quit()
        
        return True, f"Correo enviado exitosamente a {correo_destino}."
    except Exception as e:
        return False, f"Error al enviar el correo: {e}"

def obtener_imagen_bytes(prompt_texto):
    prompt_encoded = urllib.parse.quote(prompt_texto)
    seed_random = random.randint(1, 999999)
    url = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width=1024&height=1024&seed={seed_random}&nologo=true"
    
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    with urllib.request.urlopen(req) as response:
        return response.read()

# ==========================================
# 🔐 GESTIÓN DE SESIÓN, AUTO-LOGIN Y REGISTRO
# ==========================================
db_usuarios = cargar_usuarios()

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.tipo_usuario = None  
    st.session_state.usuario_info = ""

if not st.session_state.autenticado and "user" in st.query_params:
    user_guardado = st.query_params["user"]
    if user_guardado in db_usuarios:
        nombre_u = db_usuarios[user_guardado].get("nombre", "Usuario")
        st.session_state.autenticado = True
        st.session_state.tipo_usuario = "Privilegiado"
        st.session_state.usuario_info = f"{nombre_u} ({user_guardado})"

if "paso_login" not in st.session_state:
    st.session_state.paso_login = "ingresar_correo"

if "otp_generado" not in st.session_state:
    st.session_state.otp_generado = None

if "datos_registro_temp" not in st.session_state:
    st.session_state.datos_registro_temp = {}

if not st.session_state.autenticado:
    st.title("🤖 Bienvenido a Isaac AI")
    
    opcion_acceso = st.radio("Selecciona tu método de acceso:", ["Ingresar / Registrarse con Gmail", "Acceder como Invitado"])
    
    if opcion_acceso == "Ingresar / Registrarse con Gmail":
        
        if st.session_state.paso_login == "ingresar_correo":
            st.write("### Acceso con Correo Gmail")
            
            correo = st.text_input("Introduce tu correo (@gmail.com):", placeholder="tu_correo@gmail.com")
            correo_limpio = correo.strip().lower()
            
            if st.button("Continuar", use_container_width=True):
                if es_correo_valido(correo_limpio):
                    st.session_state.correo_pendiente = correo_limpio
                    
                    if correo_limpio in db_usuarios and db_usuarios[correo_limpio].get("password"):
                        st.session_state.paso_login = "pedir_password"
                    else:
                        st.session_state.paso_login = "crear_perfil"
                    st.rerun()
                else:
                    st.error("Por favor ingresa una dirección válida terminada en @gmail.com")

        elif st.session_state.paso_login == "pedir_password":
            correo_user = st.session_state.correo_pendiente
            nombre_registrado = db_usuarios[correo_user].get("nombre", "Usuario")
            st.write(f"### Hola de nuevo, **{nombre_registrado}** 👋")
            
            password_input = st.text_input("Ingresa tu contraseña:", type="password")
            
            col_login, col_cambiar = st.columns([0.7, 0.3])
            
            with col_login:
                if st.button("Verificar e Ingresar", use_container_width=True):
                    if password_input == db_usuarios[correo_user]["password"]:
                        otp = str(random.randint(100000, 999999))
                        st.session_state.otp_generado = otp
                        st.session_state.datos_registro_temp = {
                            "correo": correo_user,
                            "nombre": nombre_registrado
                        }
                        
                        exito, msj = enviar_email_otp(correo_user, otp)
                        if exito:
                            st.session_state.paso_login = "verificar_codigo"
                            st.rerun()
                        else:
                            st.error(msj)
                    else:
                        st.error("Contraseña incorrecta.")
            
            with col_cambiar:
                if st.button("Cambiar Correo", use_container_width=True):
                    st.session_state.paso_login = "ingresar_correo"
                    st.rerun()

        elif st.session_state.paso_login == "crear_perfil":
            correo_user = st.session_state.correo_pendiente
            st.write(f"### Configura tu perfil para `{correo_user}`")
            
            nombre = st.text_input("Tu Nombre o Apodo:", placeholder="Ej. Isaac")
            password = st.text_input("Crea una Contraseña (Opcional, déjala vacía si prefieres entrar libre):", type="password")
            
            if st.button("Enviar Código a mi Gmail", use_container_width=True):
                if nombre.strip():
                    otp = str(random.randint(100000, 999999))
                    st.session_state.otp_generado = otp
                    st.session_state.datos_registro_temp = {
                        "correo": correo_user,
                        "nombre": nombre.strip(),
                        "password": password.strip()
                    }
                    
                    exito, msj = enviar_email_otp(correo_user, otp)
                    if exito:
                        st.session_state.paso_login = "verificar_codigo"
                        st.rerun()
                    else:
                        st.error(msj)
                else:
                    st.error("Por favor ingresa un nombre para continuar.")

        elif st.session_state.paso_login == "verificar_codigo":
            datos_temp = st.session_state.datos_registro_temp

            st.markdown(f"""
            <div class="caja-otp">
                📧 Enviamos un código de 6 dígitos a: <b>{datos_temp['correo']}</b><br>
                👤 Usuario: <b>{datos_temp['nombre']}</b>
            </div>
            """, unsafe_allow_html=True)

            st.info("Revisa tu bandeja de entrada o la carpeta de **Spam / Correo no deseado**.")
            codigo_ingresado = st.text_input("Ingresa el código de 6 dígitos:", max_chars=6)
            
            col_validar, col_volver = st.columns([0.7, 0.3])
            
            with col_validar:
                if st.button("Confirmar e Iniciar Sesión", use_container_width=True):
                    if codigo_ingresado.strip() == st.session_state.otp_generado:
                        correo_user = datos_temp["correo"]
                        db_usuarios[correo_user] = {
                            "nombre": datos_temp["nombre"],
                            "password": datos_temp.get("password", "")
                        }
                        guardar_usuarios(db_usuarios)
                        
                        st.query_params["user"] = correo_user
                        
                        st.session_state.autenticado = True
                        st.session_state.tipo_usuario = "Privilegiado"
                        st.session_state.usuario_info = f"{datos_temp['nombre']} ({correo_user})"
                        st.session_state.paso_login = "ingresar_correo"
                        st.success("¡Inicio de sesión exitoso!")
                        st.rerun()
                    else:
                        st.error("Código incorrecto. Verifica los números ingresados.")
            
            with col_volver:
                if st.button("Volver", use_container_width=True):
                    st.session_state.paso_login = "ingresar_correo"
                    st.rerun()

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
    api_key = st.secrets.get("GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
    return Groq(api_key=api_key)

client = conectar_groq()
MODELO_TEXTO = "llama-3.3-70b-versatile"

# ==========================================
# 🔄 HISTORIAL DE CHATS
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
# 💾 BARRA LATERAL
# ==========================================
with st.sidebar:
    st.write(f"### 👤 {st.session_state.usuario_info}")
    
    if st.button("➕ Nueva conversación", use_container_width=True):
        nuevo_id = f"chat_{int(datetime.now().timestamp())}"
        st.session_state.conversaciones[nuevo_id] = {"titulo": "Nueva Conversación", "historial": []}
        st.session_state.chat_actual_id = nuevo_id
        
        base_datos_chats[usuario_actual] = st.session_state.conversaciones
        guardar_todas_las_conversaciones(base_datos_chats)
        st.rerun()
        
    st.markdown("---")

    criterio_busqueda = st.text_input("🔍 Buscar conversación...", placeholder="Filtrar...")
    
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
    
    if st.button("🔄 Cambiar de Cuenta / Salir", use_container_width=True):
        st.query_params.clear()
        st.session_state.clear()
        st.rerun()

# ==========================================
# 💬 INTERFAZ PRINCIPAL DE CHAT
# ==========================================
chat_activo = st.session_state.conversaciones[st.session_state.chat_actual_id]
st.title(f"{chat_activo['titulo']}")

# Mostrar el historial de la conversación
for msg in chat_activo["historial"]:
    with st.chat_message(msg["role"]):
        if msg.get("type") == "image":
            b64_data = msg.get("b64")
            if b64_data:
                bytes_decodificados = base64.b64decode(b64_data)
                st.image(bytes_decodificados, caption=f"🖼️ {msg.get('caption', 'Imagen generada')}")
            else:
                st.image(msg.get("content", ""), caption=f"🖼️ {msg.get('caption', 'Imagen generada')}")
        else:
            st.markdown(msg["content"])

mensajes_enviados = sum(1 for m in chat_activo["historial"] if m["role"] == "user")
bloqueado_por_restriccion = st.session_state.tipo_usuario == "Invitado" and mensajes_enviados >= 5

if bloqueado_por_restriccion:
    st.error("⚠️ Límite del Modo Invitado alcanzado. Inicia sesión para continuar.")

if not bloqueado_por_restriccion:
    
    col_pro, col_img = st.columns([0.5, 0.5])
    with col_pro:
        modo_pro = st.toggle("⚡ Modo Pro (Alta precisión)", value=False, key="toggle_pro")
    with col_img:
        modo_imagen = st.toggle("🎨 Generar Imagen", value=False, key="toggle_imagen")

    if modo_imagen:
        texto_placeholder = "Escribe qué imagen deseas crear..."
    elif modo_pro:
        texto_placeholder = "Modo Pro activo: escribe tu consulta detallada..."
    else:
        texto_placeholder = "Escribe tu mensaje..."

    if prompt := st.chat_input(texto_placeholder):
        
        with st.chat_message("user"):
            st.markdown(prompt)
        chat_activo["historial"].append({"role": "user", "content": prompt, "type": "text"})
        
        if len(chat_activo["historial"]) == 1:
            chat_activo["titulo"] = prompt[:30].strip() + ("..." if len(prompt) > 30 else "")

        with st.chat_message("assistant"):
            
            # --- GENERAR IMAGEN EN BASE64 ---
            if modo_imagen:
                with st.spinner("🎨 Creando imagen con IA..."):
                    try:
                        bytes_img = obtener_imagen_bytes(prompt)
                        b64_str = base64.b64encode(bytes_img).decode("utf-8")
                        
                        st.image(bytes_img, caption=f"🖼️ {prompt}")
                        
                        chat_activo["historial"].append({
                            "role": "assistant",
                            "content": prompt,
                            "b64": b64_str,
                            "caption": prompt,
                            "type": "image"
                        })
                    except Exception as err:
                        st.error(f"Error al generar la imagen: {err}")
            
            # --- MODO TEXTO ---
            else:
                ahora = datetime.now()
                
                if modo_pro:
                    contexto_sistema = (
                        f"Eres Isaac AI en MODO PRO. Fecha actual: {ahora.strftime('%d/%m/%Y')}. "
                        "Ofrece respuestas minuciosas, con análisis profundo, explicaciones paso a paso y excelente estructuración."
                    )
                    max_tokens_val = 2000
                    temp_val = 0.2
                else:
                    contexto_sistema = (
                        f"Eres Isaac AI, una IA inteligente, rápida y directa. "
                        f"Fecha actual: {ahora.strftime('%d/%m/%Y')}."
                    )
                    max_tokens_val = 800
                    temp_val = 0.4
                
                mensajes_api = [{"role": "system", "content": contexto_sistema}]
                
                mensajes_texto = [m for m in chat_activo["historial"] if m.get("type", "text") == "text"]
                for m in mensajes_texto[-6:]:
                    role = m.get("role")
                    content_texto = str(m.get("content", ""))
                    if role in ["user", "assistant"] and content_texto.strip():
                        if mensajes_api[-1]["role"] == role:
                            mensajes_api[-1]["content"] += "\n" + content_texto
                        else:
                            mensajes_api.append({"role": role, "content": content_texto})

                try:
                    marcador_texto = st.empty()
                    texto_completo = ""
                    
                    stream = client.chat.completions.create(
                        model=MODELO_TEXTO,
                        messages=mensajes_api,
                        stream=True,
                        temperature=temp_val,
                        max_tokens=max_tokens_val
                    )
                    
                    for parte in stream:
                        contenido = parte.choices[0].delta.content if parte.choices and parte.choices[0].delta else None
                        if contenido:
                            texto_completo += contenido
                            marcador_texto.markdown(texto_completo + "▌")
                            time.sleep(0.005)
                            
                    marcador_texto.markdown(texto_completo)

                except Exception as e:
                    texto_completo = f"🚨 **Error de API:** {e}"
                    st.markdown(texto_completo)
                    
                chat_activo["historial"].append({"role": "assistant", "content": texto_completo, "type": "text"})
    
        base_datos_chats[usuario_actual] = st.session_state.conversaciones
        guardar_todas_las_conversaciones(base_datos_chats)
        st.rerun()
