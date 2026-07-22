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
    """
    Intenta enviar correo si hay credenciales SMTP en secrets.
    Si no las hay, activa el modo de prueba (gratis y visual en pantalla).
    """
    smtp_server = st.secrets.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(st.secrets.get("SMTP_PORT", 587))
    smtp_user = st.secrets.get("SMTP_USER", "")
    smtp_password = st.secrets.get("SMTP_PASSWORD", "")

    if smtp_user and smtp_password:
        try:
            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = correo_destino
            msg['Subject'] = f"{codigo_otp} es tu código de verificación para Isaac AI"
            
            cuerpo = f"Tu código de acceso de 6 dígitos es: {codigo_otp}"
            msg.attach(MIMEText(cuerpo, 'plain'))

            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, correo_destino, msg.as_string())
            server.quit()
            return True, "Correo enviado correctamente a tu bandeja de entrada.", False
        except Exception as e:
            return False, f"Error SMTP: {e}", True
    else:
        # Modo de prueba 100% gratuito sin enviar correos reales aún
        return True, "Modo de prueba activo (Sin SMTP configurado)", True

# ==========================================
# 🔐 GESTIÓN DE SESIÓN Y REGISTRO/LOGIN
# ==========================================
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.tipo_usuario = None  
    st.session_state.usuario_info = ""

if "paso_login" not in st.session_state:
    st.session_state.paso_login = "ingresar_correo"

if "otp_generado" not in st.session_state:
    st.session_state.otp_generado = None

if "datos_registro_temp" not in st.session_state:
    st.session_state.datos_registro_temp = {}

db_usuarios = cargar_usuarios()

if not st.session_state.autenticado:
    st.title("🤖 Bienvenido a Isaac AI")
    
    opcion_acceso = st.radio("Selecciona tu método de acceso:", ["Ingresar / Registrarse con Gmail", "Acceder como Invitado"])
    
    if opcion_acceso == "Ingresar / Registrarse con Gmail":
        
        # PASO 1: Correo electrónico
        if st.session_state.paso_login == "ingresar_correo":
            st.write("### Acceso con Correo Gmail")
            
            correo = st.text_input("Introduce tu correo (@gmail.com):", placeholder="ejemplo@gmail.com")
            correo_limpio = correo.strip().lower()
            
            if st.button("Continuar", use_container_width=True):
                if es_correo_valido(correo_limpio):
                    st.session_state.correo_pendiente = correo_limpio
                    
                    # Verificar si existe en la base de usuarios registrada
                    if correo_limpio in db_usuarios and db_usuarios[correo_limpio].get("password"):
                        st.session_state.paso_login = "pedir_password"
                    else:
                        st.session_state.paso_login = "crear_perfil"
                    st.rerun()
                else:
                    st.error("Por favor ingresa un correo terminado en @gmail.com")

        # PASO 2A: Si el usuario ya existe y configuró contraseña previamente
        elif st.session_state.paso_login == "pedir_password":
            correo_user = st.session_state.correo_pendiente
            nombre_registrado = db_usuarios[correo_user].get("nombre", "Usuario")
            st.write(f"### Hola de nuevo, **{nombre_registrado}** 👋")
            
            password_input = st.text_input("Ingresa tu contraseña:", type="password")
            
            col_login, col_cambiar = st.columns([0.7, 0.3])
            
            with col_login:
                if st.button("Iniciar Sesión", use_container_width=True):
                    if password_input == db_usuarios[correo_user]["password"]:
                        otp = str(random.randint(100000, 999999))
                        st.session_state.otp_generado = otp
                        st.session_state.datos_registro_temp = {
                            "correo": correo_user,
                            "nombre": nombre_registrado
                        }
                        st.session_state.paso_login = "verificar_codigo"
                        st.rerun()
                    else:
                        st.error("Contraseña incorrecta.")
            
            with col_cambiar:
                if st.button("Cambiar Correo", use_container_width=True):
                    st.session_state.paso_login = "ingresar_correo"
                    st.rerun()

        # PASO 2B: Si el correo es nuevo o no tiene contraseña registrada
        elif st.session_state.paso_login == "crear_perfil":
            correo_user = st.session_state.correo_pendiente
            st.write(f"### Configura tu perfil para `{correo_user}`")
            st.caption("Asigna tu nombre y una contraseña personal para proteger tu cuenta.")
            
            nombre = st.text_input("Tu Nombre o Apodo:", placeholder="Ej. Isaac")
            password = st.text_input("Crea una Contraseña (Opcional, déjala en blanco si prefieres sin clave):", type="password")
            
            if st.button("Enviar Código por Gmail", use_container_width=True):
                if nombre.strip():
                    otp = str(random.randint(100000, 999999))
                    st.session_state.otp_generado = otp
                    st.session_state.datos_registro_temp = {
                        "correo": correo_user,
                        "nombre": nombre.strip(),
                        "password": password.strip()
                    }
                    st.session_state.paso_login = "verificar_codigo"
                    st.rerun()
                else:
                    st.error("Por favor ingresa tu nombre.")

        # PASO 3: Verificación del código enviado por correo
        elif st.session_state.paso_login == "verificar_codigo":
            datos_temp = st.session_state.datos_registro_temp
            exito_smtp, msj_smtp, es_modo_dev = enviar_email_otp(
                datos_temp["correo"], 
                st.session_state.otp_generado
            )

            st.markdown(f"""
            <div class="caja-otp">
                📧 Código de verificación para: <b>{datos_temp['correo']}</b><br>
                👤 Usuario: <b>{datos_temp['nombre']}</b>
            </div>
            """, unsafe_allow_html=True)

            if es_modo_dev:
                st.info(f"🔑 **Código de prueba:** `{st.session_state.otp_generado}` *(Cópialo e ingrésalo abajo)*")
            else:
                st.success("Se ha enviado un código a tu cuenta de Gmail.")
            
            codigo_ingresado = st.text_input("Ingresa el código de 6 dígitos:", max_chars=6)
            
            col_validar, col_volver = st.columns([0.7, 0.3])
            
            with col_validar:
                if st.button("Confirmar e Iniciar Sesión", use_container_width=True):
                    if codigo_ingresado.strip() == st.session_state.otp_generado:
                        # Guardar perfil de usuario
                        correo_user = datos_temp["correo"]
                        db_usuarios[correo_user] = {
                            "nombre": datos_temp["nombre"],
                            "password": datos_temp.get("password", "")
                        }
                        guardar_usuarios(db_usuarios)
                        
                        st.session_state.autenticado = True
                        st.session_state.tipo_usuario = "Privilegiado"
                        st.session_state.usuario_info = f"{datos_temp['nombre']} ({correo_user})"
                        st.session_state.paso_login = "ingresar_correo"
                        st.success("¡Bienvenido!")
                        st.rerun()
                    else:
                        st.error("El código ingresado es incorrecto.")
            
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
    if st.button("🔒 Cerrar Sesión", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# ==========================================
# 💬 INTERFAZ PRINCIPAL DE CHAT
# ==========================================
chat_activo = st.session_state.conversaciones[st.session_state.chat_actual_id]
st.title(f"{chat_activo['titulo']}")

for msg in chat_activo["historial"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

mensajes_enviados = sum(1 for m in chat_activo["historial"] if m["role"] == "user")
bloqueado_por_restriccion = st.session_state.tipo_usuario == "Invitado" and mensajes_enviados >= 5

if bloqueado_por_restriccion:
    st.error("⚠️ Límite del Modo Invitado alcanzado. Inicia sesión para continuar.")

if not bloqueado_por_restriccion:
    if prompt := st.chat_input("Escribe tu pregunta..."):
        
        with st.chat_message("user"):
            st.markdown(prompt)
        chat_activo["historial"].append({"role": "user", "content": prompt})
        
        if len(chat_activo["historial"]) == 1:
            chat_activo["titulo"] = prompt[:30].strip() + ("..." if len(prompt) > 30 else "")

        with st.chat_message("assistant"):
            ahora = datetime.now()
            contexto_sistema = f"Eres Isaac AI, una IA inteligente y directa. Fecha actual: {ahora.strftime('%d/%m/%Y')}."
            
            mensajes_api = [{"role": "system", "content": contexto_sistema}]
            
            for m in chat_activo["historial"][-5:]:
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
                texto_completo = f"🚨 **Error de API:** {e}"
                st.markdown(texto_completo)
                
            chat_activo["historial"].append({"role": "assistant", "content": texto_completo})
    
        base_datos_chats[usuario_actual] = st.session_state.conversaciones
        guardar_todas_las_conversaciones(base_datos_chats)
        st.rerun()
