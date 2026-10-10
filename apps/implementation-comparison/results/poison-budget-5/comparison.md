# Poison-injection comparison

Poison suite measures accuracy, lie propagation, source detection, and recovery. It is not an Index and cannot be compared with Artificial Analysis.

Cost and tokens are logged only. They are not part of the attribution rates.

## Controlled (micro-QnA, string-match grading)

| system | accuracy | propagation | detection | recovery | cost (USD) | tokens in/out/cache |
|--------|----------|-------------|-----------|----------|------------|---------------------|
| general-agent-system | 0.990 | 0.010 | 0.000 | 0.000 | 0.0000 | 126394/3261/0 |
| general-majority-3 | 1.000 | 0.000 | 0.000 | 0.000 | 0.0000 | 364549/9958/0 |
| flat-majority-3 | 1.000 | 0.000 | 1.000 | 1.000 | 0.0000 | 302811/7241/0 |
| judge-only-3 | 1.000 | 0.000 | 0.840 | 0.840 | 0.0000 | 302158/7256/0 |
| dag-bpd | 1.000 | 0.000 | 0.880 | 0.880 | 0.0000 | 301459/7216/0 |

## Realistic (code-verifiable, hidden pytest grading)

| system | accuracy | propagation | detection | recovery | cost (USD) | tokens in/out/cache |
|--------|----------|-------------|-----------|----------|------------|---------------------|
| general-agent-system | 0.840 | 0.110 | 0.000 | 0.000 | 0.0000 | 300975/14001/0 |
| general-majority-3 | 1.000 | 0.000 | 0.000 | 0.000 | 0.0000 | 843722/45328/0 |
| flat-majority-3 | 0.910 | 0.090 | 0.000 | 0.000 | 0.0000 | 808454/44106/0 |
| judge-only-3 | 1.000 | 0.000 | 0.630 | 0.630 | 0.0000 | 815450/43897/0 |
| dag-bpd | 0.990 | 0.010 | 0.630 | 0.630 | 0.0000 | 813676/44942/0 |

## Metrics

- **accuracy:** final answer/code passes grading (string match for micro-QnA, hidden pytest for code tasks), not the planted lie
- **propagation:** the planted lie appears in the final answer or code
- **detection:** the system names the poisoned worker or scan node
- **recovery:** detection and accuracy together

