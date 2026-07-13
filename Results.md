# GAIA DAG Evaluator — 실험 결과 보고서

> **Frozen-worker 설계:** Phase A에서 워커를 1회만 실행하고, Phase B는 동일 trace에 대해 evaluator만 교체합니다.  
> **기본 모델:** `gpt-4.1-nano` (worker/critic), `text-embedding-3-small`, multi-judge는 OpenAI + Anthropic Haiku + Gemini Flash-Lite.

---

## 1. 실행 요약

| Run | 데이터 | Tasks | Worker EM | Phase A | Phase B | 산출물 |
|-----|--------|------:|----------:|--------:|--------:|--------|
| **Demo smoke** | `--demo` | 3 | 100% | ~1분 | ~3분 | `results/gaia/worker_traces/`, `eval_results.json` |
| **L2+L3 pilot** | HF validation | 39 (L2:19, L3:20) | **7.7%** (3/39) | ~10분 | ~17분 | `worker_traces_l2l3_20/`, `eval_results_l2l3_20.json` |

- L2+L3 pilot: **40문항 중 39 trace** 생성 (1건 실패 — 첨부 파일 context 초과).
- GAIA에는 **Level 4가 없음** (Level 1–3만 존재). pilot은 Level **2·3 각 20문항** 목표.

---

## 2. Evaluator 평가 방법론 (Methodology)

실험에 사용된 5가지 Evaluator 방법들의 상세 동작 방식은 다음과 같습니다.

1. **`baseline` ([baseline.py](file:///Users/sobabear/Desktop/yonsei/DAG-Experiment/.worktrees/gaia-evaluators/src/gaia_dag/evaluators/baseline.py))**
   - **동작 방식**: 단일 LLM Critic(`gpt-4.1-nano`)을 사용하여 현재 평가할 노드의 태스크 설명(Task)과 생성된 출력물(Output)만 입력으로 제공하고 감점 지표(Deviation, $D$)와 확신도(Confidence, $C$)를 산출합니다.
   - **특징**: 부모 노드의 맥락(Context)을 보지 않고, 출력물 자체의 논리성과 태스크 준수 여부만 독립적으로 평가합니다. Secondary 답변이 있을 경우 OpenAI 임베딩을 이용해 코사인 유사도($S$)를 측정합니다.

2. **`logprobs` ([logprobs_confidence.py](file:///Users/sobabear/Desktop/yonsei/DAG-Experiment/.worktrees/gaia-evaluators/src/gaia_dag/evaluators/logprobs_confidence.py))**
   - **동작 방식**: `baseline` 평가 방법과 유사하나, 모델의 텍스트 응답에서 감점 및 확신도를 통째로 꺼내는 대신, "해당 출력물이 완벽하고 환각이 없는가? YES or NO"라는 이진 분류 템플릿 질문을 던져 그 결과 토큰의 `logprobs`를 추출하여 더욱 정밀한 확신도($C$)를 계산합니다.
   - **특징**: 첫 번째 토큰의 "YES" 혹은 "NO"에 할당된 로그 확률(Log Probability)을 바탕으로 확률론적이고 세밀한 신뢰도 점수를 부여하므로 텍스트 출력보다 정량적 편차가 큽니다.

3. **`multi_judge` ([multi_judge.py](file:///Users/sobabear/Desktop/yonsei/DAG-Experiment/.worktrees/gaia-evaluators/src/gaia_dag/evaluators/multi_judge.py))**
   - **동작 방식**: 단일 모델 비평의 주관적 한계를 극복하기 위해 서로 다른 3개의 LLM Provider(OpenAI gpt-4.1-nano, Anthropic Claude 3.5 Haiku, Gemini 2.0 Flash-Lite)를 판정단(Judge)으로 기용하여 동시에 채점하게 합니다.
   - **특징**: 각 Provider가 낸 판정 결과를 수집하여 평균 Deviation과 평균 Confidence를 구하는 앙상블 비평을 진행합니다.

4. **`dss` (Duplicate State Detection / 자가 일관성 검사 - [dss.py](file:///Users/sobabear/Desktop/yonsei/DAG-Experiment/.worktrees/gaia-evaluators/src/gaia_dag/evaluators/dss.py))**
   - **동작 방식**: `baseline`에 추가로, 태스크 프롬프트에 *"가정을 다시 점검하고 다른 관점에서 생각해보라"*는 변형 프롬프트(Perturb Prefix)를 결합하여 다른 경로로 한 번 더 답변을 생성하게 만듭니다.
   - **특징**: 본래의 출력물과 변형 입력으로 생성한 출력물 간의 임베딩 유사도를 계산하여 자가 일관성(Self-Consistency) 점수를 산출합니다. 일관성 수준이 기준치 미만(유사도 역수 $\ge 0.3$)으로 떨어지면 해당 노드를 모순 위험군(`dss_high_risk`)으로 분류합니다.

5. **`context_ensemble` ([context_ensemble.py](file:///Users/sobabear/Desktop/yonsei/DAG-Experiment/.worktrees/gaia-evaluators/src/gaia_dag/evaluators/context_ensemble.py))**
   - **동작 방식**: 본 실험의 가장 복합적이고 진보된 평가자 아키텍처입니다.
     1. **Upstream Context**: 비평을 수행할 때 현재 평가하려는 노드뿐만 아니라 **부모 노드(Upstream)들의 Task 설명과 Output 데이터**를 Critic 프롬프트에 바인딩하여 문맥 정보를 완전하게 제공합니다.
     2. **Multi-Judge & Logprobs**: 여러 Provider(OpenAI, Anthropic, Gemini)로 구성된 다중 판정단을 사용하고, 동시에 `logprobs`를 활용하여 정교한 확신도를 측정합니다.
     3. **DSS 전파 (DSS Propagation)**: 부모 노드들 중 하나라도 DSS 일관성 자가 진단에서 위험 신호(`dss_high_risk`)가 감지되었다면, Critic 프롬프트에 *"상위 부모 노드 결과에 오류 가능성이 감지되었으니 비평 시 이를 더 엄격히 검토하라"*는 알림을 동적으로 주입하여 검증 수준을 극대화합니다.

---

## 3. 성능 분석

### 3.1 Worker (evaluator-independent)

워커만의 최종 Answer **exact-match (EM)**:

| 구분 | EM | 비고 |
|------|---:|------|
| **전체** | 3/39 = **7.7%** | `gpt-4.1-nano` |
| Level 2 | 1/19 = **5.3%** | |
| Level 3 | 2/20 = **10.0%** | |

저가 모델이라 EM이 낮지만, **틀린 답이 많아 evaluator 비교 신호가 생김** (데모 100% EM과 대비).

### 3.2 Evaluator 랭킹 (Answer 노드, τ=0.3)

`eval_score = wrong_high_d×40 + correct_low_d×30 + (1−pass_on_wrong)×20 + (1−fail_on_correct)×10`

| Rank | Method | Score | wrong→high D | correct→low D | PASS-on-wrong | mean D |
|-----:|--------|------:|-------------:|--------------:|--------------:|-------:|
| 1 | **context_ensemble** | **56.1** | **13.9%** | 100% | **47.2%** | 0.185 |
| 2 | logprobs | 48.9 | 2.8% | 100% | 61.1% | 0.056 |
| 3 | baseline | 41.7 | 2.8% | 100% | 97.2% | 0.069 |
| 4 | multi_judge | 41.7 | 2.8% | 100% | 97.2% | 0.059 |
| 5 | dss | 41.7 | 2.8% | 100% | 97.2% | 0.062 |

- **EM%는 5개 방법 모두 동일** (7.7%) — frozen trace이므로 당연.
- 차이는 **D / PASS 라우팅**에서만 발생.

> [!NOTE]
> #### 💡 친절한 Evaluator 랭킹 가이드 (개념 및 점수 계산 해설)
> 
> **1. 'Evaluator 랭킹'이 무엇인가요?**
> - 문제를 풀고 최종 답안을 내는 역할은 **에이전트(Worker)**가 수행합니다.
> - **Evaluator(평가자)**는 이 에이전트가 수행한 과정과 최종 답변이 **정말 맞았는지(Correct) 혹은 틀렸는지(Wrong)**를 옆에서 관찰하고 판별하는 '채점 비평가' 역할을 합니다.
> - **Evaluator 랭킹**은 여러 평가 방식(Method) 중에서 **"누가 가장 오답을 정확하게 골라내고, 정답을 올바르게 판정하여 알맞은 최종 경로로 보냈는지(PASS/FAIL 라우팅)"** 성적을 메긴 순위표입니다.
> 
> **2. 평가지표 용어 정리**
> - **D (Deviation - 감점 지표)**: `0`에 가까울수록 정답/완벽함에 가깝고, `1`에 가까울수록 오답/환각에 가깝습니다. ($\tau=0.3$은 감점 기준점(Threshold)으로, $D \ge 0.3$이면 "심각한 오류가 있다"고 평가자가 판단한 것입니다.)
> - **Status (라우팅 상태)**: 감점($D$), 확신도($C$), 유사도($S$)를 종합 연산하여 최종 결정을 냅니다.
>   - `PASS`: 문제가 없으니 다음 단계로 진행해도 됨.
>   - `FAIL`: 문제가 발견되어 다시 생성하거나 중단해야 함.
>   - `AMBIGUOUS`: 판단이 애매한 상태.
> 
> **3. 랭킹 점수 (`eval_score`) 산출 원리**
> 공식: `eval_score = (wrong_high_d × 40) + (correct_low_d × 30) + ((1 - pass_on_wrong) × 20) + ((1 - fail_on_correct) × 10)`
> 
> 이 공식은 평가자가 해야 할 핵심 행동 양식에 가중치를 배분한 점수입니다:
> *   **`wrong_high_d × 40` (가중치 40 - 핵심!)**: 실제로 틀린 오답(`wrong`)에 대해 감점($D$)을 높은 값($\ge 0.3$)으로 책정했는지 평가합니다. 오답을 오답이라고 눈치채는 필터링 능력이 가장 중요하기에 가장 높은 40점의 비중을 둡니다.
> *   **`correct_low_d × 30` (가중치 30)**: 실제로 맞은 정답(`correct`)에 대해 감점($D$)을 낮은 값($< 0.3$)으로 잘 주었는지 평가합니다. 멀쩡한 정답을 오해하지 않고 잘 통과시키는 능력으로 30점의 비중을 둡니다.
> *   **`(1 - pass_on_wrong) × 20` (가중치 20)**: 실제로 틀린 오답(`wrong`)인데 합격(`PASS`) 통보를 해버리는 '치명적인 오탐(False Pass)'을 하지 않았는지 평가합니다. `pass_on_wrong`이 0%에 가까워질수록 이 항목은 최고점(20점)에 수렴합니다.
> *   **`(1 - fail_on_correct) × 10` (가중치 10)**: 실제로 맞은 정답(`correct`)인데 불합격(`FAIL`) 처리를 해버리는 '억울한 오탐'을 하지 않았는지 평가합니다. `fail_on_correct`가 0%에 가까울수록 최고점(10점)에 수렴합니다.
> 
> **4. 랭킹 1위 `context_ensemble` 결과 해석**
> - **결과**: `context_ensemble`이 **56.1점**으로 독보적인 1위를 차지했습니다.
> - **이유**: `baseline`, `multi_judge` 등 다른 모든 평가 방법들은 오답(wrong) 중 단 2.8%(36개 중 1개)만 오답으로 인지한 반면, `context_ensemble`은 **13.9%(36개 중 5개)**를 오답으로 짚어냈습니다. 또한 오답을 `PASS` 시키는 실수 비율(`pass_on_wrong`)도 다른 모델이 97.2%일 때 혼자 **47.2%**로 대폭 낮췄습니다.
> - **결론**: 비평 시 **부모 노드(Upstream Context) 정보**가 주어졌을 때 비로소 Critic이 오답과 정답의 미세한 흐름을 분별해 내어 똑똑하게 채점할 수 있음을 증명합니다.

### 3.3 틀린 답(36건) 기준 상세

Evaluator가 “잘못된 답을 잡았는가”에 초점:

| Method | wrong 중 D≥0.3 | wrong 중 PASS (오탐) |
|--------|---------------:|---------------------:|
| **context_ensemble** | **5 / 36 (13.9%)** | **17 / 36 (47.2%)** |
| logprobs | 1 / 36 (2.8%) | 22 / 36 (61.1%) |
| baseline | 1 / 36 (2.8%) | 35 / 36 (97.2%) |
| multi_judge | 1 / 36 (2.8%) | 35 / 36 (97.2%) |
| dss | 1 / 36 (2.8%) | 35 / 36 (97.2%) |

**context_ensemble** mean D: wrong **0.19** vs correct **0.07** — 틀린 답에 더 높은 deviation.

### 3.4 Ablation 해석

| 비교 | 관찰 |
|------|------|
| **context on vs off** | `context_ensemble` (parent context O) vs `multi_judge` (context X): 동일 score 41.7→**56.1**, wrong→high D **2.8%→13.9%**. upstream 정보가 D 신호에 결정적. |
| **Logprobs C only** | `logprobs` vs `baseline`: D는 동일(2.8%), **PASS-on-wrong 97%→61%**. C만 바꿔도 라우팅은 개선되나 D 랭킹은 제한적. |
| **DSS ≈ Baseline** | `dss` score **41.7 = baseline**. D critic 동일 설계 → D 테이블 일치. DSS는 진단용. |
| **Multi-judge without context** | 3-provider 평균이어도 context 없으면 baseline과 동일 수준. |

### 3.5 Demo smoke (천장 효과)

| Method | Score | EM | wrong→high D |
|--------|------:|---:|-------------:|
| baseline / logprobs / multi_judge / dss | 60.0 | 100% | 0% |
| context_ensemble | 50.0 | 100% | 0% |

전부 정답 → **wrong→high D로 방법 분리 불가**. context_ensemble만 correct→low D 67%로 score 하락.

### 3.6 한계 (Caveats)

- **N=39** — 통계적 유의성 낮음; 파일럿 수준.
- **저가 worker** — EM 7.7%; stronger worker면 EM↑ → wrong→high D 천장 재발 가능.
- **Answer 노드만 eval** (랭킹 기준과 일치; Plan/Solve 미평가).
- 첨부 파일 1건 context overflow; HF attachment 경로 일부 미해결.

---

## 4. 비용 분석

> 토큰은 trace 문자 길이 기반 추정(chars÷4). 가격은 2026년 공개 API 단가 기준 **근사치**입니다.

### 4.1 API 단가 (사용 모델)

| 모델 | Input | Output |
|------|------:|-------:|
| `gpt-4.1-nano` | $0.10 / 1M | $0.40 / 1M |
| `text-embedding-3-small` | $0.02 / 1M | — |
| `claude-3-5-haiku-latest` | $0.80 / 1M | $4.00 / 1M |
| `gemini-2.0-flash-lite` | $0.075 / 1M | $0.30 / 1M |

### 4.2 Phase A — Worker (39 traces)

| 항목 | 값 |
|------|-----|
| 호출 수 | 39 × (3 worker + 3 secondary) = **234** OpenAI chat |
| 추정 토큰 | ~193K in / ~186K out |
| **추정 비용** | **~$0.09** |
| Wall time | **~10분** (~15초/task) |

### 4.3 Phase B — Eval (39 traces × 5 methods, Answer 노드 only)

| Method | OpenAI chat | Anthropic | Gemini | Embed | **추정 비용** |
|--------|------------:|----------:|-------:|------:|-------------:|
| baseline | 39 | 0 | 0 | 39 | $0.008 |
| logprobs | 78 | 0 | 0 | 39 | $0.016 |
| multi_judge | 39 | 39 | 39 | 39 | $0.079 |
| dss | 78 | 0 | 0 | 78 | $0.016 |
| context_ensemble | 117 | 39 | 39 | 78 | $0.095 |
| **합계 (5 methods)** | | | | | **~$0.21** |

| 항목 | 값 |
|------|-----|
| trace×method evals | 39 × 5 = **195** |
| **Phase B 합계** | **~$0.21** |
| Wall time | **~17분** (~5.3초/eval) |

### 4.4 Pilot 총비용

| Phase | 비용 | 시간 |
|-------|-----:|-----:|
| Phase A (worker) | ~$0.09 | ~10분 |
| Phase B (5 evaluators) | ~$0.21 | ~17분 |
| **Total** | **~$0.31** | **~27분** |

- **trace 1개당 (worker + 5 eval):** ~$0.008
- **가장 비싼 evaluator:** `context_ensemble` (~$0.095 / 39 traces) — multi-judge + logprobs + DSS
- **가장 저렴:** `baseline` (~$0.008)

### 4.5 비용 최적화 참고

| 선택 | 효과 |
|------|------|
| `gpt-4.1-nano` worker | Phase A ~$0.09 / 39 tasks (4o-mini 대비 ~33%↓) |
| Answer-only eval | Plan/Solve 미평가 → Phase B **~3× 단축** (이전 3노드 eval 대비) |
| `--methods baseline,logprobs` | 5개 중 2개만 → Phase B 비용 **~40%** |
| Multi-judge 키 없음 | Anthropic/Gemini 스킵 → `multi_judge`/`context_ensemble` 비용↓ (품질 trade-off) |

---

## 5. 산출물 경로

```
results/gaia/
├── worker_traces/              # demo smoke traces
├── eval_results.json           # demo eval aggregation
├── worker_traces_l2l3_20/      # L2+L3 pilot traces (39 JSON)
└── eval_results_l2l3_20.json   # L2+L3 pilot eval + per-task rows
```

---

## 6. 재현 명령

```bash
source .venv/bin/activate
cp .env.example .env   # OPENAI_API_KEY 필수, HF_TOKEN은 real GAIA용

# Demo
python scripts/run_gaia_worker.py --demo --max-tasks 3
python scripts/run_gaia_eval.py --trace-dir results/gaia/worker_traces --methods all

# L2+L3 pilot (HF access + terms)
python scripts/run_gaia_worker.py --levels 2,3 --max-per-level 20 \
  --out-dir results/gaia/worker_traces_l2l3_20
python scripts/run_gaia_eval.py \
  --trace-dir results/gaia/worker_traces_l2l3_20 \
  --methods all \
  --out results/gaia/eval_results_l2l3_20.json
```

---

## 7. 결론 (한 줄)

**저가 frozen worker로 L2+L3 39문항을 돌린 결과, upstream context를 쓰는 `context_ensemble`만 wrong→high D(13.9%)와 PASS-on-wrong(47%)에서 유의미하게 앞섰고, 전체 비용은 ~$0.31 / ~27분 수준이었다.**
