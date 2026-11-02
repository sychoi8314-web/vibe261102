// 상태 관리 + localStorage 입출력
(function () {
  const { todayKey, addDays, uid } = window.TodoUtils;

  const KEYS = {
    todos: 'todolist:v1:todos',
    settings: 'todolist:v1:settings',
    lastVisit: 'todolist:v1:lastVisit',
  };
  const MAX_LEN = 100;
  const RETENTION_DAYS = 30; // 지난 기록 보관 기간
  const PRIORITY_RANK = { high: 0, medium: 1, low: 2 };
  const FILTERS = ['all', 'active', 'done'];
  const THEMES = ['system', 'light', 'dark'];

  const state = {
    today: todayKey(),
    todos: [],
    filter: 'all',
    theme: 'system',
    storageOk: true,
    carryFrom: null,       // 이월 제안 대상 날짜
    carryCandidates: [],   // 이월 제안 대상 할일
  };

  let lastRemoved = null;
  const listeners = [];

  // ----- 저장소 -----
  function read(key) {
    try {
      return localStorage.getItem(key);
    } catch {
      state.storageOk = false;
      return null;
    }
  }

  function write(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch {
      state.storageOk = false;
    }
  }

  function probeStorage() {
    try {
      const key = 'todolist:v1:probe';
      localStorage.setItem(key, '1');
      localStorage.removeItem(key);
      return true;
    } catch {
      return false;
    }
  }

  function safeJson(raw) {
    try {
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }

  function normalize(t) {
    const todo = {
      id: t.id,
      text: String(t.text).slice(0, MAX_LEN),
      done: !!t.done,
      priority: t.priority in PRIORITY_RANK ? t.priority : 'medium',
      date: t.date,
      order: Number.isFinite(t.order) ? t.order : 0,
      createdAt: Number.isFinite(t.createdAt) ? t.createdAt : 0,
    };
    if (t.completedAt) todo.completedAt = t.completedAt;
    if (t.carried) todo.carried = true;
    return todo;
  }

  function parseTodos(raw) {
    if (!raw) return [];
    try {
      const list = JSON.parse(raw);
      if (!Array.isArray(list)) throw new Error('not an array');
      return list
        .filter((t) => t && typeof t.id === 'string' && typeof t.text === 'string' && typeof t.date === 'string')
        .map(normalize);
    } catch {
      // 손상된 데이터는 백업 키로 옮기고 빈 목록으로 시작
      write(`${KEYS.todos}:corrupt-${Date.now()}`, raw);
      return [];
    }
  }

  function readSettings() {
    const settings = safeJson(read(KEYS.settings)) || {};
    if (THEMES.includes(settings.theme)) state.theme = settings.theme;
    if (FILTERS.includes(settings.filter)) state.filter = settings.filter;
  }

  function persist() {
    write(KEYS.todos, JSON.stringify(state.todos));
    write(KEYS.settings, JSON.stringify({ theme: state.theme, filter: state.filter }));
  }

  function emit() {
    listeners.forEach((fn) => fn(state));
  }

  function commit() {
    persist();
    emit();
  }

  // ----- 날짜 처리 -----
  function prune() {
    const cutoff = addDays(state.today, -RETENTION_DAYS);
    state.todos = state.todos.filter((t) => t.date >= cutoff);
  }

  function carryCandidatesOf(date) {
    return state.todos.filter((t) => t.date === date && !t.done && !t.carried);
  }

  function checkCarryOver() {
    const lastVisit = read(KEYS.lastVisit);
    state.carryFrom = null;
    state.carryCandidates = [];
    if (lastVisit && lastVisit < state.today) {
      const candidates = carryCandidatesOf(lastVisit);
      if (candidates.length) {
        state.carryFrom = lastVisit;
        state.carryCandidates = candidates;
        return; // 사용자가 답할 때까지 lastVisit을 유지
      }
    }
    write(KEYS.lastVisit, state.today);
  }

  // ----- 조회 -----
  function compare(a, b) {
    return (
      PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority] ||
      a.order - b.order ||
      a.createdAt - b.createdAt
    );
  }

  function find(id) {
    return state.todos.find((t) => t.id === id);
  }

  function todayTodos() {
    return state.todos.filter((t) => t.date === state.today).sort(compare);
  }

  function getTodayTodos(filter = state.filter) {
    const list = todayTodos();
    if (filter === 'active') return list.filter((t) => !t.done);
    if (filter === 'done') return list.filter((t) => t.done);
    return list;
  }

  function getStats() {
    const list = todayTodos();
    return { total: list.length, done: list.filter((t) => t.done).length };
  }

  function getHistory() {
    const byDate = new Map();
    state.todos
      .filter((t) => t.date < state.today)
      .forEach((t) => {
        if (!byDate.has(t.date)) byDate.set(t.date, []);
        byDate.get(t.date).push(t);
      });
    return [...byDate.keys()]
      .sort()
      .reverse()
      .map((date) => ({ date, todos: byDate.get(date).sort(compare) }));
  }

  function nextOrder() {
    return state.todos.reduce((max, t) => (t.date === state.today ? Math.max(max, t.order) : max), 0) + 1;
  }

  // ----- 변경 -----
  function load() {
    state.storageOk = probeStorage();
    state.today = todayKey();
    state.todos = parseTodos(read(KEYS.todos));
    readSettings();
    prune();
    checkCarryOver();
    persist();
  }

  function addTodo(text, priority = 'medium') {
    const clean = String(text).trim().slice(0, MAX_LEN);
    if (!clean) return null;
    const todo = {
      id: uid(),
      text: clean,
      done: false,
      priority: priority in PRIORITY_RANK ? priority : 'medium',
      date: state.today,
      order: nextOrder(),
      createdAt: Date.now(),
    };
    state.todos.push(todo);
    commit();
    return todo;
  }

  function toggleTodo(id) {
    const todo = find(id);
    if (!todo) return;
    todo.done = !todo.done;
    if (todo.done) todo.completedAt = Date.now();
    else delete todo.completedAt;
    commit();
  }

  function updateTodo(id, patch) {
    const todo = find(id);
    if (!todo) return;
    if (typeof patch.text === 'string') {
      const clean = patch.text.trim().slice(0, MAX_LEN);
      if (clean) todo.text = clean; // 빈 값이면 원래 값 유지
    }
    if (patch.priority in PRIORITY_RANK && patch.priority !== todo.priority) {
      todo.priority = patch.priority;
      todo.order = nextOrder(); // 새 그룹의 맨 뒤로
    }
    commit();
  }

  function removeTodo(id) {
    const index = state.todos.findIndex((t) => t.id === id);
    if (index < 0) return null;
    const [todo] = state.todos.splice(index, 1);
    lastRemoved = { todo, index };
    commit();
    return todo;
  }

  function undoRemove() {
    if (!lastRemoved) return;
    const { todo, index } = lastRemoved;
    state.todos.splice(Math.min(index, state.todos.length), 0, todo);
    lastRemoved = null;
    commit();
  }

  function clearUndo() {
    lastRemoved = null;
  }

  function clearDone() {
    const before = state.todos.length;
    state.todos = state.todos.filter((t) => !(t.date === state.today && t.done));
    lastRemoved = null;
    commit();
    return before - state.todos.length;
  }

  function renumber(group) {
    group.forEach((t, i) => {
      t.order = i + 1;
    });
  }

  // 같은 우선순위 그룹 안에서만 순서를 바꾼다
  function reorder(dragId, targetId, placeAfter) {
    const drag = find(dragId);
    const target = find(targetId);
    if (!drag || !target || drag === target || drag.priority !== target.priority) return;
    const group = todayTodos().filter((t) => t.priority === drag.priority && t !== drag);
    group.splice(group.indexOf(target) + (placeAfter ? 1 : 0), 0, drag);
    renumber(group);
    commit();
  }

  function move(id, direction) {
    const todo = find(id);
    if (!todo) return false;
    const group = todayTodos().filter((t) => t.priority === todo.priority);
    const from = group.indexOf(todo);
    const to = from + direction;
    if (to < 0 || to >= group.length) return false;
    [group[from], group[to]] = [group[to], group[from]];
    renumber(group);
    commit();
    return true;
  }

  function resolveCarryOver(accept) {
    if (accept) {
      let order = nextOrder();
      carryCandidatesOf(state.carryFrom).forEach((t) => {
        t.carried = true;
        state.todos.push({
          id: uid(),
          text: t.text,
          done: false,
          priority: t.priority,
          date: state.today,
          order: order++,
          createdAt: Date.now(),
        });
      });
    }
    state.carryFrom = null;
    state.carryCandidates = [];
    write(KEYS.lastVisit, state.today);
    commit();
  }

  function setFilter(filter) {
    if (!FILTERS.includes(filter) || filter === state.filter) return;
    state.filter = filter;
    commit();
  }

  function setTheme(theme) {
    if (!THEMES.includes(theme)) return;
    state.theme = theme;
    commit();
  }

  // 자정이 지났으면 오늘 날짜를 갱신
  function refreshDay() {
    const now = todayKey();
    if (now === state.today) return false;
    state.today = now;
    prune();
    checkCarryOver();
    commit();
    return true;
  }

  // 다른 탭에서 변경된 내용 반영
  function syncFromStorage() {
    state.todos = parseTodos(read(KEYS.todos));
    readSettings();
    const lastVisit = read(KEYS.lastVisit);
    if (lastVisit === state.today) {
      state.carryFrom = null;
      state.carryCandidates = [];
    } else if (state.carryFrom) {
      state.carryCandidates = carryCandidatesOf(state.carryFrom);
    }
    emit();
  }

  function subscribe(fn) {
    listeners.push(fn);
  }

  window.TodoStore = {
    state,
    MAX_LEN,
    load,
    subscribe,
    find,
    getTodayTodos,
    getStats,
    getHistory,
    addTodo,
    toggleTodo,
    updateTodo,
    removeTodo,
    undoRemove,
    clearUndo,
    clearDone,
    reorder,
    move,
    resolveCarryOver,
    setFilter,
    setTheme,
    refreshDay,
    syncFromStorage,
  };
})();
