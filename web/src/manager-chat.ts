export const managerChatSuggestions = [
  "Summarize today's inspection history.",
  "Explain the latest Agent decision.",
  "Which batches still need human review?",
] as const;

export function canSendManagerMessage(value: string, busy: boolean) {
  return !busy && value.trim().length > 0 && value.trim().length <= 4000;
}

export function managerChatProvenance(metadata: Record<string, unknown>) {
  return metadata.source === "openai_rag"
    ? "OpenAI + grounded FreshSense context"
    : "Grounded local fallback";
}
