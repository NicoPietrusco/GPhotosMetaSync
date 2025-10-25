"""
Google Photos Picker implementation using FastAPI.
Users select photos via Google's picker UI, then we can access selected items.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .auth import auth_router
from .endpoints import all_routers as picker_routers

# Initialize FastAPI app
app = FastAPI(
    title="Google Photos Picker",
    description="Select and manage photos from your Google Photos library",
    version="1.0.0",
)

# Setup static files
current_dir = Path(__file__).parent
static_dir = current_dir / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Setup templates
template_dir = current_dir / "templates"
templates = Jinja2Templates(directory=str(template_dir))

# Simple in-memory session storage (use Redis in production)
sessions = {}

# Inject sessions into routers for access
auth_router.sessions = sessions
for router_item in picker_routers:
    router_item.sessions = sessions

# Include API routers
app.include_router(auth_router)
for router_item in picker_routers:
    app.include_router(router_item)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main page with Photo Picker."""
    return templates.TemplateResponse("picker.html", {"request": request})


@app.get("/docs-redirect")
async def docs_redirect():
    """Redirect to API documentation."""
    return RedirectResponse(url="/docs")


def run_picker_app(host: str = "127.0.0.1", port: int = 8000, reload: bool = True):
    """Run the FastAPI app for Photo Picker."""
    import uvicorn

    print("=" * 60)
    print("GOOGLE PHOTOS PICKER APP (FastAPI)")
    print("=" * 60)
    print(f"\n📸 Main App: http://{host}:{port}")
    print(f"📚 API Docs: http://{host}:{port}/docs")
    print(f"🔧 ReDoc: http://{host}:{port}/redoc")
    print("\nSteps:")
    print("1. Click 'Authenticate' to sign in with Google")
    print("2. Use the Photo Picker to select photos")
    print("3. View selected photos and their metadata\n")
    print("=" * 60 + "\n")

    uvicorn.run("src.app:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    run_picker_app()
