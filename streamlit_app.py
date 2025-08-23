import streamlit as st
import pandas as pd
import requests
import time
import plotly.express as px
import plotly.graph_objects as go

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
    season_stats['QS%'] = (season_stats['Quality_Starts'] / season_stats['GS'] * 100).round(1)
    season_stats['Wasted%'] = (season_stats['Wasted_Starts'] / season_stats['Quality_Starts'] * 100).fillna(0).round(1)
    season_stats = season_stats[season_stats['GS'] >= min_starts]
    return season_stats

st.set_page_config(page_title="MLB Pitcher Analytics", layout="wide")

st.title("MLB Pitcher Analytics Dashboard")
st.markdown("*Advanced pitcher statistics and quality start analysis*")

# Sidebar controls
st.sidebar.header("Controls")
year = st.sidebar.selectbox("Season", [2025, 2024, 2023], index=1)
league = st.sidebar.selectbox("League", ['mlb', 'triple-a', 'double-a', 'high-a', 'low-a'])
min_starts = st.sidebar.slider("Minimum Starts", 1, 15, 5)

# Analysis type
analysis_type = st.sidebar.radio("Analysis Type", 
    ["Season Stats", "Leaderboards", "Visualizations", "Player Search"])

if st.sidebar.button("Load Data", type="primary"):
    with st.spinner(f"Loading {year} {league.upper()} data..."):
        games_df = get_game_by_game(year, league)
        
        if games_df is None or games_df.empty:
            st.error("No data available for the selected year and league")
            st.stop()
        
        season_stats = aggregate_pitcher_season_stats(games_df, min_starts)
        
        if season_stats.empty:
            st.warning(f"No pitchers found with at least {min_starts} starts")
            st.stop()
        
        st.session_state.games_df = games_df
        st.session_state.season_stats = season_stats
        st.success(f"Loaded {len(season_stats)} pitchers with {len(games_df)} total starts")

# Main content
if 'season_stats' not in st.session_state:
    st.info("Select your filters and click 'Load Data' to begin analysis")
    st.stop()

games_df = st.session_state.games_df
season_stats = st.session_state.season_stats

if analysis_type == "Season Stats":
    st.header("Season Statistics")
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Pitchers", len(season_stats))
    with col2:
        st.metric("Total Starts", len(games_df))
    with col3:
        st.metric("Quality Starts", games_df['quality_start'].sum())
    with col4:
        st.metric("Wasted Starts", games_df['wasted_start'].sum())
    
    # Full stats table
    st.subheader("Complete Statistics")
    display_cols = ['Name', 'Team', 'GS', 'W', 'L', 'ERA', 'WHIP', 'IP', 'SO', 'Quality_Starts', 'QS%', 'Wasted_Starts', 'Wasted%']
    st.dataframe(season_stats[display_cols].sort_values('Wasted_Starts', ascending=False), 
                use_container_width=True, height=400)

elif analysis_type == "Leaderboards":
    st.header("Leaderboards")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Most Wasted", "Best QS%", "Lowest ERA", "Most Strikeouts"])
    
    with tab1:
        st.subheader("Most Wasted Quality Starts")
        top_wasted = season_stats.nlargest(10, 'Wasted_Starts')[['Name', 'Team', 'Quality_Starts', 'Wasted_Starts', 'Wasted%']]
        st.dataframe(top_wasted, use_container_width=True)
    
    with tab2:
        st.subheader("Highest Quality Start Percentage")
        top_qs = season_stats.nlargest(10, 'QS%')[['Name', 'Team', 'GS', 'Quality_Starts', 'QS%']]
        st.dataframe(top_qs, use_container_width=True)
    
    with tab3:
        st.subheader("Lowest ERA (min 10 GS)")
        low_era = season_stats[season_stats['GS'] >= 10].nsmallest(10, 'ERA')[['Name', 'Team', 'GS', 'ERA', 'WHIP']]
        st.dataframe(low_era, use_container_width=True)
    
    with tab4:
        st.subheader("Most Strikeouts")
        top_so = season_stats.nlargest(10, 'SO')[['Name', 'Team', 'GS', 'SO', 'IP']]
        st.dataframe(top_so, use_container_width=True)

elif analysis_type == "Visualizations":
    st.header("Data Visualizations")
    
    tab1, tab2, tab3 = st.tabs(["Scatter Plots", "Distributions", "Team Analysis"])
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            fig1 = px.scatter(season_stats, x='ERA', y='Wasted_Starts', 
                            hover_data=['Name', 'Team'], title='ERA vs Wasted Starts',
                            color='QS%', size='GS')
            st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            fig2 = px.scatter(season_stats, x='Quality_Starts', y='Wasted_Starts',
                            hover_data=['Name', 'Team'], title='Quality Starts vs Wasted Starts',
                            color='ERA', size='GS')
            st.plotly_chart(fig2, use_container_width=True)
    
    with tab2:
        col1, col2 = st.columns(2)
        
        with col1:
            fig3 = px.histogram(season_stats, x='QS%', nbins=20, title='Quality Start % Distribution')
            st.plotly_chart(fig3, use_container_width=True)
        
        with col2:
            fig4 = px.histogram(season_stats, x='Wasted%', nbins=20, title='Wasted Start % Distribution')
            st.plotly_chart(fig4, use_container_width=True)
    
    with tab3:
        team_stats = season_stats.groupby('Team').agg({
            'Quality_Starts': 'sum',
            'Wasted_Starts': 'sum',
            'GS': 'sum'
        }).reset_index()
        team_stats['Team_QS%'] = (team_stats['Quality_Starts'] / team_stats['GS'] * 100).round(1)
        
        fig5 = px.bar(team_stats.sort_values('Wasted_Starts', ascending=False).head(15), 
                     x='Team', y='Wasted_Starts', title='Wasted Starts by Team')
        st.plotly_chart(fig5, use_container_width=True)

elif analysis_type == "Player Search":
    st.header("Player Search & Comparison")
    
    # Player search
    search_name = st.text_input("Search for a pitcher:", placeholder="Enter pitcher name...")
    
    if search_name:
        matches = season_stats[season_stats['Name'].str.contains(search_name, case=False, na=False)]
        
        if not matches.empty:
            st.subheader("Search Results")
            st.dataframe(matches[['Name', 'Team', 'GS', 'W', 'L', 'ERA', 'Quality_Starts', 'Wasted_Starts']], 
                        use_container_width=True)
            
            # Individual pitcher analysis
            if len(matches) == 1:
                pitcher = matches.iloc[0]
                st.subheader(f"Detailed Analysis: {pitcher['Name']}")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Quality Start %", f"{pitcher['QS%']}%")
                with col2:
                    st.metric("Wasted Start %", f"{pitcher['Wasted%']}%")
                with col3:
                    st.metric("ERA Rank", f"#{season_stats[season_stats['ERA'] <= pitcher['ERA']].shape[0]}")
                
                # Game log
                pitcher_games = games_df[games_df['pitcher_name'] == pitcher['Name']].sort_values('game_date')
                st.subheader("Game Log")
                st.dataframe(pitcher_games[['game_date', 'ip', 'er', 'h', 'bb', 'so', 'decision', 'quality_start', 'wasted_start']], 
                           use_container_width=True)
        else:
            st.warning("No pitchers found matching your search.")
    
    # Player comparison
    st.subheader("Player Comparison")
    col1, col2 = st.columns(2)
    
    with col1:
        player1 = st.selectbox("Select Player 1", season_stats['Name'].tolist(), key="p1")
    with col2:
        player2 = st.selectbox("Select Player 2", season_stats['Name'].tolist(), key="p2")
    
    if player1 != player2:
        p1_stats = season_stats[season_stats['Name'] == player1].iloc[0]
        p2_stats = season_stats[season_stats['Name'] == player2].iloc[0]
        
        comparison_data = {
            'Stat': ['Games Started', 'Wins', 'ERA', 'WHIP', 'Quality Starts', 'Wasted Starts', 'QS%', 'Wasted%'],
            player1: [p1_stats['GS'], p1_stats['W'], p1_stats['ERA'], p1_stats['WHIP'], 
                     p1_stats['Quality_Starts'], p1_stats['Wasted_Starts'], p1_stats['QS%'], p1_stats['Wasted%']],
            player2: [p2_stats['GS'], p2_stats['W'], p2_stats['ERA'], p2_stats['WHIP'], 
                     p2_stats['Quality_Starts'], p2_stats['Wasted_Starts'], p2_stats['QS%'], p2_stats['Wasted%']]
        }
        
        comparison_df = pd.DataFrame(comparison_data)
        st.dataframe(comparison_df, use_container_width=True)

# Footer
st.markdown("---")
st.markdown("*Data sourced from MLB Stats API | Built with Streamlit*")
