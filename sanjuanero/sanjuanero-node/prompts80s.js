/**
 * Prompts de "retrato de los años 80". Escritos para img2img.
 *
 * Del proyecto del profesor se reutiliza la estructura (Node controla el
 * flujo, un motor genera, InsightFace pega la cara real) pero no sus prompts.
 * Los suyos eran ORDENES de edición ("dress him in a blazer"), que es lo que
 * quiere instruct-pix2pix. Con img2img eso falla: el modelo obedece la orden
 * literalmente y genera la prenda sola, sin la persona.
 *
 * img2img quiere una DESCRIPCIÓN de la fotografía que queremos obtener. Parte
 * de la foto real con ruido controlado, así que la composición se conserva
 * por construcción y la intensidad se regula con un solo número, la fuerza.
 *
 * Tres reglas que salieron de probar sobre fotos reales:
 *
 * 1. Describir, nunca ordenar. "1985 studio portrait of a young man with
 *    feathered hair", no "give him feathered hair".
 * 2. Empezar por lo que define la imagen (época, tipo de foto, sujeto). Lo
 *    que va al principio pesa más.
 * 3. Mandar al prompt negativo lo que hay que quitar de la foto original
 *    -cascos, auriculares, ropa moderna-. Describir su ausencia no funciona.
 */

// Estética fotográfica, común a todos los estilos.
const PELICULA =
    "direct flash, soft focus glow, warm Kodak Gold film grain, " +
    "vintage 35mm mall portrait photograph, slight color cast";

const FONDO =
    "mottled blue-grey studio backdrop with soft pink and cyan laser beams";

const PELO_HOMBRE = "voluminous feathered 1980s hair";
const PELO_MUJER = "big voluminous feathered 1980s hair with lots of hairspray";

const ROPA_HOMBRE =
    "wide-collared shirt under a blazer with padded shoulders";
const ROPA_MUJER =
    "pastel blouse with a wide collar under a boxy blazer with padded " +
    "shoulders, large gold statement earrings";

/**
 * Lo que hay que sacar de la foto: objetos modernos que el modelo conservaría
 * porque forman parte de la composición, más los defectos habituales.
 */
const NEGATIVO =
    "headphones, headset, gaming headset, microphone, earbuds, " +
    "bare shoulders, tank top, t-shirt, modern clothing, smartphone, " +
    "webcam, computer screen, deformed face, distorted face, extra faces, " +
    "two heads, blurry, lowres, text, watermark, cartoon, 3d render";

function _persona(identityPerson, costume) {
    const esHombre = costume === "hombre";
    const sujeto = esHombre ? "a young man" : "a young woman";
    const pelo = esHombre ? PELO_HOMBRE : PELO_MUJER;
    const ropa = esHombre ? ROPA_HOMBRE : ROPA_MUJER;

    // Las gafas solo se mencionan si las lleva: nombrarlas para negarlas
    // hace que el modelo las dibuje igual.
    const gafas = identityPerson && identityPerson.hasGlasses
        ? ", wearing large 1980s eyeglasses with thin gold frames"
        : "";

    return `${sujeto} with ${pelo}${gafas}, wearing a ${ropa}`;
}

/** Misma firma que buildPrompt() en server.js. */
function buildPrompt80s(costume, _hasIdentityRef, _hasCostumeRef, identityPerson) {
    return (
        `1985 studio portrait photograph of ${_persona(identityPerson, costume)}, ` +
        `centered waist-up portrait facing the camera, ${FONDO}, ${PELICULA}`
    );
}

/** Misma firma que buildTwoPersonPrompt() en server.js. */
function buildTwoPersonPrompt80s(pairType, people, _hasCostumeRef) {
    const sujeto =
        pairType === "adulto_nino" ? "an adult and a child"
        : pairType === "pareja_mixta" ? "a young man and a young woman"
        : pairType === "dos_hombres" ? "two young men"
        : "two young women";

    const gafas = people.some(p => p.hasGlasses)
        ? ", one of them wearing large 1980s eyeglasses"
        : "";

    return (
        `1985 studio portrait photograph of ${sujeto} posing side by side${gafas}, ` +
        "both with voluminous feathered 1980s hair and 1980s clothing with " +
        `padded shoulders and wide collars, centered waist-up portrait ` +
        `facing the camera, ${FONDO}, ${PELICULA}`
    );
}

module.exports = {
    buildPrompt80s,
    buildTwoPersonPrompt80s,
    NEGATIVO_80S: NEGATIVO
};
