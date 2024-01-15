import click
import json
import os
from pprint import pprint
import requests
import sys
import textwrap

from typing import List, Optional

from .models import TMDBSearchResult, TMDBMovie


class TMDBClient(object):
    def __init__(self, tmdb_read_token: str):
        self.session = requests.Session()
        self.session.headers.update({
            "accept": "application/json",
            "Authorization": f"Bearer {tmdb_read_token}"
        })

    def movie_search(self, *, query: str, year: Optional[int], exact_match: bool) -> List[TMDBSearchResult]:
        url = "https://api.themoviedb.org/3/search/movie"
        coll_url = "https://api.themoviedb.org/3/search/collection"

        params = {
            "query": query,
            "include_adult": False,
            "language": "en-US",
            "page": 1,
        }
        if year is not None:
            params["year"] = str(year)

        search_resp = self.session.get(url, params=params).json()
        coll_resp = self.session.get(coll_url, params=params).json()

        collections = {x["id"] for x in coll_resp["results"]}
        search_results = [TMDBSearchResult(**entry) for entry in search_resp["results"] if entry["id"] not in collections]

        if exact_match:
            search_results = [s for s in search_results if s.title.lower() == query.lower()]

        return search_results

    def movie_detail(self, *, tmdb_id: int) -> TMDBMovie:
        url = f"https://api.themoviedb.org/3/movie/{tmdb_id}"

        detail = self.session.get(url, params={"append_to_response": "release_dates"}).json()

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


class NotionClient(object):
    def __init__(self, *, notion_key: str, database_id: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {notion_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        })

        self.database_id = database_id

    def find_by_id(self, *, tmdb_id: int):
        url = f"https://api.notion.com/v1/databases/{self.database_id}/query"
        body = {
            "filter": {
                "property": "TMDB ID",
                "number": {
                    "equals": tmdb_id,
                },
            },
        }

        return self.session.post(url, data=json.dumps(body)).json()["results"]

    def create_movie_row(self, *, movie: TMDBMovie):
        url = "https://api.notion.com/v1/pages"

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

        body = {
            "parent": {
                "type": "database_id",
                "database_id": self.database_id,
            },
            "properties": properties,
        }

        resp = self.session.post(url, data=json.dumps(body))
        resp.raise_for_status()

        return resp.json()


def display(s: TMDBSearchResult, idx: int) -> str:
    release_year = s.release_date.split("-")[0]
    spacer = " " * 8
    wrapped_overview = textwrap.fill(s.overview, initial_indent=spacer, subsequent_indent=spacer)

    return f"""({idx}) {s.title} ({release_year})
{wrapped_overview}"""


@click.command()
@click.argument("query", nargs=-1, required=True)
@click.option("-y", "--year", required=False, type=int)
@click.option("--dry-run", is_flag=True)
@click.option("--exact-match", is_flag=True)
@click.option("--interactive/--non-interactive", default=True)
def movie(query: List[str], year: Optional[int], dry_run: bool, exact_match: bool, interactive: bool) -> None:
    # Read in required configuration values.
    if (tmdb_read_token := os.getenv("TMDB_READ_TOKEN")) is None:
        print("fatal: environment variable TMDB_READ_TOKEN is required", file=sys.stderr)
        sys.exit(1)

    if (notion_key := os.getenv("NOTION_KEY")) is None:
        print("fatal: environment variable NOTION_KEY is required", file=sys.stderr)
        sys.exit(1)

    if (database_id := os.getenv("DATABASE_ID")) is None:
        print("fatal: environment variable DATABASE_ID is required", file=sys.stderr)
        sys.exit(1)

    # Instantiate a TMDB client connection.
    tmdb = TMDBClient(tmdb_read_token)

    # Perform a TMDB search using the input search terms.
    q = " ".join(query)
    search_results = tmdb.movie_search(query=q, year=year, exact_match=exact_match)

    # Analyze the results.
    #
    # An exact match in non-interactive mode is not actionable, so bail with an
    # error.
    if exact_match and not interactive and len(search_results) > 1:
        print("Multiple exact matches found in non-interactive mode", file=sys.stderr)
        sys.exit(1)

    # If there aren't any search results at all, bail with an error.
    if not search_results:
        print(f"No {'exact ' if exact_match else ''}search results found", file=sys.stderr)
        sys.exit(1)

    # Print out the search results, with numeric index.
    for idx, result in enumerate(search_results):
        print(display(result, idx), file=sys.stderr)
        print(file=sys.stderr)

    # Get the user to select a result (or choose the first one in
    # non-interactive mode).
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

    # Get the detailed results for the selected movie.
    movie = tmdb.movie_detail(tmdb_id = search_results[which].id)

    # In dry run mode, print out the result and exit.
    if dry_run:
        print(movie)
        sys.exit(0)

    # Instantiate a Notion client.
    notion_client = NotionClient(notion_key=notion_key, database_id=database_id)

    # Look for the same movie already in the database.
    if (dupes := notion_client.find_by_id(tmdb_id=movie.id)):
        print(f"error: movie is already in database (TMDB ID: {movie.id})", file=sys.stderr)
        for dupe in dupes:
            print(f"    {dupe['url']}", file=sys.stderr)
        sys.exit(1)

    # Create a row for the movie in the Notion database and output the URL for
    # it.
    new_row = notion_client.create_movie_row(movie=movie)
    print(new_row["url"])
