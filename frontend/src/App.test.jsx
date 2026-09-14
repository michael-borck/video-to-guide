import React from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App.jsx";

const makeGuide = (title) => ({
  title,
  sections: [{ id: "section", title, steps: [{ id: "step", timestamp: 0,
    frame: "frames/source.png", instruction: `${title} instruction`,
    suggestions: ["Suggested instruction"], annotations: [] }] }],
});
const json = (data, status = 200) => new Response(JSON.stringify(data), { status });
let requests;
let override;

beforeEach(() => {
  requests = [];
  override = () => undefined;
  vi.stubGlobal("fetch", vi.fn((url, options = {}) => {
    requests.push({ url, options });
    const custom = override(url, options);
    if (custom !== undefined) return custom;
    if (url === "/api/projects") return Promise.resolve(json(["alpha", "beta"]));
    if (options.method === "PUT") return Promise.resolve(json(JSON.parse(options.body)));
    if (url.endsWith("/guide")) return Promise.resolve(json(makeGuide(url.includes("alpha") ? "alpha" : "beta")));
    if (url.endsWith("/frames")) return Promise.resolve(json({ frames: [{ file: "source.png", timestamp: 0 }] }));
    if (url.endsWith("/export")) return Promise.resolve(json({ html: "guide.html", pdf: "guide.pdf" }));
    throw new Error(`Unexpected request: ${url}`);
  }));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function openProject(user, name = "alpha") {
  await screen.findByRole("option", { name });
  await user.selectOptions(screen.getByRole("combobox", { name: "Project" }), name);
  await screen.findByDisplayValue(`${name} instruction`);
}

it("clears the previous editor while the next project loads", async () => {
  let finishBeta;
  override = (url) => url === "/api/projects/beta/guide"
    ? new Promise((resolve) => { finishBeta = resolve; }) : undefined;
  const user = userEvent.setup();
  render(<App />);
  await openProject(user);
  await user.selectOptions(screen.getByRole("combobox", { name: "Project" }), "beta");
  await screen.findByText("Loading guide…");
  expect(screen.queryByDisplayValue("alpha instruction")).toBeNull();
  expect(screen.queryByPlaceholderText("Instruction text…")).toBeNull();
  await act(async () => finishBeta(json(makeGuide("beta"))));
  await screen.findByDisplayValue("beta instruction");
  await user.click(screen.getByRole("button", { name: /Suggested instruction/ }));
  await waitFor(() => expect(requests.filter(r => r.options.method === "PUT")).toHaveLength(1));
  const saved = requests.find(r => r.options.method === "PUT");
  expect(saved.url).toBe("/api/projects/beta/guide");
  expect(JSON.parse(saved.options.body).title).toBe("beta");
});

it("ignores late guide responses from a previously selected project", async () => {
  let finishAlpha;
  override = (url) => url === "/api/projects/alpha/guide"
    ? new Promise((resolve) => { finishAlpha = resolve; }) : undefined;
  const user = userEvent.setup();
  render(<App />);
  await screen.findByRole("option", { name: "alpha" });
  await user.selectOptions(screen.getByRole("combobox", { name: "Project" }), "alpha");
  await screen.findByText("Loading guide…");
  await openProject(user, "beta");
  await act(async () => finishAlpha(json(makeGuide("alpha"))));
  expect(screen.queryByDisplayValue("alpha instruction")).toBeNull();
  expect(screen.getByDisplayValue("beta instruction")).toBeTruthy();
});

it("updates accepted suggestions in the textarea without reverting on blur", async () => {
  const user = userEvent.setup();
  render(<App />);
  await openProject(user);
  await user.click(screen.getByRole("button", { name: /Suggested instruction/ }));
  const textarea = await screen.findByDisplayValue("Suggested instruction");
  await user.click(textarea);
  await user.tab();
  await waitFor(() => expect(requests.filter(r => r.options.method === "PUT")).toHaveLength(1));
  expect(JSON.parse(requests.find(r => r.options.method === "PUT").options.body)
    .sections[0].steps[0].instruction).toBe("Suggested instruction");
});

it("enables capture on video readiness and prevents overlapping captures", async () => {
  let finishCapture;
  override = (url) => url.endsWith("/capture")
    ? new Promise(resolve => { finishCapture = resolve; }) : undefined;
  const user = userEvent.setup();
  const { container } = render(<App />);
  await openProject(user);
  const capture = screen.getByRole("button", { name: "Capture this frame" });
  expect(capture.disabled).toBe(true);
  fireEvent.loadedData(container.querySelector("video"));
  expect(capture.disabled).toBe(false);
  await user.dblClick(capture);
  expect(requests.filter(r => r.url.endsWith("/capture"))).toHaveLength(1);
  expect(capture.disabled).toBe(true);
  await act(async () => finishCapture(json({ file: "frames/captured.png", timestamp: 1 })));
  await waitFor(() => expect(requests.filter(r => r.options.method === "PUT")).toHaveLength(1));
  const saved = JSON.parse(requests.find(r => r.options.method === "PUT").options.body);
  expect(saved.sections[0].steps).toHaveLength(2);
  expect(saved.sections[0].steps[1].frame).toBe("frames/captured.png");
});

it("keeps failed edits available for retry and blocks switching projects", async () => {
  let failing = true;
  override = (_url, options) => options.method === "PUT" && failing
    ? Promise.resolve(json({ detail: "disk full" }, 500)) : undefined;
  const user = userEvent.setup();
  render(<App />);
  await openProject(user);
  await user.click(screen.getByRole("button", { name: /Suggested instruction/ }));
  await screen.findByText("Not saved: disk full");
  expect(screen.getByDisplayValue("Suggested instruction")).toBeTruthy();
  expect(screen.getByRole("combobox", { name: "Project" }).disabled).toBe(true);
  failing = false;
  await user.click(screen.getByRole("button", { name: "Retry save" }));
  await waitFor(() => expect(screen.queryByText("Not saved: disk full")).toBeNull());
  expect(screen.getByRole("combobox", { name: "Project" }).disabled).toBe(false);
});

it("waits for saved edits before exporting and displays export failures", async () => {
  let finishSave;
  override = (url, options) => {
    if (options.method === "PUT" && !finishSave) return new Promise(resolve => { finishSave = resolve; });
    if (url.endsWith("/export")) return Promise.resolve(json({ detail: "Chrome unavailable" }, 500));
  };
  const user = userEvent.setup();
  render(<App />);
  await openProject(user);
  await user.click(screen.getByRole("button", { name: /Suggested instruction/ }));
  await user.click(screen.getByRole("button", { name: "Export HTML + PDF" }));
  expect(requests.some(r => r.url.endsWith("/export"))).toBe(false);
  await act(async () => finishSave(json({})));
  await screen.findByText("Chrome unavailable");
  expect(screen.queryByRole("link", { name: "view guide" })).toBeNull();
  const exportIndex = requests.findIndex(r => r.url.endsWith("/export"));
  expect(requests.slice(0, exportIndex).filter(r => r.options.method === "PUT")).toHaveLength(2);
});
