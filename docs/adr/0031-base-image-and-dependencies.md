# 0031. 64-bit only, base image Alpine 3.24, current libraries, paho-mqtt 2

Status: proposed (v1.8.5-beta6).

## Context

The images were built on `ghcr.io/home-assistant/<arch>-base:3.18` (Alpine
3.18, end of support May 2025, Python 3.11), with requirements pinned in early
2024. python-multipart 0.0.6, the Starlette pulled in by FastAPI 0.109 and
Jinja2 3.1.3 have published CVEs. Dependabot was off.

Checked on 2026-10-22:

- HA base images exist up to 3.24 for amd64/aarch64 but only up to 3.22 for
  armv7, armhf and i386. 3.22 and 3.23 ship Python 3.12, 3.24 Python 3.14.
- From Alpine 3.19 on the system Python is externally managed (PEP 668), so
  the plain `pip3 install` of the Dockerfile fails.
- i386 and armhf cannot build the app at all, already with the released
  1.8.4: FastAPI needs pydantic 2, and no pydantic-core release has a musl
  wheel for i686 or armv6, so pip falls back to a Rust build the image has no
  toolchain for. Built for real on i386 (runs natively here): both the 1.8.4
  image and the new one fail at pydantic-core. armv7 has wheels for every
  package once the uvicorn extras are gone.

- Home Assistant itself dropped 32-bit: the last Core image for armv7, armhf
  and i386 is 2025.11.x (registry: 2025.12.0 and later 404), the stable
  version manifest pins every 32-bit machine at 2025.11.3, and HA OS ships
  only 64-bit boards.

## Decision

- `arch` is aarch64 and amd64 only. 32-bit users are frozen on HA 2025.11.3
  and keep the version they have; i386 and armhf could not build anyway.
- Base image 3.24 (Python 3.14) on both. Every compiled package has a cp314
  musl wheel for x86_64 and aarch64, so nothing is compiled; 3.24 is
  supported until about 2028.
- `asyncio.get_event_loop()` becomes `get_running_loop()`. All ten calls were
  inside coroutines, where both return the running loop, but the former is
  the one Python 3.14 is strict about.
- `PIP_BREAK_SYSTEM_PACKAGES=1` in the Dockerfile: the container has the
  system interpreter to itself and installs nothing from apk that pip could
  clash with.
- Current pins: FastAPI 0.160 (Starlette 1.9), uvicorn 0.54, Jinja2 3.1.6,
  python-multipart 0.0.32, lxml 6.1.3, PyYAML 6.0.3, aiofiles 25.1, paho-mqtt
  2.1, websockets 17.3 now pinned directly (it is imported, and was only a
  transitive dependency of uvicorn[standard]).
- Plain `uvicorn`, not `uvicorn[standard]`: uvloop, httptools, watchfiles and
  python-dotenv are not used. aiosqlite is removed, nothing imports it.
- paho-mqtt 2 with `CallbackAPIVersion.VERSION2`: the connect/disconnect
  callbacks take a ReasonCode and properties (`is_failure` instead of `rc`).
- `TemplateResponse(request, name, context)`, the signature Starlette 1.x
  expects.
- Dependabot alerts on; `.github/dependabot.yml` updates pip in the beta tree
  only (changes reach stable by promotion) and GitHub Actions. CI compiles
  with Python 3.14.

## Consequences

- Verified in the devcontainer on the real 3.24 image (Python 3.14; an
  earlier pass on 3.22 / Python 3.12 passed too): import of every module with
  DeprecationWarning as error, clean start, MQTT
  reconnect after a broker restart, every UI page, uploads and the 422 path,
  the teach-in WebSocket, the HA WebSocket used by the migration, valve and
  UTE teach-in. The same 21 actuator commands produce byte-identical radio
  telegrams on 1.8.4 and on this build.
- The stable `addon/` gets the same `arch` and base image when beta6 is
  promoted.
