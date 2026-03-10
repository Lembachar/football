from itertools import groupby

from flask import Flask, render_template, request
from datetime import date

import requests
import os
from dotenv import load_dotenv
load_dotenv()


app = Flask(__name__)


#interface , main page
@app.route("/")
def interface():
    return render_template("interface.html")  


#matches page


@app.route("/match")
def matches():
    api_key = os.environ.get("FOOTBALL_API_KEY")
    if not api_key:
        return "API key not set", 500

    headers = {"X-Auth-Token": api_key}

    # Major competitions (free-plan safe)
    LEAGUES = ["PL", "PD", "SA", "BL1", "FL1", "CL"]

    selected_date = request.args.get("date")
    if selected_date:
        date_from = selected_date
        date_to = selected_date
    else:
        today = date.today().isoformat()
        date_from = today
        date_to = today

    all_matches = []

    for league in LEAGUES:
        url = f"https://api.football-data.org/v4/competitions/{league}/matches"
        params = {
            "dateFrom": date_from,
            "dateTo": date_to
        }

        res = requests.get(url, headers=headers, params=params, timeout=10)
        if res.status_code != 200:
            continue

        for game in res.json().get("matches", []):
            ft = game.get("score", {}).get("fullTime")
            score = "vs"
            if ft and ft.get("home") is not None:
                score = f"{ft['home']} - {ft['away']}"

            all_matches.append({
                "id": game.get("id"),
                "competition": game.get("competition", {}).get("name"),
                "competition_code": league,
                "utcDate": game.get("utcDate"),
                "home": game.get("homeTeam", {}).get("name"),
                "home_id": game.get("homeTeam", {}).get("id"),
                "home_logo": game.get("homeTeam", {}).get("crest"),
                "away": game.get("awayTeam", {}).get("name"),
                "away_id": game.get("awayTeam", {}).get("id"),
                "away_logo": game.get("awayTeam", {}).get("crest"),
                "score": score
            })

    # Sort by kickoff time
    all_matches.sort(key=lambda x: x.get("utcDate", ""))
    from itertools import groupby
    grouped = {k: list(v) for k, v in groupby(all_matches, key=lambda x: x["competition"])}

    NAME_MAP = {
        "Primera Division": "La Liga",
    }
    grouped = {NAME_MAP.get(k, k): v for k, v in grouped.items()}
    return render_template(
        "match.html",
        grouped_matches=grouped,
        selected_date=date_from
    )



@app.route("/match/<int:match_id>")
def match_detail(match_id):
    api_key = os.environ.get("FOOTBALL_API_KEY")
    if not api_key:
        return "API key not set", 500
    headers = {"X-Auth-Token": api_key}

    res = requests.get(f"https://api.football-data.org/v4/matches/{match_id}", headers=headers)
    if res.status_code != 200:
        return "Match not found", 404

    data = res.json()

    match = {
        "home": data.get("homeTeam", {}).get("name"),
        "home_logo": data.get("homeTeam", {}).get("crest"),
        "away": data.get("awayTeam", {}).get("name"),
        "away_logo": data.get("awayTeam", {}).get("crest"),
        "score": data.get("score", {}).get("fullTime", {}),
        "status": data.get("status"),
        "date": data.get("utcDate", "").split("T")[0],
        "competition": data.get("competition", {}).get("name"),
        "goals": data.get("goals", []),
        "bookings": data.get("bookings", []),
        "substitutions": data.get("substitutions", []),
        "lineups": data.get("lineups", []),
    }

    return render_template("data.html", match=match)




#club -----------------------------------------------------------------
@app.route("/club/<int:team_id>")
def club(team_id):
    api_key = os.environ.get("FOOTBALL_API_KEY")
    if not api_key:
        raise RuntimeError("FOOTBALL_API_KEY not set")
    headers = {"X-Auth-Token": api_key}

    # --- defaults (guaranteed) ---
    club = {}
    all_matches = []
    last_matches = []
    upcoming = None
    standing = None

    # --- club info ---
    res = requests.get(f"https://api.football-data.org/v4/teams/{team_id}", headers=headers)
    if res.status_code != 200:
        return "Team not found", 404

    data = res.json()
    club = {
        "id": data.get("id"),
        "name": data.get("name"),
        "logo": data.get("crest"),
        "stadium": data.get("venue"),
        "founded": data.get("founded"),
        "country": data.get("area", {}).get("name"),
        "running_competitions": data.get("runningCompetitions", []),
         "squad": data.get("squad", [])
    }

    # --- matches ---
    mres = requests.get(f"https://api.football-data.org/v4/teams/{team_id}/matches", headers=headers)
    if mres.status_code == 200:
        try:
            all_matches = mres.json().get("matches", [])
        except ValueError:
            all_matches = []

    finished = [m for m in all_matches if isinstance(m, dict) and m.get("status") == "FINISHED"]
    for m in finished[-5:][::-1]:
        last_matches.append({
            "home": m.get("homeTeam", {}).get("name"),
            "home_id": m.get("homeTeam", {}).get("id"),
            "home_logo": m.get("homeTeam", {}).get("crest"),
            "away": m.get("awayTeam", {}).get("name"),
            "away_id": m.get("awayTeam", {}).get("id"),
            "away_logo": m.get("awayTeam", {}).get("crest"),
            "score": f'{m.get("score", {}).get("fullTime", {}).get("home", "?")} - {m.get("score", {}).get("fullTime", {}).get("away", "?")}'
        })

    scheduled = [m for m in all_matches if isinstance(m, dict) and m.get("status") in ["SCHEDULED", "TIMED"]]
    if scheduled:
        m = scheduled[0]
        upcoming = {
            "home": m.get("homeTeam", {}).get("name"),
            "home_logo": m.get("homeTeam", {}).get("crest"),
            "away": m.get("awayTeam", {}).get("name"),
            "away_logo": m.get("awayTeam", {}).get("crest"),
            "date": m.get("utcDate", "").split("T")[0]
        }

    # --- standings ---
    if club["running_competitions"]:
        code = club["running_competitions"][0].get("code")
        if code:
            sres = requests.get(f"https://api.football-data.org/v4/competitions/{code}/standings", headers=headers)
            if sres.status_code == 200:
                for table in sres.json().get("standings", []):
                    for row in table.get("table", []):
                        if row.get("team", {}).get("id") == team_id:
                            standing = row
                            break

    return render_template(
        "club.html",
        club=club,
        last_matches=last_matches,
        upcoming=upcoming,
        standing=standing
    )
#standings ------------------------------------------------------------
@app.route("/standings")
def standings():
    league = request.args.get("league", "PL")
    url = f"https://api.football-data.org/v4/competitions/{league}/standings"
    api_key = os.environ.get("FOOTBALL_API_KEY")
    if not api_key:
        raise RuntimeError("FOOTBALL_API_KEY not set")
    headers = {"X-Auth-Token": api_key}

    response = requests.get(url, headers=headers)
    data = response.json()

    standings_data = []

    if "standings" in data and len(data["standings"]) > 0:
        for entry in data["standings"][0]["table"]:

            

            standings_data.append({
                "position": entry["position"],
                "team_name": entry["team"]["name"],
                "team_id": entry["team"]["id"],
                "club": {
                    "logo": entry["team"]["crest"]
                },
                "played": entry["playedGames"],
                "wins": entry["won"],
                "draws": entry["draw"],
                "losses": entry["lost"],
                "points": entry["points"]
                
            })

    return render_template(
        "standings.html",
        standings=standings_data,
        selected_league=league,
        club={}
    )

@app.route("/leagues")
def leagues():
    api_key = os.environ.get("FOOTBALL_API_KEY")
    if not api_key:
        raise RuntimeError("FOOTBALL_API_KEY not set")
    headers = {"X-Auth-Token": api_key}

    url = "https://api.football-data.org/v4/competitions"
    response = requests.get(url, headers=headers)
    data = response.json()

    leagues = []
    for comp in data.get("competitions", []):
        if comp.get("plan") == "TIER_ONE":
            leagues.append({
                "id": comp.get("id"),
                "name": comp.get("name"),
                "code": comp.get("code"),
                "area": comp.get("area", {}).get("name")
            })

    return render_template("leagues.html", leagues=leagues)






@app.route("/players")
def players():
    query = request.args.get("p", "")
    player_id = request.args.get("id", "")
    players = []
    selected_player = None
    multiple = False

    if query:
        sportsdb_key = os.environ.get("SPORTSDB_API_KEY")
        try:
            res = requests.get(f"https://www.thesportsdb.com/api/v1/json/{sportsdb_key}/searchplayers.php?p={query}")
            results = res.json().get("player", []) or []
            if player_id:
               if player_id:
                    detail = requests.get(f"https://www.thesportsdb.com/api/v1/json/{sportsdb_key}/lookupplayer.php?id={player_id}")
                    players_data = detail.json().get("players", [])
                    selected_player = players_data[0] if players_data else None
            elif len(results) == 1:
                selected_player = results[0]
            elif len(results) > 1:
                players = results
                multiple = True
        except:
            pass

    return render_template("players.html", players=players, selected_player=selected_player, multiple=multiple, query=query, player_id=player_id)










if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
