import typer

from zeph.main import zeph


def run():
    """
    Run the CLI from a path like `zeph__main__:run`.
    Useful for poetry.
    """
    typer.run(zeph)


run()
