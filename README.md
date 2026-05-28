# Bot oficial de Discord

Bot modular para el servidor oficial. Cada funcion vive en su propia zona dentro de `root_bot/features`.

## Estructura

```text
bot.py                    # Arranque para local y Railway
root_bot/config.py        # Variables de entorno y defaults
root_bot/client.py        # Cliente del bot y sincronizacion de comandos
root_bot/features/
  welcome.py              # Bienvenida de miembros
  rules.py                # Comando /reglas
  about.py                # Comando /servidor y enlace a tickets
  tickets.py              # Panel, creacion y cierre de tickets
assets/                   # Imagenes opcionales para embeds
```

## Requisitos

- Python 3.10 o superior
- Un bot creado en el Discord Developer Portal
- Scope `bot`
- Scope `applications.commands` para comandos slash
- Intent **Server Members Intent** activado para la bienvenida

## Instalacion

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Configuracion

Edita `.env` en local o usa Railway Variables:

```env
DISCORD_TOKEN="pega_aqui_el_token"
DISCORD_GUILD_ID="id_de_tu_servidor"
WELCOME_CHANNEL_ID="id_del_canal_de_bienvenida"
RULES_EMBED_COLOR=E53935
ABOUT_EMBED_COLOR=111111
TICKET_CHANNEL_ID=1509405048629755914
TICKET_CATEGORY_ID=1509407852681367632
TICKET_STAFF_ROLE_ID=""
TICKET_PANEL_EMBED_COLOR=111111
TICKET_TERMS_EMBED_COLOR=111111
TICKET_URL="https://discord.com/channels/1267197911498887332/1509405048629755914"
```

`DISCORD_GUILD_ID` es recomendado para que los comandos aparezcan rapido en tu servidor. Sin eso, Discord puede tardar en mostrar comandos globales.

## Comandos

### `/reglas`

Publica un embed rojo con reglas generales del servidor.

Solo pueden usarlo personas con permiso **Manage Server**. Puedes ejecutarlo en el canal donde quieres publicar las reglas, o elegir otro canal desde el parametro `canal`.

### `/servidor`

Publica un embed blanco/negro sobre el servidor, tus servicios, proyectos y automatizaciones.

Incluye un boton **Crear ticket** usando:

- `TICKET_CHANNEL_ID`
- `TICKET_URL`

Solo pueden usarlo personas con permiso **Manage Server**. Puedes ejecutarlo en el canal donde quieres publicarlo, o elegir otro canal desde el parametro `canal`.

### `/panel-ticket`

Publica el panel de tickets en `TICKET_CHANNEL_ID` o en el canal que elijas con el parametro `canal`.

El panel muestra un selector con motivos:

- Soporte tecnico
- Comprar o cotizar
- Proponer una idea
- Bot de Discord
- Pagina web o panel
- Automatizacion
- Ayuda general

Cuando una persona selecciona una opcion, el bot crea un canal privado dentro de `TICKET_CATEGORY_ID`. Antes de continuar, la persona debe aceptar los terminos de uso del servicio. Si rechaza, el ticket se cierra automaticamente.

Si configuras `TICKET_STAFF_ROLE_ID`, ese rol tambien podra ver y responder tickets. Si lo dejas vacio, solo el usuario, el bot y quienes tengan permisos administrativos podran acceder.

## Bienvenida

Variables disponibles:

- `{member}` menciona al usuario nuevo
- `{username}` muestra su nombre visible
- `{tag}` muestra su usuario completo
- `{server}` muestra el nombre del servidor
- `{total}` muestra el total de miembros
- `{links}` inserta la lista de `WELCOME_LINKS`
- `{decoration}` inserta el detalle decorativo del bot

Opciones:

- `WELCOME_TITLE` titulo del embed
- `WELCOME_INTRO` linea destacada debajo del titulo
- `WELCOME_MESSAGE` cuerpo del embed
- `WELCOME_LINKS` lista de enlaces o mensajes, una linea por item
- `WELCOME_EMBED_COLOR=FFFFFF` color lateral del embed
- `WELCOME_THUMBNAIL_URL` imagen pequena; vacio usa avatar del usuario
- `WELCOME_BANNER_URL` imagen grande por URL
- `WELCOME_BANNER_FILE=assets/welcome.jpg` imagen subida junto al bot
- `WELCOME_PING_OUTSIDE_EMBED=false` mantiene todo dentro del embed
- `WELCOME_PING_OUTSIDE_EMBED=true` menciona al usuario fuera del embed

## Ejecutar

```powershell
python bot.py
```

## Railway

El proyecto ya incluye `railway.toml`, asi que Railway debe iniciar con:

```bash
python bot.py
```

Variables minimas en Railway:

```env
DISCORD_TOKEN=tu_token_real
DISCORD_GUILD_ID=id_de_tu_servidor
WELCOME_CHANNEL_ID=id_del_canal_de_bienvenida
RULES_EMBED_COLOR=E53935
ABOUT_EMBED_COLOR=111111
TICKET_CHANNEL_ID=1509405048629755914
TICKET_CATEGORY_ID=1509407852681367632
TICKET_STAFF_ROLE_ID=
TICKET_PANEL_EMBED_COLOR=111111
TICKET_TERMS_EMBED_COLOR=111111
TICKET_URL=https://discord.com/channels/1267197911498887332/1509405048629755914
```

## Permisos del bot

Al invitar el bot, usa los scopes `bot` y `applications.commands`.

Permisos recomendados:

- View Channels
- Send Messages
- Embed Links
- Read Message History
- Manage Channels
- Manage Messages

Para la bienvenida, activa:

`Discord Developer Portal -> Applications -> tu app -> Bot -> Privileged Gateway Intents -> Server Members Intent`
