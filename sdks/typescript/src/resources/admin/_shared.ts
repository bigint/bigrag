export function pagination(options: { limit?: number; offset?: number }): Record<string, string> {
  const params: Record<string, string> = {};
  if (options.limit !== undefined) params.limit = String(options.limit);
  if (options.offset !== undefined) params.offset = String(options.offset);
  return params;
}
