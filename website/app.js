
/* =====================================================
   SENTINEL - LIVE NETWORK OPERATIONS CENTER
   Complete Application Controller
===================================================== */

const API = {
    status: "/api/status",
    controller: "/api/controller",
    stats: "/api/stats",
    traffic: "/api/traffic",
    devices: "/api/devices"
};

const REFRESH_MS = 3000;

let chart = null;
let devices = [];
let selectedDevice = null;

let lastEventsSignature = "";
let knownEventKeys = new Set();

let firstTrafficLoad = true;
let pollingStarted = false;

const $ = id => document.getElementById(id);

/* =====================================================
   GENERAL HELPERS
===================================================== */

function setText(id, value) {
    const element = $(id);
    if (element) {
        element.textContent = value ?? "--";
    }
}

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    })[char]);
}

async function api(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {})
        }
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
        throw new Error(
            data.error ||
            data.message ||
            `HTTP ${response.status}`
        );
    }

    return data;
}

function getRowValue(row, names, fallback = "--") {
    for (const name of names) {
        const value = row?.[name];

        if (
            value !== undefined &&
            value !== null &&
            value !== ""
        ) {
            return value;
        }
    }

    return fallback;
}

/* =====================================================
   EVENT HELPERS
===================================================== */

function getEventKey(row) {
    return [
        getRowValue(row, ["Timestamp", "Time", "Date"], ""),
        getRowValue(row, [
            "Source IP", "Source", "SourceIP", "Source_IP"
        ], ""),
        getRowValue(row, ["Source Port", "SourcePort"], ""),
        getRowValue(row, [
            "Destination IP",
            "Destination",
            "DestinationIP",
            "Destination_IP"
        ], ""),
        getRowValue(row, [
            "Destination Port",
            "DestinationPort"
        ], ""),
        getRowValue(row, ["Protocol"], ""),
        getRowValue(row, ["Message"], ""),
        getRowValue(row, ["Decision"], "")
    ].join("|");
}

function getDecision(row) {
    return String(
        getRowValue(row, ["Decision", "Action"], "")
    ).toUpperCase();
}

/* =====================================================
   CLOCK
===================================================== */

function updateClock() {
    const now = new Date();

    setText("clock", now.toLocaleTimeString());

    setText(
        "date",
        now.toLocaleDateString(undefined, {
            weekday: "short",
            day: "2-digit",
            month: "short",
            year: "numeric"
        })
    );
}

updateClock();
setInterval(updateClock, 1000);

/* =====================================================
   SYSTEM STATUS
===================================================== */

function setSystemStatus(lightId, textId, online, label) {
    const light = $(lightId);

    setText(textId, label);

    if (light) {
        light.classList.toggle("offline", !online);
        light.classList.remove("checking");
    }
}

async function checkBackend() {
    try {
        await api(API.status);

        setSystemStatus(
            "backendLight",
            "backendState",
            true,
            "Online"
        );
    } catch {
        setSystemStatus(
            "backendLight",
            "backendState",
            false,
            "Offline"
        );
    }
}

async function checkController() {
    try {
        const data = await api(API.controller);

        const online =
            data.online === true ||
            data.status === "online";

        setSystemStatus(
            "controllerLight",
            "controllerState",
            online,
            online ? "Online" : "Offline"
        );
    } catch {
        setSystemStatus(
            "controllerLight",
            "controllerState",
            false,
            "Offline"
        );
    }
}

/* =====================================================
   CHART
===================================================== */

function initialiseChart() {
    const canvas = $("trafficChart");

    if (!canvas || typeof Chart === "undefined") {
        return;
    }

    if (chart) {
        chart.destroy();
    }

    chart = new Chart(canvas, {
        type: "doughnut",

        data: {
            labels: ["Allowed", "Blocked"],

            datasets: [{
                data: [0, 0],

                backgroundColor: [
                    "#20dfff",
                    "#ff526d"
                ],

                borderColor: "#071629",
                borderWidth: 4,
                hoverOffset: 7
            }]
        },

        options: {
            responsive: true,
            maintainAspectRatio: false,

            cutout: "70%",

            plugins: {
                legend: {
                    display: false
                },

                tooltip: {
                    callbacks: {
                        label: context =>
                            `${context.label}: ${context.raw}`
                    }
                }
            }
        }
    });
}

/* =====================================================
   STATISTICS
===================================================== */

async function loadStats() {
    try {
        const data = await api(API.stats);

        const total = Number(
            data.total ??
            data.total_messages ??
            0
        );

        const allowed = Number(
            data.allowed ??
            data.allowed_messages ??
            0
        );

        const blocked = Number(
            data.blocked ??
            data.blocked_messages ??
            0
        );

        const tcp = Number(
            data.tcp ??
            data.tcp_messages ??
            0
        );

        setText("totalMessages", total.toLocaleString());
        setText("totalMessagesCenter", total.toLocaleString());
        setText("allowedMessages", allowed.toLocaleString());
        setText("blockedMessages", blocked.toLocaleString());
        setText("tcpMessages", tcp.toLocaleString());

        setText("chartAllowed", allowed.toLocaleString());
        setText("chartBlocked", blocked.toLocaleString());

        setText("analyticsAllowed", allowed.toLocaleString());
        setText("analyticsBlocked", blocked.toLocaleString());

        if (chart) {
            chart.data.datasets[0].data = [
                allowed,
                blocked
            ];

            chart.update("none");
        }

    } catch (error) {
        console.error("Statistics:", error);
    }
}

/* =====================================================
   DEVICE HELPERS
===================================================== */

function normaliseDevices(data) {
    if (Array.isArray(data)) {
        return data;
    }

    if (Array.isArray(data.devices)) {
        return data.devices;
    }

    return [];
}

async function fetchDevices() {
    const data = await api(API.devices);
    return normaliseDevices(data);
}

function deviceName(device) {
    return String(
        device?.name ??
        device?.id ??
        ""
    );
}

function deviceRole(device) {
    const name = deviceName(device).toLowerCase();

    const rawRole = String(
        device?.role ??
        device?.type ??
        device?.device_type ??
        ""
    ).toLowerCase();

    if (
        name === "s1" ||
        rawRole.includes("switch") ||
        rawRole.includes("ovs")
    ) {
        return "switch";
    }

    if (rawRole.includes("server")) {
        return "server";
    }

    return "client";
}

function isSwitch(device) {
    return deviceRole(device) === "switch";
}

function isServer(device) {
    return deviceRole(device) === "server";
}

function isClient(device) {
    return !isSwitch(device) && !isServer(device);
}

function findDevice(name) {
    return devices.find(
        device => deviceName(device) === name
    );
}

/* =====================================================
   DEVICE INSPECTOR
===================================================== */

function selectDevice(device) {
    if (!device) return;

    selectedDevice = device;

    document.querySelectorAll(".scene-device").forEach(element => {
        element.classList.toggle(
            "selected",
            element.dataset.device === deviceName(device)
        );
    });

    setText("detailName", deviceName(device));

    setText(
        "detailRole",
        deviceRole(device).toUpperCase()
    );

    setText(
        "detailIP",
        device.ip || "--"
    );

    setText(
        "detailStatus",
        device.status === "blocked" || device.blocked
            ? "Blocked"
            : "Online"
    );

    setText(
        "detailProtocol",
        deviceRole(device) === "switch"
            ? "OpenFlow 1.3"
            : "TCP / OpenFlow"
    );
}

/* =====================================================
   DYNAMIC DEVICE LABELS
===================================================== */

function makeAdditionalDevice(device, index) {
    const role = deviceRole(device);

    const element = document.createElement("div");

    element.className =
        `scene-device additional-device ${role}-device`;

    element.dataset.device = deviceName(device);

    element.tabIndex = 0;

    element.setAttribute("role", "button");

    element.setAttribute(
        "aria-label",
        `${role} ${deviceName(device)}`
    );

    element.innerHTML = `
        <div class="scene-label">
            <b>${escapeHTML(deviceName(device))}</b>
            <span>${escapeHTML(role.toUpperCase())}</span>
            <small>${escapeHTML(device.ip || "--")}</small>
        </div>
    `;

    element.addEventListener("click", () => {
        selectDevice(device);
    });

    element.addEventListener("keydown", event => {
        if (
            event.key === "Enter" ||
            event.key === " "
        ) {
            event.preventDefault();
            selectDevice(device);
        }
    });

    if (device.status === "blocked" || device.blocked) {
        element.classList.add("blocked-device");
    }

    return element;
}

/* =====================================================
   TOPOLOGY
===================================================== */

function renderTopology() {
    const extras = $("additionalDevices");

    if (!extras) return;

    extras.innerHTML = "";

    const fixedNames = ["s1", "h1", "h2", "h3"];

    const hosts = devices.filter(device =>
        !fixedNames.includes(deviceName(device).toLowerCase())
    );

    hosts.forEach((device, index) => {
        extras.appendChild(
            makeAdditionalDevice(device, index)
        );
    });

    const servers = devices.filter(isServer).length;

    const switches = Math.max(
        1,
        devices.filter(isSwitch).length
    );

    const clients = devices.filter(isClient).length;

    setText("deviceCount", devices.length);
    setText("serverCount", servers);
    setText("clientCount", clients);
    setText("switchCount", switches);

    ["h1", "h2", "h3", "s1"].forEach(name => {
        const live = findDevice(name);

        const element = document.querySelector(
            `.scene-device[data-device="${name}"]`
        );

        if (!element || !live) return;

        const label = element.querySelector(".scene-label");

        if (label) {
            label.innerHTML = `
                <b>${escapeHTML(name)}</b>
                <span>${escapeHTML(deviceRole(live).toUpperCase())}</span>
                <small>${escapeHTML(live.ip || "--")}</small>
            `;
        }

        element.onclick = () => selectDevice(live);

        element.onkeydown = event => {
            if (
                event.key === "Enter" ||
                event.key === " "
            ) {
                event.preventDefault();
                selectDevice(live);
            }
        };
    });

    setSystemStatus(
        "topologyLight",
        "topologyState",
        devices.length > 0,
        devices.length > 0
            ? "Running"
            : "Unavailable"
    );

    if (window.sentinel3D?.syncDevices) {
        window.sentinel3D.syncDevices(devices);
    }

    if (selectedDevice) {
        const refreshed = findDevice(
            deviceName(selectedDevice)
        );

        if (refreshed) {
            selectDevice(refreshed);
        } else {
            selectedDevice = null;
        }
    }
}

/* =====================================================
   DEVICE TABLE
===================================================== */

function renderDeviceTable() {
    const body = $("deviceTableBody");

    if (!body) return;

    if (!devices.length) {
        body.innerHTML = `
            <tr>
                <td colspan="5">No devices available.</td>
            </tr>
        `;

        return;
    }

    body.innerHTML = devices.map(device => {
        const name = deviceName(device);
        const role = deviceRole(device);

        const coreSwitch = isSwitch(device);

        const status =
            device.status === "blocked" || device.blocked
                ? "Blocked"
                : "Online";

        return `
            <tr>
                <td>${escapeHTML(name)}</td>

                <td>
                    <span class="role-tag">
                        ${escapeHTML(role.toUpperCase())}
                    </span>
                </td>

                <td>${escapeHTML(device.ip || "--")}</td>

                <td>${escapeHTML(status)}</td>

                <td>
                    ${
                        coreSwitch
                            ? "CORE"
                            : `
                                <button
                                    class="remove-button"
                                    data-name="${escapeHTML(name)}"
                                >
                                    Remove
                                </button>
                            `
                    }
                </td>
            </tr>
        `;
    }).join("");

    body.querySelectorAll(".remove-button").forEach(button => {
        button.addEventListener("click", () => {
            removeDevice(button.dataset.name);
        });
    });
}

/* =====================================================
   FEEDBACK
===================================================== */

function showFeedback(message, type = "") {
    const element = $("deviceFeedback");

    if (!element) return;

    element.textContent = message;
    element.className = `feedback ${type}`;
}

/* =====================================================
   LOAD DEVICES
===================================================== */

async function loadDevices() {
    try {
        devices = await fetchDevices();

        renderTopology();
        renderDeviceTable();

        const status = $("deviceApiStatus");

        if (status) {
            status.textContent = "DEVICE API CONNECTED";
            status.style.color = "var(--green)";
        }

    } catch (error) {
        console.error("Device API:", error);

        const status = $("deviceApiStatus");

        if (status) {
            status.textContent = "DEVICE API OFFLINE";
            status.style.color = "var(--red)";
        }

        showFeedback(
            "Cannot load devices. Check Flask and the Mininet topology manager.",
            "error"
        );
    }
}

/* =====================================================
   ADD DEVICE
===================================================== */

async function addDevice(role) {
    const buttons = [
        $("addServerBtn"),
        $("addClientBtn")
    ];

    buttons.forEach(button => {
        if (button) button.disabled = true;
    });

    showFeedback(`Adding ${role}...`);

    try {
        const result = await api(API.devices, {
            method: "POST",

            body: JSON.stringify({
                role
            })
        });

        await loadDevices();

        const name =
            result.name ||
            result.device?.name ||
            "New device";

        showFeedback(
            `${role} ${name} added to Mininet.`,
            "success"
        );

    } catch (error) {
        showFeedback(
            `Could not add device: ${error.message}`,
            "error"
        );

    } finally {
        buttons.forEach(button => {
            if (button) button.disabled = false;
        });
    }
}

/* =====================================================
   REMOVE DEVICE
===================================================== */

async function removeDevice(name) {
    if (!name) return;

    const device = findDevice(name);

    if (device && isSwitch(device)) {
        showFeedback(
            "The core switch cannot be removed from this dashboard.",
            "error"
        );

        return;
    }

    showFeedback(`Removing ${name}...`);

    try {
        await api(
            `${API.devices}/${encodeURIComponent(name)}`,
            {
                method: "DELETE"
            }
        );

        if (
            selectedDevice &&
            deviceName(selectedDevice) === name
        ) {
            selectedDevice = null;

            setText("detailName", "Select a device");
            setText("detailRole", "--");
            setText("detailIP", "--");
            setText("detailStatus", "--");
            setText("detailProtocol", "--");
        }

        await loadDevices();

        showFeedback(
            `${name} removed from Mininet.`,
            "success"
        );

    } catch (error) {
        showFeedback(
            `Could not remove ${name}: ${error.message}`,
            "error"
        );
    }
}

/* =====================================================
   EVENT SOURCE DEVICE
===================================================== */

function findSourceDevice(row) {
    const sourceIP = String(
        getRowValue(row, [
            "Source IP",
            "Source",
            "SourceIP",
            "Source_IP"
        ], "")
    );

    const byIP = devices.find(
        device => String(device.ip || "") === sourceIP
    );

    if (byIP) {
        return deviceName(byIP);
    }

    const message = String(
        getRowValue(row, ["Message"], "")
    ).toLowerCase();

    for (const device of devices) {
        const name = deviceName(device).toLowerCase();

        if (name && message.includes(name)) {
            return deviceName(device);
        }
    }

    return "h2";
}

/* =====================================================
   NEW EVENT ANIMATION
===================================================== */

function animateNewEvent(row) {
    if (!window.sentinel3D?.animatePacket) {
        return;
    }

    const decision = getDecision(row);

    if (
        decision !== "ALLOWED" &&
        decision !== "BLOCKED"
    ) {
        return;
    }

    window.sentinel3D.animatePacket(
        findSourceDevice(row),
        decision
    );
}

/* =====================================================
   SECURITY EVENT DISPLAY
===================================================== */

function renderEvents(rows) {
    const list = $("eventList");

    if (!list) return;

    if (!rows.length) {
        list.innerHTML = `
            <p class="empty-message">
                No security events recorded yet.
            </p>
        `;

        return;
    }

    list.innerHTML = [...rows].reverse().slice(0, 12).map(row => {
        const decision = getDecision(row);
        const blocked = decision === "BLOCKED";

        const source = escapeHTML(
            getRowValue(row, [
                "Source IP",
                "Source",
                "SourceIP",
                "Source_IP"
            ])
        );

        const destination = escapeHTML(
            getRowValue(row, [
                "Destination IP",
                "Destination",
                "DestinationIP",
                "Destination_IP"
            ])
        );

        const protocol = escapeHTML(
            getRowValue(row, ["Protocol"], "TCP")
        );

        const timestamp = escapeHTML(
            getRowValue(row, [
                "Timestamp",
                "Time",
                "Date"
            ])
        );

        return `
            <div class="event-row ${blocked ? "blocked" : "allowed"}">

                <span class="decision">
                    ${blocked ? "✕ Blocked" : "✓ Allowed"}
                </span>

                <span class="route">
                    ${source} → ${destination} (${protocol})
                </span>

                <time>${timestamp}</time>

            </div>
        `;
    }).join("");
}

/* =====================================================
   LOAD TRAFFIC
===================================================== */

async function loadTraffic() {
    try {
        const data = await api(API.traffic);

        const rows = Array.isArray(data.traffic)
            ? data.traffic
            : [];

        const signature = JSON.stringify(rows);

        if (signature === lastEventsSignature) {
            return;
        }

        lastEventsSignature = signature;

        renderEvents(rows);

        const currentKeys = new Set(
            rows.map(getEventKey)
        );

        if (!firstTrafficLoad) {
            rows.forEach(row => {
                const key = getEventKey(row);

                if (!knownEventKeys.has(key)) {
                    animateNewEvent(row);
                }
            });
        }

        knownEventKeys = currentKeys;
        firstTrafficLoad = false;

    } catch (error) {
        console.error("Traffic events:", error);
    }
}

/* =====================================================
   NAVIGATION
===================================================== */

function initialiseNavigation() {
    document.querySelectorAll(".nav-item").forEach(link => {
        link.addEventListener("click", () => {
            document.querySelectorAll(".nav-item").forEach(item => {
                item.classList.remove("active");
            });

            link.classList.add("active");
        });
    });
}

/* =====================================================
   STARTUP
===================================================== */

async function initialiseDashboard() {
    if (pollingStarted) return;

    pollingStarted = true;

    initialiseChart();
    initialiseNavigation();

    $("addServerBtn")?.addEventListener("click", () => {
        addDevice("server");
    });

    $("addClientBtn")?.addEventListener("click", () => {
        addDevice("client");
    });

    $("refreshDevicesBtn")?.addEventListener("click", () => {
        loadDevices();
    });

    await Promise.all([
        checkBackend(),
        checkController(),
        loadStats(),
        loadTraffic(),
        loadDevices()
    ]);

    setInterval(() => {
        checkBackend();
        checkController();
        loadStats();
        loadTraffic();
        loadDevices();
    }, REFRESH_MS);
}

/* =====================================================
   DOM READY
===================================================== */

document.addEventListener(
    "DOMContentLoaded",
    initialiseDashboard
);
