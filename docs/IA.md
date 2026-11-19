# Integración de IA (Ollama)

## Estado

El perfil `docker-compose.local.yml` habilita IA solo en el stack local y conecta backend y worker al daemon Ollama del equipo (`host.docker.internal:11434`) con `deepseek-v4.1-flash:cloud`. Se verificó una respuesta del modelo mediante la API local de Ollama. El sufijo `:cloud` significa que Ollama envía la inferencia a su servicio cloud: usar este modo únicamente con datos ficticios o autorizados.

Para trabajar con un modelo instalado en el equipo, se puede indicar `LOCAL_OLLAMA_MODEL=phi4-mini:3.8b` en el `.env` del override local. El compose de producción utiliza `OLLAMA_HOST` y `OLLAMA_MODEL`.

## Configuración en otros entornos

1. Obtener autorización para el tratamiento de datos y el nombre exacto de un modelo vigente.
2. Configurar `OLLAMA_HOST`, `OLLAMA_MODEL` y, si el endpoint lo requiere, `OLLAMA_API_KEY`.
3. Revisar la política de salida (abajo) y confirmar con el responsable de datos.
4. Poner `AI_ENABLED=true` y reiniciar `backend` y `worker`.
5. Verificar en la aplicación con un usuario autorizado: `GET /api/v1/health/ai` (requiere sesión).

## Política de salida de datos

| Variable | Valor por defecto | Significado |
|---|---|---|
| `AI_EGRESS_POLICY` | `minimized` | `off` (nada sale), `metadata_only`, `minimized`, `full_text`. |
| `AI_EGRESS_CLASSES` | `public,internal` | Clasificaciones de documento que pueden salir al proveedor. |
| `AI_MAX_CONTEXT_CHARS` | `24000` | Límite de contexto enviado. |

Los documentos clasificados fuera de `AI_EGRESS_CLASSES` no se envían. Antes de habilitar en producción, confirmar la clasificación de cada tipo de documento y que el proveedor cumple la normativa aplicable.

En **Comparar ofertas → Solicitar recomendación de IA**, la persona confirma la consulta. El modelo recibe los requisitos y criterios del pliego, la ponderación, los puntos por criterio, un índice de precio relativo, la entrega y la garantía de cada oferta admisible identificada por alias. La API aplica la política de salida y valida la respuesta. Un alias desconocido, una evaluación obsoleta o una respuesta sin fundamento no generan una recomendación válida.

La primera recomendación válida queda vinculada a la versión evaluada. El modelo puede abstenerse. El ordenador revisa el resultado del pliego, el criterio de IA disponible y el dictamen antes de registrar su decisión. La publicación de la adjudicación permite incorporar el análisis inicial revisado. El motor de puntajes y los controles del expediente siguen disponibles si el proveedor está deshabilitado o no responde.

## Recuperación de normativa

El comando `flask --app wsgi ai-index-normative` indexa las fuentes normativas para el RAG. El embedder por defecto es `fastembed` (modelo `EMBED_MODEL`). `EMBEDDER=hash` existe solo para pruebas unitarias y no debe usarse en producción.

## Verificación

- El flujo de recomendación estructurada se probó también con `phi4-mini:3.8b` en el daemon local, con ofertas ficticias y publicación del apartamiento de la decisión simulada.
- `Test-Stack.ps1` comprueba la salud de la aplicación; no comprueba disponibilidad del proveedor de IA.
