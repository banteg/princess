import typer

import princess.characters
import princess.choices
import princess.parser
import princess.pipeline
import princess.voice
import princess.annotate
import princess.ab_test

app = typer.Typer()
app.add_typer(princess.choices.app)
app.add_typer(princess.parser.app)
app.add_typer(princess.characters.app)
app.add_typer(princess.voice.app, name="sesame")
app.add_typer(princess.pipeline.app, name="pipeline")
app.add_typer(princess.annotate.app)
app.add_typer(princess.ab_test.app)

if __name__ == "__main__":
    app()
