import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const chromePort = 9222;
const baseUrl = "http://127.0.0.1:3000";
const outputDir = path.resolve("screens");
const csvPath = path.resolve("../../apps/web/public/demo-products.csv");
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function connect() {
  const target = await fetch(
    `http://127.0.0.1:${chromePort}/json/new?${encodeURIComponent(baseUrl)}`,
    { method: "PUT" },
  ).then((response) => response.json());
  const socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });
  let nextId = 1;
  const pending = new Map();
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (!message.id || !pending.has(message.id)) return;
    const { resolve, reject } = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) reject(new Error(message.error.message));
    else resolve(message.result);
  });
  return {
    send(method, params = {}) {
      const id = nextId++;
      socket.send(JSON.stringify({ id, method, params }));
      return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
    },
    close() {
      socket.close();
    },
  };
}

async function main() {
  await mkdir(outputDir, { recursive: true });
  const session = await fetch("http://127.0.0.1:8000/api/v1/demo/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role: "operator" }),
  }).then((response) => response.json());
  const cdp = await connect();
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  await cdp.send("DOM.enable");
  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width: 1920,
    height: 1080,
    deviceScaleFactor: 1,
    mobile: false,
  });

  async function navigate(route) {
    await cdp.send("Page.navigate", { url: `${baseUrl}${route}` });
    await delay(1400);
  }

  async function evaluate(expression) {
    return cdp.send("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
  }

  async function screenshot(name) {
    const result = await cdp.send("Page.captureScreenshot", {
      format: "png",
      fromSurface: true,
      captureBeyondViewport: false,
    });
    await writeFile(path.join(outputDir, `${name}.png`), Buffer.from(result.data, "base64"));
  }

  await navigate("/");
  await evaluate(
    `localStorage.setItem("fruit-agent-access-token", ${JSON.stringify(session.access_token)})`,
  );
  await navigate("/");
  await screenshot("home-session");

  await navigate("/members");
  await screenshot("members");

  await navigate("/imports");
  const document = await cdp.send("DOM.getDocument");
  const input = await cdp.send("DOM.querySelector", {
    nodeId: document.root.nodeId,
    selector: 'input[type="file"]',
  });
  await cdp.send("DOM.setFileInputFiles", {
    nodeId: input.nodeId,
    files: [csvPath],
  });
  await evaluate(
    `document.querySelector('input[type="file"]').dispatchEvent(new Event("change", { bubbles: true }))`,
  );
  await delay(300);
  await evaluate(
    `[...document.querySelectorAll("button")].find((button) => button.textContent.includes("校验并导入"))?.click()`,
  );
  await delay(1600);
  await screenshot("imports");

  await navigate("/knowledge");
  await screenshot("knowledge");

  await navigate("/approvals");
  await evaluate(
    `[...document.querySelectorAll("button")].find((button) => button.textContent.trim() === "批准")?.click()`,
  );
  await delay(350);
  await screenshot("approvals");

  await navigate("/copilot");
  await delay(1000);
  await evaluate(
    `[...document.querySelectorAll(".recent-cases button")].find((button) => button.textContent.includes("这款昭通苹果"))?.click()`,
  );
  await delay(900);
  await screenshot("copilot");
  await evaluate(`window.scrollTo({ top: 720, behavior: "instant" })`);
  await delay(300);
  await screenshot("copilot-detail");

  cdp.close();
  process.stdout.write("Captured 7 authenticated operation screens.\n");
}

await main();
