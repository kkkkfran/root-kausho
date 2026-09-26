"""
=============================================================================
Script: register_profile_widget.py
Propósito: Configurar y registrar un Widget de Perfil / Tablero para la aplicación
           de Discord utilizando OAuth2 (User Access Token) y la API HTTP v10.
=============================================================================

Flujo de Ejecución:
1. Servidor Local Temporal:
   - Levanta un servidor HTTP local en http://localhost:8000/callback.
2. Autorización OAuth2 del Usuario:
   - Abre automáticamente el navegador con la URL oficial de autorización:
     https://discord.com/oauth2/authorize?client_id=...&scope=application_identities.write...
3. Captura del Código y Canje de Token:
   - Captura el 'code' devuelto en el callback.
   - Realiza la petición POST a https://discord.com/api/v10/oauth2/token
     usando CLIENT_SECRET para obtener el User Access Token ('Bearer').
4. Envío del Payload de Perfil:
   - Envía la petición PATCH con encabezado 'Authorization: Bearer <access_token>'
     registrando la tarjeta con Katiusca (Katy), Chubaca y las redes sociales.
5. Confirmación y Pasos en Discord:
   - Muestra confirmación clara en consola y guía para activar el widget.
=============================================================================
"""

import os
import sys
import json
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import requests
from dotenv import load_dotenv

# Asegurar codificacion UTF-8 para consolas de Windows (evita UnicodeEncodeError)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Cargar variables de entorno desde .env
load_dotenv()

# ==========================================
# CONFIGURACIÓN Y CREDENCIALES
# ==========================================
# ID de la aplicación de Discord
APPLICATION_ID = os.getenv("DISCORD_APPLICATION_ID", "1508312731227258961").strip()

# Client Secret de la aplicación (para intercambio OAuth2)
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", os.getenv("CLIENT_SECRET", "")).strip()

# Token del Bot (opcional, para consultar assets en el portal)
BOT_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()

# ID de usuario del Owner
TARGET_USER_ID = os.getenv("BOT_OWNER_ID", "453319707743748106").strip()

# Configuración del servidor OAuth2 local
LOCAL_HOST = "localhost"
LOCAL_PORT = 8000
REDIRECT_URI = f"http://{LOCAL_HOST}:{LOCAL_PORT}/callback"
OAUTH_SCOPE = "application_identities.write"

# Identificador interno del proveedor de identidad
PROVIDER_ISSUED_USER_ID = "owner"

# API Base de Discord (v10)
DISCORD_API_BASE = "https://discord.com/api/v10"


# Variable global y evento para sincronizar la captura del código OAuth2
oauth_code_result = {"code": None, "error": None}
code_event = threading.Event()


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Manejador HTTP que recibe el callback de OAuth2 de Discord."""

    def log_message(self, format, *args):
        # Silenciar logs estándar del servidor HTTP para mantener la consola limpia
        return

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/callback":
            params = parse_qs(parsed.query)

            if "code" in params:
                code = params["code"][0]
                oauth_code_result["code"] = code
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()

                html_success = """
                <!DOCTYPE html>
                <html lang="es">
                <head>
                    <meta charset="UTF-8">
                    <title>Autorización Exitosa - root-kaush</title>
                    <style>
                        body {
                            background-color: #202225;
                            color: #f6f6f7;
                            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            height: 100vh;
                            margin: 0;
                        }
                        .card {
                            background-color: #2f3136;
                            padding: 40px;
                            border-radius: 12px;
                            box-shadow: 0 8px 24px rgba(0,0,0,0.4);
                            text-align: center;
                            max-width: 480px;
                        }
                        h1 { color: #5865F2; margin-top: 0; }
                        p { font-size: 16px; line-height: 1.5; color: #dcddde; }
                        .badge {
                            background-color: #5865F2;
                            color: white;
                            padding: 6px 14px;
                            border-radius: 20px;
                            font-size: 14px;
                            display: inline-block;
                            margin-top: 15px;
                        }
                    </style>
                </head>
                <body>
                    <div class="card">
                        <h1>¡Autorización Exitosa!</h1>
                        <p>Discord ha verificado tu identidad correctamente.</p>
                        <p>Ya puedes volver a la consola de comandos; el script completará el registro del widget automáticamente.</p>
                        <div class="badge">Puedes cerrar esta pestaña</div>
                    </div>
                </body>
                </html>
                """
                self.wfile.write(html_success.encode("utf-8"))
                code_event.set()
                return

            elif "error" in params:
                error = params["error"][0]
                desc = params.get("error_description", [""])[0]
                oauth_code_result["error"] = f"{error}: {desc}"
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()

                html_error = f"""
                <!DOCTYPE html>
                <html>
                <body style="background:#202225; color:#f04747; font-family:sans-serif; text-align:center; padding:50px;">
                    <h1>Error de Autorización</h1>
                    <p>{error}: {desc}</p>
                </body>
                </html>
                """
                self.wfile.write(html_error.encode("utf-8"))
                code_event.set()
                return

        # Cualquier otra ruta
        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"Ruta no encontrada")


def check_local_assets() -> dict:
    """Inspecciona la carpeta local de assets de Discord."""
    base_dir = Path(__file__).resolve().parent
    assets_dir = base_dir / "assets" / "discord_assets"

    found = {}
    print("\n" + "=" * 65)
    print(" 1. Inspección de carpeta local de assets")
    print("=" * 65)
    print(f"Buscando en: {assets_dir}")

    if not assets_dir.exists():
        desktop_dir = Path.home() / "Desktop" / "imagenes" / "discord_assets"
        if desktop_dir.exists():
            assets_dir = desktop_dir
            print(f"Ruta alternativa encontrada: {assets_dir}")

    if assets_dir.exists():
        for file in assets_dir.iterdir():
            if file.is_file() and file.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                key = file.stem.lower()
                size_kb = file.stat().st_size / 1024
                found[key] = {
                    "path": str(file),
                    "size_kb": f"{size_kb:.1f} KB",
                    "filename": file.name,
                }
                print(f" [OK] Asset local detectado: clave='{key}' | archivo='{file.name}' ({size_kb:.1f} KB)")
    else:
        print(" [!] No se encontró la carpeta de assets locales.")

    return found


def fetch_application_assets() -> list:
    """Consulta los assets registrados en el portal usando el BOT_TOKEN si está disponible."""
    if not BOT_TOKEN:
        return []

    url = f"{DISCORD_API_BASE}/applications/{APPLICATION_ID}/assets"
    print("\n" + "=" * 65)
    print(" 2. Consultando assets registrados en Discord")
    print("=" * 65)
    print(f"GET {url}")

    try:
        headers = {
            "Authorization": f"Bot {BOT_TOKEN}",
            "Content-Type": "application/json",
        }
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            assets = res.json()
            print(f" [OK] Código HTTP {res.status_code}: {len(assets)} asset(s) en Discord Developer Portal.")
            for item in assets:
                print(f"      - ID: {item.get('id')} | Clave: '{item.get('name')}' | Tipo: {item.get('type')}")
            return assets
        else:
            print(f" [!] Código HTTP {res.status_code}: {res.text}")
            return []
    except requests.RequestException as e:
        print(f" [ERROR] Error al consultar assets: {e}")
        return []


def start_local_server() -> HTTPServer:
    """Inicia el servidor HTTP local en un hilo secundario."""
    server = HTTPServer((LOCAL_HOST, LOCAL_PORT), OAuthCallbackHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    return server


def obtain_user_access_token(client_secret: str) -> str | None:
    """
    Inicia el flujo OAuth2 con navegador y servidor local,
    intercambia el 'code' por un 'access_token' de usuario (Bearer).
    """
    print("\n" + "=" * 65)
    print(" 3. Autenticación OAuth2 de Usuario (Bearer Token)")
    print("=" * 65)

    # Iniciar servidor local
    server = start_local_server()
    print(f" [OK] Servidor local temporal activo en http://{LOCAL_HOST}:{LOCAL_PORT}/callback")

    # Construir URL de autorización
    auth_url = (
        f"https://discord.com/oauth2/authorize"
        f"?client_id={APPLICATION_ID}"
        f"&response_type=code"
        f"&scope={OAUTH_SCOPE}"
        f"&redirect_uri=http%3A%2F%2F{LOCAL_HOST}%3A{LOCAL_PORT}%2Fcallback"
    )

    print("\n Abriendo automáticamente el navegador para autorizar:")
    print(f" -> {auth_url}\n")
    print(" (Si tu navegador no se abre automáticamente, copia y pega el enlace anterior en tu navegador)")

    # Abrir navegador
    try:
        webbrowser.open(auth_url)
    except Exception as e:
        print(f" [!] No se pudo abrir automáticamente el navegador: {e}")

    print(" Esperando autorización en el navegador...")
    # Esperar hasta 120 segundos a que el usuario autorice
    got_code = code_event.wait(timeout=120)

    server.shutdown()
    server.server_close()

    if not got_code or not oauth_code_result["code"]:
        error_msg = oauth_code_result.get("error") or "Tiempo de espera agotado sin recibir el código."
        print(f"\n [ERROR] Falló la captura del código OAuth2: {error_msg}")
        return None

    auth_code = oauth_code_result["code"]
    print(f" [OK] ¡Código de autorización recibido correctamente!")

    # Intercambiar código por token (POST /oauth2/token)
    token_url = f"{DISCORD_API_BASE}/oauth2/token"
    token_data = {
        "client_id": APPLICATION_ID,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    print(f"\n Solicitando User Access Token a: POST {token_url}")
    try:
        token_res = requests.post(token_url, data=token_data, headers=headers, timeout=12)
        if token_res.status_code == 200:
            token_json = token_res.json()
            access_token = token_json.get("access_token")
            token_type = token_json.get("token_type", "Bearer")
            scope_granted = token_json.get("scope", "")
            print(f" [OK] Código HTTP {token_res.status_code}: Token de acceso obtenido exitosamente.")
            print(f"      Tipo: {token_type} | Scope concedido: {scope_granted}")
            return access_token
        else:
            print(f" [ERROR HTTP {token_res.status_code}] Fallo en el intercambio de token:")
            print(token_res.text)
            return None
    except requests.RequestException as ex:
        print(f" [EXCEPCIÓN DE RED] Error al conectar con /oauth2/token: {ex}")
        return None


def build_widget_payload() -> dict:
    """Construye la estructura JSON del widget para el perfil."""
    return {
        "username": "kkkkfran",
        "metadata": {
            "title": "Tablero Personal - kkkkfran",
            "pet_primary": "Katiusca (Katy)",
            "pet_secondary": "Chubaca",
            "asset_katy": "foto_katy",
            "asset_chubaca": "chubaca",
            "instagram_url": "https://instagram.com/kkkkfran",
            "tiktok_url": "https://tiktok.com/@kkkkfran",
            "youtube_url": "https://youtube.com/@kaushitoo",
        },
        "data": {
            "primary": {
                "rank_name": "Katy & Chubaca",
                "season": "1",
            },
            "dynamic": [
                {
                    "type": 1,
                    "name": "Mascota Principal",
                    "value": "Katiusca (Katy)",
                },
                {
                    "type": 1,
                    "name": "Segunda Mascota",
                    "value": "Chubaca",
                },
                {
                    "type": 1,
                    "name": "Instagram",
                    "value": "@kkkkfran",
                },
                {
                    "type": 1,
                    "name": "TikTok",
                    "value": "@kkkkfran",
                },
                {
                    "type": 1,
                    "name": "YouTube",
                    "value": "@kaushitoo",
                },
            ],
        },
    }


def send_profile_patch(access_token: str) -> bool:
    """
    Envía la petición PATCH con el User Access Token ('Bearer <token>')
    para registrar o actualizar el perfil de identidad de la aplicación.
    """
    endpoint = f"/applications/{APPLICATION_ID}/users/{TARGET_USER_ID}/identities/{PROVIDER_ISSUED_USER_ID}/profile"
    full_url = f"{DISCORD_API_BASE}{endpoint}"

    payload = build_widget_payload()
    headers = {
        "Authorization": f"Bearer {access_token.strip()}",
        "Content-Type": "application/json",
        "User-Agent": f"RootBot-ProfileWidget/1.0 (AppID: {APPLICATION_ID})",
    }

    print("\n" + "=" * 65)
    print(" 4. Registrando Widget de Perfil / Tablero en Discord API (v10)")
    print("=" * 65)
    print(f"Llamando a: PATCH {full_url}")
    print("Encabezado de Autorización: Bearer [ACCESS_TOKEN]")
    print("Payload enviado:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print("-" * 65)

    try:
        res = requests.patch(full_url, headers=headers, json=payload, timeout=15)
        status_code = res.status_code
        print(f"Respuesta HTTP recibida: {status_code}")

        # Intentar ruta alternativa con @me si el ID específico devolviera 404
        if status_code == 404:
            alt_endpoint = f"/applications/{APPLICATION_ID}/users/@me/identities/{PROVIDER_ISSUED_USER_ID}/profile"
            alt_url = f"{DISCORD_API_BASE}{alt_endpoint}"
            print(f" [REINTENTO] Probando endpoint alternativo @me: PATCH {alt_url}")
            res = requests.patch(alt_url, headers=headers, json=payload, timeout=15)
            status_code = res.status_code
            print(f"Respuesta HTTP recibida: {status_code}")

        if status_code in (200, 201, 204):
            print("\n" + "★" * 65)
            print(" ¡ÉXITO TOTAL! EL WIDGET DE PERFIL HA SIDO REGISTRADO EXITOSAMENTE")
            print("★" * 65)
            if res.text.strip():
                try:
                    data = res.json()
                    print("Detalle de respuesta de Discord:")
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                except json.JSONDecodeError:
                    print(f"Cuerpo: {res.text}")
            return True
        else:
            print(f"\n [ERROR HTTP {status_code}] Discord devolvió una respuesta con error.")
            try:
                err_data = res.json()
                print("Mensaje JSON devuelto por Discord para depuración:")
                print(json.dumps(err_data, indent=2, ensure_ascii=False))
            except json.JSONDecodeError:
                print(f"Respuesta bruta: {res.text}")
            return False

    except requests.RequestException as ex:
        print(f"\n [EXCEPCIÓN DE RED] Error durante la llamada PATCH: {ex}")
        return False


def print_discord_instructions():
    """Muestra instrucciones claras tras el registro."""
    print("\n" + "=" * 65)
    print(" GUIA: ACTIVAR EL WIDGET EN TU PERFIL DE DISCORD")
    print("=" * 65)
    print("1. En Discord Developer Portal (https://discord.com/developers/applications):")
    print(f"   - Selecciona tu aplicación: 'root-kaush' (ID: {APPLICATION_ID})")
    print("   - Asegúrate de haber subido 'katy.png' (clave: foto_katy) y 'chubaca.png' (clave: chubaca)")
    print("     en la pestaña 'Rich Presence' -> 'Art Assets'.")
    print()
    print("2. En tu Discord (Escritorio o Navegador):")
    print("   - Entra a Ajustes de usuario (icono de engranaje abajo a la izquierda).")
    print("   - Haz clic en 'Perfiles'.")
    print("   - Desplázate hacia abajo hasta la sección 'Widgets de perfil'.")
    print("   - Haz clic en 'Agregar widgets' y activa la tarjeta de tu aplicación.")
    print("=" * 65 + "\n")


def main():
    print("=================================================================")
    print("   CONFIGURACIÓN DE WIDGET DE PERFIL (OAUTH2 USER TOKEN)         ")
    print("=================================================================")
    print(f"APPLICATION_ID : {APPLICATION_ID}")
    print(f"TARGET_USER_ID : {TARGET_USER_ID}")
    print(f"REDIRECT_URI   : {REDIRECT_URI}")
    print(f"SCOPE          : {OAUTH_SCOPE}")

    # Verificar Client Secret
    client_secret = CLIENT_SECRET
    if not client_secret:
        print("\n [!] No se encontró DISCORD_CLIENT_SECRET en tu archivo .env.")
        print("     Puedes encontrarlo en: Discord Developer Portal -> Applications -> [Tu App] -> OAuth2 -> Client Secret.")
        try:
            client_secret = input(" Introduce tu DISCORD_CLIENT_SECRET aquí: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nOperación cancelada.")
            sys.exit(1)

        if not client_secret:
            print(" [ERROR] El Client Secret es obligatorio para intercambiar el token OAuth2.")
            sys.exit(1)

    # 1. Comprobar assets locales
    check_local_assets()

    # 2. Comprobar assets en la nube de Discord (si hay bot token)
    fetch_application_assets()

    # 3. Flujo OAuth2 interactivo para obtener Bearer token
    access_token = obtain_user_access_token(client_secret)
    if not access_token:
        print("\n [ERROR] No se pudo obtener el User Access Token. Finalizando.")
        sys.exit(1)

    # 4. Enviar PATCH con Authorization: Bearer <access_token>
    success = send_profile_patch(access_token)

    # 5. Imprimir instrucciones finales
    if success:
        print_discord_instructions()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
