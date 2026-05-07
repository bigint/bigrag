import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const target = resolve(process.cwd(), process.argv[2] ?? "next-env.d.ts");
const bannedLines = new Set([
  "// NOTE: This file should not be edited",
  "// see https://nextjs.org/docs/app/api-reference/config/typescript for more information.",
]);

const source = readFileSync(target, "utf8");
const cleaned = source
  .split("\n")
  .filter((line) => !bannedLines.has(line.trim()))
  .join("\n")
  .replace(/\n{2,}$/, "\n");

if (cleaned !== source) {
  writeFileSync(target, cleaned);
}
