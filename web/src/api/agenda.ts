import type { components } from "./schema";
import type { Block } from "./types";

type Schema = components["schemas"];
// API responses serialize defaults; make those values explicit in local form state.
export type Task = Required<Schema["TaskResponse"]>;
export type Recurrence = Required<Schema["RecurrenceInput"]>;
export type LocalEvent = Omit<
  Required<Schema["EventResponse"]>,
  "recurrence"
> & {
  recurrence: Recurrence | null;
};
export type AgendaItem = Required<
  Schema["app__integrations__event_feed__AgendaItem"]
>;
export type NotedBlock = Block;
export type PlanChange = Omit<
  Required<Schema["PlanChangeResponse"]>,
  "before" | "after"
> & {
  before: NotedBlock;
  after: NotedBlock | null;
};
export type DraftOutcome = Omit<
  Required<Schema["DraftResponse"]>,
  "blocks" | "changes"
> & {
  blocks: NotedBlock[];
  changes: PlanChange[];
};
