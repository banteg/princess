import princess.parser
import princess.choices
import princess.characters
import princess.voice

import typer

app = typer.Typer()
app.add_typer(princess.choices.app)
app.add_typer(princess.parser.app)
app.add_typer(princess.characters.app)
app.add_typer(princess.voice.app)


if __name__ == "__main__":
    app()
