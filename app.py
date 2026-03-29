"""
app.py - Backend API de PONETE FIT
Flask API que reemplaza la logica de customtkinter de ponetefit.py
"""

import random
import re
import time
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from firebase_config import get_db_ref, init_firebase

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

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


# ──────────────────────────────────────────────────────────────
#  RUTAS - PAGINAS ESTATICAS
# ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Pagina principal - redirige al panel del profesor."""
    return app.send_static_file("profesor.html")


@app.route("/alumno")
def alumno():
    """Pagina del alumno."""
    return app.send_static_file("alumno.html")


# ──────────────────────────────────────────────────────────────
#  API - VIDEOTECA (CRUD en Firebase)
# ──────────────────────────────────────────────────────────────

@app.route("/api/videoteca", methods=["GET"])
def obtener_videoteca():
    """Obtiene toda la videoteca desde Firebase. Si no existe, la inicializa con datos por defecto."""
    try:
        ref = get_db_ref("/videoteca")
        data = ref.get()
        if not data:
            # Inicializar con datos por defecto
            ref.set(VIDEOTECA_DEFAULTS)
            data = VIDEOTECA_DEFAULTS
        return jsonify({"ok": True, "videoteca": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/videoteca/categorias", methods=["GET"])
def obtener_categorias():
    """Obtiene la lista de categorias."""
    try:
        ref = get_db_ref("/videoteca")
        data = ref.get()
        if not data:
            ref.set(VIDEOTECA_DEFAULTS)
            data = VIDEOTECA_DEFAULTS
        return jsonify({"ok": True, "categorias": list(data.keys())})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/videoteca/categoria/<categoria>", methods=["GET"])
def obtener_ejercicios_categoria(categoria):
    """Obtiene los ejercicios de una categoria especifica."""
    try:
        ref = get_db_ref(f"/videoteca/{categoria}")
        data = ref.get()
        if data is None:
            return jsonify({"ok": False, "error": "Categoria no encontrada"}), 404
        return jsonify({"ok": True, "ejercicios": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/videoteca/ejercicio", methods=["POST"])
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

        # Construir objeto del ejercicio con campos de musculos
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

        ref = get_db_ref(f"/videoteca/{categoria}")
        ejercicios = ref.get() or []

        # Buscar si ya existe para actualizar
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
def eliminar_ejercicio():
    """Elimina un ejercicio de una categoria."""
    try:
        body = request.json
        categoria = body.get("categoria", "").strip()
        nombre = body.get("nombre", "").strip().upper()

        if not categoria or not nombre:
            return jsonify({"ok": False, "error": "Categoria y nombre son obligatorios"}), 400

        ref = get_db_ref(f"/videoteca/{categoria}")
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
def nueva_categoria():
    """Crea una nueva categoria vacia en la videoteca."""
    try:
        body = request.json
        nombre = body.get("nombre", "").strip()
        if not nombre:
            return jsonify({"ok": False, "error": "Nombre de categoria obligatorio"}), 400

        ref = get_db_ref(f"/videoteca/{nombre}")
        actual = ref.get()
        if actual is not None:
            return jsonify({"ok": False, "error": "La categoria ya existe"}), 409

        ref.set([])
        return jsonify({"ok": True, "mensaje": f"Categoria creada: {nombre}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/videoteca/categoria", methods=["DELETE"])
def eliminar_categoria():
    """Elimina una categoria completa de la videoteca."""
    try:
        body = request.json
        nombre = body.get("nombre", "").strip()
        if not nombre:
            return jsonify({"ok": False, "error": "Nombre de categoria obligatorio"}), 400

        ref = get_db_ref(f"/videoteca/{nombre}")
        ref.delete()
        return jsonify({"ok": True, "mensaje": f"Categoria eliminada: {nombre}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ──────────────────────────────────────────────────────────────
#  API - GENERACION DE EJERCICIOS ALEATORIOS
# ──────────────────────────────────────────────────────────────

@app.route("/api/ejercicios/aleatorios", methods=["POST"])
def ejercicios_aleatorios():
    """Genera ejercicios aleatorios segun zona muscular.
    Body: { "zonas": ["Piernas", "Brazos", ...] }
    """
    try:
        body = request.json
        zonas = body.get("zonas", [])

        ref = get_db_ref("/videoteca")
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
def todos_los_ejercicios():
    """Retorna lista plana de todos los ejercicios de todas las categorias."""
    try:
        ref = get_db_ref("/videoteca")
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
def compartir_rutina():
    """Sube una rutina a Firebase y genera un codigo unico.
    Body: {
        "alumno": "NOMBRE",
        "tipo": "Circuito|Tabata|EMOM|Series|ENTRENAMIENTO|MULTIDIA",
        "datos": { ... payload completo de la rutina ... },
        "dias": [  <-- opcional, para rutinas multi-dia
            { "titulo": "Dia 1", "tipo": "...", "datos": { ... } },
            { "titulo": "Dia 2", "tipo": "...", "datos": { ... } },
            ...
        ]
    }
    Si se envian "dias", se guarda como rutina multi-dia.
    Si no hay "dias", se guarda como rutina clasica (retrocompatible).
    """
    try:
        body = request.json
        nombre_alumno = body.get("alumno", "ALUMNO").strip().upper()
        tipo_rutina = body.get("tipo", "Rutina")
        datos_paquete = body.get("datos", {})
        dias = body.get("dias", None)  # Lista de dias para rutinas multi-dia

        if not nombre_alumno:
            nombre_alumno = "ALUMNO"
        nombre_lower = nombre_alumno.lower()

        # Obtener y actualizar contador del alumno
        contador_ref = get_db_ref(f"/alumnos/{nombre_lower}/contador")
        contador_actual = contador_ref.get() or 0
        nuevo_contador = contador_actual + 1
        codigo = f"{nombre_lower}-{nuevo_contador:04d}"

        # Preparar payload base
        payload = {
            "app": "ponetefit",
            "tipo": tipo_rutina,
            "alumno": nombre_alumno,
            "timestamp": time.time(),
        }

        if dias and isinstance(dias, list) and len(dias) > 1:
            # ── RUTINA MULTI-DIA ──────────────────────────────────────────
            # Estructura: dias = [ {titulo, tipo, datos: {...warmup, bloques...}}, ... ]
            payload["es_multidia"] = True
            payload["total_dias"] = len(dias)
            payload["tipo"] = "MULTIDIA"
            # Serializar cada dia como dia_1, dia_2, ...
            for i, dia in enumerate(dias):
                key = f"dia_{i + 1}"
                payload[key] = {
                    "titulo": dia.get("titulo", f"Dia {i + 1}"),
                    "tipo": dia.get("tipo", "ENTRENAMIENTO"),
                    "datos": dia.get("datos", {})
                }
            # Descripcion global opcional
            if datos_paquete.get("descripcion"):
                payload["descripcion"] = datos_paquete["descripcion"]
        else:
            # ── RUTINA CLASICA (un solo dia) ──────────────────────────────
            # Retrocompatible: mismo formato de siempre
            payload["es_multidia"] = False
            payload.update(datos_paquete)

        # Guardar rutina y actualizar contador
        rutina_ref = get_db_ref(f"/rutinas/{codigo}")
        rutina_ref.set(payload)
        contador_ref.set(nuevo_contador)

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
def obtener_rutina(codigo):
    """Obtiene una rutina por su codigo.
    Retrocompatibilidad: si la rutina no tiene 'es_multidia', se trata como un solo dia.
    """
    try:
        ref = get_db_ref(f"/rutinas/{codigo}")
        data = ref.get()
        if not data:
            return jsonify({"ok": False, "error": "Codigo no encontrado"}), 404

        # ── RETROCOMPATIBILIDAD ──────────────────────────────────────────
        # Si la rutina no tiene el campo es_multidia, es una rutina clasica.
        # La marcamos explicitamente para que el frontend la trate bien.
        if "es_multidia" not in data:
            data["es_multidia"] = False

        return jsonify({"ok": True, "rutina": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/rutina/<codigo>", methods=["DELETE"])
def eliminar_rutina(codigo):
    """Elimina una rutina por su codigo y ajusta el contador del alumno."""
    try:
        codigo = codigo.strip().lower()
        ref = get_db_ref(f"/rutinas/{codigo}")
        data = ref.get()
        if not data:
            return jsonify({"ok": False, "error": "Rutina no encontrada"}), 404

        # Obtener el alumno antes de eliminar
        alumno = data.get("alumno", "").strip().lower()

        # Eliminar la rutina
        ref.delete()

        # Decrementar el contador del alumno
        if alumno:
            contador_ref = get_db_ref(f"/alumnos/{alumno}/contador")
            contador_actual = contador_ref.get() or 0
            if contador_actual > 0:
                contador_ref.set(contador_actual - 1)

        return jsonify({"ok": True, "mensaje": f"Rutina {codigo.upper()} eliminada correctamente"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/rutinas/renumerar/<nombre>", methods=["POST"])
def renumerar_rutinas(nombre):
    """Renumera todas las rutinas de un alumno para que sean consecutivas.
    Ejemplo: si se elimina rafa-0002 de [rafa-0001, rafa-0002, rafa-0003],
    rafa-0003 se renombra a rafa-0002 y el contador se ajusta a 2.
    """
    try:
        nombre_lower = nombre.strip().lower()

        # Obtener todas las rutinas del alumno
        ref_rutinas = get_db_ref("/rutinas")
        todas = ref_rutinas.get() or {}

        # Filtrar rutinas del alumno y ordenarlas por codigo
        rutinas_alumno = {}
        for cod, data in todas.items():
            if isinstance(data, dict) and data.get("alumno", "").lower() == nombre_lower:
                rutinas_alumno[cod] = data

        codigos_ordenados = sorted(rutinas_alumno.keys())

        if not codigos_ordenados:
            return jsonify({"ok": True, "mensaje": "No hay rutinas para renumerar", "cambios": 0})

        # Extraer el prefijo (ej: "rafa-" de "rafa-0001")
        primer_codigo = codigos_ordenados[0]
        match = re.match(r'^(.+?)(\d+)$', primer_codigo)
        if not match:
            return jsonify({"ok": False, "error": "No se pudo determinar el formato del codigo"}), 400

        prefijo = match.group(1)
        cambios = 0

        # Renumerar secuencialmente
        for i, codigo_viejo in enumerate(codigos_ordenados):
            num_nuevo = i + 1
            codigo_nuevo = f"{prefijo}{num_nuevo:04d}"

            if codigo_viejo != codigo_nuevo:
                # Mover la rutina al nuevo codigo
                data_rutina = rutinas_alumno[codigo_viejo]
                ref_nuevo = get_db_ref(f"/rutinas/{codigo_nuevo}")
                ref_viejo = get_db_ref(f"/rutinas/{codigo_viejo}")
                ref_nuevo.set(data_rutina)
                ref_viejo.delete()
                cambios += 1

        # Actualizar el contador del alumno
        total = len(codigos_ordenados)
        contador_ref = get_db_ref(f"/alumnos/{nombre_lower}/contador")
        contador_ref.set(total)

        return jsonify({
            "ok": True,
            "mensaje": f"Renumeracion completada: {cambios} rutina(s) renumerada(s)",
            "cambios": cambios,
            "total": total
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/rutina/renombrar", methods=["POST"])
def renombrar_rutina():
    """Renombra el codigo de una rutina (usado como fallback para renumeracion manual).
    Body: { "codigo_viejo": "rafa-0005", "codigo_nuevo": "rafa-0004" }
    """
    try:
        body = request.json
        codigo_viejo = body.get("codigo_viejo", "").strip().lower()
        codigo_nuevo = body.get("codigo_nuevo", "").strip().lower()

        if not codigo_viejo or not codigo_nuevo:
            return jsonify({"ok": False, "error": "codigo_viejo y codigo_nuevo son obligatorios"}), 400

        if codigo_viejo == codigo_nuevo:
            return jsonify({"ok": True, "mensaje": "Los codigos son iguales, nada que hacer"})

        # Obtener datos de la rutina vieja
        ref_viejo = get_db_ref(f"/rutinas/{codigo_viejo}")
        data = ref_viejo.get()
        if not data:
            return jsonify({"ok": False, "error": f"Rutina {codigo_viejo} no encontrada"}), 404

        # Verificar que el nuevo codigo no exista ya
        ref_nuevo = get_db_ref(f"/rutinas/{codigo_nuevo}")
        if ref_nuevo.get():
            return jsonify({"ok": False, "error": f"El codigo {codigo_nuevo} ya existe"}), 409

        # Mover: crear nuevo y eliminar viejo
        ref_nuevo.set(data)
        ref_viejo.delete()

        return jsonify({"ok": True, "mensaje": f"Rutina renombrada de {codigo_viejo.upper()} a {codigo_nuevo.upper()}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/rutinas/alumno/<nombre>", methods=["GET"])
def rutinas_por_alumno(nombre):
    """Lista las rutinas de un alumno."""
    try:
        nombre_lower = nombre.strip().lower()
        ref = get_db_ref("/rutinas")
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
def listar_alumnos():
    """Lista todos los alumnos que tienen rutinas asignadas."""
    try:
        ref = get_db_ref("/alumnos")
        data = ref.get() or {}
        alumnos = sorted(data.keys())
        return jsonify({"ok": True, "alumnos": alumnos})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/alumnos/<nombre>", methods=["DELETE"])
def eliminar_alumno(nombre):
    """Elimina un alumno y todas sus rutinas de Firebase."""
    try:
        nombre_lower = nombre.strip().lower()

        # 1. Obtener y eliminar todas las rutinas del alumno
        ref_rutinas = get_db_ref("/rutinas")
        todas = ref_rutinas.get() or {}

        rutinas_eliminadas = 0
        for cod, data in list(todas.items()):
            if isinstance(data, dict) and data.get("alumno", "").lower() == nombre_lower:
                get_db_ref(f"/rutinas/{cod}").delete()
                rutinas_eliminadas += 1

        # 2. Eliminar el nodo del alumno en /alumnos
        ref_alumno = get_db_ref(f"/alumnos/{nombre_lower}")
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
    """Calcula la pausa recomendada segun las repeticiones."""
    body = request.json
    reps = body.get("reps", 12)
    pausa = calcular_pausa(reps)
    return jsonify({"ok": True, "pausa": pausa, "formato": fmt_pausa(pausa)})


# ──────────────────────────────────────────────────────────────
#  INICIO
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_firebase()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
