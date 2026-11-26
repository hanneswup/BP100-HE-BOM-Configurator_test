# Local LLM experiment

This opt-in experiment sends extracted checklist text to an Ollama server at `127.0.0.1:11434` on the **same machine as Streamlit**. It does not use an API endpoint configured by the user and disables HTTP proxies and redirects. Do not use confidential documents or models unless the environment and data processing have been approved by your organisation. Only use an approved model hosted locally; a loopback connection alone cannot guarantee how a separately configured model server handles data.

## Start locally on Windows

1. Install and start Ollama using your organisation's approved process.
2. Obtain an approved local model according to the organisation's policies. Model downloads require network access. Note its installed name.
3. In PowerShell, from this `poc` directory, set the opt-in flag and start the application:

   ```powershell
   $env:BOM_LOCAL_LLM_TEST = '1'
   streamlit run configurator.py
   ```

4. Upload an approved or anonymised checklist PDF. Open **Experimental local LLM: analyse PDF text**, enter the installed local model name, and select **Analyse extracted PDF text**.
5. Compare all suggestions and quoted evidence with the actual document. The test does not apply values to the app or alter the BOM.

To disable the experiment in the current PowerShell session, run `Remove-Item Env:BOM_LOCAL_LLM_TEST` and restart Streamlit.

## Limits

- This is a text-only test. It cannot read checked boxes, scans without text or images. Printed choices may be mistaken for selections, including when an exact quote is present.
- The app uses at most the first 25,000 characters and shows a warning if the text was truncated. The request has a 120-second timeout.
- The model can return false or incomplete suggestions. Exact source matching is a basic check, not validation of a selected field. Results require human review.
- Streamlit Community Cloud runs on a different machine from a developer's laptop. `127.0.0.1` refers to the app server, so this local test will not reach Ollama on a user's laptop. A server deployment requires a separate, IT-approved design.
- The experiment is disabled by default and does not send data until the button is pressed. It does not add an LLM or Ollama as a Python dependency.
