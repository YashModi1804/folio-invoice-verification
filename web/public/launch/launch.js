import { LIVE_ORIGIN, waitForWorkspace } from "./readiness.js";

const status = document.querySelector("#status");
const detail = document.querySelector("#detail");
const retry = document.querySelector("#retry");
const connection = document.querySelector(".connection");
let attempt;

async function connect() {
  attempt?.abort();
  attempt = new AbortController();
  const { signal } = attempt;
  retry.hidden = true;
  connection.classList.remove("unavailable");
  status.textContent = "Preparing your live workspace";
  detail.textContent =
    "The free demo may take about a minute to wake up. We’ll open it automatically when it’s ready.";
  const ready = await waitForWorkspace({ signal });
  if (signal.aborted) return;
  if (ready) {
    status.textContent = "Workspace ready";
    detail.textContent = "Opening Folio…";
    window.location.replace(`${LIVE_ORIGIN}/`);
    return;
  }
  connection.classList.add("unavailable");
  status.textContent = "The live workspace is taking longer than expected";
  detail.textContent =
    "You can explore all four samples now, or try connecting again. Your browser hasn’t sent any documents.";
  retry.hidden = false;
}

retry.addEventListener("click", () => void connect());
window.addEventListener("pagehide", () => attempt?.abort());
window.addEventListener("pageshow", (event) => {
  if (event.persisted) void connect();
});
void connect();
