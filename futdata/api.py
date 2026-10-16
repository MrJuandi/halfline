"""API HTTP de solo lectura sobre los datos procesados. Toda la lógica está en futdata.web_data.

Endpoints (bajo /api):
  GET /api/meta
  GET /api/teams
  GET /api/leagues/<league>/table?season=
  GET /api/matches?league=&season=&team=&limit=
  GET /api/matches/<match_id>
  GET /api/teams/<league>/<team>?season=
  GET /api/upcoming?days=

Uso:  python -m futdata.api      (sirve en 127.0.0.1:8000, sin debug)
"""
from __future__ import annotations

from flask import Flask, jsonify, request, send_from_directory

from futdata import players_web, team_analysis, web_data
from futdata.common import RAW

CREST_DIR = RAW / "crests"
CREST_MAX_AGE = 7 * 24 * 3600

app = Flask(__name__)
app.json.ensure_ascii = False
app.json.sort_keys = False


def _error(status: int, code: str, message: str):
    return jsonify({"error": code, "message": message}), status


def _int_arg(name: str, default=None, minimum: int | None = None, maximum: int | None = None):
    raw = request.args.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"'{name}' debe ser un entero")
    if (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
        raise ValueError(f"'{name}' fuera de rango")
    return value


@app.errorhandler(404)
def not_found(_exc):
    return _error(404, "not_found", "Recurso no encontrado")


@app.errorhandler(400)
def bad_request(exc):
    return _error(400, "bad_request", getattr(exc, "description", "Petición no válida"))


@app.get("/api/meta")
def meta():
    return jsonify(web_data.meta())


@app.get("/api/teams")
def teams():
    return jsonify(web_data.teams())


@app.get("/api/leagues/<league>/table")
def table(league: str):
    try:
        season = _int_arg("season")
    except ValueError as exc:
        return _error(400, "bad_request", str(exc))
    data = web_data.table(league, season)
    if data is None:
        return _error(404, "not_found", "Liga o temporada no encontrada")
    return jsonify(data)


@app.get("/api/matches")
def matches():
    try:
        season = _int_arg("season")
        limit = _int_arg("limit", minimum=1)
    except ValueError as exc:
        return _error(400, "bad_request", str(exc))
    data = web_data.matches(
        league=request.args.get("league") or None,
        season=season,
        team=request.args.get("team") or None,
        limit=limit,
    )
    return jsonify(data)


@app.get("/api/matches/<match_id>")
def match_detail(match_id: str):
    data = web_data.match_detail(match_id)
    if data is None:
        return _error(404, "not_found", "Partido no encontrado")
    return jsonify(data)


@app.get("/api/teams/<league>/<path:team>")
def team(league: str, team: str):
    try:
        season = _int_arg("season")
    except ValueError as exc:
        return _error(400, "bad_request", str(exc))
    data = web_data.team(league, team, season)
    if data is None:
        return _error(404, "not_found", "Equipo, liga o temporada no encontrados")
    return jsonify(data)


@app.get("/api/analysis/<league>/<path:team>")
def analysis(league: str, team: str):
    try:
        season = _int_arg("season")
    except ValueError as exc:
        return _error(400, "bad_request", str(exc))
    data = team_analysis.team_analysis(league, team, season)
    if data is None:
        return _error(404, "not_found", "Equipo, liga o temporada no encontrados")
    return jsonify(data)


@app.get("/api/styles")
def styles():
    path = web_data.PROCESSED / "styles.json"
    if not path.is_file():
        return _error(404, "not_found", "Ejecuta python -m futdata.styles para generar los estilos")
    return app.response_class(path.read_bytes(), mimetype="application/json")


@app.get("/api/crests/<path:filename>")
def crest(filename: str):
    path = CREST_DIR / filename
    if not path.is_file() or not path.resolve().is_relative_to(CREST_DIR.resolve()):
        return _error(404, "not_found", "Escudo no encontrado")
    response = send_from_directory(CREST_DIR, filename, max_age=CREST_MAX_AGE)
    response.headers["Cache-Control"] = f"public, max-age={CREST_MAX_AGE}"
    return response


def _season_or_now():
    """Temporada como entero, o "now" para el estado actual."""
    if request.args.get("season") == "now":
        return "now"
    return _int_arg("season")


@app.get("/api/players")
def players():
    try:
        season = _season_or_now()
    except ValueError as exc:
        return _error(400, "bad_request", str(exc))
    return jsonify(players_web.player_map(season, request.args.get("league") or None))


@app.get("/api/players/<player_id>")
def player(player_id: str):
    try:
        season = _season_or_now()
    except ValueError as exc:
        return _error(400, "bad_request", str(exc))
    data = players_web.player_profile(player_id, season)
    if data is None:
        return _error(404, "not_found", "Jugador sin perfil (mínimo 900 minutos en una temporada)")
    return jsonify(data)


@app.get("/api/model")
def model_eval():
    data = web_data.model_eval()
    if data is None:
        return _error(404, "not_found", "Sin evaluación del modelo")
    return jsonify(data)


@app.get("/api/markets")
def markets():
    data = web_data.markets()
    if data is None:
        return _error(404, "not_found", "Sin datos de Polymarket")
    return jsonify(data)


@app.get("/api/upcoming")
def upcoming():
    try:
        days = _int_arg("days", default=21, minimum=1, maximum=365)
    except ValueError as exc:
        return _error(400, "bad_request", str(exc))
    return jsonify(web_data.upcoming(days))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
