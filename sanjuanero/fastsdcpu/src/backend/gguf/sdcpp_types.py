"""
Ctypes for stablediffusion.cpp shared library
This is as per stable-diffusion_new.h
"""

from enum import IntEnum
from ctypes import (
    c_bool,
    c_char_p,
    c_float,
    c_int,
    c_int64,
    c_size_t,
    c_uint8,
    c_uint32,
    POINTER,
    Structure,
)


class CtypesEnum(IntEnum):
    """A ctypes-compatible IntEnum superclass."""

    @classmethod
    def from_param(cls, obj):
        return int(obj)


class RngType(CtypesEnum):
    STD_DEFAULT_RNG = 0
    CUDA_RNG = 1
    CPU_RNG = 2
    RNG_TYPE_COUNT = 3


class SampleMethod(CtypesEnum):
    EULER_SAMPLE_METHOD = 0
    EULER_A_SAMPLE_METHOD = 1
    HEUN_SAMPLE_METHOD = 2
    DPM2_SAMPLE_METHOD = 3
    DPMPP2S_A_SAMPLE_METHOD = 4
    DPMPP2M_SAMPLE_METHOD = 5
    DPMPP2Mv2_SAMPLE_METHOD = 6
    IPNDM_SAMPLE_METHOD = 7
    IPNDM_V_SAMPLE_METHOD = 8
    LCM_SAMPLE_METHOD = 9
    DDIM_TRAILING_SAMPLE_METHOD = 10
    TCD_SAMPLE_METHOD = 11
    RES_MULTISTEP_SAMPLE_METHOD = 12
    RES_2S_SAMPLE_METHOD = 13
    ER_SDE_SAMPLE_METHOD = 14
    EULER_CFG_PP_SAMPLE_METHOD = 15
    EULER_A_CFG_PP_SAMPLE_METHOD = 16
    EULER_GE_SAMPLE_METHOD = 17
    SAMPLE_METHOD_COUNT = 18
    # backward-compat aliases (old names, new values)
    EULER = 0
    EULER_A = 1
    HEUN = 2
    DPM2 = 3
    DPMPP2S_A = 4
    DPMPP2M = 5
    DPMPP2Mv2 = 6
    IPNDM = 7
    IPNDM_V = 8
    LCM = 9


class Scheduler(CtypesEnum):
    DISCRETE_SCHEDULER = 0
    KARRAS_SCHEDULER = 1
    EXPONENTIAL_SCHEDULER = 2
    AYS_SCHEDULER = 3
    GITS_SCHEDULER = 4
    SGM_UNIFORM_SCHEDULER = 5
    SIMPLE_SCHEDULER = 6
    SMOOTHSTEP_SCHEDULER = 7
    KL_OPTIMAL_SCHEDULER = 8
    LCM_SCHEDULER = 9
    BONG_TANGENT_SCHEDULER = 10
    LTX2_SCHEDULER = 11
    LOGIT_NORMAL_SCHEDULER = 12
    FLUX2_SCHEDULER = 13
    FLUX_SCHEDULER = 14
    BETA_SCHEDULER = 15
    SCHEDULER_COUNT = 16


# kept for backward compat — no longer used in new API
class Schedule(CtypesEnum):
    DEFAULT = 0
    DISCRETE = 0
    KARRAS = 1
    EXPONENTIAL = 2
    AYS = 3
    GITS = 4
    N_SCHEDULES = 5


class Prediction(CtypesEnum):
    EPS_PRED = 0
    V_PRED = 1
    EDM_V_PRED = 2
    FLOW_PRED = 3
    FLUX_FLOW_PRED = 4
    SEFI_FLOW_PRED = 5
    MINIT2I_FLOW_PRED = 6
    PREDICTION_COUNT = 7


class LoraApplyMode(CtypesEnum):
    LORA_APPLY_AUTO = 0
    LORA_APPLY_IMMEDIATELY = 1
    LORA_APPLY_AT_RUNTIME = 2
    LORA_APPLY_MODE_COUNT = 3


class SdVaeFormat(CtypesEnum):
    SD_VAE_FORMAT_AUTO = -1
    SD_VAE_FORMAT_FLUX = 0
    SD_VAE_FORMAT_SD3 = 1
    SD_VAE_FORMAT_FLUX2 = 2
    SD_VAE_FORMAT_COUNT = 3


class SdCacheMode(CtypesEnum):
    SD_CACHE_DISABLED = 0
    SD_CACHE_EASYCACHE = 1
    SD_CACHE_UCACHE = 2
    SD_CACHE_DBCACHE = 3
    SD_CACHE_TAYLORSEER = 4
    SD_CACHE_CACHE_DIT = 5
    SD_CACHE_SPECTRUM = 6


class SdHiresUpscaler(CtypesEnum):
    SD_HIRES_UPSCALER_NONE = 0
    SD_HIRES_UPSCALER_LATENT = 1
    SD_HIRES_UPSCALER_LATENT_NEAREST = 2
    SD_HIRES_UPSCALER_LATENT_NEAREST_EXACT = 3
    SD_HIRES_UPSCALER_LATENT_ANTIALIASED = 4
    SD_HIRES_UPSCALER_LATENT_BICUBIC = 5
    SD_HIRES_UPSCALER_LATENT_BICUBIC_ANTIALIASED = 6
    SD_HIRES_UPSCALER_LANCZOS = 7
    SD_HIRES_UPSCALER_NEAREST = 8
    SD_HIRES_UPSCALER_MODEL = 9
    SD_HIRES_UPSCALER_COUNT = 10


class SdType(CtypesEnum):
    SD_TYPE_F32 = 0
    SD_TYPE_F16 = 1
    SD_TYPE_Q4_0 = 2
    SD_TYPE_Q4_1 = 3
    # 4, 5 removed
    SD_TYPE_Q5_0 = 6
    SD_TYPE_Q5_1 = 7
    SD_TYPE_Q8_0 = 8
    SD_TYPE_Q8_1 = 9
    SD_TYPE_Q2_K = 10
    SD_TYPE_Q3_K = 11
    SD_TYPE_Q4_K = 12
    SD_TYPE_Q5_K = 13
    SD_TYPE_Q6_K = 14
    SD_TYPE_Q8_K = 15
    SD_TYPE_IQ2_XXS = 16
    SD_TYPE_IQ2_XS = 17
    SD_TYPE_IQ3_XXS = 18
    SD_TYPE_IQ1_S = 19
    SD_TYPE_IQ4_NL = 20
    SD_TYPE_IQ3_S = 21
    SD_TYPE_IQ2_S = 22
    SD_TYPE_IQ4_XS = 23
    SD_TYPE_I8 = 24
    SD_TYPE_I16 = 25
    SD_TYPE_I32 = 26
    SD_TYPE_I64 = 27
    SD_TYPE_F64 = 28
    SD_TYPE_IQ1_M = 29
    SD_TYPE_BF16 = 30
    # 31-33 removed (Q4_0_4_4, Q4_0_4_8, Q4_0_8_8)
    SD_TYPE_TQ1_0 = 34
    SD_TYPE_TQ2_0 = 35
    # 36-38 removed
    SD_TYPE_MXFP4 = 39
    SD_TYPE_NVFP4 = 40
    SD_TYPE_Q1_0 = 41
    SD_TYPE_COUNT = 42


class SDCPPLogLevel(CtypesEnum):
    SD_LOG_DEBUG = 0
    SD_LOG_INFO = 1
    SD_LOG_WARN = 2
    SD_LOG_ERROR = 3


# ---------- structs ----------


class SDImage(Structure):
    _fields_ = [
        ("width", c_uint32),
        ("height", c_uint32),
        ("channel", c_uint32),
        ("data", POINTER(c_uint8)),
    ]


class SDEmbedding(Structure):
    _fields_ = [
        ("name", c_char_p),
        ("path", c_char_p),
    ]


class SDCtxParams(Structure):
    _fields_ = [
        ("model_path", c_char_p),
        ("clip_l_path", c_char_p),
        ("clip_g_path", c_char_p),
        ("clip_vision_path", c_char_p),
        ("t5xxl_path", c_char_p),
        ("llm_path", c_char_p),
        ("llm_vision_path", c_char_p),
        ("diffusion_model_path", c_char_p),
        ("high_noise_diffusion_model_path", c_char_p),
        ("uncond_diffusion_model_path", c_char_p),
        ("embeddings_connectors_path", c_char_p),
        ("vae_path", c_char_p),
        ("audio_vae_path", c_char_p),
        ("taesd_path", c_char_p),
        ("control_net_path", c_char_p),
        ("embeddings", POINTER(SDEmbedding)),
        ("embedding_count", c_uint32),
        ("photo_maker_path", c_char_p),
        ("pulid_weights_path", c_char_p),
        ("tensor_type_rules", c_char_p),
        ("n_threads", c_int),
        ("wtype", c_int),
        ("rng_type", c_int),
        ("sampler_rng_type", c_int),
        ("prediction", c_int),
        ("lora_apply_mode", c_int),
        ("enable_mmap", c_bool),
        ("flash_attn", c_bool),
        ("diffusion_flash_attn", c_bool),
        ("tae_preview_only", c_bool),
        ("diffusion_conv_direct", c_bool),
        ("vae_conv_direct", c_bool),
        ("circular_x", c_bool),
        ("circular_y", c_bool),
        ("force_sdxl_vae_conv_scale", c_bool),
        ("chroma_use_dit_mask", c_bool),
        ("chroma_use_t5_mask", c_bool),
        ("chroma_t5_mask_pad", c_int),
        ("qwen_image_zero_cond_t", c_bool),
        ("vae_format", c_int),
        ("max_vram", c_char_p),
        ("stream_layers", c_bool),
        ("eager_load", c_bool),
        ("backend", c_char_p),
        ("params_backend", c_char_p),
        ("rpc_servers", c_char_p),
    ]


class SDSLGParams(Structure):
    _fields_ = [
        ("layers", POINTER(c_int)),
        ("layer_count", c_size_t),
        ("layer_start", c_float),
        ("layer_end", c_float),
        ("scale", c_float),
    ]


class SDGuidanceParams(Structure):
    _fields_ = [
        ("txt_cfg", c_float),
        ("img_cfg", c_float),
        ("distilled_guidance", c_float),
        ("slg", SDSLGParams),
    ]


class SDSampleParams(Structure):
    _fields_ = [
        ("guidance", SDGuidanceParams),
        ("scheduler", c_int),
        ("sample_method", c_int),
        ("sample_steps", c_int),
        ("eta", c_float),
        ("shifted_timestep", c_int),
        ("custom_sigmas", POINTER(c_float)),
        ("custom_sigmas_count", c_int),
        ("flow_shift", c_float),
        ("extra_sample_args", c_char_p),
    ]


class SDPMParams(Structure):
    _fields_ = [
        ("id_images", POINTER(SDImage)),
        ("id_images_count", c_int),
        ("id_embed_path", c_char_p),
        ("style_strength", c_float),
    ]


class SDPulidParams(Structure):
    _fields_ = [
        ("id_embedding_path", c_char_p),
        ("id_weight", c_float),
    ]


class SDTilingParams(Structure):
    _fields_ = [
        ("enabled", c_bool),
        ("temporal_tiling", c_bool),
        ("tile_size_x", c_int),
        ("tile_size_y", c_int),
        ("target_overlap", c_float),
        ("rel_size_x", c_float),
        ("rel_size_y", c_float),
        ("extra_tiling_args", c_char_p),
    ]


class SDCacheParams(Structure):
    _fields_ = [
        ("mode", c_int),
        ("reuse_threshold", c_float),
        ("start_percent", c_float),
        ("end_percent", c_float),
        ("error_decay_rate", c_float),
        ("use_relative_threshold", c_bool),
        ("reset_error_on_compute", c_bool),
        ("Fn_compute_blocks", c_int),
        ("Bn_compute_blocks", c_int),
        ("residual_diff_threshold", c_float),
        ("max_warmup_steps", c_int),
        ("max_cached_steps", c_int),
        ("max_continuous_cached_steps", c_int),
        ("taylorseer_n_derivatives", c_int),
        ("taylorseer_skip_interval", c_int),
        ("scm_mask", c_char_p),
        ("scm_policy_dynamic", c_bool),
        ("spectrum_w", c_float),
        ("spectrum_m", c_int),
        ("spectrum_lam", c_float),
        ("spectrum_window_size", c_int),
        ("spectrum_flex_window", c_float),
        ("spectrum_warmup_steps", c_int),
        ("spectrum_stop_percent", c_float),
    ]


class SDLoraT(Structure):
    _fields_ = [
        ("is_high_noise", c_bool),
        ("multiplier", c_float),
        ("path", c_char_p),
    ]


class SDHiresParams(Structure):
    _fields_ = [
        ("enabled", c_bool),
        ("upscaler", c_int),
        ("model_path", c_char_p),
        ("scale", c_float),
        ("target_width", c_int),
        ("target_height", c_int),
        ("steps", c_int),
        ("denoising_strength", c_float),
        ("upscale_tile_size", c_int),
        ("custom_sigmas", POINTER(c_float)),
        ("custom_sigmas_count", c_int),
    ]


class SDImgGenParams(Structure):
    _fields_ = [
        ("loras", POINTER(SDLoraT)),
        ("lora_count", c_uint32),
        ("prompt", c_char_p),
        ("negative_prompt", c_char_p),
        ("clip_skip", c_int),
        ("init_image", SDImage),
        ("ref_images", POINTER(SDImage)),
        ("ref_images_count", c_int),
        ("auto_resize_ref_image", c_bool),
        ("increase_ref_index", c_bool),
        ("mask_image", SDImage),
        ("width", c_int),
        ("height", c_int),
        ("sample_params", SDSampleParams),
        ("strength", c_float),
        ("seed", c_int64),
        ("batch_count", c_int),
        ("control_image", SDImage),
        ("control_strength", c_float),
        ("pm_params", SDPMParams),
        ("pulid_params", SDPulidParams),
        ("vae_tiling_params", SDTilingParams),
        ("cache", SDCacheParams),
        ("hires", SDHiresParams),
    ]
