# Implementation Comparison Plan

## 0. 연구 목적

이 프로젝트는 **DAG가 다른 agent 시스템과 비교해 어떤 경우에 장점을 보이는지**를 실험하고, 구현·실패 모드에 대한 **인사이트**를 얻기 위함이다.

| 축 | 설정 |
|----|------|
| **질문** | DAG 기반 agent는 언제 유리하고, 언제 일반 multi-agent(예: Claude Code류)에 밀리는가? |
| **통제 변수** | **LLM은 세 시스템 모두 동일** |
| **독립 변수** | Agent system 아키텍처 3종 (아래 §1) |
| **평가** | [Artificial Analysis Coding Agent Benchmarks](https://artificialanalysis.ai/agents/coding-agents)와 **같은 채점 구조** |
| **산출** | 시스템별 점수·부가 지표 + “잘 구현된 점 / 나쁜 점” 구분 (강점·약점·실패 원인) |

기존 5차원 주관 루브릭(Accuracy / Hallucination / Quality / Robustness / Efficiency)과 노트앱·독립 미션 요구사항 목록은 **폐기**한다.

참고: Artificial Analysis **Coding Agent Index** — binary pass/fail, 태스크당 pass@1(시도 3회 평균), 합성 점수와 per-component breakdown, 보조축으로 time / cost / tokens.

---

## 1. 구축할 Agent System 3종

세 시스템을 **직접 구축**한 뒤, 같은 LLM·같은 평가 잣대로 비교한다.

| # | 시스템 ID | 디렉터리 | 무엇을 만드는가 |
|---|-----------|----------|-----------------|
| 1 | **dag-bpd** | `dag-bpd/` | **BPD 논문** 기반으로 DAG를 구성한 agent 시스템 |
| 2 | **dag-yonsei** | `dag-yonsei/` | **우리가 직접** 설계·구현하는 DAG 시스템 |
| 3 | **general-agent-system** | `general-agent-system/` | **Claude Code와 같은** multi-agent 시스템 |

- 비교 단위는 “코딩 툴 제품명”이 아니라 **우리가 구축한 agent system variant**이다.
- 기록 시 반드시 명시: **`(system_id, llm, settings)`**. LLM은 세 시스템에서 동일하게 고정한다.

```text
apps/implementation-comparison/
├── dag-bpd/                      # BPD 기반 DAG agent
│   └── runs/<variant>/
├── dag-yonsei/                   # 자체 DAG agent
│   └── runs/<variant>/
├── general-agent-system/         # Claude Code류 multi-agent
│   └── runs/<variant>/
└── results/                      # 시스템 간 비교·인사이트
```

---

## 2. 평가 잣대 (Artificial Analysis와 동일 구조)

세 시스템 모두 아래 규칙으로만 채점한다. “어느 쪽이 얼마나 잘 구현됐는지 / 무엇이 나쁜지”는 **점수 + 실패 로그 + 부가 지표**로 구분한다.

### 2.1 태스크 결과

- 모든 태스크 결과: **binary** pass / fail (verifier 또는 공식 테스트).
- 시도가 끝나도 verifier 미통과면 **0**.

### 2.2 pass@1 (태스크당 3회)

Artificial Analysis와 같이, 태스크마다 **최대 3회** 독립 시도한다.

1. 시도별: `1` (pass) 또는 `0` (fail)
2. `task_score = (a1 + a2 + a3) / 3`
3. 시스템 점수 `S_system` = 그 시스템이 돌린 태스크들의 `task_score` 산술 평균 (태스크 가중 동일)

### 2.3 시스템 간 비교 (본 실험의 핵심 표)

Artificial Analysis가 agent variant마다 Index를 내는 것처럼, **시스템마다** 점수를 낸 뒤 나란히 비교한다.

| 시스템 | Score (higher is better) | Time / Cost / Tokens |
|--------|--------------------------|----------------------|
| dag-bpd | `S_bpd` | … |
| dag-yonsei | `S_yonsei` | … |
| general-agent-system | `S_gas` | … |

- **동일 LLM · 동일 태스크 스위트**에서만 세 행을 비교한다.
- 필요하면 태스크를 카테고리로 나눠 per-category breakdown을 둔다. (Artificial Analysis의 per-benchmark breakdown과 같은 역할: Index/총점만 보지 않기)

### 2.4 부가 지표 (Index/본점수에 넣지 않음)

| 지표 | 정의 | 방향 |
|------|------|------|
| **Time per task** | 에이전트 wall time (환경 기동·verifier 제외가 이상적) | Lower is better |
| **Cost per task** | pay-per-token API 비용(USD); 불가하면 명시 후 생략 | Lower is better |
| **Token usage** | input / cache / output (가능할 때) | 참고 |

성능–비용–시간으로 “잘 되지만 비싸거나 느린” 경우를 구분한다.

### 2.5 인사이트 기록 (정성)

점수와 별도로, 시스템마다 짧게 남긴다.

- **잘 구현된 점:** 안정적으로 pass하는 태스크 유형, 구조적 강점
- **나쁜 점 / 실패 모드:** 반복 fail 원인, DAG vs multi-agent에서 깨지는 지점
- **DAG가 유리했던 조건 / 불리했던 조건**

---

## 3. 시스템별 디렉터리 역할

각 디렉터리는 **해당 agent 시스템의 코드·설정·verifier 연동·실행 산출물**을 둔다.

### 3.1 `dag-bpd`

- BPD 논문 아이디어(계층형/부호 있는 DAG 등)를 따른 agent 시스템 구현.
- 실행: `dag-bpd/runs/<variant>/`

### 3.2 `dag-yonsei`

- Yonsei 쪽에서 자체 설계한 DAG agent 시스템 구현.
- 실행: `dag-yonsei/runs/<variant>/`

### 3.3 `general-agent-system`

- Claude Code류 multi-agent 패턴을 따르는 일반 agent 시스템 구현 (DAG 특화와 대비되는 baseline).
- 실행: `general-agent-system/runs/<variant>/`

> 공유 태스크 스위트·verifier는 이후 `tasks/` 등으로 두거나 각 시스템에서 동일 스펙을 참조한다. 채점 **방법**은 §2로 고정한다.

---

## 4. 결과 기록 (`results/`)

```text
results/
  comparison.md              # 세 시스템 표 + 인사이트 요약
  <system_id>/
    score.json               # S_system, task별 attempts·task_score
    metrics.json             # optional: time / cost / tokens
    insights.md              # 잘된 점 / 나쁜 점 / DAG 유리·불리 조건
```

`score.json` 예시:

```json
{
  "system_id": "dag-yonsei",
  "llm": "…",
  "settings": "…",
  "score": 0.0,
  "tasks": {
    "task_001": { "attempts": [1, 0, 1], "task_score": 0.6667 }
  },
  "methodology": "Artificial Analysis Coding Agent Index–style: pass@1 mean of 3 attempts per task; same LLM across systems"
}
```

---

## 5. 폐기한 기존 방법론

다음을 이 계획에서 **사용하지 않는다**.

- 100점 배점 주관 루브릭 (기능 정확성 30, 환각 20, …)
- First-prompt Success / Hallucination Count / Fix Effort를 **본점수**로 쓰는 방식
- 스마트 노트 앱 20기능 · 독립 미션 20개 목록을 본 실험 Index 성분으로 쓰는 방식

---

## 6. 한 줄 요약

**같은 LLM**으로 **BPD-DAG / 자체 DAG / Claude Code류 multi-agent** 세 시스템을 만들고, **Artificial Analysis식 평가**로 점수를 낸 뒤, **DAG가 언제 유리한지·구현에서 무엇이 좋고 나쁜지**를 가린다.

방법론 원 참조: [Artificial Analysis — Coding Agents](https://artificialanalysis.ai/agents/coding-agents)
