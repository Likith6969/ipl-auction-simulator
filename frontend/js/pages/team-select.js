import { api } from "../api/client.js";
import { saveSession } from "../store/session-store.js";

const gridEl = document.getElementById("team-grid");
const statusEl = document.getElementById("status-banner");
const continueBtn = document.getElementById("continue-btn");

let teams = [];
let selectedTeamId = null;

function setStatus(message, type = "loading") {
  statusEl.textContent = message;
  statusEl.className = `status-banner status-banner--${type}`;
  statusEl.classList.remove("hidden");
}

function hideStatus() {
  statusEl.classList.add("hidden");
}

function renderTeams() {
  gridEl.innerHTML = "";

  teams.forEach((team) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "team-card";
    button.dataset.team = team.short_name;
    button.dataset.teamId = String(team.team_id);
    button.innerHTML = `
      <span class="team-card__short">${team.short_name}</span>
      <span class="team-card__name">${team.team_name}</span>
    `;
    button.addEventListener("click", () => selectTeam(team.team_id, button));
    gridEl.appendChild(button);
  });
}

function selectTeam(teamId, buttonEl) {
  selectedTeamId = teamId;

  gridEl.querySelectorAll(".team-card").forEach((card) => {
    card.classList.toggle("is-selected", card === buttonEl);
  });

  const team = teams.find((t) => t.team_id === teamId);
  continueBtn.disabled = false;
  continueBtn.textContent = `Continue as ${team?.short_name ?? "Team"}`;
}

async function loadTeams() {
  setStatus("Loading IPL franchises…");
  continueBtn.disabled = true;

  try {
    teams = await api.getTeams();
    if (!teams.length) {
      setStatus("No teams found. Run database seed first.", "error");
      return;
    }
    hideStatus();
    renderTeams();
  } catch (error) {
    setStatus(error.message || "Failed to load teams.", "error");
  }
}

async function confirmSelection() {
  if (!selectedTeamId) {
    return;
  }

  continueBtn.disabled = true;
  setStatus("Creating your auction session…");

  try {
    const session = await api.createSession(selectedTeamId);
    saveSession(session);
    window.location.href = "/pages/retention.html";
  } catch (error) {
    setStatus(error.message || "Failed to save team selection.", "error");
    continueBtn.disabled = false;
  }
}

continueBtn.addEventListener("click", confirmSelection);

loadTeams();
