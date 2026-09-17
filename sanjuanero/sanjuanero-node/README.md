# Sanjuanero IA local

Aplicación web local que transforma fotografías de una o dos personas en
escenas del baile Sanjuanero Huilense. Node.js controla la interfaz y el flujo;
FastSD CPU, OpenVINO, FLUX.2 e InsightFace realizan el procesamiento de IA en
Python.

> Este README describe el estado real del proyecto. Antes de instalarlo en
> otro computador hay que cambiar varias rutas absolutas de Windows y copiar
> las referencias y modelos faciales indicados abajo.

## 1. Funciones actuales

- Carga de fotografías JPG, PNG o WEBP de hasta 12 MB.
- Detección automática de uno o dos rostros principales.
- Clasificación aparente de hombre/mujer y estimación del grupo de edad.
- Detección local de gafas y gafas de sol.
- Selección automática de:
  - una mujer;
  - un hombre;
  - dos mujeres;
  - dos hombres;
  - pareja mixta;
  - adulto con niño.
- Corrección manual de la composición desde el frontend.
- Referencias independientes para pose, identidad/cabello y vestuario.
- Vestuario femenino y masculino de Sanjuanero Huilense.
- Mochila huilense en el vestuario femenino.
- Intercambio de uno o dos rostros mediante InsightFace/InSwapper.
- Procesamiento local: las fotos no se envían a una API externa de imágenes.
- Descarga del resultado desde el navegador.

## 2. Arquitectura

```text
Navegador
   │
   ├── POST /api/analyze-photo
   │      └── Node → analyze_photo.py → InsightFace + modelos de atributos
   │
   └── POST /api/generate
          ├── Node vuelve a validar cuántas personas hay
          ├── extrae una referencia de cabeza por persona
          ├── elige la referencia de pose y construye el prompt
          ├── envía las referencias a FastSD en http://127.0.0.1:8000
          ├── FastSD ejecuta FLUX.2 Klein con OpenVINO
          └── preserve_face.py aplica uno o dos rostros al resultado
```

La aplicación web escucha por defecto en `127.0.0.1:3000`. Node inicia
automáticamente el servidor API de FastSD en `127.0.0.1:8000`.

También existe una interfaz Gradio alternativa en
`fastsdcpu-main\sanjuanero\app.py`, iniciada por `start-sanjuanero.bat`. Es un
flujo Python separado para pruebas y no comparte automáticamente las
referencias ni los prompts de la aplicación Node.

## 3. Estructura relevante

```text
SanjuaneroIA/
├── fastsdcpu-main/
│   ├── env/                         # Entorno virtual de Python
│   ├── requirements.txt
│   ├── configs/settings.yaml        # Configuración persistente de FastSD
│   ├── src/app.py                   # Entrada de FastSD
│   ├── start-sanjuanero.bat         # Interfaz Gradio alternativa
│   └── sanjuanero/
│       ├── app.py                   # Entrada de la interfaz Gradio
│       ├── generate.py
│       ├── prompts.py
│       ├── face_preserve.py         # Intercambio y mezcla facial real
│       └── models/
│           ├── inswapper_128.onnx
│           ├── gender_net.caffemodel
│           ├── gender_deploy.prototxt
│           └── face_attrib_net/
└── sanjuanero-node/
    ├── package.json
    ├── package-lock.json
    ├── server.js                    # Servidor y configuración principal
    ├── start.bat
    ├── public/
    │   ├── index.html
    │   ├── app.js
    │   └── styles.css
    ├── scripts/
    │   ├── analyze_photo.py
    │   ├── extract_head_reference.py
    │   ├── preserve_face.py
    │   └── crop_face.py
    └── results/                     # Originales, cuerpos y resultados
```

## 4. Tecnología y modelo actual

### Aplicación

- Node.js 18 o superior.
- Express 5.
- Multer para recibir fotografías.
- HTML, CSS y JavaScript sin framework en el frontend.

### Generación

- FastSD CPU.
- OpenVINO.
- Modelo: `rupeshs/flux2-klein-4b-int4-ov`.
- FLUX.2 Klein 4B cuantizado a INT4.
- Tarea: `edit_image` con una lista de referencias.
- Resolución solicitada: 384 × 512.
- Pasos: 6 para una persona y 8 para dos personas.
- `guidance_scale`: 1.0.

### Rostros

- InsightFace `buffalo_l`: detección, embeddings, edad y género aparente.
- `inswapper_128.onnx`: intercambio facial.
- FaceAttribNet: gafas y gafas de sol.
- Modelo Caffe de género como clasificación complementaria.

InSwapper trabaja internamente a 128 × 128. Aunque se hace un recorte ampliado,
doble pase y enfoque local, esa resolución limita la fidelidad cuando aparecen
dos cuerpos completos y los rostros ocupan pocos píxeles.

## 5. Requisitos para otro computador

### Mínimos para conservar el flujo actual

- Windows 10/11 de 64 bits.
- Python 3.10 o superior.
- Node.js 18 o superior.
- Git opcional, pero recomendado.
- 20 GB de RAM recomendados; FastSD indica 8 GB como mínimo para Flux2
  OpenVINO, pero este proyecto carga además análisis e intercambio facial.
- Entre 25 y 50 GB libres para código, entornos, cachés y modelos.
- Conexión a Internet durante la primera instalación y descarga de modelos.

### Computador potente recomendado

- CPU moderna de 8 núcleos o más.
- 32 GB de RAM como base; 64 GB si se probarán modelos grandes.
- SSD NVMe.
- Para modelos CUDA como Qwen-Image-Edit o FLUX.2 Dev:
  - NVIDIA con 16 GB VRAM para cuantizaciones agresivas;
  - 24 GB VRAM como configuración recomendada;
  - 48 GB o más para mayor precisión y menos offload.

El flujo actual usa OpenVINO y está preparado principalmente para CPU o
hardware Intel. Tener una NVIDIA potente no acelera automáticamente este
backend: para aprovechar CUDA hay que instalar y conectar otro pipeline.

## 6. Instalación en un PC nuevo

### 6.1 Copiar el proyecto

Copiar las dos carpetas juntas:

```text
<RUTA_BASE>/
├── fastsdcpu-main/
└── sanjuanero-node/
```

No copiar fotografías privadas dentro de un repositorio público. Tampoco es
recomendable versionar `node_modules`, `env`, cachés, `results` ni modelos de
varios GB.

### 6.2 Instalar Node.js

Instalar Node.js 18 o superior y comprobar:

```powershell
node --version
npm --version
```

Después:

```powershell
cd <RUTA_BASE>\sanjuanero-node
npm ci
```

Si no existe `package-lock.json`, usar `npm install`.

### 6.3 Instalar FastSD y Python

La forma recomendada por FastSD en Windows es ejecutar `install.bat` dentro de
`fastsdcpu-main`. El resultado debe incluir exactamente:

```text
<RUTA_BASE>\fastsdcpu-main\env\Scripts\python.exe
```

El servidor Node espera esa ubicación. También se puede crear manualmente:

```powershell
cd <RUTA_BASE>\fastsdcpu-main
py -3.10 -m venv env
.\env\Scripts\python.exe -m pip install --upgrade pip
.\env\Scripts\python.exe -m pip install -r requirements.txt
.\env\Scripts\python.exe -m pip install insightface
```

Comprobar el API de FastSD de forma independiente:

```powershell
.\env\Scripts\python.exe .\src\app.py --api --port 8000
```

Cuando funcione, cerrar esa prueba. Node volverá a iniciarlo automáticamente.

### 6.4 Copiar los modelos faciales

Estos archivos son obligatorios:

```text
fastsdcpu-main\sanjuanero\models\inswapper_128.onnx
fastsdcpu-main\sanjuanero\models\gender_net.caffemodel
fastsdcpu-main\sanjuanero\models\gender_deploy.prototxt
fastsdcpu-main\sanjuanero\models\face_attrib_net\
  face_attrib_net-onnx-float\face_attrib_net.onnx
```

También se necesita la carpeta completa de InsightFace:

```text
%USERPROFILE%\.insightface\models\buffalo_l\
```

Como mínimo debe contener los modelos de detección, reconocimiento, landmarks
y edad/género. El código comprueba específicamente:

```text
det_10g.onnx
w600k_r50.onnx
2d106det.onnx
```

La forma más segura de desplegar es copiar la carpeta `buffalo_l` que ya
funciona o permitir que InsightFace la descargue en el usuario de Windows que
ejecutará Node.

### 6.5 Descargar FLUX.2

El identificador actual es:

```text
rupeshs/flux2-klein-4b-int4-ov
```

FastSD/Hugging Face lo descarga normalmente al utilizarlo por primera vez.
Esa primera ejecución puede tardar bastante. Para una instalación sin Internet
hay que copiar también la caché de Hugging Face del usuario y configurar el
modelo como ruta local.

## 7. Rutas portables

El servidor, los scripts Python, `start.bat` y `configs/settings.yaml` usan
rutas calculadas desde la ubicación del proyecto. El repositorio puede
clonarse en cualquier unidad o carpeta del usuario.

Las seis referencias visuales deben existir en:

```text
sanjuanero-node\references\
├── pose_mujer.png
├── pose_hombre.png
├── vestido_mujer.jpg
├── pose_dos_hombres.jpg
├── pose_dos_mujeres.jpg
└── pose_pareja_mixta.png
```

`inswapper_128.onnx` no se almacena en Git por su tamaño. Debe copiarse
manualmente a:

```text
fastsdcpu-main\sanjuanero\models\inswapper_128.onnx
```

## 8. Inicio

```powershell
cd <RUTA_BASE>\sanjuanero-node
npm start
```

Abrir:

```text
http://127.0.0.1:3000
```

Node comprobará FastSD y lo iniciará en el puerto 8000 si no está activo.
No ejecutar dos copias de Node o FastSD sobre los mismos puertos.

## 9. Publicar en red local

Por seguridad, el servidor usa:

```js
const HOST = "127.0.0.1";
```

Para permitir acceso desde otros equipos de la misma red:

1. Cambiar `HOST` a `"0.0.0.0"` en `server.js`.
2. Permitir el puerto 3000 en el firewall de Windows solo para la red privada.
3. Iniciar la aplicación.
4. Abrir desde otro equipo:

```text
http://IP_DEL_SERVIDOR:3000
```

El puerto 8000 de FastSD no necesita exponerse; Node lo consume localmente.

### No exponer directamente a Internet

La aplicación actual no tiene autenticación, TLS, usuarios, cuotas, limpieza
automática ni limitación de solicitudes. Para Internet se necesita como mínimo:

- proxy inverso con HTTPS;
- autenticación;
- límites de tamaño y frecuencia;
- una cola de generación;
- control de acceso a resultados;
- política de retención y eliminación de fotografías;
- logs y monitoreo;
- revisión de licencias de todos los modelos.

## 10. Cómo funciona una generación

1. El frontend sube la fotografía a `/api/analyze-photo`.
2. `analyze_photo.py` detecta hasta dos rostros principales.
3. Se estima género, edad y presencia de gafas para cada rostro.
4. El frontend selecciona automáticamente personas y composición.
5. Al generar, Node repite el análisis; no confía únicamente en el selector.
6. `extract_head_reference.py` crea una referencia separada por persona.
7. Node escoge la referencia de pose adecuada.
8. El prompt define qué imagen controla pose, identidad, cabello y vestuario.
9. FastSD recibe el `requestBody` mediante `/api/generate`.
10. FLUX.2 produce el cuerpo y el vestuario.
11. `preserve_face.py` aplica las identidades originales.
12. Node guarda archivos intermedios y devuelve el JPEG final en base64.

## 11. Archivos que se modifican según el objetivo

### Cambiar vestuario

Archivo principal:

```text
sanjuanero-node\server.js
```

Funciones:

```text
buildPrompt()
buildTwoPersonPrompt()
```

Ahí están las descripciones de prendas, colores, mochila, sombrero, calzado,
anatomía y encuadre. La referencia visual del vestido femenino es
`REF_VESTIDO_MUJER`.

Para cambiar solo el vestido sin alterar la pose:

1. Reemplazar `vestido_mujer.jpg`.
2. Mantener las referencias de pose sin cambios.
3. Ajustar únicamente el bloque de vestuario en los prompts.
4. No mezclar instrucciones contradictorias de pose en la referencia de ropa.

### Cambiar poses

Constantes:

```text
REF_MUJER
REF_HOMBRE
REF_DOS_HOMBRES
REF_DOS_MUJERES
REF_PAREJA_MIXTA
```

Lógica y descripciones:

```text
classifyPair()
buildPrompt()
buildTwoPersonPrompt()
```

Las imágenes de pose deben mostrar cuerpos completos, manos visibles, poco
solapamiento y rostros suficientemente grandes. Para dos personas conviene
mantener separación entre cabezas y manos.

### Cambiar o mejorar rostros

Archivos:

```text
fastsdcpu-main\sanjuanero\face_preserve.py
sanjuanero-node\scripts\preserve_face.py
sanjuanero-node\scripts\extract_head_reference.py
```

Puntos importantes:

- `sliderToIdentityStrength()` en `server.js` traduce el control del frontend.
- `_pick_dest_faces()` elige las caras generadas.
- `_match_faces()` asigna cada origen a su destino.
- `_head_crop_box()` controla el recorte de alta resolución.
- `_face_region_mask()` controla cuánto rostro se mezcla.
- `_swap_on_image()` ejecuta actualmente dos pases de InSwapper.

No reemplazar `inswapper_128.onnx` por un modelo 256/512 esperando
compatibilidad directa. HyperSwap y SimSwap usan arquitecturas, entradas y
preprocesamientos diferentes; requieren implementar otro adaptador.

### Cambiar detección de personas, edad o gafas

Archivo:

```text
sanjuanero-node\scripts\analyze_photo.py
```

Ahí se encuentran:

- umbral para descartar rostros pequeños del fondo;
- límite actual de dos rostros;
- clasificación de edad;
- género aparente;
- FaceAttribNet para gafas.

Estas predicciones son estimaciones y deben poder corregirse manualmente.

### Cambiar frontend

```text
public\index.html     # estructura y opciones
public\styles.css     # diseño
public\app.js         # análisis, selección automática y llamadas al API
```

### Cambiar resolución, pasos o guidance

En `server.js`, función:

```text
buildFastSDBody()
```

Valores actuales:

```js
image_height: 512
image_width: 384
inference_steps: isTwoPerson ? 8 : 6
guidance_scale: 1.0
```

Cambiar una variable a la vez y conservar resultados comparables. Más pasos no
garantizan mejor identidad; la identidad depende principalmente del modelo de
edición, el tamaño del rostro y el posprocesamiento.

## 12. Cambiar el modelo generativo

### Otro modelo OpenVINO compatible con FastSD

Si el modelo soporta `edit_image` y múltiples imágenes en el mismo formato:

1. Cambiar `MODEL_ID` en `server.js`.
2. Actualizar `openvino_lcm_model_id` en
   `fastsdcpu-main\configs\settings.yaml` si también se usa FastSD directamente.
3. Si se usa la interfaz Gradio, revisar `sanjuanero\generate.py`.
4. Confirmar que `buildFastSDBody()` utiliza los campos esperados.
5. Probar primero una persona.
6. Probar después dos personas y todas las combinaciones.
7. Verificar resolución, pasos, guidance y formato de respuesta.

No basta con que un repositorio sea “FLUX”: debe ser compatible con la rama de
edición y el pipeline instalado en FastSD.

### Qwen-Image-Edit-2511

Es el candidato recomendado para mejorar identidad y consistencia de varias
personas. No es un reemplazo de una línea para el modelo OpenVINO actual.
Requiere:

- un backend Qwen con PyTorch/Diffusers o ComfyUI;
- CUDA si se quiere aprovechar una GPU NVIDIA;
- cambiar `startFastSD()` o ejecutar Qwen como servicio independiente;
- cambiar `buildFastSDBody()` al esquema de Qwen;
- adaptar `postFastSD()` y `decodeFastSDImage()` si cambia la respuesta;
- volver a validar el orden de las referencias.

La variante Q4 ocupa aproximadamente 13 GB. Para trabajar cómodamente se
recomiendan 16–24 GB de VRAM; BF16 requiere alrededor de 40 GB.

### FLUX.2 Dev

Modelo de 32B con mejor calidad y edición multirreferencia. Cuantizado a 4 bits
puede funcionar con aproximadamente 20–24 GB de VRAM y offload. La licencia
`dev` debe revisarse antes de uso comercial.

### FLUX.2 Klein 9B

Es una transición más cercana a la familia actual. Aun así, hay que conseguir
una exportación compatible con el backend elegido y comprobar soporte real de
edición multirreferencia.

### NVIDIA frente a OpenVINO

El proyecto actual usa `use_openvino: true`. Para NVIDIA, normalmente se debe
cambiar a un backend CUDA. Instalar una RTX potente sin cambiar el pipeline no
garantiza que se use esa GPU.

## 13. Resultados y privacidad

`sanjuanero-node\results` guarda:

```text
original_<fecha>.jpg                # fotografía subida
sanjuanero_<fecha>_cuerpo.jpg       # salida antes del rostro
sanjuanero_<fecha>_face.jpg         # salida del intercambio
sanjuanero_<fecha>.jpg              # resultado final
```

Los recortes temporales de cabeza se eliminan, pero los originales y resultados
permanecen. En producción hay que implementar retención automática y solicitar
consentimiento para procesar rostros, especialmente cuando aparezcan menores.

## 14. API local

### Estado

```http
GET /api/status
```

### Analizar fotografía

```http
POST /api/analyze-photo
Content-Type: multipart/form-data
photo=<archivo>
```

### Generar

```http
POST /api/generate
Content-Type: multipart/form-data
photo=<archivo>
costume=mujer|hombre
peopleCount=1|2
pairType=dos_mujeres|dos_hombres|pareja_mixta|adulto_nino
strength=0.15..0.50
```

El servidor vuelve a analizar la fotografía y puede corregir automáticamente
`peopleCount`.

## 15. Pruebas mínimas antes de entregar

Probar por separado:

1. Una mujer sin gafas.
2. Una mujer con gafas.
3. Un hombre calvo o de cabello muy corto.
4. Un hombre con gafas.
5. Dos mujeres.
6. Dos hombres.
7. Pareja mixta.
8. Adulto con niño.
9. Foto con personas pequeñas en el fondo.
10. Foto sin rostro o con rostro poco visible.

En cada prueba revisar:

- cantidad de cuerpos;
- asignación correcta de identidades;
- gafas y cabello;
- manos, dedos y pies;
- pose;
- vestido y mochila;
- tiempo total;
- archivos generados;
- consumo de RAM/VRAM.

## 16. Solución de problemas

### Solo genera una persona

- Confirmar que el frontend muestre dos rostros principales.
- Revisar el log `Personas detectadas: 2`.
- Reiniciar Node después de modificar `server.js`.
- Confirmar que `extract_head_reference.py` reciba dos rutas de salida.

### El rostro no se parece

- Usar fotografías nítidas, frontales y bien iluminadas.
- Evitar rostros pequeños.
- Confirmar que InSwapper esté cargado.
- Comparar el archivo `_cuerpo.jpg` con `_face.jpg`.
- Recordar el límite de InSwapper 128.
- Considerar Qwen-Image-Edit-2511 o un face swapper de mayor resolución.

### Gafas en la persona equivocada

- Verificar `hasGlasses` en la salida de `analyze_photo.py`.
- Confirmar que exista `face_attrib_net.onnx`.
- Revisar el orden de las referencias de cabeza.

### FastSD no inicia

- Confirmar `FASTSD_PYTHON` y `FASTSD_APP`.
- Probar manualmente `python src/app.py --api --port 8000`.
- Si Windows no encuentra DLL de OpenVINO, añadir temporalmente
  `env\Lib\site-packages\openvino\libs` a `PATH`.
- Comprobar que el puerto 8000 esté libre.
- Revisar espacio en disco, RAM y descarga del modelo.

### La aplicación no inicia

- Comprobar Node 18+.
- Ejecutar `npm ci`.
- Comprobar que el puerto 3000 esté libre.
- Revisar las rutas absolutas.

## 17. Recomendación para una versión de producción

Antes de publicar para usuarios reales:

1. Eliminar todas las rutas absolutas y usar variables de entorno.
2. Mover referencias a `sanjuanero-node\references`.
3. Crear una cola: procesar una generación a la vez.
4. Añadir autenticación y HTTPS.
5. No devolver imágenes grandes como base64; usar archivos con acceso seguro.
6. Eliminar originales automáticamente.
7. Añadir pruebas automatizadas del API.
8. Registrar versión del modelo, seed, pasos y tiempos.
9. Separar el backend de IA del servidor web.
10. Revisar licencias y política de datos biométricos.
