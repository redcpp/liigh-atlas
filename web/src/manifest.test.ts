import { describe, expect, it } from "vitest";
import { dequantize, isManifest } from "./manifest";

describe("manifest", () => {
  it("dequantizes with offset and scale", () => {
    expect(dequantize(65535, 10, 0.5)).toBe(10 + 65535 * 0.5);
  });
  it("recognizes schema v1 manifests", () => {
    expect(isManifest({ schema_version: 1, dataset: { name: "fixture" }, files: {} })).toBe(true);
    expect(isManifest({ schema_version: 2 })).toBe(false);
  });
});
