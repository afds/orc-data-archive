const KNOT_TO_METRES_PER_SECOND = 0.514444;

const radians = (degrees) => degrees * Math.PI / 180;
const finite = (value, name) => {
  if (!Number.isFinite(value)) throw new TypeError(`${name} must be finite`);
  return value;
};
const cleanZero = (value) => Math.abs(value) < 1e-12 ? 0 : value;
const lerp = (left, right, ratio) => left + (right - left) * ratio;

export const allowanceToSpeed = (allowance) => {
  finite(allowance, "allowance");
  if (allowance <= 0) throw new RangeError("allowance must be positive");
  return 3600 / allowance;
};

export const apparentWind = (tws, twa, boatSpeed) => {
  finite(tws, "TWS");
  finite(twa, "TWA");
  finite(boatSpeed, "boat speed");
  const angle = radians(twa);
  const x = tws * Math.cos(angle) + boatSpeed;
  const y = tws * Math.sin(angle);
  let awa = Math.atan2(y, x) * 180 / Math.PI;
  if (awa < 0) awa += 360;
  if (awa > 180) awa = 360 - awa;
  return {awa, aws: Math.hypot(x, y)};
};

const optimum = (tws, allowance, twa, direction) => {
  const vmg = allowanceToSpeed(allowance);
  const component = Math.cos(radians(twa));
  const divisor = direction === "beat" ? component : Math.abs(component);
  if (divisor <= 0) throw new RangeError(`${direction} angle cannot produce VMG`);
  const boatSpeed = vmg / divisor;
  const {awa, aws} = apparentWind(tws, twa, boatSpeed);
  return {twa, awa, aws, boatSpeed, vmg};
};

const fixedTarget = (tws, twa, boatSpeed) => {
  const {awa, aws} = apparentWind(tws, twa, boatSpeed);
  return {
    twa,
    awa,
    aws,
    boatSpeed,
    vmg: Math.abs(boatSpeed * Math.cos(radians(twa))),
  };
};

export const publishedCondition = (allowances, index) => {
  if (!Number.isInteger(index) || index < 0 || index >= allowances.wind_speeds.length) {
    throw new RangeError("published wind-speed index is out of range");
  }
  const tws = allowances.wind_speeds[index];
  const fixed = allowances.wind_angles.map((twa) => fixedTarget(
    tws,
    twa,
    allowanceToSpeed(allowances.fixed[String(twa)][index]),
  ));
  return {
    tws,
    interpolated: false,
    beat: optimum(tws, allowances.beat[index], allowances.beat_angle[index], "beat"),
    run: optimum(tws, allowances.run[index], allowances.gybe_angle[index], "run"),
    fixed,
  };
};

export const conditionAtTws = (allowances, tws) => {
  finite(tws, "TWS");
  const speeds = allowances.wind_speeds;
  if (tws < speeds[0] || tws > speeds.at(-1)) {
    throw new RangeError(`TWS must be between ${speeds[0]} and ${speeds.at(-1)} kt`);
  }
  const exact = speeds.indexOf(tws);
  if (exact !== -1) return publishedCondition(allowances, exact);

  const upper = speeds.findIndex((speed) => speed > tws);
  const lower = upper - 1;
  const ratio = (tws - speeds[lower]) / (speeds[upper] - speeds[lower]);
  const beatVmg = lerp(
    allowanceToSpeed(allowances.beat[lower]),
    allowanceToSpeed(allowances.beat[upper]),
    ratio,
  );
  const runVmg = lerp(
    allowanceToSpeed(allowances.run[lower]),
    allowanceToSpeed(allowances.run[upper]),
    ratio,
  );
  const beatTwa = lerp(allowances.beat_angle[lower], allowances.beat_angle[upper], ratio);
  const runTwa = lerp(allowances.gybe_angle[lower], allowances.gybe_angle[upper], ratio);
  const beatAllowance = 3600 / beatVmg;
  const runAllowance = 3600 / runVmg;
  const fixed = allowances.wind_angles.map((twa) => {
    const values = allowances.fixed[String(twa)];
    const boatSpeed = lerp(
      allowanceToSpeed(values[lower]),
      allowanceToSpeed(values[upper]),
      ratio,
    );
    return fixedTarget(tws, twa, boatSpeed);
  });
  return {
    tws,
    interpolated: true,
    beat: optimum(tws, beatAllowance, beatTwa, "beat"),
    run: optimum(tws, runAllowance, runTwa, "run"),
    fixed,
  };
};

export const matrixConditions = (allowances, selectedTws) => {
  const published = allowances.wind_speeds.map((_, index) => (
    publishedCondition(allowances, index)
  ));
  if (!Number.isFinite(selectedTws)) return published;
  if (allowances.wind_speeds.includes(selectedTws)) return published;
  const selected = conditionAtTws(allowances, selectedTws);
  return [...published, selected].sort((left, right) => left.tws - right.tws);
};

export const convertWindSpeed = (value, fromUnit, toUnit) => {
  finite(value, "wind speed");
  if (!["kt", "ms"].includes(fromUnit) || !["kt", "ms"].includes(toUnit)) {
    throw new RangeError("wind unit must be kt or ms");
  }
  if (fromUnit === toUnit) return value;
  return fromUnit === "kt"
    ? value * KNOT_TO_METRES_PER_SECOND
    : value / KNOT_TO_METRES_PER_SECOND;
};

export const windSpeedForDisplay = (twsKnots, unit) => {
  const value = convertWindSpeed(twsKnots, "kt", unit);
  return unit === "ms" ? Math.round(value * 2) / 2 : value;
};

export const formatWindSpeed = (twsKnots, unit) => {
  const value = windSpeedForDisplay(twsKnots, unit);
  if (unit === "ms") {
    return `${Number.isInteger(value) ? value : value.toFixed(1)} m/s`;
  }
  return `${Number.isInteger(value) ? value : value.toFixed(1)} kt`;
};

export const formatFixedTargetDetails = ({awa, vmg}) => {
  finite(awa, "AWA");
  finite(vmg, "VMG");
  return `AWA ${awa.toFixed(0)}° · VMG ${Math.abs(vmg).toFixed(1)} kt`;
};

export const readGuideState = (params) => {
  return {
    year: params.get("year") ?? "",
    country: (params.get("country") ?? "").toUpperCase(),
    ref: params.get("ref") ?? "",
    tws: null,
    windUnit: params.get("windUnit") === "ms" ? "ms" : "kt",
  };
};

export const writeGuideState = (params, state) => {
  const updated = new URLSearchParams(params);
  updated.delete("tws");
  updated.delete("angleMode");
  if (["kt", "ms"].includes(state.windUnit)) {
    updated.set("windUnit", state.windUnit);
  }
  return updated;
};

export const polarPoint = (angleDegrees, boatSpeed, side, scale) => {
  finite(angleDegrees, "polar angle");
  finite(boatSpeed, "boat speed");
  finite(scale, "polar scale");
  if (!["left", "right"].includes(side)) throw new RangeError("polar side is invalid");
  const angle = radians(angleDegrees);
  const direction = side === "left" ? -1 : 1;
  return {
    x: cleanZero(direction * Math.sin(angle) * boatSpeed * scale),
    y: cleanZero(-Math.cos(angle) * boatSpeed * scale),
  };
};

export const oppositePolarSelection = (side, segmentIndex, ratio) => ({
  side: side === "left" ? "right" : "left",
  segmentIndex,
  ratio,
});

export const interpolatePolarTarget = (start, end, ratio) => {
  return {
    twa: lerp(start.twa, end.twa, ratio),
    awa: lerp(start.awa, end.awa, ratio),
    boatSpeed: lerp(start.boatSpeed, end.boatSpeed, ratio),
    vmg: lerp(start.vmg, end.vmg, ratio),
  };
};

const smoothSvgCommands = (points, tension) => {
  if (!Array.isArray(points) || points.length < 2) {
    throw new RangeError("a polar curve needs at least two points");
  }
  const coordinate = ({x, y}) => `${x.toFixed(2)} ${y.toFixed(2)}`;
  return points.slice(0, -1).map((point, index) => {
    const previous = points[index - 1] ?? point;
    const next = points[index + 1];
    const following = points[index + 2] ?? next;
    const firstControl = {
      x: point.x + (next.x - previous.x) * tension,
      y: point.y + (next.y - previous.y) * tension,
    };
    const secondControl = {
      x: next.x - (following.x - point.x) * tension,
      y: next.y - (following.y - point.y) * tension,
    };
    return {
      start: coordinate(point),
      curve: `C ${coordinate(firstControl)}, ${coordinate(secondControl)}, ${coordinate(next)}`,
    };
  });
};

export const smoothSvgSegments = (points, tension = 1 / 6) => (
  smoothSvgCommands(points, tension).map(({start, curve}) => `M ${start} ${curve}`)
);

export const smoothSvgPath = (points, tension = 1 / 6) => {
  const commands = smoothSvgCommands(points, tension);
  return `M ${commands[0].start} ${commands.map(({curve}) => curve).join(" ")}`;
};

export const polarSeries = (condition) => {
  const targets = [
    {...condition.beat, kind: "beat"},
    ...condition.fixed.map((target) => ({...target, kind: "fixed"})),
    {...condition.run, kind: "run"},
  ].sort((left, right) => left.twa - right.twa);
  return {
    left: targets.map((target) => ({
      angle: target.awa,
      twa: target.twa,
      awa: target.awa,
      boatSpeed: target.boatSpeed,
      vmg: target.vmg,
      kind: target.kind,
    })),
    right: targets.map((target) => ({
      angle: target.twa,
      twa: target.twa,
      awa: target.awa,
      boatSpeed: target.boatSpeed,
      vmg: target.vmg,
      kind: target.kind,
    })),
  };
};

export const polarVmgTargets = (series) => Object.fromEntries(
  Object.entries(series).map(([side, targets]) => [
    side,
    targets.filter(({kind}) => kind === "beat" || kind === "run"),
  ]),
);

export const polarHoverSeries = (activeSeries, candidateSeries, activeHovered) => (
  activeSeries && activeHovered ? activeSeries : candidateSeries
);

export const polarVmgSymbol = (kind) => {
  if (kind === "beat") return "×";
  if (kind === "run") return "◇";
  throw new RangeError(`Unsupported VMG marker kind: ${kind}`);
};

export const polarVmgMarkerPath = (kind, x, y, size) => {
  if (kind === "beat") {
    return [
      `M ${x - size} ${y - size} L ${x + size} ${y + size}`,
      `M ${x + size} ${y - size} L ${x - size} ${y + size}`,
    ].join(" ");
  }
  if (kind === "run") {
    return [
      `M ${x} ${y - size}`,
      `L ${x + size} ${y}`,
      `L ${x} ${y + size}`,
      `L ${x - size} ${y}`,
      "Z",
    ].join(" ");
  }
  throw new RangeError(`Unsupported VMG marker kind: ${kind}`);
};
