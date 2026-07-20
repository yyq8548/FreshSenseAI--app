import { describe, expect, it } from "vitest";

import {
  canSendManagerMessage,
  managerChatProvenance,
  managerChatSuggestions,
} from "./manager-chat";

describe("manager chat presentation rules", () => {
  it("rejects empty, busy, and oversized messages", () => {
    expect(canSendManagerMessage("  ", false)).toBe(false);
    expect(canSendManagerMessage("Explain batch PO-42", true)).toBe(false);
    expect(canSendManagerMessage("x".repeat(4001), false)).toBe(false);
    expect(canSendManagerMessage("Explain batch PO-42", false)).toBe(true);
  });

  it("labels model and fallback answers honestly", () => {
    expect(managerChatProvenance({ source: "openai_rag" })).toContain("OpenAI");
    expect(managerChatProvenance({ source: "grounded_fallback" })).toContain("fallback");
  });

  it("offers concrete manager questions", () => {
    expect(managerChatSuggestions).toHaveLength(3);
    expect(managerChatSuggestions.join(" ")).toContain("Agent decision");
  });
});
