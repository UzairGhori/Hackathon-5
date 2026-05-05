// Channel & Enum types
export type Channel = "web" | "gmail" | "whatsapp" | "sms" | "slack" | "teams";
export type TicketStatus = "open" | "in_progress" | "waiting_on_customer" | "escalated" | "resolved" | "closed";
export type TicketPriority = "low" | "medium" | "high" | "critical";
export type TicketEventType = "created" | "status_changed" | "priority_changed" | "assigned" | "escalated" | "note_added" | "resolved" | "closed";

// Ticket
export interface Ticket {
  id: string;
  conversation_id: string;
  customer_id: string;
  channel: Channel;
  subject: string;
  description?: string;
  status: TicketStatus;
  priority: TicketPriority;
  assigned_to?: string;
  tags: string[];
  created_at: string;
  updated_at: string;
  resolved_at?: string;
  closed_at?: string;
}

export interface TicketEvent {
  id: string;
  ticket_id: string;
  event_type: TicketEventType;
  actor: string;
  old_value?: Record<string, unknown>;
  new_value?: Record<string, unknown>;
  note?: string;
  created_at: string;
}

// Metrics
export interface ResponseTimeStats {
  total_runs: number;
  avg_ms: number;
  min_ms: number;
  max_ms: number;
  p50_ms: number;
  p95_ms: number;
}

export interface MessageCounts {
  total: number;
  inbound: number;
  outbound: number;
  by_channel: Record<string, number>;
}

export interface EscalationStats {
  total_runs: number;
  escalated_count: number;
  escalation_rate_pct: number;
  by_category: Record<string, number>;
}

export interface ResolutionRate {
  total_runs: number;
  resolved_by_ai: number;
  escalated: number;
  ai_resolution_rate_pct: number;
}

export interface ErrorRate {
  total_runs: number;
  error_count: number;
  error_rate_pct: number;
}

export interface TokenUsage {
  total_runs: number;
  total_tokens_input: number;
  total_tokens_output: number;
  total_tokens: number;
  avg_tokens_input: number;
  avg_tokens_output: number;
}

export interface ChannelStats {
  total_runs: number;
  avg_response_time_ms: number;
  resolved_by_ai: number;
  escalated: number;
  resolution_rate_pct: number;
}

export interface DashboardMetrics {
  response_time: ResponseTimeStats;
  messages: MessageCounts;
  escalations: EscalationStats;
  resolution: ResolutionRate;
  errors: ErrorRate;
  tokens: TokenUsage;
  by_channel: Record<string, ChannelStats>;
}

// Demo
export interface RecentMessage {
  id: string;
  direction: string;
  sender: string;
  content: string;
  channel: string;
  created_at: string;
}

export interface DBStats {
  total_customers: number;
  total_conversations: number;
  total_messages: number;
  total_tickets: number;
  tickets_by_status: Record<string, number>;
  tickets_by_priority: Record<string, number>;
  escalated_tickets: number;
  ai_resolved: number;
  avg_response_time_ms?: number;
  recent_messages: RecentMessage[];
}

export interface ToolTraceEntry {
  tool: string;
  args: Record<string, unknown>;
  ts_ms: number;
}

export interface TicketInfo {
  id: string;
  subject: string;
  status: string;
  priority: string;
  escalated: boolean;
  escalation_reason?: string;
}

export interface DemoProcessResponse {
  pipeline_stages: string[];
  processing_time_ms: number;
  customer_id: string;
  conversation_id: string;
  message_id: string;
  is_new_customer: boolean;
  ai_response: string;
  tool_trace: ToolTraceEntry[];
  model_used: string;
  tokens_input: number;
  tokens_output: number;
  ticket?: TicketInfo;
  escalated: boolean;
  escalation_category?: string;
}

export interface DemoProcessRequest {
  name: string;
  email: string;
  company?: string;
  subject: string;
  message: string;
}

export interface SeedResponse {
  message: string;
  kb_articles_created: number;
  sample_customers_created: number;
}
