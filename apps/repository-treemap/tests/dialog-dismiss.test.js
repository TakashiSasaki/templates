import test from "node:test";
import assert from "node:assert/strict";
import { isPointOutsideRect } from "../src/js/dialog-dismiss.js";

const rect = { left: 100, right: 300, top: 400, bottom: 700 };

test("points inside the dialog rectangle do not dismiss it", () => {
  assert.equal(isPointOutsideRect(200, 550, rect), false);
  assert.equal(isPointOutsideRect(100, 400, rect), false);
  assert.equal(isPointOutsideRect(300, 700, rect), false);
});

test("points on the backdrop outside the dialog rectangle dismiss it", () => {
  assert.equal(isPointOutsideRect(99, 550, rect), true);
  assert.equal(isPointOutsideRect(301, 550, rect), true);
  assert.equal(isPointOutsideRect(200, 399, rect), true);
  assert.equal(isPointOutsideRect(200, 701, rect), true);
});
