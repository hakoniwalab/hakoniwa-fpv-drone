const params = new URLSearchParams(location.search);
const assetRoot = params.get("assets") || "../build/catalog-showroom/glb";
const selection = document.getElementById("selection");
const graph = document.getElementById("graph");

let manifest = null;
let contract = null;
let scheduled = false;

function formatKey(key) {
  return key.replaceAll("_", " ");
}

function formatValue(value) {
  if (Array.isArray(value)) return value.join(" × ");
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : String(Number(value.toPrecision(6)));
  return String(value);
}

function safeProductUrl(value) {
  if (typeof value !== "string" || !value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}

function selectedCatalogEntry() {
  const portLabel = selection.querySelector(".port")?.textContent;
  if (!portLabel || !graph.textContent) return null;
  const [, nodeId] = portLabel.split(" / ");
  if (!nodeId) return null;
  try {
    const assembly = JSON.parse(graph.textContent);
    const node = assembly.nodes?.find((entry) => entry.id === nodeId);
    if (!node) return null;
    const item = manifest?.items?.find((entry) => entry.kind === node.kind && entry.id === node.product);
    const component = contract?.components?.find((entry) => entry.kind === node.kind && entry.id === node.product);
    return item ? { node, item, component } : null;
  } catch {
    return null;
  }
}

function renderDetails() {
  const selected = selectedCatalogEntry();
  if (!selected) return;
  const { node, item, component } = selected;
  const key = `${node.kind}:${node.product}:${node.id}`;
  if (selection.dataset.catalogDetailsKey === key && selection.querySelector(".catalog-details")) return;

  selection.querySelector(".catalog-details")?.remove();
  selection.dataset.catalogDetailsKey = key;

  const section = document.createElement("section");
  section.className = "catalog-details";

  const heading = document.createElement("h3");
  heading.textContent = "Catalog Specs";
  section.append(heading);

  if (item.vendor) {
    const vendor = document.createElement("p");
    vendor.className = "catalog-vendor";
    vendor.textContent = item.vendor;
    section.append(vendor);
  }

  if (item.description) {
    const description = document.createElement("p");
    description.className = "catalog-description";
    description.textContent = item.description;
    section.append(description);
  }

  const specs = document.createElement("dl");
  specs.className = "catalog-spec-grid";
  for (const [name, value] of Object.entries(item.specs || {})) {
    const term = document.createElement("dt");
    term.textContent = formatKey(name);
    const detail = document.createElement("dd");
    detail.textContent = formatValue(value);
    specs.append(term, detail);
  }
  if (specs.children.length) section.append(specs);

  const productUrl = safeProductUrl(item.metadata?.product_url);
  if (productUrl) {
    const link = document.createElement("a");
    link.className = "product-link";
    link.href = productUrl;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Product page ↗";
    section.append(link);
  }

  if (component?.assembly_ports?.length) {
    const interfaces = document.createElement("details");
    interfaces.className = "catalog-interfaces";
    const summary = document.createElement("summary");
    summary.textContent = `Interfaces (${component.assembly_ports.length})`;
    interfaces.append(summary);
    for (const port of component.assembly_ports) {
      const row = document.createElement("p");
      row.textContent = `${port.id} · ${port.role} · ${port.interface}`;
      interfaces.append(row);
    }
    section.append(interfaces);
  }

  selection.append(section);
}

function scheduleRender() {
  if (scheduled) return;
  scheduled = true;
  queueMicrotask(() => {
    scheduled = false;
    renderDetails();
  });
}

async function bootCatalogDetails() {
  try {
    [manifest, contract] = await Promise.all([
      fetch(`${assetRoot}/manifest.json`).then((response) => response.json()),
      fetch(`${assetRoot}/assembly-contract.json`).then((response) => response.json()),
    ]);
    new MutationObserver(scheduleRender).observe(selection, { childList: true, subtree: true, characterData: true });
    new MutationObserver(scheduleRender).observe(graph, { childList: true, subtree: true, characterData: true });
    scheduleRender();
  } catch (error) {
    console.warn("Catalog details unavailable", error);
  }
}

bootCatalogDetails();
