import test from "node:test";
import assert from "node:assert/strict";
import {
  LONG_PRESS_DELAY_MS, LONG_PRESS_MOVE_TOLERANCE_PX,
  exceedsMoveTolerance, isLongPressPointerType
} from "../src/js/touch-long-press.js";

test("mobile long press uses a 500 ms hold", () => {
  assert.equal(LONG_PRESS_DELAY_MS, 500);
});
test("touch movement tolerance is 12 px", () => {
  assert.equal(LONG_PRESS_MOVE_TOLERANCE_PX, 12);
  assert.equal(exceedsMoveTolerance(0, 0, 6, 8), false);
  assert.equal(exceedsMoveTolerance(0, 0, 13, 0), true);
});
test("long press is restricted to touch and pen pointers", () => {
  assert.equal(isLongPressPointerType("touch"), true);
  assert.equal(isLongPressPointerType("pen"), true);
  assert.equal(isLongPressPointerType("mouse"), false);
});
