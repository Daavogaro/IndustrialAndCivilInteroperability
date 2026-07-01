# Backend image: FastAPI + pythonocc-core (STEP->GLTF) + Blender 5.0 with the
# Bonsai extension (GLTF->IFC). pythonocc-core is only distributed on
# conda-forge, so this image is conda-based rather than a plain python/pip image.
#
# Miniforge is used (not continuumio/miniconda3) because it ships conda-forge as
# the only channel — mixing conda-forge with Anaconda's `defaults` channel makes
# this set of packages an unsatisfiable solve. This mirrors the Miniforge setup
# the project documents for host installs.
FROM condaforge/miniforge3:latest

# ---------------------------------------------------------------------------
# 1. Python stack (conda-forge, solved with mamba). Mirrors
#    backend/requirements.txt; `websockets` is added so uvicorn can serve the
#    WebSocket endpoints (the [standard] extra on pip). pythonocc-core and
#    ifcopenshell are conda-only.
# ---------------------------------------------------------------------------
RUN mamba install -y \
        python=3.12 \
        fastapi \
        uvicorn \
        websockets \
        requests \
        sparqlwrapper \
        python-multipart \
        pygltflib \
        numpy \
        httpx \
        rdflib \
        ifcopenshell \
        pythonocc-core \
    && conda clean -afy

# ---------------------------------------------------------------------------
# 2. Blender 5.0 (Linux x64) + the shared libraries it needs. The IFC
#    conversion script (import_gltf.py) drives Blender in GUI mode — it iterates
#    real windows looking for a VIEW_3D area to run BIM/mesh operators in — so
#    Blender is launched under a virtual X display (Xvfb), not `--background`.
#    That means the full GUI X11 stack + xvfb are required, not just the
#    headless GL libs.
# ---------------------------------------------------------------------------
ARG BLENDER_VERSION=5.0.1
ARG BLENDER_URL=https://download.blender.org/release/Blender5.0/blender-${BLENDER_VERSION}-linux-x64.tar.xz

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        wget xz-utils xvfb \
        libgl1 libegl1 libglx0 libsm6 libxext6 libxrender1 libxi6 \
        libxxf86vm1 libxfixes3 libxkbcommon0 \
        libx11-6 libxcb1 libxrandr2 libxcursor1 libxinerama1 \
    && rm -rf /var/lib/apt/lists/* \
    && wget -q "${BLENDER_URL}" -O /tmp/blender.tar.xz \
    && mkdir -p /opt/blender \
    && tar -xJf /tmp/blender.tar.xz -C /opt/blender --strip-components=1 \
    && rm /tmp/blender.tar.xz \
    && ln -s /opt/blender/blender /usr/local/bin/blender \
    && blender --version

# Wrapper that runs Blender inside a throwaway virtual X display. The app
# invokes this (via BLENDER_EXE) so the GUI-mode conversion script gets the
# VIEW_3D window/area it needs without a real monitor. `-a` auto-picks a free
# display so concurrent jobs don't collide.
RUN printf '#!/bin/sh\nexec xvfb-run -a -s "-screen 0 1920x1080x24" /opt/blender/blender "$@"\n' \
        > /usr/local/bin/blender-xvfb \
    && chmod +x /usr/local/bin/blender-xvfb

# ---------------------------------------------------------------------------
# 3. Bonsai extension: install + enable into Blender's user_default repo so it
#    persists into the image, then a fail-fast smoke check that `bonsai.tool`
#    imports the same way the app invokes Blender (background, default startup).
# ---------------------------------------------------------------------------
COPY bonsai/add-on-bonsai-v0.8.4-linux-x64.zip /tmp/bonsai.zip
RUN blender --background --command extension install-file \
        --repo user_default --enable /tmp/bonsai.zip \
    && rm /tmp/bonsai.zip \
    && blender --background --python-expr "import bonsai.tool; print('BONSAI_IMPORT_OK')" \
        | grep -q "BONSAI_IMPORT_OK"

# ---------------------------------------------------------------------------
# 3b. gltfpack (meshoptimizer) — compresses GLTF -> GLB for the web viewer.
#     The frontend pins the npm "gltfpack" (a Node/WASM wrapper); this image has
#     no Node, so install the standalone native binary on PATH instead. Without
#     it, the STEP-import pipeline throws at the compression step and never
#     reaches the RDF import (so no triples land in Virtuoso).
# ---------------------------------------------------------------------------
ARG GLTFPACK_VERSION=1.2
RUN wget -q "https://github.com/zeux/meshoptimizer/releases/download/v${GLTFPACK_VERSION}/gltfpack-ubuntu.zip" \
        -O /tmp/gltfpack.zip \
    && python -c "import zipfile; zipfile.ZipFile('/tmp/gltfpack.zip').extractall('/tmp/gltfpack')" \
    && install -m 0755 "$(find /tmp/gltfpack -name gltfpack -type f | head -1)" /usr/local/bin/gltfpack \
    && rm -rf /tmp/gltfpack /tmp/gltfpack.zip

# ---------------------------------------------------------------------------
# 4. Application. Code lives at /app/backend so models.BASE_DIR (parents[3])
#    resolves to /app and runtime files land in /app/tmp (the compose volume).
# ---------------------------------------------------------------------------
ENV BLENDER_EXE=blender-xvfb \
    DB_HOST=virtuoso \
    PYTHONUNBUFFERED=1

WORKDIR /app/backend
COPY . .

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
