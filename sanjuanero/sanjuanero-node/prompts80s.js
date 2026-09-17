/**
 * Prompts para la version "retrato de los anios 80".
 *
 * Reemplazan a buildPrompt() y buildTwoPersonPrompt() de server.js, con la
 * misma firma, para poder cambiar de tema sin tocar el resto del servidor.
 *
 * Dos decisiones de encuadre, y el motivo de cada una:
 *
 * 1. Encuadre de medio cuerpo (de la cintura para arriba), no cuerpo entero.
 *    InSwapper trabaja internamente a 128x128: cuanto mas pequenia sale la
 *    cara en la imagen generada, peor queda el intercambio. El propio README
 *    del proyecto lo advierte. En un retrato de estudio la cara ocupa mucho
 *    mas encuadre, asi que el parecido final mejora bastante.
 *
 * 2. Retrato de estudio de centro comercial, no una escena de calle.
 *    Es el formato que la gente reconoce como "foto de los 80": fondo de
 *    laser o degradado, flash directo, brillo suave. Ademas simplifica la
 *    imagen: sin manos ni pies completos, desaparecen los artefactos tipicos
 *    de dedos y piernas que arruinan estas generaciones.
 */

// Lo comun a todos los prompts: la estetica fotografica de la epoca.
const FOTOGRAFIA_80S =
    "Shot on 35mm film with direct studio flash and a soft focus glow, " +
    "warm Kodak Gold color cast, fine film grain and a subtle vignette. " +
    "Authentic 1985 mall portrait studio look, photorealistic, " +
    "no text, no logo and no watermark.";

const FONDO_80S =
    "The background is a classic 1980s portrait studio backdrop: " +
    "a mottled blue-grey gradient with soft pink and cyan laser beams.";

const ENCUADRE =
    "Vertical waist-up portrait, the person centered and facing the camera " +
    "with open eyes and a natural relaxed smile; do not use a profile view. " +
    "Keep the head and shoulders large in the frame. " +
    "Remove every other person from the scene.";

const ROPA_MUJER =
    "1980s womenswear: a pastel blouse with prominent padded shoulders and " +
    "a wide collar, worn under a boxy blazer in mauve or teal, with large " +
    "gold statement earrings and a thin gold chain";

const ROPA_HOMBRE =
    "1980s menswear: a wide-collared shirt in a soft solid color under a " +
    "boxy corduroy or tweed blazer with padded shoulders, optionally with a " +
    "knitted argyle sweater vest";

/**
 * Instruccion de pelo e identidad. Es la parte delicada: queremos pelo
 * ochentero pero sin que invente una persona distinta, porque despues el
 * face swap tiene que encajar sobre esa cabeza.
 */
function instruccionIdentidad(hasIdentityReference, identityPerson) {
    const gafas = identityPerson
        ? identityPerson.hasGlasses
            ? `Keep the exact same ${identityPerson.glassesType || "eyeglasses"} ` +
              "shown in the identity image, but restyle the frames as large " +
              "1980s glasses."
            : "This person wears no eyeglasses and no sunglasses."
        : "";

    if (!hasIdentityReference) {
        return "Give the person period-accurate 1980s hair.";
    }

    return (
        "The second input image controls the person's identity, face shape " +
        "and skin tone: keep them exactly. " +
        "Restyle only the hair into a period-accurate 1980s look, keeping " +
        "its original color and its natural texture: if the hair is straight, " +
        "wavy or curly, keep that texture, only make it fuller and feathered " +
        "with more volume at the crown and sides. " +
        "If the person is bald or has very short hair, keep it that way and " +
        "do not add hair. " +
        gafas
    );
}

function instruccionVestuario(hasCostumeReference, hasIdentityReference) {
    if (!hasCostumeReference) return "";
    const posicion = hasIdentityReference ? "third" : "second";
    return (
        `The ${posicion} input image controls only the clothing: copy its ` +
        "exact colors, fabric and cut. Ignore its body pose, background and " +
        "framing."
    );
}

/** Misma firma que buildPrompt() en server.js. */
function buildPrompt80s(
    costume,
    hasIdentityReference,
    hasCostumeReference,
    identityPerson
) {
    const identidad = instruccionIdentidad(hasIdentityReference, identityPerson);
    const vestuario = instruccionVestuario(hasCostumeReference, hasIdentityReference);
    const ropa = costume === "hombre" ? ROPA_HOMBRE : ROPA_MUJER;

    return `
Restyle this photograph into a 1985 studio portrait of one person.
The first input image controls only the pose, framing and camera angle.
${identidad}
${vestuario}
The person wears ${ropa}.
${ENCUADRE}
${FONDO_80S}
Keep one single anatomically correct person with natural shoulders and neck.
If any hand is visible it must look natural, with five separate fingers.
${FOTOGRAFIA_80S}
`;
}

/** Misma firma que buildTwoPersonPrompt() en server.js. */
function buildTwoPersonPrompt80s(pairType, people, hasCostumeReference) {
    const identidades = people
        .map((person, index) => {
            const gafas = person.hasGlasses
                ? `wearing large 1980s ${person.glassesType || "eyeglasses"}`
                : "wearing no eyeglasses and no sunglasses";
            return (
                `input image ${index + 2}: ${person.label}, ${gafas}, ` +
                "keeping that exact centered face, skin tone and baldness, " +
                "with the hair restyled into 1980s volume but the same color " +
                "and texture; ignore any partial person at the crop edge"
            );
        })
        .join("; ");

    const posicionVestuario = people.length + 2;
    const vestuario = hasCostumeReference
        ? `Input image ${posicionVestuario} controls only the clothing: copy ` +
          "its exact colors, fabric and cut."
        : "";

    const escena =
        pairType === "adulto_nino"
            ? "an adult and a child posing together"
            : pairType === "pareja_mixta"
              ? "a man and a woman posing together"
              : pairType === "dos_hombres"
                ? "two men posing together"
                : "two women posing together";

    return `
Restyle this photograph into a 1985 studio portrait of ${escena}.
The first input image controls only the pose, framing and camera angle.
Identities: ${identidades}.
${vestuario}
Both people wear 1980s clothing with padded shoulders and wide collars.
Vertical waist-up portrait of exactly two people side by side, both facing
the camera with open eyes; keep their heads clearly separated and large in
the frame. Remove every other person from the scene.
${FONDO_80S}
Keep exactly two anatomically correct people.
${FOTOGRAFIA_80S}
`;
}

module.exports = {
    buildPrompt80s,
    buildTwoPersonPrompt80s
};
