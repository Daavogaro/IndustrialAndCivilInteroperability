# 📦 Way 1: Download ZIP + Docker (easiest, no Git)

← Back to the [main README](../README.md)

This is the simplest path: grab the code as a ZIP, install Docker, and run one
command.

> 🐳 **What is Docker?** It's a program that packs the whole app — the website,
> the server, the database, and Blender — into one neat box and runs it for you,
> so you don't have to install all that stuff yourself. 🎁

Do these steps **in order**. Don't skip any.

---

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
   — it's the **Linux** version that matches the file name above
   (`v0.8.4-linux-x64`).
3. Put the downloaded file into the `backend/bonsai/` folder and make sure it's
   named **exactly** `add-on-bonsai-v0.8.4-linux-x64.zip` (replace the tiny
   placeholder). It should now be about **138 MB**. ✅

> 💡 Want to skip this annoying step? Use **[Git + Docker](git-and-docker.md)**
> instead — Git downloads the big file for you automatically.

## Step 4 — Build and start everything

1. Open a terminal **inside the project folder**.
2. Run:

   ```
   docker compose up --build
   ```

3. ⏳ **The first time is slow.** It downloads Blender and installs the add-on,
   which can take several minutes. That's totally normal — just let it run. It's
   ready when the text stops scrolling and the terminal goes quiet.

## Step 5 — Set up the database (first time only) 🔑

The **first time** you start the database, you have to give the app permission
to save into it. Do this once, right after the containers are up:

1. Go to http://localhost:8890/conductor/
2. Log in with — Account: `dba`, Password: `ddd`
3. Open **Database → Interactive SQL**, paste this, and click run:

   ```
   grant SPARQL_UPDATE to "SPARQL"
   ```

You won't need to do this again — the database remembers it.

## Step 6 — Open the app

Open your web browser and go to:

```
http://localhost:3000
```

That's it — the website, server, database, and Blender are **all running inside
Docker** for you. 🎉

---

## 🔁 Using it every day (after the first setup)

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

- **The build fails talking about "Bonsai".** The big Bonsai file is missing or
  broken. Redo **Step 3** and put the real ~138 MB file in `backend/bonsai/`.
- **Saving data doesn't work.** You probably skipped **Step 5**. Run the
  `grant SPARQL_UPDATE to "SPARQL"` command from that step.
- **`docker` isn't recognized.** Docker Desktop isn't installed or isn't
  running yet. Open it and wait until it says running, then try again.
- **First Docker build feels frozen.** It's probably just downloading Blender.
  Give it several minutes before worrying. ⏳
