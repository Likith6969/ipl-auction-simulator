import { api } from "../api/client.js";
import { loadSession, requireSession, updateRetentionSummary } from "../store/session-store.js";

const SLOT_LABELS = {
  1: { label: "1st Retention", cost: 18 },
  2: { label: "2nd Retention", cost: 15 },
  3: { label: "3rd Retention", cost: 8 },
};

const session = requireSession();
if (!session) {
  throw new Error("No active session");
}

const teamSummaryEl = document.getElementById("team-summary");
const statusEl = document.getElementById("status-banner");
const slotsEl = document.getElementById("retention-slots");
const playerGridEl = document.getElementById("player-grid");
const summaryPanelEl = document.getElementById("summary-panel");
const confirmBtn = document.getElementById("confirm-btn");
const aiSectionEl = document.getElementById("ai-retentions");
const aiTeamsGridEl = document.getElementById("ai-teams-grid");

let retentionView = null;
let selections = new Map();
let isConfirmed = false;

function formatCr(value) {
  const amount = Number(value);
  return Number.isFinite(amount) ? amount.toFixed(2) : "0.00";
}

function setStatus(message, type = "loading") {
  statusEl.textContent = message;
  statusEl.className = `status-banner status-banner--${type}`;
  statusEl.classList.remove("hidden");
}

function hideStatus() {
  statusEl.classList.add("hidden");
}

function getTotalCost() {
  let total = 0;
  selections.forEach((_, slot) => {
    total += SLOT_LABELS[slot].cost;
  });
  return total;
}

function getRemainingPurse() {
  const initial = Number(retentionView?.summary?.initial_purse_cr ?? 120);
  return initial - getTotalCost();
}

function renderSummary() {
  const initial = Number(retentionView?.summary?.initial_purse_cr ?? 120);
  const total = isConfirmed
    ? Number(retentionView.summary.total_retention_cost_cr)
    : getTotalCost();
  const remaining = isConfirmed
    ? Number(retentionView.summary.remaining_purse_cr)
    : getRemainingPurse();

  summaryPanelEl.innerHTML = `
    <div class="summary-card">
      <span class="summary-card__label">Starting Purse</span>
      <strong class="summary-card__value">₹${formatCr(initial)} Cr</strong>
    </div>
    <div class="summary-card">
      <span class="summary-card__label">Total Retention Cost</span>
      <strong class="summary-card__value summary-card__value--cost">₹${formatCr(total)} Cr</strong>
    </div>
    <div class="summary-card summary-card--highlight">
      <span class="summary-card__label">Remaining Purse</span>
      <strong class="summary-card__value">₹${formatCr(remaining)} Cr</strong>
    </div>
  `;

  confirmBtn.disabled = isConfirmed || selections.size !== 3;
  confirmBtn.textContent = isConfirmed
    ? "Retentions Confirmed"
    : selections.size === 3
      ? "Confirm Retentions"
      : `Select ${3 - selections.size} More Player${selections.size === 2 ? "" : "s"}`;
}

function renderSlots() {
  slotsEl.innerHTML = "";

  [1, 2, 3].forEach((slot) => {
    const meta = SLOT_LABELS[slot];
    const selected = selections.get(slot);
    const card = document.createElement("article");
    card.className = `retention-slot${selected ? " retention-slot--filled" : ""}`;
    card.innerHTML = `
      <div class="retention-slot__head">
        <span class="retention-slot__label">${meta.label}</span>
        <span class="retention-slot__cost">₹${meta.cost} Cr</span>
      </div>
      <div class="retention-slot__body">
        ${
          selected
            ? `
          <strong>${selected.name}</strong>
          <span>${selected.role}${selected.is_captain ? " · Captain" : ""}${selected.is_overseas ? " · Overseas" : ""}</span>
          ${isConfirmed ? "" : `<button type="button" class="slot-remove" data-slot="${slot}">Remove</button>`}
        `
            : `<span class="retention-slot__empty">Assign a player to this slot</span>`
        }
      </div>
    `;
    slotsEl.appendChild(card);
  });

  if (!isConfirmed) {
    slotsEl.querySelectorAll(".slot-remove").forEach((button) => {
      button.addEventListener("click", () => {
        selections.delete(Number(button.dataset.slot));
        renderAll();
      });
    });
  }
}

function renderPlayers() {
  playerGridEl.innerHTML = "";

  const selectedIds = new Set(
    [...selections.values()].map((player) => player.player_id),
  );

  retentionView.eligible_players.forEach((player) => {
    const isSelected = selectedIds.has(player.player_id);
    const button = document.createElement("button");
    button.type = "button";
    button.className = `player-card${isSelected ? " player-card--selected" : ""}`;
    button.disabled = isConfirmed;
    button.dataset.playerId = String(player.player_id);
    button.innerHTML = `
      <div class="player-card__top">
        <strong>${player.name}</strong>
        ${player.is_captain ? '<span class="player-badge player-badge--captain">C</span>' : ""}
        ${player.is_overseas ? '<span class="player-badge player-badge--overseas">OS</span>' : ""}
      </div>
      <div class="player-card__meta">
        <span>${player.role}</span>
        <span>${player.country}</span>
      </div>
      <div class="player-card__price">Base ₹${formatCr(player.base_price_cr)} Cr</div>
    `;

    if (!isConfirmed) {
      button.addEventListener("click", () => togglePlayer(player));
    }

    playerGridEl.appendChild(button);
  });
}

function togglePlayer(player) {
  for (const [slot, selected] of selections.entries()) {
    if (selected.player_id === player.player_id) {
      selections.delete(slot);
      renderAll();
      return;
    }
  }

  const nextSlot = [1, 2, 3].find((slot) => !selections.has(slot));
  if (!nextSlot) {
    setStatus("All three retention slots are filled. Remove a player to change your selection.", "error");
    return;
  }

  hideStatus();
  selections.set(nextSlot, player);
  renderAll();
}

function renderAll() {
  renderSlots();
  renderPlayers();
  renderSummary();
}

function hydrateConfirmedState() {
  if (!retentionView.is_confirmed) {
    return;
  }

  isConfirmed = true;
  selections = new Map(
    retentionView.selected_retentions.map((item) => [
      item.retention_slot,
      {
        player_id: item.player.player_id,
        name: item.player.name,
        role: item.player.role,
        is_captain: item.player.is_captain,
        is_overseas: item.player.is_overseas,
      },
    ]),
  );
}

function renderAiRetentions(allRetentions) {
  const aiTeams = allRetentions.teams.filter((team) => !team.is_user_team);
  if (!aiTeams.length) {
    aiSectionEl.classList.add("hidden");
    return;
  }

  aiTeamsGridEl.innerHTML = aiTeams
    .map(
      (team) => `
      <article class="ai-team-card">
        <div class="ai-team-card__head">
          <strong>${team.short_name}</strong>
          <span class="ai-team-card__purse">₹${formatCr(team.summary.remaining_purse_cr)} Cr left</span>
        </div>
        <ul class="ai-team-card__list">
          ${team.retentions
            .map(
              (item) => `
            <li>
              <span class="ai-team-card__slot">#${item.retention_slot}</span>
              <span>${item.player.name}${item.player.is_captain ? " (C)" : ""}</span>
              <span class="ai-team-card__cost">₹${formatCr(item.retention_cost_cr)} Cr</span>
            </li>
          `,
            )
            .join("")}
        </ul>
      </article>
    `,
    )
    .join("");

  aiSectionEl.classList.remove("hidden");
}

async function loadAiRetentions() {
  const allRetentions = await api.getAllRetentions(session.sessionId);
  if (allRetentions.all_retentions_complete) {
    renderAiRetentions(allRetentions);
  }
}

async function loadRetentionView() {
  setStatus("Loading squad players…");
  confirmBtn.disabled = true;

  try {
    retentionView = await api.getRetention(session.sessionId);
    teamSummaryEl.textContent = `Managing ${retentionView.team_name} (${retentionView.short_name})`;
    hydrateConfirmedState();
    hideStatus();
    renderAll();

    if (retentionView.is_confirmed || retentionView.phase === "AUCTION") {
      await loadAiRetentions();
    }
  } catch (error) {
    setStatus(error.message || "Failed to load retention data.", "error");
  }
}

async function confirmRetentions() {
  if (isConfirmed || selections.size !== 3) {
    return;
  }

  confirmBtn.disabled = true;
  setStatus("Saving retentions and running AI retentions for other teams…");

  const payload = [...selections.entries()]
    .sort(([slotA], [slotB]) => slotA - slotB)
    .map(([slot, player]) => ({
      player_id: player.player_id,
      slot,
    }));

  try {
    const result = await api.confirmRetention(session.sessionId, payload);
    retentionView = {
      ...retentionView,
      selected_retentions: result.retentions,
      summary: result.summary,
      is_confirmed: true,
    };
    isConfirmed = true;
    updateRetentionSummary(result.summary, { phase: result.phase });
    hideStatus();
    renderAll();

    if (result.all_retentions_complete) {
      setStatus(
        `All 10 franchises have retained 3 players. AI handled ${result.ai_teams_retained} teams. Auction phase ready.`,
        "success",
      );
      await loadAiRetentions();
    }
  } catch (error) {
    setStatus(error.message || "Failed to confirm retentions.", "error");
    confirmBtn.disabled = false;
  }
}

confirmBtn.addEventListener("click", confirmRetentions);
loadRetentionView();
