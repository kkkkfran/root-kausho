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
  automod.py              # Anti invites, anti links y anti spam
  giveaways.py            # Sorteos con reaccion y reclamo temporizado
assets/                   # Imagenes opcionales para embeds
```

## Requisitos

- Python 3.10 o superior
- Un bot creado en el Discord Developer Portal
- Scope `bot`
- Scope `applications.commands` para comandos slash
- Intent **Server Members Intent** activado para la bienvenida
- Intent **Message Content Intent** activado para transcripts completos de tickets

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
WELCOME_AUTO_ROLE_ID=1267198449355460700
RULES_EMBED_COLOR=E53935
ABOUT_EMBED_COLOR=111111
TICKET_CHANNEL_ID=1509405048629755914
TICKET_CATEGORY_ID=1509407852681367632
TICKET_LOG_CHANNEL_ID=1509411767250583613
TICKET_STAFF_ROLE_ID=""
TICKET_PANEL_EMBED_COLOR=111111
TICKET_TERMS_EMBED_COLOR=111111
TICKET_URL="https://discord.com/channels/1267197911498887332/1509405048629755914"
AUTOMOD_ENABLED=true
AUTOMOD_BLOCK_INVITES=true
AUTOMOD_BLOCK_LINKS=true
MOD_LOG_CHANNEL_ID=1509748290110095471
MOD_LOG_EMBED_COLOR=111111
GIVEAWAY_CLAIM_CHANNEL_ID=1507802013851717822
GIVEAWAY_EMBED_COLOR=111111
GIVEAWAY_DATA_FILE="data/giveaways.json"
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

Logs descargables:

- Se envian a `TICKET_LOG_CHANNEL_ID`.
- Solo se guardan tickets aceptados de servicio: `Comprar o cotizar`, `Bot de Discord`, `Pagina web o panel` y `Automatizacion`.
- No se guardan logs de soporte, ideas o ayuda general.
- Si el bot no puede guardar el log de un ticket de servicio, no borra el canal para no perder evidencia.
- Para que el transcript incluya el texto de los mensajes, activa **Message Content Intent** en el Developer Portal.

### `/automod`

Muestra el estado del sistema anti spam/links o lo activa/desactiva en caliente.

Acciones:

- `estado`
- `activar`
- `desactivar`

Variables:

- `AUTOMOD_ENABLED=true` activa el sistema al iniciar el bot
- `AUTOMOD_BLOCK_INVITES=true` bloquea invitaciones de Discord
- `AUTOMOD_BLOCK_LINKS=true` bloquea links externos
- `AUTOMOD_ALLOWED_DOMAINS=github.com,kausho.dev` permite dominios concretos
- `AUTOMOD_EXEMPT_ROLE_ID=` rol exento opcional
- `AUTOMOD_SPAM_MAX_MESSAGES=5` cantidad maxima de mensajes
- `AUTOMOD_SPAM_WINDOW_SECONDS=8` ventana de tiempo para detectar spam
- `AUTOMOD_TIMEOUT_SECONDS=300` segundos de timeout por spam, invites o links bloqueados
- `AUTOMOD_WARNING_DELETE_SECONDS=8` segundos antes de borrar el aviso
- `MOD_LOG_CHANNEL_ID=1509748290110095471` canal donde se registran sanciones automaticas
- `MOD_LOG_EMBED_COLOR=111111` color del embed de sanciones

El log de sanciones registra usuario, canal, accion, razon, duracion del aislamiento y contenido eliminado.

### `/sorteo iniciar`

Crea un sorteo con embed negro/blanco, mencion oculta `||@everyone||` y reaccion para participar.

Parametros:

- `premio`: lo que se sortea
- `duracion`: cuanto dura el sorteo usando abreviaciones, por ejemplo `1h`, `3h`, `1d`, `2h 30m` o `1y`
- `ganadores`: cantidad de ganadores
- `canal`: canal opcional donde publicarlo

El bot busca estos emojis personalizados en el servidor:

- `:gift_1:` para decorar el embed
- `:react_gift:` para participar

Si alguno no existe o no se puede usar, cae al emoji de regalo normal. Cuando termina el sorteo, el ganador tiene 10 segundos para mencionar al organizador en `GIVEAWAY_CLAIM_CHANNEL_ID`. Si no lo hace, el embed se edita marcando la recompensa como perdida.

El embed del ganador muestra su avatar como miniatura y mantiene el temporizador visible mientras reclama.

### `/sorteo reroll`

Elige un nuevo ganador desde un sorteo ya finalizado.

Parametros:

- `mensaje_id`: ID o enlace del mensaje original del sorteo
- `ganadores`: cantidad de nuevos ganadores
- `canal`: canal donde esta el mensaje, si no ejecutas el comando en el mismo canal

El reroll ignora al ultimo ganador registrado para intentar elegir una persona nueva. Publica un embed separado, limpio, con avatar del nuevo ganador y vuelve a iniciar el reclamo de 10 segundos.

Variables:

- `GIVEAWAY_CLAIM_CHANNEL_ID=1507802013851717822` canal donde el ganador debe reclamar
- `GIVEAWAY_EMBED_COLOR=111111` color del embed del sorteo
- `GIVEAWAY_DATA_FILE=data/giveaways.json` archivo local para recordar sorteos activos si el bot se reinicia

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
- `WELCOME_AUTO_ROLE_ID=1267198449355460700` rol que se asigna automaticamente al entrar
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
WELCOME_AUTO_ROLE_ID=1267198449355460700
RULES_EMBED_COLOR=E53935
ABOUT_EMBED_COLOR=111111
TICKET_CHANNEL_ID=1509405048629755914
TICKET_CATEGORY_ID=1509407852681367632
TICKET_LOG_CHANNEL_ID=1509411767250583613
TICKET_STAFF_ROLE_ID=
TICKET_PANEL_EMBED_COLOR=111111
TICKET_TERMS_EMBED_COLOR=111111
TICKET_URL=https://discord.com/channels/1267197911498887332/1509405048629755914
AUTOMOD_ENABLED=true
AUTOMOD_BLOCK_INVITES=true
AUTOMOD_BLOCK_LINKS=true
AUTOMOD_ALLOWED_DOMAINS=
AUTOMOD_EXEMPT_ROLE_ID=
AUTOMOD_SPAM_MAX_MESSAGES=5
AUTOMOD_SPAM_WINDOW_SECONDS=8
AUTOMOD_TIMEOUT_SECONDS=300
AUTOMOD_WARNING_DELETE_SECONDS=8
MOD_LOG_CHANNEL_ID=1509748290110095471
MOD_LOG_EMBED_COLOR=111111
GIVEAWAY_CLAIM_CHANNEL_ID=1507802013851717822
GIVEAWAY_EMBED_COLOR=111111
GIVEAWAY_DATA_FILE=data/giveaways.json
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
- Attach Files
- Moderate Members
- Manage Roles
- Add Reactions
- Mention Everyone

Para la bienvenida, activa:

`Discord Developer Portal -> Applications -> tu app -> Bot -> Privileged Gateway Intents -> Server Members Intent`

Para logs completos de tickets, activa tambien:

`Discord Developer Portal -> Applications -> tu app -> Bot -> Privileged Gateway Intents -> Message Content Intent`
