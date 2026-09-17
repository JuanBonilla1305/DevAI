/**
 * Banco de escenas ochenteras.
 *
 * La idea no es una foto siempre igual, sino muchas variantes del mismo
 * estilo. Cada generación combina al azar cuatro piezas independientes
 * -encuadre, peinado, vestuario y ambiente- así que el número de escenas
 * posibles es el producto de las cuatro listas, no la suma.
 *
 * La escena se genera entera desde el texto, sin partir de la foto: solo así
 * puede cambiar la pose y el cuerpo. La cara real se pega después con
 * InSwapper, que es lo que hace que siga siendo la misma persona.
 *
 * Referencia visual: la estética de estudio ochentera con fondo cálido,
 * sombras de persiana, radiocasete, palmeras y colores magenta y turquesa.
 */

// ---------------------------------------------------------------------
// Piezas comunes
// ---------------------------------------------------------------------

const CALIDAD =
    "authentic 1985 color photograph, shot on 35mm film, warm analog color " +
    "grading, fine film grain, studio lighting, sharp focus on the face, " +
    "photorealistic";

// Lo que hay que evitar. SD 1.5 falla sobre todo en manos y en caras
// pequeñas, así que se nombran explícitamente.
const NEGATIVO =
    "extra fingers, missing fingers, deformed hands, mutated hands, " +
    "deformed face, distorted face, extra faces, two heads, extra limbs, " +
    "modern clothing, hoodie, smartphone, headphones, headset, " +
    "blurry, lowres, jpeg artifacts, text, watermark, signature, " +
    "cartoon, 3d render, illustration, painting, " +
    // Todo lo que empuje el plano hacia atras: las escenas son de cintura
    // para arriba y el modelo tiende a alejarse si ve piernas o calzado.
    "full body, legs, knees, feet, shoes, trousers, wide shot, distant figure, " +
    "small face, face in shadow, back turned, profile view";

// SD 1.5 se va de género con facilidad: con un chaleco de rombos o una
// melena con volumen dibuja una mujer aunque el prompt diga "a man". Hay que
// insistir en el sujeto y negar el género contrario de forma explícita.
const NEGATIVO_HOMBRE = ", woman, female, feminine face, long eyelashes, lipstick, makeup, dress, skirt, breasts";
const NEGATIVO_MUJER = ", man, male, masculine face, beard, moustache, stubble, flat chest";

// ---------------------------------------------------------------------
// Encuadres
// ---------------------------------------------------------------------
//
// El plano entero es el de la referencia, pero conviene mezclarlo: cuanto
// más lejos está la persona, más pequeña sale la cara y peor la dibuja el
// modelo. Los planos medios dan caras mejores y el intercambio encaja mejor.

// Todos los encuadres son de cintura para arriba. La variedad está en la
// pose y en los brazos, no en la distancia.
//
// Además de ser lo que se pidió, ayuda al parecido: InSwapper trabaja a
// 128x128, así que cuantos más píxeles ocupe la cara en la imagen generada,
// mejor se transfiere la identidad. En un plano entero la cara acababa
// ocupando cuarenta o cincuenta píxeles y el parecido se perdía.
//
// Se repite en todos "face clearly visible and well lit": sin eso el modelo
// tiende a poner la cara en sombra o de perfil, y entonces el intercambio
// no encuentra rostro y se salta.
const CARA = "looking straight at the camera, face clearly visible and well lit";

const ENCUADRES = [
    { nombre: "brazos_cruzados", texto: `waist-up shot, arms crossed, confident relaxed posture, slight smile, ${CARA}` },
    { nombre: "manos_bolsillos", texto: `waist-up shot, thumbs hooked in the pockets, shoulders squared, ${CARA}` },
    { nombre: "cuello", texto: `waist-up shot, one hand adjusting the collar of the jacket, ${CARA}` },
    { nombre: "apoyado", texto: `waist-up shot leaning back against the wall, arms loosely crossed, ${CARA}` },
    { nombre: "gafas", texto: `waist-up shot, one hand lowering the sunglasses slightly, amused expression, ${CARA}` },
    { nombre: "pecho", texto: `chest-up portrait, head tilted slightly, face large in the frame, ${CARA}` },
    { nombre: "hombro", texto: `waist-up shot turned slightly to one side with the head facing forward, one hand on the hip, ${CARA}` },
    { nombre: "mano_pelo", texto: `waist-up shot, one hand running through the hair, relaxed smile, ${CARA}` },
    { nombre: "brazo_alzado", texto: `waist-up shot with one forearm resting on a raised surface, body turned slightly, ${CARA}` },
];
// Se descartó un encuadre "sentado en un taburete": aunque el texto pidiera
// cintura para arriba, la pose arrastra piernas y el modelo abría el plano
// para encajarlas, incluso con "legs" y "knees" en el prompt negativo. Una
// pose que implica el cuerpo entero pesa más que la instrucción de encuadre.

// ---------------------------------------------------------------------
// Ambientes
// ---------------------------------------------------------------------

const AMBIENTES = [
    { nombre: "estudio_calido", texto: "in a 1980s photo studio set with a warm amber background, hard venetian blind shadows across the wall, a potted palm and a chrome boombox on a magenta pedestal" },
    { nombre: "neon_calle", texto: "on a neon-lit city street at night, glowing pink and cyan neon signs, wet asphalt reflecting the lights, blurred city bokeh behind" },
    { nombre: "atardecer_miami", texto: "against a painted Miami sunset backdrop with palm trees, pink and orange sky, turquoise and magenta geometric shapes" },
    { nombre: "arcade", texto: "inside a 1980s video arcade, glowing arcade cabinets behind, dark room lit by screens in cyan and magenta" },
    { nombre: "cuadricula", texto: "in front of a retro studio backdrop of a purple laser grid horizon and a huge setting sun, haze in the air, magenta and teal rim lighting" },
    { nombre: "coche", texto: "leaning on the hood of a boxy 1980s sports car at dusk, warm orange sky, lens flare from the streetlights" },
];

// ---------------------------------------------------------------------
// Hombre
// ---------------------------------------------------------------------

const PELO_HOMBRE = [
    "a voluminous 1980s mullet, short on top and long at the back, with a thick moustache",
    "big feathered 1980s hair blow-dried with volume at the crown, and a moustache with a goatee",
    "curly permed 1980s hair with lots of volume, clean shaven",
    "slicked-back 1980s hair with wings at the sides, and a trimmed moustache",
];

// Solo prendas que se ven de cintura para arriba: nombrar pantalones o
// zapatos empuja al modelo a abrir el plano para encajarlos.
const ROPA_HOMBRE = [
    "an acid-wash denim jacket with magenta and teal colour-blocked panels, open over a teal graphic t-shirt printed with a sunset and palm trees, a gold chain",
    "a pastel blazer with heavy padded shoulders and rolled-up sleeves over a white t-shirt, a thin leather tie",
    "a red leather bomber jacket with zips over a black t-shirt, a gold chain",
    "a turquoise and purple windbreaker track jacket with bold geometric stripes over a white t-shirt",
    "a knitted argyle sweater vest over a wide-collared striped shirt",
    "a pale blue denim jacket with the collar up over a white polo shirt, aviator sunglasses hanging from the neckline",
];

const GAFAS_HOMBRE = [
    "wearing tinted aviator sunglasses",
    "wearing large square 1980s sunglasses",
    "",
    "",
];

// ---------------------------------------------------------------------
// Mujer
// ---------------------------------------------------------------------

const PELO_MUJER = [
    "huge permed 1980s hair teased high with lots of volume and hairspray",
    "big feathered 1980s hair with voluminous layers framing the face",
    "crimped 1980s hair with a colourful scrunchie and a side ponytail",
    "voluminous 1980s curls with a wide patterned headband",
];

const ROPA_MUJER = [
    "an oversized acid-wash denim jacket with magenta and teal panels over a bright turquoise top, huge gold hoop earrings",
    "a bright pink blazer with enormous padded shoulders over a white blouse, gold statement earrings",
    "a turquoise off-the-shoulder sweatshirt, chunky plastic bangles, big hoop earrings",
    "a purple satin blouse with a wide collar and heavy shoulder pads, a gold chain necklace",
    "a magenta and teal geometric-print top with padded shoulders, chunky colourful jewellery",
    "a white blouse with a huge ruffled collar under a teal cropped jacket, pearl earrings",
];

const GAFAS_MUJER = [
    "wearing oversized 1980s sunglasses",
    "",
    "",
    "",
];

// ---------------------------------------------------------------------

function _elegir(lista, aleatorio) {
    return lista[Math.floor(aleatorio() * lista.length)];
}

/**
 * Generador reproducible. Con la misma semilla sale la misma escena, lo que
 * permite repetir un resultado que gustó.
 */
function _aleatorio(semilla) {
    let estado = semilla >>> 0 || 1;
    return function () {
        estado ^= estado << 13; estado >>>= 0;
        estado ^= estado >> 17;
        estado ^= estado << 5;  estado >>>= 0;
        return estado / 4294967296;
    };
}

/**
 * Compone una escena al azar.
 *
 * @param {"hombre"|"mujer"} genero
 * @param {number} [semilla] para repetir una escena concreta
 * @returns {{prompt: string, negativo: string, receta: object}}
 */
function escena80s(genero, semilla) {
    const usada = Number.isFinite(semilla)
        ? semilla
        : Math.floor(Math.random() * 2147483647);
    const azar = _aleatorio(usada);

    const esHombre = genero !== "mujer";
    // El género se repite al principio y al final del prompt: es donde más
    // pesa, y sin esa insistencia el modelo lo cambia a mitad de escena.
    const sujeto = esHombre
        ? "a man, masculine, male model"
        : "a woman, feminine, female model";

    const encuadre = _elegir(ENCUADRES, azar);
    const ambiente = _elegir(AMBIENTES, azar);
    const pelo = _elegir(esHombre ? PELO_HOMBRE : PELO_MUJER, azar);
    const ropa = _elegir(esHombre ? ROPA_HOMBRE : ROPA_MUJER, azar);
    const gafas = _elegir(esHombre ? GAFAS_HOMBRE : GAFAS_MUJER, azar);

    const partes = [
        `${CALIDAD.split(",")[0]} of ${sujeto} with ${pelo}`,
        `wearing ${ropa}`,
        gafas,
        encuadre.texto,
        ambiente.texto,
        CALIDAD,
        esHombre ? "a masculine man" : "a feminine woman",
    ].filter(Boolean);

    return {
        prompt: partes.join(", "),
        negativo: NEGATIVO + (esHombre ? NEGATIVO_HOMBRE : NEGATIVO_MUJER),
        receta: {
            semilla: usada,
            genero: esHombre ? "hombre" : "mujer",
            encuadre: encuadre.nombre,
            ambiente: ambiente.nombre,
        },
    };
}

/** Cuántas escenas distintas puede producir el banco. */
function totalCombinaciones() {
    const porGenero = (pelo, ropa, gafas) =>
        ENCUADRES.length * AMBIENTES.length * pelo * ropa * gafas;
    return {
        hombre: porGenero(PELO_HOMBRE.length, ROPA_HOMBRE.length, new Set(GAFAS_HOMBRE).size),
        mujer: porGenero(PELO_MUJER.length, ROPA_MUJER.length, new Set(GAFAS_MUJER).size),
    };
}

module.exports = { escena80s, totalCombinaciones, NEGATIVO_80S: NEGATIVO };
