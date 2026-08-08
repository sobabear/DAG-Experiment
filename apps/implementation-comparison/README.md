# Implementation Comparison

이 프로젝트는 **DAG 기반 agent 시스템이 다른 agent 시스템과 비교해 어떤 경우에 장점을 보이는지**를 실험하고, 그로부터 인사이트를 얻기 위한 비교 실험입니다.

| 축 | 설정 |
|----|------|
| **통제** | 세 시스템 모두 **동일한 LLM** |
| **비교 대상** | 직접 구축한 agent system 3종 (아래) |
| **평가** | [Artificial Analysis Coding Agent Benchmarks](https://artificialanalysis.ai/agents/coding-agents)의 **채점 프로토콜** 차용 (LLM 모델 Intelligence Index 아님) |

`dagcore`와는 별도 앱이며, 코어 라이브러리를 바꾸지 않습니다.

## 무엇을 따르고 / 따르지 않는가

| 구분 | 이 실험 |
|------|---------|
| **따름** | [Coding Agents](https://artificialanalysis.ai/agents/coding-agents) — Coding Agent Index 채점 (pass@1 · 3회 · binary · 3벤치 동일가중 · time/cost/tokens) |
| **따르지 않음** | [Methodology](https://artificialanalysis.ai/methodology)의 **Language Model** Intelligence Index, TTFT, output tokens/sec 등 **모델·엔드포인트** 벤치 |

자세한 대비표는 `implementation-comparison-plan.md` §2.

## 구축할 Agent System 3종

| # | 시스템 | 디렉터리 | 설명 |
|---|--------|----------|------|
| 1 | **dag-bpd** | `dag-bpd/` | BPD 논문 기반으로 만든 DAG agent 시스템 |
| 2 | **dag-yonsei** | `dag-yonsei/` | 우리가 직접 설계·구현하는 DAG 시스템 |
| 3 | **general-agent-system** | `general-agent-system/` | Claude Code류의 multi-agent 시스템 |

실행·로그: `<system>/runs/<variant>/` · 집계: `results/`

## Artificial Analysis Index vs 이 실험

| | Artificial Analysis Coding Agent Index | 이 실험 |
|--|----------------------------------------|---------|
| **가로(과업)** | DeepSWE · Terminal-Bench v2 · SWE-Atlas-QnA (동일 가중) | **동일 3벤치를 공유 태스크 스위트로 사용** (권장·기본) |
| **세로(비교 단위)** | agent / harness / model variant | 우리가 만든 **시스템 3종** (동일 LLM) |
| **점수** | variant마다 Index | 시스템마다 `Index_system` 후 세 행 비교 |

```text
Index_system = mean(S_DeepSWE, S_Terminal-Bench_v2, S_SWE-Atlas-QnA)
```

## 실험으로 보고자 하는 것

- DAG가 **유리한 과업/조건** vs **불리한 조건** (벤치별 breakdown 포함)
- BPD DAG vs 자체 DAG vs general multi-agent의 **상대 성능**
- 구현상 **잘 된 점 / 나쁜 점** (실패 모드, verifier, 시간·토큰)

## 평가 요약

- binary pass/fail (verifier)
- 태스크당 **pass@1**, 시도 **3회** 평균 → 벤치 점수 → Index 동일가중
- 부가: time / cost / tokens(input·cache·output) / turns
- 세부: `implementation-comparison-plan.md`

## 문서

- 연구 목적·채점·시스템 정의: `implementation-comparison-plan.md`
- 레이아웃 스펙: `docs/superpowers/specs/2026-08-08-implementation-comparison-design.md`
