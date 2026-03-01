from flask import Flask, render_template, request
from datetime import date

import requests
import os



app = Flask(__name__)


#interface , main page
@app.route("/")
def interface():
    return render_template("interface.html")  


#matches page
# --- DELETE THE GLOBAL HEADERS VARIABLE AT THE TOP ---

@app.route("/match")
def matches():
    # Fetch key inside the function to ensure Railway has loaded it
    api_key = os.environ.get("FOOTBALL_API_KEY")
    if not api_key:
        raise RuntimeError("FOOTBALL_API_KEY not set")
    headers = {"X-Auth-Token": api_key}
    

    league = request.args.get("league", "PL")
    status = request.args.get("status")
    selected_date = request.args.get("date")

    if selected_date:
        date_from = selected_date
        date_to = selected_date
    else:
        today = date.today().isoformat()
        date_from = today
        date_to = today

    params = {"dateFrom": date_from, "dateTo": date_to}
    if status:
        params["status"] = status

    url = f"https://api.football-data.org/v4/competitions/{league}/matches"
    
    # Use current_headers here
    response = requests.get(url, headers=headers, params=params, timeout=10)
    data = response.json()

    # DEBUG: This will show the actual API error in Railway "Application Logs"
    if response.status_code != 200:
        print(f"MATCH API ERROR: {data}")

    matches = []
    for game in data.get("matches", []):
        score = "vs"
        if game["score"]["fullTime"]["home"] is not None:
            score = f'{game["score"]["fullTime"]["home"]} - {game["score"]["fullTime"]["away"]}'

        matches.append({
             "home": game["homeTeam"]["name"],
             "home_id": game["homeTeam"]["id"],
             "home_logo": game["homeTeam"].get("crest"),
             "away": game["awayTeam"]["name"],
             "away_id": game["awayTeam"]["id"],
             "away_logo": game["awayTeam"].get("crest"),
             "score": score
        })
        
    return render_template("match.html", matches=matches)

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
        "running_competitions": data.get("runningCompetitions", [])
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

    

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
