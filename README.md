## Conda
[Conda](https://github.com/conda/conda) is a package manager that allows user to create independent environment for their libraries. The Conda Common Line Interface (CLI) is written entirely in Python. The backend is written in Python, that's why we need it. 
### Installation of Miniforge
[Miniforge](https://github.com/conda-forge/miniforge) is a minimal installer distribution of Conda.
1. Install it using the [Miniforge installer](https://conda-forge.org/download/)
2. After the installation open **Miniforge Prompt**: this is the CLI of Miniforge
3. Run the code `conda init powershell` to enable Conda's command also in Windows PowerShell terminal
4. Close Miniforge Prompt
5. To verify the installation open Windows PowerShell and try to run `conda`, if there are no problems and it returns a list of commands you are ok
### Installation of libraries
1. Open this GitHub folder in VSCode
2. Open a new terminal
3. Run `conda create -n OCC python=3.12`: we are creating an independent environment based on the version 3.12 of Python
4. Run `conda activate OCC`: we are activating our environment
5. Run `conda install fastapi uvicorn requests SPARQLWrapper python-multipart pygltflib numpy httpx ifcopenshell rdflib pythonocc-core`: with this command we are installing all the libraries that we need
6. Close the terminal

## Docker
Docker is a platform for building, shipping, and running applications inside **containers**. A container packages an application together with everything it needs to run—libraries, dependencies, runtime, and configuration—so it behaves the same way on any machine. It is really useful for running complete applications. In our case we are running  [Openlink Virtuoso](https://virtuoso.openlinksw.com/) that is a graph database.
### Installation of Docker
1. Download the [Docker Desktop Installer](https://www.docker.com/products/docker-desktop/)
2. Launch Docker Desktop
3. To verify the installation open Windows PowerShell and run `docker`, if there are no problems and it returns a list of commands you are ok
### Setting up the database
1. Open this GitHub folder in VSCode
2. Open a new terminal and run `docker-compose up --build` 
3. Open on your Web Browser http://localhost:8890/ if you can see the Virtuoso page the database is running
4. Click on [Conductor](http://localhost:8890/conductor/) and you can login into the database with the credential:
	   Account: `dba`
	   Password: `ddd`
5. Click on `Database >> Interactive SQL` and in the panel write `grant SPARQL_UPDATE to "SPARQL"` in order to have the permissions to write triples in the graph database
6. Close the terminal

## Node.js
**Node.js** is an open-source JavaScript runtime that lets you run JavaScript outside of a web browser. This tool allow us to run the frontend. 
### Installation of Node.js
1. Download the [Node.js Windows Installer](https://nodejs.org/en/download?utm_source=chatgpt.com)
2. To verify the installation open Windows PowerShell and run `node -v`, if there are no problems and it returns the version of Node.js you are ok
### Installation of libraries
1. Open this GitHub folder in VSCode
2. Open a new terminal and run 
   `cd frontend`: to change the folder 
   `npm install`: to install all the libraries 
3. Close the terminal
# Execution
- **Backend**: 
	1. open a new terminal and run 
	   `conda activate OCC` : we are activating the Conda environment
	   `python backend\run.py` : we run the backend
	2. If we see as last message `INFO:     Application startup complete.` the backend is running 
- **Database**: 
	1. Open a new terminal and run `docker-compose up --build` 
	2. Open on your Web Browser http://localhost:8890/ if you can see the Virtuoso page the database is running
- **Frontend**: 
	1. open a new terminal and run 
	   `cd frontend`: we enter in the frontend folder
	   `npm run dev`: we run the frontend
	2. Open on your Web Browser http://localhost:3000/ if you can see the Web Application page the frontend is running
