import { renderDocument } from "./markdown.js";
const $ = (s, root = document) => root.querySelector(s);
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const money = (value) =>
  Number.isFinite(Number(value))
    ? new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 0,
      }).format(value)
    : "Not quoted";
const gram = (value) =>
  value == null ? "Not measured" : `${Number(value).toFixed(2)} g`;
const when = (value) =>
  value
    ? new Date(typeof value === "number" ? value * 1000 : value).toLocaleString(
        "en-IN",
        { dateStyle: "medium", timeStyle: "short" },
      )
    : "Not recorded";
const statusLabel = (text) =>
  ({
    needs_info: "Needs your answer",
    infeasible: "Cannot meet this brief",
    out_of_scope: "Outside our collection",
    done: "Ready",
    failed: "Needs attention",
    queued: "In the queue",
    running: "In the workshop",
    solved: "Numbers ready",
    pass: "Pass",
    warn: "Review",
    fail: "Failed",
    current: "Current",
  })[text] || text;
const badge = (text) =>
  `<span class="badge ${esc(String(text).replace(/[^a-z_]/g, ""))}">${esc(statusLabel(text))}</span>`;
const file = (path) =>
  typeof path === "string" &&
  /^\/files\/[A-Za-z0-9_-]+\/[A-Za-z0-9_.-]+$/.test(path)
    ? path
    : "";
const link = (path, label) =>
  file(path)
    ? `<a class="quiet" href="${esc(path)}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>`
    : "";
const state = {
  token: sessionStorage.getItem("karigar-owner") || "",
  data: null,
  selected: {},
  chat: [],
  busy: false,
  chatText: "",
  catalogue: null,
};
let currentRoute = "";
let pendingRender = false;
const viewMemory = new Map();
function rememberView() {
  if (!currentRoute) return;
  const fields = Array.from(
    document.querySelectorAll(
      "#main input[id], #main textarea[id], #main select[id]",
    ),
  ).map((e) => [e.id, e.value]);
  const details = Array.from(
    document.querySelectorAll("#main details[open]"),
  ).map((e) => $("summary", e)?.textContent);
  const cameras = Array.from(
    document.querySelectorAll("#main model-viewer"),
  ).map((e) => {
    const o = e.getCameraOrbit?.();
    return {
      src: e.getAttribute("src"),
      orbit: o ? `${o.theta}rad ${o.phi}rad ${o.radius}m` : null,
      rotate: e.autoRotate,
    };
  });
  viewMemory.set(currentRoute, { fields, details, cameras });
}
function restoreView(full = true) {
  const memory = viewMemory.get(currentRoute);
  if (!memory) return;
  for (const [id, value] of full ? memory.fields : []) {
    const e = document.getElementById(id);
    if (e) e.value = value;
  }
  document
    .querySelectorAll("#main details")
    .forEach(
      (e) => (e.open = memory.details.includes($("summary", e)?.textContent)),
    );
  if (full)
    document.querySelectorAll("#main model-viewer").forEach((e, i) => {
      const previous = memory.cameras[i];
      if (previous?.src === e.getAttribute("src")) {
        if (previous.orbit) e.cameraOrbit = previous.orbit;
        e.autoRotate = previous.rotate;
      }
    });
  const spin = $("#spin-view"),
    mv = $("#main model-viewer");
  if (spin && mv) {
    spin.textContent = mv.autoRotate
      ? "Pause rotation"
      : "Rotate automatically";
    spin.setAttribute("aria-pressed", String(!!mv.autoRotate));
  }
}
let noticeTimer;
function toast(text) {
  $("#toast").textContent = text;
  $("#toast").hidden = false;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => ($("#toast").hidden = true), 6000);
}
async function api(path, body, options = {}) {
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      Authorization: `Bearer ${state.token}`,
      "Content-Type": "application/json",
      ...options.headers,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    ...options,
  });
  if (response.status === 401) {
    signOut();
    throw new Error("Access token was rejected. Sign in with the owner token.");
  }
  if (!response.ok) {
    let error;
    try {
      error = await response.json();
    } catch {}
    throw new Error(
      error?.error?.message ||
        `Request failed (${response.status}). Try again.`,
    );
  }
  return response.json();
}
function signOut() {
  viewMemory.clear();
  currentRoute = "";

  state.token = "";
  state.data = null;
  state.chat = [];
  sessionStorage.removeItem("karigar-owner");
  $("#shell").hidden = true;
  $("#login").hidden = false;
  $("#token").value = "";
}
function empty(title, text, action = "", target = "#studio") {
  return `<div class="empty"><h2>${esc(title)}</h2><p>${esc(text)}</p>${action ? `<a class="primary" href="${target}">${esc(action)}</a>` : ""}</div>`;
}
function heading(title, text, actions = "") {
  return `<div class="page-head"><div><h1>${esc(title)}</h1><p>${esc(text)}</p></div>${actions ? `<div class="actions">${actions}</div>` : ""}</div>`;
}
function versions(order) {
  return Object.values(order?.versions || {}).sort(
    (a, b) => Number(a.version) - Number(b.version),
  );
}
function picked(order) {
  const vs = versions(order);
  return (
    vs.find(
      (r) => String(r.version) === String(state.selected[order.order_id]),
    ) || vs[vs.length > 3 ? vs.length - 1 : Math.floor(vs.length / 2)]
  );
}
function getShop() {
  const shop = state.data?.shop || {};
  return shop.current || {};
}
function getCatalogue() {
  return state.data?.shop?.catalogue?.catalogue || [];
}
function renderImage(r, cls = "") {
  const src = file(r?.files?.render_hero);
  return src
    ? `<img class="${cls}" src="${esc(src)}" alt="${esc(r.variant)} generated by the Karigar engine" loading="lazy" width="720" height="720">`
    : `<div class="loading">Render not available yet.</div>`;
}
function model(r) {
  const src = file(r?.files?.glb);
  return src
    ? `<model-viewer src="${esc(src)}" ${file(r?.files?.render_hero) ? `poster="${esc(file(r.files.render_hero))}"` : ""} alt="Rotatable ${esc(r.variant)} jewellery model" camera-controls touch-action="pan-y" shadow-intensity="1" exposure="1.1" interaction-prompt="none" loading="eager"></model-viewer>`
    : renderImage(r);
}
const heroBrief =
  "Purani 8.4g 22K chain exchange karni hai, uske badle 22K ladies ring chahiye, size 12, chhota floral design";
function newForm(text = "") {
  return `<form id="new-form" class="brief-panel"><h1>A wish. A design.<br>Your gold.</h1><p>Tell Sakhi what you want to make. Karigar takes it to the workshop.</p><div><label for="request">Your brief / Aapki farmaish</label><textarea id="request" name="text" maxlength="2000" required placeholder="Purane sone se kuch naya…">${esc(text)}</textarea><p class="field-help">Include the piece, purity, size, and old gold, weight or budget.</p></div><div class="examples"><button type="button" data-example="old">Old gold to floral ring</button><button type="button" data-example="budget">Budget solitaire</button></div><button type="submit" class="primary">Create my designs</button><small>Every quote uses the shop's timestamped rate. No rate is guessed.</small><p id="form-error" role="alert"></p></form>`;
}
function studio() {
  const recent = state.data.orders.find((o) =>
    versions(o).some((r) => file(r.files?.glb) || file(r.files?.render_hero)),
  );
  const r = recent ? picked(recent) : getCatalogue()[0];
  return `<div class="studio"><div class="studio-canvas">${r ? `${model(r)}<div class="canvas-caption"><span>${esc(r.variant)}</span><span>${r.weights ? gram(r.weights.finished_g) : "Engine-generated design"}</span></div>` : `<div class="studio-empty"><h2>Old gold.<br>New story.</h2><div><div class="metal-line"></div><p>Your first piece will appear here, built from your brief and measured to your gold.</p></div></div>`}</div>${newForm(sessionStorage.getItem("karigar-draft") || "")}</div><div class="process"><span><strong>Describe</strong>In your own words</span><span><strong>Compare</strong>Three design directions</span><span><strong>Inspect</strong>Weight, quote and mesh</span><span><strong>Make</strong>Production files for the caster</span></div><section class="section"><div class="page-head"><h2>On the workbench</h2><a class="quiet" href="#orders">View orders</a></div>${ordersTable(state.data.orders.slice(0, 4))}</section>`;
}
function ordersTable(orders) {
  if (!orders.length)
    return empty(
      "Your next piece starts here",
      "Create an order to see its designs, quote and production files.",
      "Create a design",
    );
  return `<div class="table-wrap"><table><thead><tr><th>Order / Brief</th><th>Status</th><th class="num">Finished gold</th><th class="num">Quote</th><th>Created</th></tr></thead><tbody>${orders
    .map((o) => {
      const r = picked(o);
      return `<tr><td><a href="#order/${encodeURIComponent(o.order_id || o.job_id)}">${esc(o.order_id || "Request pending")}</a><small>${esc(o.brief ? `${o.brief.karat}K ${o.brief.piece_type}` : o.messages[0]?.text?.slice(0, 85))}</small></td><td>${badge(o.status)}</td><td class="num">${r ? gram(r.weights?.finished_g) : "Pending"}</td><td class="num">${r ? money(r.quote?.total) : "Pending"}</td><td>${when(o.created)}</td></tr>`;
    })
    .join("")}</tbody></table></div>`;
}
function orders(params) {
  const search = params.get("q") || "",
    status = params.get("status") || "";
  const filtered = state.data.orders.filter(
    (o) =>
      (!status || o.status === status) &&
      JSON.stringify([o.order_id, o.brief, o.messages.map((m) => m.text)])
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  return `${heading("Every piece has a story", "Your requests, designs and revisions, together.")}<form id="filters" class="toolbar"><label class="visually-hidden" for="search">Search orders</label><input id="search" name="q" type="search" placeholder="Find an order or a brief" value="${esc(search)}"><label class="visually-hidden" for="status-filter">Order status</label><select name="status" id="status-filter"><option value="">All statuses</option>${["queued", "running", "solved", "done", "needs_info", "infeasible", "failed"].map((s) => `<option ${s === status ? "selected" : ""} value="${s}">${esc(statusLabel(s))}</option>`).join("")}</select><button type="submit">Filter orders</button></form>${filtered.length ? ordersTable(filtered) : empty("No matching orders", "Try a different phrase or clear the status filter.", "Clear filters", "#orders")}`;
}
function variant(r, order) {
  return `<article class="variant ${picked(order) === r ? "selected" : ""}">${renderImage(r)}<h3>${esc(r.variant)}</h3><p>${gram(r.weights?.finished_g)} <small>± ${gram(r.weights?.tolerance_g)} finished</small></p><p>${money(r.quote?.total)}</p><div class="actions"><button class="select-variant" data-order="${esc(order.order_id)}" data-version="${esc(r.version)}">Inspect v${esc(r.version)}</button>${link(r.files?.glb, "Open GLB")}</div></article>`;
}
function quote(r) {
  const q = r?.quote;
  if (!q)
    return empty(
      "Quote pending",
      "The worker will calculate the quote after solving the design.",
    );
  return `<table><thead><tr><th>Quote line and source</th><th class="num">Amount</th></tr></thead><tbody>${(q.lines || []).map((l) => `<tr><td>${esc(l.label)} ${l.assumed ? badge("assumed") : ""}<small>${esc(l.source)}</small></td><td class="num">${money(l.amount_inr)}</td></tr>`).join("")}</tbody></table><div class="quote-total"><span>Total</span><strong>${money(q.total)}</strong></div>${q.to_pay != null ? `<div class="quote-total"><span>After old-gold credit</span><strong>${money(q.to_pay)}</strong></div>` : ""}<p class="sources">${esc(q.summary || "")}</p>`;
}
function checks(list) {
  return list?.length
    ? `<div class="checks">${list.map((c) => `<div>${badge(c.status)}<p>${esc(c.rule.replaceAll("_", " "))}${c.measured_mm == null ? "" : `: ${Number(c.measured_mm).toFixed(2)} mm`}<small>${esc(c.text || c.location)}</small></p></div>`).join("")}</div>`
    : '<p class="muted">Open the job card for the measured mesh checks.</p>';
}
function detail(id) {
  const o = state.data.orders.find(
    (o) => (o.order_id || o.job_id) === id || o.job_ids?.includes(id),
  );
  if (!o)
    return empty(
      "Order not found",
      "Sync the workshop and check the order identifier.",
      "View orders",
      "#orders",
    );
  const vs = versions(o),
    r = picked(o),
    w = r?.weights || {};
  const latest = o.messages.at(-1)?.result || {};
  return `${heading(o.order_id || "Request in progress", o.brief ? `${o.brief.karat}K ${o.brief.piece_type}, ${o.brief.metal || "yellow"} gold` : "Waiting for the workshop", badge(o.status))}<p class="brief-text">“${esc(o.messages[0]?.text)}”</p>${o.error ? `<p class="error">The workshop reported ${esc(o.error)}. Check the worker, then retry the request.</p>` : ""}${latest.question ? `<p class="notice">${esc(latest.question)}</p><form id="continue-form" data-conversation="${esc(o.conversation)}" class="edit-form"><label class="visually-hidden" for="answer">Your answer</label><input id="answer" maxlength="2000" required placeholder="Answer Sakhi's question"><button class="primary">Send answer</button></form>` : ""}${latest.explanation ? `<p class="notice">${esc(latest.explanation)}</p>` : ""}${
    !r
      ? empty(
          "The workshop is on it",
          "Specs and numbers appear first. Renders and production files follow when ready.",
        )
      : `<section class="section"><h2>Choose your direction</h2><div class="variants">${vs
          .slice(0, 3)
          .map((v) => variant(v, o))
          .join(
            "",
          )}</div></section><section class="section split"><div><div class="page-head"><h2>${esc(r.variant)}</h2><a class="quiet" href="#viewer/${encodeURIComponent(o.order_id)}/${r.version}">Inspect in 3D</a></div><div class="studio-canvas">${model(r)}</div><div class="summary-figures"><div><strong>${gram(w.finished_g)}</strong><span>Expected finished</span></div><div><strong>${gram(w.casting_g || w.modelled_g)}</strong><span>Modelled for casting</span></div><div><strong>± ${gram(w.tolerance_g)}</strong><span>Expected tolerance</span></div></div><p class="sources">${esc(r.quote?.weight_text || r.quote?.weights?.weight_text || "Workshop loss and tolerance are configured assumptions until calibrated.")}</p><div class="actions">${Object.entries(
          r.files || {},
        )
          .map(([k, v]) =>
            link(
              v,
              {
                stl: "Casting STL",
                glb: "3D model",
                job_card_md: "Workshop job card",
                quote: "Quote JSON",
                render_hero: "Hero render",
              }[k] || k.replaceAll("_", " "),
            ),
          )
          .join(
            "",
          )}</div></div><div><h2>The quote, explained</h2>${quote(r)}</div></section><section class="section split"><div><h2>Make it yours</h2><p class="field-help">Edits re-run the solver and checks. Your gold target holds unless you change it.</p><form id="edit-form" data-order="${esc(o.order_id)}" data-version="${r.version}" class="edit-form"><label class="visually-hidden" for="edit">Describe your edit</label><input id="edit" required maxlength="2000" placeholder="Make the flower slightly bigger"><button class="primary">Refine this design</button></form><p id="edit-error" role="alert"></p>${o.edit ? `<p class="notice">${esc(o.edit.summary)}</p>` : ""}<details><summary>Versions and changes</summary>${vs.map((v) => `<p><button class="quiet select-variant" data-order="${esc(o.order_id)}" data-version="${v.version}">v${v.version}: ${esc(v.variant)}</button> ${gram(v.weights?.finished_g)}, ${money(v.quote?.total)}</p>`).join("")}</details><details><summary>Parsed brief and assumptions</summary><pre>${esc(JSON.stringify(o.brief, null, 2))}</pre></details><details><summary>Design dimensions and parameters</summary><pre>${esc(JSON.stringify(r.spec || {}, null, 2))}</pre></details></div><div><h2>Ready for the workshop?</h2><div id="mesh-checks" class="section">${checks(r.mesh_checks)}</div><div id="job-card" class="section"></div></div></section>`
  }`;
}
function catalogue() {
  const rows = getCatalogue();
  return `${heading("A collection with possibilities", "Original parametric families. Measured, rotatable, made to your gold.", `<button class="primary" data-action="catalogue">${rows.length ? "Rebuild collection" : "Build collection"}</button>`)}${
    rows.length
      ? `<div class="catalogue">${rows
          .map(
            (r) =>
              `<article class="variant">${renderImage(r)}<h2>${esc(r.variant)}</h2><p class="field-help">${esc(r.spec.karat)}K ${esc(r.piece_type)} at catalogue scale, modelled grams</p><div class="summary-figures">${Object.entries(
                r.catalogue_weights || {},
              )
                .map(
                  ([name, g]) =>
                    `<div><strong>${gram(g)}</strong><span>${esc(name)}</span></div>`,
                )
                .join(
                  "",
                )}</div><div class="actions"><button class="primary" data-start-family="${esc(r.family)}">Start with this design</button><a class="quiet" href="#viewer/catalogue/${r.version}">View in 3D</a></div></article>`,
          )
          .join("")}</div>`
      : empty(
          "Your collection is waiting",
          "Ask the worker to build the catalogue. Real renders and measured weights will appear here; rendering takes a few minutes.",
        )
  }`;
}
function viewer(id, version) {
  const rows =
    id === "catalogue"
      ? getCatalogue()
      : versions(state.data.orders.find((o) => o.order_id === id));
  const r =
    rows.find((r) => String(r.version) === version) ||
    rows.find((r) => file(r.files?.glb)) ||
    getCatalogue()[0] ||
    state.data.orders.flatMap(versions).find((r) => file(r.files?.glb));
  if (!r)
    return `${heading("Look closer", "Rotate the actual model, then take it to the workshop.")}${empty("No 3D model yet", "Complete a design or build the catalogue to inspect its real GLB.", "Create a design")}`;
  return `${heading(r.variant, "Drag to rotate. Pinch or scroll to inspect the details.")}<div class="viewer-layout"><div>${model(r)}<div class="viewer-controls"><button id="reset-view">Reset view</button><button id="spin-view" aria-pressed="false">Rotate automatically</button>${link(r.files?.glb, "Download GLB")}${link(r.files?.stl, "Download casting STL")}</div><p id="viewer-error" role="status" class="field-help">The GLB shows the design at real-world scale. STL includes configured casting shrinkage.</p></div><div class="stack"><h2>The piece behind the picture</h2><p>${esc(r.spec?.karat || "")}K ${esc(r.spec?.piece_type || "")} ${esc(r.spec?.metal || "")} gold</p>${r.weights ? `<div class="summary-figures"><div><strong>${gram(r.weights.finished_g)}</strong><span>Finished</span></div><div><strong>${gram(r.weights.casting_g)}</strong><span>Casting</span></div></div>` : ""}${checks(r.mesh_checks)}<details><summary>Design specification</summary><pre>${esc(JSON.stringify(r.spec || {}, null, 2))}</pre></details></div></div>`;
}
function rates() {
  const shop = getShop();
  const rows = shop.rates || [];
  return `${heading("Gold has a timestamp", "The current shop rate is used by the engine, never estimated.", `<button class="primary" data-action="rates_refresh">Refresh from MCX</button>`)}${shop.notice ? `<p class="notice">${esc(shop.notice)}</p>` : ""}${rows.length ? `<div class="table-wrap"><table><thead><tr><th>Purity</th><th class="num">Rate per gram</th><th>Status</th><th>Updated</th><th>Source</th></tr></thead><tbody>${rows.map((r) => `<tr><td>${r.karat}K</td><td class="num">${r.rate_per_g ? money(r.rate_per_g) : "Missing"}</td><td>${badge(r.status)}</td><td>${when(r.set_at)}</td><td>${esc(r.source || "Not set")}</td></tr>`).join("")}</tbody></table></div><section class="section"><h2>How the rate reaches your quote</h2><p class="sources">${shop.rate_policy ? `MCX plus ${money(shop.rate_policy.mcx_premium_per_10g)} per 10 g. Maximum age: ${esc(shop.rate_policy.max_age_h)} hours. Source: ${esc(shop.rate_policy.mcx_url)}.` : "Sync shop data to load the rate policy."} Chat messages from unknown senders cannot change the rate.</p></section>` : empty("No shop snapshot yet", "Sync shop data to read rates from the worker. Refreshing requires internet on the worker.")}<section class="section"><h2>Rates preserved in your quotes</h2><p class="field-help">Each order keeps the timestamp and source used for its quote.</p>${state.data.orders.flatMap((o) => versions(o).map((r) => ({ o, r }))).length ? `<div class="table-wrap"><table><thead><tr><th>Order / version</th><th>Gold source at quote time</th></tr></thead><tbody>${state.data.orders.flatMap((o) => versions(o).map((r) => `<tr><td>${esc(o.order_id)} / v${r.version}</td><td>${esc((r.quote?.lines || []).find((l) => l.key === "gold")?.source || "No source recorded")}</td></tr>`)).join("")}</tbody></table></div>` : '<p class="muted">Rate history appears with completed quotes.</p>'}</section>`;
}
function workshop() {
  const rows = getShop().workshops || [];
  return `${heading("The workshop learns your hand", "Record actual finished weight to improve the next prediction.")}<div class="split"><div><h2>Record a casting</h2><form id="calibrate-form" class="form-grid section"><div class="wide"><label for="cast-order">Use an order's casting weight</label><select id="cast-order"><option value="">Enter manually</option>${state.data.orders.flatMap((o) => versions(o).map((r) => `<option value="${esc(r.weights?.casting_g || r.weights?.modelled_g || "")}">${esc(o.order_id)} / v${r.version}</option>`)).join("")}</select></div><div class="wide"><label for="workshop-name">Workshop name</label><input id="workshop-name" name="workshop" maxlength="64" required value="${esc(rows[0]?.name || "demo-workshop")}"></div><div><label for="designed">Designed / casting grams</label><input id="designed" name="designed_g" type="number" min="0.001" max="500" step="0.001" required></div><div><label for="actual">Actual finished grams</label><input id="actual" name="actual_g" type="number" min="0.001" max="500" step="0.001" required></div><button class="primary wide">Record actual weight</button><p id="calibrate-error" class="wide" role="alert"></p></form></div><div><h2>Workshop calibration</h2>${rows.length ? rows.map((w) => `<div class="section"><h3>${esc(w.name)}</h3><div class="summary-figures"><div><strong>${w.loss_pct.toFixed(2)}%</strong><span>Expected loss</span></div><div><strong>${w.records.length}</strong><span>Recorded casts</span></div><div><strong>± ${Number(w.tolerance.pct || w.tolerance.tolerance_pct || 0).toFixed(1)}%</strong><span>Expected tolerance</span></div></div><p class="sources">${esc(w.tolerance.source || "Configured workshop assumption until enough actual casts are recorded.")}</p><details><summary>Cast records</summary>${w.records.map((r) => `<p>${gram(r.designed_g)} designed, ${gram(r.actual_g)} actual, ${when(r.ts)}</p>`).join("") || "No actual casts recorded."}</details></div>`).join("") : empty("No calibration snapshot", "Sync shop data to read the worker’s calibration records.")}</div></div>`;
}
function demo() {
  return `${heading("Speak the language of the shop", "The same streamed replies that Sakhi and Karigar send to Nonilion.", `<button id="clear-chat">New conversation</button>`)}<div class="chat"><div class="chat-log" id="chat-log">${state.chat.length ? state.chat.map((m) => `<div class="message ${esc(m.role)}"><strong>${m.role === "user" ? "You" : "Karigar"}</strong><div>${markdown(m.content)}</div></div>`).join("") : empty("Sakhi is listening", "Try an old-gold exchange, a budget or an impossible request.")}</div><form id="chat-form"><label for="chat-text">Your message / Aapka sawaal</label><textarea id="chat-text" maxlength="2000" required placeholder="${esc(heroBrief)}">${esc(state.chatText)}</textarea><div class="actions section"><button class="primary" ${state.busy ? "disabled" : ""}>${state.busy ? "Workshop is working…" : "Send to the workshop"}</button><button type="button" data-chat-example>Use old-gold example</button></div><p id="chat-error" role="alert" class="field-help"></p></form></div>`;
}
function system() {
  const s = state.data.system;
  return `${heading("The workshop, at a glance", "Service queue and the laptop worker. No hidden rendering dependency.", `<button id="reload">Refresh status</button>`)}<div class="summary-figures"><div><strong>${s.worker_online ? "Online" : "Offline"}</strong><span>Blender worker</span></div><div><strong>${s.queue_depth}</strong><span>Queued jobs</span></div><div><strong>${s.running}</strong><span>Running jobs</span></div></div><p class="sources">Build ${esc(s.version)}. The worker makes outgoing calls to this service. If offline, start the worker on the workshop laptop; requests remain queued.</p><section class="section"><h2>Recent jobs</h2><div class="table-wrap"><table><thead><tr><th>Job</th><th>Kind</th><th>Status</th><th>Last update</th><th>Error</th></tr></thead><tbody>${s.jobs.map((j) => `<tr><td>${esc(j.job_id)}</td><td>${esc(j.kind)}</td><td>${badge(j.status)}</td><td>${when(j.updated)}</td><td>${esc(j.error || "None")}</td></tr>`).join("")}</tbody></table></div></section>`;
}
function markdown(text) {
  return esc(text)
    .replace(
      /\[([^\]]+)\]\((\/files\/[A-Za-z0-9_/-]+\.[A-Za-z0-9]+|https:\/\/[^\s<]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>',
    )
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
}
function render() {
  if (!state.data) return;
  rememberView();
  const hash = location.hash.slice(1) || "studio";
  const [path, query] = hash.split("?");
  const [route, id, ver] = path.split("/");
  const params = new URLSearchParams(query);
  currentRoute = hash;
  const labels = {
    studio: "Design studio",
    orders: "Orders",
    order: "Order detail",
    catalogue: "Design catalogue",
    viewer: "3D showroom",
    rates: "Gold rate",
    workshop: "Workshop",
    demo: "Try in Hinglish",
    system: "System",
  };
  $("#breadcrumb").textContent =
    `${state.data.orders.some((o) => o.messages.some((m) => m.text?.startsWith("SAMPLE"))) ? "Sample workshop / " : "Jewellery / "}${labels[route] || "Design studio"}`;
  document.querySelectorAll("nav a").forEach((a) => {
    a.removeAttribute("aria-current");
    if (a.hash === `#${route === "order" ? "orders" : route}`)
      a.setAttribute("aria-current", "page");
  });
  $("#rail-health").textContent = state.data.system.worker_online
    ? "Workshop online"
    : "Workshop offline";
  $("#main").innerHTML = (
    {
      studio: () => studio(),
      orders: () => orders(params),
      order: () => detail(decodeURIComponent(id || "")),
      catalogue,
      viewer: () => viewer(decodeURIComponent(id || ""), ver),
      rates,
      workshop,
      demo,
      system,
    }[route] || studio
  )();
  bind();
  restoreView();
  document.querySelectorAll(".table-wrap").forEach((e) => {
    e.tabIndex = 0;
    e.setAttribute("role", "region");
    e.setAttribute("aria-label", "Scrollable data table");
    if (!e.previousElementSibling?.classList.contains("scroll-hint")) {
      const hint = document.createElement("p");
      hint.className = "scroll-hint";
      hint.textContent = "Swipe or scroll to see all columns.";
      e.before(hint);
    }
  });
  if (route === "order") {
    const order = state.data.orders.find(
      (o) => o.order_id === id || o.job_ids?.includes(id),
    );
    if (order)
      api(`/api/console/jobs/${order.job_id}/seen`, {}).catch((e) =>
        toast(e.message),
      );
    loadJobCard(decodeURIComponent(id || "")).then(() => restoreView(false));
  }
}
async function loadJobCard(id) {
  const order = state.data.orders.find(
      (o) => o.order_id === id || o.job_ids?.includes(id),
    ),
    r = order && picked(order);
  const card = file(r?.files?.job_card);
  if (!card) return;
  try {
    const response = await fetch(card);
    if (!response.ok) return;
    const job = await response.json();
    if (
      currentRoute.startsWith(`order/${encodeURIComponent(id)}`) &&
      $("#mesh-checks")
    ) {
      $("#mesh-checks").innerHTML = checks(job.mesh_checks);
      const mdPath = file(r.files?.job_card_md);
      const md = mdPath
        ? await fetch(mdPath).then((r) => (r.ok ? r.text() : ""))
        : "";
      if ($("#job-card"))
        $("#job-card").innerHTML =
          `<details><summary>Workshop job card</summary><div class="job-card">${md ? renderDocument(md) : `<pre>${esc(JSON.stringify(job, null, 2))}</pre>`}${link(r.files?.job_card_md, "Open Markdown job card")}</div></details>`;
    }
  } catch {}
}
async function refresh(force = false) {
  const next = await api("/api/console");
  const changed = JSON.stringify(next) !== JSON.stringify(state.data);
  state.data = next;
  $("#login").hidden = true;
  $("#shell").hidden = false;
  if (
    force ||
    ((changed || pendingRender) &&
      !["INPUT", "TEXTAREA", "SELECT"].includes(
        document.activeElement?.tagName,
      ) &&
      !state.busy)
  ) {
    pendingRender = false;
    render();
  } else if (changed) {
    pendingRender = true;
  }
}
async function action(name, extra = {}) {
  const res = await api("/api/console/actions", { action: name, ...extra });
  toast("Sent to the workshop. Results appear when the worker finishes.");
  await refresh(true);
  watchJob(res.job_id);
}
async function watchJob(id) {
  for (let i = 0; i < 300 && state.token; i++) {
    await new Promise((r) => setTimeout(r, 2000));
    const job = await api(`/api/jobs/${id}`);
    if (["done", "failed"].includes(job.status)) {
      toast(
        job.status === "done"
          ? "Workshop update ready."
          : `Workshop could not finish: ${job.error || "check worker logs"}`,
      );
      await refresh(true);
      return;
    }
  }
}
function bind() {
  document.querySelectorAll("[data-example]").forEach(
    (b) =>
      (b.onclick = () => {
        $("#request").value =
          b.dataset.example === "old"
            ? heroBrief
            : "₹60,000 all-in for an 18K solitaire with a lab-grown diamond, size 14";
      }),
  );
  $("#new-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = $("#request").value.trim();
    const button = $("button[type=submit]", e.target);
    button.disabled = true;
    try {
      sessionStorage.removeItem("karigar-draft");
      const t = await api(
        "/api/orders",
        { text, wait_s: 0 },
        { headers: { "Idempotency-Key": crypto.randomUUID() } },
      );
      await refresh();
      location.hash = `order/${t.job_id}`;
      render();
      watchJob(t.job_id);
    } catch (err) {
      $("#form-error").textContent = err.message;
    } finally {
      button.disabled = false;
    }
  });
  $("#filters")?.addEventListener("submit", (e) => {
    e.preventDefault();
    location.hash = `orders?${new URLSearchParams(new FormData(e.target))}`;
  });
  document.querySelectorAll(".select-variant").forEach(
    (b) =>
      (b.onclick = () => {
        state.selected[b.dataset.order] = b.dataset.version;
        render();
      }),
  );
  $("#continue-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const t = await api(
        `/api/conversations/${e.target.dataset.conversation}/messages`,
        { text: $("#answer").value },
      );
      watchJob(t.job_id);
      toast("Answer sent to Sakhi.");
    } catch (err) {
      toast(err.message);
    }
  });
  $("#edit-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target,
      button = $("button", form);
    button.disabled = true;
    try {
      const order = state.data.orders.find(
        (o) => o.order_id === form.dataset.order,
      );
      const vs = versions(order);
      const ix = vs
        .slice(0, 3)
        .findIndex((r) => String(r.version) === form.dataset.version);
      if (ix < 0 && String(vs.at(-1)?.version) !== form.dataset.version) {
        throw new Error(
          "This is a historical revision. Inspect the latest revision to refine it, or choose one of the original designs.",
        );
      }
      let text = $("#edit").value;
      if (ix >= 0) text = `${["First", "Middle", "Last"][ix]} one, ${text}`;
      const t = await api(
        `/api/orders/${form.dataset.order}/edits`,
        { text },
        { headers: { "Idempotency-Key": crypto.randomUUID() } },
      );
      toast("Refining the selected design.");
      watchJob(t.job_id);
    } catch (err) {
      $("#edit-error").textContent = err.message;
    } finally {
      button.disabled = false;
    }
  });
  document.querySelectorAll("[data-action]").forEach(
    (b) =>
      (b.onclick = async () => {
        b.disabled = true;
        try {
          await action(b.dataset.action);
        } catch (err) {
          toast(err.message);
          b.disabled = false;
        }
      }),
  );
  document.querySelectorAll("[data-start-family]").forEach(
    (b) =>
      (b.onclick = () => {
        const r = getCatalogue().find(
          (r) => r.family === b.dataset.startFamily,
        );
        const text =
          r.order_prompt || `${r.spec.karat}K ${r.family} ${r.piece_type}`;
        sessionStorage.setItem("karigar-draft", text);
        viewMemory.delete("studio");
        location.hash = "studio";
      }),
  );
  $("#calibrate-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = new FormData(e.target);
    try {
      await action("calibrate", {
        workshop: form.get("workshop"),
        designed_g: Number(form.get("designed_g")),
        actual_g: Number(form.get("actual_g")),
      });
    } catch (err) {
      $("#calibrate-error").textContent = err.message;
    }
  });
  $("#cast-order")?.addEventListener(
    "change",
    (e) => ($("#designed").value = e.target.value),
  );
  $("#chat-form")?.addEventListener("submit", streamChat);
  $("[data-chat-example]")?.addEventListener(
    "click",
    () => ($("#chat-text").value = heroBrief),
  );
  $("#clear-chat")?.addEventListener("click", () => {
    state.chat = [];
    render();
  });
  $("#reload")?.addEventListener("click", () =>
    refresh(true).catch((e) => toast(e.message)),
  );
  $("#reset-view")?.addEventListener("click", () => {
    const mv = $("model-viewer");
    mv.cameraOrbit = "0deg 75deg auto";
    mv.fieldOfView = "auto";
  });
  $("#spin-view")?.addEventListener("click", (e) => {
    const mv = $("model-viewer");
    mv.autoRotate = !mv.autoRotate;
    e.target.textContent = mv.autoRotate
      ? "Pause rotation"
      : "Rotate automatically";
    e.target.setAttribute("aria-pressed", String(mv.autoRotate));
  });
  document.querySelectorAll("model-viewer").forEach((mv) =>
    mv.addEventListener("error", () => {
      const error = $("#viewer-error");
      if (error)
        error.textContent =
          "The interactive model could not load. Open the GLB download or view the rendered image.";
    }),
  );
}
async function streamChat(e) {
  e.preventDefault();
  if (state.busy) return;
  const text = $("#chat-text").value.trim();
  if (!text) return;
  state.busy = true;
  state.chat.push({ role: "user", content: text });
  const history = state.chat.map((m) => ({ ...m }));
  state.chat.push({ role: "assistant", content: "" });
  state.chatText = "";
  render();
  try {
    const response = await fetch("/api/console/chat", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${state.token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "karigar",
        messages: history,
        stream: true,
      }),
    });
    if (!response.ok)
      throw new Error(
        "The service could not open the chat. Check the connection and token.",
      );
    const reader = response.body.getReader(),
      decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop();
      for (const event of events) {
        const data = event
          .split("\n")
          .find((l) => l.startsWith("data: "))
          ?.slice(6);
        if (!data || data === "[DONE]") continue;
        const delta = JSON.parse(data).choices?.[0]?.delta?.content;
        if (delta) {
          state.chat.at(-1).content += delta;
          const messages = document.querySelectorAll("#chat-log .message");
          const last = messages[messages.length - 1];
          if (last)
            $("div", last).innerHTML = markdown(state.chat.at(-1).content);
        }
      }
    }
  } catch (err) {
    toast(err.message);
    state.chat.at(-1).content +=
      "\nThe connection ended. Send another message to retrieve the order status.";
  } finally {
    state.busy = false;
    await refresh();
    render();
  }
}
$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  state.token = $("#token").value.trim();
  const button = $("button", e.target);
  button.disabled = true;
  try {
    await refresh(true);
    sessionStorage.setItem("karigar-owner", state.token);
  } catch (err) {
    $("#login-error").textContent = err.message;
  } finally {
    button.disabled = false;
  }
});
$("#logout").onclick = signOut;
$("#menu").onclick = () => {
  const open = $(".rail").classList.toggle("open");
  $("#menu").setAttribute("aria-expanded", String(open));
};
$("#sync").onclick = () => action("shop").catch((e) => toast(e.message));
window.addEventListener("hashchange", () => {
  render();
  $(".rail").classList.remove("open");
  $("#menu").setAttribute("aria-expanded", "false");
  window.scrollTo(0, 0);
});
if (state.token) refresh(true).catch((e) => toast(e.message));
setInterval(() => {
  if (state.token && !document.hidden) refresh().catch((e) => toast(e.message));
}, 5000);
