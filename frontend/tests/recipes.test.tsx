import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React, { act } from "react";
import { StockRecipes } from "../src/components/StockRecipes";
import { validRecipe, matchesRecipe, type RecipeIntent } from "../src/recipe-utils";
import { setAccessToken } from "../src/api/session";
import type { Service } from "../src/types";
const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "http://localhost:5173" });
Object.assign(globalThis, { window: dom.window, document: dom.window.document, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const token = (sub = "manager", role = "responsable_institut") => `h.${Buffer.from(JSON.stringify({ sub, role })).toString("base64url")}.s`;
const response = (value: unknown) => new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
const services = [{ id: "care", name: "Care", status: "active" }, { id: "other", name: "Other", status: "active" }] as Service[];
const intent: RecipeIntent = { base_revision: 0, enabled: true, entries: [{ item_id: "stock", quantity: "4.125", unit: "ml", name: "Serum", sku: "SERUM" }], reason: "Explicit norm", idempotency_key: "original" };
const recipe = { id: "recipe", institute_id: "inst", service_id: "care", revision: 1, base_revision: 0, enabled: true, entries: [{ item_id: "stock", quantity: "4.125", unit: "ml" as const }], reason: "Explicit norm", actor_id: "manager", idempotency_key: "original", created_at: "2026-10-06T10:00:00Z" };
const item = { id: "stock", institute_id: "inst", sku: "SERUM", name: "Serum", category: "cabine", unit: "ml", reorder_threshold: "1.000", on_hand: "0.000", at_or_below_threshold: true, actor_id: "manager", created_at: "2026-10-06T10:00:00Z" };
const key = `flowpilot.recipe-request:${JSON.stringify(["inst", "care", "manager"])}`;
function button(text: string) { return Array.from(document.querySelectorAll<HTMLButtonElement>("button")).find(button => button.textContent === text)!; }
async function select(service: string) { await act(async () => { const select = document.querySelector<HTMLSelectElement>("select")!; select.value = service; select.dispatchEvent(new dom.window.Event("change", { bubbles: true })); }); }

test("recipe snapshots reject incoherent versions, duplicate or changed-unit original terms", () => {
  assert.equal(validRecipe(recipe, "inst", "care"), true);
  assert.equal(validRecipe({ ...recipe, base_revision: 1 }, "inst", "care"), false);
  assert.equal(validRecipe({ ...recipe, entries: [...recipe.entries, ...recipe.entries] }, "inst", "care"), false);
  assert.equal(validRecipe({ ...recipe, enabled: false }, "inst", "care"), false);
  assert.equal(matchesRecipe({ ...recipe, entries: [{ ...recipe.entries[0], unit: "g" }] }, intent, "manager"), false);
});

test("reception reads recipes without authoring; failed refresh hides old facts", async () => {
  sessionStorage.clear(); setAccessToken(token("cashier", "accueil"));
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  let failed = false;
  globalThis.fetch = async url => { if (failed) throw new Error("Unavailable"); return response(String(url).includes("/items/") ? item : String(url).includes("/recipes?") ? [recipe] : recipe); };
  try {
    await act(async () => root.render(<StockRecipes institute="inst" services={services} />)); await select("care");
    assert.match(document.body.textContent!, /4,125 ml/); assert.equal(document.querySelectorAll("form").length, 0);
    failed = true; await act(async () => button("Actualiser les recettes").click());
    assert.doesNotMatch(document.body.textContent!, /4,125|Explicit norm/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});

test("saved recipe survives lost POST and remount and verifies the original version before clearing", async () => {
  sessionStorage.clear(); setAccessToken(token()); sessionStorage.setItem(key, JSON.stringify(intent));
  let root = createRoot(document.getElementById("root")!);
  const original = globalThis.fetch; let posts = 0, originals = 0;
  globalThis.fetch = async (url, options) => {
    if (options?.method === "POST") {
      assert.deepEqual(JSON.parse(String(options.body)), { ...intent, entries: [{ item_id: "stock", quantity: "4.125" }] });
      assert.deepEqual(JSON.parse(sessionStorage.getItem(key)!), intent);
      if (++posts === 1) throw new Error("Lost response"); return response(recipe);
    }
    if (String(url).endsWith("/recipes/recipe")) { originals++; return response(recipe); }
    if (String(url).includes("/items/")) return response(item);
    return response(String(url).includes("/recipes?") ? posts ? [recipe] : [] : posts ? recipe : null);
  };
  try {
    await act(async () => root.render(<StockRecipes institute="inst" services={services} />)); await select("care");
    await act(async () => button("Reprendre la recette conservée").click());
    assert.ok(sessionStorage.getItem(key)); assert.equal(originals, 0);
    await act(async () => root.unmount()); root = createRoot(document.getElementById("root")!);
    await act(async () => root.render(<StockRecipes institute="inst" services={services} />)); await select("care");
    await act(async () => button("Reprendre la recette conservée").click());
    assert.equal(posts, 2); assert.equal(originals, 1); assert.equal(sessionStorage.getItem(key), null);
    assert.match(document.body.textContent!, /Version 1 enregistrée/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});

test("late prior-service reads cannot publish into the newly selected service", async () => {
  sessionStorage.clear(); setAccessToken(token("cashier", "accueil"));
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  const pending: Array<(value: Response) => void> = [];
  globalThis.fetch = async url => String(url).includes("/services/care/") ? new Promise(resolve => pending.push(resolve)) : response(String(url).includes("/recipes?") ? [] : null);
  try {
    await act(async () => root.render(<StockRecipes institute="inst" services={services} />)); await select("care"); await select("other");
    await act(async () => { pending[0](response(recipe)); pending[1](response([recipe])); });
    assert.match(document.body.textContent!, /Aucune recette configurée/); assert.doesNotMatch(document.body.textContent!, /Explicit norm|4,125/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});

test("refreshing a newer recipe does not silently rebase an existing edit", async () => {
  sessionStorage.clear(); setAccessToken(token());
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  let latest = recipe;
  globalThis.fetch = async url => response(String(url).includes("/items/") ? item : String(url).includes("/items?") ? [item] : String(url).includes("/recipes?") ? [latest] : latest);
  try {
    await act(async () => root.render(<StockRecipes institute="inst" services={services} />)); await select("care");
    latest = { ...recipe, revision: 2, base_revision: 1, entries: [{ ...recipe.entries[0], quantity: "8.250" }], idempotency_key: "newer" };
    await act(async () => button("Actualiser les recettes").click());
    assert.match(document.body.textContent!, /Modification depuis la version 1/);
    assert.match(document.body.textContent!, /8,250 ml/);
    assert.equal(document.querySelector<HTMLInputElement>("input[inputmode='decimal']")!.value, "4.125");
    await act(async () => button("Repartir de la version courante").click());
    assert.match(document.body.textContent!, /Modification depuis la version 2/);
    assert.equal(document.querySelector<HTMLInputElement>("input[inputmode='decimal']")!.value, "8.250");
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});

test("pending recipe recovery remains selectable without an active catalogue entry", async () => {
  sessionStorage.clear(); setAccessToken(token());
  sessionStorage.setItem(key, JSON.stringify({ ...intent, service_name: "Care historique" }));
  const root = createRoot(document.getElementById("root")!), original = globalThis.fetch;
  let posts = 0;
  globalThis.fetch = async (url, options) => {
    if (options?.method === "POST") { posts++; const body = JSON.parse(String(options.body)); assert.equal(body.service_name, undefined); assert.equal(body.idempotency_key, "original"); return response(recipe); }
    return response(String(url).includes("/items/") ? item : String(url).includes("/recipes?") ? [recipe] : recipe);
  };
  try {
    await act(async () => root.render(<StockRecipes institute="inst" services={[]} />));
    assert.match(document.body.textContent!, /Care historique/); await select("care");
    await act(async () => button("Reprendre la recette conservée").click());
    assert.equal(posts, 1); assert.equal(sessionStorage.getItem(key), null);
  } finally { await act(async () => root.unmount()); globalThis.fetch = original; sessionStorage.clear(); }
});
