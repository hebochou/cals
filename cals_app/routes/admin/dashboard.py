﻿from flask import render_template, request, session

from cals_app.core.security import admin_required
from cals_app.services.shared.analytics import _admin_compute_stats

from .blueprint import admin_bp


@admin_bp.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    range_key = (request.args.get("range", "week") or "week").strip() or "week"
    if range_key not in {"day", "week", "month", "year"}:
        range_key = "week"
    stats = _admin_compute_stats(range_key)
    return render_template("admin/dashboard.html", stats=stats, range=range_key)


@admin_bp.route("/admin/api/stats")
def admin_api_stats():
    if session.get("role") != "admin":
        return {"ok": False, "error": "forbidden"}, 403
    range_key = (request.args.get("range", "week") or "week").strip() or "week"
    if range_key not in {"day", "week", "month", "year"}:
        range_key = "week"
    return {"ok": True, "data": _admin_compute_stats(range_key)}
