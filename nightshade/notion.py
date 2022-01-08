import click
import json
import os
import requests
import sys
from typing import Dict, Tuple

from .models import MovieData

from pprint import pprint

s = requests.Session()


# It's not worth the complexity to cook up the right TypedDict definition for
# the `rt` argument; see https://github.com/python/mypy/issues/5149.
def rt_to_moviedata(rt: Dict) -> MovieData:
    return MovieData(
        title=rt["Title"]["title"][0]["plain_text"],
        year=rt["Release Year"]["number"],
        href=rt["Rotten Tomatoes URL"]["url"],
        audience=rt["Audience Score"]["number"],
        tomatometer=rt["Tomatometer"]["number"],
        rating=rt["MPAA Rating"]["select"]["name"]
        if rt["MPAA Rating"]["select"] is not None
        else None,
        genres=[x["name"] for x in rt["Genre"]["multi_select"]],
        runtime=rt["Runtime"]["number"],
    )


def notion_api(path: str) -> str:
    return f"https://api.notion.com/v1/{path}"


def get_rows(database_id: str) -> Dict[str, MovieData]:
    # Iterate through the pages of rows in the database.
    api = notion_api(f"databases/{database_id}/query")
    result = s.post(
        api,
        data=json.dumps(
            {
                "page_size": 100,
            }
        ),
    )

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

        result = s.post(
            api,
            data=json.dumps(
                {
                    "page_size": 100,
                    "start_cursor": results["next_cursor"],
                }
            ),
        )

    if dupes:
        pprint(dupes)
        raise RuntimeError("dupes")

    return movies


def create_row(database_id: str, movie: MovieData, search: str, notes: str) -> None:
    blocks = [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "text": [
                    {
                        "type": "text",
                        "text": {
                            "content": "Original search phrase: ",
                        },
                        "annotations": {
                            "bold": True,
                        },
                    },
                    {
                        "type": "text",
                        "text": {
                            "content": search,
                        },
                        "annotations": {
                            "code": True,
                        },
                    },
                ],
            },
        },
    ]

    if notes:
        blocks += [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "text": [
                        {
                            "type": "text",
                            "text": {
                                "content": text,
                            },
                        },
                    ]
                },
            }
            for text in notes.replace("\\n", "\n").split("\n\n")
        ]

    properties = {
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
        "Genre": {
            "multi_select": [{"name": tag} for tag in movie.genres],
        },
        "Runtime": {
            "number": movie.runtime,
        },
        "Status": {
            "select": {
                "name": "want to watch",
            },
        },
    }

    if movie.rating:
        properties["MPAA Rating"] = {
            "select": {
                "name": movie.rating,
            },
        }

    api = notion_api("pages")
    result = s.post(
        api,
        data=json.dumps(
            {
                "parent": {
                    "type": "database_id",
                    "database_id": database_id,
                },
                "properties": properties,
                "children": blocks,
            }
        ),
    )

    if result.status_code != 200:
        raise RuntimeError(result.text)


@click.command()
@click.option("-i", "--input", "input_file", type=click.Path())
@click.option("-c", "--credential-file", type=click.Path())
@click.option("-d", "--database-id", type=str, required=True)
def notion(
    input_file: click.Path, credential_file: click.Path, database_id: str
) -> None:
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
    s.headers.update(
        {
            "Authorization": f"Bearer {notion_key}",
            "Notion-Version": "2021-08-16",
            "Content-Type": "application/json",
        }
    )

    # Open the input file for reading.
    input_stream = sys.stdin
    try:
        if input_file:
            input_stream = open(input_file)
    except OSError as err:
        print(f"error opening file '{input_file}': {err}", file=sys.stderr)
        sys.exit(1)

    # Create movie data models from the input.
    def split_data(line: str) -> Tuple[MovieData, str, str]:
        rec = json.loads(line)
        original = rec["original"]
        notes = rec["notes"]
        del rec["original"]
        del rec["notes"]

        return (MovieData.parse_obj(rec), original, notes)

    movies = [split_data(line) for line in input_stream]

    # Retrieve all the movies in the Notion database.
    db_movies = get_rows(database_id)

    # Add the input movies to the database.
    for i, (m, orig, notes) in enumerate(movies):
        if str(m.href) in db_movies:
            print(
                f"({i}) {m.title} ({m.year}) already in database, skipping",
                file=sys.stderr,
            )
            continue

        print(
            f"({i}) Adding {m.title} ({m.year})...", end="", file=sys.stderr, flush=True
        )
        create_row(database_id, m, orig, notes)
        print("done")
