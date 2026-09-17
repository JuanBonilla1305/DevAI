# camara80s

Tomas una foto con la webcam y un agente la convierte en un retrato de los años 80.
La generación de imagen corre **entera en tu máquina**: la foto no sale de tu PC.

## Cómo funciona

```
main.py  →  agente.py  ──(tool use)──┬→ camara.py      webcam + detección de cara (OpenCV)
                                     └→ generador.py   ├→ motor_flux.py   FLUX.1 Kontext GGUF
                                                       └→ motor_sd15.py   Stable Diffusion 1.5
```

El agente es Claude con cuatro herramientas. No es un pipeline fijo: **ve** la foto que
capturaste, decide si sirve, escribe una instrucción ochentera a medida de tu pelo,
gafas y ropa, genera, **mira el resultado** y ajusta si no quedó bien. Itera hasta 3 veces.

| Herramienta | Qué hace |
|---|---|
| `capturar_foto` | Abre la ventana de la webcam y mide nitidez, brillo, encuadre y nº de caras |
| `analizar_foto` | Vuelve a evaluar una foto ya guardada |
| `generar_80s` | Corre el modelo local y le devuelve la imagen generada al agente |
| `entregar_resultado` | Guarda la elegida como `FINAL_*.png` y la abre |

Solo viajan a la API de Claude el texto y las imágenes que el agente necesita ver para
razonar. La generación de imagen es local.

## Los dos motores

Se elige con `MOTOR` en el `.env`.

### `flux` (por defecto) — FLUX.1 Kontext

Modelo de **edición** de 12.000 millones de parámetros. Recibe la foto y una instrucción
(«turn this into a 1980s studio portrait») y conserva la identidad de la cara mucho
mejor que un img2img normal.

En bf16 pesaría 24 GB, así que aquí va en tres piezas:

| Pieza | Formato | Tamaño |
|---|---|---|
| Transformer | GGUF Q4_K_S | ~6,8 GB |
| T5-XXL (texto) | NF4 al cargar | ~3,0 GB en memoria, ~9,8 GB en disco |
| VAE + CLIP-L | bf16 | ~0,4 GB |

Con `enable_sequential_cpu_offload()` cada submódulo sube a la GPU solo mientras se
ejecuta, así que el pico de VRAM se queda por debajo de 6 GB — a costa de velocidad:
**3–8 minutos por imagen** en una RTX 3050 portátil.

Parámetros: `guia_texto` 2.0–4.0 (3.0 por defecto), `pasos` 20–28. El prompt negativo
activa *true CFG*, que **duplica** el tiempo; úsalo solo si hace falta.

### `sd15` — Stable Diffusion 1.5

Alternativa rápida (30–90 s) y de menor calidad. Dos modos: `pix2pix`
(`timbrooks/instruct-pix2pix`, el prompt es una instrucción) e `img2img`
(`Lykon/dreamshaper-8`, el prompt describe el resultado, `fuerza` 0.35–0.55).

## Requisitos

- Windows con GPU NVIDIA (probado en RTX 3050 Laptop, 6 GB)
- Python 3.12
- ~20 GB de disco libre para los modelos
- Una API key de Anthropic: https://console.anthropic.com/settings/keys

## Instalación

```bash
cd C:\Users\Juan\Desktop\mio\camara80s
.venv\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Pon tu clave en `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Comprueba que los repos de modelos están accesibles y descárgalos (~17 GB, se puede
cortar con Ctrl+C y retomar):

```bash
.venv\Scripts\python.exe comprobar_modelos.py
.venv\Scripts\python.exe descargar_modelos.py
```

Y revisa que todo esté en su sitio:

```bash
.venv\Scripts\python.exe main.py --diagnostico
```

## Uso

```bash
.venv\Scripts\python.exe main.py
```

Se abre la ventana de la cámara:

- **ESPACIO** — tomar la foto
- **ESC** — cancelar

El recuadro amarillo marca la cara detectada. Colócate para que salga **una sola** y
que ocupe buena parte del encuadre.

También puedes pedir un estilo concreto:

```bash
.venv\Scripts\python.exe main.py "quiero verme como un rockero glam de 1987"
```

Capturas en `capturas/`, resultados en `salidas/`.

## Problemas típicos

| Síntoma | Causa |
|---|---|
| `No se pudo abrir la camara 0` | Otra app tiene la webcam (Teams, Zoom, Meet). Ciérrala o cambia `INDICE_CAMARA` |
| `CUDA out of memory` | Baja `LADO_MAXIMO` a 512, o usa `FLUX_ARCHIVO_GGUF=flux1-kontext-dev-Q3_K_S.gguf` |
| Va lentísimo y el disco al 100 % | Tienes 16 GB de RAM; cierra el navegador antes de generar |
| Se queda "colgado" al empezar | Está descargando modelos. Corre `descargar_modelos.py` aparte para verlo |
| No se detecta la cara | Más luz de frente, quítate gorra/mascarilla, acércate |

El *safety checker* de SD 1.5 está desactivado: daba falsos positivos con retratos
normales y devolvía imágenes en negro.
