# Security & Responsible Use

POCanator is a tool for **authorized security research, defensive security, and
education**. It analyzes public GitHub Security Advisories, summarizes patches,
and generates educational proof-of-concept material to help defenders
understand how vulnerabilities work and how they are fixed.

Please read this document before using the project.

## Acceptable use

Use POCanator **only** for:

- Studying vulnerability classes and secure-coding patterns for education.
- Analyzing advisories and patches for software **you own or are explicitly
  authorized to test**.
- Defensive work: detection engineering, patch validation, triage, and
  security training.
- Academic and research purposes conducted lawfully and ethically.

## Prohibited use

Do **not** use POCanator to:

- Attack, probe, or exploit systems, networks, or software you do not own and
  do not have **explicit written authorization** to test.
- Develop or distribute working exploits intended to cause harm, gain
  unauthorized access, or disrupt services.
- Violate any applicable law, regulation, contract, or acceptable-use policy.

You are solely responsible for how you use this software and for obtaining any
authorization required in your jurisdiction. The authors and contributors
accept no liability for misuse (see the "AS IS" disclaimer in `LICENSE`).

## Generated content

PoC and analysis output is produced by large language models and is intended to
be **educational**. It may be inaccurate, incomplete, or unsafe to run. Treat
all generated code as untrusted: review it, and only execute it inside isolated,
disposable environments you control.

## Reporting a vulnerability in POCanator

If you discover a security vulnerability **in POCanator itself**, please report
it privately rather than opening a public issue:

1. Open a [GitHub Security Advisory](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
   on this repository ("Report a vulnerability"), **or**
2. Contact the maintainers privately through the repository's contact channel.

Please include steps to reproduce, affected versions, and potential impact.
We aim to acknowledge reports within a reasonable time and will coordinate a
fix and disclosure timeline with you.

Do not include details of unrelated third-party systems or any data obtained
without authorization in your report.
