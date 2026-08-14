# TomoDesk — Visión y Roadmap

---

## ¿Qué es TomoDesk?

TomoDesk es un compañero de escritorio virtual que fusiona un personaje interactivo (estilo Desktop Mate) con un agente de productividad asistido por IA. Vive en tu escritorio, reacciona a lo que haces, puede conversar contigo y ayudarte activamente en tareas diarias, todo de forma local y privada.

Inspirado en la ternura de los desktop companions, en la profundidad conversacional de los chatbots con IA (como character.ai) y en la necesidad de un asistente que realmente entienda tu contexto, TomoDesk busca ser mucho más que una mascota: es un compañero de escritorio que conoce tus hábitos, te ayuda a concentrarte, te recuerda cosas importantes y crece contigo.

---

## Inspiración y Motivación Personal

| Referente | Aporte |
|---|---|
| **Desktop Mate** | Personajes sobre ventanas, seguimiento de cursor, gestos y alarmas. *Limitación:* solo personajes licenciados, sin importación ni conversaciones profundas. |
| **Character.ai** | Conversación con personajes mediante IA generativa. *Idea:* llevar esa capacidad a un compañero que perciba el entorno. |
| **Unity-chan: Desktop Companion** | Modo streamer, minijuegos, teléfono virtual, tutorial tipo novela visual. Modelo de integración de historia y personalidad. |
| **chatWaifu** | Voz clonable, importación de modelos MMD, ejecución de scripts, gran extensibilidad. |
| **CielChan** | Captura de escritorio completo, modelos VRM, interfaz radial. |
| **LocalCowork (Liquid AI)** | Agente de escritorio con modelos ligeros LFM para tareas rápidas y privadas . |

TomoDesk aprende de todos estos referentes: interacción física, conversación contextual, utilidad real, personalización y eficiencia.

---

## Filosofía de Diseño

- **Local-first, privacidad extrema:** procesamiento principal con Ollama (y otros backends); APIs externas opcionales.
- **Modular y configurable:** el usuario decide qué funciones activa, el nivel de interacción y puede ocultar al personaje cuando necesite concentrarse.
- **Crecimiento orgánico:** funcionalidades experimentales se habilitan bajo demanda, no son obligatorias.
- **Interfaz por capas:** interacción rápida sin saturar.

---

## Roadmap por Fases

### Fase 1 — Fundación del Agente (MVP de IA) ✅ Completada (Alpha 0.1.x)

- Backend de IA conversacional con memoria local (SQLite + ChromaDB)
- Integración con Ollama y backends compatibles con OpenAI
- Sistema de observaciones espontáneas basado en reglas (triggers del sistema)
- Estado emocional con 5 variables y decaimiento temporal
- Memoria episódica automática con resúmenes generados por LLM
- Interfaz mínima: chat, menú contextual, diálogos de notas/recordatorios/memorias
- Icono en bandeja del sistema con menú contextual

### Fase 2 — Personaje 2D y Overlay ✅ Completada (Beta 0.2.x)

| Subfase | Estado |
|---|---|
| **2.0 i18n** | ✅ Internacionalización EN/ES con detección automática |
| **2.1 Overlay Window** | ✅ Ventana transparente, siempre encima, arrastrable, sin foco |
| **2.2 Sprite & Animations** | ✅ Sprites procedurales, 4 estados de animación (idle/talking/sleeping/happy) |
| **2.3 Speech Bubble** | ✅ Burbuja con typewriter, indicador de pensamiento, fade out, bordes de pantalla |
| **2.4 Interaction Layers** | ✅ Click/doble click/inline input/menú contextual |
| **2.5 Visual Cues** | ✅ Pistas visuales desactivables (tooltips one-shot) |
| **2.6 Audio-Reactive Dancing** | ✅ Baile reactivo al sistema/micrófono, detección de beats, modo emocional |
| **2.7 Window-Sitting** | ✅ Personaje sobre ventanas reales, multi-monitor, animación suave |
| **2.8 Personality Packs** | ✅ Carga de frases desde ZIP/directorio, prioridad sobre comments.yaml |
| **2.9 Animation System Redesign** | ✅ Motor data-driven con JSON Schema, estados compuestos, variantes emocionales, transiciones |
| **Post-2.9** | ✅ Sprite procedural tipo gato, Settings 5 pestañas, sprites custom desde UI |

**Logros adicionales en Fase 2:**
- Tema oscuro (Catppuccin Mocha) + claro con burbujas QFrame con border-radius
- Barra de estado humanizada (texto amigable en vez de valores crudos)
- Menú rediseñado con nombre del personaje y accesos directos (Ctrl+N/R/E/Q)
- Guía de interacción desde el menú Ayuda
- Integración de personality packs en vivo desde Settings sin reiniciar
- Eliminación de sprites personalizados desde la UI

### Fase 3 — Optimización y Pulido ✅ Completada

| Subfase | Estado |
|---|---|
| **3.0 Lazy Loading SentenceTransformer** | ✅ Modelo de embeddings cargado bajo demanda, no al inicio |
| **3.1 Deferred Audio Reactivity** | ✅ sounddevice inicializado asíncronamente tras mostrar ventana |
| **3.2 Background LLM Check** | ✅ Verificación de disponibilidad en thread separado |
| **3.3 Parallel Initialization** | ✅ Componentes independientes inicializados con ThreadPoolExecutor |
| **3.4 Splash Screen** | ✅ Ventana de carga translúcida "Cargando..." |
| **3.5 Lazy Module Imports** | ✅ Todos los imports pesados movidos a ámbito local |
| **3.6 QThread Init** | ✅ _initialize() ejecutado en QThread para no bloquear la GUI |

**Resultado:** Startup reducido de ~52s a ~13s, y el módulo main.py carga en ~0.2s.

### Fase 3b — Seguridad 🚧 En progreso

| Subfase | Estado |
|---|---|
| **CredentialManager** | ✅ API keys en keyring del SO con fallback a env y config |
| **SensitiveDataFilter** | ✅ Redacción de credenciales en logs |
| **save_config()** | ✅ Serialización YAML centralizada que filtra secrets |
| **Thread safety audit** | ✅ Locks en DatabaseManager y StateManager; signals Qt para GUI |

### Fase 4 — Personalidad Reactiva y Comportamientos Autónomos 🚧 Planeado

- Caminata autónoma por el escritorio (movimiento browniano) modulada por energía
- Window-sitting adaptativo: detecta bordes de ventanas y se sienta un rato
- Comportamientos modulados por estado emocional (energía, felicidad, curiosidad)
- Sueño por energía baja con regeneración automática (ya implementado)
- Modos Focus/DND desactivan comportamientos autónomos

### Fase 5 — Integración Avanzada con el Sistema *(planeado)*

- Pomodoro visual y recordatorios de descanso
- Widgets opcionales: clima, reloj, música
- Importación mejorada de sprites/modelos 2D personalizados
- Skins de interfaz: TomoPhone como alternativa

### Fase 6 — Voz, Visión, Modelos 3D y Arquitectura Híbrida *(largo plazo)*

- Voz (Whisper + TTS), cámara (MediaPipe), modelos 3D (VRM, MMD)
- Arquitectura híbrida: modelo pequeño para monitoreo, modelo grande para personalidad
- Habilidades experimentales: organización de ventanas, control de volumen, ejecución de scripts
- Modo streamer y minijuegos
- Plugins completos (tipo extensiones de VS Code)

---

## Sistema de Sueño

El personaje tiene dos mecanismos independientes para dormir:

| Trigger | Mecanismo |
|---|---|
| **Inactividad del sistema** | Usa EventMonitor para detectar ausencia real de mouse/teclado (GetLastInputInfo). Tiempo configurable (default 5 min). |
| **Energía baja** | Si energy < 0.05, el personaje se duerme aunque el usuario esté activo. |

**Durante el sueño:**
- Animación en cámara lenta (~5 FPS)
- Burbuja oculta
- Window-sitting y audio suspendidos
- Energía se regenera (~0.1/minuto)
- Al despertar, dice algo distinto según si ya descansó o aún está cansada

---

## Sistema de Observaciones Espontáneas

El personaje reacciona a eventos del sistema y del usuario de forma espontánea, no solo cuando se le habla:

- **Disparadores:** apertura/cierre de apps, tiempo de sesión, actividad/inactividad, recursos del sistema (CPU/RAM altos), trasnoche, cambios frecuentes de ventana
- **Fuentes:** frases del pack de personalidad activo (prioritario), comments.yaml por idioma
- **Control:** cooldown configurable, máximo por hora, modos Focus/DND silencian todo

---

## Arquitectura de Seguridad

| Capa | Mecanismo |
|---|---|
| **Credenciales** | Keyring del SO (Windows Credential Manager, macOS Keychain, Linux libsecret) |
| **Respaldo** | Variable de entorno LLM_API_KEY |
| **Config YAML** | save_config() filtra todas las keys sensibles antes de escribir |
| **Logs** | SensitiveDataFilter redacta api_key, token, secret, sk-, gsk_, hf_ |
| **Audio** | Sin almacenamiento ni transmisión; aviso de privacidad one-time |

---

## Modelos de IA y Arquitectura Híbrida

| Proveedor | Endpoint por defecto |
|---|---|
| **Ollama** | `http://localhost:11434` |
| **OpenAI Compatible** | Cualquier endpoint (LM Studio, vLLM, Groq, Jan, AnythingLLM) |

- **Hoy:** un solo modelo configurable vía `config.yaml`
- **Futuro:** dos modelos en paralelo — uno pequeño siempre cargado (clasificación, monitoreo) y uno grande bajo demanda con precarga predictiva
- La arquitectura ya soporta múltiples proveedores (Ollama, OpenAI-compatible)

---

## Interfaz y Skins

| Fase | Interfaz disponible |
|---|---|
| Fase 1 | Ventana con chat y menú contextual |
| Fase 2 | Overlay + burbuja + inline input + menú contextual |
| Fase 2.9 | Sprites custom desde UI, tema oscuro/claro |
| Fase 5+ | TomoPhone, tablet, libro, panel holográfico, etc. |

- Cambio manual entre skins
- Asociación opcional con arquetipos de personaje

---

## Escalabilidad del Código

| Aspecto | Estado actual |
|---|---|
| **Thread safety** | Locks en DB y estado; signals Qt para GUI; workers en threads daemon |
| **Modularidad** | 7 paquetes independientes (config, core, gui, llm, memory, personality, system) |
| **Animaciones** | Motor data-driven con JSON Schema; cualquier sprite con sprite.json funciona |
| **Personality Packs** | Carga desde ZIP/directorio; frases con prioridad; instalación drag-and-drop |
| **i18n** | Sistema completo EN/ES con detección automática y placeholders |
| **Tests** | 297+ tests con pytest, MockChroma, mock_i18n, fixtures centralizadas |

---

## Scripts y Modularidad (Futuro)

| Nivel | Descripción |
|---|---|
| 1 | Reacciones personalizadas |
| 2 | Automatización del escritorio y productividad |
| 3 | Comandos personalizados |
| 4 *(largo plazo)* | Plugins completos (tipo extensiones de VS Code) |

La arquitectura incluirá un sistema de hooks/eventos para facilitar esta extensibilidad. Por ahora los personality packs son el mecanismo de extensión disponible.
