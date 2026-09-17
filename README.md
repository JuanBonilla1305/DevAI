# DevAI

Registro de trabajo sobre generación local de retratos con IA. Dos proyectos
que comparten la misma idea —cámara → preservar la identidad → generar— pero
la resuelven de forma distinta.

```
camara80s/    retrato de los años 80, GPU NVIDIA, agente con Claude
sanjuanero/   proyecto base del profesor, CPU/OpenVINO, en adaptación a los 80
```

## camara80s

Tomas una foto con la webcam y un agente la convierte en un retrato ochentero.
El agente (Claude con cuatro herramientas) *ve* la foto, decide si sirve,
escribe la instrucción a medida de tu pelo y tus gafas, genera, *mira el
resultado* y ajusta. Dos motores intercambiables:

- **FLUX.1 Kontext** en GGUF Q4, con offload secuencial para caber en 6 GB de VRAM
- **Stable Diffusion 1.5** (`instruct-pix2pix`), más rápido y de menor calidad

También trae un modo `--directo` sin agente ni APIs, para probar el motor solo.

Detalles en [camara80s/README.md](camara80s/README.md).

## sanjuanero

Proyecto entregado por el profesor: transforma fotos en escenas del baile
Sanjuanero Huilense. Node.js en el frontend, FastSD CPU + OpenVINO + FLUX.2
Klein 4B en el backend, e InsightFace para el intercambio facial.

Su arquitectura resuelve el parecido mejor que `camara80s`: en vez de pedirle
al modelo que conserve la cara, genera el cuerpo y el vestuario y *después*
pega la cara real con InSwapper.

- [sanjuanero/sanjuanero-node/README.md](sanjuanero/sanjuanero-node/README.md) — documentación original
- `sanjuanero/sanjuanero-node/prompts80s.js` — adaptación a los años 80 en curso

## Lo que no está en este repositorio

Por tamaño o por privacidad. El código los espera en estas rutas:

| Qué | Dónde va | De dónde sale |
|---|---|---|
| `inswapper_128.onnx` (529 MB) | `sanjuanero/fastsdcpu/sanjuanero/models/` | Hugging Face, `ezioruan/inswapper_128.onnx` |
| `buffalo_l` (InsightFace) | `%USERPROFILE%\.insightface\models\` | Se descarga solo al primer uso |
| FLUX.2 Klein 4B INT4 (4,3 GB) | caché de Hugging Face | Se descarga sola, `rupeshs/flux2-klein-4b-int4-ov` |
| FLUX.1 Kontext GGUF (6,8 GB) | caché de Hugging Face | `QuantStack/FLUX.1-Kontext-dev-GGUF` |
| Entornos y `node_modules` | `env/`, `.venv/`, `node_modules/` | `pip install -r requirements.txt`, `npm ci` |

Tampoco se versionan las carpetas `results/`, `capturas/` ni `salidas/`:
contienen fotografías de personas reales.

## Entorno de desarrollo

- Windows 11, RTX 3050 Laptop (6 GB VRAM), 16 GB RAM
- `camara80s` usa Python 3.12 con PyTorch CUDA
- `sanjuanero` usa Python 3.11 (versiones clavadas en su `requirements.txt`) y Node 18+
