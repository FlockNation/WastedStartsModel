import streamlit as st
import pandas as pd
import requests
import time

SPORT_IDS = {
    'mlb': 1,
    'triple-a': 11,
    'double-a': 12,
    'high-a': 13,
    'low-a': 14
}

@st.cache_data
def get_game_by_game(year, league):
    sport_id = SPORT_IDS.get(league.lower(), 1)
    if year == 2025:
        start_date, end_date = "2025-03-27", "2025-09-29"
    elif year == 2024:
        start_date, end_date = "2024-03-28", "2024-09-29"
    elif year == 2023:
        start_date, end_date = "2023-03-30", "2023-10-01"
    else:
        return None

    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId={sport_id}&startDate={start_date}&endDate={end_date}&gameType=R"
    
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        schedule_data = response.json()
        all_pitcher_starts = []

        for date_info in schedule_data.get('dates', []):
            game_date = date_info.get('date')
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
                        if not pitchers_list:
                            continue
                        starter_id = pitchers_list[0]
                        player_key = f"ID{starter_id}"
                        if player_key not in players_data:
                            continue
                        player_info = players_data[player_key]
                        pitcher_name = player_info.get('person', {}).get('fullName', 'Unknown')
                        team_name = team_data.get('team', {}).get('abbreviation', '')
                        pitching_stats = player_info.get('stats', {}).get('pitching', {})
                        if not pitching_stats:
                            continue
                        ip = float(pitching_stats.get('inningsPitched', '0.0'))
                        er = int(pitching_stats.get('earnedRuns', 0))
                        decision = ''
                        if starter_id == winner_id:
                            decision = 'W'
                        elif starter_id == loser_id:
                            decision = 'L'
                        else:
                            decision = 'ND'
                        if ip < 4.0:
                            continue
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
                    time.sleep(0.02)
                except:
                    continue

        return pd.DataFrame(all_pitcher_starts) if all_pitcher_starts else None
    except:
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
    return season_stats.sort_values('Wasted_Starts', ascending=False)

st.set_page_config(page_title="MLB Pitcher Stats", layout="wide")
st.title("MLB Pitcher Statistics")

col1, col2, col3 = st.columns(3)
with col1:
    year = st.slider("Year", 2020, 2024, 2024)
with col2:
    min_starts = st.slider("Minimum Starts", 5, 10, 5)
with col3:
    league = st.selectbox("League", ['mlb', 'triple-a', 'double-a', 'high-a', 'low-a'])

if st.button("Get Stats", type="primary"):
    with st.spinner("Loading pitcher statistics..."):
        games_df = get_game_by_game(year, league)
        
        if games_df is None or games_df.empty:
            st.error("No data available for the selected year and league")
        else:
            season_stats = aggregate_pitcher_season_stats(games_df, min_starts)
            
            if season_stats.empty:
                st.warning(f"No pitchers found with at least {min_starts} starts")
            else:
                st.success(f"Found {len(season_stats)} pitchers")
                
                final_columns = ['Name', 'Team', 'GS', 'W', 'L', 'ERA', 'IP', 'SO', 'BB', 'WHIP', 'Quality_Starts', 'Wasted_Starts']
                st.dataframe(season_stats[final_columns], use_container_width=True)
