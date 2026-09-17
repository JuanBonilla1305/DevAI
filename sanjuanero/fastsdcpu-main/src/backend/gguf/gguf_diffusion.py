"""
Wrapper class to call the stablediffusion.cpp shared library for GGUF support
"""

import ctypes
import platform
from ctypes import (
    POINTER,
    c_bool,
    c_char_p,
    c_float,
    c_int,
    c_int64,
    c_void_p,
)
from dataclasses import dataclass, field
from os import path
from typing import List, Any

import numpy as np
from PIL import Image

from backend.gguf.sdcpp_types import (
    RngType,
    SampleMethod,
    Schedule,
    Scheduler,
    SDCPPLogLevel,
    SDCtxParams,
    SDImage,
    SDImgGenParams,
    SdType,
)


@dataclass
class ModelConfig:
    model_path: str = ""
    clip_l_path: str = ""
    t5xxl_path: str = ""
    llm_path: str = ""          # LLM text encoder (e.g. Qwen3 for Flux.2-Klein)
    diffusion_model_path: str = ""
    vae_path: str = ""
    taesd_path: str = ""
    control_net_path: str = ""
    lora_model_dir: str = ""
    embed_dir: str = ""
    stacked_id_embed_dir: str = ""
    # kept for backward compat, no longer passed to new_sd_ctx
    vae_decode_only: bool = True
    vae_tiling: bool = False
    free_params_immediately: bool = False
    keep_clip_on_cpu: bool = False
    keep_control_net_cpu: bool = False
    keep_vae_on_cpu: bool = False
    params_backend: str = ""
    diffusion_flash_attn: bool = True
    n_threads: int = 4
    wtype: SdType = SdType.SD_TYPE_COUNT  # auto-detect from model file
    rng_type: RngType = RngType.STD_DEFAULT_RNG
    schedule: Schedule = Schedule.DEFAULT  # deprecated, use Txt2ImgConfig.scheduler


@dataclass
class Txt2ImgConfig:
    prompt: str = "a man wearing sun glasses, highly detailed"
    negative_prompt: str = ""
    clip_skip: int = -1
    cfg_scale: float = 2.0
    guidance: float = 3.5
    width: int = 512
    height: int = 512
    sample_method: SampleMethod = SampleMethod.EULER_SAMPLE_METHOD
    scheduler: Scheduler = Scheduler.DISCRETE_SCHEDULER
    sample_steps: int = 1
    seed: int = -1
    batch_count: int = 2
    control_cond: Image = None
    control_strength: float = 0.90
    style_strength: float = 0.5
    normalize_input: bool = False
    input_id_images_path: bytes = b""


class GGUFDiffusion:
    """GGUF Diffusion
    To support GGUF diffusion model based on stablediffusion.cpp
    https://github.com/ggerganov/ggml/blob/master/docs/gguf.md
    Implemented based on stable-diffusion_new.h
    """

    def __init__(
        self,
        libpath: str,
        config: ModelConfig,
        logging_enabled: bool = False,
    ):
        sdcpp_shared_lib_path = self._get_sdcpp_shared_lib_path(libpath)
        if platform.system() == "Windows":
            import os
            os.add_dll_directory(path.abspath(libpath))
        try:
            self.libsdcpp = ctypes.CDLL(sdcpp_shared_lib_path)
        except OSError as e:
            print(f"Failed to load library {sdcpp_shared_lib_path}")
            raise ValueError(f"Error: {e}")

        # Flux.1 models need clip_l + t5xxl; Flux.2-Klein uses llm_path instead
        using_llm = config.llm_path and path.exists(config.llm_path)
        if not using_llm:
            if not config.clip_l_path or not path.exists(config.clip_l_path):
                raise ValueError(
                    "CLIP model file not found,please check readme.md for GGUF model usage"
                )
            if not config.t5xxl_path or not path.exists(config.t5xxl_path):
                raise ValueError(
                    "T5XXL model file not found,please check readme.md for GGUF model usage"
                )

        if not config.diffusion_model_path or not path.exists(
            config.diffusion_model_path
        ):
            raise ValueError(
                "Diffusion model file not found,please check readme.md for GGUF model usage"
            )

        if not config.vae_path or not path.exists(config.vae_path):
            raise ValueError(
                "VAE model file not found,please check readme.md for GGUF model usage"
            )

        self.model_config = config

        # set log callback early so new_sd_ctx errors are visible
        if logging_enabled:
            self._set_logcallback()

        # initialise ctx params via library to get safe defaults for all fields
        self.libsdcpp.sd_ctx_params_init.argtypes = [POINTER(SDCtxParams)]
        self.libsdcpp.sd_ctx_params_init.restype = None

        ctx_params = SDCtxParams()
        self.libsdcpp.sd_ctx_params_init(ctypes.byref(ctx_params))

        ctx_params.model_path = self._str_to_bytes(config.model_path)
        ctx_params.clip_l_path = self._str_to_bytes(config.clip_l_path)
        ctx_params.t5xxl_path = self._str_to_bytes(config.t5xxl_path)
        ctx_params.llm_path = self._str_to_bytes(config.llm_path)
        ctx_params.diffusion_model_path = self._str_to_bytes(config.diffusion_model_path)
        ctx_params.vae_path = self._str_to_bytes(config.vae_path)
        ctx_params.taesd_path = self._str_to_bytes(config.taesd_path)
        ctx_params.control_net_path = self._str_to_bytes(config.control_net_path)
        ctx_params.n_threads = config.n_threads
        ctx_params.wtype = int(config.wtype)
        ctx_params.rng_type = int(config.rng_type)
        if config.params_backend:
            ctx_params.params_backend = self._str_to_bytes(config.params_backend)
        ctx_params.diffusion_flash_attn = config.diffusion_flash_attn

        self.libsdcpp.new_sd_ctx.argtypes = [POINTER(SDCtxParams)]
        self.libsdcpp.new_sd_ctx.restype = c_void_p

        self.sd_ctx = self.libsdcpp.new_sd_ctx(ctypes.byref(ctx_params))

        if not self.sd_ctx:
            raise RuntimeError("Failed to create sd_ctx: new_sd_ctx returned NULL")

        # register free_sd_images once — uses library's own CRT, safe on Windows
        self.libsdcpp.free_sd_images.argtypes = [POINTER(SDImage), c_int]
        self.libsdcpp.free_sd_images.restype = None

    def _set_logcallback(self):
        print("Setting logging callback")
        SdLogCallbackType = ctypes.CFUNCTYPE(
            None,
            c_int,
            ctypes.c_char_p,
            ctypes.c_void_p,
        )

        self.libsdcpp.sd_set_log_callback.argtypes = [
            SdLogCallbackType,
            ctypes.c_void_p,
        ]
        self.libsdcpp.sd_set_log_callback.restype = None
        self.c_log_callback = SdLogCallbackType(self.log_callback)
        self.libsdcpp.sd_set_log_callback(self.c_log_callback, None)

    def _get_sdcpp_shared_lib_path(self, root_path: str) -> str:
        system_name = platform.system()
        print(f"GGUF Diffusion on {system_name}")

        if system_name == "Windows":
            lib_name = "stable-diffusion.dll"
        elif system_name == "Linux":
            lib_name = "libstable-diffusion.so"
        elif system_name == "Darwin":
            lib_name = "libstable-diffusion.dylib"
        else:
            raise OSError(f"Unsupported platform: {system_name}")

        return path.join(root_path, lib_name)

    @staticmethod
    def log_callback(level, text, data):
        try:
            msg = text.decode("utf-8")
        except (UnicodeDecodeError, AttributeError):
            msg = text.decode("utf-8", errors="replace")
        try:
            print(msg, end="")
        except UnicodeEncodeError:
            import sys
            enc = sys.stdout.encoding or "utf-8"
            print(msg.encode(enc, errors="replace").decode(enc), end="")

    def _str_to_bytes(self, in_str: str, encoding: str = "utf-8") -> bytes:
        if in_str:
            return in_str.encode(encoding)
        else:
            return b""

    def generate_text2mg(self, txt2img_cfg: Txt2ImgConfig) -> List[Any]:
        self.libsdcpp.sd_img_gen_params_init.argtypes = [POINTER(SDImgGenParams)]
        self.libsdcpp.sd_img_gen_params_init.restype = None

        # 2-arg form: returns sd_image_t* directly (matches actual DLL ABI)
        self.libsdcpp.generate_image.argtypes = [c_void_p, POINTER(SDImgGenParams)]
        self.libsdcpp.generate_image.restype = POINTER(SDImage)

        # ask the library for the correct scheduler for this model+method pair
        self.libsdcpp.sd_get_default_scheduler.argtypes = [c_void_p, c_int]
        self.libsdcpp.sd_get_default_scheduler.restype = c_int
        scheduler = self.libsdcpp.sd_get_default_scheduler(
            self.sd_ctx, int(txt2img_cfg.sample_method)
        )
        try:
            method_label = SampleMethod(int(txt2img_cfg.sample_method)).name.lower().replace("_sample_method", "")
        except ValueError:
            method_label = str(int(txt2img_cfg.sample_method))
        try:
            sched_label = Scheduler(scheduler).name.lower().replace("_scheduler", "")
        except ValueError:
            sched_label = str(scheduler)
        print(f"  default sampler   : {method_label}")
        print(f"  default scheduler : {sched_label}")

        img_params = SDImgGenParams()
        self.libsdcpp.sd_img_gen_params_init(ctypes.byref(img_params))

        img_params.prompt = self._str_to_bytes(txt2img_cfg.prompt)
        img_params.negative_prompt = self._str_to_bytes(txt2img_cfg.negative_prompt)
        img_params.clip_skip = txt2img_cfg.clip_skip
        img_params.width = txt2img_cfg.width
        img_params.height = txt2img_cfg.height
        img_params.seed = txt2img_cfg.seed
        img_params.batch_count = txt2img_cfg.batch_count
        img_params.control_strength = txt2img_cfg.control_strength
        img_params.sample_params.sample_method = int(txt2img_cfg.sample_method)
        img_params.sample_params.scheduler = scheduler
        img_params.sample_params.sample_steps = txt2img_cfg.sample_steps
        img_params.sample_params.guidance.txt_cfg = txt2img_cfg.cfg_scale
        img_params.sample_params.guidance.distilled_guidance = txt2img_cfg.guidance

        image_buffer = self.libsdcpp.generate_image(
            self.sd_ctx,
            ctypes.byref(img_params),
        )

        if not image_buffer:
            return []

        batch = max(txt2img_cfg.batch_count, 1)
        images = self._get_sd_images_from_buffer(image_buffer, batch)
        self.libsdcpp.free_sd_images(image_buffer, c_int(batch))
        return images

    def _get_sd_images_from_buffer(
        self,
        image_buffer: Any,
        batch_count: int,
    ) -> List[Any]:
        images = []
        for i in range(batch_count):
            image = image_buffer[i]
            print(
                f"Generated image: {image.width}x{image.height} with {image.channel} channels"
            )

            width = image.width
            height = image.height
            channels = image.channel
            pixel_data = np.ctypeslib.as_array(
                image.data, shape=(height, width, channels)
            )

            if channels == 1:
                pil_image = Image.fromarray(pixel_data.squeeze(), mode="L")
            elif channels == 3:
                pil_image = Image.fromarray(pixel_data, mode="RGB")
            elif channels == 4:
                pil_image = Image.fromarray(pixel_data, mode="RGBA")
            else:
                raise ValueError(f"Unsupported number of channels: {channels}")

            images.append(pil_image)
        return images

    def terminate(self):
        if self.libsdcpp:
            if self.sd_ctx:
                self.libsdcpp.free_sd_ctx.argtypes = [c_void_p]
                self.libsdcpp.free_sd_ctx.restype = None
                self.libsdcpp.free_sd_ctx(self.sd_ctx)
                self.sd_ctx = None
                self.libsdcpp = None
