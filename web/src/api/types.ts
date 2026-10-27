import type { components } from './schema';
type Schema = components['schemas'];
// Response models serialize their declared defaults. Make those fields explicit in UI state.
export type User = Omit<Required<Schema['Profile']>, 'role'|'energy_peak'> & {role:'owner'|'admin'|'user';energy_peak:'morning'|'afternoon'|'evening'};
export type Action = Required<Schema['ActionResponse']>;
export type Obstacle = Schema['ObstacleInput'];
export type Checkin = Required<Schema['CheckinResponse']>;
export type Goal = Omit<Required<Schema['GoalResponse']>,'actions'|'obstacles'|'checkins'> & {actions:Action[];obstacles:Obstacle[];checkins:Checkin[]};
export type Block = Required<Schema['BlockResponse']>;
export type FocusSession = Required<Schema['FocusResponse']>;
export type Trajectory = Required<Schema['TrajectoryResponse']>;
export type Draft = Required<Schema['DraftResponse']>;
export type Reflection = Pick<Schema['ReflectionResponse'],'wins'|'misses'|'adjustments'> & {week_start?:string};
export type Busy = Schema['BusyResponse'];
export type FocusStats = Schema['FocusStats'];
export type Season = Schema['SeasonResponse'];
