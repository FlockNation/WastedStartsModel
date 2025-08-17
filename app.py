from flask import Flask, request, jsonify, render_template
import pandas as pd
import requests
import time
import numpy as np

app = Flask(__name__)

# Dictionary to map league names to their sportId in the MLB API
SPORT_IDS = {
    'mlb': 1,
    'triple-a': 11,
    'double-a': 12,
    'high-a': 13,
    'low-a': 14
}

def get_game_by_game(year, league):
    print(f"Fetching {year} {league} regular season games...")
    
    sport_id = SPORT_IDS.get(league.lower(), 1) # Default to MLB if league is not found
    
    # Set dates based on year. This is a simplified approach.
    # For a more robust solution, you'd use a lookup table.
    if year == 2025:
        start_date = "2025-03-27"
        end_date = "2025-09-29"
    elif year == 2024:
        start_date = "2024-03-28"
        end_date = "2024-09-29"
    elif year == 2023:
        start_date = "2023-03-30"
        end_date = "2023-10-01"
    else:
        return None

    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId={sport_id}&startDate={start_date}&endDate={end_date}&gameType=R"

    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status() # Raise an HTTPError if the HTTP request returned an unsuccessful status code
        schedule_data = response.json()
        
        all_pitcher_starts = []
        
        for date_info in schedule_data.get('dates', []):
            for game in date_info.get('games', []):
                if game.get('status', {}).get('detailedState') != 'Final':
                    continue
                
                game_pk = game['gamePk']
                boxscore_url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"

                try:
                    box_response = requests.get(boxscore_url, timeout=15)
                    box_data = box_response.json()

                    teams_data = box_data.get('teams', {})
                    decisions_data = box_data.get('decisions', {})
                    
                    winner_id = decisions_data.get('winner', {}).get('id')
                    loser_id = decisions_data.get('loser', {}).get('id')

                    for side in ['home', 'away']:
                        team_data = teams_data.get(side, {})
                        pitchers_list = team_data.get('pitchers', [])
                        players_data = team_data.get('players', {})

                        if not pitchers_list: continue

                        starter_id = pitchers_list[0]
                        player_key = f"ID{starter_id}"

                        if player_key not in players_data: continue

                        player_info = players_data[player_key]
                        pitcher_name = player_info.get('person', {}).get('fullName', 'Unknown')
                        team_name = team_data.get('team', {}).get('abbreviation', '')
                        pitching_stats = player_info.get('stats', {}).get('pitching', {})
                        
                        if not pitching_stats: continue

                        ip = float(pitching_stats.get('inningsPitched', '0.0'))
                        er = int(pitching_stats.get('earnedRuns', 0))
                        
                        decision = ''
                        if starter_id == winner_id:
                            decision = 'W'
                        elif starter_id == loser_id:
                            decision = 'L'
                        else:
                            decision = 'ND'

                        if ip < 4.0: continue

                        quality_start = (ip >= 6.0) and (er <= 3)
                        wasted_start = quality_start and (decision != 'W')

                        all_pitcher_starts.append({
                            'pitcher_name': pitcher_name,
                            'team': team_name,
                            'game_date': game_date,
                            'game_pk': game_pk,
                            'ip': ip,
                            'er': er,
                            'h': int(pitching_stats.get('hits', 0)),
                            'bb': int(pitching_stats.get('baseOnBalls', 0)),
                            'so': int(pitching_stats.get('strikeOuts', 0)),
                            'decision': decision,
                            'quality_start': quality_start,
                            'wasted_start': wasted_start
                        })

                    time.sleep(0.02) # Be a good API citizen

                except requests.exceptions.RequestException as e:
                    print(f"Error fetching boxscore for game {game_pk}: {e}")
                    continue
        
        if not all_pitcher_starts:
            return None
        return pd.DataFrame(all_pitcher_starts)

    except requests.exceptions.RequestException as e:
        print(f"Failed to get game data: {e}")
        return None

def aggregate_pitcher_season_stats(games_df, min_starts):
    season_stats = games_df.groupby(['pitcher_name', 'team']).agg(
        GS=('game_date', 'count'),
        IP=('ip', 'sum'),
        ER=('er', 'sum'),
        H=('h', 'sum'),
        BB=('bb', 'sum'),
        SO=('so', 'sum'),
        Quality_Starts=('quality_start', 'sum'),
        Wasted_Starts=('wasted_start', 'sum')
    ).reset_index()

    win_loss_stats = games_df.groupby(['pitcher_name', 'team']).apply(
        lambda x: pd.Series({
            'W': (x['decision'] == 'W').sum(),
            'L': (x['decision'] == 'L').sum()
        })
    ).reset_index()

    season_stats = season_stats.merge(win_loss_stats, on=['pitcher_name', 'team'], how='left')
    season_stats = season_stats.rename(columns={'pitcher_name': 'Name', 'team': 'Team'})
    season_stats['ERA'] = (season_stats['ER'] / season_stats['IP'] * 9).round(2)
    season_stats['WHIP'] = ((season_stats['H'] + season_stats['BB']) / season_stats['IP']).round(2)
    season_stats = season_stats[season_stats['GS'] >= min_starts]
    return season_stats

def get_wasted_start_examples(games_df, season_stats):
    examples = {}
    for _, pitcher in season_stats.iterrows():
        pitcher_name = pitcher['Name']
        pitcher_games = games_df[(games_df['pitcher_name'] == pitcher_name) & (games_df['wasted_start'] == True)].sort_values('game_date')
        if not pitcher_games.empty:
            first_wasted = pitcher_games.iloc[0]
            decision_text = first_wasted['decision'] if first_wasted['decision'] else 'ND'
            examples[pitcher_name] = f"{first_wasted['game_date']} (IP:{first_wasted['ip']}, ER:{first_wasted['er']}, Dec:{decision_text})"
        else:
            examples[pitcher_name] = "No wasted starts"
    season_stats['Wasted_Start_Example'] = season_stats['Name'].map(examples)
    return season_stats

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/stats', methods=['GET'])
def get_stats():
    year = int(request.args.get('year'))
    league = request.args.get('league')
    min_starts = int(request.args.get('min_starts'))

    games_df = get_game_by_game(year, league)

    if games_df is None or games_df.empty:
        return jsonify({'error': 'No data available for the selected year and league'}), 404

    season_stats = aggregate_pitcher_season_stats(games_df, min_starts)
    final_stats = get_wasted_start_examples(games_df, season_stats)
    final_stats = final_stats.sort_values('Wasted_Starts', ascending=False)

    final_columns = [
        'Name', 'Team', 'GS', 'W', 'L', 'ERA', 'IP', 'SO', 'BB', 'WHIP',
        'Quality_Starts', 'Wasted_Starts', 'Wasted_Start_Example'
    ]
    final_output = final_stats[final_columns]
    
    return jsonify(final_output.to_dict('records'))

if __name__ == '__main__':
    logging.basicConfig(level=logging.ERROR)
    app.run(debug=True)
