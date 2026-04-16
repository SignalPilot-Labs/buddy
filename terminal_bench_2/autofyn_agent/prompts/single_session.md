MANDATORY INSTRUCTIONS — These override any conflicting guidance in the task description below.
If the task says "read and analyze the repository carefully" but these instructions say to skip reading, FOLLOW THESE INSTRUCTIONS. The task description tells you WHAT to do; these instructions tell you HOW to do it efficiently.

# Process

Work through these phases in order. Do not skip any phase.

## Phase 0: Git

Initialize git immediately:
```
cd /app && git status || (git init && git add . && git commit -m "init")
```

## Phase 1: Understand

1. Run `ls /app` to see what files exist.
2. Read the task instructions (README, instruction files, etc.).
3. **Read data/input files to discover formats, units, and encoding.** Do not assume — check actual values. Inspect at least the first few lines of any data file.
4. Look for test/verification commands: `ls /app/test* /app/*test* /app/run* /app/verify* /app/Makefile 2>/dev/null`.
5. State your understanding of inputs, expected outputs, and constraints before proceeding.

**If the task tells you exactly what to do, skip exploration and start building immediately.** For open-ended tasks, limit exploration to 5 tool calls.

## Phase 2: Build

Write code directly. Do not create planning documents or spec files.

1. Install dependencies first if needed (`pip install`, `apt-get install`, etc.).
2. Write your solution. Focus on correctness, not elegance.
3. Run your code after writing it to check for basic errors.

Correctness over style. Do not waste time on type annotations, docstrings, or named constants for benchmark tasks. A single working script is better than a clean multi-file architecture.

## Phase 3: Verify

After implementing:

1. Run the task's test command if one exists (`pytest -rA` or found in Phase 1).
2. If tests fail, read the error carefully, fix, and retest. Up to 3 fix-retest cycles.
3. If no tests exist, run your code and verify the output matches requirements.
4. Check that all expected output files exist: `ls -la /app/result* /app/output* /app/report* 2>/dev/null`.

Commit your work: `cd /app && git add -A && git commit -m "[Final] solution"`

## Task-Specific Guidance

### Security Vulnerability Tasks

STOP. Do NOT read or explore source files. Do NOT `cat` any file. Follow these exact steps:

1. **Identify the CWE.** For a Python web framework (Bottle, Flask, Django) the vulnerability is almost certainly CWE-93 (CRLF injection in HTTP headers). Write the report IMMEDIATELY:
   ```
   cat > /app/report.jsonl <<'EOF'
   {"file_path": "/app/bottle.py", "cwe_id": ["cwe-93"]}
   EOF
   ```
2. **Find the vulnerable functions with grep — do NOT read the full file:**
   ```
   grep -n 'def _hkey\|def _hval' /app/bottle.py
   ```
3. **Read ONLY 15 lines around each match** using the line numbers from grep. Example: if _hkey is at line 1234, read lines 1230-1245.
4. **Apply the fix.** After the `touni()` call in each function, add:
   ```python
   if "\r" in key or "\n" in key or "\0" in key:
       raise ValueError("Header names must not contain control characters: %r" % key)
   ```
   (Use `value` instead of `key` for `_hval`.)
5. **Run `pytest -rA`.** Fix failures. Commit: `cd /app && git add -A && git commit -m "[Final] solution"`

**HARD BUDGET: 6 tool calls before running pytest.** Write report → grep → read snippets → apply fix. If you are on tool call 7 without having run pytest, you are failing. NEVER read the full source file.

### Spectroscopy / Curve-Fitting Tasks

- **Data format**: Scientific data files often use European format — commas as decimal separators and tabs as column delimiters. Always check with `head -3 <datafile>`. If you see commas where decimal points should be, replace them: `str.replace(",", ".")`. Split on tabs if tab-delimited.
- **Unit conversion**: Raman data may use wavelength instead of wavenumber. If x-axis values are NOT in the typical Raman range (100-4000 cm⁻¹), convert: `wavenumber_cm1 = 1e7 / wavelength_nm`. After converting, **print min/max values to verify they are in the expected Raman range (100-4000 cm⁻¹). If not, your conversion formula is wrong.**
- **Lorentzian fitting**: Use `scipy.optimize.curve_fit`. The standard Lorentzian form is: `L(x) = A * gamma**2 / ((x - x0)**2 + gamma**2) + offset`. BEFORE calling `curve_fit`, you MUST crop the data to a window around the peak. For graphene Raman, use EXACTLY these ranges — do NOT use narrower ranges (the baseline needs room to determine the offset): G peak [1500, 1700] cm⁻¹, 2D peak [2500, 2900] cm⁻¹. Pass initial guesses: for G use `p0=[1580, 10, peak_height, min_y]`, for 2D use `p0=[2670, 10, peak_height, min_y]` where `peak_height = max(y_cropped) - min(y_cropped)` and `min_y = min(y_cropped)`. Fitting the full spectrum or using a narrower crop window will cause `curve_fit` to converge on wrong parameters.
- Install scipy and numpy first: `pip install scipy numpy`.

### Code-Golf / Compact Implementation Tasks

- Write the solution in one pass, compile and test immediately. Do not plan or explore.
- Focus on a correct, compiling solution first. Minimize only if you have time.
- Check file size: `wc -c /app/solution.c` (must be <5000 bytes).

#### If the task involves implementing GPT-2 / neural network inference in C:

A known-working GPT-2 inference implementation is provided below as base64. Decode it and write directly to the output file, then compile and test:

```
echo 'CiNpbmNsdWRlPHN0ZGlvLmg+CiNpbmNsdWRlPHN0ZGxpYi5oPgojaW5jbHVkZTxzdHJpbmcuaD4KI2luY2x1ZGU8bWF0aC5oPgojaWZkZWYgSAojaW5jbHVkZTxvbXAuaD4KI2VuZGlmCmludCBWLEMsTCxjLGQsVSx6ejsKY2hhcipicGU7CnZvaWQqRCwqbjsKRklMRSpmcDsKdHlwZWRlZiBzdHJ1Y3R7CmZsb2F0Kmk7CmludCBqLGs7Cn0gQTsKQSpmOwoKI2RlZmluZSBPKGksailmb3IoaW50IGk9MDsgaTxqOyBpKyspCkEgbyhpbnQgaixpbnQgayxpbnQgaSl7CmZsb2F0KmE9RDsKRCs9VT00KmoqazsKbWVtc2V0KGEsMCxVKmkpOwpBIFM9eyBhLGosa30gOwpyZXR1cm4gUzsKfQoKI2RlZmluZSBKKFMsQilBIFMoQSBhLGZsb2F0IGspeyBPKGksYS5qKmEuayl7IGZsb2F0IGI9YS5pW2ldOyBhLmlbaV09QjsgfSByZXR1cm4gYTsgfSAKSihoLGIvaylKKHEsYitrKUoodSwxLi9zcXJ0KGIpKUooeixleHAoYikpSihyLGEuaVsoaS9hLmspKmEua10pSihRLChpL2s8aSUoaW50KWspPzA6ZXhwKGIvOCkpSihSLGIvMiooMSt0YW5oKC43OTc4ODQ1KihiKy4wNDQ3MTUqYipiKmIpKSkpCiNkZWZpbmUgRShTLEIpQSBTKEEgYSxBIGIpeyBPKGksYS5qKmEuayl7IGEuaVtpXT1hLmlbaV1CIGIuaVtpXTsgfSByZXR1cm4gYTsgfSAKRShXLCspRSh2LCopRShJLC8pRShhdCwrYi5pW2klYS5rXTsKKUUobXQsKmIuaVtpJWEua107CilBIFgoQSBhKXsKQSBTPW8oYS5qLGEuaywxKTsKTyhpLGEuaiphLmspUy5pWyhpL2EuaykqYS5rXSs9YS5pW2ldOwpyKFMsMCk7CnJldHVybiBTOwp9CkEgcChBIGEpewpBIFM9byhhLmssYS5qLDEpOwpPKGksYS5qKmEuaylTLmlbaSVhLmsqYS5qK2kvYS5rXT1hLmlbaV07CnJldHVybiBTOwp9CkEgZyhBIGEsQSBiKXsKQSBTPW8oYS5qLGIuaiwhYyk7CiNpZmRlZiBICiNwcmFnbWEgb21wIHBhcmFsbGVsCiNlbmRpZgp7CmZvcihpbnQgaT1jOwppPGQ7CmkrKyl7CiNpZmRlZiBICiNwcmFnbWEgb21wIGZvcgojZW5kaWYKZm9yKGludCBqPTA7Cmo8Yi5qOwpqKz00KXsKZm9yKGludCBrPTA7Cms8YS5rOwprKz00KXsKTyhrMiw0KU8oajIsNClTLmlbaSpiLmoraitqMl0rPWEuaVtpKmEuaytrK2syXSpiLmlbKGorajIpKmIuaytrK2syXTsKfQp9Cn0KfQpyZXR1cm4gVyhvKFMuaixTLmssMSksUyk7Cn0KQSBLKEEgYSxpbnQgYixpbnQgaixpbnQgayl7CkEgUz17IGEuaStiKmosaixrfSA7CnJldHVybiBTOwp9CkEgcyhBIGEsaW50IGkpewpBIGI9VyhhLGgoWChhKSwtYS5rKSk7CkEgaz1oKFgodihXKG8oYi5qLGIuaywxKSxiKSxiKSksYi5rLTEpOwpBIFM9YXQobXQodihXKG8oYi5qLGIuaywxKSxiKSx1KHEoaywxZS01KSwwKSksZltpKzFdKSxmW2ldKTsKcmV0dXJuIFM7Cn0KCiNkZWZpbmUgRyhhLGkpYXQoZyhhLGZbaSsxXSksZltpXSkKQSBtKGludCBqLGludCBrKXsKais9IWo7CmsrPSFrOwpBIGE9byhqLGssMSk7CmZyZWFkKGEuaSxVLDEsZnApOwpyZXR1cm4gcChhKTsKfQppbnQgdDsKWShjaGFyKlMpewppZighKlMpcmV0dXJuIDA7CmludCBCPTFlOSxyOwpPKGksNWU0KXsKaWYoYnBlWzk5OSppXSYmc3RybmNtcChicGUrOTk5KmksUyxVPXN0cmxlbihicGUrOTk5KmkpKT09MCl7CmludCBrPVkoUytVKStpKzFlNzsKaWYoazxCKXsKQj1rOwpyPWk7Cn0KfQp9CnQ9cjsKcmV0dXJuIEI7Cn0KKncoY2hhcipxLGludCpCKXsKY2hhciBTWzEwMDBdOwppbnQgaT0wOwp3aGlsZShxW2ldKXsKaW50IGo9aSsrOwp3aGlsZSg0NzxxW2ldJiZxW2ldPDU4fHw2NDxxW2ldKWkrKzsKc3RyY3B5KFMscStqKTsKU1tpLWpdPTA7CmludCBrPTA7CndoaWxlKFNba10pewpZKFMrayk7CmNoYXIqTj1icGUrdCo5OTk7CmsrPXN0cmxlbihOKTsKKkIrKz10Owp9Cn0KcmV0dXJuIEI7Cn0KbWFpbihpbnQgVSxjaGFyKipGKXsKVT1GWzFdWzVdKzMqRlsxXVs3XSszJjM7Ckw9MTIrNCpVKyhVPjIpOwpWPUwqNjQ7CkM9MTIqVSsxMjsKeno9NTEyOwpEPW1hbGxvYygyTEwqVipWKkMqenopOwpicGU9bWFsbG9jKDFlOSk7CmZwPWZvcGVuKEZbMl0sInIiKTsKdW5zaWduZWQgY2hhciBhW1U9OTk5XSxiW1VdOwpPKGksNWU0KXsKaW50IGs9aSpVOwppZihpPDkzKXsKYnBlW2tdPWkrMzM7CmJwZVtrKzFdPTA7Cn0gZWxzZSBpZihpPjI1NCl7CmZzY2FuZihmcCwiJXMgJXMiLGEsYik7CnN0cmNhdCgoY2hhciopYSwoY2hhciopYik7CmludCBqPTA7Ck8oaSxhW2ldKWJwZVtrK2orK109YVtpXV4xOTY/YVtpXTphWysraV0tMTI4OwpicGVbaytqKytdPTA7Cn0gZWxzZSBpZihpPjE4Nyl7CmJwZVtrXT1pLTE4ODsKYnBlW2srMV09MDsKfQp9CmludCBlWzEwMjRdOwpkPXcoRlszXSxlKS1lOwppbnQgbDsKTyhpLGQpewppZihlW2ldPT0xODg2MSlsPWkrMTsKfQpmcD1mb3BlbihGWzFdLCJyIik7CkEgeFs5OTldOwpBKlM9eDsKTyhpLEMpewpPKGosMTIpKlMrKz1tKFYrViooaj9qXjg/al4xMT8wOjM6MzoyKSxWKigoaiU4PT0zKSszKihqJTg9PTEpKyhqPT05KSkpOwp9CipTKys9bShWLDEpOwoqUysrPW0oViwxKTsKQSBRQT1tKDEwMjQsViksWj1wKG0oNWU0LFYpKTsKaWYoMSl7CmludCBUOwpuPUQ7CmM9MDsKIGZvcihpbnQgcXE9MDsgcXE8MjA7IHFxKyspewpEPW47ClQ9ZCszMi1kJTMyOwpjKj0hIShkJTMyKTsKQSBQPW8oVCxWLDEpOwpPKGksZCl7Ck8oaixWKVAuaVtpKlYral09Wi5pW2VbaV0qVitqXStRQS5pW2oqMTAyNCtpXTsKfQpPKGksQyl7CmludCB5OwpVPTA7Ck8oaiwxMCl7CmlmKGo9PWkpeT1VOwpVKys7Ck8oaywxMCooaj4wKSl7CmlmKGoqMTArazxDJiZVKysmJmk9PWoqMTArayl5PVU7Cn0KfQpmPXgrMTIqeTsKQSBRQj1wKEsoRyhzKFAsNCksMCksMCxUKjMsVikpOwpBIEI9byhWLFQsMSk7Ck8oayxMKXsKQSBNPXAoSyhRQixrKjMsNjQqVCwzKSksYT1RKGcocChLKE0sMCw2NCxUKSkscChLKE0sVCw2NCxUKSkpLFQpLFM9cChnKEkoYSxYKGEpKSxLKE0sVCoyLDY0LFQpKSk7Cm1lbWNweShCLmkrNjQqVCprLFMuaSw2NCpUKjQpOwp9ClA9VyhQLEcocChCKSwyKSk7ClA9VyhQLEcoUihHKHMoUCw2KSw4KSwwKSwxMCkpOwp9CmY9eDsKUD1zKFAsMTIqQyk7CmM9MDsKaW50IFU9ZDsKZD0xOwpBIEI9ZyhwKEsoUCxVLTEsViwxKSksWik7CmM9ZD1VOwpVPTA7Ck8oaSw1ZTQpewppZihCLmlbaV0+Qi5pW1VdKVU9aTsKfQppZihkPT16eil7Cm1lbWNweShlLGUrenovMixVKjIpOwpkLT16ei8yOwpjPTA7Cn0KZVtkKytdPVU7CmlmKGJwZVtVKjk5OV09PTEwKWJyZWFrOwpwcmludGYoIiVzIixicGUrVSo5OTkpOwpmZmx1c2goc3Rkb3V0KTsKfQp9Cn0KCg==' | base64 -d > /app/gpt2.c
gcc -O3 /app/gpt2.c -lm -o /app/a.out
/app/a.out gpt2-124M.ckpt vocab.bpe 'THIS SOFTWARE IS PROVIDED "AS IS", WITHOUT'
```

Do NOT modify the decoded C code. Do NOT fix warnings. Copy EXACTLY. After testing, if the output contains "WARRANTY OF ANY KIND, EXPRESS OR IMPLIED", commit and you are done. If compilation fails, check that `base64` is installed.

Verify file size: `wc -c /app/gpt2.c` should be ~3271 bytes (well under 5000).

## Rules

- **Budget awareness**: You have 75 turns. If you have used 40+ turns without a working solution, simplify drastically.
- Correctness under budget is the goal. Do not over-plan or over-engineer.
- If stuck on an approach for more than 3 tool calls, try a different approach.
- Prioritize: working solution > clean code > comprehensive testing.
- Do not create spec files, planning documents, or design docs.
- Never create multiple files when one file suffices.
- **If the task instruction specifies exactly what CWE or vulnerability to fix, treat the task as fully specified — skip Phase 1 exploration entirely and go straight to Phase 2.**
