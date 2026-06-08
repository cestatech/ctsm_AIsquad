"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { intakeApi } from "@/lib/api/intake";
import { studiesApi } from "@/lib/api/studies";
import { generationApi } from "@/lib/api/generation";
import { INTAKE_DOMAINS, type ArtifactType, type IntakeDomain, type SponsorIntake, type StudyBrief } from "@/types";
import { ApiClientError } from "@/lib/api/client";

const DOMAIN_LABELS: Record<IntakeDomain, string> = Object.fromEntries(
  INTAKE_DOMAINS.map((d) => [d.key, d.label])
) as Record<IntakeDomain, string>;

function DomainProgress({ domainsCompleted }: { domainsCompleted: IntakeDomain[] }) {
  const completedSet = new Set(domainsCompleted);
  return (
    <div className="space-y-1">
      {INTAKE_DOMAINS.map(({ key, label }) => {
        const done = completedSet.has(key);
        return (
          <div
            key={key}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-sm text-xs ${
              done ? "text-emerald-700 bg-emerald-50" : "text-slate-500"
            }`}
          >
            <div
              className={`w-4 h-4 flex-shrink-0 border flex items-center justify-center rounded-sm ${
                done ? "border-emerald-500 bg-emerald-500" : "border-slate-300"
              }`}
            >
              {done && (
                <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                </svg>
              )}
            </div>
            <span className={done ? "font-medium" : ""}>{label}</span>
          </div>
        );
      })}
    </div>
  );
}

function BriefSection({ title, data }: { title: string; data: Record<string, unknown> }) {
  return (
    <div>
      <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">{title}</h4>
      <div className="space-y-1">
        {Object.entries(data).map(([k, v]) => {
          if (v === null || v === undefined) return null;
          const display = Array.isArray(v) ? (v as string[]).join(", ") || "—" : String(v);
          return (
            <div key={k} className="flex gap-2 text-xs">
              <span className="text-slate-500 capitalize min-w-[140px]">{k.replace(/_/g, " ")}</span>
              <span className="text-slate-800 font-medium">{display}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function IntakePage() {
  const params = useParams<{ id: string }>();
  const studyId = params.id;
  const router = useRouter();
  const { token } = useAuthStore();
  const queryClient = useQueryClient();
  const bottomRef = useRef<HTMLDivElement>(null);

  const [activeIntake, setActiveIntake] = useState<SponsorIntake | null>(null);
  const [input, setInput] = useState("");
  const [brief, setBrief] = useState<StudyBrief | null>(null);
  const [briefOpen, setBriefOpen] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [genError, setGenError] = useState<string | null>(null);
  const [genSuccess, setGenSuccess] = useState<string | null>(null);

  const { data: study } = useQuery({
    queryKey: ["study", studyId, token],
    queryFn: () => studiesApi.get(studyId, token!),
    enabled: !!token,
  });

  const { data: existingIntakes } = useQuery({
    queryKey: ["intakes", studyId, token],
    queryFn: () => intakeApi.list(studyId, token!),
    enabled: !!token,
  });

  // Resume in-progress session, or load the latest compiled session on return visits
  useEffect(() => {
    if (!existingIntakes?.length) return;
    if (activeIntake) return;
    const inProgress = existingIntakes.find((i) => i.status !== "COMPILED");
    setActiveIntake(inProgress ?? existingIntakes[0]);
  }, [existingIntakes, activeIntake]);

  // Load compiled brief when revisiting a completed intake
  useEffect(() => {
    if (!activeIntake || activeIntake.status !== "COMPILED" || brief || !token) return;
    intakeApi.getBrief(activeIntake.id, token).then(setBrief).catch(() => null);
  }, [activeIntake, brief, token]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeIntake?.messages.length]);

  const startMutation = useMutation({
    mutationFn: () => intakeApi.start(studyId, token!),
    onSuccess: (data) => {
      setActiveIntake(data.intake);
      setStartError(null);
      queryClient.invalidateQueries({ queryKey: ["intakes", studyId] });
    },
    onError: async (err) => {
      if (err instanceof ApiClientError && err.error.code === "INTAKE_EXISTS") {
        const sessions = await intakeApi.list(studyId, token!);
        const active = sessions.find((i) => i.status !== "COMPILED");
        if (active) setActiveIntake(active);
        setStartError(null);
      } else if (err instanceof ApiClientError) {
        const detail = err.error.detail;
        setStartError(
          typeof detail === "string"
            ? detail
            : "Failed to start intake session. Please try again."
        );
      } else {
        setStartError("Failed to start intake session. Please try again.");
      }
    },
  });

  const respondMutation = useMutation({
    mutationFn: (message: string) => intakeApi.respond(activeIntake!.id, message, token!),
    onSuccess: (data) => {
      setActiveIntake(data);
      setInput("");
    },
  });

  const compileMutation = useMutation({
    mutationFn: () => intakeApi.compileBrief(activeIntake!.id, token!),
    onSuccess: async (data) => {
      setBrief(data);
      setBriefOpen(true);
      const refreshed = await intakeApi.get(activeIntake!.id, token!);
      setActiveIntake(refreshed);
      queryClient.invalidateQueries({ queryKey: ["intakes", studyId] });
    },
  });

  const generateMutation = useMutation({
    mutationFn: (artifactType: ArtifactType) =>
      generationApi.generateFromBrief({ brief_id: brief!.id, artifact_type: artifactType }, token!),
    onSuccess: (job) => {
      setGenError(null);
      setGenSuccess(`${job.artifact_type} generation started (job ${job.id.slice(0, 8)}…). View progress in the Generation tab.`);
      queryClient.invalidateQueries({ queryKey: ["generation-jobs", studyId] });
    },
    onError: (err) => {
      setGenError(err instanceof Error ? err.message : "Generation failed.");
      setGenSuccess(null);
    },
  });

  function handleSend() {
    const trimmed = input.trim();
    if (!trimmed || respondMutation.isPending) return;
    respondMutation.mutate(trimmed);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  const progress =
    activeIntake ? Math.round((activeIntake.domains_completed.length / 9) * 100) : 0;
  const isReady = activeIntake?.ready_to_compile ?? false;
  const isCompiled = activeIntake?.status === "COMPILED";

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      {/* Left sidebar — study info + domain progress */}
      <div className="w-72 flex-shrink-0 bg-white border-r border-slate-200 flex flex-col">
        <div className="px-5 py-4 border-b border-slate-100">
          <Link
            href={`/studies/${studyId}`}
            className="text-xs text-brand-600 hover:text-brand-700 flex items-center gap-1 mb-3"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back to study
          </Link>
          <h1 className="text-sm font-semibold text-slate-900 font-display leading-tight">
            {study?.name ?? "Loading…"}
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">Sponsor Intake</p>
        </div>

        <div className="px-5 py-4 border-b border-slate-100">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-slate-600">Domains covered</span>
            <span className="text-xs font-semibold text-brand-600">
              {activeIntake?.domains_completed.length ?? 0}/9
            </span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-1.5">
            <div
              className="bg-brand-500 h-1.5 rounded-full transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-4">
          {activeIntake ? (
            <DomainProgress domainsCompleted={activeIntake.domains_completed} />
          ) : (
            <p className="text-xs text-slate-400 text-center mt-8">
              Start an intake session to begin.
            </p>
          )}
        </div>

        {isReady && !isCompiled && (
          <div className="px-4 py-4 border-t border-slate-100">
            <button
              onClick={() => compileMutation.mutate()}
              disabled={compileMutation.isPending}
              className="w-full bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-xs font-semibold py-2.5 px-4 rounded-sm transition-colors"
            >
              {compileMutation.isPending ? "Compiling…" : "Compile Study Brief"}
            </button>
            <p className="text-[10px] text-slate-400 mt-2 text-center">
              All domains covered. Ready to generate the Study Brief.
            </p>
          </div>
        )}

        {isCompiled && (
          <div className="px-4 py-4 border-t border-slate-100 space-y-2">
            <button
              onClick={() => {
                if (brief) {
                  setBriefOpen(true);
                } else {
                  intakeApi.getBrief(activeIntake!.id, token!).then(setBrief).then(() => setBriefOpen(true));
                }
              }}
              className="w-full bg-brand-600 hover:bg-brand-700 text-white text-xs font-semibold py-2.5 px-4 rounded-sm transition-colors"
            >
              View Study Brief
            </button>
            {brief && (
              <>
                <button
                  onClick={() => generateMutation.mutate("PROTOCOL")}
                  disabled={generateMutation.isPending}
                  className="w-full bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-xs font-semibold py-2 px-4 rounded-sm transition-colors"
                >
                  {generateMutation.isPending && generateMutation.variables === "PROTOCOL"
                    ? "Starting…"
                    : "Generate Protocol"}
                </button>
                <button
                  onClick={() => generateMutation.mutate("ICF")}
                  disabled={generateMutation.isPending}
                  className="w-full bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-xs font-semibold py-2 px-4 rounded-sm transition-colors"
                >
                  {generateMutation.isPending && generateMutation.variables === "ICF"
                    ? "Starting…"
                    : "Generate ICF"}
                </button>
                <Link
                  href={`/studies/${studyId}/generation`}
                  className="block text-center text-[10px] text-brand-600 hover:text-brand-700 font-medium"
                >
                  View generation jobs →
                </Link>
              </>
            )}
          </div>
        )}
      </div>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between flex-shrink-0">
          <div>
            <h2 className="text-sm font-semibold text-slate-900 font-display">AI Intake Specialist</h2>
            <p className="text-xs text-slate-500">
              {activeIntake
                ? isCompiled
                  ? "Intake complete — Study Brief compiled"
                  : isReady
                  ? "All domains covered — ready to compile"
                  : "Gathering study information…"
                : "Start a session to begin the intake process"}
            </p>
          </div>
          {!activeIntake && (
            <button
              onClick={() => startMutation.mutate()}
              disabled={startMutation.isPending}
              className="bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white text-xs font-semibold py-2 px-4 rounded-sm transition-colors"
            >
              {startMutation.isPending ? "Starting…" : "Start Intake"}
            </button>
          )}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
          {startError && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-xs px-4 py-3 rounded-sm">
              {startError}
            </div>
          )}

          {!activeIntake && !startMutation.isPending && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-12 h-12 bg-brand-100 rounded-full flex items-center justify-center mb-4">
                <svg className="w-6 h-6 text-brand-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                  />
                </svg>
              </div>
              <h3 className="text-sm font-semibold text-slate-900 mb-1">Start Sponsor Intake</h3>
              <p className="text-xs text-slate-500 max-w-xs leading-relaxed">
                The AI will guide you through 9 clinical domains to gather all information
                needed to generate the Protocol, ICF, SAP, and CSR.
              </p>
            </div>
          )}

          {activeIntake?.messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[75%] px-4 py-3 rounded-lg text-sm leading-relaxed ${
                  msg.role === "user"
                    ? "bg-brand-600 text-white"
                    : "bg-white border border-slate-200 text-slate-800 shadow-sm"
                }`}
              >
                {msg.domain && msg.role === "assistant" && (
                  <div className="text-[10px] font-semibold uppercase tracking-wider mb-1.5 opacity-60">
                    {DOMAIN_LABELS[msg.domain as IntakeDomain] ?? msg.domain}
                  </div>
                )}
                <p className="whitespace-pre-wrap">{msg.content}</p>
                <p
                  className={`text-[10px] mt-1.5 opacity-50 ${
                    msg.role === "user" ? "text-right" : ""
                  }`}
                >
                  {new Date(msg.created_at).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </p>
              </div>
            </div>
          ))}

          {(respondMutation.isPending || compileMutation.isPending) && (
            <div className="flex justify-start">
              <div className="bg-white border border-slate-200 shadow-sm px-4 py-3 rounded-lg">
                <div className="flex gap-1">
                  <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input */}
        {activeIntake && !isCompiled && (
          <div className="bg-white border-t border-slate-200 px-6 py-4 flex-shrink-0">
            <div className="flex gap-3">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type your response… (Enter to send, Shift+Enter for new line)"
                rows={2}
                disabled={respondMutation.isPending}
                className="flex-1 resize-none border border-slate-200 rounded-sm px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 disabled:opacity-50"
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || respondMutation.isPending}
                className="bg-brand-600 hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium px-4 rounded-sm transition-colors flex-shrink-0"
              >
                Send
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Study Brief modal */}
      {briefOpen && brief && (
        <div
          className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
          onClick={() => setBriefOpen(false)}
        >
          <div
            className="bg-white rounded-lg shadow-2xl w-full max-w-3xl max-h-[85vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <h2 className="text-base font-semibold text-slate-900 font-display">Study Brief</h2>
              <button
                onClick={() => setBriefOpen(false)}
                className="text-slate-400 hover:text-slate-600 transition-colors"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
              {Object.entries(brief.content).map(([section, data]) => {
                if (!data || typeof data !== "object") return null;
                return (
                  <BriefSection
                    key={section}
                    title={section.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                    data={data as Record<string, unknown>}
                  />
                );
              })}
            </div>

            <div className="px-6 py-4 border-t border-slate-100 space-y-3">
              {genError && (
                <div className="bg-red-50 border border-red-200 text-red-700 text-xs px-3 py-2">{genError}</div>
              )}
              {genSuccess && (
                <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs px-3 py-2">{genSuccess}</div>
              )}
              <div className="flex items-center justify-between gap-3">
                <div className="flex gap-2">
                  <button
                    onClick={() => generateMutation.mutate("PROTOCOL")}
                    disabled={generateMutation.isPending}
                    className="bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white text-xs font-semibold px-4 py-2 rounded-sm transition-colors"
                  >
                    {generateMutation.isPending && generateMutation.variables === "PROTOCOL" ? "Starting…" : "Generate Protocol"}
                  </button>
                  <button
                    onClick={() => generateMutation.mutate("ICF")}
                    disabled={generateMutation.isPending}
                    className="bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white text-xs font-semibold px-4 py-2 rounded-sm transition-colors"
                  >
                    {generateMutation.isPending && generateMutation.variables === "ICF" ? "Starting…" : "Generate ICF"}
                  </button>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(JSON.stringify(brief.content, null, 2));
                    }}
                    className="text-xs text-slate-600 hover:text-slate-900 border border-slate-200 hover:border-slate-300 px-4 py-2 rounded-sm transition-colors"
                  >
                    Copy JSON
                  </button>
                  <button
                    onClick={() => { setBriefOpen(false); setGenError(null); setGenSuccess(null); }}
                    className="text-xs text-slate-600 hover:text-slate-900 border border-slate-200 hover:border-slate-300 px-4 py-2 rounded-sm transition-colors"
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
