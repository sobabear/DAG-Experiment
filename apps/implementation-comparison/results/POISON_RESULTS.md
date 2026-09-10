# Poison / Attribution 실험 결과 보고서

**작성일:** 2026-09-09  
**범위:** `apps/implementation-comparison` poison suite  
**모델 (본실험):** `openai-compatible/gpt-5.6-luna`  
**연구 질문:** DAG 구조가 심은 거짓(planted lie)을 **격리·탐지·복구**할 수 있는가? (Index/비용 비교가 아님)

이 문서는 Artificial Analysis Index와 **합치지 않습니다.** 비용·토큰은 참고용 로그만 남깁니다.

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
