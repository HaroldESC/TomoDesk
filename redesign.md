# Rediseño: Sistema de Animación, Sprite Packs y Context Packs

**Estado:** En implementación. **F1, F2 y F3 completadas** (catálogo de intents, modelos,
loader `sprite-pack-v1`, `AnimationController`, sprite default migrado, integración GUI).
Pendientes: F4 (Context Packs + `VisualStateResolver`), F5 (Personality JSON), F6 (cierre).
**Versión objetivo:** `2.0.0` (rompe compatibilidad de formato de sprites).
**Fecha:** 2026-08-17

---

## 1. Resumen ejecutivo

El sistema actual mezcla tres conceptos en un único "estado de animación":

1. **Estado semántico** (qué quiere expresar el agente): `idle`, `talking`, `sleeping`, `happy`.
2. **Modo de reproducción** (cómo se muestra): loop, one-shot, hold, parpadeo temporizado.
3. **Transición visual** (cómo cambia entre animaciones).

Esto hace que cualquier sprite custom con más frames, otras velocidades u otras
animaciones rompa el modelo. La propuesta separa esos tres conceptos e introduce una
capa de abstracción nueva: **las intenciones visuales**.

Regla fundamental del rediseño:

> **El motor nunca pide una animación. El motor siempre pide una intención.**
> `request(INTENT)` — nunca `play("happy")`.

Esto desacopla por completo las integraciones (VSCode, Clip Studio, Spotify...) de los
recursos gráficos y permite que cualquier persona cree un sprite, una personalidad o una
integración sin depender de los otros dos.

### Decisiones tomadas (confirmadas con el usuario)

| Decisión | Elección |
| --- | --- |
| Nombre del 3er recurso | **Context Pack** |
| Ubicación de los clips de animación | **Dentro del Sprite Pack** |
| Formato de manifest | **JSON uniforme** para los tres packs |
| Migración del sprite actual | **Migrar y soportar solo el formato nuevo** |
| Catálogo inicial de intenciones | **Mínimo: 16 intenciones núcleo** |
| Nivel de detalle del documento | **Plan + especificación técnica** |

---

## 2. Problema actual (código real)

- `src/gui/sprites/animation_state.py` define 4 constantes fijas (`IDLE`, `TALKING`,
  `SLEEPING`, `HAPPY`). No hay estados semánticos más allá de esos.
- `src/gui/sprites/animation_manager.py` mezcla la semántica con la reproducción:
  `request_state` conoce estados, transiciones, variantes y one-shot (`exit_transition`).
- `src/gui/sprites/sprite_models.py` usa `AnimState` y `SubAnimation`, donde el parpadeo
  ("blink") está incrustado como sub-animación compuesta del estado `idle`.
- `data/sprites/default/sprite.json` codifica comportamientos en los nombres de estado:
  - `idle` es un `composite` con blink + look_around.
  - `talking` es un `simple` con 2 frames y loop.
  - `sleeping` es un `simple` con 1 frame y loop (estático en la práctica).
  - `happy` es un `one_shot` con `exit_transition: "idle"`.
- El flujo de entrada mapea eventos → estados directamente en
  `src/gui/windows/overlay_window.py` (`set_animation_state`), sin capa de intenciones.
- `src/personality/personality_pack.py` usa `manifest.yaml` + `phrases/*.yaml`. No existe
  ningún concepto de "context pack" ni catálogo de intenciones.

Problemas concretos que se resuelven:

- Cambiar `thinking` de 2 a 5 frames debe tocar **solo el Sprite Pack**.
- Añadir `coding` exige: que el Sprite Pack lo implemente **y** que un Context Pack lo
  solicite cuando corresponda (igual que una API: implementar no basta, hay que llamarla).
- El parpadeo no debe ser "el idle", sino un overlay independiente y opcional.

---

## 3. Principios de diseño

1. **Estado = qué siente/hace el agente.** No sabe de frames.
2. **Intención = qué quiere representar visualmente.** Un vocabulario semántico compartido.
3. **Clip = cómo se ve.** Frames, timing, modo de reproducción.
4. **Transición = cómo cambia.** Genérica + específica + fallback.
5. **Overlay = comportamiento simultáneo.** Parpadeo, bob, efectos, independientes del clip base.
6. **Fallback siempre.** Todo intent debe resolverse aunque el sprite no tenga nada mejor
   (último recurso: `IDLE`).
7. **Toda animación declara su modo**: `loop`, `once`, `hold`, `ping_pong` o `timed`.
8. **Toda animación define duración por frame o FPS.**
9. **Los packs son independientes y reutilizables.** Un sprite sirve con cualquier
   personalidad y cualquier contexto; ninguna pieza conoce las otras.
10. **El motor es tolerante a ausencias.** Sin Context Pack, sin clip, sin transición:
    nada se rompe, siempre hay un fallback.

---

## 4. Arquitectura objetivo

### 4.1 Tubería de decisiones

```
         Usuario / Sistema
                │
                ▼
      Context Providers (eventos)
                │   app.foreground, editor.typing, build.success,
                │   assistant_speaking, idle, sleep, user_typing...
                ▼
   VisualStateResolver (evento → intent)
                │   prioridades + estado del agente + contexto
                ▼
     Intención visual (VisualIntent)
                │   IDLE, TALKING, WORKING_CODE, CELEBRATE...
                ▼
      Sprite Pack (intent → clip, fallbacks)
                │   intent_map + fallback_chain
                ▼
    AnimationController (reproduce clips)
                │   timing, transiciones, overlays, variantes
                ▼
                Render (QPixmap)
```

Cada bloque tiene **una única responsabilidad**:

| Bloque | Responsabilidad |
| --- | --- |
| Context Providers | Producir eventos del sistema/apps (aún no hablan de sprites). |
| VisualStateResolver | Traducir eventos a intenciones visuales. No hay imágenes aquí. |
| Sprite Pack | Decidir cómo representar cada intención (o a qué hacer fallback). |
| AnimationController | Reproducir clips. No piensa, solo muestra. |

### 4.2 Los cuatro recursos

1. **Sprite Pack** — cómo se ve el personaje: imágenes, clips, `intent_map`, `fallbacks`.
2. **Personality Pack** — cómo se comporta: tono, reglas conversacionales, emociones.
3. **Context Pack** — qué significan determinados eventos de apps/sistema (producen intents).
4. **Animation Controller** — componente interno del motor que reproduce los clips.

No existe un "Animation Pack" instalable: los clips dependen directamente de las imágenes
del sprite, por lo que viven dentro del Sprite Pack.

### 4.3 Ubicación de los packs en disco

```
data/
├── sprites/
│   └── default/
│       ├── manifest.json
│       ├── clips/        (opcional: clips externos; por defecto inline en manifest)
│       └── assets/       (PNG de frames)
├── personality_packs/
│   └── friendly/
│       ├── manifest.json
│       └── phrases/
│           └── *.json
└── context_packs/
    └── vscode/
        ├── manifest.json
        └── (sin assets)
```

Los tres tipos de pack aceptan **directorio y ZIP** (reutilizando la validación de
seguridad de `src/personality/zip_security.py`).

---

## 5. Catálogo de intenciones visuales

Catálogo oficial núcleo (16). Es la "interfaz" del sistema: un Context Pack nunca pide
`coding` o `happy`; pide `WORKING_CODE` o `CELEBRATE`. Luego cada Sprite Pack decide cómo
representarlas.

| Intención | Uso típico |
| --- | --- |
| `IDLE` | Reposo, estado por defecto. |
| `TALKING` | El agente está hablando. |
| `LISTENING` | El agente escucha al usuario. |
| `THINKING` | El agente está procesando/generando. |
| `SLEEPING` | Modo reposo/dormido. |
| `CELEBRATE` | Éxito: compilación correcta, tarea completada. |
| `SURPRISED` | Sorpresa, notificación inesperada. |
| `CONFUSED` | Error, algo salió mal. |
| `WORKING_CODE` | El usuario programa (VSCode, etc.). |
| `WORKING_ART` | El usuario dibuja (Clip Studio, etc.). |
| `READING` | El usuario lee o navega. |
| `WRITING` | El usuario escribe en general. |
| `GAMING` | El usuario juega. |
| `WAITING` | Espera, operación en curso. |
| `LOOKING` | Atención a algo concreto. |
| `NOTIFICATION` | Notificación/aviso al usuario. |

El catálogo vive en `src/core/intents.py`. Es **extensible** (un Context Pack o un Sprite
Pack pueden declarar intents custom), pero lo recomendado es usar el catálogo oficial.

Los intents se referencian en mayúsculas `SNAKE_CASE` en los JSON.

---

## 6. Formato de los packs (JSON uniforme)

Todos los manifest usan JSON. Todos declaran `format` con versión para validación
(jsonschema) y evolución futura del esquema.

### 6.1 Sprite Pack — `manifest.json`

Responsabilidad: **"¿Qué animaciones sabe representar este personaje y cómo se ven?"**
No sabe cuándo usarlas.

```json
{
  "id": "default",
  "name": "Default",
  "version": "1.0.0",
  "format": "sprite-pack-v1",
  "assets": {
    "image_format": "png",
    "frame_width": 500,
    "frame_height": 500
  },
  "intent_map": {
    "IDLE": "idle",
    "TALKING": "talking",
    "SLEEPING": "sleeping",
    "CELEBRATE": "happy"
  },
  "fallbacks": {
    "LISTENING": "TALKING",
    "THINKING": "IDLE",
    "WORKING_CODE": "IDLE",
    "WORKING_ART": "IDLE",
    "READING": "IDLE",
    "WRITING": "IDLE",
    "GAMING": "CELEBRATE",
    "WAITING": "IDLE",
    "LOOKING": "IDLE",
    "NOTIFICATION": "IDLE",
    "SURPRISED": "IDLE",
    "CONFUSED": "IDLE"
  },
  "clips": {
    "idle": {
      "mode": "loop",
      "frames": [
        {"file": "assets/idle_0.png", "duration_ms": 4000}
      ],
      "interruptible": true,
      "overlays": ["blink"]
    },
    "blink": {
      "mode": "timed",
      "interval_ms": 4000,
      "frames": [
        {"file": "assets/idle_1.png", "duration_ms": 100}
      ],
      "priority": 5
    },
    "talking": {
      "mode": "loop",
      "frames": [
        {"file": "assets/talk_0.png", "duration_ms": 100},
        {"file": "assets/talk_1.png", "duration_ms": 100}
      ],
      "interruptible": true
    },
    "sleeping": {
      "mode": "hold",
      "frames": [
        {"file": "assets/sleep_0.png", "duration_ms": 1000}
      ],
      "interruptible": false
    },
    "happy": {
      "mode": "once",
      "return_to": "IDLE",
      "frames": [
        {"file": "assets/happy_0.png", "duration_ms": 150},
        {"file": "assets/happy_1.png", "duration_ms": 150}
      ],
      "interruptible": true
    }
  }
}
```

**Campos de un clip:**

| Campo | Tipo | Obligatorio | Descripción |
| --- | --- | --- | --- |
| `mode` | string | sí | `loop`, `once`, `hold`, `ping_pong`, `timed`. |
| `frames` | array | sí | Lista de `{file, duration_ms}`. |
| `interval_ms` | int | no | Solo `timed`: cada cuánto se dispara. |
| `return_to` | intent | no | Solo `once`: intent al que volver al terminar. |
| `interruptible` | bool | sí | Si puede ser interrumpido por otro intent. |
| `priority` | int | no | Prioridad frente a otros clips concurrentes. |
| `transition_in_ms` | int | no | Duración de la transición de entrada. |
| `transition_out_ms` | int | no | Duración de la transición de salida. |
| `overlays` | array | no | Nombres de clips overlay que se aplican encima. |

**Variantes por emoción** (soporta el caso actual de `variants`): un clip puede declarar
`variants` condicionadas al estado emocional del `StateManager`:

```json
"idle": {
  "mode": "loop",
  "frames": [{"file": "assets/idle_0.png", "duration_ms": 4000}],
  "variants": {
    "tired": {"condition": {"energy": [0.0, 0.3]}, "clip": "idle_tired"},
    "alert": {"condition": {"energy": [0.7, 1.0]}, "clip": "idle_alert"}
  }
}
```

**Reglas del `intent_map` + `fallbacks`:**

1. Dado un intent, se busca en `intent_map`. Si existe, se usa el clip indicado.
2. Si no existe (o el clip no pudo cargarse), se sigue la cadena de `fallbacks`
   (intent → intent) hasta encontrar un intent con clip.
3. Último recurso: `IDLE`. Si tampoco existe, se muestra un frame de error.

### 6.2 Context Pack — `manifest.json`

Responsabilidad: **"¿Qué significa determinados eventos de una aplicación/sistema?"**
Produce intenciones visuales. No conoce sprites.

```json
{
  "id": "vscode",
  "name": "VS Code",
  "version": "1.0.0",
  "format": "context-pack-v1",
  "app": "vscode",
  "events": {
    "build.success": {"intent": "CELEBRATE", "priority": 3},
    "build.failed": {"intent": "CONFUSED", "priority": 3},
    "editor.typing": {"intent": "WORKING_CODE", "priority": 2},
    "editor.idle": {"intent": "READING", "priority": 1}
  }
}
```

- Los **eventos** son el contrato con los *Context Providers* del sistema
  (detección de ventana activa en `src/system/window_manager.py`, monitoreo de build, etc.).
- `priority` define qué intent gana cuando varios eventos compiten (junto con el estado
  del agente).
- Un Context Pack para Clip Studio sería:

```json
{
  "id": "clip_studio",
  "name": "Clip Studio",
  "format": "context-pack-v1",
  "app": "clip_studio",
  "events": {
    "canvas.drawing": {"intent": "WORKING_ART", "priority": 2},
    "export.done": {"intent": "CELEBRATE", "priority": 3}
  }
}
```

### 6.3 Personality Pack — migración a JSON

Responsabilidad: **"¿Cómo se comporta el personaje?"** No contiene nada visual.

```json
{
  "id": "friendly",
  "name": "Friendly",
  "version": "1.0.0",
  "format": "personality-pack-v1",
  "conversation": {
    "style": "casual",
    "proactive": true,
    "comment_frequency": "medium"
  },
  "emotions": {
    "positive_threshold": 0.6,
    "negative_threshold": -0.4
  }
}
```

Las frases pasan de `phrases/*.yaml` a `phrases/*.json`. `PersonalityPackManager` mantiene
su API pública (`scan_packs`, `set_active_pack`, `get_phrases`, ...) pero lee JSON.

### 6.4 Validación

- Esquemas jsonschema por `format` (patrón ya usado en `src/gui/sprites/sprite_loader.py`).
- Validación de assets (formato PNG, relación de aspecto, tamaño mínimo/máximo,
  límite de frames por clip) es **validación de assets**, no lógica central.
- Si un pack falla la validación, se registra el error y se ignora ese pack (nunca romper
  la app). El sprite de error existente se mantiene como último recurso.

---

## 7. Motor de animación (AnimationController)

Reemplaza a `AnimationManager` (`src/gui/sprites/animation_manager.py`).

### 7.1 Reproducción de clips

- **`loop`** — ciclo continuo (talking).
- **`once`** — reproduce una vez y vuelve a `return_to` (happy_react).
- **`hold`** — se queda en el primer frame (sleeping, o loop lento si el creador usa `loop`
  con `duration_ms` altos).
- **`ping_pong`** — va y viene entre el primer y último frame.
- **`timed`** — se dispara cada `interval_ms` (blink).

El motor **nunca asume** cuántos frames tiene un clip ni su velocidad: todo lo define el
clip. Un sprite custom con 1, 2, 5 u 8 frames funciona igual.

La velocidad global (`set_speed`, usada hoy por el sistema para ajustar el talking según
la fluidez del LLM) se mantiene como multiplicador sobre los `duration_ms`.

### 7.2 Transiciones

- Transiciones **específicas entre clips** declaradas en el Sprite Pack
  (`transitions: {"idle_to_talking": {...}}`), reutilizando la mecánica actual.
- **Fallback genérico** si no existe transición específica: crossfade corto
  (por defecto 80-120 ms) o cambio directo.
- Si el sprite no declara ninguna, el motor hace cambio directo. Nunca falla.

### 7.3 Overlays

- Capas independientes que coexisten con el clip base (blink, bob, mood).
- El blink deja de ser "el idle": es un clip `timed` declarado como overlay de `idle`.
- Implementación inicial (sprites planos): mientras el overlay está activo, se muestran
  sus frames; al terminar vuelve al frame base del clip. La composición real por capas con
  transparencia queda como evolución futura (Roadmap).
- Si un sprite no declara overlays, simplemente no hay parpadeo: decisión del creador.

### 7.4 Variantes emocionales

Un clip puede tener `variants` condicionadas al `emotion_state` del `StateManager`
(energía, curiosidad, etc.), reemplazando el mecanismo actual de `AnimState.variants`.

### 7.5 Interrupción y colas

- `interruptible: false` bloquea el cambio mientras el clip esté activo (sleeping).
- Los intents entrantes se **encolan** hasta que el clip actual lo permita (comportamiento
  actual de `_queued_state`).
- Los clips `once` no interrumpibles pueden declarar `return_to`.

### 7.6 Resolución de intents (VisualStateResolver)

Combina tres fuentes con prioridad:

| Fuente | Prioridad (por defecto) | Ejemplo |
| --- | --- | --- |
| Agente (LLM/agente) | 100 | `assistant_speaking` → `TALKING`, `thinking` → `THINKING` |
| Context Pack | 10 | `build.success` → `CELEBRATE` |
| Idle/espera | 0 | sin actividad → `IDLE` |

Reglas:

- Cuando el agente habla o piensa, su intent **pausa** el intent de contexto.
- Al terminar, vuelve el último intent de contexto vigente (si sigue aplicando).
- Los intents `once` de contexto (p.ej. `CELEBRATE`) se reproducen y vuelven al intent base.
- El resolver conserva el "intent base" (contexto) y el "intent transitorio" (agente/once).

---

## 8. Módulos Python y firmas

### Nuevos módulos

**`src/core/intents.py`**

```python
class VisualIntent(str, Enum):
    IDLE = "IDLE"
    TALKING = "TALKING"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SLEEPING = "SLEEPING"
    CELEBRATE = "CELEBRATE"
    SURPRISED = "SURPRISED"
    CONFUSED = "CONFUSED"
    WORKING_CODE = "WORKING_CODE"
    WORKING_ART = "WORKING_ART"
    READING = "READING"
    WRITING = "WRITING"
    GAMING = "GAMING"
    WAITING = "WAITING"
    LOOKING = "LOOKING"
    NOTIFICATION = "NOTIFICATION"

OFFICIAL_INTENTS: frozenset[VisualIntent]
def normalize_intent(value: str) -> Optional[VisualIntent]
def is_official(intent: VisualIntent) -> bool
```

**`src/core/visual_state_resolver.py`**

```python
@dataclass
class IntentRequest:
    intent: VisualIntent
    priority: int
    source: str            # "agent" | "context:<pack_id>"
    one_shot: bool = False

class VisualStateResolver:
    def set_agent_intent(self, intent: Optional[VisualIntent]) -> None
    def push_event(self, event: str, payload: dict) -> None
    def resolve(self, emotion_state: dict) -> VisualIntent
```

**`src/context/context_pack.py`**

```python
class ContextPackManager:
    def __init__(self, packs_dir: str = "data/context_packs"): ...
    def scan_packs(self) -> None
    def resolve_event(self, event: str, payload: dict) -> Optional[IntentRequest]
    def list_packs(self) -> list[str]
    def set_active_packs(self, pack_ids: list[str]) -> None
```

### Módulos modificados

**`src/gui/sprites/sprite_models.py`** — reemplazar `AnimState`/`SubAnimation` por
modelos declarativos:

```python
@dataclass
class ClipFrame:
    file: str
    duration_ms: int

@dataclass
class AnimationClip:
    name: str
    mode: str                    # loop | once | hold | ping_pong | timed
    frames: list[ClipFrame]
    interval_ms: int = 0
    return_to: Optional[str] = None
    interruptible: bool = True
    priority: int = 0
    transition_in_ms: int = 0
    transition_out_ms: int = 0
    overlays: list[str] = field(default_factory=list)
    variants: dict = field(default_factory=dict)

@dataclass
class SpritePackData:
    id: str
    name: str
    version: str
    assets: dict                 # image_format, frame_width, frame_height
    intent_map: dict[str, str]
    fallbacks: dict[str, str]
    clips: dict[str, AnimationClip]
    transitions: dict[str, dict] = field(default_factory=dict)
```

**`src/gui/sprites/sprite_loader.py`** — nuevo esquema `sprite-pack-v1`, carga
`manifest.json` + assets, devuelve `SpritePackData` + `Dict[str, List[QPixmap]]`.

**`src/gui/sprites/animation_manager.py` → `src/gui/sprites/animation_controller.py`**

```python
class AnimationController:
    def __init__(self, pack: SpritePackData, frames: Dict[str, List[QPixmap]]): ...
    def request_intent(self, intent: VisualIntent, emotion_state: dict) -> bool
    def force_intent(self, intent: VisualIntent) -> None
    def update(self, dt_ms: float) -> None
    def get_current_pixmap(self) -> QPixmap
    def set_speed(self, multiplier: float) -> None
```

- La resolución `intent → clip` (con `fallbacks`) vive dentro del controller, usando
  solo `SpritePackData` (no conoce Context Packs).
- Se elimina `src/gui/sprites/animation_state.py` (las constantes se sustituyen por
  `VisualIntent` en `src/core/intents.py`).

**`src/gui/sprites/sprite_manager.py`** — orquesta resolver + controller:

```python
class SpriteManager:
    def __init__(self, config: dict, resolver: VisualStateResolver, ...): ...
    def update(self): ...        # llama resolver.resolve() y controller.request_intent()
    def get_current_pixmap(self) -> QPixmap: ...
    def set_character_size(self, size: int) -> None: ...
    def start_animation(self) / stop_animation(self): ...
```

**`src/gui/windows/overlay_window.py`** — sustituye `set_animation_state(AnimationState.X)`
por llamadas al resolver o a intents (`TALKING`, `SLEEPING`, ...). El detector de ventana
activa emite eventos (`app.foreground`) que el resolver traduce vía Context Packs.

**`src/personality/personality_pack.py`** — leer `manifest.json` + `phrases/*.json`,
manteniendo la API actual.

**`src/system/window_manager.py`** — emitir eventos de aplicación
(`app.foreground: <app>`, `app.closed`) en lugar de exponer solo detección.

**`config.example.yaml` / `config.yaml`** — sección nueva:

```yaml
ui:
  sprite:
    active: default
personality:
  active: friendly
context:
  active_packs: [vscode]   # lista de Context Packs activos
```

---

## 9. Flujo de ejecución (ejemplo VSCode)

1. El usuario activa VSCode. `window_manager.py` emite `app.foreground: {app: "Code"}`.
2. `ContextPackManager.resolve_event` consulta los packs activos. El pack `vscode` no
   tiene handler para `app.foreground` (el intent lo decide el siguiente evento).
3. El usuario escribe. El provider de VSCode emite `editor.typing`.
4. El Context Pack responde `WORKING_CODE` (prioridad 2). El resolver lo marca como
   intent base.
5. `SpriteManager.update` → `resolve()` devuelve `WORKING_CODE` → el controller consulta
   `intent_map["WORKING_CODE"]`. Este sprite no la define, aplica `fallbacks`:
   `WORKING_CODE → IDLE`. Reproduce el clip `idle`.
6. El agente decide hablar. `set_agent_intent(TALKING)` (prioridad 100) pausa el contexto.
7. Al terminar de hablar, vuelve a `WORKING_CODE` → `IDLE`.
8. Compilación correcta: `build.success` → `CELEBRATE` (one-shot, prioridad 3).
   El sprite la mapea al clip `happy` (`once`, `return_to: IDLE`). Al terminar,
   el resolver restaura el intent base.

Nada de esto rompe si no existe Context Pack ni si el sprite no implementa el intent:
siempre hay fallback a `IDLE`.

---

## 10. Plan de migración

El camino conserva los 4 estados actuales como punto de partida, pero solo con el
formato nuevo (decisión tomada):

1. **Catálogo de intents** en `src/core/intents.py` (16 núcleo).
2. **Migrar `data/sprites/default/`** al nuevo formato `manifest.json`:
   - `idle` (composite blink+look_around) → clip `idle` + overlay `blink`.
   - `talking` → clip `talking` (loop).
   - `sleeping` → clip `sleeping` (hold, `interruptible: false`).
   - `happy` → clip `happy` (once, `return_to: IDLE`).
   - `intent_map` mapea los 4 intents que usa el agente.
   - Los PNG se mueven a `assets/`.
3. **Actualizar `overlay_window.py`** para usar intents en vez de `AnimationState`.
4. **Migrar `PersonalityPackManager`** a JSON (`manifest.json`, `phrases/*.json`).
5. **Migrar tests** de `test_animation_manager.py` y `test_sprite_manager.py` al nuevo API.
6. Actualizar `docs/TECHNICAL_SPEC.md` al finalizar.

Nota: la migración de personalidad a JSON y de los nombres de carpetas de assets puede
hacerse en una fase posterior sin bloquear el sistema de animación.

---

## 11. Fases de implementación

| Fase | Contenido | Salida verificable |
| --- | --- | --- |
| **F1. Base** | `src/core/intents.py`, modelos (`sprite_models.py`), nuevo loader con schema `sprite-pack-v1`. | `pytest tests/test_loader* -v` verde. |
| **F2. Motor** | `AnimationController` (modos, timing, transiciones, overlays, variantes, colas, fallbacks). | Tests del controller verdes. |
| **F3. Integración GUI** | Migrar `data/sprites/default`, conectar `overlay_window.py` a intents. | `python main.py --gui` sin errores; los 4 estados funcionan. |
| **F4. Context Packs** | `src/context/`, `VisualStateResolver`, providers de apps (VSCode). | Resolver + contexto + prioridades verificados con tests. |
| **F5. Personalidad JSON** | Migrar `PersonalityPackManager` a JSON. | Tests de personality verdes. |
| **F6. Cierre** | Actualizar `TECHNICAL_SPEC.md`, limpiar módulos obsoletos (`animation_state.py`), suite completa. | `pytest tests/ -v` completo en local y CI. |

Cada fase termina con la suite de tests relacionada en verde antes de continuar.

---

## 12. Plan de pruebas

Nuevos tests:

- **`tests/test_intents.py`** — catálogo oficial, `normalize_intent`, validación de intents custom.
- **`tests/test_animation_controller.py`** — modos `loop`/`once`/`hold`/`ping_pong`/`timed`;
  duraciones por frame; transiciones específicas y fallback; overlays (blink) activo y
  retorno al frame base; variantes por emoción; interrupción y colas; `set_speed`.
- **`tests/test_sprite_loader.py`** (reemplaza al actual) — validación `sprite-pack-v1`,
  errores de asset, `intent_map`/`fallbacks`, sprite de error.
- **`tests/test_context_pack.py`** — resolución de eventos, prioridades, packs activos,
  seguridad ZIP, ausencia de pack.
- **`tests/test_visual_state_resolver.py`** — prioridad agente vs contexto, one-shot,
  restauración del intent base.

Tests existentes que se migran: `test_animation_manager.py`, `test_sprite_manager.py`.

CI (`ubuntu-latest` + `windows-latest`, Python 3.12) mantiene el mismo esquema actual.

---

## 13. Roadmap futuro

**Aplicaciones / Context Packs previstos** (a crear por la comunidad o en iteraciones
futuras, sin tocar sprites ni personalidad):

- Clip Studio (`WORKING_ART`), Blender, Photoshop, Unreal.
- Spotify (`LISTENING`/`WAITING`), Discord (`NOTIFICATION`), Minecraft (`GAMING`).

**Evoluciones del motor:**

- Composición real por capas con transparencia (overlays con alpha sobre el clip base).
- Catálogo de intents ampliado (30-40) cuando aparezcan casos de uso que lo justifiquen.
- Soporte de FPS global además de `duration_ms` por frame.
- Efectos procedurales (shake, glow, bounce) como overlays especiales.
- Sonidos por evento en Context Packs (usando `discover_sounds` de personality).

---

## 14. Fuera de alcance

- Implementación de código (este documento es la propuesta; la implementación se hará en
  sesiones posteriores, idealmente con subagentes por fase).
- Nuevos assets gráficos para el sprite `default`.
- UI de Settings para gestionar Context Packs (se añadirá cuando el motor exista).

---

## 15. Decisiones tomadas y su justificación

| Decisión | Justificación |
| --- | --- |
| Context Pack (no Interaction/Behavior Pack) | Nombre más descriptivo del "cuándo" usar cada intención. |
| Clips dentro del Sprite Pack | Dependen de las imágenes del sprite; un recurso instalable aparte añade complejidad sin beneficio claro. |
| JSON uniforme | Un solo parser/esquema/validador en todo el sistema. |
| Solo formato nuevo (migrar) | Evita código muerto y ramas de compatibilidad; el sprite default se migra. |
| 16 intents núcleo | Cubre los casos actuales y los Context Packs previstos (VSCode/Clip Studio/Spotify/Discord). |
| El motor pide intenciones, nunca animaciones | Desacopla integraciones de recursos gráficos; es la base para una comunidad de packs independientes. |