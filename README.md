# Industrial & Civil Interoperability Platform

This is a website that lets you take a 3D model of a machine or a building (a
**STEP** file, the kind that engineers make in CAD programs), look at it in your
browser, and turn it into other 3D formats (**GLTF** and **IFC**). It also
remembers extra info about every part inside a smart database.

Think of it like a translator + viewer for 3D engineering files. 🏗️

You can set it up in **three ways** — click the one you want for full
step-by-step instructions:

| Way | Who it's for | How hard | Guide |
|---|---|---|---|
| 📦 **Download ZIP + Docker** | You just want to run it. No Git needed. | Easiest | **[docs/zip-and-docker.md](docs/zip-and-docker.md)** |
| 🐙 **Git + Docker** | You'll pull code updates now and then. | Easy | **[docs/git-and-docker.md](docs/git-and-docker.md)** |
| 💻 **Localhost** | You want to edit the code and see changes live. | Medium | **[docs/localhost.md](docs/localhost.md)** |

Pick **one** and follow that guide. If you're not sure, use **Download ZIP +
Docker**.

> ⚠️ **Keep it on your own computer.** This app has no login or password, so
> don't put it on the open internet where strangers could reach it. It's made
> for running on your own machine only.

> 🐳 **What is Docker?** It's a program that packs the whole app — the website,
> the server, the database, and Blender — into one neat box and runs it for you,
> so you don't have to install all that stuff yourself. 🎁 Two of the three ways
> above use it.
