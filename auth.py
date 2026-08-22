"""
auth.py - Sesion de login (cookie firmada de Flask, requiere SECRET_KEY) y
decoradores para proteger rutas del backend.
"""
from functools import wraps
from flask import session, jsonify


def iniciar_sesion(account_id, email, rol):
    session["account_id"] = account_id
    session["email"] = email
    session["rol"] = rol
    session.permanent = True


def cerrar_sesion():
    session.clear()


def cuenta_actual():
    if "account_id" not in session:
        return None
    return {
        "account_id": session["account_id"],
        "email": session.get("email"),
        "rol": session.get("rol")
    }


def account_id_actual():
    return session.get("account_id")


def login_requerido(f):
    """Exige que haya una sesion iniciada (cualquier rol)."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "account_id" not in session:
            return jsonify({"ok": False, "error": "No autenticado", "auth_requerida": True}), 401
        return f(*args, **kwargs)
    return wrapper


def admin_requerido(f):
    """Exige que la sesion sea la del admin (raffa687)."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "account_id" not in session or session.get("rol") != "admin":
            return jsonify({"ok": False, "error": "Solo el administrador puede hacer esto"}), 403
        return f(*args, **kwargs)
    return wrapper
