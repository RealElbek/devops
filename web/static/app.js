// Platform dashboard: polls every service through the gateway and redraws.
// One service being down only blanks ITS numbers and turns ITS box red.
"use strict";

const SERVICES = ["event", "booking", "payment", "ticket"];
const REFRESH_MS = 5000;
const TIMEOUT_MS = 3000;
const num = new Intl.NumberFormat("en-US");
const $ = (id) => document.getElementById(id);

async function getJson(url) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  const started = performance.now();
  try {
    const res = await fetch(url, { signal: ctrl.signal, cache: "no-store" });
    const body = await res.json().catch(() => ({}));
    return { ok: res.ok, status: res.status, body, ms: Math.round(performance.now() - started) };
  } catch {
    return { ok: false, status: 0, body: {}, ms: null };
  } finally {
    clearTimeout(timer);
  }
}

function setText(id, value) { $(id).textContent = value; }
function fmt(n) { return n == null ? "—" : num.format(n); }

// ------------------------------------------------------------------ architecture
function paintNode(id, ok, stateText, replicaText) {
  const node = $(id);
  node.classList.toggle("ok", ok);
  node.classList.toggle("down", !ok);
  node.querySelector(".state").textContent = stateText;
  const replica = node.querySelector(".replica");
  if (replica) replica.textContent = replicaText || " ";
}

function paintArchitecture(health, gatewayUp) {
  $("n-gateway").classList.toggle("ok", gatewayUp);
  $("n-gateway").classList.toggle("down", !gatewayUp);
  let down = 0;
  for (const svc of SERVICES) {
    const h = health[svc];
    const up = h.ok;
    const dbUp = up || (h.status === 503 && h.body.service);  // service answered, only its DB is down
    if (!up) down += 1;
    if (up) {
      paintNode(`n-${svc}`, true, "● healthy", `${String(h.body.served_by).slice(0, 12)} · ${h.ms} ms`);
    } else if (dbUp) {
      paintNode(`n-${svc}`, false, "● running, database down", String(h.body.served_by).slice(0, 12));
    } else {
      paintNode(`n-${svc}`, false, "● not reachable", "");
    }
    // DB state: known only if the service answered
    if (up) paintNode(`d-${svc}`, true, "PostgreSQL · ok");
    else if (dbUp) paintNode(`d-${svc}`, false, "PostgreSQL · down");
    else paintNode(`d-${svc}`, false, "unknown (service down)");
  }
  const pill = $("overall");
  pill.classList.toggle("ok", down === 0 && gatewayUp);
  pill.classList.toggle("down", down > 0 || !gatewayUp);
  setText("overall-text", !gatewayUp ? "Gateway not reachable"
    : down === 0 ? "All 4 services healthy"
    : `${down} of 4 services ${down === 1 ? "has" : "have"} a problem`);
}

// ------------------------------------------------------------------ statistics
function bars(listId, items, emptyText) {
  const list = $(listId);
  list.replaceChildren();
  const max = Math.max(0, ...items.map((i) => i.value));
  if (!items.length || max === 0) {
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = emptyText;
    list.append(li);
    return;
  }
  for (const item of items) {
    const li = document.createElement("li");
    const row = document.createElement("div");
    row.className = "row";
    const label = document.createElement("span");
    label.textContent = item.label;
    const value = document.createElement("span");
    value.textContent = fmt(item.value);
    row.append(label, value);
    const track = document.createElement("div");
    track.className = "track";
    const fill = document.createElement("div");
    fill.className = "fill";
    fill.style.width = `${(item.value / max) * 100}%`;
    track.append(fill);
    li.append(row, track);
    list.append(li);
  }
}

const STATUS_COLORS = { paid: "var(--accent)", pending: "var(--warn)", cancelled: "var(--grey)", expired: "var(--line)" };

function paintStats(s) {
  const ev = s.event.ok ? s.event.body : null;
  const bk = s.booking.ok ? s.booking.body : null;
  const pay = s.payment.ok ? s.payment.body : null;
  const tk = s.ticket.ok ? s.ticket.body : null;

  setText("k-revenue", pay ? fmt(pay.revenue) : "—");
  setText("k-revenue-sub", pay ? `UZS · ${fmt(pay.payments)} payments` : "payment-service unavailable");
  setText("k-tickets", tk ? fmt(tk.tickets) : "—");
  setText("k-tickets-sub", tk ? `${fmt(tk.issued_today)} issued today` : "ticket-service unavailable");
  setText("k-held", bk ? fmt(bk.seats_held) : "—");
  setText("k-bookings", bk ? fmt(bk.bookings) : "—");
  setText("k-bookings-sub", bk ? `${fmt(bk.seats_sold)} seats sold` : "booking-service unavailable");
  setText("k-events", ev ? fmt(ev.events) : "—");
  setText("k-events-sub", ev ? `${fmt(ev.upcoming_events)} upcoming · ${fmt(ev.seats)} seats` : "event-service unavailable");

  // bookings by status: one stacked bar + legend
  const bar = $("status-bar");
  const legend = $("status-legend");
  bar.replaceChildren();
  legend.replaceChildren();
  if (bk) {
    const total = bk.bookings || 1;
    for (const [status, count] of Object.entries(bk.by_status)) {
      const part = document.createElement("span");
      part.style.width = `${(count / total) * 100}%`;
      part.style.background = STATUS_COLORS[status];
      part.title = `${status}: ${count}`;
      bar.append(part);
      const li = document.createElement("li");
      const name = document.createElement("span");
      const swatch = document.createElement("i");
      swatch.style.background = STATUS_COLORS[status];
      name.append(swatch, status);
      const value = document.createElement("span");
      value.textContent = fmt(count);
      li.append(name, value);
      legend.append(li);
    }
  } else {
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = "booking-service unavailable";
    legend.append(li);
  }

  bars("methods", pay ? Object.entries(pay.by_method).map(([label, value]) => ({ label, value })) : [],
    pay ? "No payments yet" : "payment-service unavailable");
  bars("top-events", tk ? tk.top_events.map((e) => ({ label: e.event, value: e.tickets })) : [],
    tk ? "No tickets yet" : "ticket-service unavailable");
}

// ------------------------------------------------------------------ loop
async function refresh() {
  const [gateway, healthList, statsList] = await Promise.all([
    getJson("/nginx-health").then((r) => r.status === 200).catch(() => false),
    Promise.all(SERVICES.map((s) => getJson(`/health/${s}`))),
    Promise.all(SERVICES.map((s) => getJson(`/api/v1/stats/${s}`))),
  ]);
  const health = Object.fromEntries(SERVICES.map((s, i) => [s, healthList[i]]));
  const stats = Object.fromEntries(SERVICES.map((s, i) => [s, statsList[i]]));
  paintArchitecture(health, gateway);
  paintStats(stats);
  setText("updated", `updated ${new Date().toLocaleTimeString()}`);
}

refresh();
setInterval(refresh, REFRESH_MS);
