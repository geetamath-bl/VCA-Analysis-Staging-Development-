# 4. Scoring methodology

Everything in this document comes from `vca_code/scorer.py`, with the metric
definitions from `metrics_calculator.py`, `pitch_analyzer.py` and
`vocab_grammar_analyzer.py`.

---

## 4.1 The model

Five independent dimensions, each scored 0–100, combined as a weighted sum.

```
overall = 0.20·pace + 0.25·fluency + 0.15·filler
        + 0.20·expressiveness + 0.20·vocab_grammar
```

| Dimension | Weight | Question it answers |
|---|---|---|
| Fluency | **25 %** | Does the speech flow, or does it stall? |
| Pace | 20 % | Is the speaking rate comfortable for a listener? |
| Expressiveness | 20 % | Is the delivery alive, or monotone? |
| Vocabulary & Grammar | 20 % | Is the language rich and correct? |
| Filler words | 15 % | Is the speech cluttered with "um" and "uh"? |

The weights sum to exactly 1.00. Fluency carries the most weight because
stalling is the single most noticeable defect to a listener; filler words carry
the least because a few are normal in natural speech.

---

## 4.2 Pace — 20 %

**Input:** `wpm = total_words / total_duration_sec × 60`

Note this is *gross* words per minute: it includes pause time. The alternative,
`articulation_rate`, excludes pauses and is computed and stored but **not used
by the scorer** — pause behaviour is already penalised by the fluency
dimension, so counting it twice would double-dip.

| WPM | Score |
|---|---|
| 120 – 160 | **100** |
| 100 – 119 or 161 – 180 | 80 |
| 80 – 99 or 181 – 200 | 60 |
| < 80 or > 200 | 40 |

The 120–160 target window reflects the conventional guidance for clear
presentation speech. The bands are symmetric around it, so speaking too slowly
and speaking too quickly are penalised equally.

```python
def _score_pace(self, wpm):
    if   120 <= wpm <= 160:                  return 100
    elif 100 <= wpm < 120 or 160 < wpm <= 180: return 80
    elif  80 <= wpm < 100 or 180 < wpm <= 200: return 60
    else:                                     return 40
```

---

## 4.3 Fluency — 25 %

**Inputs:** `num_pauses`, `long_pauses`, `total_duration_sec`

A pause is an acoustic gap longer than **0.3 s** between non-silent intervals,
detected with `librosa.effects.split(y, top_db=30)`. A pause longer than
**1.5 s** is additionally counted as "long".

```
pauses_per_min = num_pauses / (total_duration_sec / 60)
```

| Pauses per minute | Base |
|---|---|
| ≤ 6 | **100** |
| 7 – 10 | 80 |
| 11 – 15 | 60 |
| > 15 | 40 |

Then:

```
fluency = max(0, base − 10 × long_pauses)
```

The long-pause penalty is **absolute, not rate-normalised**, which has a sharp
consequence: six long pauses zero out even a perfect base score, regardless of
whether the recording is one minute or ten. On a long recording this makes
fluency the harshest dimension in the rubric. Rate-normalising the penalty
(`long_pauses / minutes`) would be the natural fix if that proves too severe in
practice.

Fluency is also the only dimension that can reach **0**.

---

## 4.4 Filler words — 15 %

**Input:** `filler_ratio = filler_count / total_words × 100`

Counted filler words (`MetricsCalculator.FILLER_WORDS`):

```
um   uh   umm   uhh   like   you know
actually   basically   literally   so
```

| Filler ratio | Score |
|---|---|
| ≤ 2 % | **100** |
| 2.1 – 5 % | 80 |
| 5.1 – 8 % | 60 |
| 8.1 – 12 % | 40 |
| > 12 % | 20 |

Two measurement caveats that affect this score directly:

1. **`"you know"` never matches.** The tokeniser (`\b[a-zA-Z']+\b`) emits single
   words, so the two-word entry is dead code. Real "you know" fillers are
   invisible to the score.
2. **`like` and `so` are counted unconditionally.** "I would *like* to explain"
   and "*So* the array stores…" are legitimate uses, counted as fillers. On
   technical speech this inflates the ratio and depresses the score. A
   part-of-speech check, or dropping these two from the set, would be the fix.

The score also depends on the transcription prompt explicitly instructing
Gemini to preserve fillers — most STT systems strip them, which would make this
dimension return a flat 100 for everyone.

---

## 4.5 Expressiveness — 20 %

**Inputs:** `pitch_cv_percent`, `volume_cv_percent`

Both are **coefficients of variation** — standard deviation as a percentage of
the mean:

```
pitch_cv  = std(F0) / mean(F0)  × 100      # F0 from librosa.pyin, unvoiced frames dropped
volume_cv = std(RMS) / mean(RMS) × 100     # per-frame RMS energy
```

Using CV rather than raw standard deviation is what makes the metric fair
across voices: a deep voice and a high voice with equally varied intonation
produce the same CV. Raw Hz spread would systematically favour higher-pitched
speakers.

This is the only **continuous** scorer. Each CV is scored against a target
window with asymmetric decay outside it:

```python
def sub_score(cv, low, high):
    if low <= cv <= high:  return 100
    elif cv < low:         return max(30, 100 - (low - cv) * 3)
    else:                  return max(30, 100 - (cv - high) * 1.5)
```

| Signal | Target window | Below-window slope | Above-window slope |
|---|---|---|---|
| Pitch CV | 15 – 35 % | −3 per point | −1.5 per point |
| Volume CV | 20 – 50 % | −3 per point | −1.5 per point |

```
expressiveness = 0.6 × pitch_component + 0.4 × volume_component
```

Two deliberate asymmetries:

- **Monotone is punished twice as hard as over-animation** (slope 3 vs 1.5).
  Flat delivery is the defect this dimension exists to detect; too much
  variation is merely eccentric.
- **Pitch outweighs volume, 60/40.** Intonation carries more communicative
  meaning than loudness, and RMS is more contaminated by microphone distance
  and gain than F0 is.

The floor of 30 keeps a single bad acoustic reading from destroying the
composite score.

### Worked decay example

A pitch CV of 5 % (very monotone) → `max(30, 100 − (15−5)·3) = 70`.
A pitch CV of 0 % (no voiced pitch detected at all) → `max(30, 100 − 45) = 55`.
A volume CV of 80 % (wildly uneven loudness) →
`max(30, 100 − (80−50)·1.5) = 55`.

---

## 4.6 Vocabulary & Grammar — 20 %

**Inputs:** `ttr`, `errors_per_100_words`

**Type-Token Ratio** is unique words divided by total words — a standard
lexical-diversity measure:

| TTR | Sub-score |
|---|---|
| 0.50 – 0.75 | **100** |
| 0.40 – 0.49 or 0.76 – 0.85 | 80 |
| everything else | 60 |

The band is two-sided on purpose. A *low* TTR means repetitive vocabulary. A
*very high* TTR (> 0.85) usually means the sample is too short to be
meaningful, or the speech is disjointed — not that it is impressively varied.

**Important caveat:** TTR falls naturally as transcript length grows, because
function words repeat. The 0.50–0.75 window implicitly assumes a short sample
(roughly a few minutes). On a twenty-minute recording, a perfectly articulate
speaker will land below 0.4 and be scored 60. If longer recordings matter,
switch to a length-robust measure such as MTLD or a moving-average TTR.

**Grammar errors** come from LanguageTool, normalised per 100 words:

| Errors per 100 words | Sub-score |
|---|---|
| ≤ 2 | **100** |
| 2.1 – 5 | 80 |
| 5.1 – 8 | 60 |
| 8.1 – 12 | 40 |
| > 12 | 20 |

```
vocab_grammar = 0.5 × ttr_score + 0.5 × grammar_score
```

A further caveat: LanguageTool is checking a *transcript of speech* against
written-English rules. Spoken language legitimately contains sentence fragments,
restarts and informal constructions that LanguageTool flags as errors. Expect
this dimension to read somewhat low for natural speech even from strong
speakers, and treat it as a relative signal rather than an absolute verdict.

**And a failure mode:** if LanguageTool is unreachable, `_check_grammar`
returns `(0, [])`, which scores a perfect 100 for grammar. An outage therefore
*raises* the score, silently. See [09-known-issues.md](09-known-issues.md).

---

## 4.7 Rating label

| Overall score | Rating |
|---|---|
| ≥ 85 | **Excellent** |
| 70 – 84 | **Good** |
| 50 – 69 | **Fair** |
| < 50 | **Needs Improvement** |

This is what the UI displays most prominently — the numeric score is shown
underneath in smaller type, a deliberate choice to keep users focused on the
band rather than on single-point differences that are within measurement noise.

---

## 4.8 Worked example

A three-minute technical explanation.

### Raw metrics

```json
{ "total_words": 412, "total_duration_sec": 183.42, "wpm": 134.8,
  "articulation_rate": 152.1, "num_pauses": 19, "total_pause_time": 20.11,
  "avg_pause_duration": 1.06, "long_pauses": 1,
  "filler_count": 9, "filler_ratio": 2.2 }

{ "mean_pitch_hz": 142.6, "std_pitch_hz": 31.9, "pitch_range_hz": 288.4,
  "pitch_cv_percent": 22.4, "mean_volume": 0.0412, "volume_cv_percent": 58.3 }

{ "total_words": 412, "unique_words": 251, "ttr": 0.609,
  "avg_word_length": 4.37, "grammar_error_count": 14,
  "errors_per_100_words": 3.4 }
```

### Sub-scores

| Dimension | Derivation | Score |
|---|---|---|
| Pace | 134.8 WPM lands inside 120–160 | **100** |
| Fluency | 183.42 s = 3.057 min → 19/3.057 = 6.2 pauses/min → base 80; 1 long pause → −10 | **70** |
| Filler | 2.2 % lands in 2.1–5 % | **80** |
| Expressiveness | pitch CV 22.4 inside 15–35 → 100; volume CV 58.3 above 50 → `100 − 8.3·1.5 = 87.55`; `0.6·100 + 0.4·87.55` | **95.0** |
| Vocab & Grammar | TTR 0.609 inside 0.50–0.75 → 100; 3.4 errors/100 → 80; `0.5·100 + 0.5·80` | **90** |

### Composite

```
0.20 × 100.00  =  20.000
0.25 ×  70.00  =  17.500
0.15 ×  80.00  =  12.000
0.20 ×  95.02  =  19.004
0.20 ×  90.00  =  18.000
                 ───────
                  86.504  →  86.5
```

`86.5 ≥ 85` → **Excellent**

### Response

```json
{
  "status": "success",
  "filename": "explanation_converted.wav",
  "report": {
    "pace_score": 100.0, "fluency_score": 70.0, "filler_score": 80.0,
    "expressiveness_score": 95.0, "vocab_grammar_score": 90.0,
    "overall_score": 86.5, "rating": "Excellent"
  }
}
```

Note that the composite is computed from **unrounded** sub-scores and rounded
once at the end, so summing the rounded sub-scores in the response will not
always reproduce `overall_score` exactly.

---

## 4.9 How to tune the rubric

All thresholds are class constants, so recalibration touches one file each.

| To change | Edit |
|---|---|
| Dimension weights | `VCAScorer.WEIGHTS` |
| Pace bands | `VCAScorer._score_pace` |
| Pause-rate bands, long-pause penalty | `VCAScorer._score_fluency` |
| Filler bands | `VCAScorer._score_filler_words` |
| Expressiveness windows, slopes, 60/40 blend | `VCAScorer._score_expressiveness` |
| TTR and grammar bands, 50/50 blend | `VCAScorer._score_vocab_grammar` |
| Rating cut-offs | `VCAScorer._rating_label` |
| What counts as a pause / long pause | `MetricsCalculator.PAUSE_THRESHOLD_SEC`, `LONG_PAUSE_THRESHOLD_SEC` |
| Silence sensitivity | `MetricsCalculator.TOP_DB` |
| The filler word list | `MetricsCalculator.FILLER_WORDS` |
| Pitch search range | `PitchAnalyzer.FMIN_NOTE`, `FMAX_NOTE` |

`TOP_DB = 30` deserves specific attention when calibrating: it is the single
parameter that decides what counts as silence, and it is **not** adaptive to
recording conditions. A noisy room raises the noise floor, fewer gaps clear the
30 dB threshold, and the fluency score rises spuriously. A quiet studio does
the reverse. If the system is deployed across heterogeneous recording setups,
an adaptive threshold based on the measured noise floor would make fluency far
more comparable between speakers.

---

## 4.10 Attainable ranges

Because most scorers use discrete bands with non-zero floors, the practical
range of each score is narrower than 0–100:

| Score | Minimum | Maximum | Reachable values |
|---|---|---|---|
| Pace | 40 | 100 | 40, 60, 80, 100 |
| Fluency | 0 | 100 | base ∈ {40, 60, 80, 100} minus 10 per long pause |
| Filler | 20 | 100 | 20, 40, 60, 80, 100 |
| Expressiveness | 30 | 100 | continuous |
| Vocab & Grammar | 40 | 100 | 0.5·{60,80,100} + 0.5·{20,40,60,80,100} |
| **Overall** | **25** | **100** | continuous |

The floor of 25 on the overall score is worth internalising: **no recording can
score below 25**, so "Needs Improvement" effectively spans 25–49, not 0–49. Any
report you see at or near 25 means every dimension bottomed out.

The practical consequence for interpretation is that the scale is compressed
at the bottom. Differences in the 85–100 range are driven by continuous
dimensions (expressiveness) and are meaningfully fine-grained; differences in
the 40–60 range mostly reflect band boundaries and should not be read as
precise.
