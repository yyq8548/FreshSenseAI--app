import type { RuntimeConfig } from "./config";
import type {
  AnalyzeResult,
  AuthenticatedUser,
  Dashboard,
  Inspection,
  InspectionList,
  ReviewedOutcome,
  ReviewStatus,
  Workspace,
  WorkspaceInvitation,
  WorkspaceRole,
} from "./types";

type TokenProvider = () => Promise<string>;

export class FreshSenseApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
  ) {
    super(message);
  }
}

export class FreshSenseApi {
  constructor(
    private readonly config: RuntimeConfig,
    private readonly getToken: TokenProvider,
  ) {}

  me() {
    return this.request<AuthenticatedUser>("/api/v1/me");
  }

  workspace() {
    return this.request<Workspace>("/api/v1/workspace");
  }

  dashboard() {
    return this.request<Dashboard>("/api/v1/dashboard");
  }

  inspections() {
    return this.request<InspectionList>("/api/v1/inspections?limit=200");
  }

  analyze(input: {
    file: File;
    locationName: string;
    batchReference: string;
    operatorNote: string;
  }) {
    const body = new FormData();
    body.append("file", input.file);
    body.append("location_name", input.locationName);
    body.append("batch_reference", input.batchReference);
    body.append("operator_note", input.operatorNote);
    return this.request<AnalyzeResult>("/api/v1/inspections/analyze", {
      method: "POST",
      body,
    });
  }

  review(
    inspectionId: string,
    input: {
      review_status: Exclude<ReviewStatus, "pending">;
      reviewed_outcome: ReviewedOutcome | null;
      note: string;
    },
  ) {
    return this.request<Inspection>(
      `/api/v1/inspections/${encodeURIComponent(inspectionId)}/review`,
      { method: "PATCH", body: JSON.stringify(input) },
    );
  }

  invite(email: string, role: Exclude<WorkspaceRole, "manager">) {
    return this.request<WorkspaceInvitation>("/api/v1/workspace/invitations", {
      method: "POST",
      body: JSON.stringify({ email, role, expires_days: 7 }),
    });
  }

  acceptInvitation(invitationToken: string) {
    return this.request<Workspace>("/api/v1/workspace/invitations/accept", {
      method: "POST",
      body: JSON.stringify({ invitation_token: invitationToken }),
    });
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const token = await this.getToken();
    const headers = new Headers(init.headers);
    headers.set("Authorization", `Bearer ${token}`);
    if (typeof init.body === "string") {
      headers.set("Content-Type", "application/json");
    }
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 30_000);
    let response: Response;
    try {
      response = await fetch(`${this.config.apiBaseUrl}${path}`, {
        ...init,
        headers,
        signal: controller.signal,
      });
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        throw new FreshSenseApiError(
          "FreshSense did not respond within 30 seconds. Please retry once.",
          0,
          "REQUEST_TIMEOUT",
        );
      }
      throw error;
    } finally {
      window.clearTimeout(timeout);
    }
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as
        | { error?: { code?: string; message?: string } }
        | null;
      throw new FreshSenseApiError(
        payload?.error?.message || "FreshSense could not complete the request.",
        response.status,
        payload?.error?.code || "REQUEST_FAILED",
      );
    }
    return (await response.json()) as T;
  }
}
