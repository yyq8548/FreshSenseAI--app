import {
  BrowserCacheLocation,
  type Configuration,
  PublicClientApplication,
} from "@azure/msal-browser";

import type { RuntimeConfig } from "./config";

export function createMsalClient(config: RuntimeConfig): PublicClientApplication {
  const msalConfiguration: Configuration = {
    auth: {
      clientId: config.clientId,
      authority: config.authority,
      redirectUri: window.location.origin,
      postLogoutRedirectUri: window.location.origin,
      knownAuthorities: [`${config.tenantSubdomain}.ciamlogin.com`],
    },
    cache: {
      cacheLocation: BrowserCacheLocation.SessionStorage,
    },
    system: {
      allowPlatformBroker: false,
    },
  };
  return new PublicClientApplication(msalConfiguration);
}
