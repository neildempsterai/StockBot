"""Internal admin UI. Access via SSH tunnel only (e.g. ssh -L 8080:localhost:8080 user@um790)."""
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route


async def homepage(request):
    return PlainTextResponse("StockBot Admin (internal only)\nHealth: OK")


app = Starlette(debug=False, routes=[Route("/", homepage)])
