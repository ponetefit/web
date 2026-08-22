"""
firebase_config.py - Conexion al proyecto Firebase "master".

Este proyecto cumple DOS roles:
1) Es el "plano de control" de toda la app: guarda la lista de cuentas de
   profesor (/cuentas), su estado de aprobacion y el indice global de
   codigos de rutina -> cuenta (/codigos_index).
2) Es tambien el proyecto de datos propio de la cuenta de
   raffa687@gmail.com (alumnos, rutinas, videoteca, repositorio), tal cual
   funcionaba la app antes de tener multiples cuentas.

Las cuentas de profesores NUEVOS usan cada una su PROPIO proyecto Firebase
(ver multi_firebase.py), separado de este.
"""

import os
import json
import firebase_admin
from firebase_admin import credentials, db

# URL de la Firebase Realtime Database "master"
FIREBASE_DB_URL = os.environ.get(
    "FIREBASE_DB_URL",
    "https://ponetefit-app-default-rtdb.firebaseio.com"
)

# Ruta al archivo de credenciales de servicio de Firebase (proyecto master)
FIREBASE_CRED_PATH = os.environ.get("FIREBASE_CRED_PATH", "serviceAccountKey.json")

_initialized = False


def init_firebase():
    """Inicializa Firebase Admin SDK (app por defecto = proyecto master). Solo se ejecuta una vez."""
    global _initialized
    if _initialized:
        return

    if os.path.exists(FIREBASE_CRED_PATH):
        cred = credentials.Certificate(FIREBASE_CRED_PATH)
        firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})
    else:
        cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
        if cred_json:
            cred_dict = json.loads(cred_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})
        else:
            print("ADVERTENCIA: No se encontro serviceAccountKey.json ni FIREBASE_CREDENTIALS_JSON.")
            print("Usando modo REST directo contra Firebase (sin autenticacion de admin).")
            firebase_admin.initialize_app(options={"databaseURL": FIREBASE_DB_URL})

    _initialized = True


def get_db_ref(path):
    """Retorna una referencia a un nodo del proyecto Firebase master (plano de control + datos de raffa687)."""
    init_firebase()
    return db.reference(path)
