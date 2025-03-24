from pathlib import Path

from pydantic import BaseModel


# Base models
class Line(BaseModel):
    line: int


class Meta(BaseModel):
    line: int
    indent: int


# Parser models
class Dialogue(Line):
    character: str
    dialogue: str
    voice: str | None = None


class Choice(Line):
    choice: str
    children: list = []
    condition: str | None = None


class Label(Line):
    label: str
    children: list


class Menu(Line):
    children: list


class Jump(Line):
    dest: str


class Condition(Line):
    kind: str
    condition: str
    children: list


class Script(BaseModel):
    children: list


# Choices models
class ChoiceResult(BaseModel):
    choice: str
    condition: str | None
    label: str | None
    previous_dialogues: list[Dialogue | Choice]
    subsequent_dialogues: list[Dialogue]
    path: str | None = None
    line: int | None = None
    output: Path | None = None
    clean: str | None = None


class ChoiceResultList(BaseModel):
    choices: list[ChoiceResult] = []
