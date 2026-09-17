/**
 * Prompts para el motor FLUX.2 Klein (el backend original del profesor).
 *
 * Aquí el modelo NO se inventa la escena: recibe imágenes de entrada y las
 * edita. Eso es lo que conserva el parecido, porque entre esas imágenes van
 * los recortes de la cabeza real de la persona. Por eso el prompt tiene que
 * ser una INSTRUCCIÓN que diga qué imagen controla qué, no la descripción de
 * una fotografía inventada.
 *
 * Orden de las imágenes que envía server.js:
 *   1ª  la fotografía de la persona: manda el encuadre y la postura
 *   2ª  el recorte de la cabeza: manda la identidad y el pelo
 *  (3ª) referencia de vestuario, solo en el tema sanjuanero
 *
 * Referencia visual: la foto familiar colombiana de los años 80, con el color
 * virado del revelado de barrio y un exterior de patio o jardín.
 */

const AMBIENTE =
    "Place the person outdoors in 1980s Colombia: beside a big leafy tree " +
    "with green grass, a whitewashed or red brick house behind, and a " +
    "bougainvillea in bloom.";

const PELICULA =
    "Make it look like an authentic 1985 amateur color snapshot: faded " +
    "washed-out colors with a warm magenta shift, soft focus, slight " +
    "overexposure, visible film grain, direct on-camera flash. " +
    "Photorealistic, no text and no watermark.";

const ENCUADRE =
    "Keep it a waist-up photograph with the person centered and facing the " +
    "camera, the face clearly visible and well lit.";

/** Lo que conserva el parecido. Es la parte que no se debe tocar. */
function identidad(hasIdentityReference, identityPerson) {
    const gafas = identityPerson
        ? identityPerson.hasGlasses
            ? `Keep the ${identityPerson.glassesType === "sunglasses"
                ? "sunglasses" : "eyeglasses"} the person is wearing, ` +
              "restyled as 1980s frames."
            : "The person wears no eyeglasses and no sunglasses."
        : "";

    if (!hasIdentityReference) {
        return "Keep the person's face exactly as it is.";
    }

    return (
        "The second input image controls the person's identity: keep that " +
        "exact face, bone structure and skin tone, without changing them. " +
        "Restyle only the hair into a 1980s look, keeping its original " +
        "color and texture, just fuller and with more volume. If the person " +
        "is bald or has very short hair, keep it that way. " + gafas
    );
}

const ROPA_HOMBRE =
    "Dress him in everyday 1980s Colombian menswear: a short-sleeved " +
    "checked shirt buttoned to the top, or a white guayabera, or a dark " +
    "blazer over a wide-collared shirt.";

const ROPA_MUJER =
    "Dress her in everyday 1980s Colombian womenswear: a white blouse with " +
    "shoulder pads and a wide collar, or a cardigan over a floral blouse, " +
    "with small gold earrings.";

const ROPA_NINO =
    "Dress the child in everyday 1980s clothing: a small collared shirt or " +
    "a knitted sweater. No moustache, no beard.";

/**
 * Elige el vestuario. Manda lo que seleccionó el usuario; la detección de
 * edad solo decide cuando no se ha pedido nada explícito, porque estimar si
 * alguien es un niño falla con facilidad y no debe pisar una elección.
 */
function _ropa(costume, identityPerson) {
    if (costume === "nino") return ROPA_NINO;
    if (costume === "hombre") return ROPA_HOMBRE;
    if (costume === "mujer") return ROPA_MUJER;

    if (identityPerson && identityPerson.ageGroup &&
        identityPerson.ageGroup !== "adulto") {
        return ROPA_NINO;
    }
    return ROPA_MUJER;
}

/** Misma firma que buildPrompt() en server.js. */
function buildPrompt80s(costume, hasIdentityReference, _hasCostumeRef, identityPerson) {
    return [
        "Turn this photograph into a 1980s Colombian family photograph.",
        "The first input image controls the framing and the posture.",
        identidad(hasIdentityReference, identityPerson),
        _ropa(costume, identityPerson),
        ENCUADRE,
        AMBIENTE,
        PELICULA,
    ].join("\n");
}

/** Misma firma que buildTwoPersonPrompt() en server.js. */
function buildTwoPersonPrompt80s(pairType, people, _hasCostumeRef) {
    const identidades = people
        .map((person, index) => {
            const gafas = person.hasGlasses
                ? `keeping the ${person.glassesType === "sunglasses"
                    ? "sunglasses" : "eyeglasses"} restyled as 1980s frames`
                : "wearing no eyeglasses";
            const quien = person.ageGroup && person.ageGroup !== "adulto"
                ? "a child"
                : person.gender === "mujer" ? "a woman" : "a man";
            return (
                `input image ${index + 2}: ${quien}, ${gafas}, keeping that ` +
                "exact face, skin tone and natural hair, restyled into 1980s " +
                "volume but the same color and texture"
            );
        })
        .join("; ");

    const escena =
        pairType === "dos_ninos" ? "two children"
        : pairType === "adulto_nino" ? "an adult and a child"
        : pairType === "pareja_mixta" ? "a man and a woman"
        : pairType === "dos_hombres" ? "two men"
        : "two women";

    const sinVello = pairType === "dos_ninos"
        ? " No moustache, no beard on either child."
        : "";

    return [
        `Turn this photograph into a 1980s Colombian family photograph of ${escena}.`,
        "The first input image controls the framing and the posture.",
        `Identities: ${identidades}.`,
        (pairType === "dos_ninos"
            ? "Dress them in everyday 1980s children's clothing: small " +
              "collared shirts or knitted sweaters."
            : "Dress them in everyday 1980s Colombian clothing with wide " +
              "collars and shoulder pads.") + sinVello,
        "Keep it a waist-up photograph of exactly two people side by side, " +
        "their heads clearly separated, both faces visible and well lit, " +
        "both facing the camera.",
        AMBIENTE,
        PELICULA,
    ].join("\n");
}

module.exports = { buildPrompt80s, buildTwoPersonPrompt80s };
