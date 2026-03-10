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
                "points": entry["points"],
                
                
            })
    
    
    
    return render_template(
        "standings.html",
        standings=standings_data,
        selected_league=league,
        club={}
    )








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



COMPETITION_MAP = {
    # football-data code → TheSportsDB league name (for search)
    "PL":   "English Premier League",
    "PD":   "Spanish La Liga",
    "SA":   "Italian Serie A",
    "BL1":  "German Bundesliga",
    "FL1":  "French Ligue 1",
    "CL":   "UEFA Champions League",
    "EL":   "UEFA Europa League",
    "EC":   "European Championship",
    "WC":   "FIFA World Cup",
    "CLI":  "CONMEBOL Libertadores",
}

PRIORITY_CODES = ["PL", "PD", "SA", "BL1", "FL1", "CL", "EL", "EC", "WC", "CLI"]

ROUND_ORDER = [
    "Last 16", "Round of 16", "Quarter-Final", "Quarter-Finals",
    "Semi-Final", "Semi-Finals", "Final"
]


@app.route("/competitions")
def competitions():
    api_key = os.environ.get("FOOTBALL_API_KEY")
    sportsdb_key = os.environ.get("SPORTSDB_KEY", "3")   # free key = "3"
    if not api_key:
        return "API key not set", 500

    fd_headers = {"X-Auth-Token": api_key}
    selected_code = request.args.get("code", "CL")

    
    comp_list_res = requests.get(
        "https://api.football-data.org/v4/competitions",
        headers=fd_headers, timeout=10
    )
    competitions_raw = comp_list_res.json().get("competitions", []) if comp_list_res.status_code == 200 else []

   
    seen_codes = set()
    competitions_display = []

    # Add priority ones first (in order)
    code_to_raw = {c.get("code"): c for c in competitions_raw}
    for code in PRIORITY_CODES:
        raw = code_to_raw.get(code)
        if raw:
            competitions_display.append({
                "code": raw.get("code"),
                "name": raw.get("name"),
                "area": raw.get("area", {}).get("name", ""),
                "emblem": raw.get("emblem"),
                "type": raw.get("type", "LEAGUE"),
            })
            seen_codes.add(code)

    
    for raw in competitions_raw:
        c = raw.get("code")
        if c and c not in seen_codes and raw.get("plan") == "TIER_ONE":
            competitions_display.append({
                "code": c,
                "name": raw.get("name"),
                "area": raw.get("area", {}).get("name", ""),
                "emblem": raw.get("emblem"),
                "type": raw.get("type", "LEAGUE"),
            })

    # ── 2. Fetch selected competition detail ──────────────────────────────────
    comp_res = requests.get(
        f"https://api.football-data.org/v4/competitions/{selected_code}",
        headers=fd_headers, timeout=10
    )
    if comp_res.status_code != 200:
        return render_template("competitions.html",
                               competitions=competitions_display,
                               selected_code=selected_code,
                               comp=None, **_empty_ctx())

    comp_data = comp_res.json()
    comp = {
        "name": comp_data.get("name"),
        "area": comp_data.get("area", {}).get("name"),
        "emblem": comp_data.get("emblem"),
        "type": comp_data.get("type"),
        "currentSeason": comp_data.get("currentSeason"),
    }
    is_cup = comp_data.get("type") == "CUP"

    # ── 3. Fetch matches (last 20 finished + next 20 upcoming) ────────────────
    from datetime import date, timedelta
    today = date.today()
    date_from = (today - timedelta(days=60)).isoformat()
    date_to   = (today + timedelta(days=60)).isoformat()

    matches_res = requests.get(
        f"https://api.football-data.org/v4/competitions/{selected_code}/matches",
        headers=fd_headers,
        params={"dateFrom": date_from, "dateTo": date_to},
        timeout=10
    )
    all_matches_raw = []
    if matches_res.status_code == 200:
        all_matches_raw = matches_res.json().get("matches", [])

    # Also grab full season matches for bracket/stats
    all_season_res = requests.get(
        f"https://api.football-data.org/v4/competitions/{selected_code}/matches",
        headers=fd_headers,
        params={"status": "FINISHED"},
        timeout=10
    )
    finished_season = []
    if all_season_res.status_code == 200:
        finished_season = all_season_res.json().get("matches", [])

    def build_match(m):
        ft = m.get("score", {}).get("fullTime", {})
        score = "vs"
        if ft.get("home") is not None:
            score = f"{ft['home']} – {ft['away']}"
        utc = m.get("utcDate", "")
        return {
            "home": m.get("homeTeam", {}).get("name", "TBD"),
            "home_id": m.get("homeTeam", {}).get("id"),
            "home_logo": m.get("homeTeam", {}).get("crest", ""),
            "away": m.get("awayTeam", {}).get("name", "TBD"),
            "away_id": m.get("awayTeam", {}).get("id"),
            "away_logo": m.get("awayTeam", {}).get("crest", ""),
            "score": score,
            "date": utc[:10] if utc else "",
            "time": utc[11:16] if len(utc) > 10 else "",
            "status": m.get("status"),
            "stage": m.get("stage", ""),
            "utcDate": utc,
        }

    upcoming_matches = [build_match(m) for m in all_matches_raw
                        if m.get("status") in ("SCHEDULED", "TIMED")]
    upcoming_matches.sort(key=lambda x: x["utcDate"])

    recent_matches = [build_match(m) for m in all_matches_raw
                      if m.get("status") == "FINISHED"]
    recent_matches.sort(key=lambda x: x["utcDate"], reverse=True)

    total_matches = len(finished_season)

    
    standings = []
    if not is_cup:
        st_res = requests.get(
            f"https://api.football-data.org/v4/competitions/{selected_code}/standings",
            headers=fd_headers, timeout=10
        )
        if st_res.status_code == 200:
            st_data = st_res.json().get("standings", [])
            if st_data:
                for entry in st_data[0].get("table", []):
                    standings.append({
                        "position": entry.get("position"),
                        "team_name": entry.get("team", {}).get("name"),
                        "team_id": entry.get("team", {}).get("id"),
                        "logo": entry.get("team", {}).get("crest", ""),
                        "played": entry.get("playedGames"),
                        "wins": entry.get("won"),
                        "draws": entry.get("draw"),
                        "losses": entry.get("lost"),
                        "points": entry.get("points"),
                        "goal_diff": entry.get("goalDifference"),
                    })

    # ── 5. Top scorers ────────────────────────────────────────────────────────
    scorers_res = requests.get(
        f"https://api.football-data.org/v4/competitions/{selected_code}/scorers",
        headers=fd_headers,
        params={"limit": 20},
        timeout=10
    )
    top_scorers = []
    top_assisters = []
    top_scorer = None

    if scorers_res.status_code == 200:
        raw_scorers = scorers_res.json().get("scorers", [])
        for s in raw_scorers:
            entry = {
                "player_name": s.get("player", {}).get("name"),
                "team_name": s.get("team", {}).get("name"),
                "goals": s.get("goals", 0),
                "assists": s.get("assists"),
            }
            top_scorers.append(entry)

        top_scorers.sort(key=lambda x: x["goals"] or 0, reverse=True)
        top_assisters = sorted(
            [s for s in top_scorers if s["assists"]],
            key=lambda x: x["assists"] or 0, reverse=True
        )
        if top_scorers:
            top_scorer = top_scorers[0]

   
    bracket_rounds = {}
    if is_cup:
        
        stage_map = {}
        for m in [build_match(x) for x in finished_season] + [build_match(x) for x in all_matches_raw]:
            stage = m.get("stage", "Unknown").replace("_", " ").title()
            stage_map.setdefault(stage, [])
            # Avoid duplicates
            key = f"{m['home']}__{m['away']}__{m['date']}"
            if not any(f"{x['home']}__{x['away']}__{x['date']}" == key for x in stage_map[stage]):
                stage_map[stage].append(m)

        
        def round_sort_key(name):
            for i, r in enumerate(ROUND_ORDER):
                if r.lower() in name.lower():
                    return i
            return 99

        for stage_name in sorted(stage_map.keys(), key=round_sort_key):
            if stage_name.lower() in ("regular season", "group stage"):
                continue  # skip non-knockout
            matches_in_stage = stage_map[stage_name]
            # Pair legs: match home/away combos
            pairs = {}
            for m in matches_in_stage:
                pair_key = tuple(sorted([m["home"] or "", m["away"] or ""]))
                pairs.setdefault(pair_key, [])
                pairs[pair_key].append(m)

            fixtures = []
            for pair_key, legs in pairs.items():
                legs_sorted = sorted(legs, key=lambda x: x["date"])
                f = {
                    "home": legs_sorted[0]["home"],
                    "home_id": legs_sorted[0]["home_id"],
                    "home_logo": legs_sorted[0]["home_logo"],
                    "away": legs_sorted[0]["away"],
                    "away_id": legs_sorted[0]["away_id"],
                    "away_logo": legs_sorted[0]["away_logo"],
                    "score1": legs_sorted[0]["score"],
                    "date1": legs_sorted[0]["date"],
                    "leg2": None,
                    "score2": None,
                    "date2": None,
                    "agg": None,
                }
                if len(legs_sorted) > 1:
                    f["leg2"] = True
                    f["score2"] = legs_sorted[1]["score"]
                    f["date2"] = legs_sorted[1]["date"]
                fixtures.append(f)

            if fixtures:
                bracket_rounds[stage_name] = fixtures

    
    sportsdb_info = None
    sdb_name = COMPETITION_MAP.get(selected_code)
    if sdb_name:
        try:
            sdb_res = requests.get(
                f"https://www.thesportsdb.com/api/v1/json/{sportsdb_key}/search_all_leagues.php",
                params={"c": comp.get("area", ""), "s": "Soccer"},
                timeout=8
            )
            if sdb_res.status_code == 200:
                leagues_sdb = sdb_res.json().get("countrys") or []
                for lg in leagues_sdb:
                    if lg.get("strLeague", "").lower() in sdb_name.lower() or \
                       sdb_name.lower() in lg.get("strLeague", "").lower():
                        sportsdb_info = lg
                        break
        except Exception:
            pass

    
    teams_res = requests.get(
        f"https://api.football-data.org/v4/competitions/{selected_code}/teams",
        headers=fd_headers, timeout=10
    )
    total_teams = 0
    if teams_res.status_code == 200:
        total_teams = len(teams_res.json().get("teams", []))

    return render_template(
        "competitions.html",
        competitions=competitions_display,
        selected_code=selected_code,
        comp=comp,
        is_cup=is_cup,
        upcoming_matches=upcoming_matches,
        recent_matches=recent_matches,
        standings=standings,
        top_scorers=top_scorers,
        top_assisters=top_assisters,
        top_scorer=top_scorer,
        bracket_rounds=bracket_rounds,
        total_matches=total_matches,
        total_teams=total_teams,
        sportsdb_info=sportsdb_info,
    )


def _empty_ctx():
    return dict(
        is_cup=False,
        upcoming_matches=[],
        recent_matches=[],
        standings=[],
        top_scorers=[],
        top_assisters=[],
        top_scorer=None,
        bracket_rounds={},
        total_matches=0,
        total_teams=0,
        sportsdb_info=None,
    )





if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)