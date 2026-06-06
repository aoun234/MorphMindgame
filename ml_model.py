# ─── ml_model.py  v5.1 ───────────────────────────────────────────
"""
Two-layer real-time movement predictor  —  Final Production Version

WHY NOT Q-LEARNING:
  Q-Learning is a reinforcement learning algorithm that requires thousands
  of training episodes in a simulated environment before it can make useful
  predictions. In a single game session a player makes ~200-500 moves total.
  Q-Learning would never converge meaningfully in that time. It also needs
  a full state-action-reward loop which adds significant complexity for
  no benefit in this scenario.

  Logistic Regression + Markov Chain is the correct choice because:
    • Logistic Regression trains in milliseconds on 30-100 samples
    • 2nd-order Markov chain works immediately with just 20 samples
    • Both can update incrementally every ~280 frames during gameplay
    • They predict the exact output we need: next direction (0-4)
    • They generalise well for pattern-based player movement

Layer 1 — 2nd-order Markov Chain
    Works with 20+ samples. Fast O(1) lookup.
    Stores bigram (prev2, prev1) → Counter of next moves.
    Returns most-common next move for seen bigrams.

Layer 2 — Logistic Regression  (sklearn)
    Needs 28+ samples (WINDOW + 20).  Uses StandardScaler.
    WINDOW-length feature vector. Uses predict_proba for confidence.
    Only used when max class probability ≥ 0.38.

Decision priority:
  1. LR if sklearn present + model trained + confidence ≥ 0.38
  2. Markov fallback
  3. Most common recent move (last resort)

Public interface:
  .trained         bool  — True once any layer ready (signals PREDICT ok)
  .confidence      float — LR mean-max probability [0, 1]
  .confidence_pct  int   — confidence * 100 for footer bar
  .last_pred       int   — last predicted direction
  .model           LogisticRegression or None
  .scaler          StandardScaler or None
  .train(history)  — call periodically to update
  .predict(history)— call each PREDICT frame
  .dir_to_delta(d) — static, int → (dc, dr)
"""
import numpy as np
from collections import Counter

WINDOW = 8   # exported; used by enemy._ml_confident()

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    SK = True
except ImportError:
    SK = False


class MovementPredictor:
    def __init__(self):
        self.model      = None     # LogisticRegression instance or None
        self.scaler     = None     # StandardScaler instance or None
        self.trained    = False    # True once Markov or LR is ready
        self.confidence = 0.0      # LR mean-max probability [0, 1]
        self.last_pred  = 0        # last returned direction (0-4)
        self._markov    = {}       # bigram → Counter(next_move → count)

    # ── Training ─────────────────────────────────────────────────
    def train(self, history):
        h = list(history)
        self._train_markov(h)
        if SK and len(h) >= WINDOW + 20:
            self._train_lr(h)
        elif len(h) >= 20:
            self.trained = True   # Markov alone is sufficient

    def _train_markov(self, h):
        m = {}
        for i in range(len(h) - 2):
            key = (h[i], h[i+1])
            m.setdefault(key, Counter())[h[i+2]] += 1
        self._markov = m

    def _train_lr(self, h):
        X, y = [], []
        for i in range(len(h) - WINDOW):
            X.append(h[i:i+WINDOW])
            y.append(h[i+WINDOW])
        X, y = np.array(X), np.array(y)
        if len(np.unique(y)) < 2:
            return
        try:
            sc   = StandardScaler()
            Xs   = sc.fit_transform(X)
            lr   = LogisticRegression(max_iter=400, C=1.5)
            lr.fit(Xs, y)
            probs           = lr.predict_proba(Xs)
            self.confidence = float(np.mean(np.max(probs, axis=1)))
            self.model      = lr
            self.scaler     = sc
            self.trained    = True
        except Exception:
            pass  # keep Markov-only; trained unchanged

    # ── Prediction ───────────────────────────────────────────────
    def predict(self, history):
        """Return predicted next direction integer (0-4)."""
        h = list(history)
        if len(h) < 2:
            return 0

        # Layer 2: Logistic Regression
        if SK and self.model is not None and self.scaler is not None:
            if len(h) >= WINDOW:
                try:
                    feat  = np.array(h[-WINDOW:]).reshape(1, -1)
                    feats = self.scaler.transform(feat)
                    probs = self.model.predict_proba(feats)[0]
                    bi    = int(np.argmax(probs))
                    if probs[bi] >= 0.38:
                        self.last_pred = int(self.model.classes_[bi])
                        return self.last_pred
                except Exception:
                    pass

        # Layer 1: Markov chain
        key = (h[-2], h[-1])
        if key in self._markov and self._markov[key]:
            self.last_pred = self._markov[key].most_common(1)[0][0]
            return int(self.last_pred)

        # Last resort: most common recent move
        self.last_pred = Counter(h[-15:]).most_common(1)[0][0]
        return int(self.last_pred)

    # ── Properties ───────────────────────────────────────────────
    @property
    def confidence_pct(self):
        """Integer 0-100 for the footer ML confidence bar."""
        return int(self.confidence * 100)

    @staticmethod
    def dir_to_delta(d):
        """Map direction integer → (dcol, drow)."""
        return {0:(0,0), 1:(0,-1), 2:(0,1), 3:(-1,0), 4:(1,0)}.get(d, (0,0))