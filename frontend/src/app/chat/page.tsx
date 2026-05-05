"use client";

import { useState } from "react";
import {
  Send,
  Bot,
  CheckCircle2,
  Loader2,
  Wrench,
  Ticket,
  AlertTriangle,
  User,
  Building,
  Mail,
  FileText,
  Plane,
  Sparkles,
  Zap,
} from "lucide-react";
import { processMessage } from "@/lib/api";
import type { DemoProcessResponse, DemoProcessRequest } from "@/lib/types";

const PIPELINE_LABELS: Record<string, { label: string; desc: string }> = {
  customer_resolution: {
    label: "Customer Lookup",
    desc: "Identifying customer profile",
  },
  conversation_created: {
    label: "Conversation Created",
    desc: "Opening new support thread",
  },
  message_stored: {
    label: "Message Stored",
    desc: "Recording in database",
  },
  kafka_queued: {
    label: "Queue Dispatched",
    desc: "Routing to AI processor",
  },
  agent_processing: {
    label: "AI Agent Processing",
    desc: "Analyzing and generating response",
  },
  response_generated: {
    label: "Response Generated",
    desc: "Complete - ready to deliver",
  },
};

export default function ChatPage() {
  const [form, setForm] = useState<DemoProcessRequest>({
    name: "",
    email: "",
    company: "",
    subject: "",
    message: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<DemoProcessResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentStage, setCurrentStage] = useState(0);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setResult(null);
    setCurrentStage(0);

    const stageInterval = setInterval(() => {
      setCurrentStage((prev) => Math.min(prev + 1, 5));
    }, 400);

    try {
      const data = await processMessage(form);
      clearInterval(stageInterval);
      setCurrentStage(data.pipeline_stages.length);
      setResult(data);
    } catch (e) {
      clearInterval(stageInterval);
      setError(e instanceof Error ? e.message : "Failed to process message");
    } finally {
      setSubmitting(false);
    }
  };

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  return (
    <div className="max-w-6xl space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">Live Support</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Submit a customer inquiry and watch the AI support pipeline process it
          in real-time
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
        {/* Form - 2 cols */}
        <div className="lg:col-span-2">
          <div className="bg-card border border-border rounded-2xl overflow-hidden shadow-sm">
            <div className="bg-gradient-to-r from-[#0c4a6e] to-[#1e3a5f] px-6 py-4">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-white/10 flex items-center justify-center">
                  <Plane className="w-5 h-5 text-amber-400" />
                </div>
                <div>
                  <h2 className="text-sm font-semibold text-white">
                    Customer Support Form
                  </h2>
                  <p className="text-[11px] text-sky-300/70">
                    Shaheen Airline Help Desk
                  </p>
                </div>
              </div>
            </div>
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                    <User className="w-3 h-3" />
                    Full Name
                  </label>
                  <input
                    name="name"
                    value={form.name}
                    onChange={handleChange}
                    required
                    placeholder="Ahmed Khan"
                    className="w-full px-3.5 py-2.5 bg-muted/40 border border-border rounded-xl text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent/50 transition"
                  />
                </div>
                <div>
                  <label className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                    <Mail className="w-3 h-3" />
                    Email
                  </label>
                  <input
                    name="email"
                    type="email"
                    value={form.email}
                    onChange={handleChange}
                    required
                    placeholder="ahmed@email.com"
                    className="w-full px-3.5 py-2.5 bg-muted/40 border border-border rounded-xl text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent/50 transition"
                  />
                </div>
              </div>
              <div>
                <label className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                  <Building className="w-3 h-3" />
                  Company (Optional)
                </label>
                <input
                  name="company"
                  value={form.company}
                  onChange={handleChange}
                  placeholder="Your organization"
                  className="w-full px-3.5 py-2.5 bg-muted/40 border border-border rounded-xl text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent/50 transition"
                />
              </div>
              <div>
                <label className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                  <FileText className="w-3 h-3" />
                  Subject
                </label>
                <input
                  name="subject"
                  value={form.subject}
                  onChange={handleChange}
                  required
                  placeholder="e.g. Flight cancellation refund"
                  className="w-full px-3.5 py-2.5 bg-muted/40 border border-border rounded-xl text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent/50 transition"
                />
              </div>
              <div>
                <label className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                  <Sparkles className="w-3 h-3" />
                  Message
                </label>
                <textarea
                  name="message"
                  value={form.message}
                  onChange={handleChange}
                  required
                  rows={5}
                  placeholder="Please describe your issue or inquiry in detail..."
                  className="w-full px-3.5 py-2.5 bg-muted/40 border border-border rounded-xl text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent/50 transition resize-none"
                />
              </div>
              <button
                type="submit"
                disabled={submitting}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-[#0c4a6e] to-[#1e40af] text-white rounded-xl font-semibold hover:shadow-lg hover:shadow-accent/20 transition-all disabled:opacity-50 text-sm"
              >
                {submitting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Processing Request...
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    Submit Support Request
                  </>
                )}
              </button>
            </form>
          </div>
        </div>

        {/* Results Panel - 3 cols */}
        <div className="lg:col-span-3 space-y-6">
          {/* Pipeline Animation */}
          {(submitting || result) && (
            <div className="bg-card border border-border rounded-2xl p-6 shadow-sm animate-fade-in-up">
              <div className="flex items-center justify-between mb-5">
                <h2 className="text-base font-semibold flex items-center gap-2">
                  <Zap className="w-4 h-4 text-amber-500" />
                  Processing Pipeline
                </h2>
                {result && (
                  <span className="text-xs font-medium text-emerald-600 bg-emerald-50 px-2.5 py-1 rounded-lg ring-1 ring-emerald-200">
                    Completed in {result.processing_time_ms}ms
                  </span>
                )}
              </div>
              <div className="space-y-2">
                {Object.entries(PIPELINE_LABELS).map(
                  ([key, { label, desc }], i) => {
                    const completed = i < currentStage;
                    const active = i === currentStage && submitting;
                    return (
                      <div
                        key={key}
                        className={`flex items-center gap-4 px-4 py-3 rounded-xl transition-all duration-300 ${
                          completed
                            ? "bg-emerald-50 ring-1 ring-emerald-200"
                            : active
                            ? "bg-sky-50 ring-1 ring-sky-200"
                            : "bg-muted/30"
                        }`}
                      >
                        {completed ? (
                          <CheckCircle2 className="w-5 h-5 text-emerald-500 flex-shrink-0" />
                        ) : active ? (
                          <Loader2 className="w-5 h-5 text-accent animate-spin flex-shrink-0" />
                        ) : (
                          <div className="w-5 h-5 rounded-full border-2 border-border flex-shrink-0" />
                        )}
                        <div className="flex-1 min-w-0">
                          <span
                            className={`text-sm font-medium ${
                              completed
                                ? "text-emerald-700"
                                : active
                                ? "text-accent"
                                : "text-muted-foreground"
                            }`}
                          >
                            {label}
                          </span>
                          <p
                            className={`text-[11px] ${
                              completed
                                ? "text-emerald-600/60"
                                : active
                                ? "text-sky-600/60"
                                : "text-muted-foreground/50"
                            }`}
                          >
                            {desc}
                          </p>
                        </div>
                        {completed && (
                          <span className="text-[10px] font-medium text-emerald-600">
                            Done
                          </span>
                        )}
                      </div>
                    );
                  }
                )}
              </div>
              {result && (
                <p className="text-xs text-muted-foreground mt-4 flex items-center gap-1.5">
                  <Bot className="w-3.5 h-3.5" />
                  Model: {result.model_used} | Tokens:{" "}
                  {result.tokens_input + result.tokens_output}
                </p>
              )}
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-2xl p-5 animate-fade-in-up">
              <div className="flex items-start gap-3">
                <div className="w-9 h-9 rounded-xl bg-red-100 flex items-center justify-center flex-shrink-0">
                  <AlertTriangle className="w-5 h-5 text-danger" />
                </div>
                <div>
                  <p className="text-danger text-sm font-semibold">
                    Processing Failed
                  </p>
                  <p className="text-red-600/70 text-xs mt-1 leading-relaxed whitespace-pre-wrap">
                    {error}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* AI Response */}
          {result && (
            <>
              <div className="bg-card border border-border rounded-2xl overflow-hidden shadow-sm animate-fade-in-up">
                <div className="px-6 py-4 border-b border-border flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-sky-100 to-blue-50 flex items-center justify-center">
                    <Bot className="w-5 h-5 text-accent" />
                  </div>
                  <div>
                    <h2 className="text-sm font-semibold text-foreground">
                      AI Response
                    </h2>
                    <p className="text-[11px] text-muted-foreground">
                      Shaheen Airline Support Agent
                    </p>
                  </div>
                  {result.is_new_customer && (
                    <span className="ml-auto text-xs font-medium text-sky-600 bg-sky-50 px-2.5 py-1 rounded-lg ring-1 ring-sky-200">
                      New Customer
                    </span>
                  )}
                </div>
                <div className="p-6">
                  <div className="bg-muted/30 rounded-xl p-5 text-sm leading-relaxed whitespace-pre-wrap text-foreground border border-border/50">
                    {result.ai_response}
                  </div>
                </div>
              </div>

              {/* Tool Trace */}
              {result.tool_trace.length > 0 && (
                <div className="bg-card border border-border rounded-2xl p-6 shadow-sm animate-fade-in-up">
                  <h2 className="text-sm font-semibold mb-4 flex items-center gap-2">
                    <Wrench className="w-4 h-4 text-amber-500" />
                    Tool Execution Trace
                  </h2>
                  <div className="space-y-2">
                    {result.tool_trace.map((t, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-3 px-4 py-2.5 bg-muted/30 rounded-xl border border-border/50"
                      >
                        <span className="text-[10px] font-bold text-accent bg-accent/5 px-2 py-1 rounded-lg ring-1 ring-accent/10 font-mono flex-shrink-0 uppercase tracking-wider">
                          {t.tool}
                        </span>
                        <span className="text-xs text-muted-foreground font-mono break-all leading-relaxed">
                          {JSON.stringify(t.args)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Ticket Info */}
              {result.ticket && (
                <div className="bg-card border border-border rounded-2xl overflow-hidden shadow-sm animate-fade-in-up">
                  <div className="px-6 py-4 border-b border-border flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-violet-50 flex items-center justify-center">
                      <Ticket className="w-5 h-5 text-violet-600" />
                    </div>
                    <div>
                      <h2 className="text-sm font-semibold text-foreground">
                        Ticket Created
                      </h2>
                      <p className="text-[11px] text-muted-foreground font-mono">
                        {result.ticket.id.slice(0, 8)}...
                      </p>
                    </div>
                  </div>
                  <div className="p-6">
                    <div className="grid grid-cols-2 gap-4">
                      {[
                        { label: "Subject", value: result.ticket.subject },
                        {
                          label: "Status",
                          value: result.ticket.status.replace(/_/g, " "),
                          capitalize: true,
                        },
                        {
                          label: "Priority",
                          value: result.ticket.priority,
                          capitalize: true,
                        },
                        {
                          label: "Escalated",
                          value: result.ticket.escalated ? "Yes" : "No",
                        },
                      ].map((item) => (
                        <div key={item.label} className="bg-muted/30 rounded-xl p-3.5">
                          <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider mb-1">
                            {item.label}
                          </p>
                          <p
                            className={`text-sm font-semibold text-foreground ${
                              item.capitalize ? "capitalize" : ""
                            }`}
                          >
                            {item.value}
                          </p>
                        </div>
                      ))}
                    </div>
                    {result.escalated && result.escalation_category && (
                      <div className="mt-4 px-4 py-3 bg-red-50 rounded-xl ring-1 ring-red-200">
                        <p className="text-sm text-red-700 font-medium flex items-center gap-2">
                          <AlertTriangle className="w-4 h-4" />
                          Escalated:{" "}
                          {result.escalation_category.replace(/_/g, " ")}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}

          {/* Empty state */}
          {!submitting && !result && !error && (
            <div className="flex flex-col items-center justify-center py-20 bg-card border border-border rounded-2xl">
              <div className="w-20 h-20 rounded-3xl bg-gradient-to-br from-sky-50 to-blue-50 flex items-center justify-center mb-5 shadow-sm">
                <Plane className="w-10 h-10 text-accent" />
              </div>
              <h3 className="text-lg font-semibold text-foreground">
                Ready to Assist
              </h3>
              <p className="text-muted-foreground text-sm mt-2 max-w-sm text-center">
                Fill out the support form to submit a customer inquiry. Our AI
                agent will process it instantly and provide a response.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
