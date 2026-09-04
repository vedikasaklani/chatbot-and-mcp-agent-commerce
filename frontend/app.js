"use strict";

const API_BASE = "https://backend-fastapi-bktw.onrender.com";
const API = {
  LOGIN_URL: `${API_BASE}/auth/login`,
  REGISTER_URL: `${API_BASE}/auth/register`,

  CHAT_URL: `${API_BASE}/chat`,
  CHAT_SESSION_URL: `${API_BASE}/chat/session`,
  PRODUCTS_URL: `${API_BASE}/products`,
  PRODUCTS_BY_ID_URL: (id) => `${API_BASE}/products/${id}`,

  CART_URL: `${API_BASE}/cart`,
  ADD_TO_CART_URL: (productId, quantity) => `${API_BASE}/cart/${productId}/${quantity}`,
  REMOVE_FROM_CART_URL: (productId, quantity) => `${API_BASE}/cart/${productId}/${quantity}/delete`,
  
  CREATE_ORDER_URL: `${API_BASE}/razorpay/agent/orders`,
  PAY_URL: (orderId) => `${API_BASE}/razorpay/agent/orders/${orderId}/pay`,
  VERIFY_PAYMENT_URL: (orderId) => `${API_BASE}/razorpay/agent/orders/${orderId}/verify`,
};
const state = {
  authToken: sessionStorage.getItem("authToken") || null,
  chatSessionId: sessionStorage.getItem("chatSessionId") || crypto.randomUUID(),
  cart: { items: [], total: 0 }, 
};

sessionStorage.setItem("chatSessionId", state.chatSessionId);

const loginScreen = document.getElementById("login-screen");
const appScreen = document.getElementById("app-screen");
const loginForm = document.getElementById("login-form");
const loginError = document.getElementById("login-error");
const loginSubmit = document.getElementById("login-submit");

const messagesEl = document.getElementById("messages");
const composer = document.getElementById("composer");
const composerInput = document.getElementById("composer-input");
const composerSend = document.getElementById("composer-send");

const logoutBtn = document.getElementById("logout-btn");
const cartToggle = document.getElementById("cart-toggle");
const cartClose = document.getElementById("cart-close");
const cartDrawer = document.getElementById("cart-drawer");
const cartBackdrop = document.getElementById("cart-backdrop");
const cartItemsEl = document.getElementById("cart-items");
const cartTotalEl = document.getElementById("cart-total");
const cartCheckoutBtn = document.getElementById("cart-checkout");

async function boot() {
  if (state.authToken) {
    // Verify token is valid by making a test API call
    try {
      const res = await fetch(API.CART_URL, {
        method: "GET",
        headers: authHeaders(),
      });
      if (res.ok) {
        showApp();
        refreshCart();
        return;
      }
    } catch (e) {
      // API call failed, token might be invalid
    }
    
    // If we got here, token is invalid - clear it and show login
    state.authToken = null;
    sessionStorage.removeItem("authToken");
  }
  
  showLogin();
}

function showLogin() {
  loginScreen.removeAttribute("hidden");
  appScreen.setAttribute("hidden", "");
  loginScreen.style.display = "flex";
  appScreen.style.display = "none";
}

function showApp() {
  loginScreen.setAttribute("hidden", "");
  appScreen.removeAttribute("hidden");
  loginScreen.style.display = "none";
  appScreen.style.display = "flex";
  composerInput.focus();
}

loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  loginError.hidden = true;
  loginSubmit.disabled = true;
  loginSubmit.textContent = "Signing in…";

  const username = document.getElementById("login-email").value.trim();
  const password = document.getElementById("login-password").value;

  try {
    const token = await login(username, password);
    state.authToken = token;
    sessionStorage.setItem("authToken", token);
    showApp();
    refreshCart();
  } catch (err) {
    loginError.textContent = err.message || "Sign in failed. Check your credentials.";
    loginError.hidden = false;
  } finally {
    loginSubmit.disabled = false;
    loginSubmit.textContent = "Sign in";
  }
});

// Detect whether this login was initiated by WorkOS
const params = new URLSearchParams(window.location.search);
const externalAuthId = params.get("external_auth_id");

async function login(username, password) {
  const formData = new URLSearchParams();

  formData.append("username", username);
  formData.append("password", password);

  if (externalAuthId) {
      // WorkOS OAuth login
      formData.append("external_auth_id", externalAuthId);

      const form = document.createElement("form");
      form.method = "POST";
      form.action = `${API_BASE}/auth/workos/login`;

      const externalIdInput = document.createElement("input");
      externalIdInput.type = "hidden";
      externalIdInput.name = "external_auth_id";
      externalIdInput.value = externalAuthId;

      const usernameInput = document.createElement("input");
      usernameInput.type = "hidden";
      usernameInput.name = "username";
      usernameInput.value = username;

      const passwordInput = document.createElement("input");
      passwordInput.type = "hidden";
      passwordInput.name = "password";
      passwordInput.value = password;

      form.appendChild(externalIdInput);
      form.appendChild(usernameInput);
      form.appendChild(passwordInput);

      document.body.appendChild(form);
      form.submit();
      return;
  }
  else{
    const body = new URLSearchParams();
    body.set("username", username);
    body.set("password", password);

    const res = await fetch(API.LOGIN_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "ngrok-skip-browser-warning": "true",
      },
      body,
    });

    if (!res.ok) {
      throw new Error(res.status === 401 ? "Incorrect email or password." : "Sign in failed.");
    }
    const data = await res.json();
    if (!data.access_token) throw new Error("Login response had no access_token.");
    return data.access_token;
  }
}

logoutBtn.addEventListener("click", () => {
  clearChatSession();
  state.authToken = null;
  sessionStorage.removeItem("authToken");
  sessionStorage.removeItem("chatSessionId");
  messagesEl.innerHTML = "";
  showLogin();
});

function authHeaders(extra = {}) {
  extra["ngrok-skip-browser-warning"] = "true";
  return { Authorization: `Bearer ${state.authToken}`, ...extra };
}

function chatHeaders(extra = {}) {
  return authHeaders({ "X-Chat-Session-Id": state.chatSessionId, ...extra });
}

function clearChatSession() {
  if (!state.authToken || !state.chatSessionId) return;

  // keepalive lets this request complete during page shutdown. The server also
  // expires orphaned sessions in case a browser terminates it early.
  fetch(API.CHAT_SESSION_URL, {
    method: "DELETE",
    headers: chatHeaders(),
    keepalive: true,
  }).catch(() => {});
}

window.addEventListener("pagehide", clearChatSession);

/** Redirects to login on a 401 so an expired token doesn't strand the user. */
function handleAuthFailure(res) {
  if (res.status === 401) {
    state.authToken = null;
    sessionStorage.removeItem("authToken");
    showLogin();
    return true;
  }
  return false;
}

composer.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = composerInput.value.trim();
  if (!text) return;

  addMessage("user", text);
  composerInput.value = "";
  composerInput.focus();
  setComposerBusy(true);

  const typingEl = addTypingIndicator();

  try {
    const reply = await sendChatMessage(text);
    typingEl.remove();
    renderAssistantReply(reply);
  } catch (err) {
    typingEl.remove();
    addMessage("error", err.message || "Something went wrong reaching the assistant.");
  } finally {
    setComposerBusy(false);
  }
});

function setComposerBusy(busy) {
  composerInput.disabled = busy;
  composerSend.disabled = busy;
}

async function sendChatMessage(text) {
  const res = await fetch(API.CHAT_URL, {
    method: "POST",
    headers: chatHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ messages: text }),
  });

  if (handleAuthFailure(res)) throw new Error("Session expired — please sign in again.");
  if (!res.ok) throw new Error(`Assistant request failed (${res.status}).`);

  // Response format from backend: { reply: string, products?: [...], cart?: {...}, order?: {...} }
  return res.json();
}

function renderAssistantReply(payload) {
  if (!payload || typeof payload !== "object") return;

  const text = payload.reply || payload.final_response;
  if (typeof text === "string" && text.trim()) {
    addMessage("assistant", text);
  }

  const products = Array.isArray(payload.products)
    ? payload.products
    : productsFromTrace(payload.trace);
  if (products.length) addProductGrid(products);

  const cart = payload.cart || resultFromTrace(payload.trace, "view_cart");
  if (cart && !cart.error) applyCartUpdate(cart);

  const order = payload.order || resultFromTrace(payload.trace, "create_order");
  if (order && !order.error && order.id != null) addOrderCard(order);
}

function productsFromTrace(trace) {
  if (!Array.isArray(trace)) return [];
  const listed = resultFromTrace(trace, "list_products");
  if (Array.isArray(listed) && listed.length) return listed;
  const single = resultFromTrace(trace, "get_product");
  if (single && !single.error && single.pid != null) return [single];
  return [];
}

function resultFromTrace(trace, toolName) {
  if (!Array.isArray(trace)) return null;
  for (let i = trace.length - 1; i >= 0; i--) {
    if (trace[i] && trace[i].tool === toolName) return trace[i].result;
  }
  return null;
}

/* ---- message bubbles ---- */
function addMessage(role, text) {
  const wrap = document.createElement("div");
  wrap.className = `msg msg-${role}`;
  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";
  bubble.textContent = text;
  wrap.appendChild(bubble);
  messagesEl.appendChild(wrap);
  scrollToBottom();
  return wrap;
}

function addTypingIndicator() {
  const wrap = document.createElement("div");
  wrap.className = "msg msg-assistant";
  wrap.innerHTML = `<div class="msg-bubble"><span class="typing-dots"><span></span><span></span><span></span></span></div>`;
  messagesEl.appendChild(wrap);
  scrollToBottom();
  return wrap;
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

/* ---- product cards (rendered inline in chat) ---- */
function addProductGrid(products) {
  const wrap = document.createElement("div");
  wrap.className = "msg msg-assistant";

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";
  bubble.style.background = "transparent";
  bubble.style.border = "none";
  bubble.style.padding = "0";

  const grid = document.createElement("div");
  grid.className = "product-grid";

  for (const p of products) {
    grid.appendChild(renderProductCard(p));
  }

  bubble.appendChild(grid);
  wrap.appendChild(bubble);
  messagesEl.appendChild(wrap);
  scrollToBottom();
}

function renderProductCard(p) {
  // Backend product schema: { pname, pid, price, stock, seller, categories, url }
  const card = document.createElement("div");
  card.className = "product-card";
  card.dataset.productId = p.pid;

  const img = document.createElement("img");
  img.src = p.url || "";
  img.alt = p.pname || "Product";
  img.loading = "lazy";
  card.appendChild(img);

  const name = document.createElement("div");
  name.className = "product-name";
  name.textContent = p.pname || "Unnamed product";
  card.appendChild(name);

  const seller = document.createElement("div");
  seller.className = "product-seller";
  seller.textContent = p.seller || "Unknown seller";
  card.appendChild(seller);

  const price = document.createElement("div");
  price.className = "product-price";
  price.textContent = formatRupees(p.price);
  card.appendChild(price);

  const stock = document.createElement("div");
  const inStock = typeof p.stock === "number" ? p.stock : null;
  stock.className = "product-stock" + (inStock !== null && inStock <= 3 ? " low" : "");
  stock.textContent =
    inStock === null ? "" : inStock > 0 ? `${inStock} in stock` : "Out of stock";
  card.appendChild(stock);

  // Add to cart button
  const addBtn = document.createElement("button");
  addBtn.className = "btn btn-small btn-add-to-cart";
  addBtn.textContent = "Add to cart";
  addBtn.addEventListener("click", () => addProductToCart(p.pid, p.pname, p.price));
  card.appendChild(addBtn);

  return card;
}

function addOrderCard(order) {
  const wrap = document.createElement("div");
  wrap.className = "msg msg-assistant";

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";
  bubble.style.background = "transparent";
  bubble.style.border = "none";
  bubble.style.padding = "0";

  bubble.appendChild(renderOrderCard(order));
  wrap.appendChild(bubble);
  messagesEl.appendChild(wrap);
  scrollToBottom();
}

function renderOrderCard(order) {
  const card = document.createElement("div");
  card.className = "order-card";
  card.dataset.orderId = order.id;

  const row = document.createElement("div");
  row.className = "order-card-row total";
  row.innerHTML = `<span>Order #${escapeHtml(String(order.id))}</span><span>${formatRupees(
    order.total_amount
  )}</span>`;
  card.appendChild(row);

  const statusEl = document.createElement("span");
  statusEl.className = "order-status " + statusClass(order.status);
  statusEl.textContent = statusLabel(order.status);
  card.appendChild(statusEl);

  const payBtn = document.createElement("button");
  payBtn.className = "btn btn-primary btn-block";
  payBtn.textContent = "Pay now";
  payBtn.style.marginTop = "4px";

  const isPayable = !order.status || /created|pending/i.test(order.status);
  payBtn.hidden = !isPayable;

  payBtn.addEventListener("click", () => {
    payBtn.disabled = true;
    payBtn.textContent = "Opening payment…";
    payForOrder(order.id, { statusEl, payBtn, card });
  });

  card.appendChild(payBtn);
  return card;
}

function statusClass(status) {
  if (!status) return "pending";
  const s = status.toUpperCase();
  if (s === "PAID") return "paid";
  if (s === "FAILED" || s === "CANCELLED") return "failed";
  return "pending";
}

function statusLabel(status) {
  if (!status) return "Awaiting payment";
  const s = status.toUpperCase();
  if (s === "PAID") return "Paid";
  if (s === "FAILED") return "Payment failed";
  if (s === "CANCELLED") return "Cancelled";
  if (s === "PENDING_APPROVAL") return "Pending approval"; // per README, not yet built
  return "Awaiting payment";
}

async function payForOrder(orderId, ui) {
  let session;
  try {
    const res = await fetch(API.PAY_URL(orderId), {
      method: "POST",
      headers: authHeaders(),
    });
    if (handleAuthFailure(res)) return;
    if (!res.ok) throw new Error(`Could not start checkout (${res.status}).`);
    session = await res.json();
  } catch (err) {
    resetPayButton(ui, "Pay now");
    addMessage("error", err.message || "Could not start checkout.");
    return;
  }

  if (typeof Razorpay === "undefined") {
    resetPayButton(ui, "Pay now");
    addMessage("error", "Razorpay Checkout.js did not load — check network/ad-blockers.");
    return;
  }

  const options = {
    key: session.key,
    amount: session.amount,
    currency: session.currency,
    order_id: session.order_id,
    name: session.name || "Order checkout",
    description: session.description || `Order #${orderId}`,

    prefill: session.prefill,
    notes: session.notes,
    handler: async function (response) {
      try {
        const verifyRes = await fetch(API.VERIFY_PAYMENT_URL(orderId), {
          method: "POST",
          headers: {
            ...authHeaders(),
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            razorpay_order_id: response.razorpay_order_id,
            razorpay_payment_id: response.razorpay_payment_id,
            razorpay_signature: response.razorpay_signature,
          }),
        });

        if (!verifyRes.ok) {
          const errText = await verifyRes.text();
          throw new Error(errText || "Payment verification failed.");
        }

        const verification = await verifyRes.json();
        if (String(verification.status).toLowerCase() === "paid") {
          markOrderConfirmed(ui);
        } else {
          await refreshOrderStatus(orderId, ui);
        }
      } catch (err) {
        addMessage("error", err.message || "Payment could not be confirmed.");
        if (ui?.statusEl) {
          ui.statusEl.textContent = "Payment verification failed";
          ui.statusEl.className = "order-status failed";
        }
      }
    },
    modal: {
      ondismiss: function () {
        resetPayButton(ui, "Pay now");
      },
    },
    theme: { color: "#3399cc" },
  };

  const rzp = new Razorpay(options);
  rzp.on("payment.failed", function () {
    if (ui?.statusEl) {
      ui.statusEl.textContent = "Payment failed";
      ui.statusEl.className = "order-status failed";
    }
    resetPayButton(ui, "Try again");
    addMessage("error", "Payment didn't go through. You can try again.");
  });
  rzp.open();
}

async function refreshOrderStatus(orderId, ui) {
  try {
    const res = await fetch(`${API.CREATE_ORDER_URL}/${orderId}`, {
      headers: authHeaders(),
    });
    if (handleAuthFailure(res)) return;
    if (!res.ok) throw new Error(`Could not refresh order status (${res.status}).`);

    const order = await res.json();
    if (String(order.status).toLowerCase() === "paid") {
      markOrderConfirmed(ui);
      return;
    }
    markPaymentSubmitted(ui);
  } catch (err) {
    addMessage("error", err.message || "Could not refresh order status.");
  }
}

function markOrderConfirmed(ui) {
  if (ui?.statusEl) {
    ui.statusEl.textContent = "Order confirmed";
    ui.statusEl.className = "order-status paid";
  }
  if (ui?.payBtn) {
    ui.payBtn.hidden = true;
  }
  addMessage("system", "Order confirmed. Payment received.");
  clearCart();
}

function markPaymentSubmitted(ui) {
  if (ui?.statusEl) {
    ui.statusEl.textContent = "Payment submitted";
    ui.statusEl.className = "order-status pending";
  }
  if (ui?.payBtn) {
    ui.payBtn.hidden = true;
  }
  addMessage("system", "Payment submitted. We'll confirm it on our side.");
  refreshCart();
}

function resetPayButton(ui, label) {
  if (!ui?.payBtn) return;
  ui.payBtn.hidden = false;
  ui.payBtn.disabled = false;
  ui.payBtn.textContent = label;
}
//cart
cartToggle.addEventListener("click", openCart);
cartClose.addEventListener("click", closeCart);
cartBackdrop.addEventListener("click", closeCart);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !cartDrawer.hidden) closeCart();
});

function openCart() {
  cartDrawer.hidden = false;
  cartBackdrop.hidden = false;
  cartToggle.setAttribute("aria-expanded", "true");
  cartClose.focus();
}

function closeCart() {
  cartDrawer.hidden = true;
  cartBackdrop.hidden = true;
  cartToggle.setAttribute("aria-expanded", "false");
  cartToggle.focus();
}

async function refreshCart() {
  try {
    const res = await fetch(API.CART_URL, { headers: authHeaders() });
    if (handleAuthFailure(res)) return;
    if (!res.ok) return; // non-fatal — cart just stays as last known state
    const cart = await res.json();
    applyCartUpdate(cart);
  } catch {
    // Non-fatal — chat still works without a live cart view.
  }
}

function applyCartUpdate(cart) {
  // Backend cart schema: { user, cart, total_amt, cart_items: [{id, product_id, name, price, quantity, subtotal}] }
  const cartItems = Array.isArray(cart.cart_items) ? cart.cart_items : [];
  state.cart = {
    items: cartItems,
    total: typeof cart.total_amt === "number" ? cart.total_amt : 0,
  };
  renderCart();
}

function clearCart() {
  state.cart = { items: [], total: 0 };
  renderCart();
}

function renderCart() {
  const { items, total } = state.cart;

  cartItemsEl.innerHTML = "";
  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "cart-empty";
    empty.textContent = "Your cart is empty.";
    cartItemsEl.appendChild(empty);
  } else {
    for (const item of items) {
      cartItemsEl.appendChild(renderCartItem(item));
    }
  }

  cartTotalEl.textContent = formatRupees(total);
  cartCheckoutBtn.disabled = items.length === 0;
}

function renderCartItem(item) {
  const row = document.createElement("div");
  row.className = "cart-item";

  const left = document.createElement("div");
  left.innerHTML = `
    <div class="cart-item-name">${escapeHtml(item.name || "Item")}</div>
    <div class="cart-item-meta">Qty ${escapeHtml(String(item.quantity ?? 1))} · ${formatRupees(item.price)} · Subtotal: ${formatRupees(item.subtotal || 0)}</div>
  `;

  const removeBtn = document.createElement("button");
  removeBtn.className = "cart-item-remove";
  removeBtn.textContent = "Remove";
  removeBtn.addEventListener("click", () => removeCartItem(item));

  row.appendChild(left);
  row.appendChild(removeBtn);
  return row;
}

async function removeCartItem(item) {
  // Backend route: POST /cart/{product_id}/{quantity}/delete - removes specified quantity of item
  try {
    const res = await fetch(API.REMOVE_FROM_CART_URL(item.product_id, item.quantity), {
      method: "POST",
      headers: authHeaders(),
    });
    if (handleAuthFailure(res)) return;
    if (res.ok) refreshCart();
  } catch {
    addMessage("error", "Couldn't remove that item — try again.");
  }
}

async function addProductToCart(productId, productName, price) {
  try {
    const res = await fetch(API.ADD_TO_CART_URL(productId, 1), {
      method: "POST",
      headers: authHeaders(),
    });
    if (handleAuthFailure(res)) return;
    if (!res.ok) throw new Error(`Could not add to cart (${res.status}).`);
    
    addMessage("system", `Added "${productName}" to cart`);
    await refreshCart();
  } catch (err) {
    addMessage("error", err.message || "Could not add item to cart.");
  }
}

cartCheckoutBtn.addEventListener("click", async () => {
  cartCheckoutBtn.disabled = true;
  cartCheckoutBtn.textContent = "Creating order…";
  try {
    const res = await fetch(API.CREATE_ORDER_URL, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
    });
    if (handleAuthFailure(res)) return;
    if (!res.ok) throw new Error(`Could not create order (${res.status}).`);
    const order = await res.json();
    clearCart();
    closeCart();
    addOrderCard(order);
  } catch (err) {
    addMessage("error", err.message || "Could not start checkout from cart.");
  } finally {
    cartCheckoutBtn.disabled = state.cart.items.length === 0;
    cartCheckoutBtn.textContent = "Checkout";
  }
});

function formatRupees(amount) {
  const n = typeof amount === "number" ? amount : Number(amount) || 0;
  return "₹" + n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

boot();
