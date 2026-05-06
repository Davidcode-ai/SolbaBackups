# Guía de contribución y desarrollo colaborativo

## Flujo de trabajo con Git

Este repositorio sigue el flujo de trabajo **Git Flow** simplificado:

```
main         ← Código estable / releases
develop      ← Integración continua
feature/*    ← Ramas de desarrollo de cada alumno
```

### Convenciones de ramas

| Prefijo     | Uso                                      |
|-------------|------------------------------------------|
| `feature/`  | Nueva funcionalidad                      |
| `fix/`      | Corrección de errores                    |
| `docs/`     | Cambios solo en documentación            |
| `refactor/` | Refactorización sin cambio de funcionalidad |
| `test/`     | Añadir o mejorar tests                   |

### Mensajes de commit (Conventional Commits)

```
tipo(ámbito): descripción breve en presente

Cuerpo opcional con más detalles.

Closes #123
```

Tipos válidos: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`

Ejemplos:
```
feat(backup): añadir soporte para MongoDB
fix(scheduler): corregir cálculo de día mensual
docs(usage): añadir ejemplos de restauración MySQL
test(detector): cubrir caso de timeout de puerto
```

---

## Distribución de responsabilidades (sugerencia)

| Alumno | Área principal                              |
|--------|---------------------------------------------|
| A1     | Módulos de backup (SQL Server, PostgreSQL, MySQL) + Tests |
| A2     | Scheduler, Sync, Google Drive + Documentación |
| A3     | Detector, Restore, CLI + Integración final  |

---

## Estándares de código

- **Estilo**: PEP 8, formateado con `black` (línea máx. 88 chars).
- **Linting**: `flake8` (ver `.flake8` o `setup.cfg`).
- **Tipado**: Type hints en todas las funciones públicas.
- **Docstrings**: estilo Google (con la extensión `autodocstring`).
- **Tests**: pytest, un archivo de test por módulo, cobertura ≥ 80 %.

### Antes de hacer commit

```bash
black src/ tests/
flake8 src/ tests/
pytest tests/ -v
```

O usa la tarea de VSCode **"Lint (flake8)"** y **"Ejecutar tests"**.

---

## Documentación del progreso

Cada alumno debe documentar su trabajo en el directorio `docs/`:

- `docs/diario/ALUMNO_A1.md` – diario de desarrollo de A1
- `docs/diario/ALUMNO_A2.md` – diario de desarrollo de A2
- `docs/diario/ALUMNO_A3.md` – diario de desarrollo de A3

Formato recomendado para cada entrada:

```markdown
## YYYY-MM-DD

### Tareas realizadas
- ...

### Problemas encontrados
- ...

### Soluciones aplicadas
- ...

### Próximos pasos
- ...
```

---

## Revisión de código (Pull Requests)

1. Crea tu rama: `git checkout -b feature/mi-funcionalidad`
2. Implementa los cambios y escribe tests.
3. Formatea y linta el código.
4. Abre un Pull Request hacia `develop`.
5. Otro alumno revisa el código y da feedback.
6. Tras la aprobación, se hace merge.

---

## Recursos útiles

- [Documentación de Click](https://click.palletsprojects.com/)
- [psycopg2 (PostgreSQL)](https://www.psycopg.org/docs/)
- [pymysql (MySQL)](https://pymysql.readthedocs.io/)
- [Google Drive API Python](https://developers.google.com/drive/api/quickstart/python)
- [schedule (Python)](https://schedule.readthedocs.io/)
- [watchdog (Python)](https://python-watchdog.readthedocs.io/)
- [pytest](https://docs.pytest.org/)
