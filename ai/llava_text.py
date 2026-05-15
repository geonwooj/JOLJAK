
"""
llava_caption.py

LLaVA 1.5 image caption utility for patent / technical drawing search pipeline.

Purpose
-------
- If user input contains an image, call llava_text(img)
- Insert the returned caption into your prompt as:

    [이미지 기반 도면 설명]
    이미지 d에 대한 설명: {llava_caption}

Install
-------
pip install -U "transformers>=4.35.3" accelerate pillow torch

Optional 4-bit loading:
pip install -U bitsandbytes

Example
-------
from llava_caption import llava_text

caption = llava_text("sample_drawing.png")
print(caption)
"""


from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union, Literal
import optimum

from PIL import Image


ImageInput = Union[str, Path, Image.Image]
CaptionLanguage = Literal["ko", "en"]


@dataclass
class LlavaCaptionConfig:
    # OpenVINO 8-bit weight-only quantized SmolVLM2 500M.
    # Function/class names are intentionally kept as "llava_*" for compatibility.
    model_id: str = "echarlaix/SmolVLM2-500M-Video-Instruct-openvino-8bit-woq"
    load_in_4bit: bool = False  # Kept for API compatibility. Not used by OpenVINO backend.
    max_new_tokens: int = 120
    language: CaptionLanguage = "ko"


_MODEL = None
_PROCESSOR = None
_CONFIG: Optional[LlavaCaptionConfig] = None


def _load_image(img: ImageInput) -> Image.Image:
    """Load image path or PIL image and convert to RGB."""
    if isinstance(img, Image.Image):
        image = img.convert("RGB")
    else:
        path = Path(img)
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {path}")
        image = Image.open(path).convert("RGB")

    # CPU/OpenVINO speed guard. For patent drawings, 768 is usually a reasonable start.
    # If small labels are important, raise this to 1024. If speed is more important, lower to 512.
    max_side = int(os.getenv("LLAVA_CAPTION_MAX_SIDE", "768"))
    w, h = image.size
    if max(w, h) > max_side:
        scale = max_side / max(w, h)
        new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
        image = image.resize(new_size, Image.Resampling.LANCZOS)

    return image


def _get_torch_dtype():
    """Kept for compatibility with older code. OpenVINO backend does not use this."""
    import torch
    return torch.float16 if torch.cuda.is_available() else torch.float32


def _get_model_device(model):
    """
    Return a safe input device for PyTorch models.

    OpenVINO models do not need torch tensor movement to cuda/cpu here, so this returns None
    for OpenVINO backend.
    """
    if getattr(model, "_chatgpt_openvino_backend", False):
        return None

    try:
        return next(model.parameters()).device
    except Exception:
        return None


def _load_llava(config: LlavaCaptionConfig):
    """
    Lazy-load SmolVLM2 OpenVINO model and processor.

    Function name is kept as _load_llava for compatibility with existing code.
    """
    global _MODEL, _PROCESSOR, _CONFIG

    if _MODEL is not None and _PROCESSOR is not None and _CONFIG == config:
        return _MODEL, _PROCESSOR

    from transformers import AutoProcessor
    from optimum.intel import OVModelForVisualCausalLM

    processor = AutoProcessor.from_pretrained(config.model_id)

    # Intel CPU/iGPU용. 기본 AUTO는 OpenVINO가 가능한 장치를 고르게 함.
    # 필요시 환경변수로 강제 가능:
    #   set OV_DEVICE=CPU
    #   set OV_DEVICE=GPU
    #   set OV_DEVICE=AUTO
    ov_device = os.getenv("OV_DEVICE", "AUTO").upper()

    try:
        model = OVModelForVisualCausalLM.from_pretrained(
            config.model_id,
            device=ov_device,
        )
    except Exception as e:
        # Intel GPU plugin이나 AUTO에서 실패하면 CPU로 재시도
        if ov_device != "CPU":
            print(f"[warn] OpenVINO device={ov_device} failed: {e}")
            print("[warn] retrying with OpenVINO device=CPU")
            model = OVModelForVisualCausalLM.from_pretrained(
                config.model_id,
                device="CPU",
            )
        else:
            raise

    model.eval()
    setattr(model, "_chatgpt_openvino_backend", True)

    _MODEL = model
    _PROCESSOR = processor
    _CONFIG = config

    return model, processor


def build_drawing_caption_prompt(language: CaptionLanguage = "ko") -> str:
    """
    Build a stable instruction prompt for technical / patent drawing captioning.

    The output is intentionally short because the downstream KorPatBERT search prompt
    will normalize this caption into abstract / claims / description sections.
    """
    if language == "en":
        return (
            "Describe the given image as a technical drawing or patent figure. "
            "Focus only on visually grounded information. "
            "Write 3 to 5 concise sentences. "
            "Include: drawing type, main components, relationships between components, "
            "input/process/output flow if visible, and uncertain parts. "
            "Do not invent specific algorithms, numerical values, effects, or device names "
            "that are not visible in the image. "
            "Use cautious expressions such as 'appears to' when uncertain."
        )

    # SmolVLM 계열은 영어 지시가 더 안정적인 경우가 있어,
    # 출력은 한국어로 요구하되 지시 구조는 단순하게 유지.
    return (
        "Describe the image as a technical drawing or patent figure, but answer in Korean. "
        "Use only visually grounded information. "
        "Write 3 to 5 concise Korean sentences. "
        "Include the drawing type, main components, relationships between components, "
        "visible input/process/output flow, and uncertain parts. "
        "Do not invent specific algorithms, numerical values, effects, or device names "
        "that are not visible in the image. "
        "When uncertain, use cautious Korean expressions such as '보인다' or '추정된다'."
    )


def _make_conversation(prompt: str):
    """
    SmolVLM2 chat-template compatible conversation.
    Function name is kept unchanged for compatibility.
    """
    return [
        {
            "role": "user",
            "content": [
                {"type": "image"},
                {"type": "text", "text": prompt},
            ],
        }
    ]


def llava_text(
    img: Optional[ImageInput],
    *,
    prompt: Optional[str] = None,
    model_id: str = "echarlaix/SmolVLM2-500M-Video-Instruct-openvino-8bit-woq",
    load_in_4bit: bool = False,
    max_new_tokens: int = 120,
    language: CaptionLanguage = "ko",
) -> str:
    """
    Convert an input image into a drawing/patent-style caption using SmolVLM2 OpenVINO.

    Function name is intentionally kept as llava_text for compatibility.

    Parameters
    ----------
    img:
        Image path, Path object, PIL.Image, or None.
        If None, returns an empty string.
    prompt:
        Optional custom instruction. If None, a drawing-caption prompt is used.
    model_id:
        Hugging Face model id. Default: OpenVINO 8-bit SmolVLM2-500M.
    load_in_4bit:
        Kept for compatibility. Ignored by OpenVINO backend.
    max_new_tokens:
        Maximum generated caption length.
    language:
        "ko" for Korean caption, "en" for English caption.

    Returns
    -------
    str
        Caption text. Empty string if img is None.
    """
    if img is None:
        return ""

    config = LlavaCaptionConfig(
        model_id=model_id,
        load_in_4bit=load_in_4bit,
        max_new_tokens=max_new_tokens,
        language=language,
    )

    image = _load_image(img)
    model, processor = _load_llava(config)

    instruction = prompt or build_drawing_caption_prompt(language=language)
    conversation = _make_conversation(instruction)

    # Preferred path for recent transformers / SmolVLM2 processors.
    try:
        formatted_prompt = processor.apply_chat_template(
            conversation,
            add_generation_prompt=True,
        )
    except Exception:
        formatted_prompt = f"USER: <image>\n{instruction}\nASSISTANT:"

    inputs = processor(
        images=image,
        text=formatted_prompt,
        return_tensors="pt",
    )

    # OpenVINO backend expects CPU tensors; no CUDA movement needed.
    device = _get_model_device(model)
    if device is not None:
        inputs = {k: v.to(device) for k, v in inputs.items()}

    output_ids = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        do_sample=False,
    )

    generated_ids = output_ids[0][inputs["input_ids"].shape[-1]:]
    caption = processor.decode(generated_ids, skip_special_tokens=True)

    return clean_llava_caption(caption)


def clean_llava_caption(text: str) -> str:
    """Light cleanup for generated caption text."""
    text = text.strip()

    for marker in ["ASSISTANT:", "Assistant:", "assistant:"]:
        if marker in text:
            text = text.split(marker, 1)[-1].strip()

    text = text.replace("<end_of_utterance>", " ").strip()
    text = " ".join(text.split())

    return text


def build_prompt_input_with_image_caption(
    raw_input: str,
    img: Optional[ImageInput] = None,
    *,
    image_caption: Optional[str] = None,
    caption_prefix: str = "이미지 d에 대한 설명:",
    **llava_kwargs,
) -> str:
    """
    Helper for your final prompt input block.

    Use this when constructing:

        사용자 입력:
        <<<
        [사용자 텍스트 입력]
        {raw_input}

        [이미지 기반 도면 설명]
        이미지 d에 대한 설명: {llava_caption}
        >>>

    If image_caption is already computed, pass it directly to avoid re-running VLM.
    """
    raw_input = (raw_input or "").strip()

    if image_caption is None:
        image_caption = llava_text(img, **llava_kwargs) if img is not None else ""

    image_caption = (image_caption or "").strip()

    if not image_caption:
        return f"[사용자 텍스트 입력]\n{raw_input}"

    return (
        f"[사용자 텍스트 입력]\n"
        f"{raw_input}\n\n"
        f"[이미지 기반 도면 설명]\n"
        f"{caption_prefix} {image_caption}"
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate caption for a technical drawing image.")
    parser.add_argument("image", type=str, help="Path to image file")
    parser.add_argument("--lang", choices=["ko", "en"], default="ko", help="Caption language")
    parser.add_argument("--model-id", default="echarlaix/SmolVLM2-500M-Video-Instruct-openvino-8bit-woq")
    parser.add_argument("--max-new-tokens", type=int, default=120)
    parser.add_argument("--load-in-4bit", action="store_true")  # kept for compatibility

    args = parser.parse_args()

    print(
        llava_text(
            args.image,
            model_id=args.model_id,
            load_in_4bit=args.load_in_4bit,
            max_new_tokens=args.max_new_tokens,
            language=args.lang,
        )
    )
