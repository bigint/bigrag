import type { Chunk, Document } from "@/types/bigrag";

export type QuestionDocument = Pick<Document, "chunk_count" | "filename" | "id" | "status">;
export type QuestionChunk = Pick<Chunk, "document_id" | "metadata" | "text">;

type BuildQuestionsParams = {
  collection: string;
  chunks: readonly QuestionChunk[];
  count?: number;
  documents: readonly QuestionDocument[];
  random?: () => number;
};

const STOP_WORDS = new Set([
  "about",
  "after",
  "again",
  "also",
  "and",
  "any",
  "are",
  "because",
  "been",
  "before",
  "being",
  "between",
  "both",
  "can",
  "could",
  "did",
  "does",
  "each",
  "for",
  "from",
  "had",
  "has",
  "have",
  "how",
  "into",
  "its",
  "may",
  "more",
  "must",
  "not",
  "one",
  "only",
  "other",
  "our",
  "out",
  "over",
  "should",
  "such",
  "than",
  "that",
  "the",
  "their",
  "there",
  "these",
  "they",
  "this",
  "through",
  "under",
  "use",
  "used",
  "using",
  "was",
  "were",
  "what",
  "when",
  "where",
  "which",
  "while",
  "with",
  "would",
  "your",
]);

const normalizePhrase = (value: string) =>
  value
    .replace(/\.[a-z0-9]{1,8}$/i, "")
    .replace(/[_-]+/g, " ")
    .replace(/[^a-z0-9\s]/gi, " ")
    .replace(/\s+/g, " ")
    .trim();

const titleCase = (value: string) =>
  normalizePhrase(value)
    .split(" ")
    .filter(Boolean)
    .map((word) => word.slice(0, 1).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");

const importantTokens = (value: string) =>
  normalizePhrase(value)
    .toLowerCase()
    .split(" ")
    .filter((word) => word.length >= 3 && !STOP_WORDS.has(word) && !/^\d+$/.test(word));

const addCandidate = (scores: Map<string, number>, phrase: string, weight: number) => {
  const normalized = normalizePhrase(phrase).toLowerCase();
  if (normalized.length < 4) return;
  if (STOP_WORDS.has(normalized)) return;
  scores.set(normalized, (scores.get(normalized) ?? 0) + weight);
};

const scoreChunkTerms = (scores: Map<string, number>, text: string) => {
  const sentences = text.split(/[.!?\n]/).slice(0, 8);
  for (const sentence of sentences) {
    const tokens = importantTokens(sentence).slice(0, 16);
    for (const token of tokens) addCandidate(scores, token, 1);
    for (let index = 0; index < tokens.length - 1; index += 1) {
      addCandidate(scores, `${tokens[index]} ${tokens[index + 1]}`, 3);
    }
    for (let index = 0; index < tokens.length - 2; index += 1) {
      addCandidate(scores, `${tokens[index]} ${tokens[index + 1]} ${tokens[index + 2]}`, 2);
    }
  }
};

const scoredTopics = (
  collection: string,
  documents: readonly QuestionDocument[],
  chunks: readonly QuestionChunk[],
  random: () => number,
) => {
  const scores = new Map<string, number>();
  for (const document of documents) {
    const title = titleCase(document.filename);
    if (title) addCandidate(scores, title, 5);
    for (const token of importantTokens(document.filename)) addCandidate(scores, token, 1);
  }
  for (const chunk of chunks) scoreChunkTerms(scores, chunk.text);
  const fallbackCollection = titleCase(collection) || "this collection";
  addCandidate(scores, fallbackCollection, 1);
  return [...scores.entries()]
    .map(([topic, score]) => ({ score: score + random(), topic }))
    .sort((left, right) => right.score - left.score)
    .map((item) => item.topic);
};

const pick = <T,>(items: readonly T[], index: number): T => items[index % items.length];

const uniquePush = (items: string[], value: string, limit: number) => {
  const trimmed = value.replace(/\s+/g, " ").trim();
  if (!trimmed || items.includes(trimmed) || items.length >= limit) return;
  items.push(trimmed);
};

export const questionChunkOffset = (
  document: QuestionDocument,
  limit = 24,
  random: () => number = Math.random,
) => {
  const maxOffset = Math.max(0, document.chunk_count - limit);
  return Math.floor(random() * (maxOffset + 1));
};

export const readyQuestionDocuments = (
  documents: readonly QuestionDocument[],
  count = 6,
  random: () => number = Math.random,
) =>
  documents
    .filter((document) => document.status === "ready" && document.chunk_count > 0)
    .map((document) => ({ document, rank: random() }))
    .sort((left, right) => left.rank - right.rank)
    .slice(0, count)
    .map((item) => item.document);

export const buildQuestionSuggestions = ({
  collection,
  chunks,
  count = 5,
  documents,
  random = Math.random,
}: BuildQuestionsParams) => {
  const topics = scoredTopics(collection, documents, chunks, random);
  const primary = pick(topics, 0);
  const secondary = pick(topics, 1);
  const tertiary = pick(topics, 2);
  const documentTitles = documents.map((document) => titleCase(document.filename)).filter(Boolean);
  const firstDocument = pick(documentTitles.length ? documentTitles : topics, 0);
  const secondDocument = pick(documentTitles.length > 1 ? documentTitles : topics, 1);
  const templates = [
    `What should I understand about ${primary}?`,
    `Which source best explains ${secondary}?`,
    `What evidence supports the main points about ${tertiary}?`,
    `How do ${primary} and ${secondary} connect?`,
    `What are the risks or caveats around ${pick(topics, 3)}?`,
    `What does ${firstDocument} say that I should not miss?`,
    `Where does ${collection} mention ${pick(topics, 4)}?`,
    `Compare the ideas from ${firstDocument} and ${secondDocument}.`,
    `What decisions or next steps are implied by ${pick(topics, 5)}?`,
    `What are the most repeated themes in ${collection}?`,
  ];
  const offset = Math.floor(random() * templates.length);
  const questions: string[] = [];
  for (let index = 0; index < templates.length && questions.length < count; index += 1) {
    uniquePush(questions, pick(templates, index + offset), count);
  }
  while (questions.length < count) {
    uniquePush(questions, `What else should I ask about ${pick(topics, questions.length)}?`, count);
  }
  return questions;
};
