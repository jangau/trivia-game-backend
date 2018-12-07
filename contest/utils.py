from contest.models import DuelGame, GameTeam


def register_teams(teams, game_session):
    gts = []
    for team in teams:
        gt = GameTeam(
            team=team,
            game_session=game_session
        )
        gt.save()
        gts.append(gt)
    return gts


def create_duel_games(teams, game_session):
    combinations = [teams[i:i + 2] for i in range(0, len(teams), 2)]
    games = []
    for idx, combo in enumerate(combinations):
        game = DuelGame(
            session=game_session,
            first_team=combo[0],
            second_team=combo[1],
            game_order=idx + 1
        )
        game.save()
        games.append(game)

    return games[0]
