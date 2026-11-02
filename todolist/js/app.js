// 진입점: 이벤트 바인딩
(function () {
  const store = window.TodoStore;
  const view = window.TodoRender;
  const { truncate } = window.TodoUtils;

  const $ = (id) => document.getElementById(id);
  const list = $('list');
  const input = $('newTodo');
  const darkQuery = window.matchMedia('(prefers-color-scheme: dark)');
  const PRIORITY_CYCLE = ['high', 'medium', 'low'];

  let wasAllDone = null;
  let toastTimer = null;
  let dragId = null;

  // ----- 렌더링 -----
  function captureFocus() {
    const active = document.activeElement;
    const item = active && active.closest ? active.closest('.item') : null;
    if (!item || !active.classList.length) return null;
    return { id: item.dataset.id, cls: active.classList[active.classList.length - 1] };
  }

  function restoreFocus(focus) {
    if (!focus) return;
    const target = list.querySelector(`.item[data-id="${CSS.escape(focus.id)}"] .${focus.cls}`);
    if (target) target.focus();
  }

  function isDark(theme) {
    return theme === 'dark' || (theme === 'system' && darkQuery.matches);
  }

  function applyTheme(theme) {
    if (theme === 'system') document.documentElement.removeAttribute('data-theme');
    else document.documentElement.setAttribute('data-theme', theme);
    const dark = isDark(theme);
    $('themeBtn').textContent = dark ? '☀️' : '🌙';
    $('themeBtn').setAttribute('aria-label', dark ? '라이트 모드로 전환' : '다크 모드로 전환');
  }

  function update(state) {
    const focus = captureFocus();
    applyTheme(state.theme);
    view.render(state, store);
    restoreFocus(focus);

    const { total, done } = store.getStats();
    const allDone = total > 0 && done === total;
    if (wasAllDone === false && allDone) view.celebrate();
    wasAllDone = allDone;
  }

  // ----- 토스트 -----
  function hideToast() {
    clearTimeout(toastTimer);
    view.hideToast();
    store.clearUndo();
  }

  function showUndoToast(todo) {
    clearTimeout(toastTimer);
    view.showToast(`"${truncate(todo.text, 20)}" 삭제됨`);
    toastTimer = setTimeout(hideToast, 5000);
  }

  // ----- 추가 -----
  function shake(node) {
    node.classList.remove('shake');
    void node.offsetWidth; // 애니메이션 재시작
    node.classList.add('shake');
  }

  input.addEventListener('animationend', () => input.classList.remove('shake'));

  $('addForm').addEventListener('submit', (e) => {
    e.preventDefault();
    if (!input.value.trim()) {
      shake(input);
      input.focus();
      return;
    }
    if (store.state.filter === 'done') store.setFilter('all'); // 새 항목이 보이도록
    store.addTodo(input.value, $('newPriority').value);
    input.value = '';
    input.focus();
  });

  // ----- 수정 -----
  function startEdit(item) {
    const id = item.dataset.id;
    const todo = store.find(id);
    if (!todo || item.classList.contains('editing')) return;

    const field = document.createElement('input');
    field.className = 'edit-input';
    field.maxLength = store.MAX_LEN;
    field.value = todo.text;
    field.setAttribute('aria-label', '할일 수정');

    item.classList.add('editing');
    item.draggable = false;
    item.querySelector('.text').replaceWith(field);
    field.focus();
    field.select();

    let finished = false;
    const finish = (save) => {
      if (finished) return;
      finished = true;
      const value = field.value.trim();
      if (save && value && value !== todo.text) store.updateTodo(id, { text: value });
      else update(store.state);
      const editBtn = list.querySelector(`.item[data-id="${CSS.escape(id)}"] .edit`);
      if (editBtn) editBtn.focus();
    };

    field.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        finish(true);
      } else if (e.key === 'Escape') {
        e.preventDefault();
        finish(false);
      }
    });
    field.addEventListener('blur', () => finish(true));
  }

  // ----- 삭제 -----
  function removeItem(item) {
    const id = item.dataset.id;
    const next = item.nextElementSibling || item.previousElementSibling;
    const nextId = next ? next.dataset.id : null;
    item.classList.add('leaving');
    setTimeout(() => {
      const removed = store.removeTodo(id);
      if (removed) showUndoToast(removed);
      const target = nextId && list.querySelector(`.item[data-id="${CSS.escape(nextId)}"] .check`);
      (target || input).focus();
    }, 160);
  }

  // ----- 목록 이벤트 (위임) -----
  list.addEventListener('change', (e) => {
    if (!e.target.classList.contains('check')) return;
    store.toggleTodo(e.target.closest('.item').dataset.id);
  });

  list.addEventListener('click', (e) => {
    const item = e.target.closest('.item');
    if (!item || item.classList.contains('leaving')) return;
    const id = item.dataset.id;

    if (e.target.closest('.dot')) {
      const todo = store.find(id);
      const next = PRIORITY_CYCLE[(PRIORITY_CYCLE.indexOf(todo.priority) + 1) % PRIORITY_CYCLE.length];
      store.updateTodo(id, { priority: next });
    } else if (e.target.closest('.edit')) {
      startEdit(item);
    } else if (e.target.closest('.delete')) {
      removeItem(item);
    }
  });

  list.addEventListener('dblclick', (e) => {
    if (e.target.classList.contains('text')) startEdit(e.target.closest('.item'));
  });

  list.addEventListener('keydown', (e) => {
    if (!e.altKey || (e.key !== 'ArrowUp' && e.key !== 'ArrowDown')) return;
    const item = e.target.closest('.item');
    if (!item || item.classList.contains('editing')) return;
    e.preventDefault();
    store.move(item.dataset.id, e.key === 'ArrowUp' ? -1 : 1);
  });

  // ----- 드래그 앤 드롭 (같은 우선순위 안에서만) -----
  function clearDropMarks() {
    list.querySelectorAll('.drop-before, .drop-after').forEach((n) => n.classList.remove('drop-before', 'drop-after'));
  }

  list.addEventListener('dragstart', (e) => {
    const item = e.target.closest && e.target.closest('.item');
    if (!item || item.classList.contains('editing')) return;
    dragId = item.dataset.id;
    item.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', dragId);
  });

  list.addEventListener('dragover', (e) => {
    const item = e.target.closest('.item');
    clearDropMarks();
    if (!dragId || !item || item.dataset.id === dragId) return;
    const drag = store.find(dragId);
    if (!drag || drag.priority !== item.dataset.priority) return;
    e.preventDefault();
    const rect = item.getBoundingClientRect();
    item.classList.add(e.clientY > rect.top + rect.height / 2 ? 'drop-after' : 'drop-before');
  });

  list.addEventListener('drop', (e) => {
    const item = e.target.closest('.item');
    if (!dragId || !item) return;
    e.preventDefault();
    store.reorder(dragId, item.dataset.id, item.classList.contains('drop-after'));
  });

  list.addEventListener('dragend', () => {
    dragId = null;
    clearDropMarks();
    const dragging = list.querySelector('.dragging');
    if (dragging) dragging.classList.remove('dragging');
  });

  // ----- 필터 / 일괄 삭제 -----
  document.querySelectorAll('[data-filter]').forEach((btn) => {
    btn.addEventListener('click', () => store.setFilter(btn.dataset.filter));
  });

  $('clearDone').addEventListener('click', () => {
    const { done } = store.getStats();
    if (done && confirm(`완료한 할일 ${done}개를 지울까요?`)) store.clearDone();
  });

  // ----- 토스트 / 이월 -----
  $('toastUndo').addEventListener('click', () => {
    store.undoRemove();
    hideToast();
  });

  $('carryYes').addEventListener('click', () => store.resolveCarryOver(true));
  $('carryNo').addEventListener('click', () => store.resolveCarryOver(false));

  // ----- 테마 -----
  $('themeBtn').addEventListener('click', () => {
    const wantDark = !isDark(store.state.theme);
    // 시스템 설정과 같아지면 다시 시스템을 따른다
    store.setTheme(wantDark === darkQuery.matches ? 'system' : wantDark ? 'dark' : 'light');
  });
  darkQuery.addEventListener('change', () => applyTheme(store.state.theme));

  // ----- 지난 기록 -----
  const dialog = $('historyDialog');
  $('historyBtn').addEventListener('click', () => {
    view.renderHistory(store.getHistory());
    dialog.showModal();
  });
  $('historyClose').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', (e) => {
    if (e.target === dialog) dialog.close(); // 바깥(backdrop) 클릭
  });

  // ----- 날짜 변경 / 다른 탭 동기화 -----
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) store.refreshDay();
  });
  window.addEventListener('focus', () => store.refreshDay());
  setInterval(() => store.refreshDay(), 60 * 1000);

  window.addEventListener('storage', (e) => {
    if (e.key === null || e.key.startsWith('todolist:v1:')) store.syncFromStorage();
  });

  // ----- 시작 -----
  store.load();
  store.subscribe(update);
  update(store.state);
})();
