
import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Code2,
  FileText,
  Mic,
  Play,
  ShieldCheck,
  Sparkles,
  Target,
  UserRound,
} from "lucide-react";
import "./App.css";

type Screen = "home" | "interview" | "results";

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
};

type SpeechResult = {
  0: {
    transcript: string;
  };
  isFinal: boolean;
  length: number;
};

type SpeechRecognitionEventLike = Event & {
  resultIndex: number;
  results: {
    [index: number]: SpeechResult;
    length: number;
  };
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
  onerror: ((event: any) => void) | null;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
};

type SpeechRecognitionConstructor = new () => SpeechRecognitionInstance;

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  }
}

function App() {
  const [screen, setScreen] = useState<Screen>("home");
  const [currentQuestion, setCurrentQuestion] = useState(0);

  const [answer, setAnswer] = useState("");
  const [answers, setAnswers] = useState<string[]>([]);

  const [isRecording, setIsRecording] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);

  const [questions, setQuestions] = useState<any[]>([]);

  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState("");

  const [timeLeft, setTimeLeft] = useState(30 * 60);

  // Speech recognition reference
  const recognitionRef =
    useRef<SpeechRecognitionInstance | null>(null);

  // Stores the confirmed/final speech text.
  // This prevents Chrome interim results from being duplicated.
  const finalTranscriptRef = useRef("");

  // Keeps the latest answer available immediately,
  // even before React updates the state.
  const answerRef = useRef("");

  // --------------------------------------------------
  // LOAD QUESTIONS
  // --------------------------------------------------

  useEffect(() => {
    fetch("http://localhost:8000/api/questions")
      .then((response) => {
        if (!response.ok) {
          throw new Error("Failed to load questions");
        }

        return response.json();
      })
      .then((data) => {
        setQuestions(data.questions || []);
      })
      .catch((error) => {
        console.error(
          "Failed to load interview questions:",
          error
        );
      });
  }, []);

  // --------------------------------------------------
  // LOAD FINAL ANALYSIS
  // --------------------------------------------------

  useEffect(() => {
    if (screen !== "results") {
      return;
    }

    setAnalysisLoading(true);
    setAnalysisError("");

    fetch("http://127.0.0.1:8000/api/analysis")
      .then((response) => {
        if (!response.ok) {
          throw new Error(
            "Failed to load interview analysis"
          );
        }

        return response.json();
      })
      .then((data) => {
        console.log("Analysis received:", data);
        setAnalysis(data);
      })
      .catch((error) => {
        console.error(
          "Failed to load analysis:",
          error
        );

        setAnalysisError(
          "Unable to load your AI analysis. Please make sure the backend is running."
        );
      })
      .finally(() => {
        setAnalysisLoading(false);
      });
  }, [screen]);

  // --------------------------------------------------
  // TIMER
  // --------------------------------------------------

  useEffect(() => {
    if (screen !== "interview") {
      return;
    }

    if (timeLeft <= 0) {
      stopRecording();

      alert(
        "Your 30-minute interview time has ended."
      );

      setScreen("results");

      return;
    }

    const timer = window.setInterval(() => {
      setTimeLeft((previous) => previous - 1);
    }, 1000);

    return () => {
      window.clearInterval(timer);
    };
  }, [screen, timeLeft]);

  // --------------------------------------------------
  // CLEANUP
  // --------------------------------------------------

  useEffect(() => {
    return () => {
      window.speechSynthesis.cancel();

      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {
          // Ignore cleanup errors.
        }
      }
    };
  }, []);

  // --------------------------------------------------
  // CURRENT QUESTION
  // --------------------------------------------------

  const question = questions[currentQuestion];

  // --------------------------------------------------
  // TIMER FORMAT
  // --------------------------------------------------

  const formatTime = (seconds: number) => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;

    return `${minutes
      .toString()
      .padStart(2, "0")}:${remainingSeconds
      .toString()
      .padStart(2, "0")}`;
  };

  // --------------------------------------------------
  // SPEAK QUESTION
  // --------------------------------------------------

  const speakQuestion = (questionText: string) => {
    if (!questionText) {
      return;
    }

    window.speechSynthesis.cancel();

    const utterance =
      new SpeechSynthesisUtterance(questionText);

    utterance.rate = 0.95;
    utterance.pitch = 1;
    utterance.volume = 1;

    utterance.onstart = () => {
      setIsSpeaking(true);
    };

    utterance.onend = () => {
      setIsSpeaking(false);
    };

    utterance.onerror = () => {
      setIsSpeaking(false);
    };

    window.speechSynthesis.speak(utterance);
  };

  // --------------------------------------------------
  // SPEAK QUESTION WHEN QUESTION CHANGES
  // --------------------------------------------------

  useEffect(() => {
    if (screen !== "interview") {
      return;
    }

    if (!question) {
      return;
    }

    // Reset answer for the new question
    setAnswer("");
    answerRef.current = "";
    finalTranscriptRef.current = "";

    const timer = window.setTimeout(() => {
      speakQuestion(question.question);
    }, 500);

    return () => {
      window.clearTimeout(timer);
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
    };
  }, [screen, currentQuestion]);

  // --------------------------------------------------
  // START MICROPHONE
  // --------------------------------------------------

  const startRecording = () => {
    if (isRecording) {
      return;
    }

    const SpeechRecognition =
      window.SpeechRecognition ||
      window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert(
        "Speech recognition is not supported in this browser. Please use Google Chrome."
      );

      return;
    }

    // Stop AI voice before microphone starts
    window.speechSynthesis.cancel();
    setIsSpeaking(false);

    // Make sure an old recognition instance is gone
    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort();
      } catch {
        // Ignore
      }
    }

    const recognition = new SpeechRecognition();

    recognition.continuous = true;

    // IMPORTANT:
    // We use interim results only for display.
    // They are NEVER permanently appended.
    recognition.interimResults = true;

    recognition.lang = "en-US";

    // Start with whatever was already typed/spoken
    finalTranscriptRef.current =
      answerRef.current.trim();

    recognition.onstart = () => {
      console.log("Microphone started.");
      setIsRecording(true);
    };

    recognition.onresult = (
      event: SpeechRecognitionEventLike
    ) => {
      let newFinalText = "";
      let currentInterimText = "";

      // IMPORTANT:
      // Only process results from resultIndex onward.
      // This prevents Chrome from sending old results again.
      for (
        let i = event.resultIndex;
        i < event.results.length;
        i++
      ) {
        const result = event.results[i];

        if (!result || result.length === 0) {
          continue;
        }

        const transcript =
          result[0]?.transcript?.trim() || "";

        if (!transcript) {
          continue;
        }

        if (result.isFinal) {
          newFinalText +=
            (newFinalText ? " " : "") +
            transcript;
        } else {
          currentInterimText +=
            (currentInterimText ? " " : "") +
            transcript;
        }
      }

      // Only permanently add FINAL speech.
      if (newFinalText) {
        finalTranscriptRef.current =
          `${finalTranscriptRef.current} ${newFinalText}`
            .trim();
      }

      // Show:
      // confirmed text + current temporary speech
      const displayText =
        `${finalTranscriptRef.current} ${
          currentInterimText || ""
        }`.trim();

      answerRef.current = displayText;
      setAnswer(displayText);
    };

    recognition.onerror = (event: any) => {
      console.error(
        "Speech recognition error:",
        event
      );

      if (
        event?.error === "not-allowed" ||
        event?.error === "permission-denied"
      ) {
        alert(
          "Microphone permission was denied. Please allow microphone access in Chrome."
        );
      }

      setIsRecording(false);
    };

    recognition.onend = () => {
      console.log("Microphone stopped.");
      setIsRecording(false);

      if (
        recognitionRef.current === recognition
      ) {
        recognitionRef.current = null;
      }
    };

    recognitionRef.current = recognition;

    try {
      recognition.start();
    } catch (error) {
      console.error(
        "Could not start microphone:",
        error
      );

      setIsRecording(false);
      recognitionRef.current = null;
    }
  };

  // --------------------------------------------------
  // STOP MICROPHONE
  // --------------------------------------------------

  const stopRecording = () => {
    const recognition =
      recognitionRef.current;

    if (!recognition) {
      setIsRecording(false);
      return;
    }

    try {
      recognition.stop();
    } catch {
      // Ignore if already stopped.
    }

    recognitionRef.current = null;
    setIsRecording(false);
  };

  // --------------------------------------------------
  // START INTERVIEW
  // --------------------------------------------------

  const startInterview = () => {
    if (questions.length === 0) {
      alert(
        "Interview questions are still loading. Please try again."
      );

      return;
    }

    window.speechSynthesis.cancel();
    stopRecording();

    setCurrentQuestion(0);

    setAnswer("");
    answerRef.current = "";

    setAnswers([]);

    setAnalysis(null);
    setAnalysisError("");

    setTimeLeft(30 * 60);

    finalTranscriptRef.current = "";

    setScreen("interview");
  };

  // --------------------------------------------------
  // NEXT / FINISH INTERVIEW
  // --------------------------------------------------

  const nextQuestion = async () => {
    // IMPORTANT:
    // Read from answerRef because it contains
    // the newest microphone text immediately.
    const latestAnswer =
      answerRef.current || answer;

    // Stop microphone AFTER getting latest answer
    stopRecording();

    window.speechSynthesis.cancel();

    const updatedAnswers = [...answers];

    updatedAnswers[currentQuestion] =
      latestAnswer;

    setAnswers(updatedAnswers);

    // ------------------------------------------------
    // NEXT QUESTION
    // ------------------------------------------------

    if (
      currentQuestion <
      questions.length - 1
    ) {
      const nextIndex =
        currentQuestion + 1;

      setCurrentQuestion(nextIndex);

      const nextAnswer =
        updatedAnswers[nextIndex] || "";

      setAnswer(nextAnswer);
      answerRef.current = nextAnswer;

      finalTranscriptRef.current =
        nextAnswer;

      return;
    }

    // ------------------------------------------------
    // FINAL QUESTION
    // ------------------------------------------------

    console.log(
      "Final question reached."
    );

    const submission = {
      answers: questions.map(
        (question, index) => ({
          question_id: question.id,
          question: question.question,
          category: question.category,
          competency: question.competency,
          candidate_answer:
            updatedAnswers[index] || "",
        })
      ),
    };

    console.log(
      "Submitting interview answers:",
      submission
    );

    try {
      const response = await fetch(
        "http://127.0.0.1:8000/api/answers",
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify(
            submission
          ),
        }
      );

      console.log(
        "Backend response status:",
        response.status
      );

      if (!response.ok) {
        const errorText =
          await response.text();

        console.error(
          "Backend error:",
          errorText
        );

        throw new Error(
          `Failed to submit interview: ${response.status}`
        );
      }

      const data =
        await response.json();

      console.log(
        "Interview submission response:",
        data
      );

      // If backend directly returns analysis,
      // use it immediately.
      if (data.analysis) {
        setAnalysis(data.analysis);
      }

      // Move to results screen.
      setScreen("results");
    } catch (error) {
      console.error(
        "Failed to submit interview:",
        error
      );

      alert(
        "There was a problem submitting your interview. Please make sure the backend is running on port 8000."
      );
    }
  };

  // --------------------------------------------------
  // RESULTS SCREEN
  // --------------------------------------------------

  if (screen === "results") {
    return (
      <div className="app">
        <header className="navbar">
          <div className="brand">
            <div className="brand-icon">
              <Sparkles size={20} />
            </div>

            <span>FirstRound</span>
          </div>

          <div className="nav-status">
            <CheckCircle2 size={18} />
            Interview completed
          </div>
        </header>

        <main className="results-page">
          <div className="results-header">
            <div className="success-icon">
              <CheckCircle2 size={42} />
            </div>

            <p className="eyebrow">
              INTERVIEW COMPLETE
            </p>

            <h1>
              Your interview is complete.
            </h1>

            <p>
              Your responses have been
              recorded. Your AI-powered
              performance analysis evaluates
              technical ability,
              communication and job alignment.
            </p>
          </div>

          {analysisLoading && (
            <div className="analysis-loading">
              <p>
                Analyzing your interview...
              </p>
            </div>
          )}

          {analysisError && (
            <div className="analysis-error">
              <p>{analysisError}</p>
            </div>
          )}

          <div className="score-grid">
            <div className="score-card">
              <Target size={22} />

              <span>Overall</span>

              <strong>
                {analysis
                  ? analysis.overall_score
                  : "—"}
              </strong>

              <small>
                {analysis
                  ? "Score out of 10"
                  : analysisLoading
                  ? "Loading analysis..."
                  : "Analysis pending"}
              </small>
            </div>

            <div className="score-card">
              <Code2 size={22} />

              <span>Technical</span>

              <strong>
                {analysis
                  ? analysis.technical_score
                  : "—"}
              </strong>

              <small>
                {analysis
                  ? "Score out of 10"
                  : analysisLoading
                  ? "Loading analysis..."
                  : "Analysis pending"}
              </small>
            </div>

            <div className="score-card">
              <Mic size={22} />

              <span>Communication</span>

              <strong>
                {analysis
                  ? analysis.communication_score
                  : "—"}
              </strong>

              <small>
                {analysis
                  ? "Score out of 10"
                  : analysisLoading
                  ? "Loading analysis..."
                  : "Analysis pending"}
              </small>
            </div>

            <div className="score-card">
              <ShieldCheck size={22} />

              <span>JD Alignment</span>

              <strong>
                {analysis
                  ? analysis.jd_alignment_score
                  : "—"}
              </strong>

              <small>
                {analysis
                  ? "Score out of 10"
                  : analysisLoading
                  ? "Loading analysis..."
                  : "Analysis pending"}
              </small>
            </div>
          </div>

          {analysis && (
            <div className="analysis-section">
              <div className="analysis-card">
                <h2>Strengths</h2>

                {analysis.strengths?.length >
                0 ? (
                  <ul>
                    {analysis.strengths.map(
                      (item, index) => (
                        <li key={index}>
                          {item}
                        </li>
                      )
                    )}
                  </ul>
                ) : (
                  <p>
                    No strengths recorded.
                  </p>
                )}
              </div>

              <div className="analysis-card">
                <h2>Areas to Improve</h2>

                {analysis.weaknesses?.length >
                0 ? (
                  <ul>
                    {analysis.weaknesses.map(
                      (item, index) => (
                        <li key={index}>
                          {item}
                        </li>
                      )
                    )}
                  </ul>
                ) : (
                  <p>
                    No weaknesses recorded.
                  </p>
                )}
              </div>

              <div className="analysis-card">
                <h2>Technical Gaps</h2>

                {analysis.technical_gaps?.length >
                0 ? (
                  <ul>
                    {analysis.technical_gaps.map(
                      (item, index) => (
                        <li key={index}>
                          {item}
                        </li>
                      )
                    )}
                  </ul>
                ) : (
                  <p>
                    No technical gaps recorded.
                  </p>
                )}
              </div>

              <div className="analysis-card">
                <h2>
                  Communication Gaps
                </h2>

                {analysis.communication_gaps?.length >
                0 ? (
                  <ul>
                    {analysis.communication_gaps.map(
                      (item, index) => (
                        <li key={index}>
                          {item}
                        </li>
                      )
                    )}
                  </ul>
                ) : (
                  <p>
                    No communication gaps recorded.
                  </p>
                )}
              </div>

              <div className="analysis-card">
                <h2>Improvement Plan</h2>

                {analysis.improvement_plan?.length >
                0 ? (
                  <ul>
                    {analysis.improvement_plan.map(
                      (item, index) => (
                        <li key={index}>
                          {item}
                        </li>
                      )
                    )}
                  </ul>
                ) : (
                  <p>
                    No improvement plan available.
                  </p>
                )}
              </div>

              <div className="analysis-card summary-card">
                <h2>AI Summary</h2>

                <p>
                  {analysis.summary}
                </p>

                <div className="recommendation">
                  <strong>
                    Recommendation
                  </strong>

                  <span>
                    {analysis.recommendation}
                  </span>
                </div>
              </div>
            </div>
          )}

          <div className="results-actions">
            <button
              className="primary-button"
              onClick={() =>
                setScreen("home")
              }
            >
              Back to Dashboard

              <ArrowRight size={18} />
            </button>
          </div>
        </main>
      </div>
    );
  }

  // --------------------------------------------------
  // INTERVIEW SCREEN
  // --------------------------------------------------

  if (screen === "interview") {
    if (!question) {
      return (
        <div className="app">
          <main className="interview-page">
            <h1>
              Loading interview...
            </h1>

            <p>
              Please wait while your
              questions are loaded.
            </p>
          </main>
        </div>
      );
    }

    return (
      <div className="app interview-app">
        <header className="navbar interview-navbar">
          <div className="brand">
            <div className="brand-icon">
              <Sparkles size={20} />
            </div>

            <span>FirstRound</span>
          </div>

          <div className="question-counter">
            Question{" "}
            {currentQuestion + 1} of{" "}
            {questions.length}
          </div>

          <div className="timer">
            <Clock3 size={17} />

            {formatTime(timeLeft)}
          </div>
        </header>

        <div className="progress-bar">
          <div
            className="progress-fill"
            style={{
              width: `${
                ((currentQuestion + 1) /
                  questions.length) *
                100
              }%`,
            }}
          />
        </div>

        <main className="interview-page">
          <div className="question-meta">
            <span>
              {question.category}
            </span>

            <span className="dot">
              •
            </span>

            <span>
              {question.competency}
            </span>
          </div>

          <div className="live-interviewer-status">
            <div
              className={`voice-indicator ${
                isSpeaking
                  ? "speaking"
                  : ""
              }`}
            >
              <Sparkles size={20} />
            </div>

            <span>
              {isSpeaking
                ? "AI interviewer is speaking..."
                : isRecording
                ? "Listening to your answer..."
                : "AI interviewer"}
            </span>
          </div>

          <h1>
            {question.question}
          </h1>

          <p className="question-helper">
            {isSpeaking
              ? "Listen to the interviewer. You can start answering when the question finishes."
              : "Speak naturally. Your answer will be transcribed automatically."}
          </p>

          <div className="answer-card">
            <div className="answer-header">
              <div>
                <span className="answer-label">
                  YOUR ANSWER
                </span>

                <p>
                  {isRecording
                    ? "Listening through your microphone"
                    : "Your spoken answer will appear here"}
                </p>
              </div>

              {!isRecording ? (
                <button
                  className="record-button"
                  onClick={startRecording}
                  disabled={isSpeaking}
                >
                  <Mic size={18} />

                  {isSpeaking
                    ? "Wait..."
                    : "Start Answer"}
                </button>
              ) : (
                <button
                  className="record-button recording"
                  onClick={stopRecording}
                >
                  <Mic size={18} />

                  Stop Answer
                </button>
              )}
            </div>

            <textarea
              value={answer}
              onChange={(e) => {
                const value =
                  e.target.value;

                setAnswer(value);
                answerRef.current = value;
                finalTranscriptRef.current =
                  value;
              }}
              placeholder={
                isRecording
                  ? "Speak your answer..."
                  : "Your spoken answer will appear here..."
              }
            />

            <div className="answer-footer">
              <span>
                {answer.length} characters
              </span>

              {isRecording && (
                <span className="recording-status">
                  <span className="recording-dot" />

                  Listening...
                </span>
              )}

              {isSpeaking && (
                <span className="recording-status">
                  <span className="recording-dot" />

                  AI speaking...
                </span>
              )}
            </div>
          </div>

          <div className="interview-actions">
            <button
              className="secondary-button"
              onClick={() => {
                stopRecording();
                window.speechSynthesis.cancel();
                setScreen("home");
              }}
            >
              Exit Interview
            </button>

            {/* IMPORTANT:
                Finish is NOT disabled while recording.
                Clicking it stops recording and submits
                the latest answer.
            */}
            <button
              className="primary-button"
              onClick={nextQuestion}
              disabled={isSpeaking}
            >
              {currentQuestion ===
              questions.length - 1
                ? "Finish Interview"
                : "Next Question"}

              <ChevronRight size={18} />
            </button>
          </div>

          <div className="question-dots">
            {questions.map(
              (_, index) => (
                <div
                  key={index}
                  className={`question-dot ${
                    index ===
                    currentQuestion
                      ? "active"
                      : ""
                  } ${
                    answers[index]
                      ? "answered"
                      : ""
                  }`}
                />
              )
            )}
          </div>
        </main>
      </div>
    );
  }

  // --------------------------------------------------
  // HOME SCREEN
  // --------------------------------------------------

  return (
    <div className="app">
      <header className="navbar">
        <div className="brand">
          <div className="brand-icon">
            <Sparkles size={20} />
          </div>

          <span>FirstRound</span>
        </div>

        <div className="nav-links">
          <span>
            How it works
          </span>

          <span>
            My Interviews
          </span>
        </div>

        <div className="profile">
          <div className="profile-avatar">
            <UserRound size={17} />
          </div>

          <span>
            Candidate
          </span>
        </div>
      </header>

      <main className="home-page">
        <section className="hero-section">
          <div className="hero-copy">
            <div className="eyebrow">
              <Sparkles size={15} />

              AI-POWERED INTERVIEW COACH
            </div>

            <h1>
              Your next interview
              <span>
                {" "}
                starts here.
              </span>
            </h1>

            <p>
              Practice realistic
              interviews tailored to
              your resume and the job
              you're applying for. Get
              evaluated on technical
              skills, communication and
              role alignment.
            </p>

            <div className="hero-actions">
              <button
                className="primary-button"
                onClick={
                  startInterview
                }
              >
                <Play size={18} />

                Start Interview
              </button>

              <button className="secondary-button">
                View Preparation
              </button>
            </div>

            <div className="trust-row">
              <div>
                <CheckCircle2
                  size={17}
                />

                Resume-based questions
              </div>

              <div>
                <CheckCircle2
                  size={17}
                />

                AI evaluation
              </div>

              <div>
                <CheckCircle2
                  size={17}
                />

                Personalized feedback
              </div>
            </div>
          </div>

          <div className="hero-card">
            <div className="card-top">
              <div>
                <span className="mini-label">
                  UPCOMING INTERVIEW
                </span>

                <h3>
                  Cybersecurity Interview
                </h3>
              </div>

              <div className="status-pill">
                <span />

                Ready
              </div>
            </div>

            <div className="candidate-card">
              <div className="candidate-icon">
                <UserRound size={24} />
              </div>

              <div>
                <strong>
                  Candidate Profile
                </strong>

                <p>
                  BS Cybersecurity • FAST
                  University
                </p>
              </div>
            </div>

            <div className="interview-info">
              <div>
                <FileText size={18} />

                <span>
                  <strong>
                    {questions.length}
                  </strong>

                  Questions
                </span>
              </div>

              <div>
                <Clock3 size={18} />

                <span>
                  <strong>
                    30
                  </strong>

                  Minutes
                </span>
              </div>

              <div>
                <Target size={18} />

                <span>
                  <strong>
                    3
                  </strong>

                  Competencies
                </span>
              </div>
            </div>

            <div className="card-footer">
              <span>
                Ready when you are.
              </span>

              <button
                onClick={
                  startInterview
                }
              >
                Begin

                <ArrowRight size={16} />
              </button>
            </div>
          </div>
        </section>

        <section className="feature-section">
          <div className="section-heading">
            <p className="eyebrow">
              HOW FIRSTROUND WORKS
            </p>

            <h2>
              Prepare with purpose.
            </h2>
          </div>

          <div className="feature-grid">
            <div className="feature-card">
              <div className="feature-number">
                01
              </div>

              <FileText size={25} />

              <h3>
                Understand your profile
              </h3>

              <p>
                Your resume and job
                description are used to
                understand the skills the
                interview should focus on.
              </p>
            </div>

            <div className="feature-card">
              <div className="feature-number">
                02
              </div>

              <Mic size={25} />

              <h3>
                Practice the interview
              </h3>

              <p>
                Answer realistic
                questions designed around
                your actual experience and
                target role.
              </p>
            </div>

            <div className="feature-card">
              <div className="feature-number">
                03
              </div>

              <Target size={25} />

              <h3>
                Get evaluated
              </h3>

              <p>
                Receive structured
                feedback covering
                technical performance,
                communication and job
                alignment.
              </p>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;

