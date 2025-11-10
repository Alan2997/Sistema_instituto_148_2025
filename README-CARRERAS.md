Sistema de Gestión Académica (Carreras, Cursos y Materias)
Descripción general

Este módulo forma parte de un sistema académico desarrollado con Flask (Python) y MySQL, orientado a la gestión de carreras, cursos y materias de una institución educativa.
Permite crear, editar, listar y administrar entidades académicas de manera integrada, con validaciones, filtros y control de estados.

Funcionalidades principales
Carreras

Crear nuevas carreras con datos como:

Nombre, descripción, tipo (Tecnicatura o Profesorado)

Año de creación, ley, fecha y turno (Mañana, Tarde, Noche)

Creación automática de cursos al registrar una nueva carrera.

Tecnicatura: 3 cursos

Profesorado: 4 cursos

Edición de carreras existentes.

Filtros por:

Estado (activos/inactivos/todos)

Año académico (filtra automáticamente mostrando el año actual por defecto)

Turno

Nombre (búsqueda parcial)

Paginación de resultados.

Opción de limpiar filtros fácilmente.

Cursos

Crear cursos manualmente asociados a una carrera.

Validación automática:

No permite años anteriores al año de la carrera.

El año debe ser igual o posterior al año de inicio de la carrera.

Edición y activación/desactivación de cursos.

Al desactivar un curso, las materias asociadas también se desactivan.

Filtros por nombre y estado.

Paginación de hasta 5 cursos por página.

Materias

Agregar materias a un curso específico.

Validaciones automáticas:

Campos obligatorios: nombre, carga horaria, tipo de campo.

No permite carga horaria negativa.

No permite duplicar nombres de materias dentro del mismo curso.

Edición de materias con las mismas restricciones.

Muestra la carga horaria total de todas las materias del curso.

Visualización tipo card del total de horas.

Paginación y búsqueda por nombre.

Plan de Estudio

Consulta combinada de:

Carrera → Curso → Materias.

Muestra las materias correspondientes según los filtros seleccionados.

Paginación de hasta 5 materias por página.

Cálculo automático de la carga horaria total del plan.

Mantiene numeración secuencial entre páginas (1–5, 6–10, etc.).

Validaciones destacadas

Contexto	Validación
Carrera	No se permiten nombres duplicados.
Curso	No puede tener un año anterior al año de la carrera.
Materia	No puede tener carga horaria negativa.
Curso	No puede estar activo si la carrera está inactiva.
Curso	No permite nombres duplicados dentro de la misma carrera.
Materia	No permite nombres duplicados dentro del mismo curso.
Interfaz de usuario

Desarrollada con Bootstrap 4/5.

Diseño limpio, con modales para alta y edición.

Formularios intuitivos con etiquetas descriptivas.

Botones de acción claros (Agregar, Editar, Buscar, Limpiar).

Feedback visual mediante Flask Flash Messages (éxito/error).

Paginación personalizada con estilo moderno.

Tablas responsive con encabezados claros.

Tecnologías utilizadas
Componente	Tecnología
Backend	Flask (Python)
Base de datos	MySQL / MariaDB
ORM / Queries	SQL directo con ejecutar_sql()
Frontend	HTML5, Bootstrap, Jinja2
Autenticación	Sesión Flask (session['nombre'])
Control de fechas	Python date.today()
Paginación	Manual con LIMIT y OFFSET
Alertas	flask.flash() y Bootstrap alerts

Tipos de prueba aplicados
Pruebas de Caja Negra

Se verificó la funcionalidad del sistema sin analizar el código interno:

Validación de formularios (campos vacíos, duplicados, carga horaria negativa).

Navegación entre pestañas (Carreras, Cursos, Materias, Plan de Estudio).

Paginación y filtros.

Creación automática de cursos según el tipo de carrera.

Pruebas de Caja Blanca

Se revisó la lógica de negocio en el código Python:

Flujo correcto de validaciones.

Consultas SQL seguras.

Manejo correcto de redirecciones y sesiones.

Validación de integridad entre tablas (carreras–cursos–materias).

Flujo general del sistema

El usuario inicia sesión.

Ingresa al módulo de Carreras.

Desde allí puede:

Crear o editar carreras.

Acceder a los Cursos asociados.

Desde la vista de cursos puede:

Agregar o editar cursos.

Ingresar a las Materias del curso.

Desde Materias, puede gestionar las asignaturas y visualizar la carga horaria total.

En el Plan de Estudio, puede consultar carreras, cursos y materias con su carga total.