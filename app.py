"""
app.py - Backend API de PONETE FIT (version multi-cuenta)

Cambios principales respecto a la version original:
  - Login / crear cuenta antes de entrar al panel del profesor.
  - Cuentas nuevas quedan "pendientes" hasta que raffa687@gmail.com las
    aprueba a mano desde /admin (recibe un aviso por mail al registrarse).
  - Cada cuenta aprobada usa su PROPIO proyecto Firebase (multi-tenant).
  - Si al crear la cuenta se pidio heredar la videoteca, se copia una sola
    vez (al aprobar) desde el proyecto de raffa687.
  - alumno.html ya no habla directo con Firebase: pasa por /api/fb/<codigo>/...,
    que resuelve a que proyecto Firebase pertenece ese codigo y hace de
    proxy, para que cada profesor tenga su propia base de alumnos.
"""

import json
import random
import re
import time
import os
import requests
from flask import Flask, request, jsonify, session
from flask_cors import CORS

import firebase_config
import multi_firebase
import control_db
import auth

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app, supports_credentials=True)

app.secret_key = os.environ.get("SECRET_KEY", "cambia-esta-clave-en-produccion")
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FLASK_ENV") != "development"

# ──────────────────────────────────────────────────────────────
#  VIDEOTECA - Datos por defecto
# ──────────────────────────────────────────────────────────────

VIDEOTECA_DEFAULTS = {
    "Todo el cuerpo": [
        {"nombre": "VITALIZACIONES", "link": "https://www.youtube.com/watch?v=vzx2lNOCIdQ"},
        {"nombre": "PUENTE SUPINO + PULLOVER", "link": "https://www.youtube.com/watch?v=Ue0ot0ToN_M"}
    ],
    "Piernas": [
        {"nombre": "SENTADILLAS", "link": "https://www.youtube.com/watch?v=Dl6dn7c2uCY"},
        {"nombre": "PESO MUERTO", "link": "https://www.youtube.com/watch?v=potGhXeDKdg"},
        {"nombre": "GLUTEOS 4 APOYOS PATADA HACIA ATRAS", "link": "https://youtu.be/mfwa1a3BXVE"},
        {"nombre": "ABDUCTORES DE COSTADO", "link": "https://youtu.be/mfwa1a3BXVE"},
        {"nombre": "GEMELOS", "link": "https://www.youtube.com/watch?v=GoRvh9TpNpg"},
        {"nombre": "ESTOCADAS LATERALES", "link": "https://www.youtube.com/watch?v=A78A0I_8M_I"}
    ],
    "Brazos": [
        {"nombre": "LAGARTIJAS RODILLAS APOYADAS", "link": "https://www.youtube.com/watch?v=bpq9P-NJsrE"},
        {"nombre": "PULL-OVER", "link": "https://www.youtube.com/watch?v=gn7lOaWxANs"},
        {"nombre": "VUELOS POSTERIORES EN 4 APOYOS", "link": "https://www.youtube.com/watch?v=u4nhYOMkMbY"},
        {"nombre": "TRICEPS FRANCES", "link": "https://www.youtube.com/watch?v=_1jpv8e44nM"}
    ],
    "Zona Media": [
        {"nombre": "ABDOMINALES TIJERAS PARA ARRIBA", "link": "https://www.youtube.com/watch?v=NO5g_Mz_myU"},
        {"nombre": "PLANCHA", "link": "https://www.youtube.com/watch?v=AZuRKHCZU0Q"},
        {"nombre": "ABDOMINALES INFERIORES", "link": "https://www.youtube.com/watch?v=Fhbt2p_GBOU"},
        {"nombre": "NADO CORTO", "link": "https://www.youtube.com/watch?v=gvRIYmNaKJo"},
        {"nombre": "NADO LARGO", "link": "https://www.youtube.com/watch?v=6jFYBm2yOlM"},
        {"nombre": "GATO CONTENTO GATO ENOJADO", "link": "https://www.youtube.com/watch?v=DedRH6CUOQQ"},
        {"nombre": "BICHO MUERTO", "link": "https://www.youtube.com/watch?v=yrHeUccpyl0"},
        {"nombre": "ROTACION LUMBAR PIES APOYADOS", "link": "https://youtu.be/SvIdn8l-VKQ"}
    ]
}


# ──────────────────────────────────────────────────────────────
#  HELPERS
# ──────────────────────────────────────────────────────────────

def calcular_pausa(reps):
    """Calcula la pausa de descanso segun la cantidad de repeticiones."""
    r = int(reps) if str(reps).isdigit() else 12
    if r <= 2: return 120
    if r <= 4: return 105
    if r <= 6: return 90
    if r <= 8: return 75
    if r <= 10: return 60
    if r <= 12: return 50
    return 45


def fmt_pausa(seg):
    """Formatea segundos a texto legible."""
    seg = int(seg)
    if seg < 60:
        return f"{seg}s"
    mins, resto = divmod(seg, 60)
    if resto == 0:
        return f"{mins} min"
    return f"{mins} min {resto}s"


def db_ref(path):
    """Referencia Firebase en el proyecto de LA CUENTA LOGUEADA actualmente.
    Solo usar dentro de rutas protegidas con @auth.login_requerido."""
    return multi_firebase.get_db_ref(auth.account_id_actual(), path)


# ──────────────────────────────────────────────────────────────
#  RUTAS - PAGINAS ESTATICAS
# ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Pagina principal: pide login si no hay sesion, si no va al panel del profesor."""
    if not auth.cuenta_actual():
        return app.send_static_file("login.html")
    return app.send_static_file("profesor.html")


@app.route("/login")
def pagina_login():
    return app.send_static_file("login.html")


@app.route("/registro")
def pagina_registro():
    return app.send_static_file("registro.html")


@app.route("/admin")
def pagina_admin():
    return app.send_static_file("admin.html")


@app.route("/alumno")
def alumno():
    """Pagina del alumno (publica, sin login)."""
    return app.send_static_file("alumno.html")


# ──────────────────────────────────────────────────────────────
#  API - AUTENTICACION
# ──────────────────────────────────────────────────────────────

@app.route("/api/auth/registro", methods=["POST"])
def api_registro():
    """Crea una cuenta nueva en estado 'pendiente' y avisa por mail a
    raffa687@gmail.com para que la apruebe desde /admin."""
    try:
        body = request.json or {}
        email = body.get("email", "")
        password = body.get("password", "")
        quiere_videoteca = bool(body.get("quiere_videoteca", False))

        account_id, cuenta = control_db.crear_solicitud_cuenta(email, password, quiere_videoteca)

        try:
            requests.post(
                f"https://formsubmit.co/ajax/{control_db.MASTER_EMAIL}",
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                json={
                    "_subject": "PONETE FIT - Nueva solicitud de cuenta de profesor",
                    "mensaje": f"Se registro una cuenta nueva que necesita tu aprobacion: {cuenta['email']}",
                    "quiere_heredar_videoteca": "Si" if quiere_videoteca else "No",
                    "aprobar_en": "https://TU-DOMINIO-EN-RENDER/admin",
                    "account_id": account_id
                },
                timeout=10
            )
        except Exception:
            pass  # el aviso por mail es informativo, no bloquea el registro

        return jsonify({
            "ok": True,
            "mensaje": "Cuenta creada. Queda pendiente de aprobacion de raffa687@gmail.com."
        })
    except ValueError as ve:
        return jsonify({"ok": False, "error": str(ve)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    try:
        body = request.json or {}
        email = body.get("email", "")
        password = body.get("password", "")

        account_id, error = control_db.verificar_login(email, password)
        if error:
            return jsonify({"ok": False, "error": error}), 401

        cuenta = control_db.obtener_cuenta(account_id)
        auth.iniciar_sesion(account_id, cuenta["email"], cuenta.get("rol", "profesor"))
        return jsonify({"ok": True, "email": cuenta["email"], "rol": cuenta.get("rol", "profesor")})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    auth.cerrar_sesion()
    return jsonify({"ok": True})


@app.route("/api/auth/sesion", methods=["GET"])
def api_sesion():
    cuenta = auth.cuenta_actual()
    return jsonify({"ok": True, "autenticado": cuenta is not None, "cuenta": cuenta})


# ──────────────────────────────────────────────────────────────
#  API - ADMIN (aprobar / rechazar cuentas nuevas)
# ──────────────────────────────────────────────────────────────

@app.route("/api/admin/solicitudes", methods=["GET"])
@auth.admin_requerido
def api_admin_solicitudes():
    return jsonify({"ok": True, "solicitudes": control_db.listar_solicitudes_pendientes()})


@app.route("/api/admin/aprobar", methods=["POST"])
@auth.admin_requerido
def api_admin_aprobar():
    """Vincula la cuenta pendiente al proyecto Firebase nuevo que el admin
    creo a mano en Firebase Console, y si corresponde, migra la videoteca
    de raffa687 a ese proyecto nuevo (una sola vez)."""
    try:
        body = request.json or {}
        account_id = body.get("account_id", "").strip()
        database_url = body.get("database_url", "").strip()
        credenciales_json = body.get("credenciales_json", "").strip()
        prefijo_codigo = body.get("prefijo_codigo", "").strip()

        if not account_id or not database_url or not credenciales_json:
            return jsonify({"ok": False, "error": "Faltan datos: cuenta, databaseURL o credenciales"}), 400

        try:
            json.loads(credenciales_json)
        except Exception:
            return jsonify({"ok": False, "error": "El JSON de credenciales no es valido"}), 400

        cuenta = control_db.aprobar_cuenta(account_id, database_url, credenciales_json, prefijo_codigo)

        migrado = False
        error_migracion = None
        if cuenta.get("quiere_videoteca"):
            try:
                origen = firebase_config.get_db_ref("/videoteca").get()
                if origen:
                    destino = multi_firebase.get_db_ref(account_id, "/videoteca")
                    destino.set(origen)
                    migrado = True
            except Exception as e_mig:
                error_migracion = str(e_mig)

        resultado = {"ok": True, "mensaje": "Cuenta aprobada", "videoteca_migrada": migrado}
        if error_migracion:
            resultado["error_migracion"] = error_migracion
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/admin/rechazar", methods=["POST"])
@auth.admin_requerido
def api_admin_rechazar():
    try:
        body = request.json or {}
        control_db.rechazar_cuenta(body.get("account_id", ""))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ──────────────────────────────────────────────────────────────
#  API - VIDEOTECA (CRUD en Firebase, de la cuenta logueada)
# ──────────────────────────────────────────────────────────────

@app.route("/api/videoteca", methods=["GET"])
@auth.login_requerido
def obtener_videoteca():
    """Obtiene toda la videoteca desde Firebase. Si no existe, la inicializa con datos por defecto."""
    try:
        ref = db_ref("/videoteca")
        data = ref.get()
        if not data:
            ref.set(VIDEOTECA_DEFAULTS)
            data = VIDEOTECA_DEFAULTS
        return jsonify({"ok": True, "videoteca": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/videoteca/categorias", methods=["GET"])
@auth.login_requerido
def obtener_categorias():
    """Obtiene la lista de categorias."""
    try:
        ref = db_ref("/videoteca")
        data = ref.get()
        if not data:
            ref.set(VIDEOTECA_DEFAULTS)
            data = VIDEOTECA_DEFAULTS
        return jsonify({"ok": True, "categorias": list(data.keys())})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/videoteca/categoria/<categoria>", methods=["GET"])
@auth.login_requerido
def obtener_ejercicios_categoria(categoria):
    """Obtiene los ejercicios de una categoria especifica."""
    try:
        ref = db_ref(f"/videoteca/{categoria}")
        data = ref.get()
        if data is None:
            return jsonify({"ok": False, "error": "Categoria no encontrada"}), 404
        return jsonify({"ok": True, "ejercicios": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/videoteca/ejercicio", methods=["POST"])
@auth.login_requerido
def guardar_ejercicio():
    """Agrega o actualiza un ejercicio en una categoria."""
    try:
        body = request.json
        categoria = body.get("categoria", "").strip()
        nombre = body.get("nombre", "").strip().upper()
        link = body.get("link", "").strip()
        musculo1 = body.get("musculo1", "").strip()
        musculo2 = body.get("musculo2", "").strip()
        sinergista = body.get("sinergista", "").strip()
        con_carga = body.get("con_carga", False)
        if isinstance(con_carga, str):
            con_carga = con_carga.lower() == "true"
        tip1 = body.get("tip1", "").strip()
        tip2 = body.get("tip2", "").strip()
        elemento = body.get("elemento", "").strip()

        if not categoria or not nombre or not link:
            return jsonify({"ok": False, "error": "Categoria, nombre y link son obligatorios"}), 400

        ej_data = {"nombre": nombre, "link": link}
        if musculo1:
            ej_data["musculo1"] = musculo1
        if musculo2:
            ej_data["musculo2"] = musculo2
        if sinergista:
            ej_data["sinergista"] = sinergista
        ej_data["con_carga"] = bool(con_carga)
        if tip1:
            ej_data["tip1"] = tip1
        if tip2:
            ej_data["tip2"] = tip2
        if elemento:
            ej_data["elemento"] = elemento

        ref = db_ref(f"/videoteca/{categoria}")
        ejercicios = ref.get() or []

        encontrado = False
        for i, ej in enumerate(ejercicios):
            if isinstance(ej, dict) and ej.get("nombre") == nombre:
                ejercicios[i] = ej_data
                encontrado = True
                break

        if not encontrado:
            ejercicios.append(ej_data)

        ref.set(ejercicios)
        accion = "actualizado" if encontrado else "guardado"
        return jsonify({"ok": True, "mensaje": f"Ejercicio {accion}: {nombre}", "accion": accion})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/videoteca/ejercicio", methods=["DELETE"])
@auth.login_requerido
def eliminar_ejercicio():
    """Elimina un ejercicio de una categoria."""
    try:
        body = request.json
        categoria = body.get("categoria", "").strip()
        nombre = body.get("nombre", "").strip().upper()

        if not categoria or not nombre:
            return jsonify({"ok": False, "error": "Categoria y nombre son obligatorios"}), 400

        ref = db_ref(f"/videoteca/{categoria}")
        ejercicios = ref.get() or []

        nuevos = [ej for ej in ejercicios if not (isinstance(ej, dict) and ej.get("nombre") == nombre)]

        if len(nuevos) < len(ejercicios):
            ref.set(nuevos)
            return jsonify({"ok": True, "mensaje": f"Eliminado: {nombre}"})
        else:
            return jsonify({"ok": False, "error": "Ejercicio no encontrado"}), 404
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/videoteca/categoria", methods=["POST"])
@auth.login_requerido
def nueva_categoria():
    """Crea una nueva categoria vacia en la videoteca."""
    try:
        body = request.json
        nombre = body.get("nombre", "").strip()
        if not nombre:
            return jsonify({"ok": False, "error": "Nombre de categoria obligatorio"}), 400

        ref = db_ref(f"/videoteca/{nombre}")
        actual = ref.get()
        if actual is not None:
            return jsonify({"ok": False, "error": "La categoria ya existe"}), 409

        ref.set([])
        return jsonify({"ok": True, "mensaje": f"Categoria creada: {nombre}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/videoteca/categoria", methods=["DELETE"])
@auth.login_requerido
def eliminar_categoria():
    """Elimina una categoria completa de la videoteca."""
    try:
        body = request.json
        nombre = body.get("nombre", "").strip()
        if not nombre:
            return jsonify({"ok": False, "error": "Nombre de categoria obligatorio"}), 400

        ref = db_ref(f"/videoteca/{nombre}")
        ref.delete()
        return jsonify({"ok": True, "mensaje": f"Categoria eliminada: {nombre}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ──────────────────────────────────────────────────────────────
#  API - GENERACION DE EJERCICIOS ALEATORIOS
# ──────────────────────────────────────────────────────────────

@app.route("/api/ejercicios/aleatorios", methods=["POST"])
@auth.login_requerido
def ejercicios_aleatorios():
    """Genera ejercicios aleatorios segun zona muscular."""
    try:
        body = request.json
        zonas = body.get("zonas", [])

        ref = db_ref("/videoteca")
        videoteca = ref.get() or VIDEOTECA_DEFAULTS

        resultado = []
        for zona in zonas:
            ejercicios = videoteca.get(zona, [])
            if ejercicios:
                ej = random.choice(ejercicios)
                if isinstance(ej, dict):
                    resultado.append(ej)
                elif isinstance(ej, list):
                    resultado.append({"nombre": ej[0], "link": ej[1]})
            else:
                resultado.append({"nombre": f"Sin ejercicios en {zona}", "link": ""})

        return jsonify({"ok": True, "ejercicios": resultado})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/ejercicios/todos", methods=["GET"])
@auth.login_requerido
def todos_los_ejercicios():
    """Retorna lista plana de todos los ejercicios de todas las categorias."""
    try:
        ref = db_ref("/videoteca")
        videoteca = ref.get() or VIDEOTECA_DEFAULTS

        todos = []
        for categoria, ejercicios in videoteca.items():
            for ej in ejercicios:
                if isinstance(ej, dict):
                    todos.append({**ej, "categoria": categoria})
                elif isinstance(ej, list):
                    todos.append({"nombre": ej[0], "link": ej[1], "categoria": categoria})
        return jsonify({"ok": True, "ejercicios": todos})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ──────────────────────────────────────────────────────────────
#  API - COMPARTIR RUTINA (subir a Firebase)
# ──────────────────────────────────────────────────────────────

@app.route("/api/rutina/compartir", methods=["POST"])
@auth.login_requerido
def compartir_rutina():
    """Sube una rutina a Firebase y genera un codigo unico. Registra el
    codigo en el indice global para que alumno.html sepa a que cuenta
    (proyecto Firebase) pertenece."""
    try:
        body = request.json
        nombre_alumno = body.get("alumno", "ALUMNO").strip().upper()
        tipo_rutina = body.get("tipo", "Rutina")
        datos_paquete = body.get("datos", {})
        dias = body.get("dias", None)

        if not nombre_alumno:
            nombre_alumno = "ALUMNO"
        nombre_lower = nombre_alumno.lower()

        contador_ref = db_ref(f"/alumnos/{nombre_lower}/contador")
        contador_actual = contador_ref.get() or 0
        nuevo_contador = contador_actual + 1
        codigo = f"{nombre_lower}-{nuevo_contador:04d}"

        payload = {
            "app": "ponetefit",
            "tipo": tipo_rutina,
            "alumno": nombre_alumno,
            "timestamp": time.time(),
        }

        if dias and isinstance(dias, list) and len(dias) > 1:
            payload["es_multidia"] = True
            payload["total_dias"] = len(dias)
            payload["tipo"] = "MULTIDIA"
            for i, dia in enumerate(dias):
                key = f"dia_{i + 1}"
                payload[key] = {
                    "titulo": dia.get("titulo", f"Dia {i + 1}"),
                    "tipo": dia.get("tipo", "ENTRENAMIENTO"),
                    "datos": dia.get("datos", {})
                }
            if datos_paquete.get("descripcion"):
                payload["descripcion"] = datos_paquete["descripcion"]
        else:
            payload["es_multidia"] = False
            payload.update(datos_paquete)

        rutina_ref = db_ref(f"/rutinas/{codigo}")
        rutina_ref.set(payload)
        contador_ref.set(nuevo_contador)

        control_db.registrar_codigo(codigo, auth.account_id_actual())

        return jsonify({
            "ok": True,
            "codigo": codigo,
            "alumno": nombre_alumno,
            "tipo": payload["tipo"],
            "es_multidia": payload.get("es_multidia", False),
            "total_dias": payload.get("total_dias", 1),
            "mensaje": f"Rutina compartida con codigo {codigo}"
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/rutina/<codigo>", methods=["GET"])
@auth.login_requerido
def obtener_rutina(codigo):
    """Obtiene una rutina por su codigo."""
    try:
        ref = db_ref(f"/rutinas/{codigo}")
        data = ref.get()
        if not data:
            return jsonify({"ok": False, "error": "Codigo no encontrado"}), 404

        if "es_multidia" not in data:
            data["es_multidia"] = False

        return jsonify({"ok": True, "rutina": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/rutina/<codigo>", methods=["DELETE"])
@auth.login_requerido
def eliminar_rutina(codigo):
    """Elimina una rutina por su codigo y ajusta el contador del alumno."""
    try:
        codigo = codigo.strip().lower()
        ref = db_ref(f"/rutinas/{codigo}")
        data = ref.get()
        if not data:
            return jsonify({"ok": False, "error": "Rutina no encontrada"}), 404

        alumno = data.get("alumno", "").strip().lower()
        ref.delete()
        control_db.eliminar_codigo(codigo)

        if alumno:
            contador_ref = db_ref(f"/alumnos/{alumno}/contador")
            contador_actual = contador_ref.get() or 0
            if contador_actual > 0:
                contador_ref.set(contador_actual - 1)

        return jsonify({"ok": True, "mensaje": f"Rutina {codigo.upper()} eliminada correctamente"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/rutinas/renumerar/<nombre>", methods=["POST"])
@auth.login_requerido
def renumerar_rutinas(nombre):
    """Renumera todas las rutinas de un alumno para que sean consecutivas."""
    try:
        nombre_lower = nombre.strip().lower()
        account_id = auth.account_id_actual()

        ref_rutinas = db_ref("/rutinas")
        todas = ref_rutinas.get() or {}

        rutinas_alumno = {}
        for cod, data in todas.items():
            if isinstance(data, dict) and data.get("alumno", "").lower() == nombre_lower:
                rutinas_alumno[cod] = data

        codigos_ordenados = sorted(rutinas_alumno.keys())

        if not codigos_ordenados:
            return jsonify({"ok": True, "mensaje": "No hay rutinas para renumerar", "cambios": 0})

        primer_codigo = codigos_ordenados[0]
        match = re.match(r'^(.+?)(\d+)$', primer_codigo)
        if not match:
            return jsonify({"ok": False, "error": "No se pudo determinar el formato del codigo"}), 400

        prefijo = match.group(1)
        cambios = 0
        mapeo = []  # [{"viejo": "RAFA0004", "nuevo": "RAFA0003"}, ...] para que el
                    # frontend pueda actualizar referencias guardadas (ej: repositorio)

        for i, codigo_viejo in enumerate(codigos_ordenados):
            num_nuevo = i + 1
            codigo_nuevo = f"{prefijo}{num_nuevo:04d}"

            if codigo_viejo != codigo_nuevo:
                data_rutina = rutinas_alumno[codigo_viejo]
                ref_nuevo = db_ref(f"/rutinas/{codigo_nuevo}")
                ref_viejo = db_ref(f"/rutinas/{codigo_viejo}")
                ref_nuevo.set(data_rutina)
                ref_viejo.delete()
                control_db.registrar_codigo(codigo_nuevo, account_id)
                control_db.eliminar_codigo(codigo_viejo)
                cambios += 1
                mapeo.append({"viejo": codigo_viejo.upper(), "nuevo": codigo_nuevo.upper()})

        total = len(codigos_ordenados)
        contador_ref = db_ref(f"/alumnos/{nombre_lower}/contador")
        contador_ref.set(total)

        return jsonify({
            "ok": True,
            "mensaje": f"Renumeracion completada: {cambios} rutina(s) renumerada(s)",
            "cambios": cambios,
            "total": total,
            "mapeo": mapeo
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/rutina/renombrar", methods=["POST"])
@auth.login_requerido
def renombrar_rutina():
    """Renombra el codigo de una rutina."""
    try:
        body = request.json
        codigo_viejo = body.get("codigo_viejo", "").strip().lower()
        codigo_nuevo = body.get("codigo_nuevo", "").strip().lower()

        if not codigo_viejo or not codigo_nuevo:
            return jsonify({"ok": False, "error": "codigo_viejo y codigo_nuevo son obligatorios"}), 400

        if codigo_viejo == codigo_nuevo:
            return jsonify({"ok": True, "mensaje": "Los codigos son iguales, nada que hacer"})

        ref_viejo = db_ref(f"/rutinas/{codigo_viejo}")
        data = ref_viejo.get()
        if not data:
            return jsonify({"ok": False, "error": f"Rutina {codigo_viejo} no encontrada"}), 404

        ref_nuevo = db_ref(f"/rutinas/{codigo_nuevo}")
        if ref_nuevo.get():
            return jsonify({"ok": False, "error": f"El codigo {codigo_nuevo} ya existe"}), 409

        ref_nuevo.set(data)
        ref_viejo.delete()

        control_db.registrar_codigo(codigo_nuevo, auth.account_id_actual())
        control_db.eliminar_codigo(codigo_viejo)

        return jsonify({"ok": True, "mensaje": f"Rutina renombrada de {codigo_viejo.upper()} a {codigo_nuevo.upper()}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/rutinas/alumno/<nombre>", methods=["GET"])
@auth.login_requerido
def rutinas_por_alumno(nombre):
    """Lista las rutinas de un alumno."""
    try:
        nombre_lower = nombre.strip().lower()
        ref = db_ref("/rutinas")
        todas = ref.get() or {}

        rutinas_alumno = {}
        for cod, data in todas.items():
            if isinstance(data, dict) and data.get("alumno", "").lower() == nombre_lower:
                rutinas_alumno[cod] = {
                    "tipo": data.get("tipo", ""),
                    "timestamp": data.get("timestamp", 0),
                    "alumno": data.get("alumno", "")
                }

        return jsonify({"ok": True, "rutinas": rutinas_alumno})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ──────────────────────────────────────────────────────────────
#  API - ALUMNOS
# ──────────────────────────────────────────────────────────────

@app.route("/api/alumnos", methods=["GET"])
@auth.login_requerido
def listar_alumnos():
    """Lista todos los alumnos que tienen rutinas asignadas."""
    try:
        ref = db_ref("/alumnos")
        data = ref.get() or {}
        alumnos = sorted(data.keys())
        return jsonify({"ok": True, "alumnos": alumnos})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/alumnos/<nombre>", methods=["DELETE"])
@auth.login_requerido
def eliminar_alumno(nombre):
    """Elimina un alumno y todas sus rutinas de Firebase."""
    try:
        nombre_lower = nombre.strip().lower()

        ref_rutinas = db_ref("/rutinas")
        todas = ref_rutinas.get() or {}

        rutinas_eliminadas = 0
        for cod, data in list(todas.items()):
            if isinstance(data, dict) and data.get("alumno", "").lower() == nombre_lower:
                db_ref(f"/rutinas/{cod}").delete()
                control_db.eliminar_codigo(cod)
                rutinas_eliminadas += 1

        ref_alumno = db_ref(f"/alumnos/{nombre_lower}")
        ref_alumno.delete()

        return jsonify({
            "ok": True,
            "mensaje": f"Alumno {nombre_lower.upper()} eliminado con {rutinas_eliminadas} rutina(s) borrada(s)",
            "rutinas_eliminadas": rutinas_eliminadas
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ──────────────────────────────────────────────────────────────
#  API - UTILIDADES
# ──────────────────────────────────────────────────────────────

@app.route("/api/pausa/calcular", methods=["POST"])
def calcular_pausa_endpoint():
    """Calcula la pausa recomendada segun las repeticiones. (No toca Firebase, publica.)"""
    body = request.json
    reps = body.get("reps", 12)
    pausa = calcular_pausa(reps)
    return jsonify({"ok": True, "pausa": pausa, "formato": fmt_pausa(pausa)})


# ──────────────────────────────────────────────────────────────
#  API - REPOSITORIO DE RUTINAS (Firebase)
# ──────────────────────────────────────────────────────────────

@app.route("/api/repositorio", methods=["GET"])
@auth.login_requerido
def obtener_repositorio():
    """Obtiene el repositorio de rutinas del profesor desde Firebase."""
    try:
        ref = db_ref("/repositorio")
        data = ref.get()
        return jsonify({"ok": True, "repositorio": data or []})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/repositorio", methods=["POST"])
@auth.login_requerido
def guardar_repositorio():
    """Guarda el repositorio completo de rutinas del profesor en Firebase."""
    try:
        body = request.json
        repositorio = body.get("repositorio", [])
        ref = db_ref("/repositorio")
        ref.set(repositorio)
        return jsonify({"ok": True, "mensaje": "Repositorio guardado"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ──────────────────────────────────────────────────────────────
#  API - PIZARRA OCR (proxy seguro para OpenRouter)
# ──────────────────────────────────────────────────────────────

@app.route("/api/pizarra-ocr", methods=["POST"])
@auth.login_requerido
def pizarra_ocr():
    """Proxy para OpenRouter - evita exponer la API key en el frontend."""
    try:
        body = request.json
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            return jsonify({"ok": False, "error": "API key no configurada"}), 500

        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://ponetefit.app",
                "X-Title": "PONETE FIT"
            },
            json=body,
            timeout=30
        )
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ──────────────────────────────────────────────────────────────
#  API - PROXY PUBLICO PARA ALUMNO.HTML (multi-cuenta)
# ──────────────────────────────────────────────────────────────
#
# alumno.html es publico (no requiere login). Antes hablaba DIRECTO con
# Firebase usando la URL fija de la cuenta de raffa687. Ahora, como cada
# profesor tiene su PROPIO proyecto Firebase, alumno.html llama a esta ruta
# pasando el codigo de rutina que el alumno escribio; el backend resuelve
# a que cuenta pertenece ese codigo (usando /codigos_index) y hace de
# proxy contra el proyecto Firebase correcto, sin exponer credenciales de
# ningun profesor en el navegador del alumno.
#
# Soporta el mismo "shape" que la REST API de Firebase (GET/PUT/POST sobre
# rutas .json, con orderBy/startAt/endAt), para poder reusar el JS de
# alumno.html cambiando solo las URLs base.

@app.route("/api/fb/<codigo>/<path:subpath>", methods=["GET", "POST", "PUT"])
def fb_proxy(codigo, subpath):
    try:
        account_id = control_db.cuenta_de_codigo(codigo)
        if not account_id:
            return jsonify(None if request.method == "GET" else {"ok": False, "error": "Codigo no reconocido"}), (
                200 if request.method == "GET" else 404
            )

        db_path = "/" + subpath
        if db_path.endswith(".json"):
            db_path = db_path[:-5]

        ref = multi_firebase.get_db_ref(account_id, db_path)

        order_by = request.args.get("orderBy")
        query = ref
        if order_by:
            order_by = order_by.strip('"')
            if order_by == "$key":
                query = ref.order_by_key()
            elif order_by == "$value":
                query = ref.order_by_value()
            else:
                query = ref.order_by_child(order_by)

            start_at = request.args.get("startAt")
            end_at = request.args.get("endAt")
            if start_at is not None:
                query = query.start_at(start_at.strip('"'))
            if end_at is not None:
                query = query.end_at(end_at.strip('"'))
            limit_first = request.args.get("limitToFirst")
            if limit_first:
                query = query.limit_to_first(int(limit_first))

        if request.method == "GET":
            return jsonify(query.get())

        body = request.get_json(silent=True)
        if request.method == "PUT":
            ref.set(body)
            return jsonify(body)

        # POST => equivalente a "push" de Firebase (genera un ID nuevo)
        nueva = ref.push(body)
        return jsonify({"name": nueva.key})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/fb-meta/<codigo>", methods=["GET"])
def fb_meta(codigo):
    """Datos publicos minimos de la cuenta duena de un codigo (por ahora,
    el mail del profesor, para el aviso via FormSubmit cuando entra un alumno)."""
    try:
        account_id = control_db.cuenta_de_codigo(codigo)
        if not account_id:
            return jsonify({"ok": False, "error": "Codigo no reconocido"}), 404
        cuenta = control_db.obtener_cuenta(account_id)
        return jsonify({"ok": True, "email": (cuenta or {}).get("email", control_db.MASTER_EMAIL)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ──────────────────────────────────────────────────────────────
#  INICIO
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    firebase_config.init_firebase()
    control_db.asegurar_cuenta_master()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
else:
    # Cuando corre con gunicorn (Render), tambien hay que inicializar aca.
    firebase_config.init_firebase()
    control_db.asegurar_cuenta_master()
