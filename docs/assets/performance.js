import {
  conditionAtTws,
  convertWindSpeed,
  formatWindSpeed,
  matrixConditions,
  publishedCondition,
  readGuideState,
  writeGuideState,
} from "./performance-core.mjs";

const byId = (id) => document.getElementById(id);
const guide = byId("performance-guide");
const errorBox = byId("guide-error");
const errorMessage = byId("guide-error-message");
const errorLink = byId("guide-error-link");
const twsInput = byId("tws-input");
const twsUnitLabel = byId("tws-unit-label");
const windPresets = byId("wind-presets");
const controlStatus = byId("control-status");
const unitInputs = [...document.querySelectorAll('input[name="wind-unit"]')];

let record;
let state;
let lastValidCondition;

const node = (tag, text, className) => {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
};

const setFatalError = (message, year = "") => {
  errorMessage.textContent = message;
  errorLink.href = /^\d{4}$/.test(year) ? `../certificates/${year}/` : "../";
  errorLink.textContent = /^\d{4}$/.test(year)
    ? `Return to ${year} certificates`
    : "Return to the certificate archive";
  errorBox.hidden = false;
  guide.hidden = true;
};

const speed = (value) => `${value.toFixed(1)} kt`;
const angle = (value, dense = false) => `${dense ? value.toFixed(0) : value.toFixed(1)}°`;
const date = (value) => {
  if (!value) return "Issue date unavailable";
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf())
    ? `Issued ${value.slice(0, 10)}`
    : `Issued ${new Intl.DateTimeFormat(undefined, {dateStyle: "medium"}).format(parsed)}`;
};

const selectedCell = (cell, selected) => {
  if (selected) cell.dataset.selected = "true";
  return cell;
};

const renderTargetCard = (target, heading) => {
  const fragment = document.createDocumentFragment();
  fragment.append(node("p", heading, "target-label"));
  fragment.append(node("strong", speed(target.boatSpeed), "target-speed"));
  const angles = node("dl", undefined, "target-details");
  for (const [term, value] of [
    ["TWA", angle(target.twa)],
    ["AWA", angle(target.awa)],
    ["Target VMG", speed(target.vmg)],
  ]) {
    const group = node("div");
    group.append(node("dt", term), node("dd", value));
    angles.append(group);
  }
  fragment.append(angles);
  return fragment;
};

const renderOptimumRows = (targetName, bodyId) => {
  const body = byId(bodyId);
  const rows = record.allowances.wind_speeds.map((_, index) => {
    const condition = publishedCondition(record.allowances, index);
    const target = condition[targetName];
    const row = node("tr");
    const selected = condition.tws === lastValidCondition.tws;
    row.append(
      selectedCell(node("th", formatWindSpeed(condition.tws, state.windUnit)), selected),
      selectedCell(node("td", angle(target.twa)), selected),
      selectedCell(node("td", angle(target.awa)), selected),
      selectedCell(node("td", speed(target.boatSpeed)), selected),
      selectedCell(node("td", speed(target.vmg)), selected),
    );
    row.firstElementChild.scope = "row";
    return row;
  });
  body.replaceChildren(...rows);
};

const renderMatrix = () => {
  const conditions = matrixConditions(record.allowances, lastValidCondition.tws);
  const head = byId("matrix-head");
  const corner = node("th", "TWA");
  corner.scope = "col";
  const headings = conditions.map((condition) => {
    const selected = condition.tws === lastValidCondition.tws;
    const heading = selectedCell(node("th"), selected);
    heading.scope = "col";
    heading.append(node("span", formatWindSpeed(condition.tws, state.windUnit)));
    if (condition.interpolated) heading.append(node("small", "Interpolated"));
    return heading;
  });
  head.replaceChildren(corner, ...headings);

  const rows = record.allowances.wind_angles.map((twa, angleIndex) => {
    const row = node("tr");
    const heading = node("th", angle(twa));
    heading.scope = "row";
    row.append(heading);
    for (const condition of conditions) {
      const target = condition.fixed[angleIndex];
      const cell = selectedCell(
        node("td"),
        condition.tws === lastValidCondition.tws,
      );
      cell.append(
        node("strong", speed(target.boatSpeed)),
        node("small", `AWA ${angle(target.awa, true)}`),
      );
      row.append(cell);
    }
    return row;
  });
  byId("matrix-body").replaceChildren(...rows);
};

const syncUrl = () => {
  const params = writeGuideState(new URLSearchParams(window.location.search), state);
  window.history.replaceState(null, "", `${window.location.pathname}?${params}`);
};

const renderGuide = (condition) => {
  lastValidCondition = condition;
  byId("selected-tws").textContent = `${formatWindSpeed(condition.tws, state.windUnit)} targets`;
  byId("interpolated-badge").hidden = !condition.interpolated;
  byId("beat-card").replaceChildren(renderTargetCard(condition.beat, "Best upwind VMG"));
  byId("run-card").replaceChildren(renderTargetCard(condition.run, "Best downwind VMG"));
  renderOptimumRows("beat", "beat-targets");
  renderOptimumRows("run", "run-targets");
  renderMatrix();
  byId("polar-boat-name").textContent = `${record.yacht_name || "Unnamed yacht"} · ${record.sail_no || record.ref_no}`;
  controlStatus.textContent = condition.interpolated
    ? `${formatWindSpeed(condition.tws, state.windUnit)} is interpolated between published ORC values.`
    : `${formatWindSpeed(condition.tws, state.windUnit)} is a published ORC wind speed.`;
  controlStatus.classList.remove("control-error");
  guide.hidden = false;
  errorBox.hidden = true;
  syncUrl();
};

const renderPresets = () => {
  const buttons = record.allowances.wind_speeds.map((tws) => {
    const button = node("button", formatWindSpeed(tws, state.windUnit));
    button.type = "button";
    button.dataset.tws = String(tws);
    if (tws === lastValidCondition?.tws) button.setAttribute("aria-pressed", "true");
    button.addEventListener("click", () => selectTws(tws));
    return button;
  });
  windPresets.replaceChildren(...buttons);
};

const setInputFromCanonical = () => {
  const displayed = convertWindSpeed(state.tws, "kt", state.windUnit);
  twsInput.value = displayed.toFixed(state.windUnit === "ms" ? 1 : 1).replace(/\.0$/, "");
  twsInput.step = state.windUnit === "ms" ? "0.1" : "0.1";
  twsUnitLabel.textContent = state.windUnit === "ms" ? "m/s" : "kt";
};

const selectTws = (tws) => {
  try {
    const condition = conditionAtTws(record.allowances, tws);
    state.tws = tws;
    setInputFromCanonical();
    renderPresets();
    renderGuide(condition);
  } catch (error) {
    const minimum = formatWindSpeed(record.allowances.wind_speeds[0], state.windUnit);
    const maximum = formatWindSpeed(record.allowances.wind_speeds.at(-1), state.windUnit);
    controlStatus.textContent = `Enter a true wind speed between ${minimum} and ${maximum}.`;
    controlStatus.classList.add("control-error");
  }
};

const bindControls = () => {
  twsInput.addEventListener("input", () => {
    const displayed = Number(twsInput.value);
    if (!Number.isFinite(displayed) || twsInput.value.trim() === "") {
      selectTws(Number.NaN);
      return;
    }
    selectTws(convertWindSpeed(displayed, state.windUnit, "kt"));
  });
  for (const input of unitInputs) {
    input.checked = input.value === state.windUnit;
    input.addEventListener("change", () => {
      if (!input.checked) return;
      state.windUnit = input.value;
      setInputFromCanonical();
      renderPresets();
      renderGuide(lastValidCondition);
    });
  }
  byId("print-guide").addEventListener("click", () => window.print());
};

const initialize = async () => {
  state = readGuideState(new URLSearchParams(window.location.search));
  if (!/^\d{4}$/.test(state.year) || !/^[A-Z]{2,3}$/.test(state.country) || !state.ref) {
    setFatalError("The guide URL must include a valid VPP year, country, and ORC reference.", state.year);
    return;
  }
  try {
    const response = await fetch(`./${encodeURIComponent(state.year)}/${encodeURIComponent(state.country)}.json`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    record = payload.records?.find(({ref_no: refNo}) => refNo === state.ref);
    if (!record) {
      setFatalError("No archived polar data is available for this certificate.", state.year);
      return;
    }
  } catch (error) {
    setFatalError("The archived performance data could not be loaded. Please try again later.", state.year);
    return;
  }

  const minimum = record.allowances.wind_speeds[0];
  const maximum = record.allowances.wind_speeds.at(-1);
  if (state.tws === null || state.tws < minimum || state.tws > maximum) {
    state.tws = minimum <= 10 && maximum >= 10
      ? 10
      : record.allowances.wind_speeds[Math.floor(record.allowances.wind_speeds.length / 2)];
  }

  byId("yacht-name").textContent = record.yacht_name || "Unnamed yacht";
  byId("sail-number").textContent = record.sail_no || record.ref_no;
  byId("boat-summary").textContent = record.class || "Class unavailable";
  byId("vpp-year").textContent = `VPP ${record.vpp_year}`;
  byId("issue-date").textContent = date(record.issue_date);
  byId("certificate-status").textContent = record.status === "active" ? "Active certificate" : "Archived certificate";
  byId("official-certificate").href = record.certificate_url;
  bindControls();
  setInputFromCanonical();
  selectTws(state.tws);
};

initialize();
