const titles = {
  inventory: ["Склад", "Остатки считаются из покупок"],
  review: ["Проверка", "Неизвестные товары из чеков"],
  catalog: ["Продукты", "Внутренний каталог"],
  in: ["Приход", "Ручное пополнение склада"],
};

const view = document.getElementById("view");
const title = document.getElementById("title");
const subtitle = document.getElementById("subtitle");
let tab = "inventory";
let products = [];

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = data?.detail;
    const message = typeof detail === "string" ? detail : JSON.stringify(detail || data);
    throw new Error(message);
  }
  return data;
}

function qty(value, unit) {
  const n = Number(value);
  const pretty = Number.isInteger(n) ? String(n) : n.toString();
  return `${pretty} ${unit}`;
}

function productOptions(selected = "") {
  return products
    .map((p) => `<option value="${p.id}" data-unit="${p.base_unit}" ${String(p.id) === String(selected) ? "selected" : ""}>${p.name}</option>`)
    .join("");
}

function setMessage(el, text, ok = false) {
  el.className = ok ? "ok" : "error";
  el.textContent = text;
}

async function loadProducts() {
  products = await api("/products");
}

async function renderInventory() {
  const items = await api("/inventory");
  if (!items.length) {
    view.innerHTML = `<p class="empty">Каталог пуст. Добавьте продукт.</p>`;
    return;
  }
  view.innerHTML = items
    .map((item) => {
      const low = Number(item.quantity) < Number(item.minimum_stock);
      return `<article class="card ${low ? "low" : ""}">
        <div class="row">
          <div>
            <div class="name">${item.name}</div>
            <div class="meta">${low ? "ниже минимума" : "в норме"} · мин. ${qty(item.minimum_stock, item.unit)}</div>
          </div>
          <div class="qty">${qty(item.quantity, item.unit)}</div>
        </div>
      </article>`;
    })
    .join("");
}

async function renderReview() {
  const [lines] = await Promise.all([api("/receipt-lines"), loadProducts()]);
  if (!lines.length) {
    view.innerHTML = `<p class="empty">Очередь проверки пуста.</p>`;
    return;
  }
  view.innerHTML = lines
    .map((line) => {
      return `<article class="card" data-line="${line.id}">
        <div class="row">
          <div>
            <div class="name">${line.name}</div>
            <div class="meta">${line.store_name} · ${line.external_product_id} · ${line.occurrence_count} чек(а)</div>
          </div>
          <span class="badge">${qty(line.total_package_count, "уп.")}</span>
        </div>
        <div class="grid-2">
          <button class="secondary" data-mode="existing">Есть в каталоге</button>
          <button class="secondary" data-mode="create">Создать продукт</button>
        </div>
        <form class="hidden" data-form="existing">
          <label>Продукт</label>
          <select name="product_id">${productOptions()}</select>
          <div class="grid-2">
            <div><label>В одной упаковке</label><input name="package_quantity" type="number" min="0.001" step="0.001" required /></div>
            <div><label>Единица</label>
              <select name="package_unit">
                <option value="g">g</option>
                <option value="ml">ml</option>
                <option value="pcs">pcs</option>
              </select>
            </div>
          </div>
          <button type="submit">Привязать</button>
          <div class="error"></div>
        </form>
        <form class="hidden" data-form="create">
          <label>Название у нас</label>
          <input name="name" required placeholder="Яйца" />
          <div class="grid-2">
            <div><label>Единица продукта</label>
              <select name="base_unit">
                <option value="g">g</option>
                <option value="ml">ml</option>
                <option value="pcs">pcs</option>
              </select>
            </div>
            <div><label>Минимум</label><input name="minimum_stock" type="number" min="0" step="0.001" value="0" /></div>
          </div>
          <div class="grid-2">
            <div><label>В одной упаковке</label><input name="package_quantity" type="number" min="0.001" step="0.001" required /></div>
            <div><label>Единица упаковки</label>
              <select name="package_unit">
                <option value="g">g</option>
                <option value="ml">ml</option>
                <option value="pcs">pcs</option>
              </select>
            </div>
          </div>
          <button type="submit">Создать и привязать</button>
          <div class="error"></div>
        </form>
      </article>`;
    })
    .join("");

  view.querySelectorAll("[data-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      const card = button.closest(".card");
      card.querySelectorAll("form").forEach((form) => form.classList.add("hidden"));
      card.querySelector(`[data-form="${button.dataset.mode}"]`).classList.remove("hidden");
    });
  });

  view.querySelectorAll('form[data-form="existing"]').forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const lineId = form.closest(".card").dataset.line;
      const msg = form.querySelector(".error");
      try {
        await api(`/receipt-lines/${lineId}/resolve`, {
          method: "POST",
          body: JSON.stringify({
            product_id: Number(form.product_id.value),
            package_quantity: Number(form.package_quantity.value),
            package_unit: form.package_unit.value,
          }),
        });
        await render();
      } catch (error) {
        setMessage(msg, error.message);
      }
    });
  });

  view.querySelectorAll('form[data-form="create"]').forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const lineId = form.closest(".card").dataset.line;
      const msg = form.querySelector(".error");
      try {
        await api(`/receipt-lines/${lineId}/create-and-resolve`, {
          method: "POST",
          body: JSON.stringify({
            product: {
              name: form.name.value,
              base_unit: form.base_unit.value,
              minimum_stock: Number(form.minimum_stock.value || 0),
            },
            package_quantity: Number(form.package_quantity.value),
            package_unit: form.package_unit.value,
          }),
        });
        await render();
      } catch (error) {
        setMessage(msg, error.message);
      }
    });
  });
}

async function renderCatalog() {
  await loadProducts();
  const list = products.length
    ? products
        .map(
          (p) => `<article class="card">
            <div class="row">
              <div class="name">${p.name}</div>
              <div class="meta">${p.base_unit} · мин. ${qty(p.minimum_stock, p.base_unit)}</div>
            </div>
          </article>`
        )
        .join("")
    : `<p class="empty">Пока нет продуктов.</p>`;

  view.innerHTML = `${list}
    <article class="card">
      <div class="name">Новый продукт</div>
      <form id="product-form">
        <label>Название</label>
        <input name="name" required placeholder="Куриное филе" />
        <div class="grid-2">
          <div>
            <label>Единица</label>
            <select name="base_unit">
              <option value="g">g</option>
              <option value="ml">ml</option>
              <option value="pcs">pcs</option>
            </select>
          </div>
          <div>
            <label>Минимум</label>
            <input name="minimum_stock" type="number" min="0" step="0.001" value="0" />
          </div>
        </div>
        <button type="submit">Добавить в каталог</button>
        <div class="error"></div>
      </form>
    </article>`;

  document.getElementById("product-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    const msg = form.querySelector(".error");
    try {
      await api("/products", {
        method: "POST",
        body: JSON.stringify({
          name: form.name.value,
          base_unit: form.base_unit.value,
          minimum_stock: Number(form.minimum_stock.value || 0),
        }),
      });
      await render();
    } catch (error) {
      setMessage(msg, error.message);
    }
  });
}

async function renderIn() {
  await loadProducts();
  const purchases = await api("/purchases");
  const history = purchases.length
    ? purchases
        .slice(0, 8)
        .map(
          (p) => `<article class="card">
            <div class="row">
              <div class="name">${p.product_name}</div>
              <div class="qty">+${qty(p.quantity, p.unit)}</div>
            </div>
          </article>`
        )
        .join("")
    : `<p class="empty">Приходов ещё не было.</p>`;

  view.innerHTML = `
    <article class="card">
      <div class="name">Положить на склад</div>
      <form id="purchase-form">
        <label>Продукт</label>
        <select name="product_id">${productOptions()}</select>
        <div class="grid-2">
          <div><label>Количество</label><input name="quantity" type="number" min="0.001" step="0.001" required /></div>
          <div><label>Единица</label>
            <select name="unit">
              <option value="g">g</option>
              <option value="ml">ml</option>
              <option value="pcs">pcs</option>
            </select>
          </div>
        </div>
        <button type="submit">Добавить приход</button>
        <div class="error"></div>
      </form>
    </article>
    ${history}`;

  const form = document.getElementById("purchase-form");
  const syncUnit = () => {
    const option = form.product_id.selectedOptions[0];
    if (option) form.unit.value = option.dataset.unit;
  };
  form.product_id.addEventListener("change", syncUnit);
  syncUnit();
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const msg = form.querySelector(".error");
    try {
      await api("/purchases", {
        method: "POST",
        body: JSON.stringify({
          product_id: Number(form.product_id.value),
          quantity: Number(form.quantity.value),
          unit: form.unit.value,
        }),
      });
      await render();
    } catch (error) {
      setMessage(msg, error.message);
    }
  });
}

async function render() {
  const [name, note] = titles[tab];
  title.textContent = name;
  subtitle.textContent = note;
  view.innerHTML = `<p class="empty">Загрузка…</p>`;
  try {
    if (tab === "inventory") await renderInventory();
    if (tab === "review") await renderReview();
    if (tab === "catalog") await renderCatalog();
    if (tab === "in") await renderIn();
  } catch (error) {
    view.innerHTML = `<p class="error">${error.message}</p>`;
  }
}

document.querySelectorAll(".tabs button").forEach((button) => {
  button.addEventListener("click", () => {
    tab = button.dataset.tab;
    document.querySelectorAll(".tabs button").forEach((item) => item.classList.toggle("active", item === button));
    render();
  });
});

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/app/sw.js");
}

render();
