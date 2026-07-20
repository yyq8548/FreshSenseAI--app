export type WorkspaceRole = "manager" | "inspector" | "reviewer";
export type ReviewStatus = "pending" | "confirmed" | "corrected" | "dismissed";
export type ReviewedOutcome = "fresh" | "rotten" | "unsupported" | "uncertain";

export type AuthenticatedUser = {
  account_id: string;
  display_name: string | null;
  email: string | null;
  authentication_scheme: "local" | "api_key" | "entra";
  scopes: string[];
  workspace_id: string;
  workspace_role: WorkspaceRole;
};

export type WorkspaceMember = {
  member_id: string;
  role: WorkspaceRole;
  email: string | null;
  display_name: string | null;
  created_at_utc: string;
  last_seen_at_utc: string;
};

export type Workspace = {
  workspace_id: string;
  display_name: string;
  created_at_utc: string;
  plan: "pilot";
  image_retention: false;
  locations: Array<{ location_id: string; name: string; created_at_utc: string }>;
  current_role: WorkspaceRole;
  members: WorkspaceMember[];
};

export type Dashboard = {
  total_inspections: number;
  last_7_days: number;
  pending_reviews: number;
  reviewed_inspections: number;
  review_completion_rate: number | null;
  false_fresh_reviews: number;
  review_status_counts: Record<string, number>;
  fruit_counts: Record<string, number>;
  decision_counts: Record<string, number>;
};

export type Warning = { level: string; message: string };

export type Inspection = {
  inspection_id: string;
  created_at_utc: string;
  location_name: string;
  batch_reference: string;
  operator_note: string;
  decision: string;
  analysis_status: string;
  predicted_class: string | null;
  predicted_display_name: string | null;
  fruit: string | null;
  predicted_freshness: "fresh" | "rotten" | null;
  confidence: number | null;
  risk_level: string | null;
  recommendation: string;
  safety_notice: string;
  warnings: Warning[];
  model_version: string;
  review_status: ReviewStatus;
  reviewed_outcome: ReviewedOutcome | null;
  review_note: string;
  reviewed_at_utc: string | null;
  image_retained: false;
};

export type InspectionList = { inspections: Inspection[]; count: number };

export type AnalyzeResult = {
  inspection: Inspection;
  analysis: {
    decision: string;
    status: string;
    recommendation: string;
    safety_notice: string;
    prediction: {
      display_name: string;
      fruit: string;
      freshness: "fresh" | "rotten";
      confidence: number;
    } | null;
  };
};

export type WorkspaceInvitation = {
  invitation_id: string;
  email: string;
  role: "inspector" | "reviewer";
  expires_at_utc: string;
  invitation_token: string;
};
