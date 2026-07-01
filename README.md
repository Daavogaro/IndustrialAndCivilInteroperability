# Industrial & Civil Interoperability Platform

This is a website that lets you take a 3D model of a machine or a building (a
**STEP** file, the kind that engineers make in CAD programs), look at it in your
browser, and turn it into other 3D formats (**GLTF** and **IFC**). It also
remembers extra info about every part inside a smart database.

Think of it like a translator + viewer for 3D engineering files. 🏗️

You can set it up in **three ways**:

| Way | Who it's for | How hard |
|---|---|---|
| 📦 **Download ZIP + Docker** | You just want to run it. No Git needed. | Easiest |
| 🐙 **Git + Docker** | You'll pull code updates now and then. | Easy |
| 💻 **Localhost** | You want to edit the code and see changes live. | Medium |

Pick **one** and follow that section. If you're not sure, use **Download ZIP +
Docker**.

> ⚠️ **Keep it on your own computer.** This app has no login or password, so
> don't put it on the open internet where strangers could reach it. It's made
> for running on your own machine only.

> 🐳 **What is Docker?** It's a program that packs the whole app — the website,
> the server, the database, and Blender — into one neat box and runs it for you,
> so you don't have to install all that stuff yourself. 🎁 Two of the three ways
> below use it.

---

# 📦 Way 1: Download ZIP + Docker (easiest, no Git)

This is the simplest path: grab the code as a ZIP, install Docker, and run one
command.

Do these steps **in order**. Don't skip any.

## Step 1 — Install Docker

1. Download **Docker Desktop**: https://www.docker.com/products/docker-desktop/
2. Install it, then **open Docker Desktop** and wait until it says it's running.
3. Test it. Open a terminal (on Windows that's **PowerShell**) and type:

   ```
   docker --version
   ```

   If a version number shows up, you're good. ✅

## Step 2 — Download and unzip the code

1. On the project's GitHub page, click the green **`< > Code`** button, then
   **Download ZIP**.
2. Unzip it somewhere easy to find, like your Desktop.
3. Remember this folder — it's your **project folder** for every step below.

## Step 3 — ⚠️ Get the big Blender add-on (Bonsai) by hand

This step is **only for the ZIP way**, and it's important:

> When you download a ZIP from GitHub, one **big** file does **not** come with
> it properly. The app needs a Blender add-on called **Bonsai** (about
> **138 MB**), but in the ZIP it arrives as a tiny broken placeholder. You have
> to replace it with the real one.

1. Look at this file inside your project folder:

   ```
   backend/bonsai/add-on-bonsai-v0.8.4-linux-x64.zip
   ```

   If its size is only a few hundred **bytes**, it's the broken placeholder
   (that's expected with a ZIP download).
2. Download the **real** Bonsai add-on from [here](https://extensions.blender.org/download/sha256:1494f04017c1bcd3c0686d83a323c205e5240aeee597164ac187d1290df1c5dc/add-on-bonsai-v0.8.4-linux-x64.zip?repository=%2Fapi%2Fv1%2Fextensions%2F&blender_version_min=4.2.0&platforms=linux-x64)
   — pick the **Linux** version that matches the file name above
   (`v0.8.4-linux-x64`).
3. Put the downloaded file into the `backend/bonsai/` folder and make sure it's
   named **exactly** `add-on-bonsai-v0.8.4-linux-x64.zip` (replace the tiny
   placeholder). It should now be about **138 MB**. ✅

> 💡 Want to skip this annoying step? Use **Way 2 (Git + Docker)** instead —
> Git downloads the big file for you automatically.

## Step 4 — Build and start everything

1. Open a terminal **inside the project folder** (the folder that has this
   README).
2. Run:

   ```
   docker compose up --build
   ```

3. ⏳ **The first time is slow.** It downloads Blender and installs the add-on,
   which can take several minutes. That's totally normal — just let it run. It's
   ready when the text stops scrolling and the terminal goes quiet.

## Step 5 — Open the app

Open your web browser and go to:

```
http://localhost:3000
```

That's it — the website, server, database, and Blender are **all running inside
Docker** for you. 🎉

Now jump to **[Everyday use](#-everyday-use-docker)** and
**[If something goes wrong](#-if-something-goes-wrong)** below.

---

# 🐙 Way 2: Git + Docker

Same as Way 1, but instead of downloading a ZIP you use **Git**. The big bonus:
Git grabs the huge Bonsai file for you, so there's no manual download.

## Step 1 — Install Docker

Same as **Way 1 → Step 1** above. Make sure `docker --version` works. ✅

## Step 2 — Install Git and Git LFS

- **Git** downloads the code: https://git-scm.com/downloads
- **Git LFS** is a helper for very big files (like Bonsai): https://git-lfs.com

Install both.

## Step 3 — Download the code with Git

Open a terminal where you want the project to live, then run (replace the link
with the project's real address):

```
git clone <the-project-github-link>
cd <the-project-folder>
git lfs install
git lfs pull
```

`git lfs pull` is what pulls down the big **Bonsai** file (about **138 MB**).

**Check it worked:** look at the size of

```
backend/bonsai/add-on-bonsai-v0.8.4-linux-x64.zip
```

It should be about **138 MB**. If it's only a few **bytes**, run `git lfs pull`
again. ⚠️ (A tiny file here is the #1 reason the build fails with a Bonsai
error.)

## Step 4 — Build and start everything

In the project folder, run:

```
docker compose up --build
```

⏳ The first build is slow (it downloads Blender). Let it finish — it's ready
when the terminal goes quiet.

## Step 5 — Open the app

Go to http://localhost:3000 in your browser. 🎉

Now see **[Everyday use](#-everyday-use-docker)** and
**[If something goes wrong](#-if-something-goes-wrong)** below.

---

## 🔁 Everyday use (Docker)

This applies to **both** Docker ways (1 and 2) after your first setup.

- **Start it:** in the project folder, run

  ```
  docker compose up
  ```

  (no `--build` needed unless you changed the code)

- **Stop it:** press `Ctrl+C` in that terminal, then run

  ```
  docker compose down
  ```

- **After you change the code:** run `docker compose up --build` again.

Your database keeps its saved data between restarts. 💾

## 🛠️ (You'll probably never need this) Fix database saving

The database is already set up to let the app save data. **Only** if saving
fails, do this once:

1. Go to http://localhost:8890/conductor/
2. Log in with — Account: `dba`, Password: `ddd`
3. Open **Database → Interactive SQL**, paste this, and click run:

   ```
   grant SPARQL_UPDATE to "SPARQL"
   ```

---

# 💻 Way 3: Run on your own machine (localhost)

Use this if you want to edit the code and see your changes right away. Here you
start the three pieces **yourself**: the database, the backend (server), and the
frontend (website).

You'll install these first:

- [Git](https://git-scm.com/downloads) and [Git LFS](https://git-lfs.com) — to
  download the code **and** the big Bonsai file
- [Node.js](https://nodejs.org/en/download) — runs the website part
- [Miniforge](https://conda-forge.org/download/) (Conda) — runs the Python server
- [Docker](https://www.docker.com/products/docker-desktop/) — used **only** for
  the database
- [Blender 5.0](https://www.blender.org/) with the
  [Bonsai](https://bonsaibim.org/) add-on turned on — used to make IFC files
- (Optional) [VS Code](https://code.visualstudio.com/download) to edit the code

First, download the code with Git (this also grabs the big Bonsai file):

```
git clone <the-project-github-link>
cd <the-project-folder>
git lfs install
git lfs pull
```

You'll open **three terminals** and keep all three running. Start them in this
order: **database → backend → frontend**.

## Terminal 1 — Database (with Docker)

In the project folder, run:

```
docker compose up virtuoso
```

Open http://localhost:8890/ to check it's alive. Leave this terminal running.

## Terminal 2 — Backend (the Python server)

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

## Terminal 3 — Frontend (the website)

```
cd frontend
npm install
npm run dev
```

Now open http://localhost:3000/ in your browser. 🎉

The website automatically talks to your backend at `http://localhost:8000`.
(If your backend is somewhere else, set the `VITE_API_TARGET` environment
variable to point at it.)

To stop everything, press `Ctrl+C` in each of the three terminals.

---

# 📂 Where your files go

Everything you upload or the app creates (STEP, GLTF, GLB, IFC, JSON, RDF) shows
up in the **`tmp/`** folder inside the project, so you can open them straight
from your computer.

# 🌐 The addresses (same for all three ways)

| What it is | Open this |
|---|---|
| The web app (this is the one you use) | http://localhost:3000 |
| The backend server (for debugging) | http://localhost:8000 |
| The Virtuoso database | http://localhost:8890 |

---

# 🆘 If something goes wrong

- **The build fails talking about "Bonsai".** The big Bonsai file is missing or
  broken.
  - ZIP way (Way 1): redo **Step 3** and put the real ~138 MB file in
    `backend/bonsai/`.
  - Git ways (Way 2 or 3): run `git lfs pull` again and check the file is about
    **138 MB**, not a few bytes.
- **Saving data doesn't work.** Do the one-time
  **[Fix database saving](#️-youll-probably-never-need-this-fix-database-saving)**
  command.
- **`docker` isn't recognized.** Docker Desktop isn't installed or isn't
  running yet. Open it and wait until it says running, then try again.
- **On localhost, IFC creation fails saying it can't find Blender.** Install
  Blender 5.0, or set `$env:BLENDER_EXE` to your `blender.exe` before starting
  the backend (see **Way 3 → Terminal 2**).
- **First Docker build feels frozen.** It's probably just downloading Blender.
  Give it several minutes before worrying. ⏳
