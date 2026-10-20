"""NURU web service.

Endpoints
  POST /sms/incoming     Africa's Talking incoming SMS callback (form-encoded)
  POST /rapidpro/webhook RapidPro "Call Webhook" action (JSON); returns the reply
  GET  /health           liveness and configuration summary (no secrets)

Run:  uvicorn nuru.app:app --reload
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import BackgroundTasks, Body, FastAPI, Form, HTTPException, Query

from . import __version__
from .config import Settings, get_settings
from .router import Router
from .sms import SmsSender, build_sender, hash_phone

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("nuru.app")


def create_app(
    router: Optional[Router] = None,
    sender: Optional[SmsSender] = None,
    settings: Optional[Settings] = None,
) -> FastAPI:
    settings = settings or get_settings()
    router = router or Router.from_settings(settings)
    sender = sender or build_sender(settings)

    app = FastAPI(
        title="NURU",
        version=__version__,
        description="Toll-free two-way SMS health education for Tanzania (prototype).",
    )
    app.state.router = router
    app.state.sender = sender
    app.state.settings = settings

    def _check_token(token: Optional[str]) -> None:
        if settings.webhook_token and token != settings.webhook_token:
            raise HTTPException(status_code=403, detail="invalid token")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "version": __version__,
            "llm_provider": router.provider.name,
            "content_entries": len(router.retriever.entries),
            "facilities": len(router.finder.facilities),
            "sample_facility_data": router.sample_facility_data,
            "sms_dry_run": settings.sms_dry_run or not settings.at_api_key,
        }

    @app.post("/sms/incoming")
    def sms_incoming(
        background: BackgroundTasks,
        from_: str = Form(..., alias="from"),
        to: str = Form(""),
        text: str = Form(""),
        date: str = Form(""),
        id: str = Form(""),
        linkId: Optional[str] = Form(None),
        networkCode: Optional[str] = Form(None),
        token: Optional[str] = Query(None),
    ) -> dict[str, Any]:
        _check_token(token)
        reply = router.handle(from_, text)
        log.info(
            "inbound id=%s user=%s category=%s rule=%s segments=%d",
            id,
            hash_phone(from_, settings.phone_hash_salt),
            reply.category,
            reply.rule_id,
            reply.segments,
        )
        # Africa's Talking only needs a 200 quickly; the reply goes out via the SMS API.
        background.add_task(sender.send, from_, reply.text, linkId)
        return {"status": "accepted", "id": id}

    @app.post("/rapidpro/webhook")
    def rapidpro_webhook(
        payload: dict[str, Any] = Body(...),
        token: Optional[str] = Query(None),
    ) -> dict[str, Any]:
        """RapidPro flow step: Call Webhook (POST) then send @webhook.reply.

        Accepts RapidPro's default body ({"contact": {...}, "input": {"text": ...,
        "urn": ...}}) or a minimal {"urn": ..., "text": ...}.
        """
        _check_token(token)
        input_ = payload.get("input") or {}
        contact = payload.get("contact") or {}
        text = input_.get("text", payload.get("text", "")) or ""
        user = input_.get("urn") or payload.get("urn") or contact.get("uuid") or "rapidpro:unknown"
        reply = router.handle(str(user), str(text))
        return {
            "reply": reply.text,
            "category": reply.category,
            "rule_id": reply.rule_id,
            "segments": reply.segments,
        }

    return app


app = create_app()
