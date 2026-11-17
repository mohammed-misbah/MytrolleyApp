"use strict";

// Swagger UI bootstrap for this project.
//
// The stock drf-spectacular script embeds the CSRF token at page render time.
// Django rotates that token on login and logout, so the embedded value becomes
// stale. This template reads the current `csrftoken` cookie for every unsafe
// request and bootstraps the cookie anonymously on page load.

const swaggerSettings = {{ settings|safe }};
const schemaAuthNames = {{ schema_auth_names|safe }};
let schemaAuthFailed = false;
const plugins = [];

const csrfHeaderName = "{{ csrf_header_name }}";

const getCsrfToken = () => {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  if (match) {
    return decodeURIComponent(match[1]);
  }
  // Fallback for the first paint if the bootstrap request has not completed.
  return "{{ csrf_token }}";
};

const setInputValue = (input, value) => {
  // React tracks the previous value on the DOM node. Use the native setter and
  // fire input so Swagger UI updates its operation state and validation.
  const descriptor = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype,
    "value"
  );
  if (descriptor && descriptor.set) {
    descriptor.set.call(input, value);
  } else {
    input.value = value;
  }
  input.dispatchEvent(new Event("input", { bubbles: true }));
};

const syncCsrfHeaderInputs = () => {
  const token = getCsrfToken();
  if (!token) {
    return;
  }
  const target = csrfHeaderName.toLowerCase();
  // The schema marks X-CSRFToken required, so Swagger UI refuses to execute
  // while this field is empty. Keep it filled from the current cookie so the
  // documented parameter is satisfied without manual copying.
  document.querySelectorAll("input[placeholder]").forEach((input) => {
    if (input.placeholder.toLowerCase() === target && input.value !== token) {
      setInputValue(input, token);
    }
  });
};

const bootstrapCsrf = async () => {
  try {
    await fetch("{% url 'accounts:csrf' %}", {
      method: "GET",
      credentials: "same-origin",
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
  } catch (error) {
    console.warn("CSRF bootstrap failed; reload Swagger before testing login.", error);
  }
};

const reloadSchemaOnAuthChange = () => {
  return {
    statePlugins: {
      auth: {
        wrapActions: {
          authorizeOauth2:(ori) => (...args) => {
            schemaAuthFailed = false;
            setTimeout(() => ui.specActions.download());
            return ori(...args);
          },
          authorize: (ori) => (...args) => {
            schemaAuthFailed = false;
            setTimeout(() => ui.specActions.download());
            return ori(...args);
          },
          logout: (ori) => (...args) => {
            schemaAuthFailed = false;
            setTimeout(() => ui.specActions.download());
            return ori(...args);
          },
        },
      },
    },
  };
};

if (schemaAuthNames.length > 0) {
  plugins.push(reloadSchemaOnAuthChange);
}

const uiInitialized = () => {
  try {
    ui;
    return true;
  } catch {
    return false;
  }
};

const isSchemaUrl = (url) => {
  if (!uiInitialized()) {
    return false;
  }
  return url === new URL(ui.getConfigs().url, document.baseURI).href;
};

const responseInterceptor = (response, ...args) => {
  if (!response.ok && isSchemaUrl(response.url)) {
    console.warn("schema request received '" + response.status + "'. disabling credentials for schema till logout.");
    if (!schemaAuthFailed) {
      // only retry once to prevent endless loop.
      schemaAuthFailed = true;
      setTimeout(() => ui.specActions.download());
    }
  }
  // Login and logout rotate the CSRF cookie. Refresh the visible header
  // parameter after every response so the next Execute sends a current value.
  setTimeout(syncCsrfHeaderInputs, 0);
  return response;
};

const injectAuthCredentials = (request) => {
  let authorized;
  if (uiInitialized()) {
    const state = ui.getState().get("auth").get("authorized");
    if (state !== undefined && Object.keys(state.toJS()).length !== 0) {
      authorized = state.toJS();
    }
  } else if (![undefined, "{}"].includes(localStorage.authorized)) {
    authorized = JSON.parse(localStorage.authorized);
  }
  if (authorized === undefined) {
    return;
  }
  for (const authName of schemaAuthNames) {
    const authDef = authorized[authName];
    if (authDef === undefined || authDef.schema === undefined) {
      continue;
    }
    if (authDef.schema.type === "http" && authDef.schema.scheme === "bearer") {
      request.headers["Authorization"] = "Bearer " + authDef.value;
      return;
    } else if (authDef.schema.type === "http" && authDef.schema.scheme === "basic") {
      request.headers["Authorization"] = "Basic " + btoa(authDef.value.username + ":" + authDef.value.password);
      return;
    } else if (authDef.schema.type === "apiKey" && authDef.schema.in === "header") {
      request.headers[authDef.schema.name] = authDef.value;
      return;
    } else if (authDef.schema.type === "oauth2" && authDef.token.token_type === "Bearer") {
      request.headers["Authorization"] = `Bearer ${authDef.token.access_token}`;
      return;
    }
  }
};

const requestInterceptor = (request, ...args) => {
  if (request.loadSpec && schemaAuthNames.length > 0 && !schemaAuthFailed) {
    try {
      injectAuthCredentials(request);
    } catch (e) {
      console.error("schema auth injection failed with error: ", e);
    }
  }

  // Read the cookie at request time so login/logout rotation needs no manual
  // token copy. The cookie and the returned masked token are both accepted by
  // Django; they are not expected to be byte-identical.
  const method = (request.method || "GET").toUpperCase();
  if (!["GET", "HEAD", "OPTIONS", "TRACE"].includes(method)) {
    const csrfToken = getCsrfToken();
    if (csrfToken) {
      request.headers = request.headers || {};
      // Header names are case-insensitive. Swagger may already have added the
      // documented X-CSRFToken parameter under different casing, and sending
      // both produces a combined, invalid value. Replace the existing key.
      const existing = Object.keys(request.headers).find(
        (name) => name.toLowerCase() === csrfHeaderName.toLowerCase()
      );
      request.headers[existing || csrfHeaderName] = csrfToken;
    }
  }
  return request;
};

const ui = SwaggerUIBundle({
  url: "{{ schema_url|escapejs }}",
  dom_id: "#swagger-ui",
  presets: [SwaggerUIBundle.presets.apis],
  plugins,
  layout: "BaseLayout",
  requestInterceptor,
  responseInterceptor,
  ...swaggerSettings,
});

{% if oauth2_config %}ui.initOAuth({{ oauth2_config|safe }});{% endif %}

// Swagger UI renders operation parameters lazily, so keep any X-CSRFToken
// input in sync with the cookie as the page and its operations change.
const csrfObserver = new MutationObserver(() => syncCsrfHeaderInputs());
csrfObserver.observe(document.body, { childList: true, subtree: true });

// Swagger UI mounts operation parameters asynchronously and after token
// rotation, so also reconcile on a short interval. This only writes when the
// value differs and keeps the required header field ready to Execute.
setInterval(syncCsrfHeaderInputs, 500);

bootstrapCsrf().then(syncCsrfHeaderInputs);
syncCsrfHeaderInputs();
