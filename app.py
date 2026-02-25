from flask import Flask, render_template, request
from datetime import date
import requests


app = Flask(__name__)
headers = {
        "X-Auth-Token": "1eaac83f40a6492ea0d128cedf2c55ca"
    }

#interface , main page
@app.route("/")
def interface():
    return render_template("interface.html")  


#matches page
@app.route("/match")
def matches():
    

    league = request.args.get("league", "PL")
    status = request.args.get("status")
    selected_date = request.args.get("date")
    club=request.args.get("club")

    

    if selected_date:
        date_from = selected_date
        date_to = selected_date
    else:
        today = date.today().isoformat()
        date_from = today
        date_to = today

    params = {
        "dateFrom": date_from,
        "dateTo": date_to,
    }

    if status:
        params["status"] = status

    

    url = f"https://api.football-data.org/v4/competitions/{league}/matches"
    response = requests.get(url, headers=headers, params=params)
    data = response.json()

    matches = []
    for game in data["matches"]:
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


@app.route("/club/<int:team_id>")
def club(team_id):
    url = f"https://api.football-data.org/v4/teams/{team_id}"
    res = requests.get(url, headers=headers)
    data = res.json()

    club = {
        "id": data["id"],
        "name": data["name"],
        "logo": data["crest"],
        "stadium": data["venue"],
        "founded": data["founded"],
        "country": data["area"]["name"]
    }

    # Last 5 matches
    matches_url = f"https://api.football-data.org/v4/teams/{team_id}/matches"
    params = {
    "limit": 20,
    "status": "FINISHED"
    }

    mres = requests.get(matches_url, headers=headers, params=params)
    mdata = mres.json()

    last_matches = []

    for m in mdata.get("matches", []):
        score = f'{m["score"]["fullTime"]["home"]} - {m["score"]["fullTime"]["away"]}'

        last_matches.append({
            "home": m["homeTeam"]["name"],
            "home_id": m["homeTeam"]["id"],
            "home_logo": m["homeTeam"].get("crest"),

            "away": m["awayTeam"]["name"],
            "away_id": m["awayTeam"]["id"],
            "away_logo": m["awayTeam"].get("crest"),

            "score": score
        })

    last_matches = last_matches[-5:][::-1]

    return render_template("club.html", club=club, last_matches=last_matches)


@app.route("/standings")
def standings():
    league = request.args.get("league", "PL")
    url = f"https://api.football-data.org/v4/competitions/{league}/standings"
    
    response = requests.get(url, headers=headers)
    data = response.json()

    standings_data = []
    
   
    if "standings" in data and len(data["standings"]) > 0:
        for entry in data["standings"][0]["table"]:
            standings_data.append({
                "position": entry["position"],
                "team_name": entry["team"]["name"],
                "team_logo": entry["team"]["crest"],
                "team_id": entry["team"]["id"],
                "played": entry["playedGames"],
                "wins": entry["won"],
                "draws": entry["draw"],
                "losses": entry["lost"],
                "points": entry["points"]
            })
            
    return render_template("standings.html", standings=standings_data, selected_league=league)

    

if __name__ == "__main__":
    app.run()
