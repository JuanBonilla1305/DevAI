const express = require("express");
const multer = require("multer");
const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");
const http = require("http");
const {
    buildPrompt80s,
    buildTwoPersonPrompt80s
} = require("./prompts80s");
const { escena80s, NEGATIVO_80S } = require("./escenas80s");

const GENERATE_TIMEOUT_MS = 60 * 60 * 1000;

function postFastSD(url, body) {

    return new Promise((resolve, reject) => {

        const payload =
            JSON.stringify(body);

        const parsed = new URL(url);

        const request = http.request(
            {
                hostname: parsed.hostname,
                port: parsed.port,
                path: parsed.pathname,
                method: "POST",
                headers: {
                    "Content-Type":
                        "application/json",
                    "Content-Length":
                        Buffer.byteLength(
                            payload
                        )
                }
            },
            (response) => {

                const chunks = [];

                response.on(
                    "data",
                    (chunk) => chunks.push(chunk)
                );

                response.on("end", () => {

                    const text =
                        Buffer
                            .concat(chunks)
                            .toString("utf8");

                    resolve({
                        ok:
                            response.statusCode >=
                            200 &&
                            response.statusCode <
                            300,
                        status:
                            response.statusCode,
                        async text() {
                            return text;
                        }
                    });
                });
            }
        );

        request.setTimeout(
            GENERATE_TIMEOUT_MS,
            () => {
                request.destroy(
                    new Error(
                        "FastSD tardó más de 60 minutos."
                    )
                );
            }
        );

        request.on("error", reject);
        request.write(payload);
        request.end();
    });
}

const app = express();

const HOST = "127.0.0.1";
const PORT = 3000;

// La carpeta raíz se obtiene desde la ubicación de este archivo para que el
// proyecto funcione sin importar la unidad, el usuario o la ruta del clon.
const SANJUANERO_DIR = path.resolve(__dirname, "..");
// El zip de FastSD se descomprime como "fastsdcpu", pero la documentacion
// original lo llama "fastsdcpu-main". Aceptamos los dos nombres para que el
// proyecto funcione se haya descomprimido como se haya descomprimido.
const FASTSD_DIR = (() => {
    const candidatos = ["fastsdcpu-main", "fastsdcpu"].map(
        nombre => path.join(SANJUANERO_DIR, nombre)
    );
    return candidatos.find(ruta =>
        fs.existsSync(path.join(ruta, "src", "app.py"))
    ) || candidatos[0];
})();

// Por defecto se usa FastSD tal como lo entrego el profesor: OpenVINO sobre
// CPU, unos 10 minutos por imagen. Con MOTOR_GPU=1 se levanta en su lugar
// servidor_gpu.py, que responde exactamente la misma API pero genera en la
// GPU en unos 6 segundos. server.js no nota la diferencia: lo unico que
// cambia es a quien arranca y contra quien habla.
const MOTOR_GPU = process.env.MOTOR_GPU === "1";

const CAMARA80S_DIR = path.join(SANJUANERO_DIR, "..", "camara80s");

// OJO: son dos interpretes distintos y no se pueden mezclar.
//
// FASTSD_PYTHON  entorno del profesor. Es el unico que tiene insightface,
//                asi que SIEMPRE ejecuta los scripts de analisis facial y de
//                intercambio de rostro, use el motor que use.
// MOTOR_PYTHON   quien levanta el servidor de generacion en el puerto 8000.
//                Con MOTOR_GPU=1 es el entorno de camara80s, que tiene
//                PyTorch con CUDA.
const FASTSD_PYTHON = path.join(FASTSD_DIR, "env", "Scripts", "python.exe");

const MOTOR_PYTHON = MOTOR_GPU
    ? path.join(CAMARA80S_DIR, ".venv", "Scripts", "python.exe")
    : FASTSD_PYTHON;

const FASTSD_APP = MOTOR_GPU
    ? path.join(CAMARA80S_DIR, "servidor_gpu.py")
    : path.join(FASTSD_DIR, "src", "app.py");

const MOTOR_DIR = MOTOR_GPU ? CAMARA80S_DIR : FASTSD_DIR;

const FASTSD_API = "http://127.0.0.1:8000";

const MODEL_ID = "rupeshs/flux2-klein-4b-int4-ov";

const RESULTS_DIR = path.join(__dirname, "results");

const PRESERVE_FACE_SCRIPT = path.join(
    __dirname,
    "scripts",
    "preserve_face.py"
);

const ANALYZE_PHOTO_SCRIPT = path.join(
    __dirname,
    "scripts",
    "analyze_photo.py"
);

const EXTRACT_HEAD_SCRIPT = path.join(
    __dirname,
    "scripts",
    "extract_head_reference.py"
);

const REFERENCES_DIR = path.join(__dirname, "references");
const REF_MUJER = path.join(REFERENCES_DIR, "pose_mujer.png");
const REF_HOMBRE = path.join(REFERENCES_DIR, "pose_hombre.png");
const REF_VESTIDO_MUJER = path.join(
    REFERENCES_DIR,
    "vestido_mujer.jpg"
);
const REF_DOS_HOMBRES = path.join(
    REFERENCES_DIR,
    "pose_dos_hombres.jpg"
);
const REF_DOS_MUJERES = path.join(
    REFERENCES_DIR,
    "pose_dos_mujeres.jpg"
);
const REF_PAREJA_MIXTA = path.join(
    REFERENCES_DIR,
    "pose_pareja_mixta.png"
);

function fileToBase64(filePath) {

    if (!fs.existsSync(filePath)) {
        return null;
    }

    return fs
        .readFileSync(filePath)
        .toString("base64");
}

function runPythonScript(scriptPath, args) {

    return new Promise((resolve) => {

        const child = spawn(
            FASTSD_PYTHON,
            [scriptPath, ...args],
            {
                cwd: FASTSD_DIR,
                windowsHide: true
            }
        );

        let output = "";

        child.stdout.on("data", (data) => {
            output += data.toString();
            process.stdout.write(data);
        });

        child.stderr.on("data", (data) => {
            process.stderr.write(data);
        });

        child.on("error", () => {
            resolve({ ok: false, output });
        });

        child.on("close", (code) => {
            resolve({
                ok: code === 0,
                output
            });
        });
    });
}

function parseLastJsonLine(output) {
    const lines = output
        .split(/\r?\n/)
        .map(line => line.trim())
        .filter(Boolean);

    for (let index = lines.length - 1; index >= 0; index -= 1) {
        try {
            return JSON.parse(lines[index]);
        } catch (error) {
            // Las bibliotecas de visión también escriben mensajes de carga.
        }
    }

    return null;
}

function sliderToIdentityStrength(strength) {
    const normalized = (strength - 0.15) / 0.35;
    return Math.max(0.85, Math.min(1.0, 0.85 + normalized * 0.15));
}

function runPreserveFace(
    originalPath,
    generatedPath,
    outputPath,
    identityStrength,
    maxFaces
) {

    return runPythonScript(
        PRESERVE_FACE_SCRIPT,
        [
            originalPath,
            generatedPath,
            outputPath,
            identityStrength.toFixed(3),
            String(maxFaces)
        ]
    ).then((result) => (
        result.ok &&
        fs.existsSync(outputPath) &&
        result.output.includes("OK")
    ));
}

function buildFastSDBody(
    prompt,
    initImage,
    isTwoPerson = false,
    desdeCero = false,
    negativo = null
) {

    return {

        // La escena se inventa entera desde el texto. Es la unica forma de
        // cambiar la pose y el cuerpo: partiendo de la foto, la composicion
        // se conserva y de un plano de busto no sale una persona de pie.
        txt2img: desdeCero,

        lcm_model_id:
            "stabilityai/sd-turbo",

        openvino_lcm_model_id:
            MODEL_ID,

        use_offline_model: false,

        use_lcm_lora: false,

        lcm_lora: {
            base_model_id:
                "Lykon/dreamshaper-8",
            lcm_lora_id:
                "latent-consistency/lcm-lora-sdv1-5"
        },

        use_tiny_auto_encoder: false,

        use_openvino: true,

        prompt: prompt,

        negative_prompt:
            negativo || (TEMA === "sanjuanero" ? "" : NEGATIVO_80S),

        init_image: initImage,

        // Cuanto se aleja el resultado de la foto original. FLUX.2 Klein no
        // usa este campo en la rama edit_image de FastSD; el motor GPU si.
        // Fuerza alta a proposito: el estilo ochentero necesita libertad para
        // cambiar pelo, ropa y fondo. La identidad no se juega aqui, sino en
        // preserve_face.py, que pega la cara real al final.
        strength: MOTOR_GPU ? 0.72 : 0.90,

        // FLUX.2 Klein trabaja con guidance 1.0 y muy pocos pasos; SD 1.5 en
        // img2img necesita mas pasos y guidance medio. Los valores salieron
        // de barrer parametros sobre fotos reales en una RTX 3050: a fuerza
        // 0.55 la persona sigue siendo reconocible, los objetos modernos
        // desaparecen y el retrato tarda menos de 4 segundos.
        // Vertical, pero sin exagerar el alto: las escenas son de cintura
        // para arriba, y un lienzo muy alargado invita al modelo a meter
        // cuerpo de mas y a alejar la cara.
        image_height: MOTOR_GPU ? (desdeCero ? 640 : 576) : 512,

        image_width: MOTOR_GPU ? (desdeCero ? 512 : 448) : 384,

        inference_steps: MOTOR_GPU ? (desdeCero ? 28 : 20) : (isTwoPerson ? 8 : 6),

        guidance_scale: MOTOR_GPU ? 8.0 : 1.0,

        clip_skip: 1,

        token_merging: 0,

        number_of_images: 1,

        seed: -1,

        use_seed: false,

        use_safety_checker: false,

        diffusion_task:
            "edit_image",

        lora: {
            path: null,
            weight: 0.5,
            fuse: false,
            enabled: false
        },

        controlnet: null,

        dirs: {},

        rebuild_pipeline: false,

        rebuild_controlnet_pipeline: false,

        use_gguf_model: false
    };
}

function decodeFastSDImage(result) {

    if (result.error) {
        return { error: result.error };
    }

    if (
        !result.images ||
        !Array.isArray(result.images) ||
        result.images.length === 0
    ) {
        return {
            error: "FastSD terminó pero no devolvió ninguna imagen."
        };
    }

    let cleanBase64 = result.images[0];

    if (cleanBase64.includes(",")) {
        cleanBase64 = cleanBase64.split(",")[1];
    }

    return {
        cleanBase64,
        buffer: Buffer.from(cleanBase64, "base64")
    };
}

// Crear carpeta de resultados si no existe
if (!fs.existsSync(RESULTS_DIR)) {
    fs.mkdirSync(RESULTS_DIR, { recursive: true });
}

// -----------------------------------------------------
// MULTER
// -----------------------------------------------------

const upload = multer({
    storage: multer.memoryStorage(),
    limits: {
        fileSize: 12 * 1024 * 1024
    },
    fileFilter: (req, file, cb) => {
        const allowed = [
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/webp"
        ];

        if (!allowed.includes(file.mimetype)) {
            return cb(
                new Error(
                    "Solo se permiten imágenes JPG, JPEG, PNG o WEBP."
                )
            );
        }

        cb(null, true);
    }
});

app.use(express.json({ limit: "20mb" }));
app.use(express.urlencoded({ extended: true }));

app.use(express.static(
    path.join(__dirname, "public"),
    {
        etag: false,
        lastModified: false,
        setHeaders(response) {
            response.setHeader(
                "Cache-Control",
                "no-store"
            );
        }
    }
));

// -----------------------------------------------------
// FASTSD
// -----------------------------------------------------

let fastsdProcess = null;
let fastsdStarting = false;

function startFastSD() {

    if (fastsdProcess) {
        return;
    }

    if (!fs.existsSync(MOTOR_PYTHON)) {
        console.error("");
        console.error("ERROR: No existe:");
        console.error(MOTOR_PYTHON);
        console.error("");
        return;
    }

    if (!fs.existsSync(FASTSD_APP)) {
        console.error("");
        console.error("ERROR: No existe:");
        console.error(FASTSD_APP);
        console.error("");
        return;
    }

    console.log("");
    console.log("==============================================");
    console.log(MOTOR_GPU
        ? " INICIANDO MOTOR GPU (CUDA)"
        : " INICIANDO FASTSD CPU");
    console.log("==============================================");
    console.log("Python:");
    console.log(MOTOR_PYTHON);
    console.log("");
    console.log("App:");
    console.log(FASTSD_APP);
    console.log("");
    console.log("Modelo:");
    console.log(MOTOR_GPU ? "instruct-pix2pix (CUDA)" : MODEL_ID);
    console.log("");

    fastsdStarting = true;

    fastsdProcess = spawn(
        MOTOR_PYTHON,
        [
            FASTSD_APP,
            "--api",
            "--port",
            "8000"
        ],
        {
            cwd: MOTOR_DIR,
            env: {
                ...process.env,
                DEVICE: "CPU"
            },
            windowsHide: false
        }
    );

    fastsdProcess.stdout.on("data", (data) => {
        process.stdout.write(
            `[FastSD] ${data.toString()}`
        );
    });

    fastsdProcess.stderr.on("data", (data) => {
        process.stderr.write(
            `[FastSD] ${data.toString()}`
        );
    });

    fastsdProcess.on("close", (code) => {

        console.log("");
        console.log(
            `FastSD terminó con código: ${code}`
        );

        fastsdProcess = null;
        fastsdStarting = false;
    });

    fastsdProcess.on("error", (error) => {

        console.error("");
        console.error(
            "ERROR iniciando FastSD:"
        );

        console.error(error);

        fastsdProcess = null;
        fastsdStarting = false;
    });
}

// -----------------------------------------------------
// ESPERAR FASTSD
// -----------------------------------------------------

async function waitForFastSD(
    timeoutMs = 90000
) {

    const start = Date.now();

    while (
        Date.now() - start <
        timeoutMs
    ) {

        try {

            const response = await fetch(
                `${FASTSD_API}/api/info`
            );

            if (response.ok) {

                console.log("");
                console.log(
                    "FastSD API disponible."
                );

                return true;
            }

        } catch (error) {
            // Todavía no está listo
        }

        await new Promise(
            resolve => setTimeout(resolve, 1000)
        );
    }

    return false;
}

// -----------------------------------------------------
// STATUS
// -----------------------------------------------------

app.get("/api/status", async (req, res) => {

    try {

        const response = await fetch(
            `${FASTSD_API}/api/info`
        );

        if (!response.ok) {
            throw new Error(
                "FastSD respondió con error."
            );
        }

        const info = await response.json();

        res.json({
            ok: true,
            fastsd: true,
            model: MODEL_ID,
            info
        });

    } catch (error) {

        res.json({
            ok: false,
            fastsd: false,
            model: MODEL_ID,
            message:
                "FastSD todavía no está disponible."
        });
    }
});

app.post(
    "/api/analyze-photo",
    upload.single("photo"),
    async (req, res) => {

        if (!req.file) {
            return res.status(400).json({
                ok: false,
                error: "No se recibió ninguna fotografía."
            });
        }

        const temporaryPath = path.join(
            RESULTS_DIR,
            `analyze_${Date.now()}.img`
        );

        try {
            fs.writeFileSync(temporaryPath, req.file.buffer);

            const result = await runPythonScript(
                ANALYZE_PHOTO_SCRIPT,
                [temporaryPath]
            );

            const lines = result.output
                .split(/\r?\n/)
                .map(line => line.trim())
                .filter(Boolean);

            let analysis = null;

            for (let index = lines.length - 1; index >= 0; index -= 1) {
                try {
                    analysis = JSON.parse(lines[index]);
                    break;
                } catch (error) {
                    // InsightFace también escribe mensajes de carga.
                }
            }

            if (!result.ok || !analysis) {
                return res.status(500).json({
                    ok: false,
                    error: "No se pudo analizar la fotografía."
                });
            }

            return res.json(analysis);

        } finally {
            fs.rmSync(temporaryPath, { force: true });
        }
    }
);

// -----------------------------------------------------
// CONSTRUIR PROMPT
// -----------------------------------------------------

function buildPrompt(
    costume,
    hasIdentityReference,
    hasCostumeReference,
    identityPerson
) {
    const eyewearInstruction = identityPerson
        ? identityPerson.hasGlasses
            ? `Keep the exact same ${identityPerson.glassesType || "eyeglasses"}
shown in the identity image.`
            : "This person wears no eyeglasses and no sunglasses."
        : "";

    const identityInstruction = hasIdentityReference
        ? `The second input image controls the person's identity and natural hair.
Copy the second image's exact hair presence, color, length and texture.
If that person is bald, keep the scalp bald. If the hair is straight, wavy
or curly, keep that same texture. Never invent or change the hairstyle.
${eyewearInstruction}`
        : "Use a natural hairstyle without changing the reference pose.";

    const costumeImagePosition =
        hasIdentityReference ? "third" : "second";

    const costumeInstruction = hasCostumeReference
        ? `The ${costumeImagePosition} input image controls only the woman's
clothing: copy its exact colors, fabric panels, lace, ribbons, ruffles and
decorative arrangement. Ignore its body pose, background and framing.`
        : "";

    const femaleCostume =
        "authentic female Sanjuanero Huilense clothing from Huila, Colombia: " +
        "a high-neck white blouse with large layered ruffled sleeves, decorated " +
        "with burgundy, mustard-yellow and gold ribbons and white lace; a huge " +
        "ankle-length faldeo skirt with mustard-yellow, burnt-orange patterned " +
        "and deep-burgundy tiers, finished with gold ribbon and white lace; " +
        "one clearly visible traditional handwoven Huilense fique mochila, " +
        "cream-colored with red, green and yellow geometric embroidery, worn " +
        "crossbody at the waist with its woven shoulder strap visible; " +
        "a traditional floral headpiece arranged without changing the person's " +
        "natural hairstyle, and white dance shoes";

    const maleCostume =
        "authentic male Sanjuanero Huilense clothing from Huila, Colombia: " +
        "a crisp white long-sleeve shirt, fitted white trousers, " +
        "a bright red neckerchief, a wide red handkerchief held behind the hips, " +
        "a traditional light-beige Huila straw hat with a red band, " +
        "and white alpargatas";

    if (costume === "hombre") {
        return `
Refine this photograph of one man dancing the Sanjuanero Huilense.
The first input image controls only the pose, body and camera angle.
${identityInstruction}
Keep the exact same male pose, body position and camera angle as the
reference: torso upright, arms extended holding the red handkerchief
behind his hips, one knee raised high and the other foot on the floor.
He wears ${maleCostume}.
He wears no skirt, dress, blouse or flower crown.
Keep one complete anatomically correct male body and both complete feet.
Keep both hands clearly visible and natural, with five separate fingers on
each hand. Face directly toward the camera with open eyes; do not use profile.
Remove all background people. Use a simple softly blurred Colombian plaza.
Full-body vertical professional photograph. Sharp natural face and skin.
Photorealistic, no text, no flag and no watermark.
`;
    }

    return `
Refine this photograph of one woman dancing the Sanjuanero Huilense.
The first input image controls only the pose, body and camera angle.
${identityInstruction}
${costumeInstruction}
Keep the exact same female faldeo pose, body position and camera angle
as the reference: torso upright, both arms extended, both hands lifting
the two sides of the skirt into large flowing arcs, one leg forward.
She wears ${femaleCostume}.
Keep exactly one mochila, naturally resting at her side without covering her
hands, face, skirt or body.
Keep one complete anatomically correct female body and both complete feet.
Keep both hands clearly visible and natural, with five separate fingers on
each hand. Face directly toward the camera with open eyes; do not use profile.
Remove all background people. Use a simple softly blurred Colombian plaza.
Full-body vertical professional photograph. Sharp natural face and skin.
Authentic Huilense clothing, not a Mexican Jalisco dress.
Photorealistic, no text, no flag and no watermark.
`;
}

/**
 * Tema visual activo. Se elige con la variable de entorno TEMA:
 *   TEMA=80s          retrato de estudio de los anios 80 (por defecto)
 *   TEMA=sanjuanero   el baile Sanjuanero Huilense original
 *
 * Los prompts de los 80 viven en prompts80s.js, asi que el tema original
 * queda intacto y se puede volver a el cambiando una variable.
 */
const TEMA = (process.env.TEMA || "80s").toLowerCase();

// face_preserve.py descarta las caras de la imagen generada que quedan
// demasiado abajo o demasiado anchas: sus limites asumen una escena de baile
// de cuerpo entero. En un retrato de busto la cara ocupa mas de la mitad del
// ancho, asi que los rechazaba todos y el intercambio se saltaba en silencio.
// Estos valores los amplian solo para el tema de los 80.
if (TEMA !== "sanjuanero") {
    process.env.CARA_CENTRO_Y_MAX = process.env.CARA_CENTRO_Y_MAX || "0.80";
    process.env.CARA_ANCHO_MAX = process.env.CARA_ANCHO_MAX || "0.90";
}

const construirPrompt =
    TEMA === "sanjuanero" ? buildPrompt : buildPrompt80s;

const construirPromptDosPersonas =
    TEMA === "sanjuanero" ? buildTwoPersonPrompt : buildTwoPersonPrompt80s;

console.log(`Tema activo: ${TEMA}`);

function classifyPair(people) {
    if (people.some(person => person.ageGroup !== "adulto")) {
        return "adulto_nino";
    }

    const women = people.filter(person => person.gender === "mujer").length;
    if (women === 2) return "dos_mujeres";
    if (women === 0) return "dos_hombres";
    return "pareja_mixta";
}

function buildTwoPersonPrompt(pairType, people, hasCostumeReference) {
    const identities = people
        .map((person, index) => {
            const eyewear = person.hasGlasses
                ? `wearing the same ${person.glassesType || "eyeglasses"}`
                : "wearing no eyeglasses and no sunglasses";
            return (
                `input image ${index + 2}: ${person.label}, ${eyewear}, ` +
                "preserving that exact centered face, skin tone, baldness and " +
                "natural hairstyle; ignore any partial person at the crop edge"
            );
        })
        .join("; ");

    const costumePosition = people.length + 2;
    const costumeInstruction = hasCostumeReference
        ? `Input image ${costumePosition} controls only every woman's clothing.
Copy its exact burgundy, mustard-yellow, burnt-orange and white colors,
layered ruffles, lace, gold ribbons and fabric arrangement.`
        : "";

    const common = `The first input image controls only the two-person dance
pose, body placement and camera angle. The identity references are:
${identities}. Match identities to generated bodies by gender and relative
age; when both have the same gender, preserve their left-to-right order.
Keep exactly two complete, anatomically correct bodies and four complete feet.
Give each person exactly two correctly attached arms and two natural hands.
Keep every hand fully visible and separated from the other body and clothing,
with natural wrists, five distinct fingers, correct finger length and no fused,
missing, duplicated or deformed fingers. Preserve realistic shoulders, elbows,
knees and leg proportions with no merged or duplicated limbs.
Preserve each person's hair presence, color, length and texture; never invent
hair on a bald person or curls on a straight-haired person.
Dress every man in an authentic white Sanjuanero Huilense suit, red
neckerchief, light-beige Huila hat and white alpargatas. Dress every woman in
the referenced Huilense faldeo outfit, floral headpiece without changing her
natural hairstyle, white dance shoes and one visible woven Huilense mochila.
${costumeInstruction}
Both people face directly toward the camera with open eyes and unobstructed
front-facing faces. They look at the viewer, not at each other and not in
profile. Frame them close enough that both faces remain large, sharp and easy
to recognize while keeping both complete bodies and feet visible.
Remove all background people. Use a softly blurred Colombian plaza.
Full-body vertical professional photograph, sharp natural faces and skin,
photorealistic, no text, no flag and no watermark.`;

    if (pairType === "dos_hombres") {
        return `Create two men dancing the Sanjuanero Huilense.
${common}
Copy the first image's diagonal dance-duel pose exactly: both men face and
smile toward the camera, each balancing on one foot with the other leg lifted.
The left man leans inward with both elbows bent outward. The right man holds
a red handkerchief toward his partner and keeps his other hand at his waist.`;
    }

    if (pairType === "dos_mujeres") {
        return `Create two women dancing the Sanjuanero Huilense.
${common}
Copy the first image's synchronized turning pose exactly. The front dancer
opens both skirt edges into a wide flying arc while turning toward the camera.
The second dancer mirrors her from behind while also facing the camera.
Keep both women visible and keep
the two separate skirts anatomically attached to their respective bodies.`;
    }

    if (pairType === "adulto_nino") {
        return `Create one adult and one child dancing the Sanjuanero Huilense.
${common}
Use the first image only as a loose two-person composition. Make a safe,
age-appropriate and joyful side-by-side folkloric dance: both upright, fully
visible and facing the camera, with simple natural steps, comfortable spacing
and no romantic pose.
Make the child's height and body proportions clearly age-appropriate.`;
    }

    return `Create one woman and one man dancing the Sanjuanero Huilense.
${common}
Copy the first image's walking-couple pose exactly. The woman advances with
her skirt gathered asymmetrically and one foot lifted lightly behind. The man
walks upright beside her with relaxed arms. Both turn their heads and eyes
directly toward the camera instead of looking at each other.
Keep the composition contained and natural rather than a suspended kick.`;
}

// -----------------------------------------------------
// GENERAR IMAGEN
// -----------------------------------------------------

app.post(
    "/api/generate",
    upload.single("photo"),
    async (req, res) => {

        try {

            console.log("");
            console.log(
                "=============================================="
            );

            console.log(
                " NUEVA GENERACIÓN SANJUANERO"
            );

            console.log(
                "=============================================="
            );

            if (!req.file) {

                return res.status(400).json({
                    ok: false,
                    error:
                        "No se recibió ninguna fotografía."
                });
            }

            let costume =
                req.body.costume === "hombre"
                    ? "hombre"
                    : "mujer";

            let peopleCount =
                req.body.peopleCount === "2"
                    ? "2"
                    : "1";

            let strength =
                Number(req.body.strength || 0.30);

            if (Number.isNaN(strength)) {
                strength = 0.30;
            }

            strength = Math.max(
                0.15,
                Math.min(0.50, strength)
            );

            console.log(
                `Fotografía: ${req.file.originalname}`
            );

            console.log(
                `Tamaño: ${req.file.size} bytes`
            );

            console.log(
                `Vestuario: ${costume}`
            );

            const identityStrength =
                sliderToIdentityStrength(strength);

            console.log(
                `Identidad cara: ${strength} → ${identityStrength.toFixed(2)}`
            );

            // -----------------------------------------
            // Verificar FastSD
            // -----------------------------------------

            let fastsdReady = false;

            try {

                const response = await fetch(
                    `${FASTSD_API}/api/info`
                );

                fastsdReady = response.ok;

            } catch (error) {
                fastsdReady = false;
            }

            if (!fastsdReady) {

                console.log(
                    "FastSD no está iniciado."
                );

                if (!fastsdProcess) {
                    startFastSD();
                }

                const ready =
                    await waitForFastSD(120000);

                if (!ready) {

                    return res.status(500).json({
                        ok: false,
                        error:
                            "FastSD no respondió después de 120 segundos."
                    });
                }
            }

            // -----------------------------------------
            // PROMPT
            // -----------------------------------------

            const timestamp =
                new Date()
                    .toISOString()
                    .replace(/[:.]/g, "-");

            const originalPath =
                path.join(
                    RESULTS_DIR,
                    `original_${timestamp}.jpg`
                );

            fs.writeFileSync(
                originalPath,
                req.file.buffer
            );

            let detectedPeople = [];
            let pairType = null;

            const analysisResult =
                await runPythonScript(
                    ANALYZE_PHOTO_SCRIPT,
                    [originalPath]
                );
            const analysis =
                parseLastJsonLine(analysisResult.output);

            if (
                analysisResult.ok &&
                analysis &&
                Array.isArray(analysis.people) &&
                analysis.people.length > 0
            ) {
                detectedPeople = analysis.people.slice(0, 2);
                peopleCount =
                    detectedPeople.length >= 2
                        ? "2"
                        : "1";

                if (peopleCount === "2") {
                    pairType = classifyPair(detectedPeople);

                    const allowedPairTypes = new Set([
                        "dos_mujeres",
                        "dos_hombres",
                        "pareja_mixta",
                        "adulto_nino"
                    ]);
                    if (allowedPairTypes.has(req.body.pairType)) {
                        pairType = req.body.pairType;
                    }

                    if (pairType === "dos_mujeres") {
                        detectedPeople = detectedPeople.map(
                            person => ({
                                ...person,
                                gender: "mujer",
                                ageGroup: "adulto",
                                label: "mujer"
                            })
                        );
                    } else if (pairType === "dos_hombres") {
                        detectedPeople = detectedPeople.map(
                            person => ({
                                ...person,
                                gender: "hombre",
                                ageGroup: "adulto",
                                label: "hombre"
                            })
                        );
                    }
                } else {
                    costume = detectedPeople[0].gender;
                }
            } else if (peopleCount === "2") {
                    return res.status(400).json({
                        ok: false,
                        error:
                            "Seleccionaste dos personas, pero no pude detectar dos rostros principales."
                    });
            }

            console.log(
                `Personas detectadas: ${peopleCount}`
            );

            let poseRefPath;
            if (peopleCount === "1") {
                poseRefPath =
                    costume === "hombre"
                        ? REF_HOMBRE
                        : REF_MUJER;
            } else if (pairType === "dos_hombres") {
                poseRefPath = REF_DOS_HOMBRES;
            } else if (pairType === "dos_mujeres") {
                poseRefPath = REF_DOS_MUJERES;
            } else {
                poseRefPath = REF_PAREJA_MIXTA;
            }

            const poseRefBase64 =
                fileToBase64(poseRefPath);

            if (!poseRefBase64) {
                return res.status(500).json({
                    ok: false,
                    error: "No se encontró la referencia de pose."
                });
            }

            const headReferencePaths =
                Array.from(
                    { length: Number(peopleCount) },
                    (_, index) => path.join(
                        RESULTS_DIR,
                        `head_${index + 1}_${timestamp}.jpg`
                    )
                );

            const headExtraction =
                await runPythonScript(
                    EXTRACT_HEAD_SCRIPT,
                    [originalPath, ...headReferencePaths]
                );

            const headRefsBase64 =
                headExtraction.ok
                    ? headReferencePaths
                        .map(fileToBase64)
                        .filter(Boolean)
                    : [];

            const hasWoman =
                peopleCount === "1"
                    ? costume === "mujer"
                    : detectedPeople.some(
                        person => person.gender === "mujer"
                    );
            const costumeRefBase64 =
                hasWoman
                    ? fileToBase64(REF_VESTIDO_MUJER)
                    : null;

            headReferencePaths.forEach(
                headPath => fs.rmSync(
                    headPath,
                    { force: true }
                )
            );

            if (
                peopleCount === "2" &&
                headRefsBase64.length < 2
            ) {
                return res.status(400).json({
                    ok: false,
                    error:
                        "No pude preparar las dos identidades de la fotografía."
                });
            }

            // Con el tema de los 80 y una sola persona, la escena se saca del
            // banco: cada peticion combina encuadre, peinado, vestuario y
            // ambiente distintos, asi que no salen siempre la misma foto.
            let escena = null;
            if (TEMA !== "sanjuanero" && peopleCount !== "2") {
                escena = escena80s(costume, Number(req.body.escena) || undefined);
                console.log("Escena:", JSON.stringify(escena.receta));
            }

            const prompt = escena
                ? escena.prompt
                : peopleCount === "2"
                    ? construirPromptDosPersonas(
                        pairType,
                        detectedPeople,
                        Boolean(costumeRefBase64)
                    )
                    : construirPrompt(
                        costume,
                        headRefsBase64.length > 0,
                        Boolean(costumeRefBase64),
                        detectedPeople[0] || null
                    );

            // El tema sanjuanero genera un cuerpo entero bailando, asi que
            // parte de una referencia de pose. El tema de los 80 es un
            // retrato de busto: ahi la mejor base es la propia fotografia,
            // que ya viene encuadrada como retrato. Usar la pose de baile
            // daba como resultado la foto de referencia con un filtro encima,
            // porque el modelo conserva la composicion de la imagen base.
            const imagenBase =
                TEMA === "sanjuanero"
                    ? poseRefBase64
                    : (fileToBase64(originalPath) || poseRefBase64);

            const initImages = [
                imagenBase,
                ...headRefsBase64,
                ...(costumeRefBase64 ? [costumeRefBase64] : [])
            ];

            const requestBody =
                buildFastSDBody(
                    prompt,
                    initImages,
                    peopleCount === "2",
                    Boolean(escena),
                    escena ? escena.negativo : null
                );

            console.log("");
            console.log(
                "Generando el baile. Luego se pone tu cara de la foto."
            );

            console.log(
                "Endpoint:",
                `${FASTSD_API}/api/generate`
            );

            const startTime =
                Date.now();

            console.log(
                "Esperando a FastSD. En CPU puede tardar unos 10 minutos."
            );

            const response = await postFastSD(
                `${FASTSD_API}/api/generate`,
                requestBody
            );

            const responseText =
                await response.text();

            if (!response.ok) {

                console.error(
                    "FastSD HTTP ERROR:"
                );

                console.error(
                    response.status
                );

                console.error(
                    responseText
                );

                return res.status(500).json({
                    ok: false,
                    error:
                        `FastSD respondió HTTP ${response.status}`,
                    details:
                        responseText
                });
            }

            let result;

            try {

                result =
                    JSON.parse(
                        responseText
                    );

            } catch (error) {

                console.error(
                    "Respuesta de FastSD no es JSON:"
                );

                console.error(
                    responseText
                );

                return res.status(500).json({
                    ok: false,
                    error:
                        "FastSD devolvió una respuesta inválida."
                });
            }

            const decoded =
                decodeFastSDImage(result);

            if (decoded.error) {

                console.error(
                    "FastSD reportó error:"
                );

                console.error(
                    decoded.error
                );

                return res.status(500).json({
                    ok: false,
                    error:
                        decoded.error
                });
            }

            let imageBuffer =
                decoded.buffer;

            let cleanBase64 =
                decoded.cleanBase64;

            const elapsed =
                ((Date.now() - startTime) / 1000)
                    .toFixed(1);

            console.log("");
            console.log(
                `FastSD terminó en ${elapsed} segundos.`
            );

            const filename =
                `sanjuanero_${timestamp}.jpg`;

            const outputPath =
                path.join(
                    RESULTS_DIR,
                    filename
                );

            fs.writeFileSync(
                outputPath,
                imageBuffer
            );

            const bodyPath =
                path.join(
                    RESULTS_DIR,
                    `sanjuanero_${timestamp}_cuerpo.jpg`
                );

            fs.writeFileSync(
                bodyPath,
                imageBuffer
            );

            const facePath =
                path.join(
                    RESULTS_DIR,
                    `sanjuanero_${timestamp}_face.jpg`
                );

            const preserved =
                await runPreserveFace(
                    originalPath,
                    outputPath,
                    facePath,
                    identityStrength,
                    Number(peopleCount)
                );

            if (preserved) {

                imageBuffer =
                    fs.readFileSync(facePath);

                cleanBase64 =
                    imageBuffer.toString("base64");

                fs.writeFileSync(
                    outputPath,
                    imageBuffer
                );

                console.log(
                    "Rostro original aplicado sobre el baile."
                );
            }

            console.log("");
            console.log(
                "IMAGEN GENERADA CORRECTAMENTE"
            );

            console.log(
                "Archivo:"
            );

            console.log(
                outputPath
            );

            console.log(
                `Tamaño: ${imageBuffer.length} bytes`
            );

            console.log("");

            return res.json({

                ok: true,

                filename: filename,

                path: outputPath,

                image:
                    `data:image/jpeg;base64,${cleanBase64}`,

                latency: elapsed
            });

        } catch (error) {

            console.error("");
            console.error(
                "=============================================="
            );

            console.error(
                " ERROR GENERANDO IMAGEN"
            );

            console.error(
                "=============================================="
            );

            console.error(error);

            return res.status(500).json({

                ok: false,

                error:
                    error.message ||
                    "Error interno del servidor."
            });
        }
    }
);

// -----------------------------------------------------
// ERRORES MULTER
// -----------------------------------------------------

app.use(
    (error, req, res, next) => {

        if (
            error instanceof
            multer.MulterError
        ) {

            return res.status(400).json({
                ok: false,
                error:
                    `Error de archivo: ${error.message}`
            });
        }

        if (error) {

            return res.status(400).json({
                ok: false,
                error:
                    error.message
            });
        }

        next();
    }
);

// -----------------------------------------------------
// INICIAR NODE
// -----------------------------------------------------

const server = app.listen(
    PORT,
    HOST,
    () => {

        console.log("");
        console.log(
            "=============================================="
        );

        console.log(
            "       SANJUANERO IA"
        );

        console.log(
            "       Node.js + FastSD + FLUX.2 Klein"
        );

        console.log(
            "=============================================="
        );

        console.log("");
        console.log(
            `Aplicación: http://${HOST}:${PORT}`
        );

        console.log(
            `FastSD API: ${FASTSD_API}`
        );

        console.log(
            `Resultados: ${RESULTS_DIR}`
        );

        console.log("");
        console.log(
            "Iniciando FastSD..."
        );

        startFastSD();
    }
);

server.timeout = GENERATE_TIMEOUT_MS;
server.headersTimeout = GENERATE_TIMEOUT_MS + 60 * 1000;
server.requestTimeout = GENERATE_TIMEOUT_MS;