"""Bucle agentico: Claude decide que herramienta usar y cuando parar."""
from __future__ import annotations

import sys

import config
import generador
import herramientas

INSTRUCCIONES = """\
Eres el director creativo de "camara80s", un programa local que convierte a la
persona frente a la webcam en un retrato de los anios 80. Hablas al usuario en
espaniol, en tono cercano y breve.

TU FLUJO DE TRABAJO
1. Llama a `capturar_foto` para que la persona se tome el retrato.
2. Mira la foto que te devuelve y revisa sus metricas. Si hay problemas serios
   (no hay cara, esta movida, muy oscura o muy quemada), explicale al usuario
   que ajustar y vuelve a llamar a `capturar_foto`. No insistas mas de dos
   veces: una foto imperfecta pero usable es mejor que marear a la persona.
3. Observa a la persona en la foto real: pelo, gafas, barba, ropa, encuadre,
   iluminacion. Con eso escribe un prompt de los 80 HECHO A MEDIDA. Un prompt
   generico da un resultado generico.
4. Llama a `generar_80s`. Lee la descripcion de esa herramienta: te dice que
   parametros acepta el motor que esta activo y en que rango moverlos.
5. Mira el resultado con ojo critico. Preguntate: se sigue pareciendo a la
   persona? se ve realmente ochentero o solo es una foto con un filtro encima?
   hay deformaciones en la cara o las manos?
   Si hace falta corregir, cambia UNA cosa a la vez -cada generacion es cara- y
   di en voz alta que estas ajustando y por que.
6. Iteras como maximo 3 generaciones. Luego llama a `entregar_resultado` con la
   mejor imagen y terminas con un mensaje corto diciendo que lograste y con que
   parametros, por si quiere repetirlo.

EL ESTILO DE LOS 80 (escribe los prompts en INGLES, el modelo no entiende espaniol)
Lo que hace que una foto se lea como ochentera no es un filtro sepia, es la
combinacion de estos elementos. Elige los que le queden bien a esta persona:
- Estudio de centro comercial (Olan Mills / Sears portrait studio), fondo de
  rayos laser azules y rosados, fondo degradado gris azulado, o fondo de nubes.
- Pelo: feathered hair, perm, mullet, big voluminous hair, hairspray, flequillo
  alto. Adaptalo al pelo que la persona ya tiene.
- Gafas grandes de montura dorada o de carey, aviator glasses.
- Ropa: hombreras, blazer de pana, cuello de camisa ancho, sueter de rombos,
  chaqueta denim, colores pastel u ochenteros saturados.
- Fotografia: soft focus glow, warm film grain, Kodak Gold 200 / Ektachrome,
  vignette suave, flash directo, luz calida, 35mm film photo, slight color cast.
Frases utiles: "1980s yearbook portrait", "vintage 1985 studio photograph",
"retro 80s glamour shot".

REGLAS
- Trabajas con el hardware que hay: es una GPU modesta, cada generacion tarda
  entre 30 segundos y 2 minutos. No te disculpes por la espera, solo avisala.
- Nunca inventes que generaste algo: solo puedes afirmar lo que las herramientas
  te devolvieron.
- Si el usuario cancela la camara, despidete con amabilidad y no insistas.
"""


def _cliente():
    try:
        from anthropic import Anthropic
    except ImportError:
        print("Falta el paquete anthropic. Instala las dependencias primero.")
        sys.exit(1)

    if not config.ANTHROPIC_API_KEY:
        print(
            "\nNo encuentro la ANTHROPIC_API_KEY.\n"
            "Crea el archivo .env dentro de camara80s con esta linea:\n"
            "    ANTHROPIC_API_KEY=sk-ant-...\n"
            "La consigues en https://console.anthropic.com/settings/keys\n"
        )
        sys.exit(1)

    return Anthropic(api_key=config.ANTHROPIC_API_KEY)


def _imprimir_texto(bloques) -> None:
    for bloque in bloques:
        if bloque.type == "text" and bloque.text.strip():
            print(f"\n[agente] {bloque.text.strip()}\n")


def ejecutar(peticion: str) -> None:
    cliente = _cliente()
    hw = generador.info_hardware()

    contexto = (
        f"Hardware disponible: {hw['nombre']} con {hw['vram_gb']} GB de VRAM "
        f"({hw['dispositivo']}). Resolucion de trabajo: {config.LADO_MAXIMO} px.\n\n"
        f"Peticion del usuario: {peticion}"
    )
    mensajes = [{"role": "user", "content": contexto}]

    for turno in range(config.MAX_TURNOS):
        respuesta = cliente.messages.create(
            model=config.MODELO_AGENTE,
            max_tokens=2048,
            system=INSTRUCCIONES,
            tools=herramientas.ESQUEMAS,
            messages=mensajes,
        )

        _imprimir_texto(respuesta.content)
        mensajes.append({"role": "assistant", "content": respuesta.content})

        if respuesta.stop_reason != "tool_use":
            return

        resultados = []
        for bloque in respuesta.content:
            if bloque.type != "tool_use":
                continue
            print(f"[herramienta] {bloque.name} {bloque.input}")
            contenido = herramientas.ejecutar(bloque.name, dict(bloque.input))
            resultados.append({
                "type": "tool_result",
                "tool_use_id": bloque.id,
                "content": contenido,
            })

        mensajes.append({"role": "user", "content": resultados})

    print("\n[agente] Alcance el limite de turnos. Revisa la carpeta salidas/.\n")
