# Guía para la feria

## Arrancar

Doble clic en **`INICIAR.bat`** (está en `Escritorio\mio`).

Se abre una ventana negra y, a los diez segundos, el navegador en
`http://127.0.0.1:3000`.

**No cierres la ventana negra.** Ahí es donde corre el programa. Puedes
minimizarla.

No hace falta internet: todos los modelos están descargados en el equipo.

## Usar

1. **Foto** — «📸 Tomar la foto con la cámara», o subir un archivo.
2. **Vestuario** — Mujer, Hombre, o Niño/Niña.
3. **Personas** — Una o dos. Con dos, elige la combinación.
4. **Identidad** — déjalo a la derecha del todo (máximo parecido).
5. **Generar**.

La barra muestra el tiempo. **Unos 2 minutos por foto.** La primera tarda
algo más porque carga el modelo.

El resultado se descarga con el botón de abajo, y además se guarda solo en
`sanjuanero\sanjuanero-node\results`.

## Que las fotos salgan bien

Lo que más influye, por orden:

| | |
|---|---|
| **Luz de frente** | Nada de ventana detrás. Si la cara queda en sombra, el parecido se pierde |
| **Cara grande y de frente** | Que ocupe buena parte del encuadre. Nada de perfil |
| **Sin gorra ni tapabocas** | Tapan los rasgos que necesita el modelo |
| **Fondo cualquiera** | Da igual: se reemplaza entero |

Las gafas se detectan solas y se conservan, con montura ochentera.

## Si algo falla

| Síntoma | Qué hacer |
|---|---|
| El navegador dice que no se puede conectar | Espera 20 segundos y recarga. Está arrancando |
| «No se pudo abrir la cámara» | Otra app la tiene (Teams, Zoom, Meet). Ciérrala y recarga |
| La cámara no aparece | Windows: Configuración → Privacidad → Cámara → permitir a apps de escritorio |
| «No pude detectar ningún rostro» | Más luz de frente y más cerca |
| Lleva más de 5 minutos | Cierra la ventana negra y vuelve a dar doble clic |
| Sale una cara rara o deformada | Genera otra vez: cada intento es distinto |

**El reinicio arregla casi todo:** cierra la ventana negra, espera cinco
segundos, doble clic otra vez.

## Para el público

Si te preguntan qué es, en una frase:

> Todo corre en este portátil. La foto no sale de aquí, no se sube a ninguna
> nube. Un modelo de imagen reconstruye la escena de los años 80 y después le
> devuelve tu cara real.

## Detalles por si preguntan

- **Modelo:** FLUX.2 Klein 4B, cuantizado a 4 bits para que quepa en los 6 GB
  de la tarjeta gráfica
- **Rostro:** InsightFace detecta y `inswapper_128` intercambia
- **Generación:** unos 37 segundos; el resto del tiempo se va en el análisis
  facial
- **Privacidad:** sin conexión, sin API externa, sin subir nada

## Antes de salir de casa

```
1. Doble clic en INICIAR.bat
2. Hacer una foto de prueba completa
3. Comprobar que sale el resultado
4. Cerrar la ventana negra
```

Si eso funciona sin internet, en la feria funcionará.
