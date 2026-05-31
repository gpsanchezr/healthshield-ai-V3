# TODO

- [ ] Refactor `tests/test_api.py` para pasar de smoke-script a suite profesional pytest-django.
- [ ] Usar fixtures para roles (admin/medico/analista) y datos base (paciente/registro).
- [ ] Reemplazar `django.test.Client` por `rest_framework.test.APIClient`.
- [ ] Enviar payloads JSON correctamente (vía `format='json'` o `json.dumps`).
- [ ] Eliminar estado global y ejecución manual (`main()` / `django.setup()` / DB en memoria forzada).
- [ ] Asegurar aislamiento: cada test independiente (sin mutaciones compartidas).
- [ ] Validaciones estrictas con `rest_framework.status` y verificación de claves JSON (access/refresh/kpis/openapi).
- [ ] Añadir/ajustar pruebas RBAC: admin ok; medico/analista bloqueados en acciones no permitidas (403).
- [x] Ejecutar/ajustar la refactorización base de `tests/test_api.py`.
- [ ] Ejecutar `pytest` y corregir fallos hasta que la suite pase.


