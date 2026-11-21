import { describe, expect, it } from "vitest";
import { findings } from "@/test/fixtures";
import { groupFindings, isBreaking } from "./findings";

describe("finding groups", () => {
  it("treats only COMPATIBILITY findings of HIGH+ as breaking (analyzer definition)", () => {
    expect(isBreaking(findings[0]!)).toBe(true);
    expect(isBreaking({ ...findings[0]!, category: "SECURITY_REGRESSION" })).toBe(false);
    expect(isBreaking({ ...findings[0]!, severity: "MEDIUM" })).toBe(false);
  });

  it("separates breaking, manual-review and other findings", () => {
    const groups = groupFindings(findings);
    expect(groups.breaking.map((f) => f.id)).toEqual(["f-1"]);
    expect(groups.manual.map((f) => f.id)).toEqual(["f-2"]);
    expect(groups.other.map((f) => f.id)).toEqual(["f-3"]);
  });
});
