import { bigragApiUrl, trimSlash } from "@/config/runtime";

const buildRemoteUrl = (origin: string) => `${trimSlash(origin)}/mcp`;

const buildAuthHeader = (plaintext: string) => `Authorization: Bearer ${plaintext}`;

const buildClaudeDesktopJson = (serverName: string, origin: string, plaintext: string) =>
  JSON.stringify(
    {
      mcpServers: {
        [serverName]: {
          command: "bigrag-mcp",
          env: {
            BIGRAG_URL: trimSlash(origin),
            BIGRAG_API_KEY: plaintext,
          },
        },
      },
    },
    null,
    2,
  );

const shellQuote = (s: string) => `'${s.replace(/'/g, "'\\''")}'`;

const buildShellSnippet = (origin: string, plaintext: string) =>
  `BIGRAG_URL=${shellQuote(trimSlash(origin))} \\
  BIGRAG_API_KEY=${shellQuote(plaintext)} \\
  bigrag-mcp`;

export const buildSnippets = (serverName: string, keyValue: string) => ({
  remoteUrl: buildRemoteUrl(bigragApiUrl),
  authHeader: buildAuthHeader(keyValue),
  jsonSnippet: buildClaudeDesktopJson(serverName, bigragApiUrl, keyValue),
  shellSnippet: buildShellSnippet(bigragApiUrl, keyValue),
});
