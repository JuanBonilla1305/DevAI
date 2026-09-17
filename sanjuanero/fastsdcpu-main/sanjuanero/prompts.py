"""Prompts de edición para vestir y mostrar a las personas bailando Sanjuanero."""

FEMALE_COSTUME = (
    "the authentic traditional female Sanjuanero Huilense costume from Huila, Colombia: "
    "a white off-shoulder lace blouse with ruffled lace sleeves and a gold sequin embroidered "
    "neckline; a pale mint-blue satin skirt decorated with large three-dimensional fabric roses "
    "in orange, yellow and brown; a curved gold sequin band across the skirt; white lace ruffles "
    "at the hem; an orange fabric rose in the hair; the dancer is barefoot. "
    "This is NOT a rainbow Mexican folkloric skirt and NOT a generic colorful fiesta dress."
)

MALE_COSTUME = (
    "an authentic traditional male Sanjuanero Huilense folkloric costume from Huila, Colombia: "
    "a white shirt, white trousers, a bright red pañoleta scarf around the neck, a traditional "
    "Huila hat and alpargatas"
)


def build_prompt(scene: str, has_costume_ref: bool = False) -> str:
    if scene == "Hombre":
        clothing = (
            f"Dress this same man in {MALE_COSTUME}. "
            "Keep the same man from the first image."
        )
    elif scene == "Pareja (hombre y mujer)":
        clothing = (
            f"Dress the man in {MALE_COSTUME}. "
            f"Dress the woman in {FEMALE_COSTUME}. "
            "They dance together as a Sanjuanero couple. "
            "Keep both original people from the first image."
        )
    elif scene == "Dos mujeres":
        clothing = (
            f"Dress both women in {FEMALE_COSTUME}. "
            "Keep both original women from the first image."
        )
    elif scene == "Dos hombres":
        clothing = (
            f"Dress both men in {MALE_COSTUME}. "
            "Keep both original men from the first image."
        )
    else:
        clothing = (
            f"Dress this same woman in {FEMALE_COSTUME}. "
            "Keep the same woman from the first image."
        )

    if has_costume_ref:
        reference = (
            "There are two photos. Photo 1 is the real person who must appear in the result. "
            "Photo 2 is only a costume and pose reference. Copy the exact Sanjuanero Huilense "
            "dress, colors, lace, gold sequins, 3D fabric roses and dance pose from photo 2. "
            "Do not copy the face, body or identity of the model in photo 2. "
            "Keep the exact face, identity, facial features, skin tone, age and hair from photo 1."
        )
    else:
        reference = (
            "Edit the original photograph. Keep the same real person. "
            "Do not generate a different person. Keep their exact face, identity and hair."
        )

    return (
        f"{reference}\n\n"
        f"{clothing}\n\n"
        "Create a full-body photograph of this same person dancing the Sanjuanero Huilense, "
        "lifting one side of the wide skirt as in a folkloric performance. "
        "If photo 1 is a close-up or portrait, invent the rest of the body in a natural, "
        "realistic way so the person can be seen from head to toe in the typical costume. "
        "If photo 1 already shows the body, keep the same body type and proportions. "
        "Keep only the original people. Do not add extra people, a crowd, or a festival audience.\n\n"
        "Photorealistic. Simple background. No watermark. No text."
    )
