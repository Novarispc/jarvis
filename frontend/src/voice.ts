/**
 * Voice input (Web Speech API) and audio output (AudioContext) for JARVIS.
 */

// ---------------------------------------------------------------------------
// Speech Recognition
// ---------------------------------------------------------------------------

export interface VoiceInput {
  start(): void;
  stop(): void;
  pause(): void;
  resume(): void;
  setLang(langCode: string): void;
  getLang(): string;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
declare const webkitSpeechRecognition: any;

export function createVoiceInput(
  onTranscript: (text: string, lang: string) => void,
  onError: (msg: string) => void
): VoiceInput {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const SR = (window as any).SpeechRecognition || (typeof webkitSpeechRecognition !== "undefined" ? webkitSpeechRecognition : null);
  if (!SR) {
    onError("Speech recognition not supported in this browser");
    return { start() {}, stop() {}, pause() {}, resume() {}, setLang() {}, getLang() { return "en-US"; } };
  }

  const recognition = new SR();
  recognition.continuous = true;
  recognition.interimResults = false;   // final results only — avoids noise mid-word
  recognition.maxAlternatives = 1;

  // Read language from localStorage (set by settings panel)
  const storedLang = localStorage.getItem("jarvis-lang") || "en-US";
  recognition.lang = storedLang;

  let shouldListen = false;
  let paused = false;
  let restartTimer: ReturnType<typeof setTimeout> | null = null;

  function scheduleRestart(delayMs = 300) {
    if (restartTimer) return;
    restartTimer = setTimeout(() => {
      restartTimer = null;
      if (shouldListen && !paused) {
        try { recognition.start(); } catch { /* already started */ }
      }
    }, delayMs);
  }

  // Noise-rejection: single common filler words that background audio triggers
  const NOISE_WORDS = new Set([
    "the","a","an","and","or","but","so","yeah","yes","no","okay","ok",
    "um","uh","hmm","hm","oh","ah","hey","hi","bye","right","like",
  ]);

  recognition.onresult = (event: any) => {
    for (let i = event.resultIndex; i < event.results.length; i++) {
      if (!event.results[i].isFinal) continue;

      const alt   = event.results[i][0];
      const text  = alt.transcript.trim();
      const conf  = alt.confidence as number;   // 0–1; may be 0 if browser doesn't report it
      const words = text.split(/\s+/).filter(Boolean);

      // Reject if confidence is reported AND below threshold
      if (conf > 0 && conf < 0.45) continue;

      // Reject single-word noise triggers
      if (words.length === 1 && NOISE_WORDS.has(words[0].toLowerCase())) continue;

      // Reject very short utterances (likely ambient sound)
      if (words.length < 2 && text.length < 4) continue;

      if (text) onTranscript(text, recognition.lang);
    }
  };

  recognition.onend = () => {
    if (shouldListen && !paused) scheduleRestart(300);
  };

  recognition.onerror = (event: any) => {
    if (event.error === "not-allowed") {
      onError("Microphone access denied. Please allow microphone access.");
      shouldListen = false;
    } else if (event.error === "network") {
      // Google's STT rejected a too-fast reconnect — back off and retry
      scheduleRestart(1000);
    } else if (event.error === "no-speech" || event.error === "aborted") {
      // Normal/expected — onend will handle restart
    } else {
      console.warn("[voice] recognition error:", event.error);
    }
  };

  return {
    start() {
      shouldListen = true;
      paused = false;
      try {
        recognition.start();
      } catch {
        // Already started
      }
    },
    stop() {
      shouldListen = false;
      paused = false;
      if (restartTimer) { clearTimeout(restartTimer); restartTimer = null; }
      recognition.stop();
    },
    pause() {
      paused = true;
      if (restartTimer) { clearTimeout(restartTimer); restartTimer = null; }
      recognition.stop();
    },
    resume() {
      paused = false;
      if (shouldListen) {
        try {
          recognition.start();
        } catch {
          // Already started
        }
      }
    },
    setLang(langCode: string) {
      // Stop recognition, update lang, restart — no page reload needed
      recognition.stop();
      recognition.lang = langCode;
      localStorage.setItem("jarvis-lang", langCode);
      if (restartTimer) { clearTimeout(restartTimer); restartTimer = null; }
      if (shouldListen && !paused) {
        scheduleRestart(200);
      }
    },
    getLang() {
      return recognition.lang as string;
    },
  };
}

// ---------------------------------------------------------------------------
// Audio Player
// ---------------------------------------------------------------------------

export interface AudioPlayer {
  enqueue(base64: string): Promise<void>;
  stop(): void;
  getAnalyser(): AnalyserNode;
  onFinished(cb: () => void): void;
}

export function createAudioPlayer(): AudioPlayer {
  const audioCtx = new AudioContext();
  const analyser = audioCtx.createAnalyser();
  analyser.fftSize = 256;
  analyser.smoothingTimeConstant = 0.8;
  analyser.connect(audioCtx.destination);

  const queue: AudioBuffer[] = [];
  let isPlaying = false;
  let currentSource: AudioBufferSourceNode | null = null;
  let finishedCallback: (() => void) | null = null;

  function playNext() {
    if (queue.length === 0) {
      isPlaying = false;
      currentSource = null;
      finishedCallback?.();
      return;
    }

    isPlaying = true;
    const buffer = queue.shift()!;
    const source = audioCtx.createBufferSource();
    source.buffer = buffer;
    source.connect(analyser);
    currentSource = source;

    source.onended = () => {
      if (currentSource === source) {
        playNext();
      }
    };

    source.start();
  }

  return {
    async enqueue(base64: string) {
      // Resume audio context (browser autoplay policy)
      if (audioCtx.state === "suspended") {
        await audioCtx.resume();
      }

      try {
        const binary = atob(base64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
          bytes[i] = binary.charCodeAt(i);
        }
        const audioBuffer = await audioCtx.decodeAudioData(bytes.buffer.slice(0));
        queue.push(audioBuffer);
        if (!isPlaying) playNext();
      } catch (err) {
        console.error("[audio] decode error:", err);
        // Skip bad audio, continue
        if (!isPlaying && queue.length > 0) playNext();
      }
    },

    stop() {
      queue.length = 0;
      if (currentSource) {
        try {
          currentSource.stop();
        } catch {
          // Already stopped
        }
        currentSource = null;
      }
      isPlaying = false;
    },

    getAnalyser() {
      return analyser;
    },

    onFinished(cb: () => void) {
      finishedCallback = cb;
    },
  };
}
