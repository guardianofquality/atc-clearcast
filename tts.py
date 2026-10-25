"""Text-To-Speech worker and speech queue handling."""

import queue
import subprocess
import sys
import threading
from typing import Optional


class TTSService:
    """Manages an asynchronous speech queue and executes TTS sequentially."""

    def __init__(self, speech_rate: int = 175):
        self.speech_rate = speech_rate
        self.queue: "queue.Queue[Optional[str]]" = queue.Queue()
        self.use_mac_say = sys.platform == "darwin"
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Starts the background speech worker thread."""
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def speak(self, phrase: str):
        """Enqueue a phrase for speaking."""
        if phrase:
            self.queue.put(phrase)

    def stop(self):
        """Signal the worker to stop and wait for completion."""
        self.queue.put(None)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _worker(self):
        engine = None
        if not self.use_mac_say:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", self.speech_rate)

        while True:
            phrase = self.queue.get()
            if phrase is None:
                break
            try:
                if self.use_mac_say:
                    subprocess.run(["say", "-r", str(self.speech_rate), phrase], check=False)
                elif engine:
                    engine.say(phrase)
                    engine.runAndWait()
            except Exception as e:
                print(f"[TTS Error] {e}", file=sys.stderr)
            finally:
                self.queue.task_done()
