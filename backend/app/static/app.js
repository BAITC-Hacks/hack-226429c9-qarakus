document.querySelectorAll('[data-ai-explain]').forEach((button) => {
  button.addEventListener('click', async () => {
    const panel = button.closest('[data-ai-panel]');
    const text = panel.querySelector('[data-ai-text]');
    const status = panel.querySelector('[data-ai-status]');
    const trace = panel.querySelector('[data-ai-trace]');
    button.disabled = true;
    panel.setAttribute('aria-busy', 'true');
    status.textContent = button.dataset.loading;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 9500);
    try {
      const response = await fetch(button.dataset.aiExplain, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRF-Token': button.dataset.csrf},
        signal: controller.signal,
      });
      if (!response.ok) throw new Error('Explanation unavailable');
      const result = await response.json();
      if (result.source === 'llm-agentic') {
        text.textContent = result.text;
        trace.replaceChildren(...result.tool_labels.map((label) => {
          const item = document.createElement('li');
          item.textContent = label;
          return item;
        }));
        status.textContent = button.dataset.done;
      } else {
        status.textContent = button.dataset.fallback;
        button.disabled = false;
      }
    } catch {
      status.textContent = button.dataset.fallback;
      button.disabled = false;
    } finally {
      clearTimeout(timeout);
      panel.removeAttribute('aria-busy');
    }
  });
});
