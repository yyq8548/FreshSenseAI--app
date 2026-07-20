import { describe, expect, it } from "vitest";

import { analysisProgressMessage } from "./analysis-progress";

describe("analysisProgressMessage", () => {
  it("describes upload validation at the start", () => {
    expect(analysisProgressMessage(0)).toContain("Uploading");
    expect(analysisProgressMessage(4)).toContain("fast visual scan");
  });

  it("sets a realistic expectation during normal inference", () => {
    expect(analysisProgressMessage(5)).toContain("still processing");
    expect(analysisProgressMessage(14)).toContain("recently started server");
  });

  it("explains cold-start delays without encouraging duplicate submissions", () => {
    expect(analysisProgressMessage(20)).toContain("idle period");
    expect(analysisProgressMessage(90)).toContain("do not submit");
  });
});
