# Impl-2 (Módulo 12): estado y traspaso

Fecha del corte: 2026-11-08. Rama `impl-2`, último commit del trabajo `b6ec349` (empujado; CI del run `42440115643` en verde, 5 jobs). Este documento es para quien continúe: qué está hecho, qué falta, qué hay que saber antes de tocar nada.

## 1. Dónde está todo

| Qué | Dónde |
|---|---|
| Reglas que mandan sobre cualquier otro documento | `docs/impl2-rules.md` |
| Informe de auditoría, matriz, **plan T-00..T-22**, **guía operativa BMad E-00..E-12** | `docs/impl2-continuation/01..04-*.md` (**sin trackear en git**: no se suben; el compañero necesita copia) |
| Historias (una por archivo) | `_bmad-output/implementation-artifacts/<clave>.md` (Review Findings, auditoría de trampas y cierre al final de cada una) |
| Estado del sprint | `_bmad-output/implementation-artifacts/sprint-status.yaml` y su copia `implementation-artifacts/sprint-status.yaml` (**deben ser idénticas**, `diff`) |
| Log de decisiones de IA | `docs/ai-decision-log.md` (entradas I2-xx; las últimas: I2-28 a I2-34) |
| Lo aplazado a propósito | `_bmad-output/implementation-artifacts/deferred-work.md` |
| Evidencia (logs rojos, cobertura, ATDD x3) | `docs/evidence/impl2/` |
| Contrato | `planning/detailed-design/contracts.md`, `schemas/openapi.yaml`, `schemas/dto.py` (copia exacta de `src/dto.py`) |

## 2. Cómo se trabaja (reglas que no son obvias)

- **Una tarea del plan cada vez**, con evidencia, y **un commit por tarea**, con la convención `feat(story-X.Y): ...`, `test(story-X.Y): ...`, `docs(story-X.Y): ...`. **Sin línea `Co-Authored-By`** (instrucción de Juan, también para PR).
- **Flujo A** (historias 2-x): ATDD en rojo primero, log en `docs/evidence/impl2/red-X-Y.log`, commit del rojo, y solo después el código. El log rojo debe fallar **solo por comportamiento ausente** (ni importación, ni fixture, ni sintaxis) y ningún caso puede pasar "en vacío" (un 404 también "no escribe auditoría").
- **Guía E.6, parar y preguntar al usuario** si: hay que cambiar un ATDD ya commiteado, un cambio de contrato no previsto (`contracts.md`, `openapi.yaml`, `dto.py`), un umbral de k6 no se cumple, el CI falla sin reproducirse, o hay que editar un artefacto que el plan no autoriza. Nunca relajar una aserción ni fabricar/editar un log.
- Antes de cada commit: `ruff check .`, `python test/ci/schema_check.py`, `cmp src/dto.py planning/detailed-design/schemas/dto.py`, `diff` de los dos `sprint-status.yaml`, y la suite con cobertura (`--cov-fail-under=90`). `make` no está instalado: usar `.venv/Scripts/python.exe -m ruff check .`, `-m pytest tests -q --strict-markers --cov=src --cov-branch --cov-fail-under=90`.
- **No ejecutar `ruff format src`** entero: reescribe `src/dto.py` y `src/adapters/outbound/db/session_store.py`. Formatear archivos concretos.
- `migrations/001_*.sql` no se edita (su checksum está registrado y un test lo fija). Ya existe `002_proposals_failed_to_superseded.sql` (I2-30): el trigger de la 001 no permitía `failed -> superseded`.
- `docs/impl2-continuation/` y `test/traceability-matrix.md`, `test/nfr-evidence.md`: **no regenerar las dos matrices hasta las etapas de cierre y con aprobación de Juan.**
- `_bmad/bmm/config.yaml` (D-P6, `user_name: Julio`): no tocar sin permiso.
- No se han usado subagentes (no autorizados): las revisiones de código se hacen en línea (capa ciega, de casos límite y auditor de aceptación) y se presentan a Juan; **no se aplica ningún parche sin su aprobación**.
- Entorno Windows con Git Bash: `python3` es un stub (usar `.venv/Scripts/python.exe`); los heredocs con comillas complejas fallan, así que los scripts de edición se escriben con la herramienta de archivos y se ejecutan con `python -I`. Algunos archivos son CRLF (`contracts.md`, `planning/.../dto.py`): conservar los finales de línea.
- Cada historia se cierra con: revisión de código (hallazgos con severidad), auditoría de trampas D.4 (Ice Cream Cone, Flaky Sleeper, Mocking Mirage, Blindly Green, con mutación real), cierre D.5 (log de cobertura `flow-*-review-coverage.log`, estado `done` en historia y en las dos copias del sprint, entrada nueva en el log).

## 3. Hecho

Suite: **2053 pruebas, cobertura de ramas 97,74 %**, ruff y `schema_check` limpios. Todo empujado.

| Historia | Estado | Notas |
|---|---|---|
| 1-1 a 1-5, 3-1, 4-1, 4-2 | `done` | de Impl-1 y de la primera mitad de Impl-2 |
| 2-1 clasificación y rechazo | `done` | `Terminate all active jobs for CS-101` se rechaza; `cs201` no existe en el PDF (responde Entity Not Found) |
| 2-2 dry-run | `done` | `group#CS-101` con tres jobs en ejecución sobre `ws-gpu-02/05/08`; selector persistido y re-ejecutable; token aleatorio de 60 s configurable (`M12_GATE_TOKEN_TTL_SECONDS`); `POST /copilot/chat` responde rechazo + resumen + token en una respuesta |
| 2-3 confirmación | `done` | `POST /destructive/proposals` con solo `{proposal_id, gate_token}`; caducidad derivada (`snapshot + TTL`), un solo uso, revalidación con delta, claim atómico con auditoría |
| 2-4 ejecutor | `done` | ejecutor simulado único escritor de estado; despacho exactamente una vez; `actor=executor`; 5 s en el reloj falso; parcial → 502 con la propuesta; re-despacho con `supersedes`; 4 rutas del contrato servidas |
| Épico 2 | `done` | su retrospectiva sigue opcional |

Decisiones y hallazgos importantes (todos en el log): ids de propuesta **aleatorios** porque `GET /destructive/proposals/{pid}` devuelve el token y con ids secuenciales cualquiera podía ejecutar la propuesta de otro (I2-33); migración 002 (I2-30); ATDD congelados que se cambiaron con aprobación de Juan: 2-1 (rama `copilot_chat`, I2-22), 2-3 (`confirmed` → `executed`, I2-31), 2-4 (dos casos míos, I2-32) y 2-2 (comparación de ids, I2-33).

## 4. Lo que falta, en orden

### 4.1 Obligatorio (plan T-11 a T-22)

1. **1-6 Concurrencia y k6** (T-11, Flujo D). Falta crear la historia (`/bmad-create-story`), ATDD `tests/atdd/test_story_1_6.py`, despachador paralelo con `asyncio.gather` (el handler de `/copilot/query` pasa a `async def`, D-P7), `tests/nfr/copilot-load.js` (50 VUs, consulta S1 literal, **sin `sleep`**, umbrales `p(95)<800`, `http_req_failed` 0, checks de `RULE-CAT-04`, `policy#catalog.4.2` y `deepseek-coder`), ejecución con un solo worker de uvicorn y prosa falsa, y `k6 run --summary-export=docs/evidence/impl2/k6-12-5.json`. **Requiere instalar k6.** No relajar umbrales: si no cumple, optimizar o documentar y parar (E.6). Ojo con B-04: el orden de slots del recorder debe reservarse según los argumentos **antes** del `gather`.
2. **3-3 Runbooks y triage de nodo** (T-12, Flujo B). Intención `diagnose_node_triage` para `Node ws-gpu-11 is cordoned with code ERR_THERMAL_88. What should I do?`, pasos de `err-thermal-88.json` verbatim, `RUNBOOK_NOT_FOUND`, plantilla solo por configuración (NFR-10) y la ampliación del Anexo 12.6 (`Student Alex was denied model deepseek-coder. Diagnose and provide runbook.` debe enrutar a `diagnose_access_denial` y traer el runbook; clave = clase de diagnóstico, D-P4). También sirve `GET /api/v1/runbooks/{id}` (es la **única** operación del contrato aún sin servir).
3. **1-7 Consola React y Playwright** (T-13, Flujo E). Scaffold `console/` (Vite, React 19, TS), ruta `/helpdesk/copilot`, `tests/e2e/pages/CopilotConsolePage.ts` (todos los selectores ahí, sin `waitForTimeout`), `copilot-console.spec.ts` con los 10 casos de `test/test-design.md` §6.3.7, permisos de portapapeles, `playwright.config.ts` con dos `webServer` (uvicorn y `vite preview`, D-P5), `npm ci` y build de `console/` en el job `e2e` del CI, y un `trace.zip` en `docs/evidence/impl2/`. **Requiere Node, `npm ci` y los navegadores de Playwright.** Los criterios de UX-DR8 de 2-4 (etiquetas de la tarjeta de delegación, `alertdialog` y `Esc`) pertenecen aquí o a 1-8 y hoy son un hueco de cobertura que la matriz debe declarar.
4. **Cierre** (todo con aprobación de Juan donde el plan lo exige):
   - T-15 revisión de calidad de tests y pirámide real (`/bmad-testarch-test-review`, mutación en el guardia principal de cada historia).
   - T-16 evidencia NFR final (`/bmad-testarch-nfr`; reescribe `test/nfr-evidence.md`, esperado y autorizado en el plan).
   - T-17 logs finales (`final-coverage.log`, Playwright con `--trace on`, `grep` de `sleep`/`waitForTimeout` en 0).
   - T-18 matriz de trazabilidad (`/bmad-testarch-trace`; `gate_status` distinto de `NOT_EVALUATED`; resolver FR-06 y partes de FR-01, FR-02 y FR-16 según D-P2).
   - T-19 push y CI verde sobre el commit final, con el ID del run en el walkthrough.
   - T-20 `walkthrough-impl2.md` completo.
   - T-21 retrospectiva, log de IA y estado final.
   - T-22 README y limpieza (sin "Work in progress", comandos reproducibles).

### 4.2 Opcional (T-14, D-P2)
Solo con tiempo y en este orden: 4-3, 3-2, 3-4, 1-8. Si quedan fuera, la matriz debe declarar FR-06 y las partes de FR-01, FR-02 y FR-16 como "fuera del mínimo del Anexo". Es una decisión de Juan.

### 4.3 Pendientes de decisión o de confirmación humana
- **D-P2** (alcance de las opcionales) y **D-P6** (`user_name` del config de BMad): sin resolver.
- **Revisor "Pending"** en varias entradas del log (I2-23 en adelante): Juan las debe confirmar o corregir.
- **Aplazados** (`deferred-work.md`, secciones de 2-2, 2-3 y 2-4): propuestas que pueden quedar en `dispatched` si el proceso muere, delta de `CONFIRMATION_STALE` sin tope, tope de 50 `target_refs` solo en la aplicación (no en el contrato), truncado de `select` a 10 000 filas, padre parcialmente aplicado re-despachable varias veces, candado por propuesta durante toda la llamada al ejecutor. Ninguno bloquea la entrega; deben mencionarse en el walkthrough.

## 5. Para no tropezar

- **Fallos del simulador como semilla de pruebas**: para provocar un fallo de puerto se parchea la clase del adaptador **antes** de `create_app` (`tests/support/faults.py`, `PortFault`), porque `audited()` enlaza el método al construir. El ejecutor simulado tiene sus propios controles (`down`, `delay_seconds`, `apply_only`, `extra_applied`, `calls`, `requests`) y se obtiene con `client.app.state.container.port(ExecutorPort)`. El reloj falso es `SimClock` (`advance(seconds=...)`); nada duerme.
- Para listar rutas servidas en una prueba hay que descender por `_IncludedRouter` (ver `tests/api/test_contract_routes.py::_flatten`); `app.routes` solo no basta.
- `tests/api/test_contract_routes.py::SERVED_IN_THIS_STORY` debe coincidir con `openapi.yaml`: cada ruta nueva se añade ahí en el mismo commit.
- `fixtures/` ya contiene `group#CS-101` y los jobs 8901 a 8903 con campo `node`; los registros anteriores no se tocaron (IR-12).
- Un hallazgo que ningún test habría detectado salió de **probar la aplicación real** (la fuga del token). Antes de cerrar cada historia conviene una sonda con `TestClient` sobre el flujo completo.
- Los números de pruebas de dos mensajes de commit no son exactos (`c8af915` dice 2000 y fueron 1985); la verdad está en los logs de `docs/evidence/impl2/`.
