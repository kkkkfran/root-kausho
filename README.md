# Bot de bienvenida para Discord

Bot base en Python para saludar automaticamente a usuarios nuevos del servidor.

## Requisitos

- Python 3.10 o superior
- Un bot creado en el Discord Developer Portal
- El intent **Server Members Intent** activado en la pagina del bot

## Instalacion

Desde esta carpeta:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Configuracion

Edita el archivo `.env`:

```env
DISCORD_TOKEN="pega_aqui_el_token"
WELCOME_CHANNEL_ID="123456789012345678"
WELCOME_TITLE="Welcome {member}"
WELCOME_INTRO="**Welcome {member} To {server}**"
WELCOME_MESSAGE="**Glad to have you here**\n\n{links}\n\n{decoration} Thank you for joining us, have fun {decoration}"
WELCOME_LINKS="Make sure to read the [Server Rules](https://tusitio.com/rules)\nCheck our latest [Updates](https://tusitio.com/updates)\nFor IP/Port [Click Here](https://tusitio.com/play)\nNeed Help? Check our [Ticket Support](https://tusitio.com/support)"
WELCOME_EMBED_COLOR=F2A7C6
WELCOME_BANNER_URL="https://tusitio.com/welcome-banner.png"
```

Para sacar el ID del canal: activa el modo desarrollador en Discord, clic derecho sobre el canal de bienvenida y copia el ID.

Variables disponibles para el mensaje:

- `{member}` menciona al usuario nuevo
- `{username}` muestra su nombre visible
- `{tag}` muestra su usuario completo
- `{server}` muestra el nombre del servidor
- `{total}` muestra el total de miembros
- `{links}` inserta la lista de `WELCOME_LINKS`
- `{decoration}` inserta el detalle decorativo del bot

Opciones visuales:

- `WELCOME_INTRO` muestra la linea destacada debajo del titulo
- `WELCOME_LINKS` crea la lista del embed; usa una linea por item
- `WELCOME_DECORATION` cambia el detalle que aparece antes de cada link y en el cierre
- `WELCOME_EMBED_COLOR=F2A7C6` cambia el color lateral del embed usando HEX
- `WELCOME_THUMBNAIL_URL` cambia la imagen pequena de la derecha; vacio usa el avatar del usuario
- `WELCOME_BANNER_URL` agrega una imagen grande al final del embed
- `WELCOME_BANNER_FILE=assets/welcome-banner.png` usa una imagen subida junto al bot
- `WELCOME_PING_OUTSIDE_EMBED=false` mantiene todo dentro del embed
- `WELCOME_PING_OUTSIDE_EMBED=true` menciona al usuario fuera del embed para que reciba ping real
- Puedes usar `\n` dentro de `WELCOME_MESSAGE` para crear saltos de linea
- Puedes usar links Markdown: `[texto](https://url.com)` dentro de `WELCOME_LINKS`

## Ejecutar

```powershell
python bot.py
```

## Subir a Railway

Este proyecto ya incluye `railway.toml`, asi que Railway debe iniciar el bot con:

```bash
python bot.py
```

No subas tu token dentro de `.env`. En Railway configuralo desde:

`Service -> Variables -> New Variable`

Variables minimas:

```env
DISCORD_TOKEN=tu_token_real
WELCOME_CHANNEL_ID=id_del_canal_de_bienvenida
WELCOME_TITLE=Welcome {member}
WELCOME_INTRO=**Welcome {member} To {server}**
WELCOME_MESSAGE=**Glad to have you here**\n\n{links}\n\n{decoration} Thank you for joining us, have fun {decoration}
WELCOME_LINKS=Make sure to read the [Server Rules](https://tusitio.com/rules)\nCheck our latest [Updates](https://tusitio.com/updates)\nFor IP/Port [Click Here](https://tusitio.com/play)\nNeed Help? Check our [Ticket Support](https://tusitio.com/support)
WELCOME_EMBED_COLOR=F2A7C6
WELCOME_BANNER_URL=https://tusitio.com/welcome-banner.png
WELCOME_PING_OUTSIDE_EMBED=false
```

Railway tambien puede sugerir variables desde `.env.example`. Si usas GitHub, cada push al repo puede desplegar una nueva version del bot.

## Permisos recomendados

Al invitar el bot, usa el scope `bot` y dale estos permisos:

- View Channels
- Send Messages
- Embed Links

Para que `on_member_join` funcione, tambien debes activar **Server Members Intent** en:

`Discord Developer Portal -> Applications -> tu app -> Bot -> Privileged Gateway Intents`.
