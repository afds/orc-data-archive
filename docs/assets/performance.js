import {
  formatWindSpeed,
  polarPoint,
  polarSeries,
  publishedCondition,
  readGuideState,
  smoothSvgPath,
  writeGuideState,
} from "./performance-core.mjs";

const byId = (id) => document.getElementById(id);
const guide = byId("performance-guide");
const errorBox = byId("guide-error");
const errorMessage = byId("guide-error-message");
const errorLink = byId("guide-error-link");
const unitInputs = [...document.querySelectorAll('input[name="wind-unit"]')];

let record;
let state;

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

const speed = (value) => value.toFixed(1);
const angle = (value, dense = false) => `${dense ? value.toFixed(0) : value.toFixed(1)}°`;
const date = (value) => {
  if (!value) return "Issue date unavailable";
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf())
    ? `Issued ${value.slice(0, 10)}`
    : `Issued ${new Intl.DateTimeFormat(undefined, {dateStyle: "medium"}).format(parsed)}`;
};

const SVG_NS = "http://www.w3.org/2000/svg";
const svgNode = (tag, attributes = {}, text) => {
  const element = document.createElementNS(SVG_NS, tag);
  for (const [name, value] of Object.entries(attributes)) {
    element.setAttribute(name, String(value));
  }
  if (text !== undefined) element.textContent = text;
  return element;
};

const renderSpeedTable = () => {
  const axes = node("tr");
  const twsHeading = node("th", "TWS ↓");
  twsHeading.scope = "col";
  twsHeading.rowSpan = 2;
  const twaHeading = node("th", "TWA →");
  twaHeading.scope = "colgroup";
  twaHeading.colSpan = record.allowances.wind_angles.length;
  axes.append(twsHeading, twaHeading);

  const angles = node("tr");
  for (const twa of record.allowances.wind_angles) {
    const heading = node("th", angle(twa, true));
    heading.scope = "col";
    angles.append(heading);
  }
  byId("speed-head").replaceChildren(axes, angles);

  const rows = record.allowances.wind_speeds.map((_, index) => {
    const condition = publishedCondition(record.allowances, index);
    const row = node("tr");
    const tws = node("th", formatWindSpeed(condition.tws, state.windUnit));
    tws.scope = "row";
    row.append(tws);
    for (const target of condition.fixed) {
      const cell = node("td");
      cell.append(
        node("strong", `${speed(target.boatSpeed)} kt`),
        node("small", `AWA ${angle(target.awa, true)}`),
      );
      row.append(cell);
    }
    return row;
  });
  byId("speed-body").replaceChildren(...rows);
};

const renderVmgTable = (targetName, bodyId) => {
  const rows = record.allowances.wind_speeds.map((_, index) => {
    const condition = publishedCondition(record.allowances, index);
    const target = condition[targetName];
    const row = node("tr");
    const tws = node("th", formatWindSpeed(condition.tws, state.windUnit));
    tws.scope = "row";
    row.append(
      tws,
      node("td", angle(target.twa)),
      node("td", angle(target.awa)),
      node("td", `${speed(target.boatSpeed)} kt`),
      node("td", `${speed(target.vmg)} kt`),
    );
    return row;
  });
  byId(bodyId).replaceChildren(...rows);
};

const renderPolar = () => {
  const conditions = record.allowances.wind_speeds.map((_, index) => (
    publishedCondition(record.allowances, index)
  ));
  const maxBoatSpeed = Math.max(...conditions.flatMap((condition) => [
    condition.beat.boatSpeed,
    condition.run.boatSpeed,
    ...condition.fixed.map(({boatSpeed}) => boatSpeed),
  ]));
  const ringMaximum = Math.ceil(maxBoatSpeed);
  const radius = 245;
  const scale = radius / ringMaximum;
  const center = {x: 460, y: 285};
  const svg = svgNode("svg", {
    viewBox: "0 0 920 590",
    role: "img",
    "aria-labelledby": "polar-title polar-description",
  });
  svg.append(
    svgNode("title", {id: "polar-title"}, `${record.yacht_name} speed polar`),
    svgNode("desc", {id: "polar-description"}, "Apparent wind angle is plotted on the left, true wind angle on the right, and radial distance is target boat speed in knots."),
  );

  const grid = svgNode("g", {class: "polar-grid"});
  for (let knot = 1; knot <= ringMaximum; knot += 1) {
    grid.append(svgNode("circle", {
      cx: center.x,
      cy: center.y,
      r: knot * scale,
    }));
    grid.append(svgNode("text", {
      x: center.x + knot * scale + 3,
      y: center.y - 5,
      class: "polar-speed-label",
    }, knot === ringMaximum ? `${knot} kt` : `${knot}`));
  }
  const spokeAngles = [0, 15, 30, 45, 60, 75, 90, 120, 150, 180];
  for (const side of ["left", "right"]) {
    for (const spoke of spokeAngles) {
      if (side === "left" && [0, 180].includes(spoke)) continue;
      const point = polarPoint(spoke, ringMaximum, side, scale);
      grid.append(svgNode("line", {
        x1: center.x,
        y1: center.y,
        x2: center.x + point.x,
        y2: center.y + point.y,
      }));
      const labelPoint = polarPoint(spoke, ringMaximum + 0.55, side, scale);
      grid.append(svgNode("text", {
        x: center.x + labelPoint.x,
        y: center.y + labelPoint.y + 3,
        class: "polar-angle-label",
        "text-anchor": side === "left" ? "end" : "start",
      }, `${spoke}°`));
    }
  }
  grid.append(
    svgNode("text", {x: 90, y: 28, class: "polar-side-label"}, "AWA"),
    svgNode("text", {x: 790, y: 28, class: "polar-side-label"}, "TWA"),
  );
  svg.append(grid);

  const palette = ["#78909c", "#5e8d94", "#2f8793", "#087f8c", "#22647a", "#314f68", "#614f75", "#a55845", "#cf6f2f", "#0b3f46"];
  const dashPatterns = ["2 4", "7 4", "1 3", "none", "10 4", "7 3 2 3", "3 3", "12 3", "5 2", "none"];
  const legendItems = [];
  conditions.forEach((condition, index) => {
    const series = polarSeries(condition);
    const color = palette[index % palette.length];
    const dash = dashPatterns[index % dashPatterns.length];
    const group = svgNode("g", {
      class: "polar-series",
      "data-tws": condition.tws,
    });
    for (const [side, points] of Object.entries(series)) {
      const coordinates = points.map((target) => {
        const point = polarPoint(target.angle, target.boatSpeed, side, scale);
        return {x: center.x + point.x, y: center.y + point.y};
      });
      group.append(svgNode("path", {
        d: smoothSvgPath(coordinates),
        class: "polar-curve",
        stroke: color,
        "stroke-dasharray": dash,
      }));
      for (const endpoint of [points[0], points.at(-1)]) {
        const point = polarPoint(endpoint.angle, endpoint.boatSpeed, side, scale);
        group.append(svgNode("circle", {
          cx: center.x + point.x,
          cy: center.y + point.y,
          r: 2,
          class: "polar-endpoint",
          fill: color,
        }));
      }
    }
    svg.append(group);

    const item = node("span");
    const swatch = node("i");
    swatch.style.borderColor = color;
    swatch.style.borderTopStyle = dash === "none" ? "solid" : "dashed";
    item.append(
      swatch,
      node("b", formatWindSpeed(condition.tws, state.windUnit)),
    );
    legendItems.push(item);
  });
  byId("polar-legend").replaceChildren(...legendItems);
  byId("polar-chart").replaceChildren(svg);
};

const syncUrl = () => {
  const params = writeGuideState(new URLSearchParams(window.location.search), state);
  window.history.replaceState(null, "", `${window.location.pathname}?${params}`);
};

const renderGuide = () => {
  renderVmgTable("beat", "beat-targets");
  renderVmgTable("run", "run-targets");
  renderSpeedTable();
  renderPolar();
  byId("polar-yacht-name").textContent = record.yacht_name || "Unnamed yacht";
  byId("polar-sail-number").textContent = record.sail_no || record.ref_no;
  guide.hidden = false;
  errorBox.hidden = true;
  syncUrl();
};

const bindControls = () => {
  for (const input of unitInputs) {
    input.checked = input.value === state.windUnit;
    input.addEventListener("change", () => {
      if (!input.checked) return;
      state.windUnit = input.value;
      renderGuide();
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

  byId("yacht-name").textContent = record.yacht_name || "Unnamed yacht";
  byId("sail-number").textContent = record.sail_no || record.ref_no;
  byId("certificate-ref").textContent = `RefNo ${record.ref_no}`;
  byId("polar-certificate-ref").textContent = `RefNo ${record.ref_no}`;
  byId("issue-date").textContent = date(record.issue_date);
  byId("polar-issue-date").textContent = date(record.issue_date);
  bindControls();
  renderGuide();
};

initialize();
