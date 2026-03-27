from __future__ import annotations

import logging

from fastapi import FastAPI

from config.config import Config

try:
    import inngest
    import inngest.fast_api
except ImportError:  # pragma: no cover
    inngest = None


def create_inngest_app(config: Config) -> FastAPI:
    app = FastAPI(title="CasperCode Inngest Runtime")

    if inngest is None:
        return app

    inngest_client = inngest.Inngest(
        app_id=config.inngest_app_id,
        logger=logging.getLogger("uvicorn"),
    )

    functions: list = []
    inngest.fast_api.serve(app, inngest_client, functions)

    return app
