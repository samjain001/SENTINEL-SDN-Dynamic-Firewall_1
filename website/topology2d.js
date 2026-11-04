
/* SENTINEL 2D topology renderer.
   Keeps the window.sentinel3D API name for compatibility with app.js.
   No Three.js, WebGL, or backend changes are required. */

(() => {
  "use strict";

  const root = document.getElementById("networkScene");
  const svg = document.getElementById("networkSvg");
  const cableLayer = document.getElementById("cableLayer");
  const packetLayer = document.getElementById("packetLayer");

  if (!root || !svg || !cableLayer || !packetLayer) return;

  const fixed = {
    h1: { x: 205, y: 145, role: "server" },
    s1: { x: 500, y: 250, role: "switch" },
    h2: { x: 795, y: 145, role: "client" },
    h3: { x: 795, y: 365, role: "client" }
  };

  const extraSlots = [
    { x: 205, y: 365 },
    { x: 500, y: 85 },
    { x: 795, y: 255 },
    { x: 350, y: 365 },
    { x: 650, y: 85 },
    { x: 350, y: 85 }
  ];

  const positions = new Map(
    Object.entries(fixed).map(([name, point]) => [name, point])
  );

  function makePath(a, b, className = "network-link") {
    const midX = (a.x + b.x) / 2;
    const midY = (a.y + b.y) / 2;

    const path = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "path"
    );

    path.setAttribute(
      "d",
      `M ${a.x} ${a.y} Q ${midX} ${midY - 15} ${b.x} ${b.y}`
    );

    path.setAttribute("class", className);

    return path;
  }

  function renderLinks() {
    cableLayer.replaceChildren();

    const core = positions.get("s1");
    if (!core) return;

    for (const [name, point] of positions) {
      if (name !== "s1") {
        cableLayer.appendChild(makePath(point, core));
      }
    }
  }

  function syncDevices(list) {
    if (!Array.isArray(list)) return;

    const extras = document.getElementById("additionalDevices");
    const liveNames = new Set();
    let extraIndex = 0;

    // Preserve the fixed core network.
    positions.clear();

    Object.entries(fixed).forEach(([name, point]) => {
      positions.set(name, point);
    });

    list.forEach(device => {
      const name = String(device.name || device.id || "").trim();

      if (!name || fixed[name]) return;

      liveNames.add(name);

      const slot = extraSlots[extraIndex % extraSlots.length];
      extraIndex += 1;

      positions.set(name, {
        ...slot,
        role: String(device.role || "client").toLowerCase()
      });

      let node = extras?.querySelector(
        `[data-device="${CSS.escape(name)}"]`
      );

      if (extras && !node) {
        node = document.createElement("button");
        node.type = "button";
        node.className = "scene-device additional-device";
        node.dataset.device = name;

        node.innerHTML = `
          <span class="scene-label">
            <b></b>
            <span></span>
            <small>CONNECTED</small>
          </span>
        `;

        node.addEventListener("click", () => {
          document.querySelectorAll(".scene-device").forEach(item => {
            item.classList.remove("selected");
          });

          node.classList.add("selected");
        });

        extras.appendChild(node);
      }

      if (node) {
        node.style.left = `${slot.x / 10}%`;
        node.style.top = `${slot.y / 4.7}%`;

        node.querySelector(".scene-label b").textContent = name;

        node.querySelector(".scene-label span").textContent =
          String(device.role || "CLIENT").toUpperCase();
      }
    });

    if (extras) {
      extras.querySelectorAll(".additional-device").forEach(node => {
        if (!liveNames.has(node.dataset.device)) {
          node.remove();
        }
      });
    }

    renderLinks();
  }

  function animatePacket(deviceName, decision = "ALLOWED") {
    const start =
      positions.get(String(deviceName)) || positions.get("h2");

    const end = positions.get("s1");

    if (!start || !end) return;

    const blocked =
      String(decision).toUpperCase() === "BLOCKED";

    const color = blocked ? "#ff536d" : "#20e5a0";

    const circle = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "circle"
    );

    circle.setAttribute("r", "6");
    circle.setAttribute("fill", color);
    circle.setAttribute("class", "packet-dot");
    circle.style.color = color;

    packetLayer.appendChild(circle);

    const duration = 1250;
    const startTime = performance.now();
    const stopAt = blocked ? 0.72 : 1;

    function tick(now) {
      const raw = Math.min((now - startTime) / duration, 1);
      const t = Math.min(raw, stopAt);

      const midX = (start.x + end.x) / 2;
      const midY = (start.y + end.y) / 2 - 15;

      const x =
        (1 - t) * (1 - t) * start.x +
        2 * (1 - t) * t * midX +
        t * t * end.x;

      const y =
        (1 - t) * (1 - t) * start.y +
        2 * (1 - t) * t * midY +
        t * t * end.y;

      circle.setAttribute("cx", x);
      circle.setAttribute("cy", y);

      if (raw < 1 && !(blocked && raw >= stopAt)) {
        requestAnimationFrame(tick);
      } else {
        circle.remove();
      }
    }

    requestAnimationFrame(tick);
  }

  function resize() {
    renderLinks();
  }

  document.querySelectorAll(".scene-device").forEach(node => {
    node.addEventListener("click", () => {
      document.querySelectorAll(".scene-device").forEach(item => {
        item.classList.remove("selected");
      });

      node.classList.add("selected");
    });
  });

  window.sentinel3D = {
    syncDevices,
    animatePacket,
    resize
  };

  window.sentinel2D = window.sentinel3D;

  renderLinks();

  window.dispatchEvent(new Event("sentinel3dready"));

  console.info("SENTINEL 2D topology ready.");
})();
