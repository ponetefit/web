"""
multi_firebase.py - Maneja conexiones a MULTIPLES proyectos Firebase, uno
por cada cuenta de profesor aprobada (multi-tenant real: cada profesor
tiene su propio proyecto Firebase, separado del resto).

La cuenta master (raffa687) es la excepcion: usa el mismo proyecto que el
plano de control (ver firebase_config.py), asi que no necesita una app
adicional.
"""

import json
import firebase_admin
from firebase_admin import credentials, db

import control_db
import firebase_config

_apps_cache = {}  # account_id -> firebase_admin.App


def _get_app_for_account(account_id):
    if account_id in _apps_cache:
        return _apps_cache[account_id]

    cuenta = control_db.obtener_cuenta(account_id)
    if not cuenta:
        raise ValueError(f"Cuenta no encontrada: {account_id}")

    proyecto = cuenta.get("proyecto") or {}
    database_url = proyecto.get("databaseURL")
    cred_json = proyecto.get("credenciales_json")

    if not database_url or not cred_json:
        raise ValueError(
            "Esta cuenta todavia no tiene un proyecto Firebase propio configurado. "
            "Un admin tiene que aprobarla desde /admin."
        )

    cred_dict = json.loads(cred_json) if isinstance(cred_json, str) else cred_json
    cred = credentials.Certificate(cred_dict)

    app_name = f"cuenta_{account_id}"
    try:
        app = firebase_admin.get_app(app_name)
    except ValueError:
        app = firebase_admin.initialize_app(cred, {"databaseURL": database_url}, name=app_name)

    _apps_cache[account_id] = app
    return app


def get_db_ref(account_id, path):
    """Devuelve una referencia a un nodo de la Realtime Database del
    proyecto Firebase de esta cuenta (o del proyecto master, si la cuenta
    es la de raffa687)."""
    if not account_id:
        raise ValueError("Falta account_id")

    if account_id == control_db.MASTER_ACCOUNT_ID:
        return firebase_config.get_db_ref(path)

    app = _get_app_for_account(account_id)
    return db.reference(path, app=app)
