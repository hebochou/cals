from cals_app.core.db import _db_connect

from .blueprint import student_bp


@student_bp.route("/health/db")
def health_db():
    conn = _db_connect()
    if not conn:
        return {"ok": False, "enabled": False}, 200
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return {"ok": True, "enabled": True}, 200
    except Exception as exc:
        return {"ok": False, "enabled": True, "error": str(exc)}, 500
    finally:
        try:
            conn.close()
        except Exception:
            pass
