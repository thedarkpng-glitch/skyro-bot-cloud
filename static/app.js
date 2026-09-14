let bots = [];
let currentConsoleBot = "";
let currentConfigBot = "";
let adminUnlocked = false;

const $ = id => document.getElementById(id);


/* =========================================================
   NAVEGAÇÃO
========================================================= */

document.querySelectorAll(".nav").forEach(btn => {

  btn.addEventListener("click", () => {

    document.querySelectorAll(".nav")
      .forEach(x => x.classList.remove("active"));

    btn.classList.add("active");

    document.querySelectorAll(".page")
      .forEach(x => x.classList.remove("active"));

    $("page-" + btn.dataset.page).classList.add("active");

    $("page-title").textContent =
      btn.querySelector("span").textContent;

    if (btn.dataset.page === "console")
      loadConsoleBots();

    if (btn.dataset.page === "configs")
      loadConfigBots();

    if (btn.dataset.page === "admin" && adminUnlocked)
      loadAdmin();

  });

});


/* =========================================================
   API
========================================================= */

async function api(url, options = {}) {

  const r = await fetch(url, options);

  const data = await r.json().catch(() => ({}));

  if (!r.ok) {
    throw new Error(
      data.error ||
      data.message ||
      "Erro"
    );
  }

  return data;
}


/* =========================================================
   REFRESH
========================================================= */

async function refreshAll() {

  await Promise.all([
    loadBots(),
    loadSystem()
  ]);

}


/* =========================================================
   SISTEMA
========================================================= */

async function loadSystem() {

  try {

    const x = await api("/api/system");

    $("cpu").textContent =
      x.cpu_percent + "%";

    $("ram").textContent =
      x.ram_percent + "%";

    $("disk").textContent =
      x.disk_percent + "%";

    $("host-name").textContent =
      location.hostname || "Windows runner";

  } catch (e) {}

}


/* =========================================================
   BOTS
========================================================= */

async function loadBots() {

  try {

    bots = await api("/api/bots");

    renderBots();
    fillBotSelects();

  } catch (e) {

    toast(e.message);

  }

}


function renderBots() {

  const grid = $("bot-grid");

  grid.innerHTML = "";

  let online = 0;

  bots.forEach(b => {

    if (b.status === "online")
      online++;


    const card =
      document.createElement("div");

    card.className = "bot-card";


    card.innerHTML = `

      <div class="bot-title">

        <h3>${esc(b.name)}</h3>

        <span class="status ${b.status}">
          ${b.status === "online"
            ? "● ONLINE"
            : "OFFLINE"}
        </span>

      </div>

      <div class="meta">
        ${esc(b.runtime.toUpperCase())}
        •
        ${esc(b.entrypoint || "sem entrada")}
      </div>

      <div class="bot-actions">

        <button onclick="quickAction('${b.id}','start')">
          ▶
        </button>

        <button onclick="quickAction('${b.id}','restart')">
          ↻
        </button>

        <button onclick="quickAction('${b.id}','stop')">
          ■
        </button>

      </div>
    `;

    grid.appendChild(card);

  });


  if (!bots.length) {

    grid.innerHTML = `
      <div class="panel-card">

        <b>Nenhum bot ainda.</b>

        <p style="color:#8f96a8">
          Clique em “+ Novo bot”
          para criar seu primeiro projeto.
        </p>

      </div>
    `;

  }


  $("total-bots").textContent =
    bots.length;

  $("online-bots").textContent =
    online;

  $("offline-bots").textContent =
    bots.length - online;

}


function fillBotSelects() {

  ["console-bot", "config-bot"]
    .forEach(id => {

      const s = $(id);

      const old = s.value;

      s.innerHTML =
        bots.map(b => `
          <option value="${b.id}">
            ${esc(b.name)} — ${b.runtime}
          </option>
        `).join("");

      if (
        old &&
        bots.some(b => b.id === old)
      ) {
        s.value = old;
      }

    });


  if (!currentConsoleBot && bots[0])
    currentConsoleBot = bots[0].id;


  if (!currentConfigBot && bots[0])
    currentConfigBot = bots[0].id;


  if ($("console-bot").value)
    currentConsoleBot =
      $("console-bot").value;


  if ($("config-bot").value)
    currentConfigBot =
      $("config-bot").value;

}


/* =========================================================
   AÇÕES DOS BOTS
========================================================= */

$("console-bot").addEventListener(
  "change",
  e => {

    currentConsoleBot =
      e.target.value;

    loadConsole();

  }
);


$("config-bot").addEventListener(
  "change",
  e => {

    currentConfigBot =
      e.target.value;

    loadConfig();

  }
);


async function quickAction(id, action) {

  try {

    const x = await api(
      `/api/bots/${id}/action`,
      {
        method: "POST",

        headers: {
          "Content-Type":
            "application/json"
        },

        body: JSON.stringify({
          action
        })
      }
    );

    toast(x.message);

    await loadBots();

  } catch (e) {

    toast(e.message);

  }

}


function botAction(action) {

  if (currentConsoleBot)
    quickAction(
      currentConsoleBot,
      action
    );

}


/* =========================================================
   CONSOLE
========================================================= */

async function loadConsoleBots() {

  await loadBots();

  if (currentConsoleBot)
    await loadConsole();

}


async function loadConsole() {

  if (!currentConsoleBot)
    return;


  const b =
    bots.find(
      x => x.id === currentConsoleBot
    );


  if (b)
    $("console-bot-label").textContent =
      b.name;


  try {

    const x = await api(
      `/api/bots/${currentConsoleBot}/console`
    );

    $("console-output").textContent =
      x.content || "Console vazio.";

    $("console-output").scrollTop =
      $("console-output").scrollHeight;

  } catch (e) {}

}


async function runCommand() {

  const input =
    $("command");

  const command =
    input.value.trim();


  if (
    !command ||
    !currentConsoleBot
  )
    return;


  input.value = "";


  try {

    const x = await api(
      `/api/bots/${currentConsoleBot}/console`,
      {
        method: "POST",

        headers: {
          "Content-Type":
            "application/json"
        },

        body: JSON.stringify({
          command
        })
      }
    );


    $("console-output").textContent +=
      `\n$ ${command}\n${x.output || x.message || ""}\n`;


    $("console-output").scrollTop =
      $("console-output").scrollHeight;


    loadBots();

  } catch (e) {

    toast(e.message);

  }

}


/* =========================================================
   CONFIG
========================================================= */

async function loadConfigBots() {

  await loadBots();

  if (currentConfigBot)
    await loadConfig();

  loadRuntimes();

}


async function loadConfig() {

  if (!currentConfigBot)
    return;


  const x = await api(
    `/api/bots/${currentConfigBot}/config`
  );


  $("entrypoint").value =
    x.entrypoint || "";

  $("python-exec").value =
    x.python_exec || "";

  $("node-exec").value =
    x.node_exec || "";


  $("env-list").innerHTML = "";


  (x.env || []).forEach(addEnv);

}


function addEnv(
  item = {
    key: "",
    value: ""
  }
) {

  const row =
    document.createElement("div");

  row.className =
    "env-row";


  row.innerHTML = `

    <input
      placeholder="TOKEN"
      value="${escAttr(item.key)}"
    >

    <input
      placeholder="valor secreto"
      type="password"
      value="${escAttr(item.value)}"
    >

    <button
      onclick="this.parentElement.remove()"
    >
      ×
    </button>

  `;


  $("env-list")
    .appendChild(row);

}


async function saveConfig() {

  if (!currentConfigBot)
    return;


  const env =
    [...document.querySelectorAll(".env-row")]
      .map(row => {

        const i =
          row.querySelectorAll("input");

        return {
          key: i[0].value,
          value: i[1].value
        };

      });


  try {

    await api(
      `/api/bots/${currentConfigBot}/config`,
      {
        method: "POST",

        headers: {
          "Content-Type":
            "application/json"
        },

        body: JSON.stringify({

          entrypoint:
            $("entrypoint").value,

          python_exec:
            $("python-exec").value,

          node_exec:
            $("node-exec").value,

          env

        })
      }
    );


    toast(
      "Configurações salvas."
    );

  } catch (e) {

    toast(e.message);

  }

}


/* =========================================================
   RUNTIMES
========================================================= */

async function loadRuntimes() {

  try {

    const x =
      await api("/api/runtimes");


    $("runtimes").innerHTML =

      (x.python || [])
        .map(v => `
          <div class="runtime">
            <b>Python ${esc(v.version)}</b>
            <small>${esc(v.path)}</small>
          </div>
        `)
        .join("")

      +

      (x.node || [])
        .map(v => `
          <div class="runtime">
            <b>Node.js ${esc(v.version)}</b>
            <small>${esc(v.path)}</small>
          </div>
        `)
        .join("");

  } catch (e) {}

}


/* =========================================================
   MODAL
========================================================= */

function openCreate() {

  $("modal")
    .classList
    .remove("hidden");

}


function closeModal() {

  $("modal")
    .classList
    .add("hidden");

  $("create-form").reset();

  clearSelectedFiles();

}


/* =========================================================
   UPLOAD DE ARQUIVOS
========================================================= */

const projectFiles =
  $("project-files");

const fileDrop =
  $("file-drop");

const selectedFiles =
  $("selected-files");


let selectedProjectFiles = [];


/*
    Quando o usuário seleciona arquivos
*/

projectFiles.addEventListener(
  "change",
  () => {

    addSelectedFiles(
      [...projectFiles.files]
    );

  }
);


/*
    Arrastar arquivos
*/

fileDrop.addEventListener(
  "dragover",
  event => {

    event.preventDefault();

    fileDrop.classList.add(
      "dragging"
    );

  }
);


fileDrop.addEventListener(
  "dragleave",
  () => {

    fileDrop.classList.remove(
      "dragging"
    );

  }
);


fileDrop.addEventListener(
  "drop",
  event => {

    event.preventDefault();

    fileDrop.classList.remove(
      "dragging"
    );


    const files =
      [...event.dataTransfer.files];


    addSelectedFiles(files);

  }
);


/*
    Adiciona arquivos à lista
*/

function addSelectedFiles(files) {

  files.forEach(file => {

    /*
      Evita duplicados
    */

    const exists =
      selectedProjectFiles.some(
        x =>
          x.name === file.name &&
          x.size === file.size &&
          x.lastModified ===
            file.lastModified
      );


    if (!exists)
      selectedProjectFiles.push(file);

  });


  renderSelectedFiles();

}


/*
    Lista visual
*/

function renderSelectedFiles() {

  selectedFiles.innerHTML = "";


  if (!selectedProjectFiles.length) {

    selectedFiles.innerHTML = `
      <div class="no-files">
        Nenhum arquivo selecionado.
      </div>
    `;

    return;

  }


  selectedProjectFiles.forEach(
    (file, index) => {

      const row =
        document.createElement("div");

      row.className =
        "selected-file";


      const size =
        formatFileSize(file.size);


      row.innerHTML = `

        <div class="file-info">

          <span class="file-icon">
            ${getFileIcon(file.name)}
          </span>

          <div>
            <b>${esc(file.name)}</b>
            <small>${size}</small>
          </div>

        </div>

        <button
          type="button"
          onclick="removeSelectedFile(${index})"
          title="Remover"
        >
          ×
        </button>

      `;


      selectedFiles.appendChild(row);

    }
  );

}


/*
    Remove arquivo
*/

function removeSelectedFile(index) {

  selectedProjectFiles.splice(
    index,
    1
  );

  renderSelectedFiles();

}


/*
    Limpa tudo
*/

function clearSelectedFiles() {

  selectedProjectFiles = [];

  renderSelectedFiles();

}


/*
    Ícones simples por extensão
*/

function getFileIcon(name) {

  const ext =
    name
      .split(".")
      .pop()
      .toLowerCase();


  const icons = {

    py: "PY",
    js: "JS",
    ts: "TS",
    jsx: "JS",
    tsx: "TS",

    json: "{}",

    txt: "TXT",
    md: "MD",

    html: "HTML",
    css: "CSS",

    zip: "ZIP",

    png: "IMG",
    jpg: "IMG",
    jpeg: "IMG",
    gif: "IMG",
    webp: "IMG",

    sql: "SQL",
    lua: "LUA",

    yml: "YML",
    yaml: "YML",

    xml: "XML",

    sh: "SH",
    bat: "BAT",
    ps1: "PS"

  };


  return icons[ext] || "FILE";

}


/*
    Tamanho
*/

function formatFileSize(bytes) {

  if (bytes < 1024)
    return `${bytes} B`;

  if (bytes < 1024 * 1024)
    return `${(bytes / 1024).toFixed(1)} KB`;

  if (bytes < 1024 * 1024 * 1024)
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;

  return `${(
    bytes /
    1024 /
    1024 /
    1024
  ).toFixed(1)} GB`;

}


/* =========================================================
   CRIAR BOT
========================================================= */

$("create-form")
  .addEventListener(
    "submit",
    async e => {

      e.preventDefault();


      try {

        const form =
          e.target;


        /*
          Dados básicos
        */

        const fd =
          new FormData();


        fd.append(
          "name",
          form.elements.name.value
        );


        fd.append(
          "runtime",
          form.elements.runtime.value
        );


        fd.append(
          "entrypoint",
          form.elements.entrypoint.value
        );


        /*
          Se nenhum arquivo foi enviado,
          mantém o comportamento antigo.
        */

        if (!selectedProjectFiles.length) {

          const x =
            await api(
              "/api/bots",
              {
                method: "POST",
                body: fd
              }
            );


          toast("Bot criado.");

          closeModal();

          await loadBots();

          currentConfigBot =
            x.id;

          return;

        }


        /*
          Cria ZIP no navegador.

          O backend continua recebendo
          exatamente um campo "zip".
        */

        toast(
          "Preparando arquivos..."
        );


        const zip =
          new JSZip();


        for (
          const file of selectedProjectFiles
        ) {

          /*
            webkitRelativePath permite
            preservar pastas quando o
            navegador fornecer esse caminho.
          */

          const path =
            file.webkitRelativePath ||
            file.name;


          zip.file(
            path,
            file
          );

        }


        const zipBlob =
          await zip.generateAsync({

            type: "blob",

            compression: "DEFLATE",

            compressionOptions: {
              level: 6
            }

          });


        /*
          O backend recebe como ZIP.
        */

        fd.append(
          "zip",
          zipBlob,
          "project.zip"
        );


        toast(
          "Enviando projeto..."
        );


        const x =
          await api(
            "/api/bots",
            {
              method: "POST",
              body: fd
            }
          );


        toast(
          "Bot criado com sucesso."
        );


        closeModal();


        await loadBots();


        currentConfigBot =
          x.id;


      } catch (e) {

        toast(e.message);

      }

    }
  );


/* =========================================================
   ADMIN
========================================================= */

async function unlockAdmin() {

  try {

    await api(
      "/api/admin/login",
      {
        method: "POST",

        headers: {
          "Content-Type":
            "application/json"
        },

        body: JSON.stringify({
          password:
            $("admin-password").value
        })
      }
    );


    adminUnlocked = true;

    $("admin-lock")
      .classList
      .add("hidden");

    $("admin-content")
      .classList
      .remove("hidden");


    loadAdmin();

  } catch (e) {

    toast(e.message);

  }

}


async function loadAdmin() {

  try {

    const s =
      await api(
        "/api/admin/status"
      );


    $("admin-total").textContent =
      s.total_bots;

    $("admin-online").textContent =
      s.online_bots;

    $("admin-host").textContent =
      s.host;


    const logs =
      await api(
        "/api/admin/logs"
      );


    $("logs").innerHTML =
      logs.map(l => `

        <div class="log">

          <b>${esc(l.action)}</b>

          <small>
            ${esc(l.created_at)}
          </small>

          <p>
            ${esc(l.message)}
          </p>

        </div>

      `).join("");


  } catch (e) {

    toast(e.message);

  }

}


/* =========================================================
   SEGURANÇA / HTML
========================================================= */

function esc(s) {

  return String(s ?? "")
    .replace(
      /[&<>"']/g,
      m => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
      }[m])
    );

}


function escAttr(s) {

  return esc(s);

}


/* =========================================================
   TOAST
========================================================= */

let toastTimer;


function toast(msg) {

  let el =
    document.getElementById(
      "toast"
    );


  if (!el) {

    el =
      document.createElement(
        "div"
      );


    el.id = "toast";


    el.style.cssText = `
      position:fixed;
      right:20px;
      bottom:20px;
      background:#171920;
      border:1px solid #343846;
      color:white;
      padding:12px 15px;
      border-radius:9px;
      z-index:50;
      font-size:12px;
    `;


    document.body.appendChild(el);

  }


  el.textContent = msg;


  clearTimeout(toastTimer);


  toastTimer =
    setTimeout(
      () => el.remove(),
      3000
    );

}


/* =========================================================
   ATUALIZAÇÃO AUTOMÁTICA
========================================================= */

setInterval(
  () => {

    if (
      $("page-console")
        .classList
        .contains("active") &&
      currentConsoleBot
    ) {

      loadConsole();

    }


    loadSystem();

  },
  3000
);


/* =========================================================
   INICIALIZAÇÃO
========================================================= */

renderSelectedFiles();

refreshAll();
