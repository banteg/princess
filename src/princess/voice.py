"""
Stage 4: Generate voices
Clean up the choices we have extracted and generate voice files.
"""

from functools import cache
from pathlib import Path

import audiofile
import audresample
import mlx.core as mx
import rich
import sounddevice
import typer
from csm_mlx import CSM, Segment, csm_1b, generate
from huggingface_hub import hf_hub_download
from mlx_lm.sample_utils import make_sampler
from mutagen.flac import FLAC

from princess.choices import ChoiceResult
from princess.game import get_game_path
from princess.text import print_choice_context, strip_formatting

app = typer.Typer()
target_sample_rate = 24_000


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


@cache
def load_hero_context():
    base = get_game_path()
    return [
        load_segment(
            base / "audio/voices/ch1/woods/hero/script_h_2.flac",
            "We can't just go through with this and listen to Him. She's a princess. We're supposed to save princesses, not slay them.",
        ),
        load_segment(
            base / "audio/voices/ch1/woods/hero/script_h_4.flac",
            "We're not going to go through with this, right? She's a princess. We're supposed to save princesses, not slay them.",
        ),
    ]


def sesame(text: str, context: list[Segment], output: Path, max_length: float = 10.0):
    model = load_model()
    sampler = make_sampler(temp=0.8, top_k=50, min_p=0.05)
    signal = generate(
        model=model,
        text=text,
        speaker=0,
        context=context,
        max_audio_length_ms=int(max_length * 1000),
        sampler=sampler,
    )
    max_samples = max_length * target_sample_rate
    if len(signal) >= max_samples * 0.95:
        rich.print("[red]Warning: max length reached, possibly a bad generation or truncation[/]")
    audiofile.write(output, signal, target_sample_rate)

    audio = FLAC(output)
    audio["TITLE"] = text
    audio.save()

    return signal


def play_signal(signal):
    sounddevice.play(signal, target_sample_rate)
    sounddevice.wait()


@app.command("generate")
def generate_line(text: str, output: Path = "output/sesame.flac", play: bool = False):
    context = load_hero_context()
    signal = sesame(text, context, output)
    if play:
        play_signal(signal)


def generate_choice_audio(choice: ChoiceResult, force: bool = False, verbose: bool = False):
    if choice.output is None:
        rich.print("[yellow]No output path for this choice")
        return

    if choice.clean is None:
        rich.print("[yellow]No clean text for this choice")
        return

    if choice.output.exists() and not force:
        rich.print(f"[yellow]file exists: {strip_formatting(choice.choice)}")
        return

    if verbose:
        rich.print("[green]generating...[/]")
        print_choice_context(choice)

    signal = sesame(choice.clean, load_hero_context(), choice.output)
    duration = len(signal) / target_sample_rate
    rich.print(f"[green]saved {duration:.2f}s audio to {choice.output}\n")


if __name__ == "__main__":
    app()
