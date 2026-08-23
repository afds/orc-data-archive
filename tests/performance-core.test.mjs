import assert from "node:assert/strict";
import test from "node:test";
import {
  apparentWind,
  conditionAtTws,
  convertWindSpeed,
  formatWindSpeed,
  polarPoint,
  publishedCondition,
  readGuideState,
  writeGuideState,
} from "../docs/assets/performance-core.mjs";

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
  assert.equal(formatWindSpeed(10, "ms"), "5.1 m/s");
  assert.equal(formatWindSpeed(10, "kt"), "10 kt");
});

test("guide URL state reads units and writes canonical knot TWS", () => {
  const initial = new URLSearchParams(
    "year=2026&country=est&ref=04340004VU1&tws=10&windUnit=ms",
  );
  assert.deepEqual(readGuideState(initial), {
    year: "2026",
    country: "EST",
    ref: "04340004VU1",
    tws: 10,
    windUnit: "ms",
  });

  const written = writeGuideState(initial, {tws: 11, windUnit: "kt"});
  assert.equal(written.get("tws"), "11");
  assert.equal(written.get("windUnit"), "kt");
  assert.equal(written.get("ref"), "04340004VU1");
});

test("polar coordinates mirror AWA left and TWA right", () => {
  assert.deepEqual(polarPoint(0, 5, "right", 10), {x: 0, y: -50});
  assert.deepEqual(polarPoint(90, 5, "right", 10), {x: 50, y: 0});
  assert.deepEqual(polarPoint(90, 5, "left", 10), {x: -50, y: 0});
  assert.deepEqual(polarPoint(180, 5, "left", 10), {x: 0, y: 50});
});
