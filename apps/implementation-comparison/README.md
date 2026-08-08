# Implementation Comparison

이 프로젝트는 **DAG 기반 agent 시스템이 다른 agent 시스템과 비교해 어떤 경우에 장점을 보이는지**를 실험하고, 그로부터 인사이트를 얻기 위한 비교 실험입니다.

- **통제:** 세 시스템 모두 **동일한 LLM** 사용
- **평가:** [Artificial Analysis Coding Agent Benchmarks](https://artificialanalysis.ai/agents/coding-agents)와 같은 채점 구조 (pass@1, 태스크당 3회 시도, binary verifier, time/cost/tokens 등)
- **비교 대상:** 아래 **agent system 3종**을 직접 구축한 뒤, 같은 잣대로 구현 품질·강점·약점을 구분

`dagcore`와는 별도 앱이며, 코어 라이브러리를 바꾸지 않습니다.

## 구축할 Agent System 3종

| # | 시스템 | 디렉터리 | 설명 |
|---|--------|----------|------|
| 1 | **dag-bpd** | `dag-bpd/` | BPD 논문 기반으로 만든 DAG agent 시스템 |
| 2 | **dag-yonsei** | `dag-yonsei/` | 우리가 직접 설계·구현하는 DAG 시스템 |
| 3 | **general-agent-system** | `general-agent-system/` | Claude Code류의 multi-agent 시스템 |

각 시스템 실행·로그: `<system>/runs/<variant>/`  
집계·비교표: `results/`

## 실험으로 보고자 하는 것

- DAG가 **유리한 과업/조건** vs **불리한 조건**
- BPD 기반 DAG vs 자체 DAG vs general multi-agent의 **상대 성능**
- 구현상 **잘 된 점 / 나쁜 점** (실패 모드, verifier 미통과 원인, 시간·토큰 비효율 등)

## 평가 요약

Artificial Analysis Coding Agent Index와 동일 계열:

- 태스크 결과: **pass / fail** (verifier)
- 태스크 점수: **pass@1**, 시도 **3회** 평균
- 시스템별 점수 + (선택) time / cost / tokens
- 동일 LLM · 동일 태스크 스위트로 세 시스템을 나란히 비교

세부 규칙은 `implementation-comparison-plan.md`를 따릅니다.

## 문서

- 연구 목적·채점·시스템 정의: `implementation-comparison-plan.md`
- 레이아웃 스펙: `docs/superpowers/specs/2026-08-08-implementation-comparison-design.md`
