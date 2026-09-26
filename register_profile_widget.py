"""
=============================================================================
Script: register_profile_widget.py
Propósito: Configurar y registrar un Widget de Perfil / Tablero para la aplicación
           de Discord utilizando los endpoints oficiales de la API HTTP (v10).
=============================================================================

Pasos y Flujo de Ejecución en Discord:
1. Autenticación y Verificación de Assets:
   - El script consulta 'GET /applications/{APPLICATION_ID}/assets' para verificar
     si las claves de assets ('chubaca', 'foto_katy') ya están registradas en el
     Discord Developer Portal.
   - También revisa la carpeta local 'assets/discord_assets/' ('chubaca.png', 'katy.png').

2. Endpoint de Perfil de Identidad (Game Stats / Profile Widget):
   - 'PATCH https://discord.com/api/v10/applications/{APPLICATION_ID}/users/{USER_ID}/identities/{PROVIDER_ID}/profile'
   - Este endpoint registra los metadatos y campos dinámicos de la tarjeta de perfil
     (mascotas Katiusca/Chubaca y enlaces a redes sociales).

3. Pasos a seguir tras la ejecución:
   a) En Discord Developer Portal (https://discord.com/developers/applications):
      - Selecciona tu aplicación (root-kaush, ID: 1508312731227258961).
      - Ve a "Rich Presence" -> "Art Assets".
      - Sube las imágenes de la carpeta 'assets/discord_assets/' asignando como clave:
        'chubaca' y 'foto_katy' (o 'katy').
   b) En el cliente de Discord (versión de escritorio o navegador):
      - Ve a Ajustes de usuario (icono de engranaje) -> Perfiles -> Widgets de perfil.
      - Añade el widget asociado a tu aplicación para que se muestre en tu perfil.
=============================================================================
"""

import os
import sys
import json
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

# Cargar variables de entorno si existe archivo .env
load_dotenv()

# ==========================================
# CREDENCIALES Y CONFIGURACIÓN PRINCIPAL
# ==========================================
# ID de la aplicación de Discord (Application ID)
APPLICATION_ID = os.getenv("DISCORD_APPLICATION_ID", "1508312731227258961")

# Token de autenticación del Bot (leído de forma segura desde .env para evitar filtraciones)
BOT_TOKEN = os.getenv("DISCORD_TOKEN", "")

# ID de usuario destino (Owner o usuario a quien se le asocia el widget)
TARGET_USER_ID = os.getenv("BOT_OWNER_ID", "1299297166778568801")

# Identificador interno del proveedor para la identidad (por defecto 'default' o 'owner')
PROVIDER_ISSUED_USER_ID = "owner"

# Base URL de la API de Discord (v10)
DISCORD_API_BASE = "https://discord.com/api/v10"


def get_headers() -> dict:
    """Retorna las cabeceras requeridas con autorización Bot."""
    return {
        "Authorization": f"Bot {BOT_TOKEN.strip()}",
        "Content-Type": "application/json",
        "User-Agent": f"RootBot-ProfileWidget/1.0 (AppID: {APPLICATION_ID})",
    }


def check_local_assets() -> dict:
    """Inspecciona la carpeta local de assets de Discord."""
    base_dir = Path(__file__).resolve().parent
    assets_dir = base_dir / "assets" / "discord_assets"

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    found = {}
    print("\n" + "=" * 65)
    print(" 1. Inspeccion de carpeta local de assets")
    print("=" * 65)
    print(f"Buscando en: {assets_dir}")

    if not assets_dir.exists():
        # Fallback a Desktop/imagenes/discord_assets si no existiera en el repo
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
        print(" [!] No se encontró el directorio de assets locales.")

    return found


def fetch_application_assets() -> list:
    """
    Endpoint: GET /applications/{APPLICATION_ID}/assets
    Obtiene la lista de assets de arte registrados en la aplicación de Discord.
    """
    url = f"{DISCORD_API_BASE}/applications/{APPLICATION_ID}/assets"
    print("\n" + "=" * 65)
    print(f" 2. Consultando assets registrados en Discord")
    print("=" * 65)
    print(f"GET {url}")

    try:
        response = requests.get(url, headers=get_headers(), timeout=10)
        if response.status_code == 200:
            assets = response.json()
            print(f" [OK] Código HTTP {response.status_code}: {len(assets)} asset(s) encontrados en la nube de Discord.")
            for item in assets:
                print(f"      - ID: {item.get('id')} | Nombre/Clave: '{item.get('name')}' | Tipo: {item.get('type')}")
            return assets
        else:
            print(f" [!] Código HTTP {response.status_code}: {response.text}")
            return []
    except requests.RequestException as e:
        print(f" [ERROR] Error de conexión al consultar assets: {e}")
        return []


def build_widget_payload() -> dict:
    """
    Construye la estructura de datos del Widget de perfil / Tablero.
    Incluye:
    - Mascota: Katiusca (Katy) y Chubaca con claves de assets ('foto_katy' / 'chubaca').
    - Redes Sociales con enlaces directos:
      * Instagram: @kkkkfran (https://instagram.com/kkkkfran)
      * TikTok: @kkkkfran (https://tiktok.com/@kkkkfran)
      * YouTube: @kaushitoo (https://youtube.com/@kaushitoo)
    """
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


def register_profile_widget() -> bool:
    """
    Endpoint: PATCH /applications/{APPLICATION_ID}/users/{TARGET_USER_ID}/identities/{PROVIDER_ISSUED_USER_ID}/profile
    Registra/actualiza el perfil de identidad y los datos del widget para el usuario.
    """
    endpoint = f"/applications/{APPLICATION_ID}/users/{TARGET_USER_ID}/identities/{PROVIDER_ISSUED_USER_ID}/profile"
    full_url = f"{DISCORD_API_BASE}{endpoint}"

    payload = build_widget_payload()

    print("\n" + "=" * 65)
    print(" 3. Registrando Widget de Perfil / Tablero en Discord API (v10)")
    print("=" * 65)
    print(f"Llamando a: PATCH {full_url}")
    print("Payload enviado:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print("-" * 65)

    try:
        response = requests.patch(
            full_url,
            headers=get_headers(),
            json=payload,
            timeout=12,
        )

        status_code = response.status_code
        print(f"Respuesta HTTP recibida: {status_code}")

        # Comprobación de éxito (200 OK, 201 Created o 204 No Content)
        if status_code in (200, 201, 204):
            print("\n [ÉXITO] ¡El widget de perfil / tablero fue registrado satisfactoriamente!")
            if response.text.strip():
                try:
                    data = response.json()
                    print("Detalle de respuesta de Discord:")
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                except json.JSONDecodeError:
                    print(f"Cuerpo: {response.text}")
            return True
        else:
            print(f"\n [ERROR HTTP {status_code}] Discord rechazó o devolvió un aviso en la petición.")
            try:
                error_json = response.json()
                print("Mensaje JSON de depuración devuelto por Discord:")
                print(json.dumps(error_json, indent=2, ensure_ascii=False))

                # Ayuda contextual según el código devuelto por Discord
                code = error_json.get("code")
                if status_code == 403 or code in (50025, 40001):
                    print("\n > NOTA DE AUTORIZACIÓN (OAuth2):")
                    print("   El endpoint de perfil de identidad requiere que el usuario autorice previamente")
                    print("   la aplicación con el scope 'application_identities.write'.")
                    print("   Enlace de autorización OAuth2 sugerido:")
                    print(f"   https://discord.com/oauth2/authorize?client_id={APPLICATION_ID}&scope=application_identities.write&response_type=code")
            except json.JSONDecodeError:
                print(f"Respuesta sin formato JSON: {response.text}")

            return False

    except requests.RequestException as ex:
        print(f"\n [EXCEPCIÓN DE RED] Error durante la llamada HTTP: {ex}")
        return False


def print_discord_instructions():
    """Muestra instrucciones claras para verificar y activar el widget en Discord."""
    print("\n" + "=" * 65)
    print(" GUIA: PASOS A SEGUIR EN DISCORD TRAS LA EJECUCION")
    print("=" * 65)
    print("1. Subir Arte a Discord Developer Portal:")
    print("   - Entra a: https://discord.com/developers/applications")
    print(f"   - Selecciona tu aplicacion: 'root-kaush' (ID: {APPLICATION_ID})")
    print("   - En el menu izquierdo, dirigete a 'Rich Presence' -> 'Art Assets'.")
    print("   - Sube 'katy.png' con el nombre de clave: foto_katy (o katy).")
    print("   - Sube 'chubaca.png' con el nombre de clave: chubaca.")
    print("   - Guarda los cambios.")
    print()
    print("2. Activar el Widget en tu Perfil de Discord:")
    print("   - Abre Discord en tu PC (Escritorio o Navegador).")
    print("   - Ve a 'Ajustes de usuario' (icono de engranaje abajo a la izquierda).")
    print("   - Haz clic en 'Perfiles' -> desplazate a 'Widgets de perfil'.")
    print("   - Pulsa 'Agregar widgets' y selecciona el tablero de tu bot.")
    print("=" * 65 + "\n")


def main():
    print("=================================================================")
    print("     INICIALIZANDO CONFIGURACIÓN DE WIDGET DE PERFIL DISCORD     ")
    print("=================================================================")
    if not BOT_TOKEN:
        print("\n [ERROR] No se encontro DISCORD_TOKEN configurado en el entorno ni en .env.")
        print(" Asegurate de definir DISCORD_TOKEN en tu archivo .env.")
        sys.exit(1)

    print(f"APPLICATION_ID : {APPLICATION_ID}")
    print(f"BOT_TOKEN      : {BOT_TOKEN[:10]}...{BOT_TOKEN[-6:] if len(BOT_TOKEN) > 16 else ''}")
    print(f"TARGET_USER_ID : {TARGET_USER_ID}")

    # 1. Verificar assets locales
    check_local_assets()

    # 2. Consultar assets en la API de Discord
    fetch_application_assets()

    # 3. Registrar el widget mediante PATCH a la API HTTP interna v10
    success = register_profile_widget()

    # 4. Mostrar guía de pasos en Discord
    print_discord_instructions()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
