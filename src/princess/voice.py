import re
from functools import cache
from pathlib import Path

import audiofile
import audresample
import mlx.core as mx
import typer
from csm_mlx import CSM, Segment, csm_1b, generate
from huggingface_hub import hf_hub_download
from mlx_lm.sample_utils import make_sampler
from mutagen.flac import FLAC

app = typer.Typer()
target_sample_rate = 24_000


def clean_choice_for_voice(choice):
    """
    Clean menu choice text for text-to-speech processing.

    Args:
        choice: The raw choice text

    Returns:
        Cleaned text suitable for TTS, or None if not applicable
    """
    bullet_re = re.compile(r"•\s+")
    formatting_re = re.compile(r"\{[^\}]+\}")
    prefixes_re = re.compile(r"\([^\)]+\)\s+")
    actions_re = re.compile(r"\[\[[^]]+\]")
    quoted_text_re = re.compile(r"''(.+?)''")
    special_re = re.compile(
        r"^(Say|Join|Follow|Play|Return|Make|Continue|Ignore|Embrace|Investigate|Go|Do|Drop|Tighten|Kneel|Force|Try)\s"
    )

    choice = bullet_re.sub("", choice)
    choice = formatting_re.sub("", choice)
    choice = prefixes_re.sub("", choice)
    choice = actions_re.sub("", choice)

    # quoted text is 100% spoken dialogue
    if quoted_text := quoted_text_re.findall(choice):
        return " ".join(quoted_text)

    # non-verbal lines
    if special_re.search(choice):
        return None

    rewrites = {
        "N-no. I w-won't t-tell you.": "No, I won't tell you.",
    }

    return rewrites.get(choice, choice) if choice else None


@cache
def load_model():
    csm = CSM(csm_1b())
    weights = hf_hub_download(repo_id="senstella/csm-1b-mlx", filename="ckpt.safetensors")
    csm.load_weights(weights)
    return csm


def load_segment(audio: Path, text: str, speaker: int = 0) -> Segment:
    data, sample_rate = audiofile.read(audio)
    data = audresample.resample(data, sample_rate, target_sample_rate)
    data = mx.array(data.squeeze())
    return Segment(speaker=speaker, text=text, audio=data)


def sesame(text: str, context: list[Segment], output: Path, max_length: float = 15.0):
    model = load_model()
    sampler = make_sampler(temp=0.9, top_k=50)
    signal = generate(
        model=model,
        text=text,
        speaker=0,
        context=context,
        max_audio_length_ms=int(max_length * 1000),
        sampler=sampler,
    )
    audiofile.write(output, signal, target_sample_rate)

    audio = FLAC(output)
    audio["TITLE"] = text
    audio.save()

    return output


@app.command("sesame")
def main(text: str, output: Path = "output/sesame.flac"):
    sesame(text, [], output)


if __name__ == "__main__":
    app()
