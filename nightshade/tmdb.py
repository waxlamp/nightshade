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


def rating_comparator(x):
    rating_values = {
        "NR": 0,
        "G": 1,
        "PG": 2,
        "PG-13": 3,
        "R": 4,
        "NC-17": 5,
    }

    return rating_values[x]

def get_movie_detail(detail) -> TMDBMovie:
    release_dates = detail["release_dates"]["results"]
    us_release_dates = [x for x in release_dates if x["iso_3166_1"] == "US"]
    flattened_us_release_dates = sum((x["release_dates"] for x in us_release_dates), [])
    all_certs = [x["certification"] or "NR" for x in flattened_us_release_dates]
    mpaa_rating = max(all_certs, key=rating_comparator) if all_certs else "NR"

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
@click.option("--exact-match", is_flag=True)
@click.option("--interactive/--non-interactive", default=True)
def tmdb(query: List[str], year: Optional[int], dry_run: bool, exact_match: bool, interactive: bool) -> None:
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
    coll_search_url = "https://api.themoviedb.org/3/search/collection"
    params={
        "query": q,
        "include_adult": False,
        "language": "en-US",
        "page": 1,
    }
    if year is not None:
        params["primary_release_year"] = str(year)
    resp = s.get(search_url, params=params).json()
    coll_resp = s.get(coll_search_url, params=params).json()
    collections = {x["id"] for x in coll_resp["results"]}
    search_results = [TMDBSearchResult(**entry) for entry in resp["results"] if entry["id"] not in collections]

    for idx, result in enumerate(search_results):
        print(display(result, idx))
        print()

    if exact_match:
        search_results = [s for s in search_results if s.title.lower() == q.lower()]
        if not interactive and len(search_results) > 1:
            print("Multiple exact matches found in non-interactive mode", file=sys.stderr)
            sys.exit(1)

    if not search_results:
        print(f"No {'exact ' if exact_match else ''}search results found", file=sys.stderr)
        sys.exit(1)

    which = 0
    if interactive:
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
        print(f"error: movie is already in database (TMDB ID: {movie.id}, {results[0]['url']})", file=sys.stderr)
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
