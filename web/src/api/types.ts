export interface User {id:string;email:string;name:string;timezone:string;work_days:number[];work_start:string;work_end:string;daily_max_focus_minutes:number;energy_peak:'morning'|'afternoon'|'evening';role:'owner'|'admin'|'user';plan_id:string;ai_enabled:boolean}
export interface Action {id:string;title:string;kind:'habit'|'project';weekly_minutes_target:number;total_minutes_estimate:number|null;preferred_block_minutes:number;min_block_minutes:number;max_block_minutes:number;preferred_time_of_day:'morning'|'afternoon'|'evening'|'any';requires_deep_focus:boolean}
export interface Obstacle {risk_text:string;if_cue:string;then_response:string}
export interface Checkin {id:string;metric_value:number;note:string;recorded_at:string}
export interface Goal {id:string;title:string;outcome_statement:string;season_id:string|null;metric_name:string;metric_unit:string;metric_start:number;metric_target:number;start_date:string;target_date:string;why_facts:string;why_feelings:string;why_function:string;anti_goals:string[];confidence_pct:number;follow_through_pct:number;priority:number;status:'active'|'paused'|'done'|'dropped';actions:Action[];obstacles:Obstacle[];checkins:Checkin[]}
export interface Block {id:string;goal_id:string;action_id:string;title?:string;action_title?:string;start_at:string;end_at:string;planned_minutes:number;status:'proposed'|'accepted'|'published'|'completed'|'skipped'|'moved'|'cancelled';reason:string;week_start:string}
export interface FocusSession {id:string;time_block_id:string|null;action_id:string|null;started_at:string;ends_at:string;ended_at:string|null;planned_minutes:number;actual_minutes:number|null;self_rating:number|null}
export interface Trajectory {goal_id:string;status:'on_track'|'adjust'|'off_track'|'insufficient_data';expected_fraction:number;actual_fraction:number;effort_ratio:number|null;projected_finish:string|null;reasons:string[]}
export interface Draft {blocks:Block[];capacity_warning: string | null; warnings?:string[]}
export interface Reflection {wins:string;misses:string;adjustments:string;week_start?:string}
export interface Busy {id:string;start_at:string;end_at:string}
export interface FocusStats {total_minutes:number;completed_sessions:number;average_rating:number|null;sessions?:FocusSession[]}
export interface Season {id:string;name:string;start_date:string;end_date:string;status:string}
