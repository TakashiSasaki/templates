---
id: review.require-performance-evidence
severity: mandatory
overridable: true
order: 890
---
# Require realistic workload evidence for performance findings

Report a blocking performance or resource finding only when the changed major path can be connected to realistic call frequency or input size and to material latency, timeout, rate-limit, memory, descriptor, connection, thread, process, or service-level impact. A loop containing I/O or a worse asymptotic shape is not sufficient without a realistic workload and consequence.
