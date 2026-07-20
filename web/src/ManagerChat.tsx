import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  Badge,
  Body1,
  Button,
  Caption1,
  Card,
  Field,
  MessageBar,
  MessageBarBody,
  Select,
  Spinner,
  Text,
  Textarea,
  Title1,
  Title2,
  makeStyles,
  tokens,
} from "@fluentui/react-components";
import {
  Add24Regular,
  Archive24Regular,
  Bot24Regular,
  Send24Regular,
  Settings24Regular,
} from "@fluentui/react-icons";

import { FreshSenseApi } from "./api";
import {
  canSendManagerMessage,
  managerChatProvenance,
  managerChatSuggestions,
} from "./manager-chat";
import type {
  ManagerConversation,
  ManagerConversationSummary,
  ManagerPreference,
  Workspace,
} from "./types";

const useStyles = makeStyles({
  heading: { display: "flex", flexDirection: "column", gap: "7px", marginBottom: "24px" },
  layout: {
    display: "grid",
    gridTemplateColumns: "270px minmax(0, 1fr)",
    gap: "16px",
    minHeight: "650px",
    "@media (max-width: 900px)": { gridTemplateColumns: "1fr" },
  },
  card: { padding: "16px", borderRadius: tokens.borderRadiusLarge },
  conversationRail: { display: "flex", flexDirection: "column", gap: "12px" },
  conversationList: {
    display: "flex",
    flexDirection: "column",
    gap: "6px",
    maxHeight: "570px",
    overflowY: "auto",
  },
  conversationButton: {
    justifyContent: "flex-start",
    textAlign: "left",
    minHeight: "54px",
    height: "auto",
    paddingTop: "8px",
    paddingBottom: "8px",
  },
  chatCard: {
    padding: 0,
    borderRadius: tokens.borderRadiusLarge,
    overflow: "hidden",
    display: "grid",
    gridTemplateRows: "auto minmax(360px, 1fr) auto",
  },
  chatHeader: {
    padding: "16px 18px",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "12px",
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  messages: {
    padding: "20px",
    display: "flex",
    flexDirection: "column",
    gap: "16px",
    overflowY: "auto",
    maxHeight: "590px",
    backgroundColor: tokens.colorNeutralBackground2,
  },
  message: { display: "flex", flexDirection: "column", gap: "7px", maxWidth: "82%" },
  managerMessage: { alignSelf: "flex-end", alignItems: "flex-end" },
  assistantMessage: { alignSelf: "flex-start", alignItems: "flex-start" },
  bubble: {
    padding: "12px 14px",
    borderRadius: tokens.borderRadiusLarge,
    whiteSpace: "pre-wrap",
    lineHeight: "1.55",
  },
  managerBubble: {
    color: tokens.colorNeutralForegroundOnBrand,
    backgroundColor: tokens.colorBrandBackground,
  },
  assistantBubble: {
    color: tokens.colorNeutralForeground1,
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  citations: { display: "flex", gap: "6px", flexWrap: "wrap" },
  composer: {
    padding: "16px 18px",
    display: "flex",
    flexDirection: "column",
    gap: "10px",
    borderTop: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: tokens.colorNeutralBackground1,
  },
  composerRow: { display: "flex", alignItems: "flex-end", gap: "10px" },
  composerInput: { flex: 1 },
  row: { display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" },
  spread: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px" },
  stack: { display: "flex", flexDirection: "column", gap: "12px" },
  empty: { minHeight: "360px", display: "grid", placeItems: "center", padding: "24px", textAlign: "center" },
  preferences: {
    marginTop: "16px",
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    gap: "12px",
    "@media (max-width: 700px)": { gridTemplateColumns: "1fr" },
  },
  fullWidth: { gridColumn: "1 / -1" },
});

export function ManagerChat({ api, workspace }: { api: FreshSenseApi; workspace: Workspace }) {
  const styles = useStyles();
  const endRef = useRef<HTMLDivElement>(null);
  const [conversations, setConversations] = useState<ManagerConversationSummary[]>([]);
  const [conversation, setConversation] = useState<ManagerConversation | null>(null);
  const [preferences, setPreferences] = useState<ManagerPreference | null>(null);
  const [draftPreferences, setDraftPreferences] = useState<ManagerPreference | null>(null);
  const [showPreferences, setShowPreferences] = useState(false);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshConversationList = async (selectedId?: string) => {
    const result = await api.managerConversations();
    setConversations(result.conversations);
    const currentId = result.conversations.some(
      (item) => item.conversation_id === conversation?.conversation_id,
    ) ? conversation?.conversation_id : undefined;
    const id = selectedId || currentId || result.conversations[0]?.conversation_id;
    if (id) setConversation(await api.managerConversation(id));
    else setConversation(null);
  };

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const [preferenceResult, conversationResult] = await Promise.all([
          api.managerPreferences(),
          api.managerConversations(),
        ]);
        if (!active) return;
        setPreferences(preferenceResult);
        setDraftPreferences(preferenceResult);
        setConversations(conversationResult.conversations);
        if (conversationResult.conversations[0]) {
          const selected = await api.managerConversation(
            conversationResult.conversations[0].conversation_id,
          );
          if (active) setConversation(selected);
        }
      } catch (reason) {
        if (active) setError(messageFrom(reason));
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    return () => { active = false; };
  }, [api]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversation?.messages.length, busy]);

  const selectConversation = async (conversationId: string) => {
    setError(null);
    try { setConversation(await api.managerConversation(conversationId)); }
    catch (reason) { setError(messageFrom(reason)); }
  };

  const createConversation = async () => {
    setBusy(true); setError(null);
    try {
      const created = await api.createManagerConversation();
      setConversation(created);
      await refreshConversationList(created.conversation_id);
    } catch (reason) { setError(messageFrom(reason)); }
    finally { setBusy(false); }
  };

  const send = async (event?: FormEvent) => {
    event?.preventDefault();
    const content = message.trim();
    if (!canSendManagerMessage(message, busy)) return;
    setBusy(true); setError(null); setMessage("");
    try {
      let activeConversation = conversation;
      if (!activeConversation) activeConversation = await api.createManagerConversation();
      const result = await api.sendManagerMessage(activeConversation.conversation_id, content);
      setConversation(result.conversation);
      await refreshConversationList(activeConversation.conversation_id);
    } catch (reason) {
      setMessage(content);
      setError(messageFrom(reason));
    } finally { setBusy(false); }
  };

  const savePreferences = async (event: FormEvent) => {
    event.preventDefault();
    if (!draftPreferences) return;
    setBusy(true); setError(null);
    try {
      const saved = await api.updateManagerPreferences({
        preferred_language: draftPreferences.preferred_language,
        response_detail: draftPreferences.response_detail,
        default_location_name: draftPreferences.default_location_name,
        review_focus: draftPreferences.review_focus,
        custom_instructions: draftPreferences.custom_instructions,
      });
      setPreferences(saved); setDraftPreferences(saved); setShowPreferences(false);
    } catch (reason) { setError(messageFrom(reason)); }
    finally { setBusy(false); }
  };

  const archive = async () => {
    if (!conversation) return;
    setBusy(true); setError(null);
    try {
      await api.archiveManagerConversation(conversation.conversation_id);
      setConversation(null);
      await refreshConversationList();
    } catch (reason) { setError(messageFrom(reason)); }
    finally { setBusy(false); }
  };

  if (loading) return <Spinner label="Loading Manager Chat..." />;

  return (
    <section>
      <div className={styles.heading}>
        <Title1>Manager Chat</Title1>
        <Body1>Ask about batch history, Agent decisions, review work, and store operations. Answers stay grounded in this workspace.</Body1>
      </div>
      {error ? <MessageBar intent="error"><MessageBarBody>{error}</MessageBarBody></MessageBar> : null}
      <div className={styles.spread}>
        <div className={styles.row}>
          <Badge appearance="tint" color="success">Workspace memory on</Badge>
          <Badge appearance="tint">Human approval required for high-risk actions</Badge>
        </div>
        <Button icon={<Settings24Regular />} onClick={() => setShowPreferences((value) => !value)}>
          Preferences
        </Button>
      </div>

      {showPreferences && draftPreferences ? (
        <Card className={styles.card}>
          <form className={styles.preferences} onSubmit={savePreferences}>
            <Field label="Assistant language">
              <Select value={draftPreferences.preferred_language} onChange={(_, data) => setDraftPreferences({ ...draftPreferences, preferred_language: data.value as ManagerPreference["preferred_language"] })}>
                <option value="auto">Match my message</option><option value="en">English</option><option value="zh">中文</option>
              </Select>
            </Field>
            <Field label="Response detail">
              <Select value={draftPreferences.response_detail} onChange={(_, data) => setDraftPreferences({ ...draftPreferences, response_detail: data.value as ManagerPreference["response_detail"] })}>
                <option value="concise">Concise</option><option value="standard">Standard</option><option value="detailed">Detailed</option>
              </Select>
            </Field>
            <Field label="Default store location">
              <Select value={draftPreferences.default_location_name} onChange={(_, data) => setDraftPreferences({ ...draftPreferences, default_location_name: data.value })}>
                <option value="">No default</option>{workspace.locations.map((location) => <option key={location.location_id} value={location.name}>{location.name}</option>)}
              </Select>
            </Field>
            <Field label="Review focus">
              <Select value={draftPreferences.review_focus} onChange={(_, data) => setDraftPreferences({ ...draftPreferences, review_focus: data.value as ManagerPreference["review_focus"] })}>
                <option value="balanced">Balanced</option><option value="freshness_risk">Freshness risk</option><option value="operations">Store operations</option>
              </Select>
            </Field>
            <Field className={styles.fullWidth} label="Manager instructions" hint="For example: lead with open tasks and include confidence when available.">
              <Textarea value={draftPreferences.custom_instructions} maxLength={600} onChange={(_, data) => setDraftPreferences({ ...draftPreferences, custom_instructions: data.value })} />
            </Field>
            <div className={`${styles.row} ${styles.fullWidth}`}><Button type="submit" appearance="primary" disabled={busy}>Save preferences</Button><Caption1>Last saved {preferences ? new Date(preferences.updated_at_utc).toLocaleString() : "never"}</Caption1></div>
          </form>
        </Card>
      ) : null}

      <div className={styles.layout}>
        <Card className={`${styles.card} ${styles.conversationRail}`}>
          <Button appearance="primary" icon={<Add24Regular />} onClick={() => void createConversation()} disabled={busy}>New conversation</Button>
          <div className={styles.conversationList}>
            {conversations.length === 0 ? <Caption1>No saved conversations yet.</Caption1> : conversations.map((item) => (
              <Button key={item.conversation_id} className={styles.conversationButton} appearance={conversation?.conversation_id === item.conversation_id ? "primary" : "subtle"} onClick={() => void selectConversation(item.conversation_id)}>
                <span><Text weight="semibold">{item.title}</Text><br /><Caption1>{item.message_count} messages · {new Date(item.updated_at_utc).toLocaleDateString()}</Caption1></span>
              </Button>
            ))}
          </div>
        </Card>

        <Card className={styles.chatCard}>
          <div className={styles.chatHeader}>
            <div><Title2>{conversation?.title || "Ask FreshSense"}</Title2><br /><Caption1>Workspace inspections, Agent traces, reviewed knowledge</Caption1></div>
            {conversation ? <Button appearance="subtle" icon={<Archive24Regular />} onClick={() => void archive()} disabled={busy}>Archive</Button> : null}
          </div>
          {conversation?.messages.length ? (
            <div className={styles.messages} aria-live="polite">
              {conversation.messages.map((item) => (
                <div key={item.message_id} className={`${styles.message} ${item.role === "user" ? styles.managerMessage : styles.assistantMessage}`}>
                  <Caption1>{item.role === "user" ? "You" : "FreshSense Agent"}</Caption1>
                  <div className={`${styles.bubble} ${item.role === "user" ? styles.managerBubble : styles.assistantBubble}`}>{item.content}</div>
                  {item.citations.length ? <div className={styles.citations}>{item.citations.map((citation) => <Badge key={`${citation.source_type}-${citation.source_id}`} appearance="outline">{citation.label}</Badge>)}</div> : null}
                  {item.role === "assistant" ? <Caption1>{managerChatProvenance(item.metadata)} · no action executed</Caption1> : null}
                </div>
              ))}
              {busy ? <div className={`${styles.message} ${styles.assistantMessage}`}><Spinner size="tiny" label="Reviewing workspace evidence..." /></div> : null}
              <div ref={endRef} />
            </div>
          ) : (
            <div className={styles.empty}>
              <div className={styles.stack}><Bot24Regular fontSize={42} /><Title2>Ask about your produce operation</Title2><Body1>Start with a batch reference, fruit, location, or recent Agent decision.</Body1><div className={styles.row}>{managerChatSuggestions.map((suggestion) => <Button key={suggestion} appearance="secondary" onClick={() => setMessage(suggestion)}>{suggestion}</Button>)}</div></div>
            </div>
          )}
          <form className={styles.composer} onSubmit={send}>
            <div className={styles.composerRow}>
              <Field className={styles.composerInput} label="Message Manager Chat">
                <Textarea value={message} maxLength={4000} resize="vertical" placeholder="Ask why a batch was flagged, what needs review, or what happened earlier..." onChange={(_, data) => setMessage(data.value)} />
              </Field>
              <Button type="submit" appearance="primary" icon={<Send24Regular />} disabled={!canSendManagerMessage(message, busy)}>Send</Button>
            </div>
            <Caption1>FreshSense can explain records and propose next steps. It cannot approve holds or make food-safety decisions in chat.</Caption1>
          </form>
        </Card>
      </div>
    </section>
  );
}

function messageFrom(reason: unknown) {
  return reason instanceof Error ? reason.message : "Manager Chat could not complete the request.";
}
