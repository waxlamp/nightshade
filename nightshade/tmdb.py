import click
import json
import os
from pprint import pprint
import requests
import sys
import textwrap

from typing import List, Optional

from .models import TMDBSearchResult, TMDBMovie


def display(s: TMDBSearchResult, idx: int) -> str:
    release_year = s.release_date.split("-")[0]
    spacer = " " * 8
    wrapped_overview = textwrap.fill(s.overview, initial_indent=spacer, subsequent_indent=spacer)

    return f"""({idx}) {s.title} ({release_year})
{wrapped_overview}"""


def get_movie_detail(detail) -> TMDBMovie:
    release_dates = detail["release_dates"]["results"]
    us_release_dates = [x for x in release_dates if x["iso_3166_1"] == "US"]
    mpaa_rating = None
    if len(us_release_dates) == 1:
        wide_release = [x for x in us_release_dates[0]["release_dates"] if x["release_date"][:10] == detail["release_date"]]

        if len(wide_release) == 1:
            mpaa_rating = wide_release[0]["certification"]
        else:
            raise RuntimeError("multiple wide release dates")
    else:
        raise RuntimeError("more than one US release record")

    return TMDBMovie(
        id=detail["id"],
        genres=(x["name"] for x in detail["genres"]),
        overview=detail["overview"],
        release_date=detail["release_date"],
        runtime=detail["runtime"],
        title=detail["title"],
        mpaa_rating=mpaa_rating,
        vote_average=detail["vote_average"],
        vote_count=detail["vote_count"],
    )


@click.command()
@click.argument("query", nargs=-1, required=True)
@click.option("-y", "--year", required=False, type=int)
@click.option("--dry-run", is_flag=True)
def tmdb(query: List[str], year: Optional[int], dry_run: bool) -> None:
    q = " ".join(query)

    if (tmdb_read_token := os.getenv("TMDB_READ_TOKEN")) is None:
        print("fatal: environment variable TMDB_READ_TOKEN is required", file=sys.stderr)
        sys.exit(1)

    if (notion_key := os.getenv("NOTION_KEY")) is None:
        print("fatal: environment variable NOTION_KEY is required", file=sys.stderr)
        sys.exit(1)

    if (database_id := os.getenv("DATABASE_ID")) is None:
        print("fatal: environment variable DATABASE_ID is required", file=sys.stderr)
        sys.exit(1)

    s = requests.Session()
    s.headers.update({
        "accept": "application/json",
        "Authorization": f"Bearer {tmdb_read_token}"
    })

    search_url = "https://api.themoviedb.org/3/search/movie"
    params={
        "query": q,
        "include_adult": False,
        "language": "en-US",
        "page": 1,
    }
    if year is not None:
        params["primary_release_year"] = str(year)
    resp = s.get(search_url, params=params).json()
    search_results = [TMDBSearchResult(**entry) for entry in resp["results"]]

    if not search_results:
        print("No search results found", file=sys.stderr)
        sys.exit(1)

    for idx, result in enumerate(search_results):
        print(display(result, idx))
        print()

    which = -1
    while not 0 <= which < len(search_results):
        print("Which entry (enter to select the first one)? ", end="", flush=True, file=sys.stderr)

        text = sys.stdin.readline().strip()
        if text == "":
            text = "0"

        try:
            which = int(text)
        except ValueError:
            continue

    detail_url = f"https://api.themoviedb.org/3/movie/{search_results[which].id}"
    resp = s.get(detail_url, params={"append_to_response": "release_dates"}).json()
    movie = get_movie_detail(resp)

    if dry_run:
        print(movie)
        sys.exit(0)

    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {notion_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    })

    resp = s.post(f"https://api.notion.com/v1/databases/{database_id}/query", data=json.dumps({
        "filter": {
            "property": "TMDB ID",
            "number": {
                "equals": movie.id,
            },
        },
    }))

    results = resp.json()["results"]
    if len(results) == 1:
        print(f"error: movie is already in database (TMDB ID: {movie.id}, {results[0].url})", file=sys.stderr)
        sys.exit(1)
    elif len(results) > 1:
        print(f"error: movie is already in database, with duplicates (TMDB ID: {movie.id})", file=sys.stderr)
        for r in results:
            print(r["url"], file=sys.stderr)
        sys.exit(1)

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
        "Release Date": {
            "date": {
                "start": movie.release_date,
            },
        },
        "Genre": {
            "multi_select": [
                { "name": tag } for tag in movie.genres
            ],
        },
        "Score": {
            "number": movie.vote_average,
        },
        "Vote Count": {
            "number": movie.vote_count,
        },
        "Runtime": {
            "number": movie.runtime,
        },
        "TMDB ID": {
            "number": movie.id,
        },
    }

    if movie.mpaa_rating is not None:
        properties["MPAA Rating"] = {
            "select": {
                "name": movie.mpaa_rating,
            },
        }

    result = s.post("https://api.notion.com/v1/pages", data=json.dumps({
        "parent": {
            "type": "database_id",
            "database_id": database_id,
        },
        "properties": properties,
    }))

    if result.status_code != 200:
        print(result.text, file=sys.stderr)
        sys.exit(1)

    print(result.json()["url"])
