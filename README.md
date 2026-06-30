# Industrial & Civil Interoperability Platform

Convert and browse 3D CAD models (STEP → GLTF → IFC) with a web UI, backed by a
Virtuoso RDF database. **Everything runs in Docker** — you only need to install
Docker, drop in one file, and run a single command.

> ⚠️ This setup is meant for **local / trusted use only**. It has no login or
> passwords protecting the app, so don't expose these ports to the open internet.

---

## How to start it the first time

Follow these steps in order. Don't skip any.

### Step 1 — Install Docker

1. Download **Docker Desktop**: https://www.docker.com/products/docker-desktop/
2. Install it and **start Docker Desktop** (wait until it says it's running).
3. Check it works: open a terminal (PowerShell on Windows) and run:

   ```
   docker --version
   ```

   If you see a version number, you're good. ✅

### Step 2 — Put the Bonsai file in place

The app needs a big Blender add-on file called **Bonsai**. It is too large to
keep in this project on GitHub, so you must place it yourself.

1. Get the file named **`add-on-bonsai-v0.8.4-linux-x64.zip`**.
2. Put it exactly here, inside the project:

   ```
   backend/bonsai/add-on-bonsai-v0.8.4-linux-x64.zip
   ```

   That folder already exists. Just drop the file into it. (Don't rename it.)

### Step 3 — Build and start everything

1. Open a terminal **in the project folder** (the folder that has this README).
2. Run:

   ```
   docker compose up --build
   ```

3. ⏳ **The first time is slow** (it downloads Blender and installs Bonsai — this
   can take many minutes). This is normal. Just let it finish. You'll know it's
   ready when the messages stop scrolling and stay quiet.

### Step 4 — Open the app

Open your web browser and go to:

```
http://localhost:3000
```

That's it! The website, the server, the database, and Blender are **all running
inside Docker** for you. 🎉

### Step 5 — (Almost never needed) Database write permission

The database is set up to allow writing automatically. **Only** if saving data
fails, do this once:

1. Go to http://localhost:8890/conductor/
2. Log in with — Account: `dba`, Password: `ddd`
3. Open **Database → Interactive SQL**, paste this, and run it:

   ```
   grant SPARQL_UPDATE to "SPARQL"
   ```

---

## How to run it every day (after the first time)

- **Start the app:** in the project folder, run

  ```
  docker compose up
  ```

  (no `--build` needed unless you changed the code)

- **Stop the app:** press `Ctrl+C` in that terminal, then run

  ```
  docker compose down
  ```

- **After you change the code:** run `docker compose up --build` again.

Your database keeps its data between restarts.

---

## Where your files go

Everything you upload or generate (STEP, GLTF, GLB, IFC, JSON, RDF) appears in
the **`tmp/`** folder inside the project, so you can open them directly on your
computer.

| What's running | Address |
|---|---|
| Web app (use this) | http://localhost:3000 |
| Backend API (for debugging) | http://localhost:8000 |
| Virtuoso database | http://localhost:8890 |

---

## Advanced: run without Docker

You normally **don't need this**. The Docker setup above is the recommended way.
This section is only for developers who want to run each piece directly on their
machine.

You will need: [VS Code](https://code.visualstudio.com/download), a Conda
environment, [Node.js](https://nodejs.org/en/download), Docker (for the database
only), and a local install of [Blender 5.0](https://www.blender.org/) with the
[Bonsai](https://bonsaibim.org/) add-on enabled.

### Backend (Conda)

1. Install [Miniforge](https://conda-forge.org/download/) and run
   `conda init powershell`, then reopen your terminal.
2. Create and activate the environment:

   ```
   conda create -n OCC python=3.12
   conda activate OCC
   conda install -c conda-forge fastapi uvicorn websockets requests sparqlwrapper python-multipart pygltflib numpy httpx ifcopenshell rdflib pythonocc-core
   ```

3. Tell the backend where Blender is (PowerShell):

   ```
   $env:BLENDER_EXE = "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"
   ```

4. Start it: `python backend/run.py` — ready when you see
   `Application startup complete.`

### Database (Docker)

```
docker compose up virtuoso
```

Open http://localhost:8890/ to confirm it's running.

### Frontend (Node.js)

```
cd frontend
npm install
npm run dev
```

Open http://localhost:3000/. The dev server proxies `/api` to the backend at
`http://localhost:8000` (override with the `VITE_API_TARGET` environment
variable if your backend is elsewhere).
