# Briefing: DAG vs Non-DAG Attribution under Internal Poison

**Date:** 2026-10-20  
**Status:** Draft written. Main run is budget-7; budget-8 is the second model. No further LLM run is required for the current claim scope.  
**Scope:** `apps/implementation-comparison` poison suite (not Artificial Analysis Index)  
**Models:** `gpt-5.6-luna` (budget-7, paper main), `gpt-6-luna` (budget-8)  
**Companion:** `results/EXPERIMENT_SUMMARY.md` (current), `paper/paper.tex` (manuscript), `HANDOFF.md` (how to continue). Sections below Phase 1d are the earlier log.

---

## Abstract (aligned with paper/paper.tex, 2026-10-20)

The manuscript abstract is generated from macros; do not paste a second set of numbers here. The claim, in words:

A planted lie enters one node. With that claim in the system prompt, a single loop repeats it in every QnA run. Three isolated replicas stop that on QnA. On bug fixing, a string majority is not enough: its accuracy depends on which replica carries the lie, because a failed vote promotes the last replica. Naming the source, and choosing the workspace, both require a comparison that reads the replicas' code. On these small tasks a judge-free normalized-source diff does both about as well as the judge, and backpropagation adds nothing. A second model from the same family reproduces the code results. Its QnA attribution drops where the proposal-worker prompt makes the poisoned replica read the file and answer with the source value, so a source can be named only when the lie is visible. Graph structure alone predicts neither isolation nor attribution.

**Keywords:** multi-agent LLM, coding agents, attribution, poison / misinformation, DAG, BPD

---

## Current answers (English)

- **RQ1.** Not as "DAG beats a single loop." Three replicas isolate the lie on QnA. On code, isolation of accuracy needs a choice that does not systematically promote the poisoned replica.
- **RQ2.** Redundancy, a comparison that reads replica content, and backpropagation separate. Backpropagation adds no recovery. The comparison can be an LLM judge or, on these tasks, a normalized-source diff. String majority does not read code.
- **Do not claim** that the diff replaces a judge on larger tasks, that a random replica fixes the majority arms, that `gpt-6-luna` is safer, or that the hierarchical arm (exploratory, different injection node, not rerun under budget-7) beats or loses to the single loop.

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
- “계층형(Yonsei)이 단일 루프보다 독을 더 전파한다” (단일 루프의 전파율은 주입 채널에 따라 0.01–1.00으로 변해 방향이 뒤집힘)
- “단일 루프는 거짓에 견고하다” / “general-3은 attribution이 구조적으로 불가능하다” (둘 다 user 메시지 채널 아티팩트였음, budget-6에서 반증)
- budget-6 BPD 코드 수치를 타임아웃 3건 없이 인용 (하한으로 표기)

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

### Phase 1c — Budget-5, aligned wording, n=100+100 (done, 2026-10-11)

5 arms (adds `judge-only-3`), `agent`, `results/poison-budget-5/`, 상세는 `POISON_RESULTS.md` §10, 표 `tab_budget5.tex`, 검정 `data/processed/paired_poison-budget-5.csv`.

| Arm | QnA acc/prop/det | Code acc/prop/det |
|-----|------------------|-------------------|
| general-1 | 0.99 / 0.01 / 0 | 0.84 / 0.11 / 0 |
| general-3 maj. | 1.00 / 0 / 0 | 1.00 / 0 / 0 |
| flat-3 maj. | 1.00 / 0 / **1.00** | 0.91 / 0.09 / 0 |
| judge-only-3 | 1.00 / 0 / 0.84 | 1.00 / 0 / **0.63** |
| dag-bpd | 1.00 / 0 / 0.88 | 0.99 / 0.01 / **0.63** |

**읽기 (RQ2 갱신):** (1) code attribution은 **judge**에서 오고, terminal backprop 가중은 추가 효과가 없다(BPD = judge-only, McNemar p=1.0). (2) QnA 격리·attribution은 3-replica 문자열 다수결로 충분하고 judge는 오히려 낮다(1.00 vs 0.88, p=5e-4). (3) 이득의 큰 부분은 3× 앙상블이며, "DAG 라벨"이나 "backprop"이 아니다. **한계:** 주입 채널(system vs user) 혼입으로 general-3 det=0은 구조적 한계로 읽으면 안 되고, single-loop QnA 전파는 문구에 민감(0.17→0.01)해 code를 주 증거로 삼아야 한다. 따라서 Abstract의 "judge and backward pass" 표현은 "independent judge"로 좁혀야 한다.

### Phase 1d — Budget-6, same system-prompt channel, n=100+100 (done, 2026-10-11; superseded by Phase 1e)

5 arms, `agent`, 병합본 `results/poison-budget-6-retried/` (원본 `poison-budget-6`; BPD 코드 타임아웃 11건 중 8건 재실행 통과, 3건 실패 유지), 상세 `POISON_RESULTS.md` §11, 표 `tab_main_compact.tex`, 검정 `paired_poison-budget-6-retried.csv`.

| Arm | QnA acc/prop/det | Code acc/prop/det | Code Det\|Emit |
|-----|------------------|-------------------|----------------|
| general-1 | **0.00 / 1.00** / 0 | **0.54 / 0.41** / 0 | 0 |
| general-3 maj. | 1.00 / 0 / **1.00** | 0.97 / 0.02 / 0.01 | 0.02 |
| flat-3 maj. | 1.00 / 0 / 0.99 | 0.92 / 0.08 / 0.01 | 0.02 |
| judge-only-3 | 1.00 / 0 / 0.85 | 0.99 / 0.01 / **0.64** | 0.90 |
| dag-bpd | 1.00 / 0 / 0.87 | 0.96 / 0.01 / **0.63** | 0.90 |

**읽기 (RQ1/RQ2 갱신):** (1) 같은 거짓이 system prompt에 있으면 단일 루프는 QnA에서 전부 거짓을 출력한다. 3-replica 격리는 강하다. (2) **budget-5의 general-3 det=0은 채널 때문이었다.** 독이 보이면 general-3 QnA det=1.00. (3) QnA attribution은 단순 다수결 > judge (p<0.001). (4) code attribution은 judge에서 오며 BPD = judge-only(p=1.0). (5) Abstract의 Yonsei-vs-single-loop 비교는 철회했다(채널 의존). This phase is not the paper's main result. Budget-7 superseded it.

### Phase 1e — Budget-7 and budget-8 (done, 2026-10-20) — paper main

Budget-7: budget-6 arms, system-prompt claim, poisoned index balanced, 180 s limit, `gpt-5.6-luna`, 0 timeouts. Budget-8: the same on `gpt-6-luna`.

Code string-majority accuracy falls when replica 2 is poisoned (flat-3 0.36 on budget-7, 0.30 on budget-8). Judge arms stay near 1.00. An AST-majority promotion of the saved workspaces reaches flat-3 accuracy 0.98 on both models; a uniform draw stays near 0.79. The judge-free diff also matches judge detection. Backprop still adds nothing.

Budget-8 QnA detection for flat-3, judge-only, and BPD is about 0.10–0.12 because those replicas read the file instead of stating the lie. general-3 still states it (detection 0.95). Details: `EXPERIMENT_SUMMARY.md` §§4.5 and 4.9, `POISON_RESULTS.md` §§12–14.

### Phase 1f — What is left (no new luna run)

1. AI-use disclosure, Responsible NLP checklist, anonymous artifact repo, raw-run archive.
2. arXiv endorser, then ARR 2027-01-04 if a designated service contributor is available.
3. A model from a different family only if the target is ACL main. Attempts ≥ 3 and larger tasks are not required for the current claims.

### Phase 3 — 외부타당성 (main급·나중)
| 항목 | 목적 |
|------|------|
| **F. Multi-file SE / 실 repo형 태스크** | code suite 합성도 낮추기 |
| **G. Document 경로 재설계** | 지금 document prop≈0 → “문서 독”을 주장하려면 주입 강화 필요 (별 RQ) |

### Recommended order (2026-10-20)
1. Submission mechanics in Phase 1f. The draft exists.
2. Do not start another experiment in this model family unless the claim scope changes.
3. Phase 3 (harder tasks, document poison) stays future work.

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

On this suite, isolation and attribution come from comparing independent replicas, not from the DAG label or from backpropagation. On these small code tasks a normalized-source diff both names the poisoned replica and chooses a workspace about as well as a judge does, while a string vote and a random replica do not. A hierarchical graph that trusts a poisoned scan report is a separate, exploratory case.
