(() => {
  const MIN_QUERY_LENGTH = 2;
  const SEARCH_DEBOUNCE_MS = 280;

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-channel-search]").forEach((panel) => {
      initChannelSearch(panel);
    });
  });

  function initChannelSearch(panel) {
    const toggle = document.querySelector(`[aria-controls="${panel.id}"]`);
    const searchForm = panel.querySelector("[data-channel-search-form]");
    const searchInput = panel.querySelector("[data-channel-search-input]");
    const status = panel.querySelector("[data-channel-search-status]");
    const resultsList = panel.querySelector("[data-channel-search-results]");
    const addForm = panel.querySelector("[data-channel-add-form]");
    const channelIdInput = panel.querySelector("[data-channel-id-input]");
    const channelLabelInput = panel.querySelector("[data-channel-label-input]");
    const selectedLabel = panel.querySelector("[data-channel-selected-label]");
    const aliasInput = panel.querySelector("[data-channel-alias-input]");
    const saveButton = panel.querySelector("[data-channel-save-button]");
    const searchUrl = panel.dataset.searchUrl;
    let searchTimer = 0;
    let searchController = null;
    let requestSerial = 0;
    let suggestedAlias = "";

    if (
      !toggle ||
      !searchForm ||
      !searchInput ||
      !status ||
      !resultsList ||
      !addForm ||
      !channelIdInput ||
      !channelLabelInput ||
      !selectedLabel ||
      !aliasInput ||
      !saveButton ||
      !searchUrl
    ) {
      return;
    }

    toggle.addEventListener("click", () => {
      const willOpen = panel.hidden;
      setPanelOpen(panel, toggle, willOpen);
      if (willOpen) {
        searchInput.focus();
      }
    });

    searchForm.addEventListener("submit", (event) => {
      event.preventDefault();
      runSearch(panel, {
        addForm,
        aliasInput,
        channelIdInput,
        channelLabelInput,
        resultsList,
        searchControllerRef: {
          get: () => searchController,
          set: (controller) => {
            searchController = controller;
          },
        },
        searchInput,
        searchUrl,
        selectedLabel,
        setSuggestedAlias: (value) => {
          suggestedAlias = value;
        },
        status,
        requestSerialRef: {
          next: () => {
            requestSerial += 1;
            return requestSerial;
          },
          current: () => requestSerial,
        },
      });
    });

    searchInput.addEventListener("input", () => {
      window.clearTimeout(searchTimer);
      searchTimer = window.setTimeout(() => {
        runSearch(panel, {
          addForm,
          aliasInput,
          channelIdInput,
          channelLabelInput,
          resultsList,
          searchControllerRef: {
            get: () => searchController,
            set: (controller) => {
              searchController = controller;
            },
          },
          searchInput,
          searchUrl,
          selectedLabel,
          setSuggestedAlias: (value) => {
            suggestedAlias = value;
          },
          status,
          requestSerialRef: {
            next: () => {
              requestSerial += 1;
              return requestSerial;
            },
            current: () => requestSerial,
          },
        });
      }, SEARCH_DEBOUNCE_MS);
    });

    addForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      saveButton.disabled = true;
      setStatus(status, "", false);
      try {
        const response = await fetch(addForm.action, {
          method: "POST",
          headers: { Accept: "application/json" },
          body: new FormData(addForm),
        });
        const payload = await response.json();
        if (!response.ok) {
          setStatus(status, payload.detail || panel.dataset.errorMessage, true);
          return;
        }
        appendChannel(payload.alias, payload.channel_id);
        showNotice(payload.message, "success");
        resetChannelSearch({
          addForm,
          aliasInput,
          channelIdInput,
          channelLabelInput,
          panel,
          resultsList,
          searchInput,
          selectedLabel,
          status,
          toggle,
        });
      } catch {
        setStatus(status, panel.dataset.errorMessage, true);
      } finally {
        saveButton.disabled = false;
      }
    });

    resultsList.addEventListener("click", (event) => {
      const button = event.target.closest("[data-channel-id]");
      if (!button) {
        return;
      }
      const result = {
        id: button.dataset.channelId || "",
        label: button.dataset.channelLabel || "",
        name: button.dataset.channelName || "",
      };
      selectResult({
        addForm,
        aliasInput,
        button,
        channelIdInput,
        channelLabelInput,
        result,
        resultsList,
        searchInput,
        selectedLabel,
        setSuggestedAlias: (value) => {
          suggestedAlias = value;
        },
        suggestedAlias,
      });
    });
  }

  async function runSearch(panel, options) {
    const query = options.searchInput.value.trim();
    if (query.length < MIN_QUERY_LENGTH) {
      const activeController = options.searchControllerRef.get();
      if (activeController) {
        activeController.abort();
      }
      clearResults(options.resultsList);
      options.addForm.hidden = true;
      setStatus(options.status, panel.dataset.minQueryMessage, false);
      return;
    }

    const serial = options.requestSerialRef.next();
    const activeController = options.searchControllerRef.get();
    if (activeController) {
      activeController.abort();
    }
    const controller = new AbortController();
    options.searchControllerRef.set(controller);
    setStatus(options.status, panel.dataset.loadingMessage, false);

    try {
      const url = `${options.searchUrl}?q=${encodeURIComponent(query)}`;
      const response = await fetch(url, {
        headers: { Accept: "application/json" },
        signal: controller.signal,
      });
      const payload = await response.json();
      if (serial !== options.requestSerialRef.current()) {
        return;
      }
      if (!response.ok) {
        clearResults(options.resultsList);
        options.addForm.hidden = true;
        setStatus(options.status, payload.detail || panel.dataset.errorMessage, true);
        return;
      }
      renderResults(payload.results || [], {
        addForm: options.addForm,
        aliasInput: options.aliasInput,
        channelIdInput: options.channelIdInput,
        channelLabelInput: options.channelLabelInput,
        emptyMessage: panel.dataset.emptyMessage,
        resultsList: options.resultsList,
        searchInput: options.searchInput,
        selectedLabel: options.selectedLabel,
        setSuggestedAlias: options.setSuggestedAlias,
        status: options.status,
      });
    } catch (error) {
      if (error.name === "AbortError") {
        return;
      }
      clearResults(options.resultsList);
      options.addForm.hidden = true;
      setStatus(options.status, panel.dataset.errorMessage, true);
    }
  }

  function renderResults(results, options) {
    clearResults(options.resultsList);
    options.addForm.hidden = true;
    if (results.length === 0) {
      setStatus(options.status, options.emptyMessage, false);
      return;
    }

    results.forEach((result) => {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.className = "channel-result-button";
      button.type = "button";
      button.dataset.channelId = result.id || "";
      button.dataset.channelName = result.name || "";
      button.dataset.channelLabel = result.label || result.name || result.id || "";
      button.textContent = result.label || result.name || result.id;
      item.append(button);
      options.resultsList.append(item);
    });
    options.resultsList.hidden = false;
    setStatus(options.status, "", false);
  }

  function selectResult(options) {
    options.resultsList.querySelectorAll(".channel-result-button").forEach((button) => {
      button.classList.remove("active");
    });
    options.button.classList.add("active");
    options.channelIdInput.value = options.result.id;
    options.channelLabelInput.value = options.result.label;
    options.selectedLabel.textContent = options.result.label;
    options.addForm.hidden = false;

    const nextAlias = options.result.name || options.searchInput.value.trim();
    const currentAlias = options.aliasInput.value.trim();
    if (!currentAlias || currentAlias === options.suggestedAlias || currentAlias === options.searchInput.value.trim()) {
      options.aliasInput.value = nextAlias;
      options.setSuggestedAlias(nextAlias);
    }
    options.aliasInput.focus();
  }

  function clearResults(resultsList) {
    resultsList.replaceChildren();
    resultsList.hidden = true;
  }

  function setPanelOpen(panel, toggle, isOpen) {
    panel.hidden = !isOpen;
    toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
  }

  function setStatus(status, message, isError) {
    status.textContent = message || "";
    status.classList.toggle("notice-inline-error", isError);
  }

  function appendChannel(alias, channelId) {
    const channelList = document.querySelector("[data-channel-list]");
    const emptyMessage = document.querySelector("[data-channel-empty]");
    if (channelList) {
      const item = document.createElement("li");
      const title = document.createElement("strong");
      const detail = document.createElement("span");
      title.textContent = alias;
      detail.textContent = channelId;
      item.append(title, detail);
      channelList.append(item);
      channelList.hidden = false;
    }
    if (emptyMessage) {
      emptyMessage.hidden = true;
    }

    const defaultSelect = document.querySelector("#channel_alias");
    if (defaultSelect && !defaultSelect.querySelector(`option[value="${cssEscape(alias)}"]`)) {
      const option = document.createElement("option");
      option.value = alias;
      option.textContent = alias;
      defaultSelect.append(option);
    }

    const defaultFormButton = document.querySelector(".target-form button[type='submit']");
    const botSelect = document.querySelector("#bot_alias");
    if (
      defaultFormButton &&
      botSelect &&
      defaultSelect &&
      botSelect.options.length > 0 &&
      defaultSelect.options.length > 0
    ) {
      defaultFormButton.disabled = false;
    }
  }

  function showNotice(message, kind) {
    const main = document.querySelector("main");
    if (!main || !message) {
      return;
    }
    main.querySelectorAll("[data-dynamic-notice]").forEach((notice) => notice.remove());
    const notice = document.createElement("section");
    notice.dataset.dynamicNotice = "";
    notice.className = `notice-banner notice-${kind}`;
    notice.setAttribute("role", kind === "success" ? "status" : "alert");
    notice.textContent = message;
    main.prepend(notice);
  }

  function resetChannelSearch(options) {
    options.searchInput.value = "";
    options.aliasInput.value = "";
    options.channelIdInput.value = "";
    options.channelLabelInput.value = "";
    options.selectedLabel.textContent = "";
    clearResults(options.resultsList);
    options.addForm.hidden = true;
    setStatus(options.status, options.panel.dataset.minQueryMessage, false);
    setPanelOpen(options.panel, options.toggle, false);
  }

  function cssEscape(value) {
    if (window.CSS && typeof window.CSS.escape === "function") {
      return window.CSS.escape(value);
    }
    return value.replace(/"/g, '\\"');
  }
})();
