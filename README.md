# TilTale

**TilTale** is a platform for building and running **interactive digital narratives (IDNs)**.

You do **not** need previous experience with Svelte, Node.js, or command-line development to work on this project.

TilTale is intentionally developed with students and less-experienced developers in mind. If some of the tools below are new to you, that is fine: this README explains only what you need to get started.

---

## Contents

| Section | What you will find |
|---|---|
| [Before you begin](#before-you-begin) | The tools you need and what they do. |
| [Install Node.js](#install-nodejs) | Setup for Windows, macOS, and Linux. |
| [Get TilTale](#get-tiltale) | Download the project as a ZIP or clone it with Git. |
| [Run TilTale](#run-tiltale) | Install dependencies and start the app. |
| [Useful commands](#useful-commands) | The commands you will use most often. |
| [Tech stack](#tech-stack) | A short explanation of the technologies used. |
| [Project structure](#project-structure) | Where the important files live. |
| [Development conventions](#development-conventions) | A few rules that keep the code readable. |
| [Quick fixes](#quick-fixes) | Common setup problems and how to diagnose them. |

---

## Before you begin

You need two main tools:

### Visual Studio Code

**Visual Studio Code (VS Code)** is the code editor we use for TilTale. It lets you edit the project and run terminal commands in one place.

Download:

https://code.visualstudio.com/

Recommended extension:

- **Svelte for VS Code**

### Node.js

**Node.js** lets your computer run the development tools used by TilTale.

Installing Node.js also installs **npm**, which downloads and manages the project's dependencies.

Use the current **Node.js LTS** release.

### Development environment used for TilTale

| Software | Version / environment |
|---|---|
| Operating system | Windows 11 Pro |
| Node.js | 24.20.0 LTS |
| npm | 11.19.0 |
| Editor | Visual Studio Code |

TilTale can also be developed on macOS and Linux.

---

## Install Node.js

Official download:

https://nodejs.org/en/download

### Windows 11

1. Download the **LTS** Windows installer.
2. Run it using the default options.
3. Restart VS Code.
4. Open **Terminal → New Terminal**.

Check the installation:

```powershell
node -v
npm -v
```

Check where Node.js is installed:

```powershell
where.exe node
```

> **More experienced?**
>
> ```powershell
> winget install OpenJS.NodeJS.LTS
> ```

### macOS

1. Download the **LTS** macOS installer from the Node.js website.
2. Install it and restart VS Code.

Check:

```bash
node -v
npm -v
which node
```

### Linux

Using **nvm** is recommended:

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.7/install.sh | bash
```

Restart your terminal, then install Node.js 24 LTS:

```bash
nvm install 24
```

Check:

```bash
node -v
npm -v
which node
```

---

## Get TilTale

### Recommended: Download ZIP

This is the easiest option if you are new to Git.

1. Open the repository:
   https://github.com/tiltale/tiltale-refactor
2. Select **Code → Download ZIP**.
3. Unpack the ZIP.
4. Open VS Code.
5. Select **File → Open Folder...**.
6. Open the unpacked `tiltale-refactor` folder.
7. Select **Terminal → New Terminal**.

Check that you opened the correct folder:

```powershell
Test-Path package.json
```

It should return:

```text
True
```

### More experienced? Use Git

```powershell
git clone https://github.com/tiltale/tiltale-refactor.git
cd tiltale-refactor
```

---

## Run TilTale

Install the exact project dependencies recorded in `package-lock.json`:

```powershell
npm ci
```

Then start the development server:

```powershell
npm run dev -- --open
```

Your browser should open TilTale automatically.

If it does not, open the local address shown in the terminal, usually:

```text
http://localhost:5173
```

Stop the server with:

```text
Ctrl + C
```

---

## Useful commands

| Command | What it does |
|---|---|
| `npm ci` | Installs the project's exact locked dependency versions. |
| `npm install <package>` | Adds a new dependency to the project. |
| `npm run dev` | Starts the local development server. |
| `npm run dev -- --open` | Starts the server and opens TilTale. |
| `npm run check` | Checks Svelte and TypeScript for problems. |
| `npm run build` | Creates a production build. |
| `npm run preview` | Tests the production build locally. |

Before committing or handing in work:

```powershell
npm run check
npm run build
```

---

## Tech stack

You do not need to know these tools before you begin.

| Technology | What it does |
|---|---|
| **Svelte 5** | Builds the user interface from reusable components. |
| **SvelteKit 2** | Handles pages, routing, loading, and builds. |
| **TypeScript** | Adds type checking and catches many mistakes earlier. |
| **Vite 8** | Runs the development server and build process. |
| **Tailwind CSS 4** | Provides utility classes for styling. |
| **daisyUI 5** | Adds reusable UI components and themes. |
| **adapter-static 3** | Builds TilTale as static files for deployment. |

Exact installed versions are recorded in:

```text
package.json
package-lock.json
```

---

## Project structure

The parts of the project you will work with most:

```text
tiltale-refactor/
├── src/
│   ├── lib/        Reusable components and application code
│   ├── routes/     Pages and routes
│   └── app.css     Global styling
├── static/         Images and other static files
├── package.json
```

A few useful examples:

- `src/routes/+page.svelte` → the home page
- `src/lib/components/` → reusable Svelte components
- `src/lib/types/` → shared TypeScript types
- `static/` → images, icons, and other files served directly

---

## Development conventions

To keep TilTale understandable for everyone:

- Use **TypeScript** for application code.
- Name Svelte components with **PascalCase**, for example `StoryCard.svelte`.
- Put reusable code in `src/lib`.
- Use **Tailwind CSS**, **daisyUI**, and normal CSS for styling.
- Do not manually edit `node_modules/`, `.svelte-kit/`, or `build/`.
- Prefer readable code over clever code.

In Svelte components, use:

```svelte
<script lang="ts">
    // TypeScript here
</script>
```

---

## Quick fixes

### `node` or `npm` is not recognized

Restart VS Code, then run:

```powershell
node -v
npm -v
```

On Windows, check whether Node.js can be found:

```powershell
where.exe node
```

If nothing is returned, reinstall the current Node.js LTS release.

---

### You are in the wrong folder

Check your current location:

```powershell
Get-Location
```

Then check for `package.json`:

```powershell
Test-Path package.json
```

Expected:

```text
True
```

---

### Dependencies are missing

Run:

```powershell
npm ci
```

Then:

```powershell
npm run dev
```

---

### PowerShell says `npm.ps1` cannot be loaded

Use the Windows command wrapper instead:

```powershell
npm.cmd ci
npm.cmd run dev
```

This avoids changing your PowerShell security settings.

---

### Asking for help

Include the output of:

```powershell
node -v
npm -v
npm run check
```

Also include the **first error message** shown in the terminal.