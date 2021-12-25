import click
import json
import os
import requests
import sys
from typing import List

from .models import MovieData

from pprint import pprint

s = requests.Session()


def rt_to_moviedata(rt) -> MovieData:
    return MovieData(
        title=rt["Title"]["title"][0]["plain_text"],
        year=rt["Release Year"]["number"],
        href=rt["Rotten Tomatoes URL"]["url"],
        audience=rt["Audience Score"]["number"],
        tomatometer=rt["Tomatometer"]["number"],
        rating=rt["MPAA Rating"]["select"]["name"],
        genres=[x["name"] for x in rt["Genre"]["multi_select"]],
        runtime=rt["Runtime"]["number"],
    )


def notion_api(path: str) -> str:
    return f"https://api.notion.com/v1/{path}"


def find_entry(database_id: str, url: str) -> List[str]:
    # Hit the database looking for the specific movie.
    api = notion_api(f"databases/{database_id}/query")
    result = s.post(api, data=json.dumps({
        "filter": {
            "property": "Rotten Tomatoes URL",
            "text": {"equals": url}
        }
    }))

    # Bail out if the request fails.
    if result.status_code != 200:
        raise RuntimeError(result.text)

    # Gather the results. There should only be one or zero.
    results = result.json()["results"]
    if len(results) == 0:
        return None
    elif len(results) == 1:
        return results[0]
    else:
        raise RuntimeError("too many results")


def get_rows(database_id: str) -> List[MovieData]:
    # Iterate through the pages of rows in the database.
    api = notion_api(f"databases/{database_id}/query")
    result = s.post(api, data=json.dumps({
        "page_size": 100,
    }))

    movies = {}
    names = set()
    dupes = set()

    while True:
        if result.status_code != 200:
            raise RuntimeError("something went wrong")

        results = result.json()

        new = [rt_to_moviedata(r["properties"]) for r in results["results"]]

        for n in new:
            href = str(n.href)
            if href in names:
                dupes.add(href)
            names.add(href)

        movies.update({str(x.href): x for x in new})

        if not results["has_more"]:
            break

        result = s.post(api, data=json.dumps({
            "page_size": 100,
            "start_cursor": results["next_cursor"],
        }))

    if dupes:
        pprint(dupes)
        raise RuntimeError("dupes")

    return movies


def create_row(database_id: str, movie: MovieData):
    api = notion_api("pages")
    result = s.post(api, data=json.dumps({
        "parent": {
            "type": "database_id",
            "database_id": database_id,
        },
        "properties": {
            "Title": {
                "title": [
                    {
                        "type": "text",
                        "text": {
                            "content": movie.title,
                        },
                    },
                ],
            },
            "Release Year": {
                "number": movie.year,
            },
            "Rotten Tomatoes URL": {
                "url": str(movie.href),
            },
            "Audience Score": {
                "number": movie.audience,
            },
            "Tomatometer": {
                "number": movie.tomatometer,
            },
            "MPAA Rating": {
                "select": {
                    "name": movie.rating,
                },
            },
            "Genre": {
                "multi_select": [{"name": tag} for tag in movie.genres],
            },
            "Runtime": {
                "number": movie.runtime,
            },
        },
    }))

    if result.status_code != 200:
        raise RuntimeError(result)


@click.command()
@click.option("-i", "--input", "input_file", type=click.Path())
@click.option("-c", "--credential-file", type=click.Path())
@click.option("-d", "--database-id", type=str, required=True)
def notion(input_file: click.Path, credential_file: click.Path, database_id: str) -> None:
    """
    Create or update one or more rows in a Notion database.
    """

    # Check for Notion credentials.
    notion_key = os.getenv("NIGHTSHADE_NOTION_KEY")
    if credential_file:
        with open(credential_file) as f:
            notion_key = f.read().strip()

    if notion_key is None:
        print(
            "No credential file specified, and NIGHTSHADE_NOTION_KEY not set",
            file=sys.stderr,
        )
        sys.exit(1)

    # Update the session object with the necessary headers.
    s.headers.update({
        "Authorization": f"Bearer {notion_key}",
        "Notion-Version": "2021-08-16",
        "Content-Type": "application/json",
    })

    # Open the input file for reading.
    input_stream = sys.stdin
    try:
        if input_file:
            input_stream = open(input_file)
    except OSError as err:
        print(f"error opening file '{input_file}': {err}", file=sys.stderr)
        sys.exit(1)

    # Create movie data models from the input.
    movies = [MovieData.parse_raw(line) for line in input_stream]

    # Retrieve all the movies in the Notion database.
    db_movies = get_rows(database_id)

    # Add the input movies to the database.
    for m in movies:
        if str(m.href) in db_movies:
            print(f"{m.title} ({m.year}) already in database, skipping", file=sys.stderr)
            continue

        create_row(database_id, m)
