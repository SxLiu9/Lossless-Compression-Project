# Report writing worksheet — NOT a completed submission report

The project PDF requires the report to be written by the student. Fill in every
section yourself, using your own explanation and the recorded experimental data.
Do not submit this worksheet unchanged.

**Student(s):** ____________________

**Course:** ____________________

**Date:** ____________________

## 1. Objective and constraints

[In your own words: reconstruction requirement, allowed imports, CPU limit, and
the compressed-data-plus-decoder-bytecode scoring metric.]

## 2. Design and implementation

[Explain why the reference scheme is limited and how your selected approach
models English. Explain initial state, dictionary order, context backoff, symbol
exclusion, update exclusion, escape estimation, rescaling, and range coding.
Include enough detail for another student to implement a similar solution.]

## 3. File format and decoder

[Describe the header, alphabet, payload, stopping rule, and integrity check.
Explain how the decoder reconstructs its models without the original text.]

## 4. Experiments and results

[Record your interpreter and machine; verify the master MD5. Explain how you
measured data bytes, .pyc bytes, their sum, bits per character, and user CPU time.
Discuss parameter comparisons using docs/benchmark_results.json. Distinguish
local validation from any test you personally perform on the ECE cluster.]

| Item | Your verified measurement |
|---|---|
| Original bytes / MD5 | |
| Compressed data bytes | |
| Decoder .pyc bytes | |
| Scored total bytes | |
| Total bits per character | |
| Decoder user CPU seconds | |
| Python version and test machine | |

## 5. Discussion

[Explain the main tradeoffs, why the selected order worked for this text, memory
usage, limitations, and what you learned. Do not claim global optimality or ECE
cluster validation unless you have evidence.]

## Acknowledgments

[Required exact section title. Attribute the principal algorithmic ideas and all
AI assistance. State what the AI designed/implemented/tested and what you
personally did. Read docs/acknowledgments_checklist.md and edit the attribution to
match your actual work. Do not claim AI-written code or experiments as your own.]

## References

[List the supplied course material and any external sources you actually used.
Read and verify any recommended literature before citing it.]

## Final submission check

- [ ] The PDF report is written by me/us.
- [ ] The report has a separate section titled Acknowledgments.
- [ ] The original file matches the PDF's MD5.
- [ ] The exact submitted compressed and decompress.py reproduce the original.
- [ ] The user CPU time is below 1,200 seconds on the required environment.
- [ ] Sizes include the compiled decoder under the required Python interpreter.
- [ ] I submit exactly compressed, decompress.py, and my PDF report separately.
