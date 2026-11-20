/* Bejitech License Manager (web): small helpers. Pages work without JS except New Sale's key list. */
(function () {
  "use strict";
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  function formatTZS(n) { return "TZS " + Math.round(n).toLocaleString("en-US"); }
  function parseAmount(text) {
    const v = parseFloat(String(text || "").replace(/[, ]/g, ""));
    return isNaN(v) ? 0 : v;
  }

  document.addEventListener("DOMContentLoaded", function () {
    // Click anywhere on a table row to open it (links, buttons and forms keep their own behaviour)
    $$("tr[data-href]").forEach(function (tr) {
      tr.addEventListener("click", function (e) {
        if (e.target.closest("a, button, input, select, textarea, label, form, summary")) return;
        window.location = tr.dataset.href + "#detail";
      });
    });
    // Keep the selected row's details in view
    $$("a[href*='id=']").forEach(function (a) {
      if (a.closest("tr[data-href]") && !a.hash) a.href += "#detail";
    });

    // Filters that apply as soon as they change
    $$("[data-autosubmit]").forEach(function (el) {
      el.addEventListener("change", function () { el.form.submit(); });
    });

    // Ask before destructive actions
    $$("form[data-confirm]").forEach(function (f) {
      f.addEventListener("submit", function (e) {
        if (!window.confirm(f.dataset.confirm)) e.preventDefault();
      });
    });

    // Copy a revealed licence key (and record the copy in the audit log)
    $$("[data-copy]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const el = $(btn.dataset.copy);
        if (!el) return;
        const text = el.textContent.trim();
        const done = function () {
          btn.textContent = "Copied ✓";
          if (btn.dataset.copiedUrl) {
            fetch(btn.dataset.copiedUrl, { method: "POST", credentials: "same-origin",
              headers: { "Content-Type": "application/x-www-form-urlencoded" },
              body: "csrf=" + encodeURIComponent(btn.dataset.csrf || "") });
          }
        };
        if (navigator.clipboard && window.isSecureContext) {
          navigator.clipboard.writeText(text).then(done, function () { selectText(el); });
        } else {
          selectText(el);
          try { document.execCommand("copy"); done(); } catch (err) { /* user can copy by hand */ }
        }
      });
    });
    function selectText(el) {
      const r = document.createRange(); r.selectNodeContents(el);
      const s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
    }
    // Hide a revealed key again after a while
    $$("[data-hide-after]").forEach(function (el) {
      const secs = parseInt(el.dataset.hideAfter, 10) || 30;
      setTimeout(function () {
        const box = el.closest(".reveal-box");
        if (box) box.innerHTML = '<span class="muted">Key hidden again. Use Reveal to show it.</span>';
        const h = document.querySelector(".detail h2 .mono");
        if (h) h.textContent = "XXXXX-XXXXX-XXXXX-XXXXX-" + h.textContent.trim().slice(-5);
      }, secs * 1000);
    });

    productForm();
    licenseForm();
    newSale();
  });

  // ---------- Add / edit product: suggest the display name ----------
  function productForm() {
    const display = $("[data-display-name]");
    if (!display) return;
    let auto = !display.value;
    display.addEventListener("input", function () { auto = !display.value; });
    $$("[data-name-part]").forEach(function (inp) {
      inp.addEventListener("input", function () {
        if (!auto) return;
        display.value = $$("[data-name-part]").map(function (x) { return x.value.trim(); }).filter(Boolean).join(" ");
      });
    });
  }

  // ---------- Add / edit licence key: licence-type defaults, USD rate ----------
  function licenseForm() {
    const form = $("#license-form");
    if (!form) return;
    const productTypes = JSON.parse(form.dataset.productTypes || "{}");
    const defaults = JSON.parse(form.dataset.typeDefaults || "{}");
    const editing = form.dataset.editing === "1";
    const product = $("[data-product]", form), ltype = $("[data-ltype]", form), hint = $("[data-type-hint]", form);
    const currency = $("[data-currency]", form), rateRow = $("[data-rate-row]", form);

    function applyType(setCapacity) {
      const t = defaults[ltype.value];
      if (!t) return;
      $("[data-multi]", form).checked = !!t.allows_multiple_customers;
      $("[data-reassign]", form).checked = !!t.reassignable;
      const cap = $("[data-capacity]", form);
      if (cap && setCapacity) cap.value = t.default_capacity || 1;
    }
    function showHint() {
      if (hint && product) hint.hidden = String(productTypes[product.value]) === String(ltype.value);
    }
    if (product && ltype) {
      product.addEventListener("change", function () {
        if (productTypes[product.value]) ltype.value = productTypes[product.value];
        if (!editing) applyType(true);
        showHint();
      });
      ltype.addEventListener("change", function () { applyType(!editing); showHint(); });
      if (!editing) {
        if (productTypes[product.value] && !form.querySelector("[data-ltype] option[selected]")) {
          ltype.value = productTypes[product.value];
        }
        if (!form.querySelector(".flash.error")) applyType(true);
      }
      showHint();
    }
    if (currency && rateRow) {
      const sync = function () { rateRow.hidden = currency.value !== "USD"; };
      currency.addEventListener("change", sync); sync();
    }
  }

  // ---------- New sale: live key recommendation and total ----------
  function newSale() {
    const form = $("#sale-form");
    if (!form) return;
    const customer = $("[data-customer]", form), product = $("[data-product]", form), qty = $("[data-qty]", form);
    const price = $("[data-price]", form), discount = $("[data-discount]", form), total = $("[data-total]", form);
    const options = $("[data-options]", form), plan = $("[data-plan]", form), after = $("[data-after]", form);
    const complete = $("[data-complete]", form);
    let afterTexts = {}, timer = null, seq = 0;

    function customerInfo() {
      const opt = customer.selectedOptions[0];
      $("[data-customer-info]", form).textContent = opt && opt.value ? "✓ " + opt.dataset.info : "Choose or add a customer.";
    }
    function productInfo(setPrice) {
      const opt = product.selectedOptions[0];
      $("[data-stock-info]", form).textContent = opt ? opt.dataset.stock : "";
      if (opt && setPrice) price.value = opt.dataset.price || "";
    }
    function updateTotal() {
      const t = (parseInt(qty.value, 10) || 0) * parseAmount(price.value) - parseAmount(discount.value);
      total.textContent = t >= 0 ? formatTZS(t) : "Discount too large";
      complete.disabled = !(plan.value && t >= 0);
    }
    function choose(value) {
      plan.value = value;
      after.textContent = afterTexts[value] ? "After this sale: " + afterTexts[value] : "";
      updateTotal();
    }
    function render(data) {
      options.innerHTML = ""; afterTexts = {};
      if (!data.options.length) {
        const p = document.createElement("p");
        p.className = data.message && data.message.indexOf("Not enough") === 0 ? "error" : "muted";
        p.textContent = (p.className === "error" ? "✕ " : "") + (data.message || "Choose a customer and a product.");
        options.appendChild(p); choose(""); return;
      }
      data.options.forEach(function (o, i) {
        afterTexts[o.plan] = o.after;
        const lab = document.createElement("label");
        lab.className = "option" + (o.recommended ? " rec" : "");
        const r = document.createElement("input");
        r.type = "radio"; r.name = "plan_choice"; r.value = o.plan; r.checked = i === 0;
        r.addEventListener("change", function () { choose(o.plan); });
        const span = document.createElement("span");
        const strong = document.createElement("strong");
        strong.textContent = (o.recommended ? "★ " : "") + o.label;
        span.appendChild(strong);
        if (o.reason) {
          span.appendChild(document.createElement("br"));
          const why = document.createElement("span"); why.className = "muted small"; why.textContent = o.reason;
          span.appendChild(why);
        }
        lab.appendChild(r); lab.appendChild(span); options.appendChild(lab);
      });
      choose(data.options[0].plan);
    }
    function refresh() {
      clearTimeout(timer);
      timer = setTimeout(function () {
        const mine = ++seq;
        choose("");
        if (!customer.value || !product.value || !(parseInt(qty.value, 10) > 0)) {
          render({ options: [], message: "Choose a customer and a product." }); return;
        }
        const url = "/api/recommend?" + new URLSearchParams({ customer: customer.value, product: product.value, qty: qty.value });
        fetch(url, { credentials: "same-origin" }).then(function (r) { return r.json(); }).then(function (d) {
          if (mine === seq) render(d);
        }).catch(function () { render({ options: [], message: "Could not load the keys. Check that the app is running." }); });
      }, 150);
    }
    customer.addEventListener("change", function () { customerInfo(); refresh(); });
    product.addEventListener("change", function () { productInfo(true); refresh(); });
    qty.addEventListener("input", refresh);
    price.addEventListener("input", updateTotal);
    discount.addEventListener("input", updateTotal);
    form.addEventListener("submit", function () { complete.disabled = true; complete.textContent = "Saving…"; });
    customerInfo(); productInfo(!price.value); refresh();
  }
})();
