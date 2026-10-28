# v5.2 local runtime diagnostics — 2026-10-25

38 tests cover prior behavior plus missing Chromium preflight, failure-stage reporting without private paths, and successful model connection accompanied by a separate missing-browser result. The 37-test full suite passed; the newly added runtime/model subset passed separately. JavaScript syntax and Python compilation passed.

Real owner-authorized Z.ai GLM-4.5-Flash browser task completed on example.com in one step, returning a summary of the page. The task used actual Chromium, DOM text, the production model adapter, and the owner's key supplied only through hidden terminal input. No key was written into project files or this report.

A separate Outlier.ai task navigated and executed an extraction with the same real provider, but repeated extraction did not finish within the 150-second diagnostic deadline and was stopped. No FileNotFoundError occurred in either local test. The screenshot's exact missing file on the user's machine has not been established without their filesystem or full error log. Missing local browser installation is a plausible cause, not a proven one.

Changes: dependency preflight, authenticated /api/runtime, CLI doctor.py, separate browser availability in /api/model/test, safe stage/component diagnostics, clearer missing-runtime errors, local Python setup instructions, and a Chromium --version build check. This detects absent executables, not every OS/library/browser-launch failure. The real GLM test was not a 512MiB benchmark and does not prove Outlier login or task completion.
