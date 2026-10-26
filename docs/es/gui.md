# Uso de la interfaz gráfica

**Castellano** · [English](../en/gui.md)

Se abre con `reduvid` (o `python -m reduvid`). Para servidores sin pantalla, usa la [línea de órdenes](cli.md) (`reduvid-cli`).

## Capturas

El paso Resumen del asistente, en los tres temas (rutas relativas a esta guía):

| Plegat | Riso | Cinta |
|---|---|---|
| [![Tema Plegat](../screenshots/plegat_light.png)](../screenshots/plegat_light.png) | [![Tema Riso](../screenshots/riso_light.png)](../screenshots/riso_light.png) | [![Tema Cinta](../screenshots/cinta_light.png)](../screenshots/cinta_light.png) |
| [![Tema Plegat, modo oscuro](../screenshots/plegat_dark.png)](../screenshots/plegat_dark.png) | [![Tema Riso, modo oscuro](../screenshots/riso_dark.png)](../screenshots/riso_dark.png) | [![Tema Cinta, modo oscuro](../screenshots/cinta_dark.png)](../screenshots/cinta_dark.png) |

## Primer arranque

Reduvid necesita FFmpeg. Si no lo encuentra (ni en la ruta configurada ni en el `PATH`), muestra una pantalla que explica cómo instalarlo (`winget install Gyan.FFmpeg` en Windows; `apt` o `dnf` en Linux) y ofrece **Elegir ffmpeg…** para indicar el ejecutable y **Volver a buscar**. No usa la red.

## Modo Asistente

Una decisión por pantalla. Arriba puedes pasar al modo Avanzado y volver sin perder lo que habías elegido.

1. **Vídeos.** Añade archivos o una carpeta (con la casilla para incluir subcarpetas), o arrástralos a la ventana. Reduvid los analiza en segundo plano y muestra la duración de cada uno o el error si no se puede leer. Puedes quitar los que no quieras. Para seguir hace falta al menos un vídeo analizado correctamente.
2. **¿Dónde los vas a ver?** Elige el destino: *Jellyfin* (tele, móvil o navegador; H.264, el más compatible pero con archivos más grandes), *Dispositivos modernos* (H.265, archivos más pequeños, pero los aparatos antiguos quizá no lo reproduzcan) o *Guardar para archivo* (H.265 con la codificación más lenta y cuidadosa). Cada tarjeta indica su compromiso. «No lo sé» usa Jellyfin.
3. **Calidad.** *Casi idéntica*, *Equilibrada* (recomendada) o *Máximo ahorro*. Encima de las tarjetas, unas viñetas dicen qué hará la conversión con tu vídeo (códec, resolución, HDR o 10 bits) y cada tarjeta indica qué detalle se pierde. El botón «Estimar el tamaño de cada nivel» convierte una muestra corta de 20 segundos por nivel, sin guardar nada, y muestra en cada tarjeta cuánto ocuparía el archivo y cuánto ahorra; puede tardar un par de minutos y se puede cancelar. Con varios vídeos se estima el de mayor duración. El selector de resolución (Automática, 1080p, 720p o 480p, solo las menores que el original) reduce la imagen, que es lo que más ahorra, y los «Detalles técnicos» muestran códec, preajuste, CRF, perfil y formato de píxel. Son estimaciones y se descartan si cambias el destino o la resolución.
4. **Qué conservar.** Con un solo vídeo eliges las pistas de audio una a una: verás el idioma, el formato, los canales y el tamaño estimado de cada una, y la pista predeterminada lleva una etiqueta. Los subtítulos se eligen por idioma e indican si son de texto o de imagen. Con varios vídeos se eligen los idiomas de audio y de subtítulos; «Una sola pista de audio por idioma» se queda con la mejor pista de cada idioma. En ambos casos, «Reducir el peso del audio» recodifica el audio a AAC (compatible con MP4 y MKV) y una línea muestra cuánto pesará antes y después; es una estimación. Si el contenedor elegido descarta los subtítulos de imagen o hace que Jellyfin tenga que quemarlos, una nota lo avisa. Si no marcas ninguna pista de audio, se conservan todas y se avisa.
5. **Destino.** Misma carpeta que cada vídeo u otra, MKV o MP4 y, si hay vídeo 4K con destino Jellyfin, la opción de reducirlo a 1080p. **Reemplazar el original** está desactivado por defecto: si lo activas, el original va a la papelera solo cuando la copia se ha verificado.
6. **Resumen.** Revisa qué hará Reduvid con cada vídeo antes de empezar. El botón «Estimar el tamaño final (prueba de 1 minuto)» convierte tres trozos de 20 segundos del vídeo (hacia el 20 %, el 50 % y el 80 %) con tus ajustes, sin guardar nada, y calcula cuánto ocupará el archivo final y cuánto tardará. Es una estimación: el tamaño real puede variar si el vídeo cambia mucho de unas escenas a otras. Si cambias algún ajuste, hay que volver a estimar.

### El semáforo de Jellyfin

Cada vídeo del resumen lleva un indicador:

| Color | Significado |
| --- | --- |
| Verde | Se reproducirá directo en Jellyfin, sin que el servidor lo convierta |
| Ámbar | Algo hará que Jellyfin convierta el vídeo al reproducirlo (destino H.265, 10 bits o subtítulos de imagen que tendrá que «quemar») |
| Rojo | Hay un aviso que requiere tu decisión |

Si un vídeo es HDR y tu FFmpeg no puede pasarlo a SDR, Reduvid te pregunta por cada uno: **Saltar este vídeo** (por defecto) o **Convertir igualmente** (los colores se verán apagados). Los saltados no entran en la cola.

**Empezar** lanza la conversión y abre el panel de cola.

## Modo Avanzado

Una sola página con todas las opciones de la línea de órdenes: vídeos, destino, calidad, contenedor, altura máxima, carpeta de salida, número de hilos, reemplazar el original e idiomas, más el mismo resumen con semáforo. Comparte la selección con el asistente. No se puede cambiar de modo mientras hay una conversión en marcha.

## Panel de cola

A la derecha (debajo, en ventanas estrechas) se ve el vídeo actual con su porcentaje y el tiempo restante, la lista de vídeos con sus avisos, y los botones **Pausar** / **Reanudar** y **Cancelar**. Al cancelar no queda ningún archivo a medias. Si cierras la ventana con una conversión en marcha, Reduvid te pregunta antes de cancelarla. Al terminar muestra el ahorro total y, para cada error, un mensaje claro con un desplegable de detalles técnicos que puedes copiar.

## Preferencias

- **Tema:** Plegat (por defecto), Riso o Cinta.
- **Modo de color:** Sistema (por defecto), Claro u Oscuro.
- **Idioma:** Sistema, català, castellano o English. Se aplica al reiniciar.
- **Reducir animaciones.**
- **Ruta de FFmpeg:** con **Examinar…** y **Comprobar**.

Se guardan en el archivo de configuración, el mismo que usa la línea de órdenes (ver [la guía de la CLI](cli.md)).
