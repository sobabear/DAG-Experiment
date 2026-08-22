# Implementation Comparison Plan

## 0. 연구 목적

이 프로젝트는 **DAG가 다른 agent 시스템과 비교해 어떤 경우에 장점을 보이는지**를 실험하고, 구현·실패 모드에 대한 **인사이트**를 얻기 위함이다.

| 축 | 설정 |
|----|------|
| **질문** | DAG 기반 agent는 언제 유리하고, 언제 일반 multi-agent(예: Claude Code류)에 밀리는가? |
| **통제 변수** | **LLM은 세 시스템 모두 동일** |
| **독립 변수** | Agent system 아키텍처 3종 (아래 §1) |
| **평가** | [Artificial Analysis Coding Agent Benchmarks](https://artificialanalysis.ai/agents/coding-agents)의 **채점 프로토콜** 차용 |
| **산출** | 시스템별 Index·벤치별 점수·부가 지표 + “잘 구현된 점 / 나쁜 점” |

기존 5차원 주관 루브릭과 노트앱·독립 미션 목록은 **폐기**한다 (§6).

---

## 1. 구축할 Agent System 3종

세 시스템을 **직접 구축**한 뒤, 같은 LLM·같은 태스크 스위트·같은 채점으로 비교한다.

| # | 시스템 ID | 디렉터리 | 무엇을 만드는가 |
|---|-----------|----------|-----------------|
| 1 | **dag-bpd** | `dag-bpd/` | **BPD 논문** 기반 DAG agent 시스템 |
| 2 | **dag-yonsei** | `dag-yonsei/` | **우리가 직접** 설계·구현하는 DAG 시스템 |
| 3 | **general-agent-system** | `general-agent-system/` | **Claude Code와 같은** multi-agent 시스템 |

- 비교 단위는 제품명이 아니라 **`(system_id, llm, settings)`**.
- Artificial Analysis의 harness comparison(모델 고정 · 하네스 비교)과 같은 논리다. 여기서 “하네스/아키텍처”가 위 세 시스템이다.

```text
apps/implementation-comparison/
├── dag-bpd/
├── dag-yonsei/
├── general-agent-system/
├── tasks/                 # 공유 태스크 스위트·verifier 참조 (아래 §3)
└── results/
```

---

## 2. Artificial Analysis와의 관계 (중요)

### 2.1 Agent bench를 따르고, LLM model bench는 따르지 않는다

| 출처 | 내용 | 이 실험 |
|------|------|---------|
| [Coding Agents](https://artificialanalysis.ai/agents/coding-agents) | Coding Agent Index, agent wall time, cost/tokens per task | **따름** (채점·지표·Index 구조) |
| [Methodology](https://artificialanalysis.ai/methodology) | Language Model Intelligence Index, TTFT, output tokens/sec, blended price 등 **모델·엔드포인트** 벤치 | **따르지 않음** (agent 실험의 본점수가 아님) |

이 문서는 “Artificial Analysis **Coding Agent** 채점 프로토콜을 차용한다”고 쓰고, “Language Model benchmark와 동일하다”고 쓰지 않는다.

### 2.2 Index 성분 vs 우리가 비교하는 것

Artificial Analysis Coding Agent Index(이미지·사이트와 동일):

| 벤치마크 | 성격 | 규모 (공개 Index 기준) |
|----------|------|------------------------|
| **DeepSWE** (Datacurve) | Software engineering | 113 tasks |
| **Terminal-Bench v2** (Laude Institute) | Agentic terminal use | 84 tasks |
| **SWE-Atlas-QnA** (Scale AI) | Technical Q&A | 124 tasks |

- 벤치 점수: 태스크당 **pass@1**, **3회 시도** 평균 → 태스크 균등 평균  
- Index: 세 벤치 **동일 가중** 평균  
- 보조축: Time per task · Cost per task · Token usage (본점수 아님)

| | Artificial Analysis | 이 실험 |
|--|---------------------|---------|
| **가로축 (과업)** | DeepSWE · Terminal-Bench v2 · SWE-Atlas-QnA | **같은 3벤치를 공유 스위트로 사용** (§3 기본안) |
| **세로축 (누가 점수를 받나)** | 외부 agent / harness / model variant | **dag-bpd · dag-yonsei · general-agent-system** |
| **한 줄 점수** | variant의 Coding Agent Index | 시스템마다 `Index_system` |
| **의도** | 시장 agent 순위 | **DAG가 언제 유리한지** + 구현 인사이트 |

**과대 표현 금지:** “Artificial Analysis Index와 완전히 동일하다”가 아니라  
“**동일 3벤치 · 동일 채점 공식**으로, **우리가 만든 세 시스템**을 비교한다.”

---

## 3. 태스크 스위트 결정

### 3.1 기본안 (채택)

**Artificial Analysis Coding Agent Index의 공개 3벤치를 공유 태스크 스위트로 사용한다.**

이유: verifier·과업 유형(구현 / 터미널 / Q&A)이 공개 Index와 정렬되어 공신력·재현 비교에 유리하다.

각 시스템에 대해:

```text
S_DeepSWE(system)           = mean_task pass@1 (3 attempts)
S_Terminal-Bench_v2(system) = …
S_SWE-Atlas-QnA(system)     = …
Index_system = mean(S_DeepSWE, S_Terminal-Bench_v2, S_SWE-Atlas-QnA)
```

세 시스템의 `Index_system` 및 벤치별 점수를 같은 표에 올린다.

### 3.2 대안 (공개 벤치 접근 불가 시)

라이선스·하네스·비용 때문에 공개 3벤치를 돌릴 수 없으면:

1. **SE / Terminal / Q&A** 세 카테고리로 자체 스위트를 구성하고  
2. 카테고리별 pass@1(3회) → **동일 가중 Index**는 Artificial Analysis와 같은 공식만 유지한다.  
3. `results/`와 논문/노트에 **“자체 스위트 · Artificial Analysis Index와 수치 직접 비교 불가”** 를 명시한다.

### 3.3 결정 상태

| 항목 | 상태 |
|------|------|
| 채점 공식 (pass@1 × 3, binary, 3성분 동일가중) | **확정** |
| 태스크 본문 | **실행 가능:** `python -m impl_comparison.compare --suite research-30` (§8 자체 30-task suite). 공개 3벤치는 추후 runner·라이선스 확인 후 별도 실행 |

공유 참조 위치: `tasks/research-30/` 및 `src/impl_comparison/research_suite.py`. 공개 벤치 checkout은 아직 연결하지 않는다.

연구 비교는 공개 3벤치가 아니라 §8의 자체 30-task suite를 `--suite research-30`으로 실행한다. 공개 DeepSWE · Terminal-Bench v2 · SWE-Atlas-QnA가 연결되기 전까지 모든 결과에는 **자체 스위트이며 Artificial Analysis 공개 리더보드 수치와 직접 비교할 수 없음**을 표시한다. `Index_system`은 correctness-only이며 time / cost / tokens / turns는 Index에 넣지 않는다.

---

## 4. 채점 규칙 (Coding Agent Index 프로토콜)

세 시스템 모두 아래만 본점수로 쓴다.

### 4.1 태스크 결과

- **binary** pass / fail (verifier).  
- 시도가 끝나도 verifier 미통과 → **0**.

### 4.2 pass@1 (태스크당 3회)

1. 시도별 `1` 또는 `0`  
2. `task_score = (a1 + a2 + a3) / 3`  
3. 벤치 점수 = 해당 벤치(또는 카테고리) 안 태스크 `task_score`의 산술 평균  

### 4.3 Index_system

```text
Index_system = (S_DeepSWE + S_Terminal-Bench_v2 + S_SWE-Atlas-QnA) / 3
```

- Higher is better.  
- Index만 보지 말고 **벤치별 breakdown**을 항상 함께 보고한다.

### 4.4 시스템 비교표 (핵심 산출)

| 시스템 | Index | DeepSWE | Terminal-Bench v2 | SWE-Atlas-QnA | Time | Cost | Tokens |
|--------|-------|---------|-------------------|---------------|------|------|--------|
| dag-bpd | | | | | | | |
| dag-yonsei | | | | | | | |
| general-agent-system | | | | | | | |

**동일 LLM · 동일 스위트 · 동일 시도 횟수**에서만 행을 비교한다.

### 4.5 부가 지표 (본점수·Index에 넣지 않음)

Artificial Analysis Coding Agents 페이지의 보조축과 맞춤:

| 지표 | 정의 | 방향 |
|------|------|------|
| **Time per task** | agent wall time (환경 기동·verifier/judge 제외가 이상적) | Lower is better |
| **Cost per task** | pay-per-token API 비용(USD). 가능하면 input / cached-input / cache-write / output 요금 반영. **구독제 정가와 혼동하지 않음** | Lower is better |
| **Token usage** | **input / cache / output** 분리 (가능할 때) | 참고 |
| **Turns** | 태스크당 에이전트 턴 수 (측정 가능할 때) | 참고 |

### 4.6 인사이트 기록 (정성)

- 잘 구현된 점 / 나쁜 점·실패 모드  
- **벤치별로** DAG가 유리·불리했던 조건 (예: SE는 강함, Terminal은 약함)

---

## 5. 시스템별 디렉터리 · 결과

### 5.1 시스템 디렉터리

| 경로 | 역할 |
|------|------|
| `dag-bpd/` | BPD 기반 DAG agent 구현 + `runs/<variant>/` |
| `dag-yonsei/` | 자체 DAG agent + `runs/<variant>/` |
| `general-agent-system/` | Claude Code류 multi-agent + `runs/<variant>/` |
| `tasks/` | 공유 스위트 핀·실행 방법 (공개 벤치 checkout 또는 자체 스위트) |

### 5.2 `results/`

```text
results/
  comparison.md
  <system_id>/
    score.json       # Index_system + 벤치별 S_* + task attempts
    metrics.json     # time / cost / tokens / turns
    insights.md
```

`score.json` 예시:

```json
{
  "system_id": "dag-yonsei",
  "llm": "…",
  "settings": "…",
  "index": 0.0,
  "benchmarks": {
    "deepswe": 0.0,
    "terminal_bench_v2": 0.0,
    "swe_atlas_qna": 0.0
  },
  "suite": "artificial-analysis-coding-agent-index-components",
  "methodology": "Coding Agent Index protocol: pass@1 mean of 3 attempts; equal-weight DeepSWE, Terminal-Bench v2, SWE-Atlas-QnA; same LLM across systems"
}
```

---

## 6. 폐기한 기존 방법론

- 100점 주관 루브릭 (Accuracy 30, Hallucination 20, …)  
- First-prompt Success / Hallucination Count / Fix Effort를 **본점수**로 사용  
- 스마트 노트 20기능 · 독립 미션 20개를 Index 성분으로 사용  
- [Methodology](https://artificialanalysis.ai/methodology)의 **LLM Intelligence Index / TTFT** 등을 agent 본점수로 사용  

---

## 7. 한 줄 요약

**같은 LLM**으로 **BPD-DAG / 자체 DAG / Claude Code류 multi-agent**를 만들고,  
**Artificial Analysis Coding Agent Index와 같은 3벤치·pass@1(3회)·동일가중 Index**로 점수를 낸 뒤,  
**DAG가 언제 유리한지·구현에서 무엇이 좋고 나쁜지**를 가린다.  
(LLM 모델 벤치마크 페이지의 지표는 본실험 채점이 아니다.)

원 참조:

- [Artificial Analysis — Coding Agents](https://artificialanalysis.ai/agents/coding-agents)  
- [Artificial Analysis — Methodology](https://artificialanalysis.ai/methodology) (LLM 쪽과 **구분**용)

---

## 8. 연구용 30-task suite

기존 fallback 스위트의 3개 태스크는 시스템 간 차이를 충분히 측정하지 못한다. 연구 실행은 **Software Engineering, Terminal / Agentic Workflow, Repository Q&A를 각각 10개씩 총 30개**로 확장하며, 다음 명령으로 실행한다 (동일 LLM은 환경 변수로만 설정):

```sh
export IMPL_COMPARISON_LLM_PROVIDER=openai-compatible
export IMPL_COMPARISON_LLM_MODEL=<model-id>
export IMPL_COMPARISON_LLM_ENDPOINT=<optional-base-url>
export OPENAI_API_KEY=<secret>

python -m impl_comparison.compare --suite research-30
```

자격 증명은 파일에 쓰지 않는다. provider·model 환경 변수가 없으면 오류이며 Fake LLM으로 조용히 대체하지 않는다.

### 8.1 Software Engineering (10)

다중 파일 버그 수정, API 인터페이스 변경, 데이터 모델·스키마 변경, 동시성 race condition, 캐시 무효화, 네트워크 retry·timeout, 인증·권한 보안, hidden edge case, 모듈 리팩터링, 성능 병목 개선을 각각 하나의 태스크로 구성한다.

### 8.2 Terminal / Agentic Workflow (10)

깨진 빌드 분석, 로그 기반 설정 수정, 다중 파일 변환, 실패 테스트 분류, 프로세스 timeout·재시작, checksum 산출물 검증, 환경변수 진단, 대용량 streaming 처리, rollback 후 재실행, 병렬 검사·결과 통합을 각각 하나의 태스크로 구성한다.

### 8.3 Repository Q&A (10)

end-to-end call graph, 설정 영향, root cause, 의존성·변경 영향, 보안 공격 경로, 테스트 공백, 성능 병목, 데이터·상태 흐름, 장애 복구 경로, 아키텍처 trade-off를 각각 하나의 태스크로 구성한다.

### 8.4 난이도와 공정성 통제

- 세 시스템은 동일한 task prompt, 초기 workspace snapshot, LLM, tool schema, timeout, token budget을 사용한다.
- 각 attempt는 새 workspace에서 독립 실행하며, 이전 attempt의 transcript·artifact를 볼 수 없다.
- verifier와 hidden test는 prompt에 포함하지 않는다.
- 연구 점수에는 실제 LLM 실행만 포함한다. Fake LLM은 harness와 CI smoke test 전용이다.
- 각 태스크는 binary verifier를 사용하고, 태스크당 3회 시도한다.
- 결과는 영역별 점수와 전체 Index를 모두 기록한다.

```text
S_SE       = mean(10개 Software Engineering task score)
S_Terminal = mean(10개 Terminal task score)
S_QnA      = mean(10개 Repository Q&A task score)
Index      = mean(S_SE, S_Terminal, S_QnA)
```

이 30개는 공개 DeepSWE·Terminal-Bench v2·SWE-Atlas-QnA 원본이 아니다. 따라서 결과에는 **자체 스위트이며 Artificial Analysis 공개 리더보드 수치와 직접 비교할 수 없음**을 명시한다.
