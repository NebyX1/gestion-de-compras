# Guía de desarrollo para agentes y colaboradores

Esta guía permite localizar el código correcto, ejecutar el proyecto y validar un cambio sin suponer detalles del diseño.

## Lectura inicial recomendada

1. `README.md`: propósito, arquitectura, arranque y operación.
2. `backend/app/modules/procurement/states.py`: etapas, estados y próximas acciones.
3. `backend/app/modules/identity/permissions.py`: roles, permisos y alcance.
4. `backend/app/modules/procurement/framework.py`: despacho y protección de acciones.
5. `frontend/src/App.tsx`: rutas principales y permisos de pantalla.
6. `.env.example` y `docker-compose*.yml`: configuración y servicios reales.

Evitar usar archivos de referencia o material dentro de `sample/` o `model/`: están excluidos del repositorio y no forman parte de la ejecución.

## Mapa de cambios

| Necesidad | Punto de entrada |
|---|---|
| Crear o cambiar un endpoint | `backend/app/modules/*/routes.py` o `backend/app/ai/routes.py` |
| Cambiar una transición de expediente | `backend/app/modules/procurement/actions/` |
| Registrar esquemas de acción | `backend/app/modules/procurement/actions/` y `forms.py` |
| Validar o ejecutar una acción | `framework.py`, `access.py` y decoradores de `identity/service.py` |
| Cambiar estados o etapas | `states.py`, serializadores, formularios y pantallas relacionadas |
| Cambiar evaluación determinista | `backend/app/modules/evaluation/engine.py` |
| Cambiar explicaciones | `evaluation/explain.py` |
| Cambiar permisos | `identity/permissions.py` y pruebas de permisos |
| Cambiar persistencia | `infrastructure/models/`, migración Alembic y serializadores |
| Cambiar auditoría | `infrastructure/audit.py` y `modules/audit/routes.py` |
| Cambiar carga/descarga documental | `modules/documents/`, `documents/policies.py` y `infrastructure/storage.py` |
| Cambiar IA o RAG | `backend/app/ai/` y `worker.py` |
| Cambiar API consumida por React | `frontend/src/api/endpoints.ts`, `types.ts` y `client.ts` |
| Cambiar pantalla principal | `frontend/src/pages/` |
| Cambiar panel de expediente | `frontend/src/components/case/` |
| Cambiar estilos | `frontend/src/styles.css` |

## Invariantes del dominio

No modificar estos comportamientos sin una decisión funcional explícita:

1. El backend, no el cliente, autoriza y ejecuta las transiciones.
2. La evaluación oficial es determinista y no depende de una respuesta del proveedor de IA.
3. Los importes y puntajes de dominio usan valores exactos (`Decimal`/texto), nunca `float` como fuente.
4. Un evento de negocio y su auditoría se confirman en una transacción.
5. Los permisos provienen de asignaciones vigentes y con alcance, no solo del nombre del rol.
6. Los documentos de sobres y sus originales no se sobrescriben.
7. Las mutaciones deben conservar idempotencia o versionado donde ya existan.
8. Un error externo no debe registrarse como éxito; integraciones sin contrato permanecen manuales o no configuradas.
9. La autenticación sintética solo es válida con `APP_ENV=testing`.
10. No registrar secretos, contenido sensible de documentos ni respuestas completas del proveedor en logs.

## Flujo para implementar un cambio

1. Localizar la ruta HTTP, acción o pantalla involucrada.
2. Leer el modelo, serializador, servicio, pruebas y permisos relacionados.
3. Cambiar primero el contrato del backend y sus pruebas.
4. Actualizar el cliente de API y los tipos TypeScript.
5. Ajustar la UI sin delegarle reglas de seguridad ni validación al navegador.
6. Actualizar `README.md` o `docs/` si cambia una capacidad, variable, servicio o flujo.
7. Ejecutar las validaciones mínimas que cubran el cambio.

## Comandos de validación

### Backend

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest -q
```

Para una prueba concreta:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_workflow.py
```

### Frontend

```powershell
Set-Location frontend
npm run typecheck
npm run build
```

### Stack completo

```powershell
.\scripts\Initialize-Environment.ps1
.\scripts\Start-Stack.ps1 -WithMail
.\scripts\Test-Stack.ps1
```

### Migraciones

Después de cambiar modelos:

```powershell
docker compose -f docker-compose.yml -f docker-compose.local.yml exec backend `
  flask --app wsgi db migrate -m "descripcion_del_cambio"
docker compose -f docker-compose.yml -f docker-compose.local.yml restart migrate
```

Revisar siempre el archivo Alembic generado antes de publicarlo. No modificar retroactivamente migraciones ya publicadas.

## Pruebas focalizadas

- `test_workflow.py`: recorrido de acciones y estados.
- `test_engine.py`: cálculo, exclusiones, empate y trazabilidad.
- `test_documents.py`: validación, versiones, acceso y almacenamiento.
- `test_permissions.py`: permisos, competencia y acceso local de prueba.
- `test_rules.py`: vigencias, topes y calendario.
- `test_demo_seed.py`: idempotencia y casos demostrativos.

## Comprobaciones antes de publicar

- No hay `.env`, respaldos, documentos, credenciales ni directorios `.local/` incorporados.
- `git status` solo contiene cambios intencionales.
- Las pruebas del backend y el build TypeScript pasan.
- La documentación describe cualquier variable, servicio, flujo o comando nuevo.
- El docker-compose sigue sin publicar MariaDB, backend o almacenamiento.
- `docker-compose.local.yml` no se usa para despliegues productivos.
- Los cambios de esquema tienen una migración revisada.
