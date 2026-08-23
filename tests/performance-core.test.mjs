import assert from "node:assert/strict";
import test from "node:test";
import * as performanceCore from "../docs/assets/performance-core.mjs";

const {
  apparentWind,
  conditionAtTws,
  convertWindSpeed,
  formatWindSpeed,
  windSpeedForDisplay,
  polarPoint,
  publishedCondition,
  readGuideState,
  smoothSvgPath,
  writeGuideState,
} = performanceCore;
const matrixConditions = performanceCore.matrixConditions ?? (() => []);
const interpolatePolarTarget = performanceCore.interpolatePolarTarget ?? (() => ({}));
const polarSeries = performanceCore.polarSeries ?? (() => ({left: [], right: []}));
const smoothSvgSegments = performanceCore.smoothSvgSegments ?? (() => []);

const adeleAllowances = {
  wind_speeds: [8, 10],
  wind_angles: [52, 60],
  beat: [895.5, 793.2],
  beat_angle: [41.6, 40.0],
  run: [797.6, 672.0],
  gybe_angle: [149.8, 152.5],
  fixed: {
    "52": [601.0, 548.3],
    "60": [576.7, 532.9],
  },
};

test("ADELE 10 kt beat and run targets preserve VMG geometry", () => {
  const condition = publishedCondition(adeleAllowances, 1);

  assert.equal(condition.beat.vmg.toFixed(2), "4.54");
  assert.equal(condition.beat.boatSpeed.toFixed(2), "5.92");
  assert.equal(condition.beat.awa.toFixed(1), "25.3");
  assert.equal(condition.run.vmg.toFixed(2), "5.36");
  assert.equal(condition.run.boatSpeed.toFixed(2), "6.04");
  assert.equal(condition.run.awa.toFixed(1), "121.5");
});

test("ADELE fixed 10 kt target converts allowance to speed and AWA", () => {
  const condition = publishedCondition(adeleAllowances, 1);

  assert.equal(condition.fixed[0].twa, 52);
  assert.equal(condition.fixed[0].boatSpeed.toFixed(2), "6.57");
  assert.equal(condition.fixed[0].awa.toFixed(1), "31.8");
});

test("interpolation is linear in fixed speed, VMG, and optimum angle", () => {
  const condition = conditionAtTws(adeleAllowances, 9);

  assert.equal(condition.tws, 9);
  assert.equal(condition.interpolated, true);
  assert.equal(condition.fixed[0].boatSpeed.toFixed(3), "6.278");
  assert.equal(condition.beat.vmg.toFixed(3), "4.279");
  assert.equal(condition.beat.twa.toFixed(1), "40.8");
});

test("exact published lookup is not marked interpolated", () => {
  const condition = conditionAtTws(adeleAllowances, 8);

  assert.equal(condition.tws, 8);
  assert.equal(condition.interpolated, false);
  assert.equal(condition.fixed[0].boatSpeed.toFixed(3), "5.990");
});

test("selection never extrapolates outside the published range", () => {
  assert.throws(() => conditionAtTws(adeleAllowances, 7.9), RangeError);
  assert.throws(() => conditionAtTws(adeleAllowances, 10.1), RangeError);
  assert.throws(() => conditionAtTws(adeleAllowances, Number.NaN), TypeError);
});

test("apparent wind uses the ORC vector relation", () => {
  const result = apparentWind(10, 40, 5.9246);

  assert.equal(result.awa.toFixed(1), "25.3");
  assert.equal(result.aws.toFixed(1), "15.0");
});

test("only TWS converts between knots and metres per second", () => {
  assert.equal(convertWindSpeed(10, "kt", "ms").toFixed(6), "5.144440");
  assert.equal(convertWindSpeed(5.14444, "ms", "kt").toFixed(3), "10.000");
  assert.equal(windSpeedForDisplay(10, "ms"), 5);
  assert.equal(formatWindSpeed(2.1 / 0.514444, "ms"), "2 m/s");
  assert.equal(formatWindSpeed(2.3 / 0.514444, "ms"), "2.5 m/s");
  assert.equal(formatWindSpeed(2.4 / 0.514444, "ms"), "2.5 m/s");
  assert.equal(formatWindSpeed(2.5 / 0.514444, "ms"), "2.5 m/s");
  assert.equal(formatWindSpeed(10, "kt"), "10 kt");
});

test("guide URL state ignores legacy TWS selection and preserves units", () => {
  const initial = new URLSearchParams(
    "year=2026&country=est&ref=04340004VU1&tws=10&windUnit=ms&angleMode=awa",
  );
  assert.deepEqual(readGuideState(initial), {
    year: "2026",
    country: "EST",
    ref: "04340004VU1",
    tws: null,
    windUnit: "ms",
  });

  const written = writeGuideState(initial, {windUnit: "kt"});
  assert.equal(written.has("tws"), false);
  assert.equal(written.get("windUnit"), "kt");
  assert.equal(written.has("angleMode"), false);
  assert.equal(written.get("ref"), "04340004VU1");
});

test("guide URL state removes TWS when the optional selection is cleared", () => {
  const initial = new URLSearchParams(
    "year=2026&country=EST&ref=04340004VU1&tws=10&windUnit=kt",
  );

  const written = writeGuideState(initial, {
    tws: null,
    windUnit: "kt",
  });

  assert.equal(written.has("tws"), false);
  assert.equal(written.get("ref"), "04340004VU1");
});

test("polar coordinates mirror AWA left and TWA right", () => {
  assert.deepEqual(polarPoint(0, 5, "right", 10), {x: 0, y: -50});
  assert.deepEqual(polarPoint(90, 5, "right", 10), {x: 50, y: 0});
  assert.deepEqual(polarPoint(90, 5, "left", 10), {x: -50, y: 0});
  assert.deepEqual(polarPoint(180, 5, "left", 10), {x: 0, y: 50});
});

test("polar tooltip values interpolate continuously between adjacent targets", () => {
  assert.deepEqual(
    interpolatePolarTarget(
      {twa: 40, awa: 25, boatSpeed: 6, vmg: 4.5},
      {twa: 60, awa: 37, boatSpeed: 7, vmg: 3.5},
      0.25,
    ),
    {twa: 45, awa: 28, boatSpeed: 6.25, vmg: 4.25},
  );
});

test("polar curves use a restrained smooth path through every target", () => {
  assert.equal(
    smoothSvgPath([{x: 0, y: 0}, {x: 10, y: 10}, {x: 20, y: 0}]),
    "M 0.00 0.00 C 1.67 1.67, 6.67 10.00, 10.00 10.00 C 13.33 10.00, 18.33 1.67, 20.00 0.00",
  );
});

test("polar curve segments preserve the same smooth geometry for hit testing", () => {
  assert.deepEqual(
    smoothSvgSegments([{x: 0, y: 0}, {x: 10, y: 10}, {x: 20, y: 0}]),
    [
      "M 0.00 0.00 C 1.67 1.67, 6.67 10.00, 10.00 10.00",
      "M 10.00 10.00 C 13.33 10.00, 18.33 1.67, 20.00 0.00",
    ],
  );
});

test("matrix inserts one selected interpolated column in wind-speed order", () => {
  const columns = matrixConditions(adeleAllowances, 9);

  assert.deepEqual(columns.map(({tws}) => tws), [8, 9, 10]);
  assert.deepEqual(columns.map(({interpolated}) => interpolated), [false, true, false]);
});

test("matrix does not duplicate an exact published selection", () => {
  const columns = matrixConditions(adeleAllowances, 10);

  assert.deepEqual(columns.map(({tws}) => tws), [8, 10]);
});

test("matrix renders published columns when no TWS is selected", () => {
  const columns = matrixConditions(adeleAllowances, null);

  assert.deepEqual(columns.map(({tws}) => tws), [8, 10]);
});

test("polar series orders beat, fixed angles, and run on both angle systems", () => {
  const condition = publishedCondition(adeleAllowances, 1);
  const series = polarSeries(condition);

  assert.deepEqual(
    series.right.map(({angle: value}) => value),
    [40, 52, 60, 152.5],
  );
  assert.deepEqual(
    series.left.map(({angle: value}) => Number(value.toFixed(1))),
    [25.3, 31.8, 36.4, 121.5],
  );
  assert.deepEqual(
    series.right.map(({kind}) => kind),
    ["beat", "fixed", "fixed", "run"],
  );
  assert.deepEqual(
    Object.keys(series.right[0]).sort(),
    ["angle", "awa", "boatSpeed", "kind", "twa", "vmg"],
  );
});
