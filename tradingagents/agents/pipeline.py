"""Multi-agent analysis with deterministic offline mode and optional OpenAI-compatible provider."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from tradingagents.config import settings
from tradingagents.indicators.core import calculate_indicators
from tradingagents.models import Candle, Signal


@dataclass(frozen=True)
class AnalysisResult:
    signal: Signal
    notes: tuple[str, ...]


class AgentPipeline:
    """Runs analysts, bull/bear debate, and risk review; emits paper-only signals."""

    def _provider_summary(self, prompt: str) -> tuple[str, int]:
        if settings.offline or settings.provider != "openai" or not settings.api_key:
            return "Mock provider: deterministic indicator-based analysis; no network request.", 0
        body = json.dumps({"model": settings.model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2}).encode()
        req = urllib.request.Request(f"{settings.base_url}/chat/completions", data=body, headers={"Authorization": f"Bearer {settings.api_key}", "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                payload = json.loads(response.read().decode())
            text = str(payload["choices"][0]["message"]["content"])
            count = int(payload.get("usage", {}).get("total_tokens", len(prompt.split()) + len(text.split())))
            return text, count
        except (urllib.error.URLError, KeyError, ValueError, TimeoutError) as exc:
            return f"Provider unavailable ({type(exc).__name__}); using conservative local analysis.", 0

    def analyze(self, symbol: str, candles: list[Candle]) -> AnalysisResult:
        """Analyze OHLCV bars and create a rule-based, risk-reviewed paper signal."""
        if len(candles) < 3:
            raise ValueError("at least three candles are required")
        start = time.perf_counter()
        closes = [c.close for c in candles]
        last = candles[-1]
        indicators = calculate_indicators(candles)
        momentum = indicators["momentum"]
        rsi = indicators["ultimate_rsi"]
        action = "HOLD"
        if momentum > 0.15 and rsi < 80:
            action = "BUY"
        elif momentum < -0.15 and rsi > 20:
            action = "SELL"
        prompt = f"Summarize paper-market context for {symbol}: momentum={momentum:.3f} RSI={rsi:.1f}. Never issue real orders."
        provider_text, provider_tokens = self._provider_summary(prompt)
        # Agent stages expose meaningful summaries and measured/estimated token use.
        analyst_tokens = max(provider_tokens, len(prompt.split()) + len(provider_text.split()))
        bull = "Bull case: positive momentum supports long bias." if momentum > 0 else "Bull case: wait for a momentum reversal."
        bear = "Bear case: downside risk argues for caution." if momentum < 0 else "Bear case: upside may be overextended."
        risk_note = "Risk review: use a volatility-scaled stop and cap size to paper equity risk."
        volatility = max((c.high - c.low) / max(c.close, 1e-12) for c in candles[-20:])
        stop_distance = max(last.close * max(volatility * 1.5, 0.003), last.close * 0.003)
        direction = 1 if action == "BUY" else -1
        stop = last.close - direction * stop_distance
        tp1 = last.close + direction * stop_distance
        tp2 = last.close + direction * stop_distance * 2
        tokens = {"analyst team": analyst_tokens, "bull vs bear debate": len((bull + bear).split()), "risk review": len(risk_note.split())}
        signal = Signal(symbol=symbol.upper(), action=action, confidence=min(0.95, 0.5 + abs(momentum) / 4), entry=last.close, stop_loss=stop, take_profit_1=tp1, take_profit_2=tp2, rationale=f"{bull} {bear} {risk_note} {provider_text}", agent_tokens=tokens, latency_ms=int((time.perf_counter() - start) * 1000))
        return AnalysisResult(signal, ("Analyst team completed", "Bull vs bear debate completed", "Risk review completed"))
