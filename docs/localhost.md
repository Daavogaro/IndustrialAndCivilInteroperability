# 💻 Way 3: Run on your own machine (localhost)

← Back to the [main README](../README.md)

Use this if you want to **edit the code and see your changes right away**. Here
you start the three pieces **yourself**: the database, the backend (server), and
the frontend (website).

---

## What to install first

- [Git](https://git-scm.com/downloads) and [Git LFS](https://git-lfs.com) — to
  download the code **and** the big Bonsai file
- [Node.js](https://nodejs.org/en/download) — runs the website part
- [Miniforge](https://conda-forge.org/download/) (Conda) — runs the Python server
- [Docker](https://www.docker.com/products/docker-desktop/) — used **only** for
  the database
- [Blender 5.0](https://www.blender.org/) with the
  [Bonsai](https://bonsaibim.org/) add-on turned on — used to make IFC files
- (Optional) [VS Code](https://code.visualstudio.com/download) to edit the code

## Get the code

Download the code with Git (this also grabs the big Bonsai file automatically):

```
git clone https://github.com/Daavogaro/IndustrialAndCivilInteroperability.git
cd IndustrialAndCivilInteroperability
git lfs install
git lfs pull
```

---

## Starting it up

You'll open **three terminals** and keep all three running. Start them in this
order: **database → backend → frontend**.

### Terminal 1 — Database (with Docker)

In the project folder, run:

```
docker compose up virtuoso
```

Open http://localhost:8890/ to check it's alive. Leave this terminal running.

> 🔑 **First time only — give the app permission to save.** The very first time
> you start the database, do this once (it's remembered afterwards):
>
> 1. Go to http://localhost:8890/conductor/
> 2. Log in with — Account: `dba`, Password: `ddd`
> 3. Open **Database → Interactive SQL**, paste this, and click run:
>
>    ```
>    grant SPARQL_UPDATE to "SPARQL"
>    ```

### Terminal 2 — Backend (the Python server)

1. Install Miniforge, then run `conda init powershell` and **reopen** your
   terminal (this lets you use the `conda` command).
2. Create the environment and install what it needs (do this once):

   ```
   conda create -n OCC python=3.12
   conda activate OCC
   conda install -c conda-forge fastapi uvicorn websockets requests sparqlwrapper python-multipart pygltflib numpy httpx ifcopenshell rdflib pythonocc-core
   ```

3. Start the server:

   ```
   conda activate OCC
   python backend/run.py
   ```

   It's ready when you see **`Application startup complete.`** Leave it running.

   💡 **About Blender:** the app **automatically finds** Blender at the normal
   Windows spot (`C:\Program Files\Blender Foundation\Blender 5.0`, or 4.5 if 5.0
   isn't there). So you usually don't have to do anything. Only if your Blender
   is somewhere else, tell the app where it is **before** starting the server:

   ```
   $env:BLENDER_EXE = "C:\path\to\your\blender.exe"
   ```

### Terminal 3 — Frontend (the website)

```
cd frontend
npm install
npm run dev
```

Now open http://localhost:3000/ in your browser. 🎉

The website automatically talks to your backend at `http://localhost:8000`.
(If your backend is somewhere else, set the `VITE_API_TARGET` environment
variable to point at it.)

---

## Stopping it

Press `Ctrl+C` in each of the three terminals.

---

## 📂 Where your files go

Everything you upload or the app creates (STEP, GLTF, GLB, IFC, JSON, RDF) shows
up in the **`tmp/`** folder inside the project, so you can open them straight
from your computer.

## 🌐 The addresses

| What it is | Open this |
|---|---|
| The web app (this is the one you use) | http://localhost:3000 |
| The backend server (for debugging) | http://localhost:8000 |
| The Virtuoso database | http://localhost:8890 |

---

## 🆘 If something goes wrong

- **IFC creation fails saying it can't find Blender.** Install Blender 5.0, or
  set `$env:BLENDER_EXE` to your `blender.exe` **before** starting the backend
  (see **Terminal 2**).
- **The Bonsai file is only a few bytes.** Run `git lfs pull` again — it should
  be about **138 MB**.
- **Saving data doesn't work.** You probably skipped the one-time database
  permission step under **Terminal 1**. Run the `grant SPARQL_UPDATE to "SPARQL"`
  command from there.
- **`conda` isn't recognized.** Run `conda init powershell`, then close and
  reopen the terminal.
- **`docker` isn't recognized.** Docker Desktop isn't installed or isn't
  running yet. Open it and wait until it says running, then try again.
