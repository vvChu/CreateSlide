"""SlideGenius v2.0 — AI Presentation Generator.

Slim entry-point: wires up logging, env-vars, and the Mesop page.
All business logic lives in the ``app`` package.
"""
from __future__ import annotations

import mesop as me
from dotenv import load_dotenv

from app.core.log import setup_logging
from app.ui.handlers import on_load
from app.ui.page import main_page

# ── Bootstrap ───────────────────────────────────────────────────────────
load_dotenv()
setup_logging()


@me.page(
    path="/",
    stylesheets=[
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap",
    ],
    security_policy=me.SecurityPolicy(
        allowed_script_srcs=[
            "https://fonts.googleapis.com",
            "https://fonts.gstatic.com",
        ],
        allowed_connect_srcs=[
            "https://fonts.googleapis.com",
            "https://fonts.gstatic.com",
        ],
    ),
    on_load=on_load,
)
def page():
    main_page()
