export type Paginated<Key extends string, T> = { [P in Key]: T[] } & {
  total: number | null;
  next_cursor: string | null;
};
