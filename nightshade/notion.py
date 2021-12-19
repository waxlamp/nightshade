import click


@click.command()
def notion() -> None:
    """
    Create or update one or more rows in a Notion database.
    """

    click.echo("notion")
