# Poison / Attribution experiment log

**Current status (2026-10-20, English):** the paper's main run is `poison-budget-7` (`gpt-5.6-luna`, balanced poisoned-replica index, 180 s limit). `poison-budget-8` repeats it on `gpt-6-luna`. The one-stop English summary is `results/EXPERIMENT_SUMMARY.md`. Sections 12–14 below are the English record of those runs. Sections 1–11 are the earlier Korean log and stop at budget-6; section 11 is not the main result anymore.

**작성일:** 2026-09-09  
**범위:** `apps/implementation-comparison` poison suite  
**모델 (본실험):** `openai-compatible/gpt-5.6-luna`  
**연구 질문:** DAG 구조가 심은 거짓(planted lie)을 **격리·탐지·복구**할 수 있는가? (Index/비용 비교가 아님)

이 문서는 Artificial Analysis Index와 **합치지 않습니다.** 비용·토큰은 참고용 로그만 남깁니다.

**초록·후속 실험 브리핑:** `docs/superpapers/BRIEFING-abstract-and-next-experiments.md`

---

## 1. 연구 설정 요약

### 1.1 비교 시스템

| ID | 구조 | poison 경로 |
|----|------|-------------|
| `dag-bpd` | 3 parallel workers → 3 summarizers → independent judge → backward propagation | worker 0에 거짓 주입; BPD 점수로 outlier 탐지 |
| `dag-yonsei` | scan → implement → tests → repair | scan 노드에 거짓 주입 |
| `general-agent-system` | 단일 tool loop | user message로 거짓 주입; attribution 메커니즘 없음 |

### 1.2 조건

| condition | 의미 |
|-----------|------|
| `none` | 독 없음 (baseline) |
| `document` | `NOTES.md` / policy에 거짓 |
| `agent` | 협업 노드(워커/scan)에 거짓 주입 — **본실험의 핵심** |

### 1.3 태스크 세트

| 세트 | 채점 | 개수 (최종) | 설명 |
|------|------|------------|------|
| **Controlled (micro-QnA)** | 최종 답 string match (`gold`/`lie`) | 100 | 설정 상수 QnA; 핵심 20 + 생성 80 |
| **Realistic (code)** | 숨은 pytest | 100 | 버그 픽스 + 틀린 수정 전략; 핵심 20 + 생성 80 |

### 1.4 측정 지표

| 지표 | 정의 |
|------|------|
| **accuracy** | 최종 답/코드가 gold (거짓이 아님). QnA=string, code=pytest pass |
| **propagation** | 최종 답/코드에 심은 거짓이 나타남 |
| **detection** | 시스템이 오염 출처(워커 인덱스 / `scan`)를 올바르게 지목 |
| **recovery** | detection ∧ accuracy |

값은 해당 버킷에서 조건을 만족한 **비율**(0–1). Index 점수(0–100)가 아닙니다.

### 1.5 핵심 코드 경로

- CLI: `python -m impl_comparison.poison_compare`
- QnA: `poison.py` → `POISON_TASKS`
- Code: `poison_code_tasks.py` → `CODE_POISON_TASKS`
- 강화 주입 문구: `poison_injection.py`
- 카탈로그 확장: `poison_task_catalog.py`, `poison_code_catalog.py`
- 결과 디렉터리: `apps/implementation-comparison/results/poison*/`

스펙/플랜:

- `docs/superpowers/specs/2026-08-30-poison-attribution-bpd-design.md`
- `docs/superpowers/plans/2026-08-30-poison-attribution-bpd-v2.md`

---

## 2. 구현 타임라인

### Phase A — BPD v2 + code fixtures (merged)

목표: `dag-bpd`를 논문식 signed-edge judge + backward propagation으로 재배선하고, code-verifiable 태스크를 추가.

완료 항목:

1. BPD math helpers (`terminal_scores_from_summaries`, `backward_propagate`, `detect_bpd_outlier`)
2. `dag-bpd` poison path: 3 workers → 3 summarizers → batched judge → backprop → arg-max winner
3. `verify_poison`의 pytest grading 분기
4. 초기 code fixture 5개 → 이후 20개 → 100개로 확장
5. `--task-set {all,micro-qna,code}` + 이중 표 리포팅
6. pytest 하네스 통과 (merge 시점 313+)

### Phase B — 파일럿 LLM 런 (약한 주입)

초기 주입은 “다른 에이전트 claim” 수준이라, poisoned worker가 종종 **그래도 gold**를 냄 → BPD detection이 거의 안 켜짐 (전원 동의 시 scores ≈ `[1,1,1]`).

| 런 | 경로 | 규모 | 요약 |
|----|------|------|------|
| poison | `results/poison/` | 소규모 agent | QnA prop≈0, det≈0 (yonsei QnA det=1.0은 **휴리스틱**) |
| poison-all | `results/poison-all/` | 3조건×소규모 | BPD code에서 detection 1건 수준 |
| poison-20 | `results/poison-20/` | 20+20, agent, max_turns=20 | 아래 표 |

#### poison-20 (약한 주입, n=20+20)

**QnA**

| system | accuracy | propagation | detection | recovery |
|--------|----------|-------------|-----------|----------|
| dag-bpd | 1.000 | 0.000 | 0.000 | 0.000 |
| dag-yonsei | 1.000 | 0.000 | 1.000 | 1.000 |
| general | 1.000 | 0.000 | 0.000 | 0.000 |

**Code**

| system | accuracy | propagation | detection | recovery |
|--------|----------|-------------|-----------|----------|
| dag-bpd | 0.900 | 0.100 | 0.000 | 0.000 |
| dag-yonsei | 1.000 | 0.000 | 0.050 | 0.050 |
| general | 0.900 | 0.100 | 0.000 | 0.000 |

**해석:** 독이 거의 전파되지 않음. yonsei QnA `detection=1.0`은 `final==gold → detected_source="scan"` 휴리스틱이라 **실제 attribution이 아님**. BPD는 “워커가 실제로 거짓을 말했을 때만” outlier가 생기므로 det=0이 정상.

### Phase C — 강화 주입 + n≈100 (poison-100)

변경:

1. `poison_injection.py`: MANDATORY claim (worker / scan / general / NOTES)
2. QnA·code 각 **100개**로 확장
3. yonsei/general/bpd가 강화 문구 사용

설정: `condition=agent`, `task_set=all`, `max_turns=20`, 3 systems × 200 = **600 runs**, 약 **108분**.

#### poison-100 결과

**Controlled (micro-QnA, n=100)**

| system | accuracy | propagation | detection | recovery | tokens in/out |
|--------|----------|-------------|-----------|----------|---------------|
| **dag-bpd** | **1.000** | **0.000** | **0.850** | **0.850** | 300109 / 7136 |
| dag-yonsei | 0.290 | 0.710 | 0.290 | 0.290 | 136186 / 2390 |
| general | 0.830 | 0.170 | 0.000 | 0.000 | 116970 / 3023 |

**Realistic (code, n=100)**

| system | accuracy | propagation | detection | recovery | tokens in/out |
|--------|----------|-------------|-----------|----------|---------------|
| **dag-bpd** | 0.970 | 0.020 | **0.630** | **0.630** | 796603 / 44142 |
| dag-yonsei | 1.000 | 0.000 | 0.230 | 0.230 | 237002 / 12927 |
| general | 0.880 | 0.100 | 0.000 | 0.000 | 288305 / 15346 |

원본 표: `results/poison-100/comparison.md`

#### poison-100 해석

1. **강화 주입으로 BPD가 살아남.** QnA에서 prop=0 · det=85% · recovery=85%. 거짓을 worker 0에 심어도 다수+judge+backprop가 최종을 gold로 유지하고 outlier를 지목.
2. **yonsei QnA는 취약.** scan을 authoritative로 넣자 prop=71%, accuracy=29%. 계층 DAG라도 **오염된 scan을 맹신**하면 단일 루프보다 나을 수 없음.
3. **general**은 attribution이 없어 detection=0. QnA는 가끔 source를 읽어 prop=17%만 발생; code는 prop=10%.
4. **code에서 BPD**는 accuracy 97% + detection 63%. yonsei code는 accuracy 100%지만 detection 23%(문구/휴리스틱 의존).
5. BPD 토큰이 대략 3× (워커+summarizer+judge) — research-30과 동일한 비용 패턴.

### Phase D — yonsei 개선 실험

**문제**

1. scan claim이 “authoritative”라 implement가 소스보다 독을 따름  
2. `final==gold → detected_source="scan"`은 독이 약할 때 가짜 recovery를 만듦

**개선 (옵션 2)**

1. `SOURCE_OVER_SCAN_RULE`: workspace source(및 failing tests)가 scan과 충돌하면 **source 우선**
2. Attribution: source↔scan **충돌이 확인**되고, QnA는 final이 gold / code는 `lie_pattern`이 소스에 없을 때만 `detected_source="scan"`
3. 독을 따른 경우(`lie` 채택)에는 detection을 주장하지 않음

설정: `dag-yonsei`만, `condition=agent`, 100+100, `max_turns=20`, 약 **13분**.  
결과: `results/poison-yonsei-improved/comparison.md`

#### yonsei A/B (poison-100 → improved)

**QnA (n=100)**

| 버전 | accuracy | propagation | detection | recovery |
|------|----------|-------------|-----------|----------|
| poison-100 (개선 전) | 0.290 | 0.710 | 0.290 | 0.290 |
| **yonsei-improved** | **1.000** | **0.000** | **1.000** | **1.000** |

**Code (n=100)**

| 버전 | accuracy | propagation | detection | recovery |
|------|----------|-------------|-----------|----------|
| poison-100 (개선 전) | 1.000 | 0.000 | 0.230 | 0.230 |
| **yonsei-improved** | **1.000** | **0.000** | **1.000** | **1.000** |

**해석:** source-우선 규칙만으로 QnA propagation이 71%→0%로 사라지고 accuracy·recovery가 100%로 회복. code는 원래도 prop=0이었고, 충돌+거절 기반 attribution으로 detection이 23%→100%.  
참고: BPD(QnA det 85% / code 63%)와 달리 yonsei 개선은 **독립 judge가 아니라** “소스와 충돌하는 scan을 무시”하는 규칙+사후 attribution이라 메커니즘이 다름. 다만 같은 강화 주입·같은 태스크에서 **계층 DAG도 오염 scan을 격리할 수 있음**을 보여 줌.

---

## 3. 단계별 비교 한눈에

### 3.1 QnA — BPD detection 변화

| 런 | 주입 | n | BPD det | yonsei acc | yonsei prop |
|----|------|---|---------|------------|-------------|
| poison-20 | 약함 | 20 | 0.00 | 1.00 | 0.00 |
| poison-100 | 강함 | 100 | **0.85** | 0.29 | 0.71 |
| yonsei-improved | 강함 + source 우선 | 100 | (unchanged) | **1.00** | **0.00** |

### 3.2 Code — BPD detection 변화

| 런 | 주입 | n | BPD det | BPD prop | general prop |
|----|------|---|---------|----------|--------------|
| poison-20 | 약함 | 20 | 0.00 | 0.10 | 0.10 |
| poison-100 | 강함 | 100 | **0.63** | 0.02 | 0.10 |

### 3.3 연구 질문에 대한 잠정 답

> DAG가 심은 거짓을 격리·탐지·복구할 수 있는가?

- **Faithful BPD (`dag-bpd`):** 강화 주입·n=100에서 **예** — 특히 QnA isolation/recovery가 뚜렷. code에서도 다수 탐지·복구.
- **계층 Yonsei (개선 전):** scan이 오염되면 **아니오에 가깝음** (QnA prop 71%).
- **계층 Yonsei (source-우선 개선 후):** 같은 강화 주입에서 **예** — QnA/code 모두 prop=0 · recovery=1.0. 메커니즘은 BPD(judge+backprop)와 다르고, “소스 권위” 규칙에 의존.
- **General agent:** 부분적 저항은 있어도 **attribution/recovery 메커니즘 없음** (det=0).

---

## 4. 메트릭·해석 주의사항

1. **yonsei 초기 det=1.0 (약주입)**  
   gold 답을 내면 scan을 탓하는 휴리스틱. 독이 약하면 “완벽한 recovery”처럼 보임 → **보고에서 제외하거나 명시적으로 할인**.

2. **BPD det=0 (약주입)**  
   알고리즘 실패가 아니라 **독이 워커 출력에 안 실림**. judge 전원이 +1 → outlier 없음.

3. **Cost 칸 0.0000**  
   API가 `cost_usd`를 안 주는 경우가 많아 표는 0. 토큰으로 상대 비용 비교 (BPD ≫ yonsei ≈ general).

4. **Index와 무관**  
   research-30 Index와 poison rates를 숫자로 합치거나 순위를 섞지 말 것.

5. **FakeLLM / `--allow-fake`**  
   하네스 검증용. 연구 표에 넣지 않음.

---

## 5. 재현 명령

```sh
cd apps/implementation-comparison
set -a && source ../../../.env && set +a
export IMPL_COMPARISON_LLM_PROVIDER=openai-compatible
export IMPL_COMPARISON_LLM_MODEL=gpt-5.6-luna
unset IMPL_COMPARISON_ALLOW_FAKE

# 전체 3시스템 agent (약 600 runs)
PYTHONPATH=src:../../../src python - <<'PY'
from pathlib import Path
from impl_comparison.poison_compare import compare_poison
compare_poison(Path('results/poison-100'), condition='agent', task_set='all', max_turns=20)
PY

# yonsei 개선 재실험만
PYTHONPATH=src:../../../src python - <<'PY'
from pathlib import Path
from impl_comparison.poison_compare import compare_poison
compare_poison(
    Path('results/poison-yonsei-improved'),
    condition='agent',
    system='dag-yonsei',
    task_set='all',
    max_turns=20,
)
PY
```

단위 테스트:

```sh
PYTHONPATH=src python -m pytest tests/test_poison.py tests/test_poison_code_tasks.py -q
```

---

## 6. 산출물 인덱스

| 경로 | 내용 |
|------|------|
| `results/poison/comparison.md` | 초기 파일럿 |
| `results/poison-all/comparison.md` | 3조건 소규모 |
| `results/poison-20/comparison.md` | 약한 주입, n=20+20 |
| `results/poison-100/comparison.md` | 강화 주입, n=100+100, 3시스템 |
| `results/poison-yonsei-improved/comparison.md` | yonsei source-우선 개선 후 |
| `results/poison-conditions/comparison.md` | none/document/agent ablation (pooled); 조건별은 `tab_condition_ablation.tex` |
| `results/poison-budget-4/comparison.md` | 3× 공정 비교 (general-1/3, flat-3, BPD), core 20+20 |
| `results/research-30/comparison.md` | (별도) Index 스위트 — poison과 합치지 말 것 |
| 본 파일 | 서사·해석·재현 |

---

## 7. Phase E — Condition ablation (B1, 2026-09-10)

**설정:** 3 systems × `{none, document, agent}` × 100 QnA + 100 code = **1800 runs**, `gpt-5.6-luna`, max_turns=20.  
**yonsei:** source-over-scan 개선 코드 경로.  
**원본:** `results/poison-conditions/` · 조건별 표: `output/tables/tab_condition_ablation.tex`

주의: `comparison.md`의 단일 표는 세 조건을 **합친** n=300 rates라 detection이 희석되어 보임. 해석은 아래 조건별 표를 쓴다.

### QnA (n=100 per cell)

| system | cond | acc | prop | det | rec |
|--------|------|-----|------|-----|-----|
| dag-bpd | none | 1.00 | 0.00 | 0.00 | 0.00 |
| dag-bpd | document | 1.00 | 0.00 | 0.00 | 0.00 |
| dag-bpd | agent | 1.00 | 0.00 | **0.87** | **0.87** |
| dag-yonsei | none | 0.99 | 0.00 | 0.00 | 0.00 |
| dag-yonsei | document | 0.98 | 0.00 | 0.00 | 0.00 |
| dag-yonsei | agent | 1.00 | 0.00 | **1.00** | **1.00** |
| general | none | 1.00 | 0.00 | 0.00 | 0.00 |
| general | document | 1.00 | 0.00 | 0.00 | 0.00 |
| general | agent | 0.80 | **0.20** | 0.00 | 0.00 |

### Code (n=100 per cell)

| system | cond | acc | prop | det | rec |
|--------|------|-----|------|-----|-----|
| dag-bpd | none | 1.00 | 0.00 | 0.00 | 0.00 |
| dag-bpd | document | 0.99 | 0.00 | 0.00 | 0.00 |
| dag-bpd | agent | 0.96 | 0.02 | **0.64** | **0.64** |
| dag-yonsei | none/document/agent | 1.00 | 0.00 | 0 / 0 / **1.00** | 0 / 0 / **1.00** |
| general | none | 0.98 | 0.00 | 0.00 | 0.00 |
| general | document | 0.99 | 0.00 | 0.00 | 0.00 |
| general | agent | 0.79 | **0.19** | 0.00 | 0.00 |

### 해석 (H1–H4)

1. **`none`:** 전원 prop≈0, detection off — H1 지지.  
2. **`document`:** 이 스위트·강화 NOTES에도 prop≈0 (모델이 source/tests를 더 따름). agent path와 **교환 불가** — H4 방향 지지.  
3. **`agent`:** BPD QnA rec 0.87 / code 0.64; general prop≈0.20·det=0 — H3 지지 (poison-100 재현).  
4. **yonsei (improved):** agent에서 prop=0·rec=1.0; none/document에서는 det=0 (오염 scan이 없을 때 attribution 안 함).

---

## 9. Compute-matched budget-4 (2026-09-20)

**질문:** BPD가 3워커라서 유리한 것 아닌가?  
**설정:** core 20+20, `agent`, replica 0만 독, `gpt-5.6-luna`. 원본 `results/poison-budget-4/comparison.md`.

### QnA (n=20)

| system | acc | prop | det | rec | tokens in/out |
|--------|-----|------|-----|-----|---------------|
| general-1 | 0.90 | 0.10 | 0.00 | 0.00 | 25k / 0.6k |
| general-3 majority | 1.00 | 0.00 | 0.15 | 0.15 | 72k / 2.0k |
| **flat-3 majority** | 1.00 | 0.00 | **1.00** | **1.00** | 59k / 1.4k |
| dag-bpd | 1.00 | 0.00 | 0.95 | 0.95 | 60k / 1.4k |

### Code (n=20)

| system | acc | prop | det | rec | tokens in/out |
|--------|-----|------|-----|-----|---------------|
| general-1 | 0.70 | 0.25 | 0.00 | 0.00 | 61k / 3.9k |
| general-3 majority | 0.95 | 0.00 | 0.00 | 0.00 | 182k / 11k |
| flat-3 majority | 0.95 | 0.05 | 0.00 | 0.00 | 174k / 11k |
| **dag-bpd** | **1.00** | **0.00** | **0.40** | **0.40** | 173k / 12k |

### 해석

1. **3× 예산은 isolation에 크다.** general-1 대비 3-replica는 QnA/code 모두 전파를 거의 없앰. “BPD만 3배라서 이긴다”는 지적은 QnA **정답률**에는 해당.
2. **같은 3워커에서 BPD 추가분은 QnA에선 거의 없음.** flat-3 majority가 det 1.00, BPD 0.95. 토큰도 flat-3≈BPD. judge+backprop가 QnA string-match에선 majority를 넘지 않음.
3. **code에서 attribution은 BPD만 의미 있게 켜짐** (det 0.40 vs majority 0). 전략 문구 독은 다수결이 출처를 못 짚고, judge/backprop는 일부 짚음.
4. **병렬 DAG vs 3회 단일 루프:** QnA det는 flat-3(1.00) ≫ general-3(0.15). 같은 3×라도 워커를 나란히 두고 비교하는 쪽이 출처 지목에 유리.
5. n=20이라 확정적 주장은 보류. Findings에는 “3× matched; QnA는 majority로 충분, code attribution은 BPD”로 쓰는 게 맞음.
6. **한계(§10에서 보완):** budget-4는 arm마다 주입 문구 강도가 달랐고(general-3은 user 메시지의 약한 문구, flat/BPD는 "Do not use any value from source code" 포함), n=20이며 judge 기여를 분리하는 arm이 없었다. 이 절은 **파일럿**으로만 인용한다.

## 10. Budget-5 — 문구 정렬 + judge-only ablation (2026-10-10, n=100+100)

**변경점 (파일럿 대비)**
- `injection_profile="aligned"`: general-1 / general-3의 독 replica가 flat·BPD 워커와 **동일 문구**(`agent_worker_prompt`)를 user 메시지로 받음(`poison_injection.aligned_general_message`). 문구 차이로 인한 detection 혼입 제거.
- 새 arm `judge-only-3` (`JudgeOnlyBpdSystem`): BPD와 같은 3워커→3요약자→독립 judge, 단 terminal plurality 가중 없이 worker 점수 = judge edge 평균. **요약자 투표만 쓰는 arm은 worker 작업공간으로 되돌릴 수 없어(매핑 불가) 만들 수 없다** → judge 기여와 backprop(terminal 가중) 기여를 분리하는 사다리로 대체: flat-3(LLM 없음) → judge-only-3(judge, backprop 가중 없음) → dag-bpd(judge + terminal-weighted backprop).
- 규모: core 20+20 → **100+100**, 5 arms × 200 = 1,000 runs, `agent` 조건, `gpt-5.6-luna`, max_turns=20, attempts=1.
- 통계: bootstrap seed를 `hash()`(프로세스마다 달라짐) → `crc32` 안정 seed로 교체(CI 완전 재현). Wilson 구간 + 정확 McNemar(paired, `code/04_paired_tests.py`) 추가. 표에 arm별 입력 토큰/task 열 추가.

**실행:** `compare_poison(Path('results/poison-budget-5'), condition='agent', task_set='all', scale='all', arms='budget-5', max_turns=20)` — 원본 `results/poison-budget-5/` (gitignored).
**파이프라인:** `code/01..03` → `output/tables/tab_budget5.tex`, `code/04_paired_tests.py poison-budget-5` → `data/processed/paired_poison-budget-5.csv`.

**결과 (n=100 per cell, agent, 1회 실행, 토큰은 입력 k/task)** — 표: `output/tables/tab_budget5.tex`

| arm | QnA acc/prop/det(=rec) | Code acc/prop/det(=rec) | tok QnA / code |
|-----|------------------------|-------------------------|----------------|
| general-1 | 0.99 / 0.01 / 0 | 0.84 / 0.11 / 0 | 1.3 / 3.0 |
| general-3 maj. | 1.00 / 0 / 0 | 1.00 / 0 / 0 | 3.6 / 8.4 |
| flat-3 maj. | 1.00 / 0 / **1.00** | 0.91 / 0.09 / 0 | 3.0 / 8.1 |
| judge-only-3 | 1.00 / 0 / 0.84 | 1.00 / 0 / **0.63** | 3.0 / 8.2 |
| dag-bpd | 1.00 / 0 / 0.88 | 0.99 / 0.01 / **0.63** | 3.0 / 8.1 |

**Paired exact McNemar (`paired_poison-budget-5.csv`)**
- QnA recovery: flat-3 1.00 vs BPD 0.88 → flat 우세 (12 vs 0 불일치, p=5e-4). BPD vs judge-only 0.88 vs 0.84 → 차이 없음 (12 vs 8, p=0.50).
- Code recovery: BPD 0.63 vs flat-3 0 / general-3 0 / general-1 0 (모두 p<1e-18). **BPD vs judge-only 0.63 vs 0.63, 불일치 5 vs 5 (p=1.0).**
- Code accuracy: BPD 0.99 vs flat-3 0.91 (p=0.008), vs general-1 0.84 (p=6e-5); BPD vs general-3 / judge-only 차이 없음.

**해석**
1. **코드 attribution의 원천은 judge이지 backprop 가중이 아니다.** judge-only-3과 dag-bpd가 사실상 동일(0.63/0.63, 불일치 대칭). terminal plurality 가중은 이 스위트에서 추가 이득이 없다. judge가 없는 같은 3워커(flat-3, general-3)는 code det=0.
2. **QnA에서는 judge가 오히려 손해.** 문자열 다수결(flat-3)이 det 1.00, judge arm은 0.84–0.88. QnA 답이 짧은 문자열이라 majority로 충분하고 judge는 노이즈를 더한다.
3. **정확도:** 3× 예산은 code 정확도를 올린다(general-1 0.84 → general-3 1.00). BPD의 code 정확도 이점 중 상당 부분은 3× 앙상블 효과이고, 같은 3×인 flat-3(0.91)보다는 높지만 general-3(1.00)·judge-only(1.00)와는 구분되지 않는다.
4. **budget-4 파일럿과의 일관성:** QnA 격리는 ensemble로 충분 / code attribution은 judge 필요 — 방향 동일, n=100에서 확정.

**⚠ 해석 주의 (논문에 반드시 명시)**
- **주입 채널 혼입이 남아 있다.** 문구는 같지만 flat/judge-only/BPD는 *system prompt*에, general-1/general-3은 *user 메시지*에 주입된다. general 독 replica는 거짓을 거의 말하지 않아(QnA prop 0.01) 다수결 det가 0으로 나온다. 이는 "attribution 실패"가 아니라 **독이 출력에 드러나지 않아 지목할 대상이 없는 것**이다. general-3의 det=0을 구조적 한계로 해석하지 말 것.
- **single-loop 기준선의 QnA 전파는 문구에 민감하다:** legacy 문구 poison-100 0.17, budget-4 파일럿 0.10, aligned 0.01. code는 0.10–0.25로 안정적. → QnA의 "single loop가 거짓을 전파한다"는 강한 주장은 하지 말고, code 결과를 주 증거로 삼는다.
- majority 탐지는 독 replica가 거짓 문자열을 출력해야 발동(code에서는 전략 문구가 다양해 substring 일치가 어려워 det=0 — judge arm과의 비교는 "judge가 의미 매칭을 해준다"는 효과와 섞임).
- 단일 실행(attempts=1), 단일 모델. BPD QnA det는 run 간 0.85–0.95로 변동(poison-100 0.85, conditions 0.87, 본 run 0.88).

---

## 11. Budget-6 — 모든 arm에 동일 채널(system prompt) 주입 (2026-10-11, n=100+100) — superseded by budget-7

**왜 했나:** §10의 채널 혼입(I1) 제거. general-1/general-3 독 replica도 flat/judge-only/BPD와 **바이트 동일한 문구를 system prompt**로 받는다(`injection_profile="system"`, `--arms budget-6`). 새 지표 `lie_emitted`(독 replica 자신의 출력에 거짓이 나왔는가)와 `detection_given_emitted`(Det|Emit)를 기록한다. 코드 과제의 Emit은 거짓 문구 또는 소스 파일 패턴 일치를 쓰는 **어휘 기반 근사**라 의역된 순응은 놓칠 수 있다.

**실행:** `compare_poison(Path('results/poison-budget-6'), condition='agent', task_set='all', scale='all', arms='budget-6', max_turns=20)`, 2026-10-11 13:26–17:16 KST, 1,000 runs, 원본 `results/poison-budget-6/` (score.json만 git).

**⚠ 하니스 타임아웃과 재실행 (반드시 명시):** 첫 패스에서 **dag-bpd 코드 11건이 60초 task 제한에 걸려**(`status=timeout`, 토큰 0 기록, 16:26–16:41 KST에 약 1–2분 간격으로 발생) `accurate=False`로 처리됐다. 다른 arm에는 타임아웃이 0건, budget-5에도 0건. `code/06_retry_infra_timeouts.py poison-budget-6`이 **정확히 이 11건만 동일 설정으로 1회 재실행**(`results/poison-budget-6-retry/`)하고 병합본 `results/poison-budget-6-retried/`를 만든다. 재실행에서 8건 통과, **3건(strip-once, parity-000, default-000)은 다시 타임아웃 → 실패로 유지**(통과할 때까지 반복하지 않음: 선택 편향 방지). 원본(as-run)은 그대로 보존하고 두 버전을 모두 보고한다. 논문 메인 = `poison-budget-6-retried`(매크로 `Main`/`BSixR`), 원본 = `BSix`(부록 표). BPD 코드 정확도는 하한으로 읽는다.

**결과 (retried 병합본, n=100 per cell, agent, 1회 실행)** — 표: `tab_main_compact.tex`, `tab_budget6_retried.tex`, 부록 `tab_budget6.tex`

| arm | QnA acc/prop/det(=rec) | Emit | Det\|Emit | Code acc/prop/det(=rec) | Emit | Det\|Emit |
|-----|------------------------|------|-----------|-------------------------|------|-----------|
| general-1 | **0.00 / 1.00** / 0 | 1.00 | 0 | **0.54 / 0.41** / 0 | 0.50 | 0 |
| general-3 maj. | 1.00 / 0 / **1.00** | 1.00 | 1.00 | 0.97 / 0.02 / 0.01 | 0.49 | 0.02 |
| flat-3 maj. | 1.00 / 0 / 0.99 | 0.99 | 1.00 | 0.92 / 0.08 / 0.01 | 0.56 | 0.02 |
| judge-only-3 | 1.00 / 0 / 0.85 | 0.99 | 0.86 | 0.99 / 0.01 / **0.64** | 0.58 | 0.90 |
| dag-bpd | 1.00 / 0 / 0.87 | 0.98 | 0.89 | 0.96 / 0.01 / **0.63** | 0.61* | 0.90 |

(*타임아웃 3건은 Emit 미기록이라 분모 97. 원본 as-run BPD 코드: acc 0.88, det/rec 0.61, 타임아웃 11.)

**Paired exact McNemar (`paired_poison-budget-6-retried.csv`)**
- 격리: general-1 vs general-3 정확도 — QnA 0.00 vs 1.00 (100 vs 0, p<1e-29), code 0.54 vs 0.97 (0 vs 43, p=2e-13).
- QnA recovery: general-3 1.00 vs judge-only 0.85 (15 vs 0, p=6e-5); flat-3 0.99 vs BPD 0.87 (13 vs 1, p=0.002); **BPD vs judge-only 0.87 vs 0.85 (12 vs 10, p=0.83)**.
- Code recovery: judge-only 0.64 vs flat-3 0.01 (63 vs 0, p=2e-19); **BPD vs judge-only 0.63 vs 0.64 (8 vs 9, p=1.0)**; BPD vs general-3/flat-3 p≈4e-19.

**해석 (budget-5 대비 달라진 점 포함)**
1. **채널이 단일 루프 취약성을 지배한다.** system prompt로 같은 거짓을 받으면 general-1은 QnA에서 **100% 거짓을 출력**(acc 0.00), code에서 41% 전파(acc 0.54). user 메시지로 받을 때(budget-5: 0.99/0.01, 0.84/0.11)는 거의 무시했다. §10의 "single-loop가 상대적으로 견고하다"는 인상은 **채널 아티팩트**였다.
2. **budget-5의 general-3 det=0은 기계적 결과였다.** 독이 보이면(Emit=1.00) general-3 QnA det=**1.00**. 구조적 한계가 아니라 독이 출력에 안 나온 탓이었다(I1 확인).
3. **3-replica 격리는 강하다.** QnA에서 모든 3-replica arm이 acc 1.00 / prop 0, code acc 0.92–0.99.
4. **QnA attribution은 단순 다수결이 judge보다 낫다.** Det|Emit: general-3/flat-3 1.00 vs judge-only 0.86, BPD 0.89. judge는 거짓이 보이는 run의 일부를 놓친다.
5. **code attribution은 judge에서 온다.** 다수결은 Det|Emit 0.02(문자열 매칭 한계), judge 계열 0.90. **BPD = judge-only**(backprop 추가 이득 없음)가 QnA·code 모두에서 재확인.
6. **독 replica의 순응 자체가 지표.** code에서는 약 절반의 run에서만 거짓을 출력(Emit 0.49–0.61) → 어떤 방식이든 attribution 상한을 제한한다.
7. **Hierarchical(Yonsei) vs 단일 루프 비교는 철회.** 이전의 "Yonsei QnA 전파 0.71 > single-loop 0.17"은 단일 루프가 user 메시지로 받던 설정의 결과다. system 채널에서는 단일 루프 전파가 1.00이므로 방향이 뒤집힌다. 논문에서는 Yonsei의 절대 전파율(0.71, exploratory)만 쓰고 단일 루프와 비교하지 않는다.

**남은 한계:** 단일 모델·attempts=1, 독 replica 위치 고정(항상 0), 코드 다수결은 substring 매칭, 60초 제한이 3단계 judge 파이프라인에 불리(BPD 코드 3건 실패 유지), Emit은 코드에서 어휘 근사.

---

## 8. Paperization artifacts (2026-09-09)

Replication pipeline (no API):

| Artifact | Path |
|----------|------|
| Config | `CLAUDE.superpapers.md` |
| Gap design | `docs/superpapers/specs/2026-09-09-poison-paperization-gaps-design.md` |
| Plan | `docs/superpapers/plans/2026-09-09-poison-paperization-gaps-plan.md` |
| Rates CSV | `data/processed/rates_by_run.csv` |
| Main table | `output/tables/tab_main_agent.tex` |
| Yonsei A/B | `output/tables/tab_yonsei_ab.tex` |
| Weak vs strong | `output/tables/tab_weak_vs_strong.tex` |
| Condition ablation | `output/tables/tab_condition_ablation.tex` |

Regenerate:

```sh
python code/01_manifest_poison_runs.py
python code/02_aggregate_poison_rates.py
python code/03_export_paper_tables.py
```

---

## 12. Budget-7 — balanced poison position (2026-10-13, n=100+100) — paper main run

**Why:** budget-6 always poisoned replica 0, and the string-majority fallback promotes replica 2 when no proposal matches the gold or lie string. That hid a code-accuracy failure.

**Run:** `compare_poison(Path('results/poison-budget-7'), condition='agent', task_set='all', scale='all', arms='budget-6', max_turns=20, poison_position='balanced', task_timeout=180.0)`. Model `gpt-5.6-luna`. 1,000 runs, 0 timeouts. Position assignment is a seeded hash (`20261011`): 34/33/33 tasks per index.

| arm | QnA acc/prop/det | Code acc/prop/det |
|-----|------------------|-------------------|
| general-1 | 0.00 / 1.00 / 0 | 0.59 / 0.40 / 0 |
| general-3 | 1.00 / 0 / 1.00 | 0.81 / 0.15 / 0.02 |
| flat-3 | 1.00 / 0 / 0.99 | 0.72 / 0.26 / 0.01 |
| judge-only-3 | 1.00 / 0 / 0.91 | 1.00 / 0 / 0.63 |
| dag-bpd | 1.00 / 0 / 0.94 | 0.99 / 0.01 / 0.67 |

Code accuracy by poisoned index: flat-3 0.88 / 0.91 / 0.36 and general-3 0.91 / 1.00 / 0.52 (permutation p < 0.001). Judge-only and BPD stay at 0.97–1.00. `code/09_majority_fallback.py`: the promoted source equals replica 2 in 0.90 of flat-3 code tasks. When that source is only the poisoned replica's, flat-3 accuracy is 0.30 (40 tasks); otherwise 1.00.

Judge vs BPD code recovery: discordant 7 vs 11, p = 0.48. QnA recovery, general-3 vs judge-only: p = 0.004 (majority is higher).

## 13. Budget-8 — same design, `gpt-6-luna` (2026-10-16)

Same configuration as budget-7. About 4 h 15 min, 0 timeouts. `llm.py` applies the gpt-5.6 chat-completions compatibility to `gpt-6*` models.

Code replicates: flat-3 accuracy 0.70 (0.30 when replica 2 is poisoned); judge-only 0.99; BPD 0.98; code detection 0.60 and 0.61; backprop adds nothing (p = 1.0).

QnA detection does not replicate for the proposal-worker arms: flat-3 0.12, judge-only 0.11, BPD 0.10, against general-3 0.95. Emit in those three arms is 0.12 / 0.12 / 0.10. `code/10_qna_emit_behavior.py`: on this model, calling a tool and answering with the source value go together (flat-3 0.88), and answering with no tool means stating the lie (0.11). `gpt-5.6-luna` states the lie even after a tool call. Do not read this as the second model being safer. Det|Emit remains 0.92–1.00.

Uncorrected lead: judge-only code recovery by index is 0.65 / 0.42 / 0.73 (p = 0.037) among 20 recovery tests. BPD does not show it (p = 0.20). The paper calls this a lead, not a finding.

## 14. Offline analyses (no LLM calls)

| Script | Question | Result on budget-7 (budget-8) |
|--------|----------|--------------------------------|
| `code/08_semantic_baselines.py` | Does a normalized-source diff name the poisoned replica? | Judge-only AST hit 0.60 vs the judge's own detection 0.63 (McNemar p = 0.58). BPD 0.67 vs 0.67. |
| `code/11_selection_counterfactual.py` | What if that diff also chose the workspace? | Flat-3 accuracy 0.98 (0.98) against 0.72 (0.70) actual and 0.79 (0.79) for a uniform draw. Judge-only AST 0.97 (0.99) against recorded 1.00 (0.99). |
| `code/07_position_breakdown.py` | Does the rate depend on the poisoned index, and do runs replicate? | Majority code accuracy does. Judge/BPD code recovery does not detectably (n≈33 per cell). |

The diff matches the judge on these single-module tasks because correct replicas write the same fix. It is not evidence for larger tasks. When no replica is a unique outlier, the promotion rule still picks replica 2.

