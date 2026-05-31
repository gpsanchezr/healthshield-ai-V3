# TODO

- [x] Revisar `render.yaml` y validar `wsgi.py` real.
- [x] Corregir `startCommand` de Render para que apunte a `backend.config.wsgi:application` sin asumir una ruta inexistente.
  - `gunicorn backend.config.wsgi:application --bind 0.0.0.0:$PORT --workers 2`
- [ ] Re-deploy en Render y verificar logs de Gunicorn.

- [ ] Validar healthcheck `GET /api/schema/` responde 200.

