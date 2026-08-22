"""
control_db.py - "Plano de control" multi-cuenta.

Guarda, en el proyecto Firebase MASTER (el mismo que usa raffa687@gmail.com),
todo lo necesario para manejar varias cuentas de profesor:

  /cuentas/{account_id}        -> datos de cada cuenta (email, password hash,
                                   estado, a que proyecto Firebase propio
                                   apunta, si quiere heredar la videoteca)
  /codigos_index/{codigo}      -> account_id dueno de ese codigo de rutina
                                   (asi alumno.html sabe a que proyecto
                                   Firebase consultar cuando un alumno
                                   ingresa su codigo)

raffa687@gmail.com es la cuenta "master": admin de la app y, ademas, sigue
usando el proyecto Firebase original como su propia base de datos.
"""

import time
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
import firebase_config

MASTER_ACCOUNT_ID = "raffa687"
MASTER_EMAIL = "raffa687@gmail.com"
MASTER_PASSWORD_INICIAL = "Tequiero87"


def _cuentas_ref():
    return firebase_config.get_db_ref("/cuentas")


def _codigos_ref():
    return firebase_config.get_db_ref("/codigos_index")


def asegurar_cuenta_master():
    """Crea (si no existe) la cuenta admin de raffa687, ya aprobada, apuntando
    al mismo proyecto Firebase que el plano de control. Se llama al arrancar
    el servidor; si la cuenta ya existe, no toca nada (no pisa la contrasena
    si el usuario ya la cambio)."""
    ref = firebase_config.get_db_ref(f"/cuentas/{MASTER_ACCOUNT_ID}")
    existente = ref.get()
    if existente:
        return existente

    datos = {
        "email": MASTER_EMAIL,
        "password_hash": generate_password_hash(MASTER_PASSWORD_INICIAL),
        "estado": "aprobado",
        "rol": "admin",
        "quiere_videoteca": True,
        "proyecto": {
            "databaseURL": firebase_config.FIREBASE_DB_URL,
            "es_master": True
        },
        "creado": time.time()
    }
    ref.set(datos)
    return datos


def obtener_cuenta(account_id):
    if not account_id:
        return None
    return firebase_config.get_db_ref(f"/cuentas/{account_id}").get()


def buscar_cuenta_por_email(email):
    email = (email or "").strip().lower()
    cuentas = _cuentas_ref().get() or {}
    for account_id, datos in cuentas.items():
        if isinstance(datos, dict) and (datos.get("email") or "").strip().lower() == email:
            return account_id, datos
    return None, None


def crear_solicitud_cuenta(email, password, quiere_videoteca):
    """Crea una cuenta en estado 'pendiente'. Queda bloqueada hasta que el
    admin (raffa687) la apruebe manualmente desde el panel /admin."""
    email_norm = (email or "").strip().lower()
    if not email_norm or "@" not in email_norm:
        raise ValueError("Email invalido")
    if not password or len(password) < 6:
        raise ValueError("La contrasena debe tener al menos 6 caracteres")

    _, existente = buscar_cuenta_por_email(email_norm)
    if existente:
        raise ValueError("Ya existe una cuenta con ese email")

    nuevo_id = uuid.uuid4().hex[:12]
    datos = {
        "email": email_norm,
        "password_hash": generate_password_hash(password),
        "estado": "pendiente",
        "rol": "profesor",
        "quiere_videoteca": bool(quiere_videoteca),
        "proyecto": None,
        "creado": time.time()
    }
    firebase_config.get_db_ref(f"/cuentas/{nuevo_id}").set(datos)
    return nuevo_id, datos


def verificar_login(email, password):
    account_id, datos = buscar_cuenta_por_email(email)
    if not datos:
        return None, "Cuenta no encontrada"
    if not check_password_hash(datos.get("password_hash", ""), password):
        return None, "Contrasena incorrecta"
    if datos.get("estado") == "pendiente":
        return None, "Tu cuenta todavia no fue aprobada por raffa687@gmail.com. Te avisamos por mail apenas este lista."
    if datos.get("estado") != "aprobado":
        return None, "Esta cuenta no esta activa"
    return account_id, None


def listar_solicitudes_pendientes():
    cuentas = _cuentas_ref().get() or {}
    return {
        cid: datos for cid, datos in cuentas.items()
        if isinstance(datos, dict) and datos.get("estado") == "pendiente"
    }


def aprobar_cuenta(account_id, database_url, credenciales_json, prefijo_codigo=None):
    """Vincula la cuenta pendiente a su propio proyecto Firebase (creado a
    mano por el admin en Firebase Console) y la marca como aprobada."""
    ref = firebase_config.get_db_ref(f"/cuentas/{account_id}")
    datos = ref.get()
    if not datos:
        raise ValueError("Cuenta no encontrada")

    ref.update({
        "estado": "aprobado",
        "proyecto": {
            "databaseURL": database_url,
            "credenciales_json": credenciales_json
        },
        "prefijo_codigo": (prefijo_codigo or "").strip().lower(),
        "aprobado_en": time.time()
    })
    return ref.get()


def rechazar_cuenta(account_id):
    firebase_config.get_db_ref(f"/cuentas/{account_id}").delete()


def registrar_codigo(codigo, account_id):
    """Guarda a que cuenta pertenece un codigo de rutina recien creado."""
    if not codigo:
        return
    firebase_config.get_db_ref(f"/codigos_index/{codigo.strip().lower()}").set(account_id)


def eliminar_codigo(codigo):
    if not codigo:
        return
    firebase_config.get_db_ref(f"/codigos_index/{codigo.strip().lower()}").delete()


def cuenta_de_codigo(codigo):
    """Devuelve el account_id dueno de un codigo de rutina (usado por el
    proxy publico que consulta alumno.html)."""
    codigo = (codigo or "").strip().lower()
    if not codigo:
        return None
    return firebase_config.get_db_ref(f"/codigos_index/{codigo}").get()
