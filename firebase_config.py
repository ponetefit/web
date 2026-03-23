"""
firebase_config.py - Configuracion de Firebase para PONETE FIT
Usa firebase-admin para operaciones del servidor (backend).
El frontend del alumno sigue usando la REST API directa de Firebase.
"""

import os
import json
import firebase_admin
from firebase_admin import credentials, db

# URL de tu Firebase Realtime Database
FIREBASE_DB_URL = os.environ.get(
    "FIREBASE_DB_URL",
    "https://ponetefit-app-default-rtdb.firebaseio.com"
)

# Ruta al archivo de credenciales de servicio de Firebase
# Descargalo desde: Firebase Console > Project Settings > Service Accounts > Generate New Private Key
FIREBASE_CRED_PATH = os.environ.get("FIREBASE_CRED_PATH", "serviceAccountKey.json")

_initialized = False


def init_firebase():
    """Inicializa Firebase Admin SDK. Solo se ejecuta una vez."""
    global _initialized
    if _initialized:
        return

    if os.path.exists(FIREBASE_CRED_PATH):
        cred = credentials.Certificate(FIREBASE_CRED_PATH)
        firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})
    else:
        # Fallback: si no hay archivo de credenciales, intentar con credenciales
        # de variable de entorno (util para deploy en la nube)
        cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
        if cred_json:
            cred_dict = json.loads(cred_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})
        else:
            # Sin credenciales: modo REST directo (para desarrollo)
            print("ADVERTENCIA: No se encontro serviceAccountKey.json ni FIREBASE_CREDENTIALS_JSON.")
            print("Usando modo REST directo contra Firebase (sin autenticacion de admin).")
            firebase_admin.initialize_app(options={"databaseURL": FIREBASE_DB_URL})

    _initialized = True


def get_db_ref(path):
    """Retorna una referencia a un nodo de la Realtime Database."""
    init_firebase()
    return db.reference(path)
