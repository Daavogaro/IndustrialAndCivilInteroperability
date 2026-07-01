# 🐙 Way 2: Git + Docker

← Back to the [main README](../README.md)

Same idea as the ZIP way, but instead of downloading a ZIP you use **Git**. The
big bonus: Git grabs the huge Bonsai file for you, so there's **no manual
download**.

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

## Step 2 — Install Git and Git LFS

- **Git** downloads the code: https://git-scm.com/downloads
- **Git LFS** is a helper for very big files (like Bonsai): https://git-lfs.com

Install both.

## Step 3 — Download the code with Git

Open a terminal where you want the project to live, then run:

```
git clone https://github.com/Daavogaro/IndustrialAndCivilInteroperability.git
cd IndustrialAndCivilInteroperability
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

⏳ **The first build is slow** (it downloads Blender). Let it finish — it's ready
when the terminal goes quiet.

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

- **Get the latest code:** run `git pull`, then `docker compose up --build`.

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

- **The build fails talking about "Bonsai".** The big file didn't download. Run
  `git lfs pull` again and check the file is about **138 MB**, not a few bytes.
- **Saving data doesn't work.** You probably skipped **Step 5**. Run the
  `grant SPARQL_UPDATE to "SPARQL"` command from that step.
- **`docker` isn't recognized.** Docker Desktop isn't installed or isn't
  running yet. Open it and wait until it says running, then try again.
- **First Docker build feels frozen.** It's probably just downloading Blender.
  Give it several minutes before worrying. ⏳
