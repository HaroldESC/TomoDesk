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

---

## Escalabilidad del Código

| Aspecto | Estado actual |
|---|---|
| **Thread safety** | Locks en DB y estado; signals Qt para GUI; workers en threads daemon |
| **Modularidad** | 7 paquetes independientes (config, core, gui, llm, memory, personality, system) |
| **Animaciones** | Motor data-driven con JSON Schema; intents + clips; cualquier sprite con manifest.json funciona |
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
