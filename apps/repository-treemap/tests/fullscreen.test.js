import test from "node:test";
import assert from "node:assert/strict";
import {
  fullscreenButtonLabel,
  currentFullscreenElement,
  supportsNativeFullscreen
} from "../src/js/fullscreen.js";

test("fullscreen button label reflects active state", () => {
  assert.equal(fullscreenButtonLabel(false), "Fullscreen");
  assert.equal(fullscreenButtonLabel(true), "Exit fullscreen");
});

test("fullscreen element supports standard and webkit properties", () => {
  const element = {};
  assert.equal(currentFullscreenElement({ fullscreenElement: element }), element);
  assert.equal(currentFullscreenElement({ webkitFullscreenElement: element }), element);
  assert.equal(currentFullscreenElement({}), null);
});

test("native fullscreen requires both enter and exit APIs", () => {
  assert.equal(supportsNativeFullscreen({ requestFullscreen() {} }, { exitFullscreen() {} }), true);
  assert.equal(supportsNativeFullscreen({ webkitRequestFullscreen() {} }, { webkitExitFullscreen() {} }), true);
  assert.equal(supportsNativeFullscreen({}, { exitFullscreen() {} }), false);
});
