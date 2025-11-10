from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_session import Session
from dotenv import load_dotenv
from utils.db_utils import ejecutar_sql
from functools import wraps
from flask import jsonify
from datetime import date, datetime, timedelta
import re
import math

# Aca importamos todo lo que vayamos a usar, en el documento de requerimientos estan todas las librerias que se usan
# en la consola usen el metodo pip para instalar cosas como flask

load_dotenv() #dotenv es una biblioteca de Nodejs que permite cargar las variables de entorno desde un archivo .env.

app = Flask(__name__)

# Configuración de la sesión
app.config['SECRET_KEY'] = 'tu_clave_secreta'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

#para crear rutas en flask usamos esta estructura
@app.route('/')
def path_inicial():
    # Verifica si el usuario está autenticado y ha seleccionado un perfil, esto se hara en cada ruta necesaria
    if 'nombre' in session:
        return redirect(url_for('seleccionar_perfil'))
    else:
        return redirect(url_for('login'))

# Ruta para el home donde se mostrarán los mensajes
@app.route('/home')
def home():
    if 'nombre' not in session:
        return redirect(url_for('login'))

    nombre = session['nombre']
    # Filtrar mensajes que hayan sido enviados en los últimos 7 días
    fecha_limite = datetime.now() - timedelta(days=2)
    query_mensajes = """
        SELECT mensaje, dia FROM mensajes
        WHERE dia >= %s
        ORDER BY dia DESC
    """
    mensajes = ejecutar_sql(query_mensajes, (fecha_limite,)) #ejecutar_sql enviara una consulta sql a tu base de datos,
                                                    #espera un parametro que es la query y mas de uno si usas %s, como en este caso

    return render_template('home.html',nombre=nombre, mensajes=mensajes)

@app.route('/login', methods=['GET', 'POST']) #en las rutas, puedes definir que metodos usar para hacer una cosa dependiendo cada metodo
def login():
    if 'nombre' in session:
        return redirect(url_for('seleccionar_perfil'))

    if request.method == 'POST': #por ejemplo, aqui, si el metodo es POST, haremos todo esto en el login
        dni = request.form['dni']
        password = request.form['password']
        
        # Validar el usuario contra la base de datos
        query = "SELECT id_usuario, nombre FROM usuarios WHERE dni = %s AND pass = %s AND activo = 1"
        values = dni, password
        result = ejecutar_sql(query, values)
        
        if result: #meter en session (donde se guardan los datos)
            session['dni'] = dni
            session['nombre'] = result[0][1]  # Suponiendo que el nombre está en la segunda columna del resultado
            session['id_usuario'] = result[0][0]  # Suponiendo que el id_usuario está en la primera columna del resultado
            id_usuario = session['id_usuario']  # ID del usuario autenticado

            # Consulta para obtener el instituto asociado al usuario
            query_instituto_usuario = """
                SELECT id_instituto
                FROM instituto_usuario
                WHERE id_usuario = %s
            """
            id_instituto = ejecutar_sql(query_instituto_usuario, (id_usuario,))[0][0]

            # Guardar el ID de la institución en la sesión
            session['id_instituto'] = id_instituto
            
            return redirect(url_for('seleccionar_perfil'))
        else:
            flash('DNI o contraseña incorrectos', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')

# Decorador personalizado para restringir el acceso a ciertas funciones según el perfil del usuario.
# Acepta una lista de perfiles permitidos, y si el perfil del usuario no está en esa lista, redirige a la página de inicio.
def perfil_requerido(perfiles_permitidos):
    def decorador(f):
        # Preserva la información original de la función 'f' para que el decorador no afecte su nombre o documentación.
        @wraps(f)
        def funcion_verificada(*args, **kwargs):
            # Verifica si el usuario ha seleccionado un perfil en la sesión.
            if 'perfil' not in session:
                # Si el perfil no está en la sesión, redirige al usuario a la página de selección de perfil.
                return redirect(url_for('seleccionar_perfil'))
            
            # Verifica si el perfil del usuario está en la lista de perfiles permitidos.
            if session['perfil'] not in perfiles_permitidos:
                # Si el perfil no está en la lista de permitidos, redirige al usuario a la página de inicio.
                return redirect(url_for('home'))
            
            # Si el perfil está permitido, se ejecuta la función original.
            return f(*args, **kwargs)
        
        # Retorna la función verificada que será ejecutada en lugar de la original.
        return funcion_verificada

    # Retorna el decorador configurado con los perfiles permitidos.
    return decorador

@app.route('/seleccionar_perfil', methods=['GET', 'POST'])
def seleccionar_perfil():
    if 'nombre' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Obtener el perfil seleccionado desde el formulario
        perfil_id = request.form.get('seleccionar_perfil')

        session['perfil'] = perfil_id  # Guarda el perfil en la sesión
        return redirect(url_for('home'))

    # Obtener los perfiles para la selección
    id_usuario = session['id_usuario']
    query_perfil = """
        SELECT perfiles_usuarios.id_perfil, perfiles.nombre
        FROM perfiles_usuarios 
        INNER JOIN perfiles ON perfiles_usuarios.id_perfil = perfiles.id_perfil 
        WHERE perfiles_usuarios.id_usuarios = %s
    """
    perfiles = ejecutar_sql(query_perfil, (id_usuario,))


    # Verificar si la consulta devolvió resultados
    if perfiles is None:
        return "Error al obtener los perfiles o no se encontraron perfiles asociados.", 500

    # Convertir los resultados a una lista de tuplas
    perfiles = [(perfil[0], perfil[1]) for perfil in perfiles]

    session['perfiles'] = perfiles
    
    return render_template('seleccionar_perfil.html', nombre=session['nombre'], perfiles=perfiles)

# Función para inyectar datos específicos en el contexto de la plantilla, permitiendo que las plantillas 
# tengan acceso a datos sobre permisos de usuario para mostrar u ocultar elementos de la barra de navegación (navbar.html).
@app.context_processor
def inject_navbar_data():
    # Obtener el ID del usuario desde la sesión
    id_usuario = session.get('id_usuario')

    # Verifica si el usuario ha iniciado sesión (si id_usuario existe en la sesión)
    if id_usuario:
        # Obtiene el perfil seleccionado por el usuario desde la sesión
        perfil_seleccionado = session.get('perfil')

        # Consulta SQL para obtener los permisos asociados al perfil seleccionado
        query_perfil = """
            SELECT id_permisos FROM permisos_perfiles WHERE id_perfil = %s
        """
        # Ejecuta la consulta para obtener los permisos del perfil
        permisos = ejecutar_sql(query_perfil, (perfil_seleccionado,))

        # Convierte los permisos obtenidos en una lista simple de IDs
        permisos = [permiso[0] for permiso in permisos]

    else:
        # Si no hay usuario en la sesión, asigna una lista vacía de permisos
        permisos = []

    # Devuelve un diccionario con la lista de permisos que estará disponible en el contexto de las plantillas
    return dict(permisos=permisos)


@app.route('/dashboard_alumno')
def dashboard_alumno():
    # Verificar si el usuario está autenticado y si es administrador
    if 'nombre' in session:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/dashboard_admin')
def dashboard_admin():
    # Verificar si el usuario está autenticado y si es administrador
    if 'nombre' in session:
        return redirect(url_for('home'))
    return redirect(url_for('login'))


# esta funcion y ruta crea una tabla con un filtro de busqueda y un boton para activos e inactivos
# tanto para alumnos como para pre-inscriptos, estos ultimos si los editas podras darlos de alta mas adelante
@app.route('/alumnos', methods=['GET'])
def alumnos():
    if 'nombre' not in session:
        return redirect(url_for('login'))

    # Obtener el nombre de búsqueda, número de página, estado activo y tabla seleccionada
    nombre_busqueda = request.args.get('nombre', '').strip()  # Nombre a buscar
    estado_activo = request.args.get('activo', 'todos')  # Estado activo: 'todos', 'activos' o 'inactivos'
    page = request.args.get('page', 1, type=int)
    table = request.args.get('table', 'alumnos')
    per_page = 5
    offset = (page - 1) * per_page

    # Construir condiciones de búsqueda y filtro
    nombre_filter = f"%{nombre_busqueda}%"
    activo_filter = None if estado_activo == 'todos' else ('1' if estado_activo == 'activos' else '0')

    if table == 'alumnos':
        # Consulta de alumnos con filtro de nombre y estado
        query_alumnos = """
            SELECT u.id_usuario, u.dni, u.nombre, l.nombre AS localidad, u.telefono
            FROM usuarios u
            LEFT JOIN localidades l ON u.id_localidad = l.id_localidad
            WHERE u.nombre LIKE %s
        """
        params = [nombre_filter]

        if activo_filter is not None:
            query_alumnos += " AND u.activo = %s"
            params.append(activo_filter)

        query_alumnos += " ORDER BY u.id_usuario LIMIT %s OFFSET %s"
        params.extend([per_page, offset])

        alumnos = ejecutar_sql(query_alumnos, tuple(params))

        # Contar el total de alumnos según el filtro de búsqueda y estado
        query_total_alumnos = "SELECT COUNT(*) FROM usuarios WHERE nombre LIKE %s"
        total_params = [nombre_filter]

        if activo_filter is not None:
            query_total_alumnos += " AND activo = %s"
            total_params.append(activo_filter)

        total_alumnos = ejecutar_sql(query_total_alumnos, tuple(total_params))[0][0]
        total_paginas_alumnos = (total_alumnos + per_page - 1) // per_page

        return render_template(
            'alumnos.html', 
            alumnos=alumnos,
            pre_inscripciones=[],
            page=page,
            table='alumnos',
            nombre_busqueda=nombre_busqueda,
            estado_activo=estado_activo,
            total_paginas_alumnos=total_paginas_alumnos,
            total_paginas_pre_inscripciones=None
        )

    elif table == 'pre_inscripciones':
        # Consulta de pre-inscripciones con filtro de nombre y estado
        query_pre_inscripciones = """
            SELECT u.id_usuario, u.dni, u.nombre, l.nombre AS localidad, u.telefono
            FROM pre_inscripciones u
            LEFT JOIN localidades l ON u.id_localidad = l.id_localidad
            WHERE u.nombre LIKE %s
        """
        params = [nombre_filter]

        if activo_filter is not None:
            query_pre_inscripciones += " AND u.activo = %s"
            params.append(activo_filter)

        query_pre_inscripciones += " ORDER BY u.id_usuario LIMIT %s OFFSET %s"
        params.extend([per_page, offset])

        pre_inscripciones = ejecutar_sql(query_pre_inscripciones, tuple(params))

        # Contar el total de pre-inscripciones según el filtro de búsqueda y estado
        query_total_pre_inscripciones = "SELECT COUNT(*) FROM pre_inscripciones WHERE nombre LIKE %s"
        total_params = [nombre_filter]

        if activo_filter is not None:
            query_total_pre_inscripciones += " AND activo = %s"
            total_params.append(activo_filter)

        total_pre_inscripciones = ejecutar_sql(query_total_pre_inscripciones, tuple(total_params))[0][0]
        total_paginas_pre_inscripciones = (total_pre_inscripciones + per_page - 1) // per_page

        return render_template(
            'alumnos.html',
            alumnos=[],
            pre_inscripciones=pre_inscripciones,
            page=page,
            table='pre_inscripciones',
            nombre_busqueda=nombre_busqueda,
            estado_activo=estado_activo,
            total_paginas_alumnos=None,
            total_paginas_pre_inscripciones=total_paginas_pre_inscripciones
        )


# aqui entraremos cuando seleccionamos un usuario, primero hara un get para tomar todos sus datos y 
# mostrarlos de la manera que queremos, despues, si cambiamos algo, hara un post para generar un update en la tabla usuarios
@app.route('/alumno/<int:id_usuario>', methods=['GET', 'POST'])
@perfil_requerido(['1', '2'])  # Solo perfiles 1 (directivo) y 2 (preseptor) pueden acceder
def editar_alumno(id_usuario):
    if 'nombre' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Recibir datos actualizados desde el formulario y actualizar en la base de datos
        datos = request.form.to_dict()

        # Convertir los campos a enteros, si es necesario
        datos['id_localidad'] = int(datos['id_localidad']) if datos['id_localidad'].isdigit() else None
        datos['id_pais'] = int(datos['id_pais']) if datos['id_pais'].isdigit() else None
        datos['id_provincia'] = int(datos['id_provincia']) if datos['id_provincia'].isdigit() else None
        datos['carrera'] = int(datos['carrera']) if datos['carrera'].isdigit() else None
        datos['turno'] = int(datos['turno']) if datos['turno'].isdigit() else None

        # Normalizar campos que pueden ser nulos
        datos['lugar_nacimiento'] = datos.get('lugar_nacimiento') or None
        datos['telefono_alt'] = datos.get('telefono_alt') or None
        datos['telefono_alt_propietario'] = datos.get('telefono_alt_propietario') or None
        datos['titulo_base'] = datos.get('titulo_base') or None
        datos['anio_egreso_otros'] = datos.get('anio_egreso_otros') or None
        datos['actividad'] = datos.get('actividad') or None
        datos['horario_habitual'] = datos.get('horario_habitual') or None
        datos['obra_social'] = datos.get('obra_social') or None
        datos['piso'] = datos.get('piso') if datos.get('piso') and datos['piso'] != 'NULL' else None

        # Consulta para actualizar los datos del alumno en usuarios
        query_update = """
            UPDATE usuarios SET 
                dni = %s, nombre = %s, apellido = %s, id_sexo = %s, fecha_nacimiento = %s, lugar_nacimiento = %s, 
                id_estado_civil = %s, cantidad_hijos = %s, familiares_a_cargo = %s, domicilio = %s, 
                piso = %s, id_localidad = %s, id_pais = %s, id_provincia = %s, codigo_postal = %s, 
                telefono = %s, telefono_alt = %s, telefono_alt_propietario = %s, email = %s, 
                titulo_base = %s, anio_egreso = %s, id_institucion = %s, otros_estudios = %s, 
                anio_egreso_otros = %s, trabaja = %s, actividad = %s, horario_habitual = %s, 
                obra_social = %s
            WHERE id_usuario = %s
        """
        ejecutar_sql(query_update, (
            datos['dni'], datos['nombre'], datos['apellido'], datos['id_sexo'], datos['fecha_nacimiento'], datos['lugar_nacimiento'],
            datos['id_estado_civil'], datos['cantidad_hijos'], datos['familiares_a_cargo'], datos['domicilio'],
            datos['piso'], datos['id_localidad'], datos['id_pais'], datos['id_provincia'], datos['codigo_postal'],
            datos['telefono'], datos['telefono_alt'], datos['telefono_alt_propietario'], datos['email'],
            datos['titulo_base'], datos['anio_egreso'], datos['id_institucion'], datos['otros_estudios'],
            datos['anio_egreso_otros'], datos['trabaja'], datos['actividad'], datos['horario_habitual'],
            datos['obra_social'], id_usuario
        ))

        # Obtener la inscripción actual
        query_inscripcion = """
            SELECT id_carrera, turno FROM inscripciones_carreras WHERE id_usuario = %s AND activo = 1
        """
        inscripcion_actual = ejecutar_sql(query_inscripcion, (id_usuario,))

        # Actualizar la carrera y el turno en inscripciones_carreras y cambiar estado_alumno a 2
        query_update_inscripcion = """
            UPDATE inscripciones_carreras SET 
                id_carrera = %s, turno = %s, estado_alumno = 'inscripto', fecha_inscripcion = %s
            WHERE id_usuario = %s AND activo = 1
        """
        ejecutar_sql(query_update_inscripcion, (
            datos['carrera'], datos['turno'], date.today(), id_usuario
        ))

        return redirect(url_for('alumnos'))

    # Si es GET, obtener los datos del alumno y preparar el formulario
    query_ingresante = "SELECT * FROM usuarios WHERE id_usuario = %s"
    ingresante = ejecutar_sql(query_ingresante, (id_usuario,))[0]


    # Obtener carrera y turno actuales del alumno en inscripciones_carreras
    query_carrera_turno = """
        SELECT id_carrera, turno FROM inscripciones_carreras WHERE id_usuario = %s AND activo = 1
    """
    resultado = ejecutar_sql(query_carrera_turno, (id_usuario,))
    alumno_carrera_id = resultado[0][0] if resultado else None
    alumno_turno = resultado[0][1] if resultado else None  # `id_turno` en vez de la descripción
    print (alumno_carrera_id)
    print (alumno_turno)

    # Obtener los países
    query_paises = "SELECT id_pais, nombre FROM paises"
    paises = ejecutar_sql(query_paises)

    # Obtener las provincias
    query_provincias = "SELECT id_provincia, nombre, id_pais FROM provincias"
    provincias = ejecutar_sql(query_provincias)

    # Obtener las localidades
    query_localidades = "SELECT id_localidad, nombre, id_provincia FROM localidades"
    localidades = ejecutar_sql(query_localidades)

    # Obtener las carreras y turnos
    query_carreras = "SELECT id_carrera, nombre FROM lista_carreras WHERE estado = 1"
    lista_carreras = ejecutar_sql(query_carreras)

 # Obtener los turnos asociados a las carreras
    query_turnos = """
        SELECT id_turno, id_carrera, descripcion FROM turno_carrera WHERE estado = 1
    """
    turnos_carreras = ejecutar_sql(query_turnos)
    turnos_carreras = [{"id_turno": turno[0], "id_carrera": turno[1], "descripcion": turno[2]} for turno in turnos_carreras]
    # Determina si el alumno está activo o inactivo basado en el valor de alumno[30]
    estado_actual = "Activo" if ingresante[30] == 1 else "Inactivo"

    return render_template(
        'editar_alumno.html',
        alumno=ingresante,
        paises=paises,
        provincias=provincias,
        localidades=localidades,
        lista_carreras=lista_carreras,
        turnos_carreras=turnos_carreras,
        alumno_carrera_id=alumno_carrera_id,
        alumno_turno=alumno_turno,
        estado_actual=estado_actual  # Enviar el estado como texto
    )


@app.route('/alumno/<int:id_usuario>/borrar', methods=['POST']) #alternar entre activo o inactivo, no los borra
@perfil_requerido(['1', '2'])  # Solo perfiles 1 (directivo) y 2 (preseptor) pueden acceder
def borrar_alumno(id_usuario):
    if 'nombre' not in session:
        return redirect(url_for('login'))

    # Consulta para alternar el valor de 'activo' entre 0 y 1
    query_toggle_activo = """
        UPDATE usuarios
        SET activo = CASE
            WHEN activo = 1 THEN 0
            ELSE 1
        END
        WHERE id_usuario = %s
    """
    ejecutar_sql(query_toggle_activo, (id_usuario,))

    return redirect(url_for('alumnos'))

#esta funcion toma todos los formularios llenados con datos de posibles estudiantes y si son correctos darlos de alta
#lo mismo que hace con alumnos pero cuando hacemos un POST, sera para darlos de alta y poder llevarlos con un insert usuarios
@app.route('/ingresante/<int:id_usuario>', methods=['GET', 'POST'])
@perfil_requerido(['1', '2'])  # Solo perfiles 1 (directivo) y 2 (preseptor) pueden acceder
def editar_ingresante(id_usuario):
    if 'nombre' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Recibir datos actualizados desde el formulario
        datos = request.form.to_dict()

        # Normalizar campos que pueden ser nulos
        datos['id_localidad'] = int(datos['id_localidad']) if datos['id_localidad'].isdigit() else None
        datos['id_pais'] = int(datos['id_pais']) if datos['id_pais'].isdigit() else None
        datos['id_provincia'] = int(datos['id_provincia']) if datos['id_provincia'].isdigit() else None
        datos['carrera'] = int(datos['carrera']) if datos['carrera'].isdigit() else None
        datos['turno'] = int(datos['turno']) if datos['turno'].isdigit() else None
        datos['lugar_nacimiento'] = datos.get('lugar_nacimiento') or None
        datos['telefono_alt'] = datos.get('telefono_alt') or None
        datos['telefono_alt_propietario'] = datos.get('telefono_alt_propietario') or None
        datos['titulo_base'] = datos.get('titulo_base') or None
        datos['anio_egreso_otros'] = datos.get('anio_egreso_otros') or None
        datos['actividad'] = datos.get('actividad') or None
        datos['horario_habitual'] = datos.get('horario_habitual') or None
        datos['obra_social'] = datos.get('obra_social') or None
        datos['piso'] = datos.get('piso') if datos.get('piso') and datos['piso'] != 'NULL' else None

        # Insertar en usuarios
        query_insert_usuario = """
            INSERT INTO usuarios (
                dni, nombre, apellido, id_sexo, fecha_nacimiento, lugar_nacimiento, id_estado_civil,
                cantidad_hijos, familiares_a_cargo, domicilio, piso, id_localidad, id_pais, id_provincia,
                codigo_postal, telefono, telefono_alt, telefono_alt_propietario, email, titulo_base,
                anio_egreso, id_institucion, otros_estudios, anio_egreso_otros, trabaja, actividad,
                horario_habitual, obra_social, pass, activo
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values_usuario = (
            datos['dni'], datos['nombre'], datos['apellido'], datos['id_sexo'], datos['fecha_nacimiento'],
            datos['lugar_nacimiento'], datos['id_estado_civil'], datos['cantidad_hijos'], datos['familiares_a_cargo'],
            datos['domicilio'], datos['piso'], datos['id_localidad'], datos['id_pais'], datos['id_provincia'],
            datos['codigo_postal'], datos['telefono'], datos['telefono_alt'], datos['telefono_alt_propietario'],
            datos['email'], datos['titulo_base'], datos['anio_egreso'], datos['id_institucion'], datos['otros_estudios'],
            datos['anio_egreso_otros'], datos['trabaja'], datos['actividad'], datos['horario_habitual'], datos['obra_social'],
            datos['pass'], 1  # activo = 1
        )
        ejecutar_sql(query_insert_usuario, values_usuario)


        query_select_id = "SELECT id_usuario FROM usuarios WHERE dni = %s"
        id_usuario_inscripcion = ejecutar_sql(query_select_id, (datos['dni'],))[0][0]

        # Actualizar la carrera y el turno en inscripciones_carreras con el nuevo id_usuario
        query_insert_inscripcion = """
            INSERT INTO inscripciones_carreras (
                id_usuario, id_carrera, fecha_inscripcion, turno, estado_alumno, activo
            ) VALUES (%s, %s, %s, %s, 'inscripto', %s)
        """
        values_inscripcion = (
            id_usuario_inscripcion, datos['carrera'], date.today(), datos['turno'], 1  # estado_alumno = 2, activo = 1
        )
        ejecutar_sql(query_insert_inscripcion, values_inscripcion)

        # consulta para insertar el perfil de alumno y el id_usuario en perfiles usuarios
        query_ingresar_perfil = """
            INSERT INTO perfiles_usuarios (
                id_perfil, id_usuarios
            ) VALUES (%s, %s)
        """
        # 4 = alumno y buscamos el id del usuario nuevo
        values_ingresar_perfil = (
            4, id_usuario_inscripcion
        )
        ejecutar_sql(query_ingresar_perfil,values_ingresar_perfil)

        # consulta para insertar el id del instituto actual y el id_usuario en instituto usuario
        query_ingresar_instituto = """
            INSERT INTO instituto_usuario (
                id_instituto, id_usuario
            ) VALUES (%s, %s)
        """
        # Buscar el id_instituto correspondiente al usuario
        query_sesion = """
            SELECT id_institucion FROM usuarios WHERE id_usuario = %s
        """
        # Ejecutar la consulta y obtener el resultado
        instituto = ejecutar_sql(query_sesion, (id_usuario_inscripcion,))

        # Acceder al valor de id_institucion si existe en el resultado
        id_instituto = instituto[0][0]

        # metemos en el value los datos
        print (instituto)
        values_ingresar_instituto = (
            id_instituto, id_usuario_inscripcion
        )
        ejecutar_sql(query_ingresar_instituto,values_ingresar_instituto)


        # Consulta para eliminar al ingresante de la base de datos
        query_borrar = "DELETE FROM pre_inscripciones WHERE id_usuario = %s"
        ejecutar_sql(query_borrar, (id_usuario,))

        return redirect(url_for('alumnos'))

    # Si es GET, obtener los datos del ingresante desde pre_inscripciones y prepararlos para el formulario
    query_ingresante = "SELECT * FROM pre_inscripciones WHERE id_usuario = %s"
    ingresante = ejecutar_sql(query_ingresante, (id_usuario,))[0]

    # Obtener carrera y turno actuales en inscripciones_carreras
    query_carrera_turno = """
        SELECT id_carrera, turno FROM inscripciones_carreras WHERE id_usuario = %s AND activo = 1
    """
    resultado = ejecutar_sql(query_carrera_turno, (id_usuario,))
    alumno_carrera_id = resultado[0][0] if resultado else None
    alumno_turno = resultado[0][1] if resultado else None

    # Obtener los países, provincias, localidades, carreras y turnos
    query_paises = "SELECT id_pais, nombre FROM paises"
    query_provincias = "SELECT id_provincia, nombre, id_pais FROM provincias"
    query_localidades = "SELECT id_localidad, nombre, id_provincia FROM localidades"
    query_carreras = "SELECT id_carrera, nombre FROM lista_carreras WHERE estado = 1"
    query_turnos = "SELECT id_turno, id_carrera, descripcion FROM turno_carrera WHERE estado = 1"

    paises = ejecutar_sql(query_paises)
    provincias = ejecutar_sql(query_provincias)
    localidades = ejecutar_sql(query_localidades)
    lista_carreras = ejecutar_sql(query_carreras)
    turnos_carreras = [{"id_turno": turno[0], "id_carrera": turno[1], "descripcion": turno[2]} for turno in ejecutar_sql(query_turnos)]

    return render_template(
        'editar_ingresante.html',
        alumno=ingresante,
        paises=paises,
        provincias=provincias,
        localidades=localidades,
        lista_carreras=lista_carreras,
        turnos_carreras=turnos_carreras,
        alumno_carrera_id=alumno_carrera_id,
        alumno_turno=alumno_turno
    )

# Cursos por carrera
@app.route("/carreras/<int:id_carrera>/cursos")
def cursos_por_carrera(id_carrera):
    # Traer datos de la carrera
    carrera = ejecutar_sql("""
        SELECT id_carrera, nombre, descripcion, tipo, año, ley, fecha, activo
        FROM carreras
        WHERE id_carrera = %s
    """, (id_carrera,))
    if carrera and isinstance(carrera, list):
        carrera = carrera[0]
    else:
        flash("Carrera no encontrada", "danger")
        return redirect(url_for("carreras"))

    # --- Filtros y paginación ---
    nombre_busqueda = request.args.get("nombre", "")
    estado_activo = request.args.get("activo", "activos")
    page = int(request.args.get("page", 1))
    por_pagina = 5
    offset = (page - 1) * por_pagina

    query_base = "FROM cursos WHERE id_carrera = %s"
    values = [id_carrera]

    if nombre_busqueda:
        query_base += " AND nombre LIKE %s"
        values.append(f"%{nombre_busqueda}%")

    if estado_activo == "activos":
        query_base += " AND activo = 1"
    elif estado_activo == "inactivos":
        query_base += " AND activo = 0"

    # Total de cursos
    total = ejecutar_sql(f"SELECT COUNT(*) {query_base}", tuple(values))[0][0]
    total_paginas = math.ceil(total / por_pagina)

    # Cursos paginados
    cursos = ejecutar_sql(f"""
        SELECT id_curso, nombre, año_calendario, activo
        {query_base}
        ORDER BY id_curso ASC
        LIMIT %s OFFSET %s
    """, tuple(values + [por_pagina, offset])) or []

    return render_template(
        "cursos_por_carrera.html",
        carrera=carrera,
        cursos=cursos,
        nombre_busqueda=nombre_busqueda,
        estado_activo=estado_activo,
        page=page,
        total_paginas=total_paginas
    )

# Agregar curso (versión completa y estable)
@app.route("/carreras/<int:id_carrera>/cursos/nuevo", methods=["POST"])
def crear_curso_por_carrera(id_carrera):
    if 'nombre' not in session:
        return redirect(url_for('login'))

    nombre = request.form.get("nombre")
    año_calendario = request.form.get("año_calendario")
    activo = 1  # Siempre activo por defecto

    # Validación básica
    if not nombre or not año_calendario:
        flash("Faltan datos obligatorios para crear el curso.", "danger")
        return redirect(f"/carreras/{id_carrera}/cursos")

    # Inserción segura
    query_insert = """
        INSERT INTO cursos (id_carrera, nombre, año_calendario, activo)
        VALUES (%s, %s, %s, %s)
    """
    values = (id_carrera, nombre, año_calendario, activo)
    ejecutar_sql(query_insert, values)

    flash("Curso agregado correctamente.", "success")
    return redirect(f"/carreras/{id_carrera}/cursos")

@app.route("/carreras")
def carreras():
    if 'nombre' not in session:
        return redirect(url_for('login'))

    page = int(request.args.get("page", 1))
    nombre_busqueda = request.args.get("nombre", "")
    estado_activo = request.args.get("activo", "activos")
    turno_seleccionado = request.args.get("turno", "")
    anio_actual = date.today().year
    anio_seleccionado = int(request.args.get("anio", anio_actual))

    # 🔹 Obtener todos los años disponibles (pasados, actuales, futuros)
    años_disponibles_result = ejecutar_sql("""
        SELECT DISTINCT año
        FROM carreras
        WHERE año IS NOT NULL
        ORDER BY año DESC
    """) or []

    años_disponibles = [fila[0] for fila in años_disponibles_result]

    query = """
        SELECT 
            id_carrera,
            nombre,
            descripcion,
            tipo,
            año,
            ley,
            fecha,
            activo,
            turno
        FROM carreras
        WHERE 1=1
    """
    valores = []

    # --- Filtro por nombre ---
    if nombre_busqueda:
        query += " AND nombre LIKE %s"
        valores.append(f"%{nombre_busqueda}%")

    # --- Filtro por estado ---
    if estado_activo == "activos":
        query += " AND activo = 1"
    elif estado_activo == "inactivos":
        query += " AND activo = 0"

    # --- Filtro por turno ---
    if turno_seleccionado:
        query += " AND turno = %s"
        valores.append(turno_seleccionado)

    # --- Filtro por año ---
    if anio_seleccionado:
        query += " AND año = %s"
        valores.append(anio_seleccionado)

    query += " ORDER BY id_carrera DESC"

    carreras = ejecutar_sql(query, valores) or []
    print("✅ Carreras encontradas:", carreras)

    total_paginas_carreras = 1

    return render_template(
        "carreras.html",
        carreras=carreras,
        page=page,
        total_paginas_carreras=total_paginas_carreras,
        estado_activo=estado_activo,
        nombre_busqueda=nombre_busqueda,
        turno_seleccionado=turno_seleccionado,
        anio_actual=anio_actual,
        anio_seleccionado=anio_seleccionado,
        años_disponibles=años_disponibles
    )

@app.route("/agregar_carrera", methods=["POST"])
def agregar_carrera():
    if 'nombre' not in session:
        return redirect(url_for('login'))

    # --- Obtener datos del formulario ---
    nombre = request.form.get("nombre", "").strip()
    descripcion = request.form.get("descripcion", "").strip()
    tipo = request.form.get("tipo", "").strip()
    año = request.form.get("año", "").strip()
    turno = request.form.get("turno", "").strip()  # ✅ ahora lo capturamos
    ley = request.form.get("ley", "").strip()
    fecha = request.form.get("fecha_creacion") or date.today().strftime("%Y-%m-%d")

    # --- Validaciones ---
    if not nombre or not descripcion or not tipo or not año or not turno or not ley:
        flash("Todos los campos obligatorios deben completarse.", "danger")
        return redirect(url_for("carreras"))

    # --- Validar duplicado ---
    query_existente = "SELECT id_carrera FROM carreras WHERE LOWER(nombre) = LOWER(%s)"
    existe = ejecutar_sql(query_existente, [nombre])
    if existe:
        flash(f"Ya existe una carrera registrada con el nombre '{nombre}'.", "danger")
        return redirect(url_for("carreras"))

    # --- Insertar la carrera con el turno ---
    query_insert = """
        INSERT INTO carreras (nombre, descripcion, tipo, año, ley, fecha, activo, turno)
        VALUES (%s, %s, %s, %s, %s, %s, 1, %s)
    """
    values = (nombre, descripcion, tipo, año, ley, fecha, turno)

    try:
        ejecutar_sql(query_insert, values)
    except Exception as e:
        flash(f"Error al crear la carrera: {e}", "danger")
        return redirect(url_for("carreras"))

    # --- Obtener ID recién creada ---
    result = ejecutar_sql("""
        SELECT id_carrera
        FROM carreras
        WHERE nombre = %s AND tipo = %s AND año = %s
        ORDER BY id_carrera DESC
        LIMIT 1
    """, (nombre, tipo, año))
    id_carrera = result[0][0] if result else None

    if not id_carrera:
        flash("No se pudo obtener el ID de la carrera creada.", "danger")
        return redirect(url_for("carreras"))

    # --- Crear cursos automáticos según tipo ---
    cursos_a_crear = []
    if tipo.lower() == "tecnicatura":
        cursos_a_crear = ["Primero", "Segundo", "Tercero"]
    elif tipo.lower() == "profesorado":
        cursos_a_crear = ["Primero", "Segundo", "Tercero", "Cuarto"]

    try:
        for curso_nombre in cursos_a_crear:
            ejecutar_sql("""
                INSERT INTO cursos (id_carrera, nombre, año_calendario, activo)
                VALUES (%s, %s, %s, 1)
            """, (id_carrera, curso_nombre, año))
    except Exception as e:
        flash(f"Error al crear los cursos automáticos: {e}", "danger")
        return redirect(url_for("carreras"))

    flash(f"Carrera '{nombre}' agregada correctamente con {len(cursos_a_crear)} curso(s).", "success")
    return redirect(url_for("carreras"))

@app.route("/editar_carrera", methods=["POST"])
def editar_carrera():
    id_carrera = request.form.get("id_carrera")
    nombre = request.form.get("nombre")
    descripcion = request.form.get("descripcion")
    tipo = request.form.get("tipo")
    año = request.form.get("año")
    turno = request.form.get("turno")  # 👈 nuevo
    fecha = request.form.get("fecha")  # 👈 ahora editable, no se pisa con date.today()
    ley_file = request.form.get("ley")
    activo = int(request.form.get("activo", 1))

    # --- Validaciones básicas ---
    if not id_carrera:
        flash("No se encontró la carrera seleccionada", "error")
        return redirect(url_for("carreras"))

    if not nombre:
        flash("El nombre es obligatorio", "error")
        return redirect(url_for("carreras"))

    if not re.match(r'^[A-Za-zÁÉÍÓÚáéíóúÑñ]+(?:\s[A-Za-zÁÉÍÓÚáéíóúÑñ]+)*$', nombre):
        flash("El nombre solo puede contener letras y un solo espacio entre palabras.", "error")
        return redirect(url_for("carreras"))

    if not descripcion:
        flash("La descripción es obligatoria", "error")
        return redirect(url_for("carreras"))

    if not año:
        flash("El año es obligatorio", "error")
        return redirect(url_for("carreras"))

    if not tipo:
        flash("El tipo es obligatorio", "error")
        return redirect(url_for("carreras"))

    if not turno:
        flash("El turno es obligatorio", "error")
        return redirect(url_for("carreras"))
    
    if not ley_file:
        flash("La ley es obligatoria", "error")
        return redirect(url_for("carreras"))

    # ✅ Validar duplicado (excepto el mismo id)
    query_existente = """
        SELECT id_carrera FROM carreras 
        WHERE LOWER(nombre) = LOWER(%s) AND id_carrera != %s
    """
    existe = ejecutar_sql(query_existente, [nombre, id_carrera])
    if existe and len(existe) > 0:
        flash(f"Ya existe otra carrera con el nombre '{nombre}'.", "danger")
        return redirect(url_for("carreras"))

    # --- Obtener tipo anterior ---
    query_tipo_anterior = "SELECT tipo FROM carreras WHERE id_carrera = %s"
    result_tipo = ejecutar_sql(query_tipo_anterior, [id_carrera])
    tipo_anterior = result_tipo[0][0] if result_tipo and len(result_tipo) > 0 else None

    # --- Actualizar carrera ---
    query_carrera = """
        UPDATE carreras
        SET nombre=%s, descripcion=%s, tipo=%s, año=%s, turno=%s, fecha=%s, activo=%s, ley=%s
        WHERE id_carrera=%s
    """
    values_carrera = [nombre, descripcion, tipo, año, turno, fecha, activo, ley_file, id_carrera]
    ejecutar_sql(query_carrera, values_carrera)

    # --- Desactivar o reactivar cascada ---
    if activo == 0:
        ejecutar_sql("UPDATE cursos SET activo = 0 WHERE id_carrera = %s", [id_carrera])
        ejecutar_sql("""
            UPDATE materias
            SET activo = 0
            WHERE id_curso IN (SELECT id_curso FROM cursos WHERE id_carrera = %s)
        """, [id_carrera])
    elif activo == 1:
        ejecutar_sql("UPDATE cursos SET activo = 1 WHERE id_carrera = %s", [id_carrera])
        ejecutar_sql("""
            UPDATE materias
            SET activo = 1
            WHERE id_curso IN (SELECT id_curso FROM cursos WHERE id_carrera = %s)
        """, [id_carrera])

    # --- Lógica de sincronización de cursos si cambia el tipo ---
    if tipo_anterior and tipo_anterior.lower() != tipo.lower():
        query_cursos_actuales = "SELECT id_curso, nombre FROM cursos WHERE id_carrera = %s"
        cursos_actuales = ejecutar_sql(query_cursos_actuales, [id_carrera]) or []

        if tipo.lower() == "tecnicatura":
            cursos_nuevos = ["Primero", "Segundo", "Tercero"]
        elif tipo.lower() == "profesorado":
            cursos_nuevos = ["Primero", "Segundo", "Tercero", "Cuarto"]
        else:
            cursos_nuevos = []

        # Eliminar cursos no válidos (sin materias)
        for curso in cursos_actuales:
            id_curso, nombre_curso = curso
            if nombre_curso not in cursos_nuevos:
                query_materias = "SELECT COUNT(*) FROM materias WHERE id_curso = %s"
                tiene_materias = ejecutar_sql(query_materias, [id_curso])[0][0]
                if tiene_materias == 0:
                    ejecutar_sql("DELETE FROM cursos WHERE id_curso = %s", [id_curso])
                else:
                    flash(f"No se eliminó el curso '{nombre_curso}' porque tiene materias asociadas.", "warning")

        # Crear cursos faltantes
        nombres_existentes = [c[1] for c in cursos_actuales]
        for nombre_curso in cursos_nuevos:
            if nombre_curso not in nombres_existentes:
                query_insert_curso = """
                    INSERT INTO cursos (id_carrera, nombre, año_calendario, activo)
                    VALUES (%s, %s, %s, 1)
                """
                ejecutar_sql(query_insert_curso, [id_carrera, nombre_curso, año])

        flash("Los cursos se ajustaron automáticamente según el nuevo tipo de carrera.", "info")

    flash("Carrera actualizada correctamente", "success")
    return redirect(url_for("carreras"))

# Eliminar carrera
@app.route("/eliminar_carrera", methods=["POST"])
def eliminar_carrera():
    print("request", request.form)
    id_carrera = request.form.get("id_carrera")
    query = "DELETE FROM carreras WHERE id_carrera=%s"
    values = [id_carrera]
    print("Eliminando carrera:", id_carrera)
    ejecutar_sql(query, values)
    flash("Carrera eliminada correctamente.", "error")
    return redirect(url_for("carreras"))

# Listado de cursos
@app.route("/cursos")
def cursos():
    page = int(request.args.get("page", 1))
    nombre_busqueda = request.args.get("nombre", "")
    estado_activo = request.args.get("activo", "activos")
    

    # --- Traer cursos ---
    query = """
        SELECT 
            c.id_curso,
            c.nombre AS nombre_curso,
            c.año_calendario,
            c.activo,
            ca.nombre AS nombre_carrera
        FROM cursos c
        JOIN carreras ca ON c.id_carrera = ca.id_carrera
        WHERE 1=1
    """
    params = []
    if nombre_busqueda:
        query += " AND c.nombre LIKE %s"
        params.append(f"%{nombre_busqueda}%")
    if estado_activo == "activos":
        query += " AND c.activo = 1"
    elif estado_activo == "inactivos":
        query += " AND c.activo = 0"

    query += " ORDER BY c.id_curso DESC"
    cursos = ejecutar_sql(query, tuple(params)) or []

    # --- Traer carreras para el modal de cursos ---
    query_carreras = "SELECT id_carrera, nombre FROM carreras"
    carreras = ejecutar_sql(query_carreras) or []

    return render_template(
        "carreras.html",
        cursos=cursos,
        carreras=carreras,
        table="cursos",
        estado_activo=estado_activo
    )

@app.route("/agregar_curso", methods=["POST"])
def agregar_curso():
    if 'nombre' not in session:
        return redirect(url_for('login'))

    id_carrera = request.form.get("id_carrera")
    nombre = request.form.get("nombre", "").strip()
    año = request.form.get("año_calendario")
    activo = int(request.form.get("activo", 1))

    # --- Validaciones básicas ---
    if not id_carrera or not nombre or not año:
        flash("Todos los campos son obligatorios.", "danger")
        return redirect(url_for("cursos_por_carrera", id_carrera=id_carrera))

    # --- Validar duplicado ---
    query_existente = """
        SELECT id_curso FROM cursos
        WHERE LOWER(nombre) = LOWER(%s) AND id_carrera = %s
    """
    existente = ejecutar_sql(query_existente, [nombre, id_carrera])
    if existente and len(existente) > 0:
        flash(f"Ya existe un curso con el nombre '{nombre}' en esta carrera.", "danger")
        return redirect(url_for("cursos_por_carrera", id_carrera=id_carrera))

    # --- Insertar ---
    query_insert = """
        INSERT INTO cursos (id_carrera, nombre, año_calendario, activo)
        VALUES (%s, %s, %s, %s)
    """
    values = (id_carrera, nombre, año, activo)
    ejecutar_sql(query_insert, values)

    flash("Curso agregado correctamente.", "success")
    return redirect(url_for("cursos_por_carrera", id_carrera=id_carrera))

@app.route("/editar_curso", methods=["POST"])
def editar_curso():
    if 'nombre' not in session:
        return redirect(url_for('login'))

    id_curso = request.form.get("id_curso")
    id_carrera = request.form.get("id_carrera")
    nombre = request.form.get("nombre", "").strip()
    año_calendario = request.form.get("año_calendario")
    activo = int(request.form.get("activo", 1))

    # --- Validaciones ---
    if not id_curso or not id_carrera:
        flash("Datos insuficientes para editar el curso.", "danger")
        return redirect(url_for("carreras"))

    if not nombre:
        flash("El nombre del curso es obligatorio.", "danger")
        return redirect(url_for("cursos_por_carrera", id_carrera=id_carrera))

    # --- Validar que la carrera existe ---
    query_carrera = "SELECT activo FROM carreras WHERE id_carrera = %s"
    carrera = ejecutar_sql(query_carrera, [id_carrera])
    if not carrera:
        flash("La carrera asociada no existe.", "danger")
        return redirect(url_for("cursos_por_carrera", id_carrera=id_carrera))

    carrera_activa = carrera[0]["activo"] if isinstance(carrera[0], dict) else carrera[0][0]
    if activo == 1 and carrera_activa == 0:
        flash("No se puede activar un curso si la carrera asociada está desactivada. Active la carrera primero.", "danger")
        return redirect(url_for("cursos_por_carrera", id_carrera=id_carrera))

    # --- Validar nombre duplicado ---
    query_existente = """
        SELECT id_curso FROM cursos
        WHERE LOWER(nombre) = LOWER(%s) AND id_carrera = %s AND id_curso != %s
    """
    existente = ejecutar_sql(query_existente, [nombre, id_carrera, id_curso])
    if existente and len(existente) > 0:
        flash(f"Ya existe otro curso con el nombre '{nombre}' en esta carrera.", "danger")
        return redirect(url_for("cursos_por_carrera", id_carrera=id_carrera))

    # --- Actualizar ---
    query_update = """
        UPDATE cursos
        SET id_carrera=%s, nombre=%s, año_calendario=%s, activo=%s
        WHERE id_curso=%s
    """
    ejecutar_sql(query_update, [id_carrera, nombre, año_calendario, activo, id_curso])

    # --- Sincronizar materias ---
    if activo == 0:
        ejecutar_sql("UPDATE materias SET activo = 0 WHERE id_curso = %s", [id_curso])
    elif activo == 1:
        ejecutar_sql("UPDATE materias SET activo = 1 WHERE id_curso = %s", [id_curso])

    flash("Curso actualizado correctamente.", "success")
    return redirect(url_for("cursos_por_carrera", id_carrera=id_carrera))

# Eliminar curso
@app.route("/eliminar_curso", methods=["DELETE", "POST"])
def eliminar_curso():
    print("request curso", request.form)
    id_curso = request.form.get("id_curso")
    query = "DELETE FROM cursos WHERE id_curso=%s"
    values = [id_curso]
    print("Eliminando curso:", id_curso)
    ejecutar_sql(query, values)
    flash("Curso eliminado correctamente.", "error")
    return redirect(url_for("cursos"))

@app.route("/cursos/<int:id_curso>/materias")
def materias_por_curso(id_curso):
    # Traer info del curso
    curso = ejecutar_sql("SELECT id_curso, nombre, id_carrera FROM cursos WHERE id_curso = %s", [id_curso])
    if not curso:
        flash("Curso no encontrado", "danger")
        return redirect(url_for("carreras"))
    curso = curso[0]
    id_carrera = curso[2]

    # Traer info de la carrera asociada
    carrera = ejecutar_sql("SELECT id_carrera, nombre FROM carreras WHERE id_carrera = %s", [id_carrera])
    carrera = carrera[0] if carrera else ("", "")

    # --- Filtros y paginación ---
    nombre_busqueda = request.args.get("nombre", "")
    estado_activo = request.args.get("activo", "activos")
    page = int(request.args.get("page", 1))
    por_pagina = 5
    offset = (page - 1) * por_pagina

    # Base de consulta
    query_base = "FROM materias WHERE id_curso = %s"
    values = [id_curso]

    if nombre_busqueda:
        query_base += " AND nombre LIKE %s"
        values.append(f"%{nombre_busqueda}%")

    if estado_activo == "activos":
        query_base += " AND activo = 1"
    elif estado_activo == "inactivos":
        query_base += " AND activo = 0"

    # --- Total de materias ---
    total_result = ejecutar_sql(f"SELECT COUNT(*) {query_base}", tuple(values))
    total = total_result[0][0] if total_result else 0
    total_paginas = math.ceil(total / por_pagina) if total > 0 else 1

    # --- Consulta principal ---
    materias = ejecutar_sql(f"""
        SELECT id_materia, nombre, carga_horaria, activo, tipo_campo
        {query_base}
        ORDER BY id_materia ASC
        LIMIT %s OFFSET %s
    """, tuple(values + [por_pagina, offset])) or []

    # --- Calcular total de carga horaria ---
    total_horas_result = ejecutar_sql(f"SELECT SUM(carga_horaria) {query_base}", tuple(values))
    total_horas = total_horas_result[0][0] if total_horas_result and total_horas_result[0][0] else 0

    print("🔍 Materias encontradas:", materias)
    print("🕓 Total horas:", total_horas)

    return render_template(
        "materias_por_curso.html",
        curso=curso,
        carrera=carrera,
        materias=materias,
        nombre_busqueda=nombre_busqueda,
        estado_activo=estado_activo,
        page=page,
        total_paginas=total_paginas,
        total_horas=total_horas  # 👈 ahora lo enviamos al template
    )


@app.route("/materias")
def materias():
    if 'nombre' not in session:
        return redirect(url_for('login'))

    page = int(request.args.get("page", 1))
    nombre_busqueda = request.args.get("nombre", "")
    estado_activo = request.args.get("activo", "activos")

    # --- Traer materias con su curso y carrera ---
    query = """
        SELECT 
            m.id_materia,
            m.nombre AS nombre_materia,
            m.carga_horaria,
            m.activo,
            m.tipo_campo,
            c.id_curso,
            c.nombre AS nombre_curso,
            ca.id_carrera,
            ca.nombre AS nombre_carrera
        FROM materias AS m
        LEFT JOIN cursos AS c ON m.id_curso = c.id_curso
        LEFT JOIN carreras AS ca ON c.id_carrera = ca.id_carrera
        WHERE 1=1
    """

    valores = []

    if nombre_busqueda:
        query += " AND m.nombre LIKE %s"
        valores.append(f"%{nombre_busqueda}%")

    if estado_activo == "activos":
        query += " AND m.activo = 1"
    elif estado_activo == "inactivos":
        query += " AND m.activo = 0"

    query += " ORDER BY m.id_materia DESC"

    print("🔍 Consulta SQL Materias:", query)
    print("🔹 Valores:", valores)

    materias = ejecutar_sql(query, valores) or []
    print("✅ Materias encontradas:", materias)

    # --- Calcular la carga horaria total ---
    query_total_horas = """
        SELECT SUM(m.carga_horaria)
        FROM materias AS m
        LEFT JOIN cursos AS c ON m.id_curso = c.id_curso
        LEFT JOIN carreras AS ca ON c.id_carrera = ca.id_carrera
        WHERE 1=1
    """

    valores_total = []

    if nombre_busqueda:
        query_total_horas += " AND m.nombre LIKE %s"
        valores_total.append(f"%{nombre_busqueda}%")

    if estado_activo == "activos":
        query_total_horas += " AND m.activo = 1"
    elif estado_activo == "inactivos":
        query_total_horas += " AND m.activo = 0"

    total_horas_result = ejecutar_sql(query_total_horas, tuple(valores_total))
    total_horas = total_horas_result[0][0] if total_horas_result and total_horas_result[0][0] else 0

    # --- Traer carreras y cursos (para selects) ---
    carreras = ejecutar_sql("SELECT id_carrera, nombre FROM carreras") or []
    cursos = ejecutar_sql("SELECT id_curso, nombre FROM cursos") or []

    total_paginas_materias = 1  # Si no estás usando paginación real

    return render_template(
        "materias.html",
        cursos=cursos,
        carreras=carreras,
        materias=materias,
        table="materias",
        estado_activo=estado_activo,
        total_horas=total_horas  # 👈 pasamos el total
    )


@app.route("/agregar_materia", methods=["POST"])
def agregar_materia():
    if 'nombre' not in session:
        return redirect(url_for('login'))

    id_curso = request.form.get("id_curso")
    nombre = request.form.get("nombre", "").strip()
    carga_horaria = request.form.get("carga_horaria")
    tipo_campo = request.form.get("tipo_campo", "").strip()
    activo = int(request.form.get("activo", 1))

    # --- Validaciones básicas ---
    if not id_curso or not nombre or not carga_horaria or not tipo_campo:
        flash("Todos los campos son obligatorios.", "danger")
        return redirect(url_for("materias_por_curso", id_curso=id_curso))

    # 🔹 Validar carga horaria numérica y no negativa
    try:
        carga_horaria = int(carga_horaria)
        if carga_horaria <= 0:
            flash("La carga horaria debe ser un número positivo.", "danger")
            return redirect(url_for("materias_por_curso", id_curso=id_curso))
    except ValueError:
        flash("La carga horaria debe ser un número válido.", "danger")
        return redirect(url_for("materias_por_curso", id_curso=id_curso))

    # --- Validar si ya existe una materia con el mismo nombre en el curso ---
    query_existente = """
        SELECT id_materia FROM materias
        WHERE LOWER(nombre) = LOWER(%s) AND id_curso = %s
    """
    existente = ejecutar_sql(query_existente, [nombre, id_curso])
    if existente and len(existente) > 0:
        flash(f"Ya existe una materia con el nombre '{nombre}' en este curso.", "danger")
        return redirect(url_for("materias_por_curso", id_curso=id_curso))

    # --- Insertar materia ---
    query = """
        INSERT INTO materias (id_curso, nombre, carga_horaria, tipo_campo, activo)
        VALUES (%s, %s, %s, %s, %s)
    """
    values = (id_curso, nombre, carga_horaria, tipo_campo, activo)
    ejecutar_sql(query, values)

    flash("Materia agregada correctamente.", "success")
    return redirect(url_for("materias_por_curso", id_curso=id_curso))


# Editar materia
@app.route("/editar_materia", methods=["POST"])
def editar_materia():
    if 'nombre' not in session:
        return redirect(url_for('login'))

    id_materia = request.form.get("id_materia")
    id_curso = request.form.get("id_curso")
    nombre = request.form.get("nombre", "").strip()
    carga_horaria = request.form.get("carga_horaria")
    tipo_campo = request.form.get("tipo_campo", "").strip()
    activo = int(request.form.get("activo", 1))

    # --- Validaciones ---
    if not id_materia or not id_curso:
        flash("Faltan datos de la materia.", "danger")
        return redirect(url_for("materias_por_curso", id_curso=id_curso))
    if not nombre or not tipo_campo:
        flash("El nombre y el tipo de campo son obligatorios.", "danger")
        return redirect(url_for("materias_por_curso", id_curso=id_curso))

    # 🔹 Validar carga horaria numérica y no negativa
    try:
        carga_horaria = int(carga_horaria)
        if carga_horaria <= 0:
            flash("La carga horaria debe ser un número positivo.", "danger")
            return redirect(url_for("materias_por_curso", id_curso=id_curso))
    except ValueError:
        flash("La carga horaria debe ser un número válido.", "danger")
        return redirect(url_for("materias_por_curso", id_curso=id_curso))

    # --- Validar duplicado de nombre ---
    query_existente = """
        SELECT id_materia FROM materias
        WHERE LOWER(nombre) = LOWER(%s) AND id_curso = %s AND id_materia != %s
    """
    existente = ejecutar_sql(query_existente, [nombre, id_curso, id_materia])
    if existente and len(existente) > 0:
        flash(f"Ya existe otra materia con el nombre '{nombre}' en este curso.", "danger")
        return redirect(url_for("materias_por_curso", id_curso=id_curso))

    # --- Actualizar materia ---
    query = """
        UPDATE materias
        SET id_curso=%s, nombre=%s, carga_horaria=%s, tipo_campo=%s, activo=%s
        WHERE id_materia=%s
    """
    values = [id_curso, nombre, carga_horaria, tipo_campo, activo, id_materia]
    ejecutar_sql(query, values)

    flash("Materia actualizada correctamente.", "success")
    return redirect(url_for("materias_por_curso", id_curso=id_curso))

# Eliminar materia
@app.route("/eliminar_materia", methods=["POST"])
def eliminar_materia():
    if 'nombre' not in session:
        return redirect(url_for('login'))

    id_materia = request.form.get("id_materia")
    id_curso = request.form.get("id_curso")

    if not id_materia:
        flash("No se encontró la materia a eliminar.", "danger")
        return redirect(url_for("materias_por_curso", id_curso=id_curso))

    query = "DELETE FROM materias WHERE id_materia = %s"
    ejecutar_sql(query, [id_materia])

    flash("Materia eliminada correctamente.", "success")
    return redirect(url_for("materias_por_curso", id_curso=id_curso))


@app.route("/plan_de_estudio", methods=["GET"])
def plan_de_estudio():
    if 'nombre' not in session:
        return redirect(url_for('login'))

    # Obtener todas las carreras activas
    carreras = ejecutar_sql("SELECT id_carrera, nombre FROM carreras WHERE activo = 1 ORDER BY nombre ASC")

    # Parámetros seleccionados
    id_carrera = request.args.get("id_carrera")
    id_curso = request.args.get("id_curso")
    page = int(request.args.get("page", 1))
    por_pagina = 5
    offset = (page - 1) * por_pagina

    cursos = []
    materias = []
    total_paginas = 1
    total_horas = 0

    if id_carrera:
        # Obtener cursos activos de la carrera seleccionada
        cursos = ejecutar_sql(
            "SELECT id_curso, nombre FROM cursos WHERE id_carrera = %s AND activo = 1 ORDER BY nombre ASC",
            [id_carrera]
        )

    if id_carrera and id_curso:
        # --- Total de materias (para paginación) ---
        total_result = ejecutar_sql("SELECT COUNT(*) FROM materias WHERE id_curso = %s", [id_curso])
        total = total_result[0][0] if total_result else 0
        total_paginas = math.ceil(total / por_pagina) if total > 0 else 1

        # --- Obtener las materias paginadas ---
        materias = ejecutar_sql("""
            SELECT nombre, carga_horaria, activo
            FROM materias
            WHERE id_curso = %s
            ORDER BY nombre ASC
            LIMIT %s OFFSET %s
        """, (id_curso, por_pagina, offset)) or []

        # --- Calcular la carga horaria total ---
        total_horas_result = ejecutar_sql("""
            SELECT SUM(carga_horaria)
            FROM materias
            WHERE id_curso = %s
        """, [id_curso])
        total_horas = total_horas_result[0][0] if total_horas_result and total_horas_result[0][0] else 0

    return render_template(
        "plan_de_estudio.html",
        carreras=carreras,
        cursos=cursos,
        materias=materias,
        id_carrera=id_carrera,
        id_curso=id_curso,
        page=page,
        total_paginas=total_paginas,
        total_horas=total_horas  # 👈 lo enviamos al template
    )

# 📘 Endpoint para obtener cursos por carrera
@app.route("/get_cursos_por_carrera/<int:id_carrera>")
def get_cursos_por_carrera(id_carrera):
    cursos = ejecutar_sql(
        "SELECT id_curso, nombre FROM cursos WHERE id_carrera = %s AND activo = 1 ORDER BY nombre ASC",
        [id_carrera]
    )
    return jsonify(cursos)


@app.route('/ingresante/<int:id_usuario>/borrar', methods=['POST'])
@perfil_requerido(['1', '2'])  # Solo perfiles 1 (directivo) y 2 (preseptor) pueden acceder
def borrar_ingresante(id_usuario):
    if 'nombre' not in session:
        return redirect(url_for('login'))

    # Consulta para eliminar al ingresante de la base de datos
    query_borrar = "DELETE FROM pre_inscripciones WHERE id_usuario = %s"
    ejecutar_sql(query_borrar, (id_usuario,))
    
    return redirect(url_for('alumnos'))

    
@app.route('/profesores')
@perfil_requerido(['1', '2', '3'])  # Solo perfiles 1 (directivo) y 3 (profesor) pueden acceder
def profesores():
    if 'nombre' not in session:
        return redirect(url_for('login'))
    # Renderiza la página de gestión de profesores
    return render_template('profesores.html')

# @app.route('/carreras')
# @perfil_requerido(['1', '2'])  # Solo perfiles 1 (directivo) y 2 (preseptor) pueden acceder
# def carreras():
#     if 'nombre' not in session:
#         return redirect(url_for('login'))
#     # Renderiza la página de gestión de carreras
#     return render_template('carreras.html')

@app.route('/horarios')
@perfil_requerido(['1','2', '3', '4'])  # todos los perfiles pueden acceder
def horarios():
    if 'nombre' not in session:
        return redirect(url_for('login'))
    # Renderiza la página de gestión de horarios
    return render_template('horarios.html')

# Ruta para la página de secretaria
@app.route('/secretaria')
@perfil_requerido(['1', '2'])  # Solo perfiles 1 (directivo) y 2 (secretaria) pueden acceder
def secretaria():
    if 'nombre' not in session:
        return redirect(url_for('login'))
    return render_template('secretaria.html')

# Ruta para enviar los mensajes
@app.route('/enviar_mensaje', methods=['POST'])
@perfil_requerido(['1', '2'])
def enviar_mensaje():
    if 'nombre' not in session:
        return redirect(url_for('login'))
    
    mensaje = request.form.get('mensaje')
    id_usuario = session['id_usuario']
    dia = datetime.now()

    # Insertar el mensaje en la tabla mensajes
    query_insertar_mensaje = """
        INSERT INTO mensajes (mensaje, id_usuario, dia)
        VALUES (%s, %s, %s)
    """
    ejecutar_sql(query_insertar_mensaje, (mensaje, id_usuario, dia))

    flash("Mensaje enviado a todos los usuarios", "success")
    return redirect(url_for('secretaria'))

@app.route('/reportes')
@perfil_requerido(['1', '2'])  # Solo perfiles 1 (directivo) y 3 (profesor) pueden acceder
def reportes():
    if 'nombre' not in session:
        return redirect(url_for('login'))
    # Renderiza la página de generación de reportes
    return render_template('reportes.html')

#ruta donde inscribiremos a las personas para que sean alumnos mas tarde
#primero obtiene todos los datos para los selects y si hace un POST, hace validaciones y guarda los datos para pre_inscripcion_2
@app.route('/pre_inscripcion', methods=['GET', 'POST'])
@perfil_requerido(['1', '2'])
def pre_inscripcion():
    if 'nombre' not in session:
        return redirect(url_for('login'))

    # Obtener países, provincias, localidades, carreras y turnos
    query_paises = "SELECT id_pais, nombre FROM paises"
    paises = ejecutar_sql(query_paises)

    query_provincias = "SELECT id_provincia, nombre, id_pais FROM provincias"
    provincias = ejecutar_sql(query_provincias)

    query_localidades = "SELECT id_localidad, nombre, id_provincia FROM localidades"
    localidades = ejecutar_sql(query_localidades)

    # Incluir el ID de la institución en cada carrera
    query_carreras = """
        SELECT c.id_carrera, c.nombre, c.id_instituto
        FROM lista_carreras c
    """
    lista_carreras = ejecutar_sql(query_carreras)
    carreras_dict = [{"id_carrera": carrera[0], "nombre": carrera[1], "id_instituto": carrera[2]} for carrera in lista_carreras]

    query_turnos = """
        SELECT tc.id_carrera, tc.descripcion, tc.id_turno
        FROM turno_carrera tc
        WHERE tc.estado = 1
    """
    turnos_carreras = ejecutar_sql(query_turnos)
    turnos_carreras_dict = [{"id_carrera": turno[0], "descripcion": turno[1], "id_turno": turno[2]} for turno in turnos_carreras]

        # Consulta para obtener sexos
    query_sexo = "SELECT id_sexo, descripcion FROM sexos"
    sexos = ejecutar_sql(query_sexo)

    query_institutos = "SELECT id_instituto, nombre_instituto FROM institutos"
    institutos = ejecutar_sql(query_institutos)  

    query_estados = "SELECT id_estado_civil, nombre FROM estado_civil"
    estado_civil = ejecutar_sql(query_estados)    

    if request.method == 'POST':
        # Recibir los datos desde el formulario
        datos_personales = request.form.to_dict()
        
        # Verificar si el DNI ya existe en la base de datos de usuarios
        dni = datos_personales.get('dni')
        query_verificar_dni = "SELECT COUNT(*) FROM usuarios WHERE dni = %s"
        existe_dni = ejecutar_sql(query_verificar_dni, (dni,))[0][0]

        if existe_dni > 0: #si existe, volver a enviar los datos y recargar la pagina, dando un mensaje de error
            return render_template(
                'pre_inscripcion.html',
                turnos_carreras=turnos_carreras_dict,
                lista_carreras=carreras_dict,
                paises=paises,
                provincias=provincias,
                localidades=localidades,
                error_dni=True,
                sexos=sexos,
                institutos=institutos,
                estado_civil=estado_civil,
                datos_personales=datos_personales  # Para mantener los datos ingresados
            )

        # Guardar los datos en la sesión y continuar a la siguiente página
        session['datos_personales'] = datos_personales
        return redirect(url_for('pre_inscripcion_2'))

    # Renderizar la página sin mensaje de error al cargar por primera vez (GET)
    return render_template(
        'pre_inscripcion.html',
        turnos_carreras=turnos_carreras_dict,
        lista_carreras=carreras_dict,
        paises=paises,
        provincias=provincias,
        localidades=localidades,
        error_dni=False,
        sexos=sexos,
        institutos=institutos,
        estado_civil=estado_civil
    )






#sigue el formulario y guarda todo para pre_inscripcion_3
@app.route('/pre_inscripcion_2', methods=['GET', 'POST'])
@perfil_requerido(['1', '2'])
def pre_inscripcion_2():
    if 'nombre' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Recibir los datos del formulario anterior
        datos_personales = request.form.to_dict()

        # Guardar en la sesión para usarlos más adelante
        session['datos_personales'] = datos_personales

    # Obtener el país seleccionado previamente (Argentina o no)
    id_pais_estudio = int(session['datos_personales'].get('id_pais', 0))  # Valor por defecto 0 si no está en sesión

    # Consulta para obtener provincias
    query_provincias = "SELECT id_provincia, id_pais, nombre FROM provincias"
    provincias = ejecutar_sql(query_provincias)


    return render_template(
        'pre_inscripcion_2.html',
        id_pais_estudio=id_pais_estudio,
        provincias=provincias,
    )


#una vez que esta completo el formulario, guardamos al ingresante en pre_inscripciones para mas adelante darlo de alta como alumno
@app.route('/guardar_pre_inscripcion', methods=['POST'])
def guardar_pre_inscripcion():
    # Obtener todos los datos desde la sesión
    datos = session.get('datos_completos', {})

    # Ajustar campos que pueden no estar presentes
    datos['lugar_nacimiento'] = datos.get('lugar_nacimiento') or None
    datos['telefono_alt'] = datos.get('telefono_alt') or None
    datos['telefono_alt_propietario'] = datos.get('telefono_alt_propietario') or None
    datos['titulo_base'] = datos.get('titulo_base') or None
    datos['anio_egreso_otros'] = datos.get('anio_egreso_otros') or None
    datos['piso'] = datos.get('piso') if datos.get('piso') != 'NULL' else None

    # Ajustar los campos relacionados con el trabajo
    trabaja = datos.get('trabaja')
    actividad = datos.get('actividad', '') if trabaja == 'si' else None
    horario_habitual = datos.get('horario_habitual', '') if trabaja == 'si' else None
    obra_social = datos.get('obra_social', '') if trabaja == 'si' else None

    # Usar los IDs originales para la inserción en inscripciones_carreras
    id_carrera = datos.get('id_carrera_original')
    id_turno = datos.get('id_turno_original')
    id_pais = datos.get('id_pais_original')
    id_provincia = datos.get('id_provincia_original')
    id_localidad = datos.get('id_localidad_original')
    id_institucion = datos.get('id_instituto_original')
    id_sexo = datos.get('id_sexo_original')
    id_estado_civil = datos.get('id_estado_civil_original')

    # Insertar el usuario en la tabla pre_inscripciones sin id_carrera ni id_turno
    query_usuario = """
        INSERT INTO pre_inscripciones (
            dni, nombre, apellido, id_sexo, fecha_nacimiento, lugar_nacimiento, id_estado_civil,
            cantidad_hijos, familiares_a_cargo, domicilio, piso, id_localidad, id_pais,
            id_provincia, codigo_postal, telefono, telefono_alt, telefono_alt_propietario, email,
            titulo_base, anio_egreso, id_institucion, otros_estudios, anio_egreso_otros,
            trabaja, actividad, horario_habitual, obra_social
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    ejecutar_sql(query_usuario, (
        datos['dni'], datos['nombre'], datos['apellido'], id_sexo,
        datos['fecha_nacimiento'], datos['lugar_nacimiento'], id_estado_civil,
        datos['cantidad_hijos'], datos['familiares_a_cargo'], datos['domicilio'],
        datos['piso'], id_localidad, id_pais,
        id_provincia, datos['codigo_postal'], datos['telefono'],
        datos['telefono_alt'], datos['telefono_alt_propietario'], datos['email'],
        datos['titulo_base'], datos['anio_egreso'], id_institucion,
        datos['otros_estudios'], datos['anio_egreso_otros'], trabaja,
        actividad, horario_habitual, obra_social
    ))

    # Recuperar id_usuario usando el DNI
    query_select_id = "SELECT id_usuario FROM pre_inscripciones WHERE dni = %s"
    id_usuario = ejecutar_sql(query_select_id, (datos['dni'],))[0][0]
    print (id_usuario)
    # Insertar en inscripciones_carreras con el id_usuario obtenido
    query_inscripcion = """
        INSERT INTO inscripciones_carreras (
            id_carrera, id_usuario, fecha_inscripcion, turno, estado_alumno, activo
        ) VALUES (%s, %s, NOW(), %s, 'pre_inscripto', 1)
    """
    ejecutar_sql(query_inscripcion, (id_carrera, id_usuario, id_turno))
    # Redirigir al home una vez completada la inscripción
    return redirect(url_for('home'))





#siguiendo con el formulario, aqui primero cargara todos los datos, generara algunas inteligencias para mostrar nombres en vez de
# ids y los mostrara en pantalla, si todo esta bien pasamos a guardar_pre_inscripcion
@app.route('/pre_inscripcion_3', methods=['POST'])
@perfil_requerido(['1', '2'])
def pre_inscripcion_3():
    if 'nombre' not in session:
        return redirect(url_for('login'))

    # Obtener los datos personales desde la sesión
    datos_personales = session.get('datos_personales', {})

    # Recibir los datos de estudios y laborales del formulario de pre_inscripcion_2
    datos_estudios_y_laborales = request.form.to_dict()

    # Combinar todos los datos
    datos_completos = {**datos_personales, **datos_estudios_y_laborales}

    # Guardar en la sesión
    session['datos_completos'] = datos_completos

    # Consultas SQL para obtener los nombres en lugar de IDs
    query_pais = "SELECT nombre FROM paises WHERE id_pais = %s"
    query_provincia = "SELECT nombre FROM provincias WHERE id_provincia = %s"
    query_localidad = "SELECT nombre FROM localidades WHERE id_localidad = %s"
    query_carrera = "SELECT nombre FROM lista_carreras WHERE id_carrera = %s"
    query_turno = "SELECT descripcion FROM turno_carrera WHERE id_turno = %s"
    query_instituto = "SELECT nombre_instituto FROM institutos WHERE id_instituto = %s"
    query_sexo = "SELECT descripcion FROM sexos WHERE id_sexo = %s"
    query_estado_civil = "SELECT nombre FROM estado_civil WHERE id_estado_civil = %s"

    # Mantener los IDs originales
    id_pais_original = datos_completos.get('id_pais')
    id_provincia_original = datos_completos.get('id_provincia')
    id_localidad_original = datos_completos.get('id_localidad')
    id_carrera_original = datos_completos.get('carrera')
    id_turno_original = datos_completos.get('turno')
    id_instituto_original = datos_completos.get('id_institucion')
    id_sexo_original = datos_completos.get('id_sexo')
    id_estado_civil_original = datos_completos.get('id_estado_civil')

    # Obtener los nombres basados en los IDs
    pais_nombre = ejecutar_sql(query_pais, (id_pais_original,))[0][0] if id_pais_original else None
    provincia_nombre = ejecutar_sql(query_provincia, (id_provincia_original,))[0][0] if id_provincia_original else None
    localidad_nombre = ejecutar_sql(query_localidad, (id_localidad_original,))[0][0] if id_localidad_original else None
    carrera_nombre = ejecutar_sql(query_carrera, (id_carrera_original,))[0][0] if id_carrera_original else None
    turno_descripcion = ejecutar_sql(query_turno, (id_turno_original,))[0][0] if id_turno_original else None
    instituto_nombre = ejecutar_sql(query_instituto, (id_instituto_original,))[0][0] if id_instituto_original else None
    sexo_nombre = ejecutar_sql(query_sexo, (id_sexo_original,))[0][0] if id_sexo_original else None
    estado_civil_nombre = ejecutar_sql(query_estado_civil, (id_estado_civil_original,))[0][0] if id_estado_civil_original else None

    # Guardar los valores originales junto con los nombres
    datos_completos['id_pais_original'] = id_pais_original
    datos_completos['id_provincia_original'] = id_provincia_original
    datos_completos['id_localidad_original'] = id_localidad_original
    datos_completos['id_carrera_original'] = id_carrera_original
    datos_completos['id_turno_original'] = id_turno_original
    datos_completos['id_instituto_original'] = id_instituto_original
    datos_completos['id_sexo_original'] = id_sexo_original
    datos_completos['id_estado_civil_original'] = id_sexo_original

    # Reemplazar los IDs por sus nombres para mostrar en la vista
    datos_completos['id_pais'] = pais_nombre
    datos_completos['id_provincia'] = provincia_nombre
    datos_completos['id_localidad'] = localidad_nombre
    datos_completos['carrera'] = carrera_nombre
    datos_completos['turno'] = turno_descripcion
    datos_completos['id_institucion'] = instituto_nombre
    datos_completos['id_sexo'] = sexo_nombre
    datos_completos['id_estado_civil'] = estado_civil_nombre

    return render_template('pre_inscripcion_3.html', **datos_completos)

#estas rutas hacen lo mismo que pre_inscripcion pero estas funcionan para el que hace el formulario de afuera, no vera la navbar
@app.route('/inscribite', methods=['GET', 'POST'])
def inscribite():

    # Obtener países, provincias, localidades, carreras y turnos
    query_paises = "SELECT id_pais, nombre FROM paises"
    paises = ejecutar_sql(query_paises)

    query_provincias = "SELECT id_provincia, nombre, id_pais FROM provincias"
    provincias = ejecutar_sql(query_provincias)

    query_localidades = "SELECT id_localidad, nombre, id_provincia FROM localidades"
    localidades = ejecutar_sql(query_localidades)

    # Incluir el ID de la institución en cada carrera
    query_carreras = """
        SELECT c.id_carrera, c.nombre, c.id_instituto
        FROM lista_carreras c
    """
    lista_carreras = ejecutar_sql(query_carreras)
    carreras_dict = [{"id_carrera": carrera[0], "nombre": carrera[1], "id_instituto": carrera[2]} for carrera in lista_carreras]

    query_turnos = """
        SELECT tc.id_carrera, tc.descripcion, tc.id_turno
        FROM turno_carrera tc
        WHERE tc.estado = 1
    """
    turnos_carreras = ejecutar_sql(query_turnos)
    turnos_carreras_dict = [{"id_carrera": turno[0], "descripcion": turno[1], "id_turno": turno[2]} for turno in turnos_carreras]

        # Consulta para obtener sexos
    query_sexo = "SELECT id_sexo, descripcion FROM sexos"
    sexos = ejecutar_sql(query_sexo)

    query_institutos = "SELECT id_instituto, nombre_instituto FROM institutos"
    institutos = ejecutar_sql(query_institutos)  

    query_estados = "SELECT id_estado_civil, nombre FROM estado_civil"
    estado_civil = ejecutar_sql(query_estados)    

    if request.method == 'POST':
        # Recibir los datos desde el formulario
        datos_personales = request.form.to_dict()
        
        # Verificar si el DNI ya existe en la base de datos de usuarios
        dni = datos_personales.get('dni')
        query_verificar_dni = "SELECT COUNT(*) FROM usuarios WHERE dni = %s"
        existe_dni = ejecutar_sql(query_verificar_dni, (dni,))[0][0]

        if existe_dni > 0:
            return render_template(
                'inscribite.html',
                turnos_carreras=turnos_carreras_dict,
                lista_carreras=carreras_dict,
                paises=paises,
                provincias=provincias,
                localidades=localidades,
                error_dni=True,
                sexos=sexos,
                institutos=institutos,
                estado_civil=estado_civil,
                datos_personales=datos_personales  # Para mantener los datos ingresados
            )

        # Guardar los datos en la sesión y continuar a la siguiente página
        session['datos_personales'] = datos_personales
        return redirect(url_for('inscribite_2'))

    # Renderizar la página sin mensaje de error al cargar por primera vez (GET)
    return render_template(
        'inscribite.html',
        turnos_carreras=turnos_carreras_dict,
        lista_carreras=carreras_dict,
        paises=paises,
        provincias=provincias,
        localidades=localidades,
        error_dni=False,
        sexos=sexos,
        institutos=institutos,
        estado_civil=estado_civil
    )

#estas rutas hacen lo mismo que pre_inscripcion pero estas funcionan para el que hace el formulario de afuera, no vera la navbar
@app.route('/inscribite_2', methods=['GET', 'POST'])
def inscribite_2():

    if request.method == 'POST':
        # Recibir los datos del formulario anterior
        datos_personales = request.form.to_dict()

        # Guardar en la sesión para usarlos más adelante
        session['datos_personales'] = datos_personales

    # Obtener el país seleccionado previamente (Argentina o no)
    id_pais_estudio = int(session['datos_personales'].get('id_pais', 0))  # Valor por defecto 0 si no está en sesión

    # Consulta para obtener provincias
    query_provincias = "SELECT id_provincia, id_pais, nombre FROM provincias"
    provincias = ejecutar_sql(query_provincias)


    return render_template(
        'inscribite_2.html',
        id_pais_estudio=id_pais_estudio,
        provincias=provincias,
    )


#estas rutas hacen lo mismo que pre_inscripcion pero estas funcionan para el que hace el formulario de afuera, no vera la navbar
@app.route('/inscribite_3', methods=['POST'])
def inscribite_3():

    # Obtener los datos personales desde la sesión
    datos_personales = session.get('datos_personales', {})

    # Recibir los datos de estudios y laborales del formulario de pre_inscripcion_2
    datos_estudios_y_laborales = request.form.to_dict()

    # Combinar todos los datos
    datos_completos = {**datos_personales, **datos_estudios_y_laborales}

    # Guardar en la sesión
    session['datos_completos'] = datos_completos

    # Consultas SQL para obtener los nombres en lugar de IDs
    query_pais = "SELECT nombre FROM paises WHERE id_pais = %s"
    query_provincia = "SELECT nombre FROM provincias WHERE id_provincia = %s"
    query_localidad = "SELECT nombre FROM localidades WHERE id_localidad = %s"
    query_carrera = "SELECT nombre FROM lista_carreras WHERE id_carrera = %s"
    query_turno = "SELECT descripcion FROM turno_carrera WHERE id_turno = %s"
    query_instituto = "SELECT nombre_instituto FROM institutos WHERE id_instituto = %s"
    query_sexo = "SELECT descripcion FROM sexos WHERE id_sexo = %s"
    query_estado_civil = "SELECT nombre FROM estado_civil WHERE id_estado_civil = %s"

    # Mantener los IDs originales
    id_pais_original = datos_completos.get('id_pais')
    id_provincia_original = datos_completos.get('id_provincia')
    id_localidad_original = datos_completos.get('id_localidad')
    id_carrera_original = datos_completos.get('carrera')
    id_turno_original = datos_completos.get('turno')
    id_instituto_original = datos_completos.get('id_institucion')
    id_sexo_original = datos_completos.get('id_sexo')
    id_estado_civil_original = datos_completos.get('id_estado_civil')

    # Obtener los nombres basados en los IDs
    pais_nombre = ejecutar_sql(query_pais, (id_pais_original,))[0][0] if id_pais_original else None
    provincia_nombre = ejecutar_sql(query_provincia, (id_provincia_original,))[0][0] if id_provincia_original else None
    localidad_nombre = ejecutar_sql(query_localidad, (id_localidad_original,))[0][0] if id_localidad_original else None
    carrera_nombre = ejecutar_sql(query_carrera, (id_carrera_original,))[0][0] if id_carrera_original else None
    turno_descripcion = ejecutar_sql(query_turno, (id_turno_original,))[0][0] if id_turno_original else None
    instituto_nombre = ejecutar_sql(query_instituto, (id_instituto_original,))[0][0] if id_instituto_original else None
    sexo_nombre = ejecutar_sql(query_sexo, (id_sexo_original,))[0][0] if id_sexo_original else None
    estado_civil_nombre = ejecutar_sql(query_estado_civil, (id_estado_civil_original,))[0][0] if id_estado_civil_original else None

    # Guardar los valores originales junto con los nombres
    datos_completos['id_pais_original'] = id_pais_original
    datos_completos['id_provincia_original'] = id_provincia_original
    datos_completos['id_localidad_original'] = id_localidad_original
    datos_completos['id_carrera_original'] = id_carrera_original
    datos_completos['id_turno_original'] = id_turno_original
    datos_completos['id_instituto_original'] = id_instituto_original
    datos_completos['id_sexo_original'] = id_sexo_original
    datos_completos['id_estado_civil_original'] = id_sexo_original

    # Reemplazar los IDs por sus nombres para mostrar en la vista
    datos_completos['id_pais'] = pais_nombre
    datos_completos['id_provincia'] = provincia_nombre
    datos_completos['id_localidad'] = localidad_nombre
    datos_completos['carrera'] = carrera_nombre
    datos_completos['turno'] = turno_descripcion
    datos_completos['id_institucion'] = instituto_nombre
    datos_completos['id_sexo'] = sexo_nombre
    datos_completos['id_estado_civil'] = estado_civil_nombre

    return render_template('inscribite_3.html', **datos_completos)

@app.route('/alta_de_profesores')
def alta_de_profesores():
    return render_template('alta_de_profesores.html')  



@app.route('/logout')
def logout():

    session.pop('nombre', None)
    session.pop('dni', None)

    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)

    