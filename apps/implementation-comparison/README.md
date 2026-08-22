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
| **가로(과업)** | DeepSWE · Terminal-Bench v2 · SWE-Atlas-QnA (동일 가중) | **자체 30-task suite**: SE 10 · Terminal 10 · Repository Q&A 10 |
| **세로(비교 단위)** | agent / harness / model variant | 우리가 만든 **시스템 3종** (동일 LLM) |
| **점수** | variant마다 Index | 시스템마다 `Index_system` 후 세 행 비교 |

```text
Index_system = mean(S_SE, S_Terminal, S_Repository_QnA)
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

## 로컬 테스트

앱 디렉터리에서 가상환경을 사용해 설치하고 테스트합니다:

```sh
python -m pip install -e '.[dev]'
python -m pytest
PYTHONPATH=src:../../../src python -m impl_comparison.compare
```

`--suite fallback`(각 영역 1태스크)은 CI smoke입니다. **The 30-task suite is now executable** with `--suite research-30` after configuring the same real LLM for all three systems through environment variables (never files):

```sh
export IMPL_COMPARISON_LLM_PROVIDER=openai-compatible
export IMPL_COMPARISON_LLM_MODEL=<model-id>
# optional:
export IMPL_COMPARISON_LLM_ENDPOINT=<openai-compatible-base-url>
export OPENAI_API_KEY=<secret>   # OpenAI SDK reads this; do not copy into files

PYTHONPATH=src:../../../src python -m impl_comparison.compare --suite research-30
```

Missing `IMPL_COMPARISON_LLM_PROVIDER` or `IMPL_COMPARISON_LLM_MODEL` is an error. research-30 does not silently substitute a harness Fake LLM. Optional `apps/implementation-comparison/.env.example` lists empty placeholders; never commit `.env`. The harness does **not** auto-load `.env`. Export variables into the process (or `set -a; source .env`) before running.

For a real-LLM run, install optional OpenAI support next to the command:

```sh
python -m pip install -e '.[dev,openai]'
```

`Index_system` is **correctness-only** (equal-weight SE / Terminal / QnA pass@1). Time, cost, tokens, and turns are reported beside Index and are not part of the score.

공개 DeepSWE · Terminal-Bench v2 · SWE-Atlas-QnA는 아직 연결하지 않았습니다. This is a custom suite and cannot be compared numerically with the public Artificial Analysis leaderboard.

OpenAI 지원은 선택 사항이며 fallback smoke 테스트에는 필요하지 않습니다.

## 확장 평가 스위트 (30 tasks)

현재 3개 태스크는 아키텍처 차이를 충분히 드러내지 못하므로, 연구용 스위트는 다음 30개로 확장합니다:

- **Software Engineering 10개**: 다중 파일 수정, API/스키마 변경, 동시성, 캐시, 보안, 장애 복구, 리팩터링, 성능 개선
- **Terminal / Agentic Workflow 10개**: 로그 분석, 다단계 명령, timeout, checksum, 대용량 파일, rollback, 병렬 검사
- **Repository Q&A 10개**: call graph, 설정 영향, root cause, 의존성, 보안, 테스트 공백, 성능, 상태 흐름, 장애 복구, 설계 trade-off

각 태스크는 숨겨진 verifier를 사용하고 3회 독립 시도합니다. Fake LLM 결과는 harness 검증용이며 연구 결과에 포함하지 않습니다.
