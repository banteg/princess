"""
Stage 4: Generate voices
Clean up the choices we have extracted and generate voice files.
"""

import re
from functools import cache
from hashlib import sha256
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
from rich.progress import track

from princess.characters import extract_characters
from princess.choices import ChoiceResult, extract_choices_from_script
from princess.game import get_game_path
from princess.parser import Choice, Dialogue

app = typer.Typer()
target_sample_rate = 24_000

rewrites = {
    "N-no. I w-won't t-tell you.": "No, I won't tell you.",
}


def clean_choice_for_voice(choice: str) -> str | None:
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

    return rewrites.get(choice, choice) if choice else None


def strip_formatting(text: str):
    text = re.sub(r"\{[^}]+\}", "", text)
    text = text.replace("''", '"')
    text = text.replace("\\n", "")
    return text


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


def get_output_path(choice: ChoiceResult) -> Path:
    choice_hash = sha256(choice.choice.encode()).hexdigest()
    return Path("output/voice") / f"{choice_hash}.flac"


def print_dialogues(items: list[Dialogue | Choice]):
    characters = extract_characters()
    for item in items:
        match item:
            case Dialogue(character=character, dialogue=dialogue):
                rich.print(f"[yellow]{characters[character]}[/]: [dim]{strip_formatting(dialogue)}")
            case Choice(choice=choice):
                rich.print(f"[red]Choice:[/] [dim]{strip_formatting(choice)}")


def generate_choice_audio(choice: ChoiceResult, force: bool = False):
    text = clean_choice_for_voice(choice.choice)
    if text is None:
        return

    output = get_output_path(choice)
    if output.exists() and not force:
        rich.print(f"[yellow]file exists: {strip_formatting(choice.choice)}")
        return

    rich.print("[green]generating...[/]")
    print_dialogues(choice.previous_dialogues[-3:])
    rich.print(f"[magenta]Choice:[/] {strip_formatting(choice.choice)}")
    rich.print(f"[magenta]Voiced: [bold blue]{text}")
    print_dialogues(choice.subsequent_dialogues[:3])

    sesame(text, load_hero_context(), output)
    rich.print(f"[green]saved {output}\n")


@app.command("process")
def process_choices(path: Path, force: bool = False):
    choices = extract_choices_from_script(path)
    for i, item in enumerate(track(choices), 1):
        generate_choice_audio(item, force)


if __name__ == "__main__":
    app()
