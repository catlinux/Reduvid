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
2. **¿Dónde los vas a ver?** Elige el destino: *Jellyfin* (tele, móvil o navegador; H.264, el más compatible), *Dispositivos modernos* (H.265, más ahorro) o *Guardar para archivo* (H.265 con más compresión, más lento). «No lo sé» usa Jellyfin.
3. **Calidad.** *Casi idéntica*, *Equilibrada* (recomendada) o *Máximo ahorro*. El desplegable «¿Qué es esto?» explica el compromiso entre calidad y tamaño. Debajo se muestran, si aplican al primer vídeo de la cola, los avisos de compatibilidad (HDR, 10 bits, subtítulos de imagen…) para que los veas antes de llegar al Resumen.
   - **Probar con una muestra de 30 s:** codifica un fragmento corto del primer vídeo (al 40 % de su duración) con la calidad elegida y muestra un fotograma antes/después, el tamaño estimado para el vídeo completo y el porcentaje de ahorro. Si cambias de calidad, la muestra queda invalidada y hay que volver a pedirla.
   - **Perfiles guardados:** el desplegable permite cargar una combinación de destino, calidad, contenedor e idiomas guardada antes; **Guardar como perfil…** guarda la combinación actual con el nombre que le des.
4. **Qué conservar.** Marca los idiomas de audio y de subtítulos que quieres mantener; por defecto se conserva todo. Si en un vídeo no quedara ningún audio, se conservan todos los suyos y se avisa.
5. **Destino.** Misma carpeta que cada vídeo u otra, MKV o MP4 y, si hay vídeo 4K con destino Jellyfin, la opción de reducirlo a 1080p. **Reemplazar el original** está desactivado por defecto: si lo activas, el original va a la papelera solo cuando la copia se ha verificado.
6. **Resumen.** Revisa qué hará Reduvid con cada vídeo antes de empezar. Si has calculado una muestra en el paso de Calidad, cada vídeo muestra además su tamaño y tiempo de conversión estimados, proporcionales a su duración.

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
