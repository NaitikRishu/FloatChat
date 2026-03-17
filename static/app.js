const state = {
  summary: null,
  map: null,
  health: null,
  selectedPoint: null,
  latestResult: null,
  updateFocusMarker: null,
};

const CHART_COLORS = ["#66d9ff", "#ffb703", "#2ec4b6", "#ff6b6b", "#8ecae6"];

function numberFormat(value) {
  return new Intl.NumberFormat("en-US").format(value);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function setChatStatus(message, busy = false) {
  const node = document.getElementById("chatStatus");
  node.textContent = message;
  node.classList.toggle("busy", busy);
}

function setSubmitting(isSubmitting) {
  const button = document.querySelector(".primary-btn");
  const input = document.getElementById("chatInput");
  button.disabled = isSubmitting;
  input.disabled = isSubmitting;
  setChatStatus(isSubmitting ? "Querying..." : "Ready", isSubmitting);
}

function addChatBubble(role, text) {
  const log = document.getElementById("chatLog");
  const bubble = document.createElement("div");
  const stamp = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const roleLabel = role === "user" ? "You" : "Assistant";
  bubble.className = `chat-bubble ${role}`;
  bubble.innerHTML = `
    <div class="chat-bubble-meta">
      <span>${escapeHtml(roleLabel)}</span>
      <span>${escapeHtml(stamp)}</span>
    </div>
    <div class="chat-bubble-body">
      <p>${escapeHtml(text)}</p>
    </div>
  `;
  log.appendChild(bubble);
  log.scrollTop = log.scrollHeight;
}

function projection(lat, lon) {
  const x = ((lon - 40) / 75) * 1000;
  const y = ((35 - lat) / 80) * 560;
  return { x, y };
}

function renderHero(summary) {
  const hero = document.getElementById("heroStats");
  const cards = [
    ["Floats tracked", numberFormat(summary.counts.floats)],
    ["Profiles indexed", numberFormat(summary.counts.profiles)],
    ["Measurement rows", numberFormat(summary.counts.samples)],
    ["Avg surface temp", `${summary.avg_temp} C`],
  ];
  hero.innerHTML = cards
    .map(
      ([label, value]) => `
        <article class="stat-card">
          <div class="stat-label">${escapeHtml(label)}</div>
          <div class="stat-value">${escapeHtml(value)}</div>
        </article>
      `
    )
    .join("");

  document.getElementById("coverageBadge").textContent =
    `${summary.regions.length} sub-basins • ${numberFormat(summary.counts.bgc_profiles)} BGC profiles`;
  document.getElementById("latestCatalogDate").textContent = summary.latest_date;

  const regionGrid = document.getElementById("regionGrid");
  regionGrid.innerHTML = summary.regions
    .map(
      (region) => `
        <article class="region-card">
          <h4>${escapeHtml(region.region)}</h4>
          <div class="region-meta">${numberFormat(region.profiles)} profiles</div>
          <div class="region-meta">Mean surface temperature: ${region.avg_temp} C</div>
        </article>
      `
    )
    .join("");
}

function renderHealth(health) {
  state.health = health;
  const pill = document.getElementById("aiModePill");
  const llm = health?.llm;
  if (llm?.enabled) {
    const providerLabel =
      llm.provider === "huggingface"
        ? "Hugging Face"
        : llm.provider === "ollama"
          ? "Ollama"
          : llm.provider === "openai"
            ? "OpenAI"
            : llm.provider;
    pill.textContent = `${providerLabel} configured • ${llm.model}`;
    pill.classList.add("live");
    pill.classList.remove("fallback");
    setChatStatus(`${providerLabel} ready`);
    return;
  }
  pill.textContent = "Local fallback mode";
  pill.classList.remove("live");
  pill.classList.add("fallback");
  setChatStatus("Local fallback");
}

function renderRecentProfiles(mapData) {
  const target = document.getElementById("recentProfiles");
  target.innerHTML = mapData.recent_profiles
    .slice(0, 8)
    .map(
      (profile) => `
        <article class="profile-feed-item">
          <div>
            <p class="feed-title"><strong>${escapeHtml(profile.wmo)}</strong> • ${escapeHtml(profile.region)}</p>
            <div class="profile-feed-meta">${escapeHtml(profile.profile_code)} • ${escapeHtml(profile.observed_at.slice(0, 10))}</div>
            <div class="profile-feed-meta">${profile.latitude.toFixed(2)}, ${profile.longitude.toFixed(2)}</div>
          </div>
          <button class="feed-badge" data-lat="${profile.latitude}" data-lon="${profile.longitude}" data-label="${escapeHtml(profile.wmo)} • ${escapeHtml(profile.region)}">
            Focus point
          </button>
        </article>
      `
    )
    .join("");

  target.querySelectorAll(".feed-badge").forEach((button) => {
    button.addEventListener("click", () => {
      setSelectedPoint(Number(button.dataset.lat), Number(button.dataset.lon), button.dataset.label || "Recent profile");
    });
  });
}

function renderMap(mapData) {
  const svg = document.getElementById("oceanMap");
  svg.innerHTML = "";

  const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
  defs.innerHTML = `
    <linearGradient id="oceanGradient" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#0a2235" />
      <stop offset="100%" stop-color="#05111b" />
    </linearGradient>
    <filter id="glow">
      <feGaussianBlur stdDeviation="4" result="blur"></feGaussianBlur>
      <feMerge>
        <feMergeNode in="blur"></feMergeNode>
        <feMergeNode in="SourceGraphic"></feMergeNode>
      </feMerge>
    </filter>
  `;
  svg.appendChild(defs);

  const bg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  bg.setAttribute("x", "0");
  bg.setAttribute("y", "0");
  bg.setAttribute("width", "1000");
  bg.setAttribute("height", "560");
  bg.setAttribute("fill", "url(#oceanGradient)");
  bg.setAttribute("rx", "28");
  svg.appendChild(bg);

  for (let lat = -30; lat <= 30; lat += 10) {
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    const y = projection(lat, 40).y;
    line.setAttribute("x1", "40");
    line.setAttribute("x2", "960");
    line.setAttribute("y1", y);
    line.setAttribute("y2", y);
    line.setAttribute("stroke", "#8ecae6");
    line.setAttribute("opacity", "0.18");
    svg.appendChild(line);
  }
  for (let lon = 45; lon <= 110; lon += 10) {
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    const x = projection(0, lon).x;
    line.setAttribute("x1", x);
    line.setAttribute("x2", x);
    line.setAttribute("y1", "30");
    line.setAttribute("y2", "530");
    line.setAttribute("stroke", "#8ecae6");
    line.setAttribute("opacity", "0.18");
    svg.appendChild(line);
  }

  const land = document.createElementNS("http://www.w3.org/2000/svg", "path");
  land.setAttribute(
    "d",
    "M0,20 L220,20 L270,120 L320,160 L370,200 L410,245 L470,260 L560,242 L645,190 L690,140 L760,120 L850,120 L850,70 L1000,70 L1000,0 L0,0 Z M0,560 L0,420 L85,410 L145,360 L215,330 L245,295 L280,330 L250,420 L170,465 L90,520 Z"
  );
  land.setAttribute("fill", "rgba(206, 184, 152, 0.15)");
  land.setAttribute("stroke", "rgba(206, 184, 152, 0.16)");
  land.setAttribute("stroke-width", "2");
  svg.appendChild(land);

  const trailGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
  const focusGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
  svg.appendChild(trailGroup);
  svg.appendChild(focusGroup);

  mapData.recent_profiles.slice(0, 12).forEach((item, index) => {
    const { x, y } = projection(item.latitude, item.longitude);
    const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    dot.setAttribute("cx", x);
    dot.setAttribute("cy", y);
    dot.setAttribute("r", String(Math.max(2, 6 - index * 0.22)));
    dot.setAttribute("fill", "#2ec4b6");
    dot.setAttribute("opacity", String(Math.max(0.18, 0.72 - index * 0.05)));
    trailGroup.appendChild(dot);
  });

  mapData.floats.forEach((item) => {
    const { x, y } = projection(item.latitude, item.longitude);
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", x);
    circle.setAttribute("cy", y);
    circle.setAttribute("r", item.is_bgc ? "8" : "6");
    circle.setAttribute("fill", item.is_bgc ? "#ffb703" : "#66d9ff");
    circle.setAttribute("stroke", "#03101a");
    circle.setAttribute("stroke-width", "2");
    circle.setAttribute("filter", "url(#glow)");
    circle.style.cursor = "pointer";
    circle.addEventListener("click", (event) => {
      event.stopPropagation();
      setSelectedPoint(item.latitude, item.longitude, `${item.wmo} • ${item.region}`);
    });
    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent = `${item.wmo} • ${item.region} • ${item.is_bgc ? "BGC" : "Core"}`;
    circle.appendChild(title);
    svg.appendChild(circle);
  });

  const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
  label.setAttribute("x", "48");
  label.setAttribute("y", "58");
  label.setAttribute("fill", "#dcecf7");
  label.setAttribute("font-size", "22");
  label.setAttribute("font-family", "Gill Sans, Trebuchet MS, sans-serif");
  label.textContent = "Indian Ocean focus domain";
  svg.appendChild(label);

  svg.addEventListener("click", (event) => {
    const rect = svg.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * 1000;
    const y = ((event.clientY - rect.top) / rect.height) * 560;
    const lon = ((x / 1000) * 75) + 40;
    const lat = 35 - ((y / 560) * 80);
    setSelectedPoint(lat, lon, "Custom focus point");
  });

  function updateFocusMarker() {
    focusGroup.innerHTML = "";
    if (!state.selectedPoint) return;
    const { lat, lon } = state.selectedPoint;
    const { x, y } = projection(lat, lon);
    const ring = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    ring.setAttribute("cx", x);
    ring.setAttribute("cy", y);
    ring.setAttribute("r", "14");
    ring.setAttribute("fill", "none");
    ring.setAttribute("stroke", "#2ec4b6");
    ring.setAttribute("stroke-width", "3");
    focusGroup.appendChild(ring);

    const pulse = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    pulse.setAttribute("cx", x);
    pulse.setAttribute("cy", y);
    pulse.setAttribute("r", "5");
    pulse.setAttribute("fill", "#2ec4b6");
    focusGroup.appendChild(pulse);
  }

  state.updateFocusMarker = updateFocusMarker;
  updateFocusMarker();
}

function setSelectedPoint(lat, lon, label) {
  state.selectedPoint = { lat, lon, label };
  document.getElementById("selectionReadout").textContent = `${label}: ${lat.toFixed(2)}, ${lon.toFixed(2)}`;
  if (state.updateFocusMarker) {
    state.updateFocusMarker();
  }
}

function renderRetrieval(items) {
  const target = document.getElementById("retrievalList");
  if (!items || !items.length) {
    target.innerHTML = `<div class="empty-state">Retrieval context will appear here after a query.</div>`;
    return;
  }
  target.innerHTML = items
    .map(
      (item) => `
        <article class="retrieval-item">
          <span class="retrieval-pill">${escapeHtml(item.kind)}</span>
          <h4>${escapeHtml(item.title)}</h4>
          <div class="retrieval-score">Similarity score: ${item.score}</div>
          <p>${escapeHtml(item.content)}</p>
        </article>
      `
    )
    .join("");
}

function renderTrace(result) {
  const target = document.getElementById("traceStrip");
  const modeLabel = {
    profiles: "Depth profile analysis",
    bgc_compare: "BGC comparison mode",
    nearest_floats: "Proximity search",
    trajectory: "Trajectory mode",
    summary: "Summary analytics",
  }[result.kind] || "Analytics mode";

  target.innerHTML = `
    <div class="trace-card">
      <span class="trace-label">Intent</span>
      <strong>${escapeHtml(result.intent || "unknown")}</strong>
    </div>
    <div class="trace-card">
      <span class="trace-label">Parameter</span>
      <strong>${escapeHtml(result.parameter || "n/a")}</strong>
    </div>
    <div class="trace-card">
      <span class="trace-label">Mode</span>
      <strong>${escapeHtml(modeLabel)} • ${escapeHtml(result.llm?.answer_source || "local")}</strong>
    </div>
  `;
}

function buildInsights(result) {
  if (result.kind === "nearest_floats" && result.rows?.length) {
    return [
      {
        title: "Closest match",
        body: `Float ${result.rows[0].wmo} is the nearest platform at ${result.rows[0].distance_km} km from the selected point.`,
      },
      {
        title: "Basin spread",
        body: `${result.rows.length} nearby candidates were ranked, making it easy to pick a float for targeted investigation.`,
      },
      {
        title: "Operational value",
        body: "This flow is useful for mission planning, local comparisons, or identifying the best float near a coastal event.",
      },
    ];
  }

  if (result.kind === "bgc_compare" && result.series?.length) {
    const oxygenValues = result.series.map((row) => row.oxygen).filter((value) => value != null);
    const chlorophyllValues = result.series.map((row) => row.chlorophyll).filter((value) => value != null);
    const oxygenMin = Math.min(...oxygenValues);
    const oxygenMax = Math.max(...oxygenValues);
    const chlorophyllMax = Math.max(...chlorophyllValues);
    return [
      {
        title: "Oxygen range",
        body: `Surface oxygen varies from ${oxygenMin.toFixed(1)} to ${oxygenMax.toFixed(1)} across the selected monthly window.`,
      },
      {
        title: "Biology signal",
        body: `Peak chlorophyll reaches ${chlorophyllMax.toFixed(3)}, giving a quick read on biologically active periods.`,
      },
      {
        title: "Interpretation",
        body: "Use this panel to narrate seasonal biogeochemical swings rather than reading raw tables alone.",
      },
    ];
  }

  if (result.kind === "profiles" && result.profiles?.length) {
    const first = result.profiles[0];
    const deepest = Math.max(...first.series.map((point) => point.depth_m));
    const surface = first.series[0];
    return [
      {
        title: "Profile depth",
        body: `The previewed casts extend to ${deepest} m, enough to show upper-ocean structure and deeper gradients.`,
      },
      {
        title: "Surface signal",
        body: `One representative surface value is ${surface.value.toFixed(2)} for the selected parameter.`,
      },
      {
        title: "Story angle",
        body: "Overlayed curves make differences across floats much faster to read than line-by-line measurement tables.",
      },
    ];
  }

  if (result.kind === "summary" && result.stats) {
    return [
      {
        title: "Coverage matched",
        body: `${result.stats.profiles} profiles across ${result.stats.floats} floats matched the current request window.`,
      },
      {
        title: "Surface state",
        body: `Average surface temperature is ${result.stats.avg_temp} C with salinity at ${result.stats.avg_salinity} PSU.`,
      },
      {
        title: "Next move",
        body: "Try narrowing by region or time to turn this basin summary into a targeted comparison.",
      },
    ];
  }

  return [
    {
      title: "Query ready",
      body: "Ask for a parameter, region, and time window to generate tailored insights.",
    },
  ];
}

function renderInsights(result) {
  const target = document.getElementById("insightGrid");
  const insights = buildInsights(result);
  target.innerHTML = insights
    .map(
      (item) => `
        <article class="insight-card">
          <h4>${escapeHtml(item.title)}</h4>
          <p>${escapeHtml(item.body)}</p>
        </article>
      `
    )
    .join("");
}

function renderTable(result) {
  const table = document.getElementById("resultTable");
  table.innerHTML = "";

  if (result.kind === "nearest_floats") {
    table.innerHTML = `
      <thead>
        <tr>
          <th>WMO</th>
          <th>Region</th>
          <th>Distance (km)</th>
          <th>Latitude</th>
          <th>Longitude</th>
        </tr>
      </thead>
      <tbody>
        ${result.rows
          .map(
            (row) => `
              <tr>
                <td>${escapeHtml(row.wmo)}</td>
                <td>${escapeHtml(row.region)}</td>
                <td>${row.distance_km}</td>
                <td>${row.latitude.toFixed(2)}</td>
                <td>${row.longitude.toFixed(2)}</td>
              </tr>
            `
          )
          .join("")}
      </tbody>
    `;
    return;
  }

  if (result.kind === "bgc_compare") {
    table.innerHTML = `
      <thead>
        <tr>
          <th>Month</th>
          <th>Oxygen</th>
          <th>Chlorophyll</th>
          <th>Nitrate</th>
          <th>Backscatter</th>
        </tr>
      </thead>
      <tbody>
        ${result.series
          .map(
            (row) => `
              <tr>
                <td>${escapeHtml(row.month)}</td>
                <td>${row.oxygen ?? "NA"}</td>
                <td>${row.chlorophyll ?? "NA"}</td>
                <td>${row.nitrate ?? "NA"}</td>
                <td>${row.backscatter ?? "NA"}</td>
              </tr>
            `
          )
          .join("")}
      </tbody>
    `;
    return;
  }

  if (result.kind === "profiles") {
    table.innerHTML = `
      <thead>
        <tr>
          <th>Profile</th>
          <th>Float</th>
          <th>Region</th>
          <th>Observed</th>
          <th>Location</th>
        </tr>
      </thead>
      <tbody>
        ${result.profiles
          .map(
            (row) => `
              <tr>
                <td>${escapeHtml(row.profile_code)}</td>
                <td>${escapeHtml(row.wmo)}</td>
                <td>${escapeHtml(row.region)}</td>
                <td>${escapeHtml(row.observed_at.slice(0, 10))}</td>
                <td>${row.latitude.toFixed(2)}, ${row.longitude.toFixed(2)}</td>
              </tr>
            `
          )
          .join("")}
      </tbody>
    `;
    return;
  }

  if (result.kind === "summary" && result.stats) {
    table.innerHTML = `
      <thead>
        <tr>
          <th>Profiles</th>
          <th>Floats</th>
          <th>Avg surface temperature</th>
          <th>Avg surface salinity</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>${result.stats.profiles}</td>
          <td>${result.stats.floats}</td>
          <td>${result.stats.avg_temp}</td>
          <td>${result.stats.avg_salinity}</td>
        </tr>
      </tbody>
    `;
    return;
  }

  table.innerHTML = `<tbody><tr><td>No tabular preview available for this query yet.</td></tr></tbody>`;
}

function drawAxes(svg, width, height, margin, xLabel, yLabel) {
  const axis = document.createElementNS("http://www.w3.org/2000/svg", "g");
  axis.innerHTML = `
    <line x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}" stroke="rgba(226, 244, 255, 0.35)" />
    <line x1="${margin.left}" y1="${margin.top}" x2="${margin.left}" y2="${height - margin.bottom}" stroke="rgba(226, 244, 255, 0.35)" />
    <text x="${width - margin.right}" y="${height - 18}" fill="#d7ebf7" text-anchor="end" font-size="14">${escapeHtml(xLabel)}</text>
    <text x="18" y="${margin.top}" fill="#d7ebf7" font-size="14">${escapeHtml(yLabel)}</text>
  `;
  svg.appendChild(axis);
}

function renderProfileChart(result) {
  const svg = document.getElementById("profileChart");
  svg.innerHTML = "";
  const width = 1000;
  const height = 420;
  const margin = { top: 36, right: 36, bottom: 44, left: 78 };

  const bg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  bg.setAttribute("x", "0");
  bg.setAttribute("y", "0");
  bg.setAttribute("width", width);
  bg.setAttribute("height", height);
  bg.setAttribute("fill", "rgba(4, 15, 26, 0.98)");
  svg.appendChild(bg);

  if (result.kind === "profiles" && result.profiles.length) {
    drawAxes(svg, width, height, margin, `${result.parameter} (${result.unit})`, "Depth (m)");
    let minX = Infinity;
    let maxX = -Infinity;
    let maxDepth = 0;

    result.profiles.forEach((profile) => {
      profile.series.forEach((point) => {
        minX = Math.min(minX, point.value);
        maxX = Math.max(maxX, point.value);
        maxDepth = Math.max(maxDepth, point.depth_m);
      });
    });

    const xScale = (value) =>
      margin.left + ((value - minX) / Math.max(maxX - minX, 0.001)) * (width - margin.left - margin.right);
    const yScale = (depth) =>
      margin.top + (depth / Math.max(maxDepth, 1)) * (height - margin.top - margin.bottom);

    result.profiles.forEach((profile, index) => {
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      const d = profile.series
        .map((point, pointIndex) => `${pointIndex === 0 ? "M" : "L"} ${xScale(point.value)} ${yScale(point.depth_m)}`)
        .join(" ");
      path.setAttribute("d", d);
      path.setAttribute("fill", "none");
      path.setAttribute("stroke", CHART_COLORS[index % CHART_COLORS.length]);
      path.setAttribute("stroke-width", "3");
      path.setAttribute("stroke-linecap", "round");
      svg.appendChild(path);

      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      const lastPoint = profile.series[profile.series.length - 1];
      label.setAttribute("x", xScale(lastPoint.value) + 8);
      label.setAttribute("y", yScale(lastPoint.depth_m));
      label.setAttribute("fill", CHART_COLORS[index % CHART_COLORS.length]);
      label.setAttribute("font-size", "13");
      label.textContent = profile.wmo;
      svg.appendChild(label);
    });
    return;
  }

  if (result.kind === "bgc_compare" && result.series.length) {
    drawAxes(svg, width, height, margin, "Monthly bins", "Normalized indicator");
    const keys = ["oxygen", "chlorophyll", "nitrate"];
    const seriesCount = result.series.length;
    const xScale = (index) =>
      margin.left + (index / Math.max(seriesCount - 1, 1)) * (width - margin.left - margin.right);
    const valueRange = {};

    keys.forEach((key) => {
      const values = result.series.map((item) => item[key]).filter((item) => item != null);
      valueRange[key] = { min: Math.min(...values), max: Math.max(...values) };
    });

    keys.forEach((key, keyIndex) => {
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      const d = result.series
        .map((point, index) => {
          const { min, max } = valueRange[key];
          const normalized = (point[key] - min) / Math.max(max - min, 0.001);
          const x = xScale(index);
          const y = height - margin.bottom - normalized * (height - margin.top - margin.bottom);
          return `${index === 0 ? "M" : "L"} ${x} ${y}`;
        })
        .join(" ");
      path.setAttribute("d", d);
      path.setAttribute("fill", "none");
      path.setAttribute("stroke", CHART_COLORS[keyIndex]);
      path.setAttribute("stroke-width", "3");
      svg.appendChild(path);

      const keyLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
      keyLabel.setAttribute("x", width - margin.right - 160);
      keyLabel.setAttribute("y", margin.top + 22 * keyIndex);
      keyLabel.setAttribute("fill", CHART_COLORS[keyIndex]);
      keyLabel.textContent = key;
      svg.appendChild(keyLabel);
    });

    result.series.forEach((point, index) => {
      const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
      text.setAttribute("x", xScale(index));
      text.setAttribute("y", height - 18);
      text.setAttribute("fill", "#9ab7c8");
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("font-size", "12");
      text.textContent = point.month;
      svg.appendChild(text);
    });
    return;
  }

  if (result.kind === "nearest_floats" && result.rows.length) {
    drawAxes(svg, width, height, margin, "Float rank", "Distance (km)");
    const maxDistance = Math.max(...result.rows.map((row) => row.distance_km));
    const barWidth = 120;

    result.rows.forEach((row, index) => {
      const x = margin.left + index * 150;
      const barHeight = (row.distance_km / maxDistance) * (height - margin.top - margin.bottom);
      const y = height - margin.bottom - barHeight;
      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("x", x);
      rect.setAttribute("y", y);
      rect.setAttribute("width", barWidth);
      rect.setAttribute("height", barHeight);
      rect.setAttribute("rx", "18");
      rect.setAttribute("fill", CHART_COLORS[index % CHART_COLORS.length]);
      svg.appendChild(rect);

      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("x", x + barWidth / 2);
      label.setAttribute("y", y - 8);
      label.setAttribute("text-anchor", "middle");
      label.setAttribute("fill", "#eef7fb");
      label.textContent = `${row.wmo} • ${row.distance_km} km`;
      svg.appendChild(label);
    });
    return;
  }

  const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
  text.setAttribute("x", "500");
  text.setAttribute("y", "210");
  text.setAttribute("text-anchor", "middle");
  text.setAttribute("fill", "#9ab7c8");
  text.setAttribute("font-size", "20");
  text.textContent = "Your next query will render an interactive preview here.";
  svg.appendChild(text);
}

function renderResult(result) {
  state.latestResult = result;
  document.getElementById("resultTitle").textContent = result.title;
  document.getElementById("sqlBox").textContent = result.sql || "No SQL preview";
  document.getElementById("resultSummary").textContent = result.summary || result.answer;
  renderRetrieval(result.retrieval);
  renderTrace(result);
  renderInsights(result);
  renderTable(result);
  renderProfileChart(result);
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function primeLoadingStates() {
  document.getElementById("recentProfiles").innerHTML = `
    <div class="empty-state skeleton" style="height: 92px;"></div>
    <div class="empty-state skeleton" style="height: 92px;"></div>
  `;
}

async function boot() {
  primeLoadingStates();
  const [health, summary, mapData] = await Promise.all([
    fetchJson("/api/health"),
    fetchJson("/api/summary"),
    fetchJson("/api/map"),
  ]);
  renderHealth(health);
  state.summary = summary;
  state.map = mapData;
  renderHero(summary);
  renderMap(mapData);
  renderRecentProfiles(mapData);
  renderRetrieval([]);
  renderProfileChart({ kind: "empty" });

  addChatBubble(
    "assistant",
    "Ask me about salinity structure, BGC trends, float trajectories, or the nearest float to any point in the basin."
  );
}

async function submitChat(message) {
  addChatBubble("user", message);
  const body = { message };
  if (state.selectedPoint) {
    body.lat = state.selectedPoint.lat;
    body.lon = state.selectedPoint.lon;
  }
  setSubmitting(true);
  try {
    const result = await fetchJson("/api/chat", {
      method: "POST",
      body: JSON.stringify(body),
    });
    addChatBubble("assistant", result.answer);
    renderResult(result);
  } finally {
    setSubmitting(false);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  boot().catch((error) => {
    addChatBubble("assistant", `Startup failed: ${error.message}`);
  });

  document.getElementById("chatForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = document.getElementById("chatInput");
    const message = input.value.trim();
    if (!message) return;
    input.value = "";
    try {
      await submitChat(message);
    } catch (error) {
      addChatBubble("assistant", `Request failed: ${error.message}`);
    }
  });

  document.querySelectorAll(".prompt-chip").forEach((button) => {
    button.addEventListener("click", async () => {
      const prompt = button.dataset.prompt;
      if (!prompt) return;
      try {
        await submitChat(prompt);
      } catch (error) {
        addChatBubble("assistant", `Request failed: ${error.message}`);
      }
    });
  });
});
