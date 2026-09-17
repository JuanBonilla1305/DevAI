/**
 * Banco de escenas: Colombia en los años 80.
 *
 * La referencia no es el imaginario de Miami con neón, sino la foto familiar
 * colombiana de la época: revelado de laboratorio de barrio con el color algo
 * virado, exteriores de patio o jardín, un árbol grande, la casa detrás, y
 * ropa de diario. Esa textura es la que hace que se reconozca como auténtica.
 *
 * Una generación puede llevar una o dos personas, y distingue si alguna es un
 * niño. Esos datos vienen del análisis facial que ya hace el proyecto
 * (género, grupo de edad), no se le preguntan al usuario.
 *
 * La escena se genera entera desde el texto; la cara real se pega después con
 * InSwapper. Por eso conviene que la cara salga grande y bien iluminada.
 */

// ---------------------------------------------------------------------
// Textura fotográfica
// ---------------------------------------------------------------------

// Nada de "family photo album" aquí: esa expresión arrastra la idea de grupo
// y de plano abierto, y el modelo acababa metiendo una segunda persona aunque
// el prompt pidiera una sola.
const PELICULA =
    "authentic 1985 amateur color snapshot, shot on expired Kodak film, " +
    "faded washed-out colors with a warm magenta shift, soft focus, " +
    "slight overexposure, visible film grain, direct on-camera flash, " +
    "photorealistic";

const NEGATIVO_BASE =
    "extra fingers, missing fingers, deformed hands, mutated hands, " +
    "deformed face, distorted face, extra faces, extra limbs, " +
    "modern clothing, hoodie, smartphone, headphones, headset, " +
    "neon, synthwave, cyberpunk, studio backdrop, " +
    "blurry, lowres, jpeg artifacts, text, watermark, signature, " +
    "cartoon, 3d render, illustration, painting, " +
    "full body, legs, knees, feet, shoes, wide shot, distant figure, " +
    "small face, face in shadow, back turned, profile view";

const NEGATIVO_HOMBRE = ", woman, female, feminine face, lipstick, makeup, dress, breasts";
const NEGATIVO_MUJER = ", man, male, masculine face, beard, moustache, stubble";
const NEGATIVO_NINO = ", adult, old face, wrinkles, beard, moustache, cleavage";

// ---------------------------------------------------------------------
// Ambientes colombianos
// ---------------------------------------------------------------------

const AMBIENTES = [
    "outdoors leaning against the trunk of a big leafy tree, green grass and a white house visible behind, soft overcast daylight",
    "in the patio of a Colombian house, whitewashed wall with potted plants and a tiled floor, bright midday sun",
    "in front of a red brick house with a wrought iron window grille and a bougainvillea in bloom",
    "in a garden with banana plants and tropical greenery, distant green mountains behind",
    "in a 1980s living room with dark wood furniture, a crocheted doily on the sideboard and floral wallpaper",
    "in a neighbourhood park with concrete benches and tall trees, other houses blurred in the distance",
    "standing beside an old boxy 1980s car parked on a residential street",
    "on a covered terrace with a wooden railing, green hills and a cloudy sky behind",
];

// ---------------------------------------------------------------------
// Encuadres
// ---------------------------------------------------------------------
//
// Todos de cintura para arriba. La cara grande importa: InSwapper trabaja a
// 128x128 y en un plano abierto la identidad casi no se transfiere.

const CARA = "looking straight at the camera, face clearly visible and well lit";

const ENCUADRES_UNO = [
    `waist-up shot, arms relaxed at the sides, slight smile, ${CARA}`,
    `waist-up shot, arms crossed, calm expression, ${CARA}`,
    `waist-up shot, one hand resting on the tree trunk, ${CARA}`,
    `waist-up shot, hands clasped in front, posing for the photo, ${CARA}`,
    `chest-up portrait, head tilted slightly, face large in the frame, ${CARA}`,
    `waist-up shot turned slightly to one side with the head facing forward, ${CARA}`,
];

// Las poses de dos personas se describen con cuidado: hay que decir dónde va
// cada cuerpo o el modelo los funde en uno solo o añade brazos de más.
const ENCUADRES_DOS = [
    `waist-up shot of both standing side by side, shoulders touching, both faces clearly visible side by side and well lit, looking straight at the camera`,
    `waist-up shot of both posing close together, one slightly behind the other, both heads clearly separated, both faces well lit, looking straight at the camera`,
    `waist-up shot of both standing together with an arm around the other's shoulder, both faces clearly visible and well lit, looking straight at the camera`,
    `chest-up shot of both heads close together, both faces large in the frame and well lit, looking straight at the camera`,
];

// ---------------------------------------------------------------------
// Personas
// ---------------------------------------------------------------------

const PELO_HOMBRE = [
    "a 1980s mullet and a thick moustache",
    "dark 1980s hair blow-dried with volume and a neat moustache",
    "curly 1980s hair with volume, clean shaven",
    "straight dark 1980s hair parted at the side, thin moustache",
];

const ROPA_HOMBRE = [
    "a black leather jacket over a red shirt with a wide collar",
    "a short-sleeved checked shirt buttoned to the top",
    "a white guayabera shirt",
    "a beige zip-up jacket over a striped polo shirt",
    "a dark blazer over a light shirt with a wide collar",
];

const PELO_MUJER = [
    "big permed curly 1980s hair with lots of volume",
    "voluminous 1980s hair with feathered layers framing the face",
    "dark 1980s hair with a side parting and soft curls, small gold earrings",
    "crimped 1980s hair held back with a patterned headband",
];

const ROPA_MUJER = [
    "a white blouse with shoulder pads and a wide collar",
    "a cream cardigan over a floral blouse",
    "a pastel blouse with a ruffled collar and a thin gold chain",
    "a dark blazer with shoulder pads over a white shirt",
    "a knitted sweater with a geometric 1980s pattern",
];

const PELO_NINO = [
    "a neat 1980s bowl haircut",
    "short dark hair combed to the side",
    "short curly hair",
];

const ROPA_NINO = [
    "a school uniform shirt with a small tie",
    "a striped t-shirt",
    "a knitted sweater over a collared shirt",
    "a small buttoned shirt with a wide collar",
];

// ---------------------------------------------------------------------

function _elegir(lista, aleatorio) {
    return lista[Math.floor(aleatorio() * lista.length)];
}

/** Generador reproducible: la misma semilla da la misma escena. */
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
 * Normaliza una persona a un tipo interno.
 *
 * El género que manda es el que eligió el usuario (`generoElegido`), no el
 * que estima InsightFace: esa estimación falla con frecuencia y no tiene
 * sentido que una suposición pise una decisión explícita. La detección sí
 * decide la edad, porque eso no se le pregunta.
 */
function _tipo(persona, generoElegido) {
    if (persona && persona.ageGroup && persona.ageGroup !== "adulto") {
        return "nino";
    }
    if (generoElegido === "mujer" || generoElegido === "hombre") {
        return generoElegido;
    }
    if (!persona) return "hombre";
    return persona.gender === "mujer" ? "mujer" : "hombre";
}

/**
 * Las gafas hay que pedirlas explícitamente: el intercambio de rostro cambia
 * la cara, no lo que lleva puesto, así que si la escena no las genera la
 * persona aparece sin ellas aunque las llevara en su foto.
 */
function _gafas(persona) {
    if (!persona || !persona.hasGlasses) return "";
    return persona.glassesType === "sunglasses"
        ? " wearing large 1980s sunglasses"
        : " wearing large 1980s eyeglasses with thin metal frames";
}

function _describir(tipo, persona, azar) {
    const gafas = _gafas(persona);

    if (tipo === "nino") {
        return {
            sujeto: "a child",
            pelo: _elegir(PELO_NINO, azar),
            ropa: _elegir(ROPA_NINO, azar),
            gafas,
            negativo: NEGATIVO_NINO,
        };
    }
    if (tipo === "mujer") {
        return {
            sujeto: "a woman",
            pelo: _elegir(PELO_MUJER, azar),
            ropa: _elegir(ROPA_MUJER, azar),
            gafas,
            negativo: NEGATIVO_MUJER,
        };
    }
    return {
        sujeto: "a man",
        pelo: _elegir(PELO_HOMBRE, azar),
        ropa: _elegir(ROPA_HOMBRE, azar),
        gafas,
        negativo: NEGATIVO_HOMBRE,
    };
}

/**
 * Compone una escena.
 *
 * @param {Array} personas  del análisis facial: [{gender, ageGroup}, ...].
 *                          Una o dos. Si viene vacío se asume un hombre.
 * @param {number} [semilla] para repetir una escena concreta.
 */
function escena80s(personas, semilla, generoElegido) {
    const lista = (Array.isArray(personas) ? personas : [personas])
        .slice(0, 2);
    if (!lista.length) lista.push(null);

    const usada = Number.isFinite(semilla)
        ? semilla
        : Math.floor(Math.random() * 2147483647);
    const azar = _aleatorio(usada);

    // La elección del usuario solo se aplica cuando hay una persona: con dos
    // no sabríamos a cuál de las dos corresponde, así que ahí sí decide la
    // detección.
    const unaSola = lista.length === 1;
    const tipos = lista.map(p => _tipo(p, unaSola ? generoElegido : null));
    const descripciones = tipos.map(
        (tipo, i) => _describir(tipo, lista[i], azar)
    );
    const ambiente = _elegir(AMBIENTES, azar);
    const dos = descripciones.length === 2;
    const encuadre = _elegir(dos ? ENCUADRES_DOS : ENCUADRES_UNO, azar);

    const sujetos = descripciones
        .map(d => `${d.sujeto} with ${d.pelo},${d.gafas ? d.gafas + "," : ""} wearing ${d.ropa}`)
        .join(" and ");

    const cabecera = dos
        ? `authentic 1985 Colombian photograph of exactly two people together, ${sujetos}`
        : `authentic 1985 Colombian photograph of one person alone, ${sujetos}, solo portrait`;

    // El negativo de género solo se aplica cuando hay una sola persona: con
    // dos de sexos distintos se contradiría y anularía el efecto.
    const negativoGenero = dos && tipos[0] !== tipos[1]
        ? ""
        : descripciones[0].negativo;

    // Y hay que negar explícitamente el número de personas que no queremos:
    // describir la escena no basta, el modelo añade gente por su cuenta.
    const negativoCantidad = dos
        ? ", three people, crowd, group of people, extra person"
        : ", two people, couple, group, crowd, another person in the background";

    // Si nadie lleva gafas hay que negarlas. Decir "sin gafas" en el prompt
    // positivo no funciona: nombrarlas basta para que el modelo las dibuje.
    const negativoGafas = descripciones.some(d => d.gafas)
        ? ""
        : ", eyeglasses, sunglasses, glasses";

    return {
        prompt: [cabecera, encuadre, ambiente, PELICULA].join(", "),
        negativo: NEGATIVO_BASE + negativoGenero + negativoCantidad + negativoGafas,
        receta: {
            semilla: usada,
            personas: tipos,
            gafas: descripciones.some(d => d.gafas),
            encuadre: dos ? "dos_personas" : "una_persona",
        },
    };
}

function totalCombinaciones() {
    const uno = (pelo, ropa) =>
        ENCUADRES_UNO.length * AMBIENTES.length * pelo * ropa;
    return {
        hombre: uno(PELO_HOMBRE.length, ROPA_HOMBRE.length),
        mujer: uno(PELO_MUJER.length, ROPA_MUJER.length),
        nino: uno(PELO_NINO.length, ROPA_NINO.length),
        pareja:
            ENCUADRES_DOS.length * AMBIENTES.length *
            PELO_HOMBRE.length * ROPA_HOMBRE.length *
            PELO_MUJER.length * ROPA_MUJER.length,
    };
}

module.exports = { escena80s, totalCombinaciones, NEGATIVO_80S: NEGATIVO_BASE };
