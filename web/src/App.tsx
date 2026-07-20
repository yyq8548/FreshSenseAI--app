import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type ReactElement,
} from "react";
import { InteractionRequiredAuthError } from "@azure/msal-browser";
import { useIsAuthenticated, useMsal } from "@azure/msal-react";
import {
  Avatar,
  Badge,
  Body1,
  Button,
  Caption1,
  Card,
  CardHeader,
  Divider,
  Field,
  Input,
  makeStyles,
  MessageBar,
  MessageBarBody,
  ProgressBar,
  Select,
  Spinner,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Text,
  Textarea,
  Title1,
  Title2,
  tokens,
  Tooltip,
} from "@fluentui/react-components";
import {
  ArrowUpload24Regular,
  Camera24Regular,
  CheckmarkCircle24Regular,
  ClipboardTaskListLtr24Regular,
  Home24Regular,
  PeopleTeam24Regular,
  ShieldCheckmark24Regular,
  SignOut24Regular,
  Warning24Regular,
} from "@fluentui/react-icons";

import { FreshSenseApi } from "./api";
import { analysisProgressMessage } from "./analysis-progress";
import { prepareAnalysisImage } from "./prepare-analysis-image";
import type { RuntimeConfig } from "./config";
import type {
  AnalyzeResult,
  AuthenticatedUser,
  Dashboard,
  Inspection,
  ReviewedOutcome,
  Workspace,
  WorkspaceInvitation,
  WorkspaceRole,
} from "./types";

type View = "overview" | "inspect" | "reviews" | "team";
const invitationAcceptances = new Map<string, Promise<Workspace>>();

const useStyles = makeStyles({
  page: {
    minHeight: "100vh",
    backgroundColor: tokens.colorNeutralBackground2,
    color: tokens.colorNeutralForeground1,
  },
  shell: {
    minHeight: "100vh",
    display: "grid",
    gridTemplateColumns: "248px minmax(0, 1fr)",
    "@media (max-width: 820px)": {
      gridTemplateColumns: "1fr",
    },
  },
  sidebar: {
    position: "sticky",
    top: 0,
    height: "100vh",
    padding: "20px 16px",
    display: "flex",
    flexDirection: "column",
    gap: "20px",
    backgroundColor: tokens.colorNeutralBackground1,
    borderRight: `1px solid ${tokens.colorNeutralStroke2}`,
    "@media (max-width: 820px)": {
      position: "static",
      height: "auto",
      borderRight: "none",
      borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
      padding: "14px 16px",
    },
  },
  brand: { display: "flex", alignItems: "center", gap: "12px", padding: "0 8px" },
  brandMark: {
    width: "38px",
    height: "38px",
    borderRadius: tokens.borderRadiusMedium,
    display: "grid",
    placeItems: "center",
    color: tokens.colorNeutralForegroundOnBrand,
    backgroundColor: tokens.colorBrandBackground,
  },
  nav: {
    display: "flex",
    flexDirection: "column",
    gap: "4px",
    "@media (max-width: 820px)": {
      flexDirection: "row",
      overflowX: "auto",
    },
  },
  navButton: { justifyContent: "flex-start", minHeight: "42px" },
  sidebarFooter: {
    marginTop: "auto",
    display: "flex",
    flexDirection: "column",
    gap: "12px",
    "@media (max-width: 820px)": { display: "none" },
  },
  privacyNote: {
    display: "flex",
    gap: "8px",
    padding: "12px",
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorBrandBackground2,
  },
  main: { minWidth: 0 },
  topbar: {
    minHeight: "72px",
    padding: "14px clamp(18px, 4vw, 44px)",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "16px",
    backgroundColor: tokens.colorNeutralBackground1,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  content: {
    width: "min(1180px, 100%)",
    margin: "0 auto",
    padding: "clamp(22px, 4vw, 44px)",
  },
  heading: { display: "flex", flexDirection: "column", gap: "7px", marginBottom: "24px" },
  grid4: {
    display: "grid",
    gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
    gap: "14px",
    "@media (max-width: 980px)": { gridTemplateColumns: "repeat(2, minmax(0, 1fr))" },
    "@media (max-width: 540px)": { gridTemplateColumns: "1fr" },
  },
  grid2: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1.15fr) minmax(300px, .85fr)",
    gap: "18px",
    marginTop: "18px",
    "@media (max-width: 940px)": { gridTemplateColumns: "1fr" },
  },
  card: { padding: "18px", borderRadius: tokens.borderRadiusLarge },
  metric: { display: "flex", flexDirection: "column", gap: "8px" },
  metricValue: { fontSize: "30px", lineHeight: "36px", fontWeight: tokens.fontWeightSemibold },
  stack: { display: "flex", flexDirection: "column", gap: "14px" },
  row: { display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" },
  spread: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px" },
  formGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "14px",
    "@media (max-width: 620px)": { gridTemplateColumns: "1fr" },
  },
  uploadZone: {
    minHeight: "270px",
    border: `1px dashed ${tokens.colorBrandStroke1}`,
    borderRadius: tokens.borderRadiusLarge,
    backgroundColor: tokens.colorBrandBackground2,
    display: "grid",
    placeItems: "center",
    overflow: "hidden",
    textAlign: "center",
    padding: "20px",
  },
  preview: { width: "100%", maxHeight: "360px", objectFit: "contain" },
  fileInput: { position: "absolute", width: "1px", height: "1px", overflow: "hidden", clip: "rect(0 0 0 0)" },
  tableWrap: { overflowX: "auto" },
  empty: { padding: "42px 20px", textAlign: "center", color: tokens.colorNeutralForeground2 },
  centered: { minHeight: "100vh", display: "grid", placeItems: "center", padding: "24px" },
  authCard: { width: "min(520px, 100%)", padding: "28px", borderRadius: tokens.borderRadiusXLarge },
  configList: { margin: "8px 0 0", paddingLeft: "22px" },
  result: { borderLeft: `4px solid ${tokens.colorBrandStroke1}`, paddingLeft: "14px" },
  detailList: { display: "grid", gridTemplateColumns: "140px 1fr", gap: "8px 14px" },
  inviteToken: { wordBreak: "break-all", fontFamily: "Consolas, monospace", fontSize: tokens.fontSizeBase200 },
});

export function ConfigurationRequired({
  missing,
  error,
}: {
  missing: string[];
  error?: string;
}) {
  const styles = useStyles();
  return (
    <main className={`${styles.page} ${styles.centered}`}>
      <Card className={styles.authCard}>
        <div className={styles.stack}>
          <div className={styles.brandMark}><ShieldCheckmark24Regular /></div>
          <Title1>Connect FreshSense securely</Title1>
          <Body1>
            This workbench requires Microsoft Entra External ID and the FreshSense API.
            It does not include a demo account or a browser API key.
          </Body1>
          {error ? <MessageBar intent="error"><MessageBarBody>{error}</MessageBarBody></MessageBar> : null}
          {missing.length > 0 ? (
            <div>
              <Text weight="semibold">Add these values to web/.env.local:</Text>
              <ul className={styles.configList}>
                {missing.map((key) => <li key={key}><code>{key}</code></li>)}
              </ul>
            </div>
          ) : null}
          <Caption1>Use web/.env.example as the starting point.</Caption1>
        </div>
      </Card>
    </main>
  );
}

export function App({ config }: { config: RuntimeConfig }) {
  const authenticated = useIsAuthenticated();
  const { instance, accounts } = useMsal();
  const styles = useStyles();

  const signIn = () => instance.loginRedirect({ scopes: [config.apiScope] });
  if (!authenticated || accounts.length === 0) {
    return (
      <main className={`${styles.page} ${styles.centered}`}>
        <Card className={styles.authCard}>
          <div className={styles.stack}>
            <div className={styles.brandMark}><ShieldCheckmark24Regular /></div>
            <Title1>FreshSense Workbench</Title1>
            <Body1>
              Record produce inspections, review AI-assisted results, and keep human
              decisions attached to each check.
            </Body1>
            <MessageBar intent="warning">
              <MessageBarBody>
                FreshSense supports visual decision support only. Staff remain responsible
                for food safety decisions.
              </MessageBarBody>
            </MessageBar>
            <Button appearance="primary" size="large" onClick={signIn}>
              Sign in with Microsoft
            </Button>
            <Caption1>Photos are analyzed for the request and are not retained by default.</Caption1>
          </div>
        </Card>
      </main>
    );
  }

  return <Workbench config={config} />;
}

function Workbench({ config }: { config: RuntimeConfig }) {
  const styles = useStyles();
  const { instance, accounts } = useMsal();
  const [view, setView] = useState<View>("overview");
  const [user, setUser] = useState<AuthenticatedUser | null>(null);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [inspections, setInspections] = useState<Inspection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const getToken = useCallback(async () => {
    const account = accounts[0];
    try {
      const result = await instance.acquireTokenSilent({ account, scopes: [config.apiScope] });
      return result.accessToken;
    } catch (reason) {
      if (reason instanceof InteractionRequiredAuthError) {
        await instance.acquireTokenRedirect({ account, scopes: [config.apiScope] });
      }
      throw reason;
    }
  }, [accounts, config.apiScope, instance]);
  const api = useMemo(() => new FreshSenseApi(config, getToken), [config, getToken]);

  const refresh = useCallback(async () => {
    setError(null);
    const [nextUser, nextWorkspace, nextDashboard, nextInspections] = await Promise.all([
      api.me(), api.workspace(), api.dashboard(), api.inspections(),
    ]);
    setUser(nextUser);
    setWorkspace(nextWorkspace);
    setDashboard(nextDashboard);
    setInspections(nextInspections.inspections);
  }, [api]);

  useEffect(() => {
    let active = true;
    const invitation = new URLSearchParams(window.location.search).get("invite");
    const load = async () => {
      try {
        if (invitation) {
          let acceptance = invitationAcceptances.get(invitation);
          if (!acceptance) {
            acceptance = api.acceptInvitation(invitation);
            invitationAcceptances.set(invitation, acceptance);
          }
          try {
            await acceptance;
          } catch (reason) {
            invitationAcceptances.delete(invitation);
            throw reason;
          }
          window.history.replaceState({}, "", window.location.pathname);
        }
        await refresh();
      } catch (reason) {
        if (active) setError(messageFrom(reason));
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    return () => { active = false; };
  }, [api, refresh]);

  if (loading) {
    return <main className={`${styles.page} ${styles.centered}`}><Spinner label="Loading your workspace..." /></main>;
  }

  const navItems: Array<{ id: View; label: string; icon: ReactElement; roles?: WorkspaceRole[] }> = [
    { id: "overview", label: "Overview", icon: <Home24Regular /> },
    { id: "inspect", label: "New inspection", icon: <Camera24Regular />, roles: ["manager", "inspector"] },
    { id: "reviews", label: "Review queue", icon: <ClipboardTaskListLtr24Regular />, roles: ["manager", "reviewer"] },
    { id: "team", label: "Team", icon: <PeopleTeam24Regular />, roles: ["manager"] },
  ];
  const visibleNav = navItems.filter((item) => !item.roles || (user && item.roles.includes(user.workspace_role)));

  return (
    <div className={`${styles.page} ${styles.shell}`}>
      <aside className={styles.sidebar}>
        <div className={styles.brand}>
          <div className={styles.brandMark}><ShieldCheckmark24Regular /></div>
          <div><Text size={400} weight="semibold">FreshSense</Text><br /><Caption1>Inspection workbench</Caption1></div>
        </div>
        <nav className={styles.nav} aria-label="Workspace navigation">
          {visibleNav.map((item) => (
            <Button
              key={item.id}
              className={styles.navButton}
              appearance={view === item.id ? "primary" : "subtle"}
              icon={item.icon}
              onClick={() => setView(item.id)}
            >
              {item.label}
            </Button>
          ))}
        </nav>
        <div className={styles.sidebarFooter}>
          <div className={styles.privacyNote}><ShieldCheckmark24Regular /><Caption1>Uploaded photos are not stored by default.</Caption1></div>
          <Button appearance="subtle" icon={<SignOut24Regular />} onClick={() => instance.logoutRedirect()}>Sign out</Button>
        </div>
      </aside>
      <main className={styles.main}>
        <header className={styles.topbar}>
          <div><Text weight="semibold">{workspace?.display_name || "Workspace"}</Text><br /><Caption1>{user?.workspace_role || "member"} access</Caption1></div>
          <Tooltip content={user?.email || "Signed-in account"} relationship="label">
            <Avatar name={user?.display_name || user?.email || "FreshSense user"} />
          </Tooltip>
        </header>
        <div className={styles.content}>
          {error ? <MessageBar intent="error"><MessageBarBody>{error}</MessageBarBody></MessageBar> : null}
          {view === "overview" && dashboard ? <Overview dashboard={dashboard} inspections={inspections} onNavigate={setView} /> : null}
          {view === "inspect" ? <InspectionForm api={api} onComplete={async () => { await refresh(); setView("overview"); }} /> : null}
          {view === "reviews" ? <ReviewQueue api={api} inspections={inspections} onChanged={refresh} /> : null}
          {view === "team" && workspace ? <TeamPage api={api} workspace={workspace} /> : null}
        </div>
      </main>
    </div>
  );
}

function Overview({ dashboard, inspections, onNavigate }: { dashboard: Dashboard; inspections: Inspection[]; onNavigate: (view: View) => void }) {
  const styles = useStyles();
  const completion = dashboard.review_completion_rate ?? 0;
  return (
    <section>
      <div className={styles.heading}><Title1>Inspection overview</Title1><Body1>Live workspace activity and human review progress.</Body1></div>
      <div className={styles.grid4}>
        <Metric label="Total inspections" value={dashboard.total_inspections} />
        <Metric label="Last 7 days" value={dashboard.last_7_days} />
        <Metric label="Pending review" value={dashboard.pending_reviews} />
        <Metric label="False-fresh reviews" value={dashboard.false_fresh_reviews} warning={dashboard.false_fresh_reviews > 0} />
      </div>
      <div className={styles.grid2}>
        <Card className={styles.card}>
          <div className={styles.stack}>
            <div className={styles.spread}><Title2>Review coverage</Title2><Text weight="semibold">{Math.round(completion * 100)}%</Text></div>
            <ProgressBar value={completion} />
            <Caption1>{dashboard.reviewed_inspections} of {dashboard.total_inspections} inspections reviewed</Caption1>
            <Button appearance="secondary" onClick={() => onNavigate("reviews")}>Open review queue</Button>
          </div>
        </Card>
        <Card className={styles.card}>
          <div className={styles.stack}>
            <Title2>Recent activity</Title2>
            {inspections.length === 0 ? <div className={styles.empty}>No inspections yet.</div> : inspections.slice(0, 4).map((item) => <InspectionSummary key={item.inspection_id} inspection={item} />)}
          </div>
        </Card>
      </div>
    </section>
  );
}

function Metric({ label, value, warning = false }: { label: string; value: number; warning?: boolean }) {
  const styles = useStyles();
  return <Card className={styles.card}><div className={styles.metric}><Caption1>{label}</Caption1><div className={styles.spread}><Text className={styles.metricValue}>{value}</Text>{warning ? <Warning24Regular color={tokens.colorPaletteDarkOrangeForeground1} /> : <CheckmarkCircle24Regular color={tokens.colorBrandForeground1} />}</div></div></Card>;
}

function InspectionForm({ api, onComplete }: { api: FreshSenseApi; onComplete: () => Promise<void> }) {
  const styles = useStyles();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [location, setLocation] = useState("Main store");
  const [batch, setBatch] = useState("");
  const [note, setNote] = useState("");
  const [result, setResult] = useState<AnalyzeResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [busySeconds, setBusySeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const preview = useMemo(() => file ? URL.createObjectURL(file) : null, [file]);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  useEffect(() => {
    if (!busy) {
      setBusySeconds(0);
      return;
    }
    const startedAt = Date.now();
    const timer = window.setInterval(() => {
      setBusySeconds(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [busy]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!file) { setError("Choose a JPEG, PNG, or WebP photo first."); return; }
    setBusy(true); setError(null); setResult(null);
    try {
      const upload = await prepareAnalysisImage(file);
      setResult(await api.analyze({ file: upload, locationName: location, batchReference: batch, operatorNote: note }));
    } catch (reason) { setError(messageFrom(reason)); } finally { setBusy(false); }
  };

  return (
    <section>
      <div className={styles.heading}><Title1>New inspection</Title1><Body1>Photograph one supported fruit and record where the check happened.</Body1></div>
      <form className={styles.grid2} onSubmit={submit}>
        <Card className={styles.card}>
          <div className={styles.stack}>
            <div className={styles.uploadZone}>
              {preview ? <img className={styles.preview} src={preview} alt="Selected fruit preview" /> : <div className={styles.stack}><ArrowUpload24Regular /><Text weight="semibold">Choose a fruit photo</Text><Caption1>JPEG, PNG, or WebP. One apple, banana, or orange.</Caption1></div>}
            </div>
            <input ref={inputRef} className={styles.fileInput} type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => setFile(event.target.files?.[0] || null)} />
            <Button type="button" appearance="secondary" onClick={() => inputRef.current?.click()}>Choose photo</Button>
            <div className={styles.formGrid}>
              <Field label="Location" required><Input value={location} onChange={(_, data) => setLocation(data.value)} maxLength={80} /></Field>
              <Field label="Batch reference"><Input value={batch} onChange={(_, data) => setBatch(data.value)} maxLength={100} /></Field>
            </div>
            <Field label="Operator note"><Textarea value={note} onChange={(_, data) => setNote(data.value)} maxLength={1000} resize="vertical" /></Field>
            {error ? <MessageBar intent="error"><MessageBarBody>{error}</MessageBarBody></MessageBar> : null}
            <Button type="submit" appearance="primary" size="large" disabled={busy}>{busy ? `Analyzing... ${busySeconds}s` : "Analyze and record"}</Button>
            {busy ? <MessageBar intent={busySeconds >= 20 ? "warning" : "info"}><MessageBarBody>{analysisProgressMessage(busySeconds)}</MessageBarBody></MessageBar> : null}
          </div>
        </Card>
        <Card className={styles.card}>
          {!result ? <div className={styles.empty}>The result and safety guidance will appear here.</div> : <div className={styles.stack}><Badge appearance="tint" color={result.analysis.prediction?.freshness === "rotten" ? "danger" : "success"}>{result.analysis.status}</Badge><div className={styles.result}><Title2>{result.analysis.prediction?.display_name || "Unsupported or uncertain"}</Title2>{result.analysis.prediction ? <Text>{Math.round(result.analysis.prediction.confidence * 100)}% model confidence</Text> : null}</div><Body1>{result.analysis.recommendation}</Body1><MessageBar intent="warning"><MessageBarBody>{result.analysis.safety_notice}</MessageBarBody></MessageBar><Button appearance="secondary" onClick={() => void onComplete()}>Finish and return to overview</Button></div>}
        </Card>
      </form>
    </section>
  );
}

function ReviewQueue({ api, inspections, onChanged }: { api: FreshSenseApi; inspections: Inspection[]; onChanged: () => Promise<void> }) {
  const styles = useStyles();
  const pending = inspections.filter((item) => item.review_status === "pending");
  const [selected, setSelected] = useState<Inspection | null>(pending[0] || null);
  const [outcome, setOutcome] = useState<ReviewedOutcome>("fresh");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setOutcome(selected?.predicted_freshness || "uncertain");
  }, [selected]);
  const submit = async (status: "confirmed" | "corrected" | "dismissed") => {
    if (!selected) return;
    setBusy(true); setError(null);
    try {
      await api.review(selected.inspection_id, { review_status: status, reviewed_outcome: status === "dismissed" ? null : outcome, note });
      setSelected(null); setNote(""); await onChanged();
    } catch (reason) { setError(messageFrom(reason)); } finally { setBusy(false); }
  };
  return (
    <section>
      <div className={styles.heading}><Title1>Human review queue</Title1><Body1>Confirm the visible result after a staff inspection. AI output is never the final food-safety decision.</Body1></div>
      <div className={styles.grid2}>
        <Card className={styles.card}>
          <div className={styles.stack}><div className={styles.spread}><Title2>Pending</Title2><Badge appearance="filled">{pending.length}</Badge></div>{pending.length === 0 ? <div className={styles.empty}>All recorded inspections have been reviewed.</div> : pending.map((item) => <Button key={item.inspection_id} appearance={selected?.inspection_id === item.inspection_id ? "primary" : "subtle"} onClick={() => setSelected(item)}><span>{item.predicted_display_name || "Uncertain"} · {item.location_name}</span></Button>)}</div>
        </Card>
        <Card className={styles.card}>
          {!selected ? <div className={styles.empty}>Select an inspection to review.</div> : <div className={styles.stack}><Title2>{selected.predicted_display_name || "Unsupported or uncertain"}</Title2><div className={styles.detailList}><Caption1>Location</Caption1><Text>{selected.location_name}</Text><Caption1>Confidence</Caption1><Text>{selected.confidence === null ? "Not available" : `${Math.round(selected.confidence * 100)}%`}</Text><Caption1>Recorded</Caption1><Text>{formatDate(selected.created_at_utc)}</Text></div><Divider /><Field label="Observed outcome"><Select value={outcome} onChange={(_, data) => setOutcome(data.value as ReviewedOutcome)}><option value="fresh">Fresh</option><option value="rotten">Rotten</option><option value="unsupported">Unsupported</option><option value="uncertain">Uncertain</option></Select></Field><Field label="Review note"><Textarea value={note} onChange={(_, data) => setNote(data.value)} maxLength={1000} /></Field>{error ? <MessageBar intent="error"><MessageBarBody>{error}</MessageBarBody></MessageBar> : null}<div className={styles.row}><Button appearance="primary" disabled={busy} onClick={() => void submit(outcome === selected.predicted_freshness ? "confirmed" : "corrected")}>Save review</Button><Button appearance="secondary" disabled={busy} onClick={() => void submit("dismissed")}>Dismiss result</Button></div></div>}
        </Card>
      </div>
    </section>
  );
}

function TeamPage({ api, workspace }: { api: FreshSenseApi; workspace: Workspace }) {
  const styles = useStyles();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"inspector" | "reviewer">("inspector");
  const [invitation, setInvitation] = useState<WorkspaceInvitation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const invite = async (event: FormEvent) => {
    event.preventDefault(); setError(null); setInvitation(null);
    try { setInvitation(await api.invite(email, role)); } catch (reason) { setError(messageFrom(reason)); }
  };
  const inviteUrl = invitation ? `${window.location.origin}${window.location.pathname}?invite=${encodeURIComponent(invitation.invitation_token)}` : null;
  return (
    <section>
      <div className={styles.heading}><Title1>Workspace team</Title1><Body1>Assign only the access each team member needs.</Body1></div>
      <div className={styles.grid2}>
        <Card className={styles.card}><div className={styles.stack}><Title2>Members</Title2><div className={styles.tableWrap}><Table><TableHeader><TableRow><TableHeaderCell>Member</TableHeaderCell><TableHeaderCell>Role</TableHeaderCell><TableHeaderCell>Last active</TableHeaderCell></TableRow></TableHeader><TableBody>{workspace.members.map((member) => <TableRow key={member.member_id}><TableCell><Text weight="semibold">{member.display_name || member.email || member.member_id}</Text><br /><Caption1>{member.email || "Email unavailable"}</Caption1></TableCell><TableCell><Badge appearance="tint">{member.role}</Badge></TableCell><TableCell>{formatDate(member.last_seen_at_utc)}</TableCell></TableRow>)}</TableBody></Table></div></div></Card>
        <Card className={styles.card}><form className={styles.stack} onSubmit={invite}><Title2>Invite a member</Title2><Field label="Microsoft account email" required><Input type="email" value={email} onChange={(_, data) => setEmail(data.value)} /></Field><Field label="Role"><Select value={role} onChange={(_, data) => setRole(data.value as "inspector" | "reviewer")}><option value="inspector">Inspector: run inspections</option><option value="reviewer">Reviewer: review results</option></Select></Field><Button type="submit" appearance="primary">Create one-time invitation</Button>{error ? <MessageBar intent="error"><MessageBarBody>{error}</MessageBarBody></MessageBar> : null}{inviteUrl ? <MessageBar intent="success"><MessageBarBody><div className={styles.stack}><Text weight="semibold">Copy this link now. The token is shown only once.</Text><code className={styles.inviteToken}>{inviteUrl}</code><Button type="button" appearance="secondary" onClick={() => navigator.clipboard.writeText(inviteUrl)}>Copy invitation link</Button></div></MessageBarBody></MessageBar> : null}</form></Card>
      </div>
    </section>
  );
}

function InspectionSummary({ inspection }: { inspection: Inspection }) {
  const styles = useStyles();
  return <div className={styles.spread}><div><Text weight="semibold">{inspection.predicted_display_name || "Uncertain result"}</Text><br /><Caption1>{inspection.location_name} · {formatDate(inspection.created_at_utc)}</Caption1></div><Badge appearance="tint" color={inspection.review_status === "pending" ? "warning" : "success"}>{inspection.review_status}</Badge></div>;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function messageFrom(reason: unknown) {
  return reason instanceof Error ? reason.message : "FreshSense could not complete the request.";
}
