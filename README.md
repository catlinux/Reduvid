# Reduvid

**Castellano** · [English](README.en.md)

Compresor de vídeo fácil y multiplataforma para tu biblioteca Jellyfin: reduce el tamaño con H.264/H.265 conservando subtítulos y capítulos. Con asistente paso a paso. Basado en FFmpeg.

## Qué es

Reduvid (de *reducir vídeo*) es una aplicación de escritorio para Linux y Windows que reduce el tamaño de tus vídeos perdiendo muy poca calidad. Por debajo usa [FFmpeg](https://ffmpeg.org/), pero no hace falta saber nada de códecs: un asistente te pregunta dónde vas a ver los vídeos y cuánto quieres ahorrar, y explica cada opción en lenguaje llano.

- **Tus originales no se tocan.** Reduvid escribe un archivo nuevo, comprueba que está completo y solo entonces lo deja con su nombre final. Nunca sobrescribe nada.
- **Pensado para Jellyfin.** Un perfil «Jellyfin compatible» genera vídeo que se reproduce directo en casi cualquier dispositivo, sin que el servidor tenga que convertirlo.
- **Conserva lo importante:** subtítulos, capítulos, pistas de audio e idiomas, metadatos y portada.
- **Para todos:** modo Asistente (una decisión por pantalla) y modo Avanzado (todo en una vista), más una línea de órdenes para servidores y scripts.

## Estado del proyecto

En desarrollo, **todavía no se puede usar para convertir vídeos**. La versión actual (0.0.1) solo contiene la estructura del proyecto. Plan:

| Versión | Contenido |
|---|---|
| 0.1.0 | Motor de conversión y línea de órdenes |
| 0.2.0 | Interfaz gráfica, asistente e idiomas (català, castellano, English) |
| 0.3.0 | Prueba de muestra, estimaciones, informe final y perfiles guardados |
| 0.4.0 → 1.0.0 | Instaladores para Linux y Windows y primera versión estable |

Detalle en [TODO.md](TODO.md) y en el [CHANGELOG](CHANGELOG.md).

## Capturas

Llegarán con la interfaz (versión 0.2.0).

## Requisitos

- Linux o Windows 10/11.
- Python 3.11 o posterior, mientras no haya instaladores.
- **FFmpeg** con `libx264` y `libx265`. Reduvid no lo incluye: usa el que tengas instalado.

## Instalación

1. Instala FFmpeg:
   - Debian / Ubuntu: `sudo apt install ffmpeg`
   - Windows: `winget install Gyan.FFmpeg`, o descárgalo de [ffmpeg.org](https://ffmpeg.org/download.html) y añádelo al `PATH`.
2. Instala Reduvid desde el código fuente:

   ```bash
   git clone https://github.com/catlinux/Reduvid.git
   cd Reduvid
   python -m venv .venv
   # Linux: source .venv/bin/activate    Windows: .venv\Scripts\activate
   python -m pip install -e .
   ```

Habrá paquetes con `pipx`, un instalador para Windows y una AppImage para Linux a partir de la versión 0.4.0.

## Uso rápido

```bash
reduvid --version
```

Por ahora es lo único disponible. La conversión desde la línea de órdenes llega en la 0.1.0.

## ¿H.264 o H.265 para Jellyfin?

| | H.264 («Jellyfin compatible») | H.265 / HEVC |
|---|---|---|
| Ahorro orientativo | 20-40 % | 40-70 % |
| Se reproduce directo en | Casi todo: teles, móviles, navegadores | Dispositivos modernos; en otros, Jellyfin lo convierte en el servidor o falla |
| Recomendado si | Lo ves en varios dispositivos o no lo sabes | Tus dispositivos son modernos, o solo quieres archivar |

Las cifras son orientativas y dependen de cada vídeo; la prueba de muestra de Reduvid (versión 0.3.0) da el dato real. Aunque el códec sea compatible, Jellyfin también transcodifica con vídeo de 10 bits, HDR, algunos subtítulos de imagen (PGS, VobSub) y audio DTS o TrueHD. Reduvid avisa de cada caso y propone cómo resolverlo.

## Privacidad

Reduvid no tiene telemetría ni estadísticas de uso, y no se conecta a internet. Todo ocurre en tu equipo.

## FFmpeg y licencias

Reduvid no incluye ni distribuye FFmpeg ni ningún códec. Lo ejecuta como un programa aparte, pasándole argumentos, sin enlazar ni incorporar sus bibliotecas. Las compilaciones de FFmpeg con `libx264` y `libx265` suelen estar bajo GPL; esa licencia rige FFmpeg, no Reduvid. Si redistribuyes FFmpeg (por ejemplo, junto a Reduvid), cumplir su licencia te corresponde a ti. En algunos países, H.264 y H.265 están sujetos a patentes.

Las licencias de las dependencias están en [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Contribuir

Las aportaciones son bienvenidas, incluidas las traducciones. Lee [CONTRIBUTING.md](CONTRIBUTING.md) y el [código de conducta](CODE_OF_CONDUCT.md). Para avisar de un problema de seguridad, consulta [SECURITY.md](SECURITY.md).

## Créditos y licencia

**Reduvid** está desarrollado y mantenido por **Catlinux** ([github.com/catlinux](https://github.com/catlinux)).
Copyright (C) 2026 Catlinux.

Licencia [WNCL-CU-1.0](LICENSE): puedes usarlo gratis para cualquier fin, también comercial, y modificarlo y compartirlo sin coste. Nadie puede cobrar por el software ni por su uso; solo se pueden cobrar servicios de soporte e implementación. No es una licencia Open Source aprobada por OSI.

Las copias y los forks deben conservar esta atribución y enlazar a https://github.com/catlinux/Reduvid.

### Material de terceros

| Componente | Autor | Licencia | Enlace |
| --- | --- | --- | --- |

Este repositorio no contiene material de terceros. Las dependencias que se instalan aparte conservan su licencia y se detallan en [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
