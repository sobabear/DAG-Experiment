# Briefing: DAG vs Non-DAG Attribution under Internal Poison

**Date:** 2026-09-19  
**Status:** Narrative lock candidate for workshop / ACL–EMNLP Findings draft  
**Scope:** `apps/implementation-comparison` poison suite (not Artificial Analysis Index)  
**Model (main runs):** `gpt-5.6-luna`  
**Companion detail:** `results/POISON_RESULTS.md` · tables in `output/tables/`

---

## Abstract (English, paper-ready draft)

Tool-using coding agents increasingly collaborate through multi-step or multi-agent pipelines, yet little is known about how they behave when an *internal* collaborator—not an external attacker—is fed a planted lie. We study this setting with a fixed suite of controlled configuration QnA tasks and code-verifiable bug-fix tasks (hidden pytest), comparing a single-loop agent to two DAG-structured systems: a faithful contribution-backpropagation (BPD) pipeline and a hierarchical scan→implement→test graph (Yonsei). We measure accuracy, lie propagation, source attribution (detection), and recovery. Under strong agent-side injection, the single-loop agent never attributes the poison source (detection = 0) and still propagates the lie on a non-trivial fraction of tasks. A BPD-style DAG isolates and recovers substantially more often (QnA recovery ≈ 0.85–0.87; code ≈ 0.63–0.64) by scoring worker contributions with an independent judge and backward pass. Crucially, DAG *topology alone* is not sufficient: when Yonsei treats a poisoned scan node as authoritative, lie propagation on QnA exceeds the single-loop baseline (≈ 0.71 vs ≈ 0.17). Adding an explicit source-over-scan rule restores isolation and attribution for Yonsei, but through a different mechanism than BPD. Condition ablations (`none` / `document` / `agent`) show that attribution and recovery concentrate on the agent-injection path. We conclude that DAGs enlarge the design space for node-level isolation and attribution relative to single-loop agents, while contaminated-node handling—not the DAG label—determines whether that space yields recovery.

**Keywords:** multi-agent LLM, coding agents, attribution, poison / misinformation, DAG, BPD

---

## 초록 (한국어 요약)

코딩 에이전트가 협업할 때, **외부 공격이 아니라 내부 collaborator**에게 심은 거짓(planted lie)이 들어가면 어떻게 되는지를 본다. 단일 루프(general)와 두 종류의 DAG(BPD, Yonsei)를 같은 QnA·코드(숨은 pytest) 스위트에서 비교하고, 정답률·전파·출처 지목(attribution)·복구를 잰다.

- 단일 루프는 출처를 못 짚는다 (detection = 0).
- BPD형 DAG는 judge + 기여도 backprop으로 격리·복구가 크다.
- DAG **형태만**으로는 부족하다. scan을 맹신하는 Yonsei는 QnA에서 general보다 독을 더 잘 퍼뜨렸다.
- source-우선 규칙을 넣으면 Yonsei도 회복하지만, 메커니즘은 BPD와 다르다.

**한 줄 contribution:** DAG는 노드 단위 독/attribution을 *가능하게* 하지만, 오염 노드 처리가 recovery를 가른다. “DAG라서 항상 안전”은 데이터가 거부한다.

---

## 1. 연구 질문 (확정안)

### RQ1 — DAG vs 비DAG
내부 collaborator에 planted lie가 있을 때, DAG형 코딩 에이전트는 단일 루프(비DAG)보다 거짓을 더 잘 격리·탐지·복구하는가?

**답의 형태:** 항상 그렇지는 않다. 비DAG는 attribution이 없고, DAG는 설계에 따라 더 나을 수도(BPD)·더 나쁠 수도(naive Yonsei) 있다. DAG의 이점은 무조건 승리가 아니라 **노드 단위 격리·attribution 설계 공간**이다.

### RQ2 — DAG 내부 메커니즘
같은 DAG 틀에서 오염 노드 처리(BPD backprop vs scan 맹신 vs source-우선)에 따라 isolation·attribution·recovery가 달라지는가?

**답의 형태:** 예. 차이는 토폴로지 라벨이 아니라 오염 처리 메커니즘에서 온다.

### Attribution이란
잘못(또는 심은 거짓)이 **어느 노드/에이전트에서 들어왔는지**를 시스템이 지목하는 것.  
accuracy(맞춤) ≠ attribution(출처). recovery = attribution ∧ accuracy.

---

## 2. 실험 설계 요약

| 항목 | 내용 |
|------|------|
| 시스템 | `general-agent-system` (비DAG) · `dag-bpd` · `dag-yonsei` |
| 조건 | `none` / `document` / `agent` (핵심은 agent) |
| 태스크 | micro-QnA 100 + code 100 (강화 주입 문구) |
| 지표 | accuracy, propagation, detection(=attribution hit), recovery |
| 주요 런 | poison-100 (agent) · poison-yonsei-improved · poison-conditions (1800 runs) |

세 시스템은 **같은 “독 실험”**이지만 **같은 독립변수는 아님**: 독 위치(user / worker0 / scan)와 attribution 장치가 다르다.

---

## 3. 핵심 결과

### 3.1 강한 agent 주입 (poison-100, naive Yonsei)

| system | QnA acc/prop/det | Code acc/prop/det |
|--------|------------------|-------------------|
| BPD | 1.00 / 0.00 / **0.85** | 0.97 / 0.02 / **0.63** |
| Yonsei (naive) | 0.29 / **0.71** / 0.29 | 1.00 / 0.00 / 0.23 |
| general | 0.83 / 0.17 / **0.00** | 0.88 / 0.10 / **0.00** |

### 3.2 Yonsei source-우선 개선 후 (exploratory)
QnA·code 모두 prop≈0, recovery≈1.0 (agent).  
→ “DAG 실패”가 아니라 **맹신 scan 설계의 실패**였음을 보여 줌.

### 3.3 조건 ablation (poison-conditions, Yonsei=개선 코드)

- `none` / `document`: prop≈0, detection off (이 스위트에서 document 독은 agent만큼 안 먹힘).
- `agent`: BPD QnA rec≈0.87 · code≈0.64; general prop≈0.20·det=0; Yonsei(개선) rec=1.0.

`comparison.md`의 n=300 합산 표는 detection이 희석되어 보이므로, 논문에는 **조건별 표** (`tab_condition_ablation.tex`)를 쓴다.

---

## 4. 왜 Yonsei는 나빠 보였고, BPD는 나았나

### Yonsei (개선 전)
- 파이프라인: scan → implement → …
- 독이 **권위 있는 scan**에 들어감 → implement가 따르기 쉬움 → QnA 전파↑.
- BPD식 “여러 제안 비교 + judge”가 없음 → 실질 attribution 약함.
- 계층 DAG + 오염된 입구 = 단일 루프보다 **독을 더 잘 전달**할 수 있음.

### BPD
- 독은 worker 0 **하나**; 다른 워커는 정상 가능.
- 독립 judge + 기여도 backprop → outlier 지목 + 고득점 쪽 채택.
- **격리와 attribution이 같은 알고리즘**에 묶여 있음.

### 개선 Yonsei vs BPD
둘 다 recovery를 올릴 수 있지만 메커니즘이 다름:  
BPD = 동료 출력 비교 · Yonsei rule = 소스/테스트 권위.

---

## 5. Non-claims (논문에 쓰지 말 것)

- “DAG는 항상 general보다 안전/정확하다”
- “Yonsei source-rule = BPD와 동일”
- poison rates를 research-30 Index와 합산·순위 비교
- 약한 주입 파일럿의 yonsei det=1.0을 진짜 attribution으로 과장

---

## 6. 논문을 쓰기 위한 다음 실험·작업 로드맵

목표 venue: **arXiv → agent workshop → ACL/EMNLP Findings** (realistic-to-safety).  
지금 데이터로 **초고는 가능**. 아래는 설득력 보강용이다.

### Phase 0 — 방향 고정 & 초고 (실험 없이, 즉시)
1. Abstract/Intro에 RQ1→RQ2 배치 (본 문서 §1·Abstract 사용).
2. `paper/paper.tex` 골격 + `\input{../output/tables/tab_*.tex}`.
3. Limitations에 exploratory 라벨 (강한 주입, Yonsei rule A/B, 단일 모델).

### Phase 1 — 저비용 보강 (Findings 전 권장, 택1–2)
| 항목 | 목적 | 방법 | 대략 비용 |
|------|------|------|-----------|
| **A. Cost–recovery 단락** | BPD 토큰≈3×를 숨기지 않기 | 기존 `score.json` 토큰으로 표/산문 | API 거의 없음 |
| **B. BPD miss 정성** | det 실패 15–36% 설명 | agent 실패 케이스 10–20개 transcript 코딩 | 낮음 |
| **C. Multi-model 1개** | Luna-only 반박 | 동일 agent 스위트(또는 core 20+20) 1모델 | 중~고 |

### Phase 1b — Compute-matched budget-4 (done, 2026-09-20)

Four arms, **same poison on replica 0 only**, core 20 QnA + 20 code, `agent`, `max_turns=20`.  
`results/poison-budget-4/comparison.md`

| Arm | QnA acc/prop/det | Code acc/prop/det | ~tokens in (QnA+code) |
|-----|------------------|-------------------|------------------------|
| general-1 | 0.90 / 0.10 / 0 | 0.70 / 0.25 / 0 | 86k |
| general-3 majority | 1.00 / 0 / 0.15 | 0.95 / 0 / 0 | 254k |
| flat-3 majority | 1.00 / 0 / **1.00** | 0.95 / 0.05 / 0 | 233k |
| dag-bpd | 1.00 / 0 / 0.95 | **1.00 / 0 / 0.40** | 233k |

**읽기:** 3×는 전파를 줄인다. 같은 3워커에서 QnA attribution은 majority로 충분하고 BPD가 더 낫지 않다. code attribution만 BPD가 0.40으로 살아 있고, 토큰은 flat-3과 거의 같다.

### Phase 3 — 외부타당성 (main급·나중)
| 항목 | 목적 |
|------|------|
| **F. Multi-file SE / 실 repo형 태스크** | code suite 합성도 낮추기 |
| **G. Document 경로 재설계** | 지금 document prop≈0 → “문서 독”을 주장하려면 주입 강화 필요 (별 RQ) |

### 추천 진행 순서 (논문 작성 기준)
1. **지금:** Phase 0 (쓰기 시작)  
2. **초고 리뷰 전:** Phase 1의 A + B  
3. **Findings 도전 시:** C 추가  
4. **여유/리뷰어 요구 시:** D 또는 E  
5. **미룸:** F, G (스토리가 커짐)

---

## 7. 산출물 인덱스

| 용도 | 경로 |
|------|------|
| 본 브리핑 | `docs/superpapers/BRIEFING-abstract-and-next-experiments.md` |
| 상세 결과 | `results/POISON_RESULTS.md` |
| 표 | `output/tables/tab_main_agent.tex` 등 |
| 설정 | `CLAUDE.superpapers.md` |
| 스펙/플랜 | `docs/superpapers/specs/…`, `plans/…` |

표 재생성:

```sh
python code/01_manifest_poison_runs.py
python code/02_aggregate_poison_rates.py
python code/03_export_paper_tables.py
```

---

## 8. Closing sentence (Intro 말미 후보)

We show that moving from a single-loop coding agent to a DAG enlarges the space for isolating and attributing internally planted lies, but that recovery depends on how poisoned nodes are handled: contribution backpropagation can recover where a scan-trusting hierarchy propagates the lie more than a single loop, unless an explicit source-over-scan discipline is added.
