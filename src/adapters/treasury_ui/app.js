"use strict";

// Everything the server sends is put on the page with textContent, never as HTML.

const TABS = ["ldn", "tor", "ledger"];
const REFRESH_MS = 3000;
let formId = crypto.randomUUID();
let busy = false;
let again = false;

function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs || {})) {
    if (name === "class") node.className = value;
    else if (name === "text") node.textContent = value;
    else node.setAttribute(name, value);
  }
  for (const child of children) node.append(child);
  return node;
}

async function api(method, path, body) {
  const options = { method, headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  let data = {};
  try { data = await response.json(); } catch (_) { /* not JSON */ }
  return { status: response.status, data };
}

function say(kind, message) {
  const notice = document.getElementById("notice");
  notice.className = "notice " + kind;
  notice.textContent = message;
  notice.hidden = false;
}

function describe(result) {
  const { status, data } = result;
  const text = data.message || data.error || "HTTP " + status;
  if (data.status === "done") return ["done", text];
  if (data.status === "pending") return ["pending", text];
  return ["error", text];
}

// ---- tabs ----

function showTab(name) {
  for (const tab of TABS) {
    document.getElementById("tab-" + tab).setAttribute("aria-selected", String(tab === name));
    document.getElementById("view-" + tab).hidden = tab !== name;
  }
  refresh();
}

// ---- rows ----

function chip(status) {
  return el("span", { class: "chip " + status, text: status });
}

function requestRow(request, buttons) {
  const head = el("div", { class: "head" },
    el("span", { class: "amount", text: "CAD " + request.amountCad }),
    chip(request.status),
    el("span", { class: "meta", text: request.processingDate + " · " + request.requester }),
  );
  const row = el("div", { class: "row" }, head);
  if (request.amountGbp !== null) {
    row.append(el("div", { class: "meta", text: "GBP " + request.amountGbp + " at " + request.rate }));
  }
  if (request.note) row.append(el("div", { class: "note", text: request.note }));
  if (buttons) row.append(buttons);
  return row;
}

function fill(container, rows, emptyText) {
  container.replaceChildren(...(rows.length ? rows : [el("div", { class: "empty", text: emptyText })]));
}

function actionButton(label, onClick, danger) {
  const button = el("button", { type: "button", class: "action" + (danger ? " danger" : ""), text: label });
  button.addEventListener("click", async () => {
    button.disabled = true;
    try { await onClick(); } finally { button.disabled = false; }
  });
  return button;
}

async function act(path, body) {
  const result = await api("POST", path, body);
  const [kind, message] = describe(result);
  say(kind, message);
  await refresh();
}

// ---- views ----

async function drawLondon() {
  const { data } = await api("GET", "/api/requests");
  const mine = (data.requests || []).filter((r) => r.requester === "ldn");
  fill(document.getElementById("mine"), mine.map((r) => requestRow(r)), "No requests yet.");
  const fx = await api("GET", "/api/fx");
  if (fx.data.today) document.getElementById("date").value = fx.data.today.date;
}

async function drawToronto() {
  const { data } = await api("GET", "/api/requests");
  const all = data.requests || [];
  const signer = () => document.getElementById("actas").value;
  const pending = all.filter((r) => r.status === "requested").map((r) => {
    const reason = el("input", { type: "text", maxlength: "140", placeholder: "Reason (to reject)", "aria-label": "Rejection reason" });
    const buttons = el("div", { class: "reason" },
      actionButton("Approve", () => act("/api/requests/" + r.id + "/approve", { as: signer() })),
      reason,
      actionButton("Reject", () => act("/api/requests/" + r.id + "/reject", { as: signer(), reason: reason.value }), true),
    );
    return requestRow(r, buttons);
  });
  fill(document.getElementById("pending"), pending, "Nothing waiting.");
  const approved = all.filter((r) => r.status === "approved").map((r) =>
    requestRow(r, el("div", {}, actionButton("Retry settle", () => act("/api/requests/" + r.id + "/retry-settle", {})))));
  fill(document.getElementById("approved"), approved, "Nothing with the treasury.");
}

function table(headers, rows) {
  const head = el("tr", {}, ...headers.map((h, i) => el("th", { class: i ? "num" : "", text: h })));
  const body = rows.map((cells) => el("tr", {}, ...cells.map((c, i) => el("td", { class: i ? "num" : "", text: c }))));
  return el("table", {}, el("thead", {}, head), el("tbody", {}, ...body));
}

async function drawLedger() {
  const [requests, balances, fx] = await Promise.all([
    api("GET", "/api/requests"), api("GET", "/api/balances"), api("GET", "/api/fx"),
  ]);
  const b = balances.data;
  if (b.balances) {
    const wallets = Object.entries(b.balances).map(([name, held]) => [name, held.cadc, held.gbpc]);
    wallets.push(["total supply", b.supply.cadc, b.supply.gbpc]);
    const verdict = el("p", {
      class: "books " + (b.conserved ? "ok" : "bad"),
      text: b.conserved ? "Books balance: supplies match the requests." : "Books do NOT balance: " + b.problem,
    });
    document.getElementById("books").replaceChildren(verdict, table(["Wallet", "CADC", "GBPC"], wallets));
  }
  const rows = (requests.data.requests || []).map((r) => {
    const row = requestRow(r);
    const steps = el("ul", { class: "steps" });
    row.append(actionButton("Steps", async () => {
      const one = await api("GET", "/api/requests/" + r.id);
      steps.replaceChildren(...(one.data.steps || []).map((s) =>
        el("li", { text: s.action + " · " + s.outcome + (s.operationId ? " · operation " + s.operationId : "") })));
      if (!steps.childNodes.length) steps.append(el("li", { text: "No writes recorded by this app run." }));
    }), steps);
    return row;
  });
  fill(document.getElementById("all"), rows, "No requests yet.");
  const f = fx.data;
  if (f.pair) {
    const entries = Object.entries(f.dates).map(([day, rate]) => [day, rate]);
    entries.push(["default", f.default === null ? "none" : f.default]);
    const today = f.today.rate === null ? "no rate for " + f.today.date : f.today.rate + " (" + f.today.source + ")";
    document.getElementById("fx").replaceChildren(
      el("p", { class: "meta", text: "Applies today (" + f.today.date + "): " + today }),
      table(["Date", "GBP per CAD"], entries));
  }
}

function currentTab() {
  return TABS.find((t) => !document.getElementById("view-" + t).hidden);
}

async function refresh() {
  if (busy) { again = true; return; }
  busy = true;
  try {
    const tab = currentTab();
    if (tab === "ldn") await drawLondon();
    else if (tab === "tor") await drawToronto();
    else await drawLedger();
  } catch (error) {
    say("error", "Cannot reach the app: " + error.message);
  } finally {
    busy = false;
  }
  if (again) { again = false; await refresh(); }
}

// ---- wiring ----

for (const tab of TABS) {
  document.getElementById("tab-" + tab).addEventListener("click", () => showTab(tab));
}

document.getElementById("create").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.target.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    const amount = document.getElementById("amount").value;
    const result = await api("POST", "/api/requests", { as: "ldn", amount, id: formId });
    const [kind, message] = describe(result);
    say(kind, message);
    if (result.data.status === "done") {
      formId = crypto.randomUUID(); // a new form is a new request; a retry keeps the same id
      document.getElementById("amount").value = "";
    }
    await refresh();
  } finally {
    button.disabled = false;
  }
});

setInterval(refresh, REFRESH_MS);
showTab("ldn");
