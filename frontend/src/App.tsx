import { useEffect, useRef, useState, useCallback } from "react";
import Editor from "@monaco-editor/react";
import { Room, Track } from "livekit-client";
import {
  ArrowRight, CheckCircle2, ChevronRight, Clock3,
  Code2, Eye, EyeOff, FileText, Mic, Play, ShieldCheck,
  Sparkles, Target, UserRound, AlertTriangle,
  Star, Copy, Check, Radio,
} from "lucide-react";
import "./App.css";

// ──────────────────────────────────────────────────────────────────
// TYPES
// ──────────────────────────────────────────────────────────────────

type Screen = "home" | "interview" | "results" | "linkedin" | "cv-rater";

type Question = {
  id: number;
  category: string;
  competency: string;
  question: string;
  why: string;
  language?: string | null;
  starter_code?: string | null;
  difficulty?: string | null;
};

type Analysis = {
  overall_score: number;
  technical_score: number;
  communication_score: number;
  jd_alignment_score: number;
  strengths: string[];
  weaknesses: string[];
  technical_gaps: string[];
  communication_gaps: string[];
  improvement_plan: string[];
  summary: string;
  recommendation: string;
  code_performance?: {
    attempted: number;
    passed: number;
    average_score: number;
    notes: string;
  };
  integrity?: {
    flagged_for_review: boolean;
    flag_count: number;
    flags: IntegrityFlag[];
    notes: string;
  };
};

type CodeSubmission = {
  question_id: number;
  question: string;
  language: string;
  code: string;
  stdout: string;
  stderr: string;
  competency: string;
  evaluation?: Record<string, unknown>;
};

type IntegrityFlag = {
  type: string;
  timestamp: string;
  duration: number;
  details: string;
};

type SpeechResult = {
  0: { transcript: string };
  isFinal: boolean;
  length: number;
};

type SpeechRecognitionEventLike = Event & {
  resultIndex: number;
  results: { [index: number]: SpeechResult; length: number };
};

type SpeechRecognitionInstance = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onstart: (() => void) | null;
  onend: (() => void) | null;
  onerror: ((event: unknown) => void) | null;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
};

type SpeechRecognitionConstructor = new () => SpeechRecognitionInstance;

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  }
}

const ROLE_OPTIONS = [
  "Software Engineer",
  "Backend Engineer",
  "Frontend Engineer",
  "Full Stack Engineer",
  "Data Engineer",
  "ML Engineer / AI Engineer",
  "DevOps Engineer",
  "Data Scientist",
  "Product Manager",
  "Data Analyst",
  "Business Analyst",
  "Marketing Manager",
  "UX Designer",
  "Security Engineer",
  "Cloud Engineer",
  "Other (type your own)",
];

// ──────────────────────────────────────────────────────────────────
// IN-BROWSER CODE EXECUTION (Pyodide + sandboxed iframe)
// ──────────────────────────────────────────────────────────────────

type PyodideInterface = {
  runPythonAsync: (code: string) => Promise<unknown>;
  setStdout: (opts: { batched: (s: string) => void }) => void;
  setStderr: (opts: { batched: (s: string) => void }) => void;
};

let _pyodideInstance: PyodideInterface | null = null;
let _pyodideLoading = false;

async function loadPyodide(): Promise<PyodideInterface> {
  if (_pyodideInstance) return _pyodideInstance;
  if (_pyodideLoading) {
    // Wait for in-flight load
    while (_pyodideLoading) await new Promise((r) => setTimeout(r, 100));
    return _pyodideInstance!;
  }
  _pyodideLoading = true;
  // Load the Pyodide script from CDN
  await new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://cdn.jsdelivr.net/pyodide/v0.27.5/full/pyodide.js";
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Failed to load Pyodide"));
    document.head.appendChild(script);
  });
  const loader = (window as unknown as Record<string, unknown>).loadPyodide as
    ((opts?: Record<string, unknown>) => Promise<PyodideInterface>) | undefined;
  if (!loader) throw new Error("Pyodide loader not available");
  _pyodideInstance = await loader({ indexURL: "https://cdn.jsdelivr.net/pyodide/v0.27.5/full/" });
  _pyodideLoading = false;
  return _pyodideInstance;
}

async function runPythonLocally(code: string): Promise<{ stdout: string; stderr: string; exitCode: number }> {
  const pyodide = await loadPyodide();
  let stdout = "";
  let stderr = "";
  pyodide.setStdout({ batched: (s: string) => { stdout += s + "\n"; } });
  pyodide.setStderr({ batched: (s: string) => { stderr += s + "\n"; } });
  try {
    await pyodide.runPythonAsync(code);
    return { stdout: stdout.trimEnd(), stderr: stderr.trimEnd(), exitCode: 0 };
  } catch (e: unknown) {
    const errMsg = (e as Error).message ?? String(e);
    return { stdout: stdout.trimEnd(), stderr: errMsg, exitCode: 1 };
  }
}

function runJsInIframe(code: string): Promise<{ stdout: string; stderr: string; exitCode: number }> {
  return new Promise((resolve) => {
    const iframe = document.createElement("iframe");
    iframe.sandbox.add("allow-scripts");
    iframe.style.display = "none";
    let stdout = "";
    let stderr = "";

    const timeout = setTimeout(() => {
      cleanup();
      resolve({ stdout, stderr: stderr + "\nExecution timed out (5s limit).", exitCode: 1 });
    }, 5000);

    const onMessage = (event: MessageEvent) => {
      if (event.source !== iframe.contentWindow) return;
      const data = event.data as { type?: string; text?: string };
      if (data?.type === "stdout") stdout += data.text + "\n";
      if (data?.type === "stderr") stderr += data.text + "\n";
      if (data?.type === "done") {
        clearTimeout(timeout);
        cleanup();
        resolve({ stdout: stdout.trimEnd(), stderr: stderr.trimEnd(), exitCode: data.text ? 1 : 0 });
      }
    };

    const cleanup = () => {
      window.removeEventListener("message", onMessage);
      if (iframe.parentNode) iframe.parentNode.removeChild(iframe);
    };

    window.addEventListener("message", onMessage);

    const wrappedCode = `
<script>
  const _logs = [];
  const _errs = [];
  const origLog = console.log;
  console.log = function(...args) { _logs.push(args.map(String).join(' ')); parent.postMessage({type:'stdout',text:args.map(String).join(' ')}, '*'); };
  console.error = function(...args) { _errs.push(args.map(String).join(' ')); parent.postMessage({type:'stderr',text:args.map(String).join(' ')}, '*'); };
  try {
    ${code}
    parent.postMessage({type:'done',text:''}, '*');
  } catch(e) {
    parent.postMessage({type:'stderr',text:String(e)}, '*');
    parent.postMessage({type:'done',text:'error'}, '*');
  }
</script>`;

    iframe.srcdoc = wrappedCode;
    document.body.appendChild(iframe);
  });
}

async function runCodeLocally(
  language: string,
  code: string
): Promise<{ stdout: string; stderr: string; exitCode: number }> {
  const lang = language.toLowerCase();
  if (lang === "python") {
    return runPythonLocally(code);
  }
  if (lang === "javascript" || lang === "typescript" || lang === "js" || lang === "ts") {
    return runJsInIframe(code);
  }
  // Unsupported language — no in-browser execution
  return { stdout: "", stderr: "In-browser execution not supported for this language. Code will be reviewed without execution.", exitCode: -1 };
}

// ──────────────────────────────────────────────────────────────────
// COPY BUTTON helper
// ──────────────────────────────────────────────────────────────────


function LinkedinIcon({ size = 24, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z" />
      <rect width="4" height="12" x="2" y="9" />
      <circle cx="4" cy="4" r="2" />
    </svg>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="copy-btn"
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }}
    >
      {copied ? <Check size={14} /> : <Copy size={14} />}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

// ──────────────────────────────────────────────────────────────────
// SCORE BADGE helper
// ──────────────────────────────────────────────────────────────────

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 75 ? "score-green" : score >= 50 ? "score-yellow" : "score-red";
  return <span className={`score-badge ${color}`}>{score}/100</span>;
}

// ──────────────────────────────────────────────────────────────────
// MAIN APP
// ──────────────────────────────────────────────────────────────────

function App() {
  const [screen, setScreen] = useState<Screen>("home");

  // ── Home / prepare state
  const [selectedRole, setSelectedRole] = useState("Software Engineer");
  const [customRole, setCustomRole] = useState("");
  const [jdText, setJdText] = useState("");
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [isPreparing, setIsPreparing] = useState(false);
  const [prepError, setPrepError] = useState("");
  const [prepDone, setPrepDone] = useState(false);
  const [resumeSummary, setResumeSummary] = useState<Record<string, unknown>>({});

  // ── Interview state
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [answer, setAnswer] = useState("");
  const [answers, setAnswers] = useState<string[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [timeLeft, setTimeLeft] = useState(30 * 60);

  // ── Code editor state
  const [codeMap, setCodeMap] = useState<Record<number, string>>({});
  const [runOutput, setRunOutput] = useState<{ stdout: string; stderr: string } | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [codeSubmissions, setCodeSubmissions] = useState<CodeSubmission[]>([]);

  // ── Proctoring state
  const [proctoringEnabled, setProctoringEnabled] = useState(false);
  const [cameraGranted, setCameraGranted] = useState(false);
  const [, setStrikeCount] = useState(0);
  const [integrityFlags, setIntegrityFlags] = useState<IntegrityFlag[]>([]);
  const [flaggedForReview, setFlaggedForReview] = useState(false);
  const [proctoringWarning, setProctoringWarning] = useState("");
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const proctoringIntervalRef = useRef<number | null>(null);
  const faceDetectorRef = useRef<unknown>(null);
  const tabHiddenAtRef = useRef<number | null>(null);
  const proctoringStatsRef = useRef({ total: 0, eyeContact: 0 });

  // ── Analysis state
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState("");

  // ── LinkedIn state
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [linkedinText, setLinkedinText] = useState("");
  const [linkedinLoading, setLinkedinLoading] = useState(false);
  const [linkedinResult, setLinkedinResult] = useState<Record<string, unknown> | null>(null);
  const [linkedinError, setLinkedinError] = useState("");

  // ── CV rater state
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [cvJdText, setCvJdText] = useState("");
  const [cvLoading, setCvLoading] = useState(false);
  const [cvResult, setCvResult] = useState<Record<string, unknown> | null>(null);
  const [cvError, setCvError] = useState("");

  // ── LiveKit state
  const [livekitConnected, setLivekitConnected] = useState(false);
  const livekitRoomRef = useRef<Room | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);

  // Speech refs (kept for live transcript display only)
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const finalTranscriptRef = useRef("");
  const answerRef = useRef("");

  const effectiveRole = selectedRole === "Other (type your own)" ? customRole : selectedRole;

  // ──────────────────────────────────────────────────────────────────
  // LOAD QUESTIONS
  // ──────────────────────────────────────────────────────────────────

  useEffect(() => {
    if (!prepDone) return;
    fetch("http://127.0.0.1:8000/api/questions")
      .then((r) => r.json())
      .then((data) => setQuestions(data.questions ?? []))
      .catch(console.error);
  }, [prepDone]);

  // ──────────────────────────────────────────────────────────────────
  // LOAD ANALYSIS ON RESULTS SCREEN
  // ──────────────────────────────────────────────────────────────────

  useEffect(() => {
    if (screen !== "results") return;
    if (analysis) return;
    setAnalysisLoading(true);
    setAnalysisError("");
    fetch("http://127.0.0.1:8000/api/analysis")
      .then((r) => r.json())
      .then((data) => setAnalysis(data))
      .catch(() => setAnalysisError("Unable to load analysis. Make sure the backend is running."))
      .finally(() => setAnalysisLoading(false));
  }, [screen]);

  // ──────────────────────────────────────────────────────────────────
  // TIMER
  // ──────────────────────────────────────────────────────────────────

  useEffect(() => {
    if (screen !== "interview") return;
    if (timeLeft <= 0) {
      stopRecording();
      alert("Your 30-minute interview time has ended.");
      setScreen("results");
      return;
    }
    const timer = window.setInterval(() => setTimeLeft((p) => p - 1), 1000);
    return () => window.clearInterval(timer);
  }, [screen, timeLeft]);

  // ──────────────────────────────────────────────────────────────────
  // QUESTION CHANGE (reset UI state — agent speaks questions via LiveKit)
  // ──────────────────────────────────────────────────────────────────

  useEffect(() => {
    if (screen !== "interview") return;
    const q = questions[currentQuestion];
    if (!q) return;
    setAnswer("");
    answerRef.current = "";
    finalTranscriptRef.current = "";
    setRunOutput(null);
  }, [screen, currentQuestion, questions]);

  // ──────────────────────────────────────────────────────────────────
  // TAB-SWITCH DETECTION
  // ──────────────────────────────────────────────────────────────────

  useEffect(() => {
    if (screen !== "interview") return;

    const handleVisibilityChange = () => {
      if (document.hidden) {
        tabHiddenAtRef.current = Date.now();
      } else if (tabHiddenAtRef.current) {
        const duration = (Date.now() - tabHiddenAtRef.current) / 1000;
        tabHiddenAtRef.current = null;
        addFlag("tab_switch", `Tab hidden for ${duration.toFixed(1)}s`, duration);
      }
    };

    const handleBlur = () => {
      if (!tabHiddenAtRef.current) tabHiddenAtRef.current = Date.now();
    };

    const handleFocus = () => {
      if (tabHiddenAtRef.current) {
        const duration = (Date.now() - tabHiddenAtRef.current) / 1000;
        tabHiddenAtRef.current = null;
        if (duration > 2) addFlag("window_blur", `Window out of focus for ${duration.toFixed(1)}s`, duration);
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("blur", handleBlur);
    window.addEventListener("focus", handleFocus);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("blur", handleBlur);
      window.removeEventListener("focus", handleFocus);
    };
  }, [screen]);

  // ──────────────────────────────────────────────────────────────────
  // INTEGRITY FLAG SYSTEM
  // ──────────────────────────────────────────────────────────────────

  const addFlag = useCallback((type: string, details: string, duration = 0) => {
    const flag: IntegrityFlag = {
      type,
      timestamp: new Date().toISOString(),
      duration,
      details,
    };

    setIntegrityFlags((prev) => {
      const updated = [...prev, flag];
      const recentStrikes = updated.filter((f) => {
        const age = (Date.now() - new Date(f.timestamp).getTime()) / 1000 / 60;
        return age < 10;
      }).length;

      if (recentStrikes >= 3) {
        setFlaggedForReview(true);
        setProctoringWarning("⚠️ Interview flagged for review due to repeated violations.");
      } else {
        setProctoringWarning(`⚠️ Warning: ${details} (Strike ${recentStrikes}/3)`);
        setTimeout(() => setProctoringWarning(""), 8000);
      }
      return updated;
    });

    setStrikeCount((p) => p + 1);
  }, []);

  // ──────────────────────────────────────────────────────────────────
  // WEBCAM PROCTORING (MediaPipe Tasks Vision)
  // ──────────────────────────────────────────────────────────────────

  const startProctoring = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      streamRef.current = stream;
      setCameraGranted(true);
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }

      // Dynamically import MediaPipe to avoid SSR issues
      const { FaceDetector, FilesetResolver } = await import("@mediapipe/tasks-vision");
      const vision = await FilesetResolver.forVisionTasks(
        "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.3/wasm"
      );
      const detector = await FaceDetector.createFromOptions(vision, {
        baseOptions: {
          modelAssetPath:
            "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite",
          delegate: "GPU",
        },
        runningMode: "IMAGE",
        minDetectionConfidence: 0.5,
      });
      faceDetectorRef.current = detector;

      let noFaceSince: number | null = null;

      proctoringIntervalRef.current = window.setInterval(() => {
        if (!canvasRef.current || !videoRef.current || !faceDetectorRef.current) return;
        const ctx = canvasRef.current.getContext("2d");
        if (!ctx) return;
        ctx.drawImage(videoRef.current, 0, 0, 160, 120);

          try {
          const detections = (faceDetectorRef.current as any).detect(videoRef.current);
          const faceCount = detections.detections.length;
          
          if (screen === "interview") {
            proctoringStatsRef.current.total++;
          }

          if (faceCount === 0) {
            if (!noFaceSince) noFaceSince = Date.now();
            else if (Date.now() - noFaceSince > 5000) {
              addFlag("no_face", "No face detected for more than 5 seconds", (Date.now() - noFaceSince) / 1000);
              noFaceSince = null;
            }
          } else {
            noFaceSince = null;
            if (faceCount > 1) {
              addFlag("multiple_faces", `${faceCount} faces detected`, 0);
            } else if (screen === "interview") {
              const keypoints = detections.detections[0].keypoints;
              if (keypoints && keypoints.length >= 3) {
                const rightEye = keypoints[0];
                const leftEye = keypoints[1];
                const nose = keypoints[2];
                const noseToLeft = Math.abs(leftEye.x - nose.x);
                const noseToRight = Math.abs(nose.x - rightEye.x);
                if (noseToLeft > 0 && noseToRight > 0) {
                  const ratio = Math.max(noseToLeft, noseToRight) / Math.min(noseToLeft, noseToRight);
                  if (ratio < 2.5) {
                    proctoringStatsRef.current.eyeContact++;
                  }
                }
              }
            }
          }
        } catch {
          // Detection error — silently continue
        }
      }, 1500);
    } catch {
      setCameraGranted(false);
      setProctoringWarning("Camera access denied — proctoring disabled.");
    }
  }, [addFlag]);

  const stopProctoring = useCallback(() => {
    if (proctoringIntervalRef.current) {
      clearInterval(proctoringIntervalRef.current);
      proctoringIntervalRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (screen !== "interview") {
      stopProctoring();
    }
  }, [screen, stopProctoring]);

  // ──────────────────────────────────────────────────────────────────
  // SPEECH RECOGNITION
  // ──────────────────────────────────────────────────────────────────

  const startRecording = () => {
    if (isRecording) return;
    const SR = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (!SR) { alert("Speech recognition not supported. Use Chrome."); return; }
    if (recognitionRef.current) { try { recognitionRef.current.abort(); } catch { /* ignore */ } }
    const recognition = new SR();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    finalTranscriptRef.current = answerRef.current.trim();
    recognition.onstart = () => setIsRecording(true);
    recognition.onresult = (event: SpeechRecognitionEventLike) => {
      let newFinal = "";
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (!result || result.length === 0) continue;
        const text = result[0]?.transcript?.trim() ?? "";
        if (!text) continue;
        if (result.isFinal) newFinal += (newFinal ? " " : "") + text;
        else interim += (interim ? " " : "") + text;
      }
      if (newFinal) finalTranscriptRef.current = `${finalTranscriptRef.current} ${newFinal}`.trim();
      const display = `${finalTranscriptRef.current} ${interim}`.trim();
      answerRef.current = display;
      setAnswer(display);
    };
    recognition.onerror = (event: unknown) => {
      const err = (event as { error?: string }).error;
      if (err === "not-allowed" || err === "permission-denied") {
        alert("Microphone permission denied.");
      }
      setIsRecording(false);
    };
    recognition.onend = () => {
      setIsRecording(false);
      if (recognitionRef.current === recognition) recognitionRef.current = null;
    };
    recognitionRef.current = recognition;
    try { recognition.start(); } catch { setIsRecording(false); recognitionRef.current = null; }
  };

  const stopRecording = () => {
    if (!recognitionRef.current) { setIsRecording(false); return; }
    try { recognitionRef.current.stop(); } catch { /* ignore */ }
    recognitionRef.current = null;
    setIsRecording(false);
  };

  // ──────────────────────────────────────────────────────────────────
  // PREPARE (call /api/prepare)
  // ──────────────────────────────────────────────────────────────────

  const handlePrepare = async () => {
    if (!resumeFile) { setPrepError("Please upload a resume PDF."); return; }
    if (!jdText.trim()) { setPrepError("Please paste the job description."); return; }
    if (!effectiveRole.trim()) { setPrepError("Please enter your role."); return; }

    setIsPreparing(true);
    setPrepError("");
    try {
      const form = new FormData();
      form.append("role", effectiveRole);
      form.append("jd_text", jdText);
      form.append("resume_file", resumeFile);

      const resp = await fetch("http://127.0.0.1:8000/api/prepare", {
        method: "POST",
        body: form,
      });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail ?? "Preparation failed");
      }
      const data = await resp.json();
      setResumeSummary(data.resume_summary ?? {});
      if (data.question_plan?.questions) {
        setQuestions(data.question_plan.questions);
      }
      setPrepDone(true);
    } catch (e: unknown) {
      setPrepError((e as Error).message ?? "Preparation failed. Check backend.");
    } finally {
      setIsPreparing(false);
    }
  };

  // ──────────────────────────────────────────────────────────────────
  // START INTERVIEW
  // ──────────────────────────────────────────────────────────────────

  const startInterview = async () => {
    if (questions.length === 0) { alert("Questions not loaded yet."); return; }
    stopRecording();
    setCurrentQuestion(0);
    setAnswer("");
    answerRef.current = "";
    setAnswers([]);
    setAnalysis(null);
    setAnalysisError("");
    setTimeLeft(30 * 60);
    finalTranscriptRef.current = "";
    setIntegrityFlags([]);
    setFlaggedForReview(false);
    setStrikeCount(0);
    setCodeSubmissions([]);
    setCodeMap({});
    setLivekitConnected(false);
    if (proctoringEnabled) startProctoring();
    setScreen("interview");

    // Connect to LiveKit room for real-time voice interview
    try {
      const candidateName = (resumeSummary as { name?: string }).name || "Candidate";
      const tokenResp = await fetch("http://127.0.0.1:8000/api/livekit-token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidate_name: candidateName }),
      });
      if (!tokenResp.ok) throw new Error("Failed to get LiveKit token");
      const { token, url } = await tokenResp.json();

      const room = new Room({
        adaptiveStream: true,
        dynacast: true,
      });

      // Subscribe to agent audio track for playback
      room.on("trackSubscribed", (track) => {
        if (track.kind === Track.Kind.Audio) {
          const el = audioRef.current;
          if (el) {
            track.attach(el);
            el.play().catch(() => { /* autoplay blocked */ });
          }
        }
      });

      room.on("trackUnsubscribed", (track) => {
        if (track.kind === Track.Kind.Audio) {
          track.detach().forEach((el) => el.remove());
        }
      });

      await room.connect(url, token);
      await room.localParticipant.setMicrophoneEnabled(true);
      livekitRoomRef.current = room;
      setLivekitConnected(true);
      console.log("Connected to LiveKit room:", room.name);

      // Also start browser SpeechRecognition in parallel for live transcript display
      startRecording();
    } catch (e: unknown) {
      console.error("LiveKit connection failed:", e);
      alert(`LiveKit connection failed: ${(e as Error).message}. The interview will continue without live voice.`);
    }
  };

  // ──────────────────────────────────────────────────────────────────
  // CODE: RUN + SUBMIT
  // ──────────────────────────────────────────────────────────────────

  const question = questions[currentQuestion];

  const handleRunCode = async () => {
    if (!question?.language) return;
    const code = codeMap[question.id] ?? question.starter_code ?? "";
    setIsRunning(true);
    setRunOutput(null);
    try {
      const result = await runCodeLocally(question.language, code);
      setRunOutput(result);
    } catch (e: unknown) {
      setRunOutput({ stdout: "", stderr: (e as Error).message });
    } finally {
      setIsRunning(false);
    }
  };

  const handleSubmitCode = async () => {
    if (!question) return;
    const code = codeMap[question.id] ?? question.starter_code ?? "";
    const lang = question.language ?? "python";
    const stdout = runOutput?.stdout ?? "";
    const stderr = runOutput?.stderr ?? "";

    let evaluation: Record<string, unknown> | undefined;
    try {
      const resp = await fetch("http://127.0.0.1:8000/api/evaluate-code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question_id: question.id,
          question: question.question,
          language: lang,
          code,
          stdout,
          stderr,
          competency: question.competency,
        }),
      });
      if (resp.ok) {
        const d = await resp.json();
        evaluation = d.evaluation;
      }
    } catch { /* non-blocking */ }

    const sub: CodeSubmission = {
      question_id: question.id,
      question: question.question,
      language: lang,
      code,
      stdout,
      stderr,
      competency: question.competency,
      evaluation,
    };
    setCodeSubmissions((prev) => [...prev.filter((s) => s.question_id !== question.id), sub]);
    alert("Code submitted!");
  };

  // ──────────────────────────────────────────────────────────────────
  // NEXT / FINISH QUESTION
  // ──────────────────────────────────────────────────────────────────

  const nextQuestion = async () => {
    const latestAnswer = answerRef.current || answer;
    stopRecording();
    const updated = [...answers];
    updated[currentQuestion] = latestAnswer;
    setAnswers(updated);

    if (currentQuestion < questions.length - 1) {
      const next = currentQuestion + 1;
      setCurrentQuestion(next);
      const na = updated[next] ?? "";
      setAnswer(na);
      answerRef.current = na;
      finalTranscriptRef.current = na;
      // Re-start speech recognition for the new question (LiveKit audio stays connected)
      if (livekitConnected) startRecording();
      return;
    }

    // Final submission — answers are extracted server-side from the LiveKit transcript
    await submitInterviewEnd();
  };

  // Submit the interview end via /api/answers
  const submitInterviewEnd = async () => {
    stopProctoring();
    const updated = [...answers];
    if (answer) updated[currentQuestion] = answer;

    const submission = {
      answers: questions.map((q, i) => ({
        question_id: q.id,
        question: q.question,
        category: q.category,
        competency: q.competency,
        candidate_answer: updated[i] || "Answer discussed during interview.",
      })),
      code_submissions: codeSubmissions,
      integrity_flags: integrityFlags,
      flagged_for_review: flaggedForReview,
      duration_seconds: Math.max(0, 30 * 60 - timeLeft),
      body_language_score: proctoringStatsRef.current.total > 0
        ? (proctoringStatsRef.current.eyeContact / proctoringStatsRef.current.total) * 100
        : null,
    };

    try {
      const resp = await fetch("http://127.0.0.1:8000/api/answers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(submission),
      });
      if (!resp.ok) throw new Error(`Failed to submit: ${resp.status}`);
      const data = await resp.json();
      if (data.analysis) setAnalysis(data.analysis);
    } catch (e: unknown) {
      alert(`Submission failed: ${(e as Error).message}`);
    }

    // Disconnect LiveKit if connected
    if (livekitRoomRef.current) {
      try { livekitRoomRef.current.disconnect(); } catch { /* ignore */ }
      livekitRoomRef.current = null;
      setLivekitConnected(false);
    }

    setScreen("results");
  };

  // Submit partial interview data (used when interview is halted due to proctoring violations)
  const submitPartialInterview = async () => {
    try {
      const resp = await fetch("http://127.0.0.1:8000/api/finish-interview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code_submissions: codeSubmissions,
          integrity_flags: integrityFlags,
          flagged_for_review: true,
          duration_seconds: Math.max(0, 30 * 60 - timeLeft),
          body_language_score: proctoringStatsRef.current.total > 0
            ? (proctoringStatsRef.current.eyeContact / proctoringStatsRef.current.total) * 100
            : null,
        }),
      });
      if (resp.ok) {
        const data = await resp.json();
        if (data.analysis) setAnalysis(data.analysis);
      }
    } catch {
      // Non-blocking — partial data may not produce a full analysis
      setAnalysisError("Interview was halted. Partial analysis may not be available.");
    }
  };

  const formatTime = (s: number) =>
    `${Math.floor(s / 60).toString().padStart(2, "0")}:${(s % 60).toString().padStart(2, "0")}`;

  // ──────────────────────────────────────────────────────────────────
  // LINKEDIN OPTIMIZER
  // ──────────────────────────────────────────────────────────────────

  const handleLinkedInAnalyze = async () => {
    if (!linkedinText.trim()) { setLinkedinError("Please paste your LinkedIn profile text."); return; }
    setLinkedinLoading(true);
    setLinkedinError("");
    setLinkedinResult(null);
    try {
      const resp = await fetch("http://127.0.0.1:8000/api/linkedin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile_text: linkedinText }),
      });
      if (!resp.ok) throw new Error((await resp.json()).detail);
      const data = await resp.json();
      setLinkedinResult(data.result);
    } catch (e: unknown) {
      setLinkedinError((e as Error).message);
    } finally {
      setLinkedinLoading(false);
    }
  };

  // ──────────────────────────────────────────────────────────────────
  // CV RATER
  // ──────────────────────────────────────────────────────────────────

  const handleCvRate = async () => {
    if (!cvFile) { setCvError("Please upload a resume PDF."); return; }
    setCvLoading(true);
    setCvError("");
    setCvResult(null);
    try {
      const form = new FormData();
      form.append("resume_file", cvFile);
      form.append("jd_text", cvJdText);
      const resp = await fetch("http://127.0.0.1:8000/api/cv-rate", {
        method: "POST",
        body: form,
      });
      if (!resp.ok) throw new Error((await resp.json()).detail);
      const data = await resp.json();
      setCvResult(data.result);
    } catch (e: unknown) {
      setCvError((e as Error).message);
    } finally {
      setCvLoading(false);
    }
  };

  // ──────────────────────────────────────────────────────────────────
  // 3-STRIKE HALT: stop the interview when flagged for review
  // ──────────────────────────────────────────────────────────────────

  useEffect(() => {
    if (flaggedForReview && screen === "interview") {
      stopRecording();
      stopProctoring();
      // Disconnect LiveKit
      if (livekitRoomRef.current) {
        try { livekitRoomRef.current.disconnect(); } catch { /* ignore */ }
        livekitRoomRef.current = null;
        setLivekitConnected(false);
      }
      // Submit partial data and navigate to results
      submitPartialInterview();
      setScreen("results");
    }
  }, [flaggedForReview, screen]); // eslint-disable-line react-hooks/exhaustive-deps

  // ──────────────────────────────────────────────────────────────────
  // CLEANUP
  // ──────────────────────────────────────────────────────────────────

  useEffect(() => {
    return () => {
      if (recognitionRef.current) { try { recognitionRef.current.abort(); } catch { /* ignore */ } }
      stopProctoring();
      // Cleanup LiveKit room on unmount
      if (livekitRoomRef.current) {
        try { livekitRoomRef.current.disconnect(); } catch { /* ignore */ }
        livekitRoomRef.current = null;
      }
    };
  }, [stopProctoring]);

  // ══════════════════════════════════════════════════════════════════
  // LINKEDIN SCREEN
  // ══════════════════════════════════════════════════════════════════

  if (screen === "linkedin") {
    const result = linkedinResult as {
      overall_score?: number;
      section_scores?: Record<string, number>;
      issues?: { section: string; issue: string; severity: string }[];
      rewrites?: { section: string; original: string; suggested_rewrite: string; reason: string }[];
      summary?: string;
    } | null;

    return (
      <div className="app">
        <header className="navbar">
          <div className="brand" onClick={() => setScreen("home")} style={{ cursor: "pointer" }}>
            <div className="brand-icon"><Sparkles size={20} /></div>
            <span>FirstRound</span>
          </div>
          <div className="nav-links">
            <span className="nav-active"><LinkedinIcon size={16} /> LinkedIn Optimizer</span>
            <span onClick={() => setScreen("cv-rater")} style={{ cursor: "pointer" }}>CV Rater</span>
            <span onClick={() => setScreen("home")} style={{ cursor: "pointer" }}>Home</span>
          </div>
        </header>

        <main className="tool-page">
          <div className="tool-header">
            <LinkedinIcon size={36} className="tool-icon" />
            <h1>LinkedIn Profile Optimizer</h1>
            <p>Get specific, actionable feedback to improve your LinkedIn profile and stand out to recruiters.</p>
          </div>

          <div className="tool-card">
            <label className="field-label">LinkedIn Profile URL (optional — for reference)</label>
            <input
              className="text-input"
              type="url"
              placeholder="https://linkedin.com/in/yourprofile"
              value={linkedinUrl}
              onChange={(e) => setLinkedinUrl(e.target.value)}
            />

            <label className="field-label" style={{ marginTop: 16 }}>
              Paste your profile text here <span className="required">*</span>
            </label>
            <p className="field-hint">Copy from your LinkedIn profile page or use the "Save to PDF" export and paste the text content.</p>
            <textarea
              className="big-textarea"
              placeholder="Paste your headline, About section, experience bullets, and skills here..."
              value={linkedinText}
              onChange={(e) => setLinkedinText(e.target.value)}
              rows={12}
            />

            {linkedinError && <div className="error-box">{linkedinError}</div>}

            <button
              className="primary-button"
              onClick={handleLinkedInAnalyze}
              disabled={linkedinLoading}
            >
              {linkedinLoading ? "Analyzing..." : "Analyze Profile"}
              {!linkedinLoading && <ArrowRight size={18} />}
            </button>
          </div>

          {result && (
            <div className="results-section">
              {result.overall_score !== undefined && (
                <div className="score-headline">
                  <span>Overall Profile Score</span>
                  <ScoreBadge score={result.overall_score} />
                </div>
              )}

              {result.section_scores && (
                <div className="score-grid">
                  {Object.entries(result.section_scores).map(([section, score]) => (
                    <div key={section} className="score-card">
                      <span>{section.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}</span>
                      <strong>{score}</strong>
                      <small>/ 100</small>
                    </div>
                  ))}
                </div>
              )}

              {result.issues && result.issues.length > 0 && (
                <div className="analysis-card">
                  <h2>Issues Found</h2>
                  {result.issues.map((issue, i) => (
                    <div key={i} className={`issue-row severity-${issue.severity}`}>
                      <AlertTriangle size={15} />
                      <div>
                        <strong>{issue.section}</strong>: {issue.issue}
                        <span className={`severity-badge ${issue.severity}`}>{issue.severity}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {result.rewrites && result.rewrites.length > 0 && (
                <div className="analysis-card">
                  <h2>Suggested Rewrites</h2>
                  {result.rewrites.map((rw, i) => (
                    <div key={i} className="rewrite-block">
                      <div className="rewrite-section-label">{rw.section}</div>
                      <div className="rewrite-before"><strong>Before:</strong> {rw.original}</div>
                      <div className="rewrite-after">
                        <strong>After:</strong> {rw.suggested_rewrite}
                        <CopyButton text={rw.suggested_rewrite} />
                      </div>
                      {rw.reason && <div className="rewrite-reason">{rw.reason}</div>}
                    </div>
                  ))}
                </div>
              )}

              {result.summary && (
                <div className="analysis-card summary-card">
                  <h2>Summary</h2>
                  <p>{result.summary}</p>
                </div>
              )}
            </div>
          )}
        </main>
      </div>
    );
  }

  // ══════════════════════════════════════════════════════════════════
  // CV RATER SCREEN
  // ══════════════════════════════════════════════════════════════════

  if (screen === "cv-rater") {
    const result = cvResult as {
      overall_score?: number;
      ats_score?: number;
      bullet_quality_score?: number;
      structure_score?: number;
      jd_alignment_score?: number | null;
      issues?: { category: string; issue: string; example: string; severity: string }[];
      rewrites?: { original: string; improved: string; reason: string }[];
      strengths?: string[];
      summary?: string;
    } | null;

    return (
      <div className="app">
        <header className="navbar">
          <div className="brand" onClick={() => setScreen("home")} style={{ cursor: "pointer" }}>
            <div className="brand-icon"><Sparkles size={20} /></div>
            <span>FirstRound</span>
          </div>
          <div className="nav-links">
            <span onClick={() => setScreen("linkedin")} style={{ cursor: "pointer" }}>LinkedIn Optimizer</span>
            <span className="nav-active"><FileText size={16} /> CV Rater</span>
            <span onClick={() => setScreen("home")} style={{ cursor: "pointer" }}>Home</span>
          </div>
        </header>

        <main className="tool-page">
          <div className="tool-header">
            <Star size={36} className="tool-icon" />
            <h1>CV / Resume Rater</h1>
            <p>Get an objective score and specific fixes for your resume — optionally targeted to a specific job description.</p>
          </div>

          <div className="tool-card">
            <label className="field-label">Upload Resume PDF <span className="required">*</span></label>
            <input
              type="file"
              accept=".pdf"
              className="file-input"
              onChange={(e) => setCvFile(e.target.files?.[0] ?? null)}
            />
            {cvFile && <span className="file-name">✓ {cvFile.name}</span>}

            <label className="field-label" style={{ marginTop: 16 }}>Target Job Description (optional — for alignment scoring)</label>
            <textarea
              className="big-textarea"
              placeholder="Paste job description here for JD-alignment scoring..."
              value={cvJdText}
              onChange={(e) => setCvJdText(e.target.value)}
              rows={6}
            />

            {cvError && <div className="error-box">{cvError}</div>}

            <button
              className="primary-button"
              onClick={handleCvRate}
              disabled={cvLoading}
            >
              {cvLoading ? "Rating..." : "Rate My CV"}
              {!cvLoading && <ArrowRight size={18} />}
            </button>
          </div>

          {result && (
            <div className="results-section">
              <div className="score-grid">
                {[
                  { label: "Overall", val: result.overall_score },
                  { label: "ATS Score", val: result.ats_score },
                  { label: "Bullet Quality", val: result.bullet_quality_score },
                  { label: "Structure", val: result.structure_score },
                  ...(result.jd_alignment_score != null
                    ? [{ label: "JD Alignment", val: result.jd_alignment_score }]
                    : []),
                ].map(({ label, val }) => (
                  <div key={label} className="score-card">
                    <span>{label}</span>
                    <strong>{val}</strong>
                    <small>/ 100</small>
                  </div>
                ))}
              </div>

              {result.strengths && result.strengths.length > 0 && (
                <div className="analysis-card">
                  <h2>Strengths</h2>
                  <ul>{result.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul>
                </div>
              )}

              {result.issues && result.issues.length > 0 && (
                <div className="analysis-card">
                  <h2>Issues Found</h2>
                  {result.issues.map((issue, i) => (
                    <div key={i} className={`issue-row severity-${issue.severity}`}>
                      <AlertTriangle size={15} />
                      <div>
                        <strong>[{issue.category}]</strong> {issue.issue}
                        {issue.example && <div className="issue-example">"{issue.example}"</div>}
                        <span className={`severity-badge ${issue.severity}`}>{issue.severity}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {result.rewrites && result.rewrites.length > 0 && (
                <div className="analysis-card">
                  <h2>Bullet Rewrites</h2>
                  {result.rewrites.map((rw, i) => (
                    <div key={i} className="rewrite-block">
                      <div className="rewrite-before"><strong>Before:</strong> {rw.original}</div>
                      <div className="rewrite-after">
                        <strong>After:</strong> {rw.improved}
                        <CopyButton text={rw.improved} />
                      </div>
                      {rw.reason && <div className="rewrite-reason">{rw.reason}</div>}
                    </div>
                  ))}
                </div>
              )}

              {result.summary && (
                <div className="analysis-card summary-card">
                  <h2>Summary</h2>
                  <p>{result.summary}</p>
                </div>
              )}
            </div>
          )}
        </main>
      </div>
    );
  }

  // ══════════════════════════════════════════════════════════════════
  // RESULTS SCREEN
  // ══════════════════════════════════════════════════════════════════

  if (screen === "results") {
    return (
      <div className="app">
        <header className="navbar">
          <div className="brand"><div className="brand-icon"><Sparkles size={20} /></div><span>FirstRound</span></div>
          <div className="nav-status"><CheckCircle2 size={18} /> Interview completed</div>
        </header>

        <main className="results-page">
          <div className="results-header">
            <div className="success-icon"><CheckCircle2 size={42} /></div>
            <p className="eyebrow">INTERVIEW COMPLETE</p>
            <h1>Your interview is complete.</h1>
            <p>Your responses have been recorded. Your AI-powered performance analysis evaluates technical ability, communication and job alignment.</p>
          </div>

          {flaggedForReview && (
            <div className="flag-banner">
              <AlertTriangle size={20} />
              <span>This interview has been flagged for review due to integrity violations detected during the session.</span>
            </div>
          )}

          {analysisLoading && <div className="analysis-loading"><p>Analyzing your interview...</p></div>}
          {analysisError && <div className="analysis-error"><p>{analysisError}</p></div>}

          <div className="score-grid">
            {[
              { icon: <Target size={22} />, label: "Overall", key: "overall_score" },
              { icon: <Code2 size={22} />, label: "Technical", key: "technical_score" },
              { icon: <Mic size={22} />, label: "Communication", key: "communication_score" },
              { icon: <ShieldCheck size={22} />, label: "JD Alignment", key: "jd_alignment_score" },
            ].map(({ icon, label, key }) => (
              <div key={key} className="score-card">
                {icon}
                <span>{label}</span>
                <strong>{analysis ? (analysis as Record<string, unknown>)[key] as number : "—"}</strong>
                <small>{analysis ? "Score out of 100" : analysisLoading ? "Loading..." : "Pending"}</small>
              </div>
            ))}
          </div>

          {analysis && (
            <div className="analysis-section">
              {[
                { title: "Strengths", key: "strengths" },
                { title: "Areas to Improve", key: "weaknesses" },
                { title: "Technical Gaps", key: "technical_gaps" },
                { title: "Communication Gaps", key: "communication_gaps" },
                { title: "Improvement Plan", key: "improvement_plan" },
              ].map(({ title, key }) => {
                const items = (analysis as Record<string, unknown>)[key] as string[];
                return (
                  <div key={key} className="analysis-card">
                    <h2>{title}</h2>
                    {items?.length > 0 ? <ul>{items.map((item, i) => <li key={i}>{item}</li>)}</ul> : <p>None recorded.</p>}
                  </div>
                );
              })}

              {analysis.code_performance && analysis.code_performance.attempted > 0 && (
                <div className="analysis-card">
                  <h2>Code Performance</h2>
                  <div className="code-perf-row">
                    <span>Attempted: <strong>{analysis.code_performance.attempted}</strong></span>
                    <span>Passed: <strong>{analysis.code_performance.passed}</strong></span>
                    <span>Avg Score: <strong>{analysis.code_performance.average_score}/100</strong></span>
                  </div>
                  {analysis.code_performance.notes && <p>{analysis.code_performance.notes}</p>}
                </div>
              )}

              {analysis.integrity && (analysis.integrity.flag_count > 0 || analysis.integrity.flagged_for_review) && (
                <div className="analysis-card integrity-card">
                  <h2>Integrity Report</h2>
                  {analysis.integrity.flagged_for_review ? (
                    <p className="flag-text">⚠️ This session was flagged for review ({analysis.integrity.flag_count} violation{analysis.integrity.flag_count !== 1 ? "s" : ""} detected).</p>
                  ) : (
                    <p>{analysis.integrity.flag_count} minor event(s) logged.</p>
                  )}
                  {analysis.integrity.flags?.map((f, i) => (
                    <div key={i} className="flag-row">
                      <span className="flag-type">{f.type.replace(/_/g, " ")}</span>
                      <span className="flag-detail">{f.details}</span>
                      <span className="flag-time">{new Date(f.timestamp).toLocaleTimeString()}</span>
                    </div>
                  ))}
                </div>
              )}

              <div className="analysis-card summary-card">
                <h2>AI Summary</h2>
                <p>{analysis.summary}</p>
                <div className="recommendation">
                  <strong>Recommendation</strong>
                  <span>{analysis.recommendation}</span>
                </div>
              </div>
            </div>
          )}

          <div className="results-actions">
            <button className="primary-button" onClick={() => setScreen("home")}>
              Back to Dashboard <ArrowRight size={18} />
            </button>
          </div>
        </main>
      </div>
    );
  }

  // ══════════════════════════════════════════════════════════════════
  // INTERVIEW SCREEN
  // ══════════════════════════════════════════════════════════════════

  if (screen === "interview") {
    if (!question) {
      return (
        <div className="app"><main className="interview-page">
          <h1>Loading interview...</h1>
          <p>Please wait while your questions are loaded.</p>
        </main></div>
      );
    }

    const isCoding = question.category === "coding";
    const currentCode = codeMap[question.id] ?? question.starter_code ?? "";

    return (
      <div className="app interview-app">
        <header className="navbar interview-navbar">
          <div className="brand"><div className="brand-icon"><Sparkles size={20} /></div><span>FirstRound</span></div>
          <div className="question-counter">Question {currentQuestion + 1} of {questions.length}</div>
          <div className="timer"><Clock3 size={17} />{formatTime(timeLeft)}</div>
        </header>

        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${((currentQuestion + 1) / questions.length) * 100}%` }} />
        </div>

        {proctoringWarning && (
          <div className="proctoring-warning">
            <AlertTriangle size={16} />
            {proctoringWarning}
          </div>
        )}

        <main className={`interview-page ${isCoding ? "coding-layout" : ""}`}>
          {/* Video self-view (corner panel when proctoring enabled) */}
          {cameraGranted && (
            <div className="video-corner">
              <video ref={videoRef} autoPlay muted playsInline className="video-preview" />
              <canvas ref={canvasRef} width={160} height={120} style={{ display: "none" }} />
            </div>
          )}

          <div className="question-meta">
            <span>{question.category}</span>
            <span className="dot">•</span>
            <span>{question.competency}</span>
            {isCoding && question.difficulty && (
              <><span className="dot">•</span><span className={`difficulty-badge ${question.difficulty}`}>{question.difficulty}</span></>
            )}
          </div>

          <div className="live-interviewer-status">
            <div className={`voice-indicator ${livekitConnected ? "speaking" : ""}`}>
              {livekitConnected ? <Radio size={20} /> : <Sparkles size={20} />}
            </div>
            <span>{livekitConnected ? "Live voice interview connected" : isRecording ? "Listening to your answer..." : "AI interviewer"}</span>
          </div>

          {/* Hidden audio element for LiveKit agent voice playback */}
          <audio ref={audioRef} style={{ display: "none" }} />

          <h1>{question.question}</h1>

          {isCoding ? (
            /* ── CODING QUESTION LAYOUT ─────────────────────── */
            <div className="coding-panel">
              <div className="code-editor-section">
                <div className="editor-toolbar">
                  <span className="editor-lang">{question.language ?? "python"}</span>
                  <button className="run-btn" onClick={handleRunCode} disabled={isRunning}>
                    <Play size={14} /> {isRunning ? "Running..." : "Run Code"}
                  </button>
                  <button className="submit-code-btn" onClick={handleSubmitCode}>
                    <CheckCircle2 size={14} /> Submit Code
                  </button>
                </div>
                <Editor
                  height="320px"
                  language={question.language ?? "python"}
                  value={currentCode}
                  theme="vs-dark"
                  onChange={(val) => {
                    setCodeMap((prev) => ({ ...prev, [question.id]: val ?? "" }));
                  }}
                  options={{ minimap: { enabled: false }, fontSize: 14, scrollBeyondLastLine: false }}
                />
                {runOutput && (
                  <div className="run-output">
                    {runOutput.stdout && <div className="stdout"><strong>Output:</strong><pre>{runOutput.stdout}</pre></div>}
                    {runOutput.stderr && <div className="stderr"><strong>Error:</strong><pre>{runOutput.stderr}</pre></div>}
                  </div>
                )}
              </div>

              <div className="voice-section">
                <p className="question-helper">Talk through your approach while you code.</p>
                <div className="answer-card compact">
                  <div className="answer-header">
                    <span className="answer-label">VERBAL EXPLANATION</span>
                    {!isRecording
                      ? <button className="record-button" onClick={startRecording}><Mic size={18} /> Start Talking</button>
                      : <button className="record-button recording" onClick={stopRecording}><Mic size={18} /> Stop</button>
                    }
                  </div>
                  <textarea
                    value={answer}
                    onChange={(e) => { setAnswer(e.target.value); answerRef.current = e.target.value; finalTranscriptRef.current = e.target.value; }}
                    placeholder="Your verbal explanation will appear here..."
                  />
                </div>
              </div>
            </div>
          ) : (
            /* ── VOICE QUESTION LAYOUT ──────────────────────── */
            <>
              <p className="question-helper">
                {livekitConnected ? "The AI interviewer is speaking live. Answer naturally when prompted." : isRecording ? "Speak naturally. Your answer will be transcribed automatically." : "Press Start Answer to begin speaking."}
              </p>
              <div className="answer-card">
                <div className="answer-header">
                  <div>
                    <span className="answer-label">YOUR ANSWER</span>
                    <p>{isRecording ? "Listening through your microphone" : livekitConnected ? "Live voice connected — answer when prompted" : "Your spoken answer will appear here"}</p>
                  </div>
                  {!isRecording
                    ? <button className="record-button" onClick={startRecording}><Mic size={18} />Start Answer</button>
                    : <button className="record-button recording" onClick={stopRecording}><Mic size={18} />Stop Answer</button>
                  }
                </div>
                <textarea
                  value={answer}
                  onChange={(e) => { const v = e.target.value; setAnswer(v); answerRef.current = v; finalTranscriptRef.current = v; }}
                  placeholder={isRecording ? "Speak your answer..." : "Your spoken answer will appear here..."}
                />
                <div className="answer-footer">
                  <span>{answer.length} characters</span>
                  {isRecording && <span className="recording-status"><span className="recording-dot" />Listening...</span>}
                  {livekitConnected && <span className="recording-status"><span className="recording-dot" />Live voice connected</span>}
                </div>
              </div>
            </>
          )}

          <div className="interview-actions">
            <button className="secondary-button" onClick={() => { stopRecording(); stopProctoring(); if (livekitRoomRef.current) { try { livekitRoomRef.current.disconnect(); } catch { /* ignore */ } livekitRoomRef.current = null; setLivekitConnected(false); } setScreen("home"); }}>
              Exit Interview
            </button>
            <button className="primary-button" onClick={nextQuestion}>
              {currentQuestion === questions.length - 1 ? "Finish Interview" : "Next Question"}
              <ChevronRight size={18} />
            </button>
          </div>

          <div className="question-dots">
            {questions.map((_, i) => (
              <div key={i} className={`question-dot ${i === currentQuestion ? "active" : ""} ${answers[i] ? "answered" : ""}`} />
            ))}
          </div>
        </main>
      </div>
    );
  }

  // ══════════════════════════════════════════════════════════════════
  // HOME SCREEN
  // ══════════════════════════════════════════════════════════════════

  const candidateName = (resumeSummary as { name?: string }).name;

  return (
    <div className="app">
      <header className="navbar">
        <div className="brand"><div className="brand-icon"><Sparkles size={20} /></div><span>FirstRound</span></div>
        <div className="nav-links">
          <span onClick={() => setScreen("linkedin")} style={{ cursor: "pointer" }}><LinkedinIcon size={15} /> LinkedIn</span>
          <span onClick={() => setScreen("cv-rater")} style={{ cursor: "pointer" }}><FileText size={15} /> CV Rater</span>
        </div>
        <div className="profile">
          <div className="profile-avatar"><UserRound size={17} /></div>
          <span>{candidateName || "Candidate"}</span>
        </div>
      </header>

      <main className="home-page">
        <section className="hero-section">
          <div className="hero-copy">
            <div className="eyebrow"><Sparkles size={15} />AI-POWERED INTERVIEW COACH</div>
            <h1>Your next interview<span> starts here.</span></h1>
            <p>Practice realistic interviews tailored to your resume and the job you're applying for. Get evaluated on technical skills, communication and role alignment.</p>

            <div className="trust-row">
              <div><CheckCircle2 size={17} />Resume-based questions</div>
              <div><CheckCircle2 size={17} />AI evaluation</div>
              <div><CheckCircle2 size={17} />Personalized feedback</div>
            </div>
          </div>

          <div className="hero-card">
            <div className="card-top">
              <h3>Prepare Your Interview</h3>
              {prepDone && <div className="status-pill"><span />Ready</div>}
            </div>

            {!prepDone ? (
              /* ── PREP FORM ─────────────────────────────────── */
              <div className="prep-form">
                <label className="field-label">Target Role</label>
                <select
                  className="role-select"
                  value={selectedRole}
                  onChange={(e) => setSelectedRole(e.target.value)}
                >
                  {ROLE_OPTIONS.map((r) => <option key={r}>{r}</option>)}
                </select>

                {selectedRole === "Other (type your own)" && (
                  <input
                    className="text-input"
                    placeholder="e.g. Cybersecurity Analyst"
                    value={customRole}
                    onChange={(e) => setCustomRole(e.target.value)}
                  />
                )}

                <label className="field-label" style={{ marginTop: 12 }}>Upload Resume (PDF)</label>
                <input
                  type="file"
                  accept=".pdf"
                  className="file-input"
                  onChange={(e) => setResumeFile(e.target.files?.[0] ?? null)}
                />
                {resumeFile && <span className="file-name">✓ {resumeFile.name}</span>}

                <label className="field-label" style={{ marginTop: 12 }}>Paste Job Description</label>
                <textarea
                  className="jd-textarea"
                  placeholder="Paste the full job description here..."
                  value={jdText}
                  onChange={(e) => setJdText(e.target.value)}
                  rows={5}
                />

                <label className="field-label" style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 8 }}>
                  <input
                    type="checkbox"
                    checked={proctoringEnabled}
                    onChange={(e) => setProctoringEnabled(e.target.checked)}
                  />
                  Enable Video Proctoring (optional)
                  {proctoringEnabled ? <Eye size={16} /> : <EyeOff size={16} />}
                </label>

                {prepError && <div className="error-box">{prepError}</div>}

                <button
                  className="primary-button"
                  onClick={handlePrepare}
                  disabled={isPreparing}
                  style={{ marginTop: 16, width: "100%" }}
                >
                  {isPreparing ? "Generating questions..." : "Generate Interview Plan"}
                  {!isPreparing && <ArrowRight size={18} />}
                </button>
              </div>
            ) : (
              /* ── POST-PREP: READY TO START ─────────────────── */
              <div className="ready-panel">
                {candidateName && (
                  <div className="candidate-card">
                    <div className="candidate-icon"><UserRound size={24} /></div>
                    <div>
                      <strong>{candidateName}</strong>
                      <p>{effectiveRole}</p>
                    </div>
                  </div>
                )}

                <div className="interview-info">
                  <div><FileText size={18} /><span><strong>{questions.length || "..."}</strong> Questions</span></div>
                  <div><Clock3 size={18} /><span><strong>30</strong> Minutes</span></div>
                  <div><Target size={18} /><span><strong>{effectiveRole}</strong></span></div>
                </div>

                <label className="field-label" style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 8 }}>
                  <input
                    type="checkbox"
                    checked={proctoringEnabled}
                    onChange={(e) => setProctoringEnabled(e.target.checked)}
                  />
                  Enable Video Proctoring
                  {proctoringEnabled ? <Eye size={16} /> : <EyeOff size={16} />}
                </label>

                <div className="card-footer">
                  <button className="secondary-button small" onClick={() => setPrepDone(false)}>Re-generate</button>
                  <button className="primary-button" onClick={startInterview} disabled={questions.length === 0}>
                    Begin <ArrowRight size={16} />
                  </button>
                </div>
              </div>
            )}
          </div>
        </section>

        <section className="feature-section">
          <div className="section-heading">
            <p className="eyebrow">HOW FIRSTROUND WORKS</p>
            <h2>Prepare with purpose.</h2>
          </div>
          <div className="feature-grid">
            {[
              { num: "01", icon: <FileText size={25} />, title: "Understand your profile", desc: "Your resume and job description are used to understand the skills the interview should focus on." },
              { num: "02", icon: <Mic size={25} />, title: "Practice the interview", desc: "Answer realistic questions designed around your actual experience and target role." },
              { num: "03", icon: <Target size={25} />, title: "Get evaluated", desc: "Receive structured feedback covering technical performance, communication and job alignment." },
            ].map(({ num, icon, title, desc }) => (
              <div key={num} className="feature-card">
                <div className="feature-number">{num}</div>
                {icon}
                <h3>{title}</h3>
                <p>{desc}</p>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
