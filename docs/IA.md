# Integración de IA (Ollama)

## Estado

El perfil `docker-compose.local.yml` habilita IA solo en el stack local y conecta backend y worker al daemon Ollama del equipo (`host.docker.internal:11434`) con `deepseek-v4.1-flash:cloud`. Se verificó una respuesta del modelo mediante la API local de Ollama. El sufijo `:cloud` significa que Ollama envía la inferencia a su servicio cloud: usar este modo únicamente con datos ficticios o autorizados.

`docker-compose.yml` no recibe estos overrides. La configuración de otros entornos debe habilitarse y revisarse por separado.

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

En **Comparar ofertas → Explicar con IA**, primero se pide confirmación. La solicitud envía únicamente el método de evaluación y señales booleanas del resultado (por ejemplo, si hubo un empate o quedaron ofertas pendientes), sin montos, nombres, códigos de expediente, documentos ni texto libre del pliego. El cálculo oficial no depende del proveedor ni cambia al consultar la explicación.

## Recuperación de normativa

El comando `flask --app wsgi ai-index-normative` indexa las fuentes normativas para el RAG. El embedder por defecto es `fastembed` (modelo `EMBED_MODEL`). `EMBEDDER=hash` existe solo para pruebas unitarias y no debe usarse en producción.

## Verificación

- La API local del daemon Ollama respondió con `deepseek-v4.1-flash:cloud`.
- `Test-Stack.ps1` comprueba la salud de la aplicación; no comprueba disponibilidad del proveedor de IA.
